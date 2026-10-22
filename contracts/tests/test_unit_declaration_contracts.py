"""Closed wire contracts; no runtime, engine, candidate import or live storage.

Bundle files are separately encoded bytes: pairing tests validate their declared
concrete schemas, not a claim that future launcher/worker admission is delivered.
"""
from hyprn_mvp_app.contracts import authored_schema
from test_schema_sources import assert_execution_schema, case_removal_digests
import copy
import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker, ValidationError
from test_approach_contracts import sample, valid as previous_sample

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = authored_schema()
D = SCHEMA['$defs']
PHYSICAL = [
    'm',
    'km',
    'cm',
    'mm',
    's',
    'min',
    'h',
    'kg',
    'g',
    'N',
    'Pa',
    'kPa',
    'MPa',
    'K',
    'degC',
    'degF',
    'rad',
    'deg',
    'm/s',
    'km/h',
    'J/kg',
    'kJ/kg',
    'MJ/kg',
    'kg/m**3',
    'g/cm**3',
    'm**2',
    'cm**2',
    'mm**2',
    'm**3',
    'cm**3',
    'mm**3',
    'kg/m**2',
    'g/m**2',
    '1/m**2',
    'J/(kg*K)',
    'kJ/(kg*K)',
    'J',
    'kJ',
    'MJ',
    'W',
    'kW',
    'MW',
    'm**3/s',
    'kg/s',
    'm/s**2',
    'N*m',
    'W/(m*K)',
    'W/(m**2*K)',
]
NEW_OBJECTS = [
    'PortDeclaration3',
    'Port3',
    'Definition3',
    'ModelDraft3',
    'ModelRevision3',
    'ModelPackage3',
    'Create3',
    'Preview3',
    'Apply3',
    'FrozenConfiguration5',
    'ExecutionBundle6',
    'RunHistory4',
    'ModifiedRunSeed4',
    'UnitCatalog1',
    'UnitCatalogResponse1',
]
PINNED = ['ModelPackage2', 'ModifiedRunSeed2', 'RunHistory2',
          'FrozenConfigurationLegacy', 'FrozenConfiguration4', 'RunHistory3',
          'ModifiedRunSeed3']


def validate(name, value):
    Draft202012Validator({**SCHEMA, '$ref': '#/$defs/' + name},
                         format_checker=FormatChecker()).validate(value)


def object_schema(name):
    schema = D[name]
    return D[schema["oneOf"][0]["$ref"].split("/")[-1]] if name in ("FrozenConfiguration5", "RunHistory4", "ModifiedRunSeed4", "ExecutionBundle6") else schema


def valid(name):
    value = sample(D[name])
    if name in ('ModelDraft3', 'ModelRevision3', 'ModelPackage3', 'ExecutionBundle6'):
        value['required_capabilities'] = ['unit_declarations/1']
    if name == 'ExecutionBundle6':
        value = previous_sample('ExecutionBundle5')
        value.update(schema_version='6', required_capabilities=['flat_explicit_scalar', 'unit_declarations/1'])
    if name == 'ModifiedRunSeed4':
        value['runtime_comparison'].update(state='unavailable', current=None)
        value['model_snapshot'] = valid('ModelRevision3')
    if name == 'FrozenConfiguration5':
        value['model_snapshot'] = valid('ModelRevision3')
    if name == 'UnitCatalog1': value['supported_units'] = PHYSICAL
    if name == 'UnitCatalogResponse1': value['data'] = valid('UnitCatalog1')
    return value


@pytest.mark.parametrize('name', NEW_OBJECTS)
def test_new_objects_are_closed_and_required(name):
    value = valid(name)
    validate(name, value)
    with pytest.raises(ValidationError): validate(name, value | {'unknown': True})
    for field in object_schema(name)['required']:
        bad = copy.deepcopy(value); del bad[field]
        with pytest.raises(ValidationError): validate(name, bad)


@pytest.mark.parametrize('value', [{}, None, '', {'kind': 'physical'},
    {'kind': 'physical', 'expression': ''}, {'kind': 'physical', 'expression': 'x'*65},
    {'kind': 'physical', 'expression': 'USD'}, {'kind': 'economic', 'currency_code': 'EUR'},
    {'kind': 'dimensionless', 'expression': ''}, {'kind': 'unspecified', 'extra': True},
    {'kind': 'physical', 'expression': 'm;import os'}, {'kind': 'physical', 'expression': ' m'}])
def test_declaration_rejects_malformed_unknown_and_currency(value):
    with pytest.raises(ValidationError): validate('UnitDeclaration1', value)


def test_all_physical_spellings_and_explicit_intents():
    for value in [{'kind': 'unspecified'}, {'kind': 'dimensionless'}] + [
            {'kind': 'physical', 'expression': s} for s in PHYSICAL]:
        validate('UnitDeclaration1', value)
        for name in ('Port3', 'PortDeclaration3'):
            validate(name, valid(name) | {'units': value})
    for name in ('Port', 'PortDeclaration'):
        validate(name, sample(D[name]) | {'units': ''})
        with pytest.raises(ValidationError): validate(name, sample(D[name]) | {'units': {'kind': 'dimensionless'}})


@pytest.mark.parametrize('name', ['ModelDraft3', 'ModelRevision3'])
def test_nested_ports_are_typed_and_unreferenced_unspecified_is_structural(name):
    model = valid(name)
    model['ports'] = [valid('Port3')]
    definition = valid('Definition3'); definition['ports'] = [valid('Port3')]
    model['definitions'] = [definition]
    validate(name, model)
    for location in [('ports',), ('definitions', 0, 'ports')]:
        bad = copy.deepcopy(model); node = bad
        for part in location: node = node[part]
        node[0]['units'] = {'kind': 'physical', 'expression': ''}
        with pytest.raises(ValidationError): validate(name, bad)
    with pytest.raises(ValidationError): validate(name, model | {'required_capabilities': []})


def test_new_edits_replace_all_port_branches_without_ambiguous_oneof():
    branches = D['Edit3']['oneOf']
    kinds = [b['properties']['kind']['enum'][0] for b in branches]
    assert len(kinds) == len(set(kinds)) == 14
    for branch in branches:
        edit = sample(branch)
        if edit['kind'] == 'create_definition': edit['ports'] = [valid('PortDeclaration3')]
        if edit['kind'] == 'revise_definition':
            edit['changes'] = [sample(b) for b in D['DefinitionChange3']['oneOf']]
        validate('Edit3', edit)
        validate('Edit', edit)
        for wrapper in ('Preview3', 'Apply3'):
            validate(wrapper, valid(wrapper) | {'edits': [edit]})
    for branch in D['DefinitionChange3']['oneOf']:
        change = sample(branch)
        if change['kind'] == 'update_port': change['fields']['units'] = {'kind': 'unspecified'}
        validate('DefinitionChange3', change)
        if change['kind'] in ('create_port', 'update_port'):
            bad = copy.deepcopy(change)
            (bad['fields'] if change['kind'] == 'update_port' else bad)['units'] = ''
            with pytest.raises(ValidationError): validate('DefinitionChange3', bad)
    edit = sample(branches[0]); edit['ports'] = [valid('PortDeclaration3')]
    for version in (1, 2):
        for wrapper in ('Preview', 'Apply'):
            with pytest.raises(ValidationError): validate(wrapper+str(version), sample(D[wrapper+str(version)]) | {'edits': [edit]})


def test_package_ancestry_and_historical_readers_are_exact():
    model = valid('ModelRevision3')
    package = valid('ModelPackage3')
    package['revisions'] = [sample(D['ModelRevision1']), sample(D['ModelRevision2']), model]
    validate('ModelPackage3', package)
    validate('ModelPackage', package)
    for version in (1, 2):
        with pytest.raises(ValidationError): validate('ModelPackage'+str(version), sample(D['ModelPackage'+str(version)]) | {'revisions': [model]})
    for name in ('FrozenConfigurationLegacy', 'FrozenConfiguration4', 'RunHistory1',
                 'RunHistory2', 'RunHistory3', 'ModifiedRunSeed1', 'ModifiedRunSeed2', 'ModifiedRunSeed3'):
        value = previous_sample(name)
        # Verify valid original payload before substituting only the nested model.
        if name in ('ModifiedRunSeed1', 'ModifiedRunSeed2'): value['runtime_comparison'].update(state='unavailable', current=None)
        validate(name, value)
        with pytest.raises(ValidationError): validate(name, value | {'model_snapshot': model})


def test_exact_new_frozen_history_seed_pairings_and_partial_history():
    for name in ('FrozenConfiguration5', 'RunHistory4', 'ModifiedRunSeed4'):
        value = valid(name); value['model_snapshot'] = valid('ModelRevision3')
        validate(name, value)
        for version in (1, 2):
            with pytest.raises(ValidationError): validate(name, value | {'model_snapshot': sample(D['ModelRevision'+str(version)])})
        for version in (1, 2, 3):
            field_type = 'ConfigurationRequest' if name == 'ModifiedRunSeed4' else 'ConfigurationRevision'
            if field_type+str(version) in D:
                with pytest.raises(ValidationError): validate(name, value | {'configuration': sample(D[field_type+str(version)])})
    history = valid('RunHistory4')
    validate('RunHistory4', history)  # Existing truthful null/partial semantics.
    bundle = sample(object_schema('RunHistory4')['properties']['bundle']['anyOf'][0])
    validate('RunHistory4', history | {'bundle': bundle})
    for version in ('2', '3', '4', '5'):
        with pytest.raises(ValidationError): validate('RunHistory4', history | {'bundle': bundle | {'schema_version': version}})


def test_bundle6_requires_capability_and_old_bundle_discriminators_stay_closed():
    value = valid('ExecutionBundle6'); validate('ExecutionBundle', value)
    with pytest.raises(ValidationError): validate('ExecutionBundle6', value | {'required_capabilities': []})
    for version in (2, 3, 4, 5):
        with pytest.raises(ValidationError): validate('ExecutionBundle'+str(version), value)
    metadata = D['ExecutionBundle6']['x-hyprn-mvp-file-schemas']['oneOf']
    assert [b['files']['model.json'] for b in metadata] == [
        '#/$defs/ModelRevision3', '#/$defs/ModelRevision2']
    assert [b['required_capabilities'] for b in metadata] == [
        ['flat_explicit_scalar', 'unit_declarations/1'], ['flat_explicit_scalar']]



