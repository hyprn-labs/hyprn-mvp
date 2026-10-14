"""Installation configuration loader, version 1. Standard library only; no side effect on import.

The configuration is one closed JSON object (``deployment/config.schema.json`` documents the
same fields; ``deployment/tests/test_installation_config.py`` holds both to the same
decisions). The loader takes an explicit path and refuses, before returning anything:

- a file that is not a regular file, has a symbolic link as itself or any parent, is readable
  or writable by group or others, or is owned by another user; a folder that is not owned by
  the user or is open to group or others (the file is 0600 in a 0700 folder);
- invalid UTF-8 or JSON, duplicate keys, ``NaN`` or infinite numbers, unknown or missing
  fields, wrong types or values;
- an edition other than the caller's;
- a data root or upstream cache that the core location rule refuses (synced folder, symbolic
  link, Windows-mounted drive: ``hyprn_mvp_app.locations``), an upstream cache outside the data
  root, or an existing data root that is not a folder owned by the user and closed to group
  and others.

Never in the configuration: secrets, worker policy or limits, image ids. Every refusal is an
``InstallationError`` naming a reason code; the local edition reports it with exit code 2.

This module belongs to the attested execution source set: the launcher takes its execution
root, runtime owner, native profile, Docker endpoint and the home folder its containment probe
checks from the configuration loaded here, and the modeling and application managers take their
container, network and project names, ownership label, engine endpoint and the owner's sign-in
name from it.
"""

import json
import os
from pathlib import Path
import re
import stat
from uuid import UUID

from hyprn_mvp_app.locations import location_refusal, normalized

SCHEMA = 'hyprn_mvp.installation/1'
EDITIONS = ('local',)
# Editions of the product; a configuration of another product edition is an edition mismatch.
PRODUCT_EDITIONS = ('local', 'cloud')
RELEASE_MODES = ('checkout', 'frozen')
MAX_BYTES = 65536
PORTS = (1024, 65535)
TOKEN_TTL_HOURS = (1, 168)
LOOPBACK = 'http://127.0.0.1:'
FIELDS = (
    'schema',
    'edition',
    'installation_id',
    'owner_username',
    'host_home',
    'data_root',
    'ports',
    'origin',
    'docker',
    'release',
    'agent',
    'upstream',
)
OBJECTS = {
    'ports': ('app',),
    'docker': ('endpoint', 'engine'),
    'release': ('mode', 'require_review', 'immutable'),
    'agent': ('enabled', 'token_ttl_hours'),
    'upstream': ('cache',),
}
USERNAME = re.compile(r'[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}')
ENGINE = re.compile(r'[A-Za-z0-9][A-Za-z0-9 ._:()+/-]{0,127}')
UNIX = 'unix://'


class InstallationError(ValueError):
    """A refused installation configuration. ``reason_code`` is one of
    ``configuration_unsafe``, ``configuration_invalid``, ``edition_mismatch`` and
    ``location_refused``."""

    def __init__(self, message, reason_code='configuration_invalid'):
        super().__init__(message)
        self.reason_code = reason_code


def _unique(pairs):
    document = {}
    for key, value in pairs:
        if key in document:
            raise InstallationError(
                'duplicate key ' + json.dumps(key) + ' in the installation configuration'
            )
        document[key] = value
    return document


def _constant(name):
    raise InstallationError('non-finite number ' + name + ' in the installation configuration')


def parse(raw):
    """The JSON object of ``raw`` (bytes); duplicate keys and non-finite numbers refused."""
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        raise InstallationError('the installation configuration is not UTF-8') from None
    try:
        document = json.loads(text, object_pairs_hook=_unique, parse_constant=_constant)
    except json.JSONDecodeError as error:
        raise InstallationError(
            'the installation configuration is not JSON: ' + error.msg
        ) from None
    if not isinstance(document, dict):
        raise InstallationError('the installation configuration is not a JSON object')
    return document


def _closed(value, fields, where):
    if not isinstance(value, dict):
        raise InstallationError(where + ' must be an object')
    unknown, missing = sorted(set(value) - set(fields)), [f for f in fields if f not in value]
    if unknown:
        raise InstallationError('unknown field ' + ', '.join(where + '.' + f for f in unknown))
    if missing:
        raise InstallationError('missing field ' + ', '.join(where + '.' + f for f in missing))


def _string(value, where, pattern=None):
    if not isinstance(value, str) or (pattern is not None and not pattern.fullmatch(value)):
        raise InstallationError(where + ' is invalid')
    return value


def _boolean(value, where):
    if not isinstance(value, bool):
        raise InstallationError(where + ' must be true or false')
    return value


