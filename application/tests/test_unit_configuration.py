"""Guarded configuration admission; private proofs/source history are explicit doubles.

Real Store/Auth/Coordinator and immutable saves. No numerical or native execution.
"""
from copy import deepcopy
import base64
import hashlib
import json
import pytest
import scoped_fixture as guard
from checks import PROJECTION_SCOPE
SCOPE = PROJECTION_SCOPE or guard.scope_from_environment()
guard.validate_scope(SCOPE)

from test_assumption_authoring import env, statement
from test_assumption_configuration import config as legacy_config, preview, body, counts, sample, D
from test_approach_configuration import pin
from hyprn_mvp_app.configuration import Configurations
from hyprn_mvp_app.modeling import validate, UNIT_CATALOG_DIGEST
from hyprn_mvp_app.store import DomainError, digest, uid, canonical
from hyprn_mvp_app.units import resolved_model_units
from hyprn_mvp_app.result_bindings import ResultBindings, verify_dependencies
from hyprn_mvp_app.history import History
from hyprn_mvp_app.scientific_configuration import project_scientific_configuration as project


def signed(model):
    model['ports'] = deepcopy([p for d in model['definitions'] for p in d['ports']])
    model['digest'] = digest({k:v for k,v in model.items() if k != 'digest'})


@pytest.fixture
def config(legacy_config):
    e,c,r,m,record = legacy_config
    m['schema_version'] = '3'; m['required_capabilities'].append('unit_declarations/1')
    d = m['definitions'][0]
    source = b"raise RuntimeError('candidate must remain inert')\n"
    sha = hashlib.sha256(source).hexdigest()
    m['source_files'] = [dict(encoding='base64',media_type='text/x-python',bytes=base64.b64encode(source).decode(),sha256=sha)]
    d['source_refs'] = [sha]
    d['ports'] = [dict(sample(D['Port3']),port_id=uid(),definition_version_id=d['definition_version_id'],
        direction=direction,name=name,units=dict(kind='physical',expression='J/kg'))
        for direction,name in [('input','energy'),('output','result')]]
    m['instances'] = [m['instances'][1]]
    signed(m)
    r.update(schema_version='4',approach_selection=None,
        context_override=dict(schema_version='1',description='Specific scenario',boundary='Specific boundary'))
    r['inputs'] = [dict(sample(D['LiteralRequest']),target=dict(instance_id=m['instances'][0]['instance_id'],port_id=d['ports'][0]['port_id']),value=2,units='J/kg')]
    r['inputs'][0]['provenance']['evidence_version_ids'] = [record['evidence_version_id']]
    r['criteria'] = [dict(sample(D['Criterion']),target=dict(instance_id=m['instances'][0]['instance_id'],port_id=d['ports'][1]['port_id']),units='J/kg')]
    r['criteria'][0]['evidence_version_ids'] = [record['evidence_version_id']]
    t=e['transport'];t.caps['contract_versions'].append('1.3');t.caps['schema_versions'].append('3')
    t.caps['capabilities'].append(dict(t.caps['capabilities'][0],id='unit_declarations'))
    original=e['coord'].model.transport
    e['proof_mutation']=lambda proof:None
    def transport(method,path,raw,headers):
        if not path.endswith('/configuration-compatibility'):return original(method,path,raw,headers)
        status,response=original(method,path,raw,headers)
        candidate=json.loads(raw)['configuration_candidate'];proof=response['data']
        units=resolved_model_units(m)
        versions={i['instance_id']:i['definition_version_id'] for i in m['instances']}
        proof['input_interpretations']=[]
        for item in candidate['inputs']:
            key=(item['target']['instance_id'],versions[item['target']['instance_id']],item['target']['port_id'])
            factor=1000000 if item['units']=='MJ/kg' else 1
            proof['input_interpretations'].append(dict(target=item['target'],conversion=dict(
                policy='openmdao-linear-catalog-1',catalog_digest=UNIT_CATALOG_DIGEST,
                source_units=item['units'],destination_units=units[key],factor=factor,destination_value=item['value']*factor)))
        e['proof_mutation'](proof)
        return status,response
    e['coord'].model.transport=transport
    return legacy_config


def retained_versions(m):
    first=m['definitions'][0];old=deepcopy(first)
    old['definition_version_id']=uid()
    for p in old['ports']:
        p.update(definition_version_id=old['definition_version_id'],units=dict(kind='unspecified'))
    m['definitions'].insert(0,old);signed(m)
    return old


