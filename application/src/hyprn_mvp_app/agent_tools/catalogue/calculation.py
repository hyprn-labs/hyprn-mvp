"""Analyses and reference marks (ADR-0009, ADR-0010). The ``analyses`` owner keeps
analysis versions, evaluates the runs of a version against the study criteria of the brief
version it pins, and keeps reference marks. These tools read them and save analysis versions
and marks through the public API.

Configuration versions, criteria and outputs are named as the other tools name them: a
configuration by its saved name, a study criterion by its brief name, an output as
"<component>.<port>" of the analysis's model version. Bound outputs are resolved by name
against that exact model version; nothing is converted, inferred or filled in. A criterion
without a binding is unresolved in every run, never met. A saved analysis version never
changes; running or retrying its configurations adds runs without a new version.
"""

from ..projections import (
    CURSOR_SCHEMA,
    LIMIT_SCHEMA,
    UUID_SCHEMA,
    ModelView,
    cap,
    command_id,
    decode_cursor,
    encode_cursor,
    label,
    missing,
    quantity,
    read,
    ref,
    report,
    run_name,
    send,
    study_path,
    untrusted,
    uuid_schema,
)
from ..spec import SURFACES, ToolError, ToolSpec
from .configuration import PATH, Ports

LIST = ('GET', '/api/1/studies/{study_id}/analyses')
ONE = ('GET', '/api/1/studies/{study_id}/analyses/{calculation_id}')
VERSIONS = ('GET', '/api/1/studies/{study_id}/analyses/{calculation_id}/versions')
VERSION = ('GET', '/api/1/studies/{study_id}/analysis-versions/{version_id}')
RUNS = ('GET', '/api/1/studies/{study_id}/analysis-versions/{version_id}/runs')
CREATE = ('POST', '/api/1/studies/{study_id}/analyses')
SAVE = ('POST', '/api/1/studies/{study_id}/analyses/{calculation_id}/versions')
MARKS = ('GET', '/api/1/studies/{study_id}/reference-marks')
MARK = ('POST', '/api/1/studies/{study_id}/reference-marks')
BRIEF = ('GET', '/api/1/studies/{study_id}/brief')
BRIEF_VERSION = ('GET', '/api/1/studies/{study_id}/brief/versions/{version_id}')
REVISION = ('GET', '/api/1/studies/{study_id}/models/{model_id}/revisions/{revision_id}')
SUMMARIES = ('GET', '/api/1/studies/{study_id}/configuration-summaries')
OWNERS = ('calculations',)
WRITE_OWNERS = ('calculations', 'configuration', 'brief', 'modeling', 'store')
# Configuration names are read in pages of 100, at most this many pages per call.
NAME_PAGES = 10
RUN_LIMIT = {
    'type': 'integer',
    'minimum': 1,
    'maximum': 20,
    'description': 'Runs per page, 1 to 20 (default 10).',
}
EVALUATION_NOTE = (
    'Each run is evaluated against the study criteria of the pinned brief version through '
    "this analysis version's bindings. A met constraint is not validity, applicability or "
    'feasibility; an unresolved criterion is never met.'
)
PLAYBOOK = ' Guidance: get_playbook("configuration_and_runs").'
# The owner's closed evaluation reasons; anything else is reported as unknown, never echoed.
REASONS = frozenset(
    {
        'threshold_comparison',
        'measured',
        'criterion_not_bound',
        'run_not_recorded',
        'retained_record_invalid',
        'convergence_unresolved',
        'required_output_unavailable',
        'invalid_criterion_or_units',
    }
)


# ---- Owner reads and naming ----------------------------------------------------------


async def _version(ctx, version_id):
    path = study_path(ctx, 'analysis-versions', version_id)
    return (await read(ctx, path, next_step='Call list_analyses.'))['data']


async def _brief_version(ctx, version_id):
    path = study_path(ctx, 'brief', 'versions', version_id)
    return (await read(ctx, path, next_step='Call list_study_brief_versions.'))['data']


async def _model(ctx, model_id, version_id):
    path = study_path(ctx, 'models', model_id, 'revisions', version_id)
    return (await read(ctx, path, next_step='Call list_model_versions.'))['data']


async def _configuration_names(ctx, model_version_id):
    """Saved configuration names of one model version by configuration version id."""
    names, cursor = {}, None
    for _ in range(NAME_PAGES):
        params = {'limit': '100', 'model_revision_id': model_version_id}
        if cursor is not None:
            params['cursor'] = cursor
        body = await read(ctx, study_path(ctx, 'configuration-summaries'), params)
        names.update({c['configuration_revision_id']: c['name'] for c in body['data']})
        cursor = body.get('next_cursor')
        if cursor is None:
            break
    return names


