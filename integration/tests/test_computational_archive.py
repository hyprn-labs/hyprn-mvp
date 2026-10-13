"""Actual pinned native archives from synthetic fresh records; no candidate execution."""
import base64
import copy
import io
import json
from pathlib import Path

import pytest
from aiida import orm
from aiida.common.links import LinkType
from checks import NATIVE_BACKEND, PROJECTION_SCOPE
from execution_fixtures import fixture, runtime_fixture
from hyprn_mvp_app.execution import assemble_bundle, executable_digest
from hyprn_mvp_app.scientific_configuration import project_scientific_configuration
from hyprn_mvp_app.store import canonical, digest, uid
from hyprn_mvp_integration.calculation import NativeExecution


def record(*, failed=False, seal=True, upstream=None, code=None, script=False, attributes=None, incomplete=None, diagnostic_transform=None, rounding=False, stderr=None):
    case=fixture(); config=case['frozen']['configuration']
    config.update(schema_version='2',context_source=dict(kind='current_study',expected_study_revision='fixture'),derivation=None)
    for item in config['inputs']:item['result_binding']=None
    dependencies=dict(schema_version='1',sources=[],mappings=[])
    if upstream:
        source,source_payload=upstream;source_item=source_payload['computations'][0]
        output=source.outputs.results.get_dict()['outputs'][0];item=config['inputs'][0]
        config['study_id']=source_payload['study_id']
        source_config=json.loads(source.inputs.frozen_bundle.base.repository.get_object_content('configuration.json'))
        conversion=dict(policy='openmdao-linear-catalog-1',catalog_digest='c'*64,source_units=output['units'],destination_units=item['units'],factor=1,destination_value=output['value'])
        binding=dict(source_run_id=source_item['run_id'],source_output=output['target'],results_digest=source_item['results_digest'],source_configuration_digest=source_config['digest'],original_value=output['value'],original_units=output['units'],conversion=conversion,
            labels=dict(run_name=source_config['name'],model_name=None,model_revision_id=source_config['model_revision_id'],instance_name='Fixture',output_name='Fixture'))
        item.update(value=output['value'],units=output['units'],result_binding=binding)
        config['required_capabilities'].append('result_linked_inputs/1')
        pin=dict(source_run_id=source_item['run_id'],request=source_item['request'],association=source_item['association'],results_digest=source_item['results_digest'],result_uuid=source.outputs.results.uuid,label='r'+source.outputs.results.uuid.replace('-',''))
        dependencies=dict(schema_version='1',sources=[pin],mappings=[dict(target=item['target'],source_label=pin['label'],**{k:binding[k] for k in ('source_output','results_digest','original_value','original_units','conversion')})])
    config['digest']=digest({k:v for k,v in config.items() if k!='digest'})
    prepared=case['prepared'];prepared['configuration_digest']=project_scientific_configuration(config)['digest']
    prepared['executable_content_digest']=executable_digest(prepared)
    prepared['prepared_digest']=digest({k:v for k,v in prepared.items() if k!='prepared_digest'})
    bundle=assemble_bundle(uid(),prepared,case['files'],case['frozen'],runtime_fixture(),dependencies)
    request=dict(run_id=bundle['manifest']['run_id'],scope=config['study_id'],command_id=uid(),payload_digest='a'*64,bundle_digest=bundle['manifest']['bundle_digest'])
    backend=NATIVE_BACKEND
    node=orm.CalcJobNode(process_type='aiida.calculations:hyprn_mvp.scalar',backend=backend)
    if code:
        node.computer=code.computer
        node.base.links.add_incoming(code,link_type=LinkType.INPUT_CALC,link_label='code')
    if upstream:node.base.links.add_incoming(upstream[0].outputs.results,link_type=LinkType.INPUT_CALC,link_label='upstream_results__'+pin['label'])
    req=orm.Dict(dict=request,backend=backend).store(); frozen=orm.FolderData(backend=backend)
    for path,raw in {**bundle['files'],'manifest.json':canonical(bundle['manifest'])}.items():
        frozen.base.repository.put_object_from_filelike(io.BytesIO(raw),path)
    frozen.store()
    node.base.links.add_incoming(req,link_type=LinkType.INPUT_CALC,link_label='request')
    node.base.links.add_incoming(frozen,link_type=LinkType.INPUT_CALC,link_label='frozen_bundle')
    if script:
        text=("#!/bin/bash\nexec > _scheduler-stdout.txt\nexec 2> _scheduler-stderr.txt\n\n\n"
              f"'{PROJECTION_SCOPE.root}/launch-worker' 'input' '{request['bundle_digest']}'  > 'result.json' 2> 'launcher.stderr'\n")
        if script=='unsafe':text+='export API_TOKEN=credential-value\n'
        node.base.repository.put_object_from_filelike(io.BytesIO(text.encode()),'_aiidasubmit.sh')
        calc=dict(codes_info=[dict(code_uuid=code.uuid,cmdline_params=['input',request['bundle_digest']],stdout_name='result.json',stderr_name='launcher.stderr')],local_copy_list=[[frozen.uuid,'.','input']],retrieve_list=['result.json','launcher.stderr','_scheduler-stdout.txt','_scheduler-stderr.txt'],uuid=node.uuid,file_copy_operation_order=[2,0,1])
        job=dict(submit_as_hold=False,rerunnable=False,job_name='aiida-123',sched_output_path='_scheduler-stdout.txt',shebang='#!/bin/bash',sched_error_path='_scheduler-stderr.txt',sched_join_files=False,prepend_text='',append_text='',job_resource=dict(num_machines=1,num_mpiprocs_per_machine=1,num_cores_per_machine=None,num_cores_per_mpiproc=None,tot_num_mpiprocs=1),codes_info=[dict(prepend_cmdline_params=[],cmdline_params=[str(PROJECTION_SCOPE.root/'launch-worker'),'input',request['bundle_digest']],use_double_quotes=[False,False],wrap_cmdline_params=False,stdin_name=None,stdout_name='result.json',stderr_name='launcher.stderr',join_files=False)],codes_run_mode=0,import_sys_environment=True,job_environment={},environment_variables_double_quotes=False,max_memory_kb=None,max_wallclock_seconds=60)
        for path,value in {'.aiida/calcinfo.json':calc,'.aiida/job_tmpl.json':job}.items():node.base.repository.put_object_from_filelike(io.BytesIO(canonical(value)),path)
    if attributes:node.base.attributes.set_many(attributes)
    node.store()
    outputs=json.loads(case['files'][prepared['entrypoint']['bindings_path']])['outputs']
    result=dict(schema_version='1',run_id=request['run_id'],bundle_digest=request['bundle_digest'],
        execution=dict(state='failed' if failed else 'finished',exit_code=1 if failed else 0,message='Synthetic scientific failure' if failed else 'Synthetic retained result'),
        convergence=dict(state='not_applicable',diagnostics_ref=None),optimization=dict(termination='not_applicable',feasibility='not_applicable'),
        completeness=dict(expected=len(outputs),available=len(outputs),failed=0,unavailable=0),
        outputs=[dict(target=o['target'],value=150+i,units=o['units'],availability='available',reason=None,producer_completed=True,assigned=True) for i,o in enumerate(outputs)],
        criteria=[],applicability=dict(state='unassessed',evidence_refs=[]),artifacts=[])
    if incomplete=='logs_only':result['execution']['message']=''
    if rounding:result['outputs'][0]['value']=150.00000000000003
    results=orm.Dict(dict=result,backend=backend);results.base.links.add_incoming(node,link_type=LinkType.CREATE,link_label='results');results.store()
    retrieved=orm.FolderData(backend=backend)
    envelope=dict(id=PROJECTION_SCOPE.root.name+'-worker-'+uid().replace('-',''),reason='exited',exit_code=0,seconds=1.0,
        state=dict(Status='exited',Running=False,Paused=False,Restarting=False,OOMKilled=False,Dead=False,Pid=0,ExitCode=0,Error='',StartedAt='2026-10-09T00:00:00Z',FinishedAt='2026-10-09T00:00:01Z'),
        output='HYPRN_MVP_RESULT_V1 '+json.dumps(result)+'\n')
    if diagnostic_transform:diagnostic_transform(envelope)
    for path,raw in {'result.json':canonical(envelope),'launcher.stderr':b'Synthetic scientific failure\n' if failed else b''}.items():
        if path=='launcher.stderr' and stderr is not None:raw=stderr
        if path=='launcher.stderr' and incomplete=='missing_artifact':continue
        if path=='launcher.stderr' and incomplete=='logs_only':raw=b''
        retrieved.base.repository.put_object_from_filelike(io.BytesIO(raw),path)
    retrieved.base.links.add_incoming(node,link_type=LinkType.CREATE,link_label='retrieved');retrieved.store()
    node.set_process_state('finished');node.set_exit_status(301 if failed else 0)
    if seal:node.seal()
    item=dict(run_id=request['run_id'],request=request,association=dict(store_uuid=PROJECTION_SCOPE.store_uuid,process_uuid=node.uuid),results_digest=digest(results.get_dict()),role='selected')
    payload=dict(schema_version='1',study_id=request['scope'],origin_store_uuid=PROJECTION_SCOPE.store_uuid,roots=[request['run_id']],computations=[item],policy_version='record-policy-1')
    return node,payload


