"""Verify and bind a retained release; stdlib only, importing this module has no side effects.

A retained release is a directory below the releases root holding ``manifest.json``, its
digest record ``manifest.sha256``, the exact ``source`` tree and an optional ``build`` folder
(the served UI). This module:

* verifies a release: canonical manifest, exact tree inventory and digest, retained UI build,
  and (deep) regenerated public contracts equal to the retained ones;
* binds a manager process to the release that contains its entry script before any project
  import: it removes project paths of every other checkout (including paths that an
  interpreter's startup hook adds), prepends only the release's deployment, application/src
  and integration/src roots and refuses modules, a working directory or inherited bindings
  from any other source. Effectful commands additionally require a retained, reviewed release
  and its manifest digest. A manifest is source evidence, not runtime attestation;
* records and requires the independent review of a release (create-only, digest-named) and
  makes a release immutable on explicit request.

The releases root and the development interpreters come from the sibling
deployment/local_paths.py (stdlib only, loaded from this same release tree); the operations
that need them refuse while they are unset.
"""

import argparse
from dataclasses import dataclass, field
import hashlib
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid

import local_paths

RELEASES_ROOT = local_paths.releases_root(required=False)
# Development interpreters (strings, deployment/local_paths.py); None while unconfigured.
APPROVED_PYTHON, CONTRACT_PYTHON = (
    None if p is None else str(p)
    for p in (
        local_paths.native_python(required=False),
        local_paths.contract_python(required=False),
    )
)
MANIFEST_SCHEMA = 'hyprn-mvp.release/1'
RELEASE_PREFIX = 'release-'
SAFE_PATH = '/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin'
# Manager entry points that bind through this module before any project import; every one is
# a file of this repository, and release_commands names no other script.
RELEASE_BINDING_PATHS = frozenset(
    {
        'deployment/release.py',
        'deployment/dispatch_runtime.py',
        'deployment/application_runtime.py',
        'deployment/execution_runtime.py',
        'deployment/modeling_runtime.py',
        'deployment/native_environment.py',
    }
)
GENERATED_PATHS = ('contracts/hyprn-mvp.openapi.yaml', 'ui/src/contract.ts')
# Read-only interpreter evidence modules for the live executor seam.
EVIDENCE_MODULES = (
    'hyprn_mvp_app.dispatcher',
    'hyprn_mvp_app.execution',
    'hyprn_mvp_integration.launcher',
    'hyprn_mvp_integration.results',
    'hyprn_mvp_integration.calculation',
)
EXEC_MODULES = frozenset({'hyprn_mvp_integration.launcher'})
PROJECT_PACKAGES = frozenset({'hyprn_mvp_app', 'hyprn_mvp_integration', 'hyprn_mvp_local'})
ALLOWED_RELEASE_ENTRIES = frozenset({'manifest.json', 'manifest.sha256', 'source', 'build'})
ENV_MANIFEST, ENV_SHA, ENV_ROOT = (
    'HYPRN_MVP_RELEASE_MANIFEST',
    'HYPRN_MVP_RELEASE_SHA256',
    'HYPRN_MVP_RELEASE_ROOT',
)
ENV_EVIDENCE = 'HYPRN_MVP_RELEASE_EVIDENCE_DIR'
# One-shot token from the starting manager to its executor child; names the child's evidence file.
ENV_EVIDENCE_TOKEN = 'HYPRN_MVP_RELEASE_EVIDENCE_TOKEN'


class ReleaseError(ValueError):
    """Selection/verification failure; nothing is retained."""


class ReleaseBindingError(ReleaseError):
    """Binding refusal before any project import or runtime effect."""


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()


def _relative(path):
    pure = PurePosixPath(path)
    if pure.is_absolute() or '..' in pure.parts or not pure.parts or '\\' in path:
        raise ReleaseError('Unsafe release path: ' + path[:200])
    return str(pure)


def scan(tree):
    """Exact regular-file inventory; symlinks and special files are refused."""
    tree = Path(tree)
    if not tree.is_dir() or any(p.is_symlink() for p in (tree, *tree.parents)):
        raise ReleaseError('Unsafe symlink or missing release tree')
    files = []
    for directory, dirs, names in os.walk(tree):
        base = Path(directory)
        for name in dirs:
            if (base / name).is_symlink():
                raise ReleaseError(
                    'Symlink in release tree: ' + str((base / name).relative_to(tree))
                )
        dirs.sort()
        for name in sorted(names):
            path = base / name
            if path.is_symlink() or not path.is_file():
                raise ReleaseError(
                    'Non-regular file in release tree: ' + str(path.relative_to(tree))
                )
            raw = path.read_bytes()
            files.append(
                dict(
                    path=path.relative_to(tree).as_posix(),
                    size=len(raw),
                    sha256=sha256(raw),
                    executable=bool(path.stat().st_mode & 0o100),
                )
            )
    files.sort(key=lambda item: item['path'])
    return files


def tree_digest(files):
    rows = [[f['path'], f['sha256'], f['size'], f['executable']] for f in files]
    return sha256(json.dumps(rows, separators=(',', ':')).encode())


def _clean_env(home):
    return dict(
        PATH=SAFE_PATH,
        HOME=str(home),
        TMPDIR=str(home),
        PYTHONDONTWRITEBYTECODE='1',
        PYTHONNOUSERSITE='1',
        LC_CTYPE='UTF-8',
    )


def _run(command, cwd, env, label, log=None):
    result = subprocess.run(
        [str(c) for c in command], cwd=cwd, env=env, capture_output=True, text=True, timeout=600
    )
    if log is not None:
        (log / (label + '.log')).write_text(
            '$ ' + ' '.join(map(str, command)) + '\n' + result.stdout + result.stderr
        )
    if result.returncode:
        raise ReleaseError(label + ' failed: ' + (result.stderr or result.stdout)[-600:])
    return result.stdout


def regenerate(tree, contract_python, home, log=None):
    env = _clean_env(home)
    _run(
        [
            contract_python,
            '-I',
            '-B',
            tree / 'application/generate_contract.py',
            '--output',
            tree / 'contracts/hyprn-mvp.openapi.yaml',
        ],
        tree,
        env,
        'generate-openapi',
        log,
    )
    _run(
        [
            contract_python,
            '-I',
            '-B',
            tree / 'ui/generate_types.py',
            '--input',
            tree / 'contracts/hyprn-mvp.openapi.yaml',
            '--output',
            tree / 'ui/src/contract.ts',
        ],
        tree,
        env,
        'generate-types',
        log,
    )


