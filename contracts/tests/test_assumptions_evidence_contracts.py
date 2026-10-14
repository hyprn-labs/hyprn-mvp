"""AE wire contracts only; relational authority is enforced by tasks 11/12.

JSON Schema cannot compare sibling IDs or resolve an owner against a model.
The explicit semantic counterexamples below must reach those later validators;
acceptance here is deliberately not a claim of domain or worker acceptance.
"""
from hyprn_mvp_app.contracts import authored_schema
from test_schema_sources import assert_execution_schema
import copy
import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker, ValidationError
from test_reuse_contract import uid, request, candidate, revision

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = authored_schema()
D = SCHEMA['$defs']
VERSIONS = {'ModelDraft2':'2', 'ModelRevision2':'2', 'ModelPackage2':'2',
    'Preview2':'2', 'Apply2':'2', 'ConfigurationRequest3':'3',
    'ConfigurationCandidate3':'3', 'ConfigurationRevision3':'3',
    'ConfigurationPreview3':'3', 'ModelingConfiguration3':'3',
    'ModelingConfigurationRevision3':'3', 'ModifiedRunSeed2':'2', 'ExecutionBundle4':'4'}


def validate(name, value):
    Draft202012Validator({**SCHEMA, '$ref':'#/$defs/' + name}, format_checker=FormatChecker()).validate(value)


def sample(s):
    if '$ref' in s:
        return sample(D[s['$ref'].split('/')[-1]])
    if 'const' in s:
        return s['const']
    if 'enum' in s:
        return s['enum'][0]
    kind = s.get('type')
    if kind == 'object':
        return {k:sample(s['properties'][k]) for k in s['required']}
    if 'oneOf' in s or 'anyOf' in s:
        branches = s.get('oneOf', s.get('anyOf'))
        return sample(next((b for b in branches if b.get('type') == 'null'), branches[0]))
    if kind == 'array':
        return [sample(s['items']) for _ in range(s.get('minItems', 0))]
    if kind == 'null': return None
    if kind == 'boolean': return False
    if kind in ('integer', 'number'): return s.get('minimum', 0)
    if s.get('format') == 'uuid': return uid(1)
    if s.get('format') == 'date-time': return '2026-10-10T09:00:00Z'
    if s.get('pattern') == '^[0-9a-f]{64}$': return 'a' * 64
    if s.get('pattern') == '^sha256:[0-9a-f]{64}$': return 'sha256:' + 'a' * 64
    return 'x'


def assumption(**updates):
    return dict(assumption_id=uid(1), statement='Steady flow', evidence_links=[], **updates)


@pytest.mark.parametrize('name', list(VERSIONS))
def test_versions_closed_required_and_string_discriminators(name):
    s = D[name]
    assert s['properties']['schema_version'] == {'enum':[VERSIONS[name]]}
    value = sample(s)
    if name == 'ExecutionBundle4':
        from test_native_program_contract import fixture, bundle
        artifact, files = fixture()
        value = bundle(artifact, files) | dict(schema_version='4', modeling_configuration_digest='b'*64,
            result_dependencies=dict(path='result-dependencies.json', sha256='a'*64, size=48))
        value['files'] += [dict(path=p, role=r, sha256='a'*64, size=48, media_type='application/json') for p,r in [
            ('configuration.json','configuration'), ('modeling-configuration.json','modeling_configuration'),
            ('result-dependencies.json','result_dependencies')]]
    if name == 'ModifiedRunSeed2':
        value['runtime_comparison'].update(state='unavailable', current=None)
    validate(name, value)
    for field in s['required']:
        invalid = copy.deepcopy(value)
        del invalid[field]
        with pytest.raises(ValidationError): validate(name, invalid)
    for version in (None, '', int(VERSIONS[name]), '99'):
        with pytest.raises(ValidationError): validate(name, value | {'schema_version':version})
    with pytest.raises(ValidationError): validate(name, value | {'extra':True})


@pytest.mark.parametrize('name', ['EvidenceCreate3','EvidenceRevise3','EvidenceRecord3','EvidenceSnapshot3',
    'EvidenceFamily3','ConfigurationCommit3','AssumptionEvidenceResolution1','RecordedEvidenceContext1'])
def test_new_wire_records_are_closed_and_required(name):
    value = sample(D[name])
    # Resolution selects an exact committed model, with no draft selector.
    if name == 'AssumptionEvidenceResolution1': value.update(draft_revision=None, model_revision_id=uid(1), model_digest='a'*64)
    validate(name, value)
    with pytest.raises(ValidationError): validate(name, value | {'unexpected':1})
    for field in D[name]['required']:
        bad = copy.deepcopy(value); del bad[field]
        with pytest.raises(ValidationError): validate(name, bad)


