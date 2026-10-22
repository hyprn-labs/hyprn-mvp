"""Independent worker admission; synthetic captured bytes never load candidate code."""
from copy import deepcopy
import builtins
import hashlib
import json
import sys

import pytest
from hyprn_mvp_app.store import canonical, digest, uid
from hyprn_mvp_integration import launcher, worker, results
from execution_fixtures import fixture, runtime_fixture
from hyprn_mvp_app.execution import assemble_bundle
from test_unit_execution_admission import (catalog, case6, assemble, repin, reseal,
    relocate_catalog, CATALOG_PATH, physical, linked_result, deps)
from test_unit_execution import forged


def read(bundle, request, tmp_path, monkeypatch, reject=False):
    directory = tmp_path/'bundle'
    launcher.write_bundle(bundle, directory)
    monkeypatch.setattr(worker, 'load_program', lambda *a: pytest.fail('Candidate load reached'))
    original = builtins.__import__
    def independent(name, *args, **kwargs):
        if name.startswith(('hyprn_mvp_app', 'openmdao')):
            pytest.fail('Worker admission imported application/numerical code: '+name)
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', independent)
    pins = request['bundle_digest'], hashlib.sha256(canonical(bundle['manifest'])).hexdigest()
    if reject:
        with pytest.raises((ValueError, KeyError)):
            worker.execute(directory, *pins)
    else:
        observed = worker.read_inputs(directory, *pins)
        assert observed == (bundle['manifest'], json.loads(bundle['files']['model.json']),
                            json.loads(bundle['files']['configuration.json']))


@pytest.mark.parametrize('linked', [False, True])
def test_units_worker_exact_new_branch(catalog, linked, tmp_path, monkeypatch):
    b,r = assemble(case6(catalog, linked))
    read(b,r,tmp_path,monkeypatch)


@pytest.mark.parametrize('retained', ['unspecified','legacy','active_legacy','renamed'])
def test_units_worker_retained_versions(catalog, retained, tmp_path, monkeypatch):
    case=case6(catalog);m=case['frozen']['model_snapshot']
    if retained=='renamed':relocate_catalog(case)
    elif retained=='active_legacy':
        for d in m['definitions']:
            for p in d['ports']:p['units']=''
    else:
        old=deepcopy(m['definitions'][0]);old['definition_version_id']=uid()
        for p in old['ports']:p.update(definition_version_id=old['definition_version_id'],units='' if retained=='legacy' else {'kind':'unspecified'})
        m['definitions'].insert(0,old)
    m['ports']=deepcopy([p for d in m['definitions'] for p in d['ports']]);repin(case)
    before=deepcopy(case);b,r=assemble(case)
    read(b,r,tmp_path,monkeypatch);assert case==before


@pytest.mark.parametrize('value', [0,-2,2])
def test_units_worker_compound_conversion_proof(catalog, value, tmp_path, monkeypatch):
    case=case6(catalog);physical(case);dependencies=linked_result(case,value)
    b,r=assemble(case,dependencies);read(b,r,tmp_path,monkeypatch)


@pytest.mark.parametrize('change', [
    'input','output','connected','malformed_unused','unknown','call','newline','extra',
    'aggregate','mixed_definition','old_active','second_old','inactive_legacy_malformed','inactive_mixed','inactive_extra','residual',
    'binding_units','binding_target','catalog_digest','catalog_factor','catalog_engine',
    'catalog_missing','catalog_duplicate','catalog_role','catalog_unproven','catalog_oversize',
    'capability','model2','config3','old_bundle','provenance_digest'])