def _thaw(root):
    if root.exists() and not root.is_symlink():
        for directory, dirs, names in os.walk(root):
            Path(directory).chmod(0o700)


import io
import tarfile

PRODUCT_PATHS = (
    'application',
    'contracts',
    'deployment',
    'editions',
    'integration',
    'modeling',
    'ui',
    'upstream',
)
SNAPSHOT_ROOTS = ('deployment', 'application/src', 'integration/src', 'editions/local/src')


def _private_directory(path):
    path = Path(path)
    if not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents)):
        raise ReleaseError('Absolute non-symlink directory required')
    if path.exists() and (not path.is_dir() or path.stat().st_uid != os.getuid()):
        raise ReleaseError('Foreign release directory')
    return path


def _git(checkout, *args):
    result = subprocess.run(['git', '-C', str(checkout), *args], capture_output=True, check=True)
    return result.stdout


def snapshot(
    checkout,
    releases_root,
    *,
    edition='local',
    mode='checkout',
    require_review=False,
    interpreter=None,
    warn=None,
):
    """Archive committed product bytes only; dirty edits are reported and excluded."""
    checkout, releases_root = _private_directory(checkout), _private_directory(releases_root)
    if edition != 'local' or mode not in ('checkout', 'frozen'):
        raise ReleaseError('Unsupported release edition or mode')
    if type(require_review) is not bool:
        raise ReleaseError('Review requirement must be explicit')
    if _git(checkout, 'rev-parse', '--show-toplevel').decode().strip() != str(checkout):
        raise ReleaseError('Snapshot requires the checkout root')
    loader = local_paths._installation_loader()
    for path in (checkout, releases_root):
        reason = loader.location_refusal(str(path))
        if reason:
            raise ReleaseError('Unsafe snapshot location: ' + str(reason))
    if releases_root.is_relative_to(checkout):
        raise ReleaseError('Release data must be outside the checkout')
    commit = _git(checkout, 'rev-parse', 'HEAD').decode().strip()
    dirty = _git(checkout, 'status', '--short', '--untracked-files=all').decode()
    if dirty:
        message = 'Uncommitted changes excluded from installed snapshot:\n' + dirty
        (warn or (lambda value: print(value, file=sys.stderr)))(message)
    archive = _git(checkout, 'archive', '--format=tar', commit, '--', *PRODUCT_PATHS)
    releases_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    staging = Path(tempfile.mkdtemp(prefix='.staging-', dir=releases_root))
    try:
        source = staging / 'source'
        source.mkdir(mode=0o700)
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            for member in tar:
                relative = _relative(member.name)
                if PurePosixPath(relative).parts[0] not in PRODUCT_PATHS:
                    raise ReleaseError('Archive member outside product paths')
                destination = source / relative
                if member.isdir():
                    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
                elif member.isfile():
                    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                    with destination.open('xb') as output:
                        output.write(tar.extractfile(member).read())
                    destination.chmod(0o700 if member.mode & 0o111 else 0o600)
                else:
                    raise ReleaseError('Non-regular archive member: ' + relative)
        files = scan(source)
        digest = tree_digest(files)
        release_id = edition + '-' + commit[:12] + '-' + digest[:16]
        manifest = dict(
            schema=MANIFEST_SCHEMA,
            release_id=release_id,
            edition=edition,
            mode=mode,
            source_commit=commit,
            checkout=str(checkout),
            require_review=require_review or mode == 'frozen',
            review_state=dict(state='reviewed', provisional_tasks=[]),
            selection=dict(polish_commits=[], binding_commits=[]),
            tree=dict(
                digest=digest,
                file_count=len(files),
                bytes=sum(f['size'] for f in files),
                files=files,
            ),
            runtime=dict(
                interpreter=str(interpreter or sys.executable), roots=list(SNAPSHOT_ROOTS)
            ),
            images={},
            build=dict(ui=None),
        )
        raw = canonical(manifest)
        _create_private(staging / 'manifest.json', raw)
        _create_private(staging / 'manifest.sha256', (sha256(raw) + '\n').encode())
        target = releases_root / release_id
        if target.exists():
            raise ReleaseError('Release snapshot already exists; never overwrite it')
        staging.rename(target)
        return dict(
            path=str(target),
            manifest_sha256=sha256(raw),
            release_id=release_id,
            source_commit=commit,
            dirty=dirty.splitlines(),
        )
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def require_checkout(manifest, checkout=None):
    """A retained checkout release never silently follows another commit."""
    if manifest.get('mode') != 'checkout':
        return
    root = _private_directory(checkout or manifest['checkout'])
    current = _git(root, 'rev-parse', 'HEAD').decode().strip()
    if current != manifest['source_commit']:
        raise ReleaseBindingError('source_changed: installed commit ' + manifest['source_commit'])


