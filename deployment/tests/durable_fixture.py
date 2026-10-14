"""Reviewed resolver and capture tool for the durable retained native fixture. Stdlib only;
never imports AiiDA.

The durable fixture holds recorded source/downstream runs that the Findings continuation and
the approach history browser cases reuse instead of regenerating them. Disposable scoped
folders are never retained as fixtures: a fixture lives below the durable fixture root
(``HYPRN_MVP_TEST_FIXTURES_ROOT``, default ``<data root>/fixtures``; deployment/local_paths.py).

The pinned fixture (NATIVE_FIXTURE, kind ``retained-native-scope``) is the full scope of one
fully passing units-native producer run (AiiDA profile and repository, private modeling stores,
keys, attestation, application store) plus its reuse manifest and the exact recorded outbox
payloads. Its manifest is verified against the pinned SHA256 before any identity or file is
used. Every file read through this module is checked for exact size and SHA256, and the folder
may hold no unlisted entry (a SQLite sidecar or a stray write fails closed). Absence or any
mismatch raises FixtureUnavailable with the reason; there is no fallback location.

native_scope() materializes the fixture into its guard-convention working root
(<scratch root>/hyprn-mvp-test-<run_uuid>, the same absolute root the producer used, so AiiDA's
absolute storage paths stay exact). Every byte is SHA256-checked while copied, original modes
are restored, and a marker binds the working root to the pinned manifest. An existing root is
reused only with that exact marker; anything else fails closed. The working root is a
disposable, re-materializable copy: the durable fixture is never opened writable.

capture() writes a new fixture folder from a finished, fully passing units-native producer
scope and never modifies an existing fixture:

    python3 -B deployment/tests/durable_fixture.py capture --scope <producer scope root>

Capture and every later use must resolve the same scratch root (HYPRN_MVP_SCRATCH_ROOT, outside
the operating system's temporary folder), because the fixture records its working root.
"""
from pathlib import Path
import hashlib
import json
import os
import secrets
import stat

import scoped_fixture as guard

# Durable fixture root (deployment/local_paths.py). While it is unconfigured the fixture is
# unavailable (FixtureUnavailable names the variable).
FIXTURES_ROOT = guard.local_paths.fixtures_root(required=False)
NATIVE_FIXTURE = None if FIXTURES_ROOT is None else FIXTURES_ROOT / 'native-20261014T003835Z'
NATIVE_MANIFEST_SHA256 = 'b987220af0e634d910484e4bc840083028fb3a5314bd1468de141c5b4d606718'
IDENTITY_FIELDS = frozenset({
    'run_uuid', 'profile_uuid', 'store_uuid', 'study_id', 'source_run', 'source_process',
    'source_configuration', 'source_revision', 'source_payload', 'source_results_digest',
    'violated_criterion', 'downstream_run', 'downstream_revision', 'downstream_payload', 'reuse_sha256'})
NATIVE_KIND = 'retained-native-scope'
KINDS = frozenset({NATIVE_KIND})
SCOPE_PREFIX = 'scope'
MATERIALIZATION = 'fixture-materialization.json'
# The producer: one fully passing units-native compound journey (seven recorded runs). Its first
# family's downstream run reads the source run's specific energy (MJ/kg) as a run-result input.
PRODUCER_GROUP = 'units-native'
PRODUCER_TEST = 'deployment/tests/test_units_native.py::test_native_compounds_histories_and_archive'
DOWNSTREAM_CONFIGURATION = 'Retained specific_energy'
RETAINED_RUNS = 7
# The stores the continuation reads immutably; a nonempty journal or WAL beside one means the
# producer was not quiescent when captured.
STORES = ('artifacts/combined.sqlite', 'native/database.sqlite', 'artifacts/private-http/modeling/model.sqlite3',
          'artifacts/private-http/modeling/scratch.sqlite3')
SIDECARS = frozenset(store + suffix for store in STORES for suffix in ('-wal', '-journal'))


class FixtureUnavailable(ValueError):
    """The durable fixture is absent, unpinned, changed or lacks the requested part."""


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _private(path, *, directory):
    """Owner-only, never group/other accessible; files must also be read-only."""
    info = path.lstat()
    if info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise FixtureUnavailable('Durable fixture permissions are not owner-private: ' + str(path))
    if directory != stat.S_ISDIR(info.st_mode) or (not directory and not stat.S_ISREG(info.st_mode)):
        raise FixtureUnavailable('Unexpected durable fixture entry type: ' + str(path))
    if not directory and info.st_mode & 0o222:
        raise FixtureUnavailable('Durable fixture file is writable: ' + str(path))


