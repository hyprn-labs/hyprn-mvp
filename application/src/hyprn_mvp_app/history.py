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
  bound to one approach version (and case), SQL-paged by run id.
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
        'criteria',
        'artifacts',
    }
    if version == '1':
        fields |= {'convergence', 'optimization', 'completeness', 'applicability'}
    if version not in ('1', '2') or set(result) != fields:
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
    if len(result['criteria'])!=len(config['criteria']):raise ValueError('Incomplete criteria')
    for claim,criterion in zip(result['criteria'],config['criteria']):
        if (set(claim)!={'criterion_id','outcome','reason'} or claim['criterion_id']!=criterion['criterion_id']
                or claim['outcome'] not in ('met','violated','unresolved') or not isinstance(claim['reason'],str)
                or len(claim['reason'])>4096):raise ValueError('Invalid retained criterion evaluation')


def execution_diagnostic(history, read_artifact):
    """Curated launcher metadata from authenticated retained bytes, never worker stdout."""
    result = dict(
        state='unavailable',
        message='Execution diagnostics are unavailable.',
        wall_seconds=None,
        elapsed_seconds=None,
        artifact_id=None,
    )
    artifact = next((a for a in history['artifacts'] if a['name'] == 'result.json'), None)
    if artifact is None:
        return result
    try:
        raw, _ = read_artifact(artifact['artifact_id'])
        value = data_json(raw)
        reason = value['reason']
        elapsed = value['seconds']
        wall = value.get('wall_seconds')
        from .contracts import execution_wall_seconds

        if wall is not None:
            execution_wall_seconds(wall)
        if type(elapsed) not in (float, int) or not math.isfinite(elapsed) or elapsed < 0:
            return result
        if type(value['exit_code']) is not int:
            return result
        state = value.get('state')
        if not isinstance(state, dict) or type(state.get('OOMKilled')) is not bool:
            return result
        if reason == 'wall_limit':
            outcome = 'timed_out'
            message = (
                'Execution timed out'
                + (f' after reaching the {wall}-second wall budget' if wall is not None else '')
                + '. No numerical results were produced.'
            )
        elif reason == 'output_limit':
            outcome = 'output_limit'
            message = 'Execution stopped after exceeding the output limit.'
        elif reason == 'exited' and state['OOMKilled']:
            outcome = 'memory_limit'
            message = 'Execution stopped after exceeding the memory limit.'
        elif reason == 'exited':
            outcome = 'completed' if value['exit_code'] == 0 else 'failed'
            message = (
                'Worker exited normally.'
                if outcome == 'completed'
                else 'Worker exited with an error.'
            )
        else:
            return result
        return dict(
            state=outcome,
            message=message,
            wall_seconds=wall,
            elapsed_seconds=elapsed,
            artifact_id=artifact['artifact_id'],
        )
    except (ValueError, KeyError, TypeError, OverflowError, DomainError):
        return result


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
        validate(
            'RetainedResults' if outcomes['schema_version'] == '1' else 'RetainedResults2', outcomes
        )
        # Data-only output/criterion inventory equality, using the single port-units
        # rule (units.port_units): resolved Model3/4 units, exact legacy strings.
        complete_outcome(outcomes, model, config)
        result['results_digest'] = digest(outcomes)
    except (ValueError, KeyError, TypeError, RecursionError, DomainError):
        pass
    return result


def case_projection(raw, sid, revision_id):
    """Read only the exact authorized saved revision; absence is authoritative."""
    try:
        frozen=data_json(raw.encode('utf-8'))
        validate_frozen_configuration(frozen)
        config=frozen['configuration']
        if config['study_id']!=sid or config['configuration_revision_id']!=revision_id:
            raise ValueError('Foreign configuration')
        pin=config.get('approach_binding')
        if pin is None:return config['name'],dict(state='unlinked')
        closure=frozen['approach_closure']
        version=next(v for v in closure['approach_versions'] if v['approach_version_id']==pin['approach_version_id'])
        case=next((c for c in version['content']['cases'] if c['case_id']==pin['case_id']),None)
        return config['name'],dict(state='linked',approach_id=pin['approach_id'],
            approach_version_id=pin['approach_version_id'],version_number=version['version_number'],
            case_id=pin['case_id'],case_name=case['title'] if case else None)
    except (ValueError,KeyError,TypeError,AttributeError,StopIteration,RecursionError,DomainError):
        return None,dict(state='unavailable')

