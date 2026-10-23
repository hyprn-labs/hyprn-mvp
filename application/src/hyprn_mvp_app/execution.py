"""Submission orchestration: static preparation, durable receipt/outbox and dispatch.

The frozen bundle contract (assembly and every admission check) lives in
``execution_bundle``; this module owns only ``StaticPreparation`` and ``Submissions``.
Candidate bytes remain inert here.
"""
import base64
from collections import OrderedDict
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from .contracts import DomainError, canonical, check_digest, uid
from .execution_bundle import (MAX_BYTES, assemble_bundle, closed, safe_path, uses_polish_envelope,
                               validate_frozen_configuration, validate_preparation, validate_retained_bundle)
from .history import History, association, projection, run_association, stored_request
from .result_bindings import ResultBindings
from .scientific_configuration import project_scientific_configuration
# Temporary forwarding aliases for test imports only; production code
# imports these from their owner (application/tests/test_module_boundaries.py).
from .contracts import data_json, raw_hash
from .execution_bundle import (MAX_FILES, executable_digest, frozen_version, model_capabilities, port_key,
                               unique, uses_typed_units, uses_units_envelope, validate_approach_binding,
                               validate_assumption_closure, validate_bundle_shape, validate_provenance,
                               validate_scientific_snapshot, validate_unit_catalog, verify_files)

class StaticPreparation:
    def __init__(self,model):
        self.model=model
        # Inert bytes only: never cache authority, manifests, validation or results.
        # The dispatcher serializes calls; eviction/restart simply downloads again.
        self._files=OrderedDict()
        self._file_bytes=0
    def __call__(self,actor,sid,command,frozen):
        from uuid import UUID,uuid5
        validate_frozen_configuration(frozen)
        if uses_polish_envelope(frozen['model_snapshot'],frozen.get('approach_closure')):
            status,response=self.model.call(actor,sid,'GET','/capabilities',response_schema='CapabilitiesResponseRead4',resources=[sid])
            from .readiness import supports_descriptive_execution
            if status!=200 or not supports_descriptive_execution(response.get('data'),frozen['model_snapshot']):
                raise ValueError('Modeling backend lacks exact descriptive execution support')
        config=project_scientific_configuration(frozen['configuration']);mid=config['model_id']
        # Separate from public run/authoring commands; stable across crashes.
        private_command=str(uuid5(UUID(command),'hyprn_mvp.prepare.artifact3:'+sid))
        body=dict(command_id=private_command,model_revision_id=config['model_revision_id'],
                  configuration_snapshot=config,configuration_digest=config['digest'])
        _,response=self.model.call(actor,sid,'POST',f'/models/{mid}/prepare-execution',body,
            request_schema='Prepare2' if config['schema_version']=='5' else 'Prepare',resources=[mid])
        if set(response)!={'data'} or not isinstance(response['data'],dict):raise ValueError('Invalid preparation response')
        prepared=response['data']
        if prepared.get('schema_version') not in ('2', '3', '4', '5'):
            raise ValueError('Unsupported preparation version; create a new schema2 run command')
        closed('PreparedModelArtifactRead5',prepared)
        # A configuration without criteria runs only under result protocol 3, and only it does.
        if (prepared['schema_version'] in ('4','5'))!=(config['schema_version']=='5'):
            raise ValueError('Preparation does not match the configuration version')
        if len({f['file_id'] for f in prepared['files']})!=len(prepared['files']):raise ValueError('Duplicate file identity')
        files={};total=0
        for item in prepared['files']:
            path=safe_path(item['path'])
            if path in files:raise ValueError('Duplicate prepared file')
            key=(actor,sid,item['sha256'],item['size'],item['media_type'])
            raw=self._files.get(key)
            if raw is None:
                file_path=f"/preparations/{prepared['preparation_id']}/files/{item['file_id']}"
                _,response=self.model.call(actor,sid,'GET',file_path,
                    response_schema='ByteFileResponse',resources=[mid])
                raw=base64.b64decode(response['data']['bytes'],validate=True)
                if (response['data']['sha256']!=item['sha256']
                        or response['data']['media_type']!=item['media_type']):
                    raise ValueError('Prepared file mismatch')
            total+=len(raw)
            if total>MAX_BYTES:
                raise ValueError('Prepared file mismatch')
            files[path]=raw
        validate_preparation(prepared,files,frozen)
        # Populate only after complete hash, size, model and input-binding validation.
        for item in prepared['files']:
            key=(actor,sid,item['sha256'],item['size'],item['media_type'])
            raw=files[item['path']]
            if key not in self._files:
                self._files[key]=raw
                self._file_bytes+=len(raw)
            self._files.move_to_end(key)
            while self._file_bytes>MAX_BYTES or len(self._files)>MAX_FILES:
                _,removed=self._files.popitem(last=False)
                self._file_bytes-=len(removed)
        return prepared,files

