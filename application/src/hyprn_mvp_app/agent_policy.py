"""Route allowlist for delegated agent API sessions (ND-4 as revised for ADR-0003).

Agent sessions reach ``/api/1`` only through the routes this module admits; everything else is
refused (403) by the API middleware before routing. Two rules apply, in this order:

1. every route of the closed human-only classification (``agent_tools.write_policy``: deleting
   saved records, archive and restore, access management, backup restore and import) is
   refused for every effect set, whatever a registry declares;
2. the remaining allowed operations are exactly the ``(method, template)`` pairs the tool
   registry's tools call for the delegation's effects and the advertised capability gates,
   plus the internal reads the agent runtime needs (the study's command receipts, the
   capabilities and, for run admission, the study's run list).

A working-material deletion route is therefore reachable only once a registered tool declares
it, and study creation only once the study-creation tool is registered. The middleware also
refuses every mutation of a read-only session and pins a session to its delegation's study.

Imported only by ``api``; it reads no store and holds no state.
"""

from functools import lru_cache
import re

from .agent_tools import write_policy
from .agent_tools.registry import REGISTRY
from .agent_tools.spec import DELEGATION_EFFECTS

# Reads the runtime itself makes for a session, whatever tools are registered.
INTERNAL_READS = frozenset(
    {
        ('GET', '/api/1/studies/{study_id}/commands/{command_id}'),
        ('GET', '/api/1/capabilities'),
        ('GET', '/api/1/studies/{study_id}/runs'),
    }
)
_PLACEHOLDER = re.compile(r'\{[a-z_]+\}')


@lru_cache(maxsize=256)
def _template(template):
    # A placeholder matches exactly one concrete path segment.
    return re.compile('[^/]+'.join(re.escape(p) for p in _PLACEHOLDER.split(template)))


def _effects(effects):
    effects = frozenset(effects)
    if not effects <= DELEGATION_EFFECTS:
        raise ValueError('Unknown agent effect')
    return effects


def allowed_operations(effects, capabilities=frozenset(), registry=None):
    """The ``(method, template)`` pairs an agent session holding ``effects`` may call: the
    registry's pairs plus the internal reads, never a human-only route. ``registry`` is the
    registry the application was composed with (the packaged catalogue by default)."""
    registry = REGISTRY if registry is None else registry
    operations = registry.api_operations(_effects(effects), frozenset(capabilities))
    return frozenset(
        (method, template)
        for method, template in operations | INTERNAL_READS
        if not write_policy.is_human_only(method, template)
    )


def route_allowed(method, path, effects, capabilities=frozenset(), registry=None):
    """Whether an agent session whose delegation holds ``effects`` may call ``method path``.

    ``path`` is the routed request path (no query). Unknown effects are a programming error,
    never a grant. A human-only route is refused before the allowlist is consulted.
    """
    effects = _effects(effects)
    if not isinstance(method, str) or not isinstance(path, str):
        return False
    if write_policy.is_human_only(method, path):
        return False
    return any(
        allowed_method == method and _template(template).fullmatch(path)
        for allowed_method, template in allowed_operations(effects, capabilities, registry)
    )
