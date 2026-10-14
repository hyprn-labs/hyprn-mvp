"""The agent runtime: the one admission path of every tool call on every surface.

``Runtime.call_tool(surface_ctx, call_id, name, arguments)`` admits the call — the kill switch
(consulted on every call), the session (active, not replaced, access not lost), the delegation
(live, through ``Auth``), the API-call budget and the repeated-error budget — journals it
``intended`` with its argument digest and, for a mutating tool, fresh command ids, invokes the
registry with an injected context, and records exactly one outcome. A call refused at
admission is journaled ``refused`` with its reason and makes no API call.

The injected context (``RuntimeContext``) carries the in-process API client bound to this call
(it counts every request against the session's budget, journals each operation's template,
request id and status, and never sends a run submission that run admission did not admit), the
clock, the call's command ids and three callbacks: ``admit_runs(count)`` (run admission, before
any submission), ``record(...)`` (a record the call created or changed) and ``warn(...)`` (a
guard warning).

A duplicate ``call_id`` returns the stored outcome of a write and answers a read again, both
without a second journal row. Access loss — a 403, the session's own study no longer visible,
or a delegation that is no longer live — ends the session as ``access_lost``; that call and
every later one return ``access_lost``, and nothing is delivered after it.
"""

from dataclasses import dataclass, field
import hashlib
import re
import time
from typing import Any, Callable

from ..agent_tools import projections
from ..agent_tools.api_client import ApiClient
from ..agent_tools.registry import LOCAL_STAGE
from ..agent_tools.spec import WRITE_EFFECTS, ToolContext, ToolError
from ..contracts import canonical, uid
from . import control, journal, limits, records
from .delegations import iso
from .schema import RECORD_KINDS
from .sessions import SessionRefused, Sessions

UNKNOWN_TOOL = '(unknown tool)'
CALL_ID = re.compile(r'[\x20-\x7e]{1,160}')
UUID = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')
TOKEN = re.compile(r'[a-z][a-z0-9_]{0,63}')
SEGMENT = re.compile(r'[a-z0-9-]{0,64}')
PLACEHOLDER = re.compile(r'\{[a-z_]+\}')
MAX_NAME = 200
MAX_FIELD = 128
# The digest journaled for arguments that are not JSON with finite numbers.
UNENCODABLE = hashlib.sha256(b'arguments that are not JSON').hexdigest()

# How a runtime refusal reads to the agent: (error category, retryable, next step).
REFUSALS = {
    'agent_disabled': (
        'unavailable',
        False,
        'Stop and tell the user that assistant access is off for this installation.',
    ),
    'access_lost': ('access_lost', False, 'Stop all work, tell the user and end the turn.'),
    'budget_exhausted': (
        'budget_exhausted',
        False,
        'Stop and tell the user that this session reached its limit of API calls.',
    ),
    'repeated_errors': (
        'budget_exhausted',
        False,
        'Stop repeating this call; tell the user what failed.',
    ),
    'run_limit_call': (
        'invalid_input',
        False,
        f'Submit at most {limits.MAX_RUNS_PER_CALL} runs per call.',
    ),
    'run_limit_queued': (
        'busy',
        True,
        'Wait until earlier runs have finished, then submit again.',
    ),
    'run_limit_session': (
        'budget_exhausted',
        False,
        'Stop submitting runs and tell the user that this session reached its run limit.',
    ),
    'invalid_input': ('invalid_input', False, 'Fix the input and call again.'),
}
# A tool error category and the journal outcome it ends a call with: (state, reason). Any
# other category fails the call as ``internal``.
CATEGORY_OUTCOMES = {
    'invalid_input': ('refused', 'invalid_input'),
    'too_large': ('refused', 'invalid_input'),
    'unsupported': ('refused', 'invalid_input'),
    'guard_blocked': ('refused', 'guard_blocked'),
    'conflict': ('refused', 'conflict'),
    'not_ready': ('refused', 'not_ready'),
    'not_found': ('refused', 'not_found'),
    'access_lost': ('refused', 'access_lost'),
    'budget_exhausted': ('refused', 'budget_exhausted'),
    'unavailable': ('failed', 'backend_unavailable'),
    'pending': ('uncertain', 'outcome_unknown'),
    'uncertain': ('uncertain', 'outcome_unknown'),
}
# Message parameters of error categories that name no field.
CATEGORY_PARAMS = {
    'too_large': {'field': '(input)', 'problem': 'is larger than the input limit'},
    'unsupported': {'field': '(request)', 'problem': 'is not supported by this installation'},
}
# Errors after which the runtime checks whether the delegation is still live.
_RECHECK = frozenset({'session_expired', 'not_found', 'internal'})


