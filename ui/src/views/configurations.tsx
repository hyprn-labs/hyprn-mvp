import { RecordAttribution } from '../attribution';
import { ConfigurationPanel } from '../ConfigurationPanel';
import { Button, Panel } from '../design';
import { ActionDialog } from '../Presentation';
import { RecordedConfiguration } from '../RecordedConfiguration';
import { configurationCounts } from '../recordLabels';
import { resourceViewLink } from '../workspaceModel';
import { modelWorkspace } from './model';
import type { GuardContext, ViewContext, ViewEntry } from './registry';

/** The configuration draft (or modified run) of the current model. It stays mounted, hidden,
 * while a source result it binds is read on Runs, so its unsaved edits survive the return. */
function configurationDraft(ctx: ViewContext) {
  const { view, api, study, navigate, perform, openLink, link, chooseView } = ctx;
  const { model, setModel, setRevision, setView, setContext, setSelection } = ctx;
  const { modified, sourceReturn, viewSourceResult, setResourceActions, activeRun } = ctx;
  const { initialConfigurationRevision, initialConfigurationApproach, setConfigInspection } = ctx;
  const { editorSlot, portPasteSlot, metadataDirty, configurationSlot, pendingCopy } = ctx;
  const { evidence, setEvidence, submitConfiguration } = ctx;
  return (
    <div hidden={view !== 'configurations'}>
      {(view === 'configurations' || !!sourceReturn) && (model || modified) && (
        <>
          <Button className="link back-link" onClick={() => chooseView('configurations')}>
            ← All configurations
          </Button>
          <ConfigurationPanel
            onViewModelUnit={(exact, target) =>
              navigate(() => {
                setRevision(exact);
                setModel(null);
                setView('model');
                setContext({
                  actor_id: api.actor,
                  study_id: study.study_id,
                  view: 'model',
                  kind: 'revision',
                  model_id: exact.model_id,
                  model_revision_id: exact.model_revision_id,
                  snapshot: exact,
                });
                setSelection({ kind: 'variable', ...target });
                link({
                  study: study.study_id,
                  model: exact.model_id,
                  revision: exact.model_revision_id,
                  view: 'model',
                });
              })
            }
            modified={modified ?? undefined}
            onCancelModified={() =>
              navigate(() => {
                if (study && modified)
                  void openLink({
                    study: study.study_id,
                    view: 'runs',
                    run: modified.seed.source_run_id,
                  });
              })
            }
            onViewSourceResult={(runId, output) =>
              void perform(() => viewSourceResult(runId, output))
            }
            resourceActionsRef={view === 'configurations' ? setResourceActions : undefined}
            initialRevision={initialConfigurationRevision}
            initialApproach={initialConfigurationApproach}
            key={'configuration-' + (modified?.seed.source_run_id ?? model!.model_id)}
            api={api}
            model={model ?? modified!.seed.model_snapshot}
            study={study}
            authoringDirty={editorSlot.dirty || portPasteSlot.dirty || metadataDirty}
            activeRun={activeRun}
            onInspection={setConfigInspection}
            evidence={evidence}
            onEvidenceRecords={setEvidence}
            onSubmit={submitConfiguration}
            onHandle={(h) => {
              configurationSlot.receive(h);
              if (model && pendingCopy.current?.configuration.model_id === model.model_id) {
                const copy = pendingCopy.current;
                pendingCopy.current = null;
                h.copy(copy.configuration, copy.snapshot);
              }
            }}
          />
        </>
      )}
    </div>
  );
}

