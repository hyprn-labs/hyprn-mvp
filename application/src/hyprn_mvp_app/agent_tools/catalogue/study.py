"""Study creation and versioned scientific framing through the public API.

Only the brief owner edits framing; study identity and lifecycle belong to the store.
"""

from ...contracts import uid
from ..projections import (
    CURSOR_SCHEMA,
    LIMIT_SCHEMA,
    brief_version_label,
    cap,
    command_id,
    encode_cursor,
    label,
    missing,
    page_arguments,
    quantity,
    read,
    ref,
    report,
    send,
    study_path,
    unit_text,
    untrusted,
)
from ..spec import SURFACES, ToolError, ToolSpec

SECTIONS = ('question', 'alternatives', 'criteria', 'assumptions', 'limits',
            'open_questions', 'deliverables')
STATE = ('GET', '/api/1/studies/{study_id}/brief')
VERSIONS = ('GET', '/api/1/studies/{study_id}/brief/versions')
SAVE_DRAFT = ('POST', '/api/1/studies/{study_id}/brief/draft')
SAVE_VERSION = ('POST', '/api/1/studies/{study_id}/brief/versions')


def _evidence_links(links):
    return [
        dict(
            ref(
                'evidence_version', link['evidence_version_id'], None, missing='call_read_evidence'
            ),
            relation=link['relation'],
            **(
                {'locator': untrusted('evidence locator', text=link['locator'])}
                if link.get('locator')
                else {}
            ),
        )
        for link in links
    ]


def _criterion(criterion, priority):
    """One study criterion at its priority (its position in the brief). A constraint keeps its
    operator, threshold and tolerances with their unit; an objective its direction and unit.
    Nothing is converted."""
    entry = dict(
        ref('criterion', criterion['criterion_id'], criterion['name'], priority=priority),
        criterion_kind=criterion['kind'],
        statement=untrusted('criterion statement', text=criterion['statement']),
    )
    units = criterion['units']
    if criterion['kind'] == 'constraint':
        entry['threshold'] = dict(
            quantity(None, criterion['threshold'], units), operator=criterion['operator']
        )
        if 'absolute_tolerance' in criterion:
            entry['absolute_tolerance'] = quantity(None, criterion['absolute_tolerance'], units)
        if 'relative_tolerance' in criterion:
            entry['relative_tolerance'] = quantity(
                None, criterion['relative_tolerance'], 'dimensionless'
            )
    else:
        entry['direction'] = criterion['direction']
        entry['unit'] = unit_text(units)
    entry['evidence'] = _evidence_links(criterion['evidence_links'])
    return entry


def content_projection(content, sections):
    """The brief content: alternatives and statements numbered, criteria at their priority;
    every item keeps its id and every text is the authors' (untrusted)."""
    projection = {}
    if 'deliverables' in sections:
        projection['deliverables'] = [
            dict(ref('deliverable', item['deliverable_id'], item['statement']),
                 kind=item['kind'])
            for item in content.get('deliverables', [])
        ]
    if 'question' in sections:
        texts = {'question': content['question'], 'scope': content['scope']}
        for key in ('original_question', 'elaboration'):
            claim = content.get(key)
            if claim is not None:
                texts[key] = claim['text']
        projection['question'] = untrusted('brief question', text=texts)
    if 'alternatives' in sections:
        projection['alternatives'] = [
            dict(
                ref('alternative', item['alternative_id'], item['name'], number=n),
                details=untrusted(
                    'alternative',
                    title='Alternative ' + str(n),
                    text={'description': item['description'], 'reason': item['reason']},
                ),
            )
            for n, item in enumerate(content['alternatives'], 1)
        ]
    if 'criteria' in sections:
        projection['criteria'] = [
            _criterion(item, n) for n, item in enumerate(content['criteria'], 1)
        ]
    for section, key, kind in (
        ('assumptions', 'assumption_id', 'brief_assumption'),
        ('limits', 'limit_id', 'brief_limit'),
    ):
        if section in sections:
            projection[section] = [
                dict(
                    ref(kind, item[key], item['statement'], number=n),
                    evidence=_evidence_links(item['evidence_links']),
                )
                for n, item in enumerate(content[section], 1)
            ]
    if 'open_questions' in sections:
        projection['open_questions'] = [
            ref('open_question', item['question_id'], item['text'], number=n)
            for n, item in enumerate(content['open_questions'], 1)
        ]
    return projection


