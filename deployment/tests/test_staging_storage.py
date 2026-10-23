"""Only expired inactive generated exports and exactly owned volumes are disposable."""
import live_fence
live_runtime_fence = live_fence.pytest_fixture('baseline')
import json
import time
from pathlib import Path
import pytest
import staging_storage as storage


@pytest.fixture
def staging(tmp_path):
    parent = tmp_path / 'staging'
    parent.mkdir()
    root = parent / 'build'
    root.mkdir()
    (root / 'source.json').write_text(json.dumps(dict(schema='hyprn-cloud-build-source/v1', source_commit='a'*40)))
    source = root / 'source'
    source.mkdir()
    (source / 'main.py').write_text('preserve')
    (root / 'source.tar').write_bytes(b'preserve source archive')
    artifacts = root / 'artifacts'
    artifacts.mkdir()
    policy = tmp_path / 'policy.json'
    storage.enroll(policy, [str(parent)], reserve=1)
    return policy, root, artifacts


def idle():
    return '', [], []


def collect(policy, **kwargs):
    return storage.collect(policy, include_docker=False, inspect_activity=idle, **kwargs)


def test_expired_exports_return_to_baseline_and_source_survives(staging):
    policy, root, artifacts = staging
    baseline = storage.check_storage.allocated(root)
    for _ in range(3):
        (artifacts / 'app.oci.tar').write_bytes(b'x'*131072)
        result = collect(policy, apply=True, now=time.time()+90000)
        assert result['removed_file_bytes'] == 131072
        assert result['used_bytes'] == baseline
        assert (root / 'source/main.py').read_text() == 'preserve'
        assert (root / 'source.tar').exists()


def test_recent_experiment_preserves_all_exports(staging):
    policy, root, artifacts = staging
    (artifacts / 'app.oci.tar').write_bytes(b'x'*8192)
    assert collect(policy, apply=True)['removed_file_bytes'] == 0


def test_active_old_build_preserves_exports(staging):
    policy, root, artifacts = staging
    (artifacts / 'app.oci.tar').write_bytes(b'x'*8192)
    result = storage.collect(policy, apply=True, now=time.time()+90000, include_docker=False,
                             inspect_activity=lambda: ('', [str(root / 'source/main.py')], []))
    assert result['removed_file_bytes'] == 0
    assert result['roots'][0]['state'] == 'active'


def test_nested_repository_and_linked_export_survive(staging, tmp_path):
    policy, root, artifacts = staging
    (artifacts / '.git').mkdir()
    (artifacts / 'app.oci.tar').write_bytes(b'x'*8192)
    (root / 'native.tar.gz').symlink_to(artifacts / 'app.oci.tar')
    assert collect(policy, apply=True, now=time.time()+90000)['removed_file_bytes'] == 0


def test_new_manifest_is_discovered_without_reenrollment(staging):
    policy, root, artifacts = staging
    new = root.parent / 'new-release'
    new.mkdir()
    (new / 'payload.json').write_text(json.dumps(dict(schema='hyprn-hosted-payload/v1')))
    (new / 'worker.oci.tar').write_bytes(b'x'*4096)
    assert len(collect(policy)['roots']) == 2
    assert collect(policy, apply=True, now=time.time()+90000)['removed_file_bytes'] == 4096


def test_budget_pressure_refuses_without_deleting_recent_data(staging):
    policy, root, artifacts = staging
    storage.enroll(policy, [str(root.parent)], budget=1)
    (artifacts / 'app.oci.tar').write_bytes(b'x'*8192)
    result = collect(policy, apply=True)
    assert not result['admitted']
    assert result['removed_file_bytes'] == 0


def test_volume_requires_exact_ownership_age_inactive_commit_and_no_references():
    name = 'hyprn-staging-build-'+'a'*12+'-cache'
    volume = dict(Name=name, Labels={'org.hyprn.build':'a'*40}, CreatedAt='2020-01-01T00:00:00Z')
    assert storage.old_volume(volume, {'a'*40}, set(), time.time()-86400)
    assert not storage.old_volume(volume, {'a'*40}, {name}, time.time()-86400)
    assert not storage.old_volume(volume, set(), set(), time.time()-86400)
    volume['Name'] = 'unrelated'
    assert not storage.old_volume(volume, {'a'*40}, set(), time.time()-86400)


