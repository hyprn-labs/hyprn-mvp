"""Public HTTP calculation and reference mark journeys in scoped synthetic stores.

Runs are recorded through the real submission, bundle and projection code with captured
producer bytes; nothing is executed and no modeling service is called.
"""

import copy
import json
import sqlite3

import pytest

from calculation_fixture import insert_configuration, seed, sibling
from hyprn_mvp_app.criterion_evaluation import evaluate_run
from hyprn_mvp_app.store import digest, uid
from hyprn_mvp_integration.results import evaluate_criteria
from fastapi.testclient import TestClient
from hyprn_mvp_app import auth as auth_module
from hyprn_mvp_app.api import create_app
from hyprn_mvp_app.auth import Auth
from test_assumptions_evidence_api import api, generated, ORIGIN, NoModeling  # noqa: F401
from test_brief_api import constraint, content, objective


def study_path(e, suffix):
    return '/api/1/studies/' + e['sid'] + '/' + suffix


@pytest.fixture
def calc(api):  # noqa: F811
    return dict(api, **seed(api))


def brief_version(e, criteria):
    client = e['client']
    written = client.post(
        study_path(e, 'brief/draft'),
        json=dict(command_id=uid(), expected_revision=None, content=content(criteria=criteria)),
    )
    assert written.status_code == 200, written.text
    saved = client.post(
        study_path(e, 'brief/versions'),
        json=dict(command_id=uid(), expected_revision=written.json()['data']['revision']),
    )
    assert saved.status_code == 201, saved.text
    return saved.json()['data']['version']['brief_version_id']


def body(e, members=None, brief=None, bindings=(), **changes):
    return (
        dict(
            schema_version='1',
            name='Cruise points',
            description='Hand-picked cruise points.',
            model_id=e['config']['model_id'],
            model_revision_id=e['config']['model_revision_id'],
            configuration_revision_ids=(
                [e['config']['configuration_revision_id']] if members is None else members
            ),
            design=dict(kind='hand_picked'),
            brief_version_id=brief,
            criterion_bindings=list(bindings),
        )
        | changes
    )


def create(e, content_body, command=None):
    return e['client'].post(
        study_path(e, 'calculations'), json=dict(command_id=command or uid(), content=content_body)
    )


def save_version(e, cid, expected, content_body):
    return e['client'].post(
        study_path(e, 'calculations/' + cid + '/versions'),
        json=dict(command_id=uid(), expected_version_id=expected, content=content_body),
    )


def runs(e, version_id, query=''):
    response = e['client'].get(
        study_path(e, 'calculation-versions/' + version_id + '/runs' + query)
    )
    assert response.status_code == 200, response.text
    return response.json()['data']


def test_a_saved_version_freezes_its_set_and_a_new_version_needs_the_latest(calc):
    created = create(calc, body(calc))
    assert created.status_code == 201, created.text
    first = created.json()['data']
    assert first['version_number'] == 1 and first['predecessor_version_id'] is None
    cid = first['calculation_id']
    other = sibling(calc, calc['frozen'])
    widened = body(calc, members=[calc['config']['configuration_revision_id'], other])
    second = save_version(calc, cid, first['calculation_version_id'], widened)
    assert second.status_code == 201, second.text
    second = second.json()['data']
    assert second['version_number'] == 2
    assert second['predecessor_version_id'] == first['calculation_version_id']
    stale = save_version(calc, cid, first['calculation_version_id'], body(calc))
    assert stale.status_code == 409 and stale.json()['error']['code'] == 'stale_revision'
    assert stale.json()['error']['current_revision'] == second['calculation_version_id']
    # The earlier version keeps its exact set.
    read = calc['client'].get(
        study_path(calc, 'calculation-versions/' + first['calculation_version_id'])
    )
    assert read.json()['data'] == first
    family = calc['client'].get(study_path(calc, 'calculations/' + cid)).json()['data']
    assert family['latest_version'] == second
    listed = calc['client'].get(study_path(calc, 'calculations')).json()['data']
    assert [c['calculation_id'] for c in listed['items']] == [cid]
    page = calc['client'].get(study_path(calc, 'calculations/' + cid + '/versions?limit=1'))
    assert [v['version_number'] for v in page.json()['data']['items']] == [2]
    assert page.json()['data']['next_cursor'] == 2
    rest = calc['client'].get(study_path(calc, 'calculations/' + cid + '/versions?before=2'))
    assert [v['version_number'] for v in rest.json()['data']['items']] == [1]


def test_members_share_one_model_version_of_this_study(calc):
    other_model = sibling(calc, calc['frozen'], model_revision_id=uid())
    mixed = create(
        calc, body(calc, members=[calc['config']['configuration_revision_id'], other_model])
    )
    assert mixed.status_code == 422, mixed.text
    assert mixed.json()['error']['fields'][0]['path'] == '/configuration_revision_ids/1'
    assert create(calc, body(calc, members=[uid()])).status_code == 422
    assert create(calc, body(calc, model_id=uid())).status_code == 422
    assert create(calc, body(calc, members=[])).status_code == 400
    duplicate = [calc['config']['configuration_revision_id']] * 2
    assert create(calc, body(calc, members=duplicate)).status_code == 400
    assert calc['client'].get(study_path(calc, 'calculations')).json()['data']['items'] == []


def test_the_list_filters_by_model_version_before_paging(calc):
    revision = calc['config']['model_revision_id']
    newer = uid()
    other = sibling(calc, calc['frozen'], model_revision_id=newer)
    mine = create(calc, body(calc)).json()['data']['calculation_id']
    elsewhere = create(calc, body(calc, members=[other], model_revision_id=newer))
    assert elsewhere.status_code == 201, elsewhere.text
    elsewhere = elsewhere.json()['data']['calculation_id']
    page = calc['client'].get(
        study_path(calc, 'calculations?limit=1&model_revision_id=' + revision)
    )
    assert [c['calculation_id'] for c in page.json()['data']['items']] == [mine]
    assert page.json()['data']['next_cursor'] is None
    assert elsewhere != mine
    assert (
        calc['client'].get(study_path(calc, 'calculations?model_revision_id=x')).status_code == 400
    )


