"""Fresh public HTTP -> production private JWT -> native generator -> worker.

All scientific records are newly computed in the guarded off-cloud profile.
The private producer is the pinned image plus exact cumulative audited overlays;
this is an integration proof, not deployment or human acceptance.
"""
# P2 live-runtime fence (deployment/tests/live_fence.py): refuses live roots, live ports, live docker names, live entry points and foreign signals.
import sys as _fence_sys
from pathlib import Path as _FencePath
if str(_FencePath(__file__).resolve().parent) not in _fence_sys.path:
    _fence_sys.path.append(str(_FencePath(__file__).resolve().parent))
import live_fence  # noqa: E402
live_runtime_fence = live_fence.pytest_fixture('baseline')
import base64
from copy import deepcopy
import hashlib
import io
import json
import zipfile
from concurrent.futures import ThreadPoolExecutor

from aiida import orm
from aiida.common.links import LinkType
from checks import PROJECTION_SCOPE as SCOPE, NATIVE_BACKEND as BACKEND
import scoped_fixture as guard
from combined_fixture import NativeJourney
from hyprn_mvp_app.store import canonical, digest, uid
from hyprn_mvp_app.dispatcher import encode_record
from hyprn_mvp_integration.calculation import NativeExecution
from hyprn_mvp_integration import launcher
from test_computational_archive import offline_roundtrip


