"""Configuration3 contracts through real application boundaries and isolated stores.

Private compatibility is an explicit transport fixture, not native numerical proof.
"""
from copy import deepcopy
import json
import sqlite3

import pytest
from test_assumption_authoring import env, evidence, revision, statement, sample, D
from hyprn_mvp_app.configuration import Configurations
from hyprn_mvp_app.store import DomainError, digest, uid
from hyprn_mvp_app.modeling import Coordinator, ModelingClient
from test_result_bindings import env as binding_env


@pytest.fixture
def config(env):
    t=env['transport'];cap=deepcopy(t.caps['capabilities'][0])
    cap.update(id='resolved_configuration',version='3');t.caps['capabilities'].append(cap)
    e=evidence(env);eid=e['evidence_version_id']
    t.draft['assumptions']=[statement(eid)]
    model=revision(t.draft);t.revisions[model['model_revision_id']]=model
    original=t.__call__
    def transport(method,path,raw,headers):
        if not path.endswith('/configuration-compatibility'):return original(method,path,raw,headers)
        with sqlite3.connect(env['store'].path,timeout=0) as db:
            db.execute('BEGIN IMMEDIATE');db.rollback()
        body=json.loads(raw);candidate=body['configuration_candidate']
        t.calls.append((method,path,deepcopy(body)))
        if t.hook:t.hook(method,path,body)
        proof=sample(D['CompatibilityResult2'])
        proof.update(compatible=True,candidate_digest=digest(candidate),model_digest=model['digest'],
            model_revision_id=model['model_revision_id'],required_capabilities=candidate['required_capabilities'])
        return 200,dict(schema_version='1',request_id=uid(),data=proof)
    env['coord'].model.transport=transport
    request=sample(D['ConfigurationRequest3'])
    request.update(study_id=env['sid'],model_id=env['mid'],model_revision_id=model['model_revision_id'],
        context_source=dict(kind='current_study',expected_study_revision=env['study']['revision']),
        assumptions=[{k:v for k,v in statement(eid).items() if k!='owner'}],general_context_evidence_version_ids=[eid])
    return env,Configurations(env['store'],env['coord']),request,model,e


def preview(config):
    e,c,r,_,_=config
    return c.preview(e['actor'],e['sid'],r)[0]


def body(config,p=None):
    return dict(command_id=uid(),configuration_id=None,expected_revision=None,
        configuration=deepcopy(config[2]),expected_preview_digest=(p or preview(config))['candidate_digest'])


def counts(env):
    with env['store'].connection() as db:
        return tuple(db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] for table in ('configurations','configuration_families','outbox'))


@pytest.mark.parametrize('version',['3','4'])
@pytest.mark.parametrize('action',['preview','commit'])
@pytest.mark.parametrize('location',['input','criterion'])
def test_duplicate_input_evidence_is_field_error_before_save(config,version,action,location):
    e,c,r,m,record=config
    r['schema_version']=version
    if version=='4':r['approach_selection']=None
    item=sample(D['LiteralRequest']);eid=record['evidence_version_id']
    item['provenance']['evidence_version_ids']=[eid];r['inputs']=[item]
    criterion=sample(D['Criterion']);criterion['evidence_version_ids']=[eid];r['criteria']=[criterion]
    good=preview(config)
    # Same version cited by input, assumption and general context is valid.
    assert good['resolved_candidate']['evidence_snapshots']==[record]
    citations=item['provenance']['evidence_version_ids'] if location=='input' else criterion['evidence_version_ids']
    citations.append(eid)
    bad=deepcopy(good)
    bad['resolved_candidate']['inputs'][0]['provenance']=deepcopy(item['provenance'])
    bad['resolved_candidate']['criteria']=deepcopy(r['criteria'])
    bad['candidate_digest']=digest(bad['resolved_candidate'])
    with pytest.raises(DomainError) as error:
        if action=='preview':preview(config)
        else:c.commit(e['actor'],e['sid'],body(config,bad))
    assert error.value.code=='invalid_configuration' and error.value.status==422
    field='/inputs/0/provenance/evidence_version_ids/1' if location=='input' else '/criteria/0/evidence_version_ids/1'
    owner=item['target']['port_id'] if location=='input' else criterion['criterion_id']
    assert error.value.fields==[dict(path=field,
        code='duplicate_evidence',message='This evidence version is already cited in this field.',
        element_ref=owner)]
    assert counts(e)==(0,0,0)
    # Independent worker still rejects malformed input after application repair.
    from hyprn_mvp_integration.worker import verify_assumption_closure
    invalid=dict(bad['resolved_candidate'],configuration_id=uid(),configuration_revision_id=uid(),parent_revision_id=None)
    with pytest.raises(ValueError,match='Distinct bounded UUID'):
        verify_assumption_closure(invalid,m)
    citations.pop()
    saved=c.commit(e['actor'],e['sid'],body(config,good))
    assert saved['configuration']['inputs'][0]['provenance']['evidence_version_ids']==[eid]


