"""The agent runtime: one admission path, one append-only journal row per tool call.

Every tool call passes the kill switch (consulted on every call, absent means off), the session
(one active session per token; access loss is sticky), the live delegation, the API-call budget
of 600 per session, the repeated-error budget and run admission (20 runs per call, 60 per
session, 10 of the agent waiting or running), and leaves exactly one journal row: its outcome,
its reason from the closed list with HYPRN MVP text, its guard warnings and the records it
created or changed. Arguments are journaled as digests only. A duplicate call id never repeats
a write. Journal rows and sessions refuse every change outside their allowed transitions.

Test-only tools run over a recorded API double (an ASGI application that answers the routes the
tools call and records every request), and the packaged read tools run through the real
application with its agent route allowlist. Fresh synthetic stores only; no modeling service,
runtime or live store.
"""

import asyncio
import hashlib
import json
import sqlite3
import time
from types import SimpleNamespace
from urllib.parse import parse_qs
from uuid import uuid4

import pytest

from conftest import LOOPBACK_ORIGIN
from hyprn_mvp_app.agent_runtime import control, journal, limits, schema, tokens
from hyprn_mvp_app.agent_runtime.runtime import Runtime, SessionEnded, UnknownSession
from hyprn_mvp_app.agent_runtime.sessions import SessionRefused
from hyprn_mvp_app.agent_tools.projections import study_path
from hyprn_mvp_app.agent_tools.registry import LOCAL_STAGE, REGISTRY, Registry
from hyprn_mvp_app.agent_tools.spec import SURFACES, ToolError, ToolSpec
from hyprn_mvp_app.auth import Auth, token_hash
from hyprn_mvp_app.contracts import DomainError, canonical
from hyprn_mvp_app.store import Store

ORIGIN = LOOPBACK_ORIGIN
ENABLED = {control.AGENT_ENABLED: 'true'}
WRITER = ('read', 'draft', 'record', 'submit', 'outside_study')
GUIDANCE = ' Guidance: get_playbook("workflow").'
NOTE = {'type': 'string', 'maxLength': 200, 'description': 'Free text.'}
CAPABILITIES = '/api/1/capabilities'
UUID_TEXT = 36


def uid():
    return str(uuid4())


# ---- The recorded API double ------------------------------------------------------------


class RecordedApi:
    """An ASGI double of the public API for one study: it records every request and answers
    the routes the test tools call. ``override`` forces a status for one (method, path)."""

    def __init__(self, study_id):
        self.study_id = study_id
        self.requests = []
        self.runs = {}
        self.override = {}

    def count(self, method, path=None):
        return sum(1 for m, p, *_ in self.requests if m == method and (path is None or p == path))

    def finish(self, run_ids, state='recorded'):
        for run_id in run_ids:
            self.runs[run_id] = state

    async def __call__(self, scope, receive, send):
        assert scope['type'] == 'http'
        body = b''
        while True:
            message = await receive()
            body += message.get('body', b'')
            if not message.get('more_body'):
                break
        method, path = scope['method'], scope['path']
        query = parse_qs(scope['query_string'].decode())
        self.requests.append((method, path, query, body))
        status, payload = self.answer(method, path, query, body)
        payload['request_id'] = uid()
        raw = json.dumps(payload).encode()
        headers = [(b'content-type', b'application/json')]
        await send({'type': 'http.response.start', 'status': status, 'headers': headers})
        await send({'type': 'http.response.body', 'body': raw})

    def answer(self, method, path, query, body):
        study = '/api/1/studies/' + self.study_id
        if (method, path) in self.override:
            status = self.override[(method, path)]
            return status, {'error': {'code': 'forbidden' if status == 403 else 'internal_error'}}
        if (method, path) == ('GET', CAPABILITIES):
            return 200, {'data': {'limits': {}}}
        if (method, path) == ('GET', study + '/runs'):
            ids = list(self.runs)
            limit = int(query.get('limit', ['100'])[0])
            start = ids.index(query['cursor'][0]) + 1 if 'cursor' in query else 0
            page = ids[start : start + limit]
            more = start + limit < len(ids)
            data = [{'run_id': r, 'state': self.runs[r]} for r in page]
            return 200, {'data': data, 'next_cursor': page[-1] if more else None}
        if (method, path) == ('POST', study + '/runs'):
            run_id = uid()
            self.runs[run_id] = 'accepted_run'
            command = json.loads(body)['command_id']
            return 202, {'data': {'run_id': run_id, 'command_id': command, 'state': 'accepted_run'}}
        if (method, path) == ('POST', study + '/evidence'):
            data = {
                'evidence_id': uid(),
                'evidence_version_id': uid(),
                'title': 'Mission profile note',
                'version_number': 1,
            }
            return 201, {'data': data}
        return 404, {'error': {'code': 'resource_not_found'}}