async def _marked(ctx, model_id):
    """The configuration versions of a model that carry a reference mark."""
    data = (await read(ctx, study_path(ctx, 'reference-marks'), {'model_id': model_id}))['data']
    return {m['configuration_revision_id'] for m in data['items']}


def _version_label(version):
    number = version['version_number']
    return label(
        'calculation_version',
        version['calculation_version_id'],
        'Analysis version ' + str(number),
        number=number,
    )


def _brief_label(brief):
    number = brief['version_number']
    return label(
        'brief_version',
        brief['brief_version_id'],
        'Brief version ' + str(number),
        number=number,
    )


def _head(version):
    """The analysis and version of a saved analysis version, as listed."""
    content = version['content']
    previous = version['predecessor_version_id']
    return dict(
        calculation=ref('calculation', version['calculation_id'], content['name']),
        calculation_version=_version_label(version),
        previous_version=label('calculation_version', previous, 'Earlier analysis version')
        if previous
        else missing('first_version'),
        created_at=version['created_at'],
        model=ref('model', content['model_id'], None, missing='call_list_models'),
        model_version=ref(
            'model_version', content['model_revision_id'], None, missing='call_get_model'
        ),
        design=content['design']['kind'],
        configurations=len(content['configuration_revision_ids']),
        bound_criteria=len(content['criterion_bindings']),
    )


def _criteria(brief):
    return {c['criterion_id']: c for c in brief['content']['criteria']} if brief else {}


def _criterion_ref(criteria, criterion_id):
    criterion = criteria.get(criterion_id)
    return ref(
        'criterion',
        criterion_id,
        criterion['name'] if criterion else None,
        missing='criterion_not_in_brief_version',
    )


async def version_projection(ctx, version):
    """One analysis version in full: its configurations (named, reference marks shown),
    the brief version it pins and every study criterion of it with its bound output, or
    unbound."""
    content = version['content']
    projection = _head(version)
    projection['description'] = (
        untrusted('analysis description', text=content['description'])
        if content['description']
        else missing('no_description')
    )
    names = await _configuration_names(ctx, content['model_revision_id'])
    marked = await _marked(ctx, content['model_id'])
    projection['configurations'] = [
        dict(
            ref('configuration_version', c, names.get(c), missing='call_get_configuration'),
            reference=c in marked,
        )
        for c in content['configuration_revision_ids']
    ]
    design = content['design']
    if design['kind'] == 'sampled' or content.get('estimate_plan') is not None:
        view = ModelView(await _model(ctx, content['model_id'], content['model_revision_id']))
        if design['kind'] == 'sampled':
            projection['sampling'] = dict(
                method=design['method'],
                seed=design['seed'],
                provenance=untrusted('sampling provenance', text=design['rationale']),
                groups=[
                    dict(
                        configuration=ref(
                            'configuration_version',
                            g['reference_configuration_revision_id'],
                            names.get(g['reference_configuration_revision_id']),
                            missing='call_get_configuration',
                        ),
                        training_count=g['training_count'],
                        validation_count=g.get('validation_count', g.get('check_count')),
                        dimensions=[
                            dict(
                                quantity=view.quantity_ref(d['target']),
                                **{
                                    k: d[k]
                                    for k in ('lower', 'upper', 'units', 'step', 'covary_group')
                                },
                            )
                            for d in g['dimensions']
                        ],
                    )
                    for g in design['groups']
                ],
            )
        plan = content.get('estimate_plan')
        projection['estimate_plan'] = (
            None
            if plan is None
            else dict(
                tolerances=[
                    dict(
                        output=view.quantity_ref(t['target']),
                        absolute=t['absolute'],
                        relative=t['relative'],
                    )
                    for t in plan['tolerances']
                ]
            )
        )
    if content['brief_version_id'] is None:
        projection['brief_version'] = missing('no_criteria_bound')
        projection['criteria'] = missing('no_brief_version_pinned')
        return projection
    brief = await _brief_version(ctx, content['brief_version_id'])
    view = ModelView(await _model(ctx, content['model_id'], content['model_revision_id']))
    bound = {b['criterion_id']: b['output'] for b in content['criterion_bindings']}
    projection['brief_version'] = _brief_label(brief)
    projection['criteria'] = [
        dict(
            _criterion_ref(_criteria(brief), c['criterion_id']),
            criterion_kind=c['kind'],
            output=view.quantity_ref(bound[c['criterion_id']])
            if c['criterion_id'] in bound
            else missing('criterion_not_bound'),
        )
        for c in brief['content']['criteria']
    ]
    return projection


