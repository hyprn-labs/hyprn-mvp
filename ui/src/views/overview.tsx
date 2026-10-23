import { StudyActivity } from '../StudyActivity';
import { StudyBrief } from '../StudyBrief';
import { StudyAnswer } from '../StudyAnswer';
import { ContentColumn } from '../design';
import { resourceViewLink } from '../workspaceModel';
import type { GuardContext, ViewContext, ViewEntry } from './registry';

/** The brief and versioned answer are the study's canonical Overview. */
function renderOverview(ctx: ViewContext) {
  const { view, api, study, navigate, openLink } = ctx;
  if (view !== 'overview') return null;
  return (
    <ContentColumn width="reading">
      <StudyBrief
        key={`${api.actor}:${study.study_id}`}
        api={api}
        studyId={study.study_id}
        controller={ctx.brief}
      />
      <StudyActivity key={`activity:${api.actor}:${study.study_id}`} api={api}
        study={study.study_id} onOpen={link => navigate(() => void openLink(link, true))} />
      <StudyAnswer
        key={`answer:${api.actor}:${study.study_id}`}
        api={api}
        studyId={study.study_id}
        controller={ctx.answer}
        onOpen={(link) => navigate(() => void openLink(link, true))}
      />
    </ContentColumn>
  );
}

/** Guard the brief and answer drafts before leaving Overview. */
function overviewGuard({ brief, answer }: GuardContext) {
  return [
    {
      name: 'brief',
      shown: brief.dirty,
      guard: () => brief.handle,
    },
    {
      name: 'answer',
      shown: answer.dirty,
      guard: () => answer.handle,
    },
  ];
}

export const overviewView: ViewEntry<'overview'> = {
  name: 'overview',
  placement: { kind: 'tab', label: 'Overview', position: 1 },
  parseLink: resourceViewLink,
  render: renderOverview,
  guard: overviewGuard,
  available: () => true,
};
