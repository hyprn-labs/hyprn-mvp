"""Process-wide live-runtime fence for deployment test modules.

Shared so every deployment test module can opt in. Importing this module installs one audit
hook (hooks cannot be removed) with a BASELINE policy for the rest of the process:

- no access at all to any ``HYPRN_MVP_LIVE_ROOTS`` entry, nor to anything below the
  development data root (its stores, releases, evidence and any other folder), except the
  development interpreters (and the tool cache holding the locked environments), the native
  dependency inventory, the durable test fixtures and the upstream archive cache, which may
  only be read or executed, wherever they are configured
  (including the real targets of their top-level links, which may lie inside a live root);
  a scratch root configured as a dedicated folder below the data root (HYPRN_MVP_SCRATCH_ROOT,
  overlapping no store, evidence folder, read-only location or live root) holds the scoped
  test folders and is the one place there that tests use;
- no docker invocation that names a path inside a live root, below the data root (outside that
  scratch root) or inside a read-only location (bind mounts, build contexts, copies);
- no connection to a ``HYPRN_MVP_LIVE_PORTS`` port or to ``HYPRN_MVP_PORT``;
- no launchctl/kill/pkill/osascript/crontab/curl/os.system and no management entry point
  present in the repository (modeling_runtime.py, dispatch_runtime.py, manage.py, ...) as a child;
- docker may not name an installation container, network or compose project (the ``hyprn-mvp``
  installation names and every ``HYPRN_MVP_LIVE_NAMES`` entry);
- signals only to processes this test process started.

A module whose tests need no container or signal declares the stricter UNIT policy for
its tests (``unit_fence`` for pytest, ``unit_module_fence`` for unittest): docker,
docker sockets and every non-probe signal are refused as well. Every refusal raises
LiveRuntimeAccess (not OSError, so product error handling cannot absorb it) and is
recorded; the fixtures fail the test that caused it even if the exception was caught.

Children started by product code with a scoped clean environment are not hooked; they
are bound by the scoped-fixture guard instead (documented limitation). No installation
configuration file exists yet (deployment/local_paths.py, resolution step 3), so the fence
names none.

The locations come from deployment/local_paths.py; importing this module refuses while
HYPRN_MVP_DATA_ROOT is unset.
"""
import os
from pathlib import Path
import re
import subprocess
import sys
import types

_DEPLOYMENT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _DEPLOYMENT not in sys.path:
    sys.path.append(_DEPLOYMENT)
import local_paths  # noqa: E402


def _strs(paths):
    return tuple(sorted({str(p) for p in paths if p is not None}))


def _environment(path):
    """The environment folder of an interpreter ``<environment>/bin/python``."""
    return None if path is None else Path(path).parents[1]


# Fail closed: a fence that does not know the data root refuses to load, so no guarded test
# runs without it.
DATA_ROOT = str(local_paths.data_root())
LIVE_ROOTS = _strs(local_paths.live_roots())
# Never read or written: everything below the data root (its stores included) and the
# evidence folder wherever it is configured, except the read-only locations below.
PROTECTED_ROOTS = _strs((DATA_ROOT, *local_paths.store_roots(), local_paths.evidence_root()))


def _read_only(paths):
    """The configured read-only locations plus the real targets of their top-level links and of
    the links in their package folders (``lib/python*/site-packages``): a development environment
    may link its libraries from another folder, even from a live root. A location that would
    cover a whole live root is never read-only."""
    found = set()
    for path in (str(p) for p in paths if p is not None):
        found.update((path, os.path.realpath(path)))
        if os.path.isdir(path) and not os.path.islink(path):
            folders = [path, *(str(p) for p in Path(path).glob('lib/python*/site-packages') if not p.is_symlink())]
            for folder in folders:
                found.update(os.path.realpath(entry.path) for entry in os.scandir(folder) if entry.is_symlink())
    return tuple(sorted(root for root in found if not any(
        live == root or live.startswith(root.rstrip('/') + '/') for live in LIVE_ROOTS)))


# Development interpreters (with the tool cache that holds the locked environments and their
# CPython), dependency inventory, durable fixtures and archive cache: read or execute only,
# never write. Inside a live root only these locations may be read.
READ_ONLY_ROOTS = _read_only((
    local_paths.tools_root(required=False),
    _environment(local_paths.native_python(required=False)),
    _environment(local_paths.contract_python(required=False)),
    local_paths.native_inventory(required=False), local_paths.fixtures_root(required=False),
    local_paths.upstream_archive_root(required=False)))


def _test_areas(scratch, data_root, blocked):
    """The configured scratch root when it is a dedicated folder strictly below the data root:
    the one place there that tests may use. It must neither hold nor lie inside a store, the
    evidence folder, a read-only location or a live root; otherwise nothing is exempt."""
    scratch, data_root = os.path.normpath(scratch), os.path.normpath(data_root)
    if not scratch.startswith(data_root.rstrip('/') + '/'):
        return ()
    for root in blocked:
        root = os.path.normpath(root)
        if root == scratch or root.startswith(scratch + '/') or scratch.startswith(root.rstrip('/') + '/'):
            return ()
    return (scratch,)


