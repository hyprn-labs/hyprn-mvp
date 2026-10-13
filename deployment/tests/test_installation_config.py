"""The installation configuration (version 1): its closed schema and the stdlib loader.

Every case writes a scratch configuration in a scratch folder with injected platform values;
no case reads a user configuration or touches a user data root. The loader and the schema
make the same decision on every document; the loader alone also enforces the file safety
rules, duplicate keys, the caller's edition and the core location rule.
"""
# Live-runtime fence (deployment/tests/live_fence.py): refuses live roots, live ports, docker, live entry points and real signals.
import sys as _fence_sys
from pathlib import Path as _FencePath
if str(_FencePath(__file__).resolve().parent) not in _fence_sys.path:
    _fence_sys.path.append(str(_FencePath(__file__).resolve().parent))
import live_fence  # noqa: E402
live_runtime_fence = live_fence.pytest_fixture('unit')
import copy
import json
import os
from pathlib import Path
import sys
from uuid import uuid4

import jsonschema
import pytest

REPO = Path(__file__).resolve().parents[2]
for _source in (REPO / 'application/src', REPO / 'integration/src', REPO / 'deployment'):
    if str(_source) not in sys.path:
        sys.path.append(str(_source))
from hyprn_mvp_app import locations  # noqa: E402
from hyprn_mvp_integration import installation  # noqa: E402

SCHEMA = json.loads((REPO / 'deployment/config.schema.json').read_text())
LINUX = locations.Host(system='linux')


@pytest.fixture
def scratch(tmp_path):
    root = Path(os.path.realpath(tmp_path))
    home = root / 'home'
    home.mkdir(mode=0o700)
    folder = root / 'config'
    folder.mkdir(mode=0o700)
    return root, home, folder


def document(root, home, **changes):
    data = root / 'data'
    value = {
        'schema': 'hyprn_mvp.installation/1', 'edition': 'local', 'installation_id': str(uuid4()),
        'owner_username': 'engineer', 'host_home': str(home), 'data_root': str(data),
        'ports': {'app': 18470}, 'origin': 'http://127.0.0.1:18470',
        'docker': {'endpoint': 'unix://' + str(root / 'docker.sock'), 'engine': 'Docker Engine 28.3.1'},
        'release': {'mode': 'checkout', 'require_review': False, 'immutable': False},
        'agent': {'enabled': True, 'token_ttl_hours': 8},
        'upstream': {'cache': str(data / 'cache/upstream/whatsopt')},
    }
    value.update(changes)
    return value


def write(folder, value, *, raw=None, mode=0o600):
    path = folder / 'installation.json'
    path.write_bytes(raw if raw is not None else json.dumps(value, indent=2).encode())
    path.chmod(mode)
    return path


def schema_accepts(value):
    return not list(jsonschema.Draft202012Validator(SCHEMA).iter_errors(value))


def refusal(path, host=LINUX, edition='local'):
    with pytest.raises(installation.InstallationError) as raised:
        installation.load(path, edition=edition, host=host)
    return raised.value


def test_a_valid_configuration_loads_and_the_schema_accepts_it(scratch):
    root, home, folder = scratch
    value = document(root, home)
    loaded = installation.load(write(folder, value), edition='local', host=LINUX)
    assert loaded == value and loaded is not value
    assert schema_accepts(value)
    jsonschema.Draft202012Validator.check_schema(SCHEMA)


def nested(value, path, new):
    *parents, key = path
    target = value
    for name in parents:
        target = target[name]
    if new is DELETE:
        del target[key]
    else:
        target[key] = new
    return value


DELETE = object()
# Documents both the schema and the loader refuse: (where, replacement).
INVALID = [
    (('unknown',), 1), (('ports', 'unknown'), 1), (('docker', 'socket'), 'x'), (('schema',), 'hyprn_mvp.installation/2'),
    (('edition',), 'cloud'), (('installation_id',), 'not-a-uuid'), (('installation_id',), str(uuid4()).upper()),
    (('installation_id',), '00000000-0000-1000-8000-000000000000'), (('owner_username',), ''),
    (('owner_username',), 'a b'), (('host_home',), 'relative'), (('data_root',), '/'), (('data_root',), '/a/../b'),
    (('data_root',), '/a//b'), (('data_root',), '/a/'), (('data_root',), 7), (('ports', 'app'), 80),
    (('ports', 'app'), 70000), (('ports', 'app'), True), (('ports', 'app'), '18470'),
    (('origin',), 'https://127.0.0.1:18470'), (('origin',), 'http://localhost:18470'),
    (('docker', 'endpoint'), 'tcp://127.0.0.1:2375'), (('docker', 'endpoint'), 'unix://relative.sock'),
    (('docker', 'engine'), ''), (('release', 'mode'), 'snapshot'), (('release', 'require_review'), 'no'),
    (('release', 'immutable'), 0), (('agent', 'enabled'), None), (('agent', 'token_ttl_hours'), 0),
    (('agent', 'token_ttl_hours'), 169), (('upstream', 'cache'), 'cache'), (('ports',), []),
    (('schema',), DELETE), (('agent', 'enabled'), DELETE), (('upstream',), DELETE),
]


