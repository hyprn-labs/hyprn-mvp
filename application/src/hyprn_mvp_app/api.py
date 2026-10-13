"""Version 1 public API; all model work crosses the typed private contract."""
import json
import hashlib
import os
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID
from fastapi import FastAPI, Body, Depends, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from .auth import Auth
from .agent_policy import route_allowed
from .contracts import MAX_DIAGNOSTICS, DomainError, canonical, issue, uid, validate
from .store import Store
from .readiness import execution_readiness
from .modeling import Coordinator, ModelingClient
from .configuration import Configurations
from .approach import Approaches
from .execution import Submissions
from .history import History, retained_read_integrity
from .result_bindings import ResultBindings
from .modified_runs import ModifiedRuns
from .computational_export import records_for_store, LIMITS as RECORD_LIMITS

class Closed(BaseModel):
    model_config=ConfigDict(extra="forbid",strict=True)
class Login(Closed):
    username:str=Field(min_length=1,max_length=128)
    password:str=Field(min_length=1,max_length=1024)
class NewStudy(Closed):
    command_id:str=Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
    name:str=Field(min_length=1,max_length=4096)
class StudyArchiveCommand(Closed):
    # Archive/restore body: the command identity only (no CAS; the study is unchanged).
    command_id:str=Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
class StudyPatch(Closed):
    command_id:str
    expected_revision:str
    name:str|None=Field(default=None,min_length=1,max_length=4096)
    description:str|None=Field(default=None,max_length=4096)
    boundary:str|None=Field(default=None,max_length=4096)
class NewModel(NewStudy):
    expected_revision:str
    template:Literal["empty","two_component_example"]
class NewModel3(NewModel):
    schema_version:Literal["3"]
class ImportModel(Closed):
    command_id:str
    expected_revision:str
    package:dict
class Evidence(Closed):
    command_id:str
    scope:str|None
    kind:Literal["note"]
    content:str=Field(max_length=4096)
    source_refs:list[str]=Field(max_length=1000)
class EvidenceV2(Closed):
    evidence_schema_version:Literal['2']
    command_id:str
    resource_scope:dict
    kind:Literal['note']
    content:str=Field(max_length=4096)
    source_refs:list[str]=Field(max_length=1000)
class ConfigurationCommit(Closed):
    command_id:str
    expected_revision:str|None
    configuration_id:str|None=None
    configuration:dict
class ConfigurationCommitV2(ConfigurationCommit):
    configuration_id:str|None
    expected_preview_digest:str=Field(pattern=r'^[0-9a-f]{64}$')
class SubmitRun(Closed):
    command_id:str
    configuration_revision_id:str

def valid_id(value):
    try:
        if str(UUID(value))!=value:raise ValueError()
    except (ValueError,TypeError,AttributeError):raise DomainError("invalid_request",400)
    return value

MALFORMED_BODY=("Request body must be one strict JSON value: no duplicate keys, non-finite or out-of-range "
    "numbers or invalid text, and at most 32 levels of nesting.")
REQUEST_MESSAGES={"missing":"Required field is missing.","extra_forbidden":"Field is not allowed here."}

def request_diagnostics(error):
    """Field-level detail for request-shape failures; submitted input is never echoed."""
    fields=[]
    for item in error.errors()[:MAX_DIAGNOSTICS]:
        loc=list(item.get("loc",()))
        parts=loc[1:] if loc[:1]==["body"] else loc
        message=REQUEST_MESSAGES.get(item.get("type")) or str(item.get("msg") or "Invalid value").rstrip(".")+"."
        fields.append(issue(parts,message))
    return fields

MUTATIONS=frozenset({"POST","PATCH","DELETE","PUT"})

