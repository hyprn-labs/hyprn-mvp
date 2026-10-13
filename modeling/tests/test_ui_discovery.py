"""Real Rails/SQLite adapter tests in disposable confined containers, never live stores.

Use the existing audited producer image, overlay the repository adapter patches
and schema read-only, and initialize a new tmpfs database for every invocation.
Evidence is written only in the test's own scratch scope, allocated by deployment/checks.py.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time

import pytest

ROOT = Path(__file__).resolve().parents[2]
SERVICE = 'app/services/modeling_contract.rb'


def service_patch(path):
    text = path.read_text()
    start = text.index('--- a/' + SERVICE)
    end = text.find('\n--- ', start + 1)
    return text[start:] if end == -1 else text[start:end] + '\n'


@pytest.fixture(scope='module')
def harness():
    from checks import PROJECTION_SCOPE
    import scoped_fixture as guard
    root = guard.scoped_path(guard.validate_scope(PROJECTION_SCOPE), 'evidence/discovery')
    root.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='adapter-', dir=root))
    target = stage / SERVICE
    target.parent.mkdir(parents=True)
    patch = (ROOT / 'upstream/whatsopt-patches/040-modeling-contract.patch').read_text()
    section = patch.split('+++ b/' + SERVICE + '\n', 1)[1].split('\n--- ', 1)[0]
    target.write_text('\n'.join(line[1:] for line in section.splitlines() if line.startswith('+')) + '\n')
    for name in ['050-native-generation.patch', '060-ui-discovery.patch']:
        path = ROOT / 'upstream/whatsopt-patches' / name
        if path.exists():
            result = subprocess.run(['patch', '--batch', '-p1'], input=service_patch(path),
                                    cwd=stage, text=True, capture_output=True)
            (stage / (name + '.log')).write_text(result.stdout + result.stderr)
            assert result.returncode == 0, result.stdout + result.stderr
    schema = stage / 'modeling.schema.json'
    schema.write_bytes((ROOT / 'contracts/schemas/model.schema.json').read_bytes())
    pins = json.loads((ROOT / 'deployment/pins.json').read_text())
    image = pins['modeling_producer']['image']
    identity = dict(image=image, service_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                    schema_sha256=hashlib.sha256(schema.read_bytes()).hexdigest())
    (stage / 'identity.json').write_text(json.dumps(identity, indent=2) + '\n')
    return root, target, schema, image


def native(harness, script):
    root, target, schema, image = harness
    evidence = Path(tempfile.mkdtemp(prefix='case-', dir=root))
    code = BOOT + script
    (evidence / 'case.rb').write_text(code)
    command = ['docker', 'run', '--rm', '-i', '--network', 'none', '--read-only',
               '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
               '--user', '10001:10001', '--memory', '768m', '--cpus', '1', '--pids-limit', '64',
               '--tmpfs', '/tmp:rw,noexec,nosuid,size=192m,mode=1777',
               '--tmpfs', '/native/tmp:rw,nosuid,size=16m,mode=1777',
               '--tmpfs', '/native/log:rw,nosuid,size=16m,mode=1777',
               '--mount', f'type=bind,src={target},dst=/native/{SERVICE},readonly',
               '--mount', f'type=bind,src={schema},dst=/native/config/modeling.schema.json,readonly',
               '-e', 'RAILS_ENV=test', '-e', 'DISABLE_BOOTSNAP=1', '-e', 'HOME=/tmp',
               '-e', 'NATIVE_STATIC_GENERATION=1', '-e', 'SECRET_KEY_BASE=synthetic-discovery-only',
               '--entrypoint', 'ruby', image, '-']
    started = time.monotonic()
    result = subprocess.run(command, input=code, capture_output=True, text=True, timeout=55)
    for name, value in [('stdout', result.stdout), ('stderr', result.stderr)]:
        (evidence / name).write_text(value)
    (evidence / 'result.json').write_text(json.dumps(dict(command=command, exit_code=result.returncode,
        duration=time.monotonic()-started), indent=2) + '\n')
    assert result.returncode == 0, f'{evidence}\n{result.stderr[-3500:]}\n{result.stdout[-1200:]}'
    return json.loads(result.stdout.split('DISCOVERY_RESULT=')[-1])


BOOT = """
ENV['DATABASE_URL']='sqlite3:/tmp/discovery.sqlite3'
require '/native/config/environment'
require 'json'
ActiveRecord::Schema.verbose=false
load '/native/db/schema.rb'
ActiveRecord::Base.connection.add_column(:openmdao_discipline_impls,:python_source,:text) unless OpenmdaoDisciplineImpl.column_names.include?('python_source')
OpenmdaoDisciplineImpl.reset_column_information
load '/native/db/migrate/20261008160000_add_hyprn_mvp_study_boundary.rb'
AddHyprnMvpStudyBoundary.new.migrate(:up)
load '/native/db/migrate/20261008175500_create_modeling_contract.rb'
CreateModelingContract.new.migrate(:up)
def insist(value, message)
  raise message unless value
