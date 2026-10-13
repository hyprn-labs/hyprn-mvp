"""Real HTTP/Auth/Store and fresh genuine native archive bytes, no web native work.

The guarded native fixture creates synthetic retained scientific results without
executing candidates. Dispatcher/HTTP integration and UI belong to later tasks.
"""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator,FormatChecker

import checks
from hyprn_mvp_app.api import create_app
from hyprn_mvp_app.auth import Auth
from hyprn_mvp_app.computational_export import ComputationalRecords,LIMITS
from hyprn_mvp_app.execution import Submissions
from hyprn_mvp_app.modeling import validate
from hyprn_mvp_app.store import Store,uid

ROOT=Path(__file__).resolve().parents[2]
ORIGIN='http://127.0.0.1:19999'


@pytest.fixture(scope='session')
def material():
    scope=checks.fixture.allocate_scope(checks.fixture.new_scope())
    command=[scope.interpreter,'-B',str(ROOT/'deployment/tests/api_c_fixture.py')]
    result=subprocess.run(command,cwd=ROOT,env=checks.fixture.clean_environment(scope),capture_output=True,text=True)
    evidence=checks.PROJECTION_SCOPE.root/'evidence'
    for name,text in [('stdout',result.stdout),('stderr',result.stderr)]:
        (evidence/('native-material.'+name+'.log')).write_text(text)
    (evidence/'native-material-command.json').write_text(json.dumps(dict(command=command,scope=str(scope.root),exit=result.returncode)))
    assert result.returncode==0,result.stderr
    value=json.loads(result.stdout.splitlines()[-1]);path=Path(value['material'])
    scope=checks.fixture.Scope(**{**json.loads((scope.root/'scope.json').read_text()),'root':scope.root})
    checks.fixture.scoped_path(scope,'artifacts/material')
    assert path==scope.root/'artifacts/material'
    return path


@pytest.fixture
def api(tmp_path,material,monkeypatch):
    shutil.copytree(material,tmp_path/'material')
    directory=tmp_path/'material';data=json.loads((directory/'fixture.json').read_text())
    store=Store(directory/'application.sqlite');auth=Auth(store,ORIGIN)
    # Only fixture-owned artifact locations change when cloning a fresh test DB.
    with store.connection(write=True) as db:
        for row in db.execute('SELECT request_id,kind FROM computational_record_requests').fetchall():
            if row['request_id']==data['failed_id']:continue
            path=directory/'computational-records'/row['request_id']/('record.zip' if row['kind']=='create' else 'preview.aiida')
            db.execute('UPDATE computational_record_requests SET artifact_path=? WHERE request_id=?',(str(path),row['request_id']))
    calls=[]
    def forbidden(*args,**kwargs):calls.append('native-or-processing');raise AssertionError('Web must only enqueue/read')
    monkeypatch.setattr(ComputationalRecords,'process_one',forbidden)
    monkeypatch.setattr(Submissions,'submit',forbidden)
    class OfflineModel:
        @staticmethod
        def call(actor,sid,method,path,body=None,**kwargs):
            if method=='GET' and path=='/capabilities':
                from hyprn_mvp_app.store import DomainError
                raise DomainError('backend_unavailable',503,outcome='unknown')
            return forbidden(actor,sid,method,path,body,**kwargs)
    client=TestClient(create_app(store,auth,OfflineModel()),base_url=ORIGIN)
    session=client.post('/api/1/session',json=dict(username='owner',password='correct horse battery staple'),headers={'Origin':ORIGIN})
    assert session.status_code==200,session.text
    client.headers.update({'Origin':ORIGIN,'X-CSRF-Token':session.json()['data']['csrf_token']})
    yield dict(data,client=client,store=store,calls=calls,directory=directory)
    assert calls==[]
    assert not any(n.split('.')[0] in {'aiida','openmdao','openturns'} for n in sys.modules)


def path(a,suffix):return '/api/1/studies/'+a['sid']+'/'+suffix
def post(a,body=None):return a['client'].post(path(a,'computational-record-previews'),json=body or dict(command_id=uid(),selected_run_ids=[a['rid']]))
def status(a,rid):return a['client'].get(path(a,'computational-records/'+rid))
def download(a,rid):return a['client'].get(path(a,'computational-records/'+rid+'/download'))
def rows(a):
    with a['store'].connection() as db:return [tuple(r) for r in db.execute('SELECT * FROM computational_record_requests')]


