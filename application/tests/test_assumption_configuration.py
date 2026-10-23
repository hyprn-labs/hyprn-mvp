"""Configuration 6 assumption and evidence contracts through real application boundaries and isolated stores.

New configurations carry no criteria and no approach binding; they pin an exact Model4 version.
Private compatibility is an explicit transport fixture, not native numerical proof.
"""
from copy import deepcopy
import json

import pytest
from ae_criteria_free_config import configuration6, signed
from criteria_free import bind_case, insert_case, record_run
from test_assumption_authoring import env, evidence, revision, statement, sample, D
from hyprn_mvp_app.configuration import Configurations
from hyprn_mvp_app.store import DomainError, digest, uid


@pytest.fixture
def config(env):
    return configuration6(env)


def preview(config):
    e,c,r,_,_=config
    return c.preview(e['actor'],e['sid'],r)[0]


def body(config,p=None):
    return dict(command_id=uid(),configuration_id=None,expected_revision=None,
        configuration=deepcopy(config[2]),expected_preview_digest=(p or preview(config))['candidate_digest'])


def counts(env):
    with env['store'].connection() as db:
        return tuple(db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] for table in ('configurations','configuration_families','outbox'))


@pytest.mark.parametrize('action',['preview','commit'])
def test_duplicate_input_evidence_is_field_error_before_save(config,action):
    e,c,r,m,record=config
    item=r['inputs'][0];eid=record['evidence_version_id']
    item['provenance']['evidence_version_ids']=[eid]
    good=preview(config)
    # Same version cited by input, assumption and general context is valid.
    assert good['resolved_candidate']['evidence_snapshots']==[record]
    assert 'criteria' not in good['resolved_candidate']
    citations=item['provenance']['evidence_version_ids']
    citations.append(eid)
    bad=deepcopy(good)
    bad['resolved_candidate']['inputs'][0]['provenance']=deepcopy(item['provenance'])
    bad['candidate_digest']=digest(bad['resolved_candidate'])
    with pytest.raises(DomainError) as error:
        if action=='preview':preview(config)
        else:c.commit(e['actor'],e['sid'],body(config,bad))
    assert error.value.code=='invalid_configuration' and error.value.status==422
    assert error.value.fields==[dict(path='/inputs/0/provenance/evidence_version_ids/1',
        code='duplicate_evidence',message='This evidence version is already cited in this field.',
        element_ref=item['target']['port_id'])]
    assert counts(e)==(0,0,0)
    # Independent worker still rejects malformed input after application repair.
    from hyprn_mvp_integration.worker import verify_assumption_closure
    invalid=dict(bad['resolved_candidate'],configuration_id=uid(),configuration_revision_id=uid(),parent_revision_id=None)
    with pytest.raises(ValueError,match='Distinct bounded UUID'):
        verify_assumption_closure(invalid,m)
    citations.pop()
    saved=c.commit(e['actor'],e['sid'],body(config,good))
    assert saved['configuration']['schema_version']=='6' and 'criteria' not in saved['configuration']
    assert saved['configuration']['inputs'][0]['provenance']['evidence_version_ids']==[eid]


@pytest.mark.parametrize('action',['preview','commit'])
@pytest.mark.parametrize('citation',['evidence','none'])
def test_new_configuration_refuses_criteria_and_their_evidence_citations(config,action,citation):
    # Study criteria live in the study brief; a new configuration carries none, so neither a
    # criterion nor a criterion evidence citation can be saved through it.
    e,c,r,_,record=config
    criterion=sample(D['Criterion'])
    criterion['evidence_version_ids']=[record['evidence_version_id']] if citation=='evidence' else []
    r['criteria']=[criterion]
    e['transport'].calls.clear()
    with pytest.raises(DomainError) as error:
        if action=='preview':preview(config)
        else:c.commit(e['actor'],e['sid'],dict(command_id=uid(),configuration_id=None,expected_revision=None,
            configuration=r,expected_preview_digest='0'*64))
    assert (error.value.code,error.value.status)==('invalid_request',400) and error.value.fields
    assert counts(e)==(0,0,0) and e['transport'].calls==[]
    response=e['client'].post('/api/1/studies/'+e['sid']+'/configurations/preview',json=r)
    assert response.status_code==400 and response.json()['error']['code']=='invalid_request'
    assert counts(e)==(0,0,0) and e['transport'].calls==[]


