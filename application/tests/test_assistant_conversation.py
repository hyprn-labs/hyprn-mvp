"""Public study conversation journeys through the real delegated tool runtime."""

import asyncio
from dataclasses import replace
import json
from pathlib import Path

import httpx
import pytest

from conftest import LOOPBACK_ORIGIN
from hyprn_mvp_app.api import create_app
from hyprn_mvp_app.assistant.claude import ProviderError, Settings
from hyprn_mvp_app.assistant import records
from hyprn_mvp_app.auth import Auth
from hyprn_mvp_app.agent_runtime.delegations import ROLE_EFFECTS
from hyprn_mvp_app.agent_tools.registry import LOCAL_STAGE, REGISTRY
from hyprn_mvp_app.contracts import DomainError, digest, uid
from hyprn_mvp_app.store import Store


class NoModeling:
    def call(self, *args, **kwargs):
        raise DomainError('backend_unavailable', 503)


class Provider:
    def __init__(self):
        self.history = []
        self.created = []
        self.sent = []
        self.results = []
        self.interrupted = []
        self.unknown_message = False
        self.tool = ('get_study_overview', {})
        self.thread_id = None
        self.caps = []
        self.cost = 0

    def event(self, kind, **fields):
        value = dict(
            id='event_' + str(len(self.history)),
            type=kind,
            processed_at='2026-10-20T10:00:00Z',
            **fields,
        )
        self.history.append(value)
        return value

    async def create_session(self, settings, correlation):
        self.created.append(correlation)
        self.caps.append(settings.session_cents)
        return {'id': 'session_test'}

    async def session_account(self, session_id):
        return dict(status='idle', spent_cents=self.cost)

    async def ensure_allowance(self, session_id, cents):
        self.caps.append(cents)

    async def ensure_tools(self, session_id, definitions):
        self.definitions = definitions

    async def find_session(self, correlation):
        return {'id': 'session_test'} if correlation in self.created else None

    async def send(self, session, event):
        self.sent.append(event)
        echoed = self.event(event['type'], content=event['content'])
        self.event(
            'agent.custom_tool_use',
            name=self.tool[0],
            input=self.tool[1],
            **({'session_thread_id': self.thread_id} if self.thread_id else {}),
        )
        self.event('session.status_idle', stop_reason={'type': 'requires_action'})
        if self.unknown_message:
            raise ProviderError('provider_unavailable', uncertain=True)
        return {'data': [echoed]}

    async def events(self, session, since=None):
        for event in list(self.history):
            yield dict(event)

    async def tool_result(self, session, event_id, content, is_error=False):
        self.results.append(json.loads(content))
        self.event('user.custom_tool_result', custom_tool_use_id=event_id)
        self.event('agent.message', content=[{'type': 'text', 'text': 'Read confirmed.'}])
        self.event('session.status_idle', stop_reason={'type': 'end_turn'})

    async def interrupt(self, session):
        self.interrupted.append(session)
        return {'data': [self.event('user.interrupt')]}

    async def close(self):
        pass


@pytest.fixture
def system(tmp_path):
    store = Store(tmp_path / 'conversation.sqlite')
    auth = Auth(store, LOOPBACK_ORIGIN)
    actor = auth.provision('owner', 'synthetic private test password')
    sid = store.create_study(actor, uid(), 'Synthetic heat study')['study_id']
    app = create_app(store, auth, NoModeling(), environ={'HYPRN_MVP_AGENT_ENABLED': 'true'})
    owner = app.state.assistant
    provider = Provider()
    owner.provider = provider
    owner.settings = Settings(
        Path('/unused/private-key'),
        'agent_test',
        1,
        'env_test',
        100,
        200,
        digest(REGISTRY.definitions('claude_managed', LOCAL_STAGE, ROLE_EFFECTS['writer'])),
    )
    return app, owner, provider, store, actor, sid


async def client_for(app):
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url=LOOPBACK_ORIGIN,
    )
    reply = await client.post(
        '/api/1/session',
        json={'username': 'owner', 'password': 'synthetic private test password'},
        headers={'Origin': LOOPBACK_ORIGIN},
    )
    client.headers.update(
        {
            'Origin': LOOPBACK_ORIGIN,
            'X-CSRF-Token': reply.json()['data']['csrf_token'],
        }
    )
    return client