def test_link_identity_relations_and_owners():
    link = dict(evidence_version_id=uid(2), relation='supports')
    for relation in ('supports','challenges','context'):
        validate('AssumptionEvidenceLink', link | {'relation':relation})
    for bad in (link | {'relation':'validates'}, link | {'title':'forged'},
                link | {'evidence_version_id':uid(2).upper().replace('0','A',1)}):
        with pytest.raises(ValidationError): validate('AssumptionEvidenceLink', bad)
    for owner in ({'kind':'model'}, {'kind':'instance','instance_id':uid(2)}):
        validate('ModelAssumption', assumption(owner=owner))
    for owner in ({'kind':'instance'}, {'kind':'definition','definition_id':uid(2)},
                  {'kind':'model','instance_id':uid(2)}, {'kind':'instance','instance_temp_key':'new'}):
        with pytest.raises(ValidationError): validate('ModelAssumption', assumption(owner=owner))
    value = assumption(); value['evidence_links'] = [link, link | {'relation':'challenges'}]
    validate('ConfigurationAssumption', value)
    value['evidence_links'] = [link, link]
    with pytest.raises(ValidationError): validate('ConfigurationAssumption', value)


@pytest.mark.parametrize('text', ['', ' \n\t', None, 'x'*4097], ids=['empty','blank','null','oversize'])
def test_blank_statement_and_content_rejected(text):
    with pytest.raises(ValidationError): validate('ConfigurationAssumption', assumption() | {'statement':text})
    record = sample(D['EvidenceCreate3'])
    with pytest.raises(ValidationError): validate('EvidenceCreate3', record | {'content':text})


def test_bounds_and_exact_snapshot_copy():
    record = sample(D['EvidenceRecord3'])
    record['parent_evidence_version_id'] = None
    validate('EvidenceSnapshot3', record)
    assert D['EvidenceSnapshot3'] == D['EvidenceRecord3']
    for title in ('', ' \n', None, 'x'*201):
        with pytest.raises(ValidationError): validate('EvidenceRecord3', record | {'title':title})
    for update in ({'source_refs':['x']*1001}, {'source_refs':['x'*4097]},
                   {'recorded_context':record['recorded_context'] | {'resource_labels':[sample(D['RecordedResourceLabel'])]*9}}):
        with pytest.raises(ValidationError): validate('EvidenceRecord3', record | update)
    v = assumption(); v['evidence_links'] = [dict(evidence_version_id=uid(i), relation='context') for i in range(65)]
    with pytest.raises(ValidationError): validate('ConfigurationAssumption', v)


def test_edit_owner_temporary_identity_is_add_only():
    add = dict(kind='add_assumption', temp_key='a', owner={'kind':'instance','instance_temp_key':'new'},
               statement='Steady flow', evidence_links=[])
    validate('Edit2', add)
    with pytest.raises(ValidationError): validate('Edit1', add)
    update = dict(kind='update_assumption', assumption_id=uid(1), statement='Transient flow', evidence_links=[])
    validate('Edit2', update)
    with pytest.raises(ValidationError): validate('Edit2', update | {'owner':{'kind':'model'}})
    validate('Edit2', dict(kind='remove_assumption', assumption_id=uid(1)))


def assumption_edit_result(created):
    draft = sample(D['ModelDraft2'])
    draft['assumptions'] = [assumption(owner={'kind':'model'})]
    return dict(data=draft, created_ids=created, diagnostics=[])


def validate_assumption_edit_and_receipt(created):
    result = assumption_edit_result(created)
    validate('ModelDraftEditResponse', dict(schema_version='1', request_id=uid(2), **result))
    validate('Receipt', dict(state='committed', command_id=uid(3),
                            payload_digest='a'*64, response=result, status=200))


def test_created_assumption_ids_roundtrip_edit_response_and_receipt():
    created = dict(assumption={'assumption_id':uid(1)}, instance={'instance_id':uid(2)},
                   connection={'connection_id':uid(3)},
                   definition=dict(definition_id=uid(4), definition_version_id=uid(5),
                                   ports={'out':uid(6)}))
    validate('CreatedIds', created)
    validate_assumption_edit_and_receipt(created)


@pytest.mark.parametrize('entry', [
    {}, {'assumption_id':None}, {'assumption_id':1}, {'assumption_id':'not-a-uuid'},
    {'assumption_id':'AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA'},
    {'assumption_id':uid(1)+'\n'},
    {'assumption_id':uid(1), 'extra':True},
    {'assumption_id':uid(1), 'instance_id':uid(2)},
    {'assumption_id':uid(1), 'connection_id':uid(2)},
    dict(assumption_id=uid(1), definition_id=uid(2), definition_version_id=uid(3), ports={}),
])
def test_created_assumption_ids_reject_malformed_extra_and_mixed_variants(entry):
    created = {'assumption':entry}
    result = assumption_edit_result(created)
    for name, value in [
        ('CreatedIds', created),
        ('ModelDraftEditResponse', dict(schema_version='1', request_id=uid(2), **result)),
        ('Receipt', dict(state='committed', command_id=uid(3), payload_digest='a'*64, response=result, status=200)),
    ]:
        with pytest.raises(ValidationError): validate(name, value)


