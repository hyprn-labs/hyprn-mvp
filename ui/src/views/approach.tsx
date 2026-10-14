import { ApproachPanel } from '../ApproachPanel';
import { Button } from '../design';
import { isResourceIdentity, type WorkspaceLink } from '../workspaceModel';
import type { GuardContext, ViewContext, ViewEntry } from './registry';

/** An approach link names at most an approach version and a case of that exact version. */
function approachLink(link: WorkspaceLink, query: URLSearchParams) {
  if (link.model || link.revision || link.configuration || link.run) {
    throw new Error('This approach link has conflicting resource context.');
  }
  const caseId = query.get('case');
  if (caseId !== null) {
    // A case identity is never global: it must be qualified by its exact approach version.
    if (!link.approach) throw new Error('This case link does not name an approach version.');
    if (caseId !== 'none' && !isResourceIdentity(caseId)) {
      throw new Error('This workspace link has an invalid resource identity.');
    }
    link.case = caseId;
  }
}

/** The modeling approach, reached from Overview and from approach links. On the other views
 * of the same study it renders the explicit return to the approach that was left. */
function renderApproach(ctx: ViewContext) {
  const { view, api, study, approach, navigate, perform, openLink, link } = ctx;
  const { approachReturn, setApproachReturn, caseReturn, returnFromCase } = ctx;
  const { requestedCase, setRequestedCase, requestedApproach, setRequestedApproach } = ctx;
  const { approachEditingRef, setApproachEditing, approachEditEpoch, setApproachHandoff } = ctx;
  const { returnToApproachEntry, newConfiguration } = ctx;
  return (
    <>
      {view !== 'approach' &&
        view !== approachReturn?.view &&
        approachReturn?.study === study.study_id && (
          <Button
            className="link back-link"
            onClick={() =>
              navigate(() => {
                const target = approachReturn;
                setApproachReturn(null);
                void openLink(target);
              })
            }
          >
            Return to modeling approach
          </Button>
        )}
      {view === 'approach' && caseReturn?.link.study === study.study_id && (
        <Button className="link back-link" onClick={returnFromCase}>
          {caseReturn.link.run
            ? 'Return to run'
            : caseReturn.link.view === 'runs'
              ? 'Return to run history'
              : caseReturn.link.configuration
                ? 'Return to configuration'
                : 'Return to previous page'}
        </Button>
      )}
      {view === 'approach' && (
        <ApproachPanel
          requestedCase={requestedCase}
          onCreateConfiguration={(model, selection) =>
            navigate(() => {
              setApproachReturn({
                study: study.study_id,
                view: 'approach',
                approach: selection.approach_version_id,
              });
              void perform(() => newConfiguration(model.model_id, model, selection));
            })
          }
          onOpenRecord={(target) =>
            navigate(() => {
              setApproachReturn({
                study: study.study_id,
                view: 'approach',
                approach: requestedApproach,
              });
              void openLink(target);
            })
          }
          onEditingChange={(dirty) => {
            approachEditingRef.current = dirty;
            setApproachEditing(dirty);
          }}
          onOpenModel={(id) =>
            navigate(() => void openLink({ study: study.study_id, model: id, view: 'model' }))
          }
          onHandoff={(value) =>
            navigate(() => {
              setApproachHandoff(value);
              void openLink({ study: value.studyId, model: value.modelId, view: 'model' });
            })
          }
          key={study.study_id + '/' + approachEditEpoch}
          api={api}
          controller={approach}
          studyId={study.study_id}
          requestedVersion={requestedApproach}
          navigate={navigate}
          onSelection={(id) => {
            setRequestedApproach(id);
            const exactCase = requestedCase?.approach === id ? requestedCase : null;
            if (!exactCase) setRequestedCase(undefined);
            link({
              study: study.study_id,
              view: 'approach',
              ...(id ? { approach: id } : {}),
              ...(id && exactCase ? { case: exactCase.id } : {}),
            });
          }}
          onBack={() =>
            navigate(() => {
              returnToApproachEntry.current = true;
              void openLink({ study: study.study_id, view: 'overview' });
            })
          }
        />
      )}
    </>
  );
}

/** The open approach editors: a nested editor that must be applied or discarded first, then
 * the shared approach draft, saved from its study reading and model editing views. */
function approachGuard(ctx: GuardContext) {
  const { view, approach, approachEditing, approachEditingRef } = ctx;
  const { setApproachEditing, setApproachEditEpoch } = ctx;
  return [
    {
      name: 'approach-editor',
      blocking: true,
      shown: approachEditing,
      guard: () => ({
        dirty: approachEditingRef.current,
        save: async () => !approachEditingRef.current,
        discard: () => {
          approachEditingRef.current = false;
          setApproachEditing(false);
          setApproachEditEpoch((n) => n + 1);
        },
      }),
      reset: () => {
        approachEditingRef.current = false;
        setApproachEditing(false);
      },
    },
    {
      name: 'approach',
      shown: approach.handle.dirty,
      guard: () => approach.handle,
      skip: () => view !== 'approach' && view !== 'overview' && view !== 'model',
      reset: () => approach.clear(),
    },
  ];
}

export const approachView: ViewEntry<'approach'> = {
  name: 'approach',
  placement: { kind: 'link', tab: 'overview', breadcrumb: 'Overview / Modeling approach' },
  parseLink: approachLink,
  render: renderApproach,
  guard: approachGuard,
  available: () => true,
};
