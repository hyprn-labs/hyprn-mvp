"""Agent principal: delegated agent sessions travel through the real middleware, ``authorize``
and the store, and never exceed the delegating user's current authority.

An agent actor is never a user and can never sign in. It acts only through a live delegation
of one study; its authority is the intersection of that delegation (study, role ceiling,
effects) with the delegating user's current membership. Tool tokens are never valid on the
API. The one pre-study command an agent may issue, study creation, gives the Owner membership
to the delegating user and never widens the delegation. Fresh synthetic off-cloud stores only;
no modeling service, runtime or live store.
"""
import base64
import sqlite3
import time
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from conftest import LOOPBACK_ORIGIN
from hyprn_mvp_app import auth as auth_module
from hyprn_mvp_app.api import create_app
from hyprn_mvp_app.auth import Auth
from hyprn_mvp_app.contracts import DomainError
from hyprn_mvp_app.store import Store

ORIGIN = LOOPBACK_ORIGIN
PASSWORD = 'correct horse battery staple'
COOKIE = 'hyprn_mvp_session'
WRITER_EFFECTS = ('read', 'draft', 'record', 'submit', 'outside_study')
READER_EFFECTS = ('read', 'outside_study')
# Assembled at run time so no token-shaped literal appears in the source.
TOKEN_PREFIX = 'hyprn' + '_mvp' + '_mcp_'


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


def agent_client(app, session):
    client = TestClient(app, base_url=ORIGIN)
    client.cookies.set(COOKIE, session['token'])
    client.headers.update({'Origin': ORIGIN, 'X-CSRF-Token': session['csrf_token']})
    return client


class UnavailableModeling:
    """Modeling double: records which actor probed which study, and is always unavailable."""
    def __init__(self):
        self.calls = []

    def call(self, actor, sid, method, path, **_):
        self.calls.append((actor, sid, method, path))
        raise DomainError('backend_unavailable', 503, outcome='unknown')


@pytest.fixture
def env(tmp_path):
    path = tmp_path / 'agent.sqlite'
    store = Store(path)
    auth = Auth(store, ORIGIN)
    actors = {name: uid() for name in ('owner', 'writer', 'reader', 'stranger')}
    with store.connection(write=True) as db:
        for name, actor in actors.items():
            db.execute('INSERT INTO users(actor_id,username,password_hash) VALUES(?,?,?)', (actor, name, password_hash()))
    model = UnavailableModeling()
    app = create_app(store, auth, model)
    clients = {name: login(app, name) for name in ('owner', 'writer', 'reader')}
    return dict(store=store, auth=auth, app=app, actors=actors, clients=clients, path=path, model=model)


def new_study(env, name='Study'):
    created = env['clients']['owner'].post('/api/1/studies', json=dict(command_id=uid(), name=name))
    assert created.status_code == 201, created.text
    study = created.json()['data']
    revision = study['revision']
    for who, role in (('writer', 'writer'), ('reader', 'reader')):
        revision = env['store'].set_membership(env['actors']['owner'], study['study_id'], uid(), revision,
                                               env['actors'][who], role)['revision']
    return env['store'].study(env['actors']['owner'], study['study_id'])


def set_role(env, sid, who, role):
    store, owner = env['store'], env['actors']['owner']
    revision = store.study(owner, sid)['revision']
    store.set_membership(owner, sid, uid(), revision, env['actors'][who], role)


def delegate(env, sid, *, user='writer', ceiling='writer', effects=WRITER_EFFECTS, hours=8):
    store = env['store']
    with store.connection(write=True) as db:
        agent = store.ensure_agent_actor(db, env['actors'][user], 'local_mcp', 'Coding agent (local)')
        delegation = store.create_delegation(db, agent, sid, ceiling, effects, time.time() + hours * 3600)
    return agent, delegation


def snapshot(path):
    with sqlite3.connect(path) as db:
        return list(db.iterdump())


def memberships(path, sid):
    with sqlite3.connect(path) as db:
        return dict(db.execute('SELECT actor_id,role FROM memberships WHERE study_id=?', (sid,)).fetchall())


# ---- Agent sessions through the real middleware ---------------------------------------

