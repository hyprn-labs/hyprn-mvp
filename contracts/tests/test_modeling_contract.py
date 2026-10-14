"""Backend-independent contract tests. Only HTTP/public IDs are observable here."""
from hyprn_mvp_app.contracts import authored_schema
import base64
import copy
import hashlib
import hmac
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request
import uuid
import pytest
from jsonschema import Draft202012Validator, FormatChecker

ROOT=Path(__file__).resolve().parents[2]
SCHEMA=authored_schema()
def uid(): return str(uuid.uuid4())
def raw_hash(b): return hashlib.sha256(b).hexdigest()
def encoded(b): return base64.urlsafe_b64encode(b).rstrip(b'=').decode()
def canonical(x):
    # Test fixtures use safe integers. Fraction/exponent JCS vectors are tested separately.
    return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
def digest(x): return raw_hash(canonical(x))
def source(b=b"outputs['y'] = inputs['x'] * 2\r\n# caf\xc3\xa9\r\n"):
    return dict(encoding='base64',media_type='text/x-python',bytes=base64.b64encode(b).decode(),sha256=raw_hash(b))
def declaration(key,direction):
    return dict(temp_key=key,direction=direction,name=key,code_symbol=key,value_type='real_scalar',units='')
def creation():
    return [dict(kind='create_definition',temp_key='d',definition_kind='explicit_component',name='Scale',ports=[declaration('x','input'),declaration('y','output')],source=source()),dict(kind='instantiate',temp_key='a',version_ref=dict(temp_key='d')),dict(kind='instantiate',temp_key='b',version_ref=dict(temp_key='d')),dict(kind='connect',temp_key='wire',source_ref=dict(instance_temp_key='a',definition_temp_key='d',port_temp_key='y'),target_ref=dict(instance_temp_key='b',definition_temp_key='d',port_temp_key='x'))]
def validate(kind,value): Draft202012Validator({**SCHEMA,'$ref':'#/$defs/'+kind},format_checker=FormatChecker()).validate(value)

