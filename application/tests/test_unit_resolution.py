"""Data-only app unit readers, always collected through the scoped runner."""
from copy import deepcopy
import base64
import hashlib
import subprocess
from pathlib import Path

import scoped_fixture as guard
from checks import PROJECTION_SCOPE
SCOPE = PROJECTION_SCOPE or guard.scope_from_environment()
guard.validate_scope(SCOPE)

import pytest
from hyprn_mvp_app.store import DomainError, canonical, digest
from test_assumptions_evidence_contracts import sample, D
from test_reuse_contract import uid


def model(version='3'):
    value = sample(D['ModelDraft' + version])
    source = b"raise RuntimeError('must never import source')\n"
    value['source_files'] = [dict(encoding='base64', media_type='text/x-python',
        bytes=base64.b64encode(source).decode(), sha256=hashlib.sha256(source).hexdigest())]
    definition = sample(D['Definition3' if version == '3' else 'Definition'])
    definition.update(definition_id=uid(2), definition_version_id=uid(3),
        source_refs=[value['source_files'][0]['sha256']])
    definition['ports'] = [dict(sample(D['Port3' if version == '3' else 'Port']),
        port_id=uid(4), definition_version_id=uid(3),
        units={'kind':'dimensionless'} if version == '3' else '')]
    value.update(definitions=[definition], instances=[dict(instance_id=uid(5),
        definition_version_id=uid(3), name='Active')], root_instance_id=uid(5))
    value['ports'] = deepcopy(definition['ports'])
    if version == '3': value['required_capabilities'] = ['unit_declarations/1']
    return value


def retained_versions():
    value = model()
    first = value['definitions'][0]
    first['ports'][0]['units'] = {'kind':'unspecified'}
    second = deepcopy(first)
    second['definition_version_id'] = uid(6)
    second['ports'][0].update(definition_version_id=uid(6), units={'kind':'physical', 'expression':'MJ/kg'})
    value['definitions'].append(second)
    value['instances'][0]['definition_version_id'] = uid(6)
    value['ports'] = deepcopy([p for d in value['definitions'] for p in d['ports']])
    return value


@pytest.mark.parametrize('value,label,engine', [('', 'Dimensionless', ''),
    ('m', 'm', 'm'), ({'kind':'dimensionless'}, 'Dimensionless', ''),
    ({'kind':'physical','expression':'MJ/kg'}, 'MJ/kg', 'MJ/kg')])
def test_exact_labels_and_engine_units(value, label, engine):
    from hyprn_mvp_app.units import unit_label, require_engine_unit
    before = canonical(value)
    assert unit_label(value) == label
    assert require_engine_unit(value) == engine
    assert canonical(value) == before


def test_unspecified_readable_but_no_engine_interpretation():
    from hyprn_mvp_app.units import unit_label, require_engine_unit
    assert unit_label({'kind':'unspecified'}) == 'Not specified'
    with pytest.raises(DomainError) as caught: require_engine_unit({'kind':'unspecified'})
    assert caught.value.fields[0]['code'] == 'unit_unspecified'


@pytest.mark.parametrize('value', [None, {}, [], 0, {'kind':'physical'},
    {'kind':'physical','expression':''}, {'kind':'physical','expression':'m '},
    {'kind':'physical','expression':'EUR'}, {'kind':'physical','expression':'__import__("os")'},
    {'kind':'dimensionless','expression':'m'}, {'kind':'unspecified','extra':True}])
def test_malformed_or_unsupported_typed_declarations_rejected(value):
    from hyprn_mvp_app.units import unit_label, require_engine_unit
    for reader in (unit_label, require_engine_unit):
        with pytest.raises(DomainError): reader(value)


def test_legacy_data_label_is_exact_but_unknown_engine_unit_rejected():
    from hyprn_mvp_app.units import unit_label, require_engine_unit
    assert unit_label(' historical-unit ') == ' historical-unit '
    with pytest.raises(DomainError) as caught: require_engine_unit(' historical-unit ')
    assert caught.value.fields[0]['code'] == 'unit_unsupported'


