"""Bundle4 portable records: real parsed native inputs, offline data-only import."""
import base64
from copy import deepcopy
from contextlib import contextmanager
import io
import json
from pathlib import Path
import stat
import zipfile

import pytest
from aiida import orm
from aiida.tools.archive.implementations.sqlite_zip.main import ArchiveFormatSqlZip
from checks import PROJECTION_SCOPE as SCOPE, NATIVE_BACKEND as BACKEND
from hyprn_mvp_app.store import Store, DomainError, canonical, digest, uid
from hyprn_mvp_app.computational_export import ComputationalRecords, LIMITS, sha, zip_entries
from hyprn_mvp_app.execution import validate_retained_bundle
from hyprn_mvp_app.history import History
from hyprn_mvp_app.modified_runs import ModifiedRuns, changes
from hyprn_mvp_app.result_bindings import ResultBindings
from hyprn_mvp_app.modeling import validate
from hyprn_mvp_integration.calculation import NativeExecution
from hyprn_mvp_integration.computational_export import Export, archive_bounds
from hyprn_mvp_integration.results import retained_bundle
from test_assumptions_history import actual, payload, retain
from test_assumptions_execution import repin
from test_computational_archive import offline_roundtrip


@pytest.fixture(scope='module')
def exported(actual):
    env=actual;store=env['store'];source=dict(env)
    old=env['case']['frozen']['configuration']['evidence_snapshots'][0]
    note={k:deepcopy(old[k]) for k in ('evidence_schema_version','title','kind','content','source_refs','resource_scope')}
    note.update(title='Second calibration',content='A later retained observation')
    new=store.revise_evidence(env['actor'],env['sid'],old['evidence_id'],uid(),old['evidence_version_id'],note)
    case=deepcopy(env['case']);config=case['frozen']['configuration']
    config.update(configuration_id=uid(),configuration_revision_id=uid(),name='Portable citation closure')
    # Distinct configuration-owned context must survive the same retained/archive
    # path as other scientific records, including meaningful empty/line breaks.
    config['context_snapshot']=dict(description='Edited engineering question\n\nRetained paragraph.',
        boundary=env['case']['frozen']['configuration']['context_snapshot']['boundary'],
        notes=['A configuration-specific qualification', ''])
    config['assumptions'][0]['evidence_links'][0]=dict(evidence_version_id=new['evidence_version_id'],relation='context')
    config['evidence_snapshots']=sorted([old,new],key=lambda e:e['evidence_version_id'])
    output=next(o for o in env['record']['results']['outputs'] if o['value']==7)
    resolved=ResultBindings(store).resolve(env['actor'],env['sid'],dict(source_run_id=env['rid'],source_output=output['target'],expected_results_digest=digest(env['record']['results'])))
    item=config['inputs'][0];item['value']=resolved['value'];item['units']=resolved['units']
    item['result_binding']={k:resolved[k] for k in ('source_run_id','source_output','results_digest','source_configuration_digest','labels')}
    item['result_binding'].update(original_value=resolved['value'],original_units=resolved['units'],
        conversion=dict(policy='openmdao-linear-catalog-1',catalog_digest='c'*64,source_units=resolved['units'],destination_units=resolved['units'],factor=1,destination_value=resolved['value']))
    config['required_capabilities'].append('result_linked_inputs/1')
    config['derivation']=dict(source_run_id=env['rid'],source_configuration_revision_id=env['case']['frozen']['configuration']['configuration_revision_id'],
        source_configuration_digest=env['case']['frozen']['configuration']['digest'],source_runtime=env['bundle']['manifest']['runtime'],changes=[])
    config['derivation']['changes']=changes(env['case']['frozen']['configuration'],config)[0]
    repin(case)
    child=retain(env,case)
    assert sorted(o['value'] for o in child['record']['results']['outputs'])==[17,289]
    env=dict(env,source=source,child=child,selected=child['rid'])
    env['originals']={rid:canonical(payload(env,rid)) for rid in (source['rid'],child['rid'])}
    service=ComputationalRecords(store,SCOPE.root/'artifacts/ae-records')
    env['service']=service
    return env


