"""Public HTTP study brief journeys in scoped synthetic stores; no modeling or execution."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

from hyprn_mvp_app.api import create_app
from hyprn_mvp_app import auth as auth_module
from hyprn_mvp_app.auth import Auth
from hyprn_mvp_app.store import uid
from test_assumptions_evidence_api import api, generated, ORIGIN, NoModeling, evidence_body  # noqa: F401


def path(e, suffix=''):
    return '/api/1/studies/' + e['sid'] + '/brief' + suffix


def alternative(name):
    return dict(alternative_id=uid(), name=name, description='', reason='Named in the request.')


def constraint(**changes):
    return (
        dict(
            criterion_id=uid(),
            kind='constraint',
            name='Take-off mass',
            statement='The aircraft must stay below the take-off mass limit.',
            operator='lt',
            threshold=575000,
            units='kg',
            evidence_links=[],
        )
        | changes
    )


def objective(**changes):
    return (
        dict(
            criterion_id=uid(),
            kind='objective',
            name='Fuel expense per seat',
            statement='Lower cruise fuel expense per occupied seat is preferred.',
            direction='minimize',
            units='USD',
            evidence_links=[],
        )
        | changes
    )


def content(**changes):
    return (
        dict(
            schema_version='1',
            question='Which fuel should a 100-passenger hypersonic aircraft use?',
            original_question=None,
            elaboration=None,
            scope='Cruise segment between Mach 4 and 8.',
            alternatives=[alternative('Kerosene'), alternative('Liquid hydrogen')],
            criteria=[constraint(), objective()],
            assumptions=[],
            limits=[],
            open_questions=[],
        )
        | changes
    )


def draft(e, body, expected=None, command=None):
    return e['client'].post(
        path(e, '/draft'),
        json=dict(command_id=command or uid(), expected_revision=expected, content=body),
    )


def save(e, revision, command=None):
    return e['client'].post(
        path(e, '/versions'), json=dict(command_id=command or uid(), expected_revision=revision)
    )


def test_requested_deliverables_are_explicit_and_versioned(api):
    e = api
    requirement = dict(deliverable_id=uid(), kind='interactive_exploration',
                       statement='Explore all declared input ranges together.')
    body = content(schema_version='2', deliverables=[requirement])
    written = draft(e, body)
    assert written.status_code == 200, written.text
    frozen = save(e, written.json()['data']['revision'])
    assert frozen.status_code == 201, frozen.text
    version = frozen.json()['data']['version']
    assert version['schema_version'] == '2'
    assert version['content']['deliverables'] == [requirement]
    changed = draft(e, dict(body, deliverables=[]), frozen.json()['data']['draft']['revision'])
    assert changed.status_code == 200, changed.text
    retained = e['client'].get(path(e, '/versions/' + version['brief_version_id']))
    assert retained.json()['data'] == version
    invalid = draft(e, dict(body, deliverables=[requirement, requirement]),
                    changed.json()['data']['revision'])
    assert invalid.status_code == 422


def test_a_new_study_has_no_brief_until_one_is_written(api):
    state = api['client'].get(path(api))
    assert state.status_code == 200, state.text
    assert state.json()['data'] == dict(draft=None, latest_version=None)


def test_saving_a_version_freezes_the_draft_exactly_and_the_draft_continues(api):
    first = draft(api, content())
    assert first.status_code == 200, first.text
    written = first.json()['data']
    assert written['based_on_version_id'] is None
    saved = save(api, written['revision'])
    assert saved.status_code == 201, saved.text
    version, continuing = saved.json()['data']['version'], saved.json()['data']['draft']
    assert version['version_number'] == 1 and version['predecessor_version_id'] is None
    assert version['content'] == written['content']
    assert continuing['based_on_version_id'] == version['brief_version_id']
    assert continuing['revision'] != written['revision']
    # Later draft edits never change the saved version.
    edited = draft(
        api, content(question='Which fuel minimises cruise fuel mass?'), continuing['revision']
    )
    assert edited.status_code == 200, edited.text
    read = api['client'].get(path(api, '/versions/' + version['brief_version_id']))
    assert read.json()['data'] == version
    second = save(api, edited.json()['data']['revision']).json()['data']['version']
    assert second['version_number'] == 2
    assert second['predecessor_version_id'] == version['brief_version_id']
    state = api['client'].get(path(api)).json()['data']
    assert state['latest_version'] == second
    page = api['client'].get(path(api, '/versions?limit=1')).json()['data']
    assert [v['version_number'] for v in page['items']] == [2] and page['next_cursor'] == 2
    rest = api['client'].get(path(api, '/versions?before=2')).json()['data']
    assert [v['version_number'] for v in rest['items']] == [1] and rest['next_cursor'] is None


def test_a_stale_revision_is_refused_without_writing(api):
    first = draft(api, content()).json()['data']
    stale = draft(api, content(scope='Changed'), expected=None)
    assert stale.status_code == 409, stale.text
    assert stale.json()['error']['code'] == 'stale_revision'
    assert stale.json()['error']['current_revision'] == first['revision']
    refused = save(api, uid())
    assert refused.status_code == 409
    assert api['client'].get(path(api)).json()['data']['latest_version'] is None


def test_saved_versions_cannot_be_rewritten_or_deleted_in_storage(api):
    written = draft(api, content()).json()['data']
    save(api, written['revision'])
    with api['store'].connection(write=True) as db:
        with pytest.raises(sqlite3.DatabaseError):
            db.execute("UPDATE study_brief_versions SET payload='{}'")
    with api['store'].connection(write=True) as db:
        with pytest.raises(sqlite3.DatabaseError):
            db.execute('DELETE FROM study_brief_versions')


@pytest.mark.parametrize(
    'criterion',
    [
        constraint(operator=None),
        {k: v for k, v in constraint().items() if k != 'threshold'},
        objective(direction='largest'),
        {k: v for k, v in objective().items() if k != 'direction'},
        constraint(direction='minimize'),
    ],
)
def test_constraints_need_a_threshold_and_objectives_a_direction(api, criterion):
    response = draft(api, content(criteria=[criterion]))
    assert response.status_code == 400, response.text
    assert api['client'].get(path(api)).json()['data']['draft'] is None


def test_non_finite_thresholds_are_refused_at_the_boundary(api):
    body = (
        '{"command_id":"%s","expected_revision":null,"content":{"schema_version":"1","question":"","original_question":null,"elaboration":null,"scope":"","alternatives":[],"criteria":[{"criterion_id":"%s","kind":"constraint","name":"Mass","statement":"","operator":"lt","threshold":Infinity,"units":"kg","evidence_links":[]}],"assumptions":[],"limits":[],"open_questions":[]}}'
        % (uid(), uid())
    )
    response = api['client'].post(
        path(api, '/draft'), content=body, headers={'Content-Type': 'application/json'}
    )
    assert response.status_code == 400, response.text
    assert api['client'].get(path(api)).json()['data']['draft'] is None


def test_identities_and_names_are_distinct_and_evidence_must_exist(api):
    same = alternative('Kerosene')
    duplicate = draft(api, content(alternatives=[same, dict(same, name='Methane')]))
    assert duplicate.status_code == 422, duplicate.text
    named = draft(api, content(alternatives=[alternative('Kerosene'), alternative(' kerosene ')]))
    assert named.status_code == 422, named.text
    missing = draft(
        api,
        content(
            criteria=[
                constraint(evidence_links=[dict(evidence_version_id=uid(), relation='supports')])
            ]
        ),
    )
    assert missing.status_code == 422, missing.text
    created = api['client'].post(
        '/api/1/studies/' + api['sid'] + '/evidence', json=evidence_body(api)
    )
    assert created.status_code == 201, created.text
    cited = created.json()['data']['evidence_version_id']
    accepted = draft(
        api,
        content(
            assumptions=[
                dict(
                    assumption_id=uid(),
                    statement='Steady cruise.',
                    evidence_links=[dict(evidence_version_id=cited, relation='supports')],
                )
            ],
            criteria=[
                constraint(evidence_links=[dict(evidence_version_id=cited, relation='context')])
            ],
        ),
    )
    assert accepted.status_code == 200, accepted.text


def test_a_replayed_command_returns_its_result_and_a_changed_body_conflicts(api):
    command, body = uid(), content()
    first = draft(api, body, command=command)
    again = draft(api, body, command=command)
    assert first.status_code == again.status_code == 200
    assert again.json()['data'] == first.json()['data']
    changed = draft(api, content(scope='Different'), command=command)
    assert changed.status_code == 409
    assert changed.json()['error']['code'] == 'command_payload_conflict'


def test_readers_read_and_never_write_and_strangers_see_nothing(api):
    written = draft(api, content()).json()['data']
    auth = Auth(api['store'], ORIGIN)
    # Auth.provision creates only the single owner; extra synthetic users are inserted directly.
    reader, stranger = uid(), uid()
    with api['store'].connection(write=True) as db:
        db.execute(
            'INSERT INTO users(actor_id,username,password_hash) VALUES(?,?,?)',
            (reader, 'reader', auth_module.password_hash('reader horse battery staple')),
        )
        db.execute(
            'INSERT INTO users(actor_id,username,password_hash) VALUES(?,?,?)',
            (stranger, 'stranger', auth_module.password_hash('stranger horse battery staple')),
        )
    study = api['client'].get('/api/1/studies/' + api['sid']).json()['data']
    api['store'].set_membership(
        api['actor'], api['sid'], uid(), study['revision'], reader, 'reader'
    )

    def client(username, password):
        c = TestClient(create_app(api['store'], auth, NoModeling()), base_url=ORIGIN)
        session = c.post(
            '/api/1/session',
            json=dict(username=username, password=password),
            headers={'Origin': ORIGIN},
        )
        assert session.status_code == 200
        c.headers.update({'Origin': ORIGIN, 'X-CSRF-Token': session.json()['data']['csrf_token']})
        return dict(api, client=c)

    as_reader = client('reader', 'reader horse battery staple')
    assert as_reader['client'].get(path(api)).json()['data']['draft'] == written
    assert draft(as_reader, content(), written['revision']).status_code == 403
    assert save(as_reader, written['revision']).status_code == 403
    as_stranger = client('stranger', 'stranger horse battery staple')
    assert as_stranger['client'].get(path(api)).status_code == 404
    assert stranger


@pytest.mark.parametrize(
    'query', ['?extra=1', '?limit=0', '?limit=101', '?limit=1&limit=2', '?before=x']
)
def test_unknown_or_invalid_query_fields_are_refused(api, query):
    target = path(api, '/versions') + query
    assert api['client'].get(target).status_code == 400
    assert api['client'].get(path(api) + '?limit=1').status_code == 400


def test_the_contract_declares_every_brief_route(generated):  # noqa: F811
    paths = generated['paths']
    assert paths['/studies/{study_id}/brief']['get']['responses']['200']
    assert paths['/studies/{study_id}/brief/versions']['post']['responses']['201']
    for name in ('StudyBriefContent1', 'StudyCriterion1', 'StudyBriefVersionSaved1'):
        assert name in generated['components']['schemas']


def test_scientific_framing_has_only_the_brief_write_path(api):
    store, actor, sid = api['store'], api['actor'], api['sid']
    before = store.study(actor, sid)
    command = uid()
    refused = api['client'].patch(
        f'/api/1/studies/{sid}',
        json=dict(command_id=command, expected_revision=before['revision'], name='Must not change'),
    )
    assert refused.status_code == 405
    assert store.study(actor, sid) == before
    assert not hasattr(store, 'update_study')
    with store.connection() as db:
        assert store.command_receipt(db, sid, 'study', command) is None
    saved = api['client'].post(
        path(api, '/draft'),
        json=dict(command_id=uid(), expected_revision=None, content=content()),
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()['data']['content']['question'] == content()['question']
