"""Fresh public/native regression: versioned references, early validation, retained failure.

No live study or retained calculation is replayed. Candidate executes only in the
attested worker; all authoring uses production HTTP/JWT and native generation.
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
import json

from checks import PROJECTION_SCOPE as SCOPE, NATIVE_BACKEND as BACKEND
from approach_native_fixture import ApproachJourney, source, step, literal
from hyprn_mvp_app.store import canonical, digest, uid


def test_investigation_native_journey():
    j = ApproachJourney(SCOPE, BACKEND)
    proof = {}
    try:
        j.start(); req = j.request
        note = j.evidence('Intentional failure regression'); eid = note['evidence_version_id']
        original_source = b"outputs['y'] = inputs['x'] * 2\n"
        draft, original = j.model('Versioned diagnostic component', [
            dict(kind='create_definition', temp_key='d', definition_kind='explicit_component', name='Pressure screening',
                 ports=[dict(temp_key=k, direction='input' if k == 'x' else 'output', name=k, code_symbol=k, value_type='real_scalar', units='N') for k in ('x', 'y')], source=source(original_source)),
            dict(kind='instantiate', temp_key='c', version_ref=dict(temp_key='d'))])
        instance = next(i for i in original['instances'] if i['instance_id'] != original['root_instance_id'])
        old = next(d for d in original['definitions'] if d['definition_version_id'] == instance['definition_version_id'])
        failure_source = b"# <%= File.write('/store/forbidden-candidate-import', 'bad') %>\nassert False, 'Required pressure closure not reached'\noutputs['y'] = inputs['x'] * 3\n"
        edits = [dict(kind='revise_definition', temp_key='v2', definition_id=old['definition_id'], expected_definition_version_id=old['definition_version_id'], changes=[dict(kind='set_source', source=source(failure_source))]),
                 dict(kind='replace_local_instance_version', instance_id=instance['instance_id'], expected_definition_version_id=old['definition_version_id'], version_ref=dict(temp_key='v2'))]
        mp = 'models/' + original['model_id']
        edit_body = dict(schema_version='2', command_id=uid(), expected_revision=draft['draft_revision'], edits=edits)
        draft = req('POST', mp+'/edits', edit_body)
        revised = req('POST', mp+'/commits', dict(command_id=uid(), expected_revision=draft['draft_revision']))
        selected = next(i for i in revised['instances'] if i['instance_id'] == instance['instance_id'])
        definition = next(d for d in revised['definitions'] if d['definition_version_id'] == selected['definition_version_id'])
        assert old['definition_version_id'] != definition['definition_version_id']
        assert {p['port_id'] for p in old['ports']} == {p['port_id'] for p in definition['ports']}
        assert old in revised['definitions']
        binding = dict(binding_id=uid(), model_id=revised['model_id'], model_revision_id=revised['model_revision_id'])
        method = step('Screen pressure closure'); method.update(implementation_state='linked', implementation_refs=[dict(kind='instance', binding_id=binding['binding_id'], instance_id=instance['instance_id']), dict(kind='port', binding_id=binding['binding_id'], instance_id=instance['instance_id'], port_id=definition['ports'][0]['port_id'])])
        content = dict(schema_version='1', question='Can a revised component remain traceable?', scope='Isolated regression', limitations='Intentional computational failure', open_questions='', model_bindings=[binding], steps=[method], assumptions=[], cases=[], basis_refs=[])
        approach = j.save_approach(content)
        target = dict(instance_id=instance['instance_id'], port_id=next(p['port_id'] for p in definition['ports'] if p['code_symbol'] == 'x'))
        candidate = j.configuration(revised, 'Intentional failure', [literal(target, 2, 'N', eid)], [], dict(approach_version_id=approach['version']['approach_version_id']), note)
        good_preview = req('POST', 'configurations/preview', candidate)
        bad_candidate = deepcopy(good_preview['resolved_candidate'])
        bad_candidate['inputs'][0]['provenance']['evidence_version_ids'].append(eid)
        bad = deepcopy(candidate); bad['inputs'][0]['provenance']['evidence_version_ids'].append(eid)
        error = req('POST', 'configurations/preview', bad, 422)
        assert any('/inputs/0/provenance/evidence_version_ids' in d['path'] for d in error['fields']), error
        save_error = req('POST', 'configurations', dict(command_id=uid(), configuration_id=None, expected_revision=None, configuration=bad, expected_preview_digest=digest(bad_candidate)), 422)
        assert any('/inputs/0/provenance/evidence_version_ids' in d['path'] for d in save_error['fields']), save_error
        saved = j.save_configuration(candidate)
        assert j.process_count() == 0 and not j.canary()['candidate_side_effect']
        body = dict(command_id=uid(), configuration_revision_id=saved['configuration']['configuration_revision_id'])
        run = req('POST', 'runs', body, 202); rid = run['run_id']
        j.dispatch(rid, prepare_only=True)
        assert j.process_count() == 0 and not j.canary()['candidate_side_effect']
        payload = j.payload(rid)
        files = {p:base64.b64decode(b) for p,b in payload['bundle']['files'].items()}
        assert 'app/lib/whats_opt/openmdao_generator.rb' in files['provenance/generator.json'].decode()
        prepared = json.loads(files['preparation.json'])
        assert prepared['entrypoint']['protocol'] == 'hyprn_mvp.openmdao.program/1'
        for f in prepared['files']:
            assert hashlib.sha256(files[f['path']]).hexdigest() == f['sha256']
        j.offline()  # All execution materials must already be retained.
        j.dispatch(rid)
        detail = req('GET', 'runs/'+rid)
        assert detail['state'] == 'recorded' and not detail['history']['errors'], detail
        results = detail['history']['results']
        assert results['execution']['state'] == 'failed'
        diagnostic = results['execution']['message']
        assert 'AssertionError' in diagnostic and 'Required pressure closure not reached' in diagnostic, diagnostic
        assert ':2' in diagnostic and 'sources/' in diagnostic, diagnostic
        assert all(o['availability'] != 'available' and o['value'] is None for o in results['outputs'])
        assert j.process_count() == 1
        history = deepcopy(detail['history']); frozen = canonical(j.payload(rid))
        j.dispatch(rid); assert j.process_count() == 1
        j.restart_web()
        assert req('GET', 'runs/'+rid)['history'] == history
        assert req('GET', 'configurations/'+saved['configuration']['configuration_revision_id']) == saved
        assert req('GET', 'approach/versions/'+approach['version']['approach_version_id']) == approach
        assert canonical(j.payload(rid)) == frozen
        assert req('POST', 'runs', body, 202)['run_id'] == rid
        proof = dict(passed=True, actual_public_http=True, private_http_jwt=True, native_generator=True,
                     original_model=original, revised_model=revised, approach=approach, configuration=saved,
                     duplicate_preview_error=error, duplicate_save_error=save_error, run=detail,
                     prepared=prepared, processes=1, model_outage_execution=True, restart_history_exact=True,
                     authored_source_sha256=hashlib.sha256(failure_source).hexdigest(), human_acceptance='pending')
    finally:
        (SCOPE.root/'evidence/investigation-native-events.json').write_text(json.dumps(j.events, indent=2))
        (SCOPE.root/'evidence/investigation-native-proof.json').write_text(json.dumps(proof, indent=2))
        j.close()
