"""Model explanations (ADR-0007). The application's ``explanations`` owner keeps one draft per
model and, for each saved model version, at most one explanation that pins it and never changes.
These tools read the draft or the explanation of a model version, change the draft section by
section and save the draft as the explanation of one exact model version, through the public
API. The modeling service never holds an explanation."""

from ..projections import (
    cap,
    command_id,
    label,
    missing,
    read,
    ref,
    report,
    send,
    study_path,
    tool_path,
    untrusted,
    uuid_schema,
)
from ..spec import SURFACES, ToolError, ToolSpec

BASE = '/api/1/studies/{study_id}/models/{model_id}'
STATE = ('GET', BASE + '/explanation')
OF_VERSION = ('GET', BASE + '/revisions/{revision_id}/explanation')
SAVE_DRAFT = ('POST', BASE + '/explanation/draft')
SAVE_VERSION = ('POST', BASE + '/explanation/versions')
OWNERS = ('explanations',)
TEXTS = ('represents', 'basis', 'calculation_logic')
SECTIONS = TEXTS + ('components', 'evidence_links', 'limits', 'component_details')
PRIORITIES = [
    ('evidence_links', 'evidence', 'get_model_explanation'),
    ('components', 'component explanations', 'get_model_explanation'),
]
EMPTY_CONTENT = dict(
    schema_version='1',
    represents='',
    basis='',
    calculation_logic='',
    components=[],
    evidence_links=[],
)


def _path(ctx, model_id, *parts):
    return study_path(ctx, 'models', model_id, *parts)


def _version_label(version):
    return label(
        'model_explanation_version',
        version['explanation_version_id'],
        'Model explanation ' + str(version['version_number']),
        number=version['version_number'],
        model_version=label('model_version', version['model_revision_id'], 'Model version'),
    )


def content_projection(content):
    """The explanation texts, component explanations and evidence; every text is the authors'
    (untrusted)."""
    return {
        **({'limits': untrusted('model limits', text=content['limits']),
            'component_details': [dict(
                ref('component_instance', item['instance_id'], None, missing='call_get_model'),
                description=untrusted('component description', text=item['description']),
                limits=untrusted('component limits', text=item['limits']),
            ) for item in content['component_details']]}
           if content['schema_version'] in ('2', '3') else {}),
        **({'monetary_quantities': [
            dict(instance_id=item['instance_id'], port_id=item['port_id'],
                 catalogue_expression=item['catalogue_expression'],
                 price_year=item['price_year'],
                 economic_basis=untrusted('economic basis', text=item['economic_basis']),
                 evidence_version_ids=[link['evidence_version_id']
                                       for link in item['evidence_links']])
            for item in content['monetary_quantities']
        ]} if content['schema_version'] == '3' else {}),
        'explanation': untrusted('model explanation', text={key: content[key] for key in TEXTS}),
        'components': [
            dict(
                ref(
                    'component_instance' if item['kind'] == 'instance' else 'definition_version',
                    item[_target_key(item)],
                    None,
                    missing='call_get_model',
                ),
                explanation=untrusted('component explanation', text=item['explanation']),
            )
            for item in content['components']
        ],
        'evidence_links': [
            dict(
                ref(
                    'evidence_version',
                    link['evidence_version_id'],
                    None,
                    missing='call_read_evidence',
                ),
                relation=link['relation'],
                **(
                    {'locator': untrusted('evidence locator', text=link['locator'])}
                    if link.get('locator')
                    else {}
                ),
            )
            for link in content['evidence_links']
        ],
    }


def _target_key(item):
    return 'instance_id' if item['kind'] == 'instance' else 'definition_version_id'


