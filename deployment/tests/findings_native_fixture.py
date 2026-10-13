"""One-shot continuation of the retained native fixture. Importing this module is stdlib-only.

findings-native-preflight records an authenticated baseline of the materialized working root,
findings-native adds exactly one new downstream run pinned to the retained source run and a new
approach version, and findings-native-read re-reads the recorded result without any write. The
journal admits each stage once; an uncertain launch is reconciled by lookup, never re-dispatched.
"""
from contextlib import closing, contextmanager
from dataclasses import dataclass
import fcntl
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import shutil
import sqlite3
import subprocess
import sys
from uuid import UUID

import durable_fixture
import scoped_fixture as guard

REPO = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class _Original:
    """Retained identities, read from the manifest-verified durable native fixture (durable_fixture).

    A regenerated fixture carries its own incidental identities; behavioural assertions do not
    depend on them. The working native root
    follows the guard scope convention for run_uuid and is materialized from the durable
    fixture by retained_scope(); it is never a literal /private/tmp path. available is
    False (with the reason) when the durable fixture is absent, changed, or has no native
    scope: entry points then fail closed.
    """
    root: Path
    run_uuid: str
    profile_uuid: str
    store_uuid: str
    study_id: str
    source_run: str
    source_process: str
    source_configuration: str
    source_revision: str
    source_payload: str
    source_results_digest: str
    violated_criterion: str
    downstream_run: str
    downstream_revision: str
    downstream_payload: str
    reuse: Path
    reuse_sha256: str
    available: bool
    unavailable: str


def _original():
    try:
        identity = durable_fixture.identities()
    except durable_fixture.FixtureUnavailable as error:
        empty = {name: '' for name in durable_fixture.IDENTITY_FIELDS}
        return _Original(**empty, root=durable_fixture.NATIVE_FIXTURE / 'unavailable',
                         reuse=durable_fixture.NATIVE_FIXTURE / 'unavailable', available=False, unavailable=str(error))
    try:
        durable_fixture.native_scope_available()  # Manifest only; materialization happens in retained_scope().
        available, reason = True, ''
    except durable_fixture.FixtureUnavailable as error:
        available, reason = False, str(error)
    return _Original(**identity, root=durable_fixture.scope_root(identity['run_uuid']),
                     reuse=durable_fixture.NATIVE_FIXTURE / 'reuse/fixture-reuse.json', available=available, unavailable=reason)


def require_original():
    """Fail closed with the durable-fixture reason before any retained-scope use."""
    if not ORIGINAL.available:
        raise durable_fixture.FixtureUnavailable(ORIGINAL.unavailable)


ORIGINAL = _original()
CONTINUATION = ORIGINAL.root / 'artifacts/findings-native-continuation'
_READ_ONLY = False


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def validate_identity(scope):
    require_original()
    expected = guard.Scope(ORIGINAL.root, ORIGINAL.run_uuid,
        guard.SCOPE_PREFIX + ORIGINAL.run_uuid, ORIGINAL.profile_uuid, ORIGINAL.store_uuid)
    if scope != expected:
        raise ValueError('Retained fixture identity required')
    return guard.validate_scope(scope)


def retained_scope():
    require_original()
    # Materialize (or adopt only the exactly bound) working root from verified durable bytes.
    if durable_fixture.native_scope() != ORIGINAL.root:
        raise ValueError('Native working root differs from its identity')
    return validate_identity(guard.Scope(ORIGINAL.root, ORIGINAL.run_uuid,
        guard.SCOPE_PREFIX + ORIGINAL.run_uuid, ORIGINAL.profile_uuid, ORIGINAL.store_uuid))


def validate_child():
    scope = guard.scope_from_environment()
    validate_identity(scope)
    if sys.executable != guard.APPROVED_PYTHON:
        raise ValueError('Native child must use the reviewed interpreter')
    return scope


def require_write(operation):
    if _READ_ONLY:
        raise ValueError('Findings read-only mode refuses ' + operation)


@contextmanager
def read_only_veto():
    global _READ_ONLY
    previous = _READ_ONLY
    _READ_ONLY = True
    import builtins
    original_import = builtins.__import__
    patched = []
    boundaries = (
        ('hyprn_mvp_integration.calculation', 'NativeExecution', 'launch'),
        ('hyprn_mvp_app.execution', 'Submissions', 'submit'),
        ('hyprn_mvp_app.execution', 'Submissions', 'dispatch'),
        ('hyprn_mvp_app.execution', 'StaticPreparation', '__call__'),
        ('execution_runtime', None, 'build_worker'),
        ('scoped_fixture', None, 'create_native_fixture'),
        ('scoped_fixture', None, 'prepare_worker_fixture'),
        ('combined_fixture', 'Journey', 'dispatch'),
        ('units_native_fixture', 'UnitsJourney', 'start'),
        ('aiida.orm', 'Node', 'store'),
        ('aiida.orm', 'Node', 'store_all'),
        ('aiida.engine', None, 'submit'),
        ('aiida.engine', None, 'run'),
        ('aiida.engine', None, 'run_get_node'),
    )
    def deny(*args, **kwargs):
        raise ValueError('Findings read-only mode refuses scientific write')
    def install():
        for module_name, class_name, name in boundaries:
            owner = sys.modules.get(module_name)
            if class_name:
                owner = getattr(owner, class_name, None)
            if owner is not None and hasattr(owner, name) and getattr(owner, name) is not deny:
                patched.append((owner, name, getattr(owner, name)))
                setattr(owner, name, deny)
    def guarded_import(*args, **kwargs):
        result = original_import(*args, **kwargs)
        install()
        return result
    install()
    builtins.__import__ = guarded_import
    try:
        yield
    finally:
        builtins.__import__ = original_import
        for owner, name, original in reversed(patched):
            setattr(owner, name, original)
        _READ_ONLY = previous


@contextmanager
def readonly(path):
    guard.no_symlinks(path)
    if not path.is_file():
        raise ValueError('Required retained database missing')
    wal = guard.no_symlinks(path.with_name(path.name + '-wal'))
    if wal.exists() and wal.stat().st_size:
        raise ValueError('Nonempty WAL requires quiescent backup; immutable read refused')
    handles = subprocess.run(['/usr/sbin/lsof', '-Fpcfan', str(path)], capture_output=True, text=True, env={'PATH':guard.PATH})
    descriptors = [line for line in handles.stdout.splitlines() if line.startswith('f')]
    access = [line for line in handles.stdout.splitlines() if line.startswith('a')]
    if handles.returncode not in (0, 1) or handles.stderr or len(access) != len(descriptors) or any(line != 'ar' for line in access):
        holders = [line[1:] for line in handles.stdout.splitlines() if line.startswith('c')]
        raise ValueError('Database has writable or ambiguous open handles: ' + json.dumps(dict(
            exit=handles.returncode, diagnostics=bool(handles.stderr), access=access, descriptors=len(descriptors), holders=holders)))
    connection = sqlite3.connect(path.as_uri() + '?mode=ro&immutable=1', uri=True)
    connection.execute('PRAGMA query_only=ON')
    try: yield connection
    finally: connection.close()


def original_records():
    require_original()
    raw = durable_fixture.reuse_manifest().read_bytes()
    if sha(raw) != ORIGINAL.reuse_sha256:
        raise ValueError('Retained reuse manifest changed')
    record = json.loads(raw)
    records = record['records']
    if record['scope'] != str(ORIGINAL.root) or record['study_id'] != ORIGINAL.study_id or len(records) != 7:
        raise ValueError('Retained identities changed')
    for item in records:
        # Retained payload bytes live in the durable fixture (reuse/retained/<run_id>.json).
        path = durable_fixture.retained_payload(item['run_id'])
        if Path(item['payload_path']).name != item['run_id'] + '.json' or sha(path.read_bytes()) != item['payload_sha256']:
            raise ValueError('Retained payload changed')
    by_id = {item['run_id']: item for item in records}
    source = by_id[ORIGINAL.source_run]
    if (source['payload_sha256'] != ORIGINAL.source_payload or source['process_uuid'] != ORIGINAL.source_process
            or source['configuration_revision_id'] != ORIGINAL.source_configuration
            or source['model_revision_id'] != ORIGINAL.source_revision
            or by_id[ORIGINAL.downstream_run]['payload_sha256'] != ORIGINAL.downstream_payload
            or by_id[ORIGINAL.downstream_run]['model_revision_id'] != ORIGINAL.downstream_revision):
        raise ValueError('Original source/downstream changed')
    return records


def processes():
    with readonly(ORIGINAL.root/'native/database.sqlite') as connection:
        return {row[0] for row in connection.execute("SELECT uuid FROM db_dbnode WHERE node_type='process.calculation.calcjob.CalcJobNode.'")}


