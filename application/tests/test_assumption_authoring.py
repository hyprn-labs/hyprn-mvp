"""Real Coordinator/Store/API with an explicit in-process private transport.
This boundary fixture is not native HTTP/Rails proof; the modeling-service tests prove that.
Every transport call proves no application SQLite write lock spans private I/O.
"""
from copy import deepcopy
import json
import sqlite3
from pathlib import Path

import scoped_fixture as guard
from checks import PROJECTION_SCOPE
SCOPE=PROJECTION_SCOPE or guard.scope_from_environment()
guard.validate_scope(SCOPE)

import pytest
from fastapi.testclient import TestClient
from hyprn_mvp_app.api import create_app
from hyprn_mvp_app.auth import Auth
from hyprn_mvp_app.modeling import Coordinator, ModelingClient, validate
from hyprn_mvp_app.store import Store, DomainError, uid, digest
from test_assumptions_evidence_contracts import sample,D

ORIGIN='http://127.0.0.1:19999'

def statement(*versions, owner=None):
    return dict(assumption_id=uid(),owner=owner or dict(kind='model'),statement='Steady flow',
        evidence_links=[dict(evidence_version_id=v,relation='supports') for v in versions])

def revision(draft):
    result={k:deepcopy(v) for k,v in draft.items() if k not in {'study_id','name','draft_revision'}}
    result.update(model_revision_id=uid(),parent_model_revision_id=None,originating_draft_revision=draft['draft_revision'])
    result['digest']=digest(result)
    return result

class PrivateTransport:
    """Typed deterministic private responses; never runs/imports candidate code."""
    def __init__(self,store,sid):
        self.store=store; self.sid=sid; self.calls=[]; self.receipts={}; self.revisions={}
        self.hook=None; self.lose_response=False
        self.caps=sample(D['Capabilities'])
        self.caps['generator_identity'].update(source_commit='a'*40,provenance_path='provenance/fixture.json')
        cap=sample(D['Capabilities']['properties']['capabilities']['items'])
        cap.update(id='model_assumptions',version='1',supported=True)
        self.caps.update(contract_versions=['1.2'],schema_versions=['1','2'],capabilities=[cap])
        self.draft=sample(D['ModelDraft2'])
        root,child=uid(),uid()
        definition=sample(D['Definition']);definition.update(definition_id=uid(),definition_version_id=uid())
        self.draft.update(model_id=uid(),study_id=sid,root_instance_id=root,draft_revision=uid(),name='Exact model',
            definitions=[definition],instances=[dict(instance_id=i,definition_version_id=definition['definition_version_id'],name=n) for i,n in [(root,'Root'),(child,'Child')]])
    def __call__(self,method,path,raw,headers):
        assert headers['Authorization'].startswith('Bearer ')
        with sqlite3.connect(self.store.path,timeout=0) as db:
            db.execute('BEGIN IMMEDIATE');db.rollback()
        body=json.loads(raw) if raw else None
        self.calls.append((method,path,deepcopy(body)))
        if self.hook:self.hook(method,path,body)
        response=lambda data,**extra:dict(schema_version='1',request_id=uid(),data=deepcopy(data),**extra)
        if path.endswith('/capabilities'):return 200,response(self.caps)
        if '/commands/' in path:
            command=path.split('/commands/')[1].split('?')[0]
            receipt=self.receipts.get(command)
            if receipt is None:
                receipt=dict(command_id=command,state='absent')
            return 200,response(receipt)
        if '/revisions/' in path:return 200,response(self.revisions[path.rsplit('/',1)[1]])
        if method=='GET':return 200,response(self.draft)
        operation=path.rsplit('/',1)[1]
        draft=deepcopy(self.draft)
        created={}
        if operation in {'preview','edits'}:
            for edit in body['edits']:
                if edit['kind']=='add_assumption':
                    a=statement();a.update(owner=edit['owner'],statement=edit['statement'],evidence_links=edit['evidence_links'])
                    created[edit['temp_key']]={'assumption_id':a['assumption_id']};draft['assumptions'].append(a)
                elif edit['kind']=='update_assumption':
                    a=next(a for a in draft['assumptions'] if a['assumption_id']==edit['assumption_id'])
                    a.update(statement=edit['statement'],evidence_links=edit['evidence_links'])
                elif edit['kind']=='remove_assumption':
                    draft['assumptions']=[a for a in draft['assumptions'] if a['assumption_id']!=edit['assumption_id']]
            if operation=='edits':draft['draft_revision']=uid();self.draft=draft
            result=response(draft,created_ids=created,diagnostics=[])
        elif operation=='commits':
            value=revision(draft);self.revisions[value['model_revision_id']]=value;result=response(value)
        elif operation=='imports':
            result=response(draft);operation='import'
        else:raise AssertionError((method,path))
        if 'command_id' in body:
            payload=dict(major='1',operation=operation,target=None if operation=='import' else draft['model_id'],
                study_id=self.sid,payload={k:v for k,v in body.items() if k!='command_id'})
            result_body={k:v for k,v in result.items() if k not in {'schema_version','request_id'}}
            receipt=sample(D['Receipt'])
            receipt.update(command_id=body['command_id'],state='committed',payload_digest=digest(payload),status=200,response=result_body)
            self.receipts[body['command_id']]=receipt
            if self.lose_response:self.lose_response=False;raise OSError('simulated response loss')
        return 200,result

