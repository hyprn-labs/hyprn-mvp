"""Explicit hosted database credentials and process fencing; no initialization."""

import hashlib
import json
import os
from pathlib import Path
import stat
from threading import Lock
from contextlib import contextmanager

from hyprn_mvp_app.database import Connection, PostgreSQLCredentials


def required(environ, name):
    value = environ.get('HYPRN_MVP_' + name)
    if not isinstance(value, str) or not value:
        raise ValueError('Hosted configuration is incomplete')
    return value


def credentials(environ, role, alias):
    from hyprn_mvp_app.assistant.claude import credential
    if required(environ, 'DATABASE_SSLMODE') != 'verify-full':
        raise ValueError('Hosted configuration requires verified database TLS')
    ca = Path(required(environ, 'DATABASE_CA_FILE'))
    if hashlib.sha256(ca.read_bytes()).hexdigest() != required(environ, 'DATABASE_CA_SHA256'):
        raise ValueError('Hosted configuration database trust differs')
    path = environ.get('HYPRN_SECRET_' + alias + '_FILE')
    if not path:
        raise ValueError('Hosted configuration credential is absent')
    return PostgreSQLCredentials(
        host=required(environ, 'DATABASE_HOST'), database=required(environ, 'DATABASE_NAME'),
        user=role, password=credential(path), port=int(required(environ, 'DATABASE_PORT')),
        ca_file=str(ca), server_name=required(environ, 'DATABASE_TLS_SERVER_NAME'),
    )


def open_store(environ, *, dispatcher=False):
    from hyprn_mvp_app.store import Store
    if required(environ, 'EDITION') != 'cloud':
        raise ValueError('Hosted configuration edition differs')
    request = credentials(environ, required(environ, 'DATABASE_ROLE'), 'DB_APP_REQUEST')
    if request.user != 'hyprn_request':
        raise ValueError('Hosted configuration request authority differs')
    background_role = 'hyprn_dispatcher_background' if dispatcher else 'hyprn_assistant_background'
    background_name = 'DISPATCHER' if dispatcher else 'ASSISTANT'
    if required(environ, 'DATABASE_' + background_name + '_BACKGROUND_ROLE') != background_role:
        raise ValueError('Hosted configuration background authority differs')
    background = credentials(environ, background_role, 'DB_' + background_name + '_BACKGROUND')
    # Dispatcher never receives an authentication credential. Its store uses request
    # authority in the unused authentication slot; no authentication entrypoint is built.
    authentication = request if dispatcher else credentials(environ, 'hyprn_auth', 'DB_APP_AUTH')
    root = Path(required(environ, 'ARTIFACT_ROOT'))
    if not root.is_absolute() or not root.is_dir() or root.is_symlink():
        raise ValueError('Hosted configuration artifact directory is absent')
    store = Store.postgres(request, authentication, background=background, artifact_root=root)
    identity = host_record(required(environ, 'HOST_IDENTITY_FILE'))
    from .hosted_lifecycle import store_identity
    with store.connection() as db:
        store_identity(db, identity['installation_id'], required(environ, 'APPLICATION_STORE_ID'))
    return store


@contextmanager
def request_lease(credentials):
    raw = credentials.connect()
    try:
        db = Connection(raw)
        if not db.execute('SELECT pg_try_advisory_lock_shared(68272604) AS acquired').fetchone()['acquired']:
            raise ValueError('Hosted maintenance is in progress')
        raw.commit()
        yield
    finally:
        raw.close()


class WriterLease:
    """A live database session fences a second process; loss refuses further requests."""

    def __init__(self, credentials, *, dispatcher=False):
        self._mutex = Lock()
        self._raw = credentials.connect()
        self._key = 68272603 if dispatcher else 68272602
        try:
            db = Connection(self._raw)
            if not db.execute('SELECT pg_try_advisory_lock(?) AS acquired', (self._key,)).fetchone()['acquired']:
                raise ValueError('Hosted writer already active')
            self._raw.commit()
        except BaseException:
            self._raw.close()
            raise

    def check(self):
        with self._mutex:
            Connection(self._raw).execute('SELECT 1').fetchone()
            self._raw.commit()

    def close(self):
        with self._mutex:
            self._raw.close()


def host_record(path, *, owner=0, max_bytes=65536):
    """Read a nonsecret, host-owned control document; application cannot authorize itself."""
    path = Path(path)
    if not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Hosted control identity unavailable')
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != owner or info.st_mode & 0o022
                or info.st_size > max_bytes):
            raise ValueError('Hosted control identity unavailable')
        def pairs(items):
            result = {}
            for key, value in items:
                if key in result:
                    raise ValueError('Duplicate hosted control field')
                result[key] = value
            return result
        raw = stream.read(max_bytes + 1)
        if len(raw) > max_bytes:
            raise ValueError('Hosted control identity unavailable')
        return json.loads(raw, object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
