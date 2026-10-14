import { OverviewStudyQuestion } from '../ApproachAssumptions';
import { ApproachReader } from '../ApproachPanel';
import { ApproachFindings } from '../ApproachFindings';
import { resourceViewLink } from '../workspaceModel';
import type { ViewEntry } from './registry';

export const casesView: ViewEntry<'cases'> = {
  name: 'cases',
  placement: { kind: 'tab', label: 'Cases and their answers', position: 5 },
  parseLink: resourceViewLink,
  available: () => true,
  render: (ctx) =>
    ctx.view !== 'cases' ? null : (
      <OverviewStudyQuestion api={ctx.api} studyId={ctx.study.study_id}>
        {(_question, _details, _version, saved) =>
          saved ? (
            <ApproachReader
              presentation="cases"
              source={{ kind: 'saved', record: saved }}
              studyId={ctx.study.study_id}
              findings={(slot) => (
                <ApproachFindings
                  {...slot}
                  section="cases"
                  api={ctx.api}
                  studyId={ctx.study.study_id}
                  saved={saved}
                  onOpen={(target) =>
                    ctx.navigate(() => {
                      ctx.setApproachReturn({ study: ctx.study.study_id, view: 'cases' });
                      void ctx.openLink(target);
                    })
                  }
                />
              )}
            />
          ) : (
            <p>No saved cases yet. Define them in the modeling approach.</p>
          )
        }
      </OverviewStudyQuestion>
    ),
};