# ---- Test-only tools ----------------------------------------------------------------------

HANDLED = {}


def handled(name):
    HANDLED[name] = HANDLED.get(name, 0) + 1


async def ping(arguments, ctx):
    handled('ping_capabilities')
    for _ in range(arguments.get('count', 1)):
        await ctx.api.request(ctx.session, 'GET', CAPABILITIES)
    return {'pings': arguments.get('count', 1)}


async def add_note(arguments, ctx):
    handled('add_test_note')
    reply = await ctx.api.request(
        ctx.session,
        'POST',
        study_path(ctx, 'evidence'),
        json_body={'command_id': ctx.command_ids[0], 'content': arguments['note']},
    )
    if reply.status != 201:
        raise ToolError('internal', 'The note was not saved.')
    data = reply.body['data']
    ctx.record(
        'evidence_version',
        data['evidence_id'],
        version_id=data['evidence_version_id'],
        name=data['title'],
        number=data['version_number'],
    )
    ctx.warn('long_sentence', 'note')
    if arguments.get('then') == 'fail':
        raise RuntimeError('failed after saving ' + arguments['note'])
    return {'evidence': {'id': data['evidence_id'], 'name': data['title']}}


async def submit_runs(arguments, ctx):
    handled('submit_test_runs')
    count = arguments['runs']
    await ctx.admit_runs(count)
    submitted = []
    for index in range(count):
        reply = await ctx.api.request(
            ctx.session,
            'POST',
            study_path(ctx, 'runs'),
            json_body={'command_id': ctx.command_ids[index], 'configuration_revision_id': uid()},
        )
        run_id = reply.body['data']['run_id']
        ctx.record('run', run_id, name='Baseline sizing')
        submitted.append(run_id)
    return {'runs': submitted}


async def submit_unadmitted(arguments, ctx):
    handled('submit_unadmitted_runs')
    await ctx.api.request(
        ctx.session,
        'POST',
        study_path(ctx, 'runs'),
        json_body={'command_id': ctx.command_ids[0], 'configuration_revision_id': uid()},
    )
    return {}


def spec(name, handler, effect, stage, properties, operations, outcome, owners, required=()):
    schema_ = {'type': 'object', 'additionalProperties': False, 'properties': properties}
    if required:
        schema_['required'] = list(required)
    return ToolSpec(
        name=name,
        title='Test tool ' + name,
        description='A test-only tool.' + GUIDANCE,
        input_schema=schema_,
        effect=effect,
        stage=stage,
        surfaces=SURFACES,
        owners=owners,
        outcome=outcome,
        activity_label='Test: ' + name,
        handler=handler,
        api_operations=operations,
    )


RUNS = ('POST', '/api/1/studies/{study_id}/runs')
TEST_REGISTRY = Registry(
    [
        spec(
            'ping_capabilities',
            ping,
            'read',
            'read_only',
            {'count': {'type': 'integer', 'minimum': 1, 'maximum': 700}, 'note': NOTE},
            (('GET', CAPABILITIES),),
            'none',
            ('agent_tools',),
        ),
        spec(
            'add_test_note',
            add_note,
            'record',
            'authoring',
            {'note': NOTE, 'then': {'type': 'string', 'enum': ['fail']}},
            (('POST', '/api/1/studies/{study_id}/evidence'),),
            'receipt:evidence',
            ('store',),
            required=('note',),
        ),
        spec(
            'submit_test_runs',
            submit_runs,
            'submit',
            'runs',
            {'runs': {'type': 'integer', 'minimum': 1, 'maximum': 30}},
            (RUNS,),
            'receipt:run',
            ('execution',),
            required=('runs',),
        ),
        spec(
            'submit_unadmitted_runs',
            submit_unadmitted,
            'submit',
            'runs',
            {},
            (RUNS,),
            'receipt:run',
            ('execution',),
        ),
    ]
)


# ---- Fixtures -------------------------------------------------------------------------------


class Clock:
    def __init__(self):
        self.now = time.time()

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


@pytest.fixture
def world(tmp_path):
    HANDLED.clear()
    store = Store(tmp_path / 'runtime.sqlite')
    schema.ensure(store)
    auth = Auth(store, ORIGIN)
    owner = uid()
    with store.connection(write=True) as db:
        db.execute(
            'INSERT INTO users(actor_id,username,password_hash) VALUES(?,?,?)',
            (owner, 'owner', 'unused'),
        )
    sid = store.create_study(owner, uid(), 'Wing sizing')['study_id']
    with store.connection(write=True) as db:
        agent = store.ensure_agent_actor(db, owner, 'local_mcp', 'Coding agent (local)')
        delegation = store.create_delegation(db, agent, sid, 'writer', WRITER, time.time() + 3600)
    minted = auth.mint_tool_token(delegation['delegation_id'], ttl_hours=1, client_label='local')
    grant = auth.verify_tool_token(minted['token'])
    return SimpleNamespace(
        store=store,
        auth=auth,
        owner=owner,
        sid=sid,
        agent=agent,
        delegation=delegation,
        token_id=minted['token_id'],
        grant=grant,
        api=RecordedApi(sid),
        environ=dict(ENABLED),
        clock=Clock(),
    )


