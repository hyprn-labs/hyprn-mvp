"""The ./hyprn-mvp entry point, its pins and the locked development environments.

Standard library only; run with the locked contract interpreter:

    <contract environment>/bin/python -I -B -m unittest discover -s editions/local/tests -p test_shim.py

No test touches the real tool cache or the network: every entry-point run uses a scratch copy
of the checkout's entry files, a scratch home and tool cache, stub programs (curl, uname,
sysctl, ldd and every python name) and a crafted uv archive, and is released afterwards.
"""
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[3]
ENTRY = REPO / 'hyprn-mvp'
TOOLS_JSON = REPO / 'deployment/locks/tools.json'
PINS = json.loads(TOOLS_JSON.read_text())
AUDIT = REPO / 'docs/operations/dependency-audit.md'
SUPPORTED = {'darwin-arm64': ('Darwin', 'arm64'), 'linux-x86_64': ('Linux', 'x86_64'),
             'linux-aarch64': ('Linux', 'aarch64')}
SYSTEM_PATH = '/usr/bin:/bin'
STUBS = {
    'curl': """#!/bin/sh
printf 'curl %s\\n' "$*" >> "$STUB_LOG"
[ -z "${STUB_CURL_FAIL:-}" ] || exit 22
out=
while [ $# -gt 0 ]; do
    if [ "$1" = -o ]; then out=$2; shift; fi
    shift
done
cat "$STUB_ARCHIVE" > "$out"
""",
    'uname': """#!/bin/sh
case "${1:-}" in -m) echo "$STUB_ARCH" ;; *) echo "$STUB_OS" ;; esac
""",
    'sysctl': """#!/bin/sh
echo "${STUB_ARM64:-0}"
""",
    'ldd': """#!/bin/sh
if [ "${STUB_LIBC:-glibc}" = musl ]; then echo 'musl libc (aarch64)'; else echo 'ldd (GNU libc) 2.36'; fi
""",
    'sha256sum': """#!/bin/sh
exec shasum -a 256 "$@"
""",
    **{name: """#!/bin/sh
printf 'system-python %s\\n' "$*" >> "$STUB_LOG"
exit 97
""" for name in ('python', 'python3', 'python3.12')},
}
# The crafted uv records every call and its uv settings; `sync` places a stub interpreter in
# the locked environment that records how it is run.
FAKE_UV = """#!/bin/sh
printf 'uv %s\\n' "$*" >> "$STUB_LOG"
env | sed -n 's/^\\(UV_[A-Z_]*=.*\\)$/uv-env \\1/p; s/^\\(VIRTUAL_ENV=.*\\)$/uv-env \\1/p; s/^\\(PYTHONPATH=.*\\)$/uv-env \\1/p' | sort >> "$STUB_LOG"
case "$1" in
    --version) echo 'uv 0.12.24 (crafted)' ;;
    sync)
        mkdir -p "$UV_PROJECT_ENVIRONMENT/bin"
        printf '#!/bin/sh\\nprintf "env-python %%s\\\\n" "$*" >> "$STUB_LOG"\\n' > "$UV_PROJECT_ENVIRONMENT/bin/python"
        chmod 700 "$UV_PROJECT_ENVIRONMENT/bin/python"
        ;;
esac
"""


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def normalized(name):
    return re.sub(r'[-_.]+', '-', name).lower()


def crafted_archive(platform):
    """A gzip tar laid out like the uv release archive of ``platform``, holding FAKE_UV."""
    top = PINS['uv_archives'][platform]['archive'].removesuffix('.tar.gz')
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w:gz') as archive:
        for name in ('uv', 'uvx'):
            data = FAKE_UV.encode()
            info = tarfile.TarInfo(top + '/' + name)
            info.size, info.mode = len(data), 0o755
            archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


