"""Config4 application authority with an explicit private transport, no native run."""
from copy import deepcopy
import json
import pytest
from test_assumption_configuration import env, config, preview, body, counts, evidence, sample, D
from hyprn_mvp_app.approach import Approaches
from hyprn_mvp_app.modeling import validate
from hyprn_mvp_app.store import DomainError, digest, uid, canonical
from hyprn_mvp_app.scientific_configuration import project_scientific_configuration as project

def pin(config, *, linked=True, bound_case=True, extra_evidence=False, descriptive=False):
    e,c,r,m,record=config
    service=Approaches(e['store'],e['coord']);content=sample(D['ApproachContent1'])
    binding=dict(binding_id=uid(),model_id=m['model_id'],model_revision_id=m['model_revision_id'])
    step=sample(D['ApproachStep1'])
    if linked:step.update(implementation_state='linked',remaining_work='',implementation_refs=[dict(kind='model',binding_id=binding['binding_id'])])
    content['model_bindings']=[binding] if linked else [];content['steps']=[step]
    case=sample(D['ApproachCase1']);case['binding_id']=binding['binding_id'] if bound_case and linked else None
    content['cases']=[case]
    if extra_evidence:
        extra=evidence(e,title='Approach-only basis')
        step['evidence_links']=[dict(evidence_version_id=extra['evidence_version_id'],relation='context')]
    if descriptive:content.update(schema_version='2',original_question=None,elaboration=None,limit_items=[])
    request=dict(schema_version='2' if descriptive else '1',expected_revision=None,content=content)
    p=service.preview(e['actor'],e['sid'],request)
    d=service.save_draft(e['actor'],e['sid'],dict(request,command_id=uid(),expected_preview_digest=p['preview_digest']))
    request['expected_revision']=d['revision'];p=service.preview(e['actor'],e['sid'],request)
    saved=service.save_version(e['actor'],e['sid'],dict(schema_version='1',command_id=uid(),expected_revision=d['revision'],expected_preview_digest=p['preview_digest']))['saved']
    r.update(schema_version='4',approach_selection=dict(approach_version_id=saved['version']['approach_version_id'],case_id=case['case_id']))
    return saved,case,service

def test_null_pin_private_projection_and_frozen_envelope(config):
    e,c,r,m,_=config;old=preview(config)
    r.update(schema_version='4',approach_selection=None)
    p=preview(config);assert p['approach_closure'] is None and p['resolved_candidate']['approach_binding'] is None
    assert canonical(project(p['resolved_candidate']))==canonical(project(old['resolved_candidate']))
    saved=c.commit(e['actor'],e['sid'],body(config,p));validate('FrozenConfiguration4',saved)
    assert saved['approach_closure'] is None
    assert c.commit(e['actor'],e['sid'],body(config,p) | {'configuration_id':None})['configuration']['schema_version']=='4'

@pytest.mark.parametrize('case_pin',[True,False])
def test_exact_pin_separate_closure_and_cold_replay(config,case_pin):
    e,c,r,m,record=config;old=preview(config)
    saved,case,service=pin(config,extra_evidence=True)
    if not case_pin:r['approach_selection']['case_id']=None
    p=preview(config);binding=p['resolved_candidate']['approach_binding']
    assert binding==dict(approach_id=saved['version']['approach_id'],approach_version_id=saved['version']['approach_version_id'],approach_digest=saved['version']['digest'],closure_digest=saved['closure']['digest'],case_id=case['case_id'] if case_pin else None)
    assert p['approach_closure']==saved['closure']
    assert p['resolved_candidate']['evidence_snapshots']==old['resolved_candidate']['evidence_snapshots']
    assert canonical(project(p['resolved_candidate']))==canonical(project(old['resolved_candidate']))
    request=body(config,p);frozen=c.commit(e['actor'],e['sid'],request)
    validate('FrozenConfiguration4',frozen)
    # Later draft edits and missing remote service cannot rewrite the frozen basis.
    state=service.state(e['actor'],e['sid']);draft=state['draft'];draft['content']['question']='Later question'
    q=dict(schema_version='1',expected_revision=draft['revision'],content=draft['content'])
    q['expected_preview_digest']=service.preview(e['actor'],e['sid'],q)['preview_digest']
    service.save_draft(e['actor'],e['sid'],dict(q,command_id=uid()))
    e['coord'].model.transport=lambda *a: (_ for _ in ()).throw(AssertionError('cold replay must not call model'))
    assert c.commit(e['actor'],e['sid'],request)==frozen
    assert c.read(e['actor'],e['sid'],frozen['configuration']['configuration_revision_id'])==frozen

