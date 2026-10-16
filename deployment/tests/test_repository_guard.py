"""Isolation boundary and runner registry tests; no native imports, services or candidate execution."""
# Live-runtime fence (deployment/tests/live_fence.py): refuses live roots, live ports, docker, live entry points and real signals.
import sys as _fence_sys
from pathlib import Path as _FencePath
if str(_FencePath(__file__).resolve().parent) not in _fence_sys.path:
    _fence_sys.path.append(str(_FencePath(__file__).resolve().parent))
import live_fence  # noqa: E402
setUpModule, tearDownModule = live_fence.unittest_module_hooks('unit')
from dataclasses import replace
import ast
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import sys
import threading
import time
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import scoped_fixture as fixture
import checks as runner


class GuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scope = fixture.scope_from_environment()

    def test_approach_groups_fail_closed_before_allocation(self):
        groups = runner.APPROACH_PYTEST_GROUPS | set(runner.APPROACH_BROWSER_GROUPS)
        self.assertEqual(
            groups,
            {
                'approach-contracts',
                'approach-closure',
                'approach-service',
                'approach-api',
                'answers-api',
                'approach-configuration',
                'approach-bundle',
                'approach-worker',
                'approach-history',
                'approach-export',
                'approach-native',
                'approach-ui-controller',
                'approach-ui-reading',
                'approach-ui-method',
                'approach-ui-demo',
                'approach-ui-assumptions',
                'approach-ui-configuration',
                'approach-ui-history',
                'fuel-platform',
                'fuel-native-provenance',
                'investigation-native',
                'investigation-worker',
                'investigation-evidence',
                'investigation-diagnostics',
                'findings-history',
                'exploration-contracts',
                'exploration-api',
                'exploration-native',
                'exploration-ui',
                'exploration-answer-ui',
                'exploration-numerics',
                'exploration-surrogates-native',
                'exploration-fuel-surrogate',
            },
        )
        for group in groups:
            with self.subTest(group=group), patch.object(runner, 'targets_for', side_effect=ValueError('missing')), patch.object(fixture, 'allocate_scope') as allocate:
                with self.assertRaises(ValueError): runner.run_group(group)
                allocate.assert_not_called()
        for group in groups - {'approach-contracts'}:
            with self.subTest(group=group), self.assertRaisesRegex(ValueError, 'Required target missing'):
                runner.targets_for(group, repo=self.scope.root / 'tmp/empty-targets')

    def test_findings_continuation_group_set_is_separate(self):
        self.assertEqual(runner.FINDINGS_NATIVE_GROUPS, {'findings-native-guards', 'findings-native-preflight', 'findings-native', 'findings-native-read'})
        self.assertFalse(runner.FINDINGS_NATIVE_GROUPS & (runner.APPROACH_PYTEST_GROUPS | runner.UNITS_PYTEST_GROUPS | runner.AE_PYTEST_GROUPS))
        for group in runner.FINDINGS_NATIVE_GROUPS:
            with self.assertRaisesRegex(ValueError, 'Required target missing'):
                runner.targets_for(group, repo=self.scope.root / 'tmp/missing-findings')

    def test_approach_routing_and_interpreters_are_explicit(self):
        self.assertEqual(runner.GROUPS['findings-history'], ('application/tests/test_findings_history.py',))
        self.assertIn('findings-history', runner.APPROACH_APP_GROUPS)
        self.assertNotIn('findings-history', runner.APPROACH_NATIVE_GROUPS)
        self.assertEqual(runner.GROUP_INTERPRETERS['findings-history'], fixture.APPROVED_CONTRACT_PYTHON)
        self.assertEqual(runner.GROUPS['approach-contracts'], ('contracts/tests/test_approach_contracts.py', 'deployment/tests/test_repository_guard.py'))
        for group in runner.APPROACH_APP_GROUPS | set(runner.APPROACH_BROWSER_GROUPS):
            self.assertEqual(runner.GROUP_INTERPRETERS[group], fixture.APPROVED_CONTRACT_PYTHON)
        for group in runner.APPROACH_NATIVE_GROUPS:
            self.assertEqual(runner.GROUP_INTERPRETERS.get(group, fixture.APPROVED_PYTHON), fixture.APPROVED_PYTHON)
        for group, selector in runner.APPROACH_BROWSER_GROUPS.items():
            if group == 'exploration-answer-ui':
                self.assertEqual(selector, '@exploration-answer-basis')
            else:
                self.assertTrue(selector.startswith('@approach-'))
            self.assertEqual(
                runner.GROUPS[group],
                (
                    'deployment/tests/approach_ui_fixture.py',
                    'ui/tests/approach.spec.ts',
                ) + (('ui/tests/DesignSpecimen.tsx',) if group=='approach-ui-demo' else ()),
            )

    def test_approach_child_guards_before_collection_or_native_setup(self):
        for group in runner.APPROACH_PYTEST_GROUPS:
            with self.subTest(group=group), patch.object(fixture, 'scope_from_environment', side_effect=ValueError('unsafe')), patch.object(fixture, 'create_native_fixture') as native, patch.object(runner, 'targets_for') as targets:
                with self.assertRaises(ValueError): runner.contracts_child(group)
                targets.assert_not_called()
                native.assert_not_called()

    def assert_refused(self, scope, env=None):
        callback = Mock(side_effect=AssertionError('Native import/write reached'))
        with self.assertRaises(ValueError):
            fixture.guarded(scope, callback, env=env)
        callback.assert_not_called()

    def test_safe_explicit_scope_reaches_callback(self):
        callback = Mock(return_value='safe')
        self.assertEqual(fixture.guarded(self.scope, callback), 'safe')
        callback.assert_called_once_with(self.scope)

    def test_live_cloud_relative_and_traversal_roots_refused(self):
        for root in ('/tmp/test', '/private/tmp/../tmp/x', '.',
                     str(fixture.local_paths.data_root() / 'retired-layout'),
                     str(fixture.local_paths.execution_root()), str(fixture.local_paths.application_root()),
                     *(str(r) for r in fixture.local_paths.live_roots()),
                     str(fixture.SCRATCH_ROOT / ('other-' + str(uuid4()))),
                     str(Path(__file__).resolve().parents[2])):
            with self.subTest(root=root):
                self.assert_refused(replace(self.scope, root=Path(root)))

    def test_wrong_marker_identity_refused(self):
        self.assert_refused(replace(self.scope, store_uuid=str(uuid4())))
        self.assert_refused(replace(self.scope, profile_uuid=str(uuid4())))

    def test_default_live_or_unbound_profiles_refused(self):
        for profile in ('', 'default', 'hyprn-mvp', None):
            with self.subTest(profile=profile):
                self.assert_refused(replace(self.scope, profile=profile))
        self.assert_refused(replace(self.scope, backend='core.psql_dos'))
        self.assert_refused(replace(self.scope, interpreter='/usr/bin/python3'))

    def test_live_remote_and_credential_urls_refused(self):
        for url in ('http://localhost:19000', 'http://example.com:19000',
                    'http://user:pass@127.0.0.1:19000', 'http://127.0.0.1:19000?q=x',
                    'file:///tmp/test', 'http://127.0.0.1', 'http://127.0.0.1:19000/path'):
            with self.subTest(url=url):
                self.assert_refused(replace(self.scope, url=url))
        # Ports of another installation on this host (HYPRN_MVP_LIVE_PORTS) are live.
        with patch.dict(os.environ, {fixture.local_paths.LIVE_PORTS: '19461,19467'}):
            for url in ('http://127.0.0.1:19461', 'http://127.0.0.1:19467/'):
                with self.subTest(url=url):
                    self.assert_refused(replace(self.scope, url=url))

    def test_loopback_url_requires_marker_binding(self):
        self.assert_refused(replace(self.scope, url='http://127.0.0.1:19000'))

    def test_symlink_child_and_marker_refused_before_callback(self):
        home = self.scope.root / 'home'
        saved = self.scope.root / 'home-original'
        home.rename(saved)
        home.symlink_to('/private/tmp', target_is_directory=True)
        try:
            self.assert_refused(self.scope)
        finally:
            home.unlink()
            saved.rename(home)
        marker = self.scope.root / 'scope.json'
        original = self.scope.root / 'scope-original.json'
        marker.rename(original)
        marker.symlink_to(original)
        try:
            self.assert_refused(self.scope)
        finally:
            marker.unlink()
            original.rename(marker)

    def test_root_symlink_and_prefix_sibling_refused(self):
        link = fixture.SCRATCH_ROOT / (fixture.SCOPE_PREFIX + str(uuid4()))
        link.symlink_to(self.scope.root, target_is_directory=True)
        try:
            self.assert_refused(replace(self.scope, root=link))
        finally:
            link.unlink()
        self.assert_refused(replace(self.scope, root=Path(str(self.scope.root) + '-other')))

    def test_scoped_path_denies_escape_and_symlink(self):
        for path in ('../escape', '/private/tmp/escape', 'a/../escape', 'a\\b'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                fixture.scoped_path(self.scope, path)
        self.assertEqual(fixture.scoped_path(self.scope, 'evidence/result.json'),
                         self.scope.root / 'evidence/result.json')

    def test_clean_environment_drops_ambient_secrets_and_native_defaults(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'synthetic-secret',
                                    'AIIDA_PATH': '/live', 'PYTHONPATH': '/live'}):
            env = fixture.clean_environment(self.scope)
        self.assertNotIn('OPENAI_API_KEY', env)
        self.assertNotIn('PYTHONPATH', env)
        self.assertEqual(env['AIIDA_PATH'], str(self.scope.root / 'aiida'))
        self.assertEqual(env['HOME'], str(self.scope.root / 'home'))
        self.assertEqual(env['TMPDIR'], str(self.scope.root / 'tmp'))
        self.assertEqual(env['HYPRN_MVP_TEST_SCOPE_PROFILE'], self.scope.profile)

    def test_injected_environment_rejected_before_callback(self):
        good = fixture.clean_environment(self.scope)
        for key, value in [('OPENAI_API_KEY', 'synthetic'), ('HOME', str(fixture.local_paths.account_home())),
                           ('AIIDA_PATH', '/live'), ('PYTHONPATH', '/live')]:
            self.assert_refused(self.scope, {**good, key: value})

    def test_allocate_refuses_existing_root_before_writes(self):
        marker = (self.scope.root / 'scope.json').read_bytes()
        with self.assertRaises(ValueError):
            fixture.allocate_scope(self.scope)
        self.assertEqual((self.scope.root / 'scope.json').read_bytes(), marker)

    def test_invalid_allocation_makes_no_directories(self):
        scope = replace(fixture.new_scope(), profile='default')
        with patch.object(Path, 'mkdir', side_effect=AssertionError('Write reached')) as write:
            with self.assertRaises(ValueError):
                fixture.allocate_scope(scope)
        write.assert_not_called()
        self.assertFalse(scope.root.exists())

    def test_native_config_default_and_foreign_storage_refused(self):
        directory = self.scope.root / 'aiida/.aiida'
        directory.mkdir()
        path = directory / 'config.json'
        valid = {'default_profile': None, 'profiles': {self.scope.profile: {
            'PROFILE_UUID': self.scope.profile_uuid,
            'storage': {'backend': self.scope.backend,
                        'config': {'filepath': str(self.scope.root / 'native')}}}}}
        try:
            path.write_text(json.dumps({**valid, 'default_profile': self.scope.profile}))
            self.assert_refused(self.scope)
            bad = json.loads(json.dumps(valid))
            bad['profiles'][self.scope.profile]['storage']['config']['filepath'] = '/live'
            path.write_text(json.dumps(bad))
            self.assert_refused(self.scope)
            path.write_text(json.dumps(valid))
            self.assertEqual(fixture.guarded(self.scope, lambda scope: scope), self.scope)
        finally:
            path.unlink()
            directory.rmdir()

    def test_safe_browser_url_is_explicit_and_bound_to_fresh_marker(self):
        scope = fixture.allocate_scope(fixture.new_scope(url='http://127.0.0.1:19999'))
        self.assertEqual(fixture.guarded(scope, lambda s: s.url,
                         env=fixture.clean_environment(scope)), 'http://127.0.0.1:19999')
        self.assert_refused(replace(scope, url='http://127.0.0.1:19998'))

    def test_module_imports_are_native_free(self):
        native_import = Mock(side_effect=AssertionError('Native module imported'))
        class DenyNative:
            def find_spec(self, fullname, path=None, target=None):
                if fullname.split('.')[0] in {'aiida', 'hyprn_mvp_integration', 'openmdao'}:
                    native_import(fullname)
        guard = DenyNative()
        sys.meta_path.insert(0, guard)
        try:
            importlib.reload(fixture)
            importlib.reload(runner)
        finally:
            sys.meta_path.remove(guard)
        native_import.assert_not_called()

    def test_group_mapping_is_closed_and_missing_tests_fail(self):
        self.assertEqual(runner.targets_for('guard')[0],
                         'deployment/tests/test_repository_guard.py')
        with self.assertRaises(ValueError):
            runner.targets_for('all')
        with self.assertRaises(ValueError):
            runner.targets_for('contracts', repo=self.scope.root)

    def test_zero_or_skipped_tests_cannot_pass(self):
        empty = unittest.TestResult()
        self.assertFalse(runner.successful(empty))
        skipped = unittest.TestResult()
        skipped.testsRun = 1
        skipped.skipped.append(('test', 'missing fixture'))
        self.assertFalse(runner.successful(skipped))
        passed = unittest.TestResult()
        passed.testsRun = 1
        self.assertTrue(runner.successful(passed))

    def test_ae_registry_has_exact_reviewed_groups_and_interpreters(self):
        expected = {'ae-contracts', 'ae-generated', 'ae-public', 'ae-evidence',
                    'ae-model', 'ae-authoring', 'ae-configuration', 'ae-execution',
                    'ae-history', 'ae-export', 'ae-native',
                    'ae-ui-evidence', 'ae-ui-model', 'ae-ui-configuration'}
        self.assertEqual({g for g in runner.GROUPS if g.startswith('ae-')}, expected)
        self.assertEqual(runner.AE_NATIVE_GROUPS,
                         {'ae-execution', 'ae-history', 'ae-export', 'ae-native'})
        for group in expected:
            with self.subTest(group=group):
                python = runner.GROUP_INTERPRETERS.get(group, fixture.APPROVED_PYTHON)
                application = group in runner.AE_APP_GROUPS or group in runner.AE_BROWSER_GROUPS
                self.assertEqual(python, fixture.APPROVED_CONTRACT_PYTHON if application else fixture.APPROVED_PYTHON)

    def test_ae_missing_targets_refuse_before_scope_allocation(self):
        # Future groups must remain errors until their own tasks create targets.
        for group in runner.AE_PYTEST_GROUPS | set(runner.AE_BROWSER_GROUPS):
            with self.subTest(group=group):
                with self.assertRaisesRegex(ValueError, 'Required target missing'):
                    runner.targets_for(group, repo=self.scope.root)
        with patch.object(runner, 'targets_for', side_effect=ValueError('Required target missing')):
            with patch.object(fixture, 'allocate_scope') as allocate:
                with self.assertRaisesRegex(ValueError, 'Required target missing'):
                    runner.run_group('ae-history')
                allocate.assert_not_called()

    def test_ae_api_selections_are_disjoint(self):
        self.assertEqual(runner.AE_SELECTIONS['ae-generated'], ['-k', 'test_generated_'])
        self.assertEqual(runner.AE_SELECTIONS['ae-public'], ['-k', 'test_public_'])
        self.assertEqual(runner.GROUPS['ae-generated'], runner.GROUPS['ae-public'])
        self.assertEqual(runner.GROUPS['ae-generated'], ('application/tests/test_assumptions_evidence_api.py',))

    def test_ae_browser_selections_do_not_collect_legacy_journeys(self):
        self.assertEqual(runner.AE_BROWSER_GROUPS, {
            'ae-ui-evidence': '@ae-evidence', 'ae-ui-model': '@ae-model',
            'ae-ui-configuration': '@ae-configuration',
        })
        for group in runner.AE_BROWSER_GROUPS:
            self.assertEqual(runner.targets_for(group), (
                'ui/tests/assumptions-evidence.spec.ts', 'deployment/tests/ae_ui_fixture.py'))

    def test_ae_children_guard_before_collection_or_native_creation(self):
        for group in runner.AE_PYTEST_GROUPS:
            with self.subTest(group=group):
                with patch.object(fixture, 'scope_from_environment', side_effect=ValueError('Unscoped environment')):
                    with patch.object(fixture, 'create_native_fixture') as native:
                        with self.assertRaisesRegex(ValueError, 'Unscoped environment'):
                            runner.contracts_child(group)
                        native.assert_not_called()

    def test_ae_browser_fixture_guards_before_server_or_application(self):
        import ae_ui_fixture as browser
        with patch.object(fixture, 'scope_from_environment', side_effect=ValueError('Unscoped environment')):
            with patch.object(browser, 'ThreadingHTTPServer') as server:
                with self.assertRaisesRegex(ValueError, 'Unscoped environment'):
                    browser.run(group='ae-ui-evidence')
                server.assert_not_called()


class DocumentsGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scope = fixture.scope_from_environment()

    def test_documents_groups_have_existing_targets_and_select_tests(self):
        self.assertTrue(runner.DOCUMENTS_ROUTES)
        for group, route in runner.DOCUMENTS_ROUTES.items():
            with self.subTest(group=group):
                self.assertTrue(group.startswith('documents-'))
                self.assertFalse(any(character.isdigit() for character in group))
                self.assertEqual(runner.GROUPS[group], route['targets'])
                self.assertEqual(route['selector'], 'test_' + group.replace('-', '_') + '_'
                                 if route['mode'] != 'browser' else '@' + group + '(?:\\s|$)')
                selected = runner.documents_targets(group)
                self.assertTrue(selected)
                for target in route['targets']:
                    self.assertTrue((runner.REPO / target).is_file(), target)
                    if not target.endswith('.ts'):
                        self.assertTrue(any(s.startswith(target + '::' + route['selector']) for s in selected), target)
                runner.documents_capabilities(group)
        self.assertFalse(set(runner.DOCUMENTS_ROUTES) & runner.FINDINGS_NATIVE_GROUPS)

    def test_docs_missing_targets_or_selectors_refuse_before_allocation(self):
        for group in runner.DOCUMENTS_ROUTES:
            with self.subTest(group=group), self.assertRaises(ValueError):
                runner.documents_targets(group, repo=self.scope.root / 'missing-documents')
        for group in runner.DOCUMENTS_ROUTES:
            with patch.object(runner, 'documents_targets', side_effect=ValueError('missing')), patch.object(fixture, 'allocate_scope') as allocate:
                with self.assertRaises(ValueError): runner.run_documents(group)
                allocate.assert_not_called()

    def test_docs_fixed_selectors_reject_empty_skipped_and_unrelated_targets(self):
        root = self.scope.root / 'tmp/docs-targets'
        target = root / 'integration/tests/test_documents_native.py'
        target.parent.mkdir(parents=True)
        for body in ('', 'def test_unrelated(): pass', '@pytest.mark.skip(reason="x")\ndef test_documents_native_atomicity_probe(): pass',
                     'def test_documents_native_atomicity_probe(): pytest.skip("x")',
                     'pytestmark=pytest.mark.skipif(False)\ndef test_documents_native_atomicity_probe(): pass'):
            target.write_text(body)
            with self.assertRaises(ValueError): runner.documents_targets('documents-native-atomicity', repo=root)
        target.write_text('def test_documents_native_atomicity_probe(): assert True')
        self.assertEqual(runner.documents_targets('documents-native-atomicity', repo=root), ('integration/tests/test_documents_native.py::test_documents_native_atomicity_probe',))
        target.unlink()
        target.symlink_to(Path(__file__))
        with self.assertRaisesRegex(ValueError, 'Symlink'): runner.documents_targets('documents-native-atomicity', repo=root)

    MIXED = 'documents-mixed-probe'
    MIXED_ROUTE = {'mode': 'browser', 'selector': '@documents-mixed-probe(?:\\s|$)', 'targets': (
        'deployment/tests/test_documents_journey.py', 'ui/tests/documents-journey.spec.ts',
        'deployment/tests/test_documents_activation.py', 'contracts/tests/test_documents_contract.py')}

    def synthetic_routes(self):
        # A synthetic mixed browser route: resolution must not depend on a registered one.
        return patch.dict(runner.DOCUMENTS_ROUTES, {self.MIXED: self.MIXED_ROUTE})

    def mixed_documents_sources(self):
        # Synthetic source only: preflight must parse these files without imports.
        return {
            'deployment/tests/test_documents_journey.py': (
                'raise AssertionError("Source imported")\n'
                'def test_documents_mixed_probe_journey(): pass\n'
                'def test_documents_mixed_probe2_other_group(): pass\n'),
            'ui/tests/documents-journey.spec.ts': (
                "test('journey @documents-mixed-probe', async () => {});\n"),
            'deployment/tests/test_documents_activation.py': (
                'async def test_documents_mixed_probe_activation(): pass\n'),
            'contracts/tests/test_documents_contract.py': (
                'def test_documents_mixed_probe_contract(): pass\n'),
        }

    def test_docs_mixed_route_resolves_all_four_exact_targets(self):
        root = self.scope.root / 'tmp/docs-mixed-complete'
        for relative, source in self.mixed_documents_sources().items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(source)
        with self.synthetic_routes():
            self.assertEqual(runner.documents_targets(self.MIXED, repo=root), (
                'deployment/tests/test_documents_journey.py::test_documents_mixed_probe_journey',
                'ui/tests/documents-journey.spec.ts',
                'deployment/tests/test_documents_activation.py::test_documents_mixed_probe_activation',
                'contracts/tests/test_documents_contract.py::test_documents_mixed_probe_contract',
            ))
            self.assertEqual(runner.documents_interpreter(self.MIXED),
                             fixture.APPROVED_CONTRACT_PYTHON)

    def test_docs_mixed_route_refuses_each_missing_selector(self):
        sources = self.mixed_documents_sources()
        for index, missing in enumerate(sources):
            with self.subTest(missing=missing):
                root = self.scope.root / 'tmp' / ('docs-mixed-missing-' + str(index))
                for relative, source in sources.items():
                    path = root / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(source.replace('mixed_probe_', 'mixed_probe2_')
                                    .replace('@documents-mixed-probe', '@documents-other-probe')
                                    if relative == missing else source)
                kind = 'browser' if missing.endswith('.ts') else 'test'
                with self.assertRaises(ValueError) as refusal, self.synthetic_routes():
                    runner.documents_targets(self.MIXED, repo=root)
                self.assertEqual(str(refusal.exception),
                                 'Required Documents ' + kind + ' selector missing: ' + missing)

    def test_docs_child_rejects_invalid_environment_before_import(self):
        import builtins
        original = builtins.__import__
        def tripwire(name, *args, **kwargs):
            if name.split('.')[0] in {'aiida', 'pytest', 'hyprn_mvp_app', 'hyprn_mvp_integration',
                                      'documents_native_fixture', 'documents_ui_fixture'}:
                raise AssertionError('Collection or fixture import reached')
            return original(name, *args, **kwargs)
        good = fixture.clean_environment(self.scope)
        for group in ('documents-contracts', 'documents-native-atomicity', 'documents-collection-protocol', self.MIXED):
            for env in ({}, {**good, 'AIIDA_PATH': '/live'}, {**good, 'PYTHONPATH': '/foreign'},
                        {**good, 'OPENAI_API_KEY': 'synthetic'}, {**good, 'HYPRN_MVP_TEST_SCOPE_PROFILE': 'default'}):
                with self.subTest(group=group, keys=sorted(env)), self.synthetic_routes(), patch.dict(os.environ, env, clear=True), patch.object(builtins, '__import__', side_effect=tripwire):
                    with self.assertRaises((ValueError, OSError)): runner.documents_child(group)

    def test_docs_child_rejects_wrong_interpreter_before_collection(self):
        with patch.object(sys, 'executable', '/usr/bin/python3'), patch.object(runner, 'documents_targets') as targets:
            with self.assertRaisesRegex(ValueError, 'interpreter'): runner.documents_child('documents-contracts')
            targets.assert_not_called()
        for group in ('documents-native-atomicity', self.MIXED):
            with self.synthetic_routes(), patch.object(sys, 'executable', self.scope.interpreter), patch.object(runner, 'documents_targets') as targets:
                if runner.documents_interpreter(group) != self.scope.interpreter:
                    with self.assertRaisesRegex(ValueError, 'interpreter'): runner.documents_child(group)
                    targets.assert_not_called()

    def test_docs_native_and_browser_entrypoints_guard_direct_calls(self):
        import documents_native_fixture as native
        import documents_ui_fixture as browser
        for callback, group in ((native.start, 'documents-native-atomicity'), (browser.run, self.MIXED)):
            with patch.object(fixture, 'scope_from_environment', side_effect=ValueError('unsafe')), patch.object(fixture, 'create_native_fixture') as create:
                with self.assertRaisesRegex(ValueError, 'unsafe'): callback(group=group)
                create.assert_not_called()

    def test_docs_native_store_paths_reject_symlinks_and_forged_repository(self):
        scope = fixture.allocate_scope(fixture.new_scope())
        env = fixture.clean_environment(scope)
        for relative in ('native/database.sqlite', 'native/container', 'aiida/.aiida'):
            path = scope.root / relative
            path.symlink_to('/private/tmp')
            try:
                with patch.dict(os.environ, env, clear=True), patch.object(sys, 'executable', scope.interpreter), patch.object(fixture, 'create_native_fixture') as create:
                    with self.assertRaises(ValueError): fixture.documents_scope(scope.interpreter)
                    create.assert_not_called()
            finally: path.unlink()
        container = scope.root / 'native/container'
        container.mkdir()
        (container / 'config.json').write_text(json.dumps({'container_id': str(uuid4())}))
        with patch.dict(os.environ, env, clear=True), patch.object(sys, 'executable', scope.interpreter):
            with self.assertRaisesRegex(ValueError, 'repository'): fixture.documents_scope(scope.interpreter)

    def test_docs_parent_and_cli_refuse_forged_interpreter_or_arguments(self):
        with patch.object(sys, 'executable', fixture.APPROVED_CONTRACT_PYTHON), patch.object(fixture, 'allocate_scope') as allocate:
            with self.assertRaisesRegex(ValueError, 'parent interpreter'): runner.run_documents('documents-contracts')
            allocate.assert_not_called()
        for args in (['--group', 'documents-all'], ['--group', 'documents-contracts', '--root', '/live'],
                     ['--group', 'documents-contracts', '--units-mixed-repair'], ['--documents-contracts-child', '--native'],
                     ['--group', 'documents-contracts', '--', '-k', 'anything']):
            with patch.object(sys, 'argv', ['checks', *args]), patch.object(fixture, 'allocate_scope') as allocate:
                try: self.assertNotEqual(runner.main(), 0)
                except SystemExit as error: self.assertNotEqual(error.code, 0)
                allocate.assert_not_called()

    def test_docs_future_browser_capability_is_not_a_passing_stub(self):
        import documents_ui_fixture as browser
        with patch.object(browser, 'guarded_scope', return_value=self.scope), patch.object(runner, 'documents_targets', return_value=('ui/tests/documents-library.spec.ts',)):
            with self.assertRaisesRegex(ValueError, 'capability'): browser.run(group=self.MIXED)

    def test_docs_empty_skipped_xfail_or_missing_file_results_fail(self):
        good = {'a.py': {'passed': 1, 'failed': 0, 'skipped': 0}}
        self.assertTrue(runner.documents_results_passed(0, good, ['a.py']))
        for counts in ({}, {'a.py': {'passed': 0, 'failed': 0, 'skipped': 0}},
                       {'a.py': {'passed': 1, 'failed': 0, 'skipped': 1}},
                       {'a.py': {'passed': 1, 'failed': 1, 'skipped': 0}}):
            self.assertFalse(runner.documents_results_passed(0, counts, ['a.py']))
        self.assertFalse(runner.documents_results_passed(0, good, ['a.py', 'b.py']))
        self.assertFalse(runner.documents_results_passed(1, good, ['a.py']))

    def test_docs_modules_are_stdlib_only_before_guard(self):
        import builtins
        original = builtins.__import__
        def tripwire(name, *args, **kwargs):
            if name.split('.')[0] in {'aiida', 'pytest', 'hyprn_mvp_app', 'hyprn_mvp_integration', 'fastapi'}:
                raise AssertionError('Native or application import reached')
            return original(name, *args, **kwargs)
        with patch.object(builtins, '__import__', side_effect=tripwire):
            importlib.reload(importlib.import_module('documents_native_fixture'))
            importlib.reload(importlib.import_module('documents_ui_fixture'))

    def test_docs_missing_measurements_cannot_report_success(self):
        for record in ({'passed': True}, {'passed': True, 'tests': 0, 'skipped': 0},
                       {'passed': True, 'tests': True, 'skipped': 0},
                       {'passed': True, 'tests': 1, 'skipped': 1},
                       {'passed': True, 'tests': 1, 'skipped': 0, 'errors': 1}):
            self.assertFalse(runner.documents_report_passed(record))
        self.assertTrue(runner.documents_report_passed({'passed': True, 'tests': 1, 'skipped': 0}))

    def test_docs_logical_measurements_are_mandatory(self):
        with self.assertRaisesRegex(ValueError, 'evidence'):
            runner.documents_collection_evidence(self.scope)
        path = self.scope.root / 'evidence/atomicity-logical-commit.json'
        path.write_text('{}')
        try:
            with self.assertRaisesRegex(ValueError, 'Incomplete'):
                runner.documents_collection_evidence(self.scope)
        finally:
            path.unlink()

    def test_docs_logical_child_is_finite_and_guards_before_native_import(self):
        import documents_native_fixture as native
        import builtins
        original = builtins.__import__
        def tripwire(name, *args, **kwargs):
            if name.split('.')[0] == 'aiida':
                raise AssertionError('Native import reached before guard')
            return original(name, *args, **kwargs)
        for mode in ('inspect', 'replay', 'removed', 'metadata', 'witness', 'committed'):
            with patch.object(sys, 'argv', ['probe', '--collection-protocol-child', mode, 'artifacts/request.json']), patch.object(fixture, 'scope_from_environment', side_effect=ValueError('unsafe scope')), patch.object(builtins, '__import__', side_effect=tripwire):
                with self.assertRaisesRegex(ValueError, 'unsafe scope'):
                    native.collection_protocol_child()
        with patch.object(sys, 'argv', ['probe', '--collection-protocol-child', 'anything', 'artifacts/request.json']), patch.object(native, 'reopen_probe') as reopen:
            with self.assertRaisesRegex(ValueError, 'Fixed'):
                native.collection_protocol_child()
            reopen.assert_not_called()


    def test_docs_shared_child_scope_rejected_before_native_import(self):
        scope = fixture.allocate_scope(fixture.new_scope())
        path = scope.root / 'evidence/documents-child.json'
        path.write_text(json.dumps({'pid': -1, 'run_uuid': scope.run_uuid,
                                   'interpreter': scope.interpreter}))
        with patch.dict(os.environ, fixture.clean_environment(scope), clear=True), patch.object(sys, 'executable', scope.interpreter), patch.object(fixture, 'create_native_fixture') as create:
            with self.assertRaisesRegex(ValueError, 'shared'): fixture.documents_scope(scope.interpreter)
            create.assert_not_called()

    def test_docs_root_marker_and_profile_refused_before_collection(self):
        import builtins
        original = builtins.__import__
        def tripwire(name, *args, **kwargs):
            if name.split('.')[0] in {'pytest', 'aiida', 'documents_native_fixture', 'documents_ui_fixture'}:
                raise AssertionError('Collection reached')
            return original(name, *args, **kwargs)
        for root in ('/private/tmp', str(fixture.SCRATCH_ROOT), str(fixture.local_paths.execution_root()), str(runner.REPO)):
            with patch.dict(os.environ, {**fixture.clean_environment(self.scope), 'HYPRN_MVP_TEST_SCOPE_ROOT': root}, clear=True), patch.object(builtins, '__import__', side_effect=tripwire):
                with self.assertRaises(ValueError): runner.documents_child('documents-native-atomicity')
        marker = self.scope.root / 'scope.json'
        before = marker.read_bytes()
        for change in ({'profile': 'default'}, {'store_uuid': self.scope.profile_uuid},
                       {'root': '/private/tmp'}):
            marker.write_text(json.dumps({**self.scope.record(), **change}))
            try:
                with patch.object(builtins, '__import__', side_effect=tripwire):
                    with self.assertRaises(ValueError): runner.documents_child('documents-contracts')
            finally: marker.write_bytes(before)



