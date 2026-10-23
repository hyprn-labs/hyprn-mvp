"""Opt-in retention for explicitly enrolled, disposable developer experiments.

Never enroll installation stores. Unknown file formats and source are retained;
only known data formats expire. Running and recent experiments override budgets.
"""
import fcntl
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import time

import check_storage
import local_paths

DAY = 86400
DATA = {'.sqlite', '.sqlite3', '.db', '.log', '.csv', '.parquet', '.npy', '.npz',
        '.h5', '.hdf5', '.png', '.jpg', '.webm'}
SOURCE_DIRS = {'.git', 'source', 'src', 'authoring-source', 'authoring-baseline',
               'configuration-baseline', 'node_modules', '.venv'}


def configuration(explicit=None):
    return (local_paths.absolute(explicit, '--config') if explicit else
            local_paths.located('HYPRN_MVP_EXPERIMENT_STORAGE_CONFIG', 'experiment-storage.json', required=False))


def validate_root(value):
    root = check_storage.safe(local_paths.absolute(value, 'experiment root'))
    repo = Path(__file__).resolve().parents[1]
    protected = (repo, *local_paths.store_roots(required=False), *local_paths.live_roots())
    if not root.is_dir() or root == Path(root.anchor) or any(
            root == p or root in p.parents or p in root.parents for p in protected):
        raise ValueError('Experiment root overlaps protected storage: ' + str(root))
    if any((p / '.git').exists() for p in (root, *root.parents)):
        raise ValueError('Experiment root is inside a source repository: ' + str(root))
    return root


def load(path):
    check_storage.safe(path)
    data = json.loads(path.read_text())
    if set(data) != {'version', 'roots', 'budget_bytes', 'reserve_bytes'} or data['version'] != 1:
        raise ValueError('Invalid experiment storage configuration')
    for key in ('budget_bytes', 'reserve_bytes'):
        if type(data[key]) is not int or data[key] <= 0:
            raise ValueError(key + ' must be a positive integer')
    if not isinstance(data['roots'], list) or any(not isinstance(p, str) for p in data['roots']):
        raise ValueError('roots must be explicit absolute folder paths')
    roots = [local_paths.absolute(p, 'experiment root') for p in data['roots']]
    if any(a == b or a in b.parents or b in a.parents for i, a in enumerate(roots) for b in roots[i+1:]):
        raise ValueError('Experiment roots must not overlap')
    return data


