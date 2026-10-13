"""Static-only native origin tests. Never import or run generated candidate Python."""
import base64
import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def native(code):
    import sys
    sys.path.insert(0,str(ROOT/'deployment/tests'))
    import scoped_fixture as fixture
    from checks import PROJECTION_SCOPE
    fixture.validate_scope(PROJECTION_SCOPE)
    from units_model_fixture import run_ruby
    return json.loads(run_ruby(code).split('NATIVE_RESULT=')[-1])


BOOT = """
ENV['DATABASE_URL']='sqlite3:/tmp/reference.sqlite3'
require '/native/config/environment'
require 'json'
ActiveRecord::Schema.verbose=false
load '/native/db/schema.rb'
ActiveRecord::Base.connection.add_column(:openmdao_discipline_impls,:python_source,:text) unless OpenmdaoDisciplineImpl.column_names.include?('python_source')
OpenmdaoDisciplineImpl.reset_column_information
"""


def test_real_native_static_origin_and_explicit_connections():
    result = native(BOOT + """
require 'whats_opt/openmdao_generator'
a=Analysis.create!(name:'frozen_model',public:false)
a.impl.update!(package_name:'frozen_model',parallel_group:false,use_units:true)
a.impl.nonlinear_solver.update!(name:'NonlinearRunOnce')
a.impl.linear_solver.update!(name:'LinearRunOnce')
d1=Discipline.create!(analysis:a,name:'component_aaa')
d2=Discipline.create!(analysis:a,name:'component_bbb')
d1.impl.update!(python_source: "outputs['y'] = inputs['_x'] * 2\\n")
d2.impl.update!(python_source: "outputs['z'] = inputs['other']\\n")
x=Variable.create!(discipline:d1,name:'p_x',io_mode:'in',type:'Float',shape:'1',units:'m')
y=Variable.create!(discipline:d1,name:'p_y',io_mode:'out',type:'Float',shape:'1',units:'m')
t=Variable.create!(discipline:d2,name:'p_t',io_mode:'in',type:'Float',shape:'1',units:'km')
z=Variable.create!(discipline:d2,name:'p_z',io_mode:'out',type:'Float',shape:'1',units:'km')
Connection.create!(from:y,to:t)
g=WhatsOpt::OpenmdaoGenerator.new(a,static_only:true,symbol_maps:{d1.name=>{'inputs'=>{'_x'=>'p_x'},'outputs'=>{'y'=>'p_y'}},d2.name=>{'inputs'=>{'other'=>'p_t'},'outputs'=>{'z'=>'p_z'}}})
Dir.mkdir('/tmp/generated')
files=g._generate_code('/tmp/generated')
puts 'NATIVE_RESULT='+JSON.generate({'origin'=>g.method(:_generate_code).source_location,'templates'=>g.static_templates,'files'=>files.to_h { |f| [f.delete_prefix('/tmp/generated/'),File.read(f)] }})
""")
    assert result['origin'][0] == '/native/app/lib/whats_opt/openmdao_generator.rb'
    assert set(result['templates']) == {'openmdao_analysis.py.erb', 'openmdao_analysis_base.py.erb',
        'openmdao_discipline.py.erb', 'openmdao_discipline_base.py.erb', '__init__.py.erb', 'base_header_partial.py.erb'}
    group = result['files']['base/frozen_model_base.py']
    assert "self.connect('component_aaa.p_y', 'component_bbb.p_t')" in group
    assert 'promotes=' not in group
    assert 'NonlinearRunOnce()' in group and 'LinearRunOnce()' in group
    assert "units='km'" in result['files']['base/component_bbb_base.py']
    assert "outputs['y'] = inputs['_x'] * 2" in result['files']['impl/component_aaa.py']
    assert not any(path.startswith('run_') for path in result['files'])


