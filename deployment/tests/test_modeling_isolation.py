"""Actual owned private-service and disposable native-producer probes.

The service under test is an owned modeling deployment that modeling_runtime sets up inside this
test scope (modeling_deployment_fixture.owned_modeling): it must hold no launcher, container
socket or foreign store.
"""
# Live-runtime fence (deployment/tests/live_fence.py), baseline policy: refuses live roots, live
# ports, installation names, live entry points and real signals; docker acts only on this scope's
# own deployment.
import sys as _fence_sys
from pathlib import Path as _FencePath
if str(_FencePath(__file__).resolve().parent) not in _fence_sys.path:
    _fence_sys.path.append(str(_FencePath(__file__).resolve().parent))
import live_fence  # noqa: E402
live_runtime_fence = live_fence.pytest_fixture('baseline')
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

import pytest

from model_client import ModelClient, raw_request, ruby, uid
from modeling_deployment_fixture import owned_modeling  # noqa: F401  (session fixture)

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'contracts/tests'))
from test_modeling_contract import creation, candidate, digest, source
sys.path.insert(0, str(REPO / 'deployment'))
import modeling_runtime as runtime

pytestmark = [pytest.mark.isolation, pytest.mark.usefixtures('owned_modeling')]


def test_native_build_closure_is_identity_bound():
    inventory = runtime.source_hashes()
    assert 'contracts/schemas/documents.schema.json' not in inventory
    assert len(inventory) == 23
    for path in ('modeling/rehearsal.py', 'contracts/schemas/model.schema.json',
                 'contracts/schemas/execution.schema.json', 'integration/worker-requirements.lock',
                 'upstream/whatsopt-patches/050-native-generation.patch'):
        assert path in inventory
    recipe = (REPO / 'deployment/modeling.Dockerfile').read_text()
    assert 'COPY native.patch' in recipe
    assert recipe.index('COPY replay /native/') < recipe.index('COPY native.patch')
    assert 'COPY provenance-inputs /native/provenance-inputs' in recipe
    assert 'COPY modeling.schema.json /native/config/modeling.schema.json' in recipe
    assert recipe.index('patch --batch --fuzz=0 -p1') < recipe.index('ruby /modeling_policy.rb')


def test_actual_identity_matches_reviewed_pins(owned_modeling):
    root, deployment, _ = owned_modeling
    pins = json.loads((REPO / 'deployment/pins.json').read_text())
    result = runtime.check(root, deployment=deployment)  # refuses unless the recorded identity names the current sources
    identity = json.loads((root / 'identity.json').read_text())
    assert result['image'] == identity['image'] == pins['modeling_producer']['image']
    built = runtime.image_identity(identity['image'])
    assert identity['source_image'] == built['source_image']
    assert built['source_build_inputs'] == runtime.source_build_inputs()
    assert built['source_hashes'] == runtime.source_hashes()
    assert identity['source_hashes'] == runtime.source_hashes()
    assert result['candidate_execution'] == 'blocked_pending_plan_01_12_consumer_attestation'


def test_private_auth_and_scope_fail_closed():
    assert raw_request('GET', '/modeling/1/capabilities')[0] == 401
    assert raw_request('GET', '/modeling/1/capabilities', headers={'X-Study-ID': uid(), 'X-User-ID': 'admin'})[0] == 401
    ModelClient(key=b'forged').call('GET', '/capabilities', status=401)
    c = ModelClient()
    m = c.create('Engineering / α exact name')
    assert m['name'] == 'Engineering / α exact name'
    path = '/models/' + m['model_id']
    ModelClient().call('GET', path, status=404)
    c.call('GET', path, resources=[uid()], status=403)
    c.call('POST', path+'/edits', dict(command_id=uid(), expected_revision=m['draft_revision'], edits=creation()), permissions=['read'], status=403)
    assert c.call('GET', path)['data'] == m


