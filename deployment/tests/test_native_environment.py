"""The native host environment of an execution root, built from pinned packages.

One scratch preparation serves the module: a release snapshot copied from this tree's product
paths, an execution root and a uv package cache, all inside the test's own scope. The pinned
uv and CPython are read from the tool cache and never written. Network is used only by the
acquisition steps of prepare (the locked distributions and the build backend's wheel).
"""

# Live-runtime fence (deployment/tests/live_fence.py): refuses live roots, live ports, docker,
# live entry points and real signals.
import sys as _fence_sys
from pathlib import Path as _FencePath

if str(_FencePath(__file__).resolve().parent) not in _fence_sys.path:
    _fence_sys.path.append(str(_FencePath(__file__).resolve().parent))
import live_fence  # noqa: E402

live_runtime_fence = live_fence.pytest_fixture('unit')
import ast  # noqa: E402
import base64  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
from pathlib import Path  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import tomllib  # noqa: E402
from types import SimpleNamespace  # noqa: E402

import pytest  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'deployment'))
import local_paths  # noqa: E402
import native_environment as native  # noqa: E402

# The product paths of a release snapshot that prepare and the native profile read.
SNAPSHOT_PATTERNS = (
    'application/pyproject.toml',
    'application/src/**/*.py',
    'application/src/hyprn_mvp_app/migrations/*.sql',
    'integration/pyproject.toml',
    'integration/src/**/*.py',
    'contracts/schemas/*.json',
    'deployment/locks/*',
)
INSTALLATION_ID = '0f1e2d3c-4b5a-4687-9a8b-7c6d5e4f3a2b'
INVENTORY = (
    'import importlib.metadata as m, json; '
    'print(json.dumps(sorted([d.metadata["Name"], d.version] for d in m.distributions())))'
)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def release_snapshot(target):
    """A release snapshot holding this tree's product paths (no bytecode)."""
    for pattern in SNAPSHOT_PATTERNS:
        for path in sorted(REPO.glob(pattern)):
            if '__pycache__' in path.parts or not path.is_file():
                continue
            destination = target / path.relative_to(REPO)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(path.read_bytes())
    return target


def reviewed_native_set():
    """The reviewed native set N: the native group of pyproject.toml without ruff."""
    entries = tomllib.loads((REPO / 'pyproject.toml').read_text())['dependency-groups']['native']
    pinned = dict(entry.split('==') for entry in entries)
    return {native.normalized(name): version for name, version in pinned.items() if name != 'ruff'}


def project_distributions():
    found = {}
    for folder in native.PROJECT_FOLDERS:
        project = tomllib.loads((REPO / folder / 'pyproject.toml').read_text())['project']
        found[native.normalized(project['name'])] = project['version']
    return found


def tree_state(root):
    """Every path below root with its size and modification time (links not followed)."""
    return {
        str(p.relative_to(root)): (p.lstat().st_size, p.lstat().st_mtime_ns)
        for p in root.rglob('*')
    }


@pytest.fixture(scope='module')
def prepared(tmp_path_factory):
    base = tmp_path_factory.mktemp('native')
    source = release_snapshot(base / 'release' / 'source')
    root = base / 'data' / 'execution'
    root.mkdir(parents=True, mode=0o700)
    tools = local_paths.tools_root()
    record = native.prepare(root, source, tools=tools, cache=base / 'uv-cache')
    return SimpleNamespace(
        base=base,
        source=source,
        root=root,
        tools=tools,
        record=record,
        environment=root / record['environment'],
    )


def test_native_host_lock_is_the_reviewed_native_set_with_the_hashes_of_uv_lock():
    raw = (REPO / native.NATIVE_HOST_LOCK).read_bytes()
    assert native.locked_distributions(raw) == reviewed_native_set()
    locked = {}
    for package in tomllib.loads((REPO / 'uv.lock').read_text())['package']:
        artifacts = [package.get('sdist', {}), *package.get('wheels', [])]
        hashes = {a['hash'].removeprefix('sha256:') for a in artifacts if 'hash' in a}
        locked[(package['name'], package.get('version'))] = hashes
    entries = raw.decode().split('\n')
    for name, version in reviewed_native_set().items():
        start = next(
            i for i, line in enumerate(entries) if line.startswith(name + '==' + version + ' ')
        )
        hashes = set()
        for line in entries[start + 1 :]:
            if not line.startswith('    --hash=sha256:'):
                break
            hashes.add(line.split(':')[1].split(' ')[0])
        assert hashes == locked[(name, version)], name
    pins = json.loads((REPO / 'deployment/pins.json').read_bytes())
    aiida = {item['sha256'] for item in pins['verified_artifacts']['aiida-core']}
    assert aiida == locked[('aiida-core', '2.9.3')]


