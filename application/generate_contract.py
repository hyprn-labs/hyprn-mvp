"""Export actual public routes, closed request/response schemas and error statuses."""
import copy
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent/"src"))
from hyprn_mvp_app.api import create_app
from hyprn_mvp_app.modeling import SCHEMA

ROOT=Path(__file__).resolve().parents[1]
spec=create_app(None,None,None).openapi()
spec["servers"]=[{"url":"/api/1"}]
spec["paths"]={p.removeprefix("/api/1"):v for p,v in spec["paths"].items()}
schemas=spec.setdefault("components",{}).setdefault("schemas",{})
def rewrite(value):
    if isinstance(value,dict):return {k:(v.replace("#/$defs/","#/components/schemas/") if k=="$ref" else rewrite(v)) for k,v in value.items()}
    if isinstance(value,list):return [rewrite(v) for v in value]
    return value
schemas.update(rewrite(SCHEMA["$defs"]))
schemas["Error"]["properties"]["error"]["properties"]["code"]["enum"] += ["rate_limited","internal_error","history_not_recorded","corrupt_retained_record","unsupported_record_version","missing_results","missing_artifacts","missing_or_invalid_artifact"]
def ref(name):return {"$ref":"#/components/schemas/"+name}
def obj(properties,required=None):return {"type":"object","properties":properties,"required":list(properties) if required is None else required,"additionalProperties":False}
string={"type":"string"}
uuid={"type":"string","format":"uuid"}
array=lambda item:{"type":"array","items":item}
nullable=lambda value:{"anyOf":[value,{"type":"null"}]}
schemas["Study"]=obj({k:string for k in ("study_id","revision","name","description","boundary")})
# Study archive state is additive and optional: current study reads always include it; study
# creation/update outcomes and historical receipts keep their recorded shape without it.
schemas["Study"]["properties"]["archived"]={"type":"boolean","description":"Study-wide archive state on current study reads and archive/restore outcomes. Presentation state only: archived studies keep every read and command; nothing is deleted. Absent from study creation/update outcomes and receipts recorded before archive support."}
schemas["StudyArchiveCommand"]=obj(dict(command_id=uuid))
# Preserve the shared closed old/new record union. Normalize the paired snapshot
# fields into an equivalent union so the selected scoped variant requires both
# fields. Runtime JSON Schema validation remains authoritative for closed extras.
schemas["Evidence"]=ref("EvidenceCreate1")
schemas["EvidenceV2"]=ref("EvidenceCreate2")
schemas["PublicEvidenceCreate"]={"oneOf":[ref("EvidenceCreate1"),ref("EvidenceCreate2"),ref("EvidenceCreate3")]}
legacy_snapshot=copy.deepcopy(schemas["EvidenceSnapshotLegacy"])
legacy_snapshot.pop("dependentRequired",None)
for name in ("evidence_schema_version","resource_scope"):legacy_snapshot["properties"].pop(name)
scoped_snapshot=copy.deepcopy(schemas["EvidenceSnapshotLegacy"])
scoped_snapshot.pop("dependentRequired",None)
scoped_snapshot["required"] += ["evidence_schema_version","resource_scope"]
schemas["EvidenceSnapshotLegacy"]={"oneOf":[legacy_snapshot,scoped_snapshot]}
# Snapshot/SnapshotRead keep the shared Legacy | Snapshot3 union. Only the
# legacy paired fields need normalization for the data-only TS generator.
schemas["ExecutionReadiness"]=obj(dict(readiness_schema_version={"enum":["1"]},
    capability={"enum":["flat_explicit_scalar"]},status={"enum":["ready","unavailable","unknown"]},
    reasons={"type":"array","maxItems":2,"uniqueItems":True,"items":{"enum":["executor_unavailable","attestation_invalid","modeling_unavailable","observation_stale","capability_unsupported"]}},
    observed_at=nullable({"type":"string","format":"date-time"}),expires_at=nullable({"type":"string","format":"date-time"})))
