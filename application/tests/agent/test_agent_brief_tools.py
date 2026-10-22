"""Study brief tools through the real application, middleware and agent route allowlist.

A writer delegation changes the brief draft section by section and saves versions; a section
left out stays unchanged, an item keeps the id the agent passes and a new item receives one.
A stale revision and refused input write nothing and name the tool's own input path. A reader
delegation is offered no brief write. Fresh synthetic store; no modeling service or runtime.
"""

import asyncio
import time
from uuid import uuid4

import pytest

from conftest import LOOPBACK_ORIGIN
from hyprn_mvp_app.agent_tools.api_client import ApiClient
from hyprn_mvp_app.agent_tools.registry import REGISTRY
from hyprn_mvp_app.agent_tools.spec import ToolContext, ToolError

WRITER = frozenset({'read', 'draft', 'record', 'outside_study'})
READER = frozenset({'read', 'outside_study'})
WRITES = {'update_study_brief', 'save_study_brief_version'}


class NoModeling:
    def call(self, *_, **__):
        from hyprn_mvp_app.contracts import DomainError

        raise DomainError('backend_unavailable', 503, outcome='unknown')


@pytest.fixture
def study(tmp_path):
    from hyprn_mvp_app.api import create_app
    from hyprn_mvp_app.auth import Auth
    from hyprn_mvp_app.store import Store

    store = Store(tmp_path / 'brief-tools.sqlite')
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
        # One live delegation per agent and study: the reader is a second agent principal.
        agent = store.ensure_agent_actor(db, owner, 'claude_managed', 'Coding agent (local)')
        other = store.ensure_agent_actor(db, owner, 'openai_agents', 'Coding agent (remote)')
        for who, ceiling, effects in ((agent, 'writer', WRITER), (other, 'reader', READER)):
            delegation = store.create_delegation(
                db, who, sid, ceiling, tuple(sorted(effects)), time.time() + 3600
            )
            sessions[ceiling] = delegation['delegation_id']
    return dict(
        app=create_app(store, auth, NoModeling()),
        store=store,
        sid=sid,
        agent=agent,
        writer=auth.mint_agent_session(sessions['writer']),
        reader=auth.mint_agent_session(sessions['reader']),
    )


def call(study, steps, effects=WRITER, session='writer'):
    """Run ``(tool, arguments)`` steps in order; each result or ToolError is returned."""

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


def criteria():
    return [
        {
            'kind': 'constraint',
            'name': 'Cruise range',
            'operator': 'ge',
            'threshold': 9000,
            'units': 'km',
        },
        {'kind': 'objective', 'name': 'Fuel mass', 'direction': 'minimize', 'units': 'kg'},
    ]


def test_sections_change_one_at_a_time_ids_are_kept_or_assigned_and_versions_freeze(study):
    (first,) = call(
        study,
        [
            (
                'update_study_brief',
                {
                    'expected_revision': None,
                    'content': {
                        'question': 'Which fuel should the aircraft use?',
                        'alternatives': [{'name': 'Kerosene'}, {'name': 'Liquid hydrogen'}],
                        'criteria': criteria(),
                    },
                },
            )
        ],
    )
    assert first['changed_sections'] == ['alternatives', 'criteria', 'question']
    kerosene, hydrogen = first['alternatives']
    assert kerosene['id'] != hydrogen['id']
    assert [c['priority'] for c in first['criteria']] == [1, 2]
    second, version, read = call(
        study,
        [
            (
                'update_study_brief',
                {
                    'expected_revision': first['revision_token'],
                    'content': {
                        'alternatives': [
                            {'alternative_id': hydrogen['id'], 'name': 'Liquid hydrogen'},
                            {'name': 'Methane'},
                        ]
                    },
                },
            ),
            ('get_study_brief', {}),
            ('get_study_brief', {'sections': ['question', 'criteria']}),
        ],
    )
    # The alternatives were replaced; the question and criteria were left out and stay.
    assert second['alternatives'][0]['id'] == hydrogen['id']
    assert [a['name']['untrusted_content']['text'] for a in second['alternatives']] == [
        'Liquid hydrogen',
        'Methane',
    ]
    assert read['question']['untrusted_content']['text']['question'].startswith('Which fuel')
    assert [c['id'] for c in read['criteria']] == [c['id'] for c in first['criteria']]
    saved, versions, after = call(
        study,
        [
            ('save_study_brief_version', {'expected_revision': version['revision_token']}),
            ('list_study_brief_versions', {}),
            ('get_study_brief', {'which': 'version_number', 'version_number': 1}),
        ],
    )
    assert saved['brief_version']['number'] == 1
    assert saved['draft']['based_on']['id'] == saved['brief_version']['id']
    assert [v['number'] for v in versions['versions']] == [1]
    assert after['alternatives'] == second['alternatives']
    with study['store'].connection() as db:
        row = db.execute('SELECT payload FROM study_brief_drafts').fetchone()
    assert study['agent'] in row['payload']