BRIEF_PRIORITIES = [
    ('open_questions', 'open questions', 'get_study_brief with sections ["open_questions"]'),
    ('limits', 'limits', 'get_study_brief with sections ["limits"]'),
    ('assumptions', 'assumptions', 'get_study_brief with sections ["assumptions"]'),
    ('alternatives', 'alternatives', 'get_study_brief with sections ["alternatives"]'),
    ('criteria', 'criteria', 'get_study_brief with sections ["criteria"]'),
]


async def _version_by_number(ctx, number):
    """The saved version numbered ``number``: the one version before ``number + 1``."""
    params = {'limit': '1', 'before': str(number + 1)}
    body = (await read(ctx, study_path(ctx, 'brief', 'versions'), params))['data']
    if body['items'] and body['items'][0]['version_number'] == number:
        return body['items'][0]
    raise ToolError(
        'not_found',
        'There is no saved brief version with that number.',
        next_step='Call list_study_brief_versions to see the saved versions.',
    )


async def get_study_brief(arguments, ctx):
    """The brief draft (with its revision_token) or a saved version."""
    which = arguments.get('which', 'draft')
    number = arguments.get('version_number')
    if (which == 'version_number') != (number is not None):
        raise ToolError(
            'invalid_input',
            'version_number is given exactly when which is "version_number".',
            fields=({'path': 'version_number', 'problem': 'must match which'},),
            next_step='Call get_study_brief again with a matching which and version_number.',
        )
    sections = tuple(arguments.get('sections') or SECTIONS)
    projection = {'which': which}
    if which == 'version_number':
        version = await _version_by_number(ctx, number)
    else:
        state = (await read(ctx, study_path(ctx, 'brief')))['data']
        latest = state.get('latest_version')
        if which == 'draft':
            draft = state.get('draft')
            if draft is None:
                projection['draft'] = missing('no_draft')
                projection['latest_version'] = (
                    brief_version_label(latest) if latest else missing('no_saved_version')
                )
                return projection
            projection['revision_token'] = draft['revision']
            projection['updated_at'] = draft['updated_at']
            base = draft['based_on_version_id']
            if base is None:
                projection['based_on'] = missing('not_based_on_a_saved_version')
            elif latest and latest['brief_version_id'] == base:
                projection['based_on'] = brief_version_label(latest)
            else:
                projection['based_on'] = label('brief_version', base, 'Saved brief version')
            projection.update(content_projection(draft['content'], sections))
            return cap(projection, BRIEF_PRIORITIES)
        if latest is None:
            projection['brief_version'] = missing('no_saved_version')
            return projection
        version = latest
    projection['brief_version'] = dict(
        brief_version_label(version), created_at=version['created_at']
    )
    projection.update(content_projection(version['content'], sections))
    return cap(projection, BRIEF_PRIORITIES)


