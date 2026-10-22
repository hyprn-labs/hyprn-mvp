"""Guarded public HTTP/API boundary with an explicit deterministic private double.

Real Store/Auth/Coordinator and JWT signing; native Rails behavior is proven by the
modeling-service tests.
No candidate code, native packages, live stores or generated repository artifacts.
"""
from copy import deepcopy
import base64
import hashlib
import hmac
import json
import sqlite3
import subprocess
import time

import scoped_fixture as guard
from checks import PROJECTION_SCOPE
SCOPE = PROJECTION_SCOPE or guard.scope_from_environment()
guard.validate_scope(SCOPE)

import pytest
from hyprn_mvp_app.modeling import ModelingClient, validate
from hyprn_mvp_app.store import DomainError, canonical, uid, digest
from test_assumption_authoring import env as base_env, PrivateTransport, command, url
from test_assumptions_evidence_contracts import sample,D

CATALOG = dict(
    schema_version='1',
    catalog_digest='9453b65bb997da3568956a53125f53ec83521c5b78d014fde8d15b4538c81f45',
    engine='OpenMDAO',
    engine_version='3.45.1',
    engine_source_sha256='9a812f46a371f9d10b5b17e9a21e5024b1c753ebfcee42d0e628eca4dcf3ba92',
    supported_units=[
        'm',
        'km',
        'cm',
        'mm',
        's',
        'min',
        'h',
        'kg',
        'g',
        'N',
        'Pa',
        'kPa',
        'MPa',
        'K',
        'degC',
        'degF',
        'rad',
        'deg',
        'm/s',
        'km/h',
        'J/kg',
        'kJ/kg',
        'MJ/kg',
        'kg/m**3',
        'g/cm**3',
        'm**2',
        'cm**2',
        'mm**2',
        'm**3',
        'cm**3',
        'mm**3',
        'kg/m**2',
        'g/m**2',
        '1/m**2',
        'J/(kg*K)',
        'kJ/(kg*K)',
        'J',
        'kJ',
        'MJ',
        'W',
        'kW',
        'MW',
        'm**3/s',
        'kg/s',
        'm/s**2',
        'N*m',
        'W/(m*K)',
        'W/(m**2*K)',
    ],
    affine_conversion=False,
)


class UnitTransport(PrivateTransport):
    def __init__(self, store, sid):
        super().__init__(store, sid)
        self.caps['contract_versions'].append('1.3');self.caps['schema_versions'].append('3')
        self.caps['capabilities'].append(dict(self.caps['capabilities'][0],id='unit_declarations'))
        self.catalog=deepcopy(CATALOG);self.catalog_status=200;self.catalog_failure=False
        self.draft['schema_version']='3';self.draft['required_capabilities'].append('unit_declarations/1')
        self.downgrade=False
    def __call__(self, method, path, raw, headers):
        token=headers['Authorization'].removeprefix('Bearer ')
        head,payload,signature=token.split('.')
        decode=lambda part:base64.urlsafe_b64decode(part+'='*(-len(part)%4))
        assert hmac.compare_digest(decode(signature),hmac.new(b't'*32,(head+'.'+payload).encode(),hashlib.sha256).digest())
        claims=json.loads(decode(payload))
        assert claims['study_id']==self.sid and claims['method']==method and claims['path']==path
        assert claims['body_sha256']==hashlib.sha256(raw).hexdigest()
        assert 0<claims['expires_at']-time.time()<=60
        if method=='GET' or path.endswith('/preview'):assert claims['permissions']==['read']
        if path.endswith('/unit-catalog'):
            assert claims['resource_ids']==[self.sid]
            with sqlite3.connect(self.store.path,timeout=0) as db:db.execute('BEGIN IMMEDIATE');db.rollback()
            self.calls.append((method,path,None))
            if self.hook:self.hook(method,path,None)
            if self.catalog_failure:raise OSError('private secret unavailable')
            return self.catalog_status,dict(schema_version='1',request_id=uid(),data=deepcopy(self.catalog))
        if method=='POST' and path.endswith('/models'):
            body=json.loads(raw);self.calls.append((method,path,body))
            if self.hook:self.hook(method,path,body)
            self.draft['schema_version']=body.get('schema_version','1')
            if self.draft['schema_version']=='1':self.draft.pop('assumptions',None);self.draft['required_capabilities']=[]
            result=dict(data=deepcopy(self.draft))
            identity=dict(major='1',operation='create',target=None,study_id=self.sid,payload={k:v for k,v in body.items() if k!='command_id'})
            self.receipts[body['command_id']]=dict(command_id=body['command_id'],state='committed',payload_digest=digest(identity),status=201,response=result)
            return 201,dict(schema_version='1',request_id=uid(),**result)
        status,result=super().__call__(method,path,raw,headers)
        if self.downgrade and method=='POST' and path.endswith(('/preview','/edits')):
            result['data']['schema_version']='2';result['data']['required_capabilities']=[]
        return status,result