@pytest.mark.parametrize('selection',['input','output','internal','no_rebind','second_active'])
@pytest.mark.parametrize('action',['preview','commit'])
def test_unresolved_exact_active_occurrences_block_before_private_proof(config,selection,action):
    e,c,r,m,_=config;old=retained_versions(m);instance=m['instances'][0]
    active=m['definitions'][1];port=active['ports'][0 if selection=='input' else 1]
    if selection in ('no_rebind','second_active'):
        if selection=='second_active':
            instance=dict(instance_id=uid(),definition_version_id=old['definition_version_id'],name='Old active')
            m['instances'].append(instance)
        else:instance['definition_version_id']=old['definition_version_id']
        port=old['ports'][0]
    else:
        port['units']=dict(kind='unspecified')
        if selection=='internal':
            m['connections']=[dict(connection_id=uid(),source_ref=dict(instance_id=instance['instance_id'],port_id=port['port_id']),target_ref=deepcopy(r['inputs'][0]['target']))]
    signed(m);before=canonical(m);e['transport'].calls.clear()
    with pytest.raises(DomainError) as caught:
        if action=='preview':preview(config)
        else:c.commit(e['actor'],e['sid'],body(config,dict(candidate_digest='0'*64)))
    assert caught.value.code=='invalid_configuration' and caught.value.status==422
    assert any(i['code']=='unit_unspecified' and i['path']==f"/instances/{instance['instance_id']}/definitions/{instance['definition_version_id']}/ports/{port['port_id']}/units" and i['element_ref']==port['port_id'] for i in caught.value.fields)
    assert not any(path.endswith('/configuration-compatibility') for _,path,_ in e['transport'].calls)
    assert counts(e)==(0,0,0) and canonical(m)==before


@pytest.mark.parametrize('pinned',[False,True])
def test_exact_model3_config4_save_replay_and_private3_projection(config,pinned):
    e,c,r,m,record=config;old=retained_versions(m);before=canonical(m)
    saved_approach=pin(config,extra_evidence=True)[0] if pinned else None
    p=preview(config);candidate=p['resolved_candidate'];scientific=project(candidate)
    assert scientific['schema_version']=='3'
    assert scientific['context_snapshot']==dict(description='Specific scenario',boundary='Specific boundary',notes=r['notes'])
    assert scientific['evidence_snapshots']==[record]
    assert scientific['criteria']==r['criteria']
    assert 'unit_declarations/1' in scientific['required_capabilities']
    assert project(candidate)==scientific and canonical(m)==before
    request=body(config,p);saved=c.commit(e['actor'],e['sid'],request)
    validate('FrozenConfiguration5',saved)
    assert saved['schema_version']=='5' and saved['configuration']['schema_version']=='4'
    assert saved['model_snapshot']==m and saved['model_snapshot']['definitions'][0]==old
    assert saved['approach_closure']==(saved_approach['closure'] if pinned else None)
    projected=project(saved['configuration']);validate('ModelingConfigurationRevision3',projected)
    assert projected['digest']==digest({k:v for k,v in projected.items() if k!='digest'})
    assert projected['digest']!=saved['configuration']['digest']
    e['coord'].model.transport=lambda *a:(_ for _ in ()).throw(AssertionError('replay is local'))
    assert c.commit(e['actor'],e['sid'],request)==saved
    assert c.read(e['actor'],e['sid'],saved['configuration']['configuration_revision_id'])==saved


@pytest.mark.parametrize('mv,cv,allowed', [('1','1',True),('1','2',True),('2','1',False),('2','2',False),('2','3',True),('2','4',True),('1','4',False),('3','1',False),('3','2',False),('3','3',False),('3','4',True)])
def test_explicit_pairings(mv,cv,allowed):
    if allowed:Configurations.require_version_pair(dict(schema_version=cv),dict(schema_version=mv))
    else:
        with pytest.raises(DomainError):Configurations.require_version_pair(dict(schema_version=cv),dict(schema_version=mv))


@pytest.mark.parametrize('corrupt',['source','aggregate','unused_shape','digest'])
def test_retained_corruption_rejected_without_save(config,corrupt):
    e,c,r,m,_=config;old=retained_versions(m)
    if corrupt=='source':m['source_files'][0]['bytes']=base64.b64encode(b'tamper').decode();signed(m)
    elif corrupt=='aggregate':m['ports'].pop();m['digest']=digest({k:v for k,v in m.items() if k!='digest'})
    elif corrupt=='unused_shape':old['ports'][0]['units']['extra']=True;signed(m)
    else:m['digest']='0'*64
    with pytest.raises(DomainError):preview(config)
    assert counts(e)==(0,0,0)


