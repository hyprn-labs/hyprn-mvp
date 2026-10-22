"""Model write tools through the real application, route allowlist and modeling owner.

A writer delegation edits a model draft by component and port names: each operation becomes the
exact edit batch the public contract accepts (new definitions with their ports, units and source
hash, the placed component, resolved connections, a revised definition with every component on
it moved to the new version), only from the draft revision it read. It validates statically,
saves versions only from a clean draft, and creates models. Every write is attributed to the
agent for its user. The private modeling side is an in-process double that validates requests
against the private schemas and never runs code. Fresh synthetic store only.
"""

import base64
import hashlib

import pytest

from modeling_double import ModelingDouble
from writer_tools import READER, WRITER, attributed, offered, one, writer_study

SOURCE = "def compute(inputs, outputs):\n    outputs['fuel_mass'] = 0.3 * inputs['mtow']\n"


@pytest.fixture
def env(tmp_path):
    double = ModelingDouble()
    env = writer_study(tmp_path, modeling=double)
    double.bind(env['store'], env['sid'])
    env['double'], env['model'] = double, double.model_id
    return env


def token(env):
    return one(env, 'list_models', {})['models'][0]['revision_token']


def test_name_based_operations_become_the_exact_edit_batch_and_are_attributed(env):
    edited = one(
        env,
        'edit_model',
        {
            'model_id': env['model'],
            'expected_revision': token(env),
            'operations': [
                {
                    'op': 'add_component',
                    'name': 'Fuel',
                    'inputs': [{'name': 'mtow', 'unit': 'kg'}],
                    'outputs': [{'name': 'fuel_mass', 'unit': 'kg'}],
                    'source': SOURCE,
                },
                {'op': 'connect', 'from': 'Mass closure.mtow', 'to': 'Fuel.mtow'},
                {
                    'op': 'update_component',
                    'component': 'Range',
                    'set_meanings': [
                        {'port': 'fuel_fraction', 'meaning': 'Usable fuel over MTOW.'}
                    ],
                },
                {'op': 'add_assumption', 'statement': 'Fuel burn is linear.', 'component': 'Fuel'},
            ],
        },
    )
    ((action, batch),) = env['double'].batches
    assert action == 'edits' and batch['schema_version'] == '4'
    kinds = [edit['kind'] for edit in batch['edits']]
    assert kinds == [
        'create_definition',
        'instantiate',
        'connect',
        'revise_definition',
        'replace_local_instance_version',
        'add_assumption',
    ]
    create, place, connect, revise, rebind, assume = batch['edits']
    raw = base64.b64decode(create['source']['bytes'])
    assert raw.decode() == SOURCE and create['source']['sha256'] == hashlib.sha256(raw).hexdigest()
    assert [(p['name'], p['direction'], p['units']) for p in create['ports']] == [
        ('mtow', 'input', {'kind': 'physical', 'expression': 'kg'}),
        ('fuel_mass', 'output', {'kind': 'physical', 'expression': 'kg'}),
    ]
    assert place['version_ref'] == {'temp_key': create['temp_key']}
    assert connect['target_ref'] == {
        'instance_temp_key': place['temp_key'],
        'definition_temp_key': create['temp_key'],
        'port_temp_key': create['ports'][0]['temp_key'],
    }
    assert set(connect['source_ref']) == {'instance_id', 'port_id'}
    assert revise['changes'][0]['kind'] == 'set_quantity_definition'
    assert rebind['version_ref'] == {'temp_key': revise['temp_key']}
    assert rebind['expected_definition_version_id'] == revise['expected_definition_version_id']
    assert assume['owner'] == {'kind': 'instance', 'instance_temp_key': place['temp_key']}
    assert edited['preview_only'] is False and edited['revision_token']
    assert attributed(env) == {('model_draft', env['model'], edited['revision_token'], 'model')}


def test_a_stale_revision_or_an_unknown_name_sends_nothing(env):
    stale = one(
        env,
        'edit_model',
        {
            'model_id': env['model'],
            'expected_revision': 'draft-1',
            'operations': [{'op': 'rename_model', 'name': 'Renamed'}],
        },
    )
    assert stale.category == 'conflict' and stale.fields[0]['path'] == 'expected_revision'
    unknown = one(
        env,
        'edit_model',
        {
            'model_id': env['model'],
            'expected_revision': token(env),
            'operations': [{'op': 'remove_component', 'component': 'Wing'}],
        },
    )
    assert unknown.category == 'invalid_input'
    assert unknown.fields[0]['path'] == 'operations[0].component'
    extra = one(
        env,
        'edit_model',
        {
            'model_id': env['model'],
            'expected_revision': token(env),
            'operations': [{'op': 'rename_model', 'name': 'x', 'component': 'Range'}],
        },
    )
    assert [f['path'] for f in extra.fields] == ['operations[0].component']
    assert env['double'].batches == [] and attributed(env) == set()


