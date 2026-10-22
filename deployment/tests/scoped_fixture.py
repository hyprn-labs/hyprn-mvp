"""Data-only isolation primitives. This module must never import AiiDA.

Native/backend creation belongs to the task that needs it, after guarded().
The development interpreters are those of the locked environments that ./hyprn-mvp dev check
provisions from uv.lock (deployment/local_paths.py, locked_python); they are interpreters only
and no profile of theirs is ever used. The clean child environment passes every set location
variable through unchanged, plus the resolved scratch root and live roots.
Scoped folders are <scratch root>/hyprn-mvp-test-<uuid>.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
from uuid import UUID, uuid4
from urllib.parse import urlsplit
import sys

_DEPLOYMENT = str(Path(__file__).resolve().parents[1])
if _DEPLOYMENT not in sys.path:
    sys.path.append(_DEPLOYMENT)
import local_paths  # noqa: E402


def _interpreter(path):
    return None if path is None else str(path)


# Development interpreters: the locked environments of this checkout's uv.lock, never an
# interpreter named by HYPRN_MVP_NATIVE_PYTHON or HYPRN_MVP_CONTRACT_PYTHON. None while the
# tool cache is unset: validate_scope() then refuses every scope with a message naming it.
APPROVED_PYTHON = _interpreter(local_paths.locked_python('native', required=False))
APPROVED_CONTRACT_PYTHON = _interpreter(local_paths.locked_python('contract', required=False))
# Folder holding every scope; a child resolves the same folder from the passed variable.
SCRATCH_ROOT = local_paths.scratch_root()
SCOPE_PREFIX = local_paths.SCOPE_PREFIX
# Location variables only (never credentials), captured once at import and validated as
# absolute paths, so a fixture that clears os.environ still hands its children the same values.
PASS_THROUGH = {name: str(local_paths.absolute(os.environ[name], name))
                for name in local_paths.SCOPED_PASS_THROUGH if os.environ.get(name)}
PASS_THROUGH[local_paths.SCRATCH_ROOT] = str(SCRATCH_ROOT)
# Children see the locked interpreters under the interpreter variables (browser configurations
# and the managers read them there), whatever those variables held in this process.
PASS_THROUGH.update({name: value for name, value in ((local_paths.NATIVE_PYTHON, APPROVED_PYTHON),
                                                     (local_paths.CONTRACT_PYTHON, APPROVED_CONTRACT_PYTHON))
                     if value is not None})
if local_paths.live_roots():
    PASS_THROUGH[local_paths.LIVE_ROOTS] = os.pathsep.join(str(p) for p in local_paths.live_roots())
# Value variables, validated by their readers before they are handed on.
_VALUES = {local_paths.LIVE_PORTS: ','.join(map(str, local_paths.live_ports())),
           local_paths.LIVE_NAMES: ','.join(local_paths.live_names()),
           local_paths.ENGINE_IMAGE: local_paths.engine_image(required=False),
           local_paths.MODELING_SOURCE_IMAGE: local_paths.modeling_source_image(required=False)}
PASS_THROUGH.update({name: value for name, value in _VALUES.items() if value})
PATH = '/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin'


@dataclass(frozen=True)
class Scope:
    root: Path
    run_uuid: str
    profile: str
    profile_uuid: str
    store_uuid: str
    backend: str = 'core.sqlite_dos'
    interpreter: str = APPROVED_PYTHON
    url: str | None = None

    def record(self):
        return {**asdict(self), 'root': str(self.root)}


def no_symlinks(path):
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts or '\\' in str(path):
        raise ValueError('Absolute canonical off-cloud path required')
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Symlink in fixture path')
    if path.resolve() != path:
        raise ValueError('Noncanonical fixture path')
    return path


def root_path(root):
    root = no_symlinks(root)
    if root.parent != SCRATCH_ROOT or not root.name.startswith(SCOPE_PREFIX):
        raise ValueError('Unique scoped off-cloud root required')
    suffix = root.name.removeprefix(SCOPE_PREFIX)
    if str(UUID(suffix)) != suffix:
        raise ValueError('Canonical fixture UUID required')
    return root


def validate_url(url):
    if url is None:
        return  # Pure tests have no service URL; browsers require one explicitly.
    value = urlsplit(url)
    if (value.scheme != 'http' or value.hostname != '127.0.0.1'
            or value.username is not None or value.password is not None
            or value.path not in ('', '/') or value.query or value.fragment
            or value.port is None or value.port < 1024
            or value.port in local_paths.live_ports()
            or url not in (f'http://127.0.0.1:{value.port}', f'http://127.0.0.1:{value.port}/')):
        raise ValueError('Explicit isolated loopback URL required; live URLs denied')


def validate_scope(scope, *, marker=True):
    root = root_path(scope.root)
    ids = (scope.run_uuid, scope.profile_uuid, scope.store_uuid)
    if any(not isinstance(v, str) or str(UUID(v)) != v for v in ids) or len(set(ids)) != 3:
        raise ValueError('Distinct explicit run/profile/store UUIDs required')
    if root.name != SCOPE_PREFIX + scope.run_uuid:
        raise ValueError('Root and run identity differ')
    if scope.profile != SCOPE_PREFIX + scope.run_uuid or scope.backend != 'core.sqlite_dos':
        raise ValueError('Explicit isolated profile/backend required')
    # An unset tool cache or an unprovisioned locked environment refuses with a message naming
    # the tool-cache variable.
    local_paths.require_file(APPROVED_PYTHON, local_paths.TOOLS_DIR)
    local_paths.require_file(APPROVED_CONTRACT_PYTHON, local_paths.TOOLS_DIR)
    if scope.interpreter not in (APPROVED_PYTHON, APPROVED_CONTRACT_PYTHON) or not Path(scope.interpreter).is_file():
        raise ValueError('Reviewed interpreter required')
    validate_url(scope.url)
    for name in ('scope.json', 'home', 'tmp', 'aiida', 'native', 'artifacts', 'evidence'):
        no_symlinks(root / name)
    if marker:
        if json.loads((root / 'scope.json').read_text()) != scope.record():
            raise ValueError('Fixture marker identity mismatch')
        if any(not (root / name).is_dir() for name in ('home', 'tmp', 'aiida', 'native', 'artifacts', 'evidence')):
            raise ValueError('Fixture directories missing')
    # If a later task creates an AiiDA config, never accept a default or foreign profile.
    config = no_symlinks(root / 'aiida/.aiida/config.json')
    if config.exists():
        record = json.loads(config.read_text())
        profiles = record.get('profiles', {})
        if record.get('default_profile') is not None or set(profiles) != {scope.profile}:
            raise ValueError('Default or foreign native profile forbidden')
        profile = profiles[scope.profile]
        if (profile.get('PROFILE_UUID') not in (scope.profile_uuid, UUID(scope.profile_uuid).hex)
                or profile.get('storage') != {'backend': scope.backend,
                    'config': {'filepath': str(root / 'native')}}):
            raise ValueError('Native backend/profile identity mismatch')
        repository = no_symlinks(root / 'native/container/config.json')
        if repository.exists():
            actual = json.loads(repository.read_text()).get('container_id')
            if actual not in (scope.store_uuid, UUID(scope.store_uuid).hex):
                raise ValueError('Actual native repository identity mismatch')
    return scope


def new_scope(*, url=None):
    run = str(uuid4())
    return Scope(SCRATCH_ROOT / (SCOPE_PREFIX + run), run,
                 SCOPE_PREFIX + run, str(uuid4()), str(uuid4()), url=url)


def allocate_scope(scope):
    """Validate every caller-controlled field BEFORE the first write."""
    validate_scope(scope, marker=False)
    if scope.root.exists():
        raise ValueError('Refusing existing fixture root')
    scope.root.mkdir(mode=0o700)  # Exclusive allocation; never reuse a previous run.
    for name in ('home', 'tmp', 'aiida', 'native', 'artifacts', 'evidence'):
        (scope.root / name).mkdir(mode=0o700)
    with (scope.root / 'scope.json').open('x') as output:
        json.dump(scope.record(), output, indent=2)
        output.write('\n')
    validate_scope(scope)
    import check_storage
    check_storage.register(scope)
    return scope


def scoped_path(scope, relative):
    validate_scope(scope)
    relative = Path(relative)
    if relative.is_absolute() or '..' in relative.parts or '\\' in str(relative):
        raise ValueError('Relative fixture path required')
    path = no_symlinks(scope.root / relative)
    if not path.is_relative_to(scope.root) or path == scope.root:
        raise ValueError('Fixture path escape')
    return path


def clean_environment(scope):
    validate_scope(scope)
    return {
        'PATH': PATH, 'HOME': str(scope.root / 'home'),
        'TMPDIR': str(scope.root / 'tmp'), 'AIIDA_PATH': str(scope.root / 'aiida'),
        'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONNOUSERSITE': '1',
        # CPython/macOS otherwise inject these after exec; pin them explicitly.
        'LC_CTYPE': 'UTF-8', '__CF_USER_TEXT_ENCODING': f'0x{os.getuid():X}:0:0',
        'HYPRN_MVP_TEST_SCOPE_ROOT': str(scope.root),
        'HYPRN_MVP_TEST_SCOPE_PROFILE': scope.profile,
        **({'HYPRN_MVP_TEST_SCOPE_URL': scope.url} if scope.url is not None else {}),
        **PASS_THROUGH,
        **({'HYPRN_MVP_CHECK_SESSION': os.environ['HYPRN_MVP_CHECK_SESSION']}
           if os.environ.get('HYPRN_MVP_CHECK_SESSION') else {}),
    }


def contract_generator_command(scope, output, *, interpreter=APPROVED_CONTRACT_PYTHON):
    """The reviewed app interpreter is allowed only for data-only route generation."""
    validate_scope(scope)
    if interpreter != APPROVED_CONTRACT_PYTHON or not Path(interpreter).is_file():
        raise ValueError('Reviewed application contract interpreter required')
    output = scoped_path(scope, output)
    repo = Path(__file__).resolve().parents[2]
    return [interpreter, '-B', str(repo / 'application/generate_contract.py'), '--output', str(output)]


def guarded(scope, callback, *, env=None):
    validate_scope(scope)
    actual = dict(os.environ) if env is None else env
    if actual != clean_environment(scope):
        # Never include environment values in the error or evidence.
        raise ValueError('Unscoped environment or ambient credential rejected')
    return callback(scope)


def scope_at(path):
    """The validated scope that contains ``path`` (its marker in the scope root). Unlike
    scope_from_environment it does not require the caller's own environment to be clean, so
    fixtures inside a running test process can name the scope their effects belong to."""
    path = no_symlinks(Path(path))
    root = next((p for p in (path, *path.parents) if p.parent == SCRATCH_ROOT), None)
    if root is None:
        raise ValueError('Path is not inside an isolated test scope')
    root = root_path(root)
    fields = json.loads(no_symlinks(root / 'scope.json').read_text())
    fields['root'] = Path(fields['root'])
    scope = Scope(**fields)
    if scope.root != root:
        raise ValueError('Fixture marker points outside root')
    return validate_scope(scope)


def scope_from_environment():
    root = root_path(Path(os.environ.get('HYPRN_MVP_TEST_SCOPE_ROOT', '')))
    marker = no_symlinks(root / 'scope.json')
    fields = json.loads(marker.read_text())
    fields['root'] = Path(fields['root'])
    scope = Scope(**fields)
    if scope.root != root:
        raise ValueError('Fixture marker points outside root')
    return guarded(scope, lambda valid: valid)


def create_native_fixture(scope):
    """Initialize one fresh explicit test backend after the environment guard.

    AiiDA generates the repository UUID. Pin that actual identity in the marker
    before any ORM node is created; never edit repository identity to fit a test.
    """
    guarded(scope, lambda valid: valid)
    if (scope.root / 'aiida/.aiida/config.json').exists() or any((scope.root / 'native').iterdir()):
        raise ValueError('Native fixture must be fresh')
    from dataclasses import replace
    from aiida.manage.configuration import get_config
    from aiida.manage.configuration.profile import Profile
    from aiida.manage import get_manager
    from aiida import load_profile, orm
    config = get_config(create=True)
    if config.profile_names or str(config.dirpath) != str(scope.root / 'aiida/.aiida'):
        raise ValueError('Unexpected initial native configuration')
    profile = Profile(scope.profile, dict(PROFILE_UUID=scope.profile_uuid,
        storage=dict(backend=scope.backend, config=dict(filepath=str(scope.root / 'native'))),
        process_control=dict(backend=None, config=None), test_profile=True))
    profile.storage_cls.initialise(profile)
    config.add_profile(profile).store()
    load_profile(scope.profile)
    backend = get_manager().get_profile_storage()
    actual = str(UUID(backend.get_repository().uuid))
    scope = replace(scope, store_uuid=actual)
    (scope.root / 'scope.json').write_text(json.dumps(scope.record(), indent=2) + '\n')
    guarded(scope, lambda valid: valid)
    if (str(UUID(backend.profile.uuid)) != scope.profile_uuid
            or backend.profile.storage_config != {'filepath': str(scope.root / 'native')}
            or str(UUID(backend.get_repository().uuid)) != scope.store_uuid):
        raise ValueError('Actual native identity differs from guarded marker')
    user = orm.User(email='hyprn-mvp-test@localhost.invalid', backend=backend).store()
    config.set_default_user_email(profile, user.email)
    config.store()
    guarded(scope, lambda valid: valid)
    return scope, backend


def launcher_command(scope, *, check_only=False):
    """Fixture launcher bound to THIS tree, never a checkout named by the interpreter's .pth.

    A development interpreter's startup .pth may name another checkout, so a bare `-m`
    launcher run from a worktree or a selected-release copy could run that checkout's
    launcher. scoped_fixture_launcher.py prepends this tree's roots, refuses a launcher
    resolved elsewhere and records the actual module files.
    """
    validate_scope(scope)
    entry=Path(__file__).resolve().with_name('scoped_fixture_launcher.py')
    return ['/usr/bin/env','-i',*[k+'='+v for k,v in clean_environment(scope).items()],
            APPROVED_PYTHON,'-B',str(entry),*(['--check-only'] if check_only else []),'--runtime-root',str(scope.root)]


def worker_wrapper_text(scope):
    import shlex
    return '#!/bin/sh\nexec '+shlex.join(launcher_command(scope))+' "$@"\n'


def prepare_worker_fixture(scope, backend):
    """Same reviewed builder/attestor, fresh root and ownership, reusable image."""
    import hashlib, shlex, shutil, sys
    validate_scope(scope)
    from hyprn_mvp_integration import launcher
    from aiida import orm
    repo=Path(__file__).resolve().parents[2]
    sys.path.insert(0,str(repo/'deployment'))
    from execution_runtime import build_worker
    runtime=build_worker(root=scope.root)
    # Immutable reviewed dependency/license inventory only; no profile, code,
    # credentials, attestation, execution records or live database is copied.
    origin=local_paths.native_inventory()
    raw=no_symlinks(origin/'selected.json').read_bytes()
    selection=json.loads(raw)
    for descriptor in selection['files']:
        relative=descriptor['path']
        if not relative.startswith(('locks/','licenses/')):raise ValueError('Unexpected dependency artifact')
        target=scoped_path(scope,relative)
        source=no_symlinks(origin/relative)
        content=source.read_bytes()
        if len(content)!=descriptor['size'] or hashlib.sha256(content).hexdigest()!=descriptor['sha256']:
            raise ValueError('Reviewed dependency bytes changed')
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(content)
    (scope.root/'selected.json').write_bytes(raw)
    runtime['selected_sha256']=hashlib.sha256(raw).hexdigest()
    (scope.root/'runtime.json').write_text(json.dumps(runtime,indent=2)+'\n')
    wrapper=scope.root/'launch-worker'
    wrapper.write_text(worker_wrapper_text(scope));wrapper.chmod(0o700)
    computer=orm.Computer(label='hyprn-mvp-scoped-worker',hostname='localhost',transport_type='core.local',
        scheduler_type='core.direct',workdir=str(scope.root/'tmp/work/{username}'),backend=backend).store()
    computer.configure(safe_interval=0.1);computer.set_minimum_job_poll_interval(0.2)
    code=orm.InstalledCode(label='hyprn-mvp-scalar',computer=computer,filepath_executable=str(wrapper),default_calc_job_plugin='hyprn_mvp.scalar',backend=backend).store()
    evidence=launcher.attest(root=scope.root)
    if not evidence['passed']:raise ValueError('Fixture containment failed')
    return code


def build_derived_image(scope, base, context, role, recipe, *, evidence=None, disposable=False):
    """Reuse exact derived-image inputs; container/store ownership stays scoped.

    Changed code, recipe or base requires a different image. Scope UUIDs do not.
    An image must still extend the verified base layers before it can be used.
    """
    import hashlib, subprocess, uuid
    validate_scope(scope)
    context=scoped_path(scope,Path(context).relative_to(scope.root))
    def docker(*args):
        return subprocess.run(['docker',*args],env=clean_environment(scope),capture_output=True,text=True,check=True).stdout.strip()
    info=json.loads(docker('image','inspect',base))[0]
    if info['Id']!=base:raise ValueError('Base image identity mismatch')
    files=[]
    for p in sorted(context.rglob('*')):
        no_symlinks(p)
        if p == context/'Dockerfile':continue
        if not (p.is_file() or p.is_dir()):raise ValueError('Unsupported image context entry')
        files.append((str(p.relative_to(context)),p.stat().st_mode & 0o7777,
                      hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None))
    body=recipe
    if disposable:body += 'LABEL org.hyprn-mvp.test-scope="'+scope.run_uuid+'"\n'
    digest=hashlib.sha256(json.dumps(dict(base=base,recipe=body,files=files),sort_keys=True).encode()).hexdigest()
    body += 'LABEL org.hyprn-mvp.derived-inputs=\"'+digest+'\"\n'
    tag='hyprn-mvp-'+role+':'+digest[:16]
    cached=subprocess.run(['docker','image','inspect',tag],env=clean_environment(scope),capture_output=True,text=True)
    if cached.returncode==0:
        image=json.loads(cached.stdout)[0]
        if (image.get('Config',{}).get('Labels') or {}).get('org.hyprn-mvp.derived-inputs')==digest:
            if image['RootFS']['Layers'][:len(info['RootFS']['Layers'])]!=info['RootFS']['Layers']:
                raise ValueError('Cached image does not extend its base image')
            if evidence is not None:Path(evidence).write_text(json.dumps(dict(reused=True,inputs_sha256=digest,image=image['Id']))+'\n')
            return image['Id']
    reference='hyprn-mvp-build-base:'+uuid.uuid4().hex[:16]
    (context/'Dockerfile').write_text('FROM '+reference+'\n'+body)
    command=['docker','build','--network=none','--pull=false','-t',tag,str(context)]
    docker('tag',base,reference)
    try:
        result=subprocess.run(command,env=clean_environment(scope),capture_output=True,text=True)
    finally:
        tags=json.loads(docker('image','inspect',base))[0].get('RepoTags') or []
        if reference in tags and len(tags)>1:docker('image','rm','--no-prune',reference)
    if evidence is not None:
        Path(evidence).write_text(json.dumps(dict(command=command,exit=result.returncode,stdout=result.stdout,
                                                  stderr=result.stderr),indent=2)+'\n')
    result.check_returncode()
    image=json.loads(docker('image','inspect',tag))[0]
    if image['RootFS']['Layers'][:len(info['RootFS']['Layers'])]!=info['RootFS']['Layers']:
        raise ValueError('Scoped image does not extend its base image')
    return image['Id']


def change_worker_fixture_identity(scope):
    """Reattest an actual distinct image with identical reviewed worker bytes.

    Label-only image mutation is enough to invalidate the selected image digest;
    it changes neither the numerical engine nor the production runtime/policy.
    """
    import hashlib, subprocess
    validate_scope(scope)
    from hyprn_mvp_integration import launcher
    root=launcher.fixture_runtime_root(scope.root)
    runtime=launcher.identity(root=root);original=dict(runtime)
    context=scoped_path(scope,'artifacts/changed-image');context.mkdir()
    image=build_derived_image(scope,runtime['worker_image'],context,'worker',
                              'LABEL org.hyprn-mvp.attempt="'+scope.run_uuid+'"\n',
                              evidence=root/'evidence/changed-image-build.json', disposable=True)
    if image==runtime['worker_image']:raise ValueError('Fixture image identity did not change')
    runtime['worker_image']=image
    (root/'evidence/runtime-before-change.json').write_text(json.dumps(original,indent=2)+'\n')
    (root/'runtime.json').write_text(json.dumps(runtime,indent=2)+'\n')
    try:launcher.require_attestation(root=root)
    except RuntimeError as error:
        if 'stale' not in str(error):raise
    else:raise ValueError('Changed image incorrectly reused old attestation')
    evidence=launcher.attest(root=root)
    if not evidence['passed']:raise ValueError('Changed fixture image containment failed')
    (root/'evidence/runtime-change.json').write_text(json.dumps(dict(before=original,after=runtime,
        old_attestation_rejected=True,attestation_sha256=hashlib.sha256((root/'evidence/containment.json').read_bytes()).hexdigest()),indent=2)+'\n')


def run_export_dispatcher(scope,native,store_path,request_id):
    """Actual app CLI/host codecs with the explicitly guarded native backend."""
    import sys,time
    validate_scope(scope)
    path=no_symlinks(store_path)
    if not path.is_relative_to(scope.root):raise ValueError('Fixture app store outside scope')
    from hyprn_mvp_integration import launcher
    if launcher.fixture_runtime_root(native.root)!=scope.root or native.backend.profile.name!=scope.profile:
        raise ValueError('Unbound archive backend')
    repo=Path(__file__).resolve().parents[2]
    script="""import sys,os
