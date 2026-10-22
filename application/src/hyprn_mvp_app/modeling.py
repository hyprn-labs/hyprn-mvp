"""Typed Modeling Backend Contract client and durable command coordination."""
from __future__ import annotations
import base64
import hashlib
import hmac
import json
import time
import re
from urllib.parse import urlencode
from uuid import UUID
import httpx
from .contracts import DomainError, canonical, digest, uid, validate
from .units import UNIT_CATALOG_BYTES, UNIT_CATALOG_DIGEST, UNIT_ENGINE_SOURCE_SHA256, active_ports
from .store import ForeignEvidence
# Temporary forwarding aliases for test imports only;
# production code imports these from their owner (application/tests/test_module_boundaries.py).

class ModelingClient:
    def __init__(self,base_url,key,*,transport=None):
        self.base_url=base_url.rstrip("/")
        self.key=key
        self.transport=transport
        if len(key)<32:raise ValueError("A separate 256-bit service credential is required")

    def call(self,actor,study,method,path,body=None,*,request_schema=None,response_schema=None,resources=None):
        if request_schema:validate(request_schema,body)
        raw=canonical(body) if body is not None else b""
        full="/modeling/1"+path
        # Read-only computation receives read-only permissions, even though HTTP uses POST.
        writing=method=="POST" and not path.endswith(("/preview","/validate","/configuration-compatibility"))
        claims=dict(actor_id=actor,study_id=study,resource_ids=resources or ["*"],
                    permissions=["read","write"] if writing else ["read"],expires_at=int(time.time())+60,
                    request_id=uid(),method=method,path=full,body_sha256=hashlib.sha256(raw).hexdigest())
        encode=lambda b:base64.urlsafe_b64encode(b).decode().rstrip("=")
        token=encode(b'{"alg":"HS256","typ":"JWT"}')+"."+encode(canonical(claims))
        token+="."+encode(hmac.new(self.key,token.encode(),hashlib.sha256).digest())
        headers={"Authorization":"Bearer "+token,"Content-Type":"application/json"}
        response_limit=UNIT_CATALOG_BYTES if path=="/unit-catalog" else 32*1024*1024
        try:
            if self.transport:
                status,result=self.transport(method,full,raw,headers)
                if len(canonical(result))>response_limit:raise ValueError("Response bound")
            else:
                with httpx.Client(timeout=20,follow_redirects=False,trust_env=False) as client:
                    with client.stream(method,self.base_url+path,content=raw if body is not None else None,headers=headers) as response:
                        data=bytearray()
                        for part in response.iter_bytes():
                            data.extend(part)
                            if len(data)>response_limit:raise ValueError("Response bound")
                        status,result=response.status_code,json.loads(data)
        except (OSError,ValueError,httpx.HTTPError):
            raise DomainError("backend_unavailable",503,outcome="unknown") from None
        if status>=400:
            validate("Error",result,remote=True)
            error=result["error"]
            # Messages remain controlled locally; never forward backend paths/details.
            raise DomainError(error["code"],status,current_revision=error["current_revision"],fields=error["fields"],outcome=error["outcome"])
        if response_schema:validate(response_schema,result,remote=True)
        return status,{k:v for k,v in result.items() if k not in {"request_id","schema_version"}}