def test_agent_session_reads_only_its_delegated_study_and_never_lists_studies(env):
    study, other = new_study(env, 'Delegated'), new_study(env, 'Other')
    agent, delegation = delegate(env, study['study_id'])
    session = env['auth'].mint_agent_session(delegation['delegation_id'])
    assert session['actor_id'] == agent and session['study_id'] == study['study_id']
    client = agent_client(env['app'], session)
    read = client.get(f"/api/1/studies/{study['study_id']}/runs")
    assert read.status_code == 200, read.text
    assert client.get(f"/api/1/studies/{other['study_id']}/runs").status_code == 404
    # A study-scoped session has no study listing: no registered tool or internal read uses it.
    listed = client.get('/api/1/studies')
    assert listed.status_code == 403, listed.text
    capabilities = client.get('/api/1/capabilities')
    assert capabilities.status_code == 200, capabilities.text
    assert env['model'].calls == [(agent, study['study_id'], 'GET', '/capabilities')] * len(env['model'].calls)
    assert env['model'].calls
    assert env['store'].list_studies(agent) == [env['store'].study(env['actors']['writer'], study['study_id'])]


def test_read_only_agent_session_cannot_mutate_and_the_store_is_unchanged(env):
    study = new_study(env)
    sid = study['study_id']
    _, delegation = delegate(env, sid, effects=('read',))
    session = env['auth'].mint_agent_session(delegation['delegation_id'])
    assert session['read_only'] is True
    client = agent_client(env['app'], session)
    before = snapshot(env['path'])
    refused = [
        client.post(f'/api/1/studies/{sid}/evidence', json=dict(command_id=uid(), scope=None, kind='note',
                                                                content='x', source_refs=[])),
        client.patch(f'/api/1/studies/{sid}', json=dict(command_id=uid(), expected_revision=study['revision'],
                                                        name='Renamed')),
        client.post(f'/api/1/studies/{sid}/archive', json=dict(command_id=uid())),
        client.delete('/api/1/session'),
        client.request('DELETE', f'/api/1/studies/{sid}'),
    ]
    for response in refused:
        assert response.status_code == 403, response.text
        assert response.json()['error']['code'] == 'forbidden'
    assert snapshot(env['path']) == before


def test_writer_agent_session_mutations_are_refused_by_the_route_allowlist(env):
    study = new_study(env)
    sid = study['study_id']
    _, delegation = delegate(env, sid)
    session = env['auth'].mint_agent_session(delegation['delegation_id'])
    assert session['read_only'] is False
    client = agent_client(env['app'], session)
    before = snapshot(env['path'])
    for response in (client.patch(f'/api/1/studies/{sid}', json=dict(command_id=uid(), expected_revision=study['revision'],
                                                                      name='Renamed')),
                     client.post(f'/api/1/studies/{sid}/archive', json=dict(command_id=uid())),
                     client.post(f'/api/1/studies/{sid}/restore', json=dict(command_id=uid()))):
        assert response.status_code == 403, response.text
    assert snapshot(env['path']) == before


def test_agent_session_study_creation_is_refused_by_the_route_allowlist(env):
    sid = new_study(env)['study_id']
    _, delegation = delegate(env, sid)
    client = agent_client(env['app'], env['auth'].mint_agent_session(delegation['delegation_id']))
    before = snapshot(env['path'])
    created = client.post('/api/1/studies', json=dict(command_id=uid(), name='Agent study'))
    assert created.status_code == 403, created.text
    assert created.json()['error']['code'] == 'forbidden'
    assert snapshot(env['path']) == before


def test_agent_session_cannot_reach_session_routes_or_pre_study_receipts(env):
    sid = new_study(env)['study_id']
    _, delegation = delegate(env, sid)
    client = agent_client(env['app'], env['auth'].mint_agent_session(delegation['delegation_id']))
    for response in (client.post('/api/1/session', json=dict(username='writer', password=PASSWORD)),
                     client.delete('/api/1/session'),
                     client.get(f'/api/1/commands/{uid()}', params=dict(category='study_create'))):
        assert response.status_code == 403, response.text


