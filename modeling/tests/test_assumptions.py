"""Actual cumulative Rails adapter/static native generator in guarded tmpfs stores."""
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'deployment'), str(ROOT / 'deployment/tests'), str(ROOT / 'modeling/tests')]
import scoped_fixture as fixture
from test_native_generation import public_fixture
from test_ui_discovery import BOOT

PATCHES = ('040-modeling-contract.patch', '050-native-generation.patch', '060-ui-discovery.patch', '070-assumptions-evidence.patch')


@pytest.fixture(scope='module')
def harness():
    from checks import PROJECTION_SCOPE
    from modeling_runtime import stage_modeling_contract
    scope = fixture.validate_scope(PROJECTION_SCOPE)
    stage = fixture.scoped_path(scope, 'artifacts/adapter'); stage.mkdir()
    service = stage_modeling_contract(stage)
    native_path = 'app/services/native_materializer.rb'
    section = (ROOT / 'upstream/whatsopt-patches/050-native-generation.patch').read_text().split('+++ b/' + native_path + '\n', 1)[1].split('\n--- ', 1)[0]
    target = stage / native_path; target.parent.mkdir(parents=True)
    target.write_text('\n'.join(line[1:] for line in section.splitlines() if line.startswith('+')) + '\n')
    patch = (ROOT / 'upstream/whatsopt-patches/070-assumptions-evidence.patch').read_text()
    section = patch[patch.index('--- a/' + native_path + '\n'):]
    applied = subprocess.run(['patch', '--batch', '--fuzz=0', '-p1'], input=section, cwd=stage, text=True, capture_output=True)
    (stage / 'materializer-patch.log').write_text(applied.stdout + applied.stderr)
    assert applied.returncode == 0, applied.stdout + applied.stderr
    for name in PATCHES:
        (stage / name).write_bytes((ROOT / 'upstream/whatsopt-patches' / name).read_bytes())
    (stage / 'modeling.schema.json').write_bytes((ROOT / 'contracts/schemas/model.schema.json').read_bytes())
    pins = json.loads((ROOT / 'deployment/pins.json').read_bytes())
    image = pins['modeling_producer']['image']
    (stage / 'identity.json').write_text(json.dumps(dict(image=image, files={str(p.relative_to(stage)): hashlib.sha256(p.read_bytes()).hexdigest() for p in stage.rglob('*') if p.is_file()}), indent=2))
    return scope, stage, image


def native(harness, code):
    scope, stage, image = harness
    evidence = fixture.scoped_path(scope, 'evidence/native-' + str(uuid.uuid4())); evidence.mkdir()
    (evidence / 'case.rb').write_text(code)
    mounts = {'modeling_contract.rb': 'app/services/modeling_contract.rb', 'modeling.schema.json': 'config/modeling.schema.json', 'app/services/native_materializer.rb': 'app/services/native_materializer.rb'}
    mounts.update({name: 'provenance-inputs/patches/' + name for name in PATCHES})
    command = ['docker', 'run', '--rm', '-i', '--network', 'none', '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--user', '10001:10001', '--memory', '768m', '--cpus', '1', '--pids-limit', '64', '--tmpfs', '/tmp:rw,noexec,nosuid,size=192m,mode=1777', '--tmpfs', '/native/tmp:rw,nosuid,size=16m,mode=1777', '--tmpfs', '/native/log:rw,nosuid,size=16m,mode=1777', *[arg for src,dst in mounts.items() for arg in ('--mount', f'type=bind,src={stage/src},dst=/native/{dst},readonly')], '-e', 'RAILS_ENV=test', '-e', 'DISABLE_BOOTSNAP=1', '-e', 'HOME=/tmp', '-e', 'NATIVE_STATIC_GENERATION=1', '-e', 'SECRET_KEY_BASE=synthetic-assumptions-only', '--entrypoint', 'ruby', image, '-']
    started = time.monotonic()
    result = subprocess.run(command, input=code, text=True, capture_output=True, timeout=55, env=fixture.clean_environment(scope))
    (evidence / 'stdout.log').write_text(result.stdout); (evidence / 'stderr.log').write_text(result.stderr)
    (evidence / 'result.json').write_text(json.dumps(dict(command=command, exit=result.returncode, duration_seconds=time.monotonic()-started), indent=2))
    assert result.returncode == 0, str(evidence) + '\n' + result.stderr[-3500:] + result.stdout[-1500:]
    return json.loads(result.stdout.split('AE_RESULT=')[-1])