# ---- Reads ---------------------------------------------------------------------------


async def list_analyses(arguments, ctx):
    """One page of the study's analyses in creation order, each with its latest version."""
    params = {'limit': str(arguments.get('limit', 10))}
    if arguments.get('cursor') is not None:
        params['after'] = str(decode_cursor('list_analyses', arguments['cursor']))
    if arguments.get('model_version_id') is not None:
        params['model_revision_id'] = arguments['model_version_id']
    data = (await read(ctx, study_path(ctx, 'analyses'), params))['data']
    after = data['next_cursor']
    return cap(
        {
            'calculations': [_head(item['latest_version']) for item in data['items']],
            'next_cursor': None if after is None else encode_cursor('list_analyses', after),
        },
        [('calculations', 'calculations', 'list_analyses with a smaller limit')],
    )


LIST_CALCULATIONS = ToolSpec(
    name='list_analyses',
    title='List analyses',
    description=(
        "Returns one page of the study's analyses in the order they were created, each "
        'with its latest version: name, analysis id, version number and id, the model and '
        'model version, how its configurations were chosen and its numbers of configurations '
        'and bound criteria. An analysis is a set of saved configuration versions of one '
        'model version whose runs are evaluated against the study criteria. '
        'model_version_id: only analyses whose latest version uses it; limit: items per '
        'page (1 to 25, default 10); cursor: the next_cursor of the previous page, passed '
        'back unchanged. Read one with get_analysis.' + PLAYBOOK
    ),
    input_schema={
        'type': 'object',
        'additionalProperties': False,
        'properties': {
            'model_version_id': uuid_schema('Only analyses of this saved model version.'),
            'limit': LIMIT_SCHEMA,
            'cursor': CURSOR_SCHEMA,
        },
    },
    effect='read',
    stage='read_only',
    surfaces=SURFACES,
    owners=OWNERS,
    outcome='none',
    activity_label='Read: analyses',
    handler=list_analyses,
    api_operations=(LIST,),
)


async def get_analysis(arguments, ctx):
    """The latest version of an analysis, or one saved version, in full."""
    family, version_id = (
        arguments.get('calculation_id'),
        arguments.get('calculation_version_id'),
    )
    if (family is None) == (version_id is None):
        raise ToolError(
            'invalid_input',
            'Give exactly one of calculation_id and calculation_version_id.',
            fields=({'path': 'calculation_id', 'problem': 'give it or calculation_version_id'},),
            next_step='Call get_analysis with a calculation_id from list_analyses.',
        )
    if family is not None:
        path = study_path(ctx, 'analyses', family)
        version = (await read(ctx, path, next_step='Call list_analyses.'))['data']['latest_version']
    else:
        version = await _version(ctx, version_id)
    projection = await version_projection(ctx, version)
    if family is not None:
        # The latest version a new version must be based on (save_analysis_version).
        projection['revision_token'] = version['calculation_version_id']
    projection['next_step'] = 'Read its runs with get_analysis_runs.'
    return cap(
        projection,
        [
            ('description', 'description', 'the analysis page in HYPRN MVP'),
            ('configurations', 'configurations', 'the analysis page in HYPRN MVP'),
            ('criteria', 'criteria', 'the analysis page in HYPRN MVP'),
        ],
    )


GET_CALCULATION = ToolSpec(
    name='get_analysis',
    title='Read an analysis',
    description=(
        'Returns one analysis version: the name and description, the model version, '
        'the configuration versions it holds by name (reference configurations marked), the '
        'saved brief version it pins and each study criterion of that version with the '
        'output "Component.port" bound to measure it, or unbound (unresolved in every run). '
        'Give calculation_id for the latest version, which also returns its revision_token '
        'for save_analysis_version, or calculation_version_id for one saved version. A '
        'saved version never changes. Read its runs with get_analysis_runs.' + PLAYBOOK
    ),
    input_schema={
        'type': 'object',
        'additionalProperties': False,
        'properties': {
            'calculation_id': uuid_schema('The analysis, from list_analyses.'),
            'calculation_version_id': uuid_schema('One saved analysis version.'),
        },
    },
    effect='read',
    stage='read_only',
    surfaces=SURFACES,
    owners=('calculations', 'configuration', 'brief', 'modeling'),
    outcome='none',
    activity_label='Read: analysis',
    handler=get_analysis,
    api_operations=(ONE, VERSION, SUMMARIES, MARKS, BRIEF_VERSION, REVISION),
)


