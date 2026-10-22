"""Public HTTP study answer journeys in scoped synthetic stores.

Runs are recorded through the real submission, bundle and projection code with captured
producer bytes; nothing is executed and no modeling service is called.
"""

import sqlite3

import pytest

from calculation_fixture import seed
from hyprn_mvp_app.store import uid
from test_assumptions_evidence_api import api, evidence_body, generated  # noqa: F401
from test_brief_api import alternative, constraint, content as brief_content, objective


def answer_path(e, suffix=''):
    return '/api/1/studies/' + e['sid'] + '/answer' + suffix


def study_path(e, suffix):
    return '/api/1/studies/' + e['sid'] + '/' + suffix


def framed(e, alternatives=None):
    """A saved brief version with alternatives and two criteria, one calculation version that
    binds both to its outputs, and one recorded run of it."""
    e = dict(e, **seed(e))
    limit, cost = constraint(threshold=151, units=''), objective(units='')
    alternatives = alternatives or [alternative('Kerosene'), alternative('Liquid hydrogen')]
    client = e['client']
    written = client.post(
        study_path(e, 'brief/draft'),
        json=dict(
            command_id=uid(),
            expected_revision=None,
            content=brief_content(alternatives=alternatives, criteria=[limit, cost]),
        ),
    )
    assert written.status_code == 200, written.text
    saved = client.post(
        study_path(e, 'brief/versions'),
        json=dict(command_id=uid(), expected_revision=written.json()['data']['revision']),
    )
    assert saved.status_code == 201, saved.text
    brief = saved.json()['data']['version']['brief_version_id']
    first, second = e['outputs']
    created = client.post(
        study_path(e, 'calculations'),
        json=dict(
            command_id=uid(),
            content=dict(
                schema_version='1',
                name='Cruise points',
                description='',
                model_id=e['config']['model_id'],
                model_revision_id=e['config']['model_revision_id'],
                configuration_revision_ids=[e['config']['configuration_revision_id']],
                design=dict(kind='hand_picked'),
                brief_version_id=brief,
                criterion_bindings=[
                    dict(criterion_id=limit['criterion_id'], output=first),
                    dict(criterion_id=cost['criterion_id'], output=second),
                ],
            ),
        ),
    )
    assert created.status_code == 201, created.text
    run = e['record']([150, 151])
    return dict(
        e,
        brief=brief,
        alternatives=alternatives,
        limit=limit,
        cost=cost,
        calculation=created.json()['data']['calculation_version_id'],
        run=run,
    )


def answer(f, **changes):
    kerosene, hydrogen = (a['alternative_id'] for a in (f['alternatives'] * 2)[:2])
    return (
        dict(
            schema_version='2',
            brief_version_id=f['brief'],
            alternative_mappings=[
                dict(alternative_id=kerosene, calculation_version_ids=[f['calculation']]),
                dict(alternative_id=hydrogen, calculation_version_ids=[]),
            ],
            comparison=[
                dict(
                    alternative_id=kerosene,
                    criterion_id=f['limit']['criterion_id'],
                    calculation_version_id=f['calculation'],
                    run_id=f['run'],
                    note='Cruise point at Mach 5.',
                    evaluation=None,
                    output_name=None,
                )
            ],
            justifications=[
                dict(
                    justification_id=uid(),
                    kind='run',
                    calculation_version_id=f['calculation'],
                    run_id=f['run'],
                    relation='supports',
                    reason='The recorded cruise point stays below the limit.',
                )
            ],
            interpretation=dict(
                interpretation='Kerosene is feasible at the studied point. One cruise point only.',
            ),
            outcome=dict(
                kind='recommended',
                alternative_id=kerosene,
                reason='It meets every constraint; hydrogen has no calculation yet.',
            ),
            decisive_uncertainties=[
                dict(
                    uncertainty_id=uid(),
                    statement='Structural mass fraction',
                    stated_range='0.25 to 0.35',
                    effect='Above 0.33 hydrogen would be preferred.',
                )
            ],
            next_analysis=dict(
                statement='Calculate hydrogen at the same cruise point.',
                resolves='Whether hydrogen also meets the mass limit.',
            ),
            exploration_basis=None,
        )
        | changes
    )


