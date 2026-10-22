"""Real owner ledgers are observed without migration or candidate execution."""

import copy
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / p) for p in ('deployment', 'application/src')]
import cloud_owner_schemas as schemas
import cloud_lifecycle
import test_hosted_backup as backup_fixture


class NativeSchemaTests(unittest.TestCase):
    def setUp(self):
        self.fixture = backup_fixture.OwnerSnapshotTests('runTest')
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()

    def probe(self, owner=None):
        return subprocess.run([sys.executable, '-I', '-B', str(ROOT / 'deployment/cloud_owner_schemas.py')],
                              input=json.dumps(owner or self.fixture.owner), capture_output=True, text=True, timeout=30)

    def test_installed_probe_reads_real_native_schema_without_changing_owner_files(self):
        root = self.fixture.roots['execution']
        def inventory():
            return {str(p.relative_to(root)): (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns)
                    for p in root.rglob('*') if p.is_file()}
        before = inventory()
        result = self.probe()
        self.assertEqual(result.returncode, 0, result.stderr)
        observed = json.loads(result.stdout)
        self.assertEqual(observed['backend'], 'core.sqlite_dos')
        self.assertEqual(observed['repository_uuid'], self.fixture.repository_uuid)
        self.assertTrue(observed['version'])
        self.assertEqual(inventory(), before)

    def test_native_schema_drift_and_foreign_owner_are_refused(self):
        owner = dict(self.fixture.owner, profile_uuid=str(uuid4()))
        self.assertNotEqual(self.probe(owner).returncode, 0)
        path = self.fixture.roots['execution'] / 'aiida-store/database.sqlite'
        with sqlite3.connect(path) as db:
            db.execute("UPDATE alembic_version SET version_num='unknown' ")
        result = self.probe()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('explicit migration', result.stderr)

    def test_missing_database_is_never_created(self):
        path = self.fixture.roots['execution'] / 'aiida-store/database.sqlite'
        path.rename(path.with_suffix('.retained'))
        self.assertNotEqual(self.probe().returncode, 0)
        self.assertFalse(path.exists())

    def test_uncheckpointed_native_wal_is_refused_without_discarding_its_bytes(self):
        path = self.fixture.roots['execution'] / 'aiida-store/database.sqlite'
        db = sqlite3.connect(path)
        try:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE retained_pending(value TEXT)')
            db.execute("INSERT INTO retained_pending VALUES ('retained')")
            db.commit()
            wal = Path(str(path) + '-wal')
            before = wal.read_bytes()
            self.assertTrue(before)
            result = self.probe()
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('journal requires reconciliation', result.stderr)
            self.assertEqual(wal.read_bytes(), before)
            self.assertEqual(db.execute('SELECT value FROM retained_pending').fetchone(), ('retained',))
        finally:
            db.close()


