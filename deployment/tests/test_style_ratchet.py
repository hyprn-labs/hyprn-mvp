"""Readability ratchet: existing code may keep its baselined violations, new code may not.

The tree itself must pass ``deployment/style_ratchet.py``. Seeded repositories (a scratch Git
repository per test, below the scope's temporary folder) show that each kind of new violation
fails, that unchanged or shrinking violations pass, that excluded files are never checked, and
that a missing tool, baseline or base commit refuses instead of passing.
"""

# Live-runtime fence (deployment/tests/live_fence.py): refuses live roots, live ports, docker,
# live entry points and real signals.
import sys as _fence_sys
from pathlib import Path as _FencePath

if str(_FencePath(__file__).resolve().parent) not in _fence_sys.path:
    _fence_sys.path.append(str(_FencePath(__file__).resolve().parent))
import live_fence  # noqa: E402

setUpModule, tearDownModule = live_fence.unittest_module_hooks('unit')
import ast  # noqa: E402
import json  # noqa: E402
from pathlib import Path  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import tempfile  # noqa: E402
import unittest  # noqa: E402
from unittest.mock import patch  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
if str(REPO / 'deployment') not in sys.path:
    sys.path.insert(0, str(REPO / 'deployment'))
import style_ratchet as ratchet  # noqa: E402

# The pin tables of test files known today, as (module, table name). A new table is picked up
# by the ratchet on its own; this list makes that addition a reviewed change of this test.
KNOWN_PIN_TABLES = (('contracts/tests/test_unit_declaration_contracts.py', 'FIXTURE_HASHES'),)
GIT = ['git', '-c', 'user.name=Style', '-c', 'user.email=style@example.invalid']
GIT += ['-c', 'commit.gpgsign=false', '-c', 'init.defaultBranch=base']
WORDS = ' '.join(['word'] * 30)
LONG_PYTHON = "text = '" + WORDS + "'\n"
LONG_SCRIPT = "export const text = '" + WORDS + "';\n"
DIGEST = '0' * 64

SEED = {
    # Owners of the exclusions, in the shape of the real owners.
    'application/tests/test_module_boundaries.py': (
        "ATTESTED_PROJECT_FILES = frozenset({'application/src/pkg/attested.py'})\n"
    ),
    'integration/src/hyprn_mvp_integration/launcher.py': (
        'def execution_source_hashes():\n'
        '    paths = [\n'
        "        'integration/src/hyprn_mvp_integration/launcher.py',\n"
        "        'deployment/runtime.py',\n"
        '    ]\n'
        '    return paths\n'
    ),
    'contracts/tests/test_pins.py': (
        "FIXTURE_HASHES = {'contracts/tests/test_pinned.py': '" + DIGEST + "'}\n"
        "NAMES = {'NotAPath': '" + DIGEST + "'}\n"
    ),
    'contracts/tests/test_pinned.py': 'a=1;b=2\n' + LONG_PYTHON,
    'application/src/pkg/attested.py': 'a=1;b=2\n' + LONG_PYTHON,
    'deployment/runtime.py': 'a=1;b=2\n',
    'application/tests/fixtures/captured.py': 'a=1;b=2\n' + LONG_PYTHON,
    **{path: 'generated\n' for path in ratchet.GENERATED},
    # A legacy file: unformatted, with one chained statement and one long line.
    'app/legacy.py': 'x=1\na = 1; b = 2\n' + LONG_PYTHON + 'y = 2\n',
    'app/clean.py': "value = 'clean'\n",
    'ui/src/legacy.ts': 'export const a = "double";\n' + LONG_SCRIPT,
    'ui/src/clean.ts': "export const clean = 'clean';\n",
}


