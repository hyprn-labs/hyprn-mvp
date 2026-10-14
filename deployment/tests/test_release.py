"""Committed release installation boundaries, exercised in disposable repositories."""

import json
import os
from pathlib import Path
import subprocess
import sys
import types

import pytest
import live_fence  # noqa: E402

live_runtime_fence = live_fence.pytest_fixture('unit')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import release
import application_runtime as app
import dispatch_runtime as dispatch
import native_environment as native
from test_deployment_hardening import binding_for, make_release, with_ui_build


def git(root, *args):
    return subprocess.run(
        ['git', '-C', str(root), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def checkout(tmp_path):
    root = tmp_path / 'checkout'
    root.mkdir()
    git(root, 'init', '-q')
    git(root, 'config', 'user.name', 'Fixture')
    git(root, 'config', 'user.email', 'fixture@example.invalid')
    for name, text in {
        'application/src/example.py': 'committed = 1\n',
        'deployment/manager.py': '#!/bin/sh\nexit 0\n',
        'ui/index.html': '<html>committed</html>\n',
        'outside.txt': 'excluded\n',
    }.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    for name in release.PRODUCT_PATHS:
        folder = root / name
        folder.mkdir(exist_ok=True)
        (folder / 'tracked.txt').write_text('product bytes\n')
    (root / 'deployment/manager.py').chmod(0o755)
    git(root, 'add', *release.PRODUCT_PATHS, 'outside.txt')
    git(root, 'commit', '-qm', 'fixture')
    return root


def test_snapshot_excludes_dirty_and_untracked_bytes_with_warning(checkout, tmp_path):
    (checkout / 'application/src/example.py').write_text('dirty = 2\n')
    (checkout / 'application/untracked.py').write_text('untracked\n')
    warnings = []
    result = release.snapshot(checkout, tmp_path / 'releases', warn=warnings.append)
    path = Path(result['path'])
    manifest, digest = release.verify(path, expected_sha256=result['manifest_sha256'])
    assert (path / 'source/application/src/example.py').read_text() == 'committed = 1\n'
    assert not (path / 'source/application/untracked.py').exists()
    assert not (path / 'source/outside.txt').exists()
    assert (path / 'source/deployment/manager.py').stat().st_mode & 0o100
    assert warnings and 'Uncommitted changes excluded' in warnings[0]
    assert 'untracked.py' in warnings[0] and 'example.py' in warnings[0]
    assert manifest['source_commit'] == git(checkout, 'rev-parse', 'HEAD')
    assert digest == result['manifest_sha256']
    assert manifest['release_id'].startswith('local-' + manifest['source_commit'][:12])


def test_snapshot_refuses_changed_head_and_names_installed_commit(checkout, tmp_path):
    result = release.snapshot(checkout, tmp_path / 'releases')
    manifest, _ = release.verify(Path(result['path']))
    (checkout / 'outside.txt').write_text('next commit\n')
    git(checkout, 'add', 'outside.txt')
    git(checkout, 'commit', '-qm', 'changed')
    with pytest.raises(
        release.ReleaseBindingError, match='source_changed.*' + manifest['source_commit']
    ):
        release.require_checkout(manifest)


def test_snapshot_tamper_is_refused_before_binding(checkout, tmp_path):
    result = release.snapshot(checkout, tmp_path / 'releases')
    path = Path(result['path'])
    (path / 'source/application/src/example.py').write_text('tampered\n')
    with pytest.raises(release.ReleaseError, match='differs from manifest'):
        release.bind(path / 'source/deployment/manager.py', effectful=False, project_imports=True)


@pytest.mark.parametrize('entry', ['source', 'manifest.json', 'manifest.sha256', 'build/ui-dist'])
def test_release_refuses_root_and_record_symlinks(tmp_path, entry):
    path, manifest, digest = make_release(tmp_path / 'releases')
    manifest, digest = with_ui_build(path, manifest)
    original = path / entry
    retained = tmp_path / ('retained-' + entry.replace('/', '-'))
    original.rename(retained)
    original.symlink_to(retained, target_is_directory=retained.is_dir())
    with pytest.raises(release.ReleaseError, match='[Ss]ymlink|[Uu]nsafe|regular'):
        release.verify(path, expected_sha256=digest)


def test_committed_archive_refuses_symlinks(checkout, tmp_path):
    (checkout / 'application/link').symlink_to('src/example.py')
    git(checkout, 'add', 'application/link')
    git(checkout, 'commit', '-qm', 'symlink')
    with pytest.raises(release.ReleaseError, match='Non-regular archive'):
        release.snapshot(checkout, tmp_path / 'releases')
    assert list((tmp_path / 'releases').iterdir()) == []


def test_required_review_is_explicit_for_checkout_snapshot(checkout, tmp_path):
    result = release.snapshot(checkout, tmp_path / 'releases', require_review=True)
    path = Path(result['path'])
    manifest, digest = release.verify(path)
    with pytest.raises(release.ReleaseBindingError, match='record-review'):
        release.require_review(path, manifest, digest, reviews_root=tmp_path / 'reviews')


def test_foreign_release_wrapper_is_refused(tmp_path):
    first, m1, d1 = make_release(tmp_path / 'one')
    second, m2, d2 = make_release(tmp_path / 'two')
    root = tmp_path / 'execution'
    root.mkdir()
    native.write_launch_worker(root, binding_for(first, m1, d1))
    with pytest.raises(ValueError, match='not bound'):
        native.require_launch_worker(root, binding_for(second, m2, d2))


def test_loaded_checkout_module_is_refused(tmp_path, monkeypatch):
    source = tmp_path / 'release/source'
    source.mkdir(parents=True)
    foreign = tmp_path / 'checkout/application/src/hyprn_mvp_app/example.py'
    foreign.parent.mkdir(parents=True)
    foreign.write_text('x = 1\n')
    monkeypatch.setitem(
        sys.modules, 'hyprn_mvp_app.example', types.SimpleNamespace(__file__=str(foreign))
    )
    with pytest.raises(release.ReleaseBindingError, match='outside the selected release'):
        release._check_loaded((source,), {'hyprn_mvp_app'}, source / 'deployment/manager.py')


@pytest.mark.parametrize('mutation', ['changed', 'missing', 'extra'])
def test_container_bytes_override_unchanged_saved_claims(tmp_path, monkeypatch, mutation):
    path, manifest, digest = make_release(
        tmp_path / 'releases', {'application/src/example.py': b'original\n'}
    )
    manifest, digest = with_ui_build(path, manifest)
    binding = binding_for(path, manifest, digest)
    identity_root = tmp_path / 'application'
    identity_root.mkdir()
    expected = {f['path']: f['sha256'] for f in manifest['tree']['files']}
    expected.update({'ui-dist/' + f['path']: f['sha256'] for f in manifest['build']['ui']['files']})
    identity = dict(image='sha256:' + 'a' * 64, source_hashes=expected)
    saved = json.dumps(identity).encode()
    (identity_root / 'identity.json').write_bytes(saved)
    monkeypatch.setattr(app, 'ROOT', identity_root)
    monkeypatch.setattr(app, 'inspect', lambda: dict(Image=identity['image']))
    monkeypatch.setattr(app, 'guard', lambda info: None)
    monkeypatch.setattr(app, 'container_inventory', lambda: expected)
    assert app.require_release_inventory(binding)['files'] == len(expected)
    actual = dict(expected)
    if mutation == 'changed':
        actual['application/src/example.py'] = '0' * 64
    elif mutation == 'missing':
        del actual['application/src/example.py']
    else:
        actual['application/src/extra.py'] = '0' * 64
    monkeypatch.setattr(app, 'container_inventory', lambda: actual)
    with pytest.raises(ValueError, match='inventory differs'):
        app.require_release_inventory(binding)
    assert (identity_root / 'identity.json').read_bytes() == saved


def test_child_binding_requires_all_module_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr(dispatch, 'ROOT', tmp_path)
    folder = tmp_path / 'evidence/release-binding'
    folder.mkdir(parents=True)
    token = 'a' * 32
    record = dict(pid=123, release_id='r', manifest_sha256='d', source_root='s', modules={})
    (folder / ('executor-123-' + token + '.json')).write_text(json.dumps(record))
    with pytest.raises(RuntimeError, match='module evidence incomplete'):
        dispatch.verify_child_binding(123, record, token)


def buildable_snapshot(checkout, tmp_path):
    for name, raw in {
        'deployment/locks/tools.json': '{}\n',
        'deployment/images/install_python.py': '# tool\n',
        'deployment/application.Dockerfile': 'FROM pinned\n',
        'deployment/pins.json': json.dumps(
            dict(base_image='python@sha256:' + 'a' * 64, node_base_image='node@sha256:' + 'b' * 64)
        ),
    }.items():
        path = checkout / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(raw)
    git(checkout, 'add', 'deployment')
    git(checkout, 'commit', '-qm', 'build inputs')
    result = release.snapshot(checkout, tmp_path / 'releases')
    path = Path(result['path'])
    manifest, digest = release.verify(path)
    files = {f['path']: f['sha256'] for f in manifest['tree']['files']}
    inputs = dict(
        files={
            name: value
            for name, value in files.items()
            if name.startswith(('application/', 'contracts/', 'ui/'))
        },
        bases=json.loads((checkout / 'deployment/pins.json').read_bytes()),
    )
    for name in ('deployment/locks/tools.json', 'deployment/images/install_python.py'):
        inputs['files'][name] = files[name]
    inputs['files']['Dockerfile'] = files['deployment/application.Dockerfile']
    image = 'sha256:' + 'c' * 64
    build = dict(
        image=image,
        inputs=inputs,
        inputs_sha256=release.sha256(json.dumps(inputs, sort_keys=True).encode()),
    )
    ui = tmp_path / 'ui-build'
    ui.mkdir()
    (ui / 'index.html').write_text('built from committed source\n')
    images = dict(application=image, modeling='sha256:' + 'd' * 64, worker='sha256:' + 'e' * 64)
    return path, digest, build, images, ui


@pytest.mark.parametrize('mutation', ['missing', 'base'])
def test_seal_refuses_incomplete_or_foreign_build_inputs(checkout, tmp_path, mutation):
    path, digest, build, images, ui = buildable_snapshot(checkout, tmp_path)
    if mutation == 'missing':
        build['inputs']['files'].pop('application/src/example.py')
    else:
        build['inputs']['bases']['base_image'] = 'foreign'
    build['inputs_sha256'] = release.sha256(json.dumps(build['inputs'], sort_keys=True).encode())
    with pytest.raises(release.ReleaseError, match='build input inventory differs'):
        release.seal(path, digest, images=images, ui_build=ui, application_build=build)
    assert release.verify(path)[1] == digest
    assert not (path.parent / 'active.json').exists()


def test_sealed_snapshot_activation_and_changed_head_refusal(checkout, tmp_path, monkeypatch):
    path, digest, build, images, ui = buildable_snapshot(checkout, tmp_path)
    sealed = release.seal(path, digest, images=images, ui_build=ui, application_build=build)
    replacements = []
    replace = os.replace

    def record(source, target):
        replacements.append(Path(target))
        return replace(source, target)

    monkeypatch.setattr(os, 'replace', record)
    pointer = release.activate(path, sealed)
    assert replacements == [path.parent / 'active.json']
    assert (path.parent / 'active.json').stat().st_mode & 0o777 == 0o600
    assert pointer['manifest_sha256'] == sealed
    assert release.active(path.parent, checkout=checkout) == path
    with pytest.raises(release.ReleaseError, match='unsealed'):
        release.seal(path, sealed, images=images, ui_build=ui, application_build=build)
    git(checkout, 'commit', '--allow-empty', '-qm', 'next head')
    with pytest.raises(release.ReleaseBindingError, match='source_changed'):
        release.active(path.parent, checkout=checkout)


@pytest.mark.parametrize('package', ['hyprn_mvp_app', 'hyprn_mvp_local'])
def test_public_bind_refuses_module_already_imported_from_checkout(checkout, tmp_path, package):
    repo = Path(__file__).resolve().parents[2]
    for name in ('release.py', 'local_paths.py'):
        (checkout / 'deployment' / name).write_bytes((repo / 'deployment' / name).read_bytes())
    git(checkout, 'add', 'deployment')
    git(checkout, 'commit', '-qm', 'binding bootstrap')
    result = release.snapshot(checkout, tmp_path / 'releases')
    source = Path(result['path']) / 'source'
    code = """
import sys,types
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import release
sys.modules[sys.argv[4] + '.bad']=types.SimpleNamespace(__file__=sys.argv[3])
try:
    release.bind(sys.argv[2],effectful=False,project_imports=True)
except release.ReleaseBindingError as error:
    print(str(error))
    raise SystemExit(2)
raise SystemExit('foreign import was accepted')
"""
    result = subprocess.run(
        [
            sys.executable,
            '-I',
            '-B',
            '-c',
            code,
            str(source / 'deployment'),
            str(source / 'deployment/manager.py'),
            str(checkout / 'application/src/example.py'),
            package,
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2, result.stderr
    assert package + '.bad already imported outside' in result.stdout


@pytest.mark.parametrize('failure', ['model', 'worker', 'stale'])
def test_start_requires_current_attestation_and_exact_runtime_images(monkeypatch, failure):
    import execution_runtime

    expected = dict(modeling='model-image', worker='worker-image')
    monkeypatch.setattr(
        app.modeling_runtime,
        'check',
        lambda root: dict(image='foreign' if failure == 'model' else 'model-image'),
    )
    calls = []

    def require_attestation(*, root):
        calls.append(root)
        if failure == 'stale':
            raise RuntimeError('Failed or stale containment attestation')
        return dict(fingerprint=dict(image='foreign' if failure == 'worker' else 'worker-image'))

    monkeypatch.setattr(
        execution_runtime,
        'launcher',
        lambda: types.SimpleNamespace(require_attestation=require_attestation),
    )
    with pytest.raises(RuntimeError, match='differs|stale'):
        dispatch.require_runtime_images(dict(images=expected))
    assert len(calls) == (0 if failure == 'model' else 1)
