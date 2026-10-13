"""Independent worker admission; never import generated candidate on the host."""
import io
import json
import pytest
from hyprn_mvp_app.store import canonical
from hyprn_mvp_integration import launcher,worker,results
from test_approach_bundle import case5
from test_assumptions_execution import assembled

@pytest.mark.parametrize('linked',[False,True])
def test_independent_bundle5_before_candidate_import(tmp_path,monkeypatch,linked):
    case,deps=case5(linked);bundle,request=assembled(case,deps)
    root=tmp_path/'bundle';launcher.write_bundle(bundle,root)
    monkeypatch.setattr(worker,'load_program',lambda *a:pytest.fail('Admission imported candidate'))
    assert worker.read_inputs(root,request['bundle_digest'])[2]==case['frozen']['configuration']
    class Repository:
        def open(self,path,mode='rb'):
            return io.BytesIO(canonical(bundle['manifest']) if path=='manifest.json' else bundle['files'][path])
    assert results.retained_bundle(Repository(),request)==bundle


def test_legacy_attestation_helper_refuses_before_any_live_read_or_write(monkeypatch):
    import native_origin_fixture as proof
    monkeypatch.setattr(proof,'run',lambda *a:pytest.fail('Legacy helper crossed guarded boundary'))
    # Without an explicit isolated runtime root the helper refuses before reading or writing anything.
    with pytest.raises(ValueError,match='Explicit isolated runtime root required'):
        with proof.attested_variant('inert'):pytest.fail('Legacy helper entered')

@pytest.mark.parametrize('number',[1e-7,1e20,0.000001,1.2345678901234567,-0.0])
@pytest.mark.parametrize('version',['1','4'])
def test_raw_numeric_fragments_preserved(tmp_path,number,version):
    from test_assumptions_execution import repin,legacy_pairing_case
    from hyprn_mvp_app.store import digest
    if version=='4':case,deps=case5()
    else:
        case,_,_=legacy_pairing_case('1');deps=None
    c=case['frozen']['configuration'];c['inputs'][0]['value']=number;repin(case)
    bundle,request=assembled(case,deps)
    root=tmp_path/'float';launcher.write_bundle(bundle,root)
    assert worker.read_inputs(root,request['bundle_digest'])[2]==c
    raw=worker.array_items(worker.object_fields(bundle['files']['configuration.json'])['inputs'])[0]
    literal=worker.object_fields(raw)['value']
    if version=='4':
        private=worker.array_items(worker.object_fields(bundle['files']['modeling-configuration.json'])['inputs'])[0]
        assert worker.object_fields(private)['value']==literal
        assert worker.frozen_json(worker.object_fields(bundle['files']['modeling-configuration.json'])['schema_version'])=='3'
    assert worker.verify_object_digest(bundle['files']['configuration.json'])==c['digest']

@pytest.mark.parametrize('change',['bytes','source','model','config','private','case','root','closure_digest','unused_evidence','unknown_field','missing_ref','step_cycle','case_only_binding','ancestor_digest'])
def test_worker_rejects_resealed_tamper_before_import(tmp_path,monkeypatch,change):
    from copy import deepcopy
    from hyprn_mvp_app.store import digest,uid
    from test_approach_closure import signed
    from test_result_dependencies import rehash
    case,deps=case5();bundle,request=assembled(case,deps)
    c=deepcopy(case['frozen']['configuration']);closure=deepcopy(case['frozen']['approach_closure']);v=closure['approach_versions'][0]
    changes={}
    if change=='bytes':bundle['files']['approach/closure.json']+=b' '
    elif change=='source':
        path=next(p for p in bundle['files'] if p.startswith('sources/'));bundle['files'][path]+=b"\nopen('/output/forbidden-import','w').write('bad')\n"
    elif change=='model':
        m=deepcopy(case['frozen']['model_snapshot']);m['name']='Changed exact model';signed(m);changes['model.json']=m;bundle['manifest']['model_digest']=m['digest']
    elif change=='config':c['inputs'][0]['value']+=1
    elif change=='private':
        private=json.loads(bundle['files']['modeling-configuration.json']);private['schema_version']='4';signed(private);changes['modeling-configuration.json']=private
    elif change=='case':c['approach_binding']['case_id']=uid()
    elif change=='root':closure['root_approach_version_id']=uid()
    elif change=='closure_digest':c['approach_binding']['closure_digest']='f'*64
    elif change=='unused_evidence':
        extra=deepcopy(closure['evidence'][0]);extra['evidence_version_id']=uid();closure['evidence'].append(extra);closure['evidence'].sort(key=lambda e:e['evidence_version_id'])
    elif change=='unknown_field':v['content']['steps'][0]['native_graph']={}
    elif change=='missing_ref':v['content']['steps'][0]['implementation_refs'][0]['binding_id']=uid()
    elif change=='step_cycle':v['content']['steps'][0]['intent']['depends_on_step_ids']=[v['content']['steps'][0]['step_id']]
    elif change=='case_only_binding':v['content']['steps']=[]
    else:
        # Insert a reachable prior Config4 pin with a deliberately wrong ancestor
        # digest. Every enclosing object is re-signed; ancestry must be verified.
        old=deepcopy(v);old['approach_version_id']=uid();signed(old)
        prior=deepcopy(c);prior['configuration_revision_id']=uid();prior['approach_binding'].update(approach_version_id=old['approach_version_id'],approach_digest=old['digest'],closure_digest='f'*64);signed(prior)
        closure['approach_versions'].append(old);closure['configurations']=[prior]
        v['content']['basis_refs']=[dict(kind='configuration',configuration_revision_id=prior['configuration_revision_id'],reason='Prior exact basis',relation='context')]
    if change in ('unused_evidence','unknown_field','missing_ref','step_cycle','case_only_binding','ancestor_digest'):
        signed(v);closure['root_approach_digest']=v['digest'];c['approach_binding']['approach_digest']=v['digest']
        closure['approach_versions'].sort(key=lambda a:a['approach_version_id'])
    if change not in ('bytes','source','model','private','closure_digest'):
        signed(closure);c['approach_binding']['closure_digest']=closure['digest'];changes['approach/closure.json']=closure
    signed(c);changes['configuration.json']=c;bundle['manifest']['configuration_digest']=c['digest']
    bundle['manifest'].update(approach_digest=c['approach_binding']['approach_digest'],approach_closure_digest=c['approach_binding']['closure_digest'])
    rehash(bundle,changes)
    root=tmp_path/'tampered';launcher.write_bundle(bundle,root)
    monkeypatch.setattr(worker,'load_program',lambda *a:pytest.fail('Candidate import reached'))
    with pytest.raises((ValueError,KeyError)):
        worker.execute(root,bundle['manifest']['bundle_digest'],__import__('hashlib').sha256(canonical(bundle['manifest'])).hexdigest())
    assert not (root/'forbidden-import').exists()