def validate_original_payloads(records):
    with readonly(ORIGINAL.root/'artifacts/combined.sqlite') as connection:
        for item in records:
            row = connection.execute('SELECT state,payload FROM outbox WHERE run_id=?', (item['run_id'],)).fetchone()
            if row is None or row[0] != 'recorded' or sha(row[1].encode()) != item['payload_sha256']:
                raise ValueError('Original outbox bytes/state changed')
            association = connection.execute('SELECT study_id,configuration_revision_id,store_uuid,process_uuid FROM run_associations WHERE run_id=?', (item['run_id'],)).fetchone()
            if association != (ORIGINAL.study_id, item['configuration_revision_id'], ORIGINAL.store_uuid, item['process_uuid']):
                raise ValueError('Original run association changed')


def admit_state(group, journal, actual, originals):
    if len(originals) != 7 or not originals <= actual or len(actual) not in (7, 8):
        raise ValueError('Unexpected native process identities/count')
    stage = 'initial' if journal is None else journal.get('stage')
    if stage not in {'initial', 'baselined', 'prepared', 'submitted', 'recorded'}:
        raise ValueError('Unrecognized continuation state')
    if len(actual) == 8:
        if stage not in {'submitted', 'recorded'}:
            raise ValueError('Additional process lacks authenticated journal')
        if stage == 'recorded' and actual-originals != {journal.get('process_uuid')}:
            raise ValueError('Recorded process identity mismatch')
        if stage == 'submitted' and group != 'findings-native-read':
            raise ValueError('Submitted process requires read-only reconciliation')
    elif stage in {'submitted', 'recorded'}:
        raise ValueError('Recorded/submitted process is missing; no redispatch')
    if group == 'findings-native-read' and (stage not in {'submitted', 'recorded'} or len(actual) != 8):
        raise ValueError('Read recovery requires one recorded or submitted process')
    if group == 'findings-native' and stage not in {'baselined', 'prepared'}:
        raise ValueError('Continuation cannot execute again')
    return stage


def reconcile(journal, records, additions):
    request = journal.get('request')
    if journal.get('stage') not in {'submitted', 'recorded'} or not isinstance(request, dict) or set(request) != {'run_id','scope','command_id','payload_digest','bundle_digest'}:
        raise ValueError('Pre-recorded exact request required')
    if len(records) != 1 or len(additions) != 1:
        raise ValueError('Absent or ambiguous native reconciliation')
    record = records[0]
    association = record.get('association', {})
    if (record.get('process_uuid') not in additions or record.get('request') != request
            or record.get('outbox_request') != request or record.get('outbox_state') != 'recorded'
            or association.get('run_id') != request['run_id'] or association.get('command_id') != request['command_id']
            or association.get('study_id') != request['scope'] or association.get('store_uuid') != ORIGINAL.store_uuid
            or association.get('process_uuid') != record['process_uuid']):
        raise ValueError('Native request/outbox/association reconciliation mismatch')
    return record['process_uuid']


def reconciliation_records(journal, additions):
    """Read the native request input link and authenticated local outbox bytes."""
    request = journal['request']
    records = []
    with readonly(ORIGINAL.root/'native/database.sqlite') as native, readonly(ORIGINAL.root/'artifacts/combined.sqlite') as app:
        app.row_factory = sqlite3.Row
        outbox = app.execute('SELECT state,payload FROM outbox WHERE run_id=?', (request['run_id'],)).fetchone()
        association = app.execute('SELECT * FROM run_associations WHERE run_id=?', (request['run_id'],)).fetchone()
        if outbox is None or association is None:
            return records
        for process in additions:
            links = native.execute("SELECT input.attributes FROM db_dbnode process JOIN db_dblink link ON link.output_id=process.id JOIN db_dbnode input ON input.id=link.input_id WHERE process.uuid=? AND link.label='request' AND link.type='input_calc' AND input.node_type='data.core.dict.Dict.'", (process,)).fetchall()
            for linked in links:
                records.append(dict(process_uuid=process, request=json.loads(linked[0]), outbox_state=outbox['state'],
                    outbox_request=json.loads(outbox['payload'])['request'], association=dict(association)))
    return records


def recover_recorded(journal, actual, originals):
    """A failed post-execution journal write may advance only from exact reads."""
    with read_only_veto():
        state = journal.read()  # Authenticate before inspecting or adopting a node.
        admit_state('findings-native-read', state, actual, originals)
        process = reconcile(state, reconciliation_records(state, actual-originals), actual-originals)
        if state['stage'] == 'submitted':
            state = journal.advance('recorded', process_uuid=process)
        return state


def durable_write(path, raw, *, exclusive=False):
    guard.no_symlinks(path)
    temporary = path.with_name(path.name + '.new-' + secrets.token_hex(8))
    with temporary.open('xb') as stream:
        os.chmod(temporary, 0o600); stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    if exclusive:
        os.link(temporary, path); temporary.unlink()
    else:
        os.replace(temporary, path)
    descriptor = os.open(path.parent, os.O_RDONLY)
    try: os.fsync(descriptor)
    finally: os.close(descriptor)


