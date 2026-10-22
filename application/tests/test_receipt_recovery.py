"""The owner decides how a client recovers after a lost reply.

Every receipt read carries one closed ``recovery`` value from the one table in ``store``: a
committed or accepted outcome is adopted, a stored rejection is the outcome, an uncertain run is
never resent, a pending model command is resent with the same command id only after its owner
re-queried the modeling service, and a missing receipt is resent except for a run, which is
never resent. A missing receipt in a scope the reader may see is today's 404 with the recovery
in its error object; a reader who may not see the scope gets today's 404 without it. Every
member of today's receipt bodies is unchanged. Fresh synthetic off-cloud stores only; the
modeling service is a test double that is always unavailable.
"""

import json
import time
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from legacy_study_support import seed_legacy_context
from conftest import LOOPBACK_ORIGIN
from hyprn_mvp_app import api as api_module
from hyprn_mvp_app import auth as auth_module
from hyprn_mvp_app.api import create_app
from hyprn_mvp_app.auth import Auth
from hyprn_mvp_app.computational_export import records_for_store
from hyprn_mvp_app.contracts import DomainError
from hyprn_mvp_app.modeling import Coordinator
from hyprn_mvp_app.store import (
    RECEIPT_RETRY_AFTER_S,
    RECOVERY_VALUES,
    Store,
    receipt_recovery,
)
from test_history import client as history_client
from test_run_status import runs_in_every_state
from test_submission import submission  # noqa: F401  (pytest fixture)

ORIGIN = LOOPBACK_ORIGIN
PASSWORD = 'correct horse battery staple'
COOKIE = 'hyprn_mvp_session'
RUN_STATES = ('accepted_run', 'prepared', 'preparation_failed', 'dispatching', 'recorded')
CATEGORIES = (
    'study',
    'study_archive',
    'study_create',
    'evidence',
    'configuration',
    'model',
    'approach_draft',
    'approach_version',
    'approach_restore',
    'computational_record_preview',
    'computational_record_create',
    'run',
)
STATES = ('committed', 'rejected', 'pending_remote', *RUN_STATES, 'uncertain')
WAIT = dict(recovery='wait', retry_after_s=RECEIPT_RETRY_AFTER_S)


def uid():
    return str(uuid4())


_HASH = []


def password_hash():
    if not _HASH:
        _HASH.append(auth_module.password_hash(PASSWORD))
    return _HASH[0]


class UnavailableModeling:
    """Modeling double: every call is a service outage, so nothing remote is ever adopted."""

    def __init__(self):
        self.calls = []

    def call(self, actor, sid, method, path, **_):
        self.calls.append((method, path))
        raise DomainError('backend_unavailable', 503, outcome='unknown')


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


@pytest.fixture
def env(tmp_path):
    path = tmp_path / 'recovery.sqlite'
    store = Store(path)
    auth = Auth(store, ORIGIN)
    actors = {name: uid() for name in ('owner', 'stranger')}
    with store.connection(write=True) as db:
        for name, actor in actors.items():
            db.execute(
                'INSERT INTO users(actor_id,username,password_hash) VALUES(?,?,?)',
                (actor, name, password_hash()),
            )
    model = UnavailableModeling()
    app = create_app(store, auth, model)
    clients = {name: login(app, name) for name in actors}
    created = clients['owner'].post('/api/1/studies', json=dict(command_id=uid(), name='Study'))
    assert created.status_code == 201, created.text
    return dict(
        store=store,
        auth=auth,
        app=app,
        model=model,
        actors=actors,
        clients=clients,
        sid=created.json()['data']['study_id'],
    )


def read(client, sid, category, command):
    path = f'/api/1/studies/{sid}/commands/{command}' if sid else f'/api/1/commands/{command}'
    return client.get(path, params=dict(category=category))


def todays_body(store, scope, category, command):
    """The receipt body as the read returned it before recovery existed."""
    with store.connection() as db:
        row = store.command_receipt(db, scope, category, command)
    result = None if row['state'] == 'pending_remote' else row['result']
    if category == 'model' and row['state'] == 'committed':
        result = result['response']
    return dict(command_id=command, state=row['state'], result=result, error=row['error'])


def recovered(response, expected):
    """The 200 body is today's body plus exactly the recovery members."""
    assert response.status_code == 200, response.text
    data = response.json()['data']
    recovery = {k: data.pop(k) for k in ('recovery', 'retry_after_s') if k in data}
    return data, recovery


