"""An owned modeling deployment set up by deployment/modeling_runtime.py inside one test scope.

The deployment is the installation's: the reviewed recipe settings and identity checks of
modeling_runtime, with the scope's own root, container, network and ownership label
(modeling_runtime.scoped_deployment). Its image is the reviewed producer image pinned in
deployment/pins.json, accepted only when it was built from the current reviewed sources
(modeling_runtime.reviewed_image). The deployment is removed when the test session ends; only
resources that carry this scope's label are removed. Test modules import ``owned_modeling``.
"""
import json
from pathlib import Path
import sys
import time

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'deployment'))
import modeling_runtime as runtime  # noqa: E402
import model_client  # noqa: E402
import scoped_fixture as guard  # noqa: E402


def current_scope():
    from checks import PROJECTION_SCOPE
    return guard.validate_scope(PROJECTION_SCOPE)


def ready(container, attempts=300):
    import subprocess
    for _ in range(attempts):
        probe = subprocess.run(['docker', 'exec', container, 'ruby', '-rsocket', '-e',
                                "TCPSocket.new('127.0.0.1',3000).close"], capture_output=True)
        if probe.returncode == 0:
            return
        time.sleep(.2)
    raise RuntimeError('Owned modeling deployment did not become ready; its evidence is retained in the scope')


def remove(deployment):
    """Remove the scope's container and network; anything without the scope label is refused."""
    for name, kind in ((deployment.container, 'container'), (deployment.network, 'network')):
        info = runtime.inspect(name, kind)
        if info is None:
            continue
        labels = info.get('Config', {}).get('Labels', {}) if kind == 'container' else info.get('Labels', {})
        if labels.get(deployment.label) != deployment.owner:
            raise ValueError('Refusing to remove a resource this scope does not own: ' + name)
        runtime.run('docker', *(('rm', '-f') if kind == 'container' else ('network', 'rm')), name)


@pytest.fixture(scope='session')
def owned_modeling():
    scope = current_scope()
    root = guard.scoped_path(scope, 'artifacts/modeling-deployment')
    deployment = runtime.scoped_deployment(root, scope.run_uuid)
    previous = model_client.ROOT, model_client.CONTAINER
    try:
        image = json.loads((REPO / 'deployment/pins.json').read_text())['modeling_producer']['image']
        result = runtime.setup(root, deployment=deployment, image=image)
        ready(deployment.container)
        model_client.ROOT, model_client.CONTAINER = root, deployment.container
        yield root, deployment, result
    finally:
        model_client.ROOT, model_client.CONTAINER = previous
        remove(deployment)
