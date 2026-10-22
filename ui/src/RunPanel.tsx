import { OpenLink } from './design';
import { useCollectionRead } from './useCollectionRead';
import { CollectionStatus } from './design';
import type { Selection } from './workspaceModel';
import type { CalculationScope } from './calculationScope';
import { PageHeader, RecordDetails } from './design';
import { displayUnit } from './unitLabels';
import {
  AttributionDetail,
  RecordAttribution,
  attributionText,
  useAttribution,
} from './attribution';
import { runLabel } from './recordLabels';
import { ComputationalExportDialog } from './ComputationalExportDialog';
import { ConfigurationRecord, ConfigurationRecordDetails } from './ConfigurationRecord';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { HyprnMvpApi, accessLostText, accessUnverifiedText, message } from './api';
import { useAccessLoss } from './accessLoss';
import type {
  ConfigurationRevisionRead6,
  PublicRun,
  PublicRunDetail2,
  RunHistoryRead6,
  RunHistoryItem2,
  ModifiedRunSeedRead6,
} from './api';
import {
  Button,
  Panel,
  Tabs,
  TextInput,
  Select,
  DataTable,
  RecordBar,
  StatusTag,
  Progress,
  SectionHeader,
  ResourceCard,
  ActionGroup,
  formatNumber,
} from './design';
import { modelPorts, refKey, RuntimeComparisonView } from './ConfigurationPanel';
import { executionStatus } from './runStatus';
import { configurationContext, recordLimitations } from './recordViews';

const historyErrors: Record<RunHistoryRead6['errors'][number]['code'], string> = {
  history_not_recorded: "This run's record is not available yet.",
  missing_results: 'Some results are missing. What is available is shown below.',
  missing_artifacts: 'This run file is unavailable.',
  missing_or_invalid_artifact: 'This run file is unavailable.',
  corrupt_retained_record:
    "Part of this run's record could not be verified. Verified sections remain visible.",
  unsupported_record_version: 'This run uses a record format this application cannot display.',
};
export function runPending(run: PublicRun) {
  return (
    ['accepted_run', 'prepared', 'dispatching', 'uncertain'].includes(run.state) ||
    (run.state === 'recorded' &&
      !['finished', 'excepted', 'killed'].includes(run.process_state ?? 'unknown'))
  );
}
function progressLabel(run: PublicRun) {
  if (run.state === 'accepted_run') return 'Queued for preparation';
  if (run.state === 'prepared') return 'Prepared — waiting to start';
  if (run.state === 'dispatching') return 'Starting run';
  return run.process_state === 'running' ? 'Run running' : 'Waiting for execution results';
}
const present = (value: unknown, labels: Record<string, string>) =>
  value == null
    ? 'Not available'
    : typeof value === 'string' && Object.hasOwn(labels, value)
      ? labels[value]
      : 'Unknown';
const outputReasons = {
  producer_failed: 'Producer failed',
  unassigned: 'Not assigned',
  nonfinite: 'Non-finite value',
  unavailable: 'Unavailable',
};
const tabs = ['Results', 'Model', 'Configuration'] as const;
type HistoryTab = (typeof tabs)[number];
export type RunFilters = { text: string; state: string };
export const emptyRunFilters: RunFilters = { text: '', state: '' };

