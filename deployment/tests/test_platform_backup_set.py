"""Cross-repository recovery acceptance uses the pinned native environment."""

import live_fence
setUpModule, tearDownModule = live_fence.unittest_module_hooks('unit')

import importlib.util
import json
import os
import sys
from pathlib import Path
import unittest


def load_tests(loader, _standard_tests, _pattern):
    import scoped_fixture
    scope = scoped_fixture.scope_from_environment()
    inputs = json.loads(scoped_fixture.scoped_path(
        scope, 'artifacts/platform-backup-set-input.json').read_text())
    platform = Path(inputs['platform'])
    os.environ['HYPRN_MVP_SOURCE_ROOT'] = inputs['product']
    target = platform / 'tests/platform/test_backup_set.py'
    specification = importlib.util.spec_from_file_location('platform_backup_set_checks', target)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    # unittest resolves module hooks through sys.modules, including loaded suites.
    # Fence the external tests themselves, not only this forwarding module.
    if hasattr(module, 'setUpModule') or hasattr(module, 'tearDownModule'):
        raise ValueError('External backup checks need explicit fence-hook composition')
    module.setUpModule, module.tearDownModule = setUpModule, tearDownModule
    sys.modules[module.__name__] = module
    suite = loader.loadTestsFromModule(module)
    if suite.countTestCases() == 0:
        raise ValueError('Platform backup-set checks collected no tests')
    return suite
