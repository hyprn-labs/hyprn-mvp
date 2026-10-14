import type { ApproachResolution } from './api';
import type { ApproachContent } from './api';
import { runLabel } from './recordLabels';
import {
  ApproachStepContext,
  ApproachCaseContext,
  useApproachEditGuard,
} from './ApproachAssumptions';
import { useEffect, useId, useRef, useState } from 'react';
import {
  Button,
  Checkbox,
  Disclosure,
  DialogFrame,
  Panel,
  Select,
  StatusTag,
  TextArea,
  TextInput,
  ActionDialog,
} from './design';
import { HyprnMvpApi, message } from './api';
import { MethodExplanation, ComponentSourceContent, instanceLabel } from './SelectionInspector';
import { ModelView } from './ModelView';
import { methodLinks } from './modelMethods';
import { ConfigurationRecord, ConfigurationRecordDetails } from './ConfigurationRecord';
import { ApproachReferencePicker, modelLabel } from './ApproachReferences';
import type {
  ApproachClosureRead3,
  ApproachBasisRef1,
  ApproachCase1,
  ApproachElementRef1,
  ApproachModelBinding1,
  ApproachStep1,
  ModelRevisionRead4,
  FrozenConfigurationRead7,
  RunHistoryItem,
} from './contract';
import { referencedInstances, referencedQuantities } from './quantityDefinitions';
import { CaseNavigation, type Selection } from './workspaceModel';

type EditProps = {
  content: ApproachContent;
  onChange?: (content: ApproachContent) => void;
  disabled?: boolean;
};
function BasisRecord({
  reference,
  resolved,
  closure,
}: {
  reference: ApproachBasisRef1;
  resolved?: ApproachResolution;
  closure?: ApproachClosureRead3;
}) {
  const run =
    reference.kind === 'run'
      ? resolved?.run_contexts.find((r) => r.run_id === reference.run_id)
      : undefined;
  const configuration = resolved?.configurations.find(
    (c) =>
      c.configuration_revision_id ===
      (reference.kind === 'configuration'
        ? reference.configuration_revision_id
        : run?.configuration_revision_id),
  );
  const model =
    resolved?.models.find((m) => m.model_revision_id === configuration?.model_revision_id) ?? null;
  return configuration ? (
    <>
      <div className="section-header">
        <h3>{configuration.name}</h3>
        <ConfigurationRecordDetails configuration={configuration} />
      </div>
      <p className="context-line">
        Model version {configuration.model_revision_id.slice(0, 8)} · read-only
      </p>
      {run && (
        <section>
          <h3>Run</h3>
          <StatusTag tone={run.results?.execution.state === 'finished' ? 'inert' : 'advisory'}>
            {run.results?.execution.state === 'finished'
              ? 'Finished'
              : run.results?.execution.state === 'failed'
                ? 'Failed'
                : 'Results unavailable'}
          </StatusTag>
          {run.errors.length > 0 && (
            <p>
              Execution evidence is incomplete. This run may inform the explanation; it supplies no
              verified numerical result here.
            </p>
          )}
        </section>
      )}
      <ConfigurationRecord
        approachClosure={closure}
        configuration={configuration}
        model={model}
        {...(run ? { results: run.results } : {})}
      />
    </>
  ) : (
    <p>
      Use Load linked records to inspect this earlier record. For unsaved edits, use Review approach
      changes.
    </p>
  );
}
const emptyStep = (): ApproachStep1 => ({
  step_id: crypto.randomUUID(),
  title: '',
  purpose: '',
  rationale: '',
  remaining_work: '',
  intent: { transformation: '', inputs: '', outputs: '', depends_on_step_ids: [] },
  implementation_state: 'proposed',
  implementation_refs: [],
  assumption_refs: [],
  evidence_links: [],
});
function bindingDependants(content: ApproachContent, steps: ApproachStep1[]) {
  const used = new Set(steps.flatMap((s) => s.implementation_refs.map((r) => r.binding_id)));
  if (content.cases.some((c) => c.binding_id && !used.has(c.binding_id)))
    return (
      'An intended case uses this model version. Change that case ' +
      'before removing its last implementation reference.'
    );
  if (
    steps.some((s) => s.assumption_refs.some((r) => r.kind === 'model' && !used.has(r.binding_id)))
  )
    return (
      'A method step references an assumption from this model version. ' +
      'Resolve that assumption reference before removing its last implementation reference.'
    );
  return '';
}
function swap<T>(items: T[], from: number, to: number) {
  const next = [...items];
  [next[from], next[to]] = [next[to], next[from]];
  return next;
}
function useLocalDialog(content: ApproachContent, onChange?: EditProps['onChange']) {
  const dialog = useRef<HTMLDialogElement>(null),
    before = useRef<ApproachContent | null>(null),
    invoker = useRef<HTMLElement | null>(null),
    key = useRef(crypto.randomUUID());
  const [opened, setOpened] = useState(false);
  useApproachEditGuard(
    key.current,
    opened && JSON.stringify(content) !== JSON.stringify(before.current),
  );
  function show() {
    setOpened(true);
    before.current = structuredClone(content);
    invoker.current = document.activeElement as HTMLElement;
    dialog.current?.showModal();
  }
  function close() {
    setOpened(false);
    dialog.current?.close();
    invoker.current?.focus();
  }
  function cancel() {
    if (before.current) onChange?.(before.current);
    close();
  }
  return { dialog, show, close, cancel };
}
function matches(ref: ApproachElementRef1, selection: Selection) {
  if (ref.kind === 'model') return selection.kind !== 'none';
  if (ref.kind === 'instance')
    return 'instance_id' in selection && selection.instance_id === ref.instance_id;
  if (ref.kind === 'port')
    return (
      selection.kind === 'variable' &&
      selection.instance_id === ref.instance_id &&
      selection.port_id === ref.port_id
    );
  return selection.kind === 'connection'
    ? selection.connection_id === ref.connection_id
    : selection.kind === 'connection_group' && selection.connection_ids.includes(ref.connection_id);
}

