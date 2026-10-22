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
        return {'id': 'session_test'}

    async def session_account(self, session_id):
        return dict(status='idle', spent_cents=self.cost)

    async def remove_session_cap(self, session_id):
        self.caps.append(None)

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
        assert provider.caps == [None]
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


def test_budget_public_read_is_cumulative_user_scoped_and_has_no_session_ceiling(system):
    app, owner, provider, store, actor, sid = system
    async def exercise():
        client = await client_for(app)
        empty = (await client.get('/api/1/assistant/budget')).json()['data']
        assert empty['limit_cents'] == 2000 and empty['spent_cents'] == 0
        assert empty['period'] == 'cumulative' and empty['resets_at'] is None
        owner.send(actor, sid, uid(), 'Read.')
        await drained(owner)
        provider.cost = 237
        value = (await client.get('/api/1/assistant/budget')).json()['data']
        assert value['spent_cents'] == 237 and value['remaining_cents'] == 1763
        assert 'study_limit_cents' not in value and 'reserved_cents' not in value
        async def unavailable(_):
            raise ProviderError('provider_unavailable')
        provider.session_account = unavailable
        unknown = (await client.get('/api/1/assistant/budget')).json()['data']
        assert unknown['spent_cents'] is None and unknown['remaining_cents'] is None
        await client.aclose()
        await owner.close()
    asyncio.run(exercise())


def test_other_users_spending_never_reduces_this_users_allowance(system):
    from hyprn_mvp_app.assistant import allowance
    _, owner, provider, store, actor, sid = system
    stranger = uid()
    with store.connection(write=True) as db:
        db.execute('INSERT INTO users(actor_id,username,password_hash) VALUES(?,?,?)',
                   (stranger, 'second', 'synthetic unused hash'))
    other = store.create_study(stranger, uid(), 'Other account')['study_id']
    records.accept(store, stranger, other, uid(), 'Other spending.', owner.settings)
    with store.connection(write=True) as db:
        records.update(db, other, provider_id='other_session', provision='accepted')
    async def account(session):
        assert session == 'other_session'
        return dict(status='idle', spent_cents=2500)
    provider.session_account = account
    async def exercise():
        assert await allowance.check(store, provider, actor) == (0, [])
        with pytest.raises(ProviderError, match='user_allowance_exhausted'):
            await allowance.check(store, provider, stranger)
    asyncio.run(exercise())


def test_existing_study_can_draw_all_remaining_shared_allowance(system):
    _, owner, provider, store, actor, sid = system

    async def exercise():
        owner.send(actor, sid, uid(), 'First turn.')
        await drained(owner)
        provider.cost = 120  # Above the retired per-study limit of 100.
        owner.send(actor, sid, uid(), 'Second turn.')
        await drained(owner)
        assert provider.caps == [None, None]
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


def test_parallel_studies_start_before_either_turn_finishes(system):
    app, owner, provider, store, actor, sid = system
    other = store.create_study(actor, uid(), 'Another study')['study_id']

    async def exercise():
        started = []
        release = asyncio.Event()
        caps = {}
        async def create(settings, correlation):
            session = 'session_' + str(len(caps))
            caps[session] = settings.session_cents
            return {'id': session}
        async def account(session):
            return dict(status='running', spent_cents=0, cap_cents=caps[session])
        async def ensure(session, cents, **kwargs):
            caps[session] = cents
        async def send(session, event):
            started.append(session)
            await release.wait()
            return await provider.__class__.send(provider, session, event)
        provider.create_session, provider.session_account = create, account
        provider.ensure_allowance, provider.send = ensure, send
        client = await client_for(app)
        for study in (sid, other):
            reply = await client.post('/api/1/studies/' + study + '/assistant/messages',
                                      json={'command_id': uid(), 'text': 'Read this study.'})
            assert reply.status_code == 202 and reply.json()['data']['state'] == 'queued'
        try:
            for _ in range(100):
                if len(started) == 2:
                    break
                await asyncio.sleep(.01)
            assert len(started) == 2, 'One study must not wait for the other turn to finish'
            assert all(owner.read(actor, study)['state'] == 'starting' for study in (sid, other))
        finally:
            release.set()
            await drained(owner)
            await client.aclose()
            await owner.close()
    asyncio.run(exercise())


def test_cancel_queued_message_is_immediate_and_never_delivered(system):
    _, owner, provider, store, actor, sid = system
    async def exercise():
        async with owner._allowance_admission:
            owner.send(actor, sid, uid(), 'Cancel before admission.')
            await asyncio.sleep(0)
            assert owner.read(actor, sid)['state'] == 'queued'
            assert owner.stop(actor, sid)['state'] == 'idle'
            assert not provider.sent and not provider.created
        await drained(owner)
        assert not provider.sent and not provider.created
        await owner.close()
    asyncio.run(exercise())