def infrastructure():
    codes=orm.QueryBuilder(backend=NATIVE_BACKEND).append(orm.InstalledCode,filters={'label':'hyprn-mvp-scalar'},project='*').all()
    if codes:return codes[0][0]
    computer=orm.Computer(label='hyprn-mvp-scoped-worker',hostname='localhost',transport_type='core.local',scheduler_type='core.direct',workdir=str(PROJECTION_SCOPE.root/'tmp/work/{username}'),backend=NATIVE_BACKEND)
    computer.set_minimum_job_poll_interval(0.2);computer.store()
    return orm.InstalledCode(label='hyprn-mvp-scalar',computer=computer,filepath_executable=str(PROJECTION_SCOPE.root/'launch-worker'),default_calc_job_plugin='hyprn_mvp.scalar',backend=NATIVE_BACKEND).store()


def native():return NativeExecution(backend=NATIVE_BACKEND,root=PROJECTION_SCOPE.root)


def accounting_export():
    from hyprn_mvp_integration.computational_export import Export
    value=Export.__new__(Export)
    value.bytes=value.paths=value.nested_bytes=value.nested_paths=0
    value.objects={};value.nested_archives={}
    return value


def accounting_folder(files):
    folder=orm.FolderData(backend=NATIVE_BACKEND)
    for path,raw in files.items():folder.base.repository.put_object_from_filelike(io.BytesIO(raw),path)
    return folder.store()


