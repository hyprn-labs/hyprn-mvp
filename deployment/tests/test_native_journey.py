"""Fresh Addition A checkpoint; synthetic browser bytes are never native proof."""
# P2 live-runtime fence (deployment/tests/live_fence.py): refuses live roots, live ports, live docker names, live entry points and foreign signals.
import sys as _fence_sys
from pathlib import Path as _FencePath
if str(_FencePath(__file__).resolve().parent) not in _fence_sys.path:
    _fence_sys.path.append(str(_FencePath(__file__).resolve().parent))
import live_fence  # noqa: E402
live_runtime_fence = live_fence.pytest_fixture('baseline')
import json
from pathlib import Path
import pytest


def test_isolated_runtime_root_refusals(tmp_path):
    from hyprn_mvp_integration import launcher
    from checks import PROJECTION_SCOPE
    for root in [launcher.ROOT, Path('/private/tmp'), tmp_path, Path('relative')]:
        with pytest.raises(ValueError): launcher.fixture_runtime_root(root)
    assert launcher.fixture_runtime_root(PROJECTION_SCOPE.root)==PROJECTION_SCOPE.root
    import subprocess
    import scoped_fixture as guard
    marker=PROJECTION_SCOPE.root/'scope.json';original=marker.read_bytes()
    try:
        changed=json.loads(original);changed['store_uuid']=changed['profile_uuid'];marker.write_text(json.dumps(changed))
        with pytest.raises(ValueError):launcher.fixture_runtime_root(PROJECTION_SCOPE.root)
    finally:marker.write_bytes(original)
    link=tmp_path/'linked';link.symlink_to(PROJECTION_SCOPE.root,target_is_directory=True)
    with pytest.raises(ValueError):launcher.fixture_runtime_root(link)
    # This tree's launcher entry refuses any runtime root outside the scoped convention. The
    # execution store itself is never handed to a child: the fence refuses that launch.
    entry=str(Path(guard.__file__).resolve().with_name('scoped_fixture_launcher.py'))
    assert live_fence.decide('subprocess.Popen',(None,[guard.APPROVED_PYTHON,'-B',entry,'--runtime-root',str(launcher.ROOT)],None,None),'baseline')
    command=[guard.APPROVED_PYTHON,'-B',entry,'--runtime-root',str(tmp_path/'execution'),'never','0'*64]
    result=subprocess.run(command,env=guard.clean_environment(PROJECTION_SCOPE),capture_output=True,text=True)
    assert result.returncode!=0 and 'Explicit isolated runtime root required' in result.stderr
    (PROJECTION_SCOPE.root/'evidence/rejected-live-root.json').write_text(json.dumps(dict(command=command,exit=result.returncode,stderr=result.stderr)))


def test_addition_a(monkeypatch):
    addition_a(monkeypatch)


