"""Declared private transport and inert retained-failure handoff for UI proofs.

All app scientific writes use public commands or the existing Submissions
handoff. No native imports, candidate execution, database inserts or attestation
claim. Captured generator bytes are resealed solely to exercise retained UI data.
"""
from copy import deepcopy
import base64
import hashlib
import json
from urllib.parse import urlsplit
from hyprn_mvp_app.store import uid,digest,canonical
from hyprn_mvp_app.modeling import ModelingClient,validate
from test_assumption_authoring import PrivateTransport
from execution_fixtures import fixture,runtime_fixture

def sign(value):
    value['digest']=digest({k:v for k,v in value.items() if k!='digest'})
    return value

def package(model):
    rows=[]
    def add(path,raw,role,media):rows.append(dict(file_id=uid(),path=path,size=len(raw),sha256=hashlib.sha256(raw).hexdigest(),role=role,media_type=media))
    add('revisions/'+model['model_revision_id']+'.json',canonical(model),'model','application/json')
    for source in model['source_files']:add('sources/'+source['sha256']+'.py',base64.b64decode(source['bytes']),'source','text/x-python')
    return sign(dict(schema_version=model['schema_version'],source_service='Declared UI transport fixture',model_id=model['model_id'],model_revision_id=model['model_revision_id'],revisions=[model],files=rows,required_capabilities=model['required_capabilities'],license_notices=[]))

def example():
    case=fixture();model=case['frozen']['model_snapshot'];model.update(schema_version='2',model_id=uid(),model_revision_id=uid(),originating_draft_revision=uid(),assumptions=[])
    definition=deepcopy(model['definitions'][0]);definition.update(name='Response law',definition_id=uid(),definition_version_id=uid())
    definition['ports']=[dict(port_id=uid(),definition_version_id=definition['definition_version_id'],direction=direction,name=symbol,code_symbol=symbol,value_type='real_scalar',units='') for direction,symbol in [('input','x'),('input','z'),('output','u'),('output','v')]]
    raw=b"# Retained authored source; never executed by the UI fixture.\noutputs['u'] = inputs['x'] + inputs['z']\noutputs['v'] = inputs['x'] - inputs['z']\n"
    source=dict(encoding='base64',media_type='text/x-python',bytes=base64.b64encode(raw).decode(),sha256=hashlib.sha256(raw).hexdigest());definition['source_refs']=[source['sha256']]
    root=deepcopy(definition);root.update(definition_id=uid(),definition_version_id=uid(),kind='composite',name='Response investigation',ports=[],source_refs=[])
    root_id,a,b=uid(),uid(),uid();model.update(root_instance_id=root_id,definitions=[root,definition],instances=[dict(instance_id=root_id,definition_version_id=root['definition_version_id'],name='Response investigation'),*[dict(instance_id=i,definition_version_id=definition['definition_version_id'],name='Response') for i in (a,b)]],ports=definition['ports'],source_files=[source],connections=[dict(connection_id=uid(),source_ref=dict(instance_id=a,port_id=definition['ports'][j+2]['port_id']),target_ref=dict(instance_id=b,port_id=definition['ports'][j]['port_id'])) for j in (0,1)])
    model['assumptions']=[dict(assumption_id=uid(),owner=dict(kind='model'),statement='A scalar approximation is appropriate for the declared conditions.',evidence_links=[])]
    sign(model);validate('ModelRevision',model)
    return package(model)

