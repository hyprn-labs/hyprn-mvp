"""Synthetic provider delivery through the delegated runtime and public API only."""

import asyncio
from dataclasses import replace
import json
import time
from types import SimpleNamespace
from uuid import uuid4

import pytest

from conftest import LOOPBACK_ORIGIN
from hyprn_mvp_app.agent_runtime import control, schema
from hyprn_mvp_app.agent_runtime.runtime import Runtime, SessionEnded, ToolOutcome, UnknownSession
from hyprn_mvp_app.agent_runtime.sessions import SessionHandle
from hyprn_mvp_app.agent_tools.registry import REGISTRY, definition
from hyprn_mvp_app.agent_tools.spec import ToolError
from hyprn_mvp_app.assistant.bridge import InvocationBinding, ReadOnlyBridge
from hyprn_mvp_app.auth import Auth
from hyprn_mvp_app.contracts import DomainError
from hyprn_mvp_app.store import Store


class Transport:
    def __init__(self):
        self.submissions = []
        self.inspections = []
        self.interruptions = []
        self.submit_reply = 'accepted'
        self.inspect_reply = 'accepted'
        self.interrupt_reply = 'accepted'

    async def submit_tool_result(self, session, thread, call, outcome):
        self.submissions.append((session, thread, call, outcome))
        return self.submit_reply

    async def inspect_tool_result(self, session, thread, call):
        self.inspections.append((session, thread, call))
        return self.inspect_reply

    async def interrupt(self, session, thread):
        self.interruptions.append((session, thread))
        return self.interrupt_reply


def event(**changes):
    value = dict(
        kind='tool_request',
        complete=True,
        invocation_id='invocation-1',
        provider_session_id='provider-1',
        provider_thread_id='thread-1',
        event_id='event-1',
        call_id='call-1',
        name='get_study_overview',
        arguments='{}',
    )
    value.update(changes)
    return json.dumps(value).encode()


class UnavailableModeling:
    def call(self, *args, **kwargs):
        raise DomainError('backend_unavailable', 503, outcome='unknown')


class Counting:
    def __init__(self, app):
        self.app = app
        self.paths = []

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'http':
            self.paths.append((scope['method'], scope['path']))
        await self.app(scope, receive, send)


@pytest.fixture
def real_runtime(tmp_path):
    from hyprn_mvp_app.api import create_app

    store = Store(tmp_path / 'assistant.sqlite')
    schema.ensure(store)
    auth = Auth(store, LOOPBACK_ORIGIN)
    owner = str(uuid4())
    with store.connection(write=True) as db:
        db.execute(
            'INSERT INTO users(actor_id,username,password_hash) VALUES(?,?,?)',
            (owner, 'owner', 'unused'),
        )
    study = store.create_study(owner, str(uuid4()), 'Wing sizing')['study_id']
    with store.connection(write=True) as db:
        actor = store.ensure_agent_actor(db, owner, 'claude_managed', 'Coding agent (local)')
        delegation = store.create_delegation(
            db, actor, study, 'reader', ('read',), time.time() + 3600
        )
    environ = {control.AGENT_ENABLED: 'true'}
    app = Counting(create_app(store, auth, UnavailableModeling(), environ=environ))
    runtime = Runtime(store, auth, REGISTRY, app, LOOPBACK_ORIGIN, environ, stage='read_only')
    handle = runtime.open_session(
        delegation, {'name': 'hyprn-claude-managed'}, surface='claude_managed'
    )

    def access(bound):
        row = runtime.sessions.get(bound.session_id)
        if not control.agent_enabled(environ) or row is None or row['state'] != 'active':
            return False
        runtime.sessions.live(bound.session_id, row['delegation_id'])
        return True

    return runtime, handle, access, app, delegation['delegation_id']


