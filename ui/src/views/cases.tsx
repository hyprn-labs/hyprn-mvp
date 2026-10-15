import { OverviewStudyQuestion } from '../ApproachAssumptions';
import { ApproachReader } from '../ApproachPanel';
import { ApproachFindings } from '../ApproachFindings';
import { approachLink } from './approach';
import type { ViewEntry } from './registry';

export const casesView: ViewEntry<'cases'> = {
  name: 'cases',
  placement: { kind: 'tab', label: 'Cases', position: 5 },
  parseLink: approachLink,
  available: () => true,
  render: (ctx) =>
    ctx.view !== 'cases' ? null : (
      <OverviewStudyQuestion
        key={ctx.study.study_id + (ctx.requestedApproach ?? 'latest')}
        requestedVersion={ctx.requestedApproach}
        api={ctx.api}
        studyId={ctx.study.study_id}
      >
        {(_question, _details, _version, saved) =>
          saved ? (
            <ApproachReader
              presentation="cases"
              focusCase={
                ctx.requestedCase?.approach === saved.version.approach_version_id
                  ? ctx.requestedCase
                  : undefined
              }
              source={{ kind: 'saved', record: saved }}
              studyId={ctx.study.study_id}
              findings={(slot) => (
                <ApproachFindings
                  {...slot}
                  section="cases"
                  api={ctx.api}
                  studyId={ctx.study.study_id}
                  saved={saved}
                  onCreateConfiguration={(caseId) => {
                    const item = saved.version.content.cases.find(
                      (value) => value.case_id === caseId,
                    );
                    const binding = saved.version.content.model_bindings.find(
                      (value) => value.binding_id === item?.binding_id,
                    );
                    const model = saved.closure.models.find(
                      (value) =>
                        value.model_revision_id === binding?.model_revision_id &&
                        value.model_id === binding?.model_id,
                    );
                    if (model)
                      ctx.navigate(
                        () =>
                          void ctx.perform(() =>
                            ctx.newConfiguration(model.model_id, model, {
                              approach_version_id: saved.version.approach_version_id,
                              case_id: caseId,
                            }),
                          ),
                      );
                  }}
                  onOpen={(target) =>
                    ctx.navigate(() => {
                      ctx.setApproachReturn({
                        study: ctx.study.study_id,
                        view: 'cases',
                        approach: saved.version.approach_version_id,
                        ...(ctx.requestedCase ? { case: ctx.requestedCase.id } : {}),
                      });
                      void ctx.openLink(target);
                    })
                  }
                />
              )}
            />
          ) : _version === null ? (
            <p>No saved cases yet. Define them in the modeling approach.</p>
          ) : (
            _question
          )
        }
      </OverviewStudyQuestion>
    ),
};
