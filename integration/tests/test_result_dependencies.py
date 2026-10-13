"""Real isolated AiiDA provenance; generated candidate bytes remain inert."""
import copy
import io
import json

import pytest
from checks import NATIVE_BACKEND, PROJECTION_SCOPE
from aiida import orm
from aiida.common.links import LinkType
from hyprn_mvp_app.store import canonical, digest, uid
from hyprn_mvp_app.execution import assemble_bundle
from hyprn_mvp_app.execution import executable_digest
from hyprn_mvp_app.scientific_configuration import project_scientific_configuration
from hyprn_mvp_integration.calculation import NativeExecution
from execution_fixtures import fixture, runtime_fixture


@pytest.fixture
def source(request):
    variant=getattr(request,'param','valid')
    backend = NATIVE_BACKEND
    assert backend is not None
    case = fixture()
    run = uid()
    bundle = assemble_bundle(run, case['prepared'], case['files'], case['frozen'], runtime_fixture())
    request = dict(run_id=run, scope=case['frozen']['configuration']['study_id'], command_id=uid(),
                   payload_digest='a'*64, bundle_digest=bundle['manifest']['bundle_digest'])
    process = orm.CalcJobNode(process_type='aiida.calculations:hyprn_mvp.scalar', backend=backend)
    data = orm.Dict(dict=request, backend=backend).store()
    frozen = orm.FolderData(backend=backend)
    for path, raw in {**bundle['files'], 'manifest.json': canonical(bundle['manifest'])}.items():
        frozen.base.repository.put_object_from_filelike(io.BytesIO(raw), path)
    frozen.store()
    process.base.links.add_incoming(data, link_type=LinkType.INPUT_CALC, link_label='request')
    process.base.links.add_incoming(frozen, link_type=LinkType.INPUT_CALC, link_label='frozen_bundle')
    process.store()
    outputs = json.loads(case['files'][case['prepared']['entrypoint']['bindings_path']])['outputs']
    result = dict(schema_version='1', run_id=run, bundle_digest=request['bundle_digest'],
        execution=dict(state='finished',exit_code=0,message='Synthetic retained result; no candidate executed'),
        convergence=dict(state='not_applicable',diagnostics_ref=None),
        optimization=dict(termination='not_applicable',feasibility='not_applicable'),
        completeness=dict(expected=len(outputs),available=len(outputs),failed=0,unavailable=0),
        outputs=[dict(target=o['target'],value=150+i,units=o['units'],availability='available',reason=None,
                      producer_completed=True,assigned=True) for i,o in enumerate(outputs)],
        criteria=[],applicability=dict(state='unassessed',evidence_refs=[]),artifacts=[])
    if variant=='corrupt_result':result['outputs'][0]['value']=True
    if variant=='large':result['outputs'][0]['value']=1e20
    results = orm.Dict(dict=result, backend=backend)
    results.base.links.add_incoming(process, link_type=LinkType.CREATE, link_label='other' if variant=='wronglabel' else 'results')
    results.store()
    process.set_process_state('finished'); process.set_exit_status(1 if variant=='failed' else 0); process.seal()
    approved = dict(source_run_id=run, request=request,
        association=dict(store_uuid=PROJECTION_SCOPE.store_uuid,process_uuid=process.uuid),
        results_digest=digest(results.get_dict()),
        outputs=sorted([{k:o[k] for k in ('target','value','units')} for o in result['outputs']],
                       key=lambda o:(o['target']['instance_id'],o['target']['port_id'])))
    return dict(case=case,bundle=bundle,request=request,process=process,results=results,approved=approved)


def test_resolver_returns_original_results_uuid_and_exact_scalars(source):
    native = NativeExecution(backend=NATIVE_BACKEND, root=PROJECTION_SCOPE.root)
    result = native.resolve_results([source['approved']])
    assert result == [source['approved'] | dict(result_uuid=source['results'].uuid)]
    assert source['results'].creator.uuid == source['process'].uuid


