"""Verified source acquisition never repairs an invalid cache or publishes partial bytes."""

import sys as _fence_sys
from pathlib import Path as _FencePath

if str(_FencePath(__file__).resolve().parent) not in _fence_sys.path:
    _fence_sys.path.append(str(_FencePath(__file__).resolve().parent))
import live_fence  # noqa: E402

live_runtime_fence = live_fence.pytest_fixture('unit')
import contextlib  # noqa: E402
import hashlib  # noqa: E402
import io  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
from pathlib import Path  # noqa: E402
from unittest.mock import Mock  # noqa: E402

import pytest  # noqa: E402

sys = _fence_sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import modeling_runtime as runtime  # noqa: E402


@pytest.fixture
def archive(tmp_path, monkeypatch):
    raw = b'verified source archive'
    pin = dict(runtime.UPSTREAM, size=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    monkeypatch.setattr(runtime, 'UPSTREAM', pin)
    monkeypatch.setattr(runtime, 'ARCHIVE_SHA256', pin['sha256'])
    cache = tmp_path / 'cache'
    cache.mkdir(mode=0o700)
    return raw, pin, cache


def cached(archive, *, mode=0o400, content=None):
    raw, pin, cache = archive
    target = cache / pin['sha256'] / 'WhatsOpt.tar.gz'
    target.parent.mkdir(mode=0o700)
    target.write_bytes(raw if content is None else content)
    target.chmod(mode)
    return target


def test_verified_download_is_private_read_only_and_reused_without_network(archive):
    raw, pin, cache = archive
    opener = Mock(return_value=io.BytesIO(raw))
    path = runtime.acquire_upstream(cache, opener=opener)
    opener.assert_called_once_with(pin['url'], timeout=60)
    assert path.read_bytes() == raw
    assert path.stat().st_mode & 0o777 == 0o400
    assert runtime.acquire_upstream(cache, opener=Mock(side_effect=AssertionError)) == path
    assert list(path.parent.iterdir()) == [path]


@pytest.mark.parametrize('content', [b'', b'x' * 23, b'x' * 24, b'x' * 22])
def test_hash_and_size_mismatch_never_publish_an_archive(archive, content):
    _, pin, cache = archive
    with pytest.raises(ValueError, match='identity mismatch'):
        runtime.acquire_upstream(cache, opener=Mock(return_value=io.BytesIO(content)))
    assert list((cache / pin['sha256']).iterdir()) == []


def test_network_failure_leaves_no_partial_archive(archive):
    _, pin, cache = archive
    with pytest.raises(OSError, match='offline'):
        runtime.acquire_upstream(cache, opener=Mock(side_effect=OSError('offline')))
    assert list((cache / pin['sha256']).iterdir()) == []


@pytest.mark.parametrize('mode', [0o440, 0o404, 0o600, 0o644])
def test_shared_or_writable_cached_archive_is_refused_without_fetch(archive, mode):
    path = cached(archive, mode=mode)
    with pytest.raises(ValueError, match='owner-private read-only'):
        runtime.acquire_upstream(archive[2], opener=Mock(side_effect=AssertionError))
    assert path.stat().st_mode & 0o777 == mode


def test_corrupt_cached_archive_is_never_replaced(archive):
    path = cached(archive, content=b'corrupt')
    with pytest.raises(ValueError, match='identity mismatch'):
        runtime.acquire_upstream(archive[2], opener=Mock(side_effect=AssertionError))
    assert path.read_bytes() == b'corrupt'


def test_symlinked_archive_is_refused_without_fetch(archive):
    path = cached(archive)
    saved = path.with_name('original')
    path.rename(saved)
    path.symlink_to(saved)
    with pytest.raises(ValueError, match='owner-private read-only'):
        runtime.acquire_upstream(archive[2], opener=Mock(side_effect=AssertionError))


@pytest.mark.parametrize('level', ['cache', 'digest'])
def test_symlinked_cache_folder_is_refused(archive, level):
    path = cached(archive)
    folder = archive[2] if level == 'cache' else path.parent
    original = folder.with_name(folder.name + '-original')
    folder.rename(original)
    folder.symlink_to(original, target_is_directory=True)
    with pytest.raises(ValueError, match='nonsymlink|symlinks'):
        runtime.acquire_upstream(archive[2], opener=Mock(side_effect=AssertionError))


def test_stream_read_failure_leaves_no_partial_archive(archive):
    class Interrupted(io.BytesIO):
        def read(self, size=-1):
            raise OSError('interrupted')

    with pytest.raises(OSError, match='interrupted'):
        runtime.acquire_upstream(archive[2], opener=Mock(return_value=Interrupted()))
    assert list((archive[2] / archive[1]['sha256']).iterdir()) == []


def test_concurrent_acquisition_preserves_and_verifies_winner(archive, monkeypatch):
    raw, _, cache = archive
    link = os.link

    def publish_other(source, target):
        Path(target).write_bytes(raw)
        Path(target).chmod(0o400)
        link(source, target)

    monkeypatch.setattr(runtime.os, 'link', publish_other)
    assert (
        runtime.acquire_upstream(cache, opener=Mock(return_value=io.BytesIO(raw))).read_bytes()
        == raw
    )


def test_source_inputs_bind_archive_gems_recipe_and_bases():
    inputs = runtime.source_build_inputs()
    assert set(inputs['sources']) == {
        'deployment/images/whatsopt-source.Dockerfile',
        'deployment/locks/upstream.json',
        'deployment/locks/whatsopt-gems.json',
    }
    assert all('@sha256:' in inputs[name] for name in ('ruby_image', 'node_image'))
    lock = json.loads((runtime.REPO / 'deployment/locks/whatsopt-gems.json').read_text())
    assert len(lock['gems']) == len({g['filename'] for g in lock['gems']})
    assert all(
        len(g['sha256']) == 64
        and g['checksum_source'].startswith('https://rubygems.org/api/v1/versions/')
        for g in lock['gems']
    )


def test_native_template_postimage_equals_the_reviewed_reference(tmp_path):
    raw = runtime.upstream_archive().getvalue()
    runtime.stage_generation_patch(tmp_path, raw)
    sections = runtime.patch_sections((tmp_path / 'native.patch').read_text())
    template = 'b/app/lib/whats_opt/templates/openmdao_discipline.py.erb'
    selected = [text for _, new, text in sections if new == template]
    assert len(selected) == 1
    lines = selected[0].splitlines(keepends=True)[3:]
    postimage = ''.join(line[1:] for line in lines if line.startswith(('+', ' ')))
    assert hashlib.sha256(postimage.encode()).hexdigest() == (
        'd9c720054302de48dd43116b7dc4cc563d1ca120c5ce278a2708e1b981bfcec7'
    )
    assert all(new != 'b/app/services/modeling_contract.rb' for _, new, _ in sections)


def test_template_staging_refuses_unverified_upstream_bytes(tmp_path):
    with pytest.raises(ValueError, match='identity mismatch'):
        runtime.stage_generation_patch(tmp_path, b'unverified')


def test_source_image_refuses_an_unbound_cached_image(monkeypatch):
    monkeypatch.setattr(runtime, 'inspect', lambda *args: {'Config': {'Labels': {}}})
    with pytest.raises(ValueError, match='input identity mismatch'):
        runtime.source_image()


def test_source_build_refuses_recipe_drift_before_docker(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime.local_paths, 'scratch_root', lambda: tmp_path)
    monkeypatch.setattr(runtime, 'acquire_upstream', lambda: runtime.ARCHIVE)
    monkeypatch.setattr(runtime, 'inspect', lambda *args: None)
    readable = runtime.readable_context

    def change_staged_recipe(context):
        readable(context)
        (context / 'Dockerfile').write_text('changed recipe')

    monkeypatch.setattr(runtime, 'readable_context', change_staged_recipe)
    monkeypatch.setattr(
        runtime.subprocess, 'run', Mock(side_effect=AssertionError('docker called'))
    )
    with pytest.raises(ValueError, match='changed during staging'):
        runtime.source_image(evidence=tmp_path / 'evidence')


def test_model_fields_and_ownership_replay_match_every_reference_file(tmp_path):
    runtime.stage_replayed_sources(tmp_path, runtime.upstream_archive().getvalue())
    assert len(runtime.BASELINE_SOURCES) == 7
    for name, (_, expected) in runtime.BASELINE_SOURCES.items():
        assert hashlib.sha256((tmp_path / 'replay' / name).read_bytes()).hexdigest() == expected


def test_baseline_replay_refuses_changed_reference_identity(tmp_path, monkeypatch):
    changed = dict(runtime.BASELINE_SOURCES)
    name = next(iter(changed))
    changed[name] = (changed[name][0], '0' * 64)
    monkeypatch.setattr(runtime, 'BASELINE_SOURCES', changed)
    with pytest.raises(ValueError, match='differs from the reviewed reference'):
        runtime.stage_replayed_sources(tmp_path, runtime.upstream_archive().getvalue())


def matching_source_info():
    inputs = runtime.source_build_inputs()
    digest = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
    return {
        'Id': 'sha256:' + 'a' * 64,
        'Config': {'Labels': {'org.hyprn-mvp.modeling-source-inputs': digest}},
    }


def test_matching_source_build_is_reused_without_reexport(tmp_path, monkeypatch):
    info = matching_source_info()
    monkeypatch.setattr(runtime, 'inspect', lambda *args: info)
    monkeypatch.setattr(runtime.subprocess, 'run', Mock(side_effect=AssertionError('build called')))
    retained = Mock(return_value='')
    monkeypatch.setattr(runtime, 'run', retained)
    assert runtime.source_image(evidence=tmp_path) == info['Id']
    retained.assert_called_once_with(
        'docker', 'tag', info['Id'], 'hyprn-mvp-modeling-source:built-' + 'a' * 64
    )
    assert json.loads((tmp_path / 'source-build-identity.json').read_text())['image'] == info['Id']


def test_recorded_source_identity_is_checked_without_latest_tag_substitution(monkeypatch):
    info = matching_source_info()
    inspect = Mock(return_value=info)
    monkeypatch.setattr(runtime, 'inspect', inspect)
    assert runtime.source_image(recorded=info['Id']) == info['Id']
    assert all(call.args[0] == info['Id'] for call in inspect.call_args_list)
    with pytest.raises(ValueError, match='Recorded source image identity mismatch'):
        runtime.source_image(recorded='sha256:' + 'b' * 64)


def test_modeling_build_uses_selected_base_and_records_exact_bundled_snapshot(
    tmp_path, monkeypatch
):
    repo = tmp_path / 'repo'
    for name in (*runtime.source_hashes(), 'deployment/pins.json', 'modeling/provenance.md'):
        target = repo / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(runtime.REPO / name, target)
    pins_path = repo / 'deployment/pins.json'
    pins = json.loads(pins_path.read_text())
    selected = 'ruby@sha256:' + 'b' * 64
    pins['ruby_base_image'] = selected
    pins['verified_sources']['WhatsOpt']['commit'] = 'stale duplicate'
    pins_path.write_text(json.dumps(pins) + '\n')
    monkeypatch.setattr(runtime, 'REPO', repo)
    monkeypatch.setattr(runtime.local_paths, 'scratch_root', lambda: tmp_path)
    monkeypatch.setattr(runtime, 'source_image', lambda **kwargs: 'sha256:' + 'a' * 64)
    monkeypatch.setattr(runtime, 'stage_native_inputs', lambda context: None)
    monkeypatch.setattr(runtime, 'upstream_archive', lambda: io.BytesIO(b'archive'))
    monkeypatch.setattr(runtime, 'base_reference', contextlib.nullcontext)
    monkeypatch.setattr(runtime, 'run', lambda *args: 'sha256:' + 'c' * 64)
    calls = []

    def build(command, **kwargs):
        context = Path(command[-1])
        identity = json.loads((context / 'notices/source-identity.json').read_text())
        snapshot = (context / 'notices/pins.json').read_bytes()
        calls.append((command, identity, snapshot))
        return subprocess.CompletedProcess(command, 0, '', '')

    monkeypatch.setattr(runtime.subprocess, 'run', build)
    evidence = tmp_path / 'evidence'
    evidence.mkdir()
    runtime.build(evidence=evidence)
    command, identity, snapshot = calls[0]
    assert command[command.index('RUBY_IMAGE=' + selected) - 1] == '--build-arg'
    assert identity['source_build_inputs']['ruby_image'] == selected
    assert identity['upstream']['commit'] == runtime.UPSTREAM['commit']
    assert identity['upstream']['archive_sha256'] == runtime.UPSTREAM['sha256']
    assert snapshot == pins_path.read_bytes()
    digest = hashlib.sha256(snapshot).hexdigest()
    assert identity['pins_snapshot_sha256'] == digest
    record = json.loads((evidence / 'modeling-build-identity.json').read_text())
    assert record['inputs']['ruby_image'] == selected
    assert record['pins_snapshot_sha256'] == digest
    assert 'pins_snapshot_sha256' not in record['inputs']


def test_image_identity_refuses_changed_bundled_pins(monkeypatch):
    image = 'sha256:' + 'c' * 64
    recorded = dict(pins_snapshot_sha256='a' * 64)
    responses = iter([image, json.dumps(recorded), 'b' * 64 + '  pins.json'])
    monkeypatch.setattr(runtime, 'run', lambda *args: next(responses))
    with pytest.raises(ValueError, match='bundled pins snapshot identity mismatch'):
        runtime.image_identity(image)


@pytest.mark.parametrize('field', ['source_hashes', 'source_build_inputs'])
def test_image_identity_refuses_stale_recorded_inputs(monkeypatch, field):
    image = 'sha256:' + 'c' * 64
    source = 'sha256:' + 'a' * 64
    recorded = dict(
        source_image=source,
        source_hashes=runtime.source_hashes(),
        source_build_inputs=runtime.source_build_inputs(),
        pins_snapshot_sha256='d' * 64,
    )
    recorded[field] = {}
    responses = iter([image, json.dumps(recorded), 'd' * 64 + '  pins.json'])
    monkeypatch.setattr(runtime, 'run', lambda *args: next(responses))
    lookup = Mock(return_value=source)
    monkeypatch.setattr(runtime, 'source_image', lookup)
    with pytest.raises(ValueError, match='current reviewed sources'):
        runtime.image_identity(image)
    lookup.assert_called_once_with(recorded=source)
