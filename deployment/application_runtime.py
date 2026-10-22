"""Manage only the owned application container; no execution or legacy access.

The installation decides every identity (deployment/local_paths.py): the store
<data root>/application, the published port (HYPRN_MVP_PORT, else the configuration's
ports.app), the container, public network and ownership label names
(hyprn-mvp-<edition>-<id8>-<role>, labelled with the installation's owner), the container
engine endpoint of every docker command and the owner's sign-in name provisioned with a new
store. The development data root keeps its fixed names, the ambient engine and the sign-in name
"owner". The commands refuse while the store or the port is unresolved. Every file of the build
context gets an explicit mode, whatever the caller's umask.
"""

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import sys
import subprocess
import tempfile
from uuid import uuid4
import release as release_binding
import local_paths
import modeling_runtime

ROOT = local_paths.application_root(required=False)
REPO = Path(__file__).resolve().parents[1]
NAMES = local_paths.component_names()
NAME = NAMES['application']
OWNER = NAMES['application_owner']
# Development application port (HYPRN_MVP_PORT); None while unset, refused by main().
PORT = local_paths.port(required=False)
PUBLIC_NETWORK = NAMES['public_network']
# Sign-in name of the owner provisioned with a new store.
USERNAME = local_paths.owner_username()
# Environment of every docker command: the installation's engine endpoint, or None (ambient).
DOCKER_ENVIRONMENT = local_paths.docker_environment()
UI_DIST = None if ROOT is None else ROOT / 'ui'


def run(*args, input=None):
    result = subprocess.run(
        args, input=input, text=True, capture_output=True, check=True, env=DOCKER_ENVIRONMENT
    )
    return result.stdout.strip()


def inspect():
    result = subprocess.run(
        ['docker', 'inspect', NAME], text=True, capture_output=True, env=DOCKER_ENVIRONMENT
    )
    if result.returncode:
        if 'no such' in result.stderr.lower():
            return None
        raise RuntimeError('Unable to inspect owned application')
    return json.loads(result.stdout)[0]


def guard(info):
    if info['Name'] != '/' + NAME or info['Config']['Labels'].get(modeling_runtime.LABEL) != OWNER:
        raise ValueError('Application resource is not owned')


def bound_release():
    binding = release_binding.ACTIVE
    return binding if binding is not None and binding.bound else None


def ui_dist():
    """Served UI build: the bound release's retained build/ui-dist, never the shared
    workspace dist; unbound fixture use keeps UI_DIST."""
    binding = bound_release()
    return binding.manifest_path.parent / 'build/ui-dist' if binding is not None else UI_DIST


def release_manifest(binding):
    manifest = json.loads(binding.manifest_path.read_bytes())
    if (manifest.get('build') or {}).get('ui') is None:
        raise ValueError('Selected release has no retained UI build; it cannot be served')
    return manifest


