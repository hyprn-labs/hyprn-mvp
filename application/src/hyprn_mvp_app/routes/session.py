"""Sign-in and sign-out: the session cookie is set and cleared only here."""
from typing import Annotated
from fastapi import APIRouter, Depends, Request
from ..edge import Login, ProfileUpdate, response
from .. import identity
from ..contracts import DomainError

def router(deps):
    auth=deps.auth
    Actor=Annotated[str,Depends(deps.actor)]
    CurrentSession=Annotated[dict,Depends(deps.current_session)]
    r=APIRouter()
    def public_profile(profile):
        return auth.public_profile(profile) if getattr(auth,"hosted",False) else profile

    @r.get("/api/1/session/mode")
    def mode(request:Request):
        return response(request,{"mode":"hosted" if getattr(auth,"hosted",False) else "local"})

    @r.post("/api/1/session/external")
    def external(request:Request):
        if not getattr(auth,"hosted",False):raise DomainError("resource_not_found",404)
        session=auth.bootstrap()
        from ..database import actor_scope
        with actor_scope(session["actor_id"],request_boundary=True):
            with deps.store.connection() as db:
                profile=public_profile(identity.profile(db,session["actor_id"]))
        result=response(request,{**{k:v for k,v in session.items() if k!="token"},"profile":profile})
        result.set_cookie("hyprn_mvp_session",session["token"],httponly=True,samesite="strict",
                          secure=True,path="/api/1",max_age=8*60*60)
        return result

    @r.get("/api/1/profile")
    def profile(request:Request,current:CurrentSession):
        if current["kind"]!="user":raise DomainError("forbidden",403)
        with deps.store.connection() as db:
            return response(request,public_profile(identity.profile(db,current["actor_id"])))

    @r.put("/api/1/profile")
    def update_profile(body:ProfileUpdate,request:Request,current:CurrentSession):
        if current["kind"]!="user":raise DomainError("forbidden",403)
        with deps.store.connection(write=True) as db:
            return response(request,public_profile(identity.update(
                db,current["actor_id"],body.display_alias,body.expected_revision)))

    @r.post("/api/1/session")
    def login(body:Login,request:Request):
        session=auth.login(body.username,body.password)
        with deps.store.connection() as db:
            profile=identity.profile(db,session["actor_id"])
        result=response(request,{**{k:v for k,v in session.items() if k!="token"},"profile":profile})
        result.set_cookie("hyprn_mvp_session",session["token"],httponly=True,samesite="strict",
                          secure=auth.origin.startswith("https://"),path="/api/1",max_age=8*60*60)
        return result
    @r.delete("/api/1/session")
    def logout(request:Request,who:Actor):
        auth.logout(request.cookies.get("hyprn_mvp_session"))
        result=response(request,{"ended":True});result.delete_cookie("hyprn_mvp_session",path="/api/1")
        return result
    return r
