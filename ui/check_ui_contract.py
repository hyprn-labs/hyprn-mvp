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


def has(source, fragment):
    """Source-wiring checks ignore formatting; browser checks establish behavior."""
    clean = lambda value: re.sub(r'\(([A-Za-z_$][\w$]*)\)=>', r'\1=>', re.sub(r',(?=[}\]])', '', re.sub(r'\s+', '', value)))
    return clean(fragment) in clean(source)

checks = {
    'src/ResultPicker.tsx': [
        'resultSourcesPage', '<CollectionStatus', 'collection.more()', 'Unnamed model',
        'outcomes.criteria', 'outcomes.execution', '<RunOutcomes outcomes={resultOutcomes(',
    ],
    'src/ConfigurationPanel.tsx': ['previewConfiguration6', 'commitConfiguration6', 'expected_preview_digest', 'result_binding', 'Enter a value instead', 'onViewSourceResult', 'Check original configuration command', 'Review modified run', 'choice_confirmed:true', 'seed?.configuration.derivation', 'seed?.configuration.numerical', 'RuntimeComparisonView'],
    'src/Workspace.tsx': ['setModified({seed,source})'],
    'src/views/runs.tsx': ['onViewSourceResult', 'Return to configuration',
                           'onCreateModified={createModified}'],
    'src/ConfigurationRecord.tsx': [
        'result_binding', 'ConfigurationRecordDetails', 'onViewSourceResult',
        'binding.source_output', 'Uses result from',
    ],
    'src/RecordedConfiguration.tsx': ['<ConfigurationRecord onViewSourceResult={onViewSourceResult}'],
    'src/RunPanel.tsx': ['<ConfigurationRecord onViewSourceResult={onViewSourceResult}', 'data-source-output', 'button?.focus()', 'modifiedRunSeed', 'Create modified run', 'detail?.runtime_comparison'],
    'src/api.ts': ['result-sources', 'ConfigurationRequest6', 'ConfigurationCommit6', 'ModifiedRunSeed1', 'modified-run-seed'],
}
checks['src/ConfigurationPanel.tsx'] += ['prepared_bundle', 'executor_observation', 'comparison.current.image_digest', 'comparison.source.image_digest']
checks['src/contract.ts'] = ['ModifiedRunSeed1', 'ConfigurationCommit2', 'DerivationRequest', 'RuntimeComparison']
checks['src/ComputationalExportDialog.tsx'] = ['previewComputationalRecord', 'createComputationalRecord', 'computationalRecord', 'downloadComputationalRecord', 'expected_preview_digest', 'Export contents', 'Input history', 'preview.computational_ancestors', 'preview.derivation_context_only', 'Check original export command', 'clearTimeout(timer)', 'Details']
checks['src/RunPanel.tsx'] += ['<ComputationalExportDialog']
checks['src/api.ts'] += ['RecordPreviewRequest', 'RecordCreateRequest', 'computational-record-previews', 'computational_record_create', 'downloadComputationalRecord']
# Assumptions and evidence wiring; behaviour and browser zoom are proven by the browser groups.
checks['src/Assumptions.tsx'] = ['ownerKey', 'evidence_links', 'Statement', 'Apply assumption', 'Keep assumption', 'No evidence linked', 'EvidencePicker', 'onUnavailable']
checks['src/ConfigurationPanel.tsx'] += ['ConfigurationRequest6', 'general_context_evidence_version_ids', 'assumptions:', 'commitConfiguration6', 'assumptionEvidence', 'This evidence reference could not be resolved.', 'Check original configuration command']
checks['src/RunPanel.tsx'] += ['history.model_snapshot', '<ConfigurationRecord', 'detail?.execution_summary?.duration_seconds']
# Current assumptions by owner (model, component, configuration, approach) live in the shared EvidenceIndex.
checks['src/EvidenceIndex.tsx'] = ["'Whole model'", "'Component · '", "label: 'Study brief'", 'context.assumptions.items', 'latest.content.assumptions']
# The general context field is interpreted once, in recordViews.ts.
checks['src/recordViews.ts'] = ['c.general_context_evidence_version_ids', 'export function configurationContext(']
checks['src/ComparisonView.tsx'] = ['checkPackage(packageText)', '/model-imports', 'Preview model import', 'Download portable model record', 'expected_revision: preview.revision']
checks['src/exports.ts'] = ["value.schema_version === '1'", 'revision.schema_version', 'revision.parent_model_revision_id !== parent', 'Model version identity, parent or SHA-256 mismatch.', 'exactSource(source)', '2 * 1024 * 1024 - 512']
checks['src/contract.ts'] += ['ModelRevision2', 'ModelPackage2', 'ConfigurationRequest3', 'ModifiedRunSeed2', 'ExecutionBundle4', 'RunHistory2', 'AssumptionEvidenceLink']
# Saved evidence reads beside its owning configuration assertion without live fetching.
configuration_record = (ROOT / 'src/ConfigurationRecord.tsx').read_text()
for forbidden in ('api.', 'evidenceFamily(', 'assumptionEvidence(', 'fetch('):
    assert forbidden not in configuration_record, (
        'Saved evidence must not resolve live content',
        forbidden,
    )