def test_units_worker_rejects_resealed_before_load(catalog, change, tmp_path, monkeypatch):
    case=case6(catalog);b,r=assemble(case);m=case['frozen']['model_snapshot']
    if change in ('input','output','connected','unknown','call','newline','extra'):
        ref=(case['frozen']['configuration']['inputs'][0]['target'] if change=='input'
             else m['connections'][0]['target_ref'] if change=='connected' else m['connections'][0]['source_ref'])
        i=next(i for i in m['instances'] if i['instance_id']==ref['instance_id'])
        d=next(d for d in m['definitions'] if d['definition_version_id']==i['definition_version_id'])
        p=next(p for p in d['ports'] if p['port_id']==ref['port_id'])
        p['units']=({'kind':'physical','expression':{'unknown':'USD','call':'os.system("x")','newline':'m\ns'}[change]}
                    if change in ('unknown','call','newline') else {'kind':'dimensionless','extra':1} if change=='extra' else {'kind':'unspecified'})
    elif change in ('malformed_unused','old_active','second_old','inactive_legacy_malformed','inactive_mixed','inactive_extra'):
        old=deepcopy(m['definitions'][0]);old['definition_version_id']=uid()
        for p in old['ports']:p.update(definition_version_id=old['definition_version_id'],units={'kind':'unspecified'})
        m['definitions'].append(old)
        if change=='malformed_unused':old['ports'][0]['units']['expression']=''
        elif change=='inactive_legacy_malformed':
            for p in old['ports']:p['units']=''
            old['ports'][0]['units']=7
        elif change=='inactive_mixed':old['ports'][0]['units']=''
        elif change=='inactive_extra':old['ports'][0]['unexpected']=True
        elif change=='old_active':m['instances'][0]['definition_version_id']=old['definition_version_id']
        else:m['instances'].append(dict(instance_id=uid(),definition_version_id=old['definition_version_id'],name='Unresolved'))
    elif change=='residual':
        row=deepcopy(m['definitions'][0]['ports'][0])
        row.update(port_id=uid(),direction='residual',units={'kind':'unspecified'})
        m['definitions'][0]['ports'].append(row);m['definitions'][0]['residual_port_ids'].append(row['port_id'])
    elif change=='mixed_definition':m['definitions'][0]['ports'][0]['units']=''
    elif change.startswith('binding'):
        path=case['prepared']['entrypoint']['bindings_path'];v=json.loads(case['files'][path])
        if change=='binding_units':v['outputs'][0]['units']='m'
        else:v['outputs'][0]['target']['instance_id']=uid()
        case['files'][path]=canonical(v)
    elif change.startswith('catalog'):
        if change=='catalog_duplicate':relocate_catalog(case,duplicate=True)
        elif change in ('catalog_role','catalog_unproven'):
            path=case['prepared']['generator_identity']['provenance_path'];v=json.loads(case['files'][path])
            if change=='catalog_role':next(x for x in v['patched_files'] if x['path']==CATALOG_PATH)['role']='adapter'
            else:v['patched_files']=[x for x in v['patched_files'] if x['path']!=CATALOG_PATH]
            case['files'][path]=canonical(v)
        else:
            v=deepcopy(catalog)
            if change=='catalog_digest':v['catalog_digest']='0'*64
            elif change=='catalog_factor':v['linear_pairs'][0][2]=2
            elif change=='catalog_engine':v['version']='0.0.0'
            elif change=='catalog_missing':v={}
            case['files'][CATALOG_PATH]=json.dumps(v).encode()+(b' '*17000 if change=='catalog_oversize' else b'')
    elif change=='capability':m['required_capabilities']=['flat_explicit_scalar']
    elif change=='model2':m['schema_version']='2'
    m['ports']=deepcopy([p for d in m['definitions'] for p in d['ports']])
    if change=='aggregate':m['ports'][0]['units']={'kind':'physical','expression':'m'}
    forged(case,b,r)
    if change=='catalog_duplicate':
        b['manifest']['files'].append(deepcopy(next(x for x in case['prepared']['files'] if x['path']=='provenance/backend-independent-table.dat')))
        b['manifest']['files'].sort(key=lambda x:x['path'])
    if change=='config3':
        from hyprn_mvp_app.store import digest
        config=json.loads(b['files']['configuration.json']);config['schema_version']='3'
        config['digest']=digest({k:v for k,v in config.items() if k!='digest'})
        b['files']['configuration.json']=canonical(config);b['manifest']['configuration_digest']=config['digest']
    if change=='old_bundle':b['manifest']['schema_version']='5'
    if change=='provenance_digest':
        b['manifest']['generator']['adapter_digest']='0'*64
        p=json.loads(b['files']['preparation.json']);p['generator_identity']['adapter_digest']='0'*64
        # Rehash the prepared envelope, then its outer immutable pins.
        from hyprn_mvp_app.store import digest
        p['prepared_digest']=digest({k:v for k,v in p.items() if k!='prepared_digest'})
        b['files']['preparation.json']=canonical(p);b['manifest']['prepared_digest']=p['prepared_digest']
    reseal(b,r);read(b,r,tmp_path,monkeypatch,True)


