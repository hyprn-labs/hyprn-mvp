"""Set up, check and stop the owned modeling service deployment; never migrate stores.

The compose file is JSON-compatible YAML. Setup has no implicit upgrade, delete, reset or
execution action. Every location is below HYPRN_MVP_DATA_ROOT and the WhatsOpt source base
image is HYPRN_MVP_MODELING_SOURCE_IMAGE (deployment/local_paths.py); the commands refuse while
a value they need is unset, and a build refuses a source image that differs from the reviewed
pin in deployment/pins.json.

The command line acts only on the installation (INSTALLATION). A test fixture may set up its own
deployment (scoped_deployment) below its scratch scope: the same reviewed recipe settings, image
and checks, with only the root, the container and network names and the ownership label
replaced by the scope's. Guarded tests never run docker compose, so a scope's container and
network are created with docker from the reviewed recipe (start_scoped), and the scope may use
an existing image only when it was built from the current reviewed sources (reviewed_image).
"""
import argparse
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import secrets
import shutil
import stat
import subprocess
import tempfile
import tarfile
import pwd
import sys
from typing import NamedTuple
import uuid
import local_paths

REPO = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = local_paths.modeling_root(required=False)
CONTAINER = 'hyprn-mvp-modeling'
NETWORK = 'hyprn-mvp-private'
LABEL = 'org.hyprn-mvp.owner'
OWNER = 'hyprn-mvp-modeling'
SOURCE_IMAGE = local_paths.modeling_source_image(required=False)
RUBY_IMAGE = 'ruby@sha256:bceec7582aaa80630bb51a04e2df3af658e64c0640c174371776928ad3bd57b4'
ARCHIVE_SHA256 = '4937188df6ea12daa8a2b00767005e3649d2974ab6e634409f7756043ef0b360'
# Content-addressed location of the pinned upstream archive: an owner-private read-only copy
# below the verified upstream cache. upstream_archive() is the one resolver and fails closed
# on any absence, type, permission or SHA256 mismatch.
ARCHIVE_ROOT = local_paths.upstream_archive_root(required=False)
ARCHIVE = None if ARCHIVE_ROOT is None else ARCHIVE_ROOT / ARCHIVE_SHA256 / 'WhatsOpt.tar.gz'
RECIPE = REPO / 'deployment/modeling-compose.yaml'
# Corresponding-source notice folder of every modeling image (deployment/modeling.Dockerfile).
SOURCE_NOTICE = '/usr/share/hyprn-mvp-modeling-source'


class Deployment(NamedTuple):
    """One owned modeling deployment: its root, container, internal network and the ownership
    label (key and value) carried by the container and the network."""
    root: object
    container: str
    network: str
    label: str
    owner: str


INSTALLATION = Deployment(DEFAULT_ROOT, CONTAINER, NETWORK, LABEL, OWNER)
TEST_SCOPE_LABEL = 'org.hyprn-mvp.test-scope'


def scoped_deployment(root, scope_id):
    """The deployment owned by one test scope: container hyprn-mvp-test-<scope8>-modeling on its
    own internal network, labelled with the scope id, rooted at a new folder below the scratch
    root. It never names the installation's root, container or network."""
    scope_id = str(uuid.UUID(str(scope_id)))
    root = Path(root)
    scratch = local_paths.scratch_root()
    if not root.is_absolute() or root.resolve() != root or scratch not in root.parents:
        raise ValueError('A scoped modeling deployment root must be an absolute folder below the scratch root')
    prefix = 'hyprn-mvp-test-' + scope_id.replace('-', '')[:8]
    return Deployment(root, prefix + '-modeling', prefix + '-private', TEST_SCOPE_LABEL, scope_id)

START = '''#!/bin/sh
set -eu
cd /native
if [ ! -e /store/model.sqlite3 ]; then
  bundle exec rails db:schema:load db:migrate
  touch /store/initialized
elif [ ! -f /store/initialized ]; then
  echo 'Refusing unmanaged or incomplete store' >&2
  exit 1
fi
exec bundle exec rails server -b 0.0.0.0 -p 3000
'''

