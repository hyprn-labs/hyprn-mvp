"""Authorized immutable projections of retained native evidence; no model access.

History is the single owner of retained-run reading, and of every read of a run's
association row: ``execution``, ``approach`` and ``result_bindings`` read run rows only
through the functions below, and ``execution`` keeps only the association writes.

- ``run_association(db, run_id, *, study_id=None, payload=True)``: in the caller's
  transaction, the one ``run_associations JOIN outbox`` row read (association columns, outbox
  state and, with ``payload``, the stored payload); ``None`` when absent. Without
  ``study_id`` it reads by run id only (the trusted dispatcher path, never a public read).
- ``last_run_position``, ``runs_by_position``: the study's run insertion positions, for
  position-paged consumers; ``approach_runs``: the runs whose saved configuration revision is
  bound to one approach version, SQL-paged by run id.
- ``History.run_row(db, actor, sid, rid)``: in the caller's transaction, authorize the
  reader, then return the study-scoped ``run_association`` row and its run
  receipt (``None`` when absent). A foreign study or absent run is ``resource_not_found``.
- ``History.read``: the public retained projection; corruption is a partial diagnostic.
- ``History.retained``: the authorized, integrity-checked context ``RetainedRun``.
- ``History.recheck(db, actor, sid, tokens)``: a writing workflow re-proves, in its own
  transaction, that every retained row and receipt it read is unchanged.
- Pure: ``complete_outcome`` (retained outcome completeness, never a re-evaluation) and
  ``retained_read_integrity``.

Nothing here consults the modeling service, current configurations, current evidence or
any current head: a retained run is authenticated by its own stored bytes. Source
eligibility (finished-only scalar sources, deterministic modified-run seeds) belongs to
the consumers ``result_bindings`` and ``modified_runs``, which depend on this module and
never the reverse.

Version interpretation points in this module; none holds its own table:

- ``stored_family`` (used by ``projection`` and ``History.read``): the stored bundle's
  family from ``execution_bundle.bundle_family``, which selects full retained-bundle
  validation, the reported ``history_schema_version`` (absent for history 1) and the
  approach fields. An unlisted bundle version is the ``unsupported_record_version`` partial
  diagnostic; a configuration version the family never carries is
  ``corrupt_retained_record``.
- ``retained_read_integrity``: the closed pairing check against
  ``execution_bundle.RETAINED_PAIRINGS`` (unlisted: ``results_digest=None``), plus the
  ``RunHistory<N>`` contract name and the history-6 polish-envelope identity check.
- ``History.read``: the bundle-8 ``model_schema_version`` manifest field.
- ``complete_outcome``: expected output units from ``units.port_units``.
"""
import base64
import json
import math
import sys
from functools import cache
from importlib.metadata import version as package_version
from pathlib import Path
from typing import NamedTuple
from uuid import UUID, uuid5
from .contracts import DomainError, canonical, check_digest, data_json, digest, raw_hash, validate
from .execution_bundle import (
    MAX_BYTES,
    RETAINED_PAIRINGS,
    RESULT_PAIRINGS,
    result_history_version,
    bundle_layout,
    UnsupportedRetainedVersion,
    bundle_family,
    finite,
    safe_path,
    uses_polish_envelope,
    validate_frozen_configuration,
    validate_retained_bundle,
    validate_scientific_snapshot,
    verify_files,
)
from .units import port_units

ASSOCIATION_KEYS=('store_uuid','process_uuid')

def association(row):
    return {k:row[k] for k in ASSOCIATION_KEYS}

def error(code):
    return dict(code=code,partial=True)

def stored_family(manifest, configuration):
    """The retained family of a stored bundle, from the single table (``bundle_family``).

    An unlisted bundle version raises ``UnsupportedRetainedVersion``; a listed bundle holding
    a configuration version its family never carries raises ``ValueError``. Neither is ever
    projected as another version.
    """
    family=bundle_family(manifest['schema_version'], manifest.get('input_schema_version'))
    if configuration['schema_version']!=family.configuration:
        raise ValueError('Configuration version does not match bundle family')
    return family

def projection(payload, record, expected):
    """Persist only an exact, bounded native read, alongside the existing bundle."""
    if record['request']!=payload['request'] or association(record)!=expected:
        raise ValueError('Retained association mismatch')
    bundle=record['bundle']
    if bundle is not None:
        stored=payload['bundle']
        if bundle['manifest']!=stored['manifest']:
            raise ValueError('Retained manifest mismatch')
        verify_files(bundle['manifest']['files'],bundle['files'])
        if stored_family(bundle['manifest'],payload['frozen']['configuration']).carries_dependencies:
            validate_retained_bundle(bundle,payload['request'],payload['frozen'])
        if set(bundle['files'])!=set(stored['files']) or any(
                raw!=base64.b64decode(stored['files'][path],validate=True) for path,raw in bundle['files'].items()):
            raise ValueError('Retained bytes mismatch')
    result=record['results'];assessment=record['assessment']
    if result is not None and any(result[k]!=payload['request'][k] for k in ('run_id','bundle_digest')):
        raise ValueError('Retained outcome mismatch')
    artifacts=[];total=0
    if len(record['artifacts'])>16:raise ValueError('Retained artifact count exceeded')
    for path,raw in sorted(record['artifacts'].items()):
        safe_path(path)
        if not isinstance(raw,bytes) or len(raw)>131072:raise ValueError('Retained artifact bound')
        total+=len(raw)
        if total>2*1024*1024:raise ValueError('Retained artifact total exceeded')
        artifacts.append(dict(path=path,size=len(raw),sha256=raw_hash(raw),bytes=base64.b64encode(raw).decode()))
    value=dict(schema_version='1',request=record['request'],association=expected,
        bundle_verified=bundle is not None,results=result,assessment=assessment,artifacts=artifacts,errors=record['errors'])
    if len(canonical(value))>4*1024*1024:raise ValueError('Retained projection bound')
    value['digest']=digest(value)
    return value