def run_association(db,run_id,*,study_id=None,payload=True):
    """The run's association row with its outbox state, read in the caller's transaction.

    ``payload=False`` selects no payload bytes. The caller authorizes first, except the
    trusted dispatcher path, which reads by run id only (``study_id=None``).
    """
    row=db.execute('SELECT r.*,o.state,CASE WHEN ? THEN o.payload END AS payload FROM run_associations r JOIN outbox o USING(run_id) '
                   'WHERE r.run_id=? AND (? IS NULL OR r.study_id=?)',(bool(payload),run_id,study_id,study_id)).fetchone()
    if row is None:return None
    row=dict(row)
    if not payload:del row['payload']
    return row

def last_run_position(db,sid):
    """The highest run insertion position of the study (0 when it has no run)."""
    return db.execute('SELECT COALESCE(MAX(rowid),0) FROM run_associations WHERE study_id=?',(sid,)).fetchone()[0]

def runs_by_position(db,sid,low,high,limit):
    """``(rowid, run_id)`` of the study's runs at positions ``low..high``, in insertion order."""
    return db.execute('SELECT rowid,run_id FROM run_associations WHERE study_id=? AND rowid>=? AND rowid<=? ORDER BY rowid LIMIT ?',
                      (sid,low,high,limit)).fetchall()

def approach_runs(db,sid,approach_version_id,case_id,after,limit):
    """Runs of the study whose saved configuration revision is bound to the approach version
    (and to ``case_id`` when given), ordered by run id after ``after``, at most ``limit``:
    ``run_id``, ``configuration_revision_id`` and the bound ``case_id``. Only the small pin
    projection is read, never a payload."""
    return db.execute('''SELECT r.run_id,r.configuration_revision_id,
            json_extract(c.payload,'$.configuration.approach_binding.case_id') AS case_id
        FROM run_associations r JOIN configurations c USING(configuration_revision_id)
        WHERE r.study_id=? AND c.study_id=? AND json_extract(c.payload,'$.configuration.approach_binding.approach_version_id')=?
            AND (? IS NULL OR json_extract(c.payload,'$.configuration.approach_binding.case_id')=?) AND (? IS NULL OR r.run_id>?)
        ORDER BY r.run_id LIMIT ?''',(sid,sid,approach_version_id,case_id,case_id,after,after,limit)).fetchall()

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
        facets={k:stored(k) for k in STATUS_FACETS},criteria=stored('criteria'),
        times=dict(
            submitted_at=dict(value=row['accepted_at'],reason=None) if row['accepted_at']
                else dict(value=None,reason='not_recorded'),
            started_at=dict(value=None,reason='not_projected'),
            finished_at=dict(value=None,reason='not_projected')))

