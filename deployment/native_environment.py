"""The native host environment of an execution root and its release-bound launch wrapper.

``prepare`` builds ``<execution root>/venv-<first 16 hex of the native host lock's SHA-256>``
from a release snapshot: the pinned CPython of ``deployment/locks/tools.json``, exactly the
hashed distributions of ``deployment/locks/native-host.txt``, and the snapshot's own packages
(``hyprn-mvp-app``, ``hyprn-mvp-integration``) as wheels built offline by the hashed build
backend of ``deployment/locks/build-backend.json`` and installed without dependencies. It
writes the installed inventory (``locks/native-installed.json``) and the dependency licence
texts (``licenses/native/``). ``extend`` adds the restricted worker's licence inventory once
the worker is built and binds the launch wrapper; ``initialize`` creates the installation's
native profile. Network is used only to acquire pinned artifacts; every build runs offline.
No profile, store, job or service source of another installation is ever read.

Every default location comes from deployment/local_paths.py; the commands refuse while it is
unset.
"""

import base64
import csv
import hashlib
import importlib.metadata as metadata
import io
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tomllib
import urllib.request
from datetime import datetime, timezone
from uuid import uuid4
import local_paths

REPO = Path(__file__).resolve().parents[1]
ROOT = local_paths.execution_root(required=False)
REVIEWED = local_paths.native_inventory(required=False)
PYTHON = local_paths.native_python(required=False)

