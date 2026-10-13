"""Fresh public proposal-to-native-to-offline proof; no synthetic scientific records."""
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

import pytest
from aiida import orm
from aiida.tools.archive.implementations.sqlite_zip.main import ArchiveFormatSqlZip
from checks import PROJECTION_SCOPE as SCOPE,NATIVE_BACKEND as BACKEND
import scoped_fixture as guard
from approach_native_fixture import ApproachJourney,source,step,literal,criterion
from hyprn_mvp_app.store import canonical,digest,uid
from hyprn_mvp_app.execution import validate_retained_bundle
from hyprn_mvp_app.computational_export import inspect_record
from hyprn_mvp_integration.computational_export import Export


def test_fresh_http_native_approach_journey(monkeypatch):
    j=ApproachJourney(SCOPE,BACKEND);proof={}
    try:
        j.start();req=j.request;assert j.process_count()==0
        e1=j.evidence('Original calibration note');eid=e1['evidence_version_id']
        assumption=dict(assumption_id=uid(),statement='Constant mass for the first force component',role='proposed_model_condition',evidence_links=[dict(evidence_version_id=eid,relation='supports')])
        content=dict(schema_version='1',question='How do explicit force cases compare?',scope='Synthetic deterministic physical model',limitations='Not a validity assessment',open_questions='Calibration requires independent review',model_bindings=[],steps=[step('Estimate forces')],assumptions=[assumption],cases=[],basis_refs=[])
        content['steps'][0]['assumption_refs']=[dict(kind='approach',assumption_id=assumption['assumption_id'])]
        assert req('GET','approach')==dict(draft=None,latest_version=None)
        proposal=j.save_approach(content);proposal_id=proposal['version']['approach_version_id']
        assert proposal['closure']['models']==[] and j.process_count()==0
        pbody=dict(schema_version='1',expected_revision=req('GET','approach')['draft']['revision'],content=content)
        req('POST','approach/preview',pbody,403,headers={'X-CSRF-Token':'bad'})
        import httpx
        with httpx.Client(trust_env=False) as outsider:assert outsider.get(j.url+'/api/1/studies/'+j.sid+'/approach').status_code==401
        units=dict(mass='kg',velocity='m/s',duration='s',force='N')
        force=b"# <%= File.write('/store/forbidden-candidate-import', 'bad') %>\noutputs['force'] = inputs['mass'] * inputs['velocity'] / inputs['duration']\n"
        ports=[dict(temp_key=k,direction='output' if k=='force' else 'input',name=k,code_symbol=k,value_type='real_scalar',units=u) for k,u in units.items()]
        total=b"outputs['total'] = inputs['left'] + inputs['right']\n"
        edits=[dict(kind='create_definition',temp_key='force',definition_kind='explicit_component',name='Force',ports=ports,source=source(force)),
            dict(kind='instantiate',temp_key='first',version_ref=dict(temp_key='force')),
            dict(kind='instantiate',temp_key='second',version_ref=dict(temp_key='force')),
            dict(kind='create_definition',temp_key='total',definition_kind='explicit_component',name='Total force',ports=[dict(temp_key=k,direction='output' if k=='total' else 'input',name=k,code_symbol=k,value_type='real_scalar',units='N') for k in ('left','right','total')],source=source(total)),
            dict(kind='instantiate',temp_key='sum',version_ref=dict(temp_key='total')),
            *[dict(kind='connect',temp_key='wire'+key,source_ref=dict(instance_temp_key=owner,definition_temp_key='force',port_temp_key='force'),target_ref=dict(instance_temp_key='sum',definition_temp_key='total',port_temp_key=key)) for key,owner in [('left','first'),('right','second')]],
            dict(kind='add_assumption',temp_key='condition',owner=dict(kind='instance',instance_temp_key='first'),statement=assumption['statement'],evidence_links=assumption['evidence_links'])]
        draft,model=j.model('Repeated force components',edits)
        force_def=next(d for d in model['definitions'] if d['name']=='Force');total_def=next(d for d in model['definitions'] if d['name']=='Total force')
        children=[i for i in model['instances'] if i['definition_version_id']==force_def['definition_version_id']]
        assert len(children)==2 and len(model['connections'])==2
        sum_instance=next(i for i in model['instances'] if i['definition_version_id']==total_def['definition_version_id'])
        portmap={p['code_symbol']:p['port_id'] for p in force_def['ports']}
        target=lambda i,k:dict(instance_id=i['instance_id'],port_id=portmap[k])
        total_target=dict(instance_id=sum_instance['instance_id'],port_id=next(p['port_id'] for p in total_def['ports'] if p['code_symbol']=='total'))
        actual_assumption=model['assumptions'][0]
        first=next(i for i in children if i['instance_id']==actual_assumption['owner']['instance_id']);second=next(i for i in children if i!=first);children=[first,second]
        scalar_raw=b"outputs['y'] = inputs['x'] / 2 + 1\n"
        scalar_draft,scalar=j.model('Independent affine scalar',[dict(kind='create_definition',temp_key='affine',definition_kind='explicit_component',name='Affine',ports=[dict(temp_key=k,direction='input' if k=='x' else 'output',name=k,code_symbol=k,value_type='real_scalar',units='N') for k in ('x','y')],source=source(scalar_raw)),dict(kind='instantiate',temp_key='affine_instance',version_ref=dict(temp_key='affine'))])
        si=next(i for i in scalar['instances'] if i['instance_id']!=scalar['root_instance_id']);sd=next(d for d in scalar['definitions'] if d['definition_version_id']==si['definition_version_id'])
        st=lambda k:dict(instance_id=si['instance_id'],port_id=next(p['port_id'] for p in sd['ports'] if p['code_symbol']==k))
        binding=dict(binding_id=uid(),model_id=model['model_id'],model_revision_id=model['model_revision_id'])
        sb=dict(binding_id=uid(),model_id=scalar['model_id'],model_revision_id=scalar['model_revision_id'])
        content['model_bindings']=[binding,sb];content['assumptions']=[]
        method=content['steps'][0];method['implementation_state']='linked'
        method['implementation_refs']=[dict(kind='instance',binding_id=binding['binding_id'],instance_id=i['instance_id']) for i in children]+[dict(kind='connection',binding_id=binding['binding_id'],connection_id=c['connection_id']) for c in model['connections']]
        method['assumption_refs']=[dict(kind='model',binding_id=binding['binding_id'],assumption_id=actual_assumption['assumption_id'],origin=dict(approach_version_id=proposal_id,assumption_id=assumption['assumption_id'],digest=proposal['version']['digest']))]
        method['evidence_links']=[dict(evidence_version_id=eid,relation='context',locator='Analytical force specification')]
        scalar_step=step('Transform a retained scalar');scalar_step.update(implementation_state='linked',implementation_refs=[dict(kind='model',binding_id=sb['binding_id'])]);content['steps'].append(scalar_step)
        content['cases']=[dict(case_id=uid(),title=name,question='Explicit values only',rationale='Separate immutable configuration',binding_id=binding['binding_id'],evidence_links=[]) for name in ('Baseline','Higher mass')]
        linked=j.save_approach(content);version=linked['version'];vid=version['approach_version_id']
        assert req('GET','approach/versions/'+proposal_id)==proposal
        assert {v['approach_version_id'] for v in linked['closure']['approach_versions']}=={proposal_id,vid}
        assert j.process_count()==0 and not j.canary()['candidate_side_effect']
        def candidate(name,mass,case):
            inputs=[literal(target(i,k),v,units[k],eid) for i,values in zip(children,[(mass,3,2),(4,5,2)]) for k,v in zip(('mass','velocity','duration'),values)]
            return j.configuration(model,name,inputs,[criterion(total_target,mass*3/2+10,'N',eid)],dict(approach_version_id=vid,case_id=case['case_id']),e1)
        c1=candidate('Baseline inputs',2,content['cases'][0]);c2=candidate('Higher mass inputs',6,content['cases'][1])
        wrong=deepcopy(c1);wrong['approach_selection']['case_id']=uid();req('POST','configurations/preview',wrong,422)
        saved1=j.save_configuration(c1);saved2=j.save_configuration(c2)
        assert saved1['configuration']['approach_binding']['case_id']!=saved2['configuration']['approach_binding']['case_id']
        r1,h1,n1=j.execute(saved1);r2,h2,n2=j.execute(saved2)
        def values(h):return {o['target']['instance_id']:o['value'] for o in h['history']['results']['outputs']}
        assert values(h1)=={first['instance_id']:3,second['instance_id']:10,sum_instance['instance_id']:13}
        assert values(h2)=={first['instance_id']:9,second['instance_id']:10,sum_instance['instance_id']:19}
        assert all(h['history']['results']['criteria'][0]['outcome']=='met' for h in (h1,h2))
        assert h1['history']['results']['applicability']['state']=='unassessed'
        original=deepcopy(h1['history']);frozen_bytes=canonical(j.payload(r1))
        # Scientific citation of case2 is not a native numerical ancestor.
        content['basis_refs']=[dict(kind='run',run_id=r2,reason='Compare independently executed higher-mass case',relation='context')]
        with_basis=j.save_approach(content)
        seed=req('GET','runs/'+r1+'/modified-run-seed');assert seed['schema_version']=='3'
        modified=seed['configuration'];modified['name']='Modified with explicit new explanation'
        modified['context_source']['choice_confirmed']=True
        modified['approach_selection']=dict(approach_version_id=with_basis['version']['approach_version_id'],case_id=content['cases'][0]['case_id'])
        next(i for i in modified['inputs'] if i['target']==target(first,'mass'))['value']=4
        sm=j.save_configuration(modified);rm,hm,nm=j.execute(sm)
        assert values(hm)=={first['instance_id']:6,second['instance_id']:10,sum_instance['instance_id']:16}
        # The unrelated native program consumes a real exact prior scalar output.
        result_input=dict(kind='run_result',target=st('x'),provenance=dict(kind='manual',statement='Explicit prior run transfer',evidence_version_ids=[eid]),source_run_id=r1,source_output=target(first,'force'),expected_results_digest=digest(h1['history']['results']))
        scalar_request=j.configuration(scalar,'Affine transferred result',[result_input],[criterion(st('y'),2.5,'N',eid)],dict(approach_version_id=with_basis['version']['approach_version_id'],case_id=None),e1)
        ss=j.save_configuration(scalar_request);rs,hs,ns=j.execute(ss)
        assert values(hs)=={si['instance_id']:2.5}
        source_node=ns.base.links.get_incoming().all()
        assert any(link.node.uuid==n1.outputs.results.uuid for link in source_node)
        usage=req('GET','approach/versions/'+vid+'/usage?case_id='+content['cases'][0]['case_id'])
        assert usage['items']
        # Integrity failures are refused before allocation or candidate import.
        payload=j.payload(r1);bundle=dict(manifest=payload['bundle']['manifest'],files={p:base64.b64decode(b) for p,b in payload['bundle']['files'].items()})
        for part in ('configuration.json','model.json','approach/closure.json','generated/entry.py'):
            bad=deepcopy(bundle);bad['files'][part]+=b' '
            with pytest.raises(ValueError):
                validate_retained_bundle(bad,payload['request'],saved1)
        assert j.process_count()==4
        e2=j.evidence('Later calibration note',previous=e1)
        mp='models/'+model['model_id']
        draft=req('POST',mp+'/edits',dict(schema_version='2',command_id=uid(),expected_revision=draft['draft_revision'],edits=[dict(kind='update_assumption',assumption_id=actual_assumption['assumption_id'],statement='Later condition only',evidence_links=[dict(evidence_version_id=e2['evidence_version_id'],relation='challenges')])]))
        later_model=req('POST',mp+'/commits',dict(command_id=uid(),expected_revision=draft['draft_revision']))
        content['question']='Later explanation must not replace prior context';later=j.save_approach(content)
        assert later_model['digest']!=model['digest'] and later['version']['digest']!=version['digest']
        uncertain=req('POST','runs',dict(command_id=uid(),configuration_revision_id=sm['configuration']['configuration_revision_id']),202)
        j.dispatch(uncertain['run_id'],fault='after_claim');j.dispatch(uncertain['run_id'])
        assert req('GET','runs/'+uncertain['run_id'])['state']=='uncertain' and j.process_count()==4
        j.offline();j.restart_web()
        assert req('GET','runs/'+r1)['history']==original
        assert req('GET','approach/versions/'+vid)==linked
        assert req('GET','configurations/'+saved1['configuration']['configuration_revision_id'])==saved1
        assert req('GET','runs/'+r1+'/modified-run-seed')['approach_closure']==saved1['approach_closure']
        assert canonical(j.payload(r1))==frozen_bytes
        from hyprn_mvp_app.computational_export import ComputationalRecords
        previews=req('POST','computational-record-previews',dict(command_id=uid(),selected_run_ids=[rs,rm]),202)
        guard.run_export_dispatcher(SCOPE,j.native,j.store.path,previews['request_id'])
        preview=req('GET','computational-records/'+previews['request_id']);assert preview['state']=='reviewable',preview
        create=req('POST','computational-records',dict(command_id=uid(),preview_id=preview['request_id'],expected_preview_digest=preview['preview']['preview_digest']),202)
        guard.run_export_dispatcher(SCOPE,j.native,j.store.path,create['request_id'])
        ready=req('GET','computational-records/'+create['request_id']);assert ready['state']=='ready',ready
        download='/api/1/studies/'+j.sid+'/computational-records/'+create['request_id']+'/download'
        response=j.http.get(download);assert response.status_code==200
        raw=response.content;(SCOPE.root/'evidence/approach-native.zip').write_bytes(raw)
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            manifest=json.loads(z.read('manifest.json'));path=SCOPE.root/'evidence/approach-native.aiida';path.write_bytes(z.read('computations.aiida'))
        assert manifest['computational_run_ids']==sorted([r1,rs,rm]) and r2 not in manifest['computational_run_ids']
        assert manifest['approach_summary']==ready['approach_summary']==preview['approach_summary']
        service=ComputationalRecords(j.store,SCOPE.root/'artifacts/offline-inspect')
        _,_,preflight,_=service._collect(j.actor,j.sid,sorted([rs,rm]))
        with ArchiveFormatSqlZip().open(path,'r') as archive:
            inventory,_,_=Export(j.native,preflight).inspect(archive.get_backend())
        assert inspect_record(raw,native_inventory=inventory)==manifest
        assert r2 in manifest['approach_summary']['basis_run_ids']
        with j.store.connection(write=True) as db:
            member=tuple(db.execute('SELECT * FROM memberships WHERE study_id=? AND actor_id=?',(j.sid,j.actor)).fetchone());db.execute('DELETE FROM memberships WHERE study_id=? AND actor_id=?',(j.sid,j.actor))
        assert j.http.get(download).status_code==404
        req('GET','approach/versions/'+vid, status=404)
        with j.store.connection(write=True) as db:db.execute('INSERT INTO memberships VALUES(?,?,?)',member)
        proof=dict(passed=True,actual_public_http=True,private_http_jwt=True,synthetic_retained_programs=False,
            analytical=dict(formula='F=m*v/t; sum=F1+F2; unrelated y=x/2+1',baseline=[3,10,13],higher_mass=[9,10,19],modified=[6,10,16],transferred_affine=2.5,units='N'),
            proposal=proposal,linked=linked,with_basis=with_basis,later=later,model=model,scalar_model=scalar,later_model=later_model,
            configurations=[saved1,saved2,sm,ss],runs=[r1,r2,rm,rs],processes=[n1.uuid,n2.uuid,nm.uuid,ns.uuid],manifest=manifest,
            original_payload_sha256=hashlib.sha256(frozen_bytes).hexdigest(),source_bytes=dict(force=source(force),total=source(total),scalar=source(scalar_raw)),
            modeling_stopped=True,application_restarted=True,no_duplicate_dispatch=True,human_acceptance='pending')
    finally:
        (SCOPE.root/'evidence/approach-native-events.json').write_text(json.dumps(j.events,indent=2))
        (SCOPE.root/'evidence/approach-native-proof.json').write_text(json.dumps(proof,indent=2))
        j.close()
