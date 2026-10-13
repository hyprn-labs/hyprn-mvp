"""Real Store/Coordinator with data-only private transport; no native execution.

Run-basis tests reuse existing verified retained bundle fixtures. They prove
application authority checks, not a new native process or live bridge journey.
"""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import base64
import json
import sqlite3
import pytest
from checks import PROJECTION_SCOPE
import scoped_fixture as guard
from hyprn_mvp_app.store import Store, DomainError, uid, digest, canonical
from hyprn_mvp_app.modeling import Coordinator, ModelingClient, validate
from hyprn_mvp_app.approach import Approaches, saved_version
from test_approach_closure import sample, D, model, signed, config
import test_result_bindings

@pytest.fixture
def run_env(tmp_path, request, monkeypatch):
    # The older captured producer fixture omitted its model root/global port
    # inventory. Build a complete synthetic retained snapshot and reseal all
    # envelopes; generated files stay inert. This is application proof only.
    captured = test_result_bindings.fixture
    def complete(*args, **kwargs):
        case = captured(*args, **kwargs)
        m = case['frozen']['model_snapshot']
        m['root_instance_id'] = m['instances'][0]['instance_id']
        m['ports'] = [deepcopy(p) for d in m['definitions'] for p in d['ports']]
        signed(m)
        raw = canonical(m); case['files']['model.json'] = raw
        prepared = case['prepared']; prepared['model_digest'] = m['digest']
        package = prepared['model_package_manifest']; package['revisions'] = [deepcopy(m)]
        for descriptor in prepared['files'] + package['files']:
            if descriptor['role'] == 'model':
                descriptor.update(size=len(raw),sha256=__import__('hashlib').sha256(raw).hexdigest())
        signed(package)
        return case
    monkeypatch.setattr(test_result_bindings,'fixture',complete)
    return test_result_bindings.env.__wrapped__(tmp_path,request)

@pytest.fixture
def env(tmp_path):
    assert guard.no_symlinks(tmp_path).is_relative_to(PROJECTION_SCOPE.root)
    store=Store(tmp_path/'approach.sqlite');actor=uid();sid=store.create_study(actor,uid(),'Study')['study_id']
    models={};calls=[];hooks=[]
    def transport(method,path,raw,headers):
        assert method=='GET' and '/revisions/' in path
        with sqlite3.connect(store.path,timeout=0) as db:db.execute('BEGIN IMMEDIATE');db.rollback()
        calls.append(path)
        for hook in hooks:hook()
        mid,revision=path.split('/models/')[1].split('/revisions/')
        if (mid,revision) not in models:return 404,{'error':{}}
        return 200,dict(schema_version='1',request_id=uid(),data=deepcopy(models[mid,revision]))
    coord=Coordinator(store,ModelingClient('http://private.invalid/modeling/1',b't'*32,transport=transport))
    return dict(store=store,actor=actor,sid=sid,models=models,calls=calls,hooks=hooks,service=Approaches(store,coord),coord=coord)

def content():return sample(D['ApproachContent1'])
def req(c=None,expected=None):return dict(schema_version='1',expected_revision=expected,content=c or content())
def preview(e,b):return e['service'].preview(e['actor'],e['sid'],b)
def draft(e,b=None):
    b=b or req();p=preview(e,b)
    return e['service'].save_draft(e['actor'],e['sid'],dict(b,command_id=uid(),expected_preview_digest=p['preview_digest']))
def save(e,d):
    p=preview(e,req(d['content'],d['revision']))
    b=dict(schema_version='1',command_id=uid(),expected_revision=d['revision'],expected_preview_digest=p['preview_digest'])
    return e['service'].save_version(e['actor'],e['sid'],b),b
def link(e,c=None):
    m=model();c=c or content()
    with e['store'].connection(write=True) as db:db.execute('INSERT INTO model_associations VALUES(?,?,?)',(e['sid'],m['model_id'],uid()))
    e['models'][m['model_id'],m['model_revision_id']]=m
    b=dict(binding_id=uid(),model_id=m['model_id'],model_revision_id=m['model_revision_id'])
    step=sample(D['ApproachStep1']);step.update(implementation_state='linked',remaining_work='',implementation_refs=[dict(kind='model',binding_id=b['binding_id'])])
    c['model_bindings']=[b];c['steps']=[step]
    return c,m,b,step
def rows(e):
    with e['store'].connection() as db:return {t:[tuple(r) for r in db.execute('SELECT * FROM '+t)] for t in ('approach_drafts','approach_versions','receipts')}

def test_empty_get_and_preview_do_not_create_rows(env):
    before=rows(env)
    assert env['service'].state(env['actor'],env['sid'])==dict(draft=None,latest_version=None)
    p=preview(env,req());validate('ApproachPreview1',p)
    assert p['issues']==[] and p['coverage']==dict(proposed=0,partial=0,linked=0)
    assert rows(env)==before