def checked_model(value,sid,mid,*,revision=None):
    """Model-record integrity, pure: a backend model draft (``ModelDraftRead4``) of study ``sid``
    or an immutable revision (``ModelRevisionRead4``, optionally exactly ``revision``) of model
    ``mid``. Checks the read contract, identity and digest, unique instance and assumption ids,
    assumption owners and citations, source-file hashes and schema-4 capabilities/active ports.
    Returns ``value``; any failure is ``backend_unavailable`` 503 (the backend gave an invalid
    model). Owned by the modeling domain; needs no Coordinator, Store or transport, so
    configuration replays and write-time rechecks call it on retained snapshots directly.
    """
    immutable="model_revision_id" in value
    validate("ModelRevisionRead4" if immutable else "ModelDraftRead4",value,remote=True)
    invalid=value["model_id"]!=mid or (not immutable and value["study_id"]!=sid)
    if immutable:
        invalid |= value["digest"]!=digest({k:v for k,v in value.items() if k!="digest"})
        invalid |= revision is not None and value["model_revision_id"]!=revision
    instances=[i["instance_id"] for i in value["instances"]]
    assumptions=value.get("assumptions",[])
    ids=[a["assumption_id"] for a in assumptions]
    invalid |= len(ids)!=len(set(ids)) or len(instances)!=len(set(instances))
    for assumption in assumptions:
        owner=assumption["owner"]
        invalid |= owner["kind"]=="instance" and (owner["instance_id"] not in instances or owner["instance_id"]==value["root_instance_id"])
        pairs=[(l["evidence_version_id"],l["relation"]) for l in assumption["evidence_links"]]
        invalid |= len(pairs)!=len(set(pairs))
    invalid |= len({l["evidence_version_id"] for a in assumptions for l in a["evidence_links"]})>1000
    for source in value["source_files"]:
        try:raw=base64.b64decode(source["bytes"],validate=True)
        except ValueError:raise DomainError("backend_unavailable",503,outcome="unknown") from None
        invalid |= hashlib.sha256(raw).hexdigest()!=source["sha256"]
    if value['schema_version']=='4':
        invalid |= 'quantity_definitions/1' not in value['required_capabilities']
        invalid |= any(isinstance(p['units'],dict) for p in value['ports']) and 'unit_declarations/1' not in value['required_capabilities']
        try:active_ports(value)
        except DomainError:invalid=True
    if invalid:raise DomainError("backend_unavailable",503,outcome="unknown")
    return value


