"""Sign-in and sign-out: the session cookie is set and cleared only here."""
from typing import Annotated
from fastapi import APIRouter, Depends, Request
from ..edge import Login, response

def router(deps):
    auth=deps.auth
    Actor=Annotated[str,Depends(deps.actor)]
    r=APIRouter()

    @r.post("/api/1/session")
    def login(body:Login,request:Request):
        session=auth.login(body.username,body.password)
        result=response(request,{k:v for k,v in session.items() if k!="token"})
        result.set_cookie("hyprn_mvp_session",session["token"],httponly=True,samesite="strict",
                          secure=auth.origin.startswith("https://"),path="/api/1",max_age=8*60*60)
        return result
    @r.delete("/api/1/session")
    def logout(request:Request,who:Actor):
        auth.logout(request.cookies.get("hyprn_mvp_session"))
        result=response(request,{"ended":True});result.delete_cookie("hyprn_mvp_session",path="/api/1")
        return result
    return r