class Sandbox:
    """A scratch checkout copy, home, tool cache and stub programs for one entry-point run."""

    def __init__(self, root, checkout=None):
        self.root = Path(os.path.realpath(root))
        self.home = self.root / 'home'
        self.tools = self.root / 'tools'
        self.bin = self.root / 'bin'
        self.log = self.root / 'calls.log'
        self.archive = self.root / 'archive.tar.gz'
        self.checkout = Path(checkout) if checkout else self.root / 'checkout'
        for folder in (self.home, self.bin, self.checkout / 'deployment/locks'):
            folder.mkdir(parents=True, exist_ok=True)
        for relative in ('hyprn-mvp', 'deployment/locks/tools.json', 'uv.lock', '.python-version'):
            shutil.copy2(REPO / relative, self.checkout / relative)
        for name, text in STUBS.items():
            (self.bin / name).write_text(text)
            (self.bin / name).chmod(0o700)
        self.archive.write_bytes(b'not the pinned archive')
        self.log.write_text('')

    def pin_crafted_archive(self, platform, *, size=None):
        """Replace the platform's uv pin in the scratch copy by the crafted archive's digest."""
        raw = crafted_archive(platform)
        self.archive.write_bytes(raw)
        pin = PINS['uv_archives'][platform]
        path = self.checkout / 'deployment/locks/tools.json'
        text = path.read_text()
        old = f'"size": {pin["size"]}, "sha256": "{pin["sha256"]}"'
        new = f'"size": {len(raw) if size is None else size}, "sha256": "{sha256(raw)}"'
        assert text.count(old) == 1
        path.write_text(text.replace(old, new))
        return raw

    def run(self, *args, platform='darwin-arm64', machine=None, env=None, tools=True):
        system, arch = SUPPORTED.get(platform, (None, None)) if machine is None else machine
        environment = {'PATH': str(self.bin) + ':' + SYSTEM_PATH, 'HOME': str(self.home), 'STUB_LOG': str(self.log),
                       'STUB_ARCHIVE': str(self.archive), 'STUB_OS': system, 'STUB_ARCH': arch}
        if tools:
            environment['HYPRN_MVP_TOOLS_DIR'] = str(self.tools)
        environment.update(env or {})
        return subprocess.run([str(self.checkout / 'hyprn-mvp'), *args], env=environment, capture_output=True,
                              text=True, timeout=60)

    def calls(self, prefix):
        return [line[len(prefix) + 1:] for line in self.log.read_text().splitlines() if line.startswith(prefix + ' ')]

    def uv_runs(self):
        """Every uv call as (arguments, the uv and interpreter settings it saw)."""
        runs = []
        for line in self.log.read_text().splitlines():
            if line.startswith('uv '):
                runs.append((line[3:], {}))
            elif line.startswith('uv-env '):
                name, _, value = line[7:].partition('=')
                runs[-1][1][name] = value
        return runs

    def uv_settings(self):
        """The uv settings seen by the first uv call."""
        return self.uv_runs()[0][1]


class EntryPointTest(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix='hyprn-mvp-shim-')
        self.addCleanup(self.scratch.cleanup)
        self.box = Sandbox(self.scratch.name)

    def assert_no_python_started(self, box=None):
        box = box or self.box
        self.assertEqual(box.calls('system-python'), [])
        self.assertEqual(box.calls('env-python'), [])

    def assert_nothing_installed(self, box=None):
        box = box or self.box
        uv_root = box.tools / 'uv'
        leftovers = sorted(str(p.relative_to(box.tools)) for p in uv_root.rglob('*')) if uv_root.exists() else []
        self.assertEqual([p for p in leftovers if p != 'uv/' + PINS['uv_version']], [])