async def drained(owner):
    for _ in range(100):
        if not owner._tasks:
            return
        await asyncio.sleep(0.03)
    raise AssertionError('The conversation did not settle')


def test_public_message_uses_real_tools_and_reopens_one_provider_session(system):
    app, owner, provider, store, actor, sid = system

    async def exercise():
        client = await client_for(app)
        base = '/api/1/studies/' + sid + '/assistant'
        body = {'command_id': uid(), 'text': 'Read the study.'}
        assert (await client.post(base + '/messages', json=body)).status_code == 202
        await drained(owner)
        page = (await client.get(base)).json()['data']
        assert page['state'] == 'idle' and page['messages'][-1]['text'] == 'Read confirmed.'
        assert provider.results[0]['ok']
        assert 'Synthetic heat study' in json.dumps(provider.results)
        assert (await client.post(base + '/messages', json=body)).status_code == 202
        await drained(owner)
        assert len(provider.sent) == 1
        assert (
            await client.post(
                base + '/messages',
                json={
                    'command_id': uid(),
                    'text': 'Read it again.',
                },
            )
        ).status_code == 202
        await drained(owner)
        assert len(provider.created) == 1 and len(provider.sent) == 2
        assert len(provider.results) == 2
        await client.aclose()
        await owner.close()

    asyncio.run(exercise())


def test_chat_names_are_frozen_on_accept_and_replay_never_uses_the_viewer(system):
    app, owner, provider, store, actor, sid = system

    async def exercise():
        client = await client_for(app)
        base = '/api/1/studies/' + sid + '/assistant'
        alias = await client.put('/api/1/profile', json=dict(
            display_alias='Guérric <engineer>', expected_revision=0))
        assert alias.status_code == 200
        body = dict(command_id=uid(), text='Read the study.')
        assert (await client.post(base + '/messages', json=body)).status_code == 202
        await drained(owner)
        assert (await client.put('/api/1/profile', json=dict(
            display_alias='Later name', expected_revision=1))).status_code == 200
        assert (await client.post(base + '/messages', json=body)).status_code == 202
        await drained(owner)
        result = (await client.get(base)).json()['data']
        assert result['messages'][0]['author_display_name'] == 'Guérric <engineer>'
        assert result['messages'][-1]['author_display_name'] is None
        # Pre-alias turns retain account names, never the current alias.
        with store.connection(write=True) as db:
            db.execute('UPDATE assistant_turns SET author_display_name=NULL')
        records.ensure(store)
        result = (await client.get(base)).json()['data']
        assert result['messages'][0]['author_display_name'] == 'owner'
        await client.aclose()
        await owner.close()

    asyncio.run(exercise())


def test_uncertain_message_is_reconciled_without_resending(system):
    app, owner, provider, store, actor, sid = system
    provider.unknown_message = True

    async def exercise():
        owner.send(actor, sid, uid(), 'Read once.')
        await drained(owner)
        assert owner.read(actor, sid)['state'] == 'blocked'
        provider.unknown_message = False
        await owner.start()
        await drained(owner)
        assert len(provider.sent) == 1
        assert len(provider.results) == 1
        assert owner.read(actor, sid)['state'] == 'idle'
        await owner.close()

    asyncio.run(exercise())


def test_stop_before_dispatch_prevents_provider_session_and_tools(system):
    app, owner, provider, store, actor, sid = system

    async def exercise():
        owner.send(actor, sid, uid(), 'Read.')
        owner.stop(actor, sid)
        await drained(owner)
        assert not provider.created and not provider.sent and not provider.results
        assert owner.read(actor, sid)['state'] == 'idle'
        await owner.close()

    asyncio.run(exercise())


def test_busy_study_and_changed_idempotency_payload_are_refused(system):
    app, owner, provider, store, actor, sid = system

    async def exercise():
        command = uid()
        owner.send(actor, sid, command, 'Read.')
        for candidate, text in [(uid(), 'Another turn'), (command, 'Different text')]:
            with pytest.raises(DomainError) as caught:
                owner.send(actor, sid, candidate, text)
            assert caught.value.status == 409
        owner.stop(actor, sid)
        await drained(owner)
        await owner.close()

    asyncio.run(exercise())