class History:
    def __init__(self,store):self.store=store

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
            rows = db.execute(
                "SELECT r.run_id,r.configuration_revision_id,r.command_id,CASE WHEN o.state='accepted_run' THEN COALESCE(json_extract(o.payload,'$.preparation_state'),o.state) ELSE o.state END AS public_state "
                'FROM run_associations r JOIN outbox o USING(run_id) WHERE r.study_id=? ORDER BY r.rowid',(sid,)).fetchall()
            contexts=self._contexts(db,sid,rows)
        return [dict(run_id=r['run_id'],configuration_revision_id=r['configuration_revision_id'],command_id=r['command_id'],
                     state=r['public_state'],configuration_name=contexts[r['configuration_revision_id']][0],
                     case_context=contexts[r['configuration_revision_id']][1]) for r in rows]

    @staticmethod
    def _contexts(db,sid,rows):
        # One bounded serialized configuration in memory at a time. No outbox
        # bundle/history bytes, current heads or per-run service reads.
        contexts={}
        for r in rows:
            revision=r['configuration_revision_id']
            if revision in contexts:continue
            config=db.execute(
                'SELECT CASE WHEN length(CAST(payload AS BLOB))<=? THEN payload ELSE NULL END '
                'AS payload '
                'FROM configurations WHERE study_id=? AND configuration_revision_id=?',
                (MAX_BYTES,sid,revision)).fetchall()
            contexts[revision]=(case_projection(config[0]['payload'],sid,revision) if config
                                else (None,dict(state='unavailable')))
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
            rows=db.execute(
                "SELECT r.run_id,r.configuration_revision_id,r.accepted_at,"
                "CASE WHEN o.state='accepted_run' THEN "
                "COALESCE(json_extract(o.payload,'$.preparation_state'),o.state) "
                "ELSE o.state END AS public_state,"
                "json_extract(o.payload,'$.status.process_state') AS process_state,"
                "json_extract(o.payload,'$.status.exit_status') AS exit_status,"
                "json_type(o.payload,'$.history.results') AS results_type,"
                +','.join(f"json_extract(o.payload,'$.history.results.{k}') AS {k}"
                          for k in (*STATUS_FACETS,'criteria'))+
                ' FROM run_associations r JOIN outbox o USING(run_id) '
                'WHERE r.study_id=? AND r.run_id IN ('
                +','.join('?'*len(run_ids))+')',(sid,*run_ids)).fetchall()
            # Every id must be a run of this study: no partial answer.
            if len(rows)!=len(run_ids):raise DomainError('resource_not_found',404)
            contexts=self._contexts(db,sid,rows)
        by_id={r['run_id']:r for r in rows}
        return [status_item(by_id[rid],contexts[by_id[rid]['configuration_revision_id']][0])
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
        if row['state']!='recorded':raise DomainError('record_not_ready',409)
        try:
            payload=json.loads(row['payload'])
        except (ValueError,TypeError,RecursionError) as exc:
            raise RetainedRecordError('Unreadable retained payload') from exc
        if admit is not None:admit(payload)
        try:
            if not row['store_uuid'] or not row['process_uuid']:raise ValueError('Native association missing')
            saved=validate_binding(row,payload,receipt)
            history=self.read(actor,sid,rid)
            if history['errors'] or not saved['bundle_verified'] or history['configuration'] is None:
                raise ValueError('Incomplete retained record')
        except (ValueError,KeyError,TypeError,OverflowError,RecursionError) as exc:
            raise RetainedRecordError('Retained binding invalid') from exc
        config=history['configuration'];model=history['model_snapshot'];results=history['results']
        validate('ConfigurationRevision',config);validate('ModelRevisionRead4',model)
        try:
            if results is None:raise ValueError('Retained outcome missing')
            check_digest(config);check_digest(model)
            manifest=payload['bundle']['manifest']
            if (config['digest']!=manifest['configuration_digest'] or model['digest']!=manifest['model_digest']
                    or config['model_id']!=model['model_id'] or config['model_revision_id']!=model['model_revision_id']
                    or results['run_id']!=rid or results['bundle_digest']!=manifest['bundle_digest']):
                raise ValueError('Retained identity mismatch')
            token=dict(run_id=rid,row_digest=digest(row),receipt_digest=digest(receipt))
        except (ValueError,KeyError,TypeError,OverflowError,RecursionError) as exc:
            raise RetainedRecordError('Retained identity invalid') from exc
        with self.store.connection() as db:
            self.recheck(db,actor,sid,[token])
        return RetainedRun(history,payload,token)

    def recheck(self,db,actor,sid,tokens):
        """In the caller's transaction, refuse when any retained row or receipt changed."""
        for token in tokens:
            row,receipt=self.run_row(db,actor,sid,token['run_id'])
            if digest(row)!=token['row_digest'] or digest(receipt)!=token['receipt_digest']:
                raise DomainError('reference_conflict',409)

    def read(self,actor,sid,run_id,artifact_id=None):
        with self.store.connection() as db:
            row,receipt=self.run_row(db,actor,sid,run_id)
            payload=json.loads(row['payload'])
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
                    if manifest['schema_version'] == '10':
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
                    if bundle_layout(manifest) in ('8', '9'):
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
