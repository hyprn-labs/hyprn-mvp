"""Ordinary engineering units across real HTTP authoring, execution and result reads."""

# P2 live-runtime fence (deployment/tests/live_fence.py): refuses foreign live resources.
import live_fence  # noqa: E402

live_runtime_fence = live_fence.pytest_fixture('baseline')

import json
from checks import PROJECTION_SCOPE as SCOPE, NATIVE_BACKEND as BACKEND
from units_native_fixture import UnitsJourney, literal
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
        _, ordinary = j.model('Ordinary engineering units', edits)
        assignments = [
            literal(targets(ordinary, name)['x'], 2, source_unit, eid)
            for name, source_unit, _, _ in conversions
        ]
        ordinary_saved = j.save_configuration(
            j.configuration(ordinary, 'Explicit engineering conversions', assignments, [], None, e)
        )
        _, ordinary_result, _ = j.execute(ordinary_saved)
        for name, _, destination, factor in conversions:
            result = output(ordinary_result, targets(ordinary, name)['y'])
            near(result['value'], 2 * factor)
            assert result['units'] == destination
        assert j.process_count() == 1
        j.restart_web()
        reread = j.request('GET', 'runs/' + ordinary_result['run_id'])
        assert reread['history']['results'] == ordinary_result['history']['results']
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