def checked_root(path, deployment=INSTALLATION):
    path = Path(path)
    if path != deployment.root or path.resolve() != deployment.root:
        raise ValueError('Only the exact nonsymlink off-cloud modeling root is allowed')
    if path.exists() and (path.stat().st_uid != os.getuid() or path.stat().st_mode & 0o077):
        raise ValueError('Runtime root must belong to caller and be private (0700)')
    for child in ('modeling', 'credentials', 'evidence', 'identity.json'):
        if (path / child).is_symlink():
            raise ValueError('Runtime children must not be symlinks')
    return path

def run(*args, input=None):
    return subprocess.run(args, input=input, check=True, capture_output=True, text=True).stdout.strip()

@contextlib.contextmanager
def base_reference(image):
    """A transient tag naming the verified base image id for one build (BuildKit cannot build
    FROM a bare image id). It is removed afterwards and the base keeps its other references; a
    tag that became the base's only reference stays, so the base image is never deleted."""
    reference = 'hyprn-mvp-build-base:' + uuid.uuid4().hex[:16]
    run('docker', 'tag', image, reference)
    try:
        yield reference
    finally:
        tags = json.loads(run('docker', 'image', 'inspect', image))[0].get('RepoTags') or []
        if reference in tags and len(tags) > 1:
            run('docker', 'image', 'rm', '--no-prune', reference)

def inspect(name, kind='container'):
    result = subprocess.run(['docker', kind, 'inspect', name], capture_output=True, text=True)
    if result.returncode:
        if 'No such' in result.stderr or f'network {name} not found' in result.stderr: return None
        raise RuntimeError(result.stderr)
    return json.loads(result.stdout)[0]

def assert_owned(info, kind, deployment=INSTALLATION):
    expected = deployment.container if kind == 'container' else deployment.network
    labels = info.get('Config', {}).get('Labels', {}) if kind == 'container' else info.get('Labels', {})
    if info.get('Name', '').lstrip('/') != expected or labels.get(deployment.label) != deployment.owner:
        raise ValueError('Resource identity/ownership mismatch; refusing action')

def source_hashes():
    paths = ['deployment/modeling.Dockerfile', 'deployment/modeling_policy.rb', 'deployment/modeling-compose.yaml', 'deployment/modeling_runtime.py', 'modeling/provenance.md', 'modeling/generate_unit_catalog.py', 'modeling/rehearsal.py', 'contracts/schemas/model.schema.json', 'contracts/schemas/execution.schema.json', 'integration/worker-requirements.lock']
    paths += sorted(str(p.relative_to(REPO)) for p in (REPO / 'upstream/whatsopt-patches').glob('*.patch'))
    return {p: hashlib.sha256((REPO / p).read_bytes()).hexdigest() for p in paths}

def check(root, *, allow_source_change=False, deployment=INSTALLATION):
    root = checked_root(root, deployment)
    identity = json.loads((root / 'identity.json').read_text())
    if identity.get('owner') != deployment.owner or identity.get('container') != deployment.container or identity.get('network') != deployment.network or identity.get('runtime') != str(root):
        raise ValueError('Deployment identity mismatch')
    if not allow_source_change and identity['source_hashes'] != source_hashes():
        raise ValueError('Deployment source changed; explicit reviewed rebuild required')
    model = inspect(deployment.container); net = inspect(deployment.network, 'network')
    if model is None or net is None: raise ValueError('Owned resource missing')
    assert_owned(model, 'container', deployment); assert_owned(net, 'network', deployment)
    host = model['HostConfig']
    if model['Image'] != identity['image'] or model['Config']['User'] != '10001:10001':
        raise ValueError('Unexpected modeling image or user')
    if not host['ReadonlyRootfs'] or host['Privileged'] or host['CapAdd'] or host['CapDrop'] != ['ALL']:
        raise ValueError('Unsafe effective privileges')
    if 'no-new-privileges:true' not in host['SecurityOpt'] or host['PortBindings']:
        raise ValueError('Unsafe security options or published endpoint')
    if set(model['NetworkSettings']['Networks']) != {deployment.network} or not net['Internal']:
        raise ValueError('Modeling network must be internal and exclusive')
    expected = {'/store': (str(root / 'modeling'), True), '/run/model.key': (str(root / 'credentials/model.key'), False), '/run/rails.key': (str(root / 'credentials/rails.key'), False)}
    mounts = {m['Destination']: (m['Source'], m['RW']) for m in model['Mounts'] if m['Type'] == 'bind'}
    if mounts != expected or any(m['Type'] not in ('bind','tmpfs') for m in model['Mounts']):
        raise ValueError('Unexpected modeling store/credential mount')
    if host['PidsLimit'] != 128 or host['Memory'] != 768 * 1024 * 1024 or host['NanoCpus'] != 1000000000:
        raise ValueError('Resource limits changed')
    if not allow_source_change and host['Tmpfs'] != {'/tmp': 'rw,noexec,nosuid,size=192m,mode=1777', '/native/tmp': 'rw,noexec,nosuid,size=32m,uid=10001,gid=10001'}:
        raise ValueError('Scratch limits changed')
    return {'container': deployment.container, 'image': model['Image'], 'running': model['State']['Running'], 'private_network': deployment.network, 'candidate_execution': 'blocked_pending_plan_01_12_consumer_attestation'}