async def get_model_explanation(arguments, ctx):
    """The explanation draft of a model (with its revision_token) or the saved explanation of
    one model version."""
    model_id = arguments['model_id']
    version_id = arguments.get('model_version_id')
    if version_id is not None:
        body = (
            await read(
                ctx,
                _path(ctx, model_id, 'revisions', version_id, 'explanation'),
                next_step='Call list_models and use a model id from it.',
            )
        )['data']
        explanation = body['explanation']
        if explanation is None:
            return {
                'model_version': label('model_version', version_id, 'Model version'),
                'explanation': missing('no_saved_explanation'),
            }
        projection = {'explanation_version': dict(_version_label(explanation))}
        projection['explanation_version']['created_at'] = explanation['created_at']
        projection.update(content_projection(explanation['content']))
        return cap(projection, PRIORITIES)
    state = (
        await read(
            ctx,
            _path(ctx, model_id, 'explanation'),
            next_step='Call list_models and use a model id from it.',
        )
    )['data']
    draft, latest = state['draft'], state['latest_version']
    projection = {
        'latest_explanation': _version_label(latest) if latest else missing('no_saved_explanation')
    }
    if draft is None:
        projection['draft'] = missing('no_draft')
        return projection
    projection['revision_token'] = draft['revision']
    projection['updated_at'] = draft['updated_at']
    based = draft['based_on_model_revision_id']
    projection['based_on'] = (
        label('model_version', based, 'Model version') if based else missing('never_saved')
    )
    projection.update(content_projection(draft['content']))
    return cap(projection, PRIORITIES)


MODEL_ID = uuid_schema('The model id (from list_models).')

GET_MODEL_EXPLANATION = ToolSpec(
    name='get_model_explanation',
    title='Read a model explanation',
    description=(
        'Returns the explanation of a model: what it represents, its basis and reasoning, its '
        'calculation logic, explanations of components (by instance id or definition version '
        'id) and evidence with its relation (supports, challenges or context). Without '
        'model_version_id it reads the working draft and returns its revision_token; with '
        'model_version_id it reads the saved explanation of that model version, which never '
        "changes. The text is the authors', inside untrusted_content blocks. "
        'Guidance: get_playbook("model").'
    ),
    input_schema={
        'type': 'object',
        'additionalProperties': False,
        'required': ['model_id'],
        'properties': {
            'model_id': MODEL_ID,
            'model_version_id': uuid_schema('A saved model version id (from get_model).'),
        },
    },
    effect='read',
    stage='read_only',
    surfaces=SURFACES,
    owners=OWNERS,
    outcome='none',
    activity_label='Read: model explanation',
    handler=get_model_explanation,
    api_operations=(STATE, OF_VERSION),
)

_UUID = {'type': 'string', 'format': 'uuid', 'minLength': 36, 'maxLength': 36}
_TEXT = {'type': 'string', 'maxLength': 16384}
_STATEMENT = {'type': 'string', 'minLength': 1, 'maxLength': 4096}
CONTENT_SCHEMA = {
    'type': 'object',
    'additionalProperties': False,
    'minProperties': 1,
    'description': (
        'The sections to change. A section given replaces that section whole; a section '
        'left out stays as it is.'
    ),
    'properties': {
        'limits': dict(_TEXT, description='Model applicability limits and exclusions.'),
        'component_details': {
            'type': 'array', 'maxItems': 1000,
            'description': 'Local description and applicability limits, one entry per component.',
            'items': {
                'type': 'object', 'additionalProperties': False,
                'required': ['instance_id', 'description', 'limits'],
                'properties': {'instance_id': _UUID, 'description': dict(_TEXT, maxLength=4096),
                               'limits': dict(_TEXT, maxLength=4096)},
            },
        },
        'represents': dict(
            _TEXT, description='The physical system, purpose and scope represented by the model.'
        ),
        'basis': dict(
            _TEXT,
            description=(
                'Governing relations, physical assumptions, applicability and why they '
                'fit the purpose.'
            ),
        ),
        'calculation_logic': dict(
            _TEXT,
            description=(
                'How inputs produce outputs: equations, component connections and algorithm '
                'steps. Sampling counts, training/validation partitions, accuracy targets and '
                'numerical checks belong in analysis description (Analysis details) and '
                'design/assessment records.'
            ),
        ),
        'components': {
            'type': 'array',
            'maxItems': 1000,
            'description': (
                'Component explanations, each for one instance (kind "instance" with '
                'instance_id) or for every instance of a definition version (kind '
                '"definition_version" with definition_version_id), ids from get_model.'
            ),
            'items': {
                'type': 'object',
                'additionalProperties': False,
                'required': ['kind', 'explanation'],
                'properties': {
                    'kind': {'type': 'string', 'enum': ['instance', 'definition_version']},
                    'instance_id': _UUID,
                    'definition_version_id': _UUID,
                    'explanation': _STATEMENT,
                },
            },
        },
        'evidence_links': {
            'type': 'array',
            'maxItems': 64,
            'description': 'Evidence versions of this study (from list_evidence) with their '
            'relation.',
            'items': {
                'type': 'object',
                'additionalProperties': False,
                'required': ['evidence_version_id', 'relation'],
                'properties': {
                    'evidence_version_id': _UUID,
                    'relation': {
                        'type': 'string',
                        'enum': ['supports', 'challenges', 'context'],
                    },
                    'locator': {'type': 'string', 'maxLength': 1024},
                },
            },
        },
    },
}


