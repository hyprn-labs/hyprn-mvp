"""Hosted sessions bind verified issuer/subject to isolated PostgreSQL actors."""

from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
from pathlib import Path
import sys
from uuid import uuid4
import httpx

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'editions/cloud/src'))
from hosted_fixture import postgres_fixture, hosted_http
from hyprn_mvp_app.store import Store
from hyprn_mvp_cloud.access import VerifiedIdentity
from http_contract import assert_http

SPEC = json.loads((Path(__file__).resolve().parents[2] / 'contracts/hyprn-mvp.openapi.yaml').read_text())


def test_external_identity_bootstrap_is_atomic(tmp_path):
    assert importlib.util.find_spec('hyprn_mvp_app.external_identity') is not None, (
        'Hosted bootstrap must exist'
    )
    from hyprn_mvp_app.external_identity import HostedAuth

    with postgres_fixture() as fixture:
        store = Store.postgres(fixture['request'], fixture['auth'], artifact_root=tmp_path)
        auth = HostedAuth(store, 'https://staging.hyprn.ai')
        identity = VerifiedIdentity('https://synthetic.cloudflareaccess.com', 'person-a')
        with ThreadPoolExecutor(max_workers=4) as pool:
            sessions = list(pool.map(lambda _: auth.bootstrap(identity), range(4)))
        assert len({s['actor_id'] for s in sessions}) == 1
        other = auth.bootstrap(VerifiedIdentity('https://another.cloudflareaccess.com', 'person-a'))
        assert other['actor_id'] != sessions[0]['actor_id']
        restarted = HostedAuth(Store.postgres(fixture['request'], fixture['auth'], artifact_root=tmp_path),
                               'https://staging.hyprn.ai')
        assert restarted.bootstrap(identity)['actor_id'] == sessions[0]['actor_id']


@pytest.fixture(scope='module')
def ingress(tmp_path_factory):
    with hosted_http(tmp_path_factory.mktemp('hosted-http')) as fixture:
        yield fixture


def client(ingress, subject='person-a'):
    return httpx.Client(
        base_url=ingress['origin'],
        verify=False,
        headers={
            'Cf-Access-Jwt-Assertion': ingress['assertion'](subject),
            'Origin': ingress['origin'],
        },
    )


def sign_in(client):
    response = client.post('/api/1/session/external', json={})
    assert response.status_code == 200, response.text
    assert_http(SPEC, '/session/external', 'post', response)
    cookie = response.headers['set-cookie'].lower()
    assert 'secure' in cookie and 'httponly' in cookie and 'samesite=strict' in cookie
    session = response.json()['data']
    client.headers['X-CSRF-Token'] = session['csrf_token']
    return session


def test_two_admitted_people_remain_private_at_https_boundary(ingress):
    with client(ingress) as a, client(ingress, 'person-b') as b:
        sa, sb = sign_in(a), sign_in(b)
        assert sa['actor_id'] != sb['actor_id']
        studies = []
        for c, name in ((a, 'private A'), (b, 'private B')):
            response = c.post('/api/1/studies', json={'command_id': str(uuid4()), 'name': name})
            assert response.status_code == 201, response.text
            studies.append(response.json()['data'])
        for c, own, foreign in ((a, studies[0], studies[1]), (b, studies[1], studies[0])):
            assert [s['study_id'] for s in c.get('/api/1/studies').json()['data']] == [
                own['study_id']
            ]
            assert c.get('/api/1/studies/' + foreign['study_id']).status_code == 404
        b.cookies.set(
            'hyprn_mvp_session',
            a.cookies.get('hyprn_mvp_session'),
            domain='127.0.0.1',
            path='/api/1',
        )
        denied = b.get('/api/1/studies')
        assert denied.status_code == 401 and 'private A' not in denied.text


@pytest.mark.parametrize(
    'headers',
    [
        {},
        {'Cf-Access-Jwt-Assertion': 'invalid'},
        {'X-Hyprn-Actor': 'person-a', 'X-Forwarded-User': 'person-a', 'X-Internal-Request': 'true'},
    ],
)
def test_network_identity_headers_cannot_bypass_access(ingress, headers):
    with httpx.Client(base_url=ingress['origin'], verify=False) as c:
        response = c.get('/api/1/session/mode', headers=headers)
        assert response.status_code == 401
        assert response.headers['cache-control'] == 'no-store'
        assert_http(SPEC, '/session/mode', 'get', response)


