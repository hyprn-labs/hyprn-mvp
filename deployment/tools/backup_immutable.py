"""Reviewed off-cloud activation backup of the STOPPED development stores (immutable reads).

Run it from the retained release (`<release>/source/deployment/tools/backup_immutable.py`),
whose manifest pins its sha256, never from an ad-hoc copy. Stdlib only, Python 3.9 compatible.

Reads the stores below the data root only; writes only a new backup directory (0700,
create-only; files 0600).
SQLite databases are copied with the sqlite3 backup API from `mode=ro&immutable=1` sources, so
nothing (no -shm, no journal) is created next to the live stores. Because immutable=1 ignores a
WAL and hot journals, the backup REFUSES unless every database's `-wal` and `-journal` is
absent or empty after the clean stop. Credential and AiiDA profile bytes are never
copied (identity digests only). Refuses unless the executor is stopped (parsable executor.json,
no live `dispatch_runtime.py --serve`), executor.lock is free and no hyprn-mvp container runs.

The stores (application/, modeling/, execution/) are below HYPRN_MVP_DATA_ROOT, the absolute
development data root documented in deployment/local_paths.py; every operation refuses while it
is unset.

Usage:
  backup_immutable.py <new-backup-dir> [--dry-run]
  backup_immutable.py --lock-probe        # executor/lock state only; no docker, no writes
"""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys


def stores_root():
    """HYPRN_MVP_DATA_ROOT, read the same way as deployment/local_paths.py (this standalone
    stdlib tool imports no project module); None while unset or not absolute."""
    value = os.environ.get('HYPRN_MVP_DATA_ROOT', '')
    return Path(value) if value and Path(value).is_absolute() else None


ROOT = stores_root()
DATABASES = ('application/application/application.sqlite', 'execution/aiida-store/database.sqlite',
             'modeling/modeling/model.sqlite3')
TREES = ('execution/aiida-store/container', 'modeling/modeling', 'application/application/computational-records',
         'application/evidence', 'modeling/evidence', 'application/activation')
FILES = ('execution/launch-worker', 'execution/runtime.json', 'execution/executor.json', 'execution/profile-identity.json',
         'execution/selected.json', 'application/identity.json', 'modeling/identity.json', 'execution/evidence/containment.json')
DIGEST_ONLY = ('application/credentials/owner.password', 'modeling/credentials/model.key', 'modeling/credentials/rails.key',
               'execution/aiida/.aiida/config.json')
# Store side files never copied as plain files (the backup API copies the database itself).
SIDE_SUFFIXES = ('-wal', '-shm', '-journal')
# Every container of the product (owned services and test scopes) starts with this prefix.
PRODUCT_PREFIX = 'hyprn-mvp-'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def process_command(pid):
    return subprocess.run(['/bin/ps', '-ww', '-p', str(pid), '-o', 'command='], capture_output=True, text=True).stdout.strip()


def running_containers():
    result = subprocess.run(['docker', 'ps', '--format', '{{.Names}}'], capture_output=True, text=True)
    if result.returncode:
        raise SystemExit('Cannot list running containers (is Docker Desktop running?): ' + result.stderr.strip()[:200])
    return result.stdout.split()


def executor_state(root):
    """('absent'|'valid', running). Unparsable or symlinked state refuses (fail closed)."""
    path = Path(root) / 'execution/executor.json'
    if path.is_symlink():
        raise SystemExit('executor.json is a symlink; refusing')
    if not path.exists():
        return 'absent', False
    try:
        saved = json.loads(path.read_text())
        pid = saved['pid']
        if type(pid) is not int or pid <= 0:
            raise ValueError('pid')
    except (ValueError, KeyError, TypeError):
        raise SystemExit('Unparsable executor.json; refusing (inspect the owned executor state first)')
    return 'valid', process_command(pid).endswith('/deployment/dispatch_runtime.py --serve')


def lock_free(root):
    """Non-blocking flock probe on executor.lock (released at once). Missing lock: free."""
    path = Path(root) / 'execution/executor.lock'
    if path.is_symlink():
        raise SystemExit('executor.lock is a symlink; refusing')
    if not path.exists():
        return True
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        return True
    finally:
        os.close(fd)


def lock_probe(root=ROOT):
    recorded, running = executor_state(root)
    return dict(executor_running=running, executor_json=recorded, lock_available=lock_free(root))


def preconditions(root=ROOT, containers=None):
    recorded, running = executor_state(root)
    if running:
        raise SystemExit('Executor appears to be running; refusing backup')
    if not lock_free(root):
        raise SystemExit('executor.lock is held; refusing backup')
    names = (containers or running_containers)()
    owned = [name for name in names if name.lstrip('/').startswith(PRODUCT_PREFIX)]
    if owned:
        raise SystemExit('A hyprn-mvp container is running; stop it before the backup: ' + ', '.join(owned))
    return dict(executor_json=recorded, executor_running=False, lock_available=True, running_containers=[])


