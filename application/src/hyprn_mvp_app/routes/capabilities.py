"""The global capability read: versions, capability identifiers, limits and what is unavailable."""
from typing import Annotated
from fastapi import APIRouter, Depends, Request
from ..contracts import EXECUTION_WALL_DEFAULT, EXECUTION_WALL_MAX
from ..computational_export import LIMITS as RECORD_LIMITS
from ..edge import delegated_scope, response

def router(deps):
    store,configs,coordinator=deps.store,deps.configs,deps.coordinator
    CurrentSession=Annotated[dict,Depends(deps.current_session)]
    r=APIRouter()

    @r.get("/api/1/capabilities")
    def capabilities(request:Request,current:CurrentSession):
        # The global route has no study selector. Probe through an authorized study;
        # every concrete operation negotiates again with its own current scope.
        who=current["actor_id"]
        studies=delegated_scope(current,store.list_studies(who))
        caps=configs.native_capabilities(who,studies[0]["study_id"]) if studies else None
        assumptions=bool(caps and '1.2' in caps['contract_versions'] and '2' in caps['schema_versions'] and
            any(c['id']=='model_assumptions' and c['version']=='1' and c['supported'] for c in caps['capabilities']))
        # New configurations are version 6 only: discovery advertises them, and the
        # assumptions they carry, only when the modeling service supports both.
        configuration6=configs.supports3(caps) and configs.supports_criteria_free(caps)
        units=coordinator.supports_units(caps)
        quantities=coordinator.supports_quantities(caps)
        return response(
            request,
            dict(
                contract_versions=[
                    '1',
                    '1.1',
                    'prepared_artifact/2',
                    'execution_bundle/2',
                    'execution_bundle/3',
                    'hyprn_mvp.openmdao.program/1',
                    'computational_record/1',
                ]
                + (['configuration/6', 'execution_bundle/11'] if configuration6 else [])
                + (['model/3'] if units else [])
                + (['model/4'] if quantities else []),
                engineering=[
                    'flat_explicit_scalar',
                    'result_linked_inputs/1',
                    'evidence_revisions/1',
                    'study_archive/1',
                ]
                + (['configuration_assumptions/1'] if configuration6 else []),
                modeling=['model_revision_listing', 'model_rename']
                + (['model_assumptions/1'] if assumptions else [])
                + (['unit_declarations/1'] if units else [])
                + (['quantity_definitions/1'] if quantities else []),
                execution='durable_scalar_submission',
                execution_budget=dict(
                    default_wall_seconds=EXECUTION_WALL_DEFAULT,
                    min_wall_seconds=1,
                    max_wall_seconds=EXECUTION_WALL_MAX,
                    includes_startup=True,
                ),
                model_formats=dict(
                    create_request=['3'],
                    edit_request=['4'] if quantities else ['3'],
                    saved_record=['4'] if quantities else ['3'],
                ),
                unavailable=([] if quantities else ['quantity_definitions/1'])
                + ([] if units else ['unit_declarations/1'])
                + ([] if assumptions else ['model_assumptions/1'])
                + ([] if configuration6 else ['configuration_assumptions/1'])
                + [
                    'documents',
                    'membership_management',
                    'nested_composition',
                    'selective_rebind',
                    'coupled',
                    'optimization',
                    'uncertainty',
                    'cancellation',
                    'assistance',
                ],
                limits=dict(
                    request_bytes=2 * 1024 * 1024,
                    source_bytes=256 * 1024,
                    edits=256,
                    elements=1000,
                    depth=32,
                    result_source_outputs=50,
                    result_source_runs=100,
                    result_source_bindings=1000,
                    result_source_dependencies=64,
                    computational_record=RECORD_LIMITS,
                ),
            ),
        )

    return r