def test_enqueue_only_exact_replay_conflict_and_receipt(api):
    a=api;body=dict(command_id=uid(),selected_run_ids=[a['rid']]);before=rows(a)
    with a['store'].connection() as db:originals=[tuple(r) for r in db.execute('SELECT * FROM outbox')]
    response=post(a,body);assert response.status_code==202,response.text
    first=response.json()['data'];assert first['state']=='queued'
    assert post(a,body).json()['data']==first and len(rows(a))==len(before)+1
    receipt=a['client'].get(path(a,'commands/'+body['command_id']),params={'category':'computational_record_preview'})
    assert receipt.status_code==200 and receipt.json()['data']['result']==first
    assert post(a,body|{'selected_run_ids':[a['ancestor']]}).status_code==409
    assert status(a,first['request_id']).json()['data']==first
    assert download(a,first['request_id']).status_code==409
    with a['store'].connection() as db:assert originals==[tuple(r) for r in db.execute('SELECT * FROM outbox')]


@pytest.mark.parametrize('state',['queued','building','reviewable','ready','failed'])
def test_status_is_side_effect_free_and_closed_in_each_state(api,state):
    a=api;rid=a['ready']['request_id'] if state=='ready' else a['preview']['request_id']
    if state=='queued':
        queued=post(a);assert queued.status_code==202
        rid=queued.json()['data']['request_id']
    elif state=='building':
        row=a['building_row'];rid=row['request_id']
        with a['store'].connection(write=True) as db:
            db.execute('INSERT INTO computational_record_requests ('+','.join(row)+') VALUES ('+','.join('?' for _ in row)+')',tuple(row.values()))
    elif state=='failed':rid=a['failed_id']
    before=rows(a);response=status(a,rid)
    assert response.status_code==200,response.text
    data=response.json()['data'];assert data['state']==state and rows(a)==before
    validate('RecordRequest',data)
    assert set(data)=={'schema_version','request_id','kind','state','selected_run_ids','preview','error','download'}
    if state=='failed':
        assert data['error']['code']=='unsafe_export' and data['download'] is None
        assert '/private/' not in response.text and 'API_TOKEN' not in response.text
    if state in ('queued','building'):assert data['preview'] is None
    if state!='ready':assert download(a,rid).status_code==409


def test_create_requires_reviewed_digest_replays_and_does_not_build(api):
    a=api;body=dict(a['create_body'],command_id=uid());route=path(a,'computational-records')
    assert a['client'].post(route,json=body|{'expected_preview_digest':'0'*64}).status_code==409
    response=a['client'].post(route,json=body);assert response.status_code==202,response.text
    assert response.json()['data']['kind']=='create' and response.json()['data']['state']=='queued'
    assert a['client'].post(route,json=body).json()['data']==response.json()['data']
    receipt=a['client'].get(path(a,'commands/'+body['command_id']),params={'category':'computational_record_create'})
    assert receipt.status_code==200 and receipt.json()['data']['result']==response.json()['data']
    assert a['client'].post(route,json=body|{'preview_id':uid()}).status_code==409


def test_download_exact_genuine_package_fixed_filename_and_hash(api):
    a=api;ready=a['ready'];rid=ready['request_id'];before=rows(a)
    response=download(a,rid);assert response.status_code==200,response.text
    raw=(a['directory']/'computational-records'/rid/'record.zip').read_bytes()
    assert response.content==raw and hashlib.sha256(raw).hexdigest()==ready['download']['sha256']
    assert response.headers['content-type']=='application/zip'
    assert response.headers['content-disposition']=='attachment; filename="hyprn-mvp-computational-record.zip"'
    assert response.headers['x-content-sha256']==ready['download']['sha256']
    assert response.headers['cache-control']=='no-store' and rows(a)==before


@pytest.mark.parametrize('change',['hash','missing','ancestor','foreign_ancestor','revocation'])
def test_download_and_current_closure_fail_closed(api,change):
    a=api;rid=a['ready']['request_id'];file=a['directory']/'computational-records'/rid/'record.zip'
    if change=='hash':file.chmod(0o600);file.write_bytes(b'corrupt')
    elif change=='missing':file.unlink()
    else:
        with a['store'].connection(write=True) as db:
            if change=='ancestor':db.execute("UPDATE outbox SET payload='{}' WHERE run_id=?",(a['ancestor'],))
            elif change=='foreign_ancestor':
                foreign=uid();db.execute('INSERT INTO studies VALUES(?,?,?,?,?)',(foreign,uid(),'Foreign','',''))
                db.execute('UPDATE run_associations SET study_id=? WHERE run_id=?',(foreign,a['ancestor']))
            else:db.execute('DELETE FROM memberships WHERE study_id=?',(a['sid'],))
    response=download(a,rid);assert response.status_code in (404,409,422),response.text
    assert len(response.content)<4096 and str(a['directory']) not in response.text
    if change in ('ancestor','foreign_ancestor','revocation'):
        assert status(a,rid).status_code in (404,409,422)
        receipt=a['client'].get(path(a,'commands/'+a['create_body']['command_id']),params={'category':'computational_record_create'})
        assert receipt.status_code in (404,409,422)
        assert post(a,a['preview_body']).status_code in (404,409,422)


