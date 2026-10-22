"""Configurations: preview, commit, list and read. The modified-run seed and the result-source
reads sit between commit and list because that registration order fixes the contract's path
order; they are answered by their own owners (``modified_runs``, ``result_bindings``)."""
from typing import Annotated
from fastapi import APIRouter, Body, Depends, Request
from ..contracts import DomainError, validate
from ..edge import page, response, valid_id

def router(deps):
    store,configs=deps.store,deps.configs
    modified_runs,result_bindings=deps.modified_runs,deps.result_bindings
    Actor=Annotated[str,Depends(deps.actor)]
    r=APIRouter()

    @r.post("/api/1/studies/{study_id}/configurations/preview")
    def preview_configuration(study_id:str,request:Request,who:Actor,body:dict=Body(...)):
        # New configurations are version 6 only: no criteria and no approach binding.
        if body.get("schema_version")!="6":raise DomainError("unsupported_record_version",422)
        validate("ConfigurationRequest6",body)
        with store.connection() as db:store.authorize(db,who,valid_id(study_id))
        return response(request,configs.preview(who,valid_id(study_id),body)[0])
    @r.post("/api/1/studies/{study_id}/configurations",status_code=201)
    def commit_configuration(study_id:str,request:Request,who:Actor,body:dict=Body(...)):
        candidate=body.get("configuration")
        version=candidate.get("schema_version") if isinstance(candidate,dict) else None
        if version!="6":raise DomainError("unsupported_record_version",422)
        validate("ConfigurationCommit6",body)
        if body.get("configuration_id"):valid_id(body["configuration_id"])
        with store.connection() as db:store.authorize(db,who,valid_id(study_id),write=True)
        return response(request,configs.commit(who,valid_id(study_id),body),201)
    @r.get('/api/1/studies/{study_id}/runs/{run_id}/modified-run-seed')
    def modified_run_seed(study_id:str,run_id:str,request:Request,who:Actor):
        if request.query_params:raise DomainError('invalid_request',400)
        result=modified_runs.seed(who,valid_id(study_id),valid_id(run_id))
        validate("ModifiedRunSeedRead8",result,remote=True)
        return response(request,result)
    @r.get('/api/1/studies/{study_id}/result-sources')
    def result_sources(study_id:str,request:Request,who:Actor,limit:str='25',cursor:str|None=None):
        pairs=list(request.query_params.multi_items())
        if (any(key not in {'limit','cursor'} for key,_ in pairs) or len({key for key,_ in pairs})!=len(pairs)
                or limit not in {str(i) for i in range(1,51)}):
            raise DomainError('invalid_request',400)
        return response(request,result_bindings.inventory(who,valid_id(study_id),limit=int(limit),cursor=cursor))
    @r.get("/api/1/studies/{study_id}/configurations")
    def list_configurations(study_id:str,request:Request,who:Actor,cursor:str|None=None,limit:int=100,model_id:str|None=None,model_revision_id:str|None=None):
        items, after = configs.read_page(who,valid_id(study_id),cursor=valid_id(cursor) if cursor else None,limit=limit,
            model_id=valid_id(model_id) if model_id else None,model_revision_id=valid_id(model_revision_id) if model_revision_id else None)
        return response(request,items,next_cursor=after)
    @r.get("/api/1/studies/{study_id}/configuration-summaries")
    def configuration_summaries(study_id:str,request:Request,who:Actor,cursor:str|None=None,limit:int=50,model_id:str|None=None,model_revision_id:str|None=None):
        items, after = configs.read_page(who,valid_id(study_id),cursor=valid_id(cursor) if cursor else None,limit=limit,
            model_id=valid_id(model_id) if model_id else None,model_revision_id=valid_id(model_revision_id) if model_revision_id else None,summary=True)
        return response(request,items,next_cursor=after)
    @r.get("/api/1/studies/{study_id}/configurations/{revision_id}")
    def get_configuration(study_id:str,revision_id:str,request:Request,who:Actor):
        return response(request,configs.read(who,valid_id(study_id),valid_id(revision_id)))
    return r
