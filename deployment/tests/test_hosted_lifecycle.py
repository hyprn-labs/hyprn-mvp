"""Hosted composition refuses implicit local stores or missing runtime bindings."""

import live_fence
setUpModule, tearDownModule = live_fence.unittest_module_hooks('baseline')

from pathlib import Path
import asyncio
import copy
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'application/src'))
sys.path.insert(0, str(ROOT / 'editions/cloud/src'))
sys.path.insert(0, str(ROOT / 'deployment'))
from hyprn_mvp_cloud import asgi
from hyprn_mvp_cloud.runtime import WriterLease, host_record
from hyprn_mvp_cloud.admission import Admission
from hyprn_mvp_app.database import Connection
from hyprn_mvp_app import migrations
from hyprn_mvp_app import hosted_lifecycle
from hyprn_mvp_app.hosted_runtime import request_lease
import cloud_release
import managed_assistant
from installed_hosted_app import assistant_plan
from hyprn_mvp_cloud.assistant_startup import reconcile
from hyprn_mvp_app.assistant.claude import ProviderError
from hosted_fixture import postgres_fixture


class HostedCompositionTests(unittest.TestCase):
    def test_stopped_writer_check_observes_actual_oneoff_container_state(self):
        import cloud_lifecycle
        pins = json.loads((ROOT / 'deployment/pins.json').read_text())
        image = 'python@' + pins['image_bases']['python']['platforms']['linux/amd64']
        project = 'hyprn-stopped-' + uuid4().hex
        host = cloud_lifecycle.Lifecycle.__new__(cloud_lifecycle.Lifecycle)
        host.root = Path('/unused-control')
        host.identity = {'installation_id': project}
        host.runtime = {'installation_id': project}
        host.preview = {'compose': {'services': {'app': {'image': image}}}}
        host.identity_check = lambda: None
        host.native_process = lambda: None
        host.deadline = time.monotonic() + 60
        receipt = dict(schema='hyprn-admission/v1', **host.identity,
                       browser=False, scientific=False)
        # Only protected-file/native-process observations are doubled here;
        # container creation, state changes and inspection use the real daemon.
        command = ['docker', 'create', '--pull=never', '--platform=linux/amd64',
                   '--name', project, '--label', 'com.docker.compose.project=' + project,
                   '--label', 'com.docker.compose.service=database-operation',
                   '--label', 'com.docker.compose.oneoff=True',
                   '--network=none', '--read-only', '--memory=64m', '--cpus=0.2',
                   '--pids-limit=16', '--cap-drop=ALL', '--security-opt=no-new-privileges:true',
                   '--user=65534:65534', image, 'python', '-c', 'import time;time.sleep(60)']
        created = subprocess.run(command, capture_output=True, text=True, timeout=30)
        self.assertEqual(created.returncode, 0, created.stderr)
        try:
            with patch.object(cloud_lifecycle, 'control_record', return_value=receipt):
                host.assert_stopped()
                subprocess.run(['docker', 'start', project], check=True, capture_output=True, timeout=10)
                with self.assertRaises(cloud_lifecycle.Refused) as error:
                    host.assert_stopped()
                self.assertEqual(error.exception.reason, 'writer_container_not_stopped')
                subprocess.run(['docker', 'stop', '--time=1', project], check=True,
                               capture_output=True, timeout=10)
                host.assert_stopped()
        finally:
            removed = subprocess.run(['docker', 'rm', '--force', project],
                                     capture_output=True, text=True, timeout=10)
            self.assertEqual(removed.returncode, 0, removed.stderr)

    def test_root_owned_shared_controls_are_readable_by_application_uid(self):
        # Exercise actual Linux ownership and umask, then permanently drop privilege.
        pins = json.loads((ROOT / 'deployment/pins.json').read_text())
        base = 'python@' + pins['image_bases']['python']['platforms']['linux/amd64']
        script = '''import os,sys
from pathlib import Path
sys.path[:0] = ['/source/deployment', '/source/application/src']
from cloud_lifecycle import write_record
from hyprn_mvp_app.hosted_runtime import host_record
root = Path('/control')
root.chmod(0o755)
os.umask(0o077)
write_record(root / 'admission.json', {'browser': False}, mode=0o644)
write_record(root / 'receipt.json', {'status': 'intent'})
assert (root / 'receipt.json').stat().st_mode & 0o777 == 0o600
os.setgroups([])
os.setgid(10002)
os.setuid(10002)
assert host_record(root / 'admission.json') == {'browser': False}
try:
    (root / 'admission.json').write_text('{}')
except PermissionError:
    pass
else:
    raise AssertionError('application must not change admission')
print('root-owned controls readable; writes refused')
'''
        value = subprocess.run(['docker', 'run', '--rm', '--pull=never', '--platform=linux/amd64',
                                '--network=none', '--read-only', '--user=0:0', '--memory=256m',
                                '--cpus=1', '--pids-limit=32', '--security-opt=no-new-privileges:true',
                                '--tmpfs=/control:rw,noexec,nosuid,size=1m',
                                '--mount', 'type=bind,src=' + str(ROOT) + ',dst=/source,readonly',
                                base, 'python', '-B', '-c', script],
                               capture_output=True, text=True, timeout=60)
        self.assertEqual(value.returncode, 0, value.stderr)
        self.assertIn('writes refused', value.stdout)

    def test_cloud_factory_refuses_missing_runtime_configuration(self):
        factory = getattr(asgi, 'from_environment', None)
        self.assertTrue(callable(factory), 'A hosted factory must consume explicit runtime bindings')
        with self.assertRaisesRegex(ValueError, 'configuration'):
            factory({})

    def test_invalid_cli_input_returns_closed_protocol_without_echoing_input(self):
        value = subprocess.run([sys.executable, '-B', str(ROOT / 'deployment/cloud_lifecycle.py'),
                                'start', '--binding', 'private-value', '--operation-id', str(uuid4()),
                                '--timeout', '0'], capture_output=True, text=True)
        self.assertEqual(value.returncode, 2)
        body = json.loads(value.stdout)
        self.assertEqual(body['status'], 'refused')
        self.assertIsNone(body['installation_id'])
        self.assertNotIn('private-value', value.stdout + value.stderr)
        self.assertEqual(set(body), {'operation_id', 'operation', 'installation_id', 'status',
                                    'reason_code', 'observed_schema_versions', 'evidence_refs'})

    def test_shared_platform_fixtures_validate_through_pinned_renderer(self):
        # Explicit adjacent development contract input; shipping receives a separate
        # pinned bundle. No repository paths enter the release descriptor.
        contract = cloud_release.platform_contract((ROOT.parent / 'hyprn-platform').resolve())
        fixtures = contract.read_json(contract.SCHEMA_PATH.with_name('fixtures.json'))
        contract.check_documents(fixtures['valid'])
        self.assertIn('admission', fixtures['valid']['workload']['lifecycle'])

    def test_no_binary_payload_is_not_a_source_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises((OSError, ValueError)):
                cloud_release.payload(Path(tmp) / 'missing.json', {}, None)