@pytest.mark.parametrize('version',['1','2'])
@pytest.mark.parametrize('assumptions',['unknown_citation','empty'])
@pytest.mark.parametrize('action',['preview','commit'])
def test_legacy_authoring_rejects_model2_pairing_without_allocation(config,version,assumptions,action):
    e,c,request,model,_=config
    model['assumptions']=[] if assumptions=='empty' else [statement(uid())]
    model['digest']=digest({k:v for k,v in model.items() if k!='digest'})
    if version=='1':
        candidate=sample(D['ConfigurationCandidate1'])
        candidate.update(study_id=e['sid'],model_id=e['mid'],model_revision_id=model['model_revision_id'],
            context_snapshot=dict(description=e['study']['description'],boundary=e['study']['boundary'],notes=[]))
    else:
        candidate=deepcopy(request)
        candidate.pop('assumptions');candidate.pop('general_context_evidence_version_ids')
        candidate.update(schema_version='2',evidence_version_ids=[])
    e['transport'].calls.clear()
    with pytest.raises(DomainError) as error:
        if action=='preview':c.preview(e['actor'],e['sid'],candidate)
        else:c.commit(e['actor'],e['sid'],dict(command_id=uid(),configuration_id=None,expected_revision=None,
            configuration=candidate,**({'expected_preview_digest':'0'*64} if version=='2' else {})))
    assert error.value.code=='invalid_configuration' and error.value.status==422
    assert counts(e)==(0,0,0)
    assert not any(path.endswith('/configuration-compatibility') for _,path,_ in e['transport'].calls)


def test_full_closure_contradictory_relationships_and_immutable_save(config):
    e,c,r,m,record=config;eid=record['evidence_version_id']
    r['assumptions'][0]['evidence_links'].append(dict(evidence_version_id=eid,relation='challenges'))
    p=preview(config);candidate=p['resolved_candidate']
    assert counts(e)==(0,0,0) and candidate['evidence_snapshots']==[record]
    assert candidate['assumptions']==r['assumptions'] and candidate['general_context_evidence_version_ids']==[eid]
    b=body(config,p);saved=c.commit(e['actor'],e['sid'],b)
    assert saved['model_snapshot']==m and saved['configuration']['evidence_snapshots']==[record]
    assert c.commit(e['actor'],e['sid'],b)==saved and counts(e)==(1,1,0)
    before=deepcopy(saved);r['general_context_evidence_version_ids']=[];r['assumptions']=[]
    assert preview(config)['resolved_candidate']['evidence_snapshots']==[record]
    m['assumptions']=[];m['digest']=digest({k:v for k,v in m.items() if k!='digest'})
    assert preview(config)['resolved_candidate']['evidence_snapshots']==[]
    assert c.read(e['actor'],e['sid'],saved['configuration']['configuration_revision_id'])==before


