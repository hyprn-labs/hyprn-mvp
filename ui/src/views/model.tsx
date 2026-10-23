import { OpenLink } from '../design';
import { ModelVersionSelect } from '../ModelVersionSelect';
import { RecordDetails } from '../design';
import {
  Button,
  ContentColumn,
  CreateVersionAction,
  PageHeader,
  Panel,
  ResourceCard,
  FormActions,
  ReturnLink,
  Select,
  StatusTag,
  RecordState,
  TextInput,
} from '../design';
import { ModelEditor } from '../ModelEditor';
import { ModelView } from '../ModelView';
import { ActionDialog } from '../Presentation';
import { AttributionDetail, RecordAttribution } from '../attribution';
import { ModelExplanation } from '../ModelExplanation';
import { UnitGuidance } from '../UnitEditor';
import { unresolvedModelUnits } from '../unitLabels';
import { resourceViewLink } from '../workspaceModel';
import type { GuardContext, ViewContext, ViewEntry } from './registry';

/** One canonical model view of the displayed model version: Models, Run › Model and the
 * configuration's "View model version". The current draft is authored in place on Models. */
export function modelWorkspace(ctx: ViewContext) {
  const { view, api, study, selection, select, navigate, model, revision } = ctx;
  const { displayedSnapshot, variableContext, frozenEvidence } = ctx;
  const { editorSlot, modelActionHost, currentModel } = ctx;
  if (!displayedSnapshot) return displayedSnapshot;
  const version =
    'model_revision_id' in displayedSnapshot ? displayedSnapshot.model_revision_id : 'draft';
  return (
    <div className="model-region">
      <ModelView
        api={api}
        studyId={study.study_id}
        key={`${api.actor}:${study.study_id}:${view}:${displayedSnapshot.model_id}:${version}`}
        snapshot={displayedSnapshot}
        selection={selection}
        onSelect={select}
        onEditSelection={
          view === 'model' && model && !revision
            ? (next, accepted) => {
                const apply = () => {
                  select(next);
                  accepted();
                };
                if (
                  'instance_id' in selection &&
                  'instance_id' in next &&
                  selection.instance_id === next.instance_id
                )
                  apply();
                else navigate(apply);
              }
            : undefined
        }
        modelExplanation={
          <ModelExplanation
            api={api}
            studyId={study.study_id}
            modelId={displayedSnapshot.model_id}
            revisionId={version === 'draft' ? null : version}
            revisions={ctx.revisions}
            snapshot={displayedSnapshot}
            editable={view === 'model' && !revision}
            onHandle={view === 'model' ? ctx.explanationSlot.receive : undefined}
          />
        }
        values={variableContext}
        evidence={frozenEvidence}
        authoring={
          view === 'model' && model && !revision
            ? (hosts) => (
                <ModelEditor
                  hosts={hosts}
                  explain={(_id, source) => (
                    <div hidden={hosts.pane !== 'Python'} className="component-source">
                      {source}
                    </div>
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
      <ReturnLink
        onClick={() => navigate(() => void chooseModel(revision.model_id))}
        label="Return to current model"
      />
    )
  );
}

/** Models: the model list, a new model, or one model with its version controls, its units
 * check and the canonical model view. */
function renderModel(ctx: ViewContext) {
  const { view, api, study, busy, loading, error, navigate, perform, openLink } = ctx;
  if (view !== 'model') return null;
  const { models, model, revision, revisions, selectedModel, creatingModel, dirty } = ctx;
  const { setCreatingModel, clearEditor, chooseModel, newConfiguration, select } = ctx;
  const { setResourceActions, setModelActionHost } = ctx;
  const { modelVersions, guards, currentModel, setRevisions, setNotice } = ctx;
  const unitsOf = revision ?? model;
  const leaves = revisions.filter(
    (candidate) =>
      !revisions.some((other) => other.parent_model_revision_id === candidate.model_revision_id),
  );
  const canCreateVersion =
    revision && leaves.length === 1 && leaves[0].model_revision_id === revision.model_revision_id;

  return (
    <>
      {!selectedModel && !creatingModel && (
        <section className="models-page">
          <PageHeader
            title="Models"
            actions={
              <>
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
              </>
            }
          />
          <Panel className="model-list" bodyClassName="hf-flow" label="Models">
            {models.map((m) => (
              <ResourceCard
                key={m.model_id}
                level={3}
                title={m.name}
                actions={
                  <OpenLink
                    aria-label={`Open model ${m.name}`}
                    onClick={() => navigate(() => void chooseModel(m.model_id))}
                  >
                    Open model
                  </OpenLink>
                }
              />
            ))}
            {!models.length && !loading && !error && (
              <p className="empty-state">No models yet. Add a model to this study.</p>
            )}
          </Panel>
        </section>
      )}
      {creatingModel && newModelPanel(ctx)}
      {selectedModel && (
        <>
          <PageHeader
            className="model-header"
            help="model"
            returnTo={{
              label: 'Return to all models',
              onClick: () =>
                navigate(() => void openLink({ study: study.study_id, view: 'model' })),
            }}
            title={
              (revision && 'name' in revision && typeof revision.name === 'string'
                ? revision.name : undefined) ??
              model?.name ??
              models.find((m) => m.model_id === selectedModel)?.name ??
              'Model name unavailable'
            }
            details={
              revision ? (
                <RecordDetails
                  kind="Model"
                  versionId={revision.model_revision_id}
                  metadata={
                    <>
                      <RecordState state="saved" />
                      <RecordAttribution kind="model_version" id={revision.model_revision_id} />
                    </>
                  }
                >
                  <dl className="hf-record-details">
                    <dt>Model version</dt>
                    <dd>{revision.model_revision_id}</dd>
                    <dt>SHA-256</dt>
                    <dd>{revision.digest}</dd>
                    <AttributionDetail
                      kind="model_version"
                      id={revision.model_revision_id}
                      label="Saved by"
                    />
                  </dl>
                  <pre tabIndex={0} aria-label="Model version JSON">
                    {JSON.stringify(revision, null, 2)}
                  </pre>
                </RecordDetails>
              ) : (
                <>
                  <RecordState state={dirty ? 'changed' : 'draft'} />
                  {!dirty && <RecordAttribution kind="model_draft" id={model?.draft_revision} />}
                </>
              )
            }
            controls={
              <ModelVersionSelect
                draft
                value={revision?.model_revision_id ?? 'draft'}
                revisions={revisions}
                disabled={loading || busy}
                onChange={(rid) =>
                  navigate(
                    () =>
                      void openLink({
                        study: study.study_id,
                        model: selectedModel,
                        view: 'model',
                        ...(rid === 'draft' ? {} : { revision: rid }),
                      }),
                  )
                }
              />
            }
            actions={
              <>
                {canCreateVersion && (
                  <CreateVersionAction
                    disabled={busy || loading || !!api.pending}
                    title="Prepare changes in the current model draft. Existing draft edits are kept."
                    onClick={() => navigate(() => void chooseModel(selectedModel))}
                  />
                )}
                {model && !revision && (
                  <div className="model-save-version">
                    <Button
                      variant="primary"
                      disabled={busy || loading || !!api.pending}
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
                  </div>
                )}
                <Button
                  disabled={busy || loading || !!api.pending}
                  onClick={() =>
                    navigate(
                      () =>
                        void perform(() => newConfiguration(selectedModel, revision ?? undefined)),
                    )
                  }
                >
                  Create configuration
                </Button>
                <ActionDialog title="Model actions" label="…" triggerLabel="Model actions">
                  <div className="hf-action-list">
                    <div ref={setModelActionHost} />

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
                      Refresh model
                    </Button>
                    <div className="section-actions" ref={setResourceActions} />
                  </div>
                </ActionDialog>
              </>
            }
          />
        </>
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
                  <OpenLink
                    onClick={() =>
                      select({
                        kind: 'variable',
                        instance_id: issue.instance_id,
                        port_id: issue.port_id,
                      })
                    }
                  >
                    View quantity
                  </OpenLink>
                </li>
              );
            })}
          </ul>
        </details>
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
    <ContentColumn width="form">
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
          <FormActions primary={<Button type="submit" variant="primary"
            disabled={busy || !!api.pending || !creationGuidance.catalog}>Create model</Button>}>
            <Button type="button" disabled={busy} onClick={() => setCreatingModel(false)}>Cancel</Button>
          </FormActions>
        </form>
      </Panel>
    </ContentColumn>
  );
}

/** The model editor; a refused save returns focus to its source editor. */
function modelGuard({ editorSlot, explanationSlot }: GuardContext) {
  return [
    explanationSlot.entry('explanation'),
    editorSlot.entry('editor', {
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