def hashes():
    paths = [
        p
        for group in ('application/src', 'contracts/schemas')
        for p in (REPO / group).rglob('*')
        if p.is_file() and '__pycache__' not in str(p)
    ]
    paths += [
        REPO / path
        for path in (
            'application/requirements.lock',
            'deployment/application.Dockerfile',
            'deployment/application_runtime.py',
            'deployment/pins.json',
            'deployment/locks/tools.json',
            'deployment/images/install_python.py',
        )
    ]
    result = {
        str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)
    }
    dist = ui_dist()
    for p in sorted(dist.rglob('*')):
        if p.is_file():
            result['ui-dist/' + str(p.relative_to(dist))] = hashlib.sha256(
                p.read_bytes()
            ).hexdigest()
    ui_paths = [p for group in ('ui/src', 'ui/public') for p in (REPO / group).rglob('*')]
    ui_paths += [
        REPO / 'ui' / name
        for name in (
            'index.html',
            'package.json',
            'package-lock.json',
            'vite.config.ts',
            'tsconfig.json',
        )
    ]
    for p in sorted(ui_paths):
        if p.is_file():
            result[str(p.relative_to(REPO))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return result


def container_inventory():
    """Read actual running-container bytes; identity.json is never a content oracle."""
    script = """
import hashlib,json
from pathlib import Path
result={}
for folder,prefix in (('/app/application','application/'),('/app/contracts','contracts/'),
                      ('/app/ui','ui-dist/')):
    root=Path(folder)
    if not root.is_dir() or root.is_symlink():
        raise ValueError('Missing runtime source root')
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError('Symlink in runtime source')
        if path.is_file():
            result[prefix+path.relative_to(root).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
        elif not path.is_dir():
            raise ValueError('Special runtime source file')
print(json.dumps(result,sort_keys=True))
"""
    info = inspect()
    if not info:
        raise ValueError('Application container missing')
    guard(info)
    if not info['State']['Running']:
        raise ValueError('Application container is not running')
    return json.loads(run('docker', 'exec', NAME, 'python', '-I', '-B', '-c', script))


def require_release_inventory(binding):
    """Bind exact container content and image/build identity to the verified release."""
    manifest, _ = release_binding.verify(
        binding.manifest_path.parent, expected_sha256=binding.manifest_sha256
    )
    identity = json.loads((ROOT / 'identity.json').read_bytes())
    info = inspect()
    if not info:
        raise ValueError('Application container missing')
    guard(info)
    if info['Image'] != identity.get('image'):
        raise ValueError('Application image identity differs')
    if manifest.get('images') and info['Image'] != manifest['images']['application']:
        raise ValueError('Application image differs from selected release')
    if 'source_commit' in manifest and identity.get('build') != manifest['build']['application']:
        raise ValueError('Application build differs from selected release')
    expected = {
        f['path']: f['sha256']
        for f in manifest['tree']['files']
        if f['path'].startswith(('application/', 'contracts/'))
    }
    ui = (manifest.get('build') or {}).get('ui')
    if ui is None:
        raise ValueError('Selected release has no retained UI build')
    expected.update({'ui-dist/' + f['path']: f['sha256'] for f in ui['files']})
    actual = container_inventory()
    if actual != expected:
        raise ValueError('Application container source or served UI inventory differs from release')
    return dict(
        image=info['Image'],
        files=len(actual),
        inventory_sha256=release_binding.sha256(release_binding.canonical(actual)),
    )


def check(allow_source_change=False):
    info = inspect()
    if not info:
        raise ValueError('Application not initialized')
    guard(info)
    identity = json.loads((ROOT / 'identity.json').read_text())
    if (not allow_source_change and identity['source_hashes'] != hashes()) or info[
        'Image'
    ] != identity['image']:
        raise ValueError('Application source/image drift')
    if not allow_source_change and identity.get('build', {}).get('inputs') != build_inputs():
        raise ValueError('Application build input drift; rebuild from reviewed sources')
    binding = bound_release()
    if binding is not None and not allow_source_change:
        require_release_inventory(binding)
    h = info['HostConfig']
    if (
        info['Config']['User'] != '10002:10002'
        or not h['ReadonlyRootfs']
        or h['Privileged']
        or h['CapDrop'] != ['ALL']
        or h['CapAdd']
    ):
        raise ValueError('Application isolation mismatch')
    if 'no-new-privileges:true' not in h['SecurityOpt']:
        raise ValueError('Privilege escalation permitted')
    if set(info['NetworkSettings']['Networks']) != {modeling_runtime.NETWORK, PUBLIC_NETWORK}:
        raise ValueError('Application network mismatch')
    mounts = {
        m['Destination']: (m['Source'], m['RW']) for m in info['Mounts'] if m['Type'] == 'bind'
    }
    expected = {
        '/store': (str(ROOT / 'application'), True),
        '/run/model.key': (str(modeling_runtime.DEFAULT_ROOT / 'credentials/model.key'), False),
    }
    if mounts != expected:
        raise ValueError('Unexpected application mounts')
    if h['PortBindings'] != {'8000/tcp': [{'HostIp': '127.0.0.1', 'HostPort': str(PORT)}]}:
        raise ValueError('Unexpected public bind')
    return dict(
        container=NAME,
        image=info['Image'],
        running=info['State']['Running'],
        origin=f'http://127.0.0.1:{PORT}',
        store=str(ROOT / 'application'),
    )


def build_evidence_directory(parent=None):
    parent = Path(parent) if parent is not None else ROOT / 'evidence/builds'
    for path in (parent, *parent.parents):
        if path.is_symlink():
            raise ValueError('Unsafe build evidence path')
    parent = Path(os.path.abspath(parent))
    if not (
        parent.is_relative_to(local_paths.scratch_root())
        or parent.is_relative_to(ROOT / 'evidence')
    ):
        raise ValueError('Build evidence must remain off-cloud')
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    result = parent / str(uuid4())
    result.mkdir(mode=0o700)
    return result


def write_identity(raw):
    """identity.json is replaced atomically (private temporary in ROOT, then os.replace)."""
    temporary = ROOT / ('.identity-' + uuid4().hex + '.json')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'wb') as output:
            output.write(raw)
        os.replace(temporary, ROOT / 'identity.json')
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


