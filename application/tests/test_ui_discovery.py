"""Public discovery against real Rails HTTP in a disposable, isolated tmpfs store."""
import base64
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import time

import pytest
from fastapi.testclient import TestClient
from hyprn_mvp_app.api import create_app
from hyprn_mvp_app.auth import Auth
from hyprn_mvp_app.modeling import ModelingClient
from hyprn_mvp_app.store import Store
from test_api import ORIGIN, post, study, uid, creation
from test_public_contract import check, SPEC

ROOT = Path(__file__).resolve().parents[2]
KEY = b'synthetic-public-discovery-credential-only'


def scoped_evidence_root(name):
    """Harness evidence lives only in the test's own scratch scope (the one deployment/checks.py
    allocated), never in a repository, synced or installation folder; outside a scope it is refused."""
    from checks import PROJECTION_SCOPE
    import scoped_fixture as guard
    root = guard.scoped_path(guard.validate_scope(PROJECTION_SCOPE), 'evidence/' + name)
    root.mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture(scope='module')
def private_http():
    """Reuse the private task's audited overlay recipe; never contact the live service."""
    evidence = scoped_evidence_root('public-discovery')
    evidence.mkdir(parents=True, exist_ok=True)
    loader = importlib.util.spec_from_file_location('private_discovery', ROOT / 'modeling/tests/test_ui_discovery.py')
    helper = importlib.util.module_from_spec(loader); loader.loader.exec_module(helper)
    stage = Path(tempfile.mkdtemp(prefix='adapter-', dir=evidence))
    target = stage / helper.SERVICE; target.parent.mkdir(parents=True)
    patch = (ROOT / 'upstream/whatsopt-patches/040-modeling-contract.patch').read_text()
    section = patch.split('+++ b/' + helper.SERVICE + '\n', 1)[1].split('\n--- ', 1)[0]
    target.write_text('\n'.join(line[1:] for line in section.splitlines() if line.startswith('+')) + '\n')
    for name in ['050-native-generation.patch', '060-ui-discovery.patch']:
        result = subprocess.run(['patch', '--batch', '-p1'], input=helper.service_patch(ROOT / 'upstream/whatsopt-patches' / name),
                                cwd=stage, text=True, capture_output=True, timeout=10)
        (stage / (name + '.log')).write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stdout + result.stderr
    schema = stage / 'modeling.schema.json'; schema.write_bytes((ROOT / 'contracts/schemas/model.schema.json').read_bytes())
    image = json.loads((ROOT / 'deployment/pins.json').read_text())['modeling_producer']['image']
    script = helper.BOOT + """
ENV['MODEL_KEY_FILE']='/tmp/discovery.key'
File.write(ENV['MODEL_KEY_FILE'],'synthetic-public-discovery-credential-only')
session=ActionDispatch::Integration::Session.new(Rails.application)
require 'socket'
server=UNIXServer.new('/tmp/public-discovery.sock')
loop do
  peer=server.accept
  call=JSON.parse(peer.gets)
  options={headers:call['headers']}
  options[:params]=call['body'] unless call['method']=='GET'
  session.public_send(call['method'].downcase,call['path'],**options)
  peer.puts JSON.generate({'status'=>session.response.status,'body'=>JSON.parse(session.response.body)})
  peer.close
end
"""
    (stage / 'server.rb').write_text(script)
    name = 'hyprn-mvp-test-public-discovery-' + uid()
    command = ['docker', 'run', '--rm', '-d', '--name', name, '--network', 'none', '--read-only',
               '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--user', '10001:10001',
               '--memory', '768m', '--cpus', '1', '--pids-limit', '64',
               '--tmpfs', '/tmp:rw,noexec,nosuid,size=192m,mode=1777',
               '--tmpfs', '/native/tmp:rw,nosuid,size=16m,mode=1777', '--tmpfs', '/native/log:rw,nosuid,size=16m,mode=1777',
               '--mount', f'type=bind,src={target},dst=/native/{helper.SERVICE},readonly',
               '--mount', f'type=bind,src={schema},dst=/native/config/modeling.schema.json,readonly',
               '-e', 'RAILS_ENV=test', '-e', 'DISABLE_BOOTSNAP=1', '-e', 'HOME=/tmp',
               '-e', 'NATIVE_STATIC_GENERATION=1', '-e', 'SECRET_KEY_BASE=synthetic-discovery-only',
               '--entrypoint', 'ruby', image, '-e', script]
    (stage / 'identity.json').write_text(json.dumps(dict(image=image, container=name,
        service_sha256=hashlib.sha256(target.read_bytes()).hexdigest(), schema_sha256=hashlib.sha256(schema.read_bytes()).hexdigest()), indent=2))
    result = subprocess.run(command, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    transcript = (stage / 'responses.jsonl').open('w')
    def transport(method, path, body, headers):
        request = json.dumps(dict(method=method, path=path, body=body.decode(), headers=headers)) + '\n'
        bridge = "require 'socket';s=UNIXSocket.new('/tmp/public-discovery.sock');s.write(STDIN.read);STDOUT.write(s.gets);s.close"
        reply = subprocess.run(['docker', 'exec', '-i', name, 'ruby', '-e', bridge],
                               input=request, capture_output=True, text=True, timeout=20)
        assert reply.returncode == 0, reply.stderr
        transcript.write(reply.stdout); transcript.flush()
        result = json.loads(reply.stdout)
        return result['status'], result['body']
    try:
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            ready = subprocess.run(['docker', 'exec', name, 'test', '-S', '/tmp/public-discovery.sock'], capture_output=True, timeout=5)
            if ready.returncode == 0: break
            time.sleep(0.1)
        else: raise AssertionError(f'Private harness did not become ready: {stage}')
        yield transport
    finally:
        logs = subprocess.run(['docker', 'logs', name], capture_output=True, text=True, timeout=10)
        (stage / 'stdout').write_text(logs.stdout); (stage / 'stderr').write_text(logs.stderr)
        removed = subprocess.run(['docker', 'rm', '-f', name], capture_output=True, text=True, timeout=15)
        transcript.close()
        (stage / 'exit.json').write_text(json.dumps(dict(cleanup_exit_code=removed.returncode)))
        assert removed.returncode == 0, removed.stderr



class Transport:
    def __init__(self, private):
        self.private = private; self.calls = []; self.offline = False; self.lost = False; self.transform = None

    def __call__(self, method, path, body, headers):
        self.calls.append((method, path, json.loads(base64.urlsafe_b64decode(headers['Authorization'].split('.')[1] + '=='))))
        if self.offline: raise OSError('Synthetic outage')
        status, result = self.private(method, path, body, headers)
        if self.lost and method == 'POST':
            self.lost = False; raise OSError('Lost response after durable commit')
        if self.transform and '/revisions?' in path and status == 200: result = self.transform(copy.deepcopy(result))
        return status, result


@pytest.fixture
def api(tmp_path, private_http):
    store = Store(tmp_path / 'app.sqlite'); auth = Auth(store, ORIGIN)
    actor = auth.provision('owner', 'correct horse battery staple')
    transport = Transport(private_http); model = ModelingClient('http://unused/modeling/1', KEY, transport=transport)
    client = TestClient(create_app(store, auth, model), base_url=ORIGIN)
    session = client.post('/api/1/session', json=dict(username='owner', password='correct horse battery staple'), headers={'Origin': ORIGIN})
    client.headers.update({'Origin': ORIGIN, 'X-CSRF-Token': session.json()['data']['csrf_token']})
    return client, store, auth, model, transport, actor


def empty(api, existing=None):
    c = api[0]; s = existing or study(api); sid = s['study_id']
    s = c.get('/api/1/studies/' + sid).json()['data']
    m = post(c, f'/studies/{sid}/models', dict(command_id=uid(), expected_revision=s['revision'], name='Original', template='empty'), 201)['data']
    return s, m, f'/api/1/studies/{sid}/models/{m["model_id"]}'


def commit(c, path, m):
    return post(c, path.removeprefix('/api/1') + '/commits', dict(command_id=uid(), expected_revision=m['draft_revision']))['data']


def test_empty_paged_revisions_are_neutral_exact_and_read_only(api):
    c, store, _, _, transport, _ = api; s, m, path = empty(api)
    response = c.get(path + '/revisions'); assert response.status_code == 200, response.text; check(response)
    assert response.json()['data'] == [] and response.json()['next_cursor'] is None
    pins = [commit(c, path, m) for _ in range(3)]
    first = c.get(path + '/revisions?limit=1'); check(first)
    pins.append(commit(c, path, m))
    second = c.get(path + '/revisions?limit=2&cursor=' + first.json()['next_cursor']); check(second)
    last = c.get(path + '/revisions?limit=100&cursor=' + second.json()['next_cursor']); check(last)
    keys = ('model_revision_id', 'parent_model_revision_id', 'originating_draft_revision', 'digest')
    assert first.json()['data'] + second.json()['data'] + last.json()['data'] == [{k: p[k] for k in keys} for p in pins]
    assert last.json()['next_cursor'] is None
    for pin in pins:
        exact = c.get(path + '/revisions/' + pin['model_revision_id']); check(exact); assert exact.json()['data'] == pin
    snapshot = store.path.read_bytes(); c.get(path + '/revisions'); assert store.path.read_bytes() == snapshot
    claims = transport.calls[-1][2]
    assert claims['resource_ids'] == [m['model_id']] and claims['study_id'] == s['study_id'] and claims['permissions'] == ['read']


@pytest.mark.parametrize('query', ['limit=0', 'limit=101', 'limit=-1', 'limit=1.0', 'limit=01', 'limit=', 'limit=2&limit=3', 'limit[]=2', 'cursor=bad', 'cursor=', 'cursor[]=bad', 'unknown=x'])
def test_invalid_revision_queries_fail_before_private_io(api, query):
    c, _, _, _, transport, _ = api; _, _, path = empty(api); before = len(transport.calls)
    response = c.get(path + '/revisions?' + query)
    assert response.status_code == 400, response.text; check(response)
    assert len(transport.calls) == before


def test_auth_cross_scope_missing_and_foreign_cursors(api):
    c, store, _, _, transport, actor = api; s, m, path = empty(api)
    _, other, otherpath = empty(api, s); foreign = commit(c, otherpath, other)
    otherstudy = study(api)
    before = len(transport.calls)
    public = TestClient(c.app, base_url=ORIGIN)
    assert public.get(path + '/revisions', headers={'X-Actor-ID': actor}).status_code == 401
    for url in [path.replace(s['study_id'], otherstudy['study_id']), path.replace(m['model_id'], uid())]:
        assert c.get(url + '/revisions?limit=0').status_code == 404
    assert len(transport.calls) == before
    for cursor in [foreign['model_revision_id'], uid()]:
        answer = c.get(path + '/revisions?cursor=' + cursor); assert answer.status_code == 404; check(answer)
    with store.connection(write=True) as db: db.execute('DELETE FROM memberships WHERE actor_id=?', (actor,))
    before = len(transport.calls)
    assert c.get(path + '/revisions').status_code == 404 and len(transport.calls) == before


@pytest.mark.parametrize('malformation', ['native_field', 'bad_digest', 'missing_parent', 'duplicate', 'too_many', 'bad_next', 'wrong_status'])
def test_malformed_private_pages_fail_closed(api, malformation):
    c, _, _, _, transport, _ = api; _, m, path = empty(api); commit(c, path, m)
    def corrupt(result):
        data = result['data']; row = data['items'][0]
        if malformation == 'native_field': row['native_url'] = 'http://private/native/123'
        if malformation == 'bad_digest': row['digest'] = 'invalid'
        if malformation == 'missing_parent': row.pop('parent_model_revision_id')
        if malformation == 'duplicate': data['items'] *= 2
        if malformation == 'too_many': data['items'] = [dict(row, model_revision_id=uid()) for _ in range(2)]
        if malformation == 'bad_next': data['next_cursor'] = uid()
        return result
    transport.transform = corrupt
    if malformation == 'wrong_status':
        original = transport.private
        transport.private = lambda *args: (201, original(*args)[1])
    response = c.get(path + '/revisions?limit=' + ('2' if malformation == 'duplicate' else '1'))
    assert response.status_code == 503, response.text; check(response)
    assert 'private/native' not in response.text and response.json()['error']['code'] == 'backend_unavailable'


def test_outage_is_not_unsupported_and_capabilities_are_scoped(api):
    c, _, _, _, transport, _ = api; _, _, path = empty(api); transport.offline = True
    answer = c.get(path + '/revisions'); assert answer.status_code == 503; check(answer)
    assert answer.json()['error']['code'] == 'backend_unavailable'
    capabilities = c.get('/api/1/capabilities'); check(capabilities)
    assert '1.1' in capabilities.json()['data']['contract_versions']
    assert capabilities.json()['data']['modeling'] == ['model_revision_listing', 'model_rename']
    assert 'nested_composition' in capabilities.json()['data']['unavailable']
    assert c.get(path + '/revisions/' + uid()).status_code == 503
    transport.offline = False
    assert c.get(path + '/revisions').status_code == 200
    original = transport.private
    def unsupported(method, path, body, headers):
        if '/revisions?' not in path: return original(method, path, body, headers)
        return 422, dict(error=dict(code='unsupported_capability', message='Unsupported', request_id=uid(),
            command_id=None, resource_id=None, current_revision=None, fields=[], outcome='unchanged'))
    transport.private = unsupported
    answer = c.get(path + '/revisions'); assert answer.status_code == 422; check(answer)
    assert answer.json()['error']['code'] == 'unsupported_capability'


def test_rename_preview_cas_replay_reconciliation_and_exact_revision(api):
    c, store, auth, model, transport, actor = api; s, m, path = empty(api)
    m = post(c, path.removeprefix('/api/1') + '/edits', dict(command_id=uid(), expected_revision=m['draft_revision'], edits=creation()))['data']
    pin = commit(c, path, m); frozen = c.get(path + '/revisions/' + pin['model_revision_id']).json()['data']
    body = dict(expected_revision=m['draft_revision'], edits=[dict(kind='rename_model', name='Engineering / α')])
    preview = c.post(path + '/preview', json=body); assert preview.status_code == 200; check(preview)
    assert preview.json()['data']['name'] == 'Engineering / α'
    assert c.get(path).json()['data'] == m
    command = dict(body, command_id=uid())
    assert c.post(path + '/edits', json=command, headers={'X-CSRF-Token': 'wrong'}).status_code == 403
    transport.lost = True
    pending = c.post(path + '/edits', json=command); assert pending.status_code == 202; check(pending)
    restarted = TestClient(create_app(Store(store.path), auth, model), base_url=ORIGIN)
    restarted.cookies.update(c.cookies); restarted.headers.update(c.headers)
    receipt = restarted.get(f'/api/1/studies/{s["study_id"]}/commands/{command["command_id"]}?category=model')
    assert receipt.json()['data']['state'] == 'committed'; check(receipt)
    applied = restarted.post(path + '/edits', json=command); assert applied.status_code == 200; check(applied)
    renamed = applied.json()['data']; assert renamed['name'] == 'Engineering / α' and renamed['model_id'] == m['model_id']
    assert renamed['draft_revision'] != m['draft_revision']
    assert c.post(path + '/edits', json=command).json()['data'] == renamed
    conflict = c.post(path + '/edits', json={**command, 'edits': [dict(kind='rename_model', name='Changed')]})
    assert conflict.status_code == 409 and conflict.json()['error']['code'] == 'command_payload_conflict'; check(conflict)
    stale = c.post(path + '/edits', json={**command, 'command_id': uid()})
    assert stale.status_code == 409 and stale.json()['error']['code'] == 'stale_revision'; check(stale)
    assert c.get(path + '/revisions/' + pin['model_revision_id']).json()['data'] == frozen
    assert c.get(path + '/revisions').json()['data'][0]['digest'] == pin['digest']
    with store.connection(write=True) as db: db.execute('DELETE FROM memberships WHERE actor_id=?', (actor,))
    assert c.post(path + '/edits', json=command).status_code == 404


def test_public_contract_exposes_closed_bounded_list_and_typed_rename():
    route = SPEC['paths']['/studies/{study_id}/models/{model_id}/revisions']['get']
    params = {p['name']: p['schema'] for p in route['parameters']}
    assert params['limit'] == dict(type='integer', minimum=1, maximum=100, default=50)
    assert params['cursor']['format'] == 'uuid'
    response = route['responses']['200']['content']['application/json']['schema']
    assert response['additionalProperties'] is False and 'next_cursor' in response['required']
    assert response['properties']['data']['maxItems'] == 100
    assert SPEC['components']['schemas']['RevisionSummary']['additionalProperties'] is False
    # Every concrete edit version in the inspection union offers the typed rename.
    versions = [ref['$ref'].split('/')[-1] for ref in SPEC['components']['schemas']['Edit']['anyOf']]
    assert versions
    schemas = SPEC['components']['schemas']
    def concrete(edit):
        edit = schemas[edit['$ref'].split('/')[-1]] if '$ref' in edit else edit
        return [edit] if 'properties' in edit else [e for branch in edit['oneOf'] for e in concrete(branch)]
    for version in versions:
        assert any(edit['properties']['kind'].get('enum') == ['rename_model'] for edit in concrete(schemas[version]))
