"""Real Linux initialization from exact packaged bytes; no source fallback."""

import live_fence
setUpModule, tearDownModule = live_fence.unittest_module_hooks('baseline')

import json
import unittest
from unittest.mock import patch

import scoped_fixture as fixture
from installed_native_fixture import owned_workers, platform_cli, rehearse


class InstalledNativeTests(unittest.TestCase):
    def test_released_native_owner_initializes_and_retains_actual_identity(self):
        scope = fixture.scope_from_environment()
        path = fixture.scoped_path(scope, 'artifacts/hosted-native-input.json')
        self.assertTrue(path.is_file(), 'Exact native bundle input is required')
        result = rehearse(scope, json.loads(path.read_bytes()))
        self.assertTrue(result['verified_extraction'])
        self.assertTrue(result['reinitialization_refused'])
        self.assertTrue(result['unattested_check_refused'])
        self.assertTrue(result['attested'])
        self.assertEqual(result['calculation']['exit_status'],0)
        self.assertTrue(result['restart_read_identical'])
        self.assertTrue(result['duplicate_native_request_refused'])
        self.assertTrue(result['released_lifecycle_wrapper'])
        self.assertEqual(result['schema_observation']['repository_uuid'],
                         result['owner']['repository_uuid'])


class InstalledFixtureGuards(unittest.TestCase):
    def test_platform_shim_requires_exact_supported_target(self):
        self.assertEqual(platform_cli('linux/amd64'),
                         '#!/bin/sh\nexport DOCKER_DEFAULT_PLATFORM=linux/amd64\n'
                         'exec /usr/local/libexec/docker "$@"\n')
        for target in ('linux/arm64', 'linux/amd64; exit 0', ''):
            with self.subTest(target=target), self.assertRaises(ValueError):
                platform_cli(target)

    def test_worker_discovery_preserves_live_fence_and_exact_owner(self):
        owner = 'hyprn-mvp-cloud-rehearsal-00000000-0000-4000-8000-000000000001'
        calls = []
        def command(*args):
            self.assertIsNone(live_fence.decide(
                'subprocess.Popen', ('docker', ['docker', *args], None, None), 'baseline'))
            calls.append(args)
            if args[0] == 'ps':
                return 'owned foreign'
            return json.dumps([{'Config': {'Labels': {'org.hyprn-mvp.owner':
                owner if args[1] == 'owned' else 'hyprn-mvp-cloud-live'}}}])
        with patch('installed_native_fixture.docker', side_effect=command):
            self.assertEqual(owned_workers(owner), ['owned'])
        self.assertEqual(calls[0], ('ps', '-aq', '--filter', 'label=org.hyprn-mvp.owner'))
        self.assertTrue(all(call[0] != 'rm' for call in calls))
        self.assertEqual(live_fence.decide('subprocess.Popen',
            ('docker', ['docker', 'rm', 'hyprn-mvp-cloud-live'], None, None), 'baseline'),
            'docker names a live resource')