def test_a_member_whose_stored_record_fails_validation_is_refused(calc):
    frozen = copy.deepcopy(calc['frozen'])
    config = frozen['configuration']
    config.update(configuration_id=uid(), configuration_revision_id=uid())
    config['name'] = 'Changed without a new digest'
    insert_configuration(calc, frozen)
    refused = create(calc, body(calc, members=[config['configuration_revision_id']]))
    assert refused.status_code == 409, refused.text
    assert refused.json()['error']['code'] == 'corrupt_retained_record'


def test_a_calculation_keeps_its_model(calc):
    first = create(calc, body(calc)).json()['data']
    moved = save_version(
        calc, first['calculation_id'], first['calculation_version_id'], body(calc, model_id=uid())
    )
    assert moved.status_code == 422, moved.text


def test_bindings_need_a_brief_criterion_an_output_and_identical_units(calc):
    mass, cost = constraint(units=''), objective(units='')
    weighed = constraint(name='Payload mass', units='kg')
    brief = brief_version(calc, [mass, cost, weighed])
    out = calc['outputs'][0]

    def bind(criterion, output=out):
        return dict(criterion_id=criterion['criterion_id'], output=output)

    accepted = create(calc, body(calc, brief=brief, bindings=[bind(mass), bind(cost)]))
    assert accepted.status_code == 201, accepted.text
    refusals = [
        body(calc, brief=brief, bindings=[bind(weighed)]),
        body(calc, brief=brief, bindings=[bind(mass, calc['input_ref'])]),
        body(calc, brief=brief, bindings=[bind(constraint(units=''))]),
        body(calc, brief=brief, bindings=[bind(mass), bind(mass, calc['outputs'][1])]),
        body(calc, brief=None, bindings=[bind(mass)]),
        body(calc, brief=uid(), bindings=[bind(mass)]),
    ]
    for refused in refusals:
        response = create(calc, refused)
        assert response.status_code == 422, (refused, response.text)
    units = create(calc, refusals[0]).json()['error']['fields'][0]['message']
    assert 'never converted' in units


def test_runs_attach_by_reference_and_are_evaluated_through_bindings(calc):
    below, above, cost = (
        constraint(threshold=151),
        constraint(name='Floor', operator='gt', threshold=200),
        objective(),
    )
    for criterion in (below, above, cost):
        criterion['units'] = ''
    unbound = constraint(name='Range', units='')
    brief = brief_version(calc, [below, above, cost, unbound])
    first, second = calc['outputs']
    bindings = [
        dict(criterion_id=below['criterion_id'], output=first),
        dict(criterion_id=above['criterion_id'], output=first),
        dict(criterion_id=cost['criterion_id'], output=second),
    ]
    version = create(calc, body(calc, brief=brief, bindings=bindings)).json()['data']
    vid = version['calculation_version_id']
    assert runs(calc, vid) == dict(calculation_version_id=vid, items=[], next_cursor=None)
    recorded = calc['record']([150, 151])
    pending = calc['submit']()['run_id']
    page = runs(calc, vid)
    assert [r['run_id'] for r in page['items']] == [recorded, pending]
    evaluated = {e['criterion_id']: e for e in page['items'][0]['evaluations']}
    assert [e['criterion_id'] for e in page['items'][0]['evaluations']] == [
        c['criterion_id'] for c in (below, above, cost, unbound)
    ]
    assert evaluated[below['criterion_id']] == dict(
        criterion_id=below['criterion_id'],
        kind='constraint',
        outcome='met',
        reason='threshold_comparison',
        value=150,
        units='',
    )
    assert evaluated[above['criterion_id']]['outcome'] == 'not_met'
    assert evaluated[cost['criterion_id']]['outcome'] == 'measured'
    assert evaluated[cost['criterion_id']]['value'] == 151
    # An unbound criterion is unresolved, never met; an unavailable value is null.
    assert evaluated[unbound['criterion_id']]['outcome'] == 'unresolved'
    assert evaluated[unbound['criterion_id']]['reason'] == 'criterion_not_bound'
    assert evaluated[unbound['criterion_id']]['value'] is None
    assert page['items'][1]['record_state'] != 'recorded'
    assert {e['reason'] for e in page['items'][1]['evaluations']} == {'run_not_recorded'}
    # Running a point added runs without a new calculation version.
    versions = calc['client'].get(
        study_path(calc, 'calculations/' + version['calculation_id'] + '/versions')
    )
    assert [v['version_number'] for v in versions.json()['data']['items']] == [1]
    first_page = runs(calc, vid, '?limit=1')
    assert [r['run_id'] for r in first_page['items']] == [recorded]
    after = runs(calc, vid, '?after=' + str(first_page['next_cursor']))
    assert [r['run_id'] for r in after['items']] == [pending] and after['next_cursor'] is None


def test_a_corrupt_retained_run_reads_unresolved_never_met(calc):
    criterion = constraint(threshold=151, units='')
    brief = brief_version(calc, [criterion])
    binding = dict(criterion_id=criterion['criterion_id'], output=calc['outputs'][0])
    vid = create(calc, body(calc, brief=brief, bindings=[binding])).json()['data'][
        'calculation_version_id'
    ]
    rid = calc['record']([150, 151])
    with calc['store'].connection(write=True) as db:
        payload = json.loads(
            db.execute('SELECT payload FROM outbox WHERE run_id=?', (rid,)).fetchone()[0]
        )
        payload['history']['results']['outputs'][0]['value'] = 1
        db.execute('UPDATE outbox SET payload=? WHERE run_id=?', (json.dumps(payload), rid))
    evaluation = runs(calc, vid)['items'][0]['evaluations'][0]
    assert (evaluation['outcome'], evaluation['reason']) == (
        'unresolved',
        'retained_record_invalid',
    )