@pytest.mark.parametrize('retained_old',[False,True])
def test_source_revision_with_stable_ports_links_exact_definition_versions(env,retained_old):
    c,m,b,step=link(env)
    old=deepcopy(m['definitions'][0])
    old['kind']='explicit_component'
    p=sample(D['Port']);p.update(definition_version_id=old['definition_version_id'])
    old['ports']=[p]
    new=deepcopy(old);new['definition_version_id']=uid()
    new['ports'][0]['definition_version_id']=new['definition_version_id']
    m['definitions']=[old,new];m['ports']=[p,new['ports'][0]]
    m['instances'][0]['definition_version_id']=new['definition_version_id']
    if not retained_old:
        m['definitions']=[new];m['ports']=[new['ports'][0]]
    step['implementation_refs']=[dict(kind='port',binding_id=b['binding_id'],
        instance_id=m['instances'][0]['instance_id'],port_id=p['port_id'])]
    signed(m)
    before=deepcopy(m)
    assert preview(env,req(c))['issues']==[]
    saved,_=save(env,draft(env,req(c)))
    assert saved['saved']['closure']['models']==[before]
    assert m==before
    # Exercise the independent admission checks without importing candidate code.
    from hyprn_mvp_integration.worker import ApproachClosure
    admission=ApproachClosure.__new__(ApproachClosure)
    admission.model(m)
    admission.model_port(m,step['implementation_refs'][0])
    duplicate=deepcopy(m);duplicate['ports'].append(deepcopy(new['ports'][0]));signed(duplicate)
    env['models'][m['model_id'],m['model_revision_id']]=duplicate
    assert preview(env,req(c,saved['draft_revision']))['issues']
    with pytest.raises(ValueError):admission.model(duplicate)
    duplicate=deepcopy(m);duplicate['definitions'][-1]['ports'].append(deepcopy(new['ports'][0]));signed(duplicate)
    env['models'][m['model_id'],m['model_revision_id']]=duplicate
    assert preview(env,req(c,saved['draft_revision']))['issues']
    with pytest.raises(ValueError):admission.model(duplicate)

def test_full_lifecycle_restore_retains_exact_version_and_new_draft_tokens(env):
    d=draft(env);validate('ApproachDraft1',d)
    result,_=save(env,d);validate('ApproachVersionSaved1',result)
    saved=result['saved'];v=saved['version'];assert v['content']==d['content']
    assert saved['closure']['root_approach_digest']==v['digest']
    assert env['service'].read(env['actor'],env['sid'],v['approach_version_id'])==saved
    changed=deepcopy(d['content']);changed['question']='New question'
    nextdraft=draft(env,req(changed,result['draft_revision']))
    body=dict(schema_version='1',command_id=uid(),expected_revision=nextdraft['revision'],approach_version_id=v['approach_version_id'])
    restored=env['service'].restore(env['actor'],env['sid'],body)
    assert restored['content']==d['content'] and restored['revision']!=nextdraft['revision']
    assert env['service'].restore(env['actor'],env['sid'],body)==restored
    assert env['service'].read(env['actor'],env['sid'],v['approach_version_id'])==saved
    assert env['service'].state(env['actor'],env['sid'])['latest_version']['version_number']==1

def test_first_cas_stale_preview_stale_draft_and_command_conflict(env):
    body=req();p=preview(env,body);body.update(command_id=uid(),expected_preview_digest=p['preview_digest'])
    d=env['service'].save_draft(env['actor'],env['sid'],body)
    assert env['service'].save_draft(env['actor'],env['sid'],body)==d
    changed=deepcopy(body);changed['content']['question']='Changed payload'
    with pytest.raises(DomainError,match='command_payload_conflict'):env['service'].save_draft(env['actor'],env['sid'],changed)
    with pytest.raises(DomainError,match='stale_revision'):env['service'].save_draft(env['actor'],env['sid'],body | {'command_id':uid()})
    stale=req(d['content'],d['revision']) | dict(command_id=uid(),expected_preview_digest='a'*64)
    with pytest.raises(DomainError):env['service'].save_draft(env['actor'],env['sid'],stale)
    assert env['service'].state(env['actor'],env['sid'])['draft']==d

def test_changed_content_requires_a_new_preview(env):
    b=req();p=preview(env,b);b['content']['question']='Unreviewed'
    with pytest.raises(DomainError):env['service'].save_draft(env['actor'],env['sid'],b | dict(command_id=uid(),expected_preview_digest=p['preview_digest']))
    assert rows(env)['approach_drafts']==[]

def test_exact_model_outage_read_and_no_candidate_import(env,tmp_path):
    c,m,_,_=link(env);canary=tmp_path/'candidate-ran';raw=(f'open({str(canary)!r},"w").write("bad")').encode()
    h=__import__('hashlib').sha256(raw).hexdigest();m['source_files']=[dict(encoding='base64',media_type='text/x-python',bytes=base64.b64encode(raw).decode(),sha256=h)];m['definitions'][0]['source_refs']=[h];signed(m)
    result,body=save(env,draft(env,req(c)));saved=result['saved'];env['models'].clear()
    assert env['service'].read(env['actor'],env['sid'],saved['version']['approach_version_id'])==saved
    assert env['service'].save_version(env['actor'],env['sid'],body)==result
    assert saved['closure']['models']==[m] and not canary.exists()

