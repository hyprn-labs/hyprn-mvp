"""Pure configuration compatibility and atomic immutable app snapshots."""
import json
import base64
import hashlib
from copy import deepcopy
from .approach import saved_version
from .contracts import DomainError, digest, uid, validate
from .store import ForeignEvidence, evidence_snapshot
from .units import UNIT_CATALOG_DIGEST, port_units, resolved_model_units
from .execution_bundle import finite, frozen_version, uses_polish_envelope
from .modeling import checked_model
from .history import History
from .modified_runs import ModifiedRuns, changes
from .result_bindings import ResultBindings

class Configurations:
    def __init__(self,store,coordinator):
        self.store,self.coordinator=store,coordinator

    def native_capabilities(self,actor,sid,*,strict=False):
        with self.store.connection() as db:self.store.authorize(db,actor,sid)
        try:
            status,result=self.coordinator.model.call(actor,sid,'GET','/capabilities',
                response_schema='CapabilitiesResponse',resources=[sid])
            caps=validate('Capabilities',result['data'],remote=True)
            if status!=200:raise DomainError('backend_unavailable',503,outcome='unknown')
        except DomainError:
            if strict:raise
            caps=None
        finally:
            # Current access takes precedence over either backend data or errors.
            with self.store.connection() as db:self.store.authorize(db,actor,sid)
        return caps

    @staticmethod
    def supports3(caps):
        return bool(caps and '1.2' in caps['contract_versions'] and '2' in caps['schema_versions']
            and any(c['id']=='resolved_configuration' and c['version']=='3' and c['supported'] for c in caps['capabilities']))

    @staticmethod
    def require_version_pair(configuration,model):
        if model['schema_version']=='2' and configuration['schema_version'] not in ('3','4'):
            raise DomainError('invalid_configuration',422)

        if model['schema_version'] in ('3','4') and configuration['schema_version']!='4':
            raise DomainError('invalid_configuration',422)

        if configuration['schema_version']=='4' and model['schema_version'] not in ('2','3','4'):
            raise DomainError('invalid_configuration',422)

    @staticmethod
    def _model_units(model):
        try:
            return resolved_model_units(model)
        except DomainError as error:
            raise DomainError('invalid_configuration',422,fields=error.fields) from None

    # Temporary test-only alias (identity_golden.py); production code uses
    # ``store.evidence_snapshot`` (test_module_boundaries pins both facts).
    _snapshot=staticmethod(evidence_snapshot)

    @staticmethod
    def _uses3(request,model):
        ids=[a['assumption_id'] for a in request['assumptions']]
        if len(ids)!=len(set(ids)):raise DomainError('invalid_configuration',422)
        uses={}
        def add(version,path,owner=None):uses.setdefault(version,[]).append(dict(path=path,
            code='unresolved_evidence',message='This exact evidence version is unavailable.',element_ref=owner))
        def citations(versions,path,owner):
            seen=set()
            for j,version in enumerate(versions):
                if version in seen:
                    raise DomainError('invalid_configuration',422,fields=[dict(path=f'{path}/{j}',
                        code='duplicate_evidence',message='This evidence version is already cited in this field.',
                        element_ref=owner)])
                seen.add(version)
                add(version,f'{path}/{j}')
        for base,assumptions in (('/model_snapshot/assumptions',model.get('assumptions',[])),('/assumptions',request['assumptions'])):
            for i,a in enumerate(assumptions):
                for j,link in enumerate(a['evidence_links']):
                    add(link['evidence_version_id'],f'{base}/{i}/evidence_links/{j}/evidence_version_id',a['assumption_id'])
        for i,item in enumerate(request['inputs']):
            citations(item['provenance']['evidence_version_ids'],f'/inputs/{i}/provenance/evidence_version_ids',item['target']['port_id'])
        for i,item in enumerate(request['criteria']):
            citations(item['evidence_version_ids'],f'/criteria/{i}/evidence_version_ids',item['criterion_id'])
        for j,version in enumerate(request['general_context_evidence_version_ids']):add(version,f'/general_context_evidence_version_ids/{j}')
        if len(uses)>1000:raise DomainError('limit_exceeded',413)
        return uses

    def _evidence3(self,db,actor,sid,uses):
        self.store.authorize(db,actor,sid)
        records={};missing=[]
        for version in sorted(uses):
            # Another study's version is unavailable here, exactly like an unknown one.
            try:record=self.store.evidence_record(db,actor,sid,version)
            except ForeignEvidence:record=None
            if record is None:missing.extend(uses[version]);continue
            records[version]=record
        if missing:raise DomainError('invalid_configuration',422,fields=missing)
        return records

    def _recheck3(self,db,actor,sid,request,model,study,pins,candidate=None):
        self.store.authorize(db,actor,sid)
        current=self.store.study_row(db,sid)
        if current!=study:raise DomainError('stale_revision',current_revision=current['revision'])
        if self.store.model_association(db,actor,sid,request['model_id'])!=pins['association']:raise DomainError('reference_conflict')
        checked_model(model,sid,request['model_id'],revision=request['model_revision_id'])
        if model!=pins['model']:raise DomainError('reference_conflict')
        records=self._evidence3(db,actor,sid,self._uses3(request,model))
        if records!=pins['evidence']:raise DomainError('reference_conflict')
        if candidate is not None:
            validate('ConfigurationCandidate'+request['schema_version'],candidate)
            if (candidate['evidence_snapshots']!=[evidence_snapshot(records[v]) for v in sorted(records)]
                    or candidate['assumptions']!=request['assumptions']
                    or candidate['general_context_evidence_version_ids']!=request['general_context_evidence_version_ids']):
                raise DomainError('reference_conflict')

    def _approach_pin(self,db,actor,sid,request,model):
        """Read exact local authority; never choose a current approach head."""
        self.store.authorize(db,actor,sid)
        selection=request['approach_selection']
        if selection is None:return None,None,None
        row=db.execute('SELECT * FROM approach_versions WHERE study_id=? AND approach_version_id=?',
            (sid,selection['approach_version_id'])).fetchone()
        if row is None:raise DomainError('resource_not_found',404)
        saved=saved_version(row,sid);version=saved['version'];closure=saved['closure']
        content=version['content']
        used={ref['binding_id'] for step in content['steps'] for ref in step['implementation_refs']}
        matching={b['binding_id'] for b in content['model_bindings'] if b['binding_id'] in used
            and b['model_id']==request['model_id'] and b['model_revision_id']==request['model_revision_id']}
        case=next((c for c in content['cases'] if c['case_id']==selection['case_id']),None)
        if not matching or (selection['case_id'] is not None and (case is None or case['binding_id'] not in matching)):
            raise DomainError('invalid_configuration',422,fields=[dict(path='/approach_selection',code='invalid_approach_selection',
                message='Choose a saved approach and case linked to this exact model revision.',element_ref=None)])
        retained=next((m for m in closure['models'] if m['model_id']==request['model_id']
            and m['model_revision_id']==request['model_revision_id']),None)
        if retained!=model:raise DomainError('reference_conflict')
        binding=dict(approach_id=version['approach_id'],approach_version_id=version['approach_version_id'],
            approach_digest=version['digest'],closure_digest=closure['digest'],case_id=selection['case_id'])
        return binding,deepcopy(closure),dict(row)

    def _recheck4(self,db,actor,sid,request,model,pins,candidate,closure):
        binding,current,witness=self._approach_pin(db,actor,sid,request,model)
        if witness!=pins or binding!=candidate['approach_binding'] or current!=closure:
            raise DomainError('reference_conflict')

    def freeze_candidate(self,actor,sid,candidate):
        validate("ConfigurationCandidate1",candidate)
        if set(candidate)&{"configuration_id","configuration_revision_id","parent_revision_id","digest"}:
            raise DomainError("invalid_request",400)
        if candidate["study_id"]!=sid:raise DomainError("resource_not_found",404)
        study=self.store.study(actor,sid)
        context=candidate["context_snapshot"]
        if context["description"]!=study["description"] or context["boundary"]!=study["boundary"]:
            raise DomainError("stale_revision",current_revision=study["revision"])
        snapshots={}
        for claimed in candidate["evidence_snapshots"]:
            version=claimed["evidence_version_id"]
            actual=evidence_snapshot(self.store.evidence_version(actor,sid,version),legacy_configuration=True)
            if actual!=claimed or version in snapshots:raise DomainError("reference_conflict")
            snapshots[version]=actual
        required=set()
        for value in candidate["inputs"]:
            if not value["provenance"]["statement"].strip():
                raise DomainError("invalid_configuration",422)
            required.update(value["provenance"]["evidence_version_ids"])
        for criterion in candidate["criteria"]:
            required.update(criterion["evidence_version_ids"])
        if not required<=snapshots.keys():raise DomainError("reference_conflict")
        return study,candidate

    def preview(self,actor,sid,candidate):
        if candidate.get('schema_version')=='4':
            return self._preview4(actor,sid,candidate)[:3]
        if candidate.get('schema_version')=='3':
            preview,model,study,_,_=self._preview3(actor,sid,candidate)
            return preview,model,study
        if candidate.get('schema_version')=='2':
            preview,model,study,_=self._preview2(actor,sid,candidate)
            return preview,model,study
        study,candidate=self.freeze_candidate(actor,sid,candidate)
        mid=candidate["model_id"];revision=candidate["model_revision_id"]
        model=self.coordinator.read(actor,sid,mid,"/revisions/"+revision,response_schema="ModelRevisionResponse4")["data"]
        if model["model_id"]!=mid or model["model_revision_id"]!=revision:
            raise DomainError("backend_unavailable",503,outcome="unknown")
        for source in model["source_files"]:
            try:raw=base64.b64decode(source["bytes"],validate=True)
            except ValueError:raise DomainError("backend_unavailable",503,outcome="unknown") from None
            if hashlib.sha256(raw).hexdigest()!=source["sha256"]:
                raise DomainError("backend_unavailable",503,outcome="unknown")
        if model["digest"]!=digest({k:v for k,v in model.items() if k!="digest"}):
            raise DomainError("backend_unavailable",503,outcome="unknown")
        self.require_version_pair(candidate,model)
        proof=self.coordinator.read(actor,sid,mid,"/configuration-compatibility",method="POST",
            body=dict(model_revision_id=revision,configuration_candidate=candidate),
            request_schema="Compatibility",response_schema="CompatibilityResultResponse")["data"]
        if proof["candidate_digest"]!=digest(candidate) or proof["model_digest"]!=model["digest"] or proof["model_revision_id"]!=revision:
            raise DomainError("backend_unavailable",503,outcome="unknown")
        return proof,model,study

    def commit(self,actor,sid,body):
        if body['configuration'].get('schema_version')=='4':
            return self._commit4(actor,sid,body)
        if body['configuration'].get('schema_version')=='3':
            return self._commit3(actor,sid,body)
        if body['configuration'].get('schema_version')=='2':
            return self._commit2(actor,sid,body)
        candidate=body["configuration"]
        validate("ConfigurationCandidate1",candidate)
        payload={k:v for k,v in body.items() if k!="command_id"}
        old=self.store.replay(actor,sid,"configuration",body["command_id"],payload)
        if old:
            self.require_version_pair(old['result']['configuration'],old['result']['model_snapshot'])
            return old['result']
        proof,model,study=self.preview(actor,sid,candidate)
        if not proof["compatible"]:raise DomainError("invalid_configuration",422,fields=proof["diagnostics"])
        def save(db):
            current=self.store.study_row(db,sid)
            self.store.cas(current["revision"],study["revision"])
            family=body.get("configuration_id")
            if family:
                head=db.execute("SELECT head FROM configuration_families WHERE study_id=? AND configuration_id=?",(sid,family)).fetchone()
                if not head:raise DomainError("resource_not_found",404)
                self.store.cas(head["head"],body["expected_revision"])
                parent=head["head"]
            else:
                if body["expected_revision"] is not None:raise DomainError("stale_revision")
                family=uid();parent=None
            revision=uid()
            snapshot=dict(candidate,configuration_id=family,configuration_revision_id=revision,parent_revision_id=parent)
            snapshot["digest"]=digest(snapshot)
            validate("ConfigurationRevision",snapshot)
            result=dict(configuration=snapshot,model_snapshot=model,study_revision=study["revision"])
            db.execute("INSERT INTO configurations VALUES(?,?,?,?)",(revision,family,sid,json.dumps(result)))
            db.execute("INSERT INTO configuration_families VALUES(?,?,?) ON CONFLICT(configuration_id) DO UPDATE SET head=excluded.head",(family,sid,revision))
            return result
        return self.store.command(actor,sid,"configuration",body["command_id"],payload,save)

    def _preview2(self,actor,sid,request):
        return self._preview_resolved(actor,sid,request,'2')[:4]

    def _preview3(self,actor,sid,request):
        return self._preview_resolved(actor,sid,request,'3')

    def _preview4(self,actor,sid,request):
        return self._preview_resolved(actor,sid,request,'4')

    def _preview_resolved(self,actor,sid,request,version):
        from .scientific_configuration import project_scientific_configuration
        from .readiness import runtime_comparison
        request=deepcopy(request)
        private_version='3' if version=='4' else version
        validate('ConfigurationRequest'+version,request)
        if request['study_id']!=sid:raise DomainError('resource_not_found',404)
        study=self.store.study(actor,sid)
        pins=None
        if version in ('3','4'):
            caps=self.native_capabilities(actor,sid,strict=True)
            if not self.supports3(caps):raise DomainError('unsupported_capability',422)
            with self.store.connection() as db:association=self.store.model_association(db,actor,sid,request['model_id'])
        origin=None
        if request['derivation'] is not None:
            origin,context=ModifiedRuns(self.store).authoring(actor,sid,request,study)
        else:
            if request['context_source']['kind']!='current_study':raise DomainError('reference_conflict',409)
            self.store.cas(study['revision'],request['context_source']['expected_study_revision'])
            context=dict(description=study['description'],boundary=study['boundary'],notes=deepcopy(request['notes']))
        # Resolve and authorize the basis first; edited text belongs only to
        # this new immutable configuration, never to the study or source run.
        if version in ('3','4') and 'context_override' in request:
            context.update({key:request['context_override'][key] for key in ('description','boundary')})
        targets=[(i['target']['instance_id'],i['target']['port_id']) for i in request['inputs']]
        if len(set(targets))!=len(targets):raise DomainError('invalid_configuration',422)
        if len({i['source_run_id'] for i in request['inputs'] if i['kind']=='run_result'})>64:
            raise DomainError('limit_exceeded',413)
        mid=request['model_id'];revision=request['model_revision_id']
        model=deepcopy(origin[0]['model_snapshot']) if origin else self.coordinator.read(actor,sid,mid,'/revisions/'+revision,response_schema='ModelRevisionResponse4')['data']
        validate('ModelRevisionRead4',model,remote=True)
        if model['model_id']!=mid or model['model_revision_id']!=revision or model['digest']!=digest({k:v for k,v in model.items() if k!='digest'}):
            raise DomainError('backend_unavailable',503,outcome='unknown')
        self.require_version_pair(request,model)
        if model['schema_version']=='4' and not self.coordinator.supports_quantities(caps):raise DomainError('unsupported_capability',422)
        if model['schema_version'] in ('3','4'):
            if 'unit_declarations/1' in model['required_capabilities'] and not self.coordinator.supports_units(caps):raise DomainError('unsupported_capability',422)
            # Readiness gate (admission): complete active units or invalid_configuration 422.
            self._model_units(model)
        for source in model['source_files']:
            try:raw=base64.b64decode(source['bytes'],validate=True)
            except ValueError:raise DomainError('backend_unavailable',503,outcome='unknown') from None
            if hashlib.sha256(raw).hexdigest()!=source['sha256']:raise DomainError('backend_unavailable',503,outcome='unknown')
        snapshots=[]
        if version in ('3','4'):
            checked_model(model,sid,mid,revision=revision)
            with self.store.connection() as db:evidence=self._evidence3(db,actor,sid,self._uses3(request,model))
            pins=dict(association=association,model=deepcopy(model),evidence=evidence)
            snapshots=[evidence_snapshot(evidence[v]) for v in sorted(evidence)]
        binding=closure=approach_pin=None
        if version=='4':
            with self.store.connection() as db:binding,closure,approach_pin=self._approach_pin(db,actor,sid,request,model)
            pins['approach']=approach_pin
        for eid in request.get('evidence_version_ids',[]):
            if eid in [s['evidence_version_id'] for s in snapshots]:raise DomainError('reference_conflict')
            snapshots.append(evidence_snapshot(self.store.evidence_version(actor,sid,eid),legacy_configuration=True))
        required=set()
        for item in request['inputs']:
            if not item['provenance']['statement'].strip():raise DomainError('invalid_configuration',422)
            required.update(item['provenance']['evidence_version_ids'])
        for criterion in request['criteria']:required.update(criterion['evidence_version_ids'])
        if version=='2' and not required<=set(request['evidence_version_ids']):raise DomainError('reference_conflict')
        resolver=ResultBindings(self.store);records={};resolved=[];sources={}
        for item in request['inputs']:
            target=(item['target']['instance_id'],item['target']['port_id'])
            if item['kind']=='literal':resolved.append({k:deepcopy(item[k]) for k in ('target','value','units','provenance')})
            else:
                source=resolver.resolve(actor,sid,item,records=records);sources[target]=source
                resolved.append(dict(target=deepcopy(item['target']),value=source['value'],units=source['units'],provenance=deepcopy(item['provenance'])))
        scientific=dict(schema_version=private_version,study_id=sid,model_id=mid,model_revision_id=revision,name=request['name'],inputs=resolved,
            criteria=deepcopy(request['criteria']),numerical=deepcopy(request['numerical']),
            context_snapshot=context,
            evidence_snapshots=snapshots,required_capabilities=list(model['required_capabilities']))
        validate('ModelingConfiguration'+private_version,scientific)
        proof=self.coordinator.read(actor,sid,mid,'/configuration-compatibility',method='POST',
            body=dict(model_revision_id=revision,configuration_candidate=scientific),request_schema='Compatibility',response_schema='CompatibilityResultResponse')['data']
        validate('CompatibilityResult2',proof,remote=True)
        if (proof['candidate_digest']!=digest(scientific) or proof['model_digest']!=model['digest'] or proof['model_revision_id']!=revision
                or proof['required_capabilities']!=scientific['required_capabilities']):raise DomainError('backend_unavailable',503,outcome='unknown')
        interpretations={ (i['target']['instance_id'],i['target']['port_id']):i for i in proof['input_interpretations']}
        if len(interpretations)!=len(proof['input_interpretations']):raise DomainError('backend_unavailable',503,outcome='unknown')
        full=deepcopy(scientific)
        full['schema_version']=version
        if version=='4':full['approach_binding']=binding
        bound_units=None
        for item in full['inputs']:
            key=(item['target']['instance_id'],item['target']['port_id']);source=sources.get(key)
            item['result_binding']=None
            if source:
                interpretation=interpretations.get(key);conversion=interpretation.get('conversion') if interpretation else None
                if not conversion:raise DomainError('invalid_configuration',422,fields=proof['diagnostics'])
                validate('UnitInterpretation',conversion,remote=True)
                instance=next((i for i in model['instances'] if i['instance_id']==key[0]),None)
                definition=next((d for d in model['definitions'] if instance and d['definition_version_id']==instance['definition_version_id']),None)
                port=next((p for p in definition['ports'] if p['port_id']==key[1]),None) if definition else None
                if port and bound_units is None:
                    # The single port-units rule; a legacy instance without its definition is
                    # an invalid backend model.
                    try:bound_units=port_units(model)
                    except KeyError:raise DomainError('backend_unavailable',503,outcome='unknown') from None
                if (not port or conversion['source_units']!=item['units'] or conversion['destination_units']!=bound_units[(key[0],instance['definition_version_id'],key[1])]
                        or ((model['schema_version']=='3' or isinstance(port['units'],dict)) and conversion['catalog_digest']!=UNIT_CATALOG_DIGEST)
                        or not finite(conversion['factor']) or not finite(item['value']*conversion['factor'])
                        or conversion['destination_value']!=item['value']*conversion['factor']):
                    raise DomainError('backend_unavailable',503,outcome='unknown')
                item['result_binding']=dict(source_run_id=source['source_run_id'],source_output=source['source_output'],results_digest=source['results_digest'],
                    source_configuration_digest=source['source_configuration_digest'],original_value=source['value'],original_units=source['units'],conversion=deepcopy(conversion),labels=source['labels'])
        if sources:full['required_capabilities'].append('result_linked_inputs/1')
        full.update(context_source=deepcopy(request['context_source']),derivation=None)
        if version in ('3','4'):
            full.update(assumptions=deepcopy(request['assumptions']),general_context_evidence_version_ids=deepcopy(request['general_context_evidence_version_ids']))
            full['required_capabilities'].append('configuration_assumptions/1')
        summaries=[];comparison=None
        if origin:
            source=origin[0]['configuration'];runtime=origin[1]['bundle']['manifest']['runtime']
            delta,summaries=changes(source,full)
            full['derivation']=dict(source_run_id=request['derivation']['source_run_id'],source_configuration_revision_id=source['configuration_revision_id'],
                source_configuration_digest=source['digest'],source_runtime=deepcopy(runtime),changes=delta)
            comparison=runtime_comparison(self.store,actor,sid,runtime)
            # Register after result resolution: a failed derivation source must
            # never bypass successful-result eligibility when also used as input.
            records.setdefault(request['derivation']['source_run_id'],origin)
        validate('ConfigurationCandidate'+version,full)
        if project_scientific_configuration(full)!=scientific:raise DomainError('reference_conflict')
        response=dict(schema_version=version,request_digest=digest(request),resolved_candidate=full,candidate_digest=digest(full),
            model_digest=model['digest'],compatibility=proof,changes=summaries,runtime_comparison=comparison)
        if version=='4':response['approach_closure']=closure
        if version=='4' and uses_polish_envelope(model,closure):response['schema_version']='6'
        validate('ConfigurationPreview'+response['schema_version'],response)
        if version in ('3','4'):
            with self.store.connection() as db:self._recheck3(db,actor,sid,request,model,study,pins,full)
        if version=='4':
            with self.store.connection() as db:self._recheck4(db,actor,sid,request,model,approach_pin,full,closure)
        return response,model,study,records,pins

    def _commit2(self,actor,sid,body):
        return self._commit_resolved(actor,sid,body,'2')

    def _commit3(self,actor,sid,body):
        return self._commit_resolved(actor,sid,body,'3')

    def _commit4(self,actor,sid,body):
        return self._commit_resolved(actor,sid,body,'4')

    def _commit_resolved(self,actor,sid,body,version):
        body=deepcopy(body)
        validate('ConfigurationCommit'+version,body)
        payload={k:v for k,v in body.items() if k!='command_id'}
        old=self.store.replay(actor,sid,'configuration',body['command_id'],payload)
        if old:
            self.require_version_pair(old['result']['configuration'],old['result']['model_snapshot'])
            if old['result']['model_snapshot']['schema_version'] in ('3','4'):self._model_units(old['result']['model_snapshot'])
            if version in ('3','4'):
                retained=old['result'];model=retained['model_snapshot'];candidate=retained['configuration']
                request=body['configuration']
                checked_model(model,sid,request['model_id'],revision=request['model_revision_id'])
                with self.store.connection() as db:
                    self.store.model_association(db,actor,sid,request['model_id'],write=True)
                    evidence=self._evidence3(db,actor,sid,self._uses3(request,model))
                    if candidate['evidence_snapshots']!=[evidence_snapshot(evidence[v]) for v in sorted(evidence)]:raise DomainError('reference_conflict')
                    if version=='4':
                        binding,closure,_=self._approach_pin(db,actor,sid,request,model)
                        validate('FrozenConfiguration'+frozen_version(model,closure),retained)
                        if binding!=candidate['approach_binding'] or closure!=retained['approach_closure']:raise DomainError('reference_conflict')
            return old['result']
        if body['configuration']['derivation'] is not None and (body['configuration_id'] is not None or body['expected_revision'] is not None):
            raise DomainError('reference_conflict',409)
        preview,model,study,records,pins=self._preview_resolved(actor,sid,body['configuration'],version)
        if not preview['compatibility']['compatible']:raise DomainError('invalid_configuration',422,fields=preview['compatibility']['diagnostics'])
        if preview['candidate_digest']!=body['expected_preview_digest']:raise DomainError('reference_conflict')
        candidate=preview['resolved_candidate']
        def save(db):
            if version in ('3','4'):
                self._recheck3(db,actor,sid,body['configuration'],model,study,pins,candidate)
                if digest(candidate)!=body['expected_preview_digest']:raise DomainError('reference_conflict')
                if version=='4':self._recheck4(db,actor,sid,body['configuration'],model,pins['approach'],candidate,preview['approach_closure'])
            self.store.cas(self.store.study_row(db,sid)['revision'],study['revision'])
            self.store.model_association(db,actor,sid,candidate['model_id'],write=True)
            History(self.store).recheck(db,actor,sid,[r[2] for r in records.values()])
            for snapshot in candidate['evidence_snapshots']:
                row=db.execute('SELECT payload FROM evidence WHERE study_id=? AND evidence_version_id=?',(sid,snapshot['evidence_version_id'])).fetchone()
                if row is None:raise DomainError('resource_not_found',404)
                actual=json.loads(row['payload'])
                if any(actual.get(k)!=v for k,v in snapshot.items()):raise DomainError('reference_conflict')
            family=body['configuration_id'];parent=None
            if family:
                row=db.execute('SELECT head FROM configuration_families WHERE study_id=? AND configuration_id=?',(sid,family)).fetchone()
                if row is None:raise DomainError('resource_not_found',404)
                self.store.cas(row['head'],body['expected_revision']);parent=row['head']
            elif body['expected_revision'] is not None:raise DomainError('stale_revision')
            else:family=uid()
            revision=uid();snapshot=dict(candidate,configuration_id=family,configuration_revision_id=revision,parent_revision_id=parent)
            snapshot['digest']=digest(snapshot);validate('ConfigurationRevision'+version,snapshot)
            result=dict(configuration=snapshot,model_snapshot=model,study_revision=study['revision'])
            if version=='4':
                result.update(schema_version=frozen_version(model,preview['approach_closure']),approach_closure=deepcopy(preview['approach_closure']))
                validate('FrozenConfiguration'+result['schema_version'],result)
            db.execute('INSERT INTO configurations VALUES(?,?,?,?)',(revision,family,sid,json.dumps(result)))
            db.execute('INSERT INTO configuration_families VALUES(?,?,?) ON CONFLICT(configuration_id) DO UPDATE SET head=excluded.head',(family,sid,revision))
            return result
        return self.store.command(actor,sid,'configuration',body['command_id'],payload,save)

    def read(self,actor,sid,revision=None):
        with self.store.connection() as db:
            self.store.authorize(db,actor,sid)
            if revision:
                row=db.execute("SELECT payload FROM configurations WHERE study_id=? AND configuration_revision_id=?",(sid,revision)).fetchone()
                if not row:raise DomainError("resource_not_found",404)
                return json.loads(row["payload"])
            return [json.loads(r["payload"]) for r in db.execute("SELECT payload FROM configurations WHERE study_id=? ORDER BY rowid",(sid,))]
