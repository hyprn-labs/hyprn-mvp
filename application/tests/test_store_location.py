"""The application store applies the one location rule, the same as the installation loader.

Synthetic stores in the test's own scratch folder only; synced folders are exercised through
injected platform values and a scratch home, never a real synced folder.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import pytest

REPO = Path(__file__).resolve().parents[2]
for _source in (REPO / 'application/src', REPO / 'integration/src'):
    if str(_source) not in sys.path:
        sys.path.append(str(_source))
from hyprn_mvp_app import locations  # noqa: E402
from hyprn_mvp_app.store import Store  # noqa: E402
from hyprn_mvp_integration import installation  # noqa: E402

SYNCED = {
    'every operating system': (('Dropbox',), ('Dropbox (Team)',), ('OneDrive',), ('OneDrive - Company',),
                               ('Google Drive', 'My Drive'), ('GoogleDrive',)),
    'macos': (('Library', 'CloudStorage', 'Box-Box'), ('Library', 'Mobile Documents', 'com~apple~CloudDocs'),
              ('Desktop',), ('Documents',)),
}
HOSTS = (('macos', False), ('linux', False), ('linux', True))


@pytest.fixture
def scratch(tmp_path):
    root = Path(os.path.realpath(tmp_path))
    (root / 'home').mkdir()
    return root


def host(root, system, wsl=False):
    return locations.Host(system=system, wsl=wsl, homes=(root / 'home',))


def store_refusal(path, injected, monkeypatch):
    monkeypatch.setattr(locations, 'current_host', lambda *a, **k: injected)
    try:
        Store(path)
    except ValueError as error:
        return str(error)
    except OSError:  # accepted by the rule, then not creatable here (for example /mnt on this host)
        return None
    return None


def loader_refusal(root, data_root, injected):
    folder = root / ('config-' + uuid4().hex)
    folder.mkdir(mode=0o700)
    document = {
        'schema': 'hyprn_mvp.installation/1', 'edition': 'local', 'installation_id': str(uuid4()),
        'owner_username': 'engineer', 'host_home': str(root / 'home'), 'data_root': str(data_root),
        'ports': {'app': 18470}, 'origin': 'http://127.0.0.1:18470',
        'docker': {'endpoint': 'unix://' + str(root / 'docker.sock'), 'engine': 'Docker Engine'},
        'release': {'mode': 'checkout', 'require_review': False, 'immutable': False},
        'agent': {'enabled': True, 'token_ttl_hours': 8}, 'upstream': {'cache': str(data_root / 'cache')},
    }
    path = folder / 'installation.json'
    path.write_text(json.dumps(document))
    path.chmod(0o600)
    try:
        installation.load(path, edition='local', host=injected)
    except installation.InstallationError as error:
        assert error.reason_code == 'location_refused', str(error)
        return str(error)
    return None


@pytest.mark.parametrize('system,wsl', HOSTS)
def test_store_refuses_each_synced_folder_of_the_host_before_creating_anything(scratch, monkeypatch, system, wsl):
    injected = host(scratch, system, wsl)
    for table, folders in SYNCED.items():
        for below in folders:
            target = scratch.joinpath('home', *below, 'data', 'application', 'application.sqlite')
            reason = store_refusal(target, injected, monkeypatch)
            if table == 'macos' and system != 'macos':
                assert reason is None, (system, below)
                continue
            assert reason is not None and reason.startswith('Application storage refused'), (system, below)
            assert not scratch.joinpath('home', *below).exists()


def test_store_refuses_a_windows_mounted_drive_on_wsl2(scratch, monkeypatch):
    reason = store_refusal(Path('/mnt/c/hyprn-mvp/application/application.sqlite'), host(scratch, 'linux', True),
                           monkeypatch)
    assert 'Windows drive' in reason


def test_store_refuses_a_symbolic_link_as_its_file_or_any_parent(scratch, monkeypatch):
    real = scratch / 'real'
    (real / 'nested').mkdir(parents=True)
    (scratch / 'linked').symlink_to(real)
    (real / 'target.sqlite').write_bytes(b'')
    (real / 'nested' / 'file-link.sqlite').symlink_to(real / 'target.sqlite')
    for path in (scratch / 'linked' / 'application.sqlite', scratch / 'linked' / 'nested' / 'application.sqlite',
                 real / 'nested' / 'file-link.sqlite'):
        reason = store_refusal(path, host(scratch, 'linux'), monkeypatch)
        assert reason is not None and 'symbolic link' in reason, path
    assert (real / 'target.sqlite').read_bytes() == b''


def test_store_accepts_a_scoped_scratch_root_and_creates_an_owner_only_file(scratch):
    """Scoped scratch stores need no temporary-folder exemption: the scope folder is a real,
    off-cloud folder that the location rule accepts on the host it runs on."""
    store = Store(scratch / 'artifacts' / 'application.sqlite')
    assert store.path == scratch / 'artifacts' / 'application.sqlite'
    assert store.path.stat().st_mode & 0o777 == 0o600
    scope = os.environ.get('HYPRN_MVP_TEST_SCOPE_ROOT')
    if scope is not None:  # run by the test-group runner: the store lives in its scope
        assert store.path.is_relative_to(Path(scope))


@pytest.mark.parametrize('system,wsl', HOSTS)
def test_store_and_installation_loader_refuse_exactly_the_same_locations(scratch, monkeypatch, system, wsl):
    injected = host(scratch, system, wsl)
    real = scratch / 'real-root'
    real.mkdir()
    (scratch / 'link-root').symlink_to(real)
    candidates = [scratch.joinpath('home', *below, 'hyprn-mvp') for folders in SYNCED.values() for below in folders]
    candidates += [scratch / 'home' / 'code' / 'hyprn-mvp', scratch / 'link-root' / 'hyprn-mvp',
                   Path('/mnt/c/hyprn-mvp'), Path('/mnt/data/hyprn-mvp')]
    for data_root in candidates:
        by_store = store_refusal(data_root / 'application' / 'application.sqlite', injected, monkeypatch)
        by_loader = loader_refusal(scratch, data_root, injected)
        assert (by_store is None) == (by_loader is None), (str(data_root), by_store, by_loader)


def test_store_holds_no_location_rule_of_its_own():
    """No hard-coded synced folder or temporary-folder exemption remains in the store."""
    result = subprocess.run(['git', 'grep', '-nE', 'CloudStorage|"/tmp"', '--', 'application/src/hyprn_mvp_app/store.py'],
                            cwd=REPO, capture_output=True, text=True)
    assert result.returncode == 1 and result.stdout == '', result.stdout
    source = (REPO / 'application/src/hyprn_mvp_app/store.py').read_text()
    assert 'from .locations import refuse_location' in source
    assert "refuse_location(original, what='Application storage')" in source
