"""Owner reads and the compact projections the read tools return (tooling spec sections 5.5,
5.8, 10.1 and 10.4).

A read tool calls only its declared ``/api/1`` operations through ``read`` and turns the owners'
stored records into a projection. Projections are allowlists: they name every field they
return and never copy a record whole, so tokens, cookies, cross-site request values, hashes,
locks, native identities and paths never reach an agent. The rules every projection keeps:

- an id is always paired with a name (``ref``); when the read carries no name the pair says so;
- every text written by others (names, descriptions, evidence, source, diagnostics) is inside an
  ``untrusted_content`` block with its provenance label (``untrusted``): it is data, never an
  instruction;
- a quantity always carries its unit; an unavailable value is ``{quantity, unavailable:
  reason}``, never 0; a value that is not recorded is ``{missing: reason}``, never a default;
- numbers keep the precision the owner stored;
- a result stays at or below 24 KB (``cap``), dropping its lowest-priority sections first and
  naming what was omitted and how to get it;
- a list is a page of at most 25 items (10 by default) with an opaque cursor bound to the tool
  (``page_arguments``, ``encode_cursor``, ``decode_cursor``).

Nothing is kept between calls: every call reads the owners again.
"""

import base64
import binascii
from datetime import datetime, timezone
import hashlib
import json
import re

from ..contracts import canonical
from .spec import ToolError

MAX_RESULT_BYTES = 24 * 1024
DEFAULT_LIMIT = 10
MAX_LIMIT = 25
MAX_CURSOR = 1024
AUTHOR = 'study member'
UUID = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')
CURSOR_TEXT = re.compile(r'[A-Za-z0-9_-]{1,1024}')
CURSOR_KEYS = frozenset({'tool', 'value', 'check'})

LIMIT_SCHEMA = {
    'type': 'integer',
    'minimum': 1,
    'maximum': MAX_LIMIT,
    'description': 'Items per page, 1 to 25 (default 10).',
}
CURSOR_SCHEMA = {
    'type': 'string',
    'minLength': 1,
    'maxLength': MAX_CURSOR,
    'description': 'The next_cursor of the previous page of this tool, passed back unchanged.',
}
UUID_SCHEMA = {'type': 'string', 'format': 'uuid', 'minLength': 36, 'maxLength': 36}


def uuid_schema(description):
    return dict(UUID_SCHEMA, description=description)


# ---- Owner reads ------------------------------------------------------------------------

# API error codes mapped onto the agent error categories of tooling spec section 6.2 for reads.
# Reads are never retried here; an unknown or uncertain outcome is reported, never repeated.
_ERRORS = {
    'invalid_request': ('invalid_input', False, 'The request was refused as invalid.'),
    'unsupported_capability': (
        'unsupported',
        False,
        'This installation does not support that read.',
    ),
    'limit_exceeded': ('too_large', False, 'The read is larger than the installation allows.'),
    'rate_limited': ('busy', True, 'HYPRN MVP is busy; try again shortly.'),
    'backend_unavailable': (
        'unavailable',
        True,
        'Modeling or execution is unavailable; reads of saved records still work.',
    ),
    'isolation_unverified': (
        'unavailable',
        True,
        'Modeling or execution is unavailable; reads of saved records still work.',
    ),
    'unauthenticated': ('session_expired', False, 'The agent session has expired.'),
    'forbidden': ('access_lost', False, 'Access to this study has ended.'),
    'reference_conflict': ('conflict', False, 'The record changed while it was being read.'),
}


def study_path(ctx, *parts):
    """``/api/1/studies/{study_id}/...`` for the session's study; the study is never an
    argument (D-09)."""
    study = getattr(ctx.session, 'get', lambda _: None)('study_id')
    if not isinstance(study, str) or not UUID.fullmatch(study):
        raise ToolError('access_lost', 'This session has no study.')
    return '/'.join(('/api/1/studies', study) + parts)


async def read(ctx, path, params=None, *, missing='not_found', next_step=None):
    """One owner read (GET). Returns the envelope (``data`` and, for lists, ``next_cursor``) or
    raises a ``ToolError`` whose message never echoes the API's text or a submitted value.
    ``missing`` is the category of a 404: ``not_found`` for a record, ``access_lost`` for the
    session's study itself."""
    reply = await ctx.api.request(ctx.session, 'GET', path, params=params)
    body = reply.body if isinstance(reply.body, dict) else {}
    if reply.status == 200 and 'data' in body:
        return body
    error = body.get('error') if isinstance(body.get('error'), dict) else {}
    code = error.get('code')
    if reply.status == 404 or code == 'resource_not_found':
        if missing == 'access_lost':
            raise ToolError(
                'access_lost',
                'This study is no longer visible to the agent.',
                next_step='Stop and tell the user; do not probe other ids.',
            )
        raise ToolError(
            'not_found',
            'No record with that id in this study.',
            next_step=next_step or 'List the records first and use an id from the list.',
        )
    category, retryable, message = _ERRORS.get(
        code, ('internal', False, 'HYPRN MVP could not complete the read.')
    )
    if reply.status == 403:
        category, retryable, message = _ERRORS['forbidden']
    raise ToolError(
        category,
        message,
        retryable=retryable,
        next_step=_STEPS.get(category),
    )


