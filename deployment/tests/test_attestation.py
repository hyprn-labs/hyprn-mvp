"""Worker attestation: the attested source inventory, image bytes and identity refusals.

Runs only against an isolated scoped worker, never a live activation.
"""
# Live-runtime fence (deployment/tests/live_fence.py): refuses live roots, live ports, live docker names, live entry points and foreign signals.
import sys as _fence_sys
from pathlib import Path as _FencePath
if str(_FencePath(__file__).resolve().parent) not in _fence_sys.path:
    _fence_sys.path.append(str(_FencePath(__file__).resolve().parent))
import live_fence  # noqa: E402
live_runtime_fence = live_fence.pytest_fixture('baseline')
import copy
import hashlib
import json
from pathlib import Path
import shutil
from unittest.mock import patch

import pytest
import execution_runtime as worker
import modeling_runtime as model
import checks as runner
import scoped_fixture as guard
from hyprn_mvp_integration import launcher
import native_origin_fixture as origin

REPO = Path(__file__).resolve().parents[2]
EXECUTION_SOURCES = (
    'integration/src/hyprn_mvp_integration/__init__.py',
    'integration/src/hyprn_mvp_integration/launcher.py',
    'integration/src/hyprn_mvp_integration/worker.py',
    'integration/src/hyprn_mvp_integration/results.py',
    'integration/src/hyprn_mvp_integration/calculation.py',
    # Exactly the modules reachable from a launch; modules unreachable from every launch
    # path (execution, modeling, result_bindings, store) are never part of the inventory.
    'integration/src/hyprn_mvp_integration/computational_export.py',
    # The installation loader and the location rule it applies: the launcher takes its root,
    # owner, native profile, engine endpoint and probed home folder from the installation.
    'integration/src/hyprn_mvp_integration/installation.py',
    'application/src/hyprn_mvp_app/locations.py',
    'application/src/hyprn_mvp_app/__init__.py',
    'application/src/hyprn_mvp_app/scientific_configuration.py',
    'application/src/hyprn_mvp_app/units.py',
    'application/src/hyprn_mvp_app/approach_closure.py',
    # Pure contract identity and validation, imported by the launcher and every bound validator.
    'application/src/hyprn_mvp_app/contracts.py',
    # The frozen bundle contract the launcher, calculation and retained reader import.
    'application/src/hyprn_mvp_app/execution_bundle.py',
    'deployment/execution_runtime.py',
    'deployment/worker.Dockerfile',
    'deployment/pins.json',
)
SOURCE_PATHS = tuple(sorted(set(EXECUTION_SOURCES) | set(model.source_hashes())))


@pytest.fixture(scope='module')
def attested():
    scope = guard.validate_scope(runner.PROJECTION_SCOPE)
    runtime = worker.build_worker(root=scope.root)
    evidence = launcher.attest(root=scope.root)
    assert evidence['passed'] and evidence['candidate_executions'] == 0
    assert all(evidence['access_checks'].values())
    return scope, runtime, evidence


def test_units_attestation_current_worker_bytes_and_inventory(attested):
    scope, runtime, evidence = attested
    expected = {p: hashlib.sha256((REPO/p).read_bytes()).hexdigest() for p in SOURCE_PATHS}
    assert runtime.get('source_hashes') == expected
    assert launcher.require_attestation(root=scope.root) == evidence
    # Inspect bytes inside the immutable image, not merely its source labels.
    script = "import hashlib,json;from pathlib import Path;print(json.dumps({n:hashlib.sha256(Path('/opt/hyprn_mvp_integration',n).read_bytes()).hexdigest() for n in ('worker.py','results.py','__init__.py')}))"
    output = launcher.command(['docker','run','--rm','--pull=never','--network=none',
        '--read-only','--cap-drop=ALL','--security-opt=no-new-privileges','--user=65534:65534',
        '--memory=256m','--pids-limit=32','--cpus=0.5',runtime['worker_image'],'python','-B','-c',script])
    actual = json.loads(output)
    assert actual == {n:hashlib.sha256((REPO/'integration/src/hyprn_mvp_integration'/n).read_bytes()).hexdigest() for n in actual}
    (scope.root/'evidence/image-source-bytes.json').write_text(json.dumps(actual,indent=2)+'\n')