@pytest.fixture
def env(base_env):
    e=base_env;t=UnitTransport(e['store'],e['sid'])
    t.draft['model_id']=e['mid']
    e['coord'].model.transport=t;e['transport']=t
    return e

def catalog_url(e):return '/api/1/studies/'+e['sid']+'/unit-catalog'
def edit(e, preview=False):
    body=command(e);body['schema_version']='3'
    if preview:body.pop('command_id')
    return body

def test_catalog_exact_identity_public_envelope_and_scoped_jwt(env):
    r=env['client'].get(catalog_url(env))
    assert r.status_code==200,r.text
    validate('UnitCatalogResponse1',r.json());assert r.json()['data']==CATALOG
    assert [c[1] for c in env['transport'].calls]==['/modeling/1/capabilities','/modeling/1/unit-catalog']
    assert not any(c[0]=='POST' for c in env['transport'].calls)

@pytest.mark.parametrize('scope',['anonymous','foreign','missing','revoked'])
def test_catalog_authorizes_before_any_remote_call(env,scope):
    target=catalog_url(env)
    if scope=='anonymous':env['client'].cookies.clear()
    if scope=='foreign':target=target.replace(env['sid'],env['store'].create_study(uid(),uid(),'Foreign')['study_id'])
    if scope=='missing':target=target.replace(env['sid'],uid())
    if scope=='revoked':
        with env['store'].connection(write=True) as db:db.execute('DELETE FROM memberships')
    r=env['client'].get(target)
    assert r.status_code==(401 if scope=='anonymous' else 404)
    assert env['transport'].calls==[]

@pytest.mark.parametrize('failure',['contract','schema','capability','unsupported','version','malformed','outage'])
@pytest.mark.parametrize('operation',['catalog','preview','edits','create'])
def test_model3_negotiation_is_explicit_before_remote_write(env,failure,operation):
    t=env['transport']
    if failure=='contract':t.caps['contract_versions']=['1.2']
    if failure=='schema':t.caps['schema_versions']=['1','2']
    if failure=='capability':t.caps['capabilities']=t.caps['capabilities'][:1]
    if failure=='unsupported':t.caps['capabilities'][-1]['supported']=False
    if failure=='version':t.caps['capabilities'][-1]['version']='2'
    if failure=='malformed':t.caps['unexpected']=True
    if failure=='outage':
        def fail(*args):raise OSError('private secret')
        t.hook=fail
    if operation=='catalog':r=env['client'].get(catalog_url(env))
    elif operation=='create':r=env['client'].post('/api/1/studies/'+env['sid']+'/models',json=dict(command_id=uid(),expected_revision=env['study']['revision'],name='Typed',template='empty',schema_version='3'))
    else:r=env['client'].post(url(env,'/'+operation),json=edit(env,operation=='preview'))
    assert r.status_code==(503 if failure in {'malformed','outage'} else 422),r.text
    assert not any(c[0]=='POST' for c in t.calls)
    with env['store'].connection() as db:assert db.execute("SELECT count(*) FROM receipts WHERE category='model'").fetchone()[0]==0

