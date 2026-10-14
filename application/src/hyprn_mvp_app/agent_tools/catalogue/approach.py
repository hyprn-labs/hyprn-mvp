"""Question and approach: the read tools (tooling spec section 4.3). The approach owner
(``approach``) serves the draft, the saved versions and their usage; these tools only read."""

from ...contracts import canonical
from ..projections import (
    CURSOR_SCHEMA,
    LIMIT_SCHEMA,
    approach_version_label,
    cap,
    encode_cursor,
    label,
    missing,
    page_arguments,
    read,
    ref,
    study_path,
    untrusted,
    uuid_schema,
)
from ..spec import SURFACES, ToolError, ToolSpec

SECTIONS = ('question', 'steps', 'cases', 'limits', 'assumptions', 'models', 'basis')
VERSION_PAGE = 100
MAX_VERSION_PAGES = 20
STATE = ('GET', '/api/1/studies/{study_id}/approach')
VERSIONS = ('GET', '/api/1/studies/{study_id}/approach/versions')
VERSION = ('GET', '/api/1/studies/{study_id}/approach/versions/{version_id}')
USAGE = ('GET', '/api/1/studies/{study_id}/approach/versions/{version_id}/usage')


def _api_cursor(value):
    return canonical(value).decode()


async def _version_by_number(ctx, number):
    """The saved version numbered ``number``, found through the owner's version list."""
    cursor = None
    for _ in range(MAX_VERSION_PAGES):
        params = {'limit': str(VERSION_PAGE)}
        if cursor is not None:
            params['cursor'] = _api_cursor(cursor)
        body = (await read(ctx, study_path(ctx, 'approach', 'versions'), params))['data']
        for item in body['items']:
            if item['version_number'] == number:
                return item
        cursor = body['next_cursor']
        if cursor is None:
            break
    raise ToolError(
        'not_found',
        'There is no saved approach version with that number.',
        next_step='Call list_approach_versions to see the saved versions.',
    )


async def _saved(ctx, version_id):
    path = study_path(ctx, 'approach', 'versions', version_id)
    return (await read(ctx, path, next_step='Call list_approach_versions.'))['data']['version']


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


def content_projection(content, sections):
    """The approach content, numbered: "Step 2", "Case 1", "Limit 3"; every item keeps its id
    and its title, and every text is the authors' (untrusted)."""
    bindings = {b['binding_id']: b for b in content['model_bindings']}
    numbers = {s['step_id']: n for n, s in enumerate(content['steps'], 1)}
    projection = {}
    if 'question' in sections:
        texts = {
            'question': content['question'],
            'scope': content['scope'],
            'limitations': content['limitations'],
            'open_questions': content['open_questions'],
        }
        for key in ('original_question', 'elaboration'):
            claim = content.get(key)
            if claim is not None:
                texts[key] = claim['text']
        projection['question'] = untrusted('approach question', text=texts)
    if 'steps' in sections:
        projection['steps'] = [
            dict(
                ref('approach_step', step['step_id'], step['title'], number=n),
                implementation_state=step['implementation_state'],
                linked_elements=len(step['implementation_refs']),
                depends_on=['Step ' + str(numbers[s]) for s in _depends(step) if s in numbers],
                details=untrusted(
                    'approach step',
                    title='Step ' + str(n),
                    text={
                        'purpose': step['purpose'],
                        'rationale': step['rationale'],
                        'remaining_work': step['remaining_work'],
                        'transformation': step['intent'].get('transformation', ''),
                        'inputs': step['intent'].get('inputs', ''),
                        'outputs': step['intent'].get('outputs', ''),
                    },
                ),
                evidence=_evidence_links(step['evidence_links']),
            )
            for n, step in enumerate(content['steps'], 1)
        ]
    if 'cases' in sections:
        projection['cases'] = [
            dict(
                ref('approach_case', case['case_id'], case['title'], number=n),
                details=untrusted(
                    'approach case',
                    title='Case ' + str(n),
                    text={'question': case['question'], 'rationale': case['rationale']},
                ),
                model=_binding(bindings.get(case['binding_id']))
                if case['binding_id']
                else missing('no_model_bound'),
                evidence=_evidence_links(case['evidence_links']),
            )
            for n, case in enumerate(content['cases'], 1)
        ]
    if 'limits' in sections:
        if 'limit_items' in content:
            projection['limits'] = [
                dict(
                    ref('approach_limit', item['limit_id'], item['statement'], number=n),
                    evidence=_evidence_links(item['evidence_links']),
                )
                for n, item in enumerate(content['limit_items'], 1)
            ]
        else:
            projection['limits'] = missing('limits_not_itemized_in_this_version')
    if 'assumptions' in sections:
        projection['assumptions'] = [
            dict(
                ref('approach_assumption', item['assumption_id'], item['statement'], number=n),
                role=item['role'],
                evidence=_evidence_links(item['evidence_links']),
            )
            for n, item in enumerate(content['assumptions'], 1)
        ]
    if 'models' in sections:
        projection['models'] = [_binding(b) for b in content['model_bindings']]
    if 'basis' in sections:
        projection['basis'] = [_basis(item) for item in content['basis_refs']]
    return projection