class Submissions:
    """Durable app receipt/outbox plus one serialized native boundary crossing.

    No lease or retry may turn an uncertain claim back into accepted_run. A
    stored process is adopted only by immutable exact inputs, never by age/name.
    The actual runner owns lifecycle; this class stores only its association.
    """
    def __init__(self,store,prepare,native):
        self.store,self.prepare,self.native=store,prepare,native
        self.fault=lambda point:None

    def submit(self,actor,sid,body,*,expected_runtime=None,admission_limit=None):
        command=body['command_id'];revision=body['configuration_revision_id']
        payload=dict(operation='submit_run',target=sid,configuration_revision_id=revision)
        if expected_runtime is not None:
            payload['expected_runtime'] = expected_runtime
        budget = body.get('execution_budget')
        if budget is not None:
            from .contracts import execution_wall_seconds

            if not isinstance(budget, dict) or set(budget) != {'wall_seconds'}:
                raise DomainError('invalid_request', 400)
            try:
                execution_wall_seconds(budget['wall_seconds'])
            except ValueError:
                raise DomainError('invalid_request', 400) from None
            payload['execution_budget'] = budget

        def admission(db):
            if admission_limit is None:
                return
            if type(admission_limit) is not int or admission_limit < 1:
                raise ValueError('Positive execution admission limit required')
            # Store.command already holds the single-writer transaction lock;
            # admission and receipt acceptance cannot race across actor studies.
            count = db.execute("""SELECT count(*) AS total FROM execution_operations
                WHERE actor_id=? AND state IN ('accepted_run','dispatching','uncertain')
                AND (preparation_state IS NULL OR preparation_state<>'preparation_failed')""",
                (actor,)).fetchone()['total']
            if count >= admission_limit:
                raise DomainError('limit_exceeded', 429)

        def accept(db):
            row=db.execute('SELECT payload FROM configurations WHERE study_id=? AND configuration_revision_id=?',(sid,revision)).fetchone()
            if row is None:raise DomainError('resource_not_found',404)
            frozen=json.loads(row['payload'])
            if frozen['configuration']['schema_version'] in ('3','4','6') or frozen['model_snapshot']['schema_version'] in ('2','3','4','5'):
                validate_frozen_configuration(frozen)
                if frozen['configuration']['study_id']!=sid:raise ValueError('Configuration study mismatch')
            run_id=uid();result=dict(run_id=run_id,command_id=command,state='accepted_run',
                receipt_url=f'/api/1/studies/{sid}/commands/{command}?category=run')
            # The acceptance time is written once, in the acceptance transaction, and never
            # changes; it stays out of the receipt and the outbox payload.
            accepted_at=datetime.now(timezone.utc).isoformat(
                timespec='microseconds').replace('+00:00','Z')
            db.execute('INSERT INTO run_associations(run_id,study_id,configuration_revision_id,'
                       'command_id,accepted_at) VALUES(?,?,?,?,?)',
                       (run_id,sid,revision,command,accepted_at))
            db.execute(
                'INSERT INTO outbox VALUES(?,?,?)',
                (
                    run_id,
                    'accepted_run',
                    json.dumps(
                        dict(
                            actor=actor,
                            frozen=json.loads(row['payload']),
                            **({'execution_budget': budget} if budget is not None else {}),
                            **({'expected_runtime': expected_runtime}
                               if expected_runtime is not None else {}),
                        )
                    ),
                ),
            )
            self.fault('before_receipt')
            return result
        result=self.store.command(actor,sid,'run',command,payload,accept,
            receipt_state='accepted_run',admission=admission,
            attribute=lambda accepted:[('run',accepted['run_id'],None)])
        self.fault('after_receipt')
        return self.read(actor,sid,result['run_id'])

    def read(self,actor,sid,run_id):
        return History(self.store).submission_read(actor, sid, run_id)

    def hydrate(self,actor,sid,run_id):
        """Explicit authorized read/cache of an existing association; never dispatch."""
        with self.store.connection() as db:
            row,_=History(self.store).run_row(db,actor,sid,run_id,payload=False)
            if row['state']!='recorded' or row['process_uuid'] is None:raise DomainError('history_not_recorded',409)
        self._record(run_id,association(row),actor=actor)

    def _record(self,run_id,record,*,actor=None):
        with self.store.connection() as db:
            row=run_association(db,run_id)
            if actor is not None:self.store.authorize(db,actor,row['study_id'])
            payload=json.loads(row['payload'])
            stored_request(row,payload,self.store.command_receipt(db,row['study_id'],'run',row['command_id']))
        expected=association(record)
        if row['process_uuid'] is not None and association(row)!=expected:
            raise ValueError('Recorded process association cannot change')
        retained=self.native.read_record(payload['request'],expected)
        saved=projection(payload,retained,expected)
        with self.store.connection(write=True) as db:
            row=run_association(db,run_id,payload=False)
            if actor is not None:self.store.authorize(db,actor,row['study_id'])
            if row['process_uuid'] is not None and association(row)!=expected:
                raise ValueError('Recorded process association cannot change')
            db.execute('UPDATE run_associations SET store_uuid=?,process_uuid=? WHERE run_id=?',
                       (record['store_uuid'],record['process_uuid'],run_id))
            if stored_request(row,payload,self.store.command_receipt(db,row['study_id'],'run',row['command_id']))!=saved['request']:
                raise ValueError('Stored request changed during retained read')
            current=json.loads(db.execute('SELECT payload FROM execution_operations WHERE run_id=?',
                                         (run_id,)).fetchone()[0])
            if 'history' in current and not current['history']['errors'] and current['history']!=saved:
                raise ValueError('Completed retained projection cannot change')
            current['status']={k:retained[k] for k in ('process_state','exit_status')}
            current['history']=saved
            db.execute('UPDATE execution_operations SET payload=? WHERE run_id=?',(json.dumps(current),run_id))
            self._state(db,row['study_id'],row['command_id'],run_id,'recorded')

    def _state(self,db,sid,command,run_id,state):
        receipt=self.store.command_receipt(db,sid,'run',command)
        status_field = ("read_summary->>'status'" if getattr(db,'dialect',None)=='postgresql'
                        else "json_extract(payload,'$.status')")
        status=db.execute('SELECT '+status_field+' AS status FROM execution_operations WHERE run_id=?',
                          (run_id,)).fetchone()['status']
        # Preparation is a phase of accepted work, before the native claim.
        # Preserve the existing outbox state constraint and immutable records.
        if state in ('prepared','preparation_failed'):
            db.execute('UPDATE execution_operations SET preparation_state=?,state=? WHERE run_id=?',
                       (state,'accepted_run',run_id))
        else:
            db.execute('UPDATE execution_operations SET state=? WHERE run_id=?',(state,run_id))
        result={**receipt['result'],'state':state,**(json.loads(status) if status else {})}
        db.execute("UPDATE receipts SET state=?,result=? WHERE scope=? AND category='run' AND command_id=?",
                   (state,json.dumps(result),sid,command))

    def analysis_authority_failures(self, db, sid, parent):
        """Return only proven unprepared authorization interruptions of this finite plan.

        None means a different failure or uncertain execution prevents recovery. Empty
        means no child needs repair. Frozen source bytes and native identities never change.
        """
        linked = {row['run_id']: row['child_command'] for row in db.execute(
            'SELECT run_id,child_command FROM analysis_execution_children '
            "WHERE study_id=? AND analysis_command=? AND child_category='run'",
            (sid, parent['command_id'])).fetchall()}
        runs = set(linked) | {r['run_id'] for r in parent['result']['runs'] if r['run_id']}
        interrupted, unsafe = [], False
        for rid in runs:
            row = run_association(db, rid, study_id=sid, payload=False)
            if row is None:
                return None
            operational = db.execute('SELECT o.state AS source_state,'
                "CASE WHEN x.preparation_state='preparation_failed' THEN o.payload END AS source_payload,"
                'x.actor_id,x.preparation_state,'
                "CASE WHEN x.preparation_state='preparation_failed' THEN x.payload END AS operation_payload,"
                "CASE WHEN x.state='recorded' THEN json_extract(x.payload,"
                "'$.history.results.execution.state') END AS execution_state "
                'FROM outbox o JOIN execution_operations x USING(run_id) WHERE x.run_id=?',
                (rid,)).fetchone()
            if operational is None:
                return None
            row.update(dict(operational))
            if row['state'] in ('uncertain', 'dispatching'):
                unsafe = True
            if row['state'] == 'recorded' and row['execution_state'] != 'finished':
                return None
            if row['preparation_state'] != 'preparation_failed':
                continue
            operation = json.loads(row['operation_payload'])
            receipt = self.store.command_receipt(db, sid, 'run', row['command_id'])
            source = json.loads(row['source_payload'])
            expected_error = dict(code='analysis_authority_revoked', status=403,
                                  current_revision=None, fields=[], outcome='unchanged')
            if (linked.get(rid) != row['command_id'] or row['state'] != 'accepted_run'
                    or row['source_state'] != 'accepted_run'
                    or row['store_uuid'] is not None or row['process_uuid'] is not None
                    or operation != {} or not receipt or receipt['state'] != 'preparation_failed'
                    or receipt['error'] != expected_error
                    or receipt['actor_id'] != parent['actor_id']
                    or row['actor_id'] != parent['actor_id']
                    or source.get('actor') != parent['actor_id']
                    or not set(source) <= {'actor', 'frozen', 'expected_runtime', 'execution_budget'}
                    or not {'actor', 'frozen'} <= set(source)):
                return None
            interrupted.append(dict(run_id=rid, child_command=row['command_id'],
                source_sha256=raw_hash(row['source_payload'].encode()),
                previous_receipt=receipt, previous_operation=dict(
                    state=row['state'], preparation_state=row['preparation_state'],
                    payload=row['operation_payload'])))
        return None if interrupted and unsafe else interrupted

    def resume_analysis_preparation(self, db, actor, sid, parent, command, children):
        """Audit and release only the preflight-approved unlaunched children atomically."""
        for child in children:
            db.execute('INSERT INTO analysis_run_resumptions '
                '(study_id,command_id,analysis_command,run_id,child_command,actor_id,'
                'source_sha256,previous_receipt,previous_operation) VALUES(?,?,?,?,?,?,?,?,?)',
                (sid, command, parent['command_id'], child['run_id'], child['child_command'], actor,
                 child['source_sha256'], json.dumps(child['previous_receipt']),
                 json.dumps(child['previous_operation'])))
            db.execute('UPDATE execution_operations SET preparation_state=NULL WHERE run_id=?',
                       (child['run_id'],))
            receipt = child['previous_receipt']
            result = dict(receipt['result'], state='accepted_run')
            db.execute("UPDATE receipts SET state='accepted_run',result=?,error=NULL "
                       "WHERE scope=? AND category='run' AND command_id=?",
                       (json.dumps(result), sid, child['child_command']))

    def dispatch_batch(self, run_ids):
        if (not isinstance(run_ids, list) or not run_ids
                or len(set(run_ids)) != len(run_ids)):
            raise ValueError('Distinct bounded run identities required')
        # A batch holds one actor and one finite authority. Splitting by parent
        # preserves batching while preventing a scope from hiding another plan.
        groups = {}
        for run_id in run_ids:
            parent = self.store.background_analysis_parent('run', run_id)
            if hasattr(self.store, 'database'):
                jobs = self.store.background_jobs('run', run_id)
                if not jobs:
                    continue
                actor = jobs[0]['actor_id']
            else:
                actor = parent['actor_id'] if parent else None
            key = (actor, parent['analysis_command'] if parent else None)
            groups.setdefault(key, []).append(run_id)
        for items in groups.values():
            with self.store.background_actor('run', items[0]) as admitted:
                if admitted:
                    self._dispatch_batch(items)

    def _dispatch_batch(self, run_ids):
        """Claim a bounded group under the existing dispatch lock, then cross once.

        Each receipt remains independent. Any ambiguous response leaves original
        requests uncertain; normal lookup can adopt them but never redispatch.
        """
        from .contracts import BATCH_RUN_LIMIT, EXECUTION_WALL_DEFAULT

        if (
            not isinstance(run_ids, list)
            or not 1 <= len(run_ids) <= BATCH_RUN_LIMIT
            or len(set(run_ids)) != len(run_ids)
        ):
            raise ValueError('Distinct bounded run identities required')
        if len(run_ids) == 1:
            return self.dispatch(run_ids[0])
        with self._dispatch_lock():
            pending = []
            for run_id in run_ids:
                self._dispatch_locked(run_id, deferred=pending)
            if not pending:
                return
            try:
                with self.store.connection() as db:
                    for row, payload, _ in pending:
                        self.store.authorize(db, payload['actor'], row['study_id'], write=True)
                items = [
                    dict(
                        bundle=bundle,
                        request=payload['request'],
                        wall_seconds=payload.get('execution_budget', {}).get(
                            'wall_seconds', EXECUTION_WALL_DEFAULT
                        ),
                    )
                    for _, payload, bundle in pending
                ]
                records = self.native.launch_batch(items)
                if (
                    not isinstance(records, list)
                    or len(records) != len(items)
                    or any(
                        not isinstance(record, dict)
                        or set(record) != {'request', 'record'}
                        or record['request'] != item['request']
                        for item, record in zip(items, records, strict=True)
                    )
                ):
                    raise ValueError('Independent native response identity mismatch')
            except (OSError, TimeoutError, RuntimeError, ValueError, DomainError):
                with self.store.connection(write=True) as db:
                    for row, _, _ in pending:
                        self._state(
                            db, row['study_id'], row['command_id'], row['run_id'], 'uncertain'
                        )
                return
            for (row, _, _), record in zip(pending, records, strict=True):
                self._record(row['run_id'], record['record'])

    @contextmanager
    def _dispatch_lock(self):
        import fcntl
        import os

        fd = os.open(
            self.store.lock_path('.dispatch.lock'),
            os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW,
            0o600,
        )
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def dispatch(self, run_id, *, prepare_only=False):
        with self.store.background_actor('run', run_id) as admitted:
            if admitted:
                with self._dispatch_lock():
                    self._dispatch_locked(run_id, prepare_only=prepare_only)

    def _dispatch_locked(self, run_id, *, prepare_only=False, deferred=None):
        with self.store.connection() as db:
            row = run_association(db, run_id)
            if row is None:
                # Queue discovery is not continuing authority. Expired or revoked
                # delegation hides the row; leave it untouched without taking down
                # the dispatcher or preventing other actors' work from progressing.
                return
            payload = json.loads(row['payload'])
            if row['state'] == 'accepted_run':
                row['state'] = payload.get('preparation_state', row['state'])
            receipt = self.store.command_receipt(db, row['study_id'], 'run', row['command_id'])
        if row['state'] in ('recorded', 'preparation_failed'):
            return
        if row['state'] in ('dispatching', 'uncertain'):
            try:
                matches = self.native.matches(payload['request'])
                if len(matches) == 1:
                    self._record(run_id, self.native.inspect(matches[0]))
                    return
            except (OSError, TimeoutError, RuntimeError):
                pass
            with self.store.connection(write=True) as db:
                self._state(db, row['study_id'], row['command_id'], run_id, 'uncertain')
            return
        # Current membership is checked again before preparation or claim.
        # Claimed/uncertain work above remains reconciliation-only.
        try:
            with self.store.connection() as db:
                self.store.authorize(db, payload['actor'], row['study_id'], write=True)
        except DomainError as error:
            self._preparation_failure(row, error.code, status=error.status)
            return
        if row['state'] == 'prepared' and payload['bundle']['manifest'].get(
            'schema_version'
        ) not in ('2', '3', '4', '5', '6', '8', '10', '11', '12'):
            self._preparation_failure(row, 'unsupported_execution_version')
            return
        self.native.require_attestation()
        if row['state'] != 'prepared':
            try:
                dependencies = None
                if payload['frozen']['configuration']['schema_version'] in ('3', '4', '6') or payload[
                    'frozen'
                ]['model_snapshot']['schema_version'] in ('2', '3', '4', '5'):
                    validate_frozen_configuration(payload['frozen'])
                # Every configuration that can carry result-linked inputs resolves them.
                if payload['frozen']['configuration']['schema_version'] in ('2', '3', '4', '6'):
                    dependencies = ResultBindings(self.store).dependencies(
                        payload['actor'],
                        row['study_id'],
                        payload['frozen']['configuration'],
                        self.native,
                    )
                prepared, files = self.prepare(
                    payload['actor'], row['study_id'], row['command_id'], payload['frozen']
                )
                bundle = assemble_bundle(
                    run_id,
                    prepared,
                    files,
                    payload['frozen'],
                    self.native.bundle_runtime(),
                    dependencies,
                )
                if (
                    payload.get('expected_runtime') is not None
                    and bundle['manifest']['runtime'] != payload['expected_runtime']
                ):
                    raise ValueError('Sample runtime changed')
            except DomainError as error:
                if error.status >= 500:
                    return  # Visible pending; no claim crossed.
                self._preparation_failure(row, error.code, status=error.status)
                return
            except (ValueError, KeyError, TypeError) as error:
                self._preparation_failure(
                    row,
                    'unsupported_execution_version'
                    if str(error).startswith('Unsupported')
                    else 'invalid_preparation',
                )
                return
            request = dict(
                run_id=run_id,
                scope=row['study_id'],
                command_id=row['command_id'],
                payload_digest=receipt['payload_digest'],
                bundle_digest=bundle['manifest']['bundle_digest'],
            )
            payload.update(
                request=request,
                bundle=dict(
                    manifest=bundle['manifest'],
                    files={p: base64.b64encode(b).decode() for p, b in bundle['files'].items()},
                ),
            )
            with self.store.connection(write=True) as db:
                db.execute(
                    'UPDATE outbox SET payload=? WHERE run_id=?', (json.dumps(payload), run_id)
                )
                self._state(db, row['study_id'], row['command_id'], run_id, 'prepared')
            self.fault('after_prepare')
        if prepare_only:
            return
        request = payload['request']
        bundle = dict(
            manifest=payload['bundle']['manifest'],
            files={
                p: base64.b64decode(b, validate=True) for p, b in payload['bundle']['files'].items()
            },
        )
        validate_retained_bundle(bundle, request, payload['frozen'])
        self.fault('before_claim')
        try:
            source_records = {}
            config = payload['frozen']['configuration']
            if config['schema_version'] in ('2', '3', '4', '6'):
                resolver = ResultBindings(self.store)
                source_records = resolver.verify_configuration(
                    payload['actor'], row['study_id'], config
                )
                # A prepared retry must verify the same native results again;
                # it must never silently rebuild its immutable bundle.
                current = resolver.dependencies(
                    payload['actor'], row['study_id'], config, self.native
                )
                if canonical(current) != bundle['files']['result-dependencies.json']:
                    raise DomainError('reference_conflict', 409)
            with self.store.connection(write=True) as db:
                self.store.authorize(db, payload['actor'], row['study_id'], write=True)
                if source_records:
                    History(self.store).recheck(
                        db,
                        payload['actor'],
                        row['study_id'],
                        [r[2] for r in source_records.values()],
                    )
                self._state(db, row['study_id'], row['command_id'], run_id, 'dispatching')
        except DomainError as error:
            # The claim transaction rolled back. Persist a terminal failure
            # so one revoked actor cannot poison the serialized queue.
            self._preparation_failure(row, error.code, status=error.status)
            return
        self.fault('after_claim')
        if deferred is not None:
            deferred.append((row, payload, bundle))
            return
        try:
            if 'execution_budget' in payload:
                record = self.native.launch_budgeted(
                    bundle, request, payload['execution_budget']['wall_seconds']
                )
            else:
                record = self.native.launch(bundle, request)
        except (OSError, TimeoutError, RuntimeError, ValueError):
            with self.store.connection(write=True) as db:
                self._state(db, row['study_id'], row['command_id'], run_id, 'uncertain')
            return
        self._record(run_id, record)

    def _preparation_failure(self, row, code, *, status=422):
        error = dict(
            code=code, status=status, current_revision=None, fields=[], outcome='unchanged'
        )
        with self.store.connection(write=True) as db:
            self._state(db, row['study_id'], row['command_id'], row['run_id'], 'preparation_failed')
            db.execute(
                "UPDATE receipts SET error=? WHERE scope=? AND category='run' AND command_id=?",
                (json.dumps(error), row['study_id'], row['command_id']),
            )
