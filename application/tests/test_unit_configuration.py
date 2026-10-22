"""Guarded configuration admission; private proofs/source history are explicit doubles.

New configurations are version 6 on Model4 only: no criteria and no approach binding.
Real Store/Auth/Coordinator and immutable saves. No numerical or native execution.
"""
from copy import deepcopy
import base64
import hashlib
import json
import sqlite3
import pytest
import scoped_fixture as guard
from checks import PROJECTION_SCOPE
SCOPE = PROJECTION_SCOPE or guard.scope_from_environment()
guard.validate_scope(SCOPE)

from test_assumption_authoring import env, evidence, revision, statement, sample, D
from criteria_free import CRITERIA_FREE_CAPABILITY
from hyprn_mvp_app.configuration import Configurations
from hyprn_mvp_app.modeling import validate, UNIT_CATALOG_DIGEST
from hyprn_mvp_app.store import DomainError, digest, uid, canonical
from hyprn_mvp_app.units import resolved_model_units
from hyprn_mvp_app.result_bindings import ResultBindings
from hyprn_mvp_app.history import History
from hyprn_mvp_app.scientific_configuration import project_scientific_configuration as project


def signed(model):
    model['ports'] = deepcopy([p for d in model['definitions'] for p in d['ports']])
    model['digest'] = digest({k:v for k,v in model.items() if k != 'digest'})


def rehash(value):
    value['digest'] = digest({k:v for k,v in value.items() if k != 'digest'})
    return value


@pytest.fixture
def config(env):
    """A Model4 revision with typed J/kg ports and a ConfigurationRequest6 that supplies its input."""
    t=env['transport'];record=evidence(env);eid=record['evidence_version_id']
    t.draft['assumptions']=[statement(eid)]
    m=revision(t.draft);t.revisions[m['model_revision_id']]=m
    m['schema_version']='4';m['required_capabilities']+=['unit_declarations/1','quantity_definitions/1']
    d=m['definitions'][0];d['quantity_definitions']=[]
    source = b"raise RuntimeError('candidate must remain inert')\n"
    sha = hashlib.sha256(source).hexdigest()
    m['source_files'] = [dict(encoding='base64',media_type='text/x-python',bytes=base64.b64encode(source).decode(),sha256=sha)]
    d['source_refs'] = [sha]
    d['ports'] = [dict(sample(D['Port3']),port_id=uid(),definition_version_id=d['definition_version_id'],
        direction=direction,name=name,units=dict(kind='physical',expression='J/kg'))
        for direction,name in [('input','energy'),('output','result')]]
    m['instances'] = [m['instances'][1]]
    signed(m)
    caps=t.caps;base=caps['capabilities'][0]
    caps['contract_versions']+=['1.3'];caps['schema_versions']+=['3','4']
    caps['capabilities']+=[dict(base,id='resolved_configuration',version='3'),dict(base,id='unit_declarations'),
        dict(base,id='quantity_definitions'),deepcopy(CRITERIA_FREE_CAPABILITY)]
    original=env['coord'].model.transport
    env['proof_mutation']=lambda proof:None
    def transport(method,path,raw,headers):
        if not path.endswith('/configuration-compatibility'):return original(method,path,raw,headers)
        with sqlite3.connect(env['store'].path,timeout=0) as db:
            db.execute('BEGIN IMMEDIATE');db.rollback()
        body=json.loads(raw);candidate=body['configuration_candidate']
        t.calls.append((method,path,deepcopy(body)))
        proof=sample(D['CompatibilityResult2'])
        proof.update(compatible=True,candidate_digest=digest(candidate),model_digest=m['digest'],
            model_revision_id=m['model_revision_id'],required_capabilities=candidate['required_capabilities'])
        units=resolved_model_units(m)
        versions={i['instance_id']:i['definition_version_id'] for i in m['instances']}
        proof['input_interpretations']=[]
        for item in candidate['inputs']:
            key=(item['target']['instance_id'],versions[item['target']['instance_id']],item['target']['port_id'])
            factor=1000000 if item['units']=='MJ/kg' else 1
            proof['input_interpretations'].append(dict(target=item['target'],conversion=dict(
                policy='openmdao-linear-catalog-1',catalog_digest=UNIT_CATALOG_DIGEST,
                source_units=item['units'],destination_units=units[key],factor=factor,destination_value=item['value']*factor)))
        env['proof_mutation'](proof)
        return 200,dict(schema_version='1',request_id=uid(),data=proof)
    env['coord'].model.transport=transport
    r=sample(D['ConfigurationRequest6'])
    r.update(study_id=env['sid'],model_id=m['model_id'],model_revision_id=m['model_revision_id'],
        context_source=dict(kind='current_study',expected_study_revision=env['study']['revision']),
        assumptions=[{k:v for k,v in statement(eid).items() if k!='owner'}],general_context_evidence_version_ids=[eid],
        context_override=dict(schema_version='1',description='Specific scenario',boundary='Specific boundary'))
    r['inputs'] = [dict(sample(D['LiteralRequest']),target=dict(instance_id=m['instances'][0]['instance_id'],port_id=d['ports'][0]['port_id']),value=2,units='J/kg')]
    r['inputs'][0]['provenance']['evidence_version_ids'] = [eid]
    validate('ConfigurationRequest6',r)
    return env,Configurations(env['store'],env['coord']),r,m,record


