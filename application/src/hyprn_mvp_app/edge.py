"""What the HTTP edge and the per-owner routers share: closed request models, identifier and
request-shape checks, the response envelope, pagination, the error envelope and the delegated
study scope. This module reaches no project module but ``contracts``; it never imports ``api``,
a route module or an agent module, so every router depends on the edge and never on another
router or on the application composition."""
from dataclasses import dataclass
from typing import Any, Callable, Literal
from uuid import UUID
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from .contracts import MAX_DIAGNOSTICS, DomainError, issue, uid

# Class names are schema names in the generated public contract: never rename them.
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

@dataclass(frozen=True)
class RouteDeps:
    """The owners ``create_app`` constructs, handed unchanged to every ``router(deps)``. A
    router never constructs an owner, never reads the environment and never imports ``api``."""
    store:Any
    auth:Any
    model:Any
    coordinator:Any
    configs:Any
    approaches:Any
    submissions:Any
    history:Any
    result_bindings:Any
    modified_runs:Any
    records:Any
    current_session:Callable
    actor:Callable

def valid_id(value):
    try:
        if str(UUID(value))!=value:raise ValueError()
    except (ValueError,TypeError,AttributeError):raise DomainError("invalid_request",400)
    return value

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

def delegated_scope(session,studies):
    """An agent session sees only its delegation's study; a human session sees its list."""
    if session["kind"]!="agent":return studies
    return [s for s in studies if s["study_id"]==session["study_id"]]

def error_response(request,error):
    return JSONResponse(status_code=error.status,content={"error":dict(code=error.code,message=error.code.replace("_"," "),
        request_id=getattr(request.state,"request_id",uid()),command_id=getattr(request.state,"command_id",None),
        resource_id=None,current_revision=error.current_revision,fields=error.fields,outcome=error.outcome)})

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
