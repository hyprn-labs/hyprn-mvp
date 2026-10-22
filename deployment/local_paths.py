"""The one place that resolves local data locations for the deployment managers,
their test fixtures and the helper scripts. Stdlib only; importing has no side effects.

Resolution order for every location (first match wins):

1. an explicit command-line flag or function argument, passed in by the caller;
2. the location's own ``HYPRN_MVP_*`` environment variable (below);
3. the installation configuration named by ``HYPRN_MVP_CONFIG`` (``data_root``,
   ``upstream.cache``, ``ports.app``), read and validated by the stdlib loader
   ``integration/src/hyprn_mvp_integration/installation.py``; a refused configuration is a
   refusal, never skipped;
4. a neutral default below the data root (or, for scratch folders, the operating system's
   temporary folder). No operating-system specific folder layout is written here: the per-OS
   defaults live only in the local edition's path policy
   (``editions/local/src/hyprn_mvp_local/paths.py``); where no default can be derived the
   caller refuses with a message naming the variable instead of guessing.

Neutral layout below the data root (every entry relative to ``HYPRN_MVP_DATA_ROOT``)::

    application/            development application store (installation data, credentials,
                            deployed UI)
    modeling/               development modeling store
    execution/              development execution store (attested worker, native profile)
    releases/               retained releases
    fixtures/               durable test fixtures
    cache/upstream/whatsopt verified upstream archive cache
    evidence/               evidence of development runs (logs, reports, screenshots)
    dev/python-native/      native development environment: ``venv/`` plus the reviewed
                            dependency inventory (``selected.json``, ``runtime.json``,
                            ``locks/``, ``licenses/``)
    dev/python-contract/    contract development environment: ``venv/``

Environment variables:

``HYPRN_MVP_DATA_ROOT``
    Absolute path of the development data root (outside the repository and outside any
    synced folder). Every default below needs it; a location that has neither its own
    variable nor the data root refuses with ``LocationUnset``. When it is unset, the
    installation configuration's ``data_root`` is used.
``HYPRN_MVP_CONFIG``
    Absolute path of an installation configuration (``deployment/config.schema.json``). Unset
    by default: deployment code never derives the per-OS default location of this file. Scoped
    test children never receive it.
``HYPRN_MVP_TOOLS_DIR``
    Tool cache: the pinned uv, the uv-managed CPython and the locked development environments
    ``envs/<group>-<first 16 hex of the uv.lock SHA-256>/`` (groups ``contract`` and
    ``native`` of ``uv.lock``). ``./hyprn-mvp`` resolves it (this variable, else the per-OS
    default it computes) and exports it to ``dev check``; deployment code never derives an
    operating-system default for it. The test runner and its scoped fixtures take their
    interpreters only from these locked environments; the fence treats the cache as read-only.
``HYPRN_MVP_NATIVE_PYTHON``
    Native development interpreter. Default ``<data root>/dev/python-native/venv/bin/python``.
    Read by the executor and the release tooling. Scoped test children receive the locked
    native environment's interpreter here.
``HYPRN_MVP_NATIVE_INVENTORY``
    Folder holding the reviewed native dependency inventory (``selected.json``,
    ``runtime.json``, ``locks/``, ``licenses/``) that worker fixtures copy into their scope.
    Default ``<data root>/dev/python-native``.
``HYPRN_MVP_CONTRACT_PYTHON``
    Contract development interpreter (data-only contract generation and application
    tests). Default ``<data root>/dev/python-contract/venv/bin/python``. Scoped test children
    receive the locked contract environment's interpreter here.
``HYPRN_MVP_TEST_FIXTURES_ROOT``
    Durable test fixtures. Default ``<data root>/fixtures``.
``HYPRN_MVP_UPSTREAM_CACHE``
    Verified WhatsOpt upstream archive cache. Then the installation configuration's
    ``upstream.cache``; default ``<data root>/cache/upstream/whatsopt``.
``HYPRN_MVP_EVIDENCE_ROOT``
    Evidence of development runs. Default ``<data root>/evidence``.
``HYPRN_MVP_EXPERIMENT_STORAGE_CONFIG``
    Explicit developer experiment retention policy. Default: experiment-storage.json
    below the data root. Absence disables experiment collection. Not passed to scoped
    children; installation stores are never automatically enrolled.
``HYPRN_MVP_SCRATCH_ROOT``
    Folder that holds scoped test folders (``hyprn-mvp-test-<uuid>``). Default: the
    operating system's temporary folder, resolved to its real path. Scoped test children
    always receive the resolved value, because their own temporary folder is the scope's.
``HYPRN_MVP_LIVE_ROOTS``
    Path-separator list of folders tests must never touch (no read, write, mount or
    container operation). Default: none. The test-safety fence also covers the data root's
    stores without it.
``HYPRN_MVP_PORT``
    Development application port. Then the installation configuration's ``ports.app``;
    refused when neither is set (there is no default port).
``HYPRN_MVP_DOCKER_SOCKET``
    Docker daemon socket path. Default: ``DOCKER_HOST`` when it names a unix socket,
    otherwise the endpoint of the active Docker context.
``HYPRN_MVP_CHROMIUM``
    Chromium executable for browser checks. Default: Playwright's own resolution of its
    installed Chromium.
``HYPRN_MVP_UI_OUT``
    Output folder of a plain ``vite build``. Default ``ui/dist``.
``HYPRN_MVP_UI_BASE_URL`` / ``HYPRN_MVP_UI_PASSWORD_FILE``
    The served installation that served-installation browser specs talk to (its loopback
    origin) and the absolute path of its owner password file. No default: the opt-in served
    groups refuse while either is unset, and refuse live and development installations.
``HYPRN_MVP_LIVE_PORTS`` / ``HYPRN_MVP_LIVE_NAMES``
    Comma-separated loopback ports and Docker container, network or project names of
    installations that tests must never reach (for example another installation running on
    the same host). Default: none. The test-safety fence also refuses the development
    application port and the ``hyprn-mvp`` installation names without them.
``HYPRN_MVP_ENGINE_IMAGE`` / ``HYPRN_MVP_MODELING_SOURCE_IMAGE``
    Numerical engine and WhatsOpt source base image ids (``sha256:<64 hex>``) that the
    execution and modeling managers build from. No default: a build refuses while the
    variable is unset, and refuses an id that differs from the reviewed pin in
    ``deployment/pins.json``.

The attested execution launcher (``launcher.py`` in the integration package) may not import
this module; it reads ``HYPRN_MVP_DATA_ROOT`` the same way, and ``HYPRN_MVP_SCRATCH_ROOT`` to
recognise scoped test folders.

Identities: while ``HYPRN_MVP_DATA_ROOT`` names the development data root, the managers keep
the development store's fixed container, network and owner names and the ambient container
engine; otherwise the installation configuration decides them (``configured_installation``,
read by the same loader as the attested launcher).
"""
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import subprocess
import sys
import tempfile