@pytest.mark.parametrize('bad',['missing','foreign','case','unbound_case','unlinked','model_revision','model_bytes','closure_digest','version_digest'])
def test_invalid_pin_fails_without_configuration_allocation(config,bad):
    e,c,r,m,_=config
    saved,case,_=pin(config,linked=bad!='unlinked',bound_case=bad!='unbound_case')
    version=saved['version']['approach_version_id']
    if bad=='missing':r['approach_selection']['approach_version_id']=uid()
    elif bad=='case':r['approach_selection']['case_id']=uid()
    elif bad=='model_revision':
        m['model_revision_id']=uid();m['digest']=digest({k:v for k,v in m.items() if k!='digest'})
        e['transport'].revisions[m['model_revision_id']]=m;r['model_revision_id']=m['model_revision_id']
    elif bad=='model_bytes':m['name']='Changed immutable bytes';m['digest']=digest({k:v for k,v in m.items() if k!='digest'})
    elif bad=='foreign':
        sid=e['store'].create_study(e['actor'],uid(),'Other study')['study_id']
        with e['store'].connection(write=True) as db:db.execute('INSERT INTO model_associations VALUES(?,?,?)',(sid,e['mid'],uid()))
        e['sid']=sid;r['study_id']=sid
        r['context_source']['expected_study_revision']=e['store'].study(e['actor'],sid)['revision']
        r['assumptions']=[];r['general_context_evidence_version_ids']=[];m['assumptions']=[]
        m['digest']=digest({k:v for k,v in m.items() if k!='digest'})
    elif bad in ('closure_digest','version_digest'):
        with e['store'].connection(write=True) as db:
            db.execute('DROP TRIGGER immutable_approach_version_update')
            saved['closure' if bad=='closure_digest' else 'version']['digest']='a'*64
            db.execute('UPDATE approach_versions SET payload=? WHERE approach_version_id=?',(json.dumps(saved),version))
    for action in ('preview','commit'):
        with pytest.raises(DomainError):
            if action=='preview':preview(config)
            else:c.commit(e['actor'],e['sid'],body(config,{'candidate_digest':'0'*64}))
        assert counts(e)==(0,0,0)

@pytest.mark.parametrize('race',['approach','membership','association','evidence'])
def test_commit_rechecks_all_local_authority(config,race):
    e,c,r,m,record=config;pin(config);request=body(config);original=e['store'].command
    def command(*args,**kwargs):
        with e['store'].connection(write=True) as db:
            if race=='approach':
                db.execute('DROP TRIGGER immutable_approach_version_update')
                db.execute("UPDATE approach_versions SET payload=json_set(payload,'$.closure.digest',?)",('0'*64,))
            elif race=='membership':db.execute('DELETE FROM memberships')
            elif race=='association':db.execute('DELETE FROM model_associations')
            else:
                db.execute('DROP TRIGGER immutable_evidence_update');db.execute("UPDATE evidence SET payload=json_set(payload,'$.title','Changed')")
        return original(*args,**kwargs)
    e['store'].command=command
    with pytest.raises(DomainError):c.commit(e['actor'],e['sid'],request)
    assert counts(e)==(0,0,0)