def linked_bundle(source, mode='two', other=None):
    case = source['case']; frozen = copy.deepcopy(case['frozen']); config = frozen['configuration']
    config.update(schema_version='2',configuration_id=uid(),configuration_revision_id=uid(),
        context_source=dict(kind='current_study',expected_study_revision='fixture:1'),derivation=None)
    config['required_capabilities'].append('result_linked_inputs/1')
    pin = {k:source['approved'][k] for k in ('source_run_id','request','association','results_digest')}
    pin.update(result_uuid=source['results'].uuid,label='r'+source['results'].uuid.replace('-',''))
    mappings=[];pins={pin['label']:pin}
    for index,item in enumerate(config['inputs']):
        selected=other if other is not None and index==1 else source
        if selected is not source:
            pin={k:selected['approved'][k] for k in ('source_run_id','request','association','results_digest')}
            pin.update(result_uuid=selected['results'].uuid,label='r'+selected['results'].uuid.replace('-',''))
            pins[pin['label']]=pin
        output=selected['approved']['outputs'][0 if mode=='fanout' else index]
        conversion=dict(policy='openmdao-linear-catalog-1',catalog_digest='c'*64,
            source_units=output['units'],destination_units=item['units'],factor=1,destination_value=output['value'])
        binding=dict(source_run_id=pin['source_run_id'],source_output=output['target'],results_digest=pin['results_digest'],
            source_configuration_digest=case['frozen']['configuration']['digest'],original_value=output['value'],
            original_units=output['units'],conversion=conversion,labels=dict(run_name='Retained',model_name=None,
                model_revision_id=config['model_revision_id'],instance_name='Component',output_name='Output'))
        item.update(value=output['value'],units=output['units'],result_binding=binding)
        mappings.append(dict(target=item['target'],source_label=pin['label'],**{k:binding[k] for k in
            ('source_output','results_digest','original_value','original_units','conversion')}))
    config['digest']=digest({k:v for k,v in config.items() if k!='digest'})
    prepared=copy.deepcopy(case['prepared']);private=project_scientific_configuration(config)
    prepared.update(configuration_revision_id=config['configuration_revision_id'],configuration_digest=private['digest'])
    prepared['executable_content_digest']=executable_digest(prepared)
    prepared['prepared_digest']=digest({k:v for k,v in prepared.items() if k!='prepared_digest'})
    deps=dict(schema_version='1',sources=sorted(pins.values(),key=lambda p:p['label']),mappings=sorted(mappings,key=lambda m:tuple(m['target'][k] for k in ('instance_id','port_id'))))
    bundle=assemble_bundle(uid(),prepared,case['files'],frozen,runtime_fixture(),deps)
    request=source['request']|dict(run_id=bundle['manifest']['run_id'],command_id=uid(),bundle_digest=bundle['manifest']['bundle_digest'])
    return bundle,request


@pytest.fixture
def native():
    # No runtime attestation claim: this fixture permits only node construction.
    class NodeOnly(NativeExecution):
        def require_attestation(self):return None
        def bundle_runtime(self):return runtime_fixture()
    instance=NodeOnly(backend=NATIVE_BACKEND,root=PROJECTION_SCOPE.root)
    if not orm.QueryBuilder(backend=NATIVE_BACKEND).append(orm.InstalledCode,filters={'label':'hyprn-mvp-scalar'}).count():
        wrapper=PROJECTION_SCOPE.root/'launch-worker'
        wrapper.write_text('#!/bin/sh\nexit 97\n');wrapper.chmod(0o700)
        computer=orm.Computer(label='hyprn-mvp-node-only',hostname='localhost',transport_type='core.local',
            scheduler_type='core.direct',workdir=str(PROJECTION_SCOPE.root/'tmp/work'),backend=NATIVE_BACKEND).store()
        orm.InstalledCode(label='hyprn-mvp-scalar',computer=computer,filepath_executable=str(wrapper),
            default_calc_job_plugin='hyprn_mvp.scalar',backend=NATIVE_BACKEND).store()
    def stop(point):
        if point=='after_node':raise RuntimeError('Node-only boundary stop')
    instance.fault=stop
    return instance


