import { EvidencePanel } from '../EvidencePanel';
import { resourceViewLink } from '../workspaceModel';
import type { GuardContext, ViewContext, ViewEntry } from './registry';

/** Evidence: the study's assumptions index and sources, with the evidence of the displayed
 * model version, configuration or run. Owner links open through guarded navigation. */
function renderEvidence(ctx: ViewContext) {
  const { view, api, study, revision, configInspection, configuration, runInspection } = ctx;
  const { evidence, setEvidence, evidenceSlot, navigate, openLink } = ctx;
  const snapshot =
    revision ??
    configInspection?.snapshot ??
    configuration?.model_snapshot ??
    runInspection?.history?.model_snapshot;
  const recorded =
    configuration?.configuration ??
    configInspection?.saved?.configuration ??
    runInspection?.history?.configuration;
  // prettier-ignore
  return <div hidden={view !== 'evidence'}>{view === 'evidence' && <EvidencePanel
    key={study.study_id} api={api} studyId={study.study_id} snapshot={snapshot}
    configuration={recorded} runId={runInspection?.run_id} records={evidence}
    onRecords={setEvidence} onHandle={evidenceSlot.receive}
    onOpen={target => navigate(() => void openLink(target))} />}</div>;
}

/** The evidence editor, saved after the study metadata. */
function evidenceGuard({ evidenceSlot }: GuardContext) {
  return [evidenceSlot.entry('evidence')];
}

export const evidenceView: ViewEntry<'evidence'> = {
  name: 'evidence',
  placement: { kind: 'tab', label: 'Evidence', position: 5 },
  parseLink: resourceViewLink,
  render: renderEvidence,
  guard: evidenceGuard,
  available: () => true,
};