class LocalApiClientGroupGuardTests(unittest.TestCase):
    def test_local_api_client_has_one_scoped_target_and_no_native_backend(self):
        self.assertEqual(runner.GROUPS['local-api-client'],
                         ('deployment/tests/test_local_api_client.py',))
        self.assertEqual(runner.UNITTEST_GUARD_MODULES['local-api-client'],
                         'test_local_api_client')
        self.assertNotIn('local-api-client', runner.NATIVE_BACKEND_GROUPS)
        self.assertNotIn('local-api-client', runner.BROWSER_GROUPS)
        self.assertEqual(runner.group_needs('local-api-client'), ())


class LocalityContractsGuardTests(unittest.TestCase):
    """Closed data-only locality group under the reviewed application interpreter."""

    @classmethod
    def setUpClass(cls):
        cls.scope = fixture.scope_from_environment()

    def test_locality_group_is_closed_with_fixed_application_targets(self):
        targets = ('application/tests/test_identity_golden.py', 'application/tests/test_module_boundaries.py',
                   'application/tests/test_contract_errors.py')
        self.assertEqual(runner.GROUPS['locality-contracts'], targets)
        self.assertEqual(runner.LOCALITY_PYTEST_GROUPS, {'locality-contracts'})
        self.assertEqual(runner.targets_for('locality-contracts'), targets)
        self.assertEqual(runner.GROUP_INTERPRETERS['locality-contracts'], fixture.APPROVED_CONTRACT_PYTHON)
        self.assertNotIn('locality-contracts', runner.DOCUMENTS_ROUTES)
        self.assertFalse(runner.LOCALITY_PYTEST_GROUPS & (runner.APPROACH_NATIVE_GROUPS | runner.UNITS_NATIVE_GROUPS
                                                          | runner.AE_NATIVE_GROUPS | runner.RELEASE_PYTEST_GROUPS
                                                          | runner.FINDINGS_NATIVE_GROUPS))

    def test_locality_missing_target_refuses_before_allocation(self):
        with self.assertRaisesRegex(ValueError, 'Required target missing'):
            runner.targets_for('locality-contracts', repo=self.scope.root / 'tmp/missing-locality-target')
        with patch.object(runner, 'targets_for', side_effect=ValueError('Required target missing')), \
                patch.object(fixture, 'allocate_scope') as allocate:
            with self.assertRaisesRegex(ValueError, 'Required target missing'):
                runner.run_group('locality-contracts')
            allocate.assert_not_called()


class AgentGroupsGuardTests(unittest.TestCase):
    """Closed agent groups: application tests under the reviewed application interpreter,
    one directory target each, no environment needs, disjoint from native groups."""

    @classmethod
    def setUpClass(cls):
        cls.scope = fixture.scope_from_environment()

    def test_agent_groups_are_closed_with_directory_targets_only(self):
        self.assertEqual(runner.AGENT_PYTEST_GROUPS, {'agent-tools'})
        self.assertEqual(runner.AGENT_DIRECTORY_TARGETS, {'agent-tools': 'application/tests/agent/'})
        for group, target in runner.AGENT_DIRECTORY_TARGETS.items():
            with self.subTest(group=group):
                self.assertEqual(runner.GROUPS[group], (target,))
                self.assertEqual(runner.targets_for(group), (target,))
                self.assertEqual(runner.GROUP_INTERPRETERS[group], fixture.APPROVED_CONTRACT_PYTHON)
                self.assertEqual(runner.group_class(group), 'must-pass')
                self.assertEqual(runner.group_needs(group), ())
                self.assertIn(group, runner.PROJECT_PYTEST_GROUPS)
                self.assertIn(group, runner.CHILD_GROUPS)
        directory_groups = {g for g, targets in runner.GROUPS.items() if any(t.endswith('/') for t in targets)}
        self.assertEqual(directory_groups, set(runner.AGENT_PYTEST_GROUPS))
        self.assertFalse(runner.AGENT_PYTEST_GROUPS & (runner.NATIVE_BACKEND_GROUPS | runner.DOCKER_GROUPS
                                                       | runner.BROWSER_GROUPS | runner.FIXTURE_GROUPS
                                                       | runner.FINDINGS_NATIVE_GROUPS | set(runner.DOCUMENTS_ROUTES)
                                                       | runner.MODELING_PYTEST_GROUPS | runner.RELEASE_PYTEST_GROUPS))

    def test_directory_target_must_exist_and_hold_a_test_module(self):
        repo = self.scope.root / 'tmp/agent-directory-target'
        directory = repo / 'application/tests/agent'
        with self.assertRaisesRegex(ValueError, 'Required target missing'):
            runner.targets_for('agent-tools', repo=repo)
        directory.mkdir(parents=True)
        (directory / 'helpers.py').write_text('')
        with self.assertRaisesRegex(ValueError, 'Required target missing'):
            runner.targets_for('agent-tools', repo=repo)
        (directory / 'test_example.py').write_text('')
        self.assertEqual(runner.targets_for('agent-tools', repo=repo), ('application/tests/agent/',))
        self.assertEqual(runner.target_sources(('application/tests/test_module_boundaries.py::name',)),
                         ['application/tests/test_module_boundaries.py'])
        self.assertIn('application/tests/agent/test_agent_principal.py',
                      runner.target_sources(runner.GROUPS['agent-tools']))

    def test_no_other_group_accepts_a_directory_target(self):
        with patch.dict(runner.GROUPS, {'locality-contracts': ('application/tests/agent/',)}):
            with self.assertRaisesRegex(ValueError, 'Directory target not allowed'):
                runner.targets_for('locality-contracts')
        with patch.dict(runner.GROUPS, {'agent-tools': ('application/tests/',)}):
            with self.assertRaisesRegex(ValueError, 'Directory target not allowed'):
                runner.targets_for('agent-tools')

    def test_agent_missing_target_refuses_before_allocation(self):
        with patch.object(runner, 'targets_for', side_effect=ValueError('Required target missing')), \
                patch.object(fixture, 'allocate_scope') as allocate:
            with self.assertRaisesRegex(ValueError, 'Required target missing'):
                runner.run_group('agent-tools')
            allocate.assert_not_called()


class AgentBrowserGuardTests(unittest.TestCase):
    """The agent browser group: closed specs on the in-browser agent double, the reviewed
    application interpreter, a browser need and a report that fails closed."""

    @classmethod
    def setUpClass(cls):
        cls.scope = fixture.scope_from_environment()

    def test_agent_ui_group_is_closed_with_fixed_targets_and_application_interpreter(self):
        import agent_ui_fixture as agent

        self.assertEqual(runner.AGENT_BROWSER_GROUPS, {'agent-ui'})
        self.assertEqual(
            runner.GROUPS['agent-ui'],
            (
                'deployment/tests/agent_ui_fixture.py',
                'deployment/tests/foundry_ui_fixture.py',
                'ui/tests/foundry-fixtures.ts',
                'ui/tests/agent-fixtures.ts',
                'application/tests/agent/fixtures/recorded_api.json',
                'ui/tests/agent-attribution.spec.ts',
            ),
        )
        self.assertEqual(agent.GROUP_SPECS, {'agent-ui': ('agent-attribution.spec.ts',)})
        specs = tuple(t for t in runner.GROUPS['agent-ui'] if t.endswith('.spec.ts'))
        self.assertEqual(specs, tuple('ui/tests/' + spec for spec in agent.GROUP_SPECS['agent-ui']))
        self.assertEqual(runner.GROUP_INTERPRETERS['agent-ui'], fixture.APPROVED_CONTRACT_PYTHON)
        self.assertEqual(runner.group_class('agent-ui'), 'must-pass')
        self.assertEqual(runner.group_needs('agent-ui'), ('browser',))
        self.assertIn('agent-ui', runner.CHILD_GROUPS)
        self.assertFalse(
            runner.AGENT_BROWSER_GROUPS
            & (
                runner.FOUNDRY_BROWSER_GROUPS
                | runner.PROJECT_PYTEST_GROUPS
                | runner.SERVED_BROWSER_GROUPS
                | runner.DOCKER_GROUPS
                | runner.FIXTURE_GROUPS
                | set(runner.DOCUMENTS_ROUTES)
            )
        )
        config = agent.browser_config(self.scope)
        self.assertEqual(config['testMatch'], ['agent-attribution.spec.ts'])
        self.assertEqual((config['workers'], config['retries'], config['forbidOnly']), (1, 0, True))
        for key in ('outputDir', 'snapshotPathTemplate'):
            self.assertTrue(config[key].startswith(str(self.scope.root) + '/evidence/'), key)

    def test_agent_ui_report_fails_closed(self):
        import agent_ui_fixture as agent

        good = dict(expected=7, unexpected=0, skipped=0, flaky=0)
        specs = set(agent.GROUP_SPECS['agent-ui'])
        self.assertTrue(agent.report_passed(0, good, specs, []))
        for returncode, stats, files, forbidden in (
            (1, good, specs, []),
            (0, {}, specs, []),
            (0, dict(good, expected=0), specs, []),
            (0, dict(good, skipped=1), specs, []),
            (0, dict(good, flaky=1), specs, []),
            (0, dict(good, unexpected=1), specs, []),
            (0, good, set(), []),
            (0, good, specs | {'foundry-zoom.spec.ts'}, []),
            (0, good, specs, ['openmdao']),
        ):
            with self.subTest(returncode=returncode, stats=stats, files=files, forbidden=forbidden):
                self.assertFalse(agent.report_passed(returncode, stats, files, forbidden))

    def test_agent_ui_child_refuses_wrong_interpreter_unknown_group_or_missing_target(self):
        import agent_ui_fixture as agent

        # This guard child runs the native interpreter: the application-only child must refuse.
        with patch.object(agent.subprocess, 'run') as spawned:
            with self.assertRaisesRegex(ValueError, 'reviewed interpreter'):
                runner.agent_browser_child('agent-ui')
            with self.assertRaisesRegex(ValueError, 'reviewed application interpreter'):
                agent.run(group='agent-ui')
            with self.assertRaisesRegex(ValueError, 'Unknown agent'):
                runner.agent_browser_child('agent-ui-x')
            spawned.assert_not_called()
        missing = ValueError('Required target missing')
        with patch.object(runner, 'targets_for', side_effect=missing), \
                patch.object(fixture, 'allocate_scope') as allocate:
            with self.assertRaisesRegex(ValueError, 'Required target missing'):
                runner.run_group('agent-ui')
            allocate.assert_not_called()


class RegistryGuardTests(unittest.TestCase):
    """Every group has a class and environment needs; absent needs fail before allocation."""

    RETIRED = ('ae-activation', 'approach-activation', 'units-activation', 'handoff', 'polish-release',
               'checkpoint-a', 'checkpoint-b', 'checkpoint-c', 'combined', 'ae-ui', 'approach-ui')

    @classmethod
    def setUpClass(cls):
        cls.scope = fixture.scope_from_environment()

    def test_every_group_has_a_class_and_known_needs(self):
        for group in runner.GROUPS:
            with self.subTest(group=group):
                self.assertIn(runner.group_class(group), runner.CLASSES)
                needs = runner.group_needs(group)
                self.assertEqual(len(set(needs)), len(needs))
                self.assertTrue(set(needs) <= set(runner.NEEDS))
        for group in runner.DOCUMENTS_ROUTES:
            if runner.DOCUMENTS_ROUTES[group]['mode'] == 'native':
                self.assertIn('docker', runner.group_needs(group))
        for group in runner.FOUNDRY_BROWSER_GROUPS | set(runner.APPROACH_BROWSER_GROUPS) | set(runner.UNITS_BROWSER_GROUPS):
            self.assertIn('browser', runner.group_needs(group))
        self.assertEqual(runner.group_needs('naming'), ())
        self.assertEqual(runner.group_needs('hygiene'), ())
        self.assertEqual(runner.group_needs('approach-ui-history'), ('browser', 'fixtures'))
        with self.assertRaises(ValueError):
            runner.group_class('all')

    def test_retired_groups_are_not_registered_or_routable(self):
        for group in self.RETIRED:
            with self.subTest(group=group):
                self.assertNotIn(group, runner.GROUPS)
                self.assertNotIn(group, runner.CHILD_GROUPS)
                with self.assertRaises(ValueError):
                    runner.targets_for(group)
                with patch.object(sys, 'argv', ['checks.py', '--group', group]), \
                        patch.object(fixture, 'allocate_scope') as allocate, patch('sys.stderr'):
                    with self.assertRaises(SystemExit):
                        runner.main()
                    allocate.assert_not_called()

    def test_absent_need_fails_before_allocation(self):
        for group, need in (('units-native', 'docker'), ('ui-navigation', 'browser'),
                            ('approach-ui-history', 'fixtures'), ('documents-native-atomicity', 'docker')):
            with self.subTest(group=group), patch.object(runner, 'need_present', side_effect=lambda n, absent=need: n != absent), \
                    patch.object(sys, 'executable', fixture.APPROVED_PYTHON), \
                    patch.object(fixture, 'allocate_scope') as allocate, patch.object(runner.subprocess, 'run') as launch:
                with self.assertRaisesRegex(ValueError, '^environment absent: ' + need + '$'):
                    runner.run_group(group)
                allocate.assert_not_called()
                launch.assert_not_called()
        with self.assertRaises(ValueError):
            runner.need_present('network')

    def test_list_prints_every_group_with_class_and_needs(self):
        import contextlib
        import io
        output = io.StringIO()
        with contextlib.redirect_stdout(output), patch.object(sys, 'argv', ['checks.py', '--list']):
            self.assertEqual(runner.main(), 0)
        rows = [line.split('\t') for line in output.getvalue().splitlines()]
        self.assertEqual([row[0] for row in rows], [*runner.GROUPS, 'qualification'])
        for name, group_class, needs in rows[:-1]:
            self.assertEqual(group_class, runner.group_class(name))
            self.assertEqual(needs, ','.join(runner.group_needs(name)) or '-')
        output = io.StringIO()
        with contextlib.redirect_stdout(output), patch.object(sys, 'argv', ['checks.py', '--list', '--class', 'must-pass']):
            self.assertEqual(runner.main(), 0)
        self.assertEqual([line.split('\t')[0] for line in output.getvalue().splitlines()],
                         [g for g in runner.GROUPS if runner.group_class(g) == 'must-pass'])
        with patch.object(sys, 'argv', ['checks.py', '--group', 'guard', '--class', 'must-pass']), patch('sys.stderr'), \
                patch.object(fixture, 'allocate_scope') as allocate:
            self.assertNotEqual(runner.main(), 0)
            allocate.assert_not_called()

    def test_qualification_runs_every_must_pass_group_and_stops_at_the_first_failure(self):
        groups = runner.must_pass_groups()
        self.assertEqual(sorted(groups), sorted(g for g in runner.GROUPS if runner.group_class(g) == 'must-pass'))
        self.assertEqual(len(groups), len(set(groups)))
        self.assertNotIn('qualification', runner.GROUPS)
        from types import SimpleNamespace
        calls = []
        def launch(command, **kwargs):
            calls.append(command[command.index('--group') + 1])
            return SimpleNamespace(returncode=1 if len(calls) == 3 else 0)
        with patch.object(runner.subprocess, 'run', side_effect=launch), patch('sys.stdout'):
            self.assertEqual(runner.run_group('qualification', jobs=1), 1)
        self.assertEqual(calls, groups[:3])
        calls.clear()
        with patch.object(runner.subprocess, 'run', side_effect=lambda command, **kwargs: calls.append(command) or SimpleNamespace(returncode=0)), \
                patch('sys.stdout'):
            self.assertEqual(runner.run_group('qualification', jobs=1), 0)
        self.assertEqual([c[c.index('--group') + 1] for c in calls], groups)
        for command in calls:
            group = command[command.index('--group') + 1]
            self.assertEqual(command[0], fixture.APPROVED_PYTHON if group in runner.DOCUMENTS_ROUTES else sys.executable)