@pytest.mark.parametrize('bad',['empty','duplicate','over','extra','native','uppercase','string','null'])
def test_closed_preview_rejects_malformed_selection_before_allocation(api,bad):
    a=api;body=dict(command_id=uid(),selected_run_ids=[a['rid']]);before=rows(a)
    if bad=='empty':body['selected_run_ids']=[]
    elif bad=='duplicate':body['selected_run_ids']*=2
    elif bad=='over':body['selected_run_ids']=[uid() for _ in range(17)]
    elif bad in ('extra','native'):body['process_uuid' if bad=='native' else 'value']=uid()
    elif bad=='uppercase':body['selected_run_ids']=[a['rid'].upper()]
    elif bad=='string':body['selected_run_ids']=a['rid']
    else:body['selected_run_ids']=None
    response=post(a,body);assert response.status_code==400,response.text
    assert rows(a)==before


@pytest.mark.parametrize('change',['unknown_preview','queued_preview','extra','bad_digest','bad_id','query'])
def test_create_rejects_unreviewed_or_forged_requests(api,change):
    a=api;body=dict(a['create_body'],command_id=uid());route=path(a,'computational-records');before=rows(a)
    expected=400
    if change=='unknown_preview':body['preview_id']=uid();expected=404
    elif change=='queued_preview':
        queued=post(a);assert queued.status_code==202
        body['preview_id']=queued.json()['data']['request_id'];before=rows(a);expected=409
    elif change=='extra':body['archive_path']='/private/forged.zip'
    elif change=='bad_digest':body['expected_preview_digest']='wrong'
    elif change=='bad_id':body['preview_id']='native:1'
    else:route+='?native_id=1'
    response=a['client'].post(route,json=body)
    assert response.status_code==expected,response.text
    assert rows(a)==before


def test_acknowledgement_loss_restart_and_expired_session(api):
    a=api;body=dict(command_id=uid(),selected_run_ids=[a['ancestor'],a['rid']])
    first=post(a,body);assert first.status_code==202,first.text
    assert first.json()['data']['selected_run_ids']==sorted(body['selected_run_ids'])
    restarted=TestClient(create_app(Store(a['store'].path),Auth(a['store'],ORIGIN),None),base_url=ORIGIN)
    restarted.cookies.update(a['client'].cookies);restarted.headers.update(a['client'].headers)
    receipt=restarted.get(path(a,'commands/'+body['command_id']),params={'category':'computational_record_preview'})
    assert receipt.status_code==200 and receipt.json()['data']['result']==first.json()['data']
    assert restarted.post(path(a,'computational-record-previews'),json=body).json()['data']==first.json()['data']
    assert restarted.get(path(a,'computational-records/'+a['ready']['request_id']+'/download')).status_code==200
    with a['store'].connection(write=True) as db:db.execute('UPDATE sessions SET expires_at=0')
    assert restarted.get(path(a,'computational-records/'+a['ready']['request_id'])).status_code==401


@pytest.mark.parametrize('route',['computational-record-previews','computational-records'])
def test_mutation_requires_session_csrf_current_writer(api,route):
    a=api;body=dict(command_id=uid(),selected_run_ids=[a['rid']]) if route.endswith('previews') else dict(a['create_body'],command_id=uid())
    url=path(a,route);before=rows(a)
    assert TestClient(a['client'].app,base_url=ORIGIN).post(url,json=body,headers={'Origin':ORIGIN,'X-Actor-ID':a['actor']}).status_code==401
    assert a['client'].post(url,json=body,headers={'X-CSRF-Token':'bad'}).status_code==403
    assert a['client'].post(url,json=body,headers={'Origin':'http://foreign.invalid'}).status_code==403
    with a['store'].connection(write=True) as db:db.execute("UPDATE memberships SET role='reader' WHERE study_id=?",(a['sid'],))
    assert a['client'].post(url,json=body).status_code==403
    assert status(a,a['ready']['request_id']).status_code==200 and download(a,a['ready']['request_id']).status_code==200
    assert rows(a)==before