def stage_modeling_contract(ctx):
    """Materialize the audited adapter patch chain, never stale image source.

    Only the adapter file is replayed here; native generator/template hunks
    remain applied by the existing Dockerfile to its pinned source image.
    """
    service = 'app/services/modeling_contract.rb'
    text = (REPO / 'upstream/whatsopt-patches/040-modeling-contract.patch').read_text()
    section = text.split('+++ b/' + service + '\n', 1)[1].split('\n--- ', 1)[0]
    lines = section.splitlines()
    import re
    match = re.fullmatch(r'@@ -0,0 \+1,(\d+) @@', lines[0])
    if not match or any(not line.startswith('+') for line in lines[1:]) or int(match[1]) != len(lines)-1:
        raise ValueError('Invalid audited adapter addition')
    with tempfile.TemporaryDirectory(prefix='adapter-', dir=ctx) as temporary:
        stage = Path(temporary); target = stage / service
        target.parent.mkdir(parents=True)
        target.write_text('\n'.join(line[1:] for line in lines[1:]) + '\n')
        for name in ('050-native-generation.patch', '060-ui-discovery.patch', '070-assumptions-evidence.patch', '080-unit-declarations.patch', '090-quantity-definitions.patch'):
            patch = (REPO / 'upstream/whatsopt-patches' / name).read_text()
            if name == '090-quantity-definitions.patch':
                headers = [line for line in patch.splitlines() if line.startswith(('--- ', '+++ '))]
                if headers != ['--- a/' + service, '+++ b/' + service]:
                    raise ValueError('Unexpected quantity patch sections')
            start = patch.index('--- a/' + service + '\n')
            end = patch.find('\n--- ', start + 1)
            patch = patch[start:] if end == -1 else patch[start:end] + '\n'
            result = subprocess.run(['patch', '--batch', '--fuzz=0', '--forward', '-p1'], input=patch,
                                    cwd=stage, capture_output=True, text=True)
            (ctx / (name + '.adapter.log')).write_text(result.stdout + result.stderr)
            if result.returncode or any(word in (result.stdout + result.stderr).lower() for word in ('fuzz', 'offset')):
                raise ValueError('Audited adapter patch chain failed: ' + name)
        destination = ctx / 'modeling_contract.rb'
        shutil.copyfile(target, destination)
    return destination


def patch_sections(text):
    """Split one unified diff into (old path, new path, section text) by counting hunk lines.

    Refuses any line outside a file header or a hunk, so a section boundary is never guessed
    from a removed line that happens to start with dashes."""
    import re
    lines = text.splitlines(keepends=True)
    sections, index = [], 0
    while index < len(lines):
        if not (lines[index].startswith('--- ') and index + 1 < len(lines) and lines[index + 1].startswith('+++ ')):
            raise ValueError('Unexpected patch line outside a file section')
        start = index
        old, new = lines[index][4:].rstrip('\n'), lines[index + 1][4:].rstrip('\n')
        index += 2
        if index >= len(lines) or not lines[index].startswith('@@ '):
            raise ValueError('Patch file section without a hunk')
        while index < len(lines) and lines[index].startswith('@@ '):
            match = re.match(r'@@ -\d+(?:,(\d+))? \+\d+(?:,(\d+))? @@', lines[index])
            if not match:
                raise ValueError('Invalid hunk header')
            remove = 1 if match[1] is None else int(match[1])
            add = 1 if match[2] is None else int(match[2])
            index += 1
            while remove or add:
                if index >= len(lines):
                    raise ValueError('Truncated hunk')
                tag = lines[index][:1]
                index += 1
                if tag == '\\':
                    continue
                if tag in (' ', '\n'):
                    remove, add = remove - 1, add - 1
                elif tag == '-':
                    remove -= 1
                elif tag == '+':
                    add -= 1
                else:
                    raise ValueError('Invalid hunk line')
                if remove < 0 or add < 0:
                    raise ValueError('Hunk length mismatch')
            while index < len(lines) and lines[index].startswith('\\'):
                index += 1
        sections.append((old, new, ''.join(lines[start:index])))
    return sections


