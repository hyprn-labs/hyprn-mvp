"""Export actual public routes, closed request/response schemas and error statuses."""
import copy
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent/"src"))
from hyprn_mvp_app.api import create_app
from hyprn_mvp_app.contracts import definitions
from hyprn_mvp_app.answers import DEFINITIONS as ANSWER_DEFINITIONS
from hyprn_mvp_app.exploration import DEFINITIONS as EXPLORATION_DEFINITIONS
from hyprn_mvp_app.agent_runtime.schema import RECORD_KINDS
from hyprn_mvp_app.store import AGENT_EFFECTS, RECOVERY_VALUES

ROOT=Path(__file__).resolve().parents[1]
spec=create_app(None,None,None).openapi()
spec["servers"]=[{"url":"/api/1"}]
spec["paths"]={p.removeprefix("/api/1"):v for p,v in spec["paths"].items()}
schemas=spec.setdefault("components",{}).setdefault("schemas",{})
def rewrite(value):
    if isinstance(value,dict):return {k:(v.replace("#/$defs/","#/components/schemas/") if k=="$ref" else rewrite(v)) for k,v in value.items()}
    if isinstance(value,list):return [rewrite(v) for v in value]
    return value
schemas.update(rewrite(definitions()))
schemas.update(rewrite(ANSWER_DEFINITIONS))
schemas.update(rewrite(EXPLORATION_DEFINITIONS))
# Current HTTP reads include new retained formats; authored historical schemas stay frozen.
_PUBLIC_READ_SUCCESSORS = {
    'ApproachClosureRead3': 'ApproachClosureRead4',
    'FrozenConfigurationRead7': 'FrozenConfigurationRead8',
    'RunHistoryRead6': 'RunHistoryRead7',
    'ApproachSavedRead3': 'ApproachSavedRead4',
    'ApproachVersionSavedRead3': 'ApproachVersionSavedRead4',
    'ApproachPreviewRead3': 'ApproachPreviewRead4',
    'ApproachResolution3': 'ApproachResolution4',
    'ApproachReceiptRead2': 'ApproachReceiptRead3',
    'ApproachCommandResultRead2': 'ApproachCommandResultRead3',
    'ConfigurationPreviewRead6': 'ConfigurationPreviewRead7',
    'ModifiedRunSeedRead6': 'ModifiedRunSeedRead7',
    'ResultSource': 'ResultSource2',
    'ResultSourcePage': 'ResultSourcePage2',
}

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
schemas['ApplicationCapabilities'] = obj(
    dict(
        contract_versions=array(string),
        engineering=array(string),
        modeling=array(
            {
                'enum': [
                    'model_revision_listing',
                    'model_rename',
                    'model_assumptions/1',
                    'unit_declarations/1',
                    'quantity_definitions/1',
                ]
            }
        ),
        execution=string,
        unavailable=array(string),
        execution_budget=obj(
            dict(
                default_wall_seconds={'type': 'integer', 'minimum': 1, 'maximum': 3600},
                min_wall_seconds={'const': 1},
                max_wall_seconds={'const': 3600},
                includes_startup={'const': True},
            )
        ),
        model_formats=obj(
            {k: array(string) for k in ('create_request', 'edit_request', 'saved_record')}
        ),
        limits=obj(
            {
                **{
                    k: {'type': 'integer'}
                    for k in (
                        'request_bytes',
                        'source_bytes',
                        'edits',
                        'elements',
                        'depth',
                        'result_source_outputs',
                        'result_source_runs',
                        'result_source_bindings',
                        'result_source_dependencies',
                    )
                },
                'computational_record': ref('ExportLimits'),
            }
        ),
    )
)
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
schemas['ExecutionDiagnostic1'] = obj(
    dict(
        state={
            'enum': [
                'unavailable',
                'timed_out',
                'output_limit',
                'memory_limit',
                'completed',
                'failed',
            ]
        },
        message={'type': 'string', 'maxLength': 512},
        wall_seconds=nullable({'type': 'integer', 'minimum': 1, 'maximum': 3600}),
        elapsed_seconds=nullable({'type': 'number', 'minimum': 0}),
        artifact_id=nullable(uuid),
    )
)
schemas['PublicRunDetail']['properties']['execution_diagnostic'] = ref('ExecutionDiagnostic1')


# Light run status: the facets and criterion outcomes reuse the RetainedResults definitions;
# every value that is not held is null with its reason, never a zero.
def reasoned(value,reasons):
    return obj(dict(value=nullable(value),reason=nullable({'enum':reasons})))
