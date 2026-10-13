import { Button, Panel, RecordBar, Select, StatusTag, TextInput } from '../design';
import { ModelEditor } from '../ModelEditor';
import { ModelView } from '../ModelView';
import { ActionDialog } from '../Presentation';
import { ComponentWhatWhy } from '../SelectionInspector';
import { UnitGuidance } from '../UnitEditor';
import { unresolvedModelUnits } from '../unitLabels';
import { resourceViewLink } from '../workspaceModel';
import type { GuardContext, ViewContext, ViewEntry } from './registry';

/** One canonical model view of the displayed model version: Models, Run › Model and the
 * configuration's "View model version". The current draft is authored in place on Models. */
export function modelWorkspace(ctx: ViewContext) {
  const { view, api, study, selection, select, navigate, model, revision } = ctx;
  const { displayedSnapshot, variableContext, frozenEvidence, methods, openMethodStep } = ctx;
  const { editorSlot, portPasteSlot, approachHandoff, modelActionHost, currentModel } = ctx;
  if (!displayedSnapshot) return displayedSnapshot;
  const version =
    'model_revision_id' in displayedSnapshot ? displayedSnapshot.model_revision_id : 'draft';
  return (
    <div className="model-region">
      <ModelView
        key={`${api.actor}:${study.study_id}:${view}:${displayedSnapshot.model_id}:${version}`}
        snapshot={displayedSnapshot}
        selection={selection}
        onSelect={select}
        values={variableContext}
        evidence={frozenEvidence}
        methods={methods}
        onOpenStep={openMethodStep}
        onPastePorts={
          view === 'model' && model && !revision
            ? async (scope, text, saveAuthoring) => {
                const editor = editorSlot.current();
                if (!editor.pastePorts) throw new Error('Model editor is unavailable.');
                return editor.pastePorts(scope, text, saveAuthoring);
              }
            : undefined
        }
        onPasteHandle={view === 'model' && model && !revision ? portPasteSlot.receive : undefined}
        authoring={
          view === 'model' && model && !revision
            ? (hosts) => (
                <ModelEditor
                  handoff={
                    approachHandoff?.studyId === model.study_id &&
                    approachHandoff.modelId === model.model_id
                      ? approachHandoff
                      : undefined
                  }
                  hosts={hosts}
                  explain={(id, source) => (
                    <ComponentWhatWhy
                      snapshot={model}
                      instanceId={id}
                      methods={methods}
                      onOpenStep={openMethodStep}
                      source={source}
                    />
                  )}
                  modelActionHost={modelActionHost}
                  key={model.model_id}
                  api={api}
                  model={model}
                  selection={selection}
                  onSelect={select}
                  onModel={currentModel}
                  navigate={navigate}
                  onHandle={editorSlot.receive}
                />
              )
            : undefined
        }
      />
    </div>
  );
}

/** The read-only model version bar sits directly below the study tabs. */
function modelBanner({ view, revision, navigate, chooseModel }: ViewContext) {
  return (
    view === 'model' &&
    revision && (
      <RecordBar
        title="Read-only model version"
        onReturn={() => navigate(() => void chooseModel(revision.model_id))}
        returnLabel="Return to current model"
      />
    )
  );
}

/** Models: the model list, a new model, or one model with its version controls, its units
 * check, the return to an approach hand-off and the canonical model view. */
