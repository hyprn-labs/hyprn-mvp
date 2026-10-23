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

    async def thread_agent(self, session_id, thread_id):
        return {'id': thread_id, 'session_id': session_id,
                'agent': {'id': 'agent_source_review', 'version': 1}}

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
        # Once projected, historical attribution cannot be rebuilt from mutable records.
        with store.connection(write=True) as db:
            db.execute('UPDATE assistant_turns SET author_display_name=NULL')
        records.ensure(store)
        result = (await client.get(base)).json()['data']
        assert result['messages'][0]['author_display_name'] == 'Guérric <engineer>'
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
    configure_reviewers(owner)

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
            'authorization': (owner, 'authorize_turn'),
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


def test_public_projection_retains_safe_identity_without_reading_raw_history(system, monkeypatch):
    _, owner, provider, store, actor, sid = system
    records.accept(store, actor, sid, uid(), 'Read safely.', owner.settings)
    event = dict(id='event_private_provider_identity', type='agent.message',
                 processed_at='2026-10-22T10:00:00Z', _received_at=1,
                 content=[dict(type='text', text='Visible answer.'),
                          dict(type='thinking', text='Private reasoning.')])
    with store.connection(write=True) as db:
        records.save_event(db, sid, event)
        records.save_event(db, sid, event)
    page = owner.read(actor, sid)
    assert 'event_private_provider_identity' not in json.dumps(page)
    assert len([m for m in page['messages'] if m['text'] == 'Visible answer.']) == 1
    assert 'Private reasoning.' not in json.dumps(page)
    def forbidden(*args):
        raise AssertionError('Public polling read retained raw events')
    monkeypatch.setattr(records, 'events', forbidden)
    assert owner.read(actor, sid) == page


def test_public_pages_resume_exactly_and_reject_cross_study_cursor(system):
    _, owner, _, store, actor, sid = system
    records.accept(store, actor, sid, uid(), 'Read.', owner.settings)
    for index in range(205):
        with store.connection(write=True) as db:
            records.save_event(db, sid, dict(id='provider_'+str(index), type='agent.message',
                _received_at=index, content=[dict(type='text', text=str(index))]))
    page = owner.read(actor, sid)
    assert len(page['messages']) == 200 and page['has_earlier_messages']
    assert 'next_cursor' in page
    assert owner.read(actor, sid, after=page['next_cursor'])['messages'] == []
    earlier = owner.read(actor, sid, before=page['earlier_cursor'])
    assert len(earlier['messages']) == 6 and not earlier['has_earlier_messages']
    other = store.create_study(actor, uid(), 'Other study')['study_id']
    with pytest.raises(DomainError):
        owner.read(actor, other, after=page['next_cursor'])
    with pytest.raises(DomainError):
        owner.read(uid(), sid, after=page['next_cursor'])


def test_provider_poll_uses_persisted_cursor_and_deduplicates_overlapping_page(system, monkeypatch):
    _, owner, provider, store, actor, sid = system
    records.accept(store, actor, sid, uid(), 'Read.', owner.settings)
    _, turn = owner._load(sid)
    owner._open_runtime(turn)
    provider.event('agent.message', content=[dict(type='text', text='Answer.')])
    cursors = []
    original = provider.events
    async def recorded(session, since=None):
        cursors.append(since)
        async for event in original(session, since):
            yield event
    provider.events = recorded
    def forbidden(*args):
        raise AssertionError('Provider polling loaded full retained history')
    monkeypatch.setattr(records, 'events', forbidden)
    async def exercise():
        assert len(await owner._history(sid, 'session_test', turn)) == 1
        assert await owner._history(sid, 'session_test', turn) == []
        assert cursors == [None, '2026-10-20T10:00:00Z']
        assert len(owner.read(actor, sid)['messages']) == 2
        await owner.close()
    asyncio.run(exercise())


def test_long_raw_history_never_enters_public_poll_result(system, monkeypatch):
    from contextlib import contextmanager
    _, owner, _, store, actor, sid = system
    records.accept(store, actor, sid, uid(), 'Read.', owner.settings)
    with store.connection(write=True) as db:
        for index in range(300):
            records.save_event(db, sid, dict(id='reasoning_'+str(index),
                type='agent.message', session_thread_id='private_reviewer',
                _received_at=index, content=[dict(type='text', text='x'*32768)]))
        retained_bytes = db.execute('SELECT sum(length(payload)) FROM assistant_events').fetchone()[0]
    decoded = []
    queries = []
    original = json.loads
    connection = store.connection
    @contextmanager
    def measured_connection(*args, **kwargs):
        with connection(*args, **kwargs) as db:
            db.set_trace_callback(queries.append)
            yield db
    def measured(value, *args, **kwargs):
        decoded.append(len(value))
        return original(value, *args, **kwargs)
    monkeypatch.setattr(records.json, 'loads', measured)
    monkeypatch.setattr(store, 'connection', measured_connection)
    page = records.public(store, actor, sid, available=True)
    assert retained_bytes > 9_800_000
    assert sum(decoded) == 0, 'Public read decoded retained private conversation payloads'
    assert len(queries) <= 12
    assert not any('assistant_events' in query for query in queries)
    assert len(page['messages']) == 1


