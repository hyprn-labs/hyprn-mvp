"""Actual private Rails/native static path in fresh confined tmpfs stores."""
from hyprn_mvp_app.contracts import authored_schema
import base64
import hashlib
import json
from pathlib import Path
import sys
import time

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'deployment'))
sys.path.insert(0, str(ROOT / 'deployment/tests'))
sys.path.insert(0, str(ROOT / 'modeling/tests'))
from test_native_generation import public_fixture
import scoped_fixture as fixture


@pytest.fixture(scope='module')
def harness():
    from checks import PROJECTION_SCOPE
    fixture.validate_scope(PROJECTION_SCOPE)
    from units_model_fixture import stage_sources
    scope,stage,image=stage_sources()
    return scope,stage/'modeling_contract.rb',stage/'modeling.schema.json',image


def native(harness, code):
    fixture.validate_scope(harness[0])
    from units_model_fixture import run_ruby
    return json.loads(run_ruby(code,(harness[0],harness[1].parent,harness[3])).split('PROJECTION_RESULT=')[-1])


def test_real_private_projection_preparation_and_legacy(harness):
    _, setup = public_fixture()
    result = native(harness, setup + """
legacy=c.route('POST',path+'/prepare-execution',{},body)[1]['data']
cfg['schema_version']='2';cfg['inputs'][0]['value']=150;cfg['inputs'][0]['units']='cm'
cfg['digest']=ModelingContract.digest(cfg.except('digest'))
candidate=cfg.except('digest','configuration_id','configuration_revision_id','parent_revision_id')
proof=c.route('POST',path+'/configuration-compatibility',{}, {'model_revision_id'=>m['model_revision_id'],'configuration_candidate'=>candidate})[1]['data']
prepared=c.route('POST',path+'/prepare-execution',{},body.merge('command_id'=>SecureRandom.uuid,'configuration_digest'=>cfg['digest']))[1]['data']
stored=ModelingRevision.find_by(public_id:prepared['preparation_id']).payload['bytes']
files=prepared['files'].to_h { |f| [f['path'],stored.fetch(f['file_id'])['bytes']] }
raise 'Candidate executed' if File.exist?('/tmp/erb-canary')
puts 'PROJECTION_RESULT='+JSON.generate({'proof'=>proof,'candidate'=>candidate,'configuration'=>cfg,'model'=>m,'prepared'=>prepared,'files'=>files,'legacy'=>legacy,'catalog'=>ModelingContract::UNITS,'capabilities'=>c.route('GET','/capabilities',{},nil)[1]['data']})
""")
    from hyprn_mvp_app.store import digest
    from hyprn_mvp_app.modeling import validate
    proof = result['proof']; projected = result['configuration']; artifact = result['prepared']
    validate('CompatibilityResult2', proof)
    assert proof['schema_version'] == '2' and proof['compatible']
    assert proof['candidate_digest'] == digest(result['candidate'])
    conversion = proof['input_interpretations'][0]['conversion']
    assert conversion == dict(policy='openmdao-linear-catalog-1', catalog_digest=digest(result['catalog']),
        source_units='cm', destination_units='m', factor=.01, destination_value=1.5)
    patch = (ROOT / 'upstream/whatsopt-patches/040-modeling-contract.patch').read_text()
    catalog_section = patch.split('+++ b/config/modeling.units.json\n', 1)[1].split('\n--- ', 1)[0]
    catalog = json.loads('\n'.join(line[1:] for line in catalog_section.splitlines() if line.startswith('+')))
    assert all(unit in result['catalog']['supported_units'] for unit in catalog['supported_units'])
    assert len(result['catalog']['supported_units']) == 29
    assert catalog['engine'] == 'OpenMDAO' and catalog['version'] == '3.45.1'
    assert artifact['schema_version'] == result['legacy']['schema_version'] == '3'
    assert artifact['configuration_digest'] == projected['digest']
    assert artifact['entrypoint']['protocol'] == 'hyprn_mvp.openmdao.program/1'
    assert artifact['generator_identity']['name'] == 'WhatsOpt::OpenmdaoGenerator'
    assert artifact['result_protocol_version'] == '2'
    assert any(c['id']=='resolved_configuration' and c['version']=='3' and c['supported'] for c in result['capabilities']['capabilities'])
    files = {p: base64.b64decode(raw) for p, raw in result['files'].items()}
    from test_native_program_contract import check_program
    check_program(artifact, files, artifact['prepared_digest'])
    provenance = json.loads(files['provenance/generator.json'])
    assert provenance['adapter_source'] in provenance['patched_files']
    assert files['provenance/patched/app/services/modeling_contract.rb'] == harness[1].read_bytes()
    assert files['provenance/patched/app/services/native_materializer.rb'] == (harness[1].parent / 'app/services/native_materializer.rb').read_bytes()
    for name in ('040-modeling-contract.patch', '050-native-generation.patch', '060-ui-discovery.patch'):
        assert files['provenance/patches/' + name] == (ROOT / 'upstream/whatsopt-patches' / name).read_bytes()
    # Construct a full retained app record with result authority, then prove the
    # actual private snapshot equals the production app projection byte-for-byte.
    import copy
    from test_reuse_contract import binding
    from hyprn_mvp_app.scientific_configuration import project_scientific_configuration
    full = copy.deepcopy(projected)
    full.update(context_source=dict(kind='current_study', expected_study_revision='fixture-1'), derivation=None)
    full['inputs'][0]['result_binding'] = binding()
    full['required_capabilities'].append('result_linked_inputs/1')
    full['digest'] = digest({k: v for k, v in full.items() if k != 'digest'})
    assert project_scientific_configuration(full) == projected
    assert full['digest'] != artifact['configuration_digest']
    from hyprn_mvp_app.execution import check_digest, executable_digest
    check_digest(artifact, 'prepared_digest')
    assert artifact['executable_content_digest'] == executable_digest(artifact)


