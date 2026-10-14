"""Agent administration routes of the public API, for people only.

Who wrote what (the attribution reads), which agents have access to a study (the access read)
and, for the study Owner, the study's tool tokens and their revocation. Every route refuses an
agent session (403) through its human-only actor dependency, besides the agent route allowlist
that already refuses these routes before routing. No route mints a token: tokens are minted
only by the operator command (``python -m hyprn_mvp_app.agent_runtime``).

The router follows the per-owner router convention: it reads the store, the authentication and
the environment from the composition object and tolerates an absent store (contract export).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import Field

from ..contracts import DomainError
from ..edge import Closed, page, response, valid_id
from . import attribution, control, delegations, tokens

UUID_PATTERN = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
REVOKE_CATEGORY = 'agent_token_revoke'


class AgentTokenRevokeCommand(Closed):
    """Revoke one tool token of the study: the command identity only."""

    command_id: str = Field(pattern=UUID_PATTERN)


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

    @r.get('/api/1/studies/{study_id}/agent/tokens')
    def agent_tokens(
        study_id: str, request: Request, who: Person, cursor: str | None = None, limit: int = 50
    ):
        items = tokens.owner_list(store, who, valid_id(study_id))
        return page(request, items, lambda item: item['token_id'], cursor, limit)

    @r.post('/api/1/studies/{study_id}/agent/tokens/{token_id}/revoke')
    def revoke_agent_token(
        study_id: str, token_id: str, body: AgentTokenRevokeCommand, request: Request, who: Person
    ):
        valid_id(study_id)
        valid_id(token_id)

        def apply(db):
            return tokens.revoke_in(store, db, study_id, token_id)

        payload = dict(operation='revoke_agent_token', token_id=token_id)
        outcome = store.command(
            who, study_id, REVOKE_CATEGORY, body.command_id, payload, apply, owner=True
        )
        return response(request, outcome)

    @r.get('/api/1/agent/attribution/studies')
    def created_studies(request: Request, who: Person, cursor: str | None = None, limit: int = 50):
        return response(request, attribution.created_studies(store, who, cursor, limit))

    return r