@pytest.mark.parametrize('kind',['instance','port','connection','assumption'])
def test_claimed_missing_membership_blocks_write_without_fabrication(env,kind):
    c,m,b,s=link(env)
    if kind=='assumption':s['assumption_refs']=[dict(kind='model',binding_id=b['binding_id'],assumption_id=uid(),origin=None)]
    else:
        r=dict(kind=kind,binding_id=b['binding_id'])
        if kind in ('instance','port'):r['instance_id']=uid()
        r['port_id' if kind=='port' else 'connection_id' if kind=='connection' else 'instance_id']=uid()
        s['implementation_refs']=[r]
    p=preview(env,req(c));assert p['issues']
    field='assumption_refs' if kind=='assumption' else 'implementation_refs'
    identity=s[field][0][{'port':'instance_id','instance':'instance_id','connection':'connection_id','assumption':'assumption_id'}[kind]]
    assert p['issues'][0]['path']==f'/content/steps/0/{field}/0'
    assert identity in p['issues'][0]['message']
    with pytest.raises(DomainError):env['service'].save_draft(env['actor'],env['sid'],req(c) | dict(command_id=uid(),expected_preview_digest=p['preview_digest']))
    assert rows(env)['approach_drafts']==[]

def test_proposals_and_partial_coverage_are_honest(env):
    c,m,b,s=link(env);s.update(implementation_state='partial',remaining_work='Add pressure balance')
    proposed=sample(D['ApproachStep1']);proposed['title']='Intended calibration';c['steps'].append(proposed)
    p=preview(env,req(c));assert p['coverage']==dict(proposed=1,partial=1,linked=0)
    assert save(env,draft(env,req(c)))[0]['saved']['version']['content']==c

@pytest.mark.parametrize('phase',['read','preview','write','replay'])
def test_membership_required_for_every_operation(env,phase):
    b=req();p=preview(env,b);write=b | dict(command_id=uid(),expected_preview_digest=p['preview_digest'])
    if phase=='replay':env['service'].save_draft(env['actor'],env['sid'],write)
    with env['store'].connection(write=True) as db:db.execute('DELETE FROM memberships')
    fn={'read':lambda:env['service'].state(env['actor'],env['sid']),'preview':lambda:preview(env,b),'write':lambda:env['service'].save_draft(env['actor'],env['sid'],write),'replay':lambda:env['service'].save_draft(env['actor'],env['sid'],write)}[phase]
    with pytest.raises(DomainError) as err:fn()
    assert err.value.status==404

def test_revoke_between_remote_resolution_and_transaction(env):
    c,_,_,_=link(env);p=preview(env,req(c))
    def revoke():
        with env['store'].connection(write=True) as db:db.execute('DELETE FROM memberships')
    env['hooks'].append(revoke)
    with pytest.raises(DomainError):env['service'].save_draft(env['actor'],env['sid'],req(c) | dict(command_id=uid(),expected_preview_digest=p['preview_digest']))
    assert rows(env)['approach_drafts']==[]

def test_foreign_reference_never_requests_private_model_or_leaks_metadata(env):
    c,m,_,_=link(env);before=len(env['calls'])
    with env['store'].connection(write=True) as db:db.execute('DELETE FROM model_associations')
    with pytest.raises(DomainError) as err:preview(env,req(c))
    assert err.value.status==404 and len(env['calls'])==before
    assert m['model_id'] not in str(err.value.data())

def test_concurrent_version_saves_allocate_one_ordinal_and_stable_replay(env):
    d=draft(env);p=preview(env,req(d['content'],d['revision']))
    bodies=[dict(schema_version='1',command_id=uid(),expected_revision=d['revision'],expected_preview_digest=p['preview_digest']) for _ in range(2)]
    def write(b):
        try:return env['service'].save_version(env['actor'],env['sid'],b)
        except DomainError as e:return e.code
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(write,bodies))
    assert len([x for x in results if isinstance(x,dict)])==1 and 'stale_revision' in results
    assert len(rows(env)['approach_versions'])==1
    i=next(i for i,x in enumerate(results) if isinstance(x,dict))
    assert write(bodies[i])==results[i]

def test_saved_proposal_handoff_requires_exact_prior_origin(env):
    c=content();a=sample(D['ApproachAssumption1']);a['role']='proposed_model_condition';c['assumptions']=[a]
    old,_=save(env,draft(env,req(c)));v=old['saved']['version']
    c,m,b,s=link(env);ma=dict(assumption_id=uid(),owner=dict(kind='model'),statement='Revised physical condition',evidence_links=[]);m['assumptions']=[ma];signed(m)
    origin=dict(approach_version_id=v['approach_version_id'],assumption_id=a['assumption_id'],digest=v['digest'])
    s['assumption_refs']=[dict(kind='model',binding_id=b['binding_id'],assumption_id=ma['assumption_id'],origin=origin)]
    d=draft(env,req(c,old['draft_revision']));new,_=save(env,d)
    assert len(new['saved']['closure']['approach_versions'])==2
    c['assumptions']=[a];assert preview(env,req(c,new['draft_revision']))['issues']
    c['assumptions']=[];origin['assumption_id']=uid();assert preview(env,req(c,new['draft_revision']))['issues']

