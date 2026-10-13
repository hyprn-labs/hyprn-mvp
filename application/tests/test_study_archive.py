"""Study archive: additive ``study_archive`` state, archive/restore commands and filtered listing.

Archive is study-wide presentation state, not access control and not deletion: it never changes
the study record or its revision, never deletes or rewrites any row, and every read by id keeps
working. Fresh synthetic off-cloud stores only; no modeling service, runtime or live store.
"""
import json
from pathlib import Path
import shutil
import sqlite3
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, FormatChecker

from hyprn_mvp_app.api import create_app
from hyprn_mvp_app import auth as auth_module
from hyprn_mvp_app.auth import Auth
from hyprn_mvp_app.contracts import DomainError
from hyprn_mvp_app.store import Store

ROOT = Path(__file__).resolve().parents[2]
ORIGIN = 'http://127.0.0.1:19998'
PASSWORD = 'correct horse battery staple'
ARCHIVE_TABLE = 'study_archive'


def uid():
    return str(uuid4())


_HASH = []


def password_hash():
    if not _HASH:
        _HASH.append(auth_module.password_hash(PASSWORD))
    return _HASH[0]


def login(app, username):
    client = TestClient(app, base_url=ORIGIN)
    session = client.post('/api/1/session', json=dict(username=username, password=PASSWORD), headers={'Origin': ORIGIN})
    assert session.status_code == 200, session.text
    client.headers.update({'Origin': ORIGIN, 'X-CSRF-Token': session.json()['data']['csrf_token']})
    return client


@pytest.fixture
def env(tmp_path):
    store = Store(tmp_path / 'archive.sqlite')
    auth = Auth(store, ORIGIN)
    # Auth.provision creates only the single owner; extra synthetic users share one scrypt hash.
    actors = {name: uid() for name in ('owner', 'writer', 'reader', 'stranger')}
    with store.connection(write=True) as db:
        for name, actor in actors.items():
            db.execute('INSERT INTO users(actor_id,username,password_hash) VALUES(?,?,?)', (actor, name, password_hash()))
    app = create_app(store, auth, None)
    clients = {name: login(app, name) for name in actors}
    return dict(store=store, auth=auth, app=app, actors=actors, clients=clients, path=tmp_path / 'archive.sqlite')


def new_study(env, name='Study', members=True):
    c = env['clients']['owner']
    created = c.post('/api/1/studies', json=dict(command_id=uid(), name=name))
    assert created.status_code == 201, created.text
    study = created.json()['data']
    if members:
        revision = study['revision']
        for who, role in (('writer', 'writer'), ('reader', 'reader')):
            revision = env['store'].set_membership(env['actors']['owner'], study['study_id'], uid(), revision,
                                                   env['actors'][who], role)['revision']
        study = env['store'].study(env['actors']['owner'], study['study_id'])
    return study


def archive(client, sid, command=None, action='archive'):
    return client.post(f'/api/1/studies/{sid}/{action}', json=dict(command_id=command or uid()))


def listing(client, **params):
    response = client.get('/api/1/studies', params=params)
    assert response.status_code == 200, response.text
    return response.json()['data']


def rows(path, table):
    with sqlite3.connect(path) as db:
        return db.execute(f'SELECT rowid,* FROM {table} ORDER BY rowid').fetchall()


def snapshot(path, *, exclude=()):
    """Every row of every table (with rowid) plus each object's stored SQL, read raw."""
    with sqlite3.connect(path) as db:
        objects = db.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' "
                             'ORDER BY type,name').fetchall()
        tables = [name for kind, name, _, _ in objects if kind == 'table' and name not in exclude]
        data = {name: db.execute(f'SELECT rowid,* FROM {name} ORDER BY rowid').fetchall() for name in tables}
    return dict(objects=[o for o in objects if o[2] not in exclude], rows=data)