@pytest.fixture
def env(tmp_path):
    assert guard.no_symlinks(tmp_path).is_relative_to(SCOPE.root)
    store=Store(tmp_path/'authoring.sqlite');auth=Auth(store,ORIGIN)
    actor=auth.provision('owner','correct horse battery staple')
    study=store.create_study(actor,uid(),'Exact study');sid=study['study_id']
    transport=PrivateTransport(store,sid)
    model=ModelingClient('http://private.invalid/modeling/1',b't'*32,transport=transport)
    coord=Coordinator(store,model);mid=transport.draft['model_id']
    with store.connection(write=True) as db:db.execute('INSERT INTO model_associations VALUES(?,?,?)',(sid,mid,uid()))
    client=TestClient(create_app(store,auth,model),base_url=ORIGIN)
    login=client.post('/api/1/session',json=dict(username='owner',password='correct horse battery staple'),headers={'Origin':ORIGIN})
    client.headers.update({'Origin':ORIGIN,'X-CSRF-Token':login.json()['data']['csrf_token']})
    return dict(store=store,actor=actor,sid=sid,mid=mid,coord=coord,transport=transport,client=client,study=study)

def evidence(env,*,sid=None,title='Original report'):
    sid=env['store'].create_study(uid(),uid(),'Foreign study')['study_id'] if sid else env['sid']
    record=sample(D['EvidenceRecord3'])
    record.update(study_id=sid,evidence_id=uid(),evidence_version_id=uid(),title=title,
        resource_scope=dict(scope_version='1',kind='study',study_id=sid),
        recorded_context=dict(schema_version='1',label='Recorded label',resource_labels=[]))
    with env['store'].connection(write=True) as db:
        db.execute('INSERT INTO evidence VALUES(?,?,?,?)',(record['evidence_version_id'],record['evidence_id'],sid,json.dumps(record)))
    return record

def url(env,suffix=''):
    return '/api/1/studies/'+env['sid']+'/models/'+env['mid']+suffix

def command(env,*links):
    return dict(command_id=uid(),schema_version='2',expected_revision=env['transport'].draft['draft_revision'],
        edits=[dict(kind='add_assumption',temp_key='new',owner=dict(kind='model'),statement='Added',
            evidence_links=[dict(evidence_version_id=v,relation='supports') for v in links])])