def addition_a(monkeypatch, *, mixed=False):
    import base64, copy, hashlib, sys
    from checks import PROJECTION_SCOPE as scope, NATIVE_BACKEND as backend
    import scoped_fixture as guard
    from hyprn_mvp_integration import launcher
    from hyprn_mvp_integration.calculation import NativeExecution
    from hyprn_mvp_app.store import Store, uid, digest, canonical
    from hyprn_mvp_app.execution import Submissions, assemble_bundle
    from hyprn_mvp_app.history import projection, History
    from hyprn_mvp_app.result_bindings import ResultBindings
    from hyprn_mvp_app.scientific_configuration import project_scientific_configuration
    from aiida import orm
    from aiida.common.links import LinkType
    repo=Path(__file__).resolve().parents[2]
    sys.path[:0]=[str(repo/'modeling/tests'),str(repo/'contracts/tests')]
    from test_resolved_configuration import harness, native as generate
    from combined_fixture import model4_authoring
    # Refuse unsafe roots before build, native node allocation or execution.
    for unsafe in (launcher.ROOT,Path('/private/tmp'),scope.root/'tmp'):
        with pytest.raises(ValueError):launcher.fixture_runtime_root(unsafe)
    code=guard.prepare_worker_fixture(scope,backend)
    native=NativeExecution(backend=backend,root=scope.root)
    assert native.require_attestation()['passed']
    store=Store(scope.root/'artifacts/journey.sqlite');actor=uid()
    study=store.create_study(actor,uid(),'Fresh sizing and linked comparison');sid=study['study_id']
    source=b"outputs['y'] = inputs['a'] * 1000\noutputs['z'] = inputs['b'] * 1000\noutputs['total'] = (inputs['a'] + inputs['b'] + inputs['c'] + inputs['d']) * 1000\n"
    # The Sizing model is authored as a Model4 revision with typed unit declarations.
    ruby,edits=model4_authoring(source)
    ruby=ruby.replace("'study_id'=>SecureRandom.uuid", "'study_id'=>'"+sid+"'",1)
    # Replay public authoring commands with fixture-scoped stable IDs when B
    # later asks the real private generator about this exact immutable model.
    namespace=hashlib.sha256(str(scope.root).encode()).hexdigest()
    fixed="require 'securerandom'\nfixture_counter=0\nSecureRandom.define_singleton_method(:uuid) { fixture_counter+=1; h=Digest::SHA256.hexdigest('"+namespace+"'+fixture_counter.to_s); h[0,8]+'-'+h[8,4]+'-4'+h[13,3]+'-8'+h[17,3]+'-'+h[20,12] }\n"
    ruby=ruby.replace("scope={'study_id'",fixed+"scope={'study_id'",1)
    native_harness=harness.__wrapped__()
    result=generate(native_harness,ruby+'''
cases=[]
[[0.002,0.003,0.001,0.001],[0.005,0.007,0.001,0.001],[2,3,2,5]].each_with_index do |values,index|
 cfg=Marshal.load(Marshal.dump(cfg));cfg['schema_version']='5';cfg.delete('criteria');cfg['required_capabilities']=m['required_capabilities'].dup
 cfg['configuration_id']=SecureRandom.uuid;cfg['configuration_revision_id']=SecureRandom.uuid
 cfg['name']=index==2 ? 'Linked comparison' : 'Sizing '+index.to_s
 cfg['context_snapshot']={'description'=>'','boundary'=>'','notes'=>[]}
 cfg['inputs'].each_with_index { |input,n| input['value']=values[n];input['units']=index==2 ? 'm' : 'km' }
 cfg['digest']=ModelingContract.digest(cfg.except('digest'))
 candidate=cfg.except('digest','configuration_id','configuration_revision_id','parent_revision_id')
 proof=c.route('POST',path+'/configuration-compatibility',{}, {'model_revision_id'=>m['model_revision_id'],'configuration_candidate'=>candidate})[1]['data']
 prepared=c.route('POST',path+'/prepare-execution',{}, {'command_id'=>SecureRandom.uuid,'model_revision_id'=>m['model_revision_id'],'configuration_snapshot'=>cfg,'configuration_digest'=>cfg['digest']})[1]['data']
 stored=ModelingRevision.find_by(public_id:prepared['preparation_id']).payload['bytes']
 files=prepared['files'].to_h { |f| [f['path'],stored.fetch(f['file_id'])['bytes']] }
 cases << {'configuration'=>cfg,'proof'=>proof,'prepared'=>prepared,'files'=>files}
end
puts 'PROJECTION_RESULT='+JSON.generate({'model'=>m,'cases'=>cases})
''')
    model=result['model'];sources=[];snapshots={};prestore=[]
    def snapshot(value):
        if isinstance(value,bytes):return dict(sha256=hashlib.sha256(value).hexdigest(),size=len(value))
        if isinstance(value,dict):return {k:snapshot(v) for k,v in value.items()}
        if isinstance(value,list):return [snapshot(v) for v in value]
        return value
    original_store=orm.CalcJobNode.store
    def inspect_store(node,*args,**kwargs):
        links=node.base.links.get_incoming(link_type=LinkType.INPUT_CALC).all()
        upstream=[link for link in links if link.link_label.startswith('upstream_results__')]
        if upstream:
            assert not node.is_stored
            prestore.append(sorted((link.link_label,link.node.uuid) for link in upstream))
        return original_store(node,*args,**kwargs)
    monkeypatch.setattr(orm.CalcJobNode,'store',inspect_store)
    for index,case in enumerate(result['cases']):
        config=copy.deepcopy(case['configuration']);config.pop('digest')
        # The private configuration 5 is the projection of this application revision 6.
        config.update(schema_version='6',context_source=dict(kind='current_study',expected_study_revision=study['revision']),derivation=None)
        for item in config['inputs']:item['result_binding']=None
        if index==2:
            for n,(item,(source_index,symbol)) in enumerate(zip(config['inputs'],[(0,'y'),(0,'z'),(0,'y'),(1,'y')])):
                if mixed and n==2:continue
                rid,outputs=sources[source_index]
                resolved=ResultBindings(store).resolve(actor,sid,dict(source_run_id=rid,source_output=outputs[symbol]['target'],expected_results_digest=outputs['digest']))
                interpretation=next(i['conversion'] for i in case['proof']['input_interpretations'] if i['target']==item['target'])
                item['value']=resolved['value'];item['units']=resolved['units']
                item['result_binding']={k:resolved[k] for k in ('source_run_id','source_output','results_digest','source_configuration_digest','labels')}
                item['result_binding'].update(original_value=resolved['value'],original_units=resolved['units'],conversion=interpretation)
            config['required_capabilities'].append('result_linked_inputs/1')
        # The public revision 6 adds the assumption fields its private configuration 5 drops.
        config.update(assumptions=[],general_context_evidence_version_ids=[])
        config['required_capabilities'].append('configuration_assumptions/1')
        config['digest']=digest(config)
        assert project_scientific_configuration(config)==case['configuration']
        frozen=dict(schema_version='9',configuration=config,model_snapshot=model,study_revision=study['revision'])
        with store.connection(write=True) as db:
            db.execute('INSERT INTO configurations VALUES(?,?,?,?)',(config['configuration_revision_id'],config['configuration_id'],sid,json.dumps(frozen)))
            db.execute('INSERT INTO configuration_families VALUES(?,?,?)',(config['configuration_id'],sid,config['configuration_revision_id']))
        submission=Submissions(store,None,None).submit(actor,sid,dict(command_id=uid(),configuration_revision_id=config['configuration_revision_id']))
        rid=submission['run_id'];deps=ResultBindings(store).dependencies(actor,sid,config,native)
        files={p:base64.b64decode(raw,validate=True) for p,raw in case['files'].items()}
        bundle=assemble_bundle(rid,case['prepared'],files,frozen,native.bundle_runtime(),deps)
        request=dict(run_id=rid,scope=sid,command_id=submission['command_id'],payload_digest=store.receipt(actor,sid,'run',submission['command_id'])['payload_digest'],bundle_digest=bundle['manifest']['bundle_digest'])
        before_count=orm.QueryBuilder(backend=backend).append(orm.CalcJobNode).count()
        if index==0:
            original_path=code.filepath_executable
            # Wrong code is rejected before process storage, even with valid attestation.
            monkeypatch.setattr(type(code),'filepath_executable',property(lambda _:Path('/never-execute')))
            with pytest.raises(ValueError,match='Installed code'):native.launch(bundle,request)
            monkeypatch.undo();monkeypatch.setattr(orm.CalcJobNode,'store',inspect_store)
            assert orm.QueryBuilder(backend=backend).append(orm.CalcJobNode).count()==before_count
        response=native.launch(bundle,request)
        record=native.read_record(request,{k:response[k] for k in ('store_uuid','process_uuid')})
        assert record['results']['execution']['state']=='finished',record
        payload=dict(actor=actor,frozen=frozen,request=request,bundle=dict(manifest=bundle['manifest'],files={p:base64.b64encode(raw).decode() for p,raw in bundle['files'].items()}))
        association={k:response[k] for k in ('store_uuid','process_uuid')}
        payload['history']=projection(payload,record,association)
        with store.connection(write=True) as db:
            db.execute('UPDATE run_associations SET store_uuid=?,process_uuid=? WHERE run_id=?',(*association.values(),rid))
            db.execute("UPDATE outbox SET state='recorded',payload=? WHERE run_id=?",(json.dumps(payload),rid))
        outputs={next(p['code_symbol'] for p in model['ports'] if p['port_id']==o['target']['port_id']):o for o in record['results']['outputs']}
        outputs['digest']=digest(record['results'])
        if index<2:
            sources.append((rid,outputs));snapshots[rid]=canonical(snapshot(record))
        else:
            assert outputs['y']['value']==pytest.approx(2) and outputs['z']['value']==pytest.approx(3)
            assert outputs['total']['value']==pytest.approx(12)
            assert len(deps['sources'])==2 and len(deps['mappings'])==(3 if mixed else 4)
            expected=sorted(('upstream_results__'+s['label'],s['result_uuid']) for s in deps['sources'])
            assert prestore==[expected]
            node=orm.load_node(response['process_uuid'])
            actual=sorted((l.link_label,l.node.uuid) for l in node.base.links.get_incoming(link_type=LinkType.INPUT_CALC).all() if l.link_label.startswith('upstream_results__'))
            assert actual==expected
            for source_id,_ in sources:
                with store.connection() as db:
                    row=db.execute('SELECT o.payload,r.process_uuid FROM outbox o JOIN run_associations r USING(run_id) WHERE run_id=?',(source_id,)).fetchone()
                assert canonical(snapshot(native.read_record(json.loads(row['payload'])['request'],dict(store_uuid=native.store_uuid,process_uuid=row['process_uuid']))))==snapshots[source_id]
            proof=dict(actual_restricted_worker=True,originals_unchanged=True,source_runs=2,native_input_links_before_store=prestore,converted_destination_observed={k:o['value'] for k,o in outputs.items() if k!='digest'},two_outputs=True,fanout=not mixed,dependencies=deps,run_id=rid,process_uuid=response['process_uuid'])
            (scope.root/'evidence/addition-a.json').write_text(json.dumps(proof,indent=2)+'\n')
    return locals()