class AcquisitionTests(EntryPointTest):
    def test_each_platform_downloads_its_pinned_archive_over_https_and_refuses_other_bytes(self):
        for platform, pin in PINS['uv_archives'].items():
            with self.subTest(platform=platform):
                self.box.log.write_text('')
                result = self.box.run('version', platform=platform)
                self.assertEqual(result.returncode, 5, result.stderr)
                self.assertIn('checksum mismatch for ' + pin['archive'] + ': expected ' + pin['sha256'], result.stderr)
                (call,) = self.box.calls('curl')
                options, url = call.split()[:5], call.split()[-1]
                self.assertEqual(options[:3], ['--proto', '=https', '--tlsv1.2'])
                self.assertEqual(options[3:], ['-fsSL', '-o'])
                self.assertEqual(url, PINS['uv_download_base'] + pin['archive'])
                self.assertTrue(url.startswith('https://github.com/astral-sh/uv/releases/download/'))
                self.assertEqual(self.box.calls('uv'), [])
                self.assert_no_python_started()
                self.assert_nothing_installed()

    def test_an_archive_of_the_pinned_digest_but_another_size_is_refused(self):
        raw = self.box.pin_crafted_archive('darwin-arm64', size=PINS['uv_archives']['darwin-arm64']['size'])
        result = self.box.run('version')
        self.assertEqual(result.returncode, 5, result.stderr)
        self.assertIn('size mismatch', result.stderr)
        self.assertIn('got ' + str(len(raw)) + ';', result.stderr)
        self.assertEqual(self.box.calls('uv'), [])
        self.assert_no_python_started()
        self.assert_nothing_installed()

    def test_a_failed_download_is_refused_without_installing_anything(self):
        result = self.box.run('version', env={'STUB_CURL_FAIL': '1'})
        self.assertEqual(result.returncode, 5)
        self.assertIn('network access to github.com is needed on first use', result.stderr)
        self.assert_no_python_started()
        self.assert_nothing_installed()

    def test_a_verified_archive_runs_the_cli_in_the_locked_contract_environment_with_hermetic_uv_settings(self):
        self.box.pin_crafted_archive('darwin-arm64')
        ambient = {'UV_INDEX_URL': 'https://index.invalid/simple', 'UV_PYTHON': 'python3', 'UV_NO_CONFIG': '0',
                   'UV_PYTHON_DOWNLOADS_JSON_URL': 'https://index.invalid/metadata.json', 'UV_SYSTEM_CERTS': 'true',
                   'VIRTUAL_ENV': str(self.box.root / 'venv'), 'PYTHONPATH': str(self.box.root)}
        result = self.box.run('--json', 'version', env=ambient)
        self.assertEqual(result.returncode, 0, result.stderr)
        lock16 = sha256((REPO / 'uv.lock').read_bytes())[:16]
        environment = self.box.tools / 'envs' / ('contract-' + lock16)
        root = str(self.box.checkout)
        self.assertEqual(self.box.calls('uv'), [
            '--version',
            'python install --quiet --no-bin ' + PINS['cpython_version'],
            'sync --quiet --project ' + root + ' --frozen --no-build --exact --no-install-project --no-default-groups '
            '--group contract --no-python-downloads --python ' + PINS['cpython_version']])
        hermetic = {
            'UV_CACHE_DIR': str(self.box.tools / 'uv-cache'), 'UV_NO_CONFIG': '1', 'UV_NO_PROGRESS': '1',
            'UV_PYTHON_BIN_DIR': str(self.box.tools / 'python-bin'),
            'UV_PYTHON_INSTALL_DIR': str(self.box.tools / 'python'),
            'UV_PYTHON_INSTALL_MIRROR': PINS['cpython_install_mirror'], 'UV_PYTHON_PREFERENCE': 'only-managed',
            'UV_SYSTEM_CERTS': 'true'}
        # Every uv run, including the version check, sees only the hermetic settings.
        self.assertEqual([settings for _, settings in self.box.uv_runs()],
                         [hermetic, hermetic, {**hermetic, 'UV_PROJECT_ENVIRONMENT': str(environment)}])
        (run,) = self.box.calls('env-python')
        self.assertTrue(run.startswith('-I -B -c import runpy, sys;'), run)
        self.assertTrue(run.endswith(' ' + root + '/editions/local/src --json version'), run)
        self.assertEqual(self.box.calls('system-python'), [])
        self.assertTrue((self.box.tools / 'uv' / PINS['uv_version'] / 'darwin-arm64' / 'uv').is_file())
        self.assertEqual(sorted(p.name for p in (self.box.tools / 'uv').iterdir()), [PINS['uv_version']])
        # The verified uv is reused without another download.
        self.box.log.write_text('')
        self.assertEqual(self.box.run('version').returncode, 0)
        self.assertEqual(self.box.calls('curl'), [])
        self.assertEqual(self.box.calls('uv')[0], '--version')

    def test_a_cached_uv_of_another_version_is_refused(self):
        self.box.pin_crafted_archive('darwin-arm64')
        self.assertEqual(self.box.run('version').returncode, 0)
        uv = self.box.tools / 'uv' / PINS['uv_version'] / 'darwin-arm64' / 'uv'
        uv.write_text(uv.read_text().replace("echo 'uv 0.12.24 (crafted)'", "echo 'uv 0.13.0'"))
        self.box.log.write_text('')
        result = self.box.run('version')
        self.assertEqual(result.returncode, 5)
        self.assertIn('is not uv ' + PINS['uv_version'], result.stderr)
        self.assert_no_python_started()


