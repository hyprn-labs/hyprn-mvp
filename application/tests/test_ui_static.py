"""Static assets share the existing host boundary, without exposing source or API authority."""
from test_api import api, ORIGIN
from hyprn_mvp_app.ui import mount_workspace

def test_workspace_static_boundary(api,tmp_path):
    c=api[0];public=tmp_path/'public';public.mkdir()
    (public/'index.html').write_text('<!doctype html><title>Workspace</title>')
    (tmp_path/'private.txt').write_text('not public')
    mount_workspace(c.app,public)
    response=c.get('/ui/')
    assert response.status_code==200 and 'Workspace' in response.text
    policy=response.headers['content-security-policy']
    assert "img-src 'self' blob:;" in policy
    assert "script-src 'self';" in policy
    assert "default-src 'none';" in policy
    assert 'data:' not in policy and 'unsafe-eval' not in policy and 'unsafe-inline' not in policy
    assert policy.count('blob:')==1
    assert "connect-src 'self'" in response.headers['content-security-policy']
    assert "frame-ancestors 'none'" in response.headers['content-security-policy']
    assert response.headers['x-content-type-options']=='nosniff'
    assert c.get('/ui/%2e%2e/private.txt').status_code==404
    assert c.get('/ui/',headers={'Host':'attacker.invalid'}).status_code==403
    assert c.post('/ui/',headers={'Origin':'https://attacker.invalid'}).status_code==403
    assert c.get('/ui/src/Workspace.tsx').status_code==404