@pytest.fixture(scope='module')
def current_native():
    from checks import PROJECTION_SCOPE as scope,NATIVE_BACKEND as backend
    import scoped_fixture as guard
    from hyprn_mvp_integration.calculation import NativeExecution
    guard.prepare_worker_fixture(scope,backend)
    native=NativeExecution(backend=backend,root=scope.root)
    assert native.require_attestation()['passed']
    return native

def generated_case(kind,monkeypatch):
    # Existing captured native generator output stays byte-identical. Only
    # application/model metadata and their enclosing integrity envelopes change.
    import test_assumptions_execution as fixture_module
    from execution_fixtures import fixture
    with monkeypatch.context() as patch:
        patch.setattr(fixture_module,'fixture',lambda:fixture(kind))
        return case5()

@pytest.mark.parametrize('kind,expected',[('chain',[7,49]),('unrelated',[3])])
def test_actual_restricted_native_generated_program_with_pinned_approach(current_native,monkeypatch,kind,expected):
    from hyprn_mvp_app.execution import assemble_bundle
    from hyprn_mvp_app.store import uid,digest
    from test_assumptions_execution import repin
    from aiida import orm
    from checks import PROJECTION_SCOPE as scope
    case,deps=generated_case(kind,monkeypatch)
    c=case['frozen']['configuration'];m=case['frozen']['model_snapshot']
    # Criterion is explicit; application assumptions do not imply validity.
    mapping=json.loads(case['files'][case['prepared']['entrypoint']['bindings_path']])
    target=mapping['outputs'][-1]['target']
    c['criteria']=[dict(criterion_id=uid(),target=target,operator='ge',threshold=0,units=mapping['outputs'][-1]['units'],evidence_version_ids=[])]
    repin(case)
    bundle=assemble_bundle(uid(),case['prepared'],case['files'],case['frozen'],current_native.bundle_runtime(),deps)
    request=dict(run_id=bundle['manifest']['run_id'],scope=c['study_id'],command_id=uid(),payload_digest=digest({'proof':kind}),bundle_digest=bundle['manifest']['bundle_digest'])
    record=current_native.launch(bundle,request)
    assert record['exit_status']==0,record
    result=record['results'];assert sorted(o['value'] for o in result['outputs'])==expected
    assert all(o['availability']=='available' and o['assigned'] and o['producer_completed'] for o in result['outputs'])
    assert result['execution']['state']=='finished' and result['convergence']['state']=='not_applicable'
    assert result['criteria'][0]['outcome']=='met' and result['applicability']['state']=='unassessed'
    assert current_native.retained_bundle(record['process_uuid'])==bundle
    node=orm.load_node(record['process_uuid']);assert node.outputs.results.creator.uuid==node.uuid
    with pytest.raises(RuntimeError,match='Existing native request'):current_native.launch(bundle,request)
    (scope.root/'evidence'/('approach-native-'+kind+'.json')).write_text(json.dumps(dict(record=record,capture=dict(kind=kind,files=case['prepared']['files']),bundle_digest=bundle['manifest']['bundle_digest'],worker=current_native.require_attestation()['fingerprint']),indent=2))

