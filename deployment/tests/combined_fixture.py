"""Test-only HTTP/private-model transport; no computed records are synthesized.

Native controller owns the explicit backend. The reviewed app interpreter owns
FastAPI and uses the actual dispatcher stdio protocol. Model calls replay fixed
authoring commands through the pinned native generator in isolated containers.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import scoped_fixture as guard

REPO=Path(__file__).resolve().parents[2]


def write_http_response(handler,response):
    """A browser may disconnect after the application has returned its response."""
    try:
        handler.send_response(response.status_code)
        if hasattr(response, 'elapsed'):
            duration = response.elapsed.total_seconds() * 1000
            handler.send_header('Server-Timing', 'app;dur=' + str(duration))
        for key,value in response.headers.multi_items():
            if key.lower() not in {'content-length','connection','transfer-encoding'}:handler.send_header(key,value)
        handler.send_header('Content-Length',str(len(response.content)))
        handler.end_headers();handler.wfile.write(response.content)
    except (BrokenPipeError,ConnectionResetError):
        return False
    return True


def setup_model(scope,sid):
    sys.path[:0]=[str(REPO/'modeling/tests'),str(REPO/'contracts/tests')]
    from test_native_generation import public_fixture
    from test_resolved_configuration import harness,native
    source=b"outputs['y'] = inputs['a'] * 1000\noutputs['z'] = inputs['b'] * 1000\noutputs['total'] = (inputs['a'] + inputs['b'] + inputs['c'] + inputs['d']) * 1000\n"
    ports=[dict(temp_key=k,direction='input',name=k,code_symbol=k,value_type='real_scalar',units='km') for k in 'abcd']
    ports += [dict(temp_key=k,direction='output',name=k,code_symbol=k,value_type='real_scalar',units='m') for k in ('y','z','total')]
    edits=[dict(kind='create_definition',temp_key='sizing',definition_kind='explicit_component',name='Sizing',ports=ports,source=dict(encoding='base64',media_type='text/x-python',bytes=base64.b64encode(source).decode(),sha256=hashlib.sha256(source).hexdigest())),dict(kind='instantiate',temp_key='component',version_ref=dict(temp_key='sizing'))]
    _,ruby=public_fixture();start=ruby.index('edits=JSON.parse');end=ruby.index('\ndraft=c.route',start)
    ruby=ruby[:start]+"edits=JSON.parse(Base64.strict_decode64('"+base64.b64encode(json.dumps(edits).encode()).decode()+"'))"+ruby[end:]
    ruby=ruby.replace("'study_id'=>SecureRandom.uuid", "'study_id'=>'"+sid+"'",1)
    namespace=hashlib.sha256(str(scope.root).encode()).hexdigest()
    fixed="require 'securerandom'\nfixture_counter=0\nSecureRandom.define_singleton_method(:uuid) { fixture_counter+=1; h=Digest::SHA256.hexdigest('"+namespace+"'+fixture_counter.to_s); h[0,8]+'-'+h[8,4]+'-4'+h[13,3]+'-8'+h[17,3]+'-'+h[20,12] }\n"
    ruby=ruby.replace("scope={'study_id'",fixed+"scope={'study_id'",1)
    fixture=harness.__wrapped__()
    result=native(fixture,ruby+"\nputs 'PROJECTION_RESULT='+JSON.generate({'model'=>m,'configuration'=>cfg})\n")
    return result,fixture,ruby,native


class PrivateRoutes:
    def __init__(self,scope,sid):
        self.initial,self.fixture,self.ruby,self.generate=setup_model(scope,sid)
        self.files={};self.calls=[];self.offline=False
    def call(self,request):
        assert not self.offline,'Modeling contacted during outage'
        method,path,body=request['method'],request['path'],request.get('body')
        self.calls.append((method,path))
        model=self.initial['model']
        if method=='GET' and path=='/models/'+model['model_id']+'/revisions/'+model['model_revision_id']:
            return {'data':model}
        if method=='GET' and path in self.files:return {'data':self.files[path]}
        if method=='GET' and path=='/capabilities':
            # The actual private capability advertisement of the same native harness.
            if 'capabilities' not in self.initial:
                self.initial['capabilities']=self.generate(self.fixture,self.ruby+
                    "\nputs 'PROJECTION_RESULT='+JSON.generate(c.route('GET','/capabilities',{},nil)[1]['data'])\n")
            return {'data':self.initial['capabilities']}
        assert method=='POST' and path.endswith(('/configuration-compatibility','/prepare-execution'))
        encoded=base64.b64encode(json.dumps(body).encode()).decode()
        suffix="\nraise 'Retained model changed' unless m['digest']=='"+model['digest']+"'\n"
        suffix+="answer=c.route('POST',"+json.dumps(path)+",{},JSON.parse(Base64.strict_decode64('"+encoded+"')))[1]['data']\n"
        if path.endswith('/prepare-execution'):
            suffix+="stored=ModelingRevision.find_by(public_id:answer['preparation_id']).payload['bytes']; files=answer['files'].to_h { |f| [f['path'],stored.fetch(f['file_id'])['bytes']] }; answer={'prepared'=>answer,'files'=>files}\n"
        result=self.generate(self.fixture,self.ruby+suffix+"puts 'PROJECTION_RESULT='+JSON.generate(answer)\n")
        if path.endswith('/prepare-execution'):
            prepared=result['prepared']
            for item in prepared['files']:
                self.files['/preparations/'+prepared['preparation_id']+'/files/'+item['file_id']]=dict(encoding='base64',media_type=item['media_type'],sha256=item['sha256'],bytes=result['files'][item['path']])
            result=prepared
        return {'data':result}


class ModelTransport:
    """Transport double only; actual private outputs and schema validation."""
    def __init__(self,url):guard.validate_url(url);self.url=url
    def call(self,actor,sid,method,path,body=None,**kwargs):
        import httpx
        from hyprn_mvp_app.modeling import validate
        from hyprn_mvp_app.store import uid,DomainError
        if kwargs.get('request_schema'):validate(kwargs['request_schema'],body)
        with httpx.Client(trust_env=False,timeout=90) as client:
            response=client.post(self.url,json=dict(actor=actor,sid=sid,method=method,path=path,body=body))
        if response.status_code!=200:raise DomainError('backend_unavailable',503,outcome='unknown')
        result=response.json()
        if kwargs.get('response_schema'):validate(kwargs['response_schema'],dict(schema_version='1',request_id=uid(),**result),remote=True)
        return 200,result


def app_child(mode):
    scope=guard.scope_from_environment()
    assert sys.executable==guard.APPROVED_CONTRACT_PYTHON
    sys.path.insert(0,str(REPO/'application/src'))
    config=json.loads(guard.scoped_path(scope,'artifacts/combined-setup.json').read_text())
    store_path=guard.scoped_path(scope,'artifacts/combined.sqlite')
    if config.get('production_http'):
        from hyprn_mvp_app.modeling import ModelingClient
        model=ModelingClient(config['model_url'],guard.scoped_path(scope,'artifacts/fixture-model-key').read_bytes())
        assert model.transport is None
    else:
        model=ModelTransport(config['model_url'])
    if mode=='dispatch':
        from hyprn_mvp_app import dispatcher
        os.environ['HYPRN_MVP_APP_STORE']=str(store_path)
        os.environ['HYPRN_MVP_MODEL_URL']=config['model_url']
        key=guard.scoped_path(scope,'artifacts/fixture-model-key')
        os.environ['HYPRN_MVP_MODEL_KEY_FILE']=str(key)
        if not config.get('production_http'):
            dispatcher.ModelingClient=lambda *_args:model
        sys.argv=['dispatcher',*sys.argv[2:]]
        dispatcher.main()
    elif mode=='web':
        from fastapi.testclient import TestClient
        from hyprn_mvp_app.api import create_app
        from hyprn_mvp_app.auth import Auth
        from hyprn_mvp_app.store import Store
        store=Store(store_path)
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*_args):pass
            def do_GET(self):self.handle_api()
            def do_POST(self):self.handle_api()
            def do_PATCH(self):self.handle_api()
            def handle_api(self):
                assert not any(name.split('.')[0] in {'aiida','openmdao','openturns'} for name in sys.modules)
                with TestClient(app,base_url=origin) as client:
                    response=client.request(self.command,self.path,content=self.rfile.read(int(self.headers.get('Content-Length',0))),headers={k:v for k,v in self.headers.items() if k.lower() not in {'host','content-length','connection'}})
                write_http_response(self,response)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);origin='http://127.0.0.1:'+str(server.server_port)
        guard.validate_url(origin);auth=Auth(store,origin)
        with store.connection() as db:existing=db.execute('SELECT username FROM users').fetchall()
        if not existing:auth.provision('owner',config['password'])
        else:assert [r[0] for r in existing]==['owner']
        app=create_app(store,auth,model)
        guard.scoped_path(scope,'artifacts/web-ready.json').write_text(json.dumps(dict(url=origin)))
        try:server.serve_forever()
        finally:server.server_close()
    else:raise ValueError('Unknown fixture mode')
    assert not any(name.split('.')[0] in {'aiida','openmdao','openturns'} for name in sys.modules)


class Journey:
    def __init__(self,scope,backend):
        self.scope,self.backend=scope,backend;self.events=[]
    def start(self):
        import httpx,time
        from hyprn_mvp_app.store import Store,uid
        from hyprn_mvp_integration.calculation import NativeExecution
        self.store=Store(self.scope.root/'artifacts/combined.sqlite')
        # Only auth/study membership and native-authored immutable model mapping
        # are trusted setup; every configuration/run/export is a public command.
        self.actor=uid();self.study=self.store.create_study(self.actor,uid(),'Combined acceptance')
        self.sid=self.study['study_id'];self.private=PrivateRoutes(self.scope,self.sid)
        self.model=self.private.initial['model']
        with self.store.connection(write=True) as db:db.execute('INSERT INTO model_associations VALUES(?,?,?)',(self.sid,self.model['model_id'],uid()))
        outer=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*_args):pass
            def do_POST(self):
                try:answer=outer.private.call(json.loads(self.rfile.read(int(self.headers['Content-Length']))));status=200
                except Exception as error:
                    answer={'error':type(error).__name__};status=503
                    (outer.scope.root/'evidence/model-error.txt').write_text(str(error))
                raw=json.dumps(answer).encode();self.send_response(status);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        self.model_server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.model_server.serve_forever,daemon=True);self.thread.start()
        password='fixture-'+uid();self.setup=dict(model_url='http://127.0.0.1:'+str(self.model_server.server_port),password=password)
        (self.scope.root/'artifacts/combined-setup.json').write_text(json.dumps(self.setup))
        (self.scope.root/'artifacts/fixture-model-key').write_text('test-only-nonsecret-key-32-bytes-long')
        self.log=(self.scope.root/'evidence/web.stderr.log').open('wb')
        self.web=subprocess.Popen([guard.APPROVED_CONTRACT_PYTHON,'-B',__file__,'web'],cwd=REPO,env=guard.clean_environment(self.scope),stdout=self.log,stderr=self.log)
        ready=self.scope.root/'artifacts/web-ready.json'
        for _ in range(100):
            if ready.exists():break
            assert self.web.poll() is None,'Web fixture failed; inspect web.stderr.log'
            time.sleep(.1)
        self.url=json.loads(ready.read_text())['url'];guard.validate_url(self.url)
        self.http=httpx.Client(base_url=self.url,trust_env=False,timeout=120)
        session=self.http.post('/api/1/session',json=dict(username='owner',password=password),headers={'Origin':self.url})
        assert session.status_code==200,session.text
        self.http.headers.update({'Origin':self.url,'X-CSRF-Token':session.json()['data']['csrf_token']})
        # Provision returns a new principal; align only the trusted setup membership.
        with self.store.connection(write=True) as db:
            self.actor=db.execute("SELECT actor_id FROM users WHERE username='owner'").fetchone()[0]
            db.execute('UPDATE memberships SET actor_id=? WHERE study_id=?',(self.actor,self.sid))
        guard.prepare_worker_fixture(self.scope,self.backend)
        self.native=NativeExecution(backend=self.backend,root=self.scope.root)
        return self
    def close(self):
        if hasattr(self,'http'):self.http.close()
        if hasattr(self,'web'):self.web.terminate();self.web.wait(timeout=10);self.log.close()
        if hasattr(self,'model_server'):self.model_server.shutdown();self.thread.join(timeout=10);self.model_server.server_close()
    def request(self,method,suffix,body=None,status=200,**kwargs):
        response=self.http.request(method,'/api/1/studies/'+self.sid+'/'+suffix,json=body,**kwargs)
        self.events.append(dict(method=method,path=suffix,status=response.status_code,body_sha256=hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest()))
        assert response.status_code==status,response.text
        return response.json().get('data') if status<300 else response.json()['error']
    def dispatch(self,rid,**options):
        import dispatch_runtime,time
        args=['--run-id',rid]
        if options.get('prepare_only'):args.append('--prepare-only')
        if options.get('fault'):args+=['--fault',options['fault']]
        command=[guard.APPROVED_CONTRACT_PYTHON,'-B',__file__,'dispatch',*args]
        start=time.monotonic()
        with (self.scope.root/'evidence'/('dispatch-'+rid+'-'+str(len(self.events))+'.log')).open('wb') as errors:
            status=dispatch_runtime.bridge_child(self.native,command,env=guard.clean_environment(self.scope),cwd=REPO,stderr=errors)
        self.events.append(dict(dispatch=rid,command=command,exit=status,seconds=time.monotonic()-start))
        assert status==(77 if options.get('fault') else 0)
    def payload(self,rid):
        with self.store.connection() as db:return json.loads(db.execute('SELECT payload FROM outbox WHERE run_id=?',(rid,)).fetchone()[0])


class NativeJourney(Journey):
    """Actual production private HTTP/JWT, with cumulative audited source overlays.

    A unique internal network and loopback-only ephemeral endpoint replace the
    old replay transport. No native candidate runs inside the modeling service.
    """
    def docker(self,*args,check=True):
        result=subprocess.run(['docker',*args],env=guard.clean_environment(self.scope),capture_output=True,text=True,timeout=60)
        if check:assert result.returncode==0,result.stderr
        return result

    def start(self):
        import secrets,time
        from hyprn_mvp_app.store import Store,uid
        from hyprn_mvp_integration.calculation import NativeExecution
        sys.path.insert(0,str(REPO/'modeling/tests'))
        from test_assumptions import harness,PATCHES
        _,stage,image=harness.__wrapped__()
        # Scoped names: hyprn-mvp-test-<scope8>-<role>.
        base=guard.SCOPE_PREFIX+self.scope.run_uuid[:8]
        self.name=base+'-modeling'
        self.network=base+'-private';self.label='org.hyprn-mvp.test-scope='+self.scope.run_uuid
        root=guard.scoped_path(self.scope,'artifacts/private-http');root.mkdir()
        store=root/'modeling';store.mkdir();store.chmod(0o777)
        key=guard.scoped_path(self.scope,'artifacts/fixture-model-key');key.write_text(secrets.token_hex(64));key.chmod(0o444)
        rails=root/'rails.key';rails.write_text(secrets.token_hex(64));rails.chmod(0o444)
        assert self.docker('inspect',self.name,check=False).returncode!=0
        assert self.docker('network','inspect',self.network,check=False).returncode!=0
        self.docker('network','create','--internal','--label',self.label,self.network)
        self.network_created=True
        mounts={'modeling_contract.rb':'app/services/modeling_contract.rb','modeling.schema.json':'config/modeling.schema.json','app/services/native_materializer.rb':'app/services/native_materializer.rb'}
        mounts.update({name:'provenance-inputs/patches/'+name for name in PATCHES})
        # Preserve the catalog authority exactly as staged by the production builder.
        units=stage/'modeling.units.json'
        if units.exists():mounts['modeling.units.json']='config/modeling.units.json'
        args=['run','-d','--name',self.name,'--label',self.label,'--network',self.network,
            '--user','10001:10001','--read-only','--cap-drop','ALL',
            '--security-opt','no-new-privileges','--memory','768m','--pids-limit','128','--cpus','1',
            '--tmpfs','/tmp:rw,noexec,nosuid,size=192m,mode=1777',
            '--tmpfs','/native/tmp:rw,noexec,nosuid,size=32m,uid=10001,gid=10001',
            '--mount',f'type=bind,src={store},dst=/store',
            '--mount',f'type=bind,src={key},dst=/run/model.key,readonly',
            '--mount',f'type=bind,src={rails},dst=/run/rails.key,readonly']
        for src,dst in mounts.items():args+=['--mount',f'type=bind,src={stage/src},dst=/native/{dst},readonly']
        self.docker(*args,image);self.model_created=True
        info=json.loads(self.docker('inspect',self.name).stdout)[0]
        self.gateway=base+'-gateway'
        # Docker does not publish ports on internal-only networks. This confined
        # byte tunnel has no key/store/source mounts and never interprets HTTP.
        tunnel="require 'socket'; server=TCPServer.new('0.0.0.0',8080); loop { client=server.accept; Thread.new(client) { |c| u=nil; begin; u=TCPSocket.new('"+self.name+"',3000); loop { IO.select([c,u])[0].each { |s| (s==c ? u : c).write(s.readpartial(65536)) } }; rescue EOFError,IOError,SystemCallError; ensure; c.close; u&.close; end } }"
        self.docker('run','-d','--name',self.gateway,'--label',self.label,'--network','bridge',
            '--publish','127.0.0.1::8080','--user','10001:10001','--read-only','--cap-drop','ALL',
            '--security-opt','no-new-privileges','--memory','128m','--pids-limit','64','--cpus','1',
            '--entrypoint','ruby',image,'-e',tunnel)
        self.gateway_created=True
        self.docker('network','connect',self.network,self.gateway)
        gateway=json.loads(self.docker('inspect',self.gateway).stdout)[0]
        assert gateway['Mounts']==[] and gateway['HostConfig']['ReadonlyRootfs']
        port=gateway['NetworkSettings']['Ports']['8080/tcp'][0]
        assert port['HostIp']=='127.0.0.1'
        self.model_url='http://127.0.0.1:'+port['HostPort']+'/modeling/1'
        guard.validate_url(self.model_url.removesuffix("/modeling/1"))
        import httpx
        for _ in range(120):
            try:
                with httpx.Client(trust_env=False,timeout=1) as client:
                    response=client.get(self.model_url+'/capabilities')
                if response.status_code==401:break
            except httpx.HTTPError:pass
            time.sleep(.25)
        else:raise AssertionError('Private HTTP did not become ready: '+self.docker('logs',self.name).stdout)
        with httpx.Client(trust_env=False) as client:
            assert client.get(self.model_url+'/capabilities',headers={'Authorization':'Bearer forged'}).status_code==401
            assert client.post(self.model_url.replace('/modeling/1','')+'/api/v1/analyses/1/hyprn_mvp/run').status_code==404
        self.store=Store(self.scope.root/'artifacts/combined.sqlite')
        self.setup=dict(model_url=self.model_url,password='fixture-'+uid(),production_http=True)
        (self.scope.root/'artifacts/combined-setup.json').write_text(json.dumps(self.setup))
        self.start_web()
        result=self.http.post('/api/1/studies',json=dict(command_id=uid(),name='Force evidence journey'))
        assert result.status_code==201,result.text
        self.study=result.json()['data'];self.sid=self.study['study_id']
        with self.store.connection() as db:self.actor=db.execute("SELECT actor_id FROM users WHERE username='owner'").fetchone()[0]
        guard.prepare_worker_fixture(self.scope,self.backend)
        self.native=NativeExecution(backend=self.backend,root=self.scope.root)
        assert self.native.require_attestation()['passed']
        self.identity=dict(image=image,network=self.network,container=self.name,transport='production ModelingClient HTTP/JWT',
            internal_network=json.loads(self.docker('network','inspect',self.network).stdout)[0]['Internal'],
            source_hashes={str(p.relative_to(stage)):hashlib.sha256(p.read_bytes()).hexdigest() for p in stage.rglob('*') if p.is_file()},
            user=info['Config']['User'],read_only=info['HostConfig']['ReadonlyRootfs'],cap_drop=info['HostConfig']['CapDrop'],
            mounts=[m['Destination'] for m in info['Mounts']],
            gateway=dict(image=gateway['Image'],user=gateway['Config']['User'],read_only=gateway['HostConfig']['ReadonlyRootfs'],
                cap_drop=gateway['HostConfig']['CapDrop'],mounts=gateway['Mounts'],networks=list(gateway['NetworkSettings']['Networks']),tunnel=tunnel))
        assert self.identity['internal_network'] and self.identity['read_only']
        (self.scope.root/'evidence/private-http-identity.json').write_text(json.dumps(self.identity,indent=2))
        return self

    def start_web(self):
        import httpx,time
        ready=self.scope.root/'artifacts/web-ready.json'
        if ready.exists():ready.unlink()
        self.log=(self.scope.root/'evidence/web.stderr.log').open('ab')
        self.web=subprocess.Popen([guard.APPROVED_CONTRACT_PYTHON,'-B',__file__,'web'],cwd=REPO,env=guard.clean_environment(self.scope),stdout=self.log,stderr=self.log)
        for _ in range(100):
            if ready.exists():break
            assert self.web.poll() is None,'Web fixture failed; inspect web.stderr.log'
            time.sleep(.1)
        self.url=json.loads(ready.read_text())['url'];guard.validate_url(self.url)
        self.http=httpx.Client(base_url=self.url,trust_env=False,timeout=120)
        login=self.http.post('/api/1/session',json=dict(username='owner',password=self.setup['password']),headers={'Origin':self.url})
        assert login.status_code==200,login.text
        self.http.headers.update({'Origin':self.url,'X-CSRF-Token':login.json()['data']['csrf_token']})

    def restart_web(self):
        self.http.close();self.web.terminate();self.web.wait(timeout=10);self.log.close()
        self.start_web()

    def canary(self):
        result=self.docker('exec',self.name,'ruby','-rjson','-e',
            "raise 'candidate executed' if File.exist?('/store/forbidden-candidate-import'); raise 'privilege' if File.exist?('/var/run/docker.sock') || File.exist?('/usr/local/bin/python'); puts JSON.generate(candidate_side_effect:false,docker:false,python:false)")
        return json.loads(result.stdout)

    def offline(self):
        self.docker('stop',self.name)

    def close(self):
        super().close()
        if getattr(self,'gateway_created',False):
            info=json.loads(self.docker('inspect',self.gateway).stdout)[0]
            assert info['Config']['Labels']['org.hyprn-mvp.test-scope']==self.scope.run_uuid
            self.docker('rm','-f',self.gateway)
        if getattr(self,'model_created',False):
            info=json.loads(self.docker('inspect',self.name).stdout)[0]
            assert info['Config']['Labels']['org.hyprn-mvp.test-scope']==self.scope.run_uuid
            (self.scope.root/'evidence/private-http.log').write_text(self.docker('logs',self.name).stdout)
            self.docker('rm','-f',self.name)
        if getattr(self,'network_created',False):
            info=json.loads(self.docker('network','inspect',self.network).stdout)[0]
            assert info['Labels']['org.hyprn-mvp.test-scope']==self.scope.run_uuid
            self.docker('network','rm',self.network)


if __name__=='__main__':app_child(sys.argv[1])