type MethodView = { step: string; detail: string; binding: string; focus: boolean };
/** Local reading state per exact approach version or current draft; never scientific data. */
const methodViews = new Map<string, MethodView>();
/** Forget reading positions on session end (all) or confirmed access loss (one study's keys). */
/** Open one exact step on the next read of this version (the model view's "Open step n"). */
export function rememberMethodStep(viewKey: string, stepId: string) {
  methodViews.set(viewKey, { step: stepId, detail: 'explanation', binding: '', focus: true });
}
export function forgetMethodViews(studyId?: string) {
  if (studyId === undefined) methodViews.clear();
  else
    for (const key of [...methodViews.keys()])
      if (key.startsWith(studyId + '/')) methodViews.delete(key);
}
const stepState = (step: ApproachStep1, count: number) =>
  step.implementation_state === 'proposed'
    ? 'Proposed · no model linked'
    : (step.implementation_state === 'partial' ? 'Partially linked' : 'Linked') +
      ' · ' +
      count +
      ' model ' +
      (count === 1 ? 'version' : 'versions');
const plural = (count: number, one: string, many = one + 's') =>
  count + ' ' + (count === 1 ? one : many);

export function ApproachMethod({
  api,
  studyId,
  content,
  resolved,
  onChange,
  disabled = false,
  viewKey,
  onOpenModel,
  requestedStep,
  version = null,
}: {
  version?: { id: string; number: number } | null;
  api?: HyprnMvpApi;
  studyId?: string;
  resolved?: ApproachResolution;
  viewKey?: string;
  onOpenModel?: (id: string) => void;
  requestedStep?: { id: string; token: number };
} & EditProps) {
  const remembered = useRef(viewKey ? methodViews.get(viewKey) : undefined).current;
  const [models, setModels] = useState<ModelRevisionRead4[]>(resolved?.models ?? []),
    [loadError, setLoadError] = useState(''),
    [bindingId, setBindingId] = useState(remembered?.binding ?? ''),
    [selectedStep, setSelectedStep] = useState(remembered?.step ?? content.steps[0]?.step_id ?? ''),
    [selection, setSelection] = useState<Selection>({ kind: 'none' }),
    [editing, setEditing] = useState(''),
    [error, setError] = useState('');
  const [detail, setDetail] = useState(
    remembered?.detail === 'assumptions' ? 'assumptions' : 'explanation',
  );
  const form = useLocalDialog(content, onChange),
    generation = useRef(0),
    step = content.steps.find((s) => s.step_id === editing),
    tabsId = useId(),
    map = useRef<HTMLOListElement>(null);
  const bindingKey = content.model_bindings.map((b) => b.model_revision_id).join('/');
  useEffect(() => {
    const token = ++generation.current,
      actor = api?.actor;
    setLoadError('');
    setModels(resolved?.models ?? []);
    if (!api || !studyId) return;
    const missing = content.model_bindings.filter(
      (b) => !resolved?.models.some((m) => m.model_revision_id === b.model_revision_id),
    );
    if (!missing.length) return;
    void Promise.all(missing.map((b) => api.revision(studyId, b.model_id, b.model_revision_id)))
      .then((found) => {
        if (token === generation.current && actor === api.actor)
          setModels([...(resolved?.models ?? []), ...found]);
      })
      .catch((e) => {
        if (token === generation.current && actor === api.actor) setLoadError(message(e));
      });
    return () => {
      generation.current++;
    };
  }, [api, studyId, bindingKey, resolved]);
  useEffect(() => {
    if (viewKey)
      methodViews.set(viewKey, { step: selectedStep, detail, binding: bindingId, focus: false });
  }, [viewKey, selectedStep, detail, bindingId]);
  // Results may ask to show one exact recorded step; never a positional guess.
  useEffect(() => {
    if (!requestedStep || !content.steps.some((s) => s.step_id === requestedStep.id)) return;
    setSelectedStep(requestedStep.id);
    setDetail('explanation');
    const frame = requestAnimationFrame(() =>
      map.current?.querySelector<HTMLElement>('details[open] > summary')?.focus(),
    );
    return () => cancelAnimationFrame(frame);
  }, [requestedStep?.token]);
  // Returning from the model owner restores the exact step, tab and focus.
  useEffect(() => {
    if (remembered?.focus)
      map.current?.querySelector<HTMLElement>('details[open] > summary')?.focus();
  }, [remembered]);
  const active = content.steps.find((s) => s.step_id === selectedStep);
  const bindings = content.model_bindings.filter((b) =>
    active?.implementation_refs.some((r) => r.binding_id === b.binding_id),
  );
  // Several exact bindings require an explicit choice; never the first match.
  const binding =
    bindings.find((b) => b.binding_id === bindingId) ??
    (bindings.length === 1 ? bindings[0] : undefined);
  const model = models.find(
    (m) => m.model_id === binding?.model_id && m.model_revision_id === binding?.model_revision_id,
  );
  const refs =
    active?.implementation_refs.filter((r) => r.binding_id === binding?.binding_id) ?? [];
  const quantities = model ? referencedQuantities(model, refs) : [];
  const nodeIds = new Set<string>(),
    linkIds = new Set<string>(),
    ports = new Set<string>();
  for (const ref of refs) {
    if (ref.kind === 'model' && model) {
      model.instances.forEach((i) => nodeIds.add(i.instance_id));
      model.connections.forEach((c) => linkIds.add(c.connection_id));
    }
    if ('instance_id' in ref) nodeIds.add(ref.instance_id);
    if (ref.kind === 'port') ports.add(ref.instance_id + '/' + ref.port_id);
    if (ref.kind === 'connection') linkIds.add(ref.connection_id);
  }
  const matching = content.steps.filter((s) =>
    s.implementation_refs.some(
      (r) => r.binding_id === binding?.binding_id && matches(r, selection),
    ),
  );
  function selectStep(id: string) {
    setSelectedStep(id);
    setSelection({ kind: 'none' });
    setBindingId('');
    setDetail('explanation');
  }
  // The canonical model view, read-only: the step's references are highlighted and scope
  // the quantities table; each component explains itself through this version's linked steps.
  const [openedStep, setOpenedStep] = useState(0),
    viewId = useId();
  const modelView = (prefix: string) =>
    model && (
      <ModelView
        idPrefix={prefix}
        snapshot={model}
        selection={selection}
        onSelect={setSelection}
        evidence={resolved?.evidence ?? []}
        focus={{ instances: nodeIds, ports, links: linkIds }}
        methods={{ kind: 'loaded', links: methodLinks(content, version, model) }}
        onOpenStep={(link) => {
          setOpenedStep((n) => n + 1);
          selectStep(link.stepId);
        }}
      />
    );
  const bindingLabel = (b: ApproachModelBinding1) => {
    const found = models.find(
      (m) => m.model_id === b.model_id && m.model_revision_id === b.model_revision_id,
    );
    return found ? modelLabel(found) : 'Unavailable version ' + b.model_revision_id.slice(0, 8);
  };
  const modelControls = bindings.length > 1 && (
    <div className="method-binding-choice">
      <label>
        Model version
        <Select
          aria-label="Approach model version"
          value={binding?.binding_id ?? ''}
          onChange={(e) => {
            setBindingId(e.target.value);
            setSelection({ kind: 'none' });
          }}
        >
          <option value="">Choose a model version</option>
          {bindings.map((b) => (
            <option key={b.binding_id} value={b.binding_id}>
              {bindingLabel(b)}
            </option>
          ))}
        </Select>
      </label>
      {!binding && (
        <p className="context-line">
          This step references {bindings.length} model versions. Choose one to open it.
        </p>
      )}
    </div>
  );
  function update(value: ApproachStep1) {
    onChange?.({
      ...content,
      steps: content.steps.map((s) => (s.step_id === value.step_id ? value : s)),
    });
  }
  function begin(value?: ApproachStep1) {
    form.show();
    setError('');
    const next = value ?? emptyStep();
    setEditing(next.step_id);
    if (!value) onChange?.({ ...content, steps: [...content.steps, next] });
    setTimeout(() => form.dialog.current?.querySelector<HTMLInputElement>('input')?.focus(), 0);
  }
  function apply() {
    if (!step?.title.trim()) {
      setError('Give this method step a title.');
      return;
    }
    if (
      (step.implementation_state === 'proposed' && step.implementation_refs.length) ||
      (step.implementation_state !== 'proposed' && !step.implementation_refs.length)
    ) {
      setError(
        'Proposed steps have no implementation references. Partially ' +
          'linked and linked steps require model references.',
      );
      return;
    }
    if (
      (step.implementation_state === 'partial' && !step.remaining_work.trim()) ||
      (step.implementation_state === 'linked' && step.remaining_work.trim())
    ) {
      setError(
        'Partially linked steps describe remaining work. A linked step ' +
          'has no remaining implementation work.',
      );
      return;
    }
    form.close();
    setEditing('');
    selectStep(step.step_id);
  }
  function remove(id: string) {
    const steps = content.steps.filter((s) => s.step_id !== id);
    if (steps.some((s) => s.intent.depends_on_step_ids.includes(id))) {
      setError('Another step depends on this step. Edit that explanation before removing it.');
      return;
    }
    const used = new Set(steps.flatMap((s) => s.implementation_refs.map((r) => r.binding_id)));
    const dependency = bindingDependants(content, steps);
    if (dependency) {
      setError(dependency);
      return;
    }
    onChange?.({
      ...content,
      steps,
      model_bindings: content.model_bindings.filter((b) => used.has(b.binding_id)),
    });
    setSelectedStep('');
  }
  function openOwner(id: string) {
    if (viewKey)
      methodViews.set(viewKey, {
        step: active?.step_id ?? '',
        detail,
        binding: bindingId,
        focus: true,
      });
    onOpenModel?.(id);
  }
  // One line instead of quantity cards: the step's exact references, counted by direction.
  const count = (direction: 'input' | 'output' | 'residual') =>
    quantities.filter((q) => q.port.direction === direction).length;
  const implemented = model
    ? [
        'Implemented in Model version ' + model.model_revision_id.slice(0, 8),
        plural(count('input'), 'input'),
        plural(count('output'), 'output'),
        ...(count('residual') ? [plural(count('residual'), 'residual')] : []),
      ].join(' · ')
    : '';
  return (
    <>
      {loadError && <p role="alert">This model version can't be loaded. {loadError}</p>}
      {error && !step && <p role="alert">{error}</p>}
      <section className="approach-methods" aria-label="Methods">
        {onChange && (
          <div className="section-actions">
            <Button disabled={disabled || content.steps.length >= 64} onClick={() => begin()}>
              Add method step
            </Button>
          </div>
        )}
        {!content.steps.length && <p>No method steps</p>}
        <ol ref={map} className="approach-method-rows">
          {content.steps.map((item, index) => (
            <li key={item.step_id}>
              <Disclosure className="approach-method-row" open={active?.step_id === item.step_id}>
                <summary
                  className="method-row-toggle"
                  role="button"
                  aria-label={'Select step ' + (index + 1)}
                  aria-expanded={active?.step_id === item.step_id}
                  onClick={(event) => {
                    event.preventDefault();
                    selectStep(active?.step_id === item.step_id ? '' : item.step_id);
                  }}
                >
                  <strong>{item.title || 'Untitled step'}</strong>
                  <StatusTag tone="inert">
                    {stepState(
                      item,
                      new Set(item.implementation_refs.map((r) => r.binding_id)).size,
                    )}
                  </StatusTag>
                </summary>
                {active?.step_id === item.step_id && (
                  <div className="method-detail" role="region" aria-label="Selected method step">
                    {!!item.intent.depends_on_step_ids.length && (
                      <p className="context-line">
                        Builds on{' '}
                        {item.intent.depends_on_step_ids
                          .map(
                            (id) =>
                              content.steps.find((s) => s.step_id === id)?.title ||
                              'an unavailable step',
                          )
                          .join(', ')}
                      </p>
                    )}
                    {active ? (
                      <>
                        {modelControls}
                        <div id={tabsId + '-explanation'} className="method-explanation">
                          <MethodExplanation
                            step={active}
                            source={
                              model &&
                              referencedInstances(model, refs)
                                .filter(
                                  (instance) => instance.instance_id !== model.root_instance_id,
                                )
                                .map((instance) => (
                                  <div key={instance.instance_id}>
                                    <h4>{instanceLabel(model, instance.instance_id)}</h4>
                                    <ComponentSourceContent
                                      snapshot={model}
                                      instanceId={instance.instance_id}
                                    />
                                  </div>
                                ))
                            }
                          />
                          {active.implementation_state === 'proposed' ? (
                            <>
                              <p>Proposed work — no model linked. No calculation is implied.</p>
                              <div className="method-intent-groups">
                                <section className="method-intent" aria-label="Proposed inputs">
                                  <h3>Proposed inputs</h3>
                                  <p className="context-copy">
                                    {active.intent.inputs || 'Inputs not described'}
                                  </p>
                                </section>
                                <section className="method-intent" aria-label="Proposed outputs">
                                  <h3>Proposed outputs</h3>
                                  <p className="context-copy">
                                    {active.intent.outputs || 'Outputs not described'}
                                  </p>
                                </section>
                              </div>
                            </>
                          ) : model ? (
                            <div className="method-implemented">
                              <p>{implemented}</p>
                              {onChange && onOpenModel && (
                                <ActionDialog
                                  title="Edit definitions at their owner"
                                  label="Edit definitions in model"
                                >
                                  <p>
                                    Quantity definitions belong to the model. Editing the current
                                    model draft creates a new definition version only for the
                                    instances you select. This approach keeps model version{' '}
                                    {model.model_revision_id.slice(0, 8)} until you explicitly link
                                    a newer saved version.
                                  </p>
                                  <Button
                                    variant="primary"
                                    disabled={disabled}
                                    onClick={() => openOwner(model.model_id)}
                                  >
                                    Open current model draft
                                  </Button>
                                </ActionDialog>
                              )}
                            </div>
                          ) : binding ? (
                            <p>This model version can't be loaded.</p>
                          ) : null}
                          {active.remaining_work && (
                            <>
                              <h3>Remaining work</h3>
                              <p className="context-copy">{active.remaining_work}</p>
                            </>
                          )}
                        </div>
                        <ApproachStepContext step={active} />
                      </>
                    ) : (
                      <p>Select or add a method step.</p>
                    )}
                    <div className="section-actions method-detail-footer">
                      {model && (
                        <ActionDialog
                          variant="quiet"
                          title={'Model version ' + model.model_revision_id.slice(0, 8)}
                          label="View model details"
                          width="workspace"
                          completionKey={openedStep}
                        >
                          <p className="context-line">
                            {modelLabel(model)} · read-only · linked to this approach
                          </p>
                          {selection.kind !== 'none' && (
                            <p role="status">
                              {plural(matching.length, 'method step')}{' '}
                              {matching.length === 1 ? 'references' : 'reference'} this selection.
                            </p>
                          )}
                          {modelView(viewId + '-open-')}
                        </ActionDialog>
                      )}
                    </div>
                  </div>
                )}
              </Disclosure>
              {active?.step_id !== item.step_id && (
                <p className="context-copy method-row-purpose">
                  {item.purpose || 'Purpose not described'}
                </p>
              )}
              {onChange && (
                <div className="section-actions">
                  <Button disabled={disabled} onClick={() => begin(item)}>
                    Edit step {index + 1}
                  </Button>
                  <ActionDialog
                    title={'Step ' + (index + 1) + ' actions'}
                    label="…"
                    triggerLabel={'Step ' + (index + 1) + ' actions'}
                    disabled={disabled}
                  >
                    <div className="hf-action-list">
                      <Button
                        disabled={index === 0}
                        onClick={() =>
                          onChange({ ...content, steps: swap(content.steps, index, index - 1) })
                        }
                      >
                        Move step {index + 1} up
                      </Button>
                      <Button
                        disabled={index === content.steps.length - 1}
                        onClick={() =>
                          onChange({ ...content, steps: swap(content.steps, index, index + 1) })
                        }
                      >
                        Move step {index + 1} down
                      </Button>
                      <ActionDialog title="Remove method step" label={'Remove step ' + (index + 1)}>
                        <p>
                          Remove this explanation and its links? Referenced models and records
                          remain unchanged.
                        </p>
                        <Button variant="danger" onClick={() => remove(item.step_id)}>
                          Remove this step
                        </Button>
                      </ActionDialog>
                    </div>
                  </ActionDialog>
                </div>
              )}
            </li>
          ))}
        </ol>
      </section>
      <DialogFrame ref={form.dialog} aria-labelledby="method-step-title" onCancel={form.cancel}>
        <h2 id="method-step-title">Method step</h2>
        {step && (
          <form
            className="form-stack"
            onSubmit={(e) => {
              e.preventDefault();
              apply();
            }}
          >
            <label>
              Step title
              <TextInput
                aria-label="Step title"
                maxLength={256}
                value={step.title}
                onChange={(e) => update({ ...step, title: e.target.value })}
              />
            </label>
            {(['purpose', 'rationale'] as const).map((key) => (
              <label key={key}>
                {key === 'purpose' ? 'Purpose' : 'Why this method'}
                <TextArea
                  aria-label={key === 'purpose' ? 'Purpose' : 'Why this method'}
                  maxLength={4096}
                  value={step[key]}
                  onChange={(e) => update({ ...step, [key]: e.target.value })}
                />
              </label>
            ))}
            {(['transformation', 'inputs', 'outputs'] as const).map((key) => (
              <label key={key}>
                Intended {key}
                <TextArea
                  aria-label={'Intended ' + key}
                  maxLength={4096}
                  value={step.intent[key]}
                  onChange={(e) =>
                    update({ ...step, intent: { ...step.intent, [key]: e.target.value } })
                  }
                />
              </label>
            ))}
            <fieldset>
              <legend>Builds on these steps (explanation only)</legend>
              {content.steps
                .filter((s) => s.step_id !== step.step_id)
                .map((s) => (
                  <label key={s.step_id}>
                    <Checkbox
                      checked={step.intent.depends_on_step_ids.includes(s.step_id)}
                      onChange={(e) =>
                        update({
                          ...step,
                          intent: {
                            ...step.intent,
                            depends_on_step_ids: e.target.checked
                              ? [...step.intent.depends_on_step_ids, s.step_id]
                              : step.intent.depends_on_step_ids.filter((id) => id !== s.step_id),
                          },
                        })
                      }
                    />
                    {s.title}
                  </label>
                ))}
            </fieldset>
            <label>
              Implementation status
              <Select
                aria-label="Implementation status"
                value={step.implementation_state}
                onChange={(e) =>
                  update({
                    ...step,
                    implementation_state: e.target.value as ApproachStep1['implementation_state'],
                  })
                }
              >
                <option value="proposed">Proposed</option>
                <option value="partial">Partially linked</option>
                <option value="linked">Linked</option>
              </Select>
            </label>
            <label>
              Remaining implementation work
              <TextArea
                aria-label="Remaining implementation work"
                maxLength={4096}
                value={step.remaining_work}
                onChange={(e) => update({ ...step, remaining_work: e.target.value })}
              />
            </label>
            {api && studyId && (
              <ApproachReferencePicker
                api={api}
                studyId={studyId}
                bindings={content.model_bindings}
                refs={step.implementation_refs}
                disabled={disabled}
                onChange={(binding, refs) => {
                  const steps = content.steps.map((s) =>
                      s.step_id === step.step_id ? { ...s, implementation_refs: refs } : s,
                    ),
                    used = new Set(
                      steps.flatMap((s) => s.implementation_refs.map((r) => r.binding_id)),
                    );
                  const dependency = bindingDependants(content, steps);
                  if (dependency) {
                    setError(dependency);
                    return;
                  }
                  setError('');
                  onChange?.({
                    ...content,
                    steps,
                    model_bindings: [
                      ...content.model_bindings.filter((b) => b.binding_id !== binding.binding_id),
                      binding,
                    ].filter((b) => used.has(b.binding_id)),
                  });
                }}
              />
            )}
            {error && <p role="alert">{error}</p>}
            <div className="actions">
              <Button type="submit" variant="primary">
                Apply step
              </Button>
              <Button onClick={form.cancel}>Cancel</Button>
            </div>
          </form>
        )}
      </DialogFrame>
    </>
  );
}

export function ApproachCases({
  content,
  onChange,
  disabled = false,
  models = [],
  onCreateConfiguration,
}: {
  models?: ModelRevisionRead4[];
  onCreateConfiguration?: (caseId: string) => void;
} & EditProps) {
  const form = useLocalDialog(content, onChange),
    [editing, setEditing] = useState(''),
    [error, setError] = useState(''),
    item = content.cases.find((c) => c.case_id === editing);
  function begin(value?: ApproachCase1) {
    form.show();
    setError('');
    const next = value ?? {
      case_id: crypto.randomUUID(),
      title: '',
      question: '',
      rationale: '',
      binding_id: null,
      evidence_links: [],
    };
    setEditing(next.case_id);
    if (!value) onChange?.({ ...content, cases: [...content.cases, next] });
  }
  function update(next: ApproachCase1) {
    onChange?.({
      ...content,
      cases: content.cases.map((c) => (c.case_id === next.case_id ? next : c)),
    });
  }
  return (
    <>
      {onChange && (
        <Button disabled={disabled || content.cases.length >= 64} onClick={() => begin()}>
          Add intended case
        </Button>
      )}
      {!content.cases.length && (
        <p className="context-line">
          No intended cases yet. Inputs and criteria belong to configurations.
        </p>
      )}
      {content.cases.map((c, index) => (
        <article className="approach-case" key={c.case_id}>
          <Disclosure open={!!onChange}>
            <summary>
              <h3>{c.title || 'Untitled case'}</h3>
            </summary>
            <p className="context-copy">{c.question}</p>
            <p className="context-copy">{c.rationale}</p>
            <p className="context-line">
              {c.binding_id
                ? 'Model version ' +
                  (content.model_bindings
                    .find((binding) => binding.binding_id === c.binding_id)
                    ?.model_revision_id.slice(0, 8) ?? 'unavailable')
                : 'Proposed case · no model version selected'}
            </p>
            {onChange && (
              <div className="section-actions">
                <Button
                  aria-label={`Edit case ${index + 1}`}
                  disabled={disabled}
                  onClick={() => begin(c)}
                >
                  Edit
                </Button>
                <ActionDialog
                  title={`Case ${index + 1} actions`}
                  label={`More actions for case ${index + 1}`}
                  disabled={disabled}
                >
                  <Button
                    disabled={disabled || index === 0}
                    onClick={() =>
                      onChange({ ...content, cases: swap(content.cases, index, index - 1) })
                    }
                  >
                    Move case {index + 1} up
                  </Button>
                  <Button
                    disabled={disabled || index === content.cases.length - 1}
                    onClick={() =>
                      onChange({ ...content, cases: swap(content.cases, index, index + 1) })
                    }
                  >
                    Move case {index + 1} down
                  </Button>
                  <ActionDialog
                    title="Remove intended case"
                    label={`Remove case ${index + 1}`}
                    disabled={disabled}
                  >
                    <p>
                      Remove this intended case? Saved configurations and runs remain unchanged.
                    </p>
                    <Button
                      variant="danger"
                      onClick={() =>
                        onChange({
                          ...content,
                          cases: content.cases.filter((item) => item.case_id !== c.case_id),
                        })
                      }
                    >
                      Remove this case
                    </Button>
                  </ActionDialog>
                </ActionDialog>
              </div>
            )}
            {onCreateConfiguration && c.binding_id && (
              <Button
                disabled={disabled}
                aria-label={`Create configuration for ${c.title}`}
                onClick={() => onCreateConfiguration(c.case_id)}
              >
                Create configuration
              </Button>
            )}
            {(onChange || !!c.evidence_links.length) && <ApproachCaseContext item={c} />}
          </Disclosure>
        </article>
      ))}
      <DialogFrame ref={form.dialog} aria-labelledby="approach-case-title" onCancel={form.cancel}>
        <h2 id="approach-case-title">Intended case</h2>
        {item && (
          <form
            className="form-stack"
            onSubmit={(e) => {
              e.preventDefault();
              if (!item.title.trim()) {
                setError('Give this case a title.');
                return;
              }
              form.close();
            }}
          >
            {(['title', 'question', 'rationale'] as const).map((key) => (
              <label key={key}>
                Case {key}
                <TextArea
                  aria-label={'Case ' + key}
                  maxLength={key === 'title' ? 256 : 4096}
                  value={item[key]}
                  onChange={(e) => update({ ...item, [key]: e.target.value })}
                />
              </label>
            ))}
            <label>
              Intended model version
              <Select
                aria-label="Case model version"
                value={item.binding_id ?? ''}
                onChange={(e) => update({ ...item, binding_id: e.target.value || null })}
              >
                <option value="">No model version yet</option>
                {content.model_bindings.map((b) => (
                  <option key={b.binding_id} value={b.binding_id}>
                    {models.find((m) => m.model_revision_id === b.model_revision_id)
                      ? modelLabel(models.find((m) => m.model_revision_id === b.model_revision_id)!)
                      : b.model_revision_id.slice(0, 8) + ' (read-only)'}
                  </option>
                ))}
              </Select>
            </label>
            <p>
              Inputs and acceptance criteria are specified in a configuration, not this explanation.
            </p>
            {error && <p role="alert">{error}</p>}
            <div className="actions">
              <Button type="submit" variant="primary">
                Apply case
              </Button>
              <Button onClick={form.cancel}>Cancel</Button>
            </div>
          </form>
        )}
      </DialogFrame>
    </>
  );
}

export function ApproachBasis({
  api,
  studyId,
  content,
  resolved,
  closure,
  onChange,
  disabled = false,
}: {
  api?: HyprnMvpApi;
  studyId?: string;
  resolved?: ApproachResolution;
  closure?: ApproachClosureRead3;
} & EditProps) {
  const [items, setItems] = useState<Array<{ ref: ApproachBasisRef1; label: string }>>([]),
    [editing, setEditing] = useState(-1),
    [value, setValue] = useState<ApproachBasisRef1 | null>(null),
    [error, setError] = useState(''),
    [loading, setLoading] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null),
    generation = useRef(0);
  useApproachEditGuard(
    'prior-basis',
    !!value && JSON.stringify(value) !== JSON.stringify(content.basis_refs[editing] ?? null),
  );
  useEffect(
    () => () => {
      generation.current++;
    },
    [api, studyId],
  );
  const id = (ref: ApproachBasisRef1) =>
    ref.kind === 'run' ? ref.run_id : ref.configuration_revision_id;
  async function begin(index = -1) {
    if (!api || !studyId) return;
    const token = ++generation.current,
      actor = api.actor;
    setEditing(index);
    setValue(content.basis_refs[index] ?? null);
    setError('');
    setLoading(true);
    dialog.current?.showModal();
    try {
      const [configs, runs] = await Promise.all([api.configurations(studyId), api.runs(studyId)]);
      if (token === generation.current && actor === api.actor)
        setItems([
          ...configs.map((c: FrozenConfigurationRead7) => ({
            ref: {
              kind: 'configuration' as const,
              configuration_revision_id: c.configuration.configuration_revision_id,
              reason: '',
              relation: 'context' as const,
            },
            label:
              `Configuration · ${c.configuration.name} · ` +
              c.configuration.configuration_revision_id.slice(0, 8),
          })),
          ...runs.map((r: RunHistoryItem) => ({
            ref: {
              kind: 'run' as const,
              run_id: r.run_id,
              reason: '',
              relation: 'context' as const,
            },
            label: `${runLabel(r)} · Run ${r.run_id.slice(0, 8)} · ${r.state}`,
          })),
        ]);
    } catch (e) {
      if (token === generation.current && actor === api.actor) setError(message(e));
    } finally {
      if (token === generation.current) setLoading(false);
    }
  }
  const label = (ref: ApproachBasisRef1) =>
    ref.kind === 'configuration'
      ? 'Configuration · ' +
        (resolved?.configurations.find(
          (c) => c.configuration_revision_id === ref.configuration_revision_id,
        )?.name ?? ref.configuration_revision_id.slice(0, 8))
      : `Run · ${ref.run_id.slice(0, 8)}`;
  // Retained prior-basis closures never navigate to current case usage, wherever Earlier work is shown.
  return (
    <CaseNavigation.Provider value={null}>
      <section className="approach-basis">
        <h3>Earlier work</h3>
        <p className="context-line">
          Existing configurations and runs that informed this method. A failed run may inform the
          rationale; it is not a valid numerical input.
        </p>
        {onChange && (
          <Button
            disabled={disabled || content.basis_refs.length >= 64}
            onClick={() => void begin()}
          >
            Add earlier work
          </Button>
        )}
        {content.basis_refs.map((ref, index) => (
          <article key={ref.kind + id(ref)}>
            <h4>{label(ref)}</h4>
            <p>
              {ref.relation === 'supports'
                ? 'Supports'
                : ref.relation === 'challenges'
                  ? 'Challenges'
                  : 'Context'}
            </p>
            <p className="context-copy">{ref.reason}</p>
            <ActionDialog title="Earlier work record" label="View earlier work">
              <BasisRecord reference={ref} resolved={resolved} closure={closure} />
            </ActionDialog>
            {onChange && (
              <div className="section-actions">
                <Button disabled={disabled} onClick={() => void begin(index)}>
                  Edit earlier work {index + 1}
                </Button>
                <ActionDialog
                  title="Remove earlier work"
                  label={`Remove earlier work ${index + 1}`}
                  disabled={disabled}
                >
                  <p>Remove this reference? The original record remains unchanged.</p>
                  <Button
                    variant="danger"
                    onClick={() =>
                      onChange({
                        ...content,
                        basis_refs: content.basis_refs.filter((_, n) => n !== index),
                      })
                    }
                  >
                    Remove this basis
                  </Button>
                </ActionDialog>
              </div>
            )}
          </article>
        ))}
        <DialogFrame
          ref={dialog}
          aria-labelledby="prior-basis-title"
          onCancel={() => {
            generation.current++;
            setValue(null);
          }}
        >
          <h2 id="prior-basis-title">Earlier work</h2>
          <form
            className="form-stack"
            onSubmit={(e) => {
              e.preventDefault();
              if (!value) {
                setError('Select an earlier record.');
                return;
              }
              if (
                content.basis_refs.some(
                  (ref, index) =>
                    index !== editing && ref.kind === value.kind && id(ref) === id(value),
                )
              ) {
                setError('This record is already cited. Edit its rationale instead.');
                return;
              }
              onChange?.({
                ...content,
                basis_refs:
                  editing < 0
                    ? [...content.basis_refs, value]
                    : content.basis_refs.map((ref, index) => (index === editing ? value : ref)),
              });
              dialog.current?.close();
              setValue(null);
            }}
          >
            <label>
              Earlier record
              <Select
                aria-label="Earlier record"
                disabled={loading}
                value={value ? value.kind + '/' + id(value) : ''}
                onChange={(e) =>
                  setValue(
                    items.find((item) => item.ref.kind + '/' + id(item.ref) === e.target.value)
                      ?.ref ?? null,
                  )
                }
              >
                <option value="">Choose configuration or run</option>
                {items.map((item) => (
                  <option
                    key={item.ref.kind + id(item.ref)}
                    value={item.ref.kind + '/' + id(item.ref)}
                  >
                    {item.label}
                  </option>
                ))}
              </Select>
            </label>
            {value && (
              <>
                <label>
                  Relation
                  <Select
                    aria-label="Basis relation"
                    value={value.relation}
                    onChange={(e) =>
                      setValue({
                        ...value,
                        relation: e.target.value as ApproachBasisRef1['relation'],
                      })
                    }
                  >
                    <option value="supports">Supports</option>
                    <option value="challenges">Challenges</option>
                    <option value="context">Context</option>
                  </Select>
                </label>
                <label>
                  Why this record matters
                  <TextArea
                    aria-label="Basis reason"
                    maxLength={4096}
                    value={value.reason}
                    onChange={(e) => setValue({ ...value, reason: e.target.value })}
                  />
                </label>
              </>
            )}
            {loading && <p role="status">Loading earlier records…</p>}
            {error && <p role="alert">{error}</p>}
            <div className="actions">
              <Button type="submit" variant="primary" disabled={loading}>
                Apply basis
              </Button>
              <Button
                onClick={() => {
                  generation.current++;
                  dialog.current?.close();
                  setValue(null);
                }}
              >
                Cancel
              </Button>
            </div>
          </form>
        </DialogFrame>
      </section>
    </CaseNavigation.Provider>
  );
}
