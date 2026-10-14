"""UI contract check: source wiring, public route and type bindings, and named control mappings.

Stdlib only; reads the UI sources, the public contract (contracts/hyprn-mvp.openapi.yaml) and
ui/control-map.json. Every control in the map names a browser spec under ui/tests and text that
a test title in that spec must contain; a missing spec or test fails the check. These are
source guards: they never certify behaviour, which only the browser groups running the specs
prove.

Run: python3 ui/check_ui_contract.py
"""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parent
checks = {
    'src/ResultPicker.tsx': ['resultSourcesPage', 'Load more', 'Unnamed model', 'outcomes.criteria', 'outcomes.execution', '<RunOutcomes outcomes={resultOutcomes('],
    'src/ConfigurationPanel.tsx': ['previewConfiguration2', 'commitConfiguration2', 'expected_preview_digest', 'result_binding', 'Enter a value instead', 'onViewSourceResult', 'Check original configuration command', 'Review modified run', 'choice_confirmed:true', 'seed?.configuration.derivation', 'seed?.configuration.numerical', 'RuntimeComparisonView'],
    'src/Workspace.tsx': ['setModified({seed,source})'],
    'src/views/runs.tsx': ['onViewSourceResult', 'Return to configuration',
                           'onCreateModified={createModified}'],
    'src/ConfigurationRecord.tsx': ['result_binding', 'derivation', 'onViewSourceResult', 'binding.source_output', 'Uses result from'],
    'src/RecordedConfiguration.tsx': ['<ConfigurationRecord onViewSourceResult={onViewSourceResult}'],
    'src/RunPanel.tsx': ['<ConfigurationRecord onViewSourceResult={onViewSourceResult}', 'data-source-output', 'button?.focus()', 'api.modifiedRunSeed', 'Create modified run', 'detail?.runtime_comparison'],
    'src/api.ts': ['result-sources', 'ConfigurationRequest2', 'ConfigurationCommit2', 'ModifiedRunSeed1', 'modified-run-seed'],
}
checks['src/ConfigurationPanel.tsx'] += ['prepared_bundle', 'executor_observation', 'comparison.current.image_digest', 'comparison.source.image_digest']
checks['src/contract.ts'] = ['ModifiedRunSeed1', 'ConfigurationCommit2', 'DerivationRequest', 'RuntimeComparison']
checks['src/ComputationalExportDialog.tsx'] = ['previewComputationalRecord', 'createComputationalRecord', 'computationalRecord', 'downloadComputationalRecord', 'expected_preview_digest', 'Included computations', 'Configuration origins', 'preview.computational_ancestors', 'preview.derivation_context_only', 'Check original export command', 'clearTimeout(timer)', 'Details']
checks['src/RunPanel.tsx'] += ['<ComputationalExportDialog']
checks['src/api.ts'] += ['RecordPreviewRequest', 'RecordCreateRequest', 'computational-record-previews', 'computational_record_create', 'downloadComputationalRecord']
# Assumptions and evidence wiring; behaviour and browser zoom are proven by the browser groups.
checks['src/Assumptions.tsx'] = ['ownerKey', 'evidence_links', 'Statement', 'Apply assumption', 'Keep assumption', 'No evidence linked', 'EvidencePicker', 'onUnavailable']
checks['src/ConfigurationPanel.tsx'] += ['ConfigurationRequest3', 'general_context_evidence_version_ids', 'assumptions:', 'commitConfiguration3', 'assumptionEvidence', 'This evidence reference could not be resolved.', 'Check original configuration command']
checks['src/RunPanel.tsx'] += ['RunEvidence', 'history.evidence', 'history.model_snapshot', 'retainedRunAssumptions(history, open)', '<EvidenceIndex', 'Input provenance', 'Criterion evidence', 'General context', 'configurationContext(configuration)', 'criterionOperators[criterion.operator]', '<RetainedFiles']
# A run's assumptions by owner (model, component, configuration, approach) live in the shared EvidenceIndex.
checks['src/EvidenceIndex.tsx'] = ['export function retainedRunAssumptions(', "label: 'Model'", "'Whole model'", "'Component · '", "label: 'Configuration'", "label: 'Modeling approach'", 'context.assumptions.items', 'modelAssumptions(model)', 'history.evidence', 'closure.evidence']
# The general context field is interpreted once, in recordViews.ts.
checks['src/recordViews.ts'] = ['c.general_context_evidence_version_ids', 'export function configurationContext(']
checks['src/ComparisonView.tsx'] = ['checkPackage(packageText)', '/model-imports', 'Preview model import', 'Download portable model record', 'expected_revision: preview.revision']
checks['src/exports.ts'] = ["value.schema_version === '1'", 'revision.schema_version', 'revision.parent_model_revision_id !== parent', 'Model version identity, parent or SHA-256 mismatch.', 'exactSource(source)', '2 * 1024 * 1024 - 512']
checks['src/contract.ts'] += ['ModelRevision2', 'ModelPackage2', 'ConfigurationRequest3', 'ModifiedRunSeed2', 'ExecutionBundle4', 'RunHistory2', 'AssumptionEvidenceLink']
run_evidence = (ROOT/'src/RunPanel.tsx').read_text().split('function RunEvidence(',1)[1].split('export function RunPanel(',1)[0]
for forbidden in ('api.', 'evidenceFamily(', 'assumptionEvidence(', 'useEffect(', 'fetch(', 'new HyprnMvpApi'):
    assert forbidden not in run_evidence, ('Retained evidence must not resolve live content', forbidden)
assert 'records={records}' in run_evidence
# The run's assumptions index is projected from the retained history only.
retained_index = (ROOT/'src/EvidenceIndex.tsx').read_text().split('export function retainedRunAssumptions(',1)[1].split('function OwnerGroup(',1)[0]
for forbidden in ('api.', 'evidenceFamily(', 'assumptionEvidence(', 'useEffect(', 'fetch(', 'HyprnMvpApi'):
    assert forbidden not in retained_index, ('Retained run assumptions must not resolve live content', forbidden)