CONTENT_SCHEMA['properties']['monetary_quantities'] = dict(
    type='array', maxItems=1000, items=dict(
        type='object', additionalProperties=False,
        required=['instance_id', 'port_id', 'catalogue_expression', 'price_year',
                  'economic_basis', 'evidence_links'],
        properties=dict(
            instance_id=dict(type='string', format='uuid', maxLength=36),
            port_id=dict(type='string', format='uuid', maxLength=36),
            catalogue_expression=dict(type='string', minLength=1, maxLength=64),
            price_year=dict(type='integer', minimum=1800, maximum=9999),
            economic_basis=dict(type='string', minLength=1, maxLength=4096),
            evidence_links=CONTENT_SCHEMA['properties']['evidence_links'],
        ),
    ),
    description='Exact monetary expression selected from the units catalogue, price year, '
                'economic basis and evidence for each exact model quantity. '
                'No automatic currency, inflation or denominator conversion is performed.',
)


def _components(items):
    """Each component explanation names exactly the id its kind needs."""
    components = []
    for index, item in enumerate(items):
        key = _target_key(item)
        other = 'definition_version_id' if key == 'instance_id' else 'instance_id'
        if key not in item or other in item:
            raise ToolError(
                'invalid_input',
                'Each component explanation names exactly the id its kind needs.',
                fields=(
                    {
                        'path': 'content.components[' + str(index) + ']',
                        'problem': 'needs ' + key + ' only',
                    },
                ),
                next_step='Call update_model_explanation again with corrected components.',
            )
        components.append(
            {'kind': item['kind'], key: item[key], 'explanation': item['explanation']}
        )
    return components


async def update_model_explanation(arguments, ctx):
    """Change the explanation draft section by section under the revision the agent read."""
    model_id, expected = arguments['model_id'], arguments['expected_revision']
    state = (
        await read(
            ctx,
            _path(ctx, model_id, 'explanation'),
            next_step='Call list_models and use a model id from it.',
        )
    )['data']
    draft = state['draft']
    if (draft['revision'] if draft else None) != expected:
        raise ToolError(
            'conflict',
            'The explanation draft changed since you read it; nothing was written.',
            fields=({'path': 'expected_revision', 'problem': 'is not the current draft revision'},),
            next_step='Call get_model_explanation, apply your change to what it returns and pass '
            'its revision_token as expected_revision.',
        )
    content = dict(draft['content'] if draft else EMPTY_CONTENT)
    changes = dict(arguments['content'])
    if 'components' in changes:
        changes['components'] = _components(changes['components'])
    if 'limits' in changes or 'component_details' in changes:
        content = dict(content, schema_version=max(content['schema_version'], '2'),
                       limits=content.get('limits', ''),
                       component_details=content.get('component_details', []))
    if 'monetary_quantities' in changes:
        content = dict(content, schema_version='3', limits=content.get('limits', ''),
                       component_details=content.get('component_details', []),
                       monetary_quantities=content.get('monetary_quantities', []))
    content.update(changes)
    body = {'command_id': command_id(ctx), 'expected_revision': expected, 'content': content}
    saved = (
        await send(
            ctx,
            'POST',
            _path(ctx, model_id, 'explanation', 'draft'),
            body,
            tool='update_model_explanation',
            conflict_step='Call get_model_explanation again and reapply your change.',
        )
    )['data']
    report(ctx, 'model_explanation_draft', model_id, version_id=saved['revision'])
    projection = {
        'revision_token': saved['revision'],
        'updated_at': saved['updated_at'],
        'changed_sections': sorted(arguments['content']),
    }
    projection.update(content_projection(saved['content']))
    return cap(projection, PRIORITIES)


