"""Runs and results: the read tools (tooling spec section 4.7).

Run state is owned by ``execution`` (receipts and run associations) and the retained results
by ``history``; AiiDA owns the process lifecycle, which the owners project. These tools read
the owners on every call and keep nothing between calls: ``get_run_status`` makes exactly one
light run-status read per call (no status cache, no run state of its own), and results are
read from the stored run, never recomputed or re-run. Execution, convergence, termination,
feasibility, completeness, applicability and criterion outcomes stay separate fields.
"""

import re

from ..projections import (
    CURSOR_SCHEMA,
    LIMIT_SCHEMA,
    ModelView,
    age_seconds,
    cap,
    clip,
    decode_cursor,
    encode_cursor,
    missing,
    quantity,
    read,
    ref,
    run_name,
    run_ref,
    study_path,
    untrusted,
    uuid_schema,
)
from ..spec import SURFACES, ToolSpec

LIST = ('GET', '/api/1/studies/{study_id}/runs')
ONE = ('GET', '/api/1/studies/{study_id}/runs/{run_id}')
STATUS = ('GET', '/api/1/studies/{study_id}/run-status')
OWNERS = ('execution', 'history')
FACETS = ('execution', 'convergence', 'optimization', 'completeness', 'applicability')
COMPLETENESS = ('expected', 'available', 'failed', 'unavailable')
NOT_EVALUATED = 'not evaluated'
DIAGNOSTICS_CHARS = 1200
REASON_CHARS = 300
WAITING_STATES = frozenset({'accepted_run', 'prepared', 'dispatching', 'uncertain'})
TOKEN = re.compile(r'[a-z][a-z0-9_]{0,63}')
FEASIBILITY = re.compile(r'feasib', re.IGNORECASE)
RUN_IDS = {
    'type': 'array',
    'items': uuid_schema('A run of this study.'),
    'uniqueItems': True,
}


async def list_runs(arguments, ctx):
    """One page of the study's runs in the order they were submitted."""
    limit = arguments.get('limit', 10)
    params = {'limit': str(limit)}
    if arguments.get('cursor') is not None:
        params['cursor'] = decode_cursor('list_runs', arguments['cursor'])
    body = await read(ctx, study_path(ctx, 'runs'), params)
    after = body.get('next_cursor')
    return cap(
        {
            'runs': [dict(run_ref(item), state=item['state']) for item in body['data']],
            'next_cursor': None if after is None else encode_cursor('list_runs', after),
        },
        [('runs', 'runs', 'list_runs with a smaller limit')],
    )