def draft(e, body, expected=None, command=None):
    return e['client'].post(
        answer_path(e, '/draft'),
        json=dict(command_id=command or uid(), expected_revision=expected, content=body),
    )


def save(e, revision, command=None):
    return e['client'].post(
        answer_path(e, '/versions'),
        json=dict(command_id=command or uid(), expected_revision=revision),
    )


@pytest.fixture
def study(api):  # noqa: F811
    return framed(api)


def test_a_new_study_has_no_answer_until_one_is_written(api):  # noqa: F811
    state = api['client'].get(answer_path(api))
    assert state.status_code == 200, state.text
    assert state.json()['data'] == dict(draft=None, latest_version=None)


def test_saving_a_version_pins_the_brief_and_cells_carry_the_cited_run_evaluation(study):
    written = draft(study, answer(study))
    assert written.status_code == 200, written.text
    written = written.json()['data']
    (cell,) = written['content']['comparison']
    # The evaluation is the calculation's own reading of the cited run, never sent or inferred.
    runs = (
        study['client']
        .get(study_path(study, 'calculation-versions/' + study['calculation'] + '/runs'))
        .json()['data']['items']
    )
    expected = next(
        e for e in runs[0]['evaluations'] if e['criterion_id'] == study['limit']['criterion_id']
    )
    assert cell['evaluation'] == expected and expected['outcome'] == 'met'
    forged = answer(study)
    forged['comparison'][0]['evaluation'] = dict(expected, outcome='not_met')
    assert cell['output_name']
    forged['comparison'][0]['output_name'] = 'Untrusted replacement'
    rewritten = draft(study, forged, written['revision']).json()['data']['content']
    assert rewritten['comparison'] == written['content']['comparison']
    current = study['client'].get(answer_path(study)).json()['data']['draft']
    saved = save(study, current['revision'])
    assert saved.status_code == 201, saved.text
    version, continuing = saved.json()['data']['version'], saved.json()['data']['draft']
    assert version['version_number'] == 1 and version['predecessor_version_id'] is None
    assert version['content'] == current['content']
    assert version['content']['brief_version_id'] == study['brief']
    assert continuing['based_on_version_id'] == version['answer_version_id']
    # Later draft edits never change the saved version.
    edited = draft(
        study,
        answer(study, next_analysis=dict(statement='Add a second cruise point.', resolves='')),
        continuing['revision'],
    )
    assert edited.status_code == 200, edited.text
    read = study['client'].get(answer_path(study, '/versions/' + version['answer_version_id']))
    assert read.json()['data'] == version
    second = save(study, edited.json()['data']['revision']).json()['data']['version']
    assert second['version_number'] == 2
    assert second['predecessor_version_id'] == version['answer_version_id']
    page = study['client'].get(answer_path(study, '/versions?limit=1')).json()['data']
    assert [v['version_number'] for v in page['items']] == [2] and page['next_cursor'] == 2
    rest = study['client'].get(answer_path(study, '/versions?before=2')).json()['data']
    assert [v['version_number'] for v in rest['items']] == [1]


def test_at_most_one_answer_head_per_study(study):
    first = draft(study, answer(study)).json()['data']
    assert save(study, first['revision']).status_code == 201
    # A second save from the same, now superseded, revision is refused and writes nothing.
    stale = save(study, first['revision'])
    assert stale.status_code == 409 and stale.json()['error']['code'] == 'stale_revision'
    state = study['client'].get(answer_path(study)).json()['data']
    assert state['latest_version']['version_number'] == 1
    with study['store'].connection(write=True) as db:
        heads = db.execute(
            'SELECT COUNT(*) FROM study_answer_drafts WHERE study_id=?', (study['sid'],)
        ).fetchone()[0]
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                'INSERT INTO study_answer_versions VALUES(?,?,?,?)',
                (uid(), study['sid'], 1, '{}'),
            )
    assert heads == 1


def test_saved_versions_cannot_be_rewritten_or_deleted_in_storage(study):
    written = draft(study, answer(study)).json()['data']
    save(study, written['revision'])
    with study['store'].connection(write=True) as db:
        with pytest.raises(sqlite3.DatabaseError):
            db.execute("UPDATE study_answer_versions SET payload='{}'")
    with study['store'].connection(write=True) as db:
        with pytest.raises(sqlite3.DatabaseError):
            db.execute('DELETE FROM study_answer_versions')


