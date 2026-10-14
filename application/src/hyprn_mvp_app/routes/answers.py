"""Saved scientific answers through ordinary study authorization."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Request

from ..answers import Answers, validate_answer
from ..contracts import DomainError
from ..edge import response, valid_id


def router(deps):
    answers = Answers(deps.store)
    Actor = Annotated[str, Depends(deps.actor)]
    r = APIRouter()

    def result(request, name, value, status=200):
        validate_answer(name, value, retained=True)
        return response(request, value, status)

    def scope(request, who, study_id):
        sid = valid_id(study_id)
        with deps.store.connection() as db:
            deps.store.authorize(db, who, sid)
        if request.query_params:
            raise DomainError('invalid_request', 400)
        return sid

    @r.get('/api/1/studies/{study_id}/approach/versions/{version_id}/answers')
    def answer_heads(study_id: str, version_id: str, request: Request, who: Actor):
        sid = scope(request, who, study_id)
        return result(
            request, 'ScientificAnswerHeads1', answers.heads(who, sid, valid_id(version_id))
        )

    @r.get('/api/1/studies/{study_id}/answers/{answer_version_id}')
    def answer_version(study_id: str, answer_version_id: str, request: Request, who: Actor):
        sid = scope(request, who, study_id)
        return result(
            request, 'ScientificAnswer1', answers.read(who, sid, valid_id(answer_version_id))
        )

    @r.post('/api/1/studies/{study_id}/answers', status_code=201)
    def answer_save(study_id: str, request: Request, who: Actor, body: dict = Body(...)):
        sid = scope(request, who, study_id)
        return result(request, 'ScientificAnswer1', answers.save(who, sid, body), 201)

    return r
