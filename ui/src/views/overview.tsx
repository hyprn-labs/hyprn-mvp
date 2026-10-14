import { OverviewStudyQuestion } from '../ApproachAssumptions';
import { message } from '../api';
import { RecordAttribution } from '../attribution';
import { Button, Panel, TextArea, TextInput } from '../design';
import { ApproachReader } from '../ApproachPanel';
import { ApproachFindings } from '../ApproachFindings';
import { ActionDialog, SectionHeader } from '../Presentation';
import { resourceViewLink } from '../workspaceModel';
import type { GuardContext, ViewContext, ViewEntry } from './registry';

/** Read-only projection of the exact saved approach and its associated answers. */
function renderOverview(ctx: ViewContext) {
  const { view, api, study, busy, error, notice, navigate, openLink, perform } = ctx;
  const { metadata, setMetadata, metadataDirty, saveMetadata, approachEntry } = ctx;
  if (view !== 'overview') return null;
  return (
    <>
      <div className="approach-overview">
        <OverviewStudyQuestion
          key={`${api.actor}:${study.study_id}`}
          api={api}
          studyId={study.study_id}
        >
          {(question, details, version, saved) => {
            const editStudy = (
              <ActionDialog title="Edit study" label="Edit study">
                <p>
                  Edit the study name and description used in the study list. To edit the study
                  question, open the modeling approach.
                </p>
                <RecordAttribution kind="study_context" id={study.revision} line />
                <fieldset className="form-stack" disabled={busy || !!api.pending}>
                  <label>
                    Study name
                    <TextInput
                      value={metadata.name}
                      maxLength={4096}
                      onChange={(e) => setMetadata({ ...metadata, name: e.target.value })}
                    />
                  </label>
                  <label>
                    Study list description
                    <TextArea
                      aria-label="Study list description"
                      value={metadata.description}
                      maxLength={4096}
                      onChange={(e) => setMetadata({ ...metadata, description: e.target.value })}
                    />
                  </label>
                  <Button
                    variant="primary"
                    disabled={!metadataDirty}
                    onClick={() => void perform(saveMetadata)}
                  >
                    Save study context
                  </Button>
                </fieldset>
                {metadataDirty && (
                  <p role="status">Unsaved changes are kept when you close this editor.</p>
                )}
                {busy && <p role="status">Saving study…</p>}
                {error != null && <p role="alert">{message(error)}</p>}
                {notice && <p role="status">{notice}</p>}
                {api.pending && (
                  <p role="alert">
                    Command outcome is uncertain. Close this editor and check the original command
                    before making more changes.
                  </p>
                )}
              </ActionDialog>
            );
            return saved ? (
              <ApproachReader
                source={{ kind: 'saved', record: saved }}
                api={api}
                studyId={study.study_id}
                onOpenModel={(id) =>
                  navigate(() => void openLink({ study: study.study_id, model: id, view: 'model' }))
                }
                questionActions={
                  <>
                    {editStudy}
                    <Button
                      ref={approachEntry}
                      onClick={() =>
                        navigate(() => void openLink({ study: study.study_id, view: 'approach' }))
                      }
                    >
                      Edit approach
                    </Button>
                  </>
                }
                findings={(slot) => (
                  <ApproachFindings
                    {...slot}
                    api={api}
                    studyId={study.study_id}
                    saved={saved}
                    onOpen={(target) =>
                      navigate(() => {
                        ctx.setApproachReturn({ study: study.study_id, view: 'overview' });
                        void openLink(target);
                      })
                    }
                  />
                )}
              />
            ) : (
              <Panel className="study-about overview-card" label="About this study">
                <SectionHeader level={2} title="About this study" actions={editStudy} />
                {question}
                <div className="approach-overview-entry">
                  {details}
                  <Button
                    ref={approachEntry}
                    disabled={version === undefined}
                    onClick={() =>
                      navigate(
                        () =>
                          void openLink({
                            study: study.study_id,
                            view: 'approach',
                            approach: version ?? undefined,
                          }),
                      )
                    }
                  >
                    View modeling approach
                  </Button>
                </div>
              </Panel>
            );
          }}
        </OverviewStudyQuestion>
      </div>
    </>
  );
}

/** The study metadata edited from Overview: saved after the model editors, before evidence. */
function overviewGuard({ study, metadataDirty, saveMetadata, setCurrentStudy }: GuardContext) {
  return [
    {
      name: 'metadata',
      shown: metadataDirty,
      guard: () => ({
        dirty: metadataDirty,
        save: async () => {
          await saveMetadata();
          return true;
        },
        discard: () => {
          if (study) setCurrentStudy(study);
        },
      }),
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