def source_tar(files):
    import tarfile
    stream=io.BytesIO()
    with tarfile.open(fileobj=stream,mode='w:gz') as archive:
        for name,raw in files.items():
            item=tarfile.TarInfo(name);item.size=len(raw)
            archive.addfile(item,io.BytesIO(raw))
    return stream.getvalue()


def test_accounting_duplicate_objects_keep_all_logical_paths(monkeypatch):
    from hyprn_mvp_integration import computational_export as policy
    folder=accounting_folder({'a':b'x'*40,'b':b'x'*40})
    other=accounting_folder({'c':b'x'*40})
    monkeypatch.setattr(policy,'EXPANDED',64)
    export=accounting_export()
    assert export.repositories(folder)=={'a':b'x'*40,'b':b'x'*40}
    assert export.repositories(other)=={'c':b'x'*40}
    assert export.bytes==40 and export.paths==3 and len(export.objects)==1


@pytest.mark.parametrize('kind',['distinct_bytes','logical_paths','hash','size'])
def test_accounting_bounds_and_identity_are_not_deduplicated(monkeypatch,kind):
    from hyprn_mvp_integration import computational_export as policy
    folder=accounting_folder({'a':b'x'*40,'b':(b'y' if kind=='distinct_bytes' else b'x')*40})
    export=accounting_export()
    if kind=='distinct_bytes':monkeypatch.setattr(policy,'EXPANDED',64)
    elif kind=='logical_paths':monkeypatch.setattr(policy,'PATHS',1)
    elif kind=='hash':
        from types import SimpleNamespace
        monkeypatch.setattr(folder.base.repository,'get_object',lambda path:SimpleNamespace(key='0'*64))
    else:export.objects[__import__('hashlib').sha256(b'x'*40).hexdigest()]=39
    with pytest.raises(ValueError):export.repositories(folder)


