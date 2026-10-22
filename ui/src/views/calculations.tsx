import { CalculationList, CalculationRecord } from '../CalculationsPanel';
import type { WorkspaceLink } from '../workspaceModel';
import type { ViewContext, ViewEntry } from './registry';

/** Calculations: the selected model version's calculations, or one exact calculation version
 * with its configurations, criterion bindings and evaluated runs. */
function renderCalculations(ctx: ViewContext) {
  const { view, api, study, navigate, openLink, loading } = ctx;
  if (view !== 'calculations' || loading || !ctx.calculationScope.revision) return null;
  const go = (target: Omit<WorkspaceLink, 'study'>) =>
    navigate(() => void openLink({ study: study.study_id, ...target }, true));
  const open = (version: string) => go({ view: 'calculations', calculation_version: version });
  return (
    <section className="calculations-page">
      {ctx.calculationVersion ? (
        <CalculationRecord
          key={ctx.calculationVersion}
          api={api}
          study={study.study_id}
          scope={ctx.calculationScope}
          versionId={ctx.calculationVersion}
          onOpen={open}
          onList={() => go({ view: 'calculations', ...ctx.calculationScope })}
          onOpenConfiguration={(configuration) => go({ view: 'configurations', configuration })}
          onOpenRun={(run) => go({ view: 'runs', run })}
        />
      ) : (
        <CalculationList
          key={ctx.calculationScope.revision}
          api={api}
          study={study.study_id}
          scope={ctx.calculationScope}
          onOpen={open}
        />
      )}
    </section>
  );
}

/** A calculation link names one exact calculation version and no other record. */
function calculationLink(link: WorkspaceLink) {
  if (link.configuration || link.run)
    throw new Error('This analysis link has conflicting resource context.');
}

export const calculationsView: ViewEntry<'calculations'> = {
  name: 'calculations',
  placement: { kind: 'tab', label: 'Experiments', position: 3 },
  parseLink: calculationLink,
  render: renderCalculations,
  available: () => true,
};