class ModelingSchemaTests(unittest.TestCase):
    def test_real_image_ledgers_are_read_only_and_unknown_migration_is_refused(self):
        import modeling_runtime
        import scoped_fixture
        scope = scoped_fixture.scope_from_environment()
        evidence = scoped_fixture.scoped_path(scope, 'evidence/modeling-build')
        evidence.mkdir()
        image = modeling_runtime.build(evidence=evidence)
        modeling_runtime.reviewed_image(image)
        name = 'hyprn-schema-' + uuid4().hex
        # A scoped named volume is Docker-owned and is never a live installation.
        subprocess.run(['docker', 'volume', 'create', '--label', 'ai.hyprn.schema=' + name, name],
                       check=True, capture_output=True, text=True, timeout=30)
        try:
            base = ['docker', 'run', '--rm', '--pull=never', '--network=none', '--read-only',
                    '--cap-drop=ALL', '--security-opt=no-new-privileges:true', '--pids-limit=128',
                    '--memory=512m', '--cpus=1', '--tmpfs=/tmp:rw,noexec,nosuid,size=32m',
                    '--tmpfs=/native/tmp:rw,noexec,nosuid,size=32m',
                    '--tmpfs=/native/log:rw,noexec,nosuid,size=32m']
            init = subprocess.run([*base, '--user=0:0', '--mount', 'type=volume,src=' + name + ',dst=/store',
                                   '--tmpfs=/run:rw,noexec,nosuid,size=1m', '--entrypoint=sh', image, '-ec',
                                   "ruby -rsecurerandom -e '%w[rails model].each { |n| File.write(\"/run/#{n}.key\", SecureRandom.hex(64)) }'; "
                                   'exec bundle exec rails db:schema:load db:migrate'],
                                  capture_output=True, text=True, timeout=180)
            self.assertEqual(init.returncode, 0, init.stdout + init.stderr)
            def probe():
                return subprocess.run([*base, '--user=0:0', '--mount', 'type=volume,src=' + name + ',dst=/store,readonly',
                                       '--entrypoint=bundle', image, 'exec', 'ruby', '-e', schemas.MODELING_PROBE],
                                      capture_output=True, text=True, timeout=30)
            result = probe()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(set(json.loads(result.stdout)), {'primary', 'scratch'})
            for suffix in ('-wal', '-journal'):
                pending = '/store/model.sqlite3' + suffix
                create = subprocess.run([*base, '--user=0:0', '--mount', 'type=volume,src=' + name + ',dst=/store',
                    '--entrypoint=ruby', image, '-e', 'File.write(ARGV[0], "unfinished")', pending],
                    capture_output=True, text=True, timeout=30)
                self.assertEqual(create.returncode, 0, create.stderr)
                refused = probe()
                self.assertNotEqual(refused.returncode, 0)
                self.assertIn('journal requires reconciliation', refused.stderr)
                remove = subprocess.run([*base, '--user=0:0', '--mount', 'type=volume,src=' + name + ',dst=/store',
                    '--entrypoint=ruby', image, '-e',
                    'raise "journal changed" unless File.read(ARGV[0]) == "unfinished"; File.unlink(ARGV[0])', pending],
                    capture_output=True, text=True, timeout=30)
                self.assertEqual(remove.returncode, 0, remove.stderr)
            drift = subprocess.run([*base, '--user=0:0', '--mount', 'type=volume,src=' + name + ',dst=/store',
                                    '--entrypoint=bundle', image, 'exec', 'ruby', '-rsqlite3', '-e',
                                    "SQLite3::Database.new('/store/model.sqlite3').execute(\"INSERT INTO schema_migrations VALUES ('99999999999999')\")"],
                                   capture_output=True, text=True, timeout=30)
            self.assertEqual(drift.returncode, 0, drift.stderr)
            self.assertNotEqual(probe().returncode, 0)
        finally:
            info = json.loads(subprocess.run(['docker', 'volume', 'inspect', name], check=True,
                              capture_output=True, text=True, timeout=30).stdout)[0]
            self.assertEqual(info['Labels']['ai.hyprn.schema'], name)
            subprocess.run(['docker', 'volume', 'rm', name], check=True, capture_output=True, text=True, timeout=30)