GET_STUDY_BRIEF = ToolSpec(
    name='get_study_brief',
    title='Read the study brief',
    description=(
        'Returns the study brief: the question and scope (with the original wording and its '
        'elaboration when recorded), numbered alternatives, the study criteria in priority '
        'order (a constraint with its operator, threshold, tolerances and unit; an objective '
        'with its direction and unit; the first objective decides first, and no weight or '
        'score is implied), numbered assumptions and limits with their evidence, and open '
        'questions, each with its id. which: "draft" (default) reads the working draft and '
        'returns its revision_token; "latest_version" reads the latest saved version; '
        '"version_number" reads the saved version numbered version_number. sections limits '
        'the answer to some parts (question, alternatives, criteria, assumptions, limits, '
        "open_questions). Saved versions never change. The text is the authors', inside "
        'untrusted_content blocks. Guidance: get_playbook("brief").'
    ),
    input_schema={
        'type': 'object',
        'additionalProperties': False,
        'properties': {
            'which': {
                'type': 'string',
                'enum': ['draft', 'latest_version', 'version_number'],
                'description': 'Which brief to read (default "draft").',
            },
            'version_number': {
                'type': 'integer',
                'minimum': 1,
                'maximum': 2147483647,
                'description': 'The saved version number, only with which "version_number".',
            },
            'sections': {
                'type': 'array',
                'items': {'type': 'string', 'enum': list(SECTIONS)},
                'minItems': 1,
                'maxItems': len(SECTIONS),
                'uniqueItems': True,
                'description': 'The parts to return (default: all).',
            },
        },
    },
    effect='read',
    stage='read_only',
    surfaces=SURFACES,
    owners=('brief',),
    outcome='none',
    activity_label='Read: study brief',
    handler=get_study_brief,
    api_operations=(STATE, VERSIONS),
)


async def list_study_brief_versions(arguments, ctx):
    """One page of saved brief versions in the owner's order (newest first)."""
    limit, position = page_arguments('list_study_brief_versions', arguments)
    params = {'limit': str(limit)}
    if position is not None:
        if not isinstance(position, int) or isinstance(position, bool) or position < 1:
            raise ToolError(
                'invalid_input',
                'The cursor no longer matches this list.',
                fields=({'path': 'cursor', 'problem': 'must be a next_cursor of this tool'},),
                next_step='Call the tool again without a cursor.',
            )
        params['before'] = str(position)
    body = (await read(ctx, study_path(ctx, 'brief', 'versions'), params))['data']
    after = body['next_cursor']
    return {
        'versions': [
            dict(
                brief_version_label(item),
                created_at=item['created_at'],
                predecessor=label(
                    'brief_version', item['predecessor_version_id'], 'Previous saved version'
                )
                if item['predecessor_version_id']
                else missing('first_version'),
            )
            for item in body['items']
        ],
        'next_cursor': None if after is None else encode_cursor('list_study_brief_versions', after),
    }


LIST_STUDY_BRIEF_VERSIONS = ToolSpec(
    name='list_study_brief_versions',
    title='List saved study brief versions',
    description=(
        'Returns one page of the saved study brief versions, newest first: number, id and when '
        'each was saved. Saved versions never change; read one with get_study_brief (which '
        '"version_number"). limit: items per page (1 to 25, default 10); cursor: the '
        'next_cursor of the previous page, passed back unchanged. '
        'Guidance: get_playbook("brief").'
    ),
    input_schema={
        'type': 'object',
        'additionalProperties': False,
        'properties': {'limit': LIMIT_SCHEMA, 'cursor': CURSOR_SCHEMA},
    },
    effect='read',
    stage='read_only',
    surfaces=SURFACES,
    owners=('brief',),
    outcome='none',
    activity_label='Read: study brief versions',
    handler=list_study_brief_versions,
    api_operations=(VERSIONS,),
)

# ---- Writes ------------------------------------------------------------------------------

_UUID = {'type': 'string', 'format': 'uuid', 'minLength': 36, 'maxLength': 36}
_NAME = {'type': 'string', 'minLength': 1, 'maxLength': 256}
_TEXT = {'type': 'string', 'maxLength': 4096}
_STATEMENT = {'type': 'string', 'minLength': 1, 'maxLength': 4096}
_RELATION = {'type': 'string', 'enum': ['supports', 'challenges', 'context']}


def _links(locator):
    properties = {'evidence_version_id': _UUID, 'relation': _RELATION}
    if locator:
        properties['locator'] = {'type': 'string', 'maxLength': 1024}
    return {
        'type': 'array',
        'maxItems': 64,
        'items': {
            'type': 'object',
            'additionalProperties': False,
            'required': ['evidence_version_id', 'relation'],
            'properties': properties,
        },
        'description': 'Evidence versions (from list_evidence) with their relation.',
    }