def test_delegated_read_reaches_public_api_once_and_preserves_the_exact_outcome(real_runtime):
    runtime, handle, access, app, delegation_id = real_runtime
    provider = Transport()
    outcomes = []

    async def call(*args):
        outcome = await runtime.call_tool(*args)
        outcomes.append(outcome)
        return outcome

    bridge = ReadOnlyBridge(
        InvocationBinding(handle, 'invocation-1', 'provider-1', 'thread-1'),
        registry=REGISTRY,
        definitions=REGISTRY.definitions('claude_managed', 'read_only', {'read'}),
        call_tool=call,
        current_access=access,
        transport=provider,
    )

    async def scenario():
        try:
            assert bridge.activate() == 'active'
            assert await bridge.handle_tool_request(event()) == 'accepted'
            count = len(app.paths)
            assert count > 0
            assert await bridge.handle_tool_request(event(event_id='event-2')) == 'accepted'
            assert len(app.paths) == count
            assert len(outcomes) == len(provider.submissions) == 1
            outcome = outcomes[0]
            delivered = json.loads(provider.submissions[0][3])
            assert delivered == dict(
                ok=outcome.ok,
                content=outcome.content,
                action_id=outcome.action_id,
                state=outcome.state,
            )
            assert (
                delivered['content']['study']['name']['untrusted_content']['text'] == 'Wing sizing'
            )
            assert all(method == 'GET' for method, _ in app.paths)
            with runtime.store.connection() as db:
                assert db.execute('SELECT COUNT(*) FROM agent_actions').fetchone()[0] == 1
            runtime.auth.revoke_delegation(delegation_id)
            assert await bridge.handle_tool_request(event(event_id='event-3')) == 'access_lost'
            assert len(app.paths) == count
            assert len(provider.submissions) == 1
        finally:
            await runtime.aclose()

    asyncio.run(scenario())


def bridge_for(
    call,
    provider,
    access=lambda _: True,
    *,
    invocation='invocation-1',
    definitions=None,
    registry=REGISTRY,
):
    handle = SessionHandle('session-1', 'claude_managed', 'study-1', 'Assistant')
    return ReadOnlyBridge(
        InvocationBinding(handle, invocation, 'provider-1', 'thread-1'),
        registry=registry,
        definitions=definitions
        if definitions is not None
        else REGISTRY.definitions('claude_managed', 'read_only', {'read'}),
        call_tool=call,
        current_access=access,
        transport=provider,
    )


@pytest.fixture
def harness():
    provider = Transport()
    calls = []
    allowed = [True]
    outcome = ToolOutcome(
        True, {'value': {'untrusted_content': {'text': 'source text'}}}, 'action-1', 'completed'
    )

    async def call(*args):
        calls.append(args)
        return outcome

    bridge = bridge_for(call, provider, lambda _: allowed[0])
    assert bridge.activate() == 'active'
    return SimpleNamespace(
        bridge=bridge, calls=calls, provider=provider, allowed=allowed, outcome=outcome, call=call
    )


@pytest.mark.parametrize(
    'changes',
    [
        {'provider_session_id': 'foreign'},
        {'provider_thread_id': 'foreign'},
        {'invocation_id': 'foreign'},
        {'event_id': ''},
        {'call_id': ' '},
        {'event_id': 'x' * 129},
        {'call_id': 'x\n'},
        {'provider_thread_id': 'é'},
        {'provider_session_id': 12},
        {'kind': 'partial'},
        {'complete': False},
        {'complete': 1},
        {'name': 'BadName'},
        {'name': 'x' * 65},
        {'principal': 'owner'},
        {'study_id': 'foreign'},
        {'arguments': {}},
        {'arguments': '{'},
        {'arguments': '[]'},
        {'arguments': 'null'},
        {'arguments': '{"limit":1,"limit":2}'},
        {'arguments': '{"limit":NaN}'},
        {'arguments': '{"limit":Infinity}'},
        {'arguments': '{"limit":1e400}'},
        {'arguments': '{"limit":9007199254740992}'},
        {'arguments': '{"limit":9007199254740992.0}'},
        {'arguments': '{"x":' + '[' * 33 + '0' + ']' * 33 + '}'},
        {'arguments': '{"x":"' + 'a' * (256 * 1024) + '"}'},
        {'name': 'list_runs', 'arguments': '{"limit":true}'},
        {'name': 'list_runs', 'arguments': '{"limit":0}'},
        {'name': 'get_run_status', 'arguments': '{}'},
        {'name': 'get_playbook', 'arguments': '{"section":"unknown"}'},
        {'arguments': '{"principal":"owner"}'},
    ],
)
def test_invalid_or_foreign_requests_never_dispatch_or_deliver(harness, changes):
    status = asyncio.run(harness.bridge.handle_tool_request(event(**changes)))
    assert status in ('invalid_input', 'foreign_binding')
    assert harness.calls == harness.provider.submissions == []


