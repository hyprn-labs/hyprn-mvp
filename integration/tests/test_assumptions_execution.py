"""Bundle4 admission only; parsed execution is proven by the native execution tests."""
import copy
import io
import json

import pytest
from aiida import orm
from aiida.common.links import LinkType
from checks import NATIVE_BACKEND, PROJECTION_SCOPE
from hyprn_mvp_app.store import canonical,digest,uid,DomainError
from hyprn_mvp_app.execution import assemble_bundle,executable_digest,validate_retained_bundle
from hyprn_mvp_app.scientific_configuration import project_scientific_configuration
from hyprn_mvp_app.result_bindings import ResultBindings
from hyprn_mvp_integration import launcher,worker
from hyprn_mvp_integration.calculation import ScalarCalculation,NativeExecution
from execution_fixtures import fixture,runtime_fixture
from test_result_dependencies import source,linked_bundle,rehash


def repin(case):
    model=case['frozen']['model_snapshot'];config=case['frozen']['configuration'];prepared=case['prepared']
    model['digest']=digest({k:v for k,v in model.items() if k!='digest'})
    config['digest']=digest({k:v for k,v in config.items() if k!='digest'})
    case['files']['model.json']=canonical(model)
    package=prepared['model_package_manifest'];package['schema_version']=model['schema_version']
    package['revisions'][-1]=copy.deepcopy(model)
    for row in package['files']:
        if row['path']=='revisions/'+model['model_revision_id']+'.json':
            row.update(size=len(canonical(model)),sha256=__import__('hashlib').sha256(canonical(model)).hexdigest())
    package['digest']=digest({k:v for k,v in package.items() if k!='digest'})
    for row in prepared['files']:
        raw=case['files'][row['path']];row.update(size=len(raw),sha256=__import__('hashlib').sha256(raw).hexdigest())
    prepared.update(model_digest=model['digest'],configuration_revision_id=config['configuration_revision_id'],
        configuration_digest=project_scientific_configuration(config)['digest'])
    prepared['executable_content_digest']=executable_digest(prepared)
    prepared['prepared_digest']=digest({k:v for k,v in prepared.items() if k!='prepared_digest'})


def case4(model_version='2',linked=None):
    case=fixture();config=case['frozen']['configuration'];model=case['frozen']['model_snapshot']
    deps=dict(schema_version='1',sources=[],mappings=[])
    if linked:
        bundle,_=linked_bundle(linked)
        config=json.loads(bundle['files']['configuration.json']);case['frozen']['configuration']=config
        deps=json.loads(bundle['files']['result-dependencies.json'])
    config.update(schema_version='3',context_source=dict(kind='current_study',expected_study_revision='fixture:1'),derivation=None,
        assumptions=[],general_context_evidence_version_ids=[])
    for item in config['inputs']:item.setdefault('result_binding',None)
    config['required_capabilities'].append('configuration_assumptions/1')
    eid=uid();sid=config['study_id']
    evidence=dict(evidence_schema_version='3',evidence_id=uid(),evidence_version_id=eid,parent_evidence_version_id=uid(),
        study_id=sid,title='Calibration evidence',kind='note',content='An inert exact observation',source_refs=['https://never-fetch.invalid'],
        resource_scope=dict(scope_version='1',kind='study',study_id=sid),
        recorded_context=dict(schema_version='1',label='Recorded study',resource_labels=[dict(kind='study',resource_id=sid,version_id=None,name='Original study')]))
    links=[dict(evidence_version_id=eid,relation=r) for r in ('supports','challenges')]
    config['assumptions']=[dict(assumption_id=uid(),statement='Configuration assumption',evidence_links=copy.deepcopy(links))]
    config['general_context_evidence_version_ids']=[eid]
    config['inputs'][0]['provenance']['evidence_version_ids']=[eid]
    config['evidence_snapshots']=[evidence]
    model['schema_version']=model_version
    if model_version=='2':
        model['assumptions']=[dict(assumption_id=uid(),owner=dict(kind='model'),statement='Model assumption',evidence_links=links),
            dict(assumption_id=uid(),owner=dict(kind='instance',instance_id=model['instances'][0]['instance_id']),statement='Local assumption',evidence_links=[])]
    repin(case)
    return case,deps


