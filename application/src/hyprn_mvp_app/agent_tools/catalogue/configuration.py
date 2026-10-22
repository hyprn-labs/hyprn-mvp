"""Configuration (tooling spec section 4.6). Saved configuration versions are owned by
``configuration`` and the result-linked input sources by ``result_bindings``. These tools read
them, and preview and save configurations: inputs are named by port against the exact model
version, every input states its typed source, which the tool renders into the provenance
statement, and the preview digest stays inside the tool. A saved configuration version never
changes. New configurations carry no criteria: study criteria are evaluated in analyses.
Retained versions 1 to 4 may still carry criteria and an approach binding, and are read as
saved."""

from ...contracts import uid
from ..projections import (
    CURSOR_SCHEMA,
    LIMIT_SCHEMA,
    UUID_SCHEMA,
    ModelView,
    cap,
    clip,
    command_id,
    configuration_criteria,
    configuration_ref,
    decode_cursor,
    encode_cursor,
    label,
    missing,
    quantity,
    read,
    ref,
    report,
    send,
    study_path,
    untrusted,
    uuid_schema,
)
from ..spec import SURFACES, ToolError, ToolSpec

LIST = ('GET', '/api/1/studies/{study_id}/configurations')
ONE = ('GET', '/api/1/studies/{study_id}/configurations/{revision_id}')
SOURCES = ('GET', '/api/1/studies/{study_id}/result-sources')
CONTEXT_CHARS = 600