retained=schemas['RetainedResults']['properties']
schemas['RunStatus1']=obj(dict(run_id=uuid,configuration_revision_id=uuid,
    configuration_name={**nullable({'type':'string','maxLength':4096}),
        'description':'As in the run list: the presentation name of '
        'the exact configuration revision; null when unavailable.'},state={'enum':run_states},
    process_state=nullable(copy.deepcopy(schemas['PublicRun']['properties']['process_state'])),
    exit_status=copy.deepcopy(schemas['PublicRun']['properties']['exit_status']),
    facets=obj({k:reasoned(copy.deepcopy(retained[k]),['not_recorded'])
        for k in ('execution',)}),
    criteria=reasoned(copy.deepcopy(retained['criteria']),['not_recorded']),
    times=obj(dict(submitted_at=reasoned({'type':'string','format':'date-time'},['not_recorded']),
        **{k:reasoned({'type':'string','format':'date-time'},['not_projected'])
            for k in ('started_at','finished_at')}))))
schemas['RunStatus1']['description']=(
    'Light status of one run from the stored run state. process_state and exit_status are the '
    'stored lifecycle projection (null before recording). Facets and criteria are the stored '
    'results, each null with reason '
    'not_recorded while the run has no retained results. submitted_at is the acceptance time '
    '(not_recorded for runs accepted '
    'before it was recorded); started_at and finished_at are held by the execution engine and '
    'not projected (not_projected).')
# Agent administration: who wrote what, which agents have access, the Owner's tool tokens.
# The agent and its delegating user are two separate objects; nothing names a confirmer.
date_time={'type':'string','format':'date-time'}
agent_ref=obj(dict(actor_id=uuid,display_name={'type':'string','minLength':1,'maxLength':128}))
delegator_ref=obj(dict(actor_id=uuid,
    display_name=nullable({'type':'string','minLength':1,'maxLength':128})))
schemas['AgentAttribution1']=obj(dict(study_id=uuid,record_kind={'enum':list(RECORD_KINDS)},
    record_id={'type':'string','minLength':1,'maxLength':4096},
    version_id=nullable({'type':'string','minLength':1,'maxLength':4096}),
    command_category={'type':'string','minLength':1,'maxLength':64},command_id=uuid,
    agent=agent_ref,delegator=copy.deepcopy(delegator_ref),recorded_at=date_time))
schemas['AgentAttribution1']['description']=(
    'One record written through an agent, as its receipt attributes it: the agent and the '
    'delegating user it acted for. A study an agent created has record_kind study, its id as '
    'study_id and record_id, and command_category study_create.')
schemas['AgentAttributionPage1']=obj(dict(items={**array(ref('AgentAttribution1')),'maxItems':100},
    next_cursor=nullable({'type':'string','maxLength':512})))
schemas['AgentAccess1']=obj(dict(installation_enabled={'type':'boolean'},
    agents=array(obj(dict(agent=copy.deepcopy(agent_ref),delegator=copy.deepcopy(delegator_ref),
        state={'enum':['active','ended']},
        reason={'enum':['none','revoked','expired','membership_changed']},
        expires_at=date_time,ended_at=nullable(date_time))))))
schemas['AgentAccess1']['description']=(
    'Agent access to this study. installation_enabled is the installation kill switch. Per '
    'agent, the state of its latest delegation: active (reason none) or ended with revoked, '
    'expired or membership_changed (the delegating user no longer holds the role the '
    'delegation needs; ended_at is null because the change carries no time).')
token_properties=dict(token_id=uuid,client_label={'type':'string','minLength':1,'maxLength':128},
    created_at=date_time,expires_at=date_time,revoked_at=nullable(date_time),
    effects={'type':'array','uniqueItems':True,'items':{'enum':sorted(AGENT_EFFECTS)}},
    agent=copy.deepcopy(agent_ref),delegator=copy.deepcopy(delegator_ref))
schemas['AgentToken1']=obj(copy.deepcopy(token_properties))
schemas['AgentToken1']['description']='Tool token metadata; never the token or its hash.'
schemas['AgentTokenRevoke1']=obj({**copy.deepcopy(token_properties),'revoked_at':date_time})
schemas['AgentTokenRevoke1']['description']=(
    'The revoked tool token; its delegation ended with reason revoked, so the agent loses '
    'access to the study at its next call.')