def test_queue_time_does_not_consume_the_execution_deadline(system):
    _, owner, provider, store, actor, sid = system
    async def exercise():
        command = uid()
        records.accept(store, actor, sid, command, 'Old queued request.', owner.settings)
        with store.connection(write=True) as db:
            db.execute('UPDATE assistant_turns SET created_at=1 WHERE turn_id=?', (command,))
        owner.wake(sid)
        await drained(owner)
        assert owner.read(actor, sid)['state'] == 'idle'
        assert provider.sent
        await owner.close()
    asyncio.run(exercise())


def test_spending_survives_archiving_and_membership_removal(system):
    from hyprn_mvp_app.assistant import allowance
    _, owner, provider, store, actor, sid = system
    records.accept(store, actor, sid, uid(), 'A long study.', owner.settings)
    with store.connection(write=True) as db:
        records.update(db, sid, provider_id='session_test', provision='accepted')
        db.execute('DELETE FROM memberships WHERE study_id=? AND actor_id=?',(sid,actor))
    provider.cost = 1999
    async def exercise():
        assert (await allowance.check(store, provider, actor))[0] == 1999
        provider.cost = 2000
        with pytest.raises(ProviderError, match='user_allowance_exhausted'):
            await allowance.check(store, provider, actor)
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



def test_active_work_checks_cumulative_spending_without_renewing_caps(system):
    _, owner, provider, store, actor, sid = system
    async def exercise():
        records.accept(store, actor, sid, uid(), 'Active work.', owner.settings)
        with store.connection(write=True) as db:
            records.update(db, sid, provider_id='session_test', provision='accepted')
        provider.cost = 2001
        with pytest.raises(ProviderError, match='user_allowance_exhausted'):
            await owner._check_spending(sid)
        assert not provider.caps
    asyncio.run(exercise())


def test_provider_overshoot_is_charged_before_admitting_another_study(system):
    _, owner, provider, store, actor, sid = system
    other = store.create_study(actor, uid(), 'Spent study')['study_id']
    async def exercise():
        records.accept(store, actor, other, uid(), 'Completed turn.', owner.settings)
        with store.connection(write=True) as db:
            records.update(db, other, provider_id='session_spent', provision='accepted',
                           state='idle', active_turn=None)
        provider.caps.append(100)
        provider.cost = 2005
        owner.send(actor, sid, uid(), 'No remaining allowance.')
        await drained(owner)
        assert owner.read(actor, sid)['error'] == 'user_allowance_exhausted'
        assert not provider.sent and not provider.created
        await owner.close()
    asyncio.run(exercise())


def test_resume_after_delivered_tool_error_preserves_message_and_successful_tools(system):
    app, owner, provider, store, actor, sid = system
    async def exercise():
        client = await client_for(app)
        original = provider.events
        failed = False
        async def events(session, since=None):
            nonlocal failed
            if provider.results and not failed:
                failed = True
                raise RuntimeError('synthetic transport failure after delivered tool')
            async for event in original(session, since):
                yield event
        provider.events = events
        # Keep the first history without end_turn; it is observed on the next fetch.
        async def tool_result(session, event_id, content, is_error=False):
            provider.results.append(json.loads(content))
            provider.event('user.custom_tool_result', custom_tool_use_id=event_id)
            provider.event('session.status_idle', stop_reason={'type':'end_turn'})
        provider.tool_result = tool_result
        owner.send(actor, sid, uid(), 'Continue through the result.')
        await drained(owner)
        page=owner.read(actor,sid)
        assert page['state']=='blocked' and page['can_resume']
        reply=await client.post('/api/1/studies/'+sid+'/assistant/resume',json={})
        assert reply.status_code==202
        await drained(owner)
        assert owner.read(actor,sid)['state']=='idle'
        assert len(provider.sent)==len(provider.results)==1
        await client.aclose()
        await owner.close()
    asyncio.run(exercise())



def test_restart_preserves_blocked_diagnostic_until_explicit_resume(system):
    _, owner, provider, store, actor, sid = system
    async def exercise():
        records.accept(store, actor, sid, uid(), 'Retained work.', owner.settings)
        with store.connection(write=True) as db:
            records.update(db, sid, state='blocked', error='assistant_internal_error')
        await owner.start()
        assert not owner._tasks
        assert owner.read(actor, sid)['error'] == 'assistant_internal_error'
        assert not provider.sent
        await owner.close()
    asyncio.run(exercise())