@pytest.mark.parametrize('where,replacement', INVALID, ids=['.'.join(w) + '=' + repr(r) for w, r in INVALID])
def test_an_unknown_missing_or_invalid_field_is_refused_by_the_loader_and_the_schema(scratch, where, replacement):
    root, home, folder = scratch
    value = nested(document(root, home), where, replacement)
    assert not schema_accepts(value)
    error = refusal(write(folder, value))
    assert error.reason_code in ('configuration_invalid', 'edition_mismatch')


LOADER_ONLY = [
    ('origin port other than ports.app', {'origin': 'http://127.0.0.1:18471'}),
    ('port written as a number with a fraction', {'ports': {'app': 18470.0}}),
    ('data root equal to the home folder', 'home'),
    ('data root above the home folder', 'above'),
    ('upstream cache outside the data root', 'cache-outside'),
    ('upstream cache equal to the data root', 'cache-root'),
]


@pytest.mark.parametrize('case,change', LOADER_ONLY, ids=[c for c, _ in LOADER_ONLY])
def test_cross_field_rules_are_enforced_by_the_loader(scratch, case, change):
    root, home, folder = scratch
    value = document(root, home)
    if change == 'home':
        value['data_root'] = str(home)
    elif change == 'above':
        value['data_root'] = str(root)
        value['upstream']['cache'] = str(root / 'cache')
    elif change == 'cache-outside':
        value['upstream']['cache'] = str(root / 'elsewhere')
    elif change == 'cache-root':
        value['upstream']['cache'] = value['data_root']
    else:
        value.update(change)
    assert refusal(write(folder, value)).reason_code == 'configuration_invalid'


def test_a_duplicate_key_is_refused(scratch):
    root, home, folder = scratch
    text = json.dumps(document(root, home))
    raw = text.replace('"edition": "local"', '"edition": "local", "edition": "local"', 1).encode()
    assert raw.count(b'"edition"') == 2
    assert 'duplicate key' in str(refusal(write(folder, None, raw=raw)))
    nested_raw = text.replace('"app": 18470', '"app": 18470, "app": 18470').encode()
    assert 'duplicate key' in str(refusal(write(folder, None, raw=nested_raw)))


@pytest.mark.parametrize('raw', [b'[]', b'{', b'\xff\xfe', b'{"schema": NaN}', b'{"schema": Infinity}', b''])
def test_a_document_that_is_not_one_finite_json_object_is_refused(scratch, raw):
    _, _, folder = scratch
    assert refusal(write(folder, None, raw=raw)).reason_code == 'configuration_invalid'


def test_an_edition_mismatch_is_refused(scratch):
    root, home, folder = scratch
    error = refusal(write(folder, document(root, home, edition='cloud')))
    assert error.reason_code == 'edition_mismatch' and 'cloud edition' in str(error)
    # The loader serves only the editions it knows.
    with pytest.raises(ValueError):
        installation.load(write(folder, document(root, home)), edition='cloud', host=LINUX)


@pytest.mark.parametrize('mode', [0o644, 0o640, 0o604, 0o660, 0o606])
def test_a_configuration_readable_or_writable_by_others_is_refused(scratch, mode):
    root, home, folder = scratch
    error = refusal(write(folder, document(root, home), mode=mode))
    assert error.reason_code == 'configuration_unsafe' and '0600' in str(error)


def test_an_owner_only_configuration_in_an_open_folder_is_refused(scratch):
    root, home, folder = scratch
    path = write(folder, document(root, home))
    folder.chmod(0o755)
    error = refusal(path)
    assert error.reason_code == 'configuration_unsafe' and '0700' in str(error)


def test_a_configuration_owned_by_another_user_is_refused(scratch, monkeypatch):
    root, home, folder = scratch
    path = write(folder, document(root, home))
    monkeypatch.setattr(os, 'getuid', lambda real=os.getuid(): real + 1)
    error = refusal(path)
    assert error.reason_code == 'configuration_unsafe' and 'owned by this user' in str(error)