# Retained native files that the ordered patches 010-040 create or change. The pinned source
# image carries an earlier build of them; every build replays them from the pinned upstream
# archive and these patches (zero fuzz, no offset), so the image holds exactly the patched
# bytes and patches 050-090 apply to them. Files of 010-040 that the deployment policy removes
# or rewrites (controllers other than the contract controller, views, scripts, tests, the
# authoring service, routes) and the schema copy (replaced from contracts/schemas) are not
# replayed.
REPLAYED_SOURCES = (
    ('020-authoring.patch', 'app/models/analysis.rb'),
    ('030-configuration.patch', 'app/lib/whats_opt/openmdao_generator.rb'),
    ('030-configuration.patch', 'app/lib/whats_opt/python_utils.rb'),
    ('030-configuration.patch', 'db/migrate/20261008160000_add_hyprn_mvp_study_boundary.rb'),
    ('040-modeling-contract.patch', 'app/controllers/modeling_contract_controller.rb'),
    ('040-modeling-contract.patch', 'app/models/modeling_command.rb'),
    ('040-modeling-contract.patch', 'app/models/modeling_identity.rb'),
    ('040-modeling-contract.patch', 'app/models/modeling_revision.rb'),
    ('040-modeling-contract.patch', 'app/services/modeling_contract.rb'),
    ('040-modeling-contract.patch', 'config/initializers/modeling_filter.rb'),
    ('040-modeling-contract.patch', 'config/initializers/modeling_request_bounds.rb'),
    ('040-modeling-contract.patch', 'config/modeling.units.json'),
    ('040-modeling-contract.patch', 'db/migrate/20261008175500_create_modeling_contract.rb'),
)
# A replayed migration supersedes the source image's migration of the same version, whatever
# file name that earlier build gave it (the build removes db/migrate/<version>_*.rb first).
REPLAYED_MIGRATION_VERSIONS = ('20261008160000', '20261008175500')


def stage_replayed_sources(ctx, upstream):
    """Write every REPLAYED_SOURCES file below ctx/replay: upstream bytes plus the file's
    sections of the named patch, applied with zero fuzz and no offset."""
    with tarfile.open(fileobj=io.BytesIO(upstream)) as archive:
        members = {str(Path(*Path(m.name).parts[1:])): m for m in archive.getmembers()
                   if m.isfile() and len(Path(m.name).parts) > 1}
        originals = {path: archive.extractfile(members[path]).read()
                     for _, path in REPLAYED_SOURCES if path in members}
    replay = ctx / 'replay'
    for name, path in REPLAYED_SOURCES:
        sections = [text for old, new, text in patch_sections((REPO / 'upstream/whatsopt-patches' / name).read_text())
                    if new == 'b/' + path and old in ('a/' + path, '/dev/null')]
        if len(sections) != 1:
            raise ValueError('Replayed source must have exactly one section: ' + name + ' ' + path)
        creates = sections[0].startswith('--- /dev/null\n')
        if creates == (path in originals):
            raise ValueError('Replayed source origin mismatch: ' + path)
        with tempfile.TemporaryDirectory(prefix='replay-', dir=ctx) as temporary:
            stage = Path(temporary)
            if not creates:
                (stage / path).parent.mkdir(parents=True, exist_ok=True)
                (stage / path).write_bytes(originals[path])
            result = subprocess.run(['patch', '--batch', '--fuzz=0', '--forward', '-p1'], input=sections[0],
                                    cwd=stage, capture_output=True, text=True)
            output = result.stdout + result.stderr
            if result.returncode or any(word in output.lower() for word in ('fuzz', 'offset')):
                raise ValueError('Replayed source patch failed: ' + name + ' ' + path)
            destination = replay / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(stage / path, destination)
    return replay