def test_old_approach_closure_cannot_indirectly_acquire_model3():
    closure = sample(D['ApproachClosure1']); closure['models'] = [valid('ModelRevision3')]
    validate('ApproachClosure1', closure)
    with pytest.raises(ValidationError): validate('ApproachClosurePreUnits', closure)
    for name in ('FrozenConfiguration4', 'RunHistory3', 'ModifiedRunSeed3'):
        value = previous_sample(name); value['approach_closure'] = closure
        if name == 'FrozenConfiguration4': value['configuration']['approach_binding'] = sample(D['ApproachBinding1'])
        if name == 'ModifiedRunSeed3': value['source_configuration']['approach_binding'] = sample(D['ApproachBinding1'])
        with pytest.raises(ValidationError): validate(name, value)


def test_catalog_bounds_endpoint_and_capability_declaration():
    catalog = valid('UnitCatalog1'); validate('UnitCatalog1', catalog)
    for field, value in [('supported_units', PHYSICAL[:-1]), ('supported_units', PHYSICAL+['USD']),
                         ('supported_units', PHYSICAL[:-1]+[PHYSICAL[0]]), ('affine_conversion', True),
                         ('engine_version', 'latest'), ('engine_source_sha256', 'bad')]:
        with pytest.raises(ValidationError): validate('UnitCatalog1', catalog | {field: value})
    api = json.loads((ROOT / 'contracts/modeling.openapi.yaml').read_text())
    endpoint = api['paths']['/unit-catalog']['get']
    assert endpoint['responses']['200']['content']['application/json']['schema']['$ref'].endswith('/UnitCatalogResponse1')
    assert endpoint['x-hyprn-mvp-max-response-bytes'] == 16384
    assert api['security'] == [{'scopedBearer': []}]
    assert api['x-hyprn-mvp-protocol-matrix']['required_capabilities']['unit_declarations'] == '1'
    assert api['paths']['/models']['post']['requestBody']['content']['application/json']['schema']['$ref'].endswith('/CreateRequest')


def test_schema_mirrors_and_all_local_references_resolve():
    other = authored_schema()
    assert_execution_schema()
    for schema in (SCHEMA, other):
        Draft202012Validator.check_schema(schema)
    def walk(node):
        if isinstance(node, dict):
            if '$ref' in node:
                assert node['$ref'].startswith('#/$defs/')
                assert node['$ref'].split('/')[-1] in D
            for value in node.values(): walk(value)
        elif isinstance(node, list):
            for value in node: walk(value)
    walk(D)