def waiting_analysis(system):
    _, owner, provider, store, actor, sid = system
    command, version = uid(), uid()
    records.accept(store, actor, sid, command, 'Monitor the accepted analysis.', owner.settings)
    _, turn = owner._load(sid)
    owner._open_runtime(turn)
    start = provider.event('user.message', content=[dict(type='text', text='Accepted request.')])
    event = provider.event('agent.custom_tool_use', name='get_analysis_execution',
                           input=dict(calculation_version_id=version))
    provider.event('session.status_idle', stop_reason=dict(type='requires_action'))
    result = dict(calculation_version_id=version, state='calculating', completed_count=0,
                  total_count=126, estimate_id=None, reason=None)
    with store.connection(write=True) as db:
        records.update(db, sid, provider_id='session_test', provision='accepted', state='waiting')
        db.execute("UPDATE assistant_turns SET delivery='accepted',provider_event=? WHERE turn_id=?",
                   (start['id'], command))
        for value in provider.history:
            records.save_event(db, sid, dict(value, _received_at=1))
        db.execute('INSERT INTO assistant_tool_results VALUES(?,?,?,?,?,?)',
            (sid, event['id'], command, json.dumps(dict(ok=True, content=result,
                action_id=None, state='complete')), 0, 'waiting'))
    return turn, result


def test_durable_wait_survives_restart_and_expiry_without_inference_polling(system):
    _, owner, provider, store, actor, sid = system
    turn, result = waiting_analysis(system)
    reads = []
    complete = False
    def read(human, study, version):
        assert (human, study, version) == (actor, sid, result['calculation_version_id'])
        reads.append(version)
        return dict(result, state='complete' if complete else 'calculating')
    owner._analysis_reader = read
    async def exercise():
        task = asyncio.create_task(owner._pump(sid))
        for _ in range(100):
            if reads:
                break
            await asyncio.sleep(.01)
        assert reads and not provider.results and not provider.sent
        assert owner.read(actor, sid)['state'] == 'waiting'
        for _ in range(100):
            progress = owner.read(actor, sid)['analysis_progress']
            if progress:
                break
            await asyncio.sleep(.01)
        assert progress['calculation_version_id'] == result['calculation_version_id']
        assert progress['completed_count'] == 0 and progress['total_count'] == 126
        assert progress['state'] == 'calculating'
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        with store.connection(write=True) as db:
            db.execute('UPDATE agent_delegations SET expires_at=1 WHERE study_id=?', (sid,))
        nonlocal complete
        complete = True
        await owner.start()
        await drained(owner)
        assert owner.read(actor, sid)['state'] == 'idle'
        assert owner.read(actor, sid)['analysis_progress'] is None
        assert not provider.sent and len(provider.results) == 1
        assert provider.results[0]['content']['state'] == 'complete'
        with store.connection() as db:
            assert db.execute('SELECT count(*) FROM assistant_tool_results').fetchone()[0] == 1
        await owner.close()
    asyncio.run(exercise())


def test_analysis_progress_changes_are_compact_durable_and_turn_scoped(system, monkeypatch):
    _, owner, provider, store, actor, sid = system
    turn, result = waiting_analysis(system)
    event_id = next(e['id'] for e in provider.history if e['type'] == 'agent.custom_tool_use')
    result.update(admission_state='ready', runs=[dict(reused=True), dict(reused=False)])
    monkeypatch.setattr(records.time, 'time', lambda: 100)
    records.observe_analysis(store, sid, turn['turn_id'], event_id, result)
    initial = owner.read(actor, sid)['analysis_progress']
    assert initial['reused_count'] == 1
    assert initial['last_progress_at'] == 100
    monkeypatch.setattr(records.time, 'time', lambda: 200)
    records.observe_analysis(store, sid, turn['turn_id'], event_id, result)
    assert owner.read(actor, sid)['analysis_progress'] == initial
    result.update(completed_count=126, state='validating')
    records.observe_analysis(store, sid, turn['turn_id'], event_id, result)
    current = owner.read(actor, sid)['analysis_progress']
    assert current['last_progress_at'] == 200 and current['state'] == 'validating'
    assert current['completed_count'] == current['total_count'] == 126
    with store.connection(write=True) as db:
        assert db.execute("SELECT count(*) FROM assistant_events WHERE "
            "event_type='hyprn.analysis_progress'").fetchone()[0] == 2
        saved = db.execute('SELECT content FROM assistant_tool_results').fetchone()[0]
        assert json.loads(saved)['content']['completed_count'] == 0
        db.execute("UPDATE assistant_tool_results SET delivery='accepted'")
    assert owner.read(actor, sid)['analysis_progress'] is None
    with store.connection(write=True) as db:
        db.execute("UPDATE assistant_tool_results SET delivery='waiting'")
        records.update(db, sid, active_turn=uid())
    assert owner.read(actor, sid)['analysis_progress'] is None
    with pytest.raises(DomainError):
        owner.read(uid(), sid)
    assert not provider.results and not provider.sent


