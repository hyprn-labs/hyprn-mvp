"""The study brief through ordinary study authorization: state, draft, saved versions."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Request

from ..brief import Briefs, validate_brief
from ..contracts import DomainError
from ..edge import response, valid_id


def router(deps):
    briefs = Briefs(deps.store)
    Actor = Annotated[str, Depends(deps.actor)]
    r = APIRouter()

    def result(request, name, value, status=200):
        validate_brief(name, value, retained=True)
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

    @r.get('/api/1/studies/{study_id}/brief')
    def brief_state(study_id: str, request: Request, who: Actor):
        sid, _ = scope(request, who, study_id)
        return result(request, 'StudyBriefState1', briefs.state(who, sid))

    @r.post('/api/1/studies/{study_id}/brief/draft')
    def brief_draft(study_id: str, request: Request, who: Actor, body: dict = Body(...)):
        sid, _ = scope(request, who, study_id)
        return result(request, 'StudyBriefDraft1', briefs.save_draft(who, sid, body))

    @r.get('/api/1/studies/{study_id}/brief/versions')
    def brief_versions(study_id: str, request: Request, who: Actor):
        sid, query = scope(request, who, study_id, ('limit', 'before'))
        page = briefs.versions(
            who,
            sid,
            limit=positive(query['limit'], 100) if 'limit' in query else 20,
            before=positive(query['before'], 9007199254740991) if 'before' in query else None,
        )
        return result(request, 'StudyBriefVersionPage1', page)

    @r.post('/api/1/studies/{study_id}/brief/versions', status_code=201)
    def brief_save_version(study_id: str, request: Request, who: Actor, body: dict = Body(...)):
        sid, _ = scope(request, who, study_id)
        return result(request, 'StudyBriefVersionSaved1', briefs.save_version(who, sid, body), 201)

    @r.get('/api/1/studies/{study_id}/brief/versions/{version_id}')
    def brief_version(study_id: str, version_id: str, request: Request, who: Actor):
        sid, _ = scope(request, who, study_id)
        return result(request, 'StudyBriefVersion1', briefs.read(who, sid, valid_id(version_id)))

    return r