def _depends(step):
    return step['intent'].get('depends_on_step_ids', ())


def _binding(binding):
    if binding is None:
        return missing('binding_not_in_this_approach')
    return {
        'model': ref('model', binding['model_id'], None, missing='call_list_models'),
        'model_version': ref(
            'model_version', binding['model_revision_id'], None, missing='call_get_model'
        ),
    }


def _basis(item):
    if item['kind'] == 'run':
        target = ref('run', item['run_id'], None, missing='call_get_run_results')
    else:
        target = ref(
            'configuration_version',
            item['configuration_revision_id'],
            None,
            missing='call_get_configuration',
        )
    return dict(
        target,
        relation=item['relation'],
        reason=untrusted('approach basis reason', text=item['reason']),
    )


APPROACH_PRIORITIES = [
    ('basis', 'basis references', 'get_approach with sections ["basis"]'),
    ('assumptions', 'assumptions', 'get_approach with sections ["assumptions"]'),
    ('limits', 'limits', 'get_approach with sections ["limits"]'),
    ('models', 'model bindings', 'get_approach with sections ["models"]'),
    ('cases', 'cases', 'get_approach with sections ["cases"]'),
    ('steps', 'steps', 'get_approach with sections ["steps"]'),
]


async def get_approach(arguments, ctx):
    """The approach draft (with its revision_token) or a saved version, numbered."""
    which = arguments.get('which', 'draft')
    number = arguments.get('version_number')
    if (which == 'version_number') != (number is not None):
        raise ToolError(
            'invalid_input',
            'version_number is given exactly when which is "version_number".',
            fields=({'path': 'version_number', 'problem': 'must match which'},),
            next_step='Call get_approach again with a matching which and version_number.',
        )
    sections = tuple(arguments.get('sections') or SECTIONS)
    state = (await read(ctx, study_path(ctx, 'approach')))['data']
    projection = {'which': which}
    if which == 'draft':
        draft = state.get('draft')
        if draft is None:
            projection['draft'] = missing('no_draft')
            projection['latest_version'] = (
                approach_version_label(state['latest_version'])
                if state.get('latest_version')
                else missing('no_saved_version')
            )
            return projection
        projection['revision_token'] = draft['revision']
        projection['updated_at'] = draft['updated_at']
        latest = state.get('latest_version')
        base = draft['base_version_id']
        if base is None:
            projection['based_on'] = missing('not_based_on_a_saved_version')
        elif latest and latest['approach_version_id'] == base:
            projection['based_on'] = approach_version_label(latest)
        else:
            projection['based_on'] = label('approach_version', base, 'Saved approach version')
        content = draft['content']
    else:
        if which == 'latest_version':
            summary = state.get('latest_version')
            if summary is None:
                projection['approach_version'] = missing('no_saved_version')
                return projection
        else:
            summary = await _version_by_number(ctx, number)
        version = await _saved(ctx, summary['approach_version_id'])
        projection['approach_version'] = dict(
            approach_version_label(version), created_at=version['created_at']
        )
        content = version['content']
    projection.update(content_projection(content, sections))
    return cap(projection, APPROACH_PRIORITIES)