class HostedDatabaseTests(unittest.TestCase):
    def test_dispatcher_uses_its_publication_without_bypassing_actor_isolation(self):
        from hyprn_mvp_app.store import Store
        from hyprn_mvp_app.readiness import ObservationPublisher
        from hyprn_mvp_app.database import actor_scope
        native = SimpleNamespace(require_attestation=lambda: True, bundle_runtime=lambda: {
            'runtime': {'image_digest': 'sha256:' + 'a' * 64, 'architecture': 'amd64',
                        'python_version': '3.12.15', 'worker_entrypoint':
                        'hyprn_mvp_integration.worker', 'policy_digest': 'b' * 64}})
        store = Store.postgres(self.database['request'], self.database['request'],
                               background=self.database['dispatcher'])
        publisher = ObservationPublisher(store, native)
        self.assertTrue(publisher.refresh())
        self.assertIsNone(store.execution_observation())
        self.assertTrue(publisher.ready())
        with actor_scope(str(uuid4()), request_boundary=True):
            self.assertEqual(store.execution_observation()['status'], 'ready')
        publisher.stopped()
        self.assertFalse(publisher.ready())

    @classmethod
    def setUpClass(cls):
        cls.fixture_context = postgres_fixture()
        cls.database = cls.fixture_context.__enter__()
        raw = cls.database['migration'].connect()
        try:
            Connection(raw).execute('INSERT INTO hyprn_installation_identity VALUES(1,?,?)',
                                    ('fixture-installation', 'fixture-store'))
            raw.commit()
        finally:
            raw.close()

    @classmethod
    def tearDownClass(cls):
        cls.fixture_context.__exit__(None, None, None)

    def test_writer_conflict_refuses_migration_and_releases_on_close(self):
        lease = WriterLease(self.database['request'])
        try:
            lease.check()
            with self.assertRaisesRegex(ValueError, 'writer already active'):
                WriterLease(self.database['request'])
            with self.assertRaisesRegex(ValueError, 'writer is active'):
                migrations.initialize(self.database['migration'])
        finally:
            lease.close()
        migrations.initialize(self.database['migration'])
        next_lease = WriterLease(self.database['request'])
        next_lease.close()

    def test_external_session_bootstrap_does_not_wait_on_the_application_writer(self):
        lease = WriterLease(self.database['request'])
        raw = self.database['auth'].connect()
        try:
            db = Connection(raw)
            db.execute("SET LOCAL lock_timeout='1s'")
            db.execute("SET LOCAL statement_timeout='2s'")
            session = db.execute('SELECT * FROM hyprn_external_session(?,?,?,?,?)',
                ('https://isolated.cloudflareaccess.com', str(uuid4()),
                 uuid4().hex + uuid4().hex, uuid4().hex + uuid4().hex, None)).fetchone()
            self.assertTrue(session['actor_id'])
            self.assertGreater(session['expires_at'], time.time())
            raw.commit()
            lease.check()
            with self.assertRaisesRegex(ValueError, 'writer already active'):
                WriterLease(self.database['request'])
            with self.assertRaisesRegex(ValueError, 'writer is active'):
                migrations.initialize(self.database['migration'])
        finally:
            raw.close()
            lease.close()

    def test_explicit_initialize_refuses_existing_schema_without_changing_it(self):
        def rows():
            raw = self.database['request'].connect()
            try:
                return Connection(raw).execute('SELECT * FROM hyprn_schema_versions ORDER BY version').fetchall()
            finally:
                raw.close()
        before = rows()
        with self.assertRaisesRegex(ValueError, 'nonempty database'):
            migrations.initialize(self.database['migration'], empty_only=True)
        self.assertEqual(rows(), before)

    def test_fresh_initialize_is_atomic_and_identity_survives_migrate(self):
        with postgres_fixture(initialize_schema=False) as fresh:
            hosted_lifecycle.initialize_store(fresh['migration'], 'fresh-installation', 'fresh-store')
            before = hosted_lifecycle.inspect_store(fresh['request'], 'fresh-installation', 'fresh-store')
            self.assertEqual(len(before), len(migrations.MIGRATIONS))
            self.assertEqual(hosted_lifecycle.migrate_store(fresh['migration'], 'fresh-installation', 'fresh-store'), before)
            with self.assertRaisesRegex(ValueError, 'identity differs'):
                hosted_lifecycle.inspect_store(fresh['request'], 'foreign-installation', 'fresh-store')
            self.assertEqual(hosted_lifecycle.inspect_store(fresh['request'], 'fresh-installation', 'fresh-store'), before)

    def test_request_role_cannot_create_or_change_installation_identity(self):
        from hyprn_mvp_app.database import DatabasePermissionDenied
        for sql in ('UPDATE hyprn_installation_identity SET store_id=\'changed\'',
                    'DELETE FROM hyprn_installation_identity',
                    'INSERT INTO hyprn_installation_identity VALUES(1,\'other\',\'other\')'):
            raw = self.database['request'].connect()
            try:
                with self.assertRaises(DatabasePermissionDenied):
                    Connection(raw).execute(sql)
            finally:
                raw.close()

    def test_drain_counts_no_domain_content_and_waits_for_complete_request(self):
        def counts():
            return hosted_lifecycle.drain_counts(self.database['request'], 'fixture-installation', 'fixture-store')
        with request_lease(self.database['request']):
            self.assertEqual(counts(), {'pending': 0, 'uncertain': 0, 'requests_quiescent': False})
        self.assertEqual(counts(), {'pending': 0, 'uncertain': 0, 'requests_quiescent': True})

    def test_maintenance_counts_accepted_work_without_revealing_its_payload(self):
        raw = self.database['migration'].connect()
        command = str(uuid4())
        try:
            db = Connection(raw)
            db.execute('INSERT INTO receipts(scope,category,command_id,actor_id,payload_digest,state,request) VALUES(?,?,?,?,?,?,?)',
                       ('private-study', 'calculation_sample', command, 'private-actor', 'digest',
                        'pending_remote', '{"private":"payload"}'))
            raw.commit()
            value = hosted_lifecycle.drain_counts(self.database['request'], 'fixture-installation', 'fixture-store')
            self.assertEqual(value, {'pending': 1, 'uncertain': 0, 'requests_quiescent': True})
            db.execute('UPDATE receipts SET state=? WHERE command_id=?', ('uncertain', command))
            raw.commit()
            value = hosted_lifecycle.drain_counts(self.database['request'], 'fixture-installation', 'fixture-store')
            self.assertEqual(value, {'pending': 1, 'uncertain': 1, 'requests_quiescent': True})
        finally:
            Connection(raw).execute('DELETE FROM receipts WHERE command_id=?', (command,))
            raw.commit()
            raw.close()


class HostedAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name).resolve()
        self.identity = dict(installation_id='hyprn-staging-fixture', release_sha256='a' * 64,
                             config_sha256='b' * 64)
        self.state = dict(schema='hyprn-admission/v1', **self.identity, browser=True,
                          scientific=False, expires_at=int(time.time()) + 120)
        self.identity_path = self.root / 'identity.json'
        self.identity_path.write_text(json.dumps(self.identity))
        self.path = self.root / 'admission.json'
        self.path.write_text(json.dumps(self.state))
        self.environ = {'HYPRN_MVP_ADMISSION_FILE': str(self.path),
                        'HYPRN_MVP_HOST_IDENTITY_FILE': str(self.identity_path)}
        self.gate = Admission(self.environ, owner=os.getuid())

    def test_browser_authoring_does_not_enable_execution(self):
        self.assertTrue(self.gate.allows('POST', '/api/1/studies'))
        self.assertTrue(self.gate.allows('GET', '/api/1/studies/id/runs'))
        self.assertFalse(self.gate.allows('POST', '/api/1/studies/id/runs'))
        self.assertFalse(self.gate.allows('POST', '/api/1/studies/id/calculation-samples'))

    def test_missing_expired_or_wrong_release_is_closed(self):
        for changes in ({'expires_at': 0}, {'release_sha256': 'c' * 64}, {'scientific': 1}):
            self.path.write_text(json.dumps({**self.state, **changes}))
            with self.assertRaises(ValueError):
                self.gate.read()
        self.path.unlink()
        with self.assertRaises(OSError):
            self.gate.read()

    def test_application_owned_or_writable_control_is_refused(self):
        with self.assertRaises(ValueError):
            host_record(self.path, owner=os.getuid() + 1)
        self.path.chmod(0o666)
        with self.assertRaises(ValueError):
            host_record(self.path, owner=os.getuid())


class HostedAssistantStartupTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.plan = assistant_plan()
        self.identity = dict(installation_id='fixture', release_sha256='a' * 64, config_sha256='b' * 64)
        self.settings = SimpleNamespace(definitions_sha256=self.plan['definitions_sha256'],
                                        agent_id='agent_fixture', agent_version=1,
                                        environment_id='environment_fixture', prior_cents=7, total_cents=100)
        self.continuity = dict(schema='hyprn-assistant-continuity/v1', **self.identity,
                               configuration_sha256=self.plan['configuration_sha256'],
                               prior_cents=7, total_cents=100, carried_sessions={'session_old': 5},
                               untracked_cents=2, review_sha256='c' * 64)
        self.rows = [dict(provider_id='session_retained', conversation_id='conversation_fixture', provision='ready')]
        self.store = SimpleNamespace(assistant_accounts=lambda: self.rows)
        test = self
        class ReadOnlyProvider:
            sessions = ['session_old', 'session_retained']
            status = 'idle'
            drift = False
            skill_drift = False
            reviewer_drift = False

            async def request(self, method, path, params=None):
                test.assertEqual(method, 'GET')
                if path == '/v1/sessions':
                    test.assertEqual(params, {'limit': 100, 'include_archived': 'true'})
                    return {'data': [{'id': sid} for sid in self.sessions], 'next_page': None}
                skill = test.plan['bindings']['skill']
                if path == '/v1/skills/' + skill['id'] + '/versions/' + skill['version']:
                    return {'id': skill['version'], 'skill_id': skill['id']}
                for role, binding in test.plan['bindings']['reviewers'].items():
                    if path == '/v1/agents/' + binding['id']:
                        test.assertEqual(params, {'version': binding['version']})
                        result = dict(copy.deepcopy(test.plan['reviewers'][role]), **binding)
                        if self.reviewer_drift:
                            result['tools'] = test.plan['agent']['tools']
                        return result
                if path == '/v1/agents/agent_fixture':
                    test.assertEqual(params, {'version': 1})
                    result = dict(copy.deepcopy(test.plan['agent']), id='agent_fixture', version=1)
                    if self.drift:
                        result['tools'] = []
                    return result
                if path == '/v1/environments/environment_fixture':
                    result = dict(copy.deepcopy(test.plan['environment']), id='environment_fixture')
                    result['config']['packages'] = {'type': 'packages', **{manager: [] for manager in managed_assistant.MANAGERS}}
                    return result
                raise AssertionError('Unexpected provider request')

            async def skill_content(self, skill_id, version):
                test.assertEqual((skill_id, version), ('skill_fixture', 'skver_fixture'))
                return b'wrong archive' if self.skill_drift else managed_assistant.managed_skill.bundle()[0]

            async def find_session(self, correlation):
                test.assertEqual(correlation, 'conversation_fixture')
                return {'id': 'session_retained'}

            async def session_account(self, session_id):
                return {'status': self.status, 'spent_cents': 5 if session_id == 'session_old' else 11}
        self.provider = ReadOnlyProvider()

    async def check(self):
        return await reconcile(self.store, self.provider, self.settings, self.plan, self.continuity, self.identity)

    async def test_old_release_continuity_is_refused_before_provider_calls(self):
        self.continuity['release_sha256'] = 'f' * 64
        with patch.object(self.provider, 'request') as request:
            with self.assertRaisesRegex(ProviderError, 'shared_allowance_unknown'):
                await self.check()
            request.assert_not_called()

    async def test_exact_full_definition_and_archived_prior_spend_are_checked(self):
        result = await self.check()
        self.assertEqual(result['spent_cents'], 18)
        self.assertEqual(result['sessions'], 2)

    async def test_unknown_busy_or_changed_provider_records_refuse_startup(self):
        self.provider.sessions.append('session_unknown')
        with self.assertRaisesRegex(ProviderError, 'shared_allowance_unknown'):
            await self.check()
        self.provider.sessions.pop()
        self.provider.status = 'running'
        with self.assertRaisesRegex(ProviderError, 'shared_allowance_busy'):
            await self.check()
        self.provider.status = 'idle'
        self.provider.drift = True
        with self.assertRaisesRegex(ProviderError, 'provider_definition_drift'):
            await self.check()

    async def test_changed_native_skill_or_reviewer_write_authority_blocks_startup(self):
        self.provider.skill_drift = True
        with self.assertRaisesRegex(ProviderError, 'provider_skill_drift'):
            await self.check()
        self.provider.skill_drift = False
        self.provider.reviewer_drift = True
        with self.assertRaisesRegex(ProviderError, 'provider_definition_drift'):
            await self.check()

    async def test_bootstrap_or_missing_pins_cannot_start_delivery(self):
        original = self.plan
        for invalid in (managed_assistant.bootstrap('staging', 'claude-sonnet-5-5', 'high'),
                        {key: value for key, value in original.items() if key != 'bindings'}):
            self.plan = invalid
            with patch.object(self.provider, 'request') as request:
                with self.assertRaises(ProviderError):
                    await self.check()
                request.assert_not_called()
        self.plan = original

    async def test_missing_prior_evidence_never_becomes_zero(self):
        self.continuity['untracked_cents'] = 0
        with self.assertRaisesRegex(ProviderError, 'shared_allowance_unknown'):
            await self.check()

    def test_complete_released_assistant_plan_has_explicit_bounded_size(self):
        plan = assistant_plan()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp).resolve() / 'plan.json'
            path.write_text(json.dumps(plan))
            self.assertGreater(path.stat().st_size, 65536)
            self.assertEqual(host_record(path, owner=os.getuid(), max_bytes=1024 * 1024), plan)
            with self.assertRaises(ValueError):
                host_record(path, owner=os.getuid())


class ApplicationSchemaTests(unittest.TestCase):
    def test_request_probe_matches_exact_source_and_rejects_checksum_drift(self):
        from hosted_fixture import postgres_fixture
        from hyprn_mvp_app.hosted_lifecycle import initialize_store, inspect_store
        from hyprn_mvp_app.database import Connection
        from hyprn_mvp_app.migrations import MIGRATIONS, expected
        with postgres_fixture(initialize_schema=False) as fixture:
            initialize_store(fixture['migration'], 'isolated-schema', 'application-schema')
            observed = inspect_store(fixture['request'], 'isolated-schema', 'application-schema')
            self.assertEqual(observed, [{'version': p.stem, 'checksum': expected(p)} for p in MIGRATIONS])
            raw = fixture['migration'].connect()
            try:
                Connection(raw).execute("UPDATE hyprn_schema_versions SET checksum=? WHERE version=?",
                                        ('0' * 64, MIGRATIONS[-1].stem))
                raw.commit()
            finally:
                raw.close()
            with self.assertRaisesRegex(ValueError, 'incompatible'):
                inspect_store(fixture['request'], 'isolated-schema', 'application-schema')