@pytest.mark.parametrize('change',['connection','input','criterion','affine','overflow','proof_digest','proof_factor','proof_destination'])
def test_units_worker_invalid_conversions_before_load(catalog,change,tmp_path,monkeypatch):
    case=case6(catalog);physical(case);dependencies=linked_result(case,2)
    b,r=assemble(case,dependencies);m=case['frozen']['model_snapshot'];c=case['frozen']['configuration']
    if change.startswith('proof'):
        proof=c['inputs'][0]['result_binding']['conversion']
        if change=='proof_digest':proof['catalog_digest']='0'*64
        elif change=='proof_factor':proof.update(factor=2,destination_value=4)
        else:proof['destination_units']='m'
        dependencies['mappings'][0]['conversion']=deepcopy(proof)
    elif change=='criterion':c['criteria'][0]['units']='m'
    elif change in ('input','affine','overflow'):
        c['inputs'][0]['result_binding']=None;dependencies=deps();c['required_capabilities'].remove('result_linked_inputs/1')
        if change=='overflow':c['inputs'][0]['value']=1e308
        else:c['inputs'][0]['units']='degC' if change=='affine' else 'm'
    else:
        ref=m['connections'][0]['target_ref'];i=next(i for i in m['instances'] if i['instance_id']==ref['instance_id'])
        d=next(d for d in m['definitions'] if d['definition_version_id']==i['definition_version_id'])
        next(p for p in d['ports'] if p['port_id']==ref['port_id'])['units']={'kind':'physical','expression':'m'}
    m['ports']=deepcopy([p for d in m['definitions'] for p in d['ports']])
    b['files']['result-dependencies.json']=canonical(dependencies)
    b['manifest']['result_dependencies'].update(size=len(b['files']['result-dependencies.json']),sha256=hashlib.sha256(b['files']['result-dependencies.json']).hexdigest())
    forged(case,b,r);read(b,r,tmp_path,monkeypatch,True)


@pytest.mark.parametrize('version',['1','2','3','4'])
def test_units_worker_legacy_bundle_pairings(catalog,version,tmp_path,monkeypatch):
    case=case6(catalog,legacy=True) if version=='4' else fixture()
    c=case['frozen']['configuration']
    if version in ('2','3'):
        c.update(schema_version=version,context_source=dict(kind='current_study',expected_study_revision='fixture:1'),derivation=None)
        for i in c['inputs']:i['result_binding']=None
        if version=='3':
            c.update(assumptions=[],general_context_evidence_version_ids=[])
            c['required_capabilities'].append('configuration_assumptions/1')
        repin(case)
    b=assemble_bundle(uid(),case['prepared'],case['files'],case['frozen'],runtime_fixture(),None if version=='1' else deps())
    read(b,dict(bundle_digest=b['manifest']['bundle_digest']),tmp_path,monkeypatch)


def record(model,request,units):
    definitions={d['definition_version_id']:d for d in model['definitions']}
    outputs=[dict(target=dict(instance_id=i['instance_id'],port_id=p['port_id']),value=-2,units=units,
                  availability='available',reason=None,producer_completed=True,assigned=True)
             for i in model['instances'] for p in definitions[i['definition_version_id']]['ports'] if p['direction']=='output']
    return dict(schema_version='1',**request,execution=dict(state='finished',exit_code=0,message='completed'),
        convergence=dict(state='not_applicable',diagnostics_ref=None),optimization=dict(termination='not_applicable',feasibility='not_applicable'),
        completeness=dict(expected=len(outputs),available=len(outputs),failed=0,unavailable=0),outputs=outputs,
        criteria=[],applicability=dict(state='unassessed',evidence_refs=[]),artifacts=[])


@pytest.mark.parametrize('unit', ['', *sorted(worker.PHYSICAL_UNITS)])
def test_units_worker_result_exact_resolved_units(catalog,unit):
    case=case6(catalog);m=case['frozen']['model_snapshot']
    for d in m['definitions']:
        for p in d['ports']:p['units']={'kind':'physical','expression':unit} if unit else {'kind':'dimensionless'}
    m['ports']=deepcopy([p for d in m['definitions'] for p in d['ports']]);repin(case)
    r=dict(run_id=uid(),bundle_digest='a'*64);v=record(m,r,unit);before=deepcopy(m)
    assert results.read_stored_result(v,r,m)==v and m==before
    v['outputs'][0]['units']='m' if unit!='m' else ''
    with pytest.raises(ValueError):results.read_stored_result(v,r,m)
    v['outputs'][0]['units']=unit;v['outputs'][0]['target']['instance_id']=uid()
    with pytest.raises(ValueError):results.read_stored_result(v,r,m)