export function RunPanel({
  active = true,
  modelScope,
  filters: hostFilters,
  onFilters,
  onViewSourceResult,
  sourceOutput,
  resourceActionsRef,
  listEpoch = 0,
  api,
  studyId,
  submitted,
  onActive,
  onCreateModified,
  navigate,
  onInspection,
  onHistory,
  workspace,
  onSelect,
}: {
  active?: boolean;
  modelScope?: CalculationScope;
  onViewSourceResult?: (runId: string, output: { instance_id: string; port_id: string }) => void;
  sourceOutput?: { runId: string; output: { instance_id: string; port_id: string } };
  resourceActionsRef?: (element: HTMLDivElement | null) => void;
  listEpoch?: number;
  api: HyprnMvpApi;
  studyId: string;
  submitted: PublicRun | null;
  onActive: (active: boolean) => void;
  onCreateModified: (seed: ModifiedRunSeedRead6, config: ConfigurationRevisionRead6) => void;
  navigate: (action: () => void) => void;
  onInspection?: (detail: PublicRunDetail2 | null) => void;
  /** The user explicitly returned to the run history list. */ onHistory?: () => void;
  workspace?: ReactNode;
  onSelect?: (selection: Selection) => void;
  filters?: RunFilters;
  onFilters?: (filters: RunFilters) => void;
}) {
  const [selected, setSelected] = useState(submitted?.run_id ?? '');
  const collection = useCollectionRead<RunHistoryItem2, string>({
    api,
    study: studyId,
    scope: JSON.stringify([modelScope?.model, modelScope?.revision]),
    enabled: active && (!submitted || !selected),
    load: async (cursor, signal) => {
      const page = await api.runsPage(
        studyId,
        {
          model_id: modelScope?.model,
          model_revision_id: modelScope?.revision,
          cursor,
        },
        signal,
      );
      return { rows: page.data, next: page.next_cursor ?? null };
    },
    identity: (row) => row.run_id,
  });
  const runs = collection.rows,
    listBusy = collection.busy;
  const listReady = collection.state.status === 'ready';
  const refreshList = collection.refresh;
  const listDirty = useRef(false);
  const submittedBy = useAttribution('run', selected);
  useEffect(() => {
    setSelected('');
  }, [listEpoch]);
  const [detail, setDetail] = useState<PublicRunDetail2 | null>(null);
  const [loading, setLoading] = useState(false);
  const [modifiedSeed, setModifiedSeed] = useState<ModifiedRunSeedRead6 | null>(null),
    [modifiedReason, setModifiedReason] = useState('Checking whether this run can be modified…');
  const [seedAttempt, setSeedAttempt] = useState(0),
    [seedRetry, setSeedRetry] = useState(false);
  useEffect(() => {
    let current = true;
    setModifiedSeed(null);
    setModifiedReason('Checking whether this run can be modified…');
    setSeedRetry(false);
    if (!detail || runPending(detail)) {
      setModifiedReason('Available once the run has finished.');
      return;
    }
    // The seed read is scoped by the session seam and classified like the run read. A confirmed denial
    // clears the run through the session signal; a transient study probe offers a retry.
    const read = api.fence({ studyId });
    api
      .modifiedRunSeedRead(studyId, detail.run_id, read.signal)
      .then((seed) => {
        if (current && read.valid()) {
          setModifiedSeed(seed);
          setModifiedReason('');
        }
      })
      .catch(async (e) => {
        const outcome = await api.readFailed(e, read);
        if (!current) return;
        if (outcome === 'transient') {
          setModifiedReason(accessUnverifiedText);
          setSeedRetry(true);
        } else if (outcome === 'error') setModifiedReason(message(e));
      })
      .finally(read.done);
    return () => {
      current = false;
      read.abort();
    };
  }, [api, studyId, detail?.run_id, detail?.state, detail?.process_state, seedAttempt]);
  const inspectionCallback = useRef(onInspection);
  inspectionCallback.current = onInspection;
  useEffect(() => {
    inspectionCallback.current?.(detail?.run_id === selected ? detail : null);
  }, [detail, selected]);
  const outputRoot = useRef<HTMLElement>(null);
  useEffect(() => {
    if (!sourceOutput || detail?.run_id !== sourceOutput.runId) return;
    setTab('Results');
    const frame = requestAnimationFrame(() => {
      const button = outputRoot.current?.querySelector<HTMLButtonElement>(
        `[data-source-output="${sourceOutput.output.instance_id}/${sourceOutput.output.port_id}"]`,
      );
      button?.focus();
      button?.scrollIntoView({ block: 'center' });
    });
    return () => cancelAnimationFrame(frame);
  }, [
    detail?.run_id,
    sourceOutput?.runId,
    sourceOutput?.output.instance_id,
    sourceOutput?.output.port_id,
  ]);
  const [tab, setTab] = useState<HistoryTab>('Results'),
    [localFilters, setLocalFilters] = useState<RunFilters>(emptyRunFilters);
  // The host may retain filters across navigation and return.
  const filters = hostFilters ?? localFilters,
    setFilters = (next: Partial<RunFilters>) => {
      const value = { ...filters, ...next };
      if (onFilters) onFilters(value);
      else setLocalFilters(value);
    };
  const filter = filters.text,
    stateFilter = filters.state;
  useEffect(() => setTab('Results'), [selected]);
  const [error, setError] = useState<unknown>(null);
  const generation = useRef(0);
  const alive = useRef(true);
  const detailRequest = useRef(0),
    refreshRead = useRef<() => void>(() => {});
  /** Confirmed denial (this panel's own read or any host of this study): clear the
   * run list, the run record and its history, stop status
   * backoff and drop every pending reply. Nothing is submitted. */
  // After a cleared record, "Refresh run status" starts a fresh, newly scoped read.
  const [reload, setReload] = useState(0);
  function clearProtected() {
    generation.current++;
    detailRequest.current++;
    refreshRead.current = () => setReload((n) => n + 1);
    setSelected('');
    setDetail(null);
    setLoading(false);
    setModifiedSeed(null);
    setSeedRetry(false);
    setError(new Error(accessLostText));
  }
  useAccessLoss(api, studyId, (change) => {
    if (change.kind === 'access-lost') clearProtected();
  });
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      generation.current++;
    };
  }, [studyId]);
  useEffect(() => {
    if (submitted) {
      setSelected(submitted.run_id);
    }
  }, [submitted?.run_id]);
  useEffect(() => {
    const token = ++generation.current;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let failures = 0;
    setDetail(null);
    setError(null);
    if (!selected) {
      setLoading(false);
      return;
    }
    setLoading(true);
    async function read(manual = false) {
      if (timer) {
        clearTimeout(timer);
        timer = undefined;
      }
      // A cleared panel (confirmed denial) or a newer selection never reads again from this effect.
      if (!alive.current || token !== generation.current) return;
      const request = ++detailRequest.current,
        fence = api.fence({ studyId }),
        current = () =>
          alive.current &&
          token === generation.current &&
          request === detailRequest.current &&
          fence.valid();
      if (manual) {
        setLoading(true);
        setError(null);
      }
      try {
        const value = await api.run(studyId, selected);
        if (!current()) return;
        setDetail(value);
        setError(null);
        failures = 0;
        if (submitted?.run_id === value.run_id) onActive(runPending(value));
        if (runPending(value))
          timer = setTimeout(() => void read(), value.state === 'uncertain' ? 5000 : 1500);
        else listDirty.current = true;
      } catch (e) {
        // Confirmed denial clears through the session signal and schedules nothing.
        const outcome = await api.readFailed(e, fence);
        if ((outcome === 'error' || outcome === 'transient') && current()) {
          setError(outcome === 'transient' ? new Error(accessUnverifiedText) : e);
          failures++;
          timer = setTimeout(() => void read(), Math.min(1000 * 2 ** failures, 10000));
        }
      } finally {
        fence.done();
        if (current()) setLoading(false);
      }
    }
    refreshRead.current = () => void read(true);
    void read();
    return () => {
      generation.current++;
      detailRequest.current++;
      refreshRead.current = () => {};
      if (timer) clearTimeout(timer);
    };
  }, [selected, studyId, submitted?.run_id, reload]);
  function refreshDetail() {
    refreshRead.current();
  }
  const history = detail?.history,
    results = history?.results;
  const scopedRuns = runs;
  const visibleRuns = scopedRuns.filter(
    (r) =>
      `${runLabel(r)} ${r.run_id} ${r.configuration_revision_id}`
        .toLowerCase()
        .includes(filter.trim().toLowerCase()) &&
      (!stateFilter || executionStatus(r).label === stateFilter),
  );
  function openTab(name: HistoryTab) {
    setTab(name);
    const id = 'run-tab-' + tabs.indexOf(name);
    requestAnimationFrame(() => {
      document.getElementById(id)?.focus();
      document.getElementById(id)?.scrollIntoView({ block: 'nearest' });
    });
  }
  function inspect(selection: Selection) {
    const dialog = document.activeElement?.closest('dialog');
    if (dialog instanceof HTMLDialogElement) dialog.close();
    onSelect?.(selection);
    setTab('Model');
    requestAnimationFrame(() => {
      document.getElementById('run-tab-1')?.focus();
      document.getElementById('run-tab-1')?.scrollIntoView({ block: 'nearest' });
    });
  }
  const ports = history?.model_snapshot ? modelPorts(history.model_snapshot) : [];
  const label = (target: { instance_id: string; port_id: string }) =>
    ports.find((p) => refKey(p.target) === refKey(target))?.label ?? refKey(target);
  const execution = detail ? executionStatus(detail) : null;
  const elapsed = detail?.execution_summary?.duration_seconds;
  return (
    <section ref={outputRoot} aria-label="Runs" className="run-panel">
      <Panel hidden={!!selected} label="Run history" bodyClassName="hf-flow">
        <CollectionStatus
          entity={{ singular: 'run', plural: 'runs' }}
          state={collection.state}
          matches={filter.trim() || stateFilter ? visibleRuns.length : undefined}
          onMore={() => void collection.more()}
          onRetry={() => void collection.retry()}
          actions={
            <Button disabled={listBusy} onClick={() => void refreshList()}>
              Refresh runs
            </Button>
          }
        />
        {!!runs.length && (
          <ActionGroup className="hf-collection-filters">
            <label>
              Filter runs
              <TextInput
                type="search"
                value={filter}
                onChange={(e) => setFilters({ text: e.target.value })}
              />
            </label>
            <label>
              Execution status
              <Select value={stateFilter} onChange={(e) => setFilters({ state: e.target.value })}>
                <option value="">All states</option>
                {[...new Set(runs.map((r) => executionStatus(r).label))].map((status) => (
                  <option key={status} value={status}>
                    {status}
                  </option>
                ))}
              </Select>
            </label>
          </ActionGroup>
        )}
        {visibleRuns.map((r) => (
          <ResourceCard
            key={r.run_id}
            level={3}
            title={runLabel(r)}
            facts={[
              <StatusTag tone={executionStatus(r).tone}>{executionStatus(r).label}</StatusTag>,
            ]}
            actions={
              <OpenLink
                aria-label={`Inspect run ${r.run_id}`}
                onClick={() => navigate(() => setSelected(r.run_id))}
              >
                Open run
              </OpenLink>
            }
          />
        ))}
      </Panel>
      {selected && (
        <section aria-label="Run details" className="hf-flow hf-flow--sections">
          {modifiedReason && <p role="status">{modifiedReason}</p>}
          {seedRetry && (
            <Button onClick={() => setSeedAttempt((n) => n + 1)}>Check modified run again</Button>
          )}
          <RuntimeComparisonView comparison={detail?.runtime_comparison} />
          <RecordBar
            title="Saved run · read-only"
            returnLabel="Return to run history"
            onReturn={() => {
              generation.current++;
              setSelected('');
              setDetail(null);
              onHistory?.();
              if (!listReady || listDirty.current) {
                listDirty.current = false;
                void refreshList();
              }
            }}
          />
          <PageHeader
            className="run-heading"
            title={history?.configuration?.name ?? 'Run record'}
            details={
              <>
                {history && (
                  <RecordDetails
                    kind="Run"
                    recordId={selected}
                    metadata={
                      <>
                        {execution && <StatusTag tone={execution.tone}>{execution.label}</StatusTag>}
                        <RecordAttribution kind="run" id={selected} inline />
                      </>
                    }
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
                      {'assessment' in history && history.assessment && (
                        <>
                          <dt>Recorded criterion evaluator</dt>
                          <dd>{history.assessment.evaluator_sha256}</dd>
                        </>
                      )}
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
                  </RecordDetails>
                )}
                {!history && (
                  <RecordDetails
                    kind="Run"
                    recordId={selected}
                    metadata={
                      <>
                        {execution && <StatusTag tone={execution.tone}>{execution.label}</StatusTag>}
                        <RecordAttribution kind="run" id={selected} inline />
                      </>
                    }
                  >
                    <dl className="hf-record-details">
                      <dt>Run ID</dt>
                      <dd>{selected}</dd>
                    </dl>
                  </RecordDetails>
                )}
              </>
            }
            actions={
              <>
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
              </>
            }
          />
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
                      {detail.execution_summary?.status === 'timed_out'
                        ? 'Execution timed out'
                        : detail.process_state === 'finished'
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
                  <StatusTag tone="alarm">Preparation failed</StatusTag> The model did not run, so
                  there are no results.
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
              {history?.errors
                .filter(
                  (e) =>
                    !(
                      e.code === 'missing_results' &&
                      detail.execution_summary?.status === 'timed_out'
                    ),
                )
                .map((e, i) => (
                  <p role="alert" key={i}>
                    {historyErrors[e.code]}
                  </p>
                ))}
              {results?.execution.state === 'failed' && (
                <p role="alert">{results.execution.message}</p>
              )}
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
                    <p>No results for this run.</p>
                  )}
                  {results && (
                    <>
                      <SectionHeader
                        title="Outputs"
                        help="runOutputs"
                        actions={
                          elapsed != null && Number.isFinite(elapsed) && elapsed >= 0 ? (
                            <span
                              className="hf-header-metric"
                              title="Total execution duration, including startup and shutdown"
                            >
                              Duration <span className="hf-mono">{formatNumber(elapsed)} s</span>
                            </span>
                          ) : undefined
                        }
                      />
                      <DataTable regionLabel="Output values">
                        <thead>
                          <tr>
                            <th>Output</th>
                            <th className="hf-th--num">Value</th>
                            <th>Units</th>
                          </tr>
                        </thead>
                        <tbody>
                          {results.outputs.map((o) => (
                            <tr key={refKey(o.target)}>
                              <th scope="row">
                                <OpenLink
                                  size="sm"
                                  disabled={!history?.model_snapshot}
                                  onClick={() => inspect({ kind: 'variable', ...o.target })}
                                  data-source-output={refKey(o.target)}
                                  aria-label={`Inspect output ${label(o.target)}`}
                                >
                                  {label(o.target)}
                                </OpenLink>
                              </th>
                              <td
                                className={
                                  o.availability === 'available' &&
                                  o.value !== null &&
                                  Number.isFinite(o.value)
                                    ? 'num'
                                    : 'missing'
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
                              <td>{o.units ? displayUnit(o.units) : 'dimensionless'}</td>
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
                              Model <StatusTag>Read-only</StatusTag>
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
                    <>
                      <Panel className="recorded-configuration">
                        {history.configuration ? (
                          <>
                            <SectionHeader title={history.configuration.name} />
                            <ConfigurationRecordDetails
                              configuration={history.configuration}
                              metadata={
                                <>
                                  <StatusTag>Read-only</StatusTag>
                                  <RecordAttribution
                                    kind="configuration_version"
                                    id={history.configuration.configuration_revision_id}
                                  />
                                </>
                              }
                            />
                            <ConfigurationRecord
                              onViewSourceResult={onViewSourceResult}
                              api={api}
                              configuration={history.configuration}
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
                    </>
                  </section>
                </>
              )}
            </>
          )}
        </section>
      )}
    </section>
  );
}
