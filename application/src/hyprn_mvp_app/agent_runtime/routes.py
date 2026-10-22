"""Human-only agent attribution and delegated-access reads of the public API.

The embedded Assistant never administers agents or reads attribution. No external
agent token or transport routes are exposed.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from ..contracts import DomainError
from ..edge import response, valid_id
from . import attribution, control, delegations

def router(deps):
    store = deps.store

    def person_actor(request: Request):
        # A delegated agent session never administers agents or reads attribution.
        session = deps.current_session(request)
        if session['kind'] != 'user':
            raise DomainError('forbidden', 403)
        return session['actor_id']

    Person = Annotated[str, Depends(person_actor)]
    r = APIRouter()

    @r.get('/api/1/studies/{study_id}/agent/attribution')
    def study_attribution(
        study_id: str, request: Request, who: Person, cursor: str | None = None, limit: int = 50
    ):
        return response(request, attribution.page(store, who, valid_id(study_id), cursor, limit))

    @r.get('/api/1/studies/{study_id}/agent/access')
    def agent_access(study_id: str, request: Request, who: Person):
        enabled = control.agent_enabled(deps.environ or {})
        return response(
            request, delegations.access(store, who, valid_id(study_id), enabled=enabled)
        )

    @r.get('/api/1/agent/attribution/studies')
    def created_studies(request: Request, who: Person, cursor: str | None = None, limit: int = 50):
        return response(request, attribution.created_studies(store, who, cursor, limit))

    return r
