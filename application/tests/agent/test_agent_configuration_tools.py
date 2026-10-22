"""Configuration preview and save through the real application, route allowlist and owners.

A writer delegation names inputs by port against the exact model version, gives
every input an explicit value and unit and a typed source the tool renders into its provenance
statement, previews without saving and saves exactly what it previewed, with the preview digest
kept inside the tool. A saved configuration carries no criteria: they are evaluated in
calculations. A new version needs the latest version the agent read. Every saved
version is attributed to the agent for its user; refused input saves nothing. The private
modeling side is an in-process double; no code runs. Fresh synthetic store only.
"""

import json

import pytest

from modeling_double import ModelingDouble
from writer_tools import READER, WRITER, attributed, offered, one, writer_study

VERSION = '53000000-0000-4000-8000-000000000012'


@pytest.fixture
def env(tmp_path):
    double = ModelingDouble()
    env = writer_study(tmp_path, modeling=double)
    double.bind(env['store'], env['sid'])
    double.declare(VERSION, 'fuel_fraction', {'kind': 'dimensionless'})
    env['double'], env['model'] = double, double.model_id
    return env


def configuration(env, **changes):
    evidence = one(
        env,
        'add_evidence',
        {
            'title': 'Mission requirements',
            'note': 'Payload of 100 passengers with baggage: 9,500 kg.',
            'scope': {'kind': 'study'},
        },
    )
    arguments = {
        'name': 'Liquid hydrogen, 9,000 km',
        'model_id': env['model'],
        'model_version_id': VERSION,
        'inputs': [
            {
                'quantity': 'Mass closure.payload_mass',
                'value': 9500,
                'unit': 'kg',
                'source': {
                    'authority': 'source',
                    'evidence_version_ids': [evidence['id']],
                    'locator': 'p. 12',
                },
            },
            {'quantity': 'Mass closure.structural_index', 'value': 0.38, 'unit': 'dimensionless'},
            {'quantity': 'Range.fuel_fraction', 'value': 0.3, 'unit': 'dimensionless'},
        ],
        'default_source': {'authority': 'judgement', 'note': 'historical regression'},
        'assumptions': [{'statement': 'Cruise at constant Mach number.'}],
    }
    arguments.update(changes)
    return arguments


def test_a_preview_resolves_names_renders_sources_and_saves_nothing(env):
    previewed = one(env, 'preview_configuration', configuration(env))
    assert previewed['compatible'] is True and previewed['missing_inputs'] == []
    rows = [row['untrusted_content']['text'] for row in previewed['inputs']]
    assert rows[0]['source'] == 'Mission requirements, p. 12'
    assert rows[1]['source'] == 'Judgement: historical regression'
    assert rows[1]['value'] == 0.38 and rows[1]['unit'] == 'dimensionless'
    with env['store'].connection() as db:
        assert db.execute('SELECT count(*) FROM configurations').fetchone()[0] == 0
    partial = one(
        env, 'preview_configuration', configuration(env, inputs=configuration(env)['inputs'][:1])
    )
    assert partial['missing_inputs'] == ['Mass closure.structural_index', 'Range.fuel_fraction']


def test_a_saved_configuration_pins_its_inputs_and_is_attributed(env):
    saved = one(env, 'save_configuration', configuration(env))
    version = saved['configuration_version']
    assert saved['previous_version'] == {'missing': 'first_version'}
    read = one(env, 'get_configuration', {'configuration_version_id': version['id']})
    assert [i['value'] for i in read['inputs']] == [9500, 0.38, 0.3]
    assert read['criteria'] == {'missing': 'evaluated_in_calculations'}
    listed = one(env, 'list_configurations', {})['configurations']
    assert [c['criteria'] for c in listed] == [{'missing': 'evaluated_in_calculations'}]
    with env['store'].connection() as db:
        stored = json.loads(db.execute('SELECT payload FROM configurations').fetchone()[0])
    assert stored['configuration']['schema_version'] == '6'
    assert 'criteria' not in stored['configuration']
    assert read['mode'] == 'deterministic'
    family = version['configuration_id']
    assert ('configuration_version', family, version['id'], 'configuration') in attributed(env)
    revised = one(
        env,
        'save_configuration',
        configuration(
            env,
            name='Liquid hydrogen, 9,500 km',
            configuration_id=family,
            expected_revision=version['id'],
        ),
    )
    assert revised['previous_version']['id'] == version['id']
    stale = one(
        env,
        'save_configuration',
        configuration(env, configuration_id=family, expected_revision=version['id']),
    )
    assert stale.category == 'conflict'


def test_refused_inputs_name_the_tool_field_and_save_nothing(env):
    unknown = one(
        env,
        'preview_configuration',
        configuration(env, inputs=[{'quantity': 'Wing.span', 'value': 30, 'unit': 'm'}]),
    )
    assert unknown.category == 'invalid_input' and unknown.fields[0]['path'] == 'inputs[0].quantity'
    both = one(
        env,
        'preview_configuration',
        configuration(
            env,
            inputs=[
                {
                    'quantity': 'Mass closure.payload_mass',
                    'value': 1,
                    'unit': 'kg',
                    'from_run': '5c000000-0000-4000-8000-000000000001',
                }
            ],
        ),
    )
    assert both.category == 'invalid_input' and both.fields[0]['path'] == 'inputs[0]'
    unsourced = one(env, 'preview_configuration', configuration(env, default_source=None))
    assert unsourced.category == 'invalid_input'
    arguments = configuration(env)
    del arguments['default_source']
    unsourced = one(env, 'save_configuration', arguments)
    assert unsourced.fields[0]['path'] == 'inputs[1].source'
    criteria = [{'quantity': 'Range.range', 'operator': 'ge', 'threshold': 1, 'unit': 'km'}]
    for name in ('criteria', 'approach_version_id'):
        value = criteria if name == 'criteria' else '5c000000-0000-4000-8000-000000000002'
        refused = one(env, 'preview_configuration', configuration(env, **{name: value}))
        assert refused.category == 'invalid_input', name
    with env['store'].connection() as db:
        assert db.execute('SELECT count(*) FROM configurations').fetchone()[0] == 0


def test_a_reader_delegation_is_offered_neither_preview_nor_save(env):
    for name in ('preview_configuration', 'save_configuration'):
        assert name in offered(WRITER) and name not in offered(READER)