def test_actual_native_assumptions_evidence_journey(monkeypatch):
    j=NativeJourney(SCOPE,BACKEND);proof={};originals={}
    try:
        j.start();req=j.request
        count=lambda:orm.QueryBuilder(backend=BACKEND).append(orm.CalcJobNode).count()
        assert count()==0
        def evidence(title):
            return dict(evidence_schema_version='3',title=title,kind='note',content='Synthetic force calibration observation',
                source_refs=['Synthetic report R1; no validity inference'],resource_scope=dict(scope_version='1',kind='study',study_id=j.sid))
        eb=dict(command_id=uid(),**evidence('Force report E1'))
        e1=req('POST','evidence',eb,201);eid=e1['evidence_version_id']
        assert req('POST','evidence',eb,201)==e1
        req('POST','evidence',eb|{'title':'Changed replay'},409)
        req('POST','evidence',dict(command_id=uid(),**{k:v for k,v in evidence('x').items() if k!='title'}),400)
        req('POST','evidence',dict(command_id=uid(),**evidence('x'))|{'resource_scope':dict(scope_version='1',kind='study',study_id=uid())},404)
        assert e1['recorded_context']['resource_labels'][0]['name']==j.study['name']
        draft=req('POST','models',dict(command_id=uid(),expected_revision=j.study['revision'],name='Independent force instances',template='empty'),201)
        j.study=j.http.get('/api/1/studies/'+j.sid).json()['data']
        mid=draft['model_id'];mp='models/'+mid
        source=b"# <%= File.write('/store/forbidden-candidate-import', 'bad') %>\noutputs['force'] = inputs['mass'] * inputs['velocity'] / inputs['duration']\n"
        units={'mass':'kg','velocity':'m/s','duration':'s','force':'N'}
        ports=[dict(temp_key=k,direction='output' if k=='force' else 'input',name=k,code_symbol=k,value_type='real_scalar',units=u) for k,u in units.items()]
        def add(key,owner,text,relation=None):
            return dict(kind='add_assumption',temp_key=key,owner=owner,statement=text,evidence_links=[] if relation is None else [dict(evidence_version_id=eid,relation=relation)])
        edits=[dict(kind='create_definition',temp_key='force',definition_kind='explicit_component',name='Force',ports=ports,
                source=dict(encoding='base64',media_type='text/x-python',bytes=base64.b64encode(source).decode(),sha256=hashlib.sha256(source).hexdigest())),
            dict(kind='instantiate',temp_key='first',version_ref=dict(temp_key='force')),
            dict(kind='instantiate',temp_key='second',version_ref=dict(temp_key='force')),
            add('first_assumption',dict(kind='instance',instance_temp_key='first'),'First instance: constant mass','supports'),
            add('second_assumption',dict(kind='instance',instance_temp_key='second'),'Second instance: calibration questioned','challenges'),
            add('uncited',dict(kind='model'),'Uncited idealization'),add('model',dict(kind='model'),'Model boundary','context')]
        edit_body=dict(schema_version='2',command_id=uid(),expected_revision=draft['draft_revision'],edits=edits)
        draft=req('POST',mp+'/edits',edit_body)
        assert req('POST',mp+'/edits',edit_body)==draft
        req('POST',mp+'/edits',edit_body|{'edits':[]},409)
        req('POST',mp+'/edits',edit_body|{'command_id':uid()},409)
        children=[i for i in draft['instances'] if i['instance_id']!=draft['root_instance_id']]
        assert len(children)==2 and len({i['definition_version_id'] for i in children})==1
        defid=next(d['definition_id'] for d in draft['definitions'] if d['definition_version_id']==children[0]['definition_version_id'])
        draft=req('POST',mp+'/edits',dict(schema_version='2',command_id=uid(),expected_revision=draft['draft_revision'],edits=[dict(kind='set_annotation',element_ref=defid,text='Definition note, distinct from assumptions')]))
        model=req('POST',mp+'/commits',dict(command_id=uid(),expected_revision=draft['draft_revision']))
        assert len(model['assumptions'])==4 and model['annotations'][-1]['text'].startswith('Definition note')
        before_model=canonical(model)
        assert j.canary()['candidate_side_effect'] is False
        package=req('GET',mp+'/export?model_revision_id='+model['model_revision_id'])
        # The same backend must reject preserved-ID collisions. A separately
        # identified portable canary then exercises successful public import.
        other=j.http.post('/api/1/studies',json=dict(command_id=uid(),name='Import canary'))
        assert other.status_code==201
        import_url='/api/1/studies/'+other.json()['data']['study_id']+'/model-imports'
        import_body=dict(command_id=uid(),expected_revision=other.json()['data']['revision'],package=package)
        assert j.http.post(import_url,json=import_body).status_code==409
        import_body['expected_revision']=j.http.get('/api/1/studies/'+other.json()['data']['study_id']).json()['data']['revision']
        import re,uuid
        remap={}
        portable=json.loads(re.sub(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',lambda m:remap.setdefault(m[0],uid()),json.dumps(package)))
        files={}
        def descriptor(path,raw,media,role):
            files[path]=dict(file_id=str(uuid.UUID(hashlib.sha256(('model-package-v1:'+path).encode()).hexdigest()[:32])),path=path,size=len(raw),sha256=hashlib.sha256(raw).hexdigest(),media_type=media,role=role)
        for pin in portable['revisions']:
            pin['digest']=digest({k:v for k,v in pin.items() if k!='digest'})
            descriptor('revisions/'+pin['model_revision_id']+'.json',canonical(pin),'application/json','model')
            for item in pin['source_files']:descriptor('sources/'+item['sha256']+'.py',base64.b64decode(item['bytes']),'text/x-python','source')
        portable['files']=[files[k] for k in sorted(files)]
        portable['digest']=digest({k:v for k,v in portable.items() if k!='digest'})
        (SCOPE.root/'evidence/import-canary-package.json').write_text(json.dumps(portable,indent=2))
        imported=j.http.post(import_url,json=import_body|{'command_id':uid(),'package':portable})
        assert imported.status_code==201,imported.text
        assert j.canary()['candidate_side_effect'] is False
        definition=next(d for d in model['definitions'] if d['definition_id']==defid)
        portmap={p['code_symbol']:p for p in definition['ports']}
        def target(i,k):return dict(instance_id=i['instance_id'],port_id=portmap[k]['port_id'])
        candidate=dict(schema_version='3',study_id=j.sid,model_id=mid,model_revision_id=model['model_revision_id'],name='Original force',
            inputs=[dict(kind='literal',target=target(i,k),value=v,units=units[k],provenance=dict(kind='manual',statement=f'Explicit {k}: {v} {units[k]}',evidence_version_ids=[eid])) for i,values in zip(children,[(2,3,2),(4,5,2)]) for k,v in zip(('mass','velocity','duration'),values)],
            criteria=[dict(criterion_id=uid(),target=target(children[0],'force'),operator='eq',threshold=3,units='N',evidence_version_ids=[eid])],
            numerical=dict(mode='deterministic',initialization=[],solvers=[],design_variables=[],objectives=[],constraints=[],optimizer=None,uncertainty=None,derivatives=dict(method='none',form=None,check=None)),
            context_source=dict(kind='current_study',expected_study_revision=j.study['revision']),notes=['Configuration note'],
            assumptions=[dict(assumption_id=uid(),statement='Configuration-specific steady acceleration',evidence_links=[dict(evidence_version_id=eid,relation='supports')])],
            general_context_evidence_version_ids=[eid],derivation=None)
        p=req('POST','configurations/preview',candidate)
        assert p['resolved_candidate']['evidence_snapshots']==[e1]
        removed=deepcopy(candidate);removed['general_context_evidence_version_ids']=[]
        assert req('POST','configurations/preview',removed)['resolved_candidate']['evidence_snapshots']==[e1]
        req('POST','configurations/preview',candidate,403,headers={'X-CSRF-Token':'wrong'})
        invalid=deepcopy(candidate);invalid['assumptions'][0]['evidence_links'][0]['evidence_version_id']=uid()
        req('POST','configurations/preview',invalid,422)
        assert count()==0
        def save(value):
            preview=req('POST','configurations/preview',value)
            body=dict(command_id=uid(),configuration_id=None,expected_revision=None,configuration=value,expected_preview_digest=preview['candidate_digest'])
            saved=req('POST','configurations',body,201)
            assert req('POST','configurations',body,201)==saved
            req('POST','configurations',body|{'expected_preview_digest':'0'*64},409)
            return saved
        def execute(saved):
            body=dict(command_id=uid(),configuration_revision_id=saved['configuration']['configuration_revision_id'])
            with ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(lambda _:req('POST','runs',body,202),range(2)))
            assert rows[0]==rows[1]
            rid=rows[0]['run_id'];n=count();j.dispatch(rid,prepare_only=True)
            assert count()==n and j.canary()['candidate_side_effect'] is False
            j.dispatch(rid);detail=req('GET','runs/'+rid)
            assert detail['state']=='recorded' and not detail['history']['errors'],detail
            assert detail['history']['results']['execution']['state']=='finished'
            assert count()==n+1
            j.dispatch(rid);assert count()==n+1
            assert req('POST','runs',body,202)['run_id']==rid
            payload=j.payload(rid);node=orm.load_node(payload['history']['association']['process_uuid'])
            assert node.is_finished_ok and not node.base.caching.is_created_from_cache
            assert node.outputs.results.creator.uuid==node.uuid
            originals[rid]=dict(payload=canonical(payload),native=canonical(encode_record(j.native.read_record(payload['request'],payload['history']['association']))))
            return rid,detail,node
        def values(detail):return {o['target']['instance_id']:o['value'] for o in detail['history']['results']['outputs']}
        saved=save(candidate);rid,detail,node=execute(saved)
        assert values(detail)=={children[0]['instance_id']:3,children[1]['instance_id']:10}
        assert detail['history']['results']['applicability']['state']=='unassessed'
        assert detail['history']['results']['criteria'][0]['outcome']=='met'
        original_detail=deepcopy(detail['history'])
        e2body=dict(command_id=uid(),expected_revision=eid,**evidence('Force report E2'))
        family='evidence-families/'+e1['evidence_id']+'/versions'
        e2=req('POST',family,e2body,201)
        assert req('POST',family,e2body,201)==e2
        req('POST',family,e2body|{'command_id':uid()},409)
        req('POST',family,e2body|{'title':'Changed payload'},409)
        assert req('GET','evidence/'+eid)==e1
        old_assumption=draft['assumptions'][0]
        draft=req('POST',mp+'/edits',dict(schema_version='2',command_id=uid(),expected_revision=draft['draft_revision'],edits=[dict(kind='update_assumption',assumption_id=old_assumption['assumption_id'],statement='Later first-instance assumption',evidence_links=old_assumption['evidence_links'])]))
        new_model=req('POST',mp+'/commits',dict(command_id=uid(),expected_revision=draft['draft_revision']))
        assert new_model['digest']!=model['digest'] and new_model['assumptions'][1:]==model['assumptions'][1:]
        assert canonical(req('GET',mp+'/revisions/'+model['model_revision_id']))==before_model
        seed=req('GET','runs/'+rid+'/modified-run-seed')
        assert seed['schema_version']=='2'
        modified=seed['configuration'];modified['name']='Explicit modified force'
        assert modified['model_revision_id']==model['model_revision_id']
        assert modified['assumptions']==candidate['assumptions']
        modified['assumptions'][0]['evidence_links']=[dict(evidence_version_id=e2['evidence_version_id'],relation='challenges')]
        modified['inputs'][0]['value']=6
        updated=save(modified)
        assert {e['evidence_version_id'] for e in updated['configuration']['evidence_snapshots']}=={eid,e2['evidence_version_id']}
        assert updated['configuration']['general_context_evidence_version_ids']==[eid]
        second,second_detail,second_node=execute(updated)
        assert second_node.uuid!=node.uuid
        assert values(second_detail)=={children[0]['instance_id']:9,children[1]['instance_id']:10}
        assert not second_node.base.links.get_incoming(link_type=LinkType.CALL_CALC).all()
        # Real post-claim fault must never allocate or redispatch a replacement.
        uncertain_body=dict(command_id=uid(),configuration_revision_id=updated['configuration']['configuration_revision_id'])
        uncertain=req('POST','runs',uncertain_body,202);n=count()
        j.dispatch(uncertain['run_id'],fault='after_claim');j.dispatch(uncertain['run_id'])
        assert req('POST','runs',uncertain_body,202)['run_id']==uncertain['run_id']
        assert req('GET','runs/'+uncertain['run_id'])['state']=='uncertain' and count()==n
        j.offline();j.restart_web()
        assert req('GET','runs/'+rid)['history']==original_detail
        assert req('GET','runs/'+rid+'/modified-run-seed')['configuration']['assumptions']==candidate['assumptions']
        assert req('GET','configurations/'+saved['configuration']['configuration_revision_id'])==saved
        counters={};original_read=j.native.read_record
        def deny(name):
            def forbidden(*args,**kwargs):counters[name]=counters.get(name,0)+1;raise AssertionError('Data-only path reached '+name)
            return forbidden
        from aiida.transports.plugins.local import LocalTransport
        for name in ('launch','require_attestation','bundle_runtime','read_record'):monkeypatch.setattr(NativeExecution,name,deny(name))
        monkeypatch.setattr(launcher,'isolated',deny('worker'))
        monkeypatch.setattr(orm.CalcJobNode,'process_class',property(deny('process_class')))
        monkeypatch.setattr(orm.CalcJobNode,'get_builder_restart',deny('restart'))
        monkeypatch.setattr(LocalTransport,'open',deny('transport'))
        body=dict(command_id=uid(),selected_run_ids=[second])
        queued=req('POST','computational-record-previews',body,202)
        assert req('POST','computational-record-previews',body,202)==queued
        req('POST','computational-record-previews',body|{'selected_run_ids':[rid]},409)
        guard.run_export_dispatcher(SCOPE,j.native,j.store.path,queued['request_id'])
        preview=req('GET','computational-records/'+queued['request_id']);assert preview['state']=='reviewable',preview
        created=req('POST','computational-records',dict(command_id=uid(),preview_id=preview['request_id'],expected_preview_digest=preview['preview']['preview_digest']),202)
        guard.run_export_dispatcher(SCOPE,j.native,j.store.path,created['request_id'])
        ready=req('GET','computational-records/'+created['request_id']);assert ready['state']=='ready',ready
        download='/api/1/studies/'+j.sid+'/computational-records/'+created['request_id']+'/download'
        response=j.http.get(download);assert response.status_code==200
        raw=response.content;assert hashlib.sha256(raw).hexdigest()==ready['download']['sha256']
        (SCOPE.root/'evidence/ae-native.zip').write_bytes(raw)
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            manifest=json.loads(archive.read('manifest.json'))
            assert manifest['computational_run_ids']==[second] and manifest['derivation_context_run_ids']==[rid]
            for item in manifest['inventory']:
                content=archive.read(item['path']);assert len(content)==item['size'] and hashlib.sha256(content).hexdigest()==item['sha256']
            for path,content in j.payload(second)['bundle']['files'].items():assert archive.read('hyprn-mvp/runs/'+second+'/bundle/'+path)==base64.b64decode(content)
            native_path=SCOPE.root/'evidence/computations.aiida';native_path.write_bytes(archive.read('computations.aiida'))
        roundtrip=offline_roundtrip(native_path,SCOPE,BACKEND,expected_processes={second_node.uuid})
        assert node.uuid not in roundtrip['node_uuids'] and counters=={}
        # Actual archive corruption and revoked membership are current-authority checks.
        with j.store.connection() as db:artifact=guard.no_symlinks(db.execute('SELECT artifact_path FROM computational_record_requests WHERE request_id=?',(created['request_id'],)).fetchone()[0])
        original=artifact.read_bytes();mode=artifact.stat().st_mode&0o777
        try:
            artifact.chmod(0o600);artifact.write_bytes(original[:-1]+bytes([original[-1]^1]))
            assert j.http.get(download).status_code==422
        finally:artifact.write_bytes(original);artifact.chmod(mode)
        with j.store.connection(write=True) as db:
            member=tuple(db.execute('SELECT * FROM memberships WHERE study_id=? AND actor_id=?',(j.sid,j.actor)).fetchone())
            db.execute('DELETE FROM memberships WHERE study_id=? AND actor_id=?',(j.sid,j.actor))
        assert j.http.get(download).status_code==404
        assert j.http.get('/api/1/studies/'+j.sid+'/runs/'+rid).status_code==404
        with j.store.connection(write=True) as db:db.execute('INSERT INTO memberships VALUES(?,?,?)',member)
        hashes={}
        for key,before in originals.items():
            payload=j.payload(key)
            after=canonical(payload);native=canonical(encode_record(original_read(payload['request'],payload['history']['association'])))
            assert after==before['payload'] and native==before['native']
            hashes[key]={kind:hashlib.sha256(value).hexdigest() for kind,value in before.items()}
        proof=dict(passed=True,public_http=True,private_production_http_jwt=True,cumulative_patch='070-assumptions-evidence.patch',
            independent_analytical_values={'original':[3,10],'modified':[9,10]},units='N',
            original_run=rid,modified_run=second,original_process=node.uuid,modified_process=second_node.uuid,
            fresh_process_count=count(),original_hashes_before_and_after=hashes,model_sha256=hashlib.sha256(before_model).hexdigest(),
            e1=e1,e2=e2,original_model=model,new_model=new_model,original_configuration=saved,modified_configuration=updated,
            original_results=detail['history']['results'],modified_results=second_detail['history']['results'],
            modeling_stopped=True,application_restarted=True,forbidden_calls=counters,manifest=manifest,offline=roundtrip,
            archive_sha256=hashlib.sha256(raw).hexdigest(),human_acceptance='pending')
    finally:
        (SCOPE.root/'evidence/ae-native-events.json').write_text(json.dumps(j.events,indent=2))
        (SCOPE.root/'evidence/ae-native-proof.json').write_text(json.dumps(proof,indent=2))
        j.close()
