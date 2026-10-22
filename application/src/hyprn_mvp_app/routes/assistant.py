"""Human-only conversation transport. Scientific effects use the existing delegated tools."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Request

from ..assistant.schema import validate
from ..contracts import DomainError
from ..edge import response, valid_id

BASE = '/api/1/studies/{study_id}/assistant'


def router(deps):
    Actor = Annotated[str, Depends(deps.actor)]
    r = APIRouter()

    def scope(request, who, study_id):
        sid = valid_id(study_id)
        if request.query_params or deps.current_session(request)['kind'] != 'user':
            raise DomainError('forbidden', 403)
        with deps.store.connection() as db:
            deps.store.authorize(db, who, sid)
        return sid, request.app.state.assistant

    def result(request, value, status=200):
        validate('AssistantConversationRead3', value)
        return response(request, value, status)

    @r.get('/api/1/assistant/budget')
    async def assistant_budget(request: Request, who: Actor):
        if request.query_params or deps.current_session(request)['kind'] != 'user':
            raise DomainError('forbidden', 403)
        owner = request.app.state.assistant
        value = await owner.budget.read(owner.provider, owner.settings, who)
        validate('AssistantBudgetRead2', value)
        return response(request, value)

    @r.get(BASE + '/budget')
    async def study_assistant_budget(study_id: str, request: Request, who: Actor):
        sid, owner = scope(request, who, study_id)
        value = await owner.budget.read(owner.provider, owner.settings, who)
        # Recheck access after the provider read, just as for other awaited protected reads.
        scope(request, who, study_id)
        validate('AssistantBudgetRead2', value)
        return response(request, value)

    @r.get(BASE)
    async def assistant_conversation(study_id: str, request: Request, who: Actor):
        sid, owner = scope(request, who, study_id)
        return result(request, owner.read(who, sid))

    @r.post(BASE + '/messages', status_code=202)
    async def assistant_send(study_id: str, request: Request, who: Actor, body: dict = Body(...)):
        sid, owner = scope(request, who, study_id)
        validate('AssistantMessageRequest1', body)
        command = valid_id(body['command_id'])
        if not body['text'].strip():
            raise DomainError('invalid_request', 400)
        return result(request, owner.send(who, sid, command, body['text']), 202)

    @r.post(BASE + '/resume', status_code=202)
    async def assistant_resume(study_id: str, request: Request, who: Actor, body: dict = Body(...)):
        sid, owner = scope(request, who, study_id)
        validate('AssistantResumeRequest1', body)
        return result(request, owner.resume(who, sid), 202)

    @r.post(BASE + '/stop', status_code=202)
    async def assistant_stop(study_id: str, request: Request, who: Actor, body: dict = Body(...)):
        sid, owner = scope(request, who, study_id)
        validate('AssistantStopRequest1', body)
        return result(request, owner.stop(who, sid), 202)

    return r
