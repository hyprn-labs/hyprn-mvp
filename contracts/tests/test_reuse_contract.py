"""Data-only wire examples; no model service, native store or candidate imports.

JSON Schema checks wire shapes. Canonical serialization rejects non-JSON numbers
at the same boundary used by the app. Cross-record authority, keyed uniqueness,
digest equality and archive safety remain producer/consumer checks in later tasks.
"""
from hyprn_mvp_app.contracts import authored_schema
from test_schema_sources import assert_execution_schema
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import UUID

import pytest
import rfc8785
from jsonschema import Draft202012Validator, FormatChecker, ValidationError

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = authored_schema()
DEFS = SCHEMA['$defs']
SHA = 'a' * 64


@pytest.mark.parametrize('path',['.aiida/calcinfo.json','.aiida/job_tmpl.json','generated/base/model.py','result.json'])
def test_native_repository_inventory_exact_metadata_paths(path):
    validate('RepositoryInventory',dict(node_uuid=uid(1),path=path,size=1,sha256=SHA))


@pytest.mark.parametrize('path',['.aiida/other.json','.aiida/calcinfo.json/extra','.aiida/calcinfo.json.bak',
    '.aiida/job_tmpl.jsonx','.aiida/calcinfo.json\n','.aiida/job_tmpl.json\n','ordinary.txt\n',
    'x/.aiida/calcinfo.json','.hidden','../.aiida/calcinfo.json','./.aiida/calcinfo.json',
    '/.aiida/calcinfo.json','.aiida/../calcinfo.json','.aiida\\calcinfo.json','a//b','a/./b','a/../b',
    'a/'*32+'b','a'*513])
def test_native_repository_inventory_rejects_other_hidden_or_unsafe_paths(path):
    with pytest.raises(ValidationError):
        validate('RepositoryInventory',dict(node_uuid=uid(1),path=path,size=1,sha256=SHA))


@pytest.mark.parametrize('path',['.aiida/calcinfo.json','.aiida/job_tmpl.json'])
def test_native_metadata_path_exception_does_not_apply_to_payload_files(path):
    with pytest.raises(ValidationError):
        validate('PayloadFile',dict(path=path,role='generated',size=1,sha256=SHA))


def uid(n):
    return str(UUID(int=n))


def port(n=1):
    return dict(instance_id=uid(n), port_id=uid(n + 1))


def validate(name, value):
    rfc8785.dumps(value)
    Draft202012Validator({**SCHEMA, '$ref': '#/$defs/' + name}, format_checker=FormatChecker()).validate(value)


def numerical():
    return dict(mode='deterministic', initialization=[], solvers=[],
                derivatives=dict(method='none', form=None, check=None),
                design_variables=[], objectives=[], constraints=[], optimizer=None, uncertainty=None)


def provenance():
    return dict(kind='manual', statement='Recorded sizing output', evidence_version_ids=[])


def result_request():
    return dict(kind='run_result', target=port(), source_run_id=uid(10), source_output=port(20),
                expected_results_digest=SHA, provenance=provenance())


def request():
    return dict(schema_version='2', study_id=uid(30), model_id=uid(31), model_revision_id=uid(32),
                name='Comparison', inputs=[result_request()], criteria=[], numerical=numerical(),
                context_source=dict(kind='current_study', expected_study_revision='revision-1'),
                notes=[], evidence_version_ids=[], derivation=None)


def runtime():
    return dict(image_digest='sha256:' + SHA, architecture='linux/arm64', python_version='3.12.15',
                worker_entrypoint='hyprn_mvp_integration.worker', policy_digest=SHA)


def binding():
    return dict(source_run_id=uid(10), source_output=port(20), results_digest=SHA,
                source_configuration_digest=SHA, original_value=150, original_units='cm',
                conversion=dict(policy='openmdao-linear-catalog-1', catalog_digest=SHA, source_units='cm',
                                destination_units='m', factor=.01, destination_value=1.5),
                labels=dict(run_name='Sizing', model_name=None, model_revision_id=uid(32),
                            instance_name='Sizing component', output_name='Length'))


