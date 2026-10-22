"""Run submission through the real application, route allowlist and execution owner.

A writer delegation submits one run per saved configuration version only when execution is
ready; when it is not, nothing is submitted and the readiness reasons are returned. Each run is
accepted by the execution owner, named after its configuration and attributed to the agent for
its user. An unknown configuration stops the call before anything is submitted. A reader
delegation is offered no submission. Fresh synthetic store; no runtime or modeling service.
"""

import json
import time

import pytest

from execution_fixtures import fixture
from hyprn_mvp_app.store import digest
from writer_tools import READER, WRITER, attributed, offered, one, uid, writer_study


class ReadyModeling:
    """The modeling double of an installation whose engine supports the flat scalar program."""

    def call(self, actor, sid, method, path, *_, **__):
        assert (method, path) == ('GET', '/capabilities'), path
        return 200, {'data': {'capabilities': [{'id': 'flat_explicit_scalar', 'supported': True}]}}


def saved_configuration(env, name):
    """One saved configuration version of the retained chain case, stored by its owner's rows."""
    store, sid = env['store'], env['sid']
    case = fixture('chain')
    frozen = case['frozen']
    configuration = frozen['configuration']
    study = store.study(env['owner'], sid)
    configuration.update(
        schema_version='2',
        study_id=sid,
        name=name,
        configuration_id=uid(),
        configuration_revision_id=uid(),
        context_source=dict(kind='current_study', expected_study_revision=study['revision']),
        derivation=None,
    )
    configuration['context_snapshot'].update(description='', boundary='')
    for item in configuration['inputs']:
        item['result_binding'] = None
    configuration['digest'] = digest({k: v for k, v in configuration.items() if k != 'digest'})
    with store.connection(write=True) as db:
        db.execute(
            'INSERT INTO configurations VALUES(?,?,?,?)',
            (
                configuration['configuration_revision_id'],
                configuration['configuration_id'],
                sid,
                json.dumps(frozen),
            ),
        )
        db.execute(
            'INSERT OR IGNORE INTO model_associations VALUES(?,?,?)',
            (sid, configuration['model_id'], uid()),
        )
        db.execute(
            'INSERT INTO configuration_families VALUES(?,?,?)',
            (configuration['configuration_id'], sid, configuration['configuration_revision_id']),
        )
    return configuration['configuration_revision_id']


@pytest.fixture
def env(tmp_path):
    return writer_study(tmp_path, modeling=ReadyModeling())


def runs_stored(env):
    with env['store'].connection() as db:
        return db.execute('SELECT count(*) FROM run_associations').fetchone()[0]


def test_nothing_is_submitted_while_execution_is_not_ready(env):
    version = saved_configuration(env, 'Liquid hydrogen, 9,000 km')
    refused = one(env, 'submit_runs', {'configuration_version_ids': [version]})
    assert refused.category == 'unavailable' and 'observation_stale' in refused.message
    assert runs_stored(env) == 0 and attributed(env) == set()


def test_each_configuration_runs_once_named_after_it_and_attributed(env):
    hydrogen = saved_configuration(env, 'Liquid hydrogen, 9,000 km')
    kerosene = saved_configuration(env, 'Kerosene, 9,000 km')
    env['store'].publish_execution_observation('ready', None, time.time())
    result = one(
        env,
        'submit_runs',
        {'configuration_version_ids': [hydrogen, kerosene], 'wall_seconds': 600},
    )
    assert result['refused'] == [] and result['not_submitted'] == []
    names = [r['name']['untrusted_content']['text'] for r in result['runs']]
    assert names == ["Run of 'Liquid hydrogen, 9,000 km'", "Run of 'Kerosene, 9,000 km'"]
    assert {r['state'] for r in result['runs']} == {'accepted_run'}
    assert runs_stored(env) == 2
    assert attributed(env) == {('run', r['id'], None, 'run') for r in result['runs']}


def test_an_unknown_configuration_stops_the_call_before_any_submission(env):
    known = saved_configuration(env, 'Liquid hydrogen, 9,000 km')
    env['store'].publish_execution_observation('ready', None, time.time())
    refused = one(env, 'submit_runs', {'configuration_version_ids': [known, uid()]})
    assert refused.category == 'not_found'
    assert runs_stored(env) == 0


def test_a_reader_delegation_is_offered_no_submission(env):
    assert 'submit_runs' in offered(WRITER) and 'submit_runs' not in offered(READER)
