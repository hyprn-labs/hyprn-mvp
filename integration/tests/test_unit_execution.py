"""Direct admission on isolated AiiDA; native candidate bytes never execute.

Captured producer files are resealed synthetic Model3 fixtures. Attestation is
explicitly doubled for node-only tests; native arithmetic is proven by the native tests.
"""
from copy import deepcopy
import io
import json
import sys

import scoped_fixture as guard
from checks import PROJECTION_SCOPE, NATIVE_BACKEND
guard.validate_scope(PROJECTION_SCOPE)

import pytest
from aiida import orm
from hyprn_mvp_app.store import canonical, digest, uid
from hyprn_mvp_app.execution import assemble_bundle, raw_hash
from hyprn_mvp_app.scientific_configuration import project_scientific_configuration as project
from hyprn_mvp_integration import launcher
from hyprn_mvp_integration.calculation import ScalarCalculation, NativeExecution
from execution_fixtures import fixture, runtime_fixture
from test_unit_execution_admission import (catalog, case6, assemble, repin, reseal,
    relocate_catalog, CATALOG_PATH, signed, UNIT_CATALOG_DIGEST)
from test_result_dependencies import source


class Admission(NativeExecution):
    def require_attestation(self):
        return None  # Admission-only double, no runtime qualification claim.

    def bundle_runtime(self):
        return runtime_fixture()


def native():
    instance = Admission(backend=NATIVE_BACKEND, root=PROJECTION_SCOPE.root)
    if not orm.QueryBuilder(backend=NATIVE_BACKEND).append(orm.InstalledCode).count():
        wrapper = PROJECTION_SCOPE.root/'launch-worker'
        wrapper.write_text('#!/bin/sh\nexit 97\n'); wrapper.chmod(0o700)
        computer = orm.Computer(label='hyprn-mvp-node-only', hostname='localhost', transport_type='core.local',
            scheduler_type='core.direct', workdir=str(PROJECTION_SCOPE.root/'tmp/work'), backend=NATIVE_BACKEND).store()
        orm.InstalledCode(label='hyprn-mvp-scalar', computer=computer, filepath_executable=str(wrapper),
            default_calc_job_plugin='hyprn_mvp.scalar', backend=NATIVE_BACKEND).store()
    def stop(point):
        if point == 'after_node':
            raise RuntimeError('Node-only boundary stop')
    instance.fault = stop
    return instance


def count():
    return orm.QueryBuilder(backend=NATIVE_BACKEND).append(orm.ProcessNode).count()


def inputs(bundle, request, upstream=None, cache=True):
    folder = orm.FolderData(backend=NATIVE_BACKEND)
    for path, raw in {**bundle['files'], 'manifest.json': canonical(bundle['manifest'])}.items():
        folder.base.repository.put_object_from_filelike(io.BytesIO(raw), path)
    return dict(frozen_bundle=folder, request=orm.Dict(dict=request, backend=NATIVE_BACKEND),
                upstream_results=upstream or {}, metadata=dict(disable_cache=cache))


def forged(case, bundle, request):
    """Rebind hashes without invoking application assembly/admission."""
    repin(case)
    p = case['prepared']; c = case['frozen']['configuration']; m = bundle['manifest']
    bundle['files'].update(case['files'])
    bundle['files'].update({'preparation.json': canonical(p), 'configuration.json': canonical(c),
                            'modeling-configuration.json': canonical(project(c))})
    for key in ('prepared_digest', 'model_digest', 'executable_content_digest', 'required_capabilities'):
        m[key] = p[key]
    m.update(configuration_digest=c['digest'], modeling_configuration_digest=project(c)['digest'],
             generator=deepcopy(p['generator_identity']))
    reseal(bundle, request)


def refuse(bundle, request, tmp_path):
    before = count()
    with pytest.raises(ValueError):
        launcher.verify_execution_bundle(bundle, request, runtime_fixture())
    assert ScalarCalculation.spec().inputs.validate(inputs(bundle, request)) is not None
    with pytest.raises(ValueError):
        native().launch(bundle, request)
    assert count() == before


