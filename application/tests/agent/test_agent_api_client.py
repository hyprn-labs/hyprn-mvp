"""In-process API client: tools reach ``/api/1`` through the real middleware with no socket,
see exactly what the browser path sees for the same session, send the session cookie, the
exact Origin and the cross-site request token only on mutations, and can never reach ``/mcp``
or any path outside ``/api/1``. Fresh synthetic stores only; no modeling service.
"""

import asyncio
import socket
import time
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from conftest import LOOPBACK_ORIGIN
from hyprn_mvp_app import auth as auth_module
from hyprn_mvp_app.agent_tools.api_client import ApiClient
from hyprn_mvp_app.api import create_app
from hyprn_mvp_app.auth import Auth
from hyprn_mvp_app.contracts import DomainError
from hyprn_mvp_app.store import Store

ORIGIN = LOOPBACK_ORIGIN
PASSWORD = 'correct horse battery staple'
COOKIE = 'hyprn_mvp_session'
WRITER_EFFECTS = ('read', 'draft', 'record', 'submit', 'outside_study')


def uid():
    return str(uuid4())


class UnavailableModeling:
    def call(self, *_, **__):
        raise DomainError('backend_unavailable', 503, outcome='unknown')


@pytest.fixture
def env(tmp_path):
    store = Store(tmp_path / 'client.sqlite')
    auth = Auth(store, ORIGIN)
    actors = {name: uid() for name in ('owner', 'writer')}
    digest = auth_module.password_hash(PASSWORD)
    with store.connection(write=True) as db:
        for name, actor in actors.items():
            db.execute(
                'INSERT INTO users(actor_id,username,password_hash) VALUES(?,?,?)',
                (actor, name, digest),
            )
    app = create_app(store, auth, UnavailableModeling())
    owner = TestClient(app, base_url=ORIGIN)
    signed = owner.post(
        '/api/1/session', json=dict(username='owner', password=PASSWORD), headers={'Origin': ORIGIN}
    )
    owner.headers.update({'Origin': ORIGIN, 'X-CSRF-Token': signed.json()['data']['csrf_token']})
    studies = []
    for name in ('Delegated', 'Other'):
        created = owner.post('/api/1/studies', json=dict(command_id=uid(), name=name))
        assert created.status_code == 201, created.text
        studies.append(created.json()['data'])
    sid = studies[0]['study_id']
    revision = studies[0]['revision']
    store.set_membership(actors['owner'], sid, uid(), revision, actors['writer'], 'writer')
    with store.connection(write=True) as db:
        agent = store.ensure_agent_actor(db, actors['writer'], 'local_mcp', 'Coding agent (local)')
        delegation = store.create_delegation(
            db, agent, sid, 'writer', WRITER_EFFECTS, time.time() + 3600
        )
    agent_session = auth.mint_agent_session(delegation['delegation_id'])
    writer = TestClient(app, base_url=ORIGIN)
    signed = writer.post(
        '/api/1/session',
        json=dict(username='writer', password=PASSWORD),
        headers={'Origin': ORIGIN},
    )
    human_session = {
        'token': writer.cookies[COOKIE],
        'csrf_token': signed.json()['data']['csrf_token'],
    }
    return dict(
        app=app,
        sid=sid,
        other=studies[1]['study_id'],
        sessions={'agent': agent_session, 'human': human_session},
    )


def sampled_routes(env):
    s = '/api/1/studies/' + env['sid']
    stale = dict(command_id=uid(), expected_revision='0' * 64, name='Renamed')
    return [
        ('GET', '/api/1/capabilities', None, None),
        ('GET', s + '/runs', None, None),
        ('GET', s + '/commands/' + uid(), None, {'category': 'evidence'}),
        ('GET', s, None, None),
        ('GET', s + '/evidence', None, None),
        ('GET', s + '/run-status', None, {'run_id': uid()}),
        ('GET', '/api/1/studies', None, None),
        ('POST', s + '/evidence', dict(command_id=uid(), kind='unknown'), None),
        ('PATCH', s, stale, None),
        ('GET', '/api/1/studies/' + env['other'] + '/runs', None, None),
    ]


