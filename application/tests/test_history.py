"""History API reads immutable recorded evidence, never live modeling or execution."""
import base64
import copy
import json
import pytest
from fastapi.testclient import TestClient
from hyprn_mvp_app.api import create_app
from hyprn_mvp_app.auth import Auth
from hyprn_mvp_app.store import Store, uid
from test_submission import submission, accepted

from conftest import LOOPBACK_ORIGIN as ORIGIN

class Offline:
    def __getattr__(self, name):
        raise AssertionError('History contacted modeling: '+name)

def client(store, actor):
    auth=Auth(store,ORIGIN)
    # Test fixture provisions a real authenticated actor for the existing study.
    provisioned=auth.provision('history-owner','correct horse battery staple')
    with store.connection(write=True) as db:
        db.execute('UPDATE memberships SET actor_id=? WHERE actor_id=?',(provisioned,actor))
    c=TestClient(create_app(store,auth,Offline()),base_url=ORIGIN)
    session=c.post('/api/1/session',json=dict(username='history-owner',password='correct horse battery staple'),headers={'Origin':ORIGIN})
    c.headers.update({'Origin':ORIGIN,'X-CSRF-Token':session.json()['data']['csrf_token']})
    return c,provisioned

def recording(submission):
    service,store,actor,sid,revision,native=submission
    launch=native.launch
    def capture(bundle,request):
        record=launch(bundle,request)
        native.bundle=copy.deepcopy(bundle)
        native.record={**record,'request':copy.deepcopy(request),'bundle':copy.deepcopy(bundle),
            'results':None,'assessment':None,'artifacts':{'result.json':b'raw retained failure\n'},
            'errors':[dict(code='missing_results',partial=True)]}
        return record
    def read_record(request,association):
        assert request==native.record['request']
        assert association=={k:native.record[k] for k in ('store_uuid','process_uuid')}
        return copy.deepcopy(native.record)
    native.launch=capture;native.read_record=read_record
    run=accepted(submission);service.dispatch(run['run_id'])
    return run


@pytest.mark.parametrize('state',['prepared','preparation_failed'])
def test_history_list_and_detail_agree_on_preclaim_state(submission,state):
    service,store,actor,sid,_,native=submission;run=accepted(submission)
    if state=='preparation_failed':
        def invalid(*args):raise ValueError('Controlled invalid preparation')
        service.prepare=invalid
    service.dispatch(run['run_id'],prepare_only=True)
    c,actor=client(store,actor);path=f'/api/1/studies/{sid}/runs'
    detail=c.get(path+'/'+run['run_id']).json()['data']
    listed=c.get(path).json()['data']
    assert listed[0]['state']==detail['state']==state
    assert native.launches==0

def test_recorded_history_survives_restart_offline_and_copy_without_run(submission):
    service,store,actor,sid,revision,native=submission
    run=recording(submission)
    c,actor=client(Store(store.path),actor)
    url=f'/api/1/studies/{sid}/runs'
    response=c.get(url)
    assert response.status_code==200,response.text
    assert [r['run_id'] for r in response.json()['data']]==[run['run_id']]
    detail=c.get(url+'/'+run['run_id']).json()['data']
    history=detail['history']
    assert history['configuration']==json.loads(native.bundle['files']['configuration.json'])
    assert history['model_snapshot']==json.loads(native.bundle['files']['model.json'])
    assert history['context']==history['configuration']['context_snapshot']
    assert history['evidence']==history['configuration']['evidence_snapshots']
    assert history['errors']==[dict(code='missing_results',partial=True)]
    raw=next(a for a in history['artifacts'] if a['name']=='result.json')
    assert c.get(url+'/'+run['run_id']+'/artifacts/'+raw['artifact_id']).content==b'raw retained failure\n'
    sources=[a for a in history['artifacts'] if a['role']=='source']
    assert sources
    for artifact in sources:
        assert c.get(url+'/'+run['run_id']+'/artifacts/'+artifact['artifact_id']).content==native.bundle['files'][artifact['name']]
    copied=copy.deepcopy(history['configuration']);copied['inputs'][0]['value']=999
    current=c.get(f'/api/1/studies/{sid}').json()['data']
    edited=c.patch(f'/api/1/studies/{sid}',json=dict(command_id=uid(),expected_revision=current['revision'],description='Changed current context'))
    assert edited.status_code==200
    note=c.post(f'/api/1/studies/{sid}/evidence',json=dict(command_id=uid(),scope=None,kind='note',content='New evidence',source_refs=[]))
    assert note.status_code==201
    restarted=TestClient(create_app(Store(store.path),Auth(store,ORIGIN),Offline()),base_url=ORIGIN)
    restarted.cookies.update(c.cookies)
    assert restarted.get(url+'/'+run['run_id']).json()['data']==detail
    assert c.get(url+'/'+run['run_id']).json()['data']==detail
    public=json.dumps(detail)
    assert native.record['process_uuid'] not in public and native.record['store_uuid'] not in public
    assert native.launches==1

