"""Fixed database owner operations used by a short-lived, separately credentialed image."""

import argparse
import json
import os

from hyprn_mvp_app.hosted_lifecycle import (
    initialize_store, migrate_store, inspect_store, drain_counts, stopped_work_counts,
)
from .runtime import credentials, required


def operation(name, environ):
    identity = (required(environ, 'INSTALLATION_ID'), required(environ, 'APPLICATION_STORE_ID'))
    migration = name in ('initialize', 'migrate', 'stopped-work')
    account = credentials(environ, 'hyprn_migration' if migration else 'hyprn_request',
                          'DB_APP_MIGRATION' if migration else 'DB_APP_REQUEST')
    if name == 'initialize':
        initialize_store(account, *identity)
        return {'application': inspect_store(account, *identity)}
    if name == 'migrate':
        return {'application': migrate_store(account, *identity)}
    if name == 'inspect':
        return {'application': inspect_store(account, *identity)}
    if name == 'stopped-work':
        return stopped_work_counts(account, *identity)
    if name == 'drain':
        return drain_counts(account, *identity)
    raise ValueError('Unknown database operation')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        'operation', choices=('initialize', 'migrate', 'inspect', 'drain', 'stopped-work'))
    args = parser.parse_args(argv)
    try:
        print(json.dumps(operation(args.operation, os.environ), sort_keys=True))
        return 0
    except Exception:
        print(json.dumps({'reason_code': 'database_operation_refused'}))
        return 3


if __name__ == '__main__':
    raise SystemExit(main())
