"""Sampling tools use the public owners and preserve run admission and frozen plans.

The modeling fixture is synthetic. Numerical checks remain covered by native execution
and by the live managed-assistant journey; these tests do not claim fitting accuracy.
"""

import time

from hyprn_mvp_app.agent_tools.registry import REGISTRY
from hyprn_mvp_app.agent_tools.spec import ToolError
from hyprn_mvp_app.agent_tools.catalogue.exploration import sample_projection
from test_agent_calculation_tools import env, VERSION, calculation  # noqa: F401
from test_calculation_designs_api import RUNTIME
from writer_tools import one, attributed

READ_TOOLS = {
    'get_sampling_status',
    'get_analysis_execution',
    'get_surrogate',
    'get_answer_exploration',
    'wait_for_runs',
}


def test_sampling_tools_resolve_exact_ports_and_freeze_accuracy_through_public_api(env):
    env['store'].publish_execution_observation('ready', None, time.time(), RUNTIME)
    args = dict(
        model_id=env['model'],
        model_version_id=VERSION,
        name='Joint range exploration',
        method='boundary_latin_hypercube',
        seed=42,
        groups=[
            dict(
                configuration_version_id=env['configurations'][0],
                training_count=5,
                validation_count=2,
                dimensions=[
                    dict(quantity='Range.fuel_fraction', lower=0.2, upper=0.4, unit='dimensionless')
                ],
            )
        ],
        tolerances=[dict(output='Range.range', absolute=1, relative=0.001)],
    )
    value = one(env, 'create_sampled_analysis', args)
    assert not isinstance(value, ToolError), (
        value.envelope() if isinstance(value, ToolError) else value
    )
    assert value['state'] == 'pending'
    status = one(env, 'get_sampling_status', {'operation_id': value['operation_id']})
    assert status == value
    receipt = env['store'].receipt(
        env['owner'], env['sid'], 'calculation_sample', value['operation_id']
    )
    request = receipt['result']['request']
    assert request['estimate_plan']['tolerances'][0]['relative'] == 0.001
    rows = attributed(env)
    assert any(r[0] == 'calculation_sample' for r in rows)
    args['groups'][0]['dimensions'][0]['quantity'] = 'Range.not_an_input'
    refused = one(env, 'create_sampled_analysis', args)
    assert isinstance(refused, ToolError) and refused.category == 'invalid_input'


def test_analysis_launch_accepts_missing_runs_as_one_durable_finite_plan(env):
    created = one(env, 'create_analysis', calculation(env))
    vid = created['calculation_version']['id']
    assert one(env, 'get_analysis_execution', {'calculation_version_id': vid}) == {
        'state': 'not_launched'
    }
    accepted = one(env, 'launch_analysis', {'calculation_version_id': vid})
    assert not isinstance(accepted, ToolError), accepted
    assert accepted['state'] == 'calculating'
    assert accepted['total_count'] == 1
    assert one(env, 'launch_analysis', {'calculation_version_id': vid}) == accepted
    assert one(env, 'get_analysis_execution', {'calculation_version_id': vid}) == accepted
    from hyprn_mvp_app.calculations import Calculations

    saved = Calculations(env['store']).version(env['owner'], env['sid'], vid)
    assert saved['schema_version'] == '4' and saved['content']['estimate_plan'] is None


def test_accepted_analysis_outlives_delegation_expiry_but_not_revocation(env):
    from hyprn_mvp_app.analysis_execution import AnalysisExecution
    from hyprn_mvp_app.execution import Submissions

    created = one(env, 'create_analysis', calculation(env))
    vid = created['calculation_version']['id']
    accepted = one(env, 'launch_analysis', {'calculation_version_id': vid})
    assert not isinstance(accepted, ToolError), accepted
    with env['store'].connection(write=True) as db:
        db.execute('UPDATE agent_delegations SET expires_at=? WHERE agent_actor_id=?',
                   (time.time() - 1, env['agent']))
    owner = AnalysisExecution(env['store'])
    assert owner.process_one(Submissions(env['store'], None, None))
    state = owner.read(env['owner'], env['sid'], vid)
    assert state['runs'][0]['run_id'] is not None
    with env['store'].connection(write=True) as db:
        db.execute('UPDATE agent_delegations SET revoked_at=?,revoked_reason=? '
                   'WHERE agent_actor_id=?', (time.time(), 'owner_revoked', env['agent']))
    assert owner.process_one(Submissions(env['store'], None, None))
    assert owner.read(env['owner'], env['sid'], vid)['admission_state'] == 'revoked'


