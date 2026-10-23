"""Public sampling, frozen estimate plans and checked answer exploration.

Numerical work and validation remain with the existing owners. These tools resolve names,
submit explicit plans and project their records; they never fit or calculate locally.
"""

import asyncio
from uuid import uuid4

from ..projections import cap, command_id, read, report, send, study_path, untrusted, uuid_schema
from ..spec import SURFACES, ToolError, ToolSpec
from .calculation import REVISION, VERSION, _model, _version
from .configuration import PATH, Ports, ONE as CONFIGURATION
from .runs import GET_RUN_STATUS, WAITING_STATES, get_run_status

ROOT = '/api/1/studies/{study_id}'
SAMPLES = ('POST', ROOT + '/analysis-samples')
SAMPLE = ('GET', ROOT + '/analysis-samples/{operation_id}')
EXECUTION = ('GET', ROOT + '/analysis-versions/{version_id}/execution')
LAUNCH = ('POST', ROOT + '/analysis-versions/{version_id}/execution')
RECOVERY = ('GET', ROOT + '/analysis-versions/{version_id}/execution/recovery')
RESUME = ('POST', ROOT + '/analysis-versions/{version_id}/execution/resume')
ESTIMATE = ('GET', ROOT + '/analysis-estimates/{estimate_id}')
PREPARATION = ('POST', ROOT + '/analysis-estimates/{estimate_id}/preparation')
EXPLORATION = ('GET', ROOT + '/analysis-versions/{version_id}/exploration')
PREDICT = ('POST', ROOT + '/analysis-estimates/{estimate_id}/predictions')
GUIDE = ' Guidance: get_playbook("configuration_and_runs").'
TEXT = {'type': 'string', 'maxLength': 4096}
NUMBER = {'type': 'number', 'minimum': -(2**53 - 1), 'maximum': 2**53 - 1}
WAIT = {
    'type': 'integer',
    'minimum': 0,
    'maximum': 20,
    'description': 'Wait up to this many seconds for progress, default 0. No model rerun.',
}


def obj(properties, required=()):
    return dict(
        type='object', additionalProperties=False, properties=properties, required=list(required)
    )


def array(items, maximum, minimum=0):
    return dict(type='array', items=items, maxItems=maximum, minItems=minimum)


DIMENSION = obj(
    dict(
        quantity=PATH,
        lower=NUMBER,
        upper=NUMBER,
        unit=dict(type='string', maxLength=64),
        step=dict(NUMBER, exclusiveMinimum=0),
        covary_group=dict(type='string', minLength=1, maxLength=100),
    ),
    ('quantity', 'lower', 'upper', 'unit'),
)
TOLERANCE = obj(
    dict(output=PATH, absolute=dict(NUMBER, minimum=0), relative=dict(NUMBER, minimum=0)),
    ('output', 'absolute', 'relative'),
)
GROUP = obj(
    dict(
        configuration_version_id=uuid_schema(
            'An explicit saved input vector; varied inputs use the declared ranges. '
            'First save every independent input with units and provenance using save_configuration.'
        ),
        dimensions=array(DIMENSION, 32, 1),
        training_count=dict(type='integer', minimum=3, maximum=64),
        validation_count=dict(
            type='integer', minimum=2, maximum=64,
            description='Held-out pool: one point selects the method; the remaining points '
                        'independently validate it. For 16, this is 1 selection + 15 validation.',
        ),
    ),
    ('configuration_version_id', 'dimensions', 'training_count', 'validation_count'),
)


def sample_projection(value):
    return {
        **{
            k: value[k]
            for k in (
                'operation_id',
                'state',
                'point_count',
                'retained_count',
                'calculation_id',
                'calculation_version_id',
            )
        },
        'diagnostic': untrusted('sampling diagnostic', text=value['reason']),
        'next_step': 'When complete, get_analysis lists saved point configurations. '
        'Use launch_analysis to admit the complete finite plan; missing runs progress automatically.',
    }