@pytest.mark.parametrize('failure',['digest','source','engine','version','extra','missing','duplicate','unsupported','affine','oversize','outage','status'])
def test_catalog_rejects_corrupt_bounded_backend_without_fallback(env,failure):
    t=env['transport'];c=t.catalog
    if failure=='digest':c['catalog_digest']='0'*64
    if failure=='source':c['engine_source_sha256']='0'*64
    if failure=='engine':c['engine']='Other'
    if failure=='version':c['engine_version']='3.46.0'
    if failure=='extra':c['extra']=True
    if failure=='missing':c['supported_units'].pop()
    if failure=='duplicate':c['supported_units'][0]=c['supported_units'][1]
    if failure=='unsupported':c['supported_units'][0]='USD'
    if failure=='affine':c['affine_conversion']=True
    if failure=='oversize':c['extra']='X'*16384
    if failure=='outage':t.catalog_failure=True
    if failure=='status':t.catalog_status=202
    r=env['client'].get(catalog_url(env))
    assert r.status_code==503 and r.json()['error']['code']=='backend_unavailable',r.text
    assert 'private secret' not in r.text

@pytest.mark.parametrize('phase',['capabilities','unit-catalog'])
@pytest.mark.parametrize('failure',[False,True])
def test_catalog_revocation_suppresses_remote_success_and_error(env,phase,failure):
    def revoke(method,path,body):
        if not path.endswith('/'+phase):return
        with env['store'].connection(write=True) as db:db.execute('DELETE FROM memberships')
        if failure:raise OSError('private secret after revocation')
    env['transport'].hook=revoke
    r=env['client'].get(catalog_url(env))
    assert r.status_code==404 and 'private secret' not in r.text

def test_model3_preview_apply_exact_replay_and_receipt_identity(env):
    t=env['transport'];original=deepcopy(t.draft)
    preview=env['client'].post(url(env,'/preview'),json=edit(env,True))
    assert preview.status_code==200,preview.text
    assert preview.json()['data']['schema_version']=='3' and t.draft==original
    body=edit(env);t.lose_response=True
    first=env['client'].post(url(env,'/edits'),json=body)
    assert first.status_code==202,first.text
    receipt='/api/1/studies/'+env['sid']+'/commands/'+body['command_id']+'?category=model'
    recovered=env['client'].get(receipt)
    assert recovered.status_code==200 and recovered.json()['data']['state']=='committed',recovered.text
    result=env['client'].post(url(env,'/edits'),json=body)
    assert result.status_code==200 and result.json()['data']==t.draft
    assert len([c for c in t.calls if c[0]=='POST' and c[1].endswith('/edits')])==1
    changed=deepcopy(body);changed['edits'][0]['statement']='Changed'
    assert env['client'].post(url(env,'/edits'),json=changed).status_code==409

@pytest.mark.parametrize('bad',['command','digest','version','model','study'])
def test_model3_receipt_cannot_substitute_other_identity(env,bad):
    body=edit(env);t=env['transport'];t.lose_response=True
    assert env['client'].post(url(env,'/edits'),json=body).status_code==202
    receipt=t.receipts[body['command_id']]
    if bad=='command':receipt['command_id']=uid()
    if bad=='digest':receipt['payload_digest']='0'*64
    data=receipt['response']['data']
    if bad=='version':data['schema_version']='2';data['required_capabilities']=[]
    if bad=='model':data['model_id']=uid()
    if bad=='study':data['study_id']=uid()
    result=env['client'].get('/api/1/studies/'+env['sid']+'/commands/'+body['command_id']+'?category=model')
    assert result.status_code==200 and result.json()['data']['state']=='pending_remote',result.text
    with env['store'].connection() as db:assert db.execute("SELECT state FROM receipts WHERE category='model'").fetchone()[0]=='pending_remote'

@pytest.mark.parametrize('operation',['preview','edits'])
def test_model3_response_cannot_silently_downgrade(env,operation):
    env['transport'].downgrade=True
    r=env['client'].post(url(env,'/'+operation),json=edit(env,operation=='preview'))
    assert r.status_code==(503 if operation=='preview' else 202),r.text