@contextmanager
def inert_export(env,monkeypatch):
    """All export/read/import paths must be inert, including negative tests."""
    from hyprn_mvp_integration import launcher, worker
    from hyprn_mvp_app.modeling import Coordinator, ModelingClient
    from aiida.transports.plugins.local import LocalTransport
    import importlib.abc
    import sys
    calls=[]
    def deny(*args,**kwargs):
        calls.append(True);raise AssertionError('Export reached execution/current-library authority')
    for name in ('launch','inspect','require_attestation','bundle_runtime','read_record'):
        monkeypatch.setattr(NativeExecution,name,deny)
    monkeypatch.setattr(Store,'evidence_version',deny)
    monkeypatch.setattr(Coordinator,'read',deny)
    monkeypatch.setattr(ModelingClient,'call',deny)
    monkeypatch.setattr(launcher,'isolated',deny)
    monkeypatch.setattr(worker,'load_program',deny)
    monkeypatch.setattr(LocalTransport,'open',deny)
    monkeypatch.setattr(orm.CalcJobNode,'process_class',property(deny))
    monkeypatch.setattr(orm.CalcJobNode,'get_builder_restart',deny)
    names={Path(p).stem for p in env['case']['files'] if p.endswith('.py') and not p.startswith('provenance/')}
    names.update({'base','impl'})
    assert not names.intersection(sys.modules)
    class RejectCandidate(importlib.abc.MetaPathFinder):
        def find_spec(self,fullname,path=None,target=None):
            if fullname.split('.')[0] in names:deny()
    finder=RejectCandidate();sys.meta_path.insert(0,finder)
    before=orm.QueryBuilder(backend=BACKEND).append(orm.ProcessNode).count()
    def native_bytes():
        return {rid:dict(results=canonical(node.outputs.results.get_dict()),
            request=canonical(node.inputs.request.get_dict()),
            bundle={str(directory/name):node.inputs.frozen_bundle.base.repository.get_object_content(str(directory/name),mode='rb')
                for directory,_,names in node.inputs.frozen_bundle.base.repository.walk() for name in names})
            for rid,node in ((env['source']['rid'],env['source']['node']),(env['child']['rid'],env['child']['node']))}
    original_native=native_bytes()
    try:yield
    finally:sys.meta_path.remove(finder)
    assert not calls
    assert orm.QueryBuilder(backend=BACKEND).append(orm.ProcessNode).count()==before
    assert native_bytes()==original_native
    for rid,original in env['originals'].items():assert canonical(payload(env,rid))==original


@pytest.fixture(autouse=True)
def no_execution_or_live_lookup(exported,monkeypatch):
    with inert_export(exported,monkeypatch):yield


def preview(env):
    s=env['service'];q=s.enqueue_preview(env['actor'],env['sid'],dict(command_id=uid(),selected_run_ids=[env['selected']]))
    assert s.process_one(env['native'].archive_record,request_id=q['request_id'])
    result=s.status(env['actor'],env['sid'],q['request_id'])
    assert result['state']=='reviewable',result
    return result


@pytest.fixture(scope='module')
def ready_record(exported):
    env=exported;s=env['service']
    with pytest.MonkeyPatch.context() as patch, inert_export(env,patch):
        p=preview(env)
        body=dict(command_id=uid(),preview_id=p['request_id'],expected_preview_digest=p['preview']['preview_digest'])
        q=s.enqueue_create(env['actor'],env['sid'],body)
        assert s.process_one(env['native'].archive_record,request_id=q['request_id'])
        assert s.status(env['actor'],env['sid'],q['request_id'])['state']=='ready'
    return dict(preview=p,request=q,body=body)