def test_private_rejects_authority_units_and_wrong_digest(harness):
    _, setup = public_fixture()
    result = native(harness, setup + """
cfg['schema_version']='2';cfg['digest']=ModelingContract.digest(cfg.except('digest'))
candidate=cfg.except('digest','configuration_id','configuration_revision_id','parent_revision_id')
rejections=[]
[{'derivation'=>{}},{'context_source'=>{}},{'process_uuid'=>SecureRandom.uuid},{'required_capabilities'=>['result_linked_inputs/1']}].each do |extra|
  begin
    c.route('POST',path+'/configuration-compatibility',{}, {'model_revision_id'=>m['model_revision_id'],'configuration_candidate'=>candidate.merge(extra)})
    rejections << false
  rescue ModelingContract::Failure
    rejections << true
  end
end
bad=Marshal.load(Marshal.dump(candidate));bad['inputs'][0]['result_binding']={}
begin
  c.route('POST',path+'/configuration-compatibility',{}, {'model_revision_id'=>m['model_revision_id'],'configuration_candidate'=>bad});rejections << false
rescue ModelingContract::Failure
  rejections << true
end
['kg','degC','not-a-unit'].each do |unit|
  bad=Marshal.load(Marshal.dump(candidate));bad['inputs'][0]['units']=unit
  proof=c.route('POST',path+'/configuration-compatibility',{}, {'model_revision_id'=>m['model_revision_id'],'configuration_candidate'=>bad})[1]['data']
  rejections << !proof['compatible']
end
begin
  rejected=c.route('POST',path+'/prepare-execution',{},body.merge('command_id'=>SecureRandom.uuid,'configuration_digest'=>'0'*64));rejections << (rejected[0]==422)
rescue ModelingContract::Failure
  rejections << true
end
puts 'PROJECTION_RESULT='+JSON.generate({'rejections'=>rejections,'artifacts'=>ModelingRevision.where(kind:'preparation').count,'affine'=>c.compatible_units?('degC','K')})
""")
    assert result == dict(rejections=[True]*9, artifacts=0, affine=False)


