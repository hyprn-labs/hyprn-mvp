"""Pure closure proofs: no modeling/client/store/candidate execution."""
from copy import deepcopy
import base64
import hashlib
import json
from pathlib import Path
import pytest
from hyprn_mvp_app.store import digest, uid
from hyprn_mvp_app.modeling import SCHEMA
from hyprn_mvp_app.approach_closure import build_closure, validate_closure, validate_saved

@pytest.mark.parametrize('change',[None,'output','value','units','conversion','failed'])
def test_result_binding_uses_exact_retained_output_and_conversion(change):
    m=model();p=sample(D['Port']);p.update(definition_version_id=m['definitions'][0]['definition_version_id'],direction='output',units='m')
    m['definitions'][0]['ports']=[p];m['ports']=[p];signed(m)
    original=config(m);run=sample(D['ApproachRunContext1'])
    run.update(study_id=SID,configuration_revision_id=original['configuration_revision_id'],configuration_digest=original['digest'],model_revision_id=m['model_revision_id'],model_digest=m['digest'],context=original['context_snapshot'])
    run['request'].update(run_id=run['run_id'],scope=SID)
    target=dict(instance_id=m['root_instance_id'],port_id=p['port_id'])
    results=sample(D['RetainedResults'])
    results.update(run_id=run['run_id'],bundle_digest=run['request']['bundle_digest'],execution=dict(state='finished',exit_code=0,message=''),outputs=[dict(target=target,value=2,units='m',availability='available',reason=None,producer_completed=True,assigned=True)])
    if change=='failed':results['execution'].update(state='failed',exit_code=1)
    run['results']=results;signed(run)
    copied=config(m)
    binding=sample(D['ResultBinding']);binding.update(source_run_id=run['run_id'],source_output=target,results_digest=digest(results),source_configuration_digest=original['digest'],original_value=2,original_units='m')
    binding['labels']['model_revision_id']=m['model_revision_id']
    binding['conversion'].update(source_units='m',destination_units='m',factor=1,destination_value=2)
    item=sample(D['ResolvedInput2']);item.update(value=2,units='m',result_binding=binding)
    if change=='output':binding['source_output']=dict(instance_id=uid(),port_id=p['port_id'])
    if change=='value':binding['original_value']=3
    if change=='units':binding['original_units']='kg'
    if change=='conversion':binding['conversion']['factor']=2
    copied['inputs']=[item];signed(copied)
    v=version();v['content']['basis_refs']=[dict(kind='configuration',configuration_revision_id=copied['configuration_revision_id'],reason='Transferred result',relation='context')];signed(v)
    kwargs=dict(models=[m],configurations=[original,copied],run_contexts=[run])
    if change is None:assert closure(v,**kwargs)
    else:
        with pytest.raises(ValueError):closure(v,**kwargs)


D=SCHEMA['$defs']
SID=uid()

def sample(s):
    if '$ref' in s:return sample(D[s['$ref'].split('/')[-1]])
    if 'const' in s:return s['const']
    if 'enum' in s:return s['enum'][0]
    if 'oneOf' in s or 'anyOf' in s:
        bs=s.get('oneOf',s.get('anyOf'))
        return sample(next((b for b in bs if b.get('type')=='null'),bs[0]))
    t=s.get('type')
    if t=='object':return {k:sample(s['properties'][k]) for k in s['required']}
    if t=='array':return [sample(s['items']) for _ in range(s.get('minItems',0))]
    if t=='null':return None
    if t=='boolean':return False
    if t in ('integer','number'):return s.get('minimum',0)
    if s.get('format')=='uuid':return uid()
    if s.get('pattern','').startswith('^([0-9a-f]{32}|'):return uid()
    if s.get('format')=='date-time':return '2026-10-10T14:30:00Z'
    if s.get('pattern')=='^[0-9a-f]{64}$':return 'a'*64
    if s.get('pattern')=='^sha256:[0-9a-f]{64}$':return 'sha256:'+'a'*64
    return 'x'

def signed(x):
    x['digest']=digest({k:v for k,v in x.items() if k!='digest'})
    return x

def version():
    v=sample(D['ApproachVersion1']);v['study_id']=SID
    return signed(v)

def evidence():
    e=sample(D['EvidenceSnapshot3']);e.update(study_id=SID,resource_scope=dict(scope_version='1',kind='study',study_id=SID))
    return e