def test_stopped_unused_allowance_is_available_to_another_study(system):
    _, owner, provider, store, actor, sid = system
    owner.settings = replace(owner.settings, total_cents=100)
    other = store.create_study(actor, uid(), 'Second study')['study_id']

    async def exercise():
        owner.send(actor, sid, uid(), 'Read.')
        owner.stop(actor, sid)
        await drained(owner)
        owner.send(actor, other, uid(), 'Read.')
        await drained(owner)
        assert provider.caps == [100, 100]
        assert owner.read(actor, other)['state'] == 'idle'
        await owner.close()

    asyncio.run(exercise())


def test_nonmembers_cannot_read_send_or_stop_and_unknown_fields_are_rejected(system):
    app, owner, provider, store, actor, sid = system

    async def exercise():
        with pytest.raises(DomainError):
            owner.read(uid(), sid)
        with pytest.raises(DomainError):
            owner.stop(uid(), sid)
        client = await client_for(app)
        base = '/api/1/studies/' + sid + '/assistant'
        result = await client.post(
            base + '/messages',
            json={
                'command_id': uid(),
                'text': 'Read.',
                'provider_id': 'attacker',
            },
        )
        assert result.status_code == 400
        assert not provider.created
        await client.aclose()
        await owner.close()

    asyncio.run(exercise())


def test_runtime_refuses_unoffered_effect_and_preserves_null_result(system):
    app, owner, provider, store, actor, sid = system
    provider.tool = ('delete_study', {})

    async def exercise():
        owner.send(actor, sid, uid(), 'Try an unavailable operation.')
        await drained(owner)
        assert provider.results and provider.results[0]['ok'] is False
        assert store.study(actor, sid)['name'] == 'Synthetic heat study'
        await owner.close()

    asyncio.run(exercise())


def test_lost_access_stops_delivery_before_storing_provider_messages(system):
    app, owner, provider, store, actor, sid = system

    async def exercise():
        owner.send(actor, sid, uid(), 'Read.')
        with store.connection(write=True) as db:
            db.execute('DELETE FROM memberships WHERE study_id=?', (sid,))
        await drained(owner)
        with store.connection() as db:
            assert records.row(db, sid)['error'] == 'access_lost'
            assert records.events(db, sid) == []
        assert not provider.sent
        await owner.close()

    asyncio.run(exercise())


def test_stop_clears_an_uncertain_turn_without_repeating_its_message(system):
    app, owner, provider, store, actor, sid = system
    provider.unknown_message = True

    async def exercise():
        owner.send(actor, sid, uid(), 'Read.')
        await drained(owner)
        owner.stop(actor, sid)
        await drained(owner)
        assert owner.read(actor, sid)['state'] == 'idle'
        assert len(provider.sent) == 1
        assert not provider.results
        await owner.close()

    asyncio.run(exercise())


def test_child_tool_uses_same_study_delegation_and_child_messages_stay_private(system):
    app, owner, provider, store, actor, sid = system
    provider.thread_id = 'thread_review'

    async def exercise():
        client = await client_for(app)
        base = '/api/1/studies/' + sid + '/assistant'
        response = await client.post(
            base + '/messages',
            json={'command_id': uid(), 'text': 'Ask a reviewer to read the study.'},
        )
        assert response.status_code == 202
        await drained(owner)
        assert provider.results and provider.results[0]['ok']
        child = provider.event(
            'agent.message',
            session_thread_id='thread_review',
            content=[{'type': 'text', 'text': 'Private child report.'}],
        )
        with store.connection(write=True) as db:
            records.save_event(db, sid, dict(child, _received_at=0))
        page = (await client.get(base)).json()['data']
        assert page['state'] == 'idle'
        assert all(m['text'] != 'Private child report.' for m in page['messages'])
        await client.aclose()
        await owner.close()

    asyncio.run(exercise())