def test_a_lock_entry_without_an_exact_hashed_pin_is_refused():
    marker = " ; sys_platform == 'darwin' \\\n"
    digest = '    --hash=sha256:' + '0' * 64 + '\n'
    assert native.locked_distributions(b'one==1.0' + marker.encode() + digest.encode()) == {
        'one': '1.0'
    }
    for raw in (
        'one==1.0' + marker,
        'one>=1.0' + marker + digest,
        'one==1.0' + marker + digest + 'one==1.0' + marker + digest,
        'one==1.0' + marker + '    --hash=md5:00\n',
    ):
        with pytest.raises(ValueError):
            native.locked_distributions(raw.encode())


def test_a_snapshot_package_built_by_another_backend_is_refused_before_any_effect(tmp_path):
    source = release_snapshot(tmp_path / 'source')
    project = source / 'integration' / 'pyproject.toml'
    project.write_text(project.read_text().replace('flit_core==4.1.0', 'setuptools>=61'))
    root = tmp_path / 'execution'
    root.mkdir()
    with pytest.raises(ValueError, match='pinned backend'):
        native.prepare(root, source, tools=local_paths.tools_root(), cache=tmp_path / 'cache')
    assert list(root.iterdir()) == []
    assert not (tmp_path / 'cache').exists()


def test_a_package_file_the_wheel_would_not_carry_is_refused(tmp_path):
    source = release_snapshot(tmp_path / 'source')
    (source / 'integration/src/hyprn_mvp_integration/table.json').write_text('{}')
    with pytest.raises(ValueError, match='would not carry'):
        native.stage_package(source, 'integration', tmp_path / 'build')


def test_packaged_application_keeps_exact_owned_migration_sql(prepared):
    source = prepared.source / 'application/src/hyprn_mvp_app/migrations'
    installed = prepared.environment / 'lib/python3.12/site-packages/hyprn_mvp_app/migrations'
    originals = {path.name: path.read_bytes() for path in source.glob('*.sql')}
    assert originals
    assert {path.name: path.read_bytes() for path in installed.glob('*.sql')} == originals


def test_sql_outside_the_owned_migration_directory_is_refused(tmp_path):
    source = release_snapshot(tmp_path / 'source')
    (source / 'application/src/hyprn_mvp_app/unreviewed.sql').write_text('SELECT 1')
    with pytest.raises(ValueError, match='would not carry'):
        native.stage_package(source, 'application', tmp_path / 'build')


def test_worker_notice_export_preserves_bytes_without_native_profile(tmp_path):
    tmp_path.chmod(0o700)
    content = b'Exact reviewed dependency notice\n'
    inventory = native.store_worker_inventory(tmp_path, [dict(name='dependency', version='1.0',
        files={'dependency-1.0.dist-info/licenses/LICENSE': base64.b64encode(content).decode()})])
    assert inventory == [dict(name='dependency', version='1.0')]
    assert (tmp_path / 'licenses/worker/dependency-1.0.dist-info/licenses/LICENSE').read_bytes() == content
    assert not (tmp_path / 'aiida').exists()
    with pytest.raises(ValueError, match='exists or is linked'):
        native.store_worker_inventory(tmp_path, [dict(name='dependency', version='1.0', files={})])


@pytest.mark.parametrize('relative', ['../escape', '/escape', 'dist.dist-info/../../escape',
                                    'dist.dist-info/../escape', 'notices/LICENSE',
                                    'dist.dist-info//LICENSE'])
def test_unsafe_worker_notice_paths_fail_before_any_write(tmp_path, relative):
    tmp_path.chmod(0o700)
    with pytest.raises(ValueError, match='Unsafe worker notice path'):
        native.store_worker_inventory(tmp_path, [dict(name='dependency', version='1.0',
            files={relative: base64.b64encode(b'notice').decode()})])
    assert list(tmp_path.iterdir()) == []