def model():
    m=sample(D['ModelRevision2'])
    d=sample(D['Definition']);d['kind']='composite'
    root=dict(instance_id=m['root_instance_id'],definition_version_id=d['definition_version_id'],name='Root')
    m.update(definitions=[d],instances=[root])
    return signed(m)

def link(v,m):
    b=dict(binding_id=uid(),model_id=m['model_id'],model_revision_id=m['model_revision_id'])
    s=sample(D['ApproachStep1']);s.update(implementation_state='linked',remaining_work='',implementation_refs=[dict(kind='model',binding_id=b['binding_id'])])
    v['content']['model_bindings'].append(b);v['content']['steps'].append(s)
    signed(v)
    return b,s

def resolution(**kw):
    return {k:kw.get(k,[]) for k in ('approach_versions','models','configurations','run_contexts','evidence')}

def closure(v=None,**kw):
    return build_closure(v or version(),resolution(**kw),study_id=SID)

def test_proposal_exact_read_is_pure_and_does_not_follow_family_predecessor():
    v=version();v['predecessor_version_id']=uid();signed(v)
    c=closure(v);before=deepcopy(c)
    assert validate_closure(c,study_id=SID)==c
    assert validate_saved(dict(version=v,closure=c),study_id=SID)['version']==v
    assert c==before
    v['content']['question']='later edit'
    assert c['approach_versions'][0]['content']['question']!='later edit'

def test_canonical_dedup_and_exact_source_bytes_never_execute(tmp_path):
    v=version();m=model();link(v,m)
    canary=tmp_path/'executed'
    raw=("from pathlib import Path\nPath("+repr(str(canary))+").touch()\r\n").encode()
    h=hashlib.sha256(raw).hexdigest()
    m['source_files']=[dict(encoding='base64',media_type='text/x-python',bytes=base64.b64encode(raw).decode(),sha256=h)]
    m['definitions'][0]['source_refs']=[h];signed(m)
    e=evidence();v['content']['steps'][0]['evidence_links']=[dict(evidence_version_id=e['evidence_version_id'],relation='supports')];signed(v)
    c=closure(v,models=[m,m],evidence=[e,e])
    assert len(c['models'])==1 and len(c['evidence'])==1
    assert base64.b64decode(c['models'][0]['source_files'][0]['bytes'])==raw
    assert not canary.exists()
    assert closure(v,models=[m],evidence=[e])==c

@pytest.mark.parametrize('change',['root','digest','source','unused_model','unused_evidence','duplicate','foreign','dangling'])
def test_tampering_and_unreachable_records_reject(change):
    v=version();m=model();link(v,m);c=closure(v,models=[m])
    if change=='root':c['root_approach_digest']='b'*64
    elif change=='digest':c['digest']='b'*64
    elif change=='source':
        c['models'][0]['source_files']=[dict(encoding='base64',media_type='text/x-python',bytes='eA==',sha256='b'*64)]
        signed(c['models'][0])
    elif change=='unused_model':c['models'].append(model())
    elif change=='unused_evidence':c['evidence'].append(evidence())
    elif change=='duplicate':c['models'].append(deepcopy(m))
    elif change=='foreign':c['approach_versions'][0]['study_id']=uid();signed(c['approach_versions'][0])
    else:c['models']=[]
    if change!='digest':signed(c)
    with pytest.raises(ValueError):validate_closure(c,study_id=SID)

def test_conflicting_duplicate_identity_and_unordered_wire_reject():
    v=version();m=model();link(v,m);bad=deepcopy(m);bad['originating_draft_revision']='other';signed(bad)
    with pytest.raises(ValueError):closure(v,models=[m,bad])
    e1,e2=evidence(),evidence()
    v['content']['steps'][0]['evidence_links']=[dict(evidence_version_id=e['evidence_version_id'],relation='supports') for e in (e1,e2)];signed(v)
    c=closure(v,models=[m],evidence=[e2,e1]);c['evidence'].reverse();signed(c)
    with pytest.raises(ValueError):validate_closure(c)