@pytest.mark.parametrize('version',['1','2','3','4'])
@pytest.mark.parametrize('action',['preview','commit'])
def test_new_writes_refuse_earlier_request_versions_without_allocation(config,version,action):
    e,c,request,model,_=config
    if version=='1':
        candidate=sample(D['ConfigurationCandidate1'])
        candidate.update(study_id=e['sid'],model_id=model['model_id'],model_revision_id=model['model_revision_id'],
            context_snapshot=dict(description=e['study']['description'],boundary=e['study']['boundary'],notes=[]))
    else:
        candidate=deepcopy(request);candidate.update(schema_version=version,criteria=[])
        if version=='2':
            candidate.pop('assumptions');candidate.pop('general_context_evidence_version_ids')
            candidate['evidence_version_ids']=[]
        if version=='4':candidate['approach_selection']=None
    e['transport'].calls.clear()
    commit=dict(command_id=uid(),configuration_id=None,expected_revision=None,
        configuration=candidate,**({} if version=='1' else {'expected_preview_digest':'0'*64}))
    with pytest.raises(DomainError) as error:
        if action=='preview':c.preview(e['actor'],e['sid'],candidate)
        else:c.commit(e['actor'],e['sid'],commit)
    assert (error.value.code,error.value.status)==('unsupported_record_version',422)
    route='/api/1/studies/'+e['sid']+'/configurations'+('/preview' if action=='preview' else '')
    response=e['client'].post(route,json=candidate if action=='preview' else commit)
    assert response.status_code==422 and response.json()['error']['code']=='unsupported_record_version'
    assert counts(e)==(0,0,0) and e['transport'].calls==[]


@pytest.mark.parametrize('action',['preview','commit'])
def test_configuration6_requires_a_model4_version_without_allocation(config,action):
    e,c,request,_,_=config;t=e['transport']
    earlier=revision(t.draft);t.revisions[earlier['model_revision_id']]=earlier
    assert earlier['schema_version']=='2'
    request.update(model_id=e['mid'],model_revision_id=earlier['model_revision_id'])
    t.calls.clear()
    with pytest.raises(DomainError) as error:
        if action=='preview':preview(config)
        else:c.commit(e['actor'],e['sid'],dict(command_id=uid(),configuration_id=None,expected_revision=None,
            configuration=request,expected_preview_digest='0'*64))
    assert (error.value.code,error.value.status)==('invalid_configuration',422)
    assert counts(e)==(0,0,0)
    assert not any(path.endswith('/configuration-compatibility') for _,path,_ in t.calls)


def test_full_closure_contradictory_relationships_and_immutable_save(config):
    e,c,r,m,record=config;eid=record['evidence_version_id']
    r['assumptions'][0]['evidence_links'].append(dict(evidence_version_id=eid,relation='challenges'))
    p=preview(config);candidate=p['resolved_candidate']
    assert counts(e)==(0,0,0) and candidate['evidence_snapshots']==[record]
    assert candidate['assumptions']==r['assumptions'] and candidate['general_context_evidence_version_ids']==[eid]
    b=body(config,p);saved=c.commit(e['actor'],e['sid'],b)
    assert saved['schema_version']=='9' and saved['configuration']['schema_version']=='6'
    assert not {'criteria','approach_binding'}&set(saved['configuration']) and 'approach_closure' not in saved
    assert saved['model_snapshot']==m and saved['configuration']['evidence_snapshots']==[record]
    assert c.commit(e['actor'],e['sid'],b)==saved and counts(e)==(1,1,0)
    before=deepcopy(saved);r['general_context_evidence_version_ids']=[];r['assumptions']=[]
    assert preview(config)['resolved_candidate']['evidence_snapshots']==[record]
    m['assumptions']=[];signed(m)
    assert preview(config)['resolved_candidate']['evidence_snapshots']==[]
    assert c.read(e['actor'],e['sid'],saved['configuration']['configuration_revision_id'])==before


@pytest.mark.parametrize('location',['model','assumption','input','general'])
@pytest.mark.parametrize('foreign',[False,True])
def test_unavailable_exact_reference_diagnostics_preview_and_commit_zero_allocation(config,location,foreign):
    e,c,r,m,_=config
    eid=evidence(e,sid=uid(),title='PRIVATE FOREIGN')['evidence_version_id'] if foreign else uid()
    if location=='model':m['assumptions'][0]['evidence_links'][0]['evidence_version_id']=eid
    elif location=='assumption':r['assumptions'][0]['evidence_links'][0]['evidence_version_id']=eid
    elif location=='general':r['general_context_evidence_version_ids']=[eid]
    else:r['inputs'][0]['provenance']['evidence_version_ids']=[eid]
    signed(m)
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
        assert fields[0]['path'].endswith('/0' if location in ('general','input') else '/evidence_version_id')
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


@pytest.mark.parametrize('bad',['contract','schema','resolved_version','resolved_unsupported','criteria_free_version',
    'criteria_free_unsupported','criteria_free_absent','malformed','outage','status'])
@pytest.mark.parametrize('action',['preview','commit'])
def test_configuration_support_fails_closed_without_compatibility_or_allocation(config,bad,action):
    e,c,r,_,_=config;t=e['transport']
    b=dict(command_id=uid(),configuration_id=None,expected_revision=None,configuration=r,expected_preview_digest='0'*64)
    entry=lambda name:next(cap for cap in t.caps['capabilities'] if cap['id']==name)
    if bad=='contract':t.caps['contract_versions']=['1.1']
    elif bad=='schema':t.caps['schema_versions']=['1']
    elif bad=='resolved_version':entry('resolved_configuration')['version']='2'
    elif bad=='resolved_unsupported':entry('resolved_configuration')['supported']=False
    elif bad=='criteria_free_version':entry('criteria_free_configuration')['version']='2'
    elif bad=='criteria_free_unsupported':entry('criteria_free_configuration')['supported']=False
    elif bad=='criteria_free_absent':t.caps['capabilities'].remove(entry('criteria_free_configuration'))
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
    if not bad.startswith('criteria_free'):
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