@pytest.mark.parametrize(
    'raw',
    [
        b'{}',
        b'[]',
        b'\xff',
        b'{',
        b'{"kind":"tool_request","kind":"other"}',
        b'[' * 33 + b'0' + b']' * 33,
        b' ' * (256 * 1024 + 1),
    ],
)
def test_envelope_bounds_and_strict_json_are_checked_before_dispatch(harness, raw):
    assert asyncio.run(harness.bridge.handle_tool_request(raw)) == 'invalid_input'
    assert harness.calls == harness.provider.submissions == []


@pytest.mark.parametrize(
    'name',
    [
        'not_a_tool',
        'update_study_context',
        'submit_runs',
        'check_model',
        'preview_model',
        'record_progress',
        'delete_study',
        'get_run_results',
    ],
)
def test_only_fixed_get_tools_are_admitted(harness, name):
    assert asyncio.run(harness.bridge.handle_tool_request(event(name=name))) == 'tool_refused'
    assert harness.calls == harness.provider.submissions == []


def test_valid_nonempty_arguments_and_json_booleans_keep_their_types(harness):
    async def scenario():
        assert (
            await harness.bridge.handle_tool_request(
                event(name='list_runs', arguments='{"limit":2}')
            )
            == 'accepted'
        )
        assert harness.calls[0][3] == {'limit': 2}
        # Boolean input is valid JSON but must obey the chosen tool's actual schema.
        assert (
            await harness.bridge.handle_tool_request(
                event(event_id='e2', call_id='c2', name='list_runs', arguments='{"limit":false}')
            )
            == 'invalid_input'
        )

    asyncio.run(scenario())


def test_schema_boolean_is_not_coerced_to_an_integer(harness):
    tool = replace(
        REGISTRY.tool('list_runs'),
        input_schema={
            'type': 'object',
            'properties': {'include': {'type': 'boolean'}},
            'additionalProperties': False,
        },
    )
    registry = SimpleNamespace(tool=lambda _: tool)
    bridge = bridge_for(
        harness.call, harness.provider, definitions=[definition(tool)], registry=registry
    )
    assert bridge.activate() == 'active'
    assert (
        asyncio.run(
            bridge.handle_tool_request(event(name='list_runs', arguments='{"include":true}'))
        )
        == 'accepted'
    )
    assert harness.calls[0][3]['include'] is True


@pytest.mark.parametrize(
    'change',
    [
        {'effect': 'draft'},
        {'runtime_operation': 'record_progress'},
        {'api_operations': (('POST', '/api/1/preview'),)},
        {'api_operations': ()},
    ],
)
def test_substituted_tool_policy_fails_closed(harness, change):
    tool = replace(REGISTRY.tool('get_study_overview'), **change)
    bridge = bridge_for(
        harness.call,
        harness.provider,
        registry=SimpleNamespace(tool=lambda _: tool),
        definitions=[definition(tool)],
    )
    assert bridge.activate() == 'policy_refused'
    assert asyncio.run(bridge.handle_tool_request(event())) == 'closed'
    assert harness.calls == []


def test_session_definitions_and_policy_cannot_widen_after_activation(harness):
    definitions = [definition(REGISTRY.tool('get_playbook'))]
    bridge = bridge_for(harness.call, harness.provider, definitions=definitions)
    pinned = bridge.definitions_sha256
    assert bridge.activate() == 'active'
    definitions.append(definition(REGISTRY.tool('get_study_overview')))
    assert bridge.definitions_sha256 == pinned
    assert asyncio.run(bridge.handle_tool_request(event())) == 'tool_refused'
    selected = [REGISTRY.tool('get_study_overview')]
    bridge = bridge_for(
        harness.call,
        harness.provider,
        registry=SimpleNamespace(tool=lambda _: selected[0]),
        definitions=[definition(selected[0])],
    )
    assert bridge.activate() == 'active'
    selected[0] = replace(selected[0], api_operations=(('POST', '/api/1/preview'),))
    assert asyncio.run(bridge.handle_tool_request(event())) == 'policy_refused'
    assert harness.calls == []


