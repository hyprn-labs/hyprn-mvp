"""Durable study conversation; Claude owns reasoning, Runtime owns every scientific effect.

The delivery pump forwards events only. It never plans scientific work, schedules runs,
chooses tools or retries scientific effects. Provider mutations are recorded before sending.
Interrupted local dispatch is uncertain; it is never replayed on process recovery.
"""

import asyncio
import json
import time

from ..agent_runtime import control
from ..agent_runtime.delegations import ROLE_EFFECTS, ceiling_for
from ..agent_runtime.sessions import SessionRefused
from ..agent_tools.registry import LOCAL_STAGE
from ..contracts import DomainError, canonical, digest
from . import records, allowance
from .budget import Budget
from .claude import ProviderError, identity

SURFACE = 'claude_managed'
DISPLAY_NAME = 'Assistant'
MAX_TURN_SECONDS = 3600


def message_event(turn):
    return {
        'type': 'user.message',
        'content': [
            {'type': 'text', 'text': turn['text']},
            {'type': 'text', 'text': 'HYPRN request reference: ' + turn['turn_id']},
        ],
    }


class Conversations:
    def __init__(self, store, runtime, provider, settings):
        self.store, self.runtime = store, runtime
        self.provider, self.settings = provider, settings
        self._tasks = {}
        self._closing = False
        self.budget = Budget(store)
        self._allowance_admission = asyncio.Lock()

    def available(self):
        if not self.settings or not control.agent_enabled(self.runtime.environ):
            return False
        definitions = self.runtime.registry.definitions(
            SURFACE, LOCAL_STAGE, ROLE_EFFECTS['writer']
        )
        return digest(definitions) == self.settings.definitions_sha256

    def read(self, actor, study):
        return records.public(self.store, actor, study, available=self.available())

    def send(self, actor, study, command, text):
        if not self.available():
            raise DomainError('backend_unavailable', 503)
        records.accept(self.store, actor, study, command, text, self.settings)
        self.wake(study)
        return self.read(actor, study)

    def wake(self, study):
        if self._closing or study in self._tasks:
            return
        task = asyncio.create_task(self._pump(study))
        self._tasks[study] = task
        task.add_done_callback(lambda _: self._finished(study))

    def _finished(self, study):
        self._tasks.pop(study, None)
        if self._closing:
            return
        with self.store.background_actor('assistant', study) as admitted:
            if admitted:
                self._continue(study)

    def _continue(self, study):
        current, turn = self._load(study)
        if turn and current['state'] in ('queued', 'starting', 'running', 'waiting', 'stopping'):
            self.wake(study)

    async def start(self):
        if hasattr(self.store, 'database'):
            if self.available():
                for job in self.store.background_jobs('assistant'):
                    self.wake(job['study_id'])
            return
        with self.store.connection() as db:
            studies = [
                r[0]
                for r in db.execute(
                    "SELECT c.study_id FROM assistant_conversations c JOIN assistant_turns t "
                    "ON t.turn_id=c.active_turn ORDER BY (t.delivery='new'),t.created_at"
                )
            ]
        for study in studies:
            self.wake(study)

    async def close(self):
        self._closing = True
        tasks = list(self._tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await self.runtime.aclose()
        if self.provider:
            await self.provider.close()

    def stop(self, actor, study):
        """Fence admission synchronously before any remote request can be awaited."""
        with self.store.connection(write=True) as db:
            self.store.authorize(db, actor, study)
            current = records.row(db, study)
            if current and current['active_turn']:
                db.execute(
                    'UPDATE assistant_turns SET stopped=1 WHERE turn_id=?',
                    (current['active_turn'],),
                )
                turn = records.turn(db, current['active_turn'])
                if (current['state'] == 'queued' and turn['delivery'] == 'new'
                        and not turn['runtime_session'] and current['provision'] != 'intended'):
                    records.update(db, study, state='idle', active_turn=None, error=None)
                else:
                    records.update(db, study, state='stopping')
        if current and current['active_turn']:
            self.wake(study)
        return self.read(actor, study)

    def _load(self, study):
        with self.store.connection() as db:
            current = records.row(db, study)
            active = (
                records.turn(db, current['active_turn'])
                if current and current['active_turn']
                else None
            )
            return current, active

    def _update(self, study, **values):
        with self.store.connection(write=True) as db:
            records.update(db, study, **values)

    def _authorize(self, turn):
        if not self.available():
            raise ProviderError('assistant_disabled')
        with self.store.connection() as db:
            self.store.authorize(db, turn['actor_id'], turn['study_id'])
        if turn['runtime_session']:
            session = self.runtime.sessions.get(turn['runtime_session'])
            self.runtime.sessions.live(session['session_id'], session['delegation_id'])

    def _open_runtime(self, turn):
        with self.store.connection(write=True) as db:
            ceiling = ceiling_for(self.store, db, turn['actor_id'], turn['study_id'])
            agent = self.store.ensure_agent_actor(db, turn['actor_id'], SURFACE, DISPLAY_NAME)
            grant = self.store.create_delegation(
                db,
                agent,
                turn['study_id'],
                ceiling,
                ROLE_EFFECTS[ceiling],
                time.time() + MAX_TURN_SECONDS,
            )
        handle = self.runtime.open_session(
            grant,
            {'name': 'hyprn-claude-managed'},
            surface=SURFACE,
        )
        with self.store.connection(write=True) as db:
            db.execute(
                'UPDATE assistant_turns SET runtime_session=? WHERE turn_id=?',
                (handle.session_id, turn['turn_id']),
            )
        turn['runtime_session'] = handle.session_id

    async def _session(self, current, settings):
        if current['provider_id']:
            return current['provider_id']
        study = current['study_id']
        with self.store.connection(write=True) as db:
            claimed = db.execute(
                "UPDATE assistant_conversations SET provision='intended' "
                "WHERE study_id=? AND provision='new' AND provider_id IS NULL",
                (study,),
            ).rowcount
        if not claimed:
            found = await self.provider.find_session(current['conversation_id'])
            if not found:
                raise ProviderError('session_delivery_unknown', uncertain=True)
        else:
            found = await self.provider.create_session(settings, current['conversation_id'])
        provider_id = identity(found.get('id'))
        self._update(study, provider_id=provider_id, provision='accepted')
        return provider_id

    def _events(self, study):
        with self.store.connection() as db:
            return records.events(db, study)

    def _receive_event(self, study, turn, event):
        self._authorize(turn)
        identity(event.get('id'))
        if len(canonical(event)) > 1024 * 1024:
            raise ProviderError('provider_response_too_large')
        event['_received_at'] = time.time()
        with self.store.connection(write=True) as db:
            records.save_event(db, study, event)

    async def _history(self, study, provider_id, turn):
        # Database I/O must not block HTTP serving during a page of provider events.
        # to_thread preserves the study actor scope; each event still rechecks access.
        previous = await asyncio.to_thread(self._events, study)
        timestamps = [e['processed_at'] for e in previous if e.get('processed_at')]
        since = max(timestamps) if timestamps else None
        async for event in self.provider.events(provider_id, since):
            await asyncio.to_thread(self._receive_event, study, turn, event)
        return await asyncio.to_thread(self._events, study)

    async def _deliver(self, study, turn, provider_id):
        event = message_event(turn)
        with self.store.connection(write=True) as db:
            claimed = db.execute(
                "UPDATE assistant_turns SET delivery='intended' "
                "WHERE turn_id=? AND delivery='new' AND stopped=0",
                (turn['turn_id'],),
            ).rowcount
        if not claimed:
            history = await self._history(study, provider_id, turn)
            found = [
                e
                for e in history
                if e.get('type') == 'user.message' and e.get('content') == event['content']
            ]
            if len(found) != 1:
                raise ProviderError('message_delivery_unknown', uncertain=True)
            provider_event = found[0]['id']
        else:
            result = await self.provider.send(provider_id, event)
            sent = result.get('data', result.get('events', []))
            if not sent:
                raise ProviderError('message_delivery_unknown', uncertain=True)
            provider_event = identity(sent[0].get('id'))
        with self.store.connection(write=True) as db:
            db.execute(
                "UPDATE assistant_turns SET delivery='accepted',provider_event=? WHERE turn_id=?",
                (provider_event, turn['turn_id']),
            )
        turn['provider_event'] = provider_event

    def _saved_tool(self, study, event_id):
        with self.store.connection() as db:
            return db.execute(
                'SELECT * FROM assistant_tool_results WHERE study_id=? AND event_id=?',
                (study, event_id),
            ).fetchone()

    def _intend_tool(self, study, turn, event_id):
        self._authorize(turn)
        _, latest = self._load(study)
        if latest['stopped']:
            return False
        with self.store.connection(write=True) as db:
            db.execute(
                'INSERT INTO assistant_tool_results VALUES(?,?,?,?,?,?)',
                (study, event_id, turn['turn_id'], None, 0, 'intended'),
            )
        return True

    def _retain_tool(self, study, turn, event_id, content, is_error):
        self._authorize(turn)
        with self.store.connection(write=True) as db:
            db.execute(
                'UPDATE assistant_tool_results SET content=?,is_error=?,delivery=? '
                'WHERE study_id=? AND event_id=?',
                (content, int(is_error), 'ready', study, event_id),
            )

    def _tool_delivery_allowed(self, study, turn):
        self._authorize(turn)
        _, latest = self._load(study)
        return not latest['stopped']

    def _accept_tool_result(self, study, event_id):
        with self.store.connection(write=True) as db:
            db.execute(
                "UPDATE assistant_tool_results SET delivery='accepted' "
                'WHERE study_id=? AND event_id=?',
                (study, event_id),
            )

    async def _tool(self, study, turn, provider_id, event, history):
        event_id = event['id']
        saved = await asyncio.to_thread(self._saved_tool, study, event_id)
        if saved and saved['delivery'] == 'accepted':
            return
        if saved and saved['content'] is None:
            # The process stopped across a runtime call. Its action journal is authoritative.
            # Never invoke again merely because this surface did not retain the response.
            raise ProviderError('tool_outcome_unknown', uncertain=True)
        if not saved:
            # Child tool calls are cross-posted in this session's event stream.
            # They use the same current human delegation and Stop fence as the parent.
            if event.get('session_thread_id') is not None:
                identity(event['session_thread_id'])
            if not await asyncio.to_thread(self._intend_tool, study, turn, event_id):
                return
            if event.get('name') == 'wait_for_runs':
                self._update(study, state='waiting')
            outcome = await self.runtime.call_tool(
                turn['runtime_session'], event_id, event.get('name'), event.get('input')
            )
            _, latest = self._load(study)
            if latest and not latest['stopped']:
                self._update(study, state='running')
            content = canonical(
                dict(
                    ok=outcome.ok,
                    content=outcome.content,
                    action_id=outcome.action_id,
                    state=outcome.state,
                )
            ).decode()
            await asyncio.to_thread(
                self._retain_tool, study, turn, event_id, content, not outcome.ok)
            saved = dict(content=content, is_error=not outcome.ok, delivery='ready')
        if not await asyncio.to_thread(self._tool_delivery_allowed, study, turn):
            return
        acknowledged = any(
            e.get('type') == 'user.custom_tool_result' and e.get('custom_tool_use_id') == event_id
            for e in history
        )
        if not acknowledged:
            # Provider contract deduplicates custom results by the original tool-use ID.
            await self.provider.tool_result(
                provider_id, event_id, saved['content'], is_error=bool(saved['is_error'])
            )
        await asyncio.to_thread(self._accept_tool_result, study, event_id)

    async def _pump(self, study):
        with self.store.background_actor('assistant', study) as admitted:
            if admitted:
                await self._funded_pump(study)

    async def _admit(self, study):
        while True:
            async with self._allowance_admission:
                current, turn = self._load(study)
                if not turn or turn['stopped']:
                    return None
                self._authorize(turn)
                try:
                    settings = await allowance.prepare(
                        self.store, self.provider, self.settings, current, turn,
                        renewing=turn['delivery'] != 'new')
                except ProviderError as error:
                    if error.code != 'shared_allowance_busy':
                        raise
                    self._update(study, state='queued', error=None)
                else:
                    # Stop can be admitted during provider accounting reads.
                    _, latest = self._load(study)
                    if not latest or latest['stopped']:
                        return None
                    self._update(study, state='starting', error=None)
                    provider_id = await self._session(current, settings)
                    _, latest = self._load(study)
                    if not latest or latest['stopped']:
                        return provider_id
                    await self.provider.ensure_allowance(
                        provider_id, settings.session_cents,
                        continuing=turn['delivery'] != 'new')
                    return provider_id
            await asyncio.sleep(1)

    def _started_at(self, study, turn):
        event_id = 'turn_started_' + turn['turn_id']
        with self.store.connection(write=True) as db:
            found = next((e for e in records.events(db, study) if e['id'] == event_id), None)
            if found:
                return found['_received_at']
            started = time.time() if turn['delivery'] == 'new' else turn['created_at']
            records.save_event(db, study, dict(id=event_id, type='hyprn.turn_started',
                                              _received_at=started))
            return started

    async def _renew(self, study, turn, provider_id):
        async with self._allowance_admission:
            current, latest = self._load(study)
            if not latest or latest['stopped']:
                return
            self._authorize(latest)
            settings = await allowance.prepare(
                self.store, self.provider, self.settings, current, latest, renewing=True)
            _, latest = self._load(study)
            if latest and not latest['stopped']:
                await self.provider.ensure_allowance(
                    provider_id, settings.session_cents, continuing=True)

    async def _funded_pump(self, study):
        provider_id = None
        try:
            current, turn = self._load(study)
            if not turn:
                return
            if turn['stopped'] and current['provider_id']:
                await self._stop_remote(study, turn, current['provider_id'])
                return
            self._authorize(turn)
            if turn['stopped'] and not current['provider_id']:
                if current['provision'] != 'new':
                    raise ProviderError('session_delivery_unknown', uncertain=True)
                self._update(study, state='idle', active_turn=None)
                return
            provider_id = await self._admit(study)
            current, turn = self._load(study)
            if not turn:
                return
            if turn['stopped']:
                if provider_id:
                    await self._stop_remote(study, turn, provider_id)
                else:
                    self._update(study, state='idle', active_turn=None)
                return
            started_at = self._started_at(study, turn)
            if not turn['runtime_session']:
                self._open_runtime(turn)
            if turn['delivery'] == 'new':
                await self.provider.ensure_tools(provider_id, self.runtime.registry.definitions(
                    SURFACE, LOCAL_STAGE, ROLE_EFFECTS['writer']))
            _, turn = self._load(study)
            if not turn['stopped']:
                await self._deliver(study, turn, provider_id)
                self._update(study, state='running', error=None)
            renewed_at = time.monotonic()
            while True:
                _, turn = self._load(study)
                if turn['stopped']:
                    await self._stop_remote(study, turn, provider_id)
                    return
                self._authorize(turn)
                if time.time() - started_at > MAX_TURN_SECONDS:
                    raise ProviderError('turn_time_limit')
                if time.monotonic() - renewed_at >= 15:
                    try:
                        await self._renew(study, turn, provider_id)
                    except ProviderError as error:
                        if error.code != 'shared_allowance_busy':
                            raise
                    renewed_at = time.monotonic()
                history = await self._history(study, provider_id, turn)
                self._authorize(turn)
                start = next(
                    (i for i, e in enumerate(history) if e['id'] == turn['provider_event']), None
                )
                relevant = history[start + 1 :] if start is not None else []
                for event in relevant:
                    if event.get('type') == 'agent.custom_tool_use' and not turn['stopped']:
                        await self._tool(study, turn, provider_id, event, history)
                idle = next(
                    (e for e in reversed(relevant)
                     if e.get('type') in ('session.status_idle', 'session.status_running')), None
                )
                if (idle and idle['type'] == 'session.status_idle'
                        and idle.get('stop_reason', {}).get('type') != 'requires_action'):
                    reason = idle.get('stop_reason', {}).get('type')
                    if reason == 'budget_reached':
                        # Renew only this admitted turn. Never resend its message/tools.
                        self._update(study, state='queued')
                        await self._admit(study)
                        self._update(study, state='running')
                        await asyncio.sleep(1)
                        continue
                    self.runtime.sessions.end(turn['runtime_session'])
                    self._update(
                        study,
                        state='idle' if reason == 'end_turn' else 'blocked',
                        error=None if reason == 'end_turn' else 'provider_' + str(reason),
                        active_turn=None,
                    )
                    return
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            raise
        except (DomainError, SessionRefused):
            self._update(study, state='blocked', error='access_lost')
            if provider_id:
                try:
                    await self.provider.interrupt(provider_id)
                except ProviderError:
                    pass
        except ProviderError as error:
            self._update(study, state='blocked', error=error.code)
            if provider_id:
                try:
                    await self.provider.interrupt(provider_id)
                except ProviderError:
                    pass
        except Exception:
            # Do not leak provider content or credentials through server exception logs.
            self._update(study, state='blocked', error='assistant_internal_error')

    async def _stop_remote(self, study, turn, provider_id):
        """Stop remains possible after the original delegator loses access.

        Its caller was a current human member. No transcript is delivered and no tool is
        admitted while waiting for this exact interrupt to be processed.
        """
        reply = await self.provider.interrupt(provider_id)
        sent = reply.get('data', reply.get('events', []))
        if not sent:
            raise ProviderError('interrupt_delivery_unknown', uncertain=True)
        interrupt_id = identity(sent[0].get('id'))
        for _ in range(60):
            async for event in self.provider.events(provider_id):
                if event.get('id') == interrupt_id and event.get('processed_at'):
                    if turn['runtime_session']:
                        self.runtime.sessions.end(turn['runtime_session'])
                    self._update(study, state='idle', active_turn=None, error=None)
                    return
            await asyncio.sleep(1)
        raise ProviderError('interrupt_delivery_unknown', uncertain=True)
