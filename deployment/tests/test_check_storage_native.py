"""Real Docker worker reuse retains scope ownership and attestation checks."""
import live_fence
live_runtime_fence = live_fence.pytest_fixture('baseline')
import json
import subprocess

import execution_runtime as runtime
import scoped_fixture as fixture
from hyprn_mvp_integration import launcher


def test_distinct_scopes_reuse_exact_worker_and_attest_independently():
    first = fixture.allocate_scope(fixture.new_scope())
    second = fixture.allocate_scope(fixture.new_scope())
    one = runtime.build_worker(root=first.root)
    two = runtime.build_worker(root=second.root)
    assert one['worker_image'] == two['worker_image']
    assert one['owner'] != two['owner'] and one['root'] != two['root']
    assert 'Reused exact worker' in (second.root / 'evidence/worker-build.log').read_text()
    image = json.loads(runtime.run('docker', 'image', 'inspect', two['worker_image']))[0]
    assert 'org.hyprn-mvp.test-scope' not in image['Config']['Labels']
    for scope in (first, second):
        result = launcher.attest(root=scope.root)
        assert result['passed'], result
    # No third image is created on a repeated request.
    before = set(runtime.run('docker', 'image', 'ls', '-aq', '--no-trunc').split())
    assert runtime.build_worker(root=second.root)['worker_image'] == one['worker_image']
    assert set(runtime.run('docker', 'image', 'ls', '-aq', '--no-trunc').split()) == before


def test_derived_images_reuse_inputs_and_scoped_container_cleanup_is_exact():
    import check_storage
    from uuid import uuid4
    first = fixture.allocate_scope(fixture.new_scope())
    second = fixture.allocate_scope(fixture.new_scope())
    base = runtime.build_worker(root=first.root)['worker_image']
    images = []
    for scope in (first, second):
        context = scope.root / 'tmp/context'
        context.mkdir()
        (context / 'value.txt').write_text('same reviewed bytes')
        images.append(fixture.build_derived_image(
            scope, base, context, 'storage-test', 'COPY value.txt /value.txt\n',
            evidence=scope.root / 'evidence/derived.json'))
    assert images[0] == images[1]
    assert json.loads((second.root / 'evidence/derived.json').read_text())['reused']
    (second.root / 'tmp/context/value.txt').write_text('changed reviewed bytes')
    changed = fixture.build_derived_image(second, base, second.root / 'tmp/context',
                                          'storage-test', 'COPY value.txt /value.txt\n')
    assert changed != images[0]
    (second.root / 'tmp/context/value.txt').chmod(0o400)
    changed_mode = fixture.build_derived_image(second, base, second.root / 'tmp/context',
                                               'storage-test', 'COPY value.txt /value.txt\n')
    assert changed_mode != changed
    # Exact ownership selectors must preserve an unrelated container, even on the same image.
    labels = ['org.hyprn-mvp.test-scope=' + first.run_uuid,
              'org.hyprn-mvp.owner=' + first.root.name,
              'org.hyprn-mvp.test-scope=' + str(uuid4())]
    disposable = fixture.build_derived_image(first, base, first.root / 'tmp/context',
                                               'storage-disposable', 'COPY value.txt /value.txt\n',
                                               disposable=True)
    runtime.run('docker', 'tag', disposable, 'hyprn-mvp-storage-disposable:alias-' + first.run_uuid)
    containers = []
    try:
        for label in labels:
            containers.append(runtime.run('docker', 'create', '--network=none', '--read-only',
                                          '--cap-drop=ALL', '--security-opt=no-new-privileges',
                                          '--label', label, base, 'python', '-c', 'pass'))
        check_storage.docker_resources(first.run_uuid)
        current = set(runtime.run('docker', 'ps', '-aq', '--no-trunc').split())
        assert not set(containers[:2]) & current
        assert containers[2] in current
        assert subprocess.run(['docker', 'image', 'inspect', disposable], capture_output=True).returncode != 0
    finally:
        for identifier in containers:
            subprocess.run(['docker', 'rm', '-f', identifier], capture_output=True)