def test_created_assumption_ids_preserve_temporary_key_and_map_bounds():
    entry = {'assumption_id':uid(1)}
    for created in ({'1invalid':entry}, {'a'*65:entry}, {f'a{i}':entry for i in range(257)}):
        with pytest.raises(ValidationError): validate('CreatedIds', created)
    validate('CreatedIds', {'a'*64:entry})


def test_configuration_new_closure_fields_and_private_separation():
    for name, old in [('ConfigurationRequest3',request()), ('ConfigurationCandidate3',candidate()),
                      ('ConfigurationRevision3',revision())]:
        old.pop('evidence_version_ids', None)
        value = old | dict(schema_version='3', assumptions=[assumption()], general_context_evidence_version_ids=[])
        validate(name, value)
        for change in ({'evidence_version_ids':[]}, {'assumptions':None}, {'assumptions':[assumption()]*1001},
                       {'general_context_evidence_version_ids':[uid(1),uid(1)]}):
            with pytest.raises(ValidationError): validate(name, value | change)
    private = sample(D['ModelingConfiguration3'])
    private['evidence_snapshots'] = [sample(D['EvidenceSnapshot3'])]
    validate('ModelingConfiguration3', private)
    for field in ('assumptions','general_context_evidence_version_ids','context_source','derivation'):
        with pytest.raises(ValidationError): validate('ModelingConfiguration3', private | {field:[]})
    with pytest.raises(ValidationError): validate('ModelingConfiguration2', private | {'schema_version':'2'})


def context_override(**updates):
    return dict(schema_version='1', description='Steady flow at the design point',
                boundary='Inlet to outlet', **updates)


@pytest.mark.parametrize('description,boundary', [('', ''), ('x'*4096, 'y'*4096),
    ('First paragraph.\n\nSecond paragraph.', 'Exact inherited boundary')])
def test_configuration_context_override_is_optional_and_preserves_explicit_text(description, boundary):
    value = sample(D['ConfigurationRequest3'])
    validate('ConfigurationRequest3', value)
    override = dict(schema_version='1', description=description, boundary=boundary)
    validate('ConfigurationContextOverride1', override)
    validate('ConfigurationRequest3', value | {'context_override':override})
    assert 'context_override' not in D['ConfigurationRequest3']['required']


@pytest.mark.parametrize('override', [None, '', [], {},
    {'schema_version':'1', 'description':'missing boundary'},
    {'schema_version':'1', 'boundary':'missing description'},
    {'description':'missing version', 'boundary':''},
    context_override() | {'schema_version':'2'}, context_override() | {'schema_version':1},
    context_override() | {'description':None}, context_override() | {'boundary':None},
    context_override() | {'description':1}, context_override() | {'boundary':False},
    context_override() | {'description':'x'*4097}, context_override() | {'boundary':'x'*4097},
    context_override() | {'notes':['Not owned by the override']},
    context_override() | {'unexpected':True}])
def test_configuration_context_override_rejects_invalid_closed_payloads(override):
    with pytest.raises(ValidationError): validate('ConfigurationContextOverride1', override)
    with pytest.raises(ValidationError):
        validate('ConfigurationRequest3', sample(D['ConfigurationRequest3']) | {'context_override':override})


@pytest.mark.parametrize('name', ['ConfigurationCandidate1', 'ConfigurationRequest2',
    'ConfigurationCandidate2', 'ConfigurationCandidate3', 'ConfigurationRevision1',
    'ConfigurationRevision2', 'ConfigurationRevision3', 'ModelingConfiguration2',
    'ModelingConfiguration3', 'ModelingConfigurationRevision2', 'ModelingConfigurationRevision3'])
def test_context_override_is_request3_only_never_an_immutable_or_private_field(name):
    value = sample(D[name])
    validate(name, value)
    with pytest.raises(ValidationError): validate(name, value | {'context_override':context_override()})


def test_relational_counterexamples_are_explicit_not_fake_schema_guarantees():
    model = sample(D['ModelRevision2'])
    first = assumption(owner={'kind':'instance','instance_id':uid(77)})
    model['assumptions'] = [first, first | {'statement':'Changed, same ID'}]
    # Both a dangling owner and a duplicate semantic ID require the model validator.
    validate('ModelRevision2', model)
    assert model['instances'] == []
    assert len({a['assumption_id'] for a in model['assumptions']}) == 1
    obligations = ' '.join(D['ModelRevision2']['x-hyprn-mvp-invariants'])
    assert 'assumption_id' in obligations and 'root_instance_id' in obligations
    assert 'closure' in ' '.join(D['ConfigurationRevision3']['x-hyprn-mvp-invariants'])
    assert 'projection' in ' '.join(D['ExecutionBundle4']['x-hyprn-mvp-invariants'])