def test_a_version_states_its_outcome_explicitly(study):
    kerosene = study['alternatives'][0]['alternative_id']
    undecided = draft(study, answer(study, outcome=None)).json()['data']
    refused = save(study, undecided['revision'])
    assert refused.status_code == 422, refused.text
    assert refused.json()['error']['fields'][0]['path'] == '/content/outcome'
    # No-go is for a study with one alternative; a reason is always stated.
    no_go = draft(
        study,
        answer(study, outcome=dict(kind='no_go', alternative_id=kerosene, reason='Too heavy.')),
        undecided['revision'],
    )
    assert no_go.status_code == 422, no_go.text
    silent = draft(
        study,
        answer(
            study,
            outcome=dict(kind='no_recommendation', basis='contested_evidence', reason=' '),
        ),
        undecided['revision'],
    )
    assert silent.status_code == 400, silent.text
    insufficient = draft(
        study,
        answer(
            study,
            outcome=dict(
                kind='no_recommendation',
                basis='insufficient_evidence',
                reason='Hydrogen has not been calculated.',
            ),
        ),
        undecided['revision'],
    )
    assert insufficient.status_code == 200, insufficient.text
    saved = save(study, insufficient.json()['data']['revision'])
    assert saved.status_code == 201, saved.text
    assert (
        saved.json()['data']['version']['content']['outcome']['basis']
        == 'insufficient_evidence'
    )


def test_a_single_alternative_takes_go_or_no_go(api):  # noqa: F811
    single = framed(api, alternatives=[alternative('Kerosene')])
    kerosene = single['alternatives'][0]['alternative_id']
    body = answer(
        single,
        alternative_mappings=[
            dict(alternative_id=kerosene, calculation_version_ids=[single['calculation']])
        ],
        outcome=dict(kind='no_go', alternative_id=kerosene, reason='It misses the range.'),
    )
    written = draft(single, body)
    assert written.status_code == 200, written.text
    assert save(single, written.json()['data']['revision']).status_code == 201


def test_a_version_pins_a_brief_and_maps_every_alternative(study):
    unpinned = draft(
        study,
        answer(
            study,
            brief_version_id=None,
            alternative_mappings=[],
            comparison=[],
            outcome=dict(
                kind='no_recommendation', basis='insufficient_evidence', reason='Early.'
            ),
        ),
    ).json()['data']
    refused = save(study, unpinned['revision'])
    assert refused.status_code == 422
    assert refused.json()['error']['fields'][0]['path'] == '/content/brief_version_id'
    partial = answer(study)
    partial['alternative_mappings'] = partial['alternative_mappings'][:1]
    written = draft(study, partial, unpinned['revision']).json()['data']
    refused = save(study, written['revision'])
    assert refused.status_code == 422, refused.text
    assert refused.json()['error']['fields'][0]['path'] == '/content/alternative_mappings'
    assert study['client'].get(answer_path(study)).json()['data']['latest_version'] is None


def test_an_answer_cites_only_records_of_its_own_study(study):
    other_study = study['store'].create_study(study['actor'], uid(), 'Another decision')
    other = framed(dict(study, sid=other_study['study_id']))
    evidence = study['client'].post(study_path(other, 'evidence'), json=evidence_body(other))
    assert evidence.status_code == 201, evidence.text
    foreign_evidence = evidence.json()['data']['evidence_version_id']
    kerosene = study['alternatives'][0]['alternative_id']
    mapped = answer(study)
    foreign = [
        answer(study, brief_version_id=other['brief']),
        answer(
            study,
            alternative_mappings=[
                dict(alternative_id=kerosene, calculation_version_ids=[other['calculation']])
            ],
            comparison=[],
        ),
        answer(
            study,
            comparison=[dict(mapped['comparison'][0], run_id=other['run'])],
        ),
        answer(
            study,
            justifications=[
                dict(
                    justification_id=uid(),
                    kind='evidence_version',
                    evidence_version_id=foreign_evidence,
                    relation='context',
                    reason='Another study.',
                )
            ],
        ),
        answer(
            study,
            justifications=[
                dict(
                    mapped['justifications'][0],
                    calculation_version_id=other['calculation'],
                    run_id=other['run'],
                )
            ],
        ),
        answer(
            study,
            exploration_basis=dict(
                calculation_version_id=other['calculation'], estimate_id=None, shown_outputs=[]
            ),
        ),
    ]
    for body in foreign:
        response = draft(study, body)
        assert response.status_code == 422, (body, response.text)
    assert study['client'].get(answer_path(study)).json()['data']['draft'] is None
    created = study['client'].post(study_path(study, 'evidence'), json=evidence_body(study))
    own = created.json()['data']['evidence_version_id']
    accepted = answer(
        study,
        justifications=[
            dict(
                justification_id=uid(),
                kind='evidence_version',
                evidence_version_id=own,
                relation='challenges',
                reason='Reported structural fractions are higher.',
            ),
            dict(
                justification_id=uid(),
                kind='calculation_version',
                calculation_version_id=study['calculation'],
                relation='context',
                reason='The cruise calculation.',
            ),
        ],
        exploration_basis=dict(
            calculation_version_id=study['calculation'],
            estimate_id=None,
            shown_outputs=[study['outputs'][0]],
        ),
    )
    assert draft(study, accepted).status_code == 200


