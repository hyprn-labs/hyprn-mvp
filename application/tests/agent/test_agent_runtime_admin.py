"""Agent runtime administration: local tool tokens, attribution and the access read.

A tool token is minted only by the operator command, printed once and stored only as its
SHA-256; renewal replaces the previous delegation and its tokens; minting is refused while
agent access is off. The attribution read names the agent and the delegating user separately,
is for people only and withholds any entry its receipt does not attribute to that agent. The
access read reports why an agent's access ended. Only the study Owner lists and revokes the
study's tokens, and revocation ends the agent's access at its next call. Fresh synthetic
off-cloud stores only; no modeling service, runtime or live store.
"""

import hashlib
import json
import logging
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from conftest import LOOPBACK_ORIGIN
from hyprn_mvp_app import api as api_module
from hyprn_mvp_app import auth as auth_module
from hyprn_mvp_app.agent_runtime import __main__ as operator
from hyprn_mvp_app.agent_runtime import attribution, control, delegations, tokens
from hyprn_mvp_app.api import create_app
from hyprn_mvp_app.auth import Auth
from hyprn_mvp_app.contracts import DomainError
from hyprn_mvp_app.store import Store

ORIGIN = LOOPBACK_ORIGIN
PASSWORD = 'correct horse battery staple'
COOKIE = 'hyprn_mvp_session'
ENABLED = {control.AGENT_ENABLED: 'true'}
WRITER_EFFECTS = ('read', 'draft', 'record', 'submit', 'outside_study')
SOURCES = Path(__file__).resolve().parents[2] / 'src'
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
    env, sid, *, user='owner', surface='local_mcp', ceiling='writer', effects=WRITER_EFFECTS
):
    store = env['store']
    with store.connection(write=True) as db:
        agent = store.ensure_agent_actor(db, env['actors'][user], surface, 'Codex (local)')
        delegation = store.create_delegation(db, agent, sid, ceiling, effects, time.time() + 3600)
    return agent, delegation


def mint(env, sid, **options):
    return tokens.mint_local(env['store'], env['auth'], 'owner', sid, environ=ENABLED, **options)


def store_bytes(path):
    return b''.join(p.read_bytes() for p in sorted(path.parent.glob(path.name + '*')))


def run_operator(env, *args, environ=ENABLED):
    process_env = {
        'PATH': os.environ.get('PATH', ''),
        'PYTHONPATH': str(SOURCES),
        **environ,
    }
    return subprocess.run(
        [
            sys.executable,
            '-B',
            '-m',
            'hyprn_mvp_app.agent_runtime',
            *args,
            '--store',
            str(env['path']),
        ],
        capture_output=True,
        text=True,
        env=process_env,
        timeout=120,
    )


# ---- Local tool tokens through the operator command --------------------------------------


def test_minted_token_is_printed_once_and_kept_only_as_its_hash(env):
    sid = new_study(env)
    argv = ['mint-token', '--study', sid, '--owner', 'owner', '--client-label', 'Codex']
    done = run_operator(env, *argv)
    assert done.returncode == 0, done.stderr
    assert done.stdout.count('\n') == 1 and done.stdout.endswith('\n')
    token = done.stdout[:-1]
    assert token.startswith(TOKEN_PREFIX) and token not in done.stderr
    assert token not in ' '.join(done.args)
    stored = store_bytes(env['path'])
    assert token.encode() not in stored
    assert hashlib.sha256(token.encode()).hexdigest().encode() in stored
    verified = env['auth'].verify_tool_token(token)
    assert verified['study_id'] == sid and verified['read_only']
    assert verified['effects'] == frozenset({'read', 'outside_study'})


def test_operator_mint_never_writes_the_token_to_log_records(env, capsys, caplog):
    sid = new_study(env)
    caplog.set_level(logging.DEBUG)
    argv = ['mint-token', '--store', str(env['path']), '--study', sid, '--owner', 'owner']
    assert operator.main(argv, environ=ENABLED) == 0
    out = capsys.readouterr()
    token = out.out.strip()
    assert out.out == token + '\n' and token.startswith(TOKEN_PREFIX) and out.err == ''
    assert all(token not in record.getMessage() for record in caplog.records)
    assert token not in caplog.text