@pytest.mark.parametrize('mode',['two','fanout','multi'])
def test_original_dict_input_exists_before_process_storage(source,native,monkeypatch,mode):
    other=globals()['source'].__wrapped__(None) if mode=='multi' else None
    bundle,request=linked_bundle(source,mode,other)
    expected={('upstream_results__r'+s['results'].uuid.replace('-',''),s['results'].uuid)
              for s in ([source,other] if other else [source])}
    original=canonical(source['results'].get_dict())
    saved=orm.CalcJobNode.store;observed=[]
    def before_store(node,*args,**kwargs):
        links=node.base.links.get_incoming(link_type=LinkType.INPUT_CALC).all()
        upstream=[l for l in links if l.link_label.startswith('upstream_results__')]
        assert not node.is_stored
        assert {(l.link_label,l.node.uuid) for l in upstream}==expected
        observed.append(node.uuid)
        return saved(node,*args,**kwargs)
    monkeypatch.setattr(orm.CalcJobNode,'store',before_store)
    with pytest.raises(RuntimeError,match='Node-only boundary stop'):native.launch(bundle,request)
    assert len(observed)==1
    node=orm.load_node(observed[0])
    assert node.base.caching.is_created_from_cache is False
    assert node.base.attributes.get('metadata_inputs')['metadata']['disable_cache'] is True
    assert node.inputs.upstream_results['r'+source['results'].uuid.replace('-','')].uuid==source['results'].uuid
    assert canonical(source['results'].get_dict())==original
    assert native.matches(request)==[node.uuid]
    with pytest.raises(RuntimeError,match='Existing native request'):native.launch(bundle,request)


@pytest.mark.parametrize('field',['store','process','request','digest','value','units','target','extra','duplicate'])
def test_resolver_rejects_changed_source_without_process(source,native,field):
    item=copy.deepcopy(source['approved']); before=orm.QueryBuilder().append(orm.ProcessNode).count()
    if field=='store':item['association']['store_uuid']=uid()
    elif field=='process':item['association']['process_uuid']=uid()
    elif field=='request':item['request']['payload_digest']='f'*64
    elif field=='digest':item['results_digest']='e'*64
    elif field=='value':item['outputs'][0]['value']=999
    elif field=='units':item['outputs'][0]['units']='km'
    elif field=='target':item['outputs'][0]['target']['port_id']=uid()
    elif field=='extra':item['extra']=True
    else:item['outputs'].append(copy.deepcopy(item['outputs'][0]))
    with pytest.raises(ValueError):native.resolve_results([item])
    assert orm.QueryBuilder().append(orm.ProcessNode).count()==before


def test_worker_reads_bundle3_frozen_original_values_without_import(source,tmp_path):
    from hyprn_mvp_integration.launcher import write_bundle
    from hyprn_mvp_integration.worker import read_inputs
    bundle,_=linked_bundle(source)
    directory=tmp_path/'worker';write_bundle(bundle,directory)
    manifest,_,config=read_inputs(directory,bundle['manifest']['bundle_digest'])
    assert manifest['schema_version']=='3'
    assert sorted(v['value'] for v in config['inputs'])==[150,151]


def rehash(bundle, changes):
    """Re-pin tampered outer inventory to exercise semantic, not only byte checks."""
    for path,value in changes.items():bundle['files'][path]=canonical(value)
    for descriptor in bundle['manifest']['files']:
        raw=bundle['files'][descriptor['path']]
        descriptor.update(size=len(raw),sha256=__import__('hashlib').sha256(raw).hexdigest())
    bundle['manifest']['bundle_digest']=digest({k:v for k,v in bundle['manifest'].items() if k!='bundle_digest'})


