"""Mandatory post-build gate: source checks cannot stand in for installed bytes."""

import live_fence
setUpModule, tearDownModule = live_fence.unittest_module_hooks('baseline')

import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cloud_release
import scoped_fixture as fixture
from installed_hosted_fixture import rehearse_application


class InstalledHostedArtifactTests(unittest.TestCase):
    def test_exact_payload_requires_actual_linux_installation_rehearsal(self):
        scope = fixture.scope_from_environment()
        path = fixture.scoped_path(scope, 'artifacts/hosted-artifact-input.json')
        self.assertTrue(path.is_file(), 'Built hosted payload and reviewed documents are required')
        inputs = json.loads(path.read_bytes())
        contract, documents, _ = cloud_release.documents(inputs['platform_root'], inputs)
        payload = cloud_release.payload(inputs['payload'], documents['release'], contract)
        result = rehearse_application(scope, inputs, documents, payload)
        self.assertTrue(result['actual_packaged_factory'])
        self.assertTrue(result['replacement_retained_studies'])
        self.fail('Aggregate installed native/app lifecycle and trusted admission evidence remain required '
                  'before publication; focused installed slices do not qualify the complete hosted payload')