def test_budget_public_read_separates_spend_reservations_and_unknown_usage(system):
    app, owner, provider, store, actor, sid = system
    owner.settings = replace(owner.settings, prior_cents=20, approved_minor=180,
                             approved_currency='EUR', conversion_date='2026-10-20')
    calls = []

    async def spending(session):
        calls.append(session)
        return 37

    provider.spending = spending

    async def exercise():
        client = await client_for(app)
        base = '/api/1/studies/' + sid + '/assistant'
        empty = (await client.get(base + '/budget')).json()['data']
        assert empty['spent_cents'] == 20 and empty['remaining_cents'] == 180
        assert empty['study_spent_cents'] is None
        assert empty['approved']['minor'] == 180
        records.accept(store, actor, sid, uid(), 'Unsent test intent', owner.settings)
        unknown = (await client.get(base + '/budget')).json()['data']
        assert unknown['spent_cents'] is None and unknown['remaining_cents'] is None
        assert unknown['reserved_cents'] == 0 and unknown['unallocated_cents'] is None
        with store.connection(write=True) as db:
            records.update(db, sid, provider_id='session_budget', provision='accepted')
        value = (await client.get(base + '/budget')).json()['data']
        assert value['spent_cents'] == 57 and value['remaining_cents'] == 143
        assert value['study_spent_cents'] == 37 and value['study_remaining_cents'] == 143
        assert value['usage_current'] is True
        global_value = (await client.get('/api/1/assistant/budget')).json()['data']
        assert global_value['study_spent_cents'] is None
        assert calls == ['session_budget']
        assert 'session_budget' not in json.dumps(global_value)
        owner.budget._costs['session_budget'] = (37, 1)
        owner.budget._attempted.clear()

        async def unavailable(session):
            raise ProviderError('provider_unavailable')

        provider.spending = unavailable
        stale = (await client.get(base + '/budget')).json()['data']
        assert stale['usage_current'] is False and stale['study_spent_cents'] == 37
        assert stale['checked_at'] == 1
        await client.delete('/api/1/session')
        assert (await client.get(base + '/budget')).status_code == 401
        await client.aclose()

    asyncio.run(exercise())


def test_prior_usage_reduces_shared_allowance_not_study_admission(system):
    _, owner, provider, store, actor, sid = system
    owner.settings = replace(owner.settings, prior_cents=101)

    async def exercise():
        owner.send(actor, sid, uid(), 'Read.')
        await drained(owner)
        assert provider.caps == [99, 99]
        assert owner.read(actor, sid)['state'] == 'idle'
        await owner.close()

    asyncio.run(exercise())


def test_existing_study_can_draw_all_remaining_shared_allowance(system):
    _, owner, provider, store, actor, sid = system

    async def exercise():
        owner.send(actor, sid, uid(), 'First turn.')
        await drained(owner)
        provider.cost = 120  # Above the retired per-study limit of 100.
        owner.send(actor, sid, uid(), 'Second turn.')
        await drained(owner)
        assert provider.caps == [200, 200, 200]
        assert len(provider.sent) == 2
        await owner.close()

    asyncio.run(exercise())


def test_unknown_usage_never_grants_remaining_allowance(system):
    _, owner, provider, store, actor, sid = system
    other = store.create_study(actor, uid(), 'Another study')['study_id']

    async def exercise():
        owner.send(actor, sid, uid(), 'First turn.')
        await drained(owner)
        async def unavailable(_):
            raise ProviderError('provider_unavailable')
        provider.session_account = unavailable
        owner.send(actor, other, uid(), 'Do not spend without accounting.')
        await drained(owner)
        assert len(provider.created) == 1 and len(provider.sent) == 1
        assert owner.read(actor, other)['state'] == 'blocked'
        await owner.close()

    asyncio.run(exercise())


def test_parallel_study_turns_do_not_spend_the_same_allowance(system):
    _, owner, provider, store, actor, sid = system
    other = store.create_study(actor, uid(), 'Another study')['study_id']

    async def exercise():
        entered, release = asyncio.Event(), asyncio.Event()
        original_send = provider.send
        async def hold_first(session, event):
            if not entered.is_set():
                entered.set()
                await release.wait()
                provider.cost = 30
            return await original_send(session, event)
        provider.send = hold_first
        owner.send(actor, sid, uid(), 'First turn.')
        await entered.wait()
        owner.send(actor, other, uid(), 'Second turn.')
        await asyncio.sleep(0)
        assert len(provider.created) == 1
        release.set()
        await drained(owner)
        assert provider.caps == [200, 200, 170, 170]
        assert owner.read(actor, other)['state'] == 'idle'
        await owner.close()

    asyncio.run(exercise())