def stage_assumptions_native_patch(ctx):
    """Replay only the native hunk; the adapter is materialized from 040–070.

    The pinned image has a historical adapter baseline. Replaying its adapter
    hunks is redundant and unsafe: the authoritative cumulative adapter replaces
    that file below. Preserve the full original patch in provenance/notices.
    """
    text = (REPO / 'upstream/whatsopt-patches/070-assumptions-evidence.patch').read_text()
    sections = text.split('\n--- a/')
    sections = [sections[0], *['--- a/' + part for part in sections[1:]]]
    paths = ('app/services/modeling_contract.rb', 'app/services/native_materializer.rb')
    if len(sections) != len(paths) or any(
            not section.startswith('--- a/' + path + '\n+++ b/' + path + '\n@@ ')
            for section, path in zip(sections, paths)):
        raise ValueError('Unexpected assumptions patch sections')
    destination = ctx / 'assumptions.patch'
    destination.write_text(sections[1])
    return destination


def stage_units_native_patch(ctx):
    """Closed 080 split: cumulative adapter plus once-only native/catalog hunks."""
    text = (REPO / 'upstream/whatsopt-patches/080-unit-declarations.patch').read_text()
    sections = text.split('\n--- a/')
    sections = [sections[0], *['--- a/' + part for part in sections[1:]]]
    paths = ('app/services/modeling_contract.rb', 'app/services/native_materializer.rb',
             'app/services/native_program.rb', 'config/modeling.units.json')
    if len(sections) != len(paths) or any(
            not section.startswith('--- a/' + path + '\n+++ b/' + path + '\n@@ ')
            for section, path in zip(sections, paths)):
        raise ValueError('Unexpected units patch sections')
    destination = ctx / 'units.patch'
    destination.write_text('\n'.join(sections[1:]))
    return destination


def upstream_archive(path=None):
    """Exact pinned upstream archive bytes from the reviewed location; no fallback.

    Refuses a symlink, non-regular file, foreign owner, group/other access or writable
    mode, then reads the bytes once (no-follow) and verifies the SHA256 pin. Callers use
    the returned bytes only, so the verified content is the staged content.
    """
    path = local_paths.require(ARCHIVE) if path is None else Path(path)
    try:
        info = os.lstat(path)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or info.st_mode & 0o077 or info.st_mode & 0o222):
            raise ValueError('Upstream archive is not an owner-private read-only file: ' + str(path))
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, 'rb') as stream:
            raw = stream.read()
    except OSError as error:
        raise ValueError('Upstream archive unavailable: ' + str(error)) from error
    if hashlib.sha256(raw).hexdigest() != ARCHIVE_SHA256:
        raise ValueError('Upstream archive identity mismatch')
    return io.BytesIO(raw)

# The public contract schemas are build inputs, bound by hash in the build identity; each
# prepared artifact records their identities (path, SHA-256, length) in this support record
# instead of carrying copies of their bytes. The modeling schema the service reads is still
# part of the patched inventory (config/modeling.schema.json).
SCHEMA_IDENTITY_SOURCES = ('contracts/schemas/model.schema.json', 'contracts/schemas/execution.schema.json')
SCHEMA_IDENTITY_FILE = 'schema-identities.json'


def support_sources():
    """Build inputs copied byte for byte into every artifact's provenance support set."""
    return [name for name in source_hashes() if not name.endswith('.patch') and name not in SCHEMA_IDENTITY_SOURCES]


def schema_identities():
    """Identity of every schema that the support set records instead of copying."""
    return dict(schema_version='1', schemas=[dict(path=name, sha256=hashlib.sha256((REPO / name).read_bytes()).hexdigest(),
                                                  size=len((REPO / name).read_bytes())) for name in SCHEMA_IDENTITY_SOURCES])