class HostTests(EntryPointTest):
    def test_macos_on_intel_is_refused_with_its_reason(self):
        result = self.box.run('version', machine=('Darwin', 'x86_64'), env={'STUB_ARM64': '0'})
        self.assertEqual(result.returncode, 3)
        self.assertIn('macOS on Intel (x86_64) is not supported', result.stderr)
        self.assertIn('Supported hosts', result.stderr)
        self.assertEqual(self.box.calls('curl'), [])
        self.assert_no_python_started()

    def test_a_translated_shell_on_apple_silicon_uses_the_arm64_pin(self):
        result = self.box.run('version', machine=('Darwin', 'x86_64'), env={'STUB_ARM64': '1'})
        self.assertEqual(result.returncode, 5)
        self.assertEqual(self.box.calls('curl')[0].split()[-1],
                         PINS['uv_download_base'] + PINS['uv_archives']['darwin-arm64']['archive'])

    def test_unsupported_systems_and_musl_are_refused_before_any_download(self):
        for machine, env in ((('Linux', 'armv7l'), {}), (('FreeBSD', 'amd64'), {}),
                             (('Linux', 'x86_64'), {'STUB_LIBC': 'musl'})):
            with self.subTest(machine=machine, env=env):
                self.box.log.write_text('')
                result = self.box.run('version', machine=machine, env=env)
                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertEqual(self.box.calls('curl'), [])
                self.assert_no_python_started()


class LocationTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix='hyprn-mvp-shim-')
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(os.path.realpath(self.scratch.name))

    def test_a_checkout_in_a_synced_folder_is_refused_before_any_download(self):
        home = self.root / 'home'
        cases = [('darwin-arm64', home / 'Library' / 'CloudStorage' / 'OneDrive-Personal'),
                 ('darwin-arm64', home / 'Library' / 'Mobile Documents' / 'com~apple~CloudDocs'),
                 ('darwin-arm64', home / 'Desktop'), ('darwin-arm64', home / 'Documents' / 'code'),
                 ('linux-x86_64', home / 'Dropbox' / 'code'), ('linux-x86_64', home / 'OneDrive'),
                 ('linux-aarch64', home / 'Google Drive' / 'My Drive')]
        for index, (platform, folder) in enumerate(cases):
            with self.subTest(folder=str(folder.relative_to(home))):
                box = Sandbox(self.root / str(index), checkout=folder / ('checkout-' + str(index)))
                box.home = home
                result = box.run('version', platform=platform)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn('refusing the checkout', result.stderr)
                self.assertEqual(box.calls('curl'), [])
                self.assertFalse(box.tools.exists())
                self.assertEqual(box.calls('system-python'), [])

    def test_a_checkout_in_an_ordinary_folder_is_not_refused(self):
        box = Sandbox(self.root / 'plain', checkout=self.root / 'home' / 'code' / 'hyprn-mvp')
        box.home = self.root / 'home'
        result = box.run('version', platform='darwin-arm64')
        self.assertNotIn('refusing the checkout', result.stderr)
        self.assertEqual(len(box.calls('curl')), 1)

    def test_a_relative_synced_or_checkout_tool_cache_is_refused(self):
        box = Sandbox(self.root / 'box')
        for value, message in (('relative/tools', 'must be an absolute path'),
                               (str(self.root / 'a' / '..' / 'tools'), 'normalized'),
                               (str(box.checkout / 'tools'), 'inside the checkout'),
                               (str(box.home / 'Dropbox' / 'tools'), 'refusing the tool cache')):
            with self.subTest(value=value):
                box.log.write_text('')
                result = box.run('version', env={'HYPRN_MVP_TOOLS_DIR': value})
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn(message, result.stderr)
                self.assertEqual(box.calls('curl'), [])

    def test_the_tool_cache_default_is_the_per_os_location_of_the_location_table(self):
        home = self.root / 'home'
        xdg = self.root / 'xdg-cache'
        # The location table: macOS ~/Library/Caches/hyprn-mvp/tools; Linux and WSL2
        # ${XDG_CACHE_HOME:-~/.cache}/hyprn-mvp/tools (a relative XDG_CACHE_HOME is ignored).
        cases = (('darwin-arm64', {}, home / 'Library' / 'Caches' / 'hyprn-mvp' / 'tools'),
                 ('darwin-arm64', {'XDG_CACHE_HOME': str(xdg)}, home / 'Library' / 'Caches' / 'hyprn-mvp' / 'tools'),
                 ('linux-x86_64', {}, home / '.cache' / 'hyprn-mvp' / 'tools'),
                 ('linux-aarch64', {'XDG_CACHE_HOME': str(xdg)}, xdg / 'hyprn-mvp' / 'tools'),
                 ('linux-x86_64', {'XDG_CACHE_HOME': 'relative'}, home / '.cache' / 'hyprn-mvp' / 'tools'))
        for index, (platform, env, expected) in enumerate(cases):
            with self.subTest(platform=platform, env=env):
                box = Sandbox(self.root / str(index))
                box.home = home
                box.pin_crafted_archive(platform)
                result = box.run('version', platform=platform, env=env, tools=False)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(box.uv_settings()['UV_PYTHON_INSTALL_DIR'], str(expected / 'python'))
                self.assertTrue((expected / 'uv' / PINS['uv_version'] / platform / 'uv').is_file())
                shutil.rmtree(expected)

    def test_the_locked_environment_named_by_the_entry_point_is_the_runner_s(self):
        box = Sandbox(self.root / 'box')
        box.pin_crafted_archive('darwin-arm64')
        self.assertEqual(box.run('version').returncode, 0)
        named = [line.split('=', 1)[1] for line in box.calls('uv-env') if line.startswith('UV_PROJECT_ENVIRONMENT=')]
        sys.path.insert(0, str(REPO / 'deployment'))
        self.addCleanup(sys.path.remove, str(REPO / 'deployment'))
        import local_paths
        with patch.dict(os.environ, {local_paths.TOOLS_DIR: str(box.tools)}):
            self.assertEqual(named, [str(local_paths.locked_environment('contract'))])
            self.assertEqual(local_paths.locked_python('native'),
                             box.tools / 'envs' / ('native-' + named[0].rsplit('-', 1)[1]) / 'bin/python')
        with patch.dict(os.environ, {local_paths.TOOLS_DIR: ''}):
            self.assertIsNone(local_paths.locked_python('native', required=False))
            with self.assertRaisesRegex(local_paths.LocationUnset, local_paths.TOOLS_DIR):
                local_paths.locked_python('native')


class EntryPointSourceTests(unittest.TestCase):
    def test_the_entry_point_executes_no_python_but_the_locked_environment_s(self):
        text = ENTRY.read_text()
        code = '\n'.join(line for line in text.splitlines() if not line.lstrip().startswith('#'))
        self.assertTrue(text.startswith('#!/bin/sh\n'))
        self.assertTrue(os.access(ENTRY, os.X_OK))
        self.assertEqual(re.findall(r'\bexec\b[^\n]*', code), ['exec "$ENVIRONMENT/bin/python" -I -B -c \\'])
        for word in ('python3', 'python2', 'PYTHON=', 'command -v python', 'which python', '/usr/bin/env python'):
            self.assertNotIn(word, code)
        self.assertNotIn('--seed', code)
        self.assertIn('set -eu', code)

    def test_the_entry_point_names_no_absolute_folder_of_any_host(self):
        code = '\n'.join(line for line in ENTRY.read_text().splitlines() if not line.lstrip().startswith('#'))
        for fragment in ('/' + 'Users/', '/' + 'home/', '/' + 'private/', '/' + 'opt/', '/' + 'tmp/'):
            self.assertNotIn(fragment, code)