@pytest.mark.parametrize('linked',[False,True])
def test_units_worker_retained_bundle6_result_reader(catalog,linked):
    import io
    b,r=assemble(case6(catalog,linked));before=deepcopy(b)
    class Repository:
        def open(self,path,mode='rb'):
            return io.BytesIO(canonical(b['manifest']) if path=='manifest.json' else b['files'][path])
    assert results.retained_bundle(Repository(),r)==b and b==before


@pytest.mark.parametrize('unit',['m','km','cm','mm','s','min','h','kg','g','N','Pa','kPa','MPa',
    'K','degC','degF','rad','deg','m/s','km/h','J/kg','kJ/kg','MJ/kg','kg/m**3','g/cm**3','m**2','cm**2','mm**2'])
def test_units_worker_closed_physical_spelling(unit):
    declaration={'kind':'physical','expression':unit}
    assert worker.unit_meaning(declaration)==results._result_unit(declaration,'3')==unit


@pytest.mark.parametrize('value',[{'kind':'unspecified'},{'kind':'physical','expression':'USD'},
    {'kind':'dimensionless','expression':''},{'kind':'physical','expression':'m.__class__'},
    {'kind':'physical','expression':None},None,[],'USD'])
def test_units_worker_result_rejects_unresolved_forged_declarations(catalog,value):
    case=case6(catalog);m=case['frozen']['model_snapshot']
    request=dict(run_id=uid(),bundle_digest='a'*64);v=record(m,request,'')
    m['definitions'][0]['ports'][0]['units']=value
    with pytest.raises(ValueError):results.read_stored_result(v,request,m)


@pytest.mark.parametrize('version',['5','6'])
def test_units_worker_old_bundle_cannot_admit_model3_approach(catalog,version):
    case=case6(catalog,True);b,r=assemble(case)
    b['manifest']['schema_version']=version
    if version=='5':
        with pytest.raises(ValueError,match='Approach model/bundle version'):
            worker.verify_approach(b['manifest'],b['files'],case['frozen']['configuration'])
    else:
        worker.verify_approach(b['manifest'],b['files'],case['frozen']['configuration'])


@pytest.mark.parametrize('declaration',['physical','unspecified'])
def test_mixed_worker_selected_legacy_identity(catalog,declaration,tmp_path,monkeypatch):
    from test_unit_execution_admission import mixed_case
    case=mixed_case(catalog,declaration);before=deepcopy(case);b,r=assemble(case)
    assert b['manifest']['schema_version']=='6'
    assert b['manifest']['required_capabilities']==['flat_explicit_scalar']
    assert case['prepared']['model_package_manifest']['schema_version']=='2'
    assert json.loads(b['files']['modeling-configuration.json'])['schema_version']=='3'
    assert digest(json.loads(case['files'][CATALOG_PATH]))!=worker.UNIT_CATALOG_DIGEST
    read(b,r,tmp_path,monkeypatch)
    assert case==before


@pytest.mark.parametrize('declaration',['physical','unspecified'])
def test_mixed_worker_fully_resealed_historical_downgrade(catalog,declaration,tmp_path,monkeypatch):
    from test_unit_execution_admission import mixed_case
    case=mixed_case(catalog,declaration);b,r=assemble(case)
    b['manifest']['schema_version']='5';reseal(b,r)
    read(b,r,tmp_path,monkeypatch,True)


@pytest.mark.parametrize('linked',[False,True])
def test_worker_rejects_new_envelope_without_explanatory_model3(catalog,linked,tmp_path,monkeypatch):
    b,r=assemble(case6(catalog,linked,legacy=True));b['manifest']['schema_version']='6';reseal(b,r)
    read(b,r,tmp_path,monkeypatch,True)