async def create_sampled_analysis(a, ctx):
    total = sum(g['training_count'] + g['validation_count'] for g in a['groups'])
    if total > 128:
        raise ToolError('invalid_input',
            f'The design requests {total} points; capacity is 128 points per saved analysis.',
            fields=({'path': 'groups', 'problem': f'{total} requested points exceeds capacity 128'},),
            next_step='Reduce or narrow groups before creating the design. Preserve independent '
            'validation and declared tolerances; refine using a new saved version after reviewing results.')
    ports = Ports(await _model(ctx, a['model_id'], a['model_version_id']))
    groups, provenance = [], []
    for n, group in enumerate(a['groups']):
        frozen = (
            await read(ctx, study_path(ctx, 'configurations', group['configuration_version_id']))
        )['data']
        if frozen['configuration']['model_revision_id'] != a['model_version_id']:
            raise ToolError('invalid_input', 'All groups must pin the requested model version.')
        provenance.extend(
            i['provenance']['statement']
            for i in frozen['configuration']['inputs']
            if i.get('provenance')
        )
        dimensions = [
            dict(
                target=ports.target(d['quantity'], f'groups[{n}].dimensions', 'input'),
                lower=d['lower'],
                upper=d['upper'],
                units='' if d['unit'] == 'dimensionless' else d['unit'],
                step=d.get('step'),
                covary_group=d.get('covary_group'),
            )
            for d in group['dimensions']
        ]
        groups.append(
            dict(
                reference_configuration_revision_id=group['configuration_version_id'],
                dimensions=dimensions,
                training_count=group['training_count'],
                validation_count=group['validation_count'],
            )
        )
    plan = (
        None
        if a.get('tolerances') is None
        else dict(
            tolerances=[
                dict(
                    target=ports.target(t['output'], 'tolerances.output', 'output'),
                    absolute=t['absolute'],
                    relative=t['relative'],
                )
                for t in a['tolerances']
            ]
        )
    )
    body = dict(
        command_id=command_id(ctx),
        calculation_id=a.get('calculation_id'),
        expected_version_id=a.get('expected_revision'),
        name=a['name'],
        description=a.get('description', ''),
        method=a['method'],
        seed=a['seed'],
        groups=groups,
        rationale=a.get('range_provenance')
        or '\n'.join(dict.fromkeys(provenance))[:4096]
        or 'Explicit ranges in the saved design.',
        estimate_plan=plan,
    )
    value = (
        await send(
            ctx,
            'POST',
            study_path(ctx, 'analysis-samples'),
            body,
            tool='create_sampled_analysis',
            conflict_step='Read the latest analysis '
            'before revising. Do not repeat an uncertain operation.',
        )
    )['data']
    report(ctx, 'calculation_sample', value['operation_id'])
    return sample_projection(value)