def test_confirmed_billing_failure_is_actionable_without_replaying_the_turn(system):
    _, owner, provider, store, actor, sid = system

    async def exercise():
        original = provider.send
        async def billing_failure(session, event):
            provider.sent.append(event)
            echoed = provider.event(event['type'], content=event['content'])
            provider.event('session.error', error={'type': 'billing_error',
                                                 'message': 'private provider text'})
            provider.event('session.status_idle', stop_reason={'type': 'retries_exhausted'})
            return {'data': [echoed]}
        provider.send = billing_failure
        owner.send(actor, sid, uid(), 'First request.')
        await drained(owner)
        view = owner.read(actor, sid)
        assert view['error'] == 'provider_billing_error' and view['can_send']
        assert 'private provider text' not in json.dumps(view)
        assert len(provider.sent) == 1
        provider.send = original
        owner.send(actor, sid, uid(), 'New human request after funding.')
        await drained(owner)
        assert len(provider.sent) == 2 and owner.read(actor, sid)['state'] == 'idle'
        await owner.close()
    asyncio.run(exercise())


def test_history_persistence_does_not_block_conversation_reads(system, monkeypatch):
    """A slow hosted event write must leave the HTTP event loop responsive."""
    import threading

    app, owner, provider, store, actor, sid = system
    original = records.save_event
    released = threading.Event()

    async def exercise():
        client = await client_for(app)
        records.accept(store, actor, sid, uid(), 'Synthetic history import.', owner.settings)
        _, turn = owner._load(sid)
        owner._open_runtime(turn)
        provider.event('agent.message', content=[{'type': 'text', 'text': 'Saved response.'}])
        entered = asyncio.Event()
        loop = asyncio.get_running_loop()

        def delayed_write(db, study, event):
            loop.call_soon_threadsafe(entered.set)
            assert released.wait(1), 'History persistence blocked the HTTP event loop'
            return original(db, study, event)

        monkeypatch.setattr(records, 'save_event', delayed_write)
        history = asyncio.create_task(owner._history(sid, 'session_test', turn))
        try:
            await asyncio.wait_for(entered.wait(), 2)
            response = await client.get('/api/1/studies/' + sid + '/assistant')
            assert response.status_code == 200
        finally:
            released.set()
        saved = await history
        assert len(saved) == 1 and saved[0]['type'] == 'agent.message'
        await client.aclose()
        await owner.close()

    asyncio.run(exercise())


@pytest.mark.parametrize('boundary', ['authorization', 'action_intent', 'action_completion'])
def test_tool_bookkeeping_does_not_block_http(system, monkeypatch, boundary):
    """Tool authorization and durable journals must not stall unrelated HTTP reads."""
    import threading
    from hyprn_mvp_app.agent_runtime import journal

    app, owner, provider, store, actor, sid = system
    released = threading.Event()

    async def exercise():
        client = await client_for(app)
        records.accept(store, actor, sid, uid(), 'Synthetic tool responsiveness.', owner.settings)
        _, turn = owner._load(sid)
        owner._open_runtime(turn)
        event = provider.event('agent.custom_tool_use', name='get_study_overview', input={})
        entered = asyncio.Event()
        loop = asyncio.get_running_loop()
        target, name = {
            'authorization': (owner, '_authorize'),
            'action_intent': (journal, 'intend'),
            'action_completion': (journal, 'complete'),
        }[boundary]
        original = getattr(target, name)

        def delayed(*args, **kwargs):
            loop.call_soon_threadsafe(entered.set)
            assert released.wait(1), 'Tool bookkeeping blocked the HTTP event loop'
            return original(*args, **kwargs)

        monkeypatch.setattr(target, name, delayed)
        task = asyncio.create_task(owner._tool(sid, turn, 'session_test', event, []))
        try:
            await asyncio.wait_for(entered.wait(), 2)
            reply = await client.get('/api/1/studies/' + sid + '/assistant')
            assert reply.status_code == 200
        finally:
            released.set()
        await task
        assert provider.results and provider.results[-1]['ok']
        await client.aclose()
        await owner.close()

    asyncio.run(exercise())