class UnknownSession(Exception):
    """No agent session has that id; the surface answers as for an unknown session."""


class SessionEnded(Exception):
    """The session ended (a newer session of the same token replaced it); the surface answers
    as for an unknown session and the client opens a new one."""


class Refusal(ToolError):
    """A refusal by the runtime itself, with its journal reason."""

    def __init__(self, reason, params=None):
        category, retryable, next_step = REFUSALS[reason]
        super().__init__(
            category, journal.message(reason, params), next_step=next_step, retryable=retryable
        )
        self.reason = reason
        self.params = params


@dataclass(frozen=True)
class ToolOutcome:
    """What a surface returns for one call: the projection when ``ok``, otherwise the error
    envelope; with its journal row (``None`` when the call kept no row of its own) and the
    row's state."""

    ok: bool
    content: dict
    action_id: str | None
    state: str


@dataclass(frozen=True)
class RuntimeContext(ToolContext):
    """The context a tool runs under in the runtime: ``ToolContext`` plus the clock, the command
    ids journaled for this call and the runtime callbacks."""

    clock: Callable = field(default=time.time, repr=False)
    command_ids: tuple = ()
    call: Any = field(default=None, repr=False, compare=False)

    async def admit_runs(self, count):
        """Run admission for ``count`` runs, before any submission: more than 20 in one call,
        above 60 in the session or above 10 of this agent waiting or running is refused."""
        await self.call.admit_runs(self, count)

    def record(self, kind, record_id, *, version_id=None, name=None, number=None):
        """Report a record this call created or changed, as the API returned it."""
        self.call.record(kind, record_id, version_id, name, number)

    def warn(self, code, field=None):
        """Report a guard warning: its code and the tool input path it concerns."""
        self.call.warn(code, field)


def args_digest(arguments):
    """The SHA-256 of the canonical JSON of ``arguments`` (the only trace of them kept) and its
    size in bytes; arguments that are not JSON share one fixed digest and size 0."""
    try:
        text = canonical(arguments)
    except (ValueError, TypeError, RecursionError):
        return UNENCODABLE, 0
    return hashlib.sha256(text).hexdigest(), len(text)


def route_template(path, tool):
    """The route template of ``path``: the tool's declared template it matches, otherwise the
    path with every identifier segment replaced, so no concrete value is journaled."""
    for _, template in tool.api_operations if tool is not None else ():
        pattern = '[^/]+'.join(re.escape(part) for part in PLACEHOLDER.split(template))
        if re.fullmatch(pattern, path):
            return template
    parts = path.split('/') if isinstance(path, str) else ['(path)']
    return '/'.join(p if SEGMENT.fullmatch(p) and not UUID.fullmatch(p) else '{id}' for p in parts)


def _valid_id(value):
    return isinstance(value, str) and UUID.fullmatch(value) is not None