def test_durable_analysis_authority_refuses_other_studies_and_commands_and_does_not_escape(env):
    import pytest
    from uuid import uuid4
    from hyprn_mvp_app.analysis_execution import identity
    from hyprn_mvp_app.contracts import DomainError

    vid = one(env, 'create_analysis', calculation(env))['calculation_version']['id']
    accepted = one(env, 'launch_analysis', {'calculation_version_id': vid})
    assert not isinstance(accepted, ToolError), accepted
    with env['store'].connection(write=True) as db:
        db.execute('UPDATE agent_delegations SET expires_at=? WHERE agent_actor_id=?',
                   (time.time() - 1, env['agent']))
    with env['store'].analysis_authority(env['agent'], env['sid'], identity(vid)):
        with env['store'].connection() as db:
            env['store'].authorize(db, env['agent'], env['sid'], write=True)
            with pytest.raises(DomainError):
                env['store'].authorize(db, env['agent'], str(uuid4()), write=True)
        with pytest.raises(DomainError):
            env['store'].command(env['agent'], env['sid'], 'run', str(uuid4()), {}, lambda db: {})
    with env['store'].connection() as db:
        with pytest.raises(DomainError):
            env['store'].authorize(db, env['agent'], env['sid'], write=True)


def test_background_sampling_keeps_agent_attribution_in_a_separate_store(env):
    from hyprn_mvp_app.calculation_designs import CalculationSamples
    from hyprn_mvp_app.configuration import Configurations
    from hyprn_mvp_app.dispatcher import open_dispatcher_store
    from test_calculation_designs_api import DesignTransport

    env['store'].publish_execution_observation('ready', None, time.time(), RUNTIME)
    request = dict(
        model_id=env['model'],
        model_version_id=VERSION,
        name='Independent background design',
        method='latin_hypercube',
        seed=42,
        groups=[
            dict(
                configuration_version_id=env['configurations'][0],
                training_count=5,
                validation_count=2,
                dimensions=[
                    dict(quantity='Range.fuel_fraction', lower=0, upper=10, unit='dimensionless')
                ],
            )
        ],
    )
    accepted = one(env, 'create_sampled_analysis', request)
    background = open_dispatcher_store(env['store'].path)
    samples = CalculationSamples(background, Configurations(background, None))
    native = DesignTransport()
    assert samples.process_one(native)
    assert samples.process_one(native)
    status = one(env, 'get_sampling_status', {'operation_id': accepted['operation_id']})
    assert status['state'] == 'complete', status
    assert status['point_count'] == 7
    assert len([row for row in attributed(env) if row[0] == 'configuration_version']) >= 9


def test_sampling_projection_is_an_allowlist_and_diagnostics_are_untrusted():
    value = dict(
        operation_id='operation',
        state='pending',
        point_count=7,
        retained_count=0,
        calculation_id=None,
        calculation_version_id=None,
        reason='user text',
        runtime={'secret': 'not exposed'},
        surprise='not exposed',
    )
    result = sample_projection(value)
    assert 'surprise' not in result and 'runtime' not in result
    assert result['diagnostic']['untrusted_content']['text'] == 'user text'


def test_new_read_surfaces_are_registered_and_have_closed_inputs():
    for name in READ_TOOLS:
        tool = REGISTRY.tool(name)
        assert tool.effect == 'read'
        assert tool.input_schema['additionalProperties'] is False
        assert all(method == 'GET' for method, _ in tool.api_operations)


def test_sampling_capacity_is_reported_before_a_design_is_sent(env):
    args = dict(model_id=env['model'], model_version_id=VERSION, name='Oversized design',
        method='latin_hypercube', seed=42,
        groups=[dict(configuration_version_id=env['configurations'][0],
                     training_count=64, validation_count=2,
                     dimensions=[dict(quantity='Range.fuel_fraction', lower=0.2, upper=0.4,
                                      unit='dimensionless')])] * 2)
    value = one(env, 'create_sampled_analysis', args)
    assert isinstance(value, ToolError)
    assert value.category == 'invalid_input'
    assert '132' in str(value.envelope()) and '128' in str(value.envelope())
    with env['store'].connection() as db:
        assert db.execute("SELECT count(*) FROM receipts WHERE category='calculation_sample'").fetchone()[0] == 0
