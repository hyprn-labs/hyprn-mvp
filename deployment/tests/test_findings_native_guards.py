"""Closed Findings continuation guards: stdlib only, no scientific operations."""
# P2 live-runtime fence (deployment/tests/live_fence.py): refuses live roots, live ports, docker, live entry points and real signals.
import sys as _fence_sys
from pathlib import Path as _FencePath
if str(_FencePath(__file__).resolve().parent) not in _fence_sys.path:
    _fence_sys.path.append(str(_FencePath(__file__).resolve().parent))
import live_fence  # noqa: E402
setUpModule, tearDownModule = live_fence.unittest_module_hooks('unit')
import builtins
from contextlib import nullcontext
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

import checks as runner
import scoped_fixture as guard


def synthetic_fixture(folder):
    """A synthetic retained native fixture built in this guard's own scope.

    The guards check identity, journal, lock and refusal logic only; they need a well-formed,
    manifest-verified fixture whose working root is a valid scope, never the recorded runs.
    """
    import durable_fixture
    run_uuid = str(uuid4())
    root = guard.SCRATCH_ROOT / (guard.SCOPE_PREFIX + run_uuid)
    record = guard.Scope(root, run_uuid, guard.SCOPE_PREFIX + run_uuid, str(uuid4()), str(uuid4())).record()
    contents = {'scope/scope.json': (json.dumps(record, indent=2) + '\n').encode(), 'reuse/fixture-reuse.json': b'{}'}
    modes = {'.': 0o700, 'scope.json': 0o600, **{name: 0o700 for name in ('home', 'tmp', 'aiida', 'native', 'artifacts', 'evidence')}}
    files = {}
    for directory in (folder, folder / 'scope', folder / 'reuse', *(folder / 'scope' / name for name, mode in modes.items()
                                                                    if mode == 0o700 and name != '.')):
        directory.mkdir(mode=0o700)
    for relative, raw in contents.items():
        (folder / relative).write_bytes(raw)
        (folder / relative).chmod(0o400)
        files[relative] = dict(size=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    identities = {name: 'synthetic-' + name for name in durable_fixture.IDENTITY_FIELDS}
    identities.update({key: record[key] for key in ('run_uuid', 'profile_uuid', 'store_uuid')},
                      reuse_sha256=files['reuse/fixture-reuse.json']['sha256'])
    raw = json.dumps(dict(schema_version='1', kind=durable_fixture.NATIVE_KIND, name=folder.name, identities=identities,
        native_scope=dict(root=str(durable_fixture.scope_root(run_uuid)), prefix=durable_fixture.SCOPE_PREFIX, modes=modes),
        files=files)).encode()
    (folder / 'manifest.json').write_bytes(raw)
    (folder / 'manifest.json').chmod(0o400)
    return folder, hashlib.sha256(raw).hexdigest()


def release(path):
    if not os.path.lexists(path):
        return
    for entry in sorted(path.rglob('*'), key=lambda p: len(p.parts), reverse=True):
        entry.parent.chmod(0o700)
        if entry.is_dir() and not entry.is_symlink():
            entry.chmod(0o700)
            entry.rmdir()
        else:
            entry.unlink()
    path.chmod(0o700)
    path.rmdir()


class FindingsNativeGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scope = guard.scope_from_environment()
        import durable_fixture
        import findings_native_fixture as native
        folder, digest = synthetic_fixture(cls.scope.root / 'tmp/synthetic-native-fixture')
        cls.patches = [patch.object(durable_fixture, 'NATIVE_FIXTURE', folder),
                       patch.object(durable_fixture, 'NATIVE_MANIFEST_SHA256', digest)]
        for patcher in cls.patches:
            patcher.start()
        original = native._original()
        if not original.available:
            raise AssertionError(original.unavailable)
        cls.working = original.root
        more = [patch.object(native, 'ORIGINAL', original),
                patch.object(native, 'CONTINUATION', original.root / 'artifacts/findings-native-continuation')]
        for patcher in more:
            patcher.start()
        cls.patches += more

    @classmethod
    def tearDownClass(cls):
        for patcher in reversed(cls.patches):
            patcher.stop()
        release(cls.working)

    def native(self):
        import findings_native_fixture
        return findings_native_fixture

    def test_closed_routes_separate_from_existing_privileges(self):
        expected = {'findings-native-guards', 'findings-native-preflight', 'findings-native', 'findings-native-read'}
        self.assertEqual(runner.FINDINGS_NATIVE_GROUPS, expected)
        self.assertFalse(expected & (runner.APPROACH_PYTEST_GROUPS | runner.UNITS_PYTEST_GROUPS | runner.AE_PYTEST_GROUPS))
        self.assertIn('findings-history', runner.APPROACH_APP_GROUPS)

    def test_unknown_extra_and_mixed_arguments_refuse_before_allocation(self):
        for args in (['--group', 'findings-native-other'], ['--group', 'findings-native', '--root', '/private/tmp'], ['--group', 'findings-native', '--units-mixed-repair'], ['--group', 'findings-native', '--run-id', 'x']):
            with self.subTest(args=args), patch.object(sys, 'argv', ['checks', *args]), patch.object(guard, 'allocate_scope') as allocate, patch.object(runner.subprocess, 'run') as launch:
                try:
                    self.assertNotEqual(runner.main(), 0)
                except SystemExit as error:
                    self.assertNotEqual(error.code, 0)
                allocate.assert_not_called(); launch.assert_not_called()

    def test_missing_fixed_nodes_refuse_before_allocation(self):
        for group in runner.FINDINGS_NATIVE_GROUPS:
            with self.subTest(group=group), patch.object(runner, 'targets_for', side_effect=ValueError('missing')), patch.object(guard, 'allocate_scope') as allocate, patch.object(runner.subprocess, 'run') as launch:
                with self.assertRaises(ValueError): runner.run_group(group)
                allocate.assert_not_called(); launch.assert_not_called()

    def test_target_ast_missing_skipped_and_symlink_refusals(self):
        root = self.scope.root / 'tmp/target-fixture'
        target = root / 'deployment/tests/test_findings_native.py'
        target.parent.mkdir(parents=True)
        (root / 'deployment/tests/findings_native_fixture.py').write_text('')
        browser = root / 'ui/tests/findings-native.spec.ts'
        browser.parent.mkdir(parents=True); browser.write_text('test("native", () => {});')
        for body in ('def wrong(): pass', '@pytest.mark.skip(reason="x")\ndef test_new_downstream_run_pins_retained_source_and_approach(): pass', 'pytestmark=pytest.mark.skipif(False)\ndef test_new_downstream_run_pins_retained_source_and_approach(): pass', 'def test_new_downstream_run_pins_retained_source_and_approach(): pytest.skip("x")'):
            target.write_text(body)
            with self.assertRaisesRegex(ValueError, 'Required test'): runner.targets_for('findings-native', repo=root)
        target.unlink(); target.symlink_to(Path(__file__))
        with self.assertRaisesRegex(ValueError, 'Symlink'): runner.targets_for('findings-native', repo=root)

    def test_native_child_bad_environment_refuses_before_import_or_write(self):
        native = self.native()
        scope = native.retained_scope()
        good = guard.clean_environment(scope)
        original = builtins.__import__
        def tripwire(name, *args, **kwargs):
            if name.split('.')[0] in {'aiida', 'pytest', 'hyprn_mvp_app', 'hyprn_mvp_integration', 'units_native_fixture'}:
                raise AssertionError('Native/application collection reached')
            return original(name, *args, **kwargs)
        for env in ({}, {**good, 'OPENAI_API_KEY': 'synthetic'}, {**good, 'PYTHONPATH': '/foreign'}, {**good, 'AIIDA_PATH': '/foreign'}, {**good, 'HOME': str(guard.local_paths.account_home())}, guard.clean_environment(self.scope)):
            with self.subTest(keys=sorted(env)), patch.dict(os.environ, env, clear=True), patch.object(builtins, '__import__', side_effect=tripwire), patch.object(Path, 'mkdir', side_effect=AssertionError('allocation reached')), patch.object(guard, 'create_native_fixture', side_effect=AssertionError('initialization reached')):
                with self.assertRaises(ValueError): native.child('findings-native-preflight')

    def test_wrong_interpreter_refuses_before_import(self):
        native = self.native()
        with patch.dict(os.environ, guard.clean_environment(native.retained_scope()), clear=True), patch.object(sys, 'executable', '/usr/bin/python3'), patch.object(native, 'inventory', side_effect=AssertionError('read reached')):
            with self.assertRaisesRegex(ValueError, 'interpreter'): native.child('findings-native-preflight')

    def test_exact_identity_cannot_be_repointed(self):
        native = self.native()
        scope = native.retained_scope()
        for changed in (replace(scope, profile='default'), replace(scope, store_uuid=scope.profile_uuid), replace(scope, root=self.scope.root), replace(scope, url='http://127.0.0.1:19001')):
            with self.assertRaises(ValueError): native.validate_identity(changed)
        marker = json.loads((scope.root/'scope.json').read_text())
        with patch.object(Path, 'read_text', return_value=json.dumps(marker | {'store_uuid': scope.profile_uuid})):
            with self.assertRaises(ValueError): native.retained_scope()

    def baseline_fixture(self, label, stage='baselined', defect=None):
        """Synthetic, authenticated before-images; never touch the retained stores."""
        native = self.native()
        directory = self.scope.root / 'tmp' / ('baseline-' + label)
        attempt = directory / 'attempt-0001'
        private = attempt / 'private'
        private.mkdir(parents=True)
        rows = {'proof': {'columns': [[0, 'id', 'INTEGER', 0, None, 1]],
                          'primary_key': ['id'], 'rows': [[{'type': 'int', 'raw': 1}]]}}
        databases = {}
        for relative in ('artifacts/combined.sqlite', 'native/database.sqlite',
                         'artifacts/private-http/modeling/model.sqlite3',
                         'artifacts/private-http/modeling/scratch.sqlite3'):
            name = relative.replace('/', '__')
            backup = private / (name + '.backup')
            backup.write_bytes(b'synthetic backup')
            row_file = private / (name + '.rows.json')
            row_file.write_bytes(native.canonical(rows))
            databases[relative] = dict(backup_sha256=native.sha(backup.read_bytes()),
                rows_sha256=native.sha(row_file.read_bytes()), tables={'proof': 1})
        before = dict(identity=self.scope.record(),
            records=[{'process_uuid': 'old' + str(i)} for i in range(7)],
            processes=['old' + str(i) for i in range(7)],
            files={'retained.txt': {'size': 1, 'sha256': native.sha(b'x')}})
        baseline = dict(before, databases=databases, sources={'fixture': native.sha(b'source')})
        if defect == 'empty-databases': baseline['databases'] = {}
        if defect == 'missing-database': baseline['databases'].pop('native/database.sqlite')
        if defect == 'empty-rows':
            target = private / 'native__database.sqlite.rows.json'
            target.write_bytes(native.canonical({}))
            databases['native/database.sqlite']['rows_sha256'] = native.sha(target.read_bytes())
        baseline_path = attempt / 'baseline.json'
        baseline_path.write_bytes(native.canonical(baseline))
        journal = native.Journal(directory, self.scope.record())
        fields = dict(baseline_attempt=attempt.name, baseline_sha256=native.sha(baseline_path.read_bytes()))
        if defect == 'missing-reference': fields.pop('baseline_attempt')
        journal.advance('baselined', **fields)
        if stage != 'baselined': journal.advance('prepared', request={'command_id': 'c'})
        if stage in {'submitted', 'recorded'}:
            journal.advance('submitted')
            before = dict(before, processes=before['processes'] + ['new'])
        if stage == 'recorded': journal.advance('recorded', process_uuid='new')
        targets = {
            'missing-baseline': baseline_path, 'tampered-baseline': baseline_path,
            'missing-rows': private / 'native__database.sqlite.rows.json',
            'tampered-rows': private / 'native__database.sqlite.rows.json',
            'missing-backup': private / 'native__database.sqlite.backup',
            'tampered-backup': private / 'native__database.sqlite.backup',
            'missing-key': directory / 'journal.key',
            'missing-pointer': directory / 'journal.json',
        }
        if defect in targets:
            if defect.startswith('missing-'): targets[defect].unlink()
            else: targets[defect].write_bytes(b'tampered')
        return directory, before, rows

    def assert_baseline_entry_refusals(self):
        native = self.native()
        defects = ('missing-reference', 'missing-baseline', 'tampered-baseline',
                   'empty-databases', 'missing-database', 'empty-rows',
                   'missing-rows', 'tampered-rows', 'missing-backup', 'tampered-backup',
                   'missing-key', 'missing-pointer')
        for stage in ('baselined', 'prepared', 'submitted', 'recorded'):
            group = 'findings-native-read' if stage in {'submitted', 'recorded'} else 'findings-native'
            for defect in defects:
                directory, before, rows = self.baseline_fixture(stage + '-' + defect, stage, defect)
                with (
                    self.subTest(stage=stage, defect=defect),
                    patch.object(native, 'CONTINUATION', directory),
                    patch.object(native, 'validate_child', return_value=self.scope),
                    patch.object(runner, 'targets_for', return_value=()),
                    patch.object(native, 'prove_quiescent'),
                    patch.object(native, 'inventory', return_value=before),
                    patch.object(native, 'readonly', return_value=nullcontext(None)),
                    patch.object(native, 'row_inventory', return_value=rows),
                    patch.object(native, 'continuation_lock', side_effect=AssertionError('lock write reached')),
                    patch.object(native, 'durable_write', side_effect=AssertionError('journal write reached')),
                    patch.object(Path, 'mkdir', side_effect=AssertionError('attempt allocation reached')),
                    patch.object(native, 'qualification', side_effect=AssertionError('native qualification reached')),
                ):
                    with self.assertRaises((ValueError, OSError)):
                        native.child(group)
        for stage in ('baselined', 'prepared', 'submitted', 'recorded'):
            group = 'findings-native-read' if stage in {'submitted', 'recorded'} else 'findings-native'
            directory, before, rows = self.baseline_fixture('valid-' + stage, stage)
            with (
                self.subTest(valid=stage),
                patch.object(native, 'CONTINUATION', directory),
                patch.object(native, 'validate_child', return_value=self.scope),
                patch.object(runner, 'targets_for', return_value=()),
                patch.object(native, 'prove_quiescent'),
                patch.object(native, 'inventory', return_value=before),
                patch.object(native, 'readonly', return_value=nullcontext(None)),
                patch.object(native, 'row_inventory', return_value=rows),
                patch.object(native, 'continuation_lock', return_value=nullcontext()),
                patch.object(native, 'qualification', return_value=73) as qualify,
            ):
                self.assertEqual(native.child(group), 73)
                self.assertTrue((directory / 'attempt-0002').is_dir())
                qualify.assert_called_once()
        self.assertNotIn('aiida', sys.modules)

    def test_process_count_and_lifecycle_are_closed(self):
        native = self.native()
        originals = {'old'+str(i) for i in range(7)}
        self.assertEqual(native.admit_state('findings-native-preflight', None, originals, originals), 'initial')
        with self.assertRaises(ValueError):
            native.admit_state('findings-native', None, originals, originals)
        with self.assertRaises(ValueError):
            native.verify_saved_baseline(None, {})
        self.assertIsNone(native.verify_saved_baseline(None, {}, allow_initial=True))
        directory = self.scope.root / 'tmp/no-native-journal'
        before = dict(processes=sorted(originals), records=[{'process_uuid': p} for p in originals])
        for exists in (False, True):
            if exists: directory.mkdir()
            with (
                self.subTest(directory_exists=exists),
                patch.object(native, 'CONTINUATION', directory),
                patch.object(native, 'validate_child', return_value=self.scope),
                patch.object(runner, 'targets_for', return_value=()),
                patch.object(native, 'prove_quiescent'),
                patch.object(native, 'inventory', return_value=before),
                patch.object(native, 'continuation_lock', side_effect=AssertionError('lock write reached')),
                patch.object(native, 'durable_write', side_effect=AssertionError('journal write reached')),
                patch.object(Path, 'mkdir', side_effect=AssertionError('allocation reached')),
                patch.object(native, 'qualification', side_effect=AssertionError('qualification reached')),
            ):
                with self.assertRaises(ValueError): native.child('findings-native')
        for count in (0, 6, 8, 9):
            with self.assertRaises(ValueError): native.admit_state('findings-native-preflight', None, {'x'+str(i) for i in range(count)}, originals)
        with self.assertRaises(ValueError): native.admit_state('findings-native-read', None, originals, originals)
        with self.assertRaises(ValueError): native.admit_state('findings-native', {'stage':'recorded', 'process_uuid':'new'}, originals | {'new'}, originals)
        with self.assertRaises(ValueError): native.admit_state('findings-native-preflight', {'stage':'unknown'}, originals, originals)

    def test_reconciliation_exact_request_node_outbox_only(self):
        native = self.native()
        request = dict(run_id='r', scope='s', command_id='c', payload_digest='p', bundle_digest='b')
        journal = {'stage':'submitted', 'request':request}
        proof = {'process_uuid':'new', 'request':request, 'outbox_request':request, 'outbox_state':'recorded', 'association':{'run_id':'r','command_id':'c','study_id':'s','process_uuid':'new','store_uuid':native.retained_scope().store_uuid}}
        self.assertEqual(native.reconcile(journal, [proof], {'new'}), 'new')
        for records in ([], [proof, proof], [proof | {'outbox_state':'uncertain'}], [proof | {'outbox_request': request | {'command_id':'wrong'}}], [proof | {'request':request | {'bundle_digest':'wrong'}}], [proof | {'process_uuid':'wrong'}], [proof | {'association':proof['association'] | {'store_uuid':'wrong'}}]):
            with self.assertRaises(ValueError): native.reconcile(journal, records, {'new'})
        self.assertNotIn('aiida', sys.modules)

    def test_journal_tampering_and_illegal_transitions_refused(self):
        self.assert_baseline_entry_refusals()
        native = self.native()
        directory = self.scope.root/'tmp/journal'; directory.mkdir()
        identity = native.retained_scope().record()
        journal = native.Journal(directory, identity)
        journal.advance('baselined', baseline_sha256='a'*64)
        journal.advance('prepared', request={'command_id':'c'})
        journal.advance('submitted')
        self.assertEqual(journal.read()['stage'], 'submitted')
        with self.assertRaises(ValueError): journal.advance('prepared')
        head = directory/'journal.json'; record = json.loads(head.read_text()); record['body']['stage']='recorded'; head.write_text(json.dumps(record))
        with self.assertRaises(ValueError): journal.read()

    def test_exclusive_lock_and_ambiguous_dead_owner_refuse(self):
        native = self.native()
        directory=self.scope.root/'tmp/lock'; directory.mkdir()
        with native.continuation_lock(directory):
            with self.assertRaises(ValueError):
                with native.continuation_lock(directory): pass
        lock=directory/'owner.json'; lock.write_text(json.dumps({'pid':99999999,'start':'unknown'}))
        with patch.object(native, 'prove_quiescent', side_effect=ValueError('ambiguous scoped operation')):
            with self.assertRaises(ValueError):
                with native.continuation_lock(directory): pass

    def test_fixed_child_command_environment_and_no_initialization(self):
        native=self.native(); scope=native.retained_scope()
        result=Mock(returncode=2,stdout='',stderr='missing child target')
        with patch.object(runner, 'targets_for', return_value=()), patch.object(runner, 'require_environment'), patch.object(native, 'run_retained', wraps=native.run_retained), patch.object(native.subprocess, 'run', return_value=result) as launch, patch.object(guard,'allocate_scope') as allocate:
            self.assertEqual(runner.run_group('findings-native-preflight'),2)
            args,kwargs=launch.call_args
            self.assertEqual(args[0],[guard.APPROVED_PYTHON,'-B',str(runner.REPO/'deployment/checks.py'),'--findings-native-preflight-child'])
            self.assertEqual(kwargs['env'],guard.clean_environment(scope)); allocate.assert_not_called()
            (self.scope.root/'evidence/child-command.json').write_text(json.dumps({'argv':args[0], 'env':kwargs['env']},indent=2))

    def test_empty_skipped_failed_and_wrong_counts_never_pass(self):
        for count,failed,skipped in ((0,0,0),(1,0,0),(17,1,0),(17,0,1),(18,0,0)):
            result=unittest.TestResult(); result.testsRun=count
            result.failures=[('x','x')]*failed; result.skipped=[('x','x')]*skipped
            self.assertFalse(runner.findings_guards_passed(result))
        result=unittest.TestResult(); result.testsRun=17
        self.assertTrue(runner.findings_guards_passed(result))

    def test_read_mode_veto_precedes_target(self):
        native=self.native()
        calls=[]
        with native.read_only_veto():
            with self.assertRaisesRegex(ValueError,'read-only'): native.require_write('prepare')
            with self.assertRaisesRegex(ValueError,'read-only'): native.require_write('dispatch')
            with self.assertRaisesRegex(ValueError,'read-only'): native.require_write('build-worker')
            with self.assertRaisesRegex(ValueError,'read-only'): native.require_write('submit')
            calls.append('read')
        self.assertEqual(calls,['read'])

    def test_late_imported_write_functions_are_vetoed(self):
        native=self.native()
        from types import SimpleNamespace
        module = SimpleNamespace(build_worker=Mock(side_effect=AssertionError('write reached')))
        with native.read_only_veto(), patch.dict(sys.modules, {'execution_runtime':module}):
            imported=__import__('execution_runtime')
            for _ in range(2):
                with self.assertRaisesRegex(ValueError,'read-only'): imported.build_worker()

    def test_immutable_database_refuses_wal_and_writable_handles(self):
        import sqlite3
        native=self.native(); path=self.scope.root/'tmp/readonly.sqlite'
        with sqlite3.connect(path) as connection: connection.execute('create table proof (id integer primary key, raw text)')
        wal=path.with_name(path.name+'-wal'); wal.write_bytes(b'nonempty')
        with self.assertRaisesRegex(ValueError,'Nonempty WAL'):
            with native.readonly(path): pass
        wal.unlink()
        for output in ('p123\nf3\nau\n','p123\nf3\n'):
            with patch.object(native.subprocess,'run',return_value=Mock(returncode=0,stdout=output,stderr='')), self.assertRaisesRegex(ValueError,'writable or ambiguous'):
                with native.readonly(path): pass
        with patch.object(native.subprocess,'run',return_value=Mock(returncode=1,stdout='',stderr='')):
            before=path.read_bytes()
            with native.readonly(path) as connection:
                with self.assertRaises(sqlite3.OperationalError): connection.execute('insert into proof values (1,"no")')
            self.assertEqual(path.read_bytes(),before)
            self.assertFalse(wal.exists()); self.assertFalse(path.with_name(path.name+'-shm').exists())

    def test_failed_recording_reconciles_without_scientific_calls(self):
        native=self.native(); directory=self.scope.root/'tmp/recovery'; directory.mkdir()
        journal=native.Journal(directory,native.retained_scope().record())
        request=dict(run_id='r',scope='s',command_id='c',payload_digest='p',bundle_digest='b')
        journal.advance('baselined',baseline_sha256='a'*64)
        journal.advance('prepared',request=request); journal.advance('submitted')
        with patch.object(native,'durable_write',side_effect=OSError('simulated post-execution write failure')):
            with self.assertRaises(OSError): journal.advance('recorded',process_uuid='new')
        proof=dict(process_uuid='new',request=request,outbox_request=request,outbox_state='recorded',association=dict(run_id='r',study_id='s',command_id='c',store_uuid=native.ORIGINAL.store_uuid,process_uuid='new'))
        originals={'old'+str(i) for i in range(7)}
        with patch.object(native,'reconciliation_records',return_value=[proof | {'outbox_state':'uncertain'}]), self.assertRaises(ValueError):
            native.recover_recorded(journal,originals|{'new'},originals)
        self.assertEqual(journal.read()['stage'],'submitted')
        with patch.object(native,'reconciliation_records',return_value=[proof]):
            self.assertEqual(native.recover_recorded(journal,originals|{'new'},originals)['process_uuid'],'new')
        self.assertEqual(journal.read()['stage'],'recorded')
        self.assertNotIn('aiida',sys.modules)