@pytest.mark.parametrize('version',[None,'3'])
def test_explicit_create_and_legacy_create_preserve_selected_protocol(env,version):
    body=dict(command_id=uid(),expected_revision=env['study']['revision'],name='Selected',template='empty')
    if version:body['schema_version']=version
    r=env['client'].post('/api/1/studies/'+env['sid']+'/models',json=body)
    assert r.status_code==201,r.text
    assert r.json()['data']['schema_version']==(version or '1')
    private=next(c[2] for c in env['transport'].calls if c[0]=='POST')
    assert private['expected_revision'] is None and private['study_id']==env['sid']
    assert private.get('schema_version')==version

def test_legacy_preview_apply_require_no_unit_capability(base_env):
    e=base_env
    for operation in ['preview','edits']:
        body=command(e)
        if operation=='preview':body.pop('command_id')
        r=e['client'].post(url(e,'/'+operation),json=body)
        assert r.status_code==200 and r.json()['data']['schema_version']=='2'

def test_discovery_advertises_model3_only_when_backend_supports_it(env):
    report=env['client'].get('/api/1/capabilities').json()['data']
    assert 'unit_declarations/1' in report['modeling'] and 'model/3' in report['contract_versions']
    env['transport'].caps['schema_versions']=['1','2']
    report=env['client'].get('/api/1/capabilities').json()['data']
    assert 'unit_declarations/1' in report['unavailable'] and 'model/3' not in report['contract_versions']

def test_generated_registers_route_closed_create_union_and_authoritative_schemas():
    output=guard.scoped_path(SCOPE,'artifacts/units-b1.openapi.json')
    p=subprocess.run(guard.contract_generator_command(SCOPE,'artifacts/units-b1.openapi.json'),env=guard.clean_environment(SCOPE),capture_output=True,text=True)
    guard.scoped_path(SCOPE,'evidence/generator.log').write_text(p.stdout+p.stderr)
    assert p.returncode==0
    spec=json.loads(output.read_text());schemas=spec['components']['schemas']
    route=spec['paths']['/studies/{study_id}/unit-catalog']['get']
    assert route['responses']['200']['content']['application/json']['schema']['properties']['data']['$ref'].endswith('/UnitCatalog1')
    assert 'oneOf' in schemas['PublicNewModel']
    assert spec['paths']['/studies/{study_id}/models']['post']['requestBody']['content']['application/json']['schema']['$ref'].endswith('/PublicNewModel')
    assert {'Create3','Preview3','Apply3','ModelDraft3','UnitDeclaration1','UnitCatalog1'}<=schemas.keys()
    assert 'quantity_definitions/1' in schemas['ApplicationCapabilities']['properties']['modeling']['items']['enum']
    route=spec['paths']['/studies/{study_id}/models/{model_id}/edits']['post']
    assert route['requestBody']['content']['application/json']['schema']['$ref'].endswith('/ApplyRead4')
    assert route['responses']['200']['content']['application/json']['schema']['$ref'].endswith('/ModelDraftEditResponse4')

@pytest.mark.parametrize('size',[16384,16385])
def test_private_catalog_stream_bound_applies_before_json_parsing(monkeypatch,size):
    from hyprn_mvp_app import modeling
    envelope=canonical(dict(schema_version='1',request_id=uid(),data=CATALOG))
    raw=envelope+b' '*(size-len(envelope))
    parsed=[];loads=json.loads
    def observed_loads(value):parsed.append(bytes(value));return loads(value)
    class Stream:
        status_code=200
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def iter_bytes(self):
            for offset in range(0,len(raw),4096):yield raw[offset:offset+4096]
    class Client:
        def __init__(self,**kwargs):assert kwargs==dict(timeout=20,follow_redirects=False,trust_env=False)
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def stream(self,method,url,**kwargs):
            assert method=='GET' and url=='http://private.invalid/modeling/1/unit-catalog'
            assert kwargs['content'] is None
            return Stream()
    monkeypatch.setattr(modeling.httpx,'Client',Client)
    monkeypatch.setattr(modeling.json,'loads',observed_loads)
    client=ModelingClient('http://private.invalid/modeling/1',b't'*32)
    if size==16384:
        assert client.call(uid(),uid(),'GET','/unit-catalog',response_schema='UnitCatalogResponse1')[1]['data']==CATALOG
        # The bounded stream body is parsed exactly once; the only other parse is the
        # schema check's canonical snapshot of that already-parsed value, never stream bytes.
        snapshot=json.dumps(loads(raw),sort_keys=True,ensure_ascii=True,allow_nan=False,separators=(',',':')).encode()
        assert parsed[0]==raw and len(parsed[0])==16384 and parsed[1:]==[snapshot]
    else:
        with pytest.raises(DomainError) as error:client.call(uid(),uid(),'GET','/unit-catalog',response_schema='UnitCatalogResponse1')
        assert error.value.status==503 and parsed==[]

