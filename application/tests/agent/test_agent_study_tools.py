"""Study brief and study creation tools through the real application and route allowlist.

Only the brief tool edits framing. A study the agent creates belongs to the delegating
user, is attributed to the agent and stays out of the session's reach. A reader delegation
is offered neither write tool. Fresh synthetic store only.
"""

import pytest

from hyprn_mvp_app.agent_tools.spec import ToolError
from writer_tools import READER, WRITER, attributed, offered, one, writer_study


@pytest.fixture
def env(tmp_path):
    return writer_study(tmp_path)


def test_only_the_brief_tool_edits_scientific_framing(env):
    assert 'update_study_context' not in offered(WRITER)
    assert 'update_study_brief' in offered(WRITER)
    before = env['store'].study(env['owner'], env['sid'])
    refused = one(env, 'update_study_context', {'expected_revision': before['revision'], 'name': 'Lost'})
    assert isinstance(refused, ToolError) and refused.category == 'invalid_input'
    assert env['store'].study(env['owner'], env['sid']) == before
    assert attributed(env) == set()


def test_a_created_study_belongs_to_the_user_and_stays_out_of_the_session(env):
    created = one(env, 'create_study', {'name': 'Hydrogen storage study'})
    new = created['study']['id']
    assert new != env['sid']
    store = env['store']
    assert store.study(env['owner'], new)['name'] == 'Hydrogen storage study'
    with store.connection() as db:
        rows = db.execute('SELECT actor_id,role FROM memberships WHERE study_id=?', (new,))
        assert [tuple(r) for r in rows] == [(env['owner'], 'owner')]
    assert attributed(env, new) == {('study', new, None, 'study_create')}
    # The session's study is unchanged: the overview still reads the delegated study.
    assert one(env, 'get_study_overview', {})['study']['id'] == env['sid']


def test_a_reader_delegation_is_offered_no_study_write(env):
    for name in ('update_study_brief', 'create_study'):
        assert name in offered(WRITER) and name not in offered(READER)
    refused = one(env, 'create_study', {'name': 'Reader study'}, effects=READER, session='reader')
    assert refused.category == 'invalid_input'
