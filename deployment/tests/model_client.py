"""Test-only transport into the private network; never publishes a model port."""
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import subprocess
import time
import uuid

# The modeling service under test: its scoped root (holding credentials/model.key) and its
# container. Fixtures set both; HYPRN_MVP_MODEL_TEST_ROOT and HYPRN_MVP_MODEL_TEST_CONTAINER name
# them for a manual run. There is no default service.
ROOT = Path(os.environ['HYPRN_MVP_MODEL_TEST_ROOT']) if os.environ.get('HYPRN_MVP_MODEL_TEST_ROOT') else None
CONTAINER = os.environ.get('HYPRN_MVP_MODEL_TEST_CONTAINER') or None


def _container(container=None):
    name = container or CONTAINER
    if not name:
        raise ValueError('No modeling service under test: set HYPRN_MVP_MODEL_TEST_CONTAINER or use a fixture')
    return name
HTTP = '''require 'net/http'; require 'json'
x=JSON.parse(STDIN.read)
uri=URI('http://127.0.0.1:3000'+x.fetch('path'))
r=Net::HTTPGenericRequest.new(x.fetch('method'),true,true,uri)
x.fetch('headers').each { |k,v| r[k]=v }
r.body=x.fetch('body')
http=Net::HTTP.new(uri.host,uri.port); http.read_timeout=20
v=http.request(r)
puts JSON.generate({'status'=>v.code.to_i,'body'=>v.body})
'''

def ruby(script, rails=False):
    args = ['docker','exec','-i',_container()]
    args += ['bundle','exec','rails','runner','-'] if rails else ['ruby','-']
    return subprocess.run(args,input=script,text=True,capture_output=True,check=True).stdout

def raw_request(method, path, body=b'', headers=None, container=None):
    data = dict(method=method,path=path,body=body.decode(),headers=headers or {})
    result = subprocess.run(['docker','exec','-i',_container(container),'ruby','-e',HTTP],input=json.dumps(data),text=True,capture_output=True,check=True)
    response=json.loads(result.stdout)
    return response['status'],json.loads(response['body'])

def uid(): return str(uuid.uuid4())
def encode(b): return base64.urlsafe_b64encode(b).decode().rstrip('=')

class ModelClient:
    def __init__(self, study=None, key=None):
        self.study=study or uid()
        if key is None and ROOT is None:
            raise ValueError('No modeling service under test: set HYPRN_MVP_MODEL_TEST_ROOT or use a fixture')
        self.key=key or (ROOT/'credentials/model.key').read_bytes().strip()

    def call(self, method, path, body=None, status=200, permissions=None, resources=None):
        raw=json.dumps(body,separators=(',',':'),ensure_ascii=False).encode() if body is not None else b''
        path='/modeling/1'+path
        claims=dict(actor_id=uid(),study_id=self.study,request_id=uid(),resource_ids=resources if resources is not None else ['*'],permissions=permissions if permissions is not None else ['read','write'],expires_at=int(time.time())+120,method=method,path=path,body_sha256=hashlib.sha256(raw).hexdigest())
        token=encode(b'{"alg":"HS256","typ":"JWT"}')+'.'+encode(json.dumps(claims).encode())
        token+='.'+encode(hmac.new(self.key,token.encode(),hashlib.sha256).digest())
        code,result=raw_request(method,path,raw,{'Authorization':'Bearer '+token,'Content-Type':'application/json'})
        assert code==status,(code,result,status)
        return result

    def create(self, name='Synthetic isolated model'):
        return self.call('POST','/models',dict(command_id=uid(),expected_revision=None,study_id=self.study,name=name,template='empty'),status=201)['data']

    def edit(self, model, edits):
        return self.call('POST','/models/'+model['model_id']+'/edits',dict(command_id=uid(),expected_revision=model['draft_revision'],edits=edits))['data']

    def commit(self, model):
        return self.call('POST','/models/'+model['model_id']+'/commits',dict(command_id=uid(),expected_revision=model['draft_revision']))['data']
