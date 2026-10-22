"""Private study HTTP reads and writes use real PostgreSQL and restricted roles."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import socket
from threading import Thread
import time
from uuid import uuid4

import httpx
import pytest
import uvicorn

from hosted_fixture import postgres_fixture
from hyprn_mvp_app.api import create_app
from hyprn_mvp_app.auth import Auth, token_hash
from hyprn_mvp_app.database import Connection, DatabasePermissionDenied, actor_scope
from hyprn_mvp_app.migrations import initialize
from hyprn_mvp_app.store import Store


@pytest.fixture(scope='module')
def hosted(tmp_path_factory):
    with postgres_fixture() as fixture:
        store = Store.postgres(fixture['request'], fixture['auth'],
                               artifact_root=tmp_path_factory.mktemp('hosted-artifacts'),
                               background=fixture['assistant'])
        accounts = []
        raw = fixture['admin'].connect()
        try:
            db = Connection(raw)
            for _ in range(2):
                actor, token, csrf = (str(uuid4()) for _ in range(3))
                db.execute('INSERT INTO users(actor_id,username) VALUES(?,?)', (actor, actor))
                db.execute(
                    'INSERT INTO sessions VALUES(?,?,?,?)',
                    (token_hash(token), actor, token_hash(csrf), time.time() + 600),
                )
                accounts.append(dict(actor=actor, token=token, csrf=csrf))
            raw.commit()
        finally:
            raw.close()
        try:
            yield fixture, store, accounts
        finally:
            store.database.close()


@contextmanager
def live_api(store):
    # Fixture-owned ephemeral socket, no installation port or test-only auth route.
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    origin = f'http://127.0.0.1:{sock.getsockname()[1]}'
    app = create_app(store, Auth(store, origin), None)
    server = uvicorn.Server(uvicorn.Config(app, log_level='critical', lifespan='off'))
    thread = Thread(target=server.run, kwargs=dict(sockets=[sock]), daemon=True)
    thread.start()
    try:
        for _ in range(100):
            if server.started:
                break
            time.sleep(0.02)
        assert server.started
        yield origin
    finally:
        server.should_exit = True
        thread.join(10)
        sock.close()
        assert not thread.is_alive()


def headers(account, origin):
    return {
        'Cookie': 'hyprn_mvp_session=' + account['token'],
        'Origin': origin,
        'X-CSRF-Token': account['csrf'],
    }


def test_http_private_studies_and_repeated_command(hosted):
    _, store, accounts = hosted
    with live_api(store) as origin:
        commands = [str(uuid4()), str(uuid4())]

        def create(index):
            return httpx.post(
                origin + '/api/1/studies',
                headers=headers(accounts[index], origin),
                json=dict(command_id=commands[index], name=f'Private {index}'),
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(create, range(2)))
        assert [response.status_code for response in responses] == [201, 201], [
            response.text for response in responses
        ]
        studies = [response.json()['data'] for response in responses]
        assert create(0).json()['data'] == studies[0]
        for index in range(2):
            own = httpx.get(origin + '/api/1/studies', headers=headers(accounts[index], origin))
            assert own.status_code == 200, own.text
            assert [row['study_id'] for row in own.json()['data']] == [studies[index]['study_id']]
            foreign = httpx.get(
                origin + '/api/1/studies/' + studies[1 - index]['study_id'],
                headers=headers(accounts[index], origin),
            )
            assert foreign.status_code == 404
        assert httpx.get(origin + '/api/1/studies').status_code == 401


def test_missing_scope_and_concurrent_actor_scope_deny_foreign_rows(hosted):
    _, store, accounts = hosted
    with store.connection() as db:
        assert db.execute('SELECT * FROM studies').fetchall() == []
        assert db.execute('SELECT * FROM memberships').fetchall() == []
        assert db.execute('SELECT * FROM receipts').fetchall() == []
    for account in accounts:
        with actor_scope(account['actor']):
            with store.connection() as db:
                assert all(
                    row['owner_actor_id'] == account['actor']
                    for row in db.execute('SELECT * FROM studies')
                )
            with pytest.raises(ValueError, match='cannot change'):
                with actor_scope('different'):
                    pass
    with store.connection() as db:
        assert db.execute('SELECT * FROM studies').fetchall() == []


def test_revoked_creator_has_no_sql_access(hosted):
    fixture, store, accounts = hosted
    actor = accounts[0]['actor']
    with actor_scope(actor):
        study = store.create_study(actor, str(uuid4()), 'revoked creator')
    raw = fixture['admin'].connect()
    try:
        Connection(raw).execute('DELETE FROM memberships WHERE study_id=?', (study['study_id'],))
        raw.commit()
    finally:
        raw.close()
    with actor_scope(actor):
        with store.connection() as db:
            assert (
                db.execute(
                    'SELECT * FROM studies WHERE study_id=?', (study['study_id'],)
                ).fetchall()
                == []
            )


def test_request_role_cannot_read_credentials_or_change_schema(hosted):
    _, store, accounts = hosted
    for statement in (
        'SELECT * FROM sessions',
        'SELECT * FROM users',
        'ALTER TABLE studies ADD COLUMN unauthorized TEXT',
        'SET ROLE hyprn_migration',
    ):
        with actor_scope(accounts[0]['actor']):
            with pytest.raises(DatabasePermissionDenied):
                with store.connection(write=True) as db:
                    db.execute(statement)


def test_read_connections_cannot_write(hosted):
    _, store, accounts = hosted
    with actor_scope(accounts[0]['actor']):
        with pytest.raises(DatabasePermissionDenied):
            with store.connection() as db:
                db.execute(
                    'INSERT INTO studies(study_id,revision,name,description,boundary) '
                    'VALUES(?,?,?,?,?)',
                    (str(uuid4()), str(uuid4()), 'refused', '', ''),
                )


def test_rollback_leaves_no_study_or_receipt(hosted):
    _, store, accounts = hosted
    sid, command = str(uuid4()), str(uuid4())
    with actor_scope(accounts[0]['actor']):

        def fail(db):
            db.execute(
                'INSERT INTO studies(study_id,revision,name,description,boundary) '
                'VALUES(?,?,?,?,?)',
                (sid, str(uuid4()), 'rollback', '', ''),
            )
            raise RuntimeError('failed operation')

        with pytest.raises(RuntimeError, match='failed operation'):
            store.command(accounts[0]['actor'], None, 'rollback', command, {}, fail)
        with store.connection() as db:
            assert db.execute('SELECT 1 FROM studies WHERE study_id=?', (sid,)).fetchone() is None
            assert (
                db.execute('SELECT 1 FROM receipts WHERE command_id=?', (command,)).fetchone()
                is None
            )


def test_missing_scope_cannot_create_study(hosted):
    _, store, _ = hosted
    with pytest.raises(DatabasePermissionDenied):
        with store.connection(write=True) as db:
            db.execute(
                'INSERT INTO studies(study_id,revision,name,description,boundary) '
                'VALUES(?,?,?,?,?)',
                (str(uuid4()), str(uuid4()), 'refused', '', ''),
            )


def test_startup_never_migrates_and_refuses_schema_drift(hosted):
    fixture, _, _ = hosted
    initialize(fixture['migration'])
    with pytest.raises(ValueError, match='must not own'):
        Store.postgres(fixture['admin'], fixture['auth'])
    raw = fixture['admin'].connect()
    try:
        db = Connection(raw)
        db.execute("UPDATE hyprn_schema_versions SET checksum='wrong'")
        raw.commit()
        with pytest.raises(ValueError, match='incompatible'):
            Store.postgres(fixture['request'], fixture['auth'])
        with pytest.raises(ValueError, match='incompatible'):
            initialize(fixture['migration'])
    finally:
        from hyprn_mvp_app.migrations import expected, MIGRATIONS

        for migration in MIGRATIONS:
            db.execute('UPDATE hyprn_schema_versions SET checksum=? WHERE version=?',
                       (expected(migration), migration.stem))
        raw.commit()
        raw.close()


@pytest.mark.parametrize('role', ['hyprn_migration', 'hyprn_bypass', 'hyprn_auth', 'hyprn_assistant_background'])
def test_request_role_cannot_inherit_elevated_authority(hosted, role):
    fixture, _, _ = hosted
    raw = fixture['admin'].connect()
    try:
        db = Connection(raw)
        if role == 'hyprn_bypass':
            db.execute('CREATE ROLE hyprn_bypass BYPASSRLS')
        db.execute(f'GRANT {role} TO hyprn_request')
        raw.commit()
        with pytest.raises(ValueError, match='must not own'):
            Store.postgres(fixture['request'], fixture['auth'])
    finally:
        db.execute(f'REVOKE {role} FROM hyprn_request')
        if role == 'hyprn_bypass':
            db.execute('DROP ROLE hyprn_bypass')
        raw.commit()
        raw.close()


def test_reused_connections_reset_session_and_actor_authority(hosted):
    _, store, accounts = hosted
    actor = accounts[0]['actor']
    with actor_scope(actor):
        with store.connection() as db:
            pid = db.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid']
            bound = db.execute("SELECT current_setting('hyprn.actor_id') AS actor").fetchone()
            assert bound['actor'] == actor
            db.execute("SET application_name='must-not-leak'")
    with store.connection() as db:
        assert db.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid'] == pid
        bound = db.execute("SELECT current_setting('hyprn.actor_id') AS actor").fetchone()
        assert bound['actor'] == ''
        name = db.execute("SELECT current_setting('application_name') AS name").fetchone()
        assert name['name'] != 'must-not-leak'
        assert db.execute('SELECT * FROM studies').fetchall() == []
    with store.authentication_connection() as db:
        assert db.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid'] != pid
        assert db.execute('SELECT current_user AS role').fetchone()['role'] == 'hyprn_auth'


def test_failed_transaction_is_not_reused(hosted):
    import pg8000.dbapi
    _, store, accounts = hosted
    with actor_scope(accounts[0]['actor']):
        with pytest.raises(pg8000.dbapi.DatabaseError):
            with store.connection() as db:
                pid = db.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid']
                db.execute('SELECT missing_performance_test_column')
        with store.connection() as db:
            assert db.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid'] != pid
            assert db.execute('SELECT 1 AS ok').fetchone()['ok'] == 1


def test_connection_capacity_is_bounded_and_closed_pools_refuse_checkout(hosted):
    from hyprn_mvp_app.database import _ConnectionPool, DatabaseUnavailable
    fixture, _, _ = hosted
    pool = _ConnectionPool(fixture['request'], maximum=1, wait_seconds=0.02)
    try:
        with pool.checkout() as first:
            with pytest.raises(DatabaseUnavailable, match='capacity'):
                with pool.checkout():
                    pytest.fail('A checked-out connection cannot be shared')
        with pool.checkout() as second:
            assert first is second
    finally:
        pool.close()
    assert pool.count == 0
    with pytest.raises(DatabaseUnavailable, match='closed'):
        with pool.checkout():
            pytest.fail('Closed pool admitted a caller')


def test_dead_idle_connection_is_replaced_before_starting_transaction(hosted):
    fixture, store, _ = hosted
    with store.connection() as db:
        pid = db.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid']
    raw = fixture['admin'].connect()
    try:
        stopped = Connection(raw).execute(
            'SELECT pg_terminate_backend(?) AS stopped', (pid,)
        ).fetchone()
        assert stopped['stopped']
        raw.commit()
    finally:
        raw.close()
    with store.connection() as db:
        assert db.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid'] != pid