def fake_distribution(site, name, version, files):
    """A minimal installed distribution: its files, METADATA and a RECORD hashing them."""
    info = site / (name + '-' + version + '.dist-info')
    info.mkdir(parents=True)
    (info / 'METADATA').write_text(
        'Metadata-Version: 2.1\nName: ' + name + '\nVersion: ' + version + '\n'
    )
    lines = []
    for relative, raw in {
        **files,
        info.name + '/METADATA': (info / 'METADATA').read_bytes(),
    }.items():
        (site / relative).parent.mkdir(parents=True, exist_ok=True)
        (site / relative).write_bytes(raw)
        digest = native.base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).decode().rstrip('=')
        lines.append(relative + ',sha256=' + digest + ',' + str(len(raw)))
    (info / 'RECORD').write_text('\n'.join([*lines, info.name + '/RECORD,,']) + '\n')


REFUSED_ENVIRONMENTS = {
    'missing: one==2.0': {'expected': {'one': '2.0'}},
    'unexpected: two==1.0': {'extra': 'two'},
    'startup path file': {'startup': True},
    'origin record': {'origin': True},
    'differ from the release snapshot': {'module': b'VALUE = 2\n'},
}


@pytest.mark.parametrize('case', [None, *REFUSED_ENVIRONMENTS])
def test_an_environment_that_differs_from_its_locks_is_refused(tmp_path, case):
    change = REFUSED_ENVIRONMENTS.get(case, {})
    source = tmp_path / 'source'
    (source / 'integration/src/pkg').mkdir(parents=True)
    (source / 'integration/src/pkg/__init__.py').write_bytes(b'VALUE = 1\n')
    site = tmp_path / 'site'
    fake_distribution(site, 'one', '1.0', {'one.py': b''})
    project = {'pkg/__init__.py': change.get('module', b'VALUE = 1\n')}
    if change.get('origin'):
        project['project-0.1.0.dist-info/direct_url.json'] = b'{}'
    fake_distribution(site, 'project', '0.1.0', project)
    if 'extra' in change:
        fake_distribution(site, change['extra'], '1.0', {})
    if change.get('startup'):
        (site / 'hook.pth').write_text('import os\n')
    expected = {'project': '0.1.0', **change.get('expected', {'one': '1.0'})}
    if case is None:
        found = native.check_environment(site, source, expected, {'project': 'integration'})
        assert set(found) == {'one', 'project'}
        return
    with pytest.raises(ValueError, match=case):
        native.check_environment(site, source, expected, {'project': 'integration'})


def test_a_build_backend_artifact_that_differs_from_its_pin_is_refused(tmp_path, monkeypatch):
    backend = json.loads((REPO / native.BUILD_BACKEND_LOCK).read_bytes())

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, size):
            return b'x' * backend['wheel']['size']

    monkeypatch.setattr(native.urllib.request, 'urlopen', lambda url, timeout: Response())
    with pytest.raises(ValueError, match='differs from its pin'):
        native.acquire_backend(backend, tmp_path / 'backend')
    assert not (tmp_path / 'backend').exists()


def test_environment_is_named_by_the_lock_and_holds_exactly_the_reviewed_distributions(prepared):
    lock = (prepared.source / native.NATIVE_HOST_LOCK).read_bytes()
    assert prepared.environment.name == native.ENVIRONMENT_PREFIX + sha(lock)[:16]
    result = subprocess.run(
        [str(prepared.environment / 'bin/python'), '-I', '-B', '-c', INVENTORY],
        capture_output=True,
        text=True,
        check=True,
    )
    installed = {native.normalized(name): version for name, version in json.loads(result.stdout)}
    assert installed == {**reviewed_native_set(), **project_distributions()}
    inventory = json.loads((prepared.root / native.INSTALLED_INVENTORY).read_bytes())
    assert {item['name']: item['version'] for item in inventory} == reviewed_native_set()
    for item in inventory:
        for record in item['files']:
            raw = (
                prepared.environment / 'lib/python3.12/site-packages' / record['path']
            ).read_bytes()
            assert (sha(raw), len(raw)) == (record['sha256'], record['size'])
    evidence = json.loads((prepared.root / native.ENVIRONMENT_EVIDENCE).read_bytes())
    assert evidence['build_backend']['version'] == '4.1.0'
    assert set(evidence['project_wheels']) == set(project_distributions())