def test_all_four_uses_sorted_closure_and_legacy_snapshot_shapes(config):
    e,c,r,m,record=config;records=[record,evidence(e),evidence(e),evidence(e)]
    r['assumptions'][0]['evidence_links'][0]['evidence_version_id']=records[1]['evidence_version_id']
    r['inputs'][0]['provenance']['evidence_version_ids']=[records[2]['evidence_version_id']]
    r['general_context_evidence_version_ids']=[records[3]['evidence_version_id']]
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
    # Discovery advertises only the configuration version a preview accepts.
    assert 'configuration/6' in caps['contract_versions'] and 'configuration_assumptions/1' in caps['engineering']
    assert not {'configuration/2','configuration/3'} & set(caps['contract_versions'])
    assert 'model/4' in caps['contract_versions']
    p=client.post(path+'/preview',json=r)
    assert p.status_code==200,p.text
    assert p.json()['data']['schema_version']=='8' and 'approach_closure' not in p.json()['data']
    result=client.post(path,json=body(config,p.json()['data']))
    assert result.status_code==201,result.text
    assert result.json()['data']['schema_version']=='9'
    assert result.json()['data']['configuration']['schema_version']=='6'


@pytest.mark.parametrize('bad',['duplicate_id','root_owner','wrong_revision','bad_digest'])
def test_semantic_configuration_and_exact_model_reject(config,bad):
    e,c,r,m,_=config
    if bad=='duplicate_id':r['assumptions'].append(dict(r['assumptions'][0],statement='Other'))
    elif bad=='root_owner':m['assumptions'][0]['owner']=dict(kind='instance',instance_id=m['root_instance_id'])
    elif bad=='wrong_revision':m['model_revision_id']=uid()
    else:m['digest']='0'*64
    if bad not in ('bad_digest','duplicate_id'):signed(m)
    with pytest.raises(DomainError):preview(config)
    assert counts(e)==(0,0,0)


@pytest.mark.parametrize('race',['none','source','revoked_source'])
def test_result_source_value_projection_and_transaction_pin(config,race):
    e,c,r,m,_=config
    source=bind_case('chain',e['sid']);insert_case(e['store'],e['sid'],source)
    rid,results=record_run(e['store'],e['actor'],e['sid'],source)
    item=r['inputs'][0]
    r['inputs'][0]=dict(kind='run_result',target=item['target'],source_run_id=rid,source_output=results['outputs'][0]['target'],
        expected_results_digest=digest(results),provenance=item['provenance'])
    calls=e['transport'].calls;p=c.preview(e['actor'],e['sid'],r)[0]
    b=dict(command_id=uid(),configuration_id=None,expected_revision=None,configuration=r,expected_preview_digest=p['candidate_digest'])
    original=e['store'].command
    def command(*args,**kwargs):
        with e['store'].connection(write=True) as db:
            if race=='source':db.execute('UPDATE run_associations SET process_uuid=? WHERE run_id=?',(uid(),rid))
            if race=='revoked_source':db.execute("UPDATE outbox SET state='uncertain' WHERE run_id=?",(rid,))
        return original(*args,**kwargs)
    e['store'].command=command;before=counts(e)
    if race!='none':
        with pytest.raises(DomainError):c.commit(e['actor'],e['sid'],b)
        assert counts(e)==before
    else:
        saved=c.commit(e['actor'],e['sid'],b)['configuration']
        assert saved['inputs'][0]['value']==results['outputs'][0]['value']
        assert saved['inputs'][0]['result_binding']['original_value']==results['outputs'][0]['value']
        candidate=[body for _,path,body in calls if path.endswith('/configuration-compatibility')][-1]['configuration_candidate']
        assert candidate['schema_version']=='5' and 'criteria' not in candidate
        assert all('result_binding' not in i for i in candidate['inputs'])
        assert candidate['required_capabilities']==m['required_capabilities']


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


def test_configuration_saved_time_is_atomic_replay_stable_and_outside_scientific_bytes(config):
    from datetime import datetime
    e, owner, _, _, _ = config
    command = body(config)
    saved = owner.commit(e['actor'], e['sid'], command)
    rows, _ = owner.read_page(e['actor'], e['sid'], summary=True)
    row = next(r for r in rows if r['configuration_revision_id'] ==
               saved['configuration']['configuration_revision_id'])
    assert datetime.fromisoformat(row['saved_at']).tzinfo is not None
    assert 'saved_at' not in saved['configuration']
    assert owner.commit(e['actor'], e['sid'], command) == saved
    again, _ = owner.read_page(e['actor'], e['sid'], summary=True)
    assert again == rows
