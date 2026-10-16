"""A check releases disposable stores while preserving scientific and foreign data."""
import live_fence
live_runtime_fence = live_fence.pytest_fixture('baseline')
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from uuid import uuid4

import pytest
import check_storage as storage
import check_build_cache as cache
import local_paths

DEPLOYMENT = Path(__file__).resolve().parents[1]


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    scratch = tmp_path / 'scratch'
    scratch.mkdir()
    monkeypatch.setenv(local_paths.SCRATCH_ROOT, str(scratch))
    monkeypatch.setenv('HYPRN_MVP_TEST_MIN_FREE_BYTES', '1')
    monkeypatch.setenv('HYPRN_MVP_TEST_SCRATCH_BYTES', str(32 * storage.MiB))
    monkeypatch.setenv('HYPRN_MVP_TEST_EVIDENCE_BYTES', str(64 * 1024))
    monkeypatch.delenv(storage.SESSION, raising=False)
    return scratch


def command(body):
    # Exercise the same allocation/register boundary used by the real check runner.
    setup = f"import sys; sys.path.insert(0, {str(DEPLOYMENT)!r}); sys.path.insert(0, {str(DEPLOYMENT / 'tests')!r})\n"
    setup += "import scoped_fixture as fixture\nfrom pathlib import Path\nimport os,time,sys\nscope=fixture.allocate_scope(fixture.new_scope())\n"
    return [sys.executable, '-I', '-B', '-c', setup + body]


def records(scratch):
    return [json.loads(p.read_text()) for p in (scratch / '.hyprn-checks').glob('*/session.json')]


@pytest.mark.parametrize('status', [0, 7])
def test_success_and_failure_release_stores_and_bound_repeated_evidence(isolated, status):
    unrelated = isolated / 'authored-study'
    unrelated.mkdir()
    (unrelated / 'record').write_text('immutable scientific record')
    for _ in range(4):
        assert storage.supervise(command(
            "(scope.root/'artifacts/data').write_bytes(os.urandom(2*1024*1024))\n"
            "(scope.root/'evidence/result.log').write_text('checked\\n'*3000)\n"
            f"sys.exit({status})")) == status
        assert not list(isolated.glob(local_paths.SCOPE_PREFIX + '*'))
        assert storage.allocated(isolated / '.hyprn-checks') <= 64 * 1024
    assert (unrelated / 'record').read_text() == 'immutable scientific record'


def test_budget_terminates_writer_and_releases_its_scope(isolated, monkeypatch):
    monkeypatch.setenv('HYPRN_MVP_TEST_SCRATCH_BYTES', str(storage.MiB))
    start = time.monotonic()
    assert storage.supervise(command(
        "(scope.root/'artifacts/data').write_bytes(os.urandom(2*1024*1024))\ntime.sleep(30)")) == 2
    assert time.monotonic() - start < 15
    assert not list(isolated.glob(local_paths.SCOPE_PREFIX + '*'))
    assert 'budget exceeded' in records(isolated)[0]['failure']


def test_existing_store_is_not_adopted_or_deleted(isolated):
    root = isolated / (local_paths.SCOPE_PREFIX + str(uuid4()))
    root.mkdir()
    (root / 'authored').write_text('preserve')
    assert storage.supervise(command("pass")) == 0
    assert (root / 'authored').read_text() == 'preserve'


def test_retention_expires_and_preserves_live_session(isolated):
    assert storage.supervise(command("(scope.root/'artifacts/data').write_text('retain')"), keep=True) == 0
    scope = next(isolated.glob(local_paths.SCOPE_PREFIX + '*'))
    session = next(p for p in (isolated / '.hyprn-checks').iterdir() if p.is_dir())
    record = json.loads((session / 'session.json').read_text())
    assert scope.exists()
    record['finished'] = time.time() - 86401
    storage.write(session / 'session.json', record)
    storage.collect(isolated / '.hyprn-checks', storage.MiB)
    assert not scope.exists() and not session.exists()


def test_symlink_substitution_refuses_cleanup(isolated):
    assert storage.supervise(command('pass'), keep=True) == 0
    session = next(p for p in (isolated / '.hyprn-checks').iterdir() if p.is_dir())
    record = json.loads(next(session.glob('*.scope.json')).read_text())
    root = Path(record['path'])
    moved = root.with_name('authoring')
    root.rename(moved)
    root.symlink_to(moved, target_is_directory=True)
    with pytest.raises(ValueError, match='Unsafe'):
        storage.finish(session)
    assert moved.exists()


def test_symlink_inside_disposable_tree_does_not_delete_target(isolated):
    target = isolated / 'authoring'
    target.mkdir()
    (target / 'record').write_text('preserve')
    assert storage.supervise(command(f"(scope.root/'tmp/link').symlink_to({str(target)!r}, target_is_directory=True)")) == 0
    assert (target / 'record').read_text() == 'preserve'