missing = [f'{path}: {text}' for path, texts in checks.items() for text in texts if not (ROOT / path).is_file() or text not in (ROOT / path).read_text()]
if missing:
    raise SystemExit('Missing result-binding, modified-run, record-export and evidence wiring:\n' + '\n'.join(missing))
spec=json.loads((ROOT.parent/'contracts/hyprn-mvp.openapi.yaml').read_text())
routes={
    '/studies/{study_id}/result-sources':('get','ResultSourcePage'),
    '/studies/{study_id}/runs/{run_id}/modified-run-seed':('get','ModifiedRunSeedRead6'),
    '/studies/{study_id}/computational-record-previews':('post','RecordRequest'),
    '/studies/{study_id}/computational-records':('post','RecordRequest'),
    '/studies/{study_id}/computational-records/{request_id}':('get','RecordRequest'),
}
for path,(method,kind) in routes.items():
    operation=spec['paths'][path][method]
    success=operation['responses']['202' if method=='post' else '200']
    assert kind in json.dumps(success),(path,kind)
    assert kind in (ROOT/'src/contract.ts').read_text()
assert 'application/zip' in spec['paths']['/studies/{study_id}/computational-records/{request_id}/download']['get']['responses']['200']['content']
print(f'Result-binding, modified-run, record-export and evidence wiring: {sum(map(len, checks.values()))} checks passed (behaviour requires ui-a, ui-b, ui-c and ae-ui)')
print('Result-source, modified-run seed and record-export public routes and types: 6 checks passed')
# Study archive routes and types in the public contract and the generated UI types.
for action in ('archive','restore'):
    operation=spec['paths']['/studies/{study_id}/'+action]['post']
    assert operation['requestBody']['content']['application/json']['schema']=={'$ref':'#/components/schemas/StudyArchiveCommand'},action
    assert '#/components/schemas/Study"' in json.dumps(operation['responses']['200']),action
assert any(p['name']=='archived' and p['schema']=={'enum':['true','false'],'default':'false'} for p in spec['paths']['/studies']['get']['parameters'])
contract_text=(ROOT/'src/contract.ts').read_text()
assert 'export type StudyArchiveCommand = { "command_id": string };' in contract_text
assert '"boundary": string; "archived"?: boolean };' in contract_text
print('Study archive public routes/types: 2 commands, listing filter and optional Study.archived bound')


# Approach wiring. Wiring declarations are not behavioural evidence; the approach browser
# groups and native groups prove behaviour.
approach_checks={
 'src/ApproachFindings.tsx':['retained_integrity','resolvedUnit','groupFindings','sourceMatch','this.active < 2','.slice(0,10)','Retry usage page','Upstream record unavailable','More usage is available'],
 'src/ApproachController.tsx':['previewApproach','saveApproachDraft','saveApproachVersion','restoreApproach','approachReceipt'],
 'src/ApproachPanel.tsx':['ApproachReader','ApproachFindings','RecordBar','Review latest draft'],
 'src/ApproachMethod.tsx':['implementation_refs','connection_id','<ModelView'],  # a method step's model opens in the canonical model view
 'src/ApproachAssumptions.tsx':['origin','assumption_refs','evidence_links'],
 'src/ConfigurationApproach.tsx':['case_id','approach_version_id'],
 'src/ComputationalExportDialog.tsx':['approach_summary','basis_run_ids','basis_configuration_ids'],
 'src/contract.ts':['ApproachSaved1','ConfigurationRequest4','RunHistory3','RecordRequest2'],
}
# Results-first review and version-qualified case navigation wiring. The
# @approach-history / @approach-configuration browser groups prove behaviour.
approach_checks['src/ApproachFindings.tsx']+=['No study answer has been assessed.','function CaseCard(','Remaining method work','Study limits','All usage loaded','Not evaluated in the loaded review']  # one card per case; study limits are a link
approach_checks['src/ApproachPanel.tsx']+=['CaseNavigation.Provider value={null}','ApproachResultsSlot']
approach_checks['src/ConfigurationApproach.tsx']+=['CaseContextLink','No specific case']
approach_checks['src/RunPanel.tsx']=['case_context','Run case','Case context unavailable','Retry case context','No modeling approach','CaseNavigation.Provider value={null}']
# The run's model-assumption interpretation lives with the run's assumptions in EvidenceIndex.
approach_checks['src/EvidenceIndex.tsx']=['modelAssumptions(model)','recordLimitations.modelAssumptionsNotInFormat','recordLimitations.modelAssumptionsUnreadable','No modeling approach is linked.']
# Model-assumption format interpretation and its wording live in recordViews.ts.
approach_checks['src/recordViews.ts']=['export function modelAssumptions(',"kind: 'not_in_format'","kind: 'unsupported'","kind: 'invalid'",'Model versions saved in this older format have no assumptions.','This application cannot read assumptions from this model version format.']
approach_checks['src/workspaceModel.ts']=['CaseNavigation']
approach_checks['src/views/approach.tsx']=["query.get('case')",
                                         'This case link does not name an approach version.']
approach_checks['src/Workspace.tsx']=['CaseNavigation.Provider value={openCase}','focusWhenReady','runFilters','requestedCase']
approach_checks['src/contract.ts']+=['RunCaseContext1','"case_context"?: RunCaseContext1']
for file,terms in approach_checks.items():
 text=(ROOT/file).read_text()
 for term in terms:assert term in text,(file,term)
