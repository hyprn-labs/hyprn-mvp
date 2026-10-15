"""Wire-level approach proofs. Resolution/hash/reachability belongs to task 15.2.

These tests never import native code or resolve live scientific records.
"""
from hyprn_mvp_app.contracts import authored_schema
from test_schema_sources import assert_execution_schema
import copy
import json
from pathlib import Path
import pytest
from jsonschema import Draft202012Validator, FormatChecker, ValidationError

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = authored_schema()
D = SCHEMA['$defs']
UUID = '11111111-1111-4111-8111-111111111111'
SHA = 'a' * 64
NEW_OBJECTS = '''ApproachContent1 ApproachModelBinding1 ApproachStep1 ApproachIntent1
ApproachEvidenceLink1 ApproachAssumption1 ApproachAssumptionOrigin1 ApproachCase1
ApproachDraft1 ApproachVersion1 ApproachSaved1 ApproachState1 ApproachVersionSummary1
ApproachPreviewRequest1 ApproachPreview1 ApproachDraftWrite1 ApproachVersionSave1
ApproachVersionSaved1 ApproachRestore1 ApproachResolution1 ApproachCoverage1
ApproachVersionPage1 ApproachUsagePage1 ApproachPageRequest1 ApproachUsageRequest1
ApproachRunContext1 ApproachClosure1 ApproachSelection1 ApproachBinding1
ConfigurationRequest4 ConfigurationCandidate4 ConfigurationRevision4 ConfigurationPreview4
ConfigurationCommit4 FrozenConfiguration4 ExecutionBundle5 RunHistory3 ModifiedRunSeed3
ApproachExportSummary1 RecordPreview2 RecordRequest2 ComputationalRecordManifest2
ApproachPayloadIndex1'''.split()

def validate(name, value):
    Draft202012Validator({**SCHEMA, '$ref': '#/$defs/' + name}, format_checker=FormatChecker()).validate(value)

def sample(s):
    if '$ref' in s: return sample(D[s['$ref'].split('/')[-1]])
    if 'const' in s: return s['const']
    if 'enum' in s: return s['enum'][0]
    if 'oneOf' in s or 'anyOf' in s:
        branches = s.get('oneOf', s.get('anyOf'))
        return sample(next((b for b in branches if b.get('type') == 'null'), branches[0]))
    kind = s.get('type')
    if kind == 'object': return {k: sample(s['properties'][k]) for k in s['required']}
    if kind == 'array': return [sample(s['items']) for _ in range(s.get('minItems', 0))]
    if kind == 'null': return None
    if kind == 'boolean': return False
    if kind in ('integer', 'number'): return s.get('minimum', 0)
    if s.get('format') == 'uuid': return UUID
    if s.get('format') == 'date-time': return '2026-10-10T14:30:00Z'
    if s.get('pattern') == '^[0-9a-f]{64}$': return SHA
    if s.get('pattern') == '^sha256:[0-9a-f]{64}$': return 'sha256:' + SHA
    return 'x'

def valid(name):
    value = sample(D[name])
    if name == 'ApproachRunContext1': value['association']['store_uuid'] = UUID
    if name == 'ApproachStep1': value['remaining_work'] = 'Specify correspondence'
    if name == 'ModifiedRunSeed3': value['runtime_comparison'].update(state='unavailable', current=None)
    if name == 'ComputationalRecordManifest2':
        value['runs'][0].update(process_uuid=UUID,bundle_digest=SHA)
    if name == 'ExecutionBundle5':
        from test_native_program_contract import fixture, bundle
        artifact, files = fixture()
        value = bundle(artifact, files) | dict(schema_version='5',modeling_configuration_digest=SHA,result_dependencies=dict(path='result-dependencies.json',sha256=SHA,size=10),approach_digest=None,approach_closure_digest=None)
        value['files'] = [dict(path=p, role=r, sha256=SHA, size=10, media_type='application/json') for p,r in [('configuration.json','configuration'),('modeling-configuration.json','modeling_configuration'),('result-dependencies.json','result_dependencies')]]
    return value

@pytest.mark.parametrize('name', NEW_OBJECTS)
def test_new_records_closed_required_valid(name):
    value = valid(name)
    validate(name, value)
    with pytest.raises(ValidationError): validate(name, value | {'foreign': True})
    for field in D[name]['required']:
        bad = copy.deepcopy(value); del bad[field]
        with pytest.raises(ValidationError): validate(name, bad)

def test_mirrors_and_private_protocols_unchanged():
    other = authored_schema()['$defs']
    assert_execution_schema()
    assert D['ModelingConfiguration3']['properties']['schema_version'] == {'enum':['3']}
    assert D['PreparedModelArtifact2']['properties']['schema_version'] == {'enum':['2']}
    assert 'approach_binding' not in D['ModelingConfiguration3']['properties']
    assert 'approach' not in D['BundleFileV3']['properties']['role']['enum']

@pytest.mark.parametrize('name,values', [
    ('ApproachElementRef1', [dict(kind='model',binding_id=UUID),dict(kind='instance',binding_id=UUID,instance_id=UUID),dict(kind='port',binding_id=UUID,instance_id=UUID,port_id=UUID),dict(kind='connection',binding_id=UUID,connection_id=UUID)]),
    ('ApproachAssumptionRef1', [dict(kind='approach',assumption_id=UUID),dict(kind='model',binding_id=UUID,assumption_id=UUID,origin=None),dict(kind='configuration',configuration_revision_id=UUID,assumption_id=UUID)]),
    ('ApproachBasisRef1', [dict(kind='configuration',configuration_revision_id=UUID,reason='Calibration',relation='supports'),dict(kind='run',run_id=UUID,reason='Prior failure',relation='challenges')]),
])
def test_closed_discriminators_reject_foreign_fields(name, values):
    for value in values:
        validate(name,value)
        with pytest.raises(ValidationError): validate(name,value | {'foreign':UUID})
        for field in value:
            if field.endswith('_id'):
                with pytest.raises(ValidationError): validate(name,value | {field:'latest'})
    with pytest.raises(ValidationError): validate(name,values[-1] | {'kind':values[0]['kind']})

def test_implementation_states_do_not_overclaim():
    value=valid('ApproachStep1'); validate('ApproachStep1',value)
    ref=dict(kind='model',binding_id=UUID)
    with pytest.raises(ValidationError): validate('ApproachStep1',value | {'implementation_refs':[ref]})
    for state in ('partial','linked'):
        with pytest.raises(ValidationError): validate('ApproachStep1',value | {'implementation_state':state})
    validate('ApproachStep1',value | {'implementation_state':'partial','implementation_refs':[ref]})
    with pytest.raises(ValidationError): validate('ApproachStep1',value | {'implementation_state':'partial','implementation_refs':[ref],'remaining_work':''})
    validate('ApproachStep1',value | {'implementation_state':'linked','implementation_refs':[ref],'remaining_work':''})
    with pytest.raises(ValidationError): validate('ApproachStep1',value | {'implementation_state':'linked','implementation_refs':[ref]})

def test_bounds_ids_hashes_nullable_fields_and_pairing():
    value=valid('ApproachContent1')
    for key,limit in [('model_bindings',32),('steps',64),('assumptions',256),('cases',64),('basis_refs',64)]:
        item=sample(D['ApproachContent1']['properties'][key]['items'])
        with pytest.raises(ValidationError): validate('ApproachContent1',value | {key:[item]*(limit+1)})
    with pytest.raises(ValidationError): validate('ApproachContent1',value | {'question':'x'*4097})
    for name in ('ApproachBinding1','ApproachVersion1','ApproachClosure1'):
        value=valid(name)
        for key in value:
            if key.endswith('_digest') or key=='digest':
                with pytest.raises(ValidationError): validate(name,value | {key:'A'*64})
    frozen=valid('FrozenConfiguration4')
    with pytest.raises(ValidationError): validate('FrozenConfiguration4',frozen | {'approach_closure':valid('ApproachClosure1')})
    linked=copy.deepcopy(frozen);linked['configuration']['approach_binding']=valid('ApproachBinding1')
    with pytest.raises(ValidationError): validate('FrozenConfiguration4',linked)
    linked['approach_closure']=valid('ApproachClosure1');validate('FrozenConfiguration4',linked)

def test_bundle_role_path_and_hash_pairing():
    value=valid('ExecutionBundle5');validate('ExecutionBundleRead',value)
    descriptor=dict(path='approach/closure.json',role='approach',sha256=SHA,size=10,media_type='application/json')
    with pytest.raises(ValidationError): validate('ExecutionBundle5',value | {'files':value['files']+[descriptor]})
    linked=value | {'approach_digest':SHA,'approach_closure_digest':SHA,'files':value['files']+[descriptor]}
    validate('ExecutionBundle5',linked)
    for change in ({'approach_digest':None},{'files':value['files']},{'files':value['files']+[descriptor,descriptor]}):
        with pytest.raises(ValidationError): validate('ExecutionBundle5',linked | change)
    for path in ('../closure.json','other.json'):
        with pytest.raises(ValidationError): validate('BundleFileV5',descriptor | {'path':path})
    with pytest.raises(ValidationError): validate('BundleFileV5',descriptor | {'role':'context'})

def test_export_new_and_old_read_branches_and_scope():
    for name in ('RecordPreview','RecordRequest'):
        legacy=sample(D[name]);validate(name+'Read',legacy)
        modern=valid(name+'2');validate(name+'Read',modern)
        with pytest.raises(ValidationError): validate(name,modern)
    summary=valid('ApproachExportSummary1')
    with pytest.raises(ValidationError): validate('ApproachExportSummary1',summary | {'basis_run_ids':[UUID,UUID]})
    with pytest.raises(ValidationError): validate('ApproachExportSummary1',summary | {'model_count':33})
    with pytest.raises(ValidationError): validate('RecordRequest2',valid('RecordRequest2') | {'approach_summary':summary})

def test_old_closed_read_branches_remain_explicit():
    for union,names in {'ConfigurationRevision':['ConfigurationRevision1','ConfigurationRevision2','ConfigurationRevision3','ConfigurationRevision4'], 'RunHistory':['RunHistory1','RunHistory2','RunHistory3','RunHistory4'], 'ModifiedRunSeed':['ModifiedRunSeed1','ModifiedRunSeed2','ModifiedRunSeed3','ModifiedRunSeed4']}.items():
        assert [r['$ref'].split('/')[-1] for r in D[union]['oneOf']]==names
    for schema in ('model','execution'):
        Draft202012Validator.check_schema(authored_schema())


def test_receipt_results_categories_and_stable_error_shape():
    assert D['ApproachReceiptCategory1']['enum'] == ['approach_draft','approach_version','approach_restore']
    receipt=dict(command_id=UUID,state='committed',result=valid('ApproachDraft1'),error=None)
    validate('ApproachReceipt1',receipt)
    validate('ApproachReceipt1',receipt | {'result':valid('ApproachVersionSaved1')})
    with pytest.raises(ValidationError): validate('ApproachReceipt1',receipt | {'state':'rejected'})
    with pytest.raises(ValidationError): validate('ApproachReceipt1',receipt | {'result':None})
    rejected=receipt | {'state':'rejected','result':None,'error':sample(D['StoredError'])}
    validate('ApproachReceipt1',rejected)
    with pytest.raises(ValidationError): validate('ApproachReceipt1',rejected | {'result':receipt['result']})
    assert D['ApproachError1'] == {'$ref':'#/$defs/Error'}


def test_legacy_history_cannot_drop_config4_pin():
    history=sample(D['RunHistory2'])
    history['configuration']=valid('ConfigurationRevision4')
    with pytest.raises(ValidationError): validate('RunHistory2',history)
    with pytest.raises(ValidationError): validate('RunHistory',history)
    history.update(history_schema_version='3',approach_closure=None)
    validate('RunHistory',history)
    validate('ExecutionBundle',valid('ExecutionBundle5'))


