"""Scientific and frozen-byte contracts. Real calculations require current attestation."""
import copy
import json
from pathlib import Path
import pytest
from execution_fixtures import fixture, current_fixture, runtime_fixture, uid, raw_hash
from hyprn_mvp_app.store import digest

def assemble(case=None, runtime=None):
    from hyprn_mvp_app.execution import assemble_bundle
    case=case or fixture()
    return assemble_bundle(uid(),case['prepared'],case['files'],case['frozen'],runtime or runtime_fixture())

@pytest.mark.quick
def test_final_bundle_retains_preparation_configuration_context_sources_and_locks():
    case=fixture();bundle=assemble(case)
    manifest=bundle['manifest'];files=bundle['files']
    assert manifest['prepared_digest']==case['prepared']['prepared_digest']
    assert manifest['configuration_digest']==case['frozen']['configuration']['digest']
    assert manifest['bundle_digest']==digest({k:v for k,v in manifest.items() if k!='bundle_digest'})
    assert json.loads(files['preparation.json'])==case['prepared']
    assert json.loads(files['configuration.json'])==case['frozen']['configuration']
    assert json.loads(files['context.json'])==case['frozen']['configuration']['context_snapshot']
    assert json.loads(files['evidence/index.json'])==case['frozen']['configuration']['evidence_snapshots']
    assert files['locks/worker.lock']==runtime_fixture()['files']['locks/worker.lock']
    for path,raw in case['files'].items():assert files[path]==raw
    for f in manifest['files']:
        assert f['size']==len(files[f['path']]) and f['sha256']==raw_hash(files[f['path']])

@pytest.mark.quick
@pytest.mark.parametrize('target',['source','model','configuration','context','evidence','binding','prepared','missing','dependency'])
def test_tampered_preparation_and_frozen_application_data_rejected(target):
    case=fixture()
    if target=='source':case['files'][next(p for p in case['files'] if p.startswith('sources/'))]+=b'\n'
    elif target=='model':case['files']['model.json']+=b' '
    elif target=='configuration':case['frozen']['configuration']['inputs'][0]['value']=999
    elif target=='context':case['frozen']['configuration']['context_snapshot']['description']='changed'
    elif target=='evidence':case['frozen']['configuration']['evidence_snapshots'].append({'content':'forged'})
    elif target=='binding':case['prepared']['configuration_revision_id']=uid();case['prepared']['prepared_digest']=digest({k:v for k,v in case['prepared'].items() if k!='prepared_digest'})
    elif target=='prepared':case['prepared']['generator_identity']['version']='forged'
    elif target=='missing':case['files'].pop('model.json')
    else:case['prepared']['dependency_requirements'][0]['version']='0.0.0';case['prepared']['prepared_digest']=digest({k:v for k,v in case['prepared'].items() if k!='prepared_digest'})
    with pytest.raises((ValueError,RuntimeError)):assemble(case)

@pytest.mark.quick
@pytest.mark.parametrize('bad',['/escape','../escape','sources/../escape','sources//x','sources/./x','sources\\escape','a/'*18+'x'])
def test_unsafe_preparation_paths_are_rejected_even_with_consistent_hashes(bad):
    case=fixture();f=case['prepared']['files'][0];raw=case['files'].pop(f['path']);f['path']=bad;case['files'][bad]=raw
    case['prepared']['prepared_digest']=digest({k:v for k,v in case['prepared'].items() if k!='prepared_digest'})
    with pytest.raises((ValueError,RuntimeError)):assemble(case)

@pytest.mark.quick
def test_bundle_verify_rejects_current_runtime_swap_and_symlink(tmp_path):
    from hyprn_mvp_integration.launcher import verify_bundle, write_bundle
    bundle=assemble();write_bundle(bundle,tmp_path/'input')
    verify_bundle(tmp_path/'input',runtime_fixture()['runtime'])
    changed=copy.deepcopy(runtime_fixture()['runtime']);changed['image_digest']='sha256:'+'d'*64
    with pytest.raises((ValueError,RuntimeError)):verify_bundle(tmp_path/'input',changed)
    path=tmp_path/'input/context.json';raw=path.read_bytes();path.unlink();outside=tmp_path/'outside';outside.write_bytes(raw);path.symlink_to(outside)
    with pytest.raises((ValueError,RuntimeError)):verify_bundle(tmp_path/'input',runtime_fixture()['runtime'])