/** Saved configurations: one read-only configuration, or the list with a new configuration. */
function configurationsPage(ctx: ViewContext) {
  const { api, study, busy, loading, error, navigate, perform, openLink, chooseView } = ctx;
  const { configuration, configurations, models, activeRun, setResourceActions } = ctx;
  const { viewSourceResult, submitConfiguration, copyRunConfiguration, newConfiguration } = ctx;
  const { choosingConfiguration, setChoosingConfiguration, chooseConfigurationModel } = ctx;
  return (
    <section className="configurations-page">
      {configuration ? (
        <>
          <Button className="link back-link" onClick={() => chooseView('configurations')}>
            ← All configurations
          </Button>
          <RecordedConfiguration
            onViewSourceResult={(runId, output) =>
              void perform(() => viewSourceResult(runId, output))
            }
            resourceActionsRef={setResourceActions}
            api={api}
            activeRun={activeRun}
            onSubmit={submitConfiguration}
            saved={configuration}
            onCopy={() =>
              void perform(() =>
                copyRunConfiguration(configuration.configuration, configuration.model_snapshot),
              )
            }
          >
            <ActionDialog
              title={'Model version ' + configuration.configuration.model_revision_id.slice(0, 8)}
              label="View model version"
              width="workspace"
            >
              {modelWorkspace(ctx)}
            </ActionDialog>
          </RecordedConfiguration>
        </>
      ) : (
        <>
          <div className="page-heading">
            <p>Inputs, evidence and criteria for a saved model version.</p>
            <Button
              variant="primary"
              disabled={busy || !!api.pending}
              onClick={() => void perform(chooseConfigurationModel)}
            >
              New configuration
            </Button>
          </div>
          {choosingConfiguration && (
            <Panel className="creation-page" title="New configuration">
              <p>
                Choose a model. Its current draft will be saved as the model version for this
                configuration.
              </p>
              {models.map((m) => (
                <div className="record" key={m.model_id}>
                  <span>{m.name}</span>
                  <Button
                    disabled={busy || !!api.pending}
                    onClick={() => void perform(() => newConfiguration(m.model_id))}
                  >
                    Use {m.name}
                  </Button>
                </div>
              ))}
              {!models.length && <p>Create a model before configuring a calculation.</p>}
              <Button onClick={() => setChoosingConfiguration(false)}>Cancel</Button>
            </Panel>
          )}
          <Panel label="Configurations">
            <p className="context-line">
              {configurationCounts(configurations)} · All saved versions
            </p>
            {configurations.map((c) => {
              const version = c.configuration.configuration_revision_id.slice(0, 8);
              const modelVersion = c.configuration.model_revision_id.slice(0, 8);
              const inputs = c.configuration.inputs.length;
              return (
                <article className="model-row" key={c.configuration.configuration_revision_id}>
                  <div>
                    <h3>{c.configuration.name}</h3>
                    <p className="row-description">
                      Version {version} · Model version {modelVersion} · {inputs} inputs
                      <RecordAttribution
                        kind="configuration_version"
                        id={c.configuration.configuration_revision_id}
                        inline
                      />
                    </p>
                  </div>
                  <Button
                    onClick={() =>
                      navigate(
                        () =>
                          void openLink({
                            study: study.study_id,
                            view: 'configurations',
                            configuration: c.configuration.configuration_revision_id,
                          }),
                      )
                    }
                  >
                    Open configuration
                  </Button>
                </article>
              );
            })}
            {!configurations.length && !loading && !error && (
              <p className="empty-state">
                No configurations yet. Save explicit inputs for a model version.
              </p>
            )}
          </Panel>
        </>
      )}
    </section>
  );
}

function renderConfigurations(ctx: ViewContext) {
  const { view, model, modified } = ctx;
  return (
    <>
      {configurationDraft(ctx)}
      {view === 'configurations' && !model && !modified && configurationsPage(ctx)}
    </>
  );
}

/** The configuration draft, saved last. */
function configurationsGuard({ configurationSlot }: GuardContext) {
  return [
    configurationSlot.entry('configuration', {
      onRefused: () => document.getElementById('configuration')?.scrollIntoView(),
    }),
  ];
}

export const configurationsView: ViewEntry<'configurations'> = {
  name: 'configurations',
  placement: { kind: 'tab', label: 'Configurations', position: 3 },
  parseLink: resourceViewLink,
  render: renderConfigurations,
  guard: configurationsGuard,
  available: () => true,
};
