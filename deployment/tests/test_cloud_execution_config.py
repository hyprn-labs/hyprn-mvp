"""Execution selection cannot silently borrow a local installation's identity."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'integration/src'))
sys.path.insert(0, str(ROOT / 'application/src'))
from hyprn_mvp_integration import installation
from hyprn_mvp_integration import launcher


class WorkerInputPermissionTests(unittest.TestCase):
    def test_canary_mount_is_readable_under_private_host_umask(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            root.chmod(0o700)

            def observe(directory, **kwargs):
                self.assertTrue(kwargs['canary'])
                self.assertEqual(directory.stat().st_mode & 0o777, 0o755)
                self.assertEqual((directory / 'canary.py').stat().st_mode & 0o777, 0o444)
                self.assertEqual(root.stat().st_mode & 0o777, 0o700)
                self.assertEqual((root / 'canaries/host-secret').stat().st_mode & 0o777, 0o600)
                raise RuntimeError('observed worker-readable synthetic input')

            previous = os.umask(0o077)
            try:
                with (patch.object(launcher, 'runtime_root', return_value=root),
                      patch.object(launcher, 'fingerprint', return_value={}),
                      patch.object(launcher, 'probe_homes', return_value=[]),
                      patch.object(launcher, 'isolated', side_effect=observe)):
                    with self.assertRaisesRegex(RuntimeError, 'observed worker-readable'):
                        launcher.attest(root=root)
            finally:
                os.umask(previous)

    def test_private_work_copy_becomes_readable_without_exposing_ancestors(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp).resolve()
            parent.chmod(0o700)
            old = os.umask(0o077)
            try:
                root = parent / 'input'
                (root / 'sources').mkdir(parents=True)
                (root / 'manifest.json').write_bytes(b'authenticated manifest')
                (root / 'sources/model.py').write_bytes(b'authenticated source')
                (parent / 'private-store').write_bytes(b'private sentinel')
            finally:
                os.umask(old)
            files = {'manifest.json': b'authenticated manifest',
                     'sources/model.py': b'authenticated source'}
            launcher.worker_input_permissions(root, ['sources/model.py'])
            for directory in (root, root / 'sources'):
                self.assertEqual(directory.stat().st_mode & 0o777, 0o755)
            for name, raw in files.items():
                self.assertEqual((root / name).stat().st_mode & 0o777, 0o444)
                self.assertEqual((root / name).read_bytes(), raw)
            self.assertEqual(parent.stat().st_mode & 0o777, 0o700)
            self.assertEqual((parent / 'private-store').stat().st_mode & 0o777, 0o600)

    def test_links_and_foreign_ownership_are_refused_before_any_mode_change(self):
        for kind in ('symlink', 'directory-link', 'hardlink', 'foreign-owner'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                parent = Path(tmp).resolve()
                root = parent / 'input'
                root.mkdir(mode=0o700)
                manifest = root / 'manifest.json'
                manifest.write_bytes(b'manifest')
                manifest.chmod(0o600)
                outside = parent / 'outside'
                outside.write_bytes(b'private')
                outside.chmod(0o600)
                name = 'source'
                if kind == 'symlink':
                    (root / name).symlink_to(outside)
                elif kind == 'directory-link':
                    (root / 'linked').symlink_to(parent, target_is_directory=True)
                    name = 'linked/outside'
                elif kind == 'hardlink':
                    os.link(outside, root / name)
                else:
                    (root / name).write_bytes(b'source')
                identity = os.getuid() + 1 if kind == 'foreign-owner' else os.getuid()
                with patch.object(launcher.os, 'getuid', return_value=identity):
                    with self.assertRaisesRegex(ValueError, 'owned unlinked'):
                        launcher.worker_input_permissions(root, [name])
                self.assertEqual(root.stat().st_mode & 0o777, 0o700)
                self.assertEqual(manifest.stat().st_mode & 0o777, 0o600)
                self.assertEqual(outside.stat().st_mode & 0o777, 0o600)

    def test_failed_bundle_authentication_never_changes_work_copy_permissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            with (patch.object(launcher, 'runtime_root', return_value=root),
                  patch.object(launcher, 'require_attestation'),
                  patch.object(launcher, 'selected_runtime', return_value={}),
                  patch.object(launcher, 'bundle_runtime', return_value={}),
                  patch.object(launcher, 'verify_bundle', side_effect=ValueError('immutable digest')),
                  patch.object(launcher, 'worker_input_permissions') as prepare,
                  patch.object(launcher.subprocess, 'Popen') as docker):
                with self.assertRaisesRegex(ValueError, 'immutable digest'):
                    launcher.isolated(root / 'input', expected_digest='a' * 64)
                prepare.assert_not_called()
                docker.assert_not_called()


class CloudExecutionConfigurationTests(unittest.TestCase):
    def test_worker_pin_selects_exportable_platform_image_not_build_index(self):
        sys.path.insert(0, str(ROOT / 'deployment'))
        import execution_runtime
        image = 'sha256:' + 'b' * 64
        record = {'Id': image, 'Os': 'linux', 'Architecture': 'amd64'}
        with patch.object(execution_runtime, 'run', return_value=json.dumps([record])) as run:
            self.assertEqual(execution_runtime.worker_image_identity(
                'sha256:' + 'a' * 64, target='linux/amd64'), image)
            self.assertEqual(run.call_args.args[:5],
                             ('docker', 'image', 'inspect', '--platform', 'linux/amd64'))
        with patch.object(execution_runtime, 'run', return_value=json.dumps([record])):
            with self.assertRaisesRegex(ValueError, 'architecture'):
                execution_runtime.worker_image_identity('reference', target='linux/arm64')
        with patch.object(execution_runtime, 'run', return_value=image) as run:
            self.assertEqual(execution_runtime.worker_image_identity('local'), image)
            self.assertNotIn('--platform', run.call_args.args)

    def test_cloud_selection_rejects_ambient_development_identity(self):
        loader = getattr(installation, 'cloud_from_environment', None)
        self.assertTrue(callable(loader), 'Cloud execution needs a separate validated projection')
        with self.assertRaises(installation.InstallationError):
            loader({'HYPRN_MVP_CLOUD_EXECUTION_CONFIG': '/absent/projection.json',
                    'HYPRN_MVP_DATA_ROOT': '/ambient/development'})

    def test_cloud_projection_is_closed_and_pins_native_identity(self):
        validator = getattr(installation, 'validate_cloud_execution', None)
        self.assertTrue(callable(validator), 'Cloud projection validation is required')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            value = {'schema': 'hyprn-cloud-execution/v1', 'edition': 'cloud',
                     'installation_id': 'isolated-cloud', 'store_id': 'isolated-execution',
                     'execution_root': str(root / 'execution'),
                     'host_home': str(root / 'home'), 'docker': {'endpoint': 'unix://' + str(root / 'docker.sock')},
                     'profile': 'hyprn-mvp-cloud-isolated-cloud', 'source': str(root / 'release/source'),
                     'python': str(root / 'release/native/bin/python'), 'native_root': str(root / 'release/native'),
                     'release_sha256': 'a' * 64, 'config_sha256': 'b' * 64}
            self.assertEqual(validator(value), value)
            for field in ('provider_token', 'database', 'origin', 'data_root'):
                with self.subTest(field=field), self.assertRaises(installation.InstallationError):
                    validator({**value, field: 'forbidden'})
            with self.assertRaises(installation.InstallationError):
                validator({**value, 'profile': 'hyprn-mvp'})

    def test_launcher_cloud_selection_refuses_local_fallback_in_fresh_process(self):
        environment = {key: value for key, value in os.environ.items()
                       if not key.startswith('HYPRN_MVP_')}
        environment.update(PYTHONPATH=os.pathsep.join(str(ROOT / name) for name in
                           ('integration/src', 'application/src')),
                           HYPRN_MVP_CLOUD_EXECUTION_CONFIG='/absent/projection.json',
                           HYPRN_MVP_DATA_ROOT='/ambient/development')
        result = subprocess.run([sys.executable, '-B', '-c',
                                 'from hyprn_mvp_integration import launcher; print(launcher.OWNER)'],
                                env=environment, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0, 'Cloud selection must refuse ambient local roots')
        self.assertNotIn(installation.DEVELOPMENT_OWNER, result.stdout)

    def test_explicit_linux_architecture_changes_engine_cache_identity(self):
        sys.path.insert(0, str(ROOT / 'deployment'))
        import execution_runtime
        amd64 = execution_runtime.engine_inputs(target='linux/amd64')
        arm64 = execution_runtime.engine_inputs(target='linux/arm64')
        self.assertNotEqual(amd64, arm64)
        self.assertEqual(amd64['platform'], 'linux/amd64')
        with self.assertRaises(ValueError):
            execution_runtime.engine_inputs(target='linux/unknown')

    def test_native_projection_digest_excludes_mutable_admission(self):
        sys.path.insert(0, str(ROOT / 'deployment'))
        import cloud_lifecycle
        import cloud_release
        contract = cloud_release.platform_contract((ROOT.parent / 'hyprn-platform').resolve())
        documents = contract.read_json(contract.SCHEMA_PATH.with_name('fixtures.json'))['valid']
        lifecycle = cloud_lifecycle.Lifecycle.__new__(cloud_lifecycle.Lifecycle)
        lifecycle.preview = contract.render(documents['release'], documents['runtime'])
        lifecycle.identity = {'release_sha256': 'a' * 64, 'config_sha256': 'b' * 64}
        projection = lifecycle.preview['execution']['configuration']
        projection.update(source=str(ROOT), native_root=str(ROOT.parent / 'native'),
                          python=str(ROOT.parent / 'native/venv-reviewed/bin/python'))
        first = lifecycle.native_projection()
        lifecycle.preview['admission']['attestation_sha256'] = 'c' * 64
        self.assertEqual(lifecycle.native_projection(), first)
        projection['python'] = str(ROOT.parent / 'native/venv-changed/bin/python')
        self.assertNotEqual(lifecycle.native_projection()['config_sha256'], first['config_sha256'])

    def test_engine_build_preserves_target_through_staging_and_final_identity(self):
        sys.path.insert(0, str(ROOT / 'deployment'))
        import execution_runtime
        calls = []
        image = 'sha256:' + 'a' * 64
        def run(command, **kwargs):
            calls.append(command)
            return subprocess.CompletedProcess(command, 0, '', '')
        with tempfile.TemporaryDirectory() as tmp, patch.object(execution_runtime.subprocess, 'run', run), \
                patch.object(execution_runtime.subprocess, 'check_output', return_value=image + '\n'):
            identity = execution_runtime.build_engine(Path(tmp), no_cache=True, target='linux/amd64')
            build = next(command for command in calls if command[:2] == ['docker', 'build'])
            self.assertIn('--platform=linux/amd64', build)
            self.assertEqual(identity['inputs'], execution_runtime.engine_inputs(target='linux/amd64'))
            self.assertEqual(identity['image'], image)
            self.assertEqual(json.loads((Path(tmp) / 'evidence/engine-build.json').read_text()), identity)
            cached = [{'Id': image, 'Config': {'Labels': {
                'org.hyprn-mvp.engine-inputs': identity['inputs_sha256']}}}]
            calls.clear()
            def cache(command, **kwargs):
                calls.append(command)
                self.assertEqual(command[:3], ['docker', 'image', 'inspect'])
                return subprocess.CompletedProcess(command, 0, json.dumps(cached), '')
            with patch.object(execution_runtime.subprocess, 'run', cache):
                reused = execution_runtime.build_engine(Path(tmp), target='linux/amd64')
            self.assertEqual(reused, identity)
            self.assertEqual(len(calls), 1)


class StoppedWriterTests(unittest.TestCase):
    """Docker observations are doubled; these tests do not qualify a live host."""

    def scenario(self):
        sys.path.insert(0, str(ROOT / 'deployment'))
        import cloud_lifecycle
        host = cloud_lifecycle.Lifecycle.__new__(cloud_lifecycle.Lifecycle)
        host.root = Path('/unused-control')
        host.identity = {'installation_id': 'isolated', 'release_sha256': 'a' * 64,
                         'config_sha256': 'b' * 64}
        host.runtime = {'installation_id': 'isolated'}
        host.preview = {'compose': {'services': {
            name: {'image': name + '@sha256:' + 'c' * 64}
            for name in ('app', 'modeling', 'dispatcher')}}}
        host.identity_check = lambda: None
        host.native_process = lambda: None
        host.remaining = lambda: 10
        admission = dict(schema='hyprn-admission/v1', **host.identity,
                         browser=False, scientific=False, expires_at=0)
        record = {'Id': 'd' * 64, 'Config': {
            'Image': host.preview['compose']['services']['app']['image'],
            'Labels': {'com.docker.compose.project': 'isolated',
                       'com.docker.compose.service': 'database-operation',
                       'com.docker.compose.oneoff': 'True'}},
            'HostConfig': {'RestartPolicy': {'Name': 'no'}},
            'State': {'Running': False, 'Paused': False, 'Restarting': False,
                      'Status': 'exited'}}
        return cloud_lifecycle, host, admission, record

    def observe(self, module, host, admission, records, *, listed=None):
        calls = []
        def docker(command, **kwargs):
            calls.append(command)
            self.assertNotIn('DOCKER_HOST', kwargs['env'])
            if command[1] == 'ps':
                self.assertIn('--all', command)
                self.assertEqual(command[-1], 'label=com.docker.compose.project=isolated')
                output = '\n'.join(listed if listed is not None else [r['Id'] for r in records])
            else:
                self.assertEqual(command[:4], ['docker', 'inspect', '--type', 'container'])
                output = json.dumps(records)
            return subprocess.CompletedProcess(command, 0, output, '')
        with patch.object(module, 'control_record', return_value=admission), \
                patch.object(module.subprocess, 'run', side_effect=docker):
            host.assert_stopped()
        return calls

    def test_stopped_oneoff_is_inspected_without_reacquiring_native_lock(self):
        module, host, admission, record = self.scenario()
        with patch.object(host, 'native_quiescence', side_effect=AssertionError('lock reentry')):
            self.assertEqual(len(self.observe(module, host, admission, [record])), 2)

    def test_active_or_paused_oneoff_refuses_even_when_services_are_stopped(self):
        for facet in ('Running', 'Paused', 'Restarting'):
            with self.subTest(facet=facet):
                module, host, admission, record = self.scenario()
                record['State'][facet] = True
                with self.assertRaises(module.Refused) as error:
                    self.observe(module, host, admission, [record])
                self.assertEqual(error.exception.reason, 'writer_container_not_stopped')

    def test_foreign_image_or_restart_policy_refuses_snapshot(self):
        for change in ('image', 'policy', 'project', 'service'):
            with self.subTest(change=change):
                module, host, admission, record = self.scenario()
                if change == 'image':
                    record['Config']['Image'] = 'foreign'
                elif change == 'policy':
                    record['HostConfig']['RestartPolicy']['Name'] = 'always'
                else:
                    record['Config']['Labels']['com.docker.compose.' + change] = 'foreign'
                with self.assertRaises(module.Refused) as error:
                    self.observe(module, host, admission, [record])
                self.assertEqual(error.exception.reason, 'writer_container_identity_mismatch')

    def test_missing_inspect_identity_or_state_is_not_stopped_proof(self):
        module, host, admission, record = self.scenario()
        with self.assertRaises(module.Refused):
            self.observe(module, host, admission, [], listed=[record['Id']])
        del record['State']['Paused']
        with self.assertRaises(module.Refused):
            self.observe(module, host, admission, [record])

    def test_closed_receipt_must_match_and_use_booleans(self):
        for field, value in (('browser', 0), ('scientific', True),
                             ('installation_id', 'foreign')):
            with self.subTest(field=field):
                module, host, admission, record = self.scenario()
                admission[field] = value
                with self.assertRaises(module.Refused) as error:
                    self.observe(module, host, admission, [record])
                self.assertEqual(error.exception.reason, 'backup_admission_not_closed')

    def test_live_native_process_refuses_before_container_inspection(self):
        module, host, admission, record = self.scenario()
        host.native_process = lambda: {'pid': 123}
        with self.assertRaises(module.Refused) as error:
            self.observe(module, host, admission, [record])
        self.assertEqual(error.exception.reason, 'native_owner_running')
