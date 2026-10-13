"""Deployment hardening: managers and release binding.

Every root is a disposable directory under tmp_path; docker, HTTP, signals and the live runtime
are faked or refused. No test needs Git history.
"""
# Live-runtime fence (deployment/tests/live_fence.py): refuses live roots, live ports, docker, live entry points and real signals.
import sys as _fence_sys
from pathlib import Path as _FencePath
if str(_FencePath(__file__).resolve().parent) not in _fence_sys.path:
    _fence_sys.path.append(str(_FencePath(__file__).resolve().parent))
import live_fence  # noqa: E402
live_runtime_fence = live_fence.pytest_fixture('unit')
import ast
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import types

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'deployment'))
import release_binding as release  # noqa: E402
import application_runtime as app  # noqa: E402
import dispatch_runtime as dispatch  # noqa: E402
import modeling_runtime as modeling  # noqa: E402
import native_environment as native  # noqa: E402

INDEPENDENT = 'closed: verified through the independent code and security review of this delta'
PLAIN = 'closed: task checkpoints'


# ---- Synthetic retained releases (no Git, no selection pipeline) -------------------------

def make_release(releases_root, files=None, *, basis=PLAIN):
    """A minimal release that release.verify accepts: canonical manifest, exact tree."""
    files = files or {'deployment/release_binding.py': b'# release\n', 'ui/index.html': b'<html>\n'}
    releases_root = Path(releases_root)
    staging = releases_root / '.staging-test'
    for relative, raw in files.items():
        target = staging / 'source' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    tree = release.scan(staging / 'source')
    digest = release.tree_digest(tree)
    release_id = release.RELEASE_PREFIX + digest[:16]
    manifest = dict(schema=release.MANIFEST_SCHEMA, release_id=release_id,
                    review_state=dict(state='reviewed', provisional_tasks=[], note='synthetic'),
                    tree=dict(digest=digest, file_count=len(tree), bytes=sum(f['size'] for f in tree), files=tree),
                    selection=dict(polish_commits=[dict(commit='a' * 40, task='t', review='closed', basis=basis, paths=[])],
                                   binding_commits=[dict(commit='b' * 40, task='t', basis=PLAIN, paths=[])]),
                    build=dict(ui=None, reason='synthetic'))
    raw = release.canonical(manifest)
    (staging / 'manifest.json').write_bytes(raw)
    (staging / 'manifest.sha256').write_text(release.sha256(raw) + '\n')
    target = releases_root / release_id
    staging.rename(target)
    return target, manifest, release.sha256(raw)


def binding_for(path, manifest, sha):
    return release.Binding(bound=True, script=str(path / 'source/deployment/dispatch_runtime.py'), source=path / 'source',
                           manifest_path=path / 'manifest.json', manifest_sha256=sha, release_id=manifest['release_id'],
                           roots=tuple(path / 'source' / r for r in ('deployment', 'application/src', 'integration/src')),
                           inventory={f['path']: f['sha256'] for f in manifest['tree']['files']})


def refuse_effects(monkeypatch):
    def refused(*args, **kwargs):
        raise AssertionError('runtime effect attempted: ' + repr(args)[:200])
    monkeypatch.setattr(subprocess, 'Popen', refused)
    monkeypatch.setattr(subprocess, 'run', refused)
    monkeypatch.setattr(app, 'run', refused)
    monkeypatch.setattr(modeling, 'run', refused)
    return refused


def executor_json(root, *, running_identity=None, raw=None):
    """executor.json naming an unused pid; running_identity makes process_identity report it alive."""
    (root / 'executor.json').write_text(raw if raw is not None else json.dumps(dict(
        pid=999999, identity=dict(command='/python -B /x/deployment/dispatch_runtime.py --serve', started='t'),
        release=dict(release_id='r'))))