def _scope_spec(record):
    """Closed native_scope description: working root, prefix and every entry's original mode."""
    spec = record.get('native_scope')
    run_uuid = record['identities']['run_uuid']
    if (not isinstance(spec, dict) or set(spec) != {'root', 'prefix', 'modes'} or spec['prefix'] != SCOPE_PREFIX
            or not isinstance(spec['modes'], dict) or spec['modes'].get('.') is None
            or any(type(mode) is not int or not 0 <= mode <= 0o777 for mode in spec['modes'].values())):
        raise FixtureUnavailable('Native fixture scope description is malformed')
    if spec['root'] != str(scope_root(run_uuid)):
        raise FixtureUnavailable('Native fixture working root is not below the configured scratch root; use the '
                                 'scratch root it was captured under (' + guard.local_paths.SCRATCH_ROOT + ')')
    files = {name[len(SCOPE_PREFIX) + 1:] for name in record['files'] if name.startswith(SCOPE_PREFIX + '/')}
    if not files or not files <= set(spec['modes']) or MATERIALIZATION in files:
        raise FixtureUnavailable('Native fixture scope inventory is malformed')
    for relative in spec['modes']:
        parts = Path(relative).parts
        if relative != '.' and (Path(relative).is_absolute() or '..' in parts or not parts):
            raise FixtureUnavailable('Native fixture scope path escape: ' + relative)
    return spec


def manifest(fixture=None, expected=None):
    """Verify the pinned manifest bytes and closed inventory; return the decoded manifest."""
    fixture = NATIVE_FIXTURE if fixture is None else fixture
    expected = NATIVE_MANIFEST_SHA256 if expected is None else expected
    if fixture is None:
        raise FixtureUnavailable(guard.local_paths.unset_message(guard.local_paths.TEST_FIXTURES_ROOT))
    try:
        fixture = guard.no_symlinks(fixture)
        if not fixture.is_dir():
            raise FixtureUnavailable('Durable fixture is absent: ' + str(fixture))
        _private(fixture, directory=True)
        path = guard.no_symlinks(fixture / 'manifest.json')
        if not path.is_file():
            raise FixtureUnavailable('Durable fixture manifest is absent: ' + str(path))
        _private(path, directory=False)
        raw = path.read_bytes()
    except OSError as error:
        raise FixtureUnavailable('Durable fixture is unreadable: ' + str(error)) from error
    if _sha(raw) != expected:
        raise FixtureUnavailable('Durable fixture manifest SHA256 mismatch: ' + str(path))
    record = json.loads(raw)
    if (record.get('schema_version') != '1' or record.get('kind') not in KINDS
            or record.get('name') != fixture.name or set(record.get('identities', {})) != IDENTITY_FIELDS
            or not isinstance(record.get('files'), dict) or not record['files']):
        raise FixtureUnavailable('Durable fixture manifest is malformed: ' + str(path))
    spec = _scope_spec(record)
    listed = {'manifest.json', *record['files']}
    listed.update(SCOPE_PREFIX if relative == '.' else SCOPE_PREFIX + '/' + relative for relative in spec['modes'])
    for relative in list(listed):
        parts = Path(relative).parts
        listed.update(str(Path(*parts[:index])) for index in range(1, len(parts)))
    actual = set()
    for entry in sorted(fixture.rglob('*')):
        relative = str(entry.relative_to(fixture))
        if entry.is_symlink() or relative not in listed:
            raise FixtureUnavailable('Unlisted durable fixture entry: ' + relative)
        _private(entry, directory=entry.is_dir())
        actual.add(relative)
    if actual != listed:
        raise FixtureUnavailable('Durable fixture inventory differs from its manifest')
    return record


def identities():
    return dict(manifest()['identities'])


def verified_file(relative):
    """Exact-size/SHA256 verified path of one manifest-listed file."""
    record = manifest()
    item = record['files'].get(relative)
    if item is None:
        raise FixtureUnavailable('Durable fixture does not contain ' + relative)
    path = guard.no_symlinks(NATIVE_FIXTURE / relative)
    raw = path.read_bytes()
    if len(raw) != item['size'] or _sha(raw) != item['sha256']:
        raise FixtureUnavailable('Durable fixture file changed: ' + relative)
    return path


