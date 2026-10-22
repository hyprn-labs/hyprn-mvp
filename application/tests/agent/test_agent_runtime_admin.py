"""Embedded Assistant attribution, access and retired external entrypoint checks.

Human-only reads retain membership and delegation enforcement. External token
administration and CLI minting no longer exist. Fresh synthetic stores only.
"""

from legacy_study_support import seed_legacy_context

import json
import sqlite3
import time
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from conftest import LOOPBACK_ORIGIN
from hyprn_mvp_app import api as api_module
from hyprn_mvp_app import auth as auth_module
from hyprn_mvp_app.agent_runtime import attribution, control, delegations
from hyprn_mvp_app.api import create_app
from hyprn_mvp_app.auth import Auth
from hyprn_mvp_app.contracts import DomainError
from hyprn_mvp_app.store import Store

ORIGIN = LOOPBACK_ORIGIN
PASSWORD = 'correct horse battery staple'
COOKIE = 'hyprn_mvp_session'
ENABLED = {control.AGENT_ENABLED: 'true'}
WRITER_EFFECTS = ('read', 'draft', 'record', 'submit', 'outside_study')


def uid():
    return str(uuid4())


_HASH = []


def password_hash():
    if not _HASH:
        _HASH.append(auth_module.password_hash(PASSWORD))
    return _HASH[0]


def login(app, username):
    client = TestClient(app, base_url=ORIGIN)
    session = client.post(
        '/api/1/session',
        json=dict(username=username, password=PASSWORD),
        headers={'Origin': ORIGIN},
    )
    assert session.status_code == 200, session.text
    client.headers.update({'Origin': ORIGIN, 'X-CSRF-Token': session.json()['data']['csrf_token']})
    return client


def agent_client(app, session):
    client = TestClient(app, base_url=ORIGIN)
    client.cookies.set(COOKIE, session['token'])
    client.headers.update({'Origin': ORIGIN, 'X-CSRF-Token': session['csrf_token']})
    return client


class UnavailableModeling:
    def call(self, *_, **__):
        raise DomainError('backend_unavailable', 503, outcome='unknown')


@pytest.fixture
def env(tmp_path):
    path = tmp_path / 'agent.sqlite'
    store = Store(path)
    auth = Auth(store, ORIGIN)
    actors = {name: uid() for name in ('owner', 'writer', 'reader', 'stranger')}
    with store.connection(write=True) as db:
        for name, actor in actors.items():
            db.execute(
                'INSERT INTO users(actor_id,username,password_hash) VALUES(?,?,?)',
                (actor, name, password_hash()),
            )
    app = create_app(store, auth, UnavailableModeling(), environ=dict(ENABLED))
    clients = {name: login(app, name) for name in actors}
    return dict(store=store, auth=auth, app=app, actors=actors, clients=clients, path=path)


def new_study(env, name='Study'):
    created = env['clients']['owner'].post('/api/1/studies', json=dict(command_id=uid(), name=name))
    assert created.status_code == 201, created.text
    sid = created.json()['data']['study_id']
    revision = created.json()['data']['revision']
    for who in ('writer', 'reader'):
        revision = env['store'].set_membership(
            env['actors']['owner'], sid, uid(), revision, env['actors'][who], who
        )['revision']
    return sid


def set_role(env, sid, who, role):
    store, owner = env['store'], env['actors']['owner']
    revision = store.study(owner, sid)['revision']
    store.set_membership(owner, sid, uid(), revision, env['actors'][who], role)


def delegate(
    env, sid, *, user='owner', surface='claude_managed', ceiling='writer', effects=WRITER_EFFECTS
):
    store = env['store']
    with store.connection(write=True) as db:
        agent = store.ensure_agent_actor(db, env['actors'][user], surface, 'Codex (local)')
        delegation = store.create_delegation(db, agent, sid, ceiling, effects, time.time() + 3600)
    return agent, delegation


# ---- Retired external entrypoints --------------------------------------------------------


def test_no_route_mints_a_token(env):
    agent_routes = sorted(
        (sorted(route.methods)[0], route.path)
        for route in env['app'].routes
        if '/agent' in route.path
    )
    assert agent_routes == [
        ('GET', '/api/1/agent/attribution/studies'),
        ('GET', '/api/1/studies/{study_id}/agent/access'),
        ('GET', '/api/1/studies/{study_id}/agent/attribution'),
    ]


def test_retired_external_agent_entrypoints_are_unavailable(env):
    import importlib.util

    sid = new_study(env)
    owner = env['clients']['owner']
    assert owner.get(f'/api/1/studies/{sid}/agent/tokens').status_code == 404
    assert owner.post(
        f'/api/1/studies/{sid}/agent/tokens/{uid()}/revoke',
        json=dict(command_id=uid()),
    ).status_code == 404
    # Browser cookies are scoped to /api/1: the retired external path receives none.
    assert owner.post('/mcp', json={'method': 'initialize'}).status_code == 401
    assert all(route.path != '/mcp' for route in env['app'].routes)
    assert importlib.util.find_spec('hyprn_mvp_app.agent_runtime.__main__') is None
    assert importlib.util.find_spec('hyprn_mvp_app.agent_runtime.tokens') is None
    with env['store'].connection(write=True) as db:
        for surface in ('local_mcp', 'remote_mcp'):
            with pytest.raises(DomainError, match='invalid_request'):
                env['store'].ensure_agent_actor(
                    db, env['actors']['owner'], surface, 'External agent'
                )


