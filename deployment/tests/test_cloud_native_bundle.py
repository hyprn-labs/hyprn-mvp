"""A native archive is self-contained data, never an escape into the build host."""

import importlib.util
import json
import os
from pathlib import Path
import shutil
import tarfile
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    'cloud_native_bundle', Path(__file__).resolve().parents[1] / 'cloud_native_bundle.py')
bundle = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bundle)


class NativeBundleTests(unittest.TestCase):
    def setUp(self):
        self.scope = tempfile.TemporaryDirectory(prefix='hyprn-native-bundle-')
        self.addCleanup(self.scope.cleanup)
        self.root = Path(self.scope.name).resolve()
        self.prefix = self.root / ('a' * 40)
        self.prefix.mkdir()
        (self.prefix / 'native').mkdir()
        for name in ('runtime.json', 'selected.json'):
            (self.prefix / 'native' / name).write_text('{}')
        (self.prefix / 'build.json').write_text(json.dumps({
            'prefix': str(self.prefix), 'source_commit': 'a' * 40,
            'native_lock_sha256': 'b' * 64,
        }))

    def test_internal_links_become_regular_files_with_executable_mode_retained(self):
        executable = self.prefix / 'native/python'
        executable.write_bytes(b'reviewed interpreter fixture')
        executable.chmod(0o755)
        (self.prefix / 'native/python3').symlink_to('python')
        output = self.root / 'bundle.tar.gz'
        record = bundle.pack(self.prefix, output)
        self.assertEqual(record['sha256'], bundle.digest(output))
        with tarfile.open(output) as archive:
            self.assertTrue(all(m.isfile() for m in archive.getmembers()))
            self.assertEqual(archive.extractfile('native/python3').read(), executable.read_bytes())
            self.assertEqual(archive.getmember('native/python3').mode, 0o755)
            self.assertIn('native/python3', json.load(archive.extractfile('bundle-inventory.json')))

    def test_outside_links_and_directory_cycles_are_refused_before_archive_write(self):
        secret = self.root / 'not-a-build-input'
        secret.write_bytes(b'private fixture')
        link = self.prefix / 'escape'
        link.symlink_to(secret)
        output = self.root / 'bundle.tar.gz'
        with self.assertRaisesRegex(ValueError, 'Out-of-bundle'):
            bundle.pack(self.prefix, output)
        self.assertFalse(output.exists())
        link.unlink()
        link.symlink_to(self.prefix, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'cycle'):
            bundle.pack(self.prefix, output)
        self.assertFalse(output.exists())

    def test_source_links_and_special_files_are_not_build_inputs(self):
        (self.prefix / 'source-link').symlink_to('build.json')
        with self.assertRaisesRegex(ValueError, 'Source symlink'):
            list(bundle.files(self.prefix, allow_links=False))
        (self.prefix / 'source-link').unlink()
        os.mkfifo(self.prefix / 'pipe')
        with self.assertRaisesRegex(ValueError, 'Special bundle'):
            list(bundle.files(self.prefix))

    def test_incomplete_and_existing_outputs_are_refused(self):
        output = self.root / 'bundle.tar.gz'
        (self.prefix / 'native/selected.json').unlink()
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            bundle.pack(self.prefix, output)
        output.write_bytes(b'keep')
        with self.assertRaisesRegex(ValueError, 'New external'):
            bundle.pack(self.prefix, output)
        self.assertEqual(output.read_bytes(), b'keep')

    def test_extraction_tampering_is_refused_before_any_interpreter_runs(self):
        output = self.root / 'bundle.tar.gz'
        bundle.pack(self.prefix, output)
        shutil.rmtree(self.prefix)
        self.prefix.mkdir()
        with tarfile.open(output) as archive:
            archive.extractall(self.prefix, filter='data')
        (self.prefix / 'native/runtime.json').write_text('{"changed":true}')
        with patch.object(bundle, 'linux'), patch.object(bundle.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'bytes differ'):
                bundle.verify_extracted(self.prefix)
            run.assert_not_called()

    def test_relocation_is_refused_before_any_interpreter_runs(self):
        (self.prefix / 'build.json').write_text(json.dumps({'prefix': '/different'}))
        with patch.object(bundle, 'linux'), patch.object(bundle.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'cannot be relocated'):
                bundle.verify_extracted(self.prefix)
            run.assert_not_called()

    def test_imports_use_disposable_home_and_never_inherit_operator_secrets(self):
        output = self.root / 'bundle.tar.gz'
        bundle.pack(self.prefix, output)
        shutil.rmtree(self.prefix)
        self.prefix.mkdir()
        with tarfile.open(output) as archive:
            archive.extractall(self.prefix, filter='data')
        homes = []
        def inspect_environment(command, **kwargs):
            env = kwargs['env']
            self.assertNotIn('PROVIDER_KEY', env)
            home = Path(env['HOME'])
            self.assertTrue(home.is_dir())
            self.assertFalse(home.is_relative_to(self.prefix))
            self.assertTrue(Path(env['AIIDA_PATH']).is_relative_to(home))
            homes.append(home)
        with patch.object(bundle, 'linux'), patch.dict(os.environ, {'PROVIDER_KEY': 'fixture'}), \
                patch.object(bundle.subprocess, 'run', side_effect=inspect_environment):
            self.assertTrue(bundle.verify_extracted(self.prefix)['verified'])
        self.assertEqual(len(homes), 1)
        self.assertFalse(homes[0].exists())


if __name__ == '__main__':
    unittest.main()
