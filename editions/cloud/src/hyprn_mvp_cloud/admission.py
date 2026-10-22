"""Host-owned admission applies equally to browser and delegated inner API calls."""

import time
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request

from hyprn_mvp_app.api import MUTATIONS
from hyprn_mvp_app.contracts import DomainError
from hyprn_mvp_app.edge import error_response
from .runtime import host_record, required
from hyprn_mvp_app.hosted_runtime import request_lease

# These operations admit native or asynchronous work. Authoring and saved reads
# remain possible when the browser is open and scientific admission is closed.
SCIENTIFIC_PARTS = frozenset({
    'runs', 'execution', 'run-requests', 'calculation-samples', 'calculation-estimates',
    'computational-record-previews', 'computational-records', 'predictions',
})


class Admission:
    def __init__(self, environ, *, owner=0):
        self.path = required(environ, 'ADMISSION_FILE')
        identity = host_record(required(environ, 'HOST_IDENTITY_FILE'), owner=owner)
        self.identity = {name: identity[name] for name in (
            'installation_id', 'release_sha256', 'config_sha256')}
        self.owner = owner

    def read(self):
        value = host_record(self.path, owner=self.owner)
        if (set(value) != {'schema', *self.identity, 'browser', 'scientific', 'expires_at'}
                or value['schema'] != 'hyprn-admission/v1'
                or any(value[k] != v for k, v in self.identity.items())
                or type(value['browser']) is not bool or type(value['scientific']) is not bool
                or type(value['expires_at']) is not int
                or not time.time() < value['expires_at'] <= time.time() + 300):
            raise ValueError('Hosted admission identity is unavailable or expired')
        return value

    def allows(self, method, path):
        value = self.read()
        if not value['browser']:
            return False
        return not (method in MUTATIONS and SCIENTIFIC_PARTS.intersection(path.split('/'))
                    and not value['scientific'])


def install(app, environ, lease):
    gate = Admission(environ)
    app.state.admission = gate

    app.add_middleware(AdmissionMiddleware, gate=gate, lease=lease,
                       credentials=app.state.store.database.request)


class AdmissionMiddleware:
    def __init__(self, app, *, gate, lease, credentials):
        self.app, self.gate, self.lease, self.credentials = app, gate, lease, credentials

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        request = Request(scope)
        active = request_lease(self.credentials)
        entered = False
        try:
            try:
                await run_in_threadpool(active.__enter__)
                entered = True
                await run_in_threadpool(self.lease.check)
                allowed = await run_in_threadpool(self.gate.allows, request.method, request.url.path)
            except Exception:
                allowed = False
            if not allowed:
                response = error_response(request, DomainError('backend_unavailable', 503))
                response.headers.update({'Retry-After': '5', 'Cache-Control': 'no-store'})
                return await response(scope, receive, send)
            return await self.app(scope, receive, send)
        finally:
            if entered:
                await run_in_threadpool(active.__exit__, None, None, None)
