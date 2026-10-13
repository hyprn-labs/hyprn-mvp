#!/usr/bin/env python3
"""Bounded worker isolation: attestation and isolated runs of the pinned worker image.

``launch_worker.py`` runs one bounded source bundle through ``isolated`` after
``require_attestation``; ``verify-isolation`` produces the containment attestation that
both require. No existing profiles, containers or services are enumerated or reused.
All generated state is below the private isolation root,
``<HYPRN_MVP_DATA_ROOT>/execution/isolation`` (see deployment/local_paths.py); every
command refuses while the data root is unset.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import platform
import selectors
import shutil
import subprocess
import sys
import time
import uuid
import local_paths

REPO = Path(__file__).resolve().parents[1]
# Private isolation root below the execution store (deployment/local_paths.py); None while unset.
_EXECUTION = local_paths.execution_root(required=False)
ROOT = None if _EXECUTION is None else _EXECUTION / 'isolation'
LABEL = 'org.hyprn-mvp.owner=hyprn-mvp-isolation'
ATTESTATION = 'containment.json'
POLICY = {'memory': '256m', 'cpus': '0.5', 'pids': '32', 'wall_seconds': 15,
          'output_bytes': 65536, 'scratch_bytes': 16777216, 'user': '65534:65534'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def independent_root():
    # No symlink ancestors, no cloud-sync location, no access shared with others.
    root = local_paths.require(ROOT)
    for part in [root, *root.parents]:
        if part.is_symlink():
            raise RuntimeError('Runtime symlink refused: ' + str(part))
    if any(word in str(root.resolve()).lower() for word in
           ('cloudstorage', 'google drive', 'googledrive', 'dropbox', 'onedrive', 'mobile documents')):
        raise RuntimeError('Cloud-synced runtime refused')
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if root.stat().st_uid != os.getuid() or root.stat().st_mode & 0o077:
        raise RuntimeError('Runtime must be owned by this user and mode 0700')
    for name in ('evidence', 'runs'):
        (root / name).mkdir(exist_ok=True, mode=0o700)
    return root


def command(args, timeout=120):
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError('Command failed: ' + ' '.join(args) + '\n' + result.stderr[-6000:])
    return result.stdout.strip()


def image_pin():
    pins = json.loads((REPO / 'deployment' / 'pins.json').read_text())
    image = pins.get('worker_image')
    if not image or not image.startswith('sha256:'):
        raise RuntimeError('Build and pin the worker image by immutable image ID before verification')
    return image


def fingerprint():
    image = image_pin()
    info = json.loads(command(['docker', 'image', 'inspect', image]))[0]
    return {'target': platform.platform(), 'engine': json.loads(command(['docker', 'version', '--format', '{{json .Server}}'])),
            'image': info['Id'], 'policy': POLICY,
            'launcher_sha256': digest(Path(__file__).read_bytes()),
            'entrypoint_sha256': digest((Path(__file__).parent / 'launch_worker.py').read_bytes())}


def require_attestation():
    path = local_paths.require(ROOT) / 'evidence' / ATTESTATION
    if not path.exists():
        raise RuntimeError('Execution denied: missing containment attestation; run verify-isolation')
    attestation = json.loads(path.read_text())
    if not attestation.get('passed') or attestation['fingerprint'] != fingerprint():
        raise RuntimeError('Execution denied: failed or stale containment attestation')
    return attestation


def isolated(source, synthetic=False, wall=None):
    if not synthetic:
        require_attestation()
    run_id = 'hyprn-mvp-isolation-' + uuid.uuid4().hex
    run = local_paths.require(ROOT) / 'runs' / run_id
    run.mkdir(mode=0o755)
    entry = run / 'entry.py'
    entry.write_text(source)
    entry.chmod(0o444)
    args = ['docker', 'run', '--name', run_id, '--label', LABEL, '--network', 'none',
            '--user', POLICY['user'], '--read-only', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges', '--memory', POLICY['memory'],
            '--memory-swap', POLICY['memory'], '--cpus', POLICY['cpus'],
            '--pids-limit', POLICY['pids'], '--ulimit', 'fsize=1048576:1048576',
            '--log-driver', 'none', '--tmpfs', '/tmp:rw,noexec,nosuid,size=16m,mode=1777',
            '--tmpfs', '/output:rw,noexec,nosuid,size=16m,mode=1777',
            '--mount', 'type=bind,source=' + str(entry) + ',target=/input/entry.py,readonly',
            '--workdir', '/output', '--env', 'HOME=/tmp', '--env', 'OPENMDAO_REPORTS=0',
            '--env', 'OPENBLAS_NUM_THREADS=1', '--env', 'PYTHONDONTWRITEBYTECODE=1',
            image_pin(), 'python', '-B', '/input/entry.py']
    started = time.monotonic()
    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    collected = bytearray()
    reason = 'exited'
    selector = selectors.DefaultSelector()
    selector.register(proc.stdout, selectors.EVENT_READ)
    try:
        while selector.get_map():
            if time.monotonic() - started > (wall or POLICY['wall_seconds']):
                reason = 'wall_limit'
                break
            for key, _ in selector.select(timeout=0.1):
                chunk = os.read(key.fileobj.fileno(), 8192)
                if not chunk:
                    selector.unregister(key.fileobj)
                    break
                collected.extend(chunk)
                if len(collected) > POLICY['output_bytes']:
                    reason = 'output_limit'
                    break
            if reason != 'exited':
                break
        if reason != 'exited':
            # Close the attached Docker client first: a full stdout pipe can
            # otherwise block the daemon's kill response and container removal.
            proc.kill()
            proc.wait(timeout=10)
            command(['docker', 'kill', run_id], timeout=20)
        proc.wait(timeout=10)
        state = json.loads(command(['docker', 'inspect', '--format', '{{json .State}}', run_id]))
        result = {'id': run_id, 'reason': reason, 'exit_code': proc.returncode,
                  'seconds': time.monotonic() - started, 'state': state,
                  'output': bytes(collected[:POLICY['output_bytes']]).decode(errors='replace'),
                  'source_sha256': digest(source.encode())}
        save(run / 'result.json', result)
        return result
    finally:
        selector.close()
        # Exact newly allocated name only; never enumerate or stop other workloads.
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=10)
        subprocess.run(['docker', 'rm', '-f', run_id], capture_output=True, timeout=20)


def verify_isolation():
    root = independent_root()
    attestation_path = root / 'evidence' / ATTESTATION
    if attestation_path.exists():
        archived = attestation_path.with_name(attestation_path.stem + '-' + digest(attestation_path.read_bytes()) + '.json')
        if not archived.exists():
            shutil.copyfile(attestation_path, archived)
    before = fingerprint()
    cases = {}
    # The probe is synthetic container source: the account home is substituted as a literal.
    basic = '''import json, os, socket
HOST_HOME = ''' + repr(str(local_paths.account_home())) + '''
checks = {'nonroot': os.getuid() != 0, 'socket_absent': not os.path.exists('/var/run/docker.sock'),
          'host_home_absent': not os.path.exists(HOST_HOME),
          'credentials_absent': not any(k.startswith(('AWS_', 'OPENAI_', 'AIIDA_')) for k in os.environ)}
for name, path in [('root_readonly','/escape'), ('input_readonly','/input/entry.py')]:
    try:
        open(path, 'w').write('canary')
        checks[name] = False
    except OSError:
        checks[name] = True
sock = socket.socket(); sock.settimeout(1)
try:
    sock.connect(('1.1.1.1',443)); checks['network_denied'] = False
except OSError:
    checks['network_denied'] = True
checks['cpu_limit'] = open('/sys/fs/cgroup/cpu.max').read().strip() == '50000 100000'
checks['memory_limit'] = open('/sys/fs/cgroup/memory.max').read().strip() == '268435456'
checks['pid_limit'] = open('/sys/fs/cgroup/pids.max').read().strip() == '32'
print(json.dumps(checks)); assert all(checks.values())
'''
    cases['access'] = isolated(basic, synthetic=True)
    cases['memory'] = isolated("x = bytearray(512 * 1024 * 1024)", synthetic=True)
    cases['wall'] = isolated('while True: pass', synthetic=True, wall=3)
    cases['output'] = isolated("import os\nwhile True: os.write(1, b'x'*8192)", synthetic=True)
    cases['file_bound'] = isolated("import os, json\ntry:\n open('/output/large','wb').write(b'x'*2097152)\nexcept OSError:\n pass\nsize=os.path.getsize('/output/large'); print(json.dumps({'size':size})); assert size<=1048576", synthetic=True)
    cases['pids'] = isolated("import subprocess,json\np=[]\ntry:\n for i in range(40): p.append(subprocess.Popen(['sleep','10']))\nexcept OSError:\n print(json.dumps({'spawned':len(p)}))\n assert len(p)<32\nelse:\n raise AssertionError('PID bound bypassed')\nfinally:\n for child in p: child.terminate()", synthetic=True)
    concurrent_source = "import pathlib,time,json\np=pathlib.Path('/output/owner'); assert not p.exists(); p.write_text('TOKEN'); time.sleep(1); assert p.read_text()=='TOKEN'; print(json.dumps({'owner':'TOKEN'}))"
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(isolated, concurrent_source.replace('TOKEN', value), True) for value in ('first', 'second')]
        for n, future in enumerate(futures):
            cases['concurrent_' + str(n)] = future.result()
    passed = (cases['access']['exit_code'] == 0 and cases['memory']['state']['OOMKilled']
              and cases['wall']['reason'] == 'wall_limit' and cases['output']['reason'] == 'output_limit'
              and all(cases[k]['exit_code'] == 0 for k in ('file_bound', 'pids', 'concurrent_0', 'concurrent_1')))
    evidence = {'passed': passed, 'fingerprint': before, 'cases': cases,
                'measured_at': time.time(), 'candidate_executions': 0}
    if fingerprint() != before:
        evidence['passed'] = False
    save(attestation_path, evidence)
    print(json.dumps({'passed': evidence['passed'], 'cases': {k: {'exit': v['exit_code'], 'reason': v['reason'], 'seconds': v['seconds']} for k, v in cases.items()}}))
    if not evidence['passed']:
        raise RuntimeError('Containment failed; candidate execution remains disabled')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['verify-isolation'])
    parser.parse_args()
    local_paths.require(ROOT)
    verify_isolation()


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, subprocess.SubprocessError, ValueError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