# ---- Attribution read -------------------------------------------------------------------


def agent_context_change(env, sid, agent, *, name):
    """A study context change written by the agent actor itself (its receipt names it)."""
    store = env['store']
    command = uid()
    revision = store.study(env['actors']['owner'], sid)['revision']
    seed_legacy_context(store, agent, sid, command, revision, dict(description=name))
    return command


def entry(env, sid, agent, command, *, kind='study_context', category='study', record_id=None):
    with env['store'].connection(write=True) as db:
        return attribution.record(
            db,
            dict(
                study_id=sid,
                record_kind=kind,
                record_id=record_id or sid,
                version_id=None,
                command_category=category,
                command_id=command,
                agent_actor_id=agent,
                agent_display_name='Codex (local)',
                delegator_actor_id=env['actors']['owner'],
            ),
        )


def test_attribution_names_agent_and_delegator_separately_and_withholds_foreign_receipts(env):
    sid = new_study(env)
    agent, _ = delegate(env, sid)
    command = agent_context_change(env, sid, agent, name='Written by the agent')
    entry(env, sid, agent, command)
    # A person's receipt claimed for the agent is withheld.
    human = uid()
    revision = env['store'].study(env['actors']['owner'], sid)['revision']
    seed_legacy_context(env['store'],
        env['actors']['owner'], sid, human, revision, dict(description='Person')
    )
    entry(env, sid, agent, human)
    # An entry with no receipt at all is withheld.
    entry(env, sid, agent, uid())
    page = env['clients']['reader'].get(f'/api/1/studies/{sid}/agent/attribution')
    assert page.status_code == 200, page.text
    items = page.json()['data']['items']
    assert [item['command_id'] for item in items] == [command]
    assert items[0]['agent'] == dict(actor_id=agent, display_name='Codex (local)')
    assert items[0]['delegator'] == dict(actor_id=env['actors']['owner'], display_name='owner')
    assert 'confirmer' not in json.dumps(page.json()) and page.json()['data']['next_cursor'] is None


def test_attribution_pages_newest_first_with_an_opaque_cursor(env):
    sid = new_study(env)
    agent, _ = delegate(env, sid)
    commands = []
    for index in range(3):
        commands.append(agent_context_change(env, sid, agent, name=f'Change {index}'))
        entry(env, sid, agent, commands[-1])
    client = env['clients']['owner']
    first = client.get(f'/api/1/studies/{sid}/agent/attribution', params=dict(limit=2)).json()[
        'data'
    ]
    assert [item['command_id'] for item in first['items']] == commands[:0:-1]
    rest = client.get(
        f'/api/1/studies/{sid}/agent/attribution', params=dict(limit=2, cursor=first['next_cursor'])
    ).json()['data']
    assert [item['command_id'] for item in rest['items']] == commands[:1] and rest[
        'next_cursor'
    ] is None
    for bad in (dict(limit=0), dict(limit=101), dict(cursor='not a cursor')):
        assert client.get(f'/api/1/studies/{sid}/agent/attribution', params=bad).status_code == 400


def test_attribution_is_for_members_and_never_for_agent_sessions(env):
    sid = new_study(env)
    agent, delegation = delegate(env, sid)
    assert (
        env['clients']['stranger'].get(f'/api/1/studies/{sid}/agent/attribution').status_code == 404
    )
    session = env['auth'].mint_agent_session(delegation['delegation_id'])
    client = agent_client(env['app'], session)
    for path in (
        f'/api/1/studies/{sid}/agent/attribution',
        '/api/1/agent/attribution/studies',
        f'/api/1/studies/{sid}/agent/access',
    ):
        assert client.get(path).status_code == 403, path


def test_agent_routes_refuse_agent_sessions_even_past_the_route_allowlist(env, monkeypatch):
    """The human-only actor dependency refuses an agent session on its own (defence in depth)."""
    sid = new_study(env)
    _, delegation = delegate(env, sid, surface='openai_agents')
    monkeypatch.setattr(api_module, 'route_allowed', lambda *args, **kwargs: True)
    client = agent_client(env['app'], env['auth'].mint_agent_session(delegation['delegation_id']))
    for path in (
        f'/api/1/studies/{sid}/agent/attribution',
        '/api/1/agent/attribution/studies',
        f'/api/1/studies/{sid}/agent/access',
    ):
        assert client.get(path).status_code == 403, path