def _integer(value, where, bounds):
    if isinstance(value, bool) or not isinstance(value, int) or not bounds[0] <= value <= bounds[1]:
        raise InstallationError(
            where + ' must be an integer from ' + str(bounds[0]) + ' to ' + str(bounds[1])
        )
    return value


def _path(value, where):
    path = normalized(value) if isinstance(value, str) else None
    if path is None or len(path.parts) < 2:
        raise InstallationError(where + ' must be an absolute normalized path below /')
    return path


def _admitted(path, where, host):
    reason = location_refusal(path, host)
    if reason is not None:
        raise InstallationError(
            'refusing ' + where + ' ' + str(path) + ': ' + reason, 'location_refused'
        )
    return path


def validate(document, *, edition, host=None):
    """The validated configuration (a new dict); ``host`` injects the location rule's host."""
    if edition not in EDITIONS:
        raise ValueError('Unknown edition: ' + str(edition))
    _closed(
        document,
        FIELDS
        + (('studies_root',) if isinstance(document, dict) and 'studies_root' in document else ()),
        'configuration',
    )
    for name, fields in OBJECTS.items():
        _closed(document[name], fields, name)
    if document['schema'] != SCHEMA:
        raise InstallationError('schema must be ' + SCHEMA)
    if document['edition'] != edition:
        if document['edition'] in PRODUCT_EDITIONS:
            raise InstallationError(
                'this configuration belongs to the '
                + document['edition']
                + ' edition, not the '
                + edition
                + ' edition',
                'edition_mismatch',
            )
        raise InstallationError('edition is invalid')
    identity = _string(document['installation_id'], 'installation_id')
    try:
        canonical = UUID(identity)
    except ValueError:
        canonical = None
    if canonical is None or canonical.version != 4 or str(canonical) != identity:
        raise InstallationError('installation_id must be a canonical version 4 UUID')
    _string(document['owner_username'], 'owner_username', USERNAME)
    home = _path(document['host_home'], 'host_home')
    data_root = _path(document['data_root'], 'data_root')
    if data_root == home or home.is_relative_to(data_root):
        raise InstallationError('data_root may not be the home folder or one of its parents')
    port = _integer(document['ports']['app'], 'ports.app', PORTS)
    if _string(document['origin'], 'origin') != LOOPBACK + str(port):
        raise InstallationError('origin must be ' + LOOPBACK + str(port))
    endpoint = _string(document['docker']['endpoint'], 'docker.endpoint')
    if not endpoint.startswith(UNIX):
        raise InstallationError('docker.endpoint must be a unix:// socket')
    _path(endpoint.removeprefix(UNIX), 'docker.endpoint')
    _string(document['docker']['engine'], 'docker.engine', ENGINE)
    if document['release']['mode'] not in RELEASE_MODES:
        raise InstallationError('release.mode must be checkout or frozen')
    _boolean(document['release']['require_review'], 'release.require_review')
    _boolean(document['release']['immutable'], 'release.immutable')
    _boolean(document['agent']['enabled'], 'agent.enabled')
    _integer(document['agent']['token_ttl_hours'], 'agent.token_ttl_hours', TOKEN_TTL_HOURS)
    if 'studies_root' in document:
        studies = _admitted(
            _path(document['studies_root'], 'studies_root'), 'the studies root', host
        )
        if studies.is_relative_to(Path(__file__).resolve().parents[3]):
            raise InstallationError('the studies root is inside the checkout', 'location_refused')
    cache = _path(document['upstream']['cache'], 'upstream.cache')
    if cache == data_root or not cache.is_relative_to(data_root):
        raise InstallationError('upstream.cache must be inside data_root')
    _admitted(data_root, 'the data root', host)
    _admitted(cache, 'the upstream cache', host)
    if os.path.lexists(data_root):
        status = os.lstat(data_root)
        if (
            not stat.S_ISDIR(status.st_mode)
            or status.st_uid != os.getuid()
            or status.st_mode & 0o077
        ):
            raise InstallationError(
                'refusing the data root ' + str(data_root) + ': it is not a folder owned by this '
                'user and closed to group and others',
                'location_refused',
            )
    return json.loads(json.dumps(document))


def _unsafe(message):
    return InstallationError(message, 'configuration_unsafe')