@pytest.mark.parametrize('value',[0,-2,2])
def test_mixed_worker_preserves_pinned_legacy_result_proof(catalog,value,tmp_path,monkeypatch):
    from test_unit_execution_admission import mixed_case
    case=mixed_case(catalog);dependencies=linked_result(case,value)
    c=case['frozen']['configuration'];item=c['inputs'][0];binding=item['result_binding']
    legacy_digest=digest(json.loads(case['files'][CATALOG_PATH]))
    binding['original_units']=item['units']
    binding['conversion'].update(catalog_digest=legacy_digest,source_units=item['units'],
        destination_units=item['units'],factor=1,destination_value=value)
    dependencies['mappings'][0].update(original_units=item['units'],conversion=deepcopy(binding['conversion']))
    repin(case);before=deepcopy(case);b,r=assemble(case,dependencies)
    read(b,r,tmp_path,monkeypatch)
    assert case==before and legacy_digest!=worker.UNIT_CATALOG_DIGEST
    assert json.loads(b['files']['configuration.json'])['inputs'][0]['result_binding']==binding
    assert json.loads(b['files']['result-dependencies.json'])==dependencies


@pytest.mark.parametrize('change',['model_capability','prepared_capability','package_capability',
    'private_capability','binding_units','selected_swap','explanatory_declaration','explanatory_source'])
def test_mixed_worker_resealed_semantic_forgery(catalog,change,tmp_path,monkeypatch):
    from test_unit_execution_admission import mixed_case
    from hyprn_mvp_app.store import digest
    case=mixed_case(catalog);b,r=assemble(case);m=case['frozen']['model_snapshot']
    if change=='model_capability':m['required_capabilities'].append('unit_declarations/1')
    elif change=='prepared_capability':case['prepared']['required_capabilities'].append('unit_declarations/1')
    elif change=='binding_units':
        path=case['prepared']['entrypoint']['bindings_path'];bindings=json.loads(case['files'][path])
        bindings['outputs'][0]['units']='m';case['files'][path]=canonical(bindings)
    elif change=='selected_swap':m['name']='Forged selected model'
    forged(case,b,r)
    closure=json.loads(b['files']['approach/closure.json'])
    if change=='model_capability':
        closure['models']=[deepcopy(m) if x['model_revision_id']==m['model_revision_id'] else x for x in closure['models']]
    if change.startswith('explanatory'):
        extra=next(x for x in closure['models'] if x['schema_version']=='3')
        if change=='explanatory_declaration':
            extra['definitions'][0]['ports'][0]['units']={'kind':'unspecified','expression':''}
            extra['ports']=deepcopy([p for d in extra['definitions'] for p in d['ports']])
        else:extra['source_files'][0]['bytes']='eA=='
        extra['digest']=digest({k:v for k,v in extra.items() if k!='digest'})
    if change=='model_capability' or change.startswith('explanatory'):
        # Model bindings use immutable IDs; rebind the closure and outer pins.
        closure['digest']=digest({k:v for k,v in closure.items() if k!='digest'})
        case['frozen']['configuration']['approach_binding']['closure_digest']=closure['digest']
        forged(case,b,r);b['files']['approach/closure.json']=canonical(closure)
        b['manifest']['approach_closure_digest']=closure['digest']
    if change in ('package_capability','private_capability'):
        if change=='package_capability':
            prepared=json.loads(b['files']['preparation.json']);package=prepared['model_package_manifest']
            package['required_capabilities'].append('unit_declarations/1')
            package['digest']=digest({k:v for k,v in package.items() if k!='digest'})
            prepared['prepared_digest']=digest({k:v for k,v in prepared.items() if k!='prepared_digest'})
            b['files']['preparation.json']=canonical(prepared);b['manifest']['prepared_digest']=prepared['prepared_digest']
        else:
            private=json.loads(b['files']['modeling-configuration.json']);private['required_capabilities'].append('unit_declarations/1')
            private['digest']=digest({k:v for k,v in private.items() if k!='digest'})
            b['files']['modeling-configuration.json']=canonical(private)
    reseal(b,r);read(b,r,tmp_path,monkeypatch,True)


@pytest.mark.parametrize('version,approach,legacy,mixed',[
    ('4',None,False,False),('4','1',True,False),('4','2',False,True),
    ('3','2',False,False),('2','2',True,False)])
def test_polish_worker_exact_bundle8(catalog,version,approach,legacy,mixed,tmp_path,monkeypatch):
    from test_unit_execution_admission import case8
    b,r=assemble(case8(catalog,version,approach,legacy,mixed))
    read(b,r,tmp_path,monkeypatch)