def candidate():
    r = request()
    return {k: v for k, v in r.items() if k not in {'notes', 'evidence_version_ids'}} | dict(
        inputs=[dict(target=port(), value=150, units='cm', provenance=provenance(), result_binding=binding())],
        context_snapshot=dict(description='Size the vessel', boundary='Static', notes=[]),
        evidence_snapshots=[], required_capabilities=['flat_explicit_scalar', 'result_linked_inputs/1'])


def revision():
    return candidate() | dict(configuration_id=uid(40), configuration_revision_id=uid(41),
                              parent_revision_id=None, digest=SHA)


def test_request_and_resolved_records_are_distinct_closed_types():
    validate('ConfigurationRequest2', request())
    validate('ConfigurationCandidate2', candidate())
    validate('ConfigurationRevision2', revision())
    for name, value in [('ConfigurationRequest2', candidate()), ('ConfigurationRequest2', revision()),
                        ('ConfigurationCandidate2', request()), ('ConfigurationCandidate2', revision())]:
        with pytest.raises(ValidationError):
            validate(name, value)


@pytest.mark.parametrize('field,value', [('value', 999), ('units', 'm'), ('result_uuid', uid(99)),
    ('association', dict(store_uuid=uid(98), process_uuid=uid(99))), ('result_binding', binding())])
def test_public_result_reference_cannot_claim_resolved_value_or_native_authority(field, value):
    bad = request()
    bad['inputs'][0][field] = value
    with pytest.raises(ValidationError):
        validate('ConfigurationRequest2', bad)


@pytest.mark.parametrize('value', [True, False, None, '150', float('inf'), float('-inf'), float('nan')])
def test_resolved_values_are_finite_scalars_not_bools(value):
    bad = candidate()
    bad['inputs'][0]['value'] = value
    with pytest.raises((ValidationError, ValueError)):
        validate('ConfigurationCandidate2', bad)


def test_historical_labels_allow_missing_model_name_without_losing_exact_component():
    value = binding()
    validate('ResultBinding', value)
    assert value['labels']['model_name'] is None
    for field in ('run_name', 'instance_name', 'output_name', 'model_revision_id'):
        bad = copy.deepcopy(value)
        bad['labels'][field] = None
        with pytest.raises(ValidationError):
            validate('ResultBinding', bad)


def test_private_projection_has_exact_literal_fields_and_separate_digest_shape():
    public = revision()
    private = {k: v for k, v in public.items() if k not in {'context_source', 'derivation'}}
    private['inputs'] = [{k: v for k, v in public['inputs'][0].items() if k != 'result_binding'}]
    private['required_capabilities'] = ['flat_explicit_scalar']
    validate('ModelingConfigurationRevision2', private)
    with pytest.raises(ValidationError):
        validate('ModelingConfigurationRevision2', public)
    with pytest.raises(ValidationError):
        validate('ConfigurationRevision2', private)
    assert rfc8785.dumps(public) != rfc8785.dumps(private)


def test_common_definitions_and_legacy_authorities_are_preserved():
    other = authored_schema()
    assert_execution_schema()
    for schema in (SCHEMA, other):
        Draft202012Validator.check_schema(schema)
    # Pinned pre-task definitions; this gate detects accidental v1 tightening.
    for name, expected in LEGACY_HASHES.items():
        # AE names the exact historical snapshot before widening the read alias.
        # Reverse only that reference rename for the historical hash comparison.
        legacy = json.loads(json.dumps(DEFS[name]).replace(
            '#/$defs/EvidenceSnapshotLegacy', '#/$defs/EvidenceSnapshot'))
        assert hashlib.sha256(rfc8785.dumps(legacy)).hexdigest() == expected