def test_versions_pagination_is_stable_across_later_saves(env):
    d=draft(env);saved=[]
    for _ in range(3):
        result,_=save(env,d);saved.append(result['saved']['version']);d=env['service'].state(env['actor'],env['sid'])['draft']
    first=env['service'].versions(env['actor'],env['sid'],dict(limit=2,cursor=None))
    assert [v['version_number'] for v in first['items']]==[3,2]
    save(env,d)
    page=env['service'].versions(env['actor'],env['sid'],dict(limit=2,cursor=first['next_cursor']))
    assert [v['version_number'] for v in page['items']]==[1] and page['next_cursor'] is None

@pytest.mark.parametrize('tamper',['association','request','bundle','unverified','pending'])
def test_run_basis_requires_authoritative_retained_witness(run_env,tamper):
    e=run_env;service=Approaches(e['store'],None);c=content();c['basis_refs']=[dict(kind='run',run_id=e['rid'],reason='Prior observation',relation='context')]
    with e['store'].connection(write=True) as db:
        row=db.execute('SELECT payload FROM outbox WHERE run_id=?',(e['rid'],)).fetchone();payload=json.loads(row[0])
        if tamper=='association':payload['history']['association']['process_uuid']=uid();signed(payload['history'])
        if tamper=='request':payload['history']['request']['payload_digest']='a'*64;signed(payload['history'])
        if tamper=='bundle':payload['bundle']['files']['configuration.json']=base64.b64encode(b'{}').decode()
        if tamper=='unverified':payload['history']['bundle_verified']=False;signed(payload['history'])
        db.execute('UPDATE outbox SET state=?,payload=? WHERE run_id=?',('uncertain' if tamper=='pending' else 'recorded',json.dumps(payload),e['rid']))
    with pytest.raises(DomainError):service.preview(e['actor'],e['sid'],req(c))

def test_failed_basis_retains_null_results_without_becoming_numeric_source(run_env):
    e=run_env;service=Approaches(e['store'],None);c=content();c['basis_refs']=[dict(kind='run',run_id=e['rid'],reason='Failed experiment informs method',relation='challenges')]
    with e['store'].connection(write=True) as db:
        p=json.loads(db.execute('SELECT payload FROM outbox WHERE run_id=?',(e['rid'],)).fetchone()[0]);p['history']['results']=None;p['history']['errors']=[dict(code='missing_results',partial=True)];signed(p['history']);db.execute('UPDATE outbox SET payload=? WHERE run_id=?',(json.dumps(p),e['rid']))
    p=service.preview(e['actor'],e['sid'],req(c))
    assert p['issues']==[]
    assert p['resolved']['run_contexts'][0]['results'] is None
    assert p['resolved']['run_contexts'][0]['association']['process_uuid']

def test_derived_usage_reads_actual_pins_and_preserves_saved_closure(env):
    c,m,_,_=link(env);result,_=save(env,draft(env,req(c)));saved=result['saved'];v=saved['version'];revision=config(m);revision.update(study_id=env['sid'],schema_version='4',approach_binding=dict(approach_id=v['approach_id'],approach_version_id=v['approach_version_id'],approach_digest=v['digest'],closure_digest=saved['closure']['digest'],case_id=None));signed(revision)
    frozen=dict(schema_version='4',configuration=revision,model_snapshot=m,study_revision=uid(),approach_closure=saved['closure'])
    with env['store'].connection(write=True) as db:db.execute('INSERT INTO configurations VALUES(?,?,?,?)',(revision['configuration_revision_id'],revision['configuration_id'],env['sid'],json.dumps(frozen)))
    page=env['service'].usage(env['actor'],env['sid'],v['approach_version_id'],dict(limit=20,cursor=None,case_id=None));validate('ApproachUsagePage1',page)
    assert page['items']==[dict(kind='configuration',configuration_revision_id=revision['configuration_revision_id'],case_id=None)]
    assert env['service'].read(env['actor'],env['sid'],v['approach_version_id'])==saved