def assembled(case,deps):
    bundle=assemble_bundle(uid(),case['prepared'],case['files'],case['frozen'],runtime_fixture(),deps)
    request=dict(run_id=bundle['manifest']['run_id'],scope=case['frozen']['configuration']['study_id'],command_id=uid(),payload_digest='a'*64,bundle_digest=bundle['manifest']['bundle_digest'])
    return bundle,request


def legacy_pairing_case(version,assumptions=None):
    """Re-pin every affected digest so rejection must enforce the version pair."""
    case=fixture();config=case['frozen']['configuration'];model=case['frozen']['model_snapshot']
    deps=dict(schema_version='1',sources=[],mappings=[])
    if version=='2':
        config.update(schema_version='2',context_source=dict(kind='current_study',expected_study_revision='fixture:1'),derivation=None)
        for item in config['inputs']:item['result_binding']=None
        repin(case)
    bundle,request=assembled(case,deps if version=='2' else None)
    if assumptions is not None:
        model.update(schema_version='2',assumptions=[] if assumptions=='empty' else [dict(
            assumption_id=uid(),owner=dict(kind='model'),statement='Unresolved imported assumption',
            evidence_links=[dict(evidence_version_id=uid(),relation='supports')])])
        repin(case)
        prepared=case['prepared']
        bundle['manifest'].update(model_digest=model['digest'],prepared_digest=prepared['prepared_digest'],
            executable_content_digest=prepared['executable_content_digest'])
        rehash(bundle,{'model.json':model,'preparation.json':prepared})
        request['bundle_digest']=bundle['manifest']['bundle_digest']
    return case,bundle,request


@pytest.mark.parametrize('version',['1','2'])
@pytest.mark.parametrize('assumptions',['unknown_citation','empty'])
@pytest.mark.parametrize('boundary',['frozen','submission','native'])
def test_legacy_model2_pairing_refused_at_app_admission_without_allocation(tmp_path,version,assumptions,boundary):
    from hyprn_mvp_app.execution import validate_frozen_configuration,Submissions
    from hyprn_mvp_app.store import Store
    from test_submission import NativeDouble
    case,bundle,request=legacy_pairing_case(version,assumptions)
    before=orm.QueryBuilder(backend=NATIVE_BACKEND).append(orm.ProcessNode).count()
    if boundary=='frozen':
        with pytest.raises(ValueError,match='version pairing'):validate_frozen_configuration(case['frozen'])
    elif boundary=='native':
        class Admission(NativeExecution):
            def require_attestation(self):return None
            def bundle_runtime(self):return runtime_fixture()
        native=Admission(backend=NATIVE_BACKEND,root=PROJECTION_SCOPE.root)
        with pytest.raises(ValueError,match='version pairing'):native.launch(bundle,request)
    else:
        store=Store(tmp_path/'app.sqlite');actor=uid();study=store.create_study(actor,uid(),'Pairing admission')
        config=case['frozen']['configuration'];config['study_id']=study['study_id'];repin(case)
        with store.connection(write=True) as db:
            db.execute('INSERT INTO configurations VALUES(?,?,?,?)',(config['configuration_revision_id'],config['configuration_id'],study['study_id'],json.dumps(case['frozen'])))
        native=NativeDouble()
        service=Submissions(store,lambda *args:pytest.fail('Invalid pairing reached preparation'),native)
        with pytest.raises(ValueError,match='version pairing'):
            service.submit(actor,study['study_id'],dict(command_id=uid(),configuration_revision_id=config['configuration_revision_id']))
        with store.connection() as db:
            assert db.execute('SELECT count(*) FROM run_associations').fetchone()[0]==0
            assert db.execute('SELECT count(*) FROM outbox').fetchone()[0]==0
        assert native.launches==0
    assert orm.QueryBuilder(backend=NATIVE_BACKEND).append(orm.ProcessNode).count()==before