LEGACY_HASHES = {'ConfigurationCandidate1': 'f6735d98e741172fa61c7b23101b954ce6cec1c9df25b1480657a0b8792edee3', 'ConfigurationRevision1': 'f010f3cb1987db9d49365bc6189530386e87abf72381619bc5681d3b467ef9d2', 'ExecutionBundle2': 'adc18ac80f58753bbe8c62a87ee4cb7feef74f2199032190f467cc40d04fb687', 'HistoricalExecutionBundleV1': 'fb2627608837dcf164cd6f3ff5adb007e827af1d0708445b753c6c9df9d2fe72', 'Numerical': 'd4d8aa9cb6d742747d5480c6ef3bf83e223aa6228a80726b4f73e05a04361fe7', 'Input': 'a7218e38addee8bcf308b9f15fac0685de8228a0da952e9b3d419bd75d83a0b7'}


def test_ae_preserves_preexisting_concrete_contracts_after_reference_renames():
    # Pins captured before AE schema edits. Reverse only explicit historical
    # reference renames; never erase/add fields or normalize payload versions.
    renamed = {n:n+'1' for n in ('ModelDraft','ModelRevision','ModelPackage','Edit','Preview','Apply')}
    renamed['EvidenceSnapshot'] = 'EvidenceSnapshotLegacy'
    for name, expected in AE_LEGACY_HASHES.items():
        value = json.dumps(DEFS[renamed.get(name, name)], sort_keys=True, separators=(',',':'))
        for prior, current in renamed.items():
            value = value.replace('"#/$defs/' + current + '"', '"#/$defs/' + prior + '"')
        assert hashlib.sha256(value.encode()).hexdigest() == expected, name


AE_LEGACY_HASHES = {
    'ModelDraft':'8c55ff429d90b1040e0261dd4e9e11cbed58b932733edd537d622f366779b34d',
    'ModelRevision':'acc65cb1e1c564e854c9e0b5d4b625c490644500bfdf0027f6d57a11cb5870da',
    'ModelPackage':'8fba60b6cde75e0461a10681ff956ce1e2fbcd839f6159d20c2c43db3266b293',
    'Edit':'465edcdf3c343288888f103b0da68e262f2dfb18d4c48d7def75c94e991a3586',
    'Preview':'df3da7632f39d8ea9bb70521f1e90cb8482edde013e0cda24d750612c1f17b52',
    'Apply':'89b3f38bb687ff272e07c2f271200c244e0a82ca2449c88871be210c55e24fe7',
    'EvidenceSnapshot':'539ed60f2255d146000fad995acfc565a4a04e7be7a97d37b52e57c9968741b3',
    'EvidenceRecord1':'6c8ab1a9833f640967e4557d6479c23a851c941a70a7dcee5b8eb4cb8a9d40d8',
    'EvidenceRecord2':'a35f4cf01e93329de8461bead7deb77afdf3d466b58f7b1e9f7c3d9a701544fd',
    'ConfigurationCandidate2':'d828ee1291b71df09ac985b02d4c560cd5cbd343475a5af9901d7eea7e113ded',
    'ConfigurationRevision2':'15daa1f6061570529f2e6dfa2ad0b5782c53627decb3a0105dedbe62109cd67b',
    'ModelingConfiguration2':'129267ee952dc614f4a046b4f37607ea784c955950d0ebfce0728ddf1a7abf44',
    'ModelingConfigurationRevision2':'6a387a9dc40f0a5858c4368266be206bf83db047a925095cc953f2c8b6fe528b',
    'ModifiedRunSeed1':'c57d1cc62a5132296d7a44c8192d526981a21864b53badd207b32e5b89172b8b',
    'ExecutionBundle3':'137670a8922a147fa370ee21b7f7d6e05a8df7b02047af0093a65dae92ab0e8e',
    'PreparedModelArtifact':'1f82dddac0da126c1a4bda1469f02ec35da21d76522d7e8b2c5a22da394dc73e',
    'ProgramEntrypoint':'936929ec4455acff3c69a523c47690644a9dbdc26139e31057273a3f36513d81',
    'ProgramBindings':'2785e55f2630ffb93e74475abc1dbe07dc0306e76eb73c01df046438019d9c9f',
    'ComputationalRecordManifest1':'274d2a6ed5e8e7619c636643770245f108b54767e34c3b35d8de6d5d371ab404',
    'ArchiveRecordRequest1':'b301026b0559c38f53e469261bd66067e0d96a5bed074987dd8c3cd8993c3bb5',
    'Annotation':'74b3a8f1a880bd127c6ba1111dee20ba2ff94c07c482d41b8475fc38e9af1d8d',
    'Definition':'e5d387b44f62e09b89b8646605d97082de8b2eb9d6eec77a9d50f5b4cf5fe865',
}


