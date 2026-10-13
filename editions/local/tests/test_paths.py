"""The local edition's path policy: per-OS defaults, resolution order and refusals.

Standard library only; every case uses a scratch home and injected platform values, never the
real home folder, configuration or data root:

    <contract environment>/bin/python -I -B -m unittest discover -s editions/local/tests -p test_paths.py
"""
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[3]
for _source in (REPO / 'editions/local/src', Path(__file__).resolve().parent):
    if str(_source) not in sys.path:
        sys.path.insert(0, str(_source))
from hyprn_mvp_local import paths  # noqa: E402
from test_shim import PINS, Sandbox  # noqa: E402

PLATFORM_HOSTS = {'darwin-arm64': 'macos', 'linux-x86_64': 'linux', 'linux-aarch64': 'linux'}


class ScratchTest(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory(prefix='hyprn-mvp-paths-')
        self.addCleanup(scratch.cleanup)
        self.root = Path(os.path.realpath(scratch.name))
        self.home = self.root / 'home'
        self.home.mkdir()

    def host(self, system, wsl=False):
        return paths.Host(system=system, wsl=wsl, homes=(self.home,))


class DefaultTests(ScratchTest):
    def test_each_operating_system_has_the_documented_defaults(self):
        xdg = self.root / 'xdg'
        cases = (
            ('macos', {}, {'config': self.home / '.config/hyprn-mvp/installation.json',
                           'data_root': self.home / 'Library' / 'Application Support' / 'hyprn-mvp',
                           'tools': self.home / 'Library' / 'Caches' / 'hyprn-mvp' / 'tools'}),
            # macOS ignores the XDG variables.
            ('macos', {'XDG_CONFIG_HOME': str(xdg), 'XDG_DATA_HOME': str(xdg), 'XDG_CACHE_HOME': str(xdg)},
             {'config': self.home / '.config/hyprn-mvp/installation.json',
              'data_root': self.home / 'Library' / 'Application Support' / 'hyprn-mvp',
              'tools': self.home / 'Library' / 'Caches' / 'hyprn-mvp' / 'tools'}),
            ('linux', {}, {'config': self.home / '.config/hyprn-mvp/installation.json',
                           'data_root': self.home / '.local/share/hyprn-mvp',
                           'tools': self.home / '.cache/hyprn-mvp/tools'}),
            ('linux', {'XDG_CONFIG_HOME': str(xdg / 'c'), 'XDG_DATA_HOME': str(xdg / 'd'), 'XDG_CACHE_HOME': str(xdg / 'k')},
             {'config': xdg / 'c/hyprn-mvp/installation.json', 'data_root': xdg / 'd/hyprn-mvp',
              'tools': xdg / 'k/hyprn-mvp/tools'}),
            # A relative XDG value is ignored.
            ('linux', {'XDG_DATA_HOME': 'relative', 'XDG_CACHE_HOME': 'relative'},
             {'data_root': self.home / '.local/share/hyprn-mvp', 'tools': self.home / '.cache/hyprn-mvp/tools'}),
        )
        for system, extra, expected in cases:
            for wsl in ((False, True) if system == 'linux' else (False,)):
                for name, path in expected.items():
                    with self.subTest(system=system, wsl=wsl, extra=sorted(extra), name=name):
                        environ = {'HOME': str(self.home), **extra}
                        self.assertEqual(paths.default(name, environ=environ, host=self.host(system, wsl)), path)

    def test_logs_live_in_the_data_root(self):
        self.assertEqual(paths.logs(self.root / 'data'), self.root / 'data' / 'logs')

    def test_an_absent_home_takes_the_account_home_and_an_unknown_system_has_no_default(self):
        account = self.root / 'account'
        host = paths.Host(system='linux', homes=(account,))
        self.assertEqual(paths.default('data_root', environ={'HOME': 'relative'}, host=host),
                         account / '.local/share/hyprn-mvp')
        with self.assertRaises(paths.LocationUnresolved):
            paths.default('data_root', environ={}, host=paths.Host(system='linux'))
        with self.assertRaises(paths.LocationUnresolved):
            paths.default('data_root', environ={'HOME': str(self.home)}, host=self.host('freebsd'))

    def test_wsl2_is_recognised_by_its_distribution_variable_or_kernel_release(self):
        cases = (({'WSL_DISTRO_NAME': 'Ubuntu'}, '6.6.0-generic', True),
                 ({}, '5.15.167.4-microsoft-standard-WSL2', True),
                 ({}, '6.8.0-45-generic', False))
        for environ, release, expected in cases:
            with self.subTest(release=release):
                host = paths.current_host(environ, system='Linux', osrelease=release, account_home=str(self.home))
                self.assertEqual((host.system, host.wsl), ('linux', expected))
        host = paths.current_host({'WSL_DISTRO_NAME': 'Ubuntu'}, system='Darwin', account_home=str(self.home))
        self.assertEqual((host.system, host.wsl), ('macos', False))

    def test_the_entry_point_computes_the_tool_cache_default_of_the_path_policy(self):
        xdg = self.root / 'xdg-cache'
        cases = (('darwin-arm64', {}), ('darwin-arm64', {'XDG_CACHE_HOME': str(xdg)}), ('linux-x86_64', {}),
                 ('linux-aarch64', {'XDG_CACHE_HOME': str(xdg)}), ('linux-x86_64', {'XDG_CACHE_HOME': 'relative'}))
        for index, (platform, extra) in enumerate(cases):
            with self.subTest(platform=platform, extra=extra):
                expected = paths.default('tools', environ={'HOME': str(self.home), **extra},
                                         host=self.host(PLATFORM_HOSTS[platform]))
                box = Sandbox(self.root / ('box-' + str(index)))
                box.home = self.home
                box.pin_crafted_archive(platform)
                result = box.run('version', platform=platform, env=extra, tools=False)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(box.uv_settings()['UV_PYTHON_INSTALL_DIR'], str(expected / 'python'))
                self.assertTrue((expected / 'uv' / PINS['uv_version'] / platform / 'uv').is_file())
                shutil.rmtree(expected)


class ResolutionTests(ScratchTest):
    def test_flag_then_variable_then_configuration_then_default(self):
        host = self.host('linux')
        flag, variable, configured = (self.root / name for name in ('flag', 'variable', 'configured'))
        environ = {'HOME': str(self.home), paths.DATA_ROOT: str(variable)}
        configuration = {'data_root': str(configured)}
        self.assertEqual(paths.resolve('data_root', flag=str(flag), configuration=configuration, environ=environ,
                                       host=host), paths.Resolved(flag, 'flag'))
        self.assertEqual(paths.resolve('data_root', configuration=configuration, environ=environ, host=host),
                         paths.Resolved(variable, 'environment'))
        environ.pop(paths.DATA_ROOT)
        self.assertEqual(paths.resolve('data_root', configuration=configuration, environ=environ, host=host),
                         paths.Resolved(configured, 'configuration'))
        self.assertEqual(paths.resolve('data_root', environ=environ, host=host),
                         paths.Resolved(self.home / '.local/share/hyprn-mvp', 'default'))
        self.assertEqual(paths.resolve('config', environ={'HOME': str(self.home), paths.CONFIG: str(flag)}, host=host),
                         paths.Resolved(flag, 'environment'))

    def test_an_unresolved_location_is_asked_or_refused_never_invented(self):
        host = paths.Host(system='linux')
        asked = []
        answer = self.root / 'chosen'
        resolved = paths.resolve('data_root', environ={}, host=host,
                                 ask=lambda name, reason: asked.append(name) or str(answer))
        self.assertEqual((resolved, asked), (paths.Resolved(answer, 'answer'), ['data_root']))
        for ask in (None, lambda name, reason: None):
            with self.assertRaises(paths.LocationUnresolved) as raised:
                paths.resolve('data_root', environ={}, host=host, ask=ask)
            self.assertEqual((raised.exception.reason_code, raised.exception.exit_code), ('location_unresolved', 2))
            self.assertIn('--data-dir', str(raised.exception))
            self.assertIn(paths.DATA_ROOT, str(raised.exception))

    def test_a_refused_default_is_asked_instead_of_used(self):
        home = self.root / 'Dropbox' / 'home'
        host = paths.Host(system='linux', homes=(home,))
        answer = self.root / 'local'
        resolved = paths.resolve('data_root', environ={'HOME': str(home)}, host=host, ask=lambda n, r: str(answer))
        self.assertEqual(resolved, paths.Resolved(answer, 'answer'))
        with self.assertRaises(paths.LocationUnresolved):
            paths.resolve('data_root', environ={'HOME': str(home)}, host=host)


class RefusalTests(ScratchTest):
    def refused(self, path, host):
        with self.assertRaises(paths.LocationRefused) as raised:
            paths.resolve('data_root', flag=str(path), environ={'HOME': str(self.home)}, host=host)
        self.assertEqual((raised.exception.reason_code, raised.exception.exit_code), ('location_refused', 2))
        return str(raised.exception)

    def test_each_synced_location_of_each_operating_system_is_refused(self):
        everywhere = ('Dropbox', 'Dropbox (Team)', 'OneDrive', 'OneDrive - Company', 'Google Drive', 'GoogleDrive',
                      'My Drive')
        for system, wsl in (('macos', False), ('linux', False), ('linux', True)):
            for folder in everywhere:
                with self.subTest(system=system, wsl=wsl, folder=folder):
                    self.assertIn('sync client', self.refused(self.home / folder / 'data', self.host(system, wsl)))
        for below in (('Library', 'CloudStorage', 'Box-Box'), ('Library', 'Mobile Documents', 'com~apple~CloudDocs'),
                      ('Desktop',), ('Documents', 'work')):
            with self.subTest(macos=below):
                self.refused(self.home.joinpath(*below, 'data'), self.host('macos'))
                # The same folders are ordinary folders on Linux.
                self.assertEqual(paths.resolve('data_root', flag=str(self.home.joinpath(*below, 'data')),
                                               host=self.host('linux')).source, 'flag')

    def test_a_windows_mounted_drive_is_refused_on_wsl2_only(self):
        drive = Path('/mnt/c/work/hyprn-mvp')
        self.assertIn('Windows drive', self.refused(drive, self.host('linux', wsl=True)))
        self.assertIn('Windows drive', self.refused(Path('/mnt/D'), self.host('linux', wsl=True)))
        self.assertEqual(paths.location_refusal(drive, self.host('linux')), None)
        self.assertEqual(paths.location_refusal(Path('/mnt/data/hyprn-mvp'), self.host('linux', wsl=True)), None)

    def test_a_symbolic_link_in_the_path_or_a_parent_is_refused(self):
        real = self.root / 'real'
        (real / 'inner').mkdir(parents=True)
        (self.root / 'link').symlink_to(real)
        for path in (self.root / 'link', self.root / 'link' / 'inner', self.root / 'link' / 'inner' / 'absent'):
            with self.subTest(path=str(path.relative_to(self.root))):
                self.assertIn('symbolic link', self.refused(path, self.host('linux')))
        # A link to a synced folder is refused for its target too.
        (self.home / 'Dropbox').mkdir()
        (self.root / 'synced-link').symlink_to(self.home / 'Dropbox')
        self.assertIn('sync client', self.refused(self.root / 'synced-link' / 'data', self.host('linux')))

    def test_a_relative_or_unnormalized_location_is_refused(self):
        for value in ('relative/data', str(self.root) + '/a/../data', str(self.root) + '//data', str(self.root) + '/'):
            with self.subTest(value=value):
                self.assertIn('absolute normalized', self.refused(value, self.host('linux')))

    def test_an_existing_data_root_must_be_a_folder_owned_by_the_user(self):
        folder = self.root / 'data'
        folder.mkdir()
        self.assertEqual(paths.resolve('data_root', flag=str(folder), host=self.host('linux')).path, folder)
        with patch('os.getuid', return_value=os.getuid() + 1):
            self.assertIn('owned by this user', self.refused(folder, self.host('linux')))
        file = self.root / 'file'
        file.write_text('')
        self.assertIn('owned by this user', self.refused(file, self.host('linux')))

    def test_the_entry_point_and_the_policy_refuse_the_same_synced_checkouts(self):
        cases = (('darwin-arm64', ('Library', 'CloudStorage', 'OneDrive-Personal')),
                 ('darwin-arm64', ('Library', 'Mobile Documents', 'com~apple~CloudDocs')),
                 ('darwin-arm64', ('Desktop',)), ('darwin-arm64', ('Documents', 'code')),
                 ('linux-x86_64', ('Dropbox', 'code')), ('linux-x86_64', ('OneDrive',)),
                 ('linux-aarch64', ('Google Drive', 'My Drive')), ('linux-x86_64', ('code',)),
                 ('darwin-arm64', ('code',)))
        for index, (platform, below) in enumerate(cases):
            with self.subTest(platform=platform, below=below):
                checkout = self.home.joinpath(*below, 'checkout-' + str(index))
                box = Sandbox(self.root / ('box-' + str(index)), checkout=checkout)
                box.home = self.home
                result = box.run('version', platform=platform)
                policy = paths.location_refusal(checkout, self.host(PLATFORM_HOSTS[platform]))
                self.assertEqual('refusing the checkout' in result.stderr, policy is not None, result.stderr)


if __name__ == '__main__':
    unittest.main()
