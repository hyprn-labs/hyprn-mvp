"""Runs: submission (``execution``), the run read, the run list and retained artifacts (``history``)."""
from typing import Annotated
from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from ..edge import SubmitRun, page, response, valid_id
from ..history import retained_read_integrity

def router(deps):
    submissions,history=deps.submissions,deps.history
    Actor=Annotated[str,Depends(deps.actor)]
    r=APIRouter()

    @r.post("/api/1/studies/{study_id}/runs",status_code=202)
    def submit(study_id:str,body:SubmitRun,request:Request,who:Actor):
        valid_id(body.configuration_revision_id)
        return response(request,submissions.submit(who,valid_id(study_id),body.model_dump()),202)
    @r.get("/api/1/studies/{study_id}/runs/{run_id}")
    def run_status(study_id:str,run_id:str,request:Request,who:Actor):
        result=submissions.read(who,valid_id(study_id),valid_id(run_id))
        if result['state']=='recorded':
            result['history']=history.read(who,study_id,run_id)
            result['retained_integrity']=retained_read_integrity(run_id,result['history'])
        return response(request,result)
    @r.get("/api/1/studies/{study_id}/runs")
    def run_history(study_id:str,request:Request,who:Actor,cursor:str|None=None,limit:int=100):
        return page(request,history.list(who,valid_id(study_id)),lambda x:x['run_id'],cursor,limit)
    @r.get("/api/1/studies/{study_id}/runs/{run_id}/artifacts/{artifact_id}")
    def run_artifact(study_id:str,run_id:str,artifact_id:str,request:Request,who:Actor):
        raw,descriptor=history.read(who,valid_id(study_id),valid_id(run_id),valid_id(artifact_id))
        return Response(content=raw,media_type=descriptor['media_type'],headers={
            'Content-Disposition':'attachment; filename="'+artifact_id+'"','X-Content-SHA256':descriptor['sha256']})
    return r