def stored_request(row,payload,receipt):
    request=payload['request']
    if request!=dict(run_id=row['run_id'],scope=row['study_id'],command_id=row['command_id'],
            payload_digest=receipt['payload_digest'],bundle_digest=payload['bundle']['manifest']['bundle_digest']):
        raise ValueError('Stored immutable request mismatch')
    return request

def validate_binding(row,payload,receipt):
    request=stored_request(row,payload,receipt)
    saved=payload['history'];check_digest(saved)
    if saved['schema_version']!='1':raise ValueError('Unsupported projection version')
    if saved['request']!=request or saved['association']!=association(row):
        raise ValueError('Stored association mismatch')
    return saved


def complete_outcome(result,model,config):
    """Check retained completeness without re-running any criterion evaluation."""
    version = result.get('schema_version')
    fields = {
        'schema_version',
        'run_id',
        'bundle_digest',
        'execution',
        'outputs',
        'artifacts',
    }
    # Results 3 carry no criteria: criteria are evaluated through calculation bindings.
    if version in ('1', '2'):
        fields.add('criteria')
    if version == '1':
        fields |= {'convergence', 'optimization', 'completeness', 'applicability'}
    if version not in ('1', '2', '3') or set(result) != fields:
        raise ValueError('Unsupported outcome')
    definitions={d['definition_version_id']:d for d in model['definitions']}
    units=port_units(model)
    expected={(i['instance_id'],p['port_id']):units[(i['instance_id'],i['definition_version_id'],p['port_id'])] for i in model['instances']
        for p in definitions[i['definition_version_id']]['ports'] if p['direction']=='output'}
    seen=set();available=failed=0
    for output in result['outputs']:
        if (set(output)!={'target','value','units','availability','reason','producer_completed','assigned'}
                or set(output['target'])!={'instance_id','port_id'}):raise ValueError('Invalid output')
        target=(output['target']['instance_id'],output['target']['port_id'])
        if target in seen or target not in expected or output['units']!=expected[target]:raise ValueError('Incomplete output inventory')
        seen.add(target)
        if type(output['producer_completed']) is not bool or type(output['assigned']) is not bool:raise ValueError('Invalid completion')
        failed+=not output['producer_completed']
        if output['availability']=='available':
            if not finite(output['value']) or not output['assigned'] or not output['producer_completed'] or output['reason'] is not None:raise ValueError('Invalid scalar')
            available+=1
        elif (output['availability']!='unavailable' or output['value'] is not None or not isinstance(output['reason'],str)
                or len(output['reason'])>4096):raise ValueError('Invalid missing output')
    if seen != set(expected) or (
        result['execution']['state'] == 'finished' and available != len(expected)
    ):
        raise ValueError('Incomplete outcome')
    if version == '1':
        if (
            any(type(v) is not int for v in result['completeness'].values())
            or result['completeness']
            != dict(
                expected=len(expected),
                available=available,
                failed=failed,
                unavailable=len(expected) - available,
            )
            or result['convergence'] != dict(state='not_applicable', diagnostics_ref=None)
            or result['optimization']
            != dict(termination='not_applicable', feasibility='not_applicable')
            or result['applicability'] != dict(state='unassessed', evidence_refs=[])
        ):
            raise ValueError('Invalid retained facets')
    execution = result['execution']
    if (set(execution) != {'state', 'exit_code', 'message'}
            or execution['state'] not in ('finished', 'failed')
            or type(execution['exit_code']) is not int
            or execution['exit_code'] != (0 if execution['state'] == 'finished' else 1)
            or not isinstance(execution['message'], str) or len(execution['message']) > 4096
            or result['artifacts']):
        raise ValueError('Invalid retained execution')
    if version == '3':
        if 'criteria' in config:raise ValueError('Results 3 require a configuration without criteria')
        return
    if len(result['criteria'])!=len(config['criteria']):raise ValueError('Incomplete criteria')
    for claim,criterion in zip(result['criteria'],config['criteria']):
        if (set(claim)!={'criterion_id','outcome','reason'} or claim['criterion_id']!=criterion['criterion_id']
                or claim['outcome'] not in ('met','violated','unresolved') or not isinstance(claim['reason'],str)
                or len(claim['reason'])>4096):raise ValueError('Invalid retained criterion evaluation')


def execution_summary(state, process_state, exit_status, execution, launcher=None):
    """Execution lifecycle facts, separate from persistence and scientific acceptance."""
    duration = None
    stopped = None
    if launcher:
        try:
            value = data_json(launcher)
            seconds = value['seconds']
            resource = value.get('state')
            if (type(value.get('exit_code')) is not int or not isinstance(resource, dict)
                    or type(resource.get('OOMKilled')) is not bool):
                raise ValueError('Invalid launcher record')
            if type(seconds) in (int, float) and math.isfinite(seconds) and seconds >= 0:
                duration = seconds
            if value['reason'] == 'wall_limit':
                stopped = 'timed_out'
            elif value['reason'] == 'output_limit' or resource['OOMKilled']:
                stopped = 'failed'
        except (ValueError, KeyError, TypeError, OverflowError):
            pass
    outcome = stopped
    if outcome is None and execution in ('finished', 'failed'):
        outcome = 'completed' if execution == 'finished' else 'failed'
    if outcome is None:
        if process_state in ('excepted', 'killed') or exit_status not in (None, 0):
            outcome = 'failed'
        elif process_state == 'running':
            outcome = 'running'
        else:
            outcome = {
                'accepted_run': 'queued', 'prepared': 'ready', 'dispatching': 'starting',
                'preparation_failed': 'preparation_failed', 'uncertain': 'needs_review',
            }.get(state, 'results_unavailable')
    return dict(status=outcome, duration_seconds=duration)


def retained_execution_summary(run, history, read_artifact):
    """Read only the authenticated launcher timing needed by the public summary."""
    raw = None
    artifact = next((a for a in history['artifacts'] if a['name'] == 'result.json'), None)
    if artifact:
        try:
            raw, _ = read_artifact(artifact['artifact_id'])
        except DomainError:
            pass
    result = history.get('results')
    return execution_summary(
        run['state'], run.get('process_state'), run.get('exit_status'),
        result['execution']['state'] if result else None, raw,
    )