class Coordinator:
    def __init__(self,store,model):
        self.store,self.model=store,model

    def assumptions_supported(self,actor,sid,*,strict=False):
        with self.store.connection() as db:self.store.authorize(db,actor,sid)
        try:
            status,result=self.model.call(actor,sid,"GET","/capabilities",
                response_schema="CapabilitiesResponseRead3",resources=[sid])
            caps=validate("CapabilitiesRead3",result["data"],remote=True)
            if status!=200:raise DomainError("backend_unavailable",503,outcome="unknown")
            supported=("1.2" in caps["contract_versions"] and "2" in caps["schema_versions"]
                and any(c["id"]=="model_assumptions" and c["version"]=="1" and c["supported"] for c in caps["capabilities"]))
        except DomainError:
            if strict:raise
            supported=False
        finally:
            # Revocation must suppress backend details even when the call failed.
            with self.store.connection() as db:self.store.authorize(db,actor,sid)
        return supported

    def _require_assumptions(self,actor,sid):
        if not self.assumptions_supported(actor,sid,strict=True):raise DomainError("unsupported_capability",422)

    @staticmethod
    def supports_units(caps):
        return bool(caps and "1.3" in caps["contract_versions"] and "3" in caps["schema_versions"]
            and any(c["id"]=="unit_declarations" and c["version"]=="1" and c["supported"] for c in caps["capabilities"]))

    def _require_units(self,actor,sid):
        with self.store.connection() as db:self.store.authorize(db,actor,sid)
        try:
            status,result=self.model.call(actor,sid,"GET","/capabilities",
                response_schema="CapabilitiesResponseRead3",resources=[sid])
            caps=validate("CapabilitiesRead3",result["data"],remote=True)
            if status!=200:raise DomainError("backend_unavailable",503,outcome="unknown")
            if not self.supports_units(caps):raise DomainError("unsupported_capability",422)
        finally:
            with self.store.connection() as db:self.store.authorize(db,actor,sid)

    @staticmethod
    def supports_quantities(caps):
        return bool(caps and "4" in caps["schema_versions"] and any(
            c["id"]=="quantity_definitions" and c["version"]=="1" and c["supported"] for c in caps["capabilities"]))

    def _require_quantities(self,actor,sid):
        with self.store.connection() as db:self.store.authorize(db,actor,sid)
        try:
            status,result=self.model.call(actor,sid,"GET","/capabilities",response_schema="CapabilitiesResponseRead3",resources=[sid])
            if status!=200:raise DomainError("backend_unavailable",503,outcome="unknown")
            if not self.supports_quantities(result["data"]):raise DomainError("unsupported_capability",422)
        finally:
            with self.store.connection() as db:self.store.authorize(db,actor,sid)

    def unit_catalog(self,actor,sid):
        self._require_units(actor,sid)
        try:
            status,result=self.model.call(actor,sid,"GET","/unit-catalog",
                response_schema="UnitCatalogResponse1",resources=[sid])
            catalog=validate("UnitCatalog1",result["data"],remote=True)
            if (status!=200 or catalog["catalog_digest"]!=UNIT_CATALOG_DIGEST
                or catalog["engine_source_sha256"]!=UNIT_ENGINE_SOURCE_SHA256):
                raise DomainError("backend_unavailable",503,outcome="unknown")
            return catalog
        finally:
            # Suppress successful content and backend failures after revocation.
            with self.store.connection() as db:self.store.authorize(db,actor,sid)

    def _cited(self,db,actor,sid,version):
        """Store's exact evidence record for a model citation (``Store.evidence_record``).
        A stored identity mismatch is an unavailable backend for model authoring (503)."""
        try:return self.store.evidence_record(db,actor,sid,version)
        except DomainError as error:
            if error.code=="reference_conflict":raise DomainError("backend_unavailable",503,outcome="unknown") from None
            raise

    def _evidence_check(self,db,actor,sid,versions,*,allow_unknown=False):
        """Citations must name this study's evidence. ``allow_unknown`` admits versions no
        study holds (opaque imported citations); another study's version is always 404."""
        self.store.authorize(db,actor,sid)
        result={}
        for version in sorted(set(versions)):
            record=self._cited(db,actor,sid,version)
            if record is None and allow_unknown:continue
            if record is None:raise DomainError("resource_not_found",404)
            result[version]=record
        return result

    def assumption_evidence(self,actor,sid,mid,*,model_revision_id=None,draft_revision=None):
        self.authorize_model(actor,sid,mid)
        if (model_revision_id is None)==(draft_revision is None):raise DomainError("invalid_request",400)
        if model_revision_id is not None:
            try:
                if str(UUID(model_revision_id))!=model_revision_id:raise ValueError()
            except (ValueError,TypeError,AttributeError):raise DomainError("invalid_request",400) from None
        elif not isinstance(draft_revision,str) or not draft_revision.strip() or len(draft_revision)>4096:
            raise DomainError("invalid_request",400)
        self._require_assumptions(actor,sid)
        suffix="/revisions/"+model_revision_id if model_revision_id else ""
        selected=self.read(actor,sid,mid,suffix,response_schema="ModelRevisionResponse4" if model_revision_id else "ModelDraftResponse4")["data"]
        if draft_revision is not None:self.store.cas(selected["draft_revision"],draft_revision)
        links=[];evidence={}
        with self.store.connection() as db:
            self._authorize_request(db,actor,sid,mid)
            for assumption in selected.get("assumptions",[]):
                for version in sorted({l["evidence_version_id"] for l in assumption["evidence_links"]}):
                    # Another study's version is unavailable here and never disclosed.
                    try:record=self._cited(db,actor,sid,version)
                    except ForeignEvidence:record=None
                    if record is not None:evidence[version]=record
                    links.append(dict(assumption_id=assumption["assumption_id"],evidence_version_id=version,status="resolved" if record is not None else "unavailable"))
        return validate("AssumptionEvidenceResolution1",dict(schema_version="1",model_digest=selected.get("digest"),
            draft_revision=draft_revision,model_revision_id=model_revision_id,links=links,evidence=[evidence[k] for k in sorted(evidence)]),remote=True)

    def _authorize_request(self,db,actor,sid,mid,*,write=False):
        # A study-level command (model creation/import) has no model yet.
        if mid:self.store.model_association(db,actor,sid,mid,write=write)
        else:self.store.authorize(db,actor,sid,write=write)

    def _request_evidence(self,actor,sid,mid,operation,body):
        """Read native state without a local write lock; never persist a draft copy."""
        versions=set();allow_unknown=operation=="commits"
        if body.get("schema_version")=="4" or (operation=="import" and body["package"]["schema_version"]=="4"):
            self._require_quantities(actor,sid)
        if body.get("schema_version")=="3" or (operation=="import" and body["package"]["schema_version"]=="3"):
            self._require_units(actor,sid)
        if body.get("schema_version")=="2" or (operation=="import" and body["package"]["schema_version"]=="2"):
            self._require_assumptions(actor,sid)
        if operation in {"preview","edits","commits"}:
            selected=self.read(actor,sid,mid)["data"]
            self.store.cas(selected["draft_revision"],body["expected_revision"])
            if selected["schema_version"]=="3" and body.get("schema_version")!="3":self._require_units(actor,sid)
            if selected["schema_version"]=="2" and body.get("schema_version")!="2":self._require_assumptions(actor,sid)
            if selected["schema_version"]=="4" and body.get("schema_version")!="4":self._require_quantities(actor,sid)
            old={a["assumption_id"]:a for a in selected.get("assumptions",[])}
            if operation=="commits":
                versions={l["evidence_version_id"] for a in old.values() for l in a["evidence_links"]}
            else:
                for edit in body["edits"]:
                    if edit["kind"] not in {"add_assumption","update_assumption"}:continue
                    prior=old.get(edit.get("assumption_id"),{}).get("evidence_links",[])
                    # A changed relationship is a new citation, even to the same version.
                    versions.update(l["evidence_version_id"] for l in edit["evidence_links"] if l not in prior)
        with self.store.connection() as db:
            self._authorize_request(db,actor,sid,mid)
            self._evidence_check(db,actor,sid,versions,allow_unknown=allow_unknown)
        return versions,allow_unknown

    def _checked_portable_record(self,package,sid,mid,revision):
        # Portable model record (legacy wire name ModelPackage; contracts/README.md legacy table).
        validate("ModelPackage",package,remote=True)
        if (package["model_id"]!=mid or package["model_revision_id"]!=revision
            or package["digest"]!=digest({k:v for k,v in package.items() if k!="digest"})):
            raise DomainError("backend_unavailable",503,outcome="unknown")
        ids=[v["model_revision_id"] for v in package["revisions"]]
        if len(ids)!=len(set(ids)) or revision not in ids:raise DomainError("backend_unavailable",503,outcome="unknown")
        for value in package["revisions"]:
            checked_model(value,sid,mid)
            if value["model_revision_id"]==revision and value["schema_version"]!=package["schema_version"]:
                raise DomainError("backend_unavailable",503,outcome="unknown")

    def authorize_model(self,actor,sid,mid,write=False):
        with self.store.connection() as db:self.store.model_association(db,actor,sid,mid,write=write)

    def models(self,actor,sid,*,cursor=None,limit=100):
        with self.store.connection() as db:
            self.store.authorize(db,actor,sid)
            records = [dict(r) for r in db.execute("SELECT model_id,command_id FROM model_associations WHERE study_id=? ORDER BY model_id",(sid,))]
        if not 1 <= limit <= 100:
            raise DomainError('invalid_request', 400)
        if cursor:
            position = next((i for i, item in enumerate(records) if item['model_id'] == cursor), None)
            if position is None:
                raise DomainError('resource_not_found', 404)
            records = records[position + 1:]
        more = len(records) > limit
        records = records[:limit]
        for record in records:
            try:
                record['name'] = self.read(actor, sid, record['model_id'])['data']['name']
            except DomainError as error:
                if error.code != 'backend_unavailable':
                    raise
                record['name'] = None
        return records, records[-1]["model_id"] if more else None

    def execute(self,actor,sid,operation,target,body,remote_body,path,request_schema,response_schema,*,association=False):
        validate(request_schema,remote_body)
        with self.store.connection() as db:self._authorize_request(db,actor,sid,target,write=True)
        payload=dict(operation=operation,target=target,body={k:v for k,v in body.items() if k!="command_id"})
        old=self.store.replay(actor,sid,"model",body["command_id"],payload)
        if old is None:
            versions,allow_unknown=self._request_evidence(actor,sid,target,operation,remote_body)
            # Persist before crossing the remote boundary. No lock spans HTTP.
            def reserve(db):
                self._authorize_request(db,actor,sid,target,write=True)
                self._evidence_check(db,actor,sid,versions,allow_unknown=allow_unknown)
                if association:
                    current=self.store.study_row(db,sid)
                    self.store.cas(current["revision"],body["expected_revision"])
                    db.execute("UPDATE studies SET revision=? WHERE study_id=?",(uid(),sid))
                return {"state":"pending_remote"}
            self.store.command(actor,sid,"model",body["command_id"],payload,reserve,receipt_state="pending_remote",
                request=dict(operation=operation,target=target,body=remote_body,path=path,
                    request_schema=request_schema,response_schema=response_schema,association=association,
                    citation_versions=sorted(versions),allow_unknown=allow_unknown))
        return self.reconcile(actor,sid,body["command_id"],retry=True)

    def reconcile(self,actor,sid,command,*,retry=False,receipt_view=False):
        row=self.store.receipt(actor,sid,"model",command)
        request=row["request"]
        with self.store.connection() as db:
            self._authorize_request(db,actor,sid,request["target"],write=retry)
            self._evidence_check(db,actor,sid,request.get("citation_versions",[]),allow_unknown=request.get("allow_unknown",False))
        if row["state"]=="rejected":
            if receipt_view:return row["error"]["status"],{"error":row["error"]}
            raise DomainError(**row["error"])
        if row["state"]=="committed":
            self._check_command_result(actor,sid,request,row["result"]["response"])
            self.authorize_model(actor,sid,row["result"]["response"]["data"]["model_id"],write=retry)
            return row["result"]["status"],row["result"]["response"]
        try:
            _,lookup=self.model.call(actor,sid,"GET",f"/commands/{command}?study_id={sid}&category=model",response_schema="ReceiptResponse4")
            with self.store.connection() as db:self._authorize_request(db,actor,sid,request["target"],write=retry)
            receipt=lookup["data"]
            if receipt["command_id"]!=command:raise DomainError("backend_unavailable",503,outcome="unknown")
            if receipt["state"]=="absent":
                if not retry:return 202,{"data":{"command_id":command,"state":"pending_remote","receipt_url":f"/api/1/studies/{sid}/commands/{command}?category=model"}}
                self._request_evidence(actor,sid,request["target"],request["operation"],request["body"])
                with self.store.connection() as db:self._authorize_request(db,actor,sid,request["target"],write=True)
                status,response=self.model.call(actor,sid,"POST",request["path"],request["body"],
                    request_schema=request["request_schema"],response_schema=request["response_schema"],
                    resources=[request["target"]] if request["target"] else None)
            else:
                expected=digest(dict(major="1",operation=request["operation"],target=request["target"],study_id=sid,
                    payload={k:v for k,v in request["body"].items() if k!="command_id"}))
                if receipt["payload_digest"]!=expected:raise DomainError("backend_unavailable",503,outcome="unknown")
                status,response=receipt["status"],receipt["response"]
                if receipt["state"]=="rejected":
                    e=response["error"]
                    raise DomainError(e["code"],status,current_revision=e["current_revision"],fields=e["fields"])
                validate(request["response_schema"],dict(schema_version="1",request_id=uid(),**response),remote=True)
            self._check_command_result(actor,sid,request,response)
        except DomainError as error:
            with self.store.connection() as db:self._authorize_request(db,actor,sid,request["target"],write=retry)
            if error.status>=500:
                return 202,{"data":{"command_id":command,"state":"pending_remote","receipt_url":f"/api/1/studies/{sid}/commands/{command}?category=model"}}
            with self.store.connection(write=True) as db:
                self._authorize_request(db,actor,sid,request["target"],write=retry)
                db.execute("UPDATE receipts SET state='rejected',result=NULL,error=? WHERE scope=? AND category='model' AND command_id=?",
                           (json.dumps(error.data()),sid,command))
            if receipt_view:return error.status,{"error":error.data()}
            raise
        with self.store.connection(write=True) as db:
            self._authorize_request(db,actor,sid,request["target"],write=retry)
            self._evidence_check(db,actor,sid,request.get("citation_versions",[]),allow_unknown=request.get("allow_unknown",False))
            if request["operation"]=="commits":
                self._evidence_check(db,actor,sid,self._model_versions(response["data"]),allow_unknown=True)
            current=self.store.command_receipt(db,sid,"model",command)
            if current["state"]=="committed":return current["result"]["status"],current["result"]["response"]
            if request["association"]:
                db.execute("INSERT INTO model_associations VALUES(?,?,?) ON CONFLICT DO NOTHING",(sid,response["data"]["model_id"],command))
            # Only the typed immutable command result is retained, never an editable model master.
            db.execute("UPDATE receipts SET state='committed',result=? WHERE scope=? AND category='model' AND command_id=?",
                       (json.dumps(dict(status=status,response=response)),sid,command))
            # The receipt's actor wrote the model, whoever reconciles it: a commit records a
            # model version, every other model command the draft revision it produced.
            data=response["data"]
            if request["operation"]=="commits":
                written=("model_version",data["model_id"],data["model_revision_id"])
            else:
                written=("model_draft",data["model_id"],data["draft_revision"])
            self.store.attribute(db,current["actor_id"],sid,"model",command,[written])
        return status,response

    @staticmethod
    def _model_versions(model):
        return {l["evidence_version_id"] for a in model.get("assumptions",[]) for l in a["evidence_links"]}

    def _check_command_result(self,actor,sid,request,response):
        validate(request["response_schema"],dict(schema_version="1",request_id=uid(),**response),remote=True)
        selected=response["data"]
        checked_model(selected,sid,request["target"] or selected["model_id"])
        expected_version=request["body"].get("schema_version")
        if request["operation"]=="import":expected_version=request["body"]["package"]["schema_version"]
        if expected_version in {"3","4"} and selected["schema_version"]!=expected_version:
            raise DomainError("backend_unavailable",503,outcome="unknown")
        if request["operation"]=="import" and selected["model_id"]!=request["body"]["package"]["model_id"]:
            raise DomainError("backend_unavailable",503,outcome="unknown")
        if request["operation"]=="commits" and selected["originating_draft_revision"]!=request["body"]["expected_revision"]:
            raise DomainError("backend_unavailable",503,outcome="unknown")
        with self.store.connection() as db:
            self._authorize_request(db,actor,sid,request["target"])
            if request["operation"]=="commits":self._evidence_check(db,actor,sid,self._model_versions(selected),allow_unknown=True)

    def revisions(self,actor,sid,mid,query):
        # Authorize before interpreting a cursor, and delegate storage ordering to its owner.
        self.authorize_model(actor,sid,mid)
        pairs=list(query)
        if any(key not in {"cursor","limit"} for key,_ in pairs) or len({key for key,_ in pairs})!=len(pairs):
            raise DomainError("invalid_request",400)
        values=dict(pairs)
        limit=values.get("limit","50")
        if not re.fullmatch(r"(?:[1-9]|[1-9][0-9]|100)",limit):raise DomainError("invalid_request",400)
        cursor=values.get("cursor")
        if cursor is not None:
            try:
                if str(UUID(cursor))!=cursor:raise ValueError()
            except ValueError:raise DomainError("invalid_request",400) from None
        params={"limit":limit}
        if cursor is not None:params["cursor"]=cursor
        status,result=self.model.call(actor,sid,"GET","/models/"+mid+"/revisions?"+urlencode(params),
            response_schema="RevisionListResponse",resources=[mid])
        page=result["data"];ids=[row["model_revision_id"] for row in page["items"]]
        # A typed but inconsistent page must not create duplicate/infinite navigation.
        if (status!=200 or len(ids)>int(limit) or len(set(ids))!=len(ids) or cursor in ids
            or (page["next_cursor"] is not None and (len(ids)!=int(limit) or page["next_cursor"]!=ids[-1]))):
            raise DomainError("backend_unavailable",503,outcome="unknown")
        self.authorize_model(actor,sid,mid)
        return {"data":page["items"],"next_cursor":page["next_cursor"]}

    def read(self,actor,sid,mid,suffix="",*,method="GET",body=None,request_schema=None,response_schema="ModelDraftResponse4"):
        self.authorize_model(actor,sid,mid)
        versions=set();allow_unknown=False
        if method=="POST" and suffix=="/preview":
            validate(request_schema,body)
            versions,allow_unknown=self._request_evidence(actor,sid,mid,"preview",body)
        try:
            result=self.model.call(actor,sid,method,"/models/"+mid+suffix,body,
                request_schema=request_schema,response_schema=response_schema,resources=[mid])[1]
            if suffix=="/preview" and body.get("schema_version") in {"3","4"} and result["data"]["schema_version"]!=body["schema_version"]:
                raise DomainError("backend_unavailable",503,outcome="unknown")
        finally:
            with self.store.connection() as db:self._authorize_request(db,actor,sid,mid)
        if response_schema in {"ModelDraftResponse","ModelDraftEditResponse","ModelRevisionResponse","ModelDraftResponse4","ModelDraftEditResponse4","ModelRevisionResponse4"}:
            checked_model(result["data"],sid,mid,revision=suffix.removeprefix("/revisions/") if suffix.startswith("/revisions/") else None)
        if response_schema=="ModelPackageResponse" and suffix.startswith("/export?revision="):
            self._checked_portable_record(result["data"],sid,mid,suffix.removeprefix("/export?revision="))
        # Preview returns a temporary projected draft, including its revision.
        # The original token is checked above and by the backend's atomic
        # preview operation; projected identities are never apply/CAS tokens.
        with self.store.connection() as db:
            self._authorize_request(db,actor,sid,mid)
            self._evidence_check(db,actor,sid,versions,allow_unknown=allow_unknown)
        return result