def test_old_literal_and_bundles_remain_readable_without_rewriting():
    from test_native_program_contract import fixture, bundle
    old = {k: v for k, v in revision().items() if k not in {'context_source', 'derivation'}}
    old['schema_version'] = '1'
    old['inputs'] = [{k: v for k, v in old['inputs'][0].items() if k != 'result_binding'}]
    old['required_capabilities'] = ['flat_explicit_scalar']
    before = rfc8785.dumps(old)
    validate('ConfigurationRevision', old)
    validate('ConfigurationCandidate', old)  # Legacy optional immutable fields remain legal.
    assert before == rfc8785.dumps(old)
    artifact, files = fixture()
    b = bundle(artifact, files)
    before = rfc8785.dumps(b)
    validate('ExecutionBundle2', b)
    validate('ExecutionBundleRead', b)
    assert before == rfc8785.dumps(b)
    b['schema_version'] = '1'
    for k in ('entrypoint', 'executable_content_digest'):
        del b[k]
    b['generator'] = {k: b['generator'][k] for k in ('name', 'version', 'source_commit', 'template_digest')}
    b['licenses'] = ['licenses/model-notices.json']
    before = rfc8785.dumps(b)
    validate('ExecutionBundleRead', b)
    with pytest.raises(ValidationError):
        validate('ExecutionBundle', b)
    assert before == rfc8785.dumps(b)


def test_bounds_duplicate_identities_versions_and_context_discriminants():
    for update in [dict(schema_version='99'), dict(schema_version=2), dict(notes=['x'] * 1001),
                   dict(name='x' * 4097), dict(evidence_version_ids=[uid(1), uid(1)]),
                   dict(inputs=[result_request(), result_request()]), dict(inputs=[result_request()] * 1001),
                   dict(context_source=dict(kind='current_study', expected_study_revision='r', choice_confirmed=True))]:
        with pytest.raises(ValidationError):
            validate('ConfigurationRequest2', request() | update)


