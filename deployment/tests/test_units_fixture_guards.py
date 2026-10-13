"""Closed units routing and real isolation refusals; no candidate execution."""
# P2 live-runtime fence (deployment/tests/live_fence.py): refuses live roots, live ports, live docker names, live entry points and foreign signals.
import sys as _fence_sys
from pathlib import Path as _FencePath
if str(_FencePath(__file__).resolve().parent) not in _fence_sys.path:
    _fence_sys.path.append(str(_FencePath(__file__).resolve().parent))
import live_fence  # noqa: E402
setUpModule, tearDownModule = live_fence.unittest_module_hooks('baseline')
from dataclasses import replace
import builtins
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from uuid import uuid4

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
import scoped_fixture as fixture
import checks as runner


class UnitsGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scope = fixture.scope_from_environment()

    def test_mixed_repair_selection_is_fixed_and_default_targets_preserved(self):
        expected = (
            'deployment/tests/test_units_native.py::test_native_mixed_legacy_selected_repair',
            'deployment/tests/test_units_native.py::test_http_fixture_response_disconnect_boundary',
        )
        self.assertEqual(runner.targets_for('units-native', units_mixed_repair=True), expected)
        self.assertEqual(runner.targets_for('units-native'), runner.GROUPS['units-native'])
        with self.assertRaisesRegex(ValueError, 'Required target missing'):
            runner.targets_for('units-native', units_mixed_repair=True, repo=self.scope.root/'tmp/absent')

    def test_effective_native_collections_are_disjoint_data_only(self):
        import ast
        from types import SimpleNamespace
        source = runner.REPO / 'deployment/tests/test_units_native.py'
        tree = ast.parse(source.read_text())
        # Copy declarations only: never import or execute native fixtures/bodies.
        declarations = ['import pytest']
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef) or not node.name.startswith('test_'):
                continue
            for mark in node.decorator_list:
                self.assertIsInstance(mark, ast.Call)
                self.assertEqual(ast.unparse(mark.func), 'pytest.mark.parametrize')
                self.assertIsInstance(mark.args[1], ast.List)
                declarations.append('@pytest.mark.parametrize(' + repr(ast.literal_eval(mark.args[0]))
                                    + ', ' + repr(list(range(len(mark.args[1].elts)))) + ')')
            declarations.append('def ' + node.name + '(' + ast.unparse(node.args) + '): pass')
        collection = fixture.scoped_path(self.scope, 'tmp/collection-' + str(uuid4()))
        inert = collection / 'deployment/tests/test_units_native.py'
        inert.parent.mkdir(parents=True)
        inert.write_text('\n'.join(declarations) + '\n')
        # The fixture module is a target too, but contains no test declarations.
        (inert.parent / 'units_native_fixture.py').write_text('')
        all_nodes = {}
        for mixed, expected_count in ((False, 14), (True, 5)):
            captured = []
            fake_pytest = SimpleNamespace(main=lambda args, **kw: captured.extend(args) or 5)
            with patch.dict(sys.modules, {'pytest': fake_pytest}), patch.object(sys, 'path', list(sys.path)), patch.dict(os.environ), patch.object(fixture, 'scope_from_environment', return_value=self.scope), patch.object(fixture, 'create_native_fixture', return_value=(self.scope, None)) as native, patch.object(runner, 'PROJECTION_SCOPE'), patch.object(runner, 'NATIVE_BACKEND'), patch.object(Path, 'write_text'):
                self.assertEqual(runner.contracts_child('units-native', units_mixed_repair=mixed), 1)
                native.assert_called_once_with(self.scope)
            # Use the exact trusted child's argv against inert declarations.
            env = fixture.clean_environment(self.scope)
            env['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
            result = runner.subprocess.run([self.scope.interpreter, '-B', '-m', 'pytest',
                *captured, '--collect-only'], cwd=collection, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            nodes = [line for line in result.stdout.splitlines() if line.startswith('deployment/tests/') and '::' in line]
            self.assertEqual(len(nodes), expected_count, result.stdout)
            all_nodes[str(mixed)] = nodes
            names = {line.split('::')[1].split('[')[0] for line in nodes}
            if mixed:
                self.assertEqual(names, {'test_native_mixed_legacy_selected_repair', 'test_http_fixture_response_disconnect_boundary'})
            else:
                self.assertEqual(names, {'test_native_compounds_histories_and_archive', 'test_actual_private_scope_and_inert_import', 'test_malicious_and_affine_rejected_atomically', 'test_http_fixture_response_disconnect_boundary'})
        fixture.scoped_path(self.scope, 'evidence/effective-native-collection.json').write_text(json.dumps(all_nodes, indent=2))
        self.assertNotIn('test_units_native', sys.modules)
        self.assertNotIn('units_native_fixture', sys.modules)

    def test_narrow_unit_expectation_uses_first_retained_output(self):
        import re
        source = (runner.REPO / 'ui/tests/unit-native-journey.spec.ts').read_text()
        match = re.search(r'const expectedUnit=([^;]+);', source)
        self.assertIsNotNone(match, 'Narrow check must derive its expected unit from retained output')
        self.assertIn('toHaveText(expectedUnit)', source)
        families = json.loads((runner.REPO / 'integration/tests/fixtures/units-native-evidence.json').read_text())['families']
        expressions = [families[0]['source'], families[0]['destination'], 'N', '']
        fixtures = [{'records': [{'detail': {'history': {'results': {'outputs': [{'units': unit}, {'units': 'wrong second output'}]}}}}, {'detail': {'history': {'results': {'outputs': [{'units': 'wrong second record'}]}}}}]} for unit in expressions]
        script = 'const fixtures=JSON.parse(process.argv[1]); console.log(JSON.stringify(fixtures.map(f => (' + match.group(1) + '))));'
        result = runner.subprocess.run(['node', '-e', script, json.dumps(fixtures)],
            env=fixture.clean_environment(self.scope), capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), ['MJ/kg', 'J/kg', 'N', 'dimensionless'])
        fixture.scoped_path(self.scope, 'evidence/retained-unit-expectations.json').write_text(result.stdout)

    def test_mixed_repair_wrong_groups_refuse_before_scope_import_or_write(self):
        for group in set(runner.GROUPS) - {'units-native'}:
            with self.subTest(group=group), patch.object(fixture, 'allocate_scope') as allocate, patch.object(fixture, 'scope_from_environment') as scope, patch.object(fixture, 'create_native_fixture') as native:
                with self.assertRaisesRegex(ValueError, 'units-native'):
                    runner.run_group(group, units_mixed_repair=True)
                with self.assertRaisesRegex(ValueError, 'units-native'):
                    runner.contracts_child(group, units_mixed_repair=True)
                allocate.assert_not_called();scope.assert_not_called();native.assert_not_called()

    def test_mixed_repair_child_preserves_interpreter_and_scope_guards(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(fixture, 'create_native_fixture') as native:
            with self.assertRaises(ValueError):
                runner.contracts_child('units-native', units_mixed_repair=True)
            native.assert_not_called()
        with patch.object(fixture, 'scope_from_environment', return_value=self.scope), patch.object(sys, 'executable', '/usr/bin/python3'), patch.object(fixture, 'create_native_fixture') as native:
            with self.assertRaisesRegex(ValueError, 'reviewed interpreter'):
                runner.contracts_child('units-native', units_mixed_repair=True)
            native.assert_not_called()

    def test_mixed_missing_or_skipped_function_refused_before_allocation(self):
        repo = fixture.scoped_path(self.scope, 'tmp/mixed-targets-' + str(uuid4()))
        path = repo / 'deployment/tests/test_units_native.py'
        path.parent.mkdir(parents=True)
        bodies = (
            'def different(): pass',
            '@pytest.mark.skip(reason="fixture")\ndef test_native_mixed_legacy_selected_repair(): pass',
            'pytestmark = pytest.mark.skipif(False, reason="fixture")\ndef test_native_mixed_legacy_selected_repair(): pass',
        )
        original = runner.targets_for
        for body in bodies:
            path.write_text(body + '\ndef test_http_fixture_response_disconnect_boundary(): pass\n')
            with patch.object(runner, 'targets_for', side_effect=lambda group, **kw: original(group, repo=repo, **kw)), patch.object(fixture, 'allocate_scope') as allocate, patch.object(runner.subprocess, 'run') as launch:
                with self.assertRaisesRegex(ValueError, 'Required test (missing|skipped)'):
                    runner.run_group('units-native', units_mixed_repair=True)
                allocate.assert_not_called(); launch.assert_not_called()

    def test_mixed_exact_child_argv_and_clean_environment(self):
        from types import SimpleNamespace
        scope = fixture.allocate_scope(fixture.new_scope())
        with patch.object(fixture, 'new_scope', return_value=scope), patch.object(fixture, 'allocate_scope', return_value=scope), patch.object(runner, 'require_environment'), patch.object(runner.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout='', stderr='')) as launch:
            self.assertEqual(runner.run_group('units-native', units_mixed_repair=True), 0)
        args, kwargs = launch.call_args
        self.assertEqual(args[0], [fixture.APPROVED_PYTHON, '-B', str(Path(runner.__file__).resolve()), '--units-native-child', '--units-mixed-repair'])
        self.assertEqual(kwargs['env'], fixture.clean_environment(scope))
        self.assertEqual(kwargs['cwd'], runner.REPO)

    def test_mixed_incomplete_skipped_failed_or_foreign_collection_cannot_pass(self):
        from types import SimpleNamespace
        def result(passed=5, failed=0, skipped=0):
            return SimpleNamespace(passed=passed, failed=failed, skipped=skipped)
        self.assertTrue(runner.pytest_qualification_passed(0, result(), [], mixed=True))
        for status, counts, imports in ((0,result(0),[]),(0,result(4),[]),(0,result(6),[]),(0,result(skipped=1),[]),(0,result(failed=1),[]),(5,result(),[]),(0,result(),['openmdao'])):
            self.assertFalse(runner.pytest_qualification_passed(status,counts,imports,mixed=True))
        self.assertTrue(runner.pytest_qualification_passed(0,result(10),[],mixed=False))

    def test_mixed_illegal_cli_combinations_refuse_without_native_setup(self):
        for argv in (['--group','units-guards','--units-mixed-repair'], ['--units-worker-child','--units-mixed-repair']):
            with patch.object(sys,'argv',['checks.py',*argv]), patch.object(fixture,'allocate_scope') as allocate, patch.object(fixture,'create_native_fixture') as native:
                self.assertNotEqual(runner.main(),0)
                allocate.assert_not_called();native.assert_not_called()

    def test_units_routes_are_closed_and_match_plan_commands(self):
        expected = {
            'units-guards', 'units-contracts', 'units-staging', 'units-model',
            'units-api', 'units-public-types', 'units-resolution', 'units-configuration',
            'units-bundle', 'units-history', 'units-launcher', 'units-worker',
            'units-attestation', 'units-native',
            'units-ui-authoring', 'units-ui-configuration', 'units-ui-reading', 'units-ui-history',
        }
        self.assertEqual({g for g in runner.GROUPS if g.startswith('units-')}, expected)
        self.assertEqual(runner.UNITS_PYTEST_GROUPS | set(runner.UNITS_BROWSER_GROUPS), expected)
        with patch.object(fixture, 'allocate_scope') as allocate:
            with self.assertRaises(ValueError):
                runner.run_group('units-arbitrary')
            allocate.assert_not_called()

    def test_units_missing_targets_refuse_before_allocation_or_launch(self):
        for group in runner.UNITS_PYTEST_GROUPS | set(runner.UNITS_BROWSER_GROUPS):
            with self.subTest(group=group):
                with self.assertRaisesRegex(ValueError, 'Required target missing'):
                    runner.targets_for(group, repo=self.scope.root / 'tmp/absent')
                with patch.object(runner, 'targets_for', side_effect=ValueError('missing')), patch.object(fixture, 'allocate_scope') as allocate, patch.object(runner.subprocess, 'run') as run:
                    with self.assertRaises(ValueError):
                        runner.run_group(group)
                    allocate.assert_not_called()
                    run.assert_not_called()

    def test_units_symlink_target_refused(self):
        repo = fixture.scoped_path(self.scope, 'tmp/targets-' + str(uuid4()))
        path = repo / 'contracts/tests/test_unit_declaration_contracts.py'
        path.parent.mkdir(parents=True)
        path.symlink_to(Path(__file__))
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            runner.targets_for('units-contracts', repo=repo)

    def test_units_privileges_and_interpreters_are_bounded(self):
        self.assertEqual(runner.UNITS_NATIVE_GROUPS, {
            'units-history', 'units-launcher', 'units-worker', 'units-attestation', 'units-native',
        })
        for group in runner.UNITS_APP_GROUPS | set(runner.UNITS_BROWSER_GROUPS):
            self.assertEqual(runner.GROUP_INTERPRETERS[group], fixture.APPROVED_CONTRACT_PYTHON)
        for group in runner.UNITS_NATIVE_GROUPS | {'units-model', 'units-guards', 'units-staging', 'units-contracts'}:
            self.assertEqual(runner.GROUP_INTERPRETERS.get(group, fixture.APPROVED_PYTHON), fixture.APPROVED_PYTHON)
        for group in runner.UNITS_BROWSER_GROUPS:
            self.assertEqual(runner.GROUPS[group][0], 'deployment/tests/units_ui_fixture.py')
            self.assertTrue(runner.UNITS_BROWSER_GROUPS[group].startswith('@units-'))
        self.assertEqual(runner.UNITS_SELECTIONS['units-staging'], ['-k', 'test_units_staging_'])
        self.assertEqual(runner.UNITS_SELECTIONS['units-public-types'], ['-k', 'test_generated_'])

    def assert_children_refuse(self, env):
        # Use actual malformed scope/environment validation, with import and write
        # tripwires. No test module, browser fixture or native backend may load.
        original_import = builtins.__import__
        imports = []
        def guarded_import(name, *args, **kwargs):
            if name.split('.')[0] in {'pytest', 'aiida', 'openmdao', 'openturns', 'units_ui_fixture'}:
                imports.append(name)
                raise AssertionError('Unsafe child reached an import')
            return original_import(name, *args, **kwargs)
        with patch.dict(os.environ, env, clear=True), patch.object(builtins, '__import__', side_effect=guarded_import), patch.object(fixture, 'create_native_fixture') as native, patch.object(runner, 'targets_for') as targets, patch.object(Path, 'write_text', side_effect=AssertionError('Write reached')) as write:
            for group in runner.UNITS_PYTEST_GROUPS:
                with self.subTest(group=group), self.assertRaises(ValueError):
                    runner.contracts_child(group)
            for group in runner.UNITS_BROWSER_GROUPS:
                with self.subTest(group=group), self.assertRaises(ValueError):
                    runner.units_browser_child(group)
            targets.assert_not_called()
            native.assert_not_called()
            write.assert_not_called()
        self.assertEqual(imports, [])

    def test_units_children_refuse_live_default_shared_and_foreign_environment(self):
        good = fixture.clean_environment(self.scope)
        for env in (
            {},
            {**good, 'HYPRN_MVP_TEST_SCOPE_ROOT': str(fixture.local_paths.execution_root())},
            {**good, 'HYPRN_MVP_TEST_SCOPE_ROOT': '/private/tmp'},
            {**good, 'HYPRN_MVP_TEST_SCOPE_ROOT': str(fixture.SCRATCH_ROOT)},
            {**good, 'HYPRN_MVP_SCRATCH_ROOT': str(self.scope.root / 'tmp')},
            {**good, 'HYPRN_MVP_TEST_SCOPE_PROFILE': 'default'},
            {**good, 'AIIDA_PATH': '/foreign'},
            {**good, 'HOME': str(fixture.local_paths.account_home())},
            {**good, 'PYTHONPATH': '/foreign'},
            {**good, 'OPENAI_API_KEY': 'synthetic'},
        ):
            self.assert_children_refuse(env)

    def test_units_children_refuse_foreign_marker_identity(self):
        scope = fixture.allocate_scope(fixture.new_scope())
        env = fixture.clean_environment(scope)
        marker = scope.root / 'scope.json'
        data = json.loads(marker.read_text())
        data['store_uuid'] = data['profile_uuid']
        marker.write_text(json.dumps(data))
        self.assert_children_refuse(env)

    def test_units_children_refuse_default_and_foreign_native_storage(self):
        scope = fixture.allocate_scope(fixture.new_scope())
        env = fixture.clean_environment(scope)
        directory = scope.root / 'aiida/.aiida'
        directory.mkdir()
        config = directory / 'config.json'
        for record in (
            {'default_profile': scope.profile, 'profiles': {}},
            {'default_profile': None, 'profiles': {scope.profile: {
                'PROFILE_UUID': scope.profile_uuid,
                'storage': {'backend': scope.backend, 'config': {'filepath': '/foreign'}},
            }}},
        ):
            config.write_text(json.dumps(record))
            self.assert_children_refuse(env)

    def test_units_children_refuse_symlink_root_and_directory(self):
        scope = fixture.allocate_scope(fixture.new_scope())
        env = fixture.clean_environment(scope)
        link = fixture.SCRATCH_ROOT / (fixture.SCOPE_PREFIX + str(uuid4()))
        link.symlink_to(scope.root, target_is_directory=True)
        try:
            self.assert_children_refuse({**env, 'HYPRN_MVP_TEST_SCOPE_ROOT': str(link)})
        finally:
            link.unlink()
        (scope.root / 'home').rmdir()
        (scope.root / 'home').symlink_to('/private/tmp', target_is_directory=True)
        self.assert_children_refuse(env)

    def test_units_wrong_interpreter_refused_before_collection(self):
        for group in runner.UNITS_PYTEST_GROUPS | set(runner.UNITS_BROWSER_GROUPS):
            with patch.object(fixture, 'scope_from_environment', return_value=self.scope), patch.object(sys, 'executable', '/usr/bin/python3'), patch.object(runner, 'targets_for') as targets:
                with self.subTest(group=group), self.assertRaisesRegex(ValueError, 'reviewed interpreter'):
                    if group in runner.UNITS_BROWSER_GROUPS:
                        runner.units_browser_child(group)
                    else:
                        runner.contracts_child(group)
                targets.assert_not_called()

    def test_units_existing_scope_cannot_be_shared(self):
        marker = (self.scope.root / 'scope.json').read_bytes()
        with patch.object(Path, 'mkdir', side_effect=AssertionError('Write reached')) as write:
            with self.assertRaisesRegex(ValueError, 'existing fixture root'):
                fixture.allocate_scope(self.scope)
            write.assert_not_called()
        self.assertEqual((self.scope.root / 'scope.json').read_bytes(), marker)

    def test_units_empty_or_skipped_suites_never_pass(self):
        result = unittest.TestResult()
        self.assertFalse(runner.successful(result))
        result.testsRun = 1
        result.skipped = [('synthetic', 'unimplemented')]
        self.assertFalse(runner.successful(result))

    def test_fixture_launch_worker_runs_this_trees_launcher_not_an_ambient_checkout(self):
        """Native fixtures execute this tree's launcher, never a checkout that an interpreter's
        startup path hook names (a bare `-m` launcher run from a worktree or a release copy would
        import that checkout's launcher). The case plants such a hook itself, whether or not the
        development interpreter carries one: a synthetic site folder whose .pth names a decoy
        checkout with the same package names. A bare start then reaches the decoy (the hook is
        effective), while the fixture launcher started under the same hook resolves every project
        module in this tree and drops the decoy roots from its path."""
        import hashlib
        import subprocess
        tree = Path(fixture.__file__).resolve().parents[2]
        expected = tree / 'integration/src/hyprn_mvp_integration/launcher.py'
        env = fixture.clean_environment(self.scope)
        cwd = self.scope.root / 'tmp'
        decoy = fixture.scoped_path(self.scope, 'tmp/decoy-checkout-' + uuid4().hex)
        for relative, text in (('integration/src/hyprn_mvp_integration/__init__.py', ''),
                               ('integration/src/hyprn_mvp_integration/launcher.py', 'raise SystemExit("decoy launcher ran")\n'),
                               ('application/src/hyprn_mvp_app/__init__.py', '')):
            (decoy / relative).parent.mkdir(parents=True, exist_ok=True)
            (decoy / relative).write_text(text)
        decoy_roots = [decoy / 'integration/src', decoy / 'application/src']
        site = fixture.scoped_path(self.scope, 'tmp/startup-site-' + uuid4().hex)
        site.mkdir()
        (site / 'decoy-checkout.pth').write_text(''.join(str(r) + '\n' for r in decoy_roots))
        # Processes the site folder exactly as interpreter startup processes site-packages.
        hook = 'import runpy,site,sys;site.addsitedir(sys.argv[1]);sys.argv=sys.argv[2:];'
        bare = subprocess.run([fixture.APPROVED_PYTHON, '-B', '-c', hook + (
            'import importlib.util;print(importlib.util.find_spec("hyprn_mvp_integration.launcher").origin)'),
            str(site), '-'], cwd=cwd, env=env, capture_output=True, text=True)
        self.assertEqual(bare.returncode, 0, bare.stderr)
        self.assertEqual(Path(bare.stdout.strip()).resolve(), (decoy_roots[0] / 'hyprn_mvp_integration/launcher.py').resolve())
        command = fixture.launcher_command(self.scope, check_only=True)
        self.assertEqual(command[:2], ['/usr/bin/env', '-i'])
        self.assertIn(fixture.APPROVED_PYTHON, command)
        self.assertNotIn('-m', command)
        entry = command.index(fixture.APPROVED_PYTHON) + 2
        self.assertTrue(command[entry].endswith('scoped_fixture_launcher.py'))
        hooked = [*command[:entry], '-c', hook + 'runpy.run_path(sys.argv[0],run_name="__main__")', str(site),
                  *command[entry:]]
        for argv, hooked_start in ((hooked, True), (command, False)):
            with self.subTest(hooked=hooked_start):
                result = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                record = json.loads(result.stdout)
                self.assertEqual(Path(record['modules']['hyprn_mvp_integration.launcher']['file']), expected)
                self.assertEqual(record['modules']['hyprn_mvp_integration.launcher']['sha256'],
                                 hashlib.sha256(expected.read_bytes()).hexdigest())
                self.assertTrue(Path(record['modules']['hyprn_mvp_app']['file']).is_relative_to(tree / 'application/src'))
                self.assertEqual(record['tree'], str(tree))
                # No path entry that holds a project package belongs to another checkout.
                for entry_path in map(Path, record['sys_path']):
                    if any((entry_path / name).is_dir() for name in ('hyprn_mvp_integration', 'hyprn_mvp_app')):
                        self.assertTrue(entry_path.resolve().is_relative_to(tree), entry_path)
                if hooked_start:
                    removed = {Path(p).resolve() for p in record['removed_sys_path']}
                    self.assertTrue({r.resolve() for r in decoy_roots} <= removed, record['removed_sys_path'])
        # The wrapper written by prepare_worker_fixture execs exactly this command.
        wrapper = fixture.worker_wrapper_text(self.scope)
        self.assertTrue(wrapper.startswith('#!/bin/sh\nexec '))
        self.assertTrue(wrapper.endswith(' "$@"\n'))
        self.assertIn('scoped_fixture_launcher.py', wrapper)
        self.assertNotIn(' -m ', wrapper)






class UnitsStagingTests(unittest.TestCase):
    def setUp(self):
        import modeling_runtime
        self.runtime = modeling_runtime
        self.scope = fixture.validate_scope(runner.PROJECTION_SCOPE)
        self.stage = fixture.scoped_path(self.scope, 'tmp/staging-' + str(uuid4()))
        self.stage.mkdir()

    def trusted_python(self, code):
        import subprocess
        fixture.validate_scope(self.scope)
        image=json.loads((self.runtime.REPO/'deployment/pins.json').read_text())['worker_image']
        command=['docker','run','--pull','never','--rm','-i','--network','none','--read-only',
            '--cap-drop','ALL','--security-opt','no-new-privileges','--user','10001:10001',
            '--memory','512m','--cpus','1','--pids-limit','32',
            '--tmpfs','/tmp:rw,noexec,nosuid,size=32m,mode=1777',
            '-e','HOME=/tmp','-e','OPENMDAO_REPORTS=0','--entrypoint','python',image,'-B','-']
        result=subprocess.run(command,input=code,capture_output=True,text=True,timeout=30,env=fixture.clean_environment(self.scope))
        label=str(uuid4())
        (self.stage/(label+'.py')).write_text(code)
        (self.stage/(label+'.log')).write_text(result.stdout+result.stderr)
        (self.stage/(label+'.command.json')).write_text(json.dumps(command))
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        return result

    def addition(self, patch_name, path):
        raw = (self.runtime.REPO / 'upstream/whatsopt-patches' / patch_name).read_text()
        section = raw.split('+++ b/' + path + '\n', 1)[1].split('\n--- ', 1)[0]
        return '\n'.join(line[1:] for line in section.splitlines()[1:] if line.startswith('+')) + '\n'

    def apply(self, raw):
        import subprocess
        result = subprocess.run(['patch', '--batch', '--fuzz=0', '-p1'], cwd=self.stage, input=raw, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn('fuzz', result.stdout.lower())
        self.assertNotIn('offset', result.stdout.lower())

    def native_base(self):
        for name in ('native_materializer', 'native_program'):
            path = 'app/services/' + name + '.rb'
            target = self.stage / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(self.addition('050-native-generation.patch', path))
        target = self.stage / 'config/modeling.units.json'
        target.parent.mkdir(parents=True)
        target.write_text(self.addition('040-modeling-contract.patch', 'config/modeling.units.json'))
        self.apply(self.runtime.stage_assumptions_native_patch(self.stage).read_text())

    def test_units_staging_generator_pinned_catalog_and_factors(self):
        import subprocess, hashlib
        result = self.trusted_python((self.runtime.REPO / 'modeling/generate_unit_catalog.py').read_text())
        catalog = json.loads(result.stdout)
        self.assertEqual(catalog['version'], '3.45.1')
        self.assertEqual(len(catalog['supported_units']), 29)
        self.assertEqual(len(set(catalog['supported_units'])), 29)
        body = {k:v for k,v in catalog.items() if k != 'catalog_digest'}
        self.assertEqual(catalog['catalog_digest'], hashlib.sha256(json.dumps(body, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest())
        probe = """
import hashlib, inspect, json
from pathlib import Path
import openmdao
from openmdao.utils import units
names=['','m','km','cm','mm','s','min','h','kg','g','N','Pa','kPa','MPa','K','degC','degF','rad','deg','m/s','km/h','J/kg','kJ/kg','MJ/kg','kg/m**3','g/cm**3','m**2','cm**2','mm**2']
pairs=[]
for a in names:
    for b in names:
        if not a or not b:
            if a == b: pairs.append([a,b,1.0,0.0])
            continue
        try: factor,offset=units.unit_conversion(a,b)
        except (TypeError,ValueError): continue
        if offset == 0: pairs.append([a,b,factor,offset])
print(json.dumps(dict(version=openmdao.__version__,names=names,pairs=pairs,source=hashlib.sha256(Path(inspect.getfile(units)).read_bytes()).hexdigest())))
"""
        checked = self.trusted_python(probe)
        trusted=json.loads(checked.stdout)
        self.assertEqual(trusted['version'], '3.45.1')
        self.assertEqual(catalog['source_sha256'], trusted['source'])
        self.assertEqual(catalog['supported_units'], trusted['names'])
        expected=trusted['pairs']
        self.assertEqual(catalog['linear_pairs'], expected)
        pairs={(a,b):factor for a,b,factor,offset in expected}
        for pair,value in {( 'MJ/kg','J/kg'):1e6, ('g/cm**3','kg/m**3'):1000, ('cm**2','m**2'):1e-4, ('mm**2','m**2'):1e-6}.items():
            self.assertAlmostEqual(pairs[pair], value)
        self.assertNotIn(('degC','K'), pairs)
        self.assertEqual(pairs['degC','degC'],1)
        self.native_base()
        self.apply(self.runtime.stage_units_native_patch(self.stage).read_text())
        self.assertEqual((self.stage/'config/modeling.units.json').read_text(), result.stdout)

    def test_units_staging_both_routes_and_inventory(self):
        self.native_base()
        adapter=self.runtime.stage_modeling_contract(self.stage).read_text()
        units=self.runtime.stage_units_native_patch(self.stage).read_text()
        self.apply(units)
        native=(self.stage/'app/services/native_materializer.rb').read_text()
        program=(self.stage/'app/services/native_program.rb').read_text()
        self.assertIn('validator.require_resolved_units!(model)', native)
        self.assertLess(native.index('validator.require_resolved_units!'),native.index('Analysis.create!'))
        self.assertIn("validator.unit_expression(port.fetch('units'))",native)
        self.assertIn("validator.unit_expression(port.fetch('units'))",program)
        self.assertIn('WhatsOpt::OpenmdaoGenerator.new(analysis,static_only:true',native)
        self.assertIn("bindings={'schema_version'=>'1'",native)
        self.assertIn('def unit_readiness',adapter)
        hashes=self.runtime.source_hashes()
        self.assertIn('modeling/generate_unit_catalog.py',hashes)
        self.assertIn('upstream/whatsopt-patches/080-unit-declarations.patch',hashes)
        complete=self.stage/'complete'; complete.mkdir()
        self.runtime.stage_native_inputs(complete)
        self.assertEqual((complete/'modeling_contract.rb').read_text(),adapter)
        self.assertEqual((complete/'units.patch').read_text(),units)
        for name in ('modeling/generate_unit_catalog.py','modeling/provenance.md'):
            self.assertEqual((complete/'provenance-inputs/support'/Path(name).name).read_bytes(),(self.runtime.REPO/name).read_bytes())
        self.assertEqual((complete/'provenance-inputs/patches/080-unit-declarations.patch').read_bytes(),(self.runtime.REPO/'upstream/whatsopt-patches/080-unit-declarations.patch').read_bytes())
        # Replay the full 080 on the exact pre-080 adapter and native baseline.
        target=self.stage/'app/services/modeling_contract.rb'
        target.write_text(adapter)
        import subprocess
        quantity=(self.runtime.REPO/'upstream/whatsopt-patches/090-quantity-definitions.patch').read_text()
        reverse090=subprocess.run(['patch','--batch','--fuzz=0','-R','-p1'],cwd=self.stage,input=quantity,capture_output=True,text=True)
        self.assertEqual(reverse090.returncode,0,reverse090.stdout+reverse090.stderr)
        baseline080=target.read_text()
        native_before={str(p.relative_to(self.stage)):p.read_bytes() for p in (self.stage/'app/services/native_materializer.rb',self.stage/'app/services/native_program.rb',self.stage/'config/modeling.units.json')}
        raw=(self.runtime.REPO/'upstream/whatsopt-patches/080-unit-declarations.patch').read_text()
        import subprocess
        reverse=subprocess.run(['patch','--batch','--fuzz=0','-R','-p1'],cwd=self.stage,
            input=raw,capture_output=True,text=True)
        self.assertEqual(reverse.returncode,0,reverse.stdout+reverse.stderr)
        self.apply(raw)
        self.assertEqual(target.read_text(),baseline080)
        self.apply(quantity)
        self.assertEqual(target.read_text(),adapter)
        self.assertEqual(native_before,{name:(self.stage/name).read_bytes() for name in native_before})
        self.assertEqual((complete/'provenance-inputs/patches/090-quantity-definitions.patch').read_text(),quantity)

        recipe=(self.runtime.REPO/'deployment/modeling.Dockerfile').read_text()
        self.assertLess(recipe.index('COPY assumptions.patch'),recipe.index('COPY units.patch'))
        self.assertIn('patch --batch --fuzz=0 -p1 < /tmp/units.patch',recipe)
        import subprocess
        repeated=subprocess.run(['patch','--batch','--fuzz=0','--forward','-p1'],cwd=self.stage,input=units,capture_output=True,text=True)
        self.assertNotEqual(repeated.returncode,0)

    def test_units_staging_quantity_patch_required_once_and_adapter_only(self):
        import shutil
        original=self.runtime.REPO
        repo=self.stage/'repo'; shutil.copytree(original/'upstream/whatsopt-patches',repo/'upstream/whatsopt-patches')
        quantity=repo/'upstream/whatsopt-patches/090-quantity-definitions.patch'
        self.assertTrue(quantity.is_file(), 'Production quantity patch is missing')
        raw=quantity.read_text()
        stage=self.stage/'valid';stage.mkdir()
        adapter=self.runtime.stage_modeling_contract(stage).read_text()
        self.assertEqual(adapter.count("when 'set_quantity_definition','clear_quantity_definition'"),1)
        for index,modified in enumerate((None,raw+raw,raw+'\n--- a/app/services/native_program.rb\n+++ b/app/services/native_program.rb\n@@ -1 +1 @@\n-x\n+y\n',raw.replace('--- a/app/services/modeling_contract.rb','--- a/app/lib/whats_opt/openmdao_generator.rb'))):
            target=self.stage/('bad-'+str(index));target.mkdir()
            if modified is None:quantity.unlink()
            else:quantity.write_text(modified)
            with patch.object(self.runtime,'REPO',repo),self.assertRaises((ValueError,FileNotFoundError)):
                self.runtime.stage_modeling_contract(target)
            self.assertFalse((target/'modeling_contract.rb').exists())
        quantity.write_text(raw)
        # Swapping the ordered patch bytes must fail, never fuzz or auto-reverse.
        units=repo/'upstream/whatsopt-patches/080-unit-declarations.patch'
        quantity.write_bytes(units.read_bytes());units.write_text(raw)
        target=self.stage/'reordered';target.mkdir()
        with patch.object(self.runtime,'REPO',repo),self.assertRaises(ValueError):
            self.runtime.stage_modeling_contract(target)

    def test_units_staging_refuses_unexpected_sections(self):
        repo=self.stage/'repo'; folder=repo/'upstream/whatsopt-patches';folder.mkdir(parents=True)
        original=self.runtime.REPO/'upstream/whatsopt-patches/080-unit-declarations.patch'
        self.assertTrue(original.is_file())
        for suffix in ('\n--- a/foreign.rb\n+++ b/foreign.rb\n@@ -1 +1 @@\n-x\n+y\n', '\n--- a/app/services/modeling_contract.rb\n+++ b/app/services/modeling_contract.rb\n@@ -1 +1 @@\n-x\n+y\n'):
            (folder/original.name).write_text(original.read_text()+suffix)
            with patch.object(self.runtime,'REPO',repo), self.assertRaises(ValueError):
                self.runtime.stage_units_native_patch(self.stage)

    def test_units_staging_active_occurrences_and_retained_shapes(self):
        import subprocess
        self.native_base()
        service=self.runtime.stage_modeling_contract(self.stage)
        self.apply(self.runtime.stage_units_native_patch(self.stage).read_text())
        (self.stage/'config/modeling.schema.json').write_bytes((self.runtime.REPO/'contracts/schemas/model.schema.json').read_bytes())
        # Load the actual cumulative Ruby adapter in a confined, data-only process.
        # No Rails boot, database, native generator or Python candidate is needed.
        code = r"""
require 'pathname'
require 'json'
module Rails
  def self.root = Pathname.new('/fixture')
end
load '/fixture/modeling_contract.rb'
c=ModelingContract.new({'study_id'=>'fixture'})
def copy(value) = Marshal.load(Marshal.dump(value))
def reject
  begin
    yield
  rescue ModelingContract::Failure
    return
  end
  raise 'Expected refusal'
end
v1={'definition_version_id'=>'v1','ports'=>[{'port_id'=>'shared','units'=>{'kind'=>'unspecified'}}]}
v2={'definition_version_id'=>'v2','ports'=>[{'port_id'=>'shared','units'=>{'kind'=>'physical','expression'=>'MJ/kg'}}]}
legacy={'definition_version_id'=>'legacy','ports'=>[{'port_id'=>'shared','units'=>''}]}
m={'definitions'=>[v1,v2,legacy], 'instances'=>[{'instance_id'=>'a','definition_version_id'=>'v2'}]}
before=copy(m)
raise 'Unused history blocks' unless c.unit_readiness(m).empty?
c.require_resolved_units!(m)
raise 'Mutated original' unless m==before
m['instances'][0]['definition_version_id']='v1'
issues=c.unit_readiness(m)
raise 'Wrong occurrence' unless issues.size==1 && issues[0]['code']=='unit_unspecified' && issues[0]['path'].include?('a') && issues[0]['path'].include?('v1') && issues[0]['path'].include?('shared')
reject { c.require_resolved_units!(m) }
m['instances'][0]['definition_version_id']='v2'
m['instances'] << {'instance_id'=>'b','definition_version_id'=>'v1'}
raise 'Lost second occurrence' unless c.unit_readiness(m)[0]['path'].include?('b')
m['instances'].pop
%w[input output internal].each do |direction|
  p={'port_id'=>direction,'direction'=>direction,'units'=>{'kind'=>'unspecified'}}
  v2['ports'] << p
  reject { c.require_resolved_units!(m) }
  v2['ports'].pop
end
m['instances'] << {'instance_id'=>'legacy','definition_version_id'=>'legacy'}
c.require_resolved_units!(m)
raise 'Legacy empty changed' unless c.unit_expression('')=='' && c.unit_expression({'kind'=>'dimensionless'})==''
raise 'Compound changed' unless c.unit_expression(v2['ports'][0]['units'])=='MJ/kg'
[{},nil,{'kind'=>'dimensionless','extra'=>true},{'kind'=>'physical','expression'=>"m';raise 'candidate'"},{'kind'=>'physical','expression'=>'USD'}].each do |bad|
  reject { c.unit_expression(bad) }
  v1['ports'][0]['units']=bad
  reject { c.unit_readiness(m) }
end
v1['ports'][0]['units']={'kind'=>'unspecified'}
v1['ports'] << {'port_id'=>'mixed','units'=>''}
reject { c.unit_readiness(m) }
v1['ports'].pop
m['instances'][0]['definition_version_id']='absent'
reject { c.unit_readiness(m) }
# Exercise actual whole-model validation, including exact source and retained shapes.
require 'securerandom'
raw="raise RuntimeError('must not execute')\n"
source={'encoding'=>'base64','media_type'=>'text/x-python','bytes'=>Base64.strict_encode64(raw),'sha256'=>Digest::SHA256.hexdigest(raw)}
family=SecureRandom.uuid; shared=SecureRandom.uuid
defs=[{'kind'=>'unspecified'},{'kind'=>'physical','expression'=>'MJ/kg'},''].map do |unit|
  version=SecureRandom.uuid
  {'definition_id'=>family,'definition_version_id'=>version,'kind'=>'explicit_component','name'=>'Fixture','ports'=>[{'port_id'=>shared,'definition_version_id'=>version,'direction'=>'output','name'=>'result','code_symbol'=>'result','value_type'=>'real_scalar','units'=>unit}], 'source_refs'=>[source['sha256']],'residual_port_ids'=>[],'child_instances'=>[],'boundary_mappings'=>[],'annotations'=>[]}
end
full={'schema_version'=>'3','model_id'=>SecureRandom.uuid,'root_instance_id'=>SecureRandom.uuid,'definitions'=>defs,'instances'=>[{'instance_id'=>SecureRandom.uuid,'definition_version_id'=>defs[1]['definition_version_id'],'name'=>'Active'}],'ports'=>defs.flat_map { |d| d['ports'] },'connections'=>[],'boundary_mappings'=>[],'annotations'=>[],'source_files'=>[source],'required_capabilities'=>['unit_declarations/1'],'study_id'=>SecureRandom.uuid,'name'=>'Fixture','draft_revision'=>'fixture','assumptions'=>[]}
original=copy(full)
c.validate_model(full);c.require_resolved_units!(full)
raise 'Model/source mutation' unless full==original
full['instances'][0]['definition_version_id']=defs[0]['definition_version_id']
c.validate_model(full)
reject { c.require_resolved_units!(full) }
full['instances'][0]['definition_version_id']=defs[1]['definition_version_id']
full['definitions'][0]['ports'][0]['units']={'kind'=>'physical','expression'=>'m;bad'}
reject { c.validate_model(full) }
full=copy(original);full['ports']=[]
reject { c.validate_model(full) }
full=copy(original);full['required_capabilities']=[]
reject { c.validate_model(full) }
raise 'Pair conversion missing' unless c.compatible_units?({'kind'=>'physical','expression'=>'MJ/kg'},'J/kg')
raise 'Affine conversion admitted' if c.compatible_units?('degC','K')
puts JSON.generate({'passed'=>true})
"""
        image=json.loads((self.runtime.REPO/'deployment/pins.json').read_text())['modeling_producer']['image']
        command=['docker','run','--pull','never','--rm','-i','--network','none','--read-only',
            '--cap-drop','ALL','--security-opt','no-new-privileges','--user','10001:10001',
            '--memory','256m','--cpus','1','--pids-limit','32',
            '--mount',f'type=bind,src={self.stage},dst=/fixture,readonly',
            '-e','HOME=/tmp','--entrypoint','ruby',image,'-']
        result=subprocess.run(command,input=code,capture_output=True,text=True,timeout=30,env=fixture.clean_environment(self.scope))
        (self.stage/'readiness.command.json').write_text(json.dumps(command))
        (self.stage/'readiness.rb').write_text(code)
        (self.stage/'readiness.log').write_text(result.stdout+result.stderr)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertTrue(json.loads(result.stdout)['passed'])