def test_accounting_nested_cache_is_separate_and_only_after_inspection(monkeypatch):
    import tarfile
    raw=source_tar({'source.txt':b'x'*40});export=accounting_export();export.bytes=100;export.paths=4
    calls=[];original=tarfile.open
    def counted(*args,**kwargs):calls.append(True);return original(*args,**kwargs)
    monkeypatch.setattr(tarfile,'open',counted)
    export.tar(raw);export.tar(raw)
    assert calls==[True] and export.bytes==100 and export.paths==4
    assert export.nested_bytes==40 and export.nested_paths==1


@pytest.mark.parametrize('kind',['expanded','paths','file','unsafe','duplicate_archive_failure'])
def test_accounting_nested_archives_remain_bounded(monkeypatch,kind):
    from hyprn_mvp_integration import computational_export as policy
    export=accounting_export();raw=source_tar({'a':b'x'*40,'b':b'y'*40})
    if kind=='expanded':monkeypatch.setattr(policy,'NESTED_EXPANDED',64,raising=False)
    elif kind=='paths':monkeypatch.setattr(policy,'NESTED_PATHS',1,raising=False)
    elif kind=='file':monkeypatch.setattr(policy,'RAW',39)
    elif kind=='unsafe':raw=source_tar({'../escape':b'x'})
    else:raw=b'not a gzip archive'
    for _ in range(2):
        with pytest.raises(ValueError):export.tar(raw)
    assert not export.nested_archives


def test_accounting_same_bytes_still_require_authorized_occurrence(monkeypatch):
    from hyprn_mvp_integration import computational_export as policy
    raw=fixture()['files']['provenance/patches/030-configuration.patch']
    node,payload=record(stderr=raw)
    # The same hash is authorized in provenance, but never in scientific stderr.
    assert node.outputs.retrieved.base.repository.get_object('launcher.stderr').key==node.inputs.frozen_bundle.base.repository.get_object('provenance/patches/030-configuration.patch').key
    calls=[];original=policy.sensitive
    def sensitive(value,**kwargs):
        if value==raw:calls.append(True)
        return original(value,**kwargs)
    monkeypatch.setattr(policy,'sensitive',sensitive)
    with pytest.raises(ValueError,match='Sensitive'):native().archive_record(payload)
    assert calls


@pytest.mark.parametrize('kind',['valid','rounding','identity','duplicate','exit','extra','mismatch'])
def test_actual_launcher_envelope_matches_stored_result(kind):
    def transform(envelope):
        if kind=='duplicate':envelope['output']*=2
        elif kind=='exit':envelope['exit_code']=1
        elif kind=='extra':envelope['unexpected']='not-approved'
        elif kind in ('identity','mismatch'):
            value=json.loads(envelope['output'].split(' ',1)[1])
            if kind=='identity':value['run_id']=uid()
            else:value['outputs'][0]['value']=151
            envelope['output']='HYPRN_MVP_RESULT_V1 '+json.dumps(value)+'\n'
    node,payload=record(diagnostic_transform=transform,rounding=kind=='rounding')
    original=node.outputs.retrieved.base.repository.get_object_content('result.json',mode='rb')
    if kind in ('valid','rounding'):
        assert native().archive_record(payload)['archive_size']>0
        assert node.outputs.retrieved.base.repository.get_object_content('result.json',mode='rb')==original
        if kind=='rounding':assert node.outputs.results.get_dict()['outputs'][0]['value']==150
    else:
        with pytest.raises(ValueError):native().archive_record(payload)