HELPERS = """
def edit(s,path,m,edits)
  invoke(s,'POST',path+'/edits',{}, {'schema_version'=>'2','command_id'=>SecureRandom.uuid,'expected_revision'=>m['draft_revision'],'edits'=>edits})
end
def add(key,owner,statement='Explicit assumption',links=[])
  {'kind'=>'add_assumption','temp_key'=>key,'owner'=>owner,'statement'=>statement,'evidence_links'=>links}
end
"""


def test_new_drafts_temporary_owners_independent_instances_and_rebind(harness):
    result = native(harness, BOOT + HELPERS + """
insist(m['schema_version']=='2' && m['assumptions']==[],'new draft version')
raw="outputs['y'] = inputs['x'] * 3\\n"
source={'encoding'=>'base64','media_type'=>'text/x-python','bytes'=>Base64.strict_encode64(raw),'sha256'=>Digest::SHA256.hexdigest(raw)}
ports=%w[x y].map { |k| {'temp_key'=>k,'direction'=>k=='x' ? 'input' : 'output','name'=>k,'code_symbol'=>k,'value_type'=>'real_scalar','units'=>''} }
edits=[{'kind'=>'create_definition','temp_key'=>'d','definition_kind'=>'explicit_component','name'=>'Same definition','ports'=>ports,'source'=>source},{'kind'=>'instantiate','temp_key'=>'a','version_ref'=>{'temp_key'=>'d'}},{'kind'=>'instantiate','temp_key'=>'b','version_ref'=>{'temp_key'=>'d'}},add('aa',{'kind'=>'instance','instance_temp_key'=>'a'}),add('bb',{'kind'=>'instance','instance_temp_key'=>'b'},'Different'),add('general',{'kind'=>'model'},'Global')]
answer=edit(s,path,m,edits);insist(answer[0]==200,answer.inspect);m=answer[1]['data'];ids=answer[1]['created_ids']
insist(m['assumptions'][0]['owner']=={'kind'=>'instance','instance_id'=>ids['a']['instance_id']},'temp owner retained')
before=committed(s,m);old_bytes=ModelingRevision.find_by!(public_id:before['model_revision_id']).read_attribute_before_type_cast('payload')
change=[{'kind'=>'update_assumption','assumption_id'=>ids['aa']['assumption_id'],'statement'=>'Updated A only','evidence_links'=>[]},{'kind'=>'revise_definition','temp_key'=>'d2','definition_id'=>ids['d']['definition_id'],'expected_definition_version_id'=>ids['d']['definition_version_id'],'changes'=>[{'kind'=>'rename_definition','name'=>'Revised'}]},{'kind'=>'replace_local_instance_version','instance_id'=>ids['a']['instance_id'],'expected_definition_version_id'=>ids['d']['definition_version_id'],'version_ref'=>{'temp_key'=>'d2'}},{'kind'=>'set_annotation','element_ref'=>ids['d']['definition_id'],'text'=>'Definition note, not assumption'}]
answer=edit(s,path,m,change);insist(answer[0]==200,answer.inspect);latest=answer[1]['data']
insist(latest['assumptions'][1..]==m['assumptions'][1..],'other owner changed')
insist(latest['assumptions'][0]['assumption_id']==m['assumptions'][0]['assumption_id'],'identity changed')
insist(latest['instances'].find { |i| i['instance_id']==ids['b']['instance_id'] }['definition_version_id']==ids['d']['definition_version_id'],'unselected rebind')
insist(latest['annotations'].last['text']=='Definition note, not assumption','notes lost')
insist(ModelingRevision.find_by!(public_id:before['model_revision_id']).read_attribute_before_type_cast('payload')==old_bytes,'old raw revision changed')
after=committed(s,latest);insist(before['digest']!=after['digest'],'assumptions not digested')
puts 'AE_RESULT='+JSON.generate({'before'=>before,'after'=>after})
""")
    assert len(result['after']['assumptions']) == 3