class Journal:
    """Authenticated local pointer plus immutable numbered stage records."""
    def __init__(self, directory, identity, *, create=True):
        self.directory = guard.no_symlinks(directory)
        self.identity = identity
        self.key = guard.no_symlinks(directory/'journal.key')
        self.path = guard.no_symlinks(directory/'journal.json')
        if not self.key.exists():
            if not create:
                raise ValueError('Preservation preflight journal required')
            if self.path.exists() or list(directory.glob('stage-*.json')):
                raise ValueError('Journal key missing')
            durable_write(self.key, secrets.token_bytes(32), exclusive=True)

    def read(self):
        if not self.path.exists():
            if list(self.directory.glob('stage-*.json')):
                raise ValueError('Ambiguous journal pointer; inspect immutable stages')
            return None
        envelope = json.loads(self.path.read_bytes())
        body = envelope['body']
        expected = hmac.new(self.key.read_bytes(), canonical(body), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(envelope['mac'], expected) or body['identity'] != self.identity:
            raise ValueError('Journal authentication failed')
        stages = sorted(self.directory.glob('stage-*.json'))
        if len(stages) != body['sequence'] or stages[-1].read_bytes() != self.path.read_bytes():
            raise ValueError('Journal pointer/stage history mismatch')
        previous = None
        for sequence, path in enumerate(stages, 1):
            guard.no_symlinks(path)
            raw = path.read_bytes(); entry = json.loads(raw); payload = entry['body']
            expected = hmac.new(self.key.read_bytes(), canonical(payload), hashlib.sha256).hexdigest()
            if (not hmac.compare_digest(entry['mac'], expected) or payload['identity'] != self.identity
                    or payload['sequence'] != sequence or payload['previous_sha256'] != previous):
                raise ValueError('Journal history authentication failed')
            previous = sha(raw)
        return body

    def advance(self, stage, **fields):
        previous = self.read()
        allowed = {None:'baselined', 'baselined':'prepared', 'prepared':'submitted', 'submitted':'recorded'}
        if allowed.get(previous['stage'] if previous else None) != stage and not (previous and stage == previous['stage'] == 'baselined'):
            raise ValueError('Illegal continuation journal transition')
        body = {**(previous or {}), **fields, 'stage':stage, 'identity':self.identity,
            'sequence':1 if previous is None else previous['sequence']+1,
            'previous_sha256':None if previous is None else sha(self.path.read_bytes())}
        raw = canonical({'body':body, 'mac':hmac.new(self.key.read_bytes(), canonical(body), hashlib.sha256).hexdigest()})
        durable_write(self.directory/f'stage-{body["sequence"]:04d}.json', raw, exclusive=True)
        durable_write(self.path, raw)
        return body


def process_start(pid):
    result = subprocess.run(['/bin/ps','-p',str(pid),'-o','lstart='], capture_output=True, text=True,
        env={'PATH':guard.PATH})
    return result.stdout.strip() if result.returncode == 0 else None


def prove_quiescent():
    # A dead owner is insufficient: descendants or a scoped container may live.
    result = subprocess.run(['/bin/ps','-axo','pid=,command='], capture_output=True, text=True, env={'PATH':guard.PATH})
    if result.returncode:
        raise ValueError('Cannot prove scoped processes absent')
    for line in result.stdout.splitlines():
        if (str(ORIGINAL.root) in line or ORIGINAL.run_uuid in line) and int(line.split()[0]) != os.getpid():
            raise ValueError('Scoped process remains active')
    docker = subprocess.run(['docker','ps','--format','{{.ID}}'], capture_output=True, text=True, env={'PATH':guard.PATH})
    if docker.returncode:
        raise ValueError('Cannot prove scoped containers absent')
    if docker.stdout.strip():
        inspected = subprocess.run(['docker','inspect',*docker.stdout.split()], capture_output=True, text=True, env={'PATH':guard.PATH})
        if inspected.returncode or ORIGINAL.run_uuid in inspected.stdout or str(ORIGINAL.root) in inspected.stdout:
            raise ValueError('Scoped or ambiguous container operation remains')


@contextmanager
def continuation_lock(directory):
    lock = guard.no_symlinks(directory/'continuation.lock')
    owner = guard.no_symlinks(directory/'owner.json')
    with lock.open('a+b') as stream:
        try: fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error: raise ValueError('Concurrent continuation lock holder') from error
        if owner.exists():
            record = json.loads(owner.read_bytes())
            observed = process_start(record['pid'])
            if observed is not None:
                raise ValueError('Live or reused owner identity; refusing recovery')
            prove_quiescent()
            durable_write(directory/('recovered-owner-'+secrets.token_hex(8)+'.json'), owner.read_bytes(), exclusive=True)
        start = process_start(os.getpid())
        if not start:
            raise ValueError('Cannot identify continuation owner')
        durable_write(owner, canonical(dict(pid=os.getpid(), start=start)))
        try: yield
        finally:
            owner.unlink()
            fcntl.flock(stream, fcntl.LOCK_UN)


def file_inventory(root):
    records = {}
    for path in sorted(root.rglob('*')):
        if root == ORIGINAL.root and path.is_relative_to(CONTINUATION):
            continue
        guard.no_symlinks(path)
        if path.is_file():
            raw = path.read_bytes()
            records[str(path.relative_to(root))] = dict(size=len(raw), sha256=sha(raw))
    return records


def row_inventory(connection):
    tables = {}
    for (name,) in connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
        quoted = '"'+name.replace('"','""')+'"'
        columns = connection.execute('PRAGMA table_info('+quoted+')').fetchall()
        rows = []
        for row in connection.execute('SELECT * FROM '+quoted):
            cells=[]
            for value in row:
                kind = type(value).__name__
                raw = value.hex() if isinstance(value, bytes) else value
                cell = dict(type=kind, raw=raw)
                if isinstance(value,str):
                    try: cell['canonical_json']=json.loads(value)
                    except (ValueError,TypeError): pass
                cells.append(cell)
            rows.append(cells)
        tables[name] = dict(columns=columns, primary_key=[c[1] for c in sorted(columns,key=lambda c:c[5]) if c[5]], rows=sorted(rows,key=canonical))
    return tables


def inventory():
    scope = retained_scope()
    records = original_records()
    validate_original_payloads(records)
    return dict(identity=scope.record(), records=records, processes=sorted(processes()),
        logical_repository=logical_repository(), files=file_inventory(scope.root))


def logical_repository():
    """Retained native objects are loose sha256 objects; refuse another layout."""
    entries = []
    def walk(node, tree, prefix=''):
        for name, value in tree.get('o', {}).items():
            if '/' in name or name in ('.','..'):
                raise ValueError('Native repository path escape')
            relative = prefix + name
            if 'k' in value:
                key = value['k']
                if len(key) != 64 or any(char not in '0123456789abcdef' for char in key):
                    raise ValueError('Unexpected native repository key')
                path = guard.no_symlinks(ORIGINAL.root/'native/container/loose'/key[:2]/key[2:])
                raw = path.read_bytes()
                if sha(raw) != key:
                    raise ValueError('Native repository content hash mismatch')
                entries.append(dict(node_uuid=node, path=relative, size=len(raw), sha256=key))
            else:
                walk(node, value, relative + '/')
    with readonly(ORIGINAL.root/'native/database.sqlite') as connection:
        for node, metadata in connection.execute('SELECT uuid,repository_metadata FROM db_dbnode ORDER BY uuid'):
            walk(node, json.loads(metadata))
    return entries


def capture_baseline(attempt, before):
    """Private copies only; no backup database or secret enters portable evidence."""
    private = attempt/'private'; private.mkdir(mode=0o700)
    copies = private/'original-files'; copies.mkdir(mode=0o700)
    for relative in before['files']:
        source=guard.no_symlinks(ORIGINAL.root/relative); target=copies/relative
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        shutil.copyfile(source,target); target.chmod(0o600)
    databases={}
    for relative in ('artifacts/combined.sqlite','native/database.sqlite','artifacts/private-http/modeling/model.sqlite3','artifacts/private-http/modeling/scratch.sqlite3'):
        source=ORIGINAL.root/relative
        with readonly(source) as connection:
            rows=row_inventory(connection)
            target=private/(relative.replace('/','__')+'.backup')
            with closing(sqlite3.connect(target)) as destination: connection.backup(destination)
            target.chmod(0o600)
            row_file=target.with_suffix('.rows.json'); durable_write(row_file,canonical(rows),exclusive=True)
            databases[relative]=dict(backup_sha256=sha(target.read_bytes()), rows_sha256=sha(row_file.read_bytes()), tables={name:len(table['rows']) for name,table in rows.items()})
    # db_dbnode.repository_metadata preserves each logical path/content key;
    # the copied container retains its physical objects, index and configuration.
    sources={}
    for relative in ('deployment/checks.py','deployment/tests/test_repository_guard.py','deployment/tests/test_findings_native_guards.py','deployment/tests/findings_native_fixture.py'):
        raw=(REPO/relative).read_bytes(); target=attempt/'sources'/relative
        target.parent.mkdir(parents=True,exist_ok=True); durable_write(target,raw,exclusive=True)
        sources[relative]=sha(raw)
    baseline=dict(before, databases=databases, sources=sources)
    durable_write(attempt/'baseline.json',canonical(baseline),exclusive=True)
    return baseline


def verify_preserved(before):
    after=inventory()
    if after != before:
        raise ValueError('Retained fixture preservation failed')
    return True


def verify_saved_baseline(state, before, *, allow_initial=False):
    """Authenticate complete original snapshots before continuation side effects."""
    if state is None:
        if allow_initial:
            return
        raise ValueError('Preservation preflight baseline required')
    name = state.get('baseline_attempt', '')
    if not name.startswith('attempt-') or len(name) != 12 or not name[8:].isdigit():
        raise ValueError('Invalid baseline attempt identity')
    path = guard.no_symlinks(CONTINUATION/name/'baseline.json')
    raw = path.read_bytes()
    if sha(raw) != state.get('baseline_sha256'):
        raise ValueError('Authenticated baseline bytes changed')
    baseline = json.loads(raw)
    expected_databases = {
        'artifacts/combined.sqlite', 'native/database.sqlite',
        'artifacts/private-http/modeling/model.sqlite3',
        'artifacts/private-http/modeling/scratch.sqlite3',
    }
    if (not isinstance(baseline, dict)
            or not {'identity', 'records', 'files', 'processes', 'databases', 'sources'} <= baseline.keys()
            or not isinstance(baseline['databases'], dict)
            or set(baseline['databases']) != expected_databases
            or not baseline['files'] or not baseline['sources']
            or set(baseline['processes']) != {r['process_uuid'] for r in before['records']}):
        raise ValueError('Incomplete preservation baseline')
    if baseline['identity'] != before['identity'] or baseline['records'] != before['records']:
        raise ValueError('Baseline original identities changed')
    if state['stage'] == 'baselined' and not state.get('activity') and (baseline['files'] != before['files'] or baseline['processes'] != before['processes']):
        raise ValueError('Original files changed since first preflight')
    for relative, description in baseline['databases'].items():
        if (not isinstance(description, dict)
                or not {'backup_sha256', 'rows_sha256', 'tables'} <= description.keys()
                or not isinstance(description['tables'], dict)):
            raise ValueError('Incomplete database preservation baseline')
        backup_path = guard.no_symlinks(path.parent/'private'/(relative.replace('/', '__')+'.backup'))
        if sha(backup_path.read_bytes()) != description['backup_sha256']:
            raise ValueError('Original database backup changed')
        rows_path = guard.no_symlinks(path.parent/'private'/(relative.replace('/','__')+'.rows.json'))
        rows_raw = rows_path.read_bytes()
        if sha(rows_raw) != description['rows_sha256']:
            raise ValueError('Original row snapshot changed')
        old = json.loads(rows_raw)
        if (not isinstance(old, dict) or set(old) != set(description['tables'])
                or any(not isinstance(table, dict)
                       or not {'columns', 'primary_key', 'rows'} <= table.keys()
                       or len(table['rows']) != description['tables'][name]
                       for name, table in old.items())):
            raise ValueError('Incomplete original row snapshot')
        with readonly(ORIGINAL.root/relative) as connection:
            current = row_inventory(connection)
        for table, original in old.items():
            present = current.get(table)
            if present is None or canonical(present['columns']) != canonical(original['columns']):
                raise ValueError('Original database schema changed')
            remaining = [canonical(row) for row in present['rows']]
            for row in original['rows']:
                encoded = canonical(row)
                if encoded not in remaining:
                    replacement=operational_replacement(relative,table,row,present['rows'],state)
                    encoded=canonical(replacement)
                remaining.remove(encoded)


def load_existing_backend():
    scope=validate_child()
    from aiida import load_profile
    from aiida.manage import get_manager
    load_profile(scope.profile)
    backend=get_manager().get_profile_storage()
    if (str(UUID(backend.profile.uuid)) != scope.profile_uuid
            or backend.profile.storage_config != {'filepath':str(scope.root/'native')}
            or str(UUID(backend.get_repository().uuid)) != scope.store_uuid):
        raise ValueError('Actual retained native identity mismatch')
    return backend


def bind_scope_interpreter(group):
    """The working copy's scope record names this checkout's approved interpreter.

    The interpreter is an environment binding, not retained content: the pinned record names the
    producer's interpreter. Only the preflight of a fresh working copy, before any continuation
    baseline exists, rebinds it, and only while the record still holds the pinned bytes and every
    other field equals the retained identity. A working copy baselined under another interpreter
    is refused.
    """
    require_original()
    if durable_fixture.native_scope() != ORIGINAL.root:
        raise ValueError('Native working root differs from its identity')
    marker=guard.no_symlinks(ORIGINAL.root/'scope.json')
    raw=marker.read_bytes()
    bound=json.loads(raw)
    expected=guard.Scope(ORIGINAL.root,ORIGINAL.run_uuid,guard.SCOPE_PREFIX+ORIGINAL.run_uuid,
        ORIGINAL.profile_uuid,ORIGINAL.store_uuid).record()
    if bound==expected:
        return
    pinned=durable_fixture.verified_file(durable_fixture.SCOPE_PREFIX+'/scope.json').read_bytes()
    if raw!=pinned or dict(bound,interpreter=None)!=dict(expected,interpreter=None):
        raise ValueError('Retained scope record differs beyond its interpreter binding')
    if group!='findings-native-preflight' or os.path.lexists(CONTINUATION):
        raise ValueError(
            'Only the preflight of a fresh working copy rebinds its interpreter; '
            're-materialize the working copy')
    mode=marker.stat().st_mode&0o777
    durable_write(marker,(json.dumps({**bound,'interpreter':expected['interpreter']},indent=2)+'\n').encode())
    marker.chmod(mode)


def scope_binding():
    """Pinned and working interpreter of the scope record, recorded in the preflight attempt."""
    pinned=durable_fixture.verified_file(durable_fixture.SCOPE_PREFIX+'/scope.json').read_bytes()
    working=guard.no_symlinks(ORIGINAL.root/'scope.json').read_bytes()
    return dict(pinned_interpreter=json.loads(pinned)['interpreter'],
        bound_interpreter=json.loads(working)['interpreter'],
        pinned_sha256=sha(pinned),bound_sha256=sha(working),rebound=pinned!=working)


def run_retained(group):
    if group not in {'findings-native-preflight','findings-native','findings-native-read'}:
        raise ValueError('Unknown retained group')
    require_original()
    bind_scope_interpreter(group)
    scope=retained_scope()
    command=[scope.interpreter,'-B',str(REPO/'deployment/checks.py'),'--'+group+'-child']
    result=subprocess.run(command,cwd=REPO,env=guard.clean_environment(scope),capture_output=True,text=True)
    print(result.stdout,end=''); print(result.stderr,end='',file=sys.stderr)
    return result.returncode


def child(group):
    scope=validate_child()  # Before imports, collection, allocation or writes.
    if group not in {'findings-native-preflight','findings-native','findings-native-read'}:
        raise ValueError('Unknown retained child')
    from checks import targets_for
    targets_for(group)
    prove_quiescent()
    before=inventory()
    originals={r['process_uuid'] for r in before['records']}
    guard.no_symlinks(CONTINUATION)
    if not CONTINUATION.exists():
        admit_state(group,None,set(before['processes']),originals)
        CONTINUATION.mkdir(mode=0o700)
    # Admission is read-only before lock-owner writes and attempt allocation.
    # Repeat under the exclusive lock to reject changes during acquisition.
    if group != 'findings-native-preflight':
        journal=Journal(CONTINUATION,scope.record(),create=False)
        state=journal.read()
        admit_state(group,state,set(before['processes']),originals)
        verify_saved_baseline(state,before)
    with continuation_lock(CONTINUATION):
        if inventory() != before:
            raise ValueError('Retained stores changed while acquiring lock')
        journal=Journal(CONTINUATION,scope.record(),create=group == 'findings-native-preflight')
        state=journal.read()
        admit_state(group,state,set(before['processes']),originals)
        verify_saved_baseline(state,before,allow_initial=group == 'findings-native-preflight')
        number=len(list(CONTINUATION.glob('attempt-*')))+1
        attempt=CONTINUATION/f'attempt-{number:04d}'; attempt.mkdir(mode=0o700)
        if group == 'findings-native-preflight':
            baseline=capture_baseline(attempt,before)
            durable_write(attempt/'scope-binding.json',canonical(scope_binding()),exclusive=True)
            preserved=verify_preserved(before)
            if state is None:
                journal.advance('baselined',baseline_sha256=sha((attempt/'baseline.json').read_bytes()),baseline_attempt=attempt.name)
            report=dict(group=group,passed=preserved,checks=1,process_count=len(before['processes']),original_files=len(before['files']),attempt=str(attempt),source_sha256=baseline['sources'])
            durable_write(attempt/'result.json',canonical(report),exclusive=True)
            print(json.dumps(report))
            return 0
        return qualification(group, scope, attempt, journal, before)

ACTIVE = None


def qualification(group, scope, attempt, journal, before):
    global ACTIVE, BACKEND
    ACTIVE = (scope, attempt, journal, before)
    sys.path[:0] = [str(REPO/'application/src'), str(REPO/'integration/src'), str(REPO/'deployment')]
    if group == 'findings-native-read':
        recover_recorded(journal,set(before['processes']),{r['process_uuid'] for r in before['records']})
    BACKEND = load_existing_backend()
    os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
    import pytest
    class Results:
        passed = failed = skipped = 0
        def pytest_runtest_logreport(self, report):
            if report.failed: self.failed += 1
            elif report.skipped: self.skipped += 1
            elif report.when == 'call' and report.passed: self.passed += 1
    results = Results()
    target = 'test_recorded_findings_read_only' if group == 'findings-native-read' else 'test_new_downstream_run_pins_retained_source_and_approach'
    status = pytest.main(['-q','--tb=short','-p','no:cacheprovider','--noconftest',
        '--basetemp='+str(attempt/'pytest'),str(REPO/'deployment/tests/test_findings_native.py')+'::'+target], plugins=[results])
    passed = status == 0 and results.passed == 1 and results.failed == results.skipped == 0
    report = dict(group=group,passed=passed,tests=results.passed+results.failed+results.skipped,
        failures=results.failed,skipped=results.skipped,attempt=str(attempt))
    durable_write(attempt/'result.json',canonical(report),exclusive=True)
    print(json.dumps(report))
    return 0 if passed else 1

# Every lifecycle import below occurs after the closed native/app child guard.
BACKEND = None


def signed_write(name, body, *, directory=CONTINUATION):
    key = guard.no_symlinks(CONTINUATION/'journal.key').read_bytes()
    envelope = dict(body=body, mac=hmac.new(key, canonical(body), hashlib.sha256).hexdigest())
    durable_write(directory/name, canonical(envelope), exclusive=True)


def signed_read(name, *, directory=CONTINUATION):
    envelope = json.loads(guard.no_symlinks(directory/name).read_bytes())
    expected = hmac.new((CONTINUATION/'journal.key').read_bytes(), canonical(envelope['body']), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, envelope['mac']):
        raise ValueError('Continuation command authentication failed')
    return envelope['body']


def active_attempt():
    pointer = signed_read('active.json')
    name = pointer['attempt']
    if not name.startswith('attempt-') or len(name) != 12 or not name[8:].isdigit():
        raise ValueError('Invalid active attempt')
    owner = json.loads((CONTINUATION/'owner.json').read_bytes())
    if process_start(owner['pid']) != owner['start']:
        raise ValueError('Continuation owner missing')
    attempt = guard.no_symlinks(CONTINUATION/name)
    setup = signed_read('setup.json', directory=attempt)
    if setup['attempt'] != name or setup['original_identity'] != retained_scope().record():
        raise ValueError('Setup identity mismatch')
    return attempt, setup


def app_child(mode):
    scope = guard.scope_from_environment()
    validate_identity(scope)
    if sys.executable != guard.APPROVED_CONTRACT_PYTHON or mode not in {'web-online','web-offline','prepare-once','execute-once'}:
        raise ValueError('Dedicated application child refused')
    attempt, setup = active_attempt()
    sys.path[:0] = [str(REPO/'application/src'),str(REPO/'deployment/tests')]
    from hyprn_mvp_app.store import Store
    from hyprn_mvp_app.modeling import ModelingClient
    store_path = ORIGINAL.root/'artifacts/combined.sqlite'
    key = ORIGINAL.root/'artifacts/fixture-model-key'
    if mode in {'prepare-once','execute-once'}:
        state = Journal(CONTINUATION,scope.record()).read()
        operation = signed_read(mode+'.json',directory=attempt)
        if (operation['run_id'] != state.get('run_id') or
            state['stage'] != ('baselined' if mode == 'prepare-once' else 'submitted')):
            raise ValueError('Dispatch stage/request mismatch')
        if mode == 'execute-once' and operation['request'] != state['request']:
            raise ValueError('Launch request changed')
        from hyprn_mvp_app import dispatcher
        os.environ['HYPRN_MVP_APP_STORE'] = str(store_path)
        os.environ['HYPRN_MVP_MODEL_URL'] = setup['model_url']
        os.environ['HYPRN_MVP_MODEL_KEY_FILE'] = str(key)
        sys.argv = ['dispatcher','--run-id',operation['run_id']] + (['--prepare-only'] if mode == 'prepare-once' else [])
        dispatcher.main()
        return
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from fastapi.staticfiles import StaticFiles
    from fastapi.testclient import TestClient
    from hyprn_mvp_app.api import create_app
    from hyprn_mvp_app.auth import Auth
    from combined_fixture import write_http_response
    store = Store(store_path)
    model = ModelingClient(setup['model_url'],key.read_bytes())
    assert model.transport is None
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_GET(self): self.handle_api()
        def do_POST(self): self.handle_api()
        def do_PATCH(self): self.handle_api()
        def do_PUT(self): self.handle_api()
        def do_DELETE(self): self.handle_api()
        def handle_api(self):
            if self.command != 'GET' and self.path != '/api/1/session' and (attempt/'readers-only').exists():
                self.send_response(405);self.send_header('Content-Length','0');self.end_headers();return
            assert not any(n.split('.')[0] in {'aiida','openmdao','openturns'} for n in sys.modules)
            with TestClient(app,base_url=origin) as client:
                response=client.request(self.command,self.path,
                    content=self.rfile.read(int(self.headers.get('Content-Length',0))),
                    headers={k:v for k,v in self.headers.items() if k.lower() not in {'host','content-length','connection'}})
            write_http_response(self,response)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    origin='http://127.0.0.1:'+str(server.server_port);guard.validate_url(origin)
    auth=Auth(store,origin)
    with store.connection() as db:
        assert [r[0] for r in db.execute('SELECT username FROM users')]==['owner']
    app=create_app(store,auth,model)
    app.mount('/ui',StaticFiles(directory=str(attempt/'ui'),html=True))
    durable_write(attempt/(mode+'-ready.json'),canonical(dict(url=origin)),exclusive=True)
    try: server.serve_forever()
    finally: server.server_close()


class NativeContinuation:
    def __init__(self,scope,attempt,journal,before,read_only=False):
        self.scope,self.attempt,self.journal,self.before=scope,attempt,journal,before
        self.read_only=read_only
        self.backend=BACKEND
        self.created=[]
        self.web=None
        self.http=None
        self.sid=ORIGINAL.study_id
        self.events=[]
        self.state=journal.read()

    def __enter__(self):
        try:
            self.start()
            return self
        except BaseException:
            self.close()
            raise

    def __exit__(self,*args): self.close()

    def emit(self,name,value):
        durable_write(self.attempt/name,canonical(value),exclusive=True)
        return value

    def docker(self,*args,check=True):
        result=subprocess.run(['docker',*args],env=guard.clean_environment(self.scope),
            capture_output=True,text=True,timeout=90)
        if check and result.returncode: raise AssertionError(result.stderr)
        return result

    def count(self):
        from aiida import orm
        return orm.QueryBuilder(backend=self.backend).append(orm.CalcJobNode).count()

    def payload(self,rid):
        with self.store.connection() as db:
            return json.loads(db.execute('SELECT payload FROM outbox WHERE run_id=?',(rid,)).fetchone()[0])

    def request(self,method,path,body=None,status=200):
        if self.read_only and method!='GET': require_write('public scientific command')
        response=self.http.request(method,'/api/1/studies/'+self.sid+'/'+path,json=body)
        self.events.append(dict(method=method,path=path,status=response.status_code))
        assert response.status_code==status,response.text
        return response.json()['data']

    def command(self,name,path,body,status=200):
        require_write('public '+name)
        record_name='command-'+name+'.json'
        record_path=CONTINUATION/record_name
        if record_path.exists():
            record=signed_read(record_name)
            assert record['path']==path
            body=record['body']
        else:
            # Exact bodies and deterministic IDs are durable before any POST.
            from uuid import uuid5
            body=dict(body,command_id=str(uuid5(UUID(ORIGINAL.run_uuid),'findings-continuation:'+name)))
            signed_write(record_name,dict(path=path,body=body))
        response_name='response-'+name+'.json'
        if (CONTINUATION/response_name).exists():
            return signed_read(response_name)
        response=self.request('POST',path,body,status)
        signed_write(response_name,response)
        return response

    def start(self):
        from hyprn_mvp_app.store import Store
        self.store=Store(ORIGINAL.root/'artifacts/combined.sqlite')
        with self.store.connection() as db:
            self.actor=db.execute("SELECT actor_id FROM users WHERE username='owner'").fetchone()[0]
        assert self.count()==(8 if self.read_only else 7)
        # A separate APP-only scope carries staging/browser metadata and never a native config.
        self.app_scope=guard.allocate_scope(guard.new_scope())
        original_setup=json.loads((ORIGINAL.root/'artifacts/combined-setup.json').read_bytes())
        self.password=original_setup['password']
        # Scoped names: hyprn-mvp-test-<scope8>-<role>.
        self.name=guard.SCOPE_PREFIX+ORIGINAL.run_uuid[:8]+'-findings-'+self.attempt.name
        self.network=self.name+'-private'
        self.gateway=self.name+'-gateway'
        if self.read_only:
            self.state=self.journal.read()
        else:
            self.journal.advance('baselined',activity=True)
            self.state=self.journal.read()
        # Readers never rebuild or attest. They restore only the audited private transport.
        self.start_model_copy()
        self.build_ui()
        self.setup=dict(attempt=self.attempt.name,original_identity=self.scope.record(),
            model_url=self.model_url,production_http=True,app_scope=self.app_scope.record())
        signed_write('setup.json',self.setup,directory=self.attempt)
        if (CONTINUATION/'active.json').exists():
            previous=(CONTINUATION/'active.json').read_bytes()
            durable_write(self.attempt/'previous-active.json',previous,exclusive=True)
            (CONTINUATION/'active.json').unlink()
        signed_write('active.json',dict(attempt=self.attempt.name))
        self.start_web('online')
        # Original immutable revisions/source bytes are authenticated private HTTP reads.
        from hyprn_mvp_app.modeling import ModelingClient
        model=ModelingClient(self.model_url,(ORIGINAL.root/'artifacts/fixture-model-key').read_bytes())
        for rid in (ORIGINAL.source_run,ORIGINAL.downstream_run):
            expected=self.payload(rid)['frozen']['model_snapshot']
            _,actual=model.call(self.actor,self.sid,'GET','/models/'+expected['model_id']+'/revisions/'+expected['model_revision_id'])
            assert actual['data']==expected
            self.emit('private-model-'+rid+'.json',actual)
        assert not self.canary()['candidate_side_effect']

    def start_model_copy(self):
        from units_model_fixture import stage_sources,mounts
        import checks
        checks.PROJECTION_SCOPE=self.app_scope
        _,stage,image=stage_sources()
        self.stage,self.image=stage,image
        private=self.attempt/'private';private.mkdir(mode=0o700)
        original=ORIGINAL.root/'artifacts/private-http/modeling'
        copied=private/'modeling';shutil.copytree(original,copied)
        self.private_copy=copied
        self.original_private=file_inventory(original)
        self.copy_before={}
        for name in ('model.sqlite3','scratch.sqlite3'):
            with readonly(original/name) as source:
                source_rows=row_inventory(source)
                # Backup destination is newly copied and has no open writer.
                (copied/name).unlink()
                with closing(sqlite3.connect(copied/name)) as dest: source.backup(dest)
            with closing(sqlite3.connect(copied/name)) as db:
                assert row_inventory(db)==source_rows
            self.copy_before[name]=source_rows
        for p in [copied,*copied.rglob('*')]: p.chmod(0o777 if p.is_dir() else 0o666)
        self.emit('private-copy-before.json',dict(original_files=self.original_private,
            databases={k:{t:len(v['rows']) for t,v in rows.items()} for k,rows in self.copy_before.items()}))
        self.label='org.hyprn-mvp.test-scope='+self.scope.run_uuid
        assert self.docker('inspect',self.name,check=False).returncode!=0
        assert self.docker('inspect',self.gateway,check=False).returncode!=0
        assert self.docker('network','inspect',self.network,check=False).returncode!=0
        self.docker('network','create','--internal','--label',self.label,self.network);self.created.append(('network',self.network))
        args=['run','-d','--pull','never','--name',self.name,'--label',self.label,'--network',self.network,
            '--user','10001:10001','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
            '--memory','768m','--pids-limit','128','--cpus','1',
            '--tmpfs','/tmp:rw,noexec,nosuid,size=192m,mode=1777',
            '--tmpfs','/native/tmp:rw,noexec,nosuid,size=32m,uid=10001,gid=10001',
            '--mount',f'type=bind,src={copied},dst=/store',
            '--mount',f'type=bind,src={ORIGINAL.root}/artifacts/fixture-model-key,dst=/run/model.key,readonly',
            '--mount',f'type=bind,src={ORIGINAL.root}/artifacts/private-http/rails.key,dst=/run/rails.key,readonly']
        for src,dst in mounts(stage).items():args+=['--mount',f'type=bind,src={src},dst={dst},readonly']
        self.docker(*args,image);self.created.append(('container',self.name))
        tunnel="require 'socket'; server=TCPServer.new('0.0.0.0',8080); loop { client=server.accept; Thread.new(client) { |c| u=nil; begin; u=TCPSocket.new('"+self.name+"',3000); loop { IO.select([c,u])[0].each { |s| (s==c ? u : c).write(s.readpartial(65536)) } }; rescue EOFError,IOError,SystemCallError; ensure; c.close; u&.close; end } }"
        self.docker('run','-d','--pull','never','--name',self.gateway,'--label',self.label,'--network','bridge',
            '--publish','127.0.0.1::8080','--user','10001:10001','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
            '--memory','128m','--pids-limit','64','--cpus','1','--entrypoint','ruby',image,'-e',tunnel)
        self.created.append(('container',self.gateway));self.docker('network','connect',self.network,self.gateway)
        info=json.loads(self.docker('inspect',self.name).stdout)[0]
        gateway=json.loads(self.docker('inspect',self.gateway).stdout)[0]
        assert info['Image']==image and info['HostConfig']['ReadonlyRootfs'] and info['Config']['User']=='10001:10001'
        assert gateway['Mounts']==[] and gateway['HostConfig']['ReadonlyRootfs']
        assert json.loads(self.docker('network','inspect',self.network).stdout)[0]['Internal']
        assert all(m['Source']!=str(original) for m in info['Mounts'])
        port=gateway['NetworkSettings']['Ports']['8080/tcp'][0];assert port['HostIp']=='127.0.0.1'
        self.model_url='http://127.0.0.1:'+port['HostPort']+'/modeling/1'
        guard.validate_url(self.model_url.removesuffix('/modeling/1'))
        import httpx,time
        for _ in range(120):
            try:
                with httpx.Client(trust_env=False,timeout=1) as client:
                    if client.get(self.model_url+'/capabilities').status_code==401:break
            except httpx.HTTPError:pass
            time.sleep(.25)
        else:raise AssertionError('Private producer startup failed')
        self.emit('private-transport.json',dict(image=image,container=info['Id'],network=self.network,
            user=info['Config']['User'],read_only=info['HostConfig']['ReadonlyRootfs'],cap_drop=info['HostConfig']['CapDrop'],
            security=info['HostConfig']['SecurityOpt'],mounts=info['Mounts'],
            gateway=dict(id=gateway['Id'],mounts=gateway['Mounts'],ports=gateway['NetworkSettings']['Ports']),
            sources={str(p.relative_to(stage)):sha(p.read_bytes()) for p in stage.rglob('*') if p.is_file()}))

    def canary(self):
        result=self.docker('exec',self.name,'ruby','-rjson','-e',
            "raise 'candidate executed' if File.exist?('/store/forbidden-candidate-import'); raise 'privilege' if File.exist?('/var/run/docker.sock') || File.exist?('/usr/local/bin/python'); puts JSON.generate(candidate_side_effect:false,docker:false,python:false)")
        return json.loads(result.stdout)

    def build_ui(self):
        command=['node',str(REPO/'ui/node_modules/vite/bin/vite.js'),'build',str(REPO/'ui'),
            '--config',str(REPO/'ui/vite.config.ts'),'--configLoader','runner','--outDir',str(self.attempt/'ui')]
        result=subprocess.run(command,cwd=REPO,env=guard.clean_environment(self.app_scope),capture_output=True,text=True,timeout=120)
        durable_write(self.attempt/'ui-build.log',(result.stdout+result.stderr).encode(),exclusive=True)
        assert result.returncode==0
        self.emit('ui-build.json',dict(command=command,files=file_inventory(self.attempt/'ui')))

    def start_web(self,mode):
        import httpx,time
        self.mode=mode
        self.web_log=(self.attempt/('web-'+mode+'.log')).open('xb')
        self.web=subprocess.Popen([guard.APPROVED_CONTRACT_PYTHON,'-B',str(Path(__file__)),'web-'+mode],
            cwd=REPO,env=guard.clean_environment(self.scope),stdout=self.web_log,stderr=self.web_log)
        ready=self.attempt/('web-'+mode+'-ready.json')
        for _ in range(100):
            if ready.exists():break
            assert self.web.poll() is None,'Dedicated app child failed: '+str(self.attempt/('web-'+mode+'.log'))
            time.sleep(.1)
        self.url=json.loads(ready.read_bytes())['url'];guard.validate_url(self.url)
        self.http=httpx.Client(base_url=self.url,trust_env=False,timeout=120)
        response=self.http.post('/api/1/session',json=dict(username='owner',password=self.password),headers={'Origin':self.url})
        assert response.status_code==200,response.text
        self.http.headers.update({'Origin':self.url,'X-CSRF-Token':response.json()['data']['csrf_token']})

    def stop_web(self):
        if self.http:self.http.close();self.http=None
        if self.web:
            self.web.terminate();self.web.wait(timeout=15);self.web_log.close();self.web=None

    def runtime(self):
        require_write('isolated runtime qualification')
        from hyprn_mvp_integration import launcher
        from hyprn_mvp_integration.calculation import NativeExecution
        self.native=NativeExecution(backend=self.backend,root=self.scope.root)
        self.bind_worker_entry()
        try:self.native.require_attestation()
        except RuntimeError as error:
            if self.journal.read()['stage']!='baselined':raise
            self.emit('prior-attestation-refusal.json',dict(error=str(error)))
            from execution_runtime import build_worker
            build_worker(root=self.scope.root)
            launcher.attest(root=self.scope.root)
        self.emit('runtime-qualified.json',self.native.require_attestation())
        self.runtime_hashes=launcher.execution_source_hashes()
        return self.runtime_hashes

    def bind_worker_entry(self):
        """The worker entry runs the launcher this tree attests, never the producer's checkout.

        The retained launch-worker names the checkout and interpreter of the producer run, which
        may since have moved or been removed. Only a baselined continuation, the stage that may
        also rebuild and re-attest the worker, rebinds it; both digests are recorded.
        """
        require_write('worker entry binding')
        entry=guard.no_symlinks(self.scope.root/'launch-worker')
        retained=entry.read_bytes();current=guard.worker_wrapper_text(self.scope).encode()
        if retained!=current:
            if self.journal.read()['stage']!='baselined':raise ValueError('Worker entry names another tree after baseline')
            durable_write(entry,current);entry.chmod(0o700)
        self.emit('worker-entry.json',dict(retained_sha256=sha(retained),bound_sha256=sha(current),rebound=retained!=current))

    def dispatch(self,stage):
        require_write(stage)
        import dispatch_runtime
        state=self.journal.read()
        operation=dict(run_id=state['run_id'],request=state.get('request'))
        signed_write(stage+'.json',operation,directory=self.attempt)
        # Once-only durable intent prevents duplicate launch across interrupted attempts.
        signed_write(stage+'-intent.json',operation)
        command=[guard.APPROVED_CONTRACT_PYTHON,'-B',str(Path(__file__)),stage]
        with (self.attempt/(stage+'.log')).open('xb') as stream:
            status=dispatch_runtime.bridge_child(self.native,command,env=guard.clean_environment(self.scope),cwd=REPO,stderr=stream)
        self.emit(stage+'-result.json',dict(command=command,exit=status))
        assert status==0

    def author(self):
        from copy import deepcopy
        from uuid import uuid5
        identifier=lambda label:str(uuid5(UUID(ORIGINAL.run_uuid),'findings-continuation:'+label))
        original=self.request('GET','runs/'+ORIGINAL.downstream_run)
        self.source=self.request('GET','runs/'+ORIGINAL.source_run)
        config=original['history']['configuration'];model=original['history']['model_snapshot']
        assert config['approach_binding'] is None and self.source['history']['configuration']['approach_binding'] is None
        bid=identifier('model-binding');self.case_id=identifier('case')
        content=dict(schema_version='1',question='What qualifications accompany the retained specific energy?',scope='One original-source pinned native continuation.',
            limitations='No new validity assessment.',open_questions='Independent engineering review remains pending.',steps=[
                dict(step_id=identifier('step'),title='Convert retained specific energy',purpose='Inspect exact source qualifications',
                    rationale='Native identity calculation with explicit unit conversion',remaining_work='',
                    intent=dict(transformation='Identity in J/kg',inputs='Retained specific energy in MJ/kg',outputs='Specific energy in J/kg',depends_on_step_ids=[]),
                    implementation_state='linked',implementation_refs=[dict(kind='model',binding_id=bid)],assumption_refs=[],evidence_links=[])],
            model_bindings=[dict(binding_id=bid,model_id=model['model_id'],model_revision_id=model['model_revision_id'])],
            cases=[dict(case_id=self.case_id,title='Retained energy case',question='Does the retained input preserve its qualifications?',
                rationale='An upstream failed criterion does not rewrite downstream facets.',binding_id=bid,evidence_links=[])],
            assumptions=[],basis_refs=[])
        state=self.request('GET','approach')
        revision=state['draft']['revision'] if state['draft'] else None
        if (CONTINUATION/'response-draft.json').exists():
            draft=signed_read('response-draft.json')
        else:
            body=dict(schema_version='1',expected_revision=revision,content=content)
            preview=self.request('POST','approach/preview',body)
            self.emit('approach-preview.json',dict(body=body,response=preview))
            assert not preview['issues'],preview['issues']
            draft=self.command('draft','approach/draft',dict(body,expected_preview_digest=preview['preview_digest']))
        if (CONTINUATION/'response-version.json').exists():
            self.version=signed_read('response-version.json')['saved']
        else:
            preview=self.request('POST','approach/preview',dict(schema_version='1',expected_revision=draft['revision'],content=content))
            assert not preview['issues'],preview['issues']
            self.version=self.command('version','approach/versions',dict(schema_version='1',expected_revision=draft['revision'],expected_preview_digest=preview['preview_digest']),201)['saved']
        if (CONTINUATION/'response-configuration.json').exists():
            self.saved=signed_read('response-configuration.json')
        else:
            study=self.http.get('/api/1/studies/'+self.sid).json()['data']
            input_=config['inputs'][0];binding=input_['result_binding']
            # Copy authored criterion inputs only; conversion/closure are resolved by real APIs.
            value=dict(schema_version='4',study_id=self.sid,model_id=model['model_id'],model_revision_id=model['model_revision_id'],
                name='Pinned native retained energy',inputs=[dict(kind='run_result',target=input_['target'],source_run_id=ORIGINAL.source_run,
                    source_output=binding['source_output'],expected_results_digest=ORIGINAL.source_results_digest,
                    provenance=input_['provenance'])],criteria=deepcopy(config['criteria']),numerical=deepcopy(config['numerical']),
                context_source=dict(kind='current_study',expected_study_revision=study['revision']),notes=['One original-source native Findings proof'],
                assumptions=[],general_context_evidence_version_ids=config['general_context_evidence_version_ids'],derivation=None,
                approach_selection=dict(approach_version_id=self.version['version']['approach_version_id'],case_id=self.case_id))
            preview=self.request('POST','configurations/preview',value)
            self.emit('configuration-preview.json',dict(body=value,response=preview))
            assert preview['compatibility']['compatible']
            assert '1000000' in json.dumps(preview)
            self.saved=self.command('configuration','configurations',dict(configuration_id=None,expected_revision=None,configuration=value,expected_preview_digest=preview['candidate_digest']),201)
        self.emit('public-saved-before-run.json',dict(version=self.version,saved=self.saved,source=self.source))
        binding=self.saved['configuration']['inputs'][0]['result_binding']
        assert binding['original_value']==1 and binding['original_units']=='MJ/kg'
        assert binding['conversion']['factor']==1000000 and binding['conversion']['destination_value']==1000000
        pin=self.saved['configuration']['approach_binding']
        assert pin['approach_version_id']==self.version['version']['approach_version_id'] and pin['case_id']==self.case_id
        assert self.saved['approach_closure'] and pin['closure_digest']
        run=self.command('run','runs',dict(configuration_revision_id=self.saved['configuration']['configuration_revision_id']),202)
        self.rid=run['run_id']
        self.journal.advance('baselined',run_id=self.rid,authoring=dict(case_id=self.case_id,version=self.version,saved=self.saved))

    def execute_once(self):
        self.runtime()
        self.author()
        assert self.count()==7 and not self.canary()['candidate_side_effect']
        from hyprn_mvp_integration import launcher
        assert launcher.execution_source_hashes()==self.runtime_hashes
        self.native.require_attestation()
        self.dispatch('prepare-once')
        assert self.count()==7 and not self.canary()['candidate_side_effect']
        payload=self.payload(self.rid)
        assert payload['bundle']['manifest']['schema_version']=='6' and payload['frozen']['schema_version']=='5'
        self.emit('prepared.json',payload)
        self.journal.advance('prepared',request=payload['request'],bundle_sha256=sha(canonical(payload['bundle'])),
            source_hashes=self.runtime_hashes,prepared_process_count=7,inert_canary=True)
        assert launcher.execution_source_hashes()==self.runtime_hashes
        self.native.require_attestation()
        self.journal.advance('submitted')
        self.dispatch('execute-once')
        payload=self.payload(self.rid)
        assert self.count()==8
        detail=self.request('GET','runs/'+self.rid)
        assert detail['state']=='recorded' and not detail['history']['errors'],dict(state=detail['state'],errors=detail['history']['errors'])
        self.journal.advance('recorded',process_uuid=payload['history']['association']['process_uuid'],
            outbox_sha256=sha(canonical(payload)))
        return self.finish()

    def read_recorded(self):
        state=self.journal.read()
        self.rid=state['run_id']
        self.version=state['authoring']['version'];self.saved=state['authoring']['saved'];self.case_id=state['authoring']['case_id']
        self.source=self.request('GET','runs/'+ORIGINAL.source_run)
        return self.finish()

    def scientific_rows(self):
        with self.store.connection() as db:
            return {name:table for name,table in row_inventory(db).items() if name not in {'sessions','execution_observation'}}

    def browser(self,mode,detail):
        from dataclasses import replace
        # Distinct ordinary APP scopes keep each browser invocation append-only.
        browser_scope=guard.allocate_scope(guard.new_scope(url=self.url))
        root=browser_scope.root
        manifest=dict(study_id=self.sid,password=self.password,approach_version_id=self.version['version']['approach_version_id'],
            case_id=self.case_id,configuration_name=self.saved['configuration']['name'],run_id=self.rid,
            source_id=ORIGINAL.source_run,downstream=detail,source=self.source,mode=mode)
        durable_write(root/'artifacts/findings-input.json',canonical(manifest),exclusive=True)
        durable_write(root/'artifacts/package.json',b'{"type":"module"}',exclusive=True)
        config=root/'artifacts/playwright.config.ts'
        durable_write(config,('import base from '+json.dumps(str(REPO/'ui/playwright.isolated.config.ts'))+
            ';export default {...base,testDir:'+json.dumps(str(REPO/'ui/tests'))+',testMatch:["findings-native.spec.ts"]};').encode(),exclusive=True)
        before=self.scientific_rows()
        command=['node',str(REPO/'ui/node_modules/playwright/cli.js'),'test','--config',str(config),'--grep','@findings-'+mode,'--reporter=json']
        result=subprocess.run(command,cwd=REPO,env=guard.clean_environment(browser_scope),capture_output=True,text=True,timeout=180)
        durable_write(self.attempt/('browser-'+mode+'.json'),result.stdout.encode(),exclusive=True)
        durable_write(self.attempt/('browser-'+mode+'.stderr'),result.stderr.encode(),exclusive=True)
        self.emit('browser-'+mode+'-scope.json',browser_scope.record())
        report=json.loads(result.stdout);stats=report['stats']
        assert result.returncode==0 and stats['expected']==1 and not report.get('errors') and not any(stats[k] for k in ('unexpected','skipped','flaky')),stats
        assert before==self.scientific_rows() and self.count()==8
        return dict(tests=1,scope=str(root),stats=stats)

    def finish(self):
        from aiida import orm
        detail=self.request('GET','runs/'+self.rid);payload=self.payload(self.rid)
        node=orm.load_node(self.journal.read()['process_uuid'])
        source=orm.load_node(ORIGINAL.source_process).outputs.results
        links=[dict(label=link.link_label,uuid=link.node.uuid,type=link.link_type.value) for link in node.base.links.get_incoming().all()]
        assert source.uuid in {link['uuid'] for link in links}
        assert node.is_finished_ok and not node.base.caching.is_created_from_cache
        self.emit('native-links.json',links)
        durable_write(self.attempt/'readers-only',b'GET-only after login',exclusive=True)
        before=self.scientific_rows()
        with read_only_veto():
            online=self.browser('online',detail)
            self.docker('stop',self.name)
            assert not json.loads(self.docker('inspect',self.name).stdout)[0]['State']['Running']
            self.emit('model-stopped.json',dict(container=self.name,running=False))
            self.stop_web();self.start_web('offline')
            assert self.request('GET','runs/'+self.rid)['history']==detail['history']
            assert self.request('GET','runs/'+ORIGINAL.source_run)['history']==self.source['history']
            assert self.payload(self.rid)==payload
            offline=self.browser('offline',detail)
        assert self.scientific_rows()==before
        self.stop_web()
        proof=dict(source=self.source,downstream=detail,saved=self.saved,version=self.version,case_id=self.case_id,payload=payload,
            process_count=self.count(),prepared_process_count=self.journal.read()['prepared_process_count'],
            inert_canary=self.journal.read()['inert_canary'],uncached=not node.base.caching.is_created_from_cache,
            source_result_link=source.uuid,browser=dict(online=online,offline=offline,scientific_rows_unchanged=True,model_stopped=True))
        self.close_model()
        # Close native handles before the independent immutable preservation scan.
        from aiida.manage import get_manager
        # Close the checked-out session before disposing its engine (AiiDA 2.8 resource order).
        self.backend.get_session().close()
        get_manager().reset_profile()
        proof['preservation']=preservation_after(self.journal,self.attempt)
        self.emit('proof.json',proof)
        return proof

    def close_model(self):
        for kind,name in reversed(self.created):
            info=json.loads(self.docker(*(['network','inspect',name] if kind=='network' else ['inspect',name])).stdout)[0]
            labels=info['Labels'] if kind=='network' else info['Config']['Labels']
            assert labels['org.hyprn-mvp.test-scope']==self.scope.run_uuid
            if kind=='container':
                # A graceful stop lets the private modeling service close its copied stores, so
                # no write-ahead log blocks the immutable read below, also after a failure.
                self.docker('stop',name,check=False)
                durable_write(self.attempt/(name+'.log'),(self.docker('logs',name).stdout).encode(),exclusive=True)
                self.docker('rm','-f',name)
            else:self.docker('network','rm',name)
        self.created=[]
        if hasattr(self,'original_private'):
            assert file_inventory(ORIGINAL.root/'artifacts/private-http/modeling')==self.original_private
            differences={}
            for name,old in self.copy_before.items():
                with readonly(self.private_copy/name) as db:now=row_inventory(db)
                differences[name]=private_copy_delta(old,now)
            if not (self.attempt/'private-copy-additions.json').exists():self.emit('private-copy-additions.json',differences)

    def close(self):
        self.stop_web()
        self.close_model()


def preservation_after(journal,attempt):
    state=journal.read()
    baseline_path=CONTINUATION/state['baseline_attempt']/'baseline.json'
    raw=baseline_path.read_bytes();assert sha(raw)==state['baseline_sha256']
    baseline=json.loads(raw)
    after=inventory()
    assert len(after['processes'])==8 and set(after['processes'])-set(baseline['processes'])=={state['process_uuid']}
    changed={}
    # Explicit mutable database/index/runtime artifacts only; old scientific loose objects and all other originals exact.
    mutable={'artifacts/combined.sqlite','native/database.sqlite','native/container/packs.idx','runtime.json',
        'launch-worker','evidence/containment.json','evidence/worker-build.log','canaries/host-secret'}
    for name,item in baseline['files'].items():
        if after['files'].get(name)!=item:
            assert name in mutable,('Original file changed',name)
            changed[name]=dict(before=item,after=after['files'].get(name))
    additions={}
    operational_changes={}
    for name,description in baseline['databases'].items():
        rows_path=baseline_path.parent/'private'/(name.replace('/','__')+'.rows.json')
        old=json.loads(rows_path.read_bytes());assert sha(rows_path.read_bytes())==description['rows_sha256']
        with readonly(ORIGINAL.root/name) as db:now=row_inventory(db)
        delta={}
        for table,prior in old.items():
            assert canonical(now[table]['columns'])==canonical(prior['columns'])
            remaining=[canonical(row) for row in now[table]['rows']]
            for row in prior['rows']:
                encoded=canonical(row)
                if encoded not in remaining:
                    replacement=operational_replacement(name,table,row,now[table]['rows'],state)
                    operational_changes[name+'/'+table]=dict(before=row,after=replacement)
                    encoded=canonical(replacement)
                remaining.remove(encoded)
            if remaining:delta[table]=[json.loads(row) for row in remaining]
        additions[name]=delta
    app=additions['artifacts/combined.sqlite']
    exact_counts={'approach_drafts':1,'approach_versions':1,'configuration_families':1,'configurations':1,
        'outbox':1,'receipts':4,'run_associations':1}
    assert set(app)-{'sessions'}==set(exact_counts)
    assert all(len(app[name])==count for name,count in exact_counts.items())
    native=additions['native/database.sqlite']
    assert set(native)=={'db_dblink','db_dbnode'} and len(native['db_dblink'])==8 and len(native['db_dbnode'])==7
    assert not additions['artifacts/private-http/modeling/model.sqlite3']
    assert not additions['artifacts/private-http/modeling/scratch.sqlite3']
    old_logical={canonical(row) for row in baseline['logical_repository']}
    assert old_logical <= {canonical(row) for row in after['logical_repository']}
    execution_attempts=[path.parent for path in CONTINUATION.glob('attempt-*/execute-once-result.json')
        if json.loads(path.read_bytes())['exit']==0]
    assert len(execution_attempts)==1
    execution_attempt=execution_attempts[0]
    assert json.loads((execution_attempt/'prepared.json').read_bytes())['request']==state['request']
    copy_proof={}
    for name in ('model.sqlite3','scratch.sqlite3'):
        old=json.loads((baseline_path.parent/'private'/('artifacts__private-http__modeling__'+name+'.rows.json')).read_bytes())
        with readonly(execution_attempt/'private/modeling'/name) as db:now=row_inventory(db)
        copy_proof[name]=private_copy_delta(old,now)
    assert len(copy_proof['model.sqlite3']['additions']['modeling_revisions'])==1
    result=dict(passed=True,original_processes=baseline['processes'],new_process=state['process_uuid'],
        execution_attempt=str(execution_attempt),executed_private_copy=copy_proof,original_logical_files=len(old_logical),
        original_files=len(baseline['files']),changed_files=changed,added_files={k:v for k,v in after['files'].items() if k not in baseline['files']},
        row_additions=additions,operational_changes=operational_changes,logical_repository=after['logical_repository'])
    durable_write(attempt/'preservation.json',canonical(result),exclusive=True)
    return result

def operational_replacement(relative, table, original, rows, state):
    """Only the two observed operational rows may replace original rows."""
    if relative == 'artifacts/combined.sqlite' and table == 'execution_observation' and state.get('activity'):
        matching=[row for row in rows if row[0] == original[0]]
        if len(matching)==1:
            return matching[0]
    if relative == 'native/database.sqlite' and table == 'db_dbsetting' and state['stage'] in {'submitted','recorded'}:
        if original[1]['raw'] == 'process|state_change|calculation':
            matching=[row for row in rows if all(row[n] == original[n] for n in (0,1,3))]
            if len(matching)==1:
                from datetime import datetime
                row=matching[0]
                if all(datetime.fromisoformat(row[n].get('canonical_json',row[n]['raw'])) >=
                       datetime.fromisoformat(original[n].get('canonical_json',original[n]['raw'])) for n in (2,4)):
                    return row
    raise ValueError('Original non-operational row changed: '+relative+'/'+table)


def private_copy_delta(old, now):
    """Permit only one preparation revision/receipt, with their exact sequences."""
    changes={}
    for table,prior in old.items():
        assert canonical(now[table]['columns'])==canonical(prior['columns'])
        if table == 'sqlite_sequence':continue
        remaining=[canonical(row) for row in now[table]['rows']]
        for row in prior['rows']:
            encoded=canonical(row);assert encoded in remaining,('private original row changed',table);remaining.remove(encoded)
        if remaining:
            assert table in {'modeling_commands','modeling_revisions'} and len(remaining)==1
            changes[table]=[json.loads(row) for row in remaining]
    assert set(changes) in (set(),{'modeling_commands','modeling_revisions'})
    before={row[0]['raw']:row[1]['raw'] for row in old['sqlite_sequence']['rows']}
    after={row[0]['raw']:row[1]['raw'] for row in now['sqlite_sequence']['rows']}
    assert set(before)==set(after)
    counters={}
    for name,value in before.items():
        expected=value+len(changes.get(name,[]))
        assert after[name]==expected,(name,value,after[name])
        if expected!=value:counters[name]=dict(before=value,after=expected)
    if changes:
        decoded={}
        for name,rows in changes.items():
            decoded[name]={column[1]:cell['raw'] for column,cell in zip(now[name]['columns'],rows[0])}
            assert decoded[name]['id']==after[name]
            assert decoded[name]['study_id']==ORIGINAL.study_id
        revision=decoded['modeling_revisions'];receipt=decoded['modeling_commands']
        assert revision['kind']=='preparation' and receipt['state']=='committed' and receipt['status']==200
        assert receipt['target']==revision['model_id']
        response=json.loads(receipt['response'])
        assert revision['public_id'] in json.dumps(response)
    return dict(additions=changes,sequence_changes=counters)


if __name__=='__main__':
    if len(sys.argv)!=2:raise ValueError('One fixed continuation child mode required')
    app_child(sys.argv[1])