def test_another_study_is_not_found_for_an_agent_session(env):
    study, other = new_study(env, 'Delegated'), new_study(env, 'Other')
    _, delegation = delegate(env, study['study_id'])
    client = agent_client(env['app'], env['auth'].mint_agent_session(delegation['delegation_id']))
    other_sid = other['study_id']
    for path in (f'/api/1/studies/{other_sid}/runs', f'/api/1/studies/{other_sid}/commands/{uid()}',
                 f'/api/1/studies/{uid()}/runs'):
        response = client.get(path)
        assert response.status_code == 404, response.text
        assert response.json()['error']['code'] == 'resource_not_found'


def test_agent_session_is_pinned_to_its_delegation_even_when_the_agent_holds_another(env):
    first, second = new_study(env, 'First'), new_study(env, 'Second')
    _, delegation = delegate(env, first['study_id'])
    delegate(env, second['study_id'])
    client = agent_client(env['app'], env['auth'].mint_agent_session(delegation['delegation_id']))
    assert client.get(f"/api/1/studies/{second['study_id']}/runs").status_code == 404
    assert client.get(f"/api/1/studies/{first['study_id']}/runs").status_code == 200


def test_tool_token_is_refused_on_the_api(env):
    sid = new_study(env)['study_id']
    _, delegation = delegate(env, sid)
    token = env['auth'].mint_tool_token(delegation['delegation_id'], ttl_hours=8, client_label='Codex')['token']
    anonymous = TestClient(env['app'], base_url=ORIGIN)
    for client in (anonymous, env['clients']['writer']):
        response = client.get(f'/api/1/studies/{sid}', headers={'Authorization': 'Bearer ' + token})
        assert response.status_code == 401, response.text
        assert response.json()['error']['code'] == 'unauthenticated'
    as_cookie = TestClient(env['app'], base_url=ORIGIN)
    as_cookie.cookies.set(COOKIE, token)
    assert as_cookie.get(f'/api/1/studies/{sid}').status_code == 401
    with pytest.raises(DomainError, match='unauthenticated'):
        env['auth'].authenticate(token)


# ---- Effective authority follows the delegation and the user's current membership -----

def test_agent_authority_follows_the_delegating_users_current_membership(env):
    sid = new_study(env)['study_id']
    agent, delegation = delegate(env, sid)
    store = env['store']
    with store.connection() as db:
        store.authorize(db, agent, sid, write=True)
    set_role(env, sid, 'writer', 'reader')
    with store.connection() as db:
        store.authorize(db, agent, sid)
        with pytest.raises(DomainError, match='forbidden'):
            store.authorize(db, agent, sid, write=True)
    client = agent_client(env['app'], env['auth'].mint_agent_session(delegation['delegation_id']))
    assert client.get(f'/api/1/studies/{sid}/runs').status_code == 200
    set_role(env, sid, 'writer', None)
    with store.connection() as db:
        with pytest.raises(DomainError, match='resource_not_found'):
            store.authorize(db, agent, sid)
    response = client.get(f'/api/1/studies/{sid}/runs')
    assert response.status_code == 404, response.text
    assert store.list_studies(agent) == []


def test_agent_never_holds_owner_authority_and_reads_need_no_write_effect(env):
    sid = new_study(env)['study_id']
    store = env['store']
    owner_agent, _ = delegate(env, sid, user='owner')
    with store.connection() as db:
        with pytest.raises(DomainError, match='forbidden'):
            store.authorize(db, owner_agent, sid, owner=True)
    reader_agent, _ = delegate(env, sid, user='owner', effects=('read',))
    assert reader_agent == owner_agent  # one agent actor per (user, surface); the delegation was replaced
    with store.connection() as db:
        store.authorize(db, owner_agent, sid)
        with pytest.raises(DomainError, match='forbidden'):
            store.authorize(db, owner_agent, sid, write=True)


