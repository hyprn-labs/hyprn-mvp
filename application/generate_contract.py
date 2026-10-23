"""Export actual public routes, closed request/response schemas and error statuses."""
import copy
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent/"src"))
from hyprn_mvp_app.api import create_app
from hyprn_mvp_app.contracts import definitions
from hyprn_mvp_app.brief import DEFINITIONS as BRIEF_DEFINITIONS
from hyprn_mvp_app.calculations import DEFINITIONS as CALCULATION_DEFINITIONS
from hyprn_mvp_app.calculation_designs import DEFINITIONS as CALCULATION_SAMPLE_DEFINITIONS
from hyprn_mvp_app.calculation_estimates import DEFINITIONS as CALCULATION_ESTIMATE_DEFINITIONS
from hyprn_mvp_app.calculation_preparation import (
    DEFINITIONS as CALCULATION_PREPARATION_DEFINITIONS,
)
from hyprn_mvp_app.calculation_exploration import DEFINITIONS as CALCULATION_EXPLORATION_DEFINITIONS
from hyprn_mvp_app.explanations import DEFINITIONS as EXPLANATION_DEFINITIONS
from hyprn_mvp_app.computational_export import DEFINITIONS as COMPUTATIONAL_RECORD_DEFINITIONS
from hyprn_mvp_app.study_answer import DEFINITIONS as STUDY_ANSWER_DEFINITIONS
from hyprn_mvp_app.agent_runtime.schema import RECORD_KINDS
from hyprn_mvp_app.assistant.schema import DEFINITIONS as ASSISTANT_DEFINITIONS
from hyprn_mvp_app.assistant.research import DEFINITIONS as SOURCE_INSPECTION_DEFINITIONS
from hyprn_mvp_app.store import RECOVERY_VALUES

ROOT=Path(__file__).resolve().parents[1]
spec=create_app(None,None,None).openapi()
spec["servers"]=[{"url":"/api/1"}]
spec["paths"]={p.removeprefix("/api/1"):v for p,v in spec["paths"].items()}
# Canonical analysis aliases receive the fully authored compatibility contract below.
spec['paths'] = {p: v for p, v in spec['paths'].items()
                 if '/analyses' not in p and '/analysis-' not in p}
schemas=spec.setdefault("components",{}).setdefault("schemas",{})
def rewrite(value):
    if isinstance(value,dict):return {k:(v.replace("#/$defs/","#/components/schemas/") if k=="$ref" else rewrite(v)) for k,v in value.items()}
    if isinstance(value,list):return [rewrite(v) for v in value]
    return value