def execute(env,body,action='edits'):
    return env['coord'].execute(env['actor'],env['sid'],action,env['mid'],body,body,
        '/models/'+env['mid']+'/'+action,'Apply' if action=='edits' else 'Commit',
        'ModelDraftEditResponse' if action=='edits' else 'ModelRevisionResponse')

def test_exact_draft_revision_resolution_dedup_and_no_foreign_metadata(env):
    e=evidence(env);foreign=evidence(env,sid=uid(),title='FOREIGN SECRET');missing=uid()
    a=statement(e['evidence_version_id'],foreign['evidence_version_id'],missing)
    a['evidence_links'].append(dict(evidence_version_id=e['evidence_version_id'],relation='challenges'))
    t=env['transport'];t.draft['assumptions']=[a,statement(e['evidence_version_id'])]
    frozen=revision(t.draft);t.revisions[frozen['model_revision_id']]=frozen
    for selector,value in [('draft_revision',t.draft['draft_revision']),('model_revision_id',frozen['model_revision_id'])]:
        r=env['client'].get(url(env,'/assumption-evidence')+'?'+selector+'='+value)
        assert r.status_code==200,r.text
        result=r.json()['data'];validate('AssumptionEvidenceResolution1',result)
        assert result['evidence']==[e] and len(result['links'])==4
        assert [l['status'] for l in result['links']].count('unavailable')==2
        assert 'FOREIGN SECRET' not in r.text and foreign['evidence_id'] not in r.text
        assert result['model_digest']==(frozen['digest'] if selector=='model_revision_id' else None)
    newer=deepcopy(e);newer.update(evidence_version_id=uid(),title='New head',parent_evidence_version_id=e['evidence_version_id'])
    with env['store'].connection(write=True) as db:
        db.execute('INSERT INTO evidence VALUES(?,?,?,?)',(newer['evidence_version_id'],e['evidence_id'],env['sid'],json.dumps(newer)))
    assert env['coord'].assumption_evidence(env['actor'],env['sid'],env['mid'],model_revision_id=frozen['model_revision_id'])['evidence']==[e]

@pytest.mark.parametrize('selectors',[{},dict(draft_revision=' '),dict(draft_revision='a'*4097),
    dict(model_revision_id='bad'),dict(model_revision_id=uid(),draft_revision='x')])
def test_exact_selector_validation_before_private_lookup(env,selectors):
    with pytest.raises(DomainError) as error:env['coord'].assumption_evidence(env['actor'],env['sid'],env['mid'],**selectors)
    assert error.value.status==400 and env['transport'].calls==[]

def test_stale_draft_and_unauthorized_association_fail_without_fallback(env):
    r=env['client'].get(url(env,'/assumption-evidence')+'?draft_revision=stale')
    assert r.status_code==409 and r.json()['error']['code']=='stale_revision'
    with env['store'].connection(write=True) as db:db.execute('DELETE FROM model_associations')
    before=len(env['transport'].calls)
    assert env['client'].get(url(env,'/assumption-evidence')+'?draft_revision=x').status_code==404
    assert len(env['transport'].calls)==before

@pytest.mark.parametrize('bad',['foreign_model','foreign_study','duplicate_id','missing_owner','root_owner','duplicate_link','bad_source','bad_digest','wrong_revision'])
def test_semantic_backend_corruption_rejected_even_with_rehashed_model(env,bad):
    t=env['transport'];a=statement(uid());t.draft['assumptions']=[a]
    selected=t.draft;immutable=bad in {'bad_digest','wrong_revision'}
    if immutable:
        selected=revision(selected);key=selected['model_revision_id'];t.revisions[key]=selected
    if bad=='foreign_model':selected['model_id']=uid()
    if bad=='foreign_study':selected['study_id']=uid()
    if bad=='duplicate_id':selected['assumptions'].append(dict(a,statement='Different'))
    if bad=='missing_owner':a['owner']=dict(kind='instance',instance_id=uid())
    if bad=='root_owner':a['owner']=dict(kind='instance',instance_id=selected['root_instance_id'])
    if bad=='duplicate_link':a['evidence_links']*=2
    if bad=='bad_source':
        source=sample(D['Source']);source.update(bytes='eA==',sha256='0'*64);selected['source_files']=[source]
    if bad=='bad_digest':selected['digest']='0'*64
    if bad=='wrong_revision':
        selected['model_revision_id']=uid();selected['digest']=digest({k:v for k,v in selected.items() if k!='digest'})
    suffix='/revisions/'+key if immutable else ''
    r=env['client'].get(url(env,suffix))
    assert r.status_code==503,r.text