def test_addition_b(monkeypatch):
    addition_b(monkeypatch)


def addition_b(monkeypatch):
    """Implemented authoring services -> native generator -> actual new worker."""
    import base64, copy, hashlib
    from concurrent.futures import ThreadPoolExecutor
    from hyprn_mvp_app.configuration import Configurations
    from hyprn_mvp_app.modeling import Coordinator
    from hyprn_mvp_app.modified_runs import ModifiedRuns
    from hyprn_mvp_app.execution import Submissions
    from hyprn_mvp_app.readiness import ObservationPublisher
    from hyprn_mvp_app.store import canonical, digest, uid, DomainError
    from hyprn_mvp_app.history import History
    from hyprn_mvp_app.scientific_configuration import project_scientific_configuration
    from hyprn_mvp_integration import launcher
    from aiida import orm
    from aiida.common.links import LinkType
    env=addition_a(monkeypatch,mixed=True)
    scope,store,actor,sid,native=(env[k] for k in ('scope','store','actor','sid','native'))
    source_id=env['rid'];source_config=copy.deepcopy(env['config'])
    def payload(rid):
        from hyprn_mvp_app.history import run_association
        with store.connection() as db:return json.loads(run_association(db,rid)['payload'])
    original_ids=[rid for rid,_ in env['sources']]+[source_id]
    originals={rid:canonical(payload(rid)) for rid in original_ids}
    native_originals={rid:canonical(env['snapshot'](native.read_record(payload(rid)['request'],payload(rid)['history']['association']))) for rid in original_ids}

    class PrivateNative:
        """Test transport: actual private route calls in fresh tmpfs native stores.

        Replays the identical fixture authoring commands; never substitutes a
        generated graph/program or implements unit conversion in the test.
        """
        supports_units=staticmethod(Coordinator.supports_units)
        supports_quantities=staticmethod(Coordinator.supports_quantities)
        def __init__(self):
            self.calls=[];self.capabilities=None
            # Configuration3 previews read the private capability advertisement first.
            self.model=self
        def call(self,who,study,method,path,**kwargs):
            assert (who,study,method,path)==(actor,sid,'GET','/capabilities')
            self.calls.append(path)
            if self.capabilities is None:
                self.capabilities=env['generate'](env['native_harness'],env['ruby']+
                    "\nputs 'PROJECTION_RESULT='+JSON.generate(c.route('GET','/capabilities',{},nil)[1]['data'])\n")
            return 200,{'data':copy.deepcopy(self.capabilities)}
        def request(self,path,body):
            self.calls.append(path)
            assert path.endswith(('/configuration-compatibility','/prepare-execution'))
            encoded=base64.b64encode(json.dumps(body).encode()).decode()
            suffix="\nraise 'Retained model changed' unless m['digest']=='"+env['model']['digest']+"'\n"
            suffix+="answer=c.route('POST',"+json.dumps(path)+",{},JSON.parse(Base64.strict_decode64('"+encoded+"')))[1]['data']\n"
            if path.endswith('/prepare-execution'):
                suffix+="stored=ModelingRevision.find_by(public_id:answer['preparation_id']).payload['bytes']; files=answer['files'].to_h { |f| [f['path'],stored.fetch(f['file_id'])['bytes']] }; answer={'prepared'=>answer,'files'=>files}\n"
            suffix+="puts 'PROJECTION_RESULT='+JSON.generate(answer)\n"
            return env['generate'](env['native_harness'],env['ruby']+suffix)
        def read(self,who,study,mid,path,**kwargs):
            assert (who,study,mid)==(actor,sid,env['model']['model_id']) and kwargs['method']=='POST'
            return {'data':self.request('/models/'+mid+path,kwargs['body'])}
        def prepare(self,who,study,command,frozen):
            assert (who,study)==(actor,sid)
            scientific=project_scientific_configuration(frozen['configuration'])
            answer=self.request('/models/'+scientific['model_id']+'/prepare-execution',dict(command_id=command,
                model_revision_id=scientific['model_revision_id'],configuration_snapshot=scientific,configuration_digest=scientific['digest']))
            return answer['prepared'],{p:base64.b64decode(b,validate=True) for p,b in answer['files'].items()}
    coordinator=PrivateNative();configurations=Configurations(store,coordinator)
    with store.connection(write=True) as db:db.execute('INSERT INTO model_associations VALUES(?,?,?)',(sid,env['model']['model_id'],uid()))
    class PublisherBoundary:
        # Existing private bridge normalizes the attestation document to true;
        # keep that shape at this in-process test seam after the real check.
        def require_attestation(self):
            assert native.require_attestation()['passed'] is True
            return True
        def bundle_runtime(self):return native.bundle_runtime()
    publisher=ObservationPublisher(store,PublisherBoundary());publisher.refresh()
    before=store.path.read_bytes();seed=ModifiedRuns(store).seed(actor,sid,source_id)
    assert store.path.read_bytes()==before and not coordinator.calls
    assert seed['runtime_comparison']['state']=='same'
    request=seed['configuration'];request['name']='Independent modified comparison'
    literal=next(i for i in request['inputs'] if i['kind']=='literal')
    assert literal['value']==2 and literal['units']=='m'
    literal['value']=4
    preview,_,_=configurations.preview(actor,sid,request)
    assert preview['runtime_comparison']['state']=='same'
    assert any(c['path']=='/inputs/2/value' for c in preview['changes'])
    command=dict(command_id=uid(),configuration_id=None,expected_revision=None,configuration=request,expected_preview_digest=preview['candidate_digest'])
    with ThreadPoolExecutor(max_workers=2) as pool:saved=list(pool.map(lambda _:configurations.commit(actor,sid,command),range(2)))
    assert saved[0]==saved[1];frozen=saved[0];config=frozen['configuration']
    assert config['configuration_id']!=source_config['configuration_id'] and config['configuration_revision_id']!=source_config['configuration_revision_id'] and config['parent_revision_id'] is None
    assert config['derivation']['source_run_id']==source_id
    assert config['context_snapshot']==source_config['context_snapshot'] and config['evidence_snapshots']==source_config['evidence_snapshots']
    assert [i['result_binding'] for i in config['inputs']]==[i['result_binding'] for i in source_config['inputs']]
    service=Submissions(store,coordinator.prepare,native)
    submit=dict(command_id=uid(),configuration_revision_id=config['configuration_revision_id'])
    with ThreadPoolExecutor(max_workers=2) as pool:runs=list(pool.map(lambda _:service.submit(actor,sid,submit),range(2)))
    assert runs[0]==runs[1];rid=runs[0]['run_id']
    assert rid not in original_ids and submit['command_id']!=env['submission']['command_id']
    old_runtime=copy.deepcopy(native.bundle_runtime()['runtime'])
    # An actual changed image, same audited code/dependencies/policy. The helper
    # builds only a fixture label layer and reattests before preparation.
    import scoped_fixture as guard
    guard.change_worker_fixture_identity(scope)
    current=native.bundle_runtime()['runtime'];assert current!=old_runtime
    service.dispatch(rid,prepare_only=True)
    actual=service.read(actor,sid,rid)['runtime_comparison']
    assert actual==dict(source=old_runtime,current=current,state='different',basis='prepared_bundle',observed_at=None,expires_at=None)
    assert payload(rid)['bundle']['manifest']['runtime']==current
    before_count=orm.QueryBuilder(backend=env['backend']).append(orm.CalcJobNode).count()
    service.dispatch(rid)
    public=service.read(actor,sid,rid);assert public['runtime_comparison']==actual
    history=History(store).read(actor,sid,rid)
    assert history['results']['execution']['state']=='finished',public
    values={next(p['code_symbol'] for p in env['model']['ports'] if p['port_id']==o['target']['port_id']):o['value'] for o in history['results']['outputs']}
    assert values=={'y':2,'z':3,'total':14}
    with store.connection() as db:association=dict(db.execute('SELECT store_uuid,process_uuid FROM run_associations WHERE run_id=?',(rid,)).fetchone())
    node=orm.load_node(association['process_uuid']);parent=orm.load_node(env['response']['process_uuid'])
    assert node.uuid!=parent.uuid and orm.QueryBuilder(backend=env['backend']).append(orm.CalcJobNode).count()==before_count+1
    assert node.base.caching.is_created_from_cache is False
    links=node.base.links.get_incoming().all()
    deps=json.loads(base64.b64decode(payload(rid)['bundle']['files']['result-dependencies.json']))
    expected=sorted(('upstream_results__'+s['label'],s['result_uuid']) for s in deps['sources'])
    assert sorted((l.link_label,l.node.uuid) for l in links if l.link_label.startswith('upstream_results__'))==expected
    assert len(expected)==2 and len(deps['mappings'])==3
    assert all(l.node.uuid!=parent.uuid and l.node.uuid!=parent.outputs.results.uuid for l in links)
    assert not node.base.links.get_incoming(link_type=LinkType.CALL_CALC).all()
    assert env['prestore'][-1]==expected
    # A separate fresh uncertain command is not the derivation parent and must
    # remain uncertain under explicit reconciliation; never creates a process.
    uncertain=service.submit(actor,sid,dict(command_id=uid(),configuration_revision_id=source_config['configuration_revision_id']))
    service.dispatch(uncertain['run_id'],prepare_only=True)
    with store.connection(write=True) as db:db.execute("UPDATE outbox SET state='uncertain' WHERE run_id=?",(uncertain['run_id'],))
    count=orm.QueryBuilder(backend=env['backend']).append(orm.CalcJobNode).count()
    service.dispatch(uncertain['run_id'])
    with pytest.raises(DomainError):ModifiedRuns(store).seed(actor,sid,uncertain['run_id'])
    assert service.read(actor,sid,uncertain['run_id'])['state']=='uncertain'
    assert orm.QueryBuilder(backend=env['backend']).append(orm.CalcJobNode).count()==count
    assert configurations.commit(actor,sid,command)==frozen and service.submit(actor,sid,submit)==public
    for old in original_ids:
        assert canonical(payload(old))==originals[old]
        assert canonical(env['snapshot'](native.read_record(payload(old)['request'],payload(old)['history']['association'])))==native_originals[old]
    proof=dict(actual_restricted_worker=True,source_run=source_id,run_id=rid,process_uuid=node.uuid,configuration_id=config['configuration_id'],configuration_revision_id=config['configuration_revision_id'],save_command=command['command_id'],submit_command=submit['command_id'],source_runtime=old_runtime,actual_runtime_comparison=actual,outputs=values,dependencies=deps,prestore=env['prestore'],originals_unchanged=True,cache_used=False,derivation_native_links=False,concurrent_save_submit_single_outcome=True,uncertain_not_resumed=True,private_calls=coordinator.calls)
    (scope.root/'evidence/addition-b.json').write_text(json.dumps(proof,indent=2)+'\n')
    return locals()


