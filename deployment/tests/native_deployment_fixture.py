"""Disposable reduced modeling service with no published host endpoint (test fixtures only).

The caller names a folder below its test scope, the container name and its labels first
(integration/tests/native_origin_fixture.py); there is no default location, name or label.
"""
from pathlib import Path
import secrets
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import modeling_runtime as runtime

ROOT = None
NAME = None
LABELS = ()


def setup(image):
    if ROOT is None or NAME is None or not LABELS:
        raise ValueError('Scoped fixture root, container name and labels required')
    if runtime.inspect(NAME) is not None or ROOT.exists():
        raise ValueError('Refuse existing fixture; inspect and preserve it explicitly')
    ROOT.mkdir(mode=0o700, parents=True)
    for name in ('modeling', 'credentials'):
        (ROOT / name).mkdir(mode=0o700)
    (ROOT / 'modeling').chmod(0o777)
    for name in ('model.key', 'rails.key'):
        file = ROOT / 'credentials' / name
        file.write_text(secrets.token_hex(64)); file.chmod(0o444)
    labels = [argument for label in LABELS for argument in ('--label', label)]
    runtime.run('docker', 'run', '-d', '--name', NAME, *labels,
        '--network', 'none', '--user', '10001:10001', '--read-only',
        '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
        '--memory', '768m', '--pids-limit', '128', '--cpus', '1',
        '--tmpfs', '/tmp:rw,noexec,nosuid,size=192m,mode=1777',
        '--tmpfs', '/native/tmp:rw,noexec,nosuid,size=32m,uid=10001,gid=10001',
        '-v', str(ROOT / 'modeling') + ':/store',
        '-v', str(ROOT / 'credentials/model.key') + ':/run/model.key:ro',
        '-v', str(ROOT / 'credentials/rails.key') + ':/run/rails.key:ro', image)
    for _ in range(150):
        result = subprocess.run(['docker', 'exec', NAME, 'ruby', '-rsocket', '-e',
            "TCPSocket.new('127.0.0.1',3000).close"], capture_output=True)
        if result.returncode == 0:
            return {'container': NAME, 'root': str(ROOT), 'image': image}
        time.sleep(.2)
    raise RuntimeError('Fixture did not become ready; preserve logs for diagnosis')