assert 'records={c.evidence_snapshots}' in configuration_record

# JSX line wrapping does not change the required source-result binding.
missing = [
    f'{path}: {text}'
    for path, texts in checks.items()
    for text in texts
    if not (ROOT / path).is_file()
    or not has((ROOT / path).read_text(), text)
]
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


# The retired approach is not a client destination or public authoring route.
for file in ('src/ApproachPanel.tsx', 'src/ApproachController.tsx', 'src/AnswerExplorer.tsx'):
 assert not (ROOT/file).exists(), ('Retired owner remains', file)
assert not any('/approach' in path or '/exploration-' in path for path in spec['paths'])
for file, terms in {
 'src/StudyBrief.tsx': ('Study brief', 'controller.save'),
 'src/StudyAnswer.tsx': ('CalculationExplorer', 'AnswerExplorationBasis', 'controller.save'),
 'src/CalculationExplorer.tsx': ('predictCalculation', 'sameInputVector', 'ResponseCurve',
   'selection_token', 'Expand model' if False else 'onExpand'),
 'src/ModelExplanation.tsx': ('ModelExplanation', 'modelExplanation'),
}.items():
 text=(ROOT/file).read_text()
 for term in terms: assert has(text, term), (file,term)
# These display components read versioned records through recordViews.ts (approach content
# through api.ts descriptiveApproach) instead of branching on wire versions, so every reader
# interprets every record format the same way. Command producers, api.ts and exports.ts keep
# explicit versions and are not listed. Exemptions are exact and must still exist.
display_readers={'src/ConfigurationRecord.tsx':(),'src/ChangePreview.tsx':(),'src/EvidenceIndex.tsx':(),
 'src/EvidencePanel.tsx':("evidence_schema_version: '3'",)}  # EvidenceCreate3 command
for file,exempt in display_readers.items():
 text=(ROOT/file).read_text()
 for token in exempt:assert text.count(token)==1,(file,'Stale exemption',token);text=text.replace(token,'')
 for pattern in ('schema_version',"'assumptions' in"):assert pattern not in text,(file,'Read versioned records through recordViews.ts',pattern)
panel=re.sub(r'\s+', '', (ROOT/'src/ConfigurationPanel.tsx').read_text())
for pattern in ('snapshot.schema_version','binding.schema_version','config.schema_version','c.schema_version'):assert pattern not in panel,('src/ConfigurationPanel.tsx','Read versioned records through recordViews.ts',pattern)
# Units: shared meaning, exact active-version resolution and the public route.
unit_checks = {
 'src/unitLabels.ts': ['Not specified', 'Dimensionless', 'resolvedUnit', 'instance.definition_version_id', 'catalog.supported_units.find'],
 'src/UnitEditor.tsx': ['api.unitCatalog', 'abort.signal', 'Retry unit guidance'],
 'src/views/model.tsx': ["schema_version:'3'", 'unresolvedModelUnits', 'Units incomplete',
                         'View quantity'],
 'src/ConfigurationPanel.tsx': ['UnitEditor', 'unitDeclaration', 'resolvedUnit', 'previewConfiguration6', 'commitConfiguration6'],
 'src/contract.ts': ['UnitCatalog1', 'UnitDeclaration1', 'ModelRevision3',
                     'ModifiedRunSeed4', 'RunHistory4', 'UnitCatalog2', 'UnitDeclaration2',
                     'ModelRevision5', 'ModifiedRunSeed9', 'RunHistory9'],
 'src/exports.ts': ['unitLabel(r.port.units)', 'Not recorded', 'unit_declarations/1'],
}
for path in ('VariablesTable.tsx','ChangePreview.tsx','SelectionInspector.tsx','design/graph.tsx'):
 unit_checks['src/'+path]=['unitLabel']