def test_native_generator_disabled_fails_closed():
    result = native(BOOT + """
require 'whats_opt/openmdao_generator'
puts 'NATIVE_RESULT='+JSON.generate({'denied'=>WhatsOpt::OpenmdaoGenerator.instance_method(:initialize).parameters.include?([:key,:static_only])})
""")
    assert result['denied']

def public_fixture(fanout=False):
    import hashlib
    raw=b"\xef\xbb\xbf# caf\xc3\xa9 <%= File.write('/tmp/erb-canary', 'bad') %>\r\nraise RuntimeError('candidate must not execute')\r\noutputs['y'] = inputs['_x'] * 2"
    def port(key,direction):
        return dict(temp_key=key.lstrip('_'),direction=direction,name=key,code_symbol=key,value_type='real_scalar',units='m')
    edits=[dict(kind='create_definition',temp_key='d',definition_kind='explicit_component',name='Native source',ports=[port('_x','input'),port('y','output')],source=dict(encoding='base64',media_type='text/x-python',bytes=base64.b64encode(raw).decode(),sha256=hashlib.sha256(raw).hexdigest())),
           dict(kind='instantiate',temp_key='a',version_ref=dict(temp_key='d')),
           dict(kind='instantiate',temp_key='b',version_ref=dict(temp_key='d')),
           dict(kind='connect',temp_key='wire',source_ref=dict(instance_temp_key='a',definition_temp_key='d',port_temp_key='y'),target_ref=dict(instance_temp_key='b',definition_temp_key='d',port_temp_key='x'))]
    if fanout:
        other=b"outputs['z'] = inputs['left'] + inputs['right']\n"
        ports=[dict(temp_key=k,direction=d,name=k,code_symbol=k,value_type='real_scalar',units='km') for k,d in [('left','input'),('right','input'),('z','output')]]
        target=dict(kind='create_definition',temp_key='t',definition_kind='explicit_component',name='Other',ports=ports,source=dict(encoding='base64',media_type='text/x-python',bytes=base64.b64encode(other).decode(),sha256=hashlib.sha256(other).hexdigest()))
        edits=[edits[0],target,dict(kind='instantiate',temp_key='c',version_ref=dict(temp_key='t')),edits[2],edits[1]] + [dict(kind='connect',temp_key='w'+key,source_ref=dict(instance_temp_key='a',definition_temp_key='d',port_temp_key='y'),target_ref=dict(instance_temp_key='c',definition_temp_key='t',port_temp_key=key)) for key in ('left','right')]
    encoded=base64.b64encode(json.dumps(edits).encode()).decode()
    return raw, BOOT+"""
load '/native/db/migrate/20261008160000_add_hyprn_mvp_study_boundary.rb'
AddHyprnMvpStudyBoundary.new.migrate(:up)
load '/native/db/migrate/20261008175500_create_modeling_contract.rb'
CreateModelingContract.new.migrate(:up)
scope={'study_id'=>SecureRandom.uuid,'actor_id'=>SecureRandom.uuid,'permissions'=>%w[read write],'resource_ids'=>['*'],'request_id'=>SecureRandom.uuid}
c=ModelingContract.new(scope)
created=c.route('POST','/models',{}, {'command_id'=>SecureRandom.uuid,'expected_revision'=>nil,'study_id'=>scope['study_id'],'name'=>'Synthetic static test','template'=>'empty'})[1]['data']
path='/models/'+created['model_id']
edits=JSON.parse(Base64.strict_decode64('"""+encoded+"""'))
draft=c.route('POST',path+'/edits',{}, {'command_id'=>SecureRandom.uuid,'expected_revision'=>created['draft_revision'],'edits'=>edits})[1]['data']
m=c.route('POST',path+'/commits',{}, {'command_id'=>SecureRandom.uuid,'expected_revision'=>draft['draft_revision']})[1]['data']
cfg={'schema_version'=>'1','study_id'=>scope['study_id'],'model_id'=>m['model_id'],'model_revision_id'=>m['model_revision_id'],'configuration_id'=>SecureRandom.uuid,'configuration_revision_id'=>SecureRandom.uuid,'parent_revision_id'=>nil,'name'=>'Static fixture','inputs'=>[],'criteria'=>[],'numerical'=>{'mode'=>'deterministic','initialization'=>[],'solvers'=>[],'design_variables'=>[],'objectives'=>[],'constraints'=>[],'optimizer'=>nil,'uncertainty'=>nil,'derivatives'=>{'method'=>'none','form'=>nil,'check'=>nil}},'context_snapshot'=>{'description'=>'test','boundary'=>'','notes'=>[]},'evidence_snapshots'=>[],'required_capabilities'=>['flat_explicit_scalar']}
incoming=m['connections'].map { |x| x['target_ref'] }
m['instances'].each do |i|
  d=m['definitions'].find { |d| d['definition_version_id']==i['definition_version_id'] }
  d['ports'].select { |p| p['direction']=='input' }.each do |p|
    target={'instance_id'=>i['instance_id'],'port_id'=>p['port_id']}
    cfg['inputs'] << {'target'=>target,'value'=>7,'units'=>p['units'],'provenance'=>{'kind'=>'manual','statement'=>'Explicit fixture value','evidence_version_ids'=>[]}} unless incoming.include?(target)
  end
end
cfg['digest']=ModelingContract.digest(cfg)
body={'command_id'=>SecureRandom.uuid,'model_revision_id'=>m['model_revision_id'],'configuration_snapshot'=>cfg,'configuration_digest'=>cfg['digest']}
"""