@pytest.mark.parametrize('revocation', ['delegation', 'membership', 'stop'])
def test_durable_wait_never_renews_revoked_or_stopped_authority(system, revocation):
    _, owner, provider, store, actor, sid = system
    _, result = waiting_analysis(system)
    reads = []
    def read(*args):
        reads.append(args)
        return dict(result, state='complete')
    owner._analysis_reader = read
    with store.connection(write=True) as db:
        if revocation == 'delegation':
            db.execute("UPDATE agent_delegations SET revoked_at=1,revoked_reason='explicit' "
                       'WHERE study_id=?', (sid,))
        elif revocation == 'membership':
            db.execute('DELETE FROM memberships WHERE study_id=?', (sid,))
        else:
            db.execute('UPDATE assistant_turns SET stopped=1 WHERE study_id=?', (sid,))
    async def exercise():
        await owner.start()
        await drained(owner)
        assert not reads and not provider.sent and not provider.results
        with store.connection() as db:
            assert records.row(db, sid)['state'] == ('idle' if revocation == 'stop' else 'blocked')
        await owner.close()
    asyncio.run(exercise())


def configure_reviewers(owner):
    from hyprn_mvp_app.assistant.reviewers import LIMITS
    owner.configure_reviewers({
        'source-reviewer': {'id': 'agent_source_review', 'version': 1},
        'model-reviewer': {'id': 'agent_model_review', 'version': 1},
        'answer-reviewer': {'id': 'agent_answer_review', 'version': 1},
    }, LIMITS)


@pytest.mark.parametrize('admitted', [False, True])
def test_reviewer_cannot_invoke_mutations_even_with_a_pinned_identity(system, admitted):
    app, owner, provider, store, actor, sid = system
    provider.thread_id = 'thread_review'
    provider.tool = ('update_study_brief', {})
    if admitted:
        configure_reviewers(owner)

    async def exercise():
        client = await client_for(app)
        response = await client.post('/api/1/studies/' + sid + '/assistant/messages',
            json={'command_id': uid(), 'text': 'Review the brief.'})
        assert response.status_code == 202
        await drained(owner)
        assert not provider.results
        with store.connection() as db:
            assert not db.execute('SELECT 1 FROM study_brief_drafts WHERE study_id=?', (sid,)).fetchone()
            assert records.row(db, sid)['error'] == 'reviewer_write_forbidden'
        await client.aclose()
        await owner.close()
    asyncio.run(exercise())


def test_unpinned_reviewer_cannot_read_study_data(system):
    app, owner, provider, store, actor, sid = system
    provider.thread_id = 'thread_unknown'
    async def exercise():
        client = await client_for(app)
        await client.post('/api/1/studies/' + sid + '/assistant/messages',
            json={'command_id': uid(), 'text': 'Review.'})
        await drained(owner)
        assert not provider.results
        with store.connection() as db:
            assert records.row(db, sid)['error'] == 'reviewer_identity_unapproved'
        await client.aclose()
        await owner.close()
    asyncio.run(exercise())



def test_reviewer_limits_survive_owner_recreation_and_duplicate_delivery(system):
    from hyprn_mvp_app.assistant.reviewers import admit
    app, owner, provider, store, actor, sid = system
    configure_reviewers(owner)
    records.accept(store, actor, sid, uid(), 'Review the study.', owner.settings)
    _, turn = owner._load(sid)
    owner._open_runtime(turn)
    async def exercise():
        await owner._session(owner._load(sid)[0], owner.settings, turn)
        for number in range(24):
            event = {'id': 'review_event_' + str(number), 'session_thread_id': 'thread_review',
                     'name': 'get_study_overview', 'input': {}}
            assert await admit(owner, sid, turn, 'session_test', event)
            assert await admit(owner, sid, turn, 'session_test', event)
        # No in-memory quota state: a fresh conversation owner reads the same admission ledger.
        replacement = type(owner)(store, owner.runtime, provider, owner.settings)
        configure_reviewers(replacement)
        with pytest.raises(ProviderError, match='reviewer_call_limit'):
            await admit(replacement, sid, turn, 'session_test', {**event, 'id': 'over_limit'})
        for thread in ('thread_two', 'thread_three'):
            await admit(replacement, sid, turn, 'session_test',
                        {**event, 'id': thread, 'session_thread_id': thread})
        with pytest.raises(ProviderError, match='reviewer_call_limit'):
            await admit(replacement, sid, turn, 'session_test',
                        {**event, 'id': 'four', 'session_thread_id': 'thread_four'})
        owner.runtime.sessions.end(turn['runtime_session'])
        await owner.close()
    asyncio.run(exercise())



@pytest.mark.parametrize('bindings', [None, [], {'source-reviewer': None}])
def test_reviewer_configuration_rejects_malformed_identity_records(bindings):
    from hyprn_mvp_app.assistant.reviewers import configured, LIMITS
    with pytest.raises(ProviderError, match='reviewer_configuration_invalid'):
        configured(bindings, LIMITS)


