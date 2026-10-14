"""Model and quantities: the read tools (tooling spec section 4.4). The modeling service owns
model composition, drafts and saved versions; HYPRN MVP's ``modeling`` module serves them
through the public API, and these tools only read. Saved versions are numbered by their place
in the owner's stored order (oldest first): "Model version 3" is the third saved version."""

import base64
import binascii

from ..projections import (
    CURSOR_SCHEMA,
    LIMIT_SCHEMA,
    ModelView,
    cap,
    decode_cursor,
    encode_cursor,
    label,
    missing,
    read,
    ref,
    study_path,
    untrusted,
    uuid_schema,
)
from ..spec import SURFACES, ToolError, ToolSpec

MODELS = ('GET', '/api/1/studies/{study_id}/models')
MODEL = ('GET', '/api/1/studies/{study_id}/models/{model_id}')
REVISIONS = ('GET', '/api/1/studies/{study_id}/models/{model_id}/revisions')
REVISION = ('GET', '/api/1/studies/{study_id}/models/{model_id}/revisions/{revision_id}')
EVIDENCE = ('GET', '/api/1/studies/{study_id}/models/{model_id}/assumption-evidence')
REVISION_PAGE = 100
MAX_REVISION_PAGES = 20
SOURCE_LINES = 400
SOURCE_CHARS = 16000
OWNERS = ('modeling',)


def version_label(revision_id, number):
    return label('model_version', revision_id, 'Model version ' + str(number), number=number)


async def _draft(ctx, model_id):
    path = study_path(ctx, 'models', model_id)
    return (await read(ctx, path, next_step='Call list_models.'))['data']


async def _revisions(ctx, model_id):
    """Every saved version of a model in the owner's order, with ``complete`` false when more
    than the bounded number of pages exist."""
    path = study_path(ctx, 'models', model_id, 'revisions')
    items, cursor = [], None
    for _ in range(MAX_REVISION_PAGES):
        params = {'limit': str(REVISION_PAGE)}
        if cursor is not None:
            params['cursor'] = cursor
        body = await read(ctx, path, params, next_step='Call list_models.')
        items.extend(body['data'])
        cursor = body.get('next_cursor')
        if cursor is None:
            return items, True
    return items, False


def _versions_summary(revisions, complete):
    if not revisions:
        return {'count': 0, 'latest': missing('no_saved_version')}
    return {
        'count': len(revisions),
        'complete': complete,
        'latest': version_label(revisions[-1]['model_revision_id'], len(revisions))
        if complete
        else missing('more_versions_than_read'),
    }


async def list_models(arguments, ctx):
    """One page of the study's models with their names, draft revision tokens and versions."""
    limit = arguments.get('limit', 10)
    cursor = arguments.get('cursor')
    params = {'limit': str(limit)}
    if cursor is not None:
        params['cursor'] = decode_cursor('list_models', cursor)
    body = await read(ctx, study_path(ctx, 'models'), params)
    models = []
    for association in body['data']:
        model_id = association['model_id']
        draft = await _draft(ctx, model_id)
        revisions, complete = await _revisions(ctx, model_id)
        models.append(
            dict(
                ref('model', model_id, draft['name']),
                revision_token=draft['draft_revision'],
                versions=_versions_summary(revisions, complete),
            )
        )
    after = body.get('next_cursor')
    return cap(
        {
            'models': models,
            'next_cursor': None if after is None else encode_cursor('list_models', after),
        },
        [('models', 'models', 'list_models with a smaller limit')],
    )


LIST_MODELS = ToolSpec(
    name='list_models',
    title='List the models of the study',
    description=(
        "Returns one page of the study's models: name and id, the revision_token of the "
        'working draft (pass it back as expected_revision when you edit the draft) and the '
        'saved versions (count, and the latest as "Model version N" with its id). limit: '
        'items per page (1 to 25, default 10); cursor: the next_cursor of the previous page, '
        'passed back unchanged. Read one model with get_model. '
        'Guidance: get_playbook("model").'
    ),
    input_schema={
        'type': 'object',
        'additionalProperties': False,
        'properties': {'limit': LIMIT_SCHEMA, 'cursor': CURSOR_SCHEMA},
    },
    effect='read',
    stage='read_only',
    surfaces=SURFACES,
    owners=OWNERS,
    outcome='none',
    activity_label='Read: models',
    handler=list_models,
    api_operations=(MODELS, MODEL, REVISIONS),
)


def _port(view, instance_id, port_id):
    port = view.ports[(instance_id, port_id)]
    meaning = port['meaning']
    value = dict(
        ref('port', port_id, port['port']),
        direction=port['direction'],
        unit=port['unit'],
    )
    if meaning is not None:
        value['meaning'] = untrusted('quantity meaning', text=meaning)
    else:
        value['meaning'] = missing(
            'not_declared' if port['meanings_declared'] else 'not_recorded_by_this_model_version'
        )
    return value