# Retained Earlier work closures never navigate to current
# case usage; approach tab panels are named by their tabs; case-link accessible
# names start with their visible text (WCAG 2.5.3).
basis_text=(ROOT/'src/ApproachMethod.tsx').read_text().split('export function ApproachBasis(',1)[1]
assert 'CaseNavigation.Provider value={null}' in basis_text,'ApproachBasis must suppress live case navigation'
for file in ('src/ApproachPanel.tsx','src/ApproachMethod.tsx'):
 text=(ROOT/file).read_text()
 assert 'tabId:' in text and text.count('role="tabpanel"')<=text.count('aria-labelledby='),(file,'Approach tab panels must be named by their tabs')
for file,label in (('src/ApproachFindings.tsx','View results for case'),('src/RunPanel.tsx','`View case ${value.linked.name}'),('src/ConfigurationApproach.tsx','`View case ${caseLabel}')):
 assert label not in (ROOT/file).read_text(),(file,'Accessible name must start with the visible label')
# No fabricated study verdicts or pooled pass rates in the results review.
findings_text=(ROOT/'src/ApproachFindings.tsx').read_text()
for forbidden in ('Partial answer','Mixed evidence','success rate','pass rate'):
 assert forbidden not in findings_text,('Results review must not fabricate an assessment',forbidden)
# Historical readers stay closure-only: no usage reads or live case navigation.
reader_text=(ROOT/'src/ApproachPanel.tsx').read_text().split('export function ApproachReader(',1)[1].split('export function ApproachPanel(',1)[0]
for forbidden in ('approachUsage(','api.run(','api.configuration('):
 assert forbidden not in reader_text,('Historical ApproachReader must remain closure-only',forbidden)
# These display components read versioned records through recordViews.ts (approach content
# through api.ts descriptiveApproach) instead of branching on wire versions, so every reader
# interprets every record format the same way. Command producers, api.ts and exports.ts keep
# explicit versions and are not listed. Exemptions are exact and must still exist.
display_readers={'src/ConfigurationRecord.tsx':(),'src/ChangePreview.tsx':(),'src/ApproachPanel.tsx':(),'src/ApproachAssumptions.tsx':(),'src/EvidenceIndex.tsx':(),
 'src/RunPanel.tsx':("map.schema_version !== '1'",),  # retained source-mapping admission, not record presentation
 'src/EvidencePanel.tsx':("evidence_schema_version: '3'",)}  # EvidenceCreate3 command
for file,exempt in display_readers.items():
 text=(ROOT/file).read_text()
 for token in exempt:assert text.count(token)==1,(file,'Stale exemption',token);text=text.replace(token,'')
 for pattern in ('schema_version',"'assumptions' in"):assert pattern not in text,(file,'Read versioned records through recordViews.ts',pattern)
panel=(ROOT/'src/ConfigurationPanel.tsx').read_text()
request_choice="!seed && (snapshot.schema_version === '2' || snapshot.schema_version === '3' || snapshot.schema_version === '4')"  # command: request version
assert panel.count(request_choice)==1,('src/ConfigurationPanel.tsx','Stale exemption',request_choice);panel=panel.replace(request_choice,'')
for pattern in ('snapshot.schema_version','binding.schema_version','config.schema_version','c.schema_version'):assert pattern not in panel,('src/ConfigurationPanel.tsx','Read versioned records through recordViews.ts',pattern)
approach_routes=[('','get','ApproachState2','200'),('/preview','post','ApproachPreviewRead3','200'),('/draft','post','ApproachDraftRead2','200'),('/versions','post','ApproachVersionSavedRead3','201'),('/versions','get','ApproachVersionPage2','200'),('/versions/{version_id}','get','ApproachSavedRead3','200'),('/versions/{version_id}/usage','get','ApproachUsagePage1','200'),('/draft/restore','post','ApproachDraftRead2','200')]
for suffix,method,kind,status in approach_routes:
 response=spec['paths']['/studies/{study_id}/approach'+suffix][method]['responses'][status]
 assert kind in json.dumps(response),(suffix,kind)
print('Approach wiring and eight route/type bindings present; actual browser and native passes are required separately.')


# Units: shared meaning, exact active-version resolution and the public route.
unit_checks = {
 'src/unitLabels.ts': ['Not specified', 'Dimensionless', 'resolvedUnit', 'instance.definition_version_id', 'catalog.supported_units.find'],
 'src/UnitEditor.tsx': ['api.unitCatalog', 'abort.signal', 'Retry unit guidance'],
 'src/views/model.tsx': ["schema_version:'3'", 'unresolvedModelUnits', 'Units incomplete',
                         'View quantity'],
 'src/ConfigurationPanel.tsx': ['UnitEditor', 'unitDeclaration', 'resolvedUnit', 'previewConfiguration4', 'commitConfiguration4'],
 'src/contract.ts': ['UnitCatalog1', 'UnitDeclaration1', 'ModelRevision3', 'ModifiedRunSeed4', 'RunHistory4'],
 'src/exports.ts': ['unitLabel(r.port.units)', 'Not recorded', 'unit_declarations/1'],
}
for path in ('VariablesTable.tsx','ChangePreview.tsx','ComparisonView.tsx','SelectionInspector.tsx','ApproachReferences.tsx','design/graph.tsx'):
 unit_checks['src/'+path]=['unitLabel']
for file,terms in unit_checks.items():
 text=(ROOT/file).read_text()
 for term in terms:assert term in text,(file,term)
unit_route=spec['paths']['/studies/{study_id}/unit-catalog']['get']
assert 'UnitCatalog1' in json.dumps(unit_route['responses']['200'])
native=(ROOT.parent/'deployment/tests/test_units_native.py').read_text()
assert 'browser=j.browser(records)' in native
print('Units shared labels, exact active-version resolution and public catalog route present; actual API, browser and native gates remain separate.')