@pytest.mark.parametrize('version',['1','2'])
@pytest.mark.parametrize('assumptions',['unknown_citation','empty'])
def test_worker_refuses_consistently_rehashed_legacy_model2_before_import(tmp_path,monkeypatch,version,assumptions):
    case,bundle,request=legacy_pairing_case(version,assumptions)
    directory=tmp_path/'bad-pair';launcher.write_bundle(bundle,directory)
    monkeypatch.setattr(worker,'load_program',lambda *args:pytest.fail('Imported invalid candidate'))
    with pytest.raises(ValueError,match='version pairing'):worker.read_inputs(directory,request['bundle_digest'])


@pytest.mark.parametrize('version',['1','2'])
def test_model1_legacy_pairs_remain_readable_and_admissible(tmp_path,version):
    case,bundle,request=legacy_pairing_case(version)
    validate_retained_bundle(bundle,request,case['frozen'])
    launcher.verify_execution_bundle(bundle,request,runtime_fixture())
    directory=tmp_path/'legacy';launcher.write_bundle(bundle,directory)
    assert worker.read_inputs(directory,request['bundle_digest'])[2]==case['frozen']['configuration']


def calc_inputs(bundle,request,upstream=None,cache=True):
    folder=orm.FolderData(backend=NATIVE_BACKEND)
    for path,raw in {**bundle['files'],'manifest.json':canonical(bundle['manifest'])}.items():
        folder.base.repository.put_object_from_filelike(io.BytesIO(raw),path)
    return dict(frozen_bundle=folder,request=orm.Dict(dict=request,backend=NATIVE_BACKEND),
        upstream_results=upstream or {},metadata=dict(disable_cache=cache))


@pytest.mark.parametrize('model_version',['1','2'])
def test_exact_bundle4_admission_without_candidate_import(tmp_path,monkeypatch,model_version):
    case,deps=case4(model_version);bundle,request=assembled(case,deps)
    original=fixture()
    assert {p:b for p,b in case['files'].items() if p.startswith('generated/')}=={p:b for p,b in original['files'].items() if p.startswith('generated/')}
    assert case['prepared']['entrypoint']==original['prepared']['entrypoint']
    assert bundle['manifest']['schema_version']=='4'
    assert json.loads(bundle['files']['result-dependencies.json'])==deps
    assert ResultBindings(None).verify_configuration('actor',request['scope'],case['frozen']['configuration'])=={}
    assert ResultBindings(None).dependencies('actor',request['scope'],case['frozen']['configuration'],None)==deps
    monkeypatch.setattr(worker,'load_program',lambda *a:pytest.fail('Admission imported candidate'))
    validate_retained_bundle(bundle,request,case['frozen'])
    launcher.verify_execution_bundle(bundle,request,runtime_fixture())
    directory=tmp_path/'valid';launcher.write_bundle(bundle,directory)
    assert worker.read_inputs(directory,request['bundle_digest'])[2]==case['frozen']['configuration']
    before=orm.QueryBuilder(backend=NATIVE_BACKEND).append(orm.ProcessNode).count()
    assert ScalarCalculation.spec().inputs.validate(calc_inputs(bundle,request)) is None
    assert orm.QueryBuilder(backend=NATIVE_BACKEND).append(orm.ProcessNode).count()==before


