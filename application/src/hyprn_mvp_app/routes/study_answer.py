"""The study answer through ordinary study authorization: state, draft, saved versions."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Request

from ..study_answer import StudyAnswers, validate_answer
from ..contracts import DomainError
from ..edge import response, valid_id


def router(deps):
    answers = StudyAnswers(deps.store)
    Actor = Annotated[str, Depends(deps.actor)]
    r = APIRouter()

    def result(request, name, value, status=200):
        validate_answer(name, value, retained=True)
        return response(request, value, status)

    def scope(request, who, study_id, allowed=()):
        sid = valid_id(study_id)
        with deps.store.connection() as db:
            deps.store.authorize(db, who, sid)
        pairs = list(request.query_params.multi_items())
        if any(key not in allowed for key, _ in pairs) or len({k for k, _ in pairs}) != len(pairs):
            raise DomainError('invalid_request', 400)
        return sid, dict(pairs)

    def positive(value, upper):
        if not value.isascii() or not value.isdecimal() or len(value) > 16:
            raise DomainError('invalid_request', 400)
        number = int(value)
        if not 1 <= number <= upper:
            raise DomainError('invalid_request', 400)
        return number

    @r.get('/api/1/studies/{study_id}/answer')
    def answer_state(study_id: str, request: Request, who: Actor):
        sid, _ = scope(request, who, study_id)
        return result(request, 'StudyAnswerStateRead3', answers.state(who, sid))

    @r.post('/api/1/studies/{study_id}/answer/draft')
    def answer_draft(study_id: str, request: Request, who: Actor, body: dict = Body(...)):
        sid, _ = scope(request, who, study_id)
        return result(request, 'StudyAnswerDraftRead3', answers.save_draft(who, sid, body))

    @r.get('/api/1/studies/{study_id}/answer/versions')
    def answer_versions(study_id: str, request: Request, who: Actor):
        sid, query = scope(request, who, study_id, ('limit', 'before'))
        page = answers.versions(
            who,
            sid,
            limit=positive(query['limit'], 100) if 'limit' in query else 20,
            before=positive(query['before'], 9007199254740991) if 'before' in query else None,
        )
        return result(request, 'StudyAnswerVersionPageRead3', page)

    @r.post('/api/1/studies/{study_id}/answer/versions', status_code=201)
    def answer_save_version(study_id: str, request: Request, who: Actor, body: dict = Body(...)):
        sid, _ = scope(request, who, study_id)
        return result(
            request, 'StudyAnswerVersionSavedRead3', answers.save_version(who, sid, body), 201
        )

    @r.get('/api/1/studies/{study_id}/answer/versions/{version_id}')
    def answer_version(study_id: str, version_id: str, request: Request, who: Actor):
        sid, _ = scope(request, who, study_id)
        return result(request, 'StudyAnswerVersionRead3', answers.read(who, sid, valid_id(version_id)))

    return r