@pytest.mark.parametrize('mode,expected', [
    ('fetched', 'retrieved_excerpt'), ('document', 'retrieved_excerpt'),
    ('search', 'author_supplied'), ('failed', 'author_supplied'),
    ('unknown_status', 'author_supplied'), ('different_url', 'author_supplied'),
    ('different_quote', 'author_supplied'), ('denied', 'author_supplied'),
    ('url_only', 'author_supplied'), ('later_fetch', 'author_supplied'),
    ('note', 'author_supplied'), ('provider_custom_result', 'author_supplied'),
])
def test_evidence_receipt_requires_prior_paired_fetch_and_exact_cited_excerpt(system, mode, expected):
    from hyprn_mvp_app.assistant import research

    app, owner, provider, store, actor, sid = system
    url = 'https://example.org/reference'
    excerpt = 'This is a synthetic quotation for a provenance test.'
    provider.tool = ('add_evidence', dict(title='Synthetic reference',
        source_excerpt=dict(excerpt=excerpt, source_reference=url,
            location='Section 1', explanation='Authored interpretation, not verified truth.'),
        citations=[url], scope={'kind': 'study'}))
    if mode == 'note':
        provider.tool[1].pop('source_excerpt')
        provider.tool[1]['note'] = 'A human-authored assumption is usable without a fetch.'
    original_send = provider.send

    def fetch_events():
        call = provider.event('agent.tool_use', name='web_search' if mode == 'search' else 'web_fetch',
            input={'url': url + '/other' if mode == 'different_url' else url},
            evaluated_permission='deny' if mode == 'denied' else 'allow')
        text = 'Different text.' if mode == 'different_quote' else 'Introduction. ' + excerpt
        content = [{'type': 'text', 'text': text}]
        if mode == 'document':
            content = [{'type': 'document', 'source': {
                'type': 'text', 'media_type': 'text/plain', 'data': text}}]
        if mode == 'url_only':
            content = [{'type': 'document', 'source': {'type': 'url', 'url': url}}]
        if mode == 'failed':
            content = [{'type': 'text', 'text': 'url_not_allowed: ' + excerpt}]
        provider.event('user.custom_tool_result' if mode == 'provider_custom_result'
                       else 'agent.tool_result', tool_use_id=call['id'],
                       content=content, is_error=None if mode == 'unknown_status'
                       else mode == 'failed')

    async def with_fetch(session, event):
        if mode != 'later_fetch':
            fetch_events()
        result = await original_send(session, event)
        if mode == 'later_fetch':
            fetch_events()
        return result

    provider.send = with_fetch

    async def exercise():
        client = await client_for(app)
        base = '/api/1/studies/' + sid
        assert (await client.post(base + '/assistant/messages', json={
            'command_id': uid(), 'text': 'Save the reference.'})).status_code == 202
        await drained(owner)
        assert provider.results[0]['ok'], provider.results
        version = provider.results[0]['content']['id']
        response = await client.get(base + '/evidence/' + version + '/source-inspection')
        assert response.status_code == 200, response.text
        result = response.json()['data']
        assert result == research.read(store, actor, sid, version)
        assert result['basis'] == expected
        saved = store.evidence_version(actor, sid, version)
        assert saved['source_refs'] == [url]
        if expected == 'retrieved_excerpt':
            assert result['retrieval']['source_url'] == url
            assert len(result['retrieval']['excerpt_sha256']) == 64
            assert result['retrieval']['observed_at'].endswith('+00:00')
            assert 'Authored interpretation' in saved['content']
            # The public projection leaks neither source bytes nor provider IDs.
            assert excerpt not in json.dumps(result) and 'event_' not in json.dumps(result)
        else:
            assert result['retrieval'] is None
        if mode == 'fetched':
            provider.tool = ('revise_evidence', dict(evidence_id=saved['evidence_id'],
                expected_revision=version, source_excerpt=dict(
                    excerpt='A different author assertion not returned by the fetch.',
                    source_reference=url, location='Section 2',
                    explanation='This revision must not inherit its predecessor receipt.')))
            assert (await client.post(base + '/assistant/messages', json={
                'command_id': uid(), 'text': 'Revise the reference.'})).status_code == 202
            await drained(owner)
            assert provider.results[-1]['ok'], provider.results[-1]
            revised = provider.results[-1]['content']['id']
            assert revised != version
            assert research.read(store, actor, sid, revised)['basis'] == 'author_supplied'
            assert research.read(store, actor, sid, version) == result
        other = store.create_study(actor, uid(), 'Other study')['study_id']
        with pytest.raises(DomainError) as refused:
            research.read(store, actor, other, version)
        assert refused.value.status == 404
        response = await client.get('/api/1/studies/' + other + '/evidence/'
                                    + version + '/source-inspection')
        assert response.status_code == 404
        outsider = uid()
        with store.connection(write=True) as db:
            db.execute('INSERT INTO users(actor_id,username,password_hash) VALUES(?,?,?)',
                       (outsider, 'outsider', 'synthetic-unused-hash'))
        with pytest.raises(DomainError):
            research.read(store, outsider, sid, version)
        await client.aclose()
        await owner.close()

    asyncio.run(exercise())


def test_provider_cannot_supply_internal_provenance_or_reviewer_receipts(system):
    app, owner, provider, store, actor, sid = system

    async def exercise():
        client = await client_for(app)
        provider.event('hyprn.evidence_source', evidence_version_id=uid(), retrieval={})
        response = await client.post('/api/1/studies/' + sid + '/assistant/messages', json={
            'command_id': uid(), 'text': 'Read the study.'})
        assert response.status_code == 202
        await drained(owner)
        with store.connection() as db:
            assert records.event(db, sid, 'event_0') is None
        assert not provider.results
        await client.aclose()
        await owner.close()

    asyncio.run(exercise())


