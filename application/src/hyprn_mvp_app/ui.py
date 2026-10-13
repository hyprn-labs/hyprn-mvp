"""Same-origin compiled assets only; no runtime compiler, proxy or UI database."""
from starlette.staticfiles import StaticFiles


class WorkspaceFiles(StaticFiles):
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers['Content-Security-Policy'] = (
            "default-src 'none'; script-src 'self'; style-src 'self'; "
            "img-src 'self' blob:; connect-src 'self'; font-src 'self'; "
            "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        )
        response.headers['X-Frame-Options'] = 'DENY'
        return response


def mount_workspace(app, directory):
    if directory.is_dir():
        app.mount('/ui', WorkspaceFiles(directory=directory, html=True), name='workspace')
