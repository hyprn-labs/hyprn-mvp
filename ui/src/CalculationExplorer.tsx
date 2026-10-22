import { OpenLink } from './design';
import { useEffect, useId, useState } from 'react';
import { ModelView } from './ModelView';
import { ApiError, message, type HyprnMvpApi } from './api';
import { recoverPrediction } from './predictionRecovery';
import type {
  CalculationExploration1,
  CalculationEstimateRead2,
  CalculationPoint1,
  FrozenConfigurationRead7,
  PortRef,
  StudyAnswerExplorationBasis1,
  StudyCriterion1,
} from './contract';
import type { Selection, WorkspaceLink } from './workspaceModel';
import { GraphView, project, type Snapshot } from './GraphView';
import { useAccessLoss } from './accessLoss';
import {
  ActionDialog,
  ActionGroup,
  AnswerExplorationPanel,
  Button,
  Checkbox,
  DataTable,
  ExplorationFocus,
  ExplorationLegend,
  ExplorationQuantity,
  QuantityResult,
  QuantitySlider,
  RecordDetails,
  SurrogateValidation,
  ResponseCurve,
  Select,
  TextInput,
  formatNumber,
} from './design';
import {
  completeVector,
  explorationInputVector,
  explorationReason,
  sameInputVector,
  sampleCentre,
  preparedSliderStops,
  type Dimension,
  type ExplorationPoint,
  type SelectedInput,
} from './explorationInputs';
import { unitLabel } from './unitLabels';

const key = (p: PortRef) => p.instance_id + '/' + p.port_id;
type Loaded = {
  basis: CalculationExploration1;
  frozen: FrozenConfigurationRead7;
  estimate: CalculationEstimateRead2 | null;
  groupNames: string[];
  analysisName: string;
  versionNumber: number;
  centre: ReturnType<typeof sampleCentre>;
};
const projected = (points: CalculationPoint1[]): ExplorationPoint[] =>
  points.map((p) => ({
    inputs: p.inputs,
    outputs: p.outputs,
  }));

/** Presentation of one exact saved calculation/estimate basis. Moving sliders never writes
 * an answer, calculation, configuration or sampling design. */
