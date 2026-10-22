"""Every agent write is attributed in the owner's own transaction.

When the receipt actor of an accepted command is an agent actor, the owner records which agent,
for which delegating user, wrote which record through which command, in the transaction that
stores the record and its receipt; a person's write records nothing, a refused command records
nothing, and an agent write is refused (with nothing stored) while no attribution recorder is
composed. A store made before a record kind existed keeps every entry when its table is rebuilt.
Fresh synthetic off-cloud stores; no modeling service, runtime or live store.
"""

from legacy_study_support import seed_legacy_context

import sqlite3
import time
from uuid import uuid4

import pytest

from conftest import LOOPBACK_ORIGIN
from hyprn_mvp_app.agent_runtime import attribution, schema
from hyprn_mvp_app.api import create_app
from hyprn_mvp_app.auth import Auth
from hyprn_mvp_app.brief import Briefs
from hyprn_mvp_app.contracts import DomainError
from hyprn_mvp_app.store import Store

WRITER = ('read', 'draft', 'record', 'submit', 'outside_study')
AGENT_NAME = 'Coding agent (local)'


def uid():
    return str(uuid4())


class NoModeling:
    def call(self, *_, **__):
        raise DomainError('backend_unavailable', 503, outcome='unknown')


def people(store):
    owner = uid()
    with store.connection(write=True) as db:
        db.execute(
            'INSERT INTO users(actor_id,username,password_hash) VALUES(?,?,?)',
            (owner, 'owner', 'unused'),
        )
    return owner


def delegated(store, owner, sid):
    with store.connection(write=True) as db:
        agent = store.ensure_agent_actor(db, owner, 'claude_managed', AGENT_NAME)
        delegation = store.create_delegation(db, agent, sid, 'writer', WRITER, time.time() + 3600)
    return agent, delegation['delegation_id']


@pytest.fixture
def env(tmp_path):
    store = Store(tmp_path / 'attribution.sqlite')
    # The composition root wires the recorder; the application itself is not exercised here.
    create_app(store, Auth(store, LOOPBACK_ORIGIN), NoModeling())
    owner = people(store)
    study = store.create_study(owner, uid(), 'Fuel choice')
    agent, delegation = delegated(store, owner, study['study_id'])
    return dict(
        store=store,
        owner=owner,
        sid=study['study_id'],
        study=study,
        agent=agent,
        delegation=delegation,
        path=tmp_path / 'attribution.sqlite',
    )


def entries(env, sid=None):
    page = attribution.page(env['store'], env['owner'], sid or env['sid'], None, 100)
    return [
        (item['record_kind'], item['record_id'], item['version_id'], item['command_category'])
        for item in page['items']
    ]


def note(sid, title='Mission note'):
    return dict(
        evidence_schema_version='3',
        title=title,
        kind='note',
        content='Cruise at Mach 0.78 at 35,000 ft.',
        source_refs=['Mission requirements, p. 12'],
        resource_scope=dict(scope_version='1', kind='study', study_id=sid),
    )


def test_a_persons_writes_record_no_attribution(env):
    store, owner, sid = env['store'], env['owner'], env['sid']
    store.add_evidence(owner, sid, uid(), note(sid))
    assert entries(env) == []


def test_attribution_freezes_alias_and_legacy_rows_keep_account_names(env):
    from hyprn_mvp_app import identity
    store, agent, sid, owner = env['store'], env['agent'], env['sid'], env['owner']
    with store.connection(write=True) as db:
        identity.update(db, owner, 'Guérric', 0)
    command = uid()
    store.add_evidence(agent, sid, command, note(sid))
    with store.connection(write=True) as db:
        identity.update(db, owner, 'Later alias', 1)
    store.add_evidence(agent, sid, command, note(sid))
    page = attribution.page(store, owner, sid, None, 100)
    assert page['items'][0]['delegator']['display_name'] == 'Guérric'
    with store.connection(write=True) as db:
        db.execute('UPDATE agent_attribution SET delegator_display_name=NULL')
    assert attribution.page(store, owner, sid, None, 100)['items'][0]['delegator']['display_name'] == 'owner'