class QualificationPoolTests(unittest.TestCase):
    """The phase gate's bounded pool: never more than --jobs groups at once, lanes never overlap
    and keep qualification order, an exclusive group runs alone, no group starts after a
    failure, and results are reported in qualification order whatever order groups finish in."""

    def pool(self, groups, behaviour=None, *, jobs, lanes=None, exclusive=frozenset()):
        """Fake groups: ``behaviour[group] = (exit, seconds)``, or an exception to raise."""
        behaviour = behaviour or {}
        lock = threading.Lock()
        self.events, active, self.peak, reports = [], set(), 0, []

        def run(group):
            with lock:
                active.add(group)
                self.peak = max(self.peak, len(active))
                self.events.append(('start', group, frozenset(active)))
            outcome = behaviour.get(group, (0, 0.01))
            try:
                if isinstance(outcome, Exception):
                    raise outcome
                time.sleep(outcome[1])
                return dict(group=group, exit=outcome[0], duration_seconds=outcome[1], output='')
            finally:
                with lock:
                    active.discard(group)
                    self.events.append(('end', group, frozenset(active)))

        results, not_started = runner.pool_qualification(groups, run, reports.append, jobs=jobs,
                                                         lanes=lanes or {}, exclusive=exclusive)
        self.assertEqual([r['group'] for r in reports], [r['group'] for r in results])
        return results, not_started

    def at(self, kind, group):
        return next(i for i, event in enumerate(self.events) if event[:2] == (kind, group))

    def started(self):
        return [event[1] for event in self.events if event[0] == 'start']

    def test_the_pool_never_runs_more_than_jobs_groups_at_once(self):
        groups = ['g' + str(i) for i in range(9)]
        for jobs in (1, 2, 3, 4):
            with self.subTest(jobs=jobs):
                results, not_started = self.pool(groups, {g: (0, 0.05) for g in groups}, jobs=jobs)
                self.assertEqual(self.peak, jobs)
                self.assertEqual([r['group'] for r in results], groups)
                self.assertEqual(not_started, [])
        self.pool(groups, jobs=1)
        self.assertEqual([event[:2] for event in self.events],
                         [(kind, g) for g in groups for kind in ('start', 'end')])

    def test_lane_members_never_overlap_and_start_after_every_earlier_member_finished(self):
        groups = ['a', 'b', 'c', 'd', 'e', 'f']
        lane = frozenset({'a', 'c', 'e'})
        self.pool(groups, {'a': (0, 0.2), 'c': (0, 0.1)}, jobs=3, lanes={'shared': lane})
        self.assertLess(self.at('end', 'a'), self.at('start', 'c'))
        self.assertLess(self.at('end', 'c'), self.at('start', 'e'))
        self.assertLess(self.at('start', 'b'), self.at('end', 'a'))  # Independent groups go ahead.
        self.assertLess(self.at('start', 'd'), self.at('end', 'a'))
        for event in self.events:
            self.assertLessEqual(len(event[2] & lane), 1)

    def test_an_exclusive_group_runs_alone_between_its_predecessors_and_successors(self):
        groups = ['a', 'b', 'x', 'c', 'd']
        self.pool(groups, {'a': (0, 0.1), 'x': (0, 0.1)}, jobs=3, exclusive=frozenset({'x'}))
        start = self.at('start', 'x')
        self.assertEqual(self.events[start][2], frozenset({'x'}))
        for group in ('a', 'b'):
            self.assertLess(self.at('end', group), start)
        for group in ('c', 'd'):
            self.assertLess(self.at('end', 'x'), self.at('start', group))

    def test_after_a_failure_no_group_starts_and_running_groups_finish_and_are_reported(self):
        groups = ['a', 'b', 'c', 'd', 'e', 'f']
        results, not_started = self.pool(groups, {'a': (0, 0.2), 'b': (1, 0.01)}, jobs=2)
        self.assertEqual(self.started(), ['a', 'b'])
        self.assertEqual([(r['group'], r['exit']) for r in results], [('a', 0), ('b', 1)])
        self.assertEqual(not_started, ['c', 'd', 'e', 'f'])
        results, not_started = self.pool(groups, {'a': (1, 0.01)}, jobs=1)
        self.assertEqual(([r['group'] for r in results], not_started), (['a'], groups[1:]))

    def test_a_result_after_a_group_that_never_started_is_still_reported_in_order(self):
        groups = ['a', 'b', 'c']
        results, not_started = self.pool(groups, {'a': (1, 0.05), 'c': (0, 0.2)}, jobs=2,
                                         lanes={'shared': frozenset({'a', 'b'})})
        self.assertEqual(self.started(), ['a', 'c'])
        self.assertEqual([(r['group'], r['exit']) for r in results], [('a', 1), ('c', 0)])
        self.assertEqual(not_started, ['b'])

    def test_results_are_reported_in_qualification_order_whatever_the_finishing_order(self):
        groups = ['a', 'b', 'c', 'd', 'e', 'f']
        results, _ = self.pool(groups, {g: (0, 0.05 * (len(groups) - i)) for i, g in enumerate(groups)}, jobs=6)
        finished = [event[1] for event in self.events if event[0] == 'end']
        self.assertEqual(finished, list(reversed(groups)))
        self.assertEqual([r['group'] for r in results], groups)

    def test_a_group_whose_launch_raises_fails_the_gate_and_never_passes(self):
        results, not_started = self.pool(['a', 'b', 'c'], {'a': OSError('cannot launch')}, jobs=1)
        self.assertEqual(results[0]['exit'], 2)
        self.assertIn('cannot launch', results[0]['output'])
        self.assertEqual(not_started, ['b', 'c'])

    def test_jobs_outside_the_bound_are_refused_before_any_group_starts(self):
        run = Mock()
        for jobs in (0, -1, runner.QUALIFICATION_MAX_JOBS + 1, '3', 2.0, True, None):
            with self.subTest(jobs=jobs), self.assertRaisesRegex(ValueError, '--jobs'):
                runner.pool_qualification(['a'], run, Mock(), jobs=jobs)
            with self.subTest(jobs=jobs), self.assertRaisesRegex(ValueError, '--jobs'), \
                    patch.object(runner.subprocess, 'run') as launch:
                runner.run_group('qualification', jobs=jobs)
            launch.assert_not_called()
        run.assert_not_called()

    def test_the_durable_fixture_chain_and_the_fixed_scratch_root_users_share_one_lane(self):
        self.assertEqual(runner.QUALIFICATION_JOBS, 3)
        lane = runner.SERIAL_LANES['fixed-scratch-root']
        self.assertTrue({'findings-native-preflight', 'findings-native', 'findings-native-read',
                         'approach-ui-history', 'units-native'} <= lane)
        self.assertTrue(runner.FIXTURE_GROUPS <= lane)
        members = [g for members in runner.SERIAL_LANES.values() for g in members]
        self.assertEqual(len(members), len(set(members)))
        for group in (*members, *runner.EXCLUSIVE_GROUPS):
            with self.subTest(group=group):
                self.assertEqual(runner.group_class(group), 'must-pass')
        self.assertFalse(set(members) & runner.EXCLUSIVE_GROUPS)
        order = runner.must_pass_groups()
        chain = [g for g in order if g in {'findings-native-preflight', 'findings-native', 'findings-native-read'}]
        self.assertEqual(chain, ['findings-native-preflight', 'findings-native', 'findings-native-read'])

    def test_qualification_runs_groups_concurrently_and_prints_each_result_in_order(self):
        import contextlib
        import io
        from types import SimpleNamespace
        groups = ['guard', 'naming', 'hygiene', 'contracts']
        delay = {'guard': 0.2, 'naming': 0.1, 'hygiene': 0.0, 'contracts': 0.05}
        calls = []

        def launch(command, **kwargs):
            group = command[command.index('--group') + 1]
            calls.append((group, kwargs))
            time.sleep(delay[group])
            return SimpleNamespace(returncode=0, stdout=('output of ' + group + '\n').encode())

        output = io.StringIO()
        with patch.object(runner, 'must_pass_groups', return_value=groups), \
                patch.object(runner.subprocess, 'run', side_effect=launch), contextlib.redirect_stdout(output):
            self.assertEqual(runner.run_group('qualification', jobs=3), 0)
        lines = output.getvalue().splitlines()
        expected = []
        for group in groups:
            expected += ['output of ' + group, group]
        self.assertEqual([line if line.startswith('output of') else json.loads(line).get('qualification')
                          for line in lines[:-1]], expected)
        summary = json.loads(lines[-1])
        self.assertEqual((summary['passed'], summary['jobs'], summary['not_started']), (True, 3, []))
        self.assertEqual(summary['counts'], dict(groups=4, passed=4, failed=0, not_started=0))
        self.assertEqual([g['group'] for g in summary['groups']], groups)
        self.assertTrue(all(kwargs.get('stdout') == runner.subprocess.PIPE for _, kwargs in calls))

    def test_jobs_is_refused_for_every_command_but_the_gate(self):
        for argv in (['--group', 'guard', '--jobs', '2'], ['--list', '--jobs', '2']):
            with self.subTest(argv=argv), patch.object(sys, 'argv', ['checks.py', *argv]), patch('sys.stderr'), \
                    patch.object(fixture, 'allocate_scope') as allocate, patch.object(runner.subprocess, 'run') as launch:
                self.assertEqual(runner.main(), 2)
                allocate.assert_not_called()
                launch.assert_not_called()


class DeploymentHardeningGuardTests(unittest.TestCase):
    """Closed deployment-hardening group (managers, release tooling, backup tool)."""

    @classmethod
    def setUpClass(cls):
        cls.scope = fixture.scope_from_environment()

    def test_hardening_group_is_closed_with_fixed_unit_fenced_targets(self):
        # Each fixed target loads the unit-policy live fence (pytest fixture or unittest module hooks).
        fences = {'deployment/tests/test_deployment_hardening.py': "\nlive_runtime_fence = live_fence.pytest_fixture('unit')\n",
                  'deployment/tests/test_initialize_stores.py': "\nlive_runtime_fence = live_fence.pytest_fixture('unit')\n",
                  'deployment/tests/test_term_scan.py': "\nsetUpModule, tearDownModule = live_fence.unittest_module_hooks('unit')\n",
                  'deployment/tests/test_topology.py': "\nlive_runtime_fence = live_fence.pytest_fixture('unit')\n"}
        self.assertEqual(runner.GROUPS['deployment-hardening'], tuple(fences))
        self.assertEqual(runner.targets_for('deployment-hardening'), tuple(fences))
        self.assertIn('deployment-hardening', runner.RELEASE_PYTEST_GROUPS)
        self.assertNotIn('deployment-hardening', runner.DOCUMENTS_ROUTES)
        self.assertFalse({'deployment-hardening'} & (runner.APPROACH_PYTEST_GROUPS | runner.UNITS_PYTEST_GROUPS
                                                      | runner.AE_PYTEST_GROUPS | runner.FINDINGS_NATIVE_GROUPS
                                                      | runner.FOUNDRY_BROWSER_GROUPS))
        self.assertEqual(runner.GROUP_INTERPRETERS.get('deployment-hardening', fixture.APPROVED_PYTHON), fixture.APPROVED_PYTHON)
        for target, fence in fences.items():
            with self.subTest(target=target):
                text = (runner.REPO / target).read_text()
                self.assertIn(fence, text)
                self.assertNotIn('pytest.mark.skip', text)
                self.assertNotIn('pytest.skip(', text)

    def test_hardening_missing_target_refuses_before_allocation(self):
        with self.assertRaisesRegex(ValueError, 'Required target missing'):
            runner.targets_for('deployment-hardening', repo=self.scope.root / 'tmp/missing-hardening-target')
        with patch.object(runner, 'targets_for', side_effect=ValueError('Required target missing')), \
                patch.object(fixture, 'allocate_scope') as allocate:
            with self.assertRaisesRegex(ValueError, 'Required target missing'):
                runner.run_group('deployment-hardening')
            allocate.assert_not_called()

    def test_hardening_child_refuses_wrong_interpreter_before_collection(self):
        wrong = replace(self.scope, interpreter=fixture.APPROVED_CONTRACT_PYTHON)
        with patch.object(fixture, 'scope_from_environment', return_value=wrong), \
                patch.object(sys, 'executable', fixture.APPROVED_CONTRACT_PYTHON), \
                patch.object(runner, 'targets_for') as targets, patch.object(fixture, 'create_native_fixture') as native:
            with self.assertRaisesRegex(ValueError, 'reviewed interpreter'):
                runner.contracts_child('deployment-hardening')
            targets.assert_not_called()
            native.assert_not_called()

    def test_hardening_cli_accepts_no_arbitrary_target(self):
        for argv in (['--group', 'deployment-hardening', 'deployment/tests/test_repository_guard.py'],
                     ['--group', 'deployment-hardening', '-k', 'x'], ['--deployment-hardening-child', 'extra']):
            with self.subTest(argv=argv), patch.object(sys, 'argv', ['checks.py', *argv]), \
                    patch.object(fixture, 'allocate_scope') as allocate, patch('sys.stderr'):
                with self.assertRaises(SystemExit):
                    runner.main()
                allocate.assert_not_called()