def test_exact_evidence_snapshot_and_foreign_evidence_are_authorized(env):
    e=sample(D['EvidenceRecord3']);e.update(study_id=env['sid'],title='Exact report',resource_scope=dict(scope_version='1',kind='study',study_id=env['sid']))
    with env['store'].connection(write=True) as db:db.execute('INSERT INTO evidence VALUES(?,?,?,?)',(e['evidence_version_id'],e['evidence_id'],env['sid'],json.dumps(e)))
    c=content();a=sample(D['ApproachAssumption1']);a['evidence_links']=[dict(evidence_version_id=e['evidence_version_id'],relation='challenges')];c['assumptions']=[a]
    saved,_=save(env,draft(env,req(c)));assert saved['saved']['closure']['evidence']==[e]
    foreign=env['store'].create_study(uid(),uid(),'Private study')['study_id'];f=deepcopy(e);f.update(evidence_id=uid(),evidence_version_id=uid(),study_id=foreign,title='SECRET')
    with env['store'].connection(write=True) as db:db.execute('INSERT INTO evidence VALUES(?,?,?,?)',(f['evidence_version_id'],f['evidence_id'],foreign,json.dumps(f)))
    a['evidence_links'][0]['evidence_version_id']=f['evidence_version_id']
    with pytest.raises(DomainError) as err:preview(env,req(c,saved['draft_revision']))
    assert err.value.status==404 and 'SECRET' not in str(err.value.data())

def test_local_pin_changed_before_commit_rolls_back_and_retains_rejection(env,monkeypatch):
    c,m,_,_=link(env);p=preview(env,req(c));body=req(c) | dict(command_id=uid(),expected_preview_digest=p['preview_digest'])
    original=env['store'].command
    def race(*args,**kwargs):
        with env['store'].connection(write=True) as db:db.execute('UPDATE model_associations SET command_id=?',(uid(),))
        return original(*args,**kwargs)
    monkeypatch.setattr(env['store'],'command',race)
    with pytest.raises(DomainError,match='reference_conflict'):env['service'].save_draft(env['actor'],env['sid'],body)
    assert rows(env)['approach_drafts']==[]
    r=env['service'].receipt(env['actor'],env['sid'],'approach_draft',body['command_id']);assert r['state']=='rejected' and r['result'] is None
    monkeypatch.setattr(env['store'],'command',original)
    with pytest.raises(DomainError,match='reference_conflict'):env['service'].save_draft(env['actor'],env['sid'],body)

def test_same_command_race_returns_original_after_preflight_stales(env,monkeypatch):
    d=draft(env);p=preview(env,req(d['content'],d['revision']));body=dict(schema_version='1',command_id=uid(),expected_revision=d['revision'],expected_preview_digest=p['preview_digest'])
    original=env['store'].replay;calls=0;committed=[]
    def race(*args,**kwargs):
        nonlocal calls
        calls+=1
        if calls==1:
            monkeypatch.setattr(env['store'],'replay',original)
            committed.append(env['service'].save_version(env['actor'],env['sid'],body))
            return None
        return original(*args,**kwargs)
    monkeypatch.setattr(env['store'],'replay',race)
    assert env['service'].save_version(env['actor'],env['sid'],body)==committed[0]
    assert len(rows(env)['approach_versions'])==1

def test_original_request_is_frozen_before_private_io(env):
    c,m,_,_=link(env);p=preview(env,req(c));body=req(c) | dict(command_id=uid(),expected_preview_digest=p['preview_digest']);original=deepcopy(body)
    env['hooks'].append(lambda:body['content'].update(question='Unreviewed mutation'))
    d=env['service'].save_draft(env['actor'],env['sid'],body)
    assert d['content']==original['content']
    env['hooks'].clear()
    assert env['service'].save_draft(env['actor'],env['sid'],original)==d

def test_reader_can_read_but_not_write_or_replay(env):
    d=draft(env);result,body=save(env,d)
    with env['store'].connection(write=True) as db:db.execute("UPDATE memberships SET role='reader'")
    assert env['service'].read(env['actor'],env['sid'],result['saved']['version']['approach_version_id'])==result['saved']
    with pytest.raises(DomainError) as err:env['service'].save_version(env['actor'],env['sid'],body)
    assert err.value.status==403

def test_restore_outage_stale_and_foreign_version(env):
    c,_,_,_=link(env);result,_=save(env,draft(env,req(c)));v=result['saved']['version'];env['models'].clear()
    body=dict(schema_version='1',command_id=uid(),expected_revision=result['draft_revision'],approach_version_id=v['approach_version_id'])
    restored=env['service'].restore(env['actor'],env['sid'],body);assert restored['content']==c
    with pytest.raises(DomainError,match='stale_revision'):env['service'].restore(env['actor'],env['sid'],body | {'command_id':uid()})
    other=env['store'].create_study(env['actor'],uid(),'Other')['study_id']
    with pytest.raises(DomainError) as err:env['service'].restore(env['actor'],other,body | {'command_id':uid(),'expected_revision':None})
    assert err.value.status==404

def test_unknown_missing_binding_no_remote_fallback(env):
    c,m,b,s=link(env);del env['models'][m['model_id'],m['model_revision_id']]
    with pytest.raises(DomainError):preview(env,req(c))
    assert len(env['calls'])==1 and rows(env)['approach_drafts']==[]

def test_request_content_byte_limit_is_enforced_before_resolution(env):
    c=content();c['assumptions']=[dict(assumption_id=uid(),statement='é'*4096,role='overall_method',evidence_links=[]) for _ in range(256)]
    with pytest.raises(DomainError) as err:preview(env,req(c))
    assert err.value.code=='limit_exceeded' and env['calls']==[]