def test_prepare_exact_source_determinism_draft_purity_and_manifest():
    import hashlib
    import sys
    sys.path.insert(0,str(ROOT/'contracts/tests'))
    from test_native_program_contract import check_program, validate
    raw, setup=public_fixture()
    result=native(setup+"""
before=ModelingContract.canonical(c.draft(c.identity(m['model_id'],'model')))
first=c.route('POST',path+'/prepare-execution',{},body)[1]['data']
raise 'Draft mutation' unless before==ModelingContract.canonical(c.draft(c.identity(m['model_id'],'model')))
second=c.route('POST',path+'/prepare-execution',{},body.merge('command_id'=>SecureRandom.uuid))[1]['data']
raise 'Nondeterministic native generation' unless first['executable_content_digest']==second['executable_content_digest']
instance=m['instances'][0]['instance_id']
c.route('POST',path+'/edits',{}, {'command_id'=>SecureRandom.uuid,'expected_revision'=>draft['draft_revision'],'edits'=>[{'kind'=>'rename_instance','instance_id'=>instance,'name'=>'renamed display'}]})
third=c.route('POST',path+'/prepare-execution',{},body.merge('command_id'=>SecureRandom.uuid))[1]['data']
raise 'Current draft dependency' unless first['executable_content_digest']==third['executable_content_digest']
raise 'Candidate/ERB executed' if File.exist?('/tmp/erb-canary')
stored=ModelingRevision.find_by(public_id:first['preparation_id']).payload['bytes']
files=first['files'].to_h { |f| [f['path'],stored.fetch(f['file_id'])['bytes']] }
raise 'Scratch leak' unless Dir.glob('/tmp/hyprn-mvp-native-*/request-*').empty?
puts 'NATIVE_RESULT='+JSON.generate({'artifact'=>first,'files'=>files,'capabilities'=>c.route('GET','/capabilities',{},nil)[1]['data']})
""")
    artifact=result['artifact']; files={p:base64.b64decode(v) for p,v in result['files'].items()}
    check_program(artifact,files,artifact['prepared_digest'])
    validate('ProgramProvenance',json.loads(files['provenance/generator.json']))
    validate('Capabilities',result['capabilities'])
    assert files['sources/'+hashlib.sha256(raw).hexdigest()+'.py']==raw
    assert b'<%= File.write' in b''.join(b for p,b in files.items() if p.startswith('generated/impl/'))
    assert artifact['schema_version']=='2'