end
def scope
  {'study_id'=>SecureRandom.uuid,'actor_id'=>SecureRandom.uuid,'permissions'=>%w[read write],'resource_ids'=>['*'],'request_id'=>SecureRandom.uuid}
end
def invoke(s, method, path, query={}, body={})
  ModelingContract.new(s).route(method,path,query,body)
rescue ModelingContract::Failure => e
  [e.status,ModelingContract.error(e,s['request_id'])]
end
def create(s)
  invoke(s,'POST','/models',{}, {'command_id'=>SecureRandom.uuid,'expected_revision'=>nil,'study_id'=>s['study_id'],'name'=>'Original','template'=>'empty'})[1]['data']
end
def committed(s,m)
  result=invoke(s,'POST','/models/'+m['model_id']+'/commits',{}, {'command_id'=>SecureRandom.uuid,'expected_revision'=>m['draft_revision']})
  insist(result[0]==200,result.inspect);result[1]['data']
end
def database(domain=false)
  db=ActiveRecord::Base.connection
  tables=db.tables.sort.reject { |t| domain && t=='modeling_commands' }
  result=tables.to_h { |t| [t,db.select_all('SELECT * FROM '+db.quote_table_name(t)+' ORDER BY rowid').to_a] }
  result['sqlite_sequence']=db.select_all('SELECT * FROM sqlite_sequence ORDER BY name').to_a.reject { |r| domain && r['name']=='modeling_commands' }
  ModelingContract.canonical(result)
end
s=scope;m=create(s);path='/models/'+m['model_id']
"""


def test_empty_and_stable_pages_include_only_exact_stored_revisions(harness):
    result = native(harness, """
empty=invoke(s,'GET',path+'/revisions')
insist(empty==[200,{'data'=>{'items'=>[],'next_cursor'=>nil}}],empty.inspect)
pins=3.times.map { committed(s,m) }
before=database
first=invoke(s,'GET',path+'/revisions',{'limit'=>'1'})[1]['data']
insist(database==before,'listing mutated database/sequences')
pins << committed(s,m)
second=invoke(s,'GET',path+'/revisions',{'limit'=>'2','cursor'=>first['next_cursor']})[1]['data']
last=invoke(s,'GET',path+'/revisions',{'limit'=>'100','cursor'=>second['next_cursor']})[1]['data']
rows=first['items']+second['items']+last['items']
expected=pins.map { |p| p.slice('model_revision_id','parent_model_revision_id','originating_draft_revision','digest') }
insist(rows==expected,'pagination did not follow immutable insertion order')
insist(last['next_cursor'].nil?,'terminal cursor')
tail=invoke(s,'GET',path+'/revisions',{'cursor'=>pins.last['model_revision_id']})[1]['data']
insist(tail=={'items'=>[],'next_cursor'=>nil},'past-end page')
puts 'DISCOVERY_RESULT='+JSON.generate({'count'=>rows.length,'first'=>rows.first})
""")
    assert result['count'] == 4
    assert result['first']['parent_model_revision_id'] is None


def test_cursor_query_and_authorization_fail_closed_without_effect(harness):
    result = native(harness, """
