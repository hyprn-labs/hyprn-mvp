"""Model explanation tools through the real application, middleware and agent route allowlist.

A writer delegation changes the explanation draft section by section and saves it as the
explanation of one exact model version, attributed to the agent; the saved explanation reads
back unchanged and a second save for the same model version is refused. A reader delegation
reads and is offered no explanation write. Fresh synthetic store; the modeling boundary is a
double serving one captured model version.
"""

import asyncio
import copy
import time
from uuid import uuid4

import pytest

from conftest import LOOPBACK_ORIGIN
from execution_fixtures import fixture
from hyprn_mvp_app.agent_runtime import attribution
from hyprn_mvp_app.agent_tools.api_client import ApiClient
from hyprn_mvp_app.agent_tools.registry import REGISTRY
from hyprn_mvp_app.agent_tools.spec import ToolContext, ToolError
from hyprn_mvp_app.contracts import DomainError

WRITER = frozenset({'read', 'draft', 'record', 'outside_study'})
READER = frozenset({'read', 'outside_study'})
WRITES = {'update_model_explanation', 'save_model_explanation_version'}


class OneModelVersion:
    def __init__(self, model):
        self.model = model

    def call(self, _actor, _sid, method, path, *_, **__):
        if method == 'GET' and path.endswith('/revisions/' + self.model['model_revision_id']):
            return 200, dict(
                schema_version='1', request_id=str(uuid4()), data=copy.deepcopy(self.model)
            )
        raise DomainError('backend_unavailable', 503, outcome='unknown')


@pytest.fixture
def study(tmp_path):
    from hyprn_mvp_app.api import create_app
    from hyprn_mvp_app.auth import Auth
    from hyprn_mvp_app.store import Store

    model = fixture('chain')['frozen']['model_snapshot']
    store = Store(tmp_path / 'explanation-tools.sqlite')
    auth = Auth(store, LOOPBACK_ORIGIN)
    owner = str(uuid4())
    with store.connection(write=True) as db:
        db.execute(
            'INSERT INTO users(actor_id,username,password_hash) VALUES(?,?,?)',
            (owner, 'owner', 'unused'),
        )
    sid = store.create_study(owner, str(uuid4()), 'Hypersonic fuel choice')['study_id']
    sessions = {}
    with store.connection(write=True) as db:
        db.execute(
            'INSERT INTO model_associations VALUES(?,?,?)', (sid, model['model_id'], str(uuid4()))
        )
        agent = store.ensure_agent_actor(db, owner, 'claude_managed', 'Coding agent (local)')
        other = store.ensure_agent_actor(db, owner, 'openai_agents', 'Coding agent (remote)')
        for who, ceiling, effects in ((agent, 'writer', WRITER), (other, 'reader', READER)):
            delegation = store.create_delegation(
                db, who, sid, ceiling, tuple(sorted(effects)), time.time() + 3600
            )
            sessions[ceiling] = delegation['delegation_id']
    return dict(
        app=create_app(store, auth, OneModelVersion(model)),
        store=store,
        sid=sid,
        owner=owner,
        agent=agent,
        model=model,
        writer=auth.mint_agent_session(sessions['writer']),
        reader=auth.mint_agent_session(sessions['reader']),
    )


def call(study, steps, effects=WRITER, session='writer'):
    async def run():
        async with ApiClient(study['app'], LOOPBACK_ORIGIN) as client:
            ctx = ToolContext(
                surface='claude_managed',
                stage='authoring',
                effects=effects,
                api=client,
                session=study[session],
            )
            out = []
            for name, arguments in steps:
                try:
                    out.append(await REGISTRY.invoke(name, arguments, ctx))
                except ToolError as error:
                    out.append(error)
            return out

    return asyncio.run(run())