@pytest.mark.parametrize('field',['mapping_value','mapping_bool','mapping_extra','source_label','source_uuid','scope','private','config','descriptor','digest','version'])
def test_semantic_tampering_rejected_by_launcher_worker_and_native_before_store(source,native,tmp_path,field):
    from hyprn_mvp_integration.launcher import write_bundle,verify_execution_bundle
    from hyprn_mvp_integration.worker import read_inputs
    bundle,request=linked_bundle(source);changes={}
    deps=json.loads(bundle['files']['result-dependencies.json'])
    if field=='mapping_value':deps['mappings'][0]['original_value']=999
    elif field=='mapping_bool':deps['mappings'][0]['conversion']['factor']=True
    elif field=='mapping_extra':deps['mappings'][0]['expression']='x+1'
    elif field=='source_label':deps['sources'][0]['label']='unsafe__nested'
    elif field=='source_uuid':deps['sources'][0]['result_uuid']=uid()
    elif field=='scope':deps['sources'][0]['request']['scope']=uid()
    elif field=='private':
        private=json.loads(bundle['files']['modeling-configuration.json']);private['inputs'][0]['value']=999
        private['digest']=digest({k:v for k,v in private.items() if k!='digest'})
        bundle['manifest']['modeling_configuration_digest']=private['digest']
        changes['modeling-configuration.json']=private
    elif field=='config':
        config=json.loads(bundle['files']['configuration.json']);config['inputs'][0]['value']=999
        config['digest']=digest({k:v for k,v in config.items() if k!='digest'})
        bundle['manifest']['configuration_digest']=config['digest'];changes['configuration.json']=config
    elif field=='descriptor':bundle['manifest']['result_dependencies']['size']+=1
    elif field=='digest':bundle['manifest']['configuration_digest']='d'*64
    elif field=='version':bundle['manifest']['schema_version']='1'
    if field in ('mapping_value','mapping_bool','mapping_extra','source_label','source_uuid','scope'):
        changes['result-dependencies.json']=deps;raw=canonical(deps)
        bundle['manifest']['result_dependencies'].update(size=len(raw),sha256=__import__('hashlib').sha256(raw).hexdigest())
    rehash(bundle,changes);request['bundle_digest']=bundle['manifest']['bundle_digest']
    before=orm.QueryBuilder().append(orm.ProcessNode).count()
    with pytest.raises(ValueError):verify_execution_bundle(bundle,request,runtime_fixture())
    with pytest.raises(ValueError):native.launch(bundle,request)
    assert orm.QueryBuilder().append(orm.ProcessNode).count()==before
    directory=tmp_path/'tampered';write_bundle(bundle,directory)
    with pytest.raises(ValueError):read_inputs(directory,request['bundle_digest'])


@pytest.mark.parametrize('field',['store','process','result_uuid','results_digest','value','units'])
def test_changed_native_association_rejected_after_valid_bundle_preflight(source,native,field):
    bundle,request=linked_bundle(source)
    original=native._resolve_source
    # Fault seam between prior app resolution and native pre-storage recheck.
    def changed(row):
        row=copy.deepcopy(row)
        if field in ('store','process'):row['association'][field+'_uuid']=uid()
        elif field=='results_digest':row['results_digest']='a'*64
        elif field in ('value','units'):row['outputs'][0][field]=999 if field=='value' else 'km'
        node=original(row)
        if field=='result_uuid':
            return orm.Dict(dict=node.get_dict(),backend=NATIVE_BACKEND).store()
        return node
    native._resolve_source=changed
    before=orm.QueryBuilder().append(orm.ProcessNode).count()
    with pytest.raises(ValueError):native.launch(bundle,request)
    assert orm.QueryBuilder().append(orm.ProcessNode).count()==before


def test_production_guard_rejects_isolated_environment():
    with pytest.raises(RuntimeError,match='Explicit new AIIDA_PATH'):NativeExecution.from_environment()


def test_fixture_rejects_reinitialization_or_marker_identity_changes():
    import scoped_fixture as fixture
    from dataclasses import replace
    with pytest.raises(ValueError):fixture.create_native_fixture(PROJECTION_SCOPE)
    for key in ('profile_uuid','store_uuid'):
        with pytest.raises(ValueError):fixture.validate_scope(replace(PROJECTION_SCOPE,**{key:uid()}))
    path=PROJECTION_SCOPE.root/'aiida/.aiida/config.json';original=path.read_bytes();config=json.loads(original)
    try:
        for bad in (uid(),PROJECTION_SCOPE.profile_uuid.upper(),'{'+PROJECTION_SCOPE.profile_uuid+'}'):
            config['profiles'][PROJECTION_SCOPE.profile]['PROFILE_UUID']=bad;path.write_text(json.dumps(config))
            with pytest.raises(ValueError):fixture.validate_scope(PROJECTION_SCOPE)
    finally:path.write_bytes(original)


