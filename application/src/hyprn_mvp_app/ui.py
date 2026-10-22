"""Same-origin compiled assets only; no runtime compiler, proxy or UI database."""

import html
import os
from pathlib import Path
import secrets
from uuid import UUID

import anyio
from starlette.responses import FileResponse, RedirectResponse, Response
from starlette.staticfiles import StaticFiles


def usersnap_id(value):
    """Only a canonical public widget UUID may cross into document configuration."""
    if not value:
        return None
    try:
        if str(UUID(value)) == value:
            return value
    except (ValueError, AttributeError):
        pass
    raise ValueError('HYPRN_MVP_USERSNAP_GLOBAL_ID must be a canonical lowercase UUID or empty')


class WorkspaceFiles(StaticFiles):
    def __init__(self, *args, usersnap_global_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.usersnap_global_id = usersnap_id(usersnap_global_id)

    def file_response(self, full_path, stat_result, scope, status_code=200):
        # Transformed documents must bypass StaticFiles' conditional 304 response.
        response = FileResponse(full_path, status_code=status_code, stat_result=stat_result)
        if self.usersnap_global_id and response.media_type == 'text/html' and status_code == 200:
            return response
        return super().file_response(full_path, stat_result, scope, status_code)

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        policy = (
            "default-src 'none'; script-src 'self'; style-src 'self'; "
            "img-src 'self' blob:; connect-src 'self'; font-src 'self'; "
            "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        )
        if (
            self.usersnap_global_id
            and isinstance(response, FileResponse)
            and response.status_code == 200
            and response.media_type == 'text/html'
        ):
            nonce = secrets.token_urlsafe(32)
            source = await anyio.to_thread.run_sync(Path(response.path).read_text)
            configuration = (
                '<meta name="hyprn-usersnap" content="'
                + html.escape(self.usersnap_global_id, quote=True)
                + '" data-nonce="'
                + html.escape(nonce, quote=True)
                + '">'
            )
            document = source.replace('</head>', configuration + '</head>', 1).encode('utf-8')
            if document == source.encode('utf-8'):
                raise ValueError('Usersnap requires a compiled HTML document with a closing head')
            response = Response(
                document, media_type='text/html', headers={'Cache-Control': 'no-store'}
            )
            if scope['method'] == 'HEAD':
                response.body = b''  # Retain the corresponding GET representation length.
            policy = (
                f"default-src 'none'; script-src 'self' 'nonce-{nonce}' "
                'https://widget.usersnap.com https://resources.usersnap.com; '
                f"style-src 'self' 'nonce-{nonce}'; "
                "img-src 'self' blob: https://resources.usersnap.com; "
                "connect-src 'self' https://widget.usersnap.com; font-src 'self'; "
                "frame-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
            )
        response.headers['Content-Security-Policy'] = policy
        response.headers['X-Frame-Options'] = 'DENY'
        return response


def mount_workspace(app, directory):
    configured_id = usersnap_id(os.environ.get('HYPRN_MVP_USERSNAP_GLOBAL_ID'))
    if directory.is_dir():
        async def workspace_home(request):
            return RedirectResponse('/ui/', status_code=307)

        app.add_route('/', workspace_home, methods=['GET', 'HEAD'], include_in_schema=False)
        app.mount(
            '/ui',
            WorkspaceFiles(directory=directory, html=True, usersnap_global_id=configured_id),
            name='workspace',
        )