@pytest.mark.parametrize(
    'criterion',
    [
        dict(operator='lt', threshold=151),
        dict(operator='ge', threshold=151),
        dict(operator='eq', threshold=150.5, absolute_tolerance=0.5),
        dict(operator='eq', threshold=150.5, absolute_tolerance=0.4),
        dict(operator='eq', threshold=149, relative_tolerance=0.01),
        dict(operator='gt', threshold=150),
    ],
)
def test_constraint_outcomes_match_the_worker_comparison(criterion):
    target = dict(instance_id=uid(), port_id=uid())
    output = dict(target=target, value=150, units='', availability='available')
    results = dict(schema_version='2', outputs=[output], execution=dict(state='finished'))
    full = constraint(units='') | criterion
    worker = evaluate_criteria(results, [full | dict(target=target)])[0]
    ours = evaluate_run(results, [full], {full['criterion_id']: target})[0]
    assert ours['outcome'] == {'met': 'met', 'violated': 'not_met'}[worker['outcome']]
    assert ours['reason'] == worker['reason']


def test_unconverged_or_unavailable_outputs_stay_unresolved():
    target = dict(instance_id=uid(), port_id=uid())
    criterion = constraint(units='')
    unconverged = dict(
        schema_version='1',
        convergence=dict(state='not_converged'),
        outputs=[dict(target=target, value=1, units='', availability='available')],
    )
    missing = dict(
        schema_version='2',
        outputs=[dict(target=target, value=None, units='', availability='unavailable')],
    )
    for results in (unconverged, missing):
        worker = evaluate_criteria(results, [criterion | dict(target=target)])[0]
        ours = evaluate_run(results, [criterion], {criterion['criterion_id']: target})[0]
        assert ours['outcome'] == worker['outcome'] == 'unresolved'
        assert ours['reason'] == worker['reason'] and ours['value'] is None


def test_reference_marks_move_without_changing_any_configuration(calc):
    revision = calc['config']['configuration_revision_id']
    with calc['store'].connection() as db:
        before = db.execute('SELECT payload FROM configurations').fetchall()

    def command(action, target=revision):
        return calc['client'].post(
            study_path(calc, 'reference-marks'),
            json=dict(command_id=uid(), configuration_revision_id=target, action=action),
        )

    marked = command('set')
    assert marked.status_code == 200, marked.text
    mark = marked.json()['data']['mark']
    assert mark['configuration_revision_id'] == revision
    assert mark['model_id'] == calc['config']['model_id']
    assert command('set').json()['data']['mark'] == mark
    other = sibling(calc, calc['frozen'])
    assert command('set', other).status_code == 200
    listed = calc['client'].get(
        study_path(calc, 'reference-marks?model_id=' + calc['config']['model_id'])
    )
    assert [m['configuration_revision_id'] for m in listed.json()['data']['items']] == [
        revision,
        other,
    ]
    assert command('clear').json()['data'] == dict(configuration_revision_id=revision, mark=None)
    assert command('clear').status_code == 200
    listed = calc['client'].get(study_path(calc, 'reference-marks')).json()['data']['items']
    assert [m['configuration_revision_id'] for m in listed] == [other]
    assert calc['client'].get(study_path(calc, 'reference-marks?model_id=' + uid())).json()[
        'data'
    ] == dict(items=[])
    assert command('set', uid()).status_code == 422
    with calc['store'].connection() as db:
        after = db.execute('SELECT payload FROM configurations').fetchall()
    assert [tuple(r) for r in after][: len(before)] == [tuple(r) for r in before]


def test_saved_versions_cannot_be_rewritten_or_deleted_in_storage(calc):
    create(calc, body(calc))
    for statement in (
        "UPDATE calculation_versions SET payload='{}'",
        'DELETE FROM calculation_versions',
        "UPDATE calculations SET study_id='x'",
        'DELETE FROM calculations',
    ):
        with calc['store'].connection(write=True) as db:
            with pytest.raises(sqlite3.DatabaseError):
                db.execute(statement)


def test_a_replayed_command_returns_its_result_and_a_changed_body_conflicts(calc):
    command = uid()
    first = create(calc, body(calc), command)
    again = create(calc, body(calc), command)
    assert first.status_code == again.status_code == 201
    assert again.json()['data'] == first.json()['data']
    changed = create(calc, body(calc, name='Other points'), command)
    assert changed.status_code == 409
    assert changed.json()['error']['code'] == 'command_payload_conflict'
    listed = calc['client'].get(study_path(calc, 'calculations')).json()['data']['items']
    assert len(listed) == 1