@pytest.mark.parametrize('operation',['preview','edits'])
@pytest.mark.parametrize('failure',[False,True])
def test_model3_revocation_during_operation_suppresses_output(env,operation,failure):
    def revoke(method,path,body):
        if method!='POST' or not path.endswith('/'+operation):return
        with env['store'].connection(write=True) as db:db.execute('DELETE FROM memberships')
        if failure:raise OSError('private secret')
    env['transport'].hook=revoke
    r=env['client'].post(url(env,'/'+operation),json=edit(env,operation=='preview'))
    assert r.status_code==404,r.text
    with env['store'].connection() as db:assert not db.execute("SELECT 1 FROM receipts WHERE category='model' AND state='committed'").fetchone()

def test_catalog_rejects_unknown_query_after_authorization(env):
    r=env['client'].get(catalog_url(env)+'?catalog_digest=client-authority')
    assert r.status_code==400 and env['transport'].calls==[]

def test_unit_reads_allow_reader_but_apply_and_csrf_are_protected(env):
    env['client'].headers.pop('X-CSRF-Token')
    assert env['client'].post(url(env,'/edits'),json=edit(env)).status_code==403
    with env['store'].connection(write=True) as db:db.execute("UPDATE memberships SET role='reader'")
    assert env['client'].get(catalog_url(env)).status_code==200
    with pytest.raises(DomainError) as error:
        body=edit(env)
        env['coord'].execute(env['actor'],env['sid'],'edits',env['mid'],body,body,'/models/'+env['mid']+'/edits','Apply','ModelDraftEditResponse')
    assert error.value.status==403

def test_model3_mixed_retained_unit_declarations_and_source_stay_exact(env):
    t=env['transport'];old=t.draft['definitions'][0]
    old_port=sample(D['Port']);old_port.update(port_id=uid(),definition_version_id=old['definition_version_id'],units='')
    old['ports']=[old_port]
    new=deepcopy(old);new['definition_version_id']=uid()
    new['ports']=[dict(old_port,definition_version_id=new['definition_version_id'],units={'kind':'unspecified'})]
    t.draft['definitions'].append(new)
    t.draft['ports']=[deepcopy(old_port),deepcopy(new['ports'][0])]
    source=sample(D['Source']);raw=b'raise RuntimeError("candidate must remain data")\n'
    source.update(bytes=base64.b64encode(raw).decode(),sha256=hashlib.sha256(raw).hexdigest())
    t.draft['source_files']=[source]
    original=deepcopy(t.draft)
    for action in ['preview','edits']:
        r=env['client'].post(url(env,'/'+action),json=edit(env,action=='preview'))
        assert r.status_code==200,r.text
        for field in ['definitions','ports','source_files']:
            assert r.json()['data'][field]==original[field]