def test_shared_definitions_mirror_and_local_references_resolve():
    assert_execution_schema()
    def visit(value):
        if isinstance(value, dict):
            if '$ref' in value: assert value['$ref'].removeprefix('#/$defs/') in D
            for item in value.values(): visit(item)
        elif isinstance(value, list):
            for item in value: visit(item)
    visit(D)
    Draft202012Validator.check_schema(SCHEMA)


def test_history_and_read_unions_have_one_matching_branch():
    for alias, names in [('ModelDraft',['ModelDraft1','ModelDraft2']),
                         ('ModelRevision',['ModelRevision1','ModelRevision2']),
                         ('ModelPackage',['ModelPackage1','ModelPackage2']),
                         ('EvidenceRecordRead',['EvidenceRecord1','EvidenceRecord2','EvidenceRecord3']),
                         ('RunHistory',['RunHistory1','RunHistory2'])]:
        for name in names:
            value = sample(D[name])
            validate(name, value)
            validate(alias, value)  # oneOf rejects both ambiguity and no match.
    history = sample(D['RunHistory2'])
    history['model_snapshot'] = sample(D['ModelRevision2'])
    history['configuration'] = sample(D['ConfigurationRevision3'])
    history['evidence'] = [sample(D['EvidenceSnapshot3'])]
    validate('RunHistory2', history)
    with pytest.raises(ValidationError): validate('RunHistory1', history)
    assert D['PreparedModelArtifact2'] == D['PreparedModelArtifact']
    assert D['PreparedModelArtifact2']['properties']['model_package_manifest'] == {'$ref':'#/$defs/ModelPackage'}
    assert D['ModelPackage1']['properties']['revisions']['items'] == {'$ref':'#/$defs/ModelRevision1'}


def test_legacy_config_and_seed_cannot_admit_new_nested_versions():
    for name in ('ConfigurationCandidate1','ConfigurationRevision1','ConfigurationCandidate2',
                 'ConfigurationRevision2','ModelingConfiguration2','ModelingConfigurationRevision2'):
        assert D[name]['properties']['evidence_snapshots']['items'] == {'$ref':'#/$defs/EvidenceSnapshotLegacy'}
        value = sample(D[name])
        value['evidence_snapshots'] = [sample(D['EvidenceSnapshot3'])]
        with pytest.raises(ValidationError): validate(name, value)
    assert D['ModifiedRunSeed1']['properties']['model_snapshot'] == {'$ref':'#/$defs/ModelRevision1'}


def test_resolution_selectors_and_cursor_bounds():
    result = sample(D['AssumptionEvidenceResolution1'])
    result.update(draft_revision='draft-1', model_revision_id=None, model_digest=None)
    validate('AssumptionEvidenceResolution1', result)
    for changes in ({'draft_revision':None}, {'model_revision_id':uid(1)}, {'model_digest':'a'*64}):
        with pytest.raises(ValidationError): validate('AssumptionEvidenceResolution1', result | changes)
    cursor = sample(D['EvidenceCursor1'])
    validate('EvidenceCursor1', cursor)
    for changes in ({'high_water':True}, {'last_rowid':-1}, {'view':'all'}, {'actor_id':None}, {'extra':1}):
        with pytest.raises(ValidationError): validate('EvidenceCursor1', cursor | changes)
    page = sample(D['EvidencePage1'])
    validate('EvidencePage1', page)
    with pytest.raises(ValidationError): validate('EvidencePage1', page | {'next_cursor':'x'*2049})


def test_private_requests_admit_only_projected3_with_unchanged_protocols():
    compatibility = dict(model_revision_id=uid(1), configuration_candidate=sample(D['ModelingConfiguration3']))
    validate('Compatibility', compatibility)
    with pytest.raises(ValidationError):
        validate('Compatibility', compatibility | {'configuration_candidate':sample(D['ConfigurationCandidate3'])})
    prepare = dict(command_id=uid(2),model_revision_id=uid(1),configuration_digest='a'*64,
                   configuration_snapshot=sample(D['ModelingConfigurationRevision3']))
    validate('Prepare', prepare)
    with pytest.raises(ValidationError):
        validate('Prepare', prepare | {'configuration_snapshot':sample(D['ConfigurationRevision3'])})
    versions = sample(D['ExecutionVersions'])
    versions['bundle_versions'] = ['2','3','4']
    validate('ExecutionVersions', versions)
    assert versions['artifact_versions'] == ['2']
    assert versions['program_protocols'] == ['hyprn_mvp.openmdao.program/1']