def test_cells_cite_mapped_calculations_runs_and_criteria_of_the_pinned_brief(study):
    cell = answer(study)['comparison'][0]
    refusals = [
        dict(cell, criterion_id=uid()),
        dict(cell, alternative_id=study['alternatives'][1]['alternative_id']),
        dict(cell, run_id=uid()),
    ]
    for refused in refusals:
        response = draft(study, answer(study, comparison=[refused]))
        assert response.status_code == 422, (refused, response.text)
    assert draft(study, answer(study, comparison=[cell, cell])).status_code == 422
    estimate = answer(
        study,
        exploration_basis=dict(
            calculation_version_id=study['calculation'], estimate_id=uid(), shown_outputs=[]
        ),
    )
    assert draft(study, estimate).status_code == 422


def test_a_replayed_command_returns_its_result_and_a_changed_body_conflicts(study):
    command, body = uid(), answer(study)
    first = draft(study, body, command=command)
    again = draft(study, body, command=command)
    assert first.status_code == again.status_code == 200
    assert again.json()['data'] == first.json()['data']
    changed = draft(study, answer(study, comparison=[]), command=command)
    assert changed.status_code == 409
    assert changed.json()['error']['code'] == 'command_payload_conflict'
    version_command = uid()
    saved = save(study, first.json()['data']['revision'], command=version_command)
    replayed = save(study, first.json()['data']['revision'], command=version_command)
    assert saved.status_code == 201 and replayed.status_code == 201
    assert replayed.json()['data'] == saved.json()['data']


@pytest.mark.parametrize(
    'query', ['?extra=1', '?limit=0', '?limit=101', '?limit=1&limit=2', '?before=x']
)
def test_unknown_or_invalid_query_fields_are_refused(api, query):  # noqa: F811
    assert api['client'].get(answer_path(api, '/versions') + query).status_code == 400
    assert api['client'].get(answer_path(api) + '?limit=1').status_code == 400


def test_unknown_versions_are_not_found(api):  # noqa: F811
    assert api['client'].get(answer_path(api, '/versions/' + uid())).status_code == 404


def test_the_contract_declares_every_answer_route(generated):  # noqa: F811
    paths = generated['paths']
    assert paths['/studies/{study_id}/answer']['get']['responses']['200']
    assert paths['/studies/{study_id}/answer/versions']['post']['responses']['201']
    for name in ('StudyAnswerContent1', 'StudyAnswerOutcome1', 'StudyAnswerVersionSaved1'):
        assert name in generated['components']['schemas']