def test_concurrent_duplicates_conflicts_and_detached_outcomes(harness):
    async def scenario():
        replies = await asyncio.gather(
            harness.bridge.handle_tool_request(event(name='list_runs', arguments='{"limit":2}')),
            harness.bridge.handle_tool_request(
                event(event_id='e2', name='list_runs', arguments='{ "limit": 2 }')
            ),
        )
        assert replies == ['accepted', 'accepted']
        assert len(harness.calls) == len(harness.provider.submissions) == 1
        original = harness.provider.submissions[0][3]
        harness.outcome.content['value']['untrusted_content']['text'] = 'altered'
        decoded = json.loads(original)
        decoded['content'].clear()
        assert (
            json.loads(original)['content']['value']['untrusted_content']['text'] == 'source text'
        )
        assert (
            await harness.bridge.handle_tool_request(
                event(event_id='e3', name='list_runs', arguments='{"limit":3}')
            )
            == 'conflict'
        )
        assert (
            await harness.bridge.handle_tool_request(event(event_id='event-1', call_id='c2'))
            == 'conflict'
        )
        assert (
            await harness.bridge.handle_tool_request(
                event(event_id='e4', name='get_playbook', arguments='{"section":"workflow"}')
            )
            == 'conflict'
        )
        assert len(harness.calls) == 1

    asyncio.run(scenario())


def test_refused_identity_cannot_be_reused_for_a_different_call(harness):
    async def scenario():
        assert (
            await harness.bridge.handle_tool_request(
                event(name='list_runs', arguments='{"limit":false}')
            )
            == 'invalid_input'
        )
        assert (
            await harness.bridge.handle_tool_request(
                event(event_id='e2', name='list_runs', arguments='{"limit":2}')
            )
            == 'conflict'
        )
        assert harness.calls == []

    asyncio.run(scenario())


def test_distinct_invocations_have_distinct_runtime_ids_and_start_closed(harness):
    bridge = bridge_for(harness.call, harness.provider, invocation='invocation-2')

    async def scenario():
        assert await bridge.handle_tool_request(event(invocation_id='invocation-2')) == 'closed'
        assert bridge.activate() == 'active'
        assert await bridge.handle_tool_request(event(invocation_id='invocation-2')) == 'accepted'
        assert await harness.bridge.handle_tool_request(event()) == 'accepted'
        assert harness.calls[0][1] != harness.calls[1][1]
        assert all(len(call[1]) <= 160 for call in harness.calls)
        assert bridge.activate() == 'closed'

    asyncio.run(scenario())


@pytest.mark.parametrize('error', [UnknownSession(), SessionEnded(), RuntimeError('secret-cookie')])
def test_runtime_exceptions_are_static_terminal_states_without_transport_leaks(harness, error):
    async def call(*args):
        harness.calls.append(args)
        raise error

    bridge = bridge_for(call, harness.provider)
    assert bridge.activate() == 'active'

    async def scenario():
        result = await bridge.handle_tool_request(event())
        assert result in ('session_unavailable', 'recovery_required')
        assert await bridge.handle_tool_request(event(event_id='e2', call_id='c2')) == result
        assert len(harness.calls) == 1
        assert harness.provider.submissions == []

    asyncio.run(scenario())


@pytest.mark.parametrize('permission', [False, None, 1, 'true'])
def test_access_requires_exact_true_before_dispatch_and_replay(harness, permission):
    async def scenario():
        harness.allowed[0] = permission
        assert await harness.bridge.handle_tool_request(event()) == 'access_lost'
        assert harness.calls == harness.provider.submissions == []
        harness.allowed[0] = True
        assert await harness.bridge.handle_tool_request(event()) == 'access_lost'

    asyncio.run(scenario())


def test_access_callback_exception_fails_closed_without_exception_text(harness):
    def access(_):
        raise RuntimeError('secret-token')

    bridge = bridge_for(harness.call, harness.provider, access)
    assert bridge.activate() == 'access_lost'
    assert asyncio.run(bridge.handle_tool_request(event())) == 'closed'
    assert harness.calls == harness.provider.submissions == []


def test_revocation_after_runtime_completion_suppresses_output(harness):
    async def call(*args):
        harness.calls.append(args)
        harness.allowed[0] = False
        return harness.outcome

    bridge = bridge_for(call, harness.provider, lambda _: harness.allowed[0])
    assert bridge.activate() == 'active'
    assert asyncio.run(bridge.handle_tool_request(event())) == 'access_lost'
    assert len(harness.calls) == 1
    assert harness.provider.submissions == []