# Scoped test folders (<scratch root>/hyprn-mvp-test-<uuid>) are read and written by the tests
# that own them, also when the scratch root is configured below the data root.
TEST_AREAS = _test_areas(str(local_paths.scratch_root()), DATA_ROOT,
                         (*local_paths.store_roots(), local_paths.evidence_root(), *READ_ONLY_ROOTS, *LIVE_ROOTS))
LIVE_PORTS = frozenset({*local_paths.live_ports(), *((local_paths.port(),) if os.environ.get(local_paths.PORT) else ())})
ALWAYS_BLOCKED_PROGRAMS = frozenset({'launchctl', 'kill', 'pkill', 'killall', 'osascript', 'crontab', 'curl'})
# Installation containers, networks and the compose project of a hyprn-mvp installation, plus
# the names of any other installation on this host (HYPRN_MVP_LIVE_NAMES).
INSTALLATION_DOCKER_NAMES = frozenset({
    'hyprn-mvp', 'hyprn-mvp-application', 'hyprn-mvp-modeling', 'hyprn-mvp-private', 'hyprn-mvp-public',
    'hyprn-mvp-execution'})
LIVE_DOCKER_NAMES = INSTALLATION_DOCKER_NAMES | frozenset(local_paths.live_names())
# Management entry points present in the repository: never spawned by a guarded test,
# whatever the root argument.
LIVE_ENTRYPOINTS = frozenset({'modeling_runtime.py', 'dispatch_runtime.py', 'manage.py', 'application_runtime.py',
                              'initialize_stores.py', 'execution_runtime.py', 'native_environment.py',
                              'launch_worker.py', 'backup_immutable.py'})
READ_EVENTS = frozenset({'import', 'os.listdir', 'os.scandir', 'subprocess.Popen', 'os.posix_spawn',
                         'os.exec', 'os.spawn', 'glob.glob', 'os.chdir'})
# Only events that touch a path or start a process are path-checked (os.putenv of a live
# string, used by refusal tests, is not access).
PATH_EVENTS = READ_EVENTS | frozenset({
    'open', 'os.mkdir', 'os.rmdir', 'os.remove', 'os.rename', 'os.chmod', 'os.chown', 'os.utime',
    'os.symlink', 'os.link', 'os.truncate', 'os.chflags', 'os.lchflags', 'os.setxattr', 'os.removexattr',
    'os.getxattr', 'os.listxattr', 'shutil.copyfile', 'shutil.copymode', 'shutil.copystat', 'shutil.copytree',
    'shutil.move', 'shutil.rmtree', 'shutil.chown', 'shutil.make_archive', 'shutil.unpack_archive',
    'sqlite3.connect', 'sqlite3.connect/handle', 'tempfile.mkstemp', 'tempfile.mkdtemp', 'os.startfile'})
WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC

STATE = types.SimpleNamespace(policy='baseline', trips=[], children=set(), busy=False)


class LiveRuntimeAccess(RuntimeError):
    """Raised by the fence; deliberately not an OSError."""


def _strings(value, depth=0):
    if isinstance(value, (str, bytes, os.PathLike)):
        try:
            yield os.fsdecode(value)
        except TypeError:
            return
    elif isinstance(value, (list, tuple)) and depth < 3:
        for item in value:
            yield from _strings(item, depth + 1)


def _normal(text):
    return os.path.normpath(text) if text.startswith('/') else text


def _under(text, roots):
    """``text`` is one of ``roots`` or below one of them (path semantics, not name prefixes)."""
    text = _normal(text)
    return any(text == root or text.startswith(root.rstrip('/') + '/') for root in roots)


_BOUNDARY = frozenset('/,:=" \'')


def _mentions(text, roots):
    """A docker argument that names a path inside ``roots`` anywhere in it (``-v``,
    ``--mount source=``, build contexts, ``cp`` operands)."""
    for root in roots:
        start = text.find(root)
        while start >= 0:
            end = start + len(root)
            if (start == 0 or text[start - 1] in _BOUNDARY) and (end == len(text) or text[end] in _BOUNDARY):
                return True
            start = text.find(root, start + 1)
    return False


def _without(text, areas):
    """``text`` with every whole-path mention of a test area masked (a sibling folder whose name
    merely starts with the area's name stays visible)."""
    for area in areas:
        text = re.sub(re.escape(area) + r'(?=[/,:=" \']|$)', '\0', text)
    return text


# Events whose first argument is only read (a link target or a copy source); the others are written.
SOURCE_READ_EVENTS = frozenset({'os.symlink', 'os.link', 'shutil.copyfile', 'shutil.copymode', 'shutil.copystat',
                                'shutil.copytree'})