async def list_analysis_versions(arguments, ctx):
    """One page of an analysis's saved versions, newest first."""
    params = {'limit': str(arguments.get('limit', 10))}
    if arguments.get('cursor') is not None:
        params['before'] = str(decode_cursor('list_analysis_versions', arguments['cursor']))
    path = study_path(ctx, 'analyses', arguments['calculation_id'], 'versions')
    data = (await read(ctx, path, params, next_step='Call list_analyses.'))['data']
    after = data['next_cursor']
    return cap(
        {
            'versions': [_head(item) for item in data['items']],
            'next_cursor': None
            if after is None
            else encode_cursor('list_analysis_versions', after),
        },
        [('versions', 'versions', 'list_analysis_versions with a smaller limit')],
    )


LIST_CALCULATION_VERSIONS = ToolSpec(
    name='list_analysis_versions',
    title='List the versions of an analysis',
    description=(
        "Returns one page of an analysis's saved versions, newest first: version number "
        'and id, the earlier version it follows, when it was saved, the model version and its '
        'numbers of configurations and bound criteria. calculation_id: from '
        'list_analyses; limit: items per page (1 to 25, default 10); cursor: the '
        'next_cursor of the previous page, passed back unchanged. Read one with '
        'get_analysis and its calculation_version_id.' + PLAYBOOK
    ),
    input_schema={
        'type': 'object',
        'additionalProperties': False,
        'required': ['calculation_id'],
        'properties': {
            'calculation_id': uuid_schema('The analysis.'),
            'limit': LIMIT_SCHEMA,
            'cursor': CURSOR_SCHEMA,
        },
    },
    effect='read',
    stage='read_only',
    surfaces=SURFACES,
    owners=OWNERS,
    outcome='none',
    activity_label='Read: analysis versions',
    handler=list_analysis_versions,
    api_operations=(VERSIONS,),
)


def _evaluation(criteria, item):
    entry = dict(
        _criterion_ref(criteria, item['criterion_id']),
        criterion_kind=item['kind'],
        outcome=item['outcome'],
        reason=item['reason'] if item['reason'] in REASONS else 'unknown_reason',
    )
    # A value the evaluation could not read is unavailable with its reason, never a number.
    unavailable = entry['reason'] if item['value'] is None else None
    entry.update(quantity(None, item['value'], item['units'], unavailable=unavailable))
    return entry


async def get_analysis_runs(arguments, ctx):
    """One page of an analysis version's runs with their per-criterion evaluation, as the
    owner evaluates them from the retained records."""
    version = await _version(ctx, arguments['calculation_version_id'])
    content = version['content']
    params = {'limit': str(arguments.get('limit', 10))}
    if arguments.get('cursor') is not None:
        params['after'] = str(decode_cursor('get_analysis_runs', arguments['cursor']))
    path = study_path(ctx, 'analysis-versions', version['calculation_version_id'], 'runs')
    data = (await read(ctx, path, params))['data']
    brief = None
    if content['brief_version_id'] is not None:
        brief = await _brief_version(ctx, content['brief_version_id'])
    criteria = _criteria(brief)
    names = await _configuration_names(ctx, content['model_revision_id'])
    runs = []
    for item in data['items']:
        name = names.get(item['configuration_revision_id'])
        runs.append(
            dict(
                ref('run', item['run_id'], run_name(name), missing='call_list_runs'),
                configuration=ref(
                    'configuration_version',
                    item['configuration_revision_id'],
                    name,
                    missing='call_get_configuration',
                ),
                record_state=item['record_state'],
                evaluations=[_evaluation(criteria, e) for e in item['evaluations']],
            )
        )
    after = data['next_cursor']
    return cap(
        {
            'calculation': ref('calculation', version['calculation_id'], content['name']),
            'calculation_version': _version_label(version),
            'brief_version': _brief_label(brief) if brief else missing('no_brief_version_pinned'),
            'note': EVALUATION_NOTE,
            'runs': runs,
            'next_cursor': None if after is None else encode_cursor('get_analysis_runs', after),
        },
        [('runs', 'runs', 'get_analysis_runs with a smaller limit')],
    )