def source_history(m,r):
    source=deepcopy(m);port=source['definitions'][-1]['ports'][1]
    port['units']=dict(kind='physical',expression='MJ/kg')
    source.update(model_id=uid(),model_revision_id=uid())
    definition=source['definitions'][-1];old=definition['definition_version_id'];definition['definition_version_id']=uid()
    for p in definition['ports']:p['definition_version_id']=definition['definition_version_id']
    for i in source['instances']:
        if i['definition_version_id']==old:i['definition_version_id']=definition['definition_version_id']
    signed(source)
    result=sample(D['RetainedResults']);rid=result['run_id']
    result['outputs']=[dict(target=dict(instance_id=source['instances'][0]['instance_id'],port_id=port['port_id']),
        value=1,units='MJ/kg',availability='available',reason=None,assigned=True,producer_completed=True)]
    result['execution'].update(state='finished',exit_code=0)
    result['applicability']['state']='unassessed'
    return rid,dict(model_snapshot=source,configuration=dict(digest='a'*64,name='Original upstream'),results=result)


@pytest.mark.parametrize('bad,value',[(None,0),(None,1),*[(bad,1) for bad in ['catalog','factor','value','source_units','destination_units','offset','missing','duplicate']]])
def test_source_result_original_units_and_private_conversion_proof(config,monkeypatch,bad,value):
    e,c,r,m,_=config;rid,history=source_history(m,r);result=history['results'];result['outputs'][0]['value']=value;original=canonical(history)
    # Retained history loading is proven by the history tests; this double supplies already-verified
    # immutable authority to exercise the actual scalar resolver and config path.
    monkeypatch.setattr(ResultBindings,'retained',lambda self,*a:(deepcopy(history),{},{}))
    monkeypatch.setattr(History,'recheck',lambda *a:None)
    r['inputs'][0]=dict(kind='run_result',target=r['inputs'][0]['target'],source_run_id=rid,
        source_output=result['outputs'][0]['target'],expected_results_digest=digest(result),provenance=r['inputs'][0]['provenance'])
    def mutate(proof):
        conversion=proof['input_interpretations'][0]['conversion']
        if bad=='catalog':conversion['catalog_digest']='0'*64
        elif bad=='factor':conversion['factor']=float('inf')
        elif bad=='value':conversion['destination_value']=0
        elif bad=='source_units':conversion['source_units']='kg'
        elif bad=='destination_units':conversion['destination_units']='MJ/kg'
        elif bad=='offset':conversion['offset']=1
        elif bad=='missing':proof['input_interpretations']=[]
        elif bad=='duplicate':proof['input_interpretations']*=2
    e['proof_mutation']=mutate
    if bad:
        with pytest.raises(DomainError):preview(config)
        assert counts(e)==(0,0,0);return
    p=preview(config);request=body(config,p);saved=c.commit(e['actor'],e['sid'],request)
    item=saved['configuration']['inputs'][0];binding=item['result_binding']
    assert item['value']==binding['original_value']==value
    assert item['units']==binding['original_units']=='MJ/kg'
    assert binding['conversion']==dict(policy='openmdao-linear-catalog-1',catalog_digest=UNIT_CATALOG_DIGEST,source_units='MJ/kg',destination_units='J/kg',factor=1000000,destination_value=1000000 if value else 0)
    assert project(saved['configuration'])['inputs'][0]['value']==value
    assert canonical(history)==original
    resolved=ResultBindings(e['store']).resolve(e['actor'],e['sid'],r['inputs'][0])
    assert 'applicability' not in resolved['outcomes']


@pytest.mark.parametrize('bad',['unspecified','mismatch','unavailable','not_completed'])
def test_typed_source_output_refuses_invalid_scalar(config,bad):
    e,c,r,m,_=config;rid,h=source_history(m,r);output=h['results']['outputs'][0]
    if bad=='unspecified':h['model_snapshot']['definitions'][-1]['ports'][1]['units']=dict(kind='unspecified');signed(h['model_snapshot'])
    elif bad=='mismatch':output['units']='J/kg'
    elif bad=='unavailable':output['availability']='unavailable'
    else:output['producer_completed']=False
    with pytest.raises(DomainError,match='source_result_unavailable'):ResultBindings(e['store'])._output(rid,h,output['target'])