def test_foreign_unknown_and_unauthenticated_reads_do_not_reach_native(api):
    a=api;other=a['store'].create_study(a['actor'],uid(),'Other')['study_id']
    for suffix in ['computational-records/'+a['ready']['request_id'],'computational-records/'+a['ready']['request_id']+'/download']:
        assert TestClient(a['client'].app,base_url=ORIGIN).get(path(a,suffix)).status_code==401
        assert a['client'].get(path(a,suffix).replace(a['sid'],other)).status_code==404
        assert a['client'].get(path(a,suffix).replace(a['ready']['request_id'],uid())).status_code==404
        assert a['client'].get(path(a,suffix)+'?native_id='+uid()).status_code==400
    assert post(a,dict(command_id=uid(),selected_run_ids=[uid()])).status_code==404


@pytest.mark.parametrize('global_cap',[False,True])
def test_atomic_pending_caps_and_same_command_replay(api,global_cap):
    a=api;body=dict(command_id=uid(),selected_run_ids=[a['rid']]);first=post(a,body)
    assert first.status_code==202,first.text
    if global_cap:
        with a['store'].connection(write=True) as db:
            for _ in range(31):
                sid=uid();db.execute('INSERT INTO studies VALUES(?,?,?,?,?)',(sid,uid(),'Other','',''))
                db.execute('INSERT INTO computational_record_requests VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    (uid(),sid,a['actor'],'preview',uid(),'a'*64,'[]',None,None,'queued',0,'{}',None,None,None))
    else:
        for _ in range(7):assert post(a).status_code==202
    before=rows(a);response=post(a)
    assert response.status_code==413 and response.json()['error']['code']=='limit_exceeded'
    assert post(a,body).json()['data']==first.json()['data'] and rows(a)==before


def test_generated_routes_schemas_capabilities_and_types_match(api,tmp_path):
    a=api;output=tmp_path/'openapi.json'
    subprocess.run([sys.executable,'-B',str(ROOT/'application/generate_contract.py'),'--output',str(output)],check=True,capture_output=True)
    assert output.read_bytes()==(ROOT/'contracts/hyprn-mvp.openapi.yaml').read_bytes()
    spec=json.loads(output.read_text());responses=[]
    responses.append(('/studies/{study_id}/computational-record-previews','post',post(a)))
    responses.append(('/studies/{study_id}/computational-records','post',a['client'].post(path(a,'computational-records'),json=dict(a['create_body'],command_id=uid()))))
    responses.append(('/studies/{study_id}/computational-records/{request_id}','get',status(a,a['ready']['request_id'])))
    responses.append(('/studies/{study_id}/commands/{command_id}','get',a['client'].get(path(a,'commands/'+a['create_body']['command_id']),params={'category':'computational_record_create'})))
    capabilities=a['client'].get('/api/1/capabilities');responses.append(('/capabilities','get',capabilities))
    assert 'computational_record/1' in capabilities.json()['data']['contract_versions']
    assert capabilities.json()['data']['limits']['computational_record']==LIMITS
    for route,method,response in responses:
        assert response.status_code<300,response.text
        schema=spec['paths'][route][method]['responses'][str(response.status_code)]['content']['application/json']['schema']
        assert not list(Draft202012Validator(dict(components=spec['components'],**schema),format_checker=FormatChecker()).iter_errors(response.json()))
    for suffix,name in [('computational-record-previews','RecordPreviewRequest'),('computational-records','RecordCreateRequest')]:
        assert spec['paths']['/studies/{study_id}/'+suffix]['post']['requestBody']['content']['application/json']['schema']=={'$ref':'#/components/schemas/'+name}
    types=tmp_path/'contract.ts'
    subprocess.run([sys.executable,'-B',str(ROOT/'ui/generate_types.py'),'--input',str(output),'--output',str(types)],check=True,capture_output=True)
    assert types.read_bytes()==(ROOT/'ui/src/contract.ts').read_bytes()


@pytest.mark.parametrize('interpreter',['/usr/bin/python3',checks.fixture.APPROVED_PYTHON])
def test_api_c_refuses_unreviewed_interpreter(monkeypatch,interpreter):
    from dataclasses import replace
    monkeypatch.setattr(checks.fixture,'scope_from_environment',lambda:replace(checks.PROJECTION_SCOPE,interpreter=interpreter))
    monkeypatch.setattr(checks.sys,'executable',interpreter)
    with pytest.raises(ValueError,match='reviewed interpreter'):checks.contracts_child('api-c')