def test_exact_offline_wrapper_native_read_and_import(exported,ready_record):
    env=exported;s=ComputationalRecords(Store(env['store'].path),env['service'].root)
    raw=s.download(env['actor'],env['sid'],ready_record['request']['request_id'])
    (SCOPE.root/'evidence/ae-record.zip').write_bytes(raw)
    z,_,_=zip_entries(raw,LIMITS['wrapper_bytes'])
    with z:
        manifest=json.loads(z.read('manifest.json'));validate('ComputationalRecordManifest1',manifest)
        assert manifest['schema_version']=='1' and manifest['classification']=='inspection_only'
        assert manifest['reexecution_prerequisites']['runtime_portability']=='unverified'
        assert manifest['manifest_digest']==digest({k:v for k,v in manifest.items() if k!='manifest_digest'})
        assert set(z.namelist())=={'manifest.json'}|{i['path'] for i in manifest['inventory']}
        assert set(manifest['computational_run_ids'])==set(env['originals'])
        assert manifest['selected_run_ids']==[env['selected']]
        for item in manifest['inventory']:
            data=z.read(item['path']);assert len(data)==item['size'] and sha(data)==item['sha256']
        for rid in env['originals']:
            p=payload(env,rid);prefix='hyprn-mvp/runs/'+rid+'/bundle/'
            files={path:z.read(prefix+path) for path in p['bundle']['files']}
            assert files=={path:base64.b64decode(data) for path,data in p['bundle']['files'].items()}
            bundle=dict(manifest=json.loads(z.read(prefix+'manifest.json')),files=files)
            validate_retained_bundle(bundle,p['request'],p['frozen'])
            config=json.loads(files['configuration.json']);model=json.loads(files['model.json'])
            assert (bundle['manifest']['schema_version'],config['schema_version'],model['schema_version'])==('4','3','2')
            assert config==p['frozen']['configuration'] and model==p['frozen']['model_snapshot']
            assert json.loads(files['evidence/index.json'])==config['evidence_snapshots']
        child=env['child']['case']['frozen']['configuration']
        expected_context=dict(description='Edited engineering question\n\nRetained paragraph.',
            boundary=env['source']['case']['frozen']['configuration']['context_snapshot']['boundary'],
            notes=['A configuration-specific qualification', ''])
        assert child['context_snapshot']==expected_context
        assert child['context_snapshot']!=env['source']['case']['frozen']['configuration']['context_snapshot']
        restarted=Store(env['store'].path)
        history=History(restarted).read(env['actor'],env['sid'],env['selected'])
        seed=ModifiedRuns(restarted).seed(env['actor'],env['sid'],env['selected'])
        assert history['configuration']['context_snapshot']==expected_context
        assert seed['source_context']==expected_context
        assert seed['configuration']['notes']==expected_context['notes']
        assert seed['configuration']['derivation']['source_configuration_digest']==child['digest']
        assert '/context_snapshot/description' in {change['path'] for change in child['derivation']['changes']}
        old=env['source']['case']['frozen']['configuration']['evidence_snapshots'][0]
        new=next(e for e in child['evidence_snapshots'] if e['parent_evidence_version_id'])
        assert new['parent_evidence_version_id']==old['evidence_version_id']
        assert new['recorded_context']==old['recorded_context']
        assert child['general_context_evidence_version_ids']==[old['evidence_version_id']]
        assert {l['relation'] for l in child['assumptions'][0]['evidence_links']}=={'context','challenges'}
        path=SCOPE.root/'evidence/ae-computations.aiida';path.write_bytes(z.read('computations.aiida'))
        native_zip,native_expanded,native_count=zip_entries(path.read_bytes(),LIMITS['native_archive_bytes'],metadata=True)
        native_zip.close()
        expanded=native_expanded+sum(i.file_size for i in z.infolist() if i.filename!='computations.aiida')
        paths=native_count+len(z.infolist())
        assert expanded<=33554432 and paths<=4096
    records,roles,preflight,_=s._collect(env['actor'],env['sid'],[env['selected']])
    with ArchiveFormatSqlZip().open(path,'r') as archive:
        backend=archive.get_backend()
        Export(env['native'],preflight).inspect(backend)
        for rid in env['originals']:
            p=payload(env,rid)
            node=orm.QueryBuilder(backend=backend).append(orm.CalcJobNode,filters={'uuid':p['history']['association']['process_uuid']},project='*').one()[0]
            assert retained_bundle(node.inputs.frozen_bundle.base.repository,p['request'])['files']=={key:base64.b64decode(value) for key,value in p['bundle']['files'].items()}
            retained_context=json.loads(node.inputs.frozen_bundle.base.repository.get_object_content('configuration.json'))['context_snapshot']
            assert retained_context==p['frozen']['configuration']['context_snapshot']
    proof=offline_roundtrip(path,SCOPE,BACKEND,expected_processes={payload(env,rid)['history']['association']['process_uuid'] for rid in env['originals']})
    assert proof['origin_store_uuid']!=proof['import_store_uuid']
    proof.update(package_sha256=sha(raw),expanded_bytes=expanded,logical_paths=paths,manifest=manifest,originals_unchanged=True,forbidden_calls=0,
        edited_context=expected_context,edited_configuration_digest=child['digest'],restart_and_next_seed_exact=True)
    (SCOPE.root/'evidence/ae-offline-proof.json').write_text(json.dumps(proof,indent=2)+'\n')