GET_APPROACH = ToolSpec(
    name='get_approach',
    title='Read the approach',
    description=(
        'Returns the study approach: the question, scope, limitations and open questions, '
        'then numbered steps ("Step 2"), cases, limits, assumptions, model bindings and basis '
        'references, each with its id and title. which: "draft" (default) reads the working '
        'draft and returns its revision_token, the value to pass back as expected_revision '
        'when you change the draft; "latest_version" reads the latest saved version; '
        '"version_number" reads the saved version numbered version_number. sections limits '
        'the answer to some parts (question, steps, cases, limits, assumptions, models, '
        "basis). Saved versions never change. The text is the authors', inside "
        'untrusted_content blocks. Guidance: get_playbook("approach").'
    ),
    input_schema={
        'type': 'object',
        'additionalProperties': False,
        'properties': {
            'which': {
                'type': 'string',
                'enum': ['draft', 'latest_version', 'version_number'],
                'description': 'Which approach to read (default "draft").',
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
    owners=('approach',),
    outcome='none',
    activity_label='Read: approach',
    handler=get_approach,
    api_operations=(STATE, VERSIONS, VERSION),
)


async def list_approach_versions(arguments, ctx):
    """One page of saved approach versions in the owner's order (newest first)."""
    limit, position = page_arguments('list_approach_versions', arguments)
    params = {'limit': str(limit)}
    if position is not None:
        params['cursor'] = _api_cursor(position)
    body = (await read(ctx, study_path(ctx, 'approach', 'versions'), params))['data']
    after = body['next_cursor']
    return {
        'versions': [
            dict(
                approach_version_label(item),
                created_at=item['created_at'],
                predecessor=label(
                    'approach_version', item['predecessor_version_id'], 'Previous saved version'
                )
                if item['predecessor_version_id']
                else missing('first_version'),
            )
            for item in body['items']
        ],
        'next_cursor': None if after is None else encode_cursor('list_approach_versions', after),
    }


LIST_APPROACH_VERSIONS = ToolSpec(
    name='list_approach_versions',
    title='List saved approach versions',
    description=(
        'Returns one page of the saved approach versions, newest first: number, id and when '
        'each was saved. Saved versions never change; read one with get_approach (which '
        '"version_number"). limit: items per page (1 to 25, default 10); cursor: the '
        'next_cursor of the previous page, passed back unchanged. '
        'Guidance: get_playbook("approach").'
    ),
    input_schema={
        'type': 'object',
        'additionalProperties': False,
        'properties': {'limit': LIMIT_SCHEMA, 'cursor': CURSOR_SCHEMA},
    },
    effect='read',
    stage='read_only',
    surfaces=SURFACES,
    owners=('approach',),
    outcome='none',
    activity_label='Read: approach versions',
    handler=list_approach_versions,
    api_operations=(VERSIONS,),
)


async def get_approach_usage(arguments, ctx):
    """Which saved configurations and runs implement a saved approach version (and a case)."""
    version_id = arguments['approach_version_id']
    limit, position = page_arguments('get_approach_usage', arguments)
    version = await _saved(ctx, version_id)
    cases = {c['case_id']: (n, c['title']) for n, c in enumerate(version['content']['cases'], 1)}
    params = {'limit': str(limit)}
    if position is not None:
        params['cursor'] = _api_cursor(position)
    if arguments.get('case_id') is not None:
        if arguments['case_id'] not in cases:
            raise ToolError(
                'not_found',
                'That approach version has no case with that id.',
                next_step='Call get_approach to see the cases of the version.',
            )
        params['case_id'] = arguments['case_id']
    path = study_path(ctx, 'approach', 'versions', version_id, 'usage')
    body = (await read(ctx, path, params))['data']
    items = []
    for item in body['items']:
        entry = (
            ref('run', item['run_id'], None, missing='call_list_runs')
            if item['kind'] == 'run'
            else ref(
                'configuration_version',
                item['configuration_revision_id'],
                None,
                missing='call_get_configuration',
            )
        )
        if item['kind'] == 'run':
            entry['configuration'] = ref(
                'configuration_version',
                item['configuration_revision_id'],
                None,
                missing='call_get_configuration',
            )
        case_id = item['case_id']
        if case_id is None:
            entry['case'] = missing('no_case')
        else:
            number, title = cases.get(case_id, (None, None))
            entry['case'] = ref(
                'approach_case', case_id, title, missing='case_not_in_version', number=number
            )
        items.append(entry)
    after = body['next_cursor']
    return cap(
        {
            'approach_version': approach_version_label(version),
            'usage': items,
            'next_cursor': None if after is None else encode_cursor('get_approach_usage', after),
        },
        [('usage', 'usage items', 'get_approach_usage with a smaller limit')],
    )


GET_APPROACH_USAGE = ToolSpec(
    name='get_approach_usage',
    title='See which configurations and runs implement an approach version',
    description=(
        'Returns one page of the saved configurations and runs that implement a saved '
        'approach version, each with the case it implements. approach_version_id: the saved '
        'version (from list_approach_versions or get_approach); case_id: only the '
        'configurations and runs of that case of the version. limit: items per page (1 to '
        '25, default 10); cursor: the next_cursor of the previous page, passed back unchanged. '
        'Configuration and run names are not part of this read; use get_configuration or '
        'list_runs. Guidance: get_playbook("approach").'
    ),
    input_schema={
        'type': 'object',
        'additionalProperties': False,
        'required': ['approach_version_id'],
        'properties': {
            'approach_version_id': uuid_schema('The saved approach version.'),
            'case_id': uuid_schema('A case of that version, to narrow the answer.'),
            'limit': LIMIT_SCHEMA,
            'cursor': CURSOR_SCHEMA,
        },
    },
    effect='read',
    stage='read_only',
    surfaces=SURFACES,
    owners=('approach',),
    outcome='none',
    activity_label='Read: approach usage',
    handler=get_approach_usage,
    api_operations=(VERSION, USAGE),
)

TOOLS = (GET_APPROACH, LIST_APPROACH_VERSIONS, GET_APPROACH_USAGE)