def test_staging_fails_closed_on_changed_patch_hunk(harness, monkeypatch):
    import modeling_runtime
    scope = harness[0]
    root = fixture.scoped_path(scope, 'artifacts/bad-repository'); root.mkdir()
    patches = root / 'upstream/whatsopt-patches'; patches.mkdir(parents=True)
    for name in ('040-modeling-contract.patch', '050-native-generation.patch', '060-ui-discovery.patch'):
        data = (ROOT / 'upstream/whatsopt-patches' / name).read_text()
        if name == '060-ui-discovery.patch':
            data = data.replace('-  CAPABILITIES =', '-  UNEXPECTED_CAPABILITIES =', 1)
        (patches / name).write_text(data)
    stage = fixture.scoped_path(scope, 'artifacts/bad-stage'); stage.mkdir()
    monkeypatch.setattr(modeling_runtime, 'REPO', root)
    with pytest.raises(ValueError, match='patch chain failed'):
        modeling_runtime.stage_modeling_contract(stage)
    assert not (stage / 'modeling_contract.rb').exists()


def test_private_schema_copy_and_legacy_result_preservation(harness):
    from test_reuse_contract import DEFS
    patch = (ROOT / 'upstream/whatsopt-patches/040-modeling-contract.patch').read_text()
    section = patch.split('+++ b/config/modeling.schema.json\n', 1)[1].split('\n--- ', 1)[0]
    embedded = json.loads('\n'.join(line[1:] for line in section.splitlines() if line.startswith('+')))
    # Production stages the authored model schema beside the cumulative adapter;
    # the original patch schema remains a historical baseline.
    assert harness[2].read_bytes() == (ROOT / 'contracts/schemas/model.schema.json').read_bytes()
    assert DEFS == authored_schema()['$defs']
    # The tracked 040 patch is the historical baseline of the legacy concrete shapes: the
    # current read unions were split from these definitions without changing them.
    legacy = embedded['$defs']
    assert DEFS['EvidenceSnapshotLegacy'] == legacy['EvidenceSnapshot']
    for name in ('ConfigurationCandidate1', 'ConfigurationRevision1', 'ExecutionBundle2',
                 'PreparedModelArtifact', 'ProgramBindings', 'ProgramSourceMap'):
        expected = json.loads(json.dumps(legacy[name]))
        if name in ('ConfigurationCandidate1','ConfigurationRevision1'):
            assert expected['properties']['evidence_snapshots']['items'] == {'$ref': '#/$defs/EvidenceSnapshot'}
            expected['properties']['evidence_snapshots']['items']['$ref'] = '#/$defs/EvidenceSnapshotLegacy'
        assert DEFS[name] == expected
    assert DEFS['CompatibilityResult1'] == legacy['CompatibilityResult1']