def test_readers_read_and_never_write_and_strangers_see_nothing(calc):
    version = create(calc, body(calc)).json()['data']
    auth = Auth(calc['store'], ORIGIN)
    reader, stranger = uid(), uid()
    with calc['store'].connection(write=True) as db:
        for actor, name in ((reader, 'reader'), (stranger, 'stranger')):
            db.execute(
                'INSERT INTO users(actor_id,username,password_hash) VALUES(?,?,?)',
                (actor, name, auth_module.password_hash(name + ' horse battery staple')),
            )
    study = calc['client'].get('/api/1/studies/' + calc['sid']).json()['data']
    calc['store'].set_membership(
        calc['actor'], calc['sid'], uid(), study['revision'], reader, 'reader'
    )

    def client(name):
        c = TestClient(create_app(calc['store'], auth, NoModeling()), base_url=ORIGIN)
        session = c.post(
            '/api/1/session',
            json=dict(username=name, password=name + ' horse battery staple'),
            headers={'Origin': ORIGIN},
        )
        assert session.status_code == 200
        c.headers.update({'Origin': ORIGIN, 'X-CSRF-Token': session.json()['data']['csrf_token']})
        return dict(calc, client=c)

    as_reader = client('reader')
    vid = version['calculation_version_id']
    read = as_reader['client'].get(study_path(calc, 'calculation-versions/' + vid))
    assert read.json()['data'] == version
    assert runs(as_reader, vid)['items'] == []
    assert create(as_reader, body(calc)).status_code == 403
    assert save_version(as_reader, version['calculation_id'], vid, body(calc)).status_code == 403
    marked = as_reader['client'].post(
        study_path(calc, 'reference-marks'),
        json=dict(
            command_id=uid(),
            configuration_revision_id=calc['config']['configuration_revision_id'],
            action='set',
        ),
    )
    assert marked.status_code == 403
    as_stranger = client('stranger')
    for suffix in ('calculations', 'calculation-versions/' + vid, 'reference-marks'):
        assert as_stranger['client'].get(study_path(calc, suffix)).status_code == 404


@pytest.mark.parametrize(
    'suffix',
    [
        'calculations?extra=1',
        'calculations?limit=0',
        'calculations?limit=101',
        'calculations?after=x',
        'reference-marks?model_id=x',
        'reference-marks?limit=1',
    ],
)
def test_unknown_or_invalid_query_fields_are_refused(calc, suffix):
    assert calc['client'].get(study_path(calc, suffix)).status_code == 400


def test_unknown_records_are_not_found(calc):
    vid = create(calc, body(calc)).json()['data']['calculation_version_id']
    assert calc['client'].get(study_path(calc, 'calculations/' + uid())).status_code == 404
    assert calc['client'].get(study_path(calc, 'calculation-versions/' + uid())).status_code == 404
    assert (
        calc['client'].get(study_path(calc, 'calculation-versions/' + vid + '/runs?limit=21'))
    ).status_code == 400


def test_the_contract_declares_every_calculation_route(generated):  # noqa: F811
    paths = generated['paths']
    assert paths['/studies/{study_id}/calculations']['post']['responses']['201']
    assert paths['/studies/{study_id}/calculations/{calculation_id}/versions']['post']['responses'][
        '201'
    ]
    assert paths['/studies/{study_id}/calculation-versions/{version_id}/runs']['get']
    assert 'delete' not in paths['/studies/{study_id}/reference-marks']
    for name in ('CalculationVersion1', 'CriterionEvaluation1', 'ReferenceMarkState1'):
        assert name in generated['components']['schemas']


def test_retired_authoring_routes_cannot_create_old_scientific_records(api):
    client = api['client']
    for route in ('approach', 'approach/preview', 'approach/draft', 'approach/versions',
                  'answers', 'exploration-designs', 'exploration-samples',
                  'exploration-surrogates', 'exploration-requests'):
        for method in ('get', 'post'):
            response = getattr(client, method)(study_path(api, route))
            assert response.status_code == 404, (route, method, response.text)
    with api['store'].connection() as db:
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert not tables.intersection({'approach_drafts', 'approach_versions',
                                    'scientific_answer_heads', 'scientific_answer_versions'})


def test_member_run_filter_pages_only_that_members_runs_and_rejects_nonmembers(calc):
    first = calc['config']['configuration_revision_id']
    second = sibling(calc, calc['frozen'])
    vid = create(calc, body(calc, members=[first, second])).json()['data'][
        'calculation_version_id'
    ]
    recorded = calc['record']([150, 151])
    pending = calc['submit']()['run_id']
    query = '?configuration_revision_id=' + first + '&limit=1'
    page = runs(calc, vid, query)
    assert [r['run_id'] for r in page['items']] == [recorded]
    next_page = runs(calc, vid, query + '&after=' + str(page['next_cursor']))
    assert [r['run_id'] for r in next_page['items']] == [pending]
    assert next_page['next_cursor'] is None
    assert runs(calc, vid, '?configuration_revision_id=' + second)['items'] == []
    response = calc['client'].get(study_path(
        calc, 'analysis-versions/' + vid + '/runs?configuration_revision_id=' + uid(),
    ))
    assert response.status_code == 404


def finite_analysis(calc, count=12):
    members = [calc['config']['configuration_revision_id']]
    members += [sibling(calc, calc['frozen']) for _ in range(count - 1)]
    response = create(calc, body(calc, members=members, schema_version='4', estimate_plan=None))
    assert response.status_code == 201, response.text
    vid = response.json()['data']['calculation_version_id']
    endpoint = study_path(calc, 'analysis-versions/' + vid + '/execution')
    response = calc['client'].post(endpoint, json={})
    assert response.status_code == 202, response.text
    return vid, endpoint


def test_finite_analysis_admits_only_actor_queue_capacity_and_cancellation_stops_admission(calc):
    from hyprn_mvp_app.analysis_execution import AnalysisExecution
    from hyprn_mvp_app.execution import Submissions

    vid, endpoint = finite_analysis(calc, 65)
    owner = AnalysisExecution(calc['store'])
    submissions = Submissions(calc['store'], None, None)
    owner.process_one(submissions)
    progress = calc['client'].get(endpoint).json()['data']
    assert len([r for r in progress['runs'] if r['run_id']]) == 10
    assert progress['total_count'] == 65
    owner.process_one(submissions)
    assert calc['client'].get(endpoint).json()['data']['runs'] == progress['runs']
    cancelled = owner.cancel(calc['actor'], calc['sid'], vid)
    assert cancelled['state'] == 'cancelled'
    assert not owner.process_one(submissions)
    assert calc['client'].get(endpoint).json()['data']['runs'] == progress['runs']


