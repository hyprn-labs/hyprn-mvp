"""Ordinary engineering units across real HTTP authoring, execution and result reads."""

# P2 live-runtime fence (deployment/tests/live_fence.py): refuses foreign live resources.
import live_fence  # noqa: E402

live_runtime_fence = live_fence.pytest_fixture('baseline')

import json
from checks import PROJECTION_SCOPE as SCOPE, NATIVE_BACKEND as BACKEND
from units_native_fixture import UnitsJourney, literal, source
from test_units_native import component, instance, targets, output, near


def test_ordinary_engineering_units_through_public_api():
    j = UnitsJourney(SCOPE, BACKEND)
    try:
        j.start()
        e = j.evidence('Independent SI scale expectations')
        eid = e['evidence_version_id']
        # Ordinary engineering dimensions cross the real API, generator and worker together.
        conversions = [
            ('volume', 'cm**3', 'm**3', 1e-6),
            ('surface_density', 'g/m**2', 'kg/m**2', 1e-3),
            ('specific_heat', 'kJ/(kg*K)', 'J/(kg*K)', 1000),
            ('power', 'MW', 'W', 1e6),
            ('torque_energy', 'N*m', 'J', 1),
        ]
        edits = [
            edit
            for name, _, destination, _ in conversions
            for edit in (component(name, destination), instance(name))
        ]
        # A real restricted calculation deliberately lasts beyond the old 20-second bound.
        import base64

        raw = base64.b64decode(edits[0]['source']['bytes'])
        edits[0]['source'] = source(b'import time\ntime.sleep(22)\n' + raw)
        _, ordinary = j.model('Ordinary engineering units', edits)
        assignments = [
            literal(targets(ordinary, name)['x'], 2, source_unit, eid)
            for name, source_unit, _, _ in conversions
        ]
        ordinary_saved = j.save_configuration(
            j.configuration(ordinary, 'Explicit engineering conversions', assignments, [], None, e)
        )
        from tools.study_tools import invoke
        from hyprn_mvp_app.contracts import uid

        class PublicClient:
            def request(self, command):
                reply = j.http.request(
                    command.get('method', 'GET'), command['path'], json=command.get('body')
                )
                return dict(status=reply.status_code, body=reply.json())

        client = PublicClient()

        def run_with_budget(seconds):
            reply = invoke(
                client,
                'submit_run',
                dict(
                    study_id=j.sid,
                    body=dict(
                        command_id=uid(),
                        configuration_revision_id=ordinary_saved['configuration'][
                            'configuration_revision_id'
                        ],
                        execution_budget=dict(wall_seconds=seconds),
                    ),
                ),
            )
            assert reply['status'] == 202, reply
            rid = reply['data']['run_id']
            j.dispatch(rid)
            return invoke(client, 'get_run', dict(study_id=j.sid, run_id=rid))['data']

        ordinary_result = run_with_budget(60)
        assert ordinary_result['history']['results']['execution']['state'] == 'finished', (
            ordinary_result
        )
        diagnostic = ordinary_result['execution_diagnostic']
        assert diagnostic['state'] == 'completed' and diagnostic['wall_seconds'] == 60
        assert diagnostic['elapsed_seconds'] > 20
        from aiida import orm

        node = orm.load_node(
            j.payload(ordinary_result['run_id'])['history']['association']['process_uuid']
        )
        assert node.inputs.wall_seconds.value == 60
        timed_out = run_with_budget(1)
        assert timed_out['history']['results'] is None
        assert timed_out['execution_diagnostic']['state'] == 'timed_out'
        assert timed_out['execution_diagnostic']['wall_seconds'] == 1
        timeout_id = timed_out['run_id']
        for name, _, destination, factor in conversions:
            result = output(ordinary_result, targets(ordinary, name)['y'])
            near(result['value'], 2 * factor)
            assert result['units'] == destination
        import scoped_fixture as guard

        archive_record = j.native.archive_record

        def traced_archive(payload):
            try:
                return archive_record(payload)
            except Exception:
                import traceback

                traceback.print_exc()
                raise

        j.native.archive_record = traced_archive

        preview = j.request(
            'POST',
            'computational-record-previews',
            dict(command_id=uid(), selected_run_ids=[ordinary_result['run_id']]),
            202,
        )
        guard.run_export_dispatcher(SCOPE, j.native, j.store.path, preview['request_id'])
        preview = j.request('GET', 'computational-records/' + preview['request_id'])
        assert preview['state'] == 'reviewable', preview
        created = j.request(
            'POST',
            'computational-records',
            dict(
                command_id=uid(),
                preview_id=preview['request_id'],
                expected_preview_digest=preview['preview']['preview_digest'],
            ),
            202,
        )
        guard.run_export_dispatcher(SCOPE, j.native, j.store.path, created['request_id'])
        assert (
            j.request('GET', 'computational-records/' + created['request_id'])['state'] == 'ready'
        )
        assert j.process_count() == 2
        j.restart_web()
        reread = j.request('GET', 'runs/' + ordinary_result['run_id'])
        assert reread['history']['results'] == ordinary_result['history']['results']
        assert (
            j.request('GET', 'runs/' + timeout_id)['execution_diagnostic']
            == timed_out['execution_diagnostic']
        )
        (SCOPE.root / 'evidence/engineering-units.json').write_text(
            json.dumps(
                {
                    'passed': True,
                    'run_id': ordinary_result['run_id'],
                    'expected_conversions': conversions,
                    'outputs': ordinary_result['history']['results']['outputs'],
                },
                indent=2,
            )
        )
    finally:
        j.close()
