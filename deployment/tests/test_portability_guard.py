"""Portability guard: operating-system folder layout lives only in the path policy.

- No tracked code outside the path policy names an operating system's folder layout (the
  per-OS default folders, synced folders, Windows-mounted drives). The path policy is the local
  edition's ``paths.py`` (per-OS defaults), the core location rule ``locations.py`` (refusals)
  and the ``./hyprn-mvp`` entry point (the tool-cache default and checkout refusals it needs
  before Python exists); the tests that exercise them are the only other files that may.
- No tracked file names an absolute path inside a user's home folder (the macOS or Linux
  folder of user homes followed by an account name, or a Windows drive's user folder): such
  prefixes are assembled at run time.

Every fragment below is assembled at run time so that this file never matches itself.
"""
# Live-runtime fence (deployment/tests/live_fence.py): refuses live roots, live ports, docker, live entry points and real signals.
import sys as _fence_sys
from pathlib import Path as _FencePath
if str(_FencePath(__file__).resolve().parent) not in _fence_sys.path:
    _fence_sys.path.append(str(_FencePath(__file__).resolve().parent))
import live_fence  # noqa: E402
live_runtime_fence = live_fence.pytest_fixture('unit')
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
POLICY = {
    'editions/local/src/hyprn_mvp_local/paths.py': 'per-OS default folders',
    'application/src/hyprn_mvp_app/locations.py': 'the location rule: synced folders and Windows-mounted drives',
    'hyprn-mvp': 'tool-cache default and checkout refusals before Python exists',
}
POLICY_TESTS = {
    'editions/local/tests/test_shim.py': 'entry point tool-cache default and synced checkouts',
    'editions/local/tests/test_paths.py': 'per-OS defaults and refusals of the path policy',
    'deployment/tests/test_installation_config.py': 'synced and Windows-mounted data roots in the loader',
    'application/tests/test_store_location.py': 'synced and Windows-mounted store locations',
}
# Code and configuration; prose documentation describes the defaults for people.
CODE_SUFFIXES = {'.py', '.sh', '.ts', '.tsx', '.js', '.mjs', '.cjs', '.json', '.yaml', '.yml', '.toml', '.rb', '.html',
                 '.css', '.txt', '.cfg', '.ini'}
CODE_NAMES = {'Dockerfile', 'hyprn-mvp'}
LAYOUT = [
    'Application' + ' Support', 'Library' + '/Caches', "'Library'" + ', ', 'Cloud' + 'Storage', 'Mobile' + ' Documents',
    '.local' + '/share', "'.local'" + ', ', '.config' + '/hyprn-mvp', '.cache' + '/hyprn-mvp', 'App' + 'Data',
    '/' + 'mnt/',
]
HOME_PATH = re.compile(r'(?<![A-Za-z0-9_.~-])/(?:' + 'Users' + '|' + 'home' + r')/[A-Za-z0-9_][A-Za-z0-9._-]*'
                       r'|[A-Za-z]:\\\\?' + 'Users' + r'\\\\?[A-Za-z0-9_]')


def tracked():
    result = subprocess.run(['git', 'ls-files', '-z'], cwd=REPO, capture_output=True, check=True)
    files = [name for name in result.stdout.decode().split('\0') if name]
    assert 'deployment/checks.py' in files
    return files


def is_code(name):
    path = Path(name)
    return (path.suffix in CODE_SUFFIXES or path.name in CODE_NAMES or path.name.endswith('.Dockerfile')) \
        and not path.name.endswith('-lock.json')


def text(name):
    try:
        return (REPO / name).read_text(encoding='utf-8')
    except (UnicodeDecodeError, IsADirectoryError):
        return None


def test_the_policy_and_its_tests_exist():
    files = set(tracked())
    for name in (*POLICY, *POLICY_TESTS):
        assert name in files or (REPO / name).is_file(), name


def test_no_folder_layout_outside_the_path_policy():
    found = []
    for name in tracked():
        if name in POLICY or name in POLICY_TESTS or not is_code(name):
            continue
        content = text(name)
        if content is None:
            continue
        for number, line in enumerate(content.splitlines(), 1):
            for fragment in LAYOUT:
                if fragment in line:
                    found.append(f'{name}:{number}: {fragment}')
    assert found == [], found


def test_the_policy_files_hold_the_layout_they_own():
    """The allowlist is not stale: each policy file names folder layout."""
    for name in POLICY:
        content = text(name)
        assert any(fragment in content for fragment in LAYOUT), name


def test_no_absolute_home_path_in_any_tracked_file():
    found = []
    for name in tracked():
        content = text(name)
        if content is None:
            continue
        for number, line in enumerate(content.splitlines(), 1):
            if HOME_PATH.search(line):
                found.append(f'{name}:{number}')
    assert found == [], found


def test_the_scanners_find_what_they_guard():
    assert HOME_PATH.search('see /' + 'Users/someone/data')
    assert HOME_PATH.search('"/' + 'home/someone"')
    assert HOME_PATH.search('C:\\' + 'Users\\someone')
    assert not HOME_PATH.search("'/' + '" + 'home/' + "'")
    assert not HOME_PATH.search('~/' + 'Library')
    sample = 'root = home / ' + "'Library'" + ', ' + "'Caches'"
    assert any(fragment in sample for fragment in LAYOUT)
    assert is_code('deployment/images/engine.Dockerfile') and is_code('hyprn-mvp')
    assert not is_code('docs/operations/install.md') and not is_code('ui/package-lock.json')