@pytest.mark.parametrize('failure',['contract','schema','capability','version','unsupported','malformed','outage','status'])
@pytest.mark.parametrize('action',['preview','edits'])
def test_checked_capabilities_and_no_downgrade_or_outbound_mutation(env,failure,action):
    caps=env['transport'].caps
    if failure=='contract':caps['contract_versions']=['1.1']
    if failure=='schema':caps['schema_versions']=['1']
    if failure=='capability':caps['capabilities']=[]
    if failure=='version':caps['capabilities'][0]['version']='2'
    if failure=='unsupported':caps['capabilities'][0]['supported']=False
    if failure=='malformed':caps['extra']=True
    if failure in {'outage','status'}:
        original=env['coord'].model.transport
        def unavailable(*args):
            status,result=original(*args)
            if failure=='outage':raise OSError('offline fixture')
            return 202,result
        env['coord'].model.transport=unavailable
    discovery=env['client'].get('/api/1/capabilities')
    assert discovery.status_code==200
    report=discovery.json()['data']
    assert 'model_assumptions/1' in report['unavailable']
    assert env['coord'].assumptions_supported(env['actor'],env['sid']) is False
    body=command(env)
    if action=='preview':body.pop('command_id')
    r=env['client'].post(url(env,'/'+action),json=body)
    backend_error=failure in {'malformed','outage','status'}
    assert r.status_code==(503 if backend_error else 422)
    assert r.json()['error']['code']==('backend_unavailable' if backend_error else 'unsupported_capability')
    assert not any(c[0]=='POST' for c in env['transport'].calls)
    with env['store'].connection() as db:assert db.execute("SELECT COUNT(*) FROM receipts WHERE category='model'").fetchone()[0]==0

@pytest.mark.parametrize('outcome',['supported','unsupported','malformed','outage'])
@pytest.mark.parametrize('action',['preview','edits','discovery','helper'])
def test_capability_revocation_suppresses_success_and_failure(env,outcome,action):
    t=env['transport']
    if outcome=='unsupported':t.caps['capabilities']=[]
    if outcome=='malformed':t.caps['extra']=True
    def revoke(method,path,body):
        assert path.endswith('/capabilities')
        with env['store'].connection(write=True) as db:db.execute('DELETE FROM memberships')
        if outcome=='outage':raise OSError('offline after revocation')
    t.hook=revoke
    if action=='helper':
        with pytest.raises(DomainError) as error:env['coord'].assumptions_supported(env['actor'],env['sid'])
        assert error.value.status==404 and error.value.code=='resource_not_found'
    else:
        body=command(env)
        if action=='preview':body.pop('command_id')
        r=(env['client'].get('/api/1/capabilities') if action=='discovery'
            else env['client'].post(url(env,'/'+action),json=body))
        assert r.status_code==404 and r.json()['error']['code']=='resource_not_found'
    assert not any(c[0]=='POST' for c in t.calls)
    with env['store'].connection() as db:assert db.execute("SELECT COUNT(*) FROM receipts WHERE category='model'").fetchone()[0]==0

def test_supported_capability_is_scoped_and_configuration_remains_unavailable(env):
    report=env['client'].get('/api/1/capabilities').json()['data']
    assert 'model_assumptions/1' in report['modeling'] and 'model_assumptions/1' not in report['unavailable']
    assert 'configuration_assumptions/1' in report['unavailable']
    assert env['transport'].calls==[('GET','/modeling/1/capabilities',None)]
    with env['store'].connection(write=True) as db:db.execute('DELETE FROM memberships')
    before=len(env['transport'].calls)
    report=env['client'].get('/api/1/capabilities').json()['data']
    assert 'model_assumptions/1' in report['unavailable'] and len(env['transport'].calls)==before