@pytest.mark.parametrize('linked', [False, True])
def test_exact_new_raw_bundle_and_calcjob_pass_without_wrapper_or_candidate(tmp_path, catalog, linked):
    case = case6(catalog, linked); bundle, request = assemble(case); before = deepcopy(bundle)
    launcher.verify_execution_bundle(bundle, request, runtime_fixture())
    directory = tmp_path/'bundle'; launcher.write_bundle(bundle, directory)
    assert launcher.verify_bundle(directory, bundle['manifest']['runtime'], request['bundle_digest'], runtime_fixture()) == bundle
    assert all(path.stat().st_mode & 0o222 == 0 for path in directory.rglob('*') if path.is_file())
    assert ScalarCalculation.spec().inputs.validate(inputs(bundle, request)) is None
    with pytest.raises(RuntimeError, match='Node-only boundary stop'):
        native().launch(bundle, request)
    assert len(native().matches(request)) == 1
    assert bundle == before
    assert 'hyprn_mvp_integration.worker' not in sys.modules
    assert not any(name.startswith('openmdao') for name in sys.modules)


@pytest.mark.parametrize('retained', ['unspecified', 'legacy', 'active_legacy', 'renamed_catalog'])
def test_exact_retained_versions_and_backend_neutral_catalog(catalog, retained):
    case = case6(catalog); model = case['frozen']['model_snapshot']
    if retained == 'renamed_catalog':
        relocate_catalog(case)
    elif retained == 'active_legacy':
        for definition in model['definitions']:
            for port in definition['ports']:port['units'] = ''
    else:
        old = deepcopy(model['definitions'][0]); old['definition_version_id'] = uid()
        for port in old['ports']:
            port.update(definition_version_id=old['definition_version_id'],
                        units='' if retained == 'legacy' else {'kind':'unspecified'})
        model['definitions'].insert(0, old)
    model['ports'] = deepcopy([p for d in model['definitions'] for p in d['ports']]); repin(case)
    bundle, request = assemble(case); before = deepcopy(bundle)
    launcher.verify_execution_bundle(bundle, request, runtime_fixture())
    assert ScalarCalculation.spec().inputs.validate(inputs(bundle, request)) is None
    assert bundle == before


@pytest.mark.parametrize('change', ['free', 'output', 'connected', 'active_old', 'second_old',
    'malformed_unused', 'unsupported', 'source', 'binding', 'catalog', 'private', 'config3', 'capability'])
def test_forged_scientific_bytes_refused_before_process(catalog, tmp_path, change):
    case = case6(catalog); bundle, request = assemble(case)
    model = case['frozen']['model_snapshot']; config = case['frozen']['configuration']
    if change in ('active_old', 'second_old', 'malformed_unused'):
        old = deepcopy(model['definitions'][0]); old['definition_version_id'] = uid()
        for port in old['ports']:port.update(definition_version_id=old['definition_version_id'], units={'kind':'unspecified'})
        model['definitions'].append(old)
        if change == 'active_old':model['instances'][0]['definition_version_id'] = old['definition_version_id']
        elif change == 'second_old':model['instances'].append(dict(instance_id=uid(), definition_version_id=old['definition_version_id'], name='Still old'))
        else:old['ports'][0]['units']['expression'] = ''
    elif change in ('free', 'output', 'connected', 'unsupported'):
        target = (config['inputs'][0]['target'] if change in ('free','unsupported') else
                  model['connections'][0]['target_ref' if change=='connected' else 'source_ref'])
        instance = next(i for i in model['instances'] if i['instance_id']==target['instance_id'])
        definition = next(d for d in model['definitions'] if d['definition_version_id']==instance['definition_version_id'])
        port = next(p for p in definition['ports'] if p['port_id']==target['port_id'])
        port['units'] = {'kind':'physical','expression':'evil()'} if change=='unsupported' else {'kind':'unspecified'}
    elif change == 'source':model['source_files'][0]['bytes'] = 'eA=='
    elif change == 'binding':
        path = case['prepared']['entrypoint']['bindings_path']; value=json.loads(case['files'][path])
        value['outputs'][0]['units']='m'; case['files'][path]=canonical(value)
    elif change == 'catalog':
        value=json.loads(case['files'][CATALOG_PATH]); value['linear_pairs'][0][2]=2
        case['files'][CATALOG_PATH]=canonical(value)
    elif change == 'config3':config.update(schema_version='3'); del config['approach_binding']
    elif change == 'capability':model['required_capabilities'].remove('unit_declarations/1')
    model['ports']=deepcopy([p for d in model['definitions'] for p in d['ports']])
    forged(case, bundle, request)
    if change == 'private':
        private=json.loads(bundle['files']['modeling-configuration.json']); private['name']='Forged'; signed(private)
        bundle['files']['modeling-configuration.json']=canonical(private); reseal(bundle,request)
    refuse(bundle,request,tmp_path)