def test_usage_pagination_case_filter_and_run_are_real_persisted_links(env):
    c,m,b,_=link(env);case=sample(D['ApproachCase1']);case['binding_id']=b['binding_id'];c['cases']=[case]
    result,_=save(env,draft(env,req(c)));saved=result['saved'];v=saved['version'];r=config(m);r.update(study_id=env['sid'],schema_version='4',approach_binding=dict(approach_id=v['approach_id'],approach_version_id=v['approach_version_id'],approach_digest=v['digest'],closure_digest=saved['closure']['digest'],case_id=case['case_id']));signed(r)
    frozen=dict(schema_version='4',configuration=r,model_snapshot=m,study_revision=uid(),approach_closure=saved['closure']);rid=uid()
    with env['store'].connection(write=True) as db:
        db.execute('INSERT INTO configurations VALUES(?,?,?,?)',(r['configuration_revision_id'],r['configuration_id'],env['sid'],json.dumps(frozen)))
        db.execute('INSERT INTO run_associations VALUES(?,?,?,?,?,?)',(rid,env['sid'],r['configuration_revision_id'],uid(),None,None))
    query=dict(limit=1,cursor=None,case_id=case['case_id']);p=env['service'].usage(env['actor'],env['sid'],v['approach_version_id'],query)
    assert p['items'][0]['kind']=='configuration' and p['next_cursor']
    p=env['service'].usage(env['actor'],env['sid'],v['approach_version_id'],query | {'cursor':p['next_cursor']})
    assert p['items']==[dict(kind='run',run_id=rid,configuration_revision_id=r['configuration_revision_id'],case_id=case['case_id'])] and p['next_cursor'] is None
    with pytest.raises(DomainError):env['service'].usage(env['actor'],env['sid'],v['approach_version_id'],query | {'case_id':uid()})

def test_configuration_basis_keeps_authorized_frozen_model_without_backend(env):
    c,m,_,_=link(env);r=config(m);r['study_id']=env['sid'];signed(r);frozen=dict(schema_version='4',configuration=r,model_snapshot=m,study_revision=uid(),approach_closure=None)
    with env['store'].connection(write=True) as db:db.execute('INSERT INTO configurations VALUES(?,?,?,?)',(r['configuration_revision_id'],r['configuration_id'],env['sid'],json.dumps(frozen)))
    env['models'].clear();c=content();c['basis_refs']=[dict(kind='configuration',configuration_revision_id=r['configuration_revision_id'],reason='Prior calibration',relation='supports')]
    p=preview(env,req(c));assert p['issues']==[] and p['resolved']['configurations']==[r] and env['calls']==[]

def test_saved_read_validates_payload_column_identity_and_digest(env):
    result,_=save(env,draft(env));saved=result['saved'];v=saved['version']
    with env['store'].connection() as db:row=dict(db.execute('SELECT * FROM approach_versions').fetchone())
    row['approach_version_id']=uid()
    with pytest.raises(DomainError):saved_version(row,env['sid'])
    row['approach_version_id']=v['approach_version_id'];bad=deepcopy(saved);bad['version']['content']['question']='Tamper';row['payload']=json.dumps(bad)
    with pytest.raises(DomainError):saved_version(row,env['sid'])


def test_aggregate_closure_limit_is_actionable_and_atomic(env,monkeypatch):
    import hyprn_mvp_app.approach_closure as closure_module
    monkeypatch.setattr(closure_module,'MAX_BYTES',1)
    with pytest.raises(DomainError) as err:preview(env,req())
    assert err.value.code=='limit_exceeded' and err.value.status==413
    assert rows(env)['approach_drafts']==[]


def test_final_envelope_limit_rejects_atomically_with_stable_receipt(env,monkeypatch):
    import hyprn_mvp_app.approach as approach_module
    d=draft(env);p=preview(env,req(d['content'],d['revision']))
    body=dict(schema_version='1',command_id=uid(),expected_revision=d['revision'],expected_preview_digest=p['preview_digest'])
    original=approach_module.build_closure;calls=0
    def limit(*args,**kwargs):
        nonlocal calls
        calls+=1
        if calls==2:raise ValueError('Closure byte limit')
        return original(*args,**kwargs)
    monkeypatch.setattr(approach_module,'build_closure',limit)
    with pytest.raises(DomainError) as err:env['service'].save_version(env['actor'],env['sid'],body)
    assert err.value.code=='limit_exceeded' and rows(env)['approach_versions']==[]
    assert env['service'].state(env['actor'],env['sid'])['draft']==d
    assert env['service'].receipt(env['actor'],env['sid'],'approach_version',body['command_id'])['state']=='rejected'