# Original hashes are populated once from the source captured before unit declarations, never from
# implemented schemas. Pinning is reversed ONLY for the enumerated ref rewrites.
ORIGINAL_HASHES = {
  "Source": "ced46ca6ae852ed5a1d751eac61c8b2eb5598219ad26fdd9ef29b5f67b4bb82f",
  "PortDeclaration": "56ab596fd71b2bc1585635981ec3d3d568ef128e1ccd6a5de51cebce35e4ec63",
  "Port": "49b80078c779dd026d52c4bd53dacbc22d4c0749b47c2ce962ed604332925aa3",
  "PortRef": "74ce0d29a65d8ae2a6b759ce74c60657137af3516b3ab9336610da8bf9073c75",
  "BatchPortRef": "e2beca074f11dab9ba8f46b70e85c8d81a326ef7349ebb708ef8d3c033f93667",
  "VersionRef": "3f0ce608e3f5271ee7d275bc88a7fc138d4f45da1083f1aae9e295c0062907e0",
  "Annotation": "74b3a8f1a880bd127c6ba1111dee20ba2ff94c07c482d41b8475fc38e9af1d8d",
  "BoundaryMapping": "e47b848352c27df7e23871978c4d172331d82a80df3e0762eaece87a7eb84f98",
  "Instance": "89205571745483f8589bf60e3934a82f89c4c1eec67ea2cd533ed97f5bb8313e",
  "Connection": "6bc9927a5919411a388d0b15588db9ad24041489f95c17b98436006ddde60ea7",
  "Definition": "e5d387b44f62e09b89b8646605d97082de8b2eb9d6eec77a9d50f5b4cf5fe865",
  "DefinitionChange": "9f8f3cee850e038b9f1e2d86c31a851d62dd9459199bbdc32a71301c7f010313",
  "Edit1": "465edcdf3c343288888f103b0da68e262f2dfb18d4c48d7def75c94e991a3586",
  "ModelDraft1": "8c55ff429d90b1040e0261dd4e9e11cbed58b932733edd537d622f366779b34d",
  "ModelRevision1": "acc65cb1e1c564e854c9e0b5d4b625c490644500bfdf0027f6d57a11cb5870da",
  "File": "aa4e89b13803233cae94b4f45ca642c343fdf513315ad54829ca91ae810d5d0b",
  "Generator": "ca5d842610ff173ed82f35029d6e11222e0329c5d880dc9dce52b6f21c987f82",
  "ModelPackage1": "9a4320db766612b22f0ced8dfa5665c90ed5c8da196b5db7635aecddb7a3df76",
  "Scaling": "508e9b6b2cdad53acf16b9710b584965172b6614e5ec7db2bb58d774cdb54bd7",
  "Numerical": "d4d8aa9cb6d742747d5480c6ef3bf83e223aa6228a80726b4f73e05a04361fe7",
  "Input": "a7218e38addee8bcf308b9f15fac0685de8228a0da952e9b3d419bd75d83a0b7",
  "Criterion": "cc48ccaa2550b6d2c2d0420577530641d6f032addec69ef4ccf0afebea297882",
  "EvidenceSnapshotLegacy": "539ed60f2255d146000fad995acfc565a4a04e7be7a97d37b52e57c9968741b3",
  "ConfigurationCandidate": "1aeff97303821c30d95fb56277bd73a610dbd89042089307dab49e59560aef30",
  "ConfigurationRevision": "5c0bbf520c2d73f760d435bdc1bee766ab54fa516afe7534071c55a632e61633",
  "Diagnostic": "de493804cade9a2728706278478ca78078245a2cd178fbc95bfde9a54a03553f",
  "CompatibilityResult": "f7e00da28291749f1acd0058d4342615b8d8dde7b254feb3e79d7c0694d8ad6b",
  "PreparedModelArtifact": "1f82dddac0da126c1a4bda1469f02ec35da21d76522d7e8b2c5a22da394dc73e",
  "Error": "382da9d27bdbb3394eb1e3ff666cbca937ba9626f7ba3ab04bbf542bbd5c71e1",
  "Create": "733f7f91911df862c1719969dec94cc581a38fd46187656d4cb5b00362d7925c",
  "Apply1": "2ea2639223534cd50e01babbc0e4b5c47bb9d65fe7d81fd85ca885959cd4550d",
  "Preview1": "52b97f395c14717f88fb25661c50d24895e4e6307115e8e651f3fddbd85ccf35",
  "Commit": "fb87a86960aa031383d48563553a1f8be3355ffb2e6489ff1dafb5cc64ff15ed",
  "Validate": "daf34219969c877d74826fbe2b41a0b0d38d20e66990923f3219fba4681f4248",
  "Compatibility": "73cfee3f47f30a20e8a5ff605ac5db73d278ef858507b6022ba455d39137a995",
  "Prepare": "8bc2b11e3b90636eb6869b46e98d0541e1ac84598d5860c1e2f91b2bc26d0e3b",
  "Import": "91c1c4967a6035c5d85bc6b5c9bade60355f025a0ed23cb3a3aadde8f8cba31c",
  "ByteFile": "8a76ba323d5b67529ea0e525a1704194d559737bcfe221b0a2532127aacf58e2",
  "CreatedIds": "608bb1107a10a388a914495b1de57ea39dc839ae437dab6b50f03156d80ab851",
  "ValidationResult": "3f3cfd2f47c00766fd7feccb796178b83179b25438b9f306fa73f173a7b1e056",
  "Capabilities": "0fa51e265c30665074cd3574f28800f70a4743f409a2ded405be24ff14985ab7",
  "CapabilitiesResponse": "0cb052678f6a7b1df7b18f5e127d6e35003f51618e1f88969f789956d880ea0e",
  "ModelDraftResponse": "7d1804f64ee2a7101688c03e15387e1a107121354527367c8b7fff76b99c1b95",
  "ModelDraftEditResponse": "cd2e1d443d24a8a4ff87c72a9875a76f583163ab7326a7a64f6b2a8edba59192",
  "ModelRevisionResponse": "e4a668266e58c4221d0823c4fb662f650f6718272b7e158e50b6238d471716e6",
  "ValidationResultResponse": "3358c31c8863407f54bd5768e9baf8e641ea05af6a030edd45ed6ba51f4300c6",
  "ModelPackageResponse": "f087cad877e098dc45be64105b9e398c6ab88158a63f40584625d6d45b524778",
  "CompatibilityResultResponse": "d547d4132a9d84ed2ea7703e929998cd15b4800f78997ae66e4cf0ca3a781592",
  "PreparedModelArtifactResponse": "bc90ca8a58621fffdc48a7cc4891aa7de3cf09def1adc75005f141146f2103a4",
  "ByteFileResponse": "65dc65b072de2311a0b6b82169782f4e834f23c26c02c2eb97ef82bb44ef26c8",
  "Receipt": "c757621ce3e2d87b5d2861ade2d328faa699b674314b481ea95e24111e909f8c",
  "ReceiptResponse": "a984cc465a8eb8500f4e7f4240038911afeb9cfbada34c1d0acb454fe89483bb",
  "ProgramEntrypoint": "936929ec4455acff3c69a523c47690644a9dbdc26139e31057273a3f36513d81",
  "ProgramBinding": "01105ccaf3b2edcb9de35c784628cd4336abe9817a9e035af1aa0623b9b00c80",
  "ProgramComponent": "b5fdb26e919c6882526d18c7de19ac9e9e7c55e094e01214ff182c7f23f9df31",
  "ProgramBindings": "2785e55f2630ffb93e74475abc1dbe07dc0306e76eb73c01df046438019d9c9f",
  "ProgramSourceMapEntry": "32be108cd98b45ce2f7d7997fb4e8c127b3cf7d692b7b798eea59b04b6503325",
  "ProgramSourceMap": "42a4760dacfac9da7dca2f65adb0ceb84dab8998acf952cfc47e4a6efdb57c32",
  "NativeGeneratorIdentity": "b628ceeaa63f2fadb67776e9bd3a79eaad0decf4d1160505d4bf78b22839dcb5",
  "ProgramProvenanceFile": "28dea0fc6c4270ae01286e47696f20f09e1af309030bfd1b64c332e7af8cc2f3",
  "ProgramProvenance": "322fff4704e7fd8231235b03c0d5ec598a78e71535634a14a89949e6f0e35fff",
  "PreparedFileV2": "934287a159468f37bce907650829bccffc67650820f2635f739f6c9d90266c8c",
  "BundleFileV2": "9cf600059917899f82aa8b11f9c37adff15a60be6f376111110f059422232750",
  "PreparedLicenseNotice": "f06a27c47b58aa7181b7a47ab3e4ef98cc3c768f0917948e329bc5fb63b54a1f",
  "BundleLicenseNotice": "a4f340d4f16a79e1ba5ea90c3d5ad726e3975d7277f9eed36fc774171f4b8a4c",
  "HistoricalPreparedModelArtifactV1": "d05671106fe4371ea5e370cc51ce91ecbd8e26f528f24ca9f6532d6e439ba8cb",
  "PreparedModelArtifactRead": "2304fe79566c1b37ec5a3a838debb00e132bc65459f80f058e7ddd0bfb08f2a2",
  "ExecutionBundle": "f9b4131e8abde2e40afdbbbb4417f140130cc5d1390dd5c78f72b696ad143326",
  "HistoricalExecutionBundleV1": "fb2627608837dcf164cd6f3ff5adb007e827af1d0708445b753c6c9df9d2fe72",
  "ExecutionBundleRead": "9a11622df4993f1f44588ae62f610ba521f68aa272ca4ad693987cc2bd71b2e8",
  "ExecutionVersions": "f9e6891d33feef19426fa708f074822a80e26eab383e063087d83e083f94e1cb",
  "RevisionSummary": "d977a1ce2e8085551630b73c233f470f290bdeb81fc38518c83c996be28a68aa",
  "RevisionList": "0b85450182d206cb98129592759599a1c38abf2078353a25e76b5ac226420a98",
  "RevisionListResponse": "b0ece19323f97389d82b16cb8fa0128d2b844fefcb57fff6f0ae786cb54a3412",
  "EvidenceResourceRef1": "5a01c351aee60f0ae08464ac79668f2c1fa6afeb50e2f3a8337c717e23171f83",
  "EvidenceCreate1": "156e1a35a3f9fef55c4536ae44efc7dbdfca5113d6dd08542c4002bef9ac89cd",
  "EvidenceRecord1": "6c8ab1a9833f640967e4557d6479c23a851c941a70a7dcee5b8eb4cb8a9d40d8",
  "EvidenceCreate2": "a89c3402d427873e77322bd4a4b1deb2d16d2cbc438fda1ae3e40ba0a7f19242",
  "EvidenceRecord2": "a35f4cf01e93329de8461bead7deb77afdf3d466b58f7b1e9f7c3d9a701544fd",
  "EvidenceCreate": "df70832615f3deb2d81be59fdbd09a74fa94a4e169024e6e4f61d89b10993c15",
  "EvidenceRecord": "a045071d21f7c39dcc0c85aa7012976b762a75ff0f0f5cc82553e7e312293afb",
  "ConfigurationCandidate1": "64de96a5eb2bfa28c82bd948bb4831244dc46365d9449fc0d3364c0fef5c50ec",
  "ConfigurationRevision1": "16e407c82ac644e8d19c5947cf0786cc2ff70d55ebb3cbeee8bba43e1f0ed7fd",
  "ExecutionBundle2": "adc18ac80f58753bbe8c62a87ee4cb7feef74f2199032190f467cc40d04fb687",
  "LiteralRequest": "74ff8e10f6c02d4f68d5cf523329adf114ff960c393a8eb9dff7b7e9860f2274",
  "ResultRequest": "1a4de76cab2738576a66e813ecdc8ee270dbcd9a27745a7a3b7b5681305c94bd",
  "ContextSource": "ac419693eeebbe163cab40eb9068fc4f0472819c8672e95a666de22e12a6bd76",
  "DerivationRequest": "37070c919264e5491a7575954230e709310f362bd481d64c94688056f2c4882a",
  "ConfigurationRequest2": "bcf56d309488c4de12f61b046c673d646f95b40e5e50fbfd18d74d5161c55041",
  "UnitInterpretation": "2e6140156325d520bc604145b410037cd56c8c0cc4058a7deea3d585abd78604",
  "SourceLabels": "d92aa7bc5e24b0ea3f398ff798ac8d1680f6aa03e34b2865b5e8b11dadbd1b21",
  "ResultBinding": "40531f5ad0852b509944fe2df10745da884a9209ea5e406c3f54f83e22253112",
  "ResolvedInput2": "0ba1549ac3914a6a7b6526fedf000541593e51aafb7a40d4400f3b7e5196c85a",
  "Change": "40d4dd6a4cd2ef96719341a96756c9acdb408da7ff03600a41604600418bad97",
  "ChangeSummary": "08f06656c4f8bca8b11ffade2851b08756febf58859692d6508bcc3c6f9c87c9",
  "Derivation": "d9e2bca3bf0e0e9c49c2234e7664b3458b958934b13b8b99023704bc2dbdcfa3",
  "ModelingConfiguration2": "5fa2da16ca652516f663e83725365beb0ef7bf3b88dcd3378299f5867f25341e",
  "ModelingConfigurationRevision2": "16b96c1d913cd1ec945a5b8170a9e4b580c0d285d9b30632c7067e955a98a790",
  "ConfigurationCandidate2": "96ce1423ec8b8f7287ffa5c1268e6b2ebfa38096bfa27f80292b9fa15e29d763",
  "ConfigurationRevision2": "51c1001878b212c7c449516eaa9e1199dff57e89e45a50c8fb613a074f5fd966",
  "RuntimeComparison": "583a7f51e27ded351c3a78b31e78a1ed27d859f10c6b72c630c395ce46cbb31b",
  "ConfigurationPreview2": "7d17db370162a282f90d8be57b294568f71ec3e824ba2641b5035877f50b9f71",
  "ConfigurationCommit2": "66b0b7b1569b31ba3107510828709db001af7763bd37af303f0720a6b3ce76b6",
  "ModifiedRunSeed1": "97c4498c67a98e693815e67ecf0456fdeab4a06145d3630ff131e16036fecdaf",
  "NativeSource": "2e283b02a13a7a87d256a17ea2a376eea1218c7d8388ace7e0de24e5dc46f662",
  "ScalarMapping": "c37cc671abd32788d382554216af37fe68eee2b638b994ea12c24270fe4a251b",
  "ResultDependencies1": "030603bcb89621718a2c06991937769afe7c07794e971dc619f129108c08d821",
  "BundleFileV3": "b3b4ffdc7de249bc505537c47297b7b9c175e27645c2608444d1cce20651c954",
  "ExecutionBundle3": "137670a8922a147fa370ee21b7f7d6e05a8df7b02047af0093a65dae92ab0e8e",
  "ResultSource": "35c90ed39d74cdb45e01bbe40ea480c62fb179608a9198d9d7806f5a71565ae6",
  "ResultSourcePage": "1ff43c6b6c03217c3350d849694a398855429cee994ac3af8d69deb38896dae2",
  "RunLabel": "63ab57dc9351930733b5369cc04addc464fe0c0f409cdfb0b145ad18acff7daf",
  "ExportLimits": "ae895314b0ef098cf7e2b0986ebd93440b035d67a4a253c04857ca12acb2269a",
  "ReexecutionPrerequisites": "f81a698a240d2bd7b3a971c7432bf9acc7e830e24e3bf86070d43a6e05520315",
  "RecordPreview": "a5493c53f8c3bd086b79cb59cc36de197013ce1b847b9a6d624cffc4edd85450",
  "StoredError": "dc82fac09254d5825936901f8703a951342802b8e1180c7e9fb05dedc0c2762f",
  "RecordRequest": "3fe942f629601d1757b2c45dd2ebce8e42acf3319a82887541a4ccee7b009a6e",
  "RecordPreviewRequest": "cdde744e1667df8f8d9a3cf1862beeb5a710a9c9e9dbaf335dafd688f73af860",
  "RecordCreateRequest": "521e543185c785604edc089c26661bd0b4d1740823de676828363c1ebc4a938d",
  "ArchiveRun": "e3907e0c8ac12c51afb99cb88bc2765fe8f75a67f52d7ee22b70ec3c7e52b0cb",
  "ArchiveRecordRequest1": "b301026b0559c38f53e469261bd66067e0d96a5bed074987dd8c3cd8993c3bb5",
  "NodeInventory": "3b35278fef1261ce6084ef8be5a6a2207e5b0cf50ed12fd40dc161c7e9640a71",
  "LinkInventory": "eb45f8c3025bacc973b73cc2ca6a1642423f0c5fca4734518033af5ac530d9be",
  "EntityInventory": "9ebe15c36f4ab172da018cc8b85ef5a5c9ea6aec9868e63bb342214161c2cce0",
  "RepositoryInventory": "12c138b182d18c42fb5f685e3a1f746d3062e585b9c0188b7dd5dfc0e9b0624d",
  "NativeInventory": "4414b0f436a560a5991fdc7285804bb839db4f24eec996d12d8558e60390db35",
  "ArchiveRecordResponse1": "7f1e89e645b102334c001bed2cbe66fea1a909c0da7c9180dea240ed3fb957e9",
  "RunMapping": "0931ef8571b8826d7cd98e4eea9989a0515d63b5df0f387c037dcf835ff5e0fc",
  "PayloadFile": "ed9d09fd142c8b0f3918f9339c42db9836607003cb4397e816a246d3a26b68ea",
  "ComputationalRecordManifest1": "274d2a6ed5e8e7619c636643770245f108b54767e34c3b35d8de6d5d371ab404",
  "CompatibilityResult1": "fdfe2e46fc16b158fb3c24206fd4756e03c5928a784acbb275ecada247e29f13",
  "InputInterpretation2": "43935d26c2167bd395e42ebc0173738d1d86230ffa17ad5296c755ffd536638f",
  "CompatibilityResult2": "43b32e7d9b6b232d1b73e98eda5e694bb9f610aa2333a73e086e30afa92ec212",
  "Edit": "b2cca644389913a145b6f8af2f62bc1e0397d290878221ea349030ede5603033",
  "ModelDraft": "43ea0d43bbc72612383eb55e7091b25f3b5cb4152bf8e53e7c20f4b91479af6f",
  "ModelRevision": "a7ba7a3e15b0340d9a6461f1f65f581e26ab9ba730181dc00ae16e86130347ad",
  "ModelPackage": "fa428563a4720a6f548b8be2939f662691952bd2410eebea42a8ec6a44caa42e",
  "EvidenceSnapshot": "72f16cad3ee2fd6b7814cfa8a8eae943fde1e19b9747c6546aa8cac228a85259",
  "Apply": "c300aa43d16a6f50e82133102fe7a0ae577ee30a21f40183c2a2b9eb5167352c",
  "Preview": "64dbdac7910ae096981a9d4f351491473cd2581d774f1927bfbf4191bc122210",
  "EvidenceSnapshotRead": "72f16cad3ee2fd6b7814cfa8a8eae943fde1e19b9747c6546aa8cac228a85259",
  "AssumptionEvidenceLink": "7c78894ac5323f63b6883aab7f826706470c736c41d059523562575b9236b7f7",
  "AssumptionOwner": "cc6e28324e5889535ef81fea2d7f8b47026f286ba47ecb1ad1cf97ac80352b37",
  "AssumptionBatchOwner": "5e02ecc2e9a2186c01c2214d51935dd2740dc674152f1995860c66fa60417d15",
  "ConfigurationAssumption": "9df47d73221d1e7fe83f251f918ea61bafadb35d23af1da51297efc4bbcb329c",
  "ModelAssumption": "1689c86ae528cc28f164e12e1ef2fbce73c3fa4008646088dc94b442515e7320",
  "ModelDraft2": "df67fb67d1ec7c867f3e7b9700f7edff3c80c316dab50f1c2e58a5306431f2ff",
  "ModelRevision2": "0fc0f2ce72645664fd501c57aa48c201b8eb53704a19a7403e506d45b0d2ef1b",
  "ModelPackage2": "b9c9d443fa06092741a71639bd6c8353901db429c4489b1df68e84ea793c7636",
  "Edit2": "a48a09a8e089465a4594d65a84589dacc0dcb2269692f84893d83ac88544bdb2",
  "Preview2": "81d1af2530d0908f452481c2044a6103812b93c9c6ce029a46b29c5705b19d2f",
  "Apply2": "c971b06c5f86597eb0eff54b9e641bc72a2f070019e19a00d6540d6917fd3954",
  "RecordedResourceLabel": "2f1a1234d89899368a403b801c87d50a98889ae86cac2529c3bf55d16a0c0099",
  "RecordedEvidenceContext1": "34b563cfc72dd15f9674a0e29ada8ccb9de343b14b6d920736c0cbd84b3216c3",
  "EvidenceCreate3": "ca784df79430d9ec9af518d4b37e751a778211d1453f5cfb55ab537bd683c647",
  "EvidenceRecord3": "677aece7cce85ff4408b599daf8048716bb41330da64a33fba7db89e86db209d",
  "EvidenceRevise3": "dcc757743dcd0232d3ec34b076b26f53c6f6ca23e07bedfda892bf8a71cc2256",
  "EvidenceSnapshot3": "677aece7cce85ff4408b599daf8048716bb41330da64a33fba7db89e86db209d",
  "EvidenceRecordRead": "a045071d21f7c39dcc0c85aa7012976b762a75ff0f0f5cc82553e7e312293afb",
  "EvidenceFamily3": "401fc81e3bc3c65ffd95a918a02f708e991631f31f3d52b926a0a380182067f6",
  "AssumptionEvidenceResolutionLink": "3348b97366771e8a9bc949c829abf3aa32709aa3c939b511d28a092186051f9e",
  "AssumptionEvidenceResolution1": "fe946fd62b7e5a78a10e5b35fddb591dcf5a2582ec37dcbbcf6865533d48b83d",
  "ConfigurationContextOverride1": "a4ba24402a5dc941a94c438864337425e0e628227ee69f1b322e96895276555d",
  "ConfigurationRequest3": "cd744b3f1f086c7909a019564c077af9242ec367afb3c40e9a6ec8dcc5c9997e",
  "ConfigurationCandidate3": "bb0f5336d203398cf11295b09da161009713596c06e17f78a76af2b2db20924b",
  "ConfigurationRevision3": "3edd9b01d85918a4924ef05aeb48074997ec441b0626a0a7be8be853b745fa4d",
  "ModelingConfiguration3": "94e64fd2d34908f4651acd1b29acdf2a79151f034f3eaea22f15dfe78d533fb7",
  "ModelingConfigurationRevision3": "feadf4f58d91023d25d0ea723382a7ca9705f5925bcf0434c140ac84e356901e",
  "ConfigurationPreview3": "2b63d306847e24f00b8ce876bbf08acf8b2b3ec620194b159e0571fab62e5d04",
  "ConfigurationCommit3": "c2c8aa10f4eee0daaa14847d3c064fd86e7febfe0a0a8cf01773918a63ddecb7",
  "ModifiedRunSeed2": "f5994cc4c89d420d8b4b9628ead1a96f32196ad89d5da9240b45cc0b6997b3a6",
  "ModifiedRunSeed": "0ef0e4cbbcac143882211e00d5dc9dc76164a5e479891e681943d24105316b0d",
  "ExecutionBundle4": "33db999aa28dd4f8eb94a5036eb9a663eec57b478472eb6c596fa4b9b0361a88",
  "RetainedOutput": "eb3af0bae6132d8c9008ac4d1203a626e68c7e03ffc5906abe56d33a2e0b42b0",
  "RetainedResults": "8008eb3a4af63906fc2f4b6e31d36f319cfd454c70272b60f73ea82305ce4ad1",
  "HistoryArtifact": "9d0aea8766c93ef9986e3c100b50b82fa1a2dbd72f89de887e69a5be5d822bdf",
  "ConfigurationRevisionLegacyRead": "b149a3fc3b35f0b3358a7dd6342955b7f9899e4a353514e83dd576371dee417a",
  "RunHistory1": "c6be84203a17c76d8eb6a5196f76a2fa0e741b7d68d6dd87d225b02f9686896e",
  "RunHistory2": "ce9ed945959f76eb113604d82f857bcc6b0b8cace89eaf5938756bbcaac30d7d",
  "RunHistory": "efd584902c9fb3e886905848df0d9d3926792d8ce3e7d212ad9e273e7cb6c732",
  "PreparedModelArtifact2": "1f82dddac0da126c1a4bda1469f02ec35da21d76522d7e8b2c5a22da394dc73e",
  "EvidenceCursor1": "41d9b5db9cb57ed132f6c7a3847896c45d16b788bcce27898271c8000a5b201f",
  "EvidencePage1": "552b1afdfa14033d1c5a05979013e05242fb49da1ad37d65fd3b77a86f22add1",
  "ConfigurationCommit1": "e19899c1b7ab4110b0bbba2342b481a959bfefad88dc0338162c564f050bf099",
  "ApproachModelBinding1": "ba704016b0a4d6cc13e923f52c16cb736471664e37846a1d104602fce0522633",
  "ApproachElementRef1": "773a300084e2ab3ae213fcd41d20ba684b443e0c8936a753440ffff7b5087fed",
  "ApproachEvidenceLink1": "d4d1a8c1f16925e1360670f3a659c3d21eeae2065b6d6cb349fc28c8835fc58d",
  "ApproachAssumption1": "0763376c2420afe14aa27682369c6b3b2c9ee83dd2c5ea855f703477f4b832c6",
  "ApproachAssumptionOrigin1": "28593efaf6579a1e3bdf4381b11d0134d282a707a7f3c04e9898660fc0b24d09",
  "ApproachAssumptionRef1": "c419f94c254c2d2adf4e6db687dc451d2b4936f7d5975eb6b1b235075815f86e",
  "ApproachIntent1": "2db4a2d7a0eb6031032efdab42cb82298dfc580389b57ba3f5cd094a1d7788ef",
  "ApproachStep1": "12ad0840cf54b429733564662060d24e4d48c8d25a3b2044bcedb0a58286c69c",
  "ApproachCase1": "7ac2f72c0aa1f6b370fa440ccbf40be6bbbae709cd34e1a8189864ace8606f59",
  "ApproachBasisRef1": "3bbf7b8160c5ab0bd9d2c15259b2608459a6066262e8aac1318206af92177a16",
  "ApproachContent1": "d144a40f729299b2096ad046853587eec4466fccfebf3c339d109edfa2b9d288",
  "ApproachDraft1": "2d28b00daf35947b6a9df14777fa6a1b1fefaa0f404d339255991bf45f1e738f",
  "ApproachVersion1": "8ee8aff345d7facdd423fd8e9319d97f0f424d6aba252d6423ba3343975ec8c6",
  "ApproachVersionSummary1": "ce26352eee1fa8829f11da7c701b61661fff8c4d115e88138df2d662cccf48a4",
  "ApproachState1": "fda61b11df8d0a32ddcab412a7fbf74195cd7d3b186bf800b1e014ce8c7cf156",
  "ApproachSaved1": "82a61542c0142b4bc7981331506e93fd63977fa6251e0032a66ed08070fa9972",
  "ApproachPreviewRequest1": "d7bef8efa48efde2a28b1a86ab47400d99903d2ec87e596cbb5fa6bb31cf5963",
  "ApproachDraftWrite1": "642c82d720ba6d3bff26e649451a578684038100c48a9343ecce0c0c83e72ef2",
  "ApproachVersionSave1": "3d4b878d36368287a98fe47b4b0db854ce0674e9e1dfadbbda6443735ab68701",
  "ApproachVersionSaved1": "6e458e7c531d77f2fc1d5da8121ffdfcbc5ea39471e287616aca4f00baa3b183",
  "ApproachRestore1": "30228dadb7898e685ec34bc8e87f52562b32e2bbeeacce7c5f95e4907da06583",
  "ApproachCoverage1": "ec916e9d4a1d36c6a230e085d2434bbf923f1c4a985b559654ae434d52c7ee12",
  "ApproachRunContext1": "b50b3f8749ad664d0bd179d2258e57a366b6a0919c32cde587d4a4ba68a5ae4f",
  "ApproachResolution1": "23d76f5aed637a125416a2464b379502054e89ef97a06c0cb1871afe5d7deb94",
  "ApproachClosure1": "7410f710f16d9a5d80480fb443eaac14deef120d804632c3d3116d3c17837257",
  "ApproachIssue1": "a431290f73434d5893f8c9159602e293c0b4ce3a10dabe4dc22f8645b2696bea",
  "ApproachChange1": "3f27bfd86691d6d038bded5fcf8a94b07fe3b9a626eb52ff6f96e18d7946903f",
  "ApproachPreview1": "267fb41a3dbc10101fae4b1efd57e7dc06bf23fcfd1cb8da2496e4e0eca73761",
  "ApproachCursor1": "4534cf012a3c1ada7563f49b531a3273293b535f6f670e5cf71ca25c947c3a75",
  "ApproachPageRequest1": "2be57e41a6b6dd7c1ba503b917ef999a6856611e8948271c3f00eb77a2479298",
  "ApproachVersionPage1": "60addf4b2cc2a19081226415a84ab87fab28daeb4fd7705e5c8d70a70e72112a",
  "ApproachUsage1": "f3b7c09213ec8c3eb303cb3f4c537973d300e11728726a37235ef237781c2a3f",
  "ApproachUsageCursor1": "11611ec859f75bae36f2f40147180737bbf347759de06bfd477b692b1134ca6f",
  "ApproachUsageRequest1": "2f1b64d068dee1ac709aee33864691b74e76fbd367ebe02e45318611c42fc456",
  "ApproachUsagePage1": "a7127851e0dba7ccd37c72ecfed16e0873d89d47aa491613a2981087a08504cc",
  "ApproachSelection1": "fb2bbc53d4eb01c982220f93f6c9df198ad9ed362771e5791f60e4c020124f3d",
  "ApproachBinding1": "a13bbf89b35eef2c536d65ec03177ae2ff7a3feb93c2e05a3e74029852358821",
  "ConfigurationRequest4": "90e4f682353477b1065468d96c6ad52c375fd32a33d74d99a93a40726ab0bffa",
  "ConfigurationCandidate4": "d560d934ce9d9978f76e07b869df7d4df4e7b037cae8251dca9c9292344c6ac9",
  "ConfigurationRevision4": "a66eb404258ea49ceb202c64488f9c7cfb92cc685a120f8db7e853205b96f7d3",
  "ConfigurationPreview4": "fb38e83448675cd71c4d1d3a7d6001673b91929e1631914eb480e3048d5a704e",
  "ConfigurationCommit4": "9442433f8e76be2b5b125b588d726d55ad764949314244a71995de700c41604d",
  "FrozenConfigurationLegacy": "202406bf8815c418c5ba0c3c8c06125a39a6eeb30d3b08180c36196f9b8591fa",
  "FrozenConfiguration4": "dc5b6e534cf827a31da0fb7e0e2459d37f921b84d807688f26dc5f30ad847dd1",
  "FrozenConfiguration": "c632a93af4ff1618b9577f2e97188685637007b4a6b5734a214313097b5bcbb6",
  "BundleFileV5": "f6f278906042cc63db0166bf185372eac351a6e4d43f301dbca59680e1165be5",
  "ExecutionBundle5": "9566419bb43ec552e0ca7db0a9a0085bad62a763a181d99ad9f81bef0e66442c",
  "RunHistory3": "d9e57c0cb555648c8960b83a8b1f1753d7772020a5c9cffff718277f685f1590",
  "ModifiedRunSeed3": "78eb97949fc8acca1e578bcd419b9dcfa82a24735d1b554628af7e8adecfbd4c",
  "ApproachExportSummary1": "e2b168e2601b5702f1a776cd16d5d7ec0b248a50e70e5d19794ac39cf2141f8c",
  "RecordPreview2": "e59d312db84684ad94cfa9bff0738d94af5fa50ab75b9a9b9c84e2b3710ad8bc",
  "RecordRequest2": "0c64c55ef9073bf0ea7df853c7be59b261f6e3b3380d5de0ef49e20f41c24661",
  "RecordPreviewRead": "41932fa5b04a665a740c413164ccca8ac48671c80690c5370a3fa6ecd4230461",
  "RecordRequestRead": "e660d5097093cd5feaf428c96706e741a315073b4e9c79066ac36ab147b4a678",
  "RecordRequestResponse": "734650ad3fe76f56992f50ba9258872a1faf46d3a740a300285c4bf5964e8540",
  "RecordStatusResponse": "734650ad3fe76f56992f50ba9258872a1faf46d3a740a300285c4bf5964e8540",
  "RecordReceiptResult": "734650ad3fe76f56992f50ba9258872a1faf46d3a740a300285c4bf5964e8540",
  "PayloadFile2": "1a886e8f37ae560651e8c1810db3ff1b70df9b3821d8477714e1fc02effd784d",
  "ApproachPayloadIndex1": "a3cd7ee11720e2c6682bb218ba1d36a1bb4eb893cd61f80f561f66a01e57c640",
  "ComputationalRecordManifest2": "417c7117250c8231ce24e24a24c6dd54810cf1b91353e7f434f36c7775b4bcda",
  "ComputationalRecordManifestRead": "e514ddd6f03be11baf6b14223bcfb23f006a3ad9d2b6e71ffa07ac51a39f3025",
  "ApproachError1": "fa6ae316d9a8448621f9b8c92f8f373df46e1ec2ed2d7950735f499421e8bac6",
  "ApproachCommandResult1": "0b040fe77a76b55f301f8de3fd53f75718eaf48387a838a72580d53e1b96c99f",
  "ApproachStateResponse1": "95059103090f73186462accf2397c057e7940b45fa50da812e2bf996657ae84c",
  "ApproachPreviewResponse1": "1220e8cc4bc252365fd796410a7b2739f8d5e9e55140d9fe58f88b0b4cced334",
  "ApproachDraftResponse1": "159d7025717c731f6c8cb3d1c59caf15cdaf24f47ce0fb8cea62306e133572d3",
  "ApproachSavedResponse1": "21df784e1ea1be64a129952af8b7205380571ec0f5b87d018852ea5a124144e7",
  "ApproachVersionSaveResponse1": "43f7f0726e95dd4b089bfc3dab9615017fdf8c15428af9151818e18e3ce106e7",
  "ApproachVersionListResponse1": "1fee4a53b9e36bcda68ce0759756049ada9746b4002fea316104e982eb8cf32f",
  "ApproachUsageResponse1": "efadbb7d81ea40e24d7f784dee9bd8d81d1f21bf1dce2c95eaeac9ca7868d4cd",
  "ApproachReceipt1": "210421cea864325f9478e57001da5799256b78fa50ecc20caea9c572dbcaf5b8",
  "ApproachReceiptCategory1": "04347eac80994b17e285cecc172b834286ad3d3fda5121795c0ab81e4127f1b3",
  "ConfigurationRevisionPreApproach": "d1bea7127481320ce19730d071a5307184a9d9ff94ff6c873ad5ea7c7c34e134"
}

