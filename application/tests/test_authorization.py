import sqlite3
import time
import pytest
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
