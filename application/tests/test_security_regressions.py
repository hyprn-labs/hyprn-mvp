import copy
import json
from test_api import api,study,model_revision,post,uid,configuration_commit
from test_configuration import config

def test_revoked_model_and_configuration_replay_never_reaches_backend(api):
    c,store,_,_,transport,actor=api
    s,m,cfg=config(api);sid=s["study_id"]
    body=configuration_commit(api,cfg)
    saved=post(c,f"/studies/{sid}/configurations",body,201)["data"]
    with store.connection() as db:
        record=db.execute("SELECT command_id,request FROM receipts WHERE scope=? AND category='model' ORDER BY rowid DESC LIMIT 1",(sid,)).fetchone()
        request=json.loads(record["request"]);command=record["command_id"]
    current=store.study(actor,sid)
    store.set_membership(actor,sid,uid(),current["revision"],"new-owner","owner")
    current=store.study(actor,sid)
    store.set_membership(actor,sid,uid(),current["revision"],actor,None)
    before=len(transport.calls)
    assert c.get(f"/api/1/studies/{sid}/commands/{command}?category=model").status_code==404
    post(c,f"/studies/{sid}/models/{m['model_id']}/commits",request["body"],404)
    post(c,f"/studies/{sid}/configurations",body,404)
    assert c.get(f"/api/1/studies/{sid}/configurations/{saved['configuration']['configuration_revision_id']}").status_code==404
    assert len(transport.calls)==before

def test_cursor_pagination_is_stable_and_scoped(api):
    c=api[0]
    ids={study(api)["study_id"] for _ in range(3)}
    seen=[];cursor=None
    while True:
        url="/api/1/studies?limit=1"+("&cursor="+cursor if cursor else "")
        response=c.get(url);assert response.status_code==200,response.text
        page=response.json();seen.extend(x["study_id"] for x in page["data"])
        cursor=page["next_cursor"]
        if not cursor:break
    assert seen==sorted(ids)
    assert c.get("/api/1/studies?limit=101").status_code==400
    assert c.get("/api/1/studies?cursor="+uid()).status_code==404

def test_untrusted_json_numbers_provenance_and_evidence_content(api):
    c=api[0];s,m,cfg=config(api);sid=s["study_id"];path=f"/studies/{sid}/configurations/preview"
    assert '"value": 0' in json.dumps(cfg)
    for text in ("NaN","Infinity","-Infinity","9007199254740992"):
        raw=json.dumps(cfg).replace('"value": 0','"value": '+text)
        assert c.post("/api/1"+path,content=raw,headers={"Content-Type":"application/json"}).status_code==400
    trial=copy.deepcopy(cfg);trial["inputs"][0]["provenance"]["statement"]=""
    post(c,path,trial,422)
    note=post(c,f"/studies/{sid}/evidence",dict(command_id=uid(),scope=None,kind="note",content="Actual",source_refs=[]),201)["data"]
    # Evidence content is resolved by the server from the cited version; a client-supplied
    # snapshot, forged or not, is never accepted.
    trial=copy.deepcopy(cfg);trial["evidence_snapshots"]=[{k:note[k] for k in ("evidence_version_id","kind","content","source_refs")}]
    trial["evidence_snapshots"][0]["content"]="Forged content"
    post(c,path,trial,400)