class _Call:
    """The bookkeeping of one admitted call: its API operations, records, warnings and run
    admission. No transaction is held across an awaited request."""

    def __init__(self, runtime, session, checked, tool, api_session):
        self.runtime, self.session, self.checked = runtime, session, checked
        self.tool, self.api_session = tool, api_session
        self.operations, self.records, self.warnings, self.statuses = [], [], [], []
        self.changed = self.unknown = False
        self.admitted = None
        self.submitted = 0
        self.runs_path = '/api/1/studies/' + checked['study_id'] + '/runs'
        self.client = _CallClient(self)

    @property
    def writes(self):
        return self.tool.effect in WRITE_EFFECTS

    def count_api_call(self):
        if not self.runtime.count_api_call(self.session['session_id']):
            row = self.runtime.sessions.get(self.session['session_id'])
            if row is not None and row['state'] == 'active':
                raise Refusal('budget_exhausted')
            raise Refusal('access_lost')

    def take_run_slot(self):
        if self.admitted is None or self.submitted >= self.admitted:
            # A submission run admission did not admit is a tool defect; it is never sent.
            raise ToolError('internal', 'A run submission was not admitted.')
        self.submitted += 1

    def note(self, method, path, reply):
        if reply is not None:
            self.statuses.append(reply.status)
        if len(self.operations) < limits.MAX_API_OPERATIONS:
            self.operations.append(
                dict(
                    method=method,
                    template=route_template(path, self.tool),
                    request_id=reply.request_id if reply is not None else None,
                    status=reply.status if reply is not None else None,
                )
            )

    def record(self, kind, record_id, version_id, name, number):
        valid = (
            kind in RECORD_KINDS
            and _valid_id(record_id)
            and (version_id is None or _valid_id(version_id))
            and (name is None or isinstance(name, str))
            and (
                number is None
                or (isinstance(number, int) and not isinstance(number, bool) and number >= 1)
            )
        )
        if not valid:
            raise ToolError('internal', 'A reported record is not valid.')
        entry = dict(
            kind=kind,
            record_id=record_id,
            version_id=version_id,
            name=None if name is None else name[:MAX_NAME],
            number=number,
        )
        if entry not in self.records and len(self.records) < limits.MAX_RECORDS:
            self.records.append(entry)

    def warn(self, code, field):
        if not (isinstance(code, str) and TOKEN.fullmatch(code)):
            raise ToolError('internal', 'A reported warning is not valid.')
        entry = dict(code=code, field=field[:MAX_FIELD] if isinstance(field, str) else None)
        if entry not in self.warnings and len(self.warnings) < limits.MAX_WARNINGS:
            self.warnings.append(entry)

    async def admit_runs(self, ctx, count):
        if self.tool.effect != 'submit':
            raise ToolError('internal', 'Only a submit tool requests runs.')
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            raise ToolError('internal', 'A run request names a positive number of runs.')
        if self.admitted is not None:
            raise ToolError('internal', 'Runs are admitted once per call.')
        session_runs = len(self.runtime.session_runs(self.session['session_id']))
        reason = limits.run_refusal(count, session_runs, 0)
        if reason is None:
            reason = limits.run_refusal(count, session_runs, await self.queued_runs(ctx, count))
        if reason is not None:
            raise Refusal(reason)
        self.admitted = count

    async def queued_runs(self, ctx, count):
        """The agent's runs waiting or running in the study: the runs it submitted (from the
        journal) whose state in the study's run list is a waiting state. The list is read only
        when enough runs were submitted to reach the cap; a run missing from it counts."""
        mine = set(self.runtime.actor_runs(self.checked['actor_id'], self.checked['study_id']))
        if len(mine) + count <= limits.MAX_QUEUED_RUNS_PER_ACTOR:
            return len(mine)
        states, cursor = {}, None
        for _ in range(limits.MAX_RUN_LIST_PAGES):
            params = {'limit': limits.RUN_LIST_PAGE}
            if cursor is not None:
                params['cursor'] = cursor
            body = await projections.read(ctx, self.runs_path, params, missing='access_lost')
            items = body['data'] if isinstance(body['data'], list) else []
            for item in items:
                if isinstance(item, dict) and isinstance(item.get('run_id'), str):
                    states[item['run_id']] = item.get('state')
            cursor = body.get('next_cursor')
            if not cursor:
                break
        else:
            # The list is longer than one admission reads: never admit on a partial count.
            raise Refusal('run_limit_queued')
        return sum(1 for run in mine if states.get(run, 'uncertain') in limits.QUEUED_RUN_STATES)


class _CallClient:
    """The API client a tool sees: the runtime's in-process client bound to the call's
    delegated session (a session the tool passes is ignored)."""

    def __init__(self, call):
        self._call = call

    def __repr__(self):
        return '_CallClient()'

    async def request(self, session, method, path, json_body=None, params=None):
        call = self._call
        method = str(method).upper()
        if method == 'POST' and path == call.runs_path:
            call.take_run_slot()
        call.count_api_call()
        mutation = method != 'GET' and call.writes
        call.unknown = call.unknown or mutation
        reply = None
        try:
            reply = await call.runtime.client.request(
                call.api_session, method, path, json_body, params
            )
        finally:
            call.note(method, path, reply)
        if mutation:
            call.unknown = False
            call.changed = call.changed or 200 <= reply.status < 300
        return reply