def test_export_ready_scope_manifest_index_and_legacy_rejection():
    summary=valid('ApproachExportSummary1') | {'approach_version_ids':[UUID],'basis_run_ids':[UUID]}
    preview=valid('RecordPreview2') | {'approach_summary':summary}
    state=valid('RecordRequest2') | {'kind':'preview','state':'reviewable','preview':preview,'approach_summary':summary}
    for name in ('RecordRequestRead','RecordRequestResponse','RecordStatusResponse','RecordReceiptResult'): validate(name,state)
    with pytest.raises(ValidationError): validate('RecordRequest',state)
    legacy_preview=sample(D['RecordPreview'])
    with pytest.raises(ValidationError): validate('RecordRequest2',state | {'preview':legacy_preview})
    manifest=valid('ComputationalRecordManifest2')
    descriptor=dict(path='approach/closure.json',role='approach',size=10,sha256=SHA)
    index=dict(approach_version_id=UUID,approach_digest=SHA,closure_digest=SHA,path=descriptor['path'],sha256=SHA,size=10)
    with pytest.raises(ValidationError): validate('ComputationalRecordManifest2',manifest | {'approach_summary':summary})
    manifest.update(approach_summary=summary,approaches=[index],inventory=manifest['inventory']+[descriptor])
    validate('ComputationalRecordManifestRead',manifest)
    with pytest.raises(ValidationError): validate('ComputationalRecordManifest1',manifest)
    with pytest.raises(ValidationError): validate('ApproachPayloadIndex1',index | {'path':'../escape'})


def test_exact_closure_bounds_and_failed_basis_remain_explicit():
    closure=valid('ApproachClosure1')
    for field,count in [('approach_versions',64),('models',32),('configurations',64),('run_contexts',64),('evidence',1000)]:
        item=sample(D['ApproachClosure1']['properties'][field]['items'])
        with pytest.raises(ValidationError): validate('ApproachClosure1',closure | {field:[item]*(count+1)})
    context=valid('ApproachRunContext1')
    context['errors']=[dict(code='missing_results',partial=True)]
    validate('ApproachRunContext1',context)
    assert context['results'] is None
    with pytest.raises(ValidationError): validate('ApproachRunContext1',context | {'results':0})
    with pytest.raises(ValidationError): validate('ApproachRunContext1',context | {'request':context['request'] | {'guess':True}})


@pytest.mark.parametrize('name,field',[('ApproachStep1','title'),('ApproachCase1','title'),('ApproachAssumption1','statement')])
@pytest.mark.parametrize('blank',[' ', '\t\n', '\u00a0'])
def test_approach_nonblank_fields_rejected_at_public_boundary(name,field,blank):
    value=valid(name);value[field]=blank
    with pytest.raises(ValidationError):validate(name,value)
    value[field]='  Defined scientific text  ';validate(name,value)


# Public-only read metadata must never reinterpret stored history versions.
def public_validate(name, value):
    document = json.loads((ROOT / 'contracts/hyprn-mvp.openapi.yaml').read_text())
    Draft202012Validator(
        {**document, '$ref': '#/components/schemas/' + name},
        format_checker=FormatChecker(),
    ).validate(value)


@pytest.mark.parametrize('digest', [None, SHA, '0' * 64])
def test_public_retained_integrity_accepts_verified_or_unverified_digest(digest):
    metadata = dict(schema_version='1', results_digest=digest)
    public_validate('RetainedReadIntegrity1', metadata)
    detail = dict(run_id=UUID, command_id=UUID, state='recorded', receipt_url='/receipt')
    public_validate('PublicRunDetail', detail | {'retained_integrity': metadata})


@pytest.mark.parametrize('metadata', [
    None, {}, {'schema_version': '1'}, {'results_digest': SHA},
    {'schema_version': '2', 'results_digest': SHA},
    {'schema_version': 1, 'results_digest': SHA},
    {'schema_version': '1', 'results_digest': SHA, 'foreign': True},
    *[{'schema_version': '1', 'results_digest': value}
      for value in ('', 'a' * 63, 'a' * 65, 'A' * 64, 'g' * 64,
                    'sha256:' + SHA, SHA + '\n', 0, False, [], {})],
])
def test_public_retained_integrity_rejects_malformed_metadata(metadata):
    detail = dict(run_id=UUID, command_id=UUID, state='recorded', receipt_url='/receipt')
    with pytest.raises(ValidationError):
        public_validate('PublicRunDetail', detail | {'retained_integrity': metadata})


@pytest.mark.parametrize('version', ['1', '2', '3', '4', '4-mixed'])
def test_public_integrity_preserves_old_and_typed_history_responses(version):
    from test_unit_declaration_contracts import valid as unit_sample, mixed_record
    history = (mixed_record('RunHistory4') if version == '4-mixed' else
               unit_sample('RunHistory4') if version == '4' else
               valid('RunHistory' + version))
    original = copy.deepcopy(history)
    detail = dict(run_id=UUID, command_id=UUID, state='recorded', receipt_url='/receipt', history=history)
    # Absent metadata supports old servers; metadata does not alter the history.
    public_validate('PublicRunDetail', detail)
    for digest in (None, SHA):
        public_validate('PublicRunDetail', detail | {
            'retained_integrity': dict(schema_version='1', results_digest=digest)})
    assert history == original
    with pytest.raises(ValidationError):
        public_validate('PublicRunDetail', detail | {'foreign': True})


@pytest.mark.parametrize('name', [
    'UnitDeclaration1', 'ModelRevision3', 'FrozenConfiguration5',
    'FrozenConfiguration5Model3', 'FrozenConfiguration5Model2',
    'ExecutionBundle6', 'ExecutionBundle6Model3', 'ExecutionBundle6Model2',
    'RunHistory4', 'RunHistory4Model3', 'RunHistory4Model2',
    'ModifiedRunSeed4', 'ModifiedRunSeed4Model3', 'ModifiedRunSeed4Model2',
])
def test_public_integrity_generation_preserves_units_and_mixed_branches(name):
    document = json.loads((ROOT / 'contracts/hyprn-mvp.openapi.yaml').read_text())
    def public_refs(value):
        if isinstance(value, dict):
            return {key: item.replace('#/$defs/', '#/components/schemas/')
                    if key == '$ref' else public_refs(item) for key, item in value.items()}
        if isinstance(value, list):
            return [public_refs(item) for item in value]
        return value
    expected = public_refs(D[name])
    assert document['components']['schemas'][name] == expected
    assert 'RetainedReadIntegrity1' not in D
    assert 'retained_integrity' not in json.dumps(D)

# Structural wire proof only; identity, membership and authorization are proven by the
# approach service and API tests.
POLISH_OBJECTS = "ApproachContent2 ApproachDraft2 ApproachVersion2 ApproachState2 ApproachSaved3 ApproachResolution3 ApproachClosure3 ApproachPreview3 ApproachPreviewRequest2 ApproachDraftWrite2 ApproachVersionSaved3 ModelDraft4 ModelRevision4 ModelPackage4 Definition4 Preview4 Apply4".split()

@pytest.mark.parametrize('name',POLISH_OBJECTS)
def test_polish_closed_records(name):
    value=sample({k:v for k,v in D[name].items() if k!='anyOf'});validate(name,value)
    with pytest.raises(ValidationError):validate(name,value|{'foreign':True})
    for field in D[name]['required']:
        bad=copy.deepcopy(value);del bad[field]
        with pytest.raises(ValidationError):validate(name,bad)

@pytest.mark.parametrize('field',['original_question','elaboration'])
def test_polish_question_claim_bounds(field):
    value=sample(D['ApproachContent2'])
    for kind in ('human','agent','unknown'):
        claim=dict(text='Q'*4096,attribution=dict(kind=kind,label='A'*256))
        validate('ApproachContent2',value|{field:claim})
        for bad in (claim|{'text':'x'*4097},claim|{'actor_id':UUID},claim|{'attribution':{'kind':'system','label':None}},claim|{'attribution':{'kind':kind,'label':'x'*257}},claim|{'attribution':{'kind':kind}}):
            with pytest.raises(ValidationError):validate('ApproachContent2',value|{field:bad})
    validate('ApproachContent2',value|{field:None})
    with pytest.raises(ValidationError):validate('ApproachContent1',value)

def test_polish_limits_bounds_and_semantic_counterexample():
    value=sample(D['ApproachContent2']);value['limitations']='Original.  Unsplit\ntext.'
    limit=dict(limit_id=UUID,statement='Bound',evidence_links=[sample(D['AssumptionEvidenceLink'])])
    validate('ApproachContent2',value|{'limit_items':[limit]})
    for bad in (limit|{'statement':' '},limit|{'statement':'x'*4097},limit|{'limit_id':'latest'},limit|{'document_id':UUID},limit|{'evidence_links':[{}]},limit|{'evidence_links':[sample(D['AssumptionEvidenceLink'])]*65}):
        with pytest.raises(ValidationError):validate('ApproachContent2',value|{'limit_items':[bad]})
    with pytest.raises(ValidationError):validate('ApproachContent2',value|{'limit_items':[limit]*257})
    # Unequal objects sharing identity require the43.2 semantic validator.
    validate('ApproachContent2',value|{'limit_items':[limit,limit|{'statement':'Different'}]})

def test_polish_reference_closure_no_documents():
    assert_execution_schema();seen=set()
    def walk(v):
        if isinstance(v,dict):
            if '$ref' in v:
                n=v['$ref'].split('/')[-1];assert n in D
                if n not in seen:seen.add(n);walk(D[n])
            for child in v.values():walk(child)
        elif isinstance(v,list):
            for child in v:walk(child)
    for name in POLISH_OBJECTS+['FrozenConfiguration7','ExecutionBundle8','RunHistory6','ModifiedRunSeed6','ApproachReceipt2']:
        walk(D[name])
    assert not any(n.startswith('Document') or n=='EvidenceSnapshot4' for n in seen)
    for schema in (SCHEMA,authored_schema()):
        Draft202012Validator.check_schema(schema)
        for definition in schema['$defs'].values():walk(definition)

def polish_model(version):
    v=sample(D['ModelRevision'+str(version)])
    if version==3:v['required_capabilities']=['unit_declarations/1']
    return v

@pytest.mark.parametrize('root,ancestors',[(2,()),(3,()),(2,(3,)),(2,(4,)),(4,()),(4,(2,3))])
@pytest.mark.parametrize('approaches',[(2,),(2,1),(1,2)])
def test_polish_matrix(root,ancestors,approaches):
    closure=sample(D['ApproachClosure3']);closure['models']=[polish_model(v) for v in (root,*ancestors)]
    closure['approach_versions']=[sample(D['ApproachVersion'+str(v)]) for v in approaches]
    validate('ApproachClosure3',closure)
    for name in ('FrozenConfiguration7','ModifiedRunSeed6','RunHistory6'):
        value=sample(D[name+'Model'+str(root)]);value['model_snapshot']=polish_model(root);value['approach_closure']=closure
        cfg='source_configuration' if name=='ModifiedRunSeed6' else 'configuration'
        value[cfg]=sample(D['ConfigurationRevision4']);value[cfg]['approach_binding']=sample(D['ApproachBinding1'])
        if name=='ModifiedRunSeed6':value['runtime_comparison'].update(state='unavailable',current=None)
        validate(name,value)
        for old in ('1','2'):
            with pytest.raises(ValidationError):validate(name,value|{'approach_closure':closure|{'schema_version':old}})
        with pytest.raises(ValidationError):validate(name,value|{'model_snapshot':polish_model(1)})

def test_polish_null_partial_bundle_discriminators():
    for name in ('FrozenConfiguration7Model4','ModifiedRunSeed6Model4'):
        value=sample(D[name])
        if name.startswith('Modified'):value['runtime_comparison'].update(state='unavailable',current=None)
        validate(name,value)
    h=sample(D['RunHistory6Partial']);h['errors']=[{'code':'missing_results','partial':True}];validate('RunHistory6',h)
    for root in (2,3,4):
        value=valid('ExecutionBundle5');value.update(schema_version='8',model_schema_version=str(root),required_capabilities=['flat_explicit_scalar']+(['unit_declarations/1'] if root==3 else [])+(['quantity_definitions/1'] if root==4 else []))
        if root!=4:
            value.update(approach_digest=SHA,approach_closure_digest=SHA)
            value['files'].append(dict(path='approach/closure.json',role='approach',sha256=SHA,size=10,media_type='application/json'))
        validate('ExecutionBundle8',value)
        for tag in ('5','6','7'):
            with pytest.raises(ValidationError):validate('ExecutionBundle8',value|{'schema_version':tag})
        with pytest.raises(ValidationError):validate('ExecutionBundle8',value|{'model_schema_version':'1'})

