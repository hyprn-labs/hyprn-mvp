"""External ingress only. Trusted delegated callers retain the inner API object."""

from starlette.concurrency import run_in_threadpool
from starlette.requests import Request

from hyprn_mvp_app.contracts import DomainError
from hyprn_mvp_app.edge import error_response
from hyprn_mvp_app.external_identity import verified_identity
from .access import InvalidAssertion


def from_environment(environ=None):
    """Compose hosted auth around the same inner API used by the embedded Assistant."""
    import os
    from pathlib import Path
    from hyprn_mvp_app.api import create_app
    from hyprn_mvp_app.external_identity import HostedAuth
    from hyprn_mvp_app.modeling import ModelingClient
    from hyprn_mvp_app.ui import mount_workspace
    from hyprn_mvp_app.assistant.claude import credential
    from .access import AccessVerifier
    from .runtime import open_store, required, WriterLease

    environ = os.environ if environ is None else environ
    origin = required(environ, 'EXTERNAL_ORIGIN')
    ui = Path(required(environ, 'UI_ROOT'))
    if not (ui / 'index.html').is_file():
        raise ValueError('Hosted configuration built workspace is absent')
    store = open_store(environ)
    auth = HostedAuth(store, origin)
    model = ModelingClient(required(environ, 'MODEL_URL'),
                           credential(environ['HYPRN_SECRET_MODELING_AUTH_FILE']).encode())
    verifier = AccessVerifier(required(environ, 'ACCESS_ISSUER'), required(environ, 'ACCESS_AUDIENCE'),
                              proxy=environ.get('HYPRN_MVP_EGRESS_PROXY'))
    lease = WriterLease(store.database.request)
    try:
        app = create_app(store, auth, model, environ=environ)
        mount_workspace(app, ui)
        app.router.add_event_handler('shutdown', lease.close)
        app.router.add_event_handler('shutdown', store.database.close)
        app.state.writer_lease = lease
        # The runtime gate is installed on the inner application too: trusted
        # delegated tools may not bypass maintenance or scientific admission.
        from .admission import install
        install(app, environ, lease)
        from .assistant_startup import install as install_assistant
        install_assistant(app, environ)
        return AccessIngress(app, auth, verifier)
    except BaseException:
        verifier.close()
        lease.close()
        raise


class AccessIngress:
    def __init__(self, app, auth, verifier):
        self.app, self.auth, self.verifier = app, auth, verifier
        app.router.add_event_handler('shutdown', verifier.close)

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        request = Request(scope)
        try:
            values = request.headers.getlist('cf-access-jwt-assertion')
            if len(values) != 1:
                raise InvalidAssertion('Invalid access assertion')
            identity = await run_in_threadpool(self.verifier.verify, values[0])
            token = request.cookies.get('hyprn_mvp_session')
            if token:
                await run_in_threadpool(self.auth.bind, identity, token)
        except (InvalidAssertion, DomainError):
            response = error_response(request, DomainError('unauthenticated', 401))
            response.headers.update({'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
                                     'Referrer-Policy': 'no-referrer'})
            response.delete_cookie(
                'hyprn_mvp_session', path='/api/1', secure=True, httponly=True, samesite='strict'
            )
            return await response(scope, receive, send)
        with verified_identity(identity):
            return await self.app(scope, receive, send)