def test_exploration_pins_a_finished_estimate_of_its_exact_calculation(api, tmp_path):  # noqa: F811
    from test_calculation_designs_api import (
        FitTransport,
        complete,
        path,
        reference_env,
        sample_request,
    )

    e = reference_env(api, tmp_path)
    first, version = complete(e, sample_request(e))
    target = next(
        dict(instance_id=i['instance_id'], port_id=p['port_id'])
        for i in e['case']['frozen']['model_snapshot']['instances']
        for d in e['case']['frozen']['model_snapshot']['definitions']
        if d['definition_version_id'] == i['definition_version_id']
        for p in d['ports']
        if p['direction'] == 'output'
    )
    request = dict(
        command_id=uid(),
        calculation_version_id=first['calculation_version_id'],
        tolerances=[dict(target=target, absolute=0.1, relative=0.01)],
    )
    accepted = e['client'].post(path(e, 'calculation-estimates'), json=request)
    assert accepted.status_code == 202, accepted.text
    body = dict(
        schema_version='2',
        brief_version_id=None,
        alternative_mappings=[],
        comparison=[],
        justifications=[],
        interpretation=dict(
            interpretation=''
        ),
        outcome=None,
        decisive_uncertainties=[],
        next_analysis=dict(statement='', resolves=''),
        exploration_basis=None,
    )
    body['exploration_basis'] = dict(
        calculation_version_id=first['calculation_version_id'],
        estimate_id=request['command_id'],
        shown_outputs=[],
    )
    assert draft(e, body).status_code == 422
    assert e['estimates'].process_one(FitTransport())
    # An assessed record with unavailable outputs is citable; it supplies no invented value.
    written = draft(e, body)
    assert written.status_code == 200, written.text
    revision = written.json()['data']['revision']
    second, _ = complete(e, sample_request(e))
    body['exploration_basis']['calculation_version_id'] = second['calculation_version_id']
    assert draft(e, body, revision).status_code == 422
    other = e['store'].create_study(e['actor'], uid(), 'Other estimate reader')
    response = e['client'].get(
        '/api/1/studies/'
        + other['study_id']
        + '/calculation-estimates/'
        + request['command_id']
    )
    assert response.status_code == 404


def test_publication_requires_prepared_exploration_but_keeps_the_draft(study):
    body = answer(
        study,
        exploration_basis=dict(
            calculation_version_id=study['calculation'],
            estimate_id=None,
            shown_outputs=[study['outputs'][0]],
        ),
    )
    written = draft(study, body)
    assert written.status_code == 200, written.text
    revision = written.json()['data']['revision']
    refused = save(study, revision)
    assert refused.status_code == 422, refused.text
    assert 'Prepare and check joint exploration' in refused.text
    state = study['client'].get(answer_path(study)).json()['data']
    assert state['latest_version'] is None
    assert state['draft']['revision'] == revision


@pytest.mark.parametrize('field,value', [
    ('qualifications', 'Limited scope'), ('observations', 'Observation'),
    ('open_deliverables', []),
])
def test_current_answer_rejects_retired_authoring_sections(study, field, value):
    content = answer(study)
    content['interpretation'][field] = value
    response = draft(study, content)
    assert response.status_code == 400
    assert study['client'].get(answer_path(study)).json()['data']['draft'] is None


def test_legacy_answer_read_preserves_bytes_and_edit_carries_scientific_limits(study):
    from hyprn_mvp_app.contracts import canonical, digest
    from hyprn_mvp_app.study_answer import current_content, validate_answer

    first = draft(study, answer(study)).json()['data']
    saved = save(study, first['revision']).json()['data']['version']
    legacy = dict(saved, schema_version='1', answer_version_id=uid(), version_number=2)
    legacy['content'] = dict(saved['content'], schema_version='1')
    legacy['content']['comparison'] = [
        {k: v for k, v in cell.items() if k != 'output_name'}
        for cell in legacy['content']['comparison']
    ]
    legacy['content']['interpretation'] = dict(
        observations='Observed margin.', interpretation='Screen only.',
        qualifications='No qualification claim.',
        open_deliverables=[dict(deliverable_id=uid(), text='Validate the pump.')],
    )
    legacy['digest'] = digest({k: v for k, v in legacy.items() if k != 'digest'})
    validate_answer('StudyAnswerVersion1', legacy)
    with study['store'].connection(write=True) as db:
        db.execute('INSERT INTO study_answer_versions VALUES(?,?,?,?)', (
            legacy['answer_version_id'], study['sid'], 2, canonical(legacy).decode(),
        ))
    url = answer_path(study, '/versions/' + legacy['answer_version_id'])
    assert study['client'].get(url).json()['data'] == legacy
    edited = current_content(legacy['content'])
    assert 'No qualification claim.' in edited['interpretation']['interpretation']
    assert 'Validate the pump.' in edited['next_analysis']['statement']
    current = study['client'].get(answer_path(study)).json()['data']['draft']
    response = draft(study, edited, current['revision'])
    assert response.status_code == 200, response.text
    assert response.json()['data']['schema_version'] == '2'
    assert study['client'].get(url).json()['data'] == legacy


