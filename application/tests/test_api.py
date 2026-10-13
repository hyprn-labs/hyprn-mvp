"""Public session/API against real private HTTP, using a test-only network ingress.

The private service is the modeling deployment owned by this test scope
(deployment/tests/modeling_deployment_fixture.owned_modeling), reached only through its own
container and its own service credential; never an installation's service."""
import copy
import json
import sys
from pathlib import Path
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from hyprn_mvp_app.api import create_app
from hyprn_mvp_app.modeling import ModelingClient
from hyprn_mvp_app.store import Store
from hyprn_mvp_app.auth import Auth

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'deployment/tests'))
from model_client import raw_request
from contracts.tests.test_modeling_contract import creation, candidate
# One owned modeling deployment per test session, shared by every module that uses ``api``.
pytest_plugins=('modeling_deployment_fixture',)

def uid():return str(uuid4())
from conftest import LOOPBACK_ORIGIN as ORIGIN

class FaultTransport:
    def __init__(self,container):self.container=container;self.fail_before=False;self.fail_after=False;self.calls=[];self.tamper=False
    def __call__(self,method,path,body,headers):
        self.calls.append((method,path))
        if self.fail_before:raise OSError("synthetic unavailable")
        status,result=raw_request(method,path,body,headers,container=self.container)
        if self.fail_after and method=="POST":
            self.fail_after=False
            raise OSError("response lost after durable remote commit")
        if self.tamper and path.endswith("/configuration-compatibility") and status==200:
            result["data"]["candidate_digest"]="0"*64
        return status,result

@pytest.fixture
def api(tmp_path,owned_modeling):
    root,deployment,_=owned_modeling
    store=Store(tmp_path/"app.sqlite")
    auth=Auth(store,ORIGIN);actor=auth.provision("owner","correct horse battery staple")
    transport=FaultTransport(deployment.container)
    model=ModelingClient("http://modeling:3000/modeling/1",
        (root/"credentials/model.key").read_bytes().strip(),transport=transport)
    app=create_app(store,auth,model)
    client=TestClient(app,base_url=ORIGIN)
    session=client.post("/api/1/session",json={"username":"owner","password":"correct horse battery staple"},headers={"Origin":ORIGIN})
    assert session.status_code==200,session.text
    client.headers.update({"Origin":ORIGIN,"X-CSRF-Token":session.json()["data"]["csrf_token"]})
    return client,store,auth,model,transport,actor

def post(client,path,body,status=200):
    result=client.post("/api/1"+path,json=body)
    assert result.status_code==status,result.text
    return result.json()

def study(api):
    return post(api[0],"/studies",dict(command_id=uid(),name="Study"),201)["data"]

def model_revision(api):
    c=api[0];s=study(api);sid=s["study_id"]
    m=post(c,f"/studies/{sid}/models",dict(command_id=uid(),expected_revision=s["revision"],name="Independent app model",template="empty"),201)["data"]
    m=post(c,f"/studies/{sid}/models/{m['model_id']}/edits",dict(command_id=uid(),expected_revision=m["draft_revision"],edits=creation()))["data"]
    m=post(c,f"/studies/{sid}/models/{m['model_id']}/commits",dict(command_id=uid(),expected_revision=m["draft_revision"]))["data"]
    return s,m

def configuration_request(api,s,m):
    """The public configuration3 request for a model2 revision, the only configuration a model2
    accepts: explicit literal inputs with provenance, the current study context, no assumptions."""
    sid=s["study_id"];cfg=candidate(m,sid)
    study=api[0].get(f"/api/1/studies/{sid}").json()["data"]
    return dict(schema_version="3",study_id=sid,model_id=m["model_id"],model_revision_id=m["model_revision_id"],name=cfg["name"],
        inputs=[dict(kind="literal",**{k:i[k] for k in ("target","value","units","provenance")}) for i in cfg["inputs"]],
        criteria=cfg["criteria"],numerical=cfg["numerical"],notes=[],derivation=None,
        context_source=dict(kind="current_study",expected_study_revision=study["revision"]),
        assumptions=[],general_context_evidence_version_ids=[])

def configuration_commit(api,request,**fields):
    """A configuration3 commit pins the digest of the exact preview the engineer saw."""
    preview=post(api[0],f"/studies/{request['study_id']}/configurations/preview",request)["data"]
    body=dict(command_id=uid(),expected_revision=None,configuration_id=None,configuration=request,
              expected_preview_digest=preview["candidate_digest"])
    body.update(fields)
    return body

def test_session_cookie_origin_csrf_and_forged_actor(api):
    c=api[0]
    assert c.cookies.get("hyprn_mvp_session")
    for headers in [{"Origin":"https://evil.example"},{"X-CSRF-Token":"wrong"}]:
        assert c.post("/api/1/studies",json=dict(command_id=uid(),name="bad"),headers=headers).status_code==403
    public=TestClient(c.app,base_url=ORIGIN)
    assert public.get("/api/1/studies",headers={"X-Actor-ID":api[5]}).status_code==401
    assert public.post("/api/1/session",json=dict(username="owner",password="correct horse battery staple")).status_code==403
    response=public.post("/api/1/session",json=dict(username="owner",password="correct horse battery staple"),headers={"Origin":ORIGIN})
    assert "HttpOnly" in response.headers["set-cookie"] and "SameSite=strict" in response.headers["set-cookie"]
    assert c.delete("/api/1/session").status_code==200
    assert c.get("/api/1/studies").status_code==401