def test_actual_generator_failure_prevents_preparation():
    _, setup=public_fixture()
    result=native(setup+"""
before=ModelingRevision.where(kind:'preparation').count
# Force the actual fixed generator process to fail; no alternative producer exists.
Process.singleton_class.prepend(Module.new do
  def spawn(*args, **options)
    raise 'native helper sentinel' if args.include?('/native/script/native_static.rb')
    super
  end
end)
begin
  c.route('POST',path+'/prepare-execution',{},body)
  failed=false
rescue RuntimeError => e
  failed=e.message=='native helper sentinel'
end
puts 'NATIVE_RESULT='+JSON.generate({'failed'=>failed,'no_artifact'=>ModelingRevision.where(kind:'preparation').count==before,'clean'=>Dir.glob('/tmp/hyprn-mvp-native-*/request-*').empty?})
""")
    assert result==dict(failed=True,no_artifact=True,clean=True)

def test_concurrent_generation_orphan_cleanup_and_semantic_tamper():
    _,setup=public_fixture()
    result=native(setup+"""
NativeProgram;NativeMaterializer
root="/tmp/hyprn-mvp-native-#{Process.uid}"
Dir.mkdir(root,0700)
orphan=root+'/request-expired'
Dir.mkdir(orphan,0700);File.write(orphan+'/lease','');File.utime(Time.now-300,Time.now-300,orphan)
active=root+'/request-active'
Dir.mkdir(active,0700);lease=File.open(active+'/lease','w');lease.flock(File::LOCK_EX);File.utime(Time.now-300,Time.now-300,active)
db=ActiveRecord::Base.connection_db_config.database
threads=3.times.map { Thread.new { NativeProgram.generate(m,cfg) } }
outputs=threads.map(&:value)
raise 'Nondeterministic concurrency' unless outputs.uniq.size==1
raise 'Global connection changed' unless ActiveRecord::Base.connection_db_config.database==db
raise 'Bad orphan cleanup' if File.exist?(orphan) || !File.exist?(active)
lease.close;FileUtils.remove_entry_secure(active)
failures=[]
[:duplicate,:wrong_unit,:wrong_source,:extra_file].each do |kind|
  files=outputs[0].dup
  case kind
  when :duplicate
    bindings=JSON.parse(files['generated/bindings.json']);bindings['outputs'] << bindings['outputs'][0];files['generated/bindings.json']=JSON.generate(bindings)
  when :wrong_unit
    bindings=JSON.parse(files['generated/bindings.json']);bindings['inputs'][0]['units']='km';files['generated/bindings.json']=JSON.generate(bindings)
  when :wrong_source
    sm=JSON.parse(files['generated/source-map.json']);sm['entries'][0]['source_sha256']='0'*64;files['generated/source-map.json']=JSON.generate(sm)
  when :extra_file
    files['generated/unannounced.py']='raise RuntimeError()'
  end
  begin
    NativeProgram.validate_files!(m,cfg,files)
    failures << false
  rescue RuntimeError,ModelingContract::Failure
    failures << true
  end
end
puts 'NATIVE_RESULT='+JSON.generate({'rejected'=>failures,'clean'=>Dir.glob(root+'/request-*').empty?})
""")
    assert result==dict(rejected=[True]*4,clean=True)


def test_timeout_cleans_child_and_scratch():
    _,setup=public_fixture()
    result=native(setup+"""
NativeProgram
Timeout.singleton_class.prepend(Module.new do
  def timeout(seconds,*args,&block)
    raise Timeout::Error if seconds==NativeProgram::TIMEOUT
    super
  end
end)
begin
  NativeProgram.generate(m,cfg)
  failed=false
rescue Timeout::Error
  failed=true
end
puts 'NATIVE_RESULT='+JSON.generate({'failed'=>failed,'clean'=>Dir.glob('/tmp/hyprn-mvp-native-*/request-*').empty?,'children'=>Process.waitall.empty?})
""")
    assert result==dict(failed=True,clean=True,children=True)


