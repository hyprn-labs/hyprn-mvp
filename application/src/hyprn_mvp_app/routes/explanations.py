"""Model explanations through ordinary model authorization: state, draft, saved versions and
the explanation of one model version."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Request

from ..contracts import DomainError
from ..edge import response, valid_id
from ..explanations import Explanations, validate_explanation

BASE = '/api/1/studies/{study_id}/models/{model_id}'


def router(deps):
    explanations = Explanations(deps.store, deps.coordinator)
    Actor = Annotated[str, Depends(deps.actor)]
    r = APIRouter()

    def result(request, name, value, status=200):
        validate_explanation(name, value, retained=True)
        return response(request, value, status)

    def scope(request, who, study_id, model_id, allowed=()):
        sid, mid = valid_id(study_id), valid_id(model_id)
        with deps.store.connection() as db:
            deps.store.model_association(db, who, sid, mid)
        pairs = list(request.query_params.multi_items())
        if any(key not in allowed for key, _ in pairs) or len({k for k, _ in pairs}) != len(pairs):
            raise DomainError('invalid_request', 400)
        return sid, mid, dict(pairs)

    def positive(value, upper):
        if not value.isascii() or not value.isdecimal() or len(value) > 16:
            raise DomainError('invalid_request', 400)
        number = int(value)
        if not 1 <= number <= upper:
            raise DomainError('invalid_request', 400)
        return number

    @r.get(BASE + '/explanation')
    def explanation_state(study_id: str, model_id: str, request: Request, who: Actor):
        sid, mid, _ = scope(request, who, study_id, model_id)
        return result(request, 'ModelExplanationStateRead3', explanations.state(who, sid, mid))

    @r.post(BASE + '/explanation/draft')
    def explanation_draft(
        study_id: str, model_id: str, request: Request, who: Actor, body: dict = Body(...)
    ):
        sid, mid, _ = scope(request, who, study_id, model_id)
        return result(
            request, 'ModelExplanationDraftRead3', explanations.save_draft(who, sid, mid, body)
        )

    @r.get(BASE + '/explanation/versions')
    def explanation_versions(study_id: str, model_id: str, request: Request, who: Actor):
        sid, mid, query = scope(request, who, study_id, model_id, ('limit', 'before'))
        page = explanations.versions(
            who,
            sid,
            mid,
            limit=positive(query['limit'], 100) if 'limit' in query else 20,
            before=positive(query['before'], 9007199254740991) if 'before' in query else None,
        )
        return result(request, 'ModelExplanationVersionPageRead3', page)

    @r.post(BASE + '/explanation/versions', status_code=201)
    def explanation_save_version(
        study_id: str, model_id: str, request: Request, who: Actor, body: dict = Body(...)
    ):
        sid, mid, _ = scope(request, who, study_id, model_id)
        saved = explanations.save_version(who, sid, mid, body)
        return result(request, 'ModelExplanationVersionSavedRead3', saved, 201)

    @r.get(BASE + '/revisions/{revision_id}/explanation')
    def model_version_explanation(
        study_id: str, model_id: str, revision_id: str, request: Request, who: Actor
    ):
        sid, mid, _ = scope(request, who, study_id, model_id)
        value = explanations.of_model_version(who, sid, mid, valid_id(revision_id))
        return result(request, 'ModelVersionExplanationRead3', value)

    return r
