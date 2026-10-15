"""Version 1 public API edge: the boundary middleware, the exception handlers, the session and
actor dependencies and the composition of the per-owner routers. No route is defined here; each
domain owner's routes live in ``routes/<owner>.py`` and the shared helpers in ``edge``."""
import json
import os
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from starlette.exceptions import HTTPException
from .auth import Auth
from .agent_policy import route_allowed
from .contracts import DomainError, canonical, issue, uid
from .edge import RouteDeps, error_response, request_diagnostics, valid_id
from .store import Store
from .modeling import Coordinator, ModelingClient
from .configuration import Configurations
from .approach import Approaches
from .answers import ensure as ensure_answers
from .execution import Submissions
from .history import History
from .result_bindings import ResultBindings
from .modified_runs import ModifiedRuns
from .computational_export import records_for_store
from .routes import (
    answers, approach, capabilities, commands, configurations, evidence, exploration,
    models, readiness,
    records as record_routes, runs, session as session_routes, studies,
)
from .agent_runtime import routes as agent_routes, schema as agent_schema

MALFORMED_BODY=("Request body must be one strict JSON value: no duplicate keys, non-finite or out-of-range "
    "numbers or invalid text, and at most 32 levels of nesting.")

MUTATIONS=frozenset({"POST","PATCH","DELETE","PUT"})

def agent_boundary(method,path,session,registry=None):
    """Refuse, before routing, what a delegated agent API session may never do: the session
    routes, any mutation from a read-only session, any route the agent allowlist refuses
    (403), and any study other than its delegation's study (the same undisclosed 404)."""
    if path=="/api/1/session":raise DomainError("forbidden",403)
    if session["read_only"] and method in MUTATIONS:raise DomainError("forbidden",403)
    if not route_allowed(method,path,session["effects"],registry=registry):
        raise DomainError("forbidden",403)
    parts=path.split("/")
    if len(parts)>4 and parts[1:4]==["api","1","studies"] and parts[4]!=session["study_id"]:
        raise DomainError("resource_not_found",404)

# Inclusion order is registration order, which fixes the generated contract's path order and
# every operation id: append a new owner's router, never reorder.
ROUTERS=(session_routes,capabilities,studies,readiness,approach,models,evidence,configurations,
         record_routes,commands,runs,agent_routes,answers,exploration)
# Route options an owner router may not set: re-registration carries path, endpoint, method,
# status code and name only, so any other declared option would be refused, never dropped.
ROUTE_OPTIONS=("response_model","tags","dependencies","summary","description","responses","deprecated","operation_id",
               "include_in_schema","response_class","callbacks","openapi_extra")

def include(app,owner):
    """Register an owner router's routes on the application router itself, in their order and
    exactly as routes declared on the application, so the application's route table stays one
    flat list of its routes (an included-router wrapper would change it)."""
    for route in owner.routes:
        if not isinstance(route,APIRoute) or len(route.methods)!=1:raise TypeError("one-method API routes only")
        app.router.add_api_route(route.path,route.endpoint,methods=list(route.methods),status_code=route.status_code,name=route.name)
        added=app.router.routes[-1]
        if any(getattr(added,k)!=getattr(route,k) for k in ROUTE_OPTIONS):raise TypeError("unsupported route option: "+route.name)

def create_app(store,auth,model,*,environ=None,registry=None):
    """The application over its owners. ``environ`` is the process environment the agent
    routes read (the kill switch; ``os.environ`` by default); ``registry`` is the tool
    registry the agent route allowlist derives from (the packaged one by default)."""
    if store is not None:
        # Runtime-owned agent tables, through the store's connection (idempotent).
        agent_schema.ensure(store)
        ensure_answers(store)
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
                agent_boundary(request.method,path,session,registry)
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
    def actor(request:Request):
        # The agent actor for a delegated agent session, so receipts carry the agent.
        return auth.authenticate(request.cookies.get("hyprn_mvp_session"))["actor_id"]
    deps=RouteDeps(store=store,auth=auth,model=model,coordinator=coordinator,configs=configs,approaches=approaches,
                   submissions=submissions,history=history,result_bindings=result_bindings,modified_runs=modified_runs,
                   records=records,current_session=current_session,actor=actor,
                   environ=os.environ if environ is None else environ)
    for owner in ROUTERS:include(app,owner.router(deps))
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