committed(s,m);other=create(s);foreign=committed(s,other)
before=database
queries=[{'limit'=>'0'},{'limit'=>'101'},{'limit'=>'1.0'},{'limit'=>'-1'},{'limit'=>['2']},{'cursor'=>'bad'},{'cursor'=>[]},{'unexpected'=>'x'}]
queries.each { |q| insist(invoke(s,'GET',path+'/revisions',q)[0]==400,'bad query '+q.inspect) }
insist(invoke(s,'GET',path+'/revisions',{'cursor'=>foreign['model_revision_id']})[0]==404,'foreign cursor leak')
insist(invoke(s,'GET',path+'/revisions',{'cursor'=>SecureRandom.uuid})[0]==404,'missing cursor')
insist(invoke(scope,'GET',path+'/revisions')[0]==404,'cross study')
insist(invoke(s.merge('resource_ids'=>[other['model_id']]),'GET',path+'/revisions')[0]==403,'cross model')
insist(invoke(s.merge('permissions'=>['write']),'GET',path+'/revisions')[0]==403,'read required')
insist(database==before,'failed read wrote state')
puts 'DISCOVERY_RESULT='+JSON.generate({'rejections'=>queries.length+5})
""")
    assert result['rejections'] == 13


def test_rename_preview_atomic_apply_replay_and_raw_history(harness):
    result = native(harness, r"""
raw="\xEF\xBB\xBF# caf\xC3\xA9\r\nopen('/tmp/candidate-canary','w').write('executed')\r\noutputs['y'] = inputs['x'] * 2\r\n".b
source={'encoding'=>'base64','media_type'=>'text/x-python','bytes'=>Base64.strict_encode64(raw),'sha256'=>Digest::SHA256.hexdigest(raw)}
ports=%w[x y].map { |k| {'temp_key'=>k,'direction'=>k=='x' ? 'input' : 'output','name'=>k,'code_symbol'=>k,'value_type'=>'real_scalar','units'=>''} }
setup=[{'kind'=>'create_definition','temp_key'=>'d','definition_kind'=>'explicit_component','name'=>'Canary','ports'=>ports,'source'=>source},{'kind'=>'instantiate','temp_key'=>'i','version_ref'=>{'temp_key'=>'d'}}]
m=invoke(s,'POST',path+'/edits',{}, {'command_id'=>SecureRandom.uuid,'expected_revision'=>m['draft_revision'],'edits'=>setup})[1]['data']
pin=committed(s,m)
stored=ModelingRevision.find_by!(public_id:pin['model_revision_id']).read_attribute_before_type_cast('payload')
before=database
preview={'expected_revision'=>m['draft_revision'],'edits'=>[{'kind'=>'rename_model','name'=>'Engineering / α'}]}
projected=invoke(s,'POST',path+'/preview',{},preview)
insist(projected[0]==200 && projected[1]['data']['name']=='Engineering / α',projected.inspect)
insist(database==before,'preview allocates rows/sequences')
insist(!File.exist?('/tmp/candidate-canary'),'preview executed source')
command=preview.merge('command_id'=>SecureRandom.uuid)
first=invoke(s,'POST',path+'/edits',{},command)
insist(first[0]==200,first.inspect)
current=first[1]['data'];insist(current['draft_revision']!=m['draft_revision'],'token unchanged')
insist(current['model_id']==m['model_id'] && current['instances']==m['instances'] && current['definitions']==m['definitions'],'stable identity changed')
insist(Analysis.find(ModelingIdentity.find_by!(public_id:m['model_id']).native_id).name=='Engineering / α','native label unchanged')
after=database
insist(invoke(s,'POST',path+'/edits',{},command)==first,'not original replay')
insist(database==after,'replay changed state')
conflict=invoke(s,'POST',path+'/edits',{},command.merge('edits'=>[{'kind'=>'rename_model','name'=>'Other'}]))
insist(conflict[0]==409 && conflict[1]['error']['code']=='command_payload_conflict','conflicting replay')
stale=invoke(s,'POST',path+'/edits',{},preview.merge('command_id'=>SecureRandom.uuid))
insist(stale[0]==409 && stale[1]['error']['code']=='stale_revision','stale accepted')
rollback_before=database(true)
bad={'command_id'=>SecureRandom.uuid,'expected_revision'=>current['draft_revision'],'edits'=>[{'kind'=>'rename_model','name'=>'Must rollback'},{'kind'=>'disconnect','connection_id'=>SecureRandom.uuid}]}
rejected=invoke(s,'POST',path+'/edits',{},bad)
insist(rejected[0]==409 && database(true)==rollback_before,'partial batch persisted')
insist(invoke(s,'POST',path+'/edits',{},bad)==rejected,'rejected receipt replay')
insist(ModelingRevision.find_by!(public_id:pin['model_revision_id']).read_attribute_before_type_cast('payload')==stored,'raw immutable bytes changed')
insist(invoke(s,'GET',path+'/revisions/'+pin['model_revision_id'])[1]['data']==pin,'historical read changed')
insist(current['source_files'][0]==source,'source bytes changed')
insist(!File.exist?('/tmp/candidate-canary'),'save imported candidate')
puts 'DISCOVERY_RESULT='+JSON.generate({'name'=>current['name'],'old_digest'=>pin['digest'],'source_sha256'=>source['sha256']})
""")
    assert result['name'] == 'Engineering / α'


def test_invalid_rename_has_no_receipt_and_capabilities_are_additive(harness):
    result = native(harness, """