class Models:
    def __init__(self,store):self.store=store;self.transports={};self.offline=False;self.client=ModelingClient('http://private.invalid/modeling/1',b't'*32,transport=self.call)
    def call(self,method,path,raw,headers):
        if self.offline:raise OSError('Declared model outage')
        body=json.loads(raw) if raw else None
        if '/commands/' in path:
            command=urlsplit(path).path.split('/commands/')[1]
            transport=next((t for t in self.transports.values() if command in t.receipts),None)
            if transport:return transport(method,path,raw,headers)
            return 200,dict(schema_version='1',request_id=uid(),data=dict(command_id=command,state='absent'))
        if path.endswith('/imports'):
            selected=body['package']['revisions'][-1];mid=selected['model_id'];transport=PrivateTransport(self.store,body['study_id'])
            transport.revisions={m['model_revision_id']:deepcopy(m) for m in body['package']['revisions']}
            transport.draft={k:deepcopy(v) for k,v in selected.items() if k not in {'model_revision_id','parent_model_revision_id','originating_draft_revision','digest'}}
            transport.draft.update(study_id=body['study_id'],name=selected['definitions'][0]['name'],draft_revision=uid());self.transports[mid]=transport
        elif path.endswith('/capabilities'):
            transport=PrivateTransport(self.store,uid());transport.caps['capabilities'].append({**transport.caps['capabilities'][0], 'id':'resolved_configuration','version':'3'})
            return 200,dict(schema_version='1',request_id=uid(),data=transport.caps)
        else:
            mid=path.split('/models/')[1].split('/')[0];transport=self.transports[mid]
        if method=='GET' and urlsplit(path).path.endswith('/revisions'):
            return 200,dict(schema_version='1',request_id=uid(),data=dict(items=[{k:m[k] for k in ('model_revision_id','parent_model_revision_id','originating_draft_revision','digest')} for m in transport.revisions.values()],next_cursor=None))
        if path.endswith('/configuration-compatibility'):
            candidate=body['configuration_candidate'];model=transport.revisions[candidate['model_revision_id']]
            proof=dict(schema_version='2',validator_identity='declared-ui-fixture',compatible=True,diagnostics=[],candidate_digest=digest(candidate),model_digest=model['digest'],model_revision_id=model['model_revision_id'],required_capabilities=candidate['required_capabilities'],input_interpretations=[dict(target=i['target'],conversion=dict(policy='openmdao-linear-catalog-1',catalog_digest='a'*64,source_units=i['units'],destination_units=i['units'],factor=1.0,destination_value=i['value'])) for i in candidate['inputs']])
            validate('CompatibilityResult2',proof);return 200,dict(schema_version='1',request_id=uid(),data=proof)
        return transport(method,path,raw,headers)

def failure_case():
    case=fixture();m=case['frozen']['model_snapshot'];m.update(schema_version='2',model_id=uid(),model_revision_id=uid(),originating_draft_revision=uid(),assumptions=[])
    m['root_instance_id']=m['instances'][0]['instance_id'];m['ports']=[p for d in m['definitions'] for p in d['ports']];sign(m)
    return case