schemas.update(rewrite(definitions()))
schemas.update(rewrite(json.loads((ROOT/'contracts/retired-exploration-definitions.json').read_text())))
schemas.update(rewrite(BRIEF_DEFINITIONS))
schemas.update(rewrite(CALCULATION_DEFINITIONS))
schemas.update(rewrite(CALCULATION_SAMPLE_DEFINITIONS))
schemas.update(rewrite(CALCULATION_ESTIMATE_DEFINITIONS))
schemas.update(rewrite(CALCULATION_EXPLORATION_DEFINITIONS))
schemas.update(rewrite(CALCULATION_PREPARATION_DEFINITIONS))
schemas.update(rewrite(EXPLANATION_DEFINITIONS))
schemas.update(rewrite(COMPUTATIONAL_RECORD_DEFINITIONS))
schemas.update(rewrite(STUDY_ANSWER_DEFINITIONS))
schemas.update(rewrite(ASSISTANT_DEFINITIONS))
schemas.update(rewrite(SOURCE_INSPECTION_DEFINITIONS))
# Current HTTP reads include new retained formats; authored historical schemas stay frozen.
_PUBLIC_READ_SUCCESSORS = {
    'ComputationalRecordManifestRead': 'ComputationalRecordManifestRead3',
    'ApproachClosureRead3': 'ApproachClosureRead4',
    'FrozenConfigurationRead7': 'FrozenConfigurationRead10',
    'FrozenConfigurationRead9': 'FrozenConfigurationRead10',
    'RunHistoryRead6': 'RunHistoryRead9',
    'RunHistoryRead8': 'RunHistoryRead9',
    'ApproachSavedRead3': 'ApproachSavedRead4',
    'ApproachVersionSavedRead3': 'ApproachVersionSavedRead4',
    'ApproachPreviewRead3': 'ApproachPreviewRead4',
    'ApproachResolution3': 'ApproachResolution4',
    'ApproachReceiptRead2': 'ApproachReceiptRead3',
    'ApproachCommandResultRead2': 'ApproachCommandResultRead3',
    'ConfigurationPreviewRead6': 'ConfigurationPreviewRead8',
    'ModifiedRunSeedRead6': 'ModifiedRunSeedRead9',
    'ModifiedRunSeedRead8': 'ModifiedRunSeedRead9',
    'ResultSource': 'ResultSource2',
    'ResultSourcePage': 'ResultSourcePage3',
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
schemas["ConfigurationSummary1"]=obj(dict(configuration_revision_id=uuid,configuration_id=uuid,model_id=uuid,model_revision_id=uuid,name={"type":"string","maxLength":4096},input_count={"type":"integer","minimum":0}))
schemas["Association"]=obj(dict(model_id=uuid,command_id=uuid,name={"anyOf":[string,{"type":"null"}]}))
schemas["UserProfile1"]=obj(dict(
    actor_id=uuid,account_name={"type":"string","maxLength":128},
    display_alias=nullable({"type":"string","maxLength":128}),
    display_name={"type":"string","maxLength":128},
    revision={"type":"integer","minimum":0}))
schemas["Session"]=obj(dict(actor_id=uuid,csrf_token=string,expires_at={"type":"number"},
    profile=ref("UserProfile1")))
schemas["EndedSession"]=obj(dict(ended={"const":True}))
schemas["SessionMode"]=obj(dict(mode={"type":"string","enum":["local","hosted"]}))
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
model_result={"anyOf":[obj(dict(data=ref("ModelDraftRead5"))),obj(dict(data=ref("ModelDraftRead5"),created_ids=ref("CreatedIds"),diagnostics=array(ref("Diagnostic")))),obj(dict(data=ref("ModelRevisionRead5")))]}
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

schemas['PublicRunDetail2'] = copy.deepcopy(schemas['PublicRunDetail'])
del schemas['PublicRunDetail2']['properties']['execution_diagnostic']
schemas['RunHistoryItem2'] = copy.deepcopy(schemas['RunHistoryItem'])
schemas['ExecutionSummary1'] = obj(dict(
    status={'enum': ['queued', 'ready', 'starting', 'running', 'completed', 'failed',
                     'timed_out', 'preparation_failed', 'needs_review', 'results_unavailable']},
    duration_seconds=nullable({'type': 'number', 'minimum': 0}),
))
schemas['PublicRunDetail2']['properties']['execution_summary'] = ref('ExecutionSummary1')
schemas['RunHistoryItem2']['properties']['execution_summary'] = ref('ExecutionSummary1')


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
    criteria=reasoned(copy.deepcopy(retained['criteria']),['not_recorded','evaluated_in_calculations']),
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
# Agent administration: attribution and current delegated access.
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
schemas["PublicReceipt"]=obj(dict(command_id=uuid,state={"enum":["committed","rejected","pending_remote",*run_states]},
    result={"anyOf":[ref("Study"),ref("EvidenceRecord"),ref("FrozenConfigurationRead7"),model_result,
        ref("PendingModel"),ref("PublicRun"),ref('RecordRequestRead'),ref('ApproachCommandResultRead2'),
        {"type":"null"}]},error=nullable(ref("StoredError"))))
# Receipt recovery, decided by the owner (store.receipt_recovery): every receipt read carries
# it, and a missing receipt in a scope the reader may see carries it in its 404 error object.
recovery_enum={'enum':list(RECOVERY_VALUES)}
retry_after={'type':'integer','minimum':1,'maximum':60}
schemas['PublicReceipt']['properties'].update(recovery=recovery_enum,retry_after_s=retry_after)
schemas['PublicReceipt']['required'].append('recovery')
schemas['PublicReceipt']['properties']['result']['anyOf'].append(ref('ScientificAnswer1'))
schemas['PublicReceipt']['properties']['result']['anyOf'] += [
    ref('StudyBriefDraftRead2'),
    ref('StudyBriefVersionSavedRead2'),
]
schemas['PublicReceipt']['properties']['result']['anyOf'] += [
    ref('CalculationVersionRead4'),
    ref('ReferenceMarkState1'),
]
schemas['PublicReceipt']['properties']['result']['anyOf'] += [
    ref('ModelExplanationDraftRead3'),
    ref('ModelExplanationVersionSavedRead3'),
]
schemas['PublicReceipt']['properties']['result']['anyOf'] += [
    ref('StudyAnswerDraftRead3'),
    ref('StudyAnswerVersionSavedRead3'),
]
schemas['ReceiptError'] = copy.deepcopy(schemas['Error'])
schemas['ReceiptError']['properties']['error']['properties'].update(
    recovery=copy.deepcopy(recovery_enum),retry_after_s=copy.deepcopy(retry_after))
RECEIPT_READS=('/studies/{study_id}/commands/{command_id}','/commands/{command_id}')
schemas["ConfigurationCommit"]=ref("ConfigurationCommit1")
schemas.pop('ConfigurationCommitV2',None)
# New configurations are version 6 only: no criteria and no approach binding (ADR-0010).
schemas['PublicConfigurationRequest']=ref('ConfigurationRequest6')
schemas['PublicConfigurationCommit']=ref('ConfigurationCommit6')
schemas['PublicConfigurationPreview']=ref('ConfigurationPreview8')
# Preserve the earlier concrete public reader; implemented import/export now
# uses ModelPackage with the qualified native Model4 branch.
schemas["PublicModelPackageRead3"]={"oneOf":[ref("ModelPackage1"),ref("ModelPackage2"),ref("ModelPackage3")]}
schemas["ImportModel"]["properties"]["package"]=ref("ModelPackageRead5")
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
        elif path=="/session/mode":
            schema=ref("SessionMode");op["security"]=[]
        elif path=="/session/external":
            schema=ref("Session");op["security"]=[]
        elif path=="/capabilities":schema=ref("ApplicationCapabilities")
        elif path=="/profile":schema=ref("UserProfile1")
        elif path.startswith(('/agent/','/studies/{study_id}/agent/')):
            schema={'/agent/attribution/studies':ref('AgentAttributionPage1'),
                '/studies/{study_id}/agent/attribution':ref('AgentAttributionPage1'),
                '/studies/{study_id}/agent/access':ref('AgentAccess1')}[path]
            for parameter in op['parameters']:
                if parameter['in'] == 'path':
                    parameter['schema'] = uuid
                elif parameter['name'] == 'limit':
                    parameter['schema'] = {
                        'type': 'integer',
                        'minimum': 1,
                        'maximum': 100,
                        'default': 50,
                    }
                elif parameter['name'] == 'cursor':
                    parameter['schema'] = (
                        uuid if path.endswith('/tokens') else {'type': 'string', 'maxLength': 512}
                    )
        elif path == '/studies':
            schema = array(ref('Study')) if method == 'get' else ref('Study')
            status = '200' if method == 'get' else '201'
            for parameter in op['parameters']:
                if parameter['name'] == 'archived':
                    parameter['schema'] = {'enum': ['true', 'false'], 'default': 'false'}
                    parameter['description'] = (
                        'false (default) lists studies that are not archived; true lists '
                        'only archived studies. At most once.'
                    )
        elif path in ('/assistant/budget', '/studies/{study_id}/assistant/budget'):
            schema = ref('AssistantBudgetRead2')
            status = '200'
            for parameter in op['parameters']:
                if parameter['in'] == 'path':
                    parameter['schema'] = uuid
            op['description'] = (
                'Human-only cumulative user spending across all owned study conversations. '
                'No session ceiling or automatic reset. Unknown usage is null, not zero.'
            )
        elif path.startswith('/studies/{study_id}/assistant'):
            schema = ref('AssistantConversationRead6')
            status = '200' if method == 'get' else '202'
            if method == 'get' and path.endswith('/assistant'):
                op['parameters'] += [
                    dict(name=name, **{'in': 'query'}, required=False, schema=uuid,
                         description='Study-scoped message cursor; use at most one direction.')
                    for name in ('after', 'before')
                ]
            for parameter in op['parameters']:
                if parameter['in'] == 'path':
                    parameter['schema'] = uuid
            if method == 'post':
                request_name = (
                    'AssistantResumeRequest1' if path.endswith('/resume')
                    else 'AssistantStopRequest1' if path.endswith('/stop')
                    else 'AssistantMessageRequest1'
                )
                op['requestBody']['content']['application/json']['schema'] = ref(request_name)
            op['description'] = (
                'Human-only, study-authorized managed conversation. One active turn per study; '
                'messages are idempotent by command_id. Stop fences new tool admission before '
                'requesting provider interruption. Uncertain delivery is never blindly retried. '
                'All scientific effects use the delegated tool runtime and public API. '
                'Provider credentials and raw provider records are never returned.'
            )
        elif path == '/studies/{study_id}':
            schema = ref('Study')
        elif path in ('/studies/{study_id}/archive', '/studies/{study_id}/restore'):
            schema = ref('Study')
            op['requestBody']['content']['application/json']['schema'] = ref('StudyArchiveCommand')
            for parameter in op['parameters']:
                if parameter['in'] == 'path':
                    parameter['schema'] = uuid
            op['description'] = (
                'Study-wide archive state (owner or writer, as study edits; '
                'reader403; non-member404). Idempotent by command_id '
                '(receipt category study_archive); the same id for the other '
                'operation is command_payload_conflict. Target state: an '
                'already archived/restored study commits unchanged. Never changes '
                'the study record or revision and never deletes anything.'
            )
        elif path.startswith('/studies/{study_id}/models/{model_id}') and path.endswith(
            ('/explanation', '/explanation/draft', '/explanation/versions')
        ):
            name, request_name = {
                ('/studies/{study_id}/models/{model_id}/explanation', 'get'): (
                    'ModelExplanationStateRead3',
                    None,
                ),
                ('/studies/{study_id}/models/{model_id}/explanation/draft', 'post'): (
                    'ModelExplanationDraftRead3',
                    'ModelExplanationDraftSaveRead3',
                ),
                ('/studies/{study_id}/models/{model_id}/explanation/versions', 'get'): (
                    'ModelExplanationVersionPageRead3',
                    None,
                ),
                ('/studies/{study_id}/models/{model_id}/explanation/versions', 'post'): (
                    'ModelExplanationVersionSavedRead3',
                    'ModelExplanationVersionSave1',
                ),
                (
                    '/studies/{study_id}/models/{model_id}/revisions/{revision_id}/explanation',
                    'get',
                ): ('ModelVersionExplanationRead3', None),
            }[(path, method)]
            schema = ref(name)
            if request_name:
                op['requestBody']['content']['application/json']['schema'] = ref(request_name)
            if path.endswith('/versions') and method == 'post':
                status = '201'
            for parameter in op['parameters']:
                if parameter['in'] == 'path':
                    parameter['schema'] = uuid
            if path.endswith('/versions') and method == 'get':
                op['parameters'] += [
                    dict(
                        name='limit',
                        **{'in': 'query'},
                        required=False,
                        schema={'type': 'integer', 'minimum': 1, 'maximum': 100, 'default': 20},
                    ),
                    dict(
                        name='before',
                        **{'in': 'query'},
                        required=False,
                        schema={'type': 'integer', 'minimum': 1},
                    ),
                ]
            op['description'] = (
                'The model explanation (ADR-0007): what a model version represents, its basis and '
                'reasoning, its calculation logic, explanations of its components and attached '
                'evidence. The application owns it; the modeling service never '
                'stores it. One draft '
                'per model with a revision check; saving a version freezes the draft for one exact '
                'model version (at most one explanation per model version, never changed) and '
                'continues the draft. Reading an explanation never contacts the modeling service. '
                'Receipt categories model_explanation_draft and '
                'model_explanation_version. Evidence '
                'references must exist in this study; no other query fields are accepted.'
            )
        elif path.startswith('/studies/{study_id}/brief'):
            name,request_name={
                ('/studies/{study_id}/brief','get'):('StudyBriefStateRead2',None),
                ('/studies/{study_id}/brief/draft','post'):('StudyBriefDraftRead2','StudyBriefDraftSaveRead2'),
                ('/studies/{study_id}/brief/versions','get'):('StudyBriefVersionPageRead2',None),
                ('/studies/{study_id}/brief/versions','post'):('StudyBriefVersionSavedRead2','StudyBriefVersionSave1'),
                ('/studies/{study_id}/brief/versions/{version_id}','get'):('StudyBriefVersionRead2',None),
            }[(path,method)]
            schema=ref(name)
            if request_name:op['requestBody']['content']['application/json']['schema']=ref(request_name)
            if path.endswith('/versions') and method=='post':status='201'
            for parameter in op['parameters']:
                if parameter['in']=='path':parameter['schema']=uuid
            if path.endswith('/versions') and method=='get':
                op['parameters'] += [dict(name='limit',**{'in':'query'},required=False,schema={'type':'integer','minimum':1,'maximum':100,'default':20}),
                    dict(name='before',**{'in':'query'},required=False,schema={'type':'integer','minimum':1})]
            op['description']=(
                'The study brief (ADR-0007, ADR-0010): question, alternatives, study criteria, scope, '
                'global assumptions, limits and open questions. One draft per study with a revision '
                'check; saving a version freezes the current draft exactly and continues the draft. '
                'Receipt categories brief_draft and brief_version. Evidence references must exist in '
                'this study; no other query fields are accepted.'
            )
        elif path.startswith('/studies/{study_id}/answer/') or path == '/studies/{study_id}/answer':
            name, request_name = {
                ('/studies/{study_id}/answer', 'get'): ('StudyAnswerStateRead3', None),
                ('/studies/{study_id}/answer/draft', 'post'): (
                    'StudyAnswerDraftRead3',
                    'StudyAnswerDraftSaveRead3',
                ),
                ('/studies/{study_id}/answer/versions', 'get'): ('StudyAnswerVersionPageRead3', None),
                ('/studies/{study_id}/answer/versions', 'post'): (
                    'StudyAnswerVersionSavedRead3',
                    'StudyAnswerVersionSave1',
                ),
                ('/studies/{study_id}/answer/versions/{version_id}', 'get'): (
                    'StudyAnswerVersionRead3',
                    None,
                ),
            }[(path, method)]
            schema = ref(name)
            if request_name:
                op['requestBody']['content']['application/json']['schema'] = ref(request_name)
            if path.endswith('/versions') and method == 'post':
                status = '201'
            for parameter in op['parameters']:
                if parameter['in'] == 'path':
                    parameter['schema'] = uuid
            if path.endswith('/versions') and method == 'get':
                op['parameters'] += [
                    dict(
                        name='limit',
                        **{'in': 'query'},
                        required=False,
                        schema={'type': 'integer', 'minimum': 1, 'maximum': 100, 'default': 20},
                    ),
                    dict(
                        name='before',
                        **{'in': 'query'},
                        required=False,
                        schema={'type': 'integer', 'minimum': 1},
                    ),
                ]
            op['description'] = (
                'The study answer (ADR-0008, ADR-0010): one draft per study with '
                'a revision check and '
                'immutable, numbered versions; the latest version is the only '
                'answer head. A version pins '
                'one saved brief version, maps every alternative to calculation '
                'versions, and states its '
                'outcome explicitly (recommended, no_go for a single alternative, '
                'or no_recommendation with '
                'its basis); nothing is inferred from execution or criteria. '
                'Every cited calculation version, '
                'run and evidence version must belong to this study. Table cells '
                "carry the cited run's "
                'criterion evaluation as the calculation reports it when saved. Receipt categories '
                'answer_draft and answer_version; no other query fields are accepted.'
            )
        elif path.startswith(
            ('/studies/{study_id}/calculation', '/studies/{study_id}/reference-marks')
        ):
            name, request_name = {
                ('/studies/{study_id}/calculations', 'get'): ('CalculationPage4', None),
                ('/studies/{study_id}/calculations', 'post'): (
                    'CalculationVersionRead4',
                    'CalculationCreate4',
                ),
                ('/studies/{study_id}/calculations/{calculation_id}', 'get'): (
                    'Calculation4',
                    None,
                ),
                ('/studies/{study_id}/calculations/{calculation_id}/versions', 'get'): (
                    'CalculationVersionPage4',
                    None,
                ),
                ('/studies/{study_id}/calculations/{calculation_id}/versions', 'post'): (
                    'CalculationVersionRead4',
                    'CalculationVersionSave4',
                ),
                ('/studies/{study_id}/calculation-versions/{version_id}', 'get'): (
                    'CalculationVersionRead4',
                    None,
                ),
                ('/studies/{study_id}/calculation-versions/{version_id}/execution', 'get'):
                    ('AnalysisExecutionRead2', None),
                ('/studies/{study_id}/calculation-versions/{version_id}/execution', 'post'):
                    ('AnalysisExecution2', 'AnalysisLaunch1'),
                ('/studies/{study_id}/calculation-versions/{version_id}/execution/recovery', 'get'):
                    ('AnalysisExecutionRecovery1', None),
                ('/studies/{study_id}/calculation-versions/{version_id}/execution/resume', 'post'):
                    ('AnalysisExecution2', 'AnalysisResume1'),
                ('/studies/{study_id}/calculation-versions/{version_id}/execution/cancellation', 'post'):
                    ('AnalysisExecutionRead2', 'AnalysisLaunch1'),
                ('/studies/{study_id}/calculation-versions/{version_id}/runs', 'get'): (
                    'CalculationRunPage1',
                    None,
                ),
                ('/studies/{study_id}/calculation-versions/{version_id}/run-requests', 'post'): (
                    'CalculationRunRequestResult1',
                    'CalculationRunRequest1',
                ),
                ('/studies/{study_id}/calculation-versions/{version_id}/estimates', 'get'): (
                    'CalculationEstimatePage2',
                    None,
                ),
                ('/studies/{study_id}/calculation-samples', 'get'): (
                    'CalculationSamplePage4',
                    None,
                ),
                ('/studies/{study_id}/calculation-samples', 'post'): (
                    'CalculationSampleOperationRead4',
                    'CalculationSampleRequestRead4',
                ),
                ('/studies/{study_id}/calculation-samples/{operation_id}', 'get'): (
                    'CalculationSampleOperationRead4',
                    None,
                ),
                ('/studies/{study_id}/calculation-estimates', 'post'): (
                    'CalculationEstimateRead2',
                    'CalculationEstimateRequest1',
                ),
                ('/studies/{study_id}/calculation-estimates/{estimate_id}', 'get'): (
                    'CalculationEstimateRead2',
                    None,
                ),
                ('/studies/{study_id}/calculation-versions/{version_id}/exploration', 'get'): (
                    'CalculationExploration1', None),
                ('/studies/{study_id}/calculation-estimates/{estimate_id}/predictions', 'post'): (
                    'CalculationPrediction1', 'CalculationPredictionRequest1'),
                ('/studies/{study_id}/calculation-estimates/{estimate_id}/preparation', 'post'): (
                    'CalculationPreparation1', 'CalculationPreparationRequest1'),
                ('/studies/{study_id}/reference-marks', 'get'): ('ReferenceMarkList1', None),
                ('/studies/{study_id}/reference-marks', 'post'): (
                    'ReferenceMarkState1',
                    'ReferenceMarkCommand1',
                ),
            }[(path, method)]
            schema = ref(name)
            if request_name:
                op['requestBody']['content']['application/json']['schema'] = ref(request_name)
            if method == 'post' and path.endswith(('/calculations', '/versions')):
                status = '201'
            if method == 'post' and path.endswith(
                ('/calculation-samples', '/calculation-estimates')
            ):
                status = '202'
            for parameter in op['parameters']:
                if parameter['in']=='path':parameter['schema']=uuid
            cursor=dict(type='integer',minimum=1)
            if (path,method) in (('/studies/{study_id}/calculations','get'),('/studies/{study_id}/calculations/{calculation_id}/versions','get')):
                op['parameters'] += [dict(name='limit',**{'in':'query'},required=False,schema={'type':'integer','minimum':1,'maximum':100,'default':20}),
                    dict(name='after' if path.endswith('/calculations') else 'before',**{'in':'query'},required=False,schema=cursor)]
                if path.endswith('/calculations'):
                    op['parameters'].append(dict(name='model_revision_id',**{'in':'query'},required=False,schema=uuid,
                        description='Only calculations whose latest version uses this model version.'))
            if path.endswith('/runs'):
                op['parameters'] += [dict(name='limit',**{'in':'query'},required=False,schema={'type':'integer','minimum':1,'maximum':20,'default':20}),
                    dict(name='after',**{'in':'query'},required=False,schema=cursor)]
            if path.endswith('/calculation-versions/{version_id}/runs'):
                op['parameters'].append(dict(
                    name='configuration_revision_id', **{'in': 'query'}, required=False,
                    schema=uuid, description='Only runs of this member configuration.'))
            if path.endswith('/reference-marks') and method=='get':
                op['parameters'] += [dict(name='model_id',**{'in':'query'},required=False,schema=uuid)]
            if path.endswith('/exploration'):
                op['parameters'] += [
                    dict(name='group', **{'in': 'query'}, required=False,
                         schema=dict(type='integer', minimum=1, maximum=10000, default=1)),
                    dict(name='estimate_id', **{'in': 'query'}, required=False, schema=uuid),
                ]
            if path.endswith('/estimates'):
                op['parameters'] += [
                    dict(name='cursor', **{'in': 'query'}, required=False, schema=uuid)
                ]
            op['description'] = (
                'Calculations (ADR-0009, ADR-0010): immutable, numbered versions, each freezing a set of '
                'configuration versions of one model version, how the set was made and the binding of '
                'each criterion of one saved brief version to the output that measures it. A binding '
                'needs the output\'s units to equal the criterion\'s exactly; nothing is converted. A '
                'calculation keeps its model; saving a version checks expected_version_id against the '
                'latest version. Runs are the member configurations\' runs, evaluated from their '
                'integrity-checked records: constraints met, not_met or unresolved, objectives measured '
                'or unresolved, an unbound criterion unresolved. Reference marks label a configuration '
                'version as a baseline for its model; set and clear never change '
                'or pin it. A sampled '
                'version is generated only by a sampling operation (202, receipt category '
                'calculation_sample): seeded Latin hypercube points around '
                'reference configurations, '
                "in each input's saved units, frozen as configuration versions, then saved as the "
                "version's members; points of the latest sampled version that "
                'still fit are kept. A '
                'client may carry a sampled design unchanged into a new version. '
                'A run request submits '
                'ordinary runs for named members (receipt category run, one derived command per '
                'member) and never creates a version. An estimate (202, receipt category '
                'calculation_estimate) is fitted to exactly one sampled version '
                'and the latest recorded '
                'run of each point; its values are estimates, never calculated results. Receipt '
                'categories calculation_create, calculation_version and reference_mark; no other query '
                'fields are accepted.')
        elif path.endswith("/unit-catalog"):
            schema=ref("UnitCatalog2")
            op["description"]="Study-authorized finite physical guidance from the private model3 backend. Reauthorize after I/O; validate pinned source/catalog digests and the 16384-byte private response bound. No query fields, fallback catalog or browser-to-private access. Unsupported capability422; corrupt/outage503."
        elif path.endswith("/models"):
            schema=array(ref("Association")) if method=="get" else ref("ModelDraftRead5");status="200" if method=="get" else "201"
            if method=="post":op["requestBody"]["content"]["application/json"]["schema"]=ref("PublicNewModel")
        elif path.endswith("/model-imports"):schema=ref("ModelDraftRead5");status="201"
        elif "/models/" in path:
            if path.endswith("/assumption-evidence"):
                schema=ref("AssumptionEvidenceResolution1")
                op["description"]="Exactly one model_revision_id or draft_revision selector; no unknown or repeated query fields. Resolves only authorized exact same-study evidence. Returns unsupported_capability until coordinator resolution is implemented."
                for parameter in op["parameters"]:
                    if parameter["name"]=="model_revision_id":parameter["schema"]=uuid
                    elif parameter["name"]=="draft_revision":parameter["schema"]={"type":"string","minLength":1,"maxLength":4096,"pattern":r"\S"}
            elif path.endswith("/edits") or path.endswith("/preview"):
                op["requestBody"]["content"]["application/json"]["schema"]=ref("ApplyRead5" if path.endswith("/edits") else "PreviewRead5")
                schema=ref("ModelDraftRead5")
            elif path.endswith("/commits"):
                op["requestBody"]["content"]["application/json"]["schema"]=ref("Commit");schema=ref("ModelRevisionRead5")
            elif path.endswith("/validate"):
                op["requestBody"]["content"]["application/json"]["schema"]=ref("Validate");schema=ref("ValidationResult")
            elif path.endswith("/revisions"):
                schema={**array(ref("RevisionSummary")),"maxItems":100}
                for parameter in op["parameters"]:
                    if parameter["name"]=="limit":parameter["schema"]={"type":"integer","minimum":1,"maximum":100,"default":50}
                    elif parameter["name"]=="cursor":parameter["schema"]=uuid
                op["description"]="Immutable summaries in stored insertion order; cursor belongs to this authorized model. Unknown or repeated query fields are invalid."
            elif "/revisions/" in path:schema=ref("ModelRevisionRead5")
            elif path.endswith("/export"):schema=ref("ModelPackageRead5")
            else:schema=ref("ModelDraftRead5")
        elif path.endswith("/configurations/preview"):
            op["requestBody"]["content"]["application/json"]["schema"]=ref("PublicConfigurationRequest")
            schema=ref("PublicConfigurationPreview")
        elif path.endswith("/configuration-summaries"):
            schema=array(ref("ConfigurationSummary1"))
        elif path.endswith("/configurations"):
            schema=array(ref("FrozenConfigurationRead7")) if method=="get" else ref("FrozenConfigurationRead7");status="200" if method=="get" else "201"
            if method=='post':op['requestBody']['content']['application/json']['schema']=ref('PublicConfigurationCommit')
        elif path.endswith('/result-sources'):
            schema=ref('ResultSourcePage3')
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
        elif path.endswith('/source-inspection'):schema=ref('EvidenceSourceInspection1')
        elif "/evidence/" in path:schema=ref("EvidenceRecord")
        elif path.endswith('/modified-run-seed'):schema=ref('ModifiedRunSeedRead6')
        elif path.endswith("/runs"):
            schema=array(ref('RunHistoryItem2')) if method=='get' else ref('PublicRun');status='200' if method=='get' else '202'
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
        elif "/runs/" in path:schema=ref("PublicRunDetail2")
        else:raise ValueError(path)
        response=envelope(schema) if schema else None
        if response and method == 'get' and path.endswith(
            ('/exploration-requests','/exploration-designs','/exploration-samples','/exploration-surrogates')):
            response['properties']['next_cursor'] = nullable(uuid)
            response['required'].append('next_cursor')
        if path.endswith(('/edits', '/preview')) and '/models/' in path:
            response = ref('ModelDraftEditResponse5')
        op['responses'] = {
            str(code): {
                'description': 'Typed error; inspect outcome before retry',
                'content': {'application/json': {'schema': ref('Error')}},
            }
            for code in (400, 401, 403, 404, 409, 413, 422, 429, 500, 503)
        }
        paged = (
            path == '/studies'
            or path.endswith(('/models', '/configurations', '/configuration-summaries'))
            or path.endswith(('/runs', '/revisions', '/evidence'))
            or '/evidence-families/' in path
            and path.endswith('/versions')
        )
        # A calculation version's runs page carries its cursor inside data (CalculationRunPage1).
        if (
            response
            and method == 'get'
            and paged
            and '/approach' not in path
            and '/calculation-versions/' not in path
        ):
            response['properties']['next_cursor'] = nullable(
                {'type': 'string', 'maxLength': 2048} if '/evidence' in path else uuid
            )
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
            if path not in {"/session","/session/external"} or method!="post":
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
    for old in _PUBLIC_READ_SUCCESSORS:
        schemas['Previous'+old] = old_refs(schemas['Previous'+old])
    # Freeze predecessor links in both named successors and public compatibility aliases.
    # Otherwise a successor can reach itself through an upgraded predecessor alias,
    # making a valid new record satisfy two branches of a closed oneOf union.
    successors = {new: old_refs(copy.deepcopy(schemas[new]))
                  for new in set(_PUBLIC_READ_SUCCESSORS.values())}
    schemas.update(successors)
    for old, new in _PUBLIC_READ_SUCCESSORS.items():
        schemas[old] = copy.deepcopy(successors[new])
public_views()

# Additive domain aliases preserve immutable serialized schemas and receipt categories.
for old_path, operations in tuple(spec['paths'].items()):
    if '/calculation' not in old_path:
        continue
    path = old_path.replace('/calculations', '/analyses').replace('/calculation-', '/analysis-')
    current = copy.deepcopy(operations)
    for method, operation in current.items():
        operation['operationId'] = operation['operationId'].replace('calculation', 'analysis')
        operation['summary'] = operation.get('summary', '').replace('Calculation', 'Analysis')
        operation['description'] = (
            'Analysis API. Configuration and run records remain independently addressable. '
            'Legacy calculation_* payload keys denote analysis identities and are preserved '
            'for immutable records and command receipts. '
            + operation.get('description', '')
        )
        operations[method]['deprecated'] = True
    spec['paths'][path] = current

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, default=ROOT / 'contracts/hyprn-mvp.openapi.yaml')
parser.parse_args().output.write_text(json.dumps(spec,indent=2)+"\n")