@pytest.mark.parametrize('change',['omit_model_version','wrong_model_version','downgrade','duplicate','foreign','blank','extra','limit_citation'])
def test_polish_worker_rejects_resealed_tamper(catalog,change,tmp_path,monkeypatch):
    from test_unit_execution_admission import case8
    case=case8(catalog);b,r=assemble(case)
    if change=='omit_model_version':del b['manifest']['model_schema_version']
    elif change=='wrong_model_version':b['manifest']['model_schema_version']='2'
    elif change=='downgrade':b['manifest']['schema_version']='6';del b['manifest']['model_schema_version']
    elif change=='limit_citation':
        closure=json.loads(b['files']['approach/closure.json'])
        closure['approach_versions'][0]['content']['limit_items'][0]['evidence_links']=[dict(evidence_version_id=uid(),relation='supports')]
        v=closure['approach_versions'][0];v['digest']=digest({k:v for k,v in v.items() if k!='digest'})
        closure['root_approach_digest']=v['digest'];closure['digest']=digest({k:v for k,v in closure.items() if k!='digest'})
        case['frozen']['configuration']['approach_binding'].update(approach_digest=v['digest'],closure_digest=closure['digest'])
        forged(case,b,r);b['files']['approach/closure.json']=canonical(closure)
        b['manifest'].update(approach_digest=v['digest'],approach_closure_digest=closure['digest'])
    else:
        d=case['frozen']['model_snapshot']['definitions'][0]
        if change=='duplicate':d['quantity_definitions'].append(dict(d['quantity_definitions'][0],statement='Different'))
        elif change=='foreign':d['quantity_definitions'][0]['port_id']=uid()
        elif change=='blank':d['quantity_definitions'][0]['statement']=' '
        else:d['quantity_definitions'][0]['execute']=True
        forged(case,b,r)
    reseal(b,r);read(b,r,tmp_path,monkeypatch,True)


@pytest.mark.parametrize('change',[None,'value','units','duplicate_description','unknown_description','unspecified','partial','unsupported'])
def test_polish_results_exact_mixed_definition_occurrences(catalog,change):
    from test_unit_execution_admission import case8
    case=case8(catalog,approach_version=None,mixed=True);m=case['frozen']['model_snapshot']
    request=dict(run_id=uid(),bundle_digest='a'*64);v=record(m,request,'');before=deepcopy(m)
    if change=='value':v['outputs'][0]['value']=True
    elif change=='units':v['outputs'][0]['units']='m'
    elif change=='duplicate_description':m['definitions'][0]['quantity_definitions'].append(dict(m['definitions'][0]['quantity_definitions'][0],statement='Other'))
    elif change=='unknown_description':m['definitions'][0]['quantity_definitions'][0]['port_id']=uid()
    elif change=='unspecified':
        d=m['definitions'][0]
        for p in d['ports']:p['units']={'kind':'unspecified'}
        m['ports']=deepcopy([p for d in m['definitions'] for p in d['ports']])
    elif change=='unsupported':v['schema_version']='999'
    elif change=='partial':
        v['execution'].update(state='failed',exit_code=1)
        v['outputs'][0].update(value=None,availability='unavailable',reason='component_failed',producer_completed=False,assigned=False)
        v['completeness'].update(available=len(v['outputs'])-1,failed=1,unavailable=1)
    if change in (None,'partial'):
        assert results.read_stored_result(v,request,m)==v and m==before
    else:
        with pytest.raises(ValueError):results.read_stored_result(v,request,m)


@pytest.mark.parametrize('field',['model','prepared','manifest','private'])
def test_polish_worker_quantity_capability_required(catalog,field,tmp_path,monkeypatch):
    from test_unit_execution_admission import case8
    case=case8(catalog,approach_version=None);b,r=assemble(case)
    if field=='model':
        case['frozen']['model_snapshot']['required_capabilities'].remove('quantity_definitions/1');forged(case,b,r)
    elif field=='prepared':
        case['prepared']['required_capabilities'].remove('quantity_definitions/1');forged(case,b,r)
    elif field=='private':
        c=json.loads(b['files']['modeling-configuration.json']);c['required_capabilities'].remove('quantity_definitions/1')
        c['digest']=digest({k:v for k,v in c.items() if k!='digest'});b['files']['modeling-configuration.json']=canonical(c)
    else:b['manifest']['required_capabilities'].remove('quantity_definitions/1')
    reseal(b,r);read(b,r,tmp_path,monkeypatch,True)


def test_polish_worker_model2_root_with_model4_ancestor(catalog,tmp_path,monkeypatch):
    from test_unit_execution_admission import mixed_polish_case
    b,r=assemble(mixed_polish_case(catalog));read(b,r,tmp_path,monkeypatch)