@pytest.mark.parametrize('race',['evidence','membership','association','approach'])
def test_commit_rechecks_exact_local_pins(config,race):
    e,c,r,m,_=config;pin(config);request=body(config);original=e['store'].command
    def command(*args,**kwargs):
        with e['store'].connection(write=True) as db:
            if race=='membership':db.execute('DELETE FROM memberships')
            elif race=='association':db.execute('DELETE FROM model_associations')
            elif race=='evidence':
                db.execute('DROP TRIGGER immutable_evidence_update');db.execute("UPDATE evidence SET payload=json_set(payload,'$.title','Changed')")
            else:
                db.execute('DROP TRIGGER immutable_approach_version_update');db.execute("UPDATE approach_versions SET payload=json_set(payload,'$.closure.digest',?)",('0'*64,))
        return original(*args,**kwargs)
    e['store'].command=command
    with pytest.raises(DomainError):c.commit(e['actor'],e['sid'],request)
    assert counts(e)==(0,0,0)


@pytest.mark.parametrize('bad',['contract','schema','capability','unsupported'])
def test_model3_capability_required_before_compatibility(config,bad):
    e,c,r,m,_=config;caps=e['transport'].caps
    if bad=='contract':caps['contract_versions'].remove('1.3')
    elif bad=='schema':caps['schema_versions'].remove('3')
    elif bad=='capability':caps['capabilities']=caps['capabilities'][:-1]
    else:caps['capabilities'][-1]['supported']=False
    with pytest.raises(DomainError,match='unsupported_capability'):preview(config)
    assert not any(path.endswith('/configuration-compatibility') for _,path,_ in e['transport'].calls)
    assert counts(e)==(0,0,0)


@pytest.mark.parametrize('bad',['preview','incompatible'])
def test_stale_or_incompatible_commit_cannot_allocate(config,bad):
    e,c,r,m,_=config;request=body(config)
    if bad=='preview':request['configuration']['name']='Changed case'
    else:e['proof_mutation']=lambda proof:proof.update(compatible=False,diagnostics=[dict(path='/inputs/0/units',code='unit_incompatible',message='Incompatible units',element_ref=r['inputs'][0]['target']['port_id'])])
    with pytest.raises(DomainError) as caught:c.commit(e['actor'],e['sid'],request)
    assert caught.value.code==('reference_conflict' if bad=='preview' else 'invalid_configuration')
    assert counts(e)==(0,0,0)


def test_mixed_legacy_definition_preserves_empty_dimensionless_and_http_freeze(config):
    e,c,r,m,_=config;old=retained_versions(m)
    for p in old['ports']:p['units']=''
    m['instances'].append(dict(instance_id=uid(),definition_version_id=old['definition_version_id'],name='Legacy dimensionless'))
    signed(m);before=canonical(m)
    path='/api/1/studies/'+e['sid']+'/configurations'
    response=e['client'].post(path+'/preview',json=r)
    assert response.status_code==200,response.text
    p=response.json()['data'];validate('ConfigurationPreview4',p)
    response=e['client'].post(path,json=body(config,p))
    assert response.status_code==201,response.text
    saved=response.json()['data'];validate('FrozenConfiguration5',saved)
    assert canonical(saved['model_snapshot'])==before


def test_http_unresolved_preview_error_and_no_save(config):
    e,c,r,m,_=config;m['definitions'][0]['ports'][1]['units']=dict(kind='unspecified');signed(m)
    path='/api/1/studies/'+e['sid']+'/configurations'
    for suffix,payload in [('/preview',r),('',body(config,dict(candidate_digest='0'*64)))]:
        response=e['client'].post(path+suffix,json=payload)
        assert response.status_code==422,response.text
        assert response.json()['error']['fields'][0]['code']=='unit_unspecified'
    assert counts(e)==(0,0,0)