def seal(release_dir, expected_sha256, *, images, ui_build, application_build):
    """Record built identities before activation, without changing any snapshot source."""
    release_dir = Path(release_dir)
    manifest, _ = verify(release_dir, expected_sha256=expected_sha256)
    if 'source_commit' not in manifest or manifest['images']:
        raise ReleaseError('Only an unsealed committed snapshot can be sealed')
    active = release_dir.parent / 'active.json'
    if active.is_symlink() or (
        active.exists()
        and json.loads(active.read_bytes()).get('release_id') == manifest['release_id']
    ):
        raise ReleaseError('Active release is immutable')
    if set(images) != {'application', 'modeling', 'worker'} or any(
        not re.fullmatch(r'sha256:[0-9a-f]{64}', value) for value in images.values()
    ):
        raise ReleaseError('Exact application, modeling and worker image identities required')
    if application_build.get('image') != images['application']:
        raise ReleaseError('Application build identity differs from the image')
    inputs = application_build.get('inputs', {})
    if application_build.get('inputs_sha256') != sha256(
        json.dumps(inputs, sort_keys=True).encode()
    ):
        raise ReleaseError('Application build input digest mismatch')
    inventory = {f['path']: f['sha256'] for f in manifest['tree']['files']}
    expected_files = {
        f['path']: f['sha256']
        for f in manifest['tree']['files']
        if f['path'].startswith(('application/', 'contracts/', 'ui/'))
        and not set(PurePosixPath(f['path']).parts)
        & {'__pycache__', 'node_modules', 'dist', '.vite'}
    }
    for name in ('deployment/locks/tools.json', 'deployment/images/install_python.py'):
        expected_files[name] = inventory.get(name)
    expected_files['Dockerfile'] = inventory.get('deployment/application.Dockerfile')
    pins = json.loads((release_dir / 'source/deployment/pins.json').read_bytes())
    expected_bases = {key: pins[key] for key in ('base_image', 'node_base_image')}
    if (
        inputs != dict(files=expected_files, bases=expected_bases)
        or None in expected_files.values()
    ):
        raise ReleaseError('Application build input inventory differs from snapshot')
    for name, digest in inputs.get('files', {}).items():
        path = 'deployment/application.Dockerfile' if name == 'Dockerfile' else name
        if inventory.get(path) != digest:
            raise ReleaseError('Application build input differs from snapshot: ' + path)
    if not inputs.get('files'):
        raise ReleaseError('Application build input inventory is empty')
    ui_build = _private_directory(ui_build)
    files = scan(ui_build)
    if not any(f['path'] == 'index.html' for f in files):
        raise ReleaseError('Built UI entry point missing')
    target = release_dir / 'build/ui-dist'
    target.parent.mkdir(mode=0o700)
    shutil.copytree(ui_build, target)
    if scan(target) != files:
        raise ReleaseError('UI changed while sealing release')
    manifest['images'] = images
    manifest['build'] = dict(
        ui=dict(files=files, digest=tree_digest(files)), application=application_build
    )
    raw = canonical(manifest)
    # No active pointer can name this digest until activate verifies the complete record.
    for name, data in (('manifest.json', raw), ('manifest.sha256', (sha256(raw) + '\n').encode())):
        temporary = release_dir / ('.seal-' + uuid.uuid4().hex)
        _create_private(temporary, data)
        os.replace(temporary, release_dir / name)
    return sha256(raw)


def activate(release_dir, expected_sha256, *, reviews_root=None):
    """Verify a sealed release and atomically replace the private active pointer."""
    release_dir = _private_directory(release_dir)
    manifest, digest = verify(release_dir, expected_sha256=expected_sha256)
    require_checkout(manifest)
    if 'source_commit' not in manifest or not manifest['images'] or not manifest['build']['ui']:
        raise ReleaseError('Release must be built and sealed before activation')
    review = require_review(release_dir, manifest, digest, reviews_root=reviews_root)
    pointer = release_dir.parent / 'active.json'
    if pointer.is_symlink():
        raise ReleaseError('Unsafe active release pointer')
    record = dict(
        schema='hyprn-mvp.active-release/1',
        release_id=manifest['release_id'],
        manifest_sha256=digest,
        review=review,
    )
    temporary = pointer.parent / ('.active-' + uuid.uuid4().hex)
    _create_private(temporary, canonical(record))
    os.replace(temporary, pointer)
    return record


def active(releases_root, *, checkout=None):
    """Resolve and verify the active snapshot without building or attesting anything."""
    releases_root = _private_directory(releases_root)
    pointer = releases_root / 'active.json'
    if pointer.is_symlink():
        raise ReleaseError('Unsafe active release pointer')
    record = json.loads(pointer.read_bytes())
    if record.get('schema') != 'hyprn-mvp.active-release/1':
        raise ReleaseError('Unknown active release record')
    name = _relative(record['release_id'])
    if '/' in name:
        raise ReleaseError('Invalid active release identity')
    path = releases_root / name
    manifest, digest = verify(path, expected_sha256=record['manifest_sha256'])
    require_checkout(manifest, checkout)
    review = require_review(path, manifest, digest, reviews_root=releases_root / '.reviews')
    if review != record.get('review'):
        raise ReleaseBindingError('Active release review differs from activation')
    return path