def test_bundle2_remains_literal_and_worker_rejects_bundle1(source,tmp_path):
    from hyprn_mvp_integration.launcher import write_bundle
    from hyprn_mvp_integration.worker import read_inputs
    bundle=source['bundle'];directory=tmp_path/'literal';write_bundle(bundle,directory)
    assert read_inputs(directory,bundle['manifest']['bundle_digest'])[2]['schema_version']=='1'


@pytest.mark.parametrize('bad',[True,float('nan'),float('inf'),[150]])
def test_native_scalar_type_rejection(source,native,bad):
    item=copy.deepcopy(source['approved']);item['outputs'][0]['value']=bad
    with pytest.raises(ValueError):native.resolve_results([item])


def test_native_source_and_scalar_limits(source,native):
    with pytest.raises(ValueError):native.resolve_results([source['approved']]*65)
    item=copy.deepcopy(source['approved']);item['outputs']*=501
    with pytest.raises(ValueError):native.resolve_results([item])


@pytest.mark.parametrize('source',['failed','corrupt_result','wronglabel'],indirect=True)
def test_native_rejects_failed_or_invalid_actual_source(source,native):
    before=orm.QueryBuilder().append(orm.ProcessNode).count()
    with pytest.raises(ValueError):native.resolve_results([source['approved']])
    assert orm.QueryBuilder().append(orm.ProcessNode).count()==before


@pytest.mark.parametrize('form',['canonical','hex'])
def test_real_repository_uuid_encodings_preserve_exact_association(source,native,tmp_path,form):
    from uuid import UUID
    from hyprn_mvp_integration.launcher import write_bundle,verify_execution_bundle
    from hyprn_mvp_integration.worker import read_inputs
    raw=NATIVE_BACKEND.get_repository().uuid
    native.store_uuid=raw
    source['approved']['association']['store_uuid']=raw if form=='hex' else str(UUID(raw))
    assert native.resolve_results([source['approved']])[0]['association']==source['approved']['association']
    bundle,request=linked_bundle(source);verify_execution_bundle(bundle,request,runtime_fixture())
    directory=tmp_path/'store-form';write_bundle(bundle,directory)
    assert read_inputs(directory,request['bundle_digest'])[0]['schema_version']=='3'
    with pytest.raises(RuntimeError,match='Node-only boundary stop'):native.launch(bundle,request)


def test_guard_detects_marker_rewrite_away_from_actual_repository():
    import scoped_fixture as fixture
    from dataclasses import replace
    scope=PROJECTION_SCOPE;path=scope.root/'scope.json';original=path.read_bytes()
    changed=replace(scope,store_uuid=uid())
    try:
        path.write_text(json.dumps(changed.record()))
        with pytest.raises(ValueError,match='Actual native repository'):fixture.validate_scope(changed)
    finally:path.write_bytes(original)


def test_real_namespace_rejects_nested_unstored_wrong_type_and_over_limit():
    from hyprn_mvp_integration.calculation import ScalarCalculation
    namespace=ScalarCalculation.spec().inputs['upstream_results']
    nodes=[orm.Dict(dict=dict(value=i),backend=NATIVE_BACKEND).store() for i in range(65)]
    values={'r'+n.uuid.replace('-',''):n for n in nodes}
    assert namespace.validate(dict(list(values.items())[:64])) is None
    assert namespace.validate(values) is not None
    for bad in ({'nested':values},{'human label':nodes[0]},
                {'r'+nodes[0].uuid.replace('-',''):orm.Dict(dict={},backend=NATIVE_BACKEND)},
                {'r'+nodes[0].uuid.replace('-',''):orm.Int(1,backend=NATIVE_BACKEND)}):
        assert namespace.validate(bad) is not None


