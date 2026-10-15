import {
  AttributionDetail,
  RecordAttribution,
  attributionText,
  useAttribution,
} from './attribution';
import { CaseContextLink } from './ConfigurationApproach';
import { runLabel } from './recordLabels';
import { ComputationalExportDialog } from './ComputationalExportDialog';
import { ConfigurationRecord, ConfigurationRecordDetails } from './ConfigurationRecord';
import { RetainedFiles } from './RetainedFiles';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { HyprnMvpApi, accessLostText, accessUnverifiedText, message } from './api';
import { useAccessLoss } from './accessLoss';
import type { ConfigurationRevision, PublicRun, PublicRunDetail, RunHistoryRead6, RunHistoryItem, ModifiedRunSeedRead6 } from './api';
import type { HistoryArtifact, ProgramSourceMapEntry } from './contract';
import { CaseNavigation, type Selection } from './workspaceModel';
import {
  Button, Panel, Tabs, TextInput, Select, DataTable, RecordBar, StatusTag, Progress,
  ActionDialog, SectionHeader, Disclosure, formatNumber,
} from './design';
import { modelPorts, refKey, RuntimeComparisonView } from './ConfigurationPanel';
import { criterionOperators } from './criterionLabels';
import { RunOutcomes, runOutcomes } from './runStatus';
import { configurationContext, linkedApproach, recordLimitations } from './recordViews';

const historyErrors: Record<RunHistoryRead6['errors'][number]['code'], string> = {
  history_not_recorded: "This run's record is not available yet.",
  missing_results: 'Some results are missing. What is available is shown below.',
  missing_artifacts: 'This run file is unavailable.',
  missing_or_invalid_artifact: 'This run file is unavailable.',
  corrupt_retained_record: "Part of this run's record could not be verified. Verified sections remain visible.",
  unsupported_record_version: 'This run uses a record format this application cannot display.',
};
export function runPending(run: PublicRun) { return ['accepted_run', 'prepared', 'dispatching', 'uncertain'].includes(run.state) || (run.state === 'recorded' && !['finished', 'excepted', 'killed'].includes(run.process_state ?? 'unknown')); }
const submissionLabels = { accepted_run: 'Queued', prepared: 'Prepared', dispatching: 'Starting', preparation_failed: 'Preparation failed', recorded: 'Execution recorded', uncertain: 'Needs review' };
function progressLabel(run: PublicRun) {
  if (run.state === 'accepted_run') return 'Queued for preparation';
  if (run.state === 'prepared') return 'Prepared — waiting to start';
  if (run.state === 'dispatching') return 'Starting calculation';
  return run.process_state === 'running' ? 'Calculation running' : 'Waiting for execution results';
}
const present = (value: unknown, labels: Record<string, string>) => value == null ? 'Not available' : typeof value === 'string' && Object.hasOwn(labels, value) ? labels[value] : 'Unknown';
const outputReasons = { producer_failed: 'Producer failed', unassigned: 'Not assigned', nonfinite: 'Non-finite value', unavailable: 'Unavailable' };
const executionLabels = { finished: 'Completed', failed: 'Failed' };
const tabs = ['Results', 'Model', 'Configuration'] as const;
type HistoryTab = typeof tabs[number];
const previewLimit = 64 * 1024;


// Map locations only when every retained identity binds to this frozen snapshot.
function mappedEntries(raw: string, history: RunHistoryRead6): ProgramSourceMapEntry[] {
  const map = JSON.parse(raw), snapshot = history.model_snapshot;
  if (!snapshot || map.schema_version !== '1' || map.transform_version !== '1' || !Array.isArray(map.entries) || map.entries.length > 1000) throw new Error('This source mapping is unsupported or invalid.');
  const transforms = ['utf8_bom_decode', 'line_endings', 'indent', 'source_symbol_view', 'availability_observer'];
  for (const row of map.entries) {
    const instance = snapshot.instances.find(i => i.instance_id === row?.instance_id && i.definition_version_id === row.definition_version_id);
    const definition = snapshot.definitions.find(d => d.definition_version_id === instance?.definition_version_id);
    if (!instance || !definition?.source_refs.includes(row.source_sha256) || !snapshot.source_files.some(s => s.sha256 === row.source_sha256) ||
      !history.artifacts.some(a => a.name === row.source_path && a.sha256 === row.source_sha256 && a.name.startsWith('sources/')) ||
      !history.artifacts.some(a => a.name === row.generated_path && a.role === 'generated' && a.name.startsWith('generated/')) ||
      !Number.isSafeInteger(row.generated_line_start) || !Number.isSafeInteger(row.generated_line_end) || row.generated_line_start < 1 || row.generated_line_end < row.generated_line_start ||
      !Array.isArray(row.transforms) || row.transforms.length > transforms.length || new Set(row.transforms).size !== row.transforms.length || row.transforms.some((t: unknown) => !transforms.includes(String(t)))) throw new Error("This source mapping does not match the run's source and generated files.");
  }
  return map.entries;
}