def verify(
    release_dir,
    *,
    expected_sha256=None,
    retained=False,
    deep=False,
    contract_python=CONTRACT_PYTHON,
):
    """Exact manifest/tree/build verification; deep also regenerates public contracts."""
    release_dir = Path(release_dir)
    if not release_dir.is_absolute() or any(
        p.is_symlink() for p in (release_dir, *release_dir.parents)
    ):
        raise ReleaseError('Absolute non-symlink release directory required')
    # Retained = an immediate child of the durable releases root; superseded releases moved
    # under RELEASES_ROOT/.superseded/ (or anywhere else) stay verifiable evidence only.
    if (retained and RELEASES_ROOT is None) or (deep and contract_python is None):
        raise ReleaseBindingError(local_paths.unset_message())
    if retained and (release_dir.parent != RELEASES_ROOT):
        raise ReleaseError('Not a retained release under ' + str(RELEASES_ROOT))
    entries = {p.name for p in release_dir.iterdir()}
    if (
        not entries <= ALLOWED_RELEASE_ENTRIES
        or not {'manifest.json', 'manifest.sha256', 'source'} <= entries
    ):
        raise ReleaseError('Unexpected release directory entries')
    for name in ('manifest.json', 'manifest.sha256'):
        path = release_dir / name
        if path.is_symlink() or not path.is_file():
            raise ReleaseError('Unsafe release record: ' + name)
    raw = (release_dir / 'manifest.json').read_bytes()
    actual = sha256(raw)
    if (release_dir / 'manifest.sha256').read_text() != actual + '\n':
        raise ReleaseError('Manifest digest record mismatch')
    if expected_sha256 is not None and expected_sha256 != actual:
        raise ReleaseError('Manifest is not the qualified manifest ' + str(expected_sha256)[:16])
    manifest = json.loads(raw)
    if canonical(manifest) != raw or manifest.get('schema') != MANIFEST_SCHEMA:
        raise ReleaseError('Noncanonical or unknown manifest')
    if manifest['release_id'] != release_dir.name:
        raise ReleaseError('Release identity mismatch')
    state = manifest.get('review_state') or {}
    provisional = sorted(
        {c['task'] for c in manifest['selection']['polish_commits'] if c.get('review') != 'closed'}
    )
    if state.get('provisional_tasks') != provisional or state.get('state') != (
        'provisional' if provisional else 'reviewed'
    ):
        raise ReleaseError('Manifest review state is inconsistent with its recorded reviews')
    files = scan(release_dir / 'source')
    if files != manifest['tree']['files']:
        recorded = {f['path']: f for f in manifest['tree']['files']}
        actual_files = {f['path']: f for f in files}
        diff = sorted(set(recorded) ^ set(actual_files)) or sorted(
            p for p in recorded if recorded[p] != actual_files[p]
        )
        raise ReleaseError('Release source differs from manifest: ' + ', '.join(diff[:5]))
    expected_id = RELEASE_PREFIX + manifest['tree']['digest'][:16]
    if 'source_commit' in manifest:
        if (
            manifest.get('edition') != 'local'
            or manifest.get('mode') not in ('checkout', 'frozen')
            or not re.fullmatch(r'[0-9a-f]{40}', manifest['source_commit'])
            or type(manifest.get('require_review')) is not bool
            or manifest.get('runtime', {}).get('roots') != list(SNAPSHOT_ROOTS)
        ):
            raise ReleaseError('Invalid committed snapshot identity')
        expected_id = (
            'local-' + manifest['source_commit'][:12] + '-' + manifest['tree']['digest'][:16]
        )
    if tree_digest(files) != manifest['tree']['digest'] or manifest['release_id'] != expected_id:
        raise ReleaseError('Release tree digest mismatch')
    build = manifest['build'].get('ui')
    if build is not None:
        if (
            scan(release_dir / 'build/ui-dist') != build['files']
            or tree_digest(build['files']) != build['digest']
        ):
            raise ReleaseError('Retained UI build differs from manifest')
    elif 'build' in entries:
        raise ReleaseError('Unrecorded build output')
    if deep:
        home = Path(tempfile.mkdtemp(prefix='hyprn-mvp-release-verify-'))
        try:
            copy = home / 'tree'
            shutil.copytree(release_dir / 'source', copy)
            for path in GENERATED_PATHS:
                (copy / path).chmod(0o644)
            regenerate(copy, contract_python, home)
            for path in GENERATED_PATHS:
                if (copy / path).read_bytes() != (release_dir / 'source' / path).read_bytes():
                    raise ReleaseError('Stale generated artifact: ' + path)
        finally:
            _thaw(home)
            shutil.rmtree(home, ignore_errors=True)
    return manifest, actual


@dataclass
class Binding:
    bound: bool
    script: str
    source: Path = None
    manifest_path: Path = None
    manifest_sha256: str = None
    release_id: str = None
    roots: tuple = ()
    removed_sys_path: list = field(default_factory=list)
    inventory: dict = field(default_factory=dict)

    def record(self):
        return dict(
            bound=self.bound,
            release_id=self.release_id,
            manifest_path=str(self.manifest_path) if self.manifest_path else None,
            manifest_sha256=self.manifest_sha256,
            source_root=str(self.source) if self.source else None,
            roots=[str(r) for r in self.roots],
            removed_sys_path=self.removed_sys_path,
        )


ACTIVE = None


class _ReleaseFinder:
    """Resolve guarded project modules only from the selected roots."""

    def __init__(self, roots, guarded, deny):
        self.roots, self.guarded, self.deny = [str(r) for r in roots], guarded, deny

    def find_spec(self, fullname, path=None, target=None):
        if fullname.partition('.')[0] not in self.guarded:
            return None
        if self.deny:
            raise ImportError('Unbound read-only command may not import project module ' + fullname)
        spec = importlib.machinery.PathFinder.find_spec(
            fullname, self.roots if '.' not in fullname else path, target
        )
        if spec is None:
            raise ModuleNotFoundError(fullname + ' is not in the selected release')
        locations = [spec.origin] if spec.origin else list(spec.submodule_search_locations or [])
        if not locations or not all(
            _inside(Path(p), [Path(r) for r in self.roots]) for p in locations
        ):
            raise ImportError(fullname + ' resolves outside the selected release')
        return spec


def _inside(path, roots):
    path = Path(os.path.realpath(path))
    return any(path == root or root in path.parents for root in roots)


def _project_path(entry):
    path = Path(entry or os.getcwd())
    try:
        # Package roots of any checkout are recognized by layout as well as by package name.
        return (
            (path / 'hyprn_mvp_app').is_dir()
            or (path / 'hyprn_mvp_integration').is_dir()
            or (path / 'hyprn_mvp_local').is_dir()
            or (path.name == 'src' and path.parent.name in ('application', 'integration', 'local'))
            or (path / 'release.py').is_file()
            or (path / 'dispatch_runtime.py').is_file()
        )
    except OSError:
        return False


def _guarded_names(deployment):
    return set(PROJECT_PACKAGES) | {p.stem for p in Path(deployment).glob('*.py')}


def _check_loaded(roots, guarded, script):
    for name, module in list(sys.modules.items()):
        if name.partition('.')[0] not in guarded and name != '__main__':
            continue
        locations = (
            [getattr(module, '__file__', None)]
            if getattr(module, '__file__', None)
            else list(getattr(module, '__path__', []) or [])
        )
        if name == '__main__' and not locations:
            continue
        if not locations or not all(_inside(Path(p), roots) for p in locations):
            raise ReleaseBindingError(name + ' already imported outside the selected release')


def _foreign_checkout(cwd, source):
    for directory in (cwd, *cwd.parents):
        if directory != source and (directory / 'deployment/dispatch_runtime.py').is_file():
            return True
    return False


