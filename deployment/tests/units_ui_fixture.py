"""Bounded unit UI proof: real public HTTP/API/auth/storage with a declared
private modeling transport double. No native producer or numerical proof."""
import json
import os
import sys
from pathlib import Path
import scoped_fixture as guard

REPO = Path(__file__).resolve().parents[2]

def run(*, group):
    scope = guard.scope_from_environment()
    if sys.executable != scope.interpreter or scope.interpreter != guard.APPROVED_CONTRACT_PYTHON:
        raise ValueError('Reviewed application interpreter required')
    from checks import UNITS_BROWSER_GROUPS, targets_for
    if group not in UNITS_BROWSER_GROUPS:
        raise ValueError('Unknown units browser group')
    targets_for(group)
    # No app/test/native imports, storage writes or servers before the guard.
    from copy import deepcopy
    from dataclasses import replace
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import mimetypes
    import subprocess
    import threading
    from urllib.parse import unquote, urlsplit
    for relative in ('application/src','application/tests','contracts/tests','integration/tests'):
        sys.path.insert(0, str(REPO / relative))
    from hyprn_mvp_app.api import create_app
    from hyprn_mvp_app.auth import Auth
    from hyprn_mvp_app.store import Store, uid, digest, canonical
    from hyprn_mvp_app.modeling import ModelingClient, validate
    from test_unit_guidance_api import UnitTransport
    from test_assumption_authoring import revision, sample, D
    from hyprn_mvp_app.units import resolved_model_units
    from hyprn_mvp_app.modeling import UNIT_CATALOG_DIGEST
    from fastapi.testclient import TestClient

    def package(revisions):
        import base64, hashlib
        from uuid import UUID
        files={}
        def add(path,raw,media,role):
            files[path]=dict(file_id=str(UUID(hashlib.sha256(('model-package-v1:'+path).encode()).hexdigest()[:32])),path=path,size=len(raw),sha256=hashlib.sha256(raw).hexdigest(),media_type=media,role=role)
        for item in revisions:
            add('revisions/'+item['model_revision_id']+'.json',canonical(item),'application/json','model')
            for source in item['source_files']:add('sources/'+source['sha256']+'.py',base64.b64decode(source['bytes']),'text/x-python','source')
        root=revisions[-1]
        value=dict(schema_version=root['schema_version'],source_service='Declared private unit browser double',model_id=root['model_id'],model_revision_id=root['model_revision_id'],revisions=deepcopy(revisions),files=[files[k] for k in sorted(files)],required_capabilities=root['required_capabilities'],license_notices=[])
        value['digest']=digest(value);validate('ModelPackage',value);return value

    class Models:
        def __init__(self):
            self.transports = {}
            self.client = ModelingClient('http://private.invalid/modeling/1',b't'*32,transport=self.traced)
        def traced(self, *args):
            try: return self.call(*args)
            except Exception:
                import traceback
                with (scope.root/'evidence/private-double-errors.log').open('a') as log: traceback.print_exc(file=log)
                raise
        def call(self, method, path, raw, headers):
            body = json.loads(raw) if raw else None
            # Resolve study only from the application's signed private context.
            import base64
            payload = headers['Authorization'].split('.')[1]
            sid = json.loads(base64.urlsafe_b64decode(payload+'='*(-len(payload)%4)))['study_id']
            key = urlsplit(path).path
            response = lambda value, **extra: (200, dict(schema_version='1',request_id=uid(),data=deepcopy(value),**extra))
            if key.endswith(('/capabilities','/unit-catalog')):
                catalog_transport = UnitTransport(store,sid)
                catalog_transport.caps['capabilities'].append(dict(catalog_transport.caps['capabilities'][0],id='resolved_configuration',version='3'))
                return catalog_transport(method,path,raw,headers)
            if '/commands/' in key:
                command = key.rsplit('/',1)[1]
                transport = next((t for t in self.transports.values() if command in t.receipts),None)
                return transport(method,path,raw,headers) if transport else response(dict(command_id=command,state='absent'))
            if key.endswith('/models') and method == 'POST':
                transport = UnitTransport(store,sid)
                root, version, definition = uid(),uid(),uid()
                transport.draft.update(name=body['name'],root_instance_id=root,
                    definitions=[dict(definition_id=definition,definition_version_id=version,kind='composite',name=body['name'],ports=[],source_refs=[],annotations=[],residual_port_ids=[],child_instances=[],boundary_mappings=[])],
                    instances=[dict(instance_id=root,definition_version_id=version,name=body['name'])],
                    ports=[],connections=[],boundary_mappings=[],annotations=[],source_files=[],assumptions=[])
                result = transport(method,path,raw,headers)
                self.transports[transport.draft['model_id']] = transport
                return result
            if key.endswith('/imports') and group=='units-ui-history':
                validate('ModelPackage',body['package'])
                selected=body['package']['revisions'][-1];transport=UnitTransport(store,sid)
                transport.draft={k:deepcopy(v) for k,v in selected.items() if k not in ('digest','model_revision_id','parent_model_revision_id','originating_draft_revision')}
                transport.draft.update(study_id=sid,name='Imported exact model',draft_revision=uid())
                validate('ModelDraft',transport.draft)
                transport.revisions={r['model_revision_id']:deepcopy(r) for r in body['package']['revisions']}
                self.transports[selected['model_id']]=transport
                result=response(transport.draft)[1]
                identity=dict(major='1',operation='import',target=None,study_id=sid,payload={k:v for k,v in body.items() if k!='command_id'})
                transport.receipts[body['command_id']]=dict(command_id=body['command_id'],state='committed',payload_digest=digest(identity),status=200,response={k:v for k,v in result.items() if k not in ('schema_version','request_id')})
                return 200,result
            mid = key.split('/models/')[1].split('/')[0]
            transport = self.transports[mid]
            if key.endswith('/export') and group=='units-ui-history':
                from urllib.parse import parse_qs
                selected=transport.revisions[parse_qs(urlsplit(path).query)['revision'][0]]
                revisions=[selected]
                while revisions[0]['parent_model_revision_id']:
                    revisions.insert(0,transport.revisions[revisions[0]['parent_model_revision_id']])
                return response(package(revisions))
            if key.endswith('/configuration-compatibility'):
                candidate=body['configuration_candidate'];model=transport.revisions[body['model_revision_id']]
                units=resolved_model_units(model);versions={i['instance_id']:i['definition_version_id'] for i in model['instances']}
                proof=sample(D['CompatibilityResult2'])
                proof.update(compatible=True,diagnostics=[],candidate_digest=digest(candidate),model_digest=model['digest'],model_revision_id=model['model_revision_id'],required_capabilities=candidate['required_capabilities'],input_interpretations=[])
                # Explicit bounded test double; actual OpenMDAO conversion is proven by the native tests.
                for item in candidate['inputs']:
                    target=item['target'];destination=units[(target['instance_id'],versions[target['instance_id']],target['port_id'])]
                    pair=(item['units'],destination)
                    factor=1000000 if pair==('MJ/kg','J/kg') else 1 if pair[0]==pair[1] else None
                    if factor is None:
                        proof['compatible']=False;proof['diagnostics'].append(dict(code='incompatible_units',message='Input units are incompatible with the model quantity.',path='inputs.0.units',element_ref=target['port_id']))
                    else:proof['input_interpretations'].append(dict(target=target,conversion=dict(policy='openmdao-linear-catalog-1',catalog_digest=UNIT_CATALOG_DIGEST,source_units=item['units'],destination_units=destination,factor=factor,destination_value=item['value']*factor)))
                return response(proof)
            if key.endswith('/revisions'):
                return response(dict(items=[{k:m[k] for k in ('model_revision_id','parent_model_revision_id','originating_draft_revision','digest')} for m in transport.revisions.values()],next_cursor=None))
            if method == 'GET':
                return transport(method,path,raw,headers)
            operation = key.rsplit('/',1)[1]
            draft = deepcopy(transport.draft)
            if body['expected_revision'] != draft['draft_revision']:
                return 409,dict(error=dict(code='stale_revision',message='Draft changed',fields=[],outcome='unchanged'))
            created = {}
            if operation in ('preview','edits'):
                draft['schema_version'] = body.get('schema_version','2')
                for edit in body['edits']:
                    kind = edit['kind']
                    if kind == 'create_definition':
                        did,vid=uid(),uid()
                        ports=[dict(port_id=uid(),definition_version_id=vid,**{k:v for k,v in p.items() if k!='temp_key'}) for p in edit['ports']]
                        definition=dict(definition_id=did,definition_version_id=vid,kind=edit['definition_kind'],name=edit['name'],ports=ports,source_refs=[edit['source']['sha256']],annotations=[],residual_port_ids=[],child_instances=[],boundary_mappings=[])
                        draft['definitions'].append(definition);draft['source_files'].append(edit['source'])
                        created[edit['temp_key']]=dict(definition_id=did,definition_version_id=vid,ports={p['temp_key']:port['port_id'] for p,port in zip(edit['ports'],ports)})
                    elif kind == 'instantiate':
                        ref=edit['version_ref'];vid=ref.get('definition_version_id') or created[ref['temp_key']]['definition_version_id']
                        definition=next(d for d in draft['definitions'] if d['definition_version_id']==vid)
                        iid=uid();draft['instances'].append(dict(instance_id=iid,definition_version_id=vid,name=definition['name']))
                        created[edit['temp_key']]=dict(instance_id=iid)
                    elif kind == 'revise_definition':
                        old=next(d for d in draft['definitions'] if d['definition_version_id']==edit['expected_definition_version_id'])
                        definition=deepcopy(old);vid=uid();definition['definition_version_id']=vid
                        for port in definition['ports']:port['definition_version_id']=vid
                        for change in edit['changes']:
                            if change['kind']=='update_port':
                                next(p for p in definition['ports'] if p['port_id']==change['port_id']).update(change['fields'])
                            elif change['kind']=='create_port':
                                definition['ports'].append(dict(port_id=uid(),definition_version_id=vid,**{k:v for k,v in change.items() if k not in ('kind','temp_key')}))
                            elif change['kind']=='remove_port':definition['ports']=[p for p in definition['ports'] if p['port_id']!=change['port_id']]
                            elif change['kind']=='set_source':
                                draft['source_files'].append(change['source']);definition['source_refs']=[change['source']['sha256']]
                            else:raise AssertionError(change['kind'])
                        draft['definitions'].append(definition);created[edit['temp_key']]=dict(definition_id=definition['definition_id'],definition_version_id=vid,ports={})
                    elif kind=='replace_local_instance_version':
                        next(i for i in draft['instances'] if i['instance_id']==edit['instance_id'])['definition_version_id']=created[edit['version_ref']['temp_key']]['definition_version_id']
                    elif kind=='rename_instance':next(i for i in draft['instances'] if i['instance_id']==edit['instance_id'])['name']=edit['name']
                    elif kind=='rename_model':draft['name']=edit['name']
                    elif kind=='connect':
                        draft['connections'].append(dict(connection_id=uid(),source_ref=edit['source_ref'],target_ref=edit['target_ref']))
                    else:raise AssertionError('Unsupported declared test operation: '+kind)
                draft['ports']=[deepcopy(p) for d in draft['definitions'] for p in d['ports']]
                if operation=='edits':draft['draft_revision']=uid();transport.draft=draft
                validate('ModelDraft',draft)
                result=response(draft,created_ids=created,diagnostics=[])[1]
            elif operation=='commits':
                saved=revision(draft);transport.revisions[saved['model_revision_id']]=saved;result=response(saved)[1]
            else:raise AssertionError(operation)
            if 'command_id' in body:
                identity=dict(major='1',operation=operation,target=mid,study_id=sid,payload={k:v for k,v in body.items() if k!='command_id'})
                transport.receipts[body['command_id']]=dict(command_id=body['command_id'],state='committed',payload_digest=digest(identity),status=200,response={k:v for k,v in result.items() if k not in ('schema_version','request_id')})
            return 200,result

    # Explicit in-memory retained-history double: public API/store/authorizations
    # remain real; no native bundle production, execution or integrity claim.
    from hyprn_mvp_app.history import History, RetainedRun
    from hyprn_mvp_app.result_bindings import ResultBindings
    from hyprn_mvp_app.modified_runs import ModifiedRuns
    from hyprn_mvp_app.execution import Submissions
    from hyprn_mvp_app.store import DomainError
    from execution_fixtures import runtime_fixture
    retained={}
    original_history=History.read
    original_result=ResultBindings.retained
    original_modified=ModifiedRuns.retained
    def read_history(self,actor,sid,rid,artifact_id=None):
        if rid not in retained:return original_history(self,actor,sid,rid,artifact_id)
        self.store.study(actor,sid)
        if retained[rid][0]['configuration']['study_id']!=sid:raise DomainError('resource_not_found',404)
        if artifact_id:raise DomainError('resource_not_found',404)
        return deepcopy(retained[rid][0])
    def read_retained(self,actor,sid,rid):
        if rid not in retained:
            return (original_result if isinstance(self,ResultBindings) else original_modified)(self,actor,sid,rid)
        history=read_history(self,actor,sid,rid)
        # History owns the authorized row/receipt read and the recheck token shape.
        with self.store.connection() as db:row,receipt=History(self.store).run_row(db,actor,sid,rid)
        return RetainedRun(history,deepcopy(retained[rid][1]),dict(run_id=rid,row_digest=digest(row),receipt_digest=digest(receipt)))
    History.read=read_history;ResultBindings.retained=read_retained;ModifiedRuns.retained=read_retained
    calls=[];server_errors=[];request_lock=threading.RLock()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*_args):pass
        def do_GET(self):self.guarded_request()
        def do_POST(self):self.guarded_request()
        def guarded_request(self):
            # The reused no-write-lock probe is request-local. Serialize this
            # test server so unrelated HTTP writes cannot trip that assertion.
            # UI late-response tests use declared browser transport overlays.
            with request_lock:
                try:self.handle_request()
                except (BrokenPipeError,ConnectionResetError):pass
                except Exception as error:
                    server_errors.append(dict(method=self.command,path=urlsplit(self.path).path,error=type(error).__name__))
                    raise
        def handle_request(self):
            length=int(self.headers.get('Content-Length',0))
            if length<0 or length>2*1024*1024:return self.respond(413,b'Request too large','text/plain')
            if self.path=='/fixture/read-model' and self.command=='POST' and group in ('units-ui-reading','units-ui-history'):
                guard.scope_from_environment();body=json.loads(self.rfile.read(length))
                if set(body)!={'study_id','model_id','schema'} or body['schema'] not in ('1','2','3'):return self.respond(400,b'Invalid reading fixture','text/plain')
                sid=body['study_id'];store.study(actor,sid);transport=models.transports.get(body['model_id'])
                if transport is None or transport.sid!=sid:return self.respond(404,b'Missing model','text/plain')
                # Declared data-only private snapshots. Stable port IDs are shared
                # across retained definition versions, with different labels.
                import base64,hashlib
                draft=deepcopy(transport.draft);schema=body['schema'];draft['schema_version']=schema
                draft['required_capabilities']=['unit_declarations/1','model_assumptions/1'] if schema=='3' else ['model_assumptions/1'] if schema=='2' else []
                source=b'flow = speed\n'
                if group=='units-ui-history':source=b'# <img src=x onerror=globalThis.unitSourceExecuted=true>\n'+source
                src=dict(encoding='base64',media_type='text/x-python',bytes=base64.b64encode(source).decode(),sha256=hashlib.sha256(source).hexdigest())
                draft['source_files']=[src]
                def declaration(kind,expression=None):
                    return dict(kind=kind,**(dict(expression=expression) if expression else {})) if schema=='3' else expression or ''
                def definition(name,ports):
                    vid=uid()
                    return dict(definition_id=uid(),definition_version_id=vid,kind='explicit_component',name=name,ports=[dict(port_id=uid(),definition_version_id=vid,direction=direction,name=symbol,code_symbol=symbol,value_type='real_scalar',units=units) for symbol,direction,units in ports],source_refs=[src['sha256']],residual_port_ids=[],child_instances=[],boundary_mappings=[],annotations=[])
                active=definition('Energy law',[('unknown','input',declaration('unspecified')),('ratio','input',declaration('dimensionless')),('speed','input',declaration('physical','m/s')),('flow','output',declaration('physical','m/s'))])
                old=deepcopy(active);old['definition_version_id']=uid()
                for port in old['ports']:
                    port['definition_version_id']=old['definition_version_id'];port['code_symbol']='old_'+port['code_symbol'];port['name']=port['code_symbol'];port['units']=declaration('physical','km/h')
                receiver=definition('Receiver',[('incoming','input',declaration('physical','m/s'))])
                legacy=definition('Legacy component',[('legacy','input','')])
                draft['definitions']=[draft['definitions'][0],old,active,receiver,legacy]
                producer_id,receiver_id=uid(),uid()
                draft['instances']=[draft['instances'][0],dict(instance_id=producer_id,definition_version_id=active['definition_version_id'],name='Energy law'),dict(instance_id=receiver_id,definition_version_id=receiver['definition_version_id'],name='Receiver'),dict(instance_id=uid(),definition_version_id=legacy['definition_version_id'],name='Legacy component')]
                draft['connections']=[dict(connection_id=uid(),source_ref=dict(instance_id=producer_id,port_id=active['ports'][-1]['port_id']),target_ref=dict(instance_id=receiver_id,port_id=receiver['ports'][0]['port_id']))]
                draft['ports']=[deepcopy(port) for d in draft['definitions'] for port in d['ports']]
                if schema=='1':draft.pop('assumptions',None)
                else:draft['assumptions']=[dict(assumption_id=uid(),owner=dict(kind='model'),statement='Original bounded assumption',evidence_links=[])]
                validate('ModelDraft',draft);before=revision(draft);validate('ModelRevision',before)
                after=deepcopy(before);after['model_revision_id']=uid();after['parent_model_revision_id']=before['model_revision_id']
                if schema!='1':after['assumptions'][0]['statement']='Revised bounded assumption'
                record=None
                if group=='units-ui-history' and schema!='1':
                    from test_assumption_authoring import evidence
                    record=evidence(dict(store=store,actor=actor,sid=sid),title='Retained unit evidence')
                    for value in (before,after):
                        value['assumptions'][0]['evidence_links']=[dict(evidence_version_id=record['evidence_version_id'],relation='supports')]
                        value['assumptions'].append(dict(assumption_id=uid(),owner=dict(kind='instance',instance_id=producer_id),statement='Original component assumption',evidence_links=[dict(evidence_version_id=record['evidence_version_id'],relation='context')]))
                    # A new bound definition resolves the formerly unspecified
                    # port. The original definition and immutable before remain.
                    if schema=='3':
                        resolved=deepcopy(active);resolved['definition_version_id']=uid()
                        for port in resolved['ports']:
                            port['definition_version_id']=resolved['definition_version_id']
                            if port['units']['kind']=='unspecified':port['units']=dict(kind='dimensionless')
                        after['definitions'].append(resolved)
                        next(i for i in after['instances'] if i['instance_id']==producer_id)['definition_version_id']=resolved['definition_version_id']
                        after['ports']=[deepcopy(p) for d in after['definitions'] for p in d['ports']]
                    before.pop('digest');before['digest']=digest(before);validate('ModelRevision',before)
                after.pop('digest');after['digest']=digest(after);validate('ModelRevision',after)
                transport.draft=draft
                transport.revisions.update({value['model_revision_id']:value for value in (before,after)})
                result=dict(study_id=sid,model_id=draft['model_id'],before=before,after=after,producer_id=producer_id,receiver_id=receiver_id)
                if group=='units-ui-history':result.update(package=package([before,after]),evidence=record)
                (scope.root/'evidence'/('reader-fixture-'+draft['model_id']+'.json')).write_text(json.dumps(result,indent=2)+'\n')
                return self.respond(200,json.dumps(result).encode(),'application/json')
            if self.path=='/fixture/retain' and self.command=='POST' and group in ('units-ui-configuration','units-ui-history'):
                guard.scope_from_environment();body=json.loads(self.rfile.read(length))
                if set(body)!={'study_id','configuration_revision_id'}:return self.respond(400,b'Invalid control','text/plain')
                sid=body['study_id'];store.study(actor,sid)
                with store.connection() as db:row=db.execute('SELECT payload FROM configurations WHERE study_id=? AND configuration_revision_id=?',(sid,body['configuration_revision_id'])).fetchone()
                if row is None:return self.respond(404,b'Missing configuration','text/plain')
                frozen=json.loads(row[0]);config=frozen['configuration'];model=frozen['model_snapshot']
                run=Submissions(store,None,None).submit(actor,sid,dict(command_id=uid(),configuration_revision_id=config['configuration_revision_id']))
                rid=run['run_id'];bundle_digest=digest(dict(fixture='synthetic-history',run_id=rid));units=resolved_model_units(model)
                outputs=[dict(target=dict(instance_id=i['instance_id'],port_id=p['port_id']),value=7,units=units[(i['instance_id'],i['definition_version_id'],p['port_id'])],availability='available',reason=None,producer_completed=True,assigned=True) for i in model['instances'] for d in model['definitions'] if d['definition_version_id']==i['definition_version_id'] for p in d['ports'] if p['direction']=='output']
                results=dict(schema_version='1',run_id=rid,bundle_digest=bundle_digest,execution=dict(state='finished',exit_code=0,message='Synthetic history double'),convergence=dict(state='not_applicable',diagnostics_ref=None),optimization=dict(termination='not_applicable',feasibility='not_applicable'),completeness=dict(expected=len(outputs),available=len(outputs),failed=0,unavailable=0),outputs=outputs,criteria=[dict(criterion_id=c['criterion_id'],outcome='unresolved',reason='Synthetic fixture') for c in config['criteria']],applicability=dict(state='unassessed',evidence_refs=[]),artifacts=[])
                manifest=dict(schema_version='6',bundle_digest=bundle_digest,model_digest=model['digest'],configuration_digest=config['digest'],dependencies=[],runtime=runtime_fixture()['runtime'],approach_digest=None,approach_closure_digest=None)
                history=dict(history_schema_version='4',configuration=config,model_snapshot=model,context=config['context_snapshot'],evidence=config['evidence_snapshots'],bundle={k:v for k,v in manifest.items() if k!='runtime'},results=results,assessment=None,artifacts=[],errors=[],approach_closure=frozen['approach_closure'])
                retained[rid]=(history,dict(bundle=dict(manifest=manifest),frozen=frozen))
                with store.connection(write=True) as db:
                    db.execute('UPDATE run_associations SET store_uuid=?,process_uuid=? WHERE run_id=?',(uid(),uid(),rid))
                    db.execute("UPDATE outbox SET state='recorded',payload=json_set(payload,'$.status',json(?)) WHERE run_id=?",(json.dumps(dict(process_state='finished',exit_status=0)),rid))
                return self.respond(200,json.dumps(dict(run_id=rid)).encode(),'application/json')
            if self.path=='/fixture/revoke'  and self.command=='POST':
                guard.scope_from_environment();body=json.loads(self.rfile.read(length))
                if set(body)!={'study_id'}:return self.respond(400,b'Invalid control','text/plain')
                store.study(actor,body['study_id'])
                with store.connection(write=True) as db:db.execute('DELETE FROM memberships WHERE study_id=? AND actor_id=?',(body['study_id'],actor))
                return self.respond(200,b'{}','application/json')
            if self.path.startswith('/api/1/'):
                route=urlsplit(self.path).path
                writable=route in ('/api/1/session','/api/1/studies') or '/models' in route or '/configurations' in route or (group=='units-ui-history' and '/model-imports' in route) or (group=='units-ui-reading' and '/approach' in route)
                if self.command!='GET' and not writable:return self.respond(403,b'Outside unit authoring fixture','text/plain')
                raw=self.rfile.read(length)
                with TestClient(app,base_url=scope.url) as client:
                    result=client.request(self.command,self.path,content=raw,headers={k:v for k,v in self.headers.items() if k.lower() not in ('host','content-length','connection')})
                if route!='/api/1/session':calls.append(dict(method=self.command,path=self.path,status=result.status_code,request=json.loads(raw) if raw else None,response=result.json()))
                self.send_response(result.status_code)
                for key,value in result.headers.multi_items():
                    if key.lower() not in ('content-length','connection','transfer-encoding'):self.send_header(key,value)
                self.send_header('Content-Length',str(len(result.content)));self.end_headers()
                try:self.wfile.write(result.content)
                except (BrokenPipeError,ConnectionResetError):pass
                return
            route=unquote(urlsplit(self.path).path);path=dist/(route.removeprefix('/ui/') or 'index.html')
            if not route.startswith('/ui/') or not path.resolve().is_relative_to(dist) or not path.is_file():return self.respond(404,b'Not found','text/plain')
            self.respond(200,path.read_bytes(),mimetypes.guess_type(path)[0] or 'application/octet-stream')
        def respond(self,status,body,kind):
            self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    try:
        scope=replace(scope,url=f'http://127.0.0.1:{server.server_port}')
        guard.validate_scope(scope,marker=False)
        (scope.root/'scope.json').write_text(json.dumps(scope.record(),indent=2)+'\n')
        os.environ.clear();os.environ.update(guard.clean_environment(scope));guard.scope_from_environment()
        store=Store(guard.scoped_path(scope,'artifacts/units-ui.sqlite'));auth=Auth(store,scope.url)
        actor=auth.provision('owner','correct horse battery staple');models=Models();app=create_app(store,auth,models.client)
        stage=guard.scoped_path(scope,'artifacts/ui');stage.mkdir();dist=guard.scoped_path(scope,'artifacts/dist');evidence=guard.scoped_path(scope,'evidence')
        (stage/'package.json').write_text('{"type":"module"}')
        (stage/'tsconfig.json').write_text('{"compilerOptions":{"jsx":"react-jsx"}}')
        (stage/'index.html').write_text('<!doctype html><html><body><div id="root"></div><script type="module" src="/entry.tsx"></script></body></html>')
        imports='import {createRoot} from "react-dom/client";\n'
        imports+='import {Workspace} from '+json.dumps(str(REPO/'ui/src/Workspace'))+';\n'
        imports+='import * as unitLabels from '+json.dumps(str(REPO/'ui/src/unitLabels'))+';\n'
        imports+='import {HyprnMvpApi} from '+json.dumps(str(REPO/'ui/src/api'))+';\n'
        imports+=''.join('import '+json.dumps(str(REPO/'ui/src'/p))+';\n' for p in ('design/tokens.css','design/foundry.css','styles.css'))
        if group=='units-ui-reading':
            imports+='import {ModelAssumptionChanges} from '+json.dumps(str(REPO/'ui/src/ChangePreview'))+';\n'
        if group=='units-ui-history':
            imports+='import {ComparisonView} from '+json.dumps(str(REPO/'ui/src/ComparisonView'))+';\n'
            imports+='import * as exports from '+json.dumps(str(REPO/'ui/src/exports'))+';\n'
        reader='window.showAssumptionChanges=(before,after)=>root.render(<ModelAssumptionChanges before={before} after={after}/>);' if group=='units-ui-reading' else ''
        if group=='units-ui-history':
            reader='window.exportHelpers=exports;window.showComparison=(study,snapshot)=>root.render(<ComparisonView api={window.unitsApi} study={study} scope={{snapshot,values:{kind:"model"},selection:{kind:"none"},unsaved:false}} root={{current:document.body}} navigate={f=>f()} onImported={async()=>{}} showComparison/>);'
        (stage/'entry.tsx').write_text(imports+'window.unitLabels=unitLabels;window.unitsApi=new HyprnMvpApi();const root=createRoot(document.getElementById("root"));'+reader+'root.render(<Workspace/>);')
        config=dict(root=str(stage),base='/ui/',build=dict(outDir=str(dist),target='esnext'),resolve=dict(alias={'react':str(REPO/'ui/node_modules/react'),'react-dom':str(REPO/'ui/node_modules/react-dom')}))
        (stage/'vite.config.mjs').write_text('export default '+json.dumps(config))
        env=guard.clean_environment(scope)
        build=['node',str(REPO/'ui/node_modules/vite/bin/vite.js'),'build','--config',str(stage/'vite.config.mjs'),'--configLoader','runner']
        built=subprocess.run(build,cwd=REPO,env=env,capture_output=True,text=True,timeout=120)
        (evidence/'fixture-build.log').write_text(built.stdout+built.stderr)
        if built.returncode:raise ValueError('Units harness build failed')
        configfile=stage/'playwright.config.ts'
        spec=Path(targets_for(group)[1]).name
        configfile.write_text('import base from '+json.dumps(str(REPO/'ui/playwright.isolated.config.ts'))+';export default {...base,testDir:'+json.dumps(str(REPO/'ui/tests'))+',testMatch:['+json.dumps(spec)+']};')
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        command=['node',str(REPO/'ui/node_modules/playwright/cli.js'),'test','--config',str(configfile),'--grep',UNITS_BROWSER_GROUPS[group],'--reporter=json']
        tested=subprocess.run(command,cwd=REPO,env=env,capture_output=True,text=True,timeout=420)
        (evidence/'browser-report.json').write_text(tested.stdout);(evidence/'browser-stderr.log').write_text(tested.stderr)
        (evidence/'public-api-calls.json').write_text(json.dumps(calls,indent=2)+'\n')
        try:stats=json.loads(tested.stdout)['stats']
        except (ValueError,KeyError):stats={}
        native=[n for n in sys.modules if n.split('.')[0] in ('aiida','openmdao','openturns')]
        passed=not server_errors and not (evidence/'private-double-errors.log').exists() and tested.returncode==0 and stats.get('expected',0)>0 and not native and not any(stats.get(k,0) for k in ('unexpected','skipped','flaky'))
        record=dict(group=group,passed=passed,tests=stats.get('expected',0)+stats.get('unexpected',0),failures=stats.get('unexpected',0),skipped=stats.get('skipped',0),command=command,build_command=build,native_imports=native,server_errors=server_errors,fixture='Real product/HTTP/API/auth/storage; serialized test HTTP and explicit private model transport and retained-history doubles; no numerical execution or native proof')
        (evidence/'tests.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record));return 0 if passed else 1
    finally:
        if 'thread' in locals():server.shutdown();thread.join(timeout=10)
        server.server_close()