class PinTests(unittest.TestCase):
    def test_python_version_file_project_and_tool_pins_agree(self):
        version = PINS['cpython_version']
        self.assertEqual((REPO / '.python-version').read_text(), version + '\n')
        project = tomllib.loads((REPO / 'pyproject.toml').read_text())
        self.assertEqual(project['project']['requires-python'], '==' + version)
        self.assertEqual(tomllib.loads((REPO / 'editions/local/pyproject.toml').read_text())['project']['requires-python'],
                         '==' + version)
        self.assertEqual(tomllib.loads((REPO / 'uv.lock').read_text())['requires-python'], '==' + version)

    def test_tool_pins_are_the_approved_audit_values(self):
        audit = AUDIT.read_text()
        self.assertEqual(set(PINS['uv_archives']), set(SUPPORTED))
        self.assertEqual(set(PINS['cpython_archives']), set(SUPPORTED))
        self.assertEqual(set(PINS['refused_platforms']), {'darwin-x86_64'})
        self.assertIn('**uv ' + PINS['uv_version'] + '**', audit)
        self.assertIn('**`' + PINS['cpython_build'] + '`**', audit)
        for kind in ('uv_archives', 'cpython_archives'):
            for platform, pin in PINS[kind].items():
                with self.subTest(kind=kind, platform=platform):
                    row = next(line for line in audit.splitlines() if '`' + pin['archive'] + '`' in line)
                    self.assertIn(f'{pin["size"]:,}', row)
                    self.assertIn('`' + pin['sha256'] + '`', row)
        self.assertTrue(PINS['uv_download_base'].startswith('https://github.com/astral-sh/uv/releases/download/'
                                                            + PINS['uv_version'] + '/'))
        self.assertEqual(PINS['cpython_install_mirror'],
                         'https://github.com/astral-sh/python-build-standalone/releases/download')


def audited_set(key):
    """{name: version} of the audit's "All pinned Python distributions" rows of one set key."""
    audit = AUDIT.read_text()
    section = audit[audit.index('### All pinned Python distributions'):audit.index('## 6.')]
    rows = {}
    for line in section.splitlines():
        cells = [cell.strip() for cell in line.strip().strip('|').split('|')]
        if len(cells) == 4 and re.fullmatch(r'[0-9][0-9A-Za-z.]*', cells[1]) and key in cells[2].replace(' ', '').split(','):
            rows[normalized(cells[0])] = cells[1]
    return rows


def requirements(path):
    pins = {}
    for line in (REPO / path).read_text().splitlines():
        if line.strip():
            name, version = line.split()[0].split('==')
            pins[normalized(name)] = (version, {h.removeprefix('--hash=sha256:') for h in line.split()[1:]})
    return pins


class LockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lock = tomllib.loads((REPO / 'uv.lock').read_text())
        project = tomllib.loads((REPO / 'pyproject.toml').read_text())
        cls.groups = {}
        for group, entries in project['dependency-groups'].items():
            pins = [entry.split('==') for entry in entries]
            cls.groups[group] = {normalized(name): version for name, version in pins}
            assert len(cls.groups[group]) == len(entries)
        cls.packages = [p for p in cls.lock['package'] if not p['source'].get('virtual')]

    def test_the_groups_are_the_reviewed_sets(self):
        self.assertEqual(set(self.groups), {'contract', 'native'})
        application = {name: version for name, (version, _) in requirements('application/requirements.lock').items()}
        self.assertEqual(self.groups['contract'], application)
        self.assertEqual(self.groups['contract'], audited_set('A'))
        self.assertEqual(self.groups['native'], audited_set('N'))
        # The approved change: pytest 9.0.2 -> 9.1.1 in the integration test lock, now contained in both.
        tests = {name: version for name, (version, _) in requirements('integration/test-requirements.lock').items()}
        self.assertEqual(tests['pytest'], '9.1.1')
        for group in ('contract', 'native'):
            self.assertEqual({n: self.groups[group].get(n) for n in tests}, tests)

    def test_the_lock_holds_exactly_the_reviewed_versions(self):
        locked = sorted((p['name'], p['version']) for p in self.packages)
        reviewed = sorted({*self.groups['contract'].items(), *self.groups['native'].items()})
        self.assertEqual(locked, reviewed)
        self.assertEqual([p['name'] for p in self.lock['package'] if p['source'].get('virtual')], ['hyprn-mvp'])
        self.assertEqual({json.dumps(p['source']) for p in self.packages}, {'{"registry": "https://pypi.org/simple"}'})
        self.assertEqual(self.lock['conflicts'], [[{'package': 'hyprn-mvp', 'group': 'contract'},
                                                   {'package': 'hyprn-mvp', 'group': 'native'}]])
        for worker_only in ('openmdao', 'openmdao-extensions', 'wop', 'xdsmjs', 'pip', 'setuptools'):
            self.assertNotIn(worker_only, {p['name'] for p in self.packages})

    def test_every_locked_distribution_has_a_hashed_wheel_for_each_supported_host(self):
        hosts = {'darwin-arm64': ('macosx', 'arm64'), 'linux-x86_64': ('manylinux', 'x86_64'),
                 'linux-aarch64': ('manylinux', 'aarch64')}
        for package in self.packages:
            wheels = package.get('wheels', [])
            self.assertTrue(wheels, package['name'])
            self.assertTrue(all(re.fullmatch(r'sha256:[0-9a-f]{64}', w['hash']) for w in wheels), package['name'])
            tags = [w['url'].rsplit('/', 1)[1].removesuffix('.whl').rsplit('-', 1)[1] for w in wheels]
            for host, (system, machine) in hosts.items():
                with self.subTest(package=package['name'], version=package['version'], host=host):
                    self.assertTrue(any(tag == 'any' or (system in tag and (machine in tag or 'universal2' in tag))
                                        for tag in tags))

    def test_the_lock_keeps_every_reviewed_artifact_hash(self):
        locked = {(p['name'], p['version']): {w['hash'].removeprefix('sha256:') for w in p.get('wheels', [])}
                  for p in self.packages}
        for path in ('application/requirements.lock', 'integration/test-requirements.lock'):
            for name, (version, hashes) in requirements(path).items():
                with self.subTest(path=path, name=name):
                    self.assertLessEqual(hashes, locked[(name, version)])


def toolchain_module(test):
    test.addCleanup(sys.path.remove, str(REPO / 'editions/local/src'))
    sys.path.insert(0, str(REPO / 'editions/local/src'))
    from hyprn_mvp_local import toolchain
    return toolchain


class LockedEnvironmentVerificationTests(unittest.TestCase):
    """A locked environment is used only when it holds exactly its reviewed distributions."""

    def setUp(self):
        self.toolchain = toolchain_module(self)
        scratch = tempfile.TemporaryDirectory(prefix='hyprn-mvp-shim-')
        self.addCleanup(scratch.cleanup)
        self.interpreter = Path(scratch.name) / 'python'

    def verify(self, group, distributions):
        listing = json.dumps(sorted([name, version] for name, version in distributions.items()))
        self.interpreter.write_text("#!/bin/sh\ncat <<'EOF'\n" + listing + '\nEOF\n')
        self.interpreter.chmod(0o700)
        with patch.object(self.toolchain, 'python', lambda _: self.interpreter), \
                patch.object(self.toolchain, 'environment', lambda g: self.interpreter.parent / g):
            return self.toolchain.verify(group)

    def test_exactly_the_reviewed_group_is_accepted(self):
        self.assertEqual(self.verify('contract', self.toolchain.reviewed('contract')), self.interpreter)
        self.assertEqual(self.verify('native', self.toolchain.expected('native')), self.interpreter)

    def test_an_extra_missing_or_different_distribution_is_refused(self):
        contract = self.toolchain.reviewed('contract')
        native = self.toolchain.expected('native')
        for group, distributions, word in (
                ('contract', {**contract, 'pip': '25.1.1'}, 'pip==25.1.1'),
                ('contract', {**contract, 'pytest': '9.0.2'}, 'pytest==9.0.2'),
                ('contract', {k: v for k, v in contract.items() if k != 'click'}, 'click==8.5.0'),
                ('native', self.toolchain.reviewed('native'), 'hyprn-mvp-integration==0.1.0'),
                ('native', {**native, 'setuptools': '84.0.0'}, 'setuptools==84.0.0')):
            with self.subTest(group=group, word=word), self.assertRaisesRegex(self.toolchain.ToolchainError, word):
                self.verify(group, distributions)

    def test_the_cli_refuses_macos_on_intel_and_unknown_hosts(self):
        self.assertEqual(self.toolchain.platform_key('Darwin', 'arm64'), 'darwin-arm64')
        self.assertEqual(self.toolchain.platform_key('Linux', 'arm64'), 'linux-aarch64')
        for system, machine, message in (('Darwin', 'x86_64', 'macOS on Intel'), ('Linux', 'riscv64', 'unsupported host')):
            with self.subTest(machine=machine), self.assertRaisesRegex(self.toolchain.ToolchainError, message) as refused:
                self.toolchain.platform_key(system, machine)
            self.assertEqual(refused.exception.code, 3)


