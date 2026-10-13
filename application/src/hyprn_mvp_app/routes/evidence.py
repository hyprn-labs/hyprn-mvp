"""Evidence: create, list, read one version, read a family, list and add family versions."""
from typing import Annotated
from fastapi import APIRouter, Body, Depends, Request
from ..contracts import DomainError, validate
from ..edge import response, valid_id

def router(deps):
    store,coordinator=deps.store,deps.coordinator
    Actor=Annotated[str,Depends(deps.actor)]
    r=APIRouter()

    @r.post("/api/1/studies/{study_id}/evidence",status_code=201)
    def evidence(study_id:str,request:Request,who:Actor,body:dict=Body(...)):
        validate("EvidenceCreate",body)
        return response(request,store.add_evidence(who,valid_id(study_id),body["command_id"],
            {k:v for k,v in body.items() if k!="command_id"},coordinator=coordinator),201)
    @r.get("/api/1/studies/{study_id}/evidence")
    def list_evidence(study_id:str,request:Request,who:Actor,cursor:str|None=None,limit:str="50",
        scope_kind:str|None=None,model_id:str|None=None,model_revision_id:str|None=None,instance_id:str|None=None,
        port_id:str|None=None,configuration_revision_id:str|None=None,run_id:str|None=None,legacy_scope:str|None=None,view:str="heads"):
        return response(request,**store.list_evidence(who,valid_id(study_id),request.query_params.multi_items()))
    @r.get("/api/1/studies/{study_id}/evidence/{evidence_version_id}")
    def get_evidence(study_id:str,evidence_version_id:str,request:Request,who:Actor):
        return response(request,store.evidence_version(who,valid_id(study_id),valid_id(evidence_version_id)))
    @r.get("/api/1/studies/{study_id}/evidence-families/{evidence_id}")
    def evidence_family(study_id:str,evidence_id:str,request:Request,who:Actor):
        if request.query_params:raise DomainError("invalid_request",400)
        return response(request,store.evidence_family(who,valid_id(study_id),valid_id(evidence_id)))
    @r.get("/api/1/studies/{study_id}/evidence-families/{evidence_id}/versions")
    def evidence_versions(study_id:str,evidence_id:str,request:Request,who:Actor,cursor:str|None=None,limit:str="50"):
        return response(request,**store.evidence_versions(who,valid_id(study_id),valid_id(evidence_id),request.query_params.multi_items()))
    @r.post("/api/1/studies/{study_id}/evidence-families/{evidence_id}/versions",status_code=201)
    def revise_evidence(study_id:str,evidence_id:str,request:Request,who:Actor,body:dict=Body(...)):
        validate("EvidenceRevise3",body)
        return response(request,store.revise_evidence(who,valid_id(study_id),valid_id(evidence_id),
            body["command_id"],body["expected_revision"],
            {k:v for k,v in body.items() if k not in {"command_id","expected_revision"}},coordinator=coordinator),201)
    return r