@pytest.mark.parametrize('field',['duplicate','owner','root_owner','missing','extra','foreign','scope','relation','uuid','parent','label','capability'])
def test_assembly_semantic_refusals(field):
    case,deps=case4();config=case['frozen']['configuration'];model=case['frozen']['model_snapshot']
    if field=='duplicate':config['assumptions'].append(copy.deepcopy(config['assumptions'][0]))
    elif field in ('owner','root_owner'):model['assumptions'][1]['owner']['instance_id']=uid() if field=='owner' else model['root_instance_id']
    elif field=='missing':config['evidence_snapshots']=[]
    elif field=='extra':config['evidence_snapshots'].append(dict(config['evidence_snapshots'][0],evidence_version_id=uid()))
    elif field=='foreign':config['evidence_snapshots'][0]['study_id']=uid()
    elif field=='scope':config['evidence_snapshots'][0]['resource_scope']['study_id']=uid()
    elif field=='relation':config['assumptions'][0]['evidence_links'].append(copy.deepcopy(config['assumptions'][0]['evidence_links'][0]))
    elif field=='uuid':model['assumptions'][0]['assumption_id']='invalid'
    elif field=='parent':config['evidence_snapshots'][0]['parent_evidence_version_id']=config['evidence_snapshots'][0]['evidence_version_id']
    elif field=='label':config['evidence_snapshots'][0]['recorded_context']['resource_labels'][0]['resource_id']=uid()
    else:config['required_capabilities'].append('unreviewed/1')
    with pytest.raises((ValueError,DomainError)):
        repin(case);assembled(case,deps)


@pytest.mark.parametrize('field',['relationship','title','label','parent','owner','missing','projection','model_source','pair','dependencies','descriptor'])
def test_each_admission_rejects_rehashed_partial_tampering_before_storage(tmp_path,field):
    case,deps=case4();bundle,request=assembled(case,deps);changes={}
    config=copy.deepcopy(case['frozen']['configuration']);model=copy.deepcopy(case['frozen']['model_snapshot'])
    if field=='relationship':config['assumptions'][0]['evidence_links'][0]['relation']='context'
    elif field=='title':config['evidence_snapshots'][0]['title']='Changed'
    elif field=='label':config['evidence_snapshots'][0]['recorded_context']['label']='Changed'
    elif field=='parent':config['evidence_snapshots'][0]['parent_evidence_version_id']=uid()
    elif field=='missing':config['evidence_snapshots']=[]
    elif field in ('owner','model_source'):
        if field=='owner':model['assumptions'][1]['owner']['instance_id']=uid()
        else:model['source_files'][0]['bytes']='eA=='
        model['digest']=digest({k:v for k,v in model.items() if k!='digest'})
        bundle['manifest']['model_digest']=model['digest'];changes['model.json']=model
    elif field=='projection':
        private=json.loads(bundle['files']['modeling-configuration.json']);private['name']='Changed'
        private['digest']=digest({k:v for k,v in private.items() if k!='digest'});changes['modeling-configuration.json']=private
    elif field=='pair':bundle['manifest']['schema_version']='3'
    elif field=='dependencies':changes['result-dependencies.json']=dict(schema_version='2',sources=[],mappings=[])
    else:bundle['manifest']['result_dependencies']['size']+=1
    if field in ('relationship','title','label','parent','missing'):
        config['digest']=digest({k:v for k,v in config.items() if k!='digest'})
        bundle['manifest']['configuration_digest']=config['digest'];changes['configuration.json']=config
    rehash(bundle,changes)
    # An otherwise valid app-only relationship change is bound by the original
    # request, not by a private projection that intentionally removes assumptions.
    if field!='relationship':request['bundle_digest']=bundle['manifest']['bundle_digest']
    with pytest.raises(ValueError):launcher.verify_execution_bundle(bundle,request,runtime_fixture())
    directory=tmp_path/'bad';launcher.write_bundle(bundle,directory)
    with pytest.raises(ValueError):worker.read_inputs(directory,request['bundle_digest'])
    before=orm.QueryBuilder(backend=NATIVE_BACKEND).append(orm.ProcessNode).count()
    assert ScalarCalculation.spec().inputs.validate(calc_inputs(bundle,request)) is not None
    class Admission(NativeExecution):
        def require_attestation(self):return None
        def bundle_runtime(self):return runtime_fixture()
    native=Admission(backend=NATIVE_BACKEND,root=PROJECTION_SCOPE.root)
    with pytest.raises(ValueError):native.launch(bundle,request)
    assert orm.QueryBuilder(backend=NATIVE_BACKEND).append(orm.ProcessNode).count()==before


