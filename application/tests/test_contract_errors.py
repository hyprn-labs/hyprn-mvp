"""Field-level contract errors through the public validation entry point and API.

Each failing field gets one diagnostic with a JSON-pointer path and a controlled message
derived from the contract (never from the submitted value). The envelope, codes and
statuses are unchanged: local input is ``invalid_request`` 400; a remote (modeling
backend) payload stays ``backend_unavailable`` 503 with no diagnostics.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hyprn_mvp_app import contracts
from hyprn_mvp_app.contracts import DomainError, validate
from hyprn_mvp_app.api import create_app
from hyprn_mvp_app.auth import Auth
from hyprn_mvp_app.modeling import ModelingClient
from hyprn_mvp_app.store import Store

from conftest import LOOPBACK_ORIGIN as ORIGIN

SECRET = 'SECRET-SUBMITTED-VALUE'


def test_linear_unique_items_preserves_pinned_json_schema_equality_and_mutation_checks():
    from jsonschema import Draft202012Validator
    from itertools import product

    values = [
        None,
        False,
        True,
        0,
        -0.0,
        1,
        1.0,
        2,
        1e20,
        10**20,
        '',
        '1',
        [],
        [1],
        [True],
        {},
        {'a': 1, 'b': [0]},
        {'b': [-0.0], 'a': 1.0},
    ]
    schema = dict(type='array', uniqueItems=True)
    original, fast = Draft202012Validator(schema), contracts.JsonValidator(schema)
    for left, right in product(values, repeat=2):
        assert fast.is_valid([left, right]) == original.is_valid([left, right])
    items = [{'path': str(i), 'sha256': str(i).zfill(64)} for i in range(1000)]
    assert fast.is_valid(items)
    items[-1] = dict(items[0])
    assert not fast.is_valid(items)


def rejected(name, value, **kw):
    with pytest.raises(DomainError) as caught:
        validate(name, value, **kw)
    return caught.value


def test_missing_and_unknown_fields_are_reported_per_field_not_at_root():
    error = rejected('Diagnostic', dict(path='/x', unexpected=SECRET, **{'a/b~c': 1}))
    assert (error.code, error.status, error.outcome) == ('invalid_request', 400, 'unchanged')
    # A wire/schema failure is distinguishable from domain failures but keeps the envelope.
    assert isinstance(error, contracts.ContractError) and error.schema == 'Diagnostic'
    paths = {f['path']: f['message'] for f in error.fields}
    assert paths == {
        '/code': 'Required field is missing.',
        '/message': 'Required field is missing.',
        '/element_ref': 'Required field is missing.',
        '/unexpected': 'Field is not allowed here.',
        '/a~1b~0c': 'Field is not allowed here.',
    }
    assert all(f['code'] == 'invalid' and f['element_ref'] is None for f in error.fields)
    assert 'Invalid typed value' not in str(error.fields)


def test_nested_type_bound_and_format_failures_name_the_field_and_rule():
    error = rejected(
        'Diagnostic',
        dict(path=[SECRET], code='x' * 5000, message='m', element_ref='not-a-uuid'),
    )
    by_path = {f['path']: f['message'] for f in error.fields}
    assert by_path['/path'] == 'Expected string.'
    assert by_path['/code'] == 'Must be at most 4096 characters.'
    assert by_path['/element_ref'].startswith(
        ('Does not match any allowed form', 'Must ', 'Expected ')
    )
    assert SECRET not in str(error.fields) and 'x' * 50 not in str(error.fields)


def test_closest_allowed_form_is_reported_for_typed_unions():
    error = rejected('UnitDeclaration1', dict(kind='physical', expression=SECRET))
    assert error.fields and all(
        f['path'] != '/' or f['message'] != 'Invalid typed value' for f in error.fields
    )
    assert SECRET not in str(error.fields)
    assert any(f['path'] in ('/', '/expression') for f in error.fields)


def test_non_canonical_value_points_at_the_offending_field():
    error = rejected(
        'Diagnostic',
        dict(path='/x', code='c', message='m', element_ref=None, extra=[1, float('nan')]),
    )
    assert error.fields == [
        dict(
            path='/extra/1', code='invalid', message='Number must be finite.', element_ref=None
        )
    ]
    error = rejected('Diagnostic', {'path': '\ud800'})
    assert error.fields == [
        dict(
            path='/path',
            code='invalid',
            message='Text must be valid Unicode.',
            element_ref=None,
        )
    ]
    error = rejected('Diagnostic', {'n': 2**53 + 1})
    assert error.fields[0]['path'] == '/n' and 'Integer' in error.fields[0]['message']


def test_remote_payload_failure_keeps_backend_unavailable_without_details():
    error = rejected('Diagnostic', dict(path=SECRET), remote=True)
    assert (error.code, error.status, error.outcome, error.fields) == (
        'backend_unavailable',
        503,
        'unknown',
        [],
    )
    assert error.data() == dict(
        code='backend_unavailable',
        status=503,
        current_revision=None,
        fields=[],
        outcome='unknown',
    )


def test_diagnostics_are_bounded_and_fit_the_public_diagnostic_schema():
    value = {f'k{i}': i for i in range(50)}
    error = rejected('Diagnostic', value)
    assert len(error.fields) == 20
    for field in error.fields:
        validate('Diagnostic', field)
    assert set(error.data()) == {'code', 'status', 'current_revision', 'fields', 'outcome'}


def test_valid_value_is_returned_unchanged():
    value = dict(path='/x', code='c', message='m', element_ref=None)
    assert validate('Diagnostic', value) is value


@pytest.fixture
def client(tmp_path):
    store = Store(tmp_path / 'app.sqlite')
    auth = Auth(store, ORIGIN)
    auth.provision('owner', 'correct horse battery staple')

    def unavailable(*args):
        raise OSError('No modeling service in this test')

    app = create_app(
        store, auth, ModelingClient('http://modeling.invalid', b'k' * 32, transport=unavailable)
    )
    client = TestClient(app, base_url=ORIGIN)
    session = client.post(
        '/api/1/session',
        json={'username': 'owner', 'password': 'correct horse battery staple'},
        headers={'Origin': ORIGIN},
    )
    assert session.status_code == 200, session.text
    client.headers.update(
        {'Origin': ORIGIN, 'X-CSRF-Token': session.json()['data']['csrf_token']}
    )
    return client


def test_api_request_shape_errors_carry_field_level_detail(client):
    response = client.post(
        '/api/1/studies',
        json={'command_id': '00000000-0000-4000-8000-000000000001', 'nme': SECRET},
    )
    assert response.status_code == 400
    error = response.json()['error']
    assert error['code'] == 'invalid_request' and error['outcome'] == 'unchanged'
    validate('Error', response.json())
    by_path = {f['path']: f for f in error['fields']}
    assert set(by_path) == {'/name', '/nme'}
    assert by_path['/name']['message'] == 'Required field is missing.'
    assert by_path['/nme']['message'] == 'Field is not allowed here.'
    assert SECRET not in response.text


def test_api_malformed_json_body_is_explained_without_echo(client):
    response = client.post(
        '/api/1/studies',
        content=b'{"name":"a","name":"' + SECRET.encode() + b'"}',
        headers={'Content-Type': 'application/json'},
    )
    assert response.status_code == 400
    error = response.json()['error']
    validate('Error', response.json())
    assert error['code'] == 'invalid_request'
    assert [f['path'] for f in error['fields']] == ['/']
    assert 'JSON' in error['fields'][0]['message'] and SECRET not in response.text


@pytest.mark.parametrize(
    'field,value,expected_path,expected_message',
    [
        (
            'assumptions',
            [dict(evidence_links=[])],
            '/content/assumptions/0/assumption_id',
            'Required field is missing.',
        ),
        (
            'original_question',
            SECRET,
            '/content/original_question',
            'Expected object with required fields "text", "attribution" or null.',
        ),
        ('question', True, '/content/question', 'Expected string.'),
    ],
)
def test_brief_errors_name_actionable_fields_without_echoing_values(
    client, field, value, expected_path, expected_message
):
    from uuid import uuid4
    from test_brief_api import content

    uid = str(uuid4())
    body = content()
    body[field] = value
    study = client.post(
        '/api/1/studies', json=dict(command_id=uid, name='Diagnostic study')
    ).json()['data']
    response = client.post(
        '/api/1/studies/' + study['study_id'] + '/brief/draft',
        json=dict(command_id=str(uuid4()), expected_revision=None, content=body),
    )
    assert response.status_code == 400, response.text
    validate('Error', response.json())
    fields = response.json()['error']['fields']
    assert any(
        f['path'] == expected_path and f['message'] == expected_message for f in fields
    ), fields
    assert SECRET not in response.text


def test_nested_discriminated_unit_error_identifies_expression():
    value = dict(
        temp_key='length',
        name='Length',
        code_symbol='length',
        direction='input',
        value_type='real_scalar',
        units=dict(kind='physical', expression=SECRET),
    )
    error = rejected('PortDeclaration3', value)
    fields = [f for f in error.fields if f['path'] == '/units/expression']
    assert error.fields == fields and len(fields) == 1
    assert fields[0]['message'].startswith('Must be one of:')
    assert SECRET not in str(error.fields)


def test_ambiguous_union_does_not_invent_a_selected_discriminator():
    error = rejected('UnitDeclaration1', dict(expression=SECRET))
    assert error.fields and SECRET not in str(error.fields)
    for field in error.fields:
        validate('Diagnostic', field)


def test_model_preview_names_unsupported_unit_inside_versioned_edit(client):
    import base64
    import hashlib
    from uuid import uuid4

    raw = b"outputs['y'] = inputs['x']\n"
    quantity = dict(
        temp_key='x',
        name='Input',
        code_symbol='x',
        direction='input',
        value_type='real_scalar',
        units=dict(kind='physical', expression='m'),
    )
    edit = dict(
        kind='create_definition',
        temp_key='component',
        name='Transform',
        definition_kind='explicit_component',
        ports=[quantity],
        source=dict(
            encoding='base64',
            media_type='text/x-python',
            bytes=base64.b64encode(raw).decode(),
            sha256=hashlib.sha256(raw).hexdigest(),
        ),
    )
    body = dict(schema_version='4', expected_revision='draft', edits=[edit])
    validate('PreviewRead4', body)
    quantity['units']['expression'] = SECRET
    response = client.post(f'/api/1/studies/{uuid4()}/models/{uuid4()}/preview', json=body)
    assert response.status_code == 400, response.text
    validate('Error', response.json())
    fields = response.json()['error']['fields']
    assert len(fields) == 1
    assert fields[0]['path'] == '/edits/0/ports/0/units/expression'
    assert fields[0]['message'].startswith('Must be one of:')
    assert SECRET not in response.text


def test_repeated_valid_snapshot_avoids_rewalking_schema_and_rejects_mutation(monkeypatch):
    from jsonschema import Draft202012Validator

    class Counted:
        def __init__(self):
            self.calls = 0
            self.validator = Draft202012Validator(
                {'type': 'array', 'items': {'type': 'number'}}
            )

        def iter_errors(self, value):
            self.calls += 1
            return self.validator.iter_errors(value)

    compiled = Counted()
    monkeypatch.setattr(contracts, 'validator', lambda _: compiled)
    value = [1.0, 2.0, 3.0]
    assert validate('snapshot-test', value) is value
    assert validate('snapshot-test', list(value)) == value
    assert compiled.calls == 1
    with pytest.raises(DomainError):
        validate('snapshot-test', tuple(value))
    value[1] = True
    with pytest.raises(DomainError):
        validate('snapshot-test', value)
    value[1] = float('nan')
    with pytest.raises(DomainError):
        validate('snapshot-test', value)
    replacement = Counted()
    monkeypatch.setattr(contracts, 'validator', lambda _: replacement)
    validate('snapshot-test', [1.0, 2.0, 3.0])
    assert replacement.calls == 1


def test_validation_cache_is_bounded_and_does_not_cache_invalid_values(monkeypatch):
    from jsonschema import Draft202012Validator

    class Counted:
        def __init__(self):
            self.calls = 0
            self.validator = Draft202012Validator({'type': 'string'})

        def iter_errors(self, value):
            self.calls += 1
            return self.validator.iter_errors(value)

    compiled = Counted()
    monkeypatch.setattr(contracts, 'validator', lambda _: compiled)
    monkeypatch.setattr(contracts, '_VALIDATED_MAX_BYTES', 32)
    monkeypatch.setattr(contracts, '_VALIDATED_MAX_ITEMS', 2)
    for value in ('first', 'second', 'third', 'first'):
        validate('bounded-test', value)
    assert compiled.calls == 4
    assert contracts._VALIDATED_BYTES <= 32
    assert len(contracts._VALIDATED) <= 2
    for _ in range(2):
        with pytest.raises(DomainError):
            validate('bounded-test', False)
    assert compiled.calls == 6


def test_execution_version_selection_preserves_union_and_nested_constraints(monkeypatch):
    from copy import deepcopy
    from itertools import product

    def tagged(version):
        return dict(
            type='object',
            required=['schema_version', 'id', 'value'],
            additionalProperties=False,
            properties=dict(
                schema_version=dict(const=version),
                id=dict(type='string', format='uuid'),
                value=dict(type='number', minimum=0),
            ),
        )

    schema = {
        '$defs': {
            'Old': tagged('1'),
            'New': tagged('2'),
            'Current': tagged('3'),
            'Nested': {'oneOf': [{'$ref': '#/$defs/Old'}, {'$ref': '#/$defs/New'}]},
            'All': {'oneOf': [{'$ref': '#/$defs/Nested'}, {'$ref': '#/$defs/Current'}]},
        }
    }
    monkeypatch.setattr(contracts, '_execution_schema', lambda: schema)
    contracts._execution_version_validator.cache_clear()
    try:
        original = contracts.JsonValidator(
            {**schema, '$ref': '#/$defs/All'}, format_checker=contracts.FormatChecker()
        )
        base = dict(schema_version='3', id='c12ae599-029b-45a8-b6b9-677ca19c6e26', value=1)
        for version, number, identifier, extra in product(
            ['1', '2', '3', '4', None, 3],
            [-1, 0, True, '1'],
            [base['id'], 'bad'],
            [False, True],
        ):
            value = dict(base, schema_version=version, value=number, id=identifier)
            if extra:
                value['unknown'] = 0
            selected = contracts._execution_version_validator('All', version)
            assert selected.is_valid(value) == original.is_valid(value)
        assert (
            contracts._execution_version_validator('All', '3').schema['properties']
            == (schema['$defs']['Current']['properties'])
        )
        # Missing tags and missing nested fields remain rejected by the public boundary.
        for missing in base:
            value = deepcopy(base)
            del value[missing]
            with pytest.raises(contracts.ContractError):
                contracts.validate_execution('All', value)
    finally:
        contracts._execution_version_validator.cache_clear()
        contracts._execution_validator.cache_clear()


@pytest.mark.parametrize('other', [dict(type='object'), dict(type='boolean')])
def test_execution_version_selection_keeps_unprovable_branches(monkeypatch, other):
    tagged = dict(
        type='object',
        required=['schema_version'],
        properties=dict(schema_version=dict(const='1')),
    )
    for alternatives in ([tagged, other], [tagged, tagged]):
        schema = {'$defs': {'All': dict(oneOf=alternatives)}}
        monkeypatch.setattr(contracts, '_execution_schema', lambda: schema)
        contracts._execution_version_validator.cache_clear()
        try:
            selected = contracts._execution_version_validator('All', '1')
            assert selected.schema['oneOf'] == alternatives
            original = contracts.JsonValidator({**schema, '$ref': '#/$defs/All'})
            for value in [dict(schema_version='1'), dict(schema_version='2'), {}, True]:
                assert selected.is_valid(value) == original.is_valid(value)
        finally:
            contracts._execution_version_validator.cache_clear()


def test_answer_nested_version_diagnostics_do_not_blame_derived_monetary_basis():
    from uuid import uuid4
    from test_study_answer_api import answer
    from hyprn_mvp_app.study_answer import validate_answer

    identity = lambda: str(uuid4())
    f = dict(alternatives=[dict(alternative_id=identity())], brief=identity(),
             calculation=identity(), run=identity(), limit=dict(criterion_id=identity()))
    content = answer(f, schema_version='3',
                     outcome=dict(kind='no_go', alternative_id=identity(), reason='A limit fails.'),
                     completion=dict(state='interim', deliverables=[]),
                     scientific_review={key: dict(state='limited', explanation='Screen only.')
                         for key in ('brief_fidelity', 'source_basis',
                                     'physical_validity', 'sensitivity')})
    content['comparison'][0]['monetary_basis'] = None
    body = dict(command_id=identity(), expected_revision=None, content=content)
    validate_answer('StudyAnswerDraftSaveRead3', body)
    del content['outcome']['alternative_id']
    with pytest.raises(DomainError) as caught:
        validate_answer('StudyAnswerDraftSaveRead3', body)
    assert caught.value.fields == [dict(
        path='/content/outcome/alternative_id', code='invalid',
        message='Required field is missing.', element_ref=None)]