@pytest.mark.parametrize('path', SOURCE_PATHS)
def test_units_attestation_source_drift_refuses_before_launch(attested, tmp_path, monkeypatch, path):
    scope, _, _ = attested
    for relative in SOURCE_PATHS:
        target = tmp_path/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO/relative,target)
    monkeypatch.setattr(launcher, '__file__', str(tmp_path/'integration/src/hyprn_mvp_integration/launcher.py'))
    # The unmodified local snapshot is equivalent, including actual image binding.
    launcher.require_attestation(root=scope.root)
    target = tmp_path/path
    target.write_bytes(target.read_bytes()+b'\n# deliberate source drift\n')
    original_popen = launcher.subprocess.Popen
    launches = []
    def guarded_popen(args, *a, **kw):
        if args[:2] == ['docker','run']:
            launches.append(args)
            raise AssertionError('Container launch reached')
        return original_popen(args, *a, **kw)
    with patch.object(launcher.subprocess, 'Popen', side_effect=guarded_popen):
        with pytest.raises(RuntimeError, match='source|stale'):
            launcher.require_attestation(root=scope.root)
        with pytest.raises(RuntimeError, match='source|stale'):
            launcher.isolated(tmp_path/'absent-bundle',expected_digest='0'*64,root=scope.root)
        assert launches == []


@pytest.mark.parametrize('change', ['missing-inventory','missing-entry','extra-entry','failed','policy','worker-label','results-label'])
def test_units_attestation_missing_or_forged_identity_refuses(attested, monkeypatch, change):
    scope, runtime, evidence = attested
    runtime_path = scope.root/'runtime.json'
    evidence_path = scope.root/'evidence/containment.json'
    original_runtime, original_evidence = runtime_path.read_bytes(), evidence_path.read_bytes()
    try:
        changed = copy.deepcopy(runtime)
        if change == 'missing-inventory':
            changed.pop('source_hashes', None)
        elif change == 'missing-entry':
            changed.setdefault('source_hashes', {}).pop(SOURCE_PATHS[0], None)
        elif change == 'extra-entry':
            changed.setdefault('source_hashes', {})['unreviewed.py'] = '0'*64
        elif change == 'failed':
            bad = copy.deepcopy(evidence);bad['passed'] = False
            evidence_path.write_text(json.dumps(bad))
        elif change == 'policy':
            monkeypatch.setattr(launcher,'POLICY',{**launcher.POLICY,'memory':'512m'})
        else:
            original_command = launcher.command
            def command(args, **kwargs):
                result = original_command(args, **kwargs)
                if args[:3] == ['docker','image','inspect']:
                    image = json.loads(result)
                    label = 'org.hyprn-mvp.'+change.removesuffix('-label')+'_sha256'
                    image[0]['Config']['Labels'][label] = '0'*64
                    return json.dumps(image)
                return result
            monkeypatch.setattr(launcher,'command',command)
        runtime_path.write_text(json.dumps(changed))
        with pytest.raises(RuntimeError, match='source|stale'):
            launcher.require_attestation(root=scope.root)
    finally:
        runtime_path.write_bytes(original_runtime)
        evidence_path.write_bytes(original_evidence)


@pytest.mark.parametrize('bad', ['live','shared','relative','missing-marker'])
def test_units_attestation_builder_refuses_bad_root_before_operational_access(monkeypatch, bad):
    # A well-formed scope root that was never allocated has no marker.
    roots = {'live': launcher.ROOT, 'shared': Path('/private/tmp'), 'relative': Path('relative'),
             'missing-marker': guard.new_scope().root}
    with patch.object(Path,'mkdir',side_effect=AssertionError('Write reached')) as write, \
         patch.object(worker,'run',side_effect=AssertionError('Docker reached')) as docker:
        with pytest.raises((ValueError,FileNotFoundError)):
            worker.build_worker(root=roots[bad])
        write.assert_not_called();docker.assert_not_called()


@pytest.mark.parametrize('root', [None, launcher.ROOT, Path('/private/tmp')])
def test_units_attestation_origin_refuses_live_and_default_before_operational_access(monkeypatch, root):
    monkeypatch.delenv('HYPRN_MVP_TEST_SCOPE_ROOT', raising=False)
    with patch.object(origin,'run',side_effect=AssertionError('Operational command reached')) as command, \
         patch.object(Path,'read_bytes',side_effect=AssertionError('Operational file read reached')) as read:
        with pytest.raises(ValueError,match='isolated'):
            with origin.attested_variant('sha256:'+'0'*64, **({} if root is None else {'root':root})):
                pytest.fail('Unsafe variant entered')
        command.assert_not_called();read.assert_not_called()