def retain_failure(store,actor,sid,run_id,case,*,complete=False,uncertain=False):
    from hyprn_mvp_app.execution import Submissions,executable_digest
    from hyprn_mvp_app.scientific_configuration import project_scientific_configuration
    class RetainedFailure:
        def require_attestation(self):return True # Explicit test double, no runtime certification.
        def bundle_runtime(self):return runtime_fixture()
        def launch_budgeted(self, bundle, request, wall_seconds):
            return self.launch(bundle, request)
        def launch(self,bundle,request):
            if uncertain:raise OSError('Declared lost launch response; execution state unknown')
            self.record=dict(store_uuid=uid(),process_uuid=uid(),process_state='finished',exit_status=1,request=deepcopy(request),bundle=deepcopy(bundle),results=None,assessment=None,artifacts={},errors=[dict(code='missing_results',partial=True)])
            if complete:
                # Complete synthetic failure evidence, never a numerical success.
                manifest=bundle['manifest'];config=json.loads(bundle['files']['configuration.json'])
                outputs=json.loads(case['files'][case['prepared']['entrypoint']['bindings_path']])['outputs']
                result=dict(schema_version='1',run_id=request['run_id'],bundle_digest=manifest['bundle_digest'],execution=dict(state='failed',exit_code=1,message='Declared UI fixture: terminal failure; no candidate executed'),
                    convergence=dict(state='not_applicable',diagnostics_ref=None),optimization=dict(termination='not_applicable',feasibility='not_applicable'),
                    completeness=dict(expected=len(outputs),available=0,failed=len(outputs),unavailable=len(outputs)),
                    outputs=[dict(target=o['target'],value=None,units=o['units'],availability='unavailable',reason='Declared fixture failure',producer_completed=False,assigned=False) for o in outputs],
                    criteria=[dict(criterion_id=c['criterion_id'],outcome='unresolved',reason='required_output_unavailable') for c in config['criteria']],applicability=dict(state='unassessed',evidence_refs=[]),artifacts=[])
                validate('RetainedResults',result);self.record.update(results=result,errors=[])
            return {k:self.record[k] for k in ('store_uuid','process_uuid','process_state','exit_status')}
        def read_record(self,request,association):
            assert request==self.record['request'] and all(self.record[k]==v for k,v in association.items());return deepcopy(self.record)
    def prepare(_actor,_sid,_command,frozen):
        assert (_actor,_sid)==(actor,sid)
        prepared=deepcopy(case['prepared']);files=deepcopy(case['files']);m=frozen['model_snapshot'];c=frozen['configuration'];files['model.json']=canonical(m)
        prepared['model_package_manifest']=package(m)
        for row in prepared['files']:
            raw=files[row['path']];row.update(size=len(raw),sha256=hashlib.sha256(raw).hexdigest())
        prepared.update(model_id=m['model_id'],model_revision_id=m['model_revision_id'],model_digest=m['digest'],configuration_revision_id=c['configuration_revision_id'],configuration_digest=project_scientific_configuration(c)['digest'])
        prepared['executable_content_digest']=executable_digest(prepared);prepared['prepared_digest']=digest({k:v for k,v in prepared.items() if k!='prepared_digest'})
        return prepared,files
    service=Submissions(store,prepare,RetainedFailure());service.dispatch(run_id)
    return service.read(actor,sid,run_id)


def synthetic_archive(preflight,records):
    """Data-only archive transport for browser scope/packaging proof, NOT AiiDA proof.

    Uses a valid empty SQLite container and declared inventory. Native row semantics
    are deliberately not asserted; Plan21.1 independently exercises pinned AiiDA.
    """
    import io, sqlite3, zipfile
    from uuid import UUID, uuid5
    from hyprn_mvp_app.computational_export import OMISSIONS
    nodes=[];links=[];repositories=[];repository_bytes={}
    for c in preflight['computations']:
        process=c['association']['process_uuid']
        def node(identity,kind,attributes,label):
            nodes.append(dict(uuid=identity,node_type=kind,attributes_digest=attributes,extras_digest=digest({}),label=label,description='Declared browser fixture'))
        node(process,'process.calculation.calcjob.CalcJobNode.',digest({}),'Declared terminal process')
        for label,attributes,incoming in [('request',digest(c['request']),True),('results',c['results_digest'],False)]:
            identity=str(uuid5(UUID(process),label));node(identity,'data.core.dict.Dict.',attributes,label)
            links.append(dict(source_uuid=identity if incoming else process,target_uuid=process if incoming else identity,label=label,type='input_calc' if incoming else 'create'))
        folder=str(uuid5(UUID(process),'frozen_bundle'));node(folder,'data.core.folder.FolderData.',digest({}),'Frozen bundle')
        links.append(dict(source_uuid=folder,target_uuid=process,label='frozen_bundle',type='input_calc'))
        bundle=records[c['run_id']][1]['bundle'];files={p:base64.b64decode(v) for p,v in bundle['files'].items()};files['manifest.json']=canonical(bundle['manifest'])
        for path,raw in sorted(files.items()):
            sha=hashlib.sha256(raw).hexdigest();repositories.append(dict(node_uuid=folder,path=path,size=len(raw),sha256=sha));repository_bytes[sha]=raw
    inventory=dict(nodes=nodes,links=links,computers=[],users=[],repositories=repositories,omissions=OMISSIONS)
    rules=dict(input_calc_forward=False,create_backward=True,return_backward=False,input_work_forward=False,call_calc_backward=False,call_work_backward=False,input_calc_backward=True,create_forward=True,return_forward=True,input_work_backward=True,call_calc_forward=True,call_work_forward=True)
    metadata=dict(export_version='main_0001',aiida_version='2.9.3',key_format='sha256',compression=6,ctime='2026-10-10T00:00:00+00:00',creation_parameters=dict(entities_starting_set={'node':sorted(c['association']['process_uuid'] for c in preflight['computations'] if c['role']=='selected')},include_authinfos=False,include_comments=False,include_logs=False,graph_traversal_rules=rules))
    db=sqlite3.connect(':memory:');db.execute('CREATE TABLE declared_browser_fixture (notice TEXT)');db.execute('INSERT INTO declared_browser_fixture VALUES (?)',('Not a native execution or native archive-row proof',));raw_db=db.serialize();db.close()
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w') as z:
        z.writestr('metadata.json',canonical(metadata));z.writestr('db.sqlite3',raw_db)
        for sha,raw in sorted(repository_bytes.items()):z.writestr('repo/'+sha,raw)
    raw=out.getvalue()
    return dict(schema_version='1',origin_store_uuid=preflight['origin_store_uuid'],inventory=inventory,inventory_digest=digest(inventory),archive_sha256=hashlib.sha256(raw).hexdigest(),archive_size=len(raw),archive_base64=base64.b64encode(raw).decode())


