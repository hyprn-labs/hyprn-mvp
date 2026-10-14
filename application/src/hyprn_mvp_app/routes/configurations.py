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
        version=body.get("schema_version")
        validate("ConfigurationRequest4" if version=="4" else "ConfigurationRequest3" if version=="3" else "ConfigurationRequest2" if version=="2" else "ConfigurationCandidate1",body)
        if version in ("3","4"):
            with store.connection() as db:store.authorize(db,who,valid_id(study_id))
            if not callable(getattr(configs,"_preview"+version,None)):raise DomainError("unsupported_capability",422)
        return response(request,configs.preview(who,valid_id(study_id),body)[0])
    @r.post("/api/1/studies/{study_id}/configurations",status_code=201)
    def commit_configuration(study_id:str,request:Request,who:Actor,body:dict=Body(...)):
        candidate=body.get("configuration")
        version=candidate.get("schema_version") if isinstance(candidate,dict) else None
        validate("ConfigurationCommit4" if version=="4" else "ConfigurationCommit3" if version=="3" else "ConfigurationCommit2" if version=="2" else "ConfigurationCommit1",body)
        if body.get("configuration_id"):valid_id(body["configuration_id"])
        if version in ("3","4"):
            with store.connection() as db:store.authorize(db,who,valid_id(study_id),write=True)
            if not callable(getattr(configs,"_commit"+version,None)):raise DomainError("unsupported_capability",422)
        return response(request,configs.commit(who,valid_id(study_id),body),201)
    @r.get('/api/1/studies/{study_id}/runs/{run_id}/modified-run-seed')
    def modified_run_seed(study_id:str,run_id:str,request:Request,who:Actor):
        if request.query_params:raise DomainError('invalid_request',400)
        result=modified_runs.seed(who,valid_id(study_id),valid_id(run_id))
        validate("ModifiedRunSeedRead7",result,remote=True)
        return response(request,result)
    @r.get('/api/1/studies/{study_id}/result-sources')
    def result_sources(study_id:str,request:Request,who:Actor,limit:str='25',cursor:str|None=None):
        pairs=list(request.query_params.multi_items())
        if (any(key not in {'limit','cursor'} for key,_ in pairs) or len({key for key,_ in pairs})!=len(pairs)
                or limit not in {str(i) for i in range(1,51)}):
            raise DomainError('invalid_request',400)
        return response(request,result_bindings.inventory(who,valid_id(study_id),limit=int(limit),cursor=cursor))
    @r.get("/api/1/studies/{study_id}/configurations")
    def list_configurations(study_id:str,request:Request,who:Actor,cursor:str|None=None,limit:int=100):
        return page(request,configs.read(who,valid_id(study_id)),lambda x:x["configuration"]["configuration_revision_id"],cursor,limit)
    @r.get("/api/1/studies/{study_id}/configurations/{revision_id}")
    def get_configuration(study_id:str,revision_id:str,request:Request,who:Actor):
        return response(request,configs.read(who,valid_id(study_id),valid_id(revision_id)))
    return r
