"""Checksummed PostgreSQL schema changes, invoked only by migration authority."""

import hashlib
from pathlib import Path

from .database import Connection

MIGRATIONS = tuple(Path(__file__).with_name('migrations') / name for name in
                   ('0001_core.sql', '0002_domains.sql', '0003_external_identity.sql',
                    '0004_hosted_lifecycle.sql', '0005_session_lock.sql',
                    '0006_retained_fingerprint.sql', '0007_retained_read_cache.sql',
                    '0008_run_listing_projection.sql', '0009_assistant_user_accounts.sql',
                    '0010_operational_execution.sql', '0011_assistant_projection.sql', '0012_analysis_authority.sql',
                    '0013_assistant_provider_sessions.sql', '0014_analysis_recovery.sql', '0015_analysis_preparation_recovery.sql',
                    '0016_native_reconciliation.sql'))


def expected(migration=None):
    return hashlib.sha256((migration or MIGRATIONS[-1]).read_bytes()).hexdigest()


def verify(db):
    rows = db.execute(
        'SELECT version, checksum FROM hyprn_schema_versions ORDER BY version'
    ).fetchall()
    if rows != [{'version': p.stem, 'checksum': expected(p)} for p in MIGRATIONS]:
        raise ValueError('PostgreSQL schema is incompatible; explicit migration required')


def initialize(credentials, *, empty_only=False, identity=None):
    """Initialize a fresh database or verify this exact schema, atomically.

    This deliberately has no automatic current-data transfer or application
    startup path. The migration login owns the schema; request logins do not.
    """
    raw = credentials.connect()
    db = Connection(raw)
    try:
        db.execute('BEGIN')
        db.execute("SET LOCAL lock_timeout='5s'")
        db.execute("SET LOCAL statement_timeout='60s'")
        db.execute('SELECT pg_advisory_xact_lock(68272600)')
        for writer in (68272602, 68272603):
            if not db.execute('SELECT pg_try_advisory_xact_lock(?) AS acquired', (writer,)).fetchone()['acquired']:
                raise ValueError('Refusing migration while a hosted writer is active')
        tables = db.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'").fetchall()
        if empty_only and tables:
            raise ValueError('Refusing initialization of a nonempty database')
        if tables and not any(row['tablename'] == 'hyprn_schema_versions' for row in tables):
            raise ValueError('Refusing to initialize a nonempty unrecognized database')
        db.execute(
            'CREATE TABLE IF NOT EXISTS hyprn_schema_versions('
            'version TEXT PRIMARY KEY, checksum TEXT NOT NULL)'
        )
        rows = db.execute('SELECT version,checksum FROM hyprn_schema_versions ORDER BY version').fetchall()
        known = [{'version': p.stem, 'checksum': expected(p)} for p in MIGRATIONS]
        if rows != known[:len(rows)] or len(rows) > len(known):
            raise ValueError('PostgreSQL schema is incompatible; explicit migration required')
        if not rows and tables:
            raise ValueError('Refusing an empty ledger in an existing database')
        for migration in MIGRATIONS[len(rows):]:
            raw.cursor().execute(migration.read_text())
            db.execute('INSERT INTO hyprn_schema_versions VALUES(?,?)',
                       (migration.stem, expected(migration)))
        if identity is not None:
            if not empty_only or set(identity) != {'installation_id', 'store_id'}:
                raise ValueError('Explicit empty installation identity required')
            db.execute('INSERT INTO hyprn_installation_identity VALUES(1,?,?)',
                       (identity['installation_id'], identity['store_id']))
        raw.commit()
    except BaseException:
        raw.rollback()
        raise
    finally:
        raw.close()
