import { DialogActions } from './design';
import {
  AnalysisEstimateSettings,
  estimateChoices,
  estimatePlan,
} from './AnalysisEstimateSettings';
import { useCollectionRead } from './useCollectionRead';
import { CollectionStatus } from './design';
import { useId, useEffect, useRef, useState } from 'react';
import { message, type HyprnMvpApi } from './api';
import { useStudyRead } from './calculationReads';
import type { CalculationScope } from './calculationScope';
import type {
  CalculationEstimateRead2,
  CalculationSampleOperationRead4,
  CalculationVersionRead4,
  FrozenConfigurationRead7,
  PortRef,
  ConfigurationCommit6,
  ConfigurationRequest6,
  ModelRevisionRead5,
} from './contract';
import { modelPorts } from './ConfigurationPanel';
import {
  ActionDialog,
  Button,
  Checkbox,
  DataTable,
  Panel,
  Progress,
  Select,
  StatusTag,
  FormField,
  SavedField,
  MetricGrid,
  SurrogateValidation,
  SectionHelp,
  ErrorAllowance,
  TextArea,
  TextInput,
  formatNumber,
  type Tone,
} from './design';
import { resolvedUnit, unitLabel } from './unitLabels';
import { samplingDeclaration, samplingRows, type SamplingRow } from './samplingInputs';

export const refKey = (ref: PortRef) => ref.instance_id + '/' + ref.port_id;
const POLL_MS = 1000;

/** Repeats ``load`` until ``done`` holds; stops when the owning component goes away. */
function usePoll() {
  const timer = useRef<number | undefined>(undefined);
  useEffect(() => () => window.clearTimeout(timer.current), []);
  return function poll<T>(
    load: () => Promise<T>,
    done: (value: T) => boolean,
    apply: (value: T) => void,
    fail: (e: unknown) => void,
  ) {
    const step = () =>
      void load().then((value) => {
        apply(value);
        if (!done(value)) timer.current = window.setTimeout(step, POLL_MS);
      }, fail);
    timer.current = window.setTimeout(step, POLL_MS);
  };
}

const sampleProgress: Record<CalculationSampleOperationRead4['state'], string> = {
  pending: 'Queued — waiting for the computation environment',
  designing: 'Generating the seeded points',
  configuring: 'Saving each point as a configuration version',
  complete: 'Saved',
  failed: 'Sampling failed',
  uncertain: 'Outcome unknown',
};

/** Prepare explicit independent inputs, then generate seeded points in their declared units.
 * The saved preparation anchor is an execution detail, not a configuration-picker default. The points are saved as configuration versions
 * and become the version's members; a new version of a sampled calculation keeps every existing
 * point that still fits. */