def test_completed_results_and_assessment_are_copied_exactly_not_recomputed(submission):
    from hyprn_mvp_app.history import History
    service,store,actor,sid,revision,native=submission
    run=recording(submission)
    model=json.loads(native.bundle['files']['model.json'])
    definitions={d['definition_version_id']:d for d in model['definitions']}
    targets=[dict(instance_id=i['instance_id'],port_id=p['port_id']) for i in model['instances']
             for p in definitions[i['definition_version_id']]['ports'] if p['direction']=='output']
    native.record['results']=dict(schema_version='1',run_id=run['run_id'],bundle_digest=native.record['request']['bundle_digest'],
        execution=dict(state='finished',exit_code=0,message='retained'),
        convergence=dict(state='not_applicable',diagnostics_ref=None),
        optimization=dict(termination='not_applicable',feasibility='not_applicable'),
        completeness=dict(expected=2,available=2,failed=0,unavailable=0),
        outputs=[dict(target=t,value=v,units='',availability='available',reason=None,producer_completed=True,assigned=True) for t,v in zip(targets,[49,7])],
        criteria=[],applicability=dict(state='unassessed',evidence_refs=[]),artifacts=[])
    native.record['assessment']=dict(version='fixed-threshold-1',evaluator_sha256='a'*64)
    native.record['errors']=[]
    service.hydrate(actor,sid,run['run_id'])
    history=History(Store(store.path)).read(actor,sid,run['run_id'])
    assert history['results']==native.record['results'] and history['assessment']==native.record['assessment']
    # Repeated hydration cannot silently replace an already complete assessment.
    native.record['results']['outputs'][0]['value']=0
    with pytest.raises(ValueError,match='cannot change'):service.hydrate(actor,sid,run['run_id'])
    assert History(store).read(actor,sid,run['run_id'])==history

def test_history_and_artifacts_authorize_every_read_and_replay(submission):
    service,store,actor,sid,revision,native=submission
    run=recording(submission);c,actor=client(store,actor)
    url=f'/api/1/studies/{sid}/runs';detail=c.get(url+'/'+run['run_id']).json()['data']
    aid=detail['history']['artifacts'][0]['artifact_id']
    other=store.create_study(actor,uid(),'Other study')['study_id']
    assert c.get(f"/api/1/studies/{other}/runs/{run['run_id']}").status_code==404
    assert c.get(f"/api/1/studies/{other}/runs/{run['run_id']}/artifacts/{aid}").status_code==404
    with store.connection(write=True) as db:db.execute('DELETE FROM memberships WHERE actor_id=? AND study_id=?',(actor,sid))
    for path in (url,url+'/'+run['run_id'],url+'/'+run['run_id']+'/artifacts/'+aid):
        assert c.get(path).status_code==404
    assert c.post(url,json=dict(command_id=run['command_id'],configuration_revision_id=revision)).status_code==404
    with pytest.raises(Exception,match='resource_not_found'):service.hydrate(actor,sid,run['run_id'])

def test_history_cursor_is_chronological_and_study_scoped(submission):
    service,store,actor,sid,revision,native=submission
    first=recording(submission)
    # The second run remains pending; listing must not cause dispatch/preparation.
    second=accepted(submission);c,actor=client(store,actor)
    url=f'/api/1/studies/{sid}/runs'
    page=c.get(url+'?limit=1').json()
    assert page['data'][0]['run_id']==first['run_id'] and page['next_cursor']==first['run_id']
    following=c.get(url+'?limit=1&cursor='+page['next_cursor']).json()
    assert following['data'][0]['run_id']==second['run_id'] and following['next_cursor'] is None
    assert c.get(url+'?cursor='+uid()).status_code==404
    assert c.get(url+'?limit=0').status_code==400
    assert native.launches==1