GET_CALCULATION_RUNS = ToolSpec(
    name='get_analysis_runs',
    title='Read the runs of an analysis',
    description=(
        "Returns one page of an analysis version's runs (the runs of its configurations, "
        'in the order they were submitted), each with its configuration, its record state '
        'and its evaluation against every study criterion of the pinned brief version: a '
        'constraint met, not_met or unresolved, an objective measured or unresolved, with '
        'the reason and the value with its unit, or the reason it is unavailable (never 0). '
        'An unbound criterion and a run not yet recorded are unresolved, never met. A met '
        'constraint is not validity. calculation_version_id: from get_analysis; limit: '
        'runs per page (1 to 20, default 10); cursor: the next_cursor of the previous page, '
        'passed back unchanged. Read outputs with get_run_results.' + PLAYBOOK
    ),
    input_schema={
        'type': 'object',
        'additionalProperties': False,
        'required': ['calculation_version_id'],
        'properties': {
            'calculation_version_id': uuid_schema('The saved analysis version.'),
            'limit': RUN_LIMIT,
            'cursor': CURSOR_SCHEMA,
        },
    },
    effect='read',
    stage='read_only',
    surfaces=SURFACES,
    owners=('calculations', 'configuration', 'brief', 'history'),
    outcome='none',
    activity_label='Read: analysis runs',
    handler=get_analysis_runs,
    api_operations=(VERSION, RUNS, BRIEF_VERSION, SUMMARIES),
)


async def list_reference_marks(arguments, ctx):
    """The configuration versions marked as references, optionally of one model."""
    params = {}
    if arguments.get('model_id') is not None:
        params['model_id'] = arguments['model_id']
    data = (await read(ctx, study_path(ctx, 'reference-marks'), params))['data']
    names = {}
    for model_version in sorted({m['model_revision_id'] for m in data['items']})[:20]:
        names.update(await _configuration_names(ctx, model_version))
    marks = [
        dict(
            ref(
                'configuration_version',
                m['configuration_revision_id'],
                names.get(m['configuration_revision_id']),
                missing='call_get_configuration',
                configuration_id=m['configuration_id'],
            ),
            model=ref('model', m['model_id'], None, missing='call_list_models'),
            model_version=ref(
                'model_version', m['model_revision_id'], None, missing='call_get_model'
            ),
            marked_at=m['marked_at'],
        )
        for m in data['items']
    ]
    return cap(
        {'reference_configurations': marks},
        [('reference_configurations', 'reference marks', 'list_reference_marks with model_id')],
    )


LIST_REFERENCE_MARKS = ToolSpec(
    name='list_reference_marks',
    title='List reference configurations',
    description=(
        'Returns the configuration versions marked as reference configurations (baselines '
        'for their model), each with its name, model and model version and when it was '
        'marked. model_id: only the marks of this model. A mark never changes or pins the '
        'configuration.' + PLAYBOOK
    ),
    input_schema={
        'type': 'object',
        'additionalProperties': False,
        'properties': {'model_id': uuid_schema('Only the marks of this model.')},
    },
    effect='read',
    stage='read_only',
    surfaces=SURFACES,
    owners=('calculations', 'configuration'),
    outcome='none',
    activity_label='Read: reference configurations',
    handler=list_reference_marks,
    api_operations=(MARKS, SUMMARIES),
)


# ---- Writes --------------------------------------------------------------------------