@pytest.mark.parametrize('code,status,admission_state', [
    ('backend_unavailable', 503, 'unavailable'),
    ('attestation_required', 503, 'invalid_attestation'),
    ('limit_exceeded', 429, 'waiting'),
])
def test_transient_admission_refusal_preserves_prior_run_and_recovers_original_command(
    calc, code, status, admission_state,
):
    from hyprn_mvp_app.analysis_execution import AnalysisExecution
    from hyprn_mvp_app.execution import Submissions
    from hyprn_mvp_app.contracts import DomainError

    _, endpoint = finite_analysis(calc, 3)
    submissions = Submissions(calc['store'], None, None)
    submit = submissions.submit
    attempts = []

    def temporarily_unavailable(actor, sid, body, **kwargs):
        attempts.append(body['command_id'])
        if len(attempts) == 2:
            raise DomainError(code, status)
        return submit(actor, sid, body, **kwargs)

    submissions.submit = temporarily_unavailable
    AnalysisExecution(calc['store']).process_one(submissions)
    progress = calc['client'].get(endpoint).json()['data']
    assert progress['state'] == 'calculating'
    assert progress['admission_state'] == admission_state
    first = progress['runs'][0]['run_id']
    assert first is not None
    AnalysisExecution(calc['store']).process_one(submissions)
    recovered = calc['client'].get(endpoint).json()['data']
    assert recovered['runs'][0]['run_id'] == first
    assert all(r['run_id'] for r in recovered['runs'])
    assert attempts[1] == attempts[2]


def test_uncertain_existing_run_is_pinned_and_blocks_further_dispatch(calc):
    from hyprn_mvp_app.analysis_execution import AnalysisExecution
    from hyprn_mvp_app.execution import Submissions

    pending = calc['submit']()['run_id']
    _, endpoint = finite_analysis(calc, 3)
    submissions = Submissions(calc['store'], None, None)
    original = submissions.read

    def uncertain(actor, sid, run_id):
        result = original(actor, sid, run_id)
        return dict(result, state='uncertain') if run_id == pending else result

    submissions.read = uncertain
    AnalysisExecution(calc['store']).process_one(submissions)
    result = calc['client'].get(endpoint).json()['data']
    assert result['state'] == 'needs_review'
    assert result['runs'][0]['run_id'] == pending
    assert result['runs'][0]['reused']
    assert not any(r['run_id'] for r in result['runs'][1:])


def test_two_analyses_share_one_actor_queue_without_starvation(calc):
    from hyprn_mvp_app.analysis_execution import AnalysisExecution
    from hyprn_mvp_app.execution import Submissions

    _, first = finite_analysis(calc, 12)
    _, second = finite_analysis(calc, 12)
    owner = AnalysisExecution(calc['store'])
    owner.process_one(Submissions(calc['store'], None, None))
    counts = [sum(row['run_id'] is not None for row in
                  calc['client'].get(endpoint).json()['data']['runs'])
              for endpoint in (first, second)]
    assert counts == [5, 5]


def test_126_member_finite_plan_survives_owner_restart_without_resubmitting(calc, monkeypatch):
    from types import SimpleNamespace
    from hyprn_mvp_app.analysis_execution import AnalysisExecution
    from hyprn_mvp_app.execution import Submissions
    from hyprn_mvp_app.history import History

    vid, endpoint = finite_analysis(calc, 126)
    submissions = Submissions(calc['store'], None, None)
    original_read = submissions.read
    completed = set()
    accepted = []

    def read(actor, sid, run_id):
        result = original_read(actor, sid, run_id)
        return dict(result, state='recorded') if run_id in completed else result

    monkeypatch.setattr(submissions, 'read', read)
    monkeypatch.setattr(History, 'retained_projection', lambda *args: SimpleNamespace(
        history={'results': {'execution': {'state': 'finished'}}}))
    for _ in range(14):
        # A fresh owner proves receipt recovery; execution here is a lifecycle
        # double, not evidence of physical values or native throughput.
        AnalysisExecution(calc['store']).process_one(submissions)
        progress = calc['client'].get(endpoint).json()['data']
        newly_accepted = [row['run_id'] for row in progress['runs']
                          if row['run_id'] and row['run_id'] not in completed]
        assert len(newly_accepted) <= 10
        accepted.extend(newly_accepted)
        with calc['store'].connection(write=True) as db:
            for run_id in newly_accepted:
                db.execute("UPDATE execution_operations SET state='recorded' WHERE run_id=?",
                           (run_id,))
        completed.update(newly_accepted)
        if progress['state'] == 'complete':
            break
    assert progress['state'] == 'complete'
    assert progress['completed_count'] == 126
    assert len(accepted) == len(set(accepted)) == 126
    assert not AnalysisExecution(calc['store']).process_one(submissions)


@pytest.mark.parametrize('different_actor', [False, True])
def test_distinct_studies_progress_with_actor_scoped_capacity(calc, different_actor):
    from hyprn_mvp_app.analysis_execution import AnalysisExecution
    from hyprn_mvp_app.execution import Submissions

    other = dict(calc)
    if different_actor:
        other['actor'] = uid()
        with calc['store'].connection(write=True) as db:
            db.execute('INSERT INTO users(actor_id,username,password_hash) VALUES(?,?,?)', (
                other['actor'], 'second-engineer',
                auth_module.password_hash('another correct horse battery staple')))
        other['client'] = TestClient(calc['client'].app, base_url=ORIGIN)
        session = other['client'].post('/api/1/session', headers={'Origin': ORIGIN}, json={
            'username': 'second-engineer', 'password': 'another correct horse battery staple'})
        assert session.status_code == 200
        other['client'].headers.update({
            'Origin': ORIGIN, 'X-CSRF-Token': session.json()['data']['csrf_token']})
    response = other['client'].post('/api/1/studies', json={
        'command_id': uid(), 'name': 'Independent study'})
    assert response.status_code == 201
    other['sid'] = response.json()['data']['study_id']
    other.update(seed(other))
    _, first = finite_analysis(calc, 12)
    _, second = finite_analysis(other, 12)
    AnalysisExecution(calc['store']).process_one(Submissions(calc['store'], None, None))
    counts = [sum(row['run_id'] is not None for row in
                  owner['client'].get(endpoint).json()['data']['runs'])
              for owner, endpoint in ((calc, first), (other, second))]
    assert counts == ([10, 10] if different_actor else [5, 5])
    if different_actor:
        assert other['client'].get(first).status_code == 404
        assert calc['client'].get(second).status_code == 404