class HeldLock:
    """Another open file description holding executor.lock exclusively (as a running executor does)."""
    def __init__(self, path):
        self.fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
        fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def release(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None


# ---- Executor quiescence: shared fail-closed gate ----------------------------------------

def test_executor_quiescence_requires_parsable_state_and_a_free_lock(tmp_path, monkeypatch):
    root = tmp_path / 'execution'
    root.mkdir()
    monkeypatch.setattr(dispatch, 'ROOT', root)
    assert dispatch.executor_quiescence(root) == dict(running=False, executor_json='absent', lock='absent')
    executor_json(root)
    (root / 'executor.lock').write_bytes(b'')
    assert dispatch.executor_quiescence(root) == dict(running=False, executor_json='valid', lock='free')
    for raw in ('{not json', '[]', json.dumps(dict(pid='1', identity={})), json.dumps(dict(pid=1))):
        (root / 'executor.json').write_text(raw)
        with pytest.raises(ValueError, match='executor.json'):
            dispatch.executor_quiescence(root)  # fail closed: process_status() treats these as stopped
    executor_json(root)
    held = HeldLock(root / 'executor.lock')
    try:
        with pytest.raises(ValueError, match='executor.lock is held'):
            dispatch.executor_quiescence(root)
    finally:
        held.release()
    identity = dict(command='/python -B ' + str(Path(dispatch.__file__).resolve()) + ' --serve', started='t')
    executor_json(root, raw=json.dumps(dict(pid=999999, identity=identity)))
    monkeypatch.setattr(dispatch, 'process_identity', lambda pid: identity)
    with pytest.raises(ValueError, match='Executor is running'):
        dispatch.executor_quiescence(root)
    monkeypatch.undo()
    (root / 'executor.lock').unlink()
    (root / 'executor.lock').symlink_to(tmp_path / 'elsewhere')
    with pytest.raises(ValueError, match='symlink'):
        dispatch.executor_quiescence(root)


# ---- dispatch_runtime main() fails closed unbound ----------------------------------------

@pytest.mark.parametrize('argv', [['--serve'], ['--once'], ['--run-id', 'r'], ['--stop'], ['--start'],
                                  ['--exports-only', '--once']])
def test_dispatch_main_refuses_unbound_operations_before_any_runtime_effect(argv, monkeypatch):
    refuse_effects(monkeypatch)
    monkeypatch.setattr(release, 'ACTIVE', None)
    monkeypatch.setattr(dispatch.application_runtime, 'check', lambda: pytest.fail('runtime touched while unbound'))
    monkeypatch.setattr(dispatch, 'manage', lambda op: pytest.fail('manager reached while unbound'))
    monkeypatch.setattr(sys, 'argv', ['dispatch_runtime', *argv])
    with pytest.raises(RuntimeError, match='selected release binding'):
        dispatch.main()
    unbound = release.Binding(bound=False, script='x')
    monkeypatch.setattr(release, 'ACTIVE', unbound)
    with pytest.raises(RuntimeError, match='selected release binding'):
        dispatch.main()


def test_dispatch_status_stays_available_unbound(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(release, 'ACTIVE', None)
    monkeypatch.setattr(dispatch, 'ROOT', tmp_path)
    monkeypatch.setattr(sys, 'argv', ['dispatch_runtime', '--status'])
    assert dispatch.main() == 0
    assert json.loads(capsys.readouterr().out)['running'] is False


# ---- native_environment: populated roots, bind lock probe, symlink-safe write ------------

def native_binding(tmp_path):
    path, manifest, sha = make_release(tmp_path / 'releases')
    return binding_for(path, manifest, sha)


def legacy_wrapper(root):
    return ('#!/bin/sh\nexport AIIDA_PATH=' + native.shlex.quote(str(root / 'aiida')) + '\nexec '
            + native.shlex.quote(str(native.PYTHON)) + ' -B -m hyprn_mvp_integration.launcher "$@"\n')


@pytest.mark.parametrize('extend', [False, True])
@pytest.mark.parametrize('marker', ['aiida', 'aiida-store', 'profile-identity.json', 'executor.json', 'executor.lock'])
def test_prepare_and_extend_refuse_a_populated_execution_root(tmp_path, monkeypatch, extend, marker):
    root = tmp_path / 'execution'
    (root / 'venv').mkdir(parents=True)
    target = root / marker
    if '.' in marker:
        target.write_text('{}')
    else:
        target.mkdir()
    before = {p: p.read_bytes() for p in root.rglob('*') if p.is_file()}
    monkeypatch.setattr(native, 'ROOT', root)
    refuse_effects(monkeypatch)
    monkeypatch.setitem(sys.modules, 'packaging', None)  # refusal precedes even the lazy packaging import
    with pytest.raises(ValueError, match='populated'):
        native.prepare(extend=extend)
    assert {p: p.read_bytes() for p in root.rglob('*') if p.is_file()} == before


def test_prepare_and_reuse_write_the_wrapper_the_launch_gate_accepts():
    """prepare and reuse_reviewed write exactly the wrapper that require_launch_worker accepts
    (the reviewed interpreter, never ROOT/venv/bin/python): both use
    write_launch_worker(ROOT, BINDING) and no other wrapper text."""
    tree = ast.parse(Path(native.__file__).read_text())
    functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    for name in ('prepare', 'reuse_reviewed'):
        calls = [n for n in ast.walk(functions[name]) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
        writers = [c for c in calls if c.func.id == 'write_launch_worker']
        assert len(writers) == 1 and [ast.unparse(a) for a in writers[0].args] == ['ROOT', 'BINDING'], name
        assert not [c for c in calls if c.func.id == 'launch_worker_text'], name


def test_write_launch_worker_is_exclusive_and_never_follows_a_planted_symlink(tmp_path, monkeypatch):
    binding = native_binding(tmp_path)
    root = tmp_path / 'execution'
    (root / 'evidence').mkdir(parents=True)
    victim = tmp_path / 'victim'
    victim.write_text('do not overwrite\n')
    real_uuid = native.uuid4
    fixed = types.SimpleNamespace(hex='f' * 32)
    monkeypatch.setattr(native, 'uuid4', lambda: fixed)
    (root / ('.launch-worker-' + fixed.hex)).symlink_to(victim)
    with pytest.raises(FileExistsError):
        native.write_launch_worker(root, binding)
    assert victim.read_text() == 'do not overwrite\n' and not (root / 'launch-worker').exists()
    monkeypatch.setattr(native, 'uuid4', real_uuid)
    text = native.write_launch_worker(root, binding)
    assert (root / 'launch-worker').read_bytes() == text
    assert stat.S_IMODE((root / 'launch-worker').stat().st_mode) == 0o700
    assert native.require_launch_worker(root, binding)['sha256'] == release.sha256(text)
    assert not [p for p in root.iterdir() if p.name.startswith('.launch-worker-') and not p.is_symlink()]


def test_bind_step_refuses_a_held_executor_lock_and_unparsable_executor_state(tmp_path, monkeypatch):
    binding = native_binding(tmp_path)
    root = tmp_path / 'execution'
    (root / 'evidence').mkdir(parents=True)
    legacy = legacy_wrapper(root)
    (root / 'launch-worker').write_text(legacy)
    monkeypatch.setattr(dispatch, 'ROOT', root)
    refuse_effects(monkeypatch)
    monkeypatch.setattr(dispatch, 'process_identity', lambda pid: dict(command='gone', started='t'))
    held = HeldLock(root / 'executor.lock')
    try:
        with pytest.raises(ValueError, match='executor.lock is held'):
            native.bind_step(root, binding)  # executor.json absent: process_status alone said "stopped"
    finally:
        held.release()
    executor_json(root, raw='{truncated')
    with pytest.raises(ValueError, match='executor.json'):
        native.bind_step(root, binding)
    assert (root / 'launch-worker').read_text() == legacy
    executor_json(root)
    record = native.bind_step(root, binding)
    assert record['previous_sha256'] == release.sha256(legacy.encode())


def test_launcher_evidence_must_carry_the_manifest_launcher_sha256(tmp_path):
    """A launcher-binding record naming this release counts only if its launcher module bytes
    equal the release manifest entry."""
    launcher = 'integration/src/hyprn_mvp_integration/launcher.py'
    path, manifest, sha = make_release(tmp_path / 'releases', {launcher: b'# launcher\n', 'deployment/x.py': b'#\n'})
    binding = binding_for(path, manifest, sha)
    root = tmp_path / 'execution'
    directory = root / 'evidence/release-binding'
    module = dict(file=str(binding.source / launcher), relative=launcher, sha256='0' * 64)
    record = dict(release_id=binding.release_id, manifest_sha256=binding.manifest_sha256, source_root=str(binding.source),
                  pid=7, modules={'hyprn_mvp_integration.launcher': module})
    release.write_evidence(directory, record, 'launcher-binding')
    with pytest.raises(ValueError, match='sha256'):
        native.launcher_evidence(root, binding)
    module['sha256'] = binding.inventory[launcher]
    good = release.write_evidence(directory, dict(record, pid=8), 'launcher-binding')
    for item in directory.glob('launcher-binding-7-*.json'):
        item.unlink()
    assert native.launcher_evidence(root, binding)['records'] == [str(good)]


# ---- application_runtime: retained UI builds and atomic identity writes -----------------

def with_ui_build(path, manifest, **extra):
    """Add a retained UI build (and optional manifest fields); rewrite the digest record."""
    ui = path / 'build/ui-dist'
    (ui / 'assets').mkdir(parents=True)
    (ui / 'index.html').write_text('<!doctype html>\n')
    manifest['build'] = dict(ui=dict(files=release.scan(ui), digest=release.tree_digest(release.scan(ui))))
    manifest.update(extra)
    raw = release.canonical(manifest)
    (path / 'manifest.json').write_bytes(raw)
    (path / 'manifest.sha256').write_text(release.sha256(raw) + '\n')
    assert release.verify(path, expected_sha256=release.sha256(raw))[1] == release.sha256(raw)
    return manifest, release.sha256(raw)


def test_identity_writes_are_atomic_replacements(tmp_path, monkeypatch):
    monkeypatch.setattr(app, 'ROOT', tmp_path)
    (tmp_path / 'identity.json').write_text('old\n')
    replaced = []
    real = os.replace

    def recorded(a, b):
        replaced.append((Path(a).parent, Path(b)))
        return real(a, b)

    monkeypatch.setattr(app.os, 'replace', recorded)
    app.write_identity(b'{"image": "x"}\n')
    assert (tmp_path / 'identity.json').read_bytes() == b'{"image": "x"}\n'
    assert replaced == [(tmp_path, tmp_path / 'identity.json')]
    assert stat.S_IMODE((tmp_path / 'identity.json').stat().st_mode) == 0o600


def private_tree(root, files):
    """Files written under umask 077, as by the ./hyprn-mvp entry point."""
    previous = os.umask(0o077)
    try:
        for relative in files:
            (root / relative).parent.mkdir(parents=True, exist_ok=True)
            (root / relative).write_text(relative + '\n')
    finally:
        os.umask(previous)
    return root


def modes(root):
    found = {}
    for path in sorted(root.rglob('*')):
        found[str(path.relative_to(root))] = stat.S_IMODE(path.stat().st_mode)
    return found


def test_build_contexts_are_readable_whatever_the_umask(tmp_path):
    root = private_tree(tmp_path / 'context', ('Dockerfile', 'start.sh', 'notices/a/b.json'))
    modeling.readable_context(root, executables=(root / 'start.sh',))
    assert modes(root) == {
        'Dockerfile': 0o644,
        'notices': 0o755,
        'notices/a': 0o755,
        'notices/a/b.json': 0o644,
        'start.sh': 0o755,
    }
    assert stat.S_IMODE(root.stat().st_mode) == 0o755
    # A link could make chmod act outside the context: refused.
    (root / 'notices/link').symlink_to(tmp_path)
    with pytest.raises(ValueError, match='build context'):
        modeling.readable_context(root)


APPLICATION_SOURCES = (
    'application/src/hyprn_mvp_app/__init__.py',
    'contracts/schemas/model.schema.json',
    'application/requirements.lock',
    'deployment/application.Dockerfile',
    'deployment/application_runtime.py',
)
INSTALLATION = 'hyprn-mvp-local-0123abcd'


def fresh_application(tmp_path, monkeypatch):
    """application_runtime.setup on a blank store with every docker effect faked."""
    root = tmp_path / 'application'
    (root / 'wheels').mkdir(parents=True)
    (root / 'wheels/reviewed.whl').write_bytes(b'wheel')
    repo = private_tree(tmp_path / 'repo', APPLICATION_SOURCES)
    ui = private_tree(tmp_path / 'ui', ('index.html', 'assets/app.js'))
    names = dict(
        NAME=INSTALLATION + '-application',
        OWNER=INSTALLATION + '-' + 'e' * 27,
        PUBLIC_NETWORK=INSTALLATION + '-public',
        USERNAME='engineer',
        PORT=18470,
    )
    for key, value in dict(names, ROOT=root, REPO=repo, UI_DIST=ui).items():
        monkeypatch.setattr(app, key, value)
    monkeypatch.setattr(release, 'ACTIVE', None)
    monkeypatch.setattr(modeling, 'check', lambda root, **kw: dict(running=True))
    monkeypatch.setattr(modeling, 'inspect', lambda name, kind='container': None)
    monkeypatch.setattr(app, 'inspect', lambda: None)
    state = types.SimpleNamespace(commands=[], inputs=[], context={})

    def fake_run(*args, input=None):
        state.commands.append(args)
        state.inputs.append(input)
        if args[:3] == ('docker', 'image', 'inspect'):
            return app.BASE if args[3] == 'python:3.12.11-slim-bookworm' else 'sha256:new-app'
        return ''

    def fake_build(args, **kwargs):
        state.context = modes(Path(args[-1]))
        return subprocess.CompletedProcess(args, 0, 'built', '')

    def checked(allow_source_change=False):
        return dict(container=app.NAME, running=True)

    monkeypatch.setattr(app, 'run', fake_run)
    monkeypatch.setattr(subprocess, 'run', fake_build)
    monkeypatch.setattr(app, 'check', checked)
    return types.SimpleNamespace(root=root, state=state, names=names)


def command(state, *prefix):
    return next(c for c in state.commands if c[: len(prefix)] == prefix)


def test_a_new_application_store_provisions_the_installation_owner_and_names(tmp_path, monkeypatch):
    env = fresh_application(tmp_path, monkeypatch)
    previous = os.umask(0o077)
    try:
        assert app.setup()['running']
    finally:
        os.umask(previous)
    # Every file the image copies is readable by the application user.
    context = env.state.context
    assert context and all(mode == (0o755 if mode & 0o100 else 0o644) for mode in context.values())
    assert all(context[name] == 0o755 for name in ('application', 'contracts', 'ui-dist', 'wheels'))
    provision = command(env.state, 'docker', 'run', '--rm')
    assert provision[-4:-2] == ('python', '-c') and provision[-1] == 'engineer'
    password = env.state.inputs[env.state.commands.index(provision)]
    assert password == (env.root / 'credentials/owner.password').read_text().strip()
    assert password not in ' '.join(provision)
    text = ' '.join(command(env.state, 'docker', 'run', '-d'))
    for expected in (
        '--name ' + env.names['NAME'],
        '--label org.hyprn-mvp.owner=' + env.names['OWNER'],
        '--network ' + env.names['PUBLIC_NETWORK'],
        '-p 127.0.0.1:18470:8000',
    ):
        assert expected in text
    assert command(env.state, 'docker', 'network', 'create')[-1] == env.names['PUBLIC_NETWORK']
    identity = json.loads((env.root / 'identity.json').read_text())
    assert (identity['owner'], identity['container']) == (env.names['OWNER'], env.names['NAME'])


def test_the_application_manager_has_no_upgrade_path():
    """Replacing an installed application is not a command of this phase (no update command)."""
    source = Path(app.__file__).read_text()
    for removed in ('upgrade', 'restore_upgrade', 'liveness_probe', 'in_container_dispatchers'):
        assert removed not in source
    assert not hasattr(app, 'upgrade_gate')


# ---- modeling_runtime: every compose call runs in a clean environment ---------------------

def test_compose_runs_with_a_clean_environment(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setenv('COMPOSE_PROJECT_NAME', 'hijack')
    monkeypatch.setenv('COMPOSE_FILE', '/tmp/other.yaml')
    monkeypatch.setenv('DOCKER_HOST', 'tcp://elsewhere:2375')
    monkeypatch.setattr(subprocess, 'run', lambda args, **kw: calls.append((args, kw['env'])) or
                        subprocess.CompletedProcess(args, 0, '', ''))
    (tmp_path / 'evidence').mkdir()
    assert modeling.compose_up(tmp_path, 'sha256:img', tmp_path / 'evidence/compose.log') == 0
    args, env = calls[0]
    assert args[:4] == ['docker', 'compose', '--project-name', modeling.PROJECT]
    names = tuple('HYPRN_MVP_MODELING_' + name for name in ('CONTAINER', 'NETWORK', 'OWNER'))
    reviewed = {'PATH', 'HOME', 'HYPRN_MVP_MODELING_ROOT', 'HYPRN_MVP_MODELING_IMAGE', *names}
    assert set(env) <= reviewed
    assert env['HYPRN_MVP_MODELING_ROOT'] == str(tmp_path)
    assert env['HYPRN_MVP_MODELING_IMAGE'] == 'sha256:img'
    assert [env[name] for name in names] == [modeling.CONTAINER, modeling.NETWORK, modeling.OWNER]
    assert not any(k.startswith('COMPOSE_') or k.startswith('DOCKER_') for k in env)
    # An installation's compose call names its configured engine, never the inherited one.
    configured = {'PATH': '/usr/bin', 'DOCKER_HOST': 'unix:///configured/docker.sock'}
    monkeypatch.setattr(modeling, 'DOCKER_ENVIRONMENT', configured)
    assert modeling.compose_up(tmp_path, 'sha256:img', tmp_path / 'evidence/compose.log') == 0
    env = calls[1][1]
    assert set(env) <= reviewed | {'DOCKER_HOST'}
    assert env['DOCKER_HOST'] == 'unix:///configured/docker.sock'
    source = Path(modeling.__file__).read_text()
    assert source.count("'docker', 'compose'") == 1 and source.count('compose_environment(') == 2  # one call site
    assert 'compose_up(' in source.split('def setup(', 1)[1]


# ---- modeling_runtime: a test scope's deployment never names the installation ---------------

def test_scoped_modeling_deployment_names_only_its_scope(tmp_path, monkeypatch):
    import uuid
    monkeypatch.setattr(modeling.local_paths, 'scratch_root', lambda: tmp_path)
    scope = str(uuid.uuid4())
    root = tmp_path / ('hyprn-mvp-test-' + scope) / 'artifacts/modeling-deployment'
    deployment = modeling.scoped_deployment(root, scope)
    installation = {modeling.CONTAINER, modeling.NETWORK, modeling.OWNER}
    assert not {deployment.container, deployment.network, deployment.owner} & installation
    assert deployment.container.startswith('hyprn-mvp-test-' + scope.replace('-', '')[:8] + '-')
    assert (deployment.label, deployment.owner) == ('org.hyprn-mvp.test-scope', scope)
    for outside in (Path('relative/root'), tmp_path.parent / 'elsewhere', tmp_path / 'link' / '..' / 'x'):
        with pytest.raises(ValueError):
            modeling.scoped_deployment(outside, scope)
    with pytest.raises(ValueError):
        modeling.scoped_deployment(root, 'not-a-scope')
    # A test scope's deployment is never rebuilt in place, and its root is exactly its own.
    with pytest.raises(ValueError):
        modeling.setup(root, rebuild=True, deployment=deployment)
    with pytest.raises(ValueError):
        modeling.checked_root(root.parent, deployment)


def test_scoped_start_reproduces_every_reviewed_recipe_setting(tmp_path, monkeypatch):
    import uuid
    monkeypatch.setattr(modeling.local_paths, 'scratch_root', lambda: tmp_path)
    scope = str(uuid.uuid4())
    root = tmp_path / 'scope' / 'deployment'
    deployment = modeling.scoped_deployment(root, scope)
    calls = []
    monkeypatch.setattr(modeling, 'run', lambda *args, **kw: calls.append(list(args)) or '')
    monkeypatch.setattr(subprocess, 'run', lambda args, **kw: calls.append(list(args)) or
                        subprocess.CompletedProcess(args, 0, '', ''))
    log = tmp_path / 'setup.log'
    assert modeling.start_scoped(root, 'sha256:' + 'a' * 64, log, deployment) == 0
    network, container = calls
    label = 'org.hyprn-mvp.test-scope=' + scope
    assert network == ['docker', 'network', 'create', '--internal', '--label', label, deployment.network]
    recipe = json.loads(modeling.RECIPE.read_text())['services']['modeling']
    assert container[:3] == ['docker', 'run', '-d'] and container[-1] == 'sha256:' + 'a' * 64
    text = ' '.join(container)
    for expected in ('--name ' + deployment.container, '--label ' + label, '--network ' + deployment.network,
                     '--user ' + recipe['user'], '--read-only', '--cap-drop ALL', '--security-opt no-new-privileges:true',
                     '--pids-limit 128', '--memory 768m', '--cpus 1', '--restart no',
                     *('--tmpfs ' + value for value in recipe['tmpfs']),
                     '--mount type=bind,src=' + str(root) + '/modeling,dst=/store',
                     '--mount type=bind,src=' + str(root) + '/credentials/model.key,dst=/run/model.key,readonly',
                     '--mount type=bind,src=' + str(root) + '/credentials/rails.key,dst=/run/rails.key,readonly'):
        assert expected in text
    assert '--publish' not in container and '-p' not in container
    # A recipe setting the scoped start does not reproduce fails closed.
    widened = json.loads(modeling.RECIPE.read_text())
    widened['services']['modeling']['ports'] = ['3000:3000']
    changed = tmp_path / 'recipe.json'
    changed.write_text(json.dumps(widened))
    monkeypatch.setattr(modeling, 'RECIPE', changed)
    with pytest.raises(ValueError, match='Unreviewed modeling recipe'):
        modeling.start_scoped(root, 'sha256:' + 'a' * 64, log, deployment)


# ---- Release binding: review record, immutability, binding paths ----------------------------

def test_review_requirement_follows_the_allowlist_basis(tmp_path):
    _, plain, _ = make_release(tmp_path / 'a')
    _, cited, _ = make_release(tmp_path / 'b', basis=INDEPENDENT)
    assert release.review_required(plain) is False and release.review_required(cited) is True
    assert release.review_required(json.loads(json.dumps(dict(selection=dict(binding_commits=[dict(
        basis='the independent ASVS review of this delta required before start')]))))) is True


def review_file(tmp_path, release_id, name='code-review.md', text=None):
    path = tmp_path / name
    path.write_text(text if text is not None else '# Review\n\nRelease ' + release_id + ': PASS\n')
    return path


def test_record_review_is_create_only_private_and_digest_named(tmp_path):
    path, manifest, sha = make_release(tmp_path / 'releases', basis=INDEPENDENT)
    reviews = tmp_path / 'releases/.reviews'
    with pytest.raises(release.ReleaseError, match='name the release'):
        release.record_review(path, sha, [review_file(tmp_path, release.RELEASE_PREFIX + '0' * 16)], 'ref',
                              reviews_root=reviews, retained=False)
    with pytest.raises(release.ReleaseError, match='qualified manifest'):
        release.record_review(path, '0' * 64, [review_file(tmp_path, manifest['release_id'])], 'ref',
                              reviews_root=reviews, retained=False)
    link = tmp_path / 'link.md'
    link.symlink_to(review_file(tmp_path, manifest['release_id'], 'target.md'))
    with pytest.raises(release.ReleaseError, match='regular'):
        release.record_review(path, sha, [link], 'ref', reviews_root=reviews, retained=False)
    for reference in ('', ' ', 'x' * 600):
        with pytest.raises(release.ReleaseError, match='reference'):
            release.record_review(path, sha, [review_file(tmp_path, manifest['release_id'])], reference,
                                  reviews_root=reviews, retained=False)
    files = [review_file(tmp_path, manifest['release_id']),
             review_file(tmp_path, manifest['release_id'], 'security.md')]
    record = release.record_review(path, sha, files, 'parent verification reference', reviews_root=reviews, retained=False)
    directory = reviews / manifest['release_id']
    saved = directory / 'review-record.json'
    assert record['record_sha256'] == release.sha256(saved.read_bytes())
    assert stat.S_IMODE(saved.stat().st_mode) == 0o600 and stat.S_IMODE(directory.stat().st_mode) == 0o700
    data = json.loads(saved.read_text())
    assert data['manifest_sha256'] == sha and data['release_id'] == manifest['release_id']
    assert [f['sha256'] for f in data['files']] == [release.sha256(f.read_bytes()) for f in files]
    for item in data['files']:
        assert (directory / item['name']).read_bytes() == next(f.read_bytes() for f in files
                                                                if release.sha256(f.read_bytes()) == item['sha256'])
    with pytest.raises(release.ReleaseError, match='already recorded'):
        release.record_review(path, sha, files, 'again', reviews_root=reviews, retained=False)
    assert release.sha256(saved.read_bytes()) == record['record_sha256']


def test_start_and_activation_require_the_recorded_review(tmp_path, monkeypatch):
    path, manifest, sha = make_release(tmp_path / 'releases', basis=INDEPENDENT)
    reviews = tmp_path / 'releases/.reviews'
    monkeypatch.setattr(release, 'REVIEWS_ROOT', reviews)
    with pytest.raises(release.ReleaseBindingError, match='record-review'):
        release.require_review(path, manifest, sha)
    _, plain, plain_sha = make_release(tmp_path / 'plain')
    assert release.require_review(tmp_path / 'plain' / plain['release_id'], plain, plain_sha) == dict(required=False)
    record = release.record_review(path, sha, [review_file(tmp_path, manifest['release_id'])], 'ref', retained=False)
    checked = release.require_review(path, manifest, sha)
    assert checked['required'] and checked['record_sha256'] == record['record_sha256']
    copy = next((reviews / manifest['release_id']).glob('*-code-review.md'))
    copy.chmod(0o600)
    copy.write_text('edited after recording\n')
    with pytest.raises(release.ReleaseBindingError, match='review'):
        release.require_review(path, manifest, sha)


def test_executor_start_names_the_review_record_digest(tmp_path, monkeypatch):
    path, manifest, sha = make_release(tmp_path / 'releases', basis=INDEPENDENT)
    manifest, sha = with_ui_build(path, manifest, inventories=dict(runtime_sources=dict(
        application={'deployment/application_runtime.py': '1' * 64})))
    binding = binding_for(path, manifest, sha)
    execution = tmp_path / 'execution'
    execution.mkdir()
    (execution / 'launch-worker').write_text(native.launch_worker_text(execution, binding))
    application = tmp_path / 'application'
    application.mkdir()
    identity = {'deployment/application_runtime.py': '1' * 64, 'ui-dist/index.html': manifest['build']['ui']['files'][0]['sha256']}
    (application / 'identity.json').write_text(json.dumps(dict(source_hashes=identity)))
    monkeypatch.setattr(dispatch, 'ROOT', execution)
    monkeypatch.setattr(app, 'ROOT', application)
    monkeypatch.setattr(release, 'ACTIVE', binding)
    monkeypatch.setattr(release, 'REVIEWS_ROOT', tmp_path / 'releases/.reviews')
    refuse_effects(monkeypatch)
    with pytest.raises(RuntimeError, match='record-review'):
        dispatch.require_release_start()
    record = release.record_review(path, sha, [review_file(tmp_path, manifest['release_id'])], 'ref', retained=False)
    started = dispatch.require_release_start()
    assert started['review']['record_sha256'] == record['record_sha256']  # lands in executor.json


def test_release_binding_paths_are_the_repository_managers_that_bind_before_any_effect():
    """Every release binding path is a file of this repository, and they are exactly the
    deployment managers whose __main__ guard binds to the selected release before any effect."""
    for relative in release.RELEASE_BINDING_PATHS:
        assert (REPO / relative).is_file(), relative
    binding = {'deployment/' + p.name for p in (REPO / 'deployment').glob('*.py')
               if p.name == 'release_binding.py' or 'release_binding.entrypoint(' in p.read_text()}
    assert binding == set(release.RELEASE_BINDING_PATHS)


def test_release_immutability_is_an_explicit_reversible_opt_in(tmp_path):
    path, manifest, sha = make_release(tmp_path / 'releases')
    assert release.immutable_state(path)['immutable'] == 0
    try:
        with pytest.raises(release.ReleaseError, match='qualified manifest'):
            release.make_immutable(path, '0' * 64, retained=False)
        assert release.immutable_state(path)['immutable'] == 0
        result = release.make_immutable(path, sha, retained=False)
        state = release.immutable_state(path)
        assert state['immutable'] == state['entries'] == result['immutable_entries'] > 3
        assert result['clear_command'] == "/usr/bin/chflags -R nouchg '" + str(path) + "'"
        with pytest.raises(PermissionError):
            (path / 'source/ui/index.html').chmod(0o644)
        with pytest.raises(PermissionError):
            os.rename(path, tmp_path / 'moved')  # quarantine needs the documented nouchg first
        assert release.verify(path, expected_sha256=sha)[1] == sha  # still verifiable
    finally:
        subprocess.run(['/usr/bin/chflags', '-R', 'nouchg', str(path)], check=True)
    assert release.immutable_state(path)['immutable'] == 0


def test_release_commands_document_review_and_immutability_steps(tmp_path):
    path, manifest, sha = make_release(tmp_path / 'releases')
    commands = release.release_commands(path, sha)
    assert "release_binding.py' record-review --expected-sha256 " + sha in commands['record_review']
    assert "release_binding.py' require-review --expected-sha256 " + sha in commands['require_review']
    # Every script a command names is a release binding entry point of this repository.
    named = {m.group(1) for text in commands.values() for m in re.finditer(r"/source/(deployment/[\w./-]+\.py)'", text)}
    assert named and named <= release.RELEASE_BINDING_PATHS, named
    assert 'make-immutable' in commands['make_immutable'] and 'opt-in' in commands['make_immutable']
    assert 'chflags -R nouchg' in commands['quarantine']
    # No command replaces an installed application (no update command in this phase).
    assert not any('upgrade' in text for text in commands.values())


def test_qualification_requires_the_attestation_coverage_group():
    """The narrowed attestation is safe only while its coverage test runs, so the qualification
    aggregate includes the must-pass group that runs the module-boundary test."""
    import checks as runner
    assert runner.group_class('locality-contracts') == 'must-pass'
    assert 'locality-contracts' in runner.must_pass_groups()
    assert 'application/tests/test_module_boundaries.py' in runner.GROUPS['locality-contracts']