@pytest.mark.parametrize('location',['model','assumption','input','criterion','general'])
@pytest.mark.parametrize('foreign',[False,True])
def test_unavailable_exact_reference_diagnostics_preview_and_commit_zero_allocation(config,location,foreign):
    e,c,r,m,_=config
    eid=evidence(e,sid=uid(),title='PRIVATE FOREIGN')['evidence_version_id'] if foreign else uid()
    if location=='model':m['assumptions'][0]['evidence_links'][0]['evidence_version_id']=eid
    elif location=='assumption':r['assumptions'][0]['evidence_links'][0]['evidence_version_id']=eid
    elif location=='general':r['general_context_evidence_version_ids']=[eid]
    elif location=='input':
        item=sample(D['LiteralRequest']);item['provenance']['evidence_version_ids']=[eid];r['inputs']=[item]
    else:
        item=sample(D['Criterion']);item['evidence_version_ids']=[eid];r['criteria']=[item]
    m['digest']=digest({k:v for k,v in m.items() if k!='digest'})
    for action in ('preview','commit'):
        with pytest.raises(DomainError) as error:
            if action=='preview':preview(config)
            else:c.commit(e['actor'],e['sid'],body(config,dict(candidate_digest='0'*64)))
        assert error.value.code=='invalid_configuration'
        fields=error.value.fields
        assert fields and all(f['code']=='unresolved_evidence' for f in fields)
        assert 'PRIVATE FOREIGN' not in str(fields)
        if location in ('model','assumption'):
            assert fields[0]['element_ref']==(m if location=='model' else r)['assumptions'][0]['assumption_id']
        assert fields[0]['path'].endswith('/0' if location in ('general','input','criterion') else '/evidence_version_id')
        assert counts(e)==(0,0,0)


@pytest.mark.parametrize('race',['evidence','membership','association','study'])
def test_commit_transaction_rechecks_all_pins_without_remote_io(config,race):
    e,c,r,m,record=config;b=body(config);original=e['store'].command
    def command(*args,**kwargs):
        with e['store'].connection(write=True) as db:
            if race=='evidence':
                db.execute('DROP TRIGGER immutable_evidence_update')
                changed=dict(record,title='Changed exact bytes')
                db.execute('UPDATE evidence SET payload=?',(json.dumps(changed),))
            elif race=='membership':db.execute('DELETE FROM memberships')
            elif race=='association':db.execute('DELETE FROM model_associations')
            elif race=='study':db.execute("UPDATE studies SET description='raced'")
        return original(*args,**kwargs)
    e['store'].command=command
    with pytest.raises(DomainError):c.commit(e['actor'],e['sid'],b)
    assert counts(e)==(0,0,0)


@pytest.mark.parametrize('bad',['contract','schema','version','unsupported','malformed','outage','status'])
@pytest.mark.parametrize('action',['preview','commit'])
def test_configuration_support_fails_closed_without_compatibility_or_allocation(config,bad,action):
    e,c,r,_,_=config;t=e['transport']
    b=dict(command_id=uid(),configuration_id=None,expected_revision=None,configuration=r,expected_preview_digest='0'*64)
    if bad=='contract':t.caps['contract_versions']=['1.1']
    elif bad=='schema':t.caps['schema_versions']=['1']
    elif bad=='version':t.caps['capabilities'][-1]['version']='2'
    elif bad=='unsupported':t.caps['capabilities'][-1]['supported']=False
    elif bad=='malformed':t.caps['extra']=True
    else:
        original=e['coord'].model.transport
        def unavailable(*args):
            status,result=original(*args)
            if bad=='outage':raise OSError('offline fixture')
            return 202,result
        e['coord'].model.transport=unavailable
    discovery=e['client'].get('/api/1/capabilities')
    assert discovery.status_code==200
    assert 'configuration_assumptions/1' in discovery.json()['data']['unavailable']
    with pytest.raises(DomainError) as error:
        if action=='preview':preview(config)
        else:c.commit(e['actor'],e['sid'],b)
    backend_error=bad in {'malformed','outage','status'}
    assert error.value.code==('backend_unavailable' if backend_error else 'unsupported_capability')
    assert error.value.status==(503 if backend_error else 422)
    assert not any(call[0]=='POST' for call in t.calls)
    assert counts(e)==(0,0,0)