@pytest.mark.parametrize('action',['preview','edits'])
@pytest.mark.parametrize('foreign',[False,True])
def test_new_citations_require_same_study_before_private_mutation(env,action,foreign):
    version=evidence(env,sid=uid())['evidence_version_id'] if foreign else uid()
    body=command(env,version)
    if action=='preview':body.pop('command_id')
    old=deepcopy(env['transport'].draft)
    r=env['client'].post(url(env,'/'+action),json=body)
    assert r.status_code==404 and env['transport'].draft==old
    assert not any(c[0]=='POST' for c in env['transport'].calls)

def test_statement_only_edit_preserves_unknown_but_changed_relation_rejects(env):
    t=env['transport'];a=statement(uid());t.draft['assumptions']=[a]
    edit=dict(kind='update_assumption',assumption_id=a['assumption_id'],statement='Clarified',evidence_links=a['evidence_links'])
    body=dict(command_id=uid(),schema_version='2',expected_revision=t.draft['draft_revision'],edits=[edit])
    assert execute(env,body)[0]==200
    changed=deepcopy(body);changed.update(command_id=uid(),expected_revision=t.draft['draft_revision'])
    changed['edits'][0]['evidence_links'][0]['relation']='challenges'
    with pytest.raises(DomainError) as error:execute(env,changed)
    assert error.value.status==404
    commit=dict(command_id=uid(),expected_revision=t.draft['draft_revision'])
    assert execute(env,commit,'commits')[0]==200
    assert t.draft['assumptions'][0]['evidence_links']==a['evidence_links']

def test_known_foreign_commit_rejected_while_diagnostics_are_unavailable(env):
    t=env['transport'];foreign=evidence(env,sid=uid());t.draft['assumptions']=[statement(foreign['evidence_version_id'])]
    body=dict(command_id=uid(),expected_revision=t.draft['draft_revision'])
    with pytest.raises(DomainError) as error:execute(env,body,'commits')
    assert error.value.status==404 and not t.revisions
    result=env['coord'].assumption_evidence(env['actor'],env['sid'],env['mid'],draft_revision=t.draft['draft_revision'])
    assert result['evidence']==[] and result['links'][0]['status']=='unavailable'

def test_success_exact_replay_changed_payload_stale_cas_and_reader_denial(env):
    e=evidence(env);body=command(env,e['evidence_version_id']);result=execute(env,body)
    before=len(env['transport'].calls)
    assert execute(env,body)==result and len(env['transport'].calls)==before
    changed=deepcopy(body);changed['edits'][0]['statement']='Altered'
    with pytest.raises(DomainError) as error:execute(env,changed)
    assert error.value.code=='command_payload_conflict'
    with pytest.raises(DomainError) as error:execute(env,dict(body,command_id=uid()))
    assert error.value.code=='stale_revision'
    with env['store'].connection(write=True) as db:db.execute("UPDATE memberships SET role='reader'")
    with pytest.raises(DomainError) as error:execute(env,body)
    assert error.value.status==403

def test_lost_response_reconcile_exact_receipt_without_current_draft_cas(env):
    e=evidence(env);body=command(env,e['evidence_version_id']);env['transport'].lose_response=True
    assert execute(env,body)[0]==202
    result=env['coord'].reconcile(env['actor'],env['sid'],body['command_id'])
    assert result[0]==200 and result[1]['data']==env['transport'].draft
    assert len([c for c in env['transport'].calls if c[0]=='POST'])==1
    assert execute(env,body)==result