@pytest.mark.parametrize('kind',['instance','port','connection'])
def test_exact_element_membership_not_just_any_same_name(kind):
    v=version();m=model();b,s=link(v,m)
    ref=dict(kind=kind,binding_id=b['binding_id'])
    if kind in ('instance','port'):ref['instance_id']=uid()
    if kind=='port':ref['port_id']=uid()
    if kind=='connection':ref['connection_id']=uid()
    s['implementation_refs']=[ref];signed(v)
    with pytest.raises(ValueError):closure(v,models=[m])

def test_assumption_origin_keeps_old_proposal_but_rejects_active_duplicate():
    old=version();a=sample(D['ApproachAssumption1']);a['role']='proposed_model_condition'
    old['content']['assumptions']=[a];signed(old)
    m=model();ma=dict(assumption_id=uid(),owner=dict(kind='model'),statement=a['statement'],evidence_links=[])
    m['assumptions']=[ma];signed(m)
    v=version();b,s=link(v,m)
    s['assumption_refs']=[dict(kind='model',binding_id=b['binding_id'],assumption_id=ma['assumption_id'],
        origin=dict(approach_version_id=old['approach_version_id'],assumption_id=a['assumption_id'],digest=old['digest']))]
    signed(v)
    c=closure(v,models=[m],approach_versions=[old])
    assert len(c['approach_versions'])==2
    v['content']['assumptions']=[a];signed(v)
    with pytest.raises(ValueError):closure(v,models=[m],approach_versions=[old])

def config(m,approach=None):
    c=sample(D['ConfigurationRevision4']);c.update(study_id=SID,model_id=m['model_id'],model_revision_id=m['model_revision_id'])
    c['approach_binding']=None if approach is None else dict(approach_id=approach['approach_versions'][0]['approach_id'],approach_version_id=approach['root_approach_version_id'],approach_digest=approach['root_approach_digest'],closure_digest=approach['digest'],case_id=None)
    return signed(c)

def test_nested_prior_configuration_authenticates_ancestor_subclosure_digest():
    m=model();old=version();link(old,m);ancestor=closure(old,models=[m]);cfg=config(m,ancestor)
    v=version();v['content']['basis_refs']=[dict(kind='configuration',configuration_revision_id=cfg['configuration_revision_id'],reason='Basis',relation='context')];signed(v)
    c=closure(v,models=[m],approach_versions=[old],configurations=[cfg]);validate_closure(c)
    c['configurations'][0]['approach_binding']['closure_digest']='b'*64;signed(c['configurations'][0]);signed(c)
    with pytest.raises(ValueError):validate_closure(c)

def test_failed_prior_run_context_is_retained_and_cross_identity_rejected():
    m=model();cfg=config(m);run=sample(D['ApproachRunContext1'])
    run.update(study_id=SID,configuration_revision_id=cfg['configuration_revision_id'],configuration_digest=cfg['digest'],model_revision_id=m['model_revision_id'],model_digest=m['digest'],context=cfg['context_snapshot'],results=None,assessment=None,errors=[dict(code='missing_results',partial=True)])
    run['request'].update(run_id=run['run_id'],scope=SID);signed(run)
    v=version();v['content']['basis_refs']=[dict(kind='run',run_id=run['run_id'],reason='Prior failure',relation='challenges')];signed(v)
    c=closure(v,models=[m],configurations=[cfg],run_contexts=[run])
    assert c['run_contexts'][0]['results'] is None
    c['run_contexts'][0]['request']['scope']=uid();signed(c['run_contexts'][0]);signed(c)
    with pytest.raises(ValueError):validate_closure(c)

def test_bounds_before_resolution_and_local_ids():
    v=version();v['content']['steps']=[sample(D['ApproachStep1'])]*65;signed(v)
    with pytest.raises(ValueError):closure(v)
    v=version();a=sample(D['ApproachAssumption1']);v['content']['assumptions']=[a,a];signed(v)
    with pytest.raises(ValueError):closure(v)

def test_valid_repeated_instances_port_and_multiple_connection_references():
    m=model();definition=m['definitions'][0]
    p=sample(D['Port']);p['definition_version_id']=definition['definition_version_id']
    definition['ports']=[p];m['ports']=[p]
    other=dict(instance_id=uid(),definition_version_id=definition['definition_version_id'],name='Root')
    m['instances'].append(other)
    endpoints=[dict(instance_id=i['instance_id'],port_id=p['port_id']) for i in m['instances']]
    m['connections']=[dict(connection_id=uid(),source_ref=endpoints[0],target_ref=endpoints[1]) for _ in range(2)]
    signed(m);v=version();b,s=link(v,m)
    s['implementation_refs']=[dict(kind='port',binding_id=b['binding_id'],**endpoints[1])]+[
        dict(kind='connection',binding_id=b['binding_id'],connection_id=c['connection_id']) for c in m['connections']]
    signed(v);c=closure(v,models=[m])
    assert len(c['models'][0]['connections'])==2