def test_units_attestation_closed_route_selects_only_attestation_cases():
    assert runner.GROUPS['units-attestation'] == ('deployment/tests/test_attestation.py',)
    assert runner.UNITS_SELECTIONS['units-attestation'] == ['-k','test_units_attestation_']
    assert 'units-activation' not in runner.GROUPS and 'units-activation' not in runner.UNITS_SELECTIONS
    with pytest.raises(ValueError):runner.targets_for('units-arbitrary')


def test_units_attestation_actual_variant_restores_exact_isolated_bytes_on_failure(attested):
    scope, runtime, _ = attested
    paths = [scope.root/'runtime.json',scope.root/'evidence/containment.json']
    before = [p.read_bytes() for p in paths]
    with pytest.raises(RuntimeError,match='synthetic caller failure'):
        with origin.attested_variant(origin.PRODUCER,root=scope.root) as evidence:
            assert evidence['passed'] and evidence['candidate_executions'] == 0
            assert launcher.identity(root=scope.root)['worker_image'] != runtime['worker_image']
            assert launcher.require_attestation(root=scope.root) == evidence
            raise RuntimeError('synthetic caller failure')
    assert [p.read_bytes() for p in paths] == before
    launcher.require_attestation(root=scope.root)


@pytest.mark.parametrize('name', ['locks','licenses','canaries','artifacts','evidence','runtime.json'])
def test_units_attestation_operational_symlinks_refused_before_build(name, tmp_path):
    scope = guard.allocate_scope(guard.new_scope())
    target = scope.root/name
    if target.is_dir():target.rmdir()
    target.symlink_to(tmp_path, target_is_directory=True)
    with patch.object(worker,'run',side_effect=AssertionError('Docker reached')) as docker:
        with pytest.raises(ValueError,match='Unsafe runtime'):
            worker.build_worker(root=scope.root)
        docker.assert_not_called()
    assert list(tmp_path.iterdir()) == []


def test_units_attestation_inventory_rejects_missing_and_added_native_sources(attested,tmp_path,monkeypatch):
    scope, _, _ = attested
    for relative in SOURCE_PATHS:
        target=tmp_path/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(REPO/relative,target)
    monkeypatch.setattr(launcher,'__file__',str(tmp_path/'integration/src/hyprn_mvp_integration/launcher.py'))
    target=tmp_path/'upstream/whatsopt-patches/unreviewed.patch'
    target.write_text('unreviewed')
    with pytest.raises(RuntimeError,match='source'):launcher.require_attestation(root=scope.root)
    target.unlink()
    (tmp_path/'contracts/schemas/model.schema.json').unlink()
    with pytest.raises(RuntimeError,match='source'):launcher.require_attestation(root=scope.root)


def test_units_attestation_source_change_during_build_never_publishes_runtime(monkeypatch):
    # Simulate a concurrent source edit at the builder boundary, without editing
    # repository bytes or running a second numerical dependency/image build.
    from subprocess import CompletedProcess
    scope = guard.allocate_scope(guard.new_scope())
    current = launcher.execution_source_hashes()
    changed = {**current, 'contracts/schemas/model.schema.json':'0'*64}
    calls = iter([current,changed])
    monkeypatch.setattr(launcher,'execution_source_hashes',lambda:next(calls))
    def command(*args):
        if args[:3] == ('docker','image','inspect'):
            if args[3] == worker.ENGINE:
                return json.dumps([{'Id':worker.ENGINE,'Architecture':'arm64',
                    'Config':{'Env':['PYTHON_VERSION=3.12']}}])
            return 'sha256:'+'0'*64
        assert args[:2] == ('docker','tag')
        return ''
    monkeypatch.setattr(worker,'run',command)
    monkeypatch.setattr(worker.subprocess,'run',lambda *a,**kw:CompletedProcess(a[0],0,'synthetic build',''))
    with pytest.raises(RuntimeError,match='source changed during worker build'):
        worker.build_worker(root=scope.root)
    assert not (scope.root/'runtime.json').exists()
    assert not (scope.root/'locks/worker.lock').exists()