@pytest.mark.parametrize('phase',['draft','preview','edits','receipt'])
def test_revocation_during_private_io_suppresses_results_and_local_commit(env,phase):
    e=evidence(env);body=command(env,e['evidence_version_id']);t=env['transport']
    if phase=='receipt':
        t.lose_response=True;assert execute(env,body)[0]==202
    def revoke(method,path,body):
        matches=(phase=='draft' and method=='GET' and path.endswith(env['mid']) or
            phase in {'preview','edits'} and method=='POST' and path.endswith('/'+phase) or
            phase=='receipt' and '/commands/' in path)
        if matches:
            with env['store'].connection(write=True) as db:db.execute('DELETE FROM memberships')
    t.hook=revoke
    if phase=='receipt':
        with pytest.raises(DomainError) as error:env['coord'].reconcile(env['actor'],env['sid'],body['command_id'])
        assert error.value.status==404
    else:
        request=deepcopy(body)
        if phase=='preview':request.pop('command_id')
        r=env['client'].get(url(env)) if phase=='draft' else env['client'].post(url(env,'/'+phase),json=request)
        assert r.status_code==404
    with env['store'].connection() as db:
        assert db.execute("SELECT COUNT(*) FROM receipts WHERE category='model' AND state='committed'").fetchone()[0]==0

def test_citation_disappears_after_private_apply_no_success_receipt_or_replay(env):
    e=evidence(env);body=command(env,e['evidence_version_id'])
    def remove(method,path,body):
        if method=='POST':
            # Explicit storage-loss fault in this isolated store; normal evidence
            # writes cannot remove rows because the immutable trigger forbids it.
            with env['store'].connection(write=True) as db:
                db.execute('DROP TRIGGER immutable_evidence_delete')
                db.execute('DELETE FROM evidence')
    env['transport'].hook=remove
    with pytest.raises(DomainError) as error:execute(env,body)
    assert error.value.status==404
    with env['store'].connection() as db:assert db.execute("SELECT COUNT(*) FROM receipts WHERE category='model' AND state='committed'").fetchone()[0]==0
    # The remote may already have accepted: no distributed rollback is claimed.
    assert env['transport'].draft['assumptions']
    with pytest.raises(DomainError):env['coord'].reconcile(env['actor'],env['sid'],body['command_id'])

def test_unknown_import_preserves_opaque_citation_and_association(env):
    t=env['transport'];t.draft['assumptions']=[statement(uid())]
    frozen=revision(t.draft);package=sample(D['ModelPackage2'])
    package.update(model_id=env['mid'],model_revision_id=frozen['model_revision_id'],revisions=[frozen])
    package['digest']=digest({k:v for k,v in package.items() if k!='digest'})
    with env['store'].connection(write=True) as db:db.execute('DELETE FROM model_associations')
    public=dict(command_id=uid(),expected_revision=env['study']['revision'],package=package)
    private=dict(public,expected_revision=None,study_id=env['sid'],preserve_public_ids=True)
    result=env['coord'].execute(env['actor'],env['sid'],'import',None,public,private,'/imports','Import','ModelDraftResponse',association=True)
    assert result[0]==200 and result[1]['data']['assumptions']==t.draft['assumptions']
    resolved=env['coord'].assumption_evidence(env['actor'],env['sid'],env['mid'],draft_revision=t.draft['draft_revision'])
    assert resolved['links'][0]['status']=='unavailable'

def test_public_committed_receipt_rechecks_model_association(env):
    body=command(env);result=execute(env,body)
    assert result[0]==200
    receipt='/api/1/studies/'+env['sid']+'/commands/'+body['command_id']+'?category=model'
    assert env['client'].get(receipt).status_code==200
    with env['store'].connection(write=True) as db:db.execute('DELETE FROM model_associations')
    response=env['client'].get(receipt)
    assert response.status_code==404 and 'Added' not in response.text