@pytest.mark.parametrize('version', ['1','2','3'])
def test_legacy_and_new_readers_preserve_exact_source_and_records(version):
    from hyprn_mvp_app.units import resolved_model_units, unit_readiness
    value = model(version); before = canonical(value)
    assert unit_readiness(value) == []
    assert resolved_model_units(value) == {(uid(5), uid(3), uid(4)): ''}
    assert canonical(value) == before


def test_retained_unspecified_v1_does_not_block_resolved_bound_v2():
    from hyprn_mvp_app.units import resolved_model_units, unit_readiness
    value = retained_versions(); before = canonical(value)
    assert unit_readiness(value) == []
    assert resolved_model_units(value) == {(uid(5), uid(6), uid(4)): 'MJ/kg'}
    assert canonical(value) == before


def test_creating_v2_without_rebinding_and_second_v1_instance_block_exact_occurrence():
    from hyprn_mvp_app.units import resolved_model_units, unit_readiness
    for second_instance in (False, True):
        value = retained_versions()
        if second_instance: value['instances'].append(dict(instance_id=uid(7), definition_version_id=uid(3), name='Old'))
        else: value['instances'][0]['definition_version_id'] = uid(3)
        before = canonical(value)
        issues = unit_readiness(value)
        assert len(issues) == 1 and issues[0]['code'] == 'unit_unspecified'
        assert issues[0]['path'] == f'/instances/{uid(7) if second_instance else uid(5)}/definitions/{uid(3)}/ports/{uid(4)}/units'
        assert issues[0]['element_ref'] == uid(4)
        with pytest.raises(DomainError) as caught: resolved_model_units(value)
        assert caught.value.fields == issues
        assert canonical(value) == before


@pytest.mark.parametrize('direction', ['input','output','residual'])
def test_every_active_port_requires_resolved_unit(direction):
    from hyprn_mvp_app.units import unit_readiness
    value = model(); value['definitions'][0]['ports'][0].update(direction=direction, units={'kind':'unspecified'})
    value['ports'] = deepcopy(value['definitions'][0]['ports'])
    assert unit_readiness(value)[0]['code'] == 'unit_unspecified'


def test_mixed_retained_definitions_shared_port_ids_and_exact_instance_bindings():
    from hyprn_mvp_app.units import resolved_model_units
    value = retained_versions()
    value['definitions'][0]['ports'][0]['units'] = ''
    value['instances'].append(dict(instance_id=uid(7), definition_version_id=uid(3), name='Legacy'))
    value['ports'] = deepcopy([p for d in value['definitions'] for p in d['ports']])
    before = canonical(value)
    assert resolved_model_units(value) == {(uid(5),uid(6),uid(4)):'MJ/kg', (uid(7),uid(3),uid(4)):''}
    assert canonical(value) == before


@pytest.mark.parametrize('expression', D['UnitDeclaration1']['oneOf'][2]['properties']['expression']['enum'])
def test_every_authoritative_spelling_is_returned_exactly(expression):
    from hyprn_mvp_app.units import require_engine_unit
    assert require_engine_unit(expression) == expression
    assert require_engine_unit({'kind':'physical','expression':expression}) == expression


@pytest.mark.parametrize('version', ['1','2','3'])
def test_immutable_versions_are_data_only_and_never_rewritten(version):
    from hyprn_mvp_app.units import resolved_model_units, unit_readiness
    draft = model(version)
    revision = sample(D['ModelRevision' + version])
    revision.update({key: deepcopy(value) for key, value in draft.items() if key in revision})
    revision['digest'] = digest({key:value for key,value in revision.items() if key != 'digest'})
    before = canonical(revision)
    assert resolved_model_units(revision) == {(uid(5),uid(3),uid(4)):''}
    assert canonical(revision) == before
    if version == '3':
        revision['definitions'][0]['ports'][0]['units'] = {'kind':'unspecified'}
        revision['ports'] = deepcopy(revision['definitions'][0]['ports'])
        revision['digest'] = digest({key:value for key,value in revision.items() if key != 'digest'})
        incomplete = canonical(revision)
        assert unit_readiness(revision)[0]['code'] == 'unit_unspecified'
        with pytest.raises(DomainError): resolved_model_units(revision)
        assert canonical(revision) == incomplete


