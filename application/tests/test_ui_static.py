"""Static assets share the existing host boundary, without exposing source or API authority."""

import re

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

from test_api import api, ORIGIN
from hyprn_mvp_app.ui import mount_workspace


def test_workspace_static_boundary(api, tmp_path, monkeypatch):
    monkeypatch.delenv('HYPRN_MVP_USERSNAP_GLOBAL_ID', raising=False)
    c = api[0]
    public = tmp_path / 'public'
    public.mkdir()
    (public / 'index.html').write_text('<!doctype html><title>Workspace</title>')
    (tmp_path / 'private.txt').write_text('not public')
    mount_workspace(c.app, public)
    response = c.get('/ui/')
    assert response.status_code == 200 and 'Workspace' in response.text
    policy = response.headers['content-security-policy']
    assert "img-src 'self' blob:;" in policy
    assert "script-src 'self';" in policy
    assert "default-src 'none';" in policy
    assert 'data:' not in policy and 'unsafe-eval' not in policy and 'unsafe-inline' not in policy
    assert policy.count('blob:') == 1
    assert "connect-src 'self'" in response.headers['content-security-policy']
    assert "frame-ancestors 'none'" in response.headers['content-security-policy']
    assert response.headers['x-content-type-options'] == 'nosniff'
    assert c.get('/ui/%2e%2e/private.txt').status_code == 404
    assert c.get('/ui/', headers={'Host': 'attacker.invalid'}).status_code == 403
    assert c.post('/ui/', headers={'Origin': 'https://attacker.invalid'}).status_code == 403
    assert c.get('/ui/src/Workspace.tsx').status_code == 404


WIDGET = '9c4a930c-b62f-4b89-bca3-260ec022694a'


@pytest.fixture
def static_client(tmp_path, monkeypatch):
    public = tmp_path / 'public'
    public.mkdir()
    (public / 'index.html').write_text(
        '<!doctype html><html><head><title>Workspace</title></head><body></body></html>'
    )
    (public / 'asset.js').write_text('window.asset = true;')
    (tmp_path / 'private.txt').write_text('private')

    def make(value):
        if value is None:
            monkeypatch.delenv('HYPRN_MVP_USERSNAP_GLOBAL_ID', raising=False)
        else:
            monkeypatch.setenv('HYPRN_MVP_USERSNAP_GLOBAL_ID', value)
        app = Starlette()
        mount_workspace(app, public)
        return TestClient(app)

    return make


def test_site_root_opens_workspace_without_redirecting_api_or_external_targets(static_client):
    client = static_client(None)
    for method in ('get', 'head'):
        response = getattr(client, method)('/', follow_redirects=False)
        assert response.status_code == 307
        assert response.headers['location'] == '/ui/'
    assert client.get('/').url.path == '/ui/'
    assert client.get('/?next=https://attacker.invalid', follow_redirects=False).headers[
        'location'
    ] == '/ui/'
    assert client.get('/unknown').status_code == 404
    assert client.get('/api/1/unknown').status_code == 404
    assert client.post('/', follow_redirects=False).status_code == 405


def test_workspace_landing_keeps_application_host_and_api_authorization(tmp_path, monkeypatch):
    from hyprn_mvp_app.api import create_app
    from hyprn_mvp_app.auth import Auth
    from hyprn_mvp_app.store import Store

    monkeypatch.delenv('HYPRN_MVP_USERSNAP_GLOBAL_ID', raising=False)
    store = Store(tmp_path / 'app.sqlite')
    app = create_app(store, Auth(store, ORIGIN), None, environ={})
    public = tmp_path / 'public'
    public.mkdir()
    (public / 'index.html').write_text('<!doctype html><title>Workspace</title>')
    mount_workspace(app, public)
    with TestClient(app, base_url=ORIGIN) as client:
        assert client.get('/').status_code == 200
        assert client.get('/', headers={'Host': 'attacker.invalid'}).status_code == 403
        assert client.get('/api/1/studies').status_code == 401
        assert client.get('/api/1/unknown').status_code == 404


@pytest.mark.parametrize('value', [None, ''])
def test_unconfigured_documents_keep_policy_and_static_cache(static_client, value):
    client = static_client(value)
    response = client.get('/ui/')
    assert 'hyprn-usersnap' not in response.text
    assert 'usersnap.com' not in response.headers['content-security-policy']
    assert 'nonce-' not in response.headers['content-security-policy']
    assert (
        client.get('/ui/', headers={'If-None-Match': response.headers['etag']}).status_code == 304
    )


@pytest.mark.parametrize(
    'value',
    [
        WIDGET.upper(),
        ' ' + WIDGET,
        WIDGET + ' ',
        WIDGET.replace('-', ''),
        'https://attacker.invalid',
        '"><script>alert(1)</script>',
        'x' * 1000,
    ],
)
def test_configuration_rejects_noncanonical_or_injectable_values(static_client, value):
    with pytest.raises(ValueError, match='HYPRN_MVP_USERSNAP_GLOBAL_ID'):
        static_client(value)


def test_enabled_documents_have_fresh_coherent_uncacheable_nonces(static_client, monkeypatch):
    client = static_client(WIDGET)
    monkeypatch.setenv('HYPRN_MVP_USERSNAP_GLOBAL_ID', 'invalid-after-mount')
    nonces = []
    for headers in (
        {},
        {},
        {'If-None-Match': '*'},
        {'If-Modified-Since': 'Wed, 31 Dec 2098 23:59:59 GMT'},
        {'Range': 'bytes=0-20'},
    ):
        response = client.get('/ui/', headers=headers)
        assert response.status_code == 200
        assert response.headers['content-type'] == 'text/html; charset=utf-8'
        assert int(response.headers['content-length']) == len(response.content)
        assert response.headers['cache-control'] == 'no-store'
        assert 'etag' not in response.headers and 'last-modified' not in response.headers
        assert response.text.count('name="hyprn-usersnap"') == 1
        assert f'content="{WIDGET}"' in response.text
        nonce = re.search(r'data-nonce="([A-Za-z0-9_-]{43})"', response.text).group(1)
        nonces.append(nonce)
        policy = response.headers['content-security-policy']
        assert policy.count(f"'nonce-{nonce}'") == 2
        assert "font-src 'self';" in policy and "frame-src 'self';" in policy
        assert "frame-ancestors 'none'" in policy
        assert 'unsafe-inline' not in policy and 'unsafe-eval' not in policy
        assert response.headers['x-frame-options'] == 'DENY'
    assert len(set(nonces)) == len(nonces)
    head = client.head('/ui/')
    assert head.status_code == 200 and head.content == b''
    assert int(head.headers['content-length']) == len(response.content)
    assert head.headers['cache-control'] == 'no-store'
    assert (
        re.search(r"'nonce-([^']+)'", head.headers['content-security-policy']).group(1)
        not in nonces
    )
    assert client.get('/ui/index.html').text.count('name="hyprn-usersnap"') == 1


def test_enabled_assets_and_refusals_remain_static(static_client):
    client = static_client(WIDGET)
    response = client.get('/ui/asset.js')
    assert response.status_code == 200
    assert response.text == 'window.asset = true;'
    assert 'usersnap.com' not in response.headers['content-security-policy']
    assert (
        client.get('/ui/asset.js', headers={'If-None-Match': response.headers['etag']}).status_code
        == 304
    )
    assert client.head('/ui/asset.js').content == b''
    assert client.get('/ui/missing').status_code == 404
    assert client.get('/ui/%2e%2e/private.txt').status_code == 404
    assert client.get('/ui/src/Workspace.tsx').status_code == 404
    assert client.post('/ui/').status_code == 405
