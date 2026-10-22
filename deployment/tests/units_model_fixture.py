"""Guarded private HTTP/JWT and static Rails fixtures; no candidate execution."""
import base64
import hashlib
import hmac
import json
from pathlib import Path
import secrets
import subprocess
import time
import uuid

import scoped_fixture as guard

ROOT = Path(__file__).resolve().parents[2]
PATCHES = ('040-modeling-contract.patch', '050-native-generation.patch',
           '060-ui-discovery.patch', '070-assumptions-evidence.patch', '080-unit-declarations.patch', '090-quantity-definitions.patch',
           '100-configurations-without-criteria.patch')


def current_scope():
    from checks import PROJECTION_SCOPE
    return guard.validate_scope(PROJECTION_SCOPE)


def stage_sources():
    scope = current_scope()
    from modeling_runtime import stage_native_inputs
    stage = guard.scoped_path(scope, 'artifacts/units-model-' + str(uuid.uuid4()))
    stage.mkdir()
    stage_native_inputs(stage)
    apply_display_name_policy(stage / 'modeling_contract.rb')
    for patch, path in [('050-native-generation.patch', 'app/services/native_materializer.rb'),
                        ('050-native-generation.patch', 'app/services/native_program.rb'),
                        ('040-modeling-contract.patch', 'config/modeling.units.json')]:
        section = (ROOT / 'upstream/whatsopt-patches' / patch).read_text().split('+++ b/' + path + '\n', 1)[1].split('\n--- ', 1)[0]
        target = stage / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('\n'.join(line[1:] for line in section.splitlines()[1:] if line.startswith('+')) + '\n')
    for name in ('assumptions.patch', 'units.patch'):
        result = subprocess.run(['patch', '--batch', '--fuzz=0', '-p1'], input=(stage/name).read_text(), cwd=stage,
                                capture_output=True, text=True, timeout=20, env=guard.clean_environment(scope))
        (stage/(name+'.log')).write_text(result.stdout+result.stderr)
        assert result.returncode == 0 and not any(s in result.stdout.lower() for s in ('offset', 'fuzz')), result.stdout+result.stderr
    image = json.loads((ROOT/'deployment/pins.json').read_text())['modeling_producer']['image']
    assert image.startswith('sha256:') and len(image) == 71
    return scope, stage, image


def apply_display_name_policy(service):
    """A read-only adapter overlay must retain the image's deployment naming policy."""
    text = service.read_text()
    original = "native=Analysis.create!(name:body['name'],public:false)"
    replacement = "native=Analysis.create!(name:'model_'+model_id.delete('-'),public:false)"
    policy = (ROOT / 'deployment/modeling_policy.rb').read_text()
    assert original in policy and replacement in policy
    assert text.count(original) == 1
    service.write_text(text.replace(original, replacement))


def mounts(stage):
    return {stage/'modeling_contract.rb': '/native/app/services/modeling_contract.rb',
            stage/'modeling.schema.json': '/native/config/modeling.schema.json',
            stage/'app/services/native_materializer.rb': '/native/app/services/native_materializer.rb',
            stage/'app/services/native_program.rb': '/native/app/services/native_program.rb',
            stage/'config/modeling.units.json': '/native/config/modeling.units.json',
            stage/'provenance-inputs': '/native/provenance-inputs'}


def restrictions(stage):
    return ['--pull', 'never', '--network', 'none', '--read-only', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges', '--user', '10001:10001', '--memory', '768m',
            '--cpus', '1', '--pids-limit', '128', '--tmpfs', '/tmp:rw,noexec,nosuid,size=192m,mode=1777',
            '--tmpfs', '/native/tmp:rw,noexec,nosuid,size=32m,uid=10001,gid=10001',
            '--tmpfs', '/native/log:rw,noexec,nosuid,size=16m,uid=10001,gid=10001',
            *[arg for src,dst in mounts(stage).items() for arg in ('--mount', f'type=bind,src={src},dst={dst},readonly')]]


def command(scope, args, *, input=None, check=True):
    guard.validate_scope(scope)
    evidence = guard.scoped_path(scope, 'evidence/units-command-' + str(uuid.uuid4()))
    evidence.mkdir()
    start = time.monotonic()
    result = subprocess.run(args, input=input, capture_output=True, text=True, timeout=55, env=guard.clean_environment(scope))
    (evidence/'stdout.log').write_text(result.stdout)
    (evidence/'stderr.log').write_text(result.stderr)
    if input is not None: (evidence/'stdin.txt').write_text(input)
    (evidence/'result.json').write_text(json.dumps(dict(command=args, exit=result.returncode, duration=time.monotonic()-start), indent=2))
    if check: assert result.returncode == 0, str(evidence)+'\n'+result.stderr[-4000:]+result.stdout[-2000:]
    return result


def run_ruby(code, staged=None):
    scope,stage,image = staged or stage_sources()
    args=['docker','run','--rm','-i',*restrictions(stage),'-e','RAILS_ENV=test','-e','DISABLE_BOOTSNAP=1',
          '-e','HOME=/tmp','-e','NATIVE_STATIC_GENERATION=1','-e','SECRET_KEY_BASE=synthetic-unit-test',
          '--entrypoint','ruby',image,'-']
    return command(scope,args,input=code).stdout


