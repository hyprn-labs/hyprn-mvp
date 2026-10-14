"""Configuration: the read tools (tooling spec section 4.6). Saved configuration versions are
owned by ``configuration`` and the result-linked input sources by ``result_bindings``; these
tools only read them. A saved configuration version never changes."""

from ..projections import (
    CURSOR_SCHEMA,
    LIMIT_SCHEMA,
    ModelView,
    cap,
    clip,
    configuration_ref,
    decode_cursor,
    encode_cursor,
    label,
    missing,
    quantity,
    read,
    ref,
    study_path,
    untrusted,
    uuid_schema,
)
from ..spec import SURFACES, ToolSpec

LIST = ('GET', '/api/1/studies/{study_id}/configurations')
ONE = ('GET', '/api/1/studies/{study_id}/configurations/{revision_id}')
SOURCES = ('GET', '/api/1/studies/{study_id}/result-sources')
CONTEXT_CHARS = 600


def approach_case(frozen):
    """The approach version and case a configuration implements, named from the approach
    closure frozen with it."""
    binding = frozen['configuration'].get('approach_binding')
    if binding is None:
        return missing('not_linked_to_an_approach')
    closure = frozen.get('approach_closure') or {}
    versions = {v['approach_version_id']: v for v in closure.get('approach_versions', ())}
    version = versions.get(binding['approach_version_id'])
    number = version['version_number'] if version else None
    value = {
        'approach_version': label(
            'approach_version',
            binding['approach_version_id'],
            'Approach version ' + str(number) if number else 'Saved approach version',
            number=number,
        )
    }
    case_id = binding.get('case_id')
    if case_id is None:
        value['case'] = missing('no_case')
    else:
        cases = {
            c['case_id']: c['title'] for c in (version or {}).get('content', {}).get('cases', ())
        }
        value['case'] = ref('approach_case', case_id, cases.get(case_id), missing='case_not_named')
    return value


def model_refs(configuration):
    return {
        'model': ref('model', configuration['model_id'], None, missing='call_list_models'),
        'model_version': ref(
            'model_version', configuration['model_revision_id'], None, missing='call_get_model'
        ),
    }


async def list_configurations(arguments, ctx):
    """One page of saved configuration versions in the order they were saved."""
    limit = arguments.get('limit', 10)
    params = {'limit': str(limit)}
    if arguments.get('cursor') is not None:
        params['cursor'] = decode_cursor('list_configurations', arguments['cursor'])
    body = await read(ctx, study_path(ctx, 'configurations'), params)
    items = [
        dict(
            configuration_ref(frozen),
            **model_refs(frozen['configuration']),
            approach=approach_case(frozen),
            inputs=len(frozen['configuration']['inputs']),
            criteria=len(frozen['configuration']['criteria']),
        )
        for frozen in body['data']
    ]
    after = body.get('next_cursor')
    return cap(
        {
            'configurations': items,
            'next_cursor': None if after is None else encode_cursor('list_configurations', after),
        },
        [('configurations', 'configurations', 'list_configurations with a smaller limit')],
    )


LIST_CONFIGURATIONS = ToolSpec(
    name='list_configurations',
    title='List saved configurations',
    description=(
        'Returns one page of the saved configuration versions in the order they were saved: '
        'name, configuration version id and configuration id, the model and model version '
        'it pins, the approach case it implements and its numbers of inputs and criteria. '
        'limit: items per page (1 to 25, default 10); cursor: the next_cursor of the previous '
        'page, passed back unchanged. Read one with get_configuration; see its runs with '
        'list_runs. Guidance: get_playbook("configuration_and_runs").'
    ),
    input_schema={
        'type': 'object',
        'additionalProperties': False,
        'properties': {'limit': LIMIT_SCHEMA, 'cursor': CURSOR_SCHEMA},
    },
    effect='read',
    stage='read_only',
    surfaces=SURFACES,
    owners=('configuration',),
    outcome='none',
    activity_label='Read: configurations',
    handler=list_configurations,
    api_operations=(LIST,),
)


def _evidence(ids):
    return [ref('evidence_version', e, None, missing='call_read_evidence') for e in ids]


def _input(view, item):
    target = item.get('target', {})
    provenance = item.get('provenance') or {}
    entry = quantity(
        untrusted(
            'configuration input',
            text={'quantity': view.path(target), 'source': provenance.get('statement')},
        ),
        item.get('value'),
        view.unit(target, item.get('units')),
    )
    entry['port'] = view.quantity_ref(target)
    entry['source_kind'] = provenance.get('kind')
    entry['evidence'] = _evidence(provenance.get('evidence_version_ids', ()))
    binding = item.get('result_binding')
    if binding:
        labels = binding['labels']
        entry['from_run'] = dict(
            ref('run', binding['source_run_id'], labels['run_name']),
            output=untrusted(
                'source output', text=labels['instance_name'] + '.' + labels['output_name']
            ),
            original=quantity(None, binding['original_value'], binding['original_units']),
        )
    return entry


def _criterion(view, item):
    entry = ref(
        'criterion', item['criterion_id'], view.path(item['target']), missing='port_not_in_model'
    )
    entry['operator'] = item['operator']
    entry['threshold'] = quantity(None, item['threshold'], view.unit(item['target'], item['units']))
    tolerance = {
        key: item[key] for key in ('absolute_tolerance', 'relative_tolerance') if key in item
    }
    entry['tolerance'] = tolerance or missing('not_declared')
    entry['evidence'] = _evidence(item.get('evidence_version_ids', ()))
    return entry