function renderModel(ctx: ViewContext) {
  const { view, api, study, busy, loading, error, navigate, perform, openLink } = ctx;
  if (view !== 'model') return null;
  const { models, model, revision, revisions, selectedModel, creatingModel, dirty } = ctx;
  const { setCreatingModel, clearEditor, chooseModel, newConfiguration, select } = ctx;
  const { setResourceActions, setModelActionHost, approachHandoff, setApproachHandoff } = ctx;
  const { modelVersions, guards, currentModel, setRevisions, setNotice } = ctx;
  const unitsOf = revision ?? model;
  return (
    <>
      {!selectedModel && !creatingModel && (
        <section className="models-page">
          <div className="page-heading">
            <h2>Models</h2>
            <div className="section-actions">
              <div className="section-actions" ref={setResourceActions} />
              <Button
                variant="primary"
                disabled={busy || loading || !!api.pending}
                onClick={() =>
                  navigate(() => {
                    clearEditor();
                    setCreatingModel(true);
                  })
                }
              >
                New model
              </Button>
            </div>
          </div>
          <Panel className="model-list" bodyClassName="catalogue-body" label="Models">
            {models.map((m) => (
              <article className="model-row" key={m.model_id}>
                <h3>{m.name}</h3>
                <Button
                  aria-label={`Open model ${m.name}`}
                  onClick={() => navigate(() => void chooseModel(m.model_id))}
                >
                  Open model
                </Button>
              </article>
            ))}
            {!models.length && !loading && !error && (
              <p className="empty-state">No models yet. Add a model to this study.</p>
            )}
          </Panel>
        </section>
      )}
      {creatingModel && newModelPanel(ctx)}
      {selectedModel && (
        <div className="model-heading">
          <div>
            <Button
              className="link"
              aria-label="All models"
              onClick={() =>
                navigate(() => void openLink({ study: study.study_id, view: 'model' }))
              }
            >
              ← All models
            </Button>
            <h2>
              {revision
                ? `Model version ${revision.model_revision_id.slice(0, 8)}`
                : (model?.name ??
                  models.find((m) => m.model_id === selectedModel)?.name ??
                  'Model')}
            </h2>
            <p className="model-context">
              <StatusTag tone={dirty ? 'advisory' : 'inert'}>
                {revision
                  ? 'Read-only model version'
                  : dirty
                    ? 'Unsaved local edits'
                    : 'Draft · saved'}
              </StatusTag>
            </p>
          </div>
          <div className="model-version-controls">
            <Select
              aria-label="Model version"
              value={revision?.model_revision_id ?? 'draft'}
              disabled={loading || busy}
              onChange={(e) => {
                const rid = e.target.value;
                navigate(
                  () =>
                    void openLink({
                      study: study.study_id,
                      model: selectedModel,
                      view: 'model',
                      ...(rid === 'draft' ? {} : { revision: rid }),
                    }),
                );
              }}
            >
              <option value="draft">
                {model?.draft_revision?.slice(0, 8) ?? 'Current'} (draft)
              </option>
              {revisions.map((r) => (
                <option key={r.model_revision_id} value={r.model_revision_id}>
                  {r.model_revision_id.slice(0, 8)} (read-only)
                </option>
              ))}
            </Select>
            {model && (
              <Button
                variant="primary"
                disabled={busy || !!api.pending}
                onClick={() =>
                  void perform(() =>
                    modelVersions.saveVersion(study.study_id, model.model_id, {
                      guards,
                      onModel: currentModel,
                      onRevisions: setRevisions,
                      onNotice: setNotice,
                    }),
                  )
                }
              >
                Save model version
              </Button>
            )}
            <Button
              disabled={busy || !!api.pending}
              onClick={() =>
                navigate(
                  () => void perform(() => newConfiguration(selectedModel, revision ?? undefined)),
                )
              }
            >
              Create configuration
            </Button>
            <ActionDialog title="Model actions" label="…" triggerLabel="Model actions">
              <div className="hf-action-list">
                <div ref={setModelActionHost} />
                {revision && (
                  <ActionDialog title="Model version record" label="Record details">
                    <dl className="hf-record-details">
                      <dt>Model version</dt>
                      <dd>{revision.model_revision_id}</dd>
                      <dt>SHA-256</dt>
                      <dd>{revision.digest}</dd>
                    </dl>
                    <pre tabIndex={0} aria-label="Model version JSON">
                      {JSON.stringify(revision, null, 2)}
                    </pre>
                  </ActionDialog>
                )}
                <Button
                  disabled={busy || loading}
                  onClick={() =>
                    navigate(
                      () =>
                        void openLink({
                          study: study.study_id,
                          model: selectedModel,
                          view: 'model',
                          ...(revision ? { revision: revision.model_revision_id } : {}),
                        }),
                    )
                  }
                >
                  Reload model
                </Button>
                <div className="section-actions" ref={setResourceActions} />
              </div>
            </ActionDialog>
          </div>
        </div>
      )}
      {unitsOf && unresolvedModelUnits(unitsOf).length > 0 && (
        <details>
          <summary>
            <StatusTag tone="advisory">Units incomplete</StatusTag>
          </summary>
          <p>Resolve units in these active components before creating a configuration.</p>
          <ul>
            {unresolvedModelUnits(unitsOf).map((issue) => {
              const definition = (
                <code title={'Definition version ' + issue.definition_version_id}>
                  {issue.definition_version_id.slice(0, 8)}
                </code>
              );
              return (
                <li key={issue.instance_id + '/' + issue.port_id}>
                  {issue.component} · {issue.quantity}: units are not specified. {definition}
                  <Button
                    onClick={() =>
                      select({
                        kind: 'variable',
                        instance_id: issue.instance_id,
                        port_id: issue.port_id,
                      })
                    }
                  >
                    View quantity
                  </Button>
                </li>
              );
            })}
          </ul>
        </details>
      )}
      {approachHandoff?.studyId === study.study_id && (
        <div className="section-actions">
          <Button
            disabled={!!api.pending}
            onClick={() =>
              navigate(() => {
                setApproachHandoff(null);
                void openLink({ study: study.study_id, view: 'approach' });
              })
            }
          >
            Return to modeling approach
          </Button>
          <p className="context-line">
            Apply the model change, save a model version, then explicitly link its assumption in the
            approach.
          </p>
        </div>
      )}
      {modelWorkspace(ctx)}
    </>
  );
}