def test_calcjob_original_stored_upstream_and_cache_gate(source):
    case,deps=case4(linked=source);bundle,request=assembled(case,deps)
    upstream={deps['sources'][0]['label']:source['results']}
    assert ScalarCalculation.spec().inputs.validate(calc_inputs(bundle,request,upstream)) is None
    for inputs in (calc_inputs(bundle,request),calc_inputs(bundle,request,upstream,False),
        calc_inputs(bundle,request,{deps['sources'][0]['label']:orm.Dict(dict=source['results'].get_dict(),backend=NATIVE_BACKEND).store()})):
        assert ScalarCalculation.spec().inputs.validate(inputs) is not None


@pytest.mark.parametrize('field',['creator','request','digest','value','source_configuration'])
def test_direct_calcjob_source_integrity_gate(source,field):
    case,deps=case4(linked=source)
    if field=='source_configuration':
        case['frozen']['configuration']['inputs'][0]['result_binding']['source_configuration_digest']='a'*64;repin(case)
    elif field=='value':
        for item in case['frozen']['configuration']['inputs']:
            item['value']+=1;binding=item['result_binding'];binding['original_value']+=1;binding['conversion']['destination_value']+=1
        for row in deps['mappings']:row['original_value']+=1;row['conversion']['destination_value']+=1
        repin(case)
    elif field=='request':deps['sources'][0]['request']['payload_digest']='b'*64
    elif field=='digest':
        deps['sources'][0]['results_digest']='d'*64
        for row in deps['mappings']:row['results_digest']='d'*64
        for row in case['frozen']['configuration']['inputs']:row['result_binding']['results_digest']='d'*64
        repin(case)
    elif field=='creator':deps['sources'][0]['association']['process_uuid']=uid()
    bundle,request=assembled(case,deps)
    before=orm.QueryBuilder(backend=NATIVE_BACKEND).append(orm.ProcessNode).count()
    assert ScalarCalculation.spec().inputs.validate(calc_inputs(bundle,request,{deps['sources'][0]['label']:source['results']})) is not None
    assert orm.QueryBuilder(backend=NATIVE_BACKEND).append(orm.ProcessNode).count()==before


@pytest.mark.parametrize('version',['1','5','unknown'])
def test_result_binding_check_keeps_unsupported_versions_closed(version):
    case,_=case4();config=case['frozen']['configuration'];config['schema_version']=version
    with pytest.raises(ValueError):ResultBindings(None).verify_configuration('actor',config['study_id'],config)

def test_result_binding_check_rejects_malformed_supported_configuration4():
    case,_=case4();config=case['frozen']['configuration'];config['schema_version']='4'
    with pytest.raises(DomainError) as error:
        ResultBindings(None).verify_configuration('actor',config['study_id'],config)
    assert error.value.code=='invalid_request'


