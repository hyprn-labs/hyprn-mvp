"""Fixed private dispatcher transport shared by local and cloud execution owners."""

import contextlib
import json
import queue
import subprocess
import sys
import threading
import time
import release as release_binding


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
    if method == 'explore':
        return native.explore(values[0])
    if method == 'surrogate':
        return native.surrogate(values[0], values[1])
    if method == 'read_record':
        return encode_record(native.read_record(*values))
    if method == 'require_attestation':
        native.require_attestation()
        return True
    if method == 'bundle_runtime':
        return encode_files(native.bundle_runtime())
    if method == 'launch_batch':
        return native.launch_batch([
            dict(item, bundle=decode_files(item['bundle'])) for item in values[0]
        ])
    if method == 'launch_budgeted':
        return native.launch_budgeted(decode_files(values[0]), values[1], values[2])
    if method == 'launch':
        return native.launch(decode_files(values[0]), values[1])
    if method == 'matches':
        if native_fault == 'lookup_timeout':
            raise TimeoutError()
        result = native.matches(values[0])
        return result + result if native_fault == 'multiple' else result
    return native.inspect(values[0])


def observed_native_call(native, method, values, **options):
    """Bounded operational timing without inputs, identities or exception text."""
    started = time.monotonic()
    outcome = 'failed'
    try:
        result = native_call(native, method, values, **options)
        outcome = 'finished'
        return result
    except TimeoutError:
        outcome = 'timeout'
        raise
    finally:
        if method not in ('require_attestation', 'bundle_runtime', 'matches', 'inspect'):
            print(json.dumps(dict(event='native_operation', operation=method,
                                  duration_ms=round((time.monotonic() - started) * 1000, 3),
                                  outcome=outcome)), file=sys.stderr, flush=True)


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
    # Fixed bounded lanes in the existing private stdio channel. The main
    # thread alone touches AiiDA and candidate execution; the reader may only
    # warm/query immutable numerical state, while observation verifies the
    # retained runtime and attestation. There is no dispatch queue for runs.
    primary_requests = queue.Queue(maxsize=1)
    observation_requests = queue.Queue(maxsize=1)
    write_lock = threading.Lock()
    stopped = threading.Event()

    def reply(response):
        with write_lock:
            child.stdin.write(bridge_encode(response))
            child.stdin.flush()

    def observe():
        while not stopped.is_set():
            try:
                method, values = observation_requests.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                response = dict(data=observed_native_call(native, method, values))
            except TimeoutError:
                response = dict(error='native_timeout')
            except (OSError, RuntimeError, ValueError):
                response = dict(error='native_unavailable')
            try:
                reply(dict(response, channel='observation'))
            except (OSError, ValueError):
                stopped.set()

    def receive():
        try:
            while not stopped.is_set():
                raw = child.stdout.readline(MAX_MESSAGE + 1)
                if not raw:
                    break
                if len(raw) > MAX_MESSAGE:
                    raise ValueError('App bridge bound')
                method, values = bridge_operation(
                    raw,
                    read_only=read_only,
                    exports_only=exports_only
                    or (allow_exports and bridge_decode(raw).get('method') == 'archive_record'),
                )
                if method in ('require_attestation', 'bundle_runtime'):
                    observation_requests.put_nowait((method, values))
                elif method == 'surrogate':
                    try:
                        response = dict(data=observed_native_call(native, method, values))
                    except TimeoutError:
                        response = dict(error='native_timeout')
                    except (OSError, RuntimeError, ValueError):
                        response = dict(error='native_unavailable')
                    reply(dict(response, channel='surrogate'))
                else:
                    primary_requests.put_nowait(raw)
        except (OSError, ValueError, queue.Full):
            stopped.set()
        finally:
            stopped.set()

    reader = threading.Thread(target=receive, name='surrogate-bridge', daemon=True)
    reader.start()
    observer = threading.Thread(target=observe, name='native-observation', daemon=True)
    observer.start()
    try:
        on_ready()
        while True:
            try:
                raw = primary_requests.get(timeout=0.1)
            except queue.Empty:
                if stopped.is_set():
                    break
                continue
            if len(raw) > MAX_MESSAGE:
                raise RuntimeError('App bridge bound')
            archive_mode = exports_only or (
                allow_exports and bridge_decode(raw).get('method') == 'archive_record'
            )
            method, values = bridge_operation(raw, read_only=read_only, exports_only=archive_mode)
            try:
                with contextlib.redirect_stdout(sys.stderr):
                    result = observed_native_call(
                        native,
                        method,
                        values,
                        read_only=read_only,
                        exports_only=archive_mode,
                        native_fault=native_fault,
                    )
                response = dict(data=result)
            except TimeoutError:
                response = dict(error='native_timeout')
            except (OSError, RuntimeError, ValueError):
                response = dict(error='native_unavailable')
            reply(response)
        try:
            return child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            child.terminate()
            return child.wait(timeout=10)
    finally:
        stopped.set()
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=10)
        reader.join(timeout=35)
        observer.join(timeout=35)
        if hasattr(native, 'close_surrogate'):
            native.close_surrogate()
        child.stdin.close()
        child.stdout.close()