@pytest.mark.parametrize('path', ['/analyses/1/check', '/analyses/1/run', '/analyses/1/monitor', '/analyses/1/sensitivity', '/salib', '/hyprn_mvp_probe/1/run', '/hyprn_mvp/1/edits', '/analyses'])
def test_legacy_routes_are_unavailable(path):
    for method in ('GET', 'POST'):
        assert raw_request(method, path, b'{}')[0] == 404


def test_direct_native_execution_helpers_unavailable_and_parser_is_data_only():
    script = '''
require 'json'
%w[SalibSensitivityAnalyser ServerGenerator EgmdoGenerator GemseoGenerator].each do |name|
  begin
    WhatsOpt.const_get(name)
    raise "Execution helper still loadable: #{name}"
  rescue NameError
  end
end
generator=WhatsOpt::OpenmdaoGenerator.allocate
%i[generate _format_code check_mda_setup run monitor _check_mda _run_mda _monitor_mda].each do |method|
  begin
    generator.send(method)
    raise "Unsafe native helper callable: #{method}"
  rescue SecurityError
  end
end
raise 'Wrong static origin' unless generator.method(:_generate_code).source_location[0]=='/native/app/lib/whats_opt/openmdao_generator.rb'
raise 'Legacy launcher exists' if File.exist?('/probe')
parser = Object.new.extend(WhatsOpt::PythonUtils)
raise 'Wrong parser' unless parser.str_to_ary('[1, 2.5]') == [1, 2.5]
begin
  parser.str_to_ary("__import__('os').system('touch /store/parser-side-effect')")
  raise 'Expression accepted'
rescue WhatsOpt::PythonUtils::ArrayParseError
end
raise 'Parser side effect' if File.exist?('/store/parser-side-effect')
puts JSON.generate({helpers: 'unavailable', parser: 'data-only'})
'''
    assert json.loads(ruby(script, rails=True).splitlines()[-1])['helpers'] == 'unavailable'


def test_candidate_side_effect_source_only_retained_as_bytes():
    marker = '/store/candidate-side-effect-' + uid()
    raw = ("from pathlib import Path\nPath(" + repr(marker) + ").write_text('executed')\nraise RuntimeError('must not import')\n").encode()
    c = ModelClient()
    edits = creation()
    edits[0]['source'] = source(raw)
    draft = c.edit(c.create(), edits)
    m = c.commit(draft)
    cfg = candidate(m, c.study)
    cfg.update(configuration_id=uid(), configuration_revision_id=uid(), parent_revision_id=None)
    cfg['digest'] = digest(cfg)
    request = dict(command_id=uid(), model_revision_id=m['model_revision_id'], configuration_snapshot=cfg, configuration_digest=cfg['digest'])
    before = c.call('GET', '/models/'+m['model_id'])['data']
    prepared = c.call('POST', '/models/'+m['model_id']+'/prepare-execution', request)['data']
    assert before == c.call('GET', '/models/'+m['model_id'])['data']
    assert prepared['schema_version'] == '2'
    assert c.call('POST', '/models/'+m['model_id']+'/prepare-execution', request)['data'] == prepared
    blobs = []
    files = {}
    for file in prepared['files']:
        data = c.call('GET', '/preparations/'+prepared['preparation_id']+'/files/'+file['file_id'])['data']
        blob = base64.b64decode(data['bytes'])
        assert hashlib.sha256(blob).hexdigest() == file['sha256']
        blobs.append(blob)
        files[file['path']] = blob
    from test_native_program_contract import check_program, validate
    check_program(prepared, files, prepared['prepared_digest'])
    validate('ProgramProvenance', json.loads(files['provenance/generator.json']))
    assert raw in blobs
    assert ruby('puts File.exist?('+json.dumps(marker)+')').strip() == 'false'
    assert ruby("puts Dir.glob('/tmp/hyprn-mvp-native-*/request-*').empty?").strip() == 'true'
    c.edit(before, [dict(kind='rename_instance', instance_id=before['instances'][0]['instance_id'], name='later draft')])
    again = c.call('POST', '/models/'+m['model_id']+'/prepare-execution', {**request, 'command_id': uid()})['data']
    assert again['executable_content_digest'] == prepared['executable_content_digest']
    assert c.call('GET', '/models/'+m['model_id']+'/revisions/'+m['model_revision_id'])['data'] == m
    c.call('POST', '/models/'+m['model_id']+'/prepare-execution', request, permissions=['read'], status=403)
    ModelClient().call('GET', '/preparations/'+prepared['preparation_id']+'/files/'+prepared['files'][0]['file_id'], status=404)


