import { RecordAttribution } from './attribution';
import { useEffect, useId, useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import {
  ApiError,
  HyprnMvpApi,
  accessDenied,
  accessLostText,
  type EvidenceRecord,
  type ReadFailure,
  type ReadFence,
} from './api';
import { useAccessLoss } from './accessLoss';
import type {
  ScientificAnswer1,
  FrozenConfigurationRead7,
  ApproachSavedRead3,
  ApproachUsage1,
  ApproachUsageCursor1,
  PublicRunDetail,
  ResolvedInput2,
  ResultBinding,
} from './contract';
import { EvidenceRecordBody } from './EvidenceView';
import {
  ActionDialog,
  Button,
  DataTable,
  DialogFrame,
  Disclosure,
  Panel,
  Select,
  StatusTag,
  formatNumber,
} from './design';
import { ApproachCaseContext } from './ApproachAssumptions';
import { RunOutcomes, runOutcomes } from './runStatus';
import { criterionOperators } from './criterionLabels';
import { resolvedUnit, unitLabel } from './unitLabels';
import type { WorkspaceLink } from './workspaceModel';

type Configuration = NonNullable<NonNullable<PublicRunDetail['history']>['configuration']>;
type Row = {
  usage: ApproachUsage1;
  configuration?: Configuration;
  run?: PublicRunDetail;
  loading?: boolean;
  error?: string;
};
type SourceRead = { state: 'loading' | 'error' | 'ready'; run?: PublicRunDetail };

/** Scientific prose is displayed only from an explicitly associated answer record. */
function ScientificAnswer({
  answer,
  api,
  studyId,
  onOpen,
  recordOnly = false,
  support,
}: {
  recordOnly?: boolean;
  support?: ReactNode;
  answer: ScientificAnswer1;
  api: HyprnMvpApi;
  studyId: string;
  onOpen: (target: WorkspaceLink) => void;
}) {
  return (
    <div className="approach-answer-record">
      <h4>Observations</h4>
      <p className="context-copy">{answer.observations}</p>
      <h4>Interpretation</h4>
      <p className="context-copy">{answer.interpretation}</p>
      {!!answer.qualifications.length && (
        <>
          <h4>Qualifications</h4>
          <ul>
            {answer.qualifications.map((value, index) => (
              <li key={index}>{value}</li>
            ))}
          </ul>
        </>
      )}
      {!!answer.open_deliverables.length && (
        <>
          <h4>Still to answer</h4>
          <ul>
            {answer.open_deliverables.map((value, index) => (
              <li key={index}>{value}</li>
            ))}
          </ul>
        </>
      )}
      {!recordOnly && (
        <>
          {support}
          {!!answer.basis.evidence_version_ids.length && (
            <div className="answer-support">
              <h4>Sources</h4>
              <div className="answer-source-actions">
                {answer.basis.evidence_version_ids.map((id) => (
                  <AnswerBasis
                    key={id}
                    kind="evidence"
                    id={id}
                    api={api}
                    studyId={studyId}
                    onOpen={onOpen}
                  />
                ))}
              </div>
            </div>
          )}
        </>
      )}
      <ActionDialog title="Answer record details" label="Record details" size="sm" variant="quiet">
        <dl className="answer-record-details">
          <dt>Answer version</dt>
          <dd>
            {answer.version_number} · <code>{answer.answer_version_id}</code>
          </dd>
          <dt>Approach version</dt>
          <dd>
            <code>{answer.approach_version_id}</code>
          </dd>
          {answer.case_id && (
            <>
              <dt>Case</dt>
              <dd>
                <code>{answer.case_id}</code>
              </dd>
            </>
          )}
          <dt>Recorded by</dt>
          <dd>{answer.created_by}</dd>
          <dt>Recorded at</dt>
          <dd>{answer.created_at}</dd>
          <dt>Digest</dt>
          <dd>
            <code>{answer.digest}</code>
          </dd>
          {Object.entries(answer.basis).map(([kind, ids]) =>
            ids.length ? (
              <div key={kind}>
                <dt>{kind.replaceAll('_', ' ')}</dt>
                <dd>
                  {ids.map((id) => (
                    <p key={id}>
                      <code>{id}</code>
                    </p>
                  ))}
                </dd>
              </div>
            ) : null,
          )}
        </dl>
      </ActionDialog>
    </div>
  );
}

/** Basis records load on explicit request, always by their saved version identity. */
function AnswerBasis({
  kind,
  id,
  api,
  studyId,
  onOpen,
  label,
  title: namedTitle,
}: {
  label?: string;
  title?: string;
  kind: 'evidence' | 'answer';
  id: string;
  api: HyprnMvpApi;
  studyId: string;
  onOpen: (target: WorkspaceLink) => void;
}) {
  const [record, setRecord] = useState<EvidenceRecord | ScientificAnswer1 | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState('');
  const scope = useRef<ReadFence | null>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const invoker = useRef<HTMLElement | null>(null);
  const headingId = useId();
  const title = namedTitle ?? (kind === 'evidence' ? 'Source record' : 'Case answer record');
  const identity = useRef<{ api: HyprnMvpApi; studyId: string; id: string; kind: string } | null>(
    null,
  );
  useEffect(() => {
    function clear() {
      scope.current?.abort();
      setRecord(null);
      dialog.current?.close();
      setBusy(false);
      setError('');
    }
    clear();
    const unsubscribe = api.onSessionChange((change) => {
      if (change.kind !== 'access-lost' || change.studyId === studyId) clear();
    });
    return () => {
      scope.current?.abort();
      unsubscribe();
    };
  }, [api, studyId, id, kind, api.actor, api.csrf]);
  const current = identity.current;
  const visibleRecord =
    current?.api === api &&
    current.studyId === studyId &&
    current.id === id &&
    current.kind === kind &&
    scope.current?.valid()
      ? record
      : null;
  async function load() {
    scope.current?.abort();
    const read = api.fence({ studyId });
    scope.current = read;
    identity.current = { api, studyId, id, kind };
    setBusy(true);
    setError('');
    try {
      const value = await queueFor(api).read<EvidenceRecord | ScientificAnswer1>(
        () => read.valid(),
        () =>
          kind === 'evidence'
            ? api.evidenceVersion(studyId, id, read.signal)
            : api.answer(studyId, id, read.signal),
      );
      if (value && read.valid()) {
        if (
          ('answer_version_id' in value ? value.answer_version_id : value.evidence_version_id) !==
          id
        )
          throw new Error('Answer basis identity mismatch');
        setRecord(value);
      }
    } catch (error) {
      const result = await api.readFailed(error, read);
      if (read.valid() && result !== 'stale' && result !== 'access-lost')
        setError('This answer basis could not be loaded. Retry the read.');
    } finally {
      if (read.valid()) setBusy(false);
      read.done();
    }
  }
  useEffect(() => {
    if (kind === 'evidence') void load();
  }, [api, studyId, id, kind, api.actor, api.csrf]);
  if (kind === 'evidence') return visibleRecord && !('answer_version_id' in visibleRecord)
    ? <EvidenceRecordBody compact brief record={visibleRecord} />
    : <div className="answer-evidence-loading">
        <p role={error ? 'alert' : 'status'}>{error || 'Loading evidence…'}</p>
        {error && <Button onClick={() => void load()}>Retry evidence</Button>}
      </div>;
  return (
    <>
      <Button
        aria-haspopup="dialog"
        onClick={() => {
          invoker.current = document.activeElement as HTMLElement;
          dialog.current?.showModal();
          if (!visibleRecord) void load();
        }}
      >
        {label ??
          'View case answer version ' +
            id.slice(0, 8)}
      </Button>
      <DialogFrame
        ref={dialog}
        className="action-dialog"
        aria-labelledby={headingId}
        onClose={() => {
          if (invoker.current?.isConnected) invoker.current.focus();
        }}
      >
        <div className="dialog-heading">
          <h2 id={headingId}>{title}</h2>
        </div>
        <div className="dialog-body">
          {busy && <p role="status">Loading record…</p>}
          {error && <p role="alert">{error}</p>}
          {error && <Button onClick={() => void load()}>Retry record</Button>}
          {visibleRecord &&
            ('answer_version_id' in visibleRecord ? (
              <ScientificAnswer
                recordOnly
                answer={visibleRecord}
                api={api}
                studyId={studyId}
                onOpen={onOpen}
              />
            ) : (
              <EvidenceRecordBody record={visibleRecord} />
            ))}
        </div>
        <div className="dialog-footer">
          <Button onClick={() => dialog.current?.close()}>Done</Button>
        </div>
      </DialogFrame>
    </>
  );
}
const identity = (usage: ApproachUsage1) =>
  usage.kind + '/' + (usage.kind === 'run' ? usage.run_id : usage.configuration_revision_id);
const sameTarget = (
  a: { instance_id: string; port_id: string },
  b: { instance_id: string; port_id: string },
) => a.instance_id === b.instance_id && a.port_id === b.port_id;

/** Equality uses retained numbers and the selected model, never display labels,
 * current model heads, browser digests, or conversion arithmetic. */
export function sourceMatch(
  input: ResolvedInput2,
  source: PublicRunDetail,
): 'verified' | 'unavailable' | 'mismatch' {
  const binding = input.result_binding,
    history = source.history;
  if (
    !binding ||
    source.retained_integrity?.schema_version !== '1' ||
    !source.retained_integrity.results_digest ||
    !history?.configuration ||
    !history.model_snapshot ||
    !history.results
  )
    return 'unavailable';
  const outputs = history.results.outputs.filter((output) =>
    sameTarget(output.target, binding.source_output),
  );
  const instances = history.model_snapshot.instances.filter(
    (instance) => instance.instance_id === binding.source_output.instance_id,
  );
  const definitions = history.model_snapshot.definitions.filter(
    (definition) => definition.definition_version_id === instances[0]?.definition_version_id,
  );
  const ports = definitions.flatMap((definition) =>
    definition.ports.filter(
      (port) => port.port_id === binding.source_output.port_id && port.direction === 'output',
    ),
  );
  const output = outputs[0];
  return source.run_id === binding.source_run_id &&
    history.results.run_id === binding.source_run_id &&
    source.retained_integrity.results_digest === binding.results_digest &&
    history.configuration.digest === binding.source_configuration_digest &&
    outputs.length === 1 &&
    instances.length === 1 &&
    definitions.length === 1 &&
    ports.length === 1 &&
    output.availability === 'available' &&
    output.assigned &&
    output.producer_completed &&
    output.value !== null &&
    Number.isFinite(output.value) &&
    output.value === binding.original_value &&
    output.units === binding.original_units &&
    ports[0].units != null &&
    resolvedUnit(ports[0].units) !== undefined &&
    resolvedUnit(ports[0].units) === output.units &&
    input.value === binding.original_value &&
    input.units === binding.original_units &&
    Number.isFinite(input.value)
    ? 'verified'
    : 'mismatch';
}

export function groupFindings(saved: ApproachSavedRead3, rows: Row[], caseId: string) {
  return [
    ...saved.version.content.cases
      .filter((item) => !caseId || item.case_id === caseId)
      .map((item) => ({
        id: item.case_id,
        title: item.title,
        item,
        rows: rows.filter((row) => row.usage.case_id === item.case_id),
      })),
    ...(!caseId
      ? [
          {
            id: 'none',
            title: 'No specific case',
            item: null,
            rows: rows.filter((row) => row.usage.case_id === null),
          },
        ]
      : []),
  ];
}

/** One shared queue persists across review generations. Stale queued work is
 * discarded; already-started transport occupies its slot until it settles. */
class ReadQueue {
  private active = 0;
  private pending: Array<() => void> = [];
  read<T>(valid: () => boolean, fetch: () => Promise<T>): Promise<T | undefined> {
    return new Promise((resolve, reject) => {
      this.pending.push(() => {
        if (!valid()) {
          resolve(undefined);
          this.pump();
          return;
        }
        this.active++;
        fetch()
          .then(resolve, reject)
          .finally(() => {
            this.active--;
            this.pump();
          });
      });
      this.pump();
    });
  }
  private pump() {
    while (this.active < 2 && this.pending.length) this.pending.shift()!();
  }
}

const queues = new WeakMap<HyprnMvpApi, ReadQueue>();
function queueFor(api: HyprnMvpApi) {
  let queue = queues.get(api);
  if (!queue) {
    queue = new ReadQueue();
    queues.set(api, queue);
  }
  return queue;
}

function RunFacets({ run }: { run: PublicRunDetail }) {
  const results = run.history?.results;
  if (!results)
    return (
      <p>
        {['accepted_run', 'prepared', 'dispatching'].includes(run.state)
          ? 'Not yet available'
          : 'Results unavailable'}
      </p>
    );
  // Execution and Criteria only; a failure keeps its bounded diagnostic beside Execution.
  return (
    <>
      <RunOutcomes
        variant="ledger"
        outcomes={runOutcomes(run)}
        executionDetail={
          results.execution.state === 'failed' ? results.execution.message : undefined
        }
      />
      <ul aria-label="Individual criterion outcomes">
        {results.criteria.map((item, index) => (
          <li key={item.criterion_id}>
            <StatusTag
              tone={
                item.outcome === 'met' ? 'ok' : item.outcome === 'violated' ? 'alarm' : 'advisory'
              }
            >
              {item.outcome === 'met'
                ? 'Met'
                : item.outcome === 'violated'
                  ? 'Not met'
                  : 'Not evaluated'}
            </StatusTag>{' '}
            · Criterion {index + 1} · {item.reason.replaceAll('_', ' ')}
          </li>
        ))}
      </ul>
    </>
  );
}

function RecordedOutputs({ run }: { run: PublicRunDetail }) {
  const outputs = run.history?.results?.outputs ?? [];
  const name = (target: { instance_id: string; port_id: string }) => {
    const model = run.history?.model_snapshot,
      instance = model?.instances.find((item) => item.instance_id === target.instance_id),
      port = model?.definitions
        .find((item) => item.definition_version_id === instance?.definition_version_id)
        ?.ports.find((item) => item.port_id === target.port_id);
    return instance && port
      ? `${instance.name} · ${port.name}`
      : `${target.instance_id} / ${target.port_id}`;
  };
  function table(exact: boolean) {
    return (
      <DataTable regionLabel={exact ? 'Full-precision output values' : 'Output values'}>
        <thead>
          <tr>
            <th>Output</th>
            <th>Value</th>
            <th>Units</th>
          </tr>
        </thead>
        <tbody>
          {outputs.map((output, index) => (
            <tr key={index}>
              <td>{name(output.target)}</td>
              <td className="result-number">
                {output.availability === 'available' &&
                output.value !== null &&
                Number.isFinite(output.value) ? (
                  exact ? (
                    String(output.value)
                  ) : (
                    formatNumber(output.value)
                  )
                ) : (
                  <>not computed{output.reason ? ' · ' + output.reason : ''}</>
                )}
              </td>
              <td>{unitLabel(output.units)}</td>
            </tr>
          ))}
        </tbody>
      </DataTable>
    );
  }
  return (
    <>
      <div className="section-actions">
        <h4>Outputs</h4>

      </div>
      {table(false)}
    </>
  );
}

function SourceInputs({
  configuration,
  sources,
  load,
  onOpen,
}: {
  configuration: Configuration;
  sources: Map<string, SourceRead>;
  load: (ids: string[], retry?: boolean) => void;
  onOpen: (runId: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const inputs = configuration.inputs.flatMap((input) =>
    'result_binding' in input && input.result_binding ? [input] : [],
  );
  const ids = [...new Set(inputs.map((input) => input.result_binding!.source_run_id))];
  const checked = ids.filter((id) => sources.get(id)?.state === 'ready').length,
    missing = ids.filter((id) => !sources.has(id)),
    failed = ids.filter((id) => sources.get(id)?.state === 'error'),
    busy = ids.some((id) => sources.get(id)?.state === 'loading');
  if (!inputs.length) return null;
  return (
    <section aria-label="Source-linked inputs">
      <Button aria-expanded={open} onClick={() => setOpen((value) => !value)}>
        Review source-linked inputs
      </Button>
      {open && (
        <>
          <p role="status">
            {checked} / {ids.length} source runs checked / referenced
            {busy ? ' · Loading upstream qualifications…' : ''}
          </p>
          {checked === 0 && <p>Upstream qualifications not loaded</p>}
          <p>
            These qualifications belong to the source runs; they do not change the outcomes shown
            here.
          </p>
          <div className="section-actions">
            {!!missing.length && (
              <Button disabled={busy} onClick={() => load(missing)}>
                {checked || failed.length
                  ? 'Load more source runs'
                  : 'Load upstream qualifications'}
              </Button>
            )}
            {!!failed.length && (
              <Button disabled={busy} onClick={() => load(failed, true)}>
                Retry upstream read
              </Button>
            )}
          </div>
          {inputs.map((input, index) => {
            const binding: ResultBinding = input.result_binding!,
              read = sources.get(binding.source_run_id),
              match = read?.run ? sourceMatch(input, read.run) : undefined;
            return (
              <article className="approach-case" key={index}>
                <h4>Source-linked input {index + 1}</h4>
                <p>
                  Source output {binding.labels.instance_name} · {binding.labels.output_name}
                </p>
                <p>
                  Original {String(binding.original_value)} {unitLabel(binding.original_units)}
                </p>
                <p>
                  Conversion: {unitLabel(binding.conversion.source_units)} →{' '}
                  {unitLabel(binding.conversion.destination_units)} · factor{' '}
                  {String(binding.conversion.factor)} · received{' '}
                  {String(binding.conversion.destination_value)}{' '}
                  {unitLabel(binding.conversion.destination_units)}
                </p>
                {!read ? (
                  <p>Not loaded</p>
                ) : read.state === 'loading' ? (
                  <p role="status">Loading upstream qualifications…</p>
                ) : read.state === 'error' || match === 'unavailable' ? (
                  <p role="alert">Upstream record unavailable</p>
                ) : match === 'mismatch' ? (
                  <p role="alert">Source binding mismatch</p>
                ) : (
                  read.run && (
                    <>
                      <StatusTag tone="inert">Verified source identity</StatusTag>
                      <RunFacets run={read.run} />
                      {read.run.history?.results?.criteria.some(
                        (item) => item.outcome === 'violated',
                      ) && <p>Upstream criterion not met</p>}
                      {read.run.history?.results?.criteria.some(
                        (item) => item.outcome === 'unresolved',
                      ) && <p>Upstream criterion not evaluated</p>}
                      {!!read.run.history?.errors.length && (
                        <p>
                          Source diagnostics:{' '}
                          {read.run.history.errors.map((item) => item.code).join(', ')}
                        </p>
                      )}
                    </>
                  )
                )}
                <Button onClick={() => onOpen(binding.source_run_id)}>View upstream run</Button>
              </article>
            );
          })}
        </>
      )}
    </section>
  );
}

/** One recorded run (or a configuration without a loaded run) inside its case card: name and
 * short id, the shared Execution · Criteria outcomes, the exact criterion facts, and on demand
 * the run's details and source-linked inputs. Recorded facts only; never a verdict. */
function FindingRow({
  row,
  saved,
  sources,
  load,
  retry,
  onOpen,
  hideSources = false,
  cited,
}: {
  hideSources?: boolean;
  cited?: boolean;
  row: Row;
  saved?: Configuration;
  sources: Map<string, SourceRead>;
  load: (ids: string[], retry?: boolean) => void;
  retry: () => void;
  onOpen: (target: WorkspaceLink) => void;
}) {
  // A run without retained history (queued, preparing) is named by its loaded saved configuration.
  const [details, setDetails] = useState(false),
    { usage, run } = row,
    configuration = row.configuration ?? saved;
  const id = usage.kind === 'run' ? usage.run_id : usage.configuration_revision_id;
  return (
    <article className="approach-finding" aria-label={usage.kind + ' ' + id}>
      <div className="approach-finding-head">
        <h4>
          {usage.kind === 'run'
            ? 'Run ' + id.slice(0, 8)
            : (configuration?.name ?? 'Configuration ' + id.slice(0, 8))}
        </h4>
        <Button
          size="sm"
          onClick={() =>
            onOpen({
              view: usage.kind === 'run' ? 'runs' : 'configurations',
              ...(usage.kind === 'run'
                ? { run: usage.run_id }
                : { configuration: usage.configuration_revision_id }),
            })
          }
        >
          {usage.kind === 'run' ? 'View run' : 'View configuration'}
        </Button>
      </div>
      {cited !== undefined && (
        <p className="context-line">{cited ? 'Used in this answer' : 'Additional run'}</p>
      )}
      {row.loading && <p role="status">Loading record…</p>}
      {row.error && (
        <>
          <p role="alert">{row.error}</p>
          <Button onClick={retry}>Retry record</Button>
        </>
      )}
      {usage.kind === 'configuration' && configuration && (
        <p className="context-line">Saved configuration</p>
      )}
      {run && (
        <>
          <RecordAttribution kind="run" id={run.run_id} line />

          {!run.history?.results && (
            <p className="context-line">
              {['accepted_run', 'prepared', 'dispatching'].includes(run.state)
                ? 'Results not yet available'
                : 'No results for this run'}
            </p>
          )}

          <div className="section-actions approach-finding-actions">
            <Button size="sm" aria-expanded={details} onClick={() => setDetails((value) => !value)}>
              Run details
            </Button>
          </div>
          {details && (
            <div className="approach-finding-details">
              <RunFacets run={run} />
              <CriterionFacts run={run} />
              {run.history?.results && <RecordedOutputs run={run} />}{' '}
              {!!run.history?.errors.length && (
                <p>Diagnostics: {run.history.errors.map((item) => item.code).join(', ')}</p>
              )}
            </div>
          )}
        </>
      )}
      {configuration && !hideSources && (
        <SourceInputs
          configuration={configuration}
          sources={sources}
          load={load}
          onOpen={(runId) => onOpen({ study: configuration.study_id, view: 'runs', run: runId })}
        />
      )}
    </article>
  );
}

/** Configuration identity groups its runs; names never establish the relationship. */
function SupportingResults({
  rows,
  basis,
  renderRun,
  configurationDetails,
  api,
  studyId,
  onOpen,
  caseAnswers = [],
  complete,
  heading = true,
}: {
  heading?: boolean;
  rows: Row[];
  basis?: ScientificAnswer1['basis'];
  renderRun?: (row: Row, configuration?: Configuration) => ReactNode;
  configurationDetails?: (row: Row) => ReactNode;
  api: HyprnMvpApi;
  studyId: string;
  onOpen: (target: WorkspaceLink) => void;
  caseAnswers?: { id: string; title: string }[];
  complete: boolean;
}) {
  const ids = [
    ...new Set([
      ...rows.map((row) => row.usage.configuration_revision_id),
      ...(basis?.configuration_revision_ids ?? []),
    ]),
  ];
  const knownRuns = new Set(
    rows.flatMap((row) => (row.usage.kind === 'run' ? [row.usage.run_id] : [])),
  );
  const unresolvedRuns = (basis?.run_ids ?? []).filter((id) => !knownRuns.has(id));
  if (!ids.length && !unresolvedRuns.length && !caseAnswers.length) return null;
  return (
    <div className="answer-support" role="group" aria-label="Supporting results">
      {heading && <h4>Supporting results</h4>}
      {ids.map((id) => {
        const related = rows.filter((row) => row.usage.configuration_revision_id === id);
        const configurationRow = related.find((row) => row.usage.kind === 'configuration');
        const configuration = related.find((row) => row.configuration)?.configuration;
        const runs = related.filter((row) => row.usage.kind === 'run');
        const cited = basis?.configuration_revision_ids.includes(id);
        return (
          <section className="support-configuration" key={id} aria-label={'Configuration ' + id}>
            <div className="support-record-row">
              <div>
                <strong>{configuration?.name ?? 'Configuration ' + id.slice(0, 8)}</strong>
                {basis && (
                  <p className="context-line">
                    {cited ? 'Used in this answer' : 'Associated configuration'}
                  </p>
                )}
              </div>
              <div className="support-record-actions">
                <Button
                  size="sm"
                  onClick={() =>
                    onOpen({ study: studyId, view: 'configurations', configuration: id })
                  }
                >
                  View configuration
                </Button>
              </div>
            </div>
            {configurationRow?.error && <p role="alert">{configurationRow.error}</p>}
            {configurationRow && configurationDetails?.(configurationRow)}
            {runs.map((row) =>
              renderRun ? (
                renderRun(row, configuration)
              ) : (
                <div className="support-record-row" key={identity(row.usage)}>
                  <span>Run {row.usage.kind === 'run' ? row.usage.run_id.slice(0, 8) : ''}</span>
                  <div className="support-record-actions">
                    <Button
                      size="sm"
                      onClick={() =>
                        row.usage.kind === 'run' &&
                        onOpen({ study: studyId, view: 'runs', run: row.usage.run_id })
                      }
                    >
                      View run
                    </Button>
                  </div>
                </div>
              ),
            )}
            {!runs.length && complete && !unresolvedRuns.length && (
              <p className="context-line">No run is associated with this configuration.</p>
            )}
          </section>
        );
      })}
      {unresolvedRuns.map((id) => (
        <div className="support-record-row" key={id}>
          <span>
            Run {id.slice(0, 8)}
            {complete ? ' · configuration details unavailable' : ''}
          </span>
          <div className="support-record-actions">
            <Button size="sm" onClick={() => onOpen({ study: studyId, view: 'runs', run: id })}>
              View run
            </Button>
          </div>
        </div>
      ))}
      {caseAnswers.map((item) => (
        <div className="support-record-row" key={item.id}>
          <span>{item.title}</span>
          <div className="support-record-actions">
            <AnswerBasis
              kind="answer"
              id={item.id}
              api={api}
              studyId={studyId}
              onOpen={onOpen}
              label="View case answer"
              title={item.title + ' · Case answer'}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

type Group = ReturnType<typeof groupFindings>[number];
const plural = (count: number, one: string, many = one + 's') =>
  `${count} ${count === 1 ? one : many}`;
const criterionWord = { met: 'Met', violated: 'Not met', unresolved: 'Not evaluated' } as const;
const criterionTone = { met: 'ok', violated: 'alarm', unresolved: 'advisory' } as const;

/** Exact recorded criterion facts of one loaded run. Each line is a fixed-threshold
 * criterion evaluation from the retained record, never a scientific assessment. */
function CriterionFacts({ run }: { run: PublicRunDetail }) {
  const results = run.history?.results,
    configuration = run.history?.configuration,
    model = run.history?.model_snapshot;
  if (!results) return null;
  const shown = results.criteria.slice(0, 3);
  const portName = (target: { instance_id: string; port_id: string }) => {
    const instance = model?.instances.find((item) => item.instance_id === target.instance_id),
      port = model?.definitions
        .find((item) => item.definition_version_id === instance?.definition_version_id)
        ?.ports.find((item) => item.port_id === target.port_id);
    return instance && port ? `${instance.name} · ${port.name}` : 'Output';
  };
  return (
    <ul
      className="approach-result-criteria"
      aria-label={`Criterion evaluations for run ${run.run_id.slice(0, 8)}`}
    >
      {shown.map((item, index) => {
        const declared = configuration?.criteria.find(
          (criterion) => criterion.criterion_id === item.criterion_id,
        );
        const output = declared
          ? results.outputs.find((value) => sameTarget(value.target, declared.target))
          : undefined;
        const recorded =
          output &&
          output.availability === 'available' &&
          output.value !== null &&
          Number.isFinite(output.value)
            ? `${String(output.value)} ${unitLabel(output.units)}`
            : 'not computed';
        return (
          <li key={item.criterion_id}>
            <StatusTag tone={criterionTone[item.outcome]}>
              {criterionWord[item.outcome]}
            </StatusTag>{' '}
            Criterion {index + 1}
            {declared ? (
              <>
                {' '}
                · {portName(declared.target)} {criterionOperators[declared.operator]}{' '}
                {String(declared.threshold)} {unitLabel(declared.units)} · output {recorded}
              </>
            ) : (
              ' · criterion definition unavailable'
            )}
          </li>
        );
      })}
      {results.criteria.length > shown.length && (
        <li>
          {plural(results.criteria.length - shown.length, 'more criterion evaluation')} in this
          run's details
        </li>
      )}
    </ul>
  );
}

/** One expandable row per case keeps every configuration and run, with its purpose
 * and explicit scientific assessment. Coverage never supplies an interpretation. */
function CaseCard({
  group,
  headingId,
  content,
  onCreateConfiguration,
  expanded,
  answer,
  answerStatus,
  support,
}: {
  support: ReactNode;
  answer: ReactNode;
  answerStatus: string;
  expanded?: number;
  group: Group;
  headingId: string;
  content: ApproachSavedRead3['version']['content'];
  onCreateConfiguration?: (caseId: string) => void;
}) {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (expanded !== undefined) setOpen(true);
  }, [expanded]);
  const item = group.item,
    binding = item?.binding_id
      ? content.model_bindings.find((b) => b.binding_id === item.binding_id)
      : undefined;
  return (
    <article className="approach-case-card" aria-labelledby={headingId}>
      <Disclosure open={open} onToggle={(event) => setOpen(event.currentTarget.open)}>
        <summary className="approach-case-toggle">
          <h3 id={headingId} tabIndex={-1}>
            {group.title}
          </h3>
          <StatusTag tone={answerStatus === 'Assessed' ? 'inert' : 'advisory'}>
            {answerStatus}
          </StatusTag>
        </summary>
        <div className="approach-case-content">
          <p className="context-copy approach-case-question">
            {item
              ? item.question || 'Case question not described'
              : 'Configurations and runs linked to this approach version without a case.'}
          </p>
          {item && (
            <>
              <h4>Purpose</h4>
              <p className="context-copy">{item.rationale || 'Rationale not described'}</p>
              <p className="context-line">
                {binding
                  ? 'Model version ' + binding.model_revision_id.slice(0, 8)
                  : 'Proposed case · no model version selected'}
              </p>
            </>
          )}
          <h4>What this case tells us</h4>
          {answer}
          {item && item.binding_id && onCreateConfiguration && (
            <Button
              aria-label={'Create configuration for ' + item.title}
              onClick={() => onCreateConfiguration(item.case_id)}
            >
              Create configuration
            </Button>
          )}
          {support}
          {item && !!item.evidence_links.length && <ApproachCaseContext item={item} />}
        </div>
      </Disclosure>
    </article>
  );
}

function RemainingWork({
  content,
  headingId,
  onViewStep,
}: {
  content: ApproachSavedRead3['version']['content'];
  headingId: string;
  onViewStep?: (stepId: string) => void;
}) {
  const steps = content.steps.filter(
    (step) => step.implementation_state !== 'linked' || step.remaining_work.trim(),
  );
  if (!steps.length) return null;
  return (
    <article className="approach-case-card" aria-labelledby={headingId}>
      <div className="approach-case-card-title">
        <StatusTag tone="inert">Not computed by this approach</StatusTag>
        <h3 id={headingId} tabIndex={-1}>
          Remaining method work
        </h3>
      </div>
      <p className="context-copy">
        Method steps that are proposed, partially linked or name remaining work. No case coverage is
        inferred from them.
      </p>
      <ul className="approach-result-runs">
        {steps.slice(0, 3).map((step) => (
          <li key={step.step_id}>
            <p>
              <strong>{step.title || 'Untitled step'}</strong> ·{' '}
              {step.implementation_state === 'proposed'
                ? 'Proposed · no model linked'
                : step.implementation_state === 'partial'
                  ? 'Partially linked'
                  : 'Linked'}
            </p>
            {step.remaining_work.trim() && <p className="context-copy">{step.remaining_work}</p>}
          </li>
        ))}
      </ul>
      {steps.length > 3 && (
        <p className="context-line">{plural(steps.length - 3, 'more step')} in Methods</p>
      )}
      {onViewStep && (
        <Button onClick={() => onViewStep(steps[0].step_id)}>View remaining method</Button>
      )}
    </article>
  );
}

/** Live usage is injected only by the saved approach screen. Historical
 * ApproachReader receives its retained closure without this component. */
export function ApproachFindings({
  api,
  studyId,
  saved,
  onOpen,
  focusCase,
  onViewStep,
  onCreateConfiguration,
  answerId,
  casesId,
  section = 'both',
}: {
  section?: 'both' | 'cases' | 'answer';
  answerId?: string;
  casesId?: string;
  api: HyprnMvpApi;
  studyId: string;
  saved: ApproachSavedRead3;
  onOpen: (target: WorkspaceLink) => void;
  focusCase?: { id: string; token: number };
  onViewStep?: (stepId: string) => void;
  onCreateConfiguration?: (caseId: string) => void;
}) {
  const [rows, setRows] = useState<Row[]>([]),
    [cursor, setCursor] = useState<ApproachUsageCursor1 | null>(null),
    [caseId, setCaseId] = useState(''),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(false),
    [denied, setDenied] = useState(false),
    [accessUnverified, setAccessUnverified] = useState(false),
    [sources, setSources] = useState(new Map<string, SourceRead>());
  const [missingCase, setMissingCase] = useState('');
  const generation = useRef(0),
    queue = useRef(queueFor(api)),
    cache = useRef(new Map<string, SourceRead>()),
    failedCursor = useRef<ApproachUsageCursor1 | null>(null);
  // Shared session fence for this review: the case filter and refresh generation
  // gate display only; a denial is confirmed against study/actor/session/access.
  const scope = useRef<ReadFence | null>(null);
  const base = useId();
  const actor = api.actor,
    version = saved.version.approach_version_id;
  const [answerReview, setAnswerReview] = useState(0);
  const [answerRead, setAnswerRead] = useState<{
    key: string;
    state: 'loading' | 'ready' | 'error';
    items: ScientificAnswer1[];
  }>({ key: '', state: 'loading', items: [] });
  const answerKey = studyId + '/' + version + '/' + actor;
  useEffect(() => {
    const read = api.fence({ studyId });
    setAnswerRead({ key: answerKey, state: 'loading', items: [] });
    void api
      .answers(studyId, version, read.signal)
      .then((result) => {
        if (!read.valid()) return;
        const cases = new Set<string | null>();
        if (
          result.approach_version_id !== version ||
          result.items.some((answer) => {
            const duplicate = cases.has(answer.case_id);
            cases.add(answer.case_id);
            return (
              duplicate ||
              answer.study_id !== studyId ||
              answer.approach_version_id !== version ||
              (answer.case_id !== null &&
                !saved.version.content.cases.some((item) => item.case_id === answer.case_id))
            );
          })
        )
          throw new Error('Answer association mismatch');
        setAnswerRead({ key: answerKey, state: 'ready', items: result.items });
      })
      .catch(async (error) => {
        const result = await api.readFailed(error, read);
        if (read.valid() && result !== 'access-lost' && result !== 'stale')
          setAnswerRead({ key: answerKey, state: 'error', items: [] });
      })
      .finally(read.done);
    return () => read.abort();
  }, [api, answerKey, answerReview]);
  const answerState = answerRead.key === answerKey ? answerRead.state : 'loading';
  const answers = answerRead.key === answerKey ? answerRead.items : [];
  const answerFor = (caseId: string | null) => {
    if (answerState === 'loading') return <p role="status">Loading scientific answer…</p>;
    if (answerState === 'error')
      return <p role="alert">Scientific answers could not be loaded. Retry the answer read.</p>;
    const answer = answers.find((item) => item.case_id === caseId);
    return answer ? (
      <ScientificAnswer
        key={answer.answer_version_id}
        answer={answer}
        api={api}
        studyId={studyId}
        onOpen={onOpen}
        support={
          caseId === null ? studySupport(answer) : supportFor(groupFindings(saved, rows, caseId)[0])
        }
      />
    ) : (
      <p>
        {caseId === null
          ? 'No study answer has been assessed.'
          : 'No case answer has been assessed.'}
      </p>
    );
  };

  const valid = (token: number) => token === generation.current && actor === api.actor;
  /** Clear this review. A confirmed denial from any host of this study runs it, and
   * this review's own confirmed denial is signalled so the approach reader clears too. */
  function clearProtected() {
    setAnswerRead({ key: '', state: 'error', items: [] });
    generation.current++;
    cache.current.clear();
    setSources(new Map());
    setRows([]);
    setCursor(null);
    setLoading(false);
    setDenied(true);
  }
  useAccessLoss(api, studyId, (change) => {
    if (change.kind === 'access-lost') clearProtected();
  });
  /** Shared classification with the fence captured when the read started (one
   * in-flight study probe per study and session). A superseded review generation
   * still confirms a denial; only its display updates are dropped. */
  async function failed(e: unknown, token: number, read: ReadFence | null): Promise<ReadFailure> {
    if (!read) return 'stale';
    const outcome = await api.readFailed(e, read);
    if (outcome === 'transient' && valid(token)) setAccessUnverified(true);
    return outcome;
  }
  /** A refused source does not disclose its body or erase authorized downstream
   * facts: confirm current study access with the shared probe instead. */
  async function checkStudyAccess(token: number) {
    const read = scope.current;
    if (!read || !valid(token)) return;
    const outcome = await api.confirmAccess(read);
    if (!valid(token)) return;
    if (outcome === 'ok') setAccessUnverified(false);
    else if (outcome === 'transient') setAccessUnverified(true);
  }
  async function detail(usage: ApproachUsage1, token: number) {
    if (!valid(token)) return;
    const read = scope.current;
    const update = (value: Partial<Row>) => {
      if (valid(token))
        setRows((old) =>
          old.map((row) => (identity(row.usage) === identity(usage) ? { usage, ...value } : row)),
        );
    };
    update({ loading: true });
    try {
      const record = await queue.current.read<FrozenConfigurationRead7 | PublicRunDetail>(
        () => valid(token),
        () =>
          usage.kind === 'run'
            ? api.run(studyId, usage.run_id)
            : api.configuration(studyId, usage.configuration_revision_id),
      );
      if (!valid(token) || !record) return;
      const run = 'run_id' in record ? record : undefined,
        configuration =
          'configuration' in record ? record.configuration : run?.history?.configuration;
      if (run && run.run_id !== (usage.kind === 'run' ? usage.run_id : ''))
        throw new Error('binding');
      if (configuration) {
        const pin = 'approach_binding' in configuration ? configuration.approach_binding : null;
        if (
          configuration.study_id !== studyId ||
          configuration.configuration_revision_id !== usage.configuration_revision_id ||
          pin?.approach_id !== saved.version.approach_id ||
          pin?.approach_version_id !== version ||
          pin.case_id !== usage.case_id ||
          pin.approach_digest !== saved.version.digest ||
          pin.closure_digest !== saved.closure.digest
        )
          throw new Error('binding');
      } else if (!run) throw new Error('binding');
      setAccessUnverified(false);
      update({ configuration: configuration ?? undefined, run });
    } catch (e) {
      const outcome = await failed(e, token, read);
      if (outcome === 'access-lost' || outcome === 'stale' || !valid(token)) return;
      update({
        error:
          e instanceof Error && e.message === 'binding'
            ? 'Record binding mismatch'
            : 'Record unavailable',
      });
    }
  }
  async function page(next: ApproachUsageCursor1 | null, token = generation.current) {
    const read = scope.current;
    setLoading(true);
    setError(false);
    failedCursor.current = next;
    try {
      const result = await queue.current.read(
        () => valid(token),
        () => api.approachUsage(studyId, version, { limit: 100, case_id: null, cursor: next }),
      );
      if (!valid(token) || !result) return;
      if (
        result.items.some(
          (item) =>
            item.case_id !== null &&
            !saved.version.content.cases.some((c) => c.case_id === item.case_id),
        )
      )
        throw new Error('binding');
      setRows((old) => {
        const map = new Map(old.map((row) => [identity(row.usage), row]));
        for (const usage of result.items)
          if (!map.has(identity(usage))) map.set(identity(usage), { usage, loading: true });
        return [...map.values()];
      });
      setCursor(result.next_cursor);
      for (const usage of result.items) void detail(usage, token);
      if (result.next_cursor) await page(result.next_cursor, token);
    } catch (e) {
      const outcome = await failed(e, token, read);
      if ((outcome === 'error' || outcome === 'transient') && valid(token)) setError(true);
    } finally {
      if (valid(token)) setLoading(false);
    }
  }
  function loadSources(ids: string[], retry = false) {
    const token = generation.current;
    const batch = [...new Set(ids)]
      .filter((id) => (retry ? cache.current.get(id)?.state === 'error' : !cache.current.has(id)))
      .slice(0, 10);
    for (const id of batch) cache.current.set(id, { state: 'loading' });
    setSources(new Map(cache.current));
    for (const id of batch)
      void queue.current
        .read(
          () => valid(token),
          () => api.run(studyId, id),
        )
        .then((run) => {
          if (valid(token) && run) {
            setAccessUnverified(false);
            cache.current.set(id, { state: 'ready', run });
            setSources(new Map(cache.current));
          }
        })
        .catch(async (e) => {
          if (!valid(token)) return;
          if (accessDenied(e) || (e instanceof ApiError && e.detail.code === 'resource_not_found'))
            await checkStudyAccess(token);
          if (valid(token)) {
            cache.current.set(id, { state: 'error' });
            setSources(new Map(cache.current));
          }
        });
  }
  useLayoutEffect(() => {
    const token = ++generation.current,
      read = api.fence({ studyId });
    scope.current = read;
    setRows([]);
    setCursor(null);
    setError(false);
    setDenied(false);
    setAccessUnverified(false);
    cache.current.clear();
    setSources(new Map());
    void page(null, token);
    return () => {
      generation.current++;
      cache.current.clear();
      read.done();
    };
  }, [api, actor, studyId, version]);
  const domId = (kind: string, id: string) => base + '-' + kind + '-' + id;
  // Exact version-qualified case navigation: focus that case's result, never a
  // similarly named case or the first case. Unknown identities are reported.
  useEffect(() => {
    if (!focusCase) return;
    const known =
      focusCase.id === 'none' ||
      saved.version.content.cases.some((item) => item.case_id === focusCase.id);
    setMissingCase(known ? '' : focusCase.id);
    let frames = 0,
      frame = 0;
    const attempt = () => {
      const target = document.getElementById(
        known ? domId('card', focusCase.id) : base + '-results',
      );
      if (target && target.getClientRects().length) {
        target.focus();
        target.scrollIntoView({ block: 'center' });
        return;
      }
      if (++frames < 120) frame = requestAnimationFrame(attempt);
      else document.getElementById(base + '-results')?.focus();
    };
    frame = requestAnimationFrame(attempt);
    return () => cancelAnimationFrame(frame);
  }, [focusCase?.token, version]);
  // Case definitions belong to the protected approach and clear with it.
  if (denied)
    return (
      <section className="approach-usage" aria-label="Approach usage">
        <p role="alert">{accessLostText}</p>
      </section>
    );
  const incomplete = loading || error || !!cursor || rows.some((row) => row.loading || row.error);
  const groups = groupFindings(saved, rows, caseId);
  const cardGroups = groups.filter((group) => group.item || group.rows.length);
  const row = (item: Row, configuration?: Configuration) => (
    <FindingRow
      key={identity(item.usage)}
      row={item}
      cited={
        item.usage.kind === 'run'
          ? answers
              .find((answer) => answer.case_id === item.usage.case_id)
              ?.basis.run_ids.includes(item.usage.run_id)
          : undefined
      }
      saved={configuration}
      hideSources={
        item.usage.kind === 'configuration' &&
        rows.some(
          (other) =>
            other.usage.kind === 'run' &&
            !!other.run &&
            other.usage.configuration_revision_id === item.usage.configuration_revision_id &&
            other.usage.case_id === item.usage.case_id,
        )
      }
      sources={sources}
      load={loadSources}
      retry={() => void detail(item.usage, generation.current)}
      onOpen={(target) => onOpen({ ...target, study: studyId })}
    />
  );
  const supportFor = (group: Group) => {
    const answer = answers.find((item) => item.case_id === group.id);
    return (
      <SupportingResults
        rows={group.rows}
        basis={answer?.basis}
        renderRun={row}
        configurationDetails={(item) => (
          <>
            {item.error && (
              <Button onClick={() => void detail(item.usage, generation.current)}>
                Retry configuration
              </Button>
            )}
            {item.configuration &&
              !group.rows.some(
                (other) =>
                  other.usage.kind === 'run' &&
                  !!other.run &&
                  other.usage.configuration_revision_id === item.usage.configuration_revision_id,
              ) && (
                <SourceInputs
                  configuration={item.configuration}
                  sources={sources}
                  load={loadSources}
                  onOpen={(id) => onOpen({ study: studyId, view: 'runs', run: id })}
                />
              )}
          </>
        )}
        api={api}
        studyId={studyId}
        onOpen={onOpen}
        complete={!incomplete}
      />
    );
  };
  const studySupport = (answer: ScientificAnswer1) => {
    const citedRows = rows.filter((row) =>
      row.usage.kind === 'run'
        ? answer.basis.run_ids.includes(row.usage.run_id)
        : answer.basis.configuration_revision_ids.includes(row.usage.configuration_revision_id),
    );
    const groups = groupFindings(saved, citedRows, '').filter(
      (group) =>
        group.rows.length ||
        answers.some(
          (item) =>
            item.case_id === group.id &&
            answer.basis.case_answer_version_ids.includes(item.answer_version_id),
        ),
    );
    const shownConfigurations = new Set(
      citedRows.map((row) => row.usage.configuration_revision_id),
    );
    const shownRuns = new Set(
      citedRows.flatMap((row) => (row.usage.kind === 'run' ? [row.usage.run_id] : [])),
    );
    const shownAnswers = new Set<string>();
    const grouped = groups.map((group) => {
      const related = answers.filter(
        (item) =>
          item.case_id === group.id &&
          answer.basis.case_answer_version_ids.includes(item.answer_version_id),
      );
      related.forEach((item) => shownAnswers.add(item.answer_version_id));
      return (
        <section
          key={group.id}
          className="study-support-case"
          aria-label={group.title + ' supporting results'}
        >
          <h4>{group.title}</h4>
          <div className="study-support-actions">
            {[...new Set(group.rows.map((row) => row.usage.configuration_revision_id))].map(
              (id, index, ids) => (
                <Button
                  key={id}
                  size="sm"
                  onClick={() =>
                    onOpen({ study: studyId, view: 'configurations', configuration: id })
                  }
                >
                  {ids.length === 1 ? 'View configuration' : 'View configuration ' + (index + 1)}
                </Button>
              ),
            )}
            {group.rows
              .filter((row) => row.usage.kind === 'run')
              .map((row, index, runs) => (
                <Button
                  key={identity(row.usage)}
                  size="sm"
                  onClick={() =>
                    row.usage.kind === 'run' &&
                    onOpen({ study: studyId, view: 'runs', run: row.usage.run_id })
                  }
                >
                  {runs.length === 1 ? 'View run' : 'View run ' + (index + 1)}
                </Button>
              ))}
            {related.map((item) => (
              <AnswerBasis
                key={item.answer_version_id}
                kind="answer"
                id={item.answer_version_id}
                api={api}
                studyId={studyId}
                onOpen={onOpen}
                label="View case answer"
                title={group.title + ' · Case answer'}
              />
            ))}
          </div>
        </section>
      );
    });
    const remaining = {
      ...answer.basis,
      configuration_revision_ids: answer.basis.configuration_revision_ids.filter(
        (id) => !shownConfigurations.has(id),
      ),
      run_ids: answer.basis.run_ids.filter((id) => !shownRuns.has(id)),
      case_answer_version_ids: answer.basis.case_answer_version_ids.filter(
        (id) => !shownAnswers.has(id),
      ),
    };
    return (
      <div className="answer-support" role="group" aria-label="Supporting results">
        <h4>Supporting results</h4>
        {grouped}
        <SupportingResults
          rows={[]}
          basis={remaining}
          api={api}
          studyId={studyId}
          onOpen={onOpen}
          complete={!incomplete}
          heading={false}
          caseAnswers={remaining.case_answer_version_ids.map((id) => ({
            id,
            title: 'Case answer ' + id.slice(0, 8),
          }))}
        />
      </div>
    );
  };
  // Results first (recorded facts, exact coverage, no verdict), then one card per case.
  return (
    <section className="approach-usage" aria-label="Approach usage">
      {section !== 'answer' && <Panel
        id={casesId}
        className="approach-section"
        label="Cases and their answers"
        title="Cases and their answers"
        headingLevel={3}
      >
        <div className="approach-usage-review">
          <div role="region" aria-label="Case filter" id={base + '-results'} tabIndex={-1}>
            {missingCase && (
              <p role="alert">
                This case is not part of approach v{saved.version.version_number}. No other case is
                shown in its place.
              </p>
            )}
            <div className="section-actions approach-usage-controls">
              <label>
                Case filter
                <Select
                  aria-label="Findings case"
                  value={caseId}
                  onChange={(event) => setCaseId(event.target.value)}
                >
                  <option value="">All cases</option>
                  {saved.version.content.cases.map((item) => (
                    <option key={item.case_id} value={item.case_id}>
                      {item.title}
                    </option>
                  ))}
                </Select>
              </label>
            </div>
          </div>
        </div>
        {loading && <p role="status">Loading supporting results…</p>}
        {error && <p role="alert">Supporting results could not be loaded.</p>}
        {accessUnverified && (
          <p role="alert">Study access could not be verified. Retry the read.</p>
        )}
        <div className="approach-case-cards">
          {cardGroups.map((group) => (
            <CaseCard
              key={group.id}
              group={group}
              headingId={domId('card', group.id)}
              content={saved.version.content}
              expanded={focusCase?.id === group.id ? focusCase.token : undefined}
              onCreateConfiguration={onCreateConfiguration}
              support={answers.some((item) => item.case_id === group.id) ? null : supportFor(group)}
              answer={
                group.item ? answerFor(group.id) : <p>No case is associated with these records.</p>
              }
              answerStatus={
                answerState === 'loading'
                  ? 'Loading answer'
                  : answerState === 'error'
                    ? 'Answer unavailable'
                    : answers.some((item) => item.case_id === group.id)
                      ? 'Assessed'
                      : 'Not assessed'
              }
            />
          ))}
          {!cardGroups.length && <p>No cases</p>}
          {!caseId && (
            <RemainingWork
              content={saved.version.content}
              headingId={base + '-remaining'}
              onViewStep={onViewStep}
            />
          )}
        </div>
        {error && (
          <Button disabled={loading} onClick={() => void page(failedCursor.current)}>
            Retry supporting results
          </Button>
        )}
      </Panel>}
      {section !== 'cases' && <Panel
        id={answerId}
        className="approach-section approach-study-answer"
        label="Answer to the study question"
        title="Answer to the study question"
        headingLevel={3}
      >
        {answerFor(null)}
        {answerState === 'error' && (
          <Button onClick={() => setAnswerReview((value) => value + 1)}>Retry answer read</Button>
        )}
      </Panel>}
    </section>
  );
}
