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
} from './contract';
import { Button, Disclosure, TextInput } from './design';
import { unitLabel } from './unitLabels';

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
}: {
  api: HyprnMvpApi;
  studyId: string;
  answer: ScientificAnswer1;
  basis: ExplorationBasis1;
  design: ExplorationDesign1 | null;
  categories: string[];
  onSaved: (d: ExplorationDesign1) => void;
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
        {combo.dimensions.map((d) => {
          const name =
            basis.inputs.find((p) => key(p.target) === key(d.target))?.name ?? d.target.port_id;
          return (
            <fieldset key={key(d.target)}>
              <legend>
                {name} · {unitLabel(d.units)}
              </legend>
              {(['lower', 'upper', 'step'] as const).map((field) => (
                <label key={field}>
                  {name} {field}
                  <TextInput
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
                  />
                </label>
              ))}
              {d.covary_group && <p>Linked selection: {d.covary_group}</p>}
            </fieldset>
          );
        })}
        <label>
          Design rationale
          <TextInput
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
        {(
          [
            ['Seed', seed, setSeed],
            ['Training calculations', training, setTraining],
            ['Independent checks', checks, setChecks],
            ['Maximum additional evaluations', budget, setBudget],
            ['Wall budget seconds', wall, setWall],
            ['Per-calculation seconds', pointWall, setPointWall],
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
        <p>Concurrency: 1</p>
        {tolerances.map((t, index) => (
          <fieldset key={key(t.target)}>
            <legend>
              {basis.outputs[index].name} error target · {unitLabel(basis.outputs[index].units)}
            </legend>
            {(['absolute', 'relative'] as const).map((field) => (
              <label key={field}>
                {basis.outputs[index].name} {field} error
                <TextInput
                  type="number"
                  step="any"
                  value={t[field]}
                  onChange={(e) => {
                    invalidate();
                    setTolerances(
                      tolerances.map((v) => (v === t ? { ...v, [field]: e.target.value } : v)),
                    );
                  }}
                />
              </label>
            ))}
          </fieldset>
        ))}
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
        <>
          <p role="status">
            Samples: {operation.state} · {operation.completed_count} completed ·{' '}
            {operation.failed_count} failed · {operation.attempted_count} attempted of{' '}
            {operation.allocation.total_count}. {operation.reason}
          </p>
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
          {(['cancel', 'reconcile', 'resume'] as const).map((kind) => (
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
        </>
      )}
      {error && <p role="alert">{error}</p>}
    </>
  );
}