@pytest.mark.parametrize('unit',['',{'kind':'physical','expression':'USD'}, {'kind':'unspecified','expression':'m'}, None])
def test_typed_edit_rejects_bad_new_declarations_before_private_io(env,unit):
    source=sample(D['Source']);raw=b'# data only\n'
    source.update(bytes=base64.b64encode(raw).decode(),sha256=hashlib.sha256(raw).hexdigest())
    port=sample(D['PortDeclaration']);port['units']=unit
    body=edit(env,True);body['edits']=[dict(kind='create_definition',temp_key='new',definition_kind='explicit_component',name='Typed',ports=[port],source=source)]
    r=env['client'].post(url(env,'/preview'),json=body)
    assert r.status_code==400 and env['transport'].calls==[]


def enable_quantity(e):
    t=e['transport'];t.caps['schema_versions'].append('4')
    t.caps['capabilities'].append(dict(t.caps['capabilities'][0],id='quantity_definitions'))
    t.draft['schema_version']='4';t.draft['required_capabilities'].append('quantity_definitions/1')
    return t


def test_quantity_public_preview_replay_reader_and_negotiation(env):
    t=enable_quantity(env);before=deepcopy(t.draft)
    caps=env['client'].get('/api/1/capabilities').json()['data']
    assert 'model/4' in caps['contract_versions'] and 'quantity_definitions/1' in caps['modeling']
    body=edit(env);body['schema_version']='4'
    preview=env['client'].post(url(env,'/preview'),json={k:v for k,v in body.items() if k!='command_id'})
    assert preview.status_code==200,preview.text
    validate('ModelDraftEditResponse4',preview.json());assert t.draft==before
    t.lose_response=True
    first=env['client'].post(url(env,'/edits'),json=body);assert first.status_code==202,first.text
    recovered=env['client'].get('/api/1/studies/'+env['sid']+'/commands/'+body['command_id']+'?category=model')
    assert recovered.json()['data']['state']=='committed',recovered.text
    replay=env['client'].post(url(env,'/edits'),json=body)
    assert replay.status_code==200 and replay.json()['data']['schema_version']=='4',replay.text
    assert len([x for x in t.calls if x[0]=='POST' and x[1].endswith('/edits')])==1
    read=env['client'].get(url(env,''));assert read.status_code==200,read.text
    validate('ModelDraftRead4',read.json()['data'])


@pytest.mark.parametrize('failure',['schema','capability','downgrade'])
def test_quantity_public_rejects_unsupported_and_downgraded(env,failure):
    t=enable_quantity(env)
    if failure=='schema':t.caps['schema_versions'].remove('4')
    if failure=='capability':t.caps['capabilities']=[c for c in t.caps['capabilities'] if c['id']!='quantity_definitions']
    if failure=='downgrade':t.downgrade=True
    body=edit(env,True);body['schema_version']='4'
    result=env['client'].post(url(env,'/preview'),json=body)
    assert result.status_code==(503 if failure=='downgrade' else 422),result.text
    if failure!='downgrade':assert not any(x[0]=='POST' for x in t.calls)


def test_quantity_reader_adoption_keeps_legacy_semantic_source_guard(env):
    # Configuration/worker consumers still deliberately request the old reader.
    # Its successful structural validation must not bypass exact source checks.
    env['transport'].draft['source_files']=[dict(encoding='base64',media_type='text/x-python',
        bytes=base64.b64encode(b'candidate stays inert').decode(),sha256='0'*64)]
    with pytest.raises(DomainError) as error:
        env['coord'].read(env['actor'],env['sid'],env['mid'],response_schema='ModelDraftResponse')
    assert error.value.code=='backend_unavailable'


def test_model_format_discovery_and_creation_diagnostic(env):
    enable_quantity(env)
    caps = env['client'].get('/api/1/capabilities').json()['data']
    assert caps['model_formats'] == dict(
        create_request=['3'], edit_request=['4'], saved_record=['4']
    )
    reply = env['client'].post(
        '/api/1/studies/' + env['sid'] + '/models',
        json=dict(
            command_id=uid(),
            expected_revision='token',
            name='Model',
            template='empty',
            schema_version='4',
        ),
    )
    assert reply.status_code == 400
    fields = reply.json()['error']['fields']
    assert len(fields) == 1 and fields[0]['path'] == '/schema_version'
    assert 'Model creation accepts request format 3' in fields[0]['message']
