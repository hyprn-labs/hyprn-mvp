"""Durable study conversation; Claude owns reasoning, Runtime owns every scientific effect.

The delivery pump forwards events only. It never plans scientific work, schedules runs,
chooses tools or retries scientific effects. Provider mutations are recorded before sending.
Interrupted local dispatch is uncertain; it is never replayed on process recovery.
"""

import asyncio
import json
import logging
import traceback
import time

from ..agent_runtime import control
from ..agent_runtime.delegations import ROLE_EFFECTS, ceiling_for
from ..agent_runtime.sessions import SessionRefused
from ..agent_tools.registry import LOCAL_STAGE
from ..agent_tools.catalogue.exploration import execution_projection
from ..contracts import DomainError, canonical, digest
from . import records, allowance, reviewers, research, provider_sessions
from .budget import Budget
from .claude import ProviderError, identity, retained_event

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
    def __init__(self, store, runtime, provider, settings, *, analysis_reader=None):
        self.store, self.runtime = store, runtime
        self.provider, self.settings = provider, settings
        self._tasks = {}
        self._closing = False
        self.budget = Budget(store)
        self._allowance_admission = asyncio.Lock()
        self._analysis_reader = analysis_reader
        self._reviewer_pins = {}

    def configure_reviewers(self, bindings, limits):
        self._reviewer_pins = reviewers.configured(bindings, limits)

    def available(self):
        if not self.settings or not control.agent_enabled(self.runtime.environ):
            return False
        definitions = self.runtime.registry.definitions(
            SURFACE, LOCAL_STAGE, ROLE_EFFECTS['writer']
        )
        return digest(definitions) == self.settings.definitions_sha256

    def read(self, actor, study, *, after=None, before=None):
        return records.public(self.store, actor, study, available=self.available(),
                              after=after, before=before)

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

    def _restart(self, study):
        _, turn = self._load(study)
        if turn and turn['delivery'] == 'intended':
            # Restart may reconcile a sent message once, never loop on uncertainty.
            self.wake(study)
        else:
            self._continue(study)

    async def start(self):
        if hasattr(self.store, 'database'):
            if self.available():
                for job in self.store.background_jobs('assistant'):
                    with self.store.background_actor('assistant', job['study_id']) as admitted:
                        if admitted:
                            self._restart(job['study_id'])
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
            self._restart(study)

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

    def resume(self, actor, study):
        """Human continuation of the same delivered turn, never a message resend."""
        if not self.available():
            raise DomainError('backend_unavailable', 503)
        with self.store.connection() as db:
            self.store.authorize(db, actor, study)
            current = records.row(db, study)
            if current and current['state'] in ('queued', 'starting', 'running', 'waiting'):
                return self.read(actor, study)
            if not records.may_resume(db, current, actor):
                raise DomainError('conflict', 409)
            turn = records.turn(db, current['active_turn'])
            interrupted = records.latest_event(db, study, ('hyprn.provider_interrupted',),
                                                reference=turn['turn_id'])
            continued = records.latest_event(db, study, ('hyprn.provider_continue_accepted',),
                                              reference=turn['turn_id'])
            needs_wake = interrupted and (not continued or
                interrupted['_received_at'] > continued['_received_at'])
            continue_provider = bool(needs_wake or current['error'] in (
                'provider_response_too_large', 'provider_resume_delivery_unknown'))
            pending = db.execute('SELECT event_id FROM assistant_tool_results '
                'WHERE study_id=? AND turn_id=? AND content IS NULL',
                (study, turn['turn_id'])).fetchall()
            events = {r['event_id']: records.event(db, study, r['event_id']) for r in pending}
        if turn['delivery'] == 'new' and not turn['runtime_session']:
            self._update(study, state='queued', error=None)
            self.wake(study)
            return self.read(actor, study)
        for row in pending:
            tool = self.runtime.registry.tool(events[row['event_id']]['name'])
            if tool.effect != 'read':
                raise DomainError('conflict', 409)
        if turn['runtime_session']:
            self.runtime.sessions.end(turn['runtime_session'])
        self._open_runtime(turn)
        with self.store.connection(write=True) as db:
            records.save_event(db, study, dict(id='resume_'+turn['runtime_session'],
                type='hyprn.turn_resumed', turn_id=turn['turn_id'],
                continue_provider=continue_provider, _received_at=time.time()))
            records.update(db, study, state='queued', error=None)
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

    def authorize_turn(self, turn):
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

    async def _session(self, current, settings, turn=None):
        if turn is None:
            _, turn = self._load(current['study_id'])
        return await provider_sessions.select(self, current, turn, settings)

    def configured_reviewers(self):
        return dict(self._reviewer_pins)

    def reviewer_policy(self, study):
        with self.store.connection() as db:
            return provider_sessions.reviewer_policy(db, study)

    def _pending(self, study, provider_event):
        with self.store.connection() as db:
            continued = records.latest_event(db, study, ('hyprn.provider_continue_accepted',))
            if continued and continued.get('original_event') == provider_event:
                provider_event = continued['provider_event']
            return records.pending_events(db, study, provider_event)

    def _receive_event(self, study, turn, event):
        self.authorize_turn(turn)
        identity(event.get('id'))
        if str(event.get('type', '')).startswith('hyprn.'):
            raise ProviderError('invalid_provider_record')
        event = retained_event(event)
        event['_received_at'] = time.time()
        with self.store.connection(write=True) as db:
            return event if records.save_event(db, study, event) else None

    async def _history(self, study, provider_id, turn):
        # Database I/O must not block HTTP serving during a page of provider events.
        # to_thread preserves the study actor scope; each event still rechecks access.
        current, _ = await asyncio.to_thread(self._load, study)
        since = current['provider_cursor']
        received = []
        async for event in self.provider.events(provider_id, since):
            retained = await asyncio.to_thread(self._receive_event, study, turn, event)
            if retained:
                received.append(retained)
        return received

    async def _deliver(self, study, turn, provider_id):
        if turn['delivery'] == 'accepted':
            return
        event = message_event(turn)
        with self.store.connection() as db:
            context = provider_sessions.handoff(db, study, turn['turn_id'])
        if context:
            event['content'].insert(0, {'type': 'text', 'text': context})
        with self.store.connection(write=True) as db:
            claimed = db.execute(
                "UPDATE assistant_turns SET delivery='intended' "
                "WHERE turn_id=? AND delivery='new' AND stopped=0",
                (turn['turn_id'],),
            ).rowcount
        if not claimed:
            await self._history(study, provider_id, turn)
            with self.store.connection() as db:
                found = [json.loads(r[0]) for r in db.execute(
                    'SELECT payload FROM assistant_events WHERE study_id=? '
                    "AND event_type='user.message' AND reference_id=? LIMIT 2",
                    (study, turn['turn_id']))]
            found = [e for e in found if e.get('content') == event['content']]
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
        self.authorize_turn(turn)
        _, latest = self._load(study)
        if latest['stopped']:
            return False
        with self.store.connection(write=True) as db:
            db.execute(
                'INSERT INTO assistant_tool_results VALUES(?,?,?,?,?,?)',
                (study, event_id, turn['turn_id'], None, 0, 'intended'),
            )
        return True

    def _retain_tool(self, study, turn, event_id, content, is_error, delivery='ready'):
        self.authorize_turn(turn)
        with self.store.connection(write=True) as db:
            db.execute(
                'UPDATE assistant_tool_results SET content=?,is_error=?,delivery=? '
                'WHERE study_id=? AND event_id=?',
                (content, int(is_error), delivery, study, event_id),
            )
            research.retain_evidence(
                self.store, db, turn['actor_id'], study, event_id, content, is_error)

    def _tool_delivery_allowed(self, study, turn):
        self.authorize_turn(turn)
        _, latest = self._load(study)
        return not latest['stopped']

    def _accept_tool_result(self, study, event_id):
        with self.store.connection(write=True) as db:
            db.execute(
                "UPDATE assistant_tool_results SET delivery='accepted' "
                'WHERE study_id=? AND event_id=?',
                (study, event_id),
            )

    def _authorize_wait(self, study, turn):
        """An accepted finite wait outlives expiry, never revocation or current access."""
        if not self.available():
            raise ProviderError('assistant_disabled')
        with self.store.connection() as db:
            self.store.authorize(db, turn['actor_id'], study)
            latest = records.turn(db, turn['turn_id'])
            session = self.runtime.sessions.get(turn['runtime_session'])
            delegation = db.execute('SELECT revoked_at FROM agent_delegations WHERE delegation_id=?',
                                    (session['delegation_id'],)).fetchone() if session else None
            if not delegation or delegation['revoked_at'] is not None or session['state'] == 'access_lost':
                raise SessionRefused('access_lost')
            return not latest['stopped']

    async def _wait_analysis(self, study, turn, event, saved):
        """Retain one monitoring result while the application owner advances exact work.

        No tool is reinvoked and no provider inference is requested during this wait.
        A fresh bounded reasoning lease starts only after a terminal result is retained.
        """
        if self._analysis_reader is None:
            raise ProviderError('assistant_internal_error')
        retained = json.loads(saved['content'])
        version = retained['content']['calculation_version_id']
        if version != event.get('input', {}).get('calculation_version_id'):
            raise ProviderError('invalid_provider_record')
        self._update(study, state='waiting')
        delay, previous = 1.0, None
        checked_at = 0
        while True:
            if not await asyncio.to_thread(self._authorize_wait, study, turn):
                return None
            if time.monotonic() - checked_at >= 30:
                await self._check_spending(study)
                checked_at = time.monotonic()
            value = await asyncio.to_thread(self._analysis_reader, turn['actor_id'], study, version)
            if value is None or value.get('calculation_version_id') != version:
                raise ProviderError('invalid_provider_record')
            if value['state'] not in ('calculating', 'validating'):
                if not await asyncio.to_thread(self._authorize_wait, study, turn):
                    return None
                await self._check_spending(study)
                # Ending the reasoning session never cancels accepted scientific work.
                self.runtime.sessions.end(turn['runtime_session'])
                self._open_runtime(turn)
                retained['content'] = execution_projection(value)
                content = canonical(retained).decode()
                await asyncio.to_thread(self._retain_tool, study, turn, event['id'], content, False)
                with self.store.connection(write=True) as db:
                    records.save_event(db, study, dict(id='resume_'+turn['runtime_session'],
                        type='hyprn.turn_resumed', turn_id=turn['turn_id'], _received_at=time.time()))
                    records.update(db, study, state='running')
                return dict(content=content, is_error=False, delivery='ready')
            await asyncio.to_thread(records.observe_analysis, self.store, study,
                                    turn['turn_id'], event['id'], value)
            progress = (value['state'], value.get('completed_count'), value.get('admission_state'))
            delay = 1.0 if progress != previous else min(30.0, delay * 1.5)
            previous = progress
            await asyncio.sleep(delay)

    async def _tool(self, study, turn, provider_id, event, history):
        event_id = event['id']
        saved = await asyncio.to_thread(self._saved_tool, study, event_id)
        if saved and saved['delivery'] == 'accepted':
            return
        if saved and saved['content'] is None:
            if self.runtime.registry.tool(event.get('name')).effect != 'read':
                raise ProviderError('tool_outcome_unknown', uncertain=True)
        if not saved or saved['content'] is None:
            # Provider-authenticated pinned reviewers have a strictly read-only ceiling.
            child = await reviewers.admit(self, study, turn, provider_id, event)
            if not saved and not await asyncio.to_thread(self._intend_tool, study, turn, event_id):
                return
            if event.get('name') in ('wait_for_runs', 'get_sampling_status', 'get_analysis_execution'):
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
            if child and len(content) > reviewers.LIMITS['max_result_characters']:
                content = canonical(dict(ok=False, content={
                    'error': 'reviewer_result_limit',
                    'message': 'Request a narrower section or fewer records.'},
                    action_id=outcome.action_id, state=outcome.state)).decode()
            waiting = (event.get('name') == 'get_analysis_execution' and outcome.ok
                       and isinstance(outcome.content, dict)
                       and outcome.content.get('state') in ('calculating', 'validating'))
            delivery = 'waiting' if waiting else 'ready'
            await asyncio.to_thread(
                self._retain_tool, study, turn, event_id, content, not json.loads(content)['ok'], delivery)
            saved = dict(content=content, is_error=not json.loads(content)['ok'], delivery=delivery)
        if saved['delivery'] == 'waiting':
            saved = await self._wait_analysis(study, turn, event, saved)
            if saved is None:
                return False
        if not await asyncio.to_thread(self._tool_delivery_allowed, study, turn):
            return
        with self.store.connection() as db:
            acknowledged = records.latest_event(db, study, ('user.custom_tool_result',),
                                                reference=event_id)
        if not acknowledged:
            # Provider contract deduplicates custom results by the original tool-use ID.
            await self.provider.tool_result(
                provider_id, event_id, saved['content'], is_error=bool(saved['is_error'])
            )
        await asyncio.to_thread(self._accept_tool_result, study, event_id)
        return True

    async def _continue_provider(self, study, turn, provider_id):
        """Wake an application-interrupted turn once, with durable delivery reconciliation.

        No original message or scientific effect is replayed. A lost send response is
        resolved by its exact correlation in provider history, never another send.
        """
        with self.store.connection() as db:
            resumed = records.latest_event(db, study, ('hyprn.turn_resumed',),
                                           reference=turn['turn_id'])
            intended = records.latest_event(db, study, ('hyprn.provider_continue_intended',),
                                            reference=turn['turn_id'])
            accepted = records.latest_event(db, study, ('hyprn.provider_continue_accepted',),
                                            reference=turn['turn_id'])
        if intended and accepted and accepted['intent_id'] == intended['id']:
            if not resumed or intended['resume_id'] == resumed['id']:
                return False
            intended = None
        if not intended and (not resumed or not resumed.get('continue_provider')):
            return False
        # Existing provider work may still be stopping. Do not enqueue a second turn.
        account = await self.provider.session_account(provider_id)
        if account['status'] != 'idle' and not intended:
            return True
        intent_id = intended['id'] if intended else 'continue_' + resumed['id']
        marker = 'HYPRN continuation reference: ' + intent_id
        content = [dict(type='text', text=(
            'Continue the existing study request after an application interruption. '
            'Read the current study and retained tool results before taking action. '
            'Do not repeat completed writes, submitted calculations or sampling. '
            'Continue from the saved state and report any remaining blocker clearly.')),
            dict(type='text', text=marker)]
        with self.store.connection(write=True) as db:
            claimed = records.save_event(db, study, dict(id=intent_id,
                type='hyprn.provider_continue_intended', turn_id=turn['turn_id'],
                resume_id=resumed['id'], _received_at=time.time()))
        if claimed:
            self.authorize_turn(turn)
            await self._check_spending(study)
            try:
                await self.provider.send(provider_id, dict(type='user.message', content=content))
            except ProviderError:
                # The intent remains immutable even on a missing response.
                pass
        await self._history(study, provider_id, turn)
        with self.store.connection(write=True) as db:
            matches = [json.loads(row[0]) for row in db.execute(
                "SELECT payload FROM assistant_events WHERE study_id=? "
                "AND event_type='user.message' AND reference_id=? LIMIT 2", (study, intent_id))
                if json.loads(row[0]).get('content') == content]
            if len(matches) != 1:
                raise ProviderError('provider_resume_delivery_unknown', uncertain=True)
            records.save_event(db, study, dict(id='accepted_' + intent_id,
                type='hyprn.provider_continue_accepted', turn_id=turn['turn_id'],
                intent_id=intent_id, original_event=turn['provider_event'],
                provider_event=matches[0]['id'], _received_at=time.time()))
        return True

    async def _interrupt_failed_turn(self, study, provider_id):
        reply = await self.provider.interrupt(provider_id)
        sent = reply.get('data', reply.get('events', []))
        if sent:
            event_id = identity(sent[0].get('id'))
            with self.store.connection(write=True) as db:
                current = records.row(db, study)
                records.save_event(db, study, dict(id='interrupted_' + event_id,
                    type='hyprn.provider_interrupted', turn_id=current['active_turn'],
                    _received_at=time.time()))

    async def _pump(self, study):
        with self.store.background_actor('assistant', study) as admitted:
            if admitted:
                await self._funded_pump(study)

    async def _admit(self, study):
        async with self._allowance_admission:
            current, turn = self._load(study)
            if not turn or turn['stopped']:
                return None
            self.authorize_turn(turn)
            actor = allowance.owner(self.store, study)
            await allowance.check(self.store, self.provider, actor)
            _, latest = self._load(study)
            if not latest or latest['stopped']:
                return None
            self._update(study, state='starting', error=None)
            provider_id = await self._session(current, self.settings, turn)
            # Remove only obsolete provider budget ceilings; definition upgrades
            # use pinned successor sessions and retain every prior provider cost.
            await self.provider.remove_session_cap(provider_id)
            return provider_id

    def _started_at(self, study, turn):
        event_id = 'turn_started_' + turn['turn_id']
        with self.store.connection(write=True) as db:
            resumed = records.latest_event(db, study, ('hyprn.turn_resumed',),
                                           reference=turn['turn_id'])
            if resumed:
                return resumed['_received_at']
            found = records.event(db, study, event_id)
            if found:
                return found['_received_at']
            started = time.time() if turn['delivery'] == 'new' else turn['created_at']
            records.save_event(db, study, dict(id=event_id, type='hyprn.turn_started',
                                              turn_id=turn['turn_id'], _received_at=started))
            return started

    async def _check_spending(self, study):
        actor = allowance.owner(self.store, study)
        await allowance.check(self.store, self.provider, actor)

    async def _funded_pump(self, study):
        provider_id = None
        try:
            current, turn = self._load(study)
            if not turn:
                return
            if turn['stopped'] and current['provider_id']:
                await self._stop_remote(study, turn, current['provider_id'])
                return
            # A retained monitoring result survives the reasoning lease. Its exact
            # accepted work is read by the application owner before a new lease opens.
            with self.store.connection() as db:
                waiting = db.execute('SELECT event_id FROM assistant_tool_results '
                    "WHERE study_id=? AND turn_id=? AND delivery='waiting' LIMIT 1",
                    (study, turn['turn_id'])).fetchone()
                waiting_event = records.event(db, study, waiting[0]) if waiting else None
            if waiting_event:
                provider_id = current['provider_id']
                saved = self._saved_tool(study, waiting[0])
                if await self._wait_analysis(study, turn, waiting_event, saved) is None:
                    await self._stop_remote(study, turn, provider_id)
                    return
            self.authorize_turn(turn)
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
            checked_at = time.monotonic()
            delay = 1.0
            while True:
                _, turn = self._load(study)
                if turn['stopped']:
                    await self._stop_remote(study, turn, provider_id)
                    return
                self.authorize_turn(turn)
                if time.time() - started_at > MAX_TURN_SECONDS:
                    raise ProviderError('turn_time_limit')
                if time.monotonic() - checked_at >= 10:
                    await self._check_spending(study)
                    checked_at = time.monotonic()
                history = await self._history(study, provider_id, turn)
                self.authorize_turn(turn)
                relevant, idle = await asyncio.to_thread(self._pending, study, turn['provider_event'])
                delivered = False
                for event in relevant:
                    if event.get('type') == 'agent.custom_tool_use' and not turn['stopped']:
                        if time.monotonic() - checked_at >= 10:
                            await self._check_spending(study)
                            checked_at = time.monotonic()
                        delivered = await self._tool(study, turn, provider_id, event, history) or delivered
                if delivered:
                    # A result can wake the provider; never apply an earlier idle event.
                    started_at = self._started_at(study, turn)
                    delay = 1.0
                    continue
                if not relevant and await self._continue_provider(study, turn, provider_id):
                    await asyncio.sleep(1)
                    continue
                if (idle and idle['type'] == 'session.status_idle'
                        and (idle.get('stop_reason') or {}).get('type') != 'requires_action'):
                    reason = (idle.get('stop_reason') or {}).get('type')
                    self.runtime.sessions.end(turn['runtime_session'])
                    self._update(
                        study,
                        state='idle' if reason == 'end_turn' else 'blocked',
                        error=None if reason == 'end_turn' else 'provider_' + str(reason),
                        active_turn=None,
                    )
                    return
                delay = 1.0 if history else min(10.0, delay * 1.5)
                await asyncio.sleep(delay)
        except asyncio.CancelledError:
            raise
        except (DomainError, SessionRefused):
            self._update(study, state='blocked', error='access_lost')
            if provider_id:
                try:
                    await self._interrupt_failed_turn(study, provider_id)
                except ProviderError:
                    pass
        except ProviderError as error:
            self._update(study, state='blocked', error=error.code)
            if provider_id and error.code != 'provider_resume_delivery_unknown':
                try:
                    await self._interrupt_failed_turn(study, provider_id)
                except ProviderError:
                    pass
        except Exception as error:
            # Keep the failure location, never exception messages, locals or payloads.
            frames = traceback.extract_tb(error.__traceback__)
            location = ' > '.join(f'{f.name}:{f.lineno}' for f in frames[-6:])
            logging.getLogger(__name__).error('Assistant failure %s at %s',
                                              type(error).__name__, location)
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
        current, _ = self._load(study)
        # Search from this interrupt, not the earlier unreadable attachment. Stop
        # must remain possible when prior content exceeds an admission boundary.
        since = sent[0].get('created_at') or current['provider_cursor']
        for _ in range(60):
            async for event in self.provider.events(provider_id, since):
                stamp = event.get('created_at') or event.get('processed_at')
                if stamp and (since is None or stamp > since):
                    since = stamp
                if event.get('id') == interrupt_id and event.get('processed_at'):
                    if turn['runtime_session']:
                        self.runtime.sessions.end(turn['runtime_session'])
                    self._update(study, state='idle', active_turn=None, error=None)
                    return
            await asyncio.sleep(1)
        raise ProviderError('interrupt_delivery_unknown', uncertain=True)