def agent_analysis(store, actor, sid, sample, count=3):
    """A real accepted plan with a reasoning credential and frozen member commands."""
    import time
    from hyprn_mvp_app.analysis_execution import AnalysisExecution
    from hyprn_mvp_app.calculations import Analyses
    from hyprn_mvp_app.database import actor_scope
    with actor_scope(actor):
        members = [sample['config']['configuration_revision_id']]
        members += [sibling(sample, sample['frozen']) for _ in range(count - 1)]
        version = Analyses(store).create(actor, sid, dict(command_id=uid(),
            content=body(sample, members=members, schema_version='4', estimate_plan=None)))
        with store.connection(write=True) as db:
            agent = store.ensure_agent_actor(db, actor, 'claude_managed', 'Assistant')
            grant = store.create_delegation(db, agent, sid, 'writer',
                                            {'read', 'record', 'submit'}, time.time()+600)
    with actor_scope(agent):
        AnalysisExecution(store).launch(agent, sid, version['calculation_version_id'], {})
    return agent, grant, version['calculation_version_id']


def replace_analysis_grant(store, actor, agent, sid, *, narrow=False, revoke=False):
    import time
    from hyprn_mvp_app.database import actor_scope
    with actor_scope(actor), store.connection(write=True) as db:
        if revoke:
            row = db.execute('SELECT delegation_id FROM agent_delegations '
                             'WHERE agent_actor_id=? AND study_id=? AND revoked_at IS NULL',
                             (agent, sid)).fetchone()
            store.revoke_delegation(db, row['delegation_id'], 'owner_revoked')
        return store.create_delegation(db, agent, sid, 'reader' if narrow else 'writer',
                                      {'read'} if narrow else {'read', 'record', 'submit'},
                                      time.time()+600)


def legacy_interrupted_analysis(store, actor, sid, vid):
    """Retain the exact terminal outcome emitted before credential-rotation repair."""
    from hyprn_mvp_app.analysis_execution import AnalysisExecution, identity
    from hyprn_mvp_app.database import actor_scope
    with actor_scope(actor), store.connection(write=True) as db:
        saved = store.command_receipt(db, sid, 'analysis_execution', identity(vid))
        result = dict(saved['result'], state='failed', admission_state='revoked',
                      reason='Permission to execute this analysis was lost.')
        AnalysisExecution(store)._save(db, sid, identity(vid), result, True)
        return saved['request'], result


def test_repeated_reasoning_replacement_preserves_finite_authority(calc):
    from hyprn_mvp_app.analysis_execution import AnalysisExecution
    from hyprn_mvp_app.execution import Submissions
    store, actor, sid = calc['store'], calc['actor'], calc['sid']
    agent, _, vid = agent_analysis(store, actor, sid, calc)
    for _ in range(3):
        replace_analysis_grant(store, actor, agent, sid)
    runner = AnalysisExecution(store)
    assert runner.process_one(Submissions(store, None, None))
    result = runner.read(actor, sid, vid)
    assert result['state'] == 'calculating'
    assert all(r['run_id'] for r in result['runs'])


def test_public_resume_preserves_frozen_work_replays_and_blocks_uncertain_runs(calc):
    from concurrent.futures import ThreadPoolExecutor
    from hyprn_mvp_app.analysis_execution import AnalysisExecution, identity
    from hyprn_mvp_app.database import actor_scope
    from hyprn_mvp_app.execution import Submissions
    store, actor, sid = calc['store'], calc['actor'], calc['sid']
    agent, _, vid = agent_analysis(store, actor, sid, calc, 12)
    runner = AnalysisExecution(store)
    submissions = Submissions(store, None, None)
    runner.process_one(submissions)
    request, failed = legacy_interrupted_analysis(store, actor, sid, vid)
    replace_analysis_grant(store, actor, agent, sid)
    path = study_path(calc, 'analysis-versions/' + vid + '/execution')
    assert calc['client'].post(path, json={}).json()['data'] == failed
    assert calc['client'].get(path + '/recovery').json()['data']['can_resume'] is True
    command = dict(command_id=uid())
    with ThreadPoolExecutor(2) as pool:
        replies = list(pool.map(lambda _: calc['client'].post(path + '/resume', json=command), range(2)))
    assert [r.status_code for r in replies] == [202, 202], [r.text for r in replies]
    resumed = replies[0].json()['data']
    assert replies[1].json()['data'] == resumed
    assert resumed['runs'] == failed['runs']
    assert calc['client'].post(path + '/resume', json=dict(command_id=uid())).status_code == 409
    with actor_scope(actor), store.connection() as db:
        saved = store.command_receipt(db, sid, 'analysis_execution', identity(vid))
        assert saved['request'] == request
        assert db.execute('SELECT count(*) FROM analysis_execution_resumptions WHERE study_id=?',
                          (sid,)).fetchone()[0] == 1
        assert db.execute('SELECT count(*) FROM run_associations WHERE study_id=?', (sid,)).fetchone()[0] == 10
    first = resumed['runs'][0]['run_id']
    read = submissions.read
    submissions.read = lambda who, study, run: dict(read(who, study, run), state='uncertain') if run == first else read(who, study, run)
    assert runner.process_one(submissions)
    assert runner.read(actor, sid, vid)['state'] == 'needs_review'
    assert runner.read(actor, sid, vid)['runs'] == resumed['runs']
    # Public foreign-study identity does not expose recovery or resume availability.
    other = store.create_study(actor, uid(), 'Other study')['study_id']
    foreign_path = path.replace(sid, other)
    assert calc['client'].get(foreign_path + '/recovery').status_code == 404
    assert calc['client'].post(foreign_path + '/resume', json=dict(command_id=uid())).status_code == 404