def stage_native_inputs(ctx):
    """Retain audited original bytes and every build input; no dependency fetch."""
    upstream = upstream_archive()
    prov = ctx / 'provenance-inputs'; prov.mkdir()
    (prov / 'upstream.tar.gz').write_bytes(upstream.getvalue())
    with tarfile.open(fileobj=upstream) as archive:
        for member in archive.getmembers():
            parts = Path(member.name).parts[1:]
            if not member.isfile() or not parts or '..' in parts: continue
            relative = Path(*parts)
            if str(relative).startswith(('app/lib/whats_opt/', 'app/models/')) or str(relative) in ('Gemfile.lock', 'LICENSE', 'db/schema.rb', 'VERSION'):
                destination = prov / 'upstream' / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(archive.extractfile(member).read())
    (prov / 'support').mkdir()
    for name in support_sources():
        shutil.copyfile(REPO / name, prov / 'support' / Path(name).name)
    (prov / 'support' / SCHEMA_IDENTITY_FILE).write_text(json.dumps(schema_identities(), indent=2, sort_keys=True) + '\n')
    shutil.copytree(REPO / 'upstream/whatsopt-patches', prov / 'patches')
    shutil.copyfile(REPO / 'upstream/whatsopt-patches/050-native-generation.patch', ctx / 'native.patch')
    shutil.copyfile(REPO / 'upstream/whatsopt-patches/060-ui-discovery.patch', ctx / 'discovery.patch')
    stage_assumptions_native_patch(ctx)
    stage_units_native_patch(ctx)
    shutil.copyfile(REPO / 'contracts/schemas/model.schema.json', ctx / 'modeling.schema.json')
    stage_replayed_sources(ctx, upstream.getvalue())
    stage_modeling_contract(ctx)

def source_image():
    """The reviewed WhatsOpt source base image; refused unless it is the pinned source image."""
    image = local_paths.modeling_source_image() if SOURCE_IMAGE is None else SOURCE_IMAGE
    if json.loads((REPO / 'deployment/pins.json').read_text())['modeling_source_image'] != image:
        raise ValueError('Modeling source image differs from the reviewed pin')
    if run('docker', 'image', 'inspect', '--format', '{{.Id}}', image) != image:
        raise ValueError('Source image identity mismatch')
    return image

def build(root=None, *, evidence=None):
    """Build the modeling image from the reviewed inputs; the build log goes to ``evidence``
    (default ``<root>/evidence``). Returns the image id."""
    evidence = Path(evidence) if evidence is not None else Path(root) / 'evidence'
    image = source_image()
    with tempfile.TemporaryDirectory(prefix='hyprn-mvp-modeling-build-', dir=local_paths.scratch_root()) as temp:
        ctx = Path(temp)
        stage_native_inputs(ctx)
        for src, dst in [('deployment/modeling.Dockerfile', 'Dockerfile'), ('deployment/modeling_policy.rb', 'modeling_policy.rb')]:
            shutil.copyfile(REPO / src, ctx / dst)
        (ctx / 'start.sh').write_text(START)
        notices = ctx / 'notices'; notices.mkdir()
        shutil.copytree(REPO / 'upstream/whatsopt-patches', notices / 'patches')
        for name in ('modeling/provenance.md', 'deployment/modeling_policy.rb', 'deployment/modeling.Dockerfile'):
            shutil.copyfile(REPO / name, notices / Path(name).name)
        (notices / 'source-identity.json').write_text(json.dumps({'upstream': json.loads((REPO / 'deployment/pins.json').read_text())['verified_sources']['WhatsOpt'], 'source_image': image, 'source_hashes': source_hashes()}, indent=2))
        # Image tags are hyprn-mvp-<role>:<first 16 hex of the build-input digest>.
        inputs = dict(source_image=image, ruby_image=RUBY_IMAGE, source_hashes=source_hashes())
        tag = 'hyprn-mvp-modeling:' + hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()[:16]
        with base_reference(image) as reference:
            result = subprocess.run(['docker', 'build', '--network', 'none', '--build-arg', 'SOURCE_IMAGE=' + reference, '--build-arg', 'RUBY_IMAGE='+RUBY_IMAGE, '-t', tag, str(ctx)], capture_output=True, text=True)
        (evidence / ('build-'+secrets.token_hex(4)+'.log')).write_text(result.stdout + result.stderr)
        result.check_returncode()
    return run('docker', 'image', 'inspect', '--format', '{{.Id}}', tag)