UPDATE_MODEL_EXPLANATION = ToolSpec(
    name='update_model_explanation',
    title='Change a model explanation draft',
    description=(
        'Changes the explanation draft of a model: what it represents, its basis and '
        'reasoning, its calculation logic, component explanations, local component descriptions, model/component limits and evidence links. '
        'expected_revision: the revision_token of your last get_model_explanation (null when '
        'the model has no draft yet). content: only the sections to change; a section given '
        'replaces that section whole, a section left out stays as it is. Evidence must belong '
        'to this study. Returns the new revision_token and the whole draft. Saved explanations '
        'never change; save one with save_model_explanation_version. '
        'Guidance: get_playbook("model").'
    ),
    input_schema={
        'type': 'object',
        'additionalProperties': False,
        'required': ['model_id', 'expected_revision', 'content'],
        'properties': {
            'model_id': MODEL_ID,
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
    owners=OWNERS,
    outcome='receipt:model_explanation_draft',
    activity_label='Changed: model explanation draft',
    handler=update_model_explanation,
    api_operations=(STATE, SAVE_DRAFT),
    attribution_kind='model_explanation_draft',
)


async def save_model_explanation_version(arguments, ctx):
    """Freeze the current draft as the explanation of one exact model version."""
    model_id = arguments['model_id']
    body = {
        'command_id': command_id(ctx),
        'expected_revision': arguments['expected_revision'],
        'model_revision_id': arguments['model_version_id'],
    }
    saved = (
        await send(
            ctx,
            'POST',
            _path(ctx, model_id, 'explanation', 'versions'),
            body,
            tool='save_model_explanation_version',
            conflict_step='Call get_model_explanation, check the draft and save again with its '
            'revision_token.',
            field_map=lambda pointer: (
                {
                    '/model_revision_id': 'model_version_id',
                    '/expected_revision': 'expected_revision',
                }.get(pointer)
                or tool_path(pointer, 'draft')
            ),
        )
    )['data']
    version, draft = saved['version'], saved['draft']
    report(
        ctx,
        'model_explanation_version',
        model_id,
        version_id=version['explanation_version_id'],
        number=version['version_number'],
    )
    return {
        'explanation_version': dict(_version_label(version), created_at=version['created_at']),
        'draft': {'revision_token': draft['revision']},
    }


SAVE_MODEL_EXPLANATION_VERSION = ToolSpec(
    name='save_model_explanation_version',
    title='Save a model explanation for a model version',
    description=(
        'Saves the current explanation draft of a model exactly as the explanation of one '
        'saved model version (model_version_id, from get_model). A model version has at most '
        'one explanation and it never changes afterwards; to explain a model anew, save a new '
        'model version first. Every component explanation must name an instance or definition '
        'version of that model version. expected_revision: the revision_token of the draft '
        'you checked. Returns the saved explanation and the continuing draft. '
        'Guidance: get_playbook("model").'
    ),
    input_schema={
        'type': 'object',
        'additionalProperties': False,
        'required': ['model_id', 'model_version_id', 'expected_revision'],
        'properties': {
            'model_id': MODEL_ID,
            'model_version_id': uuid_schema('The saved model version to explain.'),
            'expected_revision': {
                'type': 'string',
                'minLength': 36,
                'maxLength': 36,
                'description': 'The revision_token of the draft to save.',
            },
        },
    },
    effect='record',
    stage='authoring',
    surfaces=SURFACES,
    owners=OWNERS,
    outcome='receipt:model_explanation_version',
    activity_label='Saved: model explanation',
    handler=save_model_explanation_version,
    api_operations=(SAVE_VERSION,),
    attribution_kind='model_explanation_version',
)

TOOLS = (GET_MODEL_EXPLANATION, UPDATE_MODEL_EXPLANATION, SAVE_MODEL_EXPLANATION_VERSION)
