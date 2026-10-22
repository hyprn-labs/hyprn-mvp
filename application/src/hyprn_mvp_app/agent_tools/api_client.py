"""In-process client of the public API for the tool registry (tooling spec section 2.3).

Requests travel through an ASGI transport into the FastAPI application itself, never into a
composed application, so the full middleware applies (Origin and cross-site request token
checks, body bounds, strict JSON, the agent route allowlist) and no tool can reach ``/mcp`` or
any path outside ``/api/1``. No socket is opened. Each request carries the delegated agent
session cookie, the exact installation ``Origin`` and, on mutations, ``X-CSRF-Token``, as the
browser does. Session values and headers are never logged, stored or returned. Called only
from async code.
"""

from dataclasses import dataclass
import json
from typing import Any

import httpx

COOKIE = 'hyprn_mvp_session'
API_PREFIX = '/api/1/'
METHODS = frozenset({'GET', 'POST', 'PATCH', 'PUT', 'DELETE'})


@dataclass(frozen=True)
class ApiResponse:
    """One API reply: the status, the decoded envelope (``None`` when the body is not JSON)
    and the request id the API assigned."""

    status: int
    body: Any
    request_id: str | None


class ApiClient:
    def __init__(self, api_app, origin):
        if not isinstance(origin, str) or not origin.startswith(('https://', 'http://')):
            raise ValueError('The origin is the installation origin')
        self._origin = origin
        transport = httpx.ASGITransport(app=api_app, raise_app_exceptions=False)
        self._client = httpx.AsyncClient(transport=transport, base_url=origin)

    def __repr__(self):
        return 'ApiClient(' + self._origin + ')'

    async def request(self, session, method, path, json_body=None, params=None):
        """Send ``method path`` (an ``/api/1`` path) under the delegated ``session``, a mapping
        with its ``token`` and ``csrf_token``. Returns an ``ApiResponse``."""
        method = str(method).upper()
        if method not in METHODS:
            raise ValueError('Unsupported method')
        if not isinstance(path, str) or not path.startswith(API_PREFIX) or '..' in path:
            raise ValueError('The client reaches /api/1 paths only')
        headers = {'Origin': self._origin, 'Cookie': COOKIE + '=' + session['token']}
        if method != 'GET':
            headers['X-CSRF-Token'] = session['csrf_token']
        content = None
        if json_body is not None:
            content = json.dumps(json_body, allow_nan=False, ensure_ascii=False).encode()
            headers['Content-Type'] = 'application/json'
        try:
            reply = await self._client.request(
                method, path, headers=headers, content=content, params=params
            )
        finally:
            # The session travels only in this request's header; nothing is kept between calls.
            self._client.cookies.clear()
        try:
            body = reply.json()
        except ValueError:
            body = None
        return ApiResponse(reply.status_code, body, _request_id(body))

    async def aclose(self):
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self.aclose()


def _request_id(body):
    if not isinstance(body, dict):
        return None
    if isinstance(body.get('request_id'), str):
        return body['request_id']
    error = body.get('error')
    if isinstance(error, dict) and isinstance(error.get('request_id'), str):
        return error['request_id']
    return None