class UpgradingProvider(Provider):
    def __init__(self):
        super().__init__()
        self.bindings = []
        self.correlations = {}
        self.event_sessions = {}
        self.current = None
        self.costs = {}
        self.states = {}
        self.unknown_create = False
        self.result_gate = None
        self.result_started = None

    async def create_session(self, settings, correlation):
        self.created.append(correlation)
        self.bindings.append((settings.agent_id, settings.agent_version, settings.environment_id))
        session = 'session_generation_' + str(len(self.created))
        self.correlations[correlation] = session
        if self.unknown_create:
            self.unknown_create = False
            raise ProviderError('provider_unavailable', uncertain=True)
        return {'id': session}

    async def find_session(self, correlation):
        session = self.correlations.get(correlation)
        return {'id': session} if session else None

    async def session_account(self, session):
        return dict(status=self.states.get(session, 'idle'), spent_cents=self.costs.get(session, 0))

    def event(self, kind, **fields):
        result = super().event(kind, **fields)
        self.event_sessions[result['id']] = self.current
        return result

    async def send(self, session, event):
        self.current = session
        return await super().send(session, event)

    async def events(self, session, since=None):
        for event in list(self.history):
            if self.event_sessions[event['id']] == session:
                yield dict(event)

    async def tool_result(self, session, event_id, content, is_error=False):
        self.current = session
        if self.result_gate:
            self.result_started.set()
            await self.result_gate.wait()
        return await super().tool_result(session, event_id, content, is_error)


def test_definition_upgrade_retains_conversation_history_and_all_user_spending(system):
    from hyprn_mvp_app.assistant import provider_sessions
    app, owner, _, store, actor, sid = system
    provider = owner.provider = UpgradingProvider()

    async def exercise():
        client = await client_for(app)
        base = '/api/1/studies/' + sid + '/assistant'
        assert (await client.post(base + '/messages', json=dict(
            command_id=uid(), text='Read my study first.'))).status_code == 202
        await drained(owner)
        before = (await client.get(base)).json()['data']
        conversation_id = owner._load(sid)[0]['conversation_id']
        provider.costs['session_generation_1'] = 1200
        owner.settings = replace(owner.settings, agent_version=2)
        assert (await client.post(base + '/messages', json=dict(
            command_id=uid(), text='Continue with the saved work.'))).status_code == 202
        await drained(owner)
        after = (await client.get(base)).json()['data']
        assert owner._load(sid)[0]['conversation_id'] == conversation_id
        assert after['messages'][:len(before['messages'])] == before['messages']
        assert provider.bindings == [('agent_test', 1, 'env_test'), ('agent_test', 2, 'env_test')]
        assert len(set(provider.created)) == 2 and len(provider.sent) == 2
        assert 'untrusted historical context' in provider.sent[1]['content'][0]['text']
        assert 'Read my study first.' in provider.sent[1]['content'][0]['text']
        assert sid in provider.sent[1]['content'][0]['text']
        with store.connection() as db:
            generations = db.execute('SELECT * FROM assistant_provider_sessions '
                                    'WHERE study_id=? ORDER BY generation', (sid,)).fetchall()
        assert [row['provider_id'] for row in generations] == [
            'session_generation_1', 'session_generation_2']
        assert all(row['billing_actor'] == actor for row in generations)
        provider.costs['session_generation_2'] = 800
        spending = (await client.get('/api/1/assistant/budget')).json()['data']
        assert spending['spent_cents'] == 2000 and spending['remaining_cents'] == 0
        assert (await client.post(base + '/messages', json=dict(
            command_id=uid(), text='This must not incur another model request.'))).status_code == 202
        await drained(owner)
        assert len(provider.sent) == 2 and len(provider.created) == 2
        assert (await client.get(base)).json()['data']['state'] == 'blocked'
        await client.aclose()
        await owner.close()

    asyncio.run(exercise())


def test_new_definition_waits_for_accepted_turn_without_replaying_its_tool(system):
    from hyprn_mvp_app.assistant import provider_sessions
    app, owner, _, store, actor, sid = system
    provider = owner.provider = UpgradingProvider()
    owner._reviewer_pins = {('agent_old_reviewer', 1): 'source-reviewer'}

    async def exercise():
        client = await client_for(app)
        base = '/api/1/studies/' + sid + '/assistant'
        provider.result_gate, provider.result_started = asyncio.Event(), asyncio.Event()
        await client.post(base + '/messages', json=dict(command_id=uid(), text='Read once.'))
        await asyncio.wait_for(provider.result_started.wait(), 3)
        owner.settings = replace(owner.settings, agent_version=2)
        owner._reviewer_pins = {('agent_new_reviewer', 2): 'source-reviewer'}
        current, turn = owner._load(sid)
        assert turn['delivery'] == 'accepted'
        assert await owner._session(current, owner.settings, turn) == 'session_generation_1'
        assert owner.reviewer_policy(sid) == {('agent_old_reviewer', 1): 'source-reviewer'}
        provider.result_gate.set()
        await drained(owner)
        assert len(provider.results) == len(provider.sent) == 1
        provider.result_gate = None
        await client.post(base + '/messages', json=dict(command_id=uid(), text='Continue once.'))
        await drained(owner)
        assert len(provider.results) == len(provider.sent) == len(provider.created) == 2
        assert owner.reviewer_policy(sid) == {('agent_new_reviewer', 2): 'source-reviewer'}
        await client.aclose()
        await owner.close()

    asyncio.run(exercise())


