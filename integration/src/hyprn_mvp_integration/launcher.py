"""Trusted bounded container launcher. No candidate import or native model code.

The independent Plan01-01 selector/drain/cleanup pattern is reused with new owned
paths and identities. In particular close and wait for the attached Docker client
before killing an output-flooding container, or daemon cleanup can deadlock.
"""

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import platform
import selectors
import subprocess
import tempfile
import time
from uuid import uuid4
from uuid import UUID
from hyprn_mvp_app.contracts import DomainError, canonical, check_digest, data_json, digest
from hyprn_mvp_app.execution_bundle import safe_path, verify_files, validate_retained_bundle
from hyprn_mvp_app.contracts import (
    EXECUTION_WALL_DEFAULT,
    EXECUTION_WALL_MAX,
    execution_wall_seconds,
)
from . import installation
from . import exploration


def configured_installation():
    """The installation configuration (HYPRN_MVP_CONFIG, read by the attested loader) when no
    development data root is set. HYPRN_MVP_DATA_ROOT, documented in deployment/local_paths.py,
    comes first as in every location's resolution order (this attested module reads it directly
    and imports no deployment code); None for the development data root and while both are unset.
    """
    if os.environ.get('HYPRN_MVP_DATA_ROOT', ''):
        return None
    return installation.from_environment()


def configured_root(configured=None):
    """Execution store: <data root>/execution, the data root being HYPRN_MVP_DATA_ROOT or the
    installation's. None while neither is set: runtime_root() then refuses the store; explicit
    fixture roots are unaffected."""
    value = os.environ.get('HYPRN_MVP_DATA_ROOT', '')
    if not value:
        return None if configured is None else Path(configured['data_root']) / 'execution'
    root = Path(value)
    if not root.is_absolute() or '..' in root.parts:
        raise ValueError('HYPRN_MVP_DATA_ROOT must be an absolute normalized path')
    return root / 'execution'


def scratch_root():
    """Folder of scoped test roots: HYPRN_MVP_SCRATCH_ROOT, else the real temporary folder
    (read the same way as deployment/local_paths.py)."""
    value = os.environ.get('HYPRN_MVP_SCRATCH_ROOT', '')
    return Path(value) if value else Path(os.path.realpath(tempfile.gettempdir()))


SCOPE_PREFIX = 'hyprn-mvp-test-'

INSTALLATION = configured_installation()
ROOT = configured_root(INSTALLATION)
# Runtime owner (runtime.json, worker container label), native profile and container engine
# endpoint of the execution store: the installation's, or the development store's fixed ones
# with the ambient engine. The worker policy below is source, never configuration.
OWNER = installation.owner(INSTALLATION)
PROFILE = installation.profile_name(INSTALLATION)
DOCKER_ENDPOINT = None if INSTALLATION is None else INSTALLATION['docker']['endpoint']
POLICY = dict(
    memory='256m',
    cpus='0.5',
    pids='32',
    wall_seconds=EXECUTION_WALL_DEFAULT,
    max_wall_seconds=EXECUTION_WALL_MAX,
    output_bytes=65536,
    scratch_bytes=16777216,
    user='65534:65534',
    file_bytes=1048576,
)