def test_context_only_retains_exact_closure_and_checks_combined_bounds(exported):
    env=exported;s=env['service']
    records,_,preflight,_=s._collect(env['actor'],env['sid'],[env['selected']])
    rid=env['source']['rid'];context={rid:records[rid]};roles={rid:'derivation_context_only'}
    files,mapping,inventory,_=s._package(context,roles,preflight,b'',0,0)
    prefix='hyprn-mvp/derivations/'+rid+'/'
    config=records[rid][0]['configuration']
    assert files[prefix+'configuration.json'][1]==canonical(config)
    assert files[prefix+'evidence.json'][1]==canonical(config['evidence_snapshots'])
    assert files[prefix+'model.json'][1]==canonical(records[rid][0]['model_snapshot'])
    assert mapping[0]['process_uuid'] is None and mapping[0]['bundle_digest'] is None
    broken=deepcopy(context);broken[rid][0]['configuration']['evidence_snapshots']=[]
    with pytest.raises(ValueError):s._package(broken,roles,preflight,b'',0,0)
    for expanded,count in ((LIMITS['expanded_bytes'],0),(0,LIMITS['logical_paths'])):
        with pytest.raises(DomainError) as error:s._package(context,roles,preflight,b'',expanded,count)
        assert error.value.code=='limit_exceeded'


@pytest.mark.parametrize('field',['relationship','title','label','parent','missing','general','owner'])
def test_tampered_retained_nested_bytes_refused_at_every_operation(exported,ready_record,field):
    env=exported;s=env['service'];rid=env['source']['rid'];original=payload(env,rid);changed=deepcopy(original)
    path='model.json' if field=='owner' else 'configuration.json'
    value=json.loads(base64.b64decode(changed['bundle']['files'][path]))
    if field=='relationship':value['assumptions'][0]['evidence_links'][0]['relation']='context'
    elif field=='title':value['evidence_snapshots'][0]['title']='Changed title'
    elif field=='label':value['evidence_snapshots'][0]['recorded_context']['label']='Changed label'
    elif field=='parent':value['evidence_snapshots'][0]['parent_evidence_version_id']=uid()
    elif field=='missing':value['evidence_snapshots']=[]
    elif field=='general':value['general_context_evidence_version_ids']=[]
    else:value['assumptions'][1]['owner']['instance_id']=uid()
    changed['bundle']['files'][path]=base64.b64encode(canonical(value)).decode()
    def write(data):
        with env['store'].connection(write=True) as db:db.execute('UPDATE outbox SET payload=? WHERE run_id=?',(json.dumps(data),rid))
    try:
        write(changed)
        for action in (lambda:s.enqueue_preview(env['actor'],env['sid'],dict(command_id=uid(),selected_run_ids=[env['selected']])),
            lambda:s.enqueue_create(env['actor'],env['sid'],dict(ready_record['body'],command_id=uid())),
            lambda:s.enqueue_create(env['actor'],env['sid'],ready_record['body']),
            lambda:s.status(env['actor'],env['sid'],ready_record['request']['request_id']),
            lambda:s.download(env['actor'],env['sid'],ready_record['request']['request_id'])):
            with pytest.raises(DomainError):action()
    finally:write(original)


