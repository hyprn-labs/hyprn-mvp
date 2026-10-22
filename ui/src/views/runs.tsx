import { ReturnLink } from '../design';
import { RunPanel } from '../RunPanel';
import { resourceViewLink } from '../workspaceModel';
import { modelWorkspace } from './model';
import type { ViewContext, ViewEntry } from './registry';

/** Runs: the run history and one run record. The panel stays mounted, hidden, on every view of
 * the study, so its history, filters and open run survive navigation. */
function renderRuns(ctx: ViewContext) {
  const { view, api, study, navigate, perform, link, select, setSelection, setContext } = ctx;
  const { sourceReturn, returnToConfiguration, viewSourceResult, setResourceActions } = ctx;
  const { runFilters, setRunFilters, runListEpoch, submitted, setActiveRun } = ctx;
  const { runInspection, setRunInspection, createModified } = ctx;
  return (
    <div hidden={view !== 'runs'}>
      {sourceReturn && view === 'runs' && (
        <ReturnLink
          label={sourceReturn.view === 'runs' ? 'Return to run' : 'Return to configuration'}
          onClick={returnToConfiguration}
        />
      )}
      <RunPanel
        active={view === 'runs' && !ctx.loading}
        modelScope={ctx.calculationScope}
        filters={runFilters}
        onFilters={setRunFilters}
        onViewSourceResult={(runId, output) => void perform(() => viewSourceResult(runId, output))}
        sourceOutput={sourceReturn ?? undefined}
        resourceActionsRef={view === 'runs' ? setResourceActions : undefined}
        listEpoch={runListEpoch}
        workspace={view === 'runs' ? modelWorkspace(ctx) : undefined}
        onSelect={select}
        key={study.study_id}
        api={api}
        studyId={study.study_id}
        submitted={submitted}
        onActive={setActiveRun}
        onInspection={(detail) => {
          setRunInspection(detail);
          if (view === 'runs' && detail) {
            if (sourceReturn?.runId === detail.run_id)
              setSelection({ kind: 'variable', ...sourceReturn.output });
            else if (runInspection?.run_id !== detail.run_id) setSelection({ kind: 'none' });
            const snapshot = detail.history?.model_snapshot ?? undefined;
            setContext({
              actor_id: api.actor,
              study_id: study.study_id,
              view: 'runs',
              kind: 'run',
              run_id: detail.run_id,
              snapshot,
              model_id: snapshot?.model_id,
              model_revision_id: snapshot?.model_revision_id,
              configuration_revision_id: detail.history?.configuration?.configuration_revision_id,
            });
            link({ study: study.study_id, view: 'runs', run: detail.run_id });
          }
        }}
        onHistory={() => {
          if (view === 'runs')
            link({ study: study.study_id, view: 'runs', ...ctx.calculationScope });
        }}
        navigate={navigate}
        onCreateModified={createModified}
      />
    </div>
  );
}

export const runsView: ViewEntry<'runs'> = {
  name: 'runs',
  placement: { kind: 'link', tab: 'calculations', breadcrumb: 'Runs' },
  parseLink: resourceViewLink,
  render: renderRuns,
  available: () => true,
};
