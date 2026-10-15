"""Submission orchestration: static preparation, durable receipt/outbox and dispatch.

The frozen bundle contract (assembly and every admission check) lives in
``execution_bundle``; this module owns only ``StaticPreparation`` and ``Submissions``.
Candidate bytes remain inert here.
"""
import base64
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
    def __init__(self,model):self.model=model
    def __call__(self,actor,sid,command,frozen):
        from uuid import UUID,uuid5
        validate_frozen_configuration(frozen)
        if uses_polish_envelope(frozen['model_snapshot'],frozen.get('approach_closure')):
            status,response=self.model.call(actor,sid,'GET','/capabilities',response_schema='CapabilitiesResponseRead2',resources=[sid])
            from .readiness import supports_descriptive_execution
            if status!=200 or not supports_descriptive_execution(response.get('data'),frozen['model_snapshot']):
                raise ValueError('Modeling backend lacks exact descriptive execution support')
        config=project_scientific_configuration(frozen['configuration']);mid=config['model_id']
        # Separate from public run/authoring commands; stable across crashes.
        private_command=str(uuid5(UUID(command),'hyprn_mvp.prepare.artifact3:'+sid))
        body=dict(command_id=private_command,model_revision_id=config['model_revision_id'],
                  configuration_snapshot=config,configuration_digest=config['digest'])
        _,response=self.model.call(actor,sid,'POST',f'/models/{mid}/prepare-execution',body,
            request_schema='Prepare',resources=[mid])
        if set(response)!={'data'} or not isinstance(response['data'],dict):raise ValueError('Invalid preparation response')
        prepared=response['data']
        if prepared.get('schema_version') not in ('2', '3'):
            raise ValueError('Unsupported preparation version; create a new schema2 run command')
        closed('PreparedModelArtifactRead3',prepared)
        if len({f['file_id'] for f in prepared['files']})!=len(prepared['files']):raise ValueError('Duplicate file identity')
        files={};total=0
        for item in prepared['files']:
            path=safe_path(item['path'])
            if path in files:raise ValueError('Duplicate prepared file')
            _,response=self.model.call(actor,sid,'GET',f"/preparations/{prepared['preparation_id']}/files/{item['file_id']}",
                response_schema='ByteFileResponse',resources=[mid])
            raw=base64.b64decode(response['data']['bytes'],validate=True)
            total+=len(raw)
            if total>MAX_BYTES or response['data']['sha256']!=item['sha256'] or response['data']['media_type']!=item['media_type']:
                raise ValueError('Prepared file mismatch')
            files[path]=raw
        validate_preparation(prepared,files,frozen)
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

    def submit(self,actor,sid,body,*,expected_runtime=None):
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

        def accept(db):
            row=db.execute('SELECT payload FROM configurations WHERE study_id=? AND configuration_revision_id=?',(sid,revision)).fetchone()
            if row is None:raise DomainError('resource_not_found',404)
            frozen=json.loads(row['payload'])
            if frozen['configuration']['schema_version'] in ('3','4') or frozen['model_snapshot']['schema_version'] in ('2','3','4'):
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
        result=self.store.command(actor,sid,'run',command,payload,accept,receipt_state='accepted_run')
        self.fault('after_receipt')
        return self.read(actor,sid,result['run_id'])

    def read(self,actor,sid,run_id):
        with self.store.connection() as db:
            row,_=History(self.store).run_row(db,actor,sid,run_id)
            payload=json.loads(row['payload'])
            state=payload.get('preparation_state',row['state']) if row['state']=='accepted_run' else row['state']
            result=dict(run_id=run_id,command_id=row['command_id'],state=state,**payload.get('status',{}),
                receipt_url=f"/api/1/studies/{sid}/commands/{row['command_id']}?category=run")
        config=payload.get('frozen',{}).get('configuration',{})
        derivation=config.get('derivation') if config.get('schema_version') in ('2','3') else None
        if derivation:
            from .readiness import runtime_identity,runtime_comparison,compare_runtimes
            try:
                check_digest(config)
                source=runtime_identity(derivation['source_runtime'])
            except (ValueError,TypeError,KeyError):
                # Corrupt historical source identity is not a publishable DTO.
                # Existing History still describes the retained record error.
                return result
            if 'bundle' not in payload:
                result['runtime_comparison']=runtime_comparison(self.store,actor,sid,source)
            else:
                current=None
                try:
                    bundle=dict(manifest=payload['bundle']['manifest'],files={p:base64.b64decode(b,validate=True) for p,b in payload['bundle']['files'].items()})
                    validate_retained_bundle(bundle,payload['request'],payload['frozen'])
                    current=runtime_identity(bundle['manifest']['runtime'])
                except (ValueError,TypeError,KeyError): pass
                # Never substitute today's observation for a corrupt or missing
                # prepared identity, nor restore the derivation source runtime.
                result['runtime_comparison']=compare_runtimes(source,current,basis='prepared_bundle')
        return result

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
            payload=json.loads(db.execute('SELECT payload FROM outbox WHERE run_id=?',(run_id,)).fetchone()[0])
            if stored_request(row,payload,self.store.command_receipt(db,row['study_id'],'run',row['command_id']))!=saved['request']:
                raise ValueError('Stored request changed during retained read')
            if 'history' in payload and not payload['history']['errors'] and payload['history']!=saved:
                raise ValueError('Completed retained projection cannot change')
            payload['status']={k:retained[k] for k in ('process_state','exit_status')}
            payload['history']=saved
            db.execute('UPDATE outbox SET payload=? WHERE run_id=?',(json.dumps(payload),run_id))
            self._state(db,row['study_id'],row['command_id'],run_id,'recorded')

    def _state(self,db,sid,command,run_id,state):
        receipt=self.store.command_receipt(db,sid,'run',command)
        payload=json.loads(db.execute('SELECT payload FROM outbox WHERE run_id=?',(run_id,)).fetchone()[0])
        # Preparation is a phase of accepted work, before the native claim.
        # Preserve the existing outbox state constraint and immutable records.
        if state in ('prepared','preparation_failed'):payload['preparation_state']=state
        db.execute('UPDATE outbox SET state=?,payload=? WHERE run_id=?',
                   ('accepted_run' if state in ('prepared','preparation_failed') else state,json.dumps(payload),run_id))
        result={**receipt['result'],'state':state,**payload.get('status',{})}
        db.execute("UPDATE receipts SET state=?,result=? WHERE scope=? AND category='run' AND command_id=?",
                   (state,json.dumps(result),sid,command))

    def dispatch(self,run_id,*,prepare_only=False):
        import fcntl
        import os
        # One OS lock serializes all dispatcher threads and processes sharing this
        # application store. No custom scheduler, expiring lease or background queue.
        lock=self.store.path.with_suffix('.dispatch.lock')
        fd=os.open(lock,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        try:
            fcntl.flock(fd,fcntl.LOCK_EX)
            with self.store.connection() as db:
                row=run_association(db,run_id)
                if row is None:raise DomainError('resource_not_found',404)
                payload=json.loads(row['payload'])
                if row['state']=='accepted_run':row['state']=payload.get('preparation_state',row['state'])
                receipt=self.store.command_receipt(db,row['study_id'],'run',row['command_id'])
            if row['state'] in ('recorded','preparation_failed'):return
            if row['state'] in ('dispatching','uncertain'):
                try:
                    matches=self.native.matches(payload['request'])
                    if len(matches)==1:
                        self._record(run_id,self.native.inspect(matches[0]));return
                except (OSError,TimeoutError,RuntimeError):pass
                with self.store.connection(write=True) as db:self._state(db,row['study_id'],row['command_id'],run_id,'uncertain')
                return
            # Current membership is checked again before preparation or claim.
            # Claimed/uncertain work above remains reconciliation-only.
            try:
                with self.store.connection() as db:self.store.authorize(db,payload['actor'],row['study_id'],write=True)
            except DomainError as error:
                self._preparation_failure(row,error.code,status=error.status)
                return
            if row['state'] == 'prepared' and payload['bundle']['manifest'].get(
                'schema_version'
            ) not in ('2', '3', '4', '5', '6', '8', '10'):
                self._preparation_failure(row, 'unsupported_execution_version')
                return
            self.native.require_attestation()
            if row['state']!='prepared':
                try:
                    dependencies=None
                    if (payload['frozen']['configuration']['schema_version'] in ('3','4')
                            or payload['frozen']['model_snapshot']['schema_version'] in ('2','3','4')):
                        validate_frozen_configuration(payload['frozen'])
                    if payload['frozen']['configuration']['schema_version'] in ('2','3','4'):
                        dependencies=ResultBindings(self.store).dependencies(payload['actor'],row['study_id'],payload['frozen']['configuration'],self.native)
                    prepared,files=self.prepare(payload['actor'],row['study_id'],row['command_id'],payload['frozen'])
                    bundle=assemble_bundle(run_id,prepared,files,payload['frozen'],self.native.bundle_runtime(),dependencies)
                    if (payload.get('expected_runtime') is not None
                            and bundle['manifest']['runtime'] != payload['expected_runtime']):
                        raise ValueError('Sample runtime changed')
                except DomainError as error:
                    if error.status>=500:return  # Visible pending; no claim crossed.
                    self._preparation_failure(row,error.code,status=error.status)
                    return
                except (ValueError,KeyError,TypeError) as error:
                    self._preparation_failure(row,'unsupported_execution_version' if str(error).startswith('Unsupported') else 'invalid_preparation')
                    return
                request=dict(run_id=run_id,scope=row['study_id'],command_id=row['command_id'],payload_digest=receipt['payload_digest'],bundle_digest=bundle['manifest']['bundle_digest'])
                payload.update(request=request,bundle=dict(manifest=bundle['manifest'],files={p:base64.b64encode(b).decode() for p,b in bundle['files'].items()}))
                with self.store.connection(write=True) as db:
                    db.execute('UPDATE outbox SET payload=? WHERE run_id=?',(json.dumps(payload),run_id))
                    self._state(db,row['study_id'],row['command_id'],run_id,'prepared')
                self.fault('after_prepare')
            if prepare_only:return
            request=payload['request']
            bundle=dict(manifest=payload['bundle']['manifest'],files={p:base64.b64decode(b,validate=True) for p,b in payload['bundle']['files'].items()})
            validate_retained_bundle(bundle,request,payload['frozen'])
            self.fault('before_claim')
            try:
                source_records={}
                config=payload['frozen']['configuration']
                if config['schema_version'] in ('2','3','4'):
                    resolver=ResultBindings(self.store)
                    source_records=resolver.verify_configuration(payload['actor'],row['study_id'],config)
                    # A prepared retry must verify the same native results again;
                    # it must never silently rebuild its immutable bundle.
                    current=resolver.dependencies(payload['actor'],row['study_id'],config,self.native)
                    if canonical(current)!=bundle['files']['result-dependencies.json']:raise DomainError('reference_conflict',409)
                with self.store.connection(write=True) as db:
                    self.store.authorize(db,payload['actor'],row['study_id'],write=True)
                    if source_records:History(self.store).recheck(db,payload['actor'],row['study_id'],[r[2] for r in source_records.values()])
                    db.execute('UPDATE outbox SET payload=? WHERE run_id=?',(json.dumps(payload),run_id))
                    self._state(db,row['study_id'],row['command_id'],run_id,'dispatching')
            except DomainError as error:
                # The claim transaction rolled back. Persist a terminal failure
                # so one revoked actor cannot poison the serialized queue.
                self._preparation_failure(row,error.code,status=error.status)
                return
            self.fault('after_claim')
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
            self._record(run_id,record)
        finally:
            fcntl.flock(fd,fcntl.LOCK_UN);os.close(fd)

    def _preparation_failure(self,row,code,*,status=422):
        error=dict(code=code,status=status,current_revision=None,fields=[],outcome='unchanged')
        with self.store.connection(write=True) as db:
            self._state(db,row['study_id'],row['command_id'],row['run_id'],'preparation_failed')
            db.execute("UPDATE receipts SET error=? WHERE scope=? AND category='run' AND command_id=?",
                       (json.dumps(error),row['study_id'],row['command_id']))
