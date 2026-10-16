"""Retention never overrides recent work, active work or source preservation."""
import live_fence
live_runtime_fence = live_fence.pytest_fixture('baseline')
import json
import time
from pathlib import Path

import pytest
import experiment_storage as storage


@pytest.fixture
def experiment(tmp_path):
    root = tmp_path / 'demo'
    root.mkdir()
    policy = tmp_path / 'policy.json'
    storage.enroll(policy, [str(root)], budget=1024*1024, reserve=1)
    return policy, root


def idle():
    return '', [], []


def expired(policy, **kwargs):
    return storage.collect(policy, apply=True, now=time.time()+86410, inspect_activity=idle, **kwargs)


def test_repeated_backups_expire_without_removing_code_or_unknown_files(experiment):
    policy, root = experiment
    (root / 'serve.py').write_text('print("demo")')
    (root / 'package.json').write_text('{"type":"module"}')
    (root / 'unrecognized').write_text('retain')
    (root / 'serve.py.bak').write_text('source backup')
    (root / 'source.zip').write_bytes(b'source archive')
    baseline = storage.snapshot(root)['bytes']
    for _ in range(3):
        (root / 'backup.sqlite').write_bytes(b'x'*131072)
        result = expired(policy)
        assert result['removed_bytes'] >= 131072
        assert result['used_bytes'] == baseline
        assert (root / 'serve.py').read_text() == 'print("demo")'
        assert (root / 'package.json').exists()
        assert (root / 'unrecognized').exists()


def test_recent_file_protects_entire_experiment(experiment):
    policy, root = experiment
    (root / 'backup.sqlite').write_bytes(b'x'*8192)
    result = storage.collect(policy, apply=True, inspect_activity=idle)
    assert result['roots'][0]['state'] == 'recent'
    assert result['removed_bytes'] == 0


@pytest.mark.parametrize('state', [('python /experiment/serve.py', [], []), ('', ['/experiment/open.sqlite'], []), ('', [], ['/experiment'])])
def test_activity_signals_protect_roots(state):
    assert storage.busy(Path('/experiment'), state)
    assert not storage.busy(Path('/other'), state)
    assert not storage.busy(Path('/experiment'), ('', ['/'], []))


def test_active_expired_data_survives_budget_pressure(experiment):
    policy, root = experiment
    (root / 'backup.sqlite').write_bytes(b'x'*8192)
    storage.enroll(policy, [str(root)], budget=1)
    result = storage.collect(policy, apply=True, now=time.time()+86410,
                             inspect_activity=lambda: ('', [str(root / 'backup.sqlite')], []))
    assert not result['admitted']
    assert result['roots'][0]['state'] == 'active'
    assert (root / 'backup.sqlite').exists()


def test_source_trees_symlinks_and_hardlinks_survive(experiment, tmp_path):
    policy, root = experiment
    source = root / 'source'
    source.mkdir()
    (source / 'asset.png').write_bytes(b'code asset')
    repo = root / 'repo'
    repo.mkdir()
    (repo / '.git').mkdir()
    (repo / 'fixture.csv').write_text('source fixture')
    outside = tmp_path / 'outside.sqlite'
    outside.write_text('preserve')
    (root / 'link.sqlite').symlink_to(outside)
    (root / 'hard.sqlite').hardlink_to(outside)
    assert expired(policy)['removed_bytes'] == 0
    assert outside.read_text() == 'preserve'


def test_changed_or_newly_active_root_is_not_collected(experiment):
    policy, root = experiment
    backup = root / 'backup.sqlite'
    backup.write_text('preserve')
    calls = []
    def becomes_active():
        calls.append(1)
        return ('', [str(backup)] if len(calls) > 1 else [], [])
    result = storage.collect(policy, apply=True, now=time.time()+86410, inspect_activity=becomes_active)
    assert result['removed_bytes'] == 0
    assert backup.exists()


def test_inspection_failure_refuses_deletion(experiment):
    policy, root = experiment
    (root / 'backup.sqlite').write_text('preserve')
    def unavailable():
        raise OSError('activity unavailable')
    with pytest.raises(OSError):
        storage.collect(policy, apply=True, now=time.time()+86410, inspect_activity=unavailable)
    assert (root / 'backup.sqlite').exists()


def test_overlapping_roots_and_repository_enrollment_refused(experiment):
    policy, root = experiment
    child = root / 'nested'
    child.mkdir()
    with pytest.raises(ValueError, match='overlap'):
        storage.enroll(policy, [str(child)])
    (child / '.git').mkdir()
    with pytest.raises(ValueError, match='repository'):
        storage.enroll(policy, [str(child)])


def test_status_never_deletes_and_recent_budget_refuses(experiment):
    policy, root = experiment
    (root / 'backup.sqlite').write_bytes(b'x'*8192)
    storage.enroll(policy, [str(root)], budget=1)
    assert not storage.collect(policy, inspect_activity=idle)['admitted']
    assert (root / 'backup.sqlite').exists()


def test_replaced_root_symlink_refused(experiment, tmp_path):
    policy, root = experiment
    root.rmdir()
    other = tmp_path / 'other'
    other.mkdir()
    (other / 'backup.sqlite').write_text('preserve')
    root.symlink_to(other, target_is_directory=True)
    with pytest.raises(ValueError, match='Unsafe'):
        expired(policy)
    assert (other / 'backup.sqlite').exists()


def test_public_cli_refuses_command_under_budget_pressure(experiment, monkeypatch, capsys):
    import sys
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / 'editions/local/src'))
    from hyprn_mvp_local import cli
    policy, root = experiment
    (root / 'backup.sqlite').write_bytes(b'x'*8192)
    storage.enroll(policy, [str(root)], budget=1)
    marker = root / 'should-not-run'
    assert cli.main(['dev', 'storage', 'run', '--config', str(policy), '--', sys.executable,
                     '-c', f'open({str(marker)!r}, "w").close()']) == 2
    assert not marker.exists()
    assert (root / 'backup.sqlite').exists()


def test_public_cli_preserves_command_failure(experiment, monkeypatch):
    import sys
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / 'editions/local/src'))
    from hyprn_mvp_local import cli
    policy, root = experiment
    assert cli.main(['dev', 'storage', 'run', '--config', str(policy), '--', sys.executable,
                     '-c', 'raise SystemExit(7)']) == 7


def test_automatic_admission_uses_only_explicit_policy(experiment, monkeypatch):
    policy, root = experiment
    (root / 'backup.sqlite').write_bytes(b'x'*8192)
    storage.enroll(policy, [str(root)], budget=1)
    monkeypatch.setenv('HYPRN_MVP_EXPERIMENT_STORAGE_CONFIG', str(policy))
    with pytest.raises(ValueError, match='budget exceeded'):
        storage.automatic()
    assert (root / 'backup.sqlite').exists()