def wal_state(root=ROOT):
    """Size of each database's -wal and -journal (None when absent)."""
    state = {}
    for relative in DATABASES:
        sizes = {}
        for kind in ('wal', 'journal'):
            side = Path(root) / (relative + '-' + kind)
            if side.is_symlink():
                raise SystemExit('Database side file is a symlink; refusing: ' + str(side))
            sizes[kind] = side.stat().st_size if side.exists() else None
        state[relative] = sizes
    return state


def require_clean_databases(state):
    for relative, sizes in state.items():
        if sizes['wal']:
            raise SystemExit(relative + '-wal is not empty (' + str(sizes['wal']) + ' bytes) after the stop; '
                             'an immutable read ignores the WAL and would miss committed pages. Refusing; '
                             'restart and cleanly stop its owner, then retry.')
        if sizes['journal']:
            raise SystemExit(relative + '-journal is not empty (hot journal); refusing an immutable read.')


def _private_file(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as output:
        output.write(raw)


def backup(root, target, containers=None):
    root, target = Path(root), Path(target)
    gate = preconditions(root, containers)
    state = wal_state(root)
    require_clean_databases(state)
    target.mkdir(mode=0o700)  # create-only: never overwrite an earlier backup
    os.chmod(target, 0o700)
    manifest = dict(at=datetime.datetime.now(datetime.timezone.utc).isoformat(), root=str(root),
                    tool_sha256=sha(Path(__file__).read_bytes()), preconditions=gate, wal_state=state, entries=[])
    for relative in DATABASES:
        out = target / relative
        out.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        source = sqlite3.connect((root / relative).as_uri() + '?mode=ro&immutable=1', uri=True)
        copy = sqlite3.connect(str(out))
        try:
            source.backup(copy)
            ok = copy.execute('PRAGMA integrity_check').fetchone()[0]
        finally:
            copy.close()
            source.close()
        os.chmod(out, 0o600)
        manifest['entries'].append(dict(path=relative, kind='sqlite-backup', sha256=sha(out.read_bytes()), integrity=ok))
    skipped = set(DATABASES) | {d + s for d in DATABASES for s in SIDE_SUFFIXES}
    copied = []
    for tree in TREES:
        base = root / tree
        for path in sorted(base.rglob('*')) if base.exists() else []:
            relative = str(path.relative_to(root))
            if path.is_file() and not path.is_symlink() and relative not in skipped:
                copied.append(relative)
    copied += [f for f in FILES if (root / f).is_file() and not (root / f).is_symlink()]
    for relative in copied:
        raw = (root / relative).read_bytes()
        _private_file(target / relative, raw)
        manifest['entries'].append(dict(path=relative, kind='file', sha256=sha(raw), size=len(raw)))
    manifest['identity_digests'] = {rel: sha((root / rel).read_bytes()) for rel in DIGEST_ONLY if (root / rel).is_file()}
    for entry in manifest['entries']:
        if entry['kind'] == 'file' and sha((target / entry['path']).read_bytes()) != entry['sha256']:
            raise SystemExit('Backup copy mismatch: ' + entry['path'])
    if any(e['kind'] == 'sqlite-backup' and e['integrity'] != 'ok' for e in manifest['entries']):
        raise SystemExit('Backup integrity_check failed; keep the backup directory for diagnosis')
    raw = (json.dumps(manifest, indent=2) + '\n').encode()
    _private_file(target / 'backup-manifest.json', raw)
    return dict(target=str(target), entries=len(manifest['entries']), manifest_sha256=sha(raw),
                tool_sha256=manifest['tool_sha256'])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('target', nargs='?', type=Path)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--lock-probe', action='store_true')
    args = parser.parse_args(argv)
    if ROOT is None:
        parser.error('HYPRN_MVP_DATA_ROOT is not set: export it as the absolute path of the development data root')
    if args.lock_probe:
        if args.target or args.dry_run:
            parser.error('--lock-probe takes no target')
        print(json.dumps(lock_probe(ROOT), indent=2))
        return 0
    if args.target is None:
        parser.error('backup target required')
    if args.dry_run:
        gate = preconditions(ROOT)
        state = wal_state(ROOT)
        require_clean_databases(state)
        print(json.dumps(dict(dry_run=True, target=str(args.target), preconditions=gate, wal_state=state,
                              tool_sha256=sha(Path(__file__).read_bytes())), indent=2))
        return 0
    print(json.dumps(backup(ROOT, args.target), indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