schemas['AgentTokenRevokeCommand']=obj(dict(command_id=uuid))
schemas["PublicReceipt"]=obj(dict(command_id=uuid,state={"enum":["committed","rejected","pending_remote",*run_states]},
    result={"anyOf":[ref("Study"),ref("EvidenceRecord"),ref("FrozenConfigurationRead7"),model_result,
        ref("PendingModel"),ref("PublicRun"),ref('RecordRequestRead'),ref('ApproachCommandResultRead2'),
        ref('AgentTokenRevoke1'),{"type":"null"}]},error=nullable(ref("StoredError"))))
# Receipt recovery, decided by the owner (store.receipt_recovery): every receipt read carries
# it, and a missing receipt in a scope the reader may see carries it in its 404 error object.
recovery_enum={'enum':list(RECOVERY_VALUES)}
retry_after={'type':'integer','minimum':1,'maximum':60}
schemas['PublicReceipt']['properties'].update(recovery=recovery_enum,retry_after_s=retry_after)
schemas['PublicReceipt']['required'].append('recovery')
schemas['PublicReceipt']['properties']['result']['anyOf'].append(ref('ScientificAnswer1'))
schemas['ReceiptError']=copy.deepcopy(schemas['Error'])
schemas['ReceiptError']['properties']['error']['properties'].update(
    recovery=copy.deepcopy(recovery_enum),retry_after_s=copy.deepcopy(retry_after))
