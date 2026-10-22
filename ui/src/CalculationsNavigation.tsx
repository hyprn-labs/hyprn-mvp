import { OpenLink } from './design';
import { Button, Select, Tabs, CalculationNavigation } from './design';
import { ModelVersionSelect } from './ModelVersionSelect';
import type { ViewContext } from './views/registry';

export function CalculationsNavigation({ ctx }: { ctx: ViewContext }) {
  if (ctx.view !== 'calculations' && ctx.view !== 'configurations' && ctx.view !== 'runs')
    return null;
  const { loading, busy } = ctx;
  const snapshot =
    ctx.view === 'runs'
      ? ctx.runInspection?.history?.model_snapshot
      : ctx.view === 'configurations'
        ? (ctx.configuration?.model_snapshot ?? ctx.configInspection?.snapshot)
        : undefined;
  const scope = snapshot
    ? { model: snapshot.model_id, revision: snapshot.model_revision_id }
    : ctx.calculationScope;
  const calculationRevisions =
    scope.model === ctx.calculationScope.model ? [...ctx.calculationRevisions] : [];
  if (
    snapshot &&
    !calculationRevisions.some((r) => r.model_revision_id === snapshot.model_revision_id)
  )
    calculationRevisions.push(snapshot);
  const models = [...ctx.models];
  if (scope.model && !models.some((m) => m.model_id === scope.model))
    models.push({ model_id: scope.model, name: 'Model' });
  const change = (model?: string, revision?: string, view = ctx.view) =>
    ctx.navigate(
      () => void ctx.openLink({ study: ctx.study.study_id, view, model, revision }, true),
    );
  return (
    <CalculationNavigation
      model={
        <Select
          aria-label="Analysis model"
          value={scope.model ?? ''}
          disabled={loading || busy}
          onChange={(e) => change(e.target.value)}
        >
          {!models.length && <option value="">No models</option>}
          {models.map((m) => (
            <option key={m.model_id} value={m.model_id}>
              {m.name}
            </option>
          ))}
        </Select>
      }
      version={
        <ModelVersionSelect
          showLabel={false}
          value={scope.revision ?? ''}
          revisions={calculationRevisions}
          disabled={loading || busy || !calculationRevisions.length}
          onChange={(r) => change(scope.model, r)}
        />
      }
    >
      <Tabs
        label="Experiments"
        value={ctx.view}
        items={[
          { id: 'calculations', label: 'Analyses' },
          { id: 'configurations', label: 'Configurations' },
          { id: 'runs', label: 'Runs' },
        ]}
        onChange={(v) =>
          change(scope.model, scope.revision, v as 'calculations' | 'configurations' | 'runs')
        }
      />
      {!loading && !scope.revision && (
        <div className="empty-state">
          <p>Save a model version to prepare analyses.</p>
          <OpenLink
            onClick={() =>
              ctx.navigate(
                () =>
                  void ctx.openLink({
                    study: ctx.study.study_id,
                    view: 'model',
                    model: scope.model,
                  }),
              )
            }
          >
            View model
          </OpenLink>
        </div>
      )}
    </CalculationNavigation>
  );
}