def test_model_and_configuration_citations_have_exact_bytes_and_scope():
    e=evidence();m=model()
    m['assumptions']=[dict(assumption_id=uid(),owner=dict(kind='model'),statement='Steady',
        evidence_links=[dict(evidence_version_id=e['evidence_version_id'],relation='supports')])]
    signed(m);cfg=config(m);cfg['evidence_snapshots']=[e];signed(cfg)
    v=version();v['content']['basis_refs']=[dict(kind='configuration',configuration_revision_id=cfg['configuration_revision_id'],reason='Basis',relation='supports')];signed(v)
    c=closure(v,models=[m],configurations=[cfg],evidence=[e])
    assert c['evidence']==[e]
    bad=deepcopy(c);bad['evidence'][0]=deepcopy(bad['evidence'][0]);bad['evidence'][0]['content']='Replaced';signed(bad)
    with pytest.raises(ValueError,match='evidence bytes'):validate_closure(bad)
    bad=deepcopy(c);bad['evidence'][0]=deepcopy(bad['evidence'][0]);bad['evidence'][0]['resource_scope']['study_id']=uid();signed(bad)
    with pytest.raises(ValueError,match='Foreign'):validate_closure(bad)

def test_scientific_cycle_is_rejected_without_chasing_family_ancestry():
    m=model();v=version();link(v,m);cfg=config(m)
    v['content']['basis_refs']=[dict(kind='configuration',configuration_revision_id=cfg['configuration_revision_id'],reason='Circular',relation='context')];signed(v)
    cfg['approach_binding']=dict(approach_id=v['approach_id'],approach_version_id=v['approach_version_id'],approach_digest=v['digest'],closure_digest='a'*64,case_id=None);signed(cfg)
    with pytest.raises(ValueError,match='cycle'):closure(v,models=[m],configurations=[cfg])

def test_typed_depth_bound_uses_longest_shared_path():
    m=model();aid=uid()
    m['assumptions']=[dict(assumption_id=aid,owner=dict(kind='model'),statement='Steady',evidence_links=[])];signed(m)
    versions=[]
    for n in range(18):
        v=version();b,s=link(v,m);a=sample(D['ApproachAssumption1']);a['role']='proposed_model_condition'
        v['content']['assumptions']=[a]
        if versions:
            prior=versions[-1];prior_a=prior['content']['assumptions'][0]
            s['assumption_refs']=[dict(kind='model',binding_id=b['binding_id'],assumption_id=aid,
                origin=dict(approach_version_id=prior['approach_version_id'],assumption_id=prior_a['assumption_id'],digest=prior['digest']))]
        signed(v);versions.append(v)
    with pytest.raises(ValueError,match='depth'):closure(versions[-1],models=[m],approach_versions=versions[:-1])
    assert closure(versions[14],models=[m],approach_versions=versions[:14])

def test_aggregate_content_and_entity_limits():
    v=version()
    for _ in range(64):
        s=sample(D['ApproachStep1'])
        s.update(purpose='x'*4096,rationale='x'*4096,remaining_work='x'*4096)
        s['intent'].update(transformation='x'*4096,inputs='x'*4096,outputs='x'*4096)
        v['content']['steps'].append(s)
    signed(v)
    with pytest.raises(ValueError,match='content byte'):closure(v)
    with pytest.raises(ValueError,match='entity limit'):closure(evidence=[evidence() for _ in range(1000)])

def test_aggregate_bytes_and_combined_prior_record_limit():
    rows=[]
    for _ in range(1000):
        e=evidence();e.update(content='x'*4096,source_refs=['x'*4096]);rows.append(e)
    with pytest.raises(ValueError,match='byte limit'):closure(evidence=rows)
    m=model()
    configs=[config(m) for _ in range(33)]
    runs=[sample(D['ApproachRunContext1']) for _ in range(32)]
    with pytest.raises(ValueError,match='Prior record limit'):closure(models=[m],configurations=configs,run_contexts=runs)