# Public configuration responses use the exact old/new FrozenConfigurationRead7 union.
schemas["PublicNewModel"]={"oneOf":[ref("NewModel"),ref("NewModel3")]}
schemas["Association"]=obj(dict(model_id=uuid,command_id=uuid))
schemas["Session"]=obj(dict(actor_id=uuid,csrf_token=string,expires_at={"type":"number"}))
schemas["EndedSession"]=obj(dict(ended={"const":True}))
schemas["PendingModel"]=obj(dict(command_id=uuid,state={"const":"pending_remote"},receipt_url=string))
schemas["ApplicationCapabilities"]=obj(dict(contract_versions=array(string),engineering=array(string),modeling=array({"enum":["model_revision_listing","model_rename","model_assumptions/1","unit_declarations/1","quantity_definitions/1"]}),execution=string,unavailable=array(string),
    limits=obj({**{k:{"type":"integer"} for k in ("request_bytes","source_bytes","edits","elements","depth","result_source_outputs","result_source_runs","result_source_bindings","result_source_dependencies")},'computational_record':ref('ExportLimits')})))
# Shared StoredError keeps its diagnostic/status/text bounds.
model_result={"anyOf":[obj(dict(data=ref("ModelDraftRead4"))),obj(dict(data=ref("ModelDraftRead4"),created_ids=ref("CreatedIds"),diagnostics=array(ref("Diagnostic")))),obj(dict(data=ref("ModelRevisionRead4")))]}
run_states=["accepted_run","prepared","preparation_failed","dispatching","recorded","uncertain"]
sha={"type":"string","pattern":"^[0-9a-f]{64}$"}
boolean={"type":"boolean"}
count={"type":"integer","minimum":0}
schemas['RetainedOutput']=obj(dict(target=obj(dict(instance_id=uuid,port_id=uuid)),value=nullable({'type':'number'}),units=string,
    availability={'enum':['available','unavailable']},reason=nullable(string),producer_completed=boolean,assigned=boolean))
schemas['RetainedResults']=obj(dict(schema_version={'const':'1'},run_id=uuid,bundle_digest=sha,
    execution=obj(dict(state={'enum':['finished','failed']},exit_code={'type':'integer'},message=string)),
    convergence=obj(dict(state={'const':'not_applicable'},diagnostics_ref={'type':'null'})),
    optimization=obj(dict(termination={'const':'not_applicable'},feasibility={'const':'not_applicable'})),
    completeness=obj({k:count for k in ('expected','available','failed','unavailable')}),
    outputs=array(ref('RetainedOutput')),criteria=array(obj(dict(criterion_id=uuid,outcome={'enum':['met','violated','unresolved']},reason=string))),
    applicability=obj(dict(state={'const':'unassessed'},evidence_refs={'type':'array','maxItems':0})),artifacts={'type':'array','maxItems':0}))
schemas['HistoryArtifact']=obj(dict(artifact_id=uuid,name=string,role=string,size=count,sha256=sha,media_type={'const':'application/octet-stream'}))
# RunHistory1/2 and the read union come from the shared schema unchanged.
schemas['RunHistoryItem']=obj(dict(run_id=uuid,configuration_revision_id=uuid,command_id=uuid,state={'enum':run_states}))
# Optional upcoming projection; no service implements it yet.
schemas['RunHistoryItem']['properties']['case_context']=ref('RunCaseContext1')
schemas['RunHistoryItem']['properties']['configuration_name']={'anyOf':[{'type':'string','maxLength':4096},{'type':'null'}],'description':'Presentation name from the exact immutable configuration revision in this study; never the current family head. Optional for older servers. Null means unavailable; does not attest scientific validity.'}
schemas["PublicRun"]=obj(dict(run_id=uuid,command_id=uuid,state={"enum":run_states},receipt_url=string,
    process_state={"enum":["created","waiting","running","finished","excepted","killed","unknown"]},exit_status=nullable({"type":"integer"})),
    ["run_id","command_id","state","receipt_url"])
# Public read metadata is additive; stored history/native schema versions stay exact.
schemas['RetainedReadIntegrity1']=obj(dict(schema_version={'const':'1'},
    results_digest=nullable({**sha,'minLength':64,'maxLength':64})))
schemas['RetainedReadIntegrity1']['properties']['results_digest']['description']='Verified retained result digest from this read. Null means verification is unavailable.'
schemas['PublicRunDetail']={**schemas['PublicRun'],'properties':{**schemas['PublicRun']['properties'],'history':ref('RunHistoryRead6'),'runtime_comparison':ref('RuntimeComparison'),
    'retained_integrity':{**ref('RetainedReadIntegrity1'),'description':'Optional for older servers; absence means retained result verification is unavailable.'}}}
schemas["PublicReceipt"]=obj(dict(command_id=uuid,state={"enum":["committed","rejected","pending_remote",*run_states]},
    result={"anyOf":[ref("Study"),ref("EvidenceRecord"),ref("FrozenConfigurationRead7"),model_result,ref("PendingModel"),ref("PublicRun"),ref('RecordRequestRead'),ref('ApproachCommandResultRead2'),{"type":"null"}]},error=nullable(ref("StoredError"))))