RECEIPT_READS=('/studies/{study_id}/commands/{command_id}','/commands/{command_id}')
schemas["ConfigurationCommit"]=ref("ConfigurationCommit1")
schemas.pop('ConfigurationCommitV2',None)
schemas['PublicConfigurationRequest']={'oneOf':[ref('ConfigurationCandidate1'),ref('ConfigurationRequest2'),ref('ConfigurationRequest3'),ref('ConfigurationRequest4')]}
schemas['PublicConfigurationCommit']={'oneOf':[ref('ConfigurationCommit1'),ref('ConfigurationCommit2'),ref('ConfigurationCommit3'),ref('ConfigurationCommit4')]}
schemas['PublicConfigurationPreview']={'oneOf':[ref('CompatibilityResult1'),ref('ConfigurationPreview2'),ref('ConfigurationPreview3'),ref('ConfigurationPreview4'),ref('ConfigurationPreview6'),ref('ConfigurationPreview7')]}
# Preserve the earlier concrete public reader; implemented import/export now
# uses ModelPackage with the qualified native Model4 branch.
schemas["PublicModelPackageRead3"]={"oneOf":[ref("ModelPackage1"),ref("ModelPackage2"),ref("ModelPackage3")]}
schemas["ImportModel"]["properties"]["package"]=ref("ModelPackage")
schemas['SubmitRun']['properties'].update(command_id=uuid, configuration_revision_id=uuid)


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
        elif path.startswith(('/agent/','/studies/{study_id}/agent/')):
            schema={'/agent/attribution/studies':ref('AgentAttributionPage1'),
                '/studies/{study_id}/agent/attribution':ref('AgentAttributionPage1'),
                '/studies/{study_id}/agent/access':ref('AgentAccess1'),
                '/studies/{study_id}/agent/tokens':{**array(ref('AgentToken1')),'maxItems':100},
                '/studies/{study_id}/agent/tokens/{token_id}/revoke':ref('AgentTokenRevoke1')}[path]
            if path.endswith('/revoke'):
                body=op['requestBody']['content']['application/json']
                body['schema']=ref('AgentTokenRevokeCommand')
            for parameter in op['parameters']:
                if parameter['in']=='path':parameter['schema']=uuid
                elif parameter['name']=='limit':
                    parameter['schema']={'type':'integer','minimum':1,'maximum':100,'default':50}
                elif parameter['name']=='cursor':
                    parameter['schema']=uuid if path.endswith('/tokens') else {'type':'string',
                        'maxLength':512}
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
        elif path.endswith('/answers') and '/approach/' in path:
            schema=ref('ScientificAnswerHeads1')
            op['description']=(
                'Explicit answer heads for this exact saved approach version. Empty means '
                'unassessed. Historical answer versions remain readable by their exact IDs.')
        elif '/exploration-requests' in path:
            schema=ref('ExplorationOperation1')
            if method == 'get' and path.endswith('/exploration-requests'):
                schema={'type': 'array', 'maxItems': 20, 'items': schema}
            if method == 'post':
                status='202'
                op['requestBody']['content']['application/json']['schema']=ref('ExplorationRequest1')
            op['description']=(
                'Bounded data-only slice design or assessed prediction from exact retained '
                'scalar runs. Poll the operation; an uncertain outcome is never redispatched.')
        elif '/exploration-basis/' in path:
            schema=ref('ExplorationBasis1')
            op['description']=(
                'Read the complete free/connected input inventory for an explicit frozen '
                'configuration linked by this exact answer or its exact case answers. '
                'Run IDs identify cited runs for this configuration, not computed values. '
                'Source hashes only; no candidate execution, current-head substitution, '
                'unit conversion, inferred ranges or inferred co-varying inputs.')
        elif path.endswith('/answers') or '/answers/' in path:
            schema=ref('ScientificAnswer1')
            if method=='post':
                status='201'
                request_schema = op['requestBody']['content']['application/json']
                request_schema['schema'] = ref('ScientificAnswerSave1')
                op['description']=(
                    'Save an immutable authored case answer (case_id) or study synthesis '
                    '(case_id null). expected_revision is null for the first answer, otherwise '
                    'its current answer_version_id. Receipt category answer_save. All basis IDs '
                    'are exact, same-study references; synthesis may cite exact case answers '
                    'from this approach version. No conclusion is inferred from execution or '
                    'criteria. Ordinary study owner/writer sessions only.')
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
            schema=ref('ResultSourcePage2')
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
        elif path.endswith('/run-status'):
            schema={**array(ref('RunStatus1')),'minItems':1,'maxItems':20}
            for parameter in op['parameters']:
                if parameter['in']=='path':parameter['schema']=uuid
                elif parameter['name']=='run_id':
                    parameter['schema']={'type':'array','items':uuid,'minItems':1,'maxItems':20,
                        'uniqueItems':True}
                    parameter['description']=('One run of this study per repetition, 1 to 20 '
                        'distinct runs; the answer keeps this order. No other query field.')
        elif '/runs/' in path and '/artifacts/' in path:schema=None
        elif "/runs/" in path:schema=ref("PublicRunDetail")
        else:raise ValueError(path)
        response=envelope(schema) if schema else None
        if response and method == 'get' and path.endswith('/exploration-requests'):
            response['properties']['next_cursor'] = nullable(uuid)
            response['required'].append('next_cursor')
        if path.endswith(("/edits","/preview")) and "/models/" in path:response=ref("ModelDraftEditResponse4")
        op["responses"]={str(code):{"description":"Typed error; inspect outcome before retry","content":{"application/json":{"schema":ref("Error")}}} for code in (400,401,403,404,409,413,422,429,500,503)}
        if response and method=="get" and '/approach' not in path and (path=="/studies" or path.endswith(("/models","/configurations","/runs","/revisions","/evidence")) or "/evidence-families/" in path and path.endswith("/versions")):
            response["properties"]["next_cursor"]=nullable({"type":"string","maxLength":2048} if "/evidence" in path else uuid)
            response["required"].append("next_cursor")
        if response and path.endswith('/agent/tokens'):
            response['properties']['next_cursor']=nullable(uuid)
            response['required'].append('next_cursor')
        if response:op["responses"][status]={"description":"Authorized typed result","content":{"application/json":{"schema":response}}}
        if path in RECEIPT_READS:
            op['responses']['404']['content']['application/json']['schema']=ref('ReceiptError')
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
RECOVERY_NOTE=('recovery says how to proceed after a lost reply, decided by the owner. adopt: '
    'the result is the outcome; refused: the stored rejection is the outcome; wait: read again '
    'after retry_after_s; resend_same_command: send the same command id and body again; '
    'uncertain: never resend; a run is never resent. A missing receipt in a scope the reader may '
    'see is resource_not_found 404 whose error carries recovery (and retry_after_s); without '
    'recovery the reader may not see the scope.')
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
        'unresolved) are in history.results.criteria. history.assessment (legacy wire name) only '
        'identifies the criterion '
        'evaluator (version, evaluator_sha256); it is not a scientific assessment. '
        'history.bundle identifies the execution bundle '
        'the run used (bundle_digest and its pins).'),
    ('/studies/{study_id}/agent/attribution','get'):('Records of this study written through an '
        'agent, newest first, each with the agent and the delegating user it acted for (separate '
        'objects). Any member; agent sessions are refused (403). Every entry is checked against '
        'its receipt and withheld when the receipt actor is not that agent. The cursor is the '
        'opaque next_cursor of the previous page.'),
    ('/studies/{study_id}/agent/access','get'):('Agent access to this study: the installation '
        'kill switch and, per agent, whether its access is active or ended and why. Any member; '
        'agent sessions are refused (403).'),
    ('/studies/{study_id}/agent/tokens','get'):('Tool tokens of this study, newest first, as '
        'metadata only (never a token or a hash). Study Owner only (writers and readers 403); '
        'agent sessions are refused (403). No route mints a token: tokens are minted by the '
        'operator command of the local edition.'),
    ('/studies/{study_id}/agent/tokens/{token_id}/revoke','post'):('Revoke one tool token of '
        'this study and end its delegation (reason revoked): the agent loses access to the '
        'study at its next call. Study Owner only; agent sessions are refused (403). '
        'Idempotent by command_id (receipt category agent_token_revoke); a repeat returns the '
        'stored outcome. Saved records and submitted runs are unchanged.'),
    ('/agent/attribution/studies','get'):('Studies an agent created that the signed-in person '
        'is a current member of, newest first (record_kind study), each checked against the '
        'agent\'s pre-study receipt. Agent sessions are refused (403).'),
    **{(path,'get'):RECOVERY_NOTE for path in RECEIPT_READS},
    ('/studies/{study_id}/run-status','get'):('Light run status from the stored run state: state, '
        'lifecycle projection, '
        'outcome facets, criterion outcomes and recorded times; never the full history; '
        'nothing is read from the execution engine.'),
}
for (path,method),text in OPERATION_NOTES.items():
    op=spec['paths'][path][method]
    op['description']=(op['description']+' '+text) if op.get('description') else text

