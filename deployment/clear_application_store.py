"""Explicit stopped-staging reset; never called by application startup or clients.

The operator must separately prove stopped writers and a completed backup. This
transaction verifies the exact old ledger and store identity, then replaces only
migration-owned public objects. Roles, credentials and schema grants stay intact.
"""


def identifier(value):
    return '"' + value.replace('"', '""') + '"'


def clear_and_initialize(credentials, *, installation_id, store_id, previous, migrations):
    from hyprn_mvp_app.migrations import expected

    raw = credentials.connect()
    try:
        cur = raw.cursor()
        cur.execute('BEGIN')
        cur.execute("SET LOCAL lock_timeout='5s'")
        cur.execute("SET LOCAL statement_timeout='60s'")
        cur.execute('SELECT pg_advisory_xact_lock(68272600)')
        for lock in (68272602, 68272603, 68272604):
            cur.execute('SELECT pg_try_advisory_xact_lock(?)', (lock,))
            if tuple(cur.fetchone()) != (True,):
                raise ValueError('active_writer')
        cur.execute('SELECT installation_id,store_id FROM hyprn_installation_identity')
        if [tuple(row) for row in cur.fetchall()] != [(installation_id, store_id)]:
            raise ValueError('store_identity_changed')
        cur.execute('SELECT version,checksum FROM hyprn_schema_versions ORDER BY version')
        if [tuple(row) for row in cur.fetchall()] != [tuple(row) for row in previous]:
            raise ValueError('schema_ledger_changed')
        cur.execute("SELECT current_user")
        if tuple(cur.fetchone()) != ('hyprn_migration',):
            raise ValueError('migration_role_required')
        cur.execute("SELECT c.relname,c.relkind,pg_get_userbyid(c.relowner) "
                    "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                    "WHERE n.nspname='public'")
        relations = cur.fetchall()
        if any(owner != 'hyprn_migration' or kind not in ('r', 'i', 'S')
               for _, kind, owner in relations):
            raise ValueError('unexpected_public_object')
        cur.execute("SELECT p.proname,pg_get_function_identity_arguments(p.oid),"
                    "pg_get_userbyid(p.proowner) FROM pg_proc p JOIN pg_namespace n "
                    "ON n.oid=p.pronamespace WHERE n.nspname='public'")
        functions = cur.fetchall()
        if any(owner != 'hyprn_migration' for _, _, owner in functions):
            raise ValueError('unexpected_function_owner')
        for name, kind, _ in relations:
            if kind == 'r':
                cur.execute('DROP TABLE public.' + identifier(name) + ' CASCADE')
        for name, arguments, _ in functions:
            cur.execute('DROP FUNCTION IF EXISTS public.' + identifier(name) +
                        '(' + arguments + ') CASCADE')
        cur.execute("SELECT count(*) FROM pg_class c JOIN pg_namespace n "
                    "ON n.oid=c.relnamespace WHERE n.nspname='public'")
        if tuple(cur.fetchone()) != (0,):
            raise ValueError('public_schema_not_empty')
        cur.execute('CREATE TABLE hyprn_schema_versions('
                    'version TEXT PRIMARY KEY,checksum TEXT NOT NULL)')
        for migration in migrations:
            cur.execute(migration.read_text())
            cur.execute('INSERT INTO hyprn_schema_versions VALUES(?,?)',
                        (migration.stem, expected(migration)))
        cur.execute('INSERT INTO hyprn_installation_identity VALUES(1,?,?)',
                    (installation_id, store_id))
        raw.commit()
        return {'initialized': True, 'application_schema': len(migrations),
                'studies': 0, 'user_spending_reset': True}
    except BaseException:
        raw.rollback()
        raise
    finally:
        raw.close()