LIST_RUNS = ToolSpec(
    name='list_runs',
    title='List the runs of the study',
    description=(
        "Returns one page of the study's runs in the order they were submitted: the run "
        '("Run of \'<configuration name>\'") with its id, the configuration version it ran, '
        'the approach case it implements and its state as the execution owner records it '
        '(accepted_run, prepared, preparation_failed, dispatching, recorded or uncertain). '
        'limit: items per page (1 to 25, default 10); cursor: the next_cursor of the previous '
        'page, passed back unchanged. Use get_run_status for the outcome facets of up to 20 '
        "runs and get_run_results for one run's outputs. An uncertain run is never "
        'resubmitted. Guidance: get_playbook("configuration_and_runs").'
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
    activity_label='Read: runs',
    handler=list_runs,
    api_operations=(LIST,),
)


def _stored(value):
    """A light-read ``{value, reason}`` pair: the stored value, or missing with its reason."""
    if value.get('value') is None:
        return missing(value.get('reason') or 'not_recorded')
    return value['value']


def _facets(facets):
    stored = {key: _stored(facets[key]) for key in FACETS}
    execution = stored['execution']
    if isinstance(execution, dict) and 'state' in execution:
        message, cut = clip(execution.get('message', ''), DIAGNOSTICS_CHARS)
        execution = {
            'state': execution['state'],
            'exit_code': execution['exit_code'],
            'message': untrusted('execution diagnostics', text=message),
            'message_truncated': cut,
        }
    optimization = stored['optimization']
    return {
        'execution': execution,
        'convergence': stored['convergence']['state']
        if isinstance(stored['convergence'], dict) and 'state' in stored['convergence']
        else stored['convergence'],
        'termination': optimization['termination']
        if isinstance(optimization, dict) and 'termination' in optimization
        else optimization,
        'feasibility': optimization['feasibility']
        if isinstance(optimization, dict) and 'feasibility' in optimization
        else optimization,
        'completeness': {k: stored['completeness'][k] for k in COMPLETENESS}
        if isinstance(stored['completeness'], dict) and 'missing' not in stored['completeness']
        else stored['completeness'],
        'applicability': stored['applicability']['state']
        if isinstance(stored['applicability'], dict) and 'state' in stored['applicability']
        else stored['applicability'],
    }


def _time(value):
    if value.get('value') is None:
        return missing(value.get('reason') or 'not_recorded')
    return value['value']


def status_projection(item):
    """One run of the light status read, with every time that is not recorded or not
    projected shown as missing with its reason, never as a time."""
    times = item['times']
    submitted = times['submitted_at'].get('value')
    if item['state'] not in WAITING_STATES:
        waiting = missing('no_longer_waiting')
    elif submitted is None:
        waiting = missing(times['submitted_at'].get('reason') or 'not_recorded')
    else:
        waited = age_seconds(submitted)
        waiting = waited if waited is not None else missing('not_recorded')
    criteria = item['criteria']
    facets = _facets(item['facets'])
    if isinstance(facets['execution'], dict):
        # Diagnostics belong to get_run_results; the light status stays light.
        facets['execution'].pop('message', None)
        facets['execution'].pop('message_truncated', None)
    return dict(
        run_ref(item),
        state=item['state'],
        process_state=item['process_state'] or missing('not_recorded'),
        exit_status=item['exit_status']
        if item['exit_status'] is not None
        else missing('not_recorded'),
        facets=facets,
        criteria=[
            dict(
                ref('criterion', c['criterion_id'], None, missing='call_get_run_results'),
                outcome=c['outcome'],
            )
            for c in criteria['value']
        ]
        if criteria.get('value') is not None
        else missing(criteria.get('reason') or 'not_recorded'),
        times={
            'submitted_at': _time(times['submitted_at']),
            'started_at': _time(times['started_at']),
            'finished_at': _time(times['finished_at']),
        },
        waiting_s=waiting,
    )


async def get_run_status(arguments, ctx):
    """The light status of 1 to 20 runs from exactly one owner read; nothing is kept."""
    run_ids = arguments['run_ids']
    params = [('run_id', run_id) for run_id in run_ids]
    data = (await read(ctx, study_path(ctx, 'run-status'), params, next_step=_NOT_FOUND))['data']
    return cap(
        {'runs': [status_projection(item) for item in data]},
        [('runs', 'runs', 'get_run_status with fewer run_ids')],
    )


_NOT_FOUND = 'At least one id is not a run of this study; nothing was answered. Call list_runs.'

GET_RUN_STATUS = ToolSpec(
    name='get_run_status',
    title='Read the status of runs',
    description=(
        'Returns the current status of 1 to 20 runs in one light read of the execution owner, '
        'in the order asked: the run and its configuration, state (accepted_run, prepared, '
        'preparation_failed, dispatching, recorded or uncertain), process state and exit '
        'status, the outcome facets (execution, convergence, termination, feasibility, '
        'completeness, applicability) and criterion outcomes once results are retained, the '
        'submission time and seconds waited. A value not yet recorded or not projected is '
        'shown as missing with its reason, never as zero. run_ids: runs of this study; if one '
        'is not, nothing is answered. It never resubmits; an uncertain run is reported to the '
        'user. Use get_run_results for outputs. '
        'Guidance: get_playbook("configuration_and_runs").'
    ),
    input_schema={
        'type': 'object',
        'additionalProperties': False,
        'required': ['run_ids'],
        'properties': {
            'run_ids': dict(
                RUN_IDS, minItems=1, maxItems=20, description='1 to 20 runs of this study.'
            ),
        },
    },
    effect='read',
    stage='read_only',
    surfaces=SURFACES,
    owners=OWNERS,
    outcome='none',
    activity_label='Read: run status',
    handler=get_run_status,
    api_operations=(STATUS,),
)


def _reason(text):
    return text if isinstance(text, str) and TOKEN.fullmatch(text) else 'see_diagnostics'


async def _detail(ctx, run_id):
    path = study_path(ctx, 'runs', run_id)
    return (await read(ctx, path, next_step='Call list_runs.'))['data']


def _run_head(detail):
    history = detail.get('history') or {}
    configuration = history.get('configuration')
    name = configuration.get('name') if isinstance(configuration, dict) else None
    head = {
        'run': ref(
            'run', detail['run_id'], run_name(name), missing='configuration_not_in_this_record'
        ),
        'configuration': ref(
            'configuration_version',
            configuration['configuration_revision_id'],
            name,
            configuration_id=configuration['configuration_id'],
        )
        if isinstance(configuration, dict)
        else missing('not_in_this_record'),
        'state': detail['state'],
        'process_state': detail.get('process_state') or missing('not_recorded'),
        'exit_status': detail['exit_status']
        if detail.get('exit_status') is not None
        else missing('not_recorded'),
    }
    return head, history


def _outputs(view, results):
    """Every retained output as a quantity with its unit; an unavailable output is never a
    number."""
    entries = []
    for output in results['outputs']:
        path = view.path(output['target'])
        name = (
            untrusted('run output', text=path) if path is not None else missing('port_not_in_model')
        )
        if output['availability'] == 'available':
            entry = quantity(name, output['value'], view.unit(output['target'], output['units']))
        else:
            entry = quantity(name, None, None, unavailable=_reason(output.get('reason')))
        entries.append((path, output['target'], entry))
    return entries


async def get_run_results(arguments, ctx):
    """One run's recorded outcome facets, outputs and criterion outcomes, as stored."""
    detail = await _detail(ctx, arguments['run_id'])
    head, history = _run_head(detail)
    results = history.get('results')
    projection = dict(head)
    if results is None:
        projection['facets'] = {
            key: NOT_EVALUATED
            for key in (
                'execution',
                'convergence',
                'termination',
                'feasibility',
                'completeness',
                'applicability',
            )
        }
        projection['outputs'] = missing('no_retained_results')
        projection['criteria'] = missing('no_retained_results')
        projection['record_problems'] = [e['code'] for e in history.get('errors', ())]
        return projection
    facets = _facets({key: {'value': results[key]} for key in FACETS})
    if not arguments.get('include_diagnostics', False):
        facets['execution'].pop('message', None)
        facets['execution'].pop('message_truncated', None)
    projection['facets'] = facets
    view = ModelView(history['model_snapshot'])
    outputs = _outputs(view, results)
    wanted = arguments.get('outputs')
    if wanted:
        outputs = [o for o in outputs if o[0] in set(wanted)]
        projection['requested_outputs_not_found'] = len(set(wanted) - {o[0] for o in outputs})
    projection['outputs'] = [entry for _, _, entry in outputs]
    declared = []
    for path, target, entry in outputs:
        port = view.port(target)
        meaning = port['meaning'] if port else None
        if meaning and FEASIBILITY.search(meaning):
            declared.append(dict(entry, meaning=untrusted('quantity meaning', text=meaning)))
    if declared:
        projection['model_declared_feasibility'] = {
            'outputs': declared,
            'note': "Declared by the model in a quantity meaning; this is the model's own "
            'output, not a HYPRN MVP feasibility outcome.',
        }
    configuration = history.get('configuration') or {}
    thresholds = {c['criterion_id']: c for c in configuration.get('criteria', ())}
    criteria = []
    for item in results['criteria']:
        declared_criterion = thresholds.get(item['criterion_id'])
        entry = ref(
            'criterion',
            item['criterion_id'],
            view.path(declared_criterion['target']) if declared_criterion else None,
            missing='criterion_not_in_configuration',
        )
        entry['outcome'] = item['outcome']
        if declared_criterion:
            entry['threshold'] = dict(
                quantity(
                    None,
                    declared_criterion['threshold'],
                    view.unit(declared_criterion['target'], declared_criterion['units']),
                ),
                operator=declared_criterion['operator'],
            )
        reason, _ = clip(item.get('reason', ''), REASON_CHARS)
        entry['reason'] = untrusted('criterion evaluation', text=reason)
        criteria.append(entry)
    projection['criteria'] = criteria
    projection['record_problems'] = [e['code'] for e in history.get('errors', ())]
    return cap(
        projection,
        [
            ('model_declared_feasibility', 'model-declared feasibility outputs', 'outputs'),
            ('criteria', 'criteria', 'get_run_results again'),
            ('outputs', 'outputs', 'get_run_results with outputs naming fewer outputs'),
        ],
    )


GET_RUN_RESULTS = ToolSpec(
    name='get_run_results',
    title='Read the results of a run',
    description=(
        "Returns one run's recorded outcome as separate fields: execution (state and exit "
        'code), convergence, termination, feasibility, completeness and applicability, each '
        '"not evaluated" while no results are retained; every output as "Component.port" with '
        'value and unit, or unavailable with its reason (never 0); criteria as met, violated '
        'or unresolved with their threshold; and a feasibility output the model declares in a '
        "quantity meaning, shown as the model's own. A met criterion is not validity. "
        'run_id: the run; outputs: only these "Component.port" outputs; include_diagnostics: '
        'add the execution message (at most 1,200 characters). Results are read as stored, '
        'never recomputed. Guidance: get_playbook("configuration_and_runs").'
    ),
    input_schema={
        'type': 'object',
        'additionalProperties': False,
        'required': ['run_id'],
        'properties': {
            'run_id': uuid_schema('The run.'),
            'outputs': {
                'type': 'array',
                'items': {'type': 'string', 'minLength': 1, 'maxLength': 512},
                'minItems': 1,
                'maxItems': 50,
                'uniqueItems': True,
                'description': 'Only these outputs, as "Component.port".',
            },
            'include_diagnostics': {
                'type': 'boolean',
                'description': 'Include the execution message (default false).',
            },
        },
    },
    effect='read',
    stage='read_only',
    surfaces=SURFACES,
    owners=OWNERS,
    outcome='none',
    activity_label='Read: run results',
    handler=get_run_results,
    api_operations=(ONE,),
)


async def compare_runs(arguments, ctx):
    """Selected outputs of 2 to 20 runs side by side; units shown, never converted."""
    names = list(arguments['outputs'])
    rows, units = [], [set() for _ in names]
    for run_id in arguments['run_ids']:
        detail = await _detail(ctx, run_id)
        head, history = _run_head(detail)
        results = history.get('results')
        row = {'run': head['run'], 'state': head['state']}
        if results is None:
            row['execution'] = NOT_EVALUATED
            row['values'] = [missing('no_retained_results') for _ in names]
        else:
            row['execution'] = results['execution']['state']
            found = {
                path: entry
                for path, _, entry in _outputs(ModelView(history['model_snapshot']), results)
                if path is not None
            }
            values = []
            for position, name in enumerate(names):
                entry = found.get(name)
                if entry is None:
                    values.append({'unavailable': 'not_an_output_of_this_run'})
                    continue
                value = {k: v for k, v in entry.items() if k != 'quantity'}
                if 'unit' in value:
                    units[position].add(value['unit'])
                values.append(value)
            row['values'] = values
        rows.append(row)
    return cap(
        {
            'columns': 'values are in the order of the outputs asked for',
            'rows': rows,
            'units_differ': [n for n, found in enumerate(units, 1) if len(found) > 1],
            'note': 'Values are recorded ones at full precision; units are shown as recorded '
            'and never converted. units_differ lists the positions of outputs whose units '
            'differ between runs.',
        },
        [('rows', 'runs', 'compare_runs with fewer run_ids')],
    )


COMPARE_RUNS = ToolSpec(
    name='compare_runs',
    title='Compare outputs of several runs',
    description=(
        'Returns a table of up to 10 outputs across 2 to 20 runs: for each run its name, '
        "state and execution outcome, then each output's recorded value and unit, or "
        'unavailable with its reason. Units are shown as recorded and never converted; '
        'values follow the order of outputs, and units_differ gives the positions (from 1) of '
        'outputs whose units differ between runs, which you must not compare directly. '
        'run_ids: the runs; outputs: output names as "Component.port", as '
        'get_run_results shows them. Nothing is recomputed or re-run. '
        'Guidance: get_playbook("configuration_and_runs").'
    ),
    input_schema={
        'type': 'object',
        'additionalProperties': False,
        'required': ['run_ids', 'outputs'],
        'properties': {
            'run_ids': dict(RUN_IDS, minItems=2, maxItems=20, description='2 to 20 runs.'),
            'outputs': {
                'type': 'array',
                'items': {'type': 'string', 'minLength': 1, 'maxLength': 512},
                'minItems': 1,
                'maxItems': 10,
                'uniqueItems': True,
                'description': 'Outputs to compare, as "Component.port".',
            },
        },
    },
    effect='read',
    stage='read_only',
    surfaces=SURFACES,
    owners=OWNERS,
    outcome='none',
    activity_label='Read: run comparison',
    handler=compare_runs,
    api_operations=(ONE,),
)

TOOLS = (LIST_RUNS, GET_RUN_STATUS, GET_RUN_RESULTS, COMPARE_RUNS)