class SamplingModels(Models):
    """Declared read/compatibility transport for input-first sampling browser tests.

    Snapshots originate in the scoped fixture's captured records. Input values still go
    through the public configuration preview and commit, never through this transport.
    """

    def call(self, method, path, raw, headers):
        from criteria_free import CRITERIA_FREE_CAPABILITY
        from hyprn_mvp_app.modeling import UNIT_CATALOG_DIGEST
        if path.endswith('/capabilities'):
            transport = PrivateTransport(self.store, uid())
            caps = transport.caps
            caps['contract_versions'] += ['1.3', '1.4']
            caps['schema_versions'] += ['3', '4']
            base = caps['capabilities'][0]
            caps['capabilities'] += [
                dict(base, id='resolved_configuration', version='3'),
                dict(base, id='unit_declarations'), dict(base, id='quantity_definitions'),
                deepcopy(CRITERIA_FREE_CAPABILITY),
            ]
            return 200, dict(schema_version='1', request_id=uid(), data=caps)
        if '/models/' in path:
            mid = path.split('/models/')[1].split('/')[0]
            if mid not in self.transports:
                with self.store.connection() as db:
                    records = [json.loads(r[0]) for r in db.execute(
                        'SELECT payload FROM configurations'
                    )]
                for frozen in records:
                    model = frozen['model_snapshot']
                    if model['model_id'] != mid:
                        continue
                    transport = self.transports.setdefault(mid, PrivateTransport(
                        self.store, frozen['configuration']['study_id']))
                    transport.revisions[model['model_revision_id']] = deepcopy(model)
                    transport.draft = {k: deepcopy(v) for k, v in model.items() if k not in {
                        'model_revision_id', 'parent_model_revision_id',
                        'originating_draft_revision', 'digest'}}
                    transport.draft.update(study_id=transport.sid, name='Response model',
                                           draft_revision=model['originating_draft_revision'])
        status, response = super().call(method, path, raw, headers)
        if path.endswith('/configuration-compatibility'):
            for interpretation in response['data']['input_interpretations']:
                interpretation['conversion']['catalog_digest'] = UNIT_CATALOG_DIGEST
        return status, response