def test_ambiguous_successor_creation_reconciles_the_same_correlation_without_recreating(system):
    app, owner, _, store, actor, sid = system
    provider = owner.provider = UpgradingProvider()

    async def exercise():
        client = await client_for(app)
        base = '/api/1/studies/' + sid + '/assistant'
        await client.post(base + '/messages', json=dict(command_id=uid(), text='First turn.'))
        await drained(owner)
        owner.settings = replace(owner.settings, agent_version=2)
        provider.unknown_create = True
        await client.post(base + '/messages', json=dict(command_id=uid(), text='Next turn.'))
        await drained(owner)
        assert len(provider.created) == 2 and len(provider.sent) == 1
        assert (await client.get(base)).json()['data']['state'] == 'blocked'
        assert (await client.post(base + '/resume', json={})).status_code == 202
        await drained(owner)
        assert len(provider.created) == 2 and len(provider.sent) == 2
        assert len(provider.results) == 2
        await client.aclose()
        await owner.close()

    asyncio.run(exercise())


@pytest.mark.parametrize('obstruction', ['running', 'unresolved_tool', 'unknown_spending'])
def test_successor_refuses_busy_unknown_or_unsettled_previous_session(system, obstruction):
    app, owner, _, store, actor, sid = system
    provider = owner.provider = UpgradingProvider()

    async def exercise():
        client = await client_for(app)
        base = '/api/1/studies/' + sid + '/assistant'
        await client.post(base + '/messages', json=dict(command_id=uid(), text='Initial turn.'))
        await drained(owner)
        owner.settings = replace(owner.settings, agent_version=2)
        if obstruction == 'running':
            provider.states['session_generation_1'] = 'running'
        elif obstruction == 'unresolved_tool':
            with store.connection(write=True) as db:
                db.execute("UPDATE assistant_tool_results SET delivery='uncertain' WHERE study_id=?",
                           (sid,))
        else:
            async def unknown(session):
                raise ProviderError('user_allowance_unknown')
            provider.session_account = unknown
        await client.post(base + '/messages', json=dict(command_id=uid(), text='Upgrade now.'))
        await drained(owner)
        assert len(provider.created) == len(provider.sent) == 1
        with store.connection() as db:
            assert db.execute('SELECT count(*) FROM assistant_provider_sessions '
                              'WHERE study_id=?', (sid,)).fetchone()[0] == 1
        await client.aclose()
        await owner.close()

    asyncio.run(exercise())


def test_large_pdf_result_retains_digest_not_binary_or_quotation(system):
    import base64
    import hashlib
    _, owner, provider, store, actor, sid = system
    command = uid()
    records.accept(store, actor, sid, command, 'Research a reference.', owner.settings)
    _, turn = owner._load(sid)
    owner._open_runtime(turn)
    raw = b'%PDF-1.7\n' + b'x' * 4_780_500
    event = dict(id='large_pdf', type='agent.tool_result', tool_use_id='fetch_pdf',
                 is_error=False, content=[dict(type='document', source=dict(
                     type='base64', media_type='application/pdf',
                     data=base64.b64encode(raw).decode()))])
    provider.history = [event]
    received = asyncio.run(owner._history(sid, 'session_test', turn))
    assert len(received) == 1 and len(json.dumps(received)) < 2000
    with store.connection() as db:
        retained = records.event(db, sid, 'large_pdf')
    source = retained['content'][0]['source']
    assert source['sha256'] == hashlib.sha256(raw).hexdigest()
    assert source['byte_length'] == len(raw) and source['type'] == 'provider_attachment'
    assert 'data' not in source and len(json.dumps(retained)) < 2000
    from hyprn_mvp_app.assistant.research import _texts
    assert list(_texts(retained)) == []


@pytest.mark.parametrize('uncertain,missing', [(False, False), (True, False), (True, True)])
def test_public_resume_wakes_interrupted_provider_once_without_replaying_tools(system,
                                                                              uncertain, missing):
    app, owner, provider, store, actor, sid = system
    async def exercise():
        client = await client_for(app)
        base = '/api/1/studies/' + sid + '/assistant'
        command = uid()
        # Retained old-release failure: original message accepted and tool completed.
        records.accept(store, actor, sid, command, 'Research and finish.', owner.settings)
        current, turn = owner._load(sid)
        owner._open_runtime(turn)
        original = provider.event('user.message', content=[dict(type='text', text='Research.')])
        completed = provider.event('agent.custom_tool_use', name='add_evidence', input={})
        provider.event('user.custom_tool_result', custom_tool_use_id=completed['id'])
        provider.event('user.interrupt')
        provider.event('session.status_idle', stop_reason={'type': 'end_turn'})
        with store.connection(write=True) as db:
            db.execute("UPDATE assistant_turns SET delivery='accepted',provider_event=? "
                       'WHERE turn_id=?', (original['id'], command))
            db.execute('INSERT INTO assistant_tool_results VALUES(?,?,?,?,?,?)',
                       (sid, completed['id'], command, '{"ok":true}', 0, 'accepted'))
            records.update(db, sid, provider_id='session_test', provision='accepted',
                           state='blocked', error='provider_response_too_large')
        continuation = []
        async def send(session, event):
            continuation.append(event)
            if not missing:
                echoed = provider.event('user.message', content=event['content'])
                provider.event('agent.message', content=[dict(type='text', text='Continued.')])
                provider.event('session.status_idle', stop_reason={'type': 'end_turn'})
            if uncertain:
                raise ProviderError('provider_unavailable', uncertain=True)
            return {'data': [echoed]}
        provider.send = send
        assert owner.read(actor, sid)['can_resume']
        assert (await client.post(base + '/resume', json={})).status_code == 202
        await drained(owner)
        assert len(continuation) == 1 and not provider.results
        if missing:
            assert owner.read(actor, sid)['error'] == 'provider_resume_delivery_unknown'
            assert (await client.post(base + '/resume', json={})).status_code == 202
            await drained(owner)
            assert len(continuation) == 1
        else:
            result = owner.read(actor, sid)
            assert result['state'] == 'idle' and result['messages'][-1]['text'] == 'Continued.'
            assert [m['text'] for m in result['messages'] if m['role'] == 'user'] == [
                'Research and finish.']
            assert len(provider.created) == 0
        await client.aclose()
        await owner.close()
    asyncio.run(exercise())