@pytest.mark.parametrize('field',['duplicate','owner','root_owner','foreign','label','parent','missing','extra','relation','capability'])
def test_independent_worker_semantics_even_with_recomputed_pins(tmp_path,field):
    case,deps=case4();bundle,request=assembled(case,deps)
    config=case['frozen']['configuration'];model=case['frozen']['model_snapshot']
    if field=='duplicate':config['assumptions'].append(dict(config['assumptions'][0],statement='Distinct text, duplicate identity'))
    elif field in ('owner','root_owner'):model['assumptions'][1]['owner']['instance_id']=uid() if field=='owner' else model['root_instance_id']
    elif field=='foreign':config['evidence_snapshots'][0]['study_id']=uid()
    elif field=='label':config['evidence_snapshots'][0]['recorded_context']['resource_labels'][0]['resource_id']=uid()
    elif field=='parent':config['evidence_snapshots'][0]['parent_evidence_version_id']=config['evidence_snapshots'][0]['evidence_version_id']
    elif field=='missing':config['evidence_snapshots']=[]
    elif field=='extra':config['evidence_snapshots'].append(dict(config['evidence_snapshots'][0],evidence_version_id=uid()));config['evidence_snapshots'].sort(key=lambda r:r['evidence_version_id'])
    elif field=='relation':config['assumptions'][0]['evidence_links'][0]['relation']='invented'
    else:config['required_capabilities'].append('unreviewed/1')
    # Intentionally bypass assembly's closed/schema validation at this boundary.
    config['digest']=digest({k:v for k,v in config.items() if k!='digest'})
    if field!='relation':repin(case)
    private=copy.deepcopy(config)
    for key in ('context_source','derivation','assumptions','general_context_evidence_version_ids','digest'):private.pop(key)
    for row in private['inputs']:row.pop('result_binding')
    private['required_capabilities']=[v for v in private['required_capabilities'] if v not in ('configuration_assumptions/1','result_linked_inputs/1')]
    private['digest']=digest(private)
    prepared=case['prepared'];prepared['configuration_digest']=private['digest'];prepared['executable_content_digest']=executable_digest(prepared)
    prepared['prepared_digest']=digest({k:v for k,v in prepared.items() if k!='prepared_digest'})
    bundle['manifest'].update(configuration_digest=config['digest'],model_digest=model['digest'],modeling_configuration_digest=private['digest'],
        prepared_digest=prepared['prepared_digest'],executable_content_digest=prepared['executable_content_digest'])
    rehash(bundle,{'configuration.json':config,'modeling-configuration.json':private,'model.json':model,'preparation.json':prepared,
        'evidence/index.json':config['evidence_snapshots'],'context.json':config['context_snapshot']})
    directory=tmp_path/'independent';launcher.write_bundle(bundle,directory)
    with pytest.raises(ValueError):worker.read_inputs(directory,bundle['manifest']['bundle_digest'])


def test_launch_stores_original_upstream_once_and_stops_before_execution(source,monkeypatch):
    case,deps=case4(linked=source);bundle,request=assembled(case,deps)
    class Admission(NativeExecution):
        def require_attestation(self):return None
        def bundle_runtime(self):return runtime_fixture()
    native=Admission(backend=NATIVE_BACKEND,root=PROJECTION_SCOPE.root)
    wrapper=PROJECTION_SCOPE.root/'launch-worker'
    wrapper.write_text('#!/bin/sh\nexit 97\n');wrapper.chmod(0o700)
    computer=orm.Computer(label='ae-admission-only',hostname='localhost',transport_type='core.local',
        scheduler_type='core.direct',workdir=str(PROJECTION_SCOPE.root/'tmp/work/{username}'),backend=NATIVE_BACKEND).store()
    orm.InstalledCode(label='hyprn-mvp-scalar',computer=computer,filepath_executable=str(wrapper),
        default_calc_job_plugin='hyprn_mvp.scalar',backend=NATIVE_BACKEND).store()
    def stop(point):
        if point=='after_node':raise RuntimeError('Admission check stops before execution')
    native.fault=stop
    original=orm.CalcJobNode.store;observed=[]
    def before_store(node,*args,**kwargs):
        assert not node.is_stored
        inputs=node.base.links.get_incoming(link_type=LinkType.INPUT_CALC).all()
        assert [(link.link_label,link.node.uuid) for link in inputs if link.link_label.startswith('upstream_results__')]==[
            ('upstream_results__'+deps['sources'][0]['label'],source['results'].uuid)]
        observed.append(node.uuid)
        return original(node,*args,**kwargs)
    monkeypatch.setattr(orm.CalcJobNode,'store',before_store)
    before=canonical(source['results'].get_dict())
    with pytest.raises(RuntimeError,match='stops before execution'):native.launch(bundle,request)
    assert len(observed)==1 and native.matches(request)==observed
    node=orm.load_node(observed[0])
    assert not node.base.caching.is_created_from_cache
    assert node.base.attributes.get('metadata_inputs')['metadata']['disable_cache'] is True
    assert canonical(source['results'].get_dict())==before
    with pytest.raises(RuntimeError,match='Existing native request'):native.launch(bundle,request)