def listed_execution_summary(row):
    """Bounded stored lifecycle fields; no whole bundle loading or native service call."""
    raw = None
    if row['launcher']:
        try:
            artifact = json.loads(row['launcher'])
            candidate = base64.b64decode(artifact['bytes'], validate=True)
            if len(candidate) == artifact['size'] and raw_hash(candidate) == artifact['sha256']:
                raw = candidate
        except (ValueError, KeyError, TypeError):
            pass
    return execution_summary(
        row['public_state'], row['process_state'], row['exit_status'], row['execution_state'], raw,
    )


class _RunProjection:
    """Read database-maintained lifecycle fields without loading execution archives."""

    def __init__(self, db):
        self.postgres = getattr(db, 'dialect', None) == 'postgresql'
        # The generated column changes atomically with the canonical source payload.
        self.join = (' CROSS JOIN LATERAL (SELECT x.read_summary AS doc) j '
                     if self.postgres else ' ')

    def value(self, path):
        if self.postgres:
            return "j.doc#>>'{" + path.replace('.', ',') + "}'"
        return "json_extract(x.payload,'$." + path + "')"

    def kind(self, path):
        if self.postgres:
            return "jsonb_typeof(j.doc#>'{" + path.replace('.', ',') + "}')"
        return "json_type(x.payload,'$." + path + "')"

    @property
    def state(self):
        return ("CASE WHEN x.state='accepted_run' THEN COALESCE("
                + "x.preparation_state,x.state) ELSE x.state END AS public_state")

    @property
    def execution(self):
        launcher = (
            "(SELECT value::text FROM jsonb_array_elements(j.doc#>'{history,artifacts}') "
            "WHERE value->>'path'='result.json' LIMIT 1)"
            if self.postgres else
            "(SELECT value FROM json_each(x.payload,'$.history.artifacts') "
            "WHERE json_extract(value,'$.path')='result.json' LIMIT 1)"
        )
        return (self.value('status.process_state') + ' AS process_state,'
                + 'CAST(' + self.value('status.exit_status') + ' AS INTEGER) AS exit_status,'
                + self.value('history.results.execution.state') + ' AS execution_state,'
                + launcher + ' AS launcher,')


class RetainedRecordError(ValueError):
    """A stored retained run failed integrity verification.

    The message is internal. Each consumer maps it to its own public error code and
    never exposes stored text.
    """


class RetainedRun(NamedTuple):
    """One authorized, integrity-checked retained run.

    ``history`` is the ``History.read`` projection, ``payload`` the parsed stored outbox
    payload and ``token`` the ``(run_id, row_digest, receipt_digest)`` witness that
    ``History.recheck`` re-proves at write time.
    """
    history: dict
    payload: dict
    token: dict


class RetainedProjection(NamedTuple):
    """Checked history without embedded file bytes; never used for export or launch."""
    history: dict
    token: dict
    run: dict | None = None


@cache
def _reader_identity():
    """Invalidate persisted admission on application, schema or validator changes."""
    from .contracts import SCHEMA_DIRECTORY
    root = Path(__file__).parent
    files = [(str(p.relative_to(root)), raw_hash(p.read_bytes()))
             for p in sorted(root.rglob('*.py'))]
    schemas = [(p.name, raw_hash(p.read_bytes()))
               for p in sorted(SCHEMA_DIRECTORY.glob('*.json'))]
    return digest(dict(source=files, schemas=schemas, python=list(sys.version_info[:3]),
                       dependencies=raw_hash((root.parents[1] / 'requirements.lock').read_bytes()),
                       validators={n: package_version(n) for n in ('jsonschema', 'rfc8785')}))


# These diagnostics concern optional downloads, not the verified scientific bytes.
# Every other integrity diagnostic fails closed, including future error codes.
_RESULT_IDENTITY_ERRORS = frozenset({'missing_artifacts', 'missing_or_invalid_artifact'})


def retained_read_integrity(run_id, history):
    """Project identity from one authorized History.read result without I/O.

    History owns retained request/association, raw bundle and frozen snapshot
    verification. This public envelope adds no stored digest or source eligibility
    rule: authentic failed outcomes remain inspectable.
    """
    result = dict(schema_version='1', results_digest=None)
    try:
        version = history.get('history_schema_version', '1')
        if version not in {pairing[0] for pairing in RESULT_PAIRINGS}:
            return result
        validate('RunHistory' + version, history)
        if any(e['code'] not in _RESULT_IDENTITY_ERRORS for e in history['errors']):
            return result
        config = history['configuration']; model = history['model_snapshot']
        bundle = history['bundle']; outcomes = history['results']
        if any(v is None for v in (config, model, bundle, outcomes)):
            return result
        # Closed historical pairings (the owner's single table): do not inherit future
        # read-alias additions.
        pair = (version, bundle['schema_version'], config['schema_version'], model['schema_version'])
        if pair not in RESULT_PAIRINGS or version != result_history_version(
            bundle['schema_version'], outcomes['schema_version']
        ):
            return result
        check_digest(config); check_digest(model)
        if (config['digest'] != bundle['configuration_digest']
                or model['digest'] != bundle['model_digest']
                or config['model_id'] != model['model_id']
                or config['model_revision_id'] != model['model_revision_id']
                or outcomes['run_id'] != run_id
                or outcomes['bundle_digest'] != bundle['bundle_digest']):
            return result
        if bundle_layout(bundle) in ('8', '9'):
            closure = history['approach_closure']
            validate_scientific_snapshot(dict(configuration=config, model_snapshot=model, approach_closure=closure))
            if (bundle['model_schema_version'] != model['schema_version']
                    or (bundle_layout(bundle) == '8' and not uses_polish_envelope(model, closure))
                    or bundle['approach_digest'] != (closure['root_approach_digest'] if closure else None)
                    or bundle['approach_closure_digest'] != (closure['digest'] if closure else None)):
                return result
        if bundle_layout(bundle) in ('11', '12'):
            validate_scientific_snapshot(dict(configuration=config, model_snapshot=model))
            if bundle['model_schema_version'] != model['schema_version']:
                return result
        validate(
            {'1': 'RetainedResults', '2': 'RetainedResults2', '3': 'RetainedResults3'}[
                outcomes['schema_version']
            ],
            outcomes,
        )
        # Data-only output/criterion inventory equality, using the single port-units
        # rule (units.port_units): resolved Model3/4 units, exact legacy strings.
        complete_outcome(outcomes, model, config)
        result['results_digest'] = digest(outcomes)
    except (ValueError, KeyError, TypeError, RecursionError, DomainError):
        pass
    return result