before=database
['','a'*4097,nil,123].each do |name|
  body={'command_id'=>SecureRandom.uuid,'expected_revision'=>m['draft_revision'],'edits'=>[{'kind'=>'rename_model','name'=>name}]}
  insist(invoke(s,'POST',path+'/edits',{},body)[0]==400,'invalid name accepted')
end
insist(database==before,'invalid schema wrote receipt')
caps=invoke(s,'GET','/capabilities')[1]['data']
insist(caps['contract_versions'].include?('1') && caps['contract_versions'].include?('1.1'),'version negotiation lost')
%w[model_revision_listing model_rename flat_explicit_scalar].each { |id| insist(caps['capabilities'].any? { |c| c['id']==id && c['supported'] },'missing capability '+id) }
insist(caps['execution_versions']['artifact_versions']==['2'],'native protocol changed')
puts 'DISCOVERY_RESULT='+JSON.generate({'versions'=>caps['contract_versions']})
""")
    assert '1.1' in result['versions']


def test_late_native_failure_rolls_back_name_and_replays_rejection(harness):
    result = native(harness, """
before=database(true)
ModelingIdentity.prepend(Module.new do
  def update!(attributes)
    if attributes.dig(:metadata,'name')=='Failure after native label'
      raise ModelingContract::Failure.new(422,'invalid_model')
    end
    super
  end
end)
body={'command_id'=>SecureRandom.uuid,'expected_revision'=>m['draft_revision'],'edits'=>[{'kind'=>'rename_model','name'=>'Failure after native label'}]}
answer=invoke(s,'POST',path+'/edits',{},body)
insist(answer[0]==422,answer.inspect)
insist(database(true)==before,'native label leaked before metadata rollback')
insist(invoke(s,'POST',path+'/edits',{},body)==answer,'late rejection not replayed')
blank=body.merge('command_id'=>SecureRandom.uuid,'edits'=>[{'kind'=>'rename_model','name'=>'   '}])
rejected=invoke(s,'POST',path+'/edits',{},blank)
insist(rejected[0]==422 && rejected[1]['error']['outcome']=='unchanged','native invalid name became unknown failure')
insist(database(true)==before,'invalid native label changed state')
puts 'DISCOVERY_RESULT='+JSON.generate({'rolled_back'=>true})
""")
    assert result['rolled_back']


def test_concurrent_command_is_one_effect_and_receipt(harness):
    result = native(harness, """
body={'command_id'=>SecureRandom.uuid,'expected_revision'=>m['draft_revision'],'edits'=>[{'kind'=>'rename_model','name'=>'Concurrent name'}]}
threads=3.times.map { Thread.new { ActiveRecord::Base.connection_pool.with_connection { invoke(s,'POST',path+'/edits',{},body) } } }
answers=threads.map(&:value)
insist(answers.all? { |r| r==answers.first && r[0]==200 },answers.inspect)
insist(ModelingCommand.where(command_id:body['command_id']).count==1,'duplicate receipt')
insist(invoke(s,'GET',path)[1]['data']==answers.first[1]['data'],'not original result')
puts 'DISCOVERY_RESULT='+JSON.generate({'receipts'=>1})
""")
    assert result['receipts'] == 1


def test_actual_http_list_envelope_auth_query_and_limits(harness):
    result = native(harness, """