DATA_ROOT = 'HYPRN_MVP_DATA_ROOT'
CONFIG = 'HYPRN_MVP_CONFIG'
TOOLS_DIR = 'HYPRN_MVP_TOOLS_DIR'
NATIVE_PYTHON = 'HYPRN_MVP_NATIVE_PYTHON'
NATIVE_INVENTORY = 'HYPRN_MVP_NATIVE_INVENTORY'
CONTRACT_PYTHON = 'HYPRN_MVP_CONTRACT_PYTHON'
TEST_FIXTURES_ROOT = 'HYPRN_MVP_TEST_FIXTURES_ROOT'
UPSTREAM_CACHE = 'HYPRN_MVP_UPSTREAM_CACHE'
EVIDENCE_ROOT = 'HYPRN_MVP_EVIDENCE_ROOT'
SCRATCH_ROOT = 'HYPRN_MVP_SCRATCH_ROOT'
CHECK_SESSION = 'HYPRN_MVP_CHECK_SESSION'
LIVE_ROOTS = 'HYPRN_MVP_LIVE_ROOTS'
PORT = 'HYPRN_MVP_PORT'
DOCKER_SOCKET = 'HYPRN_MVP_DOCKER_SOCKET'
CHROMIUM = 'HYPRN_MVP_CHROMIUM'
LIVE_PORTS = 'HYPRN_MVP_LIVE_PORTS'
LIVE_NAMES = 'HYPRN_MVP_LIVE_NAMES'
ENGINE_IMAGE = 'HYPRN_MVP_ENGINE_IMAGE'
MODELING_SOURCE_IMAGE = 'HYPRN_MVP_MODELING_SOURCE_IMAGE'
# Location variables a scoped test child receives unchanged when they are set
# (scoped_fixture.clean_environment); the scratch root is always passed, resolved.
SCOPED_PASS_THROUGH = (DATA_ROOT, TOOLS_DIR, NATIVE_PYTHON, NATIVE_INVENTORY, CONTRACT_PYTHON, TEST_FIXTURES_ROOT,
                       UPSTREAM_CACHE, EVIDENCE_ROOT, CHROMIUM, CHECK_SESSION)
