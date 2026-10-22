"""Cross-repository recovery acceptance uses the pinned native environment."""

import importlib.util
import json
import os
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
    suite = loader.loadTestsFromModule(module)
    if suite.countTestCases() == 0:
        raise ValueError('Platform backup-set checks collected no tests')
    return suite
