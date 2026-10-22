"""Study answer tools through the real application and route allowlist.

A writer delegation changes the answer draft section by section and saves versions: a section
left out stays unchanged, a table cell's evaluation comes from the cited run, a stale revision
writes nothing, and a citation outside the study is refused at the tool's own input path. Every
draft and version an agent writes is attributed to the agent for its user. A reader delegation
reads but is offered no write. Fresh synthetic store; the brief, calculation and run are written
by the person through their owners.
"""

from uuid import uuid4

import pytest

from calculation_fixture import seed
from hyprn_mvp_app.brief import Briefs
from hyprn_mvp_app.calculations import Calculations
from hyprn_mvp_app.agent_tools.spec import ToolError
from writer_tools import READER, WRITER, attributed, offered, one, writer_study

WRITES = {'update_study_answer', 'save_study_answer_version'}


def uid():
    return str(uuid4())


@pytest.fixture
def env(tmp_path):
    env = writer_study(tmp_path)
    owner, sid, store = env['owner'], env['sid'], env['store']
    seeded = seed(dict(store=store, actor=owner, sid=sid))
    limit = dict(
        criterion_id=uid(),
        kind='constraint',
        name='Peak response',
        statement='',
        operator='lt',
        threshold=200,
        units='',
        evidence_links=[],
    )
    alternatives = [
        dict(alternative_id=uid(), name='Kerosene', description='', reason=''),
        dict(alternative_id=uid(), name='Liquid hydrogen', description='', reason=''),
    ]
    briefs = Briefs(store)
    draft = briefs.save_draft(
        owner,
        sid,
        dict(
            command_id=uid(),
            expected_revision=None,
            content=dict(
                schema_version='1',
                question='Which fuel?',
                original_question=None,
                elaboration=None,
                scope='',
                alternatives=alternatives,
                criteria=[limit],
                assumptions=[],
                limits=[],
                open_questions=[],
            ),
        ),
    )
    brief = briefs.save_version(
        owner, sid, dict(command_id=uid(), expected_revision=draft['revision'])
    )['version']['brief_version_id']
    config = seeded['config']
    calculation = Calculations(store).create(
        owner,
        sid,
        dict(
            command_id=uid(),
            content=dict(
                schema_version='1',
                name='Cruise points',
                description='',
                model_id=config['model_id'],
                model_revision_id=config['model_revision_id'],
                configuration_revision_ids=[config['configuration_revision_id']],
                design=dict(kind='hand_picked'),
                brief_version_id=brief,
                criterion_bindings=[
                    dict(criterion_id=limit['criterion_id'], output=seeded['outputs'][0])
                ],
            ),
        ),
    )['calculation_version_id']
    run = seeded['record']([150, 151])
    return dict(
        env,
        brief=brief,
        alternatives=[a['alternative_id'] for a in alternatives],
        limit=limit['criterion_id'],
        calculation=calculation,
        run=run,
    )


def framing(env):
    kerosene, hydrogen = env['alternatives']
    return {
        'brief_version_id': env['brief'],
        'alternative_mappings': [
            {'alternative_id': kerosene, 'calculation_version_ids': [env['calculation']]},
            {'alternative_id': hydrogen, 'calculation_version_ids': []},
        ],
        'comparison': [
            {
                'alternative_id': kerosene,
                'criterion_id': env['limit'],
                'calculation_version_id': env['calculation'],
                'run_id': env['run'],
            }
        ],
        'interpretation': {'interpretation': 'The cruise point stays below the limit.'},
    }


def test_answer_tool_preserves_estimate_pin_for_owner_validation(env):
    first = one(env, 'update_study_answer', {'expected_revision': None, 'content': framing(env)})
    refused = one(
        env,
        'update_study_answer',
        {
            'expected_revision': first['revision_token'],
            'content': {
                'exploration_basis': {
                    'calculation_version_id': env['calculation'],
                    'estimate_id': uid(),
                    'shown_outputs': [],
                },
            },
        },
    )
    # A missing estimate must reach the owner and be refused, never silently
    # replaced with null and saved as an apparently successful draft.
    assert isinstance(refused, ToolError)
    assert one(env, 'get_study_answer', {})['revision_token'] == first['revision_token']


def test_the_draft_changes_by_section_versions_freeze_and_writes_are_attributed(env):
    empty = one(env, 'get_study_answer', {})
    assert empty['draft'] == {'missing': 'no_draft'} and empty['revision_token'] is None
    first = one(env, 'update_study_answer', {'expected_revision': None, 'content': framing(env)})
    assert first['changed_sections'] == [
        'alternative_mappings',
        'brief_version_id',
        'comparison',
        'interpretation',
    ]
    (cell,) = first['comparison']
    assert cell['evaluation'] == {
        'outcome': 'met',
        'reason': 'threshold_comparison',
        'value': 150,
        'unit': 'dimensionless',
    }
    assert first['outcome'] == {'missing': 'no_outcome_stated'}
    # A version needs a stated outcome; the refusal names the draft section.
    refused = one(env, 'save_study_answer_version', {'expected_revision': first['revision_token']})
    assert refused.category == 'invalid_input' and refused.fields[0]['path'] == 'draft.outcome'
    kerosene = env['alternatives'][0]
    second = one(
        env,
        'update_study_answer',
        {
            'expected_revision': first['revision_token'],
            'content': {
                'outcome': {
                    'kind': 'recommended',
                    'alternative_id': kerosene,
                    'reason': 'It meets the only constraint; hydrogen is not calculated yet.',
                },
                'decisive_uncertainties': [{'statement': 'Structural mass fraction'}],
            },
        },
    )
    assert second['comparison'] == first['comparison']
    assert second['decisive_uncertainties'][0]['id']
    stale = one(
        env,
        'update_study_answer',
        {'expected_revision': first['revision_token'], 'content': {'comparison': []}},
    )
    assert stale.category == 'conflict' and stale.fields[0]['path'] == 'expected_revision'
    saved = one(env, 'save_study_answer_version', {'expected_revision': second['revision_token']})
    version = saved['answer_version']
    assert version['number'] == 1
    latest = one(env, 'get_study_answer', {'which': 'latest_version'})
    assert latest['answer_version']['id'] == version['id']
    assert latest['outcome']['outcome_kind'] == 'recommended'
    exact = one(env, 'get_study_answer', {'answer_version_id': version['id']})
    assert exact['comparison'] == latest['comparison']
    assert attributed(env) == {
        ('answer_draft', env['sid'], first['revision_token'], 'answer_draft'),
        ('answer_draft', env['sid'], second['revision_token'], 'answer_draft'),
        ('answer_version', env['sid'], version['id'], 'answer_version'),
    }


def test_a_citation_outside_the_study_is_refused_at_its_input_path(env):
    content = framing(env)
    content['comparison'][0]['run_id'] = uid()
    refused = one(env, 'update_study_answer', {'expected_revision': None, 'content': content})
    assert refused.category == 'invalid_input'
    assert refused.fields[0]['path'] == 'content.comparison[0].run_id'
    assert attributed(env) == set()


def test_a_reader_delegation_reads_the_answer_and_is_offered_no_write(env):
    assert 'get_study_answer' in offered(READER)
    assert WRITES <= offered(WRITER) and not WRITES & offered(READER)
    read = one(env, 'get_study_answer', {}, effects=READER, session='reader')
    assert read['revision_token'] is None
