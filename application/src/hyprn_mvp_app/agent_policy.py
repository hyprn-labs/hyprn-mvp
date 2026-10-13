"""Route allowlist for delegated agent API sessions.

Agent sessions reach ``/api/1`` only through the routes this module admits; everything else is
refused (403) by the API middleware before routing. The rule is closed: a route that is not
named here is refused for every agent session, whatever its delegation's effects. Today an
agent session may only read: ``GET`` on the capabilities, the study listing and the routes
below one study. Writes (study creation included) stay closed until the tool registry derives
the allowed operations from its declared API operations, refused after the human-only routes.

Imported only by ``api``; it reads no store and holds no state.
"""
import re

# Reads every agent session may make. The study id segment is a single path segment; the
# middleware separately pins an agent session to its delegation's study.
_READ_ROUTES = (
    re.compile(r'/api/1/capabilities'),
    re.compile(r'/api/1/studies'),
    re.compile(r'/api/1/studies/[^/]+(?:/[^/]+)*'),
)
_EFFECTS = frozenset({'read', 'draft', 'record', 'submit', 'outside_study', 'review'})


def route_allowed(method, path, effects):
    """Whether an agent session whose delegation holds ``effects`` may call ``method path``.

    ``path`` is the routed request path (no query). Unknown effects are a programming error,
    never a grant. Only ``GET`` reads are admitted.
    """
    effects = frozenset(effects)
    if not effects <= _EFFECTS:
        raise ValueError('Unknown agent effect')
    if method != 'GET' or not isinstance(path, str):
        return False
    return any(route.fullmatch(path) for route in _READ_ROUTES)