@pytest.mark.quick
def test_static_assembly_does_not_import_candidate(tmp_path):
    case=fixture('canary')
    assemble(case)
    assert not Path('/tmp/HYPRN_MVP_CANDIDATE_MUST_NOT_IMPORT').exists()

@pytest.mark.quick
@pytest.mark.parametrize('boundary', ['launcher', 'worker', 'native'])
@pytest.mark.parametrize('version', ['1', '9'])
def test_obsolete_execution_version_rejected_before_import_or_process(
    tmp_path, monkeypatch, boundary, version
):
    from hyprn_mvp_integration import launcher, worker

    bundle = assemble()
    bundle['manifest']['schema_version'] = version
    bundle['manifest']['bundle_digest']=digest({k:v for k,v in bundle['manifest'].items() if k!='bundle_digest'})
    launcher.write_bundle(bundle,tmp_path/'input')
    request={k:bundle['manifest'][k] for k in ('run_id','bundle_digest')}
    request.update(scope=uid(),command_id=uid(),payload_digest='a'*64)
    if boundary=='launcher':
        call=lambda:launcher.verify_bundle(tmp_path/'input',runtime_fixture()['runtime'],request['bundle_digest'])
    elif boundary=='worker':
        call=lambda:worker.read_inputs(tmp_path/'input')
    else:
        from hyprn_mvp_integration.calculation import NativeExecution
        native=NativeExecution()
        monkeypatch.setattr(native,'require_attestation',lambda:None)
        monkeypatch.setattr(native,'bundle_runtime',runtime_fixture)
        monkeypatch.setattr(native,'matches',lambda _:pytest.fail('Reached process lookup before version refusal'))
        call=lambda:native.launch(bundle,request)
    with pytest.raises(ValueError,match='[Uu]nsupported.*version'):
        call()


@pytest.mark.quick
def test_worker_has_no_graph_builder_or_source_body_compiler():
    import ast
    from hyprn_mvp_integration import worker
    tree=ast.parse(Path(worker.__file__).read_text())
    forbidden={'add_subsystem','connect','add_input','add_output','compile','exec','topological_sort'}
    calls={node.func.id if isinstance(node.func,ast.Name) else node.func.attr
           for node in ast.walk(tree) if isinstance(node,ast.Call) and isinstance(node.func,(ast.Name,ast.Attribute))}
    assert not calls & forbidden


@pytest.mark.quick
@pytest.mark.parametrize('mode',['missing','generated','binding','factory','protocol','expected','manifest'])
def test_worker_rejects_tamper_before_native_import(tmp_path,monkeypatch,mode):
    from hyprn_mvp_integration import worker,launcher
    from hyprn_mvp_app.store import canonical
    bundle=assemble();root=tmp_path/'input';launcher.write_bundle(bundle,root)
    expected=bundle['manifest']['bundle_digest'];manifest_sha=raw_hash((root/'manifest.json').read_bytes())
    if mode=='missing':(root/bundle['manifest']['entrypoint']['module_path']).unlink()
    elif mode in ('generated','binding'):
        key='module_path' if mode=='generated' else 'bindings_path'
        path=root/bundle['manifest']['entrypoint'][key];path.chmod(0o644);path.write_bytes(b'forged')
    elif mode=='expected':expected='f'*64
    else:
        if mode in ('factory','protocol'):bundle['manifest']['entrypoint'][mode]='forged'
        else:bundle['manifest']['run_id']=uid()
        path=root/'manifest.json';path.chmod(0o644);path.write_bytes(canonical(bundle['manifest']))
    monkeypatch.setattr(worker,'load_program',lambda *_:pytest.fail('Candidate import attempted'))
    with pytest.raises((ValueError,OSError)):
        worker.execute(root,expected,manifest_sha)


