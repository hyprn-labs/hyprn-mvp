"""Release source verification through a real scoped application-image container."""

import sys
from pathlib import Path

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.append(str(Path(__file__).resolve().parent))
import live_fence  # noqa: E402

live_runtime_fence = live_fence.pytest_fixture('baseline')

import json
import shutil
import subprocess
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import application_runtime as app
import release
import modeling_runtime as modeling
import scoped_fixture as guard
import checks
from test_deployment_hardening import binding_for

REPO = Path(__file__).resolve().parents[2]


def test_actual_container_bytes_match_then_refuse_tamper(tmp_path, monkeypatch):
    scope = guard.validate_scope(checks.PROJECTION_SCOPE)
    name = guard.SCOPE_PREFIX + scope.run_uuid[:8] + '-release'
    owner = name
    result = release.snapshot(REPO, tmp_path / 'releases')
    path = Path(result['path'])
    source = path / 'source'
    monkeypatch.setattr(app, 'REPO', source)
    monkeypatch.setattr(app, 'ROOT', tmp_path / 'application')
    app.ROOT.mkdir()
    monkeypatch.setattr(app, 'NAME', name)
    monkeypatch.setattr(app, 'OWNER', owner)
    monkeypatch.setattr(app, 'UI_DIST', tmp_path / 'ui')
    evidence = scope.root / 'evidence/release-container'
    evidence.mkdir()
    build = app.build_image(evidence)
    app.retain_image_ui(build['image'])
    digest = release.seal(
        path,
        result['manifest_sha256'],
        images=dict(
            application=build['image'], modeling='sha256:' + 'd' * 64, worker='sha256:' + 'e' * 64
        ),
        ui_build=app.UI_DIST,
        application_build=build,
    )
    manifest, _ = release.verify(path, expected_sha256=digest)
    binding = binding_for(path, manifest, digest)
    saved = release.canonical(dict(image=build['image'], build=build, source_hashes=app.hashes()))
    (app.ROOT / 'identity.json').write_bytes(saved)
    mutable = tmp_path / 'container-application'
    shutil.copytree(source / 'application', mutable)
    modeling.readable_context(mutable)
    command = [
        'docker',
        'run',
        '-d',
        '--name',
        name,
        '--network=none',
        '--read-only',
        '--cap-drop=ALL',
        '--security-opt=no-new-privileges:true',
        '--label',
        'org.hyprn-mvp.test-scope=' + scope.run_uuid,
        '--label',
        modeling.LABEL + '=' + owner,
        '--mount',
        'type=bind,src=' + str(mutable) + ',dst=/app/application,readonly',
        build['image'],
        'python',
        '-I',
        '-B',
        '-c',
        'import time;time.sleep(600)',
    ]
    subprocess.run(command, check=True, capture_output=True)
    records = []
    try:
        records.append(dict(case='original', result=app.require_release_inventory(binding)))
        target = mutable / 'src/hyprn_mvp_app/__init__.py'
        original = target.read_bytes()
        target.write_bytes(original + b'\n# changed runtime bytes\n')
        with pytest.raises(ValueError, match='inventory differs'):
            app.require_release_inventory(binding)
        records.append(dict(case='changed', refused=True))
        target.write_bytes(original)
        target.unlink()
        with pytest.raises(ValueError, match='inventory differs'):
            app.require_release_inventory(binding)
        records.append(dict(case='missing', refused=True))
        target.write_bytes(original)
        target.chmod(0o644)
        extra = mutable / 'src/hyprn_mvp_app/extra.py'
        extra.write_text('# extra runtime file\n')
        extra.chmod(0o644)
        with pytest.raises(ValueError, match='inventory differs'):
            app.require_release_inventory(binding)
        records.append(dict(case='extra', refused=True))
        extra.unlink()
        app.require_release_inventory(binding)
        assert (app.ROOT / 'identity.json').read_bytes() == saved
        (evidence / 'result.json').write_bytes(
            release.canonical(
                dict(
                    source_commit=manifest['source_commit'],
                    manifest_sha256=digest,
                    image=build['image'],
                    cases=records,
                    unchanged_identity_sha256=release.sha256(saved),
                )
            )
        )
    finally:
        info = app.inspect()
        if info:
            assert info['Config']['Labels']['org.hyprn-mvp.test-scope'] == scope.run_uuid
            (evidence / 'container.json').write_bytes(release.canonical(info))
            subprocess.run(['docker', 'rm', '-f', name], check=True, capture_output=True)
