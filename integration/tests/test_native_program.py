"""Native program deployment and execution evidence; no host candidate imports."""
import hashlib
import json
from pathlib import Path

import pytest
from execution_fixtures import criteria_free_fixture, current_fixture as fixture, uid
from hyprn_mvp_app.store import digest

ROOT = Path(__file__).resolve().parents[2]


def evidence_root():
    import os
    if 'HYPRN_MVP_TEST_SCOPE_ROOT' in os.environ:
        from checks import PROJECTION_SCOPE
        return PROJECTION_SCOPE.root/'evidence'
    from execution_fixtures import scoped_evidence_root
    return scoped_evidence_root()  # Refuses outside a scope; evidence is never written elsewhere.


@pytest.fixture(scope='module',autouse=True)
def isolated_current_worker():
    import os
    if 'HYPRN_MVP_TEST_SCOPE_ROOT' not in os.environ:
        yield
        return
    from checks import PROJECTION_SCOPE as scope,NATIVE_BACKEND as backend
    import scoped_fixture as guard
    from hyprn_mvp_integration import launcher
    from hyprn_mvp_integration.calculation import NativeExecution
    if not (scope.root/'launch-worker').exists():guard.prepare_worker_fixture(scope,backend)
    else:launcher.require_attestation(root=scope.root)
    native=NativeExecution(backend=backend,root=scope.root)
    patch=pytest.MonkeyPatch()
    patch.syspath_prepend(str(ROOT))
    patch.syspath_prepend(str(ROOT/'modeling/tests'))
    patch.setattr(NativeExecution,'from_environment',classmethod(lambda cls:native))
    patch.setenv('HYPRN_MVP_NATIVE_STATIC_IMAGE',json.loads((ROOT/'deployment/pins.json').read_text())['modeling_producer']['image'])
    import native_origin_fixture as proof
    patch.setattr(proof,'ROOT',scope.root/'artifacts/native-origin')
    from contextlib import contextmanager
    @contextmanager
    def isolated_variant(producer):
        runtime=scope.root/'runtime.json';attestation=scope.root/'evidence/containment.json'
        original_runtime=runtime.read_bytes();original_attestation=attestation.read_bytes()
        try:
            guard.change_worker_fixture_identity(scope)
            yield launcher.require_attestation(root=scope.root)
        finally:
            runtime.write_bytes(original_runtime);attestation.write_bytes(original_attestation)
            launcher.require_attestation(root=scope.root)
    patch.setattr(proof,'attested_variant',isolated_variant)
    original=launcher.require_attestation
    patch.setattr(launcher,'require_attestation',lambda *a,**kw:original(*a,root=kw.pop('root',scope.root),**kw))
    yield
    patch.undo()


@pytest.fixture(scope='module', autouse=True)
def native_profile_inside_test_scope():
    """Native runs of this module use only the profile of the test's own scratch scope: a profile
    outside it (one holding retained or live records) is refused before any test reads or
    writes it, so retained records can never be relaunched or changed from here."""
    import os
    profile = os.environ.get('AIIDA_PATH')
    if profile:
        scope = os.environ.get('HYPRN_MVP_TEST_SCOPE_ROOT')
        if not scope or not Path(profile).resolve().is_relative_to(Path(scope).resolve()):
            pytest.fail('Native profile outside the test scratch scope; refusing to run against it')
    yield


@pytest.mark.integration
def test_current_worker_is_bound_to_native_loader_and_fresh_containment():
    from hyprn_mvp_integration.launcher import require_attestation
    evidence = require_attestation()
    assert evidence['passed'] and evidence['candidate_executions'] == 0
    worker = ROOT / 'integration/src/hyprn_mvp_integration/worker.py'
    assert evidence['fingerprint']['worker_sha256'] == hashlib.sha256(worker.read_bytes()).hexdigest()
    assert b'def load_program(' in worker.read_bytes()