@pytest.mark.quick
@pytest.mark.parametrize('mode',['normal','unwritten','nan','inf','throw','write_failure','inplace','nonfinite_input'])
def test_generic_observation_excludes_initializers_and_preserves_honest_state(mode):
    # Independent protocol callback, never generated/candidate source or OpenMDAO.
    import numpy as np
    from types import SimpleNamespace
    from hyprn_mvp_integration.worker import observe_compute
    component=SimpleNamespace();state={};vector={'y':np.array([float('nan')])}
    class Vector(dict):
        def __setitem__(self,key,value):
            if key=='bad':raise ValueError('native vector write rejected')
            super().__setitem__(key,np.array([value]))
    vector=Vector(vector)
    def compute(inputs,outputs):
        component._hyprn_mvp_assigned=set();component._hyprn_mvp_completed=False
        outputs['y']=float('nan')
        if mode=='inplace':outputs['y'][0]=12
        if mode=='write_failure':outputs['bad']=1
        if mode!='unwritten':
            outputs['y']=float(mode) if mode in ('nan','inf') else 7
            component._hyprn_mvp_assigned.add('y')
        if mode=='throw':raise RuntimeError('after successful assignment')
        component._hyprn_mvp_completed=True
    callback=observe_compute(compute,component,state)
    inputs={'x':np.array([float('nan') if mode=='nonfinite_input' else 2])}
    if mode in ('throw','write_failure','inplace','nonfinite_input'):
        with pytest.raises((ValueError,RuntimeError)):callback(inputs,vector)
        assert state['completed'] is False
    else:
        callback(inputs,vector);assert state['completed'] is True
    assert state['assigned']==({'y'} if mode in ('normal','nan','inf','throw') else set())
    # A subsequent invocation cannot retain previous assignments/completion.
    with pytest.raises(ValueError):callback({'x':np.array([float('nan')])},vector)
    assert state==dict(completed=False,assigned=set())


@pytest.mark.quick
def test_generated_origins_require_real_declared_file(monkeypatch,tmp_path):
    # Inspect the class of this test-owned object; do not load frozen programs.
    import inspect
    from hyprn_mvp_integration.worker import generated_origin
    class Example:pass
    root=tmp_path;path=root/'generated/module.py';path.parent.mkdir();path.write_bytes(b'inert origin bytes')
    original=inspect.getsourcefile
    monkeypatch.setattr(inspect,'getsourcefile',lambda cls:str(path) if cls is Example else original(cls))
    manifest={'files':[dict(path='generated/module.py',sha256=raw_hash(path.read_bytes()))]}
    origins=generated_origin(Example(),root,manifest)
    assert origins==[dict(module=__name__,name='Example',path='generated/module.py',sha256=raw_hash(path.read_bytes()))]
    path.write_bytes(b'changed')
    with pytest.raises(ValueError,match='origin hash'):generated_origin(Example(),root,manifest)


@pytest.mark.quick
@pytest.mark.parametrize('boundary',['launcher','native'])
@pytest.mark.parametrize('mode',['artifact_version','protocol','factory','generated_bytes','request_pin','runtime'])
def test_new_execution_preflight_refuses_invalid_program_before_dispatch(tmp_path,monkeypatch,boundary,mode):
    from hyprn_mvp_integration import launcher
    from hyprn_mvp_integration.calculation import NativeExecution
    from hyprn_mvp_app.store import canonical
    bundle=assemble();selected=runtime_fixture()
    original=bundle['manifest']['bundle_digest']
    if mode=='artifact_version':
        p=json.loads(bundle['files']['preparation.json']);p['schema_version']='1'
        bundle['files']['preparation.json']=canonical(p)
    elif mode in ('protocol','factory'):bundle['manifest']['entrypoint'][mode]='invalid'
    elif mode=='generated_bytes':bundle['files'][bundle['manifest']['entrypoint']['module_path']]+=b'changed'
    elif mode=='request_pin':bundle['manifest']['run_id']=uid()
    elif mode=='runtime':bundle['manifest']['runtime']['policy_digest']='d'*64
    for item in bundle['manifest']['files']:
        raw=bundle['files'][item['path']];item.update(size=len(raw),sha256=raw_hash(raw))
    bundle['manifest']['bundle_digest']=digest({k:v for k,v in bundle['manifest'].items() if k!='bundle_digest'})
    request=dict(run_id=bundle['manifest']['run_id'],bundle_digest=original if mode=='request_pin' else bundle['manifest']['bundle_digest'],
                 scope=uid(),command_id=uid(),payload_digest='b'*64)
    if boundary=='launcher':
        launcher.write_bundle(bundle,tmp_path/'input')
        call=lambda:launcher.verify_bundle(tmp_path/'input',selected['runtime'],request['bundle_digest'],selected)
    else:
        native=NativeExecution()
        monkeypatch.setattr(native,'require_attestation',lambda:None)
        monkeypatch.setattr(native,'bundle_runtime',lambda:selected)
        monkeypatch.setattr(native,'matches',lambda _:pytest.fail('Reached native lookup'))
        call=lambda:native.launch(bundle,request)
    with pytest.raises(ValueError):call()

