"""Real stopped-owner files roundtrip; PostgreSQL coherence is not asserted here."""

from contextlib import contextmanager
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cloud_backup as backup


class OwnerSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.scope = tempfile.TemporaryDirectory(prefix='owner-backup-')
        self.addCleanup(self.scope.cleanup)
        self.root = Path(self.scope.name).resolve()
        self.roots = {name: self.root / name for name in backup.ROOTS}
        for path in self.roots.values():
            path.mkdir(mode=0o700)
        execution = self.roots['execution']
        os.environ['AIIDA_PATH'] = str(execution / 'aiida')
        from aiida.manage.configuration.settings import AiiDAConfigDir
        from aiida.manage.configuration.profile import Profile
        import aiida.manage.configuration as configuration
        from aiida.storage.sqlite_dos.backend import SqliteDosStorage
        from aiida import orm
        from disk_objectstore import Container
        AiiDAConfigDir.set(execution / 'aiida/.aiida')
        self.profile = Profile('snapshot-' + uuid4().hex, dict(
            PROFILE_UUID=str(uuid4()), storage=dict(backend='core.sqlite_dos',
            config=dict(filepath=str(execution / 'aiida-store'))),
            process_control=dict(backend=None, config=None), test_profile=True))
        config = dict(CONFIG_VERSION={'CURRENT': 10, 'OLDEST_COMPATIBLE': 10},
                      default_profile=None, profiles={self.profile.name: self.profile.dictionary})
        (execution / 'aiida/.aiida/config.json').write_bytes(backup.canonical(config))
        configuration.CONFIG = None
        SqliteDosStorage.initialise(self.profile)
        backend = SqliteDosStorage(self.profile)
        try:
            user = orm.User(email='fixture@hyprn.invalid', backend=backend).store()
            computer = orm.Computer(label='retained', hostname='localhost',
                transport_type='core.local', scheduler_type='core.direct',
                workdir=str(execution / 'work/{username}'), backend=backend).store()
            code = orm.InstalledCode(label='retained', computer=computer,
                filepath_executable=str(execution / 'launch-worker'), backend=backend, user=user).store()
            node = orm.Dict(dict={'temperature': 273.15, 'units': 'K'}, backend=backend, user=user)
            node.base.repository.put_object_from_filelike(io.BytesIO(b'exact historical source\n'), 'source.py')
            node.store()
            self.node_uuid = node.uuid
            self.source_hash = node.base.repository.get_object('source.py').key
            self.repository_uuid = backend.get_repository().uuid
            self.owner = dict(schema='hyprn-native-owner/v1', installation_id='isolated-backup',
                store_id='execution-store', execution_root=str(execution), profile=self.profile.name,
                profile_uuid=self.profile.uuid, repository_uuid=self.repository_uuid,
                computer_uuid=computer.uuid, code_uuid=code.uuid,
                release_sha256='a' * 64, config_sha256='c' * 64)
        finally:
            backend.close()
        with Container(execution / 'aiida-store/container') as container:
            container.pack_all_loose(compress=True)
            self.loose_hash = container.add_object(b'additional retained artifact')
            self.assertTrue(container.validate().is_valid())
        native_identity = {key: self.owner[key] for key in
                           ('profile_uuid', 'repository_uuid', 'computer_uuid', 'code_uuid')}
        (execution / 'profile-identity.json').write_bytes(backup.canonical(dict(native_identity, profile=self.profile.name)))
        (execution / 'evidence').mkdir(mode=0o700)
        (execution / 'evidence/containment.json').write_bytes(b'{"stale":true}')
        (execution / 'launch-worker').write_bytes(b'#!/bin/sh\nexit 1\n')
        (execution / 'launch-worker').chmod(0o700)
        self.connections = []
        for name in ('model.sqlite3', 'scratch.sqlite3'):
            connection = sqlite3.connect(self.roots['modeling'] / name)
            self.connections.append(connection)
            self.addCleanup(connection.close)
            connection.execute('PRAGMA journal_mode=WAL')
            connection.execute('CREATE TABLE retained (id TEXT PRIMARY KEY, source BLOB)')
            connection.execute('INSERT INTO retained VALUES (?, ?)', (self.node_uuid, b'explicit source bytes'))
            connection.commit()
        (self.roots['modeling'] / 'initialized').touch()
        (self.roots['artifacts'] / 'historical.bin').write_bytes(b'\x00\x01exact retained output\xff')
        (self.roots['artifacts'] / 'empty').mkdir(mode=0o700)
        self.identity = dict(installation_id='isolated-backup', release_sha256='a' * 64,
            config_sha256='b' * 64, store_ids=dict(application='application-store',
                                                modeling='modeling-store', execution='execution-store'))
        self.snapshot = self.root / 'snapshot'

    @contextmanager
    def held(self):
        with backup.native_hold(self.roots['execution'], self.profile.name, timeout=60) as hold:
            yield hold

    def snapshot_now(self):
        with self.held() as hold:
            return backup.snapshot_files(hold, self.snapshot, roots=self.roots,
                                         identity=self.identity, owner=self.owner)

    def empty_original_paths(self):
        for connection in self.connections:
            connection.close()
        for name, root in self.roots.items():
            root.rename(self.root / ('retained-before-restore-' + name))
            root.mkdir(mode=0o700)

    def verify(self):
        return backup.verified_manifest(self.snapshot, identity=self.identity, owner=self.owner,
                                        roots=self.roots, deadline=time.monotonic() + 60)

    def test_real_native_modeling_and_artifact_roundtrip_preserves_history_and_closes_execution(self):
        from aiida import orm
        from aiida.storage.sqlite_dos.backend import SqliteDosStorage
        from disk_objectstore import Container
        manifest = self.snapshot_now()
        self.assertFalse(manifest['coherent_backup'])
        self.assertEqual(manifest['application_database'], 'not_included')
        self.verify()
        self.assertFalse(any(entry['path'].endswith(('-wal', '-shm', '.lock')) for entry in manifest['entries']))
        self.empty_original_paths()
        receipt = backup.restore_files(self.snapshot, roots=self.roots, identity=self.identity,
                                       owner=self.owner, timeout=60)
        self.assertFalse(receipt['coherent_backup'])
        self.assertEqual(receipt['native_owner'], self.owner)
        for name in ('model.sqlite3', 'scratch.sqlite3'):
            with sqlite3.connect(self.roots['modeling'] / name) as connection:
                self.assertEqual(connection.execute('SELECT * FROM retained').fetchall(),
                                 [(self.node_uuid, b'explicit source bytes')])
        execution = self.roots['execution']
        backend = SqliteDosStorage(self.profile)
        try:
            restored = orm.QueryBuilder(backend=backend).append(orm.Dict,
                filters={'uuid': self.node_uuid}, project='*').one()[0]
            self.assertEqual(restored.get_dict(), {'temperature': 273.15, 'units': 'K'})
            self.assertEqual(restored.base.repository.get_object_content('source.py', mode='rb'),
                             b'exact historical source\n')
            self.assertEqual(backend.get_repository().uuid, self.repository_uuid)
        finally:
            backend.close()
        with Container(execution / 'aiida-store/container') as container:
            self.assertEqual(container.get_object_content(self.loose_hash), b'additional retained artifact')
            self.assertTrue(container.validate().is_valid())
        self.assertFalse((execution / 'evidence/containment.json').exists())
        self.assertEqual(next((execution / 'evidence').glob('containment-*.json')).read_bytes(), b'{"stale":true}')
        self.assertEqual((execution / 'launch-worker').stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.roots['artifacts'] / 'historical.bin').read_bytes(), b'\x00\x01exact retained output\xff')
        self.assertTrue((self.roots['artifacts'] / 'empty').is_dir())
        # Snapshot verification remains unchanged after restore; retained evidence was not rewritten.
        self.verify()

    def test_executor_and_profile_locks_remain_held_for_the_whole_caller_context(self):
        script = '''import os,sys,fcntl
from pathlib import Path
root=Path(sys.argv[1]);os.environ['AIIDA_PATH']=str(root/'aiida')
if sys.argv[2]=='executor':
    fd=os.open(root/'executor.lock',os.O_RDWR)
    try: fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError: sys.exit(23)
else:
    import cloud_backup
    from aiida.manage.profile_access import ProfileAccessManager
    from aiida.common.exceptions import LockedProfileError
    try: ProfileAccessManager(cloud_backup.profile_at(root,sys.argv[3])).request_access()
    except LockedProfileError: sys.exit(23)
'''
        with self.held() as hold:
            backup.snapshot_files(hold, self.snapshot, roots=self.roots, identity=self.identity, owner=self.owner)
            for kind in ('executor', 'profile'):
                result = subprocess.run([sys.executable, '-B', '-c', script, str(hold.root), kind, self.profile.name],
                    env=dict(os.environ, PYTHONPATH=str(Path(backup.__file__).parent)),
                    capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 23, result.stderr)
        with self.held() as hold:
            hold.check()

    def test_tampered_missing_extra_and_unsafe_inventory_never_touch_restore_targets(self):
        self.snapshot_now()
        self.empty_original_paths()
        path = self.snapshot / 'artifacts/historical.bin'
        original = path.read_bytes()
        path.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'bytes mismatch'):
            backup.restore_files(self.snapshot, roots=self.roots, identity=self.identity, owner=self.owner, timeout=60)
        path.write_bytes(original)
        manifest_path = self.snapshot / 'manifest.json'
        raw = manifest_path.read_bytes()
        manifest_path.unlink()
        with self.assertRaises(FileNotFoundError):
            backup.restore_files(self.snapshot, roots=self.roots, identity=self.identity, owner=self.owner, timeout=60)
        manifest_path.write_bytes(raw)
        extra = self.snapshot / 'unlisted'
        extra.write_bytes(b'extra')
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            self.verify()
        extra.unlink()
        manifest = json.loads(raw)
        manifest['entries'][0]['path'] = '../escape'
        manifest_path.write_bytes(backup.canonical(manifest))
        with self.assertRaisesRegex(ValueError, 'Unsafe'):
            backup.restore_files(self.snapshot, roots=self.roots, identity=self.identity, owner=self.owner, timeout=60)
        self.assertTrue(all(not any(root.iterdir()) for root in self.roots.values()))

    def test_nonempty_changed_identity_and_relocated_restore_are_refused(self):
        self.snapshot_now()
        with self.assertRaisesRegex(ValueError, 'empty'):
            backup.restore_files(self.snapshot, roots=self.roots, identity=self.identity, owner=self.owner, timeout=60)
        self.empty_original_paths()
        with self.assertRaisesRegex(ValueError, 'identity'):
            backup.restore_files(self.snapshot, roots=self.roots, identity=dict(self.identity, config_sha256='d' * 64),
                                 owner=self.owner, timeout=60)
        changed = dict(self.roots, artifacts=self.root / 'different-artifacts')
        changed['artifacts'].mkdir()
        with self.assertRaisesRegex(ValueError, 'identity'):
            backup.restore_files(self.snapshot, roots=changed, identity=self.identity, owner=self.owner, timeout=60)
        self.assertTrue(all(not any(root.iterdir()) for root in self.roots.values()))

    def test_linked_sources_and_object_corruption_refuse_manifest_publication(self):
        external = self.root / 'outside'
        external.write_bytes(b'private')
        link = self.roots['artifacts'] / 'linked'
        link.symlink_to(external)
        with self.assertRaisesRegex(ValueError, 'unlinked'):
            self.snapshot_now()
        self.assertFalse(self.snapshot.exists())
        link.unlink()
        container = self.roots['execution'] / 'aiida-store/container'
        loose = next(path for path in (container / 'loose').rglob('*') if path.is_file()
                     and hashlib.sha256(path.read_bytes()).hexdigest() == self.loose_hash)
        loose.write_bytes(b'corrupt retained content')
        with self.assertRaisesRegex(ValueError, 'object bytes'):
            self.snapshot_now()
        self.assertFalse((self.snapshot / 'manifest.json').exists())

    def test_stale_hold_and_expired_budget_never_publish_snapshot(self):
        with self.held() as hold:
            hold.deadline = time.monotonic() - 1
            with self.assertRaises(TimeoutError):
                backup.snapshot_files(hold, self.snapshot, roots=self.roots, identity=self.identity, owner=self.owner)
        with self.assertRaisesRegex(ValueError, 'not active'):
            backup.snapshot_files(hold, self.snapshot, roots=self.roots, identity=self.identity, owner=self.owner)
        self.assertFalse(self.snapshot.exists())

    def test_missing_referenced_object_is_not_a_valid_empty_repository(self):
        from disk_objectstore import Container
        with Container(self.roots['execution'] / 'aiida-store/container') as container:
            container.delete_objects([self.source_hash])
            self.assertTrue(container.validate().is_valid())
        with self.assertRaisesRegex(ValueError, 'referenced object missing'):
            self.snapshot_now()
        self.assertFalse((self.snapshot / 'manifest.json').exists())

    def test_unsettled_native_process_refuses_snapshot(self):
        from aiida import orm
        from aiida.storage.sqlite_dos.backend import SqliteDosStorage
        backend = SqliteDosStorage(self.profile)
        try:
            user = orm.QueryBuilder(backend=backend).append(orm.User, project='*').one()[0]
            orm.CalcJobNode(backend=backend, user=user).store()
        finally:
            backend.close()
        with self.assertRaisesRegex(ValueError, 'requires reconciliation'):
            self.snapshot_now()
        self.assertFalse(self.snapshot.exists())

    def test_interrupted_restore_never_activates_old_attestation_or_retries_partial_stores(self):
        self.snapshot_now()
        self.empty_original_paths()
        with patch.object(backup, 'validate_native', side_effect=RuntimeError('isolated injected interruption')):
            with self.assertRaisesRegex(RuntimeError, 'interruption'):
                backup.restore_files(self.snapshot, roots=self.roots, identity=self.identity,
                                     owner=self.owner, timeout=60)
        execution = self.roots['execution']
        self.assertFalse((execution / 'evidence/containment.json').exists())
        self.assertEqual(next((execution / 'evidence').glob('containment-*.json')).read_bytes(), b'{"stale":true}')
        self.assertTrue((execution / 'aiida-store/database.sqlite').is_file())
        with self.assertRaisesRegex(ValueError, 'empty'):
            backup.restore_files(self.snapshot, roots=self.roots, identity=self.identity, owner=self.owner, timeout=60)
        self.verify()


if __name__ == '__main__':
    unittest.main()