BUILD_EXCLUDED = frozenset({'__pycache__', 'node_modules', 'dist', '.vite', '.pytest_cache'})


def build_source_files(root):
    """Refuse local secrets/stores and links before handing any source byte to Docker."""
    paths = []
    for path in root.rglob('*'):
        parts = path.relative_to(root).parts
        if set(parts) & BUILD_EXCLUDED:
            continue
        name = path.name.lower()
        private = (
            name == '.env'
            or name.startswith('.env.')
            or name in {'credentials', 'secrets', '.git'}
            or name.endswith(('.key', '.pem', '.p12', '.pfx', '.db', '.log'))
            or '.sqlite' in name
            or '.db-' in name
            or '.local.' in name
            or ('service-account' in name or 'service_account' in name)
            and name.endswith('.json')
        )
        if path.is_symlink() or private:
            raise ValueError('Unsafe application build input; remove local material from source')
        if path.is_file():
            paths.append(path)
    return sorted(paths)


def build_inputs():
    """Inventory every source byte supplied to the build, including UI and recipe inputs."""
    pins = json.loads((REPO / 'deployment/pins.json').read_bytes())
    bases = {name: pins[name] for name in ('base_image', 'node_base_image')}
    paths = []
    for name in ('application', 'contracts', 'ui'):
        paths.extend(build_source_files(REPO / name))
    paths.extend(
        REPO / name
        for name in (
            'deployment/locks/tools.json',
            'deployment/images/install_python.py',
        )
    )
    files = {
        str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)
    }
    recipe = REPO / 'deployment/application.Dockerfile'
    files['Dockerfile'] = hashlib.sha256(recipe.read_bytes()).hexdigest()
    return dict(bases=bases, files=files)