export function CalculationExplorer({
  api,
  studyId,
  basis,
  requirements = [],
  onOpen,
}: {
  api: HyprnMvpApi;
  studyId: string;
  basis: StudyAnswerExplorationBasis1;
  requirements?: { target: PortRef; criterion: Extract<StudyCriterion1, { kind: 'constraint' }> }[];
  onOpen: (target: WorkspaceLink) => void;
}) {
  const modelPreviewId = useId();
  const [modelPreviewOpened, setModelPreviewOpened] = useState(false);
  const [modelSelection, setModelSelection] = useState<Selection>({ kind: 'none' });
  const [group, setGroup] = useState(0);
  const [pointSearch, setPointSearch] = useState('');
  const [pointChoice, setPointChoice] = useState(0);
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [selected, setSelected] = useState<SelectedInput[]>([]);
  const [axis, setAxis] = useState<PortRef | null>(null);
  const [points, setPoints] = useState<CalculationPoint1[]>([]);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  const [basisRetry, setBasisRetry] = useState(0);
  const [expanded, setExpanded] = useState(false);
  const [selection, setSelection] = useState<Selection>({ kind: 'none' });
  const [outcomes, setOutcomes] = useState<PortRef[]>(basis.shown_outputs);
  useAccessLoss(api, studyId, () => {
    setLoaded(null);
    setPoints([]);
    setSelected([]);
    setPending(false);
    setError('Access to this resource is no longer available.');
  });
  useEffect(() => {
    const fence = api.fence({ studyId });
    setLoaded(null);
    setPoints([]);
    setError('');
    setPending(false);
    void Promise.all([
      api.calculationExploration(
        studyId,
        basis.calculation_version_id,
        group,
        basis.estimate_id,
        fence.signal,
      ),
      api.calculationVersion(studyId, basis.calculation_version_id, fence.signal),
      basis.estimate_id ? api.calculationEstimate(studyId, basis.estimate_id, fence.signal) : null,
    ])
      .then(async ([projection, version, estimate]) => {
        const design = version.content.design;
        const ids =
          design.kind === 'sampled'
            ? design.groups.map((g) => g.reference_configuration_revision_id)
            : version.content.configuration_revision_ids;
        const configs = await Promise.all(
          ids.map((id) => api.configuration(studyId, id, fence.signal)),
        );
        if (!fence.valid()) return;
        const vector = explorationInputVector(projection.inputs);
        if (!vector) throw new Error('The saved configuration has incomplete input assignments.');
        const training = new Set(
          estimate?.samples
            .filter((p) => p.group === group && p.partition === 'training')
            .map((p) => p.run_id),
        );
        const centre = sampleCentre(
          projection.points
            .filter((p) => training.has(p.outputs[0]?.run_id ?? null))
            .map((p) => p.inputs),
          projection.dimensions,
        );
        setLoaded({
          basis: projection,
          analysisName: version.content.name,
          versionNumber: version.version_number,
          frozen: configs[group],
          estimate,
          groupNames: configs.map((c) => c.configuration.name),
          centre,
        });
        setSelected(centre ?? vector);
        setAxis(projection.dimensions[0]?.target ?? null);
      })
      .catch(async (e) => {
        await api.readFailed(e, fence);
        if (fence.valid()) setError(message(e));
      })
      .finally(fence.done);
    return () => fence.abort();
  }, [api, studyId, basis.calculation_version_id, basis.estimate_id, group, basisRetry]);

  const dimensions: Dimension[] = (loaded?.basis.dimensions ?? []).map((d) => ({
    ...d,
    common_key: null,
  }));
  const vector = completeVector(selected, dimensions);
  const signature = JSON.stringify(vector);
  const axisKey = axis ? key(axis) : '';
  useEffect(() => {
    if (!loaded || !vector || !basis.estimate_id) {
      setPending(false);
      return;
    }
    const fence = api.fence({ studyId });
    setPoints([]);
    setPending(true);
    setError('');
    const timer = setTimeout(() => {
      void recoverPrediction(
        async () => {
          const token = crypto.randomUUID();
          const result = await api.predictCalculation(
            studyId,
            basis.estimate_id!,
            {
              selection_token: token,
              group,
              inputs: vector,
              axis,
              curve_points: axis ? 32 : 0,
            },
            fence.signal,
          );
          if (result.selection_token !== token) throw new Error('Prediction identity mismatch.');
          return result;
        },
        (error) =>
          (error instanceof ApiError && error.detail.code === 'backend_unavailable') ||
          error instanceof TypeError,
        fence.signal,
      )
        .then((result) => {
          if (fence.valid()) setPoints(result.points);
        })
        .catch(async (e) => {
          await api.readFailed(e, fence);
          if (fence.valid()) setError(message(e));
        })
        .finally(() => {
          if (fence.valid()) setPending(false);
          fence.done();
        });
    }, 40);
    return () => {
      clearTimeout(timer);
      fence.abort();
    };
    // The full numeric vector and axis are the interaction identity, independent of rendering.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, studyId, loaded, signature, axisKey, basis.estimate_id, group, retry]);

  function changeInput(target: PortRef, value: number | null) {
    const leader = dimensions.find((d) => key(d.target) === key(target));
    setPoints([]);
    setSelected((current) =>
      current.map((p) => {
        if (key(p.target) === key(target)) return { ...p, value };
        const d = dimensions.find((d) => key(d.target) === key(p.target));
        if (leader?.covary_group && d?.covary_group === leader.covary_group) {
          const mapped =
            value === null ||
            leader.lower === null ||
            leader.upper === null ||
            d.lower === null ||
            d.upper === null
              ? null
              : d.lower +
                ((value - leader.lower) / (leader.upper - leader.lower)) * (d.upper - d.lower);
          return { ...p, value: mapped };
        }
        return p;
      }),
    );
    if (basis.estimate_id) setPending(true);
  }
  const allPoints = [...(loaded?.basis.points ?? []), ...points];
  const exact = vector && loaded?.basis.points.find((p) => sameInputVector(p.inputs, vector));
  const current = exact ?? (vector && points.find((p) => sameInputVector(p.inputs, vector)));
  const showUnavailable =
    !pending &&
    [...(current ? [current] : []), ...points.filter(onSlice)].some((p) =>
      p.outputs.some((o) => outcomes.some((t) => key(t) === key(o.target)) && o.value === null),
    );
  const axisPort = loaded?.basis.inputs.find((p) => axis && key(p.target) === key(axis));
  const axisValue = selected.find((p) => axis && key(p.target) === key(axis))?.value;
  function onSlice(p: CalculationPoint1) {
    if (!axis || !vector) return false;
    const d = dimensions.find((d) => key(d.target) === key(axis));
    return p.inputs.every(
      (v) =>
        key(v.target) === key(axis) ||
        (d?.covary_group &&
          dimensions.find((i) => key(i.target) === key(v.target))?.covary_group ===
            d.covary_group) ||
        vector.some(
          (i) => key(i.target) === key(v.target) && i.units === v.units && i.value === v.value,
        ),
    );
  }
  function renderQuantity(target: PortRef) {
    if (!loaded) return null;
    const input = loaded.basis.inputs.find((p) => key(p.target) === key(target));
    if (input?.binding.kind === 'free') {
      const d = dimensions.find((d) => key(d.target) === key(target));
      const assignment = selected.find((p) => key(p.target) === key(target));
      if (!d)
        return (
          <div className="hf-quantity-entry">
            <span>{input.name}</span>
            <span className="hf-mono">
              {assignment?.value == null ? 'Unassigned' : formatNumber(assignment.value)}{' '}
              {unitLabel(assignment?.units ?? input.units)}
            </span>
          </div>
        );
      return (
        <QuantitySlider
          label={input.name}
          units={d.units}
          value={assignment?.value ?? null}
          lower={d.lower}
          upper={d.upper}
          step={d.step}
          stops={preparedSliderStops(projected(allPoints), selected, dimensions, target, outcomes, [
            ...loaded.basis.points.map((p) => p.inputs),
            ...(loaded.centre ? [loaded.centre] : []),
          ])}
          onChange={(value) => changeInput(target, value)}
        />
      );
    }
    const source = input?.binding.kind === 'connected' ? input.binding.source : target;
    const output = loaded.basis.outputs.find((p) => key(p.target) === key(source));
    if (!output) return null;
    const result = current?.outputs.find((o) => key(o.target) === key(source));
    const assessment = loaded.estimate?.groups.find((g) => g.group === group);
    const metric = assessment?.outputs.find((o) => key(o.target) === key(source));
    const slice = allPoints
      .filter(onSlice)
      .map((p) => ({
        x: p.inputs.find((v) => axis && key(v.target) === key(axis))?.value,
        o: p.outputs.find((v) => key(v.target) === key(source)),
      }))
      .filter((p) => p.x !== undefined)
      .sort((a, b) => a.x! - b.x!);
    const calculated = slice.flatMap((p) =>
      p.o?.kind === 'calculated' && p.o.value !== null ? [{ x: p.x!, y: p.o.value }] : [],
    );
    return (
      <>
        <QuantityResult
          value={result?.value ?? null}
          units={output.units}
          state={result?.kind ?? 'unavailable'}
          pending={!result && pending}
          reason={explorationReason(result?.reason ?? metric?.reason)}
        />
        {axisPort && axisValue !== null && axisValue !== undefined && !input && (
          <ResponseCurve
            label={output.name}
            units={output.units}
            axis={
              axisPort.name + (unitLabel(axisPort.units) ? ' · ' + unitLabel(axisPort.units) : '')
            }
            selected={axisValue}
            selectedResult={
              result
                ? {
                    value: result.value,
                    state: result.kind === 'calculated' ? 'calculated' : 'estimated',
                  }
                : undefined
            }
            points={slice.map((p) => ({ x: p.x!, y: p.o?.value ?? null }))}
            calculated={calculated}
            pending={pending}
            referenceLines={requirements
              .filter(
                (r) => key(r.target) === key(output.target) && r.criterion.units === output.units,
              )
              .map((r) => ({
                value: r.criterion.threshold,
                label: { lt: '<', le: '≤', eq: '=', ge: '≥', gt: '>' }[r.criterion.operator],
              }))}
          />
        )}
        <div className="hf-output-actions">
          <ActionDialog
            purpose="reader"
            label="Why"
            title={output.name + ' — Why'}
            variant="quiet"
            size="sm"
            help={result?.run_id ? 'runOutputs' : 'surrogate'}
          >
            {result?.run_id ? (
              <OpenLink
                onClick={() => onOpen({ study: studyId, view: 'runs', run: result.run_id! })}
              >
                View run
              </OpenLink>
            ) : (
              <>
                <SurrogateValidation
                  summary
                  rows={[
                    {
                      name: output.name,
                      units: output.units,
                      method: metric?.method,
                      metrics: metric?.metrics,
                      reason: metric?.reason,
                      tolerance: loaded?.estimate?.request.tolerances.find(
                        (t) => key(t.target) === key(output.target),
                      ),
                    },
                  ]}
                />
                <p>
                  Validation describes agreement at independent model points, not a physical
                  qualification or an error guarantee everywhere.
                </p>
                <OpenLink
                  onClick={() =>
                    onOpen({
                      study: studyId,
                      view: 'calculations',
                      calculation_version: basis.calculation_version_id,
                    })
                  }
                >
                  View analysis
                </OpenLink>
              </>
            )}
            <RecordDetails kind="Prediction">
              <p>
                Analysis version: <code>{basis.calculation_version_id}</code>
              </p>
              {basis.estimate_id && (
                <p>
                  Estimate: <code>{basis.estimate_id}</code>
                </p>
              )}
              {assessment && (
                <p>
                  Artifact SHA-256: <code>{assessment.artifact_sha256}</code>
                </p>
              )}
            </RecordDetails>
          </ActionDialog>
        </div>
      </>
    );
  }
  const snapshot = loaded?.frozen.model_snapshot as Snapshot | undefined;
  const inputControls = (
    <ActionGroup>
      {' '}
      {(loaded?.groupNames.length ?? 0) > 1 && (
        <label className="hf-exploration-axis">
          Reference configuration
          <Select
            aria-label="Reference configuration"
            value={group}
            onChange={(e) => setGroup(Number(e.target.value))}
          >
            {loaded?.groupNames.map((name, i) => (
              <option key={i} value={i}>
                {name}
              </option>
            ))}
          </Select>
        </label>
      )}
      {(loaded?.basis.points.length ?? 0) > 0 && (
        <ActionDialog
          label="Load point"
          title="Load calculated point"
          width="workspace"
          completionKey={pointChoice}
        >
          <TextInput
            aria-label="Find calculated point"
            placeholder="Find an input value…"
            value={pointSearch}
            onChange={(e) => setPointSearch(e.target.value)}
          />
          <DataTable
            regionLabel="Calculated input combinations"
            columns={[
              { key: 'point', label: 'Point', presentation: 'compact' },
              ...(loaded?.basis.inputs
                .filter((p) => p.binding.kind === 'free')
                .map((p) => ({
                  key: key(p.target),
                  label: `${p.name} · ${unitLabel(p.units)}`,
                  numeric: true,
                })) ?? []),
              { key: 'action', label: 'Selection' },
            ]}
            rows={loaded?.basis.points
              .map((point, i) => ({
                point: `Point ${i + 1}`,
                ...Object.fromEntries(
                  point.inputs.map((p) => [key(p.target), formatNumber(p.value)]),
                ),
                action: (
                  <Button
                    size="sm"
                    onClick={() => {
                      setPoints([]);
                      setSelected(point.inputs);
                      setPointChoice((n) => n + 1);
                    }}
                  >
                    Load point {i + 1}
                  </Button>
                ),
              }))
              .filter((row) =>
                Object.values(row).some(
                  (value) =>
                    typeof value === 'string' &&
                    value.toLowerCase().includes(pointSearch.toLowerCase()),
                ),
              )}
          />
        </ActionDialog>
      )}
    </ActionGroup>
  );
  const outputControls = (
    <ActionGroup>
      {' '}
      {dimensions.length > 0 && (
        <label className="hf-exploration-axis">
          <span>Plot against</span>
          <Select
            aria-label="Plot against"
            value={axisKey}
            onChange={(e) => {
              const d = dimensions.find((d) => key(d.target) === e.target.value);
              if (d) {
                setPoints([]);
                setAxis(d.target);
              }
            }}
          >
            {dimensions.map((d) => (
              <option key={key(d.target)} value={key(d.target)}>
                {loaded?.basis.inputs.find((p) => key(p.target) === key(d.target))?.name}
              </option>
            ))}
          </Select>
        </label>
      )}
      <ActionDialog label="Select outcomes" title="Displayed outcomes">
        {loaded?.basis.outputs.map((p) => (
          <label key={key(p.target)} className="hf-exploration-choice-row">
            <Checkbox
              checked={outcomes.some((o) => key(o) === key(p.target))}
              onChange={(e) =>
                setOutcomes(
                  e.target.checked
                    ? [...outcomes, p.target]
                    : outcomes.filter((o) => key(o) !== key(p.target)),
                )
              }
            />
            <span>
              {p.name}
              {loaded.basis.outputs.filter((o) => o.name === p.name).length > 1 && (
                <small>{p.instance_name}</small>
              )}
            </span>
          </label>
        ))}
      </ActionDialog>
    </ActionGroup>
  );
  return (
    <AnswerExplorationPanel
      settings={
        <ActionGroup>
          <ActionDialog
            purpose="reader"
            label="Input ranges"
            title="Input ranges"
            help="explorationDomain"
          >
            <DataTable
              label="Saved input ranges"
              columns={[
                { key: 'name', label: 'Input' },
                { key: 'range', label: 'Value or range', numeric: true },
                { key: 'units', label: 'Units' },
              ]}
              rows={(loaded?.basis.inputs ?? [])
                .filter((p) => p.binding.kind === 'free')
                .map((p) => {
                  const d = dimensions.find((d) => key(d.target) === key(p.target));
                  const value = loaded?.frozen.configuration.inputs.find(
                    (i) => key(i.target) === key(p.target),
                  )?.value;
                  return {
                    name: p.name,
                    range: d
                      ? `${formatNumber(d.lower!)}–${formatNumber(d.upper!)}`
                      : value == null
                        ? 'Unassigned'
                        : formatNumber(value),
                    units: unitLabel(p.units),
                  };
                })}
            />
            <OpenLink
              onClick={() =>
                onOpen({
                  study: studyId,
                  view: 'calculations',
                  calculation_version: basis.calculation_version_id,
                })
              }
            >
              View analysis
            </OpenLink>
          </ActionDialog>
        </ActionGroup>
      }
      categories={
        expanded ? (
          <div className="hf-exploration-control-pair">
            {inputControls}
            {outputControls}
          </div>
        ) : null
      }
      footer={
        loaded && (
          <ActionGroup>
            <Button
              onClick={() => {
                setPoints([]);
                setSelected(explorationInputVector(loaded.basis.inputs)!);
              }}
            >
              Reset inputs
            </Button>
            <ActionDialog
              purpose="reader"
              label="View model"
              title="Model"
              width="workspace"
              help="model"
              onOpen={() => setModelPreviewOpened(true)}
            >
              {modelPreviewOpened && snapshot && (
                <ModelView
                  api={api}
                  studyId={studyId}
                  snapshot={snapshot}
                  selection={modelSelection}
                  onSelect={setModelSelection}
                  idPrefix={modelPreviewId}
                />
              )}
              <ActionGroup align="end">
                <OpenLink
                  onClick={() =>
                    onOpen({
                      study: studyId,
                      view: 'model',
                      model: loaded.basis.model_id,
                      revision: loaded.basis.model_revision_id,
                    })
                  }
                >
                  Open model page
                </OpenLink>
              </ActionGroup>
            </ActionDialog>
          </ActionGroup>
        )
      }
    >
      {error && (
        <div role="alert">
          <p>{error}</p>
          <Button onClick={() => (loaded ? setRetry((n) => n + 1) : setBasisRetry((n) => n + 1))}>
            {loaded ? 'Retry predictions' : 'Retry loading results'}
          </Button>
        </div>
      )}
      {!loaded ? (
        !error && <p role="status">Verifying saved calculations…</p>
      ) : (
        <>
          <div className="hf-exploration-view-actions">
            {expanded && <Button onClick={() => setExpanded(false)}>Collapse model</Button>}
            {!expanded && <ExplorationLegend unavailable={showUnavailable} />}
          </div>
          {expanded && snapshot ? (
            <GraphView
              projection={project(snapshot)}
              selection={selection}
              onSelect={setSelection}
              trace={{ nodes: new Set(), links: new Set() }}
              highlightedPorts={new Set(axis ? [key(axis)] : [])}
              toolbarEnd={<ExplorationLegend unavailable={showUnavailable} />}
              portContent={(instance, port) =>
                renderQuantity({ instance_id: instance, port_id: port.port_id })
              }
            />
          ) : (
            <ExplorationFocus
              inputControls={inputControls}
              outputControls={outputControls}
              onExpand={
                snapshot &&
                (snapshot.instances.length > 1 ||
                  loaded.basis.inputs.some((p) => p.binding.kind !== 'free'))
                  ? () => setExpanded(true)
                  : undefined
              }
              inputs={loaded.basis.inputs
                .filter((p) => p.binding.kind === 'free' &&
                  dimensions.some((d) => key(d.target) === key(p.target)))
                .map((p) => (
                  <ExplorationQuantity key={key(p.target)} context={p.instance_name}>
                    {renderQuantity(p.target)}
                  </ExplorationQuantity>
                ))}
              outputs={loaded.basis.outputs
                .filter((p) => outcomes.some((o) => key(o) === key(p.target)))
                .map((p) => (
                  <ExplorationQuantity key={key(p.target)} title={p.name} context={p.instance_name}>
                    {renderQuantity(p.target)}
                  </ExplorationQuantity>
                ))}
            />
          )}
        </>
      )}
    </AnswerExplorationPanel>
  );
}