# Value variables (not locations) a scoped test child receives, validated, when they are set.
SCOPED_VALUES = (LIVE_PORTS, LIVE_NAMES, ENGINE_IMAGE, MODELING_SOURCE_IMAGE)

# Neutral layout below the data root.
APPLICATION = 'application'
MODELING = 'modeling'
EXECUTION = 'execution'
RELEASES = 'releases'
FIXTURES = 'fixtures'
UPSTREAM = 'cache/upstream/whatsopt'
EVIDENCE = 'evidence'
NATIVE_ENVIRONMENT = 'dev/python-native'
CONTRACT_ENVIRONMENT = 'dev/python-contract'
INTERPRETER = 'venv/bin/python'
# Scoped test folders: <scratch root>/<SCOPE_PREFIX><uuid>.
SCOPE_PREFIX = 'hyprn-mvp-test-'
# Locked development environments below the tool cache, one per uv.lock group.
LOCK = Path(__file__).resolve().parents[1] / 'uv.lock'
LOCKED_GROUPS = ('contract', 'native')
LOCKED_ENVIRONMENTS = 'envs'
LOCKED_INTERPRETER = 'bin/python'


class LocationUnset(ValueError):
    """A required location is not configured. A ValueError, so every manager's refusal
    handling reports it before any effect."""


def unset_message(name=DATA_ROOT):
    if name == DATA_ROOT:
        return (DATA_ROOT + ' is not set: export it as the absolute path of the development data root '
                '(documented in deployment/local_paths.py) and rerun')
    if name == TOOLS_DIR:
        return (TOOLS_DIR + ' is not set or a locked environment is missing: run the checks through '
                './hyprn-mvp dev check, which provisions the locked environments')
    return (name + ' is not set and ' + DATA_ROOT + ' is not set: export one of them '
            '(documented in deployment/local_paths.py) and rerun')


def absolute(value, name):
    """An explicit absolute, normalized path; anything else is refused."""
    text = os.fspath(value)
    path = Path(text)
    if not text or '\x00' in text or not path.is_absolute() or '..' in path.parts or str(path) != text.rstrip('/'):
        raise LocationUnset(name + ' must be an absolute normalized path')
    return path


def installation():
    """The installation configuration named by HYPRN_MVP_CONFIG, validated by the stdlib
    loader of this checkout; None when the variable is unset. A refused configuration raises
    LocationUnset with the loader's reason."""
    value = os.environ.get(CONFIG, '')
    if not value:
        return None
    path = absolute(value, CONFIG)
    loader = _installation_loader()
    try:
        return loader.load(path, edition='local')
    except loader.InstallationError as error:
        raise LocationUnset(CONFIG + ' names a refused installation configuration (' + error.reason_code + '): '
                            + str(error)) from None


def _installation_loader():
    """integration/src/hyprn_mvp_integration/installation.py of this checkout (imported on
    first use only, with the core application package it reads the location rule from)."""
    repo = Path(__file__).resolve().parents[1]
    for source in ('integration/src', 'application/src'):
        if str(repo / source) not in sys.path:
            sys.path.append(str(repo / source))
    from hyprn_mvp_integration import installation as loader
    if Path(loader.__file__).resolve() != repo / 'integration/src/hyprn_mvp_integration/installation.py':
        raise LocationUnset('the installation loader was imported from outside this checkout: ' + loader.__file__)
    return loader


def data_root(*, required=True):
    value = os.environ.get(DATA_ROOT, '')
    if not value:
        configured = installation()
        if configured is not None:
            return Path(configured['data_root'])
        if required:
            raise LocationUnset(unset_message())
        return None
    return absolute(value, DATA_ROOT)


def configured_installation():
    """The installation configuration that decides the managers' identities: None while
    HYPRN_MVP_DATA_ROOT names the development data root (it comes first, as in the attested
    launcher) or while HYPRN_MVP_CONFIG is unset."""
    cloud = cloud_execution()
    if cloud is not None:
        return cloud
    if os.environ.get(DATA_ROOT, ''):
        return None
    return installation()


def cloud_execution():
    """Cloud execution paths are explicit and never fall back to local stores."""
    if not os.environ.get('HYPRN_MVP_CLOUD_EXECUTION_CONFIG'):
        return None
    return _installation_loader().cloud_from_environment()