FIXTURE_HASHES = {
  "contracts/tests/test_modeling_contract.py": (
      "d662f5f99406fce0eb7754f9101ceb7d0c5d2a56c5162e6e2476542a5af9fb6a"
  ),
  "contracts/tests/test_assumptions_evidence_contracts.py": (
      "db99ec35a299c21373b08279a8ca108c26c3908cd1290f0373269bc3351c5347"
  ),
  "contracts/tests/test_native_program_contract.py": (
      "add747df66e39aeb1dd76b262723b67fc1ae40b8889cef528e86ddf799104a2b"
  ),
  "contracts/tests/test_approach_contracts.py": (
      "ca318062e2b1caee3f84b54ff945dcc57878a01fce96c397aec1e681ee6436bd"
  ),
}



def test_original_concrete_definitions_and_fixture_bytes_preserved():
    aliases = {'ModelDraft', 'ModelRevision', 'ModelPackage', 'Edit', 'Apply', 'Preview',
               'FrozenConfiguration', 'ExecutionBundle', 'ExecutionBundleRead',
               'RunHistory', 'ModifiedRunSeed', 'ExecutionVersions'}
    assert ORIGINAL_HASHES and FIXTURE_HASHES
    for name, expected in ORIGINAL_HASHES.items():
        if name in aliases: continue
        if name in case_removal_digests():
            expected = case_removal_digests()[name]
            if expected is None:
                assert name not in D
                continue
        encoded = json.dumps(D[name], sort_keys=True, separators=(',', ':'))
        if name in PINNED:
            encoded = encoded.replace('#/$defs/ModelRevisionPreUnits', '#/$defs/ModelRevision')
            encoded = encoded.replace('#/$defs/ApproachClosurePreUnits', '#/$defs/ApproachClosure1')
        assert hashlib.sha256(encoded.encode()).hexdigest() == expected, name
    for path, expected in FIXTURE_HASHES.items():
        payload = (ROOT / path).read_bytes()
        if path == 'contracts/tests/test_approach_contracts.py':
            # Approved Case removal updates the matching structural fixtures.
            assert hashlib.sha256(payload).hexdigest() == '6a96fb2cc35c2fe77694525904f7b5f1e753d3f7724764801821e27a1c30afa8'
            continue

        if path == 'contracts/tests/test_native_program_contract.py':
            payload = payload.replace(
                b'validate("PreparedModelArtifact3" if artifact["schema_version"] == "3" '
                b'else "PreparedModelArtifact", artifact)',
                b'validate("PreparedModelArtifact", artifact)')
            # The current producer response was versioned in 790a09f and again when preparation
            # stopped carrying configuration criteria; normalize only that assertion.
            payload = payload.replace(b'endswith("/PreparedModelArtifactResponse4")',
                                      b'endswith("/PreparedModelArtifactResponse")')
            # Pinned as it stands (two audited repairs: digest vectors recomputed for the
            # renamed namespace, and major-one checks read through the versioned unions);
            # reversing only those audited edits must give back the original hash.
            assert hashlib.sha256(payload).hexdigest() == (
                '2c58c73500e8a41c48601c5396e43c08b7afe436c5f4e6b4ebdc9b589d557433'
            )
            payload = payload.replace(b'    assert artifact["executable_content_digest"] == "cd03923ae01b944b8ea421fb040dd4a8e5d23e07579e97f08f0fdace9df0e6db"\n    assert artifact["prepared_digest"] == "310b64ddebf0cad72f9f28bbe517e5f37f900c5a1347dbe87464f52bff6510ca"\n', b'    assert artifact["executable_content_digest"] == "4292671e4fda7313c56e211de8068e8be188f6a4facaa63ea32b6652894da517"\n    assert artifact["prepared_digest"] == "c41a9f8fac3c493d05457c1755ff690c6024aaab6e12b7866b71f2bd149fd19d"\n')
            payload = payload.replace(b'        # Versioned unions keep their major-one branch; later versions are added beside it.\n        for name in ("ModelDraft", "ModelRevision", "ModelPackage", "ConfigurationRevision"):\n            assert {"$ref": "#/$defs/" + name + "1"} in schema["$defs"][name]["oneOf"]\n            assert schema["$defs"][name + "1"]["properties"]["schema_version"] == {"enum": ["1"]}\n        assert schema["$defs"]["PreparedModelArtifactResponse"]["properties"]["schema_version"] == {"enum": ["1"]}\n', b'        for name in ("ModelDraft", "ModelRevision", "ModelPackage", "ConfigurationRevision", "PreparedModelArtifactResponse"):\n            assert schema["$defs"][name]["properties"]["schema_version"] == {"enum": ["1"]}\n')

        assert hashlib.sha256(payload).hexdigest() == expected, path