# Project historical scientific records at the public boundary. An existing digest
# identifies the retained source; record_view identifies the projected canonical JSON.
# Persisted schemas remain in model.schema.json and exact artifact downloads.
def public_views():
    marker = obj(dict(schema_version={'const':'1'}, source_sha256=sha, view_sha256=sha))
    marker['description'] = ('This object is a public view, not the exact retained record. '
        'source_sha256 hashes the original object; view_sha256 hashes this object without '
        'record_view. Existing digest fields identify original retained records.')
    schemas['RecordView1'] = marker
    legacy = schemas['RetainedResults']
    for key in ('convergence', 'optimization', 'completeness', 'applicability'):
        legacy['properties'].pop(key)
        legacy['required'].remove(key)
    legacy['properties']['record_view'] = ref('RecordView1')
    legacy['required'].append('record_view')
    legacy['description'] = (
        'Public projection of a retained format-1 result; exact source bytes are downloadable.'
    )
    affected = {'RetainedResults'}
    def contains(value):
        if isinstance(value, dict):
            if value.get('$ref', '').removeprefix('#/components/schemas/') in affected:
                return True
            return any(contains(child) for child in value.values())
        return isinstance(value, list) and any(contains(child) for child in value)
    while True:
        reached = {name for name, value in schemas.items() if contains(value)} | affected
        if reached == affected: break
        affected = reached
    def mark(value):
        if isinstance(value, dict):
            if value.get('type') == 'object' and contains(value):
                value.setdefault('properties', {})['record_view'] = ref('RecordView1')
            for child in list(value.values()):mark(child)
        elif isinstance(value, list):
            for child in value:mark(child)
    for value in schemas.values():mark(value)
    # Snapshot prior definitions under private-to-this-document aliases before
    # widening public read aliases, so unions never become self-referential.
    for old in _PUBLIC_READ_SUCCESSORS:
        schemas['Previous'+old] = copy.deepcopy(schemas[old])
    def old_refs(value):
        if isinstance(value, dict):
            return {
                k: (
                    '#/components/schemas/Previous' + v.removeprefix('#/components/schemas/')
                    if k == '$ref'
                    and v.removeprefix('#/components/schemas/') in _PUBLIC_READ_SUCCESSORS
                    else old_refs(v)
                )
                for k, v in value.items()
            }
        if isinstance(value, list):return [old_refs(v) for v in value]
        return value
    # Only the new successor definitions need their embedded predecessor links frozen.
    for old, new in _PUBLIC_READ_SUCCESSORS.items():
        schemas[old] = old_refs(copy.deepcopy(schemas[new]))
public_views()

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, default=ROOT / 'contracts/hyprn-mvp.openapi.yaml')
parser.parse_args().output.write_text(json.dumps(spec,indent=2)+"\n")