BINDING = {
    'type': 'object',
    'additionalProperties': False,
    'required': ['criterion_id', 'output'],
    'properties': {
        'criterion_id': uuid_schema(
            'A study criterion of the brief version, from get_study_brief.'
        ),
        'output': dict(
            PATH,
            description='The output "<component>.<port>" of the model version measuring it.',
        ),
    },
}
CONTENT_PROPERTIES = {
    'name': {
        'type': 'string',
        'minLength': 1,
        'maxLength': 256,
        'description': "Reviewer-readable, e.g. 'Liquid hydrogen around the 9,000 km baseline'.",
    },
    'description': {
        'type': 'string',
        'maxLength': 4096,
        'description': (
            'Analysis details: why these configurations are examined, sampling/validation plan, '
            'accuracy targets and numerical-check rationale. Exact settings and results '
            'belong in structured design/assessment records. Keep physical equations and '
            'model calculation logic in the model explanation; omit redundant prose.'
        ),
    },
    'model_version_id': uuid_schema('The saved model version every configuration uses.'),
    'configuration_version_ids': {
        'type': 'array',
        'minItems': 1,
        'maxItems': 1000,
        'uniqueItems': True,
        'items': dict(UUID_SCHEMA),
        'description': 'The saved configuration versions of that model version, hand-picked.',
    },
    'brief_version_id': uuid_schema(
        'The saved brief version whose criteria are bound (default: the latest saved one).'
    ),
    'criterion_bindings': {
        'type': 'array',
        'maxItems': 64,
        'items': BINDING,
        'description': 'Each study criterion with the output that measures it; at most once.',
    },
}
CONTENT_DESCRIPTION = (
    'name and description: reviewer-readable. model_version_id: the saved model version of '
    'every configuration. configuration_version_ids: the saved configuration versions in the '
    'set, all of that model version. criterion_bindings: {criterion_id (a criterion of the '
    'brief version, from get_study_brief), output "<component>.<port>"}; the output unit must '
    'equal the criterion unit exactly (never converted). A criterion left unbound is '
    'unresolved in every run. brief_version_id: the saved brief version whose criteria are '
    'bound; when omitted, the latest saved brief version, or none when no version is saved '
    '(then nothing can be bound). '
)
FIELDS = {
    'configuration_revision_ids': 'configuration_version_ids',
    'model_revision_id': 'model_version_id',
    'criterion_bindings': 'criterion_bindings',
    'brief_version_id': 'brief_version_id',
    'name': 'name',
    'description': 'description',
}


def calculation_field(pointer):
    """The tool input path of a field of the public analysis command the API refused."""
    parts = str(pointer).split('/')[1:]
    if parts and parts[0] == 'content':
        parts = parts[1:]
    if not parts or parts[0] not in FIELDS:
        return 'model_id' if parts and parts[0] == 'model_id' else '(input)'
    index = f'[{parts[1]}]' if len(parts) > 1 and parts[1].isdecimal() else ''
    return FIELDS[parts[0]] + index


async def _latest_brief(ctx):
    state = (await read(ctx, study_path(ctx, 'brief')))['data']
    return state.get('latest_version')


async def _content(ctx, arguments, model_id):
    """The public analysis content of the tool input: every bound output resolved by name
    against the exact model version, the brief version given or the latest saved one."""
    version_id = arguments['model_version_id']
    ports = Ports(await _model(ctx, model_id, version_id))
    bindings = [
        dict(
            criterion_id=item['criterion_id'],
            output=ports.target(item['output'], f'criterion_bindings[{n}].output', 'output'),
        )
        for n, item in enumerate(arguments.get('criterion_bindings', ()))
    ]
    brief_version = arguments.get('brief_version_id')
    if brief_version is None:
        latest = await _latest_brief(ctx)
        brief_version = latest['brief_version_id'] if latest else None
    if brief_version is None and bindings:
        raise ToolError(
            'invalid_input',
            'Criteria are bound against a saved brief version, and the study has none.',
            fields=({'path': 'criterion_bindings', 'problem': 'needs a saved brief version'},),
            next_step='Save the brief with save_study_brief_version, then bind its criteria.',
        )
    return dict(
        schema_version='4',
        estimate_plan=None,
        name=arguments['name'],
        description=arguments.get('description', ''),
        model_id=model_id,
        model_revision_id=version_id,
        configuration_revision_ids=list(arguments['configuration_version_ids']),
        design=dict(kind='hand_picked'),
        brief_version_id=brief_version,
        criterion_bindings=bindings,
    )


async def _saved(ctx, version):
    content = version['content']
    report(
        ctx,
        'calculation_version',
        version['calculation_id'],
        version_id=version['calculation_version_id'],
        name=content['name'],
        number=version['version_number'],
    )
    projection = _head(version)
    projection['brief_version'] = (
        label('brief_version', content['brief_version_id'], 'Saved brief version')
        if content['brief_version_id']
        else missing('no_brief_version_pinned')
    )
    projection['revision_token'] = version['calculation_version_id']
    projection['next_step'] = (
        'Submit runs for configurations without one (submit_runs), then read the evaluations '
        'with get_analysis_runs.'
    )
    return projection


async def create_analysis(arguments, ctx):
    """Create an analysis and its first version."""
    content = await _content(ctx, arguments, arguments['model_id'])
    body = dict(command_id=command_id(ctx), content=content)
    version = (
        await send(
            ctx,
            'POST',
            study_path(ctx, 'analyses'),
            body,
            tool='create_analysis',
            conflict_step='Call create_analysis again; a record it names changed.',
            field_map=calculation_field,
        )
    )['data']
    return await _saved(ctx, version)


