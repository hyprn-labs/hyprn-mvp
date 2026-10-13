"""The path policy of the local edition: the one place that knows each operating system's
default folders. Standard library only.

Every location resolves in this order (first match wins):

1. a command-line flag (``--config``, ``--data-dir``), passed in by the caller;
2. the location's ``HYPRN_MVP_*`` environment variable;
3. the installation configuration (``data_root``);
4. the per-OS default below;
5. otherwise the caller's question to the user, whose confirmed answer is recorded. Without a
   question (non-interactive mode) the location is unresolved: ``LocationUnresolved``, reason
   ``location_unresolved``, exit code 2. No path is ever invented.

==========================  ==================  ==================================================
Location                    macOS               Linux and WSL2
==========================  ==================  ==================================================
installation configuration  ~/.config/hyprn-mvp/installation.json
                                                ${XDG_CONFIG_HOME:-~/.config}/hyprn-mvp/installation.json
data root                   ~/Library/Application Support/hyprn-mvp
                                                ${XDG_DATA_HOME:-~/.local/share}/hyprn-mvp
tool cache (uv, CPython)    ~/Library/Caches/hyprn-mvp/tools
                                                ${XDG_CACHE_HOME:-~/.cache}/hyprn-mvp/tools
logs                        <data root>/logs    <data root>/logs
==========================  ==================  ==================================================

``~`` is ``HOME`` when it is absolute, else the account's home folder; a relative ``XDG_*``
value is ignored. ``./hyprn-mvp`` computes the tool-cache default too, because it runs before
Python exists; ``editions/local/tests/test_paths.py`` asserts both agree.

Refusals: every resolved location passes the core location rule
(``hyprn_mvp_app.locations``: synced folders, symbolic links, Windows-mounted drives), the same
rule the installation loader and the application store apply; an existing data root must also
be a folder owned by the user.
"""
from dataclasses import dataclass
import os
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[4]
_CORE = REPO / 'application/src'
if str(_CORE) not in sys.path:
    sys.path.append(str(_CORE))
from hyprn_mvp_app import locations  # noqa: E402  (the shared core location rule)

if Path(locations.__file__).resolve() != _CORE / 'hyprn_mvp_app/locations.py':
    raise ImportError('hyprn_mvp_app.locations was imported from outside this checkout: ' + locations.__file__)

CONFIG = 'HYPRN_MVP_CONFIG'
DATA_ROOT = 'HYPRN_MVP_DATA_ROOT'
TOOLS_DIR = 'HYPRN_MVP_TOOLS_DIR'
PRODUCT = 'hyprn-mvp'
CONFIG_FILE = 'installation.json'
LOGS = 'logs'
# name: (flag, environment variable, installation configuration field)
LOCATIONS = {
    'config': ('--config', CONFIG, None),
    'data_root': ('--data-dir', DATA_ROOT, 'data_root'),
    'tools': (None, TOOLS_DIR, None),
}
# Per-OS defaults: (base folder below the home folder, its XDG variable on Linux, the path
# below that base). macOS keeps its configuration under ~/.config like Linux.
_MACOS = {'config': (('.config',), None, (PRODUCT, CONFIG_FILE)),
          'data_root': (('Library', 'Application Support'), None, (PRODUCT,)),
          'tools': (('Library', 'Caches'), None, (PRODUCT, 'tools'))}
_LINUX = {'config': (('.config',), 'XDG_CONFIG_HOME', (PRODUCT, CONFIG_FILE)),
          'data_root': (('.local', 'share'), 'XDG_DATA_HOME', (PRODUCT,)),
          'tools': (('.cache',), 'XDG_CACHE_HOME', (PRODUCT, 'tools'))}
DEFAULTS = {locations.MACOS: _MACOS, locations.LINUX: _LINUX}

Host = locations.Host
current_host = locations.current_host
location_refusal = locations.location_refusal


class LocationUnresolved(ValueError):
    """A location that no flag, variable, configuration, default or answer decides."""
    reason_code = 'location_unresolved'
    exit_code = 2


class LocationRefused(ValueError):
    """A location the policy refuses (synced, symbolic link, Windows-mounted, foreign owner)."""
    reason_code = 'location_refused'
    exit_code = 2


@dataclass(frozen=True)
class Resolved:
    path: Path
    source: str  # flag, environment, configuration, default or answer


def home(environ=None, host=None):
    """``HOME`` when it is absolute and normalized, else the account's home folder."""
    environ = os.environ if environ is None else environ
    value = environ.get('HOME', '')
    if locations.normalized(value) is not None:
        return Path(value)
    host = current_host(environ) if host is None else host
    account = next(iter(host.homes), None)
    if account is None:
        raise LocationUnresolved('the home folder is unknown: set HOME or pass the location explicitly')
    return account


def default(name, *, environ=None, host=None):
    """The per-OS default of ``name``; LocationUnresolved on a host without one."""
    environ = os.environ if environ is None else environ
    host = current_host(environ) if host is None else host
    table = DEFAULTS.get(host.system)
    if table is None or name not in table:
        raise LocationUnresolved('no default ' + name.replace('_', ' ') + ' on ' + host.system
                                 + ': pass it explicitly')
    base, variable, below = table[name]
    root = None
    if variable is not None and locations.normalized(environ.get(variable, '')) is not None:
        root = Path(environ[variable])
    if root is None:
        root = home(environ, host).joinpath(*base)
    return root.joinpath(*below)


def logs(data_root):
    return Path(data_root) / LOGS


def admit(path, *, name, host=None):
    """Refuse ``path`` unless it is absolute, normalized and accepted by the location rule;
    an existing data root must also be a real folder owned by this user."""
    reason = location_refusal(path, host)
    if reason is not None:
        raise LocationRefused('refusing the ' + name.replace('_', ' ') + ' ' + os.fspath(path) + ': ' + reason)
    path = Path(path)
    if name == 'data_root' and path.exists():
        status = path.lstat()
        if not path.is_dir() or status.st_uid != os.getuid():
            raise LocationRefused('refusing the data root ' + str(path) + ': it is not a folder owned by this user')
    return path


def resolve(name, *, flag=None, configuration=None, environ=None, host=None, ask=None):
    """Resolve one location in the documented order and admit it.

    ``ask(name, reason)`` is the caller's question to the user (interactive setup); it returns
    the confirmed path or None. Without it an otherwise unresolved location is refused with
    ``location_unresolved``."""
    if name not in LOCATIONS:
        raise ValueError('Unknown location: ' + str(name))
    environ = os.environ if environ is None else environ
    host = current_host(environ) if host is None else host
    option, variable, field = LOCATIONS[name]
    candidates = (('flag', flag), ('environment', environ.get(variable) or None),
                  ('configuration', (configuration or {}).get(field) if field else None))
    for source, value in candidates:
        if value is not None:
            return Resolved(admit(value, name=name, host=host), source)
    try:
        return Resolved(admit(default(name, environ=environ, host=host), name=name, host=host), 'default')
    except (LocationUnresolved, LocationRefused) as error:  # no usable default: ask
        reason = str(error)
    if ask is not None:
        answer = ask(name, reason)
        if answer is not None:
            return Resolved(admit(answer, name=name, host=host), 'answer')
    hint = ' or '.join(item for item in (option, variable) if item)
    raise LocationUnresolved(name.replace('_', ' ') + ' unresolved (' + reason + '); set ' + hint)