def test_inspection_failure_prevents_deletion(staging):
    policy, root, artifacts = staging
    (artifacts / 'app.oci.tar').write_bytes(b'x'*8192)
    def unavailable():
        raise OSError('unavailable')
    with pytest.raises(OSError):
        storage.collect(policy, apply=True, inspect_activity=unavailable, include_docker=False)
    assert (artifacts / 'app.oci.tar').exists()


def test_recent_volume_contents_override_old_creation_time(staging, monkeypatch):
    policy, root, artifacts = staging
    now = time.time()+90000
    names = ['hyprn-staging-build-'+'a'*12+'-'+suffix for suffix in ('cache', 'native')]
    volumes = [dict(Name=name, Labels={'org.hyprn.build':'a'*40}, CreatedAt='2020-01-01T00:00:00Z') for name in names]
    removed = []
    def docker(*args):
        if args[:2] == ('volume', 'ls'):
            return '\n'.join(names)
        if args[:2] == ('volume', 'inspect'):
            return json.dumps(volumes)
        if args[:2] == ('volume', 'rm'):
            removed.append(args[2]); return args[2]
        raise AssertionError(args)
    monkeypatch.setattr(storage, 'docker', docker)
    monkeypatch.setattr(storage, 'containers', lambda: [])
    monkeypatch.setattr(storage.check_build_cache, 'inventory', lambda: [])
    monkeypatch.setattr(storage, 'volume_data', lambda name, image: dict(latest=now if name==names[0] else 0, bytes=4096))
    storage.collect(policy, apply=True, now=now, inspect_activity=idle)
    assert removed == [names[1]]


def test_cache_pruning_is_exact_unshared_and_engine_age_filtered(staging, monkeypatch):
    policy, root, artifacts = staging
    calls = []
    monkeypatch.setattr(storage, 'containers', lambda: [])
    records = [dict(ID='old-project', Reclaimable=True, Shared=False, Size=4096),
               dict(ID='shared', Reclaimable=True, Shared=True, Size=4096)]
    monkeypatch.setattr(storage.check_build_cache, 'inventory', lambda: records)
    def docker(*args):
        calls.append(args)
        return ''
    monkeypatch.setattr(storage, 'docker', docker)
    storage.collect(policy, apply=True, now=time.time()+90000, inspect_activity=idle)
    prune = next(call for call in calls if call[:2] == ('buildx', 'prune'))
    assert 'until=24h' in prune
    assert 'id~=^(old\\-project)$' in prune
    assert all('shared' not in argument for argument in prune)


def test_reviewed_native_build_recipes_identify_unnamed_cache():
    rows = [dict(ID='native', Description='mount / from exec /bin/sh -c corepack enable && corepack prepare yarn@4.14.1 --activate && yarn install --immutable'),
            dict(ID='engine', Description='[stage-1 4/6] COPY --from=build /opt/runtime/venv /opt/runtime/venv'),
            dict(ID='other', Description='RUN yarn install')]
    assert {r['ID'] for r in storage.check_build_cache.attributed(rows)} == {'native', 'engine'}


def test_automatic_diagnostics_do_not_corrupt_build_json_output(staging, monkeypatch, capsys):
    policy, root, artifacts = staging
    monkeypatch.setenv('HYPRN_MVP_STAGING_STORAGE_CONFIG', str(policy))
    monkeypatch.setattr(storage, 'policy_path', lambda: policy)
    monkeypatch.setattr(storage, 'collect', lambda *a, **k: {'admitted':True})
    storage.automatic()
    captured = capsys.readouterr()
    assert captured.out == ''
    assert 'staging_storage' in captured.err


def test_scoped_child_cannot_discover_host_retention_policy(monkeypatch):
    monkeypatch.setenv(storage.local_paths.CHECK_SESSION, '/isolated/session')
    monkeypatch.delenv('HYPRN_MVP_STAGING_STORAGE_CONFIG', raising=False)
    monkeypatch.delenv('HYPRN_MVP_EXPERIMENT_STORAGE_CONFIG', raising=False)
    def forbidden():
        raise AssertionError('host policy was accessed')
    monkeypatch.setattr(storage, 'policy_path', forbidden)
    monkeypatch.setattr(storage.experiment_storage, 'configuration', forbidden)
    storage.automatic()
    storage.experiment_storage.automatic()
