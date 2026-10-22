"""Stopped-owner file snapshots, not a complete hosted backup.

The host must close admission, settle accepted operations and stop all writers
before entering ``native_hold``. It retains its deployment fence throughout.
This adapter holds the executor and AiiDA locks until its caller leaves the
context, so the same hold can encompass an independently verified PostgreSQL
backup. No PostgreSQL receipt, cloud operation or coherent-set success is invented.
The layout adapter is restricted to the exact versions in the native lock.
"""

from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import sqlite3
import stat
import time
from uuid import UUID


SCHEMA = 'hyprn-owner-files-snapshot/v1'
TOOLS = {'aiida-core': '2.9.3', 'disk-objectstore': '1.5.0'}
ROOTS = {'execution', 'modeling', 'artifacts'}
SQLITE = {'execution/aiida-store/database.sqlite',
          'execution/aiida-store/container/packs.idx',
          'modeling/model.sqlite3', 'modeling/scratch.sqlite3'}
IDENTITY_FIELDS = {'installation_id', 'release_sha256', 'config_sha256', 'store_ids'}
OWNER_FIELDS = {'schema', 'installation_id', 'store_id', 'execution_root', 'profile',
                'profile_uuid', 'repository_uuid', 'computer_uuid', 'code_uuid',
                'release_sha256', 'config_sha256'}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def read_json(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate snapshot field')
            result[key] = value
        return result
    def invalid(_value):
        raise ValueError('Nonfinite snapshot field')
    return json.loads(path.read_bytes(), object_pairs_hook=pairs, parse_constant=invalid)


def safe_path(value):
    path = Path(value)
    if (not path.is_absolute() or '..' in path.parts
            or any(part.is_symlink() for part in (path, *path.parents))):
        raise ValueError('Explicit unlinked absolute path required')
    return path


def regular(path):
    info = safe_path(path).lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError('Only unlinked regular snapshot files are supported')
    return info


def check_tools():
    if any(version(name) != expected for name, expected in TOOLS.items()):
        raise ValueError('Unsupported native storage version')


def check_identity(identity, owner, roots):
    if (set(identity) != IDENTITY_FIELDS or set(owner) != OWNER_FIELDS
            or owner['schema'] != 'hyprn-native-owner/v1'
            or set(identity['store_ids']) != {'application', 'modeling', 'execution'}
            or any(not isinstance(value, str) or not value for value in identity['store_ids'].values())
            or owner['installation_id'] != identity['installation_id']
            or owner['store_id'] != identity['store_ids']['execution']
            or owner['execution_root'] != str(roots['execution'])
            or owner['release_sha256'] != identity['release_sha256']):
        raise ValueError('Snapshot owner identity mismatch')
    for digest in (identity['release_sha256'], identity['config_sha256'], owner['config_sha256']):
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
            raise ValueError('Invalid snapshot identity digest')
    for key in ('profile_uuid', 'repository_uuid', 'computer_uuid', 'code_uuid'):
        UUID(owner[key])


def source_roots(roots):
    if set(roots) != ROOTS:
        raise ValueError('All file-owner roots are required')
    result = {key: safe_path(value) for key, value in roots.items()}
    if any(not path.is_dir() for path in result.values()):
        raise ValueError('File-owner roots must exist')
    values = list(result.values())
    if any(a == b or a in b.parents or b in a.parents
           for index, a in enumerate(values) for b in values[index + 1:]):
        raise ValueError('File-owner roots must be disjoint')
    return result


def profile_at(root, name, *, original_root=None):
    """Read a single brokerless profile; never import a candidate component."""
    from aiida.manage.configuration.profile import Profile
    path = root / 'aiida/.aiida/config.json'
    regular(path)
    config = read_json(path)
    if config.get('default_profile') is not None or set(config.get('profiles', {})) != {name}:
        raise ValueError('Unexpected native profile configuration')
    data = config['profiles'][name]
    expected = str((original_root or root) / 'aiida-store')
    if (data.get('storage') != {'backend': 'core.sqlite_dos', 'config': {'filepath': expected}}
            or data.get('process_control', {}).get('backend') is not None):
        raise ValueError('Unsupported native profile storage')
    data = dict(data, storage={'backend': 'core.sqlite_dos', 'config': {'filepath': str(root / 'aiida-store')}})
    return Profile(name, data)


@dataclass
class NativeHold:
    root: Path
    profile: object
    deadline: float
    active: bool = False

    def check(self):
        if not self.active:
            raise ValueError('Native owner hold is not active')
        if time.monotonic() >= self.deadline:
            raise TimeoutError('Owner snapshot deadline exceeded')


@contextmanager
def native_hold(execution_root, profile_name, *, timeout, profile_source=None):
    """Hold both real locks across the caller's entire cross-store operation.

    ``profile_source`` is used only for an already validated empty-store restore.
    This context is process-global because AiiDA's configuration resolver is so;
    the lifecycle invokes it in a dedicated pinned-native-interpreter process.
    """
    if type(timeout) not in (int, float) or not 0 < timeout <= 3600:
        raise ValueError('Bounded owner timeout required')
    check_tools()
    root = safe_path(execution_root)
    safe_path(root / 'aiida/.aiida/access')
    fd = os.open(root / 'executor.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError('Unlinked native executor lock required')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        root_info = root.stat()
        if (info.st_uid, info.st_gid) != (root_info.st_uid, root_info.st_gid):
            os.fchown(fd, root_info.st_uid, root_info.st_gid)
        os.environ['AIIDA_PATH'] = str(root / 'aiida')
        from aiida.manage.configuration.settings import AiiDAConfigDir
        from aiida.manage.profile_access import ProfileAccessManager
        AiiDAConfigDir.set(root / 'aiida/.aiida')
        profile = profile_at(profile_source or root, profile_name, original_root=root)
        # On restore, lock records belong to the destination's profile, not the backup.
        hold = NativeHold(root, profile, time.monotonic() + timeout)
        with ProfileAccessManager(profile).lock():
            hold.active = True
            try:
                yield hold
            finally:
                hold.active = False
    finally:
        os.close(fd)


def sqlite_snapshot(source, destination, hold):
    regular(source)
    with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as incoming:
        with sqlite3.connect(destination) as outgoing:
            incoming.backup(outgoing, pages=128, progress=lambda *_: hold.check(), sleep=0.01)
            if outgoing.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                raise ValueError('SQLite snapshot integrity failed')
            if outgoing.execute('PRAGMA foreign_key_check').fetchall():
                raise ValueError('SQLite snapshot foreign keys failed')


def excluded(relative):
    name = relative.as_posix()
    if name == 'execution/executor.lock' or name.startswith('execution/aiida/.aiida/access/'):
        return True
    return any(name == db + suffix for db in SQLITE for suffix in ('-wal', '-shm', '-journal'))


def inventory(roots):
    """Return every retained file and directory; reject links and special files."""
    result = []
    for owner, root in sorted(roots.items()):
        for path in [root, *sorted(root.rglob('*'))]:
            relative = Path(owner) / path.relative_to(root)
            info = path.lstat()
            if excluded(relative):
                continue
            if not stat.S_ISDIR(info.st_mode):
                regular(path)
            result.append((relative, path, info))
    return result


def copy_file(source, destination, hold):
    with source.open('rb') as incoming, destination.open('xb') as outgoing:
        while block := incoming.read(1024 * 1024):
            hold.check()
            outgoing.write(block)
        outgoing.flush()
        os.fsync(outgoing.fileno())


def digest_file(path, hold):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        while block := stream.read(1024 * 1024):
            hold.check()
            result.update(block)
    return result.hexdigest()


def durable_path(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def validate_native(root, owner, hold, *, original_root):
    from aiida.storage.sqlite_dos.backend import SqliteDosStorage
    from disk_objectstore import Container
    from aiida import orm
    hold.check()
    profile = profile_at(root, owner['profile'], original_root=original_root)
    if profile.uuid != owner['profile_uuid']:
        raise ValueError('Native profile UUID mismatch')
    expected = {key: owner[key] for key in ('profile_uuid', 'repository_uuid', 'computer_uuid', 'code_uuid')}
    if read_json(root / 'profile-identity.json') != dict(expected, profile=owner['profile']):
        raise ValueError('Retained native identity mismatch')
    backend = SqliteDosStorage(profile)  # Validates current schema and DB/repository UUID agreement.
    try:
        if backend.get_repository().uuid != owner['repository_uuid']:
            raise ValueError('Native repository UUID mismatch')
        for kind, key in ((orm.Computer, 'computer_uuid'), (orm.InstalledCode, 'code_uuid')):
            if orm.QueryBuilder(backend=backend).append(kind, filters={'uuid': owner[key]}).count() != 1:
                raise ValueError('Native retained entity identity missing')
        for node, in orm.QueryBuilder(backend=backend).append(orm.ProcessNode).iterall():
            hold.check()
            if not node.is_terminated:
                raise ValueError('Native accepted process requires reconciliation')
        with Container(root / 'aiida-store/container') as container:
            if not container.validate(callback=lambda **_: hold.check()).is_valid():
                raise ValueError('Native object bytes failed validation')
            for node, in orm.QueryBuilder(backend=backend).append(orm.Node).iterall():
                for directory, _, filenames in node.base.repository.walk():
                    for filename in filenames:
                        hold.check()
                        key = node.base.repository.get_object(str(directory / filename)).key
                        if not container.has_object(key):
                            raise ValueError('Native referenced object missing')
        return backend.version_profile(profile)
    finally:
        backend.close()


def snapshot_files(hold, destination, *, roots, identity, owner):
    """Write the manifest last; a partial directory is never a usable snapshot."""
    hold.check()
    roots = source_roots(roots)
    check_identity(identity, owner, roots)
    if roots['execution'] != hold.root or owner['profile'] != hold.profile.name:
        raise ValueError('Wrong native owner hold')
    destination = safe_path(destination)
    if destination.exists() or any(root == destination or root in destination.parents
                                   or destination in root.parents for root in roots.values()):
        raise ValueError('Snapshot destination must be new and separate')
    records = inventory(roots)
    if not SQLITE <= {relative.as_posix() for relative, _, _ in records}:
        raise ValueError('Required owner database missing')
    # Validate native bytes and settled process states before copying other owners.
    native_schema = validate_native(roots['execution'], owner, hold, original_root=hold.root)
    destination.mkdir(mode=0o700)
    entries = []
    for relative, source, info in records:
        hold.check()
        target = destination / relative
        directory = stat.S_ISDIR(info.st_mode)
        if directory:
            target.mkdir(mode=0o700)
        elif relative.as_posix() in SQLITE:
            sqlite_snapshot(source, target, hold)
        else:
            copy_file(source, target, hold)
        entry = dict(path=relative.as_posix(), kind='directory' if directory else 'file',
                     mode=stat.S_IMODE(info.st_mode), uid=info.st_uid, gid=info.st_gid)
        if not directory:
            target.chmod(0o600)
            entry.update(size=target.stat().st_size, sha256=digest_file(target, hold))
        entries.append(entry)
    copied_schema = validate_native(destination / 'execution', owner, hold, original_root=hold.root)
    if copied_schema != native_schema:
        raise ValueError('Native schema changed during snapshot')
    for entry in reversed(entries):
        if entry['kind'] == 'directory':
            durable_path(destination / entry['path'])
    manifest = dict(schema=SCHEMA, coherent_backup=False, application_database='not_included',
                    identity=identity, native_owner=owner, native_schema=native_schema,
                    tools=dict(TOOLS, sqlite=sqlite3.sqlite_version),
                    roots={key: str(value) for key, value in roots.items()}, entries=entries)
    with (destination / 'manifest.json').open('xb') as stream:
        stream.write(canonical(manifest))
        stream.flush()
        os.fsync(stream.fileno())
    durable_path(destination)
    return manifest


def verified_manifest(snapshot, *, identity, owner, roots, deadline):
    """Verify every retained byte and path before touching restore destinations."""
    check_tools()
    snapshot = safe_path(snapshot)
    regular(snapshot / 'manifest.json')
    manifest = read_json(snapshot / 'manifest.json')
    required = {'schema', 'coherent_backup', 'application_database', 'identity', 'native_owner',
                'native_schema', 'tools', 'roots', 'entries'}
    if (set(manifest) != required or manifest['schema'] != SCHEMA
            or manifest['coherent_backup'] is not False or manifest['application_database'] != 'not_included'
            or manifest['identity'] != identity or manifest['native_owner'] != owner
            or manifest['roots'] != {key: str(value) for key, value in roots.items()}
            or manifest['tools'] != dict(TOOLS, sqlite=sqlite3.sqlite_version)):
        raise ValueError('Snapshot identity or storage tools mismatch')
    hold = NativeHold(roots['execution'], None, deadline, active=True)
    seen = set()
    for entry in manifest['entries']:
        path = Path(entry['path'])
        fields = {'path', 'kind', 'mode', 'uid', 'gid'}
        if entry['kind'] == 'file':
            fields |= {'sha256', 'size'}
        if (set(entry) != fields or entry['kind'] not in ('directory', 'file')
                or path.is_absolute() or '..' in path.parts or not path.parts
                or path.parts[0] not in ROOTS or path.as_posix() != entry['path']
                or '\\' in entry['path'] or entry['path'] in seen or excluded(path)
                or any(type(entry[key]) is not int or entry[key] < 0 for key in ('mode', 'uid', 'gid'))
                or entry['mode'] > 0o777):
            raise ValueError('Unsafe snapshot entry')
        seen.add(entry['path'])
        actual = safe_path(snapshot / path)
        if entry['kind'] == 'directory':
            if not actual.is_dir():
                raise ValueError('Snapshot directory missing')
        else:
            info = regular(actual)
            if info.st_size != entry['size'] or digest_file(actual, hold) != entry['sha256']:
                raise ValueError('Snapshot bytes mismatch')
    actual = {path.relative_to(snapshot).as_posix() for path in snapshot.rglob('*')}
    if actual != seen | {'manifest.json'} or not SQLITE <= seen or not ROOTS <= seen:
        raise ValueError('Incomplete snapshot inventory')
    return manifest


def restore_files(snapshot, *, roots, identity, owner, timeout):
    """Restore only empty original paths; retain old attestation as historical evidence.

    Platform still owns isolated-target authorization, stopped application/modeling
    writers, PostgreSQL restoration, ownership qualification and closed admission.
    A failure retains partial files for explicit reconciliation; it never retries.
    """
    if type(timeout) not in (int, float) or not 0 < timeout <= 3600:
        raise ValueError('Bounded owner timeout required')
    deadline = time.monotonic() + timeout
    roots = source_roots(roots)
    check_identity(identity, owner, roots)
    if any(any(root.iterdir()) for root in roots.values()):
        raise ValueError('Restore requires empty owner stores')
    snapshot = safe_path(snapshot)
    if any(root == snapshot or root in snapshot.parents or snapshot in root.parents for root in roots.values()):
        raise ValueError('Restore source must be separate')
    manifest = verified_manifest(snapshot, identity=identity, owner=owner, roots=roots, deadline=deadline)
    with native_hold(roots['execution'], owner['profile'], timeout=max(0.001, deadline - time.monotonic()),
                     profile_source=snapshot / 'execution') as hold:
        for entry in manifest['entries']:
            hold.check()
            path = Path(entry['path'])
            target = roots[path.parts[0]].joinpath(*path.parts[1:])
            if entry['kind'] == 'directory':
                target.mkdir(mode=0o700, exist_ok=True)
            else:
                # An interruption must never leave the restored old attestation
                # at the active path, even before native validation completes.
                if path.as_posix() == 'execution/evidence/containment.json':
                    target = target.with_name('containment-' + entry['sha256'] + '.json')
                if target.exists():
                    if digest_file(target, hold) != entry['sha256']:
                        raise ValueError('Historical attestation collision')
                else:
                    copy_file(snapshot / path, target, hold)
                if digest_file(target, hold) != entry['sha256']:
                    raise ValueError('Restored snapshot bytes mismatch')
                target.chmod(entry['mode'])
                if (target.stat().st_uid, target.stat().st_gid) != (entry['uid'], entry['gid']):
                    os.chown(target, entry['uid'], entry['gid'])
                durable_path(target)
        root_entry = next(entry for entry in manifest['entries'] if entry['path'] == 'execution')
        lock = roots['execution'] / 'executor.lock'
        if (lock.stat().st_uid, lock.stat().st_gid) != (root_entry['uid'], root_entry['gid']):
            os.chown(lock, root_entry['uid'], root_entry['gid'])
        if validate_native(hold.root, owner, hold, original_root=hold.root) != manifest['native_schema']:
            raise ValueError('Restored native schema mismatch')
        for entry in reversed(manifest['entries']):
            if entry['kind'] == 'directory':
                path = Path(entry['path'])
                target = roots[path.parts[0]].joinpath(*path.parts[1:])
                target.chmod(entry['mode'])
                if (target.stat().st_uid, target.stat().st_gid) != (entry['uid'], entry['gid']):
                    os.chown(target, entry['uid'], entry['gid'])
                durable_path(target)
    return {'schema': SCHEMA, 'coherent_backup': False, 'application_database': 'not_included',
            'identity': identity, 'native_owner': owner, 'native_schema': manifest['native_schema']}