def polish_content():
    c=content();c.update(schema_version='2',original_question=dict(text='Original wording\r\nverbatim',attribution=dict(kind='unknown',label=None)),elaboration=dict(text='<script>inert supplied explanation</script>',attribution=dict(kind='agent',label='Claimed author')),limit_items=[])
    c['limitations']='Legacy unsplit text.\r\nSecond line.'
    return c

def polish_req(c=None,expected=None):
    return dict(schema_version='2',expected_revision=expected,content=c or polish_content())

def polish_save(e,d):
    p=preview(e,dict(schema_version=d['schema_version'],expected_revision=d['revision'],content=d['content']))
    b=dict(schema_version='1',command_id=uid(),expected_revision=d['revision'],expected_preview_digest=p['preview_digest'])
    return e['service'].save_version(e['actor'],e['sid'],b),b

def polish_evidence(e,c):
    record=sample(D['EvidenceRecord3']);record.update(study_id=e['sid'],resource_scope=dict(scope_version='1',kind='study',study_id=e['sid']))
    with e['store'].connection(write=True) as db:db.execute('INSERT INTO evidence VALUES(?,?,?,?)',(record['evidence_version_id'],record['evidence_id'],e['sid'],json.dumps(record)))
    c['limit_items']=[dict(limit_id=uid(),statement='Bounded applicability',evidence_links=[dict(evidence_version_id=record['evidence_version_id'],relation='challenges')])]
    return record

def test_polish_lifecycle_preserves_claims_and_legacy_rows_across_restore(env):
    old,_=save(env,draft(env));old_rows=rows(env)['approach_versions'];c=polish_content();record=polish_evidence(env,c)
    p=preview(env,polish_req(c,old['draft_revision']));assert p['schema_version']=='3' and p['resolved']['evidence']==[record]
    assert {'/content/original_question','/content/elaboration','/content/limit_items'} <= {x['path'] for x in p['changes']}
    d=draft(env,polish_req(c,old['draft_revision']));assert d['schema_version']=='2' and d['updated_by']==env['actor']
    result,command=polish_save(env,d);v=result['saved']['version']
    assert v['schema_version']=='2' and v['created_by']==env['actor'] and v['content']==c
    assert result['saved']['closure']['evidence']==[record]
    assert rows(env)['approach_versions'][0]==old_rows[0]
    assert env['service'].state(env['actor'],env['sid'])['latest_version']['schema_version']=='2'
    assert [x['schema_version'] for x in env['service'].versions(env['actor'],env['sid'])['items']]==['2','1']
    env['models'].clear()
    assert env['service'].save_version(env['actor'],env['sid'],command)==result
    assert env['service'].receipt(env['actor'],env['sid'],'approach_version',command['command_id'])['result']==result
    restore=dict(schema_version='1',command_id=uid(),expected_revision=result['draft_revision'],approach_version_id=old['saved']['version']['approach_version_id'])
    restored=env['service'].restore(env['actor'],env['sid'],restore)
    assert restored['schema_version']=='1' and restored['content']==old['saved']['version']['content']
    assert env['service'].read(env['actor'],env['sid'],v['approach_version_id'])==result['saved']
    assert rows(env)['approach_versions'][0]==old_rows[0]

@pytest.mark.parametrize('fault',['duplicate_id','duplicate_relation','foreign','missing','stale','tamper_preview'])
def test_polish_invalid_limits_do_not_commit(env,fault):
    c=polish_content();record=polish_evidence(env,c);b=polish_req(c)
    p=preview(env,b);item=c['limit_items'][0]
    if fault=='duplicate_id':c['limit_items'].append(dict(item,statement='Conflicting limit'))
    if fault=='duplicate_relation':item['evidence_links']*=2
    if fault in ('foreign','missing'):item['evidence_links'][0]['evidence_version_id']=uid()
    if fault=='foreign':
        foreign=env['store'].create_study(uid(),uid(),'SECRET')['study_id'];record.update(study_id=foreign,evidence_version_id=item['evidence_links'][0]['evidence_version_id'])
        with env['store'].connection(write=True) as db:db.execute('INSERT INTO evidence VALUES(?,?,?,?)',(record['evidence_version_id'],record['evidence_id'],foreign,json.dumps(record)))
    if fault=='stale':draft(env)
    if fault=='tamper_preview':c['original_question']['text']='Unreviewed change'
    with pytest.raises(DomainError) as error:env['service'].save_draft(env['actor'],env['sid'],b|dict(command_id=uid(),expected_preview_digest=p['preview_digest']))
    if fault in ('foreign','missing'):assert error.value.status==404 and 'SECRET' not in str(error.value.data())
    assert len(rows(env)['approach_drafts'])==(1 if fault=='stale' else 0)
    assert rows(env)['approach_versions']==[]