def fixture_runtime_root(value):
    """Trusted local fixture selection only; never a public/candidate input."""
    root = Path(value)
    if (
        not root.is_absolute()
        or root.parent != scratch_root()
        or '..' in root.parts
        or not root.name.startswith(SCOPE_PREFIX)
        or root.resolve() != root
        or any(p.is_symlink() for p in (root, *root.parents))
    ):
        raise ValueError('Explicit isolated runtime root required')
    suffix = root.name.removeprefix(SCOPE_PREFIX)
    if str(UUID(suffix)) != suffix:
        raise ValueError('Invalid runtime root identity')
    marker = root / 'scope.json'
    if marker.is_symlink():
        raise ValueError('Unsafe runtime marker')
    record = json.loads(marker.read_bytes())
    if (
        record['root'] != str(root)
        or record['run_uuid'] != suffix
        or record['profile'] != SCOPE_PREFIX + suffix
        or record['backend'] != 'core.sqlite_dos'
        or len({suffix, record['profile_uuid'], record['store_uuid']}) != 3
    ):
        raise ValueError('Runtime scope mismatch')
    for key in ('profile_uuid', 'store_uuid'):
        if str(UUID(record[key])) != record[key]:
            raise ValueError('Invalid runtime identity')
    for name in (
        'evidence',
        'runtime.json',
        'selected.json',
        'launch-worker',
        'aiida',
        'native',
        'tmp',
        'home',
        'locks',
        'licenses',
        'canaries',
        'artifacts',
    ):
        path = root / name
        if path.is_symlink():
            raise ValueError('Unsafe runtime path')
    config = root / 'aiida/.aiida/config.json'
    if any(p.is_symlink() for p in (config, config.parent)):
        raise ValueError('Unsafe native config')
    if config.exists():
        native = json.loads(config.read_bytes())
        profile = native.get('profiles', {}).get(record['profile'], {})
        if (
            native.get('default_profile') is not None
            or set(native.get('profiles', {})) != {record['profile']}
            or profile.get('PROFILE_UUID')
            not in (record['profile_uuid'], UUID(record['profile_uuid']).hex)
            or profile.get('storage')
            != {'backend': 'core.sqlite_dos', 'config': {'filepath': str(root / 'native')}}
        ):
            raise ValueError('Runtime native profile mismatch')
        repository = root / 'native/container/config.json'
        if repository.is_symlink() or repository.parent.is_symlink():
            raise ValueError('Unsafe native repository')
        actual = json.loads(repository.read_bytes())['container_id']
        if actual not in (record['store_uuid'], UUID(record['store_uuid']).hex):
            raise ValueError('Runtime repository mismatch')
    return root


def runtime_root(value=None):
    if value is None and ROOT is None:
        raise ValueError('HYPRN_MVP_DATA_ROOT is not set: the execution store is unknown')
    return ROOT if value is None or value == ROOT else fixture_runtime_root(value)


def docker_environment():
    """Process environment of docker commands: the installation's engine endpoint when one is
    configured; otherwise the inherited environment (None)."""
    return None if DOCKER_ENDPOINT is None else {**os.environ, 'DOCKER_HOST': DOCKER_ENDPOINT}


def command(args, timeout=30):
    result = subprocess.run(
        args, capture_output=True, text=True, timeout=timeout, env=docker_environment()
    )
    if result.returncode:
        raise RuntimeError('Owned runtime command failed: ' + result.stderr[:1500])
    return result.stdout.strip()


def execution_configuration(root=None):
    """The configuration that matters for containment, recorded as a digest in runtime.json
    when the worker is built and compared at every use: data root, native profile and container
    engine endpoint. A scoped fixture root is its own data root and profile."""
    root = runtime_root(root)
    endpoint = (
        DOCKER_ENDPOINT if DOCKER_ENDPOINT is not None else (os.environ.get('DOCKER_HOST') or None)
    )
    if root == ROOT:
        return dict(data_root=str(root.parent), aiida_profile=PROFILE, docker_endpoint=endpoint)
    return dict(data_root=str(root), aiida_profile=root.name, docker_endpoint=endpoint)


def execution_configuration_sha256(root=None):
    return hashlib.sha256(canonical(execution_configuration(root=root))).hexdigest()


def identity(root=None):
    root = runtime_root(root)
    value = json.loads((root / 'runtime.json').read_bytes())
    owner = OWNER if root == ROOT else root.name
    if value.get('owner') != owner or value.get('root') != str(root):
        raise RuntimeError('Unknown execution runtime')
    if value.get('execution_configuration_sha256') != execution_configuration_sha256(root=root):
        raise RuntimeError(
            'Execution configuration changed (data root, native profile or container engine); '
            'rebuild and re-attest'
        )
    return value


