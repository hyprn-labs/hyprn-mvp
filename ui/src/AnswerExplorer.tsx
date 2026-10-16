import { useEffect, useRef, useState } from 'react';
import { HyprnMvpApi, message } from './api';
import type {
  ConfigurationRequest4,
  ExplorationBasis1,
  ExplorationPrediction1,
  ExplorationPrediction2,
  FrozenConfigurationRead7,
  PortRef,
  PublicRunDetail,
  ScientificAnswer1,
  ExplorationDesign1,
  ExplorationSurrogate1,
  ExplorationQueryResult1,
} from './contract';
import { GraphView, project, type Snapshot } from './GraphView';
import {
  ActionDialog,
  Button,
  ActionGroup,
  AnswerExplorationPanel,
  QuantityResult,
  QuantitySlider,
  ResponseCurve,
  Select,
  formatNumber,
} from './design';
import { unitLabel } from './unitLabels';
import type { Selection, WorkspaceLink } from './workspaceModel';
import { useAccessLoss } from './accessLoss';
import {
  explorationInputVector,
  explorationReason,
  preparedInputUnitsMatch,
  savedInputQuantity,
  sameInputVector,
  selectInput,
  carryCommon,
  completeVector,
  supportedCombination,
  selectableStops,
  type ExplorationPoint,
  type Dimension,
  type SelectedInput,
} from './explorationInputs';
import { ExplorationSettings } from './ExplorationSettings';

const key = (ref: PortRef) => ref.instance_id + '/' + ref.port_id;
type Loaded = {
  basis: ExplorationBasis1;
  frozen: FrozenConfigurationRead7;
  fits: (ExplorationPrediction1 | ExplorationPrediction2)[];
  runs: PublicRunDetail[];
};