def bind(script_file, *, effectful, project_imports, expected_sha256=None, require_source_cwd=None):
    """Bind this process to the release containing script_file; fail before effects."""
    global ACTIVE
    script = Path(os.path.abspath(script_file))
    if script.resolve() != script:
        raise ReleaseBindingError('Entry script path must be canonical')
    source = script.parents[1]
    release_dir = source.parent
    manifest_path = release_dir / 'manifest.json'
    if source.name != 'source' or not manifest_path.is_file():
        if effectful or project_imports:
            raise ReleaseBindingError(
                'Unselected source checkout: use the manifest-qualified command of a '
                'retained release'
            )
        removed = [
            p for p in sys.path if _project_path(p) and Path(p or '.').resolve() != script.parent
        ]
        sys.path[:] = [p for p in sys.path if p not in removed]
        sys.meta_path.insert(0, _ReleaseFinder([], set(PROJECT_PACKAGES), deny=True))
        ACTIVE = Binding(bound=False, script=str(script), removed_sys_path=removed)
        return ACTIVE
    env_sha = os.environ.get(ENV_SHA)
    for value in (expected_sha256, env_sha):
        if value is not None and not re.fullmatch(r'[0-9a-f]{64}', value):
            raise ReleaseBindingError('Invalid manifest digest qualifier')
    if expected_sha256 and env_sha and expected_sha256 != env_sha:
        raise ReleaseBindingError('Mixed release binding: inherited manifest digest differs')
    if effectful and not (expected_sha256 or env_sha):
        raise ReleaseBindingError(
            'Effectful command requires the manifest SHA256 qualifier (' + ENV_SHA + ')'
        )
    try:
        manifest, actual = verify(
            release_dir, expected_sha256=expected_sha256 or env_sha, retained=effectful
        )
    except ReleaseBindingError:
        raise
    except (ReleaseError, OSError, ValueError, KeyError) as error:
        raise ReleaseBindingError(str(error)) from error
    if 'source_commit' in manifest:
        require_checkout(manifest)
    if effectful and manifest['review_state']['state'] != 'reviewed':
        raise ReleaseBindingError(
            'Effectful command requires a reviewed release (review_state '
            + repr(manifest['review_state']['state'])
            + '); read-only use only'
        )
    env_manifest = os.environ.get(ENV_MANIFEST)
    if env_manifest is not None and env_manifest != str(manifest_path):
        raise ReleaseBindingError('Mixed release binding: inherited manifest path differs')
    env_root = os.environ.get(ENV_ROOT)
    if env_root is not None and env_root != str(source):
        raise ReleaseBindingError('Mixed release binding: inherited release root differs')
    if effectful and sys.executable != manifest['runtime']['interpreter']:
        raise ReleaseBindingError('Effectful command requires the reviewed interpreter')
    cwd = Path(os.getcwd()).resolve()
    if (effectful if require_source_cwd is None else require_source_cwd) and cwd != source:
        raise ReleaseBindingError('Run effectful commands from the selected release source root')
    if _foreign_checkout(cwd, source):
        raise ReleaseBindingError('Working directory is inside another source checkout')
    roots = tuple(source / r for r in manifest['runtime']['roots'])
    guarded = _guarded_names(source / 'deployment')
    _check_loaded(roots, guarded, script)
    removed = [p for p in sys.path if _project_path(p) and Path(p or '.').resolve() not in roots]
    sys.path[:] = [str(r) for r in roots] + [
        p for p in sys.path if p not in removed and Path(p or '.').resolve() not in roots
    ]
    sys.meta_path[:] = [f for f in sys.meta_path if not isinstance(f, _ReleaseFinder)]
    sys.meta_path.insert(0, _ReleaseFinder(roots, guarded, deny=False))
    os.environ[ENV_MANIFEST], os.environ[ENV_SHA], os.environ[ENV_ROOT] = (
        str(manifest_path),
        actual,
        str(source),
    )
    ACTIVE = Binding(
        bound=True,
        script=str(script),
        source=source,
        manifest_path=manifest_path,
        manifest_sha256=actual,
        release_id=manifest['release_id'],
        roots=roots,
        removed_sys_path=removed,
        inventory={f['path']: f['sha256'] for f in manifest['tree']['files']},
    )
    return ACTIVE


def entrypoint(script_file, *, read_only, project_imports, expected_sha256=None):
    """Manager __main__ guard: refusal exits 2 before any allocation or effect."""
    try:
        return bind(
            script_file,
            effectful=not read_only,
            project_imports=project_imports,
            expected_sha256=expected_sha256,
        )
    except ReleaseError as error:
        print('Release binding refused: ' + str(error), file=sys.stderr)
        raise SystemExit(2)


def module_record(name, *, imported=True):
    binding = ACTIVE
    if binding is None or not binding.bound:
        raise ReleaseBindingError('No active release binding')
    if imported:
        module = sys.modules.get(name) or importlib.import_module(name)
        file = Path(module.__file__).resolve()
    else:
        spec = importlib.util.find_spec(name)
        file = Path(spec.origin).resolve()
    if not _inside(file, binding.roots):
        raise ReleaseBindingError(name + ' resolved outside the selected release')
    relative = file.relative_to(binding.source).as_posix()
    actual = sha256(file.read_bytes())
    if binding.inventory.get(relative) != actual:
        raise ReleaseBindingError(name + ' bytes differ from the release manifest')
    return dict(file=str(file), relative=relative, sha256=actual)


def process_evidence(modules=EVIDENCE_MODULES, *, imported=True):
    binding = ACTIVE
    if binding is None or not binding.bound:
        raise ReleaseBindingError('No active release binding')
    ps = subprocess.run(
        ['/bin/ps', '-ww', '-p', str(os.getpid()), '-o', 'command='], capture_output=True, text=True
    ).stdout.strip()
    typed = sys.argv[0] if sys.argv else ''
    if binding.script not in ps and not (
        typed and typed in ps and os.path.abspath(typed) == binding.script
    ):
        raise ReleaseBindingError(
            'Process command identity does not name the bound release entry script'
        )
    return dict(
        release_id=binding.release_id,
        manifest_sha256=binding.manifest_sha256,
        manifest_path=str(binding.manifest_path),
        source_root=str(binding.source),
        pid=os.getpid(),
        ppid=os.getppid(),
        cwd=os.getcwd(),
        executable=sys.executable,
        argv=list(sys.argv),
        ps_command=ps,
        sys_path_head=sys.path[: len(binding.roots)],
        removed_sys_path=binding.removed_sys_path,
        environment={k: os.environ.get(k) for k in (ENV_MANIFEST, ENV_SHA, ENV_ROOT)},
        modules={name: module_record(name, imported=imported) for name in modules},
    )