def agent_created_study(env, sid, agent, delegation):
    command = uid()
    created = env['store'].create_study(
        agent, command, 'Started by the agent', delegation_id=delegation['delegation_id']
    )
    new = created['study_id']
    entry(env, new, agent, command, kind='study', category='study_create', record_id=new)
    return new, command


def test_studies_an_agent_created_are_shown_to_members_of_the_new_study_only(env):
    sid = new_study(env)
    agent, delegation = delegate(env, sid)
    new, command = agent_created_study(env, sid, agent, delegation)
    owner = env['clients']['owner']
    listed = owner.get('/api/1/agent/attribution/studies').json()['data']['items']
    assert [
        (item['study_id'], item['record_kind'], item['command_category']) for item in listed
    ] == [(new, 'study', 'study_create')]
    assert listed[0]['agent']['actor_id'] == agent and listed[0]['record_id'] == new
    study_page = owner.get(f'/api/1/studies/{new}/agent/attribution').json()['data']['items']
    assert [item['command_id'] for item in study_page] == [command]
    # The writer is a member of the delegated study but not of the new one.
    assert (
        env['clients']['writer'].get('/api/1/agent/attribution/studies').json()['data']['items']
        == []
    )
    assert (
        env['clients']['writer'].get(f'/api/1/studies/{new}/agent/attribution').status_code == 404
    )


def test_a_created_study_entry_whose_pre_study_receipt_actor_differs_is_withheld(env):
    sid = new_study(env)
    agent, _ = delegate(env, sid)
    # A study a person created, with a forged pre-study receipt in the agent's scope.
    command = uid()
    new = env['store'].create_study(env['actors']['owner'], command, 'Started by a person')[
        'study_id'
    ]
    with sqlite3.connect(env['path']) as db:
        db.execute(
            'INSERT INTO receipts(scope,category,command_id,actor_id,payload_digest,state,result) '
            'VALUES(?,?,?,?,?,?,?)',
            (
                'actor:' + agent,
                'study_create',
                command,
                env['actors']['owner'],
                '0' * 64,
                'committed',
                json.dumps(dict(study_id=new)),
            ),
        )
    entry(env, new, agent, command, kind='study', category='study_create', record_id=new)
    owner = env['clients']['owner']
    assert owner.get('/api/1/agent/attribution/studies').json()['data']['items'] == []
    assert owner.get(f'/api/1/studies/{new}/agent/attribution').json()['data']['items'] == []


def test_attribution_entries_are_never_deleted(env):
    sid = new_study(env)
    agent, _ = delegate(env, sid)
    entry(env, sid, agent, agent_context_change(env, sid, agent, name='Kept'))
    with pytest.raises(sqlite3.IntegrityError, match='never deleted'):
        with sqlite3.connect(env['path']) as db:
            db.execute('DELETE FROM agent_attribution')


# ---- Access read --------------------------------------------------------------------------


def test_access_read_reports_active_revoked_expired_and_membership_changed(env):
    sid = new_study(env)
    _, revoked = delegate(env, sid, user='owner', surface='claude_managed')
    active, _ = delegate(env, sid, user='owner', surface='openai_agents')
    _, expired = delegate(
        env,
        sid,
        user='reader',
        surface='claude_managed',
        ceiling='reader',
        effects=('read', 'outside_study'),
    )
    changed, _ = delegate(env, sid, user='writer', surface='claude_managed')
    env['auth'].revoke_delegation(revoked['delegation_id'])
    with sqlite3.connect(env['path']) as db:
        db.execute(
            'UPDATE agent_delegations SET expires_at=? WHERE delegation_id=?',
            (time.time() - 60, expired['delegation_id']),
        )
    set_role(env, sid, 'writer', 'reader')
    response = env['clients']['reader'].get(f'/api/1/studies/{sid}/agent/access')
    assert response.status_code == 200, response.text
    data = response.json()['data']
    assert data['installation_enabled'] is True
    states = {
        (a['delegator']['display_name'], a['agent']['actor_id'] == active): (
            a['state'],
            a['reason'],
        )
        for a in data['agents']
    }
    assert states == {
        ('owner', False): ('ended', 'revoked'),
        ('owner', True): ('active', 'none'),
        ('reader', False): ('ended', 'expired'),
        ('writer', False): ('ended', 'membership_changed'),
    }
    by_reason = {a['reason']: a for a in data['agents']}
    assert by_reason['revoked']['ended_at'] and by_reason['expired']['ended_at']
    assert (
        by_reason['membership_changed']['ended_at'] is None
        and by_reason['none']['ended_at'] is None
    )
    assert by_reason['membership_changed']['agent']['actor_id'] == changed


def test_access_read_reports_the_installation_kill_switch(env):
    sid = new_study(env)
    app = create_app(env['store'], env['auth'], UnavailableModeling(), environ={})
    data = login(app, 'owner').get(f'/api/1/studies/{sid}/agent/access').json()['data']
    assert data == dict(installation_enabled=False, agents=[])
    assert env['clients']['stranger'].get(f'/api/1/studies/{sid}/agent/access').status_code == 404