def test_generator_chain_supports_union_types_without_changing_public_outputs(tmp_path):
    assert "ConfigurationRequest2" in DEFS  # Refuse legacy generators before isolated output support.
    public = tmp_path / 'hyprn-mvp.openapi.json'
    types = tmp_path / 'contract.ts'
    before = {p: (ROOT / p).read_bytes() for p in ['contracts/hyprn-mvp.openapi.yaml', 'ui/src/contract.ts']}
    import scoped_fixture as fixture
    fields = json.loads((Path(os.environ['HYPRN_MVP_TEST_SCOPE_ROOT']) / 'scope.json').read_text())
    fields['root'] = Path(fields['root'])
    scope = fixture.Scope(**fields)
    env = fixture.clean_environment(scope)
    subprocess.run(fixture.contract_generator_command(scope, public.relative_to(scope.root)),
                   cwd=ROOT, env=env, check=True, capture_output=True)
    subprocess.run([sys.executable, '-B', str(ROOT / 'ui/generate_types.py'), '--input', str(public), '--output', str(types)],
                   cwd=ROOT, env=env, check=True, capture_output=True)
    generated = types.read_text()
    assert 'export type ConfigurationRequest2' in generated
    assert '"kind": "run_result"' in generated
    assert '"schema_version": "2"' in generated
    assert 'ConfigurationRevision1 | ConfigurationRevision2' in generated
    for line in generated.splitlines():
        if line.startswith(('export type ConfigurationRequest2', 'export type ModelingConfiguration2', 'export type ResultBinding')):
            assert 'unknown' not in line
    assert before == {p: (ROOT / p).read_bytes() for p in before}
    spec = json.loads(public.read_text())
    source_route=spec['paths']['/studies/{study_id}/result-sources']
    assert set(source_route)=={'get'}
    assert source_route['get']['responses']['200']['content']['application/json']['schema'][
        'properties'
    ]['data'] == {'$ref': '#/components/schemas/ResultSourcePage3'}
    assert spec['paths']['/studies/{study_id}/configurations/preview']['post']['requestBody']['content']['application/json']['schema']['$ref'].endswith('/PublicConfigurationRequest')
    seed_route=spec['paths']['/studies/{study_id}/runs/{run_id}/modified-run-seed']
    assert set(seed_route)=={'get'}
    assert seed_route['get'].get('security',spec['security'])==[{'session':[]}]
    # The compatibility reader includes monetary history without rewriting its predecessors.
    assert seed_route['get']['responses']['200']['content']['application/json']['schema']['properties']['data']=={
        '$ref':'#/components/schemas/ModifiedRunSeedRead6'}
    schemas = spec['components']['schemas']
    def variants(name, ancestors=()):
        assert name not in ancestors, ('recursive reader', name)
        branches = schemas[name].get('oneOf')
        if branches is None:
            return [name]
        return [leaf for branch in branches
                for leaf in variants(branch['$ref'].rsplit('/', 1)[-1], (*ancestors, name))]
    expected = {f'ModifiedRunSeed{version}' for version in (1, 2, 3, 4, 6, 7, 8, 9)}
    for name in ('ModifiedRunSeedRead6', 'ModifiedRunSeedRead8', 'ModifiedRunSeedRead9'):
        leaves = variants(name)
        assert {leaf.split('Model', 1)[0] for leaf in leaves} == expected
        assert len(leaves) == len(set(leaves)), ('ambiguous reader', name)
    for name in ('RunHistoryRead9', 'FrozenConfigurationRead10'):
        leaves = variants(name)
        assert len(leaves) == len(set(leaves)), ('ambiguous reader', name)
    assert spec['components']['schemas']['ModifiedRunSeed']=={'oneOf':[
        {'$ref':'#/components/schemas/ModifiedRunSeed1'}, {'$ref':'#/components/schemas/ModifiedRunSeed2'},
        {'$ref':'#/components/schemas/ModifiedRunSeed3'}, {'$ref':'#/components/schemas/ModifiedRunSeed4'}]}
    record_routes={
        '/studies/{study_id}/computational-record-previews':('post','202'),
        '/studies/{study_id}/computational-records':('post','202'),
        '/studies/{study_id}/computational-records/{request_id}':('get','200'),
        '/studies/{study_id}/computational-records/{request_id}/download':('get','200')}
    assert {p for p in spec['paths'] if 'computational-record' in p}==set(record_routes)
    for path,(method,status) in record_routes.items():
        assert set(spec['paths'][path])=={method}
        operation=spec['paths'][path][method]
        assert operation.get('security',spec['security'])==[{'session':[]}]
        content=operation['responses'][status]['content']
        if path.endswith('/download'):
            assert content=={'application/zip':{'schema':{'type':'string','format':'binary'}}}
        else:assert content['application/json']['schema']['properties']['data']=={'$ref':'#/components/schemas/RecordRequestRead'}
    # The implemented export reader validates this exact closed historical union.
    assert DEFS['RecordRequestRead']=={'oneOf':[{'$ref':'#/$defs/RecordRequest'},{'$ref':'#/$defs/RecordRequest2'}]}
    legacy=dict(schema_version='1',request_id=uid(1),kind='preview',state='queued',
        selected_run_ids=[uid(2)],preview=None,error=None,download=None)
    current=legacy | {'schema_version':'2','approach_summary':None}
    operation=spec['paths']['/studies/{study_id}/computational-records/{request_id}']['get']['responses']['200']['content']['application/json']['schema']['properties']['data']
    reader=Draft202012Validator(dict(operation,components=spec['components']),format_checker=FormatChecker())
    for value in (legacy,current):
        validate('RecordRequestRead',value);reader.validate(value)
        for invalid in (value | {'schema_version':'99'},value | {'unknown':True},value | {'download':{}}):
            with pytest.raises(ValidationError):reader.validate(invalid)
    subprocess.run([str(ROOT / 'ui/node_modules/.bin/tsc'), '--noEmit', '--skipLibCheck', '--strict',
                    '--target', 'ES2022', str(types)], cwd=tmp_path, env=env, check=True, capture_output=True)