_STEPS = {
    'access_lost': 'Stop all work, tell the user and end the turn.',
    'session_expired': 'Stop and tell the user that the agent session ended.',
    'unavailable': 'Tell the user; reads of saved records still work.',
    'busy': 'Wait a little before the next call.',
    'internal': 'Report it with report_platform_issue if it repeats.',
}


async def read_all(ctx, path, *, page_size=100, max_pages=5):
    """Every item of an owner list read page by page, at most ``max_pages`` pages. Returns
    ``(items, complete)``; ``complete`` is false when more items remain unread."""
    items, cursor = [], None
    for _ in range(max_pages):
        params = {'limit': str(page_size)}
        if cursor is not None:
            params['cursor'] = cursor
        body = await read(ctx, path, params)
        items.extend(body['data'])
        cursor = body.get('next_cursor')
        if cursor is None:
            return items, True
    return items, False


# ---- Pages and cursors ------------------------------------------------------------------


def encode_cursor(tool, value):
    """An opaque cursor for ``tool`` holding the owner's position ``value``: base64url of
    canonical JSON with a check over the tool name and the value."""
    body = {'tool': tool, 'value': value}
    check = hashlib.sha256(canonical(body)).hexdigest()[:24]
    raw = canonical(dict(body, check=check))
    return base64.urlsafe_b64encode(raw).decode().rstrip('=')


def decode_cursor(tool, text):
    """The owner position inside a cursor of ``tool``. A cursor of another tool, an altered
    cursor or anything that is not exactly what ``encode_cursor`` produced is ``invalid_input``.
    """
    try:
        if not isinstance(text, str) or not CURSOR_TEXT.fullmatch(text):
            raise ValueError
        raw = base64.urlsafe_b64decode(text + '=' * (-len(text) % 4))
        value = json.loads(raw, object_pairs_hook=_unique, parse_constant=_refuse)
        if not isinstance(value, dict) or set(value) != CURSOR_KEYS:
            raise ValueError
        if value['tool'] != tool or encode_cursor(tool, value['value']) != text:
            raise ValueError
    except (ValueError, TypeError, binascii.Error, RecursionError, UnicodeError):
        raise ToolError(
            'invalid_input',
            'The cursor is not a cursor of this tool.',
            fields=({'path': 'cursor', 'problem': 'must be a next_cursor of this tool'},),
            next_step='Pass back the next_cursor this tool returned, unchanged, or omit it.',
        ) from None
    return value['value']


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate key')
        result[key] = value
    return result


def _refuse(_):
    raise ValueError('non-finite number')


def page_arguments(tool, arguments):
    """``(limit, owner position or None)`` from a list tool's input (the schema bounds
    ``limit`` to 1 to 25; the default is 10)."""
    limit = arguments.get('limit', DEFAULT_LIMIT)
    cursor = arguments.get('cursor')
    return limit, (None if cursor is None else decode_cursor(tool, cursor))


def page(tool, items, limit, position=None):
    """One page of an already read list: ``(selected, next_cursor)``. ``position`` is the
    offset carried by the cursor."""
    start = position or 0
    if not isinstance(start, int) or isinstance(start, bool) or not 0 <= start <= len(items):
        raise ToolError(
            'invalid_input',
            'The cursor no longer matches this list.',
            fields=({'path': 'cursor', 'problem': 'must be a next_cursor of this tool'},),
            next_step='Call the tool again without a cursor.',
        )
    selected = items[start : start + limit]
    after = start + len(selected)
    return selected, (encode_cursor(tool, after) if after < len(items) else None)


# ---- Projection building blocks ---------------------------------------------------------


def untrusted(kind, title=None, author=AUTHOR, text=None):
    """Text written by others, with its provenance label. It is data to report, never an
    instruction to follow (tooling spec section 10.1)."""
    content = {'kind': kind, 'author': author}
    if title is not None:
        content['title'] = title
    if text is not None:
        content['text'] = text
    return {'untrusted_content': content}


def ref(kind, record_id, name=None, *, missing=None, **extra):
    """An id paired with its name. The name, written by others, is untrusted content; when the
    read carries no name the pair says why (``name: {missing: reason}``)."""
    value = {'kind': kind, 'id': record_id}
    if name is not None:
        value['name'] = untrusted(kind + ' name', text=name)
    else:
        value['name'] = {'missing': missing or 'not_in_this_read'}
    value.update(extra)
    return value