@pytest.mark.parametrize('outcome',['supported','unsupported','malformed','outage'])
@pytest.mark.parametrize('action',['preview','commit','discovery'])
def test_configuration_capability_revocation_suppresses_success_and_failure(config,outcome,action):
    e,c,r,_,_=config;t=e['transport']
    if outcome=='unsupported':t.caps['capabilities']=[]
    if outcome=='malformed':t.caps['extra']=True
    def revoke(method,path,body):
        assert path.endswith('/capabilities')
        with e['store'].connection(write=True) as db:db.execute('DELETE FROM memberships')
        if outcome=='outage':raise OSError('offline after revocation')
    t.hook=revoke
    with pytest.raises(DomainError) as error:
        if action=='preview':preview(config)
        elif action=='discovery':c.native_capabilities(e['actor'],e['sid'])
        else:c.commit(e['actor'],e['sid'],dict(command_id=uid(),configuration_id=None,expected_revision=None,
            configuration=r,expected_preview_digest='0'*64))
    assert error.value.status==404 and error.value.code=='resource_not_found'
    assert not any(call[0]=='POST' for call in t.calls)
    assert counts(e)==(0,0,0)


def test_all_five_uses_sorted_closure_and_legacy_snapshot_shapes(config):
    e,c,r,m,record=config;records=[record,evidence(e),evidence(e),evidence(e),evidence(e)]
    r['assumptions'][0]['evidence_links'][0]['evidence_version_id']=records[1]['evidence_version_id']
    item=sample(D['LiteralRequest']);item['provenance']['evidence_version_ids']=[records[2]['evidence_version_id']];r['inputs']=[item]
    criterion=sample(D['Criterion']);criterion['evidence_version_ids']=[records[3]['evidence_version_id']];r['criteria']=[criterion]
    r['general_context_evidence_version_ids']=[records[4]['evidence_version_id']]
    p=preview(config)
    assert p['resolved_candidate']['evidence_snapshots']==sorted(records,key=lambda e:e['evidence_version_id'])
    for version in ('1','2'):
        legacy=sample(D['EvidenceRecord'+version]);legacy.update(study_id=e['sid'],evidence_version_id=uid(),evidence_id=uid())
        if version=='2':legacy['resource_scope']['study_id']=e['sid']
        with e['store'].connection(write=True) as db:
            db.execute('INSERT INTO evidence VALUES(?,?,?,?)',(legacy['evidence_version_id'],legacy['evidence_id'],e['sid'],json.dumps(legacy)))
        r['general_context_evidence_version_ids'].append(legacy['evidence_version_id'])
        actual=next(x for x in preview(config)['resolved_candidate']['evidence_snapshots'] if x['evidence_version_id']==legacy['evidence_version_id'])
        keys={'evidence_version_id','kind','content','source_refs'}|({'evidence_schema_version','resource_scope'} if version=='2' else set())
        assert actual=={k:legacy[k] for k in keys}


def test_public_dispatch_and_truthful_config_capabilities(config):
    e,_,r,_,_=config;client=e['client'];path='/api/1/studies/'+e['sid']+'/configurations'
    caps=client.get('/api/1/capabilities').json()['data']
    assert 'configuration/3' in caps['contract_versions'] and 'configuration_assumptions/1' in caps['engineering']
    p=client.post(path+'/preview',json=r)
    assert p.status_code==200,p.text
    result=client.post(path,json=body(config,p.json()['data']))
    assert result.status_code==201,result.text
    assert result.json()['data']['configuration']['schema_version']=='3'


