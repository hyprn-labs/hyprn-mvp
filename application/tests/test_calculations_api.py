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