def test_run_list_reports_execution_not_storage_state(study):
    path = study_path(study, 'runs')
    rows = study['client'].get(path).json()['data']
    listed = next(r for r in rows if r['run_id'] == study['run'])
    detail = study['client'].get(path + '/' + study['run']).json()['data']
    assert listed['state'] == 'recorded'
    assert listed['execution_summary']['status'] == 'completed'
    assert detail['execution_summary'] == listed['execution_summary']
    assert 'execution_diagnostic' not in detail


@pytest.mark.parametrize('slot', ['mapping', 'justification', 'exploration'])
def test_answer_publication_refuses_two_versions_of_one_analysis(study, slot):
    client = study['client']
    first = client.get(study_path(study,
        'analysis-versions/' + study['calculation'])).json()['data']
    revised = client.post(study_path(study,
        'analyses/' + first['calculation_id'] + '/versions'), json=dict(
            command_id=uid(), expected_version_id=first['calculation_version_id'],
            content=first['content']))
    assert revised.status_code == 201, revised.text
    second = revised.json()['data']['calculation_version_id']
    content = answer(study)
    if slot == 'mapping':
        content['alternative_mappings'][1]['calculation_version_ids'] = [second]
    elif slot == 'justification':
        content['justifications'][0]['calculation_version_id'] = second
    else:
        content['exploration_basis'] = dict(calculation_version_id=second,
            estimate_id=None, shown_outputs=[study['outputs'][0]])
    written = draft(study, content)
    assert written.status_code == 200, written.text
    published = save(study, written.json()['data']['revision'])
    assert published.status_code == 422, published.text
    assert 'multiple versions of the same analysis' in published.text
    retained = client.get(answer_path(study)).json()['data']
    assert retained['latest_version'] is None
    assert retained['draft']['content'] == written.json()['data']['content']


def test_distinct_analyses_reuse_runs_and_compatibility_paths_without_new_execution(study):
    client = study['client']
    first = client.get(study_path(study,
        'analysis-versions/' + study['calculation'])).json()['data']
    command = dict(command_id=uid(), content=first['content'])
    second = client.post(study_path(study, 'analyses'), json=command)
    assert second.status_code == 201, second.text
    version = second.json()['data']
    replay = client.post(study_path(study, 'calculations'), json=command)
    assert replay.status_code == 201, replay.text
    assert replay.json()['data'] == version
    members = client.get(study_path(study,
        'analysis-versions/' + version['calculation_version_id'] + '/runs'))
    assert members.status_code == 200, members.text
    assert study['run'] in [r['run_id'] for r in members.json()['data']['items']]
    content = answer(study)
    content['alternative_mappings'][1]['calculation_version_ids'] = [
        version['calculation_version_id']]
    written = draft(study, content)
    assert written.status_code == 200, written.text
    published = save(study, written.json()['data']['revision'])
    assert published.status_code == 201, published.text


def test_answer_refuses_distinct_analyses_using_two_versions_of_one_model(study):
    from copy import deepcopy
    from calculation_fixture import sibling
    client = study['client']
    first = client.get(study_path(study,
        'analysis-versions/' + study['calculation'])).json()['data']
    frozen = client.get(study_path(study,
        'configurations/' + study['config']['configuration_revision_id'])).json()['data']
    model_version = uid()
    config_id = sibling(study, frozen, model_revision_id=model_version)
    content = deepcopy(first['content'])
    content.update(model_revision_id=model_version, configuration_revision_ids=[config_id])
    created = client.post(study_path(study, 'analyses'),
        json=dict(command_id=uid(), content=content))
    assert created.status_code == 201, created.text
    value = answer(study)
    value['alternative_mappings'][1]['calculation_version_ids'] = [
        created.json()['data']['calculation_version_id']]
    written = draft(study, value)
    assert written.status_code == 200, written.text
    published = save(study, written.json()['data']['revision'])
    assert published.status_code == 422, published.text
    assert 'multiple versions of the same model' in published.text