def test_saved_envelope_rejects_another_root_and_case_binding():
    v=version();c=closure(v)
    with pytest.raises(ValueError):validate_saved(dict(version=version(),closure=c))
    m=model();v=version();link(v,m);ancestor=closure(v,models=[m]);cfg=config(m,ancestor)
    cfg['approach_binding']['case_id']=uid();signed(cfg)
    outer=version();outer['content']['basis_refs']=[dict(kind='configuration',configuration_revision_id=cfg['configuration_revision_id'],reason='Case',relation='context')];signed(outer)
    with pytest.raises(ValueError,match='case'):closure(outer,models=[m],approach_versions=[v],configurations=[cfg])

def test_pinned_case_requires_a_matching_nonnull_model_binding():
    m=model();v=version();b,_=link(v,m)
    case=sample(D['ApproachCase1']);case['binding_id']=None
    v['content']['cases']=[case];signed(v)
    ancestor=closure(v,models=[m]);cfg=config(m,ancestor)
    cfg['approach_binding']['case_id']=case['case_id'];signed(cfg)
    outer=version();outer['content']['basis_refs']=[dict(kind='configuration',configuration_revision_id=cfg['configuration_revision_id'],reason='Case',relation='context')];signed(outer)
    with pytest.raises(ValueError,match='case'):closure(outer,models=[m],approach_versions=[v],configurations=[cfg])

@pytest.mark.parametrize('change',['result_run','result_bundle','missing_as_zero'])
def test_run_results_repeated_identities_and_missing_values(change):
    m=model();p=sample(D['Port']);p['definition_version_id']=m['definitions'][0]['definition_version_id']
    m['definitions'][0]['ports']=[p];m['ports']=[p];signed(m)
    cfg=config(m);run=sample(D['ApproachRunContext1'])
    run.update(study_id=SID,configuration_revision_id=cfg['configuration_revision_id'],configuration_digest=cfg['digest'],model_revision_id=m['model_revision_id'],model_digest=m['digest'],context=cfg['context_snapshot'])
    run['request'].update(run_id=run['run_id'],scope=SID)
    result=sample(D['RetainedResults']);result.update(run_id=run['run_id'],bundle_digest=run['request']['bundle_digest'])
    if change=='result_run':result['run_id']=uid()
    elif change=='result_bundle':result['bundle_digest']='b'*64
    else:result['outputs']=[dict(target=dict(instance_id=m['root_instance_id'],port_id=p['port_id']),value=0,units='',availability='unavailable',reason='Failed',producer_completed=False,assigned=False)]
    run['results']=result;signed(run)
    v=version();v['content']['basis_refs']=[dict(kind='run',run_id=run['run_id'],reason='Result',relation='context')];signed(v)
    with pytest.raises(ValueError):closure(v,models=[m],configurations=[cfg],run_contexts=[run])


def native_root_shape():
    """Production snapshot: separate root, repeated children and actual connection."""
    m=model();m['root_instance_id']=uid()
    d=m['definitions'][0];d['kind']='explicit_component'
    output=sample(D['Port']);output.update(definition_version_id=d['definition_version_id'],direction='output')
    incoming=sample(D['Port']);incoming.update(definition_version_id=d['definition_version_id'],direction='input')
    d['ports']=[output,incoming];m['ports']=deepcopy(d['ports'])
    child=m['instances'][0];other=dict(child,instance_id=uid());m['instances'].append(other)
    connection=dict(connection_id=uid(),source_ref=dict(instance_id=child['instance_id'],port_id=output['port_id']),target_ref=dict(instance_id=other['instance_id'],port_id=incoming['port_id']))
    m['connections']=[connection]
    m['assumptions']=[dict(assumption_id=uid(),owner=owner,statement='Exact owner condition',evidence_links=[]) for owner in (dict(kind='model'),dict(kind='instance',instance_id=child['instance_id']))]
    signed(m);v=version();binding,step=link(v,m);bid=binding['binding_id']
    step['implementation_refs']=[dict(kind='model',binding_id=bid),dict(kind='instance',binding_id=bid,instance_id=child['instance_id']),dict(kind='port',binding_id=bid,instance_id=child['instance_id'],port_id=output['port_id']),dict(kind='connection',binding_id=bid,connection_id=connection['connection_id'])]
    step['assumption_refs']=[dict(kind='model',binding_id=bid,assumption_id=a['assumption_id'],origin=None) for a in m['assumptions']]
    signed(v)
    return v,m


