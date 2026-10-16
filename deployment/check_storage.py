"""Bounded lifecycle for developer checks; never a collector for installation data.

Only scopes registered by a supervised check are removable. A marker, inode and
canonical scope identity are checked again before removal. Existing/resumed scopes
are not adopted. Scientific stores outside these disposable test scopes are untouched.
"""
from __future__ import annotations

import json
import fcntl
import os
from pathlib import Path
import shutil
import signal
import stat
import subprocess
import sys
import time
from uuid import UUID, uuid4

import local_paths

SESSION = local_paths.CHECK_SESSION
GiB = 1024**3
MiB = 1024**2


def limit(name, default):
    value = os.environ.get('HYPRN_MVP_' + name, str(default))
    if not value.isdecimal() or int(value) < 1:
        raise ValueError('HYPRN_MVP_' + name + ' must be a positive integer in bytes')
    return int(value)


def safe(path):
    path = Path(path)
    if not path.is_absolute() or path.resolve() != path or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Unsafe check storage path: ' + str(path))
    if path.exists() and path.stat().st_uid != os.getuid():
        raise ValueError('Foreign check storage owner: ' + str(path))
    return path


def allocated(path):
    """Allocated bytes, without following symlinks or counting hard links twice."""
    seen = set()
    total = 0
    for folder, dirs, files in os.walk(path, followlinks=False):
        for name in ['.', *dirs, *files]:
            try:
                s = (Path(folder) / name).lstat()
            except FileNotFoundError:
                continue
            key = (s.st_dev, s.st_ino)
            if key not in seen:
                seen.add(key)
                total += s.st_blocks * 512
    return total


def write(path, value):
    temporary = path.with_suffix('.writing')
    with temporary.open('x') as stream:
        json.dump(value, stream, sort_keys=True)
    temporary.replace(path)


def register(scope):
    """Called only after exclusive scope allocation, before any test executes."""
    value = os.environ.get(SESSION)
    if not value:
        return
    session = safe(value)
    if session.parent != safe(local_paths.check_storage_root()):
        raise ValueError('Invalid check session')
    root = safe(scope.root)
    record = dict(path=str(root), inode=root.stat().st_ino, scope=scope.record())
    record['session'] = session.name
    write(root / '.check-session.json', record)


def scope_path(record):
    root = safe(record['path'])
    identity = record['scope']
    run = str(UUID(identity['run_uuid']))
    if (root.parent != safe(local_paths.scratch_root()) or root.name != local_paths.SCOPE_PREFIX + run
            or identity['root'] != str(root) or identity['profile'] != root.name):
        raise ValueError('Invalid managed test scope')
    if any(root == p or root in p.parents or p in root.parents for p in local_paths.live_roots()):
        raise ValueError('Managed scope overlaps a live installation')
    if not root.exists():
        return root
    current = json.loads(safe(root / 'scope.json').read_text())
    fixed = ('root', 'run_uuid', 'profile', 'profile_uuid', 'backend', 'interpreter')
    if root.stat().st_ino != record['inode'] or any(current.get(k) != identity.get(k) for k in fixed):
        raise ValueError('Managed scope identity changed; refusing cleanup')
    UUID(current['store_uuid'])  # Native initialization records the actual new repository UUID.
    record['scope'] = current
    return root


def remove_tree(root):
    safe(root)
    if not root.exists():
        return
    for folder, dirs, files in os.walk(root, followlinks=False):
        path = Path(folder)
        s = path.lstat()
        if s.st_uid != os.getuid() or not stat.S_ISDIR(s.st_mode):
            raise ValueError('Unsafe disposable directory')
        path.chmod(s.st_mode | 0o700)
    shutil.rmtree(root)  # Does not traverse directory symlinks.


