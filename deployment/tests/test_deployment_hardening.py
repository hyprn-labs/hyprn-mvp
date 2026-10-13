"""Deployment hardening: managers, release binding and the reviewed backup tool.

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
import datetime
import errno
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import re
import sqlite3
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


# ---- application_runtime setup --upgrade -------------------------------------------------

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


def upgrade_env(tmp_path, monkeypatch):
    path, manifest, sha = make_release(tmp_path / 'releases')
    manifest, sha = with_ui_build(path, manifest)
    binding = binding_for(path, manifest, sha)
    root = tmp_path / 'application'
    for name in ('application', 'credentials', 'evidence', 'wheels'):
        (root / name).mkdir(parents=True)
    (root / 'application/application.sqlite').write_bytes(b'preserved application store')
    (root / 'credentials/owner.password').write_text('preserved-password\n')
    (root / 'wheels/reviewed.whl').write_bytes(b'wheel')
    (root / 'identity.json').write_text(json.dumps(dict(owner=app.OWNER, container=app.NAME, image='sha256:old-app',
                                                        base=app.BASE, source_hashes={}, store=str(root / 'application'))))
    execution = tmp_path / 'execution'
    execution.mkdir()
    repo = tmp_path / 'repo'
    for relative in ('application/src/hyprn_mvp_app/__init__.py', 'contracts/schemas/model.schema.json',
                     'application/requirements.lock', 'deployment/application.Dockerfile',
                     'deployment/application_runtime.py'):
        (repo / relative).parent.mkdir(parents=True, exist_ok=True)
        (repo / relative).write_text(relative + '\n')
    monkeypatch.setattr(app, 'ROOT', root)
    monkeypatch.setattr(app, 'REPO', repo)
    monkeypatch.setattr(dispatch, 'ROOT', execution)
    monkeypatch.setattr(release, 'ACTIVE', binding)
    monkeypatch.setattr(modeling, 'check', lambda root, **kw: dict(running=True))
    owned_network = dict(Labels={modeling.LABEL: app.OWNER})
    monkeypatch.setattr(modeling, 'inspect', lambda name, kind='container': owned_network if name == app.PUBLIC_NETWORK else None)
    state = types.SimpleNamespace(container=dict(Id='old-id', Name='/' + app.NAME, Image='sha256:old-app',
                                                 Config=dict(Labels={modeling.LABEL: app.OWNER})),
                                  commands=[], events=[], fail=None, running=True, top=[], probe='ok')

    def fake_run(*args, input=None):
        state.commands.append(args)
        state.events.append(('docker',) + args[1:3])
        if state.fail and args[:len(state.fail)] == state.fail:
            raise subprocess.CalledProcessError(1, args, '', 'injected failure')
        if args[:3] == ('docker', 'image', 'inspect'):
            return app.BASE if args[3] == 'python:3.12.11-slim-bookworm' else 'sha256:new-app'
        if args[:3] == ('docker', 'run', '-d'):
            state.container = dict(Id='new-id', Name='/' + app.NAME, Image='sha256:new-app',
                                   Config=dict(Labels={modeling.LABEL: app.OWNER}))
        if args[:2] == ('docker', 'rename') and args[2] == app.NAME:
            state.container = None
        if args[:2] == ('docker', 'rename') and args[3] == app.NAME:
            state.container = dict(Id='old-id', Name='/' + app.NAME, Image='sha256:old-app',
                                   Config=dict(Labels={modeling.LABEL: app.OWNER}))
        if args[:2] == ('docker', 'rm') and args[2] == app.NAME:
            state.container = None
        return ''

    def fake_build(args, **kwargs):
        return subprocess.CompletedProcess(args, 0, 'built', '')

    def identity_events(raw):
        state.events.append(('identity', json.loads(raw)['image']))
    real_write = app.write_identity if hasattr(app, 'write_identity') else None

    def write_identity(raw):
        identity_events(raw)
        return real_write(raw)
    monkeypatch.setattr(app, 'inspect', lambda: state.container)
    monkeypatch.setattr(app, 'run', fake_run)
    monkeypatch.setattr(subprocess, 'run', fake_build)
    if real_write is not None:
        monkeypatch.setattr(app, 'write_identity', write_identity)
    monkeypatch.setattr(app, 'check', lambda allow_source_change=False: dict(
        container=app.NAME, image=(state.container or {}).get('Image'), running=state.running))
    monkeypatch.setattr(app, 'in_container_dispatchers', lambda: list(state.top), raising=False)

    def probe(**kwargs):
        state.events.append(('probe', state.probe))
        if state.probe != 'ok':
            raise RuntimeError('Application liveness probe failed: ' + state.probe)
        return dict(status=401)
    monkeypatch.setattr(app, 'liveness_probe', probe, raising=False)
    return types.SimpleNamespace(root=root, execution=execution, state=state, binding=binding)


def test_upgrade_removes_the_replaced_container_only_after_running_and_http_401(tmp_path, monkeypatch):
    env = upgrade_env(tmp_path, monkeypatch)
    result = app.setup(upgrade=True)
    assert result['running'] and result['image'] == 'sha256:new-app'
    events = env.state.events
    removal = next(i for i, e in enumerate(events) if e[:2] == ('docker', 'rm'))
    probe = events.index(('probe', 'ok'))
    assert probe < removal  # liveness proven before the rollback container is discarded


@pytest.mark.parametrize('failure', ['not-running', 'probe'])
def test_upgrade_restores_when_the_new_container_is_not_live(tmp_path, monkeypatch, failure):
    env = upgrade_env(tmp_path, monkeypatch)
    identity_before = (env.root / 'identity.json').read_bytes()
    if failure == 'not-running':
        env.state.running = False  # created, passes inspection, but crashed
    else:
        env.state.probe = 'connection refused'
    with pytest.raises((RuntimeError, ValueError)):
        app.setup(upgrade=True)
    effects = [c for c in env.state.commands if c[:3] != ('docker', 'image', 'inspect')]
    replaced = next(c[3] for c in effects if c[:2] == ('docker', 'rename'))
    assert ('docker', 'rm', replaced) not in effects  # the previous container is never discarded
    assert effects[-2:] == [('docker', 'rename', replaced, app.NAME), ('docker', 'start', app.NAME)]
    assert env.state.container['Image'] == 'sha256:old-app'
    assert (env.root / 'identity.json').read_bytes() == identity_before


def test_upgrade_restore_writes_identity_atomically_before_any_container_step(tmp_path, monkeypatch):
    """If the container restore itself fails, identity.json already names the previous image."""
    env = upgrade_env(tmp_path, monkeypatch)
    identity_before = (env.root / 'identity.json').read_bytes()
    env.state.probe = 'timeout'
    original = app.run

    def failing_restore(*args, input=None):
        if args[:2] == ('docker', 'rename') and args[3] == app.NAME:
            env.state.commands.append(args)
            raise subprocess.CalledProcessError(1, args, '', 'restore rename failed')
        return original(*args, input=input)
    monkeypatch.setattr(app, 'run', failing_restore)
    with pytest.raises(RuntimeError, match='automatic restore failed'):
        app.setup(upgrade=True)
    assert (env.root / 'identity.json').read_bytes() == identity_before
    assert not [p for p in env.root.iterdir() if p.name.startswith('.identity')]  # temp replaced atomically


def test_identity_writes_are_atomic_replacements(tmp_path, monkeypatch):
    monkeypatch.setattr(app, 'ROOT', tmp_path)
    (tmp_path / 'identity.json').write_text('old\n')
    replaced = []
    real = os.replace
    monkeypatch.setattr(app.os, 'replace', lambda a, b: replaced.append((Path(a).parent, Path(b))) or real(a, b))
    app.write_identity(b'{"image": "x"}\n')
    assert (tmp_path / 'identity.json').read_bytes() == b'{"image": "x"}\n'
    assert replaced == [(tmp_path, tmp_path / 'identity.json')]
    assert stat.S_IMODE((tmp_path / 'identity.json').stat().st_mode) == 0o600


@pytest.mark.parametrize('case', ['lock', 'unparsable', 'in-container'])
def test_upgrade_gate_refuses_hidden_executors_before_any_effect(tmp_path, monkeypatch, case):
    env = upgrade_env(tmp_path, monkeypatch)
    held = None
    if case == 'lock':
        held = HeldLock(env.execution / 'executor.lock')
        match = 'executor.lock is held'
    elif case == 'unparsable':
        executor_json(env.execution, raw='{"pid":')
        match = 'executor.json'
    else:
        env.state.top = ['4242 python -B -m hyprn_mvp_app.dispatcher --with-exports']
        match = 'dispatcher'
    try:
        with pytest.raises(ValueError, match=match):
            app.setup(upgrade=True)
    finally:
        if held:
            held.release()
    assert env.state.commands == []


def test_upgrade_rechecks_the_executor_immediately_before_docker_stop(tmp_path, monkeypatch):
    env = upgrade_env(tmp_path, monkeypatch)
    calls = []
    real = app.require_executor_quiescent

    def counted():
        calls.append([c for c in env.state.commands if c[:2] == ('docker', 'stop')])
        if len(calls) == 2:
            env.state.top = ['4242 python -B -m hyprn_mvp_app.dispatcher']  # appeared during the build
        return real()
    monkeypatch.setattr(app, 'require_executor_quiescent', counted)
    with pytest.raises(ValueError, match='dispatcher'):
        app.setup(upgrade=True)
    assert len(calls) == 2 and calls[1] == []  # second check after the build, before any docker stop
    assert not any(c[:2] in (('docker', 'stop'), ('docker', 'rename'), ('docker', 'start')) for c in env.state.commands)
    assert env.state.container['Image'] == 'sha256:old-app'


def test_in_container_dispatchers_parse_docker_top(monkeypatch):
    outputs = {'running': types.SimpleNamespace(returncode=0, stdout='PID COMMAND\n10 python -m uvicorn\n'
                                                '11 python -B -m hyprn_mvp_app.dispatcher --with-exports\n', stderr=''),
               'stopped': types.SimpleNamespace(returncode=1, stdout='', stderr='Error response from daemon: container x is not running'),
               'broken': types.SimpleNamespace(returncode=1, stdout='', stderr='permission denied')}
    for name, output in outputs.items():
        monkeypatch.setattr(app, 'docker_top', lambda output=output: output)
        if name == 'broken':
            with pytest.raises(RuntimeError, match='docker top'):
                app.in_container_dispatchers()
        else:
            found = app.in_container_dispatchers()
            assert found == (['11 python -B -m hyprn_mvp_app.dispatcher --with-exports'] if name == 'running' else [])


def test_liveness_probe_requires_unauthenticated_401(monkeypatch):
    import urllib.error
    monkeypatch.setattr(app, 'PORT', 54321)  # Synthetic port: no development port is needed.
    answers = []

    class Opener:
        def open(self, request, timeout):
            assert request.full_url == 'http://127.0.0.1:%d/api/1/studies' % app.PORT and request.get_method() == 'GET'
            assert not request.has_header('Cookie') and not request.has_header('Authorization')
            answer = answers.pop(0)
            if isinstance(answer, Exception):
                raise answer
            return types.SimpleNamespace(status=answer, close=lambda: None)
    monkeypatch.setattr(app.urllib.request, 'build_opener', lambda *handlers: Opener())
    monkeypatch.setattr(app.time, 'sleep', lambda s: None)
    answers[:] = [urllib.error.URLError('refused'), urllib.error.HTTPError('u', 401, 'Unauthorized', {}, None)]
    assert app.liveness_probe(timeout=5, interval=0)['status'] == 401
    answers[:] = [200] * 3
    with pytest.raises(RuntimeError, match='liveness'):
        app.liveness_probe(timeout=0, interval=0)  # an unauthenticated 200 is not the reviewed application


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
    assert args[:2] == ['docker', 'compose'] and set(env) <= {'PATH', 'HOME', 'HYPRN_MVP_MODELING_ROOT', 'HYPRN_MVP_MODELING_IMAGE'}
    assert env['HYPRN_MVP_MODELING_ROOT'] == str(tmp_path) and env['HYPRN_MVP_MODELING_IMAGE'] == 'sha256:img'
    assert not any(k.startswith('COMPOSE_') or k.startswith('DOCKER_') for k in env)
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


# ---- Reviewed immutable-read backup tool --------------------------------------------------

def backup_tool():
    spec = importlib.util.spec_from_file_location('backup_immutable', REPO / 'deployment/tools/backup_immutable.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def workspace(tmp_path):
    root = tmp_path / 'data-root'
    for relative in ('application/application/computational-records', 'application/evidence', 'application/credentials',
                     'execution/aiida-store/container', 'execution/aiida/.aiida', 'execution/evidence',
                     'modeling/modeling', 'modeling/credentials', 'modeling/evidence', 'application/activation/evidence'):
        (root / relative).mkdir(parents=True)
    for relative in ('application/application/application.sqlite', 'execution/aiida-store/database.sqlite'):
        with sqlite3.connect(root / relative) as db:
            db.execute('CREATE TABLE t(v)')
            db.execute("INSERT INTO t VALUES('rollback-journal')")
        db.close()
    db = sqlite3.connect(root / 'modeling/modeling/model.sqlite3')
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('CREATE TABLE t(v)')
    db.execute("INSERT INTO t VALUES('wal')")
    db.commit()
    db.close()  # clean close checkpoints and removes the WAL
    (root / 'execution/aiida-store/container/packed').write_bytes(b'native object')
    (root / 'application/application/computational-records/r.json').write_text('{}')
    (root / 'application/activation/evidence/container-removal.json').write_text('{}')
    for relative in ('execution/launch-worker', 'execution/runtime.json', 'application/identity.json', 'modeling/identity.json'):
        (root / relative).write_text(relative + '\n')
    for relative in ('application/credentials/owner.password', 'modeling/credentials/model.key',
                     'modeling/credentials/rails.key', 'execution/aiida/.aiida/config.json'):
        (root / relative).write_text('secret ' + relative + '\n')
    (root / 'execution/executor.lock').write_bytes(b'')
    return root


def test_backup_refuses_a_nonempty_model_wal_after_stop(tmp_path):
    tool = backup_tool()
    root = workspace(tmp_path)
    assert tool.wal_state(root)['modeling/modeling/model.sqlite3'] == dict(wal=None, journal=None)
    writer = sqlite3.connect(root / 'modeling/modeling/model.sqlite3')
    writer.execute('PRAGMA wal_autocheckpoint=0')
    writer.execute("INSERT INTO t VALUES('not yet checkpointed')")
    writer.commit()
    try:
        assert tool.wal_state(root)['modeling/modeling/model.sqlite3']['wal'] > 0
        with pytest.raises(SystemExit, match='WAL'):
            tool.backup(root, tmp_path / 'backup', containers=lambda: [])
        assert not (tmp_path / 'backup').exists()
    finally:
        writer.close()
    (root / 'application/application/application.sqlite-journal').write_bytes(b'hot journal')
    with pytest.raises(SystemExit, match='journal'):
        tool.backup(root, tmp_path / 'backup', containers=lambda: [])


@pytest.mark.parametrize('case', ['running-container', 'lock', 'unparsable', 'running-executor'])
def test_backup_refuses_unless_everything_is_stopped(tmp_path, monkeypatch, case):
    tool = backup_tool()
    root = workspace(tmp_path)
    containers = lambda: []  # noqa: E731
    held = None
    if case == 'running-container':
        containers = lambda: [app.NAME]  # noqa: E731
    elif case == 'lock':
        held = HeldLock(root / 'execution/executor.lock')
    elif case == 'unparsable':
        (root / 'execution/executor.json').write_text('{')
    else:
        (root / 'execution/executor.json').write_text(json.dumps(dict(pid=os.getpid(), identity={})))
        monkeypatch.setattr(tool, 'process_command', lambda pid: '/py -B /r/source/deployment/dispatch_runtime.py --serve')
    try:
        with pytest.raises(SystemExit):
            tool.backup(root, tmp_path / 'backup', containers=containers)
    finally:
        if held:
            held.release()
    assert not (tmp_path / 'backup').exists()


def test_backup_copies_read_only_with_digest_only_credentials(tmp_path):
    tool = backup_tool()
    root = workspace(tmp_path)
    before = {p: p.read_bytes() for p in root.rglob('*') if p.is_file()}
    result = tool.backup(root, tmp_path / 'backup', containers=lambda: [])
    target = tmp_path / 'backup'
    assert {p: p.read_bytes() for p in root.rglob('*') if p.is_file()} == before  # source untouched
    manifest = json.loads((target / 'backup-manifest.json').read_text())
    assert result['manifest_sha256'] == release.sha256((target / 'backup-manifest.json').read_bytes())
    assert manifest['tool_sha256'] == release.sha256((REPO / 'deployment/tools/backup_immutable.py').read_bytes())
    assert manifest['wal_state']['modeling/modeling/model.sqlite3'] == dict(wal=None, journal=None)
    databases = [e for e in manifest['entries'] if e['kind'] == 'sqlite-backup']
    assert len(databases) == 3 and all(e['integrity'] == 'ok' for e in databases)
    with sqlite3.connect(target / 'modeling/modeling/model.sqlite3') as db:
        assert db.execute('SELECT v FROM t').fetchall() == [('wal',)]
    assert (target / 'execution/aiida-store/container/packed').read_bytes() == b'native object'
    assert not (target / 'application/credentials').exists() and not (target / 'execution/aiida').exists()
    assert set(manifest['identity_digests']) == set(tool.DIGEST_ONLY)
    assert stat.S_IMODE(target.stat().st_mode) == 0o700
    assert all(stat.S_IMODE(p.stat().st_mode) == 0o600 for p in target.rglob('*') if p.is_file())
    with pytest.raises(FileExistsError):
        tool.backup(root, target, containers=lambda: [])  # create-only


def test_lock_probe_reports_without_docker(tmp_path):
    tool = backup_tool()
    root = workspace(tmp_path)
    assert tool.lock_probe(root) == dict(executor_running=False, executor_json='absent', lock_available=True)
    held = HeldLock(root / 'execution/executor.lock')
    try:
        assert tool.lock_probe(root)['lock_available'] is False
    finally:
        held.release()


def test_backup_tool_is_stdlib_python39_compatible_and_pins_its_live_root():
    source = (REPO / 'deployment/tools/backup_immutable.py').read_text()
    tree = ast.parse(source, feature_version=(3, 9))
    imported = {a.name.split('.')[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    imported |= {n.module.split('.')[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert imported <= {'argparse', 'datetime', 'fcntl', 'hashlib', 'json', 'os', 'pathlib', 'sqlite3', 'stat',
                        'subprocess', 'sys'}
    assert "ROOT = stores_root()" in source and "os.environ.get('HYPRN_MVP_DATA_ROOT', '')" in source


def test_qualification_requires_the_attestation_coverage_group():
    """The narrowed attestation is safe only while its coverage test runs, so the qualification
    aggregate includes the must-pass group that runs the module-boundary test."""
    import checks as runner
    assert runner.group_class('locality-contracts') == 'must-pass'
    assert 'locality-contracts' in runner.must_pass_groups()
    assert 'application/tests/test_module_boundaries.py' in runner.GROUPS['locality-contracts']