def _items(maximum, required, properties, description):
    return {
        'type': 'array',
        'maxItems': maximum,
        'items': {
            'type': 'object',
            'additionalProperties': False,
            'required': list(required),
            'properties': properties,
        },
        'description': description,
    }


_CLAIM = {
    'type': ['object', 'null'],
    'additionalProperties': False,
    'required': ['text', 'attribution'],
    'properties': {
        'text': _TEXT,
        'attribution': {
            'type': 'object',
            'additionalProperties': False,
            'required': ['kind', 'label'],
            'properties': {
                'kind': {'type': 'string', 'enum': ['human', 'agent', 'unknown']},
                'label': {'type': ['string', 'null'], 'maxLength': 256},
            },
        },
    },
}
# Each list item keeps its id when the agent passes one (from get_study_brief); an item
# without an id is new and receives one here, so an agent never invents an identity.
ITEM_IDS = {
    'alternatives': 'alternative_id',
    'criteria': 'criterion_id',
    'assumptions': 'assumption_id',
    'limits': 'limit_id',
    'open_questions': 'question_id',
    'deliverables': 'deliverable_id',
}
CONTENT_SCHEMA = {
    'type': 'object',
    'additionalProperties': False,
    'minProperties': 1,
    'description': (
        'The sections to change. A section given replaces that section whole; a section '
        'left out stays as it is.'
    ),
    'properties': {
        'question': _TEXT,
        'deliverables': _items(
            32, ('kind', 'statement'),
            {'deliverable_id': _UUID,
             'kind': {'enum': ['assessment', 'interactive_exploration']},
             'statement': _STATEMENT},
            'Explicit requested outcomes. Interactive exploration requires checked joint '
            'coverage before the answer can claim completion.',
        ),
        'scope': _TEXT,
        'original_question': _CLAIM,
        'elaboration': _CLAIM,
        'alternatives': _items(
            32,
            ('name',),
            {
                'alternative_id': _UUID,
                'name': _NAME,
                'description': _TEXT,
                'reason': _TEXT,
            },
            'The design alternatives the study compares, in order.',
        ),
        'criteria': _items(
            64,
            ('kind', 'name', 'units'),
            {
                'criterion_id': _UUID,
                'kind': {'type': 'string', 'enum': ['constraint', 'objective']},
                'name': _NAME,
                'statement': _TEXT,
                'operator': {'type': 'string', 'enum': ['lt', 'le', 'eq', 'ge', 'gt']},
                'threshold': {'type': 'number'},
                'units': {'type': 'string', 'maxLength': 64},
                'absolute_tolerance': {'type': 'number', 'minimum': 0},
                'relative_tolerance': {'type': 'number', 'minimum': 0},
                'direction': {'type': 'string', 'enum': ['minimize', 'maximize']},
                'evidence_links': _links(True),
            },
            'Study criteria in priority order: a constraint needs operator, threshold and '
            'units (tolerances optional); an objective needs direction and units. The first '
            'objective decides first; no weight or score is implied. units is the exact unit '
            'text, empty for dimensionless.',
        ),
        'assumptions': _items(
            256,
            ('statement',),
            {'assumption_id': _UUID, 'statement': _STATEMENT, 'evidence_links': _links(True)},
            'Study-wide assumptions.',
        ),
        'limits': _items(
            256,
            ('statement',),
            {'limit_id': _UUID, 'statement': _STATEMENT, 'evidence_links': _links(False)},
            'What the study cannot conclude.',
        ),
        'open_questions': _items(
            64,
            ('text',),
            {'question_id': _UUID, 'text': _STATEMENT},
            'Questions the study has not answered yet.',
        ),
    },
}
EMPTY_CONTENT = dict(
    schema_version='2',
    deliverables=[],
    question='',
    original_question=None,
    elaboration=None,
    scope='',
    alternatives=[],
    criteria=[],
    assumptions=[],
    limits=[],
    open_questions=[],
)
LIST_DEFAULTS = {
    'alternatives': {'description': '', 'reason': ''},
    'criteria': {'statement': '', 'evidence_links': []},
    'assumptions': {'evidence_links': []},
    'limits': {'evidence_links': []},
}