# Workspace editor-guard seam. One guard shape and one ordered guard list in Workspace;
# new workflows add a list entry instead of editing the dirty aggregate, navigate(), the
# unsaved-changes dialog and clearEditor separately.
guard_shape=re.compile(r'\{\s*dirty:\s*boolean;\s*save:\s*\(\)\s*=>\s*Promise<boolean>;\s*discard:\s*\(\)\s*=>\s*void\s*[;}]')
declarations={str(path.relative_to(ROOT)):count for path in sorted((ROOT/'src').rglob('*.ts*')) if (count:=len(guard_shape.findall(path.read_text())))}
assert declarations=={'src/workspaceModel.ts':1},('One EditorGuard shape',declarations)
assert 'export type EditorGuard = ' in (ROOT/'src/workspaceModel.ts').read_text()
workspace=(ROOT/'src/Workspace.tsx').read_text()
for term in ('guardsShown(guards)','guardsDirty(guards)','guardsBlocked(guards)','saveGuards(guards)','discardGuards(guards)','guards.forEach(guard => guard.reset?.())'):
 assert term in workspace,('Workspace guard list',term)
for duplicate in ('Handle.current.dirty ||','handle.current.dirty ||','Handle.current.discard();','Handle.current.save()'):
 assert duplicate not in workspace,('Hand-maintained guard enumeration',duplicate)
print('Workspace editor-guard seam: one EditorGuard shape and one ordered guard list; browser gates remain separate.')


# Run outcomes. Readers see only the facets the runtime computes today, Execution and
# Criteria, through one shared RunOutcomes rendering. The constant facets stay stored and
# exported; they are not projected or labelled in reader UI, and the two outcomes are never
# merged.
outcomes_text=(ROOT/'src/runStatus.tsx').read_text()
for term in ('export function RunOutcomes(','export function runOutcomes(','export function resultOutcomes(',"{ label: 'Execution',","{ label: 'Criteria',"):
 assert term in outcomes_text,('Shared run outcomes',term)
consumers={'src/RunPanel.tsx':'<RunOutcomes','src/OverviewRecords.tsx':'<RunOutcomes','src/ApproachFindings.tsx':'<RunOutcomes','src/ResultPicker.tsx':'<RunOutcomes'}
for file,term in consumers.items():
 text=(ROOT/file).read_text()
 assert term in text,(file,'Run outcomes must use the shared RunOutcomes')
 assert '<Ledger' not in text and 'hf-run-summary' not in text,(file,'Second rendering of run outcomes')
 for removed in ('Convergence','Termination','Feasibility','Sample completeness','Output completeness','Applicability','applicability','results.convergence','results.optimization'):
  assert removed not in text,(file,'Constant facet shown to readers',removed)
run_text=(ROOT/'src/RunPanel.tsx').read_text()
for removed in ('hf-display-note','Display: up to 3 decimals','source={','RetainedStudyConditions','Assessment evaluator','Read-only retained inputs'):
 assert removed not in run_text,('src/RunPanel.tsx','Removed run page element',removed)
for file,removed in (('src/ConfigurationRecord.tsx','numerical.mode'),('src/ConfigurationRecord.tsx','numerical.derivatives'),('src/RecordedConfiguration.tsx','Deterministic scalar'),('src/ConfigurationApproach.tsx','StudyConditions')):
 assert removed not in (ROOT/file).read_text(),(file,'Removed run/configuration element',removed)
print('Run outcomes: one shared RunOutcomes (Execution and Criteria) in 4 readers, constant facets and removed run-page elements absent; browser gates remain separate.')


# Access-loss session seam. One client-only seam in api.ts: fence()
# (actor, CSRF session, session epoch, study access epoch; no dialog generation),
# readFailed() (one reconciled denial set, concealed 404 confirmed by one shared study
# probe, probe failure transient) and onSessionChange (signed-out, signed-in, access-lost).
# Protected-content hosts use it instead of their own denial lists or study probes.
seam_text=(ROOT/'src/api.ts').read_text()
for term in ("export const accessDeniedCodes: readonly string[] = ['unauthenticated', 'unauthorized', 'forbidden'];",'onSessionChange(listener: (change: SessionChange) => void)','fence(scope: { studyId?: string } = {}): ReadFence','async readFailed(error: unknown, fence: ReadFence','async confirmAccess(fence: ReadFence',"this.emit({ kind: 'signed-out' });","{ kind: 'access-lost'; studyId: string }"):
 assert term in seam_text,('Session seam',term)
seam_hosts={'src/ConfigurationApproach.tsx':'useAccessLoss(','src/ConfigurationPanel.tsx':'useAccessLoss(','src/RecordedConfiguration.tsx':'useAccessLoss(','src/executionReadiness.ts':'useAccessLoss(',
 'src/RunPanel.tsx':'useAccessLoss(','src/ApproachPanel.tsx':'useAccessLoss(','src/ApproachFindings.tsx':'useAccessLoss(','src/ApproachAssumptions.tsx':'api.readFailed(','src/ApproachController.tsx':'this.api.readFailed('}
for file,term in seam_hosts.items():
 text=(ROOT/file).read_text()
 assert term in text,(file,'Protected-content host must use the shared session seam')
 for duplicated in ("'unauthorized'","'unauthenticated'",'checkStudyAccess(token:number){\n    if(accessProbe'):
  assert duplicated not in text,(file,'Duplicated denial classification',duplicated)
 probes=text.count('api.study(')
 assert probes==(1 if file=='src/ApproachController.tsx' else 0),(file,'Study probes belong to api.confirmAccess',probes)
workspace_text=(ROOT/'src/Workspace.tsx').read_text()
assert 'requestedCaseRef' not in workspace_text,('src/Workspace.tsx','Dead requestedCaseRef')
for term in ('setCaseReturn(null); setRunFilters(emptyRunFilters); setRequestedCase(undefined);','forgetApproachReading();'):
 assert term in workspace_text,('src/Workspace.tsx','clearSession must reset',term)
assert 'export function forgetMethodViews(' in (ROOT/'src/ApproachMethod.tsx').read_text() and 'export function forgetApproachReading(' in (ROOT/'src/ApproachPanel.tsx').read_text(),'Reading positions must be forgettable'
print('Session seam: one fence/readFailed/onSessionChange in api.ts, 9 protected-content hosts on it without duplicated denial lists or probes, session reset of return state and reading positions; browser gates remain separate.')