def test_polish_projection_writers_numerical_protocols():
    api=json.loads((ROOT/'contracts/hyprn-mvp.openapi.yaml').read_text());schemas=api['components']['schemas']
    assert 'case_context' in schemas['RunHistoryItem']['properties']
    assert 'case_context' not in schemas['RunHistoryItem']['required']
    validator=Draft202012Validator({**api,'$ref':'#/components/schemas/RunCaseContext1'},format_checker=FormatChecker())
    for state in ('unlinked','unavailable'):validator.validate({'state':state})
    linked=dict(state='linked',approach_id=UUID,approach_version_id=UUID,version_number=1,case_id=None,case_name=None);validator.validate(linked)
    for bad in ({'state':'linked'},linked|{'version_number':0},linked|{'case_id':'latest'},{'state':'unlinked','case_name':'x'}):
        with pytest.raises(ValidationError):validator.validate(bad)
    assert api['paths']['/studies/{study_id}/approach/draft']['post']['requestBody']['content']['application/json']['schema']['$ref'].endswith('/ApproachDraftWriteRead2')
    assert D['PreparedModelArtifact2']['properties']['model_package_manifest']['$ref'].endswith('/ModelPackage')
    assert {'$ref':'#/$defs/ModelPackage4'} in D['ModelPackage']['oneOf']
    for name,version in [('ConfigurationRequest4','4'),('ConfigurationRevision4','4'),('ModelingConfiguration3','3'),('PreparedModelArtifact2','2')]:
        assert D[name]['properties']['schema_version']['enum']==[version]