def test_delegations_never_exceed_the_delegating_users_role_or_the_ceiling(env):
    sid = new_study(env)['study_id']
    store, actors = env['store'], env['actors']
    with store.connection(write=True) as db:
        reader_agent = store.ensure_agent_actor(db, actors['reader'], 'local_mcp', 'Coding agent (local)')
        stranger_agent = store.ensure_agent_actor(db, actors['stranger'], 'local_mcp', 'Coding agent (local)')
        writer_agent = store.ensure_agent_actor(db, actors['writer'], 'local_mcp', 'Coding agent (local)')
        later = time.time() + 3600
        with pytest.raises(DomainError, match='forbidden'):
            store.create_delegation(db, reader_agent, sid, 'writer', WRITER_EFFECTS, later)
        with pytest.raises(DomainError, match='forbidden'):
            store.create_delegation(db, writer_agent, sid, 'reader', ('read', 'draft'), later)
        with pytest.raises(DomainError, match='resource_not_found'):
            store.create_delegation(db, stranger_agent, sid, 'reader', READER_EFFECTS, later)
        for ceiling, effects, expires in (('writer', ('read', 'delete'), later), ('writer', ('read', 'archive'), later),
                                          ('writer', ('read', 'manage_access'), later), ('owner', ('read',), later),
                                          ('writer', (), later), ('writer', ('draft',), later),
                                          ('writer', ('read',), time.time() - 1)):
            with pytest.raises(DomainError, match='invalid_request'):
                store.create_delegation(db, writer_agent, sid, ceiling, effects, expires)
        # An agent for a reader (Reviewer) may read, post notes and issue reports and record reviews only.
        review = store.create_delegation(db, reader_agent, sid, 'reader', ('read', 'outside_study', 'review'), later)
    assert review['effects'] == frozenset({'read', 'outside_study', 'review'})
    with store.connection() as db:
        store.authorize(db, reader_agent, sid)
        with pytest.raises(DomainError, match='forbidden'):
            store.authorize(db, reader_agent, sid, write=True)
    assert env['auth'].mint_agent_session(review['delegation_id'])['read_only'] is True


def test_one_live_delegation_per_agent_and_study_renewal_replaces_it(env):
    sid = new_study(env)['study_id']
    agent, first = delegate(env, sid)
    token = env['auth'].mint_tool_token(first['delegation_id'], ttl_hours=1, client_label='Codex')['token']
    session = env['auth'].mint_agent_session(first['delegation_id'])
    _, second = delegate(env, sid)
    assert second['delegation_id'] != first['delegation_id']
    with sqlite3.connect(env['path']) as db:
        live = db.execute('SELECT delegation_id FROM agent_delegations WHERE agent_actor_id=? AND revoked_at IS NULL',
                          (agent,)).fetchall()
        assert live == [(second['delegation_id'],)]
        with pytest.raises(sqlite3.IntegrityError):
            db.execute('UPDATE agent_delegations SET revoked_at=NULL,revoked_reason=NULL WHERE delegation_id=?',
                       (first['delegation_id'],))
    with pytest.raises(DomainError, match='unauthenticated'):
        env['auth'].verify_tool_token(token)
    with pytest.raises(DomainError, match='unauthenticated'):
        env['auth'].authenticate(session['token'])


def test_revoked_or_expired_delegation_refuses_the_next_call(env):
    sid = new_study(env)['study_id']
    agent, delegation = delegate(env, sid)
    client = agent_client(env['app'], env['auth'].mint_agent_session(delegation['delegation_id']))
    token = env['auth'].mint_tool_token(delegation['delegation_id'], ttl_hours=8, client_label='Codex')['token']
    assert client.get(f'/api/1/studies/{sid}/runs').status_code == 200
    assert env['auth'].revoke_delegation(delegation['delegation_id']) is True
    assert env['auth'].revoke_delegation(delegation['delegation_id']) is False
    assert client.get(f'/api/1/studies/{sid}/runs').status_code == 401
    with pytest.raises(DomainError, match='unauthenticated'):
        env['auth'].verify_tool_token(token)
    with pytest.raises(DomainError, match='unauthenticated'):
        env['auth'].mint_agent_session(delegation['delegation_id'])
    with env['store'].connection() as db:
        with pytest.raises(DomainError, match='resource_not_found'):
            env['store'].authorize(db, agent, sid)

    _, renewed = delegate(env, sid)
    client = agent_client(env['app'], env['auth'].mint_agent_session(renewed['delegation_id']))
    token = env['auth'].mint_tool_token(renewed['delegation_id'], ttl_hours=8, client_label='Codex')['token']
    assert client.get(f'/api/1/studies/{sid}/runs').status_code == 200
    with sqlite3.connect(env['path']) as db:
        db.execute('UPDATE agent_delegations SET expires_at=0 WHERE delegation_id=?', (renewed['delegation_id'],))
    assert client.get(f'/api/1/studies/{sid}/runs').status_code == 401
    with pytest.raises(DomainError, match='unauthenticated'):
        env['auth'].verify_tool_token(token)
    with env['store'].connection() as db:
        with pytest.raises(DomainError, match='resource_not_found'):
            env['store'].authorize(db, agent, sid)