def test_contract_interpreter_is_fixed_and_output_cannot_escape_scope():
    import scoped_fixture as fixture
    fields = json.loads((Path(os.environ['HYPRN_MVP_TEST_SCOPE_ROOT']) / 'scope.json').read_text())
    fields['root'] = Path(fields['root'])
    scope = fixture.Scope(**fields)
    with pytest.raises(ValueError, match='Reviewed application'):
        fixture.contract_generator_command(scope, 'evidence/public.json', interpreter='/usr/bin/python3')
    with pytest.raises(ValueError, match='Relative fixture'):
        fixture.contract_generator_command(scope, '../public.json')


def test_no_native_modules_or_profile_initialization():
    assert not any(n.split('.')[0] in {'aiida', 'openmdao', 'openturns'} for n in sys.modules)
    assert not (Path(os.environ['AIIDA_PATH']) / '.aiida/config.json').exists()


def limits():
    return dict(selected_runs=16, computational_runs=64, logical_paths=4096, expanded_bytes=33554432,
                native_archive_bytes=16777216, wrapper_bytes=33554432, per_file_bytes=16777216,
                inventory_bytes=4194304, metadata_bytes=1048576)


def test_bundle3_requires_both_digest_domains_and_all_three_inventory_records():
    from test_native_program_contract import fixture, bundle
    artifact, files = fixture()
    value = bundle(artifact, files) | dict(schema_version='3', modeling_configuration_digest='b' * 64,
        result_dependencies=dict(path='result-dependencies.json', sha256=SHA, size=48))
    value['files'] += [dict(path=p, role=r, sha256=SHA, size=48, media_type='application/json') for p, r in [
        ('configuration.json', 'configuration'), ('modeling-configuration.json', 'modeling_configuration'),
        ('result-dependencies.json', 'result_dependencies')]]
    validate('ExecutionBundle3', value)
    validate('ExecutionBundle', value)
    for field in ('modeling_configuration_digest', 'result_dependencies'):
        bad = copy.deepcopy(value)
        del bad[field]
        with pytest.raises(ValidationError):
            validate('ExecutionBundle3', bad)
    for path in ('configuration.json', 'modeling-configuration.json', 'result-dependencies.json'):
        bad = copy.deepcopy(value)
        bad['files'] = [f for f in bad['files'] if f['path'] != path]
        with pytest.raises(ValidationError):
            validate('ExecutionBundle3', bad)
    with pytest.raises(ValidationError):
        validate('ExecutionBundle2', value)