from pathlib import Path
repo=Path.cwd()
sys.path.insert(0,str(repo/'deployment/tests'))
import scoped_fixture as fixture
scope=fixture.scope_from_environment()
store=fixture.no_symlinks(Path(sys.argv.pop(1)))
assert store.is_relative_to(scope.root)
os.environ['HYPRN_MVP_APP_STORE']=str(store)
sys.path.insert(0,str(repo/'application/src'))
from hyprn_mvp_app import dispatcher
def forbidden(*args,**kwargs):raise AssertionError('Forbidden export construction')
dispatcher.ModelingClient=forbidden
dispatcher.Submissions=forbidden
dispatcher.ObservationPublisher=forbidden
dispatcher.main()
assert not any(name.split('.')[0] in {'aiida','openmdao','openturns'} for name in sys.modules)
"""
    command=[APPROVED_PYTHON,'-B','-c',script,str(path),'--exports-only','--once','--export-request',request_id]
    import dispatch_runtime
    started=time.monotonic()
    with (scope.root/'evidence'/('exports-'+request_id+'.stderr.log')).open('wb') as errors:
        status=dispatch_runtime.bridge_child(native,command,exports_only=True,env=clean_environment(scope),cwd=repo,stderr=errors)
    (scope.root/'evidence'/('exports-'+request_id+'.json')).write_text(json.dumps(dict(command=command,exit=status,duration_seconds=time.monotonic()-started),indent=2)+'\n')
    if status:raise AssertionError('Isolated export child failed: '+request_id)


def documents_scope(interpreter):
    """Documents boundary: validate identity and environment before any imports.

    Keep the established environment byte-for-byte. Plugin autoload is disabled
    only after this check, immediately before pytest is imported by the runner.
    """
    import sys
    scope = scope_from_environment()
    if interpreter not in (APPROVED_PYTHON, APPROVED_CONTRACT_PYTHON):
        raise ValueError('Reviewed Documents interpreter required')
    if sys.executable != interpreter or scope.interpreter != interpreter:
        raise ValueError('Documents child interpreter mismatch')
    for relative in ('native/database.sqlite', 'native/database.sqlite-wal',
                     'native/database.sqlite-shm', 'native/container',
                     'native/container/config.json', 'aiida/.aiida',
                     'aiida/.aiida/config.json'):
        no_symlinks(scope.root / relative)
    repository = scope.root / 'native/container/config.json'
    if repository.exists():
        actual = json.loads(repository.read_text()).get('container_id')
        if actual not in (scope.store_uuid, UUID(scope.store_uuid).hex):
            raise ValueError('Documents repository identity mismatch')
    claim = no_symlinks(scope.root / 'evidence/documents-child.json')
    identity = dict(pid=os.getpid(), run_uuid=scope.run_uuid, interpreter=interpreter)
    try:
        with claim.open('x') as output:
            json.dump(identity, output)
    except FileExistsError:
        if json.loads(claim.read_text()) != identity:
            raise ValueError('Documents shared or previously consumed child scope')
    return scope
