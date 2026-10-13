"""Test-only native instrumentation. No candidate imports on the host.

Runs only inside a test scope: ROOT is a folder below the scope (set by the caller) and every
image and container this module creates carries the scope label
``org.hyprn-mvp.test-scope=<scope uuid>``; containers are named
``hyprn-mvp-test-<scope8>-origin-<mode>`` and removed when their service ends.
"""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import subprocess
import time

ROOT_PATH = Path(__file__).resolve().parents[2]
# The reviewed modeling producer image (deployment/pins.json).
PRODUCER = json.loads((ROOT_PATH / 'deployment/pins.json').read_text())['modeling_producer']['image']
# Set by the caller to a folder below its test scope; there is no default location.
ROOT = None
MARKER = 'native_template_origin_12_3_8b40bcd8'


def scope():
    """The test scope that holds ROOT; every effect of this module stays inside it."""
    import scoped_fixture as guard
    if ROOT is None:
        raise ValueError('Native origin fixtures need ROOT below an isolated test scope')
    return guard.scope_at(ROOT)


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def build(mode):
    import scoped_fixture as guard
    current = scope()
    directory = ROOT / ('build-' + mode)
    directory.mkdir(parents=True, exist_ok=False)
    if mode == 'marker':
        script = """p='/native/app/lib/whats_opt/templates/openmdao_analysis_base.py.erb'
s=File.binread(p);needle='    def initialize(self):'
raise 'unexpected template' unless s.scan(needle).size==1
File.binwrite(p,s.sub(needle,"    def native_origin_12_3(self):\\n        return 'MARKER'\\n\\n"+needle))
""".replace('MARKER', MARKER)
    else:
        assert mode == 'disabled'
        script = """p='/native/app/lib/whats_opt/openmdao_generator.rb'
s=File.binread(p);needle='    def _generate_code(gendir, options = {})'
raise 'unexpected generator' unless s.scan(needle).size==1
File.binwrite(p,s.sub(needle,needle+"\\n      raise 'native_disabled_12_3_8b40bcd8'"))
"""
    (directory/'instrument.rb').write_text(script)
    # COPY keeps the context mode, and the service user reads its provenance support files:
    # an explicit mode, never the builder's umask.
    (directory/'instrument.rb').chmod(0o644)
    assert run('docker','image','inspect',PRODUCER,'--format','{{.Id}}') == PRODUCER
    return guard.build_derived_image(
        current, PRODUCER, directory, 'origin',
        'USER root\nCOPY instrument.rb /native/provenance-inputs/support/origin-instrument.rb\n'
        'RUN ruby /native/provenance-inputs/support/origin-instrument.rb\n'
        f'LABEL org.hyprn-mvp.origin-proof="{mode}"\nUSER 10001:10001\n', evidence=directory/'build.json')


@contextmanager
def service(image, mode, monkeypatch):
    from deployment.tests import native_deployment_fixture as fixture
    from deployment.tests import model_client
    import scoped_fixture as guard
    current = scope()
    root = ROOT / mode
    # Scoped names: hyprn-mvp-test-<scope8>-<role>.
    name = guard.SCOPE_PREFIX + current.run_uuid[:8] + '-origin-' + mode
    labels = ('org.hyprn-mvp.test-scope=' + current.run_uuid, 'org.hyprn-mvp.origin-proof=' + mode)
    with monkeypatch.context() as patch:
        patch.setattr(fixture, 'ROOT', root)
        patch.setattr(fixture, 'NAME', name)
        patch.setattr(fixture, 'LABELS', labels)
        fixture.setup(image)
    identity = json.loads(run('docker','inspect',name))[0]
    assert identity['Image'] == image
    assert identity['HostConfig']['NetworkMode'] == 'none'
    assert identity['Config']['Labels']['org.hyprn-mvp.origin-proof'] == mode
    assert identity['Config']['Labels']['org.hyprn-mvp.test-scope'] == current.run_uuid
    (ROOT/(mode+'-container.json')).write_text(json.dumps(identity, indent=2))
    try:
        with monkeypatch.context() as patch:
            patch.setattr(model_client, 'ROOT', root)
            patch.setattr(model_client, 'CONTAINER', name)
            yield name
    finally:
        current = json.loads(run('docker','inspect',name))[0]
        assert current['Id'] == identity['Id'] and current['Image'] == image
        run('docker','stop',name)
        # The container belongs to this scope only; it never outlives its service.
        run('docker','rm',current['Id'])


@contextmanager
def attested_variant(producer, *, root=None):
    """Attest only an explicitly scoped temporary image; never touch live identity."""
    from uuid import uuid4
    from hyprn_mvp_integration import launcher
    if root is None:
        raise ValueError('Explicit isolated runtime root required')
    root = launcher.fixture_runtime_root(root)  # Before operational reads/writes.
    launcher.require_attestation(root=root)
    runtime_path = root/'runtime.json'
    attestation_path = root/'evidence/containment.json'
    original_runtime = runtime_path.read_bytes()
    original_attestation = attestation_path.read_bytes()
    current = launcher.identity(root=root)
    import scoped_fixture as guard
    test_scope = guard.scope_at(root)
    if test_scope.root != root:
        raise ValueError('Explicit isolated runtime root of a test scope required')
    directory = root/'artifacts'/('origin-worker-'+uuid4().hex)
    directory.mkdir(exist_ok=False)
    assert run('docker','image','inspect',current['worker_image'],'--format','{{.Id}}') == current['worker_image']
    current['worker_image'] = guard.build_derived_image(
        test_scope, current['worker_image'], directory, 'worker', f'LABEL org.hyprn-mvp.origin-proof="{MARKER}"\n',
        evidence=directory/'build.json')
    current['origin_proof_producer'] = producer
    current['origin_proof_marker'] = MARKER
    (directory/'original-runtime.json').write_bytes(original_runtime)
    (directory/'original-containment.json').write_bytes(original_attestation)
    try:
        runtime_path.write_text(json.dumps(current,indent=2)+'\n')
        evidence = launcher.attest(root=root)
        assert evidence['passed'] and evidence['candidate_executions'] == 0
        (directory/'instrumented-runtime.json').write_bytes(runtime_path.read_bytes())
        (directory/'instrumented-containment.json').write_bytes(attestation_path.read_bytes())
        yield evidence
    finally:
        runtime_path.write_bytes(original_runtime)
        attestation_path.write_bytes(original_attestation)
        launcher.require_attestation(root=root)


def restart(name, image):
    identity = json.loads(run('docker','inspect',name))[0]
    assert identity['Image'] == image
    assert identity['Config']['Labels']['org.hyprn-mvp.origin-proof'] == 'marker'
    run('docker','restart',name)
    for _ in range(150):
        result = subprocess.run(['docker','exec',name,'ruby','-rsocket','-e',
            "TCPSocket.new('127.0.0.1',3000).close"],capture_output=True)
        if result.returncode == 0:
            return
        time.sleep(.2)
    raise RuntimeError('Instrumented model restart failed')