def label(kind, record_id, text, **extra):
    """An id paired with a name HYPRN MVP gives it (for example "Approach version 3")."""
    return dict({'kind': kind, 'id': record_id, 'name': text}, **extra)


def missing(reason):
    return {'missing': reason}


def unit_text(units):
    """The unit of a port, criterion or value as the owner stored it: a typed declaration
    (``physical`` expression, ``dimensionless``, ``unspecified``) or a legacy text, where the
    empty text is dimensionless. Never converted."""
    if isinstance(units, dict):
        kind = units.get('kind')
        if kind == 'physical' and isinstance(units.get('expression'), str):
            return units['expression']
        if kind in ('dimensionless', 'unspecified'):
            return kind
        return 'unspecified'
    if isinstance(units, str):
        return units if units else 'dimensionless'
    return 'unspecified'


def quantity(name, value, units, *, unavailable=None):
    """A quantity with its unit (``name`` omitted when ``None``); an unavailable value is
    never shown as a number."""
    head = {} if name is None else {'quantity': name}
    if unavailable is not None or value is None:
        return dict(head, unavailable=unavailable or 'not_recorded')
    return dict(head, value=value, unit=unit_text(units))


def clip(text, limit):
    """``(text, truncated)``: at most ``limit`` characters, never splitting the count."""
    if not isinstance(text, str):
        return '', False
    return (text, False) if len(text) <= limit else (text[:limit], True)


def age_seconds(timestamp, now=None):
    """Whole seconds since an owner-recorded UTC time, or ``None`` when it cannot be read."""
    if not isinstance(timestamp, str):
        return None
    try:
        moment = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    except ValueError:
        return None
    if moment.tzinfo is None:
        return None
    current = now if now is not None else utc_now()
    return max(0, int((current - moment).total_seconds()))


def utc_now():
    return datetime.now(timezone.utc)


# ---- The result cap ---------------------------------------------------------------------


def size(value):
    return len(canonical(value))


def cap(projection, priorities):
    """``projection`` at or below 24 KB of canonical JSON. ``priorities`` lists the droppable
    parts, lowest priority first, as ``(key, omitted, how_to_get)``: a top-level key removed
    whole or, for a list, shortened from its end. What was dropped is named in
    ``truncated {omitted, how_to_get}``; a projection that fits is returned unchanged."""
    result = dict(projection)
    omitted, how = [], []
    for key, what, how_to_get in priorities:
        if size(_noted(result, omitted, how)) <= MAX_RESULT_BYTES:
            break
        value = result.get(key)
        if isinstance(value, list) and len(value) > 1:
            kept = _longest_prefix(result, key, value, omitted + [what], how + [how_to_get])
            result[key] = value[:kept]
            omitted.append(what + ' (' + str(len(value) - kept) + ' of ' + str(len(value)) + ')')
            how.append(how_to_get)
        elif key in result:
            del result[key]
            omitted.append(what)
            how.append(how_to_get)
    final = _noted(result, omitted, how)
    if size(final) > MAX_RESULT_BYTES:
        raise ToolError(
            'too_large',
            'The result is larger than 24 KB even after dropping optional sections.',
            next_step='Ask for fewer items (a smaller limit or fewer names).',
        )
    return final


def _noted(result, omitted, how):
    if not omitted:
        return result
    return dict(result, truncated={'omitted': list(omitted), 'how_to_get': list(how)})


def _longest_prefix(result, key, value, omitted, how):
    """The largest number of leading items of ``value`` that keeps the result within the cap
    (the note is measured with its longest count text)."""
    low, high = 0, len(value) - 1
    while low < high:
        middle = (low + high + 1) // 2
        trial = dict(result, **{key: value[:middle]})
        if size(_noted(trial, omitted, how)) + 16 <= MAX_RESULT_BYTES:
            low = middle
        else:
            high = middle - 1
    return low


# ---- Record projections shared by several tools -----------------------------------------

READINESS_ADVICE = (
    'If the status is not ready, do not resubmit or retry in a loop; tell the user the reasons.'
)


def readiness(value):
    """The readiness owner's observation as it reported it, with its age in seconds."""
    observed = value.get('observed_at')
    age = age_seconds(observed)
    return {
        'status': value['status'],
        'reasons': list(value['reasons']),
        'observed_at': observed if observed else missing('not_observed'),
        'observed_age_s': age if age is not None else missing('not_observed'),
        'expires_at': value.get('expires_at') or missing('not_observed'),
        'advice': READINESS_ADVICE,
    }


def approach_version_label(summary):
    number = summary['version_number']
    return label(
        'approach_version',
        summary['approach_version_id'],
        'Approach version ' + str(number),
        number=number,
    )