def _live_reason(event, args):
    read_only = event in READ_EVENTS
    if event == 'open' and len(args) >= 3:
        mode, flags = args[1], args[2]
        read_only = (not isinstance(mode, str) or not set(mode) & set('wax+')) and not (flags or 0) & WRITE_FLAGS
    if event in SOURCE_READ_EVENTS and isinstance(args, tuple) and args:
        reason = _live_reason('open', (args[0], 'r', 0))
        return reason or _live_reason('os.mkdir', args[1:])
    for text in _strings(args):
        if _under(text, READ_ONLY_ROOTS):
            if read_only:
                continue
            return 'read-only location ' + text
        if _under(text, LIVE_ROOTS):
            return 'live root ' + text
        if _under(text, TEST_AREAS):
            continue
        if _under(text, PROTECTED_ROOTS):
            return 'protected location ' + text
    return None


def _program(argv):
    first = argv[0] if isinstance(argv, (list, tuple)) and argv else argv
    return os.path.basename(os.fsdecode(first)) if isinstance(first, (str, bytes, os.PathLike)) else ''


def decide(event, args, policy):
    """Pure decision used by the hook and by the guard tests: refusal reason or None."""
    reason = None
    if event in ('os.kill', 'os.killpg'):
        target, signal = args[0], args[1]
        if signal != 0 and (policy == 'unit' or target not in STATE.children):
            reason = 'signal %s to %s' % (signal, target)
    elif event == 'os.system':
        reason = 'os.system'
    elif event == 'socket.connect' and len(args) >= 2:
        address = args[1]
        if isinstance(address, tuple) and len(address) >= 2 and address[1] in LIVE_PORTS:
            reason = 'live port %s' % (address[1],)
        elif isinstance(address, (str, bytes)) and 'docker' in os.fsdecode(address) and policy == 'unit':
            reason = 'docker socket'
    elif event in ('subprocess.Popen', 'os.posix_spawn', 'os.exec', 'os.spawn'):
        argv = args[1] if event == 'subprocess.Popen' else (args[1] if len(args) > 1 else args[0])
        program = _program(argv) or _program(args[0])
        names = {os.path.basename(t) for t in _strings(argv)}
        if program in ALWAYS_BLOCKED_PROGRAMS:
            reason = 'program ' + program
        elif names & LIVE_ENTRYPOINTS:
            reason = 'live entry point ' + sorted(names & LIVE_ENTRYPOINTS)[0]
        elif program == 'docker':
            tokens = set(_strings(argv))
            if policy == 'unit':
                reason = 'docker under the unit policy'
            elif tokens & LIVE_DOCKER_NAMES or 'compose' in tokens:
                reason = 'docker names a live resource'
            elif any(_mentions(t, (*LIVE_ROOTS, *READ_ONLY_ROOTS)) or _mentions(_without(t, TEST_AREAS), PROTECTED_ROOTS)
                     for t in tokens):
                reason = 'docker names a protected location'
    if reason is None and event in PATH_EVENTS:
        reason = _live_reason(event, args)
    return reason


def _audit(event, args):
    if STATE.busy:
        return
    reason = decide(event, args, STATE.policy)
    if reason:
        STATE.busy = True
        try:
            STATE.trips.append((event, reason, repr(args)[:300]))
        finally:
            STATE.busy = False
        raise LiveRuntimeAccess('live fence refused ' + event + ': ' + reason)


def _track_children():
    original = subprocess.Popen.__init__
    if getattr(original, '_hyprn_mvp_live_fence', False):
        return

    def tracking(self, *args, **kwargs):
        original(self, *args, **kwargs)
        STATE.children.add(self.pid)  # Own children (and their own new sessions) only.
    tracking._hyprn_mvp_live_fence = True
    subprocess.Popen.__init__ = tracking


if not getattr(sys, '_hyprn_mvp_live_fence_installed', False):
    _track_children()
    sys.addaudithook(_audit)
    sys._hyprn_mvp_live_fence_installed = True


def enter(policy):
    if policy not in ('baseline', 'unit'):
        raise ValueError('Unknown live fence policy')
    previous = STATE.policy
    STATE.policy = policy
    STATE.trips.clear()
    return previous


def leave(previous):
    trips = list(STATE.trips)
    STATE.trips.clear()
    STATE.policy = previous
    if trips:
        raise AssertionError('Live-runtime fence trips: %r' % (trips,))


def pytest_fixture(policy):
    """Autouse fixture factory: fence every test of the declaring module."""
    import pytest

    @pytest.fixture(autouse=True)
    def live_runtime_fence():
        previous = enter(policy)
        try:
            yield
        finally:
            leave(previous)
    return live_runtime_fence


def unittest_module_hooks(policy):
    """setUpModule/tearDownModule pair for unittest modules."""
    saved = []

    def set_up():
        saved.append(enter(policy))

    def tear_down():
        leave(saved.pop() if saved else 'baseline')
    return set_up, tear_down
