"""Explicit UI-only evaluation domains, kept outside generic application logic."""

from copy import deepcopy
import json

from hyprn_mvp_app.contracts import uid
from test_exploration_native import joint_fixture


def prepare(j, manifest, root):
    path = root / 'artifacts/exploration-controls.json'
    if path.exists() and json.loads(path.read_text()).get('fixture_version') == 2:
        return json.loads(path.read_text())
    fuel_sid = manifest['study_id']
    j.sid = fuel_sid
    basis = manifest['fit']['basis']
    free = [p for p in basis['inputs'] if p['binding']['kind'] == 'free']
    # Bounds are explicit evaluation declarations, not recommended physical domains.
    ranges = [
        (5.8, 6.2, None, None),
        (0.1, 0.3, None, 'volume'),
        (-0.1, 0.2, None, None),
        (40, 50, None, None),
        (8000000, 10000000, None, None),
        (500000, 600000, None, 'mass'),
        (500000, 600000, None, 'mass'),
        (700, 900, None, None),
        (0.1, 0.3, None, 'volume'),
        (50, 150, 1, None),
        (0.0005, 0.0015, None, None),
        (1, 2, None, None),
        (0.1, 1, None, None),
        (0.5, 1, None, None),
    ]
    # Inventory order is resolved from the exact source configuration targets,
    # not from display names; the tracer basis preserves model occurrence order.
    assert len(free) == len(ranges) == 14
    dimensions = [
        dict(
            target=p['target'],
            units=p['binding']['assignment']['units'],
            lower=lo,
            upper=hi,
            step=step,
            covary_group=group,
            common_key=None,
        )
        for p, (lo, hi, step, group) in zip(free, ranges, strict=True)
    ]
    fuel_design = j.request(
        'POST',
        'exploration-designs',
        dict(
            schema_version='1',
            command_id=uid(),
            answer_version_id=basis['answer_version_id'],
            category_dimensions=[],
            combinations=[
                dict(
                    categories=[],
                    configuration_revision_id=basis['configuration_revision_id'],
                    model_id=basis['model_id'],
                    model_revision_id=basis['model_revision_id'],
                    initial_axis=manifest['fit']['request']['axis'],
                    dimensions=dimensions,
                )
            ],
            rationale='Declared browser evaluation ranges only; no physical validity claim.',
        ),
        201,
    )
    study = j.http.post(
        '/api/1/studies', json=dict(command_id=uid(), name='Independent category interaction')
    ).json()['data']
    j.sid = study['study_id']
    body, ports = joint_fixture(j, all_combinations=True)
    combos = []
    for combo in body['combinations']:
        frozen = j.request('GET', 'configurations/' + combo['configuration_revision_id'])
        c = frozen['configuration']
        model = frozen['model_snapshot']
        definitions = {d['definition_version_id']: d for d in model['definitions']}
        names = {
            (i['instance_id'], p['port_id']): p['code_symbol']
            for i in model['instances']
            for p in definitions[i['definition_version_id']]['ports']
        }
        controls = []
        for p in c['inputs']:
            name = names[p['target']['instance_id'], p['target']['port_id']]
            controls.append(
                dict(
                    target=p['target'],
                    units=p['units'],
                    lower=0,
                    upper=10,
                    step=1,
                    covary_group=None,
                    common_key=name if name in ('x', 'y') else None,
                )
            )
        combos.append(
            dict(
                categories=combo['categories'],
                configuration_revision_id=combo['configuration_revision_id'],
                model_id=c['model_id'],
                model_revision_id=c['model_revision_id'],
                initial_axis=next(
                    p['target']
                    for p in c['inputs']
                    if names[p['target']['instance_id'], p['target']['port_id']] == 'x'
                ),
                dimensions=controls,
            )
        )
    answer_id = body['combinations'][0]['answer_version_id']
    declared = deepcopy(body['category_dimensions'])
    declared[1]['values'].append('unsupported')
    generic_design = j.request(
        'POST',
        'exploration-designs',
        dict(
            schema_version='1',
            command_id=uid(),
            answer_version_id=answer_id,
            category_dimensions=declared,
            combinations=combos,
            rationale='Generic x*y with two independent declared dimensions.',
        ),
        201,
    )
    result = dict(
        fixture_version=2,
        fuel_design=fuel_design,
        generic_design=generic_design,
        generic_study_id=j.sid,
        ports=ports,
    )
    path.write_text(json.dumps(result))
    j.sid = fuel_sid
    return result