POLISH_HISTORICAL_HASHES = {'Source': 'ced46ca6ae852ed5a1d751eac61c8b2eb5598219ad26fdd9ef29b5f67b4bb82f', 'PortDeclaration': '56ab596fd71b2bc1585635981ec3d3d568ef128e1ccd6a5de51cebce35e4ec63', 'Port': '49b80078c779dd026d52c4bd53dacbc22d4c0749b47c2ce962ed604332925aa3', 'PortRef': '74ce0d29a65d8ae2a6b759ce74c60657137af3516b3ab9336610da8bf9073c75', 'BatchPortRef': 'e2beca074f11dab9ba8f46b70e85c8d81a326ef7349ebb708ef8d3c033f93667', 'VersionRef': '3f0ce608e3f5271ee7d275bc88a7fc138d4f45da1083f1aae9e295c0062907e0', 'Annotation': '74b3a8f1a880bd127c6ba1111dee20ba2ff94c07c482d41b8475fc38e9af1d8d', 'BoundaryMapping': 'e47b848352c27df7e23871978c4d172331d82a80df3e0762eaece87a7eb84f98', 'Instance': '89205571745483f8589bf60e3934a82f89c4c1eec67ea2cd533ed97f5bb8313e', 'Connection': '6bc9927a5919411a388d0b15588db9ad24041489f95c17b98436006ddde60ea7', 'Definition': 'e5d387b44f62e09b89b8646605d97082de8b2eb9d6eec77a9d50f5b4cf5fe865', 'DefinitionChange': '9f8f3cee850e038b9f1e2d86c31a851d62dd9459199bbdc32a71301c7f010313', 'Edit1': '465edcdf3c343288888f103b0da68e262f2dfb18d4c48d7def75c94e991a3586', 'ModelDraft1': '8c55ff429d90b1040e0261dd4e9e11cbed58b932733edd537d622f366779b34d', 'ModelRevision1': 'acc65cb1e1c564e854c9e0b5d4b625c490644500bfdf0027f6d57a11cb5870da', 'File': 'aa4e89b13803233cae94b4f45ca642c343fdf513315ad54829ca91ae810d5d0b', 'Generator': 'ca5d842610ff173ed82f35029d6e11222e0329c5d880dc9dce52b6f21c987f82', 'ModelPackage1': '9a4320db766612b22f0ced8dfa5665c90ed5c8da196b5db7635aecddb7a3df76', 'Scaling': '508e9b6b2cdad53acf16b9710b584965172b6614e5ec7db2bb58d774cdb54bd7', 'Numerical': 'd4d8aa9cb6d742747d5480c6ef3bf83e223aa6228a80726b4f73e05a04361fe7', 'Input': 'a7218e38addee8bcf308b9f15fac0685de8228a0da952e9b3d419bd75d83a0b7', 'Criterion': 'cc48ccaa2550b6d2c2d0420577530641d6f032addec69ef4ccf0afebea297882', 'EvidenceSnapshotLegacy': '539ed60f2255d146000fad995acfc565a4a04e7be7a97d37b52e57c9968741b3', 'ConfigurationCandidate': '1aeff97303821c30d95fb56277bd73a610dbd89042089307dab49e59560aef30', 'ConfigurationRevision': '5c0bbf520c2d73f760d435bdc1bee766ab54fa516afe7534071c55a632e61633', 'Diagnostic': 'de493804cade9a2728706278478ca78078245a2cd178fbc95bfde9a54a03553f', 'CompatibilityResult': 'f7e00da28291749f1acd0058d4342615b8d8dde7b254feb3e79d7c0694d8ad6b', 'PreparedModelArtifact': '1f82dddac0da126c1a4bda1469f02ec35da21d76522d7e8b2c5a22da394dc73e', 'Error': '382da9d27bdbb3394eb1e3ff666cbca937ba9626f7ba3ab04bbf542bbd5c71e1', 'Create': '733f7f91911df862c1719969dec94cc581a38fd46187656d4cb5b00362d7925c', 'Apply1': '2ea2639223534cd50e01babbc0e4b5c47bb9d65fe7d81fd85ca885959cd4550d', 'Preview1': '52b97f395c14717f88fb25661c50d24895e4e6307115e8e651f3fddbd85ccf35', 'Commit': 'fb87a86960aa031383d48563553a1f8be3355ffb2e6489ff1dafb5cc64ff15ed', 'Validate': 'daf34219969c877d74826fbe2b41a0b0d38d20e66990923f3219fba4681f4248', 'Compatibility': '73cfee3f47f30a20e8a5ff605ac5db73d278ef858507b6022ba455d39137a995', 'Prepare': '8bc2b11e3b90636eb6869b46e98d0541e1ac84598d5860c1e2f91b2bc26d0e3b', 'Import': '91c1c4967a6035c5d85bc6b5c9bade60355f025a0ed23cb3a3aadde8f8cba31c', 'ByteFile': '8a76ba323d5b67529ea0e525a1704194d559737bcfe221b0a2532127aacf58e2', 'CreatedIds': '608bb1107a10a388a914495b1de57ea39dc839ae437dab6b50f03156d80ab851', 'ValidationResult': '3f3cfd2f47c00766fd7feccb796178b83179b25438b9f306fa73f173a7b1e056', 'Capabilities': '0fa51e265c30665074cd3574f28800f70a4743f409a2ded405be24ff14985ab7', 'CapabilitiesResponse': '0cb052678f6a7b1df7b18f5e127d6e35003f51618e1f88969f789956d880ea0e', 'ModelDraftResponse': '7d1804f64ee2a7101688c03e15387e1a107121354527367c8b7fff76b99c1b95', 'ModelDraftEditResponse': 'cd2e1d443d24a8a4ff87c72a9875a76f583163ab7326a7a64f6b2a8edba59192', 'ModelRevisionResponse': 'e4a668266e58c4221d0823c4fb662f650f6718272b7e158e50b6238d471716e6', 'ValidationResultResponse': '3358c31c8863407f54bd5768e9baf8e641ea05af6a030edd45ed6ba51f4300c6', 'ModelPackageResponse': 'f087cad877e098dc45be64105b9e398c6ab88158a63f40584625d6d45b524778', 'CompatibilityResultResponse': 'd547d4132a9d84ed2ea7703e929998cd15b4800f78997ae66e4cf0ca3a781592', 'PreparedModelArtifactResponse': 'bc90ca8a58621fffdc48a7cc4891aa7de3cf09def1adc75005f141146f2103a4', 'ByteFileResponse': '65dc65b072de2311a0b6b82169782f4e834f23c26c02c2eb97ef82bb44ef26c8', 'Receipt': 'c757621ce3e2d87b5d2861ade2d328faa699b674314b481ea95e24111e909f8c', 'ReceiptResponse': 'a984cc465a8eb8500f4e7f4240038911afeb9cfbada34c1d0acb454fe89483bb', 'ProgramEntrypoint': '936929ec4455acff3c69a523c47690644a9dbdc26139e31057273a3f36513d81', 'ProgramBinding': '01105ccaf3b2edcb9de35c784628cd4336abe9817a9e035af1aa0623b9b00c80', 'ProgramComponent': 'b5fdb26e919c6882526d18c7de19ac9e9e7c55e094e01214ff182c7f23f9df31', 'ProgramBindings': '2785e55f2630ffb93e74475abc1dbe07dc0306e76eb73c01df046438019d9c9f', 'ProgramSourceMapEntry': '32be108cd98b45ce2f7d7997fb4e8c127b3cf7d692b7b798eea59b04b6503325', 'ProgramSourceMap': '42a4760dacfac9da7dca2f65adb0ceb84dab8998acf952cfc47e4a6efdb57c32', 'NativeGeneratorIdentity': 'b628ceeaa63f2fadb67776e9bd3a79eaad0decf4d1160505d4bf78b22839dcb5', 'ProgramProvenanceFile': '28dea0fc6c4270ae01286e47696f20f09e1af309030bfd1b64c332e7af8cc2f3', 'ProgramProvenance': '322fff4704e7fd8231235b03c0d5ec598a78e71535634a14a89949e6f0e35fff', 'PreparedFileV2': '934287a159468f37bce907650829bccffc67650820f2635f739f6c9d90266c8c', 'BundleFileV2': '9cf600059917899f82aa8b11f9c37adff15a60be6f376111110f059422232750', 'PreparedLicenseNotice': 'f06a27c47b58aa7181b7a47ab3e4ef98cc3c768f0917948e329bc5fb63b54a1f', 'BundleLicenseNotice': 'a4f340d4f16a79e1ba5ea90c3d5ad726e3975d7277f9eed36fc774171f4b8a4c', 'HistoricalPreparedModelArtifactV1': 'd05671106fe4371ea5e370cc51ce91ecbd8e26f528f24ca9f6532d6e439ba8cb', 'PreparedModelArtifactRead': '2304fe79566c1b37ec5a3a838debb00e132bc65459f80f058e7ddd0bfb08f2a2', 'ExecutionBundle': '16abc56587aed93fdb5878bcac938859acf50c18de27bde79662bc2469482c1e', 'HistoricalExecutionBundleV1': 'fb2627608837dcf164cd6f3ff5adb007e827af1d0708445b753c6c9df9d2fe72', 'ExecutionBundleRead': 'd7b2d46e5e6e93707061dce3156bef62b472e51b84754f3f1ec18c831dbddc9c', 'ExecutionVersions': '48c450faf818dc3eaf2210e382498bc2e9d0d1618581688b91bed78def5da21b', 'RevisionSummary': 'd977a1ce2e8085551630b73c233f470f290bdeb81fc38518c83c996be28a68aa', 'RevisionList': '0b85450182d206cb98129592759599a1c38abf2078353a25e76b5ac226420a98', 'RevisionListResponse': 'b0ece19323f97389d82b16cb8fa0128d2b844fefcb57fff6f0ae786cb54a3412', 'EvidenceResourceRef1': '5a01c351aee60f0ae08464ac79668f2c1fa6afeb50e2f3a8337c717e23171f83', 'EvidenceCreate1': '156e1a35a3f9fef55c4536ae44efc7dbdfca5113d6dd08542c4002bef9ac89cd', 'EvidenceRecord1': '6c8ab1a9833f640967e4557d6479c23a851c941a70a7dcee5b8eb4cb8a9d40d8', 'EvidenceCreate2': 'a89c3402d427873e77322bd4a4b1deb2d16d2cbc438fda1ae3e40ba0a7f19242', 'EvidenceRecord2': 'a35f4cf01e93329de8461bead7deb77afdf3d466b58f7b1e9f7c3d9a701544fd', 'EvidenceCreate': 'df70832615f3deb2d81be59fdbd09a74fa94a4e169024e6e4f61d89b10993c15', 'EvidenceRecord': 'a045071d21f7c39dcc0c85aa7012976b762a75ff0f0f5cc82553e7e312293afb', 'ConfigurationCandidate1': '64de96a5eb2bfa28c82bd948bb4831244dc46365d9449fc0d3364c0fef5c50ec', 'ConfigurationRevision1': '16e407c82ac644e8d19c5947cf0786cc2ff70d55ebb3cbeee8bba43e1f0ed7fd', 'ExecutionBundle2': 'adc18ac80f58753bbe8c62a87ee4cb7feef74f2199032190f467cc40d04fb687', 'LiteralRequest': '74ff8e10f6c02d4f68d5cf523329adf114ff960c393a8eb9dff7b7e9860f2274', 'ResultRequest': '1a4de76cab2738576a66e813ecdc8ee270dbcd9a27745a7a3b7b5681305c94bd', 'ContextSource': 'ac419693eeebbe163cab40eb9068fc4f0472819c8672e95a666de22e12a6bd76', 'DerivationRequest': '37070c919264e5491a7575954230e709310f362bd481d64c94688056f2c4882a', 'ConfigurationRequest2': 'bcf56d309488c4de12f61b046c673d646f95b40e5e50fbfd18d74d5161c55041', 'UnitInterpretation': '2e6140156325d520bc604145b410037cd56c8c0cc4058a7deea3d585abd78604', 'SourceLabels': 'd92aa7bc5e24b0ea3f398ff798ac8d1680f6aa03e34b2865b5e8b11dadbd1b21', 'ResultBinding': '40531f5ad0852b509944fe2df10745da884a9209ea5e406c3f54f83e22253112', 'ResolvedInput2': '0ba1549ac3914a6a7b6526fedf000541593e51aafb7a40d4400f3b7e5196c85a', 'Change': '40d4dd6a4cd2ef96719341a96756c9acdb408da7ff03600a41604600418bad97', 'ChangeSummary': '08f06656c4f8bca8b11ffade2851b08756febf58859692d6508bcc3c6f9c87c9', 'Derivation': 'd9e2bca3bf0e0e9c49c2234e7664b3458b958934b13b8b99023704bc2dbdcfa3', 'ModelingConfiguration2': '5fa2da16ca652516f663e83725365beb0ef7bf3b88dcd3378299f5867f25341e', 'ModelingConfigurationRevision2': '16b96c1d913cd1ec945a5b8170a9e4b580c0d285d9b30632c7067e955a98a790', 'ConfigurationCandidate2': '96ce1423ec8b8f7287ffa5c1268e6b2ebfa38096bfa27f80292b9fa15e29d763', 'ConfigurationRevision2': '51c1001878b212c7c449516eaa9e1199dff57e89e45a50c8fb613a074f5fd966', 'RuntimeComparison': '583a7f51e27ded351c3a78b31e78a1ed27d859f10c6b72c630c395ce46cbb31b', 'ConfigurationPreview2': '7d17db370162a282f90d8be57b294568f71ec3e824ba2641b5035877f50b9f71', 'ConfigurationCommit2': '66b0b7b1569b31ba3107510828709db001af7763bd37af303f0720a6b3ce76b6', 'ModifiedRunSeed1': '97c4498c67a98e693815e67ecf0456fdeab4a06145d3630ff131e16036fecdaf', 'NativeSource': '2e283b02a13a7a87d256a17ea2a376eea1218c7d8388ace7e0de24e5dc46f662', 'ScalarMapping': 'c37cc671abd32788d382554216af37fe68eee2b638b994ea12c24270fe4a251b', 'ResultDependencies1': '030603bcb89621718a2c06991937769afe7c07794e971dc619f129108c08d821', 'BundleFileV3': 'b3b4ffdc7de249bc505537c47297b7b9c175e27645c2608444d1cce20651c954', 'ExecutionBundle3': '137670a8922a147fa370ee21b7f7d6e05a8df7b02047af0093a65dae92ab0e8e', 'ResultSource': '35c90ed39d74cdb45e01bbe40ea480c62fb179608a9198d9d7806f5a71565ae6', 'ResultSourcePage': '1ff43c6b6c03217c3350d849694a398855429cee994ac3af8d69deb38896dae2', 'RunLabel': '63ab57dc9351930733b5369cc04addc464fe0c0f409cdfb0b145ad18acff7daf', 'ExportLimits': 'ae895314b0ef098cf7e2b0986ebd93440b035d67a4a253c04857ca12acb2269a', 'ReexecutionPrerequisites': 'f81a698a240d2bd7b3a971c7432bf9acc7e830e24e3bf86070d43a6e05520315', 'RecordPreview': 'a5493c53f8c3bd086b79cb59cc36de197013ce1b847b9a6d624cffc4edd85450', 'StoredError': 'dc82fac09254d5825936901f8703a951342802b8e1180c7e9fb05dedc0c2762f', 'RecordRequest': '3fe942f629601d1757b2c45dd2ebce8e42acf3319a82887541a4ccee7b009a6e', 'RecordPreviewRequest': 'cdde744e1667df8f8d9a3cf1862beeb5a710a9c9e9dbaf335dafd688f73af860', 'RecordCreateRequest': '521e543185c785604edc089c26661bd0b4d1740823de676828363c1ebc4a938d', 'ArchiveRun': 'e3907e0c8ac12c51afb99cb88bc2765fe8f75a67f52d7ee22b70ec3c7e52b0cb', 'ArchiveRecordRequest1': 'b301026b0559c38f53e469261bd66067e0d96a5bed074987dd8c3cd8993c3bb5', 'NodeInventory': '3b35278fef1261ce6084ef8be5a6a2207e5b0cf50ed12fd40dc161c7e9640a71', 'LinkInventory': 'eb45f8c3025bacc973b73cc2ca6a1642423f0c5fca4734518033af5ac530d9be', 'EntityInventory': '9ebe15c36f4ab172da018cc8b85ef5a5c9ea6aec9868e63bb342214161c2cce0', 'RepositoryInventory': '12c138b182d18c42fb5f685e3a1f746d3062e585b9c0188b7dd5dfc0e9b0624d', 'NativeInventory': '4414b0f436a560a5991fdc7285804bb839db4f24eec996d12d8558e60390db35', 'ArchiveRecordResponse1': '7f1e89e645b102334c001bed2cbe66fea1a909c0da7c9180dea240ed3fb957e9', 'RunMapping': '0931ef8571b8826d7cd98e4eea9989a0515d63b5df0f387c037dcf835ff5e0fc', 'PayloadFile': 'ed9d09fd142c8b0f3918f9339c42db9836607003cb4397e816a246d3a26b68ea', 'ComputationalRecordManifest1': '274d2a6ed5e8e7619c636643770245f108b54767e34c3b35d8de6d5d371ab404', 'CompatibilityResult1': 'fdfe2e46fc16b158fb3c24206fd4756e03c5928a784acbb275ecada247e29f13', 'InputInterpretation2': '43935d26c2167bd395e42ebc0173738d1d86230ffa17ad5296c755ffd536638f', 'CompatibilityResult2': '43b32e7d9b6b232d1b73e98eda5e694bb9f610aa2333a73e086e30afa92ec212', 'Edit': '6cf0929275bfc4f8de41fb5f9f3935c3e2a96339d91c4d6f1498a151345a8890', 'ModelDraft': 'cb5c69c915253edc68537c6c3543918c4d59ce4665b640a06fa3b5cfbb481d90', 'ModelRevision': '5da7edcc783b6ab0cfca719c6742aa4d4d6ade32d2e5f540b52414417b3d5ffd', 'EvidenceSnapshot': '72f16cad3ee2fd6b7814cfa8a8eae943fde1e19b9747c6546aa8cac228a85259', 'Apply': '0b4e778f526ba4c4f094a70068e6cefb7776b42a609b653aba74f18b45ef4be6', 'Preview': '6d63e20421105db199d708e73e7734ed5bcd485da719f9977ba11a00a8411527', 'EvidenceSnapshotRead': '72f16cad3ee2fd6b7814cfa8a8eae943fde1e19b9747c6546aa8cac228a85259', 'AssumptionEvidenceLink': '7c78894ac5323f63b6883aab7f826706470c736c41d059523562575b9236b7f7', 'AssumptionOwner': 'cc6e28324e5889535ef81fea2d7f8b47026f286ba47ecb1ad1cf97ac80352b37', 'AssumptionBatchOwner': '5e02ecc2e9a2186c01c2214d51935dd2740dc674152f1995860c66fa60417d15', 'ConfigurationAssumption': '9df47d73221d1e7fe83f251f918ea61bafadb35d23af1da51297efc4bbcb329c', 'ModelAssumption': '1689c86ae528cc28f164e12e1ef2fbce73c3fa4008646088dc94b442515e7320', 'ModelDraft2': 'df67fb67d1ec7c867f3e7b9700f7edff3c80c316dab50f1c2e58a5306431f2ff', 'ModelRevision2': '0fc0f2ce72645664fd501c57aa48c201b8eb53704a19a7403e506d45b0d2ef1b', 'ModelPackage2': '426c77077c6a2f11d1b6c9ceba589a44c47d21e82045939b3fa8b68512b9c3b4', 'Edit2': 'a48a09a8e089465a4594d65a84589dacc0dcb2269692f84893d83ac88544bdb2', 'Preview2': '81d1af2530d0908f452481c2044a6103812b93c9c6ce029a46b29c5705b19d2f', 'Apply2': 'c971b06c5f86597eb0eff54b9e641bc72a2f070019e19a00d6540d6917fd3954', 'RecordedResourceLabel': '2f1a1234d89899368a403b801c87d50a98889ae86cac2529c3bf55d16a0c0099', 'RecordedEvidenceContext1': '34b563cfc72dd15f9674a0e29ada8ccb9de343b14b6d920736c0cbd84b3216c3', 'EvidenceCreate3': 'ca784df79430d9ec9af518d4b37e751a778211d1453f5cfb55ab537bd683c647', 'EvidenceRecord3': '677aece7cce85ff4408b599daf8048716bb41330da64a33fba7db89e86db209d', 'EvidenceRevise3': 'dcc757743dcd0232d3ec34b076b26f53c6f6ca23e07bedfda892bf8a71cc2256', 'EvidenceSnapshot3': '677aece7cce85ff4408b599daf8048716bb41330da64a33fba7db89e86db209d', 'EvidenceRecordRead': 'a045071d21f7c39dcc0c85aa7012976b762a75ff0f0f5cc82553e7e312293afb', 'EvidenceFamily3': '401fc81e3bc3c65ffd95a918a02f708e991631f31f3d52b926a0a380182067f6', 'AssumptionEvidenceResolutionLink': '3348b97366771e8a9bc949c829abf3aa32709aa3c939b511d28a092186051f9e', 'AssumptionEvidenceResolution1': 'fe946fd62b7e5a78a10e5b35fddb591dcf5a2582ec37dcbbcf6865533d48b83d', 'ConfigurationContextOverride1': 'a4ba24402a5dc941a94c438864337425e0e628227ee69f1b322e96895276555d', 'ConfigurationRequest3': 'cd744b3f1f086c7909a019564c077af9242ec367afb3c40e9a6ec8dcc5c9997e', 'ConfigurationCandidate3': 'bb0f5336d203398cf11295b09da161009713596c06e17f78a76af2b2db20924b', 'ConfigurationRevision3': '3edd9b01d85918a4924ef05aeb48074997ec441b0626a0a7be8be853b745fa4d', 'ModelingConfiguration3': '94e64fd2d34908f4651acd1b29acdf2a79151f034f3eaea22f15dfe78d533fb7', 'ModelingConfigurationRevision3': 'feadf4f58d91023d25d0ea723382a7ca9705f5925bcf0434c140ac84e356901e', 'ConfigurationPreview3': '2b63d306847e24f00b8ce876bbf08acf8b2b3ec620194b159e0571fab62e5d04', 'ConfigurationCommit3': 'c2c8aa10f4eee0daaa14847d3c064fd86e7febfe0a0a8cf01773918a63ddecb7', 'ModifiedRunSeed2': 'f7569a9a0267343ee13cdbda66fb4e2c9e6829dbda3b7a63b7d3dfabad84adb7', 'ModifiedRunSeed': 'e36d0c75da89ea0353d7ba294d695cbc8c9e152d4e9de44a1a96e7e03051b9d4', 'ExecutionBundle4': '33db999aa28dd4f8eb94a5036eb9a663eec57b478472eb6c596fa4b9b0361a88', 'RetainedOutput': 'eb3af0bae6132d8c9008ac4d1203a626e68c7e03ffc5906abe56d33a2e0b42b0', 'RetainedResults': '8008eb3a4af63906fc2f4b6e31d36f319cfd454c70272b60f73ea82305ce4ad1', 'HistoryArtifact': '9d0aea8766c93ef9986e3c100b50b82fa1a2dbd72f89de887e69a5be5d822bdf', 'ConfigurationRevisionLegacyRead': 'b149a3fc3b35f0b3358a7dd6342955b7f9899e4a353514e83dd576371dee417a', 'RunHistory1': 'c6be84203a17c76d8eb6a5196f76a2fa0e741b7d68d6dd87d225b02f9686896e', 'RunHistory2': 'bbe838c6eb644162df3ebcee230afca9f5067ff48f4309c99ba09051615dc716', 'RunHistory': '0d02d93c7990d0aa60d580505c8cbc6ee92cf4894d5e68fffed85afa6de70bca', 'PreparedModelArtifact2': '1f82dddac0da126c1a4bda1469f02ec35da21d76522d7e8b2c5a22da394dc73e', 'EvidenceCursor1': '41d9b5db9cb57ed132f6c7a3847896c45d16b788bcce27898271c8000a5b201f', 'EvidencePage1': '552b1afdfa14033d1c5a05979013e05242fb49da1ad37d65fd3b77a86f22add1', 'ConfigurationCommit1': 'e19899c1b7ab4110b0bbba2342b481a959bfefad88dc0338162c564f050bf099', 'ApproachModelBinding1': 'ba704016b0a4d6cc13e923f52c16cb736471664e37846a1d104602fce0522633', 'ApproachElementRef1': '773a300084e2ab3ae213fcd41d20ba684b443e0c8936a753440ffff7b5087fed', 'ApproachEvidenceLink1': 'd4d1a8c1f16925e1360670f3a659c3d21eeae2065b6d6cb349fc28c8835fc58d', 'ApproachAssumption1': '0763376c2420afe14aa27682369c6b3b2c9ee83dd2c5ea855f703477f4b832c6', 'ApproachAssumptionOrigin1': '28593efaf6579a1e3bdf4381b11d0134d282a707a7f3c04e9898660fc0b24d09', 'ApproachAssumptionRef1': 'c419f94c254c2d2adf4e6db687dc451d2b4936f7d5975eb6b1b235075815f86e', 'ApproachIntent1': '2db4a2d7a0eb6031032efdab42cb82298dfc580389b57ba3f5cd094a1d7788ef', 'ApproachStep1': '12ad0840cf54b429733564662060d24e4d48c8d25a3b2044bcedb0a58286c69c', 'ApproachCase1': '7ac2f72c0aa1f6b370fa440ccbf40be6bbbae709cd34e1a8189864ace8606f59', 'ApproachBasisRef1': '3bbf7b8160c5ab0bd9d2c15259b2608459a6066262e8aac1318206af92177a16', 'ApproachContent1': 'd144a40f729299b2096ad046853587eec4466fccfebf3c339d109edfa2b9d288', 'ApproachDraft1': '2d28b00daf35947b6a9df14777fa6a1b1fefaa0f404d339255991bf45f1e738f', 'ApproachVersion1': '8ee8aff345d7facdd423fd8e9319d97f0f424d6aba252d6423ba3343975ec8c6', 'ApproachVersionSummary1': 'ce26352eee1fa8829f11da7c701b61661fff8c4d115e88138df2d662cccf48a4', 'ApproachState1': 'fda61b11df8d0a32ddcab412a7fbf74195cd7d3b186bf800b1e014ce8c7cf156', 'ApproachSaved1': '82a61542c0142b4bc7981331506e93fd63977fa6251e0032a66ed08070fa9972', 'ApproachPreviewRequest1': 'd7bef8efa48efde2a28b1a86ab47400d99903d2ec87e596cbb5fa6bb31cf5963', 'ApproachDraftWrite1': '642c82d720ba6d3bff26e649451a578684038100c48a9343ecce0c0c83e72ef2', 'ApproachVersionSave1': '3d4b878d36368287a98fe47b4b0db854ce0674e9e1dfadbbda6443735ab68701', 'ApproachVersionSaved1': '6e458e7c531d77f2fc1d5da8121ffdfcbc5ea39471e287616aca4f00baa3b183', 'ApproachRestore1': '30228dadb7898e685ec34bc8e87f52562b32e2bbeeacce7c5f95e4907da06583', 'ApproachCoverage1': 'ec916e9d4a1d36c6a230e085d2434bbf923f1c4a985b559654ae434d52c7ee12', 'ApproachRunContext1': 'b50b3f8749ad664d0bd179d2258e57a366b6a0919c32cde587d4a4ba68a5ae4f', 'ApproachResolution1': '23d76f5aed637a125416a2464b379502054e89ef97a06c0cb1871afe5d7deb94', 'ApproachClosure1': '7410f710f16d9a5d80480fb443eaac14deef120d804632c3d3116d3c17837257', 'ApproachIssue1': 'a431290f73434d5893f8c9159602e293c0b4ce3a10dabe4dc22f8645b2696bea', 'ApproachChange1': '3f27bfd86691d6d038bded5fcf8a94b07fe3b9a626eb52ff6f96e18d7946903f', 'ApproachPreview1': '267fb41a3dbc10101fae4b1efd57e7dc06bf23fcfd1cb8da2496e4e0eca73761', 'ApproachCursor1': '4534cf012a3c1ada7563f49b531a3273293b535f6f670e5cf71ca25c947c3a75', 'ApproachPageRequest1': '2be57e41a6b6dd7c1ba503b917ef999a6856611e8948271c3f00eb77a2479298', 'ApproachVersionPage1': '60addf4b2cc2a19081226415a84ab87fab28daeb4fd7705e5c8d70a70e72112a', 'ApproachUsage1': 'f3b7c09213ec8c3eb303cb3f4c537973d300e11728726a37235ef237781c2a3f', 'ApproachUsageCursor1': '11611ec859f75bae36f2f40147180737bbf347759de06bfd477b692b1134ca6f', 'ApproachUsageRequest1': '2f1b64d068dee1ac709aee33864691b74e76fbd367ebe02e45318611c42fc456', 'ApproachUsagePage1': 'a7127851e0dba7ccd37c72ecfed16e0873d89d47aa491613a2981087a08504cc', 'ApproachSelection1': 'fb2bbc53d4eb01c982220f93f6c9df198ad9ed362771e5791f60e4c020124f3d', 'ApproachBinding1': 'a13bbf89b35eef2c536d65ec03177ae2ff7a3feb93c2e05a3e74029852358821', 'ConfigurationRequest4': '90e4f682353477b1065468d96c6ad52c375fd32a33d74d99a93a40726ab0bffa', 'ConfigurationCandidate4': 'd560d934ce9d9978f76e07b869df7d4df4e7b037cae8251dca9c9292344c6ac9', 'ConfigurationRevision4': 'a66eb404258ea49ceb202c64488f9c7cfb92cc685a120f8db7e853205b96f7d3', 'ConfigurationPreview4': 'fb38e83448675cd71c4d1d3a7d6001673b91929e1631914eb480e3048d5a704e', 'ConfigurationCommit4': '9442433f8e76be2b5b125b588d726d55ad764949314244a71995de700c41604d', 'FrozenConfigurationLegacy': '1373c7e0b1e6784d282b6c9c7af90fde2fc38df7d6a749edfb370d6971ee97b6', 'FrozenConfiguration4': '02c93f3963141c0c65652759904e8eddfe62bf65eade648236014511928dee40', 'FrozenConfiguration': '8574b45520d271b7ad2b818aa2f35493ab72ef877f1c6bdac0d7784e14cb8448', 'BundleFileV5': 'f6f278906042cc63db0166bf185372eac351a6e4d43f301dbca59680e1165be5', 'ExecutionBundle5': '9566419bb43ec552e0ca7db0a9a0085bad62a763a181d99ad9f81bef0e66442c', 'RunHistory3': '494081c0efadc9c06cb4cd830a799f2f301bca3fc7ed222fa372cca80b52b5f0', 'ModifiedRunSeed3': 'c7a8aebae4f4e5a00892bbc7e46f70ed8e0312b5c4b70113384e85423f48a626', 'ApproachExportSummary1': 'e2b168e2601b5702f1a776cd16d5d7ec0b248a50e70e5d19794ac39cf2141f8c', 'RecordPreview2': 'e59d312db84684ad94cfa9bff0738d94af5fa50ab75b9a9b9c84e2b3710ad8bc', 'RecordRequest2': '0c64c55ef9073bf0ea7df853c7be59b261f6e3b3380d5de0ef49e20f41c24661', 'RecordPreviewRead': '41932fa5b04a665a740c413164ccca8ac48671c80690c5370a3fa6ecd4230461', 'RecordRequestRead': 'e660d5097093cd5feaf428c96706e741a315073b4e9c79066ac36ab147b4a678', 'RecordRequestResponse': '734650ad3fe76f56992f50ba9258872a1faf46d3a740a300285c4bf5964e8540', 'RecordStatusResponse': '734650ad3fe76f56992f50ba9258872a1faf46d3a740a300285c4bf5964e8540', 'RecordReceiptResult': '734650ad3fe76f56992f50ba9258872a1faf46d3a740a300285c4bf5964e8540', 'PayloadFile2': '1a886e8f37ae560651e8c1810db3ff1b70df9b3821d8477714e1fc02effd784d', 'ApproachPayloadIndex1': 'a3cd7ee11720e2c6682bb218ba1d36a1bb4eb893cd61f80f561f66a01e57c640', 'ComputationalRecordManifest2': '417c7117250c8231ce24e24a24c6dd54810cf1b91353e7f434f36c7775b4bcda', 'ComputationalRecordManifestRead': 'e514ddd6f03be11baf6b14223bcfb23f006a3ad9d2b6e71ffa07ac51a39f3025', 'ApproachError1': 'fa6ae316d9a8448621f9b8c92f8f373df46e1ec2ed2d7950735f499421e8bac6', 'ApproachCommandResult1': '0b040fe77a76b55f301f8de3fd53f75718eaf48387a838a72580d53e1b96c99f', 'ApproachStateResponse1': '95059103090f73186462accf2397c057e7940b45fa50da812e2bf996657ae84c', 'ApproachPreviewResponse1': '1220e8cc4bc252365fd796410a7b2739f8d5e9e55140d9fe58f88b0b4cced334', 'ApproachDraftResponse1': '159d7025717c731f6c8cb3d1c59caf15cdaf24f47ce0fb8cea62306e133572d3', 'ApproachSavedResponse1': '21df784e1ea1be64a129952af8b7205380571ec0f5b87d018852ea5a124144e7', 'ApproachVersionSaveResponse1': '43f7f0726e95dd4b089bfc3dab9615017fdf8c15428af9151818e18e3ce106e7', 'ApproachVersionListResponse1': '1fee4a53b9e36bcda68ce0759756049ada9746b4002fea316104e982eb8cf32f', 'ApproachUsageResponse1': 'efadbb7d81ea40e24d7f784dee9bd8d81d1f21bf1dce2c95eaeac9ca7868d4cd', 'ApproachReceipt1': '210421cea864325f9478e57001da5799256b78fa50ecc20caea9c572dbcaf5b8', 'ApproachReceiptCategory1': '04347eac80994b17e285cecc172b834286ad3d3fda5121795c0ab81e4127f1b3', 'ConfigurationRevisionPreApproach': 'd1bea7127481320ce19730d071a5307184a9d9ff94ff6c873ad5ea7c7c34e134', 'UnitDeclaration1': 'fe0413ee574ae2d12bdda75d724fcf1912263d78369a38860dadb053ed2b2233', 'PortDeclaration3': 'fc9d7a340278827127b718c3305bd4bd29ee9cc17b4cf12a25dbdc1cacf172e5', 'Port3': '108c60c4fcd9a4f2df21f86cd9b53b041e4d85832e1d505822c956c9fed19bcb', 'Definition3': '3abc90a674279c6a7e0a39f951edb6f09f471dcd49de03abd456b341e15c1ae2', 'DefinitionChange3': '1c4294338e20a96affca431456151cbf93a73a48cfdb7a1adf210b325d1b853a', 'Edit3': '60067e90c697e2ca75821498180b3b901908d20f4518a5956ed634b19b8d4e28', 'ModelDraft3': 'dd5a4cb3528e73fd5a7db910cee08a97122c2ad80f41da69f3c609029d92c540', 'ModelRevision3': 'a8ef1019d96dfc6e85a039658fd81f7dd34f17ba831f2e5e4c19bbb4f48b1f42', 'ModelRevisionPreUnits': 'a7ba7a3e15b0340d9a6461f1f65f581e26ab9ba730181dc00ae16e86130347ad', 'ApproachClosurePreUnits': 'acc075427a7756bc7fc1aa7519fc8364fa4b809e01951b8fde3dd34121094634', 'ModelPackage3': '64285adf1a498493ade9430b3ae551c9390489b76d95612982045cbe412e2380', 'Create3': '727656b5868499e7ac047b6e6b399ffb319d48748a7ed53e3c85fb46814e2b4f', 'CreateRequest': '8456f725ccc44f1a1a57e2cd2f02a15409b76796c456425ab459dc9cae66daeb', 'Preview3': '26f8835642352840553701137d17a3b1eed93f779c1e7422d5675e63361909a2', 'Apply3': '47047ecc90276cacb3833f44722f0d89d631c4eb6f513094e8cd69cc749200d7', 'FrozenConfiguration5': '05b9f8808d35a9f784fe1deaddbbfbdabad9c792f294dbd668649927933fe779', 'ExecutionBundle6': 'bcddf9146373495a288da9eaf1246b2befe91eb0d918c3c4ba4b7b30955c53ab', 'RunHistory4': 'd9cc5ca090ddec300512d80b7db45e8eb4bb476dea811d46b8fab2845e2af42b', 'ModifiedRunSeed4': '5c68d13dbee3fb68432942f0c28d54b529e7046e8bbdf59bed7084690f68df9e', 'UnitCatalog1': 'd773314618fa0d1f2a08ae48b3648f5a153b939c0724fe7ebc8ccd8793570974', 'UnitCatalogResponse1': '8dc1be32050b95fe5bd848c1212971ccd668b15a70aa4058af6561fd2817b0b8', 'DefinitionRead3': '8d828991bad6b5f467ab02d6eab4ac66f1a93ee56fa7ac73d407da9699e4b4a5', 'PortRead3': '48d73ee04bdaf0ee6892a1968c8d7714d8b88c0178249b8096864adad219d0cf', 'ApproachClosureWithModel3': '5523210faf8be1865790d1db1e2889910374b6186e9945b50b182d739dc66fa6', 'FrozenConfiguration5Model3': '936e3bbe5534d08ac3683d7d5ffb71eb1aad838f0c40e926f146b62785bd7795', 'FrozenConfiguration5Model2': 'c2603bb52e6e73ccf1193b44452701d1de31e4c552c4060d8e0876ee7e1f77e4', 'RunHistory4Model3': 'bab60b0e68229a23fb8424f6643ba40ee55be09cff50a922b4dfde8651525b85', 'RunHistory4Model2': '0751816fb377cf7f8705fe68cdd5b4722fa582dc3863fe5dcc78067d641e2f9d', 'ModifiedRunSeed4Model3': '1f3ece965181ff150379e88f9ce30d7e4738d27ab142e488845174288b8619f3', 'ModifiedRunSeed4Model2': 'ff5fd13763c9eab8266de527ad518b67a05d01c35a5d386481b95761e7df2110', 'ExecutionBundle6Model3': '678a31b7a9414021ece9d69f9c9c857446ef9167208682d58f6d4b9c757357bb', 'ExecutionBundle6Model2': '20cc333d3025ce3e47ef3a4dea7bed65e23b5443633250b35895f2aee74b7068', 'DocumentId1': '586d51131ae542e6e1f9f8624e35bf9a420342117a032493409f97ee3375935c', 'DocumentDigest1': '67f459c542f6ec4afe79b51471d533c7b954d14e76adcfb186445758052e48d2', 'DocumentTimestamp1': '31f0959dced12100a5f1dd335d722c30e4cd8f0cdf3fe01d837b540628723048', 'DocumentEmpty1': 'd746974fa9afd5e951f76f9af38954b0ad7f436f2120dc974da65e5ee39f856f', 'DocumentCommand1': '2f9f44cf1d0086ba164edecfba8a8eb5923059178c6ac3d59b81048796802730', 'DocumentVersionKey1': '43322e3dc1fe60fca1ad786f1266da53cbe9b5ca3d511b971459cfd6d3eb6fcb', 'DocumentCollectionKey1': '57a03c13cdd446441b344d12fe3b51fd1fbd683ebc293cc3c8ce5a32000abb0a', 'DocumentAnnotationKey1': '9c5ab934c680b5b7a321375f391ee0ed2c40e2426ac192bb2b52c98bdb7b5a63', 'DocumentAttemptKey1': '1c53e119042305f0c3c6073fa1aad0ed5cad1036cdadc9dcbf2adab74b74c656', 'DocumentOperationKey1': '2cdcbe6e8b5fa04b97817b16f1cfc73708a459c3dc95a1d45c329c9a6a616cd7', 'DocumentOriginalLocator1': '78187663d6bfeb7ae71d118159922b89b0eb9f5ec154ea728b719daa7d5cddb5', 'DocumentPdfPageLocator1': '94a93b4085b00dd76fbf1c07e7e61bff0aa8d84eb525660b060044c26ac4d4eb', 'DocumentExtractedSpanLocator1': 'b1d968457f51d204a8f43f4269ffc69f2c554a20dc421669b88da50a8934d0e8', 'DocumentLocator1': '017a764116cfe39ae0641aeb29957929404b2893675dbe3b4966c6ee9e19d3e9', 'Document1': '74ddcfb91cabd5d8d4850a5c3a59fea5ee4b0a96a34be83a49744a1ef2acbfc9', 'DocumentVersion1': '9f81047358d8fa180736a2bd4448e196b04a05a8bc4794ba3f60fdbc80d7e102', 'DocumentNativeAssociation1': '166752090b0d76295141b873801bd2f663649661d57c854127601f9fe942ffb3', 'DocumentCollection1': 'ecd5a8abd0b65a7c9db533dbb6982a6843f8050de0473a1acdbb666dec3f614d', 'DocumentCollectionMember1': 'd1cb8b8b293c7f0f8818d01d70541e7d2c497f6799d1a5b9a3e0688355651a4e', 'DocumentAnnotation1': 'fc0ae64f1db332e21418dd9ececd78da2d12b19699620e889c2a5047ff87e84d', 'DocumentExtractorIdentity1': 'ceccc114c460b8dff0fc4ff6906c7b37302afbf70b355fa0dc53df273232d6dc', 'DocumentTextPolicy1': '2e196c77a7b43048ea4082b4ae8ddd21cf841b00bc009605270230e0e43ab02f', 'DocumentPageCoverage1': '50dc6d4ecf064dc451b7892d7f91e98b6b11bbd59c8a310ab6f3ea346002e049', 'DocumentExtractionAttempt1': '08028021713952bc2bffac4bda77aab2898210c480b6dfc2fe70eb7ae1cb8b44', 'DocumentExtractionResult1': 'b0b0847a3233bc5640b3201ecfe25987ecea47d989e86580bfe8fa6bac957771', 'DocumentFragment1': 'c6632adbf60c4551a11db36e20b97df8718a6509945dc8cd60e00d95a1561d8f', 'DocumentSourceDescriptor1': 'c43f9ee632642d6d3c1da3929884cb6071591726451822fc0b5747a3474eacdc', 'DocumentUploadBegin1': '9ee80c9981678c301ce8c4bbe00d0864d047168c410b3a6561836501d31c03e9', 'DocumentUploadChunk1': '6a95547e091b8369a3499e8cece94d35fd7ae0d82874b1a473dd2962e9426224', 'DocumentUploadChunkReceipt1': 'ae4c473d12a938830aaaa635d4183d66d51ef158946afc73c726b45de30a6cf6', 'DocumentUploadStatus1': 'fa78e4f3610afebbec2090c7ded53e1a1466979aa8d0edf68bae785c6b57b0e2', 'DocumentMetadataPatch1': '036ce64bd48219c3b1359a7fdfa7f82bfb8a4caa3a087ae7f7f783d81e6e130f', 'DocumentArchiveChange1': '45cb6d2413a407282fc0d708103dc8d19434c8175e080ba04b0cd5f915595ea7', 'DocumentListQuery1': 'c64386659975ea03ce978760b718fd5bdc8145da6b33680fb8bdf294bd72f09f', 'DocumentPageQuery1': '9db6a06ef227958facfd0e74a5d93195185acd01f513e34dd2b2f51eda2d87da', 'DocumentList1': 'c510f9ae1a8e3d04956c4c439709ab311f578b286b0d0a262a707ab1a20fb3c5', 'DocumentVersionList1': 'f419ebf216546c29b2950eb999726a338bac1d9c938df688fcc944df401592ea', 'DocumentCollectionList1': '6472f7570e25e743888ef9a28e9ae4904fa547246618bfae4a2b1e21bf1a2e0a', 'DocumentMemberList1': '68cac103ad75d7c4d40ea61b9b888fc37133fcf25c960755a0602a1717aeaf46', 'DocumentAnnotationList1': 'dc4b1b6746b5165dc06935d596cdfb545a45af12ce4569d06c17d6e84cc9de78', 'DocumentAttemptList1': 'e65a94b8872731594947de47556536893cec70c707f7bd47f59c2f2b7d2ac853', 'DocumentOriginalQuery1': '5238b7e92875efc8ed95c2f706351299e80a5447146814d51f62f6650e956009', 'DocumentByteDescriptor1': 'c57007cb4a91316e6ede6aa56170b2c49d93351c0121132fc80bce5ef825574d', 'DocumentFragmentQuery1': 'b4b28f9f70b7bd9011df90a253ff64c0eb0df0b253a961ba6f8ae9cfad526099', 'DocumentCollectionCreate1': 'a13361b401325b7c82cf15abcfa9ba604145c27c193f8d3111d708b050556fdf', 'DocumentCollectionPatch1': '21eb04e14340665f75e6cd832f9bde3923158c177ea6d8359c35f28ee1bc8e5c', 'DocumentCollectionMembersChange1': '4fc80d856d4a0732913d7586d47cd87da950c1379ed55060d3a944da6c686a65', 'DocumentCollectionDelete1': '45cb6d2413a407282fc0d708103dc8d19434c8175e080ba04b0cd5f915595ea7', 'DocumentCollectionDeleted1': '14d633c8805676a136f6cb6d788f50bc9aac2040b25cd61bbb3193f418b4fc28', 'DocumentExtractionCreate1': '01c6ca5a1b8bcdd6a6705b866ddc6605d08036abfdaa3ecb195fd935c17b8be9', 'DocumentExtractionRetry1': '5136d2dd4364e6391fa6094f513508e5baa38512bf915448a61baeb18b76555d', 'DocumentSearchQuery1': 'b31e23002102a8f4e1ea26894a9d80c80ef1f0415ad9d49a727bf2ae19d405db', 'DocumentSearchHit1': 'd99aa23f400ff025862e13e4e2e750c69c09ea2b4220bbcda9d78a908a581024', 'DocumentSearchResult1': '5d58285b42f331ddb720b557bccec10af44045778ebf9bd1ada230727d146bf5', 'DocumentAnnotationCreate1': '67d4c00b9f0a03dbff12e0ab6efd8e5cf949432a9b0580847301f24e1f16c19c', 'DocumentAnnotationRevise1': 'd423ae94e1ec08c50427c395da7613ef8a094c577c4fe2ddd6ae04f9813c7b5e', 'DocumentAnnotationDelete1': '45cb6d2413a407282fc0d708103dc8d19434c8175e080ba04b0cd5f915595ea7', 'DocumentAnnotationDeleted1': 'c81460835f6e4fa27d00ff7b83f8423f31719f7fb8442c99f1b1c32ee4d2b827', 'DocumentCitationCandidate1': '8a52e48e0344ae62654215f53d8d97e1092b6e139dee053eb234b6b3d442a273', 'DocumentCitationPreview1': '23d2949a5a408b472b2b63f2232b6d8899588ee8c7d14ac0e73786ec78355611', 'DocumentUsage1': 'd5821eecdf21d89bbac1c435af1e5d7fe611042b12396cc2ff99a10a4a7bd20e', 'DocumentUsageList1': '12a689283f6bcacd62beca154833205484f90a1a9d3be0de0ee8fdc0673e01a5', 'DocumentDeleteVersion1': 'ccbcab6c8883917e18e8fbe3f43dcf9cb22a0d76a0eccb24610f3843d0db77f7', 'DocumentDeleteSelection1': '2a5c5c40db859003fcd3382cb287ff25765cb738d342d2122dd5f5a9e641373f', 'DocumentDeletePreview1': 'c38e6a5bd0e7a63f04b70d7e82e79dc18f95d4b1fb4dbad6224a27343f481a59', 'DocumentDeleteCommit1': '0d2f116199003e71eb64260cd6e5955c2f48468537fc26e70d71eaf5274cca33', 'DocumentDeletionFence1': '3a53df3f68bd3fa9c81b01ea7f6790edf40194075aa9b5dbf6cba9c243c8d963', 'DocumentTombstone1': '7d83bfbac24aee7111a642eb007b45e133a7e2021924cdf86273471baac5d882', 'DocumentDeletionResult1': 'edeb7562d16f9bcc48ce0eb2bf9b838baa61f97dff4e0bb08ba8d689cf889b9f', 'DocumentPortableSelection1': 'eac59bbf76c8838b91b58203fd4fa04be1e4d543085c0c00421c08492d8ebfe4', 'DocumentPortablePreviewRequest1': '470c3881991cc0b970a4812731e24b49156cd5927c99f3db38dd55fba9b3bf4a', 'DocumentPortablePreview1': '31978976d41b5651558353a634fe0aaa4b2b47a89feb548f9980012e313f9596', 'DocumentPortableCreate1': '06bb479ba1f2fbc05e119ec539657f0d7dcc52dffc4e9b39a33fdcc801473291', 'DocumentPortableArtifact1': 'f1003d9bf8a32973487f4e539483f0211e740bf528e012cc2c06f103e28ac82e', 'DocumentPortableDownload1': '71f21987adc4a448ef010929a5b6280903605dccbe1878e36bc5c5bf74eb1d41', 'DocumentImportBegin1': '6b50e960f759f19aa4011851e2937532106f82fb7fc5820f98c75d2f2fb0f035', 'DocumentImportCommit1': 'a4a5fbab2612227d308d7ffe49fe2ffcac4cda6678dab3a605ac699502fd04b4', 'DocumentImportMapping1': 'd4fd9a6fa89faad4ffb0b08ca3399fa195e16154bfc2f06f1cde958fe4ee27c3', 'DocumentImportResult1': '300c6f9c01cc8da80bb8513231027ce170652c6d9274cddddfc41d1184d65c50', 'DocumentRestoreRequest1': '80ba0b5dbb22240dfa95b50f84ab6d2b9980e2a7d8857e0765a6015c932e9beb', 'DocumentRestoreResult1': '8d6a35c94661eebce4c32b9b31725f4ed73b4ca1bacaffca65e333e7efcfce70', 'DocumentError1': 'fa6ae316d9a8448621f9b8c92f8f373df46e1ec2ed2d7950735f499421e8bac6', 'DocumentReservedIds1': 'ae0af95ce3a238c129b9067cdb17a01963d85a0e034d42938ed555322bca030d', 'DocumentOperationResult1': '3db16f6a544978ada1f527271dda06148692266f7ab06be5d7a46d37c1ca23eb', 'DocumentOperation1': 'c0f6bec01a4a8194e6b7fa1e4056cfe82929ed97a9ddda7039f65610590d7904', 'DocumentCommandIdentity1': '8252785058a484c263d283c475c84a32e60a327799c9c51b6589f241a8a4ac83', 'DocumentNativeWitness1': 'aabbfecfdb59c00a7f55d27189d9b7622380d771989131738d9f56e2cedcbbcb', 'DocumentCollectionTerminal1': 'c9f916864f34681eb44285e10c249bfccb288a8fb3b767ed9e479d733f07ce5b', 'DocumentImportChunk1': '236e9c590cdbd9c31cb98635b3c7b8dfdb0206854e26c26307caf97dd4f09eb4', 'DocumentImportChunkReceipt1': '0713e4aaf2cf7f15dc5292a4f2fa19b4c557e0354def93ad9885e08a81edae65', 'DocumentNativeOriginalRead1': '739c98fd6495ba5d3594086683987eca8018188ec438f2b4263775c95ecf9dea', 'DocumentNativeOriginalReply1': 'ae9841bdd9d225a1cf2efb422655b47484e4b2f0edee9b205416613a92881f60', 'DocumentNativeMemberRead1': '89c4a4fb6af473a18cd1ddb7b55b40bdc1a96be6e8a944af565a4130359cb76e', 'DocumentNativeAnnotationRead1': '163725e2cfd630fedfe170e99d7e8287a3b7d2af39eae7ec60e1004dc1d44cd5', 'DocumentNativeFragmentRead1': 'f863c5646245dd67ea2dd91396228e8cc23d85704fe76b050da8ebacf292942b', 'DocumentNativeList1': '83bde6358506770f5b7fc35f3c2dc61d59b43886a8f4dd4895c59152bb6a3417', 'DocumentNativeListResult1': 'f77e71d2d4cb45a53d97257bfa2ebde5fd73b3a12568ae14e7f7e209e2a30946', 'DocumentNativeStatus1': '0fc09f1c131c0edbd3e96467173ff153740476471116907857dada17f4f482dc', 'DocumentNativeStatusResult1': '2be919b3520db3a12e0826d9bed8c67ce50174a58e3c35a86a3399d11854dc77', 'DocumentNativeStoreOriginal1': 'a3c9e03b0a335c9507c70ae5c4ab6d52bee1dcc9c0b15187278bc60581ba1d9c', 'DocumentNativeCollectionUpdate1': 'b1295f7af1a40edfbe74fe7328971ca77eaddc494783490658028220d981492f', 'DocumentNativeCollectionMembers1': '3e0907cca624d51f76c08155edd8fa27a579c7613ed0e9d03ec150e96eabd3ad', 'DocumentNativeCollectionDelete1': '3459be1c1dc1bdea329fdc074a9e75c29b1bac8b780647095ea656f9edfb4df9', 'DocumentNativeAnnotationCreate1': 'ec84a48bbc6ab134ea9d84d416b8d776cb1a254cb863483bc170f50c4dfe2826', 'DocumentNativeAnnotationRevise1': '9b4b74fcaea5dd7b7c933859e0f7da737f9ea9e25b7b8c641e2535583a0a55e5', 'DocumentNativeAnnotationDelete1': 'c02b2f7b4c5e98f9fd481706314f6d67787710feebb53d36c29182b6b4c54800', 'DocumentNativeExtractionStart1': '3f51707012efbf51d967fc0ac15379aae5a964bbc54798f7db58c4fdd7d92c44', 'DocumentBridgeRead1': '747bba0e0bb0505e5b16494eb96c48bddb48f76d597e30cefd68db6e52101848', 'DocumentBridgeReadReply1': '819508bf8c47a11ec1416f718843201106c22dc19294f8b130c73afc521c692b', 'DocumentBridgeWrite1': 'cdb9dd2dc6e216d62efc88009215d1488d27f3d3ce1bbb35e74787fde8e94e36', 'DocumentBridgeWriteReply1': 'c39a4952cdf5308b9e5155e4cbd4f2f677d6525796ac80ff58e4e1ab3577e037', 'DocumentFailure1': 'ce346f4858dfb09cea1b3acd45ca1036273c1c1c4d076caaffea4de88e115d1a', 'DocumentOperationTransition1': 'a1f5e29b5c1f493dc7710a401202cc82ad234dd00c7430837e3921a6ded633f0', 'DocumentNativeByteDescriptor1': '657c2e367b7e7ea5c3b88f031d1d548aae444d54ed8deed2cf4f656e8e65d402', 'DocumentCitation1': '611946612cc6f383bc8e1f125a63056c792c4e8266412b66a6081712ab6039de', 'EvidenceCreate4': '41ff3aa8e35a95460e8e4a7f9a29163d47852c19284f17de3e070d404215dc06', 'EvidenceRevise4': '94e54c8191811e1163bc647934a7407ecb6d7352f88e3e4875c17b4b8121e731', 'EvidenceRecord4': '1626936d774f02dfa4ae3f8d926c4a2526f5cefc1db4d7fcf8958ed5f700debd', 'EvidenceSnapshot4': '1626936d774f02dfa4ae3f8d926c4a2526f5cefc1db4d7fcf8958ed5f700debd', 'EvidenceCreateRead4': '1ac48b525cfe3b75ab80db87c3c59ef86512b9368a91b9c6ef9e9c79f3c37853', 'EvidenceReviseRead4': 'dca92b89efd1a48860b03f049144ceed322de434bf57da51fb6dbd87050f1f19', 'EvidenceRecordRead4': 'c96619b679701d778adf0592f9d36371222a81cbe3c777025cb318c2d6e67161', 'EvidenceSnapshotRead4': '05d495d44cc3a4e6278de4063b01be7117f42148c37fa23ca27b12de55414511', 'EvidenceFamily4': '0388cbcb2b9581b1781c9bb71a706405152e0357a72d06e2ec8888934f7b6735', 'EvidencePage2': '663261f2e4a88f9ff7c5da895dd8976b489e08130021df78030dc89c08885caa', 'EvidenceCitationPreviewRequest4': '2d890baa223f8d509fa50d0c0f2a1a2a276f4034fb0e6f9ba1ca811339a64ab4', 'EvidenceCitationPreview4': '187d805af567267c45f9464cb8c2cf1dae1b09e35aecf61c41f845f6fd598894', 'ConfigurationRequest5': '7cf73703386beaeb58b18e13409f8edb0d212252d5af4732c9f95c092bb162a6', 'ConfigurationCandidate5': '452af1f1f5a47eb9fb55a08419e079920d24c2555be7f62bcec463c23645b509', 'ConfigurationRevision5': '8c0bf2623174aaa19c4bbb2203e8967dec674cf88dab983547095c8ce9dbf87e', 'ConfigurationPreview5': '4d215a82722a2a000ebc22bb07f8ceed7a329897055737a7279848cba486a854', 'ConfigurationCommit5': '380e86532eda01f25b929f0371b776aa5f549e5086e8b43d7298ed635faeff22', 'ModelingConfiguration4': 'e455e562c3588e15cfdd0388ffddf807d9983672c2c40e5e544bcba601a9f59b', 'ModelingConfigurationRevision4': '2b67eb9108aeba2d9a9e093f5b3be11ba63a548c146b58159afa2940e9c294c5', 'ConfigurationCandidateRead5': 'f5de5634c9efc1efade7963ec76218099864ac1af7e276d9a40e2576c09faaac', 'ConfigurationRevisionRead5': '87b2115a1cd1fbec74aa214432181d06ec88b9914b8ad38abf7c7d1010af342a', 'ConfigurationRequestRead5': '3793eb7a7643d8eedf7aa4e223aef51437351bd8b14254643ed822182c7dc26c', 'ConfigurationPreviewRead5': 'fd7005adcac21d979575523c3c43b294770f158d6014154b6b0740ca59b55afb', 'ConfigurationCommitRead5': '4cbc386c6948923f9661523d9a3d677dab25e8c8cf35776209d2f8ced48c6c93', 'ApproachClosure2': '731828a171d284191da45a698e8e5af203f0ff111e0de3e973b4cd2df8180e13', 'ApproachResolution2': '500d7243519230187c778e3a08945eb8fb2d699453587501d3715a0627b1edec', 'ApproachSaved2': 'e370e3c1736e2654bda4a247fd2a1d158b68be04c46e27a8df781cfc5cbd9418', 'ApproachClosureRead2': 'fc4e6a62a827862e5591feb52c0502582141ad718eacf1ce80b66681c1ed36db', 'ApproachClosure2Model2Only': '3825ebf86282b321089b71b2cf58da3e767d25f7f3df6d696cd1289978944428', 'ApproachClosure2WithModel3': 'ad5ca5589806b713c55c5bf1e44fae1a41140cc724bf6a0037ac9ab9630d9946', 'ApproachClosureModel2Read2': '489b48e88ac09a269c82715f53d00909862371a21924065c5e8f27cf5ee5bd78', 'ApproachClosureWithModel3Read2': 'f2ffc55cbfbce6bf3283f298711a939cb278d9d83139d614c822331452837929', 'FrozenConfiguration6Model3': '6429ea302553bf9f0339750e57bdf6ec96f0708665936fc3d4276c6994a31896', 'FrozenConfiguration6Model2': 'eb5cc6220017776aaf6453c424a854a635d25dfcd1f5f4720df8a1c53e87baeb', 'FrozenConfiguration6Model2WithModel3': '88aa6e3b2ea020786293f8bee635ba1a8b57f59b37a958c334d51c3f470a029b', 'FrozenConfiguration6': 'd0820749264ac986c623ac8dfe9f9239e57991ba9aa1d962631f5e6f88f0747a', 'RunHistory5Model3': '016ecdf7d7205c2d59b7fa2d2bf4a6cad91fa4602f6e1c0536e734b92d60baba', 'RunHistory5Model2': '53b42f086b869896afd585e7716bea39e67703964c7f33615be066c158583af5', 'RunHistory5Model2WithModel3': '1a6c50d17d25c6891d7ed4eb9ae2fe57820e9852c513c3b19594712ac2f4f0f5', 'RunHistory5': '39da3dd1e18a2a79998feb333cf425c7e2359fefa8ffac141a4d2fed1da5626c', 'ModifiedRunSeed5Model3': '2e4ebd9c20ade330dae30432adf86b394ee8a190d966805220aa887a1230ec4d', 'ModifiedRunSeed5Model2': 'a12b93df236938141c7314a7cb4e1e56f1309013a7eacc9327154cab6b8985be', 'ModifiedRunSeed5Model2WithModel3': 'd77865e058a9c3e62f2f002b93188a78614a7203ebd8cc16ca3e4781b45f7d25', 'ModifiedRunSeed5': '0daa34d5127642e06786f13c65e898689a63cbf8ecf68191575b31aec64027e1', 'ExecutionBundle7Model3': 'ef15b1946fdd0d786e7766455be7feb8bb94fd872f975bb3f8f52f7879bf8567', 'ExecutionBundle7Model2': '744e29bffd9d673ae4284d320eb243ca3aae5c3591ef70edfcdd3213d120451c', 'ExecutionBundle7': '3e349bea93be58d63f7b0b686fb289cda22425ca35435fc649c48af4aeda92da', 'FrozenConfigurationRead6': '1c7a7ba41f5a39e059cf0d60456e349fb18ddd91835c0fff5e8fdb190591eb84', 'ExecutionBundleRead7': '0464e788320f9eb5dce29a0ac4dabb2399fcb98a57c907f82294aa82bc98e7aa', 'RunHistoryRead5': 'a68077e132e436476407485bba490d3e8f87c53caf8870892722a4646ff8b76d', 'ModifiedRunSeedRead5': '08128df5138bbb98b72f59f21e2fb5cc371cc3d53c1e92b503136014771cdd44', 'ApproachVersionSaved2': 'cb45f0823fb558f81c3111504cf3ac6011c8c5544a26b5111283adc45d47acfd', 'ApproachPreview2': '251b08c63e1a826d90265a5dba6e5afbdd251b273d957a28092530d478a3a7a5', 'AssumptionEvidenceResolution2': 'dfd4804afd79ac8d21f8b9655e138d9c385921e53a38b44a0ab38514fa3adac0', 'DocumentImportUploadStatus1': '83998797e57d145a87b900dfc5287d57f0194436cec58fb7c3bc84c403eba507', 'DocumentNativeCollectionCreate1': '36f28916e6344c38e2fc169d17feb887dc8c8be1118676b2ece4e1c5512adfef', 'DocumentAppCommit1': '10bbdc280e1fc4a8a1ef2a4f8d6851f456a7281960b6ab4524f4753e7d2bfe02', 'DocumentExtractionReconciliation1': '1615a56f0704ce29e79a42726258d399ee70ac0fbe67012cc4911f23b3877fb1'}
def test_polish_historical_hashes():
    import hashlib
    for path in ('model.schema.json','execution.schema.json'):
        definitions=authored_schema()['$defs']
        for name,digest in POLISH_HISTORICAL_HASHES.items():
            # Reviewed exception: observed operational capabilities admit Bundle8.
            # Keep the historical baseline above; no stored artifact schema changes.
            if name=='ExecutionVersions':
                digest='d5cbee9218c8bcab63e4ec0e58412ac095f16d423cc0f0bce45d6358e43341e7'
            definition = copy.deepcopy(definitions[name])
            if name == 'UnitDeclaration1':
                # Approved additive exception: normalize only the exact reviewed suffix.
                units = definition['oneOf'][2]['properties']['expression']['enum']
                assert units[28:] == ['m**3', 'cm**3', 'mm**3', 'kg/m**2', 'g/m**2', '1/m**2', 'J/(kg*K)', 'kJ/(kg*K)', 'J', 'kJ', 'MJ', 'W', 'kW', 'MW', 'm**3/s', 'kg/s', 'm/s**2', 'N*m', 'W/(m*K)', 'W/(m**2*K)']
                del units[28:]
            if name == 'UnitCatalog1':
                units = definition['properties']['supported_units']
                assert units['items']['enum'] == definitions['UnitDeclaration1']['oneOf'][2]['properties']['expression']['enum']
                assert units['minItems'] == units['maxItems'] == 48
                del units['items']['enum'][28:]
                units['minItems'] = units['maxItems'] = 28
            assert hashlib.sha256(json.dumps(definition,sort_keys=True,separators=(',',':')).encode()).hexdigest()==digest,name


