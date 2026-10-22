"""Human display identity. Account names and actor IDs never change with an alias."""

import unicodedata

from .contracts import DomainError


def ensure(db):
    columns = {row['name'] for row in db.execute('PRAGMA table_info(users)')}
    if 'display_alias' not in columns:
        db.execute('ALTER TABLE users ADD COLUMN display_alias TEXT')
    if 'profile_revision' not in columns:
        db.execute('ALTER TABLE users ADD COLUMN profile_revision INTEGER NOT NULL DEFAULT 0')


def display_name(db, actor_id, *, legacy=False):
    """Resolve a person, never the current viewer. Legacy records use the account name."""
    row = db.execute(
        'SELECT username,display_alias FROM users WHERE actor_id=?', (actor_id,)
    ).fetchone()
    return (row['username'] if legacy else row['display_alias'] or row['username']) if row else None


def profile(db, actor_id):
    row = db.execute(
        'SELECT actor_id,username,display_alias,profile_revision FROM users WHERE actor_id=?',
        (actor_id,),
    ).fetchone()
    if row is None:
        raise DomainError('forbidden', 403)
    return dict(
        actor_id=row['actor_id'], account_name=row['username'], display_alias=row['display_alias'],
        display_name=row['display_alias'] or row['username'], revision=row['profile_revision'],
    )


def update(db, actor_id, alias, expected_revision):
    current = profile(db, actor_id)
    if current['revision'] != expected_revision:
        raise DomainError('stale_revision', 409)
    if alias is not None:
        if not isinstance(alias, str) or len(alias) > 128 or any(
            unicodedata.category(char).startswith('C') or char in '\u2028\u2029' for char in alias
        ):
            raise DomainError('invalid_request', 400)
        alias = alias.strip() or None
    db.execute(
        'UPDATE users SET display_alias=?,profile_revision=profile_revision+1 WHERE actor_id=?',
        (alias, actor_id),
    )
    return profile(db, actor_id)