def _page_configuration_validator():
    """Same schema/semantic admission, sharing identical subrecords within one page.

    The cache belongs to this read, is bounded, and keys exact JSON bytes including
    numeric types. Failed validations are never cached. No record ID or stored
    digest alone grants a cache hit, and no cache survives an authorization scope.
    """
    from jsonschema import validators
    from .contracts import JsonValidator, validator
    from .execution_bundle import frozen_version

    validated = set()
    retained_bytes = 0
    schema_namespace = None
    reference = JsonValidator.VALIDATORS['$ref']

    def shared_reference(checker, ref, value, schema):
        nonlocal retained_bytes
        key = None
        if isinstance(value, (dict, list)):
            raw = json.dumps(value, sort_keys=True, ensure_ascii=True,
                             allow_nan=False, separators=(',', ':'))
            if len(raw) <= 131072:
                key = (schema_namespace, ref, raw)
                if key in validated:
                    return
        error = next(reference(checker, ref, value, schema), None)
        if error is None and key is not None and len(validated) < 512 and retained_bytes + len(key[2]) <= 4194304:
            validated.add(key)
            retained_bytes += len(key[2])
        if error is not None:
            yield error

    page_validator = validators.extend(JsonValidator, {'$ref': shared_reference})
    compiled = {}

    def check(frozen):
        nonlocal schema_namespace
        version = frozen.get('schema_version')
        # Keep historical formats on their existing admission path. These current
        # wrappers carry repeated model/evidence trees across sampled configurations.
        if version not in ('7', '8'):
            return validate_frozen_configuration(frozen)
        name = 'FrozenConfiguration' + version
        if name not in compiled:
            source = validator(name)
            compiled[name] = page_validator(source.schema, format_checker=source.format_checker)
        schema_namespace = id(compiled[name].schema['$defs'])
        if not compiled[name].is_valid(frozen):
            raise ValueError('Invalid frozen configuration')
        validate_scientific_snapshot(frozen)
        if version != frozen_version(frozen['model_snapshot'], frozen['approach_closure']):
            raise ValueError('Frozen descriptive branch mismatch')

    return check


def configuration_name_projection(raw, sid, revision_id, *, check=validate_frozen_configuration):
    """Read only the exact authorized saved revision; absence is authoritative."""
    try:
        frozen=data_json(raw.encode('utf-8'))
        check(frozen)
        config=frozen['configuration']
        if config['study_id']!=sid or config['configuration_revision_id']!=revision_id:
            raise ValueError('Foreign configuration')
        return config['name']
    except (ValueError,KeyError,TypeError,AttributeError,StopIteration,RecursionError,DomainError):
        return None

def run_association(db,run_id,*,study_id=None,payload=True):
    """The run's association row with its outbox state, read in the caller's transaction.

    ``payload=False`` selects no payload bytes. The caller authorizes first, except the
    trusted dispatcher path, which reads by run id only (``study_id=None``).
    """
    postgres = getattr(db, 'dialect', None) == 'postgresql'
    witness = (",o.payload_sha256 || ':' || x.payload_sha256 || ':' || "
               "COALESCE(x.preparation_state,'') AS payload_witness" if postgres else '')
    row=db.execute('SELECT r.*,x.state,CASE WHEN ? THEN o.payload END AS payload,'
                   'CASE WHEN ? THEN x.payload END AS operational_payload,x.preparation_state' + witness
                   + ' FROM run_associations r JOIN outbox o USING(run_id) JOIN execution_operations x USING(run_id) '
                   'WHERE r.run_id=? AND (CAST(? AS TEXT) IS NULL OR r.study_id=?)',
                   (bool(payload),bool(payload),run_id,study_id,study_id)).fetchone()
    if row is None:return None
    row=dict(row)
    operational = row.pop('operational_payload')
    preparation = row.pop('preparation_state')
    if not payload:
        del row['payload']
        row.pop('payload_witness', None)
    elif operational != '{}' or preparation is not None:
        original = json.loads(row['payload'])
        original.update(json.loads(operational))
        if preparation is not None:
            original['preparation_state'] = preparation
        row['payload'] = json.dumps(original)
    return row

def last_run_position(db,sid):
    """The highest run insertion position of the study (0 when it has no run)."""
    return db.execute('SELECT COALESCE(MAX(rowid),0) FROM run_associations WHERE study_id=?',(sid,)).fetchone()[0]

def runs_by_position(db,sid,low,high,limit):
    """``(rowid, run_id)`` of the study's runs at positions ``low..high``, in insertion order."""
    return db.execute('SELECT rowid,run_id FROM run_associations WHERE study_id=? AND rowid>=? AND rowid<=? ORDER BY rowid LIMIT ?',
                      (sid,low,high,limit)).fetchall()

def approach_runs(db,sid,approach_version_id,after,limit):
    """Bounded run identities whose saved configuration pins this approach version."""
    return db.execute("""SELECT r.run_id,r.configuration_revision_id
        FROM run_associations r JOIN configurations c USING(configuration_revision_id)
        WHERE r.study_id=? AND c.study_id=? AND json_extract(c.payload,'$.configuration.approach_binding.approach_version_id')=?
            AND (CAST(? AS TEXT) IS NULL OR r.run_id>?)
        ORDER BY r.run_id LIMIT ?""",(sid,sid,approach_version_id,after,after,limit)).fetchall()