# One assumption concept: an assumption is a statement plus
# evidence rows, rendered by the shared Assumptions list with one empty state and no owner
# line. Component, definition and configuration notes are neither shown nor authored in the
# UI; stored annotations/notes, command payloads and exports are unchanged. A configuration
# shows one line linking to its model's assumptions instead of repeating them.
list_text=(ROOT/'src/Assumptions.tsx').read_text()
for term in ('No assumptions</p>','assumption-evidence','relation={'):
 assert term in list_text,('src/Assumptions.tsx','Shared assumption list',term)
for removed in ('No assumptions recorded','Add approach assumption','Approach-owned','showHeading&&<p>{ownerLabel}</p>'):
 assert removed not in list_text,('src/Assumptions.tsx','Removed assumption list element',removed)
notes_free={'src/ModelEditor.tsx':('Component notes','Definition notes','title="Notes"','set_annotation','.annotations'),
 'src/SelectionInspector.tsx':('Notes</h3>','Definition notes','No recorded notes','.annotations'),
 'src/ConfigurationPanel.tsx':('Configuration notes','draft.notes','notes: draft.'),
 'src/ConfigurationRecord.tsx':('context_snapshot.notes','Model assumptions · read-only','ModelConfigurationAssumptions'),
 'src/RunPanel.tsx':('No assumptions recorded',),
 'src/ChangePreview.tsx':('· notes','.annotations'),
 'src/ComparisonView.tsx':('Notes and boundary','annotations','model-notes')}
for file,removed_terms in notes_free.items():
 text=(ROOT/file).read_text()
 for removed in removed_terms:assert removed not in text,(file,'Removed notes or repeated model assumptions',removed)
panel_text=(ROOT/'src/ConfigurationPanel.tsx').read_text()
assert 'notes: value.originalNotes' in panel_text,('src/ConfigurationPanel.tsx','Inherited notes must pass through unchanged')
record_text=(ROOT/'src/ConfigurationRecord.tsx').read_text()
for term in ('export function ModelAssumptionsLink(','Model assumptions: ','label="View model assumptions"','modelAssumptions(model)'):
 assert term in record_text,('src/ConfigurationRecord.tsx','Model assumptions link',term)
assert '<ModelAssumptionsLink' in panel_text,('src/ConfigurationPanel.tsx','Draft uses the model assumptions link')
inspector_text=(ROOT/'src/SelectionInspector.tsx').read_text()
for pattern in ('schema_version',"'assumptions' in"):assert pattern not in inspector_text,('src/SelectionInspector.tsx','Read versioned records through recordViews.ts',pattern)
print('Assumptions: one shared list (statement + evidence rows, "No assumptions", no owner line), notes absent from 7 readers/editors with inherited notes passed through, configuration model-assumptions link; browser gates remain separate.')

# Canonical model view. One ModelView everywhere a model is shown:
# Graph | XDSM on top, Details beside the canvas (What it computes · Why · Assumptions; nothing
# selected → the model and its assumptions), and one quantities table below. No inspector ports
# table, no incoming/outgoing lists, no Variables tab and no separate model-assumption dialogs.
view_text=(ROOT/'src/ModelView.tsx').read_text()
for term in ('export function ModelView(',"const views = ['Graph', 'XDSM'] as const",'<QuantitiesTable','<SelectionInspector','aria-label="Model view"'):
 assert term in view_text,('src/ModelView.tsx','Canonical model view',term)
assert "'Variables'" not in view_text,('src/ModelView.tsx','No Variables projection tab')
for file in ('src/views/model.tsx','src/ApproachMethod.tsx','src/ConfigurationRecord.tsx'):
 assert '<ModelView' in (ROOT/file).read_text(),(file,'Reuses the canonical model view')
inspector_text=(ROOT/'src/SelectionInspector.tsx').read_text()
for term in ('What it computes','>Why<','label="View source"','verifySource(','Shown as text; never run.','modelAssumptions(snapshot)'):
 assert term in inspector_text,('src/SelectionInspector.tsx','Details: what, why, assumptions',term)
removed_view={'src/SelectionInspector.tsx':('tiny-table','Incoming quantities','Outgoing quantities','DetailTabs','<DataTable'),
 'src/ModelEditor.tsx':('tiny-table','DetailTabs','<DataTable','title="Model assumptions"','{connections}','connections?: ReactNode'),
 'src/GraphView.tsx':('ConnectedViews','VariablesTable','SelectionInspector'),
 'src/Workspace.tsx':('View model assumptions','<summary>Model version record','Inspect recorded model','ConnectedViews'),
 'src/RunPanel.tsx':("'Models'",)}
# The study views render what the shell rendered; the shell's removed elements stay removed there.
for path in sorted((ROOT/'src'/'views').glob('*.tsx')):
 removed_view[str(path.relative_to(ROOT))]=removed_view['src/Workspace.tsx']
for file,terms in removed_view.items():
 text=(ROOT/file).read_text()
 for removed in terms:assert removed not in text,(file,'Removed by the canonical model view',removed)
assert "const tabs = ['Results', 'Model', 'Configuration', 'Evidence'] as const;" in (ROOT/'src/RunPanel.tsx').read_text(),'Run tab is "Model" (one version)'
table_text=(ROOT/'src/VariablesTable.tsx').read_text()
for term in ('export function QuantitiesTable(','Show all quantities','aria-label="Quantities table"','label="Quantities"',"'not computed'","'unassigned'","'computed when run'"):
 assert term in table_text,('src/VariablesTable.tsx','Quantities table',term)
