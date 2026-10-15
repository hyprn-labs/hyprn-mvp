"""Exact answer-bound exploration reads through ordinary study authorization."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from ..contracts import DomainError
from ..edge import response, valid_id
from ..exploration import Explorations
from ..sampling import Samples
from ..exploration_design import Designs
from ..surrogates import Surrogates


def router(deps):
    explorations = Explorations(deps.store, deps.configs)
    samples = Samples(deps.store, deps.configs, deps.submissions)
    designs = Designs(deps.store, deps.configs)
    surrogates = Surrogates(deps.store, deps.configs)
    Actor = Annotated[str, Depends(deps.actor)]
    r = APIRouter()

    @r.get('/api/1/studies/{study_id}/exploration-surrogates')
    def surrogate_list(
        study_id: str,
        answer_version_id: str,
        request: Request,
        who: Actor,
        cursor: str | None = None,
    ):
        if set(request.query_params) - {'answer_version_id', 'cursor'} or any(
            len(request.query_params.getlist(k)) != 1 for k in request.query_params
        ):
            raise DomainError('invalid_request', 400)
        items, next_cursor = surrogates.page(
            who,
            valid_id(study_id),
            valid_id(answer_version_id),
            valid_id(cursor) if cursor else None,
        )
        return response(request, items, next_cursor=next_cursor)

    @r.post('/api/1/studies/{study_id}/exploration-surrogates', status_code=202)
    def surrogate_build(study_id: str, body: dict, request: Request, who: Actor):
        if request.query_params:
            raise DomainError('invalid_request', 400)
        return response(request, surrogates.build(who, valid_id(study_id), body), 202)

    @r.get('/api/1/studies/{study_id}/exploration-surrogates/{version_id}')
    def surrogate_read(study_id: str, version_id: str, request: Request, who: Actor):
        if request.query_params:
            raise DomainError('invalid_request', 400)
        return response(request, surrogates.read(who, valid_id(study_id), valid_id(version_id)))

    @r.post('/api/1/studies/{study_id}/exploration-surrogates/{version_id}/warm', status_code=202)
    def surrogate_warm(study_id: str, version_id: str, body: dict, request: Request, who: Actor):
        if request.query_params:
            raise DomainError('invalid_request', 400)
        return response(
            request, surrogates.warm(who, valid_id(study_id), valid_id(version_id), body), 202
        )

    @r.get('/api/1/studies/{study_id}/exploration-warm/{command_id}')
    def surrogate_warm_status(study_id: str, command_id: str, request: Request, who: Actor):
        if request.query_params:
            raise DomainError('invalid_request', 400)
        return response(
            request, surrogates.warm_status(who, valid_id(study_id), valid_id(command_id))
        )

    @r.post('/api/1/studies/{study_id}/exploration-surrogates/{version_id}/cancel')
    def surrogate_cancel(study_id: str, version_id: str, body: dict, request: Request, who: Actor):
        if request.query_params:
            raise DomainError('invalid_request', 400)
        return response(
            request, surrogates.cancel(who, valid_id(study_id), valid_id(version_id), body)
        )

    @r.post('/api/1/studies/{study_id}/exploration-surrogates/{version_id}/predictions')
    def surrogate_query(study_id: str, version_id: str, body: dict, request: Request, who: Actor):
        if request.query_params:
            raise DomainError('invalid_request', 400)
        return response(
            request, surrogates.query(who, valid_id(study_id), valid_id(version_id), body)
        )

    @r.get('/api/1/studies/{study_id}/exploration-surrogates/{version_id}/artifacts/{combination}')
    def surrogate_artifact(
        study_id: str, version_id: str, combination: int, request: Request, who: Actor
    ):
        if request.query_params:
            raise DomainError('invalid_request', 400)
        return response(
            request, surrogates.artifact(who, valid_id(study_id), valid_id(version_id), combination)
        )

    @r.get('/api/1/studies/{study_id}/exploration-designs')
    def design_list(
        study_id: str,
        answer_version_id: str,
        request: Request,
        who: Actor,
        cursor: str | None = None,
    ):
        if set(request.query_params) - {'answer_version_id', 'cursor'} or any(
            len(request.query_params.getlist(k)) != 1 for k in request.query_params
        ):
            raise DomainError('invalid_request', 400)
        items, next_cursor = designs.page(
            who,
            valid_id(study_id),
            valid_id(answer_version_id),
            valid_id(cursor) if cursor else None,
        )
        return response(request, items, next_cursor=next_cursor)

    @r.post('/api/1/studies/{study_id}/exploration-designs', status_code=201)
    def design_save(study_id: str, body: dict, request: Request, who: Actor):
        if request.query_params:
            raise DomainError('invalid_request', 400)
        return response(request, designs.save(who, valid_id(study_id), body), 201)

    @r.get('/api/1/studies/{study_id}/exploration-designs/{design_id}')
    def design_read(study_id: str, design_id: str, request: Request, who: Actor):
        if request.query_params:
            raise DomainError('invalid_request', 400)
        return response(request, designs.read(who, valid_id(study_id), valid_id(design_id)))

    @r.get('/api/1/studies/{study_id}/exploration-samples')
    def sample_list(
        study_id: str,
        answer_version_id: str,
        request: Request,
        who: Actor,
        cursor: str | None = None,
    ):
        if set(request.query_params) - {'answer_version_id', 'cursor'} or any(
            len(request.query_params.getlist(k)) != 1 for k in request.query_params
        ):
            raise DomainError('invalid_request', 400)
        items, next_cursor = samples.page(
            who,
            valid_id(study_id),
            valid_id(answer_version_id),
            valid_id(cursor) if cursor else None,
        )
        return response(request, items, next_cursor=next_cursor)

    @r.get('/api/1/studies/{study_id}/exploration-requests')
    def exploration_prepared(
        study_id: str,
        request: Request,
        who: Actor,
        answer_version_id: str,
        configuration_revision_id: str,
        cursor: str | None = None,
    ):
        allowed = {'answer_version_id', 'configuration_revision_id', 'cursor'}
        if set(request.query_params) - allowed or any(
            len(request.query_params.getlist(key)) != 1 for key in request.query_params
        ):
            raise DomainError('invalid_request', 400)
        items, next_cursor = explorations.prepared_page(
            who,
            valid_id(study_id),
            valid_id(answer_version_id),
            valid_id(configuration_revision_id),
            valid_id(cursor) if cursor else None,
        )
        return response(request, items, next_cursor=next_cursor)

    @r.post('/api/1/studies/{study_id}/exploration-requests', status_code=202)
    def exploration_submit(study_id: str, body: dict, request: Request, who: Actor):
        sid = valid_id(study_id)
        with deps.store.connection() as db:
            deps.store.authorize(db, who, sid, write=True)
        if request.query_params:
            raise DomainError('invalid_request', 400)
        return response(request, explorations.submit(who, sid, body), 202)

    @r.get('/api/1/studies/{study_id}/exploration-requests/{request_id}')
    def exploration_status(study_id: str, request_id: str, request: Request, who: Actor):
        if request.query_params:
            raise DomainError('invalid_request', 400)
        return response(request, explorations.status(who, valid_id(study_id), valid_id(request_id)))

    @r.get(
        '/api/1/studies/{study_id}/answers/{answer_version_id}'
        '/exploration-basis/{configuration_revision_id}'
    )
    def exploration_basis(
        study_id: str,
        answer_version_id: str,
        configuration_revision_id: str,
        request: Request,
        who: Actor,
    ):
        sid = valid_id(study_id)
        with deps.store.connection() as db:
            deps.store.authorize(db, who, sid)
        if request.query_params:
            raise DomainError('invalid_request', 400)
        return response(
            request,
            explorations.basis(
                who, sid, valid_id(answer_version_id), valid_id(configuration_revision_id)
            ),
        )

    @r.post('/api/1/studies/{study_id}/exploration-samples/preview')
    def sample_preview(study_id: str, body: dict, request: Request, who: Actor):
        if request.query_params:
            raise DomainError('invalid_request', 400)
        return response(request, samples.preview(who, valid_id(study_id), body))

    @r.post('/api/1/studies/{study_id}/exploration-samples', status_code=202)
    def sample_submit(study_id: str, body: dict, request: Request, who: Actor):
        if request.query_params:
            raise DomainError('invalid_request', 400)
        return response(request, samples.submit(who, valid_id(study_id), body), 202)

    @r.get('/api/1/studies/{study_id}/exploration-samples/{operation_id}')
    def sample_status(study_id: str, operation_id: str, request: Request, who: Actor):
        if request.query_params:
            raise DomainError('invalid_request', 400)
        return response(request, samples.status(who, valid_id(study_id), valid_id(operation_id)))

    @r.post('/api/1/studies/{study_id}/exploration-samples/{operation_id}/controls')
    def sample_control(study_id: str, operation_id: str, body: dict, request: Request, who: Actor):
        if request.query_params:
            raise DomainError('invalid_request', 400)
        return response(
            request, samples.control(who, valid_id(study_id), valid_id(operation_id), body)
        )

    @r.post('/api/1/studies/{study_id}/exploration-samples/{operation_id}/points', status_code=201)
    def sample_adopt(study_id: str, operation_id: str, body: dict, request: Request, who: Actor):
        if request.query_params:
            raise DomainError('invalid_request', 400)
        return response(
            request, samples.adopt(who, valid_id(study_id), valid_id(operation_id), body), 201
        )

    return r