def component_names():
    """Compose project, container, network and owner names of the modeling and application
    components (``installation.component_names``): the installation's, or the development
    data root's fixed names."""
    return _installation_loader().component_names(configured_installation())


def owner_username():
    """The owner's sign-in name provisioned with a new application store."""
    return _installation_loader().owner_username(configured_installation())


def docker_environment():
    """Environment of the managers' docker commands: DOCKER_HOST set to the installation's
    engine endpoint, or None (the ambient engine) for the development data root."""
    return _installation_loader().docker_environment(configured_installation())


def installation_name_prefixes():
    """The prefixes every Docker name of an installation starts with (one per edition)."""
    return _installation_loader().NAME_PREFIXES


def under(relative, *, required=True):
    root = data_root(required=required)
    return None if root is None else root / relative


def located(name, relative, *, required=True):
    """``name`` when set, else ``<data root>/relative``; None (or a refusal naming both
    variables) when neither is set."""
    value = os.environ.get(name, '')
    if value:
        return absolute(value, name)
    root = data_root(required=False)
    if root is None:
        if required:
            raise LocationUnset(unset_message(name))
        return None
    return root / relative


def require(value, name=DATA_ROOT):
    """Use-time refusal for module constants that were resolved while unset."""
    if value is None:
        raise LocationUnset(unset_message(name))
    return value


def require_file(path, name):
    """Use-time refusal naming the variable when its location is unset or names no file."""
    path = require(path, name)
    if not Path(path).is_file():
        raise LocationUnset(name + ' does not name an existing file: ' + str(path)
                            + ' (documented in deployment/local_paths.py)')
    return path


def application_root(*, required=True):
    return under(APPLICATION, required=required)


def modeling_root(*, required=True):
    return under(MODELING, required=required)


def execution_root(*, required=True):
    cloud = cloud_execution()
    if cloud is not None:
        return Path(cloud['execution_root'])
    return under(EXECUTION, required=required)


def releases_root(*, required=True):
    return under(RELEASES, required=required)


def store_roots(*, required=True):
    """The development installation's stores: tests never read, write or mount them."""
    root = data_root(required=required)
    return () if root is None else tuple(root / name for name in (APPLICATION, MODELING, EXECUTION, RELEASES))


def native_python(*, required=True):
    """The native development interpreter (an interpreter only; no profile is ever used)."""
    cloud = cloud_execution()
    if cloud is not None:
        return Path(cloud['python'])
    return located(NATIVE_PYTHON, NATIVE_ENVIRONMENT + '/' + INTERPRETER, required=required)


def native_inventory(*, required=True):
    """The reviewed native dependency inventory copied by worker fixtures."""
    return located(NATIVE_INVENTORY, NATIVE_ENVIRONMENT, required=required)


def contract_python(*, required=True):
    """The contract development interpreter (data-only contract generation)."""
    return located(CONTRACT_PYTHON, CONTRACT_ENVIRONMENT + '/' + INTERPRETER, required=required)


def tools_root(*, required=True):
    """The tool cache that ./hyprn-mvp resolved and exported (no default is derived here)."""
    value = os.environ.get(TOOLS_DIR, '')
    if not value:
        if required:
            raise LocationUnset(TOOLS_DIR + ' is not set: run the checks through ./hyprn-mvp dev check, '
                                'which provisions the locked environments and sets it')
        return None
    return absolute(value, TOOLS_DIR)


def lock_sha256(*, required=True):
    """SHA-256 of this checkout's uv.lock; None (or a refusal) when it cannot be read."""
    try:
        return hashlib.sha256(LOCK.read_bytes()).hexdigest()
    except OSError:
        if required:
            raise LocationUnset('uv.lock is missing from the checkout: ' + str(LOCK)) from None
        return None


def locked_environment(group, *, required=True):
    """``<tool cache>/envs/<group>-<lock16>``: the environment of one uv.lock group, named by
    the lock's digest so that a changed lock never reuses an environment of another lock."""
    if group not in LOCKED_GROUPS:
        raise ValueError('Unknown locked environment group: ' + str(group))
    root = tools_root(required=required)
    digest = None if root is None else lock_sha256(required=required)
    return None if digest is None else root / LOCKED_ENVIRONMENTS / (group + '-' + digest[:16])


def locked_python(group, *, required=True):
    """The interpreter of one locked development environment."""
    environment = locked_environment(group, required=required)
    return None if environment is None else environment / LOCKED_INTERPRETER