for file,terms in unit_checks.items():
 text=(ROOT/file).read_text()
 for term in terms:assert has(text, term),(file,term)
unit_route=spec['paths']['/studies/{study_id}/unit-catalog']['get']
assert 'UnitCatalog2' in json.dumps(unit_route['responses']['200'])
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
 assert has(workspace, term),('Workspace guard list',term)
for duplicate in ('Handle.current.dirty ||','handle.current.dirty ||','Handle.current.discard();','Handle.current.save()'):
 assert duplicate not in workspace,('Hand-maintained guard enumeration',duplicate)
print('Workspace editor-guard seam: one EditorGuard shape and one ordered guard list; browser gates remain separate.')


# Run outcomes. Readers see only the facets the runtime computes today, Execution and
# Criteria, through one shared RunOutcomes rendering. The constant facets stay stored and
# exported; they are not projected or labelled in reader UI, and the two outcomes are never
# merged.
outcomes_text=(ROOT/'src/runStatus.tsx').read_text()
for term in ('export function RunOutcomes(','export function runOutcomes(','export function resultOutcomes(',"{ label: 'Execution',","{ label: 'Criteria',"):
 assert has(outcomes_text, term),('Shared run outcomes',term)
consumers={'src/RunPanel.tsx':'<StatusTag tone={execution.tone}>','src/ResultPicker.tsx':'<RunOutcomes'}
for file,term in consumers.items():
 text=(ROOT/file).read_text()
 assert has(text, term),(file,'Run summaries must use their shared design-system component')
 assert '<Ledger' not in text and 'hf-run-summary' not in text,(file,'Second rendering of run outcomes')
 for removed in ('Convergence','Termination','Feasibility','Sample completeness','Output completeness','Applicability','applicability','results.convergence','results.optimization'):
  assert removed not in text,(file,'Constant facet shown to readers',removed)
run_text=(ROOT/'src/RunPanel.tsx').read_text()
assert 'executionStatus(detail)' in run_text
assert '<RecordDetails' in run_text and '<SectionHeader' in run_text
assert 'runOutcomes(detail)' not in run_text, 'Study criteria do not belong in a run headline'
assert '<ResourceCard' in run_text and '<CollectionStatus' in run_text
for removed in ('hf-display-note','Display: up to 3 decimals','source={','RetainedStudyConditions','Assessment evaluator','Read-only retained inputs'):
 assert removed not in run_text,('src/RunPanel.tsx','Removed run page element',removed)
for file,removed in (('src/ConfigurationRecord.tsx','numerical.mode'),('src/ConfigurationRecord.tsx','numerical.derivatives'),('src/RecordedConfiguration.tsx','Deterministic scalar')):
 assert removed not in (ROOT/file).read_text(),(file,'Removed run/configuration element',removed)
print('Run presentation: shared execution status, output header and collection cards; criterion evaluation remains separate.')


# Access-loss session seam. One client-only seam in api.ts: fence()
# (actor, CSRF session, session epoch, study access epoch; no dialog generation),
# readFailed() (one reconciled denial set, concealed 404 confirmed by one shared study
# probe, probe failure transient) and onSessionChange (signed-out, signed-in, access-lost).
# Protected-content hosts use it instead of their own denial lists or study probes.
seam_text=(ROOT/'src/api.ts').read_text()
for term in ("export const accessDeniedCodes: readonly string[] = ['unauthenticated', 'unauthorized', 'forbidden'];",'onSessionChange(listener: (change: SessionChange) => void)','fence(scope: { studyId?: string } = {}): ReadFence','async readFailed(error: unknown, fence: ReadFence','async confirmAccess(fence: ReadFence',"this.emit({ kind: 'signed-out' });","{ kind: 'access-lost'; studyId: string }"):
 assert has(seam_text, term),('Session seam',term)