def test_deployed_four_helper_slots_remain_bounded_and_clean(owned_modeling):
    root, _, _ = owned_modeling
    c = ModelClient()
    m = c.commit(c.edit(c.create(), creation()))
    cfg = candidate(m, c.study)
    cfg.update(configuration_id=uid(), configuration_revision_id=uid(), parent_revision_id=None)
    cfg['digest'] = digest(cfg)
    payload = base64.b64encode(json.dumps([m, cfg]).encode()).decode()
    script = '''
require 'base64';require 'json'
m,cfg=JSON.parse(Base64.strict_decode64(%s))
NativeProgram; NativeMaterializer
db=ActiveRecord::Base.connection_db_config.database
threads=4.times.map { Thread.new { NativeProgram.generate(m,cfg) } }
results=threads.map(&:value)
raise 'Generation differed' unless results.uniq.size==1
raise 'Connection changed' unless ActiveRecord::Base.connection_db_config.database==db
raise 'Scratch leak' unless Dir.glob('/tmp/hyprn-mvp-native-*/request-*').empty?
raise 'Child leak' unless Process.waitall.empty?
puts JSON.generate({slots:4,clean:true,memory_peak:File.read('/sys/fs/cgroup/memory.peak').to_i,memory_events:File.read('/sys/fs/cgroup/memory.events')})
''' % json.dumps(payload)
    result = json.loads(ruby(script, rails=True).splitlines()[-1])
    assert result['slots'] == 4 and result['clean']
    assert 'oom_kill 0' in result['memory_events']
    (root/'evidence/helper-bounds.json').write_text(json.dumps(result, indent=2))


def test_effective_privileges_and_real_canary_file_denials(owned_modeling):
    root, deployment, _ = owned_modeling
    runtime.check(root, deployment=deployment)
    canaries = root / 'canaries'
    canaries.mkdir(mode=0o700, exist_ok=True)
    names = ['application.sqlite3', 'aiida.sqlite3', 'provider.key', 'launcher.sock']
    paths = []
    for name in names:
        file = canaries / name
        if not file.exists(): file.write_text('synthetic-isolation-canary')
        paths.append(str(file))
    probes = paths + ['/app/application.sqlite3', '/aiida/aiida.sqlite3', '/run/provider.key', '/var/run/docker.sock', '/probe/launch.py']
    script = '''require 'json'
paths = JSON.parse(%s)
paths.each do |path|
  begin
    File.read(path)
    raise "Prohibited readable path: #{path}"
  rescue Errno::ENOENT, Errno::EACCES
  end
end
raise 'Wrong UID' unless Process.uid == 10001
status = File.read('/proc/self/status')
raise 'Capabilities retained' unless status.match?(/^CapEff:\\s+0+$/)
raise 'Privileges enabled' unless status.match?(/^NoNewPrivs:\\s+1$/)
['/native/forbidden-write', '/run/model.key'].each do |path|
  begin
    File.open(path, 'a') { }
    raise 'Protected write succeeded'
  rescue Errno::EROFS, Errno::EACCES
  end
end
raise 'Execution runtime present' if Dir.glob('/usr/bin/python*').any? || File.exist?('/usr/local/bin/python') || File.exist?('/usr/local/bin/docker')
raise 'Provider environment' if ENV.keys.any? { |k| k.match?(/OPENAI|ANTHROPIC|AWS_|AIIDA|DOCKER_HOST|LAUNCHER/) }
puts JSON.generate({uid: Process.uid, denied_paths: paths.length, capabilities: 0, no_new_privileges: true})
''' % json.dumps(json.dumps(probes))
    result = json.loads(ruby(script))
    assert result['denied_paths'] == len(probes)