def test_complete_nested_reference_graph_and_exact_wrapper_selection():
    expected = {
        'PortDeclaration3': ['UnitDeclaration1'], 'Port3': ['UnitDeclaration1'],
        'Definition3': ['Annotation', 'BoundaryMapping', 'Instance', 'Port3'],
        'DefinitionRead3': ['Definition', 'Definition3'], 'PortRead3': ['Port', 'Port3'],
        'DefinitionChange3': ['Source', 'UnitDeclaration1', 'UnitDeclaration1'],
        'Edit3': ['AssumptionBatchOwner', 'AssumptionEvidenceLink', 'AssumptionEvidenceLink',
                  'BatchPortRef', 'BatchPortRef', 'DefinitionChange3', 'PortDeclaration3',
                  'Source', 'VersionRef', 'VersionRef'],
        'ModelDraft3': ['Annotation', 'BoundaryMapping', 'Connection', 'DefinitionRead3',
                        'Instance', 'ModelAssumption', 'PortRead3', 'Source'],
        'ModelRevision3': ['Annotation', 'BoundaryMapping', 'Connection', 'DefinitionRead3',
                           'Instance', 'ModelAssumption', 'PortRead3', 'Source'],
        'ModelPackage3': ['File', 'ModelRevision1', 'ModelRevision2', 'ModelRevision3'],
        'Preview3': ['Edit3'], 'Apply3': ['Edit3'],
        'FrozenConfiguration5Model3': ['ApproachClosure1', 'ApproachClosure1', 'ConfigurationRevision4', 'ModelRevision3'],
        'ModifiedRunSeed4Model3': ['ApproachClosure1', 'ApproachClosure1', 'ConfigurationRequest4',
                             'ConfigurationRevision4', 'ModelRevision3', 'RuntimeComparison'],
        'RunHistory4Model3': ['ApproachClosure1', 'ConfigurationRevision4', 'EvidenceSnapshotRead',
                        'HistoryArtifact', 'ModelRevision3', 'RetainedResults'],
        'ExecutionBundle6Model3': ['BundleFileV5', 'BundleLicenseNotice', 'NativeGeneratorIdentity', 'ProgramEntrypoint'],
    }
    for name in ('FrozenConfiguration5', 'RunHistory4', 'ModifiedRunSeed4', 'ExecutionBundle6'):
        expected[name] = [name+'Model3', name+'Model2']
    def refs(node):
        if isinstance(node, dict):
            return ([node['$ref'].split('/')[-1]] if '$ref' in node else []) + [r for v in node.values() for r in refs(v)]
        if isinstance(node, list): return [r for v in node for r in refs(v)]
        return []
    for name, targets in expected.items(): assert sorted(refs(D[name])) == sorted(targets), name
    for prefix in ('Apply', 'Preview'):
        for version in (1, 2, 3):
            assert D[prefix+str(version)]['properties']['edits']['items'] == {'$ref': '#/$defs/Edit'+str(version)}
    for name in PINNED:
        assert 'ModelRevision' not in refs(D[name])
        assert 'ModelRevisionPreUnits' in refs(D[name])


