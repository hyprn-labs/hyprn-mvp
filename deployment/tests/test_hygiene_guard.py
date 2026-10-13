"""Repository hygiene guard: no tracked file carries a personal location or a secret.

Checks over every tracked file (``git ls-files``):

- ``home_paths``: no absolute user-home path in macOS, Linux or Windows form;
- ``private_keys``: no private-key block header;
- ``tokens``: no token-format literal (cloud, source-hosting, chat and model-provider token
  prefixes, and the product's own agent-token prefix) followed by token characters;
- ``secret_files``: no tracked environment file, key, certificate, keychain or SQLite file.

Every searched literal is assembled at run time from fragments, so this file never contains
what it searches for, and a failure reports only the path, line and kind, never the text.
Every check must find nothing: there is no exemption list.
"""
# Live-runtime fence (deployment/tests/live_fence.py): refuses live roots, live ports, docker, live entry points and real signals.
import sys as _fence_sys
from pathlib import Path as _FencePath
if str(_FencePath(__file__).resolve().parent) not in _fence_sys.path:
    _fence_sys.path.append(str(_FencePath(__file__).resolve().parent))
import live_fence  # noqa: E402
setUpModule, tearDownModule = live_fence.unittest_module_hooks('unit')
from pathlib import Path  # noqa: E402
import re  # noqa: E402
import subprocess  # noqa: E402
import unittest  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
NAME = r'[A-Za-z0-9._-]+'
HOME_PATH = re.compile('|'.join((
    '/' + 'Users' + '/' + NAME,                         # macOS
    '/' + 'home' + '/' + NAME,                          # Linux
    r'\b[A-Za-z]:(?:\\\\|\\|/)+' + 'Users' + r'(?:\\\\|\\|/)+' + NAME,  # Windows
)))
PRIVATE_KEY = re.compile('-----' + 'BEGIN ' + r'(?:[A-Z0-9]+ )*' + 'PRIVATE' + ' KEY' + '-----')
# Token formats: prefix followed by enough token characters to be a credential, never prose.
TOKEN = re.compile('(?<![A-Za-z0-9_-])(?:' + '|'.join((
    'AK' + 'IA' + '[0-9A-Z]{16}', 'AS' + 'IA' + '[0-9A-Z]{16}',     # cloud access keys
    'AI' + 'za' + '[0-9A-Za-z_-]{35}',                              # cloud API keys
    'gh' + '[pousr]_' + '[A-Za-z0-9]{30,}', 'github' + '_pat_' + '[A-Za-z0-9_]{30,}',
    'gl' + 'pat-' + '[A-Za-z0-9_-]{20,}',                           # source hosting
    'xo' + 'x[abposr]-' + '[A-Za-z0-9-]{10,}',                      # chat
    'sk' + '-ant-' + '[A-Za-z0-9_-]{20,}', 'sk' + '-proj-' + '[A-Za-z0-9_-]{20,}',
    'sk' + '-' + '[A-Za-z0-9]{32,}',                                # model providers
    'hf' + '_' + '[A-Za-z0-9]{30,}', 'np' + 'm_' + '[A-Za-z0-9]{36}',
    'sk' + '_live_' + '[A-Za-z0-9]{16,}', 'rk' + '_live_' + '[A-Za-z0-9]{16,}',
    'hyprn' + '_mvp_mcp_' + '[A-Za-z0-9_-]{16,}',                   # product agent tokens
)) + ')')
SECRET_SUFFIXES = tuple('.' + s for s in ('pem', 'key', 'p12', 'pfx', 'crt', 'cer', 'der', 'jks', 'keystore',
                                           'keychain', 'keychain-db', 'kdbx', 'sqlite', 'sqlite3', 'db'))
SECRET_NAMES = frozenset({'.' + 'env', 'id_' + 'rsa', 'id_' + 'dsa', 'id_' + 'ecdsa', 'id_' + 'ed25519', '.netrc', '.pgpass'})

CHECKS = ('home_paths', 'private_keys', 'tokens', 'secret_files')


def tracked():
    result = subprocess.run(['git', '-C', str(REPO), 'ls-files', '-z'], capture_output=True, check=True, timeout=120)
    return [item.decode() for item in result.stdout.split(b'\0') if item]


