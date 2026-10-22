"""Calculation tools through the real application, route allowlist and owners.

A writer delegation creates a calculation from saved configuration versions of one model version
and binds the study criteria of a saved brief version to outputs named "<component>.<port>";
a new version keeps every field it does not name and needs the latest version the agent read.
An output whose unit differs from its criterion's, or that the model version lacks, is refused
with the tool's own field and nothing is saved. Reference marks are set and cleared without
changing any configuration. Every write is attributed to the agent for its user. The private
modeling side is an in-process double; no code runs. Fresh synthetic store only.
"""

import pytest

from modeling_double import ModelingDouble
from writer_tools import READER, WRITER, attributed, offered, one, writer_study

VERSION = '53000000-0000-4000-8000-000000000012'
WRITES = (
    'create_analysis',
    'save_analysis_version',
    'set_reference_mark',
    'clear_reference_mark',
)
READS = (
    'list_analyses',
    'get_analysis',
    'list_analysis_versions',
    'get_analysis_runs',
    'list_reference_marks',
)


@pytest.fixture
def env(tmp_path):
    double = ModelingDouble()
    env = writer_study(tmp_path, modeling=double)
    double.bind(env['store'], env['sid'])
    double.declare(VERSION, 'fuel_fraction', {'kind': 'dimensionless'})
    env['model'] = double.model_id
    draft = one(
        env,
        'update_study_brief',
        {
            'expected_revision': None,
            'content': {
                'question': 'Which fuel should the aircraft use?',
                'criteria': [
                    {
                        'kind': 'constraint',
                        'name': 'Design range',
                        'operator': 'ge',
                        'threshold': 9000,
                        'units': 'km',
                    },
                    {
                        'kind': 'objective',
                        'name': 'Take-off mass',
                        'direction': 'minimize',
                        'units': 'kg',
                    },
                ],
            },
        },
    )
    one(env, 'save_study_brief_version', {'expected_revision': draft['revision_token']})
    env['range'], env['mass'] = (c['id'] for c in draft['criteria'])
    env['configurations'] = [
        one(env, 'save_configuration', configuration(env, name))['configuration_version']['id']
        for name in ('Liquid hydrogen, 9,000 km', 'Liquid hydrogen, 12,000 km')
    ]
    return env


def configuration(env, name):
    return {
        'name': name,
        'model_id': env['model'],
        'model_version_id': VERSION,
        'inputs': [
            {'quantity': 'Mass closure.payload_mass', 'value': 9500, 'unit': 'kg'},
            {'quantity': 'Mass closure.structural_index', 'value': 0.38, 'unit': 'dimensionless'},
            {'quantity': 'Range.fuel_fraction', 'value': 0.3, 'unit': 'dimensionless'},
        ],
        'default_source': {'authority': 'judgement', 'note': 'historical regression'},
    }


def calculation(env, **changes):
    arguments = {
        'name': 'Liquid hydrogen range points',
        'model_id': env['model'],
        'model_version_id': VERSION,
        'configuration_version_ids': env['configurations'][:1],
        'criterion_bindings': [
            {'criterion_id': env['range'], 'output': 'Range.range'},
            {'criterion_id': env['mass'], 'output': 'Mass closure.mtow'},
        ],
    }
    arguments.update(changes)
    return arguments


def text(named):
    return named['name']['untrusted_content']['text']