def test_direct_native_reference_matches_public_materializer():
    _,setup=public_fixture()
    result=native(setup+"""
generated=NativeProgram.generate(m,cfg)
# Independent native fixture: no NativeMaterializer mapping call below.
# Its two same-definition instances and native Connection are explicit.
source_id=m['connections'][0]['source_ref']['instance_id']
target_id=m['connections'][0]['target_ref']['instance_id']
definition=m['definitions'][0]
input=definition['ports'].find { |p| p['direction']=='input' }
output=definition['ports'].find { |p| p['direction']=='output' }
analysis=Analysis.create!(name:'frozen_model',public:false)
analysis.impl.update!(package_name:'frozen_model',parallel_group:false,use_units:true)
analysis.impl.nonlinear_solver.update!(name:'NonlinearRunOnce',iprint:0)
analysis.impl.linear_solver.update!(name:'LinearRunOnce',iprint:0)
symbols={};vars={}
[source_id,target_id].each_with_index do |iid,index|
  name='component_'+iid.delete('-')
  d=Discipline.create!(analysis:analysis,name:name,position:index+1)
  d.impl.update!(python_source:Base64.strict_decode64(m['source_files'][0]['bytes']).force_encoding('UTF-8'),support_derivatives:false)
  vars[iid]={}
  [input,output].each do |port|
    vars[iid][port['direction']]=Variable.create!(discipline:d,name:'p_'+port['port_id'].delete('-'),io_mode:port['direction']=='input' ? 'in' : 'out',type:'Float',shape:'1',units:'m')
  end
  symbols[name]={'inputs'=>{'_x'=>vars[iid]['input'].name},'outputs'=>{'y'=>vars[iid]['output'].name}}
end
Connection.create!(from:vars[source_id]['output'],to:vars[target_id]['input'])
reference=WhatsOpt::OpenmdaoGenerator.new(analysis,static_only:true,symbol_maps:symbols)
Dir.mkdir('/tmp/reference-generated')
paths=reference._generate_code('/tmp/reference-generated')
equal=paths.all? { |p| File.binread(p)==generated.fetch('generated/'+p.delete_prefix('/tmp/reference-generated/')) }
puts 'NATIVE_RESULT='+JSON.generate({'equal'=>equal,'file_count'=>paths.size})
""")
    assert result==dict(equal=True,file_count=9)


def test_real_generator_and_invoked_template_sentinels_fail_prepare():
    _,setup=public_fixture()
    result=native(setup+"""
# A test-only injected require runs after the helper's environment is established.
# It disables the actual native method/template invoked in that child.
File.write('/tmp/native-sentinel.rb', <<~'SENTINEL')
  module Kernel
    alias native_original_require require
    def require(name)
      result=native_original_require(name)
      if name=='/native/config/environment'
        native_original_require('whats_opt/openmdao_generator')
        WhatsOpt::OpenmdaoGenerator.class_eval do
          def _generate_code(*args)
            raise 'real native generator disabled'
          end
        end
      end
      result
    end
  end
SENTINEL
Process.singleton_class.prepend(Module.new do
  def spawn(*args, **options)
    args[0]=args[0].merge('RUBYOPT'=>'-r/tmp/native-sentinel.rb') if args.include?('/native/script/native_static.rb')
    super(*args,**options)
  end
end)
failed=[]
2.times do |index|
  if index==1
    File.write('/tmp/native-sentinel.rb', File.read('/tmp/native-sentinel.rb').sub('def _generate_code(*args)', 'def _run_template(*args)'))
  end
  begin
    c.route('POST',path+'/prepare-execution',{},body.merge('command_id'=>SecureRandom.uuid))
    failed << false
  rescue RuntimeError => e
    failed << (e.message=='Native static generation failed')
  end
end
puts 'NATIVE_RESULT='+JSON.generate({'failed'=>failed,'clean'=>Dir.glob('/tmp/hyprn-mvp-native-*/request-*').empty?,'artifacts'=>ModelingRevision.where(kind:'preparation').count})
""")
    assert result==dict(failed=[True,True],clean=True,artifacts=0)