@pytest.mark.parametrize('change', ['raw', 'digest', 'scope', 'size', 'role', 'downgrade', 'dependency_raw'])
def test_direct_immutable_identity_refusals(catalog, tmp_path, change):
    bundle, request = assemble(case6(catalog))
    if change=='raw':bundle['files']['model.json']+=b' '
    elif change=='digest':request['bundle_digest']='0'*64
    elif change=='scope':request['scope']=uid()
    elif change=='size':bundle['manifest']['files'][0]['size']+=1
    elif change=='role':
        next(r for r in bundle['manifest']['files'] if r['path']=='model.json')['role']='evidence'; reseal(bundle,request)
    elif change=='downgrade':bundle['manifest']['schema_version']='5'; reseal(bundle,request)
    else:bundle['files']['result-dependencies.json']=b'{}'; reseal(bundle,request)
    refuse(bundle,request,tmp_path)


@pytest.mark.parametrize('change', ['runtime', 'selection', 'expected', 'extra', 'symlink', 'hardlink'])
def test_filesystem_and_runtime_refusals_before_container(catalog,tmp_path,monkeypatch,change):
    bundle,request=assemble(case6(catalog)); directory=tmp_path/'bundle'; launcher.write_bundle(bundle,directory)
    selected=runtime_fixture(); expected=request['bundle_digest']
    if change=='runtime':selected['runtime']['policy_digest']='0'*64
    elif change=='selection':selected['dependencies']=[]
    elif change=='expected':expected='0'*64
    elif change=='extra':(directory/'undeclared').write_bytes(b'x')
    elif change=='symlink':
        path=directory/'model.json'; path.unlink(); path.symlink_to(directory/'configuration.json')
    else:
        import os
        os.link(directory/'model.json',tmp_path/'outside-link')
    monkeypatch.setattr(launcher,'require_attestation',lambda **k:None)
    monkeypatch.setattr(launcher,'selected_runtime',lambda **k:selected['runtime'])
    monkeypatch.setattr(launcher,'bundle_runtime',lambda **k:selected)
    monkeypatch.setattr(launcher.subprocess,'Popen',lambda *a,**k:pytest.fail('Container creation reached'))
    with pytest.raises(ValueError):launcher.isolated(directory,root=PROJECTION_SCOPE.root,expected_digest=expected)


@pytest.mark.parametrize('version',['2','3','4','5'])
def test_legacy_exact_admission_preserved(catalog,version):
    if version=='5':case=case6(catalog,legacy=True)
    else:
        case=fixture(); c=case['frozen']['configuration']
        if version!='2':
            c.update(schema_version=str(int(version)-1),context_source=dict(kind='current_study',expected_study_revision='fixture:1'),derivation=None)
            for item in c['inputs']:item['result_binding']=None
            if version=='4':c.update(assumptions=[],general_context_evidence_version_ids=[]); c['required_capabilities'].append('configuration_assumptions/1')
            repin(case)
    if version=='2':
        bundle=assemble_bundle(uid(),case['prepared'],case['files'],case['frozen'],runtime_fixture())
        request=dict(run_id=bundle['manifest']['run_id'],scope=case['frozen']['configuration']['study_id'],
            command_id=uid(),payload_digest='a'*64,bundle_digest=bundle['manifest']['bundle_digest'])
    else:bundle,request=assemble(case)
    before=deepcopy(bundle)
    assert bundle['manifest']['schema_version']==version
    launcher.verify_execution_bundle(bundle,request,runtime_fixture())
    assert ScalarCalculation.spec().inputs.validate(inputs(bundle,request)) is None
    assert bundle==before


def linked(case, source):
    config=case['frozen']['configuration']; output=source['approved']['outputs'][0]
    config['study_id']=source['request']['scope']; config['required_capabilities'].append('result_linked_inputs/1')
    pin={k:source['approved'][k] for k in ('source_run_id','request','association','results_digest')}
    pin.update(result_uuid=source['results'].uuid,label='r'+source['results'].uuid.replace('-',''))
    conversion=dict(policy='openmdao-linear-catalog-1',catalog_digest=UNIT_CATALOG_DIGEST,
        source_units=output['units'],destination_units='',factor=1,destination_value=output['value'])
    binding=dict(source_run_id=pin['source_run_id'],source_output=output['target'],results_digest=pin['results_digest'],
        source_configuration_digest=source['bundle']['manifest']['configuration_digest'],original_value=output['value'],
        original_units=output['units'],conversion=conversion,labels=dict(run_name='Retained',model_name=None,
        model_revision_id=config['model_revision_id'],instance_name='Component',output_name='Output'))
    item=config['inputs'][0]; item.update(value=output['value'],units=output['units'],result_binding=binding)
    dependencies=dict(schema_version='1',sources=[pin],mappings=[dict(target=item['target'],source_label=pin['label'],
        **{k:binding[k] for k in ('source_output','results_digest','original_value','original_units','conversion')})])
    repin(case)
    return dependencies