def write_evidence(directory, record, prefix, token=None):
    """Create-only evidence named <prefix>-<pid>-<token>.json (a reused pid never collides).

    A starting manager passes its own one-shot token so it can read exactly its child's record;
    otherwise a fresh random token is used. An existing name is never replaced.
    """
    directory = Path(directory)
    if not directory.is_absolute() or any(p.is_symlink() for p in (directory, *directory.parents)):
        raise ReleaseBindingError('Unsafe release evidence directory')
    token = uuid.uuid4().hex if token is None else token
    if not isinstance(token, str) or not re.fullmatch(r'[0-9a-f]{32}', token):
        raise ReleaseBindingError('Invalid release evidence token')
    if not re.fullmatch(r'[a-z][a-z-]*', prefix):
        raise ReleaseBindingError('Invalid release evidence prefix')
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = directory / (prefix + '-' + str(int(record['pid'])) + '-' + token + '.json')
    with path.open('x') as output:
        output.write(json.dumps(record, indent=2, sort_keys=True) + '\n')
    return path


def application_inventory_matches(identity_hashes, manifest):
    """Container source inventory equals the manifest AND its served ui-dist equals the
    release's retained UI build; a release without a retained build is never servable."""
    expected = manifest['inventories']['runtime_sources']['application']
    ui = (manifest.get('build') or {}).get('ui')
    if ui is None:
        return False
    served = {
        k[len('ui-dist/') :]: v for k, v in identity_hashes.items() if k.startswith('ui-dist/')
    }
    source = {k: v for k, v in identity_hashes.items() if not k.startswith('ui-dist/')}
    return source == expected and served == {f['path']: f['sha256'] for f in ui['files']}


def copy_ui_build(release_dir, manifest, target):
    """Copy the retained UI into a build context, checking every file hash."""
    ui = (manifest.get('build') or {}).get('ui')
    if ui is None:
        raise ReleaseError('Release has no retained UI build; it cannot be served')
    source = Path(release_dir) / 'build/ui-dist'
    if scan(source) != ui['files'] or tree_digest(ui['files']) != ui['digest']:
        raise ReleaseError('Retained UI build differs from manifest')
    target = Path(target)
    target.mkdir(parents=True, mode=0o700)
    for item in ui['files']:
        raw = (source / _relative(item['path'])).read_bytes()
        if len(raw) != item['size'] or sha256(raw) != item['sha256']:
            raise ReleaseError('Retained UI build changed while copying: ' + item['path'])
        destination = target / item['path']
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
    copied = {f['path']: f['sha256'] for f in scan(target)}
    if copied != {f['path']: f['sha256'] for f in ui['files']}:
        raise ReleaseError('Copied UI build differs from manifest')
    return dict(files=len(copied), digest=ui['digest'])


# ---- Recorded independent review (create-only, digest-named) ------------------------------
REVIEWS_ROOT = None if RELEASES_ROOT is None else RELEASES_ROOT / '.reviews'
REVIEW_SCHEMA = 'hyprn-mvp.release-review/1'
REVIEW_RECORD = 'review-record.json'
MAX_REVIEW_FILES = 16
MAX_REVIEW_BYTES = 4 * 1024 * 1024
_INDEPENDENT_REVIEW = re.compile(r'\bindependent\b[^.;]*\breview', re.I)


def review_required(manifest):
    """A release whose allowlist basis cites an independent review needs its recorded review."""
    if manifest.get('require_review') is True or manifest.get('mode') == 'frozen':
        return True
    selection = manifest.get('selection') or {}
    bases = [
        str(item.get('basis', ''))
        for key in ('polish_commits', 'binding_commits')
        for item in selection.get(key) or []
    ]
    return any(_INDEPENDENT_REVIEW.search(basis) for basis in bases)


def _reviews_directory(reviews_root, release_id):
    if reviews_root is None and REVIEWS_ROOT is None:
        raise ReleaseBindingError(local_paths.unset_message())
    reviews_root = Path(REVIEWS_ROOT if reviews_root is None else reviews_root)
    if not reviews_root.is_absolute() or any(
        p.is_symlink() for p in (reviews_root, *reviews_root.parents)
    ):
        raise ReleaseBindingError('Absolute non-symlink review root required')
    if not re.fullmatch(
        r'(?:release-[0-9a-f]{16}|local-[0-9a-f]{12}-[0-9a-f]{16})', str(release_id)
    ):
        raise ReleaseBindingError('Invalid release id for a review record')
    return reviews_root, reviews_root / release_id


def _create_private(path, raw):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as output:
        output.write(raw)


def record_review(
    release_dir, manifest_sha256, review_files, reference, *, reviews_root=None, retained=True
):
    """Create-only record of the independent review evidence for exactly one release manifest.

    Every review file must be a regular file naming the release id; its bytes are copied
    (0600, digest-named) next to a canonical record (0600). Activation and start then require it
    (require_review) and name its digest in their records. Never replaced or extended."""
    manifest, actual = verify(release_dir, expected_sha256=manifest_sha256, retained=retained)
    if not isinstance(reference, str) or not reference.strip() or len(reference) > 512:
        raise ReleaseBindingError('Review reference required (1-512 characters)')
    files = [Path(f) for f in review_files]
    if not 0 < len(files) <= MAX_REVIEW_FILES:
        raise ReleaseBindingError('Between 1 and %d review files required' % MAX_REVIEW_FILES)
    loaded = []
    for path in files:
        if not path.is_absolute() or path.is_symlink() or not path.is_file():
            raise ReleaseBindingError(
                'Review evidence must be an absolute regular file: ' + str(path)
            )
        raw = path.read_bytes()
        if not raw or len(raw) > MAX_REVIEW_BYTES:
            raise ReleaseBindingError('Review evidence size out of bounds: ' + str(path))
        if manifest['release_id'] not in raw.decode('utf-8', errors='replace'):
            raise ReleaseBindingError(
                'Review evidence does not name the release '
                + manifest['release_id']
                + ': '
                + str(path)
            )
        name = sha256(raw) + '-' + re.sub(r'[^A-Za-z0-9._-]', '_', path.name)[:120]
        loaded.append((name, raw, path))
    if len({name for name, _, _ in loaded}) != len(loaded):
        raise ReleaseBindingError('Duplicate review evidence')
    root, directory = _reviews_directory(reviews_root, manifest['release_id'])
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        directory.mkdir(mode=0o700)
    except FileExistsError:
        raise ReleaseBindingError(
            'Review already recorded for ' + manifest['release_id'] + '; it is create-only'
        ) from None
    for name, raw, _ in loaded:
        _create_private(directory / name, raw)
    import datetime

    record = dict(
        schema=REVIEW_SCHEMA,
        release_id=manifest['release_id'],
        manifest_sha256=actual,
        reference=reference,
        files=[
            dict(name=name, source=str(path), sha256=sha256(raw), size=len(raw))
            for name, raw, path in loaded
        ],
        recorded_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    )
    raw = canonical(record)
    _create_private(directory / REVIEW_RECORD, raw)
    return dict(record, path=str(directory / REVIEW_RECORD), record_sha256=sha256(raw))