def _source(model, definition, limit_lines):
    files = {f['sha256']: f for f in model.get('source_files', ())}
    texts = []
    for digest in definition.get('source_refs', ()):
        entry = files.get(digest)
        if entry is None:
            continue
        try:
            texts.append(base64.b64decode(entry['bytes'], validate=True).decode('utf-8', 'replace'))
        except (binascii.Error, ValueError):
            continue
    if not texts:
        return missing('no_source_recorded')
    lines = '\n'.join(texts).split('\n')
    shown = '\n'.join(lines[:limit_lines])
    truncated = len(lines) > limit_lines or len(shown) > SOURCE_CHARS
    result = untrusted('component source', text=shown[:SOURCE_CHARS])
    result['lines'] = len(lines)
    result['truncated'] = truncated
    if truncated:
        result['note'] = (
            'Shown up to ' + str(limit_lines) + ' lines; the source has ' + str(len(lines)) + '.'
        )
    return result


def model_projection(model, name, include_source_for=()):
    """Components with their ports, connections, assumptions, free inputs, outputs and
    warnings of one stored model draft or version; source only for the named components."""
    view = ModelView(model)
    names = {i['instance_id']: i['name'] for i in model['instances']}
    wanted = set(include_source_for)
    known = {i['name'] for i in view.components}
    if wanted - known:
        raise ToolError(
            'invalid_input',
            'include_source_for names a component this model does not have.',
            fields=(
                {'path': 'include_source_for', 'problem': 'must name components of the model'},
            ),
            next_step='Call get_model without include_source_for to see the component names.',
        )
    targeted = {
        (c['target_ref']['instance_id'], c['target_ref']['port_id']) for c in model['connections']
    }
    components, free_inputs, outputs, warnings, sources = [], [], [], [], []
    for instance in view.components:
        definition = view.definitions.get(instance['definition_version_id'])
        if definition is None:
            continue
        iid = instance['instance_id']
        ports = [_port(view, iid, p['port_id']) for p in definition['ports']]
        components.append(
            dict(
                ref('component', iid, instance['name']),
                definition=ref(
                    'definition',
                    definition['definition_id'],
                    definition['name'],
                    definition_version_id=definition['definition_version_id'],
                    definition_kind=definition['kind'],
                ),
                inputs=[p for p in ports if p['direction'] == 'input'],
                outputs=[p for p in ports if p['direction'] == 'output'],
            )
        )
        for port in definition['ports']:
            key = (iid, port['port_id'])
            entry = view.quantity_ref({'instance_id': iid, 'port_id': port['port_id']}, 'quantity')
            entry['unit'] = view.ports[key]['unit']
            if port['direction'] == 'input' and key not in targeted:
                free_inputs.append(entry)
            elif port['direction'] == 'output':
                outputs.append(entry)
            if view.ports[key]['unit'] == 'unspecified':
                warnings.append(dict(entry, warning='unspecified_unit'))
            if view.ports[key]['meanings_declared'] and view.ports[key]['meaning'] is None:
                warnings.append(dict(entry, warning='missing_quantity_meaning'))
        if instance['name'] in wanted:
            sources.append(
                dict(
                    ref('component', iid, instance['name']),
                    source=_source(model, definition, SOURCE_LINES),
                )
            )
    connections = [
        ref(
            'connection',
            c['connection_id'],
            _arrow(view, c),
            missing='port_not_in_model',
        )
        for c in model['connections']
    ]
    assumptions = [
        dict(
            ref('model_assumption', a['assumption_id'], a['statement']),
            owner='model'
            if a['owner']['kind'] == 'model'
            else ref('component', a['owner']['instance_id'], names.get(a['owner']['instance_id'])),
            evidence=[
                dict(
                    ref(
                        'evidence_version',
                        link['evidence_version_id'],
                        None,
                        missing='call_read_evidence',
                    ),
                    relation=link['relation'],
                )
                for link in a['evidence_links']
            ],
        )
        for a in model.get('assumptions', ())
    ]
    projection = {
        'model': ref('model', model['model_id'], name),
        'components': components,
        'connections': connections,
        'assumptions': assumptions
        if 'assumptions' in model
        else missing('not_recorded_by_this_model_version'),
        'free_inputs': free_inputs,
        'outputs': outputs,
        'warnings': warnings,
    }
    if wanted:
        projection['source'] = sources
    return projection


def _arrow(view, connection):
    source, target = view.path(connection['source_ref']), view.path(connection['target_ref'])
    if source is None or target is None:
        return None
    return source + ' -> ' + target