def seed(store, sid, category, state, *, result=None, error=None, request=None, actor=None):
    command = uid()
    with store.connection(write=True) as db:
        db.execute(
            'INSERT INTO receipts(scope,category,command_id,actor_id,payload_digest,state,'
            'result,error,request) VALUES(?,?,?,?,?,?,?,?,?)',
            (
                sid,
                category,
                command,
                actor or uid(),
                '0' * 64,
                state,
                None if result is None else json.dumps(result),
                None if error is None else json.dumps(error),
                None if request is None else json.dumps(request),
            ),
        )
    return command


REJECTION = DomainError('stale_revision', 409, current_revision='r0').data()


# ---- The one table -------------------------------------------------------------------------


def test_the_recovery_table_covers_every_category_and_state():
    for category in CATEGORIES:
        for state in STATES:
            value = receipt_recovery(category, dict(state=state))
            assert value['recovery'] in RECOVERY_VALUES
            assert set(value) == (
                {'recovery', 'retry_after_s'} if value['recovery'] == 'wait' else {'recovery'}
            )
            if state == 'committed':
                assert value == dict(recovery='adopt')
            elif state == 'rejected':
                assert value == dict(recovery='refused')
            elif category == 'run':
                assert value == dict(recovery='adopt' if state in RUN_STATES else 'uncertain')
            elif state == 'pending_remote':
                assert value == (
                    dict(recovery='resend_same_command') if category == 'model' else WAIT
                )
            else:
                assert value == dict(recovery='uncertain')
        missing = receipt_recovery(category, None)
        assert missing == (WAIT if category == 'run' else dict(recovery='resend_same_command'))


def test_a_run_receipt_never_says_resend_in_any_state_or_when_missing():
    for state in (*STATES, 'absent', 'unknown_state'):
        assert receipt_recovery('run', dict(state=state))['recovery'] != 'resend_same_command'
    assert receipt_recovery('run', None)['recovery'] == 'wait'


# ---- Through the API, per category -----------------------------------------------------------


def test_historical_study_and_current_archive_receipts_through_the_api(env):
    owner, store, sid = env['clients']['owner'], env['store'], env['sid']
    revision = owner.get(f'/api/1/studies/{sid}').json()['data']['revision']
    committed, stale = uid(), uid()
    with store.connection() as db:
        who = db.execute(
            "SELECT actor_id FROM memberships WHERE study_id=? AND role='owner'", (sid,)
        ).fetchone()[0]
    seed_legacy_context(store, who, sid, committed, revision, {'name': 'Renamed'})
    with pytest.raises(DomainError, match='stale_revision'):
        seed_legacy_context(store, who, sid, stale, 'stale', {'name': 'Lost'})
    archived = uid()
    assert (
        owner.post(f'/api/1/studies/{sid}/archive', json=dict(command_id=archived)).status_code
        == 200
    )
    for category, command, expected in (
        ('study', committed, 'adopt'),
        ('study', stale, 'refused'),
        ('study_archive', archived, 'adopt'),
    ):
        body, recovery = recovered(read(owner, sid, category, command), expected)
        assert recovery == dict(recovery=expected)
        assert body == todays_body(store, sid, category, command)


def test_evidence_receipts_through_the_api(env):
    owner, store, sid = env['clients']['owner'], env['store'], env['sid']
    command = uid()
    note = dict(command_id=command, scope=None, kind='note', content='Assumption', source_refs=[])
    assert owner.post(f'/api/1/studies/{sid}/evidence', json=note).status_code == 201
    body, recovery = recovered(read(owner, sid, 'evidence', command), 'adopt')
    assert recovery == dict(recovery='adopt') and body == todays_body(
        store, sid, 'evidence', command
    )


def test_configuration_receipts_through_the_api(env):
    owner, store, sid = env['clients']['owner'], env['store'], env['sid']
    for state, expected in (('committed', 'adopt'), ('rejected', 'refused')):
        command = seed(
            store,
            sid,
            'configuration',
            state,
            result={'configuration_revision_id': uid()} if state == 'committed' else None,
            error=REJECTION if state == 'rejected' else None,
        )
        body, recovery = recovered(read(owner, sid, 'configuration', command), expected)
        assert recovery == dict(recovery=expected)
        assert body == todays_body(store, sid, 'configuration', command)