def test_units_attestation_source_inventory_is_data_only_and_offline(monkeypatch):
    import builtins
    import socket
    original_import = builtins.__import__
    def guarded_import(name,*args,**kwargs):
        if name.split('.')[0] in {'openmdao','openturns','requests','httpx','aiida'}:
            raise AssertionError('Runtime/service import reached')
        return original_import(name,*args,**kwargs)
    with patch.object(builtins,'__import__',side_effect=guarded_import),          patch.object(socket,'socket',side_effect=AssertionError('Network reached')),          patch.object(launcher.subprocess,'run',side_effect=AssertionError('Process reached')):
        assert set(launcher.execution_source_hashes()) == set(SOURCE_PATHS)


def test_units_attestation_inventories_bind_every_changed_authority(tmp_path, monkeypatch):
    import application_runtime as app
    # The source inventory must not scan a served UI build outside the scope.
    monkeypatch.setattr(app, 'ui_dist', lambda: tmp_path)
    inventories = (app.hashes(), model.source_hashes(), launcher.execution_source_hashes())
    required = (
        ('application/src/hyprn_mvp_app/units.py', 'application/src/hyprn_mvp_app/history.py',
         'application/src/hyprn_mvp_app/modified_runs.py', 'ui/src/UnitEditor.tsx',
         'ui/src/unitLabels.ts', 'contracts/schemas/model.schema.json', 'contracts/schemas/execution.schema.json'),
        ('upstream/whatsopt-patches/080-unit-declarations.patch', 'modeling/generate_unit_catalog.py',
         'contracts/schemas/model.schema.json', 'contracts/schemas/execution.schema.json'),
        SOURCE_PATHS,
    )
    for inventory, paths in zip(inventories, required):
        for path in paths:
            assert inventory[path] == hashlib.sha256((REPO/path).read_bytes()).hexdigest()
    # Every reviewed patch, including the quantity-definitions patch, is bound by the native
    # and the execution inventories alike.
    assert inventories[1]['upstream/whatsopt-patches/090-quantity-definitions.patch'] == hashlib.sha256(
        (REPO/'upstream/whatsopt-patches/090-quantity-definitions.patch').read_bytes()).hexdigest()
    assert inventories[2]['upstream/whatsopt-patches/090-quantity-definitions.patch'] == inventories[1]['upstream/whatsopt-patches/090-quantity-definitions.patch']
    # The execution inventory is exactly the launch closure: modules unreachable from every
    # launch path (execution, modeling, result_bindings, store) are never bound.
    assert len(inventories[2]) == 36
    for removed in ('execution', 'modeling', 'result_bindings', 'store'):
        assert f'application/src/hyprn_mvp_app/{removed}.py' not in inventories[2]


def test_units_attestation_imports_the_worker_package_as_the_worker_user(attested):
    scope, runtime, evidence = attested
    package = REPO / 'integration/src/hyprn_mvp_integration/__init__.py'
    assert evidence['cases']['worker_import']['exit_code'] == 0
    assert evidence['worker_import'] == {
        'package': hashlib.sha256(package.read_bytes()).hexdigest(),
        'worker': runtime['worker_sha256'],
        'results': runtime['results_sha256'],
    }


def test_units_attestation_refuses_a_worker_that_cannot_read_its_own_code(attested, monkeypatch):
    """Package files only root can read (a umask-077 build without explicit modes) pass every
    resource canary; the worker-user import probe alone refuses them. Runs last: it retags the
    scope's worker image, then restores the scope's runtime and attestation records."""
    scope, _, evidence = attested
    records = [scope.root / 'runtime.json', scope.root / 'evidence/containment.json']
    before = [path.read_bytes() for path in records]

    class RootOnly(type(Path())):
        def chmod(self, mode, *args, **kwargs):
            return super().chmod(0o400 if mode == 0o444 else mode, *args, **kwargs)

    monkeypatch.setattr(worker, 'Path', RootOnly)
    try:
        worker.build_worker(root=scope.root)
        with pytest.raises(RuntimeError, match='Containment failed'):
            launcher.attest(root=scope.root)
        failed = json.loads(records[1].read_bytes())
        cases = failed['cases']
        assert not failed['passed'] and failed['worker_import'] == {}
        assert cases['worker_import']['exit_code'] != 0
        assert 'PermissionError' in cases['worker_import']['output']
        assert all(cases[name]['exit_code'] == 0 for name in ('access', 'file_bound', 'pids'))
    finally:
        for path, raw in zip(records, before):
            path.write_bytes(raw)
    assert launcher.require_attestation(root=scope.root) == evidence