def test_archive_restore_round_trip_keeps_study_record_and_reads(env):
    c = env['clients']['owner']
    a, b = new_study(env, 'Alpha'), new_study(env, 'Beta')
    assert sorted(s['study_id'] for s in listing(c)) == sorted([a['study_id'], b['study_id']])
    assert all(s['archived'] is False for s in listing(c))
    assert c.get(f"/api/1/studies/{a['study_id']}").json()['data'] == dict(a, archived=False)

    archived = archive(c, a['study_id'])
    assert archived.status_code == 200, archived.text
    assert archived.json()['data'] == dict(a, archived=True)  # Same record and revision; only the state changed.

    assert [s['study_id'] for s in listing(c)] == [b['study_id']]
    assert listing(c, archived='false') == listing(c)
    assert listing(c, archived='true') == [dict(a, archived=True)]
    # Reads by id are unchanged access: archive is presentation state, not access control.
    assert c.get(f"/api/1/studies/{a['study_id']}").json()['data'] == dict(a, archived=True)
    for who in ('writer', 'reader'):  # Study-wide, not a per-user hide.
        assert [s['study_id'] for s in listing(env['clients'][who], archived='true')] == [a['study_id']]
        assert a['study_id'] not in [s['study_id'] for s in listing(env['clients'][who])]

    restored = archive(c, a['study_id'], action='restore')
    assert restored.status_code == 200, restored.text
    assert restored.json()['data'] == dict(a, archived=False)
    assert listing(c, archived='true') == []
    assert sorted(s['study_id'] for s in listing(c)) == sorted([a['study_id'], b['study_id']])
    assert env['store'].study(env['actors']['owner'], a['study_id']) == a  # Revision never consumed.

    # An archived study keeps every ordinary operation (here: a study edit) and stays archived.
    archive(c, a['study_id'])
    edited = c.patch(f"/api/1/studies/{a['study_id']}", json=dict(command_id=uid(), expected_revision=a['revision'], name='Alpha 2'))
    assert edited.status_code == 200, edited.text
    assert c.get(f"/api/1/studies/{a['study_id']}").json()['data']['archived'] is True


def test_state_survives_store_reopen_and_new_application(env):
    c = env['clients']['owner']
    a = new_study(env)
    archive(c, a['study_id'])
    reopened = Store(env['path'])
    app = create_app(reopened, Auth(reopened, ORIGIN), None)
    client = login(app, 'owner')
    assert listing(client, archived='true') == [dict(a, archived=True)]
    assert listing(client) == []


def test_command_id_idempotency_replay_and_payload_conflict(env):
    c, store = env['clients']['owner'], env['store']
    sid = new_study(env)['study_id']
    command = uid()
    first = archive(c, sid, command)
    receipts_after_first = rows(env['path'], 'receipts')
    state_after_first = rows(env['path'], ARCHIVE_TABLE)
    again = archive(c, sid, command)
    assert again.status_code == 200 and again.json()['data'] == first.json()['data']
    assert rows(env['path'], 'receipts') == receipts_after_first
    assert rows(env['path'], ARCHIVE_TABLE) == state_after_first

    # The same command id for the other operation is a payload conflict and changes nothing.
    conflict = archive(c, sid, command, action='restore')
    assert conflict.status_code == 409 and conflict.json()['error']['code'] == 'command_payload_conflict'
    assert rows(env['path'], ARCHIVE_TABLE) == state_after_first

    receipt = c.get(f'/api/1/studies/{sid}/commands/{command}', params=dict(category='study_archive'))
    assert receipt.status_code == 200
    assert receipt.json()['data'] == dict(command_id=command, state='committed', result=first.json()['data'], error=None)
    raw = store.receipt(env['actors']['owner'], sid, 'study_archive', command)
    assert raw['actor_id'] == env['actors']['owner'] and raw['state'] == 'committed'

    # A replay after a later restore returns the original outcome and never re-archives.
    archive(c, sid, action='restore')
    replay = archive(c, sid, command)
    assert replay.json()['data']['archived'] is True
    assert c.get(f'/api/1/studies/{sid}').json()['data']['archived'] is False

    # Archiving an archived study (new command) is a committed no-op target state: the row keeps
    # the command, actor and time that actually changed it.
    changing = uid()
    archive(c, sid, changing)
    changed = rows(env['path'], ARCHIVE_TABLE)
    noop = archive(env['clients']['writer'], sid)
    assert noop.status_code == 200 and noop.json()['data']['archived'] is True
    assert rows(env['path'], ARCHIVE_TABLE) == changed
    (_, study_id, state, row_command, actor, at), = changed
    assert (study_id, state, row_command, actor) == (sid, 1, changing, env['actors']['owner'])
    assert at.endswith('Z') and 'T' in at