def test_two_instances_of_same_version_have_separate_occurrences():
    from hyprn_mvp_app.units import resolved_model_units
    value = model()
    value['instances'].append(dict(value['instances'][0], instance_id=uid(7)))
    assert resolved_model_units(value) == {(uid(5),uid(3),uid(4)):'', (uid(7),uid(3),uid(4)):''}


def test_legacy_model_cannot_acquire_typed_port_by_reader_coercion():
    from hyprn_mvp_app.units import resolved_model_units
    value = model('2')
    value['definitions'][0]['ports'][0]['units'] = {'kind':'dimensionless'}
    value['ports'] = deepcopy(value['definitions'][0]['ports'])
    with pytest.raises(DomainError): resolved_model_units(value)


# ---- The single port-units rule (units.port_units) ----

@pytest.mark.parametrize('version', ['1','2'])
@pytest.mark.parametrize('units', ['', 'm', ' historical-unit ', 'furlong/fortnight'])
def test_port_units_returns_exact_legacy_literals_without_engine_interpretation(version, units):
    from hyprn_mvp_app.units import port_units
    value = model(version)
    value['definitions'][0]['ports'][0]['units'] = units
    value['ports'] = deepcopy(value['definitions'][0]['ports'])
    value['instances'].append(dict(value['instances'][0], instance_id=uid(7)))
    before = canonical(value)
    assert port_units(value) == {(uid(5),uid(3),uid(4)): units, (uid(7),uid(3),uid(4)): units}
    assert canonical(value) == before


def test_port_units_legacy_never_skips_an_instance_without_its_definition():
    from hyprn_mvp_app.units import port_units
    value = model('2')
    value['instances'].append(dict(instance_id=uid(7), definition_version_id=uid(99), name='Dangling'))
    with pytest.raises(KeyError): port_units(value)


def test_port_units_resolves_model3_exactly_like_the_resolver():
    from hyprn_mvp_app.units import port_units, resolved_model_units
    for value in (model('3'), retained_versions()):
        before = canonical(value)
        assert port_units(value) == resolved_model_units(value)
        assert canonical(value) == before
    assert port_units(retained_versions()) == {(uid(5),uid(6),uid(4)): 'MJ/kg'}


def test_port_units_never_relaxes_incomplete_typed_units():
    from hyprn_mvp_app.units import port_units, unit_readiness
    value = retained_versions(); value['instances'][0]['definition_version_id'] = uid(3)
    before = canonical(value)
    with pytest.raises(DomainError) as caught: port_units(value)
    assert (caught.value.code, caught.value.status) == ('invalid_model', 422)
    assert caught.value.fields == unit_readiness(value)
    assert canonical(value) == before


@pytest.mark.parametrize('version', ['0','6','99','', None, 3, '3 '])
def test_port_units_unknown_model_version_is_explicitly_unsupported(version):
    from hyprn_mvp_app.units import port_units
    value = model('2'); value['schema_version'] = version
    before = canonical(value)
    with pytest.raises(DomainError) as caught: port_units(value)
    assert (caught.value.code, caught.value.status) == ('unsupported_record_version', 422)
    assert canonical(value) == before


@pytest.mark.parametrize('failure', ['retained-malformed','mixed-in-definition','unknown-version',
    'missing-definition','duplicate-definition','duplicate-instance','duplicate-port',
    'wrong-port-version','aggregate-mismatch','aggregate-duplicate','aggregate-order'])