def compose_environment(root, image):
    """Clean compose environment: no inherited COMPOSE_*/DOCKER_* (project name, file, host,
    context) can redirect the owned deployment. Only PATH/HOME and the two reviewed inputs."""
    return {'PATH': os.environ.get('PATH', '/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:/usr/local/bin'),
            'HOME': os.environ.get('HOME', pwd.getpwuid(os.getuid()).pw_dir),
            'HYPRN_MVP_MODELING_ROOT': str(root), 'HYPRN_MVP_MODELING_IMAGE': image}

def reviewed_image(image):
    """An existing modeling image may back a deployment only when it is exactly the image of the
    current reviewed sources: its recorded source identity (the corresponding-source notice)
    names the reviewed source image and the current source hashes."""
    if run('docker', 'image', 'inspect', '--format', '{{.Id}}', image) != image:
        raise ValueError('Modeling image identity mismatch')
    recorded = json.loads(run('docker', 'run', '--rm', '--network', 'none', '--read-only', '--cap-drop', 'ALL',
                              '--security-opt', 'no-new-privileges', '--user', '10001:10001', '--entrypoint', 'cat',
                              image, SOURCE_NOTICE + '/source-identity.json'))
    if recorded.get('source_image') != source_image() or recorded.get('source_hashes') != source_hashes():
        raise ValueError('Modeling image was not built from the current reviewed sources; rebuild it')
    return image


# Recipe keys start_scoped reproduces; any other key fails closed instead of being dropped.
SCOPED_SERVICE_KEYS = frozenset({'image', 'container_name', 'labels', 'user', 'read_only', 'cap_drop', 'security_opt',
                                 'pids_limit', 'mem_limit', 'cpus', 'restart', 'networks', 'tmpfs', 'volumes'})


def start_scoped(root, image, log, deployment):
    """Create a test scope's network and container with docker from the reviewed recipe: every
    setting of the recipe's service and internal network, with the scope's names and label."""
    recipe = json.loads(RECIPE.read_text())
    service, network = recipe['services']['modeling'], recipe['networks']['model_private']
    if set(service) != SCOPED_SERVICE_KEYS or set(network) != {'name', 'internal', 'labels'} or service['networks'] != ['model_private']:
        raise ValueError('Unreviewed modeling recipe setting; refusing a scoped deployment')
    label = deployment.label + '=' + deployment.owner
    run('docker', 'network', 'create', *(['--internal'] if network['internal'] else []), '--label', label, deployment.network)
    mounts = []
    for volume in service['volumes']:
        if set(volume) - {'type', 'source', 'target', 'read_only'} or volume['type'] != 'bind':
            raise ValueError('Unreviewed modeling recipe volume')
        source = volume['source'].replace('${HYPRN_MVP_MODELING_ROOT}', str(root))
        mounts += ['--mount', 'type=bind,src=' + source + ',dst=' + volume['target'] + (',readonly' if volume.get('read_only') else '')]
    args = ['docker', 'run', '-d', '--name', deployment.container, '--label', label, '--network', deployment.network,
            '--user', service['user'], *(['--read-only'] if service['read_only'] else []),
            *[a for c in service['cap_drop'] for a in ('--cap-drop', c)],
            *[a for s in service['security_opt'] for a in ('--security-opt', s)],
            '--pids-limit', str(service['pids_limit']), '--memory', service['mem_limit'], '--cpus', str(service['cpus']),
            '--restart', service['restart'], *[a for s in service['tmpfs'] for a in ('--tmpfs', s)], *mounts, image]
    result = subprocess.run(args, capture_output=True, text=True)
    Path(log).write_text(result.stdout + result.stderr)
    return result.returncode


def compose_up(root, image, log, *options):
    """Create the owned modeling container/network from the exact image (no build, no pull).

    Every compose call goes through here, so none can inherit a redirecting environment."""
    result = subprocess.run(['docker', 'compose', '-f', str(RECIPE), 'up', '-d', '--no-build',
                             *options], env=compose_environment(root, image), capture_output=True, text=True)
    Path(log).write_text(result.stdout + result.stderr)
    return result.returncode