def change_native_root_shape(v,m,change):
    refs=v['content']['steps'][0]['implementation_refs']
    if change=='missing_instance':refs[1]['instance_id']=m['root_instance_id']
    elif change=='duplicate_instance':m['instances'].append(deepcopy(m['instances'][0]))
    elif change=='foreign_port':refs[2]['port_id']=uid()
    elif change=='root_port':refs[2]['instance_id']=m['root_instance_id']
    elif change=='root_connection':m['connections'][0]['source_ref']['instance_id']=m['root_instance_id']
    elif change=='root_assumption':m['assumptions'][1]['owner']['instance_id']=m['root_instance_id']
    elif change=='missing_definition':m['instances'][0]['definition_version_id']=uid()
    elif change=='root_uuid':m['root_instance_id']='not-a-uuid'
    signed(m);signed(v)


@pytest.mark.parametrize('change',[None,'missing_instance','duplicate_instance','foreign_port','root_port','root_connection','root_assumption','missing_definition','root_uuid'])
def test_native_separate_root_preserves_exact_component_membership(change):
    v,m=native_root_shape()
    assert m['root_instance_id'] not in {i['instance_id'] for i in m['instances']}
    change_native_root_shape(v,m,change)
    if change is None:assert closure(v,models=[m])['models']==[m]
    else:
        with pytest.raises(ValueError):closure(v,models=[m])


#43.2 descriptive retained semantics, independently of authorization.
def descriptive_version():
    v=version();v['schema_version']='2'
    v['content'].update(schema_version='2', original_question=None, elaboration=None, limit_items=[])
    return signed(v)

def descriptive_model(unit_kind='legacy'):
    m=model();m['schema_version']='4';d=m['definitions'][0]
    p=sample(D['Port']);p.update(definition_version_id=d['definition_version_id'], units='m')
    if unit_kind!='legacy':p['units']={'kind':unit_kind, **({'expression':'m'} if unit_kind=='physical' else {})}
    d['ports']=[p];d['quantity_definitions']=[dict(port_id=p['port_id'],statement='Exact distance')]
    m['ports']=[deepcopy(p)]
    return signed(m)

@pytest.mark.parametrize('unit_kind',['legacy','physical','dimensionless','unspecified'])
def test_polish_definition_descriptions_keep_exact_units_and_version_local_ids(unit_kind):
    m=descriptive_model(unit_kind);old=deepcopy(m['definitions'][0]);old['definition_version_id']=uid()
    old['ports'][0]['definition_version_id']=old['definition_version_id']
    old['quantity_definitions'][0]['statement']='Earlier exact meaning'
    m['definitions'].append(old);m['ports'].extend(deepcopy(old['ports']));signed(m)
    v=descriptive_version();link(v,m);before=deepcopy(m)
    c=closure(v,models=[m]);assert c['schema_version']=='3' and c['models']==[before]
    assert validate_saved(dict(version=v,closure=c))['closure']==c
    assert m==before

@pytest.mark.parametrize('fault',['duplicate','missing','wrong_definition'])
def test_polish_quantity_identity_and_membership_fail_semantically(fault):
    m=descriptive_model();d=m['definitions'][0];q=d['quantity_definitions'][0]
    if fault=='duplicate':d['quantity_definitions'].append(dict(q,statement='Different statement for same port'))
    elif fault=='missing':q['port_id']=uid()
    else:
        other=deepcopy(d);other['definition_version_id']=uid();other['ports'][0].update(definition_version_id=other['definition_version_id'],port_id=uid());other['quantity_definitions']=[]
        m['definitions'].append(other);m['ports'].extend(other['ports']);q['port_id']=other['ports'][0]['port_id']
    signed(m);v=descriptive_version();link(v,m)
    # All three pass the structural contract; the retained resolver must reject.
    from hyprn_mvp_app.modeling import validate
    validate('ModelRevision4',m)
    with pytest.raises(ValueError,match='quantity|port_id'):closure(v,models=[m])

