"""Pure configuration compatibility and atomic immutable app snapshots."""
import json
import base64
import hashlib
from copy import deepcopy
from .contracts import DomainError, digest, uid, validate
from .store import ForeignEvidence, evidence_snapshot
from .units import UNIT_CATALOG_DIGEST, port_units, resolved_model_units
from .execution_bundle import finite
from .modeling import checked_model
from .history import History
from .modified_runs import ModifiedRuns, changes
from .result_bindings import ResultBindings

def _configuration_written(saved):
    """The configuration version a commit wrote, for attribution."""
    configuration=saved['configuration']
    return [('configuration_version',configuration['configuration_id'],
             configuration['configuration_revision_id'])]


class Configurations:
    def __init__(self,store,coordinator):
        self.store,self.coordinator=store,coordinator

    def exploration_point(self, actor, sid, command, baseline, values, rationale, *, name=None):
        """Freeze one explicit sampled vector from an immutable configuration.

        This owner preserves exact model, evidence, approach and numerical pins.
        No modeling service read or candidate-source execution is needed.
        """
        from uuid import UUID, uuid5
        from .execution_bundle import validate_frozen_configuration

        frozen = deepcopy(self.read(actor, sid, baseline))
        configuration = frozen['configuration']
        # New configurations carry no criteria: only a version 6 baseline is copied.
        if configuration['schema_version'] != '6':
            raise DomainError('unsupported_record_version', 422)
        if name is not None:
            configuration['name'] = name
        original = configuration['inputs']
        key = lambda item: (item['target']['instance_id'], item['target']['port_id'])
        mapping = {key(item): item for item in values}
        if len(mapping) != len(values) or set(mapping) != {key(item) for item in original}:
            raise DomainError('invalid_request', 400)
        for item in original:
            value = mapping[key(item)]
            if value['units'] != item['units']:
                raise DomainError('invalid_request', 400)
            if item['value'] != value['value']:
                item['value'] = value['value']
                item['provenance']['statement'] = rationale
                item['provenance']['kind'] = 'manual'
                if 'result_binding' in item:
                    item['result_binding'] = None
        if 'derivation' in configuration:
            configuration['derivation'] = None
        configuration.update(configuration_id=str(uuid5(UUID(command), 'family')),
                             configuration_revision_id=str(uuid5(UUID(command), 'version')),
                             parent_revision_id=None)
        configuration['digest'] = digest({k:v for k,v in configuration.items() if k != 'digest'})
        validate_frozen_configuration(frozen)

        def save(db):
            db.execute('INSERT INTO configurations VALUES(?,?,?,?)',
                       (configuration['configuration_revision_id'],
                        configuration['configuration_id'], sid, json.dumps(frozen)))
            db.execute('INSERT INTO configuration_families VALUES(?,?,?)',
                       (configuration['configuration_id'], sid,
                        configuration['configuration_revision_id']))
            return dict(configuration_revision_id=configuration['configuration_revision_id'])
        # The containing sampling command pins the analysis name. Preserve this
        # point's numerical replay identity so an interrupted older operation reuses
        # its already saved configuration, including its immutable historical name.
        return self.store.command(actor, sid, 'exploration_configuration', command,
                                  dict(baseline=baseline, values=values, rationale=rationale), save,
                                  attribute=lambda saved: [('configuration_version',
                                                            configuration['configuration_id'],
                                                            saved['configuration_revision_id'])])

    def native_capabilities(self,actor,sid,*,strict=False):
        with self.store.connection() as db:self.store.authorize(db,actor,sid)
        try:
            status,result=self.coordinator.model.call(actor,sid,'GET','/capabilities',
                response_schema='CapabilitiesResponseRead4',resources=[sid])
            caps=validate('CapabilitiesRead4',result['data'],remote=True)
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
    def supports_criteria_free(caps):
        """The modeling service resolves the criteria-free private configuration 5."""
        return bool(caps and any(c['id']=='criteria_free_configuration' and c['version']=='1' and c['supported'] for c in caps['capabilities']))

    @staticmethod
    def require_version_pair(configuration,model):
        if model['schema_version']=='2' and configuration['schema_version'] not in ('3','4'):
            raise DomainError('invalid_configuration',422)

        if model['schema_version']=='3' and configuration['schema_version']!='4':
            raise DomainError('invalid_configuration',422)

        if model['schema_version']=='4' and configuration['schema_version'] not in ('4','6'):
            raise DomainError('invalid_configuration',422)

        # Version 6 carries no approach closure, which models 2 and 3 require.
        if configuration['schema_version']=='6' and model['schema_version'] not in ('4','5'):
            raise DomainError('invalid_configuration',422)

        if model['schema_version']=='5' and configuration['schema_version']!='6':
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

    @staticmethod
    def _price_bases(db, sid, model):
        """Every monetary occurrence has an exact saved basis before configuration/run."""
        from .explanations import quantity_price_basis
        from .units import monetary_expression
        bases = {}
        for (instance_id, _, port_id), expression in port_units(model).items():
            if monetary_expression(expression) is not None:
                target = dict(instance_id=instance_id, port_id=port_id)
                bases[(instance_id, port_id)] = quantity_price_basis(db, sid, model, target)
        return bases

    @staticmethod
    def _check_price_transfer(source, destination):
        """Scale conversion is checked by the engine; economic conversions need model code."""
        if source is None and destination is None:
            return
        if source is None or destination is None or (
            source['price_year'], source['economic_basis']
        ) != (destination['price_year'], destination['economic_basis']):
            raise DomainError('invalid_configuration', 422, fields=[dict(
                path='/inputs', code='monetary_basis_mismatch', element_ref=None,
                message='Linked monetary results require the same price year and economic basis; '
                        'a change requires an explicit conversion calculation with evidence.')])

    def _recheck3(self,db,actor,sid,request,model,study,pins,candidate=None):
        self.store.authorize(db,actor,sid)
        current=self.store.study_row(db,sid)
        if current!=study:raise DomainError('stale_revision',current_revision=current['revision'])
        if self.store.model_association(db,actor,sid,request['model_id'])!=pins['association']:raise DomainError('reference_conflict')
        checked_model(model,sid,request['model_id'],revision=request['model_revision_id'])
        if model!=pins['model']:raise DomainError('reference_conflict')
        if self._price_bases(db,sid,model)!=pins['price_bases']:raise DomainError('reference_conflict')
        records=self._evidence3(db,actor,sid,self._uses3(request,model))
        if records!=pins['evidence']:raise DomainError('reference_conflict')
        if candidate is not None:
            validate('ConfigurationCandidate'+request['schema_version'],candidate)
            if (candidate['evidence_snapshots']!=[evidence_snapshot(records[v]) for v in sorted(records)]
                    or candidate['assumptions']!=request['assumptions']
                    or candidate['general_context_evidence_version_ids']!=request['general_context_evidence_version_ids']):
                raise DomainError('reference_conflict')

    def preview(self,actor,sid,candidate):
        # New configurations use version 6 only: no criteria and no approach binding.
        if candidate.get('schema_version')!='6':raise DomainError('unsupported_record_version',422)
        return self._preview_resolved(actor,sid,candidate)[:3]

    def commit(self,actor,sid,body):
        if not isinstance(body,dict) or not isinstance(body.get('configuration'),dict) or body['configuration'].get('schema_version')!='6':
            raise DomainError('unsupported_record_version',422)
        return self._commit_resolved(actor,sid,body)

    def _preview_resolved(self,actor,sid,request):
        """Resolve one ConfigurationRequest6 into its candidate, private projection and proof."""
        from .scientific_configuration import PRIVATE_VERSIONS, project_scientific_configuration
        from .readiness import runtime_comparison
        request=deepcopy(request)
        validate('ConfigurationRequest6',request)
        if request['study_id']!=sid:raise DomainError('resource_not_found',404)
        study=self.store.study(actor,sid)
        caps=self.native_capabilities(actor,sid,strict=True)
        if not self.supports3(caps) or not self.supports_criteria_free(caps):raise DomainError('unsupported_capability',422)
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
        if 'context_override' in request:
            context.update({key:request['context_override'][key] for key in ('description','boundary')})
        targets=[(i['target']['instance_id'],i['target']['port_id']) for i in request['inputs']]
        if len(set(targets))!=len(targets):raise DomainError('invalid_configuration',422)
        if len({i['source_run_id'] for i in request['inputs'] if i['kind']=='run_result'})>64:
            raise DomainError('limit_exceeded',413)
        mid=request['model_id'];revision=request['model_revision_id']
        model=deepcopy(origin[0]['model_snapshot']) if origin else self.coordinator.read(actor,sid,mid,'/revisions/'+revision,response_schema='ModelRevisionResponse5')['data']
        validate('ModelRevisionRead5',model,remote=True)
        if model['model_id']!=mid or model['model_revision_id']!=revision or model['digest']!=digest({k:v for k,v in model.items() if k!='digest'}):
            raise DomainError('backend_unavailable',503,outcome='unknown')
        self.require_version_pair(request,model)
        if not self.coordinator.supports_quantities(caps):raise DomainError('unsupported_capability',422)
        if 'unit_declarations/1' in model['required_capabilities'] and not self.coordinator.supports_units(caps):raise DomainError('unsupported_capability',422)
        # Readiness gate (admission): complete active units or invalid_configuration 422.
        self._model_units(model)
        for source in model['source_files']:
            try:raw=base64.b64decode(source['bytes'],validate=True)
            except ValueError:raise DomainError('backend_unavailable',503,outcome='unknown') from None
            if hashlib.sha256(raw).hexdigest()!=source['sha256']:raise DomainError('backend_unavailable',503,outcome='unknown')
        checked_model(model,sid,mid,revision=revision)
        with self.store.connection() as db:evidence=self._evidence3(db,actor,sid,self._uses3(request,model))
        with self.store.connection() as db:price_bases=self._price_bases(db,sid,model)
        pins=dict(association=association,model=deepcopy(model),evidence=evidence,price_bases=price_bases)
        snapshots=[evidence_snapshot(evidence[v]) for v in sorted(evidence)]
        for item in request['inputs']:
            if not item['provenance']['statement'].strip():raise DomainError('invalid_configuration',422)
        resolver=ResultBindings(self.store);records={};resolved=[];sources={}
        for item in request['inputs']:
            target=(item['target']['instance_id'],item['target']['port_id'])
            if item['kind']=='literal':resolved.append({k:deepcopy(item[k]) for k in ('target','value','units','provenance')})
            else:
                source=resolver.resolve(actor,sid,item,records=records);sources[target]=source
                from .explanations import quantity_price_basis
                with self.store.connection() as db:
                    source_basis=quantity_price_basis(db,sid,records[item['source_run_id']][0]['model_snapshot'],item['source_output'])
                self._check_price_transfer(source_basis,price_bases.get(target))
                resolved.append(dict(target=deepcopy(item['target']),value=source['value'],units=source['units'],provenance=deepcopy(item['provenance'])))
        scientific=dict(schema_version=PRIVATE_VERSIONS['6'],study_id=sid,model_id=mid,model_revision_id=revision,name=request['name'],inputs=resolved,
            numerical=deepcopy(request['numerical']),context_snapshot=context,
            evidence_snapshots=snapshots,required_capabilities=list(model['required_capabilities']))
        validate('ModelingConfiguration5',scientific)
        proof=self.coordinator.read(actor,sid,mid,'/configuration-compatibility',method='POST',
            body=dict(model_revision_id=revision,configuration_candidate=scientific),request_schema='Compatibility2',response_schema='CompatibilityResultResponse')['data']
        validate('CompatibilityResult2',proof,remote=True)
        if (proof['candidate_digest']!=digest(scientific) or proof['model_digest']!=model['digest'] or proof['model_revision_id']!=revision
                or proof['required_capabilities']!=scientific['required_capabilities']):raise DomainError('backend_unavailable',503,outcome='unknown')
        interpretations={ (i['target']['instance_id'],i['target']['port_id']):i for i in proof['input_interpretations']}
        if len(interpretations)!=len(proof['input_interpretations']):raise DomainError('backend_unavailable',503,outcome='unknown')
        full=deepcopy(scientific)
        full['schema_version']='6'
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
                    # The single port-units rule; an instance without its definition is an
                    # invalid backend model.
                    try:bound_units=port_units(model)
                    except KeyError:raise DomainError('backend_unavailable',503,outcome='unknown') from None
                if (not port or conversion['source_units']!=item['units'] or conversion['destination_units']!=bound_units[(key[0],instance['definition_version_id'],key[1])]
                        or (isinstance(port['units'],dict) and conversion['catalog_digest']!=UNIT_CATALOG_DIGEST)
                        or not finite(conversion['factor']) or not finite(item['value']*conversion['factor'])
                        or conversion['destination_value']!=item['value']*conversion['factor']):
                    raise DomainError('backend_unavailable',503,outcome='unknown')
                item['result_binding']=dict(source_run_id=source['source_run_id'],source_output=source['source_output'],results_digest=source['results_digest'],
                    source_configuration_digest=source['source_configuration_digest'],original_value=source['value'],original_units=source['units'],conversion=deepcopy(conversion),labels=source['labels'])
        if sources:full['required_capabilities'].append('result_linked_inputs/1')
        full.update(context_source=deepcopy(request['context_source']),derivation=None,
            assumptions=deepcopy(request['assumptions']),general_context_evidence_version_ids=deepcopy(request['general_context_evidence_version_ids']))
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
        validate('ConfigurationCandidate6',full)
        if project_scientific_configuration(full)!=scientific:raise DomainError('reference_conflict')
        response=dict(schema_version='8',request_digest=digest(request),resolved_candidate=full,candidate_digest=digest(full),
            model_digest=model['digest'],compatibility=proof,changes=summaries,runtime_comparison=comparison)
        validate('ConfigurationPreview8',response)
        with self.store.connection() as db:self._recheck3(db,actor,sid,request,model,study,pins,full)
        return response,model,study,records,pins

    def _commit_resolved(self,actor,sid,body):
        body=deepcopy(body)
        validate('ConfigurationCommit6',body)
        payload={k:v for k,v in body.items() if k!='command_id'}
        old=self.store.replay(actor,sid,'configuration',body['command_id'],payload)
        if old:
            retained=old['result'];model=retained['model_snapshot'];candidate=retained['configuration']
            self.require_version_pair(candidate,model)
            self._model_units(model)
            request=body['configuration']
            checked_model(model,sid,request['model_id'],revision=request['model_revision_id'])
            with self.store.connection() as db:
                self.store.model_association(db,actor,sid,request['model_id'],write=True)
                evidence=self._evidence3(db,actor,sid,self._uses3(request,model))
                if candidate['evidence_snapshots']!=[evidence_snapshot(evidence[v]) for v in sorted(evidence)]:raise DomainError('reference_conflict')
                validate('FrozenConfigurationRead10',retained)
            return retained
        if body['configuration']['derivation'] is not None and (body['configuration_id'] is not None or body['expected_revision'] is not None):
            raise DomainError('reference_conflict',409)
        preview,model,study,records,pins=self._preview_resolved(actor,sid,body['configuration'])
        if not preview['compatibility']['compatible']:raise DomainError('invalid_configuration',422,fields=preview['compatibility']['diagnostics'])
        if preview['candidate_digest']!=body['expected_preview_digest']:raise DomainError('reference_conflict')
        candidate=preview['resolved_candidate']
        def save(db):
            self._recheck3(db,actor,sid,body['configuration'],model,study,pins,candidate)
            if digest(candidate)!=body['expected_preview_digest']:raise DomainError('reference_conflict')
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
            snapshot['digest']=digest(snapshot);validate('ConfigurationRevision6',snapshot)
            result=dict(schema_version='10' if model['schema_version']=='5' else '9',configuration=snapshot,model_snapshot=model,study_revision=study['revision'])
            validate('FrozenConfigurationRead10',result)
            db.execute('INSERT INTO configurations VALUES(?,?,?,?)',(revision,family,sid,json.dumps(result)))
            db.execute('INSERT INTO configuration_families VALUES(?,?,?) ON CONFLICT(configuration_id) DO UPDATE SET head=excluded.head',(family,sid,revision))
            return result
        return self.store.command(actor,sid,'configuration',body['command_id'],payload,save,
            attribute=_configuration_written)

    def read_page(self, actor, sid, *, cursor=None, limit=100, model_id=None, model_revision_id=None, summary=False):
        from .listing import window, configuration_filter
        with self.store.connection() as db:
            self.store.authorize(db, actor, sid)
            clauses, parameters = configuration_filter(sid, model_id, model_revision_id)
            where, values, order = window(db, 'configurations', 'configuration_revision_id', clauses, parameters, cursor, limit)
            projection = """c.configuration_revision_id, c.configuration_id,
                json_extract(c.payload,'$.configuration.model_id') AS model_id,
                json_extract(c.payload,'$.configuration.model_revision_id') AS model_revision_id,
                json_extract(c.payload,'$.configuration.name') AS name,
                json_array_length(c.payload,'$.configuration.inputs') AS input_count""" if summary else 'c.configuration_revision_id,c.payload'
            rows = db.execute(f'SELECT {projection} FROM configurations c WHERE {where} ORDER BY c.rowid {order} LIMIT ?', (*values, limit + 1)).fetchall()
        more = len(rows) > limit
        selected = rows[:limit]
        result = [dict(r) if summary else json.loads(r['payload']) for r in selected]
        return result, selected[-1]['configuration_revision_id'] if more else None

    def read(self,actor,sid,revision=None):
        with self.store.connection() as db:
            self.store.authorize(db,actor,sid)
            if revision:
                row=db.execute("SELECT payload FROM configurations WHERE study_id=? AND configuration_revision_id=?",(sid,revision)).fetchone()
                if not row:raise DomainError("resource_not_found",404)
                return json.loads(row["payload"])
            return [json.loads(r["payload"]) for r in db.execute("SELECT payload FROM configurations WHERE study_id=? ORDER BY rowid",(sid,))]