class InspectionAuthorityTests(unittest.TestCase):
    def test_native_receipt_preserves_upstream_uuid_encodings_and_refuses_invalid_types(self):
        from types import SimpleNamespace
        import test_cloud_native_owner
        with tempfile.TemporaryDirectory() as directory:
            case = test_cloud_native_owner.HostRebindTests('runTest').scenario(directory)
            host = case.host
            host.native_command = lambda *_args, **_kwargs: (['fixed-native-probe'], {}, os.getuid())
            host.native_socket_groups = lambda *_args, **_kwargs: []
            host.remaining = lambda: 10
            owner = dict(case.owner, release_sha256=case.new['release_sha256'], config_sha256=case.new['config_sha256'])
            keys = ('profile_uuid', 'repository_uuid', 'computer_uuid', 'code_uuid')
            identifier = uuid4()
            for encoding in (str(identifier), identifier.hex):
                owner.update({key: encoding for key in keys})
                with patch.object(cloud_lifecycle.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout=json.dumps(owner))):
                    self.assertEqual(cloud_lifecycle.Lifecycle.native(host, 'inspect'), owner)
            for invalid in (None, 1, True, [], {}, 'unknown', str(identifier).upper()):
                for key in keys:
                    with self.subTest(field=key, invalid=invalid):
                        bad = dict(owner, **{key: invalid})
                        with patch.object(cloud_lifecycle.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout=json.dumps(bad))):
                            with self.assertRaises(cloud_lifecycle.Refused) as error:
                                cloud_lifecycle.Lifecycle.native(host, 'inspect')
                            self.assertEqual(error.exception.reason, 'native_owner_receipt_invalid')

    def test_incoming_probe_preserves_exact_active_store_authority(self):
        from types import SimpleNamespace
        import test_cloud_native_owner
        for mismatch in (None, 'store', 'root', 'native'):
            with self.subTest(mismatch=mismatch), tempfile.TemporaryDirectory() as directory:
                case = test_cloud_native_owner.HostRebindTests('runTest').scenario(directory)
                runtime = dict(installation_id='retained', project_id='project', project_number='123',
                               disk_uuid='disk', store_ids={'execution': 'retained-store'},
                               mounts={'execution': case.old['execution_root']})
                case.host.runtime = copy.deepcopy(runtime)
                active = SimpleNamespace(root=case.host.root, runtime=runtime,
                    identity={'release_sha256': case.old['release_sha256']},
                    preview={'execution': {'configuration': {k: v for k, v in case.old.items()
                            if k not in ('release_sha256', 'config_sha256')}}},
                    identity_check=lambda: None, assert_stopped=lambda: None)
                if mismatch == 'store':
                    case.host.runtime['store_ids']['execution'] = 'foreign'
                elif mismatch == 'root':
                    case.host.runtime['mounts']['execution'] += '-foreign'
                elif mismatch == 'native':
                    case.owner['release_sha256'] = 'e' * 64
                with (patch.object(cloud_lifecycle, 'control_record', return_value=case.owner),
                      patch.object(cloud_lifecycle, 'binding', return_value={}),
                      patch.object(cloud_lifecycle, 'Lifecycle', return_value=active)):
                    case.host.timeout = 30
                    if mismatch:
                        with self.assertRaises(cloud_lifecycle.Refused):
                            case.host.inspection_owner(str(case.host.root / 'active-binding'))
                    else:
                        self.assertEqual(case.host.inspection_owner(str(case.host.root / 'active-binding')), case.owner)
                        self.assertEqual(json.loads(case.path.read_text()), case.old)

    def test_compatibility_flag_is_never_allowed_on_mutating_operations(self):
        for operation in ('initialize', 'migrate', 'start', 'stop'):
            result = subprocess.run([sys.executable, '-B', str(ROOT / 'deployment/cloud_lifecycle.py'), operation,
                '--binding', 'missing', '--operation-id', str(uuid4()), '--timeout', '30',
                '--compatibility-active-binding', 'missing-active'], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(json.loads(result.stdout)['reason_code'], 'invalid_arguments')

    def test_ordinary_inspect_still_checks_exact_active_release(self):
        host = cloud_lifecycle.Lifecycle.__new__(cloud_lifecycle.Lifecycle)
        host.identity = dict(installation_id='same', release_sha256='a' * 64, config_sha256='b' * 64)
        host.root = Path('/unused-control')
        with patch.object(cloud_lifecycle, 'control_record', return_value=dict(host.identity, release_sha256='c' * 64)):
            with self.assertRaises(cloud_lifecycle.Refused) as error:
                host.operation('inspect')
            self.assertEqual(error.exception.reason, 'installation_identity_mismatch')