MODEL_PRIORITIES = [
    ('source', 'component source', 'get_model with include_source_for naming fewer components'),
    ('warnings', 'warnings', 'get_model again after fixing the listed warnings'),
    ('assumptions', 'model assumptions', 'get_assumption_evidence'),
    ('connections', 'connections', 'the model page in HYPRN MVP'),
    ('outputs', 'outputs', 'the components list of this result'),
    ('free_inputs', 'free inputs', 'the components list of this result'),
    ('components', 'components', 'the model page in HYPRN MVP'),
]


async def get_model(arguments, ctx):
    """One model's draft, latest saved version or an exact saved version."""
    model_id = arguments['model_id']
    which = arguments.get('which', 'draft')
    version_id = arguments.get('model_version_id')
    if (which == 'version') != (version_id is not None):
        raise ToolError(
            'invalid_input',
            'model_version_id is given exactly when which is "version".',
            fields=({'path': 'model_version_id', 'problem': 'must match which'},),
            next_step='Call get_model again with a matching which and model_version_id.',
        )
    draft = await _draft(ctx, model_id)
    head = {}
    if which == 'draft':
        model = draft
        head['revision_token'] = draft['draft_revision']
        head['version'] = missing('working_draft')
    else:
        revisions, complete = await _revisions(ctx, model_id)
        ids = [r['model_revision_id'] for r in revisions]
        if which == 'latest':
            if not revisions or not complete:
                head['version'] = missing(
                    'no_saved_version' if not revisions else 'more_versions_than_read'
                )
                return dict({'model': ref('model', model_id, draft['name'])}, **head)
            version_id = ids[-1]
        if version_id in ids:
            head['version'] = version_label(version_id, ids.index(version_id) + 1)
        else:
            head['version'] = label('model_version', version_id, 'Saved model version')
        path = study_path(ctx, 'models', model_id, 'revisions', version_id)
        model = (await read(ctx, path, next_step='Call list_model_versions.'))['data']
    projection = model_projection(model, draft['name'], arguments.get('include_source_for', ()))
    projection.update(head)
    return cap(projection, MODEL_PRIORITIES)


GET_MODEL = ToolSpec(
    name='get_model',
    title='Read a model',
    description=(
        'Returns one model: its components (instance name, definition, input and output '
        'ports with unit and quantity meaning), connections as "A.out -> B.in", model and '
        'component assumptions, free inputs (unconnected inputs a configuration must set), '
        'outputs and warnings (unspecified units, missing quantity meanings). which: "draft" '
        '(default) reads the working draft and returns its revision_token; "latest" the '
        'latest saved version; "version" the saved version model_version_id. '
        'include_source_for: up to 3 component names whose Python source to include, at most '
        '400 lines each with a truncation note; source is never executed. Names, meanings '
        "and source are the authors', inside untrusted_content blocks. "
        'Guidance: get_playbook("model").'
    ),
    input_schema={
        'type': 'object',
        'additionalProperties': False,
        'required': ['model_id'],
        'properties': {
            'model_id': uuid_schema('The model, from list_models.'),
            'which': {
                'type': 'string',
                'enum': ['draft', 'latest', 'version'],
                'description': 'Which state of the model to read (default "draft").',
            },
            'model_version_id': uuid_schema('The saved version, only with which "version".'),
            'include_source_for': {
                'type': 'array',
                'items': {'type': 'string', 'minLength': 1, 'maxLength': 4096},
                'maxItems': 3,
                'uniqueItems': True,
                'description': 'Component names whose source to include.',
            },
        },
    },
    effect='read',
    stage='read_only',
    surfaces=SURFACES,
    owners=OWNERS,
    outcome='none',
    activity_label='Read: model',
    handler=get_model,
    api_operations=(MODEL, REVISIONS, REVISION),
)


async def list_model_versions(arguments, ctx):
    """One page of a model's saved versions, numbered in the owner's stored order."""
    model_id = arguments['model_id']
    limit = arguments.get('limit', 10)
    position = None
    if arguments.get('cursor') is not None:
        position = decode_cursor('list_model_versions:' + model_id, arguments['cursor'])
    draft = await _draft(ctx, model_id)
    params = {'limit': str(limit)}
    offset = 0
    if position is not None:
        params['cursor'], offset = position['after'], position['offset']
    path = study_path(ctx, 'models', model_id, 'revisions')
    body = await read(ctx, path, params, next_step='Call list_models.')
    versions = []
    for n, item in enumerate(body['data'], offset + 1):
        parent = item['parent_model_revision_id']
        versions.append(
            dict(
                version_label(item['model_revision_id'], n),
                parent=label('model_version', parent, 'Previous saved version')
                if parent
                else missing('first_version'),
            )
        )
    after = body.get('next_cursor')
    next_cursor = None
    if after is not None:
        next_cursor = encode_cursor(
            'list_model_versions:' + model_id, {'after': after, 'offset': offset + len(versions)}
        )
    return {
        'model': ref('model', model_id, draft['name']),
        'versions': versions,
        'next_cursor': next_cursor,
    }