@pytest.mark.parametrize('change',[None,'store','process','request','result_uuid','source_config','missing_upstream','copied_upstream','cache'])
def test_exact_native_source_provenance_before_process(catalog,source,change):
    case=case6(catalog); dependencies=linked(case,source)
    if change in ('store','process'):dependencies['sources'][0]['association'][change+'_uuid']=uid()
    elif change=='request':dependencies['sources'][0]['request']['payload_digest']='f'*64
    elif change=='result_uuid':
        pin=dependencies['sources'][0]; pin['result_uuid']=uid(); pin['label']='r'+pin['result_uuid'].replace('-','')
        dependencies['mappings'][0]['source_label']=pin['label']
    elif change=='source_config':
        case['frozen']['configuration']['inputs'][0]['result_binding']['source_configuration_digest']='b'*64; repin(case)
    bundle,request=assemble(case,dependencies); before=count()
    original=canonical(source['results'].get_dict()); pin=dependencies['sources'][0]
    upstream={pin['label']:source['results']}
    if change=='missing_upstream':upstream={}
    elif change=='copied_upstream':upstream={pin['label']:orm.Dict(dict=source['results'].get_dict(),backend=NATIVE_BACKEND).store()}
    error=ScalarCalculation.spec().inputs.validate(inputs(bundle,request,upstream,cache=change!='cache'))
    if change is None:
        assert error is None
        with pytest.raises(RuntimeError,match='Node-only boundary stop'):native().launch(bundle,request)
        node=orm.load_node(native().matches(request)[0])
        assert node.inputs.upstream_results[pin['label']].uuid==source['results'].uuid
        assert not node.base.caching.is_created_from_cache
    else:
        assert error is not None
        if change not in ('missing_upstream','copied_upstream','cache'):
            with pytest.raises(ValueError):native().launch(bundle,request)
        assert count()==before
    assert canonical(source['results'].get_dict())==original
    assert source['results'].creator.uuid==source['process'].uuid


@pytest.mark.parametrize('declaration',['physical','unspecified'])
def test_mixed_raw_launcher_calcjob_and_offline_exact(catalog,tmp_path,declaration):
    from test_unit_execution_admission import mixed_case
    from hyprn_mvp_integration.results import retained_bundle
    case=mixed_case(catalog,declaration);bundle,request=assemble(case);before=deepcopy(bundle);processes=count()
    launcher.verify_execution_bundle(bundle,request,runtime_fixture())
    prepared_inputs=inputs(bundle,request)
    assert ScalarCalculation.spec().inputs.validate(prepared_inputs) is None
    assert retained_bundle(prepared_inputs['frozen_bundle'].base.repository,request)==bundle
    assert bundle==before and count()==processes
    bundle['manifest']['schema_version']='5';reseal(bundle,request)
    from hyprn_mvp_app.execution import check_digest,verify_files
    check_digest(bundle['manifest'],'bundle_digest');verify_files(bundle['manifest']['files'],bundle['files'])
    refuse(bundle,request,tmp_path)
    with pytest.raises(ValueError) as error:
        retained_bundle(inputs(bundle,request)['frozen_bundle'].base.repository,request)
    assert not isinstance(error.value,(KeyError,AssertionError))
    assert count()==processes


@pytest.mark.parametrize('linked',[False,True])
def test_raw_legacy_bundle5_offline_has_no_invented_study_revision(catalog,linked,monkeypatch):
    from hyprn_mvp_integration.results import retained_bundle
    from hyprn_mvp_app import execution_bundle
    case=case6(catalog,linked,legacy=True);bundle,request=assemble(case)
    original=execution_bundle.validate_retained_bundle;seen=[]
    def checked(b,r,snapshot,*,raw_snapshot=False):
        assert raw_snapshot and set(snapshot)=={'configuration','model_snapshot','approach_closure'}
        seen.append(True);return original(b,r,snapshot,raw_snapshot=raw_snapshot)
    monkeypatch.setattr(execution_bundle,'validate_retained_bundle',checked)
    assert retained_bundle(inputs(bundle,request)['frozen_bundle'].base.repository,request)==bundle
    assert seen==[True]


