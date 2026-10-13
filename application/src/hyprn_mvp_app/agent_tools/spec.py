"""The provider-neutral tool specification and its closed vocabularies.

A ``ToolSpec`` names what a tool does (``effect``), where and when it is offered (``surfaces``,
``stage``, ``scopes``, ``gate``), the exact API operations it calls, the owners of those
operations and the stored outcome any client reads back afterwards (ADR-0004). The effect
vocabulary has no lifecycle, deletion or access value: those effects are human-only on every
surface and stage (ADR-0003). There is no confirmation field: every tool executes directly.
"""

from dataclasses import dataclass, field
from typing import Any, Callable

EFFECTS = ('read', 'draft', 'record', 'submit', 'outside_study')
# Effects a delegation may hold. ``review`` belongs to reviewer delegations; no tool carries it
# in this phase, so it offers nothing and is never a write effect.
DELEGATION_EFFECTS = frozenset(EFFECTS) | {'review'}
WRITE_EFFECTS = frozenset({'draft', 'record', 'submit'})
STAGES = ('read_only', 'authoring', 'runs')
SURFACES = ('local_mcp', 'remote_mcp', 'claude_managed', 'openai_agents')
SCOPES = ('study', 'workspace')
OWNERS = frozenset(
    {
        'store',
        'approach',
        'configuration',
        'modeling',
        'execution',
        'history',
        'result_bindings',
        'modified_runs',
        'readiness',
        'units',
        'api',
        'agent_runtime',
        'agent_tools',
    }
)
# ``none`` for reads; ``receipt:<category>`` for API writes; ``runtime:<table>`` for rows the
# agent runtime keeps outside the study.
OUTCOME_PATTERN = r'none|receipt:[a-z][a-z0-9_]{0,63}|runtime:[a-z][a-z0-9_]{0,63}'
RECORD_LABELS = (None, 'agent-recorded')
# Tools that replace mutable shared state or may remove draft content (ND-13 as revised).
DESTRUCTIVE_TOOLS = frozenset(
    {'update_study_context', 'restore_approach_draft', 'update_approach_draft', 'edit_model'}
)
# The only client hint a tool may carry; never a key that forces an approval prompt (D-P8).
CLIENT_META_KEYS = frozenset({'anthropic/alwaysLoad'})


@dataclass(frozen=True)
class ToolSpec:
    """One tool. ``handler`` is an async ``handler(arguments, ctx)`` returning the projection;
    a tool the runtime serves itself names ``runtime_operation`` instead. ``api_operations``
    are ``(method, '/api/1/...')`` template pairs. Annotations are derived, never declared."""

    name: str
    title: str
    description: str
    input_schema: dict
    effect: str
    stage: str
    surfaces: tuple
    owners: tuple
    outcome: str | None
    activity_label: str
    handler: Callable | None = None
    api_operations: tuple = ()
    runtime_operation: str | None = None
    attribution_kind: str | None = None
    scopes: tuple = ('study',)
    gate: str | None = None
    record_label: str | None = None
    client_meta: tuple = ()
    since: str = '0.1.0'

    @property
    def is_check(self):
        """A read whose API operations send a POST (a static check or a preview): offered only
        to a delegation holding a write effect."""
        return self.effect == 'read' and any(m == 'POST' for m, _ in self.api_operations)

    @property
    def annotations(self):
        """All four MCP hints, always set (D-P7). Clients must not trust them as authority;
        HYPRN MVP's own authorization never reads them."""
        if self.effect == 'read':
            return {
                'readOnlyHint': True,
                'destructiveHint': False,
                'idempotentHint': True,
                'openWorldHint': False,
            }
        return {
            'readOnlyHint': False,
            'destructiveHint': self.name in DESTRUCTIVE_TOOLS,
            'idempotentHint': False,
            'openWorldHint': False,
        }


@dataclass(frozen=True)
class ToolContext:
    """What one tool call runs under: the session's surface, stage, delegation effects, scope
    and advertised capabilities, with the in-process API client and the delegated agent
    session the handler passes to it. The study is the session's; no argument names it."""

    surface: str
    stage: str
    effects: frozenset
    scope: str = 'study'
    capabilities: frozenset = frozenset()
    api: Any = None
    session: Any = field(default=None, repr=False)


class ToolError(Exception):
    """A tool failure in the agent error envelope (tooling spec section 6.1). Messages and
    field problems never echo a submitted value."""

    def __init__(self, category, message, *, fields=(), next_step=None, retryable=False):
        super().__init__(category)
        self.category = category
        self.message = message
        self.fields = tuple(fields)
        self.next_step = next_step
        self.retryable = retryable

    def envelope(self, request_id=None):
        return {
            'error': {
                'category': self.category,
                'retryable': self.retryable,
                'message': self.message,
                'fields': [dict(f) for f in self.fields],
                'next_step': self.next_step,
                'request_id': request_id,
                'partial': None,
            }
        }
