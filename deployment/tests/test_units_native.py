"""Actual restricted native compound conversions and immutable offline records."""
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
from pathlib import Path
import sys
import zipfile

import pytest
from aiida.tools.archive.implementations.sqlite_zip.main import ArchiveFormatSqlZip
from checks import PROJECTION_SCOPE as SCOPE, NATIVE_BACKEND as BACKEND
import scoped_fixture as guard
guard.validate_scope(SCOPE)
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'modeling/tests'))
from units_native_fixture import UnitsJourney,source,literal,criterion
from hyprn_mvp_app.store import canonical,digest,uid,DomainError
from hyprn_mvp_app.computational_export import ComputationalRecords,inspect_record
from hyprn_mvp_integration.computational_export import Export

EXPECT=json.loads((Path(__file__).resolve().parents[2]/'integration/tests/fixtures/units-native-evidence.json').read_text())
# If accidentally imported/executed during authoring this fails and leaves a marker.
# In the worker the explicit calculation returns its real input, never a canned result.
SOURCE=b"import os\nif not os.path.isdir('/output'):\n    open('/store/forbidden-candidate-import','w').write('bad')\n    raise RuntimeError('candidate outside worker')\noutputs['y'] = inputs['x']\n"


def component(key,units,version='3'):
    value=units if version=='2' else ({'kind':'physical','expression':units} if units else {'kind':'dimensionless'})
    return dict(kind='create_definition',temp_key=key,definition_kind='explicit_component',name=key,
        ports=[dict(temp_key=k,direction='input' if k=='x' else 'output',name=k,code_symbol=k,value_type='real_scalar',units=deepcopy(value)) for k in ('x','y')],source=source(SOURCE))


def instance(key):
    return dict(kind='instantiate',temp_key=key+'_instance',version_ref=dict(temp_key=key))


def targets(model,name):
    active={i['definition_version_id'] for i in model['instances']}
    definition=next(d for d in model['definitions'] if d['name']==name and d['definition_version_id'] in active)
    inst=next(i for i in model['instances'] if i['definition_version_id']==definition['definition_version_id'])
    return {p['code_symbol']:dict(instance_id=inst['instance_id'],port_id=p['port_id']) for p in definition['ports']}


def band(target,units,eid):
    # Criterion comparison itself is exact; author an explicit analytical tolerance.
    return [criterion(target,1-EXPECT['relative_tolerance'],units,eid)|{'operator':'ge'},
            criterion(target,1+EXPECT['relative_tolerance'],units,eid)|{'operator':'le'}]


def output(detail,target):
    return next(o for o in detail['history']['results']['outputs'] if o['target']==target)


def near(actual,expected):
    assert actual==pytest.approx(expected,rel=EXPECT['relative_tolerance'],abs=EXPECT['absolute_tolerance'])