@pytest.mark.parametrize(
    'content', [{'huge': 'x' * (32 * 1024)}, {'nan': float('nan')}, {'bad': object()}]
)
def test_unusable_outcomes_become_bounded_static_failures(harness, content):
    async def call(*args):
        return ToolOutcome(True, content, 'action-1', 'completed')

    bridge = bridge_for(call, harness.provider)
    assert bridge.activate() == 'active'
    assert asyncio.run(bridge.handle_tool_request(event())) == 'accepted'
    raw = harness.provider.submissions[0][3]
    assert len(raw) < 1024
    assert (
        json.loads(raw)['content']['error']['message'] == 'The tool outcome could not be delivered.'
    )


def test_runtime_refusal_envelope_is_preserved_exactly(harness):
    refused = ToolOutcome(
        False,
        ToolError('invalid_input', 'The input was refused.').envelope(),
        'action-2',
        'refused',
    )

    async def call(*args):
        return refused

    bridge = bridge_for(call, harness.provider)
    assert bridge.activate() == 'active'
    assert asyncio.run(bridge.handle_tool_request(event())) == 'accepted'
    assert json.loads(harness.provider.submissions[0][3]) == dict(
        ok=False, content=refused.content, action_id='action-2', state='refused'
    )


@pytest.mark.parametrize('reply', ['unknown', 'not_accepted', None, 'unexpected'])
def test_uncertain_delivery_fences_dispatch_until_lookup_without_reexecution(harness, reply):
    harness.provider.submit_reply = reply

    async def scenario():
        assert await harness.bridge.handle_tool_request(event()) == 'delivery_unknown'
        assert await harness.bridge.handle_tool_request(event(event_id='e2')) == 'delivery_unknown'
        assert (
            await harness.bridge.handle_tool_request(event(event_id='e3', call_id='c2'))
            == 'delivery_pending'
        )
        assert await harness.bridge.redeliver_result('call-1') == 'redelivery_refused'
        harness.provider.inspect_reply = 'unknown'
        assert await harness.bridge.reconcile_result('call-1') == 'delivery_unknown'
        harness.provider.inspect_reply = 'accepted'
        assert await harness.bridge.reconcile_result('call-1') == 'accepted'
        assert len(harness.calls) == len(harness.provider.submissions) == 1
        assert harness.provider.inspections == [('provider-1', 'thread-1', 'call-1')] * 2

    asyncio.run(scenario())


def test_timeout_requires_lookup_then_one_explicit_identical_redelivery(harness):
    async def submit(session, thread, call, outcome):
        harness.provider.submissions.append((session, thread, call, outcome))
        raise TimeoutError('secret-provider-token')

    harness.provider.submit_tool_result = submit

    async def scenario():
        assert await harness.bridge.handle_tool_request(event()) == 'delivery_unknown'
        harness.provider.inspect_reply = 'not_accepted'
        assert await harness.bridge.reconcile_result('call-1') == 'not_accepted'
        assert await harness.bridge.handle_tool_request(event(event_id='e2')) == 'not_accepted'
        assert len(harness.provider.submissions) == 1
        assert await harness.bridge.redeliver_result('call-1') == 'delivery_unknown'
        assert harness.provider.submissions[0] == harness.provider.submissions[1]
        assert len(harness.calls) == 1
        assert await harness.bridge.reconcile_result('call-1') == 'not_accepted'
        assert await harness.bridge.redeliver_result('call-1') == 'redelivery_refused'

    asyncio.run(scenario())


@pytest.mark.parametrize('stop', [True, False])
def test_stop_or_access_loss_prevents_cached_redelivery(harness, stop):
    harness.provider.submit_reply = 'unknown'

    async def scenario():
        assert await harness.bridge.handle_tool_request(event()) == 'delivery_unknown'
        harness.provider.inspect_reply = 'not_accepted'
        assert await harness.bridge.reconcile_result('call-1') == 'not_accepted'
        if stop:
            assert await harness.bridge.stop() == 'accepted'
        else:
            harness.allowed[0] = False
        assert await harness.bridge.redeliver_result('call-1') == (
            'stopped' if stop else 'access_lost'
        )
        harness.provider.inspect_reply = 'accepted'
        assert await harness.bridge.reconcile_result('call-1') == 'accepted'
        assert len(harness.calls) == len(harness.provider.submissions) == 1

    asyncio.run(scenario())