def docker_resources(run):
    """Remove only explicitly scope-labelled containers/networks/images, never volumes."""
    if shutil.which('docker') is None:
        return
    selector = 'label=org.hyprn-mvp.test-scope=' + str(UUID(run))
    def call(*args):
        return subprocess.run(['docker', *args], capture_output=True, text=True, timeout=60)
    identifiers = set()
    for ownership in (selector, 'label=org.hyprn-mvp.owner=' + local_paths.SCOPE_PREFIX + run):
        containers = call('ps', '-aq', '--filter', ownership)
        if containers.returncode:
            raise ValueError('Cannot reconcile scoped Docker resources: ' + containers.stderr.strip())
        identifiers.update(containers.stdout.split())
    for identifier in identifiers:
        result = call('rm', '-f', identifier)
        if result.returncode:
            raise ValueError('Cannot release scoped container: ' + result.stderr.strip())
    for kind in ('network', 'image'):
        listed = call(kind, 'ls', '-q', '--filter', selector)
        if listed.returncode:
            raise ValueError('Cannot enumerate scoped Docker ' + kind)
        identifiers = set(listed.stdout.split())
        if kind == 'image' and identifiers:
            inspected = call('image', 'inspect', *sorted(identifiers))
            if inspected.returncode:
                raise ValueError('Cannot reconcile scoped images')
            for image in sorted(json.loads(inspected.stdout), key=lambda r: r['Created'], reverse=True):
                labels = image.get('Config', {}).get('Labels') or {}
                if labels.get('org.hyprn-mvp.test-scope') != run:
                    raise ValueError('Scoped image ownership changed')
                for reference in image.get('RepoTags') or [image['Id']]:
                    result = call('image', 'rm', reference)
                    if result.returncode:
                        raise ValueError('Cannot release scoped image: ' + result.stderr.strip())
        else:
            for identifier in identifiers:
                result = call(kind, 'rm', identifier)
                if result.returncode:
                    raise ValueError('Cannot release scoped ' + kind + ': ' + result.stderr.strip())


def preserve_evidence(root, destination, remaining):
    evidence = root / 'evidence'
    if not evidence.exists() or evidence.is_symlink():
        return remaining
    for folder, dirs, files in os.walk(evidence, followlinks=False):
        dirs[:] = [d for d in dirs if not (Path(folder) / d).is_symlink()]
        for name in sorted(files):
            source = Path(folder) / name
            if remaining <= 0:
                return 0
            s = source.lstat()
            if not stat.S_ISREG(s.st_mode):
                continue
            count = min(s.st_size, MiB, remaining)
            target = destination / source.relative_to(evidence)
            target.parent.mkdir(parents=True, exist_ok=True)
            with source.open('rb') as stream:
                stream.seek(max(0, s.st_size - count))
                target.write_bytes(stream.read(count))
            remaining -= count
    return remaining


def finish(session, *, keep=False, docker=False):
    remaining = 4 * MiB
    released = []
    for marker in local_paths.scratch_root().glob(local_paths.SCOPE_PREFIX + '*/.check-session.json'):
        record = json.loads(safe(marker).read_text())
        if record.get('session') == session.name:
            root = scope_path(record)
            if root != marker.parent:
                raise ValueError('Check registration path mismatch')
            write(session / (record['scope']['run_uuid'] + '.scope.json'), record)
    for entry in sorted(session.glob('*.scope.json')):
        record = json.loads(safe(entry).read_text())
        root = scope_path(record)
        if docker:
            docker_resources(record['scope']['run_uuid'])
        if root.exists() and not keep:
            remaining = preserve_evidence(root, session / 'evidence' / root.name, remaining)
            remove_tree(root)
            released.append(str(root))
    return released


