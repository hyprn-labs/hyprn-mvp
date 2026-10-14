import { useRef, useState, type ReactNode } from 'react';
import { ApproachController, useApproachController } from './ApproachController';
import { ComponentWhatWhy } from './SelectionInspector';
import { methodLinks, type MethodLink, type MethodLinks } from './modelMethods';
import type { ModelDraftRead4 } from './contract';
import { Button, DialogFrame, TextArea } from './design';

/** Edit the existing approach draft from Models; never copy method prose into the model. */
export function ModelMethodDetails({
  controller,
  snapshot,
  instanceId,
  methods,
  onOpenStep,
  source,
}: {
  controller: ApproachController;
  snapshot: ModelDraftRead4;
  instanceId: string;
  methods: MethodLinks;
  onOpenStep: (link: MethodLink) => void;
  source: ReactNode;
}) {
  const state = useApproachController(controller);
  const dialog = useRef<HTMLDialogElement>(null);
  const invoker = useRef<HTMLElement | null>(null);
  const [editing, setEditing] = useState('');
  const [saved, setSaved] = useState(false);
  const draft = state.studyId === snapshot.study_id && !state.accessLost ? state.local : null;
  const currentMethods: MethodLinks = draft
    ? { kind: 'loaded', links: methodLinks(draft, null, snapshot) }
    : methods;
  const step = draft?.steps.find((item) => item.step_id === editing);
  async function begin(link: MethodLink) {
    invoker.current = document.activeElement as HTMLElement;
    setEditing(link.stepId);
    setSaved(false);
    dialog.current?.showModal();
    if (!draft) await controller.open(snapshot.study_id);
  }
  function close() {
    dialog.current?.close();
    invoker.current?.focus();
  }
  function update(field: 'purpose' | 'rationale' | 'transformation', value: string) {
    if (!draft || !step) return;
    controller.edit({
      ...draft,
      steps: draft.steps.map((item) =>
        item.step_id !== step.step_id
          ? item
          : field === 'transformation'
            ? { ...item, intent: { ...item.intent, transformation: value } }
            : { ...item, [field]: value },
      ),
    });
    setSaved(false);
  }
  return (
    <>
      <ComponentWhatWhy
        snapshot={snapshot}
        instanceId={instanceId}
        methods={currentMethods}
        onEditStep={(link) => void begin(link)}
        onOpenStep={onOpenStep}
        source={source}
      />
      {saved && (
        <p role="status">
          Explanation saved in the approach draft. Save a new approach version to publish it in the
          overview.
        </p>
      )}
      <DialogFrame
        ref={dialog}
        aria-label="Edit method explanation"
        onCancel={(event) => {
          event.preventDefault();
          close();
        }}
      >
        <h2>Edit method explanation</h2>
        {state.error && <p role="alert">{state.error}</p>}
        {controller.busy && <p role="status">Loading or saving the approach…</p>}
        {!controller.busy && !step && <p>This method is not in the current approach draft.</p>}
        {step && (
          <fieldset disabled={controller.busy || state.accessLost || state.status === 'uncertain'}>
            <p>{step.title}</p>
            <p className="context-line">
              This explanation is shared by the components linked to this method. Saved versions
              keep their recorded explanation.
            </p>
            <label>
              Purpose
              <TextArea
                maxLength={4096}
                value={step.purpose}
                onChange={(event) => update('purpose', event.target.value)}
              />
            </label>
            <label>
              Basis and reasoning
              <TextArea
                maxLength={4096}
                value={step.rationale}
                onChange={(event) => update('rationale', event.target.value)}
              />
            </label>
            <label>
              Calculation in plain words
              <TextArea
                maxLength={4096}
                value={step.intent.transformation}
                onChange={(event) => update('transformation', event.target.value)}
              />
            </label>
            <div className="section-actions">
              <Button
                variant="primary"
                disabled={!controller.dirty}
                onClick={() =>
                  void controller.save().then((ok) => {
                    if (ok) {
                      setSaved(true);
                      close();
                    }
                  })
                }
              >
                Save explanation draft
              </Button>
              <Button onClick={close}>Close</Button>
            </div>
          </fieldset>
        )}
        {!step && <Button onClick={close}>Close</Button>}
      </DialogFrame>
    </>
  );
}
