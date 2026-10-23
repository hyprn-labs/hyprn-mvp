"""Guarded approach controller browser harness: real HTTP/API/auth/commands/storage.

Account provisioning is administrative setup. Scientific authoring uses public
HTTP commands. Method tests add a declared private modeling transport and the
existing Submissions retained-failure handoff. No native producer or candidate
execution is used; these fixtures make no native numerical acceptance claim.
"""
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import shutil
import sqlite3
import hashlib
import re
import time
import mimetypes
import os
from pathlib import Path
import subprocess
import sys
import threading
from urllib.parse import unquote, urlsplit
import scoped_fixture as guard

REPO = Path(__file__).resolve().parents[2]


def run(*, group):
    scope = guard.scope_from_environment()
    if sys.executable != scope.interpreter or scope.interpreter != guard.APPROVED_CONTRACT_PYTHON:
        raise ValueError('Reviewed application interpreter required')
    from checks import APPROACH_BROWSER_GROUPS, APPROACH_BROWSER_SPECS
    if group not in APPROACH_BROWSER_GROUPS:
        raise ValueError('Unknown approach browser group')
    requested_group = group
    if group == 'exploration-answer-ui':
        group = 'approach-ui-method'
    for relative in ('application/src','application/tests','contracts/tests','integration/tests'):
        sys.path.insert(0, str(REPO / relative))
    from hyprn_mvp_app.api import create_app
    from hyprn_mvp_app.auth import Auth
    from hyprn_mvp_app.store import Store
    from fastapi.testclient import TestClient

    class NoModeling:
        def call(self, *_args, **_kwargs):
            raise AssertionError('Proposed approach controller must not call modeling')

    cases = {}
    calls = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args): pass
        def do_GET(self): self.handle_request()
        def do_POST(self): self.handle_request()
        def do_DELETE(self): self.handle_request()
        def handle_request(self):
            length = int(self.headers.get('Content-Length', 0))
            if length < 0 or length > 2 * 1024 * 1024:
                return self.respond(413, b'Request too large', 'text/plain')
            if (
                group in ('calculations-ui', 'study-answer-ui')
                and self.path == '/fixture/calculation-seed'
                and self.command == 'POST'
            ):
                from calculation_fixture import seed, sibling
                guard.scope_from_environment();body=json.loads(self.rfile.read(length))
                if set(body)!={'study_id'}:return self.respond(400,b'Invalid fixture request','text/plain')
                store.study(actor,body['study_id'])
                seeded=seed(dict(store=store,actor=actor,sid=body['study_id']))
                other=sibling(dict(store=store,sid=body['study_id']),seeded['frozen'],name='Cruise point B')
                run=seeded['record']([150,151])
                from hyprn_mvp_app.brief import Briefs, ensure as ensure_brief
                from hyprn_mvp_app.store import uid
                ensure_brief(store);briefs=Briefs(store)
                criteria=[dict(criterion_id=uid(),kind='constraint',name='u',statement='',operator='lt',threshold=200,units='',evidence_links=[]),
                    dict(criterion_id=uid(),kind='objective',name='y',statement='',direction='minimize',units='',evidence_links=[])]
                alternatives = []
                if group == 'study-answer-ui':
                    alternatives = [
                        dict(
                            alternative_id=uid(),
                            name='Design A',
                            description='',
                            reason='Reference design',
                        )
                    ]
                existing_brief = briefs.state(actor, body['study_id'])['draft']
                draft = briefs.save_draft(
                    actor,
                    body['study_id'],
                    dict(
                        command_id=uid(),
                        expected_revision=existing_brief['revision'] if existing_brief else None,
                        content=dict(
                            schema_version='1',
                            question='Which response stays below the limit?',
                            original_question=None,
                            elaboration=None,
                            scope='',
                            alternatives=alternatives,
                            criteria=criteria,
                            assumptions=[],
                            limits=[],
                            open_questions=[],
                        ),
                    ),
                )
                briefs.save_version(
                    actor,
                    body['study_id'],
                    dict(command_id=uid(), expected_revision=draft['revision']),
                )
                return self.respond(
                    200,
                    json.dumps(
                        dict(
                            configuration=seeded['config']['configuration_revision_id'],
                            configuration_name=seeded['config']['name'],
                            other=other,
                            run=run,
                        )
                    ).encode(),
                    'application/json',
                )
            if (
                group in ('calculations-ui', 'study-answer-ui')
                and self.path == '/fixture/calculation-sample-seed'
                and self.command == 'POST'
            ):
                # A version-6 reference configuration (two free dimensionless inputs, saved 0
                # and 7), marked as a reference, and a current ready execution observation.
                import time
                from criteria_free import bind_case, insert_case
                from hyprn_mvp_app.calculations import Calculations
                from hyprn_mvp_app.store import digest, uid
                from test_calculation_designs_api import RUNTIME

                guard.scope_from_environment()
                body = json.loads(self.rfile.read(length))
                if set(body) != {'study_id'}:
                    return self.respond(400, b'Invalid fixture request', 'text/plain')
                study = store.study(actor, body['study_id'])
                case = bind_case('unrelated', body['study_id'], study_revision=study['revision'])
                config = case['frozen']['configuration']
                config['name'] = 'Sweep reference'
                for item, value in zip(config['inputs'], [0, 7], strict=True):
                    item['value'] = value
                config['digest'] = digest({k: v for k, v in config.items() if k != 'digest'})
                insert_case(store, body['study_id'], case)
                Calculations(store).mark(
                    actor,
                    body['study_id'],
                    dict(
                        command_id=uid(),
                        configuration_revision_id=config['configuration_revision_id'],
                        action='set',
                    ),
                )
                store.publish_execution_observation('ready', None, time.time(), RUNTIME)
                return self.respond(
                    200,
                    json.dumps(
                        dict(
                            reference=config['configuration_revision_id'],
                            reference_name=config['name'],
                        )
                    ).encode(),
                    'application/json',
                )
            if (
                group in ('calculations-ui', 'study-answer-ui')
                and self.path == '/fixture/calculation-step'
                and self.command == 'POST'
            ):
                # The trusted dispatcher's steps with data-only design and fit stand-ins; they
                # never import candidate code and establish no numerical accuracy.
                import time
                from hyprn_mvp_app.calculation_designs import CalculationSamples
                from hyprn_mvp_app.calculation_estimates import Estimates
                from hyprn_mvp_app.configuration import Configurations
                from test_calculation_designs_api import RUNTIME, DesignTransport, FitTransport

                guard.scope_from_environment()
                body = json.loads(self.rfile.read(length))
                if body not in ({'action': 'observe'}, {'action': 'dispatch'}, {'action': 'record'}):
                    return self.respond(400, b'Invalid fixture request', 'text/plain')
                store.publish_execution_observation('ready', None, time.time(), RUNTIME)
                steps = 0
                if body['action'] == 'record':
                    from criteria_free import bind_case, record_run
                    from test_calculation_designs_api import point_case
                    from hyprn_mvp_app.calculations import _frozen_configuration
                    with store.connection() as db:
                        versions = db.execute('SELECT study_id,payload FROM calculation_versions').fetchall()
                    seen = set()
                    for row in versions:
                        version = json.loads(row['payload'])
                        if version['content']['design']['kind'] != 'sampled':
                            continue
                        sid = row['study_id']
                        case = bind_case('unrelated', sid)
                        for member in version['content']['configuration_revision_ids']:
                            if member in seen:
                                continue
                            seen.add(member)
                            with store.connection() as db:
                                frozen = _frozen_configuration(db, sid, member)
                            record_run(store, actor, sid, point_case(dict(case=case), frozen), [42])
                            steps += 1
                if body['action'] == 'dispatch':
                    samples = CalculationSamples(store, Configurations(store, None))
                    estimates = Estimates(store)
                    while samples.process_one(DesignTransport()) or estimates.process_one(
                        FitTransport()
                    ):
                        steps += 1
                    from hyprn_mvp_app.analysis_execution import AnalysisExecution
                    from hyprn_mvp_app.execution import Submissions
                    runner = AnalysisExecution(store)
                    steps += int(runner.process_one(Submissions(store, None, None)))
                    estimates.process_one(FitTransport())
                    runner.process_one(Submissions(store, None, None))
                return self.respond(200, json.dumps(dict(steps=steps)).encode(), 'application/json')
            if (
                group
                in (
                    'approach-ui-controller',
                    'approach-ui-method',
                    'approach-ui-demo',
                    'approach-ui-assumptions',
                    'approach-ui-history',
                )
                and self.path == '/fixture/model-package'
                and self.command == 'GET'
            ):
                from approach_model_fixture import example
                return self.respond(200,json.dumps(example()).encode(),'application/json')
            if (
                group
                in (
                    'approach-ui-method',
                    'approach-ui-demo',
                    'approach-ui-assumptions',
                    'approach-ui-history',
                )
                and self.path == '/fixture/failure-package'
                and self.command == 'GET'
            ):
                from approach_model_fixture import failure_case,package
                from hyprn_mvp_app.store import uid
                case=failure_case();key=uid();cases[key]=case
                return self.respond(200,json.dumps(dict(key=key,package=package(case['frozen']['model_snapshot']),configuration=case['frozen']['configuration'])).encode(),'application/json')
            if (
                group
                in (
                    'approach-ui-method',
                    'approach-ui-demo',
                    'approach-ui-assumptions',
                    'approach-ui-history',
                )
                and self.path
                in (
                    '/fixture/retain-failure',
                    '/fixture/retain-failed-outcome',
                    '/fixture/retain-uncertain',
                )
                and self.command == 'POST'
            ):
                from approach_model_fixture import retain_failure
                guard.scope_from_environment();body=json.loads(self.rfile.read(length))
                if set(body)!={'key','study_id','run_id'} or body['key'] not in cases:return self.respond(400,b'Invalid fixture handoff','text/plain')
                store.study(actor,body['study_id'])
                from hyprn_mvp_app.execution import Submissions
                Submissions(store,None,None).read(actor,body['study_id'],body['run_id'])
                result=retain_failure(store,actor,body['study_id'],body['run_id'],cases[body['key']],complete=self.path == '/fixture/retain-failed-outcome',uncertain=self.path == '/fixture/retain-uncertain')
                return self.respond(200,json.dumps(result).encode(),'application/json')
            if (
                group
                in (
                    'approach-ui-method',
                    'approach-ui-demo',
                    'approach-ui-assumptions',
                    'approach-ui-history',
                )
                and self.path in ('/fixture/model-outage', '/fixture/model-available')
                and self.command == 'POST'
            ):
                modeling.offline=self.path == '/fixture/model-outage'
                return self.respond(200,b'{}','application/json')
            if group == 'approach-ui-history' and self.path == '/fixture/process-export' and self.command == 'POST':
                from hyprn_mvp_app.computational_export import records_for_store, inspect_record
                from approach_model_fixture import synthetic_archive
                guard.scope_from_environment();body=json.loads(self.rfile.read(length))
                if set(body)!={'study_id','request_id'}:return self.respond(400,b'Invalid request','text/plain')
                service=records_for_store(store);service.status(actor,body['study_id'],body['request_id'])
                service.process_one(lambda preflight:synthetic_archive(preflight,service._collect(actor,body['study_id'],preflight['roots'])[0]),request_id=body['request_id'])
                result=service.status(actor,body['study_id'],body['request_id'])
                proof=dict(record=result,fixture='Synthetic archive transport; no native row semantics claim')
                if result['state']=='ready':
                    raw=service.download(actor,body['study_id'],body['request_id']);proof['manifest']=inspect_record(raw)
                    (scope.root/'evidence'/('approach-export-'+body['request_id']+'.zip')).write_bytes(raw)
                (scope.root/'evidence'/('approach-export-'+body['request_id']+'.json')).write_text(json.dumps(proof,indent=2))
                return self.respond(200,json.dumps(proof).encode(),'application/json')
            if self.path == '/fixture/revoke' and self.command == 'POST':
                # Administrative fault injection only: no scientific row writes.
                guard.scope_from_environment()
                body = json.loads(self.rfile.read(length))
                if set(body) != {'study_id'}:
                    return self.respond(400,b'Invalid control','text/plain')
                store.study(actor,body['study_id'])
                with store.connection(write=True) as db:
                    db.execute('DELETE FROM memberships WHERE study_id=? AND actor_id=?',(body['study_id'],actor))
                return self.respond(200,b'{}','application/json')
            if group=='approach-ui-reading' and self.path == '/fixture/reader' and self.command == 'POST':
                # P4-S6b administrative setup only: one 'reader' account with reader membership
                # in the named owner study, so the browser can prove a reader cannot archive.
                guard.scope_from_environment()
                body = json.loads(self.rfile.read(length))
                if set(body) != {'study_id'}:
                    return self.respond(400,b'Invalid control','text/plain')
                from hyprn_mvp_app.auth import password_hash
                from hyprn_mvp_app.store import uid
                current = store.study(actor,body['study_id'])
                with store.connection(write=True) as db:
                    row = db.execute("SELECT actor_id FROM users WHERE username='reader'").fetchone()
                    reader = row[0] if row else uid()
                    if not row: db.execute('INSERT INTO users(actor_id,username,password_hash) VALUES(?,?,?)',(reader,'reader',password_hash('correct horse battery staple')))
                store.set_membership(actor,body['study_id'],uid(),current['revision'],reader,'reader')
                return self.respond(200,b'{}','application/json')
            if group=='approach-ui-history' and self.path=='/fixture/native-pair' and self.command=='GET':
                guard.scope_from_environment()
                return self.respond(200,json.dumps(native_pair).encode(),'application/json')
            if self.path.startswith('/api/1/'):
                route = urlsplit(self.path).path
                # P4-S6b: study archive/restore commands (S6a) for the Home archive journey.
                answer_write = (
                    group in ('approach-ui-method', 'approach-ui-demo')
                    and self.command == 'POST'
                    and re.fullmatch(r'/api/1/studies/[0-9a-f-]{36}/answers', route) is not None
                )
                writable = (
                    route in ('/api/1/session', '/api/1/studies')
                    or re.fullmatch(r'/api/1/studies/[0-9a-f-]{36}/(archive|restore)', route)
                    is not None
                    or '/approach/' in route
                    or re.fullmatch(r'/api/1/studies/[0-9a-f-]{36}/brief/(draft|versions)', route)
                    is not None
                    or re.fullmatch(r'/api/1/studies/[0-9a-f-]{36}/answer/(draft|versions)', route)
                    is not None
                    or answer_write
                    or (group in ('brief-ui', 'study-answer-ui') and re.fullmatch(
                        r'/api/1/studies/[0-9a-f-]{36}/(evidence|evidence-families/[0-9a-f-]{36}/versions)', route
                    ) is not None)
                    or group in ('calculations-ui', 'study-answer-ui')
                    and re.fullmatch(
                        r'/api/1/studies/[0-9a-f-]{36}/'
                        r'((?:calculations|analyses)(/[0-9a-f-]{36}/versions)?|reference-marks|'
                        r'(?:calculation|analysis)-samples|(?:calculation|analysis)-estimates|'
                        r'configurations(?:/preview)?|'
                        r'(?:calculation|analysis)-versions/[0-9a-f-]{36}/(?:run-requests|execution))',
                        route,
                    )
                    is not None
                    or group
                    in (
                        'approach-ui-method',
                        'approach-ui-demo',
                        'approach-ui-assumptions',
                        'approach-ui-history',
                    )
                    and any(
                        part in route
                        for part in (
                            '/model-imports',
                            '/models/',
                            '/configurations',
                            '/runs',
                            '/evidence',
                            '/computational-record',
                        )
                    )
                )
                if self.command != 'GET' and not writable:
                    return self.respond(403, b'Outside bounded controller fixture', 'text/plain')
                raw = self.rfile.read(length)
                with TestClient(app, base_url=scope.url) as client:
                    response = client.request(self.command, self.path, content=raw, headers={k:v for k,v in self.headers.items() if k.lower() not in {'host','content-length','connection'}})
                # No credentials/cookies/CSRF tokens in retained logs.
                if route != '/api/1/session':
                    calls.append(dict(method=self.command, path=self.path, status=response.status_code, request=json.loads(raw) if raw else None, response=response.json() if 'json' in response.headers.get('content-type','') else {'binary_size':len(response.content)}))
                self.send_response(response.status_code)
                for key,value in response.headers.multi_items():
                    if key.lower() not in {'content-length','connection','transfer-encoding'}: self.send_header(key,value)
                self.send_header('Content-Length',str(len(response.content))); self.end_headers()
                try: self.wfile.write(response.content)
                except (BrokenPipeError, ConnectionResetError): pass
                return
            route = unquote(urlsplit(self.path).path)
            path = dist / (route.removeprefix('/ui/') or 'index.html')
            if not route.startswith('/ui/') or not path.resolve().is_relative_to(dist) or not path.is_file():
                return self.respond(404,b'Not found','text/plain')
            self.respond(200,path.read_bytes(),mimetypes.guess_type(path)[0] or 'application/octet-stream')
        def respond(self,status,body,content_type):
            self.send_response(status); self.send_header('Content-Type',content_type)
            self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)

    server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
    try:
        scope = replace(scope,url=f'http://127.0.0.1:{server.server_port}')
        guard.validate_scope(scope,marker=False)
        (scope.root/'scope.json').write_text(json.dumps(scope.record(),indent=2)+'\n')
        os.environ.clear(); os.environ.update(guard.clean_environment(scope)); guard.scope_from_environment()
        database=guard.scoped_path(scope,'artifacts/approach-ui.sqlite')
        native_pair=None
        if group=='approach-ui-history':
            # Reuse retained calculations through a private read-only backup of the application store
            # of the manifest-verified durable native fixture (durable_fixture; fails closed if absent or changed).
            # No native import, profile creation, producer start or source write.
            import durable_fixture
            from contextlib import closing
            source=durable_fixture.application_store();retained=durable_fixture.identities()
            # immutable=1: no -journal/-wal/-shm sidecar may appear in the durable directory.
            with closing(sqlite3.connect(source.as_uri()+'?mode=ro&immutable=1',uri=True)) as original,closing(sqlite3.connect(database)) as copied: original.backup(copied)
            durable_fixture.manifest()  # Durable inventory still exact after the backup.
        store = Store(database)
        auth = Auth(store,scope.url)
        if group=='approach-ui-history':
            auth.recover('correct horse battery staple')
            with store.connection() as db: actor=db.execute("SELECT actor_id FROM users WHERE username='owner'").fetchone()[0]
        else: actor = auth.provision('owner','correct horse battery staple')
        if group in ('calculations-ui', 'study-answer-ui'):
            # Input-first sampling reads the model and saves explicit inputs through public APIs.
            from approach_model_fixture import Models, SamplingModels
            outage = SamplingModels(store) if group == 'calculations-ui' else Models(store)
            outage.offline = group != 'calculations-ui'
        if group in (
            'approach-ui-method',
            'approach-ui-demo',
            'approach-ui-assumptions',
            'approach-ui-history',
        ):
            from approach_model_fixture import Models
            # Existing catalog transport, data-only; never a native producer.
            from test_unit_guidance_api import UnitTransport
            class FindingsModels(Models):
                def call(self,method,path,raw,headers):
                    body=json.loads(raw) if raw else None
                    if (
                        group in ('approach-ui-method', 'approach-ui-demo')
                        and path.endswith(('/preview', '/edits'))
                        and body
                        and any(e['kind'] == 'revise_definition' for e in body.get('edits', []))
                    ):
                        # Explicit description-only private double. Native atomic semantics
                        # are separately qualified by task44; no candidate is executed here.
                        from copy import deepcopy
                        from hyprn_mvp_app.store import uid,digest
                        from hyprn_mvp_app.modeling import validate
                        from test_assumption_authoring import sample,D
                        if self.offline:raise OSError('Declared model outage')
                        transport=self.transports[path.split('/models/')[1].split('/')[0]]
                        assert headers['Authorization'].startswith('Bearer ')
                        with sqlite3.connect(self.store.path,timeout=0) as db:
                            db.execute('BEGIN IMMEDIATE');db.rollback()
                        assert body['schema_version']=='4' and body['expected_revision']==transport.draft['draft_revision']
                        draft=deepcopy(transport.draft);created={}
                        for edit in body['edits']:
                            if edit['kind']=='revise_definition':
                                old=next(d for d in draft['definitions'] if d['definition_version_id']==edit['expected_definition_version_id'])
                                assert old['definition_id']==edit['definition_id']
                                definition=deepcopy(old);version=uid();definition['definition_version_id']=version
                                for port in definition['ports']:port['definition_version_id']=version
                                definition.setdefault('quantity_definitions',[])
                                for change in edit['changes']:
                                    assert change['kind'] in ('set_quantity_definition','clear_quantity_definition'), 'Unsupported private description-double change'
                                    assert any(p['port_id']==change['port_id'] for p in definition['ports'])
                                    definition['quantity_definitions']=[q for q in definition['quantity_definitions'] if q['port_id']!=change['port_id']]
                                    if change['kind']=='set_quantity_definition':
                                        definition['quantity_definitions'].append(dict(port_id=change['port_id'],statement=change['statement']))
                                draft['definitions'].append(definition);created[edit['temp_key']]=dict(definition_id=definition['definition_id'],definition_version_id=version,ports={})
                            elif edit['kind']=='replace_local_instance_version':
                                instance=next(i for i in draft['instances'] if i['instance_id']==edit['instance_id'])
                                assert instance['definition_version_id']==edit['expected_definition_version_id']
                                instance['definition_version_id']=created[edit['version_ref']['temp_key']]['definition_version_id']
                            else:raise AssertionError('Unsupported private description-double edit')
                        draft['schema_version']='4'
                        if 'quantity_definitions/1' not in draft['required_capabilities']:draft['required_capabilities'].append('quantity_definitions/1')
                        draft['ports']=[p for d in draft['definitions'] for p in d['ports']]
                        operation=path.rsplit('/',1)[1]
                        if operation=='edits':draft['draft_revision']=uid()
                        validate('ModelDraft4',draft)
                        result=dict(schema_version='1',request_id=uid(),data=draft,created_ids=created,diagnostics=[])
                        if operation=='edits':
                            payload=dict(major='1',operation=operation,target=draft['model_id'],study_id=transport.sid,payload={k:v for k,v in body.items() if k!='command_id'})
                            receipt=sample(D['Receipt']);receipt.update(command_id=body['command_id'],state='committed',payload_digest=digest(payload),status=200,response={k:deepcopy(v) for k,v in result.items() if k not in ('schema_version','request_id')})
                            transport.receipts[body['command_id']]=receipt;transport.draft=deepcopy(draft)
                        return 200,result
                    if path.endswith(('/capabilities','/unit-catalog')):
                        if self.offline: raise OSError('Declared model outage')
                        import base64
                        claim=headers["Authorization"].split(".")[1]
                        sid=json.loads(base64.urlsafe_b64decode(claim+"="*(-len(claim)%4)))["study_id"]
                        catalog=UnitTransport(self.store,sid)
                        catalog.caps['capabilities'].append(dict(catalog.caps['capabilities'][0],id='resolved_configuration',version='3'))
                        catalog.caps['capabilities'].append(dict(catalog.caps['capabilities'][0],id='quantity_definitions',version='1'))
                        catalog.caps['schema_versions'].append('4')
                        catalog.caps['contract_versions'].append('1.4')
                        return catalog(method,path,raw,headers)
                    if path.endswith('/configuration-compatibility'):
                        from hyprn_mvp_app.units import resolved_model_units
                        from hyprn_mvp_app.store import digest,uid
                        from hyprn_mvp_app.modeling import UNIT_CATALOG_DIGEST
                        body=json.loads(raw);candidate=body['configuration_candidate']
                        mid=path.split('/models/')[1].split('/')[0]
                        model=self.transports[mid].revisions[candidate['model_revision_id']]
                        units=resolved_model_units(model);versions={i['instance_id']:i['definition_version_id'] for i in model['instances']}
                        interpretations=[]
                        for item in candidate['inputs']:
                            target=item['target'];destination=units[(target['instance_id'],versions[target['instance_id']],target['port_id'])]
                            pair=(item['units'],destination)
                            # Declared private-transport double; the retained native
                            # conversion remains separately retained and unchanged.
                            factor=1000000 if pair==('MJ/kg','J/kg') else 1 if pair[0]==pair[1] else None
                            if factor is None: raise ValueError('Unsupported fixture conversion')
                            interpretations.append(dict(target=target,conversion=dict(policy='openmdao-linear-catalog-1',catalog_digest=UNIT_CATALOG_DIGEST,source_units=item['units'],destination_units=destination,factor=factor,destination_value=item['value']*factor)))
                        proof=dict(schema_version='2',validator_identity='declared-ui-fixture',compatible=True,diagnostics=[],candidate_digest=digest(candidate),model_digest=model['digest'],model_revision_id=model['model_revision_id'],required_capabilities=candidate['required_capabilities'],input_interpretations=interpretations)
                        return 200,dict(schema_version='1',request_id=uid(),data=proof)
                    # The product sends version3 assumption commands. This declared
                    # private double must return that requested model branch, while
                    # leaving the pre-preview draft and old revisions unchanged.
                    if method=='POST' and path.endswith(('/preview','/edits')):
                        body=json.loads(raw)
                        if body.get('schema_version') in {'3','4'}:
                            from copy import deepcopy
                            mid=path.split('/models/')[1].split('/')[0]
                            transport=self.transports[mid]
                            original=deepcopy(transport.draft)
                            transport.draft=deepcopy(original)
                            transport.draft['schema_version']=body['schema_version']
                            if 'unit_declarations/1' not in transport.draft['required_capabilities']:
                                transport.draft['required_capabilities'].append('unit_declarations/1')
                            if body['schema_version']=='4' and 'quantity_definitions/1' not in transport.draft['required_capabilities']:
                                transport.draft['required_capabilities'].append('quantity_definitions/1')
                            try:return super().call(method,path,raw,headers)
                            finally:
                                if path.endswith('/preview'):transport.draft=original
                    return super().call(method,path,raw,headers)
            modeling=FindingsModels(store)
            if group=='approach-ui-history':
                from test_assumption_authoring import PrivateTransport
                from copy import deepcopy
                from hyprn_mvp_app.history import History,retained_read_integrity
                from hyprn_mvp_app.execution import Submissions
                source_id=retained['source_run'];downstream_id=retained['downstream_run']
                records={};original_payloads={}
                with store.connection() as db:
                    sid=db.execute('SELECT study_id FROM run_associations WHERE run_id=?',(source_id,)).fetchone()[0]
                    frozen=[json.loads(row[0]) for row in db.execute('SELECT payload FROM configurations WHERE study_id=?',(sid,))]
                    for rid in (source_id,downstream_id):original_payloads[rid]=db.execute('SELECT payload FROM outbox WHERE run_id=?',(rid,)).fetchone()[0]
                for record in frozen:
                    model=record['model_snapshot'];mid=model['model_id']
                    if mid not in modeling.transports:modeling.transports[mid]=PrivateTransport(store,sid)
                    transport=modeling.transports[mid];transport.revisions[model['model_revision_id']]=deepcopy(model)
                    transport.draft={k:deepcopy(v) for k,v in model.items() if k not in {'model_revision_id','parent_model_revision_id','originating_draft_revision','digest'}}
                    transport.draft.update(study_id=sid,name='Retained units model',draft_revision=model['originating_draft_revision'])
                for rid in (source_id,downstream_id):
                    record=Submissions(store,None,None).read(actor,sid,rid);record['history']=History(store).read(actor,sid,rid)
                    record['retained_integrity']=retained_read_integrity(rid,record['history'])
                    if not record['retained_integrity']['results_digest']: raise ValueError('Retained run integrity is unavailable')
                    records[rid]=record
                native_pair=dict(study_id=sid,source_id=source_id,downstream_id=downstream_id,records=records,
                    scope='Actual retained source and downstream runs; both original approach pins are null. New configuration uses declared private modeling compatibility, no new numerical execution.')
                (scope.root/'evidence'/'native-pair.json').write_text(json.dumps(native_pair,indent=2))
        app = create_app(
            store,
            auth,
            modeling.client
            if group
            in (
                'approach-ui-method',
                'approach-ui-demo',
                'approach-ui-assumptions',
                'approach-ui-history',
            )
            else outage.client
            if group in ('calculations-ui', 'study-answer-ui')
            else NoModeling(),
        )
        stage=guard.scoped_path(scope,'artifacts/ui'); stage.mkdir()
        dist=guard.scoped_path(scope,'artifacts/dist'); evidence=guard.scoped_path(scope,'evidence')
        (stage/'package.json').write_text('{"type":"module"}')
        (stage/'tsconfig.json').write_text('{"compilerOptions":{"jsx":"react-jsx"}}')
        (stage/'index.html').write_text('<!doctype html><html><body><div id="root"></div><script type="module" src="/entry.tsx"></script></body></html>')
        imports='import {createRoot} from "react-dom/client";\n'
        for symbols,module in [('HyprnMvpApi','api'),('Button','design'),('Workspace','Workspace'),('checkPackage,canonical,sha256','exports'),('unresolvedModelUnits','unitLabels'),('quantityDefinitions,referencedQuantities','quantityDefinitions')]:
            imports+='import {'+symbols+'} from '+json.dumps(str(REPO/'ui/src'/module))+';\n'
        imports += ('import {DesignSpecimen} from '
                    + json.dumps(str(REPO / 'ui/tests/DesignSpecimen.tsx')) + ';\n')
        imports+=''.join('import '+json.dumps(str(REPO/'ui/src'/p))+';\n' for p in ('design/tokens.css','design/foundry.css','styles.css'))
        (stage/'entry.tsx').write_text(imports+'''
const surface = location.search.includes('specimen') ? <DesignSpecimen/> : <Workspace/>;
createRoot(document.getElementById('root')).render(surface);
''')
        config = dict(
            root=str(stage),
            base='/ui/',
            publicDir=str(REPO / 'ui/public'),
            build=dict(outDir=str(dist), target='esnext'),
            resolve=dict(
                alias={
                    'react': str(REPO / 'ui/node_modules/react'),
                    'react-dom': str(REPO / 'ui/node_modules/react-dom'),
                }
            ),
        )
        (stage/'vite.config.mjs').write_text('export default '+json.dumps(config))
        env=guard.clean_environment(scope)
        build=['node',str(REPO/'ui/node_modules/vite/bin/vite.js'),'build','--config',str(stage/'vite.config.mjs'),'--configLoader','runner']
        built=subprocess.run(build,cwd=REPO,env=env,capture_output=True,text=True,timeout=120)
        (evidence/'fixture-build.log').write_text(built.stdout+built.stderr)
        if built.returncode: raise ValueError('Approach harness build failed; see fixture-build.log')
        browser_config=stage/'playwright.config.ts'
        browser_config.write_text('import base from '+json.dumps(str(REPO/'ui/playwright.isolated.config.ts'))+';\nexport default {...base,testDir:'+json.dumps(str(REPO/'ui/tests'))+',testMatch:['+json.dumps(APPROACH_BROWSER_SPECS.get(requested_group,'approach.spec.ts'))+']};\n')
        thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        command=['node',str(REPO/'ui/node_modules/playwright/cli.js'),'test','--config',str(browser_config),'--grep',APPROACH_BROWSER_GROUPS[requested_group],'--reporter=json']
        # Every named check gets its own retained report. No empty selection,
        # skip or failed batch can disappear into an aggregate pass.
        listed=subprocess.run(command+['--list'],cwd=REPO,env=env,capture_output=True,text=True,timeout=30)
        (evidence/'browser-list.json').write_text(listed.stdout)
        if listed.returncode:raise ValueError('Browser collection failed')
        def titles(suites):
            return [spec['title'] for suite in suites for spec in suite.get('specs',[])]+[title for suite in suites for title in titles(suite.get('suites',[]))]
        names=titles(json.loads(listed.stdout).get('suites',[]))
        if not names or len(names)!=len(set(names)):raise ValueError('Empty or duplicate browser selection')
        stats={key:0 for key in ('expected','unexpected','skipped','flaky')};suites=[];returncode=0;batches=[]
        for index,title in enumerate(names):
            batch=command.copy();batch[batch.index('--grep')+1]=re.escape(title)
            started=time.monotonic()
            tested=subprocess.run(batch,cwd=REPO,env=env,capture_output=True,text=True,timeout=150)
            (evidence/f'browser-batch-{index:02d}.json').write_text(tested.stdout)
            (evidence/f'browser-batch-{index:02d}.stderr.log').write_text(tested.stderr)
            # Playwright clears outputDir between named batches; retain every failure context.
            browser_output=evidence/'browser'
            if browser_output.exists():
                shutil.copytree(browser_output,evidence/f'browser-artifacts-{index:02d}',dirs_exist_ok=True)
            report=json.loads(tested.stdout);suites.extend(report.get('suites',[]))
            measured=report.get('stats',{})
            for key in stats:stats[key]+=measured.get(key,0)
            if tested.returncode or measured.get('expected',0)!=1 or any(measured.get(key,0) for key in ('unexpected','skipped','flaky')):returncode=1
            batches.append(dict(title=title,seconds=time.monotonic()-started,command=batch,stats=measured,exit=tested.returncode))
        (evidence/'browser-report.json').write_text(json.dumps(dict(suites=suites,stats=stats),indent=2))
        (evidence/'browser-batches.json').write_text(json.dumps(batches,indent=2))
        (evidence/'public-api-calls.json').write_text(json.dumps(calls,indent=2)+'\n')
        native=[n for n in sys.modules if n.split('.')[0] in {'aiida','openmdao','openturns'}]
        passed=returncode==0 and stats.get('expected',0)>0 and not native and not any(stats.get(k,0) for k in ('unexpected','skipped','flaky'))
        record = dict(
            group=requested_group,
            passed=passed,
            tests=stats.get('expected', 0) + stats.get('unexpected', 0),
            failures=stats.get('unexpected', 0),
            skipped=stats.get('skipped', 0),
            command=command,
            build_command=build,
            native_imports=native,
            fixture=(
                (
                'Actual product/browser/HTTP/API/auth/receipts/store; public authoring, '
                'declared private modeling transport and synthetic retained-failure '
                'Submissions handoff; history group additionally reads a private copy of '
                'actual retained native records through a new public pinned configuration; '
                'original native runs have no approach pin; no native producer or candidate '
                'execution'
            )
                if group
                in (
                    'approach-ui-method',
                    'approach-ui-demo',
                    'approach-ui-assumptions',
                    'approach-ui-history',
                )
                else (
                'Actual controller/browser/HTTP/API/auth/receipts/store; public scientific '
                'writes only; no modeling or numerical execution'
            )
            ),
        )
        if native_pair:
            with store.connection() as db:
                preserved=all(db.execute('SELECT payload FROM outbox WHERE run_id=?',(rid,)).fetchone()[0]==raw for rid,raw in original_payloads.items())
            if not preserved: raise ValueError('Retained run payload changed')
            (evidence/'native-preservation.json').write_text(json.dumps(dict(preserved=preserved,payloads={rid:hashlib.sha256(raw.encode()).hexdigest() for rid,raw in original_payloads.items()}),indent=2))
        (evidence/'tests.json').write_text(json.dumps(record,indent=2)+'\n'); print(json.dumps(record))
        return 0 if passed else 1
    finally:
        if 'thread' in locals(): server.shutdown(); thread.join(timeout=10)
        server.server_close()
