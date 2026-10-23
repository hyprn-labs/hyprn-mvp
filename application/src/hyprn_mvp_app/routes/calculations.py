"""Calculations, their runs, sampled versions, estimates and reference marks through ordinary
study authorization."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Request

from ..calculation_designs import CalculationSamples, validate as validate_sampling
from ..calculation_estimates import Estimates, validate as validate_estimate
from ..calculation_exploration import CalculationExploration
from ..calculation_preparation import preparation
from ..analysis_execution import AnalysisExecution
from ..calculations import RUN_PAGE, Analyses, validate_calculation
from ..contracts import DomainError
from ..edge import response, valid_id


def router(deps):
    calculations = Analyses(deps.store)
    samples = CalculationSamples(deps.store, deps.configs)
    estimates = Estimates(deps.store)
    exploration = CalculationExploration(deps.store)
    Actor = Annotated[str, Depends(deps.actor)]
    r = APIRouter()

    def result(request, name, value, status=200):
        validate_calculation(name, value, retained=True)
        return response(request, value, status)

    def scope(request, who, study_id, allowed=()):
        sid = valid_id(study_id)
        with deps.store.connection() as db:
            deps.store.authorize(db, who, sid)
        pairs = list(request.query_params.multi_items())
        if any(key not in allowed for key, _ in pairs) or len({k for k, _ in pairs}) != len(
            pairs
        ):
            raise DomainError('invalid_request', 400)
        return sid, dict(pairs)

    def positive(value, upper):
        if not value.isascii() or not value.isdecimal() or len(value) > 16:
            raise DomainError('invalid_request', 400)
        number = int(value)
        if not 1 <= number <= upper:
            raise DomainError('invalid_request', 400)
        return number

    def cursor(query, key):
        return positive(query[key], 9007199254740991) if key in query else None

    @r.get('/api/1/studies/{study_id}/calculations')
    def calculation_list(study_id: str, request: Request, who: Actor):
        sid, query = scope(request, who, study_id, ('limit', 'after', 'model_revision_id'))
        page = calculations.list(
            who,
            sid,
            limit=positive(query['limit'], 100) if 'limit' in query else 20,
            after=cursor(query, 'after'),
            model_revision_id=(
                valid_id(query['model_revision_id']) if 'model_revision_id' in query else None
            ),
        )
        return result(request, 'CalculationPage4', page)

    @r.post('/api/1/studies/{study_id}/calculations', status_code=201)
    def calculation_create(study_id: str, request: Request, who: Actor, body: dict = Body(...)):
        sid, _ = scope(request, who, study_id)
        return result(
            request, 'CalculationVersionRead4', calculations.create(who, sid, body), 201
        )

    @r.get('/api/1/studies/{study_id}/calculations/{calculation_id}')
    def calculation_read(study_id: str, calculation_id: str, request: Request, who: Actor):
        sid, _ = scope(request, who, study_id)
        return result(
            request, 'Calculation4', calculations.read(who, sid, valid_id(calculation_id))
        )

    @r.get('/api/1/studies/{study_id}/calculations/{calculation_id}/versions')
    def calculation_versions(study_id: str, calculation_id: str, request: Request, who: Actor):
        sid, query = scope(request, who, study_id, ('limit', 'before'))
        page = calculations.versions(
            who,
            sid,
            valid_id(calculation_id),
            limit=positive(query['limit'], 100) if 'limit' in query else 20,
            before=cursor(query, 'before'),
        )
        return result(request, 'CalculationVersionPage4', page)

    @r.post('/api/1/studies/{study_id}/calculations/{calculation_id}/versions', status_code=201)
    def calculation_save_version(
        study_id: str, calculation_id: str, request: Request, who: Actor, body: dict = Body(...)
    ):
        sid, _ = scope(request, who, study_id)
        version = calculations.save_version(who, sid, valid_id(calculation_id), body)
        return result(request, 'CalculationVersionRead4', version, 201)

    @r.get('/api/1/studies/{study_id}/calculation-versions/{version_id}')
    def calculation_version(study_id: str, version_id: str, request: Request, who: Actor):
        sid, _ = scope(request, who, study_id)
        version = calculations.version(who, sid, valid_id(version_id))
        return result(request, 'CalculationVersionRead4', version)

    @r.get('/api/1/studies/{study_id}/calculation-versions/{version_id}/execution')
    def analysis_execution(study_id: str, version_id: str, request: Request, who: Actor):
        sid, _ = scope(request, who, study_id)
        return result(request, 'AnalysisExecutionRead3',
                      AnalysisExecution(deps.store).read(who, sid, valid_id(version_id)))

    @r.post('/api/1/studies/{study_id}/calculation-versions/{version_id}/execution', status_code=202)
    def analysis_launch(study_id: str, version_id: str, request: Request, who: Actor,
                        body: dict = Body(...)):
        sid, _ = scope(request, who, study_id)
        return result(request, 'AnalysisExecutionResult3',
                      AnalysisExecution(deps.store).launch(who, sid, valid_id(version_id), body), 202)

    @r.get('/api/1/studies/{study_id}/calculation-versions/{version_id}/execution/recovery')
    def analysis_recovery(study_id: str, version_id: str, request: Request, who: Actor):
        sid, _ = scope(request, who, study_id)
        return result(request, 'AnalysisExecutionRecovery1',
                      AnalysisExecution(deps.store).recovery(who, sid, valid_id(version_id)))

    @r.post('/api/1/studies/{study_id}/calculation-versions/{version_id}/execution/resume', status_code=202)
    def analysis_resume(study_id: str, version_id: str, request: Request, who: Actor,
                        body: dict = Body(...)):
        sid, _ = scope(request, who, study_id)
        return result(request, 'AnalysisExecutionResult3',
                      AnalysisExecution(deps.store).resume(who, sid, valid_id(version_id), body), 202)

    @r.post('/api/1/studies/{study_id}/calculation-versions/{version_id}/execution/cancellation')
    def analysis_cancel(study_id: str, version_id: str, request: Request, who: Actor,
                        body: dict = Body(...)):
        sid, _ = scope(request, who, study_id)
        return result(request, 'AnalysisExecutionRead3',
                      AnalysisExecution(deps.store).cancel(who, sid, valid_id(version_id), body))

    @r.get('/api/1/studies/{study_id}/calculation-versions/{version_id}/runs')
    def calculation_runs(study_id: str, version_id: str, request: Request, who: Actor):
        sid, query = scope(request, who, study_id, ('limit', 'after', 'configuration_revision_id'))
        page = calculations.runs(
            who,
            sid,
            valid_id(version_id),
            limit=positive(query['limit'], RUN_PAGE) if 'limit' in query else RUN_PAGE,
            after=cursor(query, 'after'),
            configuration_revision_id=(
                valid_id(query['configuration_revision_id'])
                if 'configuration_revision_id' in query else None
            ),
        )
        return result(request, 'CalculationRunPage1', page)

    @r.post('/api/1/studies/{study_id}/calculation-versions/{version_id}/run-requests')
    def calculation_run_requests(
        study_id: str, version_id: str, request: Request, who: Actor, body: dict = Body(...)
    ):
        sid, _ = scope(request, who, study_id)
        value = samples.request_runs(who, sid, valid_id(version_id), body, deps.submissions)
        validate_sampling('CalculationRunRequestResult1', value, retained=True)
        return response(request, value)

    @r.get('/api/1/studies/{study_id}/calculation-samples')
    def calculation_sample_list(study_id: str, request: Request, who: Actor):
        sid, _ = scope(request, who, study_id)
        value = samples.page(who, sid)
        validate_sampling('CalculationSamplePage4', value, retained=True)
        return response(request, value)

    @r.post('/api/1/studies/{study_id}/calculation-samples', status_code=202)
    def calculation_sample(study_id: str, request: Request, who: Actor, body: dict = Body(...)):
        sid, _ = scope(request, who, study_id)
        return response(request, samples.submit(who, sid, body), 202)

    @r.get('/api/1/studies/{study_id}/calculation-samples/{operation_id}')
    def calculation_sample_status(
        study_id: str, operation_id: str, request: Request, who: Actor
    ):
        sid, _ = scope(request, who, study_id)
        return response(request, samples.status(who, sid, valid_id(operation_id)))

    @r.get('/api/1/studies/{study_id}/calculation-versions/{version_id}/estimates')
    def calculation_estimate_list(study_id: str, version_id: str, request: Request, who: Actor):
        sid, query = scope(request, who, study_id, ('cursor',))
        value = estimates.page(
            who,
            sid,
            valid_id(version_id),
            valid_id(query['cursor']) if 'cursor' in query else None,
        )
        validate_estimate('CalculationEstimatePage2', value, retained=True)
        return response(request, value)

    @r.post('/api/1/studies/{study_id}/calculation-estimates', status_code=202)
    def calculation_estimate(
        study_id: str, request: Request, who: Actor, body: dict = Body(...)
    ):
        sid, _ = scope(request, who, study_id)
        return response(request, estimates.build(who, sid, body), 202)

    @r.get('/api/1/studies/{study_id}/calculation-estimates/{estimate_id}')
    def calculation_estimate_read(
        study_id: str, estimate_id: str, request: Request, who: Actor
    ):
        sid, _ = scope(request, who, study_id)
        return response(request, estimates.read(who, sid, valid_id(estimate_id)))

    @r.post('/api/1/studies/{study_id}/calculation-estimates/{estimate_id}/preparation')
    def calculation_preparation(
        study_id: str, estimate_id: str, request: Request, who: Actor, body: dict = Body(...)
    ):
        sid, _ = scope(request, who, study_id)
        return response(request, preparation(deps.store, who, sid, valid_id(estimate_id), body))

    @r.get('/api/1/studies/{study_id}/calculation-versions/{version_id}/exploration')
    def calculation_exploration(study_id: str, version_id: str, request: Request, who: Actor):
        sid, query = scope(request, who, study_id, ('group', 'estimate_id'))
        group = positive(query['group'], 10000) - 1 if 'group' in query else 0
        value = exploration.basis(
            who,
            sid,
            valid_id(version_id),
            group=group,
            estimate_id=valid_id(query['estimate_id']) if 'estimate_id' in query else None,
        )
        return response(request, value)

    @r.post('/api/1/studies/{study_id}/calculation-estimates/{estimate_id}/predictions')
    def calculation_prediction(
        study_id: str, estimate_id: str, request: Request, who: Actor, body: dict = Body(...)
    ):
        sid, _ = scope(request, who, study_id)
        return response(request, exploration.query(who, sid, valid_id(estimate_id), body))

    @r.get('/api/1/studies/{study_id}/reference-marks')
    def reference_marks(study_id: str, request: Request, who: Actor):
        sid, query = scope(request, who, study_id, ('model_id',))
        model = valid_id(query['model_id']) if 'model_id' in query else None
        return result(
            request, 'ReferenceMarkList1', calculations.marks(who, sid, model_id=model)
        )

    @r.post('/api/1/studies/{study_id}/reference-marks')
    def reference_mark(study_id: str, request: Request, who: Actor, body: dict = Body(...)):
        sid, _ = scope(request, who, study_id)
        return result(request, 'ReferenceMarkState1', calculations.mark(who, sid, body))

    # Canonical domain routes share handlers, auth, receipts and the single writer.
    # Retained calculation_* payload keys and earlier URLs remain compatible.
    for route in tuple(r.routes):
        if '/calculation' not in route.path:
            continue
        path = route.path.replace('/calculations', '/analyses').replace(
            '/calculation-', '/analysis-'
        )
        r.add_api_route(
            path, route.endpoint, methods=list(route.methods),
            status_code=route.status_code, name=route.name.replace('calculation', 'analysis'),
        )
    return r
