"""Documents browser fixture boundary.

The authorized native-backed Documents API does not exist yet. Startup is refused
until it is implemented; never substitute a live URL or a mock
success. Reuse the scoped UI fixture patterns and installed Playwright at that time.
"""
import scoped_fixture as guard


def guarded_scope(group):
    scope = guard.documents_scope(guard.APPROVED_CONTRACT_PYTHON)
    from checks import DOCUMENTS_ROUTES, documents_targets
    route = DOCUMENTS_ROUTES.get(group)
    if route is None or route['mode'] != 'browser':
        raise ValueError('Explicit Documents browser group required')
    documents_targets(group)
    return scope


def run(*, group):
    guarded_scope(group)  # Before app/native imports, server startup or writes.
    raise ValueError('Documents isolated API/native/browser capability unavailable: ' + group)