def test_model_receipts_through_the_api(env, monkeypatch):
    owner, store, sid, model = env['clients']['owner'], env['store'], env['sid'], env['model']
    request = dict(target=None, operation='create', citation_versions=[])
    rejected = seed(store, sid, 'model', 'rejected', error=REJECTION, request=request)
    body, recovery = recovered(read(owner, sid, 'model', rejected), 'refused')
    assert recovery == dict(recovery='refused') and body == todays_body(
        store, sid, 'model', rejected
    )
    # A pending model command: the owner re-queries the modeling service with the same command
    # id first; while it cannot prove an outcome the command may be resent with that id.
    pending = seed(store, sid, 'model', 'pending_remote', request=request)
    before = len(model.calls)
    body, recovery = recovered(read(owner, sid, 'model', pending), 'resend_same_command')
    assert recovery == dict(recovery='resend_same_command')
    assert body == todays_body(store, sid, 'model', pending) and body['result'] is None
    assert model.calls[before:] == [('GET', f'/commands/{pending}?study_id={sid}&category=model')]
    # A recorded modeling response adopted by the owner earlier (its own checks are covered by
    # the coordinator's tests): the recorded response is the outcome.
    response = dict(data=dict(model_id=uid(), study_id=sid))
    committed = seed(
        store,
        sid,
        'model',
        'committed',
        result=dict(status=201, response=response),
        request=request,
    )
    monkeypatch.setattr(Coordinator, 'reconcile', lambda *args, **kwargs: None)
    body, recovery = recovered(read(owner, sid, 'model', committed), 'adopt')
    assert recovery == dict(recovery='adopt') and body['result'] == response
    assert body == todays_body(store, sid, 'model', committed)


@pytest.mark.parametrize('category', ['approach_draft', 'approach_version', 'approach_restore'])
def test_approach_receipts_through_the_api(env, category):
    owner, store, sid = env['clients']['owner'], env['store'], env['sid']
    command = seed(store, sid, category, 'rejected', error=REJECTION)
    body, recovery = recovered(read(owner, sid, category, command), 'refused')
    assert recovery == dict(recovery='refused') and body == todays_body(
        store, sid, category, command
    )
    missing = read(owner, sid, category, uid())
    assert missing.status_code == 404
    assert missing.json()['error']['recovery'] == 'resend_same_command'


@pytest.mark.parametrize(
    'category', ['computational_record_preview', 'computational_record_create']
)
def test_computational_record_receipts_through_the_api(env, category, monkeypatch):
    owner, store, sid = env['clients']['owner'], env['store'], env['sid']
    command = seed(store, sid, category, 'rejected', error=REJECTION)
    body, recovery = recovered(read(owner, sid, category, command), 'refused')
    assert recovery == dict(recovery='refused') and body == todays_body(
        store, sid, category, command
    )
    committed = seed(store, sid, category, 'committed', result=dict(request_id=uid()))
    # The retained closure is reauthorized by its owner (covered by its own tests); here the
    # read only has to reach it before answering.
    checked = []
    monkeypatch.setattr(
        type(records_for_store(store)),
        'status',
        lambda self, actor, study, request_id: checked.append(request_id),
    )
    body, recovery = recovered(read(owner, sid, category, committed), 'adopt')
    assert recovery == dict(recovery='adopt') and body == todays_body(
        store, sid, category, committed
    )
    assert checked == [body['result']['request_id']]


def test_run_receipts_through_the_api_in_every_state(submission):  # noqa: F811
    runs = runs_in_every_state(submission)
    service, store, actor, sid, _, native = submission
    c, _ = history_client(store, actor)
    seen = set()
    for label, run in runs.items():
        with store.connection() as db:
            row = store.command_receipt(db, sid, 'run', run['command_id'])
        body, recovery = recovered(read(c, sid, 'run', run['command_id']), label)
        assert body == todays_body(store, sid, 'run', run['command_id']), label
        assert recovery == receipt_recovery('run', row), label
        assert recovery['recovery'] != 'resend_same_command', label
        seen.add((row['state'], recovery['recovery']))
    assert ('uncertain', 'uncertain') in seen
    assert {state for state, recovery in seen if recovery == 'adopt'} >= {
        'accepted_run',
        'recorded',
    }
    missing = read(c, sid, 'run', uid())
    assert missing.status_code == 404
    error = missing.json()['error']
    assert (error['recovery'], error['retry_after_s']) == ('wait', RECEIPT_RETRY_AFTER_S)


# ---- Missing receipts and who may see the scope ------------------------------------------------