export function SamplingDialog({
  api,
  study,
  scope,
  current,
  creation,
  onSaved,
}: {
  api: HyprnMvpApi;
  study: string;
  scope: CalculationScope;
  current?: CalculationVersionRead4;
  creation?: {
    activation: number;
    active: boolean;
    name: string;
    description: string;
    onBusy: (busy: boolean) => void;
    readOnly?: boolean;
  };
  onSaved: (versionId: string) => void;
}) {
  const formId = useId();
  const design = current?.content.design.kind === 'sampled' ? current.content.design : null;
  const group = design?.groups[0];
  const savedPlan = current?.content.schema_version === '4' ? current.content.estimate_plan : null;
  const [estimatesEnabled, setEstimatesEnabled] = useState(!!savedPlan);
  const [estimateRows, setEstimateRows] = useState(() => estimateChoices(savedPlan));
  const [model, setModel] = useState<ModelRevisionRead5 | null>(null);
  const [savedReferences, setSavedReferences] = useState<FrozenConfigurationRead7[]>([]);
  const [reference, setReference] = useState<FrozenConfigurationRead7 | null>(null);
  const [rows, setRows] = useState<Record<string, SamplingRow>>({});
  const prepared = useRef<{
    signature: string;
    command: ConfigurationCommit6;
    saved?: FrozenConfigurationRead7;
  } | null>(null);
  const [localName, setName] = useState(current?.content.name ?? '');
  const name = creation?.name ?? localName;
  const [localDescription, setDescription] = useState(current?.content.description ?? '');
  const description = creation?.description ?? localDescription;
  const [submitting, setSubmitting] = useState(false);
  const [training, setTraining] = useState(String(group?.training_count ?? 17));
  const [method, setMethod] = useState<'boundary_latin_hypercube' | 'latin_hypercube'>(
    design?.method ?? 'boundary_latin_hypercube',
  );
  const [validation, setValidation] = useState(
    String(group ? ('validation_count' in group ? group.validation_count : group.check_count) : 8),
  );
  const [seed, setSeed] = useState(String(design?.seed ?? 17));
  const [operation, setOperation] = useState<CalculationSampleOperationRead4 | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [done, setDone] = useState(0);
  const read = useStudyRead(api, study);
  const poll = usePoll();
  function open() {
    if (model) return;
    setError(null);
    if (!scope.model || !scope.revision) {
      setError(new Error('Choose a saved model version.'));
      return;
    }
    void read(
      async (signal) => {
        const references = design
          ? await Promise.all(
              design.groups.map((g) =>
                api.configuration(study, g.reference_configuration_revision_id, signal),
              ),
            )
          : [];
        const saved = references[0] ?? null;
        const snapshot =
          saved?.model_snapshot ??
          (await api.revision(study, scope.model!, scope.revision!, signal));
        if (snapshot.model_id !== scope.model || snapshot.model_revision_id !== scope.revision)
          throw new Error('The sampling inputs do not belong to the selected model version.');
        return { saved, snapshot, references };
      },
      ({ saved, snapshot, references }) => {
        setSavedReferences(references);
        setReference(saved);
        setRows(samplingRows(snapshot, saved, group?.dimensions));
        setModel(snapshot);
      },
      setError,
    );
  }
  useEffect(() => {
    if (creation?.active && creation.activation) open();
  }, [creation?.activation, creation?.active]);
  const inputs = model
    ? modelPorts(model).filter(
        (p) =>
          p.direction === 'input' &&
          !model.connections.some((c) => refKey(c.target_ref) === refKey(p.target)),
      )
    : [];
  const running =
    operation !== null && !['complete', 'failed', 'uncertain'].includes(operation.state);
  useEffect(() => {
    creation?.onBusy(submitting || running);
  }, [submitting, running]);
  function update(key: string, change: Partial<SamplingRow>) {
    setRows((previous) => ({ ...previous, [key]: { ...previous[key], ...change } }));
  }
  async function submit() {
    if (creation?.readOnly) return;
    setError(null);
    if (!model) return;
    setSubmitting(true);
    try {
      if (design && design.groups.length !== 1)
        throw new Error(
          'This analysis has several sampling groups. Revise it through the agent tools.',
        );
      const plan = estimatePlan(
        estimatesEnabled,
        estimateRows,
        modelPorts(model).filter((p) => p.direction === 'output'),
      );
      const declaration = samplingDeclaration(model, rows, reference, design);
      const whole = (text: string) => (/^\d+$/.test(text.trim()) ? Number(text) : NaN);
      const counts = [whole(training), whole(validation), whole(seed)];
      if (
        counts.some((n) => !Number.isSafeInteger(n)) ||
        counts[0] < 3 ||
        counts[0] > 64 ||
        counts[1] < 2 ||
        counts[1] > 64 ||
        counts[2] > 4294967295
      )
        throw new Error(
          'Use 3–64 training points, 2–64 validation points, and a seed from 0 to 4294967295.',
        );
      const axes = new Set(
        declaration.dimensions.map((d) =>
          d.covary_group === null ? 'input:' + refKey(d.target) : 'group:' + d.covary_group,
        ),
      );
      if (method === 'boundary_latin_hypercube' && counts[0] <= 2 ** axes.size)
        throw new Error(
          'Include every joint boundary corner plus at least one interior training point.',
        );
      let referenceId = declaration.reuseReference
        ? reference!.configuration.configuration_revision_id
        : null;
      if (!referenceId) {
        const signature = JSON.stringify({ name, inputs: declaration.inputs });
        if (prepared.current?.signature !== signature) {
          const owner = await api.study(study);
          const prior = reference?.configuration;
          if (prior && prior.schema_version !== '6')
            throw new Error('Create a new analysis to sample this older configuration format.');
          const candidate: ConfigurationRequest6 = {
            schema_version: '6',
            study_id: study,
            model_id: model.model_id,
            model_revision_id: model.model_revision_id,
            name,
            inputs: declaration.inputs,
            numerical: reference?.configuration.numerical ?? {
              mode: 'deterministic',
              initialization: [],
              solvers: [],
              derivatives: { method: 'none', form: null, check: null },
              design_variables: [],
              objectives: [],
              constraints: [],
              optimizer: null,
              uncertainty: null,
            },
            context_source: { kind: 'current_study', expected_study_revision: owner.revision },
            notes: prior?.context_snapshot.notes ?? [],
            ...(prior
              ? {
                  context_override: {
                    schema_version: '1' as const,
                    description: prior.context_snapshot.description,
                    boundary: prior.context_snapshot.boundary,
                  },
                }
              : {}),
            derivation: null,
            assumptions: prior?.assumptions ?? [],
            general_context_evidence_version_ids: prior?.general_context_evidence_version_ids ?? [],
          };
          const proof = await api.previewConfiguration6(candidate);
          if (!proof.compatibility.compatible)
            throw new Error(proof.compatibility.diagnostics.map((d) => d.message).join('\n'));
          prepared.current = {
            signature,
            command: {
              command_id: crypto.randomUUID(),
              expected_revision: null,
              configuration_id: null,
              configuration: candidate,
              expected_preview_digest: proof.candidate_digest,
            },
          };
        }
        // The exact command is retained across a lost acknowledgement; the API's normal
        // command recovery must settle it before any further mutation is allowed.
        const preparation = prepared.current!;
        preparation.saved ??= await api.commitConfiguration6(preparation.command);
        referenceId = preparation.saved.configuration.configuration_revision_id;
      }
      const accepted = await api.sampleCalculation(study, {
        command_id: crypto.randomUUID(),
        calculation_id: current?.calculation_id ?? null,
        expected_version_id: current?.calculation_version_id ?? null,
        name,
        description,
        ...(method === 'latin_hypercube'
          ? { method: 'latin_hypercube' as const }
          : { method: 'boundary_latin_hypercube' as const }),
        seed: counts[2],
        groups: [
          {
            reference_configuration_revision_id: referenceId,
            dimensions: declaration.dimensions,
            training_count: counts[0],
            validation_count: counts[1],
          },
        ],
        rationale: declaration.rationale,
        estimate_plan: plan,
      });
      setOperation(accepted);
      poll(
        () => api.calculationSample(study, accepted.operation_id),
        (value) => ['complete', 'failed', 'uncertain'].includes(value.state),
        (value) => {
          setOperation(value);
          if (value.state === 'complete' && value.calculation_version_id) {
            setDone((n) => n + 1);
            onSaved(value.calculation_version_id);
          }
        },
        setError,
      );
    } catch (e) {
      setError(e);
    } finally {
      setSubmitting(false);
    }
  }
  if (creation?.readOnly && design)
    return (
      <div className="hf-form-stack">
        {!model && error == null && <p role="status">Loading saved settings…</p>}
        {error != null && <p role="alert">{message(error)}</p>}
        {model &&
          design.groups.map((g, i) => (
            <Panel
              key={i}
              title={design.groups.length > 1 ? `Inputs · group ${i + 1}` : 'Inputs'}
              label="Saved sampling inputs"
              headingLevel={3}
              bodyClassName="hf-flow"
              tone="sunken"
              className="hf-panel--compact"
            >
              <DataTable
                regionLabel="Saved input settings"
                columns={[
                  { key: 'input', label: 'Input' },
                  { key: 'value', label: 'Value or range' },
                ]}
                rows={inputs.map((p) => {
                  const range = g.dimensions.find((d) => refKey(d.target) === refKey(p.target));
                  const fixed = savedReferences[i]?.configuration.inputs.find(
                    (v) => refKey(v.target) === refKey(p.target),
                  );
                  return {
                    input: p.name,
                    value: range
                      ? `${formatNumber(range.lower)}–${formatNumber(range.upper)} ${unitLabel(range.units)}` +
                        (range.step !== null ? ` · step ${formatNumber(range.step)}` : '')
                      : fixed
                        ? `${formatNumber(fixed.value)} ${unitLabel(fixed.units)}`
                        : 'unassigned',
                  };
                })}
              />
            </Panel>
          ))}
        <Panel
          title="Sampling settings"
          label="Saved sampling settings"
          headingLevel={3}
          tone="sunken"
          className="hf-panel--compact"
          bodyClassName="hf-flow"
        >
          <SavedField label="Sampling method">
            {design.method === 'boundary_latin_hypercube'
              ? 'Joint boundaries and interior'
              : 'Interior only'}
          </SavedField>
          {design.groups.map((g, i) => (
            <div className="hf-flow" key={i}>
              {design.groups.length > 1 && <h4>Group {i + 1}</h4>}
              <MetricGrid
                label={`Sampling counts · group ${i + 1}`}
                items={[
                  { label: 'Training points', value: g.training_count },
                  {
                    label: 'Validation pool',
                    value: 'validation_count' in g ? g.validation_count : g.check_count,
                  },
                  { label: 'Seed', value: design.seed },
                ]}
              />
            </div>
          ))}
        </Panel>
        {model && (
          <AnalysisEstimateSettings
            readOnly
            enabled={estimatesEnabled}
            onEnabled={setEstimatesEnabled}
            choices={estimateRows}
            onChoices={setEstimateRows}
            outputs={modelPorts(model)
              .filter((p) => p.direction === 'output')
              .map((p) => ({ ...p, units: resolvedUnit(p.units) ?? '' }))}
          />
        )}
      </div>
    );
  const form = (
    <form
      id={formId}
      className="hf-form-stack"
      onSubmit={(event) => {
        event.preventDefault();
        void submit();
      }}
    >
      {!creation && (
        <>
          <label>
            Name
            <TextInput
              aria-label="Sampled analysis name"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </label>
          <FormField label="Description" optional>
            <TextArea
              aria-label="Sampled analysis description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </FormField>
        </>
      )}
      <fieldset className="hf-form-section" disabled={running || submitting}>
        {!model && error == null && <p role="status">Loading model inputs…</p>}
        {model && (
          <div className="hf-form-stack" role="region" aria-label="Sampling inputs">
            {inputs.map((input) => {
              const key = refKey(input.target);
              const row = rows[key];
              const label = input.label;
              return (
                <Panel
                  key={key}
                  tone="sunken"
                  className="hf-panel--compact"
                  label={label}
                  headingLevel={3}
                  title={
                    <>
                      {inputs.filter((p) => p.name === input.name).length > 1 ? label : input.name}
                      {' · '}
                      {unitLabel(input.units)}
                    </>
                  }
                  bodyClassName={
                    row.mode === 'fixed' ? 'hf-form-grid hf-form-grid--pair' : 'hf-form-stack'
                  }
                >
                  <FormField label="Use as">
                    <Select
                      aria-label={label + ' sampling mode'}
                      value={row.mode}
                      onChange={(e) => update(key, { mode: e.target.value as SamplingRow['mode'] })}
                    >
                      <option value="fixed">Fixed value</option>
                      <option value="range">Range</option>
                    </Select>
                  </FormField>
                  {row.mode === 'fixed' ? (
                    <FormField label="Value">
                      <TextInput
                        aria-label={label + ' value'}
                        type="number"
                        step="any"
                        value={row.value}
                        onChange={(e) => update(key, { value: e.target.value })}
                      />
                    </FormField>
                  ) : (
                    <div className="hf-form-grid hf-form-grid--triple">
                      {(['lower', 'upper', 'step'] as const).map((field) => {
                        const title =
                          field === 'lower' ? 'Minimum' : field === 'upper' ? 'Maximum' : 'Step';
                        return (
                          <FormField key={field} label={title} optional={field === 'step'}>
                            <TextInput
                              aria-label={label + ' ' + title.toLowerCase()}
                              type="number"
                              step="any"
                              value={row[field]}
                              onChange={(e) => update(key, { [field]: e.target.value })}
                            />
                          </FormField>
                        );
                      })}
                    </div>
                  )}
                </Panel>
              );
            })}
          </div>
        )}
        <Panel
          help={<SectionHelp topic="sampling" />}
          title="Sampling settings"
          label="Sampling settings"
          className="hf-panel--compact"
          tone="sunken"
          headingLevel={3}
          bodyClassName="hf-form-stack"
        >
          <FormField label="Sampling method">
            <Select
              aria-label="Sampling method"
              value={method}
              onChange={(e) => setMethod(e.target.value as typeof method)}
            >
              <option value="boundary_latin_hypercube">Joint boundaries and interior</option>
              <option value="latin_hypercube">Interior only</option>
            </Select>
          </FormField>
          <div className="hf-form-grid hf-form-grid--triple">
            <FormField label="Training points">
              <TextInput
                aria-label="Training points"
                type="number"
                step="1"
                value={training}
                onChange={(e) => setTraining(e.target.value)}
              />
            </FormField>
            <FormField label="Validation points">
              <TextInput
                aria-label="Validation points"
                type="number"
                step="1"
                value={validation}
                onChange={(e) => setValidation(e.target.value)}
              />
            </FormField>
            <FormField label="Seed">
              <TextInput
                aria-label="Seed"
                type="number"
                step="1"
                value={seed}
                onChange={(e) => setSeed(e.target.value)}
              />
            </FormField>
          </div>
        </Panel>
        {model && (
          <AnalysisEstimateSettings
            enabled={estimatesEnabled}
            onEnabled={setEstimatesEnabled}
            choices={estimateRows}
            onChoices={setEstimateRows}
            outputs={modelPorts(model)
              .filter((p) => p.direction === 'output')
              .map((p) => ({ ...p, units: resolvedUnit(p.units) ?? '' }))}
          />
        )}
      </fieldset>
      {operation &&
        (running ? (
          <Progress label={sampleProgress[operation.state]} />
        ) : operation.state !== 'complete' ? (
          <p role="alert">
            <StatusTag tone={operation.state === 'failed' ? 'alarm' : 'warning'}>
              {sampleProgress[operation.state]}
            </StatusTag>{' '}
            {operation.reason}
          </p>
        ) : null)}
      {error != null && <p role="alert">{message(error)}</p>}
      {!creation?.readOnly && (
        <DialogActions
          active={!creation || creation.active}
          primary={
            <Button
              type="submit"
              form={formId}
              variant="primary"
              disabled={!model || running || submitting || !name.trim()}
            >
              Save analysis
            </Button>
          }
        />
      )}
    </form>
  );
  if (creation) return form;
  return (
    <ActionDialog
      title={current ? 'Analysis settings' : 'New analysis'}
      label={current ? 'Analysis settings' : 'New analysis'}
      disabled={!scope.revision}
      completionKey={done}
      closeLabel="Cancel"
      onOpen={open}
    >
      {form}
    </ActionDialog>
  );
}