def runtime(world, registry=TEST_REGISTRY, api=None, stage='runs'):
    return Runtime(
        world.store,
        world.auth,
        registry,
        world.api if api is None else api,
        ORIGIN,
        world.environ,
        stage=stage,
        clock=world.clock,
    )


def open_session(rt, world, name='claude-code', surface_id=None):
    return rt.open_session(
        world.grant, surface_id or uid(), {'name': name, 'version': '1.0'}, '2025-06-18'
    )


def rows(world, table='agent_actions'):
    with world.store.connection() as db:
        return [dict(r) for r in db.execute(f'SELECT * FROM {table} ORDER BY rowid')]


def session_row(world, handle):
    with world.store.connection() as db:
        row = db.execute(
            'SELECT * FROM agent_sessions WHERE session_id=?', (handle.session_id,)
        ).fetchone()
    return dict(row)


def run(scenario):
    return asyncio.run(scenario())


def call_ids():
    counter = iter(range(1, 10_000))
    return lambda: 'mcp-session-1:' + str(next(counter))


# ---- Kill switch -----------------------------------------------------------------------------


@pytest.mark.parametrize('value', [None, 'false', 'TRUE', '1', ''])
def test_while_agent_access_is_off_every_call_is_refused_and_no_api_request_is_made(world, value):
    rt = runtime(world)
    handle = open_session(rt, world)
    world.environ.pop(control.AGENT_ENABLED)
    if value is not None:
        world.environ[control.AGENT_ENABLED] = value
    next_id = call_ids()

    async def scenario():
        return [
            await rt.call_tool(handle, next_id(), name, arguments)
            for name, arguments in (
                ('ping_capabilities', {}),
                ('add_test_note', {'note': 'Cruise at Mach 0.78.'}),
                ('submit_test_runs', {'runs': 1}),
                ('no_such_tool', {}),
            )
        ]

    outcomes = run(scenario)
    assert all(not o.ok and o.state == 'refused' for o in outcomes)
    assert {o.content['error']['message'] for o in outcomes} == {
        'Assistant access is off for this installation.'
    }
    assert world.api.requests == [] and HANDLED == {}
    journaled = rows(world)
    assert [(r['state'], r['reason_code']) for r in journaled] == [
        ('refused', 'agent_disabled')
    ] * 4
    assert all(r['command_ids'] == '[]' and r['completed_at'] for r in journaled)
    with pytest.raises(SessionRefused) as refused:
        open_session(rt, world)
    assert refused.value.reason == 'agent_disabled'


# ---- Budgets --------------------------------------------------------------------------------


def test_a_session_makes_at_most_600_api_calls_and_the_601st_is_refused(world):
    rt = runtime(world)
    handle = open_session(rt, world)
    next_id = call_ids()

    async def scenario():
        done = [await rt.call_tool(handle, next_id(), 'ping_capabilities', {'count': 100})]
        done += [await rt.call_tool(handle, next_id(), 'ping_capabilities', {'count': 100})]
        for _ in range(4):
            done.append(await rt.call_tool(handle, next_id(), 'ping_capabilities', {'count': 100}))
        refused = await rt.call_tool(handle, next_id(), 'ping_capabilities', {'count': 1})
        return done, refused

    done, refused = run(scenario)
    assert all(o.ok for o in done)
    assert world.api.count('GET', CAPABILITIES) == limits.MAX_API_CALLS_PER_SESSION
    assert not refused.ok and refused.content['error']['category'] == 'budget_exhausted'
    assert session_row(world, handle)['api_calls'] == 600
    last = rows(world)[-1]
    assert (last['state'], last['reason_code']) == ('refused', 'budget_exhausted')
    assert last['reason_message'] == (
        'The assistant reached the limit of 600 API calls for one session.'
    )


def test_the_api_call_that_crosses_the_session_budget_inside_a_call_is_never_sent(world):
    rt = runtime(world)
    handle = open_session(rt, world)
    with world.store.connection(write=True) as db:
        db.execute(
            'UPDATE agent_sessions SET api_calls=595 WHERE session_id=?', (handle.session_id,)
        )

    outcome = run(lambda: rt.call_tool(handle, 'c1', 'ping_capabilities', {'count': 10}))
    assert not outcome.ok and outcome.content['error']['category'] == 'budget_exhausted'
    assert world.api.count('GET', CAPABILITIES) == 5
    row = rows(world)[-1]
    assert (row['state'], row['reason_code']) == ('refused', 'budget_exhausted')
    assert len(json.loads(row['api_operations'])) == 5