def test_native_dependencies_are_typed_bounded_and_not_public_request_authority():
    source = dict(label='r' + uid(100).replace('-', ''), source_run_id=uid(10),
        request=dict(run_id=uid(10), scope=uid(30), command_id=uid(101), payload_digest=SHA, bundle_digest=SHA),
        association=dict(store_uuid=uid(102), process_uuid=uid(103)), result_uuid=uid(100), results_digest=SHA)
    mapping = dict(target=port(), source_label=source['label'], source_output=port(20), results_digest=SHA,
                   original_value=150, original_units='cm', conversion=binding()['conversion'])
    value = dict(schema_version='1', sources=[source], mappings=[mapping])
    validate('ResultDependencies1', value)
    raw_store=UUID(source['association']['store_uuid']).hex
    validate('NativeSource',source|dict(association=source['association']|dict(store_uuid=raw_store)))
    for invalid in (raw_store.upper().replace('0','A',1), '{'+raw_store+'}', raw_store+'0', 'not-a-store'):
        with pytest.raises(ValidationError):
            validate('NativeSource',source|dict(association=source['association']|dict(store_uuid=invalid)))
    for key in ('source_run_id','result_uuid'):
        with pytest.raises(ValidationError):validate('NativeSource',source|{key:UUID(source[key]).hex})
    with pytest.raises(ValidationError):
        validate('NativeSource',source|dict(association=source['association']|dict(process_uuid=UUID(source['association']['process_uuid']).hex)))
    validate('ResultDependencies1', dict(schema_version='1', sources=[], mappings=[]))
    for update in [dict(sources=[source] * 65), dict(mappings=[mapping] * 1001),
                   dict(sources=[source | dict(process_class='untrusted.module')]),
                   dict(sources=[source | dict(request=source['request'] | dict(native_pk=1))]),
                   dict(mappings=[mapping | dict(source_label='../../escape')])]:
        with pytest.raises(ValidationError):
            validate('ResultDependencies1', value | update)


def test_modified_seed_and_runtime_comparison_keep_context_and_native_authority_separate():
    comparison = dict(source=runtime(), current=None, state='unavailable', basis='executor_observation',
                      observed_at=None, expires_at=None)
    validate('RuntimeComparison', comparison)
    prepared = comparison | dict(current=runtime(), state='same', basis='prepared_bundle')
    validate('RuntimeComparison', prepared)
    for bad in [comparison | dict(state='same'), prepared | dict(current=None),
                prepared | dict(observed_at='2026-10-09T10:00:00Z'),
                comparison | dict(source=runtime() | dict(host_path='/private/store')),
                comparison | dict(observed_at=42)]:
        with pytest.raises(ValidationError):
            validate('RuntimeComparison', bad)
    historical = dict(kind='source_run', source_run_id=uid(10), source_configuration_digest=SHA,
                      observed_study_revision='r1', choice_confirmed=False)
    validate('ConfigurationRequest2', request() | dict(context_source=historical,
        derivation=dict(source_run_id=uid(10), source_configuration_digest=SHA)))
    # False is a valid unsaved seed choice; preview/commit semantics reject it later.
    with pytest.raises(ValidationError):
        validate('ContextSource', historical | dict(description='forged historic context'))


def test_export_selection_and_limits_reject_duplicate_ids_bools_and_oversize_values():
    validate('RecordPreviewRequest', dict(command_id=uid(1), selected_run_ids=[uid(2)]))
    for ids in ([], [uid(2), uid(2)], [uid(i) for i in range(17)]):
        with pytest.raises(ValidationError):
            validate('RecordPreviewRequest', dict(command_id=uid(1), selected_run_ids=ids))
    validate('ExportLimits', limits())
    for key in limits():
        for value in (True, -1, limits()[key] + 1):
            with pytest.raises(ValidationError):
                validate('ExportLimits', limits() | {key: value})


def test_record_request_download_requires_ready_create_and_failed_requires_error():
    queued = dict(schema_version='1', request_id=uid(1), kind='preview', state='queued',
                  selected_run_ids=[uid(2)], preview=None, error=None, download=None)
    validate('RecordRequest', queued)
    ready = queued | dict(kind='create', state='ready', download=dict(sha256=SHA, size=512))
    validate('RecordRequest', ready)
    for bad in [queued | dict(state='ready'), ready | dict(kind='preview'),
                queued | dict(download=ready['download']), queued | dict(state='failed')]:
        with pytest.raises(ValidationError):
            validate('RecordRequest', bad)


def test_derived_configuration_commit_cannot_mutate_source_family():
    derived = request() | dict(derivation=dict(source_run_id=uid(10), source_configuration_digest=SHA))
    body = dict(command_id=uid(90), expected_revision=None, configuration_id=None,
                configuration=derived, expected_preview_digest=SHA)
    validate('ConfigurationCommit2', body)
    for update in [dict(configuration_id=uid(40)), dict(expected_revision='r1')]:
        with pytest.raises(ValidationError):
            validate('ConfigurationCommit2', body | update)