def test_authorization_conceals_non_members_and_forbids_readers(env):
    sid = new_study(env)['study_id']
    before = snapshot(env['path'])
    for action in ('archive', 'restore'):
        stranger = archive(env['clients']['stranger'], sid, action=action)
        assert stranger.status_code == 404 and stranger.json()['error']['code'] == 'resource_not_found'
        reader = archive(env['clients']['reader'], sid, action=action)
        assert reader.status_code == 403 and reader.json()['error']['code'] == 'forbidden'
        unknown = archive(env['clients']['owner'], uid(), action=action)
        assert unknown.status_code == 404 and unknown.json()['error']['code'] == 'resource_not_found'
    assert snapshot(env['path']) == before  # No receipt, no state for any refused attempt.
    assert env['clients']['stranger'].get(f'/api/1/studies/{sid}').status_code == 404
    assert listing(env['clients']['stranger']) == [] and listing(env['clients']['stranger'], archived='true') == []

    writer = env['clients']['writer']  # The patch_study permission: owner or writer.
    assert archive(writer, sid).status_code == 200
    assert listing(env['clients']['stranger'], archived='true') == []
    assert archive(env['clients']['reader'], sid, action='restore').status_code == 403
    assert archive(writer, sid, action='restore').json()['data']['archived'] is False
    assert archive(env['clients']['owner'], sid).status_code == 200
    assert archive(env['clients']['owner'], sid, action='restore').status_code == 200

    # Session, Origin and CSRF protections apply to the new mutations like every other one.
    owner = env['clients']['owner']
    assert owner.post(f'/api/1/studies/{sid}/archive', json=dict(command_id=uid()),
                      headers={'X-CSRF-Token': 'wrong'}).status_code == 403
    assert owner.post(f'/api/1/studies/{sid}/archive', json=dict(command_id=uid()),
                      headers={'Origin': 'https://evil.example'}).status_code == 403
    anonymous = TestClient(env['app'], base_url=ORIGIN)
    assert anonymous.post(f'/api/1/studies/{sid}/archive', json=dict(command_id=uid()),
                          headers={'Origin': ORIGIN}).status_code in (401, 403)
    assert anonymous.get('/api/1/studies', params=dict(archived='true')).status_code == 401


@pytest.mark.parametrize('body', [{}, dict(command_id='not-a-uuid'), dict(command_id=str(uuid4()), extra=1),
                                  dict(command_id=str(uuid4()), expected_revision='x')])
def test_closed_request_body(env, body):
    sid = new_study(env, members=False)['study_id']
    before = snapshot(env['path'])
    response = env['clients']['owner'].post(f'/api/1/studies/{sid}/archive', json=body)
    assert response.status_code == 400 and response.json()['error']['code'] == 'invalid_request'
    assert snapshot(env['path']) == before


@pytest.mark.parametrize('query', ['archived=yes', 'archived=1', 'archived=True', 'archived=', 'archived=true&archived=false'])
def test_listing_query_is_strict(env, query):
    response = env['clients']['owner'].get('/api/1/studies?' + query)
    assert response.status_code == 400 and response.json()['error']['code'] == 'invalid_request'


def test_archived_listing_paginates_within_its_own_filter(env):
    c = env['clients']['owner']
    studies = [new_study(env, f'S{i}', members=False) for i in range(3)]
    for s in studies[:2]:
        archive(c, s['study_id'])
    first = c.get('/api/1/studies', params=dict(archived='true', limit=1)).json()
    ordered = sorted(s['study_id'] for s in studies[:2])
    assert [s['study_id'] for s in first['data']] == ordered[:1] and first['next_cursor'] == ordered[0]
    second = c.get('/api/1/studies', params=dict(archived='true', limit=1, cursor=first['next_cursor'])).json()
    assert [s['study_id'] for s in second['data']] == ordered[1:] and second['next_cursor'] is None
    # A cursor from another filter is not a member of this page set.
    assert c.get('/api/1/studies', params=dict(archived='true', cursor=studies[2]['study_id'])).status_code == 404


