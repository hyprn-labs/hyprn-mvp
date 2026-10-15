import { useEffect, useRef, useState } from 'react';
import { HyprnMvpApi, message } from './api';
import type {
  ConfigurationRequest4,
  ExplorationBasis1,
  ExplorationPrediction1,
  FrozenConfigurationRead7,
  PortRef,
  PublicRunDetail,
  ScientificAnswer1,
} from './contract';
import { GraphView, project, type Snapshot } from './GraphView';
import {
  ActionDialog,
  Button,
  Panel,
  QuantityResult,
  QuantitySlider,
  ResponseCurve,
  SectionHeader,
  Select,
  formatNumber,
} from './design';
import { unitLabel } from './unitLabels';
import type { Selection, WorkspaceLink } from './workspaceModel';
import { useAccessLoss } from './accessLoss';
import {
  explorationInputVector,
  preparedInputUnitsMatch,
  savedInputQuantity,
  sameInputVector,
} from './explorationInputs';

const key = (ref: PortRef) => ref.instance_id + '/' + ref.port_id;
type Loaded = {
  basis: ExplorationBasis1;
  frozen: FrozenConfigurationRead7;
  fits: ExplorationPrediction1[];
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
  const [fitIndex, setFitIndex] = useState(0),
    [value, setValue] = useState<number | null | undefined>(undefined);
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
    setValue(undefined);
    setError('');
    setFitIndex(0);
    setRunId('');
    if (!configuration) return () => fence.abort();
    void Promise.all([
      api.explorationBasis(studyId, answer.answer_version_id, configuration, fence.signal),
      api.configuration(studyId, configuration, fence.signal),
      api.preparedExplorations(studyId, answer.answer_version_id, configuration, fence.signal),
    ])
      .then(async ([basis, frozen, operations]) => {
        const fits = operations.flatMap((op) =>
          op.state === 'complete' && op.result ? [op.result] : [],
        );
        if (fits.some((f) => f.basis.digest !== basis.digest))
          throw new Error('Prepared response does not match this answer basis.');
        const runs = await Promise.all(basis.run_ids.map((id) => api.run(studyId, id)));
        if (fence.valid() && token === generation.current) setLoaded({ basis, frozen, fits, runs });
      })
      .catch(async (e) => {
        await api.readFailed(e, fence);
        if (fence.valid() && token === generation.current) setError(message(e));
      })
      .finally(fence.done);
    return () => fence.abort();
  }, [api, studyId, answer.answer_version_id, configuration, refresh]);

  const compatibleUnits = loaded && preparedInputUnitsMatch(loaded.basis.inputs);
  const fit = compatibleUnits ? loaded?.fits[fitIndex] : undefined;
  const axis = fit && loaded?.basis.inputs.find((p) => key(p.target) === key(fit.request.axis));
  const baseline = axis?.binding.kind === 'free' ? axis.binding.assignment.value : null;
  const current = value === undefined ? baseline : value;
  const values = fit
    ? [...new Set([...fit.request.query_values, ...(baseline === null ? [] : [baseline])])].sort(
        (a, b) => a - b,
      )
    : [];
  const vector = loaded && explorationInputVector(loaded.basis.inputs, axis?.target, current);
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
  const query = fit?.request.query_values.indexOf(current ?? NaN) ?? -1;
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
      if (token === generation.current) setBusy(false);
    }
  }
  async function readCalculation() {
    const token = generation.current,
      fence = api.fence({ studyId });
    try {
      const run = await api.run(studyId, runId);
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
  return (
    <Panel label="Explore the answer">
      <SectionHeader
        level={3}
        title="Explore the answer"
        actions={
          <ActionDialog title="Sample settings" label="Sample settings">
            {answer.basis.configuration_revision_ids.length > 1 && (
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
            <p>
              One prepared input slice. Other inputs stay at this configuration’s values. Sampling
              and rebuilding are not available here yet.
            </p>
            {loaded && (
              <label>
                Prepared response
                <Select
                  value={fitIndex}
                  disabled={!loaded.fits.length}
                  onChange={(e) => {
                    setFitIndex(Number(e.target.value));
                    setValue(undefined);
                  }}
                >
                  {loaded.fits.map((f, i) => (
                    <option key={f.identity} value={i}>
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
            <Button disabled={busy} onClick={() => setRefresh((n) => n + 1)}>
              Refresh preparations
            </Button>
            <Button
              variant="primary"
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
      />
      {error && <p role="alert">{error}</p>}
      {!configuration ? (
        <p>No configuration is linked directly to this answer.</p>
      ) : !loaded ? (
        <p role="status">Loading answer basis…</p>
      ) : (
        <>
          {!fit && (
            <p>
              {compatibleUnits
                ? 'No prepared estimates. Calculated results remain available.'
                : 'Estimates need model-declared units. Saved quantities stay unchanged.'}
            </p>
          )}
          {snapshot ? (
            <GraphView
              projection={project(snapshot as Snapshot)}
              selection={selection}
              onSelect={setSelection}
              trace={{ nodes: new Set(), links: new Set() }}
              portContent={(instanceId, port) => {
                const target = { instance_id: instanceId, port_id: port.port_id },
                  ref = key(target);
                const input = loaded.basis.inputs.find((p) => key(p.target) === ref);
                if (input)
                  return input.binding.kind === 'connected' ? (
                    <p>Connected · {unitLabel(input.units)}</p>
                  ) : axis && ref === key(axis.target) ? (
                    <QuantitySlider
                      label={input.name}
                      units={savedInputQuantity(input)!.units}
                      values={values}
                      value={current}
                      onChange={setValue}
                    />
                  ) : (
                    <p className="hf-mono">
                      {formatNumber(input.binding.assignment.value)}{' '}
                      {unitLabel(savedInputQuantity(input)!.units)} · Fixed
                    </p>
                  );
                const output = loaded.basis.outputs.find((p) => key(p.target) === ref);
                if (!output) return null;
                const index = fit?.request.tolerances.findIndex((t) => key(t.target) === ref) ?? -1;
                const estimated = fit?.numerical.result.outputs[index];
                const assessed =
                  `${estimated?.evaluable_count ?? 0} of ` +
                  `${estimated?.assessed_count ?? 0} independent checks evaluated.`;
                const exact = calculated?.history?.results?.outputs.find(
                  (o) => key(o.target) === ref,
                );
                const calculatedPoints =
                  !axis || !vector
                    ? []
                    : loaded.runs.flatMap((run) => {
                        const c = run.history?.configuration;
                        if (
                          !c ||
                          c.model_revision_id !== loaded.basis.model_revision_id ||
                          c.inputs.length !== vector.length
                        )
                          return [];
                        if (
                          !vector.every((v) =>
                            c.inputs.some(
                              (i) =>
                                key(i.target) === key(v.target) &&
                                i.units === v.units &&
                                (key(v.target) === key(axis.target) || i.value === v.value),
                            ),
                          )
                        )
                          return [];
                        const x = c.inputs.find((i) => key(i.target) === key(axis.target))?.value;
                        const output = run.history?.results?.outputs.find(
                          (o) => key(o.target) === ref,
                        );
                        return x !== undefined &&
                          output?.availability === 'available' &&
                          output.value !== null
                          ? [{ x, y: output.value }]
                          : [];
                      });
                const result = calculated
                  ? exact?.availability === 'available'
                    ? exact.value
                    : null
                  : query >= 0
                    ? (estimated?.values[query] ?? null)
                    : null;
                return (
                  <>
                    <QuantityResult
                      units={output.units}
                      value={result}
                      state={calculated ? 'calculated' : 'estimated'}
                      reason={calculated ? exact?.reason : estimated?.reason}
                    />
                    {fit && axis && current !== null && (
                      <ResponseCurve
                        label={output.name}
                        units={output.units}
                        axis={axis.name + ' (' + unitLabel(axis.units) + ')'}
                        selected={current}
                        points={fit.request.query_values.map((x, i) => ({
                          x,
                          y: estimated?.values[i] ?? null,
                        }))}
                        calculated={calculatedPoints}
                      />
                    )}
                    <ActionDialog
                      title={output.name + ' result basis'}
                      label="Result basis"
                      size="sm"
                    >
                      {calculated ? (
                        <Button
                          onClick={() =>
                            onOpen({ study: studyId, view: 'runs', run: calculated.run_id })
                          }
                        >
                          Open calculated run
                        </Button>
                      ) : fit ? (
                        <>
                          <p>
                            Estimated from {fit.samples.length} original-model samples; {assessed}
                          </p>
                          <p>
                            Maximum observed absolute error:{' '}
                            {estimated?.max_absolute_error == null
                              ? 'not computed'
                              : formatNumber(estimated.max_absolute_error)}{' '}
                            {unitLabel(output.units)}
                          </p>
                          <p>
                            Response identity: <code>{fit.identity}</code>
                          </p>
                          <p>
                            Result SHA-256: <code>{fit.numerical.result_sha256}</code>
                          </p>
                        </>
                      ) : (
                        <p>No estimate is available.</p>
                      )}
                    </ActionDialog>
                  </>
                );
              }}
            />
          ) : (
            <p>This older model requires its model view.</p>
          )}
          <Button
            onClick={() =>
              onOpen({
                study: studyId,
                view: 'model',
                model: loaded.basis.model_id,
                revision: loaded.basis.model_revision_id,
              })
            }
          >
            Open model
          </Button>
        </>
      )}
    </Panel>
  );
}
