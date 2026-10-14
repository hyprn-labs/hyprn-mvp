"""Command receipts: the study-scoped receipt read and the pre-study receipt read.

Every 200 answer carries the owner's ``recovery`` (``store.receipt_recovery``), added after the
owner's own read and validation; a missing receipt in a scope the reader may see is today's 404
with the recovery in its error object, and a reader who may not see the scope gets today's 404
without it."""
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, Request
from ..contracts import DomainError
from ..edge import response, valid_id
from ..store import ReceiptMissing, receipt_recovery

APPROACH_CATEGORIES=frozenset({'approach_draft','approach_version','approach_restore'})
RECORD_CATEGORIES=frozenset({'computational_record_preview','computational_record_create'})

def router(deps):
    store,approaches,coordinator,records=deps.store,deps.approaches,deps.coordinator,deps.records
    Actor=Annotated[str,Depends(deps.actor)]
    r=APIRouter()

    def visible(who,study_id,category,command_id):
        row=store.visible_receipt(who,study_id,category,command_id)
        if row is None:raise ReceiptMissing(category)
        return row

    @r.get("/api/1/studies/{study_id}/commands/{command_id}")
    def receipt(study_id:str,command_id:str,category:str,request:Request,who:Actor):
        valid_id(study_id)
        valid_id(command_id)
        if category in APPROACH_CATEGORIES:
            if list(request.query_params.multi_items())!=[('category',category)]:
                raise DomainError('invalid_request',400)
            visible(who,study_id,category,command_id)
            body=approaches.receipt(who,study_id,category,command_id)
            return response(request,dict(body,**receipt_recovery(category,body)))
        row=visible(who,study_id,category,command_id)
        if category=="model":
            # A recorded rejection is a receipt outcome; current authorization
            # failures must propagate even when their code matches that outcome.
            coordinator.reconcile(who,study_id,command_id,receipt_view=True)
            row=store.receipt(who,study_id,category,command_id)
        result=None if row["state"]=="pending_remote" else row["result"]
        if category=="model" and row["state"]=="committed":result=result["response"]
        if category in RECORD_CATEGORIES and result is not None:
            # Reauthorize the retained closure; keep the original receipt result
            # immutable. Work state is obtained from the separate status route.
            records.status(who,study_id,result['request_id'])
        body=dict(command_id=command_id,state=row["state"],result=result,error=row["error"])
        return response(request,dict(body,**receipt_recovery(category,row)))
    @r.get("/api/1/commands/{command_id}")
    def study_receipt(command_id:str,category:Literal["study_create"],request:Request,who:Actor):
        row=visible(who,None,category,valid_id(command_id))
        body=dict(command_id=command_id,state=row["state"],result=row["result"],error=row["error"])
        return response(request,dict(body,**receipt_recovery(category,row)))
    return r