def test_expired_agent_session_is_refused(env):
    sid = new_study(env)['study_id']
    _, delegation = delegate(env, sid)
    session = env['auth'].mint_agent_session(delegation['delegation_id'])
    assert session['expires_at'] <= time.time() + 15 * 60 + 1
    with sqlite3.connect(env['path']) as db:
        db.execute('UPDATE agent_api_sessions SET expires_at=0')
    assert agent_client(env['app'], session).get(f'/api/1/studies/{sid}/runs').status_code == 401


def test_owner_recovery_revokes_agent_credentials(env):
    sid = new_study(env)['study_id']
    agent, delegation = delegate(env, sid)
    session = env['auth'].mint_agent_session(delegation['delegation_id'])
    token = env['auth'].mint_tool_token(delegation['delegation_id'], ttl_hours=8, client_label='Codex')['token']
    env['auth'].recover('another long recovery password')
    with pytest.raises(DomainError, match='unauthenticated'):
        env['auth'].authenticate(session['token'])
    with pytest.raises(DomainError, match='unauthenticated'):
        env['auth'].verify_tool_token(token)
    with sqlite3.connect(env['path']) as db:
        assert db.execute('SELECT count(*) FROM agent_api_sessions').fetchone() == (0,)
        assert db.execute('SELECT count(*) FROM agent_delegations WHERE revoked_at IS NULL').fetchone() == (0,)
        assert db.execute('SELECT revoked_reason FROM agent_delegations').fetchall() == [('owner_recovery',)]
        assert db.execute('SELECT count(*) FROM agent_tool_tokens WHERE revoked_at IS NULL').fetchone() == (0,)
    with env['store'].connection() as db:
        with pytest.raises(DomainError, match='resource_not_found'):
            env['store'].authorize(db, agent, sid)


def test_agent_actor_cannot_sign_in(env):
    sid = new_study(env)['study_id']
    agent, _ = delegate(env, sid)
    with sqlite3.connect(env['path']) as db:
        assert db.execute('SELECT count(*) FROM users WHERE actor_id=?', (agent,)).fetchone() == (0,)
    client = TestClient(env['app'], base_url=ORIGIN)
    for username in (agent, 'Coding agent (local)'):
        response = client.post('/api/1/session', json=dict(username=username, password=PASSWORD),
                               headers={'Origin': ORIGIN})
        assert response.status_code == 401, response.text
    with pytest.raises(DomainError, match='unauthenticated'):
        env['auth'].login(agent, PASSWORD)


def test_receipts_written_through_a_writer_delegation_carry_the_agent_actor(env):
    study = new_study(env)
    sid = study['study_id']
    agent, _ = delegate(env, sid)
    store, command = env['store'], uid()
    updated = store.update_study(agent, sid, command, study['revision'], dict(description='Written by the agent'))
    assert updated['description'] == 'Written by the agent'
    with store.connection() as db:
        receipt = store.command_receipt(db, sid, 'study', command)
    assert receipt['actor_id'] == agent and receipt['actor_id'] != env['actors']['writer']
    read_only_agent, _ = delegate(env, sid, user='owner', effects=('read',))
    with pytest.raises(DomainError, match='forbidden'):
        store.update_study(read_only_agent, sid, uid(), updated['revision'], dict(description='Refused'))