async def _wait(ctx, path, seconds, terminal):
    value = (await read(ctx, path))['data']
    for _ in range(seconds // 2):
        if value is None or value['state'] in terminal:
            break
        await asyncio.sleep(2)
        value = (await read(ctx, path))['data']
    return value


async def get_sampling_status(a, ctx):
    value = await _wait(
        ctx,
        study_path(ctx, 'analysis-samples', a['operation_id']),
        a.get('wait_seconds', 0),
        {'complete', 'failed', 'uncertain'},
    )
    return sample_projection(value)


def execution_projection(value):
    if value is None:
        return {'state': 'not_launched'}
    return {
        **{
            k: value[k]
            for k in (
                'calculation_version_id',
                'state',
                'completed_count',
                'total_count',
                'estimate_id',
            )
        },
        **({'admission_state': value['admission_state']} if 'admission_state' in value else {}),
        'diagnostic': untrusted('analysis execution diagnostic', text=value['reason']),
    }


async def get_analysis_execution(a, ctx):
    value = await _wait(
        ctx,
        study_path(ctx, 'analysis-versions', a['calculation_version_id'], 'execution'),
        a.get('wait_seconds', 0),
        {'complete', 'failed', 'needs_review', 'cancelled'},
    )
    return await execution_recovery(value, ctx)


async def launch_analysis(a, ctx):
    """Authorize one exact finite plan; its durable owner admits bounded work."""
    vid = a['calculation_version_id']
    value = (
        await send(
            ctx,
            'POST',
            study_path(ctx, 'analysis-versions', vid, 'execution'),
            {},
            tool='launch_analysis',
            conflict_step='Read get_analysis_execution before retrying an uncertain launch.',
        )
    )['data']
    return await execution_recovery(value, ctx)


async def execution_recovery(value, ctx):
    result = execution_projection(value)
    if value is not None and value['state'] in ('failed', 'needs_review'):
        recovery = (await read(ctx, study_path(
            ctx, 'analysis-versions', value['calculation_version_id'],
            'execution', 'recovery')))['data']
        result['can_resume'] = recovery['can_resume']
        result['recovery'] = untrusted('analysis recovery diagnostic', text=recovery['reason'])
    return result


async def resume_analysis(a, ctx):
    value = (await send(
        ctx, 'POST', study_path(ctx, 'analysis-versions',
                               a['calculation_version_id'], 'execution', 'resume'),
        {'command_id': command_id(ctx)}, tool='resume_analysis',
        conflict_step='Read get_analysis_execution and its recovery reason. '
                      'Do not relaunch or create a duplicate analysis to bypass a refusal.',
    ))['data']
    return execution_projection(value)


async def _estimate(ctx, eid):
    value = (await read(ctx, study_path(ctx, 'analysis-estimates', eid)))['data']
    version = await _version(ctx, value['calculation_version_id'])
    content = version['content']
    ports = Ports(await _model(ctx, content['model_id'], content['model_revision_id']))
    return value, ports


def _sample_roles(samples, group):
    """Project the frozen pool using the qualified fitter's reserved-first-point policy.

    Counts are reserved roles, not evidence of successful execution or assessment;
    each output's metrics report the actual assessed and unavailable results.
    """
    points = [s for s in samples if s['group'] == group]
    training = sum(s['partition'] == 'training' for s in points)
    held_out = len(points) - training
    selection = min(1, held_out)
    return dict(training=training, held_out_pool=held_out, method_selection=selection,
                independent_validation=held_out - selection)


async def get_surrogate(a, ctx):
    value, ports = await _estimate(ctx, a['estimate_id'])
    result = {
        k: value[k]
        for k in (
            'estimate_id',
            'calculation_version_id',
            'state',
            'completed_groups',
            'total_groups',
        )
    }
    result['diagnostic'] = untrusted('surrogate diagnostic', text=value['reason'])
    result['groups'] = [
        dict(
            group=g['group'],
            sample_roles=_sample_roles(value['samples'], g['group']),
            outputs=[
                dict(
                    output=ports.view.quantity_ref(o['target']),
                    units=o['units'],
                    method=o['method'],
                    diagnostic=untrusted('surrogate output diagnostic', text=o['reason']),
                    metrics=None
                    if o['metrics'] is None
                    else {
                        k: o['metrics'][k]
                        for k in (
                            'assessed_count',
                            'evaluable_count',
                            'failed_count',
                            'max_absolute_error',
                            'rmse',
                            'target_met',
                        )
                    },
                )
                for o in g['outputs']
            ],
        )
        for g in value['groups']
    ]
    result['tolerances'] = [
        dict(
            output=ports.view.quantity_ref(t['target']),
            absolute=t['absolute'],
            relative=t['relative'],
        )
        for t in value['request']['tolerances']
    ]
    return cap(result, [('groups', 'validation metrics', 'get_surrogate')])


async def prepare_answer_exploration(a, ctx):
    value, ports = await _estimate(ctx, a['estimate_id'])
    targets = [ports.target(p, 'outputs', 'output') for p in a['outputs']]
    data = (
        await send(
            ctx,
            'POST',
            study_path(ctx, 'analysis-estimates', a['estimate_id'], 'preparation'),
            dict(shown_outputs=targets),
            tool='prepare_answer_exploration',
            conflict_step='Inspect get_surrogate and fix coverage or validation.',
        )
    )['data']
    return dict(
        ready=data['ready'],
        groups=[
            dict(
                group=g['group'],
                covered=g['covered'],
                problems=untrusted('publication readiness diagnostics', text=g['problems']),
            )
            for g in data['groups']
        ],
        exploration_basis=dict(
            calculation_version_id=value['calculation_version_id'],
            estimate_id=a['estimate_id'],
            shown_outputs=targets,
        ),
        next_step='Only when ready: put this exploration_basis in update_study_answer and '
        'save_study_answer_version. Publication rechecks the immutable artifacts.',
    )


async def get_answer_exploration(a, ctx):
    value, ports = await _estimate(ctx, a['estimate_id'])
    data = (
        await read(
            ctx,
            study_path(ctx, 'analysis-versions', value['calculation_version_id'], 'exploration'),
            {'estimate_id': a['estimate_id'], 'group': str(a.get('group', 0) + 1)},
        )
    )['data']
    result = dict(
        calculation_version_id=value['calculation_version_id'],
        group=data['group'],
        inputs=[
            dict(
                quantity=ports.view.quantity_ref(p['target']),
                units=p['units'],
                binding=untrusted('saved input binding', text=p['binding']),
            )
            for p in data['inputs']
        ],
        dimensions=[
            dict(
                quantity=ports.view.quantity_ref(d['target']),
                **{k: d[k] for k in ('lower', 'upper', 'units', 'step', 'covary_group')},
            )
            for d in data['dimensions']
        ],
        outputs=[ports.view.quantity_ref(o['target']) for o in data['outputs']],
        calculated_point_count=len(data['points']),
    )

    return cap(
        result,
        [
            ('inputs', 'independent inputs', 'get_model and get_configuration'),
            ('outputs', 'outputs', 'get_model'),
            ('dimensions', 'sampled ranges', 'get_analysis'),
        ],
    )


async def predict_answer(a, ctx):
    value, ports = await _estimate(ctx, a['estimate_id'])
    body = dict(
        selection_token=str(uuid4()),
        group=a.get('group', 0),
        inputs=[
            dict(
                target=ports.target(i['quantity'], 'inputs', 'input'),
                value=i['value'],
                units='' if i['unit'] == 'dimensionless' else i['unit'],
            )
            for i in a['inputs']
        ],
        axis=ports.target(a['axis'], 'axis', 'input') if a.get('axis') else None,
        curve_points=a.get('curve_points', 0),
    )
    data = (
        await send(
            ctx,
            'POST',
            study_path(ctx, 'analysis-estimates', a['estimate_id'], 'predictions'),
            body,
            tool='predict_answer',
            conflict_step='Use the full explicit input vector within the prepared domain.',
        )
    )['data']
    return cap(
        dict(
            points=[
                dict(
                    inputs=[
                        dict(
                            quantity=ports.view.quantity_ref(i['target']),
                            value=i['value'],
                            units=i['units'],
                        )
                        for i in p['inputs']
                    ],
                    outputs=[
                        dict(
                            quantity=ports.view.quantity_ref(o['target']),
                            value=o['value'],
                            units=o['units'],
                            kind=o['kind'],
                            run_id=o['run_id'],
                            diagnostic=untrusted('prediction diagnostic', text=o['reason']),
                        )
                        for o in p['outputs']
                    ],
                )
                for p in data['points']
            ]
        ),
        [('points', 'predictions', 'predict_answer with fewer curve_points')],
    )


async def wait_for_runs(a, ctx):
    result = await get_run_status({'run_ids': a['run_ids']}, ctx)
    for _ in range(a.get('wait_seconds', 20) // 2):
        if not any(
            r['state'] in WAITING_STATES and r['state'] != 'uncertain'
            for r in result.get('runs', [])
        ):
            break
        await asyncio.sleep(2)
        result = await get_run_status({'run_ids': a['run_ids']}, ctx)
    return result


def tool(
    name,
    title,
    description,
    schema,
    handler,
    operations,
    *,
    effect='read',
    outcome='none',
    attribution_kind=None,
):
    return ToolSpec(
        name=name,
        title=title,
        description=description + GUIDE,
        input_schema=schema,
        effect=effect,
        stage='runs',
        surfaces=SURFACES,
        owners=('calculations', 'configuration', 'modeling', 'history', 'store'),
        outcome=outcome,
        activity_label=title,
        handler=handler,
        api_operations=operations,
        attribution_kind=attribution_kind,
    )


VERSION_INPUT = obj(
    dict(calculation_version_id=uuid_schema('Exact saved analysis version.'), wait_seconds=WAIT),
    ('calculation_version_id',),
)
ESTIMATE_INPUT = obj(
    dict(estimate_id=uuid_schema('The estimate from get_analysis_execution.')), ('estimate_id',)
)
TOOLS = (
    tool(
        'wait_for_runs',
        'Wait for recorded runs',
        'Waits up to 20 seconds using lightweight status reads. Does not submit or retry '
        'runs. Recorded is not synonymous with scientific validity; inspect get_run_results.',
        obj(
            dict(run_ids=GET_RUN_STATUS.input_schema['properties']['run_ids'], wait_seconds=WAIT),
            ('run_ids',),
        ),
        wait_for_runs,
        GET_RUN_STATUS.api_operations,
    ),
    tool(
        'create_sampled_analysis',
        'Prepare sampled analysis',
        'Creates a distinct analysis or a new version of the same investigation. Explicit '
        'joint ranges, units, seed and sample counts; no hidden input values. Use '
        'boundary_latin_hypercube for full-box exploration: training_count includes all '
        '2^d independent corners plus interior points. validation_count is the held-out pool: '
        'one point selects the method and the rest independently validate it. '
        'Set tolerances before launch: absolute in each output unit, relative as a fraction. '
        'Null/omitted tolerances means no surrogate. Save explicit input vectors with '
        'provenance first. For revision supply calculation_id and expected_revision together. '
        'Capacity is 128 total training plus validation points across all groups (64 each per group). '
        'Check the requested total before sending. Refine ranges or create a new version after '
        'reviewing failed targets; preserve independent validation and tolerances. '
        'Bind every criterion this analysis will assess before launch. '
        'Returns an operation; poll get_sampling_status. Never loosen accuracy to publish.',
        obj(
            dict(
                model_id=uuid_schema('Model.'),
                model_version_id=uuid_schema('Saved model.'),
                name=dict(TEXT, minLength=1, maxLength=256),
                description=TEXT,
                method=dict(type='string', enum=['boundary_latin_hypercube', 'latin_hypercube']),
                seed=dict(type='integer', minimum=0, maximum=2**32 - 1),
                groups=array(GROUP, 8, 1),
                tolerances=array(TOLERANCE, 32, 1),
                range_provenance=TEXT,
                calculation_id=uuid_schema('Analysis to revise.'),
                expected_revision=uuid_schema('Its latest version from get_analysis.'),
            ),
            ('model_id', 'model_version_id', 'name', 'method', 'seed', 'groups'),
        ),
        create_sampled_analysis,
        (REVISION, CONFIGURATION, SAMPLES),
        effect='record',
        outcome='receipt:calculation_sample',
        attribution_kind='calculation_sample',
    ),
    tool(
        'get_sampling_status',
        'Read sampling progress',
        'Reads design generation and saved configurations. Does not launch model runs.',
        obj(
            dict(operation_id=uuid_schema('Sampling operation.'), wait_seconds=WAIT),
            ('operation_id',),
        ),
        get_sampling_status,
        (SAMPLE,),
    ),
    tool(
        'launch_analysis',
        'Launch analysis',
        'Authorizes the exact finite saved analysis and its frozen surrogate plan. Reuses '
        'pinned runs and automatically admits missing runs within bounded queue capacity, '
        'continuing beyond this reasoning session. Poll get_analysis_execution. Uncertain '
        'runs require reconciliation; changing fit settings requires a new version.',
        obj(
            dict(calculation_version_id=uuid_schema('Saved analysis version.')),
            ('calculation_version_id',),
        ),
        launch_analysis,
        (LAUNCH, RECOVERY),
        effect='submit',
        outcome='receipt:analysis_execution',
    ),
    tool(
        'get_analysis_execution',
        'Read analysis progress',
        'Reads real execution progress and the estimate id. Complete means the frozen '
        'validation plan passed; physical applicability still needs engineering review. '
        'In the embedded Assistant, an active analysis keeps this call pending beyond '
        'wait_seconds until it settles; HYPRN shows live progress and resumes reasoning '
        'automatically without repeated inference requests.',
        VERSION_INPUT,
        get_analysis_execution,
        (EXECUTION, RECOVERY),
    ),
    tool(
        'resume_analysis',
        'Resume analysis',
        'Resumes the same accepted plan only when get_analysis_execution reports can_resume. '
        'Reuses accepted runs and unchanged accuracy targets; never creates new versions or '
        'reruns completed work. For uncertain runs it requests a native-owner absence check; '
        'only proven unstarted work can continue. A refusal never permits manual member submission. '
        'After uncertain delivery, reconcile the original command and read analysis progress.',
        obj(dict(calculation_version_id=uuid_schema('Recoverable saved analysis version.')),
            ('calculation_version_id',)),
        resume_analysis,
        (RESUME,),
        effect='submit',
        outcome='receipt:analysis_resume',
    ),
    tool(
        'get_surrogate',
        'Read surrogate validation',
        'Reads selected methods, reserved training/selection/independent-validation counts, '
        'actual assessed counts, largest error, RMSE and '
        'declared tolerances. Failed validation never becomes a usable estimate.',
        ESTIMATE_INPUT,
        get_surrogate,
        (ESTIMATE, VERSION, REVISION),
    ),
    tool(
        'prepare_answer_exploration',
        'Check exploration readiness',
        'Checks joint boundary coverage and independent validation of every shown output '
        'in every group. Returns the exact exploration_basis for the saved answer. '
        'This checks numerical support, not physical validity or a uniform error proof.',
        obj(
            dict(estimate_id=uuid_schema('Checked estimate.'), outputs=array(PATH, 16, 1)),
            ('estimate_id', 'outputs'),
        ),
        prepare_answer_exploration,
        (ESTIMATE, VERSION, REVISION, PREPARATION),
    ),
    tool(
        'get_answer_exploration',
        'Read exploration inputs',
        'Reads independent inputs, fixed assignments and joint ranges from the exact '
        'analysis and estimate. Group is zero-based. No model execution.',
        obj(
            dict(
                estimate_id=uuid_schema('Checked estimate.'),
                group=dict(type='integer', minimum=0, maximum=7),
            ),
            ('estimate_id',),
        ),
        get_answer_exploration,
        (ESTIMATE, VERSION, REVISION, EXPLORATION),
    ),
    tool(
        'predict_answer',
        'Read checked predictions',
        'Evaluates the already checked surrogate for a complete explicit independent input '
        'vector, returning calculated or estimated outputs with reasons when unavailable. '
        'Never runs candidate code, samples or refits. Optional axis returns a slice with '
        'other inputs held at the supplied values. Stay inside the prepared joint domain.',
        obj(
            dict(
                estimate_id=uuid_schema('Checked estimate.'),
                group=dict(type='integer', minimum=0, maximum=7),
                inputs=array(
                    obj(
                        dict(quantity=PATH, value=NUMBER, unit=dict(type='string', maxLength=64)),
                        ('quantity', 'value', 'unit'),
                    ),
                    1000,
                    1,
                ),
                axis=PATH,
                curve_points=dict(type='integer', minimum=0, maximum=32),
            ),
            ('estimate_id', 'inputs'),
        ),
        predict_answer,
        (ESTIMATE, VERSION, REVISION, PREDICT),
    ),
)
