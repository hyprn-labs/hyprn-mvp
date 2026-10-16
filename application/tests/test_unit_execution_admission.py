"""App-only admission; captured native bytes are synthetically resealed, never run.

The transport/runtime doubles establish pre-dispatch validation, not native
numerical execution, history completion or current worker qualification.
"""
from copy import deepcopy
import base64
import json
from pathlib import Path
import subprocess
import sys

import scoped_fixture as guard
from checks import PROJECTION_SCOPE
SCOPE = PROJECTION_SCOPE or guard.scope_from_environment()
guard.validate_scope(SCOPE)

import pytest
from execution_fixtures import fixture, runtime_fixture
from test_approach_closure import sample, D, link, signed, resolution
from hyprn_mvp_app.approach_closure import build_closure
from hyprn_mvp_app.execution import (
    assemble_bundle,
    validate_frozen_configuration,
    validate_preparation,
    validate_retained_bundle,
    executable_digest,
    raw_hash,
    StaticPreparation,
    Submissions,
)
from hyprn_mvp_app.modeling import validate
from hyprn_mvp_app.units import UNIT_CATALOG_DIGEST as CURRENT_CATALOG_DIGEST

# This admission corpus retains its original producer bytes and conversion proofs.
UNIT_CATALOG_DIGEST = 'f9278b0e59aa2d410dcd14a2abc1306d3d18adcf9edbb433002f6466489939f3'
from hyprn_mvp_app.scientific_configuration import project_scientific_configuration as project
from hyprn_mvp_app.store import canonical, digest, uid, Store, DomainError