def test_native_compounds_histories_and_archive():
    j=UnitsJourney(SCOPE,BACKEND);proof={'passed':False};records=[];selected=[]
    try:
        j.start();e=j.evidence('Independent SI scale expectations');eid=e['evidence_version_id']
        for family in EXPECT['families']:
            src,dst,factor=family['source'],family['destination'],family['factor']
            edits=[component('source',src),instance('source'),component('connected',dst),instance('connected'),
                   component('explicit',dst),instance('explicit'),
                   dict(kind='connect',temp_key='wire',source_ref=dict(instance_temp_key='source_instance',definition_temp_key='source',port_temp_key='y'),
                        target_ref=dict(instance_temp_key='connected_instance',definition_temp_key='connected',port_temp_key='x'))]
            # Unreferenced valid unspecified content cannot poison active readiness.
            unused=component('unused',dst)
            for p in unused['ports']:p['units']={'kind':'unspecified'}
            edits.append(unused)
            first=family['name']=='specific_energy'
            if first:
                for port in edits[0]['ports']:port['units']={'kind':'unspecified'}
            draft,model=j.model(family['name'],edits)
            if first:
                old=next(d for d in model['definitions'] if d['name']=='source')
                with pytest.raises(DomainError):j.prepared(model)
                draft=j.edit(draft,[dict(kind='revise_definition',temp_key='resolved',
                    definition_id=old['definition_id'],expected_definition_version_id=old['definition_version_id'],
                    changes=[dict(kind='update_port',port_id=p['port_id'],fields=dict(units={'kind':'physical','expression':src})) for p in old['ports']])])
                # A newer definition alone never unblocks the exact active v1.
                with pytest.raises(DomainError):j.prepared(j.commit(draft))
                newer=next(d for d in draft['definitions'] if d['definition_id']==old['definition_id'] and d['definition_version_id']!=old['definition_version_id'])
                inst=next(i for i in draft['instances'] if i['definition_version_id']==old['definition_version_id'])
                draft=j.edit(draft,[dict(kind='replace_local_instance_version',instance_id=inst['instance_id'],
                    expected_definition_version_id=old['definition_version_id'],version_ref=dict(definition_version_id=newer['definition_version_id']))])
                model=j.commit(draft)
                assert next(d for d in model['definitions'] if d['definition_version_id']==old['definition_version_id'])==old
                assert [p['port_id'] for p in newer['ports']]==[p['port_id'] for p in old['ports']]
                assert j.prepared(model)['schema_version']=='3'
                def later_draft():
                    changed=j.edit(draft,[dict(kind='revise_definition',temp_key='later',
                        definition_id=newer['definition_id'],expected_definition_version_id=newer['definition_version_id'],
                        changes=[dict(kind='set_source',source=source(b"outputs['y'] = inputs['x'] * 9\n"))])])
                    latest=next(d for d in changed['definitions'] if d['definition_id']==newer['definition_id'] and d['definition_version_id'] not in {old['definition_version_id'],newer['definition_version_id']})
                    changed=j.edit(changed,[dict(kind='replace_local_instance_version',instance_id=inst['instance_id'],
                        expected_definition_version_id=newer['definition_version_id'],version_ref=dict(definition_version_id=latest['definition_version_id']))])
                    return changed
                j.after_prepare=later_draft
            s,c,x=[targets(model,k) for k in ('source','connected','explicit')]
            cfg=j.configuration(model,family['name'],[literal(s['x'],1,src,eid),literal(x['x'],1,src,eid)],
                band(c['y'],src,eid)+band(x['y'],src,eid),None,e)
            if first:cfg['criteria'].append(criterion(s['y'],2,src,eid))
            # Unsupported/incompatible/affine/overflow fail before any process exists.
            before=j.process_count()
            for unit,value in [('USD',1),('kg',1),(src,1e308)]:
                bad=deepcopy(cfg);bad['inputs'][1].update(units=unit,value=value)
                invalid=j.request('POST','configurations/preview',bad)
                assert not invalid['compatibility']['compatible'] and invalid['compatibility']['diagnostics']
                j.request('POST','configurations',dict(command_id=uid(),configuration_id=None,expected_revision=None,
                    configuration=bad,expected_preview_digest=invalid['candidate_digest']),422)
            assert j.process_count()==before
            saved=j.save_configuration(cfg);rid,detail,node=j.execute(saved)
            near(output(detail,s['y'])['value'],1)
            for target in (c['y'],x['y']):
                near(output(detail,target)['value'],factor)
                assert output(detail,target)['units']==dst
            outcomes={k['criterion_id']:k['outcome'] for k in detail['history']['results']['criteria']}
            assert all(outcomes[k['criterion_id']]==('violated' if first and k is cfg['criteria'][-1] else 'met') for k in cfg['criteria'])
            records.append((rid,detail,saved,canonical(j.payload(rid))))
            # Separate native program uses retained source units; destination conversion
            # is performed by pinned problem.set_val with the exact source result link.
            _,down=j.model(family['name']+' downstream',[component('downstream',dst),instance('downstream')])
            t=targets(down,'downstream')
            binding=dict(kind='run_result',target=t['x'],source_run_id=rid,source_output=s['y'],
                expected_results_digest=digest(detail['history']['results']),
                provenance=dict(kind='manual',statement='Exact prior native scalar',evidence_version_ids=[eid]))
            ds=j.save_configuration(j.configuration(down,'Retained '+family['name'],[binding],band(t['y'],src,eid),None,e))
            dr,dh,dn=j.execute(ds)
            near(output(dh,t['y'])['value'],factor);assert output(dh,t['y'])['units']==dst
            assert all(k['outcome']=='met' for k in dh['history']['results']['criteria'])
            assert any(link.node.uuid==node.outputs.results.uuid for link in dn.base.links.get_incoming().all())
            records.append((dr,dh,ds,canonical(j.payload(dr))));selected.append(dr)
        # A new run preserves the legacy model's string-unit convention.
        draft,legacy=j.model('Legacy dimensionless',[component('legacy','',version='2'),instance('legacy')],version='2')
        t=targets(legacy,'legacy')
        legacy_saved=j.save_configuration(j.configuration(legacy,'Legacy zero',[literal(t['x'],0,'',eid)],[criterion(t['y'],0,'',eid)],None,e))
        # Use the shared execution helper for this current run of a legacy model.
        from approach_native_fixture import ApproachJourney
        lr,lh,ln=ApproachJourney.execute(j,legacy_saved)
        near(output(lh,t['y'])['value'],0);assert output(lh,t['y'])['units']==''
        records.append((lr,lh,legacy_saved,canonical(j.payload(lr))));selected.append(lr)
        # Real legacy -> typed edit keeps old version/ports/source byte-exact.
        updated=j.edit(draft,[dict(kind='rename_model',name='Mixed current')])
        d=next(d for d in updated['definitions'] if d['name']=='legacy')
        updated=j.edit(updated,[dict(kind='revise_definition',temp_key='v2',definition_id=d['definition_id'],
            expected_definition_version_id=d['definition_version_id'],changes=[dict(kind='rename_definition',name='typed')])])
        v2=next(d for d in updated['definitions'] if d['name']=='typed')
        inst=next(i for i in updated['instances'] if i['definition_version_id']==d['definition_version_id'])
        updated=j.edit(updated,[dict(kind='replace_local_instance_version',instance_id=inst['instance_id'],
            expected_definition_version_id=d['definition_version_id'],version_ref=dict(definition_version_id=v2['definition_version_id']))])
        mixed=j.commit(updated)
        assert next(v for v in mixed['definitions'] if v['definition_version_id']==d['definition_version_id'])==d
        assert mixed['source_files']==legacy['source_files']
        assert j.prepared(mixed)['schema_version']=='3'
        assert not j.canary()['candidate_side_effect']
        assert j.process_count()==7
        j.offline();j.restart_web()
        for rid,history,saved,raw in records:
            assert j.request('GET','runs/'+rid)['history']==history['history']
            assert j.request('GET','configurations/'+saved['configuration']['configuration_revision_id'])==saved
            assert canonical(j.payload(rid))==raw
        rejected=j.request('POST','computational-record-previews',dict(command_id=uid(),selected_run_ids=selected),413)
        assert rejected['fields'][0]['code']=='expanded_bytes_limit'
        archives=[]
        for number,selection in enumerate(selected):
            previews=j.request('POST','computational-record-previews',dict(command_id=uid(),selected_run_ids=[selection]),202)
            guard.run_export_dispatcher(SCOPE,j.native,j.store.path,previews['request_id'])
            preview=j.request('GET','computational-records/'+previews['request_id']);assert preview['state']=='reviewable',preview
            create=j.request('POST','computational-records',dict(command_id=uid(),preview_id=preview['request_id'],expected_preview_digest=preview['preview']['preview_digest']),202)
            guard.run_export_dispatcher(SCOPE,j.native,j.store.path,create['request_id'])
            ready=j.request('GET','computational-records/'+create['request_id']);assert ready['state']=='ready',ready
            response=j.http.get('/api/1/studies/'+j.sid+'/computational-records/'+create['request_id']+'/download')
            assert response.status_code==200,response.text
            raw=response.content;(SCOPE.root/('evidence/units-native-'+str(number)+'.zip')).write_bytes(raw)
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                manifest=json.loads(archive.read('manifest.json'))
                path=SCOPE.root/('evidence/units-native-'+str(number)+'.aiida');path.write_bytes(archive.read('computations.aiida'))
            expected=[records[number*2][0],selection] if number<3 else [lr]
            assert manifest['computational_run_ids']==sorted(expected)
            service=ComputationalRecords(j.store,SCOPE.root/'artifacts/offline-inspect')
            _,_,preflight,_=service._collect(j.actor,j.sid,[selection])
            with ArchiveFormatSqlZip().open(path,'r') as archive:
                inventory,_,_=Export(j.native,preflight).inspect(archive.get_backend())
            assert inspect_record(raw,native_inventory=inventory)==manifest
            archives.append(dict(selected_run_id=selection,manifest=manifest,native_inventory=inventory))

        assert set().union(*(set(a['manifest']['computational_run_ids']) for a in archives))=={r[0] for r in records}
        # Restart the exact model store and check the retained native model revisions.
        j.docker('start',j.name)
        import time
        for _ in range(80):
            try:
                assert j.private('GET','/models/'+legacy['model_id']+'/revisions/'+legacy['model_revision_id'])==legacy
                break
            except DomainError:time.sleep(.25)
        else:raise AssertionError('Model did not restart')
        assert j.private('GET','/models/'+mixed['model_id']+'/revisions/'+mixed['model_revision_id'])==mixed
        for rid,history,saved,raw in records:
            assert j.request('GET','runs/'+rid)['history']==history['history']
        browser=j.browser(records)
        proof=dict(passed=True,browser=browser,analytical=EXPECT,records=[dict(run_id=r,history=h,configuration=s,payload_sha256=hashlib.sha256(b).hexdigest()) for r,h,s,b in records],
            legacy=legacy,mixed=mixed,archives=archives,aggregate_archive_refusal=rejected,selected_run_ids=selected,
            modeling_outage=True,application_restart=True,modeling_restart=True,actual_http_jwt=True,
            attestation=j.native.require_attestation(),human_acceptance='pending')
    finally:
        (SCOPE.root/'evidence/units-native-events.json').write_text(json.dumps(j.events,indent=2))
        (SCOPE.root/'evidence/units-native-proof.json').write_text(json.dumps(proof,indent=2))
        j.close()