class TreeTests(unittest.TestCase):
    """The committed tree passes the ratchet with exclusions read from their owners."""

    @classmethod
    def setUpClass(cls):
        cls.tool = ratchet.tools()

    def test_the_tree_passes_the_ratchet(self):
        self.assertEqual(ratchet.evaluate(REPO, self.tool), [])

    def test_the_tools_are_the_pinned_versions(self):
        ruff, prettier = ratchet.pinned_versions(REPO)
        project = REPO / 'pyproject.toml'
        self.assertIn('"ruff==' + ruff + '"', project.read_text())
        package = json.loads((REPO / 'ui/package.json').read_text())
        self.assertEqual(package['devDependencies']['prettier'], prettier)
        lock = json.loads((REPO / 'ui/package-lock.json').read_text())
        self.assertEqual(lock['packages']['node_modules/prettier']['version'], prettier)
        self.assertTrue(
            lock['packages']['node_modules/prettier']['integrity'].startswith('sha512-')
        )

    def test_the_attested_exclusion_equals_its_owners(self):
        tree = ast.parse((REPO / ratchet.ATTESTED_OWNER[0]).read_text())
        value = ratchet.assigned(tree, 'ATTESTED_PROJECT_FILES')
        attested = ast.literal_eval(value.args[0])
        launcher = ast.parse((REPO / ratchet.LAUNCHER_OWNER[0]).read_text())
        function = next(
            n for n in launcher.body if getattr(n, 'name', '') == 'execution_source_hashes'
        )
        literal = ast.literal_eval(ratchet.assigned(function, 'paths'))
        self.assertTrue(attested <= set(literal))
        self.assertEqual(ratchet.attested_files(REPO), set(literal) | attested)

    def test_the_hash_pinned_exclusion_equals_the_pin_tables(self):
        named = set()
        for module, table in KNOWN_PIN_TABLES:
            tree = ast.parse((REPO / module).read_text())
            named |= set(ast.literal_eval(ratchet.assigned(tree, table)))
        tracked = ratchet.tracked_files(REPO)
        self.assertTrue(named)
        self.assertEqual(ratchet.pinned_test_files(REPO, tracked), named)

    def test_every_exclusion_is_a_tracked_file(self):
        tracked = ratchet.tracked_files(REPO)
        excluded = ratchet.exclusions(REPO, tracked)
        self.assertEqual(sorted(set(excluded) - tracked), [])
        self.assertTrue(set(ratchet.GENERATED) <= set(excluded))
        covered = set(ratchet.covered_files(REPO, tracked))
        self.assertFalse(covered & set(excluded))

    def test_the_baseline_names_its_base_commit_and_only_covered_rules(self):
        baseline = ratchet.load_baseline(REPO)
        self.assertEqual(baseline['line_length'], 100)
        for path, rules in baseline['files'].items():
            self.assertTrue(ratchet.covered_suffix(path), path)
            self.assertTrue(set(rules) <= set(ratchet.RULES), path)
            self.assertTrue(all(type(n) is int and n > 0 for n in rules.values()), path)