def test_the_sixth_identical_invalid_input_within_two_minutes_is_refused_as_repeated(world):
    rt = runtime(world)
    handle = open_session(rt, world)
    next_id = call_ids()
    bad = {'count': 0}

    async def scenario():
        first = [await rt.call_tool(handle, next_id(), 'ping_capabilities', bad) for _ in range(5)]
        sixth = await rt.call_tool(handle, next_id(), 'ping_capabilities', bad)
        other = await rt.call_tool(handle, next_id(), 'ping_capabilities', {'count': -1})
        world.clock.advance(limits.REPEATED_ERROR_WINDOW_SECONDS + 1)
        later = await rt.call_tool(handle, next_id(), 'ping_capabilities', bad)
        return first, sixth, other, later

    first, sixth, other, later = run(scenario)
    assert [o.content['error']['category'] for o in first] == ['invalid_input'] * 5
    assert sixth.content['error']['category'] == 'budget_exhausted'
    assert other.content['error']['category'] == 'invalid_input'
    assert later.content['error']['category'] == 'invalid_input'
    reasons = [r['reason_code'] for r in rows(world)]
    assert reasons == ['invalid_input'] * 5 + ['repeated_errors', 'invalid_input', 'invalid_input']
    assert (
        rows(world)[0]['reason_message'] == 'The request was not valid: count must be at least 1.'
    )
    assert world.api.requests == [] and HANDLED == {}


# ---- Sessions ---------------------------------------------------------------------------------


def test_one_active_session_per_token_and_a_new_one_ends_the_previous(world):
    rt = runtime(world)
    first = open_session(rt, world)
    second = open_session(rt, world)
    ended = session_row(world, first)
    assert ended['state'] == 'ended' and ended['ended_at']
    assert session_row(world, second)['state'] == 'active'

    async def scenario():
        with pytest.raises(SessionEnded):
            await rt.call_tool(first, 'c1', 'ping_capabilities', {})
        with pytest.raises(UnknownSession):
            await rt.call_tool(uid(), 'c1', 'ping_capabilities', {})
        return await rt.call_tool(second, 'c1', 'ping_capabilities', {})

    assert run(scenario).ok
    assert len(rows(world)) == 1
    with pytest.raises(sqlite3.IntegrityError):
        open_session(rt, world, surface_id=second.mcp_session_id)


@pytest.mark.parametrize(
    'client, display, stored',
    [
        ('claude-code', 'Claude Code (local)', 'claude-code'),
        ('codex-mcp-client', 'Codex (local)', 'codex-mcp-client'),
        ('Codex', 'Coding agent (local)', 'Codex'),
        ('Assistant for the Owner', 'Coding agent (local)', 'Assistant for the Owner'),
        ('bad\x00name', 'Coding agent (local)', None),
        ('x' * 65, 'Coding agent (local)', None),
        (None, 'Coding agent (local)', None),
    ],
)
def test_the_session_display_name_comes_from_a_closed_mapping_of_client_names(
    world, client, display, stored
):
    rt = runtime(world)
    handle = open_session(rt, world, name=client)
    row = session_row(world, handle)
    assert handle.agent_display_name == row['agent_display_name'] == display
    assert row['client_name'] == stored and row['protocol_version'] == '2025-06-18'
    assert row['registry_version'] and len(row['playbook_sha256']) == 64
    assert row['tool_definitions_sha256'] == TEST_REGISTRY.definitions_sha256()
    assert row['delegation_id'] == world.delegation['delegation_id']
    assert row['token_id'] == world.token_id and row['surface'] == 'local_mcp'


def test_the_delegated_api_session_is_reminted_before_expiry_and_kept_only_in_memory(world):
    rt = runtime(world)
    handle = open_session(rt, world)
    minted = []

    async def scenario():
        await rt.call_tool(handle, 'c1', 'ping_capabilities', {})
        minted.append(dict(rt.sessions._api[handle.session_id]))
        world.clock.advance(15 * 60 - limits.API_SESSION_MARGIN_SECONDS + 5)
        await rt.call_tool(handle, 'c2', 'ping_capabilities', {})
        minted.append(dict(rt.sessions._api[handle.session_id]))

    run(scenario)
    assert minted[0]['token'] != minted[1]['token']
    stored = json.dumps(rows(world) + rows(world, 'agent_sessions'))
    held = json.dumps(rows(world, 'agent_api_sessions'))
    for session in minted:
        for secret in (session['token'], session['csrf_token']):
            assert secret not in stored and secret not in held
            assert secret not in repr(rt) + repr(rt.sessions) + repr(handle)
        assert token_hash(session['token']) in held