def test_list_and_revoke_round_trip_without_secrets(env):
    sid = new_study(env)
    token_id, token = mint(env, sid, client_label='Claude Code')
    listed = run_operator(env, 'list-tokens', '--study', sid)
    assert listed.returncode == 0, listed.stderr
    rows = json.loads(listed.stdout)
    assert [row['token_id'] for row in rows] == [token_id]
    assert rows[0]['client_label'] == 'Claude Code' and rows[0]['revoked_at'] is None
    assert rows[0]['agent']['display_name'] == delegations.LOCAL_AGENT_NAME
    assert rows[0]['delegator'] == dict(actor_id=env['actors']['owner'], display_name='owner')
    assert token not in listed.stdout
    assert hashlib.sha256(token.encode()).hexdigest() not in listed.stdout
    revoked = run_operator(env, 'revoke', '--study', sid, '--token-id', token_id)
    assert revoked.returncode == 0, revoked.stderr
    assert json.loads(revoked.stdout) == dict(revoked=[token_id])
    with pytest.raises(DomainError) as refused:
        env['auth'].verify_tool_token(token)
    assert refused.value.status == 401
    assert tokens.list_for_study(env['store'], sid)[0]['revoked_at'] is not None


def test_revoke_without_a_token_id_ends_every_local_delegation_of_the_study(env):
    sid, other = new_study(env), new_study(env, 'Other')
    _, token = mint(env, sid)
    _, kept = mint(env, other)
    assert len(tokens.revoke(env['store'], sid)) == 1
    with pytest.raises(DomainError):
        env['auth'].verify_tool_token(token)
    assert env['auth'].verify_tool_token(kept)['study_id'] == other


def test_renewal_for_the_same_study_revokes_the_previous_token(env):
    sid = new_study(env)
    _, first = mint(env, sid)
    _, second = mint(env, sid)
    with pytest.raises(DomainError) as refused:
        env['auth'].verify_tool_token(first)
    assert refused.value.status == 401
    assert env['auth'].verify_tool_token(second)['study_id'] == sid
    access = env['clients']['owner'].get(f'/api/1/studies/{sid}/agent/access').json()['data']
    assert [agent['state'] for agent in access['agents']] == ['active']


@pytest.mark.parametrize(
    'environ',
    [
        {},
        {control.AGENT_ENABLED: 'false'},
        {control.AGENT_ENABLED: 'TRUE'},
        {control.AGENT_ENABLED: '1'},
    ],
)
def test_minting_is_refused_unless_agent_access_is_exactly_on(env, environ):
    sid = new_study(env)
    with pytest.raises(DomainError) as refused:
        tokens.mint_local(env['store'], env['auth'], 'owner', sid, environ=environ)
    assert refused.value.status == 403
    done = run_operator(env, 'mint-token', '--study', sid, '--owner', 'owner', environ=environ)
    assert done.returncode == 1 and done.stdout == ''
    assert tokens.list_for_study(env['store'], sid) == []


def test_local_delegation_ceiling_follows_the_users_role_and_needs_membership(env):
    sid = new_study(env)
    for user, ceiling in (('owner', 'writer'), ('writer', 'writer'), ('reader', 'reader')):
        tokens.mint_local(env['store'], env['auth'], user, sid, environ=ENABLED)
        with env['store'].connection() as db:
            row = db.execute(
                'SELECT role_ceiling,allowed_effects FROM agent_delegations '
                'WHERE delegator_actor_id=? AND revoked_at IS NULL',
                (env['actors'][user],),
            ).fetchone()
        assert row['role_ceiling'] == ceiling
        assert json.loads(row['allowed_effects']) == ['outside_study', 'read']
    with pytest.raises(DomainError) as refused:
        tokens.mint_local(env['store'], env['auth'], 'stranger', sid, environ=ENABLED)
    assert refused.value.status == 404


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
        ('GET', '/api/1/studies/{study_id}/agent/tokens'),
        ('POST', '/api/1/studies/{study_id}/agent/tokens/{token_id}/revoke'),
    ]


# ---- Attribution read -------------------------------------------------------------------