class SeededTests(unittest.TestCase):
    """Each kind of new violation fails; unchanged, shrinking or excluded code passes."""

    @classmethod
    def setUpClass(cls):
        cls.tool = ratchet.tools()

    def setUp(self):
        scratch = tempfile.TemporaryDirectory(prefix='hyprn-mvp-style-')
        self.addCleanup(scratch.cleanup)
        self.repo = Path(scratch.name).resolve()
        for name in ('pyproject.toml', 'ui/.prettierrc.json', 'ui/package.json'):
            self.write(name, (REPO / name).read_text())
        for path, text in SEED.items():
            self.write(path, text)
        self.git('init', '-q')
        self.commit('seed')
        ratchet.create(self.repo, self.tool)
        self.commit('baseline')

    def write(self, relative, text):
        path = self.repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def append(self, relative, text):
        self.write(relative, (self.repo / relative).read_text() + text)

    def git(self, *args):
        return subprocess.run(
            [*GIT, '-C', str(self.repo), *args], capture_output=True, text=True, check=True
        ).stdout

    def commit(self, message):
        self.git('add', '-A')
        self.git('commit', '-q', '-m', message)

    def failures(self):
        return ratchet.evaluate(self.repo, self.tool)

    def assert_fails(self, *fragments):
        failures = self.failures()
        for fragment in fragments:
            self.assertTrue(any(fragment in f for f in failures), (fragment, failures))

    def test_the_seed_baseline_holds_the_legacy_violations(self):
        baseline = ratchet.load_baseline(self.repo)['files']
        self.assertEqual(baseline['app/legacy.py'], {'E501': 1, 'E702': 1})
        self.assertEqual(baseline['ui/src/legacy.ts'], {'long-line': 1})
        for excluded in (
            'application/src/pkg/attested.py',
            'contracts/tests/test_pinned.py',
            'application/tests/fixtures/captured.py',
        ):
            self.assertNotIn(excluded, baseline)
        self.assertEqual(self.failures(), [])

    def test_a_new_long_python_line_fails(self):
        self.append('app/clean.py', LONG_PYTHON)
        self.assert_fails('app/clean.py:2: E501 on a line changed', 'app/clean.py: E501 rose')

    def test_a_new_semicolon_chained_statement_fails(self):
        self.append('app/clean.py', 'a = 1; b = 2\n')
        self.assert_fails('app/clean.py:2: E702 on a line changed')

    def test_a_useless_trailing_semicolon_fails(self):
        self.append('app/clean.py', 'a = 1;\n')
        self.assert_fails('app/clean.py:2: E703 on a line changed')

    def test_a_noqa_comment_does_not_hide_a_new_violation(self):
        self.append('app/clean.py', 'a = 1; b = 2  # noqa: E702\n')
        self.assert_fails('app/clean.py:2: E702 on a line changed')

    def test_a_new_unformatted_python_file_fails(self):
        self.write('app/new.py', 'x=1\n')
        self.assertEqual(self.failures(), ['app/new.py: new file is not formatted'])

    def test_a_new_unformatted_typescript_file_fails(self):
        self.write('ui/src/new.ts', 'export const a = "double"\n')
        self.assertEqual(self.failures(), ['ui/src/new.ts: new file is not formatted'])

    def test_a_new_formatted_file_with_a_long_line_fails(self):
        self.write('app/new.py', LONG_PYTHON)
        self.assertEqual(self.failures(), ['app/new.py:1: E501 in a new file'])

    def test_a_new_long_typescript_line_in_an_existing_file_fails(self):
        self.append('ui/src/clean.ts', LONG_SCRIPT)
        self.assert_fails('ui/src/clean.ts:2: long-line on a line changed')

    def test_baselined_violations_left_unchanged_pass_without_reformatting(self):
        self.write('app/legacy.py', 'x=3\na = 1; b = 2\n' + LONG_PYTHON + 'y = 2\nz=4\n')
        self.append('ui/src/legacy.ts', 'export const b = "double";\n')
        self.assertEqual(self.failures(), [])

    def test_one_more_violation_in_a_baselined_file_fails(self):
        self.append('app/legacy.py', 'c = 3; d = 4\n')
        self.assert_fails('app/legacy.py: E702 rose from 1 to 2')

    def test_a_changed_line_keeping_a_baselined_violation_fails(self):
        text = (self.repo / 'app/legacy.py').read_text()
        self.write('app/legacy.py', text.replace("text = '", "text2 = '"))
        self.assert_fails('app/legacy.py:3: E501 on a line changed')
        self.assertFalse(any('rose' in f for f in self.failures()))

    def test_shrinking_violations_pass_and_update_lowers_the_baseline(self):
        self.write('app/legacy.py', 'x=1\na = 1\nb = 2\n' + LONG_PYTHON + 'y = 2\n')
        self.assertEqual(self.failures(), [])
        self.commit('split the chained statement')
        ratchet.update(self.repo, self.tool)
        baseline = ratchet.load_baseline(self.repo)
        self.assertEqual(baseline['files']['app/legacy.py'], {'E501': 1})
        self.assertEqual(baseline['base'], self.git('rev-parse', 'HEAD').strip())

    def test_update_never_raises_a_count(self):
        before = (self.repo / ratchet.BASELINE).read_text()
        self.append('app/legacy.py', 'c = 3; d = 4\n')
        self.commit('one more violation')
        with self.assertRaisesRegex(ratchet.StyleError, 'never raises'):
            ratchet.update(self.repo, self.tool)
        self.assertEqual((self.repo / ratchet.BASELINE).read_text(), before)

    def test_update_refuses_uncommitted_covered_changes(self):
        self.write('app/legacy.py', 'x=1\na = 1\nb = 2\n' + LONG_PYTHON + 'y = 2\n')
        with self.assertRaisesRegex(ratchet.StyleError, 'uncommitted'):
            ratchet.update(self.repo, self.tool)

    def test_create_refuses_an_existing_baseline(self):
        with self.assertRaisesRegex(ratchet.StyleError, 'baseline exists'):
            ratchet.create(self.repo, self.tool)

    def test_excluded_attested_and_hash_pinned_files_pass_unformatted(self):
        for path in (
            'application/src/pkg/attested.py',
            'deployment/runtime.py',
            'contracts/tests/test_pinned.py',
            'application/tests/fixtures/captured.py',
            'ui/src/contract.ts',
        ):
            self.append(path, 'c=3;d=4\n' + LONG_PYTHON)
        self.write('application/tests/fixtures/new.py', 'x=1;y=2\n')
        self.assertEqual(self.failures(), [])

    def test_a_table_of_type_names_is_not_a_pin_table(self):
        tracked = ratchet.tracked_files(self.repo)
        pinned = ratchet.pinned_test_files(self.repo, tracked)
        self.assertEqual(pinned, {'contracts/tests/test_pinned.py'})

    def test_a_missing_exclusion_owner_or_excluded_file_refuses(self):
        (self.repo / ratchet.ATTESTED_OWNER[0]).unlink()
        with self.assertRaisesRegex(ratchet.StyleError, 'exclusion owner missing'):
            self.failures()
        self.write(ratchet.ATTESTED_OWNER[0], SEED[ratchet.ATTESTED_OWNER[0]])
        (self.repo / 'ui/src/contract.ts').unlink()
        with self.assertRaisesRegex(ratchet.StyleError, 'excluded files missing'):
            self.failures()

    def test_a_missing_baseline_refuses(self):
        (self.repo / ratchet.BASELINE).unlink()
        with self.assertRaisesRegex(ratchet.StyleError, 'baseline missing'):
            self.failures()

    def test_a_base_commit_outside_the_history_refuses(self):
        path = self.repo / ratchet.BASELINE
        baseline = json.loads(path.read_text())
        path.write_text(json.dumps({**baseline, 'base': 'f' * 40}))
        with self.assertRaisesRegex(ratchet.StyleError, 'not an ancestor'):
            self.failures()

    def test_differing_line_limits_refuse(self):
        self.write('ui/.prettierrc.json', json.dumps({'printWidth': 80}))
        with self.assertRaisesRegex(ratchet.StyleError, 'differ'):
            self.failures()