def calculation_runs(db,sid,configuration_revision_ids,after,limit):
    """``(position, run_id, configuration_revision_id, state)`` of the study's runs of any of
    these configuration versions after insertion position ``after``, in insertion order."""
    return db.execute("""SELECT r.rowid AS position,r.run_id,r.configuration_revision_id,x.state
        FROM run_associations r JOIN execution_operations x USING(run_id)
        WHERE r.study_id=? AND r.rowid>? AND r.configuration_revision_id IN (SELECT value FROM json_each(?))
        ORDER BY r.rowid LIMIT ?""",(sid,after,json.dumps(list(configuration_revision_ids)),limit)).fetchall()

# The light run-status read: at most this many runs per call, and the outcome facets it
# reports from the stored results (the criterion outcomes are reported beside them).
STATUS_RUNS=20
STATUS_FACETS=('execution',)

def canonical_uuid(value):
    try:return isinstance(value,str) and str(UUID(value))==value
    except ValueError:return False

def status_item(row,configuration_name):
    """One light status item from a projected row; an unavailable value is null with its
    reason, never a zero or an empty outcome."""
    recorded=row['results_type'] not in (None,'null')
    def stored(key):
        text=row[key] if recorded else None
        if text is None:return dict(value=None,reason='not_recorded')
        return dict(value=json.loads(text),reason=None)
    return dict(run_id=row['run_id'],configuration_revision_id=row['configuration_revision_id'],
        configuration_name=configuration_name,state=row['public_state'],
        process_state=row['process_state'],exit_status=row['exit_status'],
        facets={k:stored(k) for k in STATUS_FACETS},
        # Results 3 carry no criteria: they are evaluated through calculations, never here.
        criteria=dict(value=None,reason='evaluated_in_calculations') if recorded and row['results_version']=='3' else stored('criteria'),
        times=dict(
            submitted_at=dict(value=row['accepted_at'],reason=None) if row['accepted_at']
                else dict(value=None,reason='not_recorded'),
            started_at=dict(value=None,reason='not_projected'),
            finished_at=dict(value=None,reason='not_projected')))