def test_computational_manifest_closes_paths_and_derivation_roles():
    mapping = dict(run_id=uid(1), configuration_revision_id=uid(2), model_revision_id=uid(3),
                   role='selected', process_uuid=uid(4), bundle_digest=SHA, configuration_digest=SHA, results_digest=SHA)
    payload = dict(path='computations.aiida', role='native_archive', size=512, sha256=SHA)
    value = dict(schema_version='1', kind='hyprn-mvp-computational-record', origin_store_uuid=uid(5),
                 selected_run_ids=[uid(1)], computational_run_ids=[uid(1)], derivation_context_run_ids=[],
                 runs=[mapping], inventory=[payload], native_inventory_digest=SHA, omissions=[],
                 classification='inspection_only', reexecution_prerequisites=dict(retained_material_complete=True,
                 runtime_portability='unverified'), limits=limits(), manifest_digest=SHA)
    validate('ComputationalRecordManifest1', value)
    validate('RunMapping', mapping | dict(role='derivation_context_only', process_uuid=None, bundle_digest=None, results_digest=None))
    with pytest.raises(ValidationError):
        validate('RunMapping', mapping | dict(role='derivation_context_only'))
    for path in ('/absolute', '../escape', 'a/../escape', 'a\\b', 'a//b', './a', 'a/' * 32 + 'b'):
        with pytest.raises(ValidationError):
            validate('PayloadFile', payload | dict(path=path))
    for update in [dict(native_pk=4), dict(schema_version='99'), dict(classification='executable'),
                   dict(inventory=[payload | dict(size=16777217)])]:
        with pytest.raises(ValidationError):
            validate('ComputationalRecordManifest1', value | update)


def test_archive_bridge_inventory_is_closed_and_size_bounded():
    value = dict(schema_version='1', origin_store_uuid=uid(1),
        inventory=dict(nodes=[dict(uuid=uid(2), node_type='data.core.dict.Dict.', attributes_digest=SHA,
            extras_digest=SHA, label='results', description='Sizing')], links=[], computers=[], users=[], repositories=[], omissions=[]),
        inventory_digest=SHA, archive_sha256=SHA, archive_size=3, archive_base64='YWJj')
    validate('ArchiveRecordResponse1', value)
    for update in [dict(archive_size=16777217), dict(archive_size=True), dict(archive_base64='not base64!'),
                   dict(inventory=value['inventory'] | dict(authinfos=[]))]:
        with pytest.raises(ValidationError):
            validate('ArchiveRecordResponse1', value | update)


def test_every_new_object_is_closed_and_references_are_local():
    def visit(value):
        if isinstance(value, dict):
            if value.get('type') == 'object':
                assert value.get('additionalProperties') is False
            if '$ref' in value:
                assert value['$ref'].startswith('#/$defs/')
                assert value['$ref'].split('/')[-1] in DEFS
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)
    for name in ('ConfigurationRequest2', 'ConfigurationCandidate2', 'ConfigurationRevision2',
                 'ModelingConfiguration2', 'ModelingConfigurationRevision2', 'ExecutionBundle3',
                 'NativeSource', 'ScalarMapping', 'RecordRequest', 'NativeInventory', 'ComputationalRecordManifest1'):
        visit(DEFS[name])


def test_public_preview_and_receipt_accept_current_prior_run_context():
    schemas = json.loads((ROOT / 'contracts/hyprn-mvp.openapi.yaml').read_text())['components'][
        'schemas'
    ]
    # New configurations preview only version 6 (no criteria, no approach binding).
    assert schemas['PublicConfigurationPreview'] == {
        '$ref': '#/components/schemas/ConfigurationPreview8'
    }
    assert {'$ref': '#/components/schemas/ApproachCommandResult3'} in schemas[
        'ApproachCommandResultRead2'
    ]['anyOf']
