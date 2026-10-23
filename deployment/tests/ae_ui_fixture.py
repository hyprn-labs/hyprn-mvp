"""Isolated assumptions-and-evidence browser scaffold using the shared scoped HTTP/build pattern.

Serves actual Workspace/client/API/Auth/Store on an ephemeral guarded socket.
Declared private modeling transport double exercises model authoring; no native or scientific execution.
"""

from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import subprocess
import sys
import threading
from urllib.parse import unquote, urlsplit, parse_qs

import scoped_fixture as guard

REPO = Path(__file__).resolve().parents[2]


def configuration_case(data, kind):
    """Inert captured program + synthetic outcome, solely for retained UI routes.

    Public history/Seed/configuration validators remain real. No producer, worker,
    native process or numerical result is exercised or claimed by this fixture.
    """
    import base64
    from copy import deepcopy
    import hashlib
    from execution_fixtures import fixture, criteria_free_fixture, runtime_fixture
    from hyprn_mvp_app.store import uid, digest, canonical
    from hyprn_mvp_app.execution import Submissions, assemble_bundle, executable_digest
    from hyprn_mvp_app.history import projection
    from hyprn_mvp_app.scientific_configuration import project_scientific_configuration
    from hyprn_mvp_app.modeling import validate
    store,actor,sid=data['store'],data['actor'],data['sid']
    # A criteria-free case is a configuration 6 on a Model4 revision with a result-protocol-3 run;
    # every other kind is a retained configuration that carries its own criteria.
    criteria_free=kind.startswith('criteria-free')
    case=criteria_free_fixture() if criteria_free else fixture();model=case['frozen']['model_snapshot'];config=case['frozen']['configuration'];prepared=case['prepared']
    previous_revision=model['model_revision_id']
    model.update(model_id=uid(),model_revision_id=uid(),originating_draft_revision=uid())
    study=store.study(actor,sid)
    evidence=store.add_evidence(actor,sid,uid(),dict(evidence_schema_version='3',title='Retained calibration E1',kind='note',content='Exact retained calibration observation',source_refs=['Inert reference'],resource_scope=dict(scope_version='1',kind='study',study_id=sid)))
    eid=evidence['evidence_version_id'];legacy=kind.startswith('legacy')
    if not legacy:
        model.update(schema_version=model['schema_version'] if criteria_free else '2',assumptions=[dict(assumption_id=uid(),owner=dict(kind='model'),statement='Retained model condition',evidence_links=[dict(evidence_version_id=eid,relation='supports')]),dict(assumption_id=uid(),owner=dict(kind='instance',instance_id=model['instances'][0]['instance_id']),statement='Retained component condition',evidence_links=[])])
    config.update(schema_version=config['schema_version'] if criteria_free else '2' if legacy else '3',configuration_id=uid(),configuration_revision_id=uid(),study_id=sid,model_id=model['model_id'],model_revision_id=model['model_revision_id'],name='Legacy residual' if kind=='legacy-residual' else 'Legacy explicit' if legacy else 'Criteria-free AE configuration' if criteria_free else 'Retained AE configuration',context_source=dict(kind='current_study',expected_study_revision=study['revision']),derivation=None,context_snapshot=dict(description=study['description'],boundary=study['boundary'],notes=['Retained note with\nits own line break', 'Separate retained note']),evidence_snapshots=[evidence])
    for item in config['inputs']:item['result_binding']=None
    if kind!='legacy-residual':config['inputs'][0]['provenance']['evidence_version_ids']=[eid]
    output=next(dict(instance_id=i['instance_id'],port_id=p['port_id']) for i in model['instances'] for d in model['definitions'] if d['definition_version_id']==i['definition_version_id'] for p in d['ports'] if p['direction']=='output')
    if not criteria_free:config['criteria']=[dict(criterion_id=uid(),target=output,operator='le',threshold=500,units='',evidence_version_ids=[] if kind=='legacy-residual' else [eid])]
    if kind=='grouped':
        model['assumptions'].append(dict(assumption_id=uid(),owner=deepcopy(model['assumptions'][1]['owner']),statement='Second retained component condition',evidence_links=[dict(evidence_version_id=eid,relation='context')]))
        config['criteria'][0].update(operator='eq',absolute_tolerance=0.01,relative_tolerance=0.001)
    if legacy:config["evidence_snapshots"]=[{k:evidence[k] for k in ("evidence_version_id","kind","content","source_refs")} ]
    if not legacy:
        config.update(assumptions=[dict(assumption_id=uid(),statement='Retained configuration condition',evidence_links=[dict(evidence_version_id=eid,relation='challenges')])],general_context_evidence_version_ids=[eid])
        if 'configuration_assumptions/1' not in config['required_capabilities']:config['required_capabilities'].append('configuration_assumptions/1')
    model['digest']=digest({k:v for k,v in model.items() if k!='digest'})
    config['digest']=digest({k:v for k,v in config.items() if k!='digest'})
    case['frozen']['study_revision']=study['revision']
    case['files']['model.json']=canonical(model)
    package=prepared['model_package_manifest'];package.update(schema_version=model['schema_version'],model_id=model['model_id'],model_revision_id=model['model_revision_id'])
    package['revisions']=[deepcopy(model)]
    for row in package['files']:
        if row['path']=='revisions/'+previous_revision+'.json':row.update(path='revisions/'+model['model_revision_id']+'.json',size=len(canonical(model)),sha256=hashlib.sha256(canonical(model)).hexdigest())
    package['digest']=digest({k:v for k,v in package.items() if k!='digest'})
    for row in prepared['files']:
        raw=case['files'][row['path']];row.update(size=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    prepared.update(model_id=model['model_id'],model_revision_id=model['model_revision_id'],model_digest=model['digest'],configuration_revision_id=config['configuration_revision_id'],configuration_digest=project_scientific_configuration(config)['digest'])
    prepared['executable_content_digest']=executable_digest(prepared);prepared['prepared_digest']=digest({k:v for k,v in prepared.items() if k!='prepared_digest'})
    with store.connection(write=True) as db:
        db.execute('INSERT INTO model_associations VALUES(?,?,?)',(sid,model['model_id'],uid()))
        db.execute('INSERT INTO configurations VALUES(?,?,?,?)',(config['configuration_revision_id'],config['configuration_id'],sid,json.dumps(case['frozen'])))
        db.execute('INSERT INTO configuration_families VALUES(?,?,?)',(config['configuration_id'],sid,config['configuration_revision_id']))
    run=Submissions(store,None,None).submit(actor,sid,dict(command_id=uid(),configuration_revision_id=config['configuration_revision_id']))
    bundle=assemble_bundle(run['run_id'],prepared,case['files'],case['frozen'],runtime_fixture(),dict(schema_version='1',sources=[],mappings=[]))
    request=dict(run_id=run['run_id'],scope=sid,command_id=run['command_id'],payload_digest=store.receipt(actor,sid,'run',run['command_id'])['payload_digest'],bundle_digest=bundle['manifest']['bundle_digest'])
    outputs=[dict(target=dict(instance_id=i['instance_id'],port_id=p['port_id']),value=1.0,units=p['units'],availability='available',reason=None,producer_completed=True,assigned=True) for i in model['instances'] for d in model['definitions'] if d['definition_version_id']==i['definition_version_id'] for p in d['ports'] if p['direction']=='output']
    if criteria_free:
        from criteria_free import outputs_of
        outputs=[dict(target=o['target'],value=1.0,units=o['units'],availability='available',reason=None,producer_completed=True,assigned=True) for o in outputs_of(case)]
        results=dict(schema_version='3',run_id=run['run_id'],bundle_digest=request['bundle_digest'],execution=dict(state='finished',exit_code=0,message='Synthetic UI outcome; no scientific execution'),outputs=outputs,artifacts=[])
    else:results=dict(schema_version='1',run_id=run['run_id'],bundle_digest=request['bundle_digest'],execution=dict(state='finished',exit_code=0,message='Synthetic UI outcome; no scientific execution'),convergence=dict(state='not_applicable',diagnostics_ref=None),optimization=dict(termination='not_applicable',feasibility='not_applicable'),completeness=dict(expected=len(outputs),available=len(outputs),failed=0,unavailable=0),outputs=outputs,criteria=[dict(criterion_id=c['criterion_id'],outcome='met',reason='Synthetic UI outcome') for c in config['criteria']],applicability=dict(state='unassessed',evidence_refs=[]),artifacts=[])
    association=dict(store_uuid=uid(),process_uuid=uid());payload=dict(actor=actor,frozen=deepcopy(case['frozen']),request=request,status=dict(process_state='finished',exit_status=0),bundle=dict(manifest=bundle['manifest'],files={p:base64.b64encode(raw).decode() for p,raw in bundle['files'].items()}))
    payload['history']=projection(payload,dict(request=request,bundle=bundle,results=results,assessment=None,artifacts={},errors=[])|association,association)
    with store.connection(write=True) as db:
        db.execute('UPDATE run_associations SET store_uuid=?,process_uuid=? WHERE run_id=?',(*association.values(),run['run_id']))
        db.execute("UPDATE outbox SET state='recorded',payload=? WHERE run_id=?",(json.dumps(payload),run['run_id']))
    transport=data['transport'];transport.revisions[model['model_revision_id']]=deepcopy(model)
    draft={k:deepcopy(v) for k,v in model.items() if k not in {'model_revision_id','parent_model_revision_id','originating_draft_revision','digest'}}
    draft.update(study_id=sid,name='Retained fixture model',draft_revision=model['originating_draft_revision'])
    if kind in ('unresolved','criteria-free-unresolved'):
        draft['assumptions'][0]['evidence_links'][0]['evidence_version_id']=uid();draft['draft_revision']=uid()
    validate('ModelDraft4' if criteria_free else 'ModelDraft',draft);transport.draft=draft;transport.sid=sid;transport.offline=False
    data['props']=dict(mid=model['model_id'],revision=model,instances=model['instances'])
    return dict(sid=sid,mid=model['model_id'],rid=run['run_id'],saved=case['frozen'],evidence=evidence,fixture='Inert captured program; synthetic UI outcome only')


def run(*, group):
    scope = guard.scope_from_environment()
    if sys.executable != scope.interpreter or scope.interpreter != guard.APPROVED_CONTRACT_PYTHON:
        raise ValueError('AE browser requires the reviewed application interpreter')
    from checks import AE_BROWSER_GROUPS
    if group not in AE_BROWSER_GROUPS:
        raise ValueError('Unknown AE browser group')
    for relative in ('application/src', 'application/tests', 'contracts/tests', 'integration/tests'):
        sys.path.insert(0, str(REPO / relative))

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args): pass
        def do_GET(self): self.handle_request()
        def do_POST(self): self.handle_request()
        def handle_request(self):
            length = int(self.headers.get('Content-Length', 0))
            if length < 0 or length > 2 * 1024 * 1024:
                return self.respond(413, b'Request too large', 'text/plain')
            if self.path == '/fixture' and self.command == 'GET':
                return self.respond(200, json.dumps(dict(sid=data['sid'], **data.get('props', {}))).encode(), 'application/json')
            if self.path == '/fixture/configuration-case' and self.command == 'POST' and group in {'ae-ui-configuration', 'ae-ui'}:
                guard.scope_from_environment()
                control = json.loads(self.rfile.read(length))
                if control not in ({'kind':'current'}, {'kind':'legacy'}, {'kind':'legacy-residual'}, {'kind':'unresolved'}, {'kind':'grouped'}, {'kind':'criteria-free'}, {'kind':'criteria-free-unresolved'}):
                    return self.respond(400, b'Invalid scenario', 'text/plain')
                value = configuration_case(data, control['kind'])
                return self.respond(200, json.dumps(value).encode(), 'application/json')
            if self.path == '/fixture/configuration-control' and self.command == 'POST' and group in {'ae-ui-configuration', 'ae-ui'}:
                guard.scope_from_environment()
                control = json.loads(self.rfile.read(length))
                if set(control) == {'offline'} and isinstance(control['offline'], bool):
                    data['transport'].offline = control['offline']
                elif control == {'stale_study':True}:
                    study=data['store'].study(data['actor'],data['sid'])
                    from legacy_study_support import seed_legacy_context
                    seed_legacy_context(
                        data['store'],
                        data['actor'],
                        data['sid'],
                        uid(),
                        study['revision'],
                        dict(description='Concurrent study context'),
                    )
                else: return self.respond(400, b'Invalid control', 'text/plain')
                return self.respond(200, b'{}', 'application/json')
            if self.path == '/fixture/configuration-counts' and self.command == 'GET':
                with data['store'].connection() as db:
                    counts={table:db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] for table in ('configurations','configuration_families','outbox')}
                return self.respond(200, json.dumps(counts).encode(), 'application/json')
            if self.path == '/fixture/membership' and self.command == 'POST':
                # Test-only control: fixed isolated actor/study, actual membership SQL.
                guard.scope_from_environment()
                control = json.loads(self.rfile.read(length))
                if set(control) != {'enabled'} or not isinstance(control['enabled'], bool):
                    return self.respond(400, b'Invalid fixture control', 'text/plain')
                with data['store'].connection(write=True) as db:
                    if control['enabled']:
                        db.execute('INSERT OR REPLACE INTO memberships VALUES(?,?,?)', (data['sid'], data['actor'], 'owner'))
                    else:
                        db.execute('DELETE FROM memberships WHERE study_id=? AND actor_id=?', (data['sid'], data['actor']))
                return self.respond(200, b'{}', 'application/json')
            if self.path.startswith('/api/1/'):
                # Evidence tests attach sources through the real brief draft API.
                route = urlsplit(self.path).path
                writable = (
                    route == '/api/1/session'
                    or (
                        group == 'ae-ui'
                        and (route == '/api/1/studies' or route.endswith('/model-imports')
                             or route.endswith('/brief/draft'))
                    )
                    or (group == 'ae-ui-evidence' and route == f"/api/1/studies/{data['sid']}/brief/draft")
                    or route.endswith('/evidence')
                    or (
                        group in {'ae-ui-configuration', 'ae-ui'}
                        and route.endswith('/configurations')
                    )
                    or '/evidence-families/' in route
                    or (
                        group != 'ae-ui-evidence'
                        and any(
                            route.endswith('/' + operation)
                            for operation in ('preview', 'edits', 'commits')
                        )
                    )
                    or (
                        group != 'ae-ui-evidence'
                        and route.endswith(('/explanation/draft', '/explanation/versions'))
                    )
                )
                if self.command != 'GET' and not writable:
                    return self.respond(403, b'Operation outside the bounded AE browser fixture', 'text/plain')
                from fastapi.testclient import TestClient
                with TestClient(data['client'].app, base_url=scope.url) as client:
                    response = client.request(self.command, self.path, content=self.rfile.read(length),
                        headers={k: v for k, v in self.headers.items() if k.lower() not in {'host', 'content-length', 'connection'}})
                self.send_response(response.status_code)
                for key, value in response.headers.multi_items():
                    if key.lower() not in {'content-length', 'connection', 'transfer-encoding'}:
                        self.send_header(key, value)
                self.send_header('Content-Length', str(len(response.content)))
                self.end_headers(); self.wfile.write(response.content)
                return
            route = unquote(urlsplit(self.path).path)
            path = dist / (route.removeprefix('/ui/') or 'index.html')
            if not route.startswith('/ui/') or not path.resolve().is_relative_to(dist) or not path.is_file():
                return self.respond(404, b'Not found', 'text/plain')
            self.respond(200, path.read_bytes(), mimetypes.guess_type(path)[0] or 'application/octet-stream')
        def respond(self, status, body, content_type):
            self.send_response(status); self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    try:
        scope = replace(scope, url=f'http://127.0.0.1:{server.server_port}')
        guard.validate_scope(scope, marker=False)
        (scope.root / 'scope.json').write_text(json.dumps(scope.record(), indent=2) + '\n')
        os.environ.clear(); os.environ.update(guard.clean_environment(scope))
        guard.scope_from_environment()
        import test_assumptions_evidence_api as records
        records.ORIGIN = scope.url
        data = records.api.__wrapped__(guard.scoped_path(scope, 'artifacts'))
        if group != 'ae-ui-evidence':
            import base64
            from copy import deepcopy
            from hyprn_mvp_app.store import uid, digest
            from hyprn_mvp_app.modeling import ModelingClient, validate
            from hyprn_mvp_app.api import create_app
            from hyprn_mvp_app.auth import Auth
            from fastapi.testclient import TestClient
            from test_assumption_authoring import PrivateTransport, revision, sample, D
            class BrowserTransport(PrivateTransport):
                # Exact typed response double, not the native model producer.
                offline = False
                # Concurrent HTTP reads can briefly write auth/receipt metadata. Wait for
                # those independent commits; a lock held across this call still fails.
                lock_probe_timeout = 2
                def __call__(self, method, path, raw, headers):
                    if self.offline: raise OSError('Declared private modeling outage')
                    if method == 'GET' and path.endswith('/unit-catalog'):
                        # Model and configuration editors read the authoritative unit
                        # catalog. Exact pinned
                        # catalog identity; the application still verifies its digests.
                        from test_unit_guidance_api import CATALOG
                        self.calls.append((method,path,None))
                        return 200,dict(schema_version='1',request_id=uid(),data=deepcopy(CATALOG))
                    if method == 'GET' and '/export?' in path:
                        from hyprn_mvp_app.store import canonical
                        import hashlib
                        import uuid
                        selected=self.revisions[parse_qs(urlsplit(path).query)['revision'][0]]
                        revisions=[];current=selected
                        while current:
                            revisions.insert(0,deepcopy(current))
                            current=self.revisions.get(current['parent_model_revision_id'])
                        inventory={}
                        def add_file(path,raw,media_type,role):
                            inventory[path]=dict(file_id=str(uuid.UUID(hashlib.sha256(('model-package-v1:'+path).encode()).hexdigest()[:32])),path=path,size=len(raw),sha256=hashlib.sha256(raw).hexdigest(),media_type=media_type,role=role)
                        for revision in revisions:
                            add_file('revisions/'+revision['model_revision_id']+'.json',canonical(revision),'application/json','model')
                            for source in revision['source_files']:add_file('sources/'+source['sha256']+'.py',base64.b64decode(source['bytes']),'text/x-python','source')
                        package=dict(schema_version=selected['schema_version'],source_service='Declared private transport fixture',model_id=selected['model_id'],model_revision_id=selected['model_revision_id'],revisions=revisions,files=[inventory[k] for k in sorted(inventory)],required_capabilities=[],license_notices=[])
                        package['digest']=digest(package)
                        validate('ModelPackage',package)
                        self.calls.append((method,path,None))
                        return 200,dict(schema_version='1',request_id=uid(),data=package)
                    if method == 'POST' and path.endswith('/imports'):
                        body=json.loads(raw);validate('Import',body)
                        package=body['package']
                        selected=next(r for r in package['revisions'] if r['model_revision_id']==package['model_revision_id'])
                        self.sid=body['study_id']
                        self.revisions.update({r['model_revision_id']:deepcopy(r) for r in package['revisions']})
                        self.draft={k:deepcopy(v) for k,v in selected.items() if k not in {'model_revision_id','parent_model_revision_id','originating_draft_revision','digest'}}
                        self.draft.update(study_id=self.sid,name='Imported exact model',draft_revision=uid())
                        validate('ModelDraft2',self.draft)
                    if method == 'GET' and '/revisions?' in path:
                        self.calls.append((method,path,None))
                        return 200, dict(schema_version='1',request_id=uid(),data=dict(items=[
                            {k:v[k] for k in ('model_revision_id','parent_model_revision_id','originating_draft_revision','digest')}
                            for v in reversed(list(self.revisions.values()))],next_cursor=None))
                    body=json.loads(raw) if raw else None
                    if path.endswith('/configuration-compatibility'):
                        candidate=body['configuration_candidate']
                        selected=self.revisions[candidate['model_revision_id']]
                        self.calls.append((method,path,deepcopy(body)))
                        proof=sample(D['CompatibilityResult2'])
                        proof.update(compatible=True,diagnostics=[],candidate_digest=digest(candidate),model_digest=selected['digest'],model_revision_id=selected['model_revision_id'],required_capabilities=candidate['required_capabilities'],
                            input_interpretations=[dict(target=i['target'],conversion=dict(policy='openmdao-linear-catalog-1',catalog_digest='a'*64,source_units=i['units'],destination_units=i['units'],factor=1.0,destination_value=i['value'])) for i in candidate['inputs']])
                        return 200,dict(schema_version='1',request_id=uid(),data=proof)
                    if body and path.endswith(('/preview','/edits')):
                        if body['expected_revision'] != self.draft['draft_revision']:
                            return 409,dict(schema_version='1',request_id=uid(),error=dict(code='stale_revision',message='Stale draft',current_revision=self.draft['draft_revision'],fields=[],outcome='rejected'))
                        assert all(e['kind'] in {'add_assumption','update_assumption','remove_assumption','set_annotation'} for e in body['edits'])
                        for edit in body['edits']:
                            if edit['kind']=='set_annotation':
                                # Apply notes in the same deterministic private draft response.
                                pass
                    # The product sends version3 model commands (unit
                    # guidance negotiated). As in the approach/units doubles, return the
                    # requested model branch; a preview never changes the stored draft.
                    before_upgrade=None
                    if body and path.endswith(('/preview','/edits')) and body.get('schema_version')=='3':
                        before_upgrade=deepcopy(self.draft)
                        self.draft['schema_version']='3'
                        if 'unit_declarations/1' not in self.draft['required_capabilities']:
                            self.draft['required_capabilities'].append('unit_declarations/1')
                    try:result=super().__call__(method,path,raw,headers)
                    finally:
                        if before_upgrade is not None and path.endswith('/preview'):self.draft=before_upgrade
                    if body and path.endswith(('/preview','/edits')):
                        for edit in body['edits']:
                            if edit['kind']=='set_annotation':
                                result[1]['data']['annotations']=[a for a in result[1]['data']['annotations'] if a['element_ref']!=edit['element_ref']]+[dict(element_ref=edit['element_ref'],text=edit['text'])]
                        if path.endswith('/edits'):
                            self.draft=deepcopy(result[1]['data'])
                            self.receipts[body['command_id']]['response']['data']=deepcopy(self.draft)
                    return result
            transport=BrowserTransport(data['store'],data['sid'])
            transport.caps['capabilities'].append({**transport.caps['capabilities'][0], 'id':'resolved_configuration', 'version':'3'})
            # Unit guidance negotiation (Coordinator.supports_units): contract 1.3, schema 3.
            transport.caps['contract_versions'].append('1.3');transport.caps['schema_versions'].append('3')
            transport.caps['capabilities'].append({**transport.caps['capabilities'][0], 'id':'unit_declarations', 'version':'1'})
            draft=transport.draft
            definition=draft['definitions'][0]
            source_raw=b'# Exact authored bytes; never executed by this fixture.\noutputs["y"] = inputs["x"]\n'
            import hashlib
            source=dict(encoding='base64',media_type='text/x-python',bytes=base64.b64encode(source_raw).decode(),sha256=hashlib.sha256(source_raw).hexdigest())
            definition.update(name='Repeated definition',kind='explicit_component',source_refs=[source['sha256']],annotations=[dict(element_ref=definition['definition_id'],text='Definition note stays separate.')],
                ports=[dict(port_id=uid(),definition_version_id=definition['definition_version_id'],name=symbol,code_symbol=symbol,direction=direction,value_type='real_scalar',units='') for symbol,direction in [('x','input'),('y','output')]])
            root=draft['instances'][0]
            root_definition=deepcopy(definition);root_definition.update(definition_id=uid(),definition_version_id=uid(),kind='composite',ports=[],source_refs=[],annotations=[])
            root['definition_version_id']=root_definition['definition_version_id']
            draft['definitions'].append(root_definition)
            draft['instances'][1]['name']='Component A'
            draft['instances'].append(dict(instance_id=uid(),definition_version_id=definition['definition_version_id'],name='Component B'))
            draft.update(source_files=[source],annotations=[dict(element_ref=draft['instances'][1]['instance_id'],text='Original component note.')],ports=[],connections=[],boundary_mappings=[],assumptions=[],required_capabilities=[])
            validate('ModelDraft2',draft)
            if group == 'ae-ui-configuration':
                # New configurations (version 6) need a Model4 revision with typed units and the
                # criteria-free capability beside resolved_configuration 3.
                from criteria_free import CRITERIA_FREE_CAPABILITY
                draft.update(schema_version='4',required_capabilities=['unit_declarations/1','quantity_definitions/1'])
                for item in draft['definitions']:
                    item['quantity_definitions']=[]
                    for port in item['ports']:port['units']=dict(kind='dimensionless')
                draft['ports']=[deepcopy(port) for item in draft['definitions'] for port in item['ports']]
                validate('ModelDraft4',draft)
                transport.caps['contract_versions'].append('1.4');transport.caps['schema_versions'].append('4')
                transport.caps['capabilities'].append({**transport.caps['capabilities'][0],'id':'quantity_definitions','version':'1'})
                transport.caps['capabilities'].append(deepcopy(CRITERIA_FREE_CAPABILITY))
            frozen=revision(draft);transport.revisions[frozen['model_revision_id']]=frozen
            with data['store'].connection(write=True) as db:
                db.execute('INSERT INTO model_associations VALUES(?,?,?)',(data['sid'],draft['model_id'],uid()))
            data['transport']=transport
            data['client']=TestClient(create_app(data['store'],Auth(data['store'],scope.url),ModelingClient('http://private.invalid/modeling/1',b't'*32,transport=transport)),base_url=scope.url)
            data['props']=dict(mid=draft['model_id'],instances=draft['instances'],revision=frozen)
        stage = guard.scoped_path(scope, 'artifacts/ui'); stage.mkdir()
        dist = guard.scoped_path(scope, 'artifacts/dist')
        (stage / 'package.json').write_text('{"type":"module"}')
        (stage / 'tsconfig.json').write_text('{"compilerOptions":{"jsx":"react-jsx"}}')
        (stage / 'index.html').write_text('<!doctype html><html data-theme="light"><head><meta name="viewport" content="width=device-width, initial-scale=1"></head><body><div id="root"></div><script type="module" src="/entry.tsx"></script></body></html>')
        imports = 'import {createRoot} from "react-dom/client";\nimport {useState,useRef} from "react";\n'
        for symbol, module in [('Workspace','Workspace'), ('ContextWorkspace','ContextDetails'), ('HyprnMvpApi','api'), ('EvidencePicker','EvidencePicker'), ('EvidenceReferences','EvidenceView'), ('Button','design'), ('checkPackage','exports'), ('Assumptions','Assumptions'), ('ConnectedViews','GraphView'), ('ConfigurationPanel','ConfigurationPanel')]:
            imports += 'import {' + symbol + '} from ' + json.dumps(str(REPO/'ui/src'/module)) + ';\n'
        imports += ''.join('import '+json.dumps(str(REPO/'ui/src'/p))+';\n' for p in ('design/tokens.css','design/foundry.css','styles.css'))
        # This harness exercises actual shared components and API, not yet-integrated
        # model/configuration assumption editors. Local target state is explicitly labeled.
        harness = '''
const api = new HyprnMvpApi();
window.checkModelPackage = checkPackage;
function Harness() {
  const [ready,setReady]=useState(false),[open,setOpen]=useState(false),[owner,setOwner]=useState('Component A assumption');
  const [attached,setAttached]=useState([]),[records,setRecords]=useState([]),[relation,setRelation]=useState('');
  const sid=SID;
  window.aeHarness = {close:()=>setOpen(false),owner:(value)=>setOwner(value)};
  return <ContextWorkspace api={api} studyId={sid} identity={sid+owner} navigation={null}><main><h1>Shared evidence component fixture</h1><p>Local draft target only; no model or configuration is saved.</p>
    {!ready ? <Button onClick={async()=>{await api.login('owner','correct horse battery staple');setReady(true);}}>Fixture sign in</Button> : <>
      <Button onClick={()=>setOpen(true)}>Add evidence</Button><p>Attached versions: {attached.length}; relationship: {relation}</p>
      <EvidenceReferences records={records} ids={attached}/>
      {open && <EvidencePicker api={api} studyId={sid} label={owner} ownerKey={owner} assumption={!location.search.includes('general')} scope={{scope_version:'1',kind:'study',study_id:sid}} onRecords={setRecords} onClose={()=>setOpen(false)} onAttach={(record,link)=>{setRecords(old=>[record,...old]);setAttached(old=>[...old,record.evidence_version_id]);setRelation(link||'');setOpen(false);}}/>}
    </>}
  </main></ContextWorkspace>;
}
function ConfigurationHarness() {
  const [data,setData]=useState(null),handle=useRef(null);
  window.aeConfiguration={copy:(id)=>api.configuration(SID,id).then(value=>handle.current.copy(value.configuration,value.model_snapshot)),discard:()=>handle.current.discard()};
  return <ContextWorkspace api={api} studyId={SID} identity={SID} navigation={null}><main><h1>Configuration owner isolation fixture</h1>{!data ? <Button onClick={async()=>{await api.login("owner","correct horse battery staple");const props=await (await fetch("/fixture")).json();const [study,model]=await Promise.all([api.study(SID),api.model(SID,props.mid)]);setData({study,model,revision:props.revision});}}>Fixture sign in</Button> : <ConfigurationPanel api={api} model={data.model} study={data.study} initialRevision={data.revision} authoringDirty={false} activeRun={false} onSubmit={async()=>{throw Error("No run in this fixture");}} onHandle={value=>handle.current=value} onEvidenceRecords={()=>{}}/>}</main></ContextWorkspace>;
}
createRoot(document.getElementById('root')).render(location.search.includes('configuration-harness') ? <ConfigurationHarness/> : location.search.includes('harness') ? <Harness/> : <Workspace/>);
'''.replace('SID', json.dumps(data['sid']))
        (stage / 'entry.tsx').write_text(imports + harness)
        config = dict(root=str(stage), base='/ui/', build=dict(outDir=str(dist), target='esnext'),
                      resolve=dict(alias={'react':str(REPO/'ui/node_modules/react'), 'react-dom':str(REPO/'ui/node_modules/react-dom')}))
        (stage / 'vite.config.mjs').write_text('export default ' + json.dumps(config))
        env = guard.clean_environment(scope)
        evidence = guard.scoped_path(scope, 'evidence')
        build = ['node', str(REPO/'ui/node_modules/vite/bin/vite.js'), 'build', '--config', str(stage/'vite.config.mjs'), '--configLoader', 'runner']
        built = subprocess.run(build, cwd=REPO, env=env, capture_output=True, text=True, timeout=120)
        (evidence/'fixture-build.log').write_text(built.stdout+built.stderr)
        if built.returncode: raise ValueError('AE fixture build failed; see fixture-build.log')
        # Extend the existing browser guard/config only inside this allocated root.
        browser_config = stage/'playwright.config.ts'
        browser_config.write_text('import base from '+json.dumps(str(REPO/'ui/playwright.isolated.config.ts'))+';\nexport default {...base,testDir:'+json.dumps(str(REPO/'ui/tests'))+',testMatch:["assumptions-evidence.spec.ts"]};\n')
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        command = ['node', str(REPO/'ui/node_modules/playwright/cli.js'), 'test', '--config', str(browser_config), '--grep', AE_BROWSER_GROUPS[group], '--reporter=json']
        tested = subprocess.run(command, cwd=REPO, env=env, capture_output=True, text=True, timeout=180)
        (evidence/'browser-report.json').write_text(tested.stdout)
        (evidence/'browser-stderr.log').write_text(tested.stderr)
        try: stats=json.loads(tested.stdout)['stats']
        except (ValueError, KeyError): stats={}
        forbidden = [n for n in sys.modules if n.split('.')[0] in {'aiida','openmdao','openturns'}]
        passed = tested.returncode == 0 and stats.get('expected',0)>0 and not forbidden and not any(stats.get(k,0) for k in ('unexpected','skipped','flaky'))
        record = dict(group=group, passed=passed, tests=stats.get('expected',0)+stats.get('unexpected',0), failures=stats.get('unexpected',0), skipped=stats.get('skipped',0), command=command, build_command=build, native_imports=forbidden,
                      fixture='Actual HTTP/Workspace/client/API/Auth/Store/Coordinator; declared typed private modeling transport double for model groups; no native producer or scientific execution')
        if 'transport' in data:
            (evidence/'model-transport-calls.json').write_text(json.dumps(data['transport'].calls,indent=2))
            (evidence/'model-final-draft.json').write_text(json.dumps(data['transport'].draft,indent=2))
            (evidence/'model-retained-revisions.json').write_text(json.dumps(data['transport'].revisions,indent=2))
        (evidence/'tests.json').write_text(json.dumps(record,indent=2)+'\n')
        print(json.dumps(record))
        return 0 if passed else 1
    finally:
        if 'thread' in locals(): server.shutdown(); thread.join(timeout=10)
        server.server_close()
