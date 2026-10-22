import sqlite3
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import pytest
from hyprn_mvp_app.store import Store, DomainError

def uid(): return str(uuid4())

@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "application.sqlite")

def create(store, actor="owner", command=None):
    return store.create_study(actor, command or uid(), "Study")

def test_atomic_study_membership_receipt_and_restart(store):
    command=uid()
    study=create(store, command=command)
    assert Store(store.path).study("owner", study["study_id"]) == study
    assert store.receipt("owner", None, "study_create", command)["result"] == study
    assert store.create_study("owner", command, "Study") == study
    with pytest.raises(DomainError, match="command_payload_conflict"):
        store.create_study("owner", command, "Changed")
    with sqlite3.connect(store.path) as db:
        names={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"studies","memberships","evidence","configurations","receipts","run_associations","outbox"} <= names
        assert not names & {"graphs","ports","definitions","source_files","model_drafts"}

def test_stale_updates_and_rejected_receipts_are_durable(store):
    study=create(store); sid=study["study_id"]; command=uid()
    updated=store.set_membership("owner",sid,uid(),study["revision"],"guest","reader")
    with pytest.raises(DomainError,match="stale_revision"):
        store.set_membership("owner",sid,command,study["revision"],"guest","writer")
    assert store.study("owner",sid)==updated
    assert store.receipt("owner",sid,"membership",command)["state"]=="rejected"
    with pytest.raises(DomainError,match="stale_revision"):
        store.set_membership("owner",sid,command,study["revision"],"guest","writer")

def test_concurrent_cas_and_same_command(store):
    study=create(store); sid=study["study_id"]
    def update(i):
        try:return store.set_membership("owner",sid,uid(),study["revision"],str(i),"reader")
        except DomainError as e:return e.code
    with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(update,range(2)))
    assert sum(isinstance(r,dict) for r in results)==1
    assert results.count("stale_revision")==1
    command=uid()
    with ThreadPoolExecutor(max_workers=2) as pool:
        repeated=list(pool.map(lambda _:create(store,command=command),range(2)))
    assert repeated[0]==repeated[1]

def test_evidence_versions_immutable_and_scoped(store):
    study=create(store); other=create(store); sid=study["study_id"]
    note={"scope":None,"kind":"note","content":"Measured assumption","source_refs":[]}
    evidence=store.add_evidence("owner",sid,uid(),note)
    assert store.evidence_version("owner",sid,evidence["evidence_version_id"])==evidence
    with pytest.raises(DomainError,match="resource_not_found"):
        store.evidence_version("owner",other["study_id"],evidence["evidence_version_id"])
    with sqlite3.connect(store.path) as db:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE evidence SET payload='{}'")
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("DELETE FROM evidence")

def test_revoke_blocks_reads_mutations_and_replay(store):
    study=create(store); sid=study["study_id"]; command=uid()
    changed=store.set_membership("owner",sid,command,study["revision"],"guest","reader")
    store.set_membership("owner",sid,uid(),changed["revision"],"guest","reader")
    assert store.study("guest",sid)["name"]=="Study"
    revision=store.study("owner",sid)["revision"]
    store.set_membership("owner",sid,uid(),revision,"guest",None)
    for call in [
        lambda:store.study("guest",sid),
        lambda:store.receipt("guest",sid,"membership",command),
        lambda:store.set_membership("guest",sid,command,study["revision"],"guest","reader"),
    ]:
        with pytest.raises(DomainError,match="resource_not_found"):call()
    assert store.list_studies("guest")==[]