def test_preview_legacy_lazy_upgrade_cas_replay_and_late_batch_rollback(harness):
    result = native(harness, BOOT + HELPERS + """
row=ModelingIdentity.find_by!(public_id:m['model_id']);row.update!(metadata:row.metadata.except('schema_version','assumptions'))
m=invoke(s,'GET',path)[1]['data'];insist(m['schema_version']=='1' && !m.key?('assumptions'),'legacy rewritten')
old=committed(s,m);before=database
body={'schema_version'=>'2','command_id'=>SecureRandom.uuid,'expected_revision'=>m['draft_revision'],'edits'=>[add('a',{'kind'=>'model'})]}
preview=invoke(s,'POST',path+'/preview',{},body.except('command_id'))
insist(preview[0]==200 && preview[1]['data']['schema_version']=='2','preview upgrade')
insist(database==before,'preview persisted')
answer=invoke(s,'POST',path+'/edits',{},body);insist(answer[0]==200,answer.inspect);current=answer[1]['data'];after=database
insist(invoke(s,'POST',path+'/edits',{},body)==answer && database==after,'receipt replay changed')
insist(invoke(s,'POST',path+'/edits',{},body.merge('edits'=>[add('a',{'kind'=>'model'},'changed')]))[0]==409,'changed replay')
insist(invoke(s,'POST',path+'/edits',{},body.merge('command_id'=>SecureRandom.uuid))[0]==409,'stale CAS')
baseline=database(true)
bad=body.merge('command_id'=>SecureRandom.uuid,'expected_revision'=>current['draft_revision'],'edits'=>[add('b',{'kind'=>'model'}),{'kind'=>'remove_assumption','assumption_id'=>SecureRandom.uuid}])
rejected=invoke(s,'POST',path+'/edits',{},bad)
insist(rejected[0]==409 && database(true)==baseline,'late batch rollback')
insist(invoke(s,'POST',path+'/edits',{},bad)==rejected,'rejected replay')
insist(invoke(s,'GET',path+'/revisions/'+old['model_revision_id'])[1]['data']==old,'legacy revision changed')
pin=committed(s,current);package=invoke(s,'GET',path+'/export',{'revision'=>pin['model_revision_id']})[1]['data']
insist(package['revisions'].map { |p| p['schema_version'] }==%w[1 2],'mixed ancestry')
puts 'AE_RESULT='+JSON.generate({'legacy'=>old,'package'=>package})
""")
    assert result['package']['schema_version'] == '2'
    assert 'assumptions' not in result['legacy']


def test_removal_requires_explicit_assumption_removal_and_rolls_back_native_writes(harness):
    result = native(harness, BOOT + HELPERS + """
example=invoke(s,'POST','/models',{}, {'command_id'=>SecureRandom.uuid,'expected_revision'=>nil,'study_id'=>s['study_id'],'name'=>'Example','template'=>'two_component_example'})[1]['data'];m=example;path='/models/'+m['model_id'];iid=m['instances'][0]['instance_id']
a=edit(s,path,m,[add('a',{'kind'=>'instance','instance_id'=>iid})]);insist(a[0]==200,a.inspect);m=a[1]['data'];aid=a[1]['created_ids']['a']['assumption_id'];baseline=database(true)
disconnects=m['connections'].map { |c| {'kind'=>'disconnect','connection_id'=>c['connection_id']} };remove={'kind'=>'remove_instance','instance_id'=>iid}
bad=edit(s,path,m,disconnects+[remove]);insist(bad[0]==409 && database(true)==baseline,'dangling owner')
ModelingIdentity.prepend(Module.new do
  def update!(attributes)
    raise ModelingContract::Failure.new(422,'invalid_model') if attributes.dig(:metadata,'assumptions')&.any? { |a| a['statement']=='fail after native writes' }
    super
  end
end)
bad=edit(s,path,m,[{'kind'=>'rename_model','name'=>'Must rollback'},{'kind'=>'update_assumption','assumption_id'=>aid,'statement'=>'fail after native writes','evidence_links'=>[]}]);insist(bad[0]==422 && database(true)==baseline,'native partial persistence')
good=edit(s,path,m,[{'kind'=>'remove_assumption','assumption_id'=>aid}]+disconnects+[remove]);insist(good[0]==200,good.inspect)
insist(good[1]['data']['assumptions']==[] && !good[1]['data']['instances'].any? { |i| i['instance_id']==iid },'explicit deletion failed')
puts 'AE_RESULT='+JSON.generate({'atomic'=>true})
""")
    assert result['atomic']