def test_addition_c(monkeypatch):
    """Actual A+B computations -> bounded package -> distinct offline store."""
    import base64, hashlib, io, zipfile, sys
    from hyprn_mvp_app.store import Store, uid, canonical
    from hyprn_mvp_app.computational_export import records_for_store
    from hyprn_mvp_integration.calculation import NativeExecution
    from hyprn_mvp_integration import launcher
    from aiida import orm
    from aiida.transports.plugins.local import LocalTransport
    from test_computational_archive import offline_roundtrip
    b=addition_b(monkeypatch);env=b['env'];scope=b['scope'];store=b['store']
    actor,sid,rid,native=(b[k] for k in ('actor','sid','rid','native'))
    ids=[*b['original_ids'],rid]
    originals={key:canonical(b['payload'](key)) for key in ids}
    native_originals={key:canonical(env['snapshot'](native.read_record(b['payload'](key)['request'],b['payload'](key)['history']['association']))) for key in ids}
    with store.connection() as db:
        rows={table:[tuple(r) for r in db.execute('SELECT * FROM '+table)] for table in ('outbox','run_associations','configurations','configuration_families')}
    # The private fixture server has already exited after preparation. Any new
    # model call or execution authority during export/inspection must fail.
    counters={}
    def deny(name):
        def forbidden(*args,**kwargs):
            counters[name]=counters.get(name,0)+1
            raise AssertionError('Offline archive reached '+name)
        return forbidden
    original_read=native.read_record
    original_inspect=NativeExecution.inspect
    for name in ('launch','inspect','require_attestation','bundle_runtime','read_record'):
        monkeypatch.setattr(NativeExecution,name,deny(name))
    monkeypatch.setattr(type(b['coordinator']),'request',deny('model'))
    monkeypatch.setattr(launcher,'isolated',deny('worker'))
    monkeypatch.setattr(orm.CalcJobNode,'process_class',property(deny('process_class')))
    monkeypatch.setattr(orm.CalcJobNode,'get_builder_restart',deny('restart'))
    monkeypatch.setattr(LocalTransport,'open',deny('transport'))
    # Native generation names are known from the actual frozen artifact. Block
    # candidate/generated code imports while permitting pinned library imports.
    import importlib.abc
    candidate_names={Path(p).stem for p in env['files'] if p.endswith('.py') and not p.startswith('provenance/')}
    candidate_names.update({'base','impl'})
    assert not candidate_names.intersection(sys.modules)
    class RejectCandidate(importlib.abc.MetaPathFinder):
        def find_spec(self,fullname,path=None,target=None):
            if fullname.split('.')[0] in candidate_names:deny('candidate_import')()
    finder=RejectCandidate();sys.meta_path.insert(0,finder)
    try:
        service=records_for_store(store)
        pending=service.enqueue_preview(actor,sid,dict(command_id=uid(),selected_run_ids=[rid]))
        assert service.process_one(native.archive_record,request_id=pending['request_id'])
        preview=service.status(actor,sid,pending['request_id'])
        assert preview['state']=='reviewable',preview
        pending=service.enqueue_create(actor,sid,dict(command_id=uid(),preview_id=preview['request_id'],expected_preview_digest=preview['preview']['preview_digest']))
        assert service.process_one(native.archive_record,request_id=pending['request_id'])
        ready=service.status(actor,sid,pending['request_id']);assert ready['state']=='ready',ready
        raw=records_for_store(Store(store.path)).download(actor,sid,pending['request_id'])
        assert hashlib.sha256(raw).hexdigest()==ready['download']['sha256']
        (scope.root/'evidence/addition-c.zip').write_bytes(raw)
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            manifest=json.loads(archive.read('manifest.json'))
            assert manifest['selected_run_ids']==[rid]
            ancestors=sorted(key for key,_ in env['sources'])
            assert sorted(manifest['computational_run_ids'])==sorted([rid,*ancestors])
            assert manifest['derivation_context_run_ids']==[b['source_id']]
            assert set(archive.namelist())=={'manifest.json'}|{item['path'] for item in manifest['inventory']}
            for item in manifest['inventory']:
                content=archive.read(item['path']);assert len(content)==item['size'] and hashlib.sha256(content).hexdigest()==item['sha256']
            for key in [rid,*ancestors]:
                for path,content in b['payload'](key)['bundle']['files'].items():
                    assert archive.read('hyprn-mvp/runs/'+key+'/bundle/'+path)==base64.b64decode(content)
            assert not any(path.startswith('hyprn-mvp/runs/'+b['source_id']+'/') for path in archive.namelist())
            path=scope.root/'evidence/computations.aiida';path.write_bytes(archive.read('computations.aiida'))
        proof=offline_roundtrip(path,scope,native.backend,expected_processes={b['payload'](key)['history']['association']['process_uuid'] for key in [rid,*ancestors]})
        assert b['parent'].uuid not in proof['node_uuids']
        assert counters=={}
    finally:sys.meta_path.remove(finder)
    # The forbidden-call assertion above covers export/import. Restore the
    # read-only inspector used internally by the final baseline comparison.
    monkeypatch.setattr(NativeExecution,'inspect',original_inspect)
    with store.connection() as db:
        for table,original in rows.items():assert original==[tuple(r) for r in db.execute('SELECT * FROM '+table)]
    for key in ids:
        assert canonical(b['payload'](key))==originals[key]
        assert canonical(env['snapshot'](original_read(b['payload'](key)['request'],b['payload'](key)['history']['association'])))==native_originals[key]
    proof.update(actual_numerical_sources=True,selected_run=rid,computational_ancestors=ancestors,derivation_context=b['source_id'],originals_unchanged=True,forbidden_calls=counters,package_sha256=hashlib.sha256(raw).hexdigest(),manifest=manifest)
    (scope.root/'evidence/addition-c.json').write_text(json.dumps(proof,indent=2)+'\n')