def test_stop_closes_admission_before_awaiting_interrupt_and_suppresses_inflight_output(harness):
    async def scenario():
        started, release = asyncio.Event(), asyncio.Event()

        async def call(*args):
            harness.calls.append(args)
            started.set()
            await release.wait()
            return harness.outcome

        bridge = bridge_for(call, harness.provider)
        assert bridge.activate() == 'active'
        first = asyncio.create_task(bridge.handle_tool_request(event()))
        await started.wait()
        queued = asyncio.create_task(bridge.handle_tool_request(event(event_id='e2', call_id='c2')))
        interruption = bridge.stop()
        release.set()
        assert await first == await queued == 'stopped'
        assert await bridge.handle_tool_request(event(event_id='e3', call_id='c3')) == 'stopped'
        assert harness.provider.interruptions == []
        assert await interruption == 'accepted'
        assert await bridge.stop() == 'accepted'
        assert len(harness.calls) == len(harness.provider.interruptions) == 1
        assert harness.provider.submissions == []

    asyncio.run(scenario())


def test_stop_during_submission_cannot_unsend_admitted_bytes_or_reopen_dispatch(harness):
    async def scenario():
        started, release = asyncio.Event(), asyncio.Event()

        async def submit(*args):
            harness.provider.submissions.append(args)
            started.set()
            await release.wait()
            return 'accepted'

        harness.provider.submit_tool_result = submit
        first = asyncio.create_task(harness.bridge.handle_tool_request(event()))
        await started.wait()
        harness.provider.interrupt_reply = 'unknown'
        assert await harness.bridge.stop() == 'unknown'
        release.set()
        assert await first == 'stopped'
        assert (
            await harness.bridge.handle_tool_request(event(event_id='e2', call_id='c2'))
            == 'stopped'
        )
        assert len(harness.provider.submissions) == len(harness.calls) == 1
        assert harness.bridge.activate() == 'closed'

    asyncio.run(scenario())


def test_cancellation_after_submission_remains_unknown_until_lookup(harness):
    async def scenario():
        started, pending = asyncio.Event(), asyncio.Event()

        async def submit(*args):
            harness.provider.submissions.append(args)
            started.set()
            await pending.wait()

        harness.provider.submit_tool_result = submit
        first = asyncio.create_task(harness.bridge.handle_tool_request(event()))
        await started.wait()
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        assert await harness.bridge.handle_tool_request(event(event_id='e2')) == 'delivery_unknown'
        assert await harness.bridge.reconcile_result('call-1') == 'accepted'
        assert len(harness.calls) == len(harness.provider.submissions) == 1

    asyncio.run(scenario())


@pytest.mark.parametrize('kind, count', [('calls', 64), ('events', 128)])
def test_capacity_never_evicts_an_identity_or_reopens_admission(harness, kind, count):
    async def scenario():
        for index in range(count):
            call = str(index) if kind == 'calls' else 'call-1'
            assert (
                await harness.bridge.handle_tool_request(event(event_id=str(index), call_id=call))
                == 'accepted'
            )
        assert (
            await harness.bridge.handle_tool_request(event(event_id='overflow', call_id='overflow'))
            == 'capacity_exhausted'
        )
        assert (
            await harness.bridge.handle_tool_request(event(event_id='0', call_id='0'))
            == 'capacity_exhausted'
        )
        assert len(harness.calls) == (count if kind == 'calls' else 1)

    asyncio.run(scenario())


def test_real_reads_refusals_and_delivery_lookup_never_repeat_api_requests(real_runtime):
    runtime, handle, access, app, _ = real_runtime
    provider = Transport()
    bridge = ReadOnlyBridge(
        InvocationBinding(handle, 'invocation-1', 'provider-1', 'thread-1'),
        registry=REGISTRY,
        definitions=REGISTRY.definitions('claude_managed', 'read_only', {'read'}),
        call_tool=runtime.call_tool,
        current_access=access,
        transport=provider,
    )

    async def scenario():
        try:
            assert bridge.activate() == 'active'
            for index, name, arguments in [
                (1, 'get_playbook', {'section': 'workflow'}),
                (2, 'list_runs', {'limit': 2}),
                (3, 'get_run_status', {'run_ids': [str(uuid4())]}),
            ]:
                provider.submit_reply = 'unknown'
                raw = event(
                    event_id=str(index),
                    call_id=str(index),
                    name=name,
                    arguments=json.dumps(arguments),
                )
                assert await bridge.handle_tool_request(raw) == 'delivery_unknown'
                count = len(app.paths)
                provider.inspect_reply = 'not_accepted'
                assert await bridge.reconcile_result(str(index)) == 'not_accepted'
                provider.submit_reply = 'accepted'
                assert await bridge.redeliver_result(str(index)) == 'accepted'
                assert len(app.paths) == count
                assert provider.submissions[-1] == provider.submissions[-2]
            assert json.loads(provider.submissions[-1][3])['ok'] is False
            assert all(method == 'GET' for method, _ in app.paths)
            with runtime.store.connection() as db:
                assert db.execute('SELECT COUNT(*) FROM agent_actions').fetchone()[0] == 3
        finally:
            await runtime.aclose()

    asyncio.run(scenario())