def test_native_receipt_payload_mismatch_stays_pending_without_redispatch(env):
    body=command(env);t=env['transport'];t.lose_response=True
    assert execute(env,body)[0]==202
    t.receipts[body['command_id']]['payload_digest']='0'*64
    assert env['coord'].reconcile(env['actor'],env['sid'],body['command_id'])[0]==202
    assert len([c for c in t.calls if c[0]=='POST'])==1
    with env['store'].connection() as db:
        assert env['store']._receipt(db,env['sid'],'model',body['command_id'])['state']=='pending_remote'

def test_committed_import_replay_requires_current_association(env):
    test_unknown_import_preserves_opaque_citation_and_association(env)
    with env['store'].connection() as db:
        command_id=db.execute("SELECT command_id FROM receipts WHERE category='model'").fetchone()[0]
    with env['store'].connection(write=True) as db:db.execute('DELETE FROM model_associations')
    with pytest.raises(DomainError) as error:env['coord'].reconcile(env['actor'],env['sid'],command_id)
    assert error.value.status==404

def test_valid_legacy_model_keeps_original_bytes(env):
    t=env['transport'];t.draft.pop('assumptions');t.draft['schema_version']='1'
    old=deepcopy(t.draft);frozen=revision(old);t.revisions[frozen['model_revision_id']]=frozen
    assert env['coord'].read(env['actor'],env['sid'],env['mid'])['data']==old
    result=env['coord'].assumption_evidence(env['actor'],env['sid'],env['mid'],model_revision_id=frozen['model_revision_id'])
    assert result['links']==result['evidence']==[] and result['model_digest']==frozen['digest']
    assert t.draft==old

def test_duplicate_assumption_identity_rehashed_revision_denied(env):
    t=env['transport'];a=statement();t.draft['assumptions']=[a,dict(a,statement='Different')]
    frozen=revision(t.draft);t.revisions[frozen['model_revision_id']]=frozen
    with pytest.raises(DomainError) as error:
        env['coord'].assumption_evidence(env['actor'],env['sid'],env['mid'],model_revision_id=frozen['model_revision_id'])
    assert error.value.status==503

def test_exact_request_version_forwarded_through_public_preview_and_apply(env):
    record=evidence(env);body=command(env,record['evidence_version_id'])
    preview={k:v for k,v in body.items() if k!='command_id'}
    old=deepcopy(env['transport'].draft)
    assert env['client'].post(url(env,'/preview'),json=preview).status_code==200
    assert env['transport'].draft==old
    assert env['client'].post(url(env,'/edits'),json=body).status_code==200
    posts=[c for c in env['transport'].calls if c[0]=='POST']
    assert posts[0][2]==preview and posts[1][2]==body

@pytest.mark.parametrize('stored_code',['invalid_request','resource_not_found'])
def test_rejected_public_receipt_never_swallows_current_authorization_failure(env,stored_code):
    body=command(env);t=env['transport'];t.lose_response=True
    assert execute(env,body)[0]==202
    with env['store'].connection(write=True) as db:
        error=DomainError(stored_code,404 if stored_code=='resource_not_found' else 400).data()
        db.execute("UPDATE receipts SET state='rejected',error=? WHERE category='model' AND command_id=?",
            (json.dumps(error),body['command_id']))
    receipt='/api/1/studies/'+env['sid']+'/commands/'+body['command_id']+'?category=model'
    visible=env['client'].get(receipt)
    assert visible.status_code==200 and visible.json()['data']['state']=='rejected'
    with env['store'].connection(write=True) as db:db.execute('DELETE FROM model_associations')
    denied=env['client'].get(receipt)
    assert denied.status_code==404 and 'state' not in denied.json().get('data',{})