def test_polish_known_model_partial_history_and_implemented_package_writer():
    for version in (2,3,4):
        value=sample(D['RunHistory6Partial'])
        value.update(model_snapshot=polish_model(version),errors=[{'code':'corrupt_retained_record','partial':True}])
        validate('RunHistory6',value)
        with pytest.raises(ValidationError):validate('RunHistory6',value|{'errors':[]})
    api=json.loads((ROOT/'contracts/hyprn-mvp.openapi.yaml').read_text())
    schemas=api['components']['schemas']
    assert schemas['ImportModel']['properties']['package']['$ref'].endswith('/ModelPackage')
    reader=schemas['ModelPackage']
    assert [b['$ref'].split('/')[-1] for b in reader['oneOf']]==['ModelPackage1','ModelPackage2','ModelPackage3','ModelPackage4']
    for path,methods in api['paths'].items():
        if path.endswith('/export'):
            assert methods['get']['responses']['200']['content']['application/json']['schema']['properties']['data']['$ref'].endswith('/ModelPackage')


def test_polish_implemented_lists_and_rejected_receipts_are_unambiguous():
    old=valid('ApproachVersionSummary1');new=dict(old,schema_version='2')
    validate('ApproachVersionPage2',dict(items=[new,old],next_cursor=None))
    validate('ApproachState2',dict(draft=None,latest_version=new))
    rejected=dict(command_id=UUID,state='rejected',result=None,error=sample(D['StoredError']))
    validate('ApproachReceiptRead2',rejected)
    with pytest.raises(ValidationError):validate('ApproachReceiptRead2',dict(rejected,state='committed'))
    with pytest.raises(ValidationError):validate('ApproachReceiptRead2',dict(rejected,error=None))
    with pytest.raises(ValidationError):validate('ApproachVersionSummary1',new)