def execution_source_hashes():
    """Trusted local qualification inputs; never paths supplied by a bundle/runtime.

    Preserve offline retained execution: this reads source bytes only, without a
    modeling service, current model lookup, candidate import or numerical engine.
    Native inputs mirror modeling_runtime.source_hashes; execution admission adds
    the actual independent validators and their local contract dependencies.

    Reviewed literal; never computed: the project modules are exactly the
    static import closure of launcher, calculation, results and worker, package
    __init__ files included (application/tests/test_module_boundaries.py enforces
    equality). Persistence/orchestration modules are bound by the application
    runtime and per-launch release verification instead.
    """
    repo = Path(__file__).resolve().parents[3]
    paths = [
        'integration/src/hyprn_mvp_integration/__init__.py',
        'integration/src/hyprn_mvp_integration/launcher.py',
        'integration/src/hyprn_mvp_integration/worker.py',
        'integration/src/hyprn_mvp_integration/exploration.py',
        'integration/src/hyprn_mvp_integration/results.py',
        'integration/src/hyprn_mvp_integration/calculation.py',
        'integration/src/hyprn_mvp_integration/computational_export.py',
        'integration/src/hyprn_mvp_integration/installation.py',
        'application/src/hyprn_mvp_app/__init__.py',
        'application/src/hyprn_mvp_app/locations.py',
        'application/src/hyprn_mvp_app/scientific_configuration.py',
        'application/src/hyprn_mvp_app/units.py',
        'application/src/hyprn_mvp_app/approach_closure.py',
        'application/src/hyprn_mvp_app/contracts.py',
        'application/src/hyprn_mvp_app/execution_bundle.py',
        'deployment/execution_runtime.py',
        'deployment/worker.Dockerfile',
        'deployment/images/engine.Dockerfile',
        'deployment/images/install_python.py',
        'deployment/images/build_engine.py',
        'deployment/locks/tools.json',
        'deployment/locks/engine-sources.json',
        'deployment/locks/build-backend.json',
        'upstream/engine-packaging/openmdao_extensions.patch',
        'upstream/engine-packaging/wop.patch',
        'upstream/engine-packaging/xdsmjs.patch',
        'deployment/pins.json',
        'deployment/images/whatsopt-source.Dockerfile',
        'deployment/locks/upstream.json',
        'deployment/locks/whatsopt-gems.json',
        'deployment/modeling.Dockerfile',
        'deployment/modeling_policy.rb',
        'deployment/modeling-compose.yaml',
        'deployment/modeling_runtime.py',
        'modeling/provenance.md',
        'modeling/generate_unit_catalog.py',
        'modeling/rehearsal.py',
        'contracts/schemas/model.schema.json',
        'contracts/schemas/execution.schema.json',
        'integration/worker-requirements.lock',
    ]
    paths += sorted(
        str(p.relative_to(repo)) for p in (repo / 'upstream/whatsopt-patches').glob('*.patch')
    )
    result = {}
    try:
        for relative in sorted(paths):
            path = repo / relative
            if any(p.is_symlink() for p in (path, *path.parents)):
                raise RuntimeError('Unsafe execution source path')
            result[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        raise RuntimeError('Missing execution source; rebuild before attesting') from error
    return result


def fingerprint(root=None):
    root = runtime_root(root)
    current = identity(root=root)
    if current.get('source_hashes') != execution_source_hashes():
        raise RuntimeError('Execution source inventory drift; rebuild before attesting')
    image = json.loads(command(['docker', 'image', 'inspect', current['worker_image']]))[0]
    if image['Id'] != current['worker_image']:
        raise RuntimeError('Worker image mismatch')
    worker = Path(__file__).with_name('worker.py')
    worker_sha = hashlib.sha256(worker.read_bytes()).hexdigest()
    if current.get('results_sha256') != hashlib.sha256(
        worker.with_name('results.py').read_bytes()
    ).hexdigest() or image['Config']['Labels'].get('org.hyprn-mvp.results_sha256') != current.get(
        'results_sha256'
    ):
        raise RuntimeError(
            'Result evaluator source/image binding mismatch; rebuild before attesting'
        )
    if (
        current['worker_sha256'] != worker_sha
        or image['Config']['Labels'].get('org.hyprn-mvp.worker_sha256') != worker_sha
    ):
        raise RuntimeError('Worker source/image binding mismatch; rebuild before attesting')
    return dict(
        target=platform.platform(),
        engine=json.loads(command(['docker', 'version', '--format', '{{json .Server}}'])),
        image=image['Id'],
        policy=POLICY,
        launcher_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        worker_sha256=worker_sha,
        runtime=current,
    )


def require_attestation(path=None, current=None, *, root=None):
    root = runtime_root(root)
    path = Path(path) if path is not None else root / 'evidence/containment.json'
    current = current if current is not None else fingerprint(root=root)
    try:
        evidence = json.loads(path.read_bytes())
    except (OSError, ValueError):
        raise RuntimeError('Missing containment attestation') from None
    if not evidence.get('passed') or evidence.get('fingerprint') != current:
        raise RuntimeError('Failed or stale containment attestation')
    return evidence


def write_bundle(bundle, destination):
    verify_files(bundle['manifest']['files'], bundle['files'])
    check_digest(bundle['manifest'], 'bundle_digest')
    destination = Path(destination)
    destination.mkdir(mode=0o755, parents=True, exist_ok=False)
    for path, raw in {**bundle['files'], 'manifest.json': canonical(bundle['manifest'])}.items():
        safe_path(path)
        file = destination / path
        file.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        with file.open('xb') as stream:
            stream.write(raw)
        file.chmod(0o444)


def verify_bundle(root, runtime, expected_digest=None, selected=None):
    root = Path(root)
    if root.is_symlink():
        raise ValueError('Symlink bundle root')
    manifest_path = root / 'manifest.json'
    if (
        manifest_path.is_symlink()
        or manifest_path.stat().st_nlink != 1
        or manifest_path.stat().st_size > 1048576
    ):
        raise ValueError('Invalid manifest')
    manifest = data_json(manifest_path.read_bytes())
    if manifest.get('schema_version') not in ('2', '3', '4', '5', '6', '8', '10'):
        raise ValueError('Unsupported bundle version; create a new run command')
    check_digest(manifest, 'bundle_digest')
    if expected_digest is not None and manifest['bundle_digest'] != expected_digest:
        raise ValueError('Immutable expected bundle digest mismatch')
    if manifest['runtime'] != runtime:
        raise ValueError('Bundle runtime binding mismatch')
    files = {}
    expected = {'manifest.json'}
    total = 0
    if not 0 < len(manifest['files']) <= 2000:
        raise ValueError('Bundle file count exceeded')
    for item in manifest['files']:
        safe_path(item['path'])
        path = root / item['path']
        expected.add(item['path'])
        if any(p.is_symlink() for p in [path, *path.parents] if p != Path('/tmp')):
            raise ValueError('Symlink in bundle')
        stat = path.stat()
        total += stat.st_size
        if total > 32 * 1024 * 1024:
            raise ValueError('Bundle size exceeded')
        if not path.is_file() or stat.st_nlink != 1 or stat.st_size > 32 * 1024 * 1024:
            raise ValueError('Invalid bundle file')
        files[item['path']] = path.read_bytes()
    if {str(p.relative_to(root)) for p in root.rglob('*') if not p.is_dir()} != expected:
        raise ValueError('Unexpected bundle files')
    verify_files(manifest['files'], files)
    bundle = dict(manifest=manifest, files=files)
    verify_execution_bundle(
        bundle,
        dict(run_id=manifest['run_id'], bundle_digest=expected_digest or manifest['bundle_digest']),
        selected or dict(runtime=runtime),
    )
    return bundle


def verify_execution_bundle(bundle, request, selected):
    """Identical pure preflight before AiiDA node creation and container creation."""
    manifest = bundle['manifest']
    files = bundle['files']
    if manifest.get('schema_version') not in ('2', '3', '4', '5', '6', '8', '10'):
        raise ValueError('Unsupported bundle version; create a new run command')
    if manifest['runtime'] != selected['runtime']:
        raise ValueError('Bundle runtime binding mismatch')
    # Raw repositories contain no application storage envelope or study revision.
    # Authenticate before parsing, including the historical Bundle2–5 readers.
    check_digest(manifest, 'bundle_digest')
    verify_files(manifest['files'], files)
    frozen = dict(
        configuration=data_json(files['configuration.json']),
        model_snapshot=data_json(files['model.json']),
    )
    if frozen['configuration'].get('schema_version') == '4':
        frozen['approach_closure'] = (
            data_json(files['approach/closure.json']) if 'approach/closure.json' in files else None
        )
    try:
        validate_retained_bundle(bundle, request, frozen, raw_snapshot=True)
    except DomainError as error:
        raise ValueError('Invalid frozen bundle contract') from error
    prepared = data_json(files['preparation.json'])
    if 'dependencies' in selected:
        notices = [
            *prepared['license_notices'],
            *[dict(kind='runtime', path=p) for p in selected['licenses']],
        ]
        if manifest['dependencies'] != selected['dependencies'] or manifest['licenses'] != notices:
            raise ValueError('Selected dependency inventory mismatch')
        if any(files.get(path) != raw for path, raw in selected['files'].items()):
            raise ValueError('Selected runtime lock/license bytes mismatch')


def selected_runtime(root=None):
    root = runtime_root(root)
    current = identity(root=root)
    return dict(
        image_digest=current['worker_image'],
        architecture=current['architecture'],
        python_version=current['python_version'],
        worker_entrypoint='hyprn_mvp_integration.worker',
        policy_digest=digest(POLICY),
    )


def bundle_runtime(root=None):
    root = runtime_root(root)
    current = identity(root=root)
    raw = (root / 'selected.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != current.get('selected_sha256'):
        raise RuntimeError('Runtime dependency inventory changed')
    selection = json.loads(raw)
    files = {}
    for item in selection['files']:
        safe_path(item['path'])
        path = root / item['path']
        if path.is_symlink():
            raise ValueError('Symlink runtime artifact')
        files[item['path']] = path.read_bytes()
    verify_files(selection['files'], files)
    return dict(
        runtime=selected_runtime(root=root),
        dependencies=selection['dependencies'],
        files=files,
        licenses=selection['licenses'],
    )


def isolated(
    input_dir, *, canary=False, wall=None, expected_digest=None, root=None, exploration_digest=None
):
    wall = execution_wall_seconds(POLICY['wall_seconds'] if wall is None else wall)
    root = runtime_root(root)
    if not canary:
        require_attestation(root=root)
        if exploration_digest is not None:
            path = Path(input_dir) / 'exploration.json'
            if (
                expected_digest is not None
                or path.is_symlink()
                or path.stat().st_size > 131072
                or set(Path(input_dir).iterdir()) != {path}
            ):
                raise ValueError('Closed data-only exploration mount required')
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != exploration_digest:
                raise ValueError('Exploration artifact identity mismatch')
            exploration.admit_request(data_json(raw))
        elif expected_digest is None:
            raise ValueError('Immutable expected bundle digest required')
        else:
            verified = verify_bundle(
                input_dir, selected_runtime(root=root), expected_digest, bundle_runtime(root=root)
            )
    elif exploration_digest is not None:
        raise ValueError('Exploration always requires attestation')
    owner = OWNER if root == ROOT else root.name
    name = ('hyprn-mvp-worker-' if root == ROOT else owner + '-worker-') + uuid4().hex
    args = [
        'docker',
        'run',
        '--name',
        name,
        '--label',
        'org.hyprn-mvp.owner=' + owner,
        '--network',
        'none',
        '--user',
        POLICY['user'],
        '--read-only',
        '--cap-drop',
        'ALL',
        '--security-opt',
        'no-new-privileges',
        '--memory',
        POLICY['memory'],
        '--memory-swap',
        POLICY['memory'],
        '--cpus',
        POLICY['cpus'],
        '--pids-limit',
        POLICY['pids'],
        '--ulimit',
        f'fsize={POLICY["file_bytes"]}:{POLICY["file_bytes"]}',
        '--log-driver',
        'none',
        '--tmpfs',
        '/tmp:rw,noexec,nosuid,size=16m,mode=1777',
        '--tmpfs',
        '/output:rw,noexec,nosuid,size=16m,mode=1777',
        '--mount',
        f'type=bind,source={input_dir},target=/input,readonly',
        '--workdir',
        '/output',
        '--env',
        'HOME=/tmp',
        '--env',
        'OPENMDAO_REPORTS=0',
        '--env',
        'OPENBLAS_NUM_THREADS=1',
        '--env',
        'PYTHONDONTWRITEBYTECODE=1',
        identity(root=root)['worker_image'],
        'python',
        '-B',
    ]
    args += (
        ['/input/canary.py']
        if canary
        else [
            '-m',
            'hyprn_mvp_integration.exploration',
            '/input/exploration.json',
            exploration_digest,
        ]
        if exploration_digest is not None
        else [
            '-m',
            'hyprn_mvp_integration.worker',
            '/input',
            expected_digest,
            hashlib.sha256(canonical(verified['manifest'])).hexdigest(),
        ]
    )
    start = time.monotonic()
    proc = subprocess.Popen(
        args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=docker_environment()
    )
    selector = selectors.DefaultSelector()
    selector.register(proc.stdout, selectors.EVENT_READ)
    collected = bytearray()
    reason = 'exited'
    try:
        while selector.get_map():
            if time.monotonic() - start > wall:
                reason = 'wall_limit'
                break
            for key, _ in selector.select(timeout=0.1):
                chunk = os.read(key.fileobj.fileno(), 8192)
                if not chunk:
                    selector.unregister(key.fileobj)
                    break
                collected.extend(chunk)
                if len(collected) > POLICY['output_bytes']:
                    reason = 'output_limit'
                    break
            if reason != 'exited':
                break
        if reason != 'exited':
            proc.kill()
            proc.wait(timeout=10)
            proc.stdout.close()
            subprocess.run(
                ['docker', 'kill', name], capture_output=True, timeout=20, env=docker_environment()
            )
        proc.wait(timeout=10)
        state = json.loads(command(['docker', 'inspect', '--format', '{{json .State}}', name]))
        result = dict(
            id=name,
            reason=reason,
            exit_code=proc.returncode,
            seconds=time.monotonic() - start,
            wall_seconds=wall,
            state=state,
            output=bytes(collected[: POLICY['output_bytes']]).decode(errors='replace'),
        )
        (root / 'evidence' / f'{name}.json').write_text(json.dumps(result, indent=2) + '\n')
        return result
    finally:
        selector.close()
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=10)
        proc.stdout.close()
        subprocess.run(
            ['docker', 'rm', '-f', name], capture_output=True, timeout=20, env=docker_environment()
        )


def explore(request, *, root=None):
    """Bounded pure numerical operation; no source or caller-selected file mount."""
    exploration.admit_request(request)
    root = runtime_root(root)
    require_attestation(root=root)
    raw = canonical(request)
    if len(raw) > 131072:
        raise ValueError('Exploration input limit')
    with tempfile.TemporaryDirectory(prefix='exploration-', dir=root) as directory:
        path = Path(directory)
        path.chmod(0o755)
        (path / 'exploration.json').write_bytes(raw)
        (path / 'exploration.json').chmod(0o444)
        report = isolated(
            path, root=root, wall=60, exploration_digest=hashlib.sha256(raw).hexdigest()
        )
    if report['reason'] != 'exited' or report['exit_code'] != 0:
        raise RuntimeError('Bounded exploration computation failed')
    records = [
        line.removeprefix('EXPLORATION_RESULT=')
        for line in report['output'].splitlines()
        if line.startswith('EXPLORATION_RESULT=')
    ]
    if len(records) != 1:
        raise ValueError('One numerical result required')
    result = data_json(records[0].encode())
    if result.get('identity') != request['identity']:
        raise ValueError('Exploration result identity mismatch')
    return dict(
        result=result,
        runtime=selected_runtime(root=root),
        request_sha256=hashlib.sha256(raw).hexdigest(),
        result_sha256=digest(result),
        elapsed_seconds=report['seconds'],
    )


def host_home():
    """The account's home folder from the password database (the probe proves it is absent
    inside the worker); not $HOME, which managers may replace with a clean folder."""
    import pwd

    return Path(pwd.getpwuid(os.getuid()).pw_dir)


def probe_homes(root=None):
    """Home folders the containment probe proves absent inside the worker: always the
    account's, plus the installation's configured host_home, or a scoped root's scratch home."""
    root = runtime_root(root)
    homes = [host_home()]
    configured = (
        (Path(INSTALLATION['host_home']) if INSTALLATION is not None else None)
        if root == ROOT
        else root / 'home'
    )
    if configured is not None and configured not in homes:
        homes.append(configured)
    return [str(home) for home in homes]


def attest(root=None):
    root = runtime_root(root)
    """Run only synthetic canaries, never model source, before granting execution."""
    before = fingerprint(root=root)
    (root / 'evidence').mkdir(exist_ok=True)
    (root / 'canaries').mkdir(exist_ok=True)
    secret = root / 'canaries' / 'host-secret'
    secret.write_text(uuid4().hex)
    secret.chmod(0o600)

    def probe(source, wall=None):
        directory = root / 'canaries' / uuid4().hex
        directory.mkdir(mode=0o755)
        (directory / 'canary.py').write_text(source)
        (directory / 'canary.py').chmod(0o444)
        return isolated(directory, canary=True, wall=wall, root=root)

    source = (
        "import json,os,socket\nchecks={'nonroot':os.getuid()!=0,"
        "'socket_denied':not os.path.exists('/var/run/docker.soc"
        "k'),'home_denied':not any(os.path.exists(p) for p in "
        f'{probe_homes(root=root)!r}'
        "),'secret_denied':not os.path.exists("
        f'{str(secret)!r}'
        ") and not any(k.startswith(('AWS_','OPENAI_','AIIDA_'))"
        " for k in os.environ)}\nfor name,path in [('outside_writ"
        "e_denied','/escape'),('input_readonly','/input/canary.p"
        "y')]:\n try:open(path,'w').write('canary');checks[name]="
        'False\n except OSError:checks[name]=True\ns=socket.socket'
        "();s.settimeout(1)\ntry:s.connect(('1.1.1.1',443));check"
        "s['network_denied']=False\nexcept OSError:checks['networ"
        "k_denied']=True\nchecks['memory_limit']=open('/sys/fs/cg"
        "roup/memory.max').read().strip()=='268435456'\nchecks['p"
        "id_limit']=open('/sys/fs/cgroup/pids.max').read().strip"
        "()=='32'\nchecks['cpu_limit']=open('/sys/fs/cgroup/cpu.m"
        "ax').read().strip()=='50000 100000'\nprint(json.dumps(ch"
        'ecks));assert all(checks.values())\n'
    )
    cases = {'access': probe(source)}
    cases['memory'] = probe('x=bytearray(512*1024*1024)')
    cases['wall'] = probe('while True: pass', 3)
    cases['output'] = probe("import os\nwhile True:os.write(1,b'x'*8192)")
    cases['file_bound'] = probe(
        (
            "import os\ntry:open('/output/large','wb').write(b'x'*209"
            "7152)\nexcept OSError:pass\nassert os.path.getsize('/outp"
            "ut/large')<=1048576"
        )
    )
    cases['pids'] = probe(
        (
            'import subprocess\np=[]\ntry:\n for i in range(40):p.appen'
            "d(subprocess.Popen(['sleep','10']))\nexcept OSError:asse"
            "rt len(p)<32\nelse:raise AssertionError('PID bound bypas"
            "sed')\nfinally:\n for c in p:c.terminate()"
        )
    )
    # The worker user imports the worker package as a launch does and reports the digests of
    # the bytes it read: a worker that cannot read its own code, or reads other code,
    # is never attested.
    cases['worker_import'] = probe(
        (
            'import hashlib,json\nimport hyprn_mvp_integration as p,h'
            'yprn_mvp_integration.worker as w,hyprn_mvp_integration.'
            'results as r,hyprn_mvp_integration.exploration as e\n'
            'print(json.dumps({n:hashlib.sha256(open(m.'
            "__file__,'rb').read()).hexdigest() for n,m in (('packag"
            "e',p),('worker',w),('results',r),('exploration',e))}))"
        )
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                probe,
                (
                    "from pathlib import Path\nimport time\np=Path('/output/ow"
                    "ner');assert not p.exists();p.write_text('"
                    f'{token}'
                    "');time.sleep(1);assert p.read_text()=='"
                    f'{token}'
                    "'"
                ),
            )
            for token in ('first', 'second')
        ]
        for n, future in enumerate(futures):
            cases['concurrent_' + str(n)] = future.result()
    try:
        access = json.loads(cases['access']['output'])
    except ValueError:
        access = {}
    try:
        imported = json.loads(cases['worker_import']['output'])
    except ValueError:
        imported = {}
    package = Path(__file__).with_name('__init__.py')
    expected = dict(
        package=hashlib.sha256(package.read_bytes()).hexdigest(),
        worker=before['worker_sha256'],
        results=before['runtime']['results_sha256'],
        exploration=hashlib.sha256(
            Path(__file__).with_name('exploration.py').read_bytes()
        ).hexdigest(),
    )
    passed = (
        cases['memory']['state']['OOMKilled']
        and cases['wall']['reason'] == 'wall_limit'
        and cases['output']['reason'] == 'output_limit'
        and all(
            cases[k]['exit_code'] == 0
            for k in (
                'access',
                'file_bound',
                'pids',
                'worker_import',
                'concurrent_0',
                'concurrent_1',
            )
        )
        and imported == expected
        and before == fingerprint(root=root)
    )
    evidence = dict(
        passed=bool(passed),
        fingerprint=before,
        cases=cases,
        access_checks=access,
        worker_import=imported,
        measured_at=time.time(),
        candidate_executions=0,
    )
    path = root / 'evidence/containment.json'
    if path.exists():
        (
            path.parent / ('containment-' + hashlib.sha256(path.read_bytes()).hexdigest() + '.json')
        ).write_bytes(path.read_bytes())
    path.write_text(json.dumps(evidence, indent=2) + '\n')
    if not passed:
        raise RuntimeError('Containment failed; execution denied')
    return evidence


def main():
    import sys

    args = sys.argv[1:]
    root = None
    if len(args) in (4, 5) and args[0] == '--runtime-root':
        root = fixture_runtime_root(args[1])
        args = args[2:]
    if len(args) not in (2, 3):
        raise ValueError('Fixed bundle directory and immutable expected digest required')
    wall = execution_wall_seconds(int(args[2])) if len(args) == 3 else EXECUTION_WALL_DEFAULT
    result = isolated(Path(args[0]).resolve(), expected_digest=args[1], wall=wall, root=root)
    print(json.dumps(result, allow_nan=False))


if __name__ == '__main__':
    main()