assert 'export function variableRows(' in table_text,('src/VariablesTable.tsx','Export projection kept unchanged')
for file in ('src/ModelView.tsx','src/modelMethods.ts','src/VariablesTable.tsx','src/SelectionInspector.tsx'):
 text=(ROOT/file).read_text()
 for pattern in ('schema_version',"'assumptions' in"):assert pattern not in text,(file,'Read versioned records through recordViews.ts',pattern)
methods_text=(ROOT/'src/modelMethods.ts').read_text()
for term in ('referencedInstances(','configurationContext(','linkedApproach(','api.fence(','api.readFailed(','useAccessLoss('):
 assert term in methods_text,('src/modelMethods.ts','Exact method links, session-scoped reads',term)
model_view_text=(ROOT/'src/views/model.tsx').read_text()
for term in ('label="Record details"','title="Model version record"'):
 assert term in model_view_text,('src/views/model.tsx','Model version record in Record details')
print('Model view: one canonical ModelView (Graph | XDSM, Details what/why/assumptions, one quantities table) reused in Models, Run › Model, configuration and approach; ports table, incoming/outgoing lists, Variables tab and model-assumption dialogs absent; browser gates remain separate.')


# Approach page and Overview question box. One StudyQuestionBox on Overview and on the
# approach page; "See more details"
# opens one StudyDetailsDialog (question, current approach, assumptions, limits, open questions)
# for the
# exact content shown. Study conditions & limits, Question in detail and the Overview
# CurrentStudyConditions are gone. Methods: Explanation · Assumptions & evidence, one
# implementation line and the canonical model version; no Model & quantities tab, quantity cards
# or source excerpt. Cases & results: results first, then one card per case; the limits aside is
# a Study limits link.
details_text=(ROOT/'src/ApproachAssumptions.tsx').read_text()
for term in ('export function StudyQuestionBox(','export function StudyDetailsDialog(','export function OverviewStudyQuestion(','>See more details<','Study details</h2>',
 'aria-label="Study question"','aria-label="Current approach"','aria-label="Study assumptions"',
 'aria-label="Study limits"','aria-label="Open questions"',
 'api.fence({studyId})','api.readFailed(error,read)','useAccessLoss(api,studyId','Current saved approach v'):
 assert term in details_text,('src/ApproachAssumptions.tsx','Study question box and details',term)
for removed in ('export function StudyConditions(','StudyConditionsAction','CurrentStudyConditions','Study conditions & limits','Approach-owned',"'Model assumption'",'(read-only)`};'):
 assert removed not in details_text,('src/ApproachAssumptions.tsx','Removed by Study details',removed)
panel_text=(ROOT/'src/ApproachPanel.tsx').read_text()
for term in ('<StudyQuestionBox','<StudyDetailsDialog',"open('limits')",'onCreateConfiguration={createForCase}'):
 assert term in panel_text,('src/ApproachPanel.tsx','Shared question box',term)
for removed in ('Question in detail','StudyConditionsAction','conditionsHost','cases:casesPanel'):
 assert removed not in panel_text,('src/ApproachPanel.tsx','Removed approach element',removed)
method_text=(ROOT/'src/ApproachMethod.tsx').read_text()
for term in ("['explanation','Explanation'],['assumptions','Assumptions & evidence']","'Implemented in Model version '",'label="Open model version"','Edit definitions in model'):
 assert term in method_text,('src/ApproachMethod.tsx','Two-tab step explanation',term)
for removed in ('Model & quantities','QuantityCard','QuantityTable','ExactMethodSource','Source excerpt','View exact source','Inspect source and ports','Exact model element','title="Exact model version"','GraphView','method-quantity'):
 assert removed not in method_text,('src/ApproachMethod.tsx','Removed method step element',removed)
findings_s5=(ROOT/'src/ApproachFindings.tsx').read_text()
for term in ('function CaseCard(','Why this case','onStudyLimits','Create configuration for ','aria-label="Approach usage"','<RunOutcomes variant="inline"','<CriterionFacts run={run}/>'):
 assert term in findings_s5,('src/ApproachFindings.tsx','One card per case',term)
for removed in ('function ResultCard(','function StudyLimits(','Study-wide limits','View case results','Back to results','Cases and recorded runs','approach-result-limits','cases?:ReactNode'):
 assert removed not in findings_s5,('src/ApproachFindings.tsx','Removed duplicate case rendering',removed)
workspace_s5=(ROOT/'src/Workspace.tsx').read_text()
overview_s5=(ROOT/'src/views/overview.tsx').read_text()
assert '<OverviewStudyQuestion' in overview_s5,\
 ('src/views/overview.tsx','Overview question box replaces the conditions entry')
assert 'CurrentStudyConditions' not in workspace_s5+overview_s5,\
 ('src/views/overview.tsx','Overview question box replaces the conditions entry')
for path in sorted((ROOT/'src').rglob('*.tsx')):
 text=path.read_text()
 for removed in ('Study conditions & limits','Question in detail','StudyConditions'):
  assert removed not in text,(str(path),'Removed everywhere',removed)
for file,exempt in (('src/ApproachAssumptions.tsx',()),('src/ApproachFindings.tsx',("source.retained_integrity?.schema_version !== '1'",)),('src/ApproachMethod.tsx',())):
 text=(ROOT/file).read_text()
 for token in exempt:assert text.count(token)==1,(file,'Stale exemption',token);text=text.replace(token,'')  # retained-integrity admission, not record presentation
 assert 'schema_version' not in text,(file,'No new schema_version branch; read through recordViews.ts / descriptiveApproach')
print('Approach page: one study question box with See more details on Overview and the approach page, one Study details dialog (question, context, assumptions, limits), no Study conditions & limits or Question in detail; Methods in two tabs with one implementation line and the canonical model version; one card per case with a Study limits link; browser gates remain separate.')