def populate(env):
    """A populated store: memberships, edits, evidence, receipts, plus raw retained records."""
    store, owner = env['store'], env['actors']['owner']
    a, b = new_study(env, 'Populated A'), new_study(env, 'Populated B')
    store.update_study(owner, a['study_id'], uid(), a['revision'], dict(description='Context', boundary='Boundary'))
    for s in (a, b):
        store.add_evidence(owner, s['study_id'], uid(), dict(scope=None, kind='note', content='Note ' + s['name'], source_refs=[]))
    with store.connection(write=True) as db:  # Retained configuration/run rows are bytes here.
        db.execute('INSERT INTO configurations VALUES(?,?,?,?)', (uid(), uid(), a['study_id'], json.dumps(dict(x=1.5))))
        cfg = db.execute('SELECT configuration_revision_id FROM configurations').fetchone()[0]
        db.execute('INSERT INTO run_associations(run_id,study_id,configuration_revision_id,command_id,store_uuid,process_uuid) '
                   'VALUES(?,?,?,?,?,?)', (uid(), a['study_id'], cfg, uid(), None, None))
    return a, b


def test_archive_never_deletes_or_rewrites_other_records(env):
    a, b = populate(env)
    c = env['clients']['owner']
    before = snapshot(env['path'], exclude=(ARCHIVE_TABLE, 'receipts', 'sessions'))
    receipts = rows(env['path'], 'receipts')
    for action in ('archive', 'restore', 'archive'):
        assert archive(c, a['study_id'], action=action).status_code == 200
    assert snapshot(env['path'], exclude=(ARCHIVE_TABLE, 'receipts', 'sessions')) == before
    assert rows(env['path'], 'receipts')[:len(receipts)] == receipts  # Receipts only appended.
    assert len(rows(env['path'], 'receipts')) == len(receipts) + 3
    restored = archive(c, a['study_id'], action='restore')
    assert restored.status_code == 200
    (_, sid, state, *_), = rows(env['path'], ARCHIVE_TABLE)
    assert (sid, state) == (a['study_id'], 0)  # Restore keeps the row; nothing is deleted.
    with sqlite3.connect(env['path']) as db, pytest.raises(sqlite3.IntegrityError, match='never deleted'):
        db.execute('DELETE FROM study_archive')
    with sqlite3.connect(env['path']) as db, pytest.raises(sqlite3.IntegrityError):
        db.execute('UPDATE study_archive SET archived=2')
    assert len(rows(env['path'], ARCHIVE_TABLE)) == 1


def test_migration_on_populated_pre_archive_store_is_additive_and_idempotent(env, tmp_path):
    populate(env)
    # Reconstruct the exact pre-S6a shape: the same populated store without the additive objects
    # (nothing was ever archived in it, so no S6a row or receipt exists).
    fixture = tmp_path / 'fixture.sqlite'
    db = sqlite3.connect(env['path'], isolation_level=None)
    try:
        db.execute('DROP TRIGGER study_archive_no_delete')
        db.execute('DROP TABLE study_archive')
    finally:
        db.close()
    shutil.copyfile(env['path'], fixture)
    assert ARCHIVE_TABLE not in [r[0] for r in sqlite3.connect(fixture).execute("SELECT name FROM sqlite_master")]
    fixture_bytes = fixture.read_bytes()

    populated = tmp_path / 'populated-copy.sqlite'  # Migrate a copy; the fixture itself stays untouched.
    shutil.copyfile(fixture, populated)
    before = snapshot(populated)
    for _ in range(2):  # Opening twice proves the migration is idempotent.
        Store(populated)
    after = snapshot(populated)
    assert {k: v for k, v in after['rows'].items() if k != ARCHIVE_TABLE} == before['rows']
    assert [o for o in after['objects'] if o[2] != ARCHIVE_TABLE] == before['objects']
    assert after['rows'][ARCHIVE_TABLE] == []
    assert sorted(o[1] for o in after['objects'] if o[2] == ARCHIVE_TABLE) == ['study_archive', 'study_archive_no_delete']
    assert fixture.read_bytes() == fixture_bytes

    store = Store(populated)
    owner = env['actors']['owner']
    # Pre-existing studies read as not archived; their records are exactly the stored ones.
    with store.connection() as db:
        stored = {r['study_id']: dict(r) for r in db.execute('SELECT * FROM studies')}
    assert store.study_listing(owner, archived=False) == sorted(
        (dict(s, archived=False) for s in stored.values()), key=lambda s: s['study_id'])
    assert store.study_listing(owner, archived=True) == []


