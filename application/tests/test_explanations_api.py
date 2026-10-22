"""Public HTTP model explanation journeys in scoped synthetic stores.

The modeling boundary is an explicit double serving one captured producer model version; it
validates the response like the real client and can be taken offline or replaced. Nothing is
executed.
"""

import copy
import sqlite3
import time

import pytest
from fastapi.testclient import TestClient

from execution_fixtures import fixture
from hyprn_mvp_app.agent_runtime import attribution
from hyprn_mvp_app.api import create_app
from hyprn_mvp_app.auth import Auth
from hyprn_mvp_app.contracts import DomainError
from hyprn_mvp_app.explanations import Explanations
from hyprn_mvp_app.modeling import Coordinator, validate
from hyprn_mvp_app.store import digest, uid
from test_assumptions_evidence_api import (
    api,
    generated,
    ORIGIN,
    NoModeling,
    evidence_body,  # noqa: F401
)

PASSWORD = 'correct horse battery staple'


class ModelVersionDouble(NoModeling):
    """Serves the given model versions; ``offline`` refuses every contact like an unavailable
    service, and ``calls`` counts them."""

    def __init__(self, models):
        self.models = {m['model_revision_id']: m for m in models}
        self.offline = False
        self.calls = 0

    def call(self, actor, sid, method, path, *args, **kwargs):
        self.calls += 1
        if self.offline:
            raise DomainError('backend_unavailable', 503, outcome='unknown')
        revision = path.rsplit('/revisions/', 1)[-1]
        if method == 'GET' and '/revisions/' in path and revision in self.models:
            body = dict(schema_version='1', request_id=uid(), data=self.models[revision])
            validate(kwargs['response_schema'], body, remote=True)
            return 200, copy.deepcopy(body)
        if method == 'GET' and '/revisions/' in path:
            raise DomainError('resource_not_found', 404)
        return super().call(actor, sid, method, path, *args, **kwargs)


def another_version(model):
    model = copy.deepcopy(model)
    model.update(model_revision_id=uid(), parent_model_revision_id=model['model_revision_id'])
    model['digest'] = digest({k: v for k, v in model.items() if k != 'digest'})
    return model


@pytest.fixture
def explained(api):  # noqa: F811
    model = fixture('chain')['frozen']['model_snapshot']
    second = another_version(model)
    double = ModelVersionDouble([model, second])
    client = TestClient(
        create_app(api['store'], Auth(api['store'], ORIGIN), double), base_url=ORIGIN
    )
    session = client.post(
        '/api/1/session', json=dict(username='owner', password=PASSWORD), headers={'Origin': ORIGIN}
    )
    assert session.status_code == 200
    client.headers.update({'Origin': ORIGIN, 'X-CSRF-Token': session.json()['data']['csrf_token']})
    with api['store'].connection(write=True) as db:
        db.execute(
            'INSERT INTO model_associations VALUES(?,?,?)', (api['sid'], model['model_id'], uid())
        )
    return dict(
        api, client=client, model=model, second=second, double=double, mid=model['model_id']
    )


def path(e, suffix=''):
    return '/api/1/studies/' + e['sid'] + '/models/' + e['mid'] + suffix


def content(e, **changes):
    instance = e['model']['instances'][0]
    return (
        dict(
            schema_version='1',
            represents='Cruise fuel mass of one mission as a chain of two scalings.',
            basis='Breguet range relation, linearised around the design cruise point.',
            calculation_logic='The first component scales the payload; the second the range.',
            components=[
                dict(
                    kind='instance',
                    instance_id=instance['instance_id'],
                    explanation='Applies the payload factor.',
                ),
                dict(
                    kind='definition_version',
                    definition_version_id=instance['definition_version_id'],
                    explanation='A linear scaling with one factor.',
                ),
            ],
            evidence_links=[],
        )
        | changes
    )


def draft(e, body, expected=None, command=None):
    return e['client'].post(
        path(e, '/explanation/draft'),
        json=dict(command_id=command or uid(), expected_revision=expected, content=body),
    )


def save(e, revision, model_revision_id=None, command=None):
    return e['client'].post(
        path(e, '/explanation/versions'),
        json=dict(
            command_id=command or uid(),
            expected_revision=revision,
            model_revision_id=model_revision_id or e['model']['model_revision_id'],
        ),
    )


def of_version(e, model_revision_id=None):
    return e['client'].get(
        path(
            e,
            '/revisions/' + (model_revision_id or e['model']['model_revision_id']) + '/explanation',
        )
    )


def test_a_model_has_no_explanation_until_one_is_written(explained):
    state = explained['client'].get(path(explained, '/explanation'))
    assert state.status_code == 200, state.text
    assert state.json()['data'] == dict(draft=None, latest_version=None)
    read = of_version(explained)
    assert read.status_code == 200, read.text
    assert read.json()['data']['explanation'] is None