class ToolTests(unittest.TestCase):
    """A missing or differently versioned tool refuses; it never skips a rule."""

    def test_missing_ruff_refuses(self):
        with tempfile.TemporaryDirectory(prefix='hyprn-mvp-style-') as empty:
            with patch.object(ratchet.sysconfig, 'get_path', return_value=empty):
                with self.assertRaisesRegex(ratchet.StyleError, 'ruff missing'):
                    ratchet.tools()

    def test_missing_node_refuses(self):
        with patch.object(ratchet.shutil, 'which', return_value=None):
            with self.assertRaisesRegex(ratchet.StyleError, 'node missing'):
                ratchet.tools()

    def test_missing_prettier_refuses(self):
        with tempfile.TemporaryDirectory(prefix='hyprn-mvp-style-') as scratch:
            root = Path(scratch)
            (root / 'ui').mkdir()
            for name in ('pyproject.toml', 'ui/package.json'):
                shutil.copyfile(REPO / name, root / name)
            with self.assertRaisesRegex(ratchet.StyleError, 'prettier missing'):
                ratchet.tools(root)

    def test_a_tool_version_other_than_its_pin_refuses(self):
        with patch.object(ratchet, 'pinned_versions', return_value=('0.0.0', '0.0.0')):
            with self.assertRaisesRegex(ratchet.StyleError, 'differ from their pins'):
                ratchet.tools()


if __name__ == '__main__':
    unittest.main()