def test_fanout_distinct_symbols_units_and_disconnected_repeat():
    _,setup=public_fixture(fanout=True)
    result=native(setup+"""
files=NativeProgram.generate(m,cfg)
bindings=JSON.parse(files['generated/bindings.json'])
expected=m['connections'].map do |c|
  source='component_'+c['source_ref']['instance_id'].delete('-')+'.p_'+c['source_ref']['port_id'].delete('-')
  target='component_'+c['target_ref']['instance_id'].delete('-')+'.p_'+c['target_ref']['port_id'].delete('-')
  "self.connect('#{source}', '#{target}')"
end
group=files['generated/base/frozen_model_base.py']
other=m['definitions'].find { |d| d['ports'].size==3 }
iid=m['instances'].find { |i| i['definition_version_id']==other['definition_version_id'] }['instance_id']
target='component_'+iid.delete('-')
implementation=files['generated/impl/'+target+'.py']
puts 'NATIVE_RESULT='+JSON.generate({'connections'=>expected.all? { |s| group.include?(s) },'free_inputs'=>bindings['inputs'].size,'components'=>bindings['components'].size,'units'=>files['generated/base/'+target+'_base.py'].include?("units='km'"),'symbols'=>implementation.include?('"left":"p_') && implementation.include?('"right":"p_'),'promotes'=>group.include?('promotes=')})
""")
    assert result==dict(connections=True,free_inputs=2,components=3,units=True,symbols=True,promotes=False)


def test_save_validate_export_import_prepare_canary_stays_data():
    import hashlib
    raw,setup=public_fixture()
    exported=native(setup+"""
c.route('POST',path+'/validate',{}, {'model_revision_id'=>m['model_revision_id']})
puts 'NATIVE_RESULT='+JSON.generate({'package'=>c.export_package(c.identity(m['model_id'],'model'),m['model_revision_id']),'cfg'=>cfg})
""")
    encoded=base64.b64encode(json.dumps(exported).encode()).decode()
    # Entirely separate container/database; exact public IDs can be imported cleanly.
    result=native(BOOT+"""
load '/native/db/migrate/20261008160000_add_hyprn_mvp_study_boundary.rb';AddHyprnMvpStudyBoundary.new.migrate(:up)
load '/native/db/migrate/20261008175500_create_modeling_contract.rb';CreateModelingContract.new.migrate(:up)
payload=JSON.parse(Base64.strict_decode64('"""+encoded+"""'))
cfg=payload['cfg'];scope={'study_id'=>cfg['study_id'],'actor_id'=>SecureRandom.uuid,'permissions'=>%w[read write],'resource_ids'=>['*'],'request_id'=>SecureRandom.uuid}
c=ModelingContract.new(scope)
draft=c.route('POST','/imports',{}, {'command_id'=>SecureRandom.uuid,'expected_revision'=>nil,'study_id'=>scope['study_id'],'package'=>payload['package'],'preserve_public_ids'=>true})[1]['data']
path='/models/'+draft['model_id']
c.route('POST',path+'/validate',{}, {'model_revision_id'=>cfg['model_revision_id']})
artifact=c.route('POST',path+'/prepare-execution',{}, {'command_id'=>SecureRandom.uuid,'model_revision_id'=>cfg['model_revision_id'],'configuration_snapshot'=>cfg,'configuration_digest'=>cfg['digest']})[1]['data']
puts 'NATIVE_RESULT='+JSON.generate({'source'=>draft['source_files'][0],'prepared'=>artifact['schema_version'],'inert'=>!File.exist?('/tmp/erb-canary')})
""")
    assert base64.b64decode(result['source']['bytes'])==raw
    assert result['source']['sha256']==hashlib.sha256(raw).hexdigest()
    assert result['inert'] and result['prepared']=='2'