def test_tool_tokens_are_prefixed_256_bit_and_stored_only_as_hashes(env):
    sid = new_study(env)['study_id']
    _, delegation = delegate(env, sid)
    minted = env['auth'].mint_tool_token(delegation['delegation_id'], ttl_hours=8, client_label='Codex')
    token = minted['token']
    assert token.startswith(TOKEN_PREFIX)
    secret = token[len(TOKEN_PREFIX):]
    assert len(base64.urlsafe_b64decode(secret + '=' * (-len(secret) % 4))) == 32
    verified = env['auth'].verify_tool_token(token)
    assert verified['token_id'] == minted['token_id'] and verified['study_id'] == sid
    assert verified['delegation_id'] == delegation['delegation_id'] and verified['read_only'] is False
    session = env['auth'].mint_agent_session(delegation['delegation_id'])
    dump = '\n'.join(snapshot(env['path']))
    for value in (token, secret, session['token'], session['csrf_token']):
        assert value not in dump
    with sqlite3.connect(env['path']) as db:
        assert db.execute('SELECT audience FROM agent_tool_tokens').fetchall() == [('/mcp',)]
    for ttl in (0, 25, True, 1.5):
        with pytest.raises(DomainError, match='invalid_request'):
            env['auth'].mint_tool_token(delegation['delegation_id'], ttl_hours=ttl, client_label='Codex')
    for forged in (secret, TOKEN_PREFIX + secret[::-1], TOKEN_PREFIX, None):
        with pytest.raises(DomainError, match='unauthenticated'):
            env['auth'].verify_tool_token(forged)


# ---- The one pre-study command: study creation owned by the delegating user ---------

def test_agent_study_creation_makes_the_delegating_user_owner_and_never_widens_the_delegation(env):
    sid = new_study(env, 'Delegated')['study_id']
    agent, delegation = delegate(env, sid)
    store, path, command = env['store'], env['path'], uid()
    session = env['auth'].mint_agent_session(delegation['delegation_id'])
    with sqlite3.connect(path) as db:
        before = db.execute('SELECT * FROM agent_delegations').fetchall()
    created = store.create_study(agent, command, 'Agent study', delegation_id=delegation['delegation_id'])
    new = created['study_id']
    assert created['name'] == 'Agent study'
    assert memberships(path, new) == {env['actors']['writer']: 'owner'}
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT count(*) FROM memberships WHERE actor_id=?', (agent,)).fetchone() == (0,)
        assert db.execute('SELECT * FROM agent_delegations').fetchall() == before
    with store.connection() as db:
        receipt = store.command_receipt(db, 'actor:' + agent, 'study_create', command)
        with pytest.raises(DomainError, match='resource_not_found'):
            store.authorize(db, agent, new)
    assert receipt['actor_id'] == agent and receipt['state'] == 'committed'
    client = agent_client(env['app'], session)
    assert client.get(f'/api/1/studies/{new}/runs').status_code == 404
    assert client.get(f'/api/1/studies/{sid}/runs').status_code == 200
    assert store.list_studies(agent) == [store.study(env['actors']['writer'], sid)]
    assert env['clients']['writer'].get(f'/api/1/studies/{new}').status_code == 200

    # A replay and the pre-study receipt read return the stored outcome without authorizing the agent.
    assert store.create_study(agent, command, 'Agent study', delegation_id=delegation['delegation_id']) == created
    assert store.receipt(agent, None, 'study_create', command)['result'] == created
    replayed = store.replay(agent, None, 'study_create', command, dict(operation='create_study', name='Agent study'))
    assert replayed['result'] == created
    with pytest.raises(DomainError, match='command_payload_conflict'):
        store.create_study(agent, command, 'Another name', delegation_id=delegation['delegation_id'])
    with store.connection() as db:
        with pytest.raises(DomainError, match='resource_not_found'):
            store.authorize(db, agent, new)
    assert memberships(path, new) == {env['actors']['writer']: 'owner'}

    # Once the delegating user is no longer a member of the created study, the outcome is not disclosed.
    owner, writer = env['actors']['owner'], env['actors']['writer']
    revision = store.set_membership(writer, new, uid(), created['revision'], owner, 'owner')['revision']
    store.set_membership(owner, new, uid(), revision, writer, None)
    with pytest.raises(DomainError, match='resource_not_found'):
        store.receipt(agent, None, 'study_create', command)
    with pytest.raises(DomainError, match='resource_not_found'):
        store.create_study(agent, command, 'Agent study', delegation_id=delegation['delegation_id'])