@pytest.mark.parametrize('version',[1,2,3,4])
def test_quantity_implemented_private_response_and_receipt_wrappers(version):
    revision=sample(D['ModelRevision'+str(version)])
    draft=sample(D['ModelDraft'+str(version)])
    if version==3:
        revision['required_capabilities']=['unit_declarations/1'];draft['required_capabilities']=['unit_declarations/1']
    envelope=dict(schema_version='1',request_id=UUID)
    responses=[('ModelDraftResponse4',dict(data=draft)),
        ('ModelDraftEditResponse4',dict(data=draft,created_ids={},diagnostics=[])),
        ('ModelRevisionResponse4',dict(data=revision))]
    for name,payload in responses:
        validate(name,envelope|payload)
        for invalid in (envelope|payload|{'extra':True},{k:v for k,v in (envelope|payload).items() if k!='data'}):
            with pytest.raises(ValidationError):validate(name,invalid)
        receipt=dict(command_id=UUID,state='committed',payload_digest=SHA,response=payload,status=200)
        validate('Receipt4',receipt)
        validate('ReceiptResponse4',envelope|{'data':receipt})
        with pytest.raises(ValidationError):validate('Receipt4',receipt|{'state':'rejected'})
        with pytest.raises(ValidationError):validate('ReceiptResponse4',envelope|{'data':receipt,'extra':None})
        if version==4:
            with pytest.raises(ValidationError):validate(name.removesuffix('4'),envelope|payload)
    rejected=dict(command_id=UUID,state='rejected',payload_digest=SHA,response=sample(D['Error']),status=422)
    validate('Receipt4',rejected)
    with pytest.raises(ValidationError):validate('Receipt4',rejected|{'response':None})
    # Summary/list wire shape has no nested model/version tag and stays unchanged.
    validate('RevisionList',dict(items=[sample(D['RevisionSummary'])],next_cursor=None))
    private=json.loads((ROOT/'contracts/modeling.openapi.yaml').read_text())
    for route,reader in [('/models/{model_id}','ModelDraftResponse4'),('/models/{model_id}/revisions/{revision_id}','ModelRevisionResponse4')]:
        assert private['paths'][route]['get']['responses']['200']['content']['application/json']['schema']['$ref'].endswith('/'+reader)