def test_quantity_closed_native_reader_legacy_units_and_generated_parity(harness):
    _,setup=public_fixture()
    result=native(harness,setup+"""
cfg['schema_version']='3';cfg['digest']=ModelingContract.digest(cfg.except('digest'))
before=NativeProgram.generate(m,cfg)
described=Marshal.load(Marshal.dump(m));described['schema_version']='4'
described['required_capabilities'] << 'quantity_definitions/1'
d=described['definitions'][0]
d['quantity_definitions']=[{'port_id'=>d['ports'][0]['port_id'],'statement'=>'Specific energy, descriptive only'}]
described['digest']=ModelingContract.digest(described.except('digest'))
c.validate_model(described)
after=NativeProgram.generate(described,cfg)
raise 'Generated program changed' unless before==after
raise 'Source changed' unless described['source_files']==m['source_files']
raise 'Legacy declaration changed' unless described['ports']==m['ports']
rejections=[]
['extra','missing','blank','blank_unicode','blank_control','duplicate','foreign','mixed'].each do |kind|
  bad=Marshal.load(Marshal.dump(described));defn=bad['definitions'][0]
  case kind
  when 'extra' then defn['unknown']=true
  when 'missing' then defn.delete('name')
  when 'blank' then defn['quantity_definitions'][0]['statement']='   '
  when 'blank_unicode' then defn['quantity_definitions'][0]['statement']=[160].pack('U')
  when 'blank_control' then defn['quantity_definitions'][0]['statement']=[28].pack('U')
  when 'duplicate' then defn['quantity_definitions'] << defn['quantity_definitions'][0].merge('statement'=>'Different')
  when 'foreign' then defn['quantity_definitions'][0]['port_id']=SecureRandom.uuid
  when 'mixed' then defn['ports'][0]['units']={'kind'=>'dimensionless'}
  end
  bad['ports']=bad['definitions'].flat_map { |d| d['ports'] }
  begin;c.validate_model(bad);rejections << false
  rescue ModelingContract::Failure;rejections << true;end
end
candidate=cfg.except('digest','configuration_id','configuration_revision_id','parent_revision_id')
proof=c.compatible(described,candidate)
legacy3=Marshal.load(Marshal.dump(m));legacy3['schema_version']='3';legacy3['required_capabilities'] << 'unit_declarations/1'
raise 'Changed historical Model3 catalog identity' unless c.compatible(legacy3,candidate)['input_interpretations'][0]['conversion']['catalog_digest']==ModelingContract::UNITS.fetch('catalog_digest')
puts 'PROJECTION_RESULT='+JSON.generate({'rejections'=>rejections,'before'=>before.transform_values { |v| Digest::SHA256.hexdigest(v) },'after'=>after.transform_values { |v| Digest::SHA256.hexdigest(v) },'model'=>described,'proof'=>proof,'catalog'=>ModelingContract::UNITS})
""")
    assert result['rejections']==[True]*8
    assert result['before']==result['after'] and result['before']
    from hyprn_mvp_app.units import resolved_model_units
    from hyprn_mvp_app.store import digest
    assert set(resolved_model_units(result['model']).values())=={'m'}
    assert result['proof']['input_interpretations'][0]['conversion']['catalog_digest']==digest(result['catalog'])


def test_quantity_app_reader_exact_version_membership_and_unresolved(harness):
    # A data-only model fixture built from the same real adapter, never a mock source.
    _,setup=public_fixture()
    result=native(harness,setup+"""
m['schema_version']='4';m['required_capabilities'] += ['quantity_definitions/1','unit_declarations/1']
d=Marshal.load(Marshal.dump(m['definitions'][0]));d['definition_version_id']=SecureRandom.uuid
d['quantity_definitions']=[{'port_id'=>d['ports'][0]['port_id'],'statement'=>'Exact retained occurrence'}]
d['ports'].each { |p| p['definition_version_id']=d['definition_version_id'];p['units']={'kind'=>'unspecified'} }
m['definitions'] << d;m['ports']=m['definitions'].flat_map { |v| v['ports'] }
m['digest']=ModelingContract.digest(m.except('digest'));c.validate_model(m)
puts 'PROJECTION_RESULT='+JSON.generate(m)
""")
    import copy
    from hyprn_mvp_app.units import resolved_model_units,unit_readiness
    from hyprn_mvp_app.store import DomainError
    assert not unit_readiness(result)  # Unused typed unresolved history is readable.
    assert set(resolved_model_units(result).values())=={'m'}
    changed=copy.deepcopy(result);changed['instances'][0]['definition_version_id']=changed['definitions'][-1]['definition_version_id']
    assert len(unit_readiness(changed))==2
    with pytest.raises(DomainError):resolved_model_units(changed)
    mixed=copy.deepcopy(changed)
    for port in mixed['definitions'][-1]['ports']:port['units']={'kind':'physical','expression':'m'}
    mixed['ports']=[p for d in mixed['definitions'] for p in d['ports']]
    resolved=resolved_model_units(mixed)
    assert len(resolved)==4 and set(resolved.values())=={'m'}
    assert len({key[1] for key in resolved})==2
    for bad in ('duplicate','foreign'):
        value=copy.deepcopy(result);q=value['definitions'][-1]['quantity_definitions']
        if bad=='duplicate':q.append(dict(q[0],statement='Different'))
        else:q[0]['port_id']=value['model_id']
        with pytest.raises(DomainError):unit_readiness(value)