@pytest.mark.parametrize('kind',['source','missing_file','request','store','process','result','artifact','snapshot'])
def test_corrupt_retained_data_is_explicit_partial_error(submission,kind):
    service,store,actor,sid,revision,native=submission
    run=recording(submission);c,actor=client(store,actor);rid=run['run_id']
    url=f'/api/1/studies/{sid}/runs/{rid}'
    aid=c.get(url).json()['data']['history']['artifacts'][0]['artifact_id']
    with store.connection(write=True) as db:
        payload=json.loads(db.execute('SELECT payload FROM outbox WHERE run_id=?',(rid,)).fetchone()[0])
        if kind=='source':payload['bundle']['files']['model.json']=base64.b64encode(b'{}').decode()
        if kind=='missing_file':payload['bundle']['files'].pop('context.json')
        if kind=='request':payload['request']['scope']=uid()
        if kind in ('store','process'):db.execute('UPDATE run_associations SET '+kind+'_uuid=? WHERE run_id=?',(uid(),rid))
        if kind=='result':payload['history']['results']={'outputs':[0]}
        if kind=='artifact':payload['history']['artifacts'][0]['bytes']='Zm9yZ2Vk'
        if kind=='snapshot':payload['frozen']['configuration']['inputs'][0]['value']=0
        db.execute('UPDATE outbox SET payload=? WHERE run_id=?',(json.dumps(payload),rid))
    detail=c.get(url).json()['data']['history']
    assert detail['errors']==[dict(code='corrupt_retained_record',partial=True)]
    assert detail['results'] is None and detail['configuration'] is None
    assert c.get(url+'/artifacts/'+aid).status_code==409
    assert native.launches==1

@pytest.mark.parametrize('version',['1','2'])
def test_retained_version_hydration_uses_exact_association_without_launch(tmp_path,version):
    from test_results import retained_record
    from hyprn_mvp_app.execution import Submissions
    from hyprn_mvp_app.store import digest
    bundle=retained_record(version);cfg=json.loads(bundle['files']['configuration.json'])
    model=json.loads(bundle['files']['model.json']);sid=cfg['study_id'];actor=uid()
    store=Store(tmp_path/'history.sqlite')
    with store.connection(write=True) as db:
        db.execute('INSERT INTO studies VALUES(?,?,?,?,?)',(sid,uid(),'History','today','today'))
        db.execute('INSERT INTO memberships VALUES(?,?,?)',(sid,actor,'owner'))
        frozen=dict(configuration=cfg,model_snapshot=model,study_revision=uid())
        db.execute('INSERT INTO configurations VALUES(?,?,?,?)',(cfg['configuration_revision_id'],cfg['configuration_id'],sid,json.dumps(frozen)))
    class Native:
        def read_record(self,request,association):
            assert request==self.record['request'] and association=={k:self.record[k] for k in ('store_uuid','process_uuid')}
            return copy.deepcopy(self.record)
        def __getattr__(self,name):raise AssertionError('History called native '+name)
    native=Native();service=Submissions(store,Offline(),native)
    run=service.submit(actor,sid,dict(command_id=uid(),configuration_revision_id=cfg['configuration_revision_id']))
    bundle['manifest']['run_id']=run['run_id'];bundle['manifest']['bundle_digest']=digest({k:v for k,v in bundle['manifest'].items() if k!='bundle_digest'})
    request=dict(run_id=run['run_id'],scope=sid,command_id=run['command_id'],
        payload_digest=store.receipt(actor,sid,'run',run['command_id'])['payload_digest'],bundle_digest=bundle['manifest']['bundle_digest'])
    native.record=dict(store_uuid='scoped-native-store',process_uuid=uid(),process_state='finished',exit_status=300,
        request=request,bundle=bundle,results=None,assessment=None,artifacts={'result.json':b'invalid raw output'},errors=[dict(code='missing_results',partial=True)])
    with store.connection(write=True) as db:
        payload=json.loads(db.execute('SELECT payload FROM outbox WHERE run_id=?',(run['run_id'],)).fetchone()[0])
        payload.update(request=request,bundle={**bundle,'files':{p:base64.b64encode(raw).decode() for p,raw in bundle['files'].items()}})
        db.execute("UPDATE outbox SET state='recorded',payload=? WHERE run_id=?",(json.dumps(payload),run['run_id']))
        db.execute('UPDATE run_associations SET store_uuid=?,process_uuid=? WHERE run_id=?',(native.record['store_uuid'],native.record['process_uuid'],run['run_id']))
    before=copy.deepcopy(payload)
    service.hydrate(actor,sid,run['run_id'])
    c,actor=client(Store(store.path),actor)
    history=c.get(f"/api/1/studies/{sid}/runs/{run['run_id']}").json()['data']['history']
    assert history['bundle']['schema_version']==version and history['configuration']==cfg
    assert history['model_snapshot']==model and history['context']['description']=='Retained context'
    with store.connection() as db:
        after=json.loads(db.execute('SELECT payload FROM outbox WHERE run_id=?',(run['run_id'],)).fetchone()[0])
    assert after['bundle']==before['bundle'] and after['request']==before['request']

