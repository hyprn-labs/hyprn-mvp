"""Execution-only cloud owner. No database/provider credentials or local manager.

The trusted host supplies a narrow projection and pins the observed native UUIDs.
Initialization is explicit. Inspect and ordinary service start never create a
profile, rebuild a worker, migrate a store or renew an attestation.
"""

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from uuid import UUID, uuid4


# Operational headroom for transient repositories, independent of model resource limits.
MIN_EXECUTION_SCRATCH_FREE_BYTES = 1024 * 1024 * 1024
SCRATCH_ABANDONED_SECONDS = 3600
SCRATCH_SCAN_LIMIT = 128


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def execution_home(configuration, *, create=False):
    """Only explicit initialization/rebind may create the owner's private home."""
    home = Path(configuration['host_home'])
    if not home.is_absolute() or any(p.is_symlink() for p in (home, *home.parents)):
        raise ValueError('Unsafe execution home')
    if create:
        home.mkdir(mode=0o700, exist_ok=True)
    try:
        info = home.stat()
    except FileNotFoundError as error:
        raise ValueError('Execution home is missing') from error
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o700):
        raise ValueError('Execution home must be private and owned by execution user')
    return home


def execution_temporary(configuration, *, create=False):
    """Private transient AiiDA repositories belong on the execution data volume."""
    scratch = Path(configuration['execution_root']) / 'tmp'
    if not scratch.is_absolute() or any(p.is_symlink() for p in (scratch, *scratch.parents)):
        raise ValueError('Unsafe execution temporary directory')
    if create:
        scratch.mkdir(mode=0o700, exist_ok=True)
    try:
        info = scratch.stat()
    except FileNotFoundError as error:
        raise ValueError('Execution temporary directory is missing') from error
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o700):
        raise ValueError('Execution temporary directory must be private and owned by execution user')
    return scratch



def collect_execution_scratch(configuration, *, now=None):
    """Collect only expired, unlocked owner sessions; unknown files are never selected."""
    root = execution_temporary(configuration)
    now = time.time() if now is None else now
    removed = 0
    # A bounded scan keeps maintenance off the critical path as stores grow.
    with os.scandir(root) as entries:
        for index, entry in enumerate(entries):
            if index >= SCRATCH_SCAN_LIMIT:
                break
            name = entry.name
            if not name.startswith('session-') or len(name) != 40:
                continue
            try:
                if UUID(name[8:]).hex != name[8:]:
                    continue
                info = entry.stat(follow_symlinks=False)
                if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
                        or stat.S_IMODE(info.st_mode) != 0o700
                        or now - info.st_mtime < SCRATCH_ABANDONED_SECONDS):
                    continue
                folder = root / name
                fd = os.open(folder / '.lease', os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK)
                try:
                    lease = os.fstat(fd)
                    if (not stat.S_ISREG(lease.st_mode) or lease.st_uid != os.getuid()
                            or lease.st_nlink != 1 or stat.S_IMODE(lease.st_mode) != 0o600
                            or os.read(fd, 64) != b'hyprn-native-scratch/v1\n'):
                        continue
                    try:
                        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        continue
                    # fd-based rmtree never follows a symlink into a scientific store.
                    if not shutil.rmtree.avoids_symlink_attacks:
                        raise RuntimeError('Safe scratch cleanup unavailable')
                    shutil.rmtree(folder)
                    removed += 1
                finally:
                    os.close(fd)
            except (FileNotFoundError, ValueError):
                continue
    return {'removed_sessions': removed}