def test_a_calculation_binds_brief_criteria_by_output_name_and_is_attributed(env):
    created = one(env, 'create_analysis', calculation(env))
    family = created['calculation']['id']
    first = created['calculation_version']
    assert first['number'] == 1 and created['previous_version'] == {'missing': 'first_version'}
    read = one(env, 'get_analysis', {'calculation_id': family})
    assert read['revision_token'] == first['id']
    assert read['brief_version']['number'] == 1
    assert [text(c) for c in read['configurations']] == ['Liquid hydrogen, 9,000 km']
    assert [text(c['output']) for c in read['criteria']] == ['Range.range', 'Mass closure.mtow']
    assert ('calculation_version', family, first['id'], 'calculation_create') in attributed(env)
    # A new version names only what changes; the bindings and name are kept.
    second = one(
        env,
        'save_analysis_version',
        {
            'calculation_id': family,
            'expected_revision': first['id'],
            'configuration_version_ids': env['configurations'],
        },
    )
    assert second['calculation_version']['number'] == 2 and second['configurations'] == 2
    latest = one(env, 'get_analysis', {'calculation_id': family})
    assert [text(c['output']) for c in latest['criteria']] == ['Range.range', 'Mass closure.mtow']
    assert text(latest['calculation']) == 'Liquid hydrogen range points'
    version = second['calculation_version']['id']
    assert ('calculation_version', family, version, 'calculation_version') in attributed(env)
    stale = one(
        env,
        'save_analysis_version',
        {'calculation_id': family, 'expected_revision': first['id'], 'name': 'Renamed'},
    )
    assert stale.category == 'conflict'
    older = one(env, 'get_analysis', {'calculation_version_id': first['id']})
    assert older['configurations'][0]['id'] == env['configurations'][0]
    assert 'revision_token' not in older
    versions = one(env, 'list_analysis_versions', {'calculation_id': family})['versions']
    assert [v['calculation_version']['number'] for v in versions] == [2, 1]
    listed = one(env, 'list_analyses', {'model_version_id': VERSION})['calculations']
    assert [c['calculation']['id'] for c in listed] == [family]
    runs = one(env, 'get_analysis_runs', {'calculation_version_id': version})
    assert runs['runs'] == [] and runs['brief_version']['number'] == 1
    # A newer brief version is pinned only when named: new bindings keep the pinned version.
    draft = one(env, 'get_study_brief', {})
    revised = one(
        env,
        'update_study_brief',
        {'expected_revision': draft['revision_token'], 'content': {'question': 'Which fuel?'}},
    )
    one(env, 'save_study_brief_version', {'expected_revision': revised['revision_token']})
    third = one(
        env,
        'save_analysis_version',
        {
            'calculation_id': family,
            'expected_revision': version,
            'criterion_bindings': [{'criterion_id': env['range'], 'output': 'Range.range'}],
        },
    )
    rebound = one(env, 'get_analysis', {'calculation_id': family})
    assert third['calculation_version']['number'] == 3 and rebound['brief_version']['number'] == 1
    assert [c['output'].get('missing') for c in rebound['criteria']] == [
        None,
        'criterion_not_bound',
    ]


def test_an_unbound_criterion_stays_unbound_and_refused_bindings_save_nothing(env):
    created = one(env, 'create_analysis', calculation(env, criterion_bindings=[]))
    read = one(env, 'get_analysis', {'calculation_id': created['calculation']['id']})
    assert [c['output'] for c in read['criteria']] == [{'missing': 'criterion_not_bound'}] * 2
    wrong_unit = one(
        env,
        'create_analysis',
        calculation(
            env, criterion_bindings=[{'criterion_id': env['range'], 'output': 'Mass closure.mtow'}]
        ),
    )
    assert wrong_unit.category == 'invalid_input'
    assert wrong_unit.fields[0]['path'] == 'criterion_bindings[0]'
    unknown = one(
        env,
        'create_analysis',
        calculation(env, criterion_bindings=[{'criterion_id': env['range'], 'output': 'Wing.x'}]),
    )
    assert unknown.fields[0]['path'] == 'criterion_bindings[0].output'
    with env['store'].connection() as db:
        assert db.execute('SELECT count(*) FROM calculation_versions').fetchone()[0] == 1


def test_reference_marks_are_set_and_cleared_without_changing_the_configuration(env):
    marked = env['configurations'][0]
    with env['store'].connection() as db:
        before = db.execute('SELECT payload FROM configurations').fetchall()
    assert one(env, 'set_reference_mark', {'configuration_version_id': marked})['reference']
    listed = one(env, 'list_reference_marks', {})['reference_configurations']
    assert [(m['id'], text(m)) for m in listed] == [(marked, 'Liquid hydrogen, 9,000 km')]
    created = one(env, 'create_analysis', calculation(env))
    read = one(env, 'get_analysis', {'calculation_id': created['calculation']['id']})
    assert read['configurations'][0]['reference'] is True
    assert (
        one(env, 'clear_reference_mark', {'configuration_version_id': marked})['reference'] is False
    )
    assert one(env, 'list_reference_marks', {})['reference_configurations'] == []
    with env['store'].connection() as db:
        assert db.execute('SELECT payload FROM configurations').fetchall() == before
    assert ('reference_mark', marked, None, 'reference_mark') in attributed(env)


def test_a_reader_delegation_reads_calculations_but_writes_none(env):
    for name in WRITES:
        assert name in offered(WRITER) and name not in offered(READER)
    for name in READS:
        assert name in offered(READER)