# Model citations read exact evidence through Store.evidence_record. A stored row
# whose own identity (study, version or resource-scope study) disagrees with its exact
# reference is a corrupt backend for model authoring: 503, nothing sent, nothing disclosed.
@pytest.mark.parametrize('field',['study_id','evidence_version_id','resource_scope'])
def test_corrupt_cited_evidence_identity_is_unavailable_before_private_mutation(env,field):
    e=evidence(env);version=e['evidence_version_id']
    with env['store'].connection(write=True) as db:
        db.execute('DROP TRIGGER IF EXISTS immutable_evidence_update')
        stored=json.loads(db.execute('SELECT payload FROM evidence WHERE evidence_version_id=?',(version,)).fetchone()[0])
        if field=='resource_scope':stored['resource_scope']['study_id']=uid()
        else:stored[field]=uid()
        db.execute('UPDATE evidence SET payload=? WHERE evidence_version_id=?',(json.dumps(stored),version))
    old=deepcopy(env['transport'].draft)
    r=env['client'].post(url(env,'/edits'),json=command(env,version))
    assert r.status_code==503 and r.json()['error']['code']=='backend_unavailable',r.text
    assert env['transport'].draft==old and not any(c[0]=='POST' for c in env['transport'].calls)
    assert 'Original report' not in r.text
    env['transport'].draft['assumptions']=[statement(version)]
    with pytest.raises(DomainError) as error:
        env['coord'].assumption_evidence(env['actor'],env['sid'],env['mid'],draft_revision=env['transport'].draft['draft_revision'])
    assert (error.value.code,error.value.status)==('backend_unavailable',503)


# Store's in-transaction interface. The caller holds the connection (and so the
# transaction); Store reads the study row, a command receipt and a study's association with
# one model. Authorization comes before the association lookup, and an unknown model, another
# study's model and a non-member are the same undisclosed 404.
def test_store_in_transaction_interface_reads_study_receipt_and_model_association(env):
    store,actor,sid,mid=env['store'],env['actor'],env['sid'],env['mid']
    command_id=uid();created=store.create_study(actor,command_id,'Receipt study')
    with store.connection() as db:
        stored=dict(db.execute('SELECT * FROM model_associations WHERE study_id=? AND model_id=?',(sid,mid)).fetchone())
        assert set(stored)=={'study_id','model_id','command_id'}
        assert store.model_association(db,actor,sid,mid)==stored
        assert store.model_association(db,actor,sid,mid,write=True)==stored
        assert store.study_row(db,sid)==dict(db.execute('SELECT * FROM studies WHERE study_id=?',(sid,)).fetchone())
        with pytest.raises(DomainError) as missing:store.study_row(db,uid())
        assert (missing.value.code,missing.value.status)==('resource_not_found',404)
        receipt=store.command_receipt(db,'actor:'+actor,'study_create',command_id)
        assert receipt==store.receipt(actor,None,'study_create',command_id)
        assert receipt['state']=='committed' and receipt['result']==created and receipt['request'] is None
        assert store.command_receipt(db,sid,'model',uid()) is None


@pytest.mark.parametrize('case',['unknown','foreign','nonmember','reader_write'])
def test_store_model_association_authorizes_before_lookup_and_never_discloses(env,case):
    store,actor,sid,mid=env['store'],env['actor'],env['sid'],env['mid'];who,target,write=actor,mid,False
    if case=='unknown':target=uid()
    elif case=='foreign':
        other=store.create_study(actor,uid(),'Other owned study')['study_id'];target=uid()
        with store.connection(write=True) as db:db.execute('INSERT INTO model_associations VALUES(?,?,?)',(other,target,uid()))
    elif case=='nonmember':who=uid()
    else:
        write=True
        with store.connection(write=True) as db:db.execute("UPDATE memberships SET role='reader' WHERE study_id=? AND actor_id=?",(sid,actor))
    with store.connection() as db:
        with pytest.raises(DomainError) as error:store.model_association(db,who,sid,target,write=write)
    expected=('forbidden',403) if case=='reader_write' else ('resource_not_found',404)
    assert (error.value.code,error.value.status)==expected
    # The Coordinator's model authorization is the same read.
    with pytest.raises(DomainError) as coordinated:env['coord'].authorize_model(who,sid,target,write=write)
    assert (coordinated.value.code,coordinated.value.status)==expected