def test_actual_cross_network_endpoint_denial(owned_modeling):
    # A live synthetic app endpoint on a distinct bridge, with positive control.
    _, deployment, _ = owned_modeling
    name = deployment.container + '-canary'
    network = name + '-private'
    label = deployment.label + '=' + deployment.owner
    assert runtime.inspect(name) is None and runtime.inspect(network, 'network') is None
    made_network = made_container = False
    try:
        runtime.run('docker', 'network', 'create', '--internal', '--label', label, network)
        made_network = True
        server = "require 'socket'; s=TCPServer.new('0.0.0.0',3443); loop { c=s.accept; c.write('synthetic-app-canary'); c.close }"
        runtime.run('docker', 'run', '-d', '--name', name, '--label', label, '--network', network,
                    '--user', '10001:10001', '--read-only', '--cap-drop', 'ALL', '--security-opt',
                    'no-new-privileges', '--pids-limit', '32', '--memory', '64m', '--entrypoint',
                    'ruby', runtime.source_build_inputs()['ruby_image'], '-e', server)
        made_container = True
        probe = "require 'socket'; puts TCPSocket.new('127.0.0.1',3443).read"
        for attempt in range(20):
            positive = subprocess.run(['docker', 'exec', name, 'ruby', '-e', probe], capture_output=True, text=True)
            if positive.returncode == 0: break
            time.sleep(.1)
        assert positive.returncode == 0 and 'synthetic-app-canary' in positive.stdout
        address = runtime.inspect(name)['NetworkSettings']['Networks'][network]['IPAddress']
        result = ruby("require 'socket'; require 'json'; begin; Socket.tcp("+json.dumps(address)+",3443,connect_timeout:2) { |s| raise 'Cross-network endpoint reachable' }; rescue Errno::EHOSTUNREACH, Errno::ENETUNREACH, Errno::ETIMEDOUT, IO::TimeoutError; puts JSON.generate({denied:true}); end")
        assert json.loads(result)['denied']
    finally:
        if made_container:
            info = runtime.inspect(name)
            assert info['Config']['Labels'][deployment.label] == deployment.owner
            runtime.run('docker', 'rm', '-f', name)
        if made_network:
            info = runtime.inspect(network, 'network')
            assert info['Labels'][deployment.label] == deployment.owner
            runtime.run('docker', 'network', 'rm', network)


def test_owned_stop_setup_retains_revisions_and_credentials(owned_modeling):
    root, deployment, _ = owned_modeling
    c = ModelClient()
    draft = c.edit(c.create('Restart / retention'), creation())
    revision = c.commit(draft)
    keys = {name: (root/'credentials'/name).read_bytes() for name in ('model.key', 'rails.key')}
    before = runtime.check(root, deployment=deployment)
    try:
        assert not runtime.stop(root, deployment=deployment)['running']
    finally:
        runtime.setup(root, deployment=deployment)
    for attempt in range(300):
        ready = subprocess.run(['docker', 'exec', deployment.container, 'ruby', '-rsocket', '-e', "TCPSocket.new('127.0.0.1',3000).close"], capture_output=True)
        if ready.returncode == 0: break
        time.sleep(.2)
    assert ready.returncode == 0
    assert runtime.check(root, deployment=deployment) == before
    assert all((root/'credentials'/name).read_bytes() == raw for name, raw in keys.items())
    path = '/models/'+draft['model_id']
    assert c.call('GET', path)['data'] == draft
    assert c.call('GET', path+'/revisions/'+revision['model_revision_id'])['data'] == revision
    (root/'evidence/restart-retention.json').write_text(json.dumps(dict(model_id=draft['model_id'], model_revision_id=revision['model_revision_id'], revision_digest=revision['digest'], image=before['image'], credential_retention=True), indent=2))