def _merged(current, changes):
    """The current draft content with the given sections replaced; new items get an id and the
    optional texts and link lists of an item default to empty (never a number)."""
    content = dict(current)
    content.update(schema_version='2', deliverables=current.get('deliverables', []))
    for key, value in changes.items():
        if key in ITEM_IDS:
            id_key = ITEM_IDS[key]
            value = [
                dict(
                    LIST_DEFAULTS.get(key, {}),
                    **item,
                    **({} if id_key in item else {id_key: uid()}),
                )
                for item in value
            ]
        content[key] = value
    return content


async def update_study_brief(arguments, ctx):
    """Change the brief draft section by section under the draft revision the agent read."""
    expected = arguments['expected_revision']
    state = (await read(ctx, study_path(ctx, 'brief')))['data']
    draft = state.get('draft')
    current = draft['revision'] if draft else None
    if current != expected:
        raise ToolError(
            'conflict',
            'The brief draft changed since you read it; nothing was written.',
            fields=({'path': 'expected_revision', 'problem': 'is not the current draft revision'},),
            next_step='Call get_study_brief, apply your change to what it returns and pass its '
            'revision_token as expected_revision.',
        )
    content = _merged(draft['content'] if draft else EMPTY_CONTENT, arguments['content'])
    body = {'command_id': command_id(ctx), 'expected_revision': expected, 'content': content}
    saved = (
        await send(
            ctx,
            'POST',
            study_path(ctx, 'brief', 'draft'),
            body,
            tool='update_study_brief',
            conflict_step='Call get_study_brief again and reapply your change.',
        )
    )['data']
    report(ctx, 'brief_draft', saved['study_id'], version_id=saved['revision'])
    projection = {
        'revision_token': saved['revision'],
        'updated_at': saved['updated_at'],
        'changed_sections': sorted(arguments['content']),
    }
    projection.update(content_projection(saved['content'], SECTIONS))
    return cap(projection, BRIEF_PRIORITIES)


UPDATE_STUDY_BRIEF = ToolSpec(
    name='update_study_brief',
    title='Change the study brief draft',
    description=(
        'Changes the study brief draft: the question, scope, original wording and '
        'elaboration, alternatives, criteria (in priority order), assumptions, limits and '
        'open questions. expected_revision: the revision_token of your last get_study_brief '
        '(null when the study has no draft yet). content: only the sections to change; a '
        'section given replaces that section whole (keep the ids of items you keep, omit the '
        'id of a new item and one is assigned), a section left out stays as it is. Returns '
        'the new revision_token and the whole draft with every item id. Saved versions never '
        'change; save one with save_study_brief_version. Guidance: get_playbook("brief").'
    ),
    input_schema={
        'type': 'object',
        'additionalProperties': False,
        'required': ['expected_revision', 'content'],
        'properties': {
            'expected_revision': {
                'type': ['string', 'null'],
                'maxLength': 36,
                'description': 'The revision_token of the draft you read, or null for none.',
            },
            'content': CONTENT_SCHEMA,
        },
    },
    effect='draft',
    stage='authoring',
    surfaces=SURFACES,
    owners=('brief',),
    outcome='receipt:brief_draft',
    activity_label='Changed: study brief draft',
    handler=update_study_brief,
    api_operations=(STATE, SAVE_DRAFT),
    attribution_kind='brief_draft',
)