def test_closed_shape_ids_owners_duplicates_and_union_limit(harness):
    result = native(harness, BOOT + HELPERS + """
base=database(true);evidence=SecureRandom.uuid;link={'evidence_version_id'=>evidence,'relation'=>'supports'}
invalid=[add('a',{'kind'=>'model'},'   '),add('a',{'kind'=>'model'},'ok',[link,link]),add('a',{'kind'=>'model'},'ok',[link.merge('relation'=>'proves')]),add('a',{'kind'=>'instance','instance_id'=>m['root_instance_id']}),add('a',{'kind'=>'instance','instance_temp_key'=>'missing'}),add('a',{'kind'=>'instance','instance_id'=>SecureRandom.uuid}),add('a',{'kind'=>'model'},'x'*4097),add('a',{'kind'=>'model'},'ok',[link.merge('evidence_version_id'=>evidence+"\\n")])]
invalid.each { |e| answer=edit(s,path,m,[e]);insist([400,409,422].include?(answer[0]),answer.inspect);insist(database(true)==base,'invalid edit changed state') }
valid=edit(s,path,m,[add('a',{'kind'=>'model'},'ok',[link,link.merge('relation'=>'challenges')])]);insist(valid[0]==200,valid.inspect);current=valid[1]['data']
duplicate=Marshal.load(Marshal.dump(current));duplicate['assumptions'] << duplicate['assumptions'][0].merge('statement'=>'different')
begin ModelingContract.new(s).validate_model(duplicate);raise 'duplicate id admitted';rescue ModelingContract::Failure;end
large=Marshal.load(Marshal.dump(current));large['assumptions']=1001.times.map { |n| {'assumption_id'=>SecureRandom.uuid,'owner'=>{'kind'=>'model'},'statement'=>'x','evidence_links'=>[]} }
begin ModelingContract.new(s).validate_model(large);raise 'assumption limit admitted';rescue ModelingContract::Failure;end
large['assumptions']=17.times.map { |n| {'assumption_id'=>SecureRandom.uuid,'owner'=>{'kind'=>'model'},'statement'=>'x','evidence_links'=>64.times.map { {'evidence_version_id'=>SecureRandom.uuid,'relation'=>'context'} }} }
begin ModelingContract.new(s).validate_model(large);raise 'union limit admitted';rescue ModelingContract::Failure;end
puts 'AE_RESULT='+JSON.generate({'invalid_cases'=>invalid.size+3})
""")
    assert result['invalid_cases'] == 11


def test_unknown_opaque_citations_and_exact_package_roundtrip(harness):
    package = native(harness, BOOT + HELPERS + """
links=%w[supports challenges context].map { |r| {'evidence_version_id'=>'12345678-1234-1234-1234-123456789abc','relation'=>r} }
answer=edit(s,path,m,[add('a',{'kind'=>'model'},'Opaque external citation',links)]);insist(answer[0]==200,answer.inspect)
pin=committed(s,answer[1]['data']);package=invoke(s,'GET',path+'/export',{'revision'=>pin['model_revision_id']})[1]['data']
puts 'AE_RESULT='+JSON.generate(package)
""")
    encoded = base64.b64encode(json.dumps(package).encode()).decode()
    result = native(harness, BOOT + """
package=JSON.parse(Base64.strict_decode64('""" + encoded + """'))
request={'command_id'=>SecureRandom.uuid,'expected_revision'=>nil,'study_id'=>s['study_id'],'package'=>package,'preserve_public_ids'=>true}
answer=invoke(s,'POST','/imports',{},request);insist(answer[0]==201,answer.inspect)
copy=invoke(s,'GET','/models/'+package['model_id']+'/export',{'revision'=>package['model_revision_id']})[1]['data']
insist(copy==package,'package not exact');insist(answer[1]['data']['assumptions']==package['revisions'].last['assumptions'],'opaque refs rewritten')
puts 'AE_RESULT='+JSON.generate(copy)
""")
    assert result == package


