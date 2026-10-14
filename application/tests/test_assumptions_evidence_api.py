"""Guarded assumptions-and-evidence API expectations over the public contract.

generated_ and public_ are disjoint runner selections. Evidence operations use
real storage. Diagnostic/configuration3 dispatch doubles are labeled explicitly;
real dispatch and native resolution are proven by the native execution tests.
"""
from hyprn_mvp_app.contracts import authored_schema
import json
import importlib.util
from pathlib import Path
import subprocess

import scoped_fixture as guard
from checks import PROJECTION_SCOPE

# The runner guards before pytest adds its own environment keys. The browser
# imports this shared fixture before pytest collection and guards directly.
SCOPE = PROJECTION_SCOPE or guard.scope_from_environment()
guard.validate_scope(SCOPE)

import pytest
from fastapi.testclient import TestClient
from hyprn_mvp_app.api import create_app
from hyprn_mvp_app.auth import Auth
from hyprn_mvp_app.store import Store, uid

ORIGIN = 'http://127.0.0.1:19999'
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope='module')
def generated():
    output = guard.scoped_path(SCOPE, 'artifacts/ae.openapi.json')
    result = subprocess.run(guard.contract_generator_command(SCOPE, 'artifacts/ae.openapi.json'),
                            env=guard.clean_environment(SCOPE), capture_output=True, text=True)
    (SCOPE.root / 'evidence/generator.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0
    return json.loads(output.read_text())


class NoModeling:
    def call(self, _actor, _sid, method, path, **_kwargs):
        if (method,path)==('GET','/capabilities'):
            # Explicit unsupported private boundary, not a native-service claim.
            from test_assumptions_evidence_contracts import sample,D
            caps=sample(D['Capabilities'])
            caps['generator_identity'].update(source_commit='a'*40,provenance_path='provenance/fixture.json')
            caps.update(contract_versions=['1.1'],schema_versions=['1'],capabilities=[])
            return 200,dict(data=caps)
        raise AssertionError('Study evidence must not call modeling or execute science')


@pytest.fixture
def api(tmp_path):
    path = guard.no_symlinks(tmp_path)
    if not path.is_relative_to(SCOPE.root):
        raise ValueError('AE store must remain inside its isolated scope')
    store = Store(path / 'ae.sqlite')
    auth = Auth(store, ORIGIN)
    actor = auth.provision('owner', 'correct horse battery staple')
    study = store.create_study(actor, uid(), 'Assumptions and evidence fixture')
    client = TestClient(create_app(store, auth, NoModeling()), base_url=ORIGIN)
    session = client.post('/api/1/session', json=dict(username='owner', password='correct horse battery staple'), headers={'Origin': ORIGIN})
    assert session.status_code == 200
    client.headers.update({'Origin': ORIGIN, 'X-CSRF-Token': session.json()['data']['csrf_token']})
    return dict(client=client, store=store, actor=actor, sid=study['study_id'], study=study)


def path(api, suffix):
    return '/api/1/studies/' + api['sid'] + '/' + suffix


def evidence_body(api):
    return dict(command_id=uid(), evidence_schema_version='3', title='Heat capacity report',
                resource_scope=dict(scope_version='1', kind='study', study_id=api['sid']),
                kind='note', content='Reference observation; applicability remains unassessed.',
                source_refs=['Report section 4 — inert reference'])


def test_generated_declares_closed_titled_evidence(generated):
    schemas = generated['components']['schemas']
    assert 'EvidenceRecord3' in schemas
    assert 'title' in schemas['EvidenceRecord3']['required']
    assert schemas['EvidenceRecord3']['additionalProperties'] is False


def public_refs(value):
    """Rewrite only $ref keys, as the generator does; other strings (file-schema maps) stay exact."""
    if isinstance(value, dict):
        return {key: (item.replace('#/$defs/', '#/components/schemas/') if key == '$ref' and isinstance(item, str)
                      else public_refs(item)) for key, item in value.items()}
    if isinstance(value, list):
        return [public_refs(item) for item in value]
    return value


def test_generated_preserves_shared_concrete_variants_and_read_unions(generated):
    shared = authored_schema()['$defs']
    schemas = generated['components']['schemas']
    for name, definition in shared.items():
        if name in {'EvidenceSnapshotLegacy', 'Error'}:
            continue  # Equivalent paired-scope normalization and public error additions.
        assert schemas[name] == public_refs(definition), name


def test_generated_snapshot_normalization_preserves_validation(generated):
    from jsonschema import Draft202012Validator, FormatChecker
    shared = authored_schema()
    plain = dict(evidence_version_id=uid(), kind='note', content='Exact legacy bytes', source_refs=[])
    scope = dict(scope_version='1', kind='study', study_id=uid())
    record3 = {**plain, 'evidence_schema_version':'3', 'evidence_id':uid(), 'study_id':scope['study_id'],
               'title':'Report', 'parent_evidence_version_id':None, 'resource_scope':scope,
               'recorded_context':dict(schema_version='1', label='Original study', resource_labels=[])}
    cases = [(plain, True), ({**plain, 'evidence_schema_version':'2', 'resource_scope':scope}, True),
             ({**plain, 'evidence_schema_version':'2'}, False), ({**plain, 'resource_scope':scope}, False),
             (record3, True), ({**record3, 'title':''}, False), ({**plain, 'title':'Unexpected'}, False)]
    for name in ('EvidenceSnapshot', 'EvidenceSnapshotRead', 'EvidenceSnapshotLegacy'):
        old = Draft202012Validator({**shared, '$ref':'#/$defs/' + name}, format_checker=FormatChecker())
        new = Draft202012Validator({**generated, '$ref':'#/components/schemas/' + name}, format_checker=FormatChecker())
        for value, accepted in cases:
            expected = accepted and not (name == 'EvidenceSnapshotLegacy' and value.get('evidence_schema_version') == '3')
            assert old.is_valid(value) == new.is_valid(value) == expected


def test_generated_only_registered_routes_and_current_endpoint_versions(generated):
    actual = create_app(None, None, None).openapi()
    assert {p: set(v) for p, v in generated['paths'].items()} == {
        p.removeprefix('/api/1'):set(v) for p, v in actual['paths'].items()}
    for route, methods in {
        '/studies/{study_id}/evidence-families/{evidence_id}':{'get'},
        '/studies/{study_id}/evidence-families/{evidence_id}/versions':{'get','post'},
        '/studies/{study_id}/models/{model_id}/assumption-evidence':{'get'},
    }.items():
        assert set(generated['paths'][route]) == methods
    writer = generated['paths']['/studies/{study_id}/evidence']['post']['requestBody']['content']['application/json']['schema']
    assert writer == {'$ref':'#/components/schemas/PublicEvidenceCreate'}
    assert generated['components']['schemas']['PublicEvidenceCreate']['oneOf'] == [
        {'$ref':'#/components/schemas/EvidenceCreate1'}, {'$ref':'#/components/schemas/EvidenceCreate2'}, {'$ref':'#/components/schemas/EvidenceCreate3'}]
    seed = generated['paths']['/studies/{study_id}/runs/{run_id}/modified-run-seed']['get']
    # The public seed endpoint returns exactly the shared seed read union: every earlier seed
    # version plus the current one, never a narrower set.
    assert seed['responses']['200']['content']['application/json']['schema']['properties']['data'] == {
        '$ref':'#/components/schemas/ModifiedRunSeedRead6'}
    assert generated['components']['schemas']['ModifiedRunSeedRead6'] == {'oneOf':[
        {'$ref':'#/components/schemas/ModifiedRunSeed'}, {'$ref':'#/components/schemas/ModifiedRunSeed6'}]}
    assert generated['components']['schemas']['ModifiedRunSeed']['oneOf'] == [
        {'$ref':'#/components/schemas/ModifiedRunSeed' + version} for version in ('1', '2', '3', '4')]
    for name, branches in {'PublicConfigurationRequest':['ConfigurationCandidate1','ConfigurationRequest2','ConfigurationRequest3','ConfigurationRequest4'],
                          'PublicConfigurationCommit':['ConfigurationCommit1','ConfigurationCommit2','ConfigurationCommit3','ConfigurationCommit4'],
                          'PublicConfigurationPreview':['CompatibilityResult1','ConfigurationPreview2','ConfigurationPreview3','ConfigurationPreview4','ConfigurationPreview6']}.items():
        assert generated['components']['schemas'][name]['oneOf'] == [{'$ref':'#/components/schemas/'+b} for b in branches]
    for route in ('/studies/{study_id}/evidence', '/studies/{study_id}/evidence-families/{evidence_id}/versions'):
        operation=generated['paths'][route]['get']
        cursor=next(p for p in operation['parameters'] if p['name']=='cursor')
        assert cursor['schema']=={'type':'string','maxLength':2048}
        assert operation['responses']['200']['content']['application/json']['schema']['properties']['next_cursor']['anyOf'][0]==cursor['schema']


def test_generated_private_protocol_matrix_and_refs():
    private = json.loads((ROOT / 'contracts/modeling.openapi.yaml').read_text())
    shared = authored_schema()['$defs']
    matrix = private['x-hyprn-mvp-protocol-matrix']
    assert matrix['envelope_version'] == '1'
    assert matrix['contract_versions'] == ['1.2', '1.3']
    assert matrix['schema_versions'] == ['1', '2', '3']
    assert matrix['bundle_versions'] == ['2', '3', '4', '5', '6']
    assert matrix['artifact_versions'] == ['2']
    assert matrix['program_versions'] == ['1']
    assert matrix['required_capabilities']['resolved_configuration'] == '3'
    assert matrix['required_capabilities']['model_assumptions'] == '1'
    assert matrix['required_capabilities']['unit_declarations'] == '1'
    # The one compatible unit pairing: a model3 is configured, frozen, bundled and read only as these.
    assert matrix['compatible_unit_pairing'] == dict(model='3', configuration='4', private_configuration='3',
        frozen='5', bundle='6', history='4', modified_run_seed='4')
    assert matrix['capability_advertisement'] == 'only_when_supported'
    def check(value):
        if isinstance(value, dict):
            if '$ref' in value:
                assert value['$ref'].startswith('./schemas/model.schema.json#/$defs/')
                assert value['$ref'].split('/')[-1] in shared
            for child in value.values(): check(child)
        elif isinstance(value, list):
            for child in value: check(child)
    check(private)
    for route, request in (('configuration-compatibility', 'Compatibility'), ('prepare-execution', 'Prepare')):
        op = private['paths']['/models/{model_id}/' + route]['post']
        assert op['requestBody']['content']['application/json']['schema']['$ref'].endswith('/' + request)
        expected = 'ModelingConfiguration3' if request == 'Compatibility' else 'ModelingConfigurationRevision3'
        field = 'configuration_candidate' if request == 'Compatibility' else 'configuration_snapshot'
        assert {'$ref':'#/$defs/' + expected} in shared[request]['properties'][field]['oneOf']


def test_generated_object_constraint_unions_preserve_base_and_required():
    spec = importlib.util.spec_from_file_location('ae_generate_types', ROOT / 'ui/generate_types.py')
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    base = dict(type='object', properties={'selector': {'type': 'string'}, 'common': {'type': 'boolean'}},
                required=['common'], additionalProperties=False)
    for union in ('oneOf', 'anyOf'):
        schema = {**base, union: [{'properties': {'selector': {'const': 'chosen'}}, 'required': ['selector']},
                                  {'required': ['selector']}]}
        result = generator.ts(schema)
        assert result == ('({ "selector"?: string; "common": boolean } & '
                          '({ "selector": "chosen" } | { "selector": string }))')
        assert generator.ts({union: [{'type': 'string'}, {'type': 'null'}]}) == '(string | null)'
    inherited = {**base, 'oneOf': [{'properties': {'common': {'const': True}}}]}
    assert generator.ts(inherited) == '({ "selector"?: string; "common": boolean } & ({ "common": true }))'


def test_generated_types_reproducible_and_discriminated(generated):
    output = guard.scoped_path(SCOPE, 'artifacts/ae.contract.ts')
    result = subprocess.run([SCOPE.interpreter, '-B', str(ROOT / 'ui/generate_types.py'),
        '--input', str(SCOPE.root / 'artifacts/ae.openapi.json'), '--output', str(output)],
        env=guard.clean_environment(SCOPE), capture_output=True, text=True)
    (SCOPE.root / 'evidence/types-generator.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0
    assert output.read_bytes() == (ROOT / 'ui/src/contract.ts').read_bytes()
    assert generated == json.loads((ROOT / 'contracts/hyprn-mvp.openapi.yaml').read_text())
    lines = {line.split(' = ', 1)[0].removeprefix('export type '):line for line in output.read_text().splitlines() if line.startswith('export type ')}
    for name, version, discriminator in [('ModelDraft2','2','schema_version'), ('ConfigurationRequest3','3','schema_version'),
        ('EvidenceRecord3','3','evidence_schema_version'), ('ModifiedRunSeed2','2','schema_version'), ('RunHistory2','2','history_schema_version')]:
        assert f'"{discriminator}": "{version}"' in lines[name]
        assert 'unknown' not in lines[name] and 'Record<string' not in lines[name]
    assert 'RunHistory1 | RunHistory2' in lines['RunHistory']
    assert 'EvidenceSnapshotLegacy | EvidenceSnapshot3' in lines['EvidenceSnapshotRead']
    # Compile real clients of the generated discriminators separately from the
    # existing application consumers, so each union compiles on its own.
    proof = guard.scoped_path(SCOPE, 'artifacts/ae-type-proof.ts')
    proof.write_text('''import type { ModelDraft, ConfigurationRequest3, ConfigurationCommit3, EvidenceSnapshotRead,
  EvidenceSnapshotLegacy, RunHistory, ModifiedRunSeed, Apply2, AssumptionEvidenceResolution1,
  AssumptionEvidenceResolutionLink, EvidenceRecordRead } from './ae.contract';
type Equal<A, B> = (<T>() => T extends A ? 1 : 2) extends (<T>() => T extends B ? 1 : 2) ? true : false;
type Assert<T extends true> = T;
type ModelVersion = Assert<Equal<ModelDraft['schema_version'], '1' | '2' | '3'>>;
type CommitVersion = Assert<Equal<ConfigurationCommit3['configuration']['schema_version'], '3'>>;
type Statement = Assert<Equal<ConfigurationRequest3['assumptions'][number]['statement'], string>>;
type Relation = Assert<Equal<ConfigurationRequest3['assumptions'][number]['evidence_links'][number]['relation'], 'supports' | 'challenges' | 'context'>>;
type SnapshotTitle = Assert<Equal<Extract<EvidenceSnapshotRead, {evidence_schema_version:'3'}>['title'], string>>;
type HistoryVersion = Assert<Equal<Extract<RunHistory, {history_schema_version:'2'}>['history_schema_version'], '2'>>;
type SeedVersion = Assert<Equal<ModifiedRunSeed['schema_version'], '1' | '2' | '3' | '4'>>;
type ResolutionLinks = Assert<Equal<AssumptionEvidenceResolution1['links'], AssumptionEvidenceResolutionLink[]>>;
type ResolutionEvidence = Assert<Equal<AssumptionEvidenceResolution1['evidence'], EvidenceRecordRead[]>>;
const draft: AssumptionEvidenceResolution1 = {schema_version:'1', model_digest:null, draft_revision:'draft', model_revision_id:null, links:[], evidence:[]};
const revision: AssumptionEvidenceResolution1 = {schema_version:'1', model_digest:'digest', draft_revision:null, model_revision_id:'revision', links:[], evidence:[]};
// @ts-expect-error Draft and revision selectors cannot both be populated.
const both: AssumptionEvidenceResolution1 = {...draft, model_revision_id:'revision'};
// @ts-expect-error Exactly one selector must be populated.
const neither: AssumptionEvidenceResolution1 = {...draft, draft_revision:null};
// @ts-expect-error A selected revision must carry its digest.
const noDigest: AssumptionEvidenceResolution1 = {...revision, model_digest:null};
// @ts-expect-error A selected draft has no immutable model digest.
const draftDigest: AssumptionEvidenceResolution1 = {...draft, model_digest:'digest'};
// @ts-expect-error Base required fields survive the selector union.
const missingLinks: AssumptionEvidenceResolution1 = {schema_version:'1', model_digest:null, draft_revision:'draft', model_revision_id:null, evidence:[]};
// @ts-expect-error Inherited required selector properties cannot be omitted.
const missingSelector: AssumptionEvidenceResolution1 = {schema_version:'1', model_digest:null, draft_revision:'draft', links:[], evidence:[]};
function selected(value: AssumptionEvidenceResolution1): string {
  if (value.draft_revision !== null) {
    const absent: null = value.model_revision_id;
    const digest: null = value.model_digest;
    return value.draft_revision;
  }
  const revisionId: string = value.model_revision_id;
  const digest: string = value.model_digest;
  return revisionId + digest;
}
const unscoped: EvidenceSnapshotLegacy = {evidence_version_id:'v', kind:'note', content:'Retained', source_refs:[]};
// TypeScript structural unions cannot enforce JSON Schema closed extras; check
// the selected version2 branch here, and both complete schemas above at runtime.
type ScopedLegacy = Extract<EvidenceSnapshotLegacy, {evidence_schema_version:'2'}>;
// @ts-expect-error A selected version2 snapshot requires its resource scope.
const incomplete: ScopedLegacy = {evidence_version_id:'v', kind:'note', content:'Retained', source_refs:[], evidence_schema_version:'2'};
// @ts-expect-error An Apply2 command must explicitly select schema2.
const unversioned: Apply2 = {command_id:'c', expected_revision:'r', edits:[]};
''')
    checked = subprocess.run(['node', str(ROOT / 'ui/node_modules/typescript/bin/tsc'), '--noEmit',
        '--strict', '--skipLibCheck', '--target', 'ES2022', '--moduleResolution', 'Bundler', '--module', 'ESNext', str(proof)],
        env=guard.clean_environment(SCOPE), capture_output=True, text=True)
    (SCOPE.root / 'evidence/types-compile.log').write_text(checked.stdout + checked.stderr)
    assert checked.returncode == 0, checked.stdout + checked.stderr


def create_evidence(api, **updates):
    body = {**evidence_body(api), **updates}
    response = api['client'].post(path(api, 'evidence'), json=body)
    assert response.status_code == 201, response.text
    return response.json()['data']


def test_public_family_revision_cas_exact_reads_and_receipt(api):
    original = create_evidence(api)
    route = path(api, 'evidence-families/' + original['evidence_id'])
    body = {**evidence_body(api), 'expected_revision':original['evidence_version_id'], 'title':'Revised report'}
    revised = api['client'].post(route + '/versions', json=body)
    assert revised.status_code == 201, revised.text
    head = revised.json()['data']
    assert head['evidence_id'] == original['evidence_id']
    assert head['parent_evidence_version_id'] == original['evidence_version_id']
    assert head['evidence_version_id'] != original['evidence_version_id']
    assert api['client'].get(route).json()['data']['head'] == head
    assert api['client'].get(path(api, 'evidence/' + original['evidence_version_id'])).json()['data'] == original
    stale = api['client'].post(route + '/versions', json={**body, 'command_id':uid()})
    assert stale.status_code == 409 and stale.json()['error']['current_revision'] == head['evidence_version_id']
    assert api['client'].post(route + '/versions', json=body).json()['data'] == head
    recovered = api['client'].get(path(api, 'commands/' + body['command_id']) + '?category=evidence')
    assert recovered.json()['data']['result'] == head
    changed = api['client'].post(route + '/versions', json={**body, 'content':'Changed replay'})
    assert changed.status_code == 409
    with api['store'].connection() as db:
        assert db.execute('SELECT COUNT(*) FROM evidence').fetchone()[0] == 2


def test_public_heads_versions_pagination_and_query_binding(api):
    originals = [create_evidence(api, title='Report ' + str(i)) for i in range(3)]
    first = api['client'].get(path(api, 'evidence') + '?view=heads&limit=2')
    assert first.status_code == 200
    page = first.json()
    assert len(page['data']) == 2 and page['next_cursor']
    # A family inserted after the high-water mark must not leak into the continuation.
    create_evidence(api, title='Late report')
    second = api['client'].get(path(api, 'evidence'), params={'view':'heads','limit':2,'cursor':page['next_cursor']})
    assert second.status_code == 200
    combined = page['data'] + second.json()['data']
    assert {r['evidence_version_id'] for r in combined} == {r['evidence_version_id'] for r in originals}
    assert len(combined) == 3 and second.json()['next_cursor'] is None
    mismatch = api['client'].get(path(api, 'evidence'), params={'view':'versions','limit':2,'cursor':page['next_cursor']})
    assert mismatch.status_code == 400
    route = path(api, 'evidence-families/' + originals[0]['evidence_id'] + '/versions')
    versions = api['client'].get(route + '?limit=1')
    assert versions.status_code == 200 and versions.json()['data'] == originals[:1]


def test_public_recorded_labels_do_not_follow_study_rename(api):
    original = create_evidence(api)
    study_url = '/api/1/studies/' + api['sid']
    renamed = api['client'].patch(study_url, json=dict(command_id=uid(), expected_revision=api['study']['revision'], name='Renamed study'))
    assert renamed.status_code == 200
    reread = api['client'].get(path(api, 'evidence/' + original['evidence_version_id']))
    assert reread.status_code == 200 and reread.json()['data'] == original
    assert any(label['name'] == api['study']['name'] for label in original['recorded_context']['resource_labels'])
    later = create_evidence(api)
    assert any(label['name'] == 'Renamed study' for label in later['recorded_context']['resource_labels'])


def test_public_family_scope_and_revoked_replay_do_not_leak(api):
    original_body = evidence_body(api)
    original = create_evidence(api, **original_body)
    other = api['store'].create_study(api['actor'], uid(), 'Other authorized study')
    foreign_route = '/api/1/studies/' + other['study_id'] + '/evidence-families/' + original['evidence_id']
    for suffix in ('', '/versions'):
        response = api['client'].get(foreign_route + suffix)
        assert response.status_code == 404 and original['content'] not in response.text
    with api['store'].connection(write=True) as db:
        db.execute('DELETE FROM memberships WHERE study_id=? AND actor_id=?', (api['sid'], api['actor']))
    for response in (api['client'].get(path(api, 'evidence/' + original['evidence_version_id'])),
                     api['client'].get(path(api, 'evidence-families/' + original['evidence_id'])),
                     api['client'].get(path(api, 'commands/' + original_body['command_id']) + '?category=evidence'),
                     api['client'].post(path(api, 'evidence'), json=original_body)):
        assert response.status_code in (403, 404) and original['content'] not in response.text


@pytest.mark.parametrize('update', [{'title':''}, {'title':' '}, {'title':'x'*201}, {'title':None},
    {'content':''}, {'recorded_context':{}}, {'resource_scope':{'scope_version':'1','kind':'study','study_id':'invalid'}}])
def test_public_closed_create_rejects_malformed_without_writes(api, update):
    response = api['client'].post(path(api, 'evidence'), json={**evidence_body(api), **update})
    assert response.status_code in (400, 422)
    with api['store'].connection() as db:
        assert db.execute('SELECT COUNT(*) FROM evidence').fetchone()[0] == 0


@pytest.mark.parametrize('suffix,method', [('evidence','post'), ('evidence-families/' + '00000000-0000-0000-0000-000000000001' + '/versions','post')])
def test_public_mutations_require_csrf(api, suffix, method):
    api['client'].headers.pop('X-CSRF-Token')
    response = api['client'].request(method, path(api, suffix), json=evidence_body(api))
    assert response.status_code == 403


@pytest.mark.parametrize('suffix', ['', '/versions'])
def test_public_family_reads_require_session(api, suffix):
    api['client'].cookies.clear()
    response = api['client'].get(path(api, 'evidence-families/' + uid() + suffix))
    assert response.status_code == 401


def test_public_titled_evidence_retains_exact_version(api):
    body = evidence_body(api)
    response = api['client'].post(path(api, 'evidence'), json=body)
    assert response.status_code == 201, response.text
    record = response.json()['data']
    assert record['title'] == body['title']
    assert record['parent_evidence_version_id'] is None
    assert record['recorded_context']['label']
    exact = api['client'].get(path(api, 'evidence/' + record['evidence_version_id']))
    assert exact.status_code == 200 and exact.json()['data'] == record


def test_public_original_command_recovery_does_not_duplicate(api):
    body = evidence_body(api)
    saved = api['client'].post(path(api, 'evidence'), json=body)
    assert saved.status_code == 201, saved.text
    recovered = api['client'].get(path(api, 'commands/' + body['command_id']) + '?category=evidence')
    assert recovered.status_code == 200
    assert recovered.json()['data']['result'] == saved.json()['data']
    replay = api['client'].post(path(api, 'evidence'), json=body)
    assert replay.status_code == 201 and replay.json()['data'] == saved.json()['data']
    changed = api['client'].post(path(api, 'evidence'), json={**body, 'title': 'Changed replay'})
    assert changed.status_code == 409
    with api['store'].connection() as db:
        assert db.execute('SELECT COUNT(*) FROM evidence').fetchone()[0] == 1


@pytest.mark.parametrize('update', [{'expected_revision':'invalid'}, {'title':' '}, {'recorded_context':{}}, {'evidence_id':'forged'}, {'evidence_schema_version':'2'}])
def test_public_revision_is_closed_and_atomic(api, update):
    original=create_evidence(api)
    route=path(api,'evidence-families/'+original['evidence_id'])
    body={**evidence_body(api),'expected_revision':original['evidence_version_id'],**update}
    response=api['client'].post(route+'/versions',json=body)
    assert response.status_code in (400,422)
    assert api['client'].get(route).json()['data']['head']==original
    with api['store'].connection() as db:
        assert db.execute('SELECT COUNT(*) FROM evidence').fetchone()[0]==1


def test_public_readonly_actor_can_read_but_cannot_mutate_or_replay(api):
    body=evidence_body(api);original=create_evidence(api,**body)
    family=path(api,'evidence-families/'+original['evidence_id'])
    with api['store'].connection(write=True) as db:
        db.execute("UPDATE memberships SET role='reader' WHERE actor_id=? AND study_id=?",(api['actor'],api['sid']))
    for url in (family,family+'/versions',path(api,'evidence'),path(api,'evidence/'+original['evidence_version_id'])):
        assert api['client'].get(url).status_code==200
    for url,request in ((path(api,'evidence'),body),(family+'/versions',{**evidence_body(api),'expected_revision':original['evidence_version_id']})):
        response=api['client'].post(url,json=request)
        assert response.status_code==403 and original['content'] not in response.text


def test_public_revocation_blocks_every_family_and_exact_read_and_revision_replay(api):
    original=create_evidence(api);family=path(api,'evidence-families/'+original['evidence_id'])
    body={**evidence_body(api),'expected_revision':original['evidence_version_id']}
    assert api['client'].post(family+'/versions',json=body).status_code==201
    with api['store'].connection(write=True) as db:
        db.execute('DELETE FROM memberships WHERE actor_id=? AND study_id=?',(api['actor'],api['sid']))
    for url in (family,family+'/versions',path(api,'evidence'),path(api,'evidence/'+original['evidence_version_id']),path(api,'commands/'+body['command_id'])+'?category=evidence'):
        response=api['client'].get(url)
        assert response.status_code in (403,404) and original['content'] not in response.text
    response=api['client'].post(family+'/versions',json=body)
    assert response.status_code in (403,404) and original['content'] not in response.text


@pytest.mark.parametrize('query',['?unknown=x','?limit=0','?limit=101','?limit=1&limit=2','?cursor=invalid'])
def test_public_family_pages_reject_unbounded_or_ambiguous_query(api,query):
    original=create_evidence(api)
    assert api['client'].get(path(api,'evidence-families/'+original['evidence_id']+'/versions')+query).status_code==400


def associated_model(api):
    mid=uid()
    with api['store'].connection(write=True) as db:
        db.execute('INSERT INTO model_associations(study_id,model_id,command_id) VALUES(?,?,?)',(api['sid'],mid,uid()))
    return mid


@pytest.mark.parametrize('query',['','?draft_revision=x&model_revision_id=bad','?draft_revision=x&draft_revision=y','?other=x','?draft_revision=','?model_revision_id=bad'])
def test_public_diagnostic_selector_exclusive_closed_and_bounded(api,query):
    mid=associated_model(api)
    response=api['client'].get(path(api,'models/'+mid+'/assumption-evidence')+query)
    assert response.status_code==400


@pytest.mark.parametrize('selector',['draft_revision','model_revision_id'])
def test_public_diagnostic_dispatch_scoped_coordinator_double(api,monkeypatch,selector):
    # API dispatch/authorization proof only, not native assumption resolution.
    from hyprn_mvp_app.modeling import Coordinator
    original=create_evidence(api);mid=associated_model(api);selected=uid();calls=[]
    result=dict(schema_version='1',model_digest='a'*64 if selector=='model_revision_id' else None,
        draft_revision=selected if selector=='draft_revision' else None,
        model_revision_id=selected if selector=='model_revision_id' else None,
        links=[dict(assumption_id=uid(),evidence_version_id=original['evidence_version_id'],status='resolved')],evidence=[original])
    def resolver(self,actor,sid,model_id,**selectors):
        calls.append((actor,sid,model_id,selectors));return result
    monkeypatch.setattr(Coordinator,'assumption_evidence',resolver,raising=False)
    url=path(api,'models/'+mid+'/assumption-evidence')+'?'+selector+'='+selected
    response=api['client'].get(url)
    assert response.status_code==200 and response.json()['data']==result
    assert calls==[(api['actor'],api['sid'],mid,{'model_revision_id':result['model_revision_id'],'draft_revision':result['draft_revision']})]
    other=api['store'].create_study(api['actor'],uid(),'Other')
    assert api['client'].get(url.replace(api['sid'],other['study_id'])).status_code==404
    with api['store'].connection(write=True) as db:
        db.execute('DELETE FROM memberships WHERE actor_id=? AND study_id=?',(api['actor'],api['sid']))
    assert api['client'].get(url).status_code in (403,404)
    api['client'].cookies.clear()
    assert api['client'].get(url).status_code==401
    assert len(calls)==1


def test_public_pending_features_unavailable_and_evidence_capability_truthful(api):
    caps=api['client'].get('/api/1/capabilities').json()['data']
    assert 'evidence_revisions/1' in caps['engineering']
    for pending in ('model_assumptions/1','configuration_assumptions/1'):
        assert pending in caps['unavailable'] and pending not in caps['engineering']+caps['modeling']
    mid=associated_model(api)
    response=api['client'].get(path(api,'models/'+mid+'/assumption-evidence')+'?draft_revision=exact-token')
    assert response.status_code==422 and response.json()['error']['code']=='unsupported_capability'
    from test_assumptions_evidence_contracts import sample,D
    body=sample(D['ConfigurationRequest3']);body['study_id']=api['sid']
    commit=dict(command_id=uid(),configuration_id=None,expected_revision=None,expected_preview_digest='a'*64,configuration=body)
    for url,value in ((path(api,'configurations/preview'),body),(path(api,'configurations'),commit)):
        response=api['client'].post(url,json=value)
        assert response.status_code==422 and response.json()['error']['code']=='unsupported_capability'
    with api['store'].connection() as db:
        assert db.execute('SELECT COUNT(*) FROM configurations').fetchone()[0]==0


def test_public_configuration3_closed_dispatch_double_preserves_request(api,monkeypatch):
    # Only the typed API dispatch seam; actual closure implementation is11.3.
    from hyprn_mvp_app.configuration import Configurations
    from test_assumptions_evidence_contracts import sample,D
    body=sample(D['ConfigurationRequest3']);body['study_id']=api['sid']
    calls=[]
    monkeypatch.setattr(Configurations,'_preview3',lambda *_:None,raising=False)
    monkeypatch.setattr(Configurations,'_commit3',lambda *_:None,raising=False)
    def preview(self,actor,sid,value):
        calls.append(('preview',actor,sid,value));return ({'dispatch':'preview'},None,None)
    def commit(self,actor,sid,value):
        calls.append(('commit',actor,sid,value));return {'dispatch':'commit'}
    monkeypatch.setattr(Configurations,'preview',preview);monkeypatch.setattr(Configurations,'commit',commit)
    command=dict(command_id=uid(),configuration_id=None,expected_revision=None,expected_preview_digest='a'*64,configuration=body)
    assert api['client'].post(path(api,'configurations/preview'),json=body).status_code==200
    assert api['client'].post(path(api,'configurations'),json=command).status_code==201
    assert calls==[('preview',api['actor'],api['sid'],body),('commit',api['actor'],api['sid'],command)]
    for url,value in ((path(api,'configurations/preview'),{**body,'evidence_version_ids':[]}),(path(api,'configurations'),{**command,'unexpected':True})):
        assert api['client'].post(url,json=value).status_code==400
    assert len(calls)==2


def test_public_client_original_commands_cancellation_and_session_binding():
    # Execute the actual typed client with deterministic HTTP doubles. No UI or
    # native execution is claimed; server behavior is exercised separately above.
    folder=guard.scoped_path(SCOPE,'artifacts/client');folder.mkdir()
    for name in ('api.ts','contract.ts'):
        (folder/name).write_bytes((ROOT/'ui/src'/name).read_bytes())
    compile_command=['node',str(ROOT/'ui/node_modules/typescript/bin/tsc'),'--strict','--skipLibCheck',
        '--target','ES2022','--module','commonjs','--lib','ES2022,DOM','--outDir',str(folder/'js'),str(folder/'api.ts')]
    result=subprocess.run(compile_command,env=guard.clean_environment(SCOPE),capture_output=True,text=True)
    (SCOPE.root/'evidence/client-compile.log').write_text(result.stdout+result.stderr)
    assert result.returncode==0,result.stdout+result.stderr
    script=folder/'client-check.cjs'
    script.write_text('''const assert = require('node:assert/strict');
const client = require('./js/api.js');
const [[, PublicApi], ...otherApis] = Object.entries(client).filter(([name, value]) => typeof value === 'function' && /Api$/.test(name));
assert.equal(otherApis.length, 0, 'one public API client class');
const response = (data, status=200) => ({ ok:status<400, status, json:async()=>status<400?{schema_version:'1',data}:data });
async function main() {
  const api = new PublicApi(); api.actor='owner'; api.csrf='csrf';
  const command={command_id:'original',evidence_schema_version:'3',title:'Original',content:'Bytes',kind:'note',source_refs:[],resource_scope:{scope_version:'1',kind:'study',study_id:'study'}};
  const sent=[];
  global.fetch=async(url, options)=>{sent.push([url,JSON.parse(options.body)]);throw new Error('lost response');};
  await assert.rejects(api.createEvidenceCommand('study',command));
  command.title='Edited after send';
  assert.equal(api.pending.body.title,'Original');
  assert.equal(api.pending.body.command_id,'original');
  await assert.rejects(api.reviseEvidence('study','family',{...command,expected_revision:'head'}),/original command/);
  assert.equal(sent.length,1);
  const adopted={command_id:'original',state:'committed',result:{title:'Original'},error:null,
    recovery:'adopt'};
  global.fetch=async(url)=>{
    assert.equal(url,'/api/1/studies/study/commands/original?category=evidence');
    return response(adopted);
  };
  const receipt=await api.reconcile();assert.equal(receipt.result.title,'Original');assert.equal(api.pending,null);
  const abort=new AbortController();
  global.fetch=async(_url, options)=>new Promise((_resolve,reject)=>options.signal.addEventListener('abort',()=>reject(options.signal.reason)));
  const mutation=api.reviseEvidence('study','family',{...command,expected_revision:'head'},abort.signal);
  abort.abort();await assert.rejects(mutation);assert.equal(api.pending.path,'/studies/study/evidence-families/family/versions');
  global.fetch=async()=>response(adopted);await api.reconcile();
  const stale=new AbortController();let deliver;
  global.fetch=async()=>({ok:true,status:200,json:()=>new Promise(resolve=>{deliver=resolve;})});
  const read=api.evidenceVersion('study','version',stale.signal);await new Promise(resolve=>setImmediate(resolve));
  stale.abort();deliver({data:{title:'Do not display'}});await assert.rejects(read);
  global.fetch=async()=>{api.actor='different-owner';return response({title:'Do not display'});};
  await assert.rejects(api.evidenceFamily('study','family'),/session changed/);
  api.actor='owner';let loss=0;api.onAuthorizationLoss=()=>loss++;
  global.fetch=async()=>response({error:{code:'forbidden',message:'revoked',fields:[],outcome:'unchanged'}},401);
  await assert.rejects(api.evidenceVersion('study','version'));assert.equal(api.actor,'');assert.equal(loss,1);
  api.actor='owner';const calls=[];
  global.fetch=async(url,options)=>{calls.push([url,JSON.parse(options.body)]);return response({instances:[],connections:[],definitions:[]});};
  const model={study_id:'study',model_id:'model',draft_revision:'draft'};
  const apply={schema_version:'2',command_id:'stable-command',expected_revision:'draft',edits:[{kind:'rename_model',name:'Changed'}]};
  await api.previewEdits(model,apply);await api.applyCommand(model,apply);
  assert.deepEqual(calls[0][1],{schema_version:'2',expected_revision:'draft',edits:apply.edits});
  assert.deepEqual(calls[1][1],apply);assert.equal(apply.command_id,'stable-command');
  console.log('Client recovery, cancellation, authorization and command identity passed');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
''')
    result=subprocess.run(['node',str(script)],env=guard.clean_environment(SCOPE),capture_output=True,text=True)
    (SCOPE.root/'evidence/client-runtime.log').write_text(result.stdout+result.stderr)
    assert result.returncode==0,result.stdout+result.stderr