def test_stale_preview_selection_mutation_and_current_write_permission(config):
    e,c,r,m,_=config;pin(config);request=body(config)
    changed=deepcopy(request);changed['configuration']['approach_selection']=None
    with pytest.raises(DomainError,match='reference_conflict'):c.commit(e['actor'],e['sid'],changed)
    frozen=c.commit(e['actor'],e['sid'],request)
    with e['store'].connection(write=True) as db:db.execute('DELETE FROM memberships')
    with pytest.raises(DomainError):c.commit(e['actor'],e['sid'],request)

def test_http_accepts_request4_and_returns_closed_preview_and_save(config):
    e,c,r,m,_=config;pin(config);client=e['client'];path='/api/1/studies/'+e['sid']+'/configurations'
    p=client.post(path+'/preview',json=r)
    assert p.status_code==200,p.text
    validate('ConfigurationPreview4',p.json()['data'])
    response=client.post(path,json=body(config,p.json()['data']))
    assert response.status_code==201,response.text
    validate('FrozenConfiguration4',response.json()['data'])


@pytest.mark.parametrize('version,linked',[('2',True),('4',False),('4',True)])
def test_polish_configuration_exact_frozen7_and_cold_replay(config,version,linked):
    e,c,r,m,_=config
    if version=='4':
        m['schema_version']='4';m['required_capabilities']=['flat_explicit_scalar','quantity_definitions/1']
        for d in m['definitions']:d['quantity_definitions']=[]
        m['digest']=digest({k:v for k,v in m.items() if k!='digest'})
        caps=e['transport'].caps;caps['schema_versions'].append('4')
        caps['capabilities'].append(dict(caps['capabilities'][0],id='quantity_definitions',version='1',supported=True))
    r.update(schema_version='4',approach_selection=None)
    if linked:pin(config,descriptive=True)
    p=preview(config);request=body(config,p);frozen=c.commit(e['actor'],e['sid'],request)
    assert frozen['schema_version']=='7' and frozen['configuration']['schema_version']=='4'
    assert project(frozen['configuration'])['schema_version']=='3'
    e['coord'].model.transport=lambda *a:pytest.fail('Replay must use exact retained bytes')
    assert c.commit(e['actor'],e['sid'],request)==frozen
    assert c.read(e['actor'],e['sid'],frozen['configuration']['configuration_revision_id'])==frozen


def test_polish_http_preview_commit_mixed_list_and_receipt(config):
    from jsonschema import Draft202012Validator,FormatChecker
    from pathlib import Path
    e,c,r,m,_=config;client=e['client'];path='/api/1/studies/'+e['sid']+'/configurations'
    api=json.loads((Path(__file__).resolve().parents[2]/'contracts/hyprn-mvp.openapi.yaml').read_text())
    def check(name,value):Draft202012Validator({**api,'$ref':'#/components/schemas/'+name},format_checker=FormatChecker()).validate(value)
    r.update(schema_version='4',approach_selection=None)
    old=client.post(path+'/preview',json=r);assert old.status_code==200,old.text
    check('PublicConfigurationPreview',old.json()['data'])
    saved_old=client.post(path,json=body(config,old.json()['data']));assert saved_old.status_code==201,saved_old.text
    pin(config,descriptive=True)
    previewed=client.post(path+'/preview',json=r);assert previewed.status_code==200,previewed.text
    assert previewed.json()['data']['schema_version']=='6';check('PublicConfigurationPreview',previewed.json()['data'])
    request=body(config,previewed.json()['data']);saved=client.post(path,json=request)
    assert saved.status_code==201,saved.text
    check('FrozenConfigurationRead7',saved.json()['data'])
    assert client.post(path,json=request).json()['data']==saved.json()['data']
    revision=saved.json()['data']['configuration']['configuration_revision_id']
    assert client.get(path+'/'+revision).json()['data']==saved.json()['data']
    rows=client.get(path).json()['data'];assert len(rows)==2
    for row in rows:check('FrozenConfigurationRead7',row)
    receipt=client.get('/api/1/studies/'+e['sid']+'/commands/'+request['command_id']+'?category=configuration')
    assert receipt.status_code==200,receipt.text
    check('PublicReceipt',receipt.json()['data'])