def without_request_id(body):
    body = dict(body)
    body.pop('request_id', None)
    if isinstance(body.get('error'), dict):
        body['error'] = {k: v for k, v in body['error'].items() if k != 'request_id'}
    return body


def refuse(*_, **__):
    raise AssertionError('a socket was opened')


def test_in_process_client_matches_the_browser_path_and_opens_no_socket(env, monkeypatch):
    routes = sampled_routes(env)
    loop = asyncio.new_event_loop()  # its self-pipe exists before sockets are refused
    try:
        with monkeypatch.context() as patch:
            for name in ('socket', 'create_connection', 'socketpair'):
                patch.setattr(socket, name, refuse)

            async def through_client():
                results = {}
                async with ApiClient(env['app'], ORIGIN) as client:
                    for who, session in env['sessions'].items():
                        for method, path, body, params in routes:
                            reply = await client.request(session, method, path, body, params)
                            assert reply.request_id, (who, method, path)
                            results[who, method, path] = (
                                reply.status,
                                without_request_id(reply.body),
                            )
                return results

            in_process = loop.run_until_complete(through_client())
    finally:
        loop.close()
    statuses = set()
    for who, session in env['sessions'].items():
        browser = TestClient(env['app'], base_url=ORIGIN)
        browser.cookies.set(COOKIE, session['token'])
        browser.headers.update({'Origin': ORIGIN, 'X-CSRF-Token': session['csrf_token']})
        for method, path, body, params in routes:
            reply = browser.request(method, path, json=body, params=params)
            expected = (reply.status_code, without_request_id(reply.json()))
            assert in_process[who, method, path] == expected, (who, method, path)
            statuses.add((who, reply.status_code))
    # The sample covers allowed reads, refusals and not-found answers for both principals.
    assert {
        ('agent', 200),
        ('agent', 403),
        ('agent', 404),
        ('human', 200),
        ('human', 400),
    } <= statuses


def test_the_client_reaches_only_api_paths_and_never_mcp(env):
    async def attempts():
        async with ApiClient(env['app'], ORIGIN) as client:
            session = env['sessions']['agent']
            for path in ('/mcp', '/mcp/', '/api/1/../mcp', 'http://127.0.0.1:19999/mcp', '/api/1'):
                with pytest.raises(ValueError):
                    await client.request(session, 'POST', path, {})
            with pytest.raises(ValueError):
                await client.request(session, 'TRACE', '/api/1/capabilities')

    asyncio.run(attempts())
    with pytest.raises(ValueError):
        ApiClient(env['app'], 'ftp://127.0.0.1')


def test_the_client_sends_cookie_and_origin_and_the_csrf_token_only_on_mutations():
    async def echo(request):
        body = await request.body()
        headers = {
            k: request.headers.get(k) for k in ('cookie', 'origin', 'x-csrf-token', 'content-type')
        }
        return JSONResponse({'request_id': 'r1', 'headers': headers, 'body': body.decode()})

    app = Starlette(routes=[Route('/api/1/echo', echo, methods=['GET', 'POST'])])
    session = {'token': 'session-' + uid(), 'csrf_token': 'csrf-' + uid()}

    async def calls():
        async with ApiClient(app, ORIGIN) as client:
            assert session['token'] not in repr(client)
            read = await client.request(session, 'GET', '/api/1/echo')
            write = await client.request(session, 'POST', '/api/1/echo', {'b': 1})
            again = await client.request(
                {'token': 'other', 'csrf_token': 'x'}, 'GET', '/api/1/echo'
            )
            return read, write, again

    read, write, again = asyncio.run(calls())
    assert read.status == 200 and read.request_id == 'r1'
    assert read.body['headers'] == {
        'cookie': COOKIE + '=' + session['token'],
        'origin': ORIGIN,
        'x-csrf-token': None,
        'content-type': None,
    }
    assert write.body['headers']['x-csrf-token'] == session['csrf_token']
    assert write.body['headers']['content-type'] == 'application/json'
    assert write.body['body'] == '{"b": 1}'
    # Nothing of one call's session is carried into the next.
    assert again.body['headers']['cookie'] == COOKIE + '=other'