@pytest.mark.parametrize('mode',['foreign_ancestor','revoked'])
def test_authorization_rechecked_for_all_export_operations(exported,ready_record,mode):
    env=exported;s=env['service'];rid=env['source']['rid'];sid=env['sid'];actor=env['actor']
    foreign=uid()
    with env['store'].connection(write=True) as db:
        if mode=='foreign_ancestor':
            db.execute('INSERT INTO studies VALUES(?,?,?,?,?)',(foreign,uid(),'Foreign','',''))
            db.execute('UPDATE run_associations SET study_id=? WHERE run_id=?',(foreign,rid))
        else:db.execute('DELETE FROM memberships WHERE study_id=? AND actor_id=?',(sid,actor))
    try:
        for action in (lambda:s.enqueue_preview(actor,sid,dict(command_id=uid(),selected_run_ids=[env['selected']])),
            lambda:s.enqueue_create(actor,sid,dict(ready_record['body'],command_id=uid())),
            lambda:s.enqueue_create(actor,sid,ready_record['body']),
            lambda:s.status(actor,sid,ready_record['request']['request_id']),
            lambda:s.download(actor,sid,ready_record['request']['request_id'])):
            with pytest.raises(DomainError):action()
    finally:
        with env['store'].connection(write=True) as db:
            if mode=='foreign_ancestor':
                db.execute('UPDATE run_associations SET study_id=? WHERE run_id=?',(sid,rid));db.execute('DELETE FROM studies WHERE study_id=?',(foreign,))
            else:db.execute('INSERT INTO memberships VALUES(?,?,?)',(sid,actor,'owner'))


@pytest.mark.parametrize('kind',['relationship','label','missing'])
def test_offline_native_reader_rejects_changed_nested_content(exported,tmp_path,kind):
    env=exported;p=payload(env);files={path:base64.b64decode(value) for path,value in p['bundle']['files'].items()}
    files['manifest.json']=canonical(p['bundle']['manifest'])
    if kind=='missing':files.pop('evidence/index.json')
    else:
        config=json.loads(files['configuration.json'])
        if kind=='relationship':config['assumptions'][0]['evidence_links'][0]['relation']='context'
        else:config['evidence_snapshots'][0]['recorded_context']['label']='Replaced label'
        files['configuration.json']=canonical(config)
    folder=orm.FolderData(backend=BACKEND)
    for path,data in files.items():folder.base.repository.put_object_from_filelike(io.BytesIO(data),path)
    with pytest.raises((ValueError,FileNotFoundError)):retained_bundle(folder.base.repository,p['request'])


@pytest.mark.parametrize('kind',['expanded','paths','symlink','traversal'])
def test_archive_limits_and_unsafe_paths_remain_closed(exported,tmp_path,kind):
    assert LIMITS['expanded_bytes']==33554432 and LIMITS['logical_paths']==4096
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED) as z:
        if kind=='expanded':
            for index in range(3):z.writestr(str(index),b'x'*(12*1024*1024))
        elif kind=='paths':
            for index in range(4097):z.writestr(str(index),b'')
        else:
            entry=zipfile.ZipInfo('../escape' if kind=='traversal' else 'link')
            entry.external_attr=((stat.S_IFLNK if kind=='symlink' else stat.S_IFREG)|0o600)<<16
            z.writestr(entry,b'outside')
    raw=stream.getvalue()
    with pytest.raises((ValueError,DomainError)):zip_entries(raw,LIMITS['wrapper_bytes'])
    path=tmp_path/'unsafe.aiida';path.write_bytes(raw)
    with pytest.raises(ValueError):archive_bounds(path)
