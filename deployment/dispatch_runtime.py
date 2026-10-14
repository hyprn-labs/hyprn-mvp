"""One dedicated executor for the new application and exact fresh native store.

Only fixed native operations cross a private stdio channel. No listening
socket, generic RPC, retry lease, native lifecycle manager or extra database.
The execution store and the native interpreter come from deployment/local_paths.py
(HYPRN_MVP_DATA_ROOT, else the installation configuration named by HYPRN_MVP_CONFIG, which the
executor and its native children inherit, so the attested launcher reads the same
installation); main() refuses while they are unset.
"""

import argparse
import contextlib
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import signal
import time
import uuid
import application_runtime
import release as release_binding
import local_paths

ROOT = local_paths.execution_root(required=False)
PYTHON = local_paths.native_python(required=False)


def native_call(native, method, values, *, read_only=False, exports_only=False, native_fault=None):
    """Fixed private wire dispatch; hydration has no execution operations."""
    from hyprn_mvp_app.dispatcher import (
        encode_files,
        decode_files,
        encode_record,
        bridge_request,
        archive_response,
    )

    bridge_request(method, values, read_only=read_only, exports_only=exports_only)
    if method == 'archive_record':
        return archive_response(native.archive_record(values[0]))
    if method == 'resolve_results':
        return native.resolve_results(values[0])
    if method == 'read_record':
        return encode_record(native.read_record(*values))
    if method == 'require_attestation':
        native.require_attestation()
        return True
    if method == 'bundle_runtime':
        return encode_files(native.bundle_runtime())
    if method == 'launch':
        return native.launch(decode_files(values[0]), values[1])
    if method == 'matches':
        if native_fault == 'lookup_timeout':
            raise TimeoutError()
        result = native.matches(values[0])
        return result + result if native_fault == 'multiple' else result
    return native.inspect(values[0])


def bridge_child(
    native,
    command,
    *,
    read_only=False,
    exports_only=False,
    allow_exports=False,
    native_fault=None,
    env=None,
    cwd=None,
    stderr=None,
    on_ready=lambda: None,
):
    """Owned bounded stdio transport, also used by isolated backend fixtures."""
    from hyprn_mvp_app.dispatcher import MAX_MESSAGE, bridge_operation, bridge_encode, bridge_decode

    if release_binding.ACTIVE is not None and release_binding.ACTIVE.bound:
        release_binding.module_record(
            'hyprn_mvp_app.dispatcher'
        )  # live seam must be the selected release
    child = subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr, env=env, cwd=cwd
    )
    try:
        on_ready()
        while True:
            raw = child.stdout.readline(MAX_MESSAGE + 1)
            if not raw:
                break
            if len(raw) > MAX_MESSAGE:
                raise RuntimeError('App bridge bound')
            archive_mode = exports_only or (
                allow_exports and bridge_decode(raw).get('method') == 'archive_record'
            )
            method, values = bridge_operation(raw, read_only=read_only, exports_only=archive_mode)
            try:
                with contextlib.redirect_stdout(sys.stderr):
                    result = native_call(
                        native,
                        method,
                        values,
                        read_only=read_only,
                        exports_only=archive_mode,
                        native_fault=native_fault,
                    )
                response = dict(data=result)
            except (OSError, RuntimeError, ValueError, TimeoutError):
                response = dict(error='native_unavailable')
            child.stdin.write(bridge_encode(response))
            child.stdin.flush()
        return child.wait()
    finally:
        child.stdin.close()
        child.stdout.close()
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=10)


def process_identity(pid):
    def field(name):
        return subprocess.run(
            ['/bin/ps', '-ww', '-p', str(pid), '-o', name + '='],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

    return dict(command=field('command'), started=field('lstart'))


def process_status(root=None):
    """Exact owned executor identity from any source; matches_source names this one."""
    try:
        saved = json.loads((Path(root or local_paths.require(ROOT)) / 'executor.json').read_text())
        ps = process_identity(saved['pid'])
        alive = (
            ps == saved['identity']
            and ps['command'].endswith(' --serve')
            and '/deployment/dispatch_runtime.py --serve' in ps['command']
        )
        if not alive:
            return dict(running=False, pid=None)
        own = ps['command'].endswith(str(Path(__file__).resolve()) + ' --serve')
        return dict(
            running=True, pid=saved['pid'], matches_source=own, release=saved.get('release')
        )
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError):
        return dict(running=False, pid=None)