class FoundryNavGuardTests(unittest.TestCase):
    """Closed isolated browser groups on the in-browser API double."""

    @classmethod
    def setUpClass(cls):
        cls.scope = fixture.scope_from_environment()

    def test_foundry_nav_group_is_closed_with_fixed_targets_and_application_interpreter(self):
        self.assertEqual(runner.GROUPS['foundry-nav'], (
            'deployment/tests/foundry_ui_fixture.py', 'ui/tests/foundry-fixtures.ts',
            'ui/tests/model-configuration-run.spec.ts', 'ui/tests/foundry-zoom.spec.ts',
            'ui/tests/DesignSpecimen.tsx'))
        self.assertEqual(runner.GROUPS['ported-isolated'], (
            'deployment/tests/foundry_ui_fixture.py', 'ui/tests/foundry-fixtures.ts',
            'ui/tests/command-recovery.spec.ts', 'ui/tests/history-races-isolated.spec.ts'))
        self.assertEqual(runner.GROUPS['ui-navigation'], (
            'deployment/tests/foundry_ui_fixture.py', 'ui/tests/foundry-fixtures.ts',
            'ui/tests/study-navigation.spec.ts'))
        self.assertEqual(runner.GROUPS['ui-reading'], (
            'deployment/tests/foundry_ui_fixture.py', 'ui/tests/foundry-fixtures.ts',
            'ui/tests/screen-readability.spec.ts', 'ui/tests/evidence-workspace.spec.ts',
            'ui/tests/record-labels.spec.ts', 'ui/tests/DesignSpecimen.tsx'))
        self.assertEqual(runner.GROUPS['ui-fidelity'], (
            'deployment/tests/foundry_ui_fixture.py', 'ui/tests/foundry-fixtures.ts',
            'ui/tests/prototype-fidelity.spec.ts'))
        self.assertEqual(runner.FOUNDRY_BROWSER_GROUPS,
                         {'foundry-nav', 'ported-isolated', 'ui-navigation', 'ui-reading', 'ui-fidelity'})
        for group in runner.FOUNDRY_BROWSER_GROUPS:
            self.assertEqual(runner.GROUP_INTERPRETERS[group], fixture.APPROVED_CONTRACT_PYTHON)
        self.assertFalse(runner.FOUNDRY_BROWSER_GROUPS & (runner.APPROACH_PYTEST_GROUPS | runner.UNITS_PYTEST_GROUPS
            | runner.AE_PYTEST_GROUPS | runner.RELEASE_PYTEST_GROUPS | runner.FINDINGS_NATIVE_GROUPS
            | set(runner.DOCUMENTS_ROUTES) | set(runner.AE_BROWSER_GROUPS) | set(runner.APPROACH_BROWSER_GROUPS)
            | set(runner.UNITS_BROWSER_GROUPS)))
        import foundry_ui_fixture as foundry
        self.assertEqual(foundry.GROUP_SPECS, {
            'foundry-nav': ('model-configuration-run.spec.ts', 'foundry-zoom.spec.ts'),
            'ported-isolated': ('command-recovery.spec.ts', 'history-races-isolated.spec.ts'),
            'ui-navigation': ('study-navigation.spec.ts',),
            'ui-reading': ('screen-readability.spec.ts', 'evidence-workspace.spec.ts', 'record-labels.spec.ts'),
            'ui-fidelity': ('prototype-fidelity.spec.ts',)})
        for group, specs in foundry.GROUP_SPECS.items():
            specimen = (('ui/tests/DesignSpecimen.tsx',)
                        if group in {'ui-reading', 'foundry-nav'} else ())
            self.assertEqual(tuple('ui/tests/' + spec for spec in specs) + specimen,
                             runner.GROUPS[group][2:])
        # Isolated specs never name another installation's ports or names, the development
        # application port, an installation's credentials or a default base URL. Ports and names
        # come from the environment the test-safety fence reads; none is written in source.
        paths = fixture.local_paths
        live = (*(str(port) for port in paths.live_ports()), *paths.live_names(),
                *((str(paths.port()),) if os.environ.get(paths.PORT) else ()),
                'credentials/owner.password', "goto('/ui")
        for spec in (spec for specs in foundry.GROUP_SPECS.values() for spec in specs):
            text = (runner.REPO / 'ui/tests' / spec).read_text()
            for value in live:
                self.assertNotIn(value, text, spec)

    def test_foundry_nav_missing_target_refuses_before_allocation(self):
        with self.assertRaisesRegex(ValueError, 'Required target missing'):
            runner.targets_for('foundry-nav', repo=self.scope.root / 'tmp/missing-foundry-target')
        with patch.object(runner, 'targets_for', side_effect=ValueError('Required target missing')), \
                patch.object(fixture, 'allocate_scope') as allocate:
            with self.assertRaisesRegex(ValueError, 'Required target missing'):
                runner.run_group('foundry-nav')
            allocate.assert_not_called()

    def test_foundry_nav_child_refuses_wrong_interpreter_or_scope_before_build(self):
        import foundry_ui_fixture as foundry
        # This guard child runs the native interpreter: the application-only child must refuse.
        with patch.object(foundry.subprocess, 'run') as spawned, patch.object(runner, 'targets_for') as targets:
            with self.assertRaisesRegex(ValueError, 'reviewed interpreter'):
                runner.foundry_browser_child('foundry-nav')
            with self.assertRaisesRegex(ValueError, 'reviewed application interpreter'):
                foundry.run(group='foundry-nav')
            targets.assert_not_called(); spawned.assert_not_called()
        with patch.object(fixture, 'scope_from_environment', side_effect=ValueError('Unscoped environment')), \
                patch.object(foundry.subprocess, 'run') as spawned:
            with self.assertRaisesRegex(ValueError, 'Unscoped environment'):
                runner.foundry_browser_child('foundry-nav')
            with self.assertRaisesRegex(ValueError, 'Unscoped environment'):
                foundry.run(group='foundry-nav')
            spawned.assert_not_called()
        with self.assertRaisesRegex(ValueError, 'Unknown foundry'):
            runner.foundry_browser_child('foundry-nav-x')
        with self.assertRaisesRegex(ValueError, 'Unknown foundry'):
            runner.foundry_browser_child('ported-isolated-x')

    def test_foundry_nav_environment_and_outputs_stay_in_scope(self):
        import foundry_ui_fixture as foundry
        env = foundry.browser_environment(self.scope)
        clean = fixture.clean_environment(self.scope)
        self.assertEqual(set(env) - set(clean), {'HYPRN_MVP_NAV_BUILD', 'HYPRN_MVP_UI_EVIDENCE_ROOT'})
        self.assertEqual({k: env[k] for k in clean}, clean)
        self.assertEqual(env['HYPRN_MVP_NAV_BUILD'], str(self.scope.root / 'artifacts/nav-dist'))
        self.assertEqual(env['HYPRN_MVP_UI_EVIDENCE_ROOT'], str(self.scope.root / 'evidence/nav'))
        config = foundry.browser_config(self.scope)
        self.assertEqual(config['testMatch'], list(foundry.SPECS))
        self.assertEqual(foundry.browser_config(self.scope, 'ported-isolated')['testMatch'],
                         ['command-recovery.spec.ts', 'history-races-isolated.spec.ts'])
        self.assertEqual((config['workers'], config['retries'], config['forbidOnly']), (1, 0, True))
        for key in ('outputDir', 'snapshotPathTemplate'):
            self.assertTrue(config[key].startswith(str(self.scope.root) + '/evidence/'), key)
        self.assertNotIn('baseURL', config['use'])  # Specs serve their own isolated origin.
        guarded = (runner.REPO / 'ui/tests/foundry-fixtures.ts').read_text()
        self.assertIn("build === scopeRoot + '/artifacts/nav-dist'", guarded)

    def test_foundry_nav_report_fails_closed(self):
        import foundry_ui_fixture as foundry
        good = dict(expected=7, unexpected=0, skipped=0, flaky=0)
        specs = set(foundry.SPECS)
        self.assertTrue(foundry.report_passed(0, good, specs, []))
        for returncode, stats, files, forbidden in (
                (1, good, specs, []), (0, {}, specs, []), (0, dict(good, expected=0), specs, []),
                (0, dict(good, skipped=1), specs, []), (0, dict(good, flaky=1), specs, []),
                (0, dict(good, unexpected=1), specs, []), (0, good, set(), []),
                (0, good, {'model-configuration-run.spec.ts'}, []), (0, good, specs | {'workspace.spec.ts'}, []),
                (0, good, specs, ['aiida'])):
            with self.subTest(returncode=returncode, stats=stats, files=files, forbidden=forbidden):
                self.assertFalse(foundry.report_passed(returncode, stats, files, forbidden))
        ported = set(foundry.GROUP_SPECS['ported-isolated'])
        self.assertTrue(foundry.report_passed(0, good, ported, [], 'ported-isolated'))
        self.assertFalse(foundry.report_passed(0, good, specs, [], 'ported-isolated'))
        self.assertFalse(foundry.report_passed(0, good, {'command-recovery.spec.ts'}, [], 'ported-isolated'))

    def test_foundry_nav_cli_accepts_no_arbitrary_target_or_module(self):
        for argv in (['--group', 'foundry-nav', 'ui/tests/workspace.spec.ts'], ['--group', 'foundry-nav', '--grep', 'x'],
                     ['--group', 'foundry-nav-x'], ['--foundry-nav-child', 'extra'],
                     ['--group', 'ported-isolated', 'ui/tests/workspace.spec.ts'], ['--ported-isolated-child', 'extra']):
            with self.subTest(argv=argv), patch.object(sys, 'argv', ['checks.py', *argv]), \
                    patch.object(fixture, 'allocate_scope') as allocate, patch('sys.stderr'):
                with self.assertRaises(SystemExit):
                    runner.main()
                allocate.assert_not_called()


class BrowserSpecRegistryTests(unittest.TestCase):
    """Every browser spec runs in a registered group; served and fidelity groups are opt-in and
    refuse before any scope or browser when what they need is absent."""

    @classmethod
    def setUpClass(cls):
        cls.scope = fixture.scope_from_environment()

    def test_every_browser_spec_is_registered_in_a_group(self):
        present = {str(p.relative_to(runner.REPO)) for p in (runner.REPO / 'ui/tests').rglob('*.spec.ts')}
        registered = runner.browser_specs()
        self.assertTrue(present)
        self.assertIn('exploration-ui', registered['ui/tests/exploration.spec.ts'])
        self.assertIn('browser', runner.group_needs('exploration-ui'))
        self.assertEqual(sorted(present - set(registered)), [], 'browser specs selected by no group')
        self.assertEqual(sorted(set(registered) - present), [], 'registered browser specs that do not exist')

    def test_opt_in_groups_are_the_served_and_fidelity_groups(self):
        self.assertEqual(runner.OPT_IN_GROUPS, {'ui-served', 'ui-fidelity'})
        for group in runner.OPT_IN_GROUPS:
            self.assertEqual(runner.group_class(group), 'opt-in')
            self.assertNotIn(group, runner.must_pass_groups())
        self.assertEqual(runner.group_needs('ui-served'), ('browser', 'installation'))
        self.assertEqual(runner.group_needs('ui-fidelity'), ('browser',))
        self.assertEqual(runner.group_class('ui-reading'), 'must-pass')
        self.assertIn('installation', runner.NEEDS)

    def test_fidelity_group_refuses_without_reference_images(self):
        empty = self.scope.root / 'tmp' / ('fidelity-' + uuid4().hex)
        empty.mkdir(parents=True)
        with patch.object(runner, 'REPO', empty), patch.object(fixture, 'allocate_scope') as allocate:
            with self.assertRaisesRegex(ValueError, 'reference absent'):
                runner.run_group('ui-fidelity')
            allocate.assert_not_called()

    def test_served_group_refuses_an_unnamed_live_or_development_installation(self):
        password = self.scope.root / 'tmp' / ('owner-' + uuid4().hex)
        password.write_text('synthetic owner password\n')
        live = self.scope.root / 'tmp' / ('live-' + uuid4().hex)
        live.mkdir()
        inside = live / 'owner.password'
        inside.write_text('synthetic\n')
        cases = (
            ({}, 'environment absent: installation'),
            ({runner.UI_BASE_URL: 'http://127.0.0.1:' + str(max(live_fence.LIVE_PORTS)), runner.UI_PASSWORD_FILE: str(password)},
             'live URLs denied'),
            ({runner.UI_BASE_URL: 'http://example.invalid:19000', runner.UI_PASSWORD_FILE: str(password)}, 'loopback'),
            ({runner.UI_BASE_URL: 'http://127.0.0.1:19111', runner.UI_PASSWORD_FILE: str(password),
              'HYPRN_MVP_PORT': '19111'}, 'development installation'),
            ({runner.UI_BASE_URL: 'http://127.0.0.1:19112', runner.UI_PASSWORD_FILE: 'owner.password'}, 'absolute path'),
            ({runner.UI_BASE_URL: 'http://127.0.0.1:19112', runner.UI_PASSWORD_FILE: str(inside),
              'HYPRN_MVP_LIVE_ROOTS': str(live)}, 'live root'),
        )
        for variables, message in cases:
            with self.subTest(message=message), \
                    patch.dict(os.environ, variables), \
                    patch.object(runner, 'need_present', side_effect=lambda need, v=variables: need != 'installation' or bool(v)), \
                    patch.object(runner.subprocess, 'run') as spawned, patch.object(fixture, 'allocate_scope') as allocate:
                with self.assertRaisesRegex(ValueError, message):
                    runner.run_group('ui-served')
                allocate.assert_not_called(); spawned.assert_not_called()

    def test_served_selection_cannot_narrow_qualification_or_other_groups(self):
        for group, selection in [('qualification', 'one'), ('guard', 'one'), ('ui-served', '')]:
            with self.subTest(group=group), patch.object(fixture, 'allocate_scope') as allocate:
                with self.assertRaisesRegex(ValueError, 'served-grep'):
                    runner.run_group(group, served_grep=selection)
                allocate.assert_not_called()
        with patch.object(runner, 'targets_for', return_value=['example.spec.ts']), \
                patch.object(runner, 'run_served', return_value=0) as served:
            self.assertEqual(runner.run_group('ui-served', served_grep='exact title'), 0)
            served.assert_called_once_with(
                'ui-served', ['example.spec.ts'], served_grep='exact title')

    def test_served_environment_adds_only_the_installation_variables(self):
        clean = fixture.clean_environment(self.scope)
        env = runner.served_child_environment(self.scope, 'http://127.0.0.1:19113', '/synthetic/owner.password')
        self.assertEqual(set(env) - set(clean), {runner.UI_BASE_URL, runner.UI_PASSWORD_FILE})
        self.assertEqual({k: env[k] for k in clean}, clean)

    def test_browser_specs_name_no_fixed_origin_password_location_or_scratch_path(self):
        # Fragments are joined so this guard never contains what it searches for.
        forbidden = (*('127.0.0.1:' + str(port) for port in sorted(live_fence.LIVE_PORTS)), 'credentials/' + 'owner.password',
                     '/private/' + 'tmp/', 'HYPRN_' + 'DATA_ROOT', 'HYPRN_' + 'CHROMIUM', 'HYPRN_' + 'UI_OUT')
        files = [*sorted((runner.REPO / 'ui/tests').rglob('*.ts')), runner.REPO / 'ui/playwright.config.ts',
                 runner.REPO / 'ui/playwright.isolated.config.ts', runner.REPO / 'ui/vite.config.ts']
        offenders = [(str(p.relative_to(runner.REPO)), term) for p in files for term in forbidden if term in p.read_text()]
        self.assertEqual(offenders, [])
        served = (runner.REPO / 'ui/tests/support/served.ts').read_text()
        for name in (runner.UI_BASE_URL, runner.UI_PASSWORD_FILE):
            self.assertIn('process.env.' + name, served)


class PythonTestModuleRegistryTests(unittest.TestCase):
    """Qualification cannot pass while a tracked Python test module silently never runs."""

    @staticmethod
    def tracked_test_modules():
        import subprocess
        listed = subprocess.run(['git', '-C', str(runner.REPO), 'ls-files', '-z', '--', '*/tests/test_*.py'],
                                capture_output=True, check=True, timeout=120).stdout.decode().split('\0')
        return {path for path in listed if path and re.fullmatch(r'(?:[^/]+/)+tests/test_[^/]+\.py', path)}

    def test_every_tracked_python_test_module_runs_in_a_must_pass_group_or_is_retired(self):
        tracked = self.tracked_test_modules()
        self.assertTrue(tracked)
        registered = runner.python_test_modules()
        must_pass = {path for path, groups in registered.items()
                     if any(runner.group_class(group) == 'must-pass' for group in groups)}
        retired = set(runner.RETIRED_TEST_MODULES)
        self.assertEqual(sorted(tracked - must_pass - retired), [],
                         'tracked test modules that no must-pass group runs and that are not retired')
        self.assertEqual(sorted(set(registered) - tracked), [], 'group targets that are not tracked test modules')

    def test_retired_test_modules_are_closed_tracked_and_never_group_targets(self):
        tracked = self.tracked_test_modules()
        registered = runner.python_test_modules()
        for path, reason in runner.RETIRED_TEST_MODULES.items():
            with self.subTest(path=path):
                self.assertIn(path, tracked)
                self.assertNotIn(path, registered, 'a retired test module may not be a group target')
                self.assertIsInstance(reason, str)
                self.assertTrue(reason.strip())
                self.assertNotIn('\n', reason)


