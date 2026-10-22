"""One bounded invocation of read-only tools through the existing runtime.

This cache is ephemeral delivery state, not an operation journal. Process loss has no
resume path. The trusted caller supplies current session/permission checks and explicitly
activates each fresh invocation. No provider is connected by this module.
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import json
import math
import re

from jsonschema import Draft202012Validator, FormatChecker

from ..agent_runtime.runtime import SessionEnded, ToolOutcome, UnknownSession
from ..agent_runtime.sessions import SessionHandle
from ..agent_tools.registry import NAME, Registry, definition, input_problems
from ..agent_tools.spec import ToolError
from ..contracts import canonical, data_json, digest
from .provider import ToolRequest, ToolResultTransport

ALLOWED = frozenset({'get_study_overview', 'get_playbook', 'list_runs', 'get_run_status'})
MAX_BYTES = 256 * 1024
MAX_OUTCOME_BYTES = 32 * 1024
MAX_CALLS = 64
MAX_EVENTS = 128
IDENTITY = re.compile(r'[\x21-\x7e]{1,128}')
ENVELOPE_KEYS = frozenset(ToolRequest.__dataclass_fields__) | {'kind', 'complete'}


def _identity(value):
    return isinstance(value, str) and IDENTITY.fullmatch(value) is not None


def _bounded_json(raw):
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
        raise ValueError('invalid_input')
    # Check nesting before the recursive parser/canonical encoder sees the input.
    text = raw.decode('utf-8')
    depth, quoted, escaped = 0, False, False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in '[{':
            depth += 1
            if depth > 32:
                raise ValueError('invalid_input')
        elif char in ']}':
            depth -= 1
    value = data_json(text)
    pending = [value]
    while pending:
        item = pending.pop()
        if isinstance(item, dict):
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
        elif type(item) in (int, float):
            if not math.isfinite(item) or (item == int(item) and abs(item) > 2**53 - 1):
                raise ValueError('invalid_input')
    return value


@dataclass(frozen=True)
class InvocationBinding:
    session: SessionHandle
    invocation_id: str
    provider_session_id: str
    provider_thread_id: str


@dataclass
class _Call:
    fingerprint: str
    state: str = 'invalid_input'
    outcome: bytes | None = None
    redelivered: bool = False


class ReadOnlyBridge:
    """Serialized local admission, with synchronous Stop and fresh access checks.

    ``current_access(SessionHandle)`` must synchronously check the live session,
    delegation and installation permission, returning exactly True to allow work.
    ``definitions`` are the trusted session's offered definitions, not provider data.
    Public results are closed status words; protected data travels only via transport.
    """

    def __init__(
        self,
        binding: InvocationBinding,
        *,
        registry: Registry,
        definitions: list,
        call_tool: Callable[[SessionHandle, str, str, dict], Awaitable[ToolOutcome]],
        current_access: Callable[[SessionHandle], bool],
        transport: ToolResultTransport,
    ):
        self._binding = binding
        self._registry = registry
        self._definitions = canonical(definitions)
        self._call_tool = call_tool
        self._current_access = current_access
        self._transport = transport
        self._lock = asyncio.Lock()
        self._active = False
        self._stopped = False
        self._terminal = None
        self._pending = None
        self._interrupt_state = None
        self._calls = {}
        self._events = {}
        self._schemas = {}
        self._policies = {}

    @property
    def definitions_sha256(self):
        return digest(json.loads(self._definitions))

    def _access(self):
        try:
            return self._current_access(self._binding.session) is True
        except Exception:
            return False

    def _gate(self):
        if self._stopped:
            return 'stopped'
        if not self._active:
            return 'closed'
        if not self._access():
            self._terminal = 'access_lost'
        return self._terminal

    def _policy(self, name):
        tool = self._registry.tool(name)
        if tool.effect != 'read' or tool.runtime_operation is not None:
            raise ValueError('policy_refused')
        if (not tool.api_operations and name != 'get_playbook') or any(
            method != 'GET' for method, _ in tool.api_operations
        ):
            raise ValueError('policy_refused')
        return digest([definition(tool), tool.effect, tool.runtime_operation, tool.api_operations])

    def activate(self):
        """Open once after trusted binding/access validation; never reopens a stopped bridge."""
        if self._active or self._stopped or self._terminal:
            return 'closed'
        binding = self._binding
        if not isinstance(binding.session, SessionHandle) or not all(
            _identity(value)
            for value in (
                binding.invocation_id,
                binding.provider_session_id,
                binding.provider_thread_id,
                binding.session.session_id,
                binding.session.study_id,
            )
        ):
            return 'invalid_binding'
        if not self._access():
            self._terminal = 'access_lost'
            return self._terminal
        try:
            definitions = json.loads(self._definitions)
            names = [item['name'] for item in definitions]
            if len(names) != len(set(names)):
                raise ValueError('policy_refused')
            for item in definitions:
                name = item['name']
                if name not in ALLOWED:
                    continue
                self._policies[name] = self._policy(name)
                tool = self._registry.tool(name)
                if canonical(item) != canonical(definition(tool)):
                    raise ValueError('policy_refused')
                self._schemas[name] = Draft202012Validator(
                    json.loads(canonical(tool.input_schema)), format_checker=FormatChecker()
                )
        except (KeyError, TypeError, ValueError):
            self._terminal = 'policy_refused'
            return self._terminal
        self._active = True
        return 'active'

    def _request(self, raw):
        value = _bounded_json(raw)
        if not isinstance(value, dict) or value.keys() != ENVELOPE_KEYS:
            raise ValueError('invalid_input')
        if value.pop('kind') != 'tool_request' or value.pop('complete') is not True:
            raise ValueError('invalid_input')
        request = ToolRequest(**value)
        if not all(
            _identity(getattr(request, key))
            for key in (
                'invocation_id',
                'provider_session_id',
                'provider_thread_id',
                'event_id',
                'call_id',
            )
        ) or not isinstance(request.arguments, str):
            raise ValueError('invalid_input')
        if not isinstance(request.name, str) or not NAME.fullmatch(request.name):
            raise ValueError('invalid_input')
        return request

    async def handle_tool_request(self, raw: bytes):
        """Admit a complete envelope; repeated observations never resubmit a result.

        A call first seen behind the delivery fence reserves its identity. After recovery,
        only an explicit identical request may continue that still-undispatched call.
        """
        async with self._lock:
            if refusal := self._gate():
                return refusal
            try:
                request = self._request(raw)
            except (ValueError, TypeError, OverflowError):
                return 'invalid_input'
            binding = self._binding
            if (
                request.invocation_id != binding.invocation_id
                or request.provider_session_id != binding.provider_session_id
                or request.provider_thread_id != binding.provider_thread_id
            ):
                return 'foreign_binding'
            arguments = None
            try:
                arguments = _bounded_json(request.arguments.encode('utf-8'))
                if not isinstance(arguments, dict):
                    arguments = None
            except (ValueError, TypeError, OverflowError):
                pass
            fingerprint = digest(
                [request.name, arguments, request.arguments if arguments is None else None]
            )
            observation = (request.call_id, fingerprint)
            if request.event_id in self._events and self._events[request.event_id] != observation:
                return 'conflict'
            if request.event_id not in self._events:
                if len(self._events) >= MAX_EVENTS:
                    self._terminal = 'capacity_exhausted'
                    return self._terminal
                self._events[request.event_id] = observation
            record = self._calls.get(request.call_id)
            if record is not None:
                if record.fingerprint != fingerprint:
                    return 'conflict'
                if record.state != 'delivery_pending' or self._pending is not None:
                    return record.state
            else:
                if len(self._calls) >= MAX_CALLS:
                    self._terminal = 'capacity_exhausted'
                    return self._terminal
                record = _Call(fingerprint)
                self._calls[request.call_id] = record
            if self._pending is not None:
                record.state = 'delivery_pending'
                return record.state
            record.state = 'invalid_input'
            if arguments is None:
                return record.state
            if request.name not in self._schemas:
                record.state = 'tool_refused'
                return record.state
            try:
                if self._policy(request.name) != self._policies[request.name]:
                    raise ValueError('policy_refused')
            except (KeyError, TypeError, ValueError):
                self._terminal = record.state = 'policy_refused'
                return record.state
            if input_problems(self._schemas[request.name], arguments):
                return record.state
            if refusal := self._gate():
                return refusal
            runtime_id = 'assistant:' + digest(
                [binding.session.session_id, binding.invocation_id, request.call_id]
            )
            record.state = 'recovery_required'
            try:
                outcome = await self._call_tool(
                    binding.session, runtime_id, request.name, arguments
                )
            except (UnknownSession, SessionEnded):
                self._terminal = 'session_unavailable'
            except asyncio.CancelledError:
                self._terminal = 'recovery_required'
                raise
            except Exception:
                self._terminal = 'recovery_required'
            else:
                record.outcome = self._freeze(outcome)
            if refusal := self._gate():
                return refusal
            return await self._submit(request.call_id, record)

    @staticmethod
    def _freeze(outcome):
        try:
            if not isinstance(outcome, ToolOutcome):
                raise ValueError('invalid_outcome')
            value = dict(
                ok=outcome.ok,
                content=outcome.content,
                action_id=outcome.action_id,
                state=outcome.state,
            )
            raw = canonical(value)
            if len(raw) > MAX_OUTCOME_BYTES:
                raise ValueError('invalid_outcome')
            _bounded_json(raw)
            return raw
        except (ValueError, TypeError, RecursionError, OverflowError):
            return canonical(
                dict(
                    ok=False,
                    content=ToolError(
                        'internal', 'The tool outcome could not be delivered.'
                    ).envelope(),
                    action_id=None,
                    state='refused',
                )
            )

    async def _submit(self, call_id, record):
        if refusal := self._gate():
            return refusal
        binding = self._binding
        self._pending = call_id
        record.state = 'delivery_unknown'
        try:
            reply = await self._transport.submit_tool_result(
                binding.provider_session_id, binding.provider_thread_id, call_id, record.outcome
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            reply = 'unknown'
        if reply == 'accepted':
            record.state = 'accepted'
            self._pending = None
        # A submission's negative/invalid reply is reconciled by lookup before any retry.
        return self._gate() or record.state

    async def reconcile_result(self, call_id: str):
        """Lookup is permitted after Stop; it conveys no protected outcome bytes."""
        async with self._lock:
            if not _identity(call_id) or call_id != self._pending:
                return 'not_pending'
            binding = self._binding
            record = self._calls[call_id]
            try:
                reply = await self._transport.inspect_tool_result(
                    binding.provider_session_id, binding.provider_thread_id, call_id
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                reply = 'unknown'
            if reply == 'accepted':
                record.state = 'accepted'
                self._pending = None
            elif reply == 'not_accepted':
                record.state = 'not_accepted'
            else:
                record.state = 'delivery_unknown'
            self._gate()
            return record.state

    async def redeliver_result(self, call_id: str):
        """One explicit resend after proven nonacceptance, never a runtime replay."""
        async with self._lock:
            if refusal := self._gate():
                return refusal
            if not _identity(call_id) or call_id != self._pending:
                return 'not_pending'
            record = self._calls[call_id]
            if record.state != 'not_accepted' or record.redelivered:
                return 'redelivery_refused'
            record.redelivered = True
            return await self._submit(call_id, record)

    def stop(self):
        """Close local admission now, returning an awaitable interruption observation.

        Results already admitted to submit_tool_result cannot be unsent. An in-flight
        runtime read may finish, but a result not yet admitted will not be submitted.
        """
        self._stopped = True
        return self._interrupt()

    async def _interrupt(self):
        if self._interrupt_state is not None:
            return self._interrupt_state
        self._interrupt_state = 'requested'
        binding = self._binding
        try:
            reply = await self._transport.interrupt(
                binding.provider_session_id, binding.provider_thread_id
            )
        except asyncio.CancelledError:
            self._interrupt_state = 'unknown'
            raise
        except Exception:
            reply = 'unknown'
        self._interrupt_state = (
            reply if reply in ('requested', 'accepted', 'unknown') else 'unknown'
        )
        return self._interrupt_state