@pytest.mark.parametrize('interruption', ['revoke', 'narrow', 'membership'])
def test_regrant_cannot_restore_interrupted_analysis_authority(calc, interruption):
    from hyprn_mvp_app.analysis_execution import AnalysisExecution
    from hyprn_mvp_app.execution import Submissions
    store, actor, sid = calc['store'], calc['actor'], calc['sid']
    agent, _, vid = agent_analysis(store, actor, sid, calc)
    if interruption == 'membership':
        with store.connection(write=True) as db:
            db.execute("UPDATE memberships SET role='reader' WHERE study_id=? AND actor_id=?", (sid, actor))
            db.execute("UPDATE memberships SET role='owner' WHERE study_id=? AND actor_id=?", (sid, actor))
    else:
        replace_analysis_grant(store, actor, agent, sid,
                               narrow=interruption == 'narrow', revoke=interruption == 'revoke')
    replace_analysis_grant(store, actor, agent, sid)
    runner = AnalysisExecution(store)
    assert runner.process_one(Submissions(store, None, None))
    assert runner.read(actor, sid, vid)['admission_state'] == 'revoked'
    path = study_path(calc, 'analysis-versions/' + vid + '/execution')
    assert calc['client'].get(path + '/recovery').json()['data']['can_resume'] is False
    assert calc['client'].post(path + '/resume', json=dict(command_id=uid())).status_code == 409


@pytest.mark.parametrize('code', ['forbidden', 'resource_not_found'])
def test_resource_failure_is_not_reported_as_explicit_authority_revocation(calc, code):
    from hyprn_mvp_app.analysis_execution import AnalysisExecution
    from hyprn_mvp_app.contracts import DomainError
    from hyprn_mvp_app.execution import Submissions
    _, endpoint = finite_analysis(calc, 1)
    submissions = Submissions(calc['store'], None, None)
    def denied(*args, **kwargs):
        raise DomainError(code, 403 if code == 'forbidden' else 404)
    submissions.submit = denied
    AnalysisExecution(calc['store']).process_one(submissions)
    result = calc['client'].get(endpoint).json()['data']
    assert result['admission_state'] == 'stopped'
    assert 'Permission to execute this analysis was lost' not in result['reason']


def interrupted_analysis_with_unprojected_uncertain_child(store, actor, sid, sample):
    from uuid import UUID, uuid5
    from hyprn_mvp_app.analysis_execution import AnalysisExecution, identity
    from hyprn_mvp_app.database import actor_scope
    from hyprn_mvp_app.execution import Submissions
    agent, _, vid = agent_analysis(store, actor, sid, sample)
    with actor_scope(agent), store.analysis_authority(agent, sid, identity(vid)):
        result = AnalysisExecution(store).read(agent, sid, vid)
        last = result['runs'][-1]['configuration_revision_id']
        accepted = Submissions(store, None, None).submit(agent, sid, dict(
            command_id=str(uuid5(UUID(identity(vid)), last)), configuration_revision_id=last))
        with store.connection(write=True) as db:
            db.execute("UPDATE outbox SET state='uncertain' WHERE run_id=?", (accepted['run_id'],))
    legacy_interrupted_analysis(store, actor, sid, vid)
    replace_analysis_grant(store, actor, agent, sid)
    return vid, accepted['run_id']


def test_recovery_reconciles_unprojected_uncertain_children_before_any_new_admission(calc):
    from hyprn_mvp_app.analysis_execution import AnalysisExecution
    from hyprn_mvp_app.execution import Submissions
    store, actor, sid = calc['store'], calc['actor'], calc['sid']
    vid, run_id = interrupted_analysis_with_unprojected_uncertain_child(store, actor, sid, calc)
    path = study_path(calc, 'analysis-versions/' + vid + '/execution')
    response = calc['client'].post(path + '/resume', json=dict(command_id=uid()))
    assert response.status_code == 202, response.text
    AnalysisExecution(store).process_one(Submissions(store, None, None))
    state = calc['client'].get(path).json()['data']
    assert state['state'] == 'needs_review'
    assert [r['run_id'] for r in state['runs']] == [None, None, run_id]
    with store.connection() as db:
        assert db.execute('SELECT count(*) FROM run_associations WHERE study_id=?', (sid,)).fetchone()[0] == 1


def analysis_with_unprepared_authority_failure(store, actor, sid, sample, worker=None, *, revoked_parent=False):
    """Reproduce the old false authorization refusal through the real preparation owner."""
    from hyprn_mvp_app.analysis_execution import AnalysisExecution
    from hyprn_mvp_app.database import actor_scope
    from hyprn_mvp_app.execution import Submissions
    worker = worker or store
    agent, _, vid = agent_analysis(store, actor, sid, sample, 1)
    runner = AnalysisExecution(worker)
    runner.process_one(Submissions(worker, None, None))
    with actor_scope(actor):
        state = AnalysisExecution(store).read(actor, sid, vid)
    rid = state['runs'][0]['run_id']
    grant = replace_analysis_grant(store, actor, agent, sid)
    authorized = worker.analysis_authorized
    worker.analysis_authorized = lambda *args: False
    try:
        Submissions(worker, None, None).dispatch(rid)
    finally:
        worker.analysis_authorized = authorized
    with actor_scope(actor):
        assert Submissions(store, None, None).read(actor, sid, rid)['state'] == 'preparation_failed'
    if revoked_parent:
        legacy_interrupted_analysis(store, actor, sid, vid)
    else:
        runner.process_one(Submissions(worker, None, None))
        with actor_scope(actor):
            assert AnalysisExecution(store).read(actor, sid, vid)['admission_state'] == 'stopped'
    return agent, grant, vid, rid


