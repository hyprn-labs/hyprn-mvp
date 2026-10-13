"""Computational record exports: preview and create requests, their status and the download."""
import hashlib
from typing import Annotated
from fastapi import APIRouter, Body, Depends, Request
from fastapi.responses import Response
from ..contracts import DomainError
from ..edge import response, valid_id

def router(deps):
    records=deps.records
    Actor=Annotated[str,Depends(deps.actor)]
    r=APIRouter()

    @r.post('/api/1/studies/{study_id}/computational-record-previews',status_code=202)
    def preview_record(study_id:str,request:Request,who:Actor,body:dict=Body(...)):
        if request.query_params:raise DomainError('invalid_request',400)
        return response(request,records.enqueue_preview(who,valid_id(study_id),body),202)
    @r.post('/api/1/studies/{study_id}/computational-records',status_code=202)
    def create_record(study_id:str,request:Request,who:Actor,body:dict=Body(...)):
        if request.query_params:raise DomainError('invalid_request',400)
        return response(request,records.enqueue_create(who,valid_id(study_id),body),202)
    @r.get('/api/1/studies/{study_id}/computational-records/{request_id}')
    def record_status(study_id:str,request_id:str,request:Request,who:Actor):
        if request.query_params:raise DomainError('invalid_request',400)
        return response(request,records.status(who,valid_id(study_id),valid_id(request_id)))
    @r.get('/api/1/studies/{study_id}/computational-records/{request_id}/download')
    def record_download(study_id:str,request_id:str,request:Request,who:Actor):
        if request.query_params:raise DomainError('invalid_request',400)
        raw=records.download(who,valid_id(study_id),valid_id(request_id))
        return Response(content=raw,media_type='application/zip',headers={
            'Content-Disposition':'attachment; filename="hyprn-mvp-computational-record.zip"',
            'X-Content-SHA256':hashlib.sha256(raw).hexdigest()})
    return r