def alive(pid):
    if not isinstance(pid, int) or pid < 1:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def collect(root, budget):
    # Qualification may finish groups concurrently; serialize only retirement.
    with safe(root / '.collection.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        _collect(root, budget)


def _collect(root, budget):
    """Recover only owned, inactive sessions; age and capacity bound diagnostics."""
    complete = []
    for session in root.iterdir():
        if not session.is_dir() or session.is_symlink():
            continue
        try:
            UUID(session.name)
        except ValueError:
            continue
        record_path = safe(session / 'session.json')
        if not record_path.exists():
            continue
        record = json.loads(record_path.read_text())
        if not record.get('finished'):
            if alive(record.get('pid')) or alive(record.get('child')):
                continue
            finish(session, docker=record.get('docker', False))
            record.update(finished=time.time(), recovered=True, keep=False)
            write(record_path, record)
        if record.get('keep'):
            if time.time() - record['finished'] < 86400:
                continue
            finish(session, docker=record.get('docker', False))
        complete.append((record['finished'], session, allocated(session)))
    total = sum(item[2] for item in complete)
    for when, session, size in sorted(complete):
        if time.time() - when >= 86400 or total > budget:
            remove_tree(session)
            total -= size


def scratch_bytes():
    root = safe(local_paths.scratch_root())
    return sum(allocated(p) for p in root.glob(local_paths.SCOPE_PREFIX + '*') if p.is_dir() and not p.is_symlink())


def check_budget(scratch, reserve):
    used = scratch_bytes()
    if used > scratch:
        raise ValueError(f'Test scratch budget exceeded: {used} > {scratch} bytes. '
                         'Release inactive experiments or raise HYPRN_MVP_TEST_SCRATCH_BYTES.')
    free = shutil.disk_usage(local_paths.scratch_root()).free
    if free < reserve:
        raise ValueError(f'Insufficient free disk: {free} < {reserve} bytes '
                         '(HYPRN_MVP_TEST_MIN_FREE_BYTES).')


def stop(child):
    # Every supervised group gets its own process group. Never signal the user's agent.
    try:
        os.killpg(child.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        child.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(child.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    child.wait()


def supervise(command, *, docker=False, keep=False):
    scratch = limit('TEST_SCRATCH_BYTES', 10 * GiB)
    reserve = limit('TEST_MIN_FREE_BYTES', 5 * GiB)
    evidence = limit('TEST_EVIDENCE_BYTES', 512 * MiB)
    root = safe(local_paths.check_storage_root())
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    collect(root, evidence)
    check_budget(scratch, reserve)
    if docker:
        import check_build_cache
        check_build_cache.enforce(limit('TEST_BUILD_CACHE_BYTES', 10 * GiB))
    session = root / str(uuid4())
    session.mkdir(mode=0o700)
    record = dict(pid=os.getpid(), started=time.time(), docker=docker, keep=keep)
    write(session / 'session.json', record)
    env = dict(os.environ, **{SESSION: str(session)})
    child = None
    code = 2
    failure = None
    previous = signal.getsignal(signal.SIGTERM)
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    try:
        child = subprocess.Popen(command, env=env, start_new_session=True)
        record['child'] = child.pid
        write(session / 'session.json', record)
        while True:
            try:
                code = child.wait(timeout=1)
                break
            except subprocess.TimeoutExpired:
                check_budget(scratch, reserve)
        check_budget(scratch, reserve)
    except KeyboardInterrupt:
        code = 130
        failure = 'Check interrupted'
    except (OSError, ValueError) as error:
        code = 2
        failure = str(error)
    finally:
        if child is not None:
            stop(child)
        signal.signal(signal.SIGTERM, previous)
        try:
            # An exceeded budget overrides full-scope retention.
            released = finish(session, keep=keep and failure is None, docker=docker)
            if docker:
                import check_build_cache
                check_build_cache.enforce(limit('TEST_BUILD_CACHE_BYTES', 10 * GiB))
            record.update(finished=time.time(), exit=code, failure=failure,
                          keep=keep and failure is None, released=released)
            write(session / 'session.json', record)
            collect(root, evidence)
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            code = 2
            failure = 'Check cleanup incomplete: ' + str(error)
        print(json.dumps(dict(check_storage=str(session), exit=code, failure=failure)), flush=True)
    return code
