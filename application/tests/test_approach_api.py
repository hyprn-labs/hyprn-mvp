"""Actual HTTP public approach operations against synthetic off-cloud stores."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import pytest
from jsonschema import Draft202012Validator, FormatChecker
from fastapi.testclient import TestClient
from test_assumptions_evidence_api import api, generated, ORIGIN, SCOPE, guard, ROOT
from test_approach_closure import sample,D
from hyprn_mvp_app.store import uid
from test_approach_service import env, run_env

def test_http_linked_model_source_and_history_are_exact_during_modeling_outage(env,tmp_path):
    from hyprn_mvp_app.api import create_app
    from hyprn_mvp_app.auth import Auth
    from test_approach_service import link
    from hyprn_mvp_app.store import digest
    import base64,hashlib
    e=env;auth=Auth(e['store'],ORIGIN);actor=auth.provision('approach_owner','correct horse battery staple')
    with e['store'].connection(write=True) as db:db.execute('UPDATE memberships SET actor_id=? WHERE study_id=?',(actor,e['sid']))
    e['actor']=actor
    content,m,_,_=link(e)
    canary=tmp_path/'candidate-ran'
    source=("from pathlib import Path\nPath("+repr(str(canary))+").touch()\n").encode()
    sha=hashlib.sha256(source).hexdigest()
    m['source_files']=[dict(encoding='base64',media_type='text/x-python',bytes=base64.b64encode(source).decode(),sha256=sha)]
    m['definitions'][0]['source_refs']=[sha];m['digest']=digest({k:v for k,v in m.items() if k!='digest'})
    e['models'][m['model_id'],m['model_revision_id']]=deepcopy(m)
    client=TestClient(create_app(e['store'],auth,e['coord'].model),base_url=ORIGIN)
    session=client.post('/api/1/session',json=dict(username='approach_owner',password='correct horse battery staple'),headers={'Origin':ORIGIN})
    client.headers.update({'Origin':ORIGIN,'X-CSRF-Token':session.json()['data']['csrf_token']});e['client']=client
    d,_=write(e,dict(schema_version='1',expected_revision=None,content=content));saved,_=save(e,d)
    original=saved.json()['data'];vid=original['saved']['version']['approach_version_id']
    assert not canary.exists()
    assert original['saved']['closure']['models'][0]==m
    def unavailable(*args,**kwargs):raise AssertionError('Historical route called current modeling service')
    e['coord'].model.transport=unavailable
    assert client.get(url(e,'/versions/'+vid)).json()['data']==original['saved']
    assert client.get(url(e,'/versions')).status_code==200
    restored=post(e,'/draft/restore',dict(schema_version='1',command_id=uid(),expected_revision=original['draft_revision'],approach_version_id=vid))
    assert restored.status_code==200
    assert client.get(url(e)).json()['data']['draft']['content']==content
    assert not canary.exists()

def test_http_usage_cursor_and_receipt_query_are_typed(api,generated):
    d,command=write(api);saved,_=save(api,d);vid=saved.json()['data']['saved']['version']['approach_version_id']
    endpoint=url(api,'/versions/'+vid+'/usage')
    for params in ({'cursor':json.dumps({'kind':'run','resource_id':uid()})},{'limit':20}):
        r=api['client'].get(endpoint,params=params);assert r.status_code==200
        assert_http(generated,'/studies/{study_id}/approach/versions/{version_id}/usage','get',r)
    for params in ({'cursor':json.dumps({'kind':'native','resource_id':uid()})},{'case_id':'latest'},{'case_id':uid()},{'limit':101}):
        r=api['client'].get(endpoint,params=params);assert r.status_code in (400,404)
        assert_shape(generated,'Error',r.json())
    path='/api/1/studies/'+api['sid']+'/commands/'+command['command_id']
    for suffix in ('?category=approach_draft&category=approach_draft','?category=approach_draft&native=true'):
        r=api['client'].get(path+suffix);assert r.status_code==400;assert_shape(generated,'Error',r.json())


def url(e,suffix=''):return '/api/1/studies/'+e['sid']+'/approach'+suffix
def body():return dict(schema_version='1',expected_revision=None,content=sample(D['ApproachContent1']))
def post(e,suffix,b):return e['client'].post(url(e,suffix),json=b)
def assert_shape(generated,name,value):
    Draft202012Validator({**generated,'$ref':'#/components/schemas/'+name},format_checker=FormatChecker()).validate(value)
def assert_http(generated,path,method,response):
    schema=generated['paths'][path][method]['responses'][str(response.status_code)]['content']['application/json']['schema']
    Draft202012Validator({**generated,**schema},format_checker=FormatChecker()).validate(response.json())
def write(e,b=None):
    b=b or body();preview=post(e,'/preview',b);assert preview.status_code==200,preview.text
    request=dict(b,command_id=uid(),expected_preview_digest=preview.json()['data']['preview_digest'])
    response=post(e,'/draft',request);assert response.status_code==200,response.text
    return response.json()['data'],request
def save(e,d):
    preview=post(e,'/preview',dict(schema_version='1',expected_revision=d['revision'],content=d['content']))
    b=dict(schema_version='1',command_id=uid(),expected_revision=d['revision'],expected_preview_digest=preview.json()['data']['preview_digest'])
    r=post(e,'/versions',b);assert r.status_code==201,r.text
    return r,b
def counts(e):
    with e['store'].connection() as db:return tuple(db.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in ('approach_drafts','approach_versions','receipts'))

def test_http_complete_lifecycle_exact_read_restore_and_receipts(api,generated):
    c=api['client'];before=counts(api)
    r=c.get(url(api));assert r.status_code==200;assert_http(generated,'/studies/{study_id}/approach','get',r)
    assert r.json()['data']==dict(draft=None,latest_version=None)
    assert counts(api)==before
    d,request=write(api);assert_shape(generated,'ApproachDraft1',d)
    saved,command=save(api,d);assert_http(generated,'/studies/{study_id}/approach/versions','post',saved)
    value=saved.json()['data'];vid=value['saved']['version']['approach_version_id']
    r=c.get(url(api,'/versions/'+vid));assert r.status_code==200;assert r.json()['data']==value['saved']
    assert_http(generated,'/studies/{study_id}/approach/versions/{version_id}','get',r)
    for category,b,expected in [('approach_draft',request,d),('approach_version',command,value)]:
        r=c.get('/api/1/studies/'+api['sid']+'/commands/'+b['command_id'],params={'category':category})
        assert r.status_code==200;assert r.json()['data']['result']==expected
        assert_shape(generated,'PublicReceipt',r.json()['data'])
    restored=post(api,'/draft/restore',dict(schema_version='1',command_id=uid(),expected_revision=value['draft_revision'],approach_version_id=vid))
    assert restored.status_code==200;assert restored.json()['data']['base_version_id']==vid
    assert c.get(url(api,'/versions/'+vid)).json()['data']==value['saved']
    assert c.get(url(api,'/versions/'+vid+'/usage')).json()['data']==dict(items=[],next_cursor=None)

def test_http_unknown_outcome_retry_original_and_concurrent_command(api):
    d,request=write(api)
    # Ignore first result to model a lost response; original ID/payload is retried.
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses=list(pool.map(lambda _:post(api,'/draft',request),range(2)))
    assert all(r.status_code==200 and r.json()['data']==d for r in responses)
    assert counts(api)[:2]==(1,0)
    changed=deepcopy(request);changed['content']['question']='Changed'
    r=post(api,'/draft',changed);assert r.status_code==409
    assert r.json()['error']['code']=='command_payload_conflict'

@pytest.mark.parametrize('kind',['unknown','duplicate','limit','cursor','cursor_duplicate'])
def test_http_query_strictness(api,kind,generated):
    queries={'unknown':'?extra=1','duplicate':'?limit=1&limit=2','limit':'?limit=0','cursor':'?cursor=bad','cursor_duplicate':'?cursor=%7B%22version_number%22%3A1%2C%22version_number%22%3A2%7D'}
    r=api['client'].get(url(api,'/versions')+queries[kind])
    assert r.status_code==400
    assert_shape(generated,'Error',r.json())

def test_http_version_cursor_and_no_read_writes(api,generated):
    d,_=write(api);first,_=save(api,d)
    d=api['client'].get(url(api)).json()['data']['draft'];second,_=save(api,d)
    before=counts(api)
    page=api['client'].get(url(api,'/versions'),params={'limit':1})
    assert page.status_code==200;assert_http(generated,'/studies/{study_id}/approach/versions','get',page)
    page=page.json()['data'];assert len(page['items'])==1 and page['next_cursor']
    next_page=api['client'].get(url(api,'/versions'),params={'limit':1,'cursor':json.dumps(page['next_cursor'])})
    assert next_page.status_code==200
    assert next_page.json()['data']['items'][0]['approach_version_id']==first.json()['data']['saved']['version']['approach_version_id']
    assert counts(api)==before

@pytest.mark.parametrize('route',['','/preview','/draft','/versions','/draft/restore'])
def test_http_auth_and_csrf(api,route,generated):
    c=api['client']
    unauth=TestClient(c.app,base_url=ORIGIN)
    r=unauth.get(url(api)) if route=='' else unauth.post(url(api,route),json=body(),headers={'Origin':ORIGIN})
    assert r.status_code==401;assert_shape(generated,'Error',r.json())
    if route:
        r=c.post(url(api,route),json=body(),headers={'X-CSRF-Token':'wrong'})
        assert r.status_code==403;assert_shape(generated,'Error',r.json())

def test_http_stale_reader_foreign_and_revoked_access(api,generated):
    d,b=write(api)
    stale=deepcopy(b);stale['command_id']=uid()
    r=post(api,'/draft',stale);assert r.status_code==409;assert_shape(generated,'Error',r.json())
    assert r.json()['error']['current_revision']==d['revision']
    foreign=api['client'].get('/api/1/studies/'+uid()+'/approach')
    assert foreign.status_code==404
    with api['store'].connection(write=True) as db:db.execute('UPDATE memberships SET role=? WHERE actor_id=?',('reader',api['actor']))
    assert api['client'].get(url(api)).status_code==200
    assert post(api,'/draft',b).status_code==403
    with api['store'].connection(write=True) as db:db.execute('DELETE FROM memberships WHERE actor_id=?',(api['actor'],))
    assert api['client'].get(url(api)).status_code==404
    receipt='/api/1/studies/'+api['sid']+'/commands/'+b['command_id']
    assert api['client'].get(receipt,params={'category':'approach_draft'}).status_code==404

def test_http_closed_body_ids_and_no_native_forwarding(api,generated):
    for patch in ({'native_options':{}},{'content':{}},{'expected_revision':'latest'}):
        r=post(api,'/preview',body()|patch)
        assert r.status_code==400;assert_shape(generated,'Error',r.json())
    assert api['client'].get(url(api,'/versions/latest')).status_code==400

def test_generated_approach_routes_use_concrete_schemas_and_frozen_union(generated):
    schemas=generated['components']['schemas']
    expected=json.loads(json.dumps(D['FrozenConfiguration']).replace('#/$defs/','#/components/schemas/'))
    assert schemas['FrozenConfiguration']==expected
    paths=generated['paths'];base='/studies/{study_id}/approach'
    expected={'':('get',None,'ApproachState2'),'/preview':('post','ApproachPreviewRequestRead2','ApproachPreviewRead3'),
        '/draft':('post','ApproachDraftWriteRead2','ApproachDraftRead2'),'/draft/restore':('post','ApproachRestore1','ApproachDraftRead2'),
        '/versions':('post','ApproachVersionSave1','ApproachVersionSavedRead3'),
        '/versions/{version_id}':('get',None,'ApproachSavedRead3'),
        '/versions/{version_id}/usage':('get',None,'ApproachUsagePage1')}
    for suffix,(method,request,response) in expected.items():
        op=paths[base+suffix][method]
        if request:assert op['requestBody']['content']['application/json']['schema']=={'$ref':'#/components/schemas/'+request}
        success=op['responses']['201' if suffix=='/versions' else '200']['content']['application/json']['schema']
        assert success['properties']['data']=={'$ref':'#/components/schemas/'+response}
        for status in ('400','401','403','404','409','413','422','429','500','503'):assert status in op['responses']
    assert not any('resolve' in p for p in paths if '/approach' in p)
    receipt=schemas['PublicReceipt']['properties']['result']['anyOf']
    assert {'$ref':'#/components/schemas/ApproachCommandResultRead2'} in receipt

def test_generated_types_include_approach_and_preserve_legacy_branches(generated):
    from importlib.util import spec_from_file_location,module_from_spec
    spec=spec_from_file_location('approach_ts',ROOT/'ui/generate_types.py');module=module_from_spec(spec);spec.loader.exec_module(module)
    schemas=generated['components']['schemas']
    assert 'ApproachDraft1' in module.ts(schemas['ApproachCommandResult1'])
    assert 'FrozenConfiguration4' in module.ts(schemas['FrozenConfiguration'])
    assert 'FrozenConfigurationLegacy' in module.ts(schemas['FrozenConfiguration'])


def test_polish_http_new_lifecycle_and_old_history_use_generated_contracts(api,generated):
    from test_approach_service import polish_content,polish_evidence
    old,_=write(api);old_saved,_=save(api,old);old_value=old_saved.json()['data']
    c=polish_content();polish_evidence(api,c)
    d,command=write(api,dict(schema_version='2',expected_revision=old_value['draft_revision'],content=c))
    assert d['content']==c and d['updated_by']==api['actor']
    p=post(api,'/preview',dict(schema_version='2',expected_revision=d['revision'],content=c))
    assert p.status_code==200;assert_http(generated,'/studies/{study_id}/approach/preview','post',p)
    save_command=dict(schema_version='1',command_id=uid(),expected_revision=d['revision'],expected_preview_digest=p.json()['data']['preview_digest'])
    result=post(api,'/versions',save_command);assert result.status_code==201,result.text
    assert_http(generated,'/studies/{study_id}/approach/versions','post',result)
    data=result.json()['data'];vid=data['saved']['version']['approach_version_id']
    for suffix in ('','/versions','/versions/'+vid):
        r=api['client'].get(url(api,suffix));assert r.status_code==200,r.text
        path='/studies/{study_id}/approach'+('/versions/{version_id}' if suffix.startswith('/versions/') else suffix)
        assert_http(generated,path,'get',r)
    for category,b in [('approach_draft',command),('approach_version',save_command)]:
        r=api['client'].get('/api/1/studies/'+api['sid']+'/commands/'+b['command_id'],params={'category':category})
        assert r.status_code==200;assert_shape(generated,'PublicReceipt',r.json()['data'])
    assert post(api,'/versions',save_command).json()['data']==data
    restored=post(api,'/draft/restore',dict(schema_version='1',command_id=uid(),expected_revision=data['draft_revision'],approach_version_id=vid))
    assert restored.status_code==200 and restored.json()['data']['content']==c
    assert_http(generated,'/studies/{study_id}/approach/draft/restore','post',restored)
    before=counts(api)
    with api['store'].connection(write=True) as db:db.execute('DELETE FROM memberships')
    assert api['client'].get(url(api,'/versions/'+vid)).status_code==404
    assert post(api,'/draft',command).status_code==404
    assert counts(api)==before

@pytest.mark.parametrize('patch',[{'authenticated_actor':'forged'},{'schema_version':'3'},{'created_by':'forged'}])
def test_polish_http_claims_are_closed_inert_data(api,patch):
    from test_approach_service import polish_content
    before=counts(api);c=polish_content();c['original_question'].update(patch)
    r=post(api,'/preview',dict(schema_version='2',expected_revision=None,content=c))
    assert r.status_code==400 and counts(api)==before


@pytest.mark.parametrize('current', [False, True])
def test_http_run_basis_preserves_exact_source_and_projects_only_historical_views(
    run_env, generated, current
):
    from hyprn_mvp_app.api import create_app
    from hyprn_mvp_app.auth import Auth
    from hyprn_mvp_app.store import canonical, digest
    from test_approach_service import content

    e = run_env
    rid, result = e['source'](current=current)
    auth = Auth(e['store'], ORIGIN)
    actor = auth.provision('basis-owner', 'correct horse battery staple')
    with e['store'].connection(write=True) as db:
        db.execute('UPDATE memberships SET actor_id=? WHERE study_id=?', (actor, e['sid']))
    client = TestClient(create_app(e['store'], auth, None), base_url=ORIGIN)
    session = client.post('/api/1/session', json=dict(username='basis-owner',
        password='correct horse battery staple'), headers={'Origin': ORIGIN})
    client.headers.update({'Origin': ORIGIN, 'X-CSRF-Token': session.json()['data']['csrf_token']})
    e['client'] = client
    c = content()
    c['basis_refs'] = [dict(kind='run', run_id=rid, reason='Prior observation', relation='context')]
    request = dict(schema_version='1', expected_revision=None, content=c)
    preview = post(e, '/preview', request)
    assert preview.status_code == 200, preview.text
    assert_http(generated, '/studies/{study_id}/approach/preview', 'post', preview)
    draft, _ = write(e, request)
    response, command = save(e, draft)
    assert_http(generated, '/studies/{study_id}/approach/versions', 'post', response)
    saved = response.json()['data']['saved']
    version = saved['version']['approach_version_id']
    closure = saved['closure']
    assert closure['schema_version'] == ('4' if current else '1')
    shown = closure['run_contexts'][0]['results']
    assert shown['schema_version'] == ('2' if current else '1')
    assert not {'convergence', 'optimization', 'completeness', 'applicability'} & shown.keys()
    with e['store'].connection() as db:
        original = json.loads(
            db.execute(
                'SELECT payload FROM approach_versions WHERE approach_version_id=?', (version,)
            ).fetchone()[0]
        )
        outbox = db.execute('SELECT payload FROM outbox WHERE run_id=?', (rid,)).fetchone()[0]
    assert original['closure']['run_contexts'][0]['results'] == result
    if current:
        assert shown == result
        assert 'record_view' not in closure
    else:
        assert shown['record_view']['source_sha256'] == digest(result)
        assert closure['record_view']['source_sha256'] == digest(original['closure'])
        assert closure['record_view']['view_sha256'] == digest(
            {k: v for k, v in closure.items() if k != 'record_view'}
        )
    read = client.get(url(e, '/versions/' + version))
    assert read.status_code == 200 and read.json()['data'] == saved
    assert_http(generated, '/studies/{study_id}/approach/versions/{version_id}', 'get', read)
    receipt = client.get('/api/1/studies/' + e['sid'] + '/commands/' + command['command_id'],
        params={'category': 'approach_version'})
    assert receipt.status_code == 200, receipt.text
    assert receipt.json()['data']['result'] == response.json()['data']
    assert_shape(generated, 'PublicReceipt', receipt.json()['data'])
    with e['store'].connection() as db:
        assert (
            db.execute('SELECT payload FROM outbox WHERE run_id=?', (rid,)).fetchone()[0] == outbox
        )
        assert canonical(
            json.loads(
                db.execute(
                    'SELECT payload FROM approach_versions WHERE approach_version_id=?', (version,)
                ).fetchone()[0]
            )
        ) == canonical(original)
