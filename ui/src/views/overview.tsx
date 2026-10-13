import { OverviewStudyQuestion } from '../ApproachAssumptions';
import { message } from '../api';
import { Button, Panel, TextArea, TextInput } from '../design';
import { OverviewRecords } from '../OverviewRecords';
import { ActionDialog, SectionHeader } from '../Presentation';
import { resourceViewLink } from '../workspaceModel';
import type { GuardContext, ViewContext, ViewEntry } from './registry';

/** Overview: the study question, the study's About card with its Edit study dialog and the
 * recent records. */
function renderOverview(ctx: ViewContext) {
  const { view, api, study, busy, error, notice, navigate, openLink, perform } = ctx;
  const { metadata, setMetadata, metadataDirty, saveMetadata, approachEntry } = ctx;
  if (view !== 'overview') return null;
  return (
    <>
      <OverviewStudyQuestion
        key={`${api.actor}:${study.study_id}`}
        api={api}
        studyId={study.study_id}
      />
      <div className="overview-grid">
        <Panel className="study-about overview-card" label="About this study">
          <SectionHeader
            level={2}
            title="About this study"
            actions={
              <ActionDialog title="Edit study" label="Edit">
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
                    Description
                    <TextArea
                      aria-label="Description"
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
            }
          />
          <p className="context-copy">
            <strong>Description: </strong>
            {study.description || 'No description yet.'}
          </p>
          <div className="approach-overview-entry">
            <Button
              ref={approachEntry}
              onClick={() =>
                navigate(() => void openLink({ study: study.study_id, view: 'approach' }))
              }
            >
              View modeling approach
            </Button>
          </div>
        </Panel>
        <OverviewRecords
          key={`${api.actor}:${study.study_id}`}
          api={api}
          study={study}
          onOpen={(target) => navigate(() => void openLink(target))}
        />
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
