"""Focused installed application slice; it cannot qualify aggregate host lifecycle."""

import live_fence
setUpModule, tearDownModule = live_fence.unittest_module_hooks('baseline')

import json
import unittest

import cloud_release
import scoped_fixture as fixture
from installed_hosted_fixture import rehearse_application


class InstalledHostedApplicationTests(unittest.TestCase):
    def test_exact_application_image_runs_private_workspace_and_retains_restart(self):
        scope = fixture.scope_from_environment()
        path = fixture.scoped_path(scope, 'artifacts/hosted-artifact-input.json')
        self.assertTrue(path.is_file(), 'Built hosted payload and reviewed documents are required')
        inputs = json.loads(path.read_bytes())
        contract, documents, _ = cloud_release.documents(inputs['platform_root'], inputs)
        payload = cloud_release.payload(inputs['payload'], documents['release'], contract)
        observed = rehearse_application(scope, inputs, documents, payload)
        self.assertTrue(observed['replacement_retained_studies'])
        self.assertTrue(observed['foreign_reads_denied'])
        self.assertTrue(observed['live_migration_refused'])
        self.assertFalse(observed['aggregate_host_lifecycle_verified'])