def test_encoded_bundle_file_pairing_matrix_rejects_cross_version_substitution():
    # Admission contract for independently encoded files. These synthetic payloads
    # establish schema discrimination only; digest, identity and runtime admission are proven
    # by the bundle and worker admission tests.
    matrix = {
        2: ('ModelRevision1', 'ConfigurationRevision1', None, 'FrozenConfigurationLegacy'),
        3: ('ModelRevision1', 'ConfigurationRevision2', 'ModelingConfigurationRevision2', 'FrozenConfigurationLegacy'),
        4: ('ModelRevision2', 'ConfigurationRevision3', 'ModelingConfigurationRevision3', 'FrozenConfigurationLegacy'),
        5: ('ModelRevision2', 'ConfigurationRevision4', 'ModelingConfigurationRevision3', 'FrozenConfiguration4'),
        6: ('ModelRevision3', 'ConfigurationRevision4', 'ModelingConfigurationRevision3', 'FrozenConfiguration5'),
    }
    for version, (model_name, config_name, private_name, frozen_name) in matrix.items():
        model = valid(model_name) if version == 6 else sample(D[model_name])
        config = sample(D[config_name])
        frozen = valid(frozen_name) if version == 6 else previous_sample(frozen_name)
        frozen.update(model_snapshot=model, configuration=config)
        validate(frozen_name, frozen)
        if private_name: validate(private_name, sample(D[private_name]))
        if version < 6:
            with pytest.raises(ValidationError): validate(frozen_name, frozen | {'model_snapshot': valid('ModelRevision3')})
        else:
            for old_model in ('ModelRevision1', 'ModelRevision2'):
                with pytest.raises(ValidationError): validate(frozen_name, frozen | {'model_snapshot': sample(D[old_model])})
            for old_config in ('ConfigurationRevision1', 'ConfigurationRevision2', 'ConfigurationRevision3'):
                with pytest.raises(ValidationError): validate(frozen_name, frozen | {'configuration': sample(D[old_config])})
            with pytest.raises(ValidationError): validate(private_name, sample(D['ModelingConfigurationRevision2']))


def test_current_response_and_receipt_paths_admit_new_branches():
    for name, target in [('ModelDraftResponse', 'ModelDraft3'), ('ModelDraftEditResponse', 'ModelDraft3'),
                         ('ModelRevisionResponse', 'ModelRevision3'), ('ModelPackageResponse', 'ModelPackage3')]:
        envelope = {field: ({} if field == 'created_ids' else sample(D[name]['properties'][field])) for field in D[name]['required']}; envelope['data'] = valid(target)
        validate(name, envelope)
    validate('CreateRequest', sample(D['Create']))
    validate('CreateRequest', valid('Create3'))
    for alias, concrete in [('Apply','Apply3'),('Preview','Preview3'),('ModelDraft','ModelDraft3'),
                            ('ModelRevision','ModelRevision3'),('FrozenConfiguration','FrozenConfiguration5'),
                            ('RunHistory','RunHistory4'),('ModifiedRunSeed','ModifiedRunSeed4')]:
        validate(alias, valid(concrete))


def test_receipts_preserve_typed_model3_results():
    for target in ('ModelDraft3', 'ModelRevision3'):
        receipt = dict(state='committed', command_id='11111111-1111-4111-8111-111111111111',
                       payload_digest='a'*64, response={'data': valid(target)}, status=201)
        validate('Receipt', receipt)
        if target == 'ModelDraft3':
            receipt['response'].update(created_ids={}, diagnostics=[])
            validate('Receipt', receipt)