# ---- Access loss ------------------------------------------------------------------------------


def test_access_loss_from_a_revoked_token_is_sticky_and_makes_no_further_request(world):
    rt = runtime(world)
    handle = open_session(rt, world)

    async def scenario():
        ok = await rt.call_tool(handle, 'c1', 'add_test_note', {'note': 'Cruise.'})
        tokens.revoke(world.store, world.sid, world.token_id)
        before = len(world.api.requests)
        # The stored outcome of an earlier write is not delivered after access loss.
        replay = await rt.call_tool(handle, 'c1', 'add_test_note', {'note': 'Cruise.'})
        lost = await rt.call_tool(handle, 'c2', 'ping_capabilities', {})
        again = await rt.call_tool(handle, 'c3', 'ping_capabilities', {})
        return ok, before, lost, again, replay

    ok, before, lost, again, replay = run(scenario)
    assert ok.ok
    assert len(world.api.requests) == before
    for outcome in (lost, again, replay):
        assert not outcome.ok and outcome.content['error']['category'] == 'access_lost'
    assert session_row(world, handle)['state'] == 'access_lost'
    journaled = rows(world)
    assert [(r['call_id'], r['state'], r['reason_code']) for r in journaled] == [
        ('c1', 'completed', None),
        ('c2', 'refused', 'access_lost'),
        ('c3', 'refused', 'access_lost'),
    ]
    assert journaled[1]['reason_message'] == "The assistant's access to this study had ended."
    with pytest.raises(SessionRefused):
        open_session(rt, world)


def test_a_403_from_the_api_ends_the_session_as_access_lost(world):
    rt = runtime(world)
    handle = open_session(rt, world)
    world.api.override[('GET', CAPABILITIES)] = 403

    async def scenario():
        lost = await rt.call_tool(handle, 'c1', 'ping_capabilities', {})
        world.api.override.clear()
        later = await rt.call_tool(handle, 'c2', 'ping_capabilities', {})
        return lost, later

    lost, later = run(scenario)
    assert lost.content['error']['category'] == later.content['error']['category'] == 'access_lost'
    assert world.api.count('GET', CAPABILITIES) == 1
    assert session_row(world, handle)['state'] == 'access_lost'
    assert [r['reason_code'] for r in rows(world)] == ['access_lost', 'access_lost']


# ---- Duplicates and the journal ----------------------------------------------------------


def test_a_duplicate_call_id_never_repeats_a_write_and_answers_a_read_again(world):
    rt = runtime(world)
    handle = open_session(rt, world)
    note = {'note': 'Cruise at Mach 0.78.'}

    async def scenario():
        write = [await rt.call_tool(handle, 'w1', 'add_test_note', note) for _ in range(3)]
        read = [await rt.call_tool(handle, 'r1', 'ping_capabilities', {}) for _ in range(2)]
        other = await rt.call_tool(handle, 'w1', 'add_test_note', {'note': 'Other.'})
        return write, read, other

    write, read, other = run(scenario)
    assert all(o.ok for o in write + read)
    assert write[0].content == write[1].content == write[2].content
    assert HANDLED['add_test_note'] == 1 and world.api.count('POST') == 1
    assert HANDLED['ping_capabilities'] == 2 and world.api.count('GET', CAPABILITIES) == 2
    assert not other.ok and other.content['error']['category'] == 'invalid_input'
    assert [(r['call_id'], r['state']) for r in rows(world)] == [
        ('w1', 'completed'),
        ('r1', 'completed'),
    ]


def test_a_refused_write_is_answered_from_the_journal_on_a_duplicate(world):
    rt = runtime(world)
    handle = open_session(rt, world)

    async def scenario():
        return [await rt.call_tool(handle, 'w1', 'add_test_note', {}) for _ in range(2)]

    first, second = run(scenario)
    assert first.content['error']['category'] == second.content['error']['category']
    assert second.content['error']['message'] == (
        'The request was not valid: note required field is missing.'
    )
    assert len(rows(world)) == 1 and HANDLED == {}


