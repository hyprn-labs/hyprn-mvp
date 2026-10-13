"""Studies: list, create, read, archive, restore and update, all owned by ``store``."""
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, Request
from ..contracts import DomainError
from ..edge import NewStudy, StudyArchiveCommand, StudyPatch, delegated_scope, page, response, valid_id

def router(deps):
    store=deps.store
    CurrentSession=Annotated[dict,Depends(deps.current_session)]
    Actor=Annotated[str,Depends(deps.actor)]
    r=APIRouter()

    @r.get("/api/1/studies")
    def studies(request:Request,current:CurrentSession,cursor:str|None=None,limit:int=100,archived:Literal["true","false"]="false"):
        # Archived studies are listed only on request (?archived=true), never mixed with others.
        if [k for k,_ in request.query_params.multi_items()].count("archived")>1:raise DomainError("invalid_request",400)
        listing=delegated_scope(current,store.study_listing(current["actor_id"],archived=="true"))
        return page(request,listing,lambda x:x["study_id"],cursor,limit)
    @r.post("/api/1/studies",status_code=201)
    def create_study(body:NewStudy,request:Request,current:CurrentSession):
        # An agent session's study creation names its delegation; the store admits it only
        # under a live writer delegation and makes the delegating user the Owner.
        return response(request,store.create_study(current["actor_id"],body.command_id,body.name,
                                                   delegation_id=current["delegation_id"]),201)
    @r.get("/api/1/studies/{study_id}")
    def read_study(study_id:str,request:Request,who:Actor):return response(request,store.study_read(who,valid_id(study_id)))
    @r.post("/api/1/studies/{study_id}/archive")
    def archive_study(study_id:str,body:StudyArchiveCommand,request:Request,who:Actor):
        return response(request,store.set_study_archived(who,valid_id(study_id),body.command_id,True))
    @r.post("/api/1/studies/{study_id}/restore")
    def restore_study(study_id:str,body:StudyArchiveCommand,request:Request,who:Actor):
        return response(request,store.set_study_archived(who,valid_id(study_id),body.command_id,False))
    @r.patch("/api/1/studies/{study_id}")
    def patch_study(study_id:str,body:StudyPatch,request:Request,who:Actor):
        changes=body.model_dump(exclude={"command_id","expected_revision"},exclude_unset=True)
        if any(v is None for v in changes.values()):raise DomainError("invalid_request",400)
        return response(request,store.update_study(who,valid_id(study_id),body.command_id,body.expected_revision,changes))
    return r