def recovered_submission_owner(store):
    """Real bundle validation/claim with an explicitly uncertain native-boundary double."""
    from execution_fixtures import fixture, runtime_fixture
    from hyprn_mvp_app.execution import Submissions, executable_digest
    def prepare(actor, sid, command, frozen):
        case = fixture('chain')
        prepared = case['prepared']
        config = frozen['configuration']
        prepared.update(configuration_digest=config['digest'],
                        configuration_revision_id=config['configuration_revision_id'])
        prepared['executable_content_digest'] = executable_digest(prepared)
        prepared['prepared_digest'] = digest({k:v for k,v in prepared.items() if k != 'prepared_digest'})
        return prepared, case['files']
    class Native:
        launches = 0
        def require_attestation(self):
            pass
        def bundle_runtime(self):
            return runtime_fixture()
        def launch(self, bundle, request):
            self.launches += 1
            raise TimeoutError('Explicit uncertain native-boundary double')
        def matches(self, request):
            return []
    native = Native()
    return Submissions(store, prepare, native), native


@pytest.mark.parametrize('revoked_parent', [False, True])
def test_public_resume_repairs_only_unprepared_authority_refusal_and_advances_same_run(calc, revoked_parent):
    from hyprn_mvp_app.execution import Submissions
    store, actor, sid = calc['store'], calc['actor'], calc['sid']
    agent, grant, vid, rid = analysis_with_unprepared_authority_failure(
        store, actor, sid, calc, revoked_parent=revoked_parent)
    path = study_path(calc, 'analysis-versions/' + vid + '/execution')
    with store.connection() as db:
        source = db.execute('SELECT payload FROM outbox WHERE run_id=?', (rid,)).fetchone()[0]
    assert calc['client'].get(path + '/recovery').json()['data']['can_resume'] is True
    command = dict(command_id=uid())
    response = calc['client'].post(path + '/resume', json=command)
    assert response.status_code == 202, response.text
    assert response.json()['data']['runs'][0]['run_id'] == rid
    assert Submissions(store, None, None).read(actor, sid, rid)['state'] == 'accepted_run'
    with store.connection() as db:
        audit = db.execute('SELECT * FROM analysis_run_resumptions WHERE run_id=?', (rid,)).fetchone()
        assert json.loads(audit['previous_receipt'])['error']['code'] == 'analysis_authority_revoked'
        assert json.loads(audit['previous_operation'])['preparation_state'] == 'preparation_failed'
        assert db.execute('SELECT payload FROM outbox WHERE run_id=?', (rid,)).fetchone()[0] == source
    submissions, native = recovered_submission_owner(store)
    submissions.dispatch(rid)
    assert submissions.read(actor, sid, rid)['state'] == 'uncertain'
    assert native.launches == 1
    assert calc['client'].post(path + '/resume', json=command).json()['data'] == response.json()['data']
    submissions.dispatch(rid)
    assert native.launches == 1
    assert submissions.read(actor, sid, rid)['state'] == 'uncertain'


@pytest.mark.parametrize('interruption', ['preparation', 'prepared', 'uncertain', 'recorded', 'revoked'])
def test_public_child_recovery_refuses_actual_failures_prepared_or_claimed_work(calc, interruption):
    store, actor, sid = calc['store'], calc['actor'], calc['sid']
    agent, grant, vid, rid = analysis_with_unprepared_authority_failure(store, actor, sid, calc)
    with store.connection(write=True) as db:
        if interruption == 'preparation':
            receipt = db.execute('SELECT command_id FROM run_associations WHERE run_id=?', (rid,)).fetchone()
            db.execute("UPDATE receipts SET error=? WHERE scope=? AND category='run' AND command_id=?",
                       (json.dumps(dict(code='invalid_preparation', status=422, current_revision=None,
                                        fields=[], outcome='unchanged')), sid, receipt['command_id']))
        elif interruption == 'prepared':
            source = json.loads(db.execute('SELECT payload FROM outbox WHERE run_id=?', (rid,)).fetchone()[0])
            source['request'] = {}
            db.execute('UPDATE outbox SET payload=? WHERE run_id=?', (json.dumps(source), rid))
        elif interruption in ('uncertain', 'recorded'):
            db.execute('UPDATE execution_operations SET state=? WHERE run_id=?', (interruption, rid))
        else:
            store.revoke_delegation(db, grant['delegation_id'], 'owner_revoked')
    if interruption == 'revoked':
        replace_analysis_grant(store, actor, agent, sid)
    path = study_path(calc, 'analysis-versions/' + vid + '/execution')
    assert calc['client'].get(path + '/recovery').json()['data']['can_resume'] is False
    response = calc['client'].post(path + '/resume', json=dict(command_id=uid()))
    assert response.status_code == 409, response.text
    with store.connection() as db:
        assert db.execute('SELECT count(*) FROM analysis_run_resumptions WHERE run_id=?', (rid,)).fetchone()[0] == 0
        assert db.execute('SELECT preparation_state FROM execution_operations WHERE run_id=?', (rid,)).fetchone()[0] == 'preparation_failed'