def test_polish_limit_only_evidence_reachability_and_tamper():
    v=descriptive_version();e=evidence()
    v['content']['limit_items']=[dict(limit_id=uid(),statement='Only tested at room temperature',evidence_links=[dict(evidence_version_id=e['evidence_version_id'],relation='challenges')])];signed(v)
    c=closure(v,evidence=[e]);assert c['evidence']==[e]
    broken=deepcopy(c);broken['evidence'][0]['content']='tampered'
    with pytest.raises(ValueError,match='digest'):validate_closure(broken)
    for fault in ('duplicate_id','duplicate_link','missing','foreign','unknown'):
        bad=deepcopy(v);sources=[deepcopy(e)];item=bad['content']['limit_items'][0]
        if fault=='duplicate_id':bad['content']['limit_items'].append(dict(item,statement='Different statement'))
        if fault=='duplicate_link':item['evidence_links']*=2
        if fault=='missing':sources=[]
        if fault=='foreign':sources[0]['study_id']=uid()
        if fault=='unknown':item['native_execution']=True
        signed(bad)
        with pytest.raises(ValueError):closure(bad,evidence=sources)

@pytest.mark.parametrize('old_kind',['legacy','typed','descriptive'])
def test_polish_ancestor_subclosure_keeps_own_schema_and_digest(old_kind):
    m=model() if old_kind=='legacy' else descriptive_model('physical')
    if old_kind=='typed':
        m['schema_version']='3';m['required_capabilities']=['unit_declarations/1'];del m['definitions'][0]['quantity_definitions'];signed(m)
    old=descriptive_version() if old_kind=='descriptive' else version();link(old,m)
    ancestor=closure(old,models=[m]);cfg=config(m,ancestor)
    outer=descriptive_version();outer['content']['basis_refs']=[dict(kind='configuration',configuration_revision_id=cfg['configuration_revision_id'],reason='Exact ancestor',relation='context')];signed(outer)
    c=closure(outer,models=[m],approach_versions=[old],configurations=[cfg])
    assert c['schema_version']=='3' and ancestor['schema_version']==('3' if old_kind=='descriptive' else '1')
    assert validate_closure(c)==c
    c['configurations'][0]['approach_binding']['closure_digest']=c['digest'];signed(c['configurations'][0]);signed(c)
    with pytest.raises(ValueError,match='Ancestor'):validate_closure(c)

def test_polish_old_approach_model4_is_explicit_new_closure_not_downgrade():
    v=version();m=descriptive_model();link(v,m);c=closure(v,models=[m])
    assert c['schema_version']=='3' and c['approach_versions'][0]==v
    c['schema_version']='1';signed(c)
    with pytest.raises(ValueError):validate_closure(c)


@pytest.mark.parametrize('ancestor_model',['typed','descriptive'])
@pytest.mark.parametrize('root_approach',['old','new'])
def test_polish_model2_root_with_newer_ancestor_preserves_exact_families(ancestor_model,root_approach):
    prior_model=descriptive_model('physical')
    if ancestor_model=='typed':
        prior_model['schema_version']='3';prior_model['required_capabilities']=['unit_declarations/1'];del prior_model['definitions'][0]['quantity_definitions'];signed(prior_model)
    prior=version();link(prior,prior_model);ancestor=closure(prior,models=[prior_model]);cfg=config(prior_model,ancestor)
    current_model=model();v=version() if root_approach=='old' else descriptive_version();link(v,current_model)
    v['content']['basis_refs']=[dict(kind='configuration',configuration_revision_id=cfg['configuration_revision_id'],reason='Exact earlier model',relation='context')];signed(v)
    c=closure(v,models=[current_model,prior_model],approach_versions=[prior],configurations=[cfg])
    assert c['schema_version']==('1' if ancestor_model=='typed' and root_approach=='old' else '3')
    assert next(m for m in c['models'] if m['model_id']==current_model['model_id'])==current_model
    assert validate_saved(dict(version=v,closure=c))['version']==v

def test_polish_conflicting_limit_source_rejects_even_with_same_id():
    v=descriptive_version();e=evidence();other=dict(e,content='Different immutable bytes')
    v['content']['limit_items']=[dict(limit_id=uid(),statement='Restriction',evidence_links=[dict(evidence_version_id=e['evidence_version_id'],relation='context')])];signed(v)
    with pytest.raises(ValueError,match='Conflicting'):closure(v,evidence=[e,other])
