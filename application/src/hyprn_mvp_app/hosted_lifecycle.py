"""The application owner's explicit initialization, identity check and bounded drain."""

from .database import Connection
from .migrations import initialize, verify


def store_identity(db, installation_id, store_id):
    rows = db.execute('SELECT installation_id,store_id FROM hyprn_installation_identity').fetchall()
    if rows != [dict(installation_id=installation_id, store_id=store_id)]:
        raise ValueError('Hosted database identity differs; operator recovery required')


def initialize_store(credentials, installation_id, store_id):
    """Create schema and immutable identity in one empty-store transaction."""
    initialize(credentials, empty_only=True,
               identity=dict(installation_id=installation_id, store_id=store_id))


def inspect_store(credentials, installation_id, store_id):
    raw = credentials.connect()
    try:
        db = Connection(raw)
        db.execute('BEGIN READ ONLY')
        db.execute("SET LOCAL statement_timeout='15s'")
        verify(db)
        store_identity(db, installation_id, store_id)
        return [dict(r) for r in db.execute('SELECT version,checksum FROM hyprn_schema_versions ORDER BY version')]
    finally:
        raw.close()


def migrate_store(credentials, installation_id, store_id):
    raw = credentials.connect()
    try:
        store_identity(Connection(raw), installation_id, store_id)
    finally:
        raw.close()
    initialize(credentials)
    return inspect_store(credentials, installation_id, store_id)


def drain_counts(credentials, installation_id, store_id):
    """A shared request lock closes the gap between admission and a later write."""
    raw = credentials.connect()
    try:
        db = Connection(raw)
        db.execute('BEGIN READ ONLY')
        db.execute("SET LOCAL statement_timeout='15s'")
        store_identity(db, installation_id, store_id)
        quiet = db.execute('SELECT pg_try_advisory_lock(68272604) AS quiet').fetchone()['quiet']
        counts = dict(db.execute('SELECT * FROM hyprn_lifecycle_counts()').fetchone())
        return {**counts, 'requests_quiescent': quiet}
    finally:
        raw.close()


def stopped_work_counts(credentials, installation_id, store_id):
    """Read-only upgrade admission separates retained work from remote activity.

    Only the short-lived migration role can inspect all Assistant rows. Local
    owners must already be stopped by the host; unfinished records stay intact.
    """
    raw = credentials.connect()
    try:
        db = Connection(raw)
        db.execute('BEGIN READ ONLY')
        db.execute("SET LOCAL statement_timeout='15s'")
        store_identity(db, installation_id, store_id)
        quiet = db.execute('SELECT pg_try_advisory_lock(68272604) AS quiet').fetchone()['quiet']
        counts = dict(db.execute('SELECT * FROM hyprn_lifecycle_counts()').fetchone())
        active = db.execute(
            'SELECT count(*) AS active FROM assistant_conversations WHERE active_turn IS NOT NULL'
        ).fetchone()['active']
        return {**counts, 'requests_quiescent': quiet, 'active_assistant_turns': active}
    finally:
        raw.close()