async def get_configuration(arguments, ctx):
    """One saved configuration version: inputs as quantity, value, unit and source; criteria;
    assumptions; the approach case; an excerpt of the study context copied into it."""
    revision_id = arguments['configuration_version_id']
    path = study_path(ctx, 'configurations', revision_id)
    frozen = (await read(ctx, path, next_step='Call list_configurations.'))['data']
    configuration = frozen['configuration']
    view = ModelView(frozen['model_snapshot'])
    context = configuration.get('context_snapshot') or {}
    description, cut_description = clip(context.get('description', ''), CONTEXT_CHARS)
    boundary, cut_boundary = clip(context.get('boundary', ''), CONTEXT_CHARS)
    parent = configuration.get('parent_revision_id')
    projection = dict(
        configuration_ref(frozen),
        **model_refs(configuration),
        previous_version=ref(
            'configuration_version', parent, None, missing='call_get_configuration'
        )
        if parent
        else missing('first_version'),
        approach=approach_case(frozen),
        mode=configuration['numerical']['mode'],
        inputs=[_input(view, item) for item in configuration['inputs']],
        criteria=[_criterion(view, item) for item in configuration['criteria']],
        assumptions=[
            dict(
                ref('configuration_assumption', a['assumption_id'], a['statement']),
                evidence=_evidence(link['evidence_version_id'] for link in a['evidence_links']),
            )
            for a in configuration.get('assumptions', ())
        ],
        study_context=untrusted(
            'study context copied into the configuration',
            text={'description': description, 'boundary': boundary},
        ),
        study_context_truncated=cut_description or cut_boundary,
    )
    return cap(
        projection,
        [
            ('study_context', 'study context excerpt', 'get_study_overview'),
            ('assumptions', 'configuration assumptions', 'the configuration page in HYPRN MVP'),
            ('criteria', 'criteria', 'the configuration page in HYPRN MVP'),
            ('inputs', 'inputs', 'the configuration page in HYPRN MVP'),
        ],
    )


GET_CONFIGURATION = ToolSpec(
    name='get_configuration',
    title='Read a saved configuration',
    description=(
        'Returns one saved configuration version: name, ids, the model version it pins, the '
        'approach case it implements, every input as quantity "Component.port", value, unit '
        'and source (with the run it was taken from when result-linked), the criteria with '
        'operator, threshold, unit and tolerance, the configuration assumptions and an '
        'excerpt of the study context copied into it when it was saved. Values keep full '
        'precision; units are shown as saved, never converted. configuration_version_id: the '
        'version, from list_configurations. A saved version never changes. '
        'Guidance: get_playbook("configuration_and_runs").'
    ),
    input_schema={
        'type': 'object',
        'additionalProperties': False,
        'required': ['configuration_version_id'],
        'properties': {
            'configuration_version_id': uuid_schema('The saved configuration version.'),
        },
    },
    effect='read',
    stage='read_only',
    surfaces=SURFACES,
    owners=('configuration',),
    outcome='none',
    activity_label='Read: configuration',
    handler=get_configuration,
    api_operations=(ONE,),
)


async def list_result_sources(arguments, ctx):
    """One page of run outputs usable as result-linked inputs, as their owner lists them."""
    limit = arguments.get('limit', 10)
    params = {'limit': str(limit)}
    if arguments.get('cursor') is not None:
        params['cursor'] = decode_cursor('list_result_sources', arguments['cursor'])
    data = (await read(ctx, study_path(ctx, 'result-sources'), params))['data']
    items = []
    for item in data['items']:
        labels, outcomes = item['labels'], item['outcomes']
        output = item['source_output']
        items.append(
            dict(
                quantity(
                    untrusted(
                        'source output', text=labels['instance_name'] + '.' + labels['output_name']
                    ),
                    item['value'],
                    item['units'],
                ),
                run=ref('run', item['source_run_id'], labels['run_name']),
                output=ref(
                    'port',
                    output['port_id'],
                    labels['instance_name'] + '.' + labels['output_name'],
                    component_id=output['instance_id'],
                ),
                model_version=ref(
                    'model_version',
                    labels['model_revision_id'],
                    labels['model_name'],
                    missing='model_name_not_recorded',
                ),
                execution=outcomes['execution']['state'],
                criteria=[c['outcome'] for c in outcomes['criteria']],
            )
        )
    after = data['next_cursor']
    return cap(
        {
            'sources': items,
            'next_cursor': None if after is None else encode_cursor('list_result_sources', after),
        },
        [('sources', 'result sources', 'list_result_sources with a smaller limit')],
    )


LIST_RESULT_SOURCES = ToolSpec(
    name='list_result_sources',
    title='List run outputs usable as inputs',
    description=(
        'Returns one page of recorded run outputs that a configuration can take as a '
        'result-linked input: the output "Component.port" with its value and unit, the run '
        "and model version it comes from, and the run's execution and criterion "
        'outcomes as recorded. limit: items per page (1 to 25, default 10); '
        'cursor: the next_cursor of the previous page, passed back unchanged. Values are the '
        'recorded ones at full precision, never recomputed. '
        'Guidance: get_playbook("configuration_and_runs").'
    ),
    input_schema={
        'type': 'object',
        'additionalProperties': False,
        'properties': {'limit': LIMIT_SCHEMA, 'cursor': CURSOR_SCHEMA},
    },
    effect='read',
    stage='read_only',
    surfaces=SURFACES,
    owners=('result_bindings',),
    outcome='none',
    activity_label='Read: result sources',
    handler=list_result_sources,
    api_operations=(SOURCES,),
)

TOOLS = (LIST_CONFIGURATIONS, GET_CONFIGURATION, LIST_RESULT_SOURCES)