def test_guarded_model_export_regression(monkeypatch):
    """Existing portable-model canary via the reviewed scoped native adapter."""
    import test_native_generation as regression
    from test_resolved_configuration import harness as reviewed, native as generate
    # The reviewed scoped stage: pinned producer image plus the cumulative patched sources.
    harness=reviewed.__wrapped__()
    assert harness[1].is_file()
    monkeypatch.setattr(regression,'native',lambda code:generate(harness,code.replace('NATIVE_RESULT=','PROJECTION_RESULT=')))
    regression.test_save_validate_export_import_prepare_canary_stays_data()


def test_combined(monkeypatch):
    """Fresh public HTTP commands -> actual dispatcher -> generated worker -> C."""
    import base64,copy,hashlib,io,sys,zipfile
    from concurrent.futures import ThreadPoolExecutor
    from checks import PROJECTION_SCOPE as scope,NATIVE_BACKEND as backend
    from combined_fixture import Journey
    import scoped_fixture as guard
    from hyprn_mvp_app.store import canonical,uid
    from hyprn_mvp_app.dispatcher import encode_record
    from hyprn_mvp_app.computational_export import records_for_store
    from hyprn_mvp_integration.calculation import NativeExecution
    from hyprn_mvp_integration import launcher
    from aiida import orm
    from aiida.common.links import LinkType
    from aiida.transports.plugins.local import LocalTransport
    from test_computational_archive import offline_roundtrip
    journey=Journey(scope,backend)
    try:
        j=journey.start();req=j.request;model=j.model
        original_store=orm.CalcJobNode.store;prestore=[]
        def observe(node,*args,**kwargs):
            links=node.base.links.get_incoming(link_type=LinkType.INPUT_CALC).all()
            linked=sorted((l.link_label,l.node.uuid) for l in links if l.link_label.startswith('upstream_results__'))
            if linked:assert not node.is_stored;prestore.append(linked)
            return original_store(node,*args,**kwargs)
        monkeypatch.setattr(orm.CalcJobNode,'store',observe)
        template=j.private.initial['configuration']
        # A Model4 is configured only through configuration request 6: explicit literal
        # inputs in unit spellings, never a criterion.
        literals=[dict(kind='literal',target=i['target'],value=i['value'],units='km',provenance=i['provenance']) for i in template['inputs']]
        candidate=dict(schema_version='6',study_id=j.sid,model_id=model['model_id'],model_revision_id=model['model_revision_id'],name='Sizing 0',
            inputs=literals,numerical=template['numerical'],
            context_source=dict(kind='current_study',expected_study_revision=j.study['revision']),notes=[],assumptions=[],
            general_context_evidence_version_ids=[],derivation=None)
        # Evidence and context are nonempty public data in the same fresh journey.
        evidence=req('POST','evidence',dict(command_id=uid(),evidence_schema_version='2',resource_scope=dict(scope_version='1',kind='study',study_id=j.sid),kind='note',content='Combined acceptance observation',source_refs=['Explicit synthetic study']),201)
        candidate['general_context_evidence_version_ids']=[evidence['evidence_version_id']]
        candidate['notes']=['Exact original scientific context']
        sources=[];originals={};native_originals={};saved_configs=[]
        def count():return orm.QueryBuilder(backend=backend).append(orm.CalcJobNode).count()
        def save(value):
            preview=req('POST','configurations/preview',value)
            body=dict(command_id=uid(),configuration_id=None,expected_revision=None,configuration=copy.deepcopy(value),expected_preview_digest=preview['candidate_digest'])
            result=req('POST','configurations',body,201)
            assert req('POST','configurations',body,201)==result
            req('POST','configurations',body|{'expected_preview_digest':'0'*64},409)
            return result,body
        def run(saved):
            body=dict(command_id=uid(),configuration_revision_id=saved['configuration']['configuration_revision_id'])
            with ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(lambda _:req('POST','runs',body,202),range(2)))
            assert rows[0]==rows[1];rid=rows[0]['run_id'];before=count()
            j.dispatch(rid);detail=req('GET','runs/'+rid)
            assert detail['state']=='recorded' and detail['history']['results']['execution']['state']=='finished',detail
            j.recorded_without_criteria(detail)
            assert count()==before+1
            j.dispatch(rid);assert count()==before+1
            replay=req('POST','runs',body,202)
            assert replay['run_id']==rid and replay['command_id']==body['command_id'] and replay['state']=='recorded'
            return rid,detail
        def values(detail):return {next(p['code_symbol'] for p in model['ports'] if p['port_id']==o['target']['port_id']):o['value'] for o in detail['history']['results']['outputs']}
        def remember(rid):
            payload=j.payload(rid);originals[rid]=canonical(payload)
            native_originals[rid]=canonical(encode_record(j.native.read_record(payload['request'],payload['history']['association'])))
        # No valid public request can supply a resolved scalar or native selector.
        req('POST','configurations/preview',candidate,status=403,headers={'X-CSRF-Token':'wrong'})
        assert j.http.get('/api/1/studies/'+uid()+'/result-sources').status_code==404
        for index,inputs in enumerate(([.002,.003,.001,.001],[.005,.007,.001,.001])):
            current=copy.deepcopy(candidate);current['name']='Sizing '+str(index)
            for item,value in zip(current['inputs'],inputs):item['value']=value;item['units']='km'
            saved,_=save(current);rid,detail=run(saved);sources.append((rid,detail));saved_configs.append(saved);remember(rid)
        page=req('GET','result-sources?limit=50')
        assert len(page['items'])==6 and all(i['native_availability']=='not_rechecked' for i in page['items'])
        linked=copy.deepcopy(candidate);linked['name']='Linked comparison'
        for n,(source_index,symbol) in enumerate([(0,'y'),(0,'z'),(0,'y'),(1,'y')]):
            if n==2:linked['inputs'][n].update(value=2,units='m');continue
            source=next(i for i in page['items'] if i['source_run_id']==sources[source_index][0] and i['labels']['output_name']==symbol)
            old=linked['inputs'][n]
            linked['inputs'][n]=dict(kind='run_result',target=old['target'],provenance=old['provenance'],source_run_id=source['source_run_id'],source_output=source['source_output'],expected_results_digest=source['results_digest'])
        forged=copy.deepcopy(linked);forged['inputs'][0]['value']=0
        req('POST','configurations/preview',forged,400)
        forged=copy.deepcopy(linked);forged['inputs'][0]['source_run_id']=uid()
        req('POST','configurations/preview',forged,404)
        comparison,comparison_body=save(linked);parent,parent_detail=run(comparison);remember(parent)
        assert values(parent_detail)==dict(y=2,z=3,total=12)
        # An actual public context edit forces an explicit historical choice.
        changed=j.http.patch('/api/1/studies/'+j.sid,json=dict(command_id=uid(),expected_revision=j.study['revision'],description='Changed current boundary context'))
        assert changed.status_code==200,changed.text
        before=j.store.path.read_bytes();j.private.offline=True
        seed=req('GET','runs/'+parent+'/modified-run-seed')
        assert j.store.path.read_bytes()==before and seed['requires_context_choice']
        j.private.offline=False
        modified=seed['configuration'];modified['name']='Modified comparison';modified['inputs'][2]['value']=4
        req('POST','configurations/preview',modified,409)
        modified['context_source']['choice_confirmed']=True
        raced=j.http.patch('/api/1/studies/'+j.sid,json=dict(command_id=uid(),expected_revision=changed.json()['data']['revision'],boundary='Concurrent current boundary'))
        assert raced.status_code==200,raced.text
        req('POST','configurations/preview',modified,409)
        latest=req('GET','runs/'+parent+'/modified-run-seed')
        modified['context_source']=latest['configuration']['context_source']|{'choice_confirmed':True}
        saved,modified_body=save(modified)
        assert saved['configuration']['configuration_id']!=comparison['configuration']['configuration_id']
        assert saved['configuration']['context_snapshot']==comparison['configuration']['context_snapshot']
        assert saved['configuration']['evidence_snapshots']==comparison['configuration']['evidence_snapshots']
        assert [i['result_binding'] for i in saved['configuration']['inputs']]==[i['result_binding'] for i in comparison['configuration']['inputs']]
        guard.change_worker_fixture_identity(scope)
        rid,detail=run(saved);remember(rid)
        assert values(detail)==dict(y=2,z=3,total=14)
        # Results 3 keep execution and outputs only; criteria are judged in calculations.
        outcomes=j.recorded_without_criteria(detail)
        assert len(outcomes['outputs'])==3
        assert detail['runtime_comparison']['state']=='different' and detail['runtime_comparison']['basis']=='prepared_bundle'
        deps=json.loads(base64.b64decode(j.payload(rid)['bundle']['files']['result-dependencies.json']))
        expected=sorted(('upstream_results__'+s['label'],s['result_uuid']) for s in deps['sources'])
        assert len(expected)==2 and len(deps['mappings'])==3 and prestore==[expected,expected]
        node=orm.load_node(j.payload(rid)['history']['association']['process_uuid'])
        parent_node=orm.load_node(j.payload(parent)['history']['association']['process_uuid'])
        links=node.base.links.get_incoming().all()
        assert all(l.node.uuid not in (parent_node.uuid,parent_node.outputs.results.uuid) for l in links)
        assert not node.base.links.get_incoming(link_type=LinkType.CALL_CALC).all() and not node.base.caching.is_created_from_cache
        # Real irreversible claim crash: reconciliation never makes it eligible.
        uncertain=req('POST','runs',dict(command_id=uid(),configuration_revision_id=saved['configuration']['configuration_revision_id']),202)
        before_count=count();j.dispatch(uncertain['run_id'],fault='after_claim');j.dispatch(uncertain['run_id'])
        assert req('GET','runs/'+uncertain['run_id'])['state']=='uncertain' and count()==before_count
        # Export runs through the actual fixed exports-only application child.
        j.private.offline=True;counters={};original_read=j.native.read_record;original_inspect=NativeExecution.inspect
        def deny(name):
            def forbidden(*args,**kwargs):counters[name]=counters.get(name,0)+1;raise AssertionError('Data-only path reached '+name)
            return forbidden
        for name in ('launch','inspect','require_attestation','bundle_runtime','read_record'):monkeypatch.setattr(NativeExecution,name,deny(name))
        monkeypatch.setattr(launcher,'isolated',deny('worker'))
        monkeypatch.setattr(orm.CalcJobNode,'process_class',property(deny('process_class')))
        monkeypatch.setattr(orm.CalcJobNode,'get_builder_restart',deny('restart'))
        monkeypatch.setattr(LocalTransport,'open',deny('transport'))
        import importlib.abc
        names={Path(p).stem for p in j.payload(rid)['bundle']['files'] if p.endswith('.py') and not p.startswith('provenance/')}|{'base','impl'}
        assert not names.intersection(sys.modules)
        class RejectCandidate(importlib.abc.MetaPathFinder):
            def find_spec(self,fullname,path=None,target=None):
                if fullname.split('.')[0] in names:deny('candidate_import')()
        finder=RejectCandidate();sys.meta_path.insert(0,finder)
        try:
            body=dict(command_id=uid(),selected_run_ids=[rid]);queued=req('POST','computational-record-previews',body,202)
            assert req('POST','computational-record-previews',body,202)==queued
            req('POST','computational-record-previews',body|{'selected_run_ids':[parent]},409)
            assert req('GET','computational-records/'+queued['request_id'])['state']=='queued'
            guard.run_export_dispatcher(scope,j.native,j.store.path,queued['request_id'])
            preview=req('GET','computational-records/'+queued['request_id']);assert preview['state']=='reviewable',preview
            body=dict(command_id=uid(),preview_id=preview['request_id'],expected_preview_digest=preview['preview']['preview_digest'])
            created=req('POST','computational-records',body,202)
            assert req('POST','computational-records',body,202)==created
            guard.run_export_dispatcher(scope,j.native,j.store.path,created['request_id'])
            ready=req('GET','computational-records/'+created['request_id']);assert ready['state']=='ready',ready
            download='/api/1/studies/'+j.sid+'/computational-records/'+created['request_id']+'/download'
            response=j.http.get(download);assert response.status_code==200,response.text
            raw=response.content;assert hashlib.sha256(raw).hexdigest()==ready['download']['sha256']
            (scope.root/'evidence/combined.zip').write_bytes(raw)
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                manifest=json.loads(archive.read('manifest.json'))
                assert sorted(manifest['computational_run_ids'])==sorted([rid,*[x[0] for x in sources]])
                assert manifest['derivation_context_run_ids']==[parent]
                for item in manifest['inventory']:
                    content=archive.read(item['path']);assert len(content)==item['size'] and hashlib.sha256(content).hexdigest()==item['sha256']
                for run_id in manifest['computational_run_ids']:
                    for path,content in j.payload(run_id)['bundle']['files'].items():assert archive.read('hyprn-mvp/runs/'+run_id+'/bundle/'+path)==base64.b64decode(content)
                archive_path=scope.root/'evidence/computations.aiida';archive_path.write_bytes(archive.read('computations.aiida'))
            proof=offline_roundtrip(archive_path,scope,backend,expected_processes={j.payload(key)['history']['association']['process_uuid'] for key in manifest['computational_run_ids']})
            assert parent_node.uuid not in proof['node_uuids'] and counters=={}
            # Actual ready-byte corruption and current membership revocation.
            service=records_for_store(j.store)
            with j.store.connection() as db:artifact=Path(db.execute('SELECT artifact_path FROM computational_record_requests WHERE request_id=?',(created['request_id'],)).fetchone()[0])
            original=artifact.read_bytes();mode=artifact.stat().st_mode & 0o777
            try:
                artifact.chmod(0o600)
                artifact.write_bytes(original[:-1]+bytes([original[-1]^1]))
                assert j.http.get(download).status_code==422
            finally:artifact.write_bytes(original);artifact.chmod(mode)
            revoked=req('POST','computational-record-previews',dict(command_id=uid(),selected_run_ids=[rid]),202)
            archive_calls=[];archive_method=NativeExecution.archive_record
            def track_archive(self,*args,**kwargs):archive_calls.append(True);return archive_method(self,*args,**kwargs)
            monkeypatch.setattr(NativeExecution,'archive_record',track_archive)
            with j.store.connection(write=True) as db:
                member=tuple(db.execute('SELECT * FROM memberships WHERE study_id=? AND actor_id=?',(j.sid,j.actor)).fetchone())
                db.execute('DELETE FROM memberships WHERE study_id=? AND actor_id=?',(j.sid,j.actor))
            assert j.http.get(download).status_code==404
            guard.run_export_dispatcher(scope,j.native,j.store.path,revoked['request_id'])
            assert archive_calls==[]
            with j.store.connection(write=True) as db:db.execute('INSERT INTO memberships VALUES(?,?,?)',member)
            assert req('GET','computational-records/'+revoked['request_id'])['state']=='failed'
        finally:sys.meta_path.remove(finder)
        monkeypatch.setattr(NativeExecution,'inspect',original_inspect)
        for key,original in originals.items():
            assert canonical(j.payload(key))==original
            assert canonical(encode_record(original_read(j.payload(key)['request'],j.payload(key)['history']['association'])))==native_originals[key]
            assert req('GET','runs/'+key)['history']['errors']==[]
            configuration=j.payload(key)['frozen']['configuration']
            with j.store.connection() as db:
                assert db.execute('SELECT head FROM configuration_families WHERE configuration_id=?',(configuration['configuration_id'],)).fetchone()[0]==configuration['configuration_revision_id']
                retained=json.loads(db.execute('SELECT payload FROM configurations WHERE configuration_revision_id=?',(configuration['configuration_revision_id'],)).fetchone()[0])
                assert retained==j.payload(key)['frozen']
        test_guarded_model_export_regression(monkeypatch)
        proof.update(public_http=True,actual_dispatch_bridge=True,actual_worker=True,values=values(detail),originals_unchanged=True,forbidden_calls=counters,prestore_links=prestore,manifest=manifest,package_sha256=hashlib.sha256(raw).hexdigest())
        (scope.root/'evidence/combined.json').write_text(json.dumps(proof,indent=2)+'\n')
    finally:
        (scope.root/'evidence/combined-events.json').write_text(json.dumps(journey.events,indent=2)+'\n')
        journey.close()