seam_hosts={file:'useAccessLoss(' for file in ('src/ConfigurationPanel.tsx', 'src/RecordedConfiguration.tsx', 'src/executionReadiness.ts', 'src/RunPanel.tsx')}
for file,term in seam_hosts.items():
 text=(ROOT/file).read_text()
 assert has(text, term),(file,'Protected-content host must use the shared session seam')
 for duplicated in ("'unauthorized'","'unauthenticated'",'checkStudyAccess(token:number){\n    if(accessProbe'):
  assert duplicated not in text,(file,'Duplicated denial classification',duplicated)
 probes=text.count('api.study(')
 assert probes==0,(file,'Study probes belong to api.confirmAccess',probes)
workspace_text=(ROOT/'src/Workspace.tsx').read_text()
assert 'requestedCaseRef' not in workspace_text,('src/Workspace.tsx','Dead requestedCaseRef')
for term in ('setRunFilters(emptyRunFilters);',):
 assert has(workspace_text, term),('src/Workspace.tsx','clearSession must reset',term)
print('Session seam: one fence/readFailed/onSessionChange in api.ts, 9 protected-content hosts on it without duplicated denial lists or probes, session reset of return state and reading positions; browser gates remain separate.')


# One assumption concept: an assumption is a statement plus
# evidence rows, rendered by the shared Assumptions list with one empty state and no owner
# line. Instance descriptions use model-local annotations; definition and configuration
# notes remain outside the UI. A configuration
# shows one line linking to its model's assumptions instead of repeating them.
list_text=(ROOT/'src/Assumptions.tsx').read_text()
for term in ('No assumptions</p>','<Assertion','<EvidenceStack','relation={'):
 assert has(list_text, term),('src/Assumptions.tsx','Shared assumption list',term)
for removed in ('No assumptions recorded','Add approach assumption','Approach-owned','showHeading&&<p>{ownerLabel}</p>'):
 assert removed not in list_text,('src/Assumptions.tsx','Removed assumption list element',removed)