@pytest.mark.parametrize('typed', [False, True])
def test_polish_worker_catalog_policy_follows_exact_target_declaration(
    catalog, typed, tmp_path, monkeypatch
):
    from test_unit_execution_admission import case8

    case = case8(catalog, approach_version=None, mixed=not typed)
    dependencies = linked_result(case, 2)
    c = case['frozen']['configuration']
    item = c['inputs'][0]
    binding = item['result_binding']
    binding['original_units'] = item['units']
    binding['conversion'].update(
        source_units=item['units'],
        destination_units=item['units'],
        factor=1,
        destination_value=2,
        catalog_digest=catalog['catalog_digest'] if typed else digest(catalog),
    )
    dependencies['mappings'][0].update(
        original_units=item['units'], conversion=deepcopy(binding['conversion'])
    )
    repin(case)
    b, r = assemble(case, dependencies)
    read(b, r, tmp_path, monkeypatch)


@pytest.mark.parametrize('field', ['original_question', 'elaboration'])
@pytest.mark.parametrize('text', ['', ' \t\r\n', 'x' * 4096], ids=['empty', 'whitespace', 'maximum'])
def test_polish_worker_optional_question_claim_preserved(catalog, field, text, tmp_path, monkeypatch):
    from test_unit_execution_admission import case8, build_closure, resolution, signed
    case = case8(catalog)
    frozen = case['frozen']
    version = deepcopy(frozen['approach_closure']['approach_versions'][0])
    claim = dict(text=text, attribution=dict(kind='unknown', label=None))
    version['content'][field] = claim
    signed(version)
    closure = build_closure(version, resolution(models=[frozen['model_snapshot']]),
                            study_id=frozen['configuration']['study_id'])
    frozen['approach_closure'] = closure
    frozen['configuration']['approach_binding'].update(
        approach_digest=version['digest'], closure_digest=closure['digest'])
    repin(case)
    bundle, request = assemble(case)
    assert bundle['manifest']['schema_version'] == '8'
    assert json.loads(bundle['files']['approach/closure.json'])['approach_versions'][0]['content'][field] == claim
    read(bundle, request, tmp_path, monkeypatch)


@pytest.mark.parametrize('field', ['original_question', 'elaboration', 'limit'])
@pytest.mark.parametrize('text', ['x' * 4097, None, 7], ids=['oversize', 'null', 'number'])
def test_polish_worker_rejects_resealed_invalid_claim_or_limit(catalog, field, text, tmp_path, monkeypatch):
    _polish_worker_resealed_text(catalog, field, text, tmp_path, monkeypatch)


@pytest.mark.parametrize('field', ['quantity', 'limit'])
@pytest.mark.parametrize('text', ['', ' \t\r\n'], ids=['empty', 'whitespace'])
def test_polish_worker_still_rejects_blank_description(catalog, field, text, tmp_path, monkeypatch):
    _polish_worker_resealed_text(catalog, field, text, tmp_path, monkeypatch)


def _polish_worker_resealed_text(catalog, field, text, tmp_path, monkeypatch):
    from test_unit_execution_admission import case8
    case = case8(catalog)
    bundle, request = assemble(case)
    if field == 'quantity':
        case['frozen']['model_snapshot']['definitions'][0]['quantity_definitions'][0]['statement'] = text
        forged(case, bundle, request)
    else:
        closure = json.loads(bundle['files']['approach/closure.json'])
        version = closure['approach_versions'][0]
        if field == 'limit':
            version['content']['limit_items'][0]['statement'] = text
        else:
            version['content'][field] = dict(text=text, attribution=dict(kind='unknown', label=None))
        version['digest'] = digest({k: v for k, v in version.items() if k != 'digest'})
        closure['root_approach_digest'] = version['digest']
        closure['digest'] = digest({k: v for k, v in closure.items() if k != 'digest'})
        case['frozen']['configuration']['approach_binding'].update(
            approach_digest=version['digest'], closure_digest=closure['digest'])
        forged(case, bundle, request)
        bundle['files']['approach/closure.json'] = canonical(closure)
        bundle['manifest'].update(approach_digest=version['digest'], approach_closure_digest=closure['digest'])
    reseal(bundle, request)
    read(bundle, request, tmp_path, monkeypatch, True)
