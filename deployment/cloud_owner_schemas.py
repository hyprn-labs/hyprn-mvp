"""Read-only schema observations from fixed owner paths and reviewed dependencies.

No AiiDA backend is opened: its migrator touches the database even when querying
the version. Scientific source, Rails application startup and migrations never
run here. The host supplies the protected owner receipt on standard input.
"""

from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import sys
from uuid import UUID


def regular(path):
    path = Path(path)
    if (not path.is_file() or path.stat().st_nlink != 1
            or any(p.is_symlink() for p in (path, *path.parents))):
        raise ValueError('Owner file missing or linked')
    return path


def execution(owner):
    from cloud_backup import OWNER_FIELDS, profile_at, read_json
    if set(owner) != OWNER_FIELDS or owner['schema'] != 'hyprn-native-owner/v1':
        raise ValueError('Invalid native owner receipt')
    root = Path(owner['execution_root'])
    regular(root / 'aiida/.aiida/config.json')
    os.environ['AIIDA_PATH'] = str(root / 'aiida')
    from aiida.storage.sqlite_dos.backend import SqliteDosStorage
    profile = profile_at(root, owner['profile'])
    keys = ('profile_uuid', 'repository_uuid', 'computer_uuid', 'code_uuid')
    for key in keys:
        if owner[key] not in (str(UUID(owner[key])), UUID(owner[key]).hex):
            raise ValueError('Invalid native identity')
    identities = {key: owner[key] for key in keys}
    if (profile.uuid != owner['profile_uuid'] or
            read_json(regular(root / 'profile-identity.json')) != dict(identities, profile=owner['profile'])):
        raise ValueError('Native owner identity differs')
    database = regular(root / 'aiida-store/database.sqlite')
    for suffix in ('-wal', '-journal'):
        pending = Path(str(database) + suffix)
        if pending.exists() and (regular(pending).stat().st_size != 0):
            raise ValueError('Native uncheckpointed journal requires reconciliation')
    # The host holds stopped writers. Immutable mode avoids creating SQLite
    # sidecars; journal content is never ignored or checkpointed by this probe.
    with closing(sqlite3.connect(database.as_uri() + '?mode=ro&immutable=1', uri=True)) as db:
        db.execute('PRAGMA query_only=ON')
        db.execute('BEGIN')
        versions = db.execute('SELECT version_num FROM alembic_version').fetchall()
        head = SqliteDosStorage.version_head()
        if not isinstance(head, str) or not head or versions != [(head,)]:
            raise ValueError('Native schema requires explicit migration')
        repository = db.execute('SELECT val FROM db_dbsetting WHERE key=?', ('repository|uuid',)).fetchall()
        if len(repository) != 1 or json.loads(repository[0][0]) != owner['repository_uuid']:
            raise ValueError('Native database repository identity differs')
        for table, key in (('db_dbcomputer', 'computer_uuid'), ('db_dbnode', 'code_uuid')):
            # Upstream SQLite stores UUID strings; accept its two UUID encodings
            # but refuse duplicate identities rather than choosing either row.
            identifier = UUID(owner[key])
            rows = db.execute('SELECT uuid FROM ' + table + ' WHERE uuid IN (?,?)',
                              (str(identifier), identifier.hex)).fetchall()
            if len(rows) != 1:
                raise ValueError('Native retained entity identity missing')
    container = read_json(regular(root / 'aiida-store/container/config.json'))
    if UUID(container['container_id']) != UUID(owner['repository_uuid']):
        raise ValueError('Native object repository identity differs')
    return dict(backend='core.sqlite_dos', version=head, profile=owner['profile'], **identities)


# This is a fixed Ruby program, run in the pinned modeling image with the store
# mounted read-only and networking disabled. It loads sqlite3, never Rails.
MODELING_PROBE = r'''
require 'json'; require 'digest'; require 'sqlite3'
result = {}
[['primary', 'model.sqlite3', 'migrate', 'schema.rb'],
 ['scratch', 'scratch.sqlite3', 'scratch_migrate', 'scratch_schema.rb']].each do |name, file, migrations, schema|
  files = Dir.glob("db/#{migrations}/*.rb").sort
  expected = files.map { |path| File.basename(path).split('_').first }
  raise 'invalid migration inventory' if expected.uniq != expected || expected.any? { |v| !v.match?(/\A[0-9]+\z/) }
  # Rails schema:load stamps its declared version even for scratch, whose
  # migration directory is empty. Parse the declaration without evaluating it.
  baseline = File.read("db/#{schema}").scan(/^ActiveRecord::Schema\[[0-9.]+\]\.define\(version: ([0-9_]+)\) do$/)
  raise 'unknown schema baseline' unless baseline.length == 1
  expected = (expected + [baseline[0][0].delete('_')]).uniq.sort
  path = "/store/#{file}"
  raise 'unsafe modeling database' unless File.file?(path) && !File.symlink?(path)
  ['-wal', '-journal'].each do |suffix|
    raise 'modeling journal requires reconciliation' if File.symlink?(path + suffix) || File.size?(path + suffix)
  end
  db = SQLite3::Database.new("file:#{path}?mode=ro&immutable=1",
                             flags: SQLite3::Constants::Open::READONLY | SQLite3::Constants::Open::URI)
  begin
    db.execute('PRAGMA query_only=ON')
    db.execute('BEGIN')
    actual = db.execute('SELECT version FROM schema_migrations ORDER BY version').flatten
    raise 'modeling schema requires explicit migration' unless actual == expected
    result[name] = {'versions'=>actual, 'sources'=>files.to_h { |path| [path, Digest::SHA256.file(path).hexdigest] },
                    'schema_sha256'=>Digest::SHA256.file("db/#{schema}").hexdigest}
  ensure
    db.close
  end
end
puts JSON.generate(result)
'''


if __name__ == '__main__':
    # -I removes the script directory; only this retained trusted source is added.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    print(json.dumps(execution(json.loads(sys.stdin.read(65537))), sort_keys=True))
