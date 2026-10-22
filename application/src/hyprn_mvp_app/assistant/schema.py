"""Closed public conversation shapes; raw provider records never cross this boundary."""

from copy import deepcopy

from jsonschema import Draft202012Validator

from ..contracts import DomainError


def obj(properties):
    return {
        'type': 'object',
        'properties': properties,
        'required': list(properties),
        'additionalProperties': False,
    }


def text(limit):
    return {'type': 'string', 'maxLength': limit}


def nullable(value):
    return {'anyOf': [value, {'type': 'null'}]}


DEFINITIONS = {
    'AssistantMessageRequest1': obj(
        {
            'command_id': {'type': 'string', 'format': 'uuid'},
            'text': {'type': 'string', 'minLength': 1, 'maxLength': 16384},
        }
    ),
    'AssistantStopRequest1': obj({}),
    'AssistantConversationRead1': obj(
        {
            'state': {'enum': ['idle', 'running', 'stopping', 'blocked', 'unavailable']},
            'error': nullable(text(128)),
            'can_send': {'type': 'boolean'},
            'can_stop': {'type': 'boolean'},
            'messages': {
                'type': 'array',
                'maxItems': 200,
                'items': obj(
                    {
                        'message_id': text(160),
                        'role': {'enum': ['user', 'assistant']},
                        'text': text(65536),
                        'actor_id': nullable({'type': 'string', 'format': 'uuid'}),
                        'author_display_name': nullable(text(128)),
                        'created_at': {'type': 'number'},
                    }
                ),
            },
            'has_earlier_messages': {'type': 'boolean'},
        }
    ),
}


DEFINITIONS['AssistantConversationRead2'] = deepcopy(DEFINITIONS['AssistantConversationRead1'])
DEFINITIONS['AssistantConversationRead2']['properties']['state'] = {
    'enum': ['idle', 'queued', 'starting', 'running', 'waiting', 'stopping', 'blocked', 'unavailable']}


money = {'type': 'integer', 'minimum': 0, 'maximum': 10**12}
DEFINITIONS['AssistantBudgetRead1'] = obj({
    'configured': {'type': 'boolean'},
    'currency': {'const': 'USD'},
    'limit_cents': nullable(money),
    'reserved_cents': money,
    'unallocated_cents': nullable(money),
    'spent_cents': nullable(money),
    'remaining_cents': nullable(money),
    'prior_cents': money,
    'new_study_limit_cents': nullable(money),
    'study_limit_cents': nullable(money),
    'study_spent_cents': nullable(money),
    'study_remaining_cents': nullable(money),
    'checked_at': nullable({'type': 'number'}),
    'usage_current': {'type': 'boolean'},
    'approved': nullable(obj({
        'minor': money, 'currency': {'type': 'string', 'pattern': '^[A-Z]{3}$'},
        'conversion_date': nullable(text(10)),
    })),
})


def validate(name, value):
    errors = list(Draft202012Validator(DEFINITIONS[name]).iter_errors(value))
    if errors:
        raise DomainError('invalid_request', 400)