/** One immutable answer/configuration basis; estimates are already returned vectors. */
export function AnswerExplorer({
  api,
  studyId,
  answer,
  onOpen,
}: {
  api: HyprnMvpApi;
  studyId: string;
  answer: ScientificAnswer1;
  onOpen: (target: WorkspaceLink) => void;
}) {
  const [configuration, setConfiguration] = useState(
    answer.basis.configuration_revision_ids[0] ?? '',
  );
  const [loaded, setLoaded] = useState<Loaded | null>(null),
    [error, setError] = useState('');
  const [fitIndex, setFitIndex] = useState(0);
  const [design, setDesign] = useState<ExplorationDesign1 | null>(null);
  const [categories, setCategories] = useState<string[]>([]);
  const [selected, setSelected] = useState<SelectedInput[]>([]);
  const [activeAxis, setActiveAxis] = useState<PortRef | null>(null);
  const [surrogates, setSurrogates] = useState<ExplorationSurrogate1[]>([]);
  const [prediction, setPrediction] = useState<ExplorationQueryResult1 | null>(null);
  const [predictionError, setPredictionError] = useState('');
  const carry = useRef<{ vector: SelectedInput[]; dimensions: Dimension[] } | null>(null);
  const combo = design && supportedCombination(design.request.combinations, categories);
  const dimensions = combo?.dimensions ?? [];
  useEffect(() => {
    const fence = api.fence({ studyId });
    setDesign(null);
    void api
      .explorationDesigns(studyId, answer.answer_version_id, fence.signal)
      .then((items) => {
        if (!fence.valid()) return;
        const d = items[0];
        if (d) {
          setDesign(d);
          setCategories(d.request.combinations[0].categories);
          setConfiguration(d.request.combinations[0].configuration_revision_id);
        }
      })
      .catch(async (e) => {
        await api.readFailed(e, fence);
        if (fence.valid()) setError(message(e));
      })
      .finally(fence.done);
    return () => fence.abort();
  }, [api, studyId, answer.answer_version_id]);
  const [selection, setSelection] = useState<Selection>({ kind: 'none' });
  const [busy, setBusy] = useState(false),
    [runId, setRunId] = useState(''),
    [refresh, setRefresh] = useState(0);
  const generation = useRef(0);
  useAccessLoss(api, studyId, () => {
    generation.current++;
    setLoaded(null);
    setError('Access to this resource is no longer available.');
  });
  useEffect(() => {
    const token = ++generation.current,
      fence = api.fence({ studyId });
    setLoaded(null);
    setPrediction(null);
    setError('');
    setFitIndex(0);
    setRunId('');
    if (!configuration) return () => fence.abort();
    void Promise.all([
      api.explorationBasis(studyId, answer.answer_version_id, configuration, fence.signal),
      api.configuration(studyId, configuration, fence.signal),
      api.preparedExplorations(studyId, answer.answer_version_id, configuration, fence.signal),
      api.explorationSamples(studyId, answer.answer_version_id, fence.signal),
    ])
      .then(async ([basis, frozen, operations, samples]) => {
        const fits = operations.flatMap((op) =>
          op.state === 'complete' && op.result ? [op.result] : [],
        );
        // Refinements retain earlier attempts; prefer the preparation that assessed
        // more outputs, so an earlier failed method cannot mask a usable curve.
        fits.sort(
          (a, b) =>
            b.numerical.result.outputs.filter((o) => o.target_met).length -
            a.numerical.result.outputs.filter((o) => o.target_met).length,
        );
        if (fits.some((f) => f.basis.digest !== basis.digest))
          throw new Error('Prepared response does not match this answer basis.');
        const ids = new Set([
          ...basis.run_ids,
          ...fits.flatMap((f) => (f.schema_version === '1' ? f.samples.map((p) => p.run_id) : [])),
        ]);
        const latest = samples.find((op) =>
          op.request.combinations.some((c) => c.configuration_revision_id === configuration),
        );
        if (latest) {
          const index = latest.request.combinations.findIndex(
            (c) => c.configuration_revision_id === configuration,
          );
          const baseline = explorationInputVector(basis.inputs)!;
          latest.points
            .filter((p) => p.combination === index && p.state === 'recorded' && p.run_id)
            .filter((p) =>
              baseline.some((axis) => {
                const value = p.inputs.find((i) => key(i.target) === key(axis.target))?.value;
                return (
                  value !== undefined &&
                  sameInputVector(
                    selectInput(
                      baseline,
                      dimensions,
                      axis.target,
                      value,
                    ) as ExplorationPoint['inputs'],
                    p.inputs,
                  )
                );
              }),
            )
            .forEach((p) => ids.add(p.run_id!));
        }
        // V2 carries checked original outputs alongside their exact run identities.
        // Avoid re-reading full native histories already represented by those points.
        for (const f of fits)
          if (f.schema_version === '2') for (const sample of f.samples) ids.delete(sample.run_id);
        // Publish the answer basis before hydrating optional calculated overlays.
        // Bounded reads avoid queueing a whole sample behind a single HTTP server.
        const runs: PublicRunDetail[] = [];
        if (fence.valid() && token === generation.current) {
          setLoaded({ basis, frozen, fits, runs });
          const baseline = explorationInputVector(basis.inputs)!;
          setSelected(
            carry.current
              ? carryCommon(carry.current.vector, carry.current.dimensions, baseline, dimensions)
              : baseline,
          );
          carry.current = null;
          setActiveAxis(
            combo?.initial_axis ?? fits[0]?.request.axis ?? baseline[0]?.target ?? null,
          );
        }
        for (const id of ids) {
          if (!fence.valid()) break;
          const run = await api.run(studyId, id);
          if (!fence.valid()) break;
          setLoaded((old) =>
            old && old.basis.digest === basis.digest ? { ...old, runs: [...old.runs, run] } : old,
          );
        }
      })
      .catch(async (e) => {
        await api.readFailed(e, fence);
        if (fence.valid() && token === generation.current) setError(message(e));
      })
      .finally(fence.done);
    return () => fence.abort();
  }, [api, studyId, answer.answer_version_id, configuration, refresh, design, categories]);

  const compatibleUnits = loaded && preparedInputUnitsMatch(loaded.basis.inputs);
  const vector = completeVector(selected, dimensions);
  const surrogate = surrogates.find(
    (s) => s.design_id === design?.design_id && (s.state === 'ready' || s.state === 'assessed'),
  );
  const combinationIndex = design?.request.combinations.findIndex((c) => c === combo) ?? -1;
  const vectorSignature = JSON.stringify(vector);
  useEffect(() => {
    const fence = api.fence({ studyId });
    void api
      .explorationSurrogates(studyId, answer.answer_version_id, fence.signal)
      .then((items) => {
        if (fence.valid()) setSurrogates(items);
      })
      .catch(async (e) => {
        await api.readFailed(e, fence);
      })
      .finally(fence.done);
    return () => fence.abort();
  }, [api, studyId, answer.answer_version_id, refresh]);
  useEffect(() => {
    setPredictionError('');
    if (!loaded || !surrogate || !vector || combinationIndex < 0) return;
    const fence = api.fence({ studyId });
    const token = crypto.randomUUID();
    // Immediate local control update; only the last settled selection is sent.
    const timer = window.setTimeout(() => {
      void api
        .predictExploration(
          studyId,
          surrogate.surrogate_version_id,
          {
            schema_version: '1',
            selection_token: token,
            combination: combinationIndex,
            inputs: vector,
            axis: activeAxis,
            curve_points: 17,
          },
          fence.signal,
        )
        .then((result) => {
          if (fence.valid() && result.selection_token === token) setPrediction(result);
        })
        .catch(async (e) => {
          await api.readFailed(e, fence);
          if (fence.valid())
            setPredictionError('Live estimates unavailable. ' + message(e));
        })
        .finally(fence.done);
    }, 20);
    return () => {
      window.clearTimeout(timer);
      fence.abort();
    };
  }, [
    api,
    studyId,
    surrogate?.surrogate_version_id,
    combinationIndex,
    vectorSignature,
    loaded?.basis.digest,
    activeAxis,
    refresh,
  ]);
  const candidateFit =
    compatibleUnits && activeAxis && vector
      ? [loaded?.fits[fitIndex], ...(loaded?.fits ?? [])].find(
          (f) =>
            f &&
            (f.request.schema_version === '2' ? f.request.varying_targets : [f.request.axis]).some(
              (t) => key(t) === key(activeAxis),
            ) &&
            f.query_inputs.some((q) =>
              sameInputVector(
                selectInput(
                  vector,
                  dimensions,
                  activeAxis,
                  q.find((v) => key(v.target) === key(activeAxis))!.value,
                ) as ExplorationPoint['inputs'],
                q,
              ),
            ),
        )
      : undefined;
  const fit = candidateFit;
  const points: ExplorationPoint[] = [];
  if (prediction)
    prediction.vectors.forEach((inputs, i) =>
      points.push({
        inputs,
        outputs: prediction.outputs.map((o) => ({
          target: o.target,
          units: o.units,
          ...o.values[i],
        })),
      }),
    );
  for (const f of loaded?.fits ?? [])
    f.query_inputs.forEach((inputs, i) =>
      points.push({
        inputs,
        outputs: f.request.tolerances.map((t, n) => ({
          target: t.target,
          units: loaded?.basis.outputs.find((o) => key(o.target) === key(t.target))?.units ?? '',
          value: f.numerical.result.outputs[n]?.values[i] ?? null,
          kind: 'estimated',
          preparation_id: f.identity,
          reason: f.numerical.result.outputs[n]?.reason,
        })),
      }),
    );
  for (const f of loaded?.fits ?? []) {
    if (f.schema_version !== '2') continue;
    f.samples.forEach((sample, i) =>
      points.push({
        inputs: sample.inputs,
        outputs: f.request.tolerances.map((t, n) => ({
          target: t.target,
          units: loaded?.basis.outputs.find((o) => key(o.target) === key(t.target))?.units ?? '',
          value: f.sample_outputs[i]?.[n] ?? null,
          kind: f.sample_outputs[i]?.[n] == null ? 'unavailable' : 'calculated',
          run_id: sample.run_id,
        })),
      }),
    );
  }
  for (const run of loaded?.runs ?? []) {
    if (
      !run.history?.configuration ||
      run.history.configuration.model_revision_id !== loaded?.basis.model_revision_id
    )
      continue;
    points.push({
      inputs: run.history.configuration.inputs,
      outputs: (run.history.results?.outputs ?? []).map((o) => ({
        target: o.target,
        units: o.units,
        value: o.availability === 'available' ? o.value : null,
        kind: o.availability === 'available' ? 'calculated' : 'unavailable',
        reason: o.reason,
        run_id: run.run_id,
      })),
    });
  }
  const selectedPoints = vector ? points.filter((p) => sameInputVector(p.inputs, vector)) : [];
  const axis = loaded?.basis.inputs.find((p) => activeAxis && key(p.target) === key(activeAxis));
  const current = axis
    ? (selected.find((p) => key(p.target) === key(axis.target))?.value ?? null)
    : null;
  // Only the same complete vector and exact model can provide calculated overlays.
  const matching = (run: PublicRunDetail) => {
    const c = run.history?.configuration;
    return (
      c &&
      c.model_revision_id === loaded?.basis.model_revision_id &&
      vector &&
      sameInputVector(vector, c.inputs)
    );
  };
  const calculated = loaded?.runs.find(matching);
  const preparationCounts = fit
    ? `${fit.request.training_count} training calculations · ` +
      `${fit.request.check_count} independent checks.`
    : '';

  async function calculate() {
    if (!loaded || !vector || busy || api.pending) return;
    const token = generation.current,
      fence = api.fence({ studyId });
    setBusy(true);
    setError('');
    try {
      const c = loaded.frozen.configuration;
      if (c.schema_version !== '4')
        throw new Error('This older configuration requires the configuration editor.');
      const study = await api.study(studyId, fence.signal);
      const request: ConfigurationRequest4 = {
        schema_version: '4',
        study_id: studyId,
        model_id: c.model_id,
        model_revision_id: c.model_revision_id,
        name: c.name + ' · selected point',
        inputs: c.inputs.map((i) => {
          const selected = vector.find((v) => key(v.target) === key(i.target))!;
          const changed = selected.value !== i.value;
          if (!changed && i.result_binding)
            return {
              kind: 'run_result',
              target: i.target,
              source_run_id: i.result_binding.source_run_id,
              source_output: i.result_binding.source_output,
              expected_results_digest: i.result_binding.results_digest,
              provenance: i.provenance,
            };
          return {
            kind: 'literal',
            ...selected,
            provenance: changed
              ? {
                  kind: 'manual',
                  statement:
                    'Selected in answer exploration; original value ' + i.value + ' ' + i.units,
                  evidence_version_ids: [],
                }
              : i.provenance,
          };
        }),
        criteria: c.criteria,
        numerical: c.numerical,
        notes: c.context_snapshot.notes,
        context_source: { kind: 'current_study', expected_study_revision: study.revision },
        context_override: {
          schema_version: '1',
          description: c.context_snapshot.description,
          boundary: c.context_snapshot.boundary,
        },
        derivation: null,
        assumptions: c.assumptions,
        general_context_evidence_version_ids: c.general_context_evidence_version_ids,
        approach_selection: c.approach_binding
          ? {
              approach_version_id: c.approach_binding.approach_version_id,
              case_id: c.approach_binding.case_id,
            }
          : null,
      };
      const preview = await api.previewConfiguration4(request, fence.signal);
      if (!fence.valid() || token !== generation.current) return;
      const saved = await api.commitConfiguration4({
        command_id: crypto.randomUUID(),
        expected_revision: null,
        configuration_id: null,
        configuration: request,
        expected_preview_digest: preview.candidate_digest,
      });
      if (!fence.valid() || token !== generation.current) return;
      const run = await api.submitRun(studyId, saved.configuration.configuration_revision_id);
      if (fence.valid() && token === generation.current) setRunId(run.run_id);
    } catch (e) {
      await api.readFailed(e, fence);
      if (fence.valid() && token === generation.current) setError(message(e));
    } finally {
      fence.done();
      setBusy(false);
    }
  }
  async function readCalculation() {
    const token = generation.current,
      fence = api.fence({ studyId });
    try {
      const run = await api.run(studyId, runId);
      if (run.state === 'recorded' && design && combo) {
        const operations = await api.explorationSamples(
          studyId,
          answer.answer_version_id,
          fence.signal,
        );
        const previous = operations.find((op) =>
          op.request.combinations.some((c) => c.configuration_revision_id === configuration),
        );
        const index =
          previous?.request.combinations.findIndex(
            (c) => c.configuration_revision_id === configuration,
          ) ?? -1;
        if (previous && index >= 0)
          await api.adoptExplorationPoint(studyId, previous.operation_id, runId, index);
      }
      if (fence.valid() && token === generation.current)
        setLoaded(
          (old) =>
            old && { ...old, runs: [...old.runs.filter((r) => r.run_id !== run.run_id), run] },
        );
    } catch (e) {
      await api.readFailed(e, fence);
      if (fence.valid() && token === generation.current) setError(message(e));
    } finally {
      fence.done();
    }
  }
  const snapshot = loaded?.frozen.model_snapshot;
  function changeCategory(index: number, value: string) {
    if (!design) return;
    const next = categories.map((v, i) => (i === index ? value : v));
    const mapped = supportedCombination(design.request.combinations, next);
    generation.current++;
    if (!mapped) {
      setLoaded(null);
      setError('This category combination is not supported.');
      return;
    }
    carry.current = { vector: selected, dimensions };
    setLoaded(null);
    setPrediction(null);
    setCategories(next);
    setConfiguration(mapped.configuration_revision_id);
  }
  return (
    <AnswerExplorationPanel
      settings={
        <ActionDialog
          title="Sample settings"
          label="Sample settings"
          closeLabel="Close"
          width="workspace"
        >
          {loaded && (
            <ExplorationSettings
              api={api}
              studyId={studyId}
              answer={answer}
              basis={loaded.basis}
              design={design}
              categories={categories}
              onPrepared={() => setRefresh((v) => v + 1)}
              onSaved={(d) => {
                const selectedCombo =
                  supportedCombination(d.request.combinations, categories) ??
                  d.request.combinations[0];
                setDesign(d);
                setCategories(selectedCombo.categories);
                setConfiguration(selectedCombo.configuration_revision_id);
              }}
            />
          )}
          {!design && answer.basis.configuration_revision_ids.length > 1 && (
            <label>
              Answer configuration
              <Select value={configuration} onChange={(e) => setConfiguration(e.target.value)}>
                {answer.basis.configuration_revision_ids.map((id, i) => (
                  <option key={id} value={id}>
                    Configuration {i + 1}
                  </option>
                ))}
              </Select>
            </label>
          )}
          {!!loaded?.fits.length && (
            <label>
              Prepared response
              <Select
                value={fitIndex}
                disabled={!loaded.fits.length}
                onChange={(e) => {
                  setFitIndex(Number(e.target.value));
                  setActiveAxis(loaded.fits[Number(e.target.value)].request.axis);
                }}
              >
                {loaded.fits.map((f, i) => (
                  <option key={f.identity} value={i}>
                    {loaded.basis.inputs.find((p) => key(p.target) === key(f.request.axis))?.name}
                    {' · '}
                    {f.request.method === 'kriging' ? 'Kriging' : 'Response surface'} ·{' '}
                    {f.request.lower}–{f.request.upper}
                  </option>
                ))}
              </Select>
            </label>
          )}
          {fit && (
            <>
              <p>
                {preparationCounts} {fit.request.rationale}
              </p>
              <p>Observed agreement with the model is not physical validation.</p>
            </>
          )}
          {!!loaded?.fits.length && (
            <Button disabled={busy} onClick={() => setRefresh((n) => n + 1)}>
              Refresh preparations
            </Button>
          )}
          <Button
            variant="secondary"
            disabled={!loaded || !vector || busy || !!api.pending}
            onClick={() => void calculate()}
          >
            Calculate selected point
          </Button>
          {busy && <p role="status">Submitting selected point…</p>}
          {runId && (
            <>
              <p role="status">Calculation submitted.</p>
              <Button onClick={() => void readCalculation()}>Read selected calculation</Button>
              <Button onClick={() => onOpen({ study: studyId, view: 'runs', run: runId })}>
                Open selected run
              </Button>
            </>
          )}
          {error && <p role="alert">{error}</p>}
        </ActionDialog>
      }
      categories={
        <>
          {loaded && (
            <label>
              Plot against
              <Select
                value={activeAxis ? key(activeAxis) : ''}
                onChange={(e) => {
                  const input = loaded.basis.inputs.find((p) => key(p.target) === e.target.value);
                  if (input) setActiveAxis(input.target);
                }}
              >
                {loaded.basis.inputs
                  .filter((p) => p.binding.kind === 'free')
                  .map((p) => (
                    <option key={key(p.target)} value={key(p.target)}>
                      {p.name} · {p.instance_name}
                    </option>
                  ))}
              </Select>
            </label>
          )}
          {design?.request.category_dimensions.map((d, i) => (
            <label key={d.name}>
              {d.name}
              <Select
                value={categories[i] ?? ''}
                onChange={(e) => changeCategory(i, e.target.value)}
              >
                {d.values.map((v) => (
                  <option
                    key={v}
                    value={v}
                    disabled={
                      !supportedCombination(
                        design.request.combinations,
                        categories.map((old, n) => (n === i ? v : old)),
                      )
                    }
                  >
                    {v}
                    {!supportedCombination(
                      design.request.combinations,
                      categories.map((old, n) => (n === i ? v : old)),
                    )
                      ? ' — unsupported combination'
                      : ''}
                  </option>
                ))}
              </Select>
            </label>
          ))}
        </>
      }
      footer={
        loaded && (
          <ActionGroup>
            <Button
              onClick={() => {
                generation.current++;
                setSelected(explorationInputVector(loaded.basis.inputs)!);
              }}
            >
              Reset inputs
            </Button>
            <Button
              onClick={() =>
                onOpen({
                  study: studyId,
                  view: 'model',
                  model: loaded.basis.model_id,
                  revision: loaded.basis.model_revision_id,
                  approach: answer.approach_version_id,
                })
              }
            >
              Open model
            </Button>
          </ActionGroup>
        )
      }
    >
      {error && <p role="alert">{error}</p>}
      {!configuration ? (
        <p>No configuration is linked directly to this answer.</p>
      ) : !loaded ? (
        <p role="status">Loading answer basis…</p>
      ) : (
        <>
          {!loaded.fits.length && !surrogate && (
            <p>
              {compatibleUnits
                ? 'No prepared estimates. Calculated results remain available.'
                : 'Estimates need model-declared units. Saved quantities stay unchanged.'}
            </p>
          )}
          <p className="hf-slider-caption">
            <span className="hf-result-basis hf-result-basis--calculated">
              <span aria-hidden="true">●</span> calculated
            </span>
            {' · '}
            <span className="hf-result-basis hf-result-basis--estimated">
              <span aria-hidden="true">○</span> estimated
            </span>
            {' · '}
            <span className="hf-result-basis hf-result-basis--unavailable">
              <span aria-hidden="true">□</span> no result
            </span>
          </p>
          <p className="hf-slider-caption">
            Plots vary the chosen input; other inputs keep their selected values.
          </p>
          {axis && dimensions.find((d) => key(d.target) === key(axis.target))?.covary_group && (
            <p className="hf-slider-caption">
              Linked inputs vary together:{' '}
              {loaded.basis.inputs
                .filter((p) => {
                  const group = dimensions.find(
                    (d) => key(d.target) === key(axis.target),
                  )?.covary_group;
                  return (
                    key(p.target) !== key(axis.target) &&
                    dimensions.some(
                      (d) => key(d.target) === key(p.target) && d.covary_group === group,
                    )
                  );
                })
                .map((p) => p.name + ' · ' + p.instance_name)
                .join(', ')}
              .
            </p>
          )}
          {vector && !selectedPoints.some((p) => p.outputs.some((o) => o.value !== null)) && (
            <p role="status" className="hf-exploration-gap">
              {predictionError ||
                'This input combination has no available results. Use Sample settings to calculate it or prepare more samples.'}
            </p>
          )}
          {snapshot ? (
            <GraphView
              projection={project(snapshot as Snapshot)}
              selection={selection}
              onSelect={setSelection}
              trace={{ nodes: new Set(), links: new Set() }}
              highlightedPorts={new Set(activeAxis ? [key(activeAxis)] : [])}
              portContent={(instanceId, port) => {
                const target = { instance_id: instanceId, port_id: port.port_id },
                  ref = key(target);
                const input = loaded.basis.inputs.find((p) => key(p.target) === ref);
                if (input)
                  return input.binding.kind === 'connected' ? (
                    <p className="hf-connected-input">{input.name} · Connected</p>
                  ) : (
                    <QuantitySlider
                      label={input.name}
                      units={savedInputQuantity(input)!.units}
                      stops={selectableStops(
                        points,
                        selected,
                        dimensions,
                        target,
                        loaded.basis.outputs.map((o) => o.target),
                      )}
                      lower={dimensions.find((d) => key(d.target) === ref)?.lower}
                      upper={dimensions.find((d) => key(d.target) === ref)?.upper}
                      step={dimensions.find((d) => key(d.target) === ref)?.step}
                      value={selected.find((p) => key(p.target) === ref)?.value ?? null}
                      onChange={(value) => {
                        generation.current++;
                        setSelected((old) => selectInput(old, dimensions, target, value));
                      }}
                    />
                  );
                const output = loaded.basis.outputs.find((p) => key(p.target) === ref);
                if (!output) return null;
                const index = fit?.request.tolerances.findIndex((t) => key(t.target) === ref) ?? -1;
                const estimated = fit?.numerical.result.outputs[index];
                const exact = calculated?.history?.results?.outputs.find(
                  (o) => key(o.target) === ref,
                );
                const calculatedPoints =
                  !axis || !vector
                    ? []
                    : points.flatMap((point) => {
                        const x = point.inputs.find(
                          (p) => key(p.target) === key(axis.target),
                        )?.value;
                        const output = point.outputs.find((o) => key(o.target) === ref);
                        return x !== undefined &&
                          output?.kind === 'calculated' &&
                          output.value !== null &&
                          sameInputVector(
                            selectInput(
                              vector,
                              dimensions,
                              axis.target,
                              x,
                            ) as ExplorationPoint['inputs'],
                            point.inputs,
                          )
                          ? [{ x, y: output.value }]
                          : [];
                      });
                const matchingCurve =
                  prediction &&
                  vector &&
                  activeAxis &&
                  prediction.vectors.every((v) => {
                    const coordinate = v.find((p) => key(p.target) === key(activeAxis))?.value;
                    return (
                      coordinate !== undefined &&
                      sameInputVector(
                        selectInput(
                          vector,
                          dimensions,
                          activeAxis,
                          coordinate,
                        ) as ExplorationPoint['inputs'],
                        v,
                      )
                    );
                  });
                const joint = matchingCurve
                  ? prediction.outputs.find((o) => key(o.target) === ref)
                  : undefined;
                const jointGroup = surrogate?.groups[combinationIndex];
                const jointAssessment = jointGroup?.outputs.find((o) => key(o.target) === ref);
                const candidates = selectedPoints.flatMap((p) =>
                  p.outputs.filter((o) => key(o.target) === ref),
                );
                const selectedResult =
                  candidates.find((o) => o.run_id && o.value !== null) ??
                  candidates.find((o) => o.value !== null) ??
                  candidates[0];
                const resultFit = loaded.fits.find(
                  (f) => f.identity === selectedResult?.preparation_id,
                );
                const resultMetric =
                  resultFit?.numerical.result.outputs[
                    resultFit.request.tolerances.findIndex((t) => key(t.target) === ref)
                  ];
                const originalRun = selectedResult?.run_id ?? calculated?.run_id;
                const result = selectedResult?.value ?? null;
                const resultKind =
                  selectedResult?.kind === 'calculated' ? 'calculated' : 'estimated';
                return (
                  <>
                    <QuantityResult
                      units={output.units}
                      value={result}
                      state={resultKind}
                      reason={explorationReason(
                        selectedResult?.reason || (calculated ? exact?.reason : null),
                      )}
                    />
                    {axis && current !== null && (
                      <ResponseCurve
                        label={output.name}
                        units={output.units}
                        axis={axis.name + ' (' + unitLabel(axis.units) + ')'}
                        selected={current}
                        selectedResult={{
                          value: result,
                          state: resultKind,
                        }}
                        points={
                          joint &&
                          prediction &&
                          joint.values.some((v) => v.value !== null && v.kind === 'estimated')
                            ? prediction.vectors.slice(1).map((v, i) => ({
                                x: v.find((p) => key(p.target) === key(axis.target))!.value,
                                y: joint.values[i + 1]?.value ?? null,
                              }))
                            : fit
                              ? fit.request.query_values.map((x, i) => ({
                                  x,
                                  y: estimated?.values[i] ?? null,
                                }))
                              : []
                        }
                        calculated={
                          joint &&
                          prediction &&
                          joint.values.some((v) => v.value !== null && v.kind === 'estimated')
                            ? prediction.vectors.slice(1).flatMap((v, i) => {
                                const value = joint.values[i + 1];
                                return value?.kind === 'calculated' && value.value !== null
                                  ? [
                                      {
                                        x: v.find((p) => key(p.target) === key(axis.target))!.value,
                                        y: value.value,
                                      },
                                    ]
                                  : [];
                              })
                            : calculatedPoints
                        }
                      />
                    )}
                    <div className="hf-output-actions">
                      <ActionDialog
                        variant="quiet"
                        title={output.name + ' result basis'}
                        label="Result basis"
                        size="sm"
                      >
                        {originalRun ? (
                          <Button
                            onClick={() =>
                              onOpen({ study: studyId, view: 'runs', run: originalRun })
                            }
                          >
                            Open calculated run
                          </Button>
                        ) : jointGroup && jointAssessment && !resultFit ? (
                          <>
                            <p>
                              {jointAssessment.method ?? 'No eligible method'};{' '}
                              {jointAssessment.metrics?.evaluable_count ?? 0} of{' '}
                              {jointAssessment.metrics?.assessed_count ?? 0} independent checks
                              evaluated.
                            </p>
                            <p>
                              Maximum observed absolute error:{' '}
                              {jointAssessment.metrics?.max_absolute_error == null
                                ? 'not computed'
                                : formatNumber(jointAssessment.metrics.max_absolute_error)}{' '}
                              {unitLabel(output.units)}. These checks do not establish a universal
                              error bound or physical validity.
                            </p>
                            <p>
                              {explorationReason(jointAssessment.reason) ??
                                'Observed targets met within the prepared domain.'}
                            </p>
                            <p>
                              Surrogate version: <code>{surrogate?.surrogate_version_id}</code>
                            </p>
                            <p>
                              Data artifact SHA-256: <code>{jointGroup.artifact_sha256}</code>
                            </p>
                          </>
                        ) : resultFit ? (
                          <>
                            <p>
                              Estimated from {resultFit.samples.length} original-model samples;{' '}
                              {resultMetric?.evaluable_count ?? 0} of{' '}
                              {resultMetric?.assessed_count ?? 0} independent checks evaluated.
                            </p>
                            <p>
                              Maximum observed absolute error:{' '}
                              {resultMetric?.max_absolute_error == null
                                ? 'not computed'
                                : formatNumber(resultMetric.max_absolute_error)}{' '}
                              {unitLabel(output.units)}
                            </p>
                            <p>
                              Response identity: <code>{resultFit.identity}</code>
                            </p>
                            <p>
                              Result SHA-256: <code>{resultFit.numerical.result_sha256}</code>
                            </p>
                          </>
                        ) : (
                          <p>No estimate is available.</p>
                        )}
                      </ActionDialog>
                    </div>
                  </>
                );
              }}
            />
          ) : (
            <p>This older model requires its model view.</p>
          )}
        </>
      )}
    </AnswerExplorationPanel>
  );
}