class LocationResolutionTests(unittest.TestCase):
    """Every location comes from its own variable, else a neutral default below the data root,
    else a refusal naming the variable; no installation's folder is ever invented."""

    VARIABLES = {
        'native_python': ('HYPRN_MVP_NATIVE_PYTHON', 'dev/python-native/venv/bin/python'),
        'native_inventory': ('HYPRN_MVP_NATIVE_INVENTORY', 'dev/python-native'),
        'contract_python': ('HYPRN_MVP_CONTRACT_PYTHON', 'dev/python-contract/venv/bin/python'),
        'fixtures_root': ('HYPRN_MVP_TEST_FIXTURES_ROOT', 'fixtures'),
        'upstream_archive_root': ('HYPRN_MVP_UPSTREAM_CACHE', 'cache/upstream/whatsopt'),
        'evidence_root': ('HYPRN_MVP_EVIDENCE_ROOT', 'evidence'),
    }
    STORES = {'application_root': 'application', 'modeling_root': 'modeling', 'execution_root': 'execution',
              'releases_root': 'releases'}

    @classmethod
    def setUpClass(cls):
        cls.scope = fixture.scope_from_environment()
        cls.paths = fixture.local_paths

    def scratch(self, name):
        return str(self.scope.root / 'tmp' / 'locations' / name)

    def clean(self, **values):
        names = {variable for variable, _ in self.VARIABLES.values()} | {
            self.paths.DATA_ROOT, self.paths.SCRATCH_ROOT, self.paths.LIVE_ROOTS, self.paths.PORT}
        environment = {k: v for k, v in os.environ.items() if k not in names}
        return patch.dict(os.environ, {**environment, **values}, clear=True)

    def test_each_variable_overrides_its_default(self):
        data = self.scratch('data')
        for resolver, (variable, _) in self.VARIABLES.items():
            with self.subTest(variable=variable), self.clean(**{self.paths.DATA_ROOT: data, variable: self.scratch(variable)}):
                self.assertEqual(getattr(self.paths, resolver)(), Path(self.scratch(variable)))
            with self.subTest(variable=variable, data_root='unset'), self.clean(**{variable: self.scratch(variable)}):
                self.assertEqual(getattr(self.paths, resolver)(), Path(self.scratch(variable)))
        with self.clean(**{self.paths.SCRATCH_ROOT: self.scratch('scratch')}):
            self.assertEqual(self.paths.scratch_root(), Path(self.scratch('scratch')))
        with self.clean(**{self.paths.LIVE_ROOTS: os.pathsep.join((self.scratch('live-a'), self.scratch('live-b')))}):
            self.assertEqual(self.paths.live_roots(), (Path(self.scratch('live-a')), Path(self.scratch('live-b'))))
        with self.clean(**{self.paths.PORT: '54321'}):
            self.assertEqual(self.paths.port(), 54321)

    def test_defaults_are_neutral_and_below_the_data_root(self):
        data = self.scratch('data')
        with self.clean(**{self.paths.DATA_ROOT: data}):
            for resolver, (_, relative) in self.VARIABLES.items():
                with self.subTest(resolver=resolver):
                    self.assertEqual(getattr(self.paths, resolver)(), Path(data) / relative)
            for resolver, relative in self.STORES.items():
                with self.subTest(resolver=resolver):
                    self.assertEqual(getattr(self.paths, resolver)(), Path(data) / relative)
            self.assertEqual(self.paths.store_roots(), tuple(Path(data) / r for r in self.STORES.values()))
            self.assertEqual(self.paths.live_roots(), ())
            import tempfile
            self.assertEqual(self.paths.scratch_root(), Path(os.path.realpath(tempfile.gettempdir())))
            # No location names a retired runtime: the native environment is built from pins.
            self.assertFalse(hasattr(self.paths, 'old_runtime_root'))

    def test_unset_or_invalid_locations_refuse_with_a_message_naming_the_variable(self):
        with self.clean():
            for resolver, (variable, _) in self.VARIABLES.items():
                with self.subTest(resolver=resolver):
                    self.assertIsNone(getattr(self.paths, resolver)(required=False))
                    with self.assertRaisesRegex(self.paths.LocationUnset, variable):
                        getattr(self.paths, resolver)()
            for resolver in self.STORES:
                with self.subTest(resolver=resolver), self.assertRaisesRegex(self.paths.LocationUnset, self.paths.DATA_ROOT):
                    getattr(self.paths, resolver)()
            with self.assertRaisesRegex(self.paths.LocationUnset, self.paths.PORT):
                self.paths.port()
            self.assertIsNone(self.paths.port(required=False))
            with self.assertRaisesRegex(self.paths.LocationUnset, self.paths.NATIVE_PYTHON):
                self.paths.require_file(None, self.paths.NATIVE_PYTHON)
        with self.assertRaisesRegex(self.paths.LocationUnset, self.paths.NATIVE_PYTHON):
            self.paths.require_file(self.scope.root / 'tmp' / 'absent-python', self.paths.NATIVE_PYTHON)
        for variable, value in ((self.paths.DATA_ROOT, 'relative/root'), (self.paths.NATIVE_PYTHON, '/a/../b'),
                                (self.paths.LIVE_ROOTS, 'relative'), (self.paths.PORT, '80'), (self.paths.PORT, 'x')):
            with self.subTest(variable=variable, value=value), self.clean(**{variable: value}):
                with self.assertRaisesRegex(self.paths.LocationUnset, variable):
                    {self.paths.DATA_ROOT: self.paths.data_root, self.paths.NATIVE_PYTHON: self.paths.native_python,
                     self.paths.LIVE_ROOTS: self.paths.live_roots, self.paths.PORT: self.paths.port}[variable]()

    def test_scoped_children_receive_the_resolved_locations(self):
        env = fixture.clean_environment(self.scope)
        self.assertEqual(env[self.paths.SCRATCH_ROOT], str(fixture.SCRATCH_ROOT))
        self.assertEqual(env[self.paths.NATIVE_PYTHON], fixture.APPROVED_PYTHON)
        self.assertEqual(env[self.paths.CONTRACT_PYTHON], fixture.APPROVED_CONTRACT_PYTHON)
        self.assertEqual(self.scope.root.parent, fixture.SCRATCH_ROOT)
        self.assertTrue(self.scope.root.name.startswith(self.paths.SCOPE_PREFIX))
        if self.paths.live_roots():
            self.assertEqual(env[self.paths.LIVE_ROOTS], os.pathsep.join(map(str, self.paths.live_roots())))
        self.assertFalse({k for k in env if k.startswith('HYPRN_MVP_') and k not in (
            *self.paths.SCOPED_PASS_THROUGH, *self.paths.SCOPED_VALUES, self.paths.SCRATCH_ROOT, self.paths.LIVE_ROOTS)}
            - {'HYPRN_MVP_TEST_SCOPE_ROOT', 'HYPRN_MVP_TEST_SCOPE_PROFILE', 'HYPRN_MVP_TEST_SCOPE_URL'})

    def test_location_code_names_no_installation_folder(self):
        source = (runner.REPO / 'deployment/local_paths.py').read_text()
        code = source[source.index('"""', 3) + 3:]
        # Assembled so this file names no home or system folder itself.
        for fragment in ('workspace-', 'probe-' + '01', '/' + 'private/', '/' + 'Users/', '/' + 'home/',
                         'Lib' + 'rary/', 'App' + 'Data'):
            with self.subTest(fragment=fragment):
                self.assertNotIn(fragment, code)