@pytest.mark.parametrize('bad',[False,True])
def test_submission_and_preparation_config3_closure_before_allocation(tmp_path,bad):
    from hyprn_mvp_app.store import Store
    from hyprn_mvp_app.execution import Submissions
    from test_submission import NativeDouble
    store=Store(tmp_path/'app.sqlite');actor=uid();study=store.create_study(actor,uid(),'Admission')
    case,deps=case4();config=case['frozen']['configuration'];config['study_id']=study['study_id']
    row=config['evidence_snapshots'][0];row['study_id']=study['study_id'];row['resource_scope']['study_id']=study['study_id']
    row['recorded_context']['resource_labels'][0]['resource_id']=study['study_id']
    if bad:config['evidence_snapshots']=[]
    repin(case)
    with store.connection(write=True) as db:
        db.execute('INSERT INTO configurations VALUES(?,?,?,?)',(config['configuration_revision_id'],config['configuration_id'],study['study_id'],json.dumps(case['frozen'])))
    native=NativeDouble();calls=[]
    def prepare(*args):calls.append(True);return case['prepared'],case['files']
    service=Submissions(store,prepare,native)
    body=dict(command_id=uid(),configuration_revision_id=config['configuration_revision_id'])
    if bad:
        with pytest.raises(ValueError):service.submit(actor,study['study_id'],body)
        with store.connection() as db:assert db.execute('SELECT COUNT(*) FROM run_associations').fetchone()[0]==0
        assert not calls
    else:
        run=service.submit(actor,study['study_id'],body);service.dispatch(run['run_id'],prepare_only=True)
        assert service.read(actor,study['study_id'],run['run_id'])['state']=='prepared'
        with store.connection() as db:
            payload=json.loads(db.execute('SELECT payload FROM outbox WHERE run_id=?',(run['run_id'],)).fetchone()[0])
        assert payload['bundle']['manifest']['schema_version']=='4'
    assert native.launches==0


@pytest.mark.parametrize('tamper',[False,True])
def test_source_resolver_admits_and_verifies_synthetic_bundle4_without_parser_claim(source,tamper):
    case,deps=case4();bundle,request=assembled(case,deps)
    # A deliberately synthetic retained record only exercises the source reader.
    # It is not a completed native execution or parser proof.
    process=orm.CalcJobNode(process_type='aiida.calculations:hyprn_mvp.scalar',backend=NATIVE_BACKEND)
    request_node=orm.Dict(dict=request,backend=NATIVE_BACKEND).store()
    folder=calc_inputs(bundle,request)['frozen_bundle']
    if tamper:folder.base.repository.put_object_from_filelike(io.BytesIO(b'{}'),'evidence/index.json')
    folder.store()
    process.base.links.add_incoming(request_node,link_type=LinkType.INPUT_CALC,link_label='request')
    process.base.links.add_incoming(folder,link_type=LinkType.INPUT_CALC,link_label='frozen_bundle');process.store()
    result=source['results'].get_dict();result.update(run_id=request['run_id'],bundle_digest=request['bundle_digest'])
    node=orm.Dict(dict=result,backend=NATIVE_BACKEND)
    node.base.links.add_incoming(process,link_type=LinkType.CREATE,link_label='results');node.store()
    process.set_process_state('finished');process.set_exit_status(0);process.seal()
    approved=copy.deepcopy(source['approved']);approved.update(source_run_id=request['run_id'],request=request,
        association=dict(store_uuid=PROJECTION_SCOPE.store_uuid,process_uuid=process.uuid),results_digest=digest(result))
    native=NativeExecution(backend=NATIVE_BACKEND,root=PROJECTION_SCOPE.root)
    before=orm.QueryBuilder(backend=NATIVE_BACKEND).append(orm.ProcessNode).count()
    if tamper:
        with pytest.raises(ValueError):native.resolve_results([approved])
    else:assert native.resolve_results([approved])[0]['result_uuid']==node.uuid
    assert orm.QueryBuilder(backend=NATIVE_BACKEND).append(orm.ProcessNode).count()==before
