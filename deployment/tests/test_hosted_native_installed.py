"""Real Linux initialization from exact packaged bytes; no source fallback."""

import json
import unittest

import scoped_fixture as fixture
from installed_native_fixture import rehearse


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
