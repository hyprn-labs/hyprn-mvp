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
from hyprn_mvp_app.locations import location_refusal


def test_active_roots_are_persistent_separate_and_off_cloud():
    roots = [application_runtime.ROOT, modeling_runtime.DEFAULT_ROOT, execution_runtime.ROOT]
    assert len(set(roots)) == 3
    for root in roots:
        assert root.parent == local_paths.data_root()
        assert location_refusal(root) is None and 'tmp' not in root.parts
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


@pytest.mark.parametrize('collision', range(4))
def test_bootstrap_preserves_every_existing_deployment_resource(tmp_path, monkeypatch, collision):
    monkeypatch.setattr(local_paths, 'port', lambda: 8000)
    monkeypatch.setattr(recovery, 'STORES', (tmp_path / 'application', tmp_path / 'modeling'))
    calls = []

    def inspect(*args):
        calls.append(args)
        return {} if len(calls) - 1 == collision else None

    monkeypatch.setattr(modeling_runtime, 'inspect', inspect)
    monkeypatch.setattr(modeling_runtime, 'setup', lambda *a: pytest.fail('Unsafe setup'))
    monkeypatch.setattr(application_runtime, 'setup', lambda: pytest.fail('Unsafe setup'))
    with pytest.raises(ValueError, match='Existing deployment resource'):
        recovery.bootstrap()
    assert not any(tmp_path.iterdir())


def test_bootstrap_uses_current_build_managers_after_all_preflights(tmp_path, monkeypatch):
    monkeypatch.setattr(local_paths, 'port', lambda: 8000)
    monkeypatch.setattr(recovery, 'STORES', (tmp_path / 'application', tmp_path / 'modeling'))
    monkeypatch.setattr(recovery, 'EVIDENCE', tmp_path / 'evidence')
    monkeypatch.setattr(modeling_runtime, 'inspect', lambda *a: None)
    calls = []
    monkeypatch.setattr(modeling_runtime, 'setup', lambda root: calls.append('modeling') or {})
    monkeypatch.setattr(application_runtime, 'setup', lambda: calls.append('application') or {})
    recovery.bootstrap()
    assert calls == ['modeling', 'application']
    assert (tmp_path / 'evidence/bootstrap.json').is_file()


def test_recovery_evidence_is_append_only(tmp_path):
    path = tmp_path/'checkpoint.json'
    recovery.emit(path, {'first':True})
    with pytest.raises(FileExistsError): recovery.emit(path, {'second':True})
    assert 'first' in path.read_text()