schemas["ConfigurationCommit"]=ref("ConfigurationCommit1")
schemas.pop('ConfigurationCommitV2',None)
schemas['PublicConfigurationRequest']={'oneOf':[ref('ConfigurationCandidate1'),ref('ConfigurationRequest2'),ref('ConfigurationRequest3'),ref('ConfigurationRequest4')]}
schemas['PublicConfigurationCommit']={'oneOf':[ref('ConfigurationCommit1'),ref('ConfigurationCommit2'),ref('ConfigurationCommit3'),ref('ConfigurationCommit4')]}
schemas['PublicConfigurationPreview']={'oneOf':[ref('CompatibilityResult1'),ref('ConfigurationPreview2'),ref('ConfigurationPreview3'),ref('ConfigurationPreview4'),ref('ConfigurationPreview6')]}
# Preserve the earlier concrete public reader; implemented import/export now
# uses ModelPackage with the qualified native Model4 branch.
schemas["PublicModelPackageRead3"]={"oneOf":[ref("ModelPackage1"),ref("ModelPackage2"),ref("ModelPackage3")]}
schemas["ImportModel"]["properties"]["package"]=ref("ModelPackage")
schemas["SubmitRun"]["properties"]={"command_id":uuid,"configuration_revision_id":uuid}
def envelope(data):
    return obj(dict(schema_version={"const":"1"},request_id=uuid,data=data))