def require_review(release_dir, manifest, manifest_sha256, *, reviews_root=None):
    """Refuse start/activation of a release citing an independent review without its record."""
    if not review_required(manifest):
        return dict(required=False)
    _, directory = _reviews_directory(reviews_root, manifest['release_id'])
    path = directory / REVIEW_RECORD
    if any(p.is_symlink() for p in (directory, path, *directory.parents)):
        raise ReleaseBindingError('Unsafe review record path')
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        raise ReleaseBindingError(
            'Release ' + manifest['release_id'] + ' cites an independent review but has no '
            'recorded review; run the reviewed record-review step first'
        ) from None
    record = json.loads(raw)
    if (
        canonical(record) != raw
        or record.get('schema') != REVIEW_SCHEMA
        or record.get('release_id') != manifest['release_id']
        or record.get('manifest_sha256') != manifest_sha256
        or not record.get('files')
    ):
        raise ReleaseBindingError('Review record does not name this release manifest')
    for item in record['files']:
        name = _relative(item['name'])
        if '/' in name:
            raise ReleaseBindingError('Invalid review evidence name')
        copy = directory / name
        if (
            copy.is_symlink()
            or not copy.is_file()
            or not item['name'].startswith(item['sha256'] + '-')
            or sha256(copy.read_bytes()) != item['sha256']
            or copy.stat().st_size != item['size']
        ):
            raise ReleaseBindingError('Recorded review evidence changed: ' + item['name'])
    return dict(
        required=True,
        path=str(path),
        record_sha256=sha256(raw),
        reference=record['reference'],
        files=len(record['files']),
    )


# ---- Opt-in immutability of retained releases (chflags uchg) -----------------------------
CHFLAGS = '/usr/bin/chflags'


def immutable_state(release_dir):
    release_dir = Path(release_dir)
    entries = immutable = 0
    for directory, dirs, names in os.walk(release_dir):
        for item in [Path(directory)] + [Path(directory) / n for n in names]:
            entries += 1
            info = os.lstat(item)
            immutable += (
                bool(getattr(info, 'st_flags', 0) & getattr(stat, 'UF_IMMUTABLE', 0))
                if sys.platform == 'darwin'
                else not bool(info.st_mode & 0o222)
            )
    return dict(entries=entries, immutable=immutable)


def make_immutable(release_dir, expected_sha256, *, retained=True):
    """Explicit opt-in: verify, then `chflags -R uchg` the whole release. Reversal (needed before
    a quarantine rename) is the documented manual `chflags -R nouchg <release>`."""
    release_dir = Path(release_dir)
    manifest, actual = verify(release_dir, expected_sha256=expected_sha256, retained=retained)
    if sys.platform != 'darwin':
        for directory, dirs, names in os.walk(release_dir, topdown=False):
            for name in names:
                path = Path(directory) / name
                path.chmod(path.stat().st_mode & ~0o222)
            Path(directory).chmod(0o500)
        state = immutable_state(release_dir)
        return dict(
            release_id=manifest['release_id'],
            manifest_sha256=actual,
            immutable_entries=state['immutable'],
            clear_command="chmod -R u+w '" + str(release_dir) + "'",
        )
    result = subprocess.run(
        [CHFLAGS, '-R', 'uchg', str(release_dir)],
        capture_output=True,
        text=True,
        env=dict(PATH=SAFE_PATH, LC_ALL='C'),
    )
    if result.returncode:
        raise ReleaseError('chflags uchg failed: ' + result.stderr.strip()[:300])
    state = immutable_state(release_dir)
    if state['immutable'] != state['entries']:
        raise ReleaseError('Not every release entry became immutable')
    return dict(
        release_id=manifest['release_id'],
        manifest_sha256=actual,
        immutable_entries=state['immutable'],
        clear_command=CHFLAGS + " -R nouchg '" + str(release_dir) + "'",
    )