def test_a_completed_write_lists_its_records_command_ids_and_operations(world):
    rt = runtime(world)
    handle = open_session(rt, world)

    async def scenario():
        await rt.call_tool(handle, 'w1', 'add_test_note', {'note': 'Cruise at Mach 0.78.'})
        await rt.call_tool(handle, 'r1', 'ping_capabilities', {})

    run(scenario)
    write, read = rows(world)
    assert (write['state'], write['outcome_class'], write['effect']) == (
        'completed',
        'ok',
        'record',
    )
    found = json.loads(write['records'])
    assert len(found) == 1
    assert {k: found[0][k] for k in ('kind', 'name', 'number')} == {
        'kind': 'evidence_version',
        'name': 'Mission profile note',
        'number': 1,
    }
    assert len(found[0]['record_id']) == len(found[0]['version_id']) == UUID_TEXT
    assert json.loads(write['warnings']) == [{'code': 'long_sentence', 'field': 'note'}]
    commands = json.loads(write['command_ids'])
    assert len(commands) == limits.COMMAND_IDS['record'] and len(set(commands)) == len(commands)
    posted = [json.loads(body) for m, _, _, body in world.api.requests if m == 'POST']
    assert posted[0]['command_id'] == commands[0]
    (operation,) = json.loads(write['api_operations'])
    assert operation['method'] == 'POST' and operation['status'] == 201
    assert operation['template'] == '/api/1/studies/{study_id}/evidence'
    assert len(operation['request_id']) == UUID_TEXT
    assert json.loads(write['result_json'])['evidence']['name'] == 'Mission profile note'
    assert read['result_json'] is None and read['command_ids'] == '[]'
    assert json.loads(read['records']) == []


def test_a_write_that_may_have_changed_something_is_never_journaled_as_nothing_changed(world):
    rt = runtime(world)
    handle = open_session(rt, world)
    marker = 'seeded-' + uuid4().hex

    async def scenario():
        saved = await rt.call_tool(handle, 'w1', 'add_test_note', {'note': marker, 'then': 'fail'})
        world.api.override[('POST', '/api/1/studies/' + world.sid + '/evidence')] = 500
        refused = await rt.call_tool(handle, 'w2', 'add_test_note', {'note': 'Cruise.'})
        return saved, refused

    saved, refused = run(scenario)
    assert saved.content['error']['category'] == 'internal'
    assert marker not in json.dumps(saved.content)
    assert refused.content['error']['category'] == 'internal'
    first, second = rows(world)
    assert (first['state'], first['reason_code']) == ('uncertain', 'outcome_unknown')
    assert [r['kind'] for r in json.loads(first['records'])] == ['evidence_version']
    assert first['result_json'] is None
    assert (second['state'], second['reason_code']) == ('failed', 'internal')
    assert second['reason_message'] == 'An internal error stopped the call.'
    assert json.loads(second['records']) == []
    assert marker not in json.dumps(rows(world))
    assert session_row(world, handle)['state'] == 'active'


def test_a_refused_call_leaves_one_refused_row_with_a_reason_from_the_closed_list(world):
    rt = runtime(world)
    handle = open_session(rt, world)
    outcome = run(lambda: rt.call_tool(handle, 'c1', 'delete_everything', {}))
    assert not outcome.ok
    (row,) = rows(world)
    assert row['state'] == 'refused' and row['tool'] == '(unknown tool)' and row['effect'] is None
    assert row['reason_code'] in journal.REASONS
    assert row['reason_message'] == (
        'The request was not valid: tool is not available in this session.'
    )
    assert world.api.requests == []


def test_journal_rows_and_sessions_refuse_changes_outside_the_allowed_transitions(world):
    rt = runtime(world)
    handle = open_session(rt, world)
    run(lambda: rt.call_tool(handle, 'c1', 'ping_capabilities', {}))
    run(lambda: rt.call_tool(handle, 'c2', 'ping_capabilities', {'count': 0}))
    intent = dict(
        session_id=handle.session_id,
        delegation_id=world.delegation['delegation_id'],
        study_id=world.sid,
        call_id='c3',
        tool='add_test_note',
        effect='record',
        args_sha256='0' * 64,
        command_ids=(uid(),),
    )
    pending = journal.intend(world.store, intent, time.time())
    completed, refused = (r['action_id'] for r in rows(world)[:2])
    statements = [
        ("UPDATE agent_actions SET tool='other' WHERE action_id=?", completed),
        ("UPDATE agent_actions SET state='failed' WHERE action_id=?", completed),
        (
            'UPDATE agent_actions SET reason_code=NULL,reason_message=NULL WHERE action_id=?',
            refused,
        ),
        ("UPDATE agent_actions SET args_sha256='" + '1' * 64 + "' WHERE action_id=?", pending),
        ("UPDATE agent_actions SET command_ids='[]' WHERE action_id=?", pending),
        ("UPDATE agent_actions SET state='intended' WHERE action_id=?", pending),
        ('DELETE FROM agent_actions WHERE action_id=?', completed),
        ('DELETE FROM agent_actions WHERE action_id=?', pending),
        ("UPDATE agent_sessions SET delegation_id='other' WHERE session_id=?", handle.session_id),
        ('UPDATE agent_sessions SET api_calls=0 WHERE session_id=?', handle.session_id),
        ('DELETE FROM agent_sessions WHERE session_id=?', handle.session_id),
    ]
    for statement, key in statements:
        with pytest.raises(sqlite3.DatabaseError):
            with world.store.connection(write=True) as db:
                db.execute(statement, (key,))
    with pytest.raises(sqlite3.DatabaseError):
        with world.store.connection(write=True) as db:
            db.execute(
                'INSERT INTO agent_actions(action_id,session_id,delegation_id,study_id,call_id,'
                'tool,effect,args_sha256,command_ids,state,created_at,outcome_class) '
                "VALUES(?,?,?,?,'c4','ping_capabilities','read',?,'[]','completed','t','ok')",
                (uid(), handle.session_id, world.delegation['delegation_id'], world.sid, '0' * 64),
            )
    assert journal.fail(world.store, pending, 'internal', time.time(), outcome_class='internal')
    assert not journal.complete(world.store, pending, time.time())
    with pytest.raises(sqlite3.DatabaseError):
        with world.store.connection(write=True) as db:
            db.execute("UPDATE agent_actions SET state='completed' WHERE action_id=?", (pending,))
    rt.sessions.end(handle.session_id)
    with pytest.raises(sqlite3.DatabaseError):
        with world.store.connection(write=True) as db:
            db.execute(
                "UPDATE agent_sessions SET state='active',ended_at=NULL WHERE session_id=?",
                (handle.session_id,),
            )
    assert [r['state'] for r in rows(world)] == ['completed', 'refused', 'failed']