def test_a_configuration_behind_a_symbolic_link_is_refused(scratch):
    root, home, folder = scratch
    path = write(folder, document(root, home))
    (root / 'linked-file.json').symlink_to(path)
    (root / 'linked-folder').symlink_to(folder)
    for linked in (root / 'linked-file.json', root / 'linked-folder' / 'installation.json'):
        error = refusal(linked)
        assert error.reason_code == 'configuration_unsafe' and 'symbolic link' in str(error)


def test_a_relative_missing_or_irregular_configuration_is_refused(scratch):
    root, home, folder = scratch
    assert refusal('installation.json').reason_code == 'configuration_unsafe'
    assert refusal(folder / 'absent.json').reason_code == 'configuration_invalid'
    (folder / 'directory.json').mkdir(mode=0o700)
    assert refusal(folder / 'directory.json').reason_code == 'configuration_unsafe'
    path = write(folder, document(root, home))
    os.link(path, folder / 'second-link.json')
    assert 'one link' in str(refusal(path))


def test_an_oversized_configuration_is_refused(scratch):
    _, _, folder = scratch
    raw = b'{"padding": "' + b'x' * installation.MAX_BYTES + b'"}'
    assert 'exceeds' in str(refusal(write(folder, None, raw=raw)))


def test_a_symlinked_data_root_is_refused(scratch):
    root, home, folder = scratch
    (root / 'real').mkdir(mode=0o700)
    (root / 'data').symlink_to(root / 'real')
    error = refusal(write(folder, document(root, home)))
    assert error.reason_code == 'location_refused' and 'symbolic link' in str(error)


def test_an_existing_data_root_must_be_an_owner_only_folder_of_this_user(scratch, monkeypatch):
    root, home, folder = scratch
    path = write(folder, document(root, home))
    (root / 'data').mkdir(mode=0o700)
    assert installation.load(path, edition='local', host=LINUX)['data_root'] == str(root / 'data')
    (root / 'data').chmod(0o755)
    assert refusal(path).reason_code == 'location_refused'
    (root / 'data').chmod(0o700)
    real = os.getuid()
    monkeypatch.setattr(os, 'getuid', lambda: real + 1)
    monkeypatch.setattr(installation, 'read', lambda p: Path(p).read_bytes())
    assert refusal(path).reason_code == 'location_refused'


SYNCED = [
    ('linux', False, ('Dropbox', 'hyprn-mvp')), ('linux', False, ('OneDrive - Company', 'hyprn-mvp')),
    ('linux', True, ('Google Drive', 'hyprn-mvp')), ('macos', False, ('GoogleDrive', 'hyprn-mvp')),
    ('macos', False, ('My Drive', 'hyprn-mvp')),
    ('macos', False, ('Library', 'CloudStorage', 'OneDrive-Personal', 'hyprn-mvp')),
    ('macos', False, ('Library', 'Mobile Documents', 'com~apple~CloudDocs', 'hyprn-mvp')),
    ('macos', False, ('Desktop', 'hyprn-mvp')), ('macos', False, ('Documents', 'hyprn-mvp')),
]


@pytest.mark.parametrize('system,wsl,below', SYNCED, ids=[s + ('-wsl2' if w else '') + ':' + '/'.join(b)
                                                         for s, w, b in SYNCED])
def test_each_synced_location_is_refused_as_data_root_and_upstream_cache(scratch, system, wsl, below):
    root, home, folder = scratch
    host = locations.Host(system=system, wsl=wsl, homes=(home,))
    synced = home.joinpath(*below)
    value = document(root, home, data_root=str(synced), upstream={'cache': str(synced / 'cache')})
    assert schema_accepts(value)
    error = refusal(write(folder, value), host=host)
    assert error.reason_code == 'location_refused' and 'refusing the data root' in str(error)


def test_a_windows_mounted_drive_is_refused_on_wsl2(scratch):
    root, home, folder = scratch
    drive = Path('/mnt/c/hyprn-mvp')
    value = document(root, home, data_root=str(drive), upstream={'cache': str(drive / 'cache')})
    path = write(folder, value)
    error = refusal(path, host=locations.Host(system='linux', wsl=True, homes=(home,)))
    assert error.reason_code == 'location_refused' and 'Windows drive' in str(error)
    assert installation.load(path, edition='local', host=LINUX)['data_root'] == str(drive)