def test_invalid_retained_structure_and_ambiguous_bindings_fail_closed(failure):
    from hyprn_mvp_app.units import unit_readiness
    value = retained_versions(); first = value['definitions'][0]
    if failure == 'retained-malformed': first['ports'][0]['units']['extra'] = True
    if failure == 'mixed-in-definition': first['ports'].append(dict(first['ports'][0], port_id=uid(8), units='m'))
    if failure == 'unknown-version': value['schema_version'] = '99'
    if failure == 'missing-definition': value['instances'][0]['definition_version_id'] = uid(99)
    if failure == 'duplicate-definition': value['definitions'].append(deepcopy(first))
    if failure == 'duplicate-instance': value['instances'].append(deepcopy(value['instances'][0]))
    if failure == 'duplicate-port': first['ports'].append(deepcopy(first['ports'][0]))
    if failure == 'wrong-port-version': first['ports'][0]['definition_version_id'] = uid(99)
    value['ports'] = deepcopy([p for d in value['definitions'] for p in d['ports']])
    if failure == 'aggregate-mismatch': value['ports'][0]['units'] = {'kind':'dimensionless'}
    if failure == 'aggregate-duplicate': value['ports'].append(deepcopy(value['ports'][0]))
    if failure == 'aggregate-order': value['ports'].reverse()
    before = canonical(value)
    with pytest.raises(DomainError): unit_readiness(value)
    assert canonical(value) == before