def test_saving_freezes_the_draft_for_one_exact_model_version(explained):
    e = explained
    written = draft(e, content(e))
    assert written.status_code == 200, written.text
    saved = save(e, written.json()['data']['revision'])
    assert saved.status_code == 201, saved.text
    version, continuing = saved.json()['data']['version'], saved.json()['data']['draft']
    assert version['model_revision_id'] == e['model']['model_revision_id']
    assert version['model_digest'] == e['model']['digest']
    assert version['content'] == written.json()['data']['content']
    assert version['version_number'] == 1
    assert continuing['based_on_model_revision_id'] == e['model']['model_revision_id']
    # Draft edits never change the saved explanation.
    edited = draft(e, content(e, represents='Changed after saving.'), continuing['revision'])
    assert edited.status_code == 200, edited.text
    assert of_version(e).json()['data']['explanation'] == version
    # A model version is explained once; its explanation never changes.
    again = save(e, edited.json()['data']['revision'])
    assert again.status_code == 409, again.text
    assert again.json()['error']['code'] == 'reference_conflict'
    assert of_version(e).json()['data']['explanation'] == version
    # The next model version takes the edited draft as its own explanation.
    second = save(e, edited.json()['data']['revision'], e['second']['model_revision_id'])
    assert second.status_code == 201, second.text
    assert second.json()['data']['version']['content']['represents'] == 'Changed after saving.'
    assert second.json()['data']['version']['version_number'] == 2
    page = e['client'].get(path(e, '/explanation/versions?limit=1')).json()['data']
    assert [v['version_number'] for v in page['items']] == [2] and page['next_cursor'] == 2
    state = e['client'].get(path(e, '/explanation')).json()['data']
    assert state['latest_version'] == second.json()['data']['version']


def test_saved_explanations_cannot_be_rewritten_or_deleted_in_storage(explained):
    written = draft(explained, content(explained)).json()['data']
    assert save(explained, written['revision']).status_code == 201
    with explained['store'].connection(write=True) as db:
        with pytest.raises(sqlite3.DatabaseError):
            db.execute("UPDATE model_explanation_versions SET payload='{}'")
    with explained['store'].connection(write=True) as db:
        with pytest.raises(sqlite3.DatabaseError):
            db.execute('DELETE FROM model_explanation_versions')


def test_an_explanation_is_read_from_the_application_store_with_the_modeling_service_gone(
    explained,
):
    e = explained
    written = draft(e, content(e)).json()['data']
    version = save(e, written['revision']).json()['data']['version']
    state = e['client'].get(path(e, '/explanation')).json()['data']
    # The service stops, and is then replaced by one that knows nothing of this model.
    e['double'].offline = True
    calls = e['double'].calls
    assert of_version(e).json()['data']['explanation'] == version
    assert e['client'].get(path(e, '/explanation')).json()['data'] == state
    assert e['double'].calls == calls
    replaced = TestClient(
        create_app(e['store'], Auth(e['store'], ORIGIN), ModelVersionDouble([])), base_url=ORIGIN
    )
    session = replaced.post(
        '/api/1/session', json=dict(username='owner', password=PASSWORD), headers={'Origin': ORIGIN}
    )
    assert session.status_code == 200
    assert of_version(dict(e, client=replaced)).json()['data']['explanation'] == version
    # Saving needs the exact model version, so it is refused while the service is unavailable.
    assert save(e, state['draft']['revision'], e['second']['model_revision_id']).status_code == 503


def test_cited_evidence_must_belong_to_the_study(explained):
    e = explained
    foreign = e['store'].create_study(e['actor'], uid(), 'Another study')
    other = e['client'].post(
        '/api/1/studies/' + foreign['study_id'] + '/evidence',
        json=dict(
            evidence_body(e),
            resource_scope=dict(scope_version='1', kind='study', study_id=foreign['study_id']),
        ),
    )
    assert other.status_code == 201, other.text
    elsewhere = other.json()['data']['evidence_version_id']
    for cited in (elsewhere, uid()):
        refused = draft(
            e, content(e, evidence_links=[dict(evidence_version_id=cited, relation='supports')])
        )
        assert refused.status_code == 422, refused.text
    assert e['client'].get(path(e, '/explanation')).json()['data']['draft'] is None
    own = e['client'].post('/api/1/studies/' + e['sid'] + '/evidence', json=evidence_body(e))
    links = [
        dict(evidence_version_id=own.json()['data']['evidence_version_id'], relation=relation)
        for relation in ('supports',)
    ]
    accepted = draft(e, content(e, evidence_links=links))
    assert accepted.status_code == 200, accepted.text
    saved = save(e, accepted.json()['data']['revision'])
    assert saved.status_code == 201, saved.text
    assert saved.json()['data']['version']['content']['evidence_links'] == links


def test_components_are_distinct_and_must_belong_to_the_explained_model_version(explained):
    e = explained
    item = content(e)['components'][0]
    assert draft(e, content(e, components=[item, item])).status_code == 422
    stranger = dict(item, instance_id=uid())
    written = draft(e, content(e, components=[stranger]))
    # A draft may name components of a model version not saved yet; a version may not.
    assert written.status_code == 200, written.text
    refused = save(e, written.json()['data']['revision'])
    assert refused.status_code == 422, refused.text
    assert of_version(e).json()['data']['explanation'] is None