def test_the_loader_and_the_location_rule_decide_alike(scratch):
    root, home, folder = scratch
    hosts = [locations.Host(system='macos', homes=(home,)), locations.Host(system='linux', wsl=True, homes=(home,))]
    for system, wsl, below in [*SYNCED, ('macos', False, ('code', 'data')), ('linux', True, ('code', 'data'))]:
        data = home.joinpath(*below)
        value = document(root, home, data_root=str(data), upstream={'cache': str(data / 'cache')})
        path = write(folder, value)
        for host in hosts:
            expected = locations.location_refusal(data, host)
            try:
                installation.load(path, edition='local', host=host)
                actual = None
            except installation.InstallationError as error:
                assert error.reason_code == 'location_refused'
                actual = str(error)
            assert (actual is None) == (expected is None), (str(data), host)


def test_the_schema_is_closed_and_names_exactly_the_loader_fields():
    assert SCHEMA['additionalProperties'] is False
    assert tuple(SCHEMA['required']) == installation.FIELDS == tuple(SCHEMA['properties'])
    for name, fields in installation.OBJECTS.items():
        part = SCHEMA['properties'][name]
        assert part['additionalProperties'] is False
        assert tuple(part['required']) == fields == tuple(part['properties'])
    assert SCHEMA['properties']['schema']['const'] == installation.SCHEMA
    assert tuple(SCHEMA['properties']['edition']['enum']) == installation.EDITIONS
    assert tuple(SCHEMA['properties']['release']['properties']['mode']['enum']) == installation.RELEASE_MODES
    names = set()

    def collect(node):
        for key, value in node.get('properties', {}).items():
            names.add(key)
            collect(value)
    collect(SCHEMA)
    for name in names - {'token_ttl_hours'}:
        assert not any(word in name for word in ('password', 'secret', 'token', 'key', 'image', 'policy', 'limit',
                                                 'memory', 'cpus', 'pids')), name


def test_the_loader_is_standard_library_only_and_holds_no_folder_layout():
    source = (REPO / 'integration/src/hyprn_mvp_integration/installation.py').read_text()
    imported = {line.split()[1].split('.')[0] for line in source.splitlines() if line.startswith(('import ', 'from '))}
    assert imported <= {'json', 'os', 'pathlib', 're', 'stat', 'uuid', 'hyprn_mvp_app'}
    assert 'from hyprn_mvp_app.locations import' in source
    for fragment in ('Library', 'CloudStorage', 'XDG_', '/mnt', '.config', 'HOME'):
        assert fragment not in source.replace('host_home', ''), fragment


def test_a_loaded_configuration_is_a_copy_that_callers_cannot_alias(scratch):
    root, home, folder = scratch
    value = document(root, home)
    loaded = installation.load(write(folder, value), edition='local', host=LINUX)
    loaded['ports']['app'] = 1
    assert installation.load(write(folder, copy.deepcopy(value)), edition='local', host=LINUX)['ports']['app'] == 18470


def test_deployment_locations_take_the_installation_configuration_after_their_variables(scratch, monkeypatch):
    import local_paths
    root, home, folder = scratch
    value = document(root, home)
    path = write(folder, value)
    for name in (local_paths.DATA_ROOT, local_paths.UPSTREAM_CACHE, local_paths.PORT, local_paths.CONFIG):
        monkeypatch.delenv(name, raising=False)
    assert local_paths.installation() is None and local_paths.data_root(required=False) is None
    monkeypatch.setenv(local_paths.CONFIG, str(path))
    assert local_paths.data_root() == Path(value['data_root'])
    assert local_paths.execution_root() == Path(value['data_root']) / 'execution'
    assert local_paths.upstream_archive_root() == Path(value['upstream']['cache'])
    assert local_paths.port() == 18470
    # The location's own variable still comes first.
    monkeypatch.setenv(local_paths.DATA_ROOT, str(root / 'variable'))
    monkeypatch.setenv(local_paths.UPSTREAM_CACHE, str(root / 'variable-cache'))
    monkeypatch.setenv(local_paths.PORT, '18999')
    assert (local_paths.data_root(), local_paths.upstream_archive_root(), local_paths.port()) == (
        root / 'variable', root / 'variable-cache', 18999)


def test_a_refused_installation_configuration_is_a_deployment_refusal_never_skipped(scratch, monkeypatch):
    import local_paths
    root, home, folder = scratch
    path = write(folder, document(root, home), mode=0o644)
    monkeypatch.delenv(local_paths.DATA_ROOT, raising=False)
    monkeypatch.setenv(local_paths.CONFIG, str(path))
    with pytest.raises(local_paths.LocationUnset, match='configuration_unsafe'):
        local_paths.data_root(required=False)
    monkeypatch.setenv(local_paths.CONFIG, 'relative.json')
    with pytest.raises(local_paths.LocationUnset, match=local_paths.CONFIG):
        local_paths.data_root(required=False)