def test_polish_bundle8_model4_requires_exact_quantity_capability():
    value=valid('ExecutionBundle5');value.update(schema_version='8',model_schema_version='4',
        required_capabilities=['flat_explicit_scalar','quantity_definitions/1'])
    validate('ExecutionBundle8',value)
    for caps in (['flat_explicit_scalar'],['flat_explicit_scalar','unit_declarations/1'],
                 ['flat_explicit_scalar','quantity_definitions/1','execute_prose']):
        with pytest.raises(ValidationError):validate('ExecutionBundle8',value|{'required_capabilities':caps})


def test_polish_configuration_preview_enclosing_reader_preserves_documents():
    value=sample(D['ConfigurationPreview6']);value['approach_closure']=sample(D['ApproachClosure3'])
    value['resolved_candidate']['approach_binding']=sample(D['ApproachBinding1'])
    validate('ConfigurationPreviewRead6',value)
    assert D['ConfigurationPreview6']['properties']['resolved_candidate']=={'$ref':'#/$defs/ConfigurationCandidate4'}
    assert D['ConfigurationPreview4']['properties']['approach_closure']['anyOf'][0]['$ref'].endswith('/ApproachClosure1')
    for tag in ('4','5'):
        with pytest.raises(ValidationError):validate('ConfigurationPreviewRead6',value|{'schema_version':tag})


def test_polish_observed_execution_capabilities_are_finite():
    value=sample(D['ExecutionVersions'])
    for versions in (['2'],['2','3','4','5','6'],['2','3','4','5','6','8']):
        validate('ExecutionVersions',value|{'bundle_versions':versions})
    for versions in (['7'],['9'],['2','3','4','5','6','8','8'],[]):
        with pytest.raises(ValidationError):validate('ExecutionVersions',value|{'bundle_versions':versions})
    assert D['ExecutionVersions']['properties']['bundle_versions']['maxItems']==6