@pytest.mark.parametrize('kind',['unwritten','nan','throw'])
def test_failed_native_outputs_are_not_valid_zero(current_native,monkeypatch,kind):
    from hyprn_mvp_app.execution import assemble_bundle
    from hyprn_mvp_app.store import uid,digest
    from checks import PROJECTION_SCOPE as scope
    case,deps=generated_case(kind,monkeypatch)
    bundle=assemble_bundle(uid(),case['prepared'],case['files'],case['frozen'],current_native.bundle_runtime(),deps)
    request=dict(run_id=bundle['manifest']['run_id'],scope=case['frozen']['configuration']['study_id'],command_id=uid(),payload_digest=digest({'proof':kind}),bundle_digest=bundle['manifest']['bundle_digest'])
    record=current_native.launch(bundle,request);result=record['results']
    assert record['exit_status']!=0 and result['completeness']['available']<result['completeness']['expected']
    assert any(o['availability']!='available' and o['value'] is None for o in result['outputs'])
    assert result['applicability']['state']=='unassessed'
    if kind=='throw':
        assert 'RuntimeError: downstream failed' in result['execution']['message']
        assert 'sources/' in result['execution']['message']
        assert '; instance ' in result['execution']['message']
    (scope.root/'evidence'/('approach-native-'+kind+'.json')).write_text(json.dumps(record,indent=2))


@pytest.mark.parametrize('linked',[False,True])
def test_reserved_approach_prefix_rejected_before_import(tmp_path,monkeypatch,linked):
    from hashlib import sha256
    from hyprn_mvp_app.store import digest
    case,deps=case5(linked);bundle,request=assembled(case,deps)
    path='approach/undeclared.json';raw=b'{}'
    bundle['files'][path]=raw
    bundle['manifest']['files'].append(dict(path=path,role='dependency',media_type='application/json',sha256=sha256(raw).hexdigest(),size=len(raw)))
    bundle['manifest']['files'].sort(key=lambda f:f['path'])
    bundle['manifest']['bundle_digest']=digest({k:v for k,v in bundle['manifest'].items() if k!='bundle_digest'})
    root=tmp_path/'reserved';launcher.write_bundle(bundle,root)
    monkeypatch.setattr(worker,'load_program',lambda *a:pytest.fail('Candidate import reached'))
    with pytest.raises(ValueError,match='approach inventory|Approach reserved'):
        worker.execute(root,bundle['manifest']['bundle_digest'],sha256(canonical(bundle['manifest'])).hexdigest())


def test_explanatory_method_cycle_admitted_across_authoring_and_worker(tmp_path):
    from copy import deepcopy
    from hyprn_mvp_app.store import uid
    from hyprn_mvp_app.approach_closure import build_closure
    from test_approach_closure import signed,resolution
    from test_assumptions_execution import repin
    case,deps=case5();f=case['frozen'];c=f['configuration']
    v=deepcopy(f['approach_closure']['approach_versions'][0])
    first=v['content']['steps'][0];second=deepcopy(first);second['step_id']=uid()
    first['intent']['depends_on_step_ids']=[second['step_id']]
    second['intent']['depends_on_step_ids']=[first['step_id']]
    v['content']['steps'].append(second);signed(v)
    closure=build_closure(v,resolution(models=[f['model_snapshot']],evidence=c['evidence_snapshots']),study_id=c['study_id'])
    f['approach_closure']=closure;c['approach_binding'].update(approach_digest=v['digest'],closure_digest=closure['digest']);repin(case)
    bundle,request=assembled(case,deps);root=tmp_path/'method-cycle';launcher.write_bundle(bundle,root)
    assert worker.read_inputs(root,request['bundle_digest'])[2]==c

@pytest.mark.parametrize('kind',['step','case','assumption'])
def test_blank_approach_text_rejected_before_closure_persistence(kind):
    from copy import deepcopy
    from hyprn_mvp_app.approach_closure import build_closure
    from test_approach_closure import signed,resolution,sample,D
    case,_=case5();f=case['frozen'];c=f['configuration'];v=deepcopy(f['approach_closure']['approach_versions'][0])
    if kind=='assumption':
        item=sample(D['ApproachAssumption1']);item['statement']=' \t\n';v['content']['assumptions']=[item]
    else:v['content']['steps' if kind=='step' else 'cases'][0]['title']=' \t\n'
    signed(v)
    with pytest.raises(ValueError):
        build_closure(v,resolution(models=[f['model_snapshot']],evidence=c['evidence_snapshots']),study_id=c['study_id'])


@pytest.mark.parametrize('change',[None,'missing_instance','duplicate_instance','foreign_port','root_port','root_connection','root_assumption','missing_definition','root_uuid'])
def test_worker_native_separate_root_preserves_exact_component_membership(change):
    from copy import deepcopy
    from hyprn_mvp_app.store import uid
    from test_approach_closure import native_root_shape,change_native_root_shape,closure,signed,SID
    v,m=native_root_shape();c=closure(v,models=[m]);v=c['approach_versions'][0];m=c['models'][0]
    change_native_root_shape(v,m,change)
    signed(m);signed(v);c['root_approach_digest']=v['digest'];signed(c)
    if change is None:assert worker.ApproachClosure(canonical(c),SID).root==v
    else:
        with pytest.raises(ValueError):worker.ApproachClosure(canonical(c),SID)