CREATE_CALCULATION = ToolSpec(
    name='create_analysis',
    title='Create an analysis',
    description=(
        'Creates a distinct investigation and its first version: a hand-picked set of saved '
        'configuration versions of one model version, with the study criteria bound to the '
        'outputs that measure them, so their runs are evaluated against the criteria. '
        'model_id: the model. ' + CONTENT_DESCRIPTION + 'Returns the analysis and version '
        'ids and the revision_token for the next version. A saved version never changes.' + PLAYBOOK
    ),
    input_schema={
        'type': 'object',
        'additionalProperties': False,
        'required': ['name', 'model_id', 'model_version_id', 'configuration_version_ids'],
        'properties': dict(CONTENT_PROPERTIES, model_id=uuid_schema('The model.')),
    },
    effect='record',
    stage='runs',
    surfaces=SURFACES,
    owners=WRITE_OWNERS,
    outcome='receipt:calculation_create',
    activity_label='Saved: analysis',
    handler=create_analysis,
    api_operations=(BRIEF, REVISION, CREATE),
    attribution_kind='calculation_version',
)


async def save_analysis_version(arguments, ctx):
    """Save the next version of an analysis from the latest one the agent read: the fields
    given replace the latest version's, the others are kept."""
    family = arguments['calculation_id']
    path = study_path(ctx, 'analyses', family)
    latest = (await read(ctx, path, next_step='Call list_analyses.'))['data']['latest_version']
    if latest['calculation_version_id'] != arguments['expected_revision']:
        raise ToolError(
            'conflict',
            'The analysis has a newer version than the one you read; nothing was saved.',
            fields=({'path': 'expected_revision', 'problem': 'is not the latest version'},),
            next_step='Call get_analysis, apply your change to what it returns and pass its '
            'revision_token as expected_revision.',
        )
    kept = latest['content']
    merged = dict(
        name=kept['name'],
        description=kept['description'],
        model_version_id=kept['model_revision_id'],
        configuration_version_ids=kept['configuration_revision_ids'],
    )
    if kept['brief_version_id'] is not None:
        merged['brief_version_id'] = kept['brief_version_id']
    if 'criterion_bindings' not in arguments and kept['brief_version_id'] is not None:
        if arguments.get('brief_version_id', kept['brief_version_id']) != kept['brief_version_id']:
            raise ToolError(
                'invalid_input',
                'A new brief version needs its criteria bound again.',
                fields=(
                    {'path': 'criterion_bindings', 'problem': 'give it with brief_version_id'},
                ),
                next_step='Call get_study_brief for that version and give criterion_bindings.',
            )
        view = ModelView(await _model(ctx, kept['model_id'], kept['model_revision_id']))
        merged['criterion_bindings'] = [
            dict(criterion_id=b['criterion_id'], output=view.path(b['output']))
            for b in kept['criterion_bindings']
        ]
    merged.update({k: v for k, v in arguments.items() if k in CONTENT_PROPERTIES})
    if any(b['output'] is None for b in merged.get('criterion_bindings', ())):
        raise ToolError('internal', 'HYPRN MVP returned a binding it cannot name.')
    content = await _content(ctx, merged, kept['model_id'])
    if (
        content['model_revision_id'] == kept['model_revision_id']
        and content['configuration_revision_ids'] == kept['configuration_revision_ids']
    ):
        content['design'] = kept['design']
        content['schema_version'] = kept['schema_version']
        if kept['schema_version'] == '4':
            content['estimate_plan'] = kept['estimate_plan']
        else:
            content.pop('estimate_plan', None)
    body = dict(
        command_id=command_id(ctx),
        expected_version_id=arguments['expected_revision'],
        content=content,
    )
    version = (
        await send(
            ctx,
            'POST',
            study_path(ctx, 'analyses', family, 'versions'),
            body,
            tool='save_analysis_version',
            conflict_step='Call get_analysis for the latest version, then save again with its '
            'revision_token as expected_revision.',
            field_map=calculation_field,
        )
    )['data']
    return await _saved(ctx, version)