def setup(root, rebuild=False, *, deployment=INSTALLATION, image=None):
    """Set up (or start) the owned deployment. ``image``: an existing image built from the current
    reviewed sources, used instead of a build; a test scope's deployment is never rebuilt in place."""
    root = checked_root(root, deployment)
    if rebuild and (image is not None or deployment != INSTALLATION):
        raise ValueError('Only the installation is rebuilt in place, from its sources')
    if (root / 'identity.json').exists():
        check(root, allow_source_change=rebuild, deployment=deployment)
        if not rebuild:
            run('docker', 'start', deployment.container)
            return check(root, deployment=deployment)
        image = build(root)
        identity = json.loads((root / 'identity.json').read_text())
        # A rebuild never erases the evidence of an earlier rebuild or failure.
        evidence = Path(tempfile.mkdtemp(prefix='rebuild-', dir=root / 'evidence'))
        (evidence / 'identity-before.json').write_text(json.dumps(identity, indent=2)+'\n')
        identity.update(image=image, source_hashes=source_hashes())
        (evidence / 'identity-requested.json').write_text(json.dumps(identity, indent=2)+'\n')
        (root / 'identity.json').write_text(json.dumps(identity, indent=2)+'\n')
        returncode = compose_up(root, image, evidence / 'rebuild.log', '--force-recreate', 'modeling')
        (evidence / 'result.json').write_text(json.dumps({'returncode': returncode, 'image': image}, indent=2)+'\n')
        if returncode:
            raise ValueError('Modeling rebuild compose failed; evidence retained for diagnosis')
        return check(root, deployment=deployment)
    if root.exists() and any(root.iterdir()) and not ((root / '.setup-owner').is_file() and (root / '.setup-owner').read_text() == deployment.owner and not any((root / 'modeling').iterdir())):
        raise ValueError('Refuse adopting existing unowned runtime contents')
    # Inspect name collisions before creating files or touching resources.
    if inspect(deployment.container) is not None or inspect(deployment.network, 'network') is not None:
        raise ValueError('Refuse pre-existing resources without local deployment identity')
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    (root / '.setup-owner').write_text(deployment.owner)
    for sub in ('modeling', 'credentials', 'evidence'): (root / sub).mkdir(mode=0o700, exist_ok=True)
    # Host root and credentials directory are 0700; Docker receives only individual
    # immutable files. Readability inside the nonroot container is intentional.
    (root / 'modeling').chmod(0o777)
    for key in ('model.key', 'rails.key'):
        path = root / 'credentials' / key
        if not path.exists(): path.write_text(secrets.token_hex(64))
        path.chmod(0o444)
    image = build(root) if image is None else reviewed_image(image)
    # Identity precedes compose creation; failures retain evidence and require explicit
    # diagnosis, never automatic deletion or store reset.
    identity = {'owner': deployment.owner, 'container': deployment.container, 'network': deployment.network, 'image': image, 'source_image': source_image(), 'source_hashes': source_hashes(), 'runtime': str(root)}
    (root / 'identity.json').write_text(json.dumps(identity, indent=2)+'\n')
    start = compose_up if deployment == INSTALLATION else (lambda *a: start_scoped(*a, deployment))
    if start(root, image, root / 'evidence/setup.log'):
        raise ValueError('Modeling setup compose failed; evidence retained for diagnosis')
    return check(root, deployment=deployment)


def stop(root, *, deployment=INSTALLATION):
    """Stop only the owned modeling container after its identity check; stores and keys stay."""
    check(root, deployment=deployment)
    run('docker', 'stop', deployment.container)
    return check(root, deployment=deployment)


def main():
    local_paths.require(DEFAULT_ROOT)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['setup', 'check', 'stop'])
    parser.add_argument('--root', type=Path, default=DEFAULT_ROOT)
    parser.add_argument('--rebuild', action='store_true', help='Explicit reviewed rebuild of the owned deployment; preserves stores and keys')
    args = parser.parse_args()
    if args.rebuild and args.action != 'setup': parser.error('--rebuild requires setup')
    if args.action == 'setup': result = setup(args.root, rebuild=args.rebuild)
    else:
        result = stop(args.root) if args.action == 'stop' else check(args.root)
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    # check is read-only and import-free; setup and stop require the selected release.
    action = sys.argv[1] if len(sys.argv) > 1 else ''
    import release_binding
    release_binding.entrypoint(__file__, read_only=action == 'check', project_imports=action != 'check')
    main()
