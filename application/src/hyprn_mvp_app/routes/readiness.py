"""The study's execution-readiness read, answered by the ``readiness`` owner."""
from typing import Annotated
from fastapi import APIRouter, Depends, Request
from ..contracts import DomainError
from ..edge import response, valid_id
from ..readiness import execution_readiness

def router(deps):
    store,model=deps.store,deps.model
    Actor=Annotated[str,Depends(deps.actor)]
    r=APIRouter()

    @r.get("/api/1/studies/{study_id}/execution-readiness")
    def readiness(study_id:str,request:Request,who:Actor):
        sid=valid_id(study_id)
        with store.connection() as db:store.authorize(db,who,sid)
        if request.query_params:raise DomainError("invalid_request",400)
        return response(request,execution_readiness(store,model,who,sid))
    return r