def application_store():
    """Read-only retained application store; callers open it immutably and copy privately."""
    return verified_file(SCOPE_PREFIX + '/artifacts/combined.sqlite')


def reuse_manifest():
    path = verified_file('reuse/fixture-reuse.json')
    if _sha(path.read_bytes()) != manifest()['identities']['reuse_sha256']:
        raise FixtureUnavailable('Durable reuse manifest differs from its pinned identity')
    return path


def retained_payload(run_id):
    return verified_file('reuse/retained/' + run_id + '.json')


def native_scope_available(fixture=None, expected=None):
    """Manifest of the pinned native fixture, verified without materializing it."""
    return manifest(fixture, expected)


def _release(path):
    """Remove one incomplete staging tree created by this process (modes may be read-only)."""
    for entry in sorted(path.rglob('*'), key=lambda p: len(p.parts), reverse=True):
        if entry.is_dir() and not entry.is_symlink():
            entry.chmod(0o700)
            entry.rmdir()
        else:
            entry.parent.chmod(0o700)
            entry.unlink()
    path.chmod(0o700)
    path.rmdir()


def native_scope(fixture=None, expected=None):
    """Working root of the pinned native fixture, materialized once from verified bytes."""
    fixture = NATIVE_FIXTURE if fixture is None else fixture
    expected = NATIVE_MANIFEST_SHA256 if expected is None else expected
    record = native_scope_available(fixture, expected)
    spec = record['native_scope']
    root = scope_root(record['identities']['run_uuid'])
    binding = dict(fixture=record['name'], manifest_sha256=expected)
    if os.path.lexists(root):
        marker = guard.no_symlinks(root / MATERIALIZATION)
        try:
            bound = json.loads(marker.read_bytes()) if marker.is_file() else None
        except (OSError, ValueError):
            bound = None
        if bound != binding:
            raise FixtureUnavailable('Existing native working root is not a materialization of the pinned '
                                       'fixture; refusing to adopt it: ' + str(root))
        return root
    staging = root.with_name(root.name + '.materializing-' + secrets.token_hex(8))
    os.mkdir(staging, 0o700)
    try:
        modes = spec['modes']
        directories = sorted((r for r in modes if r != '.' and SCOPE_PREFIX + '/' + r not in record['files']),
                             key=lambda r: len(Path(r).parts))
        for relative in directories:
            os.mkdir(staging / relative, 0o700)
        for name, item in sorted(record['files'].items()):
            if not name.startswith(SCOPE_PREFIX + '/'):
                continue
            relative = name[len(SCOPE_PREFIX) + 1:]
            source = guard.no_symlinks(fixture / name)
            descriptor = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(descriptor, 'rb') as stream:
                raw = stream.read()
            if len(raw) != item['size'] or _sha(raw) != item['sha256']:
                raise FixtureUnavailable('Durable native fixture file changed: ' + name)
            target = staging / relative
            descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(raw)
            os.chmod(target, modes[relative])
        marker = staging / MATERIALIZATION
        descriptor = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(json.dumps(binding, sort_keys=True).encode())
        os.chmod(marker, 0o400)
        for relative in reversed(directories):
            os.chmod(staging / relative, modes[relative])
        os.chmod(staging, modes['.'])
        os.rename(staging, root)
    except BaseException:
        if os.path.lexists(staging):
            _release(staging)
        raise
    return root


def scope_root(run_uuid):
    """Guard-convention working root of a native scope (below the scratch root)."""
    return guard.root_path(guard.SCRATCH_ROOT / (guard.SCOPE_PREFIX + run_uuid))


def _json(path):
    try:
        return json.loads(guard.no_symlinks(path).read_bytes())
    except (OSError, ValueError) as error:
        raise FixtureUnavailable('Producer evidence is unreadable: ' + path.name) from error


def _producer(root):
    """The producer scope, its passing group result and its quiescent state."""
    import subprocess
    root = guard.root_path(Path(root))
    scope = guard.Scope(**{**_json(root / 'scope.json'), 'root': root})
    guard.validate_scope(scope)
    result, tests, proof = (_json(root / 'evidence' / name) for name in ('result.json', 'tests.json', 'units-native-proof.json'))
    if (result.get('group') != PRODUCER_GROUP or result.get('exit') != 0 or result.get('scope') != scope.record()
            or tests.get('passed') is not True or tests.get('failures') or tests.get('skipped')
            or proof.get('passed') is not True):
        raise FixtureUnavailable('Capture requires a finished, fully passing ' + PRODUCER_GROUP + ' producer scope')
    containers = subprocess.run(['docker', 'ps', '-aq', '--filter', 'label=org.hyprn-mvp.test-scope=' + scope.run_uuid],
                                capture_output=True, text=True, env={'PATH': guard.PATH}, timeout=60)
    if containers.returncode or containers.stdout.strip():
        raise FixtureUnavailable('Producer scope still has containers or their state is unknown')
    return scope, result, tests, proof