def test_the_draft_changes_by_section_and_saves_for_one_exact_model_version(study):
    from hyprn_mvp_app import identity
    with study['store'].connection(write=True) as db:
        identity.update(db, study['owner'], 'Guérric', 0)
    mid, revision = study['model']['model_id'], study['model']['model_revision_id']
    instance = study['model']['instances'][0]
    (first,) = call(
        study,
        [
            (
                'update_model_explanation',
                {
                    'model_id': mid,
                    'expected_revision': None,
                    'content': {
                        'represents': 'Cruise fuel mass of one mission.',
                        'components': [
                            {
                                'kind': 'instance',
                                'instance_id': instance['instance_id'],
                                'explanation': 'Applies the payload factor.',
                            }
                        ],
                    },
                },
            )
        ],
    )
    assert first['changed_sections'] == ['components', 'represents'], first
    second, saved, read, again = call(
        study,
        [
            (
                'update_model_explanation',
                {
                    'model_id': mid,
                    'expected_revision': first['revision_token'],
                    'content': {'basis': 'Breguet range relation.'},
                },
            ),
            ('get_model_explanation', {'model_id': mid}),
            ('get_model_explanation', {'model_id': mid, 'model_version_id': revision}),
            ('get_model_explanation', {'model_id': mid}),
        ],
    )
    text = second['explanation']['untrusted_content']['text']
    # A section left out stays as it is.
    assert text['represents'] == 'Cruise fuel mass of one mission.'
    assert text['basis'] == 'Breguet range relation.'
    assert saved['revision_token'] == second['revision_token']
    assert read['explanation'] == {'missing': 'no_saved_explanation'}
    (version,) = call(
        study,
        [
            (
                'save_model_explanation_version',
                {
                    'model_id': mid,
                    'model_version_id': revision,
                    'expected_revision': second['revision_token'],
                },
            )
        ],
    )
    assert version['explanation_version']['model_version']['id'] == revision, version
    frozen, refused = call(
        study,
        [
            ('get_model_explanation', {'model_id': mid, 'model_version_id': revision}),
            (
                'save_model_explanation_version',
                {
                    'model_id': mid,
                    'model_version_id': revision,
                    'expected_revision': version['draft']['revision_token'],
                },
            ),
        ],
    )
    assert frozen['explanation']['untrusted_content']['text']['basis'] == 'Breguet range relation.'
    assert isinstance(refused, ToolError)
    kinds = sorted(
        item['record_kind']
        for item in attribution.page(study['store'], study['owner'], study['sid'], None, 100)[
            'items'
        ]
        if item['agent']['actor_id'] == study['agent']
    )
    with study['store'].connection(write=True) as db:
        identity.update(db, study['owner'], 'Later name', 1)
    assert all(item['delegator']['display_name'] == 'Guérric' for item in
        attribution.page(study['store'], study['owner'], study['sid'], None, 100)['items'])
    assert kinds == [
        'model_explanation_draft',
        'model_explanation_draft',
        'model_explanation_version',
    ]


def test_a_stale_revision_writes_nothing(study):
    mid = study['model']['model_id']
    (stale,) = call(
        study,
        [
            (
                'update_model_explanation',
                {'model_id': mid, 'expected_revision': str(uuid4()), 'content': {'basis': 'x'}},
            )
        ],
    )
    assert isinstance(stale, ToolError) and stale.category == 'conflict'
    (state,) = call(study, [('get_model_explanation', {'model_id': mid})])
    assert state['draft'] == {'missing': 'no_draft'}


def test_a_reader_reads_and_is_offered_no_explanation_write(study):
    (state,) = call(
        study,
        [('get_model_explanation', {'model_id': study['model']['model_id']})],
        effects=READER,
        session='reader',
    )
    assert state['draft'] == {'missing': 'no_draft'}
    offered = {tool.name for tool in REGISTRY.offered('claude_managed', 'authoring', READER)}
    assert 'get_model_explanation' in offered and not WRITES & offered


def test_agent_authors_limits_without_replacing_other_explanation_sections(study):
    mid = study['model']['model_id']
    instance = study['model']['instances'][0]['instance_id']
    first, = call(study, [('update_model_explanation', dict(
        model_id=mid, expected_revision=None, content=dict(
            represents='Steady thermal model.', limits='No transient storage.',
            component_details=[dict(instance_id=instance,
                                    description='Conserves sensible heat.',
                                    limits='Single phase only.')],
        ),
    ))])
    assert not isinstance(first, ToolError), first
    second, = call(study, [('update_model_explanation', dict(
        model_id=mid, expected_revision=first['revision_token'],
        content=dict(basis='Conservation of energy.'),
    ))])
    assert second['limits']['untrusted_content']['text'] == 'No transient storage.'
    assert second['component_details'][0]['limits']['untrusted_content']['text'] == 'Single phase only.'
    assert second['explanation']['untrusted_content']['text']['represents'] == 'Steady thermal model.'