def test_historical_context_and_current_evidence_preserve_agent_attribution(env):
    store, agent, sid = env['store'], env['agent'], env['sid']
    command = uid()
    changed = seed_legacy_context(store,
        agent, sid, command, env['study']['revision'], dict(description='By the agent')
    )
    added = store.add_evidence(agent, sid, uid(), note(sid))
    revised = store.revise_evidence(
        agent,
        sid,
        added['evidence_id'],
        uid(),
        added['evidence_version_id'],
        note(sid, 'Mission note, corrected'),
    )
    page = attribution.page(store, env['owner'], sid, None, 100)['items']
    assert {(i['record_kind'], i['record_id'], i['version_id']) for i in page} == {
        ('study_context', sid, changed['revision']),
        ('evidence_version', added['evidence_id'], added['evidence_version_id']),
        ('evidence_version', added['evidence_id'], revised['evidence_version_id']),
    }
    for item in page:
        assert item['agent'] == dict(actor_id=agent, display_name=AGENT_NAME)
        assert item['delegator'] == dict(actor_id=env['owner'], display_name='owner')
    # A replay returns the stored outcome and adds no second entry.
    seed_legacy_context(store,
        agent, sid, command, env['study']['revision'], dict(description='By the agent')
    )
    assert len(entries(env)) == 3


def test_a_study_an_agent_created_is_attributed_in_the_new_study(env):
    store, agent = env['store'], env['agent']
    created = store.create_study(agent, uid(), 'Agent study', delegation_id=env['delegation'])
    new = created['study_id']
    assert entries(env, new) == [('study', new, None, 'study_create')]
    listed = attribution.created_studies(store, env['owner'], None, 100)['items']
    assert [item['study_id'] for item in listed] == [new]


def test_brief_drafts_and_versions_written_by_an_agent_are_attributed(env):
    store, agent, sid = env['store'], env['agent'], env['sid']
    briefs = Briefs(store)
    content = dict(
        schema_version='1',
        question='Which fuel?',
        original_question=None,
        elaboration=None,
        scope='',
        alternatives=[],
        criteria=[],
        assumptions=[],
        limits=[],
        open_questions=[],
    )
    draft = briefs.save_draft(
        agent, sid, dict(command_id=uid(), expected_revision=None, content=content)
    )
    saved = briefs.save_version(
        agent, sid, dict(command_id=uid(), expected_revision=draft['revision'])
    )
    assert set(entries(env)) == {
        ('brief_draft', sid, draft['revision'], 'brief_draft'),
        ('brief_version', sid, saved['version']['brief_version_id'], 'brief_version'),
    }


def test_a_refused_agent_command_records_nothing(env):
    store, agent, sid = env['store'], env['agent'], env['sid']
    saved = store.add_evidence(agent, sid, uid(), note(sid))
    before = entries(env)
    with pytest.raises(DomainError, match='stale_revision'):
        store.revise_evidence(agent, sid, saved['evidence_id'], uid(), uid(), note(sid))
    assert entries(env) == before


def test_an_agent_write_without_a_recorder_is_refused_and_stores_nothing(tmp_path):
    store = Store(tmp_path / 'uncomposed.sqlite')
    schema.ensure(store)
    owner = people(store)
    study = store.create_study(owner, uid(), 'Fuel choice')
    agent, _ = delegated(store, owner, study['study_id'])
    with pytest.raises(DomainError, match='internal_error'):
        store.add_evidence(agent, study['study_id'], uid(), note(study['study_id']))
    assert store.study(owner, study['study_id'])['name'] == 'Fuel choice'
    with sqlite3.connect(tmp_path / 'uncomposed.sqlite') as db:
        assert db.execute("SELECT count(*) FROM receipts WHERE category='evidence'").fetchone() == (0,)


def test_a_table_made_before_a_record_kind_existed_is_rebuilt_with_every_entry(env):
    store, sid, agent = env['store'], env['sid'], env['agent']
    old = schema._ATTRIBUTION_TABLE.replace("'brief_draft',", '').replace("'brief_version',", '')
    old = old.replace(', delegator_display_name TEXT', '')
    assert "'brief_draft'" not in old
    command = uid()
    seed_legacy_context(
        store,
        agent,
        sid,
        command,
        env['study']['revision'],
        dict(description='Kept'),
    )
    before = entries(env)
    with sqlite3.connect(env['path']) as db:
        rows = [row[:-1] for row in db.execute('SELECT * FROM agent_attribution').fetchall()]
        db.execute('ALTER TABLE agent_attribution RENAME TO kept')
        db.execute('DROP TRIGGER agent_attribution_no_delete')
        db.execute(old)
        db.executemany(
            'INSERT INTO agent_attribution VALUES(' + ','.join('?' * len(rows[0])) + ')', rows
        )
        db.execute('DROP TABLE kept')
    schema.ensure(store)
    assert entries(env) == before
    with sqlite3.connect(env['path']) as db:
        (sql,) = db.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='agent_attribution'"
        ).fetchone()
        assert all(f"'{kind}'" in sql for kind in schema.RECORD_KINDS)
        with pytest.raises(sqlite3.DatabaseError, match='never deleted'):
            db.execute('DELETE FROM agent_attribution')
