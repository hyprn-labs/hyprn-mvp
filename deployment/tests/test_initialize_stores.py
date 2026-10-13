"""Store initialization must never replace retained data or weaken storage boundaries."""
# Live-runtime fence (deployment/tests/live_fence.py): refuses live roots, live ports, docker, live entry points and real signals.
import sys as _fence_sys
from pathlib import Path as _FencePath
if str(_FencePath(__file__).resolve().parent) not in _fence_sys.path:
    _fence_sys.path.append(str(_FencePath(__file__).resolve().parent))
import live_fence  # noqa: E402
live_runtime_fence = live_fence.pytest_fixture('unit')
import importlib.util
import sys
from pathlib import Path
import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'deployment'))
import initialize_stores as recovery
import local_paths
import application_runtime
import modeling_runtime
import execution_runtime
import native_environment
import dispatch_runtime


def test_active_roots_are_persistent_separate_and_off_cloud():
    roots = [application_runtime.ROOT, modeling_runtime.DEFAULT_ROOT, execution_runtime.ROOT]
    assert len(set(roots)) == 3
    for root in roots:
        assert root.parent == local_paths.data_root()
        assert 'CloudStorage' not in root.parts and 'tmp' not in root.parts
    assert recovery.STORES == (application_runtime.ROOT, modeling_runtime.DEFAULT_ROOT)
    assert execution_runtime.ROOT == native_environment.ROOT == dispatch_runtime.ROOT
    assert application_runtime.UI_DIST.is_relative_to(application_runtime.ROOT)
    assert recovery.EVIDENCE.is_relative_to(application_runtime.ROOT)


def test_bootstrap_refuses_an_unset_port_before_any_effect(monkeypatch):
    monkeypatch.delenv(local_paths.PORT, raising=False)
    monkeypatch.setattr(recovery, 'guarded_empty_root', lambda root: pytest.fail('store inspected before the port'))
    with pytest.raises(local_paths.LocationUnset, match=local_paths.PORT):
        recovery.bootstrap()


def test_store_root_refuses_nonempty_unknown_or_alias(tmp_path, monkeypatch):
    root = tmp_path / 'application'
    monkeypatch.setattr(recovery, 'STORES', (root,))
    with pytest.raises(ValueError, match='nonsymlink store'):
        recovery.guarded_empty_root(tmp_path / 'other')
    recovery.guarded_empty_root(root)
    root.mkdir()
    (root/'study.sqlite').write_bytes(b'retained')
    with pytest.raises(ValueError, match='already has contents'):
        recovery.guarded_empty_root(root)
    assert (root/'study.sqlite').read_bytes() == b'retained'
    alias = tmp_path/'alias'; alias.symlink_to(root, target_is_directory=True)
    monkeypatch.setattr(recovery, 'STORES', (alias,))
    with pytest.raises(ValueError, match='nonsymlink'):
        recovery.guarded_empty_root(alias)


@pytest.mark.parametrize('difference', ['running','image','owner','retained_mount'])
def test_container_archive_refuses_unexpected_or_retained_resources(tmp_path, monkeypatch, difference):
    info = {'Image': recovery.APP_IMAGE, 'State': {'Running': False},
            'Config': {'Labels': {modeling_runtime.LABEL: application_runtime.OWNER}}, 'Mounts': []}
    if difference == 'running': info['State']['Running'] = True
    if difference == 'image': info['Image'] = 'another-image'
    if difference == 'owner': info['Config']['Labels'] = {}
    if difference == 'retained_mount': info['Mounts'] = [{'Type':'bind','Source':str(tmp_path)}]
    monkeypatch.setattr(modeling_runtime, 'inspect', lambda name: info)
    monkeypatch.setattr(recovery, 'run', lambda *a, **kw: pytest.fail('Unsafe mutation'))
    with pytest.raises(ValueError):
        recovery.archive_missing_container(application_runtime.NAME, recovery.APP_IMAGE, application_runtime.OWNER)


def test_recovery_evidence_is_append_only(tmp_path):
    path = tmp_path/'checkpoint.json'
    recovery.emit(path, {'first':True})
    with pytest.raises(FileExistsError): recovery.emit(path, {'second':True})
    assert 'first' in path.read_text()