def test_private3_static_preparation_retains_exact_bytes_and_native_program(harness):
    raw, setup = public_fixture()
    result = native(harness, setup + """
before=NativeProgram.generate(m,cfg)
old=m;state=c.route('GET',path,{},nil)[1]['data'];ev=SecureRandom.uuid
change={'schema_version'=>'2','command_id'=>SecureRandom.uuid,'expected_revision'=>state['draft_revision'],'edits'=>[{'kind'=>'add_assumption','temp_key'=>'a','owner'=>{'kind'=>'model'},'statement'=>'Context only','evidence_links'=>[{'evidence_version_id'=>ev,'relation'=>'supports'}]}]}
answer=c.route('POST',path+'/edits',{},change);raise answer.inspect unless answer[0]==200
m=c.route('POST',path+'/commits',{}, {'command_id'=>SecureRandom.uuid,'expected_revision'=>answer[1]['data']['draft_revision']})[1]['data']
cfg['schema_version']='3';cfg['model_revision_id']=m['model_revision_id']
cfg['evidence_snapshots']=[{'evidence_id'=>SecureRandom.uuid,'evidence_version_id'=>ev,'study_id'=>scope['study_id'],'evidence_schema_version'=>'3','resource_scope'=>{'scope_version'=>'1','kind'=>'study','study_id'=>scope['study_id']},'kind'=>'note','content'=>'Exact frozen evidence','source_refs'=>[],'title'=>'Retained report','parent_evidence_version_id'=>SecureRandom.uuid,'recorded_context'=>{'schema_version'=>'1','label'=>'Original study label','resource_labels'=>[]}}]
cfg['digest']=ModelingContract.digest(cfg.except('digest'))
candidate=cfg.except('configuration_id','configuration_revision_id','parent_revision_id','digest')
proof=c.route('POST',path+'/configuration-compatibility',{}, {'model_revision_id'=>m['model_revision_id'],'configuration_candidate'=>candidate})[1]['data']
after=NativeProgram.generate(m,cfg);raise 'numerical program changed with assumptions' unless before==after
artifact=c.route('POST',path+'/prepare-execution',{},body.merge('command_id'=>SecureRandom.uuid,'model_revision_id'=>m['model_revision_id'],'configuration_snapshot'=>cfg,'configuration_digest'=>cfg['digest']))[1]['data'];raise artifact.inspect unless artifact['schema_version']=='2'
stored=ModelingRevision.find_by!(public_id:artifact['preparation_id']).payload['bytes']
files=artifact['files'].to_h { |f| [f['path'],stored.fetch(f['file_id'])['bytes']] }
raise 'candidate executed' if File.exist?('/tmp/erb-canary')
puts 'AE_RESULT='+JSON.generate({'proof'=>proof,'artifact'=>artifact,'files'=>files,'configuration'=>cfg,'model'=>m,'capabilities'=>c.route('GET','/capabilities',{},nil)[1]['data']})
""")
    artifact = result['artifact']
    assert result['proof']['compatible'] and result['proof']['schema_version'] == '2'
    assert artifact['schema_version'] == artifact['model_package_manifest']['schema_version'] == '2'
    assert artifact['model_digest'] == result['model']['digest']
    assert artifact['configuration_digest'] == result['configuration']['digest']
    files = {p: base64.b64decode(v) for p,v in result['files'].items()}
    for entry in artifact['files']:
        assert len(files[entry['path']]) == entry['size']
        assert hashlib.sha256(files[entry['path']]).hexdigest() == entry['sha256']
    assert files['sources/' + hashlib.sha256(raw).hexdigest() + '.py'] == raw
    assert files['provenance/patched/app/services/modeling_contract.rb'] == (harness[1] / 'modeling_contract.rb').read_bytes()
    for name in PATCHES:
        assert files['provenance/patches/' + name] == (ROOT / 'upstream/whatsopt-patches' / name).read_bytes()
    assert artifact['generator_identity']['name'] == 'WhatsOpt::OpenmdaoGenerator'
    caps = result['capabilities']
    assert '1.2' in caps['contract_versions'] and '2' in caps['schema_versions']
    assert caps['execution_versions']['artifact_versions'] == ['2'] and '4' in caps['execution_versions']['bundle_versions']
    assert any(x['id']=='model_assumptions' and x['version']=='1' and x['supported'] for x in caps['capabilities'])
    assert any(x['id']=='resolved_configuration' and x['version']=='3' and x['supported'] for x in caps['capabilities'])