@pytest.mark.parametrize('name', ['ModelDraft3', 'ModelRevision3'])
def test_mixed_snapshot_retains_exact_legacy_versions_and_stable_port_ids(name):
    legacy = sample(D['Definition'])
    legacy['definition_version_id'] = '11111111-1111-4111-8111-111111111111'
    port = sample(D['Port']); port['units'] = ''
    port['definition_version_id'] = legacy['definition_version_id']
    legacy['ports'] = [port]
    legacy_bytes = json.dumps(legacy, sort_keys=True, separators=(',', ':')).encode()
    legacy_sha = hashlib.sha256(legacy_bytes).hexdigest()
    newer = copy.deepcopy(legacy)
    newer['definition_version_id'] = '22222222-2222-4222-8222-222222222222'
    newer['ports'][0].update(definition_version_id=newer['definition_version_id'], units={'kind':'dimensionless'})
    assert newer['ports'][0]['port_id'] == port['port_id']
    snapshot = valid(name)
    snapshot['definitions'] = [legacy, newer]
    snapshot['ports'] = [port, newer['ports'][0]]
    instance = sample(D['Instance']); instance['definition_version_id'] = newer['definition_version_id']
    snapshot['instances'] = [instance]
    validate(name, snapshot)
    roundtrip = json.loads(json.dumps(snapshot))
    assert hashlib.sha256(json.dumps(roundtrip['definitions'][0], sort_keys=True, separators=(',', ':')).encode()).hexdigest() == legacy_sha
    assert roundtrip['ports'] == [p for definition in roundtrip['definitions'] for p in definition['ports']]
    assert roundtrip['ports'][0]['units'] == ''
    for old_name in ('ModelDraft1', 'ModelDraft2', 'ModelRevision1', 'ModelRevision2'):
        old = sample(D[old_name]); old['definitions'] = [legacy, newer]; old['ports'] = snapshot['ports']
        with pytest.raises(ValidationError): validate(old_name, old)
    with pytest.raises(ValidationError): validate('Definition3', legacy)
    with pytest.raises(ValidationError): validate('Port3', port)
    # Same immutable definition cannot mix old/new port representations.
    hybrid = copy.deepcopy(legacy); hybrid['ports'].append(newer['ports'][0])
    with pytest.raises(ValidationError): validate('DefinitionRead3', hybrid)
    for malformed in ({'kind':'unknown'}, {'kind':'physical'}, {'kind':'physical','expression':''}, None):
        bad = copy.deepcopy(snapshot); bad['definitions'][1]['ports'][0]['units'] = malformed
        with pytest.raises(ValidationError): validate(name, bad)


def test_zero_port_definition_union_is_unambiguous_and_new_edits_remain_strict():
    empty = sample(D['Definition'])
    validate('Definition', empty); validate('Definition3', empty)
    validate('DefinitionRead3', empty)
    snapshot = valid('ModelDraft3'); snapshot['definitions'] = [empty]
    validate('ModelDraft3', snapshot)
    for version in (1, 2):
        snapshot = sample(D['ModelDraft'+str(version)]); snapshot['definitions'] = [empty]
        validate('ModelDraft'+str(version), snapshot)
    edit = sample(D['Edit3']['oneOf'][0]); old_port = sample(D['PortDeclaration'])
    old_port['units'] = ''; edit['ports'] = [old_port]
    with pytest.raises(ValidationError): validate('Edit3', edit)
    with pytest.raises(ValidationError): validate('Preview3', valid('Preview3') | {'edits':[edit]})
    with pytest.raises(ValidationError): validate('Apply3', valid('Apply3') | {'edits':[edit]})


# Exact pre-repair hashes; no normalization or allowlist expansion.
PRE_REPAIR_HASHES = {'ModelRevision1': 'acc65cb1e1c564e854c9e0b5d4b625c490644500bfdf0027f6d57a11cb5870da', 'ModelRevision2': '0fc0f2ce72645664fd501c57aa48c201b8eb53704a19a7403e506d45b0d2ef1b', 'ModelPackage1': '9a4320db766612b22f0ced8dfa5665c90ed5c8da196b5db7635aecddb7a3df76', 'ModelPackage2': '426c77077c6a2f11d1b6c9ceba589a44c47d21e82045939b3fa8b68512b9c3b4', 'ModelRevisionPreUnits': 'a7ba7a3e15b0340d9a6461f1f65f581e26ab9ba730181dc00ae16e86130347ad', 'ApproachClosurePreUnits': 'acc075427a7756bc7fc1aa7519fc8364fa4b809e01951b8fde3dd34121094634', 'FrozenConfigurationLegacy': '1373c7e0b1e6784d282b6c9c7af90fde2fc38df7d6a749edfb370d6971ee97b6', 'FrozenConfiguration4': '02c93f3963141c0c65652759904e8eddfe62bf65eade648236014511928dee40', 'ExecutionBundle2': 'adc18ac80f58753bbe8c62a87ee4cb7feef74f2199032190f467cc40d04fb687', 'ExecutionBundle3': '137670a8922a147fa370ee21b7f7d6e05a8df7b02047af0093a65dae92ab0e8e', 'ExecutionBundle4': '33db999aa28dd4f8eb94a5036eb9a663eec57b478472eb6c596fa4b9b0361a88', 'ExecutionBundle5': '9566419bb43ec552e0ca7db0a9a0085bad62a763a181d99ad9f81bef0e66442c', 'RunHistory1': 'c6be84203a17c76d8eb6a5196f76a2fa0e741b7d68d6dd87d225b02f9686896e', 'RunHistory2': 'bbe838c6eb644162df3ebcee230afca9f5067ff48f4309c99ba09051615dc716', 'RunHistory3': '494081c0efadc9c06cb4cd830a799f2f301bca3fc7ed222fa372cca80b52b5f0', 'ModifiedRunSeed1': '97c4498c67a98e693815e67ecf0456fdeab4a06145d3630ff131e16036fecdaf', 'ModifiedRunSeed2': 'f7569a9a0267343ee13cdbda66fb4e2c9e6829dbda3b7a63b7d3dfabad84adb7', 'ModifiedRunSeed3': 'c7a8aebae4f4e5a00892bbc7e46f70ed8e0312b5c4b70113384e85423f48a626', 'ConfigurationRevision4': 'a66eb404258ea49ceb202c64488f9c7cfb92cc685a120f8db7e853205b96f7d3', 'ModelingConfigurationRevision3': 'feadf4f58d91023d25d0ea723382a7ca9705f5925bcf0434c140ac84e356901e', 'PreparedModelArtifact2': '1f82dddac0da126c1a4bda1469f02ec35da21d76522d7e8b2c5a22da394dc73e'}


def test_repair_preserves_exact_historical_and_private_concrete_schemas():
    for name, expected in PRE_REPAIR_HASHES.items():
        assert hashlib.sha256(json.dumps(D[name], sort_keys=True,
            separators=(',', ':')).encode()).hexdigest() == expected, name


def mixed_record(name, units=None):
    """Schema samples only; semantic reachability/digest admission is R2/R3."""
    record = valid(name)
    model = sample(D['ModelRevision2'])
    model['required_capabilities'] = ['flat_explicit_scalar']
    model['ports'] = [sample(D['Port']) | {'units': ''}]
    explanatory = valid('ModelRevision3')
    explanatory['model_revision_id'] = '22222222-2222-4222-8222-222222222222'
    explanatory['ports'] = [valid('Port3') | {'units': units or {'kind': 'unspecified'}}]
    closure = sample(D['ApproachClosure1'])
    closure['models'] = [model, explanatory]
    record.update(model_snapshot=model, approach_closure=closure)
    field = 'source_configuration' if name == 'ModifiedRunSeed4' else 'configuration'
    record[field] = sample(D['ConfigurationRevision4'])
    record[field]['approach_binding'] = sample(D['ApproachBinding1'])
    return record


@pytest.mark.parametrize('name', ['FrozenConfiguration5', 'RunHistory4', 'ModifiedRunSeed4'])
@pytest.mark.parametrize('units', [{'kind': 'unspecified'}, {'kind': 'physical', 'expression': 'N'}])
def test_mixed_exact_model2_is_an_explicit_new_envelope_branch(name, units):
    value = mixed_record(name, units)
    original = json.dumps(value['model_snapshot'], sort_keys=True)
    validate(name, value)
    validate({'FrozenConfiguration5':'FrozenConfiguration', 'RunHistory4':'RunHistory',
              'ModifiedRunSeed4':'ModifiedRunSeed'}[name], value)
    assert json.dumps(value['model_snapshot'], sort_keys=True) == original
    assert value['model_snapshot']['ports'][0]['units'] == ''
    with pytest.raises(ValidationError): validate(name, value | {'unknown': True})
    for field in value:
        bad = copy.deepcopy(value); del bad[field]
        with pytest.raises(ValidationError): validate(name, bad)
    # Both unions are disjoint, including the selected Model3 alternative.
    branches = D[name]['oneOf']
    assert sum(Draft202012Validator({**SCHEMA, **branch}).is_valid(value)
               for branch in branches) == 1
    typed = valid(name)
    assert sum(Draft202012Validator({**SCHEMA, **branch}).is_valid(typed)
               for branch in branches) == 1


@pytest.mark.parametrize('name', ['FrozenConfiguration5', 'RunHistory4', 'ModifiedRunSeed4'])
@pytest.mark.parametrize('defect', ['absent_closure', 'legacy_closure', 'null_pin', 'null_config',
    'model1', 'malformed_model3', 'wrong_config', 'foreign_closure'])
def test_mixed_new_envelope_rejects_incomplete_and_wrong_pairings(name, defect):
    value = mixed_record(name)
    field = 'source_configuration' if name == 'ModifiedRunSeed4' else 'configuration'
    if defect == 'absent_closure': value['approach_closure'] = None
    elif defect == 'legacy_closure': value['approach_closure']['models'] = [value['model_snapshot']]
    elif defect == 'null_pin': value[field]['approach_binding'] = None
    elif defect == 'null_config': value[field] = None
    elif defect == 'model1': value['model_snapshot'] = sample(D['ModelRevision1'])
    elif defect == 'malformed_model3': value['approach_closure']['models'][1]['ports'][0]['units'] = {'kind':'physical'}
    elif defect == 'wrong_config': value[field] = sample(D['ConfigurationRevision3'])
    elif defect == 'foreign_closure': value['approach_closure']['unknown'] = True
    with pytest.raises(ValidationError): validate(name, value)


def linked_manifest(capabilities):
    value = previous_sample('ExecutionBundle5')
    value.update(schema_version='6', required_capabilities=capabilities,
                 approach_digest='a'*64, approach_closure_digest='b'*64)
    value['files'].append(dict(path='approach/closure.json', role='approach',
        sha256='b'*64, size=10, media_type='application/json'))
    return value