def _inventory(root):
    """Every entry of the producer scope with its mode; only directories and regular files."""
    modes, files = {'.': stat.S_IMODE(root.lstat().st_mode)}, []
    for directory, names, entries in os.walk(root):
        for name in sorted(names + entries):
            path = Path(directory) / name
            info = path.lstat()
            relative = str(path.relative_to(root))
            if stat.S_ISREG(info.st_mode):
                files.append(relative)
            elif not stat.S_ISDIR(info.st_mode):
                raise FixtureUnavailable('Producer scope holds a link or special file: ' + relative)
            if relative == MATERIALIZATION or (relative in SIDECARS and info.st_size):
                raise FixtureUnavailable('Producer scope is not quiescent: ' + relative)
            modes[relative] = stat.S_IMODE(info.st_mode)
    if not set(STORES) <= set(files):
        raise FixtureUnavailable('Producer scope lacks a retained store')
    return modes, sorted(files)


def _records(scope):
    """Seven recorded runs, their exact outbox bytes and the specific-energy source/downstream pair."""
    import sqlite3
    store = guard.no_symlinks(scope.root / 'artifacts/combined.sqlite')
    connection = sqlite3.connect(store.as_uri() + '?mode=ro&immutable=1', uri=True)
    try:
        outbox = connection.execute('SELECT run_id,state,payload FROM outbox ORDER BY run_id').fetchall()
        associations = {row[0]: row[1:] for row in connection.execute(
            'SELECT run_id,study_id,store_uuid,process_uuid FROM run_associations')}
    finally:
        connection.close()
    if len(outbox) != RETAINED_RUNS or any(state != 'recorded' for _, state, _ in outbox):
        raise FixtureUnavailable('Producer store must hold exactly seven recorded runs')
    records, payloads, values = [], {}, {}
    for run_id, state, payload in outbox:
        value = json.loads(payload)
        configuration = value['frozen']['configuration']
        study_id, store_uuid, process_uuid = associations[run_id]
        if (store_uuid != scope.store_uuid or process_uuid != value['history']['association']['process_uuid']
                or configuration['configuration_revision_id'] is None):
            raise FixtureUnavailable('Producer run association differs from its scope: ' + run_id)
        payloads[run_id], values[run_id] = payload.encode(), value
        records.append(dict(run_id=run_id, state=state, process_uuid=process_uuid,
            configuration_revision_id=configuration['configuration_revision_id'],
            model_revision_id=configuration['model_revision_id'],
            payload_path='reuse/retained/' + run_id + '.json', payload_sha256=_sha(payloads[run_id]),
            results=value['history']['results']))
    studies = {associations[run_id][0] for run_id in payloads}
    downstream = [r for r, v in values.items() if v['frozen']['configuration']['name'] == DOWNSTREAM_CONFIGURATION]
    if len(studies) != 1 or len(downstream) != 1:
        raise FixtureUnavailable('Producer store lacks one study with one retained specific-energy run')
    bindings = [i['result_binding'] for i in values[downstream[0]]['frozen']['configuration']['inputs'] if i['result_binding']]
    if len(bindings) != 1 or bindings[0]['source_run_id'] not in values:
        raise FixtureUnavailable('Retained specific-energy run must read exactly one recorded source result')
    source = bindings[0]['source_run_id']
    violated = [c['criterion_id'] for c in values[source]['history']['results']['criteria'] if c['outcome'] == 'violated']
    if len(violated) != 1:
        raise FixtureUnavailable('Specific-energy source run must carry exactly one violated criterion')
    by_id = {r['run_id']: r for r in records}
    pair = dict(study_id=studies.pop(), source_run=source, source_process=by_id[source]['process_uuid'],
        source_configuration=by_id[source]['configuration_revision_id'], source_revision=by_id[source]['model_revision_id'],
        source_payload=by_id[source]['payload_sha256'], source_results_digest=bindings[0]['results_digest'],
        violated_criterion=violated[0], downstream_run=downstream[0],
        downstream_revision=by_id[downstream[0]]['model_revision_id'], downstream_payload=by_id[downstream[0]]['payload_sha256'])
    return records, payloads, pair


