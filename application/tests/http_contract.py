"""Public HTTP contract assertions shared by owner boundary tests."""

from jsonschema import Draft202012Validator, FormatChecker


def assert_shape(generated, name, value):
    Draft202012Validator(
        {**generated, '$ref': '#/components/schemas/' + name}, format_checker=FormatChecker()
    ).validate(value)


def assert_http(generated, path, method, response):
    schema = generated['paths'][path][method]['responses'][str(response.status_code)][
        'content'
    ]['application/json']['schema']
    Draft202012Validator({**generated, **schema}, format_checker=FormatChecker()).validate(
        response.json()
    )