def test_private3_rejects_unprojected_authority_duplicate_evidence_and_digest(harness):
    _, setup = public_fixture()
    result = native(harness, setup + """
cfg['schema_version']='3';cfg['digest']=ModelingContract.digest(cfg.except('digest'))
candidate=cfg.except('configuration_id','configuration_revision_id','parent_revision_id','digest')
rejected=[]
ev={'evidence_id'=>SecureRandom.uuid,'evidence_version_id'=>SecureRandom.uuid,'study_id'=>scope['study_id'],'evidence_schema_version'=>'3','resource_scope'=>{'scope_version'=>'1','kind'=>'study','study_id'=>scope['study_id']},'kind'=>'note','content'=>'Frozen','source_refs'=>[],'title'=>'Title','parent_evidence_version_id'=>nil,'recorded_context'=>{'schema_version'=>'1','label'=>'Study','resource_labels'=>[]}}
[[ev,ev.merge('title'=>'Different same version')],[ev.merge('study_id'=>SecureRandom.uuid)]].each do |records|
  begin c.compatible(m,candidate.merge('evidence_snapshots'=>records));rejected << false;rescue ModelingContract::Failure;rejected << true;end
end
[{'assumptions'=>[]},{'general_context_evidence_version_ids'=>[]},{'context_source'=>{}},{'derivation'=>nil},{'required_capabilities'=>['configuration_assumptions/1']}].each do |extra|
  begin c.route('POST',path+'/configuration-compatibility',{}, {'model_revision_id'=>m['model_revision_id'],'configuration_candidate'=>candidate.merge(extra)});rejected << false;rescue ModelingContract::Failure;rejected << true;end
end
begin c.compatible(m,candidate.merge('schema_version'=>'4'));rejected << false;rescue ModelingContract::Failure;rejected << true;end
answer=c.route('POST',path+'/prepare-execution',{},body.merge('command_id'=>SecureRandom.uuid,'configuration_digest'=>'0'*64))
rejected << (answer[0]==422)
raise 'unexpected preparations' unless ModelingRevision.where(kind:'preparation').count==0
puts 'AE_RESULT='+JSON.generate({'rejected'=>rejected})
""")
    assert result['rejected'] == [True] * 9