@pytest.mark.quick
def test_rehashed_runtime_lock_and_changed_expected_digest_are_rejected(tmp_path):
    from hyprn_mvp_integration.launcher import verify_bundle,write_bundle
    from hyprn_mvp_app.store import canonical
    selected=runtime_fixture();bundle=assemble(runtime=selected)
    original=bundle['manifest']['bundle_digest']
    bundle['files']['locks/worker.lock']+=b'forged\n'
    descriptor=next(f for f in bundle['manifest']['files'] if f['path']=='locks/worker.lock')
    descriptor.update(size=len(bundle['files']['locks/worker.lock']),sha256=raw_hash(bundle['files']['locks/worker.lock']))
    bundle['manifest']['bundle_digest']=digest({k:v for k,v in bundle['manifest'].items() if k!='bundle_digest'})
    write_bundle(bundle,tmp_path/'input')
    with pytest.raises(ValueError,match='expected bundle digest'):
        verify_bundle(tmp_path/'input',selected['runtime'],original)
    with pytest.raises(ValueError,match='lock/license'):
        verify_bundle(tmp_path/'input',selected['runtime'],bundle['manifest']['bundle_digest'],selected)

@pytest.fixture
def execution_runtime():
    from execution_fixtures import scoped_native_runtime
    # Never select a historical or live profile: the runtime belongs to this test's scope.
    runtime=scoped_native_runtime()
    assert runtime.require_attestation()['passed']
    return runtime

@pytest.mark.integration
@pytest.mark.parametrize('kind,multiplier,expected',[('chain',2,[7,49]),('chain',3,[9,81]),('unrelated',2,[3]),('units',2,[2])])
def test_native_general_scalar_equations_retained_exactly(execution_runtime,kind,multiplier,expected):
    case = current_fixture(kind, multiplier)
    bundle = assemble(case, execution_runtime.bundle_runtime())
    request=dict(run_id=bundle['manifest']['run_id'],scope=case['frozen']['configuration']['study_id'],command_id=uid(),payload_digest=digest({'kind':kind,'multiplier':multiplier}),bundle_digest=bundle['manifest']['bundle_digest'])
    record=execution_runtime.launch(bundle,request)
    result=record['results']
    assert record['process_state']=='finished' and record['exit_status']==0
    assert result['run_id']==request['run_id'] and result['bundle_digest']==request['bundle_digest']
    assert sorted(o['value'] for o in result['outputs'])==pytest.approx(sorted(expected),rel=1e-8,abs=1e-9)
    assert all(o['availability']=='available' and o['producer_completed'] and o['assigned'] for o in result['outputs'])
    assert execution_runtime.retained_bundle(record['process_uuid'])==bundle
    assert execution_runtime.matches(request)==[record['process_uuid']]
    assert execution_runtime.matches({**request,'bundle_digest':'f'*64})==[]
    from aiida import orm
    raw=json.loads(orm.load_node(record['process_uuid']).outputs.retrieved.base.repository.get_object_content('result.json'))
    origins=json.loads(next(line.split(' ',1)[1] for line in raw['output'].splitlines()
                           if line.startswith('HYPRN_MVP_NATIVE_ORIGINS_V1 ')))
    assert origins['group'] and len(origins['components'])==len(case['frozen']['model_snapshot']['instances'])
    declared={f['path']:f['sha256'] for f in bundle['manifest']['files']}
    for origin in [*origins['group'],*[c for row in origins['components'] for c in row['classes']]]:
        assert origin['path'].startswith('generated/') and declared[origin['path']]==origin['sha256']