CATALOG_PATH = 'provenance/patched/config/modeling.units.json'
REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope='module')
def catalog(tmp_path_factory):
    # The producer's patched catalog is the 040 catalog with the 080 catalog hunk applied once,
    # exactly; the fixture carries those bytes.
    root = tmp_path_factory.mktemp('catalog')
    (root / 'config').mkdir()
    created = (REPO / 'upstream/whatsopt-patches/040-modeling-contract.patch').read_text()
    section = created.split('+++ b/config/modeling.units.json\n', 1)[1].split('\n--- ', 1)[0]
    (root / 'config/modeling.units.json').write_text(
        '\n'.join(line[1:] for line in section.splitlines()[1:] if line.startswith('+')) + '\n'
    )
    patch = (REPO / 'upstream/whatsopt-patches/080-unit-declarations.patch').read_text()
    patch = patch[patch.index('--- a/config/modeling.units.json') :]
    result = subprocess.run(
        ['patch', '--batch', '--forward', '--fuzz=0', '-p1'],
        input=patch,
        text=True,
        cwd=root,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'offset' not in result.stdout and 'fuzz' not in result.stdout
    current = json.loads((root / 'config/modeling.units.json').read_bytes())
    assert current['catalog_digest'] == CURRENT_CATALOG_DIGEST
    value = json.loads(fixture()['files'][CATALOG_PATH])
    assert current['supported_units'][: len(value['supported_units'])] == value['supported_units']
    assert all(pair in current['linear_pairs'] for pair in value['linear_pairs'])
    assert (
        raw_hash(
            json.dumps(
                {k: v for k, v in value.items() if k != 'catalog_digest'},
                sort_keys=True,
                separators=(',', ':'),
                allow_nan=False,
            ).encode()
        )
        == UNIT_CATALOG_DIGEST
    )
    return value


def repin(case):
    """Rehash all affected envelopes so semantic negatives cannot pass on stale hashes."""
    f=case['frozen'];m=f['model_snapshot'];c=f['configuration'];p=case['prepared'];files=case['files']
    for value in (m,c): signed(value)
    files['model.json']=canonical(m)
    package=p['model_package_manifest']
    package.update(schema_version=m['schema_version'],revisions=[deepcopy(m)],required_capabilities=list(m['required_capabilities']))
    for row in package['files']:
        if row['path'].startswith('revisions/'):
            row.update(size=len(canonical(m)),sha256=raw_hash(canonical(m)))
    signed(package)
    provenance=json.loads(files[p['generator_identity']['provenance_path']])
    for row in provenance['patched_files']:
        raw=files[row['path']];row.update(size=len(raw),sha256=raw_hash(raw))
    provenance['adapter_source']=deepcopy(next(row for row in provenance['patched_files'] if row['path']==provenance['adapter_source']['path']))
    identity=p['generator_identity']
    for key,rows in [('generator_digest',[r for r in provenance['patched_files'] if r['role']=='generator']),
                     ('template_digest',[r for r in provenance['patched_files'] if r['role']=='template']),
                     ('adapter_digest',[r for r in provenance['patched_files'] if r['role'] not in ('generator','template')])]:
        identity[key]=digest(rows)
    files[identity['provenance_path']]=canonical(provenance)
    for row in p['files']:
        raw=files[row['path']];row.update(size=len(raw),sha256=raw_hash(raw))
    p.update(model_digest=m['digest'],configuration_digest=project(c)['digest'])
    p['executable_content_digest']=executable_digest(p)
    p['prepared_digest']=digest({k:v for k,v in p.items() if k!='prepared_digest'})


def case6(catalog, linked=False, legacy=False):
    case=fixture();f=case['frozen'];m=f['model_snapshot'];c=f['configuration']
    m.update(schema_version='2' if legacy else '3',assumptions=[],root_instance_id=m['instances'][0]['instance_id'])
    if not legacy:
        m['required_capabilities'].append('unit_declarations/1')
        for d in m['definitions']:
            for port in d['ports']:port['units']={'kind':'dimensionless'}
        case['files'][CATALOG_PATH]=json.dumps(catalog,sort_keys=True,indent=2).encode()
    m['ports']=deepcopy([p for d in m['definitions'] for p in d['ports']])
    c.update(schema_version='4',approach_binding=None,context_source=dict(kind='current_study',expected_study_revision='fixture:1'),
             derivation=None,assumptions=[],general_context_evidence_version_ids=[],
             required_capabilities=[*m['required_capabilities'],'configuration_assumptions/1'])
    for item in c['inputs']:item['result_binding']=None
    f.update(schema_version='4' if legacy else '5',approach_closure=None)
    case['prepared']['required_capabilities']=list(m['required_capabilities'])
    repin(case)
    if linked:
        v=sample(D['ApproachVersion1']);v['study_id']=c['study_id'];link(v,m)
        closure=build_closure(v,resolution(models=[m]),study_id=c['study_id'])
        f['approach_closure']=closure
        c['approach_binding']=dict(approach_id=v['approach_id'],approach_version_id=v['approach_version_id'],
            approach_digest=v['digest'],closure_digest=closure['digest'],case_id=None)
        repin(case)
    return case


def deps():return dict(schema_version='1',sources=[],mappings=[])


def assemble(case, dependencies=None):
    b=assemble_bundle(uid(),case['prepared'],case['files'],case['frozen'],runtime_fixture(),
        None if case['frozen']['configuration']['schema_version']=='1' else dependencies or deps())
    r=dict(run_id=b['manifest']['run_id'],scope=case['frozen']['configuration']['study_id'],command_id=uid(),payload_digest='a'*64,bundle_digest=b['manifest']['bundle_digest'])
    return b,r


def reseal(bundle,request):
    for row in bundle['manifest']['files']:
        raw=bundle['files'][row['path']];row.update(size=len(raw),sha256=raw_hash(raw))
    m=bundle['manifest'];m['bundle_digest']=digest({k:v for k,v in m.items() if k!='bundle_digest'})
    request['bundle_digest']=m['bundle_digest']


@pytest.mark.parametrize('linked',[False,True])
def test_exact_frozen5_bundle6_private3_retains_originals(catalog,linked):
    case=case6(catalog,linked);before=deepcopy(case)
    validate_frozen_configuration(case['frozen'])
    bundle,request=assemble(case)
    assert bundle['manifest']['schema_version']=='6'
    validate_retained_bundle(bundle,request,case['frozen'])
    assert case==before
    assert bundle['files']['modeling-configuration.json']==canonical(project(case['frozen']['configuration']))
    assert json.loads(bundle['files']['modeling-configuration.json'])['schema_version']=='3'
    assert ('approach/closure.json' in bundle['files'])==linked
    assert bundle['manifest']['required_capabilities']==['flat_explicit_scalar','unit_declarations/1']
    assert not any(n.split('.')[0] in ('aiida','openmdao','openturns') for n in sys.modules)
    assert not any(n in sys.modules for n in ('hyprn_mvp_integration.worker','hyprn_mvp_integration.launcher'))


@pytest.mark.parametrize('change',['frozen4','missing_frozen_version','config3','model2','missing_model_capability','missing_prepared_capability','missing_private_capability'])
def test_exact_new_pairing_and_capabilities_before_preparation(catalog,change):
    case=case6(catalog);f=case['frozen'];m=f['model_snapshot'];c=f['configuration']
    if change=='frozen4':f['schema_version']='4'
    elif change=='missing_frozen_version':del f['schema_version']
    elif change=='config3':c['schema_version']='3';del c['approach_binding']
    elif change=='model2':m['schema_version']='2'
    elif change=='missing_model_capability':m['required_capabilities'].remove('unit_declarations/1')
    elif change=='missing_prepared_capability':case['prepared']['required_capabilities'].remove('unit_declarations/1')
    else:c['required_capabilities'].remove('unit_declarations/1')
    repin(case)
    with pytest.raises((ValueError,DomainError)):assemble(case)


@pytest.mark.parametrize('change',['input','output','connected','old_active','second_old','malformed_unused'])
def test_exact_active_units_rejected_before_remote_call(catalog,change):
    case=case6(catalog);m=case['frozen']['model_snapshot'];old=deepcopy(m['definitions'][0]);old['definition_version_id']=uid()
    for p in old['ports']:p.update(definition_version_id=old['definition_version_id'],units={'kind':'unspecified'})
    m['definitions'].append(old)
    if change=='old_active':m['instances'][0]['definition_version_id']=old['definition_version_id']
    elif change=='second_old':m['instances'].append(dict(instance_id=uid(),definition_version_id=old['definition_version_id'],name='Old active'))
    elif change=='malformed_unused':old['ports'][0]['units']={'kind':'unspecified','expression':''}
    else:
        target=(case['frozen']['configuration']['inputs'][0]['target'] if change=='input'
                else m['connections'][0]['target_ref'] if change=='connected' else m['connections'][0]['source_ref'])
        instance=next(i for i in m['instances'] if i['instance_id']==target['instance_id'])
        definition=next(d for d in m['definitions'] if d['definition_version_id']==instance['definition_version_id'])
        next(p for p in definition['ports'] if p['port_id']==target['port_id'])['units']={'kind':'unspecified'}
    m['ports']=deepcopy([p for d in m['definitions'] for p in d['ports']]);repin(case)
    class Unavailable:
        def call(self,*a,**k):pytest.fail('Unresolved model crossed private boundary')
    with pytest.raises((ValueError,DomainError)):StaticPreparation(Unavailable())(uid(),m['model_id'],uid(),case['frozen'])


@pytest.mark.parametrize('unused',['unspecified','legacy'])
def test_retained_shared_port_versions_do_not_block_active_exact_version(catalog,unused):
    case=case6(catalog);m=case['frozen']['model_snapshot'];old=deepcopy(m['definitions'][0]);old['definition_version_id']=uid()
    for p in old['ports']:p.update(definition_version_id=old['definition_version_id'],units={'kind':'unspecified'} if unused=='unspecified' else '')
    m['definitions'].insert(0,old);m['ports']=deepcopy([p for d in m['definitions'] for p in d['ports']]);repin(case)
    before=deepcopy(m);bundle,request=assemble(case)
    validate_retained_bundle(bundle,request,case['frozen']);assert m==before


@pytest.mark.parametrize('change',['binding_units','binding_target','binding_duplicate','catalog_digest','catalog_factor','catalog_engine','catalog_missing','catalog_duplicate_key','native_source','source_map'])
def test_rehashed_preparation_tampering_refused(catalog,change):
    case=case6(catalog);p=case['prepared'];files=case['files']
    if change.startswith('binding'):
        path=p['entrypoint']['bindings_path'];value=json.loads(files[path])
        if change=='binding_units':value['outputs'][0]['units']='m'
        elif change=='binding_target':value['outputs'][0]['target']['instance_id']=uid()
        else:value['outputs'].append(deepcopy(value['outputs'][0]))
        files[path]=canonical(value)
    elif change=='native_source':files[next(k for k in files if k.startswith('sources/'))]+=b'\n'
    elif change=='source_map':
        path=p['entrypoint']['source_map_path'];value=json.loads(files[path]);value['entries'][0]['definition_version_id']=uid();files[path]=canonical(value)
    else:
        value=deepcopy(catalog)
        if change=='catalog_digest':value['catalog_digest']='0'*64
        elif change=='catalog_factor':value['linear_pairs'][0][2]=2
        elif change=='catalog_engine':value['version']='0.0.0'
        elif change=='catalog_missing':value={}
        files[CATALOG_PATH]=json.dumps(value,sort_keys=True,indent=2).encode()
        if change=='catalog_duplicate_key':files[CATALOG_PATH]=files[CATALOG_PATH].replace(b'{',b'{"engine":"forged",',1)
    repin(case)
    with pytest.raises((ValueError,DomainError)):assemble(case)


@pytest.mark.parametrize('change',['old_bundle','raw','private_pair','private_bytes','dependency_role','dependency_raw','approach_role','approach_raw','manifest_pin','config_raw','model_raw','generator'])
def test_retained_bundle_tamper_is_rejected_after_manifest_rehash(catalog,change):
    case=case6(catalog,True);b,r=assemble(case);m=b['manifest'];files=b['files']
    if change=='old_bundle':m['schema_version']='5'
    elif change=='raw':files['context.json']+=b' '
    elif change in ('private_pair','private_bytes'):
        value=json.loads(files['modeling-configuration.json']);value['schema_version']='2' if change=='private_pair' else '3'
        if change=='private_bytes':value['name']='changed'
        signed(value);files['modeling-configuration.json']=canonical(value)
    elif change.endswith('_role'):
        path='result-dependencies.json' if change.startswith('dependency') else 'approach/closure.json'
        next(row for row in m['files'] if row['path']==path)['role']='evidence'
    elif change=='dependency_raw':files['result-dependencies.json']=b'{}'
    elif change=='approach_raw':files['approach/closure.json']+=b' '
    elif change=='manifest_pin':m['approach_closure_digest']='0'*64
    elif change=='config_raw':files['configuration.json']+=b' '
    elif change=='model_raw':files['model.json']+=b' '
    else:m['generator']['adapter_digest']='0'*64
    if change!='raw':reseal(b,r)
    with pytest.raises((ValueError,DomainError)):validate_retained_bundle(b,r,case['frozen'])


@pytest.mark.parametrize('linked',[False,True])
def test_existing_model2_bundle5_remains_exact(catalog,linked):
    case=case6(catalog,linked,legacy=True);before=deepcopy(case);b,r=assemble(case)
    assert b['manifest']['schema_version']=='5'
    validate_retained_bundle(b,r,case['frozen']);assert case==before


def submission(tmp_path,catalog):
    store=Store(tmp_path/'app.sqlite');actor=uid();sid=store.create_study(actor,uid(),'Unit admission')['study_id']
    case=case6(catalog);case['frozen']['configuration']['study_id']=sid;repin(case)
    c=case['frozen']['configuration']
    with store.connection(write=True) as db:
        db.execute('INSERT INTO configurations VALUES(?,?,?,?)',(c['configuration_revision_id'],c['configuration_id'],sid,json.dumps(case['frozen'])))
    class Native:
        launches=0
        def require_attestation(self):return True
        def bundle_runtime(self):return runtime_fixture()
        def launch(self,*args):self.launches+=1;raise TimeoutError('Explicit uncertain native double')
    native=Native();service=Submissions(store,lambda *a:(case['prepared'],case['files']),native)
    return service,store,actor,sid,case,native


def test_prepared_retry_exact_bundle6_idempotency_and_uncertain_no_retry(tmp_path,catalog):
    service,store,actor,sid,case,native=submission(tmp_path,catalog)
    body=dict(command_id=uid(),configuration_revision_id=case['frozen']['configuration']['configuration_revision_id'])
    accepted=service.submit(actor,sid,body);rid=accepted['run_id'];service.dispatch(rid,prepare_only=True)
    assert service.read(actor,sid,rid)['state']=='prepared'
    assert service.submit(actor,sid,body)['run_id']==rid
    with store.connection() as db:before=json.loads(db.execute('SELECT payload FROM outbox WHERE run_id=?',(rid,)).fetchone()[0])['bundle']
    service.dispatch(rid);assert native.launches==1 and service.read(actor,sid,rid)['state']=='uncertain'
    native.matches=lambda request:[]
    service.dispatch(rid);assert native.launches==1
    with store.connection() as db:after=json.loads(db.execute('SELECT payload FROM outbox WHERE run_id=?',(rid,)).fetchone()[0])['bundle']
    assert before==after


def test_retained_tamper_stops_before_claim_or_native_dispatch(tmp_path,catalog):
    service,store,actor,sid,case,native=submission(tmp_path,catalog)
    accepted=service.submit(actor,sid,dict(command_id=uid(),configuration_revision_id=case['frozen']['configuration']['configuration_revision_id']))
    rid=accepted['run_id'];service.dispatch(rid,prepare_only=True)
    with store.connection(write=True) as db:
        payload=json.loads(db.execute('SELECT payload FROM outbox WHERE run_id=?',(rid,)).fetchone()[0])
        payload['bundle']['files']['modeling-configuration.json']=base64.b64encode(b'{}').decode()
        db.execute('UPDATE outbox SET payload=? WHERE run_id=?',(json.dumps(payload),rid))
    with pytest.raises(ValueError):service.dispatch(rid)
    assert native.launches==0
    with store.connection() as db:assert db.execute('SELECT state FROM outbox WHERE run_id=?',(rid,)).fetchone()[0]=='accepted_run'


def physical(case):
    m=case['frozen']['model_snapshot'];c=case['frozen']['configuration']
    for d in m['definitions']:
        for port in d['ports']:port['units']={'kind':'physical','expression':'J/kg'}
    m['ports']=deepcopy([p for d in m['definitions'] for p in d['ports']])
    for item in c['inputs']:item['units']='MJ/kg'
    path=case['prepared']['entrypoint']['bindings_path'];bindings=json.loads(case['files'][path])
    for row in bindings['inputs']+bindings['outputs']:row['units']='J/kg'
    case['files'][path]=canonical(bindings)
    c['criteria']=[dict(sample(D['Criterion']),target=deepcopy(bindings['outputs'][0]['target']),units='kJ/kg')]
    repin(case)


def linked_result(case,value=0):
    c=case['frozen']['configuration'];item=c['inputs'][0];item['value']=value
    source=sample(D['NativeSource']);rid=uid()
    source.update(source_run_id=rid,result_uuid=uid(),results_digest='a'*64)
    source['request'].update(run_id=rid,scope=c['study_id'])
    source['label']='r'+source['result_uuid'].replace('-','')
    binding=sample(D['ResultBinding'])
    binding.update(source_run_id=rid,source_configuration_digest='b'*64,results_digest=source['results_digest'],
        source_output=dict(instance_id=uid(),port_id=uid()),original_value=value,original_units='MJ/kg')
    binding['conversion']=dict(policy='openmdao-linear-catalog-1',catalog_digest=UNIT_CATALOG_DIGEST,
        source_units='MJ/kg',destination_units='J/kg',factor=1000000.0,destination_value=value*1000000)
    item['result_binding']=binding;c['required_capabilities'].append('result_linked_inputs/1')
    dependencies=dict(schema_version='1',sources=[source],mappings=[dict(target=item['target'],source_label=source['label'],
        **{k:binding[k] for k in ('source_output','results_digest','original_value','original_units','conversion')})])
    repin(case)
    return deepcopy(dependencies)


@pytest.mark.parametrize('value',[0,2])
def test_original_source_value_units_native_identity_and_conversion_retained(catalog,value):
    case=case6(catalog);physical(case);dependencies=linked_result(case,value)
    original=deepcopy(case);expected=deepcopy(dependencies);b,r=assemble(case,dependencies)
    validate_retained_bundle(b,r,case['frozen'])
    assert case==original and dependencies==expected
    retained=json.loads(b['files']['result-dependencies.json'])
    assert retained==expected
    item=json.loads(b['files']['configuration.json'])['inputs'][0]
    assert (item['value'],item['units'])==(value,'MJ/kg')
    assert item['result_binding']['conversion']['destination_value']==value*1000000
    assert retained['sources'][0]['association']==expected['sources'][0]['association']
    assert retained['sources'][0]['result_uuid']==expected['sources'][0]['result_uuid']
    assert retained['mappings'][0]['conversion']['catalog_digest']==UNIT_CATALOG_DIGEST


@pytest.mark.parametrize('change',['catalog','factor','destination','source','original','product','native_uuid','native_origin','mapping','request_scope','unused_source'])
def test_conversion_and_native_dependency_tampering_before_dispatch(catalog,change):
    case=case6(catalog);physical(case);dependencies=linked_result(case,2)
    c=case['frozen']['configuration'];binding=c['inputs'][0]['result_binding'];conversion=binding['conversion']
    if change=='catalog':conversion['catalog_digest']='0'*64
    elif change=='factor':conversion.update(factor=2,destination_value=4)
    elif change=='destination':conversion['destination_units']='m'
    elif change=='source':conversion['source_units']='kJ/kg'
    elif change=='original':binding['original_value']=3
    elif change=='product':conversion['destination_value']=1
    elif change=='native_uuid':dependencies['sources'][0]['result_uuid']=uid()
    elif change=='native_origin':dependencies['sources'][0]['association']['store_uuid']='invalid'
    elif change=='mapping':dependencies['mappings'][0]['source_output']['port_id']=uid()
    elif change=='request_scope':dependencies['sources'][0]['request']['scope']=uid()
    else:dependencies['sources'].append(deepcopy(dependencies['sources'][0]))
    repin(case)
    with pytest.raises((ValueError,DomainError)):assemble(case,dependencies)


@pytest.mark.parametrize('change',['connection','input','criterion','affine'])
def test_catalog_rejects_incompatible_resolved_units(catalog,change):
    case=case6(catalog);physical(case);c=case['frozen']['configuration'];m=case['frozen']['model_snapshot']
    if change=='input':c['inputs'][0]['units']='m'
    elif change=='criterion':c['criteria'][0]['units']='m'
    elif change=='affine':
        for d in m['definitions']:
            for p in d['ports']:p['units']={'kind':'physical','expression':'K'}
        m['ports']=deepcopy([p for d in m['definitions'] for p in d['ports']])
        for i in c['inputs']:i['units']='degC'
        c['criteria'][0]['units']='K'
        path=case['prepared']['entrypoint']['bindings_path'];b=json.loads(case['files'][path])
        for row in b['inputs']+b['outputs']:row['units']='K'
        case['files'][path]=canonical(b)
    else:
        ref=m['connections'][0]['target_ref'];i=next(i for i in m['instances'] if i['instance_id']==ref['instance_id'])
        d=next(d for d in m['definitions'] if d['definition_version_id']==i['definition_version_id'])
        next(p for p in d['ports'] if p['port_id']==ref['port_id'])['units']={'kind':'physical','expression':'m'}
        m['ports']=deepcopy([p for d in m['definitions'] for p in d['ports']])
    repin(case)
    with pytest.raises((ValueError,DomainError)):assemble(case)


@pytest.mark.parametrize('version',['1','2','3'])
def test_legacy_bundle2_to_4_preserves_exact_retained_bytes(catalog,version):
    case=fixture();f=case['frozen'];c=f['configuration']
    if version!='1':
        c.update(schema_version=version,context_source=dict(kind='current_study',expected_study_revision='fixture:1'),derivation=None)
        for i in c['inputs']:i['result_binding']=None
        if version=='3':
            c.update(assumptions=[],general_context_evidence_version_ids=[])
            c['required_capabilities'].append('configuration_assumptions/1')
        repin(case)
    before=deepcopy(case)
    b=assemble_bundle(uid(),case['prepared'],case['files'],f,runtime_fixture(),None if version=='1' else deps())
    r=dict(run_id=b['manifest']['run_id'],scope=c['study_id'],command_id=uid(),payload_digest='a'*64,bundle_digest=b['manifest']['bundle_digest'])
    assert b['manifest']['schema_version']==str(int(version)+1)
    validate_retained_bundle(b,r,f);assert case==before


def test_bridge_roundtrip_keeps_exact_bundle6_bytes(catalog):
    from hyprn_mvp_app.dispatcher import encode_files,decode_files,bridge_request,bridge_operation
    case=case6(catalog);b,r=assemble(case)
    raw=bridge_request('launch',[encode_files(b),r]);method,args=bridge_operation(raw)
    assert method=='launch' and args[1]==r and decode_files(args[0])==b


@pytest.mark.parametrize('path',['model.json','generated/entry.py','provenance/patched/config/modeling.units.json','configuration.json'])
def test_bundle6_file_role_tamper_cannot_relabel_retained_native_content(catalog,path):
    case=case6(catalog);b,r=assemble(case)
    next(row for row in b['manifest']['files'] if row['path']==path)['role']='evidence'
    reseal(b,r)
    with pytest.raises(ValueError):validate_retained_bundle(b,r,case['frozen'])


def test_model3_submission_and_prepared_retry_reauthorize_without_dispatch(tmp_path,catalog):
    service,store,actor,sid,case,native=submission(tmp_path,catalog)
    body=dict(command_id=uid(),configuration_revision_id=case['frozen']['configuration']['configuration_revision_id'])
    accepted=service.submit(actor,sid,body);rid=accepted['run_id'];service.dispatch(rid,prepare_only=True)
    with store.connection(write=True) as db:db.execute('DELETE FROM memberships WHERE study_id=? AND actor_id=?',(sid,actor))
    with pytest.raises(DomainError):service.submit(actor,sid,body)
    service.dispatch(rid);assert native.launches==0
    with store.connection() as db:
        assert db.execute('SELECT count(*) FROM run_associations').fetchone()[0]==1
        assert store._receipt(db,sid,'run',body['command_id'])['state']=='preparation_failed'


def relocate_catalog(case,duplicate=False):
    files=case['files'];p=case['prepared'];path='provenance/backend-independent-table.dat'
    files[path]=files[CATALOG_PATH]
    descriptor=next(r for r in p['files'] if r['path']==CATALOG_PATH)
    provenance=json.loads(files[p['generator_identity']['provenance_path']])
    row=next(r for r in provenance['patched_files'] if r['path']==CATALOG_PATH)
    if duplicate:
        p['files'].append(dict(descriptor,path=path,file_id=uid()))
        provenance['patched_files'].append(dict(row,path=path))
    else:
        files.pop(CATALOG_PATH);descriptor['path']=path;row['path']=path
    p['files'].sort(key=lambda r:r['path'])
    provenance['patched_files'].sort(key=lambda r:r['path'])
    files[p['generator_identity']['provenance_path']]=canonical(provenance)
    repin(case)


def test_declared_trusted_catalog_is_backend_neutral_not_a_native_filename(catalog):
    case=case6(catalog);relocate_catalog(case)
    before=deepcopy(case);b,r=assemble(case)
    validate_retained_bundle(b,r,case['frozen']);assert case==before
    assert CATALOG_PATH not in b['files']


@pytest.mark.parametrize('change',['duplicate','missing','unproven','provenance_role'])
def test_exactly_one_authenticated_declared_catalog_required(catalog,change):
    case=case6(catalog)
    if change=='duplicate':relocate_catalog(case,duplicate=True)
    elif change=='missing':case['files'][CATALOG_PATH]=b'{}';repin(case)
    else:
        p=case['prepared'];path=p['generator_identity']['provenance_path'];provenance=json.loads(case['files'][path])
        if change=='unproven':provenance['patched_files']=[r for r in provenance['patched_files'] if r['path']!=CATALOG_PATH]
        else:next(r for r in provenance['patched_files'] if r['path']==CATALOG_PATH)['role']='adapter'
        case['files'][path]=canonical(provenance);repin(case)
    with pytest.raises((ValueError,DomainError)):assemble(case)


def explanatory_model(model, declaration='unspecified'):
    """New explanatory identities with reachable exact bindings; no selected promotion."""
    from uuid import UUID
    ids={}
    def fresh(value):
        if isinstance(value,dict):return {k:fresh(v) for k,v in value.items()}
        if isinstance(value,list):return [fresh(v) for v in value]
        if isinstance(value,str):
            try:UUID(value)
            except ValueError:return value
            return ids.setdefault(value,uid())
        return value
    result=fresh(deepcopy(model))
    result.update(schema_version='3',required_capabilities=['flat_explicit_scalar','unit_declarations/1'],assumptions=[])
    for definition in result['definitions']:
        for port in definition['ports']:
            port['units']=dict(kind=declaration,**({'expression':'J/kg'} if declaration=='physical' else {}))
    result['ports']=deepcopy([p for d in result['definitions'] for p in d['ports']])
    signed(result);validate('ModelRevision3',result)
    return result


def mixed_case(catalog,declaration='unspecified'):
    case=case6(catalog,legacy=True);f=case['frozen'];m=f['model_snapshot'];c=f['configuration']
    selected=canonical(m);extra=explanatory_model(m,declaration)
    v=sample(D['ApproachVersion1']);v['study_id']=c['study_id'];link(v,m);link(v,extra)
    closure=build_closure(v,resolution(models=[m,extra]),study_id=c['study_id'])
    f.update(schema_version='5',approach_closure=closure)
    c['approach_binding']=dict(approach_id=v['approach_id'],approach_version_id=v['approach_version_id'],
        approach_digest=v['digest'],closure_digest=closure['digest'],case_id=None)
    repin(case);assert canonical(m)==selected
    return case


def raw_snapshot(case):
    return {key:deepcopy(case['frozen'][key]) for key in ('configuration','model_snapshot','approach_closure')}


@pytest.mark.parametrize('declaration',['physical','unspecified'])
def test_mixed_selected_model2_full_raw_bundle6_preserves_native_bytes(catalog,declaration):
    case=mixed_case(catalog,declaration);before=deepcopy(case)
    validate_frozen_configuration(case['frozen'])
    b,r=assemble(case)
    assert b['manifest']['schema_version']=='6'
    validate_retained_bundle(b,r,case['frozen'])
    validate_retained_bundle(b,r,raw_snapshot(case),raw_snapshot=True)
    assert b['manifest']['required_capabilities']==['flat_explicit_scalar']
    assert case==before
    assert all(b['files'][p]==raw for p,raw in case['files'].items())
    assert json.loads(b['files']['model.json'])==before['frozen']['model_snapshot']
    assert json.loads(b['files']['modeling-configuration.json'])==project(before['frozen']['configuration'])


@pytest.mark.parametrize('declaration',['physical','unspecified'])
def test_mixed_old_full_wrapper_rejected_on_concrete_pairing(catalog,declaration):
    case=mixed_case(catalog,declaration);case['frozen']['schema_version']='4'
    # All semantic pins are valid; only the historical enclosing family is false.
    from hyprn_mvp_app.execution import validate_scientific_snapshot
    validate_scientific_snapshot(raw_snapshot(case))
    with pytest.raises((ValueError,DomainError)):validate_frozen_configuration(case['frozen'])


@pytest.mark.parametrize('linked',[False,True])
def test_raw_legacy_bundle5_needs_no_storage_context_but_full_wrapper_does(catalog,linked):
    case=case6(catalog,linked,legacy=True);b,r=assemble(case)
    validate_retained_bundle(b,r,raw_snapshot(case),raw_snapshot=True)
    incomplete=deepcopy(case['frozen']);del incomplete['study_revision']
    with pytest.raises((ValueError,DomainError)):validate_frozen_configuration(incomplete)


@pytest.mark.parametrize('kind',['mixed','legacy'])
@pytest.mark.parametrize('change',['extra','missing_closure','forged_study_revision'])
def test_raw_snapshot_keys_are_exact(catalog,kind,change):
    case=mixed_case(catalog) if kind=='mixed' else case6(catalog,True,legacy=True)
    b,r=assemble(case);raw=raw_snapshot(case)
    if change=='missing_closure':del raw['approach_closure']
    else:raw['study_revision' if change=='forged_study_revision' else 'extra']='fabricated'
    with pytest.raises((ValueError,DomainError)):validate_retained_bundle(b,r,raw,raw_snapshot=True)


@pytest.mark.parametrize('declaration',['physical','unspecified'])
def test_resealed_mixed_bundle5_refused_at_app_full_and_raw_boundaries(catalog,declaration):
    from hyprn_mvp_app.execution import check_digest,verify_files,validate_bundle_shape
    case=mixed_case(catalog,declaration);b,r=assemble(case)
    b['manifest']['schema_version']='5';reseal(b,r)
    validate_bundle_shape(b['manifest']);check_digest(b['manifest'],'bundle_digest')
    verify_files(b['manifest']['files'],b['files'])
    check_digest(case['frozen']['configuration']);check_digest(case['frozen']['approach_closure'])
    assert b['files']['configuration.json']==canonical(case['frozen']['configuration'])
    assert b['files']['modeling-configuration.json']==canonical(project(case['frozen']['configuration']))
    case['frozen']['schema_version']='4'
    with pytest.raises(ValueError,match='ApproachClosurePreUnits'):
        validate_retained_bundle(b,r,raw_snapshot(case),raw_snapshot=True)
    with pytest.raises(ValueError):validate_retained_bundle(b,r,case['frozen'])


@pytest.mark.parametrize('linked',[False,True])
def test_new_bundle6_refuses_ordinary_legacy_envelope_upgrade(catalog,linked):
    case=case6(catalog,linked,legacy=True);b,r=assemble(case)
    b['manifest']['schema_version']='6';reseal(b,r)
    with pytest.raises(ValueError):validate_retained_bundle(b,r,raw_snapshot(case),raw_snapshot=True)
    case['frozen']['schema_version']='5'
    with pytest.raises(ValueError):validate_frozen_configuration(case['frozen'])


@pytest.mark.parametrize('version',['1','2','3'])
def test_legacy_raw_keys_and_real_storage_wrapper_are_not_interchangeable(catalog,version):
    case=fixture();f=case['frozen'];c=f['configuration']
    if version!='1':
        c.update(schema_version=version,context_source=dict(kind='current_study',expected_study_revision='fixture:1'),derivation=None)
        for item in c['inputs']:item['result_binding']=None
        if version=='3':c.update(assumptions=[],general_context_evidence_version_ids=[]);c['required_capabilities'].append('configuration_assumptions/1')
        repin(case)
    b=assemble_bundle(uid(),case['prepared'],case['files'],f,runtime_fixture(),None if version=='1' else deps())
    r=dict(run_id=b['manifest']['run_id'],scope=c['study_id'],command_id=uid(),payload_digest='a'*64,bundle_digest=b['manifest']['bundle_digest'])
    raw={k:deepcopy(f[k]) for k in ('model_snapshot','configuration')}
    validate_retained_bundle(b,r,raw,raw_snapshot=True)
    with pytest.raises(ValueError):validate_frozen_configuration(raw)
    for key in ('study_revision','approach_closure','schema_version'):
        with pytest.raises(ValueError):validate_retained_bundle(b,r,dict(raw,**{key:None}),raw_snapshot=True)
    with pytest.raises(ValueError):validate_retained_bundle(b,r,dict(raw,model_snapshot={}),raw_snapshot=True)


def case8(catalog, model_version='4', approach_version='2', legacy=False, mixed=False):
    """Descriptive edits of captured producer data, with no candidate execution."""
    case=case6(catalog,legacy=legacy);f=case['frozen'];m=f['model_snapshot'];c=f['configuration']
    if model_version=='4':
        m['schema_version']='4';m['required_capabilities'].append('quantity_definitions/1')
        for d in m['definitions']:
            d['quantity_definitions']=[dict(port_id=p['port_id'],statement='Recorded quantity; never an instruction') for p in d['ports']]
        if mixed:
            for p in m['definitions'][0]['ports']:p['units']=''
            # Repeated port identities are valid across exact definition versions.
            old=deepcopy(m['definitions'][0]);old['definition_version_id']=uid()
            for p in old['ports']:p.update(definition_version_id=old['definition_version_id'],units={'kind':'unspecified'})
            m['definitions'].append(old)
        m['ports']=deepcopy([p for d in m['definitions'] for p in d['ports']])
    c['required_capabilities']=[*m['required_capabilities'],'configuration_assumptions/1']
    case['prepared']['required_capabilities']=list(m['required_capabilities'])
    f.update(schema_version='7',approach_closure=None);repin(case)
    if approach_version:
        v=sample(D['ApproachVersion1']);v['study_id']=c['study_id'];link(v,m)
        if approach_version=='2':
            v['schema_version']='2';v['content'].update(schema_version='2',original_question=None,elaboration=None,
                limit_items=[dict(limit_id=uid(),statement='A bounded descriptive limit',evidence_links=[])])
            signed(v)
        closure=build_closure(v,resolution(models=[m]),study_id=c['study_id'])
        f['approach_closure']=closure
        c['approach_binding']=dict(approach_id=v['approach_id'],approach_version_id=v['approach_version_id'],
            approach_digest=v['digest'],closure_digest=closure['digest'],case_id=None)
        repin(case)
    return case


@pytest.mark.parametrize('version,approach,legacy,mixed',[
    ('4',None,False,False),('4','1',True,False),('4','2',False,True),
    ('3','2',False,False),('2','2',True,False)])
def test_polish_exact_frozen7_bundle8(catalog,version,approach,legacy,mixed):
    case=case8(catalog,version,approach,legacy,mixed);before=deepcopy(case)
    b,r=assemble(case)
    assert b['manifest']['schema_version']=='8'
    assert b['manifest']['model_schema_version']==version
    validate_retained_bundle(b,r,case['frozen'])
    raw={k:v for k,v in case['frozen'].items() if k in ('model_snapshot','configuration','approach_closure')}
    validate_retained_bundle(b,r,raw,raw_snapshot=True)
    assert case==before
    assert b['files']['modeling-configuration.json']==canonical(project(case['frozen']['configuration']))
    assert json.loads(b['files']['modeling-configuration.json'])['schema_version']=='3'
    assert {p:v for p,v in b['files'].items() if p.startswith(('generated/','sources/'))}=={p:v for p,v in case['files'].items() if p.startswith(('generated/','sources/'))}


@pytest.mark.parametrize('change',['missing_quantities','duplicate','foreign','blank','extra','mixed_units','unspecified','frozen5'])
def test_polish_preparation_rejects_invalid_descriptions_and_units(catalog,change):
    case=case8(catalog,approach_version=None);m=case['frozen']['model_snapshot'];d=m['definitions'][0]
    if change=='missing_quantities':del d['quantity_definitions']
    elif change=='duplicate':d['quantity_definitions'].append(dict(d['quantity_definitions'][0],statement='Different duplicate'))
    elif change=='foreign':d['quantity_definitions'][0]['port_id']=uid()
    elif change=='blank':d['quantity_definitions'][0]['statement']='  '
    elif change=='extra':d['quantity_definitions'][0]['execute']='ignored?'
    elif change=='mixed_units':d['ports'][0]['units']=''
    elif change=='unspecified':d['ports'][0]['units']={'kind':'unspecified'}
    else:case['frozen']['schema_version']='5'
    m['ports']=deepcopy([p for d in m['definitions'] for p in d['ports']])
    if change!='missing_quantities':repin(case)
    with pytest.raises((ValueError,DomainError)):assemble(case)


@pytest.mark.parametrize('missing',[None,'bundle','model','quantity','unit','program'])
def test_polish_preparation_requires_actual_backend_support(catalog,missing):
    case=case8(catalog,approach_version=None)
    caps=dict(schema_versions=['1','2','3','4'],execution_versions=dict(bundle_versions=['2','3','4','5','6','8'],
        artifact_versions=['2'],program_protocols=['hyprn_mvp.openmdao.program/1']),capabilities=[
        dict(id=name,version='1',supported=True) for name in ('flat_explicit_scalar','unit_declarations','quantity_definitions')])
    if missing=='bundle':caps['execution_versions']['bundle_versions'].remove('8')
    elif missing=='model':caps['schema_versions'].remove('4')
    elif missing in ('quantity','unit'):caps['capabilities'][-1 if missing=='quantity' else 1]['supported']=False
    elif missing=='program':caps['execution_versions']['program_protocols']=[]
    class Private:
        posts=0
        def call(self,actor,sid,method,path,*args,**kwargs):
            if path=='/capabilities':return 200,dict(data=caps)
            if method=='POST':
                self.posts+=1;return 200,dict(data=case['prepared'])
            descriptor=next(f for f in case['prepared']['files'] if f['file_id']==path.rsplit('/',1)[-1])
            return 200,dict(data=dict(bytes=base64.b64encode(case['files'][descriptor['path']]).decode(),
                sha256=descriptor['sha256'],media_type=descriptor['media_type']))
    remote=Private();prepare=StaticPreparation(remote)
    if missing:
        with pytest.raises(ValueError):prepare(uid(),case['frozen']['configuration']['study_id'],uid(),case['frozen'])
        assert remote.posts==0
    else:
        p,files=prepare(uid(),case['frozen']['configuration']['study_id'],uid(),case['frozen'])
        assert p==case['prepared'] and files==case['files'] and remote.posts==1


def mixed_polish_case(catalog):
    case=mixed_case(catalog);f=case['frozen'];c=f['configuration'];closure=f['approach_closure']
    extra=next(m for m in closure['models'] if m['schema_version']=='3')
    extra['schema_version']='4';extra['required_capabilities'].append('quantity_definitions/1')
    for d in extra['definitions']:d['quantity_definitions']=[]
    signed(extra);v=closure['approach_versions'][0]
    closure=build_closure(v,resolution(models=closure['models']),study_id=c['study_id'])
    f.update(schema_version='7',approach_closure=closure)
    c['approach_binding']['closure_digest']=closure['digest'];repin(case)
    return case


def test_polish_model2_root_with_unresolved_model4_ancestor(catalog):
    case=mixed_polish_case(catalog);b,r=assemble(case)
    assert b['manifest']['model_schema_version']=='2' and b['manifest']['schema_version']=='8'
    validate_retained_bundle(b,r,case['frozen'])
    assert json.loads(b['files']['modeling-configuration.json'])['required_capabilities']==['flat_explicit_scalar']


@pytest.mark.parametrize('layout', ['2', '3', '4', '5', '6', '8'])
def test_current_result_protocol_uses_explicit_input_layout_and_strict_pairing(
    catalog, layout, tmp_path
):
    from hyprn_mvp_app.execution_bundle import bundle_layout, result_history_version
    if layout in ('5', '6'):
        case = case6(catalog, linked=True, legacy=layout == '5')
    elif layout == '8':
        case = case8(catalog)
    else:
        case = fixture()
        config = case['frozen']['configuration']
        if layout != '2':
            config.update(
                schema_version='2' if layout == '3' else '3',
                context_source=dict(kind='current_study', expected_study_revision='fixture:1'),
                derivation=None,
            )
            for item in config['inputs']:
                item['result_binding'] = None
            if layout == '4':
                config.update(assumptions=[], general_context_evidence_version_ids=[])
                config['required_capabilities'].append('configuration_assumptions/1')
    case['prepared'].update(schema_version='3', result_protocol_version='2')
    repin(case)
    bundle, request = assemble(case)
    manifest = bundle['manifest']
    assert manifest['schema_version'] == '10'
    assert manifest['input_schema_version'] == bundle_layout(manifest) == layout
    assert manifest['result_protocol_version'] == '2'
    assert result_history_version('10', '2') == '7'
    validate_retained_bundle(bundle, request, case['frozen'])
    directory = tmp_path / 'current-inputs'
    directory.mkdir()
    for name, raw in {**bundle['files'], 'manifest.json': canonical(manifest)}.items():
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    # Worker admission stays in its own process; application imports remain inert.
    code = '''
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from hyprn_mvp_integration.worker import read_inputs
root = Path(sys.argv[2])
observed = read_inputs(root, sys.argv[3], sys.argv[4])
expected = tuple(json.loads((root / name).read_bytes()) for name in
                 ('manifest.json', 'model.json', 'configuration.json'))
assert observed == expected
print('current worker inputs accepted')
'''
    checked = subprocess.run(
        [sys.executable, '-B', '-c', code, str(REPO / 'integration/src'), str(directory),
         manifest['bundle_digest'], raw_hash(canonical(manifest))],
        capture_output=True, text=True,
    )
    assert checked.returncode == 0, checked.stderr
    assert checked.stdout.strip() == 'current worker inputs accepted'
    for field, value in [('result_protocol_version', '1'), ('input_schema_version', '1')]:
        altered, altered_request = deepcopy((bundle, request))
        altered['manifest'][field] = value
        reseal(altered, altered_request)
        with pytest.raises((ValueError, DomainError)):
            validate_retained_bundle(altered, altered_request, case['frozen'])
    with pytest.raises(ValueError):
        result_history_version('10', '1')
    with pytest.raises(ValueError):
        result_history_version(layout, '2')


def test_current_prior_run_closure_freezes_and_reexecutes_with_exact_protocol(catalog):
    case = case6(catalog)
    frozen = case['frozen']
    model, config = frozen['model_snapshot'], frozen['configuration']
    prior = deepcopy(config)
    prior.update(configuration_id=uid(), configuration_revision_id=uid())
    signed(prior)
    context = sample(D['ApproachRunContext2'])
    context.update(
        study_id=prior['study_id'],
        configuration_revision_id=prior['configuration_revision_id'],
        configuration_digest=prior['digest'],
        model_revision_id=model['model_revision_id'],
        model_digest=model['digest'],
        context=prior['context_snapshot'],
        assessment=None,
        errors=[],
    )
    context['request'].update(run_id=context['run_id'], scope=prior['study_id'])
    result = sample(D['RetainedResults2'])
    result.update(
        run_id=context['run_id'],
        bundle_digest=context['request']['bundle_digest'],
        execution=dict(state='failed', exit_code=1, message='Prior recorded failure'),
        outputs=[],
        criteria=[],
    )
    context['results'] = result
    signed(context)
    version = sample(D['ApproachVersion1'])
    version['study_id'] = prior['study_id']
    link(version, model)
    version['content']['basis_refs'] = [dict(kind='run', run_id=context['run_id'],
        reason='Prior recorded calculation', relation='context')]
    signed(version)
    closure = build_closure(version, resolution(models=[model], configurations=[prior],
        run_contexts=[context]), study_id=prior['study_id'])
    assert closure['schema_version'] == '4'
    assert closure['run_contexts'] == [context]
    frozen.update(schema_version='8', approach_closure=closure)
    config['approach_binding'] = dict(approach_id=version['approach_id'],
        approach_version_id=version['approach_version_id'], approach_digest=version['digest'],
        closure_digest=closure['digest'], case_id=None)
    case['prepared'].update(schema_version='3', result_protocol_version='2')
    repin(case)
    bundle, request = assemble(case)
    assert bundle['manifest']['input_schema_version'] == '9'
    validate_retained_bundle(bundle, request, frozen)
    assert json.loads(bundle['files']['approach/closure.json']) == closure


class PreparationFiles:
    """Exact retained bytes behind a counted, independently authorized preparation."""
    def __init__(self, case):
        self.case = case
        self.downloads = 0
        self.preparations = 0
        self.refuse = False

    def call(self, actor, sid, method, path, *args, **kwargs):
        if self.refuse:
            raise DomainError('resource_not_found', 404)
        if method == 'POST':
            self.preparations += 1
            return 200, dict(data=deepcopy(self.case['prepared']))
        self.downloads += 1
        item = next(f for f in self.case['prepared']['files'] if path.endswith(f['file_id']))
        return 200, dict(data=dict(
            bytes=base64.b64encode(self.case['files'][item['path']]).decode(),
            sha256=item['sha256'], media_type=item['media_type'],
        ))


def test_repeated_preparation_reuses_only_verified_bytes():
    case = fixture()
    remote = PreparationFiles(case)
    prepare = StaticPreparation(remote)
    actor, sid = uid(), case['frozen']['configuration']['study_id']
    first = prepare(actor, sid, uid(), case['frozen'])
    count = remote.downloads
    # New preparations retain fresh authority and bindings, even for identical content.
    second = prepare(actor, sid, uid(), case['frozen'])
    assert first == second
    assert remote.preparations == 2
    assert remote.downloads == count
    remote.refuse = True
    with pytest.raises(DomainError):
        prepare(actor, sid, uid(), case['frozen'])


def test_preparation_cache_is_scoped_and_revalidates_manifest():
    case = fixture()
    remote = PreparationFiles(case)
    prepare = StaticPreparation(remote)
    actor, sid = uid(), case['frozen']['configuration']['study_id']
    prepare(actor, sid, uid(), case['frozen'])
    count = remote.downloads
    prepare(uid(), sid, uid(), case['frozen'])
    assert remote.downloads == count * 2
    remote.case['prepared']['configuration_digest'] = '0' * 64
    with pytest.raises(ValueError):
        prepare(actor, sid, uid(), case['frozen'])


def test_failed_preparation_does_not_populate_byte_cache():
    case = fixture()
    remote = PreparationFiles(case)
    prepare = StaticPreparation(remote)
    actor, sid = uid(), case['frozen']['configuration']['study_id']
    good = deepcopy(case['prepared'])
    case['prepared']['configuration_digest'] = '0' * 64
    with pytest.raises(ValueError):
        prepare(actor, sid, uid(), case['frozen'])
    count = remote.downloads
    case['prepared'] = good
    prepare(actor, sid, uid(), case['frozen'])
    assert remote.downloads == count * 2


def test_preparation_cache_eviction_only_causes_redownload(monkeypatch):
    import hyprn_mvp_app.execution as execution

    case = fixture()
    remote = PreparationFiles(case)
    prepare = StaticPreparation(remote)
    actor, sid = uid(), case['frozen']['configuration']['study_id']
    monkeypatch.setattr(execution, 'MAX_FILES', 3)
    first = prepare(actor, sid, uid(), case['frozen'])
    assert len(prepare._files) <= 3
    count = remote.downloads
    assert prepare(actor, sid, uid(), case['frozen']) == first
    assert remote.downloads > count
    assert len(prepare._files) <= 3
    assert prepare._file_bytes == sum(map(len, prepare._files.values()))


def test_changed_prepared_file_cannot_hit_old_hash_cache():
    case = fixture()
    remote = PreparationFiles(case)
    prepare = StaticPreparation(remote)
    actor, sid = uid(), case['frozen']['configuration']['study_id']
    prepare(actor, sid, uid(), case['frozen'])
    count = remote.downloads
    item = case['prepared']['files'][0]
    item['sha256'] = '0' * 64
    with pytest.raises(ValueError):
        prepare(actor, sid, uid(), case['frozen'])
    assert remote.downloads > count