def test_bundle6_explicit_capability_branches_and_linked_legacy_fields():
    for capabilities in (['flat_explicit_scalar'], ['flat_explicit_scalar', 'unit_declarations/1']):
        value = linked_manifest(capabilities)
        validate('ExecutionBundle6', value)
        branches = D['ExecutionBundle6']['oneOf']
        assert sum(Draft202012Validator({**SCHEMA, **b}).is_valid(value) for b in branches) == 1
    value = linked_manifest(['flat_explicit_scalar'])
    for capabilities in ([], ['unit_declarations/1'], ['flat_explicit_scalar','foreign'],
                         ['flat_explicit_scalar','flat_explicit_scalar']):
        with pytest.raises(ValidationError): validate('ExecutionBundle6', value | {'required_capabilities': capabilities})
    for field in ('approach_digest', 'approach_closure_digest'):
        with pytest.raises(ValidationError): validate('ExecutionBundle6', value | {field: None})
    value['files'] = [f for f in value['files'] if f['role'] != 'approach']
    with pytest.raises(ValidationError): validate('ExecutionBundle6', value)


def test_mixed_encoded_payload_matrix_not_just_manifest_validation():
    frozen = mixed_record('FrozenConfiguration5')
    payloads = json.loads(json.dumps({'model.json': frozen['model_snapshot'],
        'configuration.json': frozen['configuration'],
        'modeling-configuration.json': sample(D['ModelingConfigurationRevision3']),
        'approach/closure.json': frozen['approach_closure'], 'frozen_configuration': frozen}))
    branch = next(b for b in D['ExecutionBundle6']['x-hyprn-mvp-file-schemas']['oneOf']
                  if b['required_capabilities'] == ['flat_explicit_scalar'])
    for path, ref in branch['files'].items(): validate(ref.split('/')[-1], payloads[path])
    validate('ExecutionBundle6', linked_manifest(['flat_explicit_scalar']))
    # Manifest cannot inspect payloads: explicitly decode/validate the concrete
    # wrapper and private file. Fully authenticated runtime checks belong R2/R3.
    old_manifest = linked_manifest(['flat_explicit_scalar']) | {'schema_version':'5'}
    validate('ExecutionBundle5', old_manifest)
    with pytest.raises(ValidationError): validate('FrozenConfiguration4', frozen | {'schema_version':'4'})
    with pytest.raises(ValidationError): validate('ApproachClosurePreUnits', payloads['approach/closure.json'])
    with pytest.raises(ValidationError): validate('ModelingConfigurationRevision3', sample(D['ModelingConfigurationRevision2']))
    for name, old, discriminator, version in [('RunHistory4','RunHistory3','history_schema_version','3'),
                                             ('ModifiedRunSeed4','ModifiedRunSeed3','schema_version','3')]:
        with pytest.raises(ValidationError): validate(old, mixed_record(name) | {discriminator:version})


def test_history4_null_partial_disjointness_and_no_fabricated_model2():
    history = valid('RunHistory4')
    history.update(configuration=None, model_snapshot=None, context=None, evidence=None,
        bundle=None, results=None, assessment=None, approach_closure=None,
        errors=[{'code':'corrupt_retained_record','partial':True}])
    validate('RunHistory4', history)
    assert sum(Draft202012Validator({**SCHEMA, **b}).is_valid(history)
               for b in D['RunHistory4']['oneOf']) == 1
    with pytest.raises(ValidationError): validate('RunHistory4', history | {'model_snapshot':sample(D['ModelRevision2'])})
    with pytest.raises(ValidationError): validate('RunHistory4', history | {'unknown':True})



@pytest.mark.parametrize('name,field', [('FrozenConfiguration5','configuration'),
                                      ('ModifiedRunSeed4','source_configuration')])
def test_selected_model3_keeps_null_and_linked_closure_rules(name, field):
    value = valid(name)
    validate(name, value)
    value['approach_closure'] = sample(D['ApproachClosure1'])
    with pytest.raises(ValidationError): validate(name, value)
    value[field]['approach_binding'] = sample(D['ApproachBinding1'])
    validate(name, value)
    with pytest.raises(ValidationError): validate(name, value | {'approach_closure':None})


def test_private_refs_and_generated_public_branches_keep_real_types():
    api = json.loads((ROOT / 'contracts/modeling.openapi.yaml').read_text())
    def walk(node):
        if isinstance(node, dict):
            if '$ref' in node:
                filename, fragment = node['$ref'].split('#', 1)
                assert filename == './schemas/model.schema.json'
                target = SCHEMA
                for part in fragment.lstrip('/').split('/'): target = target[part]
                assert target
            for child in node.values(): walk(child)
        elif isinstance(node, list):
            for child in node: walk(child)
    walk(api)
    public = json.loads((ROOT / 'contracts/hyprn-mvp.openapi.yaml').read_text())['components']['schemas']
    def rewrite(node):
        if isinstance(node, dict):
            return {key:(value.replace('#/$defs/','#/components/schemas/') if key == '$ref'
                         else rewrite(value)) for key,value in node.items()}
        if isinstance(node, list): return [rewrite(value) for value in node]
        return node
    names = ['ApproachClosureWithModel3']
    for family in ('FrozenConfiguration5','RunHistory4','ModifiedRunSeed4','ExecutionBundle6'):
        names.extend([family,family+'Model3',family+'Model2'])
    types = (ROOT / 'ui/src/contract.ts').read_text().splitlines()
    for name in names:
        projected = copy.deepcopy(public[name])
        def remove_view_marker(node):
            if isinstance(node, dict):
                props = node.get('properties', {})
                if 'record_view' in props:
                    assert props.pop('record_view') == {'$ref':'#/components/schemas/RecordView1'}
                    assert 'record_view' not in node.get('required', [])
                for child in node.values(): remove_view_marker(child)
            elif isinstance(node, list):
                for child in node: remove_view_marker(child)
        remove_view_marker(projected)
        assert projected == rewrite(D[name]), name
        declaration = next(line for line in types if line.startswith('export type '+name+' = '))
        assert 'unknown' not in declaration and ' as ' not in declaration, name
    for family in ('FrozenConfiguration5','RunHistory4','ModifiedRunSeed4'):
        for version in ('2','3'):
            declaration = next(line for line in types if line.startswith('export type '+family+'Model'+version+' = '))
            assert '"model_snapshot":' in declaration
            assert 'ModelRevision'+version in declaration

@pytest.mark.parametrize('units',['','m',{'kind':'dimensionless'},{'kind':'unspecified'},{'kind':'physical','expression':'m'}])
def test_polish_quantity_exact_units_bounds_and_semantic_counterexamples(units):
    definition=sample({k:v for k,v in D['Definition4'].items() if k!='anyOf'});port=sample(D['Port']);port['units']=units
    definition['ports']=[port];definition['quantity_definitions']=[dict(port_id=port['port_id'],statement='Meaning')]
    validate('Definition4',definition)
    for statement in ('',' ','x'*4097):
        bad=copy.deepcopy(definition);bad['quantity_definitions'][0]['statement']=statement
        with pytest.raises(ValidationError):validate('Definition4',bad)
    bad=copy.deepcopy(definition);bad['quantity_definitions']*=1001
    with pytest.raises(ValidationError):validate('Definition4',bad)
    bad=copy.deepcopy(definition);other=copy.deepcopy(port);other['units']={'kind':'dimensionless'} if isinstance(units,str) else 'm';bad['ports'].append(other)
    with pytest.raises(ValidationError):validate('Definition4',bad)
    semantic=copy.deepcopy(definition);semantic['quantity_definitions'].append(dict(port_id=port['port_id'],statement='Different'));validate('Definition4',semantic)
    semantic['quantity_definitions'][0]['port_id']='22222222-2222-4222-8222-222222222222';validate('Definition4',semantic)
    assert D['Definition4']['properties']['annotations']==D['Definition']['properties']['annotations']

def test_polish_definition_edits_are_nested_and_versioned():
    for change in (dict(kind='set_quantity_definition',port_id='11111111-1111-4111-8111-111111111111',statement='Meaning'),dict(kind='clear_quantity_definition',port_id='11111111-1111-4111-8111-111111111111')):
        validate('DefinitionChange4',change)
        edit=sample(next(b for b in D['Edit4']['oneOf'] if b['properties']['kind']['enum']==['revise_definition']));edit['changes']=[change]
        for name in ('Preview4','Apply4'):validate(name,sample(D[name])|{'edits':[edit]})
        with pytest.raises(ValidationError):validate('Edit4',change)
        with pytest.raises(ValidationError):validate('DefinitionChange3',change)


def test_only_approved_catalogue_enum_suffix_and_count_changed():
    from test_approach_contracts import test_polish_historical_hashes
    test_polish_historical_hashes()


@pytest.mark.parametrize('expression', ['USD', 'kUSD', 'MUSD', 'pax', 'USD/pax', 'USD/kg',
                                      'USD/m**3', 'USD/h', 'USD/kW', 'USD/(kW*h)', 'USD/J', 'USD/MJ'])
def test_monetary_expressions_require_successor_unit_declaration(expression):
    declaration = dict(kind='physical', expression=expression)
    validate('UnitDeclaration2', declaration)
    with pytest.raises(ValidationError):
        validate('UnitDeclaration1', declaration)


@pytest.mark.parametrize('expression', ['EUR', 'EUR/kg', 'USD/kWh', 'GBP', 'USD_2025'])
def test_unsupported_currency_and_aliases_are_not_catalogue_authority(expression):
    with pytest.raises(ValidationError):
        validate('UnitDeclaration2', dict(kind='physical', expression=expression))


def test_monetary_metadata_binds_expression_numerator_scale_and_denominator():
    record = dict(expression='kUSD', numerator='USD', scale=1000.0, denominator='')
    validate('MonetaryUnit1', record)
    for changes in [dict(numerator='EUR'), dict(scale=1), dict(denominator='kg')]:
        with pytest.raises(ValidationError):
            validate('MonetaryUnit1', record | changes)