def offline_roundtrip(path,scope,origin,*,expected_processes):
    """Pinned data-only import to an explicit fresh backend, never global profile."""
    import hashlib
    from aiida.manage.configuration.profile import Profile
    from aiida.storage.sqlite_dos.backend import SqliteDosStorage
    from aiida.tools.archive import import_archive
    from aiida.tools.archive.implementations.sqlite_zip.main import ArchiveFormatSqlZip
    import scoped_fixture as guard
    guard.validate_scope(scope)
    destination=guard.scoped_path(scope,'artifacts/offline-'+uid())
    assert not destination.exists();destination.mkdir(mode=0o700)
    profile=Profile('hyprn-mvp-offline-'+uid(),dict(PROFILE_UUID=uid(),storage=dict(backend='core.sqlite_dos',config=dict(filepath=str(destination))),process_control=dict(backend=None,config=None),test_profile=True))
    SqliteDosStorage.initialise(profile);backend=SqliteDosStorage(profile)
    assert orm.QueryBuilder(backend=backend).append(orm.Node).count()==0
    assert backend.get_repository().uuid!=origin.get_repository().uuid
    def snapshot(storage):
        nodes={};links=[]
        for [node] in orm.QueryBuilder(backend=storage).append(orm.Node,project='*').all():
            repository={}
            for directory,_,names in node.base.repository.walk():
                for name in names:
                    key=str(directory/name);raw=node.base.repository.get_object_content(key,mode='rb')
                    repository[key]=dict(size=len(raw),sha256=hashlib.sha256(raw).hexdigest())
            attrs=dict(node.base.attributes.all);attrs.pop(orm.ProcessNode.CHECKPOINT_KEY,None)
            # AiiDA import_new_extras explicitly omits private _aiida_ keys.
            extras={k:v for k,v in node.base.extras.all.items() if not k.startswith('_aiida_')}
            nodes[node.uuid]=dict(node_type=node.node_type,process_type=node.process_type,attributes=attrs,extras=extras,label=node.label,description=node.description,repository=repository)
            links.extend((link.node.uuid,node.uuid,link.link_label,link.link_type.value) for link in node.base.links.get_incoming().all())
        return dict(nodes=nodes,links=sorted(links))
    try:
        with ArchiveFormatSqlZip().open(path,'r') as reader:
            archived=snapshot(reader.get_backend())
            processes={key for key,row in archived['nodes'].items() if row['node_type'].startswith('process.')}
            assert processes==expected_processes
        group=import_archive(path,backend=backend,include_authinfos=False,create_group=False,import_new_extras=True,merge_extras=('k','n','l'))
        assert group is None
        imported=snapshot(backend);assert imported==archived
        for entity in (orm.AuthInfo,orm.Comment,orm.Log,orm.Group):assert orm.QueryBuilder(backend=backend).append(entity).count()==0
        origin_nodes=snapshot(origin)['nodes']
        for key,value in archived['nodes'].items():assert value==origin_nodes[key]
        proof=dict(origin_store_uuid=str(origin.get_repository().uuid),import_store_uuid=str(backend.get_repository().uuid),profile_uuid=profile.uuid,node_uuids=sorted(archived['nodes']),inventory=archived,excluded_private_extras_prefix='_aiida_',excluded_process_checkpoint=orm.ProcessNode.CHECKPOINT_KEY,include_authinfos=False,create_group=False,import_new_extras=True,merge_extras=['k','n','l'])
        (destination/'roundtrip.json').write_text(json.dumps(proof,indent=2)+'\n')
        return proof
    finally:backend.close()


@pytest.mark.parametrize('path',['licenses/native/'+name+'.dist-info/METADATA' for name in ('aio_pika-9.5.8','shortuuid-1.0.13','charset_normalizer-3.5.2','jedi-0.18.2','psutil-7.2.2')]+['licenses/worker/'+name+'.dist-info/METADATA' for name in ('charset_normalizer-3.5.2','tomli-2.5.0')])
@pytest.mark.parametrize('change',['none','bytes','role','path','notice','hash'])
def test_license_documentation_allowance_is_exact(path,change):
    import hashlib
    import scoped_fixture as guard
    from hyprn_mvp_integration import computational_export as policy
    raw=(Path(guard.APPROVED_PYTHON).parents[2]/path).read_bytes()
    manifest=dict(files=[dict(path=path,role='licenses',sha256=hashlib.sha256(raw).hexdigest(),size=len(raw))],licenses=[dict(kind='runtime',path=path)])
    if change=='bytes':raw+=b'\nAPI_TOKEN=credential-value'
    elif change=='role':manifest['files'][0]['role']='source'
    elif change=='path':path='sources/copied.py'
    elif change=='notice':manifest['licenses']=[]
    elif change=='hash':manifest['files'][0]['sha256']='a'*64
    assert policy.audited_license(manifest,path,raw)==(change=='none')
    # No global hash exemption, even for exactly these documentation bytes.
    with pytest.raises(ValueError):policy.sensitive(raw)