HTTP = """require 'net/http'; require 'json'
x=JSON.parse(STDIN.read); uri=URI('http://127.0.0.1:3000'+x.fetch('path'))
r=Net::HTTPGenericRequest.new(x.fetch('method'),true,true,uri)
x.fetch('headers').each { |k,v| r[k]=v }; r.body=x.fetch('body')
h=Net::HTTP.new(uri.host,uri.port); h.read_timeout=20
v=h.request(r); puts JSON.generate({'status'=>v.code.to_i,'body'=>v.body})
"""


class PrivateModel:
    def __init__(self):
        self.scope,self.stage,self.image = stage_sources()
        # Scoped names: hyprn-mvp-test-<scope8>-<role>; one scope may run several models.
        self.name = guard.SCOPE_PREFIX+self.scope.run_uuid[:8]+'-model-'+uuid.uuid4().hex[:8]
        self.label = 'org.hyprn-mvp.test-scope'
        self.key = secrets.token_hex(64).encode()
        self.study,self.actor = str(uuid.uuid4()),str(uuid.uuid4())
        self.store = self.stage/'store'; self.store.mkdir(); self.store.chmod(0o777)
        key = self.stage/'model.key'; key.write_bytes(self.key); key.chmod(0o444)
        rails = self.stage/'rails.key'; rails.write_text(secrets.token_hex(64)); rails.chmod(0o444)
        args=['docker','run','-d','--name',self.name,'--label',self.label+'='+self.scope.run_uuid,
              *restrictions(self.stage),'--mount',f'type=bind,src={self.store},dst=/store',
              '--mount',f'type=bind,src={key},dst=/run/model.key,readonly',
              '--mount',f'type=bind,src={rails},dst=/run/rails.key,readonly',self.image]
        self.started = False
        try:
            command(self.scope,args); self.started = True
            self.ready()
            info=json.loads(command(self.scope,['docker','inspect',self.name]).stdout)[0]
            assert info['Image']==self.image and info['HostConfig']['NetworkMode']=='none'
            assert not info['HostConfig']['PortBindings'] and info['HostConfig']['ReadonlyRootfs']
            (self.stage/'identity.json').write_text(json.dumps(dict(image=info['Image'],container=info['Id'],
                network='none',ports={},source_hashes={str(p.relative_to(self.stage)):hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.stage.rglob('*') if p.is_file() and not p.is_relative_to(self.store) and p.suffix!='key'}),indent=2))
        except BaseException:
            self.close(); raise

    def ready(self):
        for _ in range(60):
            result=command(self.scope,['docker','exec',self.name,'ruby','-rsocket','-e',"TCPSocket.new('127.0.0.1',3000).close"],check=False)
            if result.returncode==0:return
            time.sleep(.25)
        raise AssertionError(command(self.scope,['docker','logs',self.name]).stdout)

    def call(self, method, path, body=None, status=200, *, study=None, permissions=None, expired=False, wrong_hash=False, key=None):
        guard.validate_scope(self.scope)
        raw=json.dumps(body,separators=(',',':'),ensure_ascii=False).encode() if body is not None else b''
        path='/modeling/1'+path
        claims=dict(actor_id=self.actor,study_id=study or self.study,resource_ids=['*'],permissions=permissions if permissions is not None else ['read','write'],
                    expires_at=int(time.time())+(-10 if expired else 120),request_id=str(uuid.uuid4()),method=method,path=path,
                    body_sha256='0'*64 if wrong_hash else hashlib.sha256(raw).hexdigest())
        enc=lambda b:base64.urlsafe_b64encode(b).rstrip(b'=').decode()
        token=enc(b'{"alg":"HS256","typ":"JWT"}')+'.'+enc(json.dumps(claims).encode())
        token+='.'+enc(hmac.new(key or self.key,token.encode(),hashlib.sha256).digest())
        result=command(self.scope,['docker','exec','-i',self.name,'ruby','-e',HTTP],input=json.dumps(dict(method=method,path=path,body=raw.decode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})))
        response=json.loads(result.stdout); value=json.loads(response['body'])
        assert response['status']==status,(response['status'],value,status)
        from test_modeling_contract import validate
        if status>=400:
            validate('Error',value)
        else:
            import re
            spec=json.loads((ROOT/'contracts/modeling.openapi.yaml').read_text())
            relative=path.removeprefix('/modeling/1').split('?')[0]
            route=next(v for k,v in spec['paths'].items() if re.fullmatch(re.sub(r'\{[^}]+\}','[^/]+',k),relative))
            response=route[method.lower()]['responses'][str(status)]['content']['application/json']['schema']['$ref'].split('/')[-1]
            validate(response,value)
        return value

    def restart(self):
        command(self.scope,['docker','restart',self.name]); self.ready()

    def close(self):
        if self.started:
            info=json.loads(command(self.scope,['docker','inspect',self.name]).stdout)[0]
            assert info['Config']['Labels'][self.label]==self.scope.run_uuid
            command(self.scope,['docker','logs',self.name],check=False)
            try:
                command(self.scope,['docker','exec',self.name,'ruby','-e',"raise 'candidate executed' if File.exist?('/store/forbidden-candidate-import') || File.exist?('/tmp/erb-canary')"])
            finally:
                command(self.scope,['docker','rm','-f',self.name]);self.started=False