/** Version-qualified case context from the authorized run list projection.
 * Missing or malformed metadata is unavailable, never the explicit null case. */
const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
type RunCase = { key: string; label: string; option: string; order: [number, number, string]; linked?: { approach_version_id: string; case_id: string | null; version_number: number; name: string } };
function runCase(context: unknown): RunCase {
  const unavailable: RunCase = { key: 'unavailable', label: 'Case context unavailable', option: 'Case context unavailable', order: [2, 0, ''] };
  if (!context || typeof context !== 'object') return unavailable;
  const value = context as Record<string, unknown>;
  if (value.state === 'unlinked') return { key: 'unlinked', label: 'No modeling approach', option: 'No modeling approach', order: [1, 0, ''] };
  if (value.state !== 'linked' || typeof value.approach_version_id !== 'string' || !uuidPattern.test(value.approach_version_id) ||
    typeof value.version_number !== 'number' || !Number.isSafeInteger(value.version_number) || value.version_number < 1 ||
    !(value.case_id === null || typeof value.case_id === 'string' && uuidPattern.test(value.case_id)) ||
    !(value.case_name === null || typeof value.case_name === 'string' && value.case_name.length <= 4096)) return unavailable;
  const caseId = value.case_id as string | null, name = caseId === null ? 'No specific case' : (value.case_name as string | null) ?? 'Unnamed case';
  return { key: 'linked:' + value.approach_version_id + ':' + (caseId ?? 'none'), label: `${name} · approach v${value.version_number}`, option: `Approach v${value.version_number} · ${name}`, order: [0, value.version_number, name],
    linked: { approach_version_id: value.approach_version_id, case_id: caseId, version_number: value.version_number, name } };
}
export type RunFilters = { text: string; state: string; caseKey: string };
export const emptyRunFilters: RunFilters = { text: '', state: '', caseKey: '' };

function RunCaseCell({ run, value }: { run: RunHistoryItem; value: RunCase }) {
  return <p className="run-case"><span className="run-case-label">Case</span>{value.linked
    ? <CaseContextLink target={{ approach_version_id: value.linked.approach_version_id, case_id: value.linked.case_id }} returnKey={'run-case:' + run.run_id} label={`${value.label}, open case for run ${run.run_id.slice(0, 8)}`}>{value.label}</CaseContextLink>
    : <span>{value.label}</span>}</p>;
}