@pytest.mark.parametrize('bad',[False,True])
def test_approach_data_only_unspecified_model_allowed_but_configured_closure_resolved(config,bad):
    from hyprn_mvp_app.approach_closure import build_closure, validate_closure
    e,c,r,m,record=config;retained_versions(m)
    frozen=c.commit(e['actor'],e['sid'],body(config));saved=frozen['configuration']
    explanatory=deepcopy(m);explanatory.update(model_id=uid(),model_revision_id=uid(),assumptions=[])
    for d in explanatory['definitions']:
        for p in d['ports']:p['units']=dict(kind='unspecified')
    signed(explanatory)
    version=sample(D['ApproachVersion1']);version['study_id']=e['sid']
    version['content']['basis_refs']=[dict(kind='configuration',configuration_revision_id=saved['configuration_revision_id'],reason='Prior exact case',relation='context')]
    binding=dict(binding_id=uid(),model_id=explanatory['model_id'],model_revision_id=explanatory['model_revision_id'])
    version['content']['model_bindings']=[binding]
    step=sample(D['ApproachStep1']);step.update(implementation_state='linked',remaining_work='',implementation_refs=[dict(kind='model',binding_id=binding['binding_id'])])
    version['content']['steps']=[step]
    version['digest']=digest({k:v for k,v in version.items() if k!='digest'})
    if bad:
        m['definitions'][-1]['ports'][1]['units']=dict(kind='unspecified');signed(m)
    resolution=dict(approach_versions=[],models=[m,explanatory],configurations=[saved],run_contexts=[],evidence=[record])
    before=canonical(resolution)
    if bad:
        with pytest.raises(ValueError):build_closure(version,resolution,study_id=e['sid'])
    else:
        closure=build_closure(version,resolution,study_id=e['sid'])
        assert validate_closure(closure,study_id=e['sid'])==closure
        assert explanatory in closure['models']
    assert canonical(resolution)==before


@pytest.mark.parametrize('bad',[None,'original','factor','catalog','units'])
def test_approach_conversion_keeps_original_scalar_and_exact_destination(config,monkeypatch,bad):
    from hyprn_mvp_app.approach_closure import build_closure
    e,c,r,m,record=config
    original=c.commit(e['actor'],e['sid'],body(config))['configuration']
    rid,h=source_history(m,r)
    source=h['model_snapshot'];source.update(model_id=uid(),model_revision_id=uid());signed(source)
    original=deepcopy(original);original.update(model_id=source['model_id'],model_revision_id=source['model_revision_id'])
    original['digest']=digest({k:v for k,v in original.items() if k!='digest'});h['configuration']=original
    result=h['results'];result['completeness'].update(expected=1,available=1,failed=0,unavailable=0)
    monkeypatch.setattr(ResultBindings,'retained',lambda self,*a:(deepcopy(h),{},{}))
    monkeypatch.setattr(History,'recheck',lambda *a:None)
    r['inputs'][0]=dict(kind='run_result',target=r['inputs'][0]['target'],source_run_id=rid,source_output=result['outputs'][0]['target'],expected_results_digest=digest(result),provenance=r['inputs'][0]['provenance'])
    copied=c.commit(e['actor'],e['sid'],body(config))['configuration']
    item=copied['inputs'][0];conversion=item['result_binding']['conversion']
    if bad=='original':item['value']=conversion['destination_value'];item['units']='J/kg'
    elif bad=='factor':conversion['factor']=2
    elif bad=='catalog':conversion['catalog_digest']='0'*64
    elif bad=='units':conversion['destination_units']='MJ/kg'
    copied['digest']=digest({k:v for k,v in copied.items() if k!='digest'})
    run=sample(D['ApproachRunContext1']);run.update(run_id=rid,study_id=e['sid'],configuration_revision_id=original['configuration_revision_id'],configuration_digest=original['digest'],model_revision_id=source['model_revision_id'],model_digest=source['digest'],context=original['context_snapshot'],results=result)
    run['association']['store_uuid']=uid()
    run['request'].update(run_id=rid,scope=e['sid'],bundle_digest=result['bundle_digest'])
    run['digest']=digest({k:v for k,v in run.items() if k!='digest'})
    version=sample(D['ApproachVersion1']);version['study_id']=e['sid']
    version['content']['basis_refs']=[dict(kind='configuration',configuration_revision_id=copied['configuration_revision_id'],reason='Result reuse',relation='context')]
    version['digest']=digest({k:v for k,v in version.items() if k!='digest'})
    resolution=dict(approach_versions=[],models=[m,source],configurations=[original,copied],run_contexts=[run],evidence=[record])
    if bad:
        with pytest.raises(ValueError):build_closure(version,resolution,study_id=e['sid'])
    else:assert build_closure(version,resolution,study_id=e['sid'])['configurations']


