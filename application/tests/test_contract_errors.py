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
        'Diagnostic', dict(path=[SECRET], code='x' * 5000, message='m', element_ref='not-a-uuid')
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
        dict(path='/extra/1', code='invalid', message='Number must be finite.', element_ref=None)
    ]
    error = rejected('Diagnostic', {'path': '\ud800'})
    assert error.fields == [
        dict(path='/path', code='invalid', message='Text must be valid Unicode.', element_ref=None)
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
        code='backend_unavailable', status=503, current_revision=None, fields=[], outcome='unknown'
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
    client.headers.update({'Origin': ORIGIN, 'X-CSRF-Token': session.json()['data']['csrf_token']})
    return client


def test_api_request_shape_errors_carry_field_level_detail(client):
    response = client.post(
        '/api/1/studies', json={'command_id': '00000000-0000-4000-8000-000000000001', 'nme': SECRET}
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


def approach_request():
    return dict(
        schema_version='2',
        expected_revision=None,
        content=dict(
            schema_version='2',
            question='Compare designs',
            scope='',
            limitations='',
            open_questions='',
            model_bindings=[],
            steps=[],
            assumptions=[],
            cases=[],
            basis_refs=[],
            original_question=None,
            elaboration=None,
            limit_items=[],
        ),
    )


@pytest.mark.parametrize(
    'failure,expected_path,expected_message',
    [
        ('role', '/content/assumptions/0/role', 'Required field is missing.'),
        (
            'question',
            '/content/original_question',
            'Expected object with required fields "text", "attribution" or null.',
        ),
        ('remaining_work', '/content/steps/0/remaining_work', 'Must be at most 0 characters.'),
    ],
)
def test_versioned_approach_errors_name_the_actionable_field(
    client, failure, expected_path, expected_message
):
    from uuid import uuid4

    uid = str(uuid4())
    request = approach_request()
    validate('ApproachPreviewRequestRead2', request)
    content = request['content']
    if failure == 'role':
        content['assumptions'] = [dict(assumption_id=uid, statement=SECRET, evidence_links=[])]
    elif failure == 'question':
        content['original_question'] = SECRET
    else:
        content['steps'] = [
            dict(
                step_id=uid,
                title='Compute response',
                purpose='',
                rationale='',
                remaining_work=SECRET,
                intent=dict(transformation='', inputs='', outputs='', depends_on_step_ids=[]),
                implementation_state='linked',
                implementation_refs=[dict(kind='model', binding_id=uid)],
                assumption_refs=[],
                evidence_links=[],
            )
        ]
    study = client.post(
        '/api/1/studies', json=dict(command_id=uid, name='Diagnostic study')
    ).json()['data']
    response = client.post(
        '/api/1/studies/' + study['study_id'] + '/approach/preview', json=request
    )
    assert response.status_code == 400, response.text
    validate('Error', response.json())
    assert response.json()['error']['fields'] == [
        dict(path=expected_path, code='invalid', message=expected_message, element_ref=None)
    ]
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
            self.validator = Draft202012Validator({'type': 'array', 'items': {'type': 'number'}})

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