class Runtime:
    """The agent runtime of one application process: its sessions and the one admission path
    of their tool calls."""

    def __init__(
        self,
        store,
        auth,
        registry,
        api_app,
        origin,
        environ,
        *,
        stage=LOCAL_STAGE,
        capabilities=frozenset(),
        clock=time.time,
    ):
        self.store, self.auth, self.registry = store, auth, registry
        self.environ, self.stage, self.clock = environ, stage, clock
        self.capabilities = frozenset(capabilities)
        self.client = ApiClient(api_app, origin)
        self.sessions = Sessions(store, auth, registry, environ, clock=clock)

    def __repr__(self):
        return 'Runtime()'

    async def aclose(self):
        await self.client.aclose()

    def open_session(self, grant, mcp_session_id, client_info, protocol_version, **options):
        """Open an agent session (``Sessions.open``); refused while agent access is off."""
        return self.sessions.open(grant, mcp_session_id, client_info, protocol_version, **options)

    # ---- Journal reads and counters --------------------------------------------------------

    def count_api_call(self, session_id):
        with self.store.connection(write=True) as db:
            return records.count_api_call(db, session_id, limits.MAX_API_CALLS_PER_SESSION)

    def session_runs(self, session_id):
        with self.store.connection() as db:
            return records.session_runs(db, session_id)

    def actor_runs(self, agent_actor_id, study_id):
        with self.store.connection() as db:
            return records.actor_runs(db, agent_actor_id, study_id)

    def _study(self, delegation_id):
        with self.store.connection() as db:
            return records.delegation_study(db, delegation_id)

    def _repeated(self, session_id, tool, digest, now):
        since = iso(now - limits.REPEATED_ERROR_WINDOW_SECONDS)
        with self.store.connection() as db:
            count = records.identical_refusals(db, session_id, tool, digest, 'invalid_input', since)
        return count >= limits.REPEATED_ERROR_LIMIT

    # ---- Calls -------------------------------------------------------------------------------

    async def call_tool(self, surface_ctx, call_id, name, arguments):
        """Run one tool call of the session ``surface_ctx`` names (a ``SessionHandle`` or a
        session id); returns a ``ToolOutcome``. Raises ``UnknownSession`` or ``SessionEnded``,
        with no journal row, for a session that does not exist or was replaced."""
        session_id = getattr(surface_ctx, 'session_id', surface_ctx)
        session = self.sessions.get(session_id) if isinstance(session_id, str) else None
        if session is None:
            raise UnknownSession()
        if session['state'] == 'ended':
            raise SessionEnded()
        if not (isinstance(call_id, str) and CALL_ID.fullmatch(call_id)):
            raise ValueError('A call id is 1 to 160 printable ASCII characters')
        now = self.clock()
        tool = self._tool(name)
        digest, size = args_digest(arguments)
        intent = dict(
            session_id=session_id,
            delegation_id=session['delegation_id'],
            study_id=self._study(session['delegation_id']),
            call_id=call_id,
            tool=tool.name if tool is not None else UNKNOWN_TOOL,
            effect=tool.effect if tool is not None else None,
            args_sha256=digest,
        )

        # The kill switch comes first: while agent access is off, every call is refused.
        if not control.agent_enabled(self.environ):
            return self._refused(intent, Refusal('agent_disabled'), now)
        if session['state'] == 'access_lost':
            return self._refused(intent, Refusal('access_lost'), now)
        existing = journal.find(self.store, session_id, call_id)
        # The delegation is checked before anything is answered, a stored outcome included:
        # nothing is delivered after access loss.
        try:
            api_session, checked = self.sessions.live(session_id, session['delegation_id'])
        except SessionRefused:
            self.sessions.end(session_id, 'access_lost')
            return self._refused(intent, Refusal('access_lost'), now, existing)
        if existing is not None and (
            existing['tool'] != intent['tool'] or existing['args_sha256'] != digest
        ):
            error = ToolError(
                'invalid_input',
                'This call id was already used for a different call.',
                next_step='Send each call with its own call id.',
            )
            return ToolOutcome(False, error.envelope(), None, 'refused')
        if existing is not None and existing['effect'] != 'read':
            return self._stored(existing)
        if session['api_calls'] >= limits.MAX_API_CALLS_PER_SESSION:
            return self._refused(intent, Refusal('budget_exhausted'), now, existing)
        if self._repeated(session_id, intent['tool'], digest, now):
            return self._refused(intent, Refusal('repeated_errors'), now, existing)
        effects = frozenset(checked['effects'])
        offered = self.registry.offered(
            session['surface'], self.stage, effects, 'study', self.capabilities
        )
        if tool is None or all(t.name != tool.name for t in offered):
            problem = {'field': 'tool', 'problem': 'is not available in this session'}
            return self._refused(intent, Refusal('invalid_input', problem), now, existing)
        if size > limits.MAX_INPUT_BYTES:
            refusal = Refusal('invalid_input', CATEGORY_PARAMS['too_large'])
            return self._refused(intent, refusal, now, existing)

        command_ids = tuple(uid() for _ in range(limits.COMMAND_IDS.get(tool.effect, 0)))
        action_id = None
        if existing is None:
            try:
                action_id = journal.intend(self.store, dict(intent, command_ids=command_ids), now)
            except journal.Duplicate:
                return self._stored(journal.find(self.store, session_id, call_id))
        call = _Call(self, session, checked, tool, api_session)
        ctx = RuntimeContext(
            surface=session['surface'],
            stage=self.stage,
            effects=effects,
            scope='study',
            capabilities=self.capabilities,
            api=call.client,
            session=api_session,
            clock=self.clock,
            command_ids=command_ids,
            call=call,
        )
        try:
            result = await self.registry.invoke(tool.name, arguments, ctx)
        except ToolError as error:
            return self._ended(action_id, call, error)
        except Exception:
            # Never the exception's text: it may carry a submitted value.
            error = ToolError('internal', 'HYPRN MVP could not complete the call.')
            return self._ended(action_id, call, error)
        if 403 in call.statuses:
            return self._ended(action_id, call, Refusal('access_lost'))
        if action_id is not None:
            journal.complete(
                self.store,
                action_id,
                self.clock(),
                records=call.records,
                warnings=call.warnings,
                result=result if call.writes else None,
                api_operations=call.operations,
                session_id=session_id,
            )
        return ToolOutcome(True, result, action_id, 'completed')

    def _tool(self, name):
        if not isinstance(name, str):
            return None
        try:
            return self.registry.tool(name)
        except KeyError:
            return None

    def _refused(self, intent, refusal, now, existing=None):
        """Journal ``intent`` as refused at admission (no second row for a duplicate read)."""
        action_id = None
        if existing is None:
            action_id = journal.refused(
                self.store,
                intent,
                refusal.reason,
                now,
                outcome_class=refusal.category,
                params=refusal.params,
            )
        return ToolOutcome(False, refusal.envelope(), action_id, 'refused')

    def _lost(self, call, error):
        """Whether the call saw access loss: an ``access_lost`` error or a 403, or, after an
        error that can hide it, a delegation that is no longer live."""
        if error.category == 'access_lost' or 403 in call.statuses:
            return True
        if error.category not in _RECHECK:
            return False
        try:
            self.sessions.live(call.session['session_id'], call.session['delegation_id'])
        except SessionRefused:
            return True
        return False

    def _ended(self, action_id, call, error):
        """Record the outcome of a call that ended in ``error``; returns its envelope."""
        session_id = call.session['session_id']
        if self._lost(call, error):
            self.sessions.end(session_id, 'access_lost')
            if not isinstance(error, Refusal) or error.reason != 'access_lost':
                error = Refusal('access_lost')
        if isinstance(error, Refusal):
            state, reason, params = 'refused', error.reason, error.params
        else:
            state, reason = CATEGORY_OUTCOMES.get(error.category, ('failed', 'internal'))
            params = _params(error)
        if call.writes and (call.changed or call.unknown):
            # Something may already have changed, so the call never reads "nothing changed".
            state, reason = 'uncertain', 'outcome_unknown'
        request_id = next(
            (op['request_id'] for op in reversed(call.operations) if op['request_id']), None
        )
        if action_id is not None:
            common = dict(
                outcome_class=error.category,
                api_operations=call.operations,
                warnings=call.warnings,
                records=call.records,
                session_id=session_id,
            )
            now = self.clock()
            if state == 'uncertain':
                journal.uncertain(self.store, action_id, now, **common)
            elif state == 'refused':
                journal.refuse(self.store, action_id, reason, now, params=params, **common)
            else:
                journal.fail(self.store, action_id, reason, now, params=params, **common)
        return ToolOutcome(False, error.envelope(request_id), action_id, state)

    def _stored(self, row):
        """The stored outcome of a journaled write, returned for a duplicate call id; nothing
        is executed again."""
        state = row['state']
        if state == 'completed':
            result = journal.loads(row['result_json'])
            if result is None:
                result = {'records': journal.loads(row['records'])}
            return ToolOutcome(True, result, row['action_id'], state)
        if state in ('intended', 'reconciling'):
            error = ToolError(
                'pending',
                'This call is still in progress.',
                next_step='Wait, then read the records before calling again.',
            )
        elif state == 'uncertain':
            error = ToolError(
                'uncertain',
                row['reason_message'],
                next_step="Don't resubmit; tell the user and check the records.",
            )
        else:
            error = ToolError(row['outcome_class'] or 'internal', row['reason_message'])
        return ToolOutcome(False, error.envelope(), row['action_id'], state)


def _params(error):
    """Message parameters of a tool error: its first field's path and problem (HYPRN MVP text:
    tool input paths and schema-derived problems, never a submitted value)."""
    if error.category in CATEGORY_PARAMS:
        return dict(CATEGORY_PARAMS[error.category])
    if error.fields:
        first = error.fields[0]
        return {
            'field': str(first.get('path', '(input)')),
            'problem': str(first.get('problem', 'is not valid')),
        }
    return None