class LiveFenceTests(unittest.TestCase):
    """Shared live-runtime fence decisions (pure; no live access is attempted)."""

    def test_a_dedicated_scratch_root_below_the_data_root_is_the_only_usable_place_there(self):
        fence = live_fence
        data = fence.DATA_ROOT
        scratch = data + '/scratch'
        blocked = (data + '/application', data + '/evidence', data + '/fixtures', data + '/dev/python-native')
        self.assertEqual(fence._test_areas(scratch, data, blocked), (scratch,))
        # Never the data root itself, a folder outside it, or one that overlaps a protected location.
        for candidate in (data, data + '/application', data + '/application/scratch', data + '/fixtures/scratch',
                          data + '/dev', str(Path(data).parent / 'scratch')):
            with self.subTest(candidate=candidate):
                self.assertEqual(fence._test_areas(candidate, data, blocked), ())
        written = scratch + '/' + fixture.SCOPE_PREFIX + str(uuid4())
        with patch.object(fence, 'TEST_AREAS', (scratch,)):
            for policy in ('baseline', 'unit'):
                self.assertIsNone(fence.decide('open', (written + '/evidence/x.json', 'w', os.O_WRONLY | os.O_CREAT), policy))
            self.assertIsNone(fence.decide('subprocess.Popen', (None, ['docker', 'run', '--mount',
                'type=bind,src=' + written + '/artifacts/store,dst=/store', 'image'], None, None), 'baseline'))
            for path in (data + '/scratchy/x', data + '/application/x', data + '/x', data + '/fixtures/x'):
                with self.subTest(path=path):
                    self.assertIsNotNone(fence.decide('open', (path, 'w', os.O_WRONLY | os.O_CREAT), 'baseline'))
                    self.assertIsNotNone(fence.decide('subprocess.Popen', (None, ['docker', 'run', '--mount',
                        'type=bind,src=' + path + ',dst=/x', 'image'], None, None), 'baseline'))

    def test_data_root_stores_and_live_roots_are_refused_and_development_locations_are_read_only(self):
        fence = live_fence
        data = fence.DATA_ROOT
        interpreter = fixture.APPROVED_PYTHON
        refused = [
            # Any folder below the data root, including layouts that no longer exist.
            ('open', (data + '/retired-layout/execution/executor.lock', 'r', os.O_RDONLY)),
            ('open', (data + '/retired-layout/execution/executor.lock', None, os.O_RDWR | os.O_CREAT)),
            ('sqlite3.connect', (data + '/retired-layout/application/app.sqlite3',)),
            ('os.listdir', (data + '/another-layout/stores',)),
            ('open', (data + '/retired-runtime/native/x', 'rb', os.O_RDONLY)),
            ('open', (data + '/releases/r/manifest.json', 'r', os.O_RDONLY)),
            # The development installation's stores and evidence.
            ('open', (data + '/execution/executor.lock', 'r', os.O_RDONLY)),
            ('open', (data + '/execution/executor.lock', None, os.O_RDWR | os.O_CREAT)),
            ('sqlite3.connect', (data + '/application/application/application.sqlite',)),
            ('os.mkdir', (data + '/modeling/new', 0o700, -1)),
            ('shutil.copyfile', (str(self.scope_root()) + '/x', data + '/releases/x')),
            ('open', (str(fixture.local_paths.evidence_root()) + '/x.json', 'w', os.O_WRONLY | os.O_CREAT)),
            ('open', (data + '/fixtures/../execution/runtime.json', 'rb', os.O_RDONLY)),
            # Development interpreters, inventory, fixtures and cache are never written.
            ('open', (interpreter, 'wb', os.O_WRONLY | os.O_TRUNC)),
            ('os.remove', (interpreter, -1)),
            ('open', (str(fixture.local_paths.native_inventory()) + '/selected.json', 'w', os.O_WRONLY)),
            ('os.mkdir', (str(fixture.local_paths.fixtures_root()) + '/new', 0o700, -1)),
            ('os.chmod', (str(fixture.local_paths.upstream_archive_root()) + '/x', 0o600, -1, True)),
        ]
        for root in fence.READ_ONLY_ROOTS:  # Including link targets inside a live root.
            refused.append(('open', (root + '/x', 'wb', os.O_WRONLY | os.O_CREAT)))
            self.assertIsNone(fence.decide('open', (root + '/x', 'rb', os.O_RDONLY), 'unit'), root)
            self.assertIsNone(fence.decide('os.scandir', (root + '/x',), 'unit'), root)
        for root in fence.LIVE_ROOTS:
            self.assertNotIn(root, fence.READ_ONLY_ROOTS)
        for event, args in refused:
            for policy in ('baseline', 'unit'):
                with self.subTest(event=event, args=args, policy=policy):
                    self.assertIsNotNone(fence.decide(event, args, policy))
        for event, args in (('open', (interpreter, 'rb', os.O_RDONLY)),
                            ('subprocess.Popen', (None, [interpreter, '-B', '-c', 'pass'], None, None)),
                            ('import', ('json', None, [str(Path(interpreter).parents[1] / 'lib/python3.12/site-packages')], [], [])),
                            ('open', (str(fixture.local_paths.native_inventory()) + '/selected.json', 'rb', os.O_RDONLY)),
                            ('os.listdir', (str(fixture.local_paths.fixtures_root()),)),
                            ('open', (str(self.scope_root()) + '/evidence/x.json', 'w', os.O_WRONLY | os.O_CREAT))):
            with self.subTest(event=event, args=args):
                self.assertIsNone(fence.decide(event, args, 'unit'))

    def live_roots(self):
        """The configured live roots, plus one synthetic root so the refusals are always exercised."""
        return (*live_fence.LIVE_ROOTS, str(self.scope_root() / 'tmp' / 'synthetic-live-root'))

    def test_writes_mounts_and_container_operations_inside_each_live_root_are_refused(self):
        fence = live_fence
        popen = lambda *argv: (None, list(argv), None, None)  # noqa: E731
        for root in self.live_roots():
            roots = fence.LIVE_ROOTS if root in fence.LIVE_ROOTS else (*fence.LIVE_ROOTS, root)
            with patch.object(fence, 'LIVE_ROOTS', roots):
                cases = [
                    ('open', (root + '/store/application.sqlite', 'w', os.O_WRONLY | os.O_CREAT)),
                    ('open', (root + '/store/application.sqlite', 'rb', os.O_RDONLY)),
                    ('os.rename', (str(self.scope_root()) + '/x', root + '/x', -1, -1)),
                    ('shutil.rmtree', (root + '/store',)),
                    ('sqlite3.connect', (root + '/store/application.sqlite',)),
                    # Mounts: bind sources inside the live root.
                    ('subprocess.Popen', popen('docker', 'run', '--rm', '--mount',
                                               'type=bind,source=' + root + '/store,target=/store', 'image')),
                    ('subprocess.Popen', popen('docker', 'run', '--rm', '-v', root + ':/data:ro', 'image')),
                    ('subprocess.Popen', popen('docker', 'create', '--volume=' + root + '/store:/store', 'image')),
                    # Container operations naming a path inside the live root.
                    ('subprocess.Popen', popen('docker', 'cp', root + '/store/x', 'container:/x')),
                    ('subprocess.Popen', popen('docker', 'cp', 'container:/x', root + '/store/x')),
                    ('subprocess.Popen', popen('docker', 'build', '-t', 'image:tag', root)),
                    ('subprocess.Popen', popen(fixture.APPROVED_PYTHON, root + '/start.py')),
                ]
                for event, args in cases:
                    for policy in ('baseline', 'unit'):
                        with self.subTest(root=root, event=event, args=args, policy=policy):
                            self.assertIsNotNone(fence.decide(event, args, policy))
                # A sibling whose name only starts like the live root is not inside it.
                self.assertIsNone(fence.decide('open', (root + '-sibling/x', 'rb', os.O_RDONLY), 'baseline'))
                self.assertIsNone(fence.decide('subprocess.Popen', popen('docker', 'run', '-v', root + '-sibling:/x', 'i'),
                                               'baseline'))
        # Store mounts are refused as well, and scope paths stay allowed.
        for source in (fence.DATA_ROOT + '/execution', fence.DATA_ROOT + '/application/application'):
            self.assertIsNotNone(fence.decide('subprocess.Popen', popen(
                'docker', 'run', '--mount', 'type=bind,src=' + source + ',dst=/store', 'image'), 'baseline'))
        self.assertIsNone(fence.decide('subprocess.Popen', popen(
            'docker', 'run', '--mount', 'type=bind,source=' + str(self.scope_root()) + '/tmp,target=/input,readonly',
            'image'), 'baseline'))

    def scope_root(self):
        return fixture.scope_from_environment().root

    def test_live_ports_programs_entry_points_and_docker(self):
        fence = live_fence
        # Every configured live port and the development port are refused.
        self.assertTrue(set(fixture.local_paths.live_ports()) <= fence.LIVE_PORTS)
        with patch.object(fence, 'LIVE_PORTS', frozenset({19461, 19467})):
            for port in (19461, 19467):
                self.assertIsNotNone(fence.decide('socket.connect', (None, ('127.0.0.1', port)), 'baseline'))
            self.assertIsNone(fence.decide('socket.connect', (None, ('127.0.0.1', 54321)), 'unit'))
        # Installation names of this product and of any configured other installation are refused.
        self.assertTrue(set(fixture.local_paths.live_names()) <= fence.LIVE_DOCKER_NAMES)
        self.assertTrue(fence.INSTALLATION_DOCKER_NAMES <= fence.LIVE_DOCKER_NAMES)
        popen = lambda *argv: (None, list(argv), None, None)  # noqa: E731
        with patch.object(fence, 'LIVE_DOCKER_NAMES', fence.LIVE_DOCKER_NAMES | {'other-installation-modeling'}):
            self.assertIsNotNone(fence.decide('subprocess.Popen', popen('docker', 'stop', 'other-installation-modeling'), 'baseline'))
        for argv in (('launchctl', 'list'), ('/usr/bin/curl', 'http://127.0.0.1:19467'), ('kill', '-9', '1'),
                     (sys.executable, 'deployment/modeling_runtime.py', 'stop'),
                     (fixture.APPROVED_PYTHON, '-B', 'deployment/dispatch_runtime.py', '--serve'),
                     ('python3', 'deployment/application_runtime.py', 'setup'),
                     ('python3', 'deployment/initialize_stores.py', 'bootstrap'),
                     ('python3', 'deployment/manage.py', 'verify-isolation'),
                     ('docker', 'exec', 'hyprn-mvp-modeling', 'ruby'), ('docker', 'compose', 'down'),
                     ('docker', 'network', 'rm', 'hyprn-mvp-private'), ('docker', 'stop', 'hyprn-mvp-application')):
            for policy in ('baseline', 'unit'):
                with self.subTest(argv=argv, policy=policy):
                    self.assertIsNotNone(fence.decide('subprocess.Popen', popen(*argv), policy))
        fixture_docker = popen('docker', 'image', 'inspect', 'hyprn-mvp-worker:0123456789abcdef')
        self.assertIsNone(fence.decide('subprocess.Popen', fixture_docker, 'baseline'))
        self.assertIsNotNone(fence.decide('subprocess.Popen', fixture_docker, 'unit'))
        socket_path = str(fixture.local_paths.account_home() / '.docker/run/docker.sock')
        self.assertIsNotNone(fence.decide('socket.connect', (None, socket_path), 'unit'))
        self.assertIsNotNone(fence.decide('os.system', ('true',), 'baseline'))

    def test_user_installations_are_never_read_written_mounted_or_named(self):
        fence = live_fence
        popen = lambda *argv: (None, list(argv), None, None)  # noqa: E731
        policy = fence._path_policy()
        environ = {**os.environ, 'HOME': str(fixture.local_paths.account_home())}
        config = str(policy.default('config', environ=environ))
        data = str(policy.default('data_root', environ=environ))
        self.assertIn(config, fence.INSTALLATION_CONFIGS)
        mount = 'type=bind,src=' + data + '/modeling,dst=/x'
        refused = [
            ('open', (config, 'rb', os.O_RDONLY)),
            ('open', (config, 'w', os.O_WRONLY | os.O_CREAT)),
            ('os.listdir', (data,)),
            ('sqlite3.connect', (data + '/application/application/application.sqlite',)),
            ('subprocess.Popen', popen('docker', 'run', '--mount', mount, 'i')),
        ]
        prefix = 'hyprn-mvp-local-0123abcd'
        owner = 'org.hyprn-mvp.owner=hyprn-mvp-local-' + str(uuid4())
        for argv in (
            ('docker', 'stop', prefix + '-modeling'),
            ('docker', 'network', 'rm', prefix + '-public'),
            ('docker', 'ps', '--filter', 'label=' + owner),
            ('docker', 'run', '--label', owner, 'image'),
        ):
            refused.append(('subprocess.Popen', popen(*argv)))
        for event, args in refused:
            for policy_name in ('baseline', 'unit'):
                with self.subTest(event=event, args=args, policy=policy_name):
                    self.assertIsNotNone(fence.decide(event, args, policy_name))
        # A test scope's own names stay usable.
        scoped = popen('docker', 'stop', fixture.SCOPE_PREFIX + '0123abcd-modeling')
        self.assertIsNone(fence.decide('subprocess.Popen', scoped, 'baseline'))

    def test_a_configured_installation_adds_its_data_root_cache_and_port(self):
        folder = fixture.scope_from_environment().root / 'tmp' / ('installation-' + uuid4().hex)
        folder.mkdir(parents=True)
        data = str(folder / 'data')
        config = folder / 'installation.json'
        named = {'data_root': data, 'upstream': {'cache': data + '/cache'}, 'ports': {'app': 19999}}
        config.write_text(json.dumps(named))
        named_only = {'HYPRN_MVP_CONFIG': str(config)}
        configs, roots, ports = live_fence.installations(named_only, defaults=False)
        self.assertIn(str(config), configs)
        self.assertTrue({data, data + '/cache'} <= set(roots))
        self.assertIn(19999, ports)
        # A configuration that cannot be read as JSON still protects its own file.
        config.write_text('{')
        configs, roots, ports = live_fence.installations(named_only, defaults=False)
        self.assertIn(str(config), configs)
        self.assertNotIn(data, roots)

    def test_entry_points_named_by_the_fence_exist_in_the_repository(self):
        present = {p.name for p in (runner.REPO / 'deployment').rglob('*') if p.is_file()}
        self.assertEqual(sorted(live_fence.LIVE_ENTRYPOINTS - present), [])

    def test_signals_only_to_own_children_and_never_in_unit_tests(self):
        fence = live_fence
        child = 4242424
        fence.STATE.children.add(child)
        try:
            self.assertIsNone(fence.decide('os.kill', (child, 15), 'baseline'))
            self.assertIsNone(fence.decide('os.killpg', (child, 9), 'baseline'))
            self.assertIsNotNone(fence.decide('os.kill', (child, 15), 'unit'))
            self.assertIsNotNone(fence.decide('os.kill', (1, 15), 'baseline'))
            self.assertIsNone(fence.decide('os.kill', (1, 0), 'unit'))  # Liveness probe only.
        finally:
            fence.STATE.children.discard(child)

    def test_hook_records_and_raises_and_fixture_fails_caught_trips(self):
        fence = live_fence
        previous = fence.enter('unit')
        try:
            with self.assertRaises(fence.LiveRuntimeAccess):
                open(fence.DATA_ROOT + '/execution/executor.json', 'rb')
            self.assertEqual(len(fence.STATE.trips), 1)
            with self.assertRaisesRegex(AssertionError, 'Live-runtime fence trips'):
                fence.leave(previous)
        finally:
            fence.STATE.trips.clear()
            fence.STATE.policy = 'unit'  # the unit policy declared by setUpModule applies again
        with self.assertRaises(ValueError):
            fence.enter('permissive')

    def test_fenced_deployment_modules_are_declared(self):
        for name, policy in (('test_bridge.py', "pytest_fixture('unit')"),
                             ('test_initialize_stores.py', "pytest_fixture('unit')"), ('test_topology.py', "pytest_fixture('unit')"),
                             ('test_deployment_hardening.py', "pytest_fixture('unit')"),
                             ('test_repository_guard.py', "unittest_module_hooks('unit')"),
                             ('test_naming_guard.py', "unittest_module_hooks('unit')"),
                             ('test_hygiene_guard.py', "unittest_module_hooks('unit')"),
                             ('test_term_scan.py', "unittest_module_hooks('unit')"),
                             ('test_findings_native_guards.py', "unittest_module_hooks('unit')"),
                             ('test_units_fixture_guards.py', "unittest_module_hooks('baseline')"),
                             *((name, "pytest_fixture('baseline')") for name in (
                                 'test_native_journey.py', 'test_units_native.py', 'test_approach_native.py',
                                 'test_assumptions_evidence_journey.py', 'test_investigation_native.py',
                                 'test_findings_native.py', 'test_attestation.py',
                                 'test_modeling_isolation.py',
                                 'test_exploration_native.py', 'test_exploration_ui.py'))):
            with self.subTest(module=name):
                text = (runner.REPO / 'deployment/tests' / name).read_text()
                self.assertIn('live_fence.' + policy, text)
        # Every deployment test module declares a fence policy.
        modules = {p.name for p in (runner.REPO / 'deployment/tests').glob('test_*.py')}
        for name in modules:
            with self.subTest(unfenced=name):
                tree = ast.parse((runner.REPO / 'deployment/tests' / name).read_text())
                self.assertTrue(any(
                    isinstance(node, ast.Import) and any(
                        alias.name == 'live_fence' and alias.asname in (None, 'live_fence')
                        for alias in node.names) for node in tree.body), 'fence import absent')
                declarations = [
                    node for statement in tree.body
                    if isinstance(statement, (ast.Assign, ast.AnnAssign, ast.Expr))
                    for node in ast.walk(statement) if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == 'live_fence'
                    and node.func.attr in ('pytest_fixture', 'unittest_module_hooks')
                ]
                self.assertTrue(declarations, 'fence policy declaration absent')


