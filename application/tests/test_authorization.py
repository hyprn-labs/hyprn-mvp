import sqlite3
import time
import pytest
import asyncio
import httpx
from hyprn_mvp_app.store import Store, DomainError
from hyprn_mvp_app.auth import Auth
from conftest import LOOPBACK_ORIGIN

@pytest.fixture
def auth(tmp_path): return Auth(Store(tmp_path/"application.sqlite"),LOOPBACK_ORIGIN)

def test_no_default_owner_and_password_hashing(auth):
    with pytest.raises(DomainError,match="unauthenticated"):
        auth.login("owner","password")
    owner=auth.provision("owner","correct horse battery staple")
    with pytest.raises(DomainError,match="reference_conflict"):
        auth.provision("second","a different long password")
    with sqlite3.connect(auth.store.path) as db:
        password_hash=db.execute("SELECT password_hash FROM users").fetchone()[0]
        assert "correct horse" not in password_hash
        assert password_hash.startswith("scrypt$")
    session=auth.login("owner","correct horse battery staple")
    assert auth.authenticate(session["token"])["actor_id"]==owner
    assert auth.authenticate(session["token"])["actor_id"]!=session["token"]

def test_origin_csrf_logout_and_expiry(auth):
    auth.provision("owner","correct horse battery staple")
    session=auth.login("owner","correct horse battery staple")
    for origin,csrf in [(None,session["csrf_token"]),("https://evil.example",session["csrf_token"]),(auth.origin,"wrong")]:
        with pytest.raises(DomainError,match="forbidden"):
            auth.authorize_mutation(session["token"],origin,csrf)
    auth.authorize_mutation(session["token"],auth.origin,session["csrf_token"])
    auth.logout(session["token"])
    with pytest.raises(DomainError,match="unauthenticated"):auth.authenticate(session["token"])
    new=auth.login("owner","correct horse battery staple")
    with sqlite3.connect(auth.store.path) as db:db.execute("UPDATE sessions SET expires_at=0")
    with pytest.raises(DomainError,match="unauthenticated"):auth.authenticate(new["token"])

def test_recovery_keeps_identity_revokes_sessions_and_requires_local_secret(auth):
    owner=auth.provision("owner","correct horse battery staple")
    old=auth.login("owner","correct horse battery staple")
    auth.recover("new secure recovery password")
    with pytest.raises(DomainError,match="unauthenticated"):auth.authenticate(old["token"])
    new=auth.login("owner","new secure recovery password")
    assert auth.authenticate(new["token"])["actor_id"]==owner

def test_login_throttle_and_weak_secret(auth):
    with pytest.raises(DomainError,match="invalid_request"):auth.provision("owner","short")
    auth.provision("owner","correct horse battery staple")
    for _ in range(5):
        with pytest.raises(DomainError,match="unauthenticated"):auth.login("owner","incorrect")
    with pytest.raises(DomainError,match="rate_limited"):auth.login("owner","correct horse battery staple")


def test_self_profile_persists_without_changing_credentials_and_refuses_stale_edits(auth):
    from hyprn_mvp_app.api import create_app
    from hyprn_mvp_app.contracts import uid
    from hyprn_mvp_app import identity

    owner = auth.provision("owner", "correct horse battery staple")
    app = create_app(auth.store, auth, None)

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url=LOOPBACK_ORIGIN) as client:
            assert (await client.get('/api/1/profile')).status_code == 401
            login = await client.post('/api/1/session', headers={'Origin': LOOPBACK_ORIGIN},
                                      json=dict(username='owner', password='correct horse battery staple'))
            data = login.json()['data']
            assert data['profile']['display_name'] == 'owner'
            headers = {'Origin': LOOPBACK_ORIGIN, 'X-CSRF-Token': data['csrf_token']}
            initial = (await client.get('/api/1/profile')).json()['data']
            assert initial['actor_id'] == owner and initial['revision'] == 0
            body = dict(display_alias='  Guérric <engineer>  ', expected_revision=0)
            assert (await client.put('/api/1/profile', json=body)).status_code == 403
            assert (await client.put('/api/1/profile', headers=headers,
                                     json={**body, 'actor_id': uid()})).status_code == 400
            changed = await client.put('/api/1/profile', headers=headers, json=body)
            assert changed.status_code == 200
            assert changed.json()['data']['display_alias'] == 'Guérric <engineer>'
            assert (await client.put('/api/1/profile', headers=headers, json=body)).status_code == 409
            for alias in ['a\nb', '\x00', '\u202ealias', 'x' * 129, True, 4]:
                response = await client.put('/api/1/profile', headers=headers,
                    json=dict(display_alias=alias, expected_revision=1))
                assert response.status_code == 400, response.text
            with Store(auth.store.path).connection() as db:
                assert identity.profile(db, owner)['display_name'] == 'Guérric <engineer>'
            assert auth.login('owner', 'correct horse battery staple')['actor_id'] == owner
            with pytest.raises(DomainError):
                auth.login('Guérric <engineer>', 'correct horse battery staple')
            cleared = await client.put('/api/1/profile', headers=headers,
                json=dict(display_alias='   ', expected_revision=1))
            assert cleared.json()['data']['display_name'] == 'owner'
            assert cleared.json()['data']['display_alias'] is None
            second = uid()
            with auth.store.connection(write=True) as db:
                password = db.execute('SELECT password_hash FROM users WHERE actor_id=?',
                                      (owner,)).fetchone()[0]
                db.execute('INSERT INTO users(actor_id,username,password_hash) VALUES(?,?,?)',
                           (second, 'second', password))
                assert identity.profile(db, second)['display_alias'] is None
            second_login = await client.post('/api/1/session', headers={'Origin': LOOPBACK_ORIGIN},
                json=dict(username='second', password='correct horse battery staple'))
            second_headers = {**headers, 'X-CSRF-Token': second_login.json()['data']['csrf_token']}
            second_profile = await client.put('/api/1/profile', headers=second_headers,
                json=dict(display_alias='Second person', expected_revision=0))
            assert second_profile.json()['data']['actor_id'] == second
            with auth.store.connection() as db:
                assert identity.profile(db, owner)['display_alias'] is None
            sid = auth.store.create_study(owner, uid(), 'Alias isolation')['study_id']
            with auth.store.connection(write=True) as db:
                agent = auth.store.ensure_agent_actor(db, owner, 'claude_managed', 'Assistant')
                delegation = auth.store.create_delegation(
                    db, agent, sid, 'writer', ('read', 'draft', 'record'), time.time() + 3600)
            session = auth.mint_agent_session(delegation['delegation_id'])
            client.cookies.set('hyprn_mvp_session', session['token'])
            assert (await client.get('/api/1/profile')).status_code == 403
            assert (await client.put('/api/1/profile',
                headers={**headers, 'X-CSRF-Token': session['csrf_token']},
                json=dict(display_alias='Agent name', expected_revision=2))).status_code == 403

    asyncio.run(exercise())


def test_legacy_user_table_gains_alias_without_changing_existing_rows(tmp_path):
    from hyprn_mvp_app import identity
    path = tmp_path / 'legacy.sqlite'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE users(actor_id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, '
                   'password_hash TEXT NOT NULL, failures INTEGER DEFAULT 0, locked_until REAL DEFAULT 0)')
        db.execute("INSERT INTO users VALUES('legacy','Original name','hash',2,0)")
    store = Store(path)
    Store(path)
    with store.connection() as db:
        assert identity.profile(db, 'legacy')['display_name'] == 'Original name'
        assert db.execute('SELECT password_hash,failures FROM users').fetchone()[:] == ('hash', 2)