@pytest.mark.parametrize('race',['revoke','evidence'])
def test_polish_limit_witness_rechecked_at_commit(env,monkeypatch,race):
    c=polish_content();record=polish_evidence(env,c);b=polish_req(c);p=preview(env,b);original=env['store'].command
    def change(*args,**kwargs):
        with env['store'].connection(write=True) as db:
            if race=='revoke':db.execute('DELETE FROM memberships')
            else:
                # Explicit corruption injection in this isolated synthetic store;
                # ordinary writes already fail its immutable evidence trigger.
                trigger=db.execute("SELECT sql FROM sqlite_master WHERE type='trigger' AND name='immutable_evidence_update'").fetchone()[0]
                db.execute('DROP TRIGGER immutable_evidence_update')
                db.execute('UPDATE evidence SET payload=? WHERE evidence_version_id=?',(json.dumps(dict(record,title='Changed')),record['evidence_version_id']))
                db.execute(trigger)
        return original(*args,**kwargs)
    monkeypatch.setattr(env['store'],'command',change)
    with pytest.raises(DomainError):env['service'].save_draft(env['actor'],env['sid'],b|dict(command_id=uid(),expected_preview_digest=p['preview_digest']))
    assert rows(env)['approach_drafts']==[]

def test_polish_rejected_receipt_and_lost_draft_reply_are_recoverable(env):
    b=polish_req();p=preview(env,b);b.update(command_id=uid(),expected_preview_digest=p['preview_digest'])
    d=env['service'].save_draft(env['actor'],env['sid'],b)
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:env['service'].save_draft(env['actor'],env['sid'],b),range(2)))
    assert results==[d,d]
    changed=deepcopy(b);changed['content']['elaboration']['text']='Changed'
    with pytest.raises(DomainError,match='command_payload_conflict'):env['service'].save_draft(env['actor'],env['sid'],changed)
    rejected=polish_req(d['content'],d['revision'])|dict(command_id=uid(),expected_preview_digest='a'*64)
    with pytest.raises(DomainError):env['service'].save_draft(env['actor'],env['sid'],rejected)
    receipt=env['service'].receipt(env['actor'],env['sid'],'approach_draft',rejected['command_id'])
    validate('ApproachReceiptRead2',receipt);assert receipt['state']=='rejected' and receipt['result'] is None


def test_polish_reopen_retained_content_and_restore_need_no_model_service(env):
    c,m,_,_=link(env,polish_content());record=polish_evidence(env,c)
    saved,_=polish_save(env,draft(env,polish_req(c)))
    before=rows(env);reopened=Approaches(Store(env['store'].path),None)
    v=saved['saved']['version'];assert reopened.read(env['actor'],env['sid'],v['approach_version_id'])==saved['saved']
    assert reopened.state(env['actor'],env['sid'])['draft']['content']==c
    assert rows(env)==before
    b=dict(schema_version='1',command_id=uid(),expected_revision=saved['draft_revision'],approach_version_id=v['approach_version_id'])
    restored=reopened.restore(env['actor'],env['sid'],b)
    assert restored['schema_version']=='2' and restored['content']==c
    assert reopened.receipt(env['actor'],env['sid'],'approach_restore',b['command_id'])['result']==restored
    assert reopened.read(env['actor'],env['sid'],v['approach_version_id'])['closure']['evidence']==[record]

def test_polish_null_claim_upgrade_does_not_invent_original_wording(env):
    old,_=save(env,draft(env));c=deepcopy(old['saved']['version']['content'])
    c.update(schema_version='2',original_question=None,elaboration=None,limit_items=[])
    d=draft(env,polish_req(c,old['draft_revision']));new,_=polish_save(env,d)
    assert new['saved']['version']['content']==c
    assert env['service'].read(env['actor'],env['sid'],old['saved']['version']['approach_version_id'])==old['saved']


def test_polish_explicit_legacy_edit_reports_removed_claims_before_commit(env):
    d=draft(env,polish_req());legacy=content();legacy['question']=d['content']['question']
    p=preview(env,req(legacy,d['revision']))
    removed={x['path'] for x in p['changes'] if x['kind']=='removed'}
    assert removed=={'/content/original_question','/content/elaboration','/content/limit_items'}
    assert env['service'].state(env['actor'],env['sid'])['draft']==d


@pytest.mark.parametrize('field', ['original_question', 'elaboration'])
@pytest.mark.parametrize('text', ['', ' \t\r\n', 'x' * 4096], ids=['empty', 'whitespace', 'maximum'])
def test_polish_optional_question_claim_saved_verbatim(env, field, text):
    c = polish_content()
    c[field]['text'] = text
    result, _ = polish_save(env, draft(env, polish_req(c)))
    saved = result['saved']
    assert saved['version']['content'][field] == c[field]
    assert saved['closure']['approach_versions'][0]['content'][field] == c[field]
    assert env['service'].read(env['actor'], env['sid'], saved['version']['approach_version_id']) == saved


@pytest.mark.parametrize('field', ['original_question', 'elaboration'])
@pytest.mark.parametrize('text', ['x' * 4097, None, 7], ids=['oversize', 'null', 'number'])
def test_polish_optional_question_claim_invalid_text_rejected(env, field, text):
    c = polish_content()
    c[field]['text'] = text
    before = rows(env)
    with pytest.raises(DomainError):
        draft(env, polish_req(c))
    assert rows(env) == before
