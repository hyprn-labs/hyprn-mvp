"""The Modeling approach: state, preview, draft, restore, saved versions and their usage."""
import json
from typing import Annotated
from fastapi import APIRouter, Body, Depends, Request
from ..contracts import DomainError, validate
from ..edge import response, valid_id

def router(deps):
    store,approaches=deps.store,deps.approaches
    Actor=Annotated[str,Depends(deps.actor)]
    r=APIRouter()

    def approach_query(request, who, sid, *, usage=False, paginated=False):
        # Authorization precedes detailed cursor diagnostics; cursors are typed
        # JSON query values, not resource authority or a second mutable state.
        with store.connection() as db:store.authorize(db,who,sid)
        pairs=list(request.query_params.multi_items())
        allowed={'limit','cursor'} | ({'case_id'} if usage else set()) if paginated else set()
        if any(k not in allowed for k,_ in pairs) or len({k for k,_ in pairs})!=len(pairs):
            raise DomainError('invalid_request',400)
        result={}
        for key,value in pairs:
            if key=='limit':
                if not value.isascii() or not value.isdecimal() or len(value)>3:raise DomainError('invalid_request',400)
                result[key]=int(value)
            elif key=='case_id':result[key]=valid_id(value)
            else:
                if len(value)>256:raise DomainError('invalid_request',400)
                def unique(items):
                    decoded={}
                    for k,v in items:
                        if k in decoded:raise ValueError('Duplicate cursor field')
                        decoded[k]=v
                    return decoded
                try:result[key]=json.loads(value,object_pairs_hook=unique)
                except (ValueError,TypeError,RecursionError):raise DomainError('invalid_request',400) from None
                validate('ApproachUsageCursor1' if usage else 'ApproachCursor1',result[key])
        return result

    def approach_result(request,name,value,status=200):
        validate(name,value,remote=True)
        return response(request,value,status)

    @r.get('/api/1/studies/{study_id}/approach')
    def approach_state(study_id:str,request:Request,who:Actor):
        sid=valid_id(study_id);approach_query(request,who,sid)
        return approach_result(request,'ApproachState2',approaches.state(who,sid))

    @r.post('/api/1/studies/{study_id}/approach/preview')
    def approach_preview(study_id:str,request:Request,who:Actor,body:dict=Body(...)):
        sid=valid_id(study_id);approach_query(request,who,sid)
        return approach_result(request,'ApproachPreviewRead3',approaches.preview(who,sid,body))

    @r.post('/api/1/studies/{study_id}/approach/draft')
    def approach_draft(study_id:str,request:Request,who:Actor,body:dict=Body(...)):
        sid=valid_id(study_id);approach_query(request,who,sid)
        return approach_result(request,'ApproachDraftRead2',approaches.save_draft(who,sid,body))

    @r.post('/api/1/studies/{study_id}/approach/draft/restore')
    def approach_restore(study_id:str,request:Request,who:Actor,body:dict=Body(...)):
        sid=valid_id(study_id);approach_query(request,who,sid)
        return approach_result(request,'ApproachDraftRead2',approaches.restore(who,sid,body))

    @r.get('/api/1/studies/{study_id}/approach/versions')
    def approach_versions(study_id:str,request:Request,who:Actor):
        sid=valid_id(study_id);query=approach_query(request,who,sid,paginated=True)
        return approach_result(request,'ApproachVersionPage2',approaches.versions(who,sid,query))

    @r.post('/api/1/studies/{study_id}/approach/versions',status_code=201)
    def approach_save_version(study_id:str,request:Request,who:Actor,body:dict=Body(...)):
        sid=valid_id(study_id);approach_query(request,who,sid)
        return approach_result(request,'ApproachVersionSavedRead3',approaches.save_version(who,sid,body),201)

    @r.get('/api/1/studies/{study_id}/approach/versions/{version_id}')
    def approach_version(study_id:str,version_id:str,request:Request,who:Actor):
        sid=valid_id(study_id);approach_query(request,who,sid)
        return approach_result(request,'ApproachSavedRead3',approaches.read(who,sid,valid_id(version_id)))

    @r.get('/api/1/studies/{study_id}/approach/versions/{version_id}/usage')
    def approach_usage(study_id:str,version_id:str,request:Request,who:Actor):
        sid=valid_id(study_id);query=approach_query(request,who,sid,usage=True,paginated=True)
        return approach_result(request,'ApproachUsagePage1',approaches.usage(who,sid,valid_id(version_id),query))
    return r