@pytest.mark.parametrize('bad',['duplicate_id','root_owner','wrong_revision','bad_digest'])
def test_semantic_configuration_and_exact_model_reject(config,bad):
    e,c,r,m,_=config
    if bad=='duplicate_id':r['assumptions'].append(dict(r['assumptions'][0],statement='Other'))
    elif bad=='root_owner':m['assumptions'][0]['owner']=dict(kind='instance',instance_id=m['root_instance_id'])
    elif bad=='wrong_revision':m['model_revision_id']=uid()
    else:m['digest']='0'*64
    if bad not in ('bad_digest','duplicate_id'):m['digest']=digest({k:v for k,v in m.items() if k!='digest'})
    with pytest.raises(DomainError):preview(config)
    assert counts(e)==(0,0,0)


@pytest.mark.parametrize('race',['none','source','revoked_source'])
def test_result_source_value_projection_and_transaction_pin(binding_env,config,race):
    e=binding_env;r=deepcopy(e['request']);r.pop('evidence_version_ids')
    r.update(schema_version='3',assumptions=[],general_context_evidence_version_ids=[])
    model=e['case']['frozen']['model_snapshot'];caps=config[0]['transport'].caps
    calls=[]
    def transport(method,path,raw,headers):
        with sqlite3.connect(e['store'].path,timeout=0) as db:db.execute('BEGIN IMMEDIATE');db.rollback()
        if path.endswith('/capabilities'):data=caps
        elif '/revisions/' in path:data=model
        else:
            candidate=json.loads(raw)['configuration_candidate'];calls.append(deepcopy(candidate))
            data=dict(schema_version='2',model_revision_id=model['model_revision_id'],model_digest=model['digest'],
                candidate_digest=digest(candidate),compatible=True,diagnostics=[],required_capabilities=model['required_capabilities'],
                validator_identity='explicit-private-transport',input_interpretations=[dict(target=i['target'],conversion=dict(
                    policy='openmdao-linear-catalog-1',catalog_digest='a'*64,source_units=i['units'],destination_units=i['units'],
                    factor=1,destination_value=i['value'])) for i in candidate['inputs']])
        return 200,dict(schema_version='1',request_id=uid(),data=deepcopy(data))
    coord=Coordinator(e['store'],ModelingClient('http://private.invalid/modeling/1',b't'*32,transport=transport))
    c=Configurations(e['store'],coord);p=c.preview(e['actor'],e['sid'],r)[0]
    b=dict(command_id=uid(),configuration_id=None,expected_revision=None,configuration=r,expected_preview_digest=p['candidate_digest'])
    original=e['store'].command
    def command(*args,**kwargs):
        with e['store'].connection(write=True) as db:
            if race=='source':db.execute('UPDATE run_associations SET process_uuid=? WHERE run_id=?',(uid(),e['rid']))
            if race=='revoked_source':db.execute("UPDATE outbox SET state='uncertain' WHERE run_id=?",(e['rid'],))
        return original(*args,**kwargs)
    e['store'].command=command;before=counts(e)
    if race!='none':
        with pytest.raises(DomainError):c.commit(e['actor'],e['sid'],b)
        assert counts(e)==before
    else:
        saved=c.commit(e['actor'],e['sid'],b)['configuration']
        assert saved['inputs'][0]['value']==150
        assert saved['inputs'][0]['result_binding']['original_value']==150
        assert calls[-1]['schema_version']=='3' and all('result_binding' not in i for i in calls[-1]['inputs'])
        assert calls[-1]['required_capabilities']==model['required_capabilities']