def test_duplicate_queued_during_submission_does_not_submit_or_execute_again(harness):
    async def scenario():
        started, release = asyncio.Event(), asyncio.Event()

        async def submit(*args):
            harness.provider.submissions.append(args)
            started.set()
            await release.wait()
            return 'accepted'

        harness.provider.submit_tool_result = submit
        first = asyncio.create_task(harness.bridge.handle_tool_request(event()))
        await started.wait()
        duplicate = asyncio.create_task(harness.bridge.handle_tool_request(event(event_id='e2')))
        release.set()
        assert await first == await duplicate == 'accepted'
        assert len(harness.calls) == len(harness.provider.submissions) == 1

    asyncio.run(scenario())


def test_cancelled_runtime_call_requires_recovery_and_never_reexecutes(harness):
    async def scenario():
        started, pending = asyncio.Event(), asyncio.Event()

        async def call(*args):
            harness.calls.append(args)
            started.set()
            await pending.wait()

        bridge = bridge_for(call, harness.provider)
        assert bridge.activate() == 'active'
        first = asyncio.create_task(bridge.handle_tool_request(event()))
        await started.wait()
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        assert await bridge.handle_tool_request(event(event_id='e2')) == 'recovery_required'
        assert len(harness.calls) == 1
        assert harness.provider.submissions == []

    asyncio.run(scenario())


def test_lookup_and_interrupt_exceptions_preserve_unknown_without_leaking(harness):
    async def fail(*args):
        raise RuntimeError('secret-token')

    harness.provider.inspect_tool_result = fail
    harness.provider.interrupt = fail
    harness.provider.submit_reply = 'unknown'

    async def scenario():
        assert await harness.bridge.handle_tool_request(event()) == 'delivery_unknown'
        assert await harness.bridge.reconcile_result('call-1') == 'delivery_unknown'
        assert await harness.bridge.stop() == 'unknown'
        assert await harness.bridge.redeliver_result('call-1') == 'stopped'
        assert len(harness.calls) == len(harness.provider.submissions) == 1

    asyncio.run(scenario())


@pytest.mark.parametrize('invocation', ['', ' ', 'x\n', 'é', 'x' * 129])
def test_invalid_trusted_binding_cannot_activate(harness, invocation):
    bridge = bridge_for(harness.call, harness.provider, invocation=invocation)
    assert bridge.activate() == 'invalid_binding'
    assert asyncio.run(bridge.handle_tool_request(event())) == 'closed'
    assert harness.calls == harness.provider.submissions == []


def test_pending_observation_reserves_call_identity_until_explicit_same_request_continues(harness):
    async def scenario():
        harness.provider.submit_reply = 'unknown'
        assert await harness.bridge.handle_tool_request(event()) == 'delivery_unknown'
        pending = event(event_id='e2', call_id='c2', name='list_runs', arguments='{"limit":2}')
        assert await harness.bridge.handle_tool_request(pending) == 'delivery_pending'
        assert await harness.bridge.reconcile_result('call-1') == 'accepted'
        changed = event(event_id='e3', call_id='c2', name='list_runs', arguments='{"limit":3}')
        assert await harness.bridge.handle_tool_request(changed) == 'conflict'
        assert len(harness.calls) == 1
        harness.provider.submit_reply = 'accepted'
        assert await harness.bridge.handle_tool_request(pending) == 'accepted'
        assert len(harness.calls) == 2
        assert harness.calls[-1][3] == {'limit': 2}

    asyncio.run(scenario())


@pytest.mark.parametrize('arguments', ['"\ud800"', '{"x":"\udfff"}', '"\\ud800"'])
def test_unpaired_surrogates_are_refused_without_dispatch(harness, arguments):
    assert (
        asyncio.run(harness.bridge.handle_tool_request(event(arguments=arguments)))
        == 'invalid_input'
    )
    assert harness.calls == harness.provider.submissions == []