def test_installed_project_modules_are_byte_identical_to_the_release_snapshot(prepared):
    site = prepared.environment / 'lib/python3.12/site-packages'
    for folder in native.PROJECT_FOLDERS:
        sources = prepared.source / folder / 'src'
        for path in sources.rglob('*.py'):
            relative = path.relative_to(sources)
            assert (site / relative).read_bytes() == path.read_bytes(), relative


def test_a_second_prepare_is_refused_and_changes_nothing(prepared):
    before = tree_state(prepared.root)
    with pytest.raises(ValueError, match='already prepared'):
        native.prepare(
            prepared.root, prepared.source, tools=prepared.tools, cache=prepared.base / 'uv-cache'
        )
    assert tree_state(prepared.root) == before


def test_audited_licence_metadata_bytes_are_the_installed_ones(prepared):
    path = REPO / 'integration/src/hyprn_mvp_integration/computational_export.py'
    tree = ast.parse(path.read_text())
    audited = next(
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and [ast.unparse(t) for t in node.targets] == ['AUDITED_LICENSES']
    )
    native_entries = {
        k: v for k, v in audited.items() if k.startswith(native.NATIVE_LICENSES + '/')
    }
    assert len(native_entries) == 5
    for relative, expected in native_entries.items():
        assert sha((prepared.root / relative).read_bytes()) == expected, relative


def test_environment_names_no_checkout_path_and_holds_no_startup_path_file(prepared):
    checkout, snapshot = str(REPO).encode(), str(prepared.source).encode()
    for path in [*prepared.environment.rglob('*'), *prepared.root.glob('l*/**/*')]:
        if path.is_symlink():
            assert not Path(path.readlink()).is_relative_to(REPO), path
            continue
        assert path.suffix != '.pth', path
        assert path.name != 'direct_url.json', path
        if path.is_file():
            raw = path.read_bytes()
            assert checkout not in raw and snapshot not in raw, path


def test_profile_is_initialised_in_scratch_and_the_scalar_entry_point_loads(prepared):
    """The installation's core.sqlite_dos profile; the plugin entry point comes from the
    installed integration wheel and resolves to the release snapshot's module, which the
    release binding puts first on the import path."""
    code = (
        'import json, sys\n'
        'source = sys.argv[1]\n'
        "sys.path[:0] = [source + '/application/src', source + '/integration/src', sys.argv[2]]\n"
        'import native_environment\n'
        "configuration = {'edition': 'local', 'installation_id': sys.argv[4]}\n"
        'profile = native_environment.initialize(sys.argv[3], configuration)\n'
        'import importlib.metadata as m\n'
        'from aiida.plugins import CalculationFactory, ParserFactory\n'
        "calculation = CalculationFactory('hyprn_mvp.scalar')\n"
        "parser = ParserFactory('hyprn_mvp.scalar')\n"
        "points = m.entry_points(group='aiida.calculations', name='hyprn_mvp.scalar')\n"
        'print(json.dumps(dict(profile=profile, calculation=calculation.__qualname__,\n'
        '    parser=parser.__qualname__, file=sys.modules[calculation.__module__].__file__,\n'
        '    distributions=[[e.dist.name, e.dist.version] for e in points])))\n'
    )
    env = {
        'PATH': '/usr/bin:/bin',
        'HOME': str(prepared.base),
        'AIIDA_PATH': str(prepared.root / 'aiida'),
    }
    arguments = [prepared.source, REPO / 'deployment', prepared.root, INSTALLATION_ID]
    result = subprocess.run(
        [str(prepared.environment / 'bin/python'), '-I', '-B', '-c', code, *map(str, arguments)],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr[-3000:]
    loaded = json.loads(result.stdout.splitlines()[-1])
    profile = 'hyprn-mvp-local-' + INSTALLATION_ID[:8]
    assert loaded['profile'] == profile
    assert (loaded['calculation'], loaded['parser']) == ('ScalarCalculation', 'ScalarParser')
    assert Path(loaded['file']).is_relative_to(prepared.source)
    assert loaded['distributions'] == [['hyprn-mvp-integration', '0.1.0']]
    config = json.loads((prepared.root / 'aiida/.aiida/config.json').read_bytes())
    assert config.get('default_profile') is None and set(config['profiles']) == {profile}
    storage = config['profiles'][profile]['storage']
    assert storage == {
        'backend': 'core.sqlite_dos',
        'config': {'filepath': str(prepared.root / 'aiida-store')},
    }
    identity = json.loads((prepared.root / 'profile-identity.json').read_bytes())
    assert identity['profile'] == profile