# Evidence index. One shared EvidenceIndex lists assumptions by owner with their evidence: the Evidence
# page reads the current owners (latest saved approach version, model drafts, latest revision of each
# configuration family) two reads at a time through the session seam, with a partial state that never
# reports an unread owner as having no assumptions; Run › Evidence reads only the retained versions.
# Run artifact, modified-seed and export reads and the approach controller use the session seam.
index_text=(ROOT/'src/EvidenceIndex.tsx').read_text()
for term in ('export function EvidenceIndex(','export function useCurrentAssumptions(','limiter(2)','api.fence({ studyId })','api.readFailed(error, read)','useAccessLoss(api, studyId',
 'latest_version','api.approachVersion(','descriptiveApproach(','api.models(','api.model(','assumptionEvidence(','api.configurations(','record.configuration.configuration_id ?? record.configuration.configuration_revision_id',
 "kind: 'failed'","kind: 'limitation'",'Assumptions could not be loaded.','groups loaded','could not be listed','Groups that could not be loaded are left out; they are not shown as having no assumptions.','<Assumptions regionless'):
 assert term in index_text,('src/EvidenceIndex.tsx','Evidence index',term)
assert index_text.count("'No assumptions'")==0 and index_text.count('>No assumptions<')==1,('src/EvidenceIndex.tsx','"No assumptions" only for a loaded index without owners')
evidence_panel=(ROOT/'src/EvidencePanel.tsx').read_text()
for term in ('useCurrentAssumptions(api, studyId, onOpen)','<EvidenceIndex framed','aria-label="Evidence library"','title="Sources"','Sources and observations used in this study.','useAccessLoss(api, studyId'):
 assert term in evidence_panel,('src/EvidencePanel.tsx','Evidence page: assumptions index then sources',term)
assert 'Saved notes and references' not in evidence_panel and 'title="Saved evidence"' not in evidence_panel,('src/EvidencePanel.tsx','Replaced Evidence page copy')
assert 'onOpen={target => navigate(() => void openLink(target))} />}</div>' in \
 (ROOT/'src/views/evidence.tsx').read_text(),\
 ('src/views/evidence.tsx','Evidence page owner links use guarded navigation')
assert '<Assumptions regionless' not in (ROOT/'src/RunPanel.tsx').read_text() and 'function RunEvidence(' in run_text,('src/RunPanel.tsx','Run evidence renders through the shared index')
for file,terms in {'src/RunPanel.tsx':('api.artifact(studyId, selected, artifact, read.signal)','api.modifiedRunSeedRead(studyId, detail.run_id, read.signal)','Check modified run again'),
 'src/ComputationalExportDialog.tsx':('api.computationalRecord(studyId,record!.request_id,read.signal)','api.readFailed(failure,read)','useAccessLoss(api,studyId'),
 'src/api.ts':("throw new ApiError(value?.error ? { ...value.error, message: unavailable }",),
 'src/ApproachController.tsx':('this.api.onSessionChange(this.sessionChanged)','loseAccess = (studyId: string)','accessLost: true','if (this.state.accessLost) { this.clear(); return; }'),
 'src/ApproachPanel.tsx':('controller.loseAccess(studyId)','state.accessLost ? null :'),
 'src/Workspace.tsx':('approach.dispose()',)}.items():
 text=(ROOT/file).read_text()
 for term in terms:assert term in text,(file,'Session seam',term)
 assert "'unauthorized'" not in text and "'unauthenticated'" not in text or file=='src/api.ts',(file,'Duplicated denial classification')
assert (ROOT/'src/RunPanel.tsx').read_text().count('readFailed(')>=4,('src/RunPanel.tsx','Run list, run, artifact and seed reads classified by readFailed')
print('Evidence index: one shared EvidenceIndex (assumptions by owner, partial and denied states, never an implied "No assumptions") on the Evidence page with sources and in Run › Evidence from retained versions; run artifact/seed/export reads and the approach controller on the session seam; browser gates remain separate.')

# Home archive, Overview identities, study header and footer. Archive is a study-wide
# presentation command through the shared receipt path; Home reads both lists.
api_s6b=(ROOT/'src/api.ts').read_text()
for term in ("archivedStudies = () => this.list<Study>('/studies?archived=true');",
 "this.mutate<Study>(`/studies/${sid}/archive`, command, 'study_archive', sid)",
 "this.mutate<Study>(`/studies/${sid}/restore`, command, 'study_archive', sid)",'command: StudyArchiveCommand'):
 assert term in api_s6b,('src/api.ts','Study archive client',term)
workspace_s6b=(ROOT/'src/Workspace.tsx').read_text()
for term in ('Promise.all([api.studies(), api.archivedStudies()])','label="Study list"',"label: 'Studies'","label: 'Archived'",'label="Archived studies"','>Archived</StatusTag>',
 'aria-label={`Archive study ${s.name}`}','aria-label={`Restore study ${s.name}`}','It disappears from Home for everyone. Nothing is deleted; restore it from Archived.',
 '<Button data-safe-choice',"pending?.category === 'study_archive'",'.catch(archiveRefusal)',
 '<footer><a href="/ui/THIRD_PARTY_NOTICES.txt">Third-party software notices</a></footer>'):
 assert term in workspace_s6b,('src/Workspace.tsx','Home archive, study header and footer',term)
assert re.search(
 r'<div className="study-heading actions">\s*<h1>\{study.name\}</h1>\s*'
 r'\{studyCreator && <AttributionChip \{\.\.\.studyCreator\} />\}\s*</div>',
 workspace_s6b,
), ('src/Workspace.tsx', 'Study heading names the study then conditionally shows its creator')
for removed in ("'Study overview'",'Choose a study to continue your work.'):
 assert removed not in workspace_s6b,('src/Workspace.tsx','Removed shell element',removed)
overview_s6b=(ROOT/'src/OverviewRecords.tsx').read_text()
for removed in ('Exact run identities','Exact configuration identities','<Disclosure'):
 assert removed not in overview_s6b,('src/OverviewRecords.tsx','Full identities live in Record details',removed)
