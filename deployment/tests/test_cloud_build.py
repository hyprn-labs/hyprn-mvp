"""Only committed, unchanged source can become a cloud Docker build context."""

import live_fence
setUpModule, tearDownModule = live_fence.unittest_module_hooks('unit')

from pathlib import Path
import json
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import cloud_build


class CloudBuildTests(unittest.TestCase):
    def setUp(self):
        scope = tempfile.TemporaryDirectory(prefix='hyprn-cloud-build-')
        self.addCleanup(scope.cleanup)
        self.root = Path(scope.name).resolve()
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.git('init', '--quiet')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('config', 'user.name', 'Fixture')
        (self.repo / 'input.txt').write_text('committed')
        self.commit = self.save()
        self.output = self.root / 'build'

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], text=True).strip()

    def save(self):
        self.git('add', '--', 'input.txt')
        self.git('commit', '--quiet', '-m', 'Fixture')
        return self.git('rev-parse', 'HEAD')

    def snapshot(self):
        return cloud_build.snapshot(self.repo, self.commit, self.output)

    def test_dirty_and_untracked_bytes_never_enter_build_context(self):
        (self.repo / 'input.txt').write_text('uncommitted')
        (self.repo / 'credential.key').write_text('private fixture')
        self.snapshot()
        self.assertEqual((self.output / 'source/input.txt').read_text(), 'committed')
        self.assertFalse((self.output / 'source/credential.key').exists())
        self.assertEqual(cloud_build.verify_source(self.output)['source_commit'], self.commit)

    def test_snapshot_identity_is_repeatable_and_output_is_create_only(self):
        first = self.snapshot()
        second = cloud_build.snapshot(self.repo, self.commit, self.root / 'other')
        self.assertEqual(first['source_record_sha256'], second['source_record_sha256'])
        with self.assertRaisesRegex(ValueError, 'New build'):
            self.snapshot()

    def test_snapshot_refuses_mutable_refs_symlinks_and_repository_output(self):
        with self.assertRaisesRegex(ValueError, 'Exact full'):
            cloud_build.snapshot(self.repo, 'HEAD', self.output)
        with self.assertRaisesRegex(ValueError, 'outside repository'):
            cloud_build.snapshot(self.repo, self.commit, self.repo / 'build')
        (self.repo / 'input.txt').unlink()
        (self.repo / 'input.txt').symlink_to('../private')
        self.commit = self.save()
        with self.assertRaisesRegex(ValueError, 'unsupported entries'):
            self.snapshot()

    def test_changed_source_is_refused_before_docker(self):
        self.snapshot()
        (self.output / 'source/input.txt').write_text('changed')
        with patch.object(cloud_build.subprocess, 'run') as docker:
            with self.assertRaisesRegex(ValueError, 'source changed'):
                cloud_build.build_app(self.output)
        docker.assert_not_called()

    def test_added_source_or_changed_archive_is_refused(self):
        self.snapshot()
        extra = self.output / 'source/extra'
        extra.write_text('unexpected')
        with self.assertRaisesRegex(ValueError, 'source changed'):
            cloud_build.verify_source(self.output)
        extra.unlink()
        (self.output / 'source.tar').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'source changed'):
            cloud_build.verify_source(self.output)

    def test_tracked_private_directory_is_not_exported(self):
        (self.repo / 'credentials').mkdir()
        (self.repo / 'credentials/key').write_text('private fixture')
        self.git('add', '--', 'credentials/key')
        self.git('commit', '--quiet', '-m', 'Private fixture')
        self.commit = self.git('rev-parse', 'HEAD')
        with self.assertRaisesRegex(ValueError, 'Private or generated'):
            self.snapshot()
        self.assertFalse((self.output / 'source').exists())

    def test_payload_keeps_actual_evidence_and_verifies_copied_bytes(self):
        documents = self.root / 'documents'
        documents.mkdir()
        roles = ('app', 'modeling', 'worker', 'native_bundle', 'ui', 'tests')
        inputs = {}
        for role in roles:
            source = self.root / (role + '.input')
            source.write_text('runtime acceptance pending' if role == 'tests' else role)
            inputs[role] = str(source)
        inputs_path = self.root / 'inputs.json'
        inputs_path.write_text(json.dumps(inputs))
        release = {'images': {role: 'image@sha256:' + 'a' * 64
                              for role in ('app', 'modeling', 'worker')},
                   'native_bundle': {},
                   'ui_manifest_sha256': cloud_build.cloud_release.file_hash(inputs['ui']),
                   'evidence': {'tests': cloud_build.cloud_release.file_hash(inputs['tests'])}}
        values = {'release': release, 'runtime': {}, 'desired': {}, 'workload': {}}
        contract = SimpleNamespace(digest=cloud_build.cloud_release.digest,
                                   check_bundle=lambda *args: None)
        with patch.object(cloud_build.cloud_release, 'documents',
                          return_value=(contract, values, {})), \
                patch.object(cloud_build.cloud_release, 'verify_oci'):
            result = cloud_build.freeze_payload(self.root, documents, inputs_path, self.output)
        self.assertTrue(result['payload_verified'])
        self.assertFalse(result['runtime_acceptance_performed'])
        self.assertEqual((self.output / 'tests.json').read_text(), 'runtime acceptance pending')
        (self.output / 'tests.json').write_text('incorrect qualification')
        with self.assertRaisesRegex(ValueError, 'payload_bytes'):
            cloud_build.cloud_release.payload(self.output / 'payload.json', release, contract)

    def test_payload_missing_role_is_refused_before_creating_output(self):
        documents = self.root / 'documents'
        documents.mkdir()
        inputs_path = self.root / 'inputs.json'
        inputs_path.write_text('{}')
        values = {'release': {'evidence': {'tests': 'a' * 64}}}
        with patch.object(cloud_build.cloud_release, 'documents',
                          return_value=(None, values, {})):
            with self.assertRaisesRegex(ValueError, 'Every payload role'):
                cloud_build.freeze_payload(self.root, documents, inputs_path, self.output)
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()