def test_rehashed_import_rejects_duplicate_ids_dangling_owners_and_wrong_root(harness):
    result = native(harness, BOOT + HELPERS + """
answer=edit(s,path,m,[add('a',{'kind'=>'model'})]);pin=committed(s,answer[1]['data']);package=invoke(s,'GET',path+'/export',{'revision'=>pin['model_revision_id']})[1]['data']
# Remove only this synthetic fixture's model identity to reach package semantics;
# the test rolls that transaction back after every attempt, including sequences.
rejected=[]
3.times do |index|
  candidate=Marshal.load(Marshal.dump(package));p=candidate['revisions'].last
  case index
  when 0 then p['assumptions'] << p['assumptions'][0].merge('statement'=>'different duplicate')
  when 1 then p['assumptions'][0]['owner']={'kind'=>'instance','instance_id'=>SecureRandom.uuid}
  when 2 then candidate['schema_version']='1'
  end
  p['digest']=ModelingContract.digest(p.except('digest'));candidate['files']=ModelingContract.new(s).package_files(candidate['revisions']);candidate['digest']=ModelingContract.digest(candidate.except('digest'))
  ModelingIdentity.transaction(requires_new:true) do
    ModelingIdentity.where(public_id:m['model_id']).delete_all
    baseline=database(true)
    request={'command_id'=>SecureRandom.uuid,'expected_revision'=>nil,'study_id'=>s['study_id'],'package'=>candidate,'preserve_public_ids'=>true}
    result=invoke(s,'POST','/imports',{},request);rejected << ([400,409,422].include?(result[0]) && database(true)==baseline)
    raise ActiveRecord::Rollback
  end
end
puts 'AE_RESULT='+JSON.generate({'rejected'=>rejected})
""")
    assert result['rejected'] == [True] * 3


@pytest.mark.parametrize('name', [
    'test_direct_native_reference_matches_public_materializer',
    'test_real_generator_and_invoked_template_sentinels_fail_prepare',
    'test_fanout_distinct_symbols_units_and_disconnected_repeat',
    'test_save_validate_export_import_prepare_canary_stays_data',
])
def test_existing_native_origin_and_canary_regressions(harness, monkeypatch, name):
    import test_native_generation as existing
    monkeypatch.setattr(existing, 'native', lambda code: native(harness, code.replace('NATIVE_RESULT=', 'AE_RESULT=')))
    getattr(existing, name)()


@pytest.mark.parametrize('name', [
    'test_cursor_query_and_authorization_fail_closed_without_effect',
    'test_concurrent_command_is_one_effect_and_receipt',
    'test_actual_http_list_envelope_auth_query_and_limits',
])
def test_existing_authorization_receipt_http_regressions(harness, monkeypatch, name):
    import test_ui_discovery as existing
    monkeypatch.setattr(existing, 'native', lambda unused, code: native(harness, BOOT + code.replace('DISCOVERY_RESULT=', 'AE_RESULT=')))
    getattr(existing, name)(harness)


def test_docker_applies_each_patch_once_in_order_and_patches_are_the_reviewed_bytes():
    import re
    docker = (ROOT / 'deployment/modeling.Dockerfile').read_text()
    for name in ('native', 'discovery', 'assumptions', 'units'):
        assert docker.count('RUN patch --batch --fuzz=0 -p1 < /tmp/' + name + '.patch\n') == 1
    assert (docker.index('COPY replay /native/') < docker.index('/tmp/native.patch\n') < docker.index('/tmp/discovery.patch\n')
            < docker.index('/tmp/assumptions.patch\n') < docker.index('/tmp/units.patch\n') < docker.index('COPY modeling_contract.rb'))
    # The ordered patches are exactly the bytes the modeling provenance record lists.
    record = (ROOT / 'modeling/provenance.md').read_text()
    listed = dict(re.findall(r'^\| `(\d{3}-[a-z-]+\.patch)` \|.*\| `([0-9a-f]{64})` \|$', record, re.M))
    actual = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT / 'upstream/whatsopt-patches').glob('*.patch')}
    assert listed == actual and len(actual) == 9
    pins = json.loads((ROOT / 'deployment/pins.json').read_text())
    assert pins['native_patch_sha256'] == actual['050-native-generation.patch']