@contextlib.contextmanager
def execution_scratch_session(configuration):
    """One disposable lease per native process, independent of durable execution records."""
    root = execution_temporary(configuration)
    collect_execution_scratch(configuration)
    if shutil.disk_usage(root).free < MIN_EXECUTION_SCRATCH_FREE_BYTES:
        raise RuntimeError('Execution temporary storage has insufficient free space')
    folder = root / ('session-' + uuid4().hex)
    folder.mkdir(mode=0o700)
    fd = os.open(folder / '.lease', os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    previous_env, previous_cache = os.environ.get('TMPDIR'), tempfile.tempdir
    try:
        os.write(fd, b'hyprn-native-scratch/v1\n')
        os.fsync(fd)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        os.environ['TMPDIR'] = str(folder)
        tempfile.tempdir = str(folder)
        yield folder
    finally:
        tempfile.tempdir = previous_cache
        if previous_env is None:
            os.environ.pop('TMPDIR', None)
        else:
            os.environ['TMPDIR'] = previous_env
        try:
            shutil.rmtree(folder)
        finally:
            os.close(fd)


def scratch_admission(configuration, method):
    if method not in ('launch', 'launch_batch', 'launch_budgeted'):
        return
    root = execution_temporary(configuration)
    collect_execution_scratch(configuration)
    if shutil.disk_usage(root).free < MIN_EXECUTION_SCRATCH_FREE_BYTES:
        raise RuntimeError('Execution temporary storage has insufficient free space')


def select_execution_temporary(configuration):
    # tempfile caches its first selection; setting TMPDIR alone cannot dislodge
    # a host /tmp selected during imports. An explicit path also forbids fallback
    # to another filesystem when the execution volume cannot accept writes.
    scratch = str(Path(configuration['execution_root']) / 'tmp')
    os.environ['TMPDIR'] = scratch
    tempfile.tempdir = scratch


def host_prerequisites(configuration=None):
    """Check the real owner's scheduler utilities before any execution mutation."""
    import pwd
    names = ('bash', 'ps', 'tail', 'whoami')
    commands = {name: shutil.which(name, path=os.environ.get('PATH', '')) for name in names}
    missing = [name for name, path in commands.items() if path is None]
    if missing:
        raise RuntimeError('Execution host requires commands on owner PATH: ' + ', '.join(missing))
    checks = (
        ('bash', ['-c', 'exit 0'], None, ''),
        ('ps', ['-o', 'pid=', '-p', str(os.getpid())], None, str(os.getpid())),
        ('tail', ['-n', '+2'], 'header\nready\n', 'ready'),
        ('whoami', [], None, pwd.getpwuid(os.getuid()).pw_name),
    )
    for name, arguments, incoming, expected in checks:
        try:
            result = subprocess.run([commands[name], *arguments], input=incoming,
                                    capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise RuntimeError('Execution host command unavailable: ' + name) from error
        if result.returncode or result.stdout.strip() != expected:
            raise RuntimeError('Execution host command failed scheduler preflight: ' + name)
    if configuration is not None:
        home = execution_home(configuration)
        # LocalTransport starts its first scheduler command in the account home.
        # Test that working directory before accepting any candidate calculation.
        result = subprocess.run([commands['whoami']], cwd=home, capture_output=True,
                                text=True, timeout=10)
        if result.returncode or result.stdout.strip() != pwd.getpwuid(os.getuid()).pw_name:
            raise RuntimeError('Execution home failed scheduler preflight')
        scratch = execution_temporary(configuration)
        if shutil.disk_usage(scratch).free < MIN_EXECUTION_SCRATCH_FREE_BYTES:
            raise RuntimeError('Execution temporary storage has insufficient free space')
        try:
            with tempfile.TemporaryFile(dir=scratch) as probe:
                probe.write(b'owner storage ready')
                probe.flush()
                os.fsync(probe.fileno())
        except OSError as error:
            raise RuntimeError('Execution temporary storage cannot accept writes') from error


def bootstrap(path):
    # -I disables environment and user-site injection. Only this exact retained
    # source supplies project modules; the packaged interpreter supplies dependencies.
    source = Path(__file__).resolve().parents[1]
    sys.path[:0] = [str(source / name) for name in ('deployment', 'application/src', 'integration/src')]
    from hyprn_mvp_integration import installation
    os.environ[installation.CLOUD_CONFIG] = str(path)
    value = installation.cloud_from_environment()
    if (Path(value['source']) != source
            or Path(sys.executable).absolute() != Path(value['python'])):
        raise ValueError('Cloud owner must use the exact released source and interpreter')
    root = Path(value['execution_root'])
    if any(part.is_symlink() for part in (root, *root.parents)):
        raise ValueError('Unsafe execution root')
    status = root.stat()
    if not stat.S_ISDIR(status.st_mode) or status.st_uid != os.getuid() or status.st_mode & 0o077:
        raise ValueError('Execution root must be private and owned by execution user')
    os.environ['AIIDA_PATH'] = str(root / 'aiida')
    os.environ['HOME'] = value['host_home']
    select_execution_temporary(value)
    return value


def wrapper(configuration, config_path):
    return ('#!/bin/sh\nexec ' + shlex.quote(configuration['python']) + ' -I -B '
            + shlex.quote(str(Path(configuration['source']) / 'deployment/cloud_native.py'))
            + ' --config ' + shlex.quote(str(config_path)) + ' launch -- "$@"\n')


def prepared_inventory(configuration):
    # The venv name is pinned by the native lock; no search or "latest" selection.
    source = Path(configuration['source'])
    lock = source / 'deployment/locks/native-host.txt'
    environment = 'venv-' + hashlib.sha256(lock.read_bytes()).hexdigest()[:16]
    python = Path(configuration['python'])
    if python.parent.name != 'bin' or python.parent.parent.name != environment:
        raise ValueError('Native interpreter does not match released lock')
    if python.parents[2] != Path(configuration['native_root']):
        raise ValueError('Native inventory root mismatch')
    return python.parents[2]


def packaged_inventory(configuration):
    """Verify every packaged byte before any mutable execution record changes."""
    from hyprn_mvp_integration import launcher
    root = Path(configuration['execution_root'])
    prepared = prepared_inventory(configuration)
    runtime = json.loads((prepared / 'runtime.json').read_bytes())
    selected = (prepared / 'selected.json').read_bytes()
    if (runtime['source_hashes'] != launcher.execution_source_hashes()
            or runtime['selected_sha256'] != hashlib.sha256(selected).hexdigest()):
        raise ValueError('Packaged native inventory identity mismatch')
    selection = json.loads(selected)
    # Validate the complete selection before the first mutable-store write.
    files, seen = [], set()
    for item in selection['files']:
        relative = Path(item['path'])
        if (relative.is_absolute() or '..' in relative.parts or '\\' in item['path']
                or relative.as_posix() != item['path'] or len(relative.parts) < 2
                or relative.parts[0] not in ('locks', 'licenses') or relative in seen):
            raise ValueError('Unsafe native inventory path')
        seen.add(relative)
        path = prepared / relative
        if any(part.is_symlink() for part in (path, *path.parents)):
            raise ValueError('Linked native inventory path')
        raw = path.read_bytes()
        if len(raw) != item['size'] or hashlib.sha256(raw).hexdigest() != item['sha256']:
            raise ValueError('Packaged native inventory bytes mismatch')
        files.append((relative, raw))
    runtime.update(owner=launcher.OWNER, root=str(root),
                   execution_configuration_sha256=launcher.execution_configuration_sha256())
    return runtime, selected, files


def initialize(configuration, config_path):
    """Prepare mutable execution records from exact packaged inventories, then initialize."""
    host_prerequisites()
    from hyprn_mvp_integration import launcher
    import native_environment
    root = Path(configuration['execution_root'])
    if any(root.iterdir()):
        raise ValueError('Refusing nonempty execution store')
    runtime, selected, files = packaged_inventory(configuration)
    execution_home(configuration, create=True)
    execution_temporary(configuration, create=True)
    select_execution_temporary(configuration)
    # Source/image checks use the original built identities; nothing is rebuilt here.
    for name in ('locks', 'licenses', 'evidence'):
        (root / name).mkdir(mode=0o700)
    for relative, raw in files:
        target = root / relative
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        target.write_bytes(raw)
    (root / 'runtime.json').write_bytes(canonical(runtime))
    (root / 'selected.json').write_bytes(selected)
    (root / 'launch-worker').write_text(wrapper(configuration, config_path))
    (root / 'launch-worker').chmod(0o700)
    launcher.fingerprint()  # Fail closed if the loaded worker differs from the packaged one.
    with contextlib.redirect_stdout(sys.stderr):
        native_environment.initialize(root, configuration)
    return inspect(configuration, config_path)


def inspect(configuration, config_path, *, attested=False):
    if attested:
        host_prerequisites(configuration)
    from hyprn_mvp_integration.calculation import NativeExecution
    root = Path(configuration['execution_root'])
    if (root / 'rebind-pending.json').exists():
        raise ValueError('Native rebind requires reconciliation')
    expected = wrapper(configuration, config_path)
    launch = root / 'launch-worker'
    if launch.is_symlink() or launch.read_text() != expected:
        raise ValueError('Native launch wrapper changed')
    native = NativeExecution.from_environment()
    if attested:
        native.require_attestation()
    pinned = json.loads((root / 'profile-identity.json').read_bytes())
    return {'schema': 'hyprn-native-owner/v1', 'installation_id': configuration['installation_id'],
            'store_id': configuration['store_id'], 'execution_root': str(root),
            'profile': configuration['profile'],
            **{key: pinned[key] for key in ('profile_uuid', 'repository_uuid', 'computer_uuid', 'code_uuid')},
            'release_sha256': configuration['release_sha256'],
            'config_sha256': configuration['config_sha256']}


def rebind_request(path, configuration):
    """Only a protected host receipt authorizes replacement of retained metadata."""
    from hyprn_mvp_integration import installation
    path = Path(path)
    if not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Unsafe rebind authorization')
    for candidate in (path, path.parent):
        info = candidate.stat()
        if info.st_uid != 0 or info.st_mode & 0o022:
            raise ValueError('Rebind requires protected host authority')
    if not stat.S_ISREG(path.stat().st_mode) or path.stat().st_nlink != 1:
        raise ValueError('Rebind requires a regular host authorization')
    request = installation.parse(path.read_bytes())
    if (set(request) != {'schema', 'previous', 'owner', 'configuration_sha256'}
            or request['schema'] != 'hyprn-native-rebind/v1'
            or request['configuration_sha256'] != hashlib.sha256(canonical(configuration)).hexdigest()):
        raise ValueError('Rebind authorization differs from selected release')
    previous = installation.validate_cloud_execution(request['previous'])
    # Store and engine authority cannot be changed as a side effect of a release.
    stable = ('schema', 'edition', 'installation_id', 'store_id', 'execution_root',
              'profile', 'host_home', 'docker')
    if any(previous[key] != configuration[key] for key in stable):
        raise ValueError('Rebind cannot change native ownership or containment paths')
    if previous == configuration:
        raise ValueError('Rebind requires a different release configuration')
    projection = {key: value for key, value in previous.items()
                  if key not in ('release_sha256', 'config_sha256')}
    if previous['config_sha256'] != hashlib.sha256(canonical(projection)).hexdigest():
        raise ValueError('Previous execution projection digest differs')
    owner = request['owner']
    keys = ('installation_id', 'store_id', 'execution_root', 'profile',
            'release_sha256', 'config_sha256')
    if (owner.get('schema') != 'hyprn-native-owner/v1'
            or any(owner.get(key) != previous[key] for key in keys)):
        raise ValueError('Previous protected native identity differs')
    return previous, owner


def replace_record(path, raw, *, mode=0o600):
    temporary = path.with_name('.' + path.name + '.new')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def rebind(configuration, config_path, authorization):
    """Replace execution metadata only; the native store and recorded nodes stay intact."""
    host_prerequisites()
    from hyprn_mvp_integration import launcher
    from hyprn_mvp_integration.calculation import NativeExecution
    previous, owner = rebind_request(authorization, configuration)
    root = Path(configuration['execution_root'])
    fd = os.open(root / 'executor.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        pending = root / 'rebind-pending.json'
        if pending.exists():
            raise ValueError('Native rebind requires reconciliation')
        execution_temporary(configuration, create=True)
        select_execution_temporary(configuration)
        NativeExecution.from_environment()
        from aiida import orm
        if any(not node.is_terminated for node, in orm.QueryBuilder().append(orm.ProcessNode).iterall()):
            raise ValueError('Native accepted processes require reconciliation')
        pinned = json.loads((root / 'profile-identity.json').read_bytes())
        if any(pinned[key] != owner[key] for key in
               ('profile_uuid', 'repository_uuid', 'computer_uuid', 'code_uuid')):
            raise ValueError('Native identity differs from protected previous receipt')
        launch = root / 'launch-worker'
        if launch.is_symlink() or launch.read_text() != wrapper(previous, config_path):
            raise ValueError('Previous native launch wrapper changed')
        old_runtime = json.loads((root / 'runtime.json').read_bytes())
        if (old_runtime.get('execution_configuration_sha256') != hashlib.sha256(canonical(previous)).hexdigest()
                or old_runtime.get('root') != str(root) or old_runtime.get('owner') != launcher.OWNER
                or old_runtime.get('selected_sha256') != hashlib.sha256((root / 'selected.json').read_bytes()).hexdigest()):
            raise ValueError('Previous native runtime identity differs')
        runtime, selected, files = packaged_inventory(configuration)
        replacements = [*files, (Path('runtime.json'), canonical(runtime)),
                        (Path('selected.json'), selected),
                        (Path('launch-worker'), wrapper(configuration, config_path).encode())]
        # Validate destinations before starting; a partial operation retains its
        # pending marker and cannot be mistaken for a completed owner operation.
        for relative, _raw in [*replacements, (Path('evidence/execution-polling.json'), b'')]:
            target = root / relative
            for part in (target, *target.parents):
                if part == root.parent:
                    break
                if part.is_symlink() or (part.exists() and part.stat().st_uid != os.getuid()):
                    raise ValueError('Unsafe retained inventory destination')
        import native_environment
        computer = orm.load_computer(pinned['computer_uuid'])
        previous_poll = computer.get_minimum_job_poll_interval()
        with pending.open('x') as stream:
            json.dump({'previous': owner,
                       'previous_minimum_job_poll_interval': previous_poll,
                       'configuration_sha256': hashlib.sha256(
                           canonical(configuration)).hexdigest()}, stream)
            stream.flush()
            os.fsync(stream.fileno())
        for relative, raw in replacements:
            target = root / relative
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            replace_record(target, raw, mode=0o700 if relative == Path('launch-worker') else 0o600)
        # This is an owner deployment setting, not a change to any scientific
        # record. The pending journal retains its old value for recovery.
        poll_seconds = min(previous_poll, native_environment.MAX_JOB_POLL_SECONDS)
        computer.set_minimum_job_poll_interval(poll_seconds)
        replace_record(root / 'evidence' / 'execution-polling.json', canonical({
            'computer_uuid': pinned['computer_uuid'],
            'previous_seconds': previous_poll,
            'current_seconds': poll_seconds,
            'release_sha256': configuration['release_sha256'],
        }))
        execution_home(configuration, create=True)
        launcher.fingerprint()
        # The old containment evidence remains available, but cannot match this
        # release/configuration fingerprint. Only explicit qualify renews it.
        pending.unlink()
        return inspect(configuration, config_path)
    finally:
        os.close(fd)


def serve(configuration, config_path, command):
    """One owner lock and one attached dispatcher; fixed bridge methods only."""
    from hyprn_mvp_integration.calculation import NativeExecution
    from dispatch_bridge import bridge_child
    def stopped(_signal, _frame):
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, stopped)
    root = Path(configuration['execution_root'])
    fd = os.open(root / 'executor.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        receipt = inspect(configuration, config_path, attested=True)
        native = NativeExecution.from_environment()
        # The host has constructed this fixed argv from the pinned renderer. No
        # shell, user command, application secret or runtime document reaches here.
        def ready():
            print(json.dumps(receipt), flush=True)
        return bridge_child(native, command, env={'PATH': os.environ['PATH'],
                            'DOCKER_HOST': configuration['docker']['endpoint']},
                            cwd=configuration['source'], stderr=sys.stderr, on_ready=ready,
                            allow_exports=True,
                            before_call=lambda method: scratch_admission(configuration, method))
    finally:
        os.close(fd)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    parser.add_argument('operation', choices=('initialize', 'inspect', 'check', 'attest', 'launch', 'serve', 'rebind'))
    parser.add_argument('arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    configuration = bootstrap(args.config)
    arguments = args.arguments[1:] if args.arguments[:1] == ['--'] else args.arguments
    if args.operation == 'launch':
        host_prerequisites(configuration)
        from hyprn_mvp_integration import launcher
        sys.argv = [sys.argv[0], *arguments]
        with execution_scratch_session(configuration):
            launcher.main()
        return 0
    if args.operation == 'serve':
        # Fixed container invocation is assembled by trusted lifecycle code.
        # This process never accepts generic executable selection.
        import re
        if len(arguments) != 1 or not re.fullmatch(r'[0-9a-f]{64}', arguments[0]):
            raise ValueError('Fixed owned dispatcher invocation required')
        with execution_scratch_session(configuration):
            return serve(configuration, args.config,
                         ['docker', 'start', '--attach', '--interactive', arguments[0]])
    if args.operation == 'rebind':
        if len(arguments) != 1:
            raise ValueError('Protected rebind authorization required')
        result = rebind(configuration, args.config, arguments[0])
        print(json.dumps(result), flush=True)
        return 0
    if arguments:
        raise ValueError('Unexpected native operation arguments')
    if args.operation == 'initialize':
        result = initialize(configuration, args.config)
    elif args.operation == 'attest':
        host_prerequisites(configuration)
        from hyprn_mvp_integration import launcher
        inspect(configuration, args.config)
        launcher.attest()
        result = inspect(configuration, args.config, attested=True)
    else:
        result = inspect(configuration, args.config, attested=args.operation == 'check')
    print(json.dumps(result), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