@pytest.mark.parametrize('kind',['physical','unspecified','legacy','typed'])
def test_portable_raw_inspection_preserves_exact_selected_model_without_wrapper(catalog,tmp_path,kind):
    from test_unit_execution_admission import mixed_case
    from test_approach_modified_runs import retain_api
    from hyprn_mvp_app.store import Store
    from test_unit_history import portable,archive
    from hyprn_mvp_app.computational_export import inspect_record
    case=(case6(catalog,True,legacy=kind=='legacy') if kind in ('legacy','typed') else mixed_case(catalog,kind))
    store=Store(tmp_path/'portable.sqlite');actor=uid()
    study=store.create_study(actor,uid(),'Portable raw fixture');c=case['frozen']['configuration']
    with store.connection(write=True) as db:
        db.execute('PRAGMA defer_foreign_keys=ON')
        db.execute('UPDATE studies SET study_id=? WHERE study_id=?',(c['study_id'],study['study_id']))
        db.execute('UPDATE memberships SET study_id=? WHERE study_id=?',(c['study_id'],study['study_id']))
        db.execute('INSERT INTO configurations VALUES(?,?,?,?)',(c['configuration_revision_id'],c['configuration_id'],c['study_id'],json.dumps(case['frozen'])))
    e=dict(store=store,actor=actor,sid=c['study_id'],case=case)
    e['rid']=retain_api(e,case['frozen']);files=portable(e);before=deepcopy(files)
    manifest=inspect_record(archive(files))
    assert manifest['selected_run_ids']==[e['rid']]
    loc='hyprn-mvp/runs/'+e['rid']+'/bundle/'
    assert files[loc+'model.json']==canonical(case['frozen']['model_snapshot'])
    assert files[loc+'configuration.json']==canonical(case['frozen']['configuration'])
    assert files==before
    if kind in ('physical','unspecified'):
        from hyprn_mvp_app.computational_export import sha
        # Reseal every affected nested and outer identity: only pairing is false.
        bundle=json.loads(files[loc+'manifest.json']);bundle['schema_version']='5'
        bundle['bundle_digest']=digest({k:v for k,v in bundle.items() if k!='bundle_digest'})
        files[loc+'manifest.json']=canonical(bundle)
        prefix='hyprn-mvp/runs/'+e['rid']+'/'
        result=json.loads(files[prefix+'results.json']);result['bundle_digest']=bundle['bundle_digest']
        files[prefix+'results.json']=canonical(result)
        mapping=manifest['runs'][0];mapping.update(bundle_digest=bundle['bundle_digest'],results_digest=digest(result))
        files[prefix+'identity.json']=canonical(mapping)
        for row in manifest['inventory']:
            raw=files[row['path']];row.update(size=len(raw),sha256=sha(raw))
        manifest['manifest_digest']=digest({k:v for k,v in manifest.items() if k!='manifest_digest'})
        files['manifest.json']=canonical(manifest)
        with pytest.raises(ValueError,match='ApproachClosurePreUnits'):inspect_record(archive(files))


@pytest.mark.parametrize('version,approach,legacy,mixed',[
    ('4',None,False,False),('4','1',True,False),('4','2',False,True),
    ('3','2',False,False),('2','2',True,False)])
def test_polish_launcher_and_retained_reader(catalog,version,approach,legacy,mixed):
    from test_unit_execution_admission import case8
    from hyprn_mvp_integration.results import retained_bundle
    case=case8(catalog,version,approach,legacy,mixed);b,r=assemble(case)
    launcher.verify_execution_bundle(b,r,runtime_fixture())
    assert ScalarCalculation.spec().inputs.validate(inputs(b,r)) is None
    repository=inputs(b,r)['frozen_bundle'].base.repository
    assert retained_bundle(repository,r)==b


@pytest.mark.parametrize('change',['missing','mismatch','downgrade','corrupt_closure'])
def test_polish_retained_manifest_tamper(catalog,change):
    from test_unit_execution_admission import case8
    from hyprn_mvp_integration.results import retained_bundle
    b,r=assemble(case8(catalog))
    if change=='missing':del b['manifest']['model_schema_version']
    elif change=='mismatch':b['manifest']['model_schema_version']='2'
    elif change=='downgrade':b['manifest']['schema_version']='6';del b['manifest']['model_schema_version']
    else:b['files']['approach/closure.json']+=b' '
    reseal(b,r)
    with pytest.raises(ValueError):retained_bundle(inputs(b,r)['frozen_bundle'].base.repository,r)