def agent_context_change(env, sid, agent, *, name):
    """A study context change written by the agent actor itself (its receipt names it)."""
    store = env['store']
    command = uid()
    revision = store.study(env['actors']['owner'], sid)['revision']
    store.update_study(agent, sid, command, revision, dict(description=name))
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
    env['store'].update_study(
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
        f'/api/1/studies/{sid}/agent/tokens',
    ):
        assert client.get(path).status_code == 403, path


def test_agent_routes_refuse_agent_sessions_even_past_the_route_allowlist(env, monkeypatch):
    """The human-only actor dependency refuses an agent session on its own (defence in depth)."""
    sid = new_study(env)
    token_id, _ = mint(env, sid)
    _, delegation = delegate(env, sid, surface='remote_mcp')
    monkeypatch.setattr(api_module, 'route_allowed', lambda *args, **kwargs: True)
    client = agent_client(env['app'], env['auth'].mint_agent_session(delegation['delegation_id']))
    for path in (
        f'/api/1/studies/{sid}/agent/attribution',
        '/api/1/agent/attribution/studies',
        f'/api/1/studies/{sid}/agent/access',
        f'/api/1/studies/{sid}/agent/tokens',
    ):
        assert client.get(path).status_code == 403, path
    revoke = client.post(
        f'/api/1/studies/{sid}/agent/tokens/{token_id}/revoke', json=dict(command_id=uid())
    )
    assert revoke.status_code == 403
    assert tokens.list_for_study(env['store'], sid)[0]['revoked_at'] is None


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
    _, revoked = delegate(env, sid, user='owner', surface='local_mcp')
    active, _ = delegate(env, sid, user='owner', surface='remote_mcp')
    _, expired = delegate(
        env,
        sid,
        user='reader',
        surface='local_mcp',
        ceiling='reader',
        effects=('read', 'outside_study'),
    )
    changed, _ = delegate(env, sid, user='writer', surface='local_mcp')
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


# ---- Owner token routes -------------------------------------------------------------------


def test_only_the_study_owner_lists_and_revokes_tokens(env):
    sid = new_study(env)
    token_id, token = mint(env, sid)
    secret_hash = hashlib.sha256(token.encode()).hexdigest()
    for who in ('writer', 'reader'):
        client = env['clients'][who]
        assert client.get(f'/api/1/studies/{sid}/agent/tokens').status_code == 403
        refused = client.post(
            f'/api/1/studies/{sid}/agent/tokens/{token_id}/revoke', json=dict(command_id=uid())
        )
        assert refused.status_code == 403
    assert env['clients']['stranger'].get(f'/api/1/studies/{sid}/agent/tokens').status_code == 404
    owner = env['clients']['owner']
    listed = owner.get(f'/api/1/studies/{sid}/agent/tokens')
    assert listed.status_code == 200, listed.text
    assert [row['token_id'] for row in listed.json()['data']] == [token_id]
    assert token not in listed.text and secret_hash not in listed.text
    command = uid()
    revoked = owner.post(
        f'/api/1/studies/{sid}/agent/tokens/{token_id}/revoke', json=dict(command_id=command)
    )
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()['data']['token_id'] == token_id and revoked.json()['data']['revoked_at']
    assert token not in revoked.text and secret_hash not in revoked.text
    with pytest.raises(DomainError) as refused:
        env['auth'].verify_tool_token(token)
    assert refused.value.status == 401
    access = owner.get(f'/api/1/studies/{sid}/agent/access').json()['data']['agents']
    assert [(a['state'], a['reason']) for a in access] == [('ended', 'revoked')]
    repeat = owner.post(
        f'/api/1/studies/{sid}/agent/tokens/{token_id}/revoke', json=dict(command_id=command)
    )
    assert repeat.status_code == 200 and repeat.json()['data'] == revoked.json()['data']


def test_revoking_another_studys_token_is_not_found_and_changes_nothing(env):
    sid, other = new_study(env), new_study(env, 'Other')
    token_id, token = mint(env, other)
    refused = env['clients']['owner'].post(
        f'/api/1/studies/{sid}/agent/tokens/{token_id}/revoke', json=dict(command_id=uid())
    )
    assert refused.status_code == 404
    assert env['auth'].verify_tool_token(token)['study_id'] == other