def criteria_count(configuration):
    """The number of criteria a retained configuration carries; a version without criteria
    says that its runs are evaluated in analyses."""
    criteria = configuration_criteria(configuration)
    return missing('evaluated_in_calculations') if criteria is None else len(criteria)


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

            inputs=len(frozen['configuration']['inputs']),
            criteria=criteria_count(frozen['configuration']),
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
        'it pins and its number of inputs. Configurations saved before criteria moved to the '
        'study brief also show the approach version they implement and their number of '
        'criteria; newer ones show criteria as evaluated in analyses. '
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
    assumptions; the approach version; an excerpt of the study context copied into it."""
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

        mode=configuration['numerical']['mode'],
        inputs=[_input(view, item) for item in configuration['inputs']],
        criteria=[_criterion(view, item) for item in configuration_criteria(configuration)]
        if configuration_criteria(configuration) is not None
        else missing('evaluated_in_calculations'),
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
        'Returns one saved configuration version: name, ids, the model version it pins, every '
        'input as quantity "Component.port", value, unit and source (with the run it was taken '
        'from when result-linked), the configuration assumptions and an excerpt of the study '
        'context copied into it when it was saved. Study criteria are evaluated in '
        'calculations, not in configurations; a version saved before that shows its own '
        'criteria and approach version as saved. Values keep full '
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
                criteria=[c['outcome'] for c in outcomes['criteria']]
                if 'criteria' in outcomes
                else missing('evaluated_in_calculations'),
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

# ---- Writes: preview and save ----------------------------------------------------------

STUDY = ('GET', '/api/1/studies/{study_id}')
REVISION = ('GET', '/api/1/studies/{study_id}/models/{model_id}/revisions/{revision_id}')
EVIDENCE = ('GET', '/api/1/studies/{study_id}/evidence/{evidence_version_id}')
PREVIEW = ('POST', '/api/1/studies/{study_id}/configurations/preview')
COMMIT = ('POST', '/api/1/studies/{study_id}/configurations')
AUTHORITIES = ('brief', 'source', 'property', 'constant', 'judgement', 'numerical')
LABELS = {
    'brief': 'Study brief',
    'property': 'Material or fluid property',
    'constant': 'Physical constant',
    'numerical': 'Numerical choice',
}
# The one numerical setting this tool writes, stated in its description: a deterministic
# evaluation without solvers, derivatives, optimization or uncertainty.
DETERMINISTIC = dict(
    mode='deterministic',
    initialization=[],
    solvers=[],
    derivatives=dict(method='none', form=None, check=None),
    design_variables=[],
    objectives=[],
    constraints=[],
    optimizer=None,
    uncertainty=None,
)
PATH = {
    'type': 'string',
    'minLength': 3,
    'maxLength': 300,
    'description': 'A port as "<component name>.<port name>" of the chosen model version.',
}
EVIDENCE_IDS = {'type': 'array', 'maxItems': 64, 'uniqueItems': True, 'items': dict(UUID_SCHEMA)}
SOURCE = {
    'type': 'object',
    'additionalProperties': False,
    'required': ['authority'],
    'properties': {
        'authority': {
            'type': 'string',
            'enum': list(AUTHORITIES),
            'description': (
                'brief: the study brief; source: a published source (evidence_version_ids '
                'required, locator recommended); property, constant, numerical; judgement: '
                'an engineering judgement (note required).'
            ),
        },
        'evidence_version_ids': dict(EVIDENCE_IDS, description='Evidence versions of the source.'),
        'locator': {
            'type': 'string',
            'minLength': 1,
            'maxLength': 80,
            'description': 'Where in the source: "Table 3", "p. 5, Eq. 12".',
        },
        'note': {
            'type': 'string',
            'minLength': 1,
            'maxLength': 200,
            'description': 'Only when the value deviates from its source, or the judgement.',
        },
    },
    'description': 'Where the value comes from; rendered into the input provenance statement.',
}
INPUT = {
    'type': 'object',
    'additionalProperties': False,
    'required': ['quantity'],
    'properties': {
        'quantity': PATH,
        'value': {'type': 'number', 'description': 'The explicit value (never left to a default).'},
        'unit': {
            'type': 'string',
            'minLength': 1,
            'maxLength': 64,
            'description': 'The unit of value, from the unit vocabulary, or "dimensionless".',
        },
        'from_run': uuid_schema(
            'Instead of value and unit: a run whose output supplies the value.'
        ),
        'output': dict(
            PATH, description='With from_run: the output "<component>.<port>" of that run.'
        ),
        'source': SOURCE,
    },
}
ASSUMPTION = {
    'type': 'object',
    'additionalProperties': False,
    'required': ['statement'],
    'properties': {
        'statement': {'type': 'string', 'minLength': 1, 'maxLength': 4096},
        'evidence': {
            'type': 'array',
            'maxItems': 64,
            'items': {
                'type': 'object',
                'additionalProperties': False,
                'required': ['evidence_version_id', 'relation'],
                'properties': {
                    'evidence_version_id': dict(UUID_SCHEMA),
                    'relation': {'type': 'string', 'enum': ['supports', 'challenges', 'context']},
                },
            },
        },
    },
}
CANDIDATE_PROPERTIES = {
    'name': {
        'type': 'string',
        'minLength': 1,
        'maxLength': 200,
        'description': "Reviewer-readable, e.g. 'Liquid hydrogen, 9,000 km'.",
    },
    'model_id': uuid_schema('The model.'),
    'model_version_id': uuid_schema('The exact saved model version the configuration pins.'),
    'inputs': {
        'type': 'array',
        'maxItems': 1000,
        'items': INPUT,
        'description': 'One entry per free input of the model version.',
    },
    'default_source': SOURCE,
    'assumptions': {'type': 'array', 'maxItems': 100, 'items': ASSUMPTION},
}
CANDIDATE_REQUIRED = ['name', 'model_id', 'model_version_id', 'inputs']


class Ports:
    """The ports of one exact model version by "<component>.<port>" path."""

    def __init__(self, model):
        self.view = ModelView(model)
        self.by_path = {}
        for key, port in self.view.ports.items():
            self.by_path.setdefault(port['component'] + '.' + port['port'], []).append((key, port))
        connected = {
            (c['target_ref']['instance_id'], c['target_ref']['port_id'])
            for c in model.get('connections', ())
        }
        # Free inputs: unconnected inputs of the model's components (the root alone when the
        # model has no other component), as get_model lists them.
        components = {i['instance_id'] for i in self.view.components}
        self.free = sorted(
            port['component'] + '.' + port['port']
            for key, port in self.view.ports.items()
            if port['direction'] == 'input' and key not in connected and key[0] in components
        )

    def target(self, path, field, direction):
        found = self.by_path.get(path, [])
        if len(found) != 1 or found[0][1]['direction'] != direction:
            near = sorted(
                p
                for p, items in self.by_path.items()
                if any(port['direction'] == direction for _, port in items)
            )[:5]
            raise ToolError(
                'invalid_input',
                'That ' + direction + ' is not a port of the chosen model version.',
                fields=(
                    {
                        'path': field,
                        'problem': 'must be one of: ' + ', '.join(near)
                        if near
                        else 'the model version has no such port',
                    },
                ),
                next_step='Call get_model for the model version and use its "<component>.<port>" '
                'names.',
            )
        (instance_id, port_id), _ = found[0]
        return {'instance_id': instance_id, 'port_id': port_id}


def _unit(text):
    """The configuration unit text: the vocabulary spelling, or '' for "dimensionless"."""
    return '' if text == 'dimensionless' else text


async def _statement(ctx, source, field, titles):
    """The provenance of a typed source: its kind, a deterministic statement that never repeats
    the port or value, and its evidence versions."""
    authority = source['authority']
    evidence = list(source.get('evidence_version_ids', ()))
    note = source.get('note')
    if authority == 'source':
        if not evidence:
            raise ToolError(
                'invalid_input',
                'A source needs the evidence version it comes from.',
                fields=(
                    {'path': field + '.evidence_version_ids', 'problem': 'required for a source'},
                ),
                next_step='Add the evidence with add_evidence, then cite its evidence_version_id.',
            )
        names = []
        for version in evidence:
            if version not in titles:
                record = (
                    await read(
                        ctx,
                        study_path(ctx, 'evidence', version),
                        next_step='Call list_evidence and cite an evidence version id.',
                    )
                )['data']
                titles[version] = record.get('title') or 'Evidence record'
            names.append(titles[version])
        text = '; '.join(names)
        if source.get('locator'):
            text += ', ' + source['locator']
        kind = 'source'
    elif authority == 'judgement':
        if note is None:
            raise ToolError(
                'invalid_input',
                'A judgement states its reasoning in note.',
                fields=({'path': field + '.note', 'problem': 'required for a judgement'},),
                next_step='Add a short note explaining the judgement.',
            )
        text, kind, note = 'Judgement: ' + note, 'manual', None
    else:
        text, kind = LABELS[authority], 'manual'
        if source.get('locator'):
            text += ', ' + source['locator']
    if note:
        text += ' (' + note + ')'
    return dict(kind=kind, statement=text, evidence_version_ids=evidence)


async def _result_source(ctx, run_id, output, ports, field):
    """The retained output of ``run_id`` named ``output``, with the digest of its results."""
    cursor = None
    for _ in range(20):
        params = {'limit': '50'}
        if cursor:
            params['cursor'] = cursor
        page = (await read(ctx, study_path(ctx, 'result-sources'), params))['data']
        for item in page['items']:
            labels = item['labels']
            name = (labels.get('instance_name') or '') + '.' + (labels.get('output_name') or '')
            if item['source_run_id'] == run_id and name == output:
                return item
        cursor = page['next_cursor']
        if not cursor:
            break
    raise ToolError(
        'invalid_input',
        'That run has no retained output of that name usable as an input.',
        fields=({'path': field + '.output', 'problem': 'must be a retained output of from_run'},),
        next_step='Call list_result_sources and use a run and output it lists.',
    )


async def _candidate(arguments, ctx):
    """The public ``ConfigurationRequest6`` of the tool input, built against the exact model
    version: every port resolved by name, every source rendered, new ids assigned here, the
    study context copied from the current study. Returns ``(candidate, ports)``."""
    model_id, version_id = arguments['model_id'], arguments['model_version_id']
    study = (await read(ctx, study_path(ctx), missing='access_lost'))['data']
    model = (
        await read(
            ctx,
            study_path(ctx, 'models', model_id, 'revisions', version_id),
            next_step='Call list_model_versions and use a saved model version id.',
        )
    )['data']
    ports = Ports(model)
    titles, inputs = {}, []
    default = arguments.get('default_source')
    for n, item in enumerate(arguments['inputs']):
        field = f'inputs[{n}]'
        target = ports.target(item['quantity'], field + '.quantity', 'input')
        literal = 'value' in item or 'unit' in item
        linked = 'from_run' in item or 'output' in item
        if (
            literal == linked
            or (literal and not ('value' in item and 'unit' in item))
            or (linked and not ('from_run' in item and 'output' in item))
        ):
            raise ToolError(
                'invalid_input',
                'An input gives either value and unit, or from_run and output.',
                fields=({'path': field, 'problem': 'give value and unit, or from_run and output'},),
                next_step='Fix the listed input and call the tool again.',
            )
        source = item.get('source', default)
        if source is None:
            raise ToolError(
                'invalid_input',
                'Every input states where its value comes from.',
                fields=({'path': field + '.source', 'problem': 'required without default_source'},),
                next_step='Give the input a source, or give default_source.',
            )
        where = field + '.source' if 'source' in item else 'default_source'
        provenance = await _statement(ctx, source, where, titles)
        if literal:
            inputs.append(
                dict(
                    kind='literal',
                    target=target,
                    value=item['value'],
                    units=_unit(item['unit']),
                    provenance=provenance,
                )
            )
        else:
            found = await _result_source(ctx, item['from_run'], item['output'], ports, field)
            inputs.append(
                dict(
                    kind='run_result',
                    target=target,
                    source_run_id=item['from_run'],
                    source_output=found['source_output'],
                    expected_results_digest=found['results_digest'],
                    provenance=provenance,
                )
            )
    assumptions = [
        dict(
            assumption_id=uid(),
            statement=item['statement'],
            evidence_links=[dict(link) for link in item.get('evidence', ())],
        )
        for item in arguments.get('assumptions', ())
    ]
    candidate = dict(
        schema_version='6',
        study_id=study['study_id'],
        model_id=model_id,
        model_revision_id=version_id,
        name=arguments['name'],
        inputs=inputs,
        numerical=DETERMINISTIC,
        context_source=dict(kind='current_study', expected_study_revision=study['revision']),
        context_override=dict(
            schema_version='1', description=study['description'], boundary=study['boundary']
        ),
        notes=[],
        derivation=None,
        assumptions=assumptions,
        general_context_evidence_version_ids=[],
    )
    return candidate, ports


def configuration_field(pointer):
    """The tool input path of a field of the public request the API refused."""
    parts = [p for p in str(pointer).split('/')[1:]]
    if parts and parts[0] == 'configuration':
        parts = parts[1:]
    if not parts:
        return '(input)'
    head = parts[0]
    index = f'[{parts[1]}]' if len(parts) > 1 and parts[1].isdecimal() else ''
    if head in ('inputs', 'assumptions'):
        return head + index
    if head == 'name':
        return 'name'
    if head in ('model_id', 'model_revision_id'):
        return 'model_version_id' if head == 'model_revision_id' else 'model_id'
    return '(input)'


def _diagnostics(compatibility):
    return [
        {
            'field': configuration_field(item['path']),
            'code': item['code'],
            'problem': clip(item['message'], 512)[0],
        }
        for item in compatibility['diagnostics'][:50]
    ]


def _summary(candidate, ports, arguments):
    """The candidate as the engineer reads it: quantity = value unit (source)."""
    rows = []
    for item, given in zip(candidate['inputs'], arguments['inputs']):
        row = {'quantity': given['quantity'], 'source': item['provenance']['statement']}
        if item['kind'] == 'literal':
            row.update(value=item['value'], unit=given['unit'])
        else:
            row.update(from_run=item['source_run_id'], output=given['output'])
        rows.append(untrusted('configuration input', text=row))
    assigned = {given['quantity'] for given in arguments['inputs']}
    return rows, [path for path in ports.free if path not in assigned]


async def _preview(arguments, ctx, tool):
    candidate, ports = await _candidate(arguments, ctx)
    preview = (
        await send(
            ctx,
            'POST',
            study_path(ctx, 'configurations', 'preview'),
            candidate,
            tool=tool,
            conflict_step='Call ' + tool + ' again; the study or a cited record changed.',
            field_map=configuration_field,
        )
    )['data']
    return candidate, ports, preview


async def preview_configuration(arguments, ctx):
    """Check a configuration against its exact model version without saving anything."""
    candidate, ports, preview = await _preview(arguments, ctx, 'preview_configuration')
    rows, missing_inputs = _summary(candidate, ports, arguments)
    compatibility = preview['compatibility']
    return cap(
        {
            'compatible': compatibility['compatible'],
            'diagnostics': _diagnostics(compatibility),
            'missing_inputs': missing_inputs,
            'inputs': rows,
            'assumptions': len(candidate['assumptions']),
            'numerical_mode': 'deterministic',
            'next_step': 'Save it with save_configuration and the same input.'
            if compatibility['compatible']
            else 'Fix the diagnostics and preview again.',
        },
        [('inputs', 'input summary', 'get_configuration after saving')],
    )


async def save_configuration(arguments, ctx):
    """Preview again and save exactly the previewed configuration as a new configuration or
    the next version of one."""
    family = arguments.get('configuration_id')
    expected = arguments.get('expected_revision')
    if (family is None) != (expected is None):
        raise ToolError(
            'invalid_input',
            'A new version names configuration_id and the expected_revision of its latest version.',
            fields=(
                {'path': 'expected_revision', 'problem': 'give it exactly with configuration_id'},
            ),
            next_step='Call get_configuration for the latest version and pass its '
            'configuration_version_id as expected_revision.',
        )
    candidate, ports, preview = await _preview(arguments, ctx, 'save_configuration')
    compatibility = preview['compatibility']
    if not compatibility['compatible']:
        raise ToolError(
            'invalid_input',
            'The configuration does not match its model version; nothing was saved.',
            fields=tuple(
                {'path': d['field'], 'problem': d['problem']}
                for d in _diagnostics(compatibility)[:20]
            ),
            next_step='Fix the listed fields and call save_configuration again.',
        )
    body = dict(
        command_id=command_id(ctx),
        expected_revision=expected,
        configuration_id=family,
        configuration=candidate,
        expected_preview_digest=preview['candidate_digest'],
    )
    frozen = (
        await send(
            ctx,
            'POST',
            study_path(ctx, 'configurations'),
            body,
            tool='save_configuration',
            conflict_step='Call get_configuration for the latest version, then save again with its '
            'configuration_version_id as expected_revision.',
            field_map=configuration_field,
        )
    )['data']
    saved = frozen['configuration']
    report(
        ctx,
        'configuration_version',
        saved['configuration_id'],
        version_id=saved['configuration_revision_id'],
        name=saved['name'],
    )
    rows, missing_inputs = _summary(candidate, ports, arguments)
    return cap(
        {
            'configuration_version': dict(configuration_ref(frozen), **model_refs(saved)),
            'previous_version': ref(
                'configuration_version',
                saved['parent_revision_id'],
                None,
                missing='call_get_configuration',
            )
            if saved.get('parent_revision_id')
            else missing('first_version'),
            'inputs': rows,
            'missing_inputs': missing_inputs,
            'next_step': 'Submit it with submit_runs, then add it to an analysis '
            '(create_analysis or save_analysis_version) to evaluate the study criteria.',
        },
        [('inputs', 'input summary', 'get_configuration')],
    )


OWNERS = ('configuration', 'store', 'modeling', 'result_bindings')
CANDIDATE_DESCRIPTION = (
    'name: reviewer-readable. model_id and model_version_id: the exact saved model version the '
    'configuration pins. inputs: one entry per free input, quantity "<component>.<port>" with '
    'value and unit (a unit of the vocabulary, or "dimensionless"), or with from_run and output '
    '(a retained output of that run, from list_result_sources); never leave a value to a '
    'default. Every input states its source {authority: brief | source | property | constant '
    '| judgement | numerical, evidence_version_ids, locator, note}, or default_source applies; '
    'the tool writes the provenance statement from it. assumptions: {statement, evidence}. A '
    'configuration carries no criteria: the study criteria are defined in the study brief '
    'and evaluated in analyses. The evaluation is deterministic (no solvers, '
    'optimization or uncertainty); the current study description and boundary are copied '
    'into it.'
)

PREVIEW_CONFIGURATION = ToolSpec(
    name='preview_configuration',
    title='Check a configuration before saving',
    description=(
        'Checks a configuration against its exact model version without saving anything: '
        'compatibility diagnostics with the input field they concern, the free inputs still '
        'unassigned, and the inputs as quantity, value, unit and source. '
        + CANDIDATE_DESCRIPTION
        + ' Save it with save_configuration and the same input. '
        'Guidance: get_playbook("configuration_and_runs").'
    ),
    input_schema={
        'type': 'object',
        'additionalProperties': False,
        'required': CANDIDATE_REQUIRED,
        'properties': CANDIDATE_PROPERTIES,
    },
    effect='read',
    stage='runs',
    surfaces=SURFACES,
    owners=OWNERS,
    outcome='none',
    activity_label='Checked: configuration',
    handler=preview_configuration,
    api_operations=(STUDY, REVISION, EVIDENCE, SOURCES, PREVIEW),
)

SAVE_CONFIGURATION = ToolSpec(
    name='save_configuration',
    title='Save a configuration',
    description=(
        'Previews the configuration again and saves exactly what was previewed as a new saved '
        'configuration version, which never changes afterwards; a configuration that does not '
        'match its model version is not saved. A new version of an existing configuration '
        'names its configuration_id and expected_revision (the '
        "configuration_version_id of its latest version you read), so a person's newer version "
        'is never overwritten. ' + CANDIDATE_DESCRIPTION + ' Returns the configuration version '
        'id; submit it with submit_runs. Guidance: get_playbook("configuration_and_runs").'
    ),
    input_schema={
        'type': 'object',
        'additionalProperties': False,
        'required': CANDIDATE_REQUIRED,
        'properties': dict(
            CANDIDATE_PROPERTIES,
            configuration_id=uuid_schema(
                'The configuration_id of an existing configuration to save a new version of.'
            ),
            expected_revision=uuid_schema(
                'With configuration_id: the configuration_version_id of its latest version.'
            ),
        ),
    },
    effect='record',
    stage='runs',
    surfaces=SURFACES,
    owners=OWNERS,
    outcome='receipt:configuration',
    activity_label='Saved: configuration',
    handler=save_configuration,
    api_operations=(STUDY, REVISION, EVIDENCE, SOURCES, PREVIEW, COMMIT),
    attribution_kind='configuration_version',
)

TOOLS = (
    LIST_CONFIGURATIONS,
    GET_CONFIGURATION,
    LIST_RESULT_SOURCES,
    PREVIEW_CONFIGURATION,
    SAVE_CONFIGURATION,
)