spec["components"]["securitySchemes"]={"session":{"type":"apiKey","in":"cookie","name":"hyprn_mvp_session"}}
spec["security"]=[{"session":[]}]
for path,methods in spec["paths"].items():
    for method,op in methods.items():
        # FastAPI dependency parameters describe actor through Depends, never identity headers.
        op["parameters"]=[p for p in op.get("parameters",[]) if p["name"]!="who"]
        status="200";schema=None
        if path=="/session":
            schema=ref("Session" if method=="post" else "EndedSession")
            if method=="post":op["security"]=[]
        elif path=="/capabilities":schema=ref("ApplicationCapabilities")
        elif path=="/studies":
            schema=array(ref("Study")) if method=="get" else ref("Study");status="200" if method=="get" else "201"
            for parameter in op["parameters"]:
                if parameter["name"]=="archived":
                    parameter["schema"]={"enum":["true","false"],"default":"false"}
                    parameter["description"]="false (default) lists studies that are not archived; true lists only archived studies. At most once."
        elif path=="/studies/{study_id}":schema=ref("Study")
        elif path in ("/studies/{study_id}/archive","/studies/{study_id}/restore"):
            schema=ref("Study")
            op["requestBody"]["content"]["application/json"]["schema"]=ref("StudyArchiveCommand")
            for parameter in op["parameters"]:
                if parameter["in"]=="path":parameter["schema"]=uuid
            op["description"]=("Study-wide archive state (owner or writer, as study edits; reader403; non-member404). Idempotent by command_id "
                "(receipt category study_archive); the same id for the other operation is command_payload_conflict. Target state: an "
                "already archived/restored study commits unchanged. Never changes the study record or revision and never deletes anything.")
        elif '/approach' in path:
            suffix=path.split('/approach',1)[1]
            result_name,request_name={
                ('','get'):('ApproachState2',None),
                ('/preview','post'):('ApproachPreviewRead3','ApproachPreviewRequestRead2'),
                ('/draft','post'):('ApproachDraftRead2','ApproachDraftWriteRead2'),
                ('/draft/restore','post'):('ApproachDraftRead2','ApproachRestore1'),
                ('/versions','get'):('ApproachVersionPage2',None),
                ('/versions','post'):('ApproachVersionSavedRead3','ApproachVersionSave1'),
                ('/versions/{version_id}','get'):('ApproachSavedRead3',None),
                ('/versions/{version_id}/usage','get'):('ApproachUsagePage1',None),
            }[(suffix,method)]
            schema=ref(result_name)
            if request_name:op['requestBody']['content']['application/json']['schema']=ref(request_name)
            if suffix=='/versions' and method=='post':status='201'
            for parameter in op['parameters']:
                if parameter['in']=='path':parameter['schema']=uuid
            if method=='get' and (suffix=='/versions' or suffix.endswith('/usage')):
                op['parameters'] += [dict(name='limit',**{'in':'query'},required=False,schema={'type':'integer','minimum':1,'maximum':100,'default':20}),
                    dict(name='cursor',**{'in':'query'},required=False,content={'application/json':{'schema':ref('ApproachUsageCursor1' if suffix.endswith('/usage') else 'ApproachCursor1')}})]
                if suffix.endswith('/usage'):op['parameters'].append(dict(name='case_id',**{'in':'query'},required=False,schema=uuid))
            op['description']='Study-authorized exact approach operation. No unknown/repeated query fields. Cursor is one JSON-encoded closed object (maximum256 characters). Saved reads and restore use retained closure without current modeling access; mutations preserve command identity and draft CAS.'
        elif path.endswith("/unit-catalog"):
            schema=ref("UnitCatalog1")
            op["description"]="Study-authorized finite physical guidance from the private model3 backend. Reauthorize after I/O; validate pinned source/catalog digests and the 16384-byte private response bound. No query fields, fallback catalog or browser-to-private access. Unsupported capability422; corrupt/outage503."
        elif path.endswith("/models"):
            schema=array(ref("Association")) if method=="get" else ref("ModelDraftRead4");status="200" if method=="get" else "201"
            if method=="post":op["requestBody"]["content"]["application/json"]["schema"]=ref("PublicNewModel")
        elif path.endswith("/model-imports"):schema=ref("ModelDraftRead4");status="201"
        elif "/models/" in path:
            if path.endswith("/assumption-evidence"):
                schema=ref("AssumptionEvidenceResolution1")
                op["description"]="Exactly one model_revision_id or draft_revision selector; no unknown or repeated query fields. Resolves only authorized exact same-study evidence. Returns unsupported_capability until coordinator resolution is implemented."
                for parameter in op["parameters"]:
                    if parameter["name"]=="model_revision_id":parameter["schema"]=uuid
                    elif parameter["name"]=="draft_revision":parameter["schema"]={"type":"string","minLength":1,"maxLength":4096,"pattern":r"\S"}
            elif path.endswith("/edits") or path.endswith("/preview"):
                op["requestBody"]["content"]["application/json"]["schema"]=ref("ApplyRead4" if path.endswith("/edits") else "PreviewRead4")
                schema=ref("ModelDraftRead4")
            elif path.endswith("/commits"):
                op["requestBody"]["content"]["application/json"]["schema"]=ref("Commit");schema=ref("ModelRevisionRead4")
            elif path.endswith("/validate"):
                op["requestBody"]["content"]["application/json"]["schema"]=ref("Validate");schema=ref("ValidationResult")
            elif path.endswith("/revisions"):
                schema={**array(ref("RevisionSummary")),"maxItems":100}
                for parameter in op["parameters"]:
                    if parameter["name"]=="limit":parameter["schema"]={"type":"integer","minimum":1,"maximum":100,"default":50}
                    elif parameter["name"]=="cursor":parameter["schema"]=uuid
                op["description"]="Immutable summaries in stored insertion order; cursor belongs to this authorized model. Unknown or repeated query fields are invalid."
            elif "/revisions/" in path:schema=ref("ModelRevisionRead4")
            elif path.endswith("/export"):schema=ref("ModelPackage")
            else:schema=ref("ModelDraftRead4")
        elif path.endswith("/configurations/preview"):
            op["requestBody"]["content"]["application/json"]["schema"]=ref("PublicConfigurationRequest")
            schema=ref("PublicConfigurationPreview")
        elif path.endswith("/configurations"):
            schema=array(ref("FrozenConfigurationRead7")) if method=="get" else ref("FrozenConfigurationRead7");status="200" if method=="get" else "201"
            if method=='post':op['requestBody']['content']['application/json']['schema']=ref('PublicConfigurationCommit')
        elif path.endswith('/result-sources'):
            schema=ref('ResultSourcePage')
            for parameter in op['parameters']:
                if parameter['name']=='limit':parameter['schema']={'type':'integer','minimum':1,'maximum':50,'default':25}
                elif parameter['name']=='cursor':parameter['schema']={'type':'string','maxLength':2048}
            op['description']='Same-study verified retained scalar outputs; no native recheck. At most50 outputs and100 inspected runs per page. Cursor binds actor, study, limit and insertion high-water mark. Unknown or repeated query fields are invalid.'
        elif "/configurations/" in path:schema=ref("FrozenConfigurationRead7")
        elif path.endswith('/computational-record-previews'):
            schema=ref('RecordRequestRead');status='202'
            op['requestBody']['content']['application/json']['schema']=ref('RecordPreviewRequest')
            op['description']='Enqueue bounded data-only archive inspection. No native work occurs in the web process.'
        elif path.endswith('/computational-records'):
            schema=ref('RecordRequestRead');status='202'
            op['requestBody']['content']['application/json']['schema']=ref('RecordCreateRequest')
            op['description']='Enqueue creation from an authorized reviewable preview with its exact digest.'
        elif '/computational-records/' in path:
            schema=None if path.endswith('/download') else ref('RecordRequestRead')
            op['description']='Reauthorize retained closure. Status reads never process queued work; download requires a verified ready create request.'
        elif "/commands/" in path:schema=ref("PublicReceipt")
        elif path.endswith("/execution-readiness"):schema=ref("ExecutionReadiness")
        elif "/evidence-families/" in path:
            if path.endswith("/versions"):
                if method=="post":
                    schema=ref("EvidenceRecord3");status="201"
                    op["requestBody"]["content"]["application/json"]["schema"]=ref("EvidenceRevise3")
                else:
                    schema={**array(ref("EvidenceRecordRead")),"maxItems":100}
                    for parameter in op["parameters"]:
                        if parameter["name"]=="limit":parameter["schema"]={"type":"integer","minimum":1,"maximum":100,"default":50}
                        elif parameter["name"]=="cursor":parameter["schema"]={"type":"string","maxLength":2048}
            else:schema=ref("EvidenceFamily3")
        elif path.endswith("/evidence"):
            if method=="post":
                schema=ref("EvidenceRecord");status="201"
                op["requestBody"]["content"]["application/json"]["schema"]=ref("PublicEvidenceCreate")
            else:
                schema={**array(ref("EvidenceRecord")),"maxItems":100}
                for parameter in op["parameters"]:
                    name=parameter["name"]
                    if name=="limit":parameter["schema"]={"type":"integer","minimum":1,"maximum":100,"default":50}
                    elif name=="cursor":parameter["schema"]={"type":"string","maxLength":2048}
                    elif name=="view":parameter["schema"]={"enum":["heads","versions"],"default":"heads"}
                    elif name=="scope_kind":parameter["schema"]={"enum":["study","model_revision","definition_version","instance","port","connection","configuration","run","criterion","legacy"]}
                    elif name=="legacy_scope":parameter["schema"]={"anyOf":[uuid,{"enum":["null"]}]}
                    elif parameter["in"]=="query":parameter["schema"]=uuid
                op["description"]="Default heads returns one current version per family in stable family insertion order; versions returns immutable rows newest first. Opaque cursor binds actor, study, view, filters and insertion high-water. Unknown/repeated fields and incompatible filters are invalid. Revision requires model; instance requires model and revision; port requires model, revision and instance. Configuration/run filters cannot combine with model filters. legacy_scope is an exact legacy UUID or the literal null; legacy records have no inferred typed scope."
        elif "/evidence/" in path:schema=ref("EvidenceRecord")
        elif path.endswith('/modified-run-seed'):schema=ref('ModifiedRunSeedRead6')
        elif path.endswith("/runs"):
            schema=array(ref('RunHistoryItem')) if method=='get' else ref('PublicRun');status='200' if method=='get' else '202'
        elif '/runs/' in path and '/artifacts/' in path:schema=None
        elif "/runs/" in path:schema=ref("PublicRunDetail")
        else:raise ValueError(path)
        response=envelope(schema) if schema else None
        if path.endswith(("/edits","/preview")) and "/models/" in path:response=ref("ModelDraftEditResponse4")
        op["responses"]={str(code):{"description":"Typed error; inspect outcome before retry","content":{"application/json":{"schema":ref("Error")}}} for code in (400,401,403,404,409,413,422,429,500,503)}
        if response and method=="get" and '/approach' not in path and (path=="/studies" or path.endswith(("/models","/configurations","/runs","/revisions","/evidence")) or "/evidence-families/" in path and path.endswith("/versions")):
            response["properties"]["next_cursor"]=nullable({"type":"string","maxLength":2048} if "/evidence" in path else uuid)
            response["required"].append("next_cursor")
        if response:op["responses"][status]={"description":"Authorized typed result","content":{"application/json":{"schema":response}}}
        if '/runs/' in path and '/artifacts/' in path:
            op['responses']['200']={'description':'Authorized exact retained bytes; never execute or inline-render source',
                'content':{'application/octet-stream':{'schema':{'type':'string','format':'binary'}}},
                'headers':{'X-Content-SHA256':{'schema':sha},'Content-Disposition':{'schema':string}}}
        if '/computational-records/' in path and path.endswith('/download'):
            op['responses']['200']={'description':'Authorized hash-verified computational record export archive (ZIP) for inspection; fixed attachment filename',
                'content':{'application/zip':{'schema':{'type':'string','format':'binary'}}},
                'headers':{'X-Content-SHA256':{'schema':sha},'Content-Disposition':{'schema':{'enum':['attachment; filename="hyprn-mvp-computational-record.zip"']}}}}
        if method=="post" and (path.endswith(("/models","/model-imports","/edits","/commits"))):
            op["responses"]["202"]={"description":"Remote outcome pending; reconcile same command","content":{"application/json":{"schema":envelope(ref("PendingModel"))}}}
        if method in {"post","patch","delete"}:
            op["parameters"]+= [{"name":"Origin","in":"header","required":True,"schema":string}]
            if path!="/session" or method!="post":
                op["parameters"]+=[{"name":"X-CSRF-Token","in":"header","required":True,"schema":string}]