@pytest.mark.integration
def test_current_application_contains_native_bundle_consumer():
    import subprocess,os
    if 'HYPRN_MVP_TEST_SCOPE_ROOT' in os.environ:
        # Isolated group has no deployed app; verify the current consumer with
        # a real frozen fixture instead of inspecting a live service.
        from hyprn_mvp_app.execution import assemble_bundle,validate_retained_bundle
        from hyprn_mvp_integration.calculation import NativeExecution
        case=fixture();bundle=assemble_bundle(uid(),case['prepared'],case['files'],case['frozen'],NativeExecution.from_environment().bundle_runtime())
        validate_retained_bundle(bundle,dict(run_id=bundle['manifest']['run_id'],bundle_digest=bundle['manifest']['bundle_digest']),case['frozen'])
        return
    result = subprocess.run(['python3', 'deployment/application_runtime.py', 'check'],
                            cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['running']


def execute_case(case):
    from hyprn_mvp_app.execution import assemble_bundle
    from hyprn_mvp_integration.calculation import NativeExecution
    native = NativeExecution.from_environment()
    native.require_attestation()
    # A configuration 6 bundle always carries its (here empty) resolved result dependencies.
    dependencies = (dict(schema_version='1', sources=[], mappings=[])
                    if case['frozen']['configuration']['schema_version'] == '6' else None)
    bundle = assemble_bundle(uid(), case['prepared'], case['files'], case['frozen'], native.bundle_runtime(),
                             dependencies)
    request = dict(run_id=bundle['manifest']['run_id'], scope=case['frozen']['configuration']['study_id'],
                   command_id=uid(), payload_digest=digest({'proof':'native-program'}),
                   bundle_digest=bundle['manifest']['bundle_digest'])
    record = native.launch(bundle, request)
    assert native.retained_bundle(record['process_uuid']) == bundle
    return record, bundle


@pytest.mark.integration
def test_native_affine_conversion_rejected_without_available_output():
    from hyprn_mvp_app.execution import executable_digest
    case = fixture('affine')
    config = case['frozen']['configuration']
    config['inputs'][0]['units'] = 'degC'
    config['digest'] = digest({k:v for k,v in config.items() if k != 'digest'})
    case['prepared']['configuration_digest'] = config['digest']
    case['prepared']['executable_content_digest'] = executable_digest(case['prepared'])
    case['prepared']['prepared_digest'] = digest({k:v for k,v in case['prepared'].items() if k != 'prepared_digest'})
    record, _ = execute_case(case)
    assert record['exit_status'] == 301
    assert record['results']['execution']['message'] == 'ValueError'
    assert all(output['availability'] != 'available' for output in record['results']['outputs'])
    assert all(o['value'] is None for o in record['results']['outputs'])


@pytest.mark.integration
def test_native_kelvin_alias_preserves_explicit_value():
    record, _ = execute_case(fixture('affine'))
    assert record['exit_status'] == 0
    assert [(o['value'],o['units'],o['availability']) for o in record['results']['outputs']] == [(20,'K','available')]


def expected_mapping(case):
    model = case['frozen']['model_snapshot']
    values = {v['target']['instance_id']:2*v['value'] for v in case['frozen']['configuration']['inputs']}
    source = model['connections'][0]['source_ref']['instance_id']
    target = model['connections'][0]['target_ref']['instance_id']
    assert all(c['source_ref']['instance_id'] == source and c['target_ref']['instance_id'] == target
               for c in model['connections'])
    # Fixed independently specified fixture equation: same m output reaches both km inputs.
    return {**values, target:2*values[source]/1000}


@pytest.mark.integration
def test_native_mapping_and_direct_manual_sql_reference_agree(tmp_path):
    import base64
    import os
    from modeling.tests.test_native_generation import BOOT, native
    # The current producer generator: the case captured by the pinned producer image.
    case = criteria_free_fixture('mapping')
    model = case['frozen']['model_snapshot']
    assert case['capture']['draft_edit_invariance']
    assert len(model['definitions']) == 2 and len(model['instances']) == 3
    assert os.environ['HYPRN_MVP_NATIVE_STATIC_IMAGE'] == case['capture']['producer_image']
    encoded = base64.b64encode(json.dumps(model).encode()).decode()
    # A second native invocation with manually specified SQL rows. This never
    # calls NativeProgram, NativeMaterializer or a public-to-native mapper.
    reference = native(BOOT + """
require 'whats_opt/openmdao_generator'
require 'base64';require 'digest'
m=JSON.parse(Base64.strict_decode64('""" + encoded + """'))
scale=m['definitions'].find { |d| d['name']=='scale' }
sum=m['definitions'].find { |d| d['name']=='sum' }
scales=m['instances'].select { |i| i['definition_version_id']==scale['definition_version_id'] }.sort_by { |i| i['instance_id'] }
consumer=m['instances'].find { |i| i['definition_version_id']==sum['definition_version_id'] }
raise 'Unexpected independent fixture' unless scales.size==2 && m['connections'].size==2
a=Analysis.create!(name:'frozen_model',public:false)
a.impl.update!(package_name:'frozen_model',parallel_group:false,use_units:true)
a.impl.nonlinear_solver.update!(name:'NonlinearRunOnce',iprint:0)
a.impl.linear_solver.update!(name:'LinearRunOnce',iprint:0)
vars={};symbols={}
[ *scales.map { |i| [i,scale,{'_x'=>['in','m'],'y'=>['out','m']}] },
  [consumer,sum,{'left'=>['in','km'],'right'=>['in','km'],'y'=>['out','km']}] ].each_with_index do |(i,definition,spec),index|
  iid=i['instance_id']; name='component_'+iid.delete('-')
  d=Discipline.create!(analysis:a,name:name,position:index+1)
  authored=m['source_files'].find { |s| s['sha256']==definition['source_refs'][0] }
  d.impl.update!(python_source:Base64.strict_decode64(authored['bytes']).force_encoding('UTF-8'),support_derivatives:false)
  vars[iid]={};symbols[name]={'inputs'=>{},'outputs'=>{}}
  definition['ports'].sort_by { |p| p['port_id'] }.each do |p|
    io,units=spec.fetch(p['code_symbol'])
    v=Variable.create!(discipline:d,name:'p_'+p['port_id'].delete('-'),io_mode:io,type:'Float',shape:'1',units:units)
    vars[iid][p['code_symbol']]=v
    symbols[name][io=='in' ? 'inputs' : 'outputs'][p['code_symbol']]=v.name
  end
end
producer=m['connections'][0]['source_ref']['instance_id']
Connection.create!(from:vars.fetch(producer).fetch('y'),to:vars.fetch(consumer['instance_id']).fetch('left'))
Connection.create!(from:vars.fetch(producer).fetch('y'),to:vars.fetch(consumer['instance_id']).fetch('right'))
g=WhatsOpt::OpenmdaoGenerator.new(a,static_only:true,symbol_maps:symbols)
Dir.mkdir('/tmp/direct-native')
paths=g._generate_code('/tmp/direct-native')
files=paths.to_h { |p| ['generated/'+p.delete_prefix('/tmp/direct-native/'),Base64.strict_encode64(File.binread(p))] }
origin=g.method(:_generate_code).source_location[0]
puts 'NATIVE_RESULT='+JSON.generate({'files'=>files,'origin'=>origin,'origin_sha256'=>Digest::SHA256.file(origin).hexdigest})
""")
    assert reference['origin'] == '/native/app/lib/whats_opt/openmdao_generator.rb'
    pinned = json.loads((ROOT/'deployment/pins.json').read_text())['modeling_producer']
    assert reference['origin_sha256'] == pinned['artifact_source_hashes'][reference['origin']]
    reference_files = {p:base64.b64decode(raw, validate=True) for p,raw in reference['files'].items()}
    assert len(reference_files) == 11
    assert all(case['files'][p] == raw for p,raw in reference_files.items())
    # Retain the independently emitted files and identity, not only an equality label.
    (tmp_path/'direct-native.json').write_text(json.dumps(reference))
    actual, _ = execute_case(case)
    # Replace the executable native module bytes with the independently emitted
    # bytes just compared. Equal bytes preserve the producer's immutable manifest.
    case['files'].update(reference_files)
    direct, _ = execute_case(case)
    expected = expected_mapping(case)
    for record in (actual, direct):
        assert record['exit_status'] == 0
        assert {o['target']['instance_id']:o['value'] for o in record['results']['outputs']} == pytest.approx(expected, abs=1e-9, rel=1e-8)
    assert actual['process_uuid'] != direct['process_uuid']


@pytest.mark.integration
def test_instrumented_http_native_origin_restart_and_disabled_generator(monkeypatch):
    """Actual HTTP preparation, attested AiiDA execution and immutable restart."""
    import base64
    from aiida import orm
    from capture_native_programs import capture
    from deployment.tests.model_client import ModelClient
    import native_origin_fixture as proof
    monkeypatch.setattr(proof, 'ROOT', proof.ROOT/uid())
    marker_image = proof.build('marker')
    disabled_image = proof.build('disabled')
    records = dict(marker_image=marker_image, disabled_image=disabled_image)
    with proof.service(marker_image, 'marker', monkeypatch) as name:
        blobs = {}
        case = capture('mapping', blobs)
        case['files'] = {f['path']:base64.b64decode(blobs[f['sha256']]) for f in case['prepared']['files']}
        marked = {p:raw for p,raw in case['files'].items()
                  if p.startswith('generated/') and proof.MARKER.encode() in raw}
        assert len(marked) == 1
        marked_path, marked_raw = next(iter(marked.items()))
        assert b'def native_origin_12_3(self):' in marked_raw
        client = ModelClient(study=case['frozen']['configuration']['study_id'])
        model = case['frozen']['model_snapshot']
        proof.restart(name, marker_image)
        prepared = client.call('POST','/models/'+model['model_id']+'/prepare-execution',
            dict(command_id=uid(),model_revision_id=model['model_revision_id'],
                 configuration_snapshot=case['frozen']['configuration'],
                 configuration_digest=case['frozen']['configuration']['digest']))['data']
        assert prepared['executable_content_digest'] == case['prepared']['executable_content_digest']
        for item in prepared['files']:
            if item['path'].startswith('generated/'):
                raw = client.call('GET','/preparations/'+prepared['preparation_id']+'/files/'+item['file_id'])['data']
                assert base64.b64decode(raw['bytes']) == case['files'][item['path']]
        records['restart_preparation_id'] = prepared['preparation_id']
    # Both producer and generator are now unavailable; only retained bytes enter
    # the same production loader, using a separately attested test image identity.
    with proof.attested_variant(marker_image) as attestation:
        record, bundle = execute_case(case)
        assert record['exit_status'] == 0
        assert {o['target']['instance_id']:o['value'] for o in record['results']['outputs']} == pytest.approx(expected_mapping(case), abs=1e-9, rel=1e-8)
        raw = json.loads(orm.load_node(record['process_uuid']).outputs.retrieved.base.repository.get_object_content('result.json'))
        origins = json.loads(next(line.split(' ',1)[1] for line in raw['output'].splitlines()
                                 if line.startswith('HYPRN_MVP_NATIVE_ORIGINS_V1 ')))
        assert any(o['path']==marked_path and o['sha256']==hashlib.sha256(marked_raw).hexdigest()
                   for o in origins['group'])
        records.update(process=record, bundle_digest=bundle['manifest']['bundle_digest'], origins=origins,
                       executable_content_digest=prepared['executable_content_digest'],
                       instrumented_fingerprint=attestation['fingerprint'])
    with proof.service(disabled_image, 'disabled', monkeypatch):
        # Same typed create/save/commit/prepare path; force actual generator failure.
        with pytest.raises(AssertionError) as error:
            capture('mapping', {})
        message = str(error.value)
        assert '503' in message and 'backend_unavailable' in message, message
        from deployment.tests.model_client import ruby
        row = json.loads(ruby("puts JSON.generate({'preparations'=>ModelingRevision.where(kind:'preparation').count})",rails=True).splitlines()[-1])
        assert row['preparations'] == 0
        records['disabled_prepare_error'] = message
        records['disabled_preparations'] = row['preparations']
    (proof.ROOT/'proof.json').write_text(json.dumps(records,indent=2)+'\n')


@pytest.mark.integration
def test_original_upstream_static_templates_simple_reference(tmp_path):
    """Original static methods/templates, with the ordinary user compute edit.

    Original upstream emits a placeholder compute body. Its documented user edit
    seam receives the already declared source/symbol/availability wrapper; no
    upstream scaffold, solver, unit or topology is rewritten by this test.
    """
    import ast
    import base64
    from modeling.tests.test_native_generation import BOOT, native
    from hyprn_mvp_app.execution import executable_digest
    from hyprn_mvp_app.store import canonical
    case = fixture('affine')
    encoded = base64.b64encode(json.dumps(case['frozen']['model_snapshot']).encode()).decode()
    reference = native(BOOT + """
require 'whats_opt/openmdao_generator';require 'base64';require 'digest'
m=JSON.parse(Base64.strict_decode64('""" + encoded + """'))
i=m['instances'].fetch(0);definition=m['definitions'].fetch(0)
raise 'Simple fixture only' unless m['instances'].size==1 && m['connections'].empty?
a=Analysis.create!(name:'frozen_model',public:false)
a.impl.update!(package_name:'frozen_model',parallel_group:false,use_units:true)
a.impl.nonlinear_solver.update!(name:'NonlinearRunOnce',iprint:0)
a.impl.linear_solver.update!(name:'LinearRunOnce',iprint:0)
d=Discipline.create!(analysis:a,name:'component_'+i['instance_id'].delete('-'),position:1)
d.impl.update!(support_derivatives:false)
definition['ports'].sort_by { |p| p['port_id'] }.each do |p|
  Variable.create!(discipline:d,name:'p_'+p['port_id'].delete('-'),io_mode:p['direction']=='input' ? 'in' : 'out',type:'Float',shape:'1',units:'K')
end
# The existing audited static constructor avoids unused service generators.
# Reload exact upstream class bytes only after construction. No upstream
# convenience/run/check/formatter method is invoked.
g=WhatsOpt::OpenmdaoGenerator.new(a,static_only:true,symbol_maps:{})
base='/native/provenance-inputs/upstream/app/lib/whats_opt'
# This require has no role in the two local static methods below; the reduced
# image intentionally contains no ServerGenerator. No substitute class exists.
$LOADED_FEATURES << 'whats_opt/server_generator.rb'
load base+'/code_generator.rb'
load base+'/openmdao_generator.rb'
g.instance_variable_set(:@template_dir,base+'/templates')
Dir.mkdir('/tmp/upstream-reference')
g._generate_discipline(d,'/tmp/upstream-reference',with_server:false)
g._generate_main('/tmp/upstream-reference',with_server:false)
files=g.genfiles.to_h { |p| ['generated/'+p.delete_prefix('/tmp/upstream-reference/'),Base64.strict_encode64(File.binread(p))] }
paths=[base+'/code_generator.rb',base+'/openmdao_generator.rb',*Dir.glob(base+'/templates/*')].select { |p| File.file?(p) }
puts 'NATIVE_RESULT='+JSON.generate({'files'=>files,'source_hashes'=>paths.to_h { |p| [p,Digest::SHA256.file(p).hexdigest] },'origins'=>['_generate_discipline','_generate_main'].to_h { |m| [m,g.method(m).source_location] }})
""")
    assert reference['source_hashes']['/native/provenance-inputs/upstream/app/lib/whats_opt/openmdao_generator.rb'] == 'b4fb23ea2a09d37c5c206d51e142958ff872ce20e89a4fcd3275b4d9253edabd'
    original = {p:base64.b64decode(raw) for p,raw in reference['files'].items()}
    assert len(original) == 7
    assert all(v[0].endswith('/upstream/app/lib/whats_opt/openmdao_generator.rb') for v in reference['origins'].values())
    # Compare meaningful static structure while retaining the promotion delta.
    group = 'generated/base/frozen_model_base.py'
    def structure(raw):
        tree = ast.parse(raw)
        return [(n.func.attr,ast.literal_eval(n.args[0])) for n in ast.walk(tree)
                if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
                and n.func.attr in ('add_subsystem','connect','add_input','add_output')]
    assert structure(original[group]) == structure(case['files'][group])
    component_base = next(p for p in original if '/base/component_' in p)
    assert structure(original[component_base]) == structure(case['files'][component_base])
    for raw in (original[group],case['files'][group]):
        assert b'NonlinearRunOnce()' in raw and b'LinearRunOnce()' in raw
    calls = [n for n in ast.walk(ast.parse(original[group])) if isinstance(n,ast.Call)
             and isinstance(n.func,ast.Attribute) and n.func.attr=='add_subsystem']
    promoted = next(k.value for k in calls[0].keywords if k.arg=='promotes')
    assert set(ast.literal_eval(promoted)) == {'p_'+p['port_id'].replace('-','')
        for p in case['frozen']['model_snapshot']['definitions'][0]['ports']}
    assert b'promotes=' not in case['files'][group]
    for port in case['frozen']['model_snapshot']['definitions'][0]['ports']:
        assert b"units='K'" in original[component_base]
    actual, _ = execute_case(case)
    # Only fill the upstream-generated implementation's documented user compute
    # seam. Preserve the exact native class declaration/imports and all bases.
    implementation = next(p for p in original if '/impl/component_' in p)
    authored = case['files'][implementation]
    tree = ast.parse(authored)
    compute = next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='compute')
    original_tree = ast.parse(original[implementation])
    old_compute = next(n for n in ast.walk(original_tree) if isinstance(n,ast.FunctionDef) and n.name=='compute')
    lines = original[implementation].decode().splitlines(keepends=True)
    # Include the separate authored-body method and its exact source markers.
    body = authored.decode().splitlines(keepends=True)[compute.lineno-1:]
    lines[old_compute.lineno-1:old_compute.end_lineno] = body
    updated = 'from native_support import SymbolView\n'+''.join(lines)
    files = {**case['files'],**original,implementation:updated.encode()}
    mapping = json.loads(files['generated/source-map.json'])
    body_lines = updated.splitlines()
    mapping['entries'][0]['generated_line_start'] = next(i+2 for i,l in enumerate(body_lines) if '# BEGIN EXACT BODY' in l)
    mapping['entries'][0]['generated_line_end'] = next(i for i,l in enumerate(body_lines) if '# END EXACT BODY' in l)
    files['generated/source-map.json'] = canonical(mapping)
    prepared = case['prepared']
    # Test-only identity makes the independently generated reference explicit.
    prepared['generator_identity']['name'] += '/original-static-reference'
    for item in prepared['files']:
        raw = files[item['path']]
        item.update(size=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    prepared['executable_content_digest'] = executable_digest(prepared)
    prepared['prepared_digest'] = digest({k:v for k,v in prepared.items() if k!='prepared_digest'})
    case['files'] = files
    direct, _ = execute_case(case)
    assert actual['exit_status'] == direct['exit_status'] == 0
    assert [o['value'] for o in actual['results']['outputs']] == [20]
    assert [o['value'] for o in direct['results']['outputs']] == [20]
    evidence = evidence_root()/('original-reference-'+uid()+'.json')
    evidence.write_text(json.dumps(dict(reference=reference,actual=actual,direct=direct,
        adaptations=['audited static constructor','ordinary user compute body with declared symbol/availability protocol'],
        topology_difference='upstream named variable promotion versus isolated adapter namespaces; single component has no connections'),indent=2)+'\n')