class History:
    def __init__(self,store):self.store=store

    def retained_projection(self, actor, sid, rid):
        """Reuse full admission, not authority, across hosted process restarts.

        Every hit authenticates the original row's exact bytes, association and
        receipt in the caller's current scope. Cache bytes carry a separate digest
        and validator identity. Missing/damaged caches rebuild from full archives;
        changed source witnesses fail closed. No model or native execution occurs.
        """
        hosted = getattr(getattr(self.store, 'database', None), 'dialect', None) == 'postgresql'
        identity = _reader_identity() if hosted else None
        if hosted:
            with self.store.connection() as db:
                self.store.authorize(db, actor, sid)
                row = db.execute(
                    'SELECT payload,payload_sha256 FROM retained_read_cache '
                    'WHERE study_id=? AND run_id=? AND reader_sha256=?',
                    (sid, rid, identity),
                ).fetchone()
                value = None
                if row and raw_hash(row['payload'].encode('utf-8')) == row['payload_sha256']:
                    try:
                        candidate = data_json(row['payload'].encode('utf-8'))
                        if (set(candidate) == {'history', 'token', 'run'}
                                and candidate['token']['run_id'] == rid
                                and candidate['history']['configuration']['study_id'] == sid
                                and retained_read_integrity(rid, candidate['history'])['results_digest']):
                            run = candidate['run']
                            if (isinstance(run, dict) and run.get('run_id') == rid
                                    and run.get('state') == 'recorded'
                                    and run.get('retained_integrity') ==
                                    retained_read_integrity(rid, candidate['history'])):
                                value = candidate
                    except (ValueError, KeyError, TypeError, DomainError):
                        pass
                if value is not None:
                    self.recheck(db, actor, sid, [value['token']])
                    return RetainedProjection(**value)
        retained = self.retained(actor, sid, rid)
        if not hosted:
            return RetainedProjection(retained.history, retained.token)
        with self.store.connection() as db:
            row, receipt = self.run_row(db, actor, sid, rid, payload=False)
        run = self._submission_projection(actor, sid, row, retained.payload)
        run['retained_integrity'] = retained_read_integrity(rid, retained.history)
        run['execution_summary'] = retained_execution_summary(
            run, retained.history,
            lambda aid: self._read_saved(row, receipt, retained.payload, aid),
        )
        result = RetainedProjection(retained.history, retained.token, run)
        raw = canonical(dict(history=result.history, token=result.token, run=result.run))
        if hosted and len(raw) <= 1048576:
            with self.store.connection(write=True) as db:
                self.recheck(db, actor, sid, [result.token])
                db.execute(
                    'INSERT INTO retained_read_cache VALUES(?,?,?,?,?) '
                    'ON CONFLICT(run_id) DO UPDATE SET reader_sha256=excluded.reader_sha256,'
                    'payload=excluded.payload,payload_sha256=excluded.payload_sha256',
                    (rid, sid, identity, raw.decode('utf-8'), raw_hash(raw)),
                )
        return result

    def public_run(self, actor, sid, rid):
        """Fast verified hosted detail; old/partial records keep diagnostic reads."""
        if getattr(getattr(self.store, 'database', None), 'dialect', None) != 'postgresql':
            return None
        try:
            retained = self.retained_projection(actor, sid, rid)
        except RetainedRecordError:
            return None
        except DomainError as error:
            if error.status in (403, 404) or error.code == 'reference_conflict':
                raise
            return None
        return dict(retained.run, history=retained.history)

    def submission_read(self, actor, sid, rid):
        """Submission state and exact prepared-runtime comparison from retained bytes."""
        with self.store.connection() as db:
            row, _ = self.run_row(db, actor, sid, rid)
            payload = json.loads(row['payload'])
        return self._submission_projection(actor, sid, row, payload)

    def _submission_projection(self, actor, sid, row, payload):
        run_id = row['run_id']
        state = (payload.get('preparation_state', row['state'])
                 if row['state'] == 'accepted_run' else row['state'])
        result = dict(
            run_id=run_id, command_id=row['command_id'], state=state,
            **payload.get('status', {}),
            receipt_url=f"/api/1/studies/{sid}/commands/{row['command_id']}?category=run",
        )
        config = payload.get('frozen', {}).get('configuration', {})
        # Every configuration recording a derivation reports its runtime comparison.
        derivation = (config.get('derivation')
                      if config.get('schema_version') in ('2', '3', '4', '6') else None)
        if derivation:
            from .readiness import runtime_identity, runtime_comparison, compare_runtimes
            try:
                check_digest(config)
                source = runtime_identity(derivation['source_runtime'])
            except (ValueError, TypeError, KeyError):
                # The full history reader retains corrupt source diagnostics.
                return result
            if 'bundle' not in payload:
                result['runtime_comparison'] = runtime_comparison(self.store, actor, sid, source)
            else:
                current = None
                try:
                    bundle = dict(
                        manifest=payload['bundle']['manifest'],
                        files={p: base64.b64decode(b, validate=True)
                               for p, b in payload['bundle']['files'].items()},
                    )
                    validate_retained_bundle(bundle, payload['request'], payload['frozen'])
                    current = runtime_identity(bundle['manifest']['runtime'])
                except (ValueError, TypeError, KeyError):
                    pass
                # Never replace a missing prepared identity with today's runtime.
                result['runtime_comparison'] = compare_runtimes(
                    source, current, basis='prepared_bundle',
                )
        return result

    def list(self,actor,sid):
        # No SQLite statement may stay open while Python validates a frozen
        # configuration. In rollback-journal mode an open read keeps SHARED, so every
        # writer's COMMIT (the executor's claim) waits on the whole projection, and new
        # readers queue behind that pending writer. Each statement below is exhausted
        # before any projection runs.
        with self.store.connection() as db:
            self.store.authorize(db,actor,sid)
            # Project only the public state before sorting. Full payloads contain
            # retained bundles and can exhaust bounded SQLite temporary storage.
            projection = _RunProjection(db)
            rows = db.execute(
                "SELECT " + projection.execution + "r.run_id,r.configuration_revision_id,r.command_id,"
                + projection.state + ' FROM run_associations r JOIN execution_operations x USING(run_id) '
                + projection.join + 'WHERE r.study_id=? ORDER BY r.rowid', (sid,),
            ).fetchall()
            contexts=self._contexts(db,sid,rows)
        return [dict(run_id=r['run_id'],configuration_revision_id=r['configuration_revision_id'],command_id=r['command_id'],
                     state=r['public_state'],configuration_name=contexts[r['configuration_revision_id']],
                     execution_summary=listed_execution_summary(r)) for r in rows]

    def list_page(self, actor, sid, *, cursor=None, limit=100, model_id=None, model_revision_id=None, newest_first=False):
        from .listing import window
        with self.store.connection() as db:
            self.store.authorize(db, actor, sid)
            clauses, values = ['c.study_id=?'], [sid]
            for key, value in [('model_id', model_id), ('model_revision_id', model_revision_id)]:
                if value:
                    clauses.append(f"EXISTS (SELECT 1 FROM configurations f WHERE f.study_id=c.study_id AND f.configuration_revision_id=c.configuration_revision_id AND json_extract(f.payload,'$.configuration.{key}')=?)")
                    values.append(value)
            where, values, order = window(db, 'run_associations', 'run_id', clauses, values, cursor, limit, descending=newest_first)
            projection = _RunProjection(db)
            rows = db.execute(
                "SELECT " + projection.execution + "c.run_id,c.configuration_revision_id,c.command_id,"
                + projection.state + ' FROM run_associations c JOIN execution_operations x USING(run_id) '
                + projection.join + f'WHERE {where} ORDER BY c.rowid {order} LIMIT ?',
                (*values, limit + 1),
            ).fetchall()
            more = len(rows) > limit
            rows = rows[:limit]
            contexts = self._contexts(db, sid, rows)
        result = [dict(run_id=r['run_id'], configuration_revision_id=r['configuration_revision_id'], command_id=r['command_id'],
                       state=r['public_state'], configuration_name=contexts[r['configuration_revision_id']],
                       execution_summary=listed_execution_summary(r)) for r in rows]
        return result, rows[-1]['run_id'] if more else None

    @staticmethod
    def _contexts(db,sid,rows):
        # One bounded serialized configuration in memory at a time. No outbox
        # bundle/history bytes, current heads or per-run service reads.
        contexts={}
        check = _page_configuration_validator()
        payload_bytes = ('octet_length(payload)' if getattr(db, 'dialect', None) == 'postgresql'
                         else 'length(CAST(payload AS BLOB))')
        for r in rows:
            revision=r['configuration_revision_id']
            if revision in contexts:continue
            config=db.execute(
                f'SELECT CASE WHEN {payload_bytes}<=? THEN payload ELSE NULL END '
                'AS payload '
                'FROM configurations WHERE study_id=? AND configuration_revision_id=?',
                (MAX_BYTES,sid,revision)).fetchall()
            contexts[revision]=(configuration_name_projection(config[0]['payload'],sid,revision,check=check) if config
                                else None)
        return contexts

    def status(self,actor,sid,run_ids):
        """The light status of 1 to 20 distinct runs of the study, in request order.

        One authorization and one statement over the association, the outbox state and the
        stored status and result paths (``json_extract``), so no payload is loaded or decoded
        whole; the configuration name is the run list's. Facets and criterion outcomes are
        the stored results as they are, each null with ``not_recorded`` while the run has no
        retained results. The only time HYPRN MVP owns is the acceptance time; the process
        start and finish times are held by the execution engine and not projected
        (``not_projected``). Nothing is verified, recomputed or read from the engine here: the
        full run read stays the integrity-checked record.
        """
        with self.store.connection() as db:
            self.store.authorize(db,actor,sid)
            if (not isinstance(run_ids,(list,tuple)) or not 1<=len(run_ids)<=STATUS_RUNS
                    or len(set(run_ids))!=len(run_ids) or not all(map(canonical_uuid,run_ids))):
                raise DomainError('invalid_request',400)
            projection = _RunProjection(db)
            rows=db.execute(
                "SELECT r.run_id,r.configuration_revision_id,r.accepted_at,"
                + projection.state + ','
                + projection.value('status.process_state') + ' AS process_state,'
                + 'CAST(' + projection.value('status.exit_status') + ' AS INTEGER) AS exit_status,'
                + projection.kind('history.results') + ' AS results_type,'
                + projection.value('history.results.schema_version') + ' AS results_version,'
                + ','.join(projection.value('history.results.' + k) + ' AS ' + k
                           for k in (*STATUS_FACETS, 'criteria'))
                + ' FROM run_associations r JOIN execution_operations x USING(run_id) '
                + projection.join + 'WHERE r.study_id=? AND r.run_id IN ('
                + ','.join('?' * len(run_ids)) + ')', (sid, *run_ids),
            ).fetchall()
            # Every id must be a run of this study: no partial answer.
            if len(rows)!=len(run_ids):raise DomainError('resource_not_found',404)
            contexts=self._contexts(db,sid,rows)
        by_id={r['run_id']:r for r in rows}
        return [status_item(by_id[rid],contexts[by_id[rid]['configuration_revision_id']])
                for rid in run_ids]

    def run_row(self,db,actor,sid,rid,*,payload=True):
        """Authorize, then read the study-scoped run row and its run receipt in ``db``.

        The caller holds the connection and therefore the transaction. The receipt is
        ``None`` when absent; the caller judges integrity, nothing is repaired here.
        """
        self.store.authorize(db,actor,sid)
        row=run_association(db,rid,study_id=sid,payload=payload)
        if row is None:raise DomainError('resource_not_found',404)
        return row,self.store.command_receipt(db,sid,'run',row['command_id'])

    def retained(self,actor,sid,rid,*,admit=None):
        """Authorized retained run context, verified from its own stored bytes only.

        Order: authorize and read the row and receipt; refuse a run that is not
        ``recorded`` (``record_not_ready`` 409); call ``admit(payload)`` on the parsed
        stored payload, so that a consumer's explicit refusal of records it never
        accepts (for example an unsupported configuration version) is not masked by an
        integrity failure; verify the native association, the immutable request and
        projection binding, the verified bundle and complete ``History.read`` projection,
        then the frozen configuration and model against the bundle manifest and the
        retained outcome; finally re-read the row and receipt in a new transaction and
        refuse any change (``reference_conflict`` 409).

        Errors: ``resource_not_found`` 404 (unauthorized reader, foreign study, absent
        run), ``record_not_ready``, ``reference_conflict``, a contract ``DomainError`` when
        the retained configuration or model fails today's read contract, whatever
        ``admit`` raises, and ``RetainedRecordError`` for every integrity failure. Outcome
        eligibility (terminal state, exit code, completeness) is the consumer's decision:
        failed outcomes stay readable here.
        """
        with self.store.connection() as db:
            row,receipt=self.run_row(db,actor,sid,rid)
            compact_witness = getattr(db, 'dialect', None) == 'postgresql'
        if row['state']!='recorded':raise DomainError('record_not_ready',409)
        try:
            payload=json.loads(row['payload'])
        except (ValueError,TypeError,RecursionError) as exc:
            raise RetainedRecordError('Unreadable retained payload') from exc
        if admit is not None:admit(payload)
        try:
            if not row['store_uuid'] or not row['process_uuid']:raise ValueError('Native association missing')
            saved=validate_binding(row,payload,receipt)
            history=self._read_saved(row,receipt,payload)
            if history['errors'] or not saved['bundle_verified'] or history['configuration'] is None:
                raise ValueError('Incomplete retained record')
        except (ValueError,KeyError,TypeError,OverflowError,RecursionError) as exc:
            raise RetainedRecordError('Retained binding invalid') from exc
        config=history['configuration'];model=history['model_snapshot'];results=history['results']
        validate('ConfigurationRevisionRead6',config);validate('ModelRevisionRead5',model)
        try:
            if results is None:raise ValueError('Retained outcome missing')
            check_digest(config);check_digest(model)
            manifest=payload['bundle']['manifest']
            if (config['digest']!=manifest['configuration_digest'] or model['digest']!=manifest['model_digest']
                    or config['model_id']!=model['model_id'] or config['model_revision_id']!=model['model_revision_id']
                    or results['run_id']!=rid or results['bundle_digest']!=manifest['bundle_digest']):
                raise ValueError('Retained identity mismatch')
            token=dict(run_id=rid,receipt_digest=digest(receipt))
            if compact_witness:
                token['row_fingerprint'] = digest(
                    dict(row, payload=row['payload_witness'])
                )
            else:
                token['row_digest'] = digest(row)
        except (ValueError,KeyError,TypeError,OverflowError,RecursionError) as exc:
            raise RetainedRecordError('Retained identity invalid') from exc
        with self.store.connection() as db:
            self.recheck(db,actor,sid,[token])
        return RetainedRun(history,payload,token)

    def recheck(self,db,actor,sid,tokens):
        """In the caller's transaction, refuse when any retained row or receipt changed."""
        if (tokens and getattr(db, 'dialect', None) == 'postgresql'
                and all('row_fingerprint' in token for token in tokens)):
            self.store.authorize(db, actor, sid)
            ids = list(dict.fromkeys(token['run_id'] for token in tokens))
            rows = db.execute(
                "SELECT r.*,x.state,o.payload_sha256 || ':' || x.payload_sha256 || ':' || "
                "COALESCE(x.preparation_state,'') AS payload,"
                "o.payload_sha256 || ':' || x.payload_sha256 || ':' || COALESCE(x.preparation_state,'') AS payload_witness "
                'FROM run_associations r JOIN outbox o USING(run_id) JOIN execution_operations x USING(run_id) '
                'WHERE r.study_id=? AND r.run_id IN (' + ','.join('?' * len(ids)) + ')',
                (sid, *ids),
            ).fetchall()
            by_id = {row['run_id']: row for row in rows}
            if len(by_id) != len(ids):
                raise DomainError('resource_not_found', 404)
            receipts = self.store.command_receipts(
                db, sid, 'run', [row['command_id'] for row in rows]
            )
            for token in tokens:
                row = by_id[token['run_id']]
                receipt = receipts.get(row['command_id'])
                if (digest(dict(row)) != token['row_fingerprint']
                        or digest(receipt) != token['receipt_digest']):
                    raise DomainError('reference_conflict', 409)
            return
        for token in tokens:
            row,receipt=self.run_row(db,actor,sid,token['run_id'])
            if digest(row)!=token['row_digest'] or digest(receipt)!=token['receipt_digest']:
                raise DomainError('reference_conflict',409)

    def read(self,actor,sid,run_id,artifact_id=None):
        with self.store.connection() as db:
            row,receipt=self.run_row(db,actor,sid,run_id)
            payload=json.loads(row['payload'])
        return self._read_saved(row,receipt,payload,artifact_id)

    def _read_saved(self,row,receipt,payload,artifact_id=None):
        """Project already authorized bytes; retained readers recheck before returning."""
        run_id = row['run_id']
        sid = row['study_id']
        value=dict(configuration=None,model_snapshot=None,context=None,evidence=None,
                   bundle=None,results=None,assessment=None,artifacts=[],errors=[])
        downloads={}
        try:
            if 'history' not in payload:
                value['errors']=[error('history_not_recorded')]
            else:
                saved=validate_binding(row,payload,receipt)
                value.update(results=saved['results'],assessment=saved['assessment'],errors=list(saved['errors']))
                if saved['bundle_verified']:
                    bundle=payload['bundle'];manifest=bundle['manifest'];check_digest(manifest,'bundle_digest')
                    if len(canonical(bundle))>2*MAX_BYTES:raise ValueError('Stored bundle bound')
                    files={p:base64.b64decode(b,validate=True) for p,b in bundle['files'].items()}
                    verify_files(manifest['files'],files)
                    family=stored_family(manifest,payload['frozen']['configuration'])
                    if family.carries_dependencies:
                        validate_retained_bundle(dict(manifest=manifest,files=files),payload['request'],payload['frozen'])
                    config=data_json(files['configuration.json']);model=data_json(files['model.json'])
                    if (config!=payload['frozen']['configuration'] or model!=payload['frozen']['model_snapshot']
                        or config['study_id']!=sid or config['configuration_revision_id']!=row['configuration_revision_id']
                        or files['context.json']!=canonical(config['context_snapshot'])
                        or files['evidence/index.json']!=canonical(config['evidence_snapshots'])):
                        raise ValueError('Stored scientific snapshot mismatch')
                    value.update(configuration=config,model_snapshot=model,context=config['context_snapshot'],evidence=config['evidence_snapshots'],
                        bundle={k:manifest[k] for k in ('schema_version','bundle_digest','model_digest','configuration_digest','dependencies')})
                    if manifest['schema_version'] in ('10', '11', '12'):
                        value['bundle']['input_schema_version'] = manifest['input_schema_version']
                    # History 1 is the absent field (RunHistory1 has none).
                    history_version = (
                        result_history_version(
                            manifest['schema_version'], saved['results']['schema_version']
                        )
                        if saved['results'] is not None
                        else result_history_version(
                            manifest['schema_version'], manifest.get('result_protocol_version', '1')
                        )
                    )
                    if history_version != '1':value['history_schema_version'] = history_version
                    if family.carries_approach:
                        value['approach_closure']=payload['frozen']['approach_closure']
                        value['bundle'].update({k:manifest[k] for k in ('approach_digest','approach_closure_digest')})
                    if bundle_layout(manifest) in ('8', '9', '11', '12'):
                        value['bundle']['model_schema_version'] = manifest['model_schema_version']
                    for f in manifest['files']:
                        self._artifact(value,downloads,run_id,'bundle',f['path'],files[f['path']],f.get('role','bundle'))
                for f in saved['artifacts']:
                    raw=base64.b64decode(f['bytes'],validate=True)
                    if len(raw)!=f['size'] or raw_hash(raw)!=f['sha256']:raise ValueError('Stored artifact mismatch')
                    self._artifact(value,downloads,run_id,'retrieved',f['path'],raw,'retrieved')
        except (ValueError,KeyError,TypeError,RecursionError,DomainError) as exc:
            # An unlisted stored bundle version is unsupported, distinct from corruption;
            # neither is read as another version.
            code='unsupported_record_version' if isinstance(exc,UnsupportedRetainedVersion) else 'corrupt_retained_record'
            value=dict(configuration=None,model_snapshot=None,context=None,evidence=None,
                       bundle=None,results=None,assessment=None,artifacts=[],errors=[error(code)])
            downloads={}
        if (
            value['bundle'] is None
            and value['results'] is not None
            and value['results']['schema_version'] == '2'
        ):
            value.update(history_schema_version='7', approach_closure=None)
        if (
            value['bundle'] is None
            and value['results'] is not None
            and value['results']['schema_version'] == '3'
        ):
            value['history_schema_version'] = (
                '9' if (value.get('model_snapshot') or {}).get('schema_version') == '5' else '8'
            )
        # History 8 has no criterion evaluator identity: configurations carry no criteria.
        if value.get('history_schema_version') in ('8', '9'):
            if value.pop('assessment') is not None:
                value = dict(value, configuration=None, model_snapshot=None, context=None,
                    evidence=None, bundle=None, results=None, artifacts=[],
                    errors=[error('corrupt_retained_record')])
                downloads = {}
        if artifact_id is not None:
            if artifact_id not in downloads:
                if value['errors'] and not value['artifacts']:raise DomainError(value['errors'][0]['code'],409)
                raise DomainError('resource_not_found',404)
            return downloads[artifact_id]
        return value

    @staticmethod
    def _artifact(value,downloads,run_id,origin,path,raw,role):
        safe_path(path)
        aid=str(uuid5(UUID(run_id),origin+':'+path))
        descriptor=dict(artifact_id=aid,name=path,role=role,size=len(raw),sha256=raw_hash(raw),media_type='application/octet-stream')
        value['artifacts'].append(descriptor);downloads[aid]=(raw,descriptor)
