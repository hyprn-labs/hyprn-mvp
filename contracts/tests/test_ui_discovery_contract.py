"""Additive private discovery contract: closed wire shapes and unchanged roots."""
from hyprn_mvp_app.contracts import authored_schema
from test_schema_sources import assert_execution_schema
import copy
import json
from pathlib import Path
from uuid import uuid4

import pytest
from jsonschema import Draft202012Validator, FormatChecker, ValidationError

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = authored_schema()


def validate(kind, value):
    Draft202012Validator({**SCHEMA, '$ref': '#/$defs/' + kind},
                         format_checker=FormatChecker()).validate(value)


def test_rename_is_closed_nonempty_bounded_and_additive():
    for name in ['Engineering / α', 'a' * 4096]:
        validate('Edit', dict(kind='rename_model', name=name))
    for name in ['', 'a' * 4097, None, 3]:
        with pytest.raises(ValidationError):
            validate('Edit', dict(kind='rename_model', name=name))
    with pytest.raises(ValidationError):
        validate('Edit', dict(kind='rename_model', name='New', native_id=1))
    validate('Edit', dict(kind='rename_instance', instance_id=str(uuid4()), name='Existing'))
    # A model's name is a draft label, never part of any recorded revision version.
    branches = [ref['$ref'].split('/')[-1] for ref in SCHEMA['$defs']['ModelRevision']['oneOf']]
    assert branches and set(SCHEMA['$defs']['ModelRevision']) == {'oneOf'}
    for branch in branches:
        assert 'name' not in SCHEMA['$defs'][branch]['properties']


def test_revision_list_is_closed_typed_bounded_and_has_no_invented_events():
    row = dict(model_revision_id=str(uuid4()), parent_model_revision_id=None,
               originating_draft_revision=str(uuid4()), digest='a' * 64)
    response = dict(schema_version='1', request_id=str(uuid4()),
                    data=dict(items=[row], next_cursor=row['model_revision_id']))
    validate('RevisionListResponse', response)
    validate('RevisionListResponse', {**response, 'data': dict(items=[], next_cursor=None)})
    for bad in [dict(row, actor_id=str(uuid4())), dict(row, name='Current label'),
                dict(row, digest='bad'), dict(row, parent_model_revision_id='native:1')]:
        with pytest.raises(ValidationError):
            validate('RevisionListResponse', {**response, 'data': dict(items=[bad], next_cursor=None)})
    with pytest.raises(ValidationError):
        validate('RevisionListResponse', {**response, 'data': dict(items=[row] * 101, next_cursor=None)})
    with pytest.raises(ValidationError):
        validate('RevisionListResponse', {**response, 'data': dict(items=[], next_cursor='bad')})


def test_openapi_listing_has_exact_parameters_responses_and_schema_refs():
    spec = json.loads((ROOT / 'contracts/modeling.openapi.yaml').read_text())
    route = spec['paths']['/models/{model_id}/revisions']['get']
    params = {p['name']: p for p in route['parameters']}
    assert set(params) == {'model_id', 'cursor', 'limit'}
    assert params['limit']['schema']['minimum'] == 1
    assert params['limit']['schema']['maximum'] == 100
    assert params['cursor']['schema']['format'] == 'uuid'
    assert params['model_id']['required'] is True
    assert {'200', '400', '401', '403', '404', '413', '503'} <= set(route['responses'])
    assert route['responses']['200']['content']['application/json']['schema']['$ref'].endswith('/RevisionListResponse')
    assert spec['info']['version'] == '1.3.0'
    for schema in [SCHEMA, authored_schema()]:
        Draft202012Validator.check_schema(schema)
        assert_execution_schema()