require 'openssl'
ENV['MODEL_KEY_FILE']='/tmp/discovery.key'
File.write(ENV['MODEL_KEY_FILE'],'synthetic-discovery-key')
pins=101.times.map { committed(s,m) }
session=ActionDispatch::Integration::Session.new(Rails.application)
def signed_get(session,s,path)
  h=Base64.urlsafe_encode64(JSON.generate({'alg'=>'HS256','typ'=>'JWT'}),padding:false)
  claims=s.merge('expires_at'=>Time.now.to_i+120,'method'=>'GET','path'=>path,'body_sha256'=>Digest::SHA256.hexdigest(''))
  p=Base64.urlsafe_encode64(JSON.generate(claims),padding:false)
  token=h+'.'+p
  signature=Base64.urlsafe_encode64(OpenSSL::HMAC.digest('SHA256','synthetic-discovery-key',token),padding:false)
  session.get(path,headers:{'Authorization'=>'Bearer '+token+'.'+signature})
  [session.response.status,JSON.parse(session.response.body)]
end
url='/modeling/1'+path+'/revisions'
first=signed_get(session,s,url)
insist(first[0]==200,first.inspect)
insist(first[1]['schema_version']=='1' && first[1]['request_id']==s['request_id'],'missing envelope')
insist(first[1]['data']['items'].length==50,'default page limit')
maximum=signed_get(session,s,url+'?limit=100')
insist(maximum[1]['data']['items'].length==100 && maximum[1]['data']['next_cursor']==pins[99]['model_revision_id'],'maximum page')
last=signed_get(session,s,url+'?cursor='+maximum[1]['data']['next_cursor'])
insist(last[1]['data']['items'].map { |x| x['model_revision_id'] }==[pins.last['model_revision_id']],'HTTP cursor')
insist(signed_get(session,s,url+'?limit=101')[0]==400,'HTTP limit accepted')
insist(signed_get(session,s,url+'?limit%5B%5D=1')[0]==400,'nested HTTP query accepted')
session.get(url);insist(session.response.status==401,'unsigned read allowed')
insist(signed_get(session,scope,url)[0]==404,'signed cross-study read allowed')
puts 'DISCOVERY_RESULT='+JSON.generate(first[1])
""")
    from jsonschema import Draft202012Validator, FormatChecker
    schema = json.loads((ROOT / 'contracts/schemas/model.schema.json').read_text())
    Draft202012Validator({**schema, '$ref': '#/$defs/RevisionListResponse'},
                         format_checker=FormatChecker()).validate(result)


def test_imported_parentage_is_discoverable_in_a_second_fresh_store(harness):
    package = native(harness, """
pins=3.times.map { committed(s,m) }
exported=invoke(s,'GET',path+'/export',{'revision'=>pins.last['model_revision_id']})
insist(exported[0]==200,exported.inspect)
puts 'DISCOVERY_RESULT='+JSON.generate(exported[1]['data'])
""")
    import base64
    encoded = base64.b64encode(json.dumps(package).encode()).decode()
    imported = native(harness, """
package=JSON.parse(Base64.strict_decode64('""" + encoded + """'))
answer=invoke(s,'POST','/imports',{}, {'command_id'=>SecureRandom.uuid,'expected_revision'=>nil,'study_id'=>s['study_id'],'package'=>package,'preserve_public_ids'=>true})
insist(answer[0]==201,answer.inspect)
id=answer[1]['data']['model_id']
rows=invoke(s,'GET','/models/'+id+'/revisions',{'limit'=>'2'})[1]['data']
tail=invoke(s,'GET','/models/'+id+'/revisions',{'cursor'=>rows['next_cursor']})[1]['data']
expected=package['revisions'].map { |p| p.slice('model_revision_id','parent_model_revision_id','originating_draft_revision','digest') }
insist(rows['items']+tail['items']==expected,'imported ancestry changed')
package['revisions'].each { |p| insist(invoke(s,'GET','/models/'+id+'/revisions/'+p['model_revision_id'])[1]['data']==p,'imported pin changed') }
puts 'DISCOVERY_RESULT='+JSON.generate({'count'=>expected.length,'model_id'=>id})
""")
    assert imported['count'] == 3
    assert imported['model_id'] == package['model_id']