LIST_MODEL_VERSIONS = ToolSpec(
    name='list_model_versions',
    title='List the saved versions of a model',
    description=(
        'Returns one page of the saved versions of a model, oldest first, as "Model version '
        'N" with id and the version it was saved from. Saved versions never change; read one '
        'with get_model (which "version"). model_id: the model, from list_models. limit: items '
        'per page (1 to 25, default 10); cursor: the next_cursor of the previous page for the '
        'same model, passed back unchanged. Guidance: get_playbook("model").'
    ),
    input_schema={
        'type': 'object',
        'additionalProperties': False,
        'required': ['model_id'],
        'properties': {
            'model_id': uuid_schema('The model, from list_models.'),
            'limit': LIMIT_SCHEMA,
            'cursor': CURSOR_SCHEMA,
        },
    },
    effect='read',
    stage='read_only',
    surfaces=SURFACES,
    owners=OWNERS,
    outcome='none',
    activity_label='Read: model versions',
    handler=list_model_versions,
    api_operations=(MODEL, REVISIONS),
)


async def get_assumption_evidence(arguments, ctx):
    """Which evidence supports each model assumption of the draft or of a saved version."""
    model_id = arguments['model_id']
    which = arguments.get('which', 'draft')
    version_id = arguments.get('model_version_id')
    if (which == 'version') != (version_id is not None):
        raise ToolError(
            'invalid_input',
            'model_version_id is given exactly when which is "version".',
            fields=({'path': 'model_version_id', 'problem': 'must match which'},),
            next_step='Call get_assumption_evidence again with a matching which.',
        )
    draft = await _draft(ctx, model_id)
    if which == 'draft':
        params = {'draft_revision': draft['draft_revision']}
        statements = {a['assumption_id']: a['statement'] for a in draft.get('assumptions', ())}
        head = {'version': missing('working_draft'), 'revision_token': draft['draft_revision']}
    else:
        params = {'model_revision_id': version_id}
        path = study_path(ctx, 'models', model_id, 'revisions', version_id)
        saved = (await read(ctx, path, next_step='Call list_model_versions.'))['data']
        statements = {a['assumption_id']: a['statement'] for a in saved.get('assumptions', ())}
        head = {'version': label('model_version', version_id, 'Saved model version')}
    path = study_path(ctx, 'models', model_id, 'assumption-evidence')
    data = (await read(ctx, path, params))['data']
    records = {e['evidence_version_id']: e for e in data['evidence']}
    assumptions = {}
    for link in data['links']:
        entry = assumptions.setdefault(
            link['assumption_id'],
            dict(
                ref(
                    'model_assumption',
                    link['assumption_id'],
                    statements.get(link['assumption_id']),
                    missing='call_get_model',
                ),
                evidence=[],
            ),
        )
        record = records.get(link['evidence_version_id'])
        if link['status'] == 'resolved' and record is not None:
            evidence = ref(
                'evidence_version',
                link['evidence_version_id'],
                record.get('title'),
                missing='no_title_recorded',
            )
        else:
            evidence = ref(
                'evidence_version', link['evidence_version_id'], None, missing='unavailable'
            )
        evidence['status'] = link['status']
        entry['evidence'].append(evidence)
    projection = dict(
        {'model': ref('model', model_id, draft['name'])},
        **head,
        assumptions=list(assumptions.values()),
    )
    return cap(projection, [('assumptions', 'assumptions', 'get_model and read_evidence')])


GET_ASSUMPTION_EVIDENCE = ToolSpec(
    name='get_assumption_evidence',
    title='See which evidence supports each model assumption',
    description=(
        'Returns, for each model and component assumption, the evidence versions it cites '
        'with their titles and whether each is still available in the study. which: "draft" '
        '(default) for the working draft, or "version" for the saved version model_version_id. '
        'model_id: the model, from list_models. Read the evidence itself with read_evidence. '
        'Guidance: get_playbook("evidence").'
    ),
    input_schema={
        'type': 'object',
        'additionalProperties': False,
        'required': ['model_id'],
        'properties': {
            'model_id': uuid_schema('The model, from list_models.'),
            'which': {
                'type': 'string',
                'enum': ['draft', 'version'],
                'description': 'The working draft (default) or a saved version.',
            },
            'model_version_id': uuid_schema('The saved version, only with which "version".'),
        },
    },
    effect='read',
    stage='read_only',
    surfaces=SURFACES,
    owners=OWNERS,
    outcome='none',
    activity_label='Read: assumption evidence',
    handler=get_assumption_evidence,
    api_operations=(MODEL, REVISION, EVIDENCE),
)

TOOLS = (LIST_MODELS, GET_MODEL, LIST_MODEL_VERSIONS, GET_ASSUMPTION_EVIDENCE)
