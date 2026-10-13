"""Pinned toolchain and locked development environments (standard library only).

``./hyprn-mvp`` verifies uv against ``deployment/locks/tools.json``, lets it provision the
pinned CPython and the locked contract environment, exports ``HYPRN_MVP_TOOLS_DIR`` and runs
this CLI there. This module finds the same artifacts from the same pins, installs the native
environment, and verifies that every locked environment holds exactly the reviewed
distributions of its ``uv.lock`` group: an extra, missing or different distribution is refused,
never repaired silently.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tomllib

REPO = Path(__file__).resolve().parents[4]
TOOLS_JSON = REPO / 'deployment/locks/tools.json'
PYPROJECT = REPO / 'pyproject.toml'
PLATFORMS = {('Darwin', 'arm64'): 'darwin-arm64', ('Linux', 'x86_64'): 'linux-x86_64',
             ('Linux', 'aarch64'): 'linux-aarch64'}
# Authored AiiDA plugin registration of the integration package, the only distribution the
# native environment holds beyond its uv.lock group: metadata and entry points only, no code
# and no startup path file, so the environment never names a checkout. The code itself is
# imported from the checkout under test.
PLUGIN_DIST_INFO = 'hyprn_mvp_integration-0.1.0.dist-info'
PLUGIN = ('hyprn-mvp-integration', '0.1.0')
PLUGIN_FILES = {
    'METADATA': 'Metadata-Version: 2.1\nName: hyprn-mvp-integration\nVersion: 0.1.0\n',
    'entry_points.txt': ('[aiida.calculations]\nhyprn_mvp.scalar = hyprn_mvp_integration.calculation:ScalarCalculation\n\n'
                         '[aiida.parsers]\nhyprn_mvp.scalar = hyprn_mvp_integration.calculation:ScalarParser\n'),
}
INVENTORY = ('import importlib.metadata as m, json; '
             'print(json.dumps(sorted([d.metadata["Name"], d.version] for d in m.distributions())))')


class ToolchainError(RuntimeError):
    """A refusal with the CLI exit code: 2 invalid input or location, 3 unsupported host,
    5 failed verification or dependency."""

    def __init__(self, message, code=5):
        super().__init__(message)
        self.code = code


def local_paths():
    """deployment/local_paths.py of this checkout (the locked environments' locations)."""
    deployment = str(REPO / 'deployment')
    if deployment not in sys.path:
        sys.path.append(deployment)
    import local_paths as module
    if Path(module.__file__).resolve() != REPO / 'deployment/local_paths.py':
        raise ToolchainError('local_paths was imported from outside this checkout: ' + module.__file__)
    return module


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pins():
    return json.loads(TOOLS_JSON.read_bytes())


def platform_key(system=None, machine=None):
    """The supported host this process runs on; macOS on Intel and every other host refused."""
    uname = os.uname()
    system, machine = system or uname.sysname, machine or uname.machine
    machine = {'amd64': 'x86_64', 'arm64': 'arm64' if system == 'Darwin' else 'aarch64'}.get(machine, machine)
    key = PLATFORMS.get((system, machine))
    if key is None:
        refused = pins()['refused_platforms'].get(system.lower() + '-' + machine)
        raise ToolchainError(refused or 'unsupported host ' + system + ' ' + machine
                             + ': use macOS on Apple silicon, Linux (glibc), or Windows through WSL2', 3)
    return key


def tools_root():
    paths = local_paths()
    try:
        return paths.tools_root()
    except paths.LocationUnset as error:
        raise ToolchainError(str(error), 2) from None


def uv():
    """The verified uv of the tool cache (./hyprn-mvp placed it after checking its archive)."""
    pinned = pins()
    path = tools_root() / 'uv' / pinned['uv_version'] / platform_key() / 'uv'
    if not path.is_file():
        raise ToolchainError('uv ' + pinned['uv_version'] + ' is not in the tool cache; run ./hyprn-mvp')
    version = subprocess.run([str(path), '--version'], capture_output=True, text=True).stdout.strip()
    if version.split(' ')[:2] != ['uv', pinned['uv_version']]:
        raise ToolchainError(str(path) + ' is not uv ' + pinned['uv_version'])
    return path, version


def hermetic_environment(environment):
    """The process environment for uv: ambient uv settings removed (except the TLS trust
    choice), the pinned interpreter source and the tool-cache folders set."""
    pinned, root = pins(), tools_root()
    env = {k: v for k, v in os.environ.items()
           if not k.startswith('UV_') or k in ('UV_SYSTEM_CERTS', 'UV_NATIVE_TLS')}
    for name in ('VIRTUAL_ENV', 'CONDA_PREFIX', 'PYTHONPATH', 'PYTHONHOME', 'PYTHONSTARTUP', 'PYTHONUSERBASE'):
        env.pop(name, None)
    env.update(UV_NO_CONFIG='1', UV_PYTHON_PREFERENCE='only-managed', UV_PYTHON_INSTALL_DIR=str(root / 'python'),
               UV_PYTHON_BIN_DIR=str(root / 'python-bin'), UV_CACHE_DIR=str(root / 'uv-cache'),
               UV_PYTHON_INSTALL_MIRROR=pinned['cpython_install_mirror'], UV_NO_PROGRESS='1',
               UV_PROJECT_ENVIRONMENT=str(environment))
    return env


def normalized(name):
    return re.sub(r'[-_.]+', '-', name).lower()


def reviewed(group):
    """The exact pins of one uv.lock group (pyproject.toml), as {name: version}."""
    entries = tomllib.loads(PYPROJECT.read_text())['dependency-groups'][group]
    pinned = {}
    for entry in entries:
        match = re.fullmatch(r'([A-Za-z0-9][A-Za-z0-9._-]*)==([A-Za-z0-9.+!]+)', entry)
        if match is None or normalized(match[1]) in pinned:
            raise ToolchainError('pyproject.toml group ' + group + ' has a non-exact or repeated pin: ' + entry)
        pinned[normalized(match[1])] = match[2]
    return pinned


def expected(group):
    pinned = reviewed(group)
    if group == 'native':
        pinned[PLUGIN[0]] = PLUGIN[1]
    return pinned


def environment(group):
    paths = local_paths()
    try:
        return paths.locked_environment(group)
    except paths.LocationUnset as error:
        raise ToolchainError(str(error), 2) from None


def python(group):
    return environment(group) / 'bin/python'


def site_packages(group):
    version = pins()['cpython_version'].rsplit('.', 1)[0]
    return environment(group) / 'lib' / ('python' + version) / 'site-packages'


def installed(interpreter):
    """{name: version} of every distribution the interpreter sees in isolated mode."""
    result = subprocess.run([str(interpreter), '-I', '-B', '-c', INVENTORY], capture_output=True, text=True)
    if result.returncode:
        raise ToolchainError('cannot read the distributions of ' + str(interpreter) + ': ' + result.stderr.strip())
    found = {}
    for name, version in json.loads(result.stdout):
        if normalized(name) in found:
            raise ToolchainError('two installed distributions are named ' + name + ' in ' + str(interpreter))
        found[normalized(name)] = version
    return found


def verify(group):
    """Refuse a locked environment whose distributions differ from its reviewed group."""
    interpreter = python(group)
    if not interpreter.is_file():
        raise ToolchainError('the locked ' + group + ' environment is not installed: ' + str(environment(group)))
    actual, wanted = installed(interpreter), expected(group)
    if actual != wanted:
        extra = sorted(f'{n}=={v}' for n, v in actual.items() if wanted.get(n) != v)
        missing = sorted(f'{n}=={v}' for n, v in wanted.items() if actual.get(n) != v)
        raise ToolchainError('the locked ' + group + ' environment ' + str(environment(group))
                             + ' differs from uv.lock (unexpected: ' + (', '.join(extra) or 'none')
                             + '; missing: ' + (', '.join(missing) or 'none') + '); delete it and rerun')
    return interpreter


def write_plugin():
    """Write the authored plugin registration only where it is absent or different."""
    folder = site_packages('native') / PLUGIN_DIST_INFO
    folder.mkdir(mode=0o700, exist_ok=True)
    for name, text in PLUGIN_FILES.items():
        target = folder / name
        if target.is_symlink() or not target.is_file() or target.read_text() != text:
            staged = folder / ('.' + name + '.' + str(os.getpid()))
            staged.write_text(text)
            os.replace(staged, target)


def provision(group):
    """Install one locked group with uv from uv.lock only (no resolution, no source builds),
    then verify its distributions. The native environment keeps its authored plugin
    registration, so uv leaves undeclared distributions in place there and the verification
    refuses any other one."""
    path, _ = uv()
    target = environment(group)
    command = [str(path), 'sync', '--quiet', '--project', str(REPO), '--frozen', '--no-build',
               '--exact' if group == 'contract' else '--inexact', '--no-install-project', '--no-default-groups',
               '--group', group, '--no-python-downloads', '--python', pins()['cpython_version']]
    result = subprocess.run(command, env=hermetic_environment(target), cwd=REPO)
    if result.returncode:
        raise ToolchainError('uv could not install the locked ' + group + ' environment from uv.lock')
    if group == 'native':
        write_plugin()
    return verify(group)


def build_tag(prefix):
    """The python-build-standalone build of a uv-managed interpreter, from its BUILD file."""
    try:
        return (Path(prefix) / 'BUILD').read_text().strip()
    except OSError:
        return None


def identities():
    pinned = pins()
    _, uv_version = uv()
    lock = local_paths().lock_sha256()
    try:
        commit = subprocess.run(['git', '-C', str(REPO), 'rev-parse', 'HEAD'], capture_output=True,
                                text=True, timeout=20).stdout.strip() or None
    except (OSError, subprocess.TimeoutExpired):
        commit = None
    return dict(
        edition='local',
        tool=dict(uv=uv_version, tools_json_sha256=sha256(TOOLS_JSON)),
        python=dict(version='.'.join(map(str, sys.version_info[:3])), build=build_tag(sys.base_prefix),
                    pinned_version=pinned['cpython_version'], pinned_build=pinned['cpython_build'],
                    executable=sys.executable),
        lock=dict(uv_lock_sha256=lock, pyproject_sha256=sha256(PYPROJECT),
                  environments={group: dict(path=str(environment(group)), installed=python(group).is_file())
                                for group in ('contract', 'native')}),
        release=dict(installed=None, checkout_commit=commit),
    )
