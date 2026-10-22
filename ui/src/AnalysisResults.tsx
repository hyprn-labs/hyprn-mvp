import { useEffect, useState } from 'react';
import { message, type HyprnMvpApi } from './api';
import type {
  CalculationRun1,
  CalculationVersionRead4,
  CriterionEvaluation1,
  FrozenConfigurationRead7,
  ModelRevisionRead4,
  PublicRunDetail2,
  StudyCriterion1,
} from './contract';
import { useStudyRead } from './calculationReads';
import { modelPorts } from './modelPorts';
import { refKey } from './CalculationDesign';
import { criterionOperators } from './criterionLabels';
import { executionStatus } from './runStatus';
import {
  RecordNavigation,
  ActionDialog,
  Button,
  Checkbox,
  TableControls,
  DataTable,
  Select,
  StatusTag,
  formatNumber,
  type Tone,
} from './design';
import { unitLabel } from './unitLabels';
/** Why a criterion reads as it does for a run, in the reader's words. */
const evaluationReasons: Record<CriterionEvaluation1['reason'], string> = {
  threshold_comparison: 'Compared with the threshold',
  measured: 'Measured',
  criterion_not_bound: 'Criterion not bound',
  run_not_recorded: 'No results yet',
  retained_record_invalid: 'Record could not be verified',
  convergence_unresolved: 'Convergence unresolved',
  required_output_unavailable: 'Output not computed',
  invalid_criterion_or_units: 'Value or units invalid',
};

/** One evaluation cell: shape, word and colour; the value with its units, or "not computed". */
export function EvaluationCell({
  evaluation,
  showUnits = true,
}: {
  evaluation: CriterionEvaluation1;
  showUnits?: boolean;
}) {
  const value =
    evaluation.value === null
      ? 'not computed'
      : formatNumber(evaluation.value) + (showUnits ? ' ' + unitLabel(evaluation.units) : '');
  const [tone, word]: [Tone, string] =
    evaluation.outcome === 'met'
      ? ['ok', 'Met']
      : evaluation.outcome === 'not_met'
        ? ['alarm', 'Not met']
        : evaluation.outcome === 'measured'
          ? ['inert', 'Measured']
          : ['advisory', 'Not evaluated'];
  return (
    <span className="calculation-evaluation">
      <StatusTag tone={tone}>{word}</StatusTag>
      <span>
        {evaluation.outcome === 'unresolved' ? evaluationReasons[evaluation.reason] : value}
      </span>
    </span>
  );
}

export function requirement(criterion: StudyCriterion1) {
  if (criterion.kind === 'objective')
    return criterion.direction === 'minimize' ? 'Minimize' : 'Maximize';
  return (
    criterionOperators[criterion.operator] +
    ' ' +
    formatNumber(criterion.threshold) +
    ' ' +
    unitLabel(criterion.units)
  );
}

/** Names are concise until two quantities actually need component context. */
export function analysisPorts(model: ModelRevisionRead4 | null) {
  const ports = model ? modelPorts(model) : [];
  return ports.map((p) => ({
    ...p,
    label: ports.filter((other) => other.name === p.name).length > 1 ? p.label : p.name,
  }));
}

type RecordRead = {
  configuration: FrozenConfigurationRead7;
  run: PublicRunDetail2 | null;
  runs: CalculationRun1[];
};
const PAGE_SIZE = 10;

/** One row per configuration, explicitly choosing which execution supplies its outputs.
 * Only the visible page's inputs/results are read; no computation or stored selection occurs. */
