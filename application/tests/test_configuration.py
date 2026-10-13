"""Public configuration preview and freeze for a model2 revision (configuration3 requests)."""
import copy
import hashlib
import json
import sqlite3
from pathlib import Path
from fastapi.testclient import TestClient
from hyprn_mvp_app.api import create_app
from hyprn_mvp_app.store import Store,digest
from test_api import api,study,model_revision,post,uid,ORIGIN,candidate,configuration_request,configuration_commit
from model_client import ruby  # Bound to this scope's owned modeling container by the api fixture.

def config(api):
    s,m=model_revision(api)
    return s,m,configuration_request(api,s,m)

def remote_inventory():
    # SQLite stays within its Linux container; no host WAL reads.
    return ruby("puts JSON.generate(ActiveRecord::Base.connection.tables.sort.to_h { |t| [t,ActiveRecord::Base.connection.select_value('SELECT COUNT(*) FROM '+ActiveRecord::Base.connection.quote_table_name(t))] })",rails=True)

def configuration_rows(store):
    with sqlite3.connect(store.path) as db:
        return db.execute("SELECT COUNT(*) FROM configurations").fetchone()[0]

def test_preview_is_pure_in_both_stores_and_checks_exact_digests(api):
    c,store,_,_,transport,_=api;s,m,cfg=config(api)
    before=store.path.read_bytes();files=sorted(p.name for p in store.path.parent.iterdir());remote=remote_inventory()
    result=post(c,f"/studies/{s['study_id']}/configurations/preview",cfg)["data"]
    assert result["compatibility"]["compatible"] and result["request_digest"]==digest(cfg)
    assert result["candidate_digest"]==digest(result["resolved_candidate"]) and result["model_digest"]==m["digest"]
    assert store.path.read_bytes()==before and sorted(p.name for p in store.path.parent.iterdir())==files
    assert remote_inventory()==remote
    assert not any("prepare-execution" in p for _,p in transport.calls)

def test_free_input_semantics_and_unsupported_numerics(api):
    c=api[0];s,m,cfg=config(api);path=f"/studies/{s['study_id']}/configurations/preview"
    for value in [0,-2,0.25]:
        trial=copy.deepcopy(cfg);trial["inputs"][0]["value"]=value
        result=post(c,path,trial)["data"]
        assert result["compatibility"]["compatible"]
        assert result["resolved_candidate"]["inputs"][0]["value"]==value  # Zero stays an explicit value.
    for mutate in [lambda t:t.update(inputs=[]),lambda t:t["inputs"][0].update(units="s")]:
        trial=copy.deepcopy(cfg);mutate(trial)
        assert not post(c,path,trial)["data"]["compatibility"]["compatible"]
    trial=copy.deepcopy(cfg);trial["inputs"][0]["value"]=""
    post(c,path,trial,400)
    trial=copy.deepcopy(cfg);trial["numerical"]["mode"]="coupled"
    post(c,path,trial,422)

def test_configuration_freezes_model_context_evidence_replay_and_outage(api):
    c,store,auth,model,transport,actor=api;s,m,cfg=config(api);sid=s["study_id"]
    evidence=post(c,f"/studies/{sid}/evidence",dict(command_id=uid(),scope=None,kind="note",content="Exact evidence",source_refs=[]),201)["data"]
    cfg["inputs"][0]["provenance"]["evidence_version_ids"]=[evidence["evidence_version_id"]]
    body=configuration_commit(api,cfg)
    frozen=post(c,f"/studies/{sid}/configurations",body,201)["data"]
    snapshots=frozen["configuration"]["evidence_snapshots"]
    assert [x["evidence_version_id"] for x in snapshots]==[evidence["evidence_version_id"]]
    assert {k:snapshots[0][k] for k in ("kind","content","source_refs")}=={k:evidence[k] for k in ("kind","content","source_refs")}
    assert frozen["model_snapshot"]==m
    current=store.study(actor,sid)
    store.update_study(actor,sid,uid(),current["revision"],{"description":"Later context"})
    transport.fail_before=True
    restarted=TestClient(create_app(Store(store.path),auth,model),base_url=ORIGIN)
    restarted.cookies.update(c.cookies);restarted.headers.update(c.headers)
    assert restarted.get(f"/api/1/studies/{sid}/configurations/{frozen['configuration']['configuration_revision_id']}").json()["data"]==frozen
    # Replay is answered from the local receipt while the private service is unavailable.
    assert post(restarted,f"/studies/{sid}/configurations",body,201)["data"]==frozen
    transport.fail_before=False
    # A new command against the earlier study context never freezes.
    post(restarted,f"/studies/{sid}/configurations",{**body,"command_id":uid()},409)
    assert configuration_rows(store)==1

def test_family_head_cas_tamper_evidence_and_backend_outage(api):
    c,store,_,_,transport,_=api;s,m,cfg=config(api);sid=s["study_id"];path=f"/studies/{sid}/configurations"
    body=configuration_commit(api,cfg)
    transport.fail_before=True;post(c,path,body,503);transport.fail_before=False
    transport.tamper=True;post(c,path,body,503);transport.tamper=False
    assert configuration_rows(store)==0
    first=post(c,path,body,201)["data"]["configuration"]
    body2={**body,"command_id":uid(),"expected_revision":first["configuration_revision_id"],"configuration_id":first["configuration_id"]}
    second=post(c,path,body2,201)["data"]["configuration"]
    assert second["parent_revision_id"]==first["configuration_revision_id"]
    post(c,path,{**body2,"command_id":uid()},409)
    # Evidence that does not exist in this study is never frozen.
    evil=copy.deepcopy(cfg);evil["inputs"][0]["provenance"]["evidence_version_ids"]=[uid()]
    refused=c.post("/api/1"+path+"/preview",json=evil)
    assert refused.status_code==422 and refused.json()["error"]["code"]=="invalid_configuration"
    assert [f["code"] for f in refused.json()["error"]["fields"]]==["unresolved_evidence"]
    post(c,path,{**body,"command_id":uid(),"configuration":evil},422)
    assert configuration_rows(store)==2