def read(path):
    """The bytes of the configuration file at ``path`` after the file-safety checks."""
    location = normalized(path)
    if location is None:
        raise _unsafe('the installation configuration path must be absolute and normalized')
    for part in (location, *location.parents):
        if part.is_symlink():
            raise _unsafe('the installation configuration path has a symbolic link at ' + str(part))
    folder = os.lstat(location.parent)
    if not stat.S_ISDIR(folder.st_mode) or folder.st_uid != os.getuid() or folder.st_mode & 0o077:
        raise _unsafe(
            'the folder of the installation configuration must be owned by this user and closed to '
            'group and others (0700)'
        )
    try:
        descriptor = os.open(location, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, 'O_CLOEXEC', 0))
    except FileNotFoundError:
        raise InstallationError('no installation configuration at ' + str(location)) from None
    except OSError as error:
        raise _unsafe(
            'the installation configuration cannot be opened safely: ' + error.strerror
        ) from None
    status = os.fstat(descriptor)
    if not stat.S_ISREG(status.st_mode):
        os.close(descriptor)
        raise _unsafe('the installation configuration must be a regular file with one link')
    with os.fdopen(descriptor, 'rb') as stream:
        if status.st_nlink != 1:
            raise _unsafe('the installation configuration must be a regular file with one link')
        if status.st_uid != os.getuid():
            raise _unsafe('the installation configuration is owned by another user')
        if status.st_mode & 0o077:
            raise _unsafe(
                'the installation configuration must be readable only by its owner (0600)'
            )
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise InstallationError(
            'the installation configuration exceeds ' + str(MAX_BYTES) + ' bytes'
        )
    return raw


def load(path, *, edition, host=None):
    """Read, parse and validate the installation configuration at the explicit ``path``."""
    return validate(parse(read(path)), edition=edition, host=host)


# ---- Execution identities. One definition for the launcher, the worker builder and the
# native environment manager; the development data root (``HYPRN_MVP_DATA_ROOT``, no
# configuration) keeps its own fixed identities.
CONFIG = 'HYPRN_MVP_CONFIG'
DEVELOPMENT_OWNER = 'hyprn-mvp-execution'
DEVELOPMENT_PROFILE = 'hyprn-mvp'


def from_environment(environ=None, *, edition='local'):
    """The configuration named by ``HYPRN_MVP_CONFIG``, loaded and validated; None when unset."""
    environ = os.environ if environ is None else environ
    value = environ.get(CONFIG, '')
    return load(value, edition=edition) if value else None


def owner(configuration):
    """Owner label of the execution runtime and its worker containers."""
    if configuration is None:
        return DEVELOPMENT_OWNER
    return 'hyprn-mvp-' + configuration['edition'] + '-' + configuration['installation_id']


def profile_name(configuration):
    """Name of the native (AiiDA) profile of the execution store."""
    if configuration is None:
        return DEVELOPMENT_PROFILE
    return 'hyprn-mvp-' + configuration['edition'] + '-' + configuration['installation_id'][:8]


# ---- Component identities of the modeling and application managers.
# Docker names of an installation start with one of these prefixes; test scopes use
# ``hyprn-mvp-test-`` and the development data root its fixed names below.
NAME_PREFIXES = tuple('hyprn-mvp-' + edition + '-' for edition in PRODUCT_EDITIONS)
DEVELOPMENT_NAMES = {
    'project': 'hyprn-mvp',
    'modeling': 'hyprn-mvp-modeling',
    'private_network': 'hyprn-mvp-private',
    'modeling_owner': 'hyprn-mvp-modeling',
    'application': 'hyprn-mvp-application',
    'public_network': 'hyprn-mvp-public',
    'application_owner': 'hyprn-mvp-application',
}
DEVELOPMENT_USERNAME = 'owner'


def component_names(configuration):
    """Compose project, container and network names of the modeling and application
    components, and the value of their ownership label: ``hyprn-mvp-<edition>-<id8>-<role>``,
    every resource labelled with ``owner(configuration)``, so two installations on one engine
    never share a name and each resource names the installation that owns it."""
    if configuration is None:
        return dict(DEVELOPMENT_NAMES)
    base = 'hyprn-mvp-' + configuration['edition'] + '-' + configuration['installation_id'][:8]
    label = owner(configuration)
    return {
        'project': base,
        'modeling': base + '-modeling',
        'private_network': base + '-private',
        'modeling_owner': label,
        'application': base + '-application',
        'public_network': base + '-public',
        'application_owner': label,
    }


def owner_username(configuration):
    """Sign-in name provisioned for the owner when the application store is initialized."""
    return DEVELOPMENT_USERNAME if configuration is None else configuration['owner_username']


def docker_environment(configuration, environ=None):
    """Process environment of a docker command: ``environ`` with ``DOCKER_HOST`` set to the
    installation's engine endpoint; None (inherit) for the development data root."""
    if configuration is None:
        return None
    environ = os.environ if environ is None else environ
    return {**environ, 'DOCKER_HOST': configuration['docker']['endpoint']}