# Inputs of prepare, read from the release snapshot (never from a checkout).
NATIVE_HOST_LOCK = 'deployment/locks/native-host.txt'
BUILD_BACKEND_LOCK = 'deployment/locks/build-backend.json'
TOOLS_LOCK = 'deployment/locks/tools.json'
# Snapshot folders of the packages that are built into wheels.
PROJECT_FOLDERS = ('application', 'integration')
ENVIRONMENT_PREFIX = 'venv-'
INSTALLED_INVENTORY = 'locks/native-installed.json'
NATIVE_LICENSES = 'licenses/native'
ENVIRONMENT_EVIDENCE = 'evidence/native-environment.json'
# Fixed wheel timestamp (1980-01-01, the earliest a zip entry records): the wheels of one
# snapshot are byte-identical whenever they are built.
SOURCE_DATE_EPOCH = '315532800'
DOWNLOAD_TIMEOUT_SECONDS = 60
# uv settings that survive the hermetic environment: the TLS trust choice only.
UV_KEPT = ('UV_SYSTEM_CERTS', 'UV_NATIVE_TLS')
PLATFORMS = {
    ('darwin', 'arm64'): 'darwin-arm64',
    ('linux', 'x86_64'): 'linux-x86_64',
    ('linux', 'aarch64'): 'linux-aarch64',
    ('linux', 'arm64'): 'linux-aarch64',
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def emit(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')


# Selected-release binding of this process (set by the __main__ entrypoint only).
BINDING = None


def launch_worker_text(root, binding, python=PYTHON):
    """Launcher wrapper that re-binds through the exact retained release bootstrap.

    An interpreter's startup path hook may name another checkout, so
    `-m hyprn_mvp_integration.launcher` could import ambient source. The bootstrap
    validates the manifest digest, removes those paths and refuses mixed bindings.
    """
    if binding is None or not binding.bound:
        raise ValueError('Selected release binding required for launch-worker')
    python = local_paths.require(python)
    return (
        '#!/bin/sh\nexport AIIDA_PATH='
        + shlex.quote(str(Path(root) / 'aiida'))
        + '\nexec '
        + shlex.quote(str(python))
        + ' -B '
        + shlex.quote(str(binding.source / 'deployment/release.py'))
        + ' exec-module --expected-sha256 '
        + binding.manifest_sha256
        + ' hyprn_mvp_integration.launcher -- "$@"\n'
    )


def write_launch_worker(root, binding):
    """Write the release wrapper through an exclusive, never-followed temporary in root,
    then atomically replace launch-worker. A planted symlink or leftover name is refused."""
    root = Path(root)
    if any(p.is_symlink() for p in (root, root / 'launch-worker')):
        raise ValueError('Unsafe launch-worker path')
    text = launch_worker_text(root, binding).encode()
    temporary = root / ('.launch-worker-' + uuid4().hex)
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o700)
    try:
        with os.fdopen(fd, 'wb') as output:
            output.write(text)
            os.fchmod(output.fileno(), 0o700)
        os.replace(temporary, root / 'launch-worker')
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return text


# An execution root holding a native profile/store or executor state is populated; prepare
# and extend would overwrite its launch-worker, selected.json, runtime.json and locks.
POPULATED_MARKERS = (
    'aiida',
    'aiida-store',
    'profile-identity.json',
    'executor.json',
    'executor.lock',
    'evidence/release-binding',
)


def refuse_populated(root):
    present = [
        name
        for name in POPULATED_MARKERS
        if (Path(root) / name).exists() or (Path(root) / name).is_symlink()
    ]
    if present:
        raise ValueError(
            'Refusing prepare/extend of a populated execution root ('
            + ', '.join(present)
            + '); use the reviewed bind-launch-worker step instead'
        )


def bind_launch_worker(root, binding):
    """Replace only the launch-worker wrapper, retaining its previous bytes as evidence.

    Accepts the reviewed legacy wrapper or an earlier release wrapper for this root;
    anything else is refused unchanged. No profile, store, process or job is touched.
    """
    root = Path(root)
    wrapper = root / 'launch-worker'
    if any(p.is_symlink() for p in (root, wrapper, root / 'evidence')):
        raise ValueError('Unsafe launch-worker path')
    previous = wrapper.read_bytes()
    local_paths.require(PYTHON)
    legacy = (
        '#!/bin/sh\nexport AIIDA_PATH='
        + shlex.quote(str(root / 'aiida'))
        + '\nexec '
        + shlex.quote(str(PYTHON))
        + ' -B -m hyprn_mvp_integration.launcher "$@"\n'
    ).encode()
    released = re.fullmatch(
        rb'#!/bin/sh\nexport AIIDA_PATH='
        + re.escape(shlex.quote(str(root / 'aiida')).encode())
        + rb'\nexec '
        + re.escape(shlex.quote(str(PYTHON)).encode())
        + rb" -B (?:'[^'\n]+/source/deployment/release\.py'|"
        rb"[^\s'\"]+/source/deployment/release\.py) exec-module --expected-sha256 "
        rb'[0-9a-f]{64} hyprn_mvp_integration\.launcher -- \"\$@\"\n',
        previous,
    )
    if previous != legacy and not released:
        raise ValueError('Unexpected existing launch-worker; refusing replacement')
    retained = root / 'evidence' / ('launch-worker-' + sha(previous) + '.sh')
    if retained.exists():
        if retained.read_bytes() != previous:
            raise ValueError('Retained launch-worker evidence differs; refusing replacement')
    else:
        with retained.open('xb') as output:
            output.write(previous)
    text = write_launch_worker(root, binding)
    if wrapper.read_bytes() != text:
        raise ValueError('launch-worker replacement not observed')
    record = dict(
        previous_sha256=sha(previous),
        current_sha256=sha(text),
        release_id=binding.release_id,
        manifest_sha256=binding.manifest_sha256,
        source_root=str(binding.source),
        retained_previous=str(retained),
        bound_at=datetime.now(timezone.utc).isoformat(),
    )
    # Create-only, uniquely named evidence (never overwrites an earlier binding record).
    evidence = root / 'evidence' / ('launch-worker-binding-' + uuid4().hex + '.json')
    with evidence.open('x') as output:
        output.write(json.dumps(record, sort_keys=True, indent=2) + '\n')
    return dict(record, evidence=str(evidence))


def require_launch_worker(root, binding):
    """Refuse unless launch-worker is exactly this release's wrapper.

    The reviewed legacy wrapper runs `-m hyprn_mvp_integration.launcher`, which may resolve to
    another checkout through an interpreter's startup path hook; an earlier release's
    wrapper names another manifest. Either would execute source other than this release.
    """
    if binding is None or not binding.bound:
        raise ValueError('Selected release binding required for launch-worker')
    root = Path(root)
    wrapper = root / 'launch-worker'
    if any(p.is_symlink() for p in (root, wrapper)):
        raise ValueError('Unsafe launch-worker path')
    try:
        actual = wrapper.read_bytes()
    except FileNotFoundError:
        raise ValueError(
            'launch-worker missing; run the reviewed bind-launch-worker step'
        ) from None
    if actual != launch_worker_text(root, binding).encode():
        raise ValueError(
            'launch-worker is not bound to release '
            + str(binding.release_id)
            + ' (sha256 '
            + sha(actual)[:16]
            + '); stop, back up, then run the reviewed bind-launch-worker step of this release'
        )
    return dict(
        path=str(wrapper),
        sha256=sha(actual),
        release_id=binding.release_id,
        manifest_sha256=binding.manifest_sha256,
    )


def bind_step(root, binding):
    """Reviewed rebinding step: executor stopped, wrapper rebound, result re-verified.

    The stop is proven by the shared fail-closed quiescence gate (parsable executor.json,
    no live executor, executor.lock not held), not by executor.json alone."""
    import dispatch_runtime

    dispatch_runtime.executor_quiescence(root)
    record = bind_launch_worker(root, binding)
    require_launch_worker(root, binding)
    return record


def launcher_evidence(root, binding):
    """Post-activation check: the first launch through launch-worker proved this release."""
    directory = Path(root) / 'evidence/release-binding'
    if directory.is_symlink():
        raise ValueError('Unsafe launcher evidence directory')
    ours, others = [], 0
    for path in sorted(directory.glob('launcher-binding-*.json')) if directory.is_dir() else []:
        record = json.loads(path.read_text())
        if (record.get('release_id'), record.get('manifest_sha256'), record.get('source_root')) != (
            binding.release_id,
            binding.manifest_sha256,
            str(binding.source),
        ):
            others += 1
            continue
        module = record['modules']['hyprn_mvp_integration.launcher']
        launcher = Path(module['file'])
        if not launcher.is_relative_to(binding.source):
            raise ValueError('Launcher evidence names source outside the release')
        # The launched module bytes must be this release's manifest entry, not only its path.
        expected = binding.inventory.get('integration/src/hyprn_mvp_integration/launcher.py')
        if expected is None or module.get('sha256') != expected:
            raise ValueError(
                'Launcher evidence sha256 differs from the release manifest: ' + path.name
            )
        ours.append(str(path))
    if not ours:
        raise ValueError(
            'No launcher-binding evidence for release '
            + str(binding.release_id)
            + ' yet; run one launch, then recheck'
        )
    return dict(release_id=binding.release_id, records=ours, other_releases=others)


def reviewed_selection(source):
    source = Path(source)
    selected = json.loads((source / 'selected.json').read_bytes())
    for item in selected['files']:
        relative = Path(item['path'])
        if (
            relative.is_absolute()
            or '..' in relative.parts
            or relative.parts[0] not in ('locks', 'licenses')
        ):
            raise ValueError('Reviewed selection path refused')
        path = source / relative
        if any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError('Reviewed selection symlink refused')
        raw = path.read_bytes()
        if len(raw) != item['size'] or sha(raw) != item['sha256']:
            raise ValueError('Reviewed selection bytes changed')
    return selected


def reuse_reviewed():
    """Reuse only fixed audited interpreter/lock/license bytes; no old data."""
    if (ROOT / 'selected.json').exists() or (ROOT / 'aiida').exists():
        raise ValueError('Refusing existing selected runtime or native profile')
    selection = reviewed_selection(REVIEWED)
    previous = json.loads((REVIEWED / 'runtime.json').read_bytes())
    runtime = json.loads((ROOT / 'runtime.json').read_bytes())
    if (
        previous['selected_sha256'] != sha((REVIEWED / 'selected.json').read_bytes())
        or runtime['engine_image'] != previous['engine_image']
        or runtime['worker_lock_sha256'] != previous['worker_lock_sha256']
    ):
        raise ValueError('Reviewed runtime dependency identity changed')
    site = (
        Path(local_paths.require(PYTHON, local_paths.NATIVE_PYTHON)).parents[1]
        / 'lib/python3.12/site-packages'
    )
    for dist in json.loads((REVIEWED / 'locks/native-installed.json').read_bytes()):
        for item in dist['files']:
            raw = (site / item['path']).read_bytes()
            if sha(raw) != item['sha256'] or len(raw) != item['size']:
                raise ValueError('Reviewed native dependency bytes changed')
    for item in selection['files']:
        target = ROOT / item['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        raw = (REVIEWED / item['path']).read_bytes()
        if target.exists() and target.read_bytes() != raw:
            raise ValueError('New dependency selection mismatch')
        target.write_bytes(raw)
    (ROOT / 'selected.json').write_bytes((REVIEWED / 'selected.json').read_bytes())
    runtime['selected_sha256'] = sha((ROOT / 'selected.json').read_bytes())
    emit(ROOT / 'runtime.json', runtime)
    write_launch_worker(ROOT, BINDING)
    emit(
        ROOT / 'evidence/dependency-reuse.json',
        dict(
            interpreter=str(PYTHON),
            source=str(REVIEWED),
            selected_sha256=runtime['selected_sha256'],
            copied_scientific_records=False,
        ),
    )


def normalized(name):
    return re.sub(r'[-_.]+', '-', name).lower()


def locked_distributions(raw):
    """{name: version} of a hashed requirements lock. Every entry is one exact pin starting at
    the first column, followed by at least one SHA-256; anything else is refused."""
    pinned, current = {}, None
    for line in raw.decode().splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        if not line[0].isspace():
            match = re.match(
                r'([A-Za-z0-9][A-Za-z0-9._-]*)==([A-Za-z0-9.+!]+)(?: ;[^\\]*)? \\$', line
            )
            if match is None or normalized(match[1]) in pinned:
                raise ValueError(
                    'Native host lock entry is not one exact, hashed pin: ' + line[:80]
                )
            current = normalized(match[1])
            pinned[current] = [match[2], 0]
        elif current is not None and re.fullmatch(r' {4}--hash=sha256:[0-9a-f]{64}(?: \\)?', line):
            pinned[current][1] += 1
        else:
            raise ValueError('Native host lock line refused: ' + line[:80])
    if not pinned or any(hashes == 0 for _, hashes in pinned.values()):
        raise ValueError('Native host lock holds an entry without a hash')
    return {name: version for name, (version, _) in pinned.items()}


def safe_folder(path, name):
    """An existing absolute folder with no symlink in any component."""
    path = Path(path)
    if (
        not path.is_absolute()
        or any(p.is_symlink() for p in (path, *path.parents))
        or not path.is_dir()
    ):
        raise ValueError(
            name + ' must be an existing absolute folder without a symlink: ' + str(path)
        )
    return path


def snapshot_file(source, relative):
    path = source / relative
    if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file():
        raise ValueError('Release snapshot file missing or linked: ' + relative)
    return path


def run(command, env, what):
    """Run one tool command; a failure names the step and the tail of its output."""
    result = subprocess.run(
        [str(part) for part in command], env=env, capture_output=True, text=True
    )
    if result.returncode:
        output = (result.stdout + '\n' + result.stderr).strip()
        raise ValueError(what + ' failed: ' + output[-3000:])
    return result.stdout


def hermetic(tools, cache, **extra):
    """Process environment of uv and the pinned interpreter: no ambient uv or Python setting,
    the tool cache's interpreters, the given package cache, no interpreter download."""
    env = {
        k: v
        for k, v in os.environ.items()
        if not (k.startswith('UV_') and k not in UV_KEPT)
        and not k.startswith('PYTHON')
        and k not in ('VIRTUAL_ENV', 'CONDA_PREFIX', 'PIP_REQUIRE_VIRTUALENV')
    }
    env.update(
        UV_NO_CONFIG='1',
        UV_PYTHON_PREFERENCE='only-managed',
        UV_PYTHON_DOWNLOADS='never',
        UV_PYTHON_INSTALL_DIR=str(tools / 'python'),
        UV_CACHE_DIR=str(cache),
        UV_NO_PROGRESS='1',
        PYTHONDONTWRITEBYTECODE='1',
        **extra,
    )
    return env


def platform_key(pins):
    uname = os.uname()
    key = PLATFORMS.get((uname.sysname.lower(), uname.machine))
    if key is None or key not in pins['uv_archives']:
        raise ValueError(
            'Unsupported host for the native environment: ' + uname.sysname + ' ' + uname.machine
        )
    return key


def pinned_toolchain(tools, pins, env):
    """The tool cache's uv and uv-managed CPython, each checked against tools.json."""
    uv = tools / 'uv' / pins['uv_version'] / platform_key(pins) / 'uv'
    if not uv.is_file() or run([uv, '--version'], env, 'uv').split(' ')[:2] != [
        'uv',
        pins['uv_version'],
    ]:
        raise ValueError('uv ' + pins['uv_version'] + ' is not in the tool cache; run ./hyprn-mvp')
    found = run(
        [
            uv,
            'python',
            'find',
            '--no-python-downloads',
            '--no-project',
            pins['cpython_version'],
        ],
        env,
        'Pinned CPython lookup',
    ).strip()
    probe = 'import sys;print("%d.%d.%d" % sys.version_info[:3]);print(sys.base_prefix)'
    version, prefix = run([found, '-I', '-B', '-c', probe], env, 'Pinned CPython').split('\n')[:2]
    try:
        build = (Path(prefix) / 'BUILD').read_text().strip()
    except OSError:
        build = None
    if version != pins['cpython_version'] or build != pins['cpython_build']:
        raise ValueError(
            'The tool cache interpreter is not CPython '
            + pins['cpython_version']
            + ' build '
            + pins['cpython_build']
            + ': '
            + found
        )
    return uv, Path(found)


def acquire_backend(backend, folder):
    """The build backend's wheel, fetched from its pinned URL and verified by size and SHA-256
    before any use. Acquisition is the only network step of a build."""
    wheel = backend['wheel']
    if not wheel['url'].startswith('https://') or Path(wheel['filename']).name != wheel['filename']:
        raise ValueError('Build backend lock refused')
    with urllib.request.urlopen(wheel['url'], timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
        raw = response.read(wheel['size'] + 1)
    if len(raw) != wheel['size'] or sha(raw) != wheel['sha256']:
        raise ValueError('Build backend artifact differs from its pin: ' + wheel['filename'])
    folder.mkdir(mode=0o700)
    (folder / wheel['filename']).write_bytes(raw)
    return folder


def project_identity(source, folder, backend):
    """Distribution name and version of one snapshot package whose build system is exactly the
    pinned backend."""
    project = tomllib.loads(snapshot_file(source, folder + '/pyproject.toml').read_text())
    expected = {'requires': [backend['requirement']], 'build-backend': backend['build_backend']}
    if project.get('build-system') != expected:
        raise ValueError(
            folder
            + '/pyproject.toml does not build with the pinned backend '
            + backend['requirement']
        )
    return normalized(project['project']['name']), project['project']['version']


def stage_package(source, folder, work):
    """Copy one snapshot package (Python and owned SQL migrations) into the build
    folder: the build never writes into the release and sees no other file. Any other file
    under src/ is refused rather than left out of the wheel."""
    package = source / folder
    target = work / folder
    files = [snapshot_file(source, folder + '/pyproject.toml')]
    for path in sorted((package / 'src').rglob('*')):
        relative = path.relative_to(package)
        if path.is_symlink():
            raise ValueError('Release snapshot file linked: ' + str(relative))
        if '__pycache__' in relative.parts or path.is_dir():
            continue
        migration = (folder == 'application'
                     and relative.parent == Path('src/hyprn_mvp_app/migrations')
                     and re.fullmatch(r'[0-9]{4}_[a-z0-9_]+\.sql', path.name))
        if path.suffix != '.py' and not migration:
            raise ValueError(
                'Package file the wheel would not carry: ' + folder + '/' + str(relative)
            )
        files.append(path)
    for path in files:
        destination = target / path.relative_to(package)
        destination.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        destination.write_bytes(path.read_bytes())
        destination.chmod(0o644)
    return target


def installed(site):
    """{normalized name: distribution} of one site-packages folder, read as data only."""
    found = {}
    for dist in metadata.distributions(path=[str(site)]):
        name = normalized(dist.metadata['Name'])
        if name in found:
            raise ValueError('Two installed distributions are named ' + name)
        found[name] = dist
    return found


def verified_files(dist):
    """Every installed file of a distribution with its RECORD hash re-checked. Console wrappers
    outside site-packages, bytecode and RECORD itself are generated, not package content."""
    records = []
    for entry in dist.files or []:
        relative = str(entry)
        if relative.startswith('../') or relative.endswith('.pyc') or relative.endswith('/RECORD'):
            continue
        if entry.hash is None or entry.hash.mode != 'sha256':
            raise ValueError('Unhashed installed artifact: ' + relative)
        raw = Path(dist.locate_file(entry)).read_bytes()
        if (
            base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).decode().rstrip('=')
            != entry.hash.value
        ):
            raise ValueError('Installed artifact differs from its RECORD: ' + relative)
        records.append((relative, raw))
    return records


def check_environment(site, source, expected, projects):
    """Refuse an environment that differs from its locks: exactly the expected distributions,
    no startup path file, no install-origin record, every RECORD hash verified, and the
    project modules byte-identical to the snapshot's sources."""
    distributions = installed(site)
    actual = {name: dist.version for name, dist in distributions.items()}
    if actual != expected:
        extra = sorted(f'{n}=={v}' for n, v in actual.items() if expected.get(n) != v)
        missing = sorted(f'{n}=={v}' for n, v in expected.items() if actual.get(n) != v)
        raise ValueError(
            'Native environment differs from its locks (unexpected: '
            + (', '.join(extra) or 'none')
            + '; missing: '
            + (', '.join(missing) or 'none')
            + ')'
        )
    startup = sorted(p.name for p in site.glob('*.pth'))
    if startup:
        raise ValueError('Native environment holds a startup path file: ' + ', '.join(startup))
    for name, folder in projects.items():
        sources = {
            str(p.relative_to(source / folder / 'src')): p.read_bytes()
            for p in (source / folder / 'src').rglob('*')
            if p.is_file() and '__pycache__' not in p.parts and
            (p.suffix == '.py' or (folder == 'application'
             and p.parent == source / folder / 'src/hyprn_mvp_app/migrations'
             and re.fullmatch(r'[0-9]{4}_[a-z0-9_]+\.sql', p.name)))
        }
        modules = {}
        for relative, raw in verified_files(distributions[name]):
            if relative.endswith('/direct_url.json'):
                raise ValueError('Project wheel installed with an origin record: ' + relative)
            if '.dist-info/' not in relative:
                modules[relative] = raw
        if modules != sources:
            raise ValueError('Installed ' + name + ' modules differ from the release snapshot')
    return distributions


def prepare(root, source, *, tools, cache):
    """Build the native host environment of ``root`` from the release snapshot ``source``.

    Refused before any effect on a populated root or a root already prepared for any lock.
    A failure removes what this call created; nothing is ever replaced."""
    refuse_populated(root)  # before any read or write
    root, source = safe_folder(root, 'Execution root'), safe_folder(source, 'Release snapshot')
    tools, cache = safe_folder(tools, 'Tool cache'), Path(cache)
    lock_raw = snapshot_file(source, NATIVE_HOST_LOCK).read_bytes()
    environment = root / (ENVIRONMENT_PREFIX + sha(lock_raw)[:16])
    prepared = [p.name for p in root.glob(ENVIRONMENT_PREFIX + '*')]
    prepared += [n for n in (INSTALLED_INVENTORY, NATIVE_LICENSES) if (root / n).exists()]
    if prepared:
        raise ValueError(
            'Native environment already prepared ('
            + ', '.join(sorted(prepared))
            + '); refusing replacement'
        )
    third_party = locked_distributions(lock_raw)
    backend = json.loads(snapshot_file(source, BUILD_BACKEND_LOCK).read_bytes())
    pins = json.loads(snapshot_file(source, TOOLS_LOCK).read_bytes())
    projects = {}
    for folder in PROJECT_FOLDERS:
        name, version = project_identity(source, folder, backend)
        if name in third_party or name in projects:
            raise ValueError('Project distribution name collides with a locked one: ' + name)
        projects[name] = (folder, version)
    env = hermetic(tools, cache)
    uv, python = pinned_toolchain(tools, pins, env)
    work = root / ('.native-build-' + uuid4().hex)
    created = []
    work.mkdir(mode=0o700)
    try:
        backend_folder = acquire_backend(backend, work / 'backend')
        constraints = work / 'build-constraints.txt'
        constraints.write_text(
            backend['requirement'] + ' --hash=sha256:' + backend['wheel']['sha256'] + '\n'
        )
        wheels = work / 'wheels'
        build_env = hermetic(tools, cache, SOURCE_DATE_EPOCH=SOURCE_DATE_EPOCH)
        for name, (folder, version) in projects.items():
            staged = stage_package(source, folder, work / 'build')
            run(
                [
                    uv,
                    'build',
                    '--wheel',
                    '--offline',
                    '--no-index',
                    '--find-links',
                    backend_folder,
                    '--build-constraints',
                    constraints,
                    '--require-hashes',
                    '--python',
                    python,
                    '--no-create-gitignore',
                    '--out-dir',
                    wheels,
                    staged,
                ],
                build_env,
                'Wheel build of ' + name,
            )
        built = {}
        for name, (folder, version) in projects.items():
            wheel = wheels / (name.replace('-', '_') + '-' + version + '-py3-none-any.whl')
            if not wheel.is_file():
                raise ValueError('Wheel build of ' + name + ' produced no ' + wheel.name)
            built[name] = sha(wheel.read_bytes())
        if sorted(p.name for p in wheels.iterdir()) != sorted(
            name.replace('-', '_') + '-' + version + '-py3-none-any.whl'
            for name, (_, version) in projects.items()
        ):
            raise ValueError('Wheel builds produced unexpected files')
        requirements = work / 'project-wheels.txt'
        requirements.write_text(
            ''.join(
                name + '==' + projects[name][1] + ' --hash=sha256:' + digest + '\n'
                for name, digest in sorted(built.items())
            )
        )
        created.append(environment)
        run(
            [python, '-I', '-B', '-m', 'venv', '--without-pip', environment],
            env,
            'Environment creation',
        )
        target = environment / 'bin/python'
        run(
            [
                uv,
                'pip',
                'sync',
                '--python',
                target,
                '--require-hashes',
                '--no-build',
                '--strict',
                '--link-mode',
                'copy',
                '--quiet',
                source / NATIVE_HOST_LOCK,
            ],
            env,
            'Locked dependency install',
        )
        run(
            [
                uv,
                'pip',
                'install',
                '--python',
                target,
                '--no-deps',
                '--require-hashes',
                '--offline',
                '--no-index',
                '--find-links',
                wheels,
                '--link-mode',
                'copy',
                '--quiet',
                '-r',
                requirements,
            ],
            env,
            'Project wheel install',
        )
        series = '.'.join(pins['cpython_version'].split('.')[:2])
        site = environment / 'lib' / ('python' + series) / 'site-packages'
        expected = {**third_party, **{name: version for name, (_, version) in projects.items()}}
        distributions = check_environment(
            site, source, expected, {n: f for n, (f, _) in projects.items()}
        )
        inventory, licenses = [], {}
        for name in sorted(third_party):
            dist = distributions[name]
            records = []
            for relative, raw in verified_files(dist):
                records.append(dict(path=relative, sha256=sha(raw), size=len(raw)))
                lowered = relative.lower()
                if '.dist-info/' in relative and (
                    Path(relative).name == 'METADATA'
                    or any(word in lowered for word in ('license', 'copying', 'notice'))
                ):
                    licenses[NATIVE_LICENSES + '/' + relative] = raw
            inventory.append(
                dict(
                    name=name,
                    version=dist.version,
                    origin=dist.metadata.get_all('Project-URL') or [],
                    license=dist.metadata.get('License-Expression')
                    or dist.metadata.get('License')
                    or dist.metadata.get_all('Classifier'),
                    files=records,
                )
            )
        for folder in ('locks', 'licenses', 'evidence'):
            (root / folder).mkdir(mode=0o700, exist_ok=True)
        created.append(root / NATIVE_LICENSES)
        for relative, raw in licenses.items():
            target_file = root / relative
            target_file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            target_file.write_bytes(raw)
        record = dict(
            environment=environment.name,
            native_host_lock_sha256=sha(lock_raw),
            python=dict(version=pins['cpython_version'], build=pins['cpython_build']),
            build_backend=dict(
                name=backend['name'], version=backend['version'], sha256=backend['wheel']['sha256']
            ),
            project_wheels=built,
            distributions=len(expected),
            prepared_at=datetime.now(timezone.utc).isoformat(),
        )
        created.append(root / ENVIRONMENT_EVIDENCE)
        emit(root / ENVIRONMENT_EVIDENCE, record)
        created.append(root / INSTALLED_INVENTORY)
        emit(root / INSTALLED_INVENTORY, inventory)
    except BaseException:
        for path in reversed(created):
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            elif path.exists():
                path.unlink()
        raise
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return record


def extend(root, binding):
    """Add the restricted worker's distribution inventory and licence texts to a prepared root,
    select the runtime inventory and bind the launch wrapper. Runs once the worker is built
    (runtime.json names its image); the worker metadata is read in that image with network
    disabled and imports no candidate code."""
    refuse_populated(root)  # before any read or write
    root = Path(root)
    if not (root / INSTALLED_INVENTORY).is_file():
        raise ValueError('Native environment not prepared; run prepare first')
    inventory = json.loads((root / INSTALLED_INVENTORY).read_bytes())
    runtime = json.loads((root / 'runtime.json').read_bytes())
    workers = export_worker_inventory(root, runtime['worker_image'],
                                      environment=local_paths.docker_environment())
    select_inventory(root)
    runtime['selected_sha256'] = sha((root / 'selected.json').read_bytes())
    emit(root / 'runtime.json', runtime)
    # The same wrapper (reviewed interpreter) that require_launch_worker accepts.
    write_launch_worker(root, binding)
    summary = dict(
        native_distributions=len(inventory),
        worker_distributions=len(workers),
        selected_sha256=runtime['selected_sha256'],
    )
    print(json.dumps(summary))
    return summary


def export_worker_inventory(root, worker_image, *, environment=None):
    """Export only exact worker dependency notices; no profile or launch binding."""
    root = safe_folder(root, 'Worker inventory output')
    if root.stat().st_uid != os.getuid() or root.stat().st_mode & 0o077:
        raise ValueError('Worker inventory output must be private and owned')
    if not isinstance(worker_image, str) or not re.fullmatch(r'sha256:[0-9a-f]{64}', worker_image):
        raise ValueError('Exact worker image identity required')
    for relative in ('licenses/worker', 'locks/worker-installed.json'):
        path = root / relative
        if any(p.is_symlink() for p in (path, *path.parents)) or path.exists():
            raise ValueError('Worker inventory output exists or is linked')
    script = (
        'import base64, importlib.metadata as m, json\n'
        'out = []\n'
        'for d in m.distributions():\n'
        '    files = {}\n'
        '    for f in d.files or []:\n'
        '        s = str(f)\n'
        "        named = ('/METADATA', 'license', 'copying', 'notice')\n"
        "        if '.dist-info/' in s and any(x in s.lower() or s.endswith(x) for x in named):\n"
        '            files[s] = base64.b64encode(d.locate_file(f).read_bytes()).decode()\n'
        "    out.append({'name': d.metadata['Name'], 'version': d.version, 'files': files})\n"
        'print(json.dumps(out))\n'
    )
    output = subprocess.run(
        [
            'docker',
            'run',
            '--rm',
            '--network=none',
            '--read-only',
            '--cap-drop=ALL',
            '--security-opt=no-new-privileges',
            worker_image,
            'python',
            '-B',
            '-c',
            script,
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
        env=environment,
    ).stdout
    return store_worker_inventory(root, json.loads(output))


def store_worker_inventory(root, workers):
    """Validate all image-reported paths and bytes before writing the owned inventory."""
    root = safe_folder(root, 'Worker inventory output')
    if root.stat().st_uid != os.getuid() or root.stat().st_mode & 0o077:
        raise ValueError('Worker inventory output must be private and owned')
    for relative in ('licenses/worker', 'locks/worker-installed.json'):
        target = root / relative
        if any(p.is_symlink() for p in (target, *target.parents)) or target.exists():
            raise ValueError('Worker inventory output exists or is linked')
    if not isinstance(workers, list) or not workers or len(workers) > 1000:
        raise ValueError('Invalid worker distribution inventory')
    inventory, files, names = [], {}, set()
    for distribution in workers:
        if (not isinstance(distribution, dict) or set(distribution) != {'name', 'version', 'files'}
                or not isinstance(distribution['name'], str) or not distribution['name']
                or not isinstance(distribution['version'], str) or not distribution['version']
                or not isinstance(distribution['files'], dict)):
            raise ValueError('Invalid worker distribution')
        name = normalized(distribution['name'])
        if name in names:
            raise ValueError('Duplicate worker distribution')
        names.add(name)
        inventory.append({key: distribution[key] for key in ('name', 'version')})
        for relative, encoded in distribution['files'].items():
            if not isinstance(relative, str):
                raise ValueError('Unsafe worker notice path')
            path = Path(relative)
            if (path.is_absolute() or '..' in path.parts
                    or '\\' in relative or len(path.parts) < 2 or not path.parts[0].endswith('.dist-info')
                    or path.as_posix() != relative or relative in files
                    or not isinstance(encoded, str)):
                raise ValueError('Unsafe worker notice path')
            raw = base64.b64decode(encoded, validate=True)
            if len(raw) > 4 * 1024 * 1024:
                raise ValueError('Worker notice too large')
            files[relative] = raw
    if not files or sum(map(len, files.values())) > 32 * 1024 * 1024:
        raise ValueError('Worker notices missing or too large')
    for relative, raw in files.items():
        path = root / 'licenses/worker' / relative
        path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        path.write_bytes(raw)
    (root / 'locks').mkdir(mode=0o700, exist_ok=True)
    emit(root / 'locks/worker-installed.json', inventory)
    return inventory


def select_inventory(root):
    """Select verified native and worker inventories for a packaged or mutable root."""
    root = Path(root)
    inventory = json.loads((root / INSTALLED_INVENTORY).read_bytes())
    workers = json.loads((root / 'locks/worker-installed.json').read_bytes())
    dependencies = [
        dict(name=d['name'], version=d['version'], lock_path=INSTALLED_INVENTORY) for d in inventory
    ]
    dependencies += [
        dict(name=d['name'], version=d['version'], lock_path='locks/worker-installed.json')
        for d in workers
    ]
    descriptors = []
    for top in ('locks', 'licenses'):
        for path in sorted((root / top).rglob('*')):
            if path.is_file():
                descriptors.append(
                    dict(
                        path=str(path.relative_to(root)),
                        size=path.stat().st_size,
                        sha256=sha(path.read_bytes()),
                    )
                )
    licenses = [d['path'] for d in descriptors if d['path'].startswith('licenses/')]
    emit(
        root / 'selected.json',
        dict(dependencies=dependencies, files=descriptors, licenses=licenses),
    )
    return sha((root / 'selected.json').read_bytes())


def profile_name():
    """The native profile of the execution store as the attested launcher names it: the
    installation's own profile, or the development store's."""
    from hyprn_mvp_integration import launcher

    return launcher.PROFILE


def initialize(root, configuration):
    """Create the native profile of an installation (``hyprn-mvp-<edition>-<id8>``; the
    development store's own name without one) in an empty ``<root>/aiida``: a core.sqlite_dos
    store, no broker, no default profile, the local computer and the launch-worker code."""
    from hyprn_mvp_integration import installation

    root = Path(root)
    profile = installation.profile_name(configuration)
    if os.environ.get('AIIDA_PATH') != str(root / 'aiida'):
        raise ValueError('Explicit new profile path required')
    import aiida
    from aiida import orm
    from aiida.manage.configuration import get_config, create_profile

    config = get_config(create=True)
    if config.profile_names:
        raise ValueError('Refusing to initialize existing profile')
    create_profile(
        config,
        name=profile,
        email='owner@hyprn-mvp.invalid',
        storage_backend='core.sqlite_dos',
        storage_config={'filepath': str(root / 'aiida-store')},
        broker_backend=None,
        broker_config={},
    )
    config.store()
    if config.default_profile_name is not None:
        raise ValueError('Default profile is forbidden')
    aiida.load_profile(profile)
    computer = orm.Computer(
        label='hyprn-mvp-local',
        hostname='localhost',
        transport_type='core.local',
        scheduler_type='core.direct',
        workdir=str(root / 'aiida-work/{username}'),
    ).store()
    computer.configure(safe_interval=0.1)
    code = orm.InstalledCode(
        label='hyprn-mvp-scalar',
        computer=computer,
        filepath_executable=str(root / 'launch-worker'),
        default_calc_job_plugin='hyprn_mvp.scalar',
    ).store()
    from aiida.manage import get_manager

    emit(
        root / 'profile-identity.json',
        dict(
            profile_uuid=config.get_profile(profile).uuid,
            repository_uuid=get_manager().get_profile_storage().get_repository().uuid,
            computer_uuid=computer.uuid,
            code_uuid=code.uuid,
            profile=profile,
        ),
    )
    print('Fresh isolated profile initialized without broker or daemon')
    return profile


def evidence():
    profile = profile_name()
    from aiida import orm
    from hyprn_mvp_integration.calculation import NativeExecution

    native = NativeExecution.from_environment()
    records = []
    for (node,) in (
        orm.QueryBuilder()
        .append(
            orm.CalcJobNode,
            filters={'process_type': 'aiida.calculations:hyprn_mvp.scalar'},
            project='*',
        )
        .all()
    ):
        bundle = native.retained_bundle(node.uuid)
        request = node.inputs.request.get_dict()
        records.append(
            dict(
                request=request,
                record=native.inspect(node.uuid),
                model_revision_id=bundle['manifest']['model_revision_id'],
                configuration_revision_id=bundle['manifest']['configuration_revision_id'],
                file_count=len(bundle['files']),
                retained_manifest_digest=bundle['manifest']['bundle_digest'],
                retained_exact_match=native.matches(request) == [node.uuid],
            )
        )
    emit(
        ROOT / 'evidence/native-records.json',
        dict(profile=profile, store_uuid=native.store_uuid, records=records),
    )
    print(
        json.dumps(
            dict(
                records=len(records), unique_matches=all(r['retained_exact_match'] for r in records)
            )
        )
    )


if __name__ == '__main__':
    import release as release_binding

    # check-* are read-only; every other operation has effects. None may run from an
    # unselected checkout (the expected wrapper names the selected release).
    read_only = sys.argv[1:] in (['check-launch-worker'], ['check-launcher-evidence'])
    BINDING = release_binding.entrypoint(__file__, read_only=read_only, project_imports=True)
    local_paths.require(ROOT)
    if sys.argv[1:] == ['bind-launch-worker']:
        print(json.dumps(bind_step(ROOT, BINDING)))
    elif sys.argv[1:] == ['check-launch-worker']:
        print(json.dumps(require_launch_worker(ROOT, BINDING)))
    elif sys.argv[1:] == ['check-launcher-evidence']:
        print(json.dumps(launcher_evidence(ROOT, BINDING)))
    elif sys.argv[1:] == ['reuse-reviewed']:
        reuse_reviewed()
    elif sys.argv[1:] == ['prepare']:
        # The selected release's snapshot is the source; the tool cache's uv cache holds downloads.
        tools = local_paths.tools_root()
        print(json.dumps(prepare(ROOT, BINDING.source, tools=tools, cache=tools / 'uv-cache')))
    elif sys.argv[1:] == ['extend']:
        extend(ROOT, BINDING)
    elif sys.argv[1:] == ['initialize']:
        from hyprn_mvp_integration import launcher

        initialize(ROOT, launcher.INSTALLATION)
    elif sys.argv[1:] == ['evidence']:
        evidence()
    else:
        raise ValueError('Choose prepare or initialize')