export function AnalysisResults({
  api,
  study,
  version,
  criteria,
  names,
  snapshot,
  frozen,
  refresh,
  pinnedRuns = null,
  onOpenConfiguration,
  onOpenRun,
}: {
  api: HyprnMvpApi;
  study: string;
  version: CalculationVersionRead4;
  criteria: StudyCriterion1[];
  names: Record<string, string>;
  snapshot: ModelRevisionRead4 | null;
  frozen: FrozenConfigurationRead7;
  refresh: number;
  pinnedRuns?: Record<string, string | null> | null;
  onOpenConfiguration: (id: string) => void;
  onOpenRun: (id: string) => void;
}) {
  const content = version.content;
  const sampled = content.design.kind === 'sampled' ? content.design : null;
  const ports = analysisPorts(snapshot);
  const inputs = ports.filter(
    (p) =>
      p.direction === 'input' &&
      !snapshot?.connections.some((c) => refKey(c.target_ref) === refKey(p.target)),
  );
  const outputs = ports.filter((p) => p.direction === 'output');
  const [page, setPage] = useState(0);
  const [choices, setChoices] = useState<Record<string, string>>({});
  const [columns, setColumns] = useState<string[] | null>(null);
  const [records, setRecords] = useState<Record<string, RecordRead>>({});
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(false);
  const [retry, setRetry] = useState(0);
  const read = useStudyRead(api, study);
  const ids = content.configuration_revision_ids.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const selected = (id: string) =>
    records[id]?.runs.find((r) => r.run_id === choices[id]) ?? records[id]?.runs[0];
  const selectionKey = ids.map((id) => id + ':' + (choices[id] ?? '')).join('|');
  useEffect(() => {
    setRecords({});
    setLoading(true);
    setError(null);
    void read(
      async (signal) => {
        const result: Record<string, RecordRead> = {};
        let next = 0;
        // Bound reads so a long analysis cannot flood the local application.
        await Promise.all(
          Array.from({ length: Math.min(4, ids.length) }, async () => {
            while (next < ids.length) {
              const id = ids[next++];
              if (signal.aborted) throw new DOMException('Aborted', 'AbortError');
              const configuration =
                id === frozen.configuration.configuration_revision_id
                  ? frozen
                  : await api.configuration(study, id, signal);
              const runs: CalculationRun1[] = [];
              let cursor: number | undefined;
              do {
                if (signal.aborted) throw new DOMException('Aborted', 'AbortError');
                const page = await api.calculationRuns(
                  study,
                  version.calculation_version_id,
                  cursor,
                  signal,
                  id,
                );
                runs.push(
                  ...page.items.filter((r) => pinnedRuns === null || r.run_id === pinnedRuns[id]),
                );
                cursor = page.next_cursor ?? undefined;
              } while (cursor !== undefined);
              const run = runs.find((r) => r.run_id === choices[id]) ?? runs[0];
              result[id] = {
                configuration,
                runs,
                run: run ? await api.run(study, run.run_id) : null,
              };
            }
          }),
        );
        return result;
      },
      (value) => {
        setRecords(value);
        setLoading(false);
      },
      (failure) => {
        setError(failure);
        setLoading(false);
      },
    );
  }, [selectionKey, refresh, retry]);
  const defaultColumns = [
    ...inputs.filter(
      (p) =>
        !sampled ||
        sampled.groups.some((g) => g.dimensions.some((d) => refKey(d.target) === refKey(p.target))),
    ),
    ...outputs.filter(
      (p) =>
        !content.criterion_bindings.length ||
        content.criterion_bindings.some((b) => refKey(b.output) === refKey(p.target)),
    ),
  ].map((p) => refKey(p.target));
  const shown = columns ?? defaultColumns;
  const bindings = (key: string) =>
    criteria.filter((c) =>
      content.criterion_bindings.some(
        (b) => b.criterion_id === c.criterion_id && refKey(b.output) === key,
      ),
    );
  const unbound = criteria.filter(
    (c) => !content.criterion_bindings.some((b) => b.criterion_id === c.criterion_id),
  );
  // The saved design reserves the first held-out point in each group for method selection.
  const selectionPoints = new Set(
    sampled?.groups.flatMap((_, group) => {
      const first = sampled.points.find((p) => p.group === group && p.partition !== 'training');
      return first ? [first.configuration_revision_id] : [];
    }) ?? [],
  );
  return (
    <div className="hf-flow">
      <TableControls
        label="Results pagination"
        itemLabel={sampled ? 'Points' : 'Configurations'}
        page={page}
        pageSize={PAGE_SIZE}
        total={content.configuration_revision_ids.length}
        onPage={setPage}
        columns={
          <ActionDialog title="Table columns" label="Columns" closeLabel="Done">
            <div className="hf-form-stack">
              {[
                { title: 'Outputs', ports: outputs },
                { title: 'Inputs', ports: inputs },
              ].map((group) => (
                <fieldset key={group.title} className="hf-form-section">
                  <legend>{group.title}</legend>
                  {group.ports.map((p) => {
                    const key = refKey(p.target);
                    return (
                      <label key={key}>
                        <Checkbox
                          checked={shown.includes(key)}
                          aria-label={p.label}
                          onChange={(e) =>
                            setColumns(
                              e.target.checked ? [...shown, key] : shown.filter((k) => k !== key),
                            )
                          }
                        />
                        {p.label}
                      </label>
                    );
                  })}
                </fieldset>
              ))}
            </div>
          </ActionDialog>
        }
      />
      {loading && <p role="status">Loading inputs and results…</p>}
      {error != null && (
        <div role="alert">
          <p>{message(error)}</p>
          <Button onClick={() => setRetry((v) => v + 1)}>Retry results</Button>
        </div>
      )}
      <DataTable
        regionLabel="Analysis results"
        className="hf-table--comparison hf-table--points"
        columns={[
          { key: 'point', label: sampled ? 'Point' : 'Configuration', presentation: 'compact' },
          ...(sampled ? [{ key: 'role', label: 'Use', presentation: 'compact' as const }] : []),
          ...outputs
            .filter((p) => shown.includes(refKey(p.target)))
            .map((p) => ({
              key: refKey(p.target),
              numeric: true,
              label: (
                <span className="hf-result-cell">
                  <span>
                    {p.label} · {unitLabel(p.units)}
                  </span>
                  {bindings(refKey(p.target)).map((c) => (
                    <span key={c.criterion_id}>{requirement(c)}</span>
                  ))}
                </span>
              ),
            })),
          ...unbound.map((c) => ({ key: c.criterion_id, label: `${c.name} · ${requirement(c)}` })),
          { key: 'execution', label: 'Run', presentation: 'compact' },
          ...inputs
            .filter((p) => shown.includes(refKey(p.target)))
            .map((p) => ({
              key: refKey(p.target),
              label: `${p.label} · ${unitLabel(p.units)}`,
              numeric: true,
            })),
        ]}
        rows={ids.map((id) => {
          const run = selected(id);
          const record = records[id];
          const history = record?.runs ?? [];
          const pointIndex =
            sampled?.points.findIndex((p) => p.configuration_revision_id === id) ?? -1;
          const point = pointIndex >= 0 ? sampled!.points[pointIndex] : null;
          const name = point ? `Point ${pointIndex + 1}` : (names[id] ?? 'Configuration');
          const status = record?.run ? executionStatus(record.run) : null;
          return {
            point: (
              <RecordNavigation
                onOpen={() => onOpenConfiguration(id)}
                label={`Open configuration · ${name}`}
              >
                {name}
              </RecordNavigation>
            ),
            role: point
              ? point.partition === 'training'
                ? 'Training'
                : selectionPoints.has(id)
                  ? 'Method selection'
                  : 'Validation'
              : '',
            ...Object.fromEntries(
              inputs.map((p) => {
                const input = record?.configuration.configuration.inputs.find(
                  (i) => refKey(i.target) === refKey(p.target),
                );
                return [
                  refKey(p.target),
                  input
                    ? formatNumber(input.value)
                    : record
                      ? 'unassigned'
                      : error
                        ? 'Read unavailable'
                        : '…',
                ];
              }),
            ),
            execution: (
              <span className="hf-result-cell">
                {history.length > 1 && (
                  <Select
                    aria-label={`${name} displayed run`}
                    value={run?.run_id ?? ''}
                    onChange={(e) => setChoices((v) => ({ ...v, [id]: e.target.value }))}
                  >
                    {history.map((r, i) => (
                      <option key={r.run_id} value={r.run_id}>
                        Execution {i + 1}
                      </option>
                    ))}
                  </Select>
                )}
                {run && status ? (
                  <RecordNavigation
                    onOpen={() => onOpenRun(run.run_id)}
                    label={`Open run · ${name} · ${status.label}`}
                  >
                    <StatusTag tone={status.tone}>{status.label}</StatusTag>
                  </RecordNavigation>
                ) : (
                  <span>{record ? 'Not run' : error ? 'Read unavailable' : '…'}</span>
                )}
              </span>
            ),
            ...Object.fromEntries(
              outputs.map((p) => {
                const evaluations = bindings(refKey(p.target))
                  .map((c) => run?.evaluations.find((e) => e.criterion_id === c.criterion_id))
                  .filter((e) => e !== undefined);
                const value = record?.run?.history?.results?.outputs.find(
                  (o) => refKey(o.target) === refKey(p.target),
                );
                return [
                  refKey(p.target),
                  evaluations.length ? (
                    <span className="hf-result-cell">
                      {evaluations.map((e) => (
                        <EvaluationCell key={e.criterion_id} evaluation={e} showUnits={false} />
                      ))}
                    </span>
                  ) : value ? (
                    <span>
                      {value.value === null
                        ? `not computed${value.reason ? ': ' + value.reason : ''}`
                        : formatNumber(value.value)}
                    </span>
                  ) : (
                    <span>{!record ? (error ? 'Read unavailable' : '…') : 'not computed'}</span>
                  ),
                ];
              }),
            ),
            ...Object.fromEntries(
              unbound.map((c) => [
                c.criterion_id,
                <StatusTag tone="advisory">Output not assigned</StatusTag>,
              ]),
            ),
          };
        })}
      />
    </div>
  );
}