@pytest.fixture(scope='module')
def static_service():
    from units_model_fixture import PrivateModel
    value=PrivateModel()
    try:yield value
    finally:value.close()


@pytest.mark.parametrize('case',[
    'test_exact_active_version_closure_and_retained_unused',
    'test_all_active_ports_and_unused_definition_readiness',
    'test_package_ancestry_import_restore_and_conflicting_definition',
    'test_actionable_unsupported_incompatible_and_prepare_diagnostics'])
def test_actual_private_scope_and_inert_import(static_service,case):
    import test_unit_declarations as native
    getattr(native,case)(static_service)


@pytest.mark.parametrize('expression',["m'","m\n","__import__('os')","m.real","degC"])
def test_malicious_and_affine_rejected_atomically(static_service,expression):
    from test_unit_declarations import create,edits,edit
    c=static_service;m=create(c);attempt=edits({'kind':'physical','expression':'K'})
    attempt[0]['ports'][0]['units']['expression']=expression
    edit(c,m,attempt,status=422)
    assert c.call('GET','/models/'+m['model_id'])['data']==m


@pytest.mark.parametrize('failure',[None,BrokenPipeError,ConnectionResetError,RuntimeError])
def test_http_fixture_response_disconnect_boundary(failure):
    from types import SimpleNamespace
    from combined_fixture import write_http_response
    calls=[]
    def write(content):
        calls.append(content)
        if failure:raise failure('fixture write')
    handler=SimpleNamespace(send_response=lambda status:calls.append(status),
        send_header=lambda key,value:calls.append((key,value)),end_headers=lambda:None,
        wfile=SimpleNamespace(write=write))
    response=SimpleNamespace(status_code=200,content=b'exact retained bytes',
        headers=SimpleNamespace(multi_items=lambda:[('content-type','application/json'),('content-length','wrong')]))
    if failure is RuntimeError:
        with pytest.raises(RuntimeError,match='fixture write'):write_http_response(handler,response)
    else:assert write_http_response(handler,response)==(failure is None)
    assert calls==[200,('content-type','application/json'),('Content-Length','20'),b'exact retained bytes']