def test_generated_artifacts_match_authority_and_typed_client_preserves_protocol():
    root = Path(__file__).resolve().parents[2]
    output = guard.scoped_path(SCOPE, 'artifacts/b2.openapi.json')
    generated = subprocess.run(guard.contract_generator_command(SCOPE, 'artifacts/b2.openapi.json'),
        env=guard.clean_environment(SCOPE), capture_output=True, text=True)
    assert generated.returncode == 0, generated.stdout + generated.stderr
    assert output.read_bytes() == (root/'contracts/hyprn-mvp.openapi.yaml').read_bytes()
    client = guard.scoped_path(SCOPE, 'artifacts/client')
    client.mkdir()
    generated_ts = subprocess.run([SCOPE.interpreter, '-B', str(root/'ui/generate_types.py'),
        '--input', str(output), '--output', str(client/'contract.ts')],
        env=guard.clean_environment(SCOPE), capture_output=True, text=True)
    assert generated_ts.returncode == 0, generated_ts.stderr
    assert (client/'contract.ts').read_bytes() == (root/'ui/src/contract.ts').read_bytes()
    (client/'api.ts').write_bytes((root/'ui/src/api.ts').read_bytes())
    (client/'types.ts').write_text('''import type { NewModel3, PublicNewModel, Apply3, PortDeclaration3 } from './contract';
const fresh: NewModel3 = { schema_version: '3', command_id: 'c', expected_revision: 'r', name: 'm', template: 'empty' };
const publicValue: PublicNewModel = fresh;
// @ts-expect-error explicit new creation must include its version
const missing: NewModel3 = { command_id: 'c', expected_revision: 'r', name: 'm', template: 'empty' };
// @ts-expect-error new authoring never accepts historical raw unit strings
const legacy: PortDeclaration3 = { temp_key: 'p', direction: 'input', name: 'p', code_symbol: 'p', value_type: 'real_scalar', units: '' };
const typed: PortDeclaration3 = { temp_key: 'p', direction: 'input', name: 'p', code_symbol: 'p', value_type: 'real_scalar', units: {kind: 'unspecified'} };
const edits: Apply3 = { schema_version: '3', command_id: 'c', expected_revision: 'r', edits: [{kind:'create_definition', temp_key:'d', definition_kind:'explicit_component', name:'d', ports:[typed], source:{encoding:'base64',media_type:'text/x-python',bytes:'',sha256:'a'}}] };
''')
    compiled = subprocess.run(['node', str(root/'ui/node_modules/typescript/bin/tsc'),
        '--strict', '--skipLibCheck', '--target', 'ES2022', '--module', 'commonjs',
        '--lib', 'ES2022,DOM', '--outDir', str(client/'out'), str(client/'api.ts'), str(client/'types.ts')],
        env=guard.clean_environment(SCOPE), capture_output=True, text=True)
    guard.scoped_path(SCOPE, 'evidence/client-types.log').write_text(compiled.stdout + compiled.stderr)
    assert compiled.returncode == 0, compiled.stdout + compiled.stderr
    script = client/'client-check.cjs'
    script.write_text('''const assert = require('node:assert/strict');
const client = require('./out/api.js');
const {ApiError} = client;
const [[, PublicApi], ...otherApis] = Object.entries(client).filter(([name, value]) => typeof value === 'function' && /Api$/.test(name));
assert.equal(otherApis.length, 0, 'one public API client class');
(async () => {
 const api = new PublicApi(); api.actor='owner'; api.csrf='csrf';
 const calls=[]; let payload; let status=200;
 global.fetch=async (path, options) => {calls.push({path,options}); return {ok:status===200,status,json:async()=>payload};};
 const catalog={schema_version:'1',supported_units:['MJ/kg'],catalog_digest:'frozen'};
 payload={schema_version:'1',data:catalog}; const controller=new AbortController();
 assert.deepEqual(await api.unitCatalog('study',controller.signal),catalog);
 assert.equal(calls.at(-1).path,'/api/1/studies/study/unit-catalog');
 assert.equal(calls.at(-1).options.method,'GET'); assert.equal(calls.at(-1).options.credentials,'same-origin');
 controller.abort(); assert.equal(calls.at(-1).options.signal.aborted,true);
 const model={schema_version:'3',study_id:'study',model_id:'model',draft_revision:'r',instances:[],connections:[],definitions:[]};
 payload={schema_version:'1',data:model};
 const create={schema_version:'3',command_id:'create',expected_revision:'r',name:'Model',template:'empty'};
 await api.createModelCommand('study',create); assert.deepEqual(JSON.parse(calls.at(-1).options.body),create);
 for(const version of [undefined,'2','3']) {
  const command={command_id:'edit',expected_revision:'r',edits:[{kind:'rename_model',name:'Renamed'}]};
  if(version) command.schema_version=version;
  const before=JSON.stringify(command);
  await api.previewEdits(model,command);
  const sent=JSON.parse(calls.at(-1).options.body);
  assert.equal(sent.schema_version,version); assert.equal('command_id' in sent,false);
  assert.deepEqual(sent.edits,command.edits); assert.equal(JSON.stringify(command),before);
 }
 const apply={schema_version:'3',command_id:'apply',expected_revision:'r',edits:[{kind:'rename_model',name:'New'}]};
 await api.applyCommand(model,apply); assert.deepEqual(JSON.parse(calls.at(-1).options.body),apply);
 assert.equal(calls.at(-1).options.headers['X-CSRF-Token'],'csrf');
 const callCount=calls.length;
 await assert.rejects(api.apply(model,apply.edits), /explicit version3 or version4 command/);
 await assert.rejects(api.apply({...model,schema_version:'4'},apply.edits), /explicit version3 or version4 command/);
 assert.equal(calls.length,callCount);
 await api.apply({...model,schema_version:'2'},apply.edits);
 assert.equal(JSON.parse(calls.at(-1).options.body).schema_version,'2');
 status=503; payload={error:{code:'backend_unavailable',message:'Unavailable',fields:[],outcome:'unchanged'}};
 await assert.rejects(api.unitCatalog('study'), ApiError);
 console.log('Catalog public GET, abort/error, Create3, Preview1/2/3, Apply3 and unchanged command verified (fetch double).');
})().catch(error=>{console.error(error);process.exit(1)});
''')
    checked = subprocess.run(['node', str(script)], env=guard.clean_environment(SCOPE), capture_output=True, text=True)
    guard.scoped_path(SCOPE, 'evidence/client-runtime.log').write_text(checked.stdout + checked.stderr)
    assert checked.returncode == 0, checked.stdout + checked.stderr