def test_actual_build_staging_and_zero_fuzz_failure(harness, monkeypatch):
    import modeling_runtime
    scope, adapter, _ = harness
    stage = fixture.scoped_path(scope, 'artifacts/build-inputs'); stage.mkdir()
    modeling_runtime.stage_native_inputs(stage)
    assert (stage / 'modeling_contract.rb').read_bytes() == (adapter / 'modeling_contract.rb').read_bytes()
    # Only the native hunk of 070 is applied to the image; its adapter hunk is part of the
    # cumulative adapter above.
    assumptions = (ROOT / 'upstream/whatsopt-patches/070-assumptions-evidence.patch').read_text()
    assert (stage / 'assumptions.patch').read_text() == assumptions[assumptions.index('--- a/app/services/native_materializer.rb\n'):]
    assert (stage / 'replay/app/services/modeling_contract.rb').is_file()
    for name in PATCHES:
        assert (stage / 'provenance-inputs/patches' / name).read_bytes() == (ROOT / 'upstream/whatsopt-patches' / name).read_bytes()
    repository = fixture.scoped_path(scope, 'artifacts/bad-repository')
    patches = repository / 'upstream/whatsopt-patches'; patches.mkdir(parents=True)
    for name in PATCHES:
        data = (ROOT / 'upstream/whatsopt-patches' / name).read_text()
        if name == PATCHES[-1]:
            data = data.replace('-  CAPABILITIES =', '-  UNEXPECTED_CAPABILITIES =', 1)
        (patches / name).write_text(data)
    bad_stage = fixture.scoped_path(scope, 'artifacts/bad-stage'); bad_stage.mkdir()
    monkeypatch.setattr(modeling_runtime, 'REPO', repository)
    with pytest.raises(ValueError, match='patch chain failed: 070'):
        modeling_runtime.stage_modeling_contract(bad_stage)
    assert not (bad_stage / 'modeling_contract.rb').exists()


def test_replayed_sources_are_upstream_plus_the_ordered_patches(harness, monkeypatch):
    import shutil
    import modeling_runtime
    scope, _, _ = harness
    stage = fixture.scoped_path(scope, 'artifacts/replay'); stage.mkdir()
    upstream = modeling_runtime.upstream_archive().getvalue()
    replay = modeling_runtime.stage_replayed_sources(stage, upstream)
    expected = sorted(path for _, path in modeling_runtime.REPLAYED_SOURCES)
    assert sorted(str(p.relative_to(replay)) for p in replay.rglob('*') if p.is_file()) == expected
    # Rails loads a migration by the class its file name names; every replayed migration's
    # version is one the build removes from the source image first.
    migration = replay / 'db/migrate/20261008160000_add_hyprn_mvp_study_boundary.rb'
    assert 'class AddHyprnMvpStudyBoundary <' in migration.read_text()
    assert {p.split('/')[-1].split('_')[0] for p in expected if p.startswith('db/migrate/')} == set(modeling_runtime.REPLAYED_MIGRATION_VERSIONS)
    # The native patch applies to the replayed generator and adapter with zero fuzz.
    work = stage / 'native'
    sections = modeling_runtime.patch_sections((ROOT / 'upstream/whatsopt-patches/050-native-generation.patch').read_text())
    for path in ('app/lib/whats_opt/openmdao_generator.rb', 'app/services/modeling_contract.rb'):
        (work / path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(replay / path, work / path)
        section = [text for _, new, text in sections if new == 'b/' + path]
        applied = subprocess.run(['patch', '--batch', '--fuzz=0', '-p1'], input=section[0], cwd=work, text=True, capture_output=True)
        assert applied.returncode == 0, applied.stdout + applied.stderr
        assert 'fuzz' not in applied.stdout.lower() and 'offset' not in applied.stdout.lower()
    # A replayed patch whose context no longer matches the upstream bytes fails closed.
    repository = fixture.scoped_path(scope, 'artifacts/bad-replay-repository')
    patches = repository / 'upstream/whatsopt-patches'; patches.mkdir(parents=True)
    for source in (ROOT / 'upstream/whatsopt-patches').glob('*.patch'):
        data = source.read_text()
        if source.name == '030-configuration.patch':
            start = data.index('--- a/app/lib/whats_opt/python_utils.rb\n')
            context = data.index('\n ', data.index('@@', start)) + 2
            data = data[:context] + 'X' + data[context:]
        (patches / source.name).write_text(data)
    bad = fixture.scoped_path(scope, 'artifacts/bad-replay'); bad.mkdir()
    monkeypatch.setattr(modeling_runtime, 'REPO', repository)
    with pytest.raises(ValueError, match='Replayed source patch failed: 030'):
        modeling_runtime.stage_replayed_sources(bad, upstream)
