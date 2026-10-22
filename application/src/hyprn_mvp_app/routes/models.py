"""Models through the modeling coordinator: unit catalog, models, imports, drafts, versions,
export, assumption evidence and the four draft actions (preview, edits, commits, validate)."""
from typing import Annotated
from fastapi import APIRouter, Body, Depends, Request
from ..contracts import DomainError, validate
from ..edge import ImportModel, NewModel, NewModel3, page, remote_response, response, valid_id

def router(deps):
    store,coordinator=deps.store,deps.coordinator
    Actor=Annotated[str,Depends(deps.actor)]
    r=APIRouter()

    @r.get("/api/1/studies/{study_id}/unit-catalog")
    def unit_catalog(study_id:str,request:Request,who:Actor):
        sid=valid_id(study_id)
        with store.connection() as db:store.authorize(db,who,sid)
        if request.query_params:raise DomainError("invalid_request",400)
        return response(request,coordinator.unit_catalog(who,sid))

    @r.get("/api/1/studies/{study_id}/models")
    def models(study_id:str,request:Request,who:Actor,cursor:str|None=None,limit:int=100):
        records, next_cursor = coordinator.models(who,valid_id(study_id),cursor=valid_id(cursor) if cursor else None,limit=limit)
        return response(request, records, next_cursor=next_cursor)
    @r.post("/api/1/studies/{study_id}/models",status_code=201)
    def new_model(study_id:str,body:NewModel|NewModel3,request:Request,who:Actor):
        valid_id(study_id);data=body.model_dump()
        private=dict(data,expected_revision=None,study_id=study_id)
        return remote_response(request,coordinator.execute(who,study_id,"create",None,data,private,"/models","CreateRequest","ModelDraftResponse4",association=True))
    @r.post("/api/1/studies/{study_id}/model-imports",status_code=201)
    def import_model(study_id:str,body:ImportModel,request:Request,who:Actor):
        valid_id(study_id);data=body.model_dump()
        private=dict(command_id=body.command_id,expected_revision=None,study_id=study_id,package=body.package,preserve_public_ids=True)
        return remote_response(request,coordinator.execute(who,study_id,"import",None,data,private,"/imports","Import","ModelDraftResponse4",association=True))
    @r.get("/api/1/studies/{study_id}/models/{model_id}")
    def model_draft(study_id:str,model_id:str,request:Request,who:Actor):
        result=coordinator.read(who,valid_id(study_id),valid_id(model_id))
        return response(request,**result)
    @r.get("/api/1/studies/{study_id}/models/{model_id}/revisions")
    def revisions(study_id:str,model_id:str,request:Request,who:Actor,cursor:str|None=None,limit:str="50"):
        return response(request,**coordinator.revisions(who,valid_id(study_id),valid_id(model_id),request.query_params.multi_items()))
    @r.get("/api/1/studies/{study_id}/models/{model_id}/revisions/{revision_id}")
    def revision(study_id:str,model_id:str,revision_id:str,request:Request,who:Actor):
        result=coordinator.read(who,valid_id(study_id),valid_id(model_id),"/revisions/"+valid_id(revision_id),response_schema="ModelRevisionResponse4")
        return response(request,**result)
    @r.get("/api/1/studies/{study_id}/models/{model_id}/export")
    def export(study_id:str,model_id:str,model_revision_id:str,request:Request,who:Actor):
        result=coordinator.read(who,valid_id(study_id),valid_id(model_id),"/export?revision="+valid_id(model_revision_id),response_schema="ModelPackageResponse")
        return response(request,**result)

    @r.get("/api/1/studies/{study_id}/models/{model_id}/assumption-evidence")
    def assumption_evidence(study_id:str,model_id:str,request:Request,who:Actor,
                           model_revision_id:str|None=None,draft_revision:str|None=None):
        sid,mid=valid_id(study_id),valid_id(model_id)
        coordinator.authorize_model(who,sid,mid)
        pairs=list(request.query_params.multi_items())
        if len(pairs)!=1 or pairs[0][0] not in {"model_revision_id","draft_revision"}:
            raise DomainError("invalid_request",400)
        if model_revision_id is not None:valid_id(model_revision_id)
        if draft_revision is not None and (not draft_revision.strip() or len(draft_revision)>4096):
            raise DomainError("invalid_request",400)
        resolver=getattr(coordinator,"assumption_evidence",None)
        if not callable(resolver):raise DomainError("unsupported_capability",422)
        result=resolver(who,sid,mid,model_revision_id=model_revision_id,draft_revision=draft_revision)
        validate("AssumptionEvidenceResolution1",result,remote=True)
        return response(request,result)

    def modeling_route(action,request_schema,response_schema,mutation):
        def route(study_id:str,model_id:str,request:Request,who:Actor,body:dict=Body(...)):
            sid,mid=valid_id(study_id),valid_id(model_id)
            validate(request_schema,body);coordinator.authorize_model(who,sid,mid,write=mutation)
            if mutation:
                return remote_response(request,coordinator.execute(who,sid,action,mid,body,body,
                    "/models/"+mid+"/"+action,request_schema,response_schema))
            return response(request,**coordinator.read(who,sid,mid,"/"+action,method="POST",body=body,
                request_schema=request_schema,response_schema=response_schema))
        # The endpoint name fixes the operation id of each draft action.
        route.__name__="model_"+action
        r.post("/api/1/studies/{study_id}/models/{model_id}/"+action)(route)
    for args in [("preview","PreviewRead4","ModelDraftEditResponse4",False),("edits","ApplyRead4","ModelDraftEditResponse4",True),
                 ("commits","Commit","ModelRevisionResponse4",True),("validate","Validate","ValidationResultResponse",False)]:
        modeling_route(*args)
    return r