@pytest.mark.parametrize('kind',['request','association','bundle','result','artifact'])
def test_wrong_native_read_is_never_recorded(submission,kind):
    service,store,actor,sid,revision,native=submission
    run=recording(submission)
    if kind=='request':native.record['request']['scope']=uid()
    if kind=='association':native.record['process_uuid']=uid()
    if kind=='bundle':native.record['bundle']['files']['context.json']=b'wrong'
    if kind=='result':native.record['results']=dict(run_id=uid(),bundle_digest='f'*64)
    if kind=='artifact':native.record['artifacts']={'../bad':b'wrong'}
    # A hostile/mistaken native response cannot retarget a stored request.
    native.read_record=lambda *args:copy.deepcopy(native.record)
    with pytest.raises(ValueError):service.hydrate(actor,sid,run['run_id'])
    assert service.read(actor,sid,run['run_id'])['state']=='recorded' and native.launches==1

@pytest.mark.parametrize('code',['unsupported_record_version','corrupt_retained_record','missing_artifacts'])
def test_partial_native_error_preserves_raw_artifact_without_current_model_fallback(submission,code):
    service,store,actor,sid,revision,native=submission
    run=recording(submission)
    native.record.update(bundle=None,results=None,assessment=None,errors=[dict(code=code,partial=True)])
    service.hydrate(actor,sid,run['run_id'])
    c,actor=client(store,actor);url=f"/api/1/studies/{sid}/runs/{run['run_id']}"
    history=c.get(url).json()['data']['history']
    assert history['errors']==[dict(code=code,partial=True)] and history['configuration'] is None
    assert history['results'] is None and len(history['artifacts'])==1
    assert c.get(url+'/artifacts/'+history['artifacts'][0]['artifact_id']).content==b'raw retained failure\n'

def test_hydration_rechecks_authorization_after_native_read(submission):
    from hyprn_mvp_app.store import DomainError
    service,store,actor,sid,revision,native=submission
    run=recording(submission)
    def revoked(*args):
        with store.connection(write=True) as db:db.execute('DELETE FROM memberships WHERE actor_id=? AND study_id=?',(actor,sid))
        return copy.deepcopy(native.record)
    native.read_record=revoked
    with pytest.raises(DomainError):service.hydrate(actor,sid,run['run_id'])
    assert native.launches==1

def test_hydration_does_not_dispatch_pending_or_uncertain_work(submission):
    from hyprn_mvp_app.store import DomainError
    service,store,actor,sid,revision,native=submission
    run=accepted(submission)
    with pytest.raises(DomainError,match='history_not_recorded'):service.hydrate(actor,sid,run['run_id'])
    service.dispatch(run['run_id'],prepare_only=True)
    with store.connection(write=True) as db:db.execute("UPDATE outbox SET state='uncertain' WHERE run_id=?",(run['run_id'],))
    with pytest.raises(DomainError,match='history_not_recorded'):service.hydrate(actor,sid,run['run_id'])
    assert native.launches==0


def test_run_list_name_uses_exact_revision_not_family_head_offline(submission):
    service,store,actor,sid,revision,native=submission
    run=accepted(submission)
    with store.connection(write=True) as db:
        original=json.loads(db.execute('SELECT payload FROM configurations WHERE configuration_revision_id=?',(revision,)).fetchone()[0])
        newer=copy.deepcopy(original);config=newer['configuration']
        config.update(configuration_revision_id=uid(),parent_revision_id=revision,name='Renamed current family')
        from hyprn_mvp_app.store import digest
        config['digest']=digest({k:v for k,v in config.items() if k!='digest'})
        db.execute('INSERT INTO configurations VALUES(?,?,?,?)',(config['configuration_revision_id'],config['configuration_id'],sid,json.dumps(newer)))
        db.execute('INSERT INTO configuration_families VALUES(?,?,?)',(config['configuration_id'],sid,config['configuration_revision_id']))
    c,actor=client(Store(store.path),actor)
    response=c.get(f'/api/1/studies/{sid}/runs?limit=1')
    assert response.status_code==200,response.text
    listed=response.json()['data'][0]
    assert listed['configuration_name']==original['configuration']['name']!='Renamed current family'
    assert listed['configuration_revision_id']==revision and listed['run_id']==run['run_id']
    from jsonschema import Draft202012Validator
    from pathlib import Path
    # Validated against the whole public contract so its internal references resolve.
    spec=json.loads((Path(__file__).resolve().parents[2]/'contracts/hyprn-mvp.openapi.yaml').read_text())
    validator=Draft202012Validator({**spec,'$ref':'#/components/schemas/RunHistoryItem'})
    validator.validate(listed)
    old=dict(listed);old.pop('configuration_name');validator.validate(old)
    missing=dict(listed,configuration_name=None);validator.validate(missing)
    assert native.launches==0
    with store.connection(write=True) as db:db.execute('DELETE FROM memberships WHERE study_id=? AND actor_id=?',(sid,actor))
    assert c.get(f'/api/1/studies/{sid}/runs').status_code in (403,404)
