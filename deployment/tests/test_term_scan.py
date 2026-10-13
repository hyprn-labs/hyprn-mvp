"""The term scan reads only configured pattern files, scans tracked contents and paths, and
fails closed when it is not configured. Every repository and pattern file here is synthetic,
in a scratch folder that each test creates and releases."""
# Live-runtime fence (deployment/tests/live_fence.py): refuses live roots, live ports, docker, live entry points and real signals.
import sys as _fence_sys
from pathlib import Path as _FencePath
if str(_FencePath(__file__).resolve().parent) not in _fence_sys.path:
    _fence_sys.path.append(str(_FencePath(__file__).resolve().parent))
import live_fence  # noqa: E402
setUpModule, tearDownModule = live_fence.unittest_module_hooks('unit')
import os  # noqa: E402
from pathlib import Path  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import tempfile  # noqa: E402
import unittest  # noqa: E402

TOOL = Path(__file__).resolve().parents[1] / 'tools/term_scan.py'
VARIABLE = 'HYPRN_MVP_TERM_SCAN_FILES'


class TermScanTests(unittest.TestCase):
    def setUp(self):
        self.scratch = Path(tempfile.mkdtemp(prefix='term-scan-test-')).resolve()
        self.addCleanup(shutil.rmtree, self.scratch, True)
        self.repo = self.scratch / 'repo'
        self.repo.mkdir()
        self.git('init', '-q')
        self.patterns = self.scratch / 'patterns'
        self.patterns.mkdir()

    def git(self, *args):
        subprocess.run(['git', '-C', str(self.repo), *args], check=True, capture_output=True,
                       env={**self.environment(), 'GIT_CONFIG_NOSYSTEM': '1'})

    def environment(self, **extra):
        env = {k: v for k, v in os.environ.items() if k != VARIABLE}
        env.update(extra)
        return env

    def track(self, files):
        for relative, content in files.items():
            path = self.repo / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, bytes):
                path.write_bytes(content)
            else:
                path.write_text(content)
        self.git('add', '--', *files)

    def pattern_file(self, name, text):
        path = self.patterns / name
        path.write_text(text)
        return path

    def scan(self, *args, env=None):
        result = subprocess.run([sys.executable, '-B', str(TOOL), '--root', str(self.repo), *args],
                                capture_output=True, text=True, env=self.environment() if env is None else env,
                                timeout=120)
        return result.returncode, result.stdout, result.stderr

    def test_no_configured_pattern_file_exits_2(self):
        self.track({'a.txt': 'zebraquux\n'})
        status, stdout, stderr = self.scan()
        self.assertEqual(status, 2)
        self.assertEqual(stdout, '')
        self.assertIn(VARIABLE, stderr)
        status, _, _ = self.scan(env=self.environment(**{VARIABLE: ''}))
        self.assertEqual(status, 2)

    def test_unreadable_empty_or_invalid_pattern_files_exit_2(self):
        self.track({'a.txt': 'zebraquux\n'})
        good = self.pattern_file('good', 'zebraquux\n')
        missing = self.patterns / 'absent'
        status, _, stderr = self.scan('--patterns', str(good), '--patterns', str(missing))
        self.assertEqual(status, 2)
        self.assertNotIn(str(missing), stderr)
        comments = self.pattern_file('comments', '# a comment only\n\n   \n')
        self.assertEqual(self.scan('--patterns', str(comments))[0], 2)
        invalid = self.pattern_file('invalid', 'zebra(quux\n')
        self.assertEqual(self.scan('--patterns', str(invalid))[0], 2)
        self.assertEqual(self.scan('--patterns', str(good), '--root', str(self.scratch / 'not-a-repo'))[0], 2)

    def test_clean_tree_exits_0_with_zero_total(self):
        self.track({'a.txt': 'nothing to see\n', 'src/b.py': 'x = 1\n'})
        patterns = self.pattern_file('terms', '# synthetic terms\nzebraquux\n\n')
        self.assertEqual(self.scan('--patterns', str(patterns)), (0, 'total: 0\n', ''))

    def test_tracked_contents_and_paths_counted_case_insensitively_without_matched_text(self):
        self.track({'a.txt': 'one ZebraQuux\nzebraquux twice zebraquux\n',
                    'docs/zebraquux-notes.md': 'clean body\n',
                    'src/clean.py': 'value = 2\n'})
        (self.repo / 'untracked.txt').write_text('zebraquux\n')
        patterns = self.pattern_file('terms', 'zebraquux\n')
        status, stdout, _ = self.scan('--patterns', str(patterns))
        self.assertEqual(status, 1)
        self.assertEqual(stdout.splitlines(), ['a.txt:3', 'docs/zebraquux-notes.md:1', 'total: 4'])
        self.assertNotIn('ZebraQuux', stdout)
        status, shown, _ = self.scan('--patterns', str(patterns), '--show')
        self.assertEqual(status, 1)
        self.assertIn('  a.txt:1: ZebraQuux', shown.splitlines())
        self.assertIn('  docs/zebraquux-notes.md:path: zebraquux', shown.splitlines())

    def test_patterns_are_extended_expressions_joined_across_files_from_the_environment(self):
        self.track({'a.txt': 'alpha-123\n', 'b.txt': 'gamma\n', 'c.txt': 'alpha-x\n'})
        first = self.pattern_file('first', r'alpha-[0-9]+' + '\n')
        second = self.pattern_file('second', '# second file\n(gamma|delta)\n')
        env = self.environment(**{VARIABLE: os.pathsep.join((str(first), str(second)))})
        status, stdout, _ = self.scan(env=env)
        self.assertEqual(status, 1)
        self.assertEqual(stdout.splitlines(), ['a.txt:1', 'b.txt:1', 'total: 2'])
        # Explicit --patterns replace the environment list.
        status, stdout, _ = self.scan('--patterns', str(second), env=env)
        self.assertEqual(stdout.splitlines(), ['b.txt:1', 'total: 1'])

    def test_binary_contents_are_skipped_but_their_paths_are_scanned(self):
        self.track({'blob.bin': b'\x00zebraquux\x00', 'zebraquux.bin': b'\x00\x01'})
        patterns = self.pattern_file('terms', 'zebraquux\n')
        status, stdout, _ = self.scan('--patterns', str(patterns))
        self.assertEqual(status, 1)
        self.assertEqual(stdout.splitlines(), ['zebraquux.bin:1', 'total: 1'])


if __name__ == '__main__':
    unittest.main()