class Client:
    def __init__(self,base=None,study=None,actor=None,key=None):
        self.base=(base or os.environ['HYPRN_MVP_MODEL_URL']).rstrip('/')
        self.study=study or uid();self.actor=actor or uid()
        self.key=key or Path(os.environ['HYPRN_MVP_MODEL_KEY_FILE']).read_bytes().strip()
    def call(self,method,path,body=None,status=200,permissions=None,resources=None,expired=False,raw=None):
        data=raw if raw is not None else (canonical(body) if body is not None else b'')
        claims=dict(actor_id=self.actor,study_id=self.study,resource_ids=resources if resources is not None else ['*'],permissions=permissions if permissions is not None else ['read','write'],expires_at=int(time.time())+(-10 if expired else 120),request_id=uid(),method=method,path='/modeling/1'+path,body_sha256=raw_hash(data))
        head=encoded(b'{"alg":"HS256","typ":"JWT"}');payload=encoded(canonical(claims));token=head+'.'+payload
        token+='.'+encoded(hmac.new(self.key,token.encode(),hashlib.sha256).digest())
        req=urllib.request.Request(self.base+path,data=data if method=='POST' else None,method=method,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
        if self.base in ('private://modeling', 'private://modeling-import'):
            # Test-only transport: exercise actual HTTP inside the isolated service.
            from deployment.tests.model_client import raw_request
            container = os.environ['HYPRN_MVP_MODEL_IMPORT_CONTAINER'] if self.base == 'private://modeling-import' else None
            code,result=raw_request(method,'/modeling/1'+path,data,dict(req.header_items()),container=container)
        else:
            try:
                with urllib.request.urlopen(req,timeout=20) as response: code=response.status;result=json.load(response)
            except urllib.error.HTTPError as e: code=e.code;result=json.load(e)
        assert code==status,(code,result,status)
        if status>=400: validate('Error',result)
        if status<400:
            import re
            spec=json.loads((ROOT/'contracts/modeling.openapi.yaml').read_text())
            route=next(v for k,v in spec['paths'].items() if re.fullmatch(re.sub(r'\{[^}]+\}','[^/]+',k),path.split('?')[0]))
            response=route[method.lower()]['responses'][str(status)]['content']['application/json']['schema']['$ref'].split('/')[-1]
            validate(response,result)
        return result
    def create(self): return self.call('POST','/models',dict(command_id=uid(),expected_revision=None,study_id=self.study,name='Synthetic contract model',template='empty'),status=201)['data']
    def edit(self,m,edits,**kw): return self.call('POST','/models/'+m['model_id']+'/edits',dict(command_id=uid(),expected_revision=m['draft_revision'],edits=edits),**kw)
    def commit(self,m): return self.call('POST','/models/'+m['model_id']+'/commits',dict(command_id=uid(),expected_revision=m['draft_revision']))['data']

@pytest.fixture
def client(): return Client()

@pytest.mark.schema
def test_schema_is_closed_and_examples_validate():
    Draft202012Validator.check_schema(SCHEMA)
    validate('Apply',dict(command_id=uid(),expected_revision='draft:1',edits=creation()))
    for bad in [dict(kind='native_payload',options={}),{**creation()[0],'native_id':1}]:
        with pytest.raises(Exception): validate('Edit',bad)
    with pytest.raises(Exception): validate('PortRef',dict(instance_id='7',port_id=uid()))
    with pytest.raises(Exception): validate('File',dict(file_id=uid(),path='../escape',size=1,sha256='0'*64,media_type='text/plain',role='source'))

@pytest.mark.schema
def test_source_and_numerical_slots_are_typed():
    validate('Source',source(b'\xef\xbb\xbf# \xc3\xa9\r\n'))
    n=numerical();validate('Numerical',n)
    for bad in [{**n,'native_options':{}},{**n,'optimizer':{'family':'whatever'}}]:
        with pytest.raises(Exception): validate('Numerical',bad)

def numerical():
    return dict(mode='deterministic',initialization=[],solvers=[],derivatives=dict(method='none',form=None,check=None),design_variables=[],objectives=[],constraints=[],optimizer=None,uncertainty=None)

def candidate(m,study):
    incoming=[x['target_ref'] for x in m['connections']]
    versions={d['definition_version_id']:d for d in m['definitions']}
    inputs=[]
    for inst in m['instances']:
        for p in versions[inst['definition_version_id']]['ports']:
            target=dict(instance_id=inst['instance_id'],port_id=p['port_id'])
            if p['direction']=='input' and target not in incoming: inputs.append(dict(target=target,value=0,units=p['units'],provenance=dict(kind='manual',statement='Explicit test input',evidence_version_ids=[])))
    return dict(schema_version='1',study_id=study,model_id=m['model_id'],model_revision_id=m['model_revision_id'],name='Test configuration',inputs=inputs,criteria=[],numerical=numerical(),context_snapshot=dict(description='test',boundary='',notes=[]),evidence_snapshots=[],required_capabilities=['flat_explicit_scalar'])

def test_capabilities_and_authentication(client):
    cap=client.call('GET','/capabilities')['data']
    assert any(c['id']=='flat_explicit_scalar' and c['supported'] for c in cap['capabilities'])
    assert any(c['id']=='nested_composition' and not c['supported'] for c in cap['capabilities'])
    client.call('GET','/capabilities',expired=True,status=401)
    bad=Client(key=b'invalid');bad.call('GET','/capabilities',status=401)

def test_create_revision_selective_local_update_and_immutable_history(client):
    m=client.create();validate('ModelDraft',m)
    applied=client.edit(m,creation());m=applied['data'];ids=applied['created_ids'];m1=client.commit(m);validate('ModelRevision',m1)
    before=copy.deepcopy(m1);old=ids['d']['definition_version_id'];a=ids['a']['instance_id'];b=ids['b']['instance_id']
    newsource=source(b"outputs['y'] = inputs['x'] * 3\n")
    changes=[dict(kind='revise_definition',temp_key='v2',definition_id=ids['d']['definition_id'],expected_definition_version_id=old,changes=[dict(kind='set_source',source=newsource)]),dict(kind='replace_local_instance_version',instance_id=a,expected_definition_version_id=old,version_ref=dict(temp_key='v2'))]
    m2=client.commit(client.edit(m,changes)['data'])
    assert next(i for i in m2['instances'] if i['instance_id']==b)['definition_version_id']==old
    assert next(i for i in m2['instances'] if i['instance_id']==a)['definition_version_id']!=old
    assert client.call('GET',f"/models/{m['model_id']}/revisions/{m1['model_revision_id']}")['data']==before
    assert m2['parent_model_revision_id']==m1['model_revision_id']
    assert source() in m2['source_files'] and newsource in m2['source_files']

def test_atomic_stale_replay_and_preview(client):
    m=client.create();path='/models/'+m['model_id'];command=uid();body=dict(command_id=command,expected_revision=m['draft_revision'],edits=creation())
    preview=client.call('POST',path+'/preview',{k:v for k,v in body.items() if k!='command_id'})
    assert preview['data']['instances'];assert client.call('GET',path)['data']==m
    first=client.call('POST',path+'/edits',body);again=client.call('POST',path+'/edits',body)
    assert first['data']==again['data'] and first['created_ids']==again['created_ids']
    client.call('POST',path+'/edits',{**body,'edits':[]},status=409)
    client.call('POST',path+'/edits',{**body,'command_id':uid()},status=409)
    m=first['data'];before=copy.deepcopy(m)
    rejected=uid();bad=dict(command_id=rejected,expected_revision=m['draft_revision'],edits=[dict(kind='rename_instance',instance_id=m['instances'][0]['instance_id'],name='changed'),dict(kind='remove_instance',instance_id=uid())])
    r=client.call('POST',path+'/edits',bad,status=409);assert r['error']['outcome']=='unchanged'
    assert client.call('GET',path)['data']==before
    assert client.call('POST',path+'/edits',bad,status=409)['error']['code']==r['error']['code']
    receipt=client.call('GET',f'/commands/{rejected}?study_id={client.study}&category=model')['data'];assert receipt['state']=='rejected'
    foreign=Client(study=uid());foreign.call('GET',path,status=404)
    client.call('GET',f'/commands/{command}?study_id={client.study}&category=model',permissions=[],status=403)

def test_unsupported_unknown_fields_and_raw_json_rejected(client):
    m=client.create();path='/models/'+m['model_id'];edits=creation();edits[0]['definition_kind']='composite'
    client.edit(m,edits,status=422)
    body=dict(command_id=uid(),expected_revision=m['draft_revision'],edits=creation(),native_payload={})
    client.call('POST',path+'/edits',body,status=400)
    client.call('POST',path+'/edits',raw=b'{"edits":[],"edits":[]}',status=400)
    assert client.call('GET',path)['data']==m

def test_pure_compatibility_and_prepared_model_only(client):
    m=client.commit(client.edit(client.create(),creation())['data']);cfg=candidate(m,client.study);path='/models/'+m['model_id']
    validate('ConfigurationCandidate',cfg)
    proof=client.call('POST',path+'/configuration-compatibility',dict(model_revision_id=m['model_revision_id'],configuration_candidate=cfg))['data'];validate('CompatibilityResult',proof)
    assert proof['compatible'] and proof['candidate_digest']==digest(cfg)
    assert client.call('POST',path+'/configuration-compatibility',dict(model_revision_id=m['model_revision_id'],configuration_candidate=cfg))['data']==proof
    wrong=copy.deepcopy(cfg);wrong['inputs']=[]
    assert not client.call('POST',path+'/configuration-compatibility',dict(model_revision_id=m['model_revision_id'],configuration_candidate=wrong))['data']['compatible']
    wrong=copy.deepcopy(cfg);wrong['numerical']['mode']='coupled'
    client.call('POST',path+'/configuration-compatibility',dict(model_revision_id=m['model_revision_id'],configuration_candidate=wrong),status=422)
    cfg.update(configuration_id=uid(),configuration_revision_id=uid(),parent_revision_id=None);cfg['digest']=digest(cfg)
    body=dict(command_id=uid(),model_revision_id=m['model_revision_id'],configuration_snapshot=cfg,configuration_digest=cfg['digest'])
    prepared=client.call('POST',path+'/prepare-execution',body)['data'];validate('PreparedModelArtifact',prepared)
    assert prepared==client.call('POST',path+'/prepare-execution',body)['data']
    assert not any(k in prepared for k in ('run_id','runtime','evidence_snapshots','context_snapshot'))
    assert prepared['prepared_digest']==digest({k:v for k,v in prepared.items() if k!='prepared_digest'})
    for f in prepared['files']:
        file=client.call('GET',f"/preparations/{prepared['preparation_id']}/files/{f['file_id']}")['data'];raw=base64.b64decode(file['bytes']);assert raw_hash(raw)==f['sha256'] and len(raw)==f['size']
    body['command_id']=uid();body['configuration_digest']='0'*64
    client.call('POST',path+'/prepare-execution',body,status=422)
