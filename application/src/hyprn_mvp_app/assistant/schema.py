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


DEFINITIONS['AssistantResumeRequest1'] = obj({})
DEFINITIONS['AssistantConversationRead3'] = deepcopy(DEFINITIONS['AssistantConversationRead2'])
DEFINITIONS['AssistantConversationRead3']['properties']['can_resume'] = {'type': 'boolean'}
DEFINITIONS['AssistantConversationRead3']['required'].append('can_resume')
DEFINITIONS['AssistantConversationRead4'] = deepcopy(DEFINITIONS['AssistantConversationRead3'])
DEFINITIONS['AssistantConversationRead4']['properties'].update(
    next_cursor=nullable(text(160)), earlier_cursor=nullable(text(160)),
    has_more_messages={'type': 'boolean'},
)
DEFINITIONS['AssistantConversationRead4']['required'] += [
    'next_cursor', 'earlier_cursor', 'has_more_messages',
]
DEFINITIONS['AssistantAnalysisProgress1'] = obj({
    'calculation_version_id': {'type': 'string', 'format': 'uuid'},
    'state': {'enum': ['calculating', 'validating']},
    'completed_count': {'type': 'integer', 'minimum': 0},
    'total_count': {'type': 'integer', 'minimum': 0},
    'reused_count': nullable({'type': 'integer', 'minimum': 0}),
    'admission_state': nullable(text(64)),
    'last_progress_at': {'type': 'number'},
})
DEFINITIONS['AssistantConversationRead5'] = deepcopy(DEFINITIONS['AssistantConversationRead4'])
DEFINITIONS['AssistantConversationRead5']['properties']['analysis_progress'] = nullable(
    DEFINITIONS['AssistantAnalysisProgress1'])
DEFINITIONS['AssistantConversationRead5']['required'].append('analysis_progress')
DEFINITIONS['AssistantActivityRead1'] = obj({
    'steps': {'type': 'array', 'maxItems': 40, 'items': obj({
        'step_id': text(64), 'label': text(128),
        'state': {'enum': ['running', 'waiting', 'completed', 'failed', 'returned', 'uncertain']},
        'actor': {'enum': ['assistant', 'reviewer']},
        'started_at': nullable({'type': 'number'}),
        'finished_at': nullable({'type': 'number'}),
    })},
    'has_earlier_steps': {'type': 'boolean'},
})
DEFINITIONS['AssistantConversationRead6'] = deepcopy(DEFINITIONS['AssistantConversationRead5'])
DEFINITIONS['AssistantConversationRead6']['properties']['activity'] = (
    DEFINITIONS['AssistantActivityRead1'])
DEFINITIONS['AssistantConversationRead6']['required'].append('activity')
DEFINITIONS['AssistantBudgetRead2'] = obj({
    'configured': {'type': 'boolean'}, 'currency': {'const': 'USD'},
    'limit_cents': money, 'spent_cents': nullable(money), 'remaining_cents': nullable(money),
    'checked_at': nullable({'type': 'number'}), 'scope': {'const': 'user'},
    'period': {'const': 'cumulative'}, 'resets_at': {'type': 'null'},
})


def validate(name, value):
    errors = list(Draft202012Validator(DEFINITIONS[name]).iter_errors(value))
    if errors:
        raise DomainError('invalid_request', 400)