def test_argument_strings_appear_in_no_journal_column_only_their_digests(world):
    rt = runtime(world)
    handle = open_session(rt, world)
    marker = 'seeded-' + uuid4().hex
    calls = [
        ('ping_capabilities', {'count': 1, 'note': marker}),
        ('ping_capabilities', {'count': 0, 'note': marker}),
        ('ping_capabilities', {'note': marker, marker: marker}),
        ('add_test_note', {'note': marker}),
        ('add_test_note', {'note': marker * 10}),
        ('submit_test_runs', {'runs': 21, marker: 1}),
    ]

    async def scenario():
        return [
            await rt.call_tool(handle, 'c' + str(n), name, arguments)
            for n, (name, arguments) in enumerate(calls)
        ]

    outcomes = run(scenario)
    assert [o.ok for o in outcomes] == [True, False, False, True, False, False]
    journaled = rows(world) + rows(world, 'agent_sessions')
    assert marker not in json.dumps(journaled)
    for row, (_, arguments) in zip(rows(world), calls):
        assert row['args_sha256'] == hashlib.sha256(canonical(arguments)).hexdigest()
    assert any(marker.encode() in body for *_, body in world.api.requests)


# ---- Run admission ---------------------------------------------------------------------------


def test_more_than_20_runs_in_one_call_are_refused_before_any_submission(world):
    rt = runtime(world)
    handle = open_session(rt, world)
    outcome = run(lambda: rt.call_tool(handle, 'c1', 'submit_test_runs', {'runs': 21}))
    assert outcome.content['error']['category'] == 'invalid_input'
    assert outcome.content['error']['message'] == 'One call can submit at most 20 runs.'
    assert world.api.requests == []
    (row,) = rows(world)
    assert (row['state'], row['reason_code']) == ('refused', 'run_limit_call')


def test_the_11th_waiting_run_of_the_agent_is_refused_before_any_submission(world):
    rt = runtime(world)
    first = open_session(rt, world)

    async def scenario():
        ten = await rt.call_tool(first, 'c1', 'submit_test_runs', {'runs': 10})
        assert world.api.count('GET') == 0
        eleventh = await rt.call_tool(first, 'c2', 'submit_test_runs', {'runs': 1})
        # Another session of the same agent counts the same waiting runs.
        second = open_session(rt, world)
        again = await rt.call_tool(second, 'c1', 'submit_test_runs', {'runs': 1})
        world.api.finish(ten.content['runs'][:5])
        admitted = await rt.call_tool(second, 'c2', 'submit_test_runs', {'runs': 5})
        refused = await rt.call_tool(second, 'c3', 'submit_test_runs', {'runs': 1})
        return ten, eleventh, again, admitted, refused

    ten, eleventh, again, admitted, refused = run(scenario)
    assert ten.ok and admitted.ok
    for outcome in (eleventh, again, refused):
        error = outcome.content['error']
        assert error['category'] == 'busy' and error['retryable'] is True
        assert error['message'] == 'At most 10 runs from this assistant can wait or run at once.'
    assert world.api.count('POST') == 15
    assert world.api.count('GET', '/api/1/studies/' + world.sid + '/runs') == 4
    reasons = [(r['state'], r['reason_code']) for r in rows(world)]
    assert reasons == [
        ('completed', None),
        ('refused', 'run_limit_queued'),
        ('refused', 'run_limit_queued'),
        ('completed', None),
        ('refused', 'run_limit_queued'),
    ]