def test_store_interface_is_in_transaction_and_authorized(env):
    store, owner, reader = env['store'], env['actors']['owner'], env['actors']['reader']
    sid = new_study(env)['study_id']
    with store.connection() as db:
        assert store.study_archived(db, sid) is False
    with pytest.raises(DomainError) as denied:
        store.set_study_archived(reader, sid, uid(), True)
    assert denied.value.status == 403
    with pytest.raises(DomainError) as hidden:
        store.set_study_archived(env['actors']['stranger'], sid, uid(), True)
    assert hidden.value.status == 404
    assert store.set_study_archived(owner, sid, uid(), True)['archived'] is True
    with store.connection() as db:
        assert store.study_archived(db, sid) is True
    assert store.study_read(reader, sid)['archived'] is True
    # Existing study reads and creation/update outcomes keep their exact recorded shape.
    assert 'archived' not in store.study(owner, sid)
    assert all('archived' not in s for s in store.list_studies(owner))


def test_capabilities_advertise_study_archive(env):
    caps = env['clients']['stranger'].get('/api/1/capabilities')  # No study: no private probe.
    assert caps.status_code == 200, caps.text
    data = caps.json()['data']
    assert 'study_archive/1' in data['engineering'] and 'archive' not in data['unavailable']
    assert 'documents' in data['unavailable']


def test_generated_contract_declares_archive_additively(env):
    spec = json.loads((ROOT / 'contracts/hyprn-mvp.openapi.yaml').read_text())
    schemas = spec['components']['schemas']
    study = schemas['Study']
    assert study['properties']['archived']['type'] == 'boolean'
    assert study['required'] == ['study_id', 'revision', 'name', 'description', 'boundary']  # Historical receipts stay valid.
    assert schemas['StudyArchiveCommand'] == dict(type='object', properties=dict(command_id=dict(type='string', format='uuid')),
                                                  required=['command_id'], additionalProperties=False)
    listing_parameters = {p['name']: p for p in spec['paths']['/studies']['get']['parameters']}
    assert listing_parameters['archived']['schema'] == {'enum': ['true', 'false'], 'default': 'false'}
    validator = lambda schema: Draft202012Validator({'components': spec['components'], **schema}, format_checker=FormatChecker())
    c = env['clients']['owner']
    sid = new_study(env)['study_id']
    command = uid()
    for action in ('archive', 'restore'):
        operation = spec['paths']['/studies/{study_id}/' + action]['post']
        assert operation['requestBody']['content']['application/json']['schema'] == {'$ref': '#/components/schemas/StudyArchiveCommand'}
        assert {p['name'] for p in operation['parameters']} == {'study_id', 'Origin', 'X-CSRF-Token'}
        assert set(operation['responses']) >= {'200', '400', '403', '404', '409'}
        response = archive(c, sid, command if action == 'archive' else None, action=action)
        assert not list(validator(operation['responses']['200']['content']['application/json']['schema']).iter_errors(response.json()))
    cases = [('/studies', 'get', c.get('/api/1/studies', params=dict(archived='true'))), ('/studies', 'get', c.get('/api/1/studies')),
             ('/studies/{study_id}', 'get', c.get(f'/api/1/studies/{sid}')),
             ('/studies/{study_id}/commands/{command_id}', 'get', c.get(f'/api/1/studies/{sid}/commands/{command}', params=dict(category='study_archive')))]
    for route, method, response in cases:
        assert response.status_code == 200, response.text
        schema = spec['paths'][route][method]['responses']['200']['content']['application/json']['schema']
        assert not list(validator(schema).iter_errors(response.json())), (route, response.text)
    types = (ROOT / 'ui/src/contract.ts').read_text()
    assert 'export type Study = { "study_id": string; "revision": string; "name": string; "description": string; "boundary": string; "archived"?: boolean };' in types
    assert 'export type StudyArchiveCommand = { "command_id": string };' in types