@pytest.mark.parametrize('number',[1e-7,1e20,1e21,0.000001,-0.0])
def test_worker_preserves_canonical_fraction_exponent_and_unicode_projection(source,tmp_path,number):
    from hyprn_mvp_integration.launcher import write_bundle,verify_execution_bundle
    from hyprn_mvp_integration.worker import read_inputs
    bundle,request=linked_bundle(source);config=json.loads(bundle['files']['configuration.json'])
    config['name']='Unicode café 🛰';config['required_capabilities'].remove('result_linked_inputs/1')
    for item in config['inputs']:item.update(value=number,result_binding=None)
    config['digest']=digest({k:v for k,v in config.items() if k!='digest'})
    private=project_scientific_configuration(config);prepared=json.loads(bundle['files']['preparation.json'])
    prepared['configuration_digest']=private['digest'];prepared['executable_content_digest']=executable_digest(prepared)
    prepared['prepared_digest']=digest({k:v for k,v in prepared.items() if k!='prepared_digest'})
    deps=dict(schema_version='1',sources=[],mappings=[]);raw=canonical(deps)
    bundle['manifest'].update(configuration_digest=config['digest'],modeling_configuration_digest=private['digest'],
        prepared_digest=prepared['prepared_digest'],executable_content_digest=prepared['executable_content_digest'],
        result_dependencies=dict(path='result-dependencies.json',size=len(raw),sha256=__import__('hashlib').sha256(raw).hexdigest()))
    rehash(bundle,{'configuration.json':config,'modeling-configuration.json':private,'preparation.json':prepared,'result-dependencies.json':deps})
    request['bundle_digest']=bundle['manifest']['bundle_digest'];verify_execution_bundle(bundle,request,runtime_fixture())
    directory=tmp_path/'fraction';write_bundle(bundle,directory)
    result=read_inputs(directory,request['bundle_digest'])[2]
    assert result['name']=='Unicode café 🛰' and all(i['value']==number for i in result['inputs'])


def test_canonical_exact_large_numbers_roundtrip_without_mutating_types():
    from hyprn_mvp_app.execution import data_json
    value={'a':[10**20,-10**20,True,3,{'value':10**20}]}
    before=copy.deepcopy(value)
    raw=canonical(value)
    assert raw==b'{"a":[100000000000000000000,-100000000000000000000,true,3,{"value":100000000000000000000}]}'
    assert value==before and type(value['a'][0]) is int and type(value['a'][2]) is bool
    assert canonical(data_json(raw))==raw
    assert canonical(1e20)==canonical(10**20)
    assert canonical(-1e20)==canonical(-10**20)
    assert canonical({'a':True,'b':[3,-0.0,0.1]})==b'{"a":true,"b":[3,0,0.1]}'
    case=fixture()
    for record in (case['frozen']['configuration'],case['frozen']['model_snapshot']):
        assert digest({k:v for k,v in record.items() if k!='digest'})==record['digest']


@pytest.mark.parametrize('number',[9007199254740993,-9007199254740993,10**1000])
def test_canonical_rejects_inexact_or_overflowing_integers(number):
    with pytest.raises(ValueError):canonical({'nested':[number]})


@pytest.mark.parametrize('source',['large'],indirect=True)
def test_large_retained_native_scalar_roundtrips_into_linked_worker_input(source,native,tmp_path):
    from hyprn_mvp_integration.launcher import write_bundle,verify_execution_bundle
    from hyprn_mvp_integration.worker import read_inputs
    assert native.resolve_results([source['approved']])[0]['result_uuid']==source['results'].uuid
    bundle,request=linked_bundle(source);verify_execution_bundle(bundle,request,runtime_fixture())
    directory=tmp_path/'large-linked';write_bundle(bundle,directory)
    config=read_inputs(directory,request['bundle_digest'])[2]
    linked=next(i for i in config['inputs'] if i['value']==1e20)
    assert linked['result_binding']['original_value']==1e20
    with pytest.raises(RuntimeError,match='Node-only boundary stop'):native.launch(bundle,request)