def release_commands(release_dir, manifest_sha):
    """The operator commands of one retained release; every script they name is a binding path."""
    release_dir = Path(release_dir)
    source = release_dir / 'source'
    data_root, execution = local_paths.data_root(), local_paths.execution_root()
    # HOME is the operator's own ($HOME); HYPRN_MVP_DATA_ROOT is the resolved data root.
    env = (
        'env -i HOME="$HOME" PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin '
        f"PYTHONDONTWRITEBYTECODE=1 AIIDA_PATH='{execution}/aiida' "
        f"HYPRN_MVP_DATA_ROOT='{data_root}' "
        f"{ENV_SHA}={manifest_sha} '{local_paths.native_python()}' -B"
    )
    cd = f"cd '{source}' && "

    def script(relative, arguments):
        if relative not in RELEASE_BINDING_PATHS:
            raise ReleaseError('Not a release binding entry point: ' + relative)
        return cd + f"{env} '{source}/{relative}' {arguments}"

    return dict(
        verify=script('deployment/release.py', f'verify --expected-sha256 {manifest_sha}'),
        status=script('deployment/dispatch_runtime.py', '--status'),
        start=script('deployment/dispatch_runtime.py', '--start'),
        stop=script('deployment/dispatch_runtime.py', '--stop'),
        bind_launch_worker=script('deployment/native_environment.py', 'bind-launch-worker')
        + '  # executor stopped, after the backup',
        check_launch_worker=script('deployment/native_environment.py', 'check-launch-worker'),
        check_launcher_evidence=script(
            'deployment/native_environment.py', 'check-launcher-evidence'
        )
        + '  # after the first launch',
        build_worker=script('deployment/execution_runtime.py', 'build-worker'),
        attest_worker=script('deployment/execution_runtime.py', 'attest'),
        # Create-only review record; start requires it when the release cites an independent review.
        record_review=script(
            'deployment/release.py',
            f'record-review --expected-sha256 {manifest_sha} '
            "--reference '<review reference>' --review '<absolute review file naming "
            "the release id>'"
            ' [--review ...]',
        ),
        require_review=script(
            'deployment/release.py', f'require-review --expected-sha256 {manifest_sha}'
        ),
        make_immutable=script(
            'deployment/release.py',
            f"make-immutable --release '{release_dir}' --expected-sha256 {manifest_sha}",
        )
        + '  # optional opt-in hardening; never automatic',
        quarantine=(
            f"/usr/bin/chflags -R nouchg '{release_dir}'  # only if made immutable; "
            f'then rename into '
            f"'{release_dir.parent}/.superseded/' (contents byte-identical, still verifiable)"
        ),
        never_run=(
            'never run against a populated workspace: native_environment.py '
            'prepare/extend (they overwrite '
            'launch-worker/selected.json/runtime.json/locks), initialize_stores.py bootstrap, '
            'application_runtime.py setup --rebuild (ungated), '
            'or setup --rebuild of a missing container'
        ),
        rollback=(
            'stop with this release, then run the start command of the retained compatible release '
            'with its own manifest SHA256; after new-format writes use read-only '
            'forward repair instead'
        ),
        emergency_stop=(
            'manual, only when no manager can stop the executor (different/older source): read '
            f"'{execution}/executor.json' (pid, identity); require `/bin/ps -ww -p "
            f'<pid> -o command=` and '
            '`-o lstart=` to equal identity.command/started exactly; then `kill -TERM '
            '<pid>`; wait up to 10 s; '
            'confirm --status running:false and that executor.lock can be locked; record evidence. '
            'Never SIGKILL, never signal any other pid.'
        ),
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = parser.add_subparsers(dest='operation', required=True)
    p = sub.add_parser('verify')
    p.add_argument('--release', type=Path)
    p.add_argument('--expected-sha256', required=True)
    p.add_argument('--deep', action='store_true')
    sub.add_parser('probe')
    p = sub.add_parser('exec-module')
    p.add_argument('--expected-sha256', required=True)
    p.add_argument('--check-only', action='store_true')
    p.add_argument('module', choices=sorted(EXEC_MODULES))
    p.add_argument('args', nargs=argparse.REMAINDER)
    p = sub.add_parser('commands')
    p.add_argument('--release', type=Path, required=True)
    p = sub.add_parser('record-review')
    p.add_argument('--expected-sha256', required=True)
    p.add_argument('--reference', required=True)
    p.add_argument('--review', type=Path, action='append', required=True)
    p = sub.add_parser('require-review')
    p.add_argument('--expected-sha256', required=True)
    p = sub.add_parser('make-immutable')
    p.add_argument('--release', type=Path, required=True)
    p.add_argument('--expected-sha256', required=True)
    args = parser.parse_args(argv)
    try:
        if args.operation == 'verify':
            if args.release is None:
                binding = bind(
                    __file__,
                    effectful=False,
                    project_imports=False,
                    expected_sha256=args.expected_sha256,
                )
                if not binding.bound:
                    raise ReleaseBindingError(
                        'verify without --release must run inside a retained release'
                    )
                release = binding.manifest_path.parent
            else:
                release = args.release
            manifest, digest = verify(release, expected_sha256=args.expected_sha256, deep=args.deep)
            print(
                json.dumps(
                    dict(
                        release_id=manifest['release_id'],
                        manifest_sha256=digest,
                        verified=True,
                        files=manifest['tree']['file_count'],
                        deep=args.deep,
                    )
                )
            )
        elif args.operation == 'probe':
            bind(__file__, effectful=False, project_imports=True)
            print(json.dumps(process_evidence(), indent=2, sort_keys=True))
        elif args.operation == 'exec-module':
            # AiiDA runs the launcher in its job directory, so no source-root cwd here.
            bind(
                __file__,
                effectful=not args.check_only,
                project_imports=True,
                expected_sha256=args.expected_sha256,
                require_source_cwd=False,
            )
            evidence = process_evidence((args.module,), imported=False)
            rest = args.args[1:] if args.args[:1] == ['--'] else args.args
            evidence['module_argv'] = [evidence['modules'][args.module]['file'], *rest]
            if args.check_only:
                print(json.dumps(evidence, indent=2, sort_keys=True))
                return 0
            directory = os.environ.get(ENV_EVIDENCE)
            if directory:
                write_evidence(
                    directory, evidence, 'launcher-binding'
                )  # fresh token: never collides
            import runpy

            sys.argv = evidence['module_argv']
            runpy.run_module(args.module, run_name='__main__', alter_sys=True)
        elif args.operation == 'commands':
            manifest, digest = verify(args.release)
            print(json.dumps(release_commands(args.release, digest), indent=2))
        elif args.operation == 'record-review':
            # Effect limited to the create-only review record of the bound, retained release.
            binding = bind(
                __file__,
                effectful=True,
                project_imports=False,
                expected_sha256=args.expected_sha256,
            )
            print(
                json.dumps(
                    record_review(
                        binding.manifest_path.parent,
                        binding.manifest_sha256,
                        args.review,
                        args.reference,
                    ),
                    indent=2,
                )
            )
        elif args.operation == 'require-review':
            binding = bind(
                __file__,
                effectful=False,
                project_imports=False,
                expected_sha256=args.expected_sha256,
            )
            if not binding.bound:
                raise ReleaseBindingError('require-review must run inside a retained release')
            manifest, digest = verify(
                binding.manifest_path.parent, expected_sha256=args.expected_sha256, retained=True
            )
            print(json.dumps(require_review(binding.manifest_path.parent, manifest, digest)))
        elif args.operation == 'make-immutable':
            print(json.dumps(make_immutable(args.release, args.expected_sha256), indent=2))
    except ReleaseError as error:
        print(
            (
                'Release binding refused: '
                if isinstance(error, ReleaseBindingError)
                else 'Release refused: '
            )
            + str(error),
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