def preview(config):
    e,c,r,_,_=config
    return c.preview(e['actor'],e['sid'],r)[0]


def body(config,p=None):
    return dict(command_id=uid(),configuration_id=None,expected_revision=None,
        configuration=deepcopy(config[2]),expected_preview_digest=(p or preview(config))['candidate_digest'])


def counts(env):
    with env['store'].connection() as db:
        return tuple(db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] for table in ('configurations','configuration_families','outbox'))


def compatibility_calls(e):
    return [body for _,path,body in e['transport'].calls if path.endswith('/configuration-compatibility')]


def retained4(configuration):
    """The retained revision-4 shape of the same immutable values: empty criteria, no approach."""
    retained=deepcopy(configuration);retained.update(schema_version='4',criteria=[],approach_binding=None)
    return validate('ConfigurationRevision4',rehash(retained))


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
    assert not compatibility_calls(e)
    assert counts(e)==(0,0,0) and canonical(m)==before


def test_exact_model4_config6_save_replay_and_criteria_free_private_projection(config):
    e,c,r,m,record=config;old=retained_versions(m);before=canonical(m)
    p=preview(config);validate('ConfigurationPreview8',p)
    assert p['schema_version']=='8' and 'approach_closure' not in p
    candidate=p['resolved_candidate'];scientific=project(candidate)
    assert candidate['schema_version']=='6' and not {'criteria','approach_binding'}&candidate.keys()
    assert scientific['schema_version']=='5' and 'criteria' not in scientific
    assert compatibility_calls(e)==[dict(model_revision_id=m['model_revision_id'],configuration_candidate=scientific)]
    assert scientific['context_snapshot']==dict(description='Specific scenario',boundary='Specific boundary',notes=r['notes'])
    assert scientific['evidence_snapshots']==[record]
    assert {'unit_declarations/1','quantity_definitions/1'}<=set(scientific['required_capabilities'])
    assert project(candidate)==scientific and canonical(m)==before
    request=body(config,p);saved=c.commit(e['actor'],e['sid'],request)
    validate('FrozenConfiguration9',saved)
    assert saved['schema_version']=='9' and saved['configuration']['schema_version']=='6'
    assert not {'criteria','approach_binding'}&saved['configuration'].keys() and 'approach_closure' not in saved
    assert saved['model_snapshot']==m and saved['model_snapshot']['definitions'][0]==old
    projected=project(saved['configuration']);validate('ModelingConfigurationRevision5',projected)
    assert projected['digest']==digest({k:v for k,v in projected.items() if k!='digest'})
    assert projected['digest']!=saved['configuration']['digest']
    e['coord'].model.transport=lambda *a:(_ for _ in ()).throw(AssertionError('replay is local'))
    assert c.commit(e['actor'],e['sid'],request)==saved
    assert c.read(e['actor'],e['sid'],saved['configuration']['configuration_revision_id'])==saved