@pytest.mark.integration
@pytest.mark.parametrize('source,assigned',[('pass\n',False),("outputs['y'] = float('nan')\n",True),("outputs['y'] = float('inf')\n",True),("outputs['y'] = 12\nraise RuntimeError('downstream failed')\n",True)])
def test_incomplete_downstream_preserves_completed_upstream(execution_runtime,source,assigned):
    case = current_fixture(downstream=source)
    bundle = assemble(case, execution_runtime.bundle_runtime())
    request=dict(run_id=bundle['manifest']['run_id'],scope=case['frozen']['configuration']['study_id'],command_id=uid(),payload_digest=digest({'source':source}),bundle_digest=bundle['manifest']['bundle_digest'])
    record=execution_runtime.launch(bundle,request);outputs=record['results']['outputs']
    upstream=next(o for o in outputs if o['target']==case['targets']['linear']['u'])
    downstream=next(o for o in outputs if o['target']==case['targets']['square']['y'])
    assert upstream['value']==7 and upstream['availability']=='available'
    assert downstream['value'] is None and downstream['availability']=='unavailable' and downstream['assigned']==assigned
    assert len(outputs) == 2
    assert sum(o['availability'] == 'available' for o in outputs) == 1
    assert record['results']['schema_version'] == '2'

@pytest.mark.integration
def test_prepared_native_execution_does_not_contact_modeling(execution_runtime,monkeypatch):
    import hyprn_mvp_app.modeling
    def forbidden(*args,**kwargs):raise AssertionError('Prepared execution contacted modeling')

    case = current_fixture()
    bundle = assemble(case, execution_runtime.bundle_runtime())
    monkeypatch.setattr(hyprn_mvp_app.modeling.ModelingClient,'call',forbidden)
    request=dict(run_id=bundle['manifest']['run_id'],scope=case['frozen']['configuration']['study_id'],command_id=uid(),payload_digest=digest({'prepared':True}),bundle_digest=bundle['manifest']['bundle_digest'])
    result = execution_runtime.launch(bundle,request)['results']
    assert result['schema_version'] == '2'
    assert len(result['outputs']) == 2
    assert all(o['availability'] == 'available' for o in result['outputs'])

@pytest.mark.integration
@pytest.mark.parametrize('point,expected',[('before_node',0),('after_node',1),('before_continuation',1),('after_continuation',1),('before_response',1)])
def test_native_fault_windows(execution_runtime,point,expected):
    case = current_fixture()
    bundle = assemble(case, execution_runtime.bundle_runtime())
    request=dict(run_id=bundle['manifest']['run_id'],scope=case['frozen']['configuration']['study_id'],command_id=uid(),payload_digest=digest({'fault':point}),bundle_digest=bundle['manifest']['bundle_digest'])
    def fault(at):
        if at==point:raise RuntimeError('injected native boundary fault')
    execution_runtime.fault=fault
    with pytest.raises(RuntimeError,match='injected native'):
        execution_runtime.launch(bundle,request)
    execution_runtime.fault=lambda at:None
    matches=execution_runtime.matches(request)
    assert len(matches)==expected
    if expected:
        record=execution_runtime.inspect(matches[0])
        assert execution_runtime.retained_bundle(matches[0])==bundle
        assert record['process_state']==('created' if point in ('after_node','before_continuation') else 'finished')
        with pytest.raises(RuntimeError,match='Existing native'):
            execution_runtime.launch(bundle,request)
        assert execution_runtime.matches(request)==matches

@pytest.mark.integration
@pytest.mark.parametrize('value,expected',[(0,3),(-2,-1)])
def test_explicit_zero_and_negative_inputs(execution_runtime,value,expected):
    case = current_fixture()
    config = case['frozen']['configuration']
    config['inputs'][0]['value'] = value
    config['digest']=digest({k:v for k,v in config.items() if k!='digest'})
    case['prepared']['configuration_digest']=config['digest']
    from hyprn_mvp_app.execution import executable_digest
    case['prepared']['executable_content_digest']=executable_digest(case['prepared'])
    case['prepared']['prepared_digest']=digest({k:v for k,v in case['prepared'].items() if k!='prepared_digest'})
    bundle=assemble(case,execution_runtime.bundle_runtime())
    request=dict(run_id=bundle['manifest']['run_id'],scope=config['study_id'],command_id=uid(),payload_digest=digest({'value':value}),bundle_digest=bundle['manifest']['bundle_digest'])
    record=execution_runtime.launch(bundle,request)
    values={tuple(o['target'].values()):o['value'] for o in record['results']['outputs']}
    assert sorted(values.values())==sorted([expected,expected**2])