class DevCheckArgumentTests(unittest.TestCase):
    """dev check hands the runner exactly the requested command; --jobs belongs to the gate only."""

    def setUp(self):
        self.toolchain = toolchain_module(self)
        from hyprn_mvp_local import cli
        self.cli = cli
        from types import SimpleNamespace
        paths = SimpleNamespace(NATIVE_PYTHON='HYPRN_MVP_NATIVE_PYTHON', CONTRACT_PYTHON='HYPRN_MVP_CONTRACT_PYTHON')
        for target, name, value in ((self.toolchain, 'provision', Path('native-python')),
                                    (self.toolchain, 'local_paths', paths)):
            patcher = patch.object(target, name, return_value=value)
            setattr(self, name, patcher.start())
            self.addCleanup(patcher.stop)
        for name in ('chdir', 'execve'):
            patcher = patch.object(cli.os, name)
            setattr(self, name, patcher.start())
            self.addCleanup(patcher.stop)

    def runner_arguments(self, *argv):
        self.cli.main(['dev', 'check', *argv])
        arguments = self.execve.call_args.args[1]
        return arguments[arguments.index(str(self.toolchain.REPO / 'deployment/checks.py')) + 1:]

    def test_the_gate_receives_jobs_only_when_given(self):
        self.assertEqual(self.runner_arguments('qualification', '--jobs', '4'), ['--group', 'qualification', '--jobs', '4'])
        self.assertEqual(self.runner_arguments('qualification', '--jobs', '1'), ['--group', 'qualification', '--jobs', '1'])
        self.assertEqual(self.runner_arguments('qualification'), ['--group', 'qualification'])
        self.assertEqual(self.runner_arguments('guard'), ['--group', 'guard'])

    def test_jobs_with_a_single_group_or_the_list_is_refused_before_provisioning(self):
        for argv in (('guard', '--jobs', '2'), ('--list', '--jobs', '2')):
            with self.subTest(argv=argv), patch('sys.stderr', new_callable=io.StringIO) as stderr:
                self.assertEqual(self.cli.main(['dev', 'check', *argv]), 2)
                self.assertIn('--jobs is valid only with qualification', stderr.getvalue())
        self.provision.assert_not_called()
        self.execve.assert_not_called()


class PluginRegistrationTests(unittest.TestCase):
    def test_the_authored_plugin_registration_equals_the_integration_entry_points(self):
        toolchain = toolchain_module(self)
        project = tomllib.loads((REPO / 'integration/pyproject.toml').read_text())['project']
        self.assertEqual(toolchain.PLUGIN, (project['name'], project['version']))
        sections = {}
        for section in toolchain.PLUGIN_FILES['entry_points.txt'].strip().split('\n\n'):
            header, *lines = section.splitlines()
            sections[header.strip('[]')] = dict(line.split(' = ') for line in lines)
        self.assertEqual(sections, project['entry-points'])


if __name__ == '__main__':
    unittest.main()