def agent_boundary(method,path,session):
    """Refuse, before routing, what a delegated agent API session may never do: the session
    routes, any mutation from a read-only session, any route the agent allowlist refuses
    (403), and any study other than its delegation's study (the same undisclosed 404)."""
    if path=="/api/1/session":raise DomainError("forbidden",403)
    if session["read_only"] and method in MUTATIONS:raise DomainError("forbidden",403)
    if not route_allowed(method,path,session["effects"]):raise DomainError("forbidden",403)
    parts=path.split("/")
    if len(parts)>4 and parts[1:4]==["api","1","studies"] and parts[4]!=session["study_id"]:
        raise DomainError("resource_not_found",404)

def delegated_scope(session,studies):
    """An agent session sees only its delegation's study; a human session sees its list."""
    if session["kind"]!="agent":return studies
    return [s for s in studies if s["study_id"]==session["study_id"]]

def error_response(request,error):
    return JSONResponse(status_code=error.status,content={"error":dict(code=error.code,message=error.code.replace("_"," "),
        request_id=getattr(request.state,"request_id",uid()),command_id=getattr(request.state,"command_id",None),
        resource_id=None,current_revision=error.current_revision,fields=error.fields,outcome=error.outcome)})

def create_app(store,auth,model):
    app=FastAPI(title="HYPRN MVP API",version="1.0.0",docs_url=None,redoc_url=None,openapi_url=None)
    app.state.store=store;app.state.auth=auth;app.state.model=model
    coordinator=Coordinator(store,model);configs=Configurations(store,coordinator)
    approaches=Approaches(store,coordinator)
    submissions=Submissions(store,None,None)
    history=History(store)
    result_bindings=ResultBindings(store)
    modified_runs=ModifiedRuns(store)
    records=records_for_store(store) if store is not None else None

    @app.middleware("http")
    async def boundaries(request,call_next):
        request.state.request_id=uid()
        try:
            path=request.scope["path"]
            api_path=path=="/api/1" or path.startswith("/api/1/")
            # A tool token (or any other bearer credential) is never valid on the API.
            if api_path and "authorization" in request.headers:raise DomainError("unauthenticated",401)
            if request.url.netloc!=auth.origin.split("://",1)[-1]:raise DomainError("forbidden",403)
            session=None
            if request.method in MUTATIONS:
                auth.authorize_origin(request.headers.get("origin"))
                if request.url.path!="/api/1/session" or request.method!="POST":
                    session=auth.authorize_mutation(request.cookies.get("hyprn_mvp_session"),request.headers.get("origin"),request.headers.get("x-csrf-token"))
            if api_path and session is None and request.cookies.get("hyprn_mvp_session"):
                try:session=auth.authenticate(request.cookies.get("hyprn_mvp_session"))
                except DomainError:session=None  # the route's actor dependency answers 401
            if session is not None and session["kind"]=="agent":
                agent_boundary(request.method,path,session)
            raw=bytearray()
            async for part in request.stream():
                raw.extend(part)
                if len(raw)>2*1024*1024:raise DomainError("limit_exceeded",413)
            if raw:
                if request.headers.get("content-type","").split(";")[0]!="application/json":
                    raise DomainError("invalid_request",400,fields=[issue((),"Content-Type must be application/json.")])
                def pairs(items):
                    result={}
                    for key,value in items:
                        if key in result:raise ValueError("Duplicate key")
                        result[key]=value
                    return result
                def bound(v,depth=0):
                    if depth>32:raise ValueError("Depth")
                    if isinstance(v,dict):
                        for x in v.values():bound(x,depth+1)
                    if isinstance(v,list):
                        for x in v:bound(x,depth+1)
                try:
                    value=json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(ValueError()))
                    bound(value);canonical(value)
                except (ValueError,UnicodeError,RecursionError):
                    raise DomainError("invalid_request",400,fields=[issue((),MALFORMED_BODY)]) from None
                if isinstance(value,dict) and "command_id" in value:
                    valid_id(value["command_id"]);request.state.command_id=value["command_id"]
                request._body=bytes(raw)
            response=await call_next(request)
        except DomainError as exc:response=error_response(request,exc)
        except (ValueError,UnicodeError,RecursionError):response=error_response(request,DomainError("invalid_request",400))
        response.headers.update({"Cache-Control":"no-store","X-Content-Type-Options":"nosniff","Referrer-Policy":"no-referrer"})
        return response

    @app.exception_handler(DomainError)
    async def domain_error(request,error):return error_response(request,error)
    @app.exception_handler(RequestValidationError)
    async def validation_error(request,error):return error_response(request,DomainError("invalid_request",400,fields=request_diagnostics(error)))
    @app.exception_handler(HTTPException)
    async def http_error(request,error):return error_response(request,DomainError("resource_not_found",error.status_code))
    @app.exception_handler(Exception)
    async def unexpected_error(request,error):return error_response(request,DomainError("internal_error",500,outcome="unknown"))

    def current_session(request:Request):
        return auth.authenticate(request.cookies.get("hyprn_mvp_session"))
    CurrentSession=Annotated[dict,Depends(current_session)]
    def actor(request:Request):
        # The agent actor for a delegated agent session, so receipts carry the agent.
        return auth.authenticate(request.cookies.get("hyprn_mvp_session"))["actor_id"]
    Actor=Annotated[str,Depends(actor)]
    def response(request,data,status=200,**extra):
        return JSONResponse(status_code=status,content=dict(schema_version="1",request_id=request.state.request_id,data=data,**extra))
    def page(request,items,key,cursor,limit):
        if not 1<=limit<=100:raise DomainError("invalid_request",400)
        if cursor:
            valid_id(cursor)
            position=next((i for i,x in enumerate(items) if key(x)==cursor),None)
            if position is None:raise DomainError("resource_not_found",404)
            items=items[position+1:]
        selected=items[:limit]
        return response(request,selected,next_cursor=key(selected[-1]) if len(items)>limit else None)
    def remote_response(request,result):
        status,body=result
        return response(request,status=status,**body)

    @app.post("/api/1/session")
    def login(body:Login,request:Request):
        session=auth.login(body.username,body.password)
        result=response(request,{k:v for k,v in session.items() if k!="token"})
        result.set_cookie("hyprn_mvp_session",session["token"],httponly=True,samesite="strict",
                          secure=auth.origin.startswith("https://"),path="/api/1",max_age=8*60*60)
        return result
    @app.delete("/api/1/session")
    def logout(request:Request,who:Actor):
        auth.logout(request.cookies.get("hyprn_mvp_session"))
        result=response(request,{"ended":True});result.delete_cookie("hyprn_mvp_session",path="/api/1")
        return result
    @app.get("/api/1/capabilities")
    def capabilities(request:Request,current:CurrentSession):
        # The global route has no study selector. Probe through an authorized study;
        # every concrete operation negotiates again with its own current scope.
        who=current["actor_id"]
        studies=delegated_scope(current,store.list_studies(who))
        caps=configs.native_capabilities(who,studies[0]["study_id"]) if studies else None
        assumptions=bool(caps and '1.2' in caps['contract_versions'] and '2' in caps['schema_versions'] and
            any(c['id']=='model_assumptions' and c['version']=='1' and c['supported'] for c in caps['capabilities']))
        configuration3=configs.supports3(caps)
        units=coordinator.supports_units(caps)
        quantities=coordinator.supports_quantities(caps)
        return response(request,dict(contract_versions=["1","1.1","prepared_artifact/2","execution_bundle/2","execution_bundle/3","configuration/2","hyprn_mvp.openmdao.program/1","computational_record/1"]+(['configuration/3','execution_bundle/4'] if configuration3 else [])+(["model/3"] if units else [])+(["model/4"] if quantities else []),engineering=["flat_explicit_scalar","result_linked_inputs/1","evidence_revisions/1","study_archive/1"]+(['configuration_assumptions/1'] if configuration3 else []),modeling=["model_revision_listing","model_rename"]+(["model_assumptions/1"] if assumptions else [])+(["unit_declarations/1"] if units else [])+(["quantity_definitions/1"] if quantities else []),
            execution="durable_scalar_submission",unavailable=([] if quantities else ["quantity_definitions/1"])+([] if units else ["unit_declarations/1"])+([] if assumptions else ["model_assumptions/1"])+([] if configuration3 else ["configuration_assumptions/1"])+["documents","membership_management","nested_composition","selective_rebind","coupled","optimization","uncertainty","cancellation","assistance"],
            limits=dict(request_bytes=2*1024*1024,source_bytes=256*1024,edits=256,elements=1000,depth=32,result_source_outputs=50,result_source_runs=100,result_source_bindings=1000,result_source_dependencies=64,computational_record=RECORD_LIMITS)))
    @app.get("/api/1/studies")
    def studies(request:Request,current:CurrentSession,cursor:str|None=None,limit:int=100,archived:Literal["true","false"]="false"):
        # Archived studies are listed only on request (?archived=true), never mixed with others.
        if [k for k,_ in request.query_params.multi_items()].count("archived")>1:raise DomainError("invalid_request",400)
        listing=delegated_scope(current,store.study_listing(current["actor_id"],archived=="true"))
        return page(request,listing,lambda x:x["study_id"],cursor,limit)
    @app.post("/api/1/studies",status_code=201)
    def create_study(body:NewStudy,request:Request,current:CurrentSession):
        # An agent session's study creation names its delegation; the store admits it only
        # under a live writer delegation and makes the delegating user the Owner.
        return response(request,store.create_study(current["actor_id"],body.command_id,body.name,
                                                   delegation_id=current["delegation_id"]),201)
    @app.get("/api/1/studies/{study_id}")
    def read_study(study_id:str,request:Request,who:Actor):return response(request,store.study_read(who,valid_id(study_id)))
    @app.post("/api/1/studies/{study_id}/archive")
    def archive_study(study_id:str,body:StudyArchiveCommand,request:Request,who:Actor):
        return response(request,store.set_study_archived(who,valid_id(study_id),body.command_id,True))
    @app.post("/api/1/studies/{study_id}/restore")
    def restore_study(study_id:str,body:StudyArchiveCommand,request:Request,who:Actor):
        return response(request,store.set_study_archived(who,valid_id(study_id),body.command_id,False))
    @app.get("/api/1/studies/{study_id}/execution-readiness")
    def readiness(study_id:str,request:Request,who:Actor):
        sid=valid_id(study_id)
        with store.connection() as db:store.authorize(db,who,sid)
        if request.query_params:raise DomainError("invalid_request",400)
        return response(request,execution_readiness(store,model,who,sid))
    @app.patch("/api/1/studies/{study_id}")
    def patch_study(study_id:str,body:StudyPatch,request:Request,who:Actor):
        changes=body.model_dump(exclude={"command_id","expected_revision"},exclude_unset=True)
        if any(v is None for v in changes.values()):raise DomainError("invalid_request",400)
        return response(request,store.update_study(who,valid_id(study_id),body.command_id,body.expected_revision,changes))

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

    @app.get('/api/1/studies/{study_id}/approach')
    def approach_state(study_id:str,request:Request,who:Actor):
        sid=valid_id(study_id);approach_query(request,who,sid)
        return approach_result(request,'ApproachState2',approaches.state(who,sid))

    @app.post('/api/1/studies/{study_id}/approach/preview')
    def approach_preview(study_id:str,request:Request,who:Actor,body:dict=Body(...)):
        sid=valid_id(study_id);approach_query(request,who,sid)
        return approach_result(request,'ApproachPreviewRead3',approaches.preview(who,sid,body))

    @app.post('/api/1/studies/{study_id}/approach/draft')
    def approach_draft(study_id:str,request:Request,who:Actor,body:dict=Body(...)):
        sid=valid_id(study_id);approach_query(request,who,sid)
        return approach_result(request,'ApproachDraftRead2',approaches.save_draft(who,sid,body))

    @app.post('/api/1/studies/{study_id}/approach/draft/restore')
    def approach_restore(study_id:str,request:Request,who:Actor,body:dict=Body(...)):
        sid=valid_id(study_id);approach_query(request,who,sid)
        return approach_result(request,'ApproachDraftRead2',approaches.restore(who,sid,body))

    @app.get('/api/1/studies/{study_id}/approach/versions')
    def approach_versions(study_id:str,request:Request,who:Actor):
        sid=valid_id(study_id);query=approach_query(request,who,sid,paginated=True)
        return approach_result(request,'ApproachVersionPage2',approaches.versions(who,sid,query))

    @app.post('/api/1/studies/{study_id}/approach/versions',status_code=201)
    def approach_save_version(study_id:str,request:Request,who:Actor,body:dict=Body(...)):
        sid=valid_id(study_id);approach_query(request,who,sid)
        return approach_result(request,'ApproachVersionSavedRead3',approaches.save_version(who,sid,body),201)

    @app.get('/api/1/studies/{study_id}/approach/versions/{version_id}')
    def approach_version(study_id:str,version_id:str,request:Request,who:Actor):
        sid=valid_id(study_id);approach_query(request,who,sid)
        return approach_result(request,'ApproachSavedRead3',approaches.read(who,sid,valid_id(version_id)))

    @app.get('/api/1/studies/{study_id}/approach/versions/{version_id}/usage')
    def approach_usage(study_id:str,version_id:str,request:Request,who:Actor):
        sid=valid_id(study_id);query=approach_query(request,who,sid,usage=True,paginated=True)
        return approach_result(request,'ApproachUsagePage1',approaches.usage(who,sid,valid_id(version_id),query))


    @app.get("/api/1/studies/{study_id}/unit-catalog")
    def unit_catalog(study_id:str,request:Request,who:Actor):
        sid=valid_id(study_id)
        with store.connection() as db:store.authorize(db,who,sid)
        if request.query_params:raise DomainError("invalid_request",400)
        return response(request,coordinator.unit_catalog(who,sid))

    @app.get("/api/1/studies/{study_id}/models")
    def models(study_id:str,request:Request,who:Actor,cursor:str|None=None,limit:int=100):
        return page(request,coordinator.models(who,valid_id(study_id)),lambda x:x["model_id"],cursor,limit)
    @app.post("/api/1/studies/{study_id}/models",status_code=201)
    def new_model(study_id:str,body:NewModel|NewModel3,request:Request,who:Actor):
        valid_id(study_id);data=body.model_dump()
        private=dict(data,expected_revision=None,study_id=study_id)
        return remote_response(request,coordinator.execute(who,study_id,"create",None,data,private,"/models","CreateRequest","ModelDraftResponse4",association=True))
    @app.post("/api/1/studies/{study_id}/model-imports",status_code=201)
    def import_model(study_id:str,body:ImportModel,request:Request,who:Actor):
        valid_id(study_id);data=body.model_dump()
        private=dict(command_id=body.command_id,expected_revision=None,study_id=study_id,package=body.package,preserve_public_ids=True)
        return remote_response(request,coordinator.execute(who,study_id,"import",None,data,private,"/imports","Import","ModelDraftResponse4",association=True))
    @app.get("/api/1/studies/{study_id}/models/{model_id}")
    def model_draft(study_id:str,model_id:str,request:Request,who:Actor):
        result=coordinator.read(who,valid_id(study_id),valid_id(model_id))
        return response(request,**result)
    @app.get("/api/1/studies/{study_id}/models/{model_id}/revisions")
    def revisions(study_id:str,model_id:str,request:Request,who:Actor,cursor:str|None=None,limit:str="50"):
        return response(request,**coordinator.revisions(who,valid_id(study_id),valid_id(model_id),request.query_params.multi_items()))
    @app.get("/api/1/studies/{study_id}/models/{model_id}/revisions/{revision_id}")
    def revision(study_id:str,model_id:str,revision_id:str,request:Request,who:Actor):
        result=coordinator.read(who,valid_id(study_id),valid_id(model_id),"/revisions/"+valid_id(revision_id),response_schema="ModelRevisionResponse4")
        return response(request,**result)
    @app.get("/api/1/studies/{study_id}/models/{model_id}/export")
    def export(study_id:str,model_id:str,model_revision_id:str,request:Request,who:Actor):
        result=coordinator.read(who,valid_id(study_id),valid_id(model_id),"/export?revision="+valid_id(model_revision_id),response_schema="ModelPackageResponse")
        return response(request,**result)

    @app.get("/api/1/studies/{study_id}/models/{model_id}/assumption-evidence")
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
        route.__name__="model_"+action
        app.post("/api/1/studies/{study_id}/models/{model_id}/"+action)(route)
    for args in [("preview","PreviewRead4","ModelDraftEditResponse4",False),("edits","ApplyRead4","ModelDraftEditResponse4",True),
                 ("commits","Commit","ModelRevisionResponse4",True),("validate","Validate","ValidationResultResponse",False)]:
        modeling_route(*args)

    @app.post("/api/1/studies/{study_id}/evidence",status_code=201)
    def evidence(study_id:str,request:Request,who:Actor,body:dict=Body(...)):
        validate("EvidenceCreate",body)
        return response(request,store.add_evidence(who,valid_id(study_id),body["command_id"],
            {k:v for k,v in body.items() if k!="command_id"},coordinator=coordinator),201)
    @app.get("/api/1/studies/{study_id}/evidence")
    def list_evidence(study_id:str,request:Request,who:Actor,cursor:str|None=None,limit:str="50",
        scope_kind:str|None=None,model_id:str|None=None,model_revision_id:str|None=None,instance_id:str|None=None,
        port_id:str|None=None,configuration_revision_id:str|None=None,run_id:str|None=None,legacy_scope:str|None=None,view:str="heads"):
        return response(request,**store.list_evidence(who,valid_id(study_id),request.query_params.multi_items()))
    @app.get("/api/1/studies/{study_id}/evidence/{evidence_version_id}")
    def get_evidence(study_id:str,evidence_version_id:str,request:Request,who:Actor):
        return response(request,store.evidence_version(who,valid_id(study_id),valid_id(evidence_version_id)))
    @app.get("/api/1/studies/{study_id}/evidence-families/{evidence_id}")
    def evidence_family(study_id:str,evidence_id:str,request:Request,who:Actor):
        if request.query_params:raise DomainError("invalid_request",400)
        return response(request,store.evidence_family(who,valid_id(study_id),valid_id(evidence_id)))
    @app.get("/api/1/studies/{study_id}/evidence-families/{evidence_id}/versions")
    def evidence_versions(study_id:str,evidence_id:str,request:Request,who:Actor,cursor:str|None=None,limit:str="50"):
        return response(request,**store.evidence_versions(who,valid_id(study_id),valid_id(evidence_id),request.query_params.multi_items()))
    @app.post("/api/1/studies/{study_id}/evidence-families/{evidence_id}/versions",status_code=201)
    def revise_evidence(study_id:str,evidence_id:str,request:Request,who:Actor,body:dict=Body(...)):
        validate("EvidenceRevise3",body)
        return response(request,store.revise_evidence(who,valid_id(study_id),valid_id(evidence_id),
            body["command_id"],body["expected_revision"],
            {k:v for k,v in body.items() if k not in {"command_id","expected_revision"}},coordinator=coordinator),201)
    @app.post("/api/1/studies/{study_id}/configurations/preview")
    def preview_configuration(study_id:str,request:Request,who:Actor,body:dict=Body(...)):
        version=body.get("schema_version")
        validate("ConfigurationRequest4" if version=="4" else "ConfigurationRequest3" if version=="3" else "ConfigurationRequest2" if version=="2" else "ConfigurationCandidate1",body)
        if version in ("3","4"):
            with store.connection() as db:store.authorize(db,who,valid_id(study_id))
            if not callable(getattr(configs,"_preview"+version,None)):raise DomainError("unsupported_capability",422)
        return response(request,configs.preview(who,valid_id(study_id),body)[0])
    @app.post("/api/1/studies/{study_id}/configurations",status_code=201)
    def commit_configuration(study_id:str,request:Request,who:Actor,body:dict=Body(...)):
        candidate=body.get("configuration")
        version=candidate.get("schema_version") if isinstance(candidate,dict) else None
        validate("ConfigurationCommit4" if version=="4" else "ConfigurationCommit3" if version=="3" else "ConfigurationCommit2" if version=="2" else "ConfigurationCommit1",body)
        if body.get("configuration_id"):valid_id(body["configuration_id"])
        if version in ("3","4"):
            with store.connection() as db:store.authorize(db,who,valid_id(study_id),write=True)
            if not callable(getattr(configs,"_commit"+version,None)):raise DomainError("unsupported_capability",422)
        return response(request,configs.commit(who,valid_id(study_id),body),201)
    @app.get('/api/1/studies/{study_id}/runs/{run_id}/modified-run-seed')
    def modified_run_seed(study_id:str,run_id:str,request:Request,who:Actor):
        if request.query_params:raise DomainError('invalid_request',400)
        result=modified_runs.seed(who,valid_id(study_id),valid_id(run_id))
        validate("ModifiedRunSeedRead6",result,remote=True)
        return response(request,result)
    @app.get('/api/1/studies/{study_id}/result-sources')
    def result_sources(study_id:str,request:Request,who:Actor,limit:str='25',cursor:str|None=None):
        pairs=list(request.query_params.multi_items())
        if (any(key not in {'limit','cursor'} for key,_ in pairs) or len({key for key,_ in pairs})!=len(pairs)
                or limit not in {str(i) for i in range(1,51)}):
            raise DomainError('invalid_request',400)
        return response(request,result_bindings.inventory(who,valid_id(study_id),limit=int(limit),cursor=cursor))
    @app.get("/api/1/studies/{study_id}/configurations")
    def list_configurations(study_id:str,request:Request,who:Actor,cursor:str|None=None,limit:int=100):
        return page(request,configs.read(who,valid_id(study_id)),lambda x:x["configuration"]["configuration_revision_id"],cursor,limit)
    @app.get("/api/1/studies/{study_id}/configurations/{revision_id}")
    def get_configuration(study_id:str,revision_id:str,request:Request,who:Actor):
        return response(request,configs.read(who,valid_id(study_id),valid_id(revision_id)))
    @app.post('/api/1/studies/{study_id}/computational-record-previews',status_code=202)
    def preview_record(study_id:str,request:Request,who:Actor,body:dict=Body(...)):
        if request.query_params:raise DomainError('invalid_request',400)
        return response(request,records.enqueue_preview(who,valid_id(study_id),body),202)
    @app.post('/api/1/studies/{study_id}/computational-records',status_code=202)
    def create_record(study_id:str,request:Request,who:Actor,body:dict=Body(...)):
        if request.query_params:raise DomainError('invalid_request',400)
        return response(request,records.enqueue_create(who,valid_id(study_id),body),202)
    @app.get('/api/1/studies/{study_id}/computational-records/{request_id}')
    def record_status(study_id:str,request_id:str,request:Request,who:Actor):
        if request.query_params:raise DomainError('invalid_request',400)
        return response(request,records.status(who,valid_id(study_id),valid_id(request_id)))
    @app.get('/api/1/studies/{study_id}/computational-records/{request_id}/download')
    def record_download(study_id:str,request_id:str,request:Request,who:Actor):
        if request.query_params:raise DomainError('invalid_request',400)
        raw=records.download(who,valid_id(study_id),valid_id(request_id))
        return Response(content=raw,media_type='application/zip',headers={
            'Content-Disposition':'attachment; filename="hyprn-mvp-computational-record.zip"',
            'X-Content-SHA256':hashlib.sha256(raw).hexdigest()})
    @app.get("/api/1/studies/{study_id}/commands/{command_id}")
    def receipt(study_id:str,command_id:str,category:str,request:Request,who:Actor):
        valid_id(study_id);valid_id(command_id)
        if category in {'approach_draft','approach_version','approach_restore'}:
            if list(request.query_params.multi_items())!=[('category',category)]:raise DomainError('invalid_request',400)
            return response(request,approaches.receipt(who,study_id,category,command_id))
        row=store.receipt(who,study_id,category,command_id)
        if category=="model":
            # A recorded rejection is a receipt outcome; current authorization
            # failures must propagate even when their code matches that outcome.
            coordinator.reconcile(who,study_id,command_id,receipt_view=True)
            row=store.receipt(who,study_id,category,command_id)
        result=None if row["state"]=="pending_remote" else row["result"]
        if category=="model" and row["state"]=="committed":result=result["response"]
        if category in {'computational_record_preview','computational_record_create'} and result is not None:
            # Reauthorize the retained closure; keep the original receipt result
            # immutable. Work state is obtained from the separate status route.
            records.status(who,study_id,result['request_id'])
        return response(request,dict(command_id=command_id,state=row["state"],result=result,error=row["error"]))
    @app.get("/api/1/commands/{command_id}")
    def study_receipt(command_id:str,category:Literal["study_create"],request:Request,who:Actor):
        row=store.receipt(who,None,category,valid_id(command_id))
        return response(request,dict(command_id=command_id,state=row["state"],result=row["result"],error=row["error"]))
    @app.post("/api/1/studies/{study_id}/runs",status_code=202)
    def submit(study_id:str,body:SubmitRun,request:Request,who:Actor):
        valid_id(body.configuration_revision_id)
        return response(request,submissions.submit(who,valid_id(study_id),body.model_dump()),202)
    @app.get("/api/1/studies/{study_id}/runs/{run_id}")
    def run_status(study_id:str,run_id:str,request:Request,who:Actor):
        result=submissions.read(who,valid_id(study_id),valid_id(run_id))
        if result['state']=='recorded':
            result['history']=history.read(who,study_id,run_id)
            result['retained_integrity']=retained_read_integrity(run_id,result['history'])
        return response(request,result)
    @app.get("/api/1/studies/{study_id}/runs")
    def run_history(study_id:str,request:Request,who:Actor,cursor:str|None=None,limit:int=100):
        return page(request,history.list(who,valid_id(study_id)),lambda x:x['run_id'],cursor,limit)
    @app.get("/api/1/studies/{study_id}/runs/{run_id}/artifacts/{artifact_id}")
    def run_artifact(study_id:str,run_id:str,artifact_id:str,request:Request,who:Actor):
        raw,descriptor=history.read(who,valid_id(study_id),valid_id(run_id),valid_id(artifact_id))
        return Response(content=raw,media_type=descriptor['media_type'],headers={
            'Content-Disposition':'attachment; filename="'+artifact_id+'"','X-Content-SHA256':descriptor['sha256']})
    return app

def from_environment():
    store=Store(os.environ["HYPRN_MVP_APP_STORE"])
    origin=os.environ["HYPRN_MVP_ORIGIN"]
    if not origin.startswith("https://") and not origin.startswith("http://127.0.0.1:"):
        raise ValueError("Use HTTPS or explicitly scoped loopback")
    auth=Auth(store,origin)
    model=ModelingClient(os.environ["HYPRN_MVP_MODEL_URL"],Path(os.environ["HYPRN_MVP_MODEL_KEY_FILE"]).read_bytes().strip())
    app=create_app(store,auth,model)
    from .ui import mount_workspace
    mount_workspace(app,Path('/app/ui'))
    return app