def test_agent_study_creation_needs_a_live_writer_delegation_with_record(env):
    sid = new_study(env)['study_id']
    store, path = env['store'], env['path']
    read_agent, read_only = delegate(env, sid, user='owner', effects=('read', 'draft'))
    agent, delegation = delegate(env, sid)
    other_sid = new_study(env, 'Other')['study_id']
    before = snapshot(path)
    refused = [
        lambda: store.create_study(read_agent, uid(), 'No record effect', delegation_id=read_only['delegation_id']),
        lambda: store.create_study(agent, uid(), 'No delegation'),
        lambda: store.create_study(agent, uid(), 'Unknown delegation', delegation_id=uid()),
        lambda: store.create_study(agent, uid(), "Another agent's delegation", delegation_id=read_only['delegation_id']),
    ]
    for attempt in refused:
        with pytest.raises(DomainError, match='forbidden'):
            attempt()
    assert snapshot(path) == before

    set_role(env, sid, 'writer', 'reader')
    with pytest.raises(DomainError, match='forbidden'):
        store.create_study(agent, uid(), 'Delegating user demoted', delegation_id=delegation['delegation_id'])
    set_role(env, sid, 'writer', 'writer')
    env['auth'].revoke_delegation(delegation['delegation_id'])
    with pytest.raises(DomainError, match='forbidden'):
        store.create_study(agent, uid(), 'Revoked delegation', delegation_id=delegation['delegation_id'])
    _, expired = delegate(env, sid)
    with sqlite3.connect(path) as db:
        db.execute('UPDATE agent_delegations SET expires_at=0 WHERE delegation_id=?', (expired['delegation_id'],))
    with pytest.raises(DomainError, match='forbidden'):
        store.create_study(agent, uid(), 'Expired delegation', delegation_id=expired['delegation_id'])
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT count(*) FROM receipts WHERE category='study_create' AND actor_id IN (?,?)",
                          (agent, read_agent)).fetchone() == (0,)
    assert other_sid


def test_every_other_pre_study_command_of_an_agent_actor_is_refused(env):
    sid = new_study(env)['study_id']
    agent, delegation = delegate(env, sid)
    store, path = env['store'], env['path']
    ran = []
    before = snapshot(path)
    for category in ('study', 'membership', 'study_archive', 'evidence', 'model', 'configuration', 'run'):
        with pytest.raises(DomainError, match='forbidden'):
            store.command(agent, None, category, uid(), dict(operation=category), lambda db: ran.append(category) or {},
                          delegation_id=delegation['delegation_id'])
        with pytest.raises(DomainError, match='forbidden'):
            store.replay(agent, None, category, uid(), dict(operation=category))
        with pytest.raises(DomainError, match='resource_not_found'):
            store.receipt(agent, None, category, uid())
    assert ran == [] and snapshot(path) == before


def test_human_study_creation_and_its_receipt_read_are_unchanged(env):
    store, owner, command = env['store'], env['actors']['owner'], uid()
    client = env['clients']['owner']
    created = client.post('/api/1/studies', json=dict(command_id=command, name='Human study'))
    assert created.status_code == 201, created.text
    study = created.json()['data']
    assert memberships(env['path'], study['study_id']) == {owner: 'owner'}
    read = client.get(f'/api/1/commands/{command}', params=dict(category='study_create'))
    assert read.status_code == 200, read.text
    assert read.json()['data']['result'] == study and read.json()['data']['state'] == 'committed'
    replay = client.post('/api/1/studies', json=dict(command_id=command, name='Human study'))
    assert replay.status_code == 201 and replay.json()['data'] == study
    with store.connection() as db:
        assert store.command_receipt(db, 'actor:' + owner, 'study_create', command)['actor_id'] == owner
    assert env['clients']['writer'].get(f'/api/1/commands/{command}', params=dict(category='study_create')).status_code == 404