def test_study_evidence_receipts_and_cross_study(api):
    c=api[0];s=study(api);sid=s["study_id"];command=uid()
    note=post(c,f"/studies/{sid}/evidence",dict(command_id=command,scope=None,kind="note",content="Assumption",source_refs=[]),201)["data"]
    assert c.get(f"/api/1/studies/{sid}/evidence/{note['evidence_version_id']}").json()["data"]==note
    other=study(api)
    assert c.get(f"/api/1/studies/{other['study_id']}/evidence/{note['evidence_version_id']}").status_code==404
    assert c.get(f"/api/1/studies/{sid}/commands/{command}?category=evidence").json()["data"]["state"]=="committed"
    assert c.patch(f"/api/1/studies/{sid}",json=dict(command_id=uid(),expected_revision="stale",name="bad")).status_code==409

def test_remote_response_loss_reconciles_one_model_after_restart(api):
    c,store,auth,model,transport,actor=api;s=study(api);sid=s["study_id"]
    body=dict(command_id=uid(),expected_revision=s["revision"],name="Lost response",template="empty")
    transport.fail_after=True
    pending=post(c,f"/studies/{sid}/models",body,202)
    assert pending["data"]["state"]=="pending_remote"
    restarted=TestClient(create_app(Store(store.path),auth,model),base_url=ORIGIN)
    restarted.cookies.update(c.cookies);restarted.headers.update(c.headers)
    receipt=restarted.get(f"/api/1/studies/{sid}/commands/{body['command_id']}?category=model").json()["data"]
    assert receipt["state"]=="committed"
    same=post(restarted,f"/studies/{sid}/models",body,201)["data"]
    assert same["model_id"]==receipt["result"]["data"]["model_id"]
    assert len(restarted.get(f"/api/1/studies/{sid}/models").json()["data"])==1
    post(restarted,f"/studies/{sid}/models",{**body,"name":"Changed"},409)

def test_pending_before_send_same_command_and_stale_association(api):
    c,store,auth,model,transport,actor=api;s=study(api);sid=s["study_id"]
    body=dict(command_id=uid(),expected_revision=s["revision"],name="Before send",template="empty")
    transport.fail_before=True
    post(c,f"/studies/{sid}/models",body,202)
    transport.fail_before=False
    post(c,f"/studies/{sid}/models",body,201)
    before=len(transport.calls)
    post(c,f"/studies/{sid}/models",{**body,"command_id":uid()},409)
    assert len(transport.calls)==before

def test_model_read_preview_validate_export_and_authorized_replay(api):
    c,store,_,_,transport,actor=api;s,m=model_revision(api);sid=s["study_id"];mid=m["model_id"]
    base=f"/studies/{sid}/models/{mid}"
    draft=c.get("/api/1"+base).json()["data"]
    preview=post(c,base+"/preview",dict(expected_revision=draft["draft_revision"],edits=[]))
    assert preview["data"]["model_id"]==draft["model_id"]
    assert c.get("/api/1"+base).json()["data"]==draft
    assert post(c,base+"/validate",dict(model_revision_id=m["model_revision_id"]))["data"]["validation_scope"]=="static"
    assert c.get("/api/1"+base+f"/export?model_revision_id={m['model_revision_id']}").status_code==200
    other=study(api)
    assert c.get(f"/api/1/studies/{other['study_id']}/models/{mid}").status_code==404
    current=store.study(actor,sid)
    store.set_membership(actor,sid,uid(),current["revision"],"replacement","owner")
    current=store.study(actor,sid)
    store.set_membership(actor,sid,uid(),current["revision"],actor,None)
    before=len(transport.calls)
    assert c.get("/api/1"+base).status_code==404
    assert len(transport.calls)==before

def test_closed_bounded_json_and_explicit_capabilities(api):
    c=api[0];s=study(api);sid=s["study_id"]
    for raw in ['{"command_id":"'+uid()+'","name":"a","name":"b"}','{"x":NaN}','['*34+'0'+']'*34]:
        assert c.post("/api/1/studies",content=raw,headers={"Content-Type":"application/json"}).status_code==400
    assert c.post("/api/1/studies",content=b"x"*(2*1024*1024+1),headers={"Content-Type":"application/json"}).status_code==413
    post(c,"/studies",dict(command_id=uid(),name="Bad",native_payload={}),400)
    cap=c.get("/api/1/capabilities").json()["data"]
    assert cap["execution"]=="durable_scalar_submission"
    post(c,f"/studies/{sid}/runs",dict(command_id=uid(),configuration_revision_id=uid()),404)

def test_public_import_is_typed_and_collision_receipt_replays(api):
    c=api[0];s,m=model_revision(api);sid=s["study_id"]
    package=c.get(f"/api/1/studies/{sid}/models/{m['model_id']}/export?model_revision_id={m['model_revision_id']}").json()["data"]
    target=study(api);tid=target["study_id"]
    body=dict(command_id=uid(),expected_revision=target["revision"],package=package)
    # Preserve-ID import into this same authoritative service must reject collision.
    result=post(c,f"/studies/{tid}/model-imports",body,409)
    assert result["error"]["code"]=="identity_collision"
    assert post(c,f"/studies/{tid}/model-imports",body,409)["error"]["code"]=="identity_collision"
    assert c.get(f"/api/1/studies/{tid}/models").json()["data"]==[]
    receipt=c.get(f"/api/1/studies/{tid}/commands/{body['command_id']}?category=model")
    assert receipt.status_code==200 and receipt.json()["data"]["state"]=="rejected"