@pytest.mark.parametrize('race',['evidence','association','reader'])
def test_current_replay_authorization_and_exact_evidence(config,race):
    e,c,r,m,record=config;b=body(config);saved=c.commit(e['actor'],e['sid'],b);before=counts(e)
    with e['store'].connection(write=True) as db:
        if race=='evidence':
            db.execute('DROP TRIGGER immutable_evidence_delete');db.execute('DELETE FROM evidence')
        elif race=='association':db.execute('DELETE FROM model_associations')
        else:db.execute("UPDATE memberships SET role='reader'")
    with pytest.raises(DomainError):c.commit(e['actor'],e['sid'],b)
    assert counts(e)==before


def test_expected_preview_family_cas_and_exact_unchanged_receipt(config):
    e,c,r,m,record=config;b=body(config);saved=c.commit(e['actor'],e['sid'],b)['configuration']
    with pytest.raises(DomainError,match='command_payload_conflict'):
        c.commit(e['actor'],e['sid'],dict(b,expected_preview_digest='0'*64))
    b.update(command_id=uid(),configuration_id=saved['configuration_id'],expected_revision=saved['configuration_revision_id'])
    second=c.commit(e['actor'],e['sid'],b)['configuration']
    assert second['parent_revision_id']==saved['configuration_revision_id']
    with pytest.raises(DomainError,match='stale_revision'):c.commit(e['actor'],e['sid'],dict(b,command_id=uid()))
    b.update(command_id=uid(),expected_revision=second['configuration_revision_id'],expected_preview_digest='0'*64)
    with pytest.raises(DomainError,match='reference_conflict'):c.commit(e['actor'],e['sid'],b)
    assert counts(e)==(2,1,0)


@pytest.mark.parametrize('race',['missing','altered','association','study','revoked'])
def test_preview_rechecks_after_private_compatibility(config,race):
    e,c,r,m,record=config
    def hook(method,path,body):
        if not path.endswith('/configuration-compatibility'):return
        with e['store'].connection(write=True) as db:
            if race=='missing':db.execute('DROP TRIGGER immutable_evidence_delete');db.execute('DELETE FROM evidence')
            elif race=='altered':
                db.execute('DROP TRIGGER immutable_evidence_update')
                db.execute('UPDATE evidence SET payload=?',(json.dumps(dict(record,title='Changed')),))
            elif race=='association':db.execute('DELETE FROM model_associations')
            elif race=='study':db.execute("UPDATE studies SET boundary='changed'")
            else:db.execute('DELETE FROM memberships')
    e['transport'].hook=hook
    with pytest.raises(DomainError):preview(config)
    assert counts(e)==(0,0,0)


@pytest.mark.parametrize('description',['An explicit new question\n\nWith its scope.',''])
def test_public_context_override_is_exact_digest_bound_and_replay_safe(config,description):
    from hyprn_mvp_app.scientific_configuration import project_scientific_configuration
    e,c,r,_,_=config;client=e['client'];path='/api/1/studies/'+e['sid']+'/configurations'
    original_study=deepcopy(e['store'].study(e['actor'],e['sid']))
    absent=client.post(path+'/preview',json=r).json()['data']
    r['context_override']=dict(schema_version='1',description=description,boundary='Retained boundary')
    r['notes']=['Exact notes\nwith line breaks']
    response=client.post(path+'/preview',json=r);assert response.status_code==200,response.text
    p=response.json()['data'];context=dict(description=description,boundary='Retained boundary',notes=r['notes'])
    assert p['resolved_candidate']['context_snapshot']==context
    assert p['request_digest']==digest(r) and p['request_digest']!=absent['request_digest']
    assert p['candidate_digest']!=absent['candidate_digest']
    b=body(config,p);response=client.post(path,json=b);assert response.status_code==201,response.text
    saved=response.json()['data'];actual=saved['configuration']
    assert actual['context_snapshot']==context and actual['context_source']==r['context_source']
    assert actual['digest']==digest({k:v for k,v in actual.items() if k!='digest'})
    private=project_scientific_configuration(actual)
    assert private['context_snapshot']==context and 'context_override' not in private
    assert 'context_override' not in actual and 'context_source' not in private
    assert client.post(path,json=b).json()['data']==saved
    receipt=e['store'].receipt(e['actor'],e['sid'],'configuration',b['command_id'])
    assert receipt['payload_digest']==digest(dict(major='1',scope=e['sid'],category='configuration',payload={k:v for k,v in b.items() if k!='command_id'}))
    changed=deepcopy(b);changed['configuration']['context_override']['description']='Altered under same command'
    response=client.post(path,json=changed)
    assert response.status_code==409 and response.json()['error']['code']=='command_payload_conflict'
    changed['command_id']=uid();response=client.post(path,json=changed)
    assert response.status_code==409 and response.json()['error']['code']=='reference_conflict'
    assert counts(e)==(1,1,0) and e['store'].study(e['actor'],e['sid'])==original_study
    assert c.read(e['actor'],e['sid'],actual['configuration_revision_id'])==saved