def enroll(path, roots, budget=None, reserve=None):
    path = check_storage.safe(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with check_storage.safe(path.with_suffix('.lock')).open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        data = load(path) if path.exists() else dict(version=1, roots=[], budget_bytes=40*1024**3, reserve_bytes=5*1024**3)
        for value in roots:
            root = validate_root(value)
            if path == root or root in path.parents:
                raise ValueError('Configuration must be outside enrolled experiments')
            if str(root) not in data['roots']:
                data['roots'].append(str(root))
        for key, value in [('budget_bytes', budget), ('reserve_bytes', reserve)]:
            if value is not None:
                if value <= 0:
                    raise ValueError(key + ' must be positive')
                data[key] = value
        paths = [Path(p) for p in data['roots']]
        if any(a in b.parents or b in a.parents for i, a in enumerate(paths) for b in paths[i+1:]):
            raise ValueError('Experiment roots must not overlap')
        check_storage.write(path, data)
    return data


def activity():
    """Fail closed if host processes, open files or Docker cannot be inspected."""
    listing = subprocess.run(['ps', '-axo', 'pid=,command='], capture_output=True, text=True, check=True, timeout=30)
    commands = '\n'.join(line for line in listing.stdout.splitlines()
                         if line.strip() and int(line.split()[0]) != os.getpid())
    opened = subprocess.run(['lsof', '-nP', '-Fpn'], capture_output=True, text=True, timeout=60)
    if opened.returncode not in (0, 1) or not opened.stdout:
        raise ValueError('Cannot inspect open files; no experiment data removed')
    paths = [line[1:] for line in opened.stdout.splitlines() if line.startswith('n/')]
    ids = subprocess.run(['docker', 'ps', '-aq'], capture_output=True, text=True, check=True, timeout=30).stdout.split()
    containers = json.loads(subprocess.run(['docker', 'inspect', *ids], capture_output=True, text=True,
                                          check=True, timeout=30).stdout) if ids else []
    mounts = [m['Source'] for c in containers for m in c.get('Mounts', []) if m['Type'] == 'bind']
    return commands, paths, mounts


def busy(root, state):
    commands, paths, mounts = state
    return (str(root) in commands or any(root == Path(p) or root in Path(p).parents for p in paths)
            or any(root == Path(p) or root in Path(p).parents or Path(p) in root.parents for p in mounts))


def snapshot(root):
    """Unknown files, repositories, links and source subtrees are never disposable."""
    entries = []
    targets = []
    latest = 0
    total = 0
    def visit(path, protected=False):
        nonlocal latest, total
        s = path.lstat()
        if s.st_uid != os.getuid():
            raise ValueError('Foreign owner: ' + str(path))
        entries.append((str(path), s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_mode))
        total += s.st_blocks * 512
        if stat.S_ISDIR(s.st_mode):
            protected = protected or path.name in SOURCE_DIRS or (path / '.git').exists()
            children = sorted(path.iterdir())
            if not children:
                latest = max(latest, s.st_mtime, s.st_ctime, getattr(s, 'st_birthtime', 0))
            for child in children:
                visit(child, protected)
        else:
            latest = max(latest, s.st_mtime, s.st_ctime, getattr(s, 'st_birthtime', 0))
            # Hard-linked data may be owned by another experiment; preserve it.
            suffix = path.suffix.lower()
            sqlite_sidecar = path.name.endswith(('.sqlite-wal', '.sqlite-shm', '.sqlite3-wal', '.sqlite3-shm', '.db-wal', '.db-shm'))
            if not protected and stat.S_ISREG(s.st_mode) and s.st_nlink == 1 and (suffix in DATA or sqlite_sidecar):
                targets.append(path)
    visit(root)
    return dict(entries=entries, targets=targets, latest=latest, bytes=total)


def collect(path, *, apply=False, now=None, inspect_activity=activity):
    now = time.time() if now is None else now
    check_storage.safe(path)
    with check_storage.safe(path.with_suffix('.lock')).open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        config = load(path)
        report = dict(removed_bytes=0, used_bytes=0, budget_bytes=config['budget_bytes'], roots=[])
        for value in config['roots']:
            root = Path(value)
            if not root.exists() and not root.is_symlink():
                continue
            validate_root(value)
            before = snapshot(root)
            reason = 'recent' if before['latest'] >= now-DAY else 'expired'
            if reason == 'expired' and busy(root, inspect_activity()):
                reason = 'active'
            if reason == 'expired' and apply:
                # Inspect again after traversal: changed trees and newly active work stay intact.
                if snapshot(root) != before or busy(root, inspect_activity()):
                    reason = 'changed or active'
                else:
                    identities = {e[0]: e for e in before['entries']}
                    for target in before['targets']:
                        check_storage.safe(target)
                        expected = identities[str(target)]
                        s = target.lstat()
                        actual = (str(target), s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_mode)
                        if actual != expected:
                            raise ValueError('Experiment changed during cleanup: ' + str(target))
                        target.unlink()
                    reason = 'collected'
            after = snapshot(root)
            report['removed_bytes'] += max(0, before['bytes'] - after['bytes'])
            report['used_bytes'] += after['bytes']
            report['roots'].append(dict(path=value, state=reason, bytes=after['bytes'], eligible_files=len(before['targets'])))
        report['over_budget'] = report['used_bytes'] > config['budget_bytes']
        report['low_free_space'] = any(shutil.disk_usage(p).free < config['reserve_bytes']
                                       for p in config['roots'] if Path(p).exists())
        report['admitted'] = not (report['over_budget'] or report['low_free_space'])
        return report


def automatic():
    # Scoped children may exercise the CLI; never discover a host policy there.
    if os.environ.get(local_paths.CHECK_SESSION) and not os.environ.get('HYPRN_MVP_EXPERIMENT_STORAGE_CONFIG'):
        return
    path = configuration()
    if path is None or not path.exists():
        return
    report = collect(path, apply=True)
    print(json.dumps({'experiment_storage': report}), flush=True)
    if not report['admitted']:
        raise ValueError('Experiment storage budget exceeded; protected data retained. Free space or raise the explicit budget.')
