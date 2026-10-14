"""Guarded real editor/client/API fixture; private compatibility is a test double.

Fresh synthetic retained results exercise UI authority, not numerical execution.
The server owns only a marker-bound ephemeral loopback socket and fresh SQLite.
"""
from copy import deepcopy as private_copy
import base64
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import subprocess
import shutil
import sys
import threading
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit

import scoped_fixture as guard

ROOT = Path(__file__).resolve().parents[2]


def build_image_ui(scope, stage, dist, env):
    """Serve fixture bytes produced by the application's pinned, offline UI build stage."""
    import modeling_runtime

    context = guard.scoped_path(scope, 'artifacts/image-build')
    context.mkdir()
    ui = context / 'ui'
    shutil.copytree(ROOT / 'ui', ui, ignore=shutil.ignore_patterns('node_modules', 'dist'))
    shutil.copyfile(stage / 'index.html', ui / 'index.html')
    entry = (stage / 'entry.tsx').read_text().replace(str(ROOT / 'ui/src'), '/build/ui/src')
    (ui / 'entry.tsx').write_text(entry)
    config = dict(base='/ui/', build=dict(outDir='dist', target='esnext'))
    (ui / 'vite.config.ts').write_text('export default ' + json.dumps(config))
    shutil.copyfile(ROOT / 'deployment/application.Dockerfile', context / 'Dockerfile')
    modeling_runtime.readable_context(context)
    pins = json.loads((ROOT / 'deployment/pins.json').read_bytes())
    inputs = {str(p.relative_to(context)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(context.rglob('*')) if p.is_file()}
    serialized = json.dumps([scope.run_uuid, inputs], sort_keys=True).encode()
    digest = hashlib.sha256(serialized).hexdigest()
    tag = 'hyprn-mvp-ui-fixture:' + digest[:16]
    command = [
        'docker', 'build', '--pull=false', '--target', 'ui',
        '--label', 'org.hyprn-mvp.test-scope=' + scope.run_uuid,
        '--build-arg', 'NODE_IMAGE=' + pins['node_base_image'],
        '--build-arg', 'PYTHON_IMAGE=' + pins['base_image'], '-t', tag, str(context),
    ]
    evidence = guard.scoped_path(scope, 'evidence')
    built = subprocess.run(command, env=dict(env, DOCKER_BUILDKIT='1'),
                           capture_output=True, text=True)
    (evidence / 'fixture-build.log').write_text(built.stdout + built.stderr)
    built.check_returncode()
    try:
        inspected = subprocess.run(
            ['docker', 'image', 'inspect', tag], env=env,
            capture_output=True, text=True, check=True,
        )
        image = json.loads(inspected.stdout)[0]
        if image['Config']['Labels'].get('org.hyprn-mvp.test-scope') != scope.run_uuid:
            raise ValueError('UI image scope mismatch')
        script = (
            "const fs=require('fs'),p=require('path'),root='/build/ui/dist',out={};"
            "function walk(d){for(const n of fs.readdirSync(d)){const f=p.join(d,n);"
            "if(fs.statSync(f).isDirectory())walk(f);"
            "else out[p.relative(root,f)]=fs.readFileSync(f).toString('base64');}}"
            "walk(root);console.log(JSON.stringify(out));"
        )
        extracted = subprocess.run([
            'docker', 'run', '--rm', '--network=none', '--read-only', '--cap-drop=ALL',
            '--security-opt=no-new-privileges:true',
            '--label', 'org.hyprn-mvp.test-scope=' + scope.run_uuid,
            image['Id'], 'node', '-e', script,
        ], env=env, capture_output=True, text=True, check=True)
        assets = json.loads(extracted.stdout)
        dist.mkdir()
        hashes = {}
        for name, value in assets.items():
            relative = Path(name)
            if relative.is_absolute() or '..' in relative.parts:
                raise ValueError('Unsafe image-built UI path')
            target = dist / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            raw = base64.b64decode(value, validate=True)
            target.write_bytes(raw)
            hashes[name] = hashlib.sha256(raw).hexdigest()
        if 'index.html' not in hashes:
            raise ValueError('Image-built UI entry point missing')
        (evidence / 'image-built-ui.json').write_text(json.dumps(dict(
            image=image['Id'], node_base=pins['node_base_image'], inputs=inputs, assets=hashes,
            command=command, scope=scope.run_uuid,
        ), indent=2) + '\n')
    finally:
        if 'image' in locals() and image['Config']['Labels'].get(
            'org.hyprn-mvp.test-scope'
        ) == scope.run_uuid:
            subprocess.run(['docker', 'image', 'rm', '--no-prune', tag], env=env, check=True,
                           capture_output=True, text=True)
    return command


def run(*, retained=False, modified=False, exported=False):
    retained = retained or modified
    scope = guard.scope_from_environment()
    if sys.executable != scope.interpreter or scope.interpreter != guard.APPROVED_CONTRACT_PYTHON:
        raise ValueError('UI fixture requires the reviewed application interpreter')
    for path in ('application/src', 'application/tests', 'integration/tests', 'integration/src', 'contracts/tests'):
        sys.path.insert(0, str(ROOT / path))
    import test_reuse_api as records
    from fastapi.testclient import TestClient

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args): pass
        def do_GET(self): self.handle_request()
        def do_POST(self): self.handle_request()
        def do_DELETE(self): self.handle_request()
        def handle_request(self):
            if exported and self.path == '/fixture/export-control' and self.command == 'POST':
                control=json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))))
                return self.respond(200,json.dumps(export.control(control)).encode(),'application/json')
            if modified and self.path == '/fixture/control' and self.command == 'POST':
                control = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))))
                assert set(control) in ({'offline'}, {'description'})
                if 'offline' in control:
                    assert isinstance(control['offline'], bool)
                    data['model'].offline = control['offline']
                else:
                    assert isinstance(control['description'], str) and len(control['description']) <= 200
                    from hyprn_mvp_app.store import uid
                    study = data['store'].study(data['actor'], data['sid'])
                    data['store'].update_study(data['actor'], data['sid'], uid(), study['revision'], {'description':control['description']})
                return self.respond(200, b'{}', 'application/json')
            if self.path == '/fixture':
                return self.respond(200, json.dumps(props).encode(), 'application/json')
            if self.path.startswith('/api/1/'):
                # Fresh client per request: only the browser's cookies/CSRF reach Auth.
                with TestClient(data['client'].app, base_url=scope.url) as client:
                    response = client.request(self.command, self.path,
                        content=self.rfile.read(int(self.headers.get('Content-Length', 0))),
                        headers={k: v for k, v in self.headers.items() if k.lower() not in {'host', 'content-length', 'connection'}})
                self.send_response(response.status_code)
                for key, value in response.headers.multi_items():
                    if key.lower() not in {'content-length', 'connection', 'transfer-encoding'}: self.send_header(key, value)
                self.send_header('Content-Length', str(len(response.content))); self.end_headers(); self.wfile.write(response.content)
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
        records.ORIGIN = scope.url
        if exported:
            from export_ui_fixture import ExportFixture
            export=ExportFixture(scope);data=export.data;props=export.props
        else:
            data = records.api.__wrapped__(guard.scoped_path(scope, 'artifacts'))
        if retained:
            import copy, base64
            from hyprn_mvp_app.store import uid
            from hyprn_mvp_app.execution import Submissions, assemble_bundle
            from hyprn_mvp_app.history import projection
            from hyprn_mvp_app.result_bindings import ResultBindings
            from test_result_bindings import prepared2, NativeResolverDouble
            from execution_fixtures import runtime_fixture
            if modified:
                note = data['client'].post(records.path(data,'evidence'), json=dict(evidence_schema_version='2', command_id=uid(), resource_scope=dict(scope_version='1',kind='study',study_id=data['sid']),kind='note',content='Retained observation α',source_refs=['Fixture observation']))
                assert note.status_code == 201, note.text
                data['candidate']['evidence_version_ids'] = [note.json()['data']['evidence_version_id']]
            response=data['client'].post(records.path(data,'configurations'),json=records.commit_body(data))
            assert response.status_code==201,response.text
            saved=response.json()['data']
            # The public save returns the immutable pair; synthetic numerical
            # bytes here exercise presentation only, never native acceptance.
            frozen=saved
            prepared,files=prepared2(data,frozen)
            deps=ResultBindings(data['store']).dependencies(data['actor'],data['sid'],frozen['configuration'],NativeResolverDouble())
            submitted=Submissions(data['store'],None,None).submit(data['actor'],data['sid'],dict(command_id=uid(),configuration_revision_id=frozen['configuration']['configuration_revision_id']))
            rid=submitted['run_id'];bundle=assemble_bundle(rid,prepared,files,frozen,runtime_fixture(),deps)
            with data['store'].connection() as db:
                original=json.loads(db.execute('SELECT payload FROM outbox WHERE run_id=?',(data['rid'],)).fetchone()[0])
            request=dict(run_id=rid,scope=data['sid'],command_id=submitted['command_id'],payload_digest=data['store'].receipt(data['actor'],data['sid'],'run',submitted['command_id'])['payload_digest'],bundle_digest=bundle['manifest']['bundle_digest'])
            results=copy.deepcopy(original['history']['results']);results.update(run_id=rid,bundle_digest=request['bundle_digest'])
            association=dict(store_uuid=uid(),process_uuid=uid())
            payload=dict(actor=data['actor'],frozen=frozen,request=request,status=dict(process_state='finished',exit_status=0),bundle=dict(manifest=bundle['manifest'],files={p:base64.b64encode(b).decode() for p,b in bundle['files'].items()}))
            payload['history']=projection(payload,dict(request=request,bundle=bundle,results=results,assessment=None,artifacts={},errors=[])|association,association)
            with data['store'].connection(write=True) as db:
                original['status']=dict(process_state='finished',exit_status=0)
                db.execute('UPDATE outbox SET payload=? WHERE run_id=?',(json.dumps(original),data['rid']))
                db.execute('UPDATE run_associations SET store_uuid=?,process_uuid=? WHERE run_id=?',(*association.values(),rid))
                db.execute("UPDATE outbox SET state='recorded',payload=? WHERE run_id=?",(json.dumps(payload),rid))
            data['saved']=frozen;data['linked_run']=rid
        if not exported:
            original_call = data['model'].call
            def private_read(kwargs, result):
                # Declared typed private-read double; validated exactly like the real client.
                from hyprn_mvp_app.modeling import validate
                from hyprn_mvp_app.store import uid
                validate(kwargs['response_schema'], dict(schema_version='1', request_id=uid(), data=result))
                return 200, dict(data=private_copy(result))
            def private_call(actor, sid, method, path, body=None, **kwargs):
                if method == 'GET' and path in ('/capabilities', '/unit-catalog'):
                    # Configuration editing needs the
                    # authoritative unit catalog, and Request3 needs the
                    # resolved-configuration capability. The double advertises exactly those;
                    # it has no execution backend, so readiness still reports modeling_unavailable.
                    # A declared outage (retained/offline) behaves like the real client: 503.
                    if data['model'].offline:
                        from hyprn_mvp_app.store import DomainError
                        raise DomainError('backend_unavailable', 503, outcome='unknown')
                    if path == '/unit-catalog':
                        from test_unit_guidance_api import CATALOG
                        return private_read(kwargs, CATALOG)
                    from test_assumptions_evidence_contracts import sample, D
                    caps = sample(D['Capabilities'])
                    item = sample(D['Capabilities']['properties']['capabilities']['items'])
                    caps.update(contract_versions=['1.1', '1.2', '1.3'], schema_versions=['1', '2', '3'],
                        service_build='isolated-editor-private-double',
                        generator_identity=private_copy(data['case']['prepared']['generator_identity']),
                        capabilities=[dict(item, id='resolved_configuration', version='3', supported=True),
                                      dict(item, id='unit_declarations', version='1', supported=True)])
                    return private_read(kwargs, caps)
                if modified and data['model'].offline and method == 'POST':
                    from hyprn_mvp_app.store import DomainError
                    raise DomainError('backend_unavailable', 503)
                return original_call(actor, sid, method, path, body, **kwargs)
            data['model'].call = private_call
            frozen = data['case']['frozen']; revision = frozen['model_snapshot']
            props = dict(study=data['store'].study(data['actor'], data['sid']), revision=revision,
                model=dict(revision, study_id=data['sid'], name='Fresh model', draft_revision=revision['originating_draft_revision']),
                source=data['client'].get(records.path(data, 'result-sources')).json()['data']['items'][0])
            if retained:
                source=data['client'].get(records.path(data,'result-sources')).json()['data']['items']
                props.update(saved=data['saved'],linked_run=data['linked_run'],source=next(s for s in source if s['source_run_id']==data['rid']))
                props['model']['name']='Renamed current model'
                data['model'].offline=True  # Saved records must work without today's model.
        stage = guard.scoped_path(scope, 'artifacts/ui'); stage.mkdir()
        dist = guard.scoped_path(scope, 'artifacts/dist')
        (stage / 'index.html').write_text('<!doctype html><html data-theme="light"><head><meta name="viewport" content="width=device-width, initial-scale=1"></head><body><div id="root"></div><script type="module" src="/entry.tsx"></script></body></html>')
        (stage / 'package.json').write_text('{"type":"module"}')
        (stage / 'tsconfig.json').write_text('{"compilerOptions":{"jsx":"react-jsx"}}')
        entry = '''import {useRef,useState} from 'react';
import {createRoot} from 'react-dom/client';
import {ConfigurationPanel} from REPO_CONFIG;
import {HyprnMvpApi} from REPO_API;
import {Button} from REPO_DESIGN;
import REPO_TOKENS;
import REPO_FOUNDRY;
import REPO_CSS;
const api=new HyprnMvpApi(); await api.login('owner','correct horse battery staple');
const props=await(await fetch('/fixture')).json();
function Fixture(){const [dirty,setDirty]=useState(false),[source,setSource]=useState(null);const handle=useRef(null);
return <main><header className="appbar"><strong className="brand">HYPRN MVP</strong><span>Isolated editor fixture</span></header><div className="workspace-shell"><div className="workspace-content">
<ConfigurationPanel api={api} model={props.model} study={props.study} initialRevision={props.revision} authoringDirty={false} activeRun={false}
onSubmit={async()=>{throw Error('Scientific submission is outside this fixture')}} onEvidenceRecords={()=>{}}
onHandle={h=>{handle.current=h; if(dirty!==h.dirty)setDirty(h.dirty)}} onViewSourceResult={(runId,output)=>setSource({runId,output})}/>
</div></div><output className="sr-only" data-testid="dirty">{dirty?'dirty':'clean'}</output><output className="sr-only" data-testid="source-reference">{source?JSON.stringify(source):''}</output></main>}
createRoot(document.getElementById('root')).render(<Fixture/>);
'''
        for token, relative in {'REPO_CONFIG': 'ConfigurationPanel', 'REPO_API': 'api', 'REPO_DESIGN': 'design', 'REPO_TOKENS': 'design/tokens.css', 'REPO_FOUNDRY': 'design/foundry.css', 'REPO_CSS': 'styles.css'}.items():
            entry = entry.replace(token, json.dumps(str(ROOT / 'ui/src' / relative)))
        (stage / 'entry.tsx').write_text(entry)
        if retained or exported:
            (stage/'entry.tsx').write_text('import {createRoot} from "react-dom/client";\nimport {Workspace} from '+json.dumps(str(ROOT/'ui/src/Workspace'))+';\n'+''.join('import '+json.dumps(str(ROOT/'ui/src'/p))+';\n' for p in ('design/tokens.css','design/foundry.css','styles.css'))+'createRoot(document.getElementById("root")).render(<Workspace/>);')
        config = dict(root=str(stage), base='/ui/', build=dict(outDir=str(dist), target='esnext'),
            resolve=dict(alias={'react': str(ROOT / 'ui/node_modules/react'), 'react-dom': str(ROOT / 'ui/node_modules/react-dom')}))
        (stage / 'vite.config.mjs').write_text('export default ' + json.dumps(config))
        env = guard.clean_environment(scope)
        build = ['node', str(ROOT / 'ui/node_modules/vite/bin/vite.js'), 'build', '--config', str(stage / 'vite.config.mjs'), '--configLoader', 'runner']
        evidence = guard.scoped_path(scope, 'evidence')
        if not (retained or exported):
            build = build_image_ui(scope, stage, dist, env)
        else:
            built = subprocess.run(build, cwd=ROOT, env=env, text=True, capture_output=True)
            (evidence / 'fixture-build.log').write_text(built.stdout + built.stderr)
            if built.returncode:
                raise ValueError('Isolated UI fixture build failed; see fixture-build.log')
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        command = ['node', str(ROOT / 'ui/node_modules/playwright/cli.js'), 'test', '--config', 'ui/playwright.isolated.config.ts', '--grep', '@export' if exported else '@modified' if modified else '@retained' if retained else '@editor', '--reporter=json']
        tested = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
        (evidence / 'browser-report.json').write_text(tested.stdout)
        (evidence / 'browser-stderr.log').write_text(tested.stderr)
        try: stats = json.loads(tested.stdout)['stats']
        except (ValueError, KeyError): stats = {}
        checked = subprocess.run([scope.interpreter, '-B', 'ui/check_ui_contract.py'], cwd=ROOT, env=env, capture_output=True, text=True)
        (evidence / 'wiring-check.log').write_text(checked.stdout + checked.stderr)
        forbidden = [n for n in sys.modules if n.split('.')[0] in {'aiida', 'openmdao', 'openturns'}]
        passed = not forbidden and checked.returncode == 0 and tested.returncode == 0 and stats.get('expected', 0) > 0 and not any(stats.get(k, 0) for k in ('unexpected', 'skipped', 'flaky'))
        record = dict(tests=stats.get('expected', 0)+stats.get('unexpected', 0), passed=passed, skipped=stats.get('skipped', 0),
            failures=stats.get('unexpected', 0), command=command, build_command=build,
            fixture='Real HTTP/Auth/Store/package; verified native archive response transport double; bounded data-only driver; no candidate execution' if exported else 'Actual public API/client/editor; private compatibility double; synthetic fresh retained result bytes; no native execution')
        (evidence / 'tests.json').write_text(json.dumps(record, indent=2)+'\n')
        print(json.dumps(record))
        return 0 if passed else 1
    finally:
        if 'thread' in locals(): server.shutdown(); thread.join(timeout=10)
        server.server_close()
