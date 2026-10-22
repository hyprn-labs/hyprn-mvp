"""Evidence write tools through the real application and route allowlist.

A writer delegation adds one-source evidence records, as a verbatim excerpt kept apart from the
explanation or as a plain note, scoped with exactly the ids their kind names, and revises them
only from the latest version it read; fields left out keep their value and earlier versions
never change. Every saved version is attributed to the agent for its user; refused input and a
stale revision write nothing. Fresh synthetic store only.
"""

from uuid import uuid4

import pytest

from writer_tools import READER, WRITER, attributed, offered, one, writer_study

EXCERPT = {
    'excerpt': 'The structural index of hydrogen aircraft is 0.38 at Mach 5.',
    'source_reference': 'Andro et al. 2022, Hypersonic transport sizing',
    'location': 'Table 3',
    'explanation': 'Supports the structural index input at the cruise Mach number only.',
}


@pytest.fixture
def env(tmp_path):
    return writer_study(tmp_path)


def add(env, **fields):
    arguments = dict(title='Andro et al. 2022 — sizing method', scope={'kind': 'study'})
    arguments.update(fields)
    return one(env, 'add_evidence', arguments)


def test_an_excerpt_is_stored_apart_from_the_explanation_and_attributed(env):
    added = add(env, source_excerpt=EXCERPT, citations=['https://example.org/andro-2022'])
    assert added['previous_version'] == {'missing': 'first_version'}
    assert added['scope'] == {'kind': 'study'}
    read = one(env, 'read_evidence', {'evidence_version_id': added['id']})
    assert read['source_excerpt']['untrusted_content']['text'] == EXCERPT
    assert read['citations']['untrusted_content']['text'] == ['https://example.org/andro-2022']
    assert attributed(env) == {('evidence_version', added['evidence_id'], added['id'], 'evidence')}


def test_exactly_one_of_excerpt_and_note_and_exactly_the_scope_ids_of_its_kind(env):
    both = add(env, source_excerpt=EXCERPT, note='Also a note.')
    neither = add(env)
    assert both.category == neither.category == 'invalid_input'
    model = add(env, note='Applies to a model version.', scope={'kind': 'model_version'})
    assert model.category == 'invalid_input'
    assert {f['path'] for f in model.fields} == {'scope.model_id', 'scope.model_version_id'}
    extra = add(env, note='A study note.', scope={'kind': 'study', 'run_id': str(uuid4())})
    assert [f['path'] for f in extra.fields] == ['scope.run_id']
    absent = add(env, note='About a run.', scope={'kind': 'run', 'run_id': str(uuid4())})
    assert absent.category in ('invalid_input', 'not_found', 'conflict')
    assert attributed(env) == set()


def test_a_revision_keeps_what_it_does_not_change_and_needs_the_latest_version(env):
    added = add(env, note='Cruise at Mach 5 at 30 km.', citations=['Mission requirements, p. 12'])
    revised = one(
        env,
        'revise_evidence',
        {
            'evidence_id': added['evidence_id'],
            'expected_revision': added['id'],
            'title': 'Mission requirements — cruise point',
        },
    )
    assert revised['changed_fields'] == ['title']
    assert revised['previous_version']['id'] == added['id'] and revised['id'] != added['id']
    read = one(env, 'read_evidence', {'evidence_version_id': revised['id']})
    assert read['content']['untrusted_content']['text'] == 'Cruise at Mach 5 at 30 km.'
    assert read['citations']['untrusted_content']['text'] == ['Mission requirements, p. 12']
    first = one(env, 'read_evidence', {'evidence_version_id': added['id']})
    assert first['name']['untrusted_content']['text'] == 'Andro et al. 2022 — sizing method'
    stale = one(
        env,
        'revise_evidence',
        {'evidence_id': added['evidence_id'], 'expected_revision': added['id'], 'note': 'Late.'},
    )
    assert stale.category == 'conflict' and stale.fields[0]['path'] == 'expected_revision'
    assert attributed(env) == {
        ('evidence_version', added['evidence_id'], added['id'], 'evidence'),
        ('evidence_version', added['evidence_id'], revised['id'], 'evidence'),
    }


def test_a_reader_delegation_is_offered_no_evidence_write(env):
    for name in ('add_evidence', 'revise_evidence'):
        assert name in offered(WRITER) and name not in offered(READER)
