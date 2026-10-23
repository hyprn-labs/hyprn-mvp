"""Explicit PostgreSQL authority and request-local transactions.

No ambient database authority is granted by constructing a Store. Authentication
has a separate, read-only credential lookup role; ordinary connections are scoped
to the verified actor by the API boundary. Connections are never shared by requests.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
import ssl
import socket
from threading import Condition
import time


class DatabaseConflict(RuntimeError):
    """The database rejected an integrity constraint."""


class DatabaseUnavailable(RuntimeError):
    """The database could not complete a transaction."""


class DatabasePermissionDenied(RuntimeError):
    """The database authority or transaction scope refused an operation."""


_actor = ContextVar('hyprn_database_actor', default=None)
_analysis = ContextVar('hyprn_database_analysis', default=None)
_analysis_child = ContextVar('hyprn_database_analysis_child', default=False)


@contextmanager
def analysis_scope(study_id, command_id):
    """Private owner context for one accepted finite plan, never an HTTP credential.

    PostgreSQL independently checks the retained receipt and current authority.
    Application command admission additionally restricts exact member identities.
    """
    current = _analysis.get()
    value = (study_id, command_id)
    if current is not None and current != value:
        raise ValueError('An accepted analysis scope cannot change')
    token = _analysis.set(value)
    try:
        yield
    finally:
        _analysis.reset(token)


@contextmanager
def analysis_child_scope():
    token = _analysis_child.set(True)
    try:
        yield
    finally:
        _analysis_child.reset(token)


@contextmanager
def actor_scope(actor_id, *, request_boundary=False):
    """Bind verified authority, propagated by AnyIO into synchronous route threads."""
    current = _actor.get()
    if current is not None and current != actor_id and not request_boundary:
        raise ValueError('A database identity scope cannot change')
    token = _actor.set(actor_id)
    try:
        yield
    finally:
        _actor.reset(token)


@dataclass(frozen=True)
class PostgreSQLCredentials:
    host: str
    database: str
    user: str
    password: str = field(repr=False)
    port: int = 5432
    tls: bool = True
    ca_file: str | None = None
    server_name: str | None = None

    def connect(self):
        import pg8000.dbapi

        # PEP-249 declares paramstyle at module level. All callers of this driver
        # use the same fixed binding convention; it never varies by request.
        pg8000.dbapi.paramstyle = 'qmark'
        # Cloud SQL can route to a private IP while its verified certificate
        # names a DNS endpoint. Preserve both identities; never disable hostname
        # checking to make a private-IP connection succeed.
        sock = socket.create_connection((self.host, self.port), 15) if self.server_name else None
        try:
            return pg8000.dbapi.connect(
                host=self.server_name or self.host,
                database=self.database,
                user=self.user,
                password=self.password,
                port=self.port,
                timeout=15,
                sock=sock,
                ssl_context=ssl.create_default_context(cafile=self.ca_file) if self.tls else False,
            )
        except BaseException:
            if sock is not None:
                sock.close()
            raise


class Row(dict):
    """Named and positional DB-API row access, preserving column order."""

    def __getitem__(self, key):
        return tuple(self.values())[key] if isinstance(key, int) else super().__getitem__(key)


class Rows:
    def __init__(self, cursor):
        self.cursor = cursor
        self.rowcount = cursor.rowcount
        self.names = [column[0] for column in cursor.description or ()]

    def fetchone(self):
        row = self.cursor.fetchone()
        return None if row is None else Row(zip(self.names, row))

    def fetchall(self):
        return [Row(zip(self.names, row)) for row in self.cursor.fetchall()]

    def __iter__(self):
        return iter(self.fetchall())


class Connection:
    """DB-API qmark binding, with no SQL rewriting or literal interpolation."""

    dialect = 'postgresql'

    def __init__(self, connection):
        self.raw = connection

    def execute(self, statement, parameters=()):
        import pg8000.dbapi

        try:
            cursor = self.raw.cursor()
            cursor.execute(statement, parameters)
            return Rows(cursor)
        except OSError as error:
            raise DatabaseUnavailable('Database transport unavailable; reconcile outcome') from error
        except pg8000.dbapi.IntegrityError as error:
            raise DatabaseConflict('Database integrity constraint refused') from error
        except pg8000.dbapi.InterfaceError as error:
            raise DatabaseUnavailable('Database connection unavailable') from error
        except pg8000.dbapi.DatabaseError as error:
            code = (
                error.args[0].get('C') if error.args and isinstance(error.args[0], dict) else None
            )
            if code in {'42501', '25006'}:
                raise DatabasePermissionDenied('Database operation not permitted') from error
            if code and code.startswith('23'):
                raise DatabaseConflict('Database integrity constraint refused') from error
            if code in {'40001', '40P01', '55P03', '57014'} or (code and code.startswith('08')):
                raise DatabaseUnavailable('Database transaction unavailable') from error
            raise


class _ConnectionPool:
    """Bounded transport reuse for one authority; never reuse transaction state.

    Checkout is exclusive. Failed transactions/connections are discarded without
    replay, including ambiguous commits. DISCARD ALL clears session settings,
    prepared statements and session locks before another caller can use a socket.
    """

    def __init__(self, credentials, *, maximum=8, wait_seconds=5):
        self.credentials = credentials
        self.maximum, self.wait_seconds = maximum, wait_seconds
        self.condition = Condition()
        self.idle = []
        self.count = 0
        self.closed = False

    @contextmanager
    def checkout(self):
        deadline = time.monotonic() + self.wait_seconds
        with self.condition:
            while not self.closed and not self.idle and self.count >= self.maximum:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise DatabaseUnavailable('Database connection capacity unavailable')
                self.condition.wait(remaining)
            if self.closed:
                raise DatabaseUnavailable('Database connections are closed')
            raw = self.idle.pop() if self.idle else None
            if raw is None:
                self.count += 1
        reusable = False
        try:
            if raw is not None:
                try:
                    raw.autocommit = True
                    cursor = raw.cursor()
                    try:
                        cursor.execute('SELECT 1')
                        cursor.fetchall()
                    finally:
                        cursor.close()
                    raw.autocommit = False
                except Exception:
                    try:
                        raw.close()
                    except Exception:
                        pass
                    raw = None
            if raw is None:
                try:
                    raw = self.credentials.connect()
                except OSError as error:
                    raise DatabaseUnavailable('Database connection unavailable') from error
            yield raw
            try:
                raw.rollback()
                raw.autocommit = True
                cursor = raw.cursor()
                try:
                    cursor.execute('DISCARD ALL')
                finally:
                    cursor.close()
                raw.autocommit = False
                reusable = True
            except Exception:
                # A cleanup failure must not turn an acknowledged commit into
                # an ambiguous operation. Discard the transport, not its result.
                pass
        finally:
            with self.condition:
                if reusable and not self.closed:
                    self.idle.append(raw)
                else:
                    self.count -= 1
                    if raw is not None:
                        try:
                            raw.close()
                        except Exception:
                            pass
                self.condition.notify()

    def close(self):
        with self.condition:
            self.closed = True
            idle, self.idle = self.idle, []
            self.count -= len(idle)
            self.condition.notify_all()
        for raw in idle:
            try:
                raw.close()
            except Exception:
                pass


class PostgreSQL:
    dialect = 'postgresql'
    schema_profile = 'full'

    def __init__(self, request, authentication, background=None):
        self.request = request
        self.authentication = authentication
        self.background = background
        self._request_pool = _ConnectionPool(request)
        self._authentication_pool = _ConnectionPool(authentication, maximum=2)
        self._background_pool = (
            _ConnectionPool(background, maximum=2) if background is not None else None
        )
        try:
            self._inspect_authority()
        except BaseException:
            self.close()
            raise

    def _inspect_authority(self):
        background = self.background
        if background is not None:
            if background.user not in {'hyprn_assistant_background', 'hyprn_dispatcher_background'}:
                raise ValueError('Unknown background authority')
            with self.background_connection() as db:
                elevated = db.execute(
                    "SELECT 1 FROM pg_roles WHERE pg_has_role(current_user,oid,'MEMBER') "
                    "AND (rolsuper OR rolbypassrls OR rolcreaterole OR rolname IN "
                    "('hyprn_request','hyprn_auth','hyprn_migration') OR "
                    "(rolname<>current_user AND rolname IN "
                    "('hyprn_assistant_background','hyprn_dispatcher_background')))"
                ).fetchone()
                tables = db.execute(
                    "SELECT 1 FROM pg_tables WHERE schemaname='public' AND "
                    "(has_table_privilege(current_user,quote_ident(schemaname)||'.'||quote_ident(tablename),'SELECT,INSERT,UPDATE,DELETE') "
                    "OR pg_has_role(current_user,tableowner,'MEMBER'))"
                ).fetchone()
                if elevated or tables:
                    raise ValueError('Background authority must have only purpose function access')
        # Authority inspection uses read-only request authority, never migrations.
        with self.connection() as db:
            role = db.execute(
                'SELECT rolsuper, rolbypassrls, rolcreaterole FROM pg_roles '
                'WHERE rolname=current_user'
            ).fetchone()
            owns = db.execute(
                "SELECT 1 FROM pg_tables WHERE schemaname='public' "
                "AND pg_has_role(current_user,tableowner,'MEMBER')"
            ).fetchone()
            elevated = db.execute(
                "SELECT 1 FROM pg_roles WHERE pg_has_role(current_user,oid,'MEMBER') "
                "AND (rolsuper OR rolbypassrls OR rolcreaterole OR rolname IN "
                "('hyprn_auth','hyprn_assistant_background','hyprn_dispatcher_background'))"
            ).fetchone()
            privileged = role['rolsuper'] or role['rolbypassrls'] or role['rolcreaterole']
            if privileged or owns or elevated:
                raise ValueError('Request role must not own tables or bypass row policies')

    @contextmanager
    def connection(self, write=False, *, authentication=False):
        pool = self._authentication_pool if authentication else self._request_pool
        with pool.checkout() as raw:
            with self._transaction(raw, write=write, authentication=authentication) as db:
                yield db

    @contextmanager
    def _transaction(self, raw, *, write, authentication=False, background=False):
        db = Connection(raw)
        try:
            db.execute('BEGIN')
            if not write:
                db.execute('SET TRANSACTION READ ONLY')
            if not authentication and not background:
                db.execute("SELECT set_config('hyprn.actor_id', ?, true)", (_actor.get() or '',))
                if _analysis.get() is not None:
                    study_id, command_id = _analysis.get()
                    db.execute("SELECT set_config('hyprn.analysis_study', ?, true), "
                               "set_config('hyprn.analysis_command', ?, true)",
                               (study_id, command_id))
                    db.execute("SELECT set_config('hyprn.analysis_child', ?, true)",
                               ('true' if _analysis_child.get() else 'false',))
                if write:
                    # The single writer serializes short write transactions. Domain
                    # CAS and receipts observe the prior accepted commit; no native
                    # or provider call holds this transaction lock.
                    # Cancel contention server-side before the 15-second socket
                    # deadline, preserving an unambiguous transaction rollback.
                    db.execute("SET LOCAL lock_timeout = '5s'")
                    db.execute('SELECT pg_advisory_xact_lock(68272601)')
            yield db
            raw.commit()
        except BaseException as primary:
            try:
                raw.rollback()
            except Exception as cleanup:
                # Preserve the statement/commit failure. A lost transport during
                # cleanup cannot establish whether a commit was acknowledged.
                primary.add_note('Transaction rollback also failed: ' + type(cleanup).__name__)
            if isinstance(primary, OSError):
                raise DatabaseUnavailable(
                    'Database transport unavailable; reconcile outcome') from primary
            raise

    @contextmanager
    def background_connection(self, *, write=False):
        if self.background is None:
            raise DatabasePermissionDenied('Explicit background authority required')
        with self._background_pool.checkout() as raw:
            with self._transaction(raw, write=write, background=True) as db:
                yield db

    def close(self):
        for pool in (self._request_pool, self._authentication_pool, self._background_pool):
            if pool is not None:
                pool.close()
