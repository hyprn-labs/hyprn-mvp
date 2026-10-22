"""Explicit source transcription and reasoning inside immutable authored notes.

The evidence envelope and all historical closures remain byte-for-byte compatible.
Only content bearing the version marker is structured; legacy prose is never guessed.
This format records an author's transcription, not source authentication.
"""
import json

from .contracts import DomainError, data_json

PREFIX = 'HYPRN evidence/1\n'
FIELDS = frozenset({'excerpt', 'source_reference', 'location', 'explanation'})


def read_content(content):
    if not content.startswith(PREFIX):
        return None
    try:
        value = data_json(content[len(PREFIX):])
        if (not isinstance(value, dict) or set(value) != FIELDS
                or any(not isinstance(v, str) or not v.strip() or len(v) > 4096
                       for v in value.values())):
            raise ValueError('Invalid structured evidence')
        return value
    except (ValueError, TypeError, RecursionError) as error:
        raise DomainError('invalid_request', 400, fields=[{
            'path': '/content', 'code': 'invalid', 'message': 'Provide excerpt, source_reference, location and explanation as nonempty text.'
        }]) from error


def write_content(value):
    content = PREFIX + json.dumps(value, ensure_ascii=False, separators=(',', ':'))
    read_content(content)
    if len(content) > 4096:
        raise DomainError('invalid_request', 400)
    return content