# Domain wording (CONTEXT.md glossary) and request-field guidance appear as operation
# descriptions only. Shared schema components stay byte-equal to contracts/schemas; legacy wire
# names are mapped to domain terms in contracts/README.md ("Domain terms and legacy wire names").
OPERATION_NOTES={
    ('/studies/{study_id}/models','post'):('Create a model in this study. expected_revision is the study\'s current revision '
        '(GET /studies/{study_id}); creating a model advances the study revision. Later model edits and the commit use the '
        'model draft\'s own draft_revision instead.'),
    ('/studies/{study_id}/model-imports','post'):('Import a portable model record. The request field package carries the record '
        '(legacy wire name ModelPackage; not a method package). expected_revision is the study\'s current revision. Import '
        'verifies identities, revision digests, ancestry and exact source bytes; it never imports or runs candidate code.'),
    ('/studies/{study_id}/models/{model_id}/export','get'):('Portable model record (legacy wire name ModelPackage) for one '
        'committed model version: its ancestry, component definitions, exact source bytes and identity relationships. It is '
        'neither a method package nor an execution bundle.'),
    ('/studies/{study_id}/models/{model_id}/preview','post'):('Dry run of a model edit batch against the draft. expected_revision '
        'is the draft\'s current draft_revision; the returned projected token is temporary and never replaces it. Revising a '
        'component definition (revise_definition, including quantity definitions) creates a new definition version; existing '
        'instances keep their pinned version until rebound (see edits).'),
    ('/studies/{study_id}/models/{model_id}/edits','post'):('Apply a model edit batch to the draft. expected_revision is the '
        'draft\'s current draft_revision. Revising a component definition creates a new definition version but does not move '
        'instances: rebind each instance with replace_local_instance_version (expected_definition_version_id = its current pin; '
        'version_ref = the new definition_version_id, or the revise_definition temp_key in the same batch), or selective_rebind '
        'with an explicit port_map when port identities change.'),
    ('/studies/{study_id}/models/{model_id}/commits','post'):('Freeze the draft as an immutable model version (model_revision_id). '
        'expected_revision is the draft_revision being committed.'),
    ('/studies/{study_id}/configurations/preview','post'):('Resolve and check a configuration without saving it. The response '
        'carries request_digest (digest of this request) and candidate_digest (digest of the resolved configuration); commit '
        'with expected_preview_digest = candidate_digest.'),
    ('/studies/{study_id}/configurations','post'):('Save an immutable configuration version. expected_preview_digest must equal '
        'the preview\'s candidate_digest, not its request_digest; a mismatch is reference_conflict. For a new configuration send '
        'configuration_id null and expected_revision null; for a new version of an existing configuration send its '
        'configuration_id and its current head configuration_revision_id as expected_revision.'),
    ('/studies/{study_id}/runs/{run_id}','get'):('Run status and retained history. Criterion evaluations (met, violated or '
        'unresolved) are in history.results.criteria. history.assessment (legacy wire name) only identifies the criterion '
        'evaluator (version, evaluator_sha256); it is not a scientific assessment. history.bundle identifies the execution bundle '
        'the run used (bundle_digest and its pins).'),
}
for (path,method),text in OPERATION_NOTES.items():
    op=spec['paths'][path][method]
    op['description']=(op['description']+' '+text) if op.get('description') else text
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, default=ROOT / 'contracts/hyprn-mvp.openapi.yaml')
parser.parse_args().output.write_text(json.dumps(spec,indent=2)+"\n")