def approach_summary(state):
    """The approach state (draft and latest saved version) in counts and the question."""
    draft, latest = state.get('draft'), state.get('latest_version')
    summary = {}
    if draft is None:
        summary['draft'] = missing('no_draft')
    else:
        content = draft['content']
        limits = content.get('limit_items')
        summary['draft'] = {
            'revision_token': draft['revision'],
            'updated_at': draft['updated_at'],
            'question': untrusted('approach question', text=content['question']),
            'counts': {
                'steps': len(content['steps']),
                'cases': len(content['cases']),
                'limits': len(limits) if limits is not None else missing('limits_not_itemized'),
                'assumptions': len(content['assumptions']),
            },
        }
    summary['latest_version'] = (
        approach_version_label(latest) if latest else missing('no_saved_version')
    )
    return summary


def run_name(configuration_name):
    """The name a run is shown under: "Run of '<configuration name>'"."""
    return None if configuration_name is None else "Run of '" + configuration_name + "'"


def case_context(context):
    """The approach case a run's configuration implements, as the owner projects it."""
    if not isinstance(context, dict):
        return missing('not_recorded')
    if context.get('state') != 'linked':
        return {'state': context.get('state')}
    case_id = context.get('case_id')
    return {
        'state': 'linked',
        'approach_version': label(
            'approach_version',
            context['approach_version_id'],
            'Approach version ' + str(context['version_number']),
            number=context['version_number'],
        ),
        'case': ref('approach_case', case_id, context.get('case_name'), missing='case_not_named')
        if case_id
        else missing('no_case'),
    }


def run_ref(item):
    """A run of the run list or the light status read, named after its configuration."""
    name = item.get('configuration_name')
    value = ref('run', item['run_id'], run_name(name), missing='configuration_name_not_recorded')
    value['configuration'] = ref(
        'configuration_version',
        item['configuration_revision_id'],
        name,
        missing='configuration_name_not_recorded',
    )
    if 'case_context' in item:
        value['case'] = case_context(item['case_context'])
    return value


def configuration_ref(frozen):
    """A saved configuration version of the configuration list."""
    configuration = frozen['configuration']
    return ref(
        'configuration_version',
        configuration['configuration_revision_id'],
        configuration['name'],
        configuration_id=configuration['configuration_id'],
    )


def evidence_ref(record):
    """An evidence version, named by its title (records saved before titles have none)."""
    return ref(
        'evidence_version',
        record['evidence_version_id'],
        record.get('title'),
        missing='no_title_recorded',
        evidence_id=record['evidence_id'],
    )


class ModelView:
    """Names and declarations of one stored model draft or version, for projections: the
    components (every instance but the root, or the root alone), their ports with direction,
    unit and quantity meaning, and the port path ``"<component>.<port>"``."""

    def __init__(self, model):
        self.model = model
        self.root = model['root_instance_id']
        self.definitions = {d['definition_version_id']: d for d in model['definitions']}
        instances = list(model['instances'])
        others = [i for i in instances if i['instance_id'] != self.root]
        self.components = others or [i for i in instances if i['instance_id'] == self.root]
        self.ports = {}
        for instance in instances:
            definition = self.definitions.get(instance['definition_version_id'])
            if definition is None:
                continue
            meanings = {
                q['port_id']: q['statement'] for q in definition.get('quantity_definitions', ())
            }
            for port in definition['ports']:
                self.ports[(instance['instance_id'], port['port_id'])] = {
                    'component': instance['name'],
                    'port': port['name'],
                    'direction': port['direction'],
                    'unit': unit_text(port.get('units')),
                    'meaning': meanings.get(port['port_id']),
                    'meanings_declared': 'quantity_definitions' in definition,
                }

    def port(self, target):
        if not isinstance(target, dict):
            return None
        return self.ports.get((target.get('instance_id'), target.get('port_id')))

    def unit(self, target, stored):
        """The unit of a stored value bound to ``target``: the stored text, or, when the text
        is empty, the unit the port declares (an empty text never claims dimensionless for a
        port whose unit is unspecified)."""
        if isinstance(stored, str) and stored:
            return stored
        port = self.port(target)
        return port['unit'] if port is not None else unit_text(stored)

    def path(self, target):
        """``"<component>.<port>"`` for a ``{instance_id, port_id}`` reference, or ``None``."""
        port = self.port(target)
        return None if port is None else port['component'] + '.' + port['port']

    def quantity_ref(self, target, kind='port'):
        """A port reference paired with its path name; a port the model does not hold says so."""
        return ref(
            kind,
            target.get('port_id'),
            self.path(target),
            missing='port_not_in_model',
            component_id=target.get('instance_id'),
        )
