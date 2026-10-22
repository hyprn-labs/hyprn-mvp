"""Provider-independent hosted sessions; no passwords or identity linking by email."""

from contextlib import contextmanager
from contextvars import ContextVar
import secrets
from urllib.parse import urlsplit

from .auth import Auth, token_hash
from .contracts import DomainError

_verified = ContextVar('hyprn_external_identity', default=None)


@contextmanager
def verified_identity(identity):
    token = _verified.set(identity)
    try:
        yield
    finally:
        _verified.reset(token)


class HostedAuth(Auth):
    hosted = True

    def __init__(self, store, origin):
        parsed = urlsplit(origin)
        if (
            parsed.scheme != 'https'
            or not parsed.hostname
            or parsed.path
            or parsed.query
            or parsed.fragment
            or parsed.username
        ):
            raise ValueError('Hosted authentication requires an explicit HTTPS origin')
        if getattr(store.database, 'dialect', None) != 'postgresql':
            raise ValueError('Hosted authentication requires PostgreSQL')
        super().__init__(store, origin)

    def provision(self, *args):
        raise DomainError('forbidden', 403)

    recover = provision
    login = provision

    def bootstrap(self, identity=None):
        identity = identity or _verified.get()
        if identity is None:
            raise DomainError('unauthenticated', 401)
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        with self.store.authentication_connection(write=True) as db:
            row = db.execute(
                'SELECT * FROM hyprn_external_session(?,?,?,?,?)',
                (
                    identity.issuer,
                    identity.subject,
                    token_hash(token),
                    token_hash(csrf),
                    identity.contact,
                ),
            ).fetchone()
        return dict(row, token=token, csrf_token=csrf)

    def public_profile(self, profile):
        identity = _verified.get()
        contact = identity.contact if identity else None
        return dict(
            profile,
            account_name=contact or 'Hosted account',
            display_name=profile['display_alias'] or contact or 'Member',
        )

    def bind(self, identity, token):
        session = self.authenticate(token)
        with self.store.authentication_connection() as db:
            row = db.execute(
                'SELECT actor_id FROM external_identities WHERE issuer=? AND subject=?',
                (identity.issuer, identity.subject),
            ).fetchone()
        if session['kind'] != 'user' or row is None or row['actor_id'] != session['actor_id']:
            raise DomainError('unauthenticated', 401)

    def invalidate(self, issuer, subject):
        with self.store.authentication_connection(write=True) as db:
            db.execute('SELECT hyprn_invalidate_external(?,?)', (issuer, subject))

    def logout(self, token):
        with self.store.authentication_connection(write=True) as db:
            db.execute('SELECT hyprn_end_external_session(?)', (token_hash(token),))