def test_a_preview_changes_nothing_and_records_nothing(env):
    before = token(env)
    previewed = one(
        env,
        'edit_model',
        {
            'model_id': env['model'],
            'expected_revision': before,
            'operations': [{'op': 'rename_component', 'component': 'Range', 'name': 'Cruise'}],
            'preview_only': True,
        },
    )
    assert previewed['preview_only'] is True and previewed['revision_token'] is None
    assert [action for action, _ in env['double'].batches] == ['preview']
    assert token(env) == before and attributed(env) == set()


def test_versions_are_saved_only_from_a_clean_draft_and_attributed(env):
    double = env['double']
    double.diagnostics = [
        {'path': '/edits/0', 'code': 'missing_source', 'message': 'No source.', 'element_ref': None}
    ]
    blocked = one(
        env, 'commit_model_version', {'model_id': env['model'], 'expected_revision': token(env)}
    )
    assert blocked.category == 'invalid_input' and len(double.revisions[env['model']]) == 2
    double.diagnostics = []
    checked = one(env, 'validate_model', {'model_id': env['model']})
    assert checked['valid'] is True and 'no code was executed' in checked['note']
    saved = one(
        env, 'commit_model_version', {'model_id': env['model'], 'expected_revision': token(env)}
    )
    assert saved['model_version']['number'] == 3
    version = saved['model_version']['id']
    assert attributed(env) == {('model_version', env['model'], version, 'model')}


def test_a_created_model_belongs_to_the_study_and_is_attributed(env):
    created = one(env, 'create_model', {'name': 'Tank sizing'})
    model = created['model']['id']
    assert env['double'].created[0]['template'] == 'empty'
    assert {m['id'] for m in one(env, 'list_models', {})['models']} == {env['model'], model}
    assert attributed(env) == {('model_draft', model, created['revision_token'], 'model')}
    malformed = one(env, 'import_model', {'portable_record': '{"a": 1, "a": 2}'})
    assert malformed.category == 'invalid_input'


def test_a_reader_delegation_is_offered_no_model_write_or_check(env):
    names = ('create_model', 'edit_model', 'validate_model', 'commit_model_version', 'import_model')
    for name in names:
        assert name in offered(WRITER) and name not in offered(READER)


def test_quantity_changes_use_versioned_definition_edits_with_exact_existing_ids(env):
    from hyprn_mvp_app.agent_tools.catalogue.model import translate
    model = env['double'].drafts[env['model']]
    edits, _ = translate(model, [{
        'op': 'update_component', 'component': 'Range',
        'set_quantities': [
            {'current_name': 'fuel_fraction', 'name': 'Fuel fraction',
             'symbol': 'fuel_fraction', 'direction': 'input', 'unit': 'dimensionless'},
            {'name': 'diagnostic', 'direction': 'output', 'unit': 'km'},
        ],
    }])
    revision = next(e for e in edits if e['kind'] == 'revise_definition')
    changes = revision['changes']
    assert [c['kind'] for c in changes] == ['update_port', 'create_port']
    assert changes[0]['fields']['code_symbol'] == 'fuel_fraction'
    assert changes[1]['units'] == {'kind': 'physical', 'expression': 'km'}
    assert any(e['kind'] == 'replace_local_instance_version' for e in edits)


def test_catalogue_backed_monetary_edits_negotiate_current_model_format(env):
    caps = env['double'].caps
    caps['schema_versions'].append('5')
    caps['capabilities'].append(dict(
        caps['capabilities'][0], id='unit_declarations', version='2', supported=True,
    ))
    preview = one(env, 'edit_model', {
        'model_id': env['model'], 'expected_revision': token(env), 'preview_only': True,
        'operations': [{
            'op': 'add_component', 'name': 'Expense',
            'inputs': [{'name': 'mass', 'unit': 'kg'}, {'name': 'price', 'unit': 'USD/kg'}],
            'outputs': [{'name': 'expense', 'unit': 'USD'}],
            'source': "def compute(inputs, outputs):\n    outputs['expense'] = inputs['mass'] * inputs['price']\n",
        }],
    })
    assert preview['preview_only'] is True
    ((action, batch),) = env['double'].batches
    assert action == 'preview' and batch['schema_version'] == '5'
    ports = batch['edits'][0]['ports']
    assert [port['units'] for port in ports] == [
        {'kind': 'physical', 'expression': unit} for unit in ('kg', 'USD/kg', 'USD')
    ]
    assert attributed(env) == set()