def build_image(evidence, *, no_cache=False):
    """Build from source and reviewed registry inputs, retaining the exact build inventory."""
    expected = build_inputs()
    bases = expected['bases']
    with tempfile.TemporaryDirectory(prefix='build-', dir=evidence) as temporary:
        context = Path(temporary)
        for name in ('application', 'contracts', 'ui'):
            for source in build_source_files(REPO / name):
                target = context / source.relative_to(REPO)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target, follow_symlinks=False)
        for name in ('deployment/locks/tools.json', 'deployment/images/install_python.py'):
            target = context / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REPO / name, target)
        shutil.copyfile(REPO / 'deployment/application.Dockerfile', context / 'Dockerfile')
        modeling_runtime.readable_context(context)
        inputs = dict(
            bases=bases,
            files={
                str(path.relative_to(context)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in sorted(context.rglob('*'))
                if path.is_file()
            },
        )
        if inputs != expected:
            raise ValueError('Application source changed while staging build inputs')
        digest = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
        tag = 'hyprn-mvp-application:' + digest[:16]
        command = [
            'docker',
            'build',
            '--target',
            'local',
            '--pull=false',
            *(['--no-cache'] if no_cache else []),
            '--build-arg',
            'PYTHON_IMAGE=' + bases['base_image'],
            '--build-arg',
            'NODE_IMAGE=' + bases['node_base_image'],
            '-t',
            tag,
            str(context),
        ]
        built = subprocess.run(command, text=True, capture_output=True, env=DOCKER_ENVIRONMENT)
        (evidence / 'build.log').write_text(built.stdout)
        (evidence / 'build.stderr').write_text(built.stderr)
        (evidence / 'result.json').write_text(json.dumps({'exit': built.returncode}) + '\n')
        built.check_returncode()
    if build_inputs() != expected:
        raise ValueError('Application source changed during image build')
    image = run('docker', 'image', 'inspect', tag, '--format', '{{.Id}}')
    run('docker', 'tag', image, 'hyprn-mvp-application:built-' + image.removeprefix('sha256:'))
    identity = dict(image=image, inputs=inputs, inputs_sha256=digest)
    (evidence / 'build-identity.json').write_text(json.dumps(identity, indent=2) + '\n')
    return identity


def retain_image_ui(image):
    """Retain image-built bytes for identity checks; never use host output as a build input."""
    script = (
        "import base64,json; from pathlib import Path; root=Path('/app/ui'); "
        'print(json.dumps({str(p.relative_to(root)):base64.b64encode(p.read_bytes()).decode() '
        "for p in root.rglob('*') if p.is_file()}))"
    )
    assets = json.loads(
        run(
            'docker',
            'run',
            '--rm',
            '--network=none',
            '--read-only',
            '--cap-drop=ALL',
            '--security-opt=no-new-privileges:true',
            image,
            'python',
            '-B',
            '-c',
            script,
        )
    )
    if 'index.html' not in assets:
        raise ValueError('Application image has no UI entry point')
    decoded = {}
    for name, encoded in assets.items():
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Unsafe application UI inventory')
        decoded[name] = base64.b64decode(encoded, validate=True)
    destination = ui_dist()
    binding = bound_release()
    if binding is not None:
        expected = {
            str(p.relative_to(destination)): p.read_bytes()
            for p in destination.rglob('*')
            if p.is_file()
        }
        if decoded != expected:
            raise ValueError('Image-built UI differs from the selected release')
        return
    if any(p.is_symlink() for p in (destination, *destination.parents)):
        raise ValueError('Unsafe retained UI path')
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(mode=0o700)
    for name, raw in decoded.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        target.write_bytes(raw)


def setup(rebuild=False, build_evidence_dir=None):
    if bound_release() is not None:
        release_manifest(bound_release())  # refuse a release without a UI build first
    modeling_runtime.check(modeling_runtime.DEFAULT_ROOT)
    if ROOT.is_symlink():
        raise ValueError('Unsafe runtime root')
    ROOT.mkdir(exist_ok=True, mode=0o700)
    ROOT.chmod(0o700)
    for name in ('application', 'credentials', 'evidence'):
        path = ROOT / name
        if path.is_symlink():
            raise ValueError('Unsafe runtime child')
        path.mkdir(exist_ok=True, mode=0o700)
    net = modeling_runtime.inspect(PUBLIC_NETWORK, 'network')
    if net is None:
        run(
            'docker',
            'network',
            'create',
            '--label',
            modeling_runtime.LABEL + '=' + OWNER,
            PUBLIC_NETWORK,
        )
    elif net.get('Labels', {}).get(modeling_runtime.LABEL) != OWNER:
        raise ValueError('Public network identity mismatch')
    existing = inspect()
    if existing:
        guard(existing)
        if not rebuild:
            check()
            run('docker', 'start', NAME)
            return check()
    elif (ROOT / 'identity.json').exists():
        raise ValueError('Owned application container missing; preserve store and investigate')
    build = build_image(build_evidence_directory(build_evidence_dir))
    image = build['image']
    retain_image_ui(image)
    store = ROOT / 'application'
    if not existing:
        if list(store.iterdir()):
            raise ValueError('Refusing unowned nonempty application store')
        password_file = ROOT / 'credentials/owner.password'
        fd = os.open(password_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        password = secrets.token_urlsafe(32)
        with os.fdopen(fd, 'w') as f:
            f.write(password + '\n')
        # The owner's sign-in name is an argument and the password is read from standard input.
        bootstrap = (
            'import sys,os\n'
            'from hyprn_mvp_app.store import Store\n'
            'from hyprn_mvp_app.auth import Auth\n'
            "s=Store('/store/application.sqlite')\n"
            "Auth(s,'').provision(sys.argv[1],sys.stdin.read().strip())\n"
            "os.chown('/store/application.sqlite',10002,10002)\n"
            "os.chown('/store',10002,10002)\n"
        )
        run(
            'docker',
            'run',
            '--rm',
            '-i',
            '--network=none',
            '--user',
            '0:0',
            '--mount',
            f'type=bind,src={store},dst=/store',
            image,
            'python',
            '-c',
            bootstrap,
            USERNAME,
            input=password,
        )
    else:
        run('docker', 'stop', NAME)
        run('docker', 'rm', NAME)

    def create():
        run(
            'docker',
            'run',
            '-d',
            '--name',
            NAME,
            '--label',
            modeling_runtime.LABEL + '=' + OWNER,
            '--user',
            '10002:10002',
            '--read-only',
            '--cap-drop=ALL',
            '--security-opt=no-new-privileges:true',
            '--memory=512m',
            '--cpus=1',
            '--pids-limit=64',
            '--restart=no',
            '--network',
            PUBLIC_NETWORK,
            '-p',
            f'127.0.0.1:{PORT}:8000',
            '--tmpfs',
            '/tmp:rw,noexec,nosuid,size=16m',
            '--mount',
            f'type=bind,src={store},dst=/store',
            '--mount',
            f'type=bind,src={modeling_runtime.DEFAULT_ROOT}/credentials/model.key,dst=/run/model.key,readonly',
            '-e',
            'HYPRN_MVP_APP_STORE=/store/application.sqlite',
            '-e',
            f'HYPRN_MVP_ORIGIN=http://127.0.0.1:{PORT}',
            '-e',
            f'HYPRN_MVP_MODEL_URL=http://{modeling_runtime.CONTAINER}:3000/modeling/1',
            '-e',
            'HYPRN_MVP_MODEL_KEY_FILE=/run/model.key',
            image,
        )
        run('docker', 'network', 'connect', modeling_runtime.NETWORK, NAME)
        identity = dict(
            owner=OWNER,
            container=NAME,
            image=image,
            build=build,
            source_hashes=hashes(),
            store=str(store),
        )
        write_identity((json.dumps(identity, indent=2) + '\n').encode())
        return check()

    return create()


def main():
    local_paths.require(ROOT)
    local_paths.require(PORT, local_paths.PORT)
    parser = argparse.ArgumentParser()
    parser.add_argument('operation', choices=['setup', 'check', 'stop'])
    parser.add_argument('--rebuild', action='store_true')
    parser.add_argument('--build-evidence-dir', type=Path)
    args = parser.parse_args()
    if args.build_evidence_dir and args.operation != 'setup':
        parser.error('Build evidence requires setup')
    if args.operation == 'setup':
        result = setup(args.rebuild, args.build_evidence_dir)
    elif args.operation == 'check':
        result = check()
    else:
        result = check()
        run('docker', 'stop', NAME)
        result['running'] = False
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    # check is read-only and import-free; setup/stop require the selected release.
    release_binding.entrypoint(__file__, read_only=sys.argv[1:] == ['check'], project_imports=False)
    main()