class DurableFixtureGuardTests(unittest.TestCase):
    """Retained runs must come from the manifest-verified durable fixture, never from scoped folders."""

    UUID = r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})'
    # A scoped folder, or any fixed temporary folder named by a run UUID, written into a source
    # would be a retained run; split so this guard's own source never matches what it forbids.
    RETAINED_SCOPE = re.compile('(?:' + re.escape(fixture.SCOPE_PREFIX) + '|' + '/private/tmp/' + r'[A-Za-z0-9_.-]+-)' + UUID)
    # Any fixed, named folder below the temporary root (retained evidence of an earlier run).
    RETAINED_EVIDENCE = re.compile('/private/tmp/' + r'[A-Za-z0-9_.]+-[A-Za-z0-9_.-]+')

    def test_no_fixture_references_retained_tmp_scopes(self):
        files = [*sorted((runner.REPO / 'deployment/tests').glob('*.py')),
                 *sorted(p for p in (runner.REPO / 'ui/tests').rglob('*') if p.suffix in ('.ts', '.tsx', '.js', '.mjs', '.json'))]
        self.assertTrue(files)
        offenders = []
        for path in files:
            text = path.read_text()
            # Single-digit sentinel UUIDs (e.g. all 'a') are synthetic refusal inputs, not scopes.
            offenders += [(path.name, m.group(0)) for m in self.RETAINED_SCOPE.finditer(text)
                          if len(set(m.group(1).replace('-', ''))) > 1]
            offenders += [(path.name, m.group(0)) for m in self.RETAINED_EVIDENCE.finditer(text)]
        self.assertEqual(offenders, [])
        for name in ('approach_ui_fixture.py', 'findings_native_fixture.py'):
            self.assertIn('durable_fixture.', (runner.REPO / 'deployment/tests' / name).read_text())

    @classmethod
    def setUpClass(cls):
        cls.scope = fixture.scope_from_environment()

    @staticmethod
    def rewrite(path, raw):
        path.parent.chmod(0o700)
        path.chmod(0o600)
        path.write_bytes(raw)
        path.chmod(0o400)

    def test_resolver_verifies_pinned_manifest_and_closed_inventory(self):
        durable, root, digest, _, _, _ = self.native_synthetic('ok')
        self.assertEqual(durable.manifest(root, digest)['name'], root.name)
        with patch.object(durable, 'NATIVE_FIXTURE', root), patch.object(durable, 'NATIVE_MANIFEST_SHA256', digest):
            self.assertEqual(durable.application_store(), root / 'scope/artifacts/combined.sqlite')
            self.assertEqual(durable.reuse_manifest(), root / 'reuse/fixture-reuse.json')
            with self.assertRaisesRegex(durable.FixtureUnavailable, 'does not contain'):
                durable.verified_file('scope/native/other.sqlite')
        # A fixture without its native scope description is not a retained native fixture.
        record = json.loads((root / 'manifest.json').read_bytes())
        for spec, reason in ((None, 'malformed'), (dict(record['native_scope'], prefix='other'), 'malformed'),
                             (dict(record['native_scope'], root=str(self.scope.root)), 'scratch root')):
            raw = json.dumps(dict(record, native_scope=spec)).encode()
            self.rewrite(root / 'manifest.json', raw)
            with self.subTest(spec=spec), self.assertRaisesRegex(durable.FixtureUnavailable, reason):
                durable.manifest(root, hashlib.sha256(raw).hexdigest())

    def test_resolver_fails_closed_when_absent_changed_or_extended(self):
        durable, root, digest, _, _, _ = self.native_synthetic('refusals')
        with self.assertRaisesRegex(durable.FixtureUnavailable, 'absent'):
            durable.manifest(root.with_name('durable-missing'), digest)
        with self.assertRaisesRegex(durable.FixtureUnavailable, 'SHA256 mismatch'):
            durable.manifest(root, '0' * 64)
        artifacts = root / 'scope/artifacts'
        artifacts.chmod(0o700)
        sidecar = artifacts / 'combined.sqlite-journal'
        sidecar.write_bytes(b'')
        sidecar.chmod(0o400)
        with self.assertRaisesRegex(durable.FixtureUnavailable, 'Unlisted'):
            durable.manifest(root, digest)
        sidecar.unlink()
        store = artifacts / 'combined.sqlite'
        store.chmod(0o600)
        with self.assertRaisesRegex(durable.FixtureUnavailable, 'writable'):
            durable.manifest(root, digest)
        store.write_bytes(b'changed store!!')
        store.chmod(0o400)
        artifacts.chmod(0o500)
        with patch.object(durable, 'NATIVE_FIXTURE', root), patch.object(durable, 'NATIVE_MANIFEST_SHA256', digest):
            with self.assertRaisesRegex(durable.FixtureUnavailable, 'changed'):
                durable.application_store()
        link = root.with_name('durable-link')
        link.symlink_to(root, target_is_directory=True)
        with self.assertRaises(ValueError):
            durable.manifest(link, digest)

    def producer(self, *, passed=True):
        """Synthetic finished producer scope: seven recorded runs and one specific-energy pair."""
        import sqlite3
        import durable_fixture
        scope = fixture.allocate_scope(fixture.new_scope())
        self.addCleanup(self.release_tree, scope.root)
        runs = [str(uuid4()) for _ in range(durable_fixture.RETAINED_RUNS)]
        source, downstream, study = runs[0], runs[1], str(uuid4())
        violated, digest = str(uuid4()), 'd' * 64
        with sqlite3.connect(scope.root / 'artifacts/combined.sqlite') as db:
            db.execute('CREATE TABLE outbox (run_id TEXT PRIMARY KEY, state TEXT, payload TEXT)')
            db.execute('CREATE TABLE run_associations (run_id TEXT PRIMARY KEY, study_id TEXT, store_uuid TEXT, process_uuid TEXT)')
            for run_id in runs:
                process = str(uuid4())
                binding = dict(source_run_id=source, results_digest=digest) if run_id == downstream else None
                criteria = [dict(criterion_id=str(uuid4()), outcome='met')]
                if run_id == source:
                    criteria.append(dict(criterion_id=violated, outcome='violated'))
                payload = dict(frozen=dict(configuration=dict(configuration_revision_id=str(uuid4()), model_revision_id=str(uuid4()),
                    name=durable_fixture.DOWNSTREAM_CONFIGURATION if run_id == downstream else 'Other ' + run_id,
                    inputs=[dict(result_binding=binding)])),
                    history=dict(association=dict(process_uuid=process), results=dict(criteria=criteria)))
                db.execute('INSERT INTO outbox VALUES (?,?,?)', (run_id, 'recorded', json.dumps(payload)))
                db.execute('INSERT INTO run_associations VALUES (?,?,?,?)', (run_id, study, scope.store_uuid, process))
        db.close()
        (scope.root / 'native/database.sqlite').write_bytes(b'synthetic native store')
        modeling = scope.root / 'artifacts/private-http/modeling'
        modeling.mkdir(parents=True)
        for name in ('model.sqlite3', 'scratch.sqlite3'):
            (modeling / name).write_bytes(b'synthetic modeling store')
        evidence = scope.root / 'evidence'
        (evidence / 'result.json').write_text(json.dumps(dict(group=durable_fixture.PRODUCER_GROUP, exit=0, scope=scope.record(),
            duration_seconds=1.0, source_sha256={'deployment/tests/test_units_native.py': 'e' * 64})))
        (evidence / 'tests.json').write_text(json.dumps(dict(tests=14, passed=passed, failures=0, skipped=0)))
        (evidence / 'units-native-proof.json').write_text(json.dumps(dict(passed=True,
            attestation=dict(fingerprint=dict(image='sha256:' + 'f' * 64)))))
        return durable_fixture, scope, dict(source=source, downstream=downstream, study=study, violated=violated, digest=digest)

    def test_capture_writes_a_new_verified_fixture_from_a_passing_producer_scope(self):
        durable, scope, expected = self.producer()
        destination = self.scope.root / 'tmp/captured-fixtures'
        destination.mkdir(mode=0o700)
        with patch('subprocess.run', return_value=Mock(returncode=0, stdout='', stderr='')) as docker:
            folder, digest = durable.capture(scope.root, destination, created_utc='20260101T000000Z')
        self.assertIn('label=org.hyprn-mvp.test-scope=' + scope.run_uuid, docker.call_args.args[0])
        record = durable.manifest(folder, digest)
        self.assertEqual((record['name'], record['kind']), ('native-20260101T000000Z', durable.NATIVE_KIND))
        identities = record['identities']
        self.assertEqual((identities['run_uuid'], identities['store_uuid'], identities['study_id']),
                         (scope.run_uuid, scope.store_uuid, expected['study']))
        self.assertEqual((identities['source_run'], identities['downstream_run'], identities['violated_criterion'],
                          identities['source_results_digest']),
                         (expected['source'], expected['downstream'], expected['violated'], expected['digest']))
        self.assertEqual(record['native_scope']['root'], str(scope.root))
        self.assertEqual(record['provenance']['human_acceptance'], 'pending')
        # Exact producer bytes, exact outbox payload bytes and the closed reuse inventory.
        self.assertEqual((folder / 'scope/scope.json').read_bytes(), (scope.root / 'scope.json').read_bytes())
        reuse = json.loads((folder / 'reuse/fixture-reuse.json').read_bytes())
        self.assertEqual(hashlib.sha256((folder / 'reuse/fixture-reuse.json').read_bytes()).hexdigest(), identities['reuse_sha256'])
        self.assertEqual((reuse['scope'], len(reuse['records'])), (str(scope.root), durable.RETAINED_RUNS))
        import sqlite3
        with sqlite3.connect(scope.root / 'artifacts/combined.sqlite') as db:
            for run_id, payload in db.execute('SELECT run_id,payload FROM outbox'):
                self.assertEqual((folder / 'reuse/retained' / (run_id + '.json')).read_bytes(), payload.encode())
        db.close()
        with self.assertRaisesRegex(durable.FixtureUnavailable, 'already exists'), \
                patch('subprocess.run', return_value=Mock(returncode=0, stdout='', stderr='')):
            durable.capture(scope.root, destination, created_utc='20260101T000000Z')
        self.release_tree(folder)

    def test_capture_refuses_a_failing_or_busy_producer_and_writes_nothing(self):
        destination = self.scope.root / 'tmp/refused-fixtures'
        destination.mkdir(mode=0o700)
        durable, failing, _ = self.producer(passed=False)
        with patch('subprocess.run', return_value=Mock(returncode=0, stdout='', stderr='')):
            with self.assertRaisesRegex(durable.FixtureUnavailable, 'fully passing'):
                durable.capture(failing.root, destination)
        durable, busy, _ = self.producer()
        with patch('subprocess.run', return_value=Mock(returncode=0, stdout='container\n', stderr='')):
            with self.assertRaisesRegex(durable.FixtureUnavailable, 'containers'):
                durable.capture(busy.root, destination)
        (busy.root / 'artifacts/combined.sqlite-wal').write_bytes(b'uncheckpointed')
        with patch('subprocess.run', return_value=Mock(returncode=0, stdout='', stderr='')):
            with self.assertRaisesRegex(durable.FixtureUnavailable, 'not quiescent'):
                durable.capture(busy.root, destination)
        self.assertEqual(list(destination.iterdir()), [])

    def native_synthetic(self, label):
        """Synthetic retained native fixture whose working root is a fresh guard-convention path."""
        import durable_fixture
        run_uuid = str(uuid4())
        root = self.scope.root / 'tmp' / ('durable-native-' + label)
        modes = {'.': 0o700, 'artifacts': 0o755, 'artifacts/private': 0o777, 'native': 0o700, 'empty': 0o700,
                 'artifacts/combined.sqlite': 0o644, 'artifacts/private/model.key': 0o444, 'native/database.sqlite': 0o600}
        content = {'artifacts/combined.sqlite': b'synthetic store', 'artifacts/private/model.key': b'synthetic key',
                   'native/database.sqlite': b'synthetic native'}
        files = {}
        for relative, raw in [*(('scope/' + r, b) for r, b in content.items()), ('reuse/fixture-reuse.json', b'{}')]:
            (root / relative).parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            (root / relative).write_bytes(raw)
            (root / relative).chmod(0o400)
            files[relative] = dict(size=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        (root / 'scope/empty').mkdir(mode=0o700)
        for directory in sorted((p for p in root.rglob('*') if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
            directory.chmod(0o500)
        root.chmod(0o700)
        identities = {name: 'x' for name in durable_fixture.IDENTITY_FIELDS}
        identities.update(run_uuid=run_uuid, reuse_sha256=files['reuse/fixture-reuse.json']['sha256'])
        raw = json.dumps(dict(schema_version='1', kind=durable_fixture.NATIVE_KIND, name=root.name, identities=identities,
                              native_scope=dict(root=str(durable_fixture.scope_root(run_uuid)), prefix='scope', modes=modes),
                              files=files)).encode()
        (root / 'manifest.json').write_bytes(raw)
        (root / 'manifest.json').chmod(0o400)
        working = durable_fixture.scope_root(run_uuid)
        self.addCleanup(self.release_tree, working)
        return durable_fixture, root, hashlib.sha256(raw).hexdigest(), working, content, modes

    @staticmethod
    def release_tree(path):
        if not os.path.lexists(path):
            return
        for entry in sorted(path.rglob('*'), key=lambda p: len(p.parts), reverse=True):
            if entry.is_dir():
                entry.chmod(0o700)
                entry.rmdir()
            else:
                entry.parent.chmod(0o700)
                entry.unlink()
        path.chmod(0o700)
        path.rmdir()

    def test_native_fixture_materializes_exact_bytes_modes_and_binding(self):
        durable, root, digest, working, content, modes = self.native_synthetic('materialize')
        self.assertFalse(os.path.lexists(working))
        self.assertEqual(durable.native_scope_available(root, digest)['kind'], durable.NATIVE_KIND)
        self.assertEqual(durable.native_scope(root, digest), working)
        for relative, raw in content.items():
            self.assertEqual((working / relative).read_bytes(), raw)
        for relative, mode in modes.items():
            self.assertEqual(stat_mode(working / relative if relative != '.' else working), mode, relative)
        self.assertEqual(json.loads((working / durable.MATERIALIZATION).read_bytes()),
                         dict(fixture=root.name, manifest_sha256=digest))
        # The working copy is mutable by design (continuation journals); the bound root is adopted.
        (working / 'native/database.sqlite').write_bytes(b'continued')
        self.assertEqual(durable.native_scope(root, digest), working)
        self.assertEqual(durable.manifest(root, digest)['name'], root.name)  # Durable bytes untouched.
        self.assertEqual([p.name for p in working.parent.glob(working.name + '.materializing-*')], [])

    def test_native_fixture_refuses_unbound_root_and_changed_bytes(self):
        durable, root, digest, working, _, _ = self.native_synthetic('refuse')
        working.mkdir(mode=0o700)  # A foreign root at the convention path is never adopted.
        with self.assertRaisesRegex(durable.FixtureUnavailable, 'not a materialization'):
            durable.native_scope(root, digest)
        working.rmdir()
        stored = root / 'scope/native/database.sqlite'
        stored.parent.chmod(0o700)
        stored.chmod(0o600)
        stored.write_bytes(b'synthetic NATIVE')  # Same size, different bytes.
        stored.chmod(0o400)
        stored.parent.chmod(0o500)
        with self.assertRaisesRegex(durable.FixtureUnavailable, 'changed'):
            durable.native_scope(root, digest)
        self.assertFalse(os.path.lexists(working))
        self.assertEqual([p.name for p in working.parent.glob(working.name + '.materializing-*')], [])
        with self.assertRaisesRegex(durable.FixtureUnavailable, 'SHA256 mismatch'):
            durable.native_scope(root, '0' * 64)


def stat_mode(path):
    return path.lstat().st_mode & 0o777


class UpstreamArchiveGuardTests(unittest.TestCase):
    """Native staging reads the pinned upstream archive only from its reviewed non-live location.

    The live fence stays unchanged: fixtures never read a retired runtime's downloads.
    """

    # Split so this guard's own source never matches the retired download path it forbids.
    OLD_DOWNLOADS = 'downloads' + '/WhatsOpt'

    @classmethod
    def setUpClass(cls):
        cls.scope = fixture.scope_from_environment()
        import modeling_runtime
        cls.runtime = modeling_runtime

    def test_reviewed_location_is_outside_every_live_root(self):
        runtime = self.runtime
        self.assertEqual(runtime.ARCHIVE, runtime.ARCHIVE_ROOT / runtime.ARCHIVE_SHA256 / 'WhatsOpt.tar.gz')
        self.assertEqual(runtime.ARCHIVE_ROOT, fixture.local_paths.upstream_archive_root())
        for root in live_fence.LIVE_ROOTS:
            self.assertFalse(str(runtime.ARCHIVE).startswith(root + '/'), root)
        for policy in ('baseline', 'unit'):
            self.assertIsNone(live_fence.decide('open', (str(runtime.ARCHIVE), 'rb', os.O_RDONLY), policy))
            # The cache is read-only for tests.
            self.assertIsNotNone(live_fence.decide('open', (str(runtime.ARCHIVE), 'wb', os.O_WRONLY | os.O_TRUNC), policy))
        # An old copy below the data root stays refused under every policy.
        old = live_fence.DATA_ROOT + '/retired-runtime/' + self.OLD_DOWNLOADS + '.tar.gz'
        for event, args in (('open', (old, 'rb', os.O_RDONLY)), ('shutil.copyfile', (old, '/private/tmp/x'))):
            for policy in ('baseline', 'unit'):
                self.assertIsNotNone(live_fence.decide(event, args, policy))

    def test_no_fixture_or_staging_source_names_the_old_runtime_downloads(self):
        repo = runner.REPO
        files = [repo / 'deployment/modeling_runtime.py', repo / 'deployment/checks.py',
                 *sorted(p for d in ('deployment/tests', 'modeling/tests', 'integration/tests', 'application/tests')
                         for p in (repo / d).rglob('*.py')),
                 *sorted(p for p in (repo / 'ui/tests').rglob('*') if p.suffix in ('.ts', '.tsx', '.js', '.mjs', '.json'))]
        offenders = [str(p.relative_to(repo)) for p in files if self.OLD_DOWNLOADS in p.read_text()]
        self.assertEqual(offenders, [])

    def test_actual_staging_reads_no_live_path_under_the_fence(self):
        # The unit policy applies here; any retired-runtime or other live access would raise and trip.
        self.assertEqual(live_fence.STATE.policy, 'unit')
        stage = self.scope.root / 'tmp' / ('upstream-stage-' + uuid4().hex)
        stage.mkdir(parents=True)
        previous = os.umask(0o077)  # as under the ./hyprn-mvp entry point
        try:
            self.runtime.stage_native_inputs(stage)
        finally:
            os.umask(previous)
        self.assertEqual(live_fence.STATE.trips, [])
        # Staged build inputs are readable by the image's non-root service user.
        for path in (stage, *stage.rglob('*')):
            mode = path.stat().st_mode & 0o777
            self.assertEqual(mode, 0o755 if path.is_dir() else 0o644, str(path))
        staged = (stage / 'provenance-inputs/upstream.tar.gz').read_bytes()
        self.assertEqual(hashlib.sha256(staged).hexdigest(), self.runtime.ARCHIVE_SHA256)
        self.assertTrue((stage / 'provenance-inputs/upstream/LICENSE').is_file())

    def synthetic(self, label, raw):
        root = self.scope.root / 'tmp' / ('upstream-' + label + '-' + uuid4().hex)
        root.mkdir(parents=True, mode=0o700)
        path = root / 'WhatsOpt.tar.gz'
        path.write_bytes(raw)
        path.chmod(0o400)
        return path

    def test_resolver_fails_closed_without_fallback(self):
        runtime = self.runtime
        missing = self.scope.root / 'tmp' / ('upstream-missing-' + uuid4().hex) / 'WhatsOpt.tar.gz'
        with self.assertRaisesRegex(ValueError, 'unavailable'):
            runtime.upstream_archive(missing)
        with self.assertRaisesRegex(ValueError, 'identity mismatch'):
            runtime.upstream_archive(self.synthetic('wrong', b'not the pinned archive'))
        writable = self.synthetic('writable', b'x')
        writable.chmod(0o600)
        with self.assertRaisesRegex(ValueError, 'owner-private read-only'):
            runtime.upstream_archive(writable)
        shared = self.synthetic('shared', b'x')
        shared.chmod(0o440)
        with self.assertRaisesRegex(ValueError, 'owner-private read-only'):
            runtime.upstream_archive(shared)
        link = shared.with_name('link.tar.gz')
        link.symlink_to(runtime.ARCHIVE)
        with self.assertRaisesRegex(ValueError, 'owner-private read-only'):
            runtime.upstream_archive(link)
        with patch.object(runtime, 'ARCHIVE', missing):
            with self.assertRaisesRegex(ValueError, 'unavailable'):
                runtime.stage_native_inputs(self.scope.root / 'tmp')


if __name__ == '__main__':
    unittest.main()