ERROR_FIELDS = (
    'code',
    'message',
    'request_id',
    'command_id',
    'resource_id',
    'current_revision',
    'fields',
    'outcome',
)


def test_a_missing_receipt_for_a_member_is_todays_404_with_the_recovery(env):
    owner, sid = env['clients']['owner'], env['sid']
    for category in ('study', 'evidence', 'configuration', 'model', 'computational_record_create'):
        response = read(owner, sid, category, uid())
        assert response.status_code == 404, category
        error = response.json()['error']
        assert tuple(error)[: len(ERROR_FIELDS)] == ERROR_FIELDS
        assert (error['code'], error['message'], error['outcome']) == (
            'resource_not_found',
            'resource not found',
            'unchanged',
        )
        assert error['recovery'] == 'resend_same_command' and 'retry_after_s' not in error
    assert env['model'].calls == []  # a missing model receipt is never looked up remotely


def test_a_reader_who_may_not_see_the_scope_gets_todays_404_without_recovery(env):
    store, sid = env['store'], env['sid']
    stranger = env['clients']['stranger']
    command = seed(store, sid, 'study', 'committed', result={})
    for target in (command, uid()):
        response = read(stranger, sid, 'study', target)
        assert response.status_code == 404
        assert (
            'recovery' not in response.json()['error']
            and 'retry_after_s' not in response.json()['error']
        )
    foreign = store.create_study(env['actors']['stranger'], uid(), 'Foreign')['study_id']
    response = read(env['clients']['owner'], foreign, 'run', uid())
    assert response.status_code == 404 and 'recovery' not in response.json()['error']


def test_the_pre_study_read_for_a_person(env):
    owner, store = env['clients']['owner'], env['store']
    command = uid()
    created = owner.post('/api/1/studies', json=dict(command_id=command, name='Second'))
    assert created.status_code == 201
    body, recovery = recovered(read(owner, None, 'study_create', command), 'adopt')
    assert recovery == dict(recovery='adopt')
    assert body == todays_body(store, 'actor:' + env['actors']['owner'], 'study_create', command)
    missing = read(owner, None, 'study_create', uid())
    assert (
        missing.status_code == 404 and missing.json()['error']['recovery'] == 'resend_same_command'
    )
    # Another person's study creation is in that person's own scope: missing here.
    assert read(env['clients']['stranger'], None, 'study_create', command).json()['error'][
        'recovery'
    ]


def test_the_pre_study_read_for_an_agent(env, monkeypatch):
    store, auth, owner = env['store'], env['auth'], env['actors']['owner']
    with store.connection(write=True) as db:
        agent = store.ensure_agent_actor(db, owner, 'claude_managed', 'Coding agent (local)')
        delegation = store.create_delegation(
            db, agent, env['sid'], 'writer', ('read', 'record'), time.time() + 3600
        )
    command = uid()
    new = store.create_study(
        agent, command, 'Started by the agent', delegation_id=delegation['delegation_id']
    )['study_id']
    # The agent session reaches the pre-study read only through the agent runtime; let it
    # through the route allowlist here so the store's own pre-study rules decide.
    monkeypatch.setattr(api_module, 'route_allowed', lambda *args, **kwargs: True)
    session = auth.mint_agent_session(delegation['delegation_id'])
    client = TestClient(env['app'], base_url=ORIGIN)
    client.cookies.set(COOKIE, session['token'])
    body, recovery = recovered(read(client, None, 'study_create', command), 'adopt')
    assert recovery == dict(recovery='adopt') and body['result']['study_id'] == new
    assert body == todays_body(store, 'actor:' + agent, 'study_create', command)
    missing = read(client, None, 'study_create', uid())
    assert (
        missing.status_code == 404 and missing.json()['error']['recovery'] == 'resend_same_command'
    )
    # Outside its pre-study rules: once the delegating user has left the created study the
    # agent gets today's 404 without a recovery.
    revision = store.study(owner, new)['revision']
    store.set_membership(owner, new, uid(), revision, env['actors']['stranger'], 'owner')
    revision = store.study(owner, new)['revision']
    store.set_membership(owner, new, uid(), revision, owner, None)
    gone = read(client, None, 'study_create', command)
    assert gone.status_code == 404 and 'recovery' not in gone.json()['error']
    with pytest.raises(DomainError) as refused:
        store.visible_receipt(agent, None, 'evidence', uid())
    assert refused.value.status == 404