def test_stale_revisions_and_replayed_commands(explained):
    e = explained
    command, body = uid(), content(e)
    first = draft(e, body, command=command)
    assert draft(e, body, command=command).json()['data'] == first.json()['data']
    assert draft(e, content(e, basis='x'), command=command).status_code == 409
    stale = draft(e, content(e, basis='Other'), expected=None)
    assert stale.status_code == 409 and stale.json()['error']['code'] == 'stale_revision'
    assert save(e, uid()).status_code == 409


def test_another_studys_model_and_invalid_queries_are_refused(explained):
    e = explained
    unknown = dict(e, mid=uid())
    assert unknown['client'].get(path(unknown, '/explanation')).status_code == 404
    assert of_version(unknown).status_code == 404
    for query in ('?extra=1', '?limit=0', '?limit=101', '?before=x', '?limit=1&limit=2'):
        assert e['client'].get(path(e, '/explanation/versions' + query)).status_code == 400
    assert e['client'].get(path(e, '/explanation?limit=1')).status_code == 400


def test_agent_writes_are_attributed_to_the_agent_for_its_user(explained):
    e = explained
    store = e['store']
    with store.connection(write=True) as db:
        agent = store.ensure_agent_actor(db, e['actor'], 'claude_managed', 'Coding agent (local)')
        store.create_delegation(
            db, agent, e['sid'], 'writer', ('read', 'draft', 'record'), time.time() + 3600
        )
    explanations = Explanations(store, Coordinator(store, e['double']))
    written = explanations.save_draft(
        agent,
        e['sid'],
        e['mid'],
        dict(command_id=uid(), expected_revision=None, content=content(e)),
    )
    saved = explanations.save_version(
        agent,
        e['sid'],
        e['mid'],
        dict(
            command_id=uid(),
            expected_revision=written['revision'],
            model_revision_id=e['model']['model_revision_id'],
        ),
    )
    page = attribution.page(store, e['actor'], e['sid'], None, 100)['items']
    assert sorted(
        (item['record_kind'], item['record_id'], item['version_id'], item['agent']['actor_id'])
        for item in page
    ) == sorted(
        [
            ('model_explanation_draft', e['mid'], written['revision'], agent),
            (
                'model_explanation_version',
                e['mid'],
                saved['version']['explanation_version_id'],
                agent,
            ),
        ]
    )
    assert {item['delegator']['actor_id'] for item in page} == {e['actor']}
    # A person's write records nothing.
    draft(e, content(e), saved['draft']['revision'])
    assert len(attribution.page(store, e['actor'], e['sid'], None, 100)['items']) == 2


def test_the_contract_declares_every_explanation_route(generated):  # noqa: F811
    paths = generated['paths']
    base = '/studies/{study_id}/models/{model_id}'
    assert paths[base + '/explanation']['get']['responses']['200']
    assert paths[base + '/explanation/draft']['post']['responses']['200']
    assert paths[base + '/explanation/versions']['post']['responses']['201']
    assert paths[base + '/revisions/{revision_id}/explanation']['get']['responses']['200']
    for name in (
        'ModelExplanationContent1',
        'ModelExplanationVersion1',
        'ModelVersionExplanation1',
    ):
        assert name in generated['components']['schemas']


def test_model_and_component_limits_freeze_with_the_exact_explanation(explained):
    e = explained
    instance = e['model']['instances'][0]['instance_id']
    body = content(e, schema_version='2', limits='Steady operation only.', component_details=[
        dict(instance_id=instance, description='Conserves sensible heat.',
             limits='Single phase; constant heat capacity.'),
    ])
    written = draft(e, body)
    assert written.status_code == 200, written.text
    version = save(e, written.json()['data']['revision'])
    assert version.status_code == 201, version.text
    saved = version.json()['data']
    assert saved['version']['schema_version'] == '2'
    assert of_version(e).json()['data']['explanation']['content'] == body
    changed = dict(body, limits='Changed draft only.')
    assert draft(e, changed, saved['draft']['revision']).status_code == 200
    assert of_version(e).json()['data']['explanation'] == saved['version']
    state = e['client'].get(path(e, '/explanation')).json()['data']
    downgrade = draft(e, content(e), state['draft']['revision'])
    assert downgrade.status_code == 422


def test_component_documentation_rejects_duplicates_and_foreign_model_targets(explained):
    e = explained
    item = dict(instance_id=uid(), description='Local description.', limits='Known domain.')
    body = content(e, schema_version='2', limits='', component_details=[item, item])
    assert draft(e, body).status_code == 422
    body['component_details'] = [item]
    written = draft(e, body)
    assert written.status_code == 200, written.text
    rejected = save(e, written.json()['data']['revision'])
    assert rejected.status_code == 422, rejected.text
    assert 'component_details' in str(rejected.json())