def executor_quiescence(root=None):
    """Fail-closed proof that no owned executor can be running.

    process_status() is deliberately fail-open for status display (unparsable state reads as
    stopped). Effectful steps (bind-launch-worker, application upgrade) instead
    require: no symlinked state, a parsable executor.json (when present), no live executor
    with that identity, and executor.lock not held (non-blocking flock probe, released at once).
    """
    root = Path(root or local_paths.require(ROOT))
    state, lock = root / 'executor.json', root / 'executor.lock'
    if any(p.is_symlink() for p in (root, state, lock)):
        raise ValueError('Executor state or lock is a symlink; refusing')
    recorded = 'absent'
    if state.exists():
        try:
            saved = json.loads(state.read_text())
            identity = saved['identity']
            if (
                type(saved.get('pid')) is not int
                or saved['pid'] <= 0
                or not isinstance(identity, dict)
                or not all(isinstance(identity.get(k), str) for k in ('command', 'started'))
            ):
                raise ValueError('fields')
        except (ValueError, KeyError, TypeError, UnicodeDecodeError):
            raise ValueError(
                'Unparsable executor.json; refusing (inspect the owned executor state first)'
            ) from None
        recorded = 'valid'
    status = process_status() if root == ROOT else process_status(root)
    if status['running']:
        raise ValueError('Executor is running; stop it with its own manager first')
    if not lock.exists():
        return dict(running=False, executor_json=recorded, lock='absent')
    fd = os.open(lock, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('executor.lock is held by another process; refusing') from None
    finally:
        os.close(fd)
    return dict(running=False, executor_json=recorded, lock='free')


def require_bound_release():
    """Every operation except --status runs only inside a selected, verified release."""
    binding = release_binding.ACTIVE
    if binding is None or not binding.bound:
        raise RuntimeError(
            'dispatch_runtime requires a selected release binding (use the '
            'manifest-qualified command)'
        )
    return binding


def release_record():
    binding = release_binding.ACTIVE
    return binding.record() if binding is not None else None


def require_release_start():
    """Bound start only: launch-worker wrapper, app container source and served UI all
    belong to the selected release. Reads files only; no runtime effect."""
    binding = release_binding.ACTIVE
    if binding is None or not binding.bound:
        raise RuntimeError('Executor start requires a selected release binding')
    manifest, _ = release_binding.verify(
        binding.manifest_path.parent, expected_sha256=binding.manifest_sha256
    )
    release_binding.require_checkout(manifest)
    import native_environment

    try:
        launch = native_environment.require_launch_worker(ROOT, binding)
    except ValueError as error:
        raise RuntimeError(str(error)) from None
    try:
        container = application_runtime.require_release_inventory(binding)
    except ValueError as error:
        raise RuntimeError(str(error)) from None
    if manifest.get('images'):
        require_runtime_images(manifest)
    # A release whose manifest cites an independent review starts only with its recorded
    # review; the record digest is kept in executor.json (the activation record of this start).
    try:
        review = release_binding.require_review(
            binding.manifest_path.parent, manifest, binding.manifest_sha256
        )
    except release_binding.ReleaseError as error:
        raise RuntimeError(str(error)) from None
    return dict(
        release_id=binding.release_id,
        manifest_sha256=binding.manifest_sha256,
        manifest_path=str(binding.manifest_path),
        source_root=str(binding.source),
        launch_worker=launch,
        review=review,
        container=container,
    )


def require_runtime_images(manifest):
    """Read current runtime identities and attestation; never build or re-attest on start."""
    import execution_runtime

    model = application_runtime.modeling_runtime
    modeling = model.check(model.DEFAULT_ROOT)
    if modeling['image'] != manifest['images']['modeling']:
        raise RuntimeError('Modeling image differs from the selected release')
    attestation = execution_runtime.launcher().require_attestation(root=ROOT)
    if attestation['fingerprint']['image'] != manifest['images']['worker']:
        raise RuntimeError('Worker image differs from the selected release')
    return attestation


def verify_child_binding(pid, release, token):
    """Read exactly the record of this child (pid + one-shot start token), never a stale one."""
    path = ROOT / 'evidence/release-binding' / ('executor-' + str(int(pid)) + '-' + token + '.json')
    record = json.loads(path.read_text())
    if record.get('pid') != pid:
        raise RuntimeError('Executor evidence pid differs from the started child')
    if (record['release_id'], record['manifest_sha256'], record['source_root']) != (
        release['release_id'],
        release['manifest_sha256'],
        release['source_root'],
    ):
        raise RuntimeError('Executor child bound a different release')
    if set(record['modules']) != set(release_binding.EVIDENCE_MODULES):
        raise RuntimeError('Executor module evidence incomplete')
    return str(path)


def manage(operation):
    current = process_status()
    if operation == 'status':
        return dict(current, binding=release_record())
    if current['running'] and not current.get('matches_source'):
        raise RuntimeError(
            'Executor is bound to a different source; use its manifest-qualified command'
        )
    if operation == 'stop':
        if current['running']:
            os.kill(current['pid'], signal.SIGTERM)
            for _ in range(100):
                if not process_status()['running']:
                    break
                time.sleep(0.1)
            else:
                raise RuntimeError('Executor has not stopped; inspect owned process')
        return process_status()
    if current['running']:
        return current
    if Path(sys.executable) != PYTHON:
        raise RuntimeError('Use reviewed native interpreter')
    # Release gates (launch-worker, container source, served UI) read files only and refuse first.
    release = require_release_start()
    application_runtime.check()
    token = uuid.uuid4().hex
    with (ROOT / 'evidence/executor-service.log').open('ab') as log:
        child = subprocess.Popen(
            [sys.executable, '-B', str(Path(__file__).resolve()), '--serve'],
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            start_new_session=True,
            cwd=application_runtime.REPO,
            env={
                **os.environ,
                'AIIDA_PATH': str(ROOT / 'aiida'),
                'PYTHONDONTWRITEBYTECODE': '1',
                release_binding.ENV_EVIDENCE_TOKEN: token,
            },
        )
    for _ in range(100):
        if child.poll() is not None:
            raise RuntimeError('Executor startup failed; inspect private log')
        try:
            if int((ROOT / 'executor.ready').read_text()) == child.pid:
                identity = process_identity(child.pid)
                try:
                    release['child_evidence'] = verify_child_binding(child.pid, release, token)
                except (OSError, ValueError, KeyError, RuntimeError):
                    child.terminate()
                    child.wait(timeout=10)
                    raise RuntimeError('Executor child release binding not proven; stopped')
                (ROOT / 'executor.json').write_text(
                    json.dumps(dict(pid=child.pid, identity=identity, release=release)) + '\n'
                )
                return process_status()
        except (OSError, ValueError):
            pass
        time.sleep(0.1)
    raise RuntimeError('Executor startup not confirmed')


def main():
    local_paths.require(ROOT)
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    for operation in ('start', 'stop', 'status', 'serve'):
        group.add_argument('--' + operation, action='store_true')
    parser.add_argument('--run-id')
    parser.add_argument('--hydrate', action='store_true')
    parser.add_argument('--actor-id')
    parser.add_argument('--study-id')
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--exports-only', action='store_true')
    parser.add_argument('--export-request')
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--fault', choices=['after_prepare', 'before_claim', 'after_claim'])
    parser.add_argument(
        '--native-fault',
        choices=[
            'before_node',
            'after_node',
            'before_continuation',
            'after_continuation',
            'before_response',
            'lookup_timeout',
            'multiple',
        ],
    )
    args = parser.parse_args()
    if args.exports_only:
        if not (args.once or args.export_request) or any(
            (
                args.start,
                args.stop,
                args.status,
                args.serve,
                args.run_id,
                args.hydrate,
                args.actor_id,
                args.study_id,
                args.prepare_only,
                args.fault,
                args.native_fault,
            )
        ):
            parser.error('Exports require bounded mode and no execution options')
    elif args.export_request:
        parser.error('Export request requires exports-only mode')
    if args.export_request:
        from uuid import UUID

        try:
            if str(UUID(args.export_request)) != args.export_request:
                raise ValueError()
        except ValueError:
            parser.error('Canonical export request identity required')
    if args.hydrate:
        if not all((args.actor_id, args.study_id, args.run_id)) or any(
            (
                args.start,
                args.stop,
                args.status,
                args.serve,
                args.once,
                args.prepare_only,
                args.fault,
                args.native_fault,
            )
        ):
            parser.error('Hydration requires exact actor/study/run and no execution options')
    elif args.actor_id or args.study_id:
        parser.error('Actor/study are for authorized hydration only')
    # Only the import-free --status may run unbound; the __main__ entrypoint is not the only gate.
    if not args.status:
        require_bound_release()
    for operation in ('start', 'stop', 'status'):
        if getattr(args, operation):
            if args.run_id or args.fault or args.native_fault or args.prepare_only or args.once:
                parser.error('Management command cannot dispatch')
            print(json.dumps(manage(operation)))
            return 0
    if (args.fault or args.native_fault or args.prepare_only) and not args.run_id:
        parser.error('Explicit run required')
    if os.environ.get('AIIDA_PATH') != str(ROOT / 'aiida'):
        raise RuntimeError('Explicit new AIIDA_PATH required')
    application_runtime.check()
    # Single host executor plus the app-side flock: both hold across native calls.
    fd = os.open(ROOT / 'executor.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    from hyprn_mvp_integration.calculation import NativeExecution
    from hyprn_mvp_app.dispatcher import MAX_MESSAGE, bridge_operation, bridge_encode

    token = os.environ.pop(
        release_binding.ENV_EVIDENCE_TOKEN, None
    )  # one-shot; never inherited further
    if release_binding.ACTIVE is not None and release_binding.ACTIVE.bound:
        import native_environment

        native_environment.require_launch_worker(
            ROOT, release_binding.ACTIVE
        )  # before any native call
        # Actual module files/cwd/argv/hashes of this process, before any native call.
        evidence = ROOT / 'evidence/release-binding'
        release_binding.write_evidence(
            evidence,
            release_binding.process_evidence(),
            'executor' if args.serve else 'dispatch',
            token=token,
        )
        os.environ[release_binding.ENV_EVIDENCE] = str(evidence)
    native = NativeExecution.from_environment()
    if not (args.hydrate or args.exports_only or args.serve):
        native.require_attestation()
    if args.native_fault:

        def fault(point):
            if point == args.native_fault:
                os._exit(78)

        native.fault = fault
    command = [
        'docker',
        'exec',
        '-i',
        application_runtime.NAME,
        'python',
        '-B',
        '-m',
        'hyprn_mvp_app.dispatcher',
    ]
    for name in ('run_id', 'fault', 'actor_id', 'study_id', 'export_request'):
        if getattr(args, name):
            command.extend(['--' + name.replace('_', '-'), getattr(args, name)])
    for name in ('once', 'prepare_only', 'hydrate', 'exports_only'):
        if getattr(args, name):
            command.append('--' + name.replace('_', '-'))
    if args.serve:
        command.append('--with-exports')

    def stopped(signum, frame):
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stopped)
    try:

        def ready():
            if args.serve:
                (ROOT / 'executor.ready').write_text(str(os.getpid()))

        return bridge_child(
            native,
            command,
            read_only=args.hydrate,
            exports_only=args.exports_only,
            allow_exports=args.serve,
            native_fault=args.native_fault,
            on_ready=ready,
        )
    finally:
        os.close(fd)


if __name__ == '__main__':
    # Bind before any project import; only plain --status is read-only and import-free.
    read_only = sys.argv[1:] == ['--status']
    release_binding.entrypoint(__file__, read_only=read_only, project_imports=not read_only)
    sys.exit(main())