@pytest.mark.parametrize('mv,cv,allowed', [('1','1',True),('1','2',True),('2','1',False),('2','2',False),('2','3',True),('2','4',True),('1','4',False),('3','1',False),('3','2',False),('3','3',False),('3','4',True),
    ('4','6',True),('4','4',True),('4','3',False),('1','6',False),('2','6',False),('3','6',False)])
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
    with pytest.raises(DomainError) as caught:preview(config)
    assert caught.value.code=='backend_unavailable' and caught.value.status==503
    assert not compatibility_calls(e)
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
        with pytest.raises(DomainError) as caught:preview(config)
        assert caught.value.code in ('backend_unavailable','invalid_configuration'),caught.value.code
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


@pytest.mark.parametrize('race',['evidence','membership','association','study','selected_model'])
def test_commit_rechecks_exact_local_pins(config,race):
    e,c,r,m,_=config;request=body(config);original=e['store'].command
    if race=='selected_model':
        m['name']='Changed immutable selected model';signed(m)
    else:
        def command(*args,**kwargs):
            with e['store'].connection(write=True) as db:
                if race=='membership':db.execute('DELETE FROM memberships')
                elif race=='association':db.execute('DELETE FROM model_associations')
                elif race=='study':db.execute("UPDATE studies SET revision='changed'")
                else:
                    db.execute('DROP TRIGGER immutable_evidence_update');db.execute("UPDATE evidence SET payload=json_set(payload,'$.title','Changed')")
            return original(*args,**kwargs)
        e['store'].command=command
    with pytest.raises(DomainError):c.commit(e['actor'],e['sid'],request)
    assert counts(e)==(0,0,0)


@pytest.mark.parametrize('bad',['resolved','criteria_free','criteria_free_unsupported','quantities','units'])
def test_model4_configuration6_capabilities_required_before_compatibility(config,bad):
    e,c,r,m,_=config;caps=e['transport'].caps
    named=lambda name:next(cap for cap in caps['capabilities'] if cap['id']==name)
    if bad=='resolved':caps['capabilities'].remove(named('resolved_configuration'))
    elif bad=='criteria_free':caps['capabilities'].remove(named('criteria_free_configuration'))
    elif bad=='criteria_free_unsupported':named('criteria_free_configuration')['supported']=False
    elif bad=='quantities':caps['schema_versions'].remove('4')
    else:caps['contract_versions'].remove('1.3')
    with pytest.raises(DomainError,match='unsupported_capability'):preview(config)
    assert not compatibility_calls(e)
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
    p=response.json()['data'];validate('ConfigurationPreview8',p)
    response=e['client'].post(path,json=body(config,p))
    assert response.status_code==201,response.text
    saved=response.json()['data'];validate('FrozenConfiguration9',saved)
    assert canonical(saved['model_snapshot'])==before


def test_http_unresolved_preview_error_and_no_save(config):
    e,c,r,m,_=config;m['definitions'][0]['ports'][1]['units']=dict(kind='unspecified');signed(m)
    path='/api/1/studies/'+e['sid']+'/configurations'
    for suffix,payload in [('/preview',r),('',body(config,dict(candidate_digest='0'*64)))]:
        response=e['client'].post(path+suffix,json=payload)
        assert response.status_code==422,response.text
        assert response.json()['error']['fields'][0]['code']=='unit_unspecified'
    assert counts(e)==(0,0,0)


