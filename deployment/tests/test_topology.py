"""Fail-closed deployment decisions; no Docker or legacy runtime is required."""
# Live-runtime fence (deployment/tests/live_fence.py): refuses live roots, live ports, docker, live entry points and real signals.
import sys as _fence_sys
from pathlib import Path as _FencePath
if str(_FencePath(__file__).resolve().parent) not in _fence_sys.path:
    _fence_sys.path.append(str(_FencePath(__file__).resolve().parent))
import live_fence  # noqa: E402
live_runtime_fence = live_fence.pytest_fixture('unit')
import importlib.util
import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]

def runtime():
    spec = importlib.util.spec_from_file_location('modeling_runtime_copy', ROOT / 'deployment/modeling_runtime.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def test_root_is_fixed_offcloud_and_rejects_symlink(tmp_path):
    m = runtime()
    assert m.checked_root(m.DEFAULT_ROOT) == m.DEFAULT_ROOT
    for path in [ROOT, Path('/tmp'), m.DEFAULT_ROOT.parent, tmp_path / 'other-modeling-root']:
        with pytest.raises(ValueError): m.checked_root(path)
    link = tmp_path / 'linked'
    link.symlink_to(ROOT, target_is_directory=True)
    with pytest.raises(ValueError): m.checked_root(link)

def test_only_exact_owned_resources_are_actionable():
    m = runtime()
    valid = {'Name': '/' + m.CONTAINER, 'Config': {'Labels': {m.LABEL: m.OWNER}}}
    m.assert_owned(valid, 'container')
    for value in [{**valid, 'Name': '/' + m.CONTAINER + '-other'}, {**valid, 'Config': {'Labels': {}}}]:
        with pytest.raises(ValueError): m.assert_owned(value, 'container')

def test_recipe_has_private_modeling_and_no_launch_or_app_mounts():
    m = runtime()
    recipe = json.loads((ROOT / 'deployment/modeling-compose.yaml').read_text())
    model = recipe['services']['modeling']
    assert not model.get('ports')
    assert model['networks'] == ['model_private']
    assert recipe['networks']['model_private']['internal'] is True
    assert model['user'] == '10001:10001'
    assert model['read_only'] and model['cap_drop'] == ['ALL']
    assert model['security_opt'] == ['no-new-privileges:true']
    assert set(v['target'] for v in model['volumes']) == {'/store', '/run/model.key', '/run/rails.key'}
    assert not any(v['target'].endswith('sock') for v in model['volumes'])
    assert set(recipe['services']) == {'modeling'}
    assert recipe['x-hyprn-mvp-boundaries']['candidate_execution'] == 'blocked_pending_plan_01_12_consumer_attestation'
    assert model['container_name'] == m.CONTAINER and model['labels'] == {m.LABEL: m.OWNER}
    assert recipe['networks']['model_private']['name'] == m.NETWORK

def test_image_is_rebuilt_without_inheriting_execution_layers():
    dockerfile = (ROOT / 'deployment/modeling.Dockerfile').read_text()
    assert 'FROM ${RUBY_IMAGE}' in dockerfile
    assert 'USER 10001:10001' in dockerfile
    assert 'COPY --from=source /native /native' in dockerfile
    assert 'LAUNCHER=' not in dockerfile