def mixed_saved_approach(config,declaration):
    from test_unit_execution_admission import explanatory_model
    from test_approach_closure import link
    from hyprn_mvp_app.approach import Approaches
    e,c,r,m,_=config;extra=explanatory_model(m,declaration)
    e['transport'].revisions[extra['model_revision_id']]=extra
    with e['store'].connection(write=True) as db:
        db.execute('INSERT INTO model_associations VALUES(?,?,?)',(e['sid'],extra['model_id'],uid()))
    version=sample(D['ApproachVersion1']);link(version,m);link(version,extra)
    service=Approaches(e['store'],e['coord'])
    request=dict(schema_version='1',expected_revision=None,content=version['content'])
    p=service.preview(e['actor'],e['sid'],request)
    draft=service.save_draft(e['actor'],e['sid'],dict(request,command_id=uid(),expected_preview_digest=p['preview_digest']))
    request['expected_revision']=draft['revision'];p=service.preview(e['actor'],e['sid'],request)
    saved=service.save_version(e['actor'],e['sid'],dict(schema_version='1',command_id=uid(),expected_revision=draft['revision'],expected_preview_digest=p['preview_digest']))['saved']
    r.update(schema_version='4',approach_selection=dict(approach_version_id=saved['version']['approach_version_id'],case_id=None))
    return saved


@pytest.mark.parametrize('declaration',['physical','unspecified'])
def test_http_mixed_legacy_selected_preview_save_and_cold_replay(legacy_config,declaration):
    e,c,r,m,_=legacy_config;selected=canonical(m);saved_approach=mixed_saved_approach(legacy_config,declaration)
    client=e['client'];path='/api/1/studies/'+e['sid']+'/configurations'
    p=client.post(path+'/preview',json=r);assert p.status_code==200,p.text
    p=p.json()['data'];assert p['approach_closure']==saved_approach['closure']
    assert project(p['resolved_candidate'])['required_capabilities']==m['required_capabilities']
    request=body(legacy_config,p);response=client.post(path,json=request)
    assert response.status_code==201,response.text
    frozen=response.json()['data'];validate('FrozenConfiguration5',frozen)
    assert frozen['schema_version']=='5' and canonical(frozen['model_snapshot'])==selected
    assert frozen['approach_closure']==saved_approach['closure']
    e['coord'].model.transport=lambda *a:(_ for _ in ()).throw(AssertionError('Replay must use retained bytes'))
    replay=client.post(path,json=request);assert replay.status_code==201,replay.text
    assert replay.json()['data']==frozen
    assert c.read(e['actor'],e['sid'],frozen['configuration']['configuration_revision_id'])==frozen
    changed=deepcopy(request);changed['configuration']['approach_selection']=None
    assert client.post(path,json=changed).status_code==409
    with e['store'].connection(write=True) as db:db.execute('DELETE FROM memberships')
    assert client.post(path,json=request).status_code in (403,404)
    assert counts(e)==(1,1,0)


@pytest.mark.parametrize('race',['approach','membership','association','evidence','study','selected_model'])
def test_mixed_save_rechecks_authority_without_partial_allocation(legacy_config,race):
    e,c,r,m,_=legacy_config;mixed_saved_approach(legacy_config,'unspecified')
    request=body(legacy_config);original=e['store'].command
    if race=='selected_model':
        m['name']='Changed immutable selected model';signed(m)
    else:
        def command(*args,**kwargs):
            with e['store'].connection(write=True) as db:
                if race=='approach':
                    db.execute('DROP TRIGGER immutable_approach_version_update')
                    db.execute("UPDATE approach_versions SET payload=json_set(payload,'$.closure.digest',?)",('0'*64,))
                elif race=='membership':db.execute('DELETE FROM memberships')
                elif race=='association':db.execute('DELETE FROM model_associations')
                elif race=='study':db.execute("UPDATE studies SET revision='changed'")
                else:
                    db.execute('DROP TRIGGER immutable_evidence_update')
                    db.execute("UPDATE evidence SET payload=json_set(payload,'$.title','Changed')")
            return original(*args,**kwargs)
        e['store'].command=command
    with pytest.raises(DomainError):c.commit(e['actor'],e['sid'],request)
    assert counts(e)==(0,0,0)


@pytest.mark.parametrize('linked',[False,True])
def test_ordinary_legacy_configuration_keeps_frozen4(legacy_config,linked):
    e,c,r,m,_=legacy_config;selected=canonical(m)
    if linked:pin(legacy_config)
    else:r.update(schema_version='4',approach_selection=None)
    request=body(legacy_config);saved=c.commit(e['actor'],e['sid'],request)
    validate('FrozenConfiguration4',saved)
    assert canonical(saved['model_snapshot'])==selected
    assert c.commit(e['actor'],e['sid'],request)==saved