def _write(path, raw):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(raw)
    os.chmod(path, 0o400)
    return dict(size=len(raw), sha256=_sha(raw))


def capture(producer, fixtures_root=None, *, created_utc=None):
    """Write a new durable fixture folder from one finished producer scope; return (folder, manifest SHA256)."""
    import time
    fixtures_root = FIXTURES_ROOT if fixtures_root is None else fixtures_root
    if fixtures_root is None:
        raise FixtureUnavailable(guard.local_paths.unset_message(guard.local_paths.TEST_FIXTURES_ROOT))
    fixtures_root = guard.no_symlinks(Path(fixtures_root))
    scope, result, tests, proof = _producer(producer)
    modes, scope_files = _inventory(scope.root)
    records, payloads, pair = _records(scope)
    created_utc = created_utc or time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
    name = 'native-' + created_utc
    if os.path.lexists(fixtures_root / name):
        raise FixtureUnavailable('Durable fixture folder already exists: ' + name)
    staging = fixtures_root / ('.' + name + '.capturing-' + secrets.token_hex(8))
    os.mkdir(staging, 0o700)
    try:
        files = {}
        for relative, mode in sorted(modes.items(), key=lambda item: len(Path(item[0]).parts)):
            if relative != '.' and relative not in scope_files:
                os.mkdir(staging / SCOPE_PREFIX / relative, 0o700)
            elif relative == '.':
                os.mkdir(staging / SCOPE_PREFIX, 0o700)
        for relative in scope_files:
            raw = guard.no_symlinks(scope.root / relative).read_bytes()
            files[SCOPE_PREFIX + '/' + relative] = _write(staging / SCOPE_PREFIX / relative, raw)
        os.mkdir(staging / 'reuse', 0o700)
        os.mkdir(staging / 'reuse/retained', 0o700)
        for run_id, raw in sorted(payloads.items()):
            files['reuse/retained/' + run_id + '.json'] = _write(staging / 'reuse/retained' / (run_id + '.json'), raw)
        reuse = dict(scope=str(scope.root), study_id=pair['study_id'], source_run_id=pair['source_run'],
                     downstream_run_id=pair['downstream_run'], status='captured-producer-scope',
                     human_acceptance='pending', records=records)
        reuse_raw = json.dumps(reuse, indent=2, sort_keys=True).encode() + b'\n'
        files['reuse/fixture-reuse.json'] = _write(staging / 'reuse/fixture-reuse.json', reuse_raw)
        pins = json.loads((Path(__file__).resolve().parents[2] / 'deployment/pins.json').read_bytes())
        record = dict(schema_version='1', kind=NATIVE_KIND, name=name, created_utc=created_utc,
            identities=dict(pair, run_uuid=scope.run_uuid, profile_uuid=scope.profile_uuid, store_uuid=scope.store_uuid,
                            reuse_sha256=files['reuse/fixture-reuse.json']['sha256']),
            native_scope=dict(root=str(scope_root(scope.run_uuid)), prefix=SCOPE_PREFIX, modes=modes),
            files=files,
            provenance=dict(producer_group=PRODUCER_GROUP, producer_test=PRODUCER_TEST, exit=result['exit'],
                tests=dict(tests=tests.get('tests'), failures=tests.get('failures'), skipped=tests.get('skipped')),
                duration_seconds=round(result['duration_seconds']), producer_sources=result['source_sha256'],
                modeling_producer_image=pins['modeling_producer']['image'],
                attested_worker_image=proof['attestation']['fingerprint']['image'],
                human_acceptance='pending'))
        raw = json.dumps(record, indent=1, sort_keys=True).encode() + b'\n'
        _write(staging / 'manifest.json', raw)
        os.rename(staging, fixtures_root / name)
    except BaseException:
        if os.path.lexists(staging):
            _release(staging)
        raise
    digest = _sha(raw)
    manifest(fixtures_root / name, digest)
    return fixtures_root / name, digest


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description='Durable native fixture tool.')
    commands = parser.add_subparsers(dest='command', required=True)
    command = commands.add_parser('capture', help='capture a finished, fully passing units-native producer scope')
    command.add_argument('--scope', required=True, type=Path, help='producer scope root below the scratch root')
    args = parser.parse_args(argv)
    folder, digest = capture(args.scope)
    print(json.dumps(dict(fixture=folder.name, manifest_sha256=digest)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