const estimateStates: Record<CalculationEstimateRead2['state'], [Tone, string]> = {
  pending: ['running', 'Queued'],
  building: ['running', 'Fitting'],
  ready: ['ok', 'Validation passed'],
  assessed: ['advisory', 'No output passed validation'],
  failed: ['alarm', 'Failed'],
};

/** Read-only estimates for the saved version. Estimates are fitted
 * to this exact version and its latest recorded runs; their values are never calculated results. */
export function EstimatesPanel({
  api,
  study,
  version,
  outputs,
  refresh = 0,
}: {
  api: HyprnMvpApi;
  study: string;
  version: CalculationVersionRead4;
  outputs: { target: PortRef; label: string; units: string }[];
  refresh?: number;
}) {
  const [error, setError] = useState<unknown>(null);
  const sampled = version.content.design.kind === 'sampled';
  const collection = useCollectionRead<CalculationEstimateRead2, string>({
    api,
    study,
    scope: version.calculation_version_id,
    load: async (cursor, signal) => {
      const page = await api.calculationEstimates(
        study,
        version.calculation_version_id,
        cursor,
        signal,
      );
      return { rows: page.items, next: page.next_cursor };
    },
    identity: (row) => row.estimate_id,
    onUnavailable: () => setError(new Error('Surrogate records are no longer available.')),
  });
  useEffect(() => {
    if (refresh) void collection.refresh();
  }, [refresh]);
  const label = (target: PortRef) =>
    outputs.find((o) => refKey(o.target) === refKey(target))?.label ?? 'Output';
  const shown = collection.rows;
  if (!sampled) return null;
  return (
    <Panel
      label="Surrogate"
      title="Surrogate validation"
      help={<SectionHelp topic="surrogate" />}
      headingLevel={3}
      bodyClassName="hf-flow"
    >
      {(collection.state.status !== 'ready' ||
        collection.state.more ||
        collection.state.error ||
        !shown.length) && (
        <CollectionStatus
          entity={{ singular: 'surrogate', plural: 'surrogates' }}
          state={
            collection.state.status === 'ready'
              ? { ...collection.state, count: shown.length }
              : collection.state
          }
          onMore={() => void collection.more()}
          onRetry={() => void collection.retry()}
        />
      )}
      {error != null && <p role="alert">{message(error)}</p>}
      {shown.map((estimate, estimateIndex) => {
        const [tone, word] = estimateStates[estimate.state];
        const training = estimate.samples.filter((s) => s.partition === 'training');
        const validation = estimate.samples.filter((s) => s.partition !== 'training');
        const selections = new Set(validation.map((s) => s.group)).size;
        const assessedOutputs = estimate.groups.flatMap((g) => g.outputs);
        const passed = assessedOutputs.filter(
          (o) => o.reason === null && o.metrics?.target_met,
        ).length;
        const assessmentRows = estimate.groups.flatMap((group) =>
          estimate.request.tolerances.map((t) => {
            const output = group.outputs.find((o) => refKey(o.target) === refKey(t.target));
            return {
              name:
                (estimate.groups.length > 1 ? `Group ${group.group + 1} · ` : '') + label(t.target),
              units:
                output?.units ?? outputs.find((o) => refKey(o.target) === refKey(t.target))?.units,
              method: output?.method,
              reason: output?.reason,
              metrics: output?.metrics,
              tolerance: t,
            };
          }),
        );
        return (
          <div key={estimate.estimate_id} className="hf-flow">
            <p className="hf-result-cell">
              {shown.length > 1 && <strong>Surrogate {estimateIndex + 1}</strong>}
              <StatusTag tone={tone}>
                {estimate.state === 'ready' || estimate.state === 'assessed'
                  ? `${passed}/${estimate.request.tolerances.length * estimate.total_groups} outputs passed`
                  : word}
              </StatusTag>
            </p>
            <MetricGrid
              label="Sample use"
              layout="inline"
              items={[
                { label: 'Training points', value: training.length },
                { label: 'Method selection', value: selections },
                { label: 'Validation points', value: validation.length - selections },
              ]}
            />
            {estimate.reason && <p role="status">{estimate.reason.replace(/_/g, ' ')}</p>}
            {['pending', 'building'].includes(estimate.state) && (
              <Progress
                label="Fitting the surrogate"
                count={{ completed: estimate.completed_groups, total: estimate.total_groups }}
                message={`${estimate.completed_groups} of ${estimate.total_groups} groups fitted`}
              />
            )}
            {assessmentRows.length > 0 && <SurrogateValidation rows={assessmentRows} />}
          </div>
        );
      })}
    </Panel>
  );
}