export function RunPanel({ filters: hostFilters, onFilters, onViewSourceResult, sourceOutput, resourceActionsRef, listEpoch = 0, api, studyId, submitted, onActive, onCreateModified, navigate, onInspection, onHistory, workspace, onSelect }: { onViewSourceResult?: (runId: string, output: { instance_id: string; port_id: string }) => void; sourceOutput?: { runId: string; output: { instance_id: string; port_id: string } }; resourceActionsRef?: (element: HTMLDivElement | null) => void; listEpoch?: number; api: HyprnMvpApi; studyId: string; submitted: PublicRun | null; onActive: (active: boolean) => void; onCreateModified: (seed: ModifiedRunSeedRead6, config: ConfigurationRevision) => void; navigate: (action: () => void) => void; onInspection?: (detail: PublicRunDetail | null) => void; /** The user explicitly returned to the run history list. */ onHistory?: () => void; workspace?: ReactNode; onSelect?: (selection: Selection) => void; filters?: RunFilters; onFilters?: (filters: RunFilters) => void }) {
  const [runs, setRuns] = useState<RunHistoryItem[]>([]); const [listReady, setListReady] = useState(false); const [listBusy, setListBusy] = useState(false);
  const [selected, setSelected] = useState('');
  const submittedBy = useAttribution('run', selected);
  useEffect(() => { setSelected(''); }, [listEpoch]); const [detail, setDetail] = useState<PublicRunDetail | null>(null); const [loading, setLoading] = useState(false);
  const [modifiedSeed, setModifiedSeed] = useState<ModifiedRunSeedRead6 | null>(null), [modifiedReason, setModifiedReason] = useState('Checking whether this run can be modified…');
  const [seedAttempt, setSeedAttempt] = useState(0), [seedRetry, setSeedRetry] = useState(false);
  useEffect(() => {
    let current = true; setModifiedSeed(null); setModifiedReason('Checking whether this run can be modified…'); setSeedRetry(false);
    if (!detail || runPending(detail)) { setModifiedReason('Available once the run has finished.'); return; }
    // The seed read is scoped by the session seam and classified like the run read. A confirmed denial
    // clears the run through the session signal; a transient study probe offers a retry.
    const read = api.fence({ studyId });
    api.modifiedRunSeedRead(studyId, detail.run_id, read.signal).then(seed => { if (current && read.valid()) { setModifiedSeed(seed); setModifiedReason(''); } }).catch(async e => {
      const outcome = await api.readFailed(e, read);
      if (!current) return;
      if (outcome === 'transient') { setModifiedReason(accessUnverifiedText); setSeedRetry(true); }
      else if (outcome === 'error') setModifiedReason(message(e));
    }).finally(read.done);
    return () => { current = false; read.abort(); };
  }, [api, studyId, detail?.run_id, detail?.state, detail?.process_state, seedAttempt]);
  const inspectionCallback = useRef(onInspection); inspectionCallback.current = onInspection;
  useEffect(() => { inspectionCallback.current?.(detail?.run_id === selected ? detail : null); }, [detail, selected]);
  const outputRoot = useRef<HTMLElement>(null);
  useEffect(() => {
    if (!sourceOutput || detail?.run_id !== sourceOutput.runId) return;
    setTab('Results');
    const frame = requestAnimationFrame(() => {
      const button = outputRoot.current?.querySelector<HTMLButtonElement>(`[data-source-output="${sourceOutput.output.instance_id}/${sourceOutput.output.port_id}"]`);
      button?.focus(); button?.scrollIntoView({block:'center'});
    });
    return () => cancelAnimationFrame(frame);
  }, [detail?.run_id, sourceOutput?.runId, sourceOutput?.output.instance_id, sourceOutput?.output.port_id]);
  const [artifactBusy, setArtifactBusy] = useState(false);
  const [tab, setTab] = useState<HistoryTab>('Results'), [localFilters, setLocalFilters] = useState<RunFilters>(emptyRunFilters);
  // The host may retain filters across exact case navigation and return.
  const filters = hostFilters ?? localFilters, setFilters = (next: Partial<RunFilters>) => { const value = { ...filters, ...next }; if (onFilters) onFilters(value); else setLocalFilters(value); };
  const filter = filters.text, stateFilter = filters.state, caseFilter = filters.caseKey;
  const [preview, setPreview] = useState<{ artifact: HistoryArtifact; text: string } | null>(null);
  const previewElement = useRef<HTMLPreElement>(null);
  useEffect(() => { if (preview) { previewElement.current?.focus(); previewElement.current?.scrollIntoView({ block: 'nearest' }); } }, [preview]);
  const [mappings, setMappings] = useState<ProgramSourceMapEntry[] | null>(null);
  const artifactRequest = useRef(0);
  useEffect(() => { artifactRequest.current++; setPreview(null); setMappings(null); setArtifactBusy(false); setTab('Results'); }, [selected]);
  const [error, setError] = useState<unknown>(null); const [listError, setListError] = useState<unknown>(null); const generation = useRef(0); const alive = useRef(true);
  const listRequest = useRef(0), detailRequest = useRef(0), refreshRead = useRef<() => void>(() => {});
  /** Confirmed denial (this panel's own read or any host of this study): clear the
   * run list with its case labels, the run record and its history, stop status
   * backoff and drop every pending reply. Nothing is submitted. */
  // After a cleared record, "Refresh run status" starts a fresh, newly scoped read.
  const [reload, setReload] = useState(0);
  function clearProtected() {
    generation.current++; listRequest.current++; detailRequest.current++; artifactRequest.current++; refreshRead.current = () => setReload(n => n + 1);
    setRuns([]); setListReady(false); setListBusy(false); setDetail(null); setLoading(false); setPreview(null); setMappings(null); setArtifactBusy(false); setModifiedSeed(null); setSeedRetry(false);
    setError(new Error(accessLostText)); setListError(new Error(accessLostText));
  }
  useAccessLoss(api, studyId, change => { if (change.kind === 'access-lost') clearProtected(); });
  async function refreshList() {
    const request = ++listRequest.current, read = api.fence({ studyId }), latest = () => alive.current && request === listRequest.current, current = () => latest() && read.valid();
    setListBusy(true); setListError(null);
    try { const value = await api.runs(studyId); if (current()) { setRuns(value.slice().reverse()); setListReady(true); } }
    catch (e) { const outcome = await api.readFailed(e, read); if ((outcome === 'error' || outcome === 'transient') && current()) setListError(outcome === 'transient' ? new Error(accessUnverifiedText) : e); }
    finally { read.done(); if (latest()) setListBusy(false); }
  }
  useEffect(() => { alive.current = true; setRuns([]); setListReady(false); void refreshList(); return () => { alive.current = false; generation.current++; listRequest.current++; }; }, [studyId]);
  useEffect(() => { if (submitted) { setSelected(submitted.run_id); void refreshList(); } }, [submitted?.run_id]);
  useEffect(() => {
    const token = ++generation.current; let timer: ReturnType<typeof setTimeout> | undefined; let failures = 0;
    setDetail(null); setError(null); if (!selected) { setLoading(false); return; }
    setLoading(true);
    async function read(manual = false) {
      if (timer) { clearTimeout(timer); timer = undefined; }
      // A cleared panel (confirmed denial) or a newer selection never reads again from this effect.
      if (!alive.current || token !== generation.current) return;
      const request = ++detailRequest.current, fence = api.fence({ studyId }), current = () => alive.current && token === generation.current && request === detailRequest.current && fence.valid();
      if (manual) { setLoading(true); setError(null); }
      try { const value = await api.run(studyId, selected); if (!current()) return; setDetail(value); setError(null); failures = 0;
        if (submitted?.run_id === value.run_id) onActive(runPending(value));
        if (runPending(value)) timer = setTimeout(() => void read(), value.state === 'uncertain' ? 5000 : 1500);
        else void refreshList();
      } catch (e) {
        // Confirmed denial clears through the session signal and schedules nothing.
        const outcome = await api.readFailed(e, fence);
        if ((outcome === 'error' || outcome === 'transient') && current()) { setError(outcome === 'transient' ? new Error(accessUnverifiedText) : e); failures++; timer = setTimeout(() => void read(), Math.min(1000 * 2 ** failures, 10000)); }
      }
      finally { fence.done(); if (current()) setLoading(false); }
    }
    refreshRead.current = () => void read(true);
    void read(); return () => { generation.current++; detailRequest.current++; refreshRead.current = () => {}; if (timer) clearTimeout(timer); };
  }, [selected, studyId, submitted?.run_id, reload]);
  function refreshDetail() { refreshRead.current(); }
  const history = detail?.history, results = history?.results;
  const cases = new Map(runs.map(r => [r.run_id, runCase(r.case_context)]));
  const caseOptions = [...new Map([...cases.values()].map(c => [c.key, c])).values()].sort((a, b) => a.order[0] - b.order[0] || a.order[1] - b.order[1] || a.order[2].localeCompare(b.order[2]) || a.key.localeCompare(b.key));
  const visibleRuns = runs.filter(r => `${runLabel(r)} ${r.run_id} ${r.configuration_revision_id}`.toLowerCase().includes(filter.trim().toLowerCase()) && (!stateFilter || r.state === stateFilter) && (!caseFilter || cases.get(r.run_id)?.key === caseFilter));
  const caseUnavailable = runs.some(r => cases.get(r.run_id)?.key === 'unavailable');
  // A recorded run resolves its case through its own retained closure. Before a
  // history exists (queued/preparing), the authorized list projection for this
  // exact run is the only source; unknown metadata stays unavailable.
  const detailCase = (() => {
    const configuration = history?.configuration;
    if (!history || !configuration) {
      const listed = runs.find(r => r.run_id === selected);
      if (!listed || !detail) return null;
      const value = runCase(listed.case_context);
      return value.linked ? { label: value.label, link: { target: { approach_version_id: value.linked.approach_version_id, case_id: value.linked.case_id }, name: value.linked.name, version: value.linked.version_number } } : { label: value.label };
    }
    const context = configurationContext(configuration), pin = linkedApproach(context);
    if (context.kind === 'unsupported') return { label: 'Case context unavailable' };
    if (!pin) return { label: 'No modeling approach' };
    const closure = 'approach_closure' in history ? history.approach_closure : undefined;
    const version = closure?.approach_versions.find(v => v.approach_version_id === pin.approach_version_id);
    if (!version) return { label: 'Case context unavailable' };
    const item = version.content.cases.find(c => c.case_id === pin.case_id), name = pin.case_id === null ? 'No specific case' : item?.title ?? 'Case not in this approach version';
    return { label: `${name} · approach v${version.version_number}`, link: { target: { approach_version_id: pin.approach_version_id, case_id: pin.case_id }, name, version: version.version_number } };
  })();
  const sourceMap = history?.artifacts.find(a => a.name === 'generated/source-map.json' && a.role === 'generated');
  function openTab(name: HistoryTab) { setTab(name); const id = 'run-tab-' + tabs.indexOf(name); requestAnimationFrame(() => { document.getElementById(id)?.focus(); document.getElementById(id)?.scrollIntoView({ block: 'nearest' }); }); }
  function inspect(selection: Selection) { const dialog = document.activeElement?.closest('dialog'); if (dialog instanceof HTMLDialogElement) dialog.close(); onSelect?.(selection); setTab('Model'); requestAnimationFrame(() => { document.getElementById('run-tab-1')?.focus(); document.getElementById('run-tab-1')?.scrollIntoView({ block: 'nearest' }); }); }
  async function readArtifact(artifact: HistoryArtifact, mode: 'preview' | 'map' | 'download') {
    const token = generation.current, request = ++artifactRequest.current, read = api.fence({ studyId }); setError(null); setArtifactBusy(true); setPreview(null);
    const current = () => token === generation.current && request === artifactRequest.current && alive.current && read.valid();
    if (mode === 'map') setMappings(null);
    try {
      if (mode !== 'download' && artifact.size > previewLimit) throw new Error('Preview is limited to 64 KiB. Download the file instead.');
      const blob = await api.artifact(studyId, selected, artifact, read.signal);
      if (!current()) return;
      if (mode === 'download') { const url = URL.createObjectURL(blob), link = document.createElement('a'); link.href = url; link.download = artifact.name.split('/').pop()!; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); }
      else {
        const text = new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(await blob.arrayBuffer());
        if (!current()) return;
        if (mode === 'map') setMappings(mappedEntries(text, history!)); else setPreview({ artifact, text });
      }
    } catch (e) {
      // Classified like the run read. A confirmed denial clears the run through the
      // session signal; a transient study probe keeps the record and the read can be retried.
      const outcome = await api.readFailed(e, read);
      if (current() && (outcome === 'error' || outcome === 'transient')) setError(outcome === 'transient' ? new Error(accessUnverifiedText) : e);
    }
    finally { read.done(); if (token === generation.current && request === artifactRequest.current && alive.current) setArtifactBusy(false); }
  }
  const ports = history?.model_snapshot ? modelPorts(history.model_snapshot) : [];
  const label = (target: { instance_id: string; port_id: string }) => ports.find(p => refKey(p.target) === refKey(target))?.label ?? refKey(target);
  return (
    <section ref={outputRoot} aria-label="Runs" className="run-panel">
      <div hidden={!!selected}>
        <div className="page-heading">
          <h2 id="history-title">Run history</h2>
        </div>
        <div className="run-filters">
          <Button disabled={listBusy} onClick={() => void refreshList()}>
            Refresh run history
          </Button>
          {!!runs.length && (
            <>
              <label>
                Filter loaded runs
                <TextInput
                  type="search"
                  value={filter}
                  onChange={(e) => setFilters({ text: e.target.value })}
                />
              </label>
              <label>
                Run case
                <Select
                  aria-label="Run case"
                  value={caseFilter}
                  onChange={(e) => setFilters({ caseKey: e.target.value })}
                >
                  <option value="">All cases</option>
                  {caseOptions.map((c) => (
                    <option key={c.key} value={c.key}>
                      {c.option}
                    </option>
                  ))}
                  {caseFilter && !caseOptions.some((c) => c.key === caseFilter) && (
                    <option value={caseFilter}>Selected case · no loaded runs</option>
                  )}
                </Select>
              </label>
              <label>
                Run submission state
                <Select value={stateFilter} onChange={(e) => setFilters({ state: e.target.value })}>
                  <option value="">All states</option>
                  {[
                    'accepted_run',
                    'prepared',
                    'preparation_failed',
                    'dispatching',
                    'recorded',
                    'uncertain',
                  ].map((state) => (
                    <option key={state} value={state}>
                      {submissionLabels[state as keyof typeof submissionLabels]}
                    </option>
                  ))}
                </Select>
              </label>
              <p aria-live="polite">
                {visibleRuns.length} of {runs.length} loaded runs
              </p>
              {caseUnavailable && (
                <Button disabled={listBusy} onClick={() => void refreshList()}>
                  Retry case context
                </Button>
              )}
            </>
          )}
        </div>
        {listBusy && (
          <p aria-live="polite">
            <StatusTag tone="running">Loading run history…</StatusTag>
          </p>
        )}
        {listError != null && !selected && <p role="alert">{message(listError)}</p>}
        {listReady && !listBusy && !listError && !runs.length && (
          <Panel>
            <p>
              This study has no runs yet. Commit a configuration, then run the model.{' '}
              <a href="#configuration">Open configuration</a>
            </p>
          </Panel>
        )}
        {!!runs.length && (
          <Panel className="run-history">
            <ol className="run-list">
              {visibleRuns.map((r) => (
                <li key={r.run_id}>
                  <div>
                    <Button
                      variant="quiet"
                      aria-label={`Inspect run ${r.run_id}`}
                      aria-pressed={selected === r.run_id}
                      onClick={() => navigate(() => setSelected(r.run_id))}
                    >
                      {runLabel(r)} · {r.run_id.slice(0, 8)}
                    </Button>
                    <p>
                      Configuration version {r.configuration_revision_id.slice(0, 8)}
                      <RecordAttribution kind="run" id={r.run_id} inline />
                    </p>
                  </div>
                  <RunCaseCell run={r} value={cases.get(r.run_id)!} />
                  <StatusTag
                    tone={
                      r.state === 'preparation_failed'
                        ? 'alarm'
                        : r.state === 'uncertain'
                          ? 'warning'
                          : 'inert'
                    }
                  >
                    {submissionLabels[r.state]}
                  </StatusTag>
                </li>
              ))}
            </ol>
            {!visibleRuns.length && <p>No runs match these filters.</p>}
          </Panel>
        )}
      </div>
      {selected && (
        <section aria-label="Run details">
          <p role="status">{modifiedReason}</p>
          {seedRetry && (
            <Button onClick={() => setSeedAttempt((n) => n + 1)}>Check modified run again</Button>
          )}
          <RuntimeComparisonView comparison={detail?.runtime_comparison} />
          <RecordBar
            title="Saved run · read-only"
            returnLabel="Back to run history"
            onReturn={() => {
              generation.current++;
              setSelected('');
              setDetail(null);
              onHistory?.();
            }}
          />
          <div className="page-heading run-heading">
            <div>
              <h2>{history?.configuration?.name ?? 'Run record'}</h2>
              <p className="context-line">
                Run {selected.slice(0, 8)}
                {detailCase && (
                  <span className="run-detail-case">
                    {' '}
                    · Case: {detailCase.label}
                    {detailCase.link && (
                      <>
                        {' '}
                        <CaseContextLink
                          target={detailCase.link.target}
                          returnKey={'run-detail-case:' + selected}
                          label={
                            `View case ${detailCase.link.name} in approach v` +
                            detailCase.link.version
                          }
                        >
                          View case
                        </CaseContextLink>
                      </>
                    )}
                  </span>
                )}
                <RecordAttribution kind="run" id={selected} inline />
              </p>
            </div>
            <div className="section-actions">
              <div className="section-actions" role="group" aria-label="Run exports">
                <div className="section-actions" ref={resourceActionsRef} />
                {history?.configuration && detail && !runPending(detail) && (
                  <ComputationalExportDialog
                    key={selected}
                    api={api}
                    studyId={studyId}
                    runId={selected}
                    name={history.configuration.name}
                  />
                )}
              </div>
              {history && (
                <>
                  <ActionDialog
                    title="Run record"
                    label="Run record details"
                    size="sm"
                    variant="quiet"
                  >
                    {submittedBy && <p>Submitted by {attributionText(submittedBy)}</p>}
                    <dl className="hf-record-details">
                      <AttributionDetail kind="run" id={selected} label="Submitted by" />
                      <dt>Run ID</dt>
                      <dd>{selected}</dd>
                      <dt>Configuration version</dt>
                      <dd>{history.configuration?.configuration_revision_id ?? 'Unavailable'}</dd>
                      <dt>Model version</dt>
                      <dd>{history.model_snapshot?.model_revision_id ?? 'Unavailable'}</dd>
                      <dt>Execution bundle SHA-256</dt>
                      <dd>{history.bundle?.bundle_digest ?? 'Unavailable'}</dd>
                      <dt>Criterion evaluator</dt>
                      <dd>{history.assessment?.evaluator_sha256 ?? 'Unavailable'}</dd>
                      <dt>Model SHA-256</dt>
                      <dd>{history.model_snapshot?.digest ?? 'Unavailable'}</dd>
                      <dt>Configuration SHA-256</dt>
                      <dd>{history.configuration?.digest ?? 'Unavailable'}</dd>
                    </dl>
                    <h3>Dependency versions</h3>
                    {history.bundle ? (
                      <ul>
                        {history.bundle.dependencies.map((d) => (
                          <li key={d.name}>
                            {d.name}: {d.version} · {d.lock_path}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p>Unavailable</p>
                    )}
                  </ActionDialog>
                </>
              )}
              {history?.configuration && history.model_snapshot && (
                <Button
                  disabled={!modifiedSeed}
                  onClick={() =>
                    modifiedSeed &&
                    navigate(() => onCreateModified(modifiedSeed, history.configuration!))
                  }
                >
                  Create modified run
                </Button>
              )}
              {(!detail || runPending(detail)) && (
                <Button disabled={loading} onClick={() => void refreshDetail()}>
                  Refresh run status
                </Button>
              )}
            </div>
          </div>
          {loading && (
            <p aria-live="polite" aria-busy="true">
              Loading run…
            </p>
          )}
          {error != null && <p role="alert">{message(error)}</p>}
          {detail && (
            <>
              {runPending(detail) && detail.state !== 'uncertain' ? (
                <Progress
                  label={progressLabel(detail)}
                  message="Status updates automatically. Results appear here when available."
                />
              ) : (
                detail.state === 'recorded' &&
                !results && (
                  <p role="status">
                    <StatusTag
                      tone={
                        ['excepted', 'killed'].includes(detail.process_state ?? '') ||
                        (detail.exit_status != null && detail.exit_status !== 0)
                          ? 'alarm'
                          : 'inert'
                      }
                    >
                      {detail.process_state === 'finished'
                        ? 'Execution finished'
                        : 'Execution stopped'}
                    </StatusTag>
                  </p>
                )
              )}
              {error != null && runPending(detail) && (
                <p role="status">Connection interrupted. Retrying status updates automatically.</p>
              )}
              {detail.state === 'preparation_failed' && (
                <p role="alert">
                  <StatusTag tone="alarm">Preparation failed</StatusTag> The calculation did not
                  run, so there are no results.
                </p>
              )}
              {detail.state === 'uncertain' && (
                <p role="status">
                  <StatusTag tone="warning">Submission outcome is uncertain</StatusTag> Checking the
                  original command is a read; no new run will be submitted.
                </p>
              )}
              {!history && (!runPending(detail) || detail.state === 'uncertain') && (
                <p>This run's record is not available yet.</p>
              )}
              {history?.errors.map((e, i) => (
                <p role="alert" key={i}>
                  {historyErrors[e.code]}
                </p>
              ))}
              <Tabs
                label="Run detail sections"
                value={tab}
                onChange={(name) => setTab(name as HistoryTab)}
                items={tabs.map((name, i) => ({
                  id: name,
                  label: name,
                  tabId: 'run-tab-' + i,
                  panelId: 'run-panel-' + i,
                }))}
              />
              <section
                role="tabpanel"
                id="run-panel-0"
                aria-labelledby="run-tab-0"
                hidden={tab !== 'Results'}
              >
                <Panel hidden={!results && runPending(detail) && detail.state !== 'uncertain'}>
                  {!results && (!runPending(detail) || detail.state === 'uncertain') && (
                    <p>No results for this run. Missing values are never shown as zero.</p>
                  )}
                  {results && (
                    <>
                      <RunOutcomes variant="ledger" outcomes={runOutcomes(detail)} />
                      {results.execution.state === 'failed' && (
                        <section
                          aria-label="Execution diagnostic"
                          className="run-execution-diagnostic"
                        >
                          <StatusTag tone="alarm">Execution failed</StatusTag>
                          <p className="context-copy">{results.execution.message}</p>
                        </section>
                      )}
                      <SectionHeader title="Outputs" />
                      <DataTable regionLabel="Output values">
                        <thead>
                          <tr>
                            <th>Output</th>
                            <th>Value</th>
                            <th>Units</th>
                          </tr>
                        </thead>
                        <tbody>
                          {results.outputs.map((o) => (
                            <tr key={refKey(o.target)}>
                              <th scope="row">
                                <Button
                                  variant="quiet"
                                  size="sm"
                                  disabled={!history?.model_snapshot}
                                  onClick={() => inspect({ kind: 'variable', ...o.target })}
                                  data-source-output={refKey(o.target)}
                                  aria-label={`Inspect output ${label(o.target)}`}
                                >
                                  {label(o.target)}
                                </Button>
                              </th>
                              <td
                                className={
                                  o.availability === 'available' &&
                                  o.value !== null &&
                                  Number.isFinite(o.value)
                                    ? 'numeric-value numeric-cell hf-mono'
                                    : undefined
                                }
                              >
                                {o.availability === 'available' &&
                                o.value !== null &&
                                Number.isFinite(o.value) ? (
                                  <span title={`Full precision: ${o.value}`}>
                                    {formatNumber(o.value)}
                                  </span>
                                ) : (
                                  <>
                                    not computed
                                    {o.reason && `: ${present(o.reason, outputReasons)}`}
                                  </>
                                )}
                              </td>
                              <td>{o.units || 'dimensionless'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </DataTable>
                    </>
                  )}
                </Panel>
              </section>
              {history && (
                <>
                  <section
                    role="tabpanel"
                    id="run-panel-1"
                    aria-labelledby="run-tab-1"
                    hidden={tab !== 'Model'}
                  >
                    {history.model_snapshot ? (
                      <>
                        <SectionHeader
                          title={
                            <>
                              Model version{' '}
                              {history.model_snapshot.model_revision_id.slice(0, 8)}{' '}
                              <StatusTag>Read-only</StatusTag>
                            </>
                          }
                        />
                        {workspace}
                      </>
                    ) : (
                      <p>
                        This run's model version can't be shown. The current model is not shown in
                        its place.
                      </p>
                    )}
                  </section>
                  <section
                    role="tabpanel"
                    id="run-panel-2"
                    aria-labelledby="run-tab-2"
                    hidden={tab !== 'Configuration'}
                  >
                    <CaseNavigation.Provider value={null}>
                      <Panel className="recorded-configuration">
                        {history.configuration ? (
                          <>
                            <SectionHeader
                              title={history.configuration.name}
                              actions={
                                <>
                                  <StatusTag>Read-only</StatusTag>
                                  <RecordAttribution
                                    kind="configuration_version"
                                    id={history.configuration.configuration_revision_id}
                                  />
                                  <ConfigurationRecordDetails
                                    configuration={history.configuration}
                                  />
                                </>
                              }
                            />
                            <ConfigurationRecord
                              onViewSourceResult={onViewSourceResult}
                              configuration={history.configuration}
                              approachClosure={
                                'approach_closure' in history ? history.approach_closure : undefined
                              }
                              model={history.model_snapshot}
                              results={history.results}
                            />
                          </>
                        ) : (
                          <p>
                            This run's configuration can't be shown. The current configuration is
                            not shown in its place.
                          </p>
                        )}
                      </Panel>
                    </CaseNavigation.Provider>
                  </section>
                  <div hidden={tab !== 'Results'}>
                    <Disclosure className="run-files">
                      <summary>Run files and diagnostics</summary>
                      <SectionHeader
                        title="Run files"
                        actions={
                          <ActionDialog
                            title="Execution diagnostics and source mapping"
                            label="Diagnostics"
                          >
                            {results ? (
                              <>
                                <p>
                                  {present(results.execution.state, executionLabels)} ·{' '}
                                  {results.execution.message}
                                </p>
                                <pre tabIndex={0} aria-label="Execution diagnostics">
                                  {JSON.stringify({ execution: results.execution }, null, 2)}
                                </pre>
                              </>
                            ) : (
                              <p>No verified execution diagnostics.</p>
                            )}
                            <p>
                              Generated locations refer to the generated file this run used. Source
                              maps identify authored blocks and their transformations; they never
                              invent an authored line.
                            </p>
                            {sourceMap ? (
                              <Button
                                disabled={artifactBusy}
                                onClick={() => void readArtifact(sourceMap, 'map')}
                              >
                                Read source mapping
                              </Button>
                            ) : (
                              <p>No source mapping is available.</p>
                            )}
                            {mappings && (
                              <ul>
                                {mappings.map((m, i) => (
                                  <li key={i}>
                                    <p>
                                      {m.generated_path}:{m.generated_line_start}–
                                      {m.generated_line_end} → {m.source_path} · SHA-256{' '}
                                      {m.source_sha256}
                                    </p>
                                    <p>Transforms: {m.transforms.join(', ')}</p>
                                    <Button
                                      onClick={() =>
                                        inspect({ kind: 'instance', instance_id: m.instance_id })
                                      }
                                    >
                                      Inspect mapped source{' '}
                                      {history.model_snapshot?.instances.find(
                                        (n) => n.instance_id === m.instance_id,
                                      )?.name ?? m.instance_id}
                                    </Button>
                                  </li>
                                ))}
                              </ul>
                            )}
                          </ActionDialog>
                        }
                      />
                      <RetainedFiles
                        key={selected}
                        artifacts={history.artifacts}
                        busy={artifactBusy}
                        read={(a, mode) => void readArtifact(a, mode)}
                      />
                      {preview && (
                        <section aria-label="Artifact preview" className="hf-artifact-preview">
                          <SectionHeader
                            title={preview.artifact.name}
                            actions={
                              <Button
                                onClick={() => {
                                  artifactRequest.current++;
                                  setPreview(null);
                                }}
                              >
                                Close preview
                              </Button>
                            }
                          />
                          <p className="evidence-content">SHA-256 {preview.artifact.sha256}</p>
                          <pre ref={previewElement} tabIndex={0} aria-label="Read-only run file">
                            {preview.text}
                          </pre>
                        </section>
                      )}
                    </Disclosure>
                  </div>
                </>
              )}
            </>
          )}
        </section>
      )}
    </section>
  );
}