notes_free={'src/ModelEditor.tsx':('Component notes','Definition notes','title="Notes"'),
 'src/SelectionInspector.tsx':('Notes</h3>','Definition notes','No recorded notes'),
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
 assert has(record_text, term),('src/ConfigurationRecord.tsx','Model assumptions link',term)
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
 assert has(view_text, term),('src/ModelView.tsx','Canonical model view',term)
assert "'Variables'" not in view_text,('src/ModelView.tsx','No Variables projection tab')
for file in ('src/views/model.tsx','src/ConfigurationRecord.tsx'):
 assert '<ModelView' in (ROOT/file).read_text(),(file,'Reuses the canonical model view')
inspector_text=(ROOT/'src/SelectionInspector.tsx').read_text()
for term in (
    'verifySource(',
    'ComponentSourceContent',
    'modelAssumptions(snapshot)',
):
 assert has(inspector_text, term),('src/SelectionInspector.tsx','Details: what, why, assumptions',term)
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
assert "const tabs = ['Results', 'Model', 'Configuration'] as const;" in (
    ROOT / 'src/RunPanel.tsx'
).read_text(), 'Run tab is "Model" (one version)'
table_text=(ROOT/'src/VariablesTable.tsx').read_text()
for term in (
 'export function QuantitiesTable(', 'Show all quantities',
 'regionLabel="Quantities table"', 'label="Quantities"',
 "'not computed'", "'unassigned'", "'computed when run'",
):
 assert has(table_text, term),('src/VariablesTable.tsx','Quantities table',term)
assert 'export function variableRows(' in table_text,('src/VariablesTable.tsx','Export projection kept unchanged')
for file in ('src/ModelView.tsx','src/VariablesTable.tsx','src/SelectionInspector.tsx'):
 text=(ROOT/file).read_text()
 for pattern in ('schema_version',"'assumptions' in"):assert pattern not in text,(file,'Read versioned records through recordViews.ts',pattern)
model_view_text=(ROOT/'src/views/model.tsx').read_text()
for term in ('<RecordDetails kind="Model"', 'revision.model_revision_id', 'revision.digest'):
    assert re.sub(r'\s+', '', term) in re.sub(r'\s+', '', model_view_text), (
        'src/views/model.tsx',
        'Model version record in Record details',
    )
print(
 'Model view: one canonical ModelView (Diagram | Model explanation, component reading tabs, '
 'one quantities table) reused in Models, Run › Model, configuration and approach; '
 'ports table, incoming/outgoing lists, Variables tab and model-assumption dialogs absent; '
 'browser gates remain separate.'
)


# Overview contains exactly the two canonical authored owners; figure lives in the answer.
overview_text=(ROOT/'src/views/overview.tsx').read_text()
assert '<StudyBrief' in overview_text and '<StudyAnswer' in overview_text
assert 'ApproachReader' not in overview_text and 'OverviewStudyQuestion' not in overview_text

# Evidence index. One shared EvidenceIndex lists assumptions by owner with their evidence: the Evidence
# page reads the current owners (latest saved approach version, model drafts, latest revision of each
# configuration family) two reads at a time through the session seam, with a partial state that never
# reports an unread owner as having no assumptions; Run › Evidence reads only the retained versions.
# Run artifact, modified-seed and export reads and the approach controller use the session seam.
index_text=(ROOT/'src/EvidenceIndex.tsx').read_text()
for term in ('export function EvidenceIndex(','export function useCurrentAssumptions(','limiter(2)','api.fence({ studyId })','api.readFailed(error, read)','useAccessLoss(api, studyId',
 'latest_version','api.brief(','api.models(','api.model(','assumptionEvidence(','api.configurations(','record.configuration.configuration_id ?? record.configuration.configuration_revision_id',
 "kind: 'failed'","kind: 'limitation'",'Assumptions could not be loaded.','groups loaded','could not be listed','Groups that could not be loaded are left out; they are not shown as having no assumptions.','<Assumptions regionless'):
 assert has(index_text, term),('src/EvidenceIndex.tsx','Evidence index',term)
assert index_text.count("'No assumptions'")==0 and index_text.count('>No assumptions<')==1,('src/EvidenceIndex.tsx','"No assumptions" only for a loaded index without owners')
evidence_panel=(ROOT/'src/EvidencePanel.tsx').read_text()
for term in ('useReferencedEvidence(api, studyId)', 'aria-label="Evidence library"', '<EvidenceStack className="hf-evidence-list">', 'contextual', 'No evidence referenced yet.'):
 assert has(evidence_panel, term),('src/EvidencePanel.tsx','Direct referenced evidence library',term)
assert '<EvidenceIndex' not in evidence_panel, ('src/EvidencePanel.tsx', 'Claims stay at their owner')
for file in ('src/StudyBrief.tsx', 'src/StudyAnswer.tsx'):
 assert 'EvidenceList' in (ROOT/file).read_text(), (file, 'Claim evidence uses the shared direct reader')
assert 'Saved notes and references' not in evidence_panel and 'title="Saved evidence"' not in evidence_panel,('src/EvidencePanel.tsx','Replaced Evidence page copy')
assert has((ROOT/'src/views/evidence.tsx').read_text(), 'onOpen={target => navigate(() => void openLink(target))} />}</div>'),\
 ('src/views/evidence.tsx','Evidence page owner links use guarded navigation')
assert 'function RunEvidence(' not in run_text, (
    'src/RunPanel.tsx', 'Evidence stays with its owning assertion',
)
for file, terms in {
    'src/RunPanel.tsx': (
        'api.modifiedRunSeedRead(studyId, detail.run_id, read.signal)',
        'Check modified run again',
    ),
    'src/ComputationalExportDialog.tsx': (
        'api.computationalRecord(studyId,record!.request_id,read.signal)',
        'api.readFailed(failure,read)',
        'useAccessLoss(api,studyId',
    ),
    'src/api.ts': ('throw new ApiError(value?.error ? { ...value.error, message: unavailable }',),
    'src/Workspace.tsx': ('brief.dispose()', 'answer.dispose()'),
}.items():
 text=(ROOT/file).read_text()
 for term in terms:assert has(text, term),(file,'Session seam',term)
 assert "'unauthorized'" not in text and "'unauthenticated'" not in text or file=='src/api.ts',(file,'Duplicated denial classification')
assert (ROOT/'src/RunPanel.tsx').read_text().count('readFailed(')>=2, (
    'src/RunPanel.tsx',
    'Run and seed reads classified by readFailed; collection read classified in shared hook',
)
print('Evidence library reads cited versions directly; claim readers use the shared evidence panel. Browser gates remain separate.')

# Home archive, Overview identities, study header and footer. Archive is a study-wide
# presentation command through the shared receipt path; Home reads both lists.
api_s6b=(ROOT/'src/api.ts').read_text()
for term in ("archivedStudies = () => this.list<Study>('/studies?archived=true');",
 "this.mutate<Study>(`/studies/${sid}/archive`, command, 'study_archive', sid)",
 "this.mutate<Study>(`/studies/${sid}/restore`, command, 'study_archive', sid)",'command: StudyArchiveCommand'):
 assert term in api_s6b,('src/api.ts','Study archive client',term)
workspace_s6b=(ROOT/'src/Workspace.tsx').read_text()
for term in ('Promise.all([api.studies(), api.archivedStudies()])','label="Study list"',"label: 'Active'","label: 'Trash'",'label="Trash"','>In Trash</StatusTag>',
 'aria-label={`Delete study ${s.name}`}','aria-label={`Restore study ${s.name}`}','to Trash for everyone? You can restore the study and all its records later.',
 '<Button data-safe-choice',"pending?.category === 'study_archive'",'.catch(archiveRefusal)'):
 assert re.sub(r'\s+', '', term) in re.sub(r'\s+', '', workspace_s6b), (
  'src/Workspace.tsx', 'Home archive, study header and footer', term
 )
assert re.search(
 r'<div className="study-heading actions">\s*<h1>\{study.name\}</h1>\s*'
 r'\{studyCreator && <AttributionChip \{\.\.\.studyCreator\} />\}\s*</div>',
 workspace_s6b,
), ('src/Workspace.tsx', 'Study heading names the study then conditionally shows its creator')
for removed in ("'Study overview'",'Choose a study to continue your work.'):
 assert removed not in workspace_s6b,('src/Workspace.tsx','Removed shell element',removed)
fixture_s6b=(ROOT.parent/'deployment/tests/approach_ui_fixture.py').read_text()
for term in ("/(archive|restore)', route)","self.path == '/fixture/reader'"):
 assert term in fixture_s6b,('deployment/tests/approach_ui_fixture.py','Archive commands and reader setup',term)
print('Home archive: Active | Trash from two reads, recoverable Delete with confirmation and Restore through study_archive commands; Overview without identity disclosures; study name shown once; licences accompany browser assets; browser gates remain separate.')

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
for file,terms in {
  'src/runStatus.tsx': ('label="Run status"',),
  'src/RunPanel.tsx': (
    'title="Outputs"', 'className="hf-header-metric"',
    '<dt>Execution bundle SHA-256</dt>',
  ),
 'src/ComputationalExportDialog.tsx':("'Create export'","'Download ZIP'",'For inspection; this archive does not guarantee that the calculation can run on another installation.'),'src/ComparisonView.tsx':('Download portable model record','label="Portable model record file"',"'Quantities CSV'")}.items():
 text=(ROOT/file).read_text()
 for term in terms:
  assert re.sub(r'\s+', '', term) in re.sub(r'\s+', '', text), (
   file, 'Plain-language name (design-system/Naming.md)', term
  )
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


# Collection readers share presentation and the public session boundary.
collection_read=(ROOT/'src/useCollectionRead.ts').read_text()
for term in ('api.fence({ studyId: study })','api.readFailed(error, fence)',
             'api?.onSessionChange','latest.current.key === key','cursor !== undefined'):
 assert has(collection_read, term), ('Shared collection lifecycle', term)
for name in ('ConfigurationList','CalculationsPanel','RunPanel','CalculationDesign',
             'EvidencePicker','ResultPicker','EvidenceView','Assumptions'):
 text=(ROOT/('src/'+name+'.tsx')).read_text()
 assert '<CollectionStatus' in text and 'useCollectionRead' in text, (
     name, 'Use shared collection boundary',
 )
 for obsolete in ('saved versions loaded', 'loaded runs', 'loaded records', 'loaded page'):
  assert obsolete not in text, (name,'Obsolete collection coverage',obsolete)
print('Collections: shared presentation, scope fences and cursor coverage in all paged readers.')