def test_the_61st_run_of_a_session_is_refused_before_any_submission(world):
    rt = runtime(world)
    handle = open_session(rt, world)

    async def scenario():
        outcomes = []
        # Ten at a time: a call that would take the agent above 10 waiting runs is refused.
        for n in range(6):
            outcome = await rt.call_tool(handle, 'c' + str(n), 'submit_test_runs', {'runs': 10})
            world.api.finish(outcome.content['runs'])
            outcomes.append(outcome)
        posts, gets = world.api.count('POST'), world.api.count('GET')
        refused = await rt.call_tool(handle, 'c9', 'submit_test_runs', {'runs': 1})
        assert (world.api.count('POST'), world.api.count('GET')) == (posts, gets)
        return outcomes, refused

    outcomes, refused = run(scenario)
    assert all(o.ok for o in outcomes)
    assert refused.content['error']['category'] == 'budget_exhausted'
    assert refused.content['error']['message'] == (
        'The assistant reached the limit of 60 runs for one session.'
    )
    assert world.api.count('POST') == limits.MAX_RUNS_PER_SESSION
    assert session_row(world, handle)['runs_submitted'] == 60
    assert rows(world)[-1]['reason_code'] == 'run_limit_session'


def test_a_run_submission_that_run_admission_did_not_admit_is_never_sent(world):
    rt = runtime(world)
    handle = open_session(rt, world)
    outcome = run(lambda: rt.call_tool(handle, 'c1', 'submit_unadmitted_runs', {}))
    assert outcome.content['error']['category'] == 'internal'
    assert world.api.requests == []
    (row,) = rows(world)
    assert (row['state'], row['reason_code']) == ('failed', 'internal')


@pytest.mark.parametrize(
    'requested, session_runs, queued, reason',
    [
        (10, 0, 0, None),
        (11, 0, 0, 'run_limit_queued'),
        (20, 0, 0, 'run_limit_queued'),
        (21, 0, 0, 'run_limit_call'),
        (1, 59, 0, None),
        (1, 60, 0, 'run_limit_session'),
        (1, 0, 9, None),
        (1, 0, 10, 'run_limit_queued'),
        (21, 60, 10, 'run_limit_call'),
        (2, 59, 10, 'run_limit_session'),
    ],
)
def test_run_admission_checks_the_call_then_the_session_then_the_queue(
    requested, session_runs, queued, reason
):
    assert limits.run_refusal(requested, session_runs, queued) == reason


# ---- Through the real application ----------------------------------------------------------


class UnavailableModeling:
    def call(self, *_, **__):
        raise DomainError('backend_unavailable', 503, outcome='unknown')


class Counting:
    def __init__(self, app):
        self.app, self.paths = app, []

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'http':
            self.paths.append((scope['method'], scope['path']))
        await self.app(scope, receive, send)


def test_packaged_read_tools_run_through_the_real_application_and_lose_access_on_revocation(
    world,
):
    from hyprn_mvp_app.api import create_app

    app = Counting(create_app(world.store, world.auth, UnavailableModeling(), environ=ENABLED))
    token_id, token = tokens.mint_local(
        world.store, world.auth, 'owner', world.sid, environ=ENABLED
    )
    world.grant = world.auth.verify_tool_token(token)
    rt = runtime(world, registry=REGISTRY, api=app, stage=LOCAL_STAGE)
    handle = open_session(rt, world, name='codex-mcp-client')

    async def scenario():
        overview = await rt.call_tool(handle, 'c1', 'get_study_overview', {})
        listed = await rt.call_tool(handle, 'c2', 'list_runs', {})
        write = await rt.call_tool(handle, 'c3', 'add_test_note', {'note': 'x'})
        tokens.revoke(world.store, world.sid, token_id)
        count = len(app.paths)
        lost = await rt.call_tool(handle, 'c4', 'get_study_overview', {})
        assert len(app.paths) == count
        return overview, listed, write, lost

    overview, listed, write, lost = run(scenario)
    assert overview.ok and listed.ok
    assert overview.content['study']['name']['untrusted_content']['text'] == 'Wing sizing'
    assert write.content['error']['category'] == 'invalid_input'
    assert lost.content['error']['category'] == 'access_lost'
    journaled = rows(world)
    assert [(r['tool'], r['state'], r['reason_code']) for r in journaled] == [
        ('get_study_overview', 'completed', None),
        ('list_runs', 'completed', None),
        ('(unknown tool)', 'refused', 'invalid_input'),
        ('get_study_overview', 'refused', 'access_lost'),
    ]
    templates = {op['template'] for op in json.loads(journaled[0]['api_operations'])}
    declared = {t for _, t in REGISTRY.tool('get_study_overview').api_operations}
    assert templates and templates <= declared
    assert all(op['status'] == 200 for op in json.loads(journaled[0]['api_operations']))
    assert session_row(world, handle)['api_calls'] == len(app.paths)