def test_a_stale_revision_and_refused_input_write_nothing_and_name_the_input_path(study):
    created, stale, missing, state = call(
        study,
        [
            ('update_study_brief', {'expected_revision': None, 'content': {'scope': 'Cruise.'}}),
            ('update_study_brief', {'expected_revision': None, 'content': {'scope': 'Other.'}}),
            ('save_study_brief_version', {'expected_revision': str(uuid4())}),
            ('get_study_brief', {'sections': ['question']}),
        ],
    )
    assert isinstance(stale, ToolError) and stale.category == 'conflict'
    assert stale.fields[0]['path'] == 'expected_revision'
    current = created['revision_token']
    (invalid,) = call(
        study,
        [
            (
                'update_study_brief',
                {
                    'expected_revision': current,
                    'content': {
                        'criteria': [{'kind': 'constraint', 'name': 'Mass', 'units': 'kg'}]
                    },
                },
            )
        ],
    )
    assert isinstance(invalid, ToolError) and invalid.category == 'invalid_input'
    assert all(f['path'].startswith('content.criteria') for f in invalid.fields), invalid.fields
    assert isinstance(missing, ToolError) and missing.category == 'conflict'
    assert state['revision_token'] == current
    assert state['question']['untrusted_content']['text']['scope'] == 'Cruise.'
    (versions,) = call(study, [('list_study_brief_versions', {})])
    assert versions['versions'] == []


def test_a_reader_delegation_is_offered_no_brief_write_and_its_session_cannot_write(study):
    offered = {t.name for t in REGISTRY.offered('claude_managed', 'authoring', READER)}
    assert offered & WRITES == set()
    assert WRITES <= {t.name for t in REGISTRY.offered('claude_managed', 'authoring', WRITER)}
    (refused,) = call(
        study,
        [('update_study_brief', {'expected_revision': None, 'content': {'scope': 'x'}})],
        effects=READER,
        session='reader',
    )
    assert isinstance(refused, ToolError) and refused.category == 'invalid_input'
    # Even offered by mistake, the reader session's write is refused by the application.
    (forbidden,) = call(
        study,
        [('update_study_brief', {'expected_revision': None, 'content': {'scope': 'x'}})],
        session='reader',
    )
    assert isinstance(forbidden, ToolError) and forbidden.category == 'access_lost'
    (empty,) = call(study, [('get_study_brief', {})])
    assert empty['draft'] == {'missing': 'no_draft'}


def test_brief_write_tools_declare_their_owner_receipts_and_routes():
    update = REGISTRY.tool('update_study_brief')
    save = REGISTRY.tool('save_study_brief_version')
    assert (update.effect, update.outcome, update.owners) == (
        'draft',
        'receipt:brief_draft',
        ('brief',),
    )
    assert (save.effect, save.outcome, save.owners) == (
        'record',
        'receipt:brief_version',
        ('brief',),
    )
    assert update.annotations['destructiveHint'] is True
    assert save.annotations['destructiveHint'] is False
    routes = REGISTRY.api_operations(WRITER)
    assert ('POST', '/api/1/studies/{study_id}/brief/draft') in routes
    assert ('POST', '/api/1/studies/{study_id}/brief/versions') in routes
    assert ('POST', '/api/1/studies/{study_id}/brief/draft') not in REGISTRY.api_operations(READER)