def text(relative):
    path = REPO / relative
    if path.is_symlink():
        return str(path.readlink()) if hasattr(path, 'readlink') else None
    if not path.is_file():
        return None
    raw = path.read_bytes()
    if b'\0' in raw[:8192]:
        return None
    return raw.decode('utf-8', errors='replace')


def line_findings(content, expression):
    """Line numbers only: a finding never carries the matched text."""
    return sorted({content.count('\n', 0, match.start()) + 1 for match in expression.finditer(content)})


def secret_file(relative):
    name = relative.rsplit('/', 1)[-1]
    return name in SECRET_NAMES or name.startswith('.' + 'env.') or name.lower().endswith(SECRET_SUFFIXES)


def inventory(files=None):
    files = tracked() if files is None else files
    found = {check: {} for check in CHECKS}
    for relative in files:
        if secret_file(relative):
            found['secret_files'][relative] = ['tracked']
        content = text(relative)
        if content is None:
            continue
        for check, expression in (('home_paths', HOME_PATH), ('private_keys', PRIVATE_KEY), ('tokens', TOKEN)):
            lines = line_findings(content, expression)
            if lines:
                found[check][relative] = lines
    return found


class HygieneGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inventory = inventory()

    def assert_clean(self, check):
        self.assertEqual(self.inventory[check], {}, check + ': violations (path: line numbers)')

    def test_no_absolute_user_home_path(self):
        self.assert_clean('home_paths')

    def test_no_private_key_block(self):
        self.assert_clean('private_keys')

    def test_no_token_format_literal(self):
        self.assert_clean('tokens')

    def test_no_tracked_environment_key_certificate_keychain_or_sqlite_file(self):
        self.assert_clean('secret_files')

    def test_detectors_flag_synthetic_inputs_assembled_at_run_time(self):
        person = 'some' + 'one'
        for value in ('/' + 'Users/' + person + '/x', '/' + 'home/' + person, 'C:' + '\\' + 'Users' + '\\' + person,
                      'C:' + '/' + 'Users/' + person, 'C:' + '\\\\' + 'Users' + '\\\\' + person):
            with self.subTest(value=value):
                self.assertTrue(HOME_PATH.search(value))
        for value in ('/' + 'Users', 'scope.root / ' + "'home'", '/opt/homebrew/bin'):
            with self.subTest(value=value):
                self.assertFalse(HOME_PATH.search(value))
        for kind in ('', 'RSA ', 'EC ', 'OPENSSH ', 'ENCRYPTED '):
            self.assertTrue(PRIVATE_KEY.search('-----' + 'BEGIN ' + kind + 'PRIVATE' + ' KEY' + '-----'))
        self.assertFalse(PRIVATE_KEY.search('-----' + 'BEGIN ' + 'PUBLIC' + ' KEY' + '-----'))
        body = 'Ab1' * 14
        for prefix in ('gh' + 'p_', 'sk' + '-ant-', 'sk' + '-proj-', 'sk' + '-', 'gl' + 'pat-', 'xo' + 'xb-',
                       'hyprn' + '_mvp_mcp_', 'github' + '_pat_'):
            with self.subTest(prefix=prefix):
                self.assertTrue(TOKEN.search('token = "' + prefix + body + '"'))
        self.assertTrue(TOKEN.search('AK' + 'IA' + 'ABCDEFGHIJKLMNOP'))
        for value in ('task-' + body, 'sk' + '-short', 'the ' + 'gh' + 'p_ prefix', 'hyprn' + '_mvp_mcp_'):
            with self.subTest(value=value):
                self.assertFalse(TOKEN.search(value))
        files = ['a/.' + 'env', 'a/.' + 'env.local', 'k/server.' + 'pem', 'db/app.' + 'sqlite3', 'b/id_' + 'ed25519',
                 'ok/environment.py', 'ok/keys.md', 'ok/database.py']
        self.assertEqual([f for f in files if secret_file(f)], files[:5])
        self.assertEqual(line_findings('a\n' + '/' + 'home/' + person + '\nb', HOME_PATH), [2])


if __name__ == '__main__':
    unittest.main()