def test_stop_after_unreadable_attachment_starts_at_new_interrupt_receipt(system):
    _, owner, provider, store, actor, sid = system
    async def exercise():
        command = uid()
        records.accept(store, actor, sid, command, 'Read document.', owner.settings)
        _, turn = owner._load(sid)
        owner._open_runtime(turn)
        with store.connection(write=True) as db:
            records.update(db, sid, provider_id='session_test', provision='accepted',
                           state='blocked', error='provider_attachment_too_large',
                           provider_cursor='2026-10-20T10:00:00Z')
        stamp = '2026-10-20T10:01:00Z'
        stopped = dict(id='interrupt_new', type='user.interrupt', created_at=stamp,
                       processed_at=stamp)
        async def interrupt(session):
            return {'data': [stopped]}
        async def events(session, since=None):
            assert since == stamp  # Reading from the old cursor would re-hit the bad attachment.
            yield stopped
        provider.interrupt, provider.events = interrupt, events
        owner.stop(actor, sid)
        await drained(owner)
        page = owner.read(actor, sid)
        assert page['state'] == 'idle' and page['can_send']
        assert not provider.sent and not provider.results
        await owner.close()
    asyncio.run(exercise())


def test_old_interruption_does_not_wake_a_successfully_continued_turn_again(system):
    _, owner, provider, store, actor, sid = system
    async def exercise():
        command = uid()
        records.accept(store, actor, sid, command, 'Finish existing work.', owner.settings)
        _, turn = owner._load(sid)
        owner._open_runtime(turn)
        original = provider.event('user.message', content=[])
        continuation = provider.event('user.message', content=[])
        provider.event('session.status_idle', stop_reason={'type': 'end_turn'})
        with store.connection(write=True) as db:
            db.execute("UPDATE assistant_turns SET delivery='accepted',provider_event=? "
                       'WHERE turn_id=?', (original['id'], command))
            records.save_event(db, sid, dict(id='old_interrupt', type='hyprn.provider_interrupted',
                turn_id=command, _received_at=1))
            records.save_event(db, sid, dict(id='old_continue',
                type='hyprn.provider_continue_accepted', turn_id=command, intent_id='old_intent',
                original_event=original['id'], provider_event=continuation['id'], _received_at=2))
            records.update(db, sid, provider_id='session_test', provision='accepted',
                           state='blocked', error='assistant_internal_error')
        owner.resume(actor, sid)
        await drained(owner)
        assert owner.read(actor, sid)['state'] == 'idle'
        assert not provider.sent
        await owner.close()
    asyncio.run(exercise())