def fixtures_root(*, required=True):
    return located(TEST_FIXTURES_ROOT, FIXTURES, required=required)


def upstream_archive_root(*, required=True):
    if not os.environ.get(UPSTREAM_CACHE, ''):
        configured = installation()
        if configured is not None:
            return Path(configured['upstream']['cache'])
    return located(UPSTREAM_CACHE, UPSTREAM, required=required)


def evidence_root(*, required=True):
    return located(EVIDENCE_ROOT, EVIDENCE, required=required)


def scratch_root():
    """HYPRN_MVP_SCRATCH_ROOT, else the operating system's temporary folder (real path)."""
    value = os.environ.get(SCRATCH_ROOT, '')
    if value:
        return absolute(value, SCRATCH_ROOT)
    return Path(os.path.realpath(tempfile.gettempdir()))


def live_roots():
    """Every HYPRN_MVP_LIVE_ROOTS entry, each an absolute normalized path; empty when unset."""
    value = os.environ.get(LIVE_ROOTS, '')
    return tuple(absolute(item, LIVE_ROOTS) for item in value.split(os.pathsep) if item)


def live_ports():
    """Every HYPRN_MVP_LIVE_PORTS entry as an int; empty when unset."""
    value = os.environ.get(LIVE_PORTS, '')
    ports = tuple(item.strip() for item in value.split(',') if item.strip())
    if any(not item.isdigit() or not 1 <= int(item) <= 65535 for item in ports):
        raise LocationUnset(LIVE_PORTS + ' must be a comma-separated list of port numbers')
    return tuple(int(item) for item in ports)


def live_names():
    """Every HYPRN_MVP_LIVE_NAMES entry (Docker container, network or project names)."""
    value = os.environ.get(LIVE_NAMES, '')
    names = tuple(item.strip() for item in value.split(',') if item.strip())
    if any(not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', item) for item in names):
        raise LocationUnset(LIVE_NAMES + ' must be a comma-separated list of Docker names')
    return names


def _image(name, required):
    value = os.environ.get(name, '')
    if not value:
        if required:
            raise LocationUnset(name + ' is not set: export the reviewed base image id (sha256:<64 hex>) '
                                '(documented in deployment/local_paths.py) and rerun')
        return None
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', value):
        raise LocationUnset(name + ' must be an image id of the form sha256:<64 hex>')
    return value


def engine_image(*, required=True):
    """Numerical engine base image id that the restricted worker image derives from."""
    return _image(ENGINE_IMAGE, required)


def modeling_source_image(*, required=True):
    """WhatsOpt source base image id that the modeling image builds from."""
    return _image(MODELING_SOURCE_IMAGE, required)


def port(*, required=True):
    """The development application port; refused when unset (there is no default)."""
    value = os.environ.get(PORT, '')
    if not value:
        configured = installation()
        if configured is not None:
            return configured['ports']['app']
        if required:
            raise LocationUnset(PORT + ' is not set: export the development application port and rerun')
        return None
    if not value.isdigit() or not 1024 <= int(value) <= 65535:
        raise LocationUnset(PORT + ' must be a port number from 1024 to 65535')
    return int(value)


def account_home():
    """The account's home folder from the password database, not ``$HOME`` (scoped test
    children replace ``HOME`` with a scope folder)."""
    return Path(pwd.getpwuid(os.getuid()).pw_dir)


def docker_socket():
    """Docker daemon socket: HYPRN_MVP_DOCKER_SOCKET, then a unix ``DOCKER_HOST``, then the
    active Docker context as reported by the docker CLI itself."""
    value = os.environ.get(DOCKER_SOCKET, '')
    if value:
        return absolute(value, DOCKER_SOCKET)
    host = os.environ.get('DOCKER_HOST', '')
    if not host:
        result = subprocess.run(['docker', 'context', 'inspect'], capture_output=True, text=True, timeout=20)
        if result.returncode:
            raise LocationUnset('Docker context unavailable; set ' + DOCKER_SOCKET)
        host = json.loads(result.stdout)[0]['Endpoints']['docker']['Host']
    if not host.startswith('unix://'):
        raise LocationUnset('Docker endpoint is not a local unix socket; set ' + DOCKER_SOCKET)
    return absolute(host.removeprefix('unix://'), 'Docker socket')


def check_storage_root():
    """Supervisor records and bounded diagnostics, separate from disposable scopes."""
    return scratch_root() / ".hyprn-checks"