/** A new model from a starting template, created only once unit guidance has loaded. */
function newModelPanel(ctx: ViewContext) {
  const { api, study, busy, perform, openLink, generation, creationGuidance } = ctx;
  const { newModel, setNewModel, template, setTemplate, setCreatingModel } = ctx;
  return (
    <Panel className="creation-page">
      <h2>New model</h2>
      <UnitGuidance guidance={creationGuidance} />
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void perform(async () => {
            const token = generation.current,
              actor = api.actor,
              sid = study.study_id;
            if (!creationGuidance.catalog)
              throw new Error(
                'Unit guidance is unavailable. Retry unit guidance. Your edits are kept.',
              );
            // prettier-ignore
            const created = await api.createModelCommand(sid, {schema_version:'3',
              command_id:crypto.randomUUID(), expected_revision:study.revision, name:newModel,
              template});
            if (token !== generation.current || actor !== api.actor) return;
            setNewModel('');
            await openLink({ study: sid, model: created.model_id, view: 'model' });
          });
        }}
      >
        <label>
          New model name
          <TextInput
            required
            maxLength={4096}
            value={newModel}
            onChange={(e) => setNewModel(e.target.value)}
          />
        </label>
        <label>
          Starting model
          <Select
            aria-label="Starting model"
            value={template}
            onChange={(e) => setTemplate(e.target.value as typeof template)}
          >
            <option value="empty">Empty model</option>
            <option value="two_component_example">Ordinary two-component example</option>
          </Select>
        </label>
        <div className="actions">
          <Button
            type="submit"
            variant="primary"
            disabled={busy || !!api.pending || !creationGuidance.catalog}
          >
            Create model
          </Button>
          <Button type="button" disabled={busy} onClick={() => setCreatingModel(false)}>
            Cancel
          </Button>
        </div>
      </form>
    </Panel>
  );
}

/** The model editors: pasted ports, then the model editor, whose save is skipped when the
 * paste was dirty (the paste saves the authored editor edits with it). */
function modelGuard({ portPasteSlot, editorSlot }: GuardContext) {
  return [
    portPasteSlot.entry('port-paste'),
    editorSlot.entry('editor', {
      skip: (dirtyWhenSaved) => dirtyWhenSaved.has('port-paste'),
      onRefused: () =>
        document.querySelector<HTMLTextAreaElement>('textarea[spellcheck=false]')?.focus(),
    }),
  ];
}

export const modelView: ViewEntry<'model'> = {
  name: 'model',
  placement: { kind: 'tab', label: 'Models', position: 2 },
  parseLink: resourceViewLink,
  banner: modelBanner,
  render: renderModel,
  guard: modelGuard,
  available: () => true,
};