def test_native_mixed_legacy_selected_repair():
    """One authentic mixed process; explanatory variants never change Model2."""
    from approach_native_fixture import step
    from hyprn_mvp_app.scientific_configuration import project_scientific_configuration
    j=UnitsJourney(SCOPE,BACKEND);proof={'passed':False,'scientific_process_budget':1};records=[]
    try:
        j.start();assert j.process_count()==0
        e=j.evidence('Mixed exact legacy reuse');eid=e['evidence_version_id']
        _,legacy=j.model('Retained legacy force',[component('legacy','N','2'),instance('legacy'),
            component('unused_dimensionless','','2')],version='2')
        original=canonical(legacy);target=targets(legacy,'legacy')
        package=j.private('GET','/models/'+legacy['model_id']+'/export?revision='+legacy['model_revision_id'])
        assert package['schema_version']=='2'
        assert any(p['units']=='' for d in legacy['definitions'] for p in d['ports'])
        variants=[]
        for kind in ('physical','unspecified'):
            edit=component('explanation','N')
            for port in edit['ports']:port['units']={'kind':kind,**({'expression':'N'} if kind=='physical' else {})}
            _,explanation=j.model('Explanatory '+kind,[edit,instance('explanation')])
            bindings=[dict(binding_id=uid(),model_id=m['model_id'],model_revision_id=m['model_revision_id']) for m in (legacy,explanation)]
            primary=step('Use retained legacy force');primary.update(implementation_state='linked',implementation_refs=[dict(kind='model',binding_id=bindings[0]['binding_id'])])
            explanatory=step('Read explanatory '+kind);et=targets(explanation,'explanation')['y']
            explanatory.update(implementation_state='linked',implementation_refs=[dict(kind='port',binding_id=bindings[1]['binding_id'],**et)])
            content=dict(schema_version='1',question='Can exact legacy science retain new explanations?',scope='One authored scalar identity',
                limitations='Fixture evidence only',open_questions='Human acceptance pending',model_bindings=bindings,
                steps=[primary,explanatory],assumptions=[],cases=[],basis_refs=[])
            approach=j.save_approach(content)
            config=j.configuration(legacy,'Mixed '+kind,[literal(target['x'],3,'N',eid)],[criterion(target['y'],3,'N',eid)],
                dict(approach_version_id=approach['version']['approach_version_id'],case_id=None),e)
            preview=j.request('POST','configurations/preview',config)
            assert preview['compatibility']['compatible'],preview
            saved=j.save_configuration(config)
            assert saved['schema_version']=='5' and canonical(saved['model_snapshot'])==original
            assert saved['approach_closure']==approach['closure']
            assert j.request('GET','configurations/'+saved['configuration']['configuration_revision_id'])==saved
            private=project_scientific_configuration(saved['configuration'])
            assert private['schema_version']=='3' and 'unit_declarations/1' not in private['required_capabilities']
            prepared=j.private('POST','/models/'+legacy['model_id']+'/prepare-execution',dict(command_id=uid(),
                model_revision_id=legacy['model_revision_id'],configuration_snapshot=private,configuration_digest=private['digest']))
            assert prepared['schema_version']=='3'
            assert prepared['result_protocol_version']=='2'
            assert prepared['required_capabilities']==legacy['required_capabilities']
            assert j.private('GET','/models/'+legacy['model_id']+'/revisions/'+legacy['model_revision_id'])==legacy
            assert j.private('GET','/models/'+legacy['model_id']+'/export?revision='+legacy['model_revision_id'])==package
            assert j.process_count()==0 and not j.canary()['candidate_side_effect']
            variants.append(dict(kind=kind,model=explanation,approach=approach,configuration=saved,preview=preview,private=private,prepared=prepared))
        # Scientific expectation is authored before execution: y=x, x=3 N => y=3 N.
        proof.update(variants=variants,selected_model=legacy,selected_model_sha256=hashlib.sha256(original).hexdigest(),package=package,
            expected=dict(relation='y = x',input=3,output=3,units='N'),processes_before=0,preparation_processes=0)
        (SCOPE.root/'evidence/mixed-pre-execution.json').write_text(json.dumps(proof,indent=2))
        saved=variants[1]['configuration'];rid,detail,node=j.execute(saved)
        proof.update(science_succeeded=True,run_id=rid,process_uuid=node.uuid,processes_after=j.process_count())
        (SCOPE.root/'evidence/mixed-science-retained.json').write_text(json.dumps(proof,indent=2))
        near(output(detail,target['y'])['value'],3);assert output(detail,target['y'])['units']=='N'
        payload=j.payload(rid);raw=canonical(payload);bundle=payload['bundle']
        files={p:base64.b64decode(b) for p,b in bundle['files'].items()}
        assert bundle['manifest']['schema_version']=='10'
        assert bundle['manifest']['input_schema_version']=='6'
        assert bundle['manifest']['result_protocol_version']=='2'
        assert bundle['manifest']['required_capabilities']==legacy['required_capabilities']
        assert json.loads(files['model.json'])==legacy
        assert json.loads(files['configuration.json'])==saved['configuration']
        assert json.loads(files['approach/closure.json'])==saved['approach_closure']
        assert detail['history']['model_snapshot']==legacy and detail['history']['approach_closure']==saved['approach_closure']
        seed=j.request('GET','runs/'+rid+'/modified-run-seed')
        assert seed['schema_version']=='4' and seed['model_snapshot']==legacy and seed['source_configuration']==saved['configuration']
        assert seed['approach_closure']==saved['approach_closure']
        modified=deepcopy(seed['configuration']);modified['name']='Mixed modified without dispatch'
        modified['context_source']['choice_confirmed']=True
        changed=j.save_configuration(modified)
        assert changed['model_snapshot']==legacy and changed['approach_closure']==saved['approach_closure']
        assert j.process_count()==1
        records=[(rid,detail,saved,raw)]
        preview=j.request('POST','computational-record-previews',dict(command_id=uid(),selected_run_ids=[rid]),202)
        guard.run_export_dispatcher(SCOPE,j.native,j.store.path,preview['request_id'])
        preview=j.request('GET','computational-records/'+preview['request_id']);assert preview['state']=='reviewable',preview
        create=j.request('POST','computational-records',dict(command_id=uid(),preview_id=preview['request_id'],expected_preview_digest=preview['preview']['preview_digest']),202)
        guard.run_export_dispatcher(SCOPE,j.native,j.store.path,create['request_id'])
        ready=j.request('GET','computational-records/'+create['request_id']);assert ready['state']=='ready',ready
        response=j.http.get('/api/1/studies/'+j.sid+'/computational-records/'+create['request_id']+'/download')
        assert response.status_code==200
        archive_bytes=response.content;(SCOPE.root/'evidence/mixed-native.zip').write_bytes(archive_bytes)
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            manifest=json.loads(archive.read('manifest.json'))
            path=SCOPE.root/'evidence/mixed-native.aiida';path.write_bytes(archive.read('computations.aiida'))
        assert manifest['computational_run_ids']==[rid]
        service=ComputationalRecords(j.store,SCOPE.root/'artifacts/mixed-offline-inspect')
        _,_,preflight,_=service._collect(j.actor,j.sid,[rid])
        with ArchiveFormatSqlZip().open(path,'r') as archive:
            inventory,_,_=Export(j.native,preflight).inspect(archive.get_backend())
        assert inspect_record(archive_bytes,native_inventory=inventory)==manifest
        assert j.process_count()==1 and canonical(j.payload(rid))==raw
        # Archive is already authenticated before presentation-only checks.
        browser=j.browser(records,mixed=dict(variants=variants,seed=seed,modified=changed,
            archive_id=create['request_id'],archive_manifest=manifest,archive_sha256=hashlib.sha256(archive_bytes).hexdigest()))
        j.restart_web()
        assert j.request('GET','runs/'+rid)['history']==detail['history']
        assert j.request('GET','runs/'+rid+'/modified-run-seed')==seed
        for variant in variants:
            s=variant['configuration'];assert j.request('GET','configurations/'+s['configuration']['configuration_revision_id'])==s
        assert canonical(j.payload(rid))==raw
        proof.update(passed=True,browser=browser,seed=seed,modified=changed,history=detail,
            archive=dict(manifest=manifest,native_inventory=inventory,sha256=hashlib.sha256(archive_bytes).hexdigest()),
            retained_payload_sha256=hashlib.sha256(raw).hexdigest(),retained_file_hashes={p:hashlib.sha256(b).hexdigest() for p,b in files.items()},
            application_restart=True,modeling_outage=True,actual_http_jwt=True,attestation=j.native.require_attestation(),human_acceptance='pending')
    finally:
        (SCOPE.root/'evidence/mixed-native-events.json').write_text(json.dumps(j.events,indent=2))
        (SCOPE.root/'evidence/mixed-native-proof.json').write_text(json.dumps(proof,indent=2))
        j.close()