def test_activity_projection_is_bounded_turn_scoped_and_excludes_provider_content(system):
    app, owner, provider, store, actor, sid = system
    command = uid()
    records.accept(store, actor, sid, command, 'Read the current study.', owner.settings)
    with store.connection(write=True) as db:
        records.save_event(db, sid, dict(id='current-message', type='user.message',
            _received_at=1, content=[]))
        db.execute('UPDATE assistant_turns SET provider_event=? WHERE turn_id=?',
                   ('current-message', command))
        for index in range(43):
            records.save_event(db, sid, dict(id=f'tool-{index}', type='agent.custom_tool_use',
                name='get_study_overview', input={'secret': 'private argument'},
                _received_at=2 + index))
            db.execute('INSERT INTO assistant_tool_results VALUES(?,?,?,?,?,?)',
                (sid, f'tool-{index}', command, 'private result', index == 40,
                 'waiting' if index == 42 else 'accepted'))
            if index != 42:
                records.save_event(db, sid, dict(id=f'result-{index}',
                    type='user.custom_tool_result', custom_tool_use_id=f'tool-{index}',
                    content='private provider result', _received_at=2.5 + index))
        records.save_event(db, sid, dict(id='thinking', type='agent.thinking',
            thinking='private thought', _received_at=45))
        records.save_event(db, sid, dict(id='fetch', type='agent.tool_use', name='web_fetch',
            input={'url': 'https://private.invalid'}, session_thread_id='private-thread',
            _received_at=46))
        records.save_event(db, sid, dict(id='fetch-result', type='agent.tool_result',
            tool_use_id='fetch', is_error=True, content='private document', _received_at=47))
        records.save_event(db, sid, dict(id='unknown', type='agent.tool_use',
            name='secret provider name', _received_at=48))

    async def exercise():
        client = await client_for(app)
        reply = await client.get(f'/api/1/studies/{sid}/assistant')
        assert reply.status_code == 200
        activity = reply.json()['data']['activity']
        assert activity['has_earlier_steps'] is True
        assert len(activity['steps']) == 40
        assert [s['state'] for s in activity['steps'][-5:]] == [
            'failed', 'completed', 'waiting', 'failed', 'running']
        assert activity['steps'][-2]['label'] == 'Read source'
        assert activity['steps'][-2]['actor'] == 'reviewer'
        assert activity['steps'][-2]['finished_at'] == 47
        assert activity['steps'][-1]['label'] == 'Research tool'
        assert activity['steps'][-1]['finished_at'] is None
        assert 'private' not in json.dumps(activity)
        assert 'secret' not in json.dumps(activity)
        assert 'thinking' not in json.dumps(activity)
        with store.connection(write=True) as db:
            records.update(db, sid, active_turn=None, state='idle')
        reply = await client.get(f'/api/1/studies/{sid}/assistant')
        assert reply.json()['data']['activity'] == {'steps': [], 'has_earlier_steps': False}
        records.accept(store, actor, sid, uid(), 'A different request.', owner.settings)
        reply = await client.get(f'/api/1/studies/{sid}/assistant')
        assert reply.json()['data']['activity']['steps'] == []
        await client.aclose()
        await owner.close()

    asyncio.run(exercise())


def test_activity_never_treats_an_unconfirmed_tool_result_as_success(system):
    app, owner, provider, store, actor, sid = system
    command = uid()
    records.accept(store, actor, sid, command, 'Read sources.', owner.settings)
    with store.connection(write=True) as db:
        records.save_event(db, sid, dict(id='message', type='user.message',
            _received_at=1, content=[]))
        db.execute('UPDATE assistant_turns SET provider_event=? WHERE turn_id=?', ('message', command))
        for index, flag in enumerate((False, None)):
            records.save_event(db, sid, dict(id=f'fetch-{index}', type='agent.tool_use',
                name='web_fetch', _received_at=2))
            records.save_event(db, sid, dict(id=f'result-{index}', type='agent.tool_result',
                tool_use_id=f'fetch-{index}', is_error=flag, _received_at=3))
        records.save_event(db, sid, dict(id='uncertain', type='agent.custom_tool_use',
            name='submit_runs', _received_at=4))
        db.execute('INSERT INTO assistant_tool_results VALUES(?,?,?,?,?,?)',
                   (sid, 'uncertain', command, None, 0, 'uncertain'))
    activity = owner.read(actor, sid)['activity']
    assert [s['state'] for s in activity['steps']] == ['completed', 'returned', 'uncertain']
    assert activity['steps'][-1]['finished_at'] is None


def test_user_specific_limit_preserves_spending_and_other_users_default(system):
    from dataclasses import replace
    from hyprn_mvp_app.assistant import allowance
    app, owner, provider, store, actor, sid = system
    owner.settings = replace(owner.settings, user_limits_cents={actor: 4900})
    async def exercise():
        owner.send(actor, sid, uid(), 'Read.')
        await drained(owner)
        provider.cost = 2003
        client = await client_for(app)
        budget = (await client.get('/api/1/assistant/budget')).json()['data']
        assert budget['limit_cents'] == 4900
        assert budget['spent_cents'] == 2003 and budget['remaining_cents'] == 2897
        assert allowance.limit(uid(), owner.settings) == 2000
        assert (await allowance.check(store, provider, actor, owner.settings))[0] == 2003
        provider.cost = 4900
        with pytest.raises(ProviderError, match='user_allowance_exhausted'):
            await allowance.check(store, provider, actor, owner.settings)
        await client.aclose()
        await owner.close()
    asyncio.run(exercise())


def test_allowance_increase_requires_explicit_resume_and_rechecks_actual_spending(system):
    _, owner, provider, store, actor, sid = system
    other = store.create_study(actor, uid(), 'Existing spending')['study_id']
    async def exercise():
        records.accept(store, actor, other, uid(), 'Completed turn.', owner.settings)
        with store.connection(write=True) as db:
            records.update(db, other, provider_id='session_spent', provision='accepted',
                           state='idle', active_turn=None)
        provider.cost = 2003
        command = uid()
        owner.send(actor, sid, command, 'Retained request.')
        await drained(owner)
        assert owner.read(actor, sid)['can_resume']
        owner.resume(actor, sid)
        await drained(owner)
        assert owner.read(actor, sid)['error'] == 'user_allowance_exhausted'
        assert not provider.sent
        owner.settings = replace(owner.settings, user_limits_cents={actor: 4900})
        await owner.start()
        assert not owner._tasks and not provider.sent
        owner.resume(actor, sid)
        await drained(owner)
        assert len(provider.sent) == 1
        assert owner.read(actor, sid)['state'] == 'idle'
        with store.connection() as db:
            assert records.turn(db, command)['delivery'] == 'accepted'
        await owner.close()
    asyncio.run(exercise())