def test_origin_csrf_password_logout_and_invalidation(ingress):
    with client(ingress, 'mutation-person') as c:
        assert (
            c.post(
                '/api/1/session/external', headers={'Origin': 'https://evil.invalid'}, json={}
            ).status_code
            == 403
        )
        session = sign_in(c)
        assert (
            c.post(
                '/api/1/session',
                json={'username': 'owner', 'password': 'correct horse battery staple'},
            ).status_code
            == 403
        )
        assert (
            c.post(
                '/api/1/studies',
                headers={'X-CSRF-Token': ''},
                json={'command_id': str(uuid4()), 'name': 'bad'},
            ).status_code
            == 403
        )
        token = c.cookies.get('hyprn_mvp_session')
        assert c.delete('/api/1/session').status_code == 200
        assert (
            c.get('/api/1/studies', headers={'Cookie': 'hyprn_mvp_session=' + token}).status_code
            == 401
        )
        c.cookies.clear()
        sign_in(c)
        ingress['auth'].invalidate(ingress['issuer'], 'mutation-person')
        assert c.get('/api/1/studies').status_code == 401


def test_authentication_role_has_only_narrow_write_functions(ingress):
    from hyprn_mvp_app.database import DatabasePermissionDenied

    for sql in (
        "INSERT INTO users(actor_id,username) VALUES('bad','bad')",
        'DELETE FROM external_identities',
        "UPDATE sessions SET actor_id='bad'",
    ):
        with pytest.raises(DatabasePermissionDenied):
            with ingress['store'].authentication_connection(write=True) as db:
                db.execute(sql)


@pytest.mark.parametrize(
    'claims',
    [
        {'aud': 'foreign'},
        {'iss': 'https://other.invalid'},
        {'exp': 1},
        {'nbf': 2**40},
        {'iat': 2**40},
    ],
)
def test_invalid_signed_assertion_is_denied_before_session_bootstrap(ingress, claims):
    with client(ingress) as c:
        response = c.post(
            '/api/1/session/external',
            json={},
            headers={'Cf-Access-Jwt-Assertion': ingress['assertion']('denied', **claims)},
        )
        assert response.status_code == 401


def test_same_contact_never_merges_distinct_subjects(ingress):
    actors = []
    for person in ('same-email-a', 'same-email-b'):
        with client(ingress, person) as c:
            c.headers['Cf-Access-Jwt-Assertion'] = ingress['assertion'](
                person, email='shared@example.invalid'
            )
            session = sign_in(c)
            assert session['profile']['account_name'] == 'shared@example.invalid'
            actors.append(session['actor_id'])
    assert len(set(actors)) == 2


def test_inner_delegated_api_works_but_network_agent_cookie_is_refused(ingress):
    import asyncio
    import time
    from hyprn_mvp_app.database import actor_scope
    from hyprn_mvp_app.agent_tools.api_client import ApiClient

    with client(ingress, 'delegating-person') as c:
        actor = sign_in(c)['actor_id']
        study = c.post(
            '/api/1/studies', json={'command_id': str(uuid4()), 'name': 'Delegated private'}
        ).json()['data']
        store, auth = ingress['store'], ingress['auth']
        with actor_scope(actor):
            with store.connection(write=True) as db:
                agent = store.ensure_agent_actor(db, actor, 'claude_managed', 'Embedded assistant')
                grant = store.create_delegation(
                    db, agent, study['study_id'], 'reader', {'read'}, time.time() + 600
                )
            session = auth.mint_agent_session(grant['delegation_id'])

        async def exercise():
            async with ApiClient(ingress['app'], ingress['origin']) as inner:
                reply = await inner.request(session, 'GET', '/api/1/studies/' + study['study_id'])
                assert reply.status == 200
                assert reply.body['data']['name'] == 'Delegated private'

        asyncio.run(exercise())
        denied = c.get(
            '/api/1/studies/' + study['study_id'],
            headers={
                'Cookie': 'hyprn_mvp_session=' + session['token'],
                'X-Internal-Request': 'true',
            },
        )
        assert denied.status_code == 401
        auth.invalidate(ingress['issuer'], 'delegating-person')
        from hyprn_mvp_app.contracts import DomainError

        with pytest.raises(DomainError):
            auth.authenticate(session['token'])
