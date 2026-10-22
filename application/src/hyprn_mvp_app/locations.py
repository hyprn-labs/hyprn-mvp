"""The one rule that refuses a location for HYPRN MVP data. Standard library only; importing
has no side effects.

Live stores, configuration, logs, scratch folders and checkouts never live where a sync client
or another file system can rewrite, delay, duplicate or upload them, and never behind a symbolic
link that could redirect them. ``location_refusal`` returns the reason a path is refused, or
``None``:

- a path that is not absolute and normalized (no ``.`` or ``..`` component, no repeated or
  trailing separator);
- a folder of a sync client on every operating system: a path component that starts with
  ``Dropbox``, ``OneDrive``, ``Google Drive`` or ``GoogleDrive``, or that is ``My Drive``;
- on macOS, a folder that the system or iCloud may sync: ``<home>/Library/CloudStorage``,
  ``<home>/Library/Mobile Documents``, ``<home>/Desktop`` and ``<home>/Documents``;
- on Windows Subsystem for Linux (WSL2), a Windows drive mounted under ``/mnt/<letter>``;
- a symbolic link as the path itself or as any existing parent.

The given path and its resolved form are both checked against the folder rules. Every
component that uses a location applies this same rule: the local edition's path policy
(``editions/local/src/hyprn_mvp_local/paths.py``, which also owns the per-OS defaults), the
installation configuration loader (``hyprn_mvp_integration.installation``) and the application
store. It lives in the shared core because the application store runs inside the application
container, which carries neither the local edition nor the integration package.

Host facts (operating system, WSL2, home folders) are read when a check runs, never at import;
tests inject them through ``Host`` or ``current_host``'s arguments.
"""

from dataclasses import dataclass
import os
from pathlib import Path
import pwd
import re

MACOS = 'macos'
LINUX = 'linux'
# Sync clients that may use a folder anywhere, on every operating system.
SYNC_PREFIXES = ('Dropbox', 'OneDrive', 'Google Drive', 'GoogleDrive')
SYNC_NAMES = ('My Drive',)
# macOS folders below a home folder that the system or iCloud may sync, with their reasons.
MACOS_SYNCED = (
    (('Library', 'CloudStorage'), 'it is inside ~/Library/CloudStorage (a cloud storage provider)'),
    (('Library', 'Mobile Documents'), 'it is inside ~/Library/Mobile Documents (iCloud Drive)'),
    (('Desktop',), 'it is inside ~/Desktop, which iCloud may sync'),
    (('Documents',), 'it is inside ~/Documents, which iCloud may sync'),
)
WINDOWS_DRIVE = re.compile(r'[A-Za-z]')
WSL_KERNEL = 'microsoft'
OSRELEASE = '/proc/sys/kernel/osrelease'


class LocationRefused(ValueError):
    """A location the rule refuses. A ValueError, so every refusal handler reports it before
    any effect."""


@dataclass(frozen=True)
class Host:
    """The facts the rule depends on: ``system`` (``macos``, ``linux`` or another lower-case
    system name), whether Linux runs under WSL2, and the account's home folders (the password
    database entry and ``HOME``, each with its resolved form)."""

    system: str
    wsl: bool = False
    homes: tuple = ()


def _homes(values):
    found = []
    for value in values:
        if value and os.path.isabs(value):
            for path in (Path(os.path.normpath(value)), Path(os.path.realpath(value))):
                if path not in found:
                    found.append(path)
    return tuple(found)


def current_host(environ=None, *, system=None, osrelease=None, account_home=None):
    """The host this process runs on. Every argument may be injected; otherwise ``uname``,
    the kernel release file (Linux), the password database and ``environ['HOME']`` decide.
    WSL2 is recognised by ``WSL_DISTRO_NAME`` or a kernel release naming Microsoft."""
    environ = os.environ if environ is None else environ
    name = (system or os.uname().sysname).lower()
    name = MACOS if name == 'darwin' else name
    wsl = False
    if name == LINUX:
        if osrelease is None:
            try:
                with open(OSRELEASE, encoding='utf-8', errors='replace') as stream:
                    osrelease = stream.read(256)
            except OSError:
                osrelease = ''
        wsl = bool(environ.get('WSL_DISTRO_NAME')) or WSL_KERNEL in osrelease.lower()
    if account_home is None:
        try:
            account_home = pwd.getpwuid(os.getuid()).pw_dir
        except KeyError:  # an account without a password database entry (some containers)
            account_home = ''
    return Host(system=name, wsl=wsl, homes=_homes((account_home, environ.get('HOME', ''))))


def normalized(path):
    """``path`` as an absolute normalized Path, or None."""
    text = os.fspath(path)
    if not isinstance(text, str) or not text or '\x00' in text:
        return None
    candidate = Path(text)
    if not candidate.is_absolute() or str(candidate) != text or '..' in candidate.parts:
        return None
    return candidate


def _synced(path, host):
    for part in path.parts[1:]:
        if part.startswith(SYNC_PREFIXES) or part in SYNC_NAMES:
            return (
                'it is inside a '
                + next((p for p in (*SYNC_PREFIXES, *SYNC_NAMES) if part.startswith(p)), part)
                + ' folder, which a sync client may rewrite or upload'
            )
    if host.system == MACOS:
        for home in host.homes:
            if path.is_relative_to(home):
                below = path.relative_to(home).parts
                for prefix, reason in MACOS_SYNCED:
                    if below[: len(prefix)] == prefix:
                        return reason
    if (
        host.wsl
        and len(path.parts) >= 3
        and path.parts[1] == 'mnt'
        and WINDOWS_DRIVE.fullmatch(path.parts[2])
    ):
        return 'it is on a Windows drive mounted under /mnt (use a folder of the Linux file system)'
    return None


def location_refusal(path, host=None):
    """Why ``path`` may not hold HYPRN MVP data or a checkout, or None when it may."""
    candidate = normalized(path)
    if candidate is None:
        return 'it is not an absolute normalized path'
    host = current_host() if host is None else host
    for form in (candidate, Path(os.path.realpath(candidate))):
        reason = _synced(form, host)
        if reason is not None:
            return reason
    for part in (candidate, *candidate.parents):
        if part.is_symlink():
            return 'it has a symbolic link at ' + str(part) + ' (use the real folder)'
    return None


def refuse_location(path, host=None, *, what='Location'):
    """Raise LocationRefused naming the rule when ``path`` is refused; return it otherwise."""
    reason = location_refusal(path, host)
    if reason is not None:
        raise LocationRefused(what + ' refused (' + os.fspath(path) + '): ' + reason)
    return path