@pytest.mark.parametrize('failure',['stale','revoked','foreign','race'])
def test_override_does_not_bypass_context_authority_or_transaction_cas(config,failure):
    e,c,r,_,_=config;r['context_override']=dict(schema_version='1',description='Edited',boundary='')
    b=body(config)
    if failure=='foreign':b['configuration']['study_id']=uid()
    elif failure=='stale':b['configuration']['context_source']['expected_study_revision']='stale'
    elif failure=='revoked':
        with e['store'].connection(write=True) as db:db.execute('DELETE FROM memberships')
    else:
        original=e['store'].command
        def command(*args,**kwargs):
            with e['store'].connection(write=True) as db:db.execute("UPDATE studies SET description='Raced'")
            return original(*args,**kwargs)
        e['store'].command=command
    response=e['client'].post('/api/1/studies/'+e['sid']+'/configurations',json=b)
    assert response.status_code in (404,409),response.text
    assert counts(e)==(0,0,0)


class NoModelService:
    """A replayed configuration is a historical read: it never reaches the model service."""
    def __getattr__(self,name):raise AssertionError('Model service reached during replay: '+name)


# Replay rechecks the retained model with the pure ``modeling.checked_model`` and the
# association with ``Store.model_association``. Neither needs the Coordinator, so replay works
# with no model service object at all; current authorization and evidence still apply.
def test_committed_replay_is_local_and_never_reaches_the_model_service(config):
    e,c,r,m,record=config;b=body(config);saved=c.commit(e['actor'],e['sid'],b);before=counts(e)
    offline=Configurations(e['store'],NoModelService())
    assert offline.commit(e['actor'],e['sid'],b)==saved and counts(e)==before
    with e['store'].connection(write=True) as db:db.execute('DELETE FROM model_associations')
    with pytest.raises(DomainError) as error:offline.commit(e['actor'],e['sid'],b)
    assert (error.value.code,error.value.status)==('resource_not_found',404) and counts(e)==before


@pytest.mark.parametrize('tamper',['digest','revision'])
def test_replayed_retained_model_integrity_is_unavailable_backend(config,tamper):
    e,c,r,m,record=config;b=body(config);c.commit(e['actor'],e['sid'],b);before=counts(e)
    with e['store'].connection(write=True) as db:
        result=json.loads(db.execute("SELECT result FROM receipts WHERE category='configuration' AND command_id=?",(b['command_id'],)).fetchone()[0])
        model=result['model_snapshot']
        if tamper=='digest':model['digest']='0'*64
        else:
            model['model_revision_id']=uid();model['digest']=digest({k:v for k,v in model.items() if k!='digest'})
        db.execute("UPDATE receipts SET result=? WHERE category='configuration' AND command_id=?",(json.dumps(result),b['command_id']))
    with pytest.raises(DomainError) as error:Configurations(e['store'],NoModelService()).commit(e['actor'],e['sid'],b)
    assert (error.value.code,error.value.status)==('backend_unavailable',503) and counts(e)==before