@pytest.mark.integration
@pytest.mark.parametrize('mode',['missing','incompatible'])
def test_invalid_input_configuration_never_becomes_zero(execution_runtime,mode):
    case = current_fixture('units')
    config = case['frozen']['configuration']
    if mode=='missing':config['inputs']=[]
    else:config['inputs'][0]['units']='s' if mode=='incompatible' else 'degC'
    config['digest']=digest({k:v for k,v in config.items() if k!='digest'})
    case['prepared']['configuration_digest']=config['digest']
    from hyprn_mvp_app.execution import executable_digest
    case['prepared']['executable_content_digest']=executable_digest(case['prepared'])
    case['prepared']['prepared_digest']=digest({k:v for k,v in case['prepared'].items() if k!='prepared_digest'})
    if mode=='missing':
        with pytest.raises(ValueError):assemble(case,execution_runtime.bundle_runtime())
        return
    bundle=assemble(case,execution_runtime.bundle_runtime())
    request=dict(run_id=bundle['manifest']['run_id'],scope=config['study_id'],command_id=uid(),payload_digest=digest({'invalid':mode}),bundle_digest=bundle['manifest']['bundle_digest'])
    record=execution_runtime.launch(bundle,request)
    assert record['process_state']=='finished' and record['exit_status']==301
    assert record['results']['schema_version'] == '2'
    assert all(o['availability'] == 'unavailable' and o['value'] is None
        for o in record['results']['outputs'])


@pytest.mark.integration
def test_generated_symbol_view_inplace_write_is_explicitly_unavailable(execution_runtime):
    case = current_fixture('inplace')
    bundle = assemble(case, execution_runtime.bundle_runtime())
    request=dict(run_id=bundle['manifest']['run_id'],scope=case['frozen']['configuration']['study_id'],
                 command_id=uid(),payload_digest=digest({'case':'inplace'}),bundle_digest=bundle['manifest']['bundle_digest'])
    record=execution_runtime.launch(bundle,request)
    downstream=next(o for o in record['results']['outputs'] if o['target']==case['targets']['square']['y'])
    assert downstream['availability']=='unavailable' and downstream['value'] is None
    assert not downstream['assigned'] and not downstream['producer_completed']


@pytest.mark.integration
def test_native_batch_retains_independent_results_and_separate_workers(execution_runtime):
    import time
    from aiida import orm

    selected = execution_runtime.bundle_runtime()
    items = []
    for multiplier in (2, 3):
        case = current_fixture('chain', multiplier)
        bundle = assemble(case, selected)
        request = dict(run_id=bundle['manifest']['run_id'],
                       scope=case['frozen']['configuration']['study_id'], command_id=uid(),
                       payload_digest=digest({'multiplier': multiplier}),
                       bundle_digest=bundle['manifest']['bundle_digest'])
        items.append(dict(bundle=bundle, request=request, wall_seconds=60))
    started = time.monotonic()
    records = execution_runtime.launch_batch(items)
    elapsed = time.monotonic() - started
    worker_ids = []
    for item, row, expected in zip(items, records, ([7, 49], [9, 81]), strict=True):
        assert row['request'] == item['request']
        record = row['record']
        assert record['exit_status'] == 0
        assert sorted(o['value'] for o in record['results']['outputs']) == expected
        assert execution_runtime.matches(item['request']) == [record['process_uuid']]
        assert execution_runtime.retained_bundle(record['process_uuid']) == item['bundle']
        node = orm.load_node(record['process_uuid'])
        raw = json.loads(node.outputs.retrieved.base.repository.get_object_content('result.json'))
        worker_ids.append(raw['id'])
    assert len(set(worker_ids)) == 2
    with pytest.raises(RuntimeError, match='Existing native'):
        execution_runtime.launch_batch(items)
    timing = dict(batch_seconds=elapsed, seconds_per_point=elapsed / 2,
                  independent_workers=worker_ids)
    (execution_runtime.root / 'evidence/batch-timing.json').write_text(json.dumps(timing))
    print(json.dumps(timing))
