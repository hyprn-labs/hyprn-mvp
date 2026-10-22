"""Normalized complete requests and result transport, independent of any provider wire API."""

from dataclasses import dataclass
from typing import Literal, Protocol

Delivery = Literal['accepted', 'not_accepted', 'unknown']
Interruption = Literal['requested', 'accepted', 'unknown']


@dataclass(frozen=True)
class ToolRequest:
    invocation_id: str
    provider_session_id: str
    provider_thread_id: str
    event_id: str
    call_id: str
    name: str
    arguments: str


class ToolResultTransport(Protocol):
    """Submission bytes are the immutable ToolOutcome envelope, never credentials.

    An adapter must preserve the original correlation on lookup and resubmission.
    Interruption acceptance acknowledges the request, not remote termination.
    """

    async def submit_tool_result(
        self, session: str, thread: str, call: str, outcome: bytes
    ) -> Delivery: ...

    async def inspect_tool_result(self, session: str, thread: str, call: str) -> Delivery: ...

    async def interrupt(self, session: str, thread: str) -> Interruption: ...
