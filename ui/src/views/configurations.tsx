import { ConfigurationList } from '../ConfigurationList';
import { ConfigurationPanel } from '../ConfigurationPanel';
import { Button, ReturnLink } from '../design';
import { ActionDialog } from '../Presentation';
import { RecordedConfiguration } from '../RecordedConfiguration';
import { resourceViewLink } from '../workspaceModel';
import { modelWorkspace } from './model';
import type { GuardContext, ViewContext, ViewEntry } from './registry';

/** The configuration draft (or modified run) of the current model. It stays mounted, hidden,
 * while a source result it binds is read on Runs, so its unsaved edits survive the return. */
function configurationDraft(ctx: ViewContext) {
  const { view, api, study, navigate, perform, openLink, link, chooseView } = ctx;
  const { model, setModel, setRevision, setView, setContext, setSelection } = ctx;
  const { modified, sourceReturn, viewSourceResult, setResourceActions, activeRun } = ctx;
  const { initialConfigurationRevision, setConfigInspection } = ctx;
  const { editorSlot, configurationSlot, pendingCopy } = ctx;
  const { evidence, setEvidence, submitConfiguration } = ctx;
  return (
    <div hidden={view !== 'configurations'}>
      {(view === 'configurations' || !!sourceReturn) && (model || modified) && (
        <>
          <ReturnLink
            label="Return to all configurations"
            onClick={() => chooseView('configurations')}
          />
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
            key={'configuration-' + (modified?.seed.source_run_id ?? model!.model_id)}
            api={api}
            model={model ?? modified!.seed.model_snapshot}
            study={study}
            authoringDirty={editorSlot.dirty}
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
  const { configuration, activeRun, setResourceActions } = ctx;
  const { viewSourceResult, submitConfiguration, copyRunConfiguration, newConfiguration } = ctx;
  return (
    <section className="configurations-page">
      {configuration ? (
        <>
          <ReturnLink
            label="Return to all configurations"
            onClick={() => chooseView('configurations')}
          />
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
            <ActionDialog purpose="reader" title="Configuration model" label="View model version" width="workspace">
              {modelWorkspace(ctx)}
            </ActionDialog>
          </RecordedConfiguration>
        </>
      ) : (
        <>
          <ConfigurationList
            actions={
              <Button
                variant="primary"
                disabled={busy || loading || !!api.pending || !ctx.calculationScope.revision}
                onClick={() =>
                  navigate(
                    () =>
                      void perform(async () => {
                        const { model, revision } = ctx.calculationScope;
                        if (!model || !revision) return;
                        const token = ctx.generation.current,
                          actor = api.actor;
                        const exact = await api.revision(study.study_id, model, revision);
                        if (token !== ctx.generation.current || actor !== api.actor) return;
                        await newConfiguration(model, exact);
                      }),
                  )
                }
              >
                New configuration
              </Button>
            }
            api={api}
            study={study.study_id}
            scope={ctx.calculationScope}
            onOpen={(id) =>
              navigate(
                () =>
                  void openLink({
                    study: study.study_id,
                    view: 'configurations',
                    configuration: id,
                  }),
              )
            }
          />
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
      {view === 'configurations' && !ctx.loading && !model && !modified && configurationsPage(ctx)}
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
  placement: { kind: 'link', tab: 'calculations', breadcrumb: 'Configurations' },
  parseLink: resourceViewLink,
  render: renderConfigurations,
  guard: configurationsGuard,
  available: () => true,
};