@pytest.mark.parametrize('version',[1,True,'2'])
def test_archive_wire_version_matches_closed_contract(version):
    _,payload=record();payload['schema_version']=version
    with pytest.raises(ValueError,match='policy'):native().archive_record(payload)


@pytest.mark.parametrize('failed',[False,True])
def test_actual_archive_inventory_and_readback(failed,tmp_path):
    node,payload=record(failed=failed);other,_=record()
    response=native().archive_record(payload)
    raw=base64.b64decode(response['archive_base64'],validate=True)
    assert response['archive_size']==len(raw) and response['archive_sha256']==__import__('hashlib').sha256(raw).hexdigest()
    assert response['inventory_digest']==digest(response['inventory'])
    assert node.uuid in {n['uuid'] for n in response['inventory']['nodes']}
    assert other.uuid not in {n['uuid'] for n in response['inventory']['nodes']}
    path=tmp_path/'actual.aiida';path.write_bytes(raw)
    from aiida.tools.archive.implementations.sqlite_zip.main import ArchiveFormatSqlZip
    with ArchiveFormatSqlZip().open(path,'r') as reader:
        assert reader.querybuilder().append(orm.CalcJobNode,project='uuid').all(flat=True)==[node.uuid]
        assert reader.get(orm.Dict,uuid=node.outputs.results.uuid).get_dict()==node.outputs.results.get_dict()
    (PROJECTION_SCOPE.root/'evidence'/('failed.aiida' if failed else 'finished.aiida')).write_bytes(raw)


@pytest.mark.parametrize('bad',['unsealed','request','store','store_spelling','digest','scope','extra','missing','label','secret'])
def test_refuses_unapproved_or_incomplete_records(bad):
    node,payload=record(seal=bad!='unsealed')
    item=payload['computations'][0]
    if bad=='request':item['request']['payload_digest']='b'*64
    elif bad=='store':item['association']['store_uuid']=uid()
    elif bad=='store_spelling':item['association']['store_uuid']=item['association']['store_uuid'].upper()
    elif bad=='digest':item['results_digest']='b'*64
    elif bad=='scope':payload['study_id']=uid()
    elif bad=='extra':payload['native_id']=node.uuid
    elif bad=='missing':item['association']['process_uuid']=uid()
    elif bad=='label':node.label='token=secret-value'
    elif bad=='secret':node.base.extras.set('API_TOKEN','secret-value')
    with pytest.raises(ValueError):native().archive_record(payload)


def test_exact_computational_closure_shared_code_no_unrelated_descendants():
    code=infrastructure();source=record(code=code);selected,payload=record(upstream=source,code=code,script=True)
    unrelated,_=record(code=code);descendant,_=record(upstream=source,code=code)
    ancestor=copy.deepcopy(source[1]['computations'][0]);ancestor['role']='computational_ancestor'
    payload['computations']=sorted([*payload['computations'],ancestor],key=lambda r:r['run_id'])
    response=native().archive_record(payload);inventory=response['inventory']
    processes={n['uuid'] for n in inventory['nodes'] if n['node_type'].startswith('process.')}
    assert processes=={source[0].uuid,selected.uuid}
    assert not processes&{unrelated.uuid,descendant.uuid}
    assert len(inventory['computers'])==len(inventory['users'])==1
    assert any(r['path']=='_aiidasubmit.sh' for r in inventory['repositories'])
    without=copy.deepcopy(payload);without['computations']=[r for r in payload['computations'] if r['role']=='selected']
    with pytest.raises(ValueError,match='creator|closure'):native().archive_record(without)
    (PROJECTION_SCOPE.root/'evidence/linked.aiida').write_bytes(base64.b64decode(response['archive_base64']))


def test_metadata_race_blocks_archive_release():
    node,payload=record();service=native()
    def race(point):
        if point=='archive_preflight':node.base.extras.set('credential','not-for-export')
    service.fault=race
    with pytest.raises(ValueError,match='extras'):service.archive_record(payload)