def test_abandoned_completed_child_is_recovered(isolated):
    assert storage.supervise(command('pass'), keep=True) == 0
    session = next(p for p in (isolated / '.hyprn-checks').iterdir() if p.is_dir())
    record = json.loads((session / 'session.json').read_text())
    record.pop('finished')
    record.update(pid=2147483647, child=2147483646)
    storage.write(session / 'session.json', record)
    storage.collect(isolated / '.hyprn-checks', storage.MiB)
    assert not list(isolated.glob(local_paths.SCOPE_PREFIX + '*'))


def test_interrupt_stops_child_and_releases_files(isolated):
    script = f"import sys; sys.path.insert(0,{str(DEPLOYMENT)!r}); import check_storage; sys.exit(check_storage.supervise({command('time.sleep(60)')!r}))"
    parent = subprocess.Popen([sys.executable, '-I', '-B', '-c', script])
    try:
        deadline = time.monotonic() + 10
        while not list(isolated.glob(local_paths.SCOPE_PREFIX + '*')):
            assert time.monotonic() < deadline
            time.sleep(.05)
        parent.send_signal(signal.SIGTERM)
        assert parent.wait(timeout=10) == 130
        assert not list(isolated.glob(local_paths.SCOPE_PREFIX + '*'))
    finally:
        if parent.poll() is None:
            parent.kill()
            parent.wait()


def test_invalid_budget_is_refused_before_allocation(isolated, monkeypatch):
    monkeypatch.setenv('HYPRN_MVP_TEST_SCRATCH_BYTES', '0')
    with pytest.raises(ValueError, match='positive integer'):
        storage.supervise(command('pass'))
    assert not list(isolated.iterdir())


def test_cache_attribution_does_not_cross_into_unrelated_descendants():
    rows = [dict(ID='base', Description='base'),
            dict(ID='project', Description='COPY hyprn', Parents=['base']),
            dict(ID='child', Description='compile', Parents=['project']),
            dict(ID='other', Description='other app', Parents=['base'])]
    assert {r['ID'] for r in cache.attributed(rows)} == {'base', 'project', 'child'}


def test_prune_success_does_not_hide_an_unreclaimed_budget(monkeypatch):
    row = dict(ID='owned', Description='hyprn', Size='2MB', Reclaimable=True, Shared=False)
    monkeypatch.setattr(cache, 'inventory', lambda: [row])
    calls = []
    monkeypatch.setattr(cache.subprocess, 'run', lambda command, **kw: calls.append(command))
    with pytest.raises(ValueError, match='remains over budget'):
        cache.enforce(100)
    assert '--reserved-space' in calls[0] and 'id~=^(owned)$' in calls[0]


def test_live_session_is_never_recovered(isolated):
    assert storage.supervise(command('pass'), keep=True) == 0
    session = next(p for p in (isolated / '.hyprn-checks').iterdir() if p.is_dir())
    record = json.loads((session / 'session.json').read_text())
    record.pop('finished')
    record.update(pid=os.getpid(), child=None)
    storage.write(session / 'session.json', record)
    storage.collect(isolated / '.hyprn-checks', storage.MiB)
    assert list(isolated.glob(local_paths.SCOPE_PREFIX + '*'))


def test_actual_native_store_identity_update_can_be_released(isolated):
    assert storage.supervise(command(
        "import json\nfrom uuid import uuid4\np=scope.root/'scope.json'\n"
        "value=json.loads(p.read_text()); value['store_uuid']=str(uuid4()); p.write_text(json.dumps(value))")) == 0
    assert not list(isolated.glob(local_paths.SCOPE_PREFIX + '*'))


def test_replaced_directory_is_not_deleted(isolated):
    assert storage.supervise(command('pass'), keep=True) == 0
    session = next(p for p in (isolated / '.hyprn-checks').iterdir() if p.is_dir())
    record = json.loads(next(session.glob('*.scope.json')).read_text())
    original = Path(record['path'])
    marker = (original / 'scope.json').read_bytes()
    original.rename(original.with_name('saved-experiment'))
    original.mkdir()
    (original / 'scope.json').write_bytes(marker)
    with pytest.raises(ValueError, match='identity changed'):
        storage.finish(session)
    assert original.exists()


def test_free_disk_reserve_refuses_admission(isolated, monkeypatch):
    import shutil
    monkeypatch.setenv('HYPRN_MVP_TEST_MIN_FREE_BYTES', str(shutil.disk_usage(isolated).free + storage.GiB))
    with pytest.raises(ValueError, match='Insufficient free disk'):
        storage.supervise(command('pass'))
    assert not list(isolated.glob(local_paths.SCOPE_PREFIX + '*'))
