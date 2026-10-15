"""Exact answer-bound exploration reads through ordinary study authorization."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from ..contracts import DomainError
from ..edge import response, valid_id
from ..exploration import Explorations


def router(deps):
    explorations = Explorations(deps.store, deps.configs)
    Actor = Annotated[str, Depends(deps.actor)]
    r = APIRouter()

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

    return r