SAVE_CALCULATION_VERSION = ToolSpec(
    name='save_analysis_version',
    title='Save a new analysis version',
    description=(
        'Revises the same investigation, for example to add or remove '
        'configurations or to bind criteria; earlier versions never change, and running '
        'configurations needs no new version. Use create_analysis for a complementary investigation. calculation_id: the analysis; '
        "expected_revision: the revision_token of its latest version you read, so a person's "
        'newer version is never overwritten. Give only the fields you change; the others '
        'are kept from the latest version (criterion_bindings, when given, replaces the whole '
        'list, and a different brief_version_id needs it). The model stays the same. '
        + CONTENT_DESCRIPTION
        + 'Returns the new version id and its revision_token.'
        + PLAYBOOK
    ),
    input_schema={
        'type': 'object',
        'additionalProperties': False,
        'required': ['calculation_id', 'expected_revision'],
        'properties': dict(
            CONTENT_PROPERTIES,
            calculation_id=uuid_schema('The analysis.'),
            expected_revision=uuid_schema(
                'The revision_token (latest analysis version id) from get_analysis.'
            ),
        ),
    },
    effect='record',
    stage='runs',
    surfaces=SURFACES,
    owners=WRITE_OWNERS,
    outcome='receipt:calculation_version',
    activity_label='Saved: analysis version',
    handler=save_analysis_version,
    api_operations=(ONE, BRIEF, REVISION, SAVE),
    attribution_kind='calculation_version',
)


async def _mark(arguments, ctx, action, tool):
    body = dict(
        command_id=command_id(ctx),
        configuration_revision_id=arguments['configuration_version_id'],
        action=action,
    )
    state = (
        await send(
            ctx,
            'POST',
            study_path(ctx, 'reference-marks'),
            body,
            tool=tool,
            conflict_step='Call ' + tool + ' again.',
            field_map=lambda _: 'configuration_version_id',
        )
    )['data']
    report(ctx, 'reference_mark', state['configuration_revision_id'])
    mark = state['mark']
    return {
        'configuration_version': ref(
            'configuration_version',
            state['configuration_revision_id'],
            None,
            missing='call_get_configuration',
        ),
        'reference': mark is not None,
        'marked_at': mark['marked_at'] if mark else missing('not_marked'),
    }


async def set_reference_mark(arguments, ctx):
    """Mark a configuration version as a reference configuration of its model."""
    return await _mark(arguments, ctx, 'set', 'set_reference_mark')


async def clear_reference_mark(arguments, ctx):
    """Remove the reference mark of a configuration version."""
    return await _mark(arguments, ctx, 'clear', 'clear_reference_mark')


MARK_INPUT = {
    'type': 'object',
    'additionalProperties': False,
    'required': ['configuration_version_id'],
    'properties': {
        'configuration_version_id': uuid_schema('The saved configuration version.'),
    },
}

SET_REFERENCE_MARK = ToolSpec(
    name='set_reference_mark',
    title='Mark a reference configuration',
    description=(
        'Marks a saved configuration version as a reference configuration: a baseline for '
        'its model, typically the centre an analysis is built around. A model may have '
        'several. The mark never changes or pins the configuration; marking a version that '
        'is already marked changes nothing. configuration_version_id: from '
        'list_configurations.' + PLAYBOOK
    ),
    input_schema=MARK_INPUT,
    effect='record',
    stage='runs',
    surfaces=SURFACES,
    owners=('calculations', 'configuration', 'store'),
    outcome='receipt:reference_mark',
    activity_label='Marked: reference configuration',
    handler=set_reference_mark,
    api_operations=(MARK,),
    attribution_kind='reference_mark',
)

CLEAR_REFERENCE_MARK = ToolSpec(
    name='clear_reference_mark',
    title='Remove a reference mark',
    description=(
        'Removes the reference mark of a saved configuration version. The configuration '
        'version, its runs and every analysis that holds it stay unchanged; clearing an '
        'unmarked version changes nothing. configuration_version_id: from '
        'list_reference_marks.' + PLAYBOOK
    ),
    input_schema=MARK_INPUT,
    effect='record',
    stage='runs',
    surfaces=SURFACES,
    owners=('calculations', 'configuration', 'store'),
    outcome='receipt:reference_mark',
    activity_label='Cleared: reference mark',
    handler=clear_reference_mark,
    api_operations=(MARK,),
    attribution_kind='reference_mark',
)

TOOLS = (
    LIST_CALCULATIONS,
    GET_CALCULATION,
    LIST_CALCULATION_VERSIONS,
    GET_CALCULATION_RUNS,
    LIST_REFERENCE_MARKS,
    CREATE_CALCULATION,
    SAVE_CALCULATION_VERSION,
    SET_REFERENCE_MARK,
    CLEAR_REFERENCE_MARK,
)