async def save_study_brief_version(arguments, ctx):
    """Freeze the current draft as the next numbered version."""
    body = {'command_id': command_id(ctx), 'expected_revision': arguments['expected_revision']}
    saved = (
        await send(
            ctx,
            'POST',
            study_path(ctx, 'brief', 'versions'),
            body,
            tool='save_study_brief_version',
            conflict_step='Call get_study_brief, check the draft and save again with its '
            'revision_token.',
        )
    )['data']
    version, draft = saved['version'], saved['draft']
    report(
        ctx,
        'brief_version',
        version['study_id'],
        version_id=version['brief_version_id'],
        number=version['version_number'],
    )
    return {
        'brief_version': dict(brief_version_label(version), created_at=version['created_at']),
        'draft': {'revision_token': draft['revision'], 'based_on': brief_version_label(version)},
    }


SAVE_STUDY_BRIEF_VERSION = ToolSpec(
    name='save_study_brief_version',
    title='Save a study brief version',
    description=(
        'Saves the current study brief draft exactly as the next numbered version, which '
        'never changes afterwards; the draft continues from it with a new revision_token. '
        'expected_revision: the revision_token of the draft you checked (from get_study_brief '
        'or update_study_brief). Returns the version number and id and the continuing '
        'draft. Guidance: get_playbook("brief").'
    ),
    input_schema={
        'type': 'object',
        'additionalProperties': False,
        'required': ['expected_revision'],
        'properties': {
            'expected_revision': {
                'type': 'string',
                'minLength': 36,
                'maxLength': 36,
                'description': 'The revision_token of the draft to save.',
            }
        },
    },
    effect='record',
    stage='authoring',
    surfaces=SURFACES,
    owners=('brief',),
    outcome='receipt:brief_version',
    activity_label='Saved: study brief version',
    handler=save_study_brief_version,
    api_operations=(SAVE_VERSION,),
    attribution_kind='brief_version',
)

# ---- Study creation ------------------------------------------------------------------

NEW_STUDY = ('POST', '/api/1/studies')
STUDY_NAME = {'type': 'string', 'minLength': 1, 'maxLength': 200, 'pattern': r'\S'}


async def create_study(arguments, ctx):
    """Create a study owned by the delegating user; the session's delegation does not widen."""
    body = {'command_id': command_id(ctx), 'name': arguments['name']}
    study = (
        await send(
            ctx,
            'POST',
            NEW_STUDY[1],
            body,
            tool='create_study',
            conflict_step='Call create_study again with a new call.',
        )
    )['data']
    report(ctx, 'study', study['study_id'], name=study['name'])
    return {
        'study': ref('study', study['study_id'], study['name']),
        'owner': 'the user you act for',
        'access': (
            'This session stays scoped to the current study. Working in the new study needs '
            'access its Owner gives: locally, a study token minted with the command line.'
        ),
    }


CREATE_STUDY = ToolSpec(
    name='create_study',
    title='Create a study',
    description=(
        'Creates a new, empty study owned by the user you act for, under the name given (a '
        'reviewer-readable name, 1 to 200 characters). Use it only when the user asks for a '
        'separate study. This session stays scoped to the current study: you cannot read or '
        'change the new one until its Owner gives an agent access to it (locally, a study '
        'token minted with the command line). Returns the new study id and name. '
        'Guidance: get_playbook("workflow").'
    ),
    input_schema={
        'type': 'object',
        'additionalProperties': False,
        'required': ['name'],
        'properties': {'name': dict(STUDY_NAME, description='The name of the new study.')},
    },
    effect='record',
    stage='authoring',
    surfaces=SURFACES,
    owners=('store',),
    outcome='receipt:study_create',
    activity_label='Created: study',
    handler=create_study,
    api_operations=(NEW_STUDY,),
    attribution_kind='study',
)

TOOLS = (
    GET_STUDY_BRIEF,
    LIST_STUDY_BRIEF_VERSIONS,
    UPDATE_STUDY_BRIEF,
    SAVE_STUDY_BRIEF_VERSION,
    CREATE_STUDY,
)