@pytest.mark.parametrize('legacy',['3','4'])
def test_configuration_requests_with_criteria_are_refused_without_allocation(config,legacy):
    e,c,r,m,_=config;path='/api/1/studies/'+e['sid']+'/configurations'
    old=dict(deepcopy(r),schema_version=legacy,criteria=[])
    if legacy=='4':old['approach_selection']=None
    validate('ConfigurationRequest'+legacy,old)
    commit=dict(command_id=uid(),configuration_id=None,expected_revision=None,configuration=old,expected_preview_digest='0'*64)
    for suffix,payload in [('/preview',old),('',commit)]:
        response=e['client'].post(path+suffix,json=payload)
        assert response.status_code==422 and response.json()['error']['code']=='unsupported_record_version',response.text
    for call,payload in [(c.preview,old),(c.commit,commit)]:
        with pytest.raises(DomainError) as caught:call(e['actor'],e['sid'],payload)
        assert (caught.value.code,caught.value.status)==('unsupported_record_version',422)
    # Version 6 has no criteria or approach selection fields to carry.
    for extra in [dict(criteria=[]),dict(approach_selection=None)]:
        response=e['client'].post(path+'/preview',json=dict(r,**extra))
        assert response.status_code==400 and response.json()['error']['code']=='invalid_request',response.text
    assert not compatibility_calls(e)
    assert counts(e)==(0,0,0)


def test_retained_model4_configuration4_reads_unchanged(config):
    e,c,r,m,_=config;saved=c.commit(e['actor'],e['sid'],body(config))
    configuration=dict(saved['configuration'],configuration_id=uid(),configuration_revision_id=uid())
    retained=dict(schema_version='8',configuration=retained4(configuration),model_snapshot=deepcopy(saved['model_snapshot']),
        study_revision=saved['study_revision'],approach_closure=None)
    validate('FrozenConfiguration8',retained)
    revision_id=retained['configuration']['configuration_revision_id']
    with e['store'].connection(write=True) as db:
        db.execute('INSERT INTO configurations VALUES(?,?,?,?)',(revision_id,retained['configuration']['configuration_id'],e['sid'],json.dumps(retained)))
    assert c.read(e['actor'],e['sid'],revision_id)==retained
    response=e['client'].get('/api/1/studies/'+e['sid']+'/configurations/'+revision_id)
    assert response.status_code==200 and response.json()['data']==retained,response.text


@pytest.mark.parametrize('bad',[False,True])
def test_approach_data_only_unspecified_model_allowed_but_configured_closure_resolved(config,bad):
    from hyprn_mvp_app.approach_closure import build_closure, validate_closure
    e,c,r,m,record=config;retained_versions(m)
    frozen=c.commit(e['actor'],e['sid'],body(config));current=frozen['configuration'];saved=retained4(current)
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
    rehash(version)
    # An approach closure never cites a criteria-free configuration.
    with pytest.raises(ValueError):
        build_closure(version,dict(approach_versions=[],models=[m,explanatory],configurations=[current],run_contexts=[],evidence=[record]),study_id=e['sid'])
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
    original=retained4(original);h['configuration']=original
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
    copied=retained4(copied)
    run=sample(D['ApproachRunContext1']);run.update(run_id=rid,study_id=e['sid'],configuration_revision_id=original['configuration_revision_id'],configuration_digest=original['digest'],model_revision_id=source['model_revision_id'],model_digest=source['digest'],context=original['context_snapshot'],results=result)
    run['association']['store_uuid']=uid()
    run['request'].update(run_id=rid,scope=e['sid'],bundle_digest=result['bundle_digest'])
    rehash(run)
    version=sample(D['ApproachVersion1']);version['study_id']=e['sid']
    version['content']['basis_refs']=[dict(kind='configuration',configuration_revision_id=copied['configuration_revision_id'],reason='Result reuse',relation='context')]
    rehash(version)
    resolution=dict(approach_versions=[],models=[m,source],configurations=[original,copied],run_contexts=[run],evidence=[record])
    if bad:
        with pytest.raises(ValueError):build_closure(version,resolution,study_id=e['sid'])
    else:assert build_closure(version,resolution,study_id=e['sid'])['configurations']