@pytest.mark.parametrize('incomplete',['missing_artifact','logs_only'])
def test_incomplete_failed_scientific_record_is_not_exportable(incomplete):
    _,payload=record(failed=True,incomplete=incomplete)
    with pytest.raises(ValueError,match='diagnostics|failure explanation'):native().archive_record(payload)


@pytest.mark.parametrize('bad',['user','computer','code','script','environment','unknown_attribute','checkpoint'])
def test_infrastructure_and_process_policy(bad):
    code=infrastructure()
    if bad=='code':
        code=orm.InstalledCode(label='hyprn-mvp-scalar',computer=code.computer,filepath_executable=str(PROJECTION_SCOPE.root/'launch-worker'),default_calc_job_plugin='hyprn_mvp.scalar',backend=NATIVE_BACKEND)
        code.base.attributes.set('prepend_text','export API_TOKEN=credential-value');code.store()
    attributes={'environment':{'environment_variables':{'API_TOKEN':'credential-value'}},'unknown_attribute':{'unknown':'value'},'checkpoint':{orm.ProcessNode.CHECKPOINT_KEY:'executable private checkpoint'}}.get(bad)
    node,payload=record(code=code,script='unsafe' if bad=='script' else True,seal=False,attributes=attributes)
    original_user=node.user.email
    try:
        if bad=='user':node.user.email='private@example.invalid'
        elif bad=='computer':code.computer.hostname='private.example.invalid'
        node.seal()
        if bad=='checkpoint':
            result=native().archive_record(payload)
            assert 'process_checkpoints' in result['inventory']['omissions']
        else:
            with pytest.raises(ValueError):native().archive_record(payload)
    finally:
        node.user.email=original_user
        code.computer.hostname='localhost'


@pytest.mark.parametrize('limit',['RAW','EXPANDED','PATHS','METADATA','INVENTORY'])
def test_bounds_before_transfer(monkeypatch,limit):
    from hyprn_mvp_integration import computational_export as export
    _,payload=record();monkeypatch.setattr(export,limit,1)
    with pytest.raises(ValueError):native().archive_record(payload)


@pytest.mark.parametrize('name',['../escape','/absolute','a\\b','repo/not-a-hash','metadata.json'])
def test_malformed_native_zip_is_refused_before_reader(tmp_path,name):
    import zipfile
    from hyprn_mvp_integration.computational_export import archive_bounds
    path=tmp_path/'malformed.aiida'
    with zipfile.ZipFile(path,'w') as archive:
        archive.writestr('metadata.json','{}');archive.writestr('db.sqlite3',b'not sqlite');archive.writestr(name,b'x')
    with pytest.raises(ValueError):archive_bounds(path)


def test_audited_provenance_allowance_is_exact_role_path_and_hash():
    from hyprn_mvp_integration.computational_export import AUDITED_PROVENANCE,sensitive
    case=fixture();path='provenance/patches/030-configuration.patch';raw=case['files'][path]
    assert __import__('hashlib').sha256(raw).hexdigest()==AUDITED_PROVENANCE[path]
    with pytest.raises(ValueError):sensitive(raw)  # No global hash exemption.
    assert __import__('hashlib').sha256(raw+b'\nAPI_TOKEN=credential-value').hexdigest()!=AUDITED_PROVENANCE[path]


# Account-home paths in macOS and Linux form are assembled from fragments at run time, so the
# source never holds a literal that the repository hygiene guard refuses.
@pytest.mark.parametrize('raw',[b'API_TOKEN=credential-value',b'access_token: private-value',b'/'+b'Users'+b'/'+b'private/account.txt',b'/'+b'home'+b'/'+b'private/account.txt',b'/private/tmp/unapproved/account.txt'])
def test_sensitive_candidate_content_has_no_infrastructure_exemption(raw):
    from hyprn_mvp_integration.computational_export import sensitive
    with pytest.raises(ValueError):sensitive(raw)


