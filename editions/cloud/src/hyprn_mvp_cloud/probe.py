"""Read-only product/database compatibility probe, never an HTTP bypass."""

import json
import os
from .runtime import open_store, host_record, required


def inspect(environ):
    store = open_store(environ)
    with store.connection() as db:
        versions = [dict(row) for row in db.execute(
            'SELECT version, checksum FROM hyprn_schema_versions ORDER BY version')]
    return {'application': versions}


if __name__ == '__main__':
    print(json.dumps(inspect(os.environ), sort_keys=True))