for term in ('{runLabel(run)} · {run.run_id.slice(0, 8)}','<RecentRunOutcome','Version {c.configuration_revision_id.slice(0, 8)} · read-only'):
 assert term in overview_s6b,('src/OverviewRecords.tsx','Recent record rows',term)
fixture_s6b=(ROOT.parent/'deployment/tests/approach_ui_fixture.py').read_text()
for term in ("/(archive|restore)', route)","self.path == '/fixture/reader'"):
 assert term in fixture_s6b,('deployment/tests/approach_ui_fixture.py','Archive commands and reader setup',term)
print('Home archive: Studies | Archived from two reads, quiet Archive with confirmation and Restore through study_archive commands; Overview without identity disclosures; study name shown once; one notices link; browser gates remain separate.')

# Plain-language names (design-system/Naming.md). Retired reader-facing phrases stay out of ui/src: implementation vocabulary, "package" outside a
# method package, "revision" for a saved version and "digest"/"SHA256" labels. Wire names, stored
# data and exported record formats are unchanged. Text guards only; browser gates prove behaviour.
retired=('Recorded outputs','Exact values','Exact recorded values','Exact output values','Recorded output values','Exact value: ','Retained files','retained artifact',
 'Scientific outcomes','Checking retained configuration','complete retained terminal run','View case context','Supporting evidence','No verified results are retained',
 'recorded model version is unavailable','recorded configuration is unavailable','Inspection package','Snapshot comparison','comparison snapshot','loaded snapshot','Create package','Download package','model package','Model package',
 'Prior scientific basis','prior basis','Recorded limitations (legacy text)','Retained with approach','Recorded modeling approach','No modeling approach was recorded',
 'Configuration revision','saved revision','recent revisions','Revision {','Variables CSV','Worker isolation','Bundle digest','Model digest','Configuration digest','Preview digest',
 'Package SHA256','SHA256 {','`SHA256','>SHA256<','owners loaded','Add a description of what you want to investigate.','does not record assumptions','not recorded','Not recorded<',
 'Source and ports are retained','Exact model version','exact saved version','All returned usage loaded for this review')
for path in sorted([*(ROOT/'src').glob('*.ts'),*(ROOT/'src').glob('*.tsx'),
                   *(ROOT/'src'/'design').glob('*.tsx'),*(ROOT/'src'/'views').glob('*.ts*')]):
 if path.name=='contract.ts':continue
 text=re.sub(r'(^|\s)//[^\n]*',r'\1',re.sub(r'/\*.*?\*/','',path.read_text(),flags=re.S))  # reader text, not comments
 for phrase in retired:
  assert phrase not in text,(str(path.relative_to(ROOT)),'Retired reader-facing phrase (design-system/Naming.md)',phrase)
for file,terms in {'src/runStatus.tsx':('label="Run status"',),'src/RunPanel.tsx':('title="Outputs"','label="Full-precision values"','Values at full precision.','title="Run files"','>View case</CaseContextLink>','<dt>Execution bundle SHA-256</dt>'),
 'src/ComputationalExportDialog.tsx':("'Create record export'","'Download record export'",'<h3>Computational record export</h3>'),'src/ComparisonView.tsx':('Download portable model record','label="Portable model record file"',"'Quantities CSV'"),
 'src/ApproachMethod.tsx':('<h3>Earlier work</h3>','>Add earlier work</Button>'),'src/OverviewRecords.tsx':('>Version {c.configuration_revision_id.slice(0, 8)} · read-only</StatusTag>',)}.items():
 text=(ROOT/file).read_text()
 for term in terms:assert term in text,(file,'Plain-language name (design-system/Naming.md)',term)
assert 'evaluation?: {' in (ROOT/'src/design/primitives.tsx').read_text() and 'assessment' not in (ROOT/'src/design/primitives.tsx').read_text(),('src/design/primitives.tsx','CriterionRecord takes a criterion evaluation, not an assessment')
print(f'Plain-language names: {len(retired)} retired reader-facing phrases absent from ui/src; run, export, portable model record, earlier work and configuration version names present (design-system/Naming.md); browser gates remain separate.')


# Named controls: each maps to a browser spec test that must exist. The map is the single list
# of named controls; a control without its spec or test fails, never passes silently.
TEST_TITLE = re.compile(r"""\btest(?:\.(?:only|skip|fixme|fail|slow))?\(\s*(['"`])(.*?)(?<!\\)\1""", re.S)
control_map = json.loads((ROOT / 'control-map.json').read_text(encoding='utf-8'))
controls = control_map['controls']
assert isinstance(controls, dict) and controls, 'ui/control-map.json names no control'
titles = {}
missing_controls = []
for identifier, control in controls.items():
    assert re.fullmatch(r'[a-z]+(?:-[a-z]+)*-\d{2}', identifier), ('Control identifier', identifier)
    assert set(control) == {'spec', 'test'} and all(isinstance(v, str) and v for v in control.values()), (identifier, control)
    spec = ROOT / 'tests' / control['spec']
    if not (control['spec'].endswith('.spec.ts') and '/' not in control['spec'] and spec.is_file()):
        missing_controls.append(f"{identifier}: spec ui/tests/{control['spec']} is missing")
        continue
    if spec not in titles:
        titles[spec] = [m.group(2) for m in TEST_TITLE.finditer(spec.read_text(encoding='utf-8'))]
    if not any(control['test'] in title for title in titles[spec]):
        missing_controls.append(f"{identifier}: no test in ui/tests/{control['spec']} is titled with '{control['test']}'")
if missing_controls:
    raise SystemExit('Named controls without a spec test:\n' + '\n'.join(missing_controls))
areas = sorted({identifier.rsplit('-', 1)[0] for identifier in controls})
print(f'Named controls: {len(controls)} controls in {len(areas)} areas ({", ".join(areas)}) each map to an existing spec test; browser gates prove behaviour.')