def test_data_only_operation_omits_admin_and_preserves_science(monkeypatch,tmp_path):
    node,payload=record(code=infrastructure(),script=True)
    original=canonical(node.outputs.results.get_dict())
    from hyprn_mvp_integration import launcher
    def forbidden(*args,**kwargs):raise AssertionError('Execution authority reached')
    for name in ('launch','require_attestation','bundle_runtime','read_record','inspect'):
        monkeypatch.setattr(NativeExecution,name,forbidden)
    monkeypatch.setattr(launcher,'require_attestation',forbidden)
    monkeypatch.setattr(orm.CalcJobNode,'process_class',property(forbidden))
    monkeypatch.setattr(orm.CalcJobNode,'get_builder_restart',forbidden)
    orm.AuthInfo(computer=node.computer,user=node.user,backend=NATIVE_BACKEND).store()
    node.base.comments.add('Administrative comment not part of scientific record')
    response=native().archive_record(payload)
    assert canonical(node.outputs.results.get_dict())==original
    path=tmp_path/'admin.aiida';path.write_bytes(base64.b64decode(response['archive_base64']))
    from aiida.tools.archive.implementations.sqlite_zip.main import ArchiveFormatSqlZip
    with ArchiveFormatSqlZip().open(path,'r') as reader:
        for entity in (orm.AuthInfo,orm.Comment,orm.Log):assert reader.querybuilder().append(entity).count()==0


@pytest.mark.parametrize('tamper',['extra_object','metadata','checkpoint_policy'])
def test_actual_archive_tampering_blocks_release(monkeypatch,tamper):
    import zipfile
    from hyprn_mvp_integration import computational_export as export
    _,payload=record();original=export.create_archive
    def altered(*args,**kwargs):
        if tamper=='checkpoint_policy':kwargs['include_comments']=True
        result=original(*args,**kwargs)
        if tamper!='checkpoint_policy':
            with zipfile.ZipFile(args[1],'a') as archive:
                name='repo/'+__import__('hashlib').sha256(b'unlisted').hexdigest() if tamper=='extra_object' else 'metadata.json'
                archive.writestr(name,b'unlisted' if tamper=='extra_object' else b'{}')
        return result
    monkeypatch.setattr(export,'create_archive',altered)
    with pytest.raises(ValueError):native().archive_record(payload)


@pytest.mark.parametrize('location',['process','input','creator','archive'])
def test_unexpected_plugin_type_rejected_before_orm_materialization(monkeypatch,location):
    from aiida.orm.utils import node as conversion
    from sqlalchemy import text
    from hyprn_mvp_integration import computational_export as export
    node,payload=record();bad='data.untrusted.Candidate.';calls=[]
    original_loader=conversion.load_node_class
    def loader(kind):
        if kind==bad:
            calls.append(kind);raise AssertionError('Unexpected plugin would have been imported')
        return original_loader(kind)
    monkeypatch.setattr(conversion,'load_node_class',loader)
    if location!='archive':
        if location=='creator':
            target=orm.CalcJobNode(process_type='aiida.calculations:hyprn_mvp.scalar',backend=NATIVE_BACKEND).store()
            session=NATIVE_BACKEND.get_session()
            session.execute(text('INSERT INTO db_dblink(input_id,output_id,label,type) VALUES(:source,:target,:label,:kind)'),dict(source=target.pk,target=node.inputs.request.pk,label='unapproved',kind='create'))
        else:target=node if location=='process' else node.inputs.request
        session=NATIVE_BACKEND.get_session()
        session.execute(text('UPDATE db_dbnode SET node_type=:kind WHERE id=:id'),dict(kind=bad,id=target.pk));session.commit()
    else:
        import sqlite3,zipfile
        original=export.create_archive
        def altered(*args,**kwargs):
            result=original(*args,**kwargs);path=Path(args[1])
            with zipfile.ZipFile(path) as archive:files={name:archive.read(name) for name in archive.namelist()}
            db=path.with_suffix('.sqlite');db.write_bytes(files['db.sqlite3'])
            with sqlite3.connect(db) as connection:
                changed=connection.execute('UPDATE db_dbnode SET node_type=? WHERE uuid=?',(bad,node.inputs.request.uuid))
                assert changed.rowcount==1
            files['db.sqlite3']=db.read_bytes()
            with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as archive:
                for name,raw in files.items():archive.writestr(name,raw)
            return result
        monkeypatch.setattr(export,'create_archive',altered)
    with pytest.raises(ValueError,match='unsupported|Unsupported'):native().archive_record(payload)
    assert calls==[]
