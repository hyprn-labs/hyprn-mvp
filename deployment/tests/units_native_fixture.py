"""Actual Model3 native units fixture; isolated HTTP/JWT, stores and attestation.

The start routine follows NativeJourney's confined transport lifecycle, with
the cumulative reviewed units staging rather than its historical Model2 overlay.
No numerical data, generated program or result is synthesized.
"""
import base64
import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from aiida import orm
from pathlib import Path

import scoped_fixture as guard
from approach_native_fixture import ApproachJourney, source, literal, criterion
from hyprn_mvp_app.store import uid

REPO=Path(__file__).resolve().parents[2]


class UnitsJourney(ApproachJourney):
    def start(self):
        import secrets,time
        from hyprn_mvp_app.store import Store,uid
        from hyprn_mvp_integration.calculation import NativeExecution
        sys.path.insert(0,str(REPO/'modeling/tests'))
        from units_model_fixture import stage_sources
        _,stage,image=stage_sources()
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
        mounts={'modeling_contract.rb':'app/services/modeling_contract.rb',
            'modeling.schema.json':'config/modeling.schema.json',
            'app/services/native_materializer.rb':'app/services/native_materializer.rb',
            'app/services/native_program.rb':'app/services/native_program.rb',
            'config/modeling.units.json':'config/modeling.units.json',
            'provenance-inputs':'provenance-inputs'}
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
        """Serve the exact product build from the existing app-only HTTP child."""
        import httpx, subprocess, time
        dist=guard.scoped_path(self.scope,'artifacts/units-product-ui')
        env=guard.clean_environment(self.scope)
        if not dist.exists():
            command=['node',str(REPO/'ui/node_modules/vite/bin/vite.js'),'build',str(REPO/'ui'),
                '--config',str(REPO/'ui/vite.config.ts'),'--configLoader','runner','--outDir',str(dist)]
            result=subprocess.run(command,cwd=REPO,env=env,capture_output=True,text=True,timeout=120)
            (self.scope.root/'evidence/native-browser-build.log').write_text(result.stdout+result.stderr)
            assert result.returncode==0,'Native browser product build failed'
        child=guard.scoped_path(self.scope,'artifacts/units-web.py')
        # The reviewed application interpreter validates the scope before imports;
        # it still has no native dependencies or numerical authority.
        child.write_text("import sys\nsys.path.insert(0,"+repr(str(REPO/'deployment/tests'))+")\n"
            "import scoped_fixture as guard\nscope=guard.scope_from_environment()\n"
            "assert sys.executable==guard.APPROVED_CONTRACT_PYTHON\n"
            "sys.path.insert(0,"+repr(str(REPO/'application/src'))+")\n"
            "from fastapi.staticfiles import StaticFiles\nfrom hyprn_mvp_app import api\n"
            "original=api.create_app\ndef create(*args):\n app=original(*args)\n"
            " app.mount('/ui',StaticFiles(directory=str(guard.scoped_path(scope,'artifacts/units-product-ui')),html=True))\n return app\n"
            "api.create_app=create\nfrom combined_fixture import app_child\napp_child('web')\n")
        ready=self.scope.root/'artifacts/web-ready.json'
        if ready.exists():ready.unlink()
        self.log=(self.scope.root/'evidence/web.stderr.log').open('ab')
        self.web=subprocess.Popen([guard.APPROVED_CONTRACT_PYTHON,'-B',str(child)],cwd=REPO,env=env,stdout=self.log,stderr=self.log)
        for _ in range(100):
            if ready.exists():break
            assert self.web.poll() is None,'Web fixture failed; inspect web.stderr.log'
            time.sleep(.1)
        self.url=json.loads(ready.read_text())['url'];guard.validate_url(self.url)
        self.http=httpx.Client(base_url=self.url,trust_env=False,timeout=120)
        login=self.http.post('/api/1/session',json=dict(username='owner',password=self.setup['password']),headers={'Origin':self.url})
        assert login.status_code==200,login.text
        self.http.headers.update({'Origin':self.url,'X-CSRF-Token':login.json()['data']['csrf_token']})

    def validate_seed_contract(self,run_ids,*,mixed=False):
        """Validate genuine retained HTTP responses against the advertised operation."""
        from jsonschema import Draft202012Validator,FormatChecker,ValidationError
        from copy import deepcopy
        spec=json.loads((REPO/'contracts/hyprn-mvp.openapi.yaml').read_text())
        response=spec['paths']['/studies/{study_id}/runs/{run_id}/modified-run-seed']['get']['responses']['200']['content']['application/json']['schema']
        validator=Draft202012Validator(dict(response,components=spec['components']),format_checker=FormatChecker())
        # The previous operation union: the shared seed read union without ModifiedRunSeed4.
        components=deepcopy(spec['components'])
        union=components['schemas']['ModifiedRunSeed']['oneOf']
        assert {'$ref':'#/components/schemas/ModifiedRunSeed4'} in union
        components['schemas']['ModifiedRunSeed']['oneOf']=[v for v in union if not v['$ref'].endswith('/ModifiedRunSeed4')]
        stale=Draft202012Validator(dict(response,components=components),format_checker=FormatChecker())
        responses=[]
        for rid in run_ids:
            reply=self.http.get('/api/1/studies/'+self.sid+'/runs/'+rid+'/modified-run-seed')
            assert reply.status_code==200,reply.text
            envelope=reply.json();validator.validate(envelope)
            if envelope['data']['schema_version']=='4':
                try:stale.validate(envelope)
                except ValidationError:pass
                else:raise AssertionError('Seed4 must fail the previous operation union')
            responses.append(envelope)
        assert sorted(v['data']['schema_version'] for v in responses)==(['4'] if mixed else ['3']+['4']*6)
        proof=dict(passed=True,responses=responses,old_operation_rejects_seed4=True,
            openapi_sha256=hashlib.sha256((REPO/'contracts/hyprn-mvp.openapi.yaml').read_bytes()).hexdigest())
        (self.scope.root/'evidence/native-seed-operation-contract.json').write_text(json.dumps(proof,indent=2))
        return proof

    def browser(self,records,*,mixed=None):
        """Current UI reads genuine frozen records while the real model is down."""
        import subprocess
        from dataclasses import replace
        before=self.process_count()
        assert before==(1 if mixed else 7)
        self.validate_seed_contract([r[0] for r in records],mixed=mixed is not None)
        evidence=self.scope.root/'evidence'
        manifest=dict(study_id=self.sid,records=[dict(run_id=r,detail=h,configuration=c) for r,h,c,_ in records],
            password=self.setup['password'],outage_expected=True,process_count=before,mixed=mixed)
        # Fixture-only credentials stay in private scoped artifacts, not reports.
        (self.scope.root/'artifacts/native-browser-input.json').write_text(json.dumps(manifest))
        (self.scope.root/'artifacts/package.json').write_text('{"type":"module"}')
        config=self.scope.root/'artifacts/native-playwright.config.ts'
        config.write_text('import base from '+json.dumps(str(REPO/'ui/playwright.isolated.config.ts'))+
            ';export default {...base,testDir:'+json.dumps(str(REPO/'ui/tests'))+
            ',testMatch:["unit-native-journey.spec.ts"]};')
        original_scope=self.scope
        scope=replace(self.scope,url=self.url)
        guard.validate_scope(scope,marker=False)
        (scope.root/'scope.json').write_text(json.dumps(scope.record(),indent=2)+'\n')
        self.scope=scope
        try:
            online=subprocess.run(['node',str(REPO/'ui/node_modules/playwright/cli.js'),'test','--config',str(config),
                '--grep','@units-mixed-producer' if mixed else '@units-producer','--reporter=json'],cwd=REPO,env=guard.clean_environment(scope),capture_output=True,text=True,timeout=150)
            (evidence/'native-browser-authoring-report.json').write_text(online.stdout)
            (evidence/'native-browser-authoring-stderr.log').write_text(online.stderr)
            report=json.loads(online.stdout);online_stats=report['stats']
            assert online.returncode==0 and online_stats['expected']==1 and not report.get('errors') and not any(online_stats[k] for k in ('unexpected','skipped','flaky')),online_stats
            assert self.process_count()==before and not self.canary()['candidate_side_effect']
            self.offline()
            assert not json.loads(self.docker('inspect',self.name).stdout)[0]['State']['Running']
            result=subprocess.run(['node',str(REPO/'ui/node_modules/playwright/cli.js'),'test','--config',str(config),
                '--grep','@units-mixed-retained' if mixed else '@units-native','--reporter=json'],cwd=REPO,env=guard.clean_environment(scope),
                capture_output=True,text=True,timeout=300)
            (evidence/'native-browser-report.json').write_text(result.stdout)
            (evidence/'native-browser-stderr.log').write_text(result.stderr)
            report=json.loads(result.stdout);stats=report['stats']
            assert result.returncode==0 and stats['expected']==2 and not report.get('errors') and not any(stats[k] for k in ('unexpected','skipped','flaky')),stats
            assert self.process_count()==before
            for rid,history,_,raw in records:
                from hyprn_mvp_app.store import canonical
                assert self.request('GET','runs/'+rid)['history']==history['history']
                assert canonical(self.payload(rid))==raw
            stderr=(evidence/'web.stderr.log').read_text()
            assert 'Traceback' not in stderr and 'Exception occurred' not in stderr,stderr
            proof=dict(passed=True,tests=stats['expected']+online_stats['expected'],browser_authoring=True,processes_before=before,processes_after=self.process_count(),
                modeling_offline=True,product_ui=True,actual_http_jwt=True,native_records=[r[0] for r in records],
                source_sha256={str(p.relative_to(REPO)):hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in [REPO/'ui/tests/unit-native-journey.spec.ts',*sorted((REPO/'ui/src').rglob('*'))] if p.is_file()})
            (evidence/'native-browser-proof.json').write_text(json.dumps(proof,indent=2))
            return proof
        finally:
            self.scope=original_scope
            (self.scope.root/'scope.json').write_text(json.dumps(self.scope.record(),indent=2)+'\n')

    def execute(self,saved):
        body=dict(command_id=uid(),configuration_revision_id=saved['configuration']['configuration_revision_id'])
        with ThreadPoolExecutor(max_workers=2) as pool:
            rows=list(pool.map(lambda _:self.request('POST','runs',body,202),range(2)))
        assert rows[0]==rows[1]
        rid=rows[0]['run_id'];n=self.process_count()
        self.dispatch(rid,prepare_only=True)
        assert self.process_count()==n and not self.canary()['candidate_side_effect']
        if getattr(self,'after_prepare',None):
            from hyprn_mvp_app.store import canonical
            before=canonical(self.payload(rid)['bundle'])
            later=self.after_prepare();self.after_prepare=None
            assert canonical(self.payload(rid)['bundle'])==before
            (self.scope.root/'evidence/frozen-before-later-draft.json').write_text(json.dumps(dict(
                run_id=rid,bundle_sha256=hashlib.sha256(before).hexdigest(),later_draft=later),indent=2))
        self.dispatch(rid);detail=self.request('GET','runs/'+rid)
        assert detail['state']=='recorded' and not detail['history']['errors'],detail
        assert detail['history']['history_schema_version']=='4'
        assert detail['history']['results']['execution']['state']=='finished'
        assert self.process_count()==n+1
        self.dispatch(rid);assert self.process_count()==n+1
        assert self.request('POST','runs',body,202)['run_id']==rid
        payload=self.payload(rid);node=orm.load_node(payload['history']['association']['process_uuid'])
        assert node.is_finished_ok and not node.base.caching.is_created_from_cache
        assert node.outputs.results.creator.uuid==node.uuid
        files={p:base64.b64decode(b) for p,b in payload['bundle']['files'].items()}
        prepared=json.loads(files['preparation.json']);generator=json.loads(files['provenance/generator.json'])
        assert prepared['entrypoint']['protocol']=='hyprn_mvp.openmdao.program/1'
        assert any(p.startswith('generated/base/') for p in files)
        assert 'app/lib/whats_opt/openmdao_generator.rb' in json.dumps(generator)
        for item in prepared['files']:
            assert hashlib.sha256(files[item['path']]).hexdigest()==item['sha256']
        proof=dict(prepared=prepared,generator=generator,source_hashes={p:hashlib.sha256(b).hexdigest() for p,b in files.items()},
            process_uuid=node.uuid,run_id=rid,results=detail['history']['results'])
        (self.scope.root/'evidence'/('native-run-'+rid+'.json')).write_text(json.dumps(proof,indent=2))
        return rid,detail,node


    def model(self,name,edits,version='3'):
        study=self.http.get('/api/1/studies/'+self.sid).json()['data']
        body=dict(command_id=uid(),expected_revision=study['revision'],name=name,template='empty')
        if version=='3':body['schema_version']='3'
        draft=self.request('POST','models',body,201)
        draft=self.edit(draft,edits,version)
        return draft,self.commit(draft)

    def edit(self,draft,edits,version='3'):
        body=dict(schema_version=version,command_id=uid(),expected_revision=draft['draft_revision'],edits=edits)
        result=self.request('POST','models/'+draft['model_id']+'/edits',body)
        assert not self.canary()['candidate_side_effect']
        return result

    def commit(self,draft):
        return self.request('POST','models/'+draft['model_id']+'/commits',
            dict(command_id=uid(),expected_revision=draft['draft_revision']))

    def private(self,method,path,body=None):
        # Same production JWT client as the application, for explicit static gates.
        from hyprn_mvp_app.modeling import ModelingClient
        client=ModelingClient(self.model_url,(self.scope.root/'artifacts/fixture-model-key').read_bytes())
        return client.call(self.actor,self.sid,method,path,body)[1]['data']

    def prepared(self,model):
        from test_unit_declarations import config
        from hyprn_mvp_app.store import digest
        class Context:study=self.sid
        value=config(model,Context())
        value.update(configuration_id=uid(),configuration_revision_id=uid(),parent_revision_id=None)
        value['digest']=digest(value)
        return self.private('POST','/models/'+model['model_id']+'/prepare-execution',
            dict(command_id=uid(),model_revision_id=model['model_revision_id'],
                 configuration_snapshot=value,configuration_digest=value['digest']))
