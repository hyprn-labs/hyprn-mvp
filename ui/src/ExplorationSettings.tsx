import { useEffect, useRef, useState } from 'react';
import { HyprnMvpApi, ApiError, message } from './api';
import type {
  ExplorationBasis1,
  ExplorationDesign1,
  ExplorationDesignRequest1,
  ExplorationSampleOperation1,
  ExplorationSampleOperation2,
  ExplorationSampleRequest2,
  ExplorationSamplePreview1,
  ScientificAnswer1,
  ExplorationSurrogate1,
  ExplorationWarmOperation1,
} from './contract';
import {
  Button,
  Disclosure,
  TextInput,
  TextArea,
  Progress,
  DataTable,
  ActionGroup,
  ReadingSection,
  StatusTag,
} from './design';
import { unitLabel } from './unitLabels';
import { explorationReason } from './explorationInputs';

type Operation = ExplorationSampleOperation1 | ExplorationSampleOperation2;
const key = (p: { instance_id: string; port_id: string }) => p.instance_id + '/' + p.port_id;

/** Settings alone may save declarations or request expensive original evaluations. */
export function ExplorationSettings({
  api,
  studyId,
  answer,
  basis,
  design,
  categories,
  onSaved,
  onPrepared,
}: {
  api: HyprnMvpApi;
  studyId: string;
  answer: ScientificAnswer1;
  basis: ExplorationBasis1;
  design: ExplorationDesign1 | null;
  categories: string[];
  onSaved: (d: ExplorationDesign1) => void;
  onPrepared: () => void;
}) {
  const [draft, setDraft] = useState<ExplorationDesignRequest1>(
    () =>
      design?.request ?? {
        schema_version: '1',
        command_id: crypto.randomUUID(),
        answer_version_id: answer.answer_version_id,
        category_dimensions: [],
        combinations: [
          {
            categories: [],
            configuration_revision_id: basis.configuration_revision_id,
            model_id: basis.model_id,
            model_revision_id: basis.model_revision_id,
            initial_axis: basis.inputs.find((p) => p.binding.kind === 'free')!.target,
            dimensions: basis.inputs.flatMap((p) =>
              p.binding.kind === 'free'
                ? [
                    {
                      target: p.target,
                      units: p.binding.assignment.units,
                      lower: null,
                      upper: null,
                      step: null,
                      common_key: null,
                      covary_group: null,
                    },
                  ]
                : [],
            ),
          },
        ],
        rationale: '',
      },
  );
  const [operations, setOperations] = useState<Operation[]>([]);
  const [preview, setPreview] = useState<ExplorationSamplePreview1 | null>(null);
  const [surrogate, setSurrogate] = useState<ExplorationSurrogate1 | null>(null);
  const [warm, setWarm] = useState<ExplorationWarmOperation1 | null>(null);
  const [error, setError] = useState(''),
    [busy, setBusy] = useState(false);
  const [seed, setSeed] = useState('17'),
    [training, setTraining] = useState('3'),
    [checks, setChecks] = useState('2');
  const [budget, setBudget] = useState('10'),
    [wall, setWall] = useState('3600'),
    [pointWall, setPointWall] = useState('60');
  const [tolerances, setTolerances] = useState(
    basis.outputs.map((p) => ({ target: p.target, absolute: '', relative: '' })),
  );
  const pending = useRef<ExplorationSampleRequest2 | null>(null),
    generation = useRef(0);
  const combo =
    draft.combinations.find((c) => c.categories.every((v, i) => v === categories[i])) ??
    draft.combinations[0];
  const operation = operations[0];
  useEffect(() => {
    const fence = api.fence({ studyId });
    void api
      .explorationSamples(studyId, answer.answer_version_id, fence.signal)
      .then((ops) => {
        if (fence.valid()) setOperations(ops);
      })
      .catch(async (e) => {
        await api.readFailed(e, fence);
        if (fence.valid()) setError(message(e));
      })
      .finally(fence.done);
    return () => {
      generation.current++;
      fence.abort();
    };
  }, [api, studyId, answer.answer_version_id]);
  useEffect(() => {
    const fence = api.fence({ studyId });
    void api
      .explorationSurrogates(studyId, answer.answer_version_id, fence.signal)
      .then((items) => {
        if (fence.valid())
          setSurrogate(items.find((s) => s.design_id === design?.design_id) ?? null);
      })
      .catch(async (e) => {
        await api.readFailed(e, fence);
      })
      .finally(fence.done);
    return () => fence.abort();
  }, [api, studyId, answer.answer_version_id, design?.design_id]);
  useEffect(() => {
    if (!surrogate || !['pending', 'building'].includes(surrogate.state)) return;
    const fence = api.fence({ studyId });
    const timer = window.setInterval(() => {
      void api
        .readExplorationSurrogate(studyId, surrogate.surrogate_version_id, fence.signal)
        .then((value) => {
          if (fence.valid()) setSurrogate(value);
        })
        .catch(async (e) => {
          await api.readFailed(e, fence);
        });
    }, 1000);
    return () => {
      window.clearInterval(timer);
      fence.abort();
    };
  }, [api, studyId, surrogate?.surrogate_version_id, surrogate?.state]);
  useEffect(() => {
    if (!warm || warm.state !== 'pending') return;
    const fence = api.fence({ studyId });
    const timer = window.setInterval(() => {
      void api
        .readExplorationWarm(studyId, warm.command_id, fence.signal)
        .then((value) => {
          if (!fence.valid()) return;
          setWarm(value);
          if (value.state === 'ready') onPrepared();
        })
        .catch(async (e) => {
          await api.readFailed(e, fence);
        });
    }, 500);
    return () => {
      window.clearInterval(timer);
      fence.abort();
    };
  }, [api, studyId, warm?.command_id, warm?.state, onPrepared]);
  function invalidate() {
    generation.current++;
    setPreview(null);
    pending.current = null;
  }
  async function action(fn: () => Promise<void>) {
    const token = generation.current;
    setBusy(true);
    setError('');
    try {
      await fn();
    } catch (e) {
      if (token === generation.current)
        setError(
          e instanceof ApiError && e.detail.fields.length
            ? e.detail.fields.map((f) => f.path + ': ' + f.message).join(' ')
            : message(e),
        );
    } finally {
      setBusy(false);
    }
  }
  function sampleRequest(): ExplorationSampleRequest2 {
    if (
      !design ||
      JSON.stringify({ ...draft, command_id: '' }) !==
        JSON.stringify({ ...design.request, command_id: '' })
    )
      throw new Error('Save the input design before previewing samples.');
    if (
      [seed, training, checks, budget, wall, pointWall].some(
        (value) => value.trim() === '' || !Number.isSafeInteger(Number(value)),
      )
    )
      throw new Error('Enter a whole number for the seed, sample counts and time budgets.');
    if (tolerances.some((t) => t.absolute.trim() === '' || t.relative.trim() === ''))
      throw new Error('Declare absolute and relative error targets for every output.');
    return {
      schema_version: '2',
      command_id: crypto.randomUUID(),
      previous_operation_id: operation?.operation_id ?? null,
      seed: Number(seed),
      category_dimensions: draft.category_dimensions,
      // Sampling the selected tuple has an explicit scope and exact configuration pin.
      combinations: [
        {
          ...combo,
          answer_version_id: answer.answer_version_id,
          training_count: Number(training),
          check_count: Number(checks),
          tolerances: tolerances.map((t) => ({
            ...t,
            absolute: Number(t.absolute),
            relative: Number(t.relative),
          })),
        },
      ],
      budget: {
        additional_evaluations: Number(budget),
        wall_seconds: Number(wall),
        point_wall_seconds: Number(pointWall),
        concurrency: 1,
      },
      rationale: draft.rationale,
    };
  }
  return (
    <>
      <p>Sampling scope: {combo.categories.join(' · ') || 'This configuration'}</p>
      <Disclosure open>
        <summary>Input ranges and steps</summary>
        <p>Blank step allows continuous selection. Linked inputs move together.</p>
        <DataTable
          label="Input ranges and steps"
          className="hf-settings-table"
          columns={[
            { key: 'quantity', label: 'Input' },
            { key: 'lower', label: 'Minimum' },
            { key: 'upper', label: 'Maximum' },
            { key: 'step', label: 'Step' },
          ]}
          rows={combo.dimensions.map((d) => {
            const input = basis.inputs.find((p) => key(p.target) === key(d.target));
            const name = input?.name ?? d.target.port_id;
            const linked = combo.dimensions
              .filter((p) => p !== d && d.covary_group && p.covary_group === d.covary_group)
              .map(
                (p) =>
                  basis.inputs.find((v) => key(v.target) === key(p.target))?.name ??
                  p.target.port_id,
              );
            return {
              quantity: (
                <>
                  <strong>{name}</strong>
                  <div>{input?.instance_name}</div>
                  <div>{unitLabel(d.units)}</div>
                  {linked.length > 0 && <small>Linked with {linked.join(', ')}</small>}
                </>
              ),
              ...Object.fromEntries(
                (['lower', 'upper', 'step'] as const).map((field) => [
                  field,
                  <TextInput
                    aria-label={name + ' ' + field}
                    type="number"
                    step="any"
                    value={d[field] ?? ''}
                    onChange={(e) => {
                      const value = e.target.value === '' ? null : e.target.valueAsNumber;
                      invalidate();
                      setDraft({
                        ...draft,
                        combinations: draft.combinations.map((c) =>
                          c === combo
                            ? {
                                ...c,
                                dimensions: c.dimensions.map((p) =>
                                  p === d ? { ...p, [field]: value } : p,
                                ),
                              }
                            : c,
                        ),
                      });
                    }}
                  />,
                ]),
              ),
            };
          })}
        />
        <label>
          Design rationale
          <TextArea
            value={draft.rationale}
            onChange={(e) => {
              invalidate();
              setDraft({ ...draft, rationale: e.target.value });
            }}
          />
        </label>
        <Button
          disabled={busy || !!api.pending}
          onClick={() =>
            void action(async () => {
              const saved = await api.saveExplorationDesign(studyId, {
                ...draft,
                command_id: crypto.randomUUID(),
              });
              setDraft(saved.request);
              onSaved(saved);
            })
          }
        >
          Save input design
        </Button>
      </Disclosure>
      <Disclosure>
        <summary>Sampling budget and error targets</summary>
        <p>
          Proposed next sampling request. These settings do not describe the recorded samples or
          assessment below.
        </p>
        <div className="hf-sampling-budget">
          {(
            [
              ['Seed', seed, setSeed],
              ['Training calculations', training, setTraining],
              ['Independent checks', checks, setChecks],
              ['Maximum additional evaluations', budget, setBudget],
              ['Total time limit (seconds)', wall, setWall],
              ['Time limit per calculation (seconds)', pointWall, setPointWall],
            ] as const
          ).map(([label, value, setter]) => (
            <label key={label}>
              {label}
              <TextInput
                type="number"
                step="1"
                value={value}
                onChange={(e) => {
                  invalidate();
                  setter(e.target.value);
                }}
              />
            </label>
          ))}
        </div>
        <p>
          Absolute targets use the output unit; relative targets are fractions (0.01 = 1%). Both
          must be explicit, including zero.
        </p>
        <DataTable
          label="Output error targets"
          className="hf-settings-table"
          columns={[
            { key: 'quantity', label: 'Output' },
            { key: 'absolute', label: 'Absolute error' },
            { key: 'relative', label: 'Relative error' },
          ]}
          rows={tolerances.map((t, index) => ({
            quantity: (
              <>
                <strong>{basis.outputs[index].name}</strong>
                <div>{unitLabel(basis.outputs[index].units)}</div>
              </>
            ),
            ...Object.fromEntries(
              (['absolute', 'relative'] as const).map((field) => [
                field,
                <TextInput
                  aria-label={basis.outputs[index].name + ' ' + field + ' error'}
                  type="number"
                  step="any"
                  value={t[field]}
                  onChange={(e) => {
                    invalidate();
                    setTolerances(
                      tolerances.map((v) => (v === t ? { ...v, [field]: e.target.value } : v)),
                    );
                  }}
                />,
              ]),
            ),
          }))}
        />
        <Button
          disabled={busy || !!api.pending}
          onClick={() =>
            void action(async () => {
              const body = sampleRequest(),
                token = generation.current;
              const p = await api.previewExplorationSamples(studyId, body);
              if (token === generation.current) {
                pending.current = body;
                setPreview(p);
              }
            })
          }
        >
          Preview samples
        </Button>
        {preview && (
          <>
            <p role="status">
              {preview.retained_count} reusable · {preview.new_count} new calculations ·{' '}
              {preview.total_count} total
            </p>
            <Button
              variant="primary"
              disabled={busy || !!api.pending}
              onClick={() =>
                void action(async () => {
                  if (!pending.current) return;
                  const op = await api.submitExplorationSamples(studyId, pending.current);
                  setOperations([op, ...operations]);
                  setPreview(null);
                  pending.current = null;
                })
              }
            >
              Prepare samples
            </Button>
          </>
        )}
      </Disclosure>
      {operation && (
        <ReadingSection aria-label="Recorded samples">
          <h3>Recorded samples</h3>
          <ActionGroup>
            <Button
              disabled={
                busy || !design || !['complete', 'limited', 'cancelled'].includes(operation.state)
              }
              onClick={() =>
                void action(async () => {
                  if (!design) return;
                  setSurrogate(
                    await api.buildExplorationSurrogate(studyId, {
                      schema_version: '1',
                      command_id: crypto.randomUUID(),
                      design_id: design.design_id,
                      sample_operation_id: operation.operation_id,
                    }),
                  );
                })
              }
            >
              Build and assess estimates
            </Button>
          </ActionGroup>
          <p role="status">
            Samples: {operation.state} · {operation.completed_count} completed ·{' '}
            {operation.failed_count} failed · {operation.allocation.total_count} total.
            {operation.attempted_count > 0 && (
              <>
                {' '}
                {operation.attempted_count} attempted in this operation ·{' '}
                {operation.elapsed_seconds.toFixed(1)} s elapsed.
              </>
            )}{' '}
            {explorationReason(operation.reason)}
          </p>
          {['pending', 'designing', 'sampling'].includes(operation.state) && (
            <Progress
              label={'Sampling: ' + operation.state}
              count={{
                completed: operation.completed_count,
                total: operation.allocation.total_count,
              }}
              message="Completed sample points; this is not an elapsed-time percentage."
            />
          )}
          <ActionGroup>
            <Button
              disabled={busy}
              onClick={() =>
                void action(async () => {
                  const op = await api.readExplorationSamples(studyId, operation.operation_id);
                  setOperations([op, ...operations.slice(1)]);
                })
              }
            >
              Read sampling progress
            </Button>
            {(['cancel', 'reconcile', 'resume'] as const)
              .filter((kind) =>
                kind === 'cancel'
                  ? ['pending', 'designing', 'sampling', 'uncertain'].includes(operation.state)
                  : kind === 'resume'
                    ? ['cancelled', 'limited'].includes(operation.state) &&
                      (!!operation.design_digest || !operation.reason)
                    : ['uncertain', 'cancelled'].includes(operation.state) &&
                      !!operation.design_digest,
              )
              .map((kind) => (
                <Button
                  key={kind}
                  disabled={busy || !!api.pending}
                  onClick={() =>
                    void action(async () => {
                      const op = await api.controlExplorationSamples(
                        studyId,
                        operation.operation_id,
                        kind,
                      );
                      setOperations([op, ...operations.slice(1)]);
                    })
                  }
                >
                  {kind === 'cancel'
                    ? 'Cancel sampling'
                    : kind === 'resume'
                      ? 'Resume sampling'
                      : 'Reconcile sampling'}
                </Button>
              ))}
          </ActionGroup>
        </ReadingSection>
      )}
      {surrogate && (
        <ReadingSection aria-label="Recorded assessment">
          <h3>Recorded assessment</h3>
          <p role="status">
            Assessment process: {surrogate.state} · {surrogate.completed_groups}
            {' of '}
            {surrogate.total_groups} groups assessed. {explorationReason(surrogate.reason)}
          </p>
          {['pending', 'building'].includes(surrogate.state) && (
            <Progress
              label={'Estimate assessment: ' + surrogate.state}
              count={{ completed: surrogate.completed_groups, total: surrogate.total_groups }}
            />
          )}
          <ActionGroup>
            <Button
              disabled={busy}
              onClick={() =>
                void action(async () => {
                  setSurrogate(
                    await api.readExplorationSurrogate(studyId, surrogate.surrogate_version_id),
                  );
                })
              }
            >
              Refresh assessment
            </Button>
            {['pending', 'building'].includes(surrogate.state) && (
              <Button
                disabled={busy}
                onClick={() =>
                  void action(async () => {
                    setSurrogate(
                      await api.cancelExplorationSurrogate(studyId, surrogate.surrogate_version_id),
                    );
                  })
                }
              >
                Cancel assessment
              </Button>
            )}
            <Button
              disabled={busy || !['ready', 'assessed'].includes(surrogate.state)}
              onClick={() =>
                void action(async () => {
                  setWarm(
                    await api.warmExplorationSurrogate(studyId, surrogate.surrogate_version_id),
                  );
                })
              }
            >
              Prepare fast predictions
            </Button>
          </ActionGroup>
          <p>
            Completion describes the assessment process. Each output must meet its error target
            before it can be estimated.
          </p>
          {surrogate.groups.map((g) => {
            const sampled = operations.find(
              (op) => op.operation_id === surrogate.sample_operation_id,
            )?.request.combinations[g.combination];
            const group = design?.request.combinations.find(
              (c) => c.configuration_revision_id === sampled?.configuration_revision_id,
            );
            const sameModel = group?.model_revision_id === basis.model_revision_id;
            return (
              <Disclosure
                key={g.identity}
                open={group?.configuration_revision_id === basis.configuration_revision_id}
              >
                <summary>
                  {group?.categories.join(' · ') || 'Configuration ' + (g.combination + 1)} ·{' '}
                  {g.outputs.filter((o) => !o.reason && o.metrics?.target_met).length} of{' '}
                  {g.outputs.length} outputs meet targets
                </summary>
                <DataTable
                  label={'Assessment for ' + (group?.categories.join(' · ') || g.combination + 1)}
                  columns={[
                    { key: 'quantity', label: 'Output' },
                    { key: 'state', label: 'Assessment' },
                    { key: 'checks', label: 'Checks', numeric: true },
                  ]}
                  rows={g.outputs.map((o) => ({
                    quantity: (
                      <>
                        {(sameModel &&
                          basis.outputs.find((v) => key(v.target) === key(o.target))?.name) ||
                          o.target.port_id}
                        <div>{unitLabel(o.units)}</div>
                      </>
                    ),
                    state: (
                      <>
                        <StatusTag tone={!o.reason && o.metrics?.target_met ? 'ok' : 'advisory'}>
                          {!o.reason && o.metrics?.target_met ? 'Target met' : 'Not eligible'}
                        </StatusTag>
                        {o.reason && <p>{explorationReason(o.reason)}</p>}
                      </>
                    ),
                    checks: o.metrics?.assessed_count ?? 0,
                  }))}
                />
              </Disclosure>
            );
          })}
        </ReadingSection>
      )}
      {warm && (
        <>
          <p role="status">
            Fast predictions: {warm.state}. {explorationReason(warm.reason)}
          </p>
          {warm.state === 'pending' && <Progress label="Preparing fast predictions" />}
          <Button
            disabled={busy}
            onClick={() =>
              void action(async () => {
                setWarm(await api.readExplorationWarm(studyId, warm.command_id));
              })
            }
          >
            Refresh prediction readiness
          </Button>
        </>
      )}
      {error && <p role="alert">{error}</p>}
    </>
  );
}
