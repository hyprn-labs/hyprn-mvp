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
from units_native_fixture import UnitsJourney,source,literal
from combined_fixture import brief_constraint
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


def expectation(name,threshold,units):
    """A brief constraint in the exact output units with the analytical tolerances."""
    return brief_constraint(name,'eq',threshold,units,relative_tolerance=EXPECT['relative_tolerance'],
        absolute_tolerance=EXPECT['absolute_tolerance'])


def output(detail,target):
    return next(o for o in detail['history']['results']['outputs'] if o['target']==target)


def near(actual,expected):
    assert actual==pytest.approx(expected,rel=EXPECT['relative_tolerance'],abs=EXPECT['absolute_tolerance'])


def test_native_compounds_histories_and_archive():
    j=UnitsJourney(SCOPE,BACKEND);proof={'passed':False};records=[];selected=[]
    try:
        j.start();e=j.evidence('Independent SI scale expectations');eid=e['evidence_version_id']
        # Criteria are study brief constraints in the exact output units. They are evaluated
        # only through calculations over the recorded runs; no configuration or run holds one.
        expected={family['name']:{role:expectation(family['name']+' '+role,family['factor'],
            family['destination']) for role in ('connected','explicit','downstream')}
            for family in EXPECT['families']}
        first_family=EXPECT['families'][0]
        violated=brief_constraint(first_family['name']+' source above its input','eq',2,
            first_family['source'])
        brief=j.brief_version([c for f in expected.values() for c in f.values()]+[violated])
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
            assert model['schema_version']=='4'
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
                # The private configuration 5 prepares artifact 4, which pins result protocol 3.
                prepared=j.prepared(model)
                assert prepared['schema_version']=='4' and prepared['result_protocol_version']=='3'
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
            cfg=j.configuration(model,family['name'],[literal(s['x'],1,src,eid),literal(x['x'],1,src,eid)],e)
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
            # The analytical expectations are judged in a calculation, never inside the run.
            own=expected[family['name']]
            bindings=[(own['connected']['criterion_id'],c['y']),(own['explicit']['criterion_id'],x['y'])]
            if first:bindings.append((violated['criterion_id'],s['y']))
            outcomes={k:v['outcome'] for k,v in j.evaluate([saved],brief,bindings)[rid].items()}
            assert [outcomes[k] for k,_ in bindings]==['met','met']+(['not_met'] if first else [])
            records.append((rid,detail,saved,canonical(j.payload(rid))))
            # Separate native program uses retained source units; destination conversion
            # is performed by pinned problem.set_val with the exact source result link.
            _,down=j.model(family['name']+' downstream',[component('downstream',dst),instance('downstream')])
            t=targets(down,'downstream')
            binding=dict(kind='run_result',target=t['x'],source_run_id=rid,source_output=s['y'],
                expected_results_digest=digest(detail['history']['results']),
                provenance=dict(kind='manual',statement='Exact prior native scalar',evidence_version_ids=[eid]))
            ds=j.save_configuration(j.configuration(down,'Retained '+family['name'],[binding],e))
            dr,dh,dn=j.execute(ds)
            near(output(dh,t['y'])['value'],factor);assert output(dh,t['y'])['units']==dst
            evaluated=j.evaluate([ds],brief,[(own['downstream']['criterion_id'],t['y'])])[dr]
            assert evaluated[own['downstream']['criterion_id']]['outcome']=='met'
            assert any(link.node.uuid==node.outputs.results.uuid for link in dn.base.links.get_incoming().all())
            records.append((dr,dh,ds,canonical(j.payload(dr))));selected.append(dr)
        # A legacy string-unit model can no longer be configured; its upgrade to format 4 by a
        # typed edit keeps the old version, ports and source byte-exact.
        draft,legacy=j.model('Legacy dimensionless',[component('legacy','',version='2'),instance('legacy')],version='2')
        assert legacy['schema_version']=='2'
        updated=j.edit(draft,[dict(kind='rename_model',name='Mixed current')])
        d=next(d for d in updated['definitions'] if d['name']=='legacy')
        updated=j.edit(updated,[dict(kind='revise_definition',temp_key='v2',definition_id=d['definition_id'],
            expected_definition_version_id=d['definition_version_id'],changes=[dict(kind='rename_definition',name='typed')])])
        v2=next(d for d in updated['definitions'] if d['name']=='typed')
        inst=next(i for i in updated['instances'] if i['definition_version_id']==d['definition_version_id'])
        updated=j.edit(updated,[dict(kind='replace_local_instance_version',instance_id=inst['instance_id'],
            expected_definition_version_id=d['definition_version_id'],version_ref=dict(definition_version_id=v2['definition_version_id']))])
        mixed=j.commit(updated)
        assert mixed['schema_version']=='4'
        assert next(v for v in mixed['definitions'] if v['definition_version_id']==d['definition_version_id'])==d
        assert mixed['source_files']==legacy['source_files']
        assert j.prepared(mixed)['schema_version']=='4'
        assert not j.canary()['candidate_side_effect']
        assert j.process_count()==6
        # Assess the already retained native records through ordinary study HTTP commands.
        # Answer authoring must neither launch science nor change any retained run/configuration.
        from approach_native_fixture import step

        bindings = [
            dict(
                binding_id=uid(),
                model_id=saved['configuration']['model_id'],
                model_revision_id=saved['configuration']['model_revision_id'],
            )
            for _, _, saved, _ in records
        ]
        method = step('Compare explicit conversions with retained-result reuse')
        method.update(
            purpose='Test the independently specified SI scale relationships.',
            rationale='Compare independently executed identity models and exact retained reuse.',
            intent=dict(
                transformation='Scalar identity with explicit compatible SI unit conversion.',
                inputs='Specified unit-bearing scalars and exact prior recorded outputs.',
                outputs='Converted scalar outputs with retained units.',
                depends_on_step_ids=[],
            ),
            implementation_state='linked',
            implementation_refs=[
                dict(kind='model', binding_id=binding['binding_id']) for binding in bindings
            ],
        )
        approach = j.save_approach(dict(
            schema_version='1',
            question='Do the native fixture calculations preserve the specified SI relationships?',
            scope='Synthetic scalar identity models with explicit units and exact retained inputs.',
            limitations='Unit-conversion evidence only; no engineering-validity claim.',
            open_questions='Independent engineering validation is outside this fixture.',
            model_bindings=bindings,
            steps=[method],
            assumptions=[],
            basis_refs=[],
        ))
        answer_path = 'approach/versions/' + approach['version']['approach_version_id'] + '/answers'
        assert j.request('GET', answer_path)['items'] == []
        assert all(
            result['availability'] == 'available'
            for _, detail, _, _ in records[:2]
            for result in detail['history']['results']['outputs']
        )
        answer_command = dict(
            schema_version='1', command_id=uid(), expected_revision=None,
            approach_version_id=approach['version']['approach_version_id'],
            observations='The two cited native runs retain available outputs and explicit units.',
            interpretation=(
                'Direct and result-linked calculations agree with the specified SI scale '
                'expectations for this synthetic identity-model comparison.'
            ),
            qualifications=['This fixture does not validate an engineering model.'],
            open_deliverables=['Independent engineering validation remains outside this fixture.'],
            basis=dict(
                configuration_revision_ids=[
                    saved['configuration']['configuration_revision_id']
                    for _, _, saved, _ in records[:2]
                ],
                run_ids=[rid for rid, _, _, _ in records[:2]],
                evidence_version_ids=[eid],
            ),
        )
        first_answer = j.request('POST', 'answers', answer_command, 201)
        synthesis_command = dict(
            answer_command, command_id=uid(), expected_revision=first_answer['answer_version_id'],
            observations='Six retained native runs cover the stated SI conversion fixture.',
            interpretation=(
                'The examined computations support unit conversion and exact retained reuse; '
                'they establish no physical feasibility conclusion.'
            ),
            basis=dict(
                configuration_revision_ids=[
                    saved['configuration']['configuration_revision_id']
                    for _, _, saved, _ in records
                ],
                run_ids=[rid for rid, _, _, _ in records],
                evidence_version_ids=[eid],
            ),
        )
        study_answer = j.request('POST', 'answers', synthesis_command, 201)
        revised_answer = j.request('POST', 'answers', dict(
            synthesis_command, command_id=uid(),
            expected_revision=study_answer['answer_version_id'],
            qualifications=[
                'This fixture does not validate an engineering model.',
                'The comparison covers only the explicitly referenced unit relationships.',
            ],
        ), 201)
        assert revised_answer['previous_version_id'] == study_answer['answer_version_id']
        assert j.request('GET', 'answers/' + first_answer['answer_version_id']) == first_answer
        assert j.request('GET', 'answers/' + study_answer['answer_version_id']) == study_answer
        assert j.process_count() == 6
        j.offline();j.restart_web()
        for answer in (first_answer, revised_answer, study_answer):
            assert j.request('GET', 'answers/' + answer['answer_version_id']) == answer
        assert {
            answer['answer_version_id'] for answer in j.request('GET', answer_path)['items']
        } == {revised_answer['answer_version_id']}
        receipt = j.request(
            'GET', 'commands/' + answer_command['command_id'] + '?category=answer_save'
        )
        assert receipt['recovery'] == 'adopt' and receipt['result'] == first_answer
        assert j.process_count() == 6
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
            assert manifest['computational_run_ids']==sorted([records[number*2][0],selection])
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
        j.scientific_answers = dict(
            approach_version_id=approach['version']['approach_version_id'],
            first_answer=first_answer, revised_answer=revised_answer,
            study_answer=study_answer,
        )
        browser=j.browser(records)
        proof=dict(passed=True,browser=browser,analytical=EXPECT,records=[dict(run_id=r,history=h,configuration=s,payload_sha256=hashlib.sha256(b).hexdigest()) for r,h,s,b in records],
            scientific_answers=dict(
                approach_version_id=approach['version']['approach_version_id'],
                first_answer=first_answer, revised_answer=revised_answer,
                study_answer=study_answer, application_restart=True,
            ),
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
