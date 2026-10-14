import { useUnitCatalog } from './UnitEditor';
import { unresolvedModelUnits } from './unitLabels';
import type { ApproachSelection1 } from './contract';
import type { ApproachHandoff } from './ApproachAssumptions';
import { Button, Panel, TextInput, DialogFrame, Tabs, ActionIcon, StatusTag } from './design';
import { Fragment, useEffect, useRef, useState } from 'react';
import { ApiError, HyprnMvpApi, message } from './api';
import type { ModelDraftRead4, ModelRevisionRead4, Study, PublicRun, PublicRunDetail, RevisionSummary, EvidenceRecord, FrozenConfigurationRead7, ConfigurationRevision, ModifiedRunSeedRead6 } from './api';
import { CaseNavigation, cleanGuard, discardGuards, guardsBlocked } from './workspaceModel';
import { guardsDirty, guardsShown, saveGuards, useGuardSlot } from './workspaceModel';
import { workspaceHash } from './workspaceModel';
import type { CaseNavigationTarget, GuardEntry, WorkspaceContext } from './workspaceModel';
import type { WorkspaceLink, WorkspaceView, Selection } from './workspaceModel';
import { retainedApproachVersion, retainedMethodLinks, useLatestMethodLinks, type MethodLink } from './modelMethods';

import type { EditorHandle } from './ModelEditor';
import type { ConfigurationHandle, ConfigurationInspection } from './ConfigurationPanel';
import type { VariableContext } from './VariablesTable';
import { runPending, emptyRunFilters, type RunFilters } from './RunPanel';
import { ComparisonView } from './ComparisonView';
import { ApproachController, useApproachController } from './ApproachController';
import { forgetApproachReading, showMethodStep } from './ApproachPanel';
import { ModelController } from './ModelController';
import { breadcrumbOf, parseViewLink, selectedTab, studyTabs } from './views/registry';
import { viewGuards, viewRegistry } from './views/registry';
import type { GuardContext, ViewContext } from './views/registry';
import { AttributionChip } from './design';
import { attributionKey } from './api';
import type { AttributionEntry, AttributionIndex } from './api';
import { AttributionContext, emptyAttribution } from './attribution';
import { useAccessLoss } from './accessLoss';

type RunOrigin = { actor: string; study: string; model: string; generation: number; link: string };

/** Return focus to the exact invoking control once its host has rendered again.
 * Bounded: gives up after about two seconds without stealing focus elsewhere. */
function focusWhenReady(returnKey: string) {
  let frames = 0;
  const attempt = () => {
    const target = [...document.querySelectorAll<HTMLElement>('[data-case-return]')].find(element => element.dataset.caseReturn === returnKey && element.getClientRects().length > 0);
    if (target) { target.focus(); target.scrollIntoView({ block: 'center' }); return; }
    if (++frames < 120) requestAnimationFrame(attempt);
  };
  requestAnimationFrame(attempt);
}

/** The API refuses a reader's archive or restore (403, outcome unchanged); say so plainly. */
function archiveRefusal(error: unknown): never {
  if (error instanceof ApiError && error.detail.code === 'forbidden') throw new Error('Only owners and writers of this study can archive or restore it. Nothing was changed.');
  throw error;
}

export function Workspace() {
  const workspaceRoot = useRef<HTMLElement>(null);
  const [modelActionHost, setModelActionHost] = useState<HTMLDivElement | null>(null);
  const [resourceActions, setResourceActions] = useState<HTMLDivElement | null>(null);
  const api = useRef(new HyprnMvpApi()).current;
  const approach = useRef(new ApproachController(api)).current;
  const approachState = useApproachController(approach);
  const approachEditingRef=useRef(false);
  const [approachEditing, setApproachEditing] = useState(false), [approachEditEpoch,setApproachEditEpoch] = useState(0);
  const [approachHandoff, setApproachHandoff] = useState<ApproachHandoff | null>(null);
  const approachEntry = useRef<HTMLButtonElement>(null);
  const returnToApproachEntry = useRef(false);
  const [requestedApproach, setRequestedApproach] = useState<string | undefined>();
  const [, refreshPending] = useState(0);
  api.onPendingChange = () => refreshPending(n => n + 1);
  const [signedIn, setSignedIn] = useState(false); const [username, setUsername] = useState(''); const [password, setPassword] = useState('');
  const [studies, setStudies] = useState<Study[]>([]); const [study, setStudy] = useState<Study | null>(null);
  // Home: two reads (active, archived), a Studies | Archived switch and a confirmed archive.
  const [archivedStudies, setArchivedStudies] = useState<Study[]>([]); const [homeView, setHomeView] = useState<'active' | 'archived'>('active');
  const [studiesFailed, setStudiesFailed] = useState(false); const [archiveTarget, setArchiveTarget] = useState<Study | null>(null);
  const archiveDialog = useRef<HTMLDialogElement>(null), homeTabs = useRef<HTMLDivElement>(null), archiveInvoker = useRef<HTMLElement | null>(null);
  const [view, setView] = useState<WorkspaceView>('overview');
  const [page, setPage] = useState<'home' | 'new-study' | 'profile' | 'study'>('home');
  const [creatingModel, setCreatingModel] = useState(false);
  const creationGuidance = useUnitCatalog(api, creatingModel ? study?.study_id ?? '' : '', 'new-model');
  const [choosingConfiguration, setChoosingConfiguration] = useState(false);
  const [modified, setModified] = useState<{seed: ModifiedRunSeedRead6; source: ConfigurationRevision} | null>(null);
  const [initialConfigurationApproach,setInitialConfigurationApproach]=useState<ApproachSelection1|null>(null);
  const [approachReturn,setApproachReturn]=useState<WorkspaceLink|null>(null);
  // Exact case navigation keeps its origin (run, run history or configuration),
  // the invoking control and the run list filters for an explicit return.
  const [caseReturn,setCaseReturn]=useState<{link:WorkspaceLink;key:string}|null>(null);
  // The exact case named by the current approach link, qualified by its approach version.
  const [requestedCase,setRequestedCase]=useState<{approach?:string;id:string;token:number}|undefined>();
  const caseToken=useRef(0);
  const [runFilters,setRunFilters]=useState<RunFilters>(emptyRunFilters);
  const [initialConfigurationRevision, setInitialConfigurationRevision] = useState<ModelRevisionRead4 | null>(null);
  const [runListEpoch, setRunListEpoch] = useState(0);
  const [selection, setSelection] = useState<Selection>({ kind: 'none' });
  const [context, setContext] = useState<WorkspaceContext | null>(null);
  const [configInspection, setConfigInspection] = useState<ConfigurationInspection | null>(null);
  const [sourceReturn, setSourceReturn] = useState<{ view: WorkspaceView; link: string; context: WorkspaceContext | null; selection: Selection; run: PublicRun | null; runId: string; output: { instance_id: string; port_id: string } } | null>(null);
  const [runInspection, setRunInspection] = useState<PublicRunDetail | null>(null);
  const [revision, setRevision] = useState<ModelRevisionRead4 | null>(null);
  const [revisions, setRevisions] = useState<RevisionSummary[]>([]);
  const [configuration, setConfiguration] = useState<FrozenConfigurationRead7 | null>(null);
  const [configurations, setConfigurations] = useState<FrozenConfigurationRead7[]>([]);
  const [evidence, setEvidence] = useState<EvidenceRecord[]>([]);
  const evidenceSlot = useGuardSlot(cleanGuard);
  const [filter, setFilter] = useState('');
  const currentLink = useRef('');
  const [models, setModels] = useState<Array<{ model_id: string; name: string }>>([]); const [model, setModel] = useState<ModelDraftRead4 | null>(null);
  const [newStudy, setNewStudy] = useState(''); const [newModel, setNewModel] = useState(''); const [template, setTemplate] = useState<'empty' | 'two_component_example'>('empty');
  const [metadata, setMetadata] = useState({ name: '', description: '', boundary: '' });
  const [busy, setBusy] = useState(false); const [loading, setLoading] = useState(false); const [error, setError] = useState<unknown>(null);
  const [notice, setNotice] = useState('');
  const editorSlot = useGuardSlot<EditorHandle>(cleanGuard);
  const pendingCopy = useRef<{ configuration: ConfigurationRevision; snapshot: ModelRevisionRead4 } | null>(null);
  const configurationSlot = useGuardSlot<ConfigurationHandle>(() => ({ ...cleanGuard(), copy: () => {} }));
  const portPasteSlot = useGuardSlot(cleanGuard);
  const [submitted, setSubmitted] = useState<PublicRun | null>(null); const [activeRun, setActiveRun] = useState(false);
  const submittingOrigin = useRef<{ command: string; scope: RunOrigin } | null>(null);
  const [resolvedRuns, setResolvedRuns] = useState<Array<{ actor: string; study: string; run: string }>>([]);
  const transition = useRef<null | (() => void)>(null); const returnFocus = useRef<HTMLElement | null>(null);
  const dialog = useRef<HTMLDialogElement>(null); const generation = useRef(0);
  const modelVersions = useRef(new ModelController(api, generation)).current;
  // Who wrote what: the open study's attribution index, read once per open study and provided
  // to the study views; Home's marks of the studies an agent created. Both are empty until
  // their read answers and are cleared when the session or access to the study ends.
  const attributionStudy = useRef<string | null>(null);
  const attributionGeneration = useRef(0);
  const [attribution, setAttribution] = useState<{ study: string; index: AttributionIndex }>();
  const [createdStudies, setCreatedStudies] =
    useState<ReadonlyMap<string, AttributionEntry>>(emptyAttribution);
  useEffect(() => () => { generation.current++; approach.dispose(); }, [approach]);
  useEffect(() => { if (view === 'overview' && study && returnToApproachEntry.current) { approachEntry.current?.focus(); returnToApproachEntry.current = false; } }, [view, study]);
  const metadataDirty = !!study && (metadata.name !== study.name || metadata.description !== study.description || metadata.boundary !== study.boundary);
  // One ordered unsaved-changes list. Its order is the save and discard order; it also
  // drives the page dirty state, navigate(), the dialog and clearEditor. A view's editor
  // adds its entry through the view's registry guard; the registry fixes the save order.
  // Metadata errors propagate and keep the dialog open.
  const guardContext: GuardContext = {
    view, study, approach, approachEditing, approachEditingRef, setApproachEditing,
    setApproachEditEpoch, portPasteSlot, editorSlot, metadataDirty, saveMetadata,
    setCurrentStudy, evidenceSlot, configurationSlot,
  };
  const guards: GuardEntry[] = viewGuards(guardContext);
  const dirty = guardsShown(guards);
  useEffect(() => { const unload = (e: BeforeUnloadEvent) => { if (dirty) { e.preventDefault(); e.returnValue = ''; } }; window.addEventListener('beforeunload', unload); return () => window.removeEventListener('beforeunload', unload); }, [dirty]);
  function setCurrentStudy(value: Study) { setStudy(value); setStudies(previous => previous.some(s => s.study_id === value.study_id) ? previous.map(s => s.study_id === value.study_id ? value : s) : [value, ...previous]); setMetadata({ name: value.name, description: value.description, boundary: value.boundary }); }
  function clearEditor() { guards.forEach(guard => guard.reset?.()); setModified(null); setSourceReturn(null); setInitialConfigurationRevision(null);setInitialConfigurationApproach(null); setChoosingConfiguration(false); pendingCopy.current = null; setConfigInspection(null); setRunInspection(null); setSelection({ kind: 'none' }); setModel(null); setRevision(null); setRevisions([]); setConfiguration(null); setContext(null); }
  // Session end also forgets navigation return state, run filters, the requested
  // case and approach reading positions; none may outlive the session that read them.
  function clearSession() { setApproachHandoff(null); setCaseReturn(null); setRunFilters(emptyRunFilters); setRequestedCase(undefined); setRequestedApproach(undefined); setApproachReturn(null); forgetApproachReading(); generation.current++; setResolvedRuns([]); submittingOrigin.current = null; clearEditor(); setStudies([]); setArchivedStudies([]); setHomeView('active'); setStudiesFailed(false); setArchiveTarget(null); archiveDialog.current?.close(); setStudy(null); setModels([]); setConfigurations([]); setEvidence([]); setSubmitted(null); setActiveRun(false); setMetadata({ name: '', description: '', boundary: '' }); setNewStudy(''); setNewModel(''); setFilter(''); setNotice(''); setError(null); setLoading(false); setPage('home'); setCreatingModel(false); setSignedIn(false); }
  api.onAuthorizationLoss = clearSession;
  useAccessLoss(api, study?.study_id, (change) => {
    attributionGeneration.current++;
    attributionStudy.current = null;
    setAttribution(undefined);
    if (change.kind === 'signed-out') setCreatedStudies(emptyAttribution);
  });
  async function loadAttribution(sid: string) {
    const token = ++attributionGeneration.current;
    attributionStudy.current = sid;
    setAttribution(undefined);
    const fence = api.fence({ studyId: sid });
    try {
      const index = await api.attribution(sid, fence.signal);
      if (fence.valid() && token === attributionGeneration.current) {
        setAttribution({ study: sid, index });
      }
    } catch (e) {
      // A confirmed denial ends access to the study; any other failure leaves the index empty.
      if (token === attributionGeneration.current) await api.readFailed(e, fence);
    } finally {
      fence.done();
    }
  }
  async function loadCreatedStudies(token: number) {
    const fence = api.fence();
    setCreatedStudies(emptyAttribution);
    try {
      const created = await api.createdStudies(fence.signal);
      if (fence.valid() && token === generation.current) setCreatedStudies(created);
    } catch (e) {
      // Home stays usable without the marks; no row is marked from a failed read.
      await api.readFailed(e, fence);
    } finally {
      fence.done();
    }
  }
  function link(value: WorkspaceLink) { currentLink.current = workspaceHash(value); window.history.replaceState(null, '', currentLink.current); }
  async function openPage(next: 'home' | 'new-study' | 'profile') {
    const token = ++generation.current, actor = api.actor;
    clearEditor(); setStudy(null); setModels([]); setConfigurations([]); setEvidence([]); setSubmitted(null); setActiveRun(false); setCreatingModel(false); setPage(next); setError(null); setNotice(''); setLoading(next === 'home'); setStudiesFailed(false);
    currentLink.current = next === 'home' ? '#home' : next === 'profile' ? '#profile' : '#new-study';
    window.history.replaceState(null, '', currentLink.current);
    attributionStudy.current = null;
    attributionGeneration.current++;
    if (next !== 'home') return;
    void loadCreatedStudies(token);
    try { const [records, archived] = await Promise.all([api.studies(), api.archivedStudies()]); if (token === generation.current && actor === api.actor) { setStudies(records); setArchivedStudies(archived); } }
    catch (e) { if (token === generation.current && actor === api.actor) { setError(e); setStudiesFailed(true); } }
    finally { if (token === generation.current && actor === api.actor) setLoading(false); }
  }
  /** Re-read both Home lists after an archive command; the lists are never edited locally. */
  async function reloadStudies() {
    const token = generation.current, actor = api.actor;
    const [records, archived] = await Promise.all([api.studies(), api.archivedStudies()]);
    if (token === generation.current && actor === api.actor) { setStudies(records); setArchivedStudies(archived); setStudiesFailed(false); }
  }
  function askArchive(value: Study) {
    archiveInvoker.current = document.activeElement as HTMLElement | null;
    setArchiveTarget(value); archiveDialog.current?.showModal(); archiveDialog.current?.querySelector<HTMLButtonElement>('[data-safe-choice]')?.focus();
  }
  // Archive and restore are study-wide presentation state: idempotent commands with
  // receipts; an uncertain outcome is held as the pending command and checked like any other.
  function confirmArchive() {
    const target = archiveTarget; archiveDialog.current?.close(); if (!target) return;
    void perform(async () => {
      const actor = api.actor;
      await api.archiveStudy(target.study_id, { command_id: crypto.randomUUID() }).catch(archiveRefusal);
      if (actor !== api.actor) return;
      await reloadStudies(); setNotice(`“${target.name}” archived. Restore it from Archived.`);
      homeTabs.current?.querySelector<HTMLButtonElement>('[aria-selected=true]')?.focus();
    });
  }
  function restoreStudy(value: Study) {
    void perform(async () => {
      const actor = api.actor;
      await api.restoreStudy(value.study_id, { command_id: crypto.randomUUID() }).catch(archiveRefusal);
      if (actor !== api.actor) return;
      await reloadStudies(); setNotice(`“${value.name}” restored to Studies.`);
      homeTabs.current?.querySelector<HTMLButtonElement>('[aria-selected=true]')?.focus();
    });
  }
  function currentModel(value: ModelDraftRead4) { setModel(value); setRevision(null); setContext({ actor_id: api.actor, study_id: value.study_id, view: 'model', kind: 'draft', model_id: value.model_id, draft_revision: value.draft_revision, snapshot: value }); setModels(previous => previous.map(m => m.model_id === value.model_id ? { model_id: value.model_id, name: value.name } : m)); }
  async function perform(action: () => Promise<void>) {
    if (busy) return; setBusy(true); setError(null);
    try { await action(); } catch (e) { setError(e); } finally { setBusy(false); }
  }
  async function viewSourceResult(runId: string, output: { instance_id: string; port_id: string }) {
    if (!study) return;
    const token = generation.current, actor = api.actor;
    const detail = await api.run(study.study_id, runId);
    if (token !== generation.current || actor !== api.actor) return;
    setSourceReturn({ view, link: currentLink.current, context, selection, run: submitted, runId, output });
    setSubmitted(detail); setView('runs'); setSelection({ kind: 'variable', ...output });
    link({ study: study.study_id, view: 'runs', run: runId });
  }
  function returnToConfiguration() {
    if (!sourceReturn) return;
    setView(sourceReturn.view); setContext(sourceReturn.context); setSelection(sourceReturn.selection); setSubmitted(sourceReturn.run);
    currentLink.current = sourceReturn.link; window.history.replaceState(null, '', sourceReturn.link);
    setSourceReturn(null);
  }
  function navigate(action: () => void) {
    if (view === 'approach' && (approach.busy || !!api.pending || approachState.status === 'uncertain')) return;
    const proceed = () => { generation.current++; action(); };
    if (!guardsDirty(guards)) { proceed(); return; }
    returnFocus.current = document.activeElement as HTMLElement;
    transition.current = proceed; dialog.current?.showModal(); dialog.current?.querySelector<HTMLButtonElement>('[data-safe-choice]')?.focus();
  }
  function closeDialog() { dialog.current?.close(); returnFocus.current?.focus(); }
  function receiveRun(run: PublicRun, origin: Pick<RunOrigin, 'actor' | 'study'>, original?: RunOrigin | null) {
    if (origin.actor !== api.actor) return;
    if (original && original.actor === origin.actor && original.study === origin.study && original.generation === generation.current && original.link === currentLink.current) {
      setSubmitted(run); setActiveRun(runPending(run)); setView('runs'); link({ study: origin.study, view: 'runs', run: run.run_id });
    } else {
      // Navigation notices retain identities only; public history owns the run.
      setResolvedRuns(previous => [...previous.filter(item => !(item.actor === origin.actor && item.study === origin.study && item.run === run.run_id)), { ...origin, run: run.run_id }]);
    }
  }
  async function submitConfiguration(configurationId: string) {
    const modelId = model?.model_id ?? modified?.seed.model_snapshot.model_id ?? configuration?.model_snapshot.model_id;
    if (!study || !modelId) return;
    const origin: RunOrigin = { actor: api.actor, study: study.study_id, model: modelId, generation: generation.current, link: currentLink.current };
    try { receiveRun(await api.submitRun(origin.study, configurationId), origin, origin); }
    catch (error) {
      const pending = api.pending;
      if (origin.actor === api.actor && pending?.study === origin.study && pending.category === 'run' && 'configuration_revision_id' in pending.body && pending.body.configuration_revision_id === configurationId) submittingOrigin.current = { command: pending.body.command_id, scope: origin };
      throw error;
    }
  }
  async function reconcileCommand() {
    if (view === 'approach' && approach.ownsPendingCommand) { await approach.reconcile(); return; }
    const pending = api.pending, actor = api.actor;
    const original = submittingOrigin.current?.command === pending?.body.command_id ? submittingOrigin.current?.scope : null;
    const receipt = await api.reconcile();
    if (actor !== api.actor) return;
    if (pending?.category === 'run' && pending.study && receipt?.result && 'run_id' in receipt.result) receiveRun(receipt.result, { actor, study: pending.study }, original);
    if (pending?.category === 'study_archive' && page === 'home') { await reloadStudies(); setNotice(`Original command: ${receipt?.state ?? (api.retryReady ? 'not found; retry is available' : 'no pending command')}. Study lists reloaded.`); return; }
    setNotice(`Original command: ${receipt?.state ?? (api.retryReady ? 'not found; retry is available' : 'no pending command')}. Reload the study after reviewing unsaved edits.`);
  }
  async function saveMetadata() {
    if (!study || !metadataDirty) return;
    const saved = await api.updateStudy(study, metadata); setCurrentStudy(saved);
    setStudies(studies.map(s => s.study_id === saved.study_id ? saved : s)); setNotice('Study saved');
  }
  async function openLink(target: WorkspaceLink, keepCaseReturn = false) {
    if (!target.study) return;
    if (!keepCaseReturn) setCaseReturn(null);
    if (study?.study_id !== target.study) setRunFilters(emptyRunFilters);
    const sid = target.study, token = ++generation.current;
    clearEditor(); setPage('study'); setCreatingModel(false); setModels([]); setStudy(null); setSubmitted(null); setActiveRun(false); setConfigurations([]); setEvidence([]); setView(target.view); setLoading(true); setError(null); link(target);
    if (attributionStudy.current !== sid) void loadAttribution(sid);
    try {
      const current = await api.study(sid);
      if (token !== generation.current) return;
      setCurrentStudy(current);
      setContext({ actor_id: api.actor, study_id: sid, view: target.view, kind: 'study' });
      // Retained application records never require the mutable model service.
      if (target.view === 'approach') {
        setRequestedApproach(target.approach);
        setRequestedCase(target.case ? { approach: target.approach, id: target.case, token: ++caseToken.current } : undefined);
        await approach.open(sid, target.approach);
      } else if (target.view === 'overview') {
        // Overview and approach are application-owned; no mutable model read.
      } else if (target.run) {
        const run = await api.run(sid, target.run); if (token !== generation.current) return;
        setSubmitted(run); setActiveRun(runPending(run));
        const snapshot = run.history?.model_snapshot ?? undefined;
        setContext({ actor_id: api.actor, study_id: sid, view: 'runs', kind: 'run', run_id: run.run_id, snapshot, model_id: snapshot?.model_id, model_revision_id: snapshot?.model_revision_id, configuration_revision_id: run.history?.configuration?.configuration_revision_id });
      } else if (target.configuration) {
        const frozen = await api.configuration(sid, target.configuration); if (token !== generation.current) return;
        setConfiguration(frozen); setContext({ actor_id: api.actor, study_id: sid, view: 'configurations', kind: 'configuration', model_id: frozen.model_snapshot.model_id, model_revision_id: frozen.model_snapshot.model_revision_id, configuration_revision_id: frozen.configuration.configuration_revision_id, snapshot: frozen.model_snapshot });
      } else if (target.view === 'runs') {
        setRunListEpoch(value => value + 1);
        // RunPanel independently reads the application history API.
      } else if (target.view === 'evidence') {
        const records = await api.evidence(sid); if (token !== generation.current) return; setEvidence(records);
      } else if (target.view === 'configurations' && !target.model) {
        const records = await api.configurations(sid); if (token !== generation.current) return; setConfigurations(records);
      } else {
        const associations = await api.models(sid); if (token !== generation.current) return;
        setModels(associations.map(a => ({ model_id: a.model_id, name: a.model_id })));
        if (target.model) {
          if (target.revision) {
            const exact = await api.revision(sid, target.model, target.revision); if (token !== generation.current) return;
            setRevision(exact); const first = exact.instances.find(i => i.instance_id !== exact.root_instance_id); if (first) setSelection({ kind: 'instance', instance_id: first.instance_id }); setContext({ actor_id: api.actor, study_id: sid, view: 'model', kind: 'revision', model_id: exact.model_id, model_revision_id: exact.model_revision_id, snapshot: exact });
          } else {
            const draft = await api.model(sid, target.model); if (token !== generation.current) return; currentModel(draft); const first = draft.instances.find(i => i.instance_id !== draft.root_instance_id); if (first) setSelection({ kind: 'instance', instance_id: first.instance_id });
          }
          const summaries = await api.revisions(sid, target.model); if (token !== generation.current) return; setRevisions(summaries);
          if (target.revision) { const resolved = await api.assumptionEvidence(sid, target.model, { model_revision_id: target.revision }); if (token !== generation.current) return; setEvidence(resolved.evidence); }
        } else {
          const names = await Promise.allSettled(associations.map(async a => { const draft = await api.model(sid, a.model_id); return { model_id: a.model_id, name: draft.name }; }));
          if (token !== generation.current) return;
          setModels(associations.map((a, i) => names[i].status === 'fulfilled' ? (names[i] as PromiseFulfilledResult<{ model_id: string; name: string }>).value : { model_id: a.model_id, name: a.model_id + ' · name unavailable' }));
        }
      }
      if (token === generation.current) link(target);
    } catch (e) { if (token === generation.current) setError(e); }
    finally { if (token === generation.current) setLoading(false); }
  }
  /** Open the exact approach version and case named by a retained pin. */
  function openCase(target: CaseNavigationTarget, returnKey: string) {
    if (!study) return;
    const sid = study.study_id;
    let origin: WorkspaceLink | null = null;
    try { origin = parseViewLink(currentLink.current); } catch { origin = null; }
    navigate(() => {
      setCaseReturn(origin?.study === sid ? { link: origin, key: returnKey } : null);
      void openLink({ study: sid, view: 'approach', approach: target.approach_version_id, case: target.case_id ?? 'none' }, true);
    });
  }
  function returnFromCase() {
    if (!caseReturn) return;
    const target = caseReturn;
    navigate(() => { setCaseReturn(null); void openLink(target.link).then(() => focusWhenReady(target.key)); });
  }
  async function chooseStudy(sid: string) { await openLink({ study: sid, view: 'overview' }); }
  async function chooseModel(mid: string) {
    if (!study) return;
    await openLink({ study: study.study_id, model: mid, view: 'model' });
  }
  function createModified(seed: ModifiedRunSeedRead6, source: ConfigurationRevision) {
    if (!study || source.study_id !== study.study_id || source.digest !== seed.source_configuration_digest || source.model_revision_id !== seed.model_snapshot.model_revision_id) throw new Error("The modified run's origin does not match this source run.");
    clearEditor(); setModified({seed,source}); setInitialConfigurationRevision(seed.model_snapshot); setView('configurations');
    setContext({actor_id:api.actor, study_id:study.study_id, view:'configurations',kind:'revision',model_id:source.model_id,model_revision_id:source.model_revision_id,snapshot:seed.model_snapshot});
    link({study:study.study_id,view:'configurations'});
  }
  async function copyRunConfiguration(config: ConfigurationRevision, snapshot: ModelRevisionRead4) {
    if (!study || config.study_id !== study.study_id || config.model_id !== snapshot.model_id) throw new Error('This configuration does not belong to this study and model.');
    const token = ++generation.current;
    const draft = model?.model_id === config.model_id ? model : await api.model(study.study_id, config.model_id);
    if (token !== generation.current) return;
    if (model?.model_id === config.model_id) configurationSlot.current().copy(config, snapshot);
    else { pendingCopy.current = { configuration: config, snapshot }; currentModel(draft); setModels(previous => previous.some(m => m.model_id === draft.model_id) ? previous : [...previous, { model_id: draft.model_id, name: draft.name }]); }
    setConfiguration(null); setSelection({ kind: 'none' }); setView('configurations');
    setContext({ actor_id: api.actor, study_id: study.study_id, view: 'configurations', kind: 'draft', model_id: draft.model_id, draft_revision: draft.draft_revision, snapshot: draft });
    link({ study: study.study_id, view: 'configurations', model: draft.model_id });
  }
  async function newConfiguration(modelId: string, exact?: ModelRevisionRead4, approachSelection?:ApproachSelection1) {
    if (!study) return;
    const sid = study.study_id, token = ++generation.current, actor = api.actor;
    const draft = model?.model_id === modelId ? model : await api.model(sid, modelId);
    if (token !== generation.current || actor !== api.actor) return;
    const unresolved = unresolvedModelUnits(exact ?? draft);
    if (unresolved.length) throw new Error(unresolved.map(issue => `${issue.component} · ${issue.quantity}: units are not specified. View quantity to resolve them.`).join('\n'));
    const recorded = exact ?? await api.commitModel(draft);
    if (token !== generation.current || actor !== api.actor) return;
    clearEditor(); currentModel(draft); setInitialConfigurationRevision(recorded);setInitialConfigurationApproach(approachSelection??null); setView('configurations');
    setContext({ actor_id: actor, study_id: sid, view: 'configurations', kind: 'draft', model_id: modelId, snapshot: draft, draft_revision: draft.draft_revision });
    link({ study: sid, model: modelId, view: 'configurations' });
  }
  async function chooseConfigurationModel() {
    if (!study) return;
    const token = generation.current, sid = study.study_id;
    const associations = await api.models(sid);
    const entries = await Promise.all(associations.map(a => api.model(sid, a.model_id)));
    if (token !== generation.current) return;
    setModels(entries.map(m => ({ model_id: m.model_id, name: m.name }))); setChoosingConfiguration(true);
  }
  function chooseView(next: WorkspaceView) {
    if (!study) return;
    navigate(() => {
      setCreatingModel(false);
      if (next === 'configurations' || next === 'runs') { void openLink({ study: study.study_id, view: next }); return; }
      if ((next === 'model' || next === 'overview') && !model && !revision) { void openLink({ study: study.study_id, view: next }); return; }
      setView(next); setContext(previous => next === 'overview' ? { actor_id: api.actor, study_id: study.study_id, view: next, kind: 'study' } : previous ? { ...previous, view: next } : previous);
      link({ study: study.study_id, view: next, ...(next === 'model' ? { model: model?.model_id ?? revision?.model_id, revision: revision?.model_revision_id } : {}) });
    });
  }
  useEffect(() => {
    const changed = () => {
      if (!signedIn) return;
      const wanted = window.location.hash;
      window.history.replaceState(null, '', currentLink.current || window.location.pathname);
      navigate(() => {
        try {
          const value = parseViewLink(wanted);
          if (value) void openLink(value);
          else {
            const next = wanted === '#profile' ? 'profile'
              : wanted === '#new-study' ? 'new-study' : 'home';
            void openPage(next);
          }
        } catch (e) { setError(e); }
      });
    };
    window.addEventListener('hashchange', changed); return () => window.removeEventListener('hashchange', changed);
  });
  const homeList = homeView === 'archived' ? archivedStudies : studies;
  const visibleStudies = homeList.filter(s => `${s.name} ${s.description} ${s.study_id}`.toLocaleLowerCase().includes(filter.toLocaleLowerCase()));
  const selectedModel = model?.model_id ?? revision?.model_id ?? '';
  const displayedSnapshot = view === 'model' ? revision ?? model : view === 'configurations' ? configuration?.model_snapshot ?? configInspection?.snapshot ?? model : view === 'runs' ? runInspection?.history?.model_snapshot : null;
  const variableContext: VariableContext = view === 'runs' && runInspection?.history ? { kind: 'run', history: runInspection.history } : view === 'configurations' ? configuration ? { kind: 'configuration', configuration: configuration.configuration } : configInspection?.saved && !configInspection.dirty ? { kind: 'configuration', configuration: configInspection.saved.configuration } : { kind: 'configuration_draft', inputs: configInspection?.inputs ?? [] } : { kind: 'model' };
  const frozenEvidence = view === 'runs' ? runInspection?.history?.evidence ?? [] : view === 'configurations' ? configuration?.configuration.evidence_snapshots ?? configInspection?.evidence ?? [] : evidence;
  function select(value: Selection) {
    if (value.kind === 'variable') value = { kind: 'instance', instance_id: value.instance_id };
    const currentOwner = selection.kind === 'instance' || selection.kind === 'variable' ? selection.instance_id : '';
    const nextOwner = value.kind === 'instance' ? value.instance_id : '';
    if (currentOwner === nextOwner) setSelection(value); else navigate(() => setSelection(value));
  }
  // Why each component exists: the Models page reads the latest saved approach
  // version; configurations and runs read only the exact version retained with them.
  const latestMethods = useLatestMethodLinks(api, view === 'model' ? study?.study_id : undefined, view === 'model' ? displayedSnapshot : null);
  const retainedHistory = view === 'runs' ? runInspection?.history : null;
  const methods = view === 'model' ? latestMethods : retainedMethodLinks(view === 'runs' ? retainedApproachVersion(retainedHistory?.configuration, retainedHistory && 'approach_closure' in retainedHistory ? retainedHistory.approach_closure : null)
    : view === 'configurations' && configuration ? retainedApproachVersion(configuration.configuration, 'approach_closure' in configuration ? configuration.approach_closure : null) : null, displayedSnapshot);
  function openMethodStep(link: MethodLink) {
    const version = link.approachVersionId; if (!study || !version) return;
    navigate(() => { showMethodStep(study.study_id, version, link.stepId); void openLink({ study: study.study_id, view: 'approach', approach: version }); });
  }
  const studyAttribution =
    study && attribution?.study === study.study_id ? attribution.index : emptyAttribution;
  const studyCreator = study && studyAttribution.get(attributionKey('study', study.study_id));
  const creatorChip = (entry: AttributionEntry | null | undefined) =>
    entry && (
      <p>
        <AttributionChip agent={entry.agent} user={entry.user} />
      </p>
    );
  // The values the study views render from (views/registry.ts ViewContext).
  const ctx: ViewContext | null = study && {
    ...guardContext, study, api, guards, dirty, busy, loading, error, notice, generation,
    navigate, perform, openLink, link, clearEditor, select, selection, setSelection, setView,
    setContext, metadata, setMetadata, approachEntry, approachReturn, setApproachReturn,
    caseReturn, returnFromCase, requestedCase, setRequestedCase, requestedApproach,
    setRequestedApproach, approachEditEpoch, approachHandoff, setApproachHandoff,
    returnToApproachEntry, newConfiguration, models, model, setModel, revision, setRevision,
    revisions, selectedModel, creatingModel, setCreatingModel, creationGuidance, newModel,
    setNewModel, template, setTemplate, chooseModel, currentModel, modelVersions, setNotice,
    setRevisions, modelActionHost, setModelActionHost, setResourceActions, displayedSnapshot,
    variableContext, frozenEvidence, methods, openMethodStep, configuration, configurations,
    configInspection, setConfigInspection, modified, initialConfigurationRevision,
    initialConfigurationApproach, choosingConfiguration, setChoosingConfiguration,
    chooseConfigurationModel, chooseView, copyRunConfiguration, pendingCopy, evidence,
    setEvidence, submitConfiguration, viewSourceResult, sourceReturn, activeRun,
    returnToConfiguration, runFilters, setRunFilters, runListEpoch, submitted, setActiveRun,
    runInspection, setRunInspection, createModified,
  };
  return <CaseNavigation.Provider value={openCase}><main ref={workspaceRoot}>
    <header className="appbar"><p className="brand">HYPRN MVP</p>{signedIn && <>
      <nav aria-label="Main navigation">
        <Button aria-current={page === 'home' ? 'page' : undefined}
          onClick={() => navigate(() => void openPage('home'))}>Home</Button>
        {study && <><span className="breadcrumb-study">/ {study.name}</span>
          <span className="breadcrumb-section">/ {breadcrumbOf(view)}</span></>}
      </nav>
      <Button className="profile-link" aria-current={page === 'profile' ? 'page' : undefined}
        onClick={() => navigate(() => void openPage('profile'))}>Profile</Button>
    </>}</header>
    {error != null && <div role="alert"><p>{message(error)}</p>{study && !api.pending && <Button onClick={() => navigate(() => void chooseStudy(study.study_id))}>Retry study read</Button>}</div>}
    {notice && <p aria-live="polite">{notice}</p>}
    {busy && <p role="status" aria-live="polite"><StatusTag tone="running">Request in progress…</StatusTag></p>}
    {!signedIn ? <Panel className="login"><h1>Sign in to HYPRN MVP</h1>
      <form onSubmit={e => { e.preventDefault(); void perform(async () => {
        await api.login(username, password); setPassword(''); setSignedIn(true);
        const target = parseViewLink(window.location.hash);
        if (target) await openLink(target);
        else await openPage(window.location.hash === '#profile' ? 'profile'
          : window.location.hash === '#new-study' ? 'new-study' : 'home');
      }); }}>
        <fieldset disabled={busy}>
          <label>Username<TextInput autoComplete="username" required value={username}
            onChange={e => setUsername(e.target.value)} /></label>
          <label>Password<TextInput type="password" autoComplete="current-password" required
            value={password} onChange={e => setPassword(e.target.value)} /></label>
          <Button type="submit" variant="primary">Sign in</Button>
        </fieldset>
      </form></Panel> : <>
      {api.pending && <aside><p>{api.pending.category === "run" ? "Submission outcome is uncertain. Check the original command before making more changes." : "Command outcome is uncertain. Check the original command before making more changes."}</p><Button disabled={busy} onClick={() => void perform(async () => { await reconcileCommand(); })}>Check original command</Button>{api.retryReady && <Button disabled={busy} onClick={() => void perform(async () => { if (view === 'approach' && approach.ownsPendingCommand) { await approach.retryOriginal(); return; } const category = api.pending?.category; await api.retryOriginal(); if (category === 'study_archive' && page === 'home' && !api.pending) { await reloadStudies(); setNotice('Original command resolved. Study lists reloaded.'); return; } setNotice(api.pending ? 'Original command is still pending.' : 'Original command resolved. Reload the study after reviewing unsaved edits.'); })}>Retry original command</Button>}</aside>}
      {resolvedRuns.filter(item => item.actor === api.actor).map(item => <aside key={item.study + item.run}><p>Run {item.run} was accepted in study {item.study}. Your current workspace is unchanged.</p><Button onClick={() => navigate(() => void openLink({ study: item.study, view: 'runs', run: item.run }))}>Open original run</Button></aside>)}
      <div className="workspace-shell">
      <div className="workspace-content">
      {page === 'profile' && <Panel className="profile-page"><h1>Profile</h1><dl><dt>Account name</dt><dd>{username}</dd></dl><Button disabled={busy || !!api.pending} onClick={() => navigate(() => void perform(async () => { await api.logout(); clearSession(); setUsername(''); window.history.replaceState(null, '', '/ui/'); currentLink.current = ''; }))}>Sign out</Button></Panel>}
      {page === 'home' && <section className="home-page"><div className="page-heading"><div><h1>Studies</h1></div><Button variant="primary" icon={<ActionIcon name="add" />} disabled={busy || !!api.pending} onClick={() => navigate(() => void openPage('new-study'))}>New study</Button></div>
        <div className="catalogue-toolbar"><label className="study-search"><span className="sr-only">Filter loaded studies</span><TextInput placeholder="Find a study…" type="search" value={filter} onChange={e => setFilter(e.target.value)} /></label>
          <div ref={homeTabs}><Tabs variant="segmented" label="Study list" value={homeView} onChange={next => setHomeView(next === 'archived' ? 'archived' : 'active')} items={[{ id: 'active', label: 'Studies', count: loading || studiesFailed ? undefined : studies.length, tabId: 'home-tab-active', panelId: 'home-panel-active' }, { id: 'archived', label: 'Archived', count: loading || studiesFailed ? undefined : archivedStudies.length, tabId: 'home-tab-archived', panelId: 'home-panel-archived' }]} /></div></div>
        {filter && !loading && !studiesFailed && <p className="context-line home-count">{visibleStudies.length} of {homeList.length} loaded {homeView === 'archived' ? 'archived studies' : 'studies'}</p>}
        <div
          role="tabpanel"
          id="home-panel-active"
          aria-labelledby="home-tab-active"
          hidden={homeView !== 'active'}
        >
          {homeView === 'active' &&
            (loading ? (
              <p role="status" aria-busy="true">
                <StatusTag tone="running">Loading studies…</StatusTag>
              </p>
            ) : studiesFailed ? (
              <Button onClick={() => void openPage('home')}>Retry studies</Button>
            ) : (
              <Panel className="study-list" bodyClassName="catalogue-body" label="Studies">
                {visibleStudies.map((s) => (
                  <article className="study-row" key={s.study_id}>
                    <div>
                      <h2>{s.name}</h2>
                      {s.description && <p>{s.description}</p>}
                      {creatorChip(createdStudies.get(s.study_id))}
                    </div>
                    <div className="actions">
                      <Button
                        aria-label={`Open study ${s.name}`}
                        onClick={() => navigate(() => void chooseStudy(s.study_id))}
                      >
                        Open study
                      </Button>
                      <Button
                        variant="quiet"
                        aria-label={`Archive study ${s.name}`}
                        aria-haspopup="dialog"
                        disabled={busy || !!api.pending}
                        onClick={() => askArchive(s)}
                      >
                        Archive
                      </Button>
                    </div>
                  </article>
                ))}
                {!visibleStudies.length && (
                  <p className="empty-state">
                    {studies.length
                      ? 'No studies match this filter.'
                      : archivedStudies.length
                        ? 'No studies. Archived studies are listed under Archived.'
                        : 'No studies yet. Create a study to start building a model.'}
                  </p>
                )}
              </Panel>
            ))}
        </div>
        <div
          role="tabpanel"
          id="home-panel-archived"
          aria-labelledby="home-tab-archived"
          hidden={homeView !== 'archived'}
        >
          {homeView === 'archived' &&
            (loading ? (
              <p role="status" aria-busy="true">
                <StatusTag tone="running">Loading studies…</StatusTag>
              </p>
            ) : studiesFailed ? (
              <Button onClick={() => void openPage('home')}>Retry studies</Button>
            ) : (
              <>
                <p className="context-line home-note">
                  Archived studies are hidden from Home for everyone. Nothing in them is deleted.
                </p>
                <Panel
                  className="study-list"
                  bodyClassName="catalogue-body"
                  label="Archived studies"
                >
                  {visibleStudies.map((s) => (
                    <article className="study-row" key={s.study_id}>
                      <div>
                        <h2>
                          {s.name} <StatusTag tone="inert">Archived</StatusTag>
                        </h2>
                        {s.description && <p>{s.description}</p>}
                        {creatorChip(createdStudies.get(s.study_id))}
                      </div>
                      <div className="actions">
                        <Button
                          aria-label={`Open study ${s.name}`}
                          onClick={() => navigate(() => void chooseStudy(s.study_id))}
                        >
                          Open study
                        </Button>
                        <Button
                          aria-label={`Restore study ${s.name}`}
                          disabled={busy || !!api.pending}
                          onClick={() => restoreStudy(s)}
                        >
                          Restore
                        </Button>
                      </div>
                    </article>
                  ))}
                  {!visibleStudies.length && (
                    <p className="empty-state">
                      {archivedStudies.length
                        ? 'No archived studies match this filter.'
                        : 'No archived studies.'}
                    </p>
                  )}
                </Panel>
              </>
            ))}
        </div>
      </section>}
      {page === 'new-study' && <Panel className="creation-page"><h1>New study</h1><form onSubmit={e => { e.preventDefault(); void perform(async () => { const token = generation.current, actor = api.actor; const created = await api.createStudy(newStudy); if (token !== generation.current || actor !== api.actor) return; setNewStudy(''); await openLink({ study: created.study_id, view: 'overview' }); }); }}><label>New study name<TextInput required maxLength={4096} value={newStudy} onChange={e => setNewStudy(e.target.value)} /></label><div className="actions"><Button type="submit" variant="primary" disabled={busy || !!api.pending}>Create study</Button><Button type="button" disabled={busy} onClick={() => void openPage('home')}>Cancel</Button></div></form></Panel>}
      {page === 'study' && loading && <p aria-live="polite" aria-busy="true">Loading study/model…</p>}
      {study && <AttributionContext.Provider value={studyAttribution}>
        {(view !== 'model' || !selectedModel) && !(view === 'runs' && runInspection) ? (
          <div className="study-heading actions">
            <h1>{study.name}</h1>
            {studyCreator && <AttributionChip {...studyCreator} />}
          </div>
        ) : null}
        <Tabs
          navigation
          className="workspace-views"
          label="Workspace sections"
          value={selectedTab(view)}
          onChange={next => chooseView(next as WorkspaceView)}
          items={studyTabs()}
        />
        {ctx && viewRegistry.map(entry => (
          <Fragment key={entry.name}>{entry.banner?.(ctx)}</Fragment>))}
        {ctx && viewRegistry.map(entry => (
          <Fragment key={entry.name}>{entry.render(ctx)}</Fragment>))}
        {(view === 'model' || view === 'configurations' || view === 'runs') && !creatingModel && <ComparisonView actionHost={resourceActions} allowImport={view === 'model'} key={`${api.actor}:${study.study_id}:${view}:${displayedSnapshot?.model_id ?? 'none'}:${displayedSnapshot && 'model_revision_id' in displayedSnapshot ? displayedSnapshot.model_revision_id : displayedSnapshot?.draft_revision ?? 'none'}:${runInspection?.run_id ?? ''}:${configuration?.configuration.configuration_revision_id ?? ''}`} api={api} study={study} root={workspaceRoot} navigate={navigate} scope={displayedSnapshot ? { snapshot: displayedSnapshot, values: variableContext, configuration: variableContext.kind === 'run' ? variableContext.history.configuration?.configuration_revision_id : variableContext.kind === 'configuration' ? variableContext.configuration.configuration_revision_id : undefined, run: view === 'runs' ? runInspection?.run_id : undefined, selection, unsaved: dirty } : null} onImported={async imported => { const token = ++generation.current; clearEditor(); currentModel(imported); setModels(previous => [...previous.filter(m => m.model_id !== imported.model_id), { model_id: imported.model_id, name: imported.name }]); setView('model'); link({ study: study.study_id, model: imported.model_id, view: 'model' }); const [fresh, entries] = await Promise.all([api.study(study.study_id), api.revisions(study.study_id, imported.model_id)]); if (token !== generation.current) return; setCurrentStudy(fresh); setRevisions(entries); setNotice('Model imported with preserved public identities. No source executed.'); }} />}
      </AttributionContext.Provider>}
      </div></div>
    </>}
    <DialogFrame ref={dialog} aria-labelledby="dirty-title" onCancel={() => { transition.current = null; returnFocus.current?.focus(); }}><h2 id="dirty-title">Unsaved changes</h2><p>{guardsBlocked(guards) ? "Apply or discard the open editor changes before saving this draft." : "Save your changes before leaving this draft?"}</p><div className="actions"><Button disabled={busy || guardsBlocked(guards)} onClick={() => void perform(async () => { const result = await saveGuards(guards); if (result.outcome !== 'saved') { transition.current = null; closeDialog(); if (result.outcome === 'refused') result.entry.onRefused?.(); return; } guards.forEach(guard => guard.settle?.()); const next = transition.current; transition.current = null; closeDialog(); next?.(); })}>Save changes</Button><Button variant="danger" disabled={busy} onClick={() => { const next = transition.current; transition.current = null; discardGuards(guards); closeDialog(); next?.(); }}>Discard changes</Button><Button data-safe-choice onClick={() => { transition.current = null; closeDialog(); }}>Keep editing</Button></div></DialogFrame>
    <DialogFrame ref={archiveDialog} aria-labelledby="archive-title" onClose={() => { setArchiveTarget(null); const active = document.activeElement; if (archiveInvoker.current?.isConnected && (!active || active === document.body || archiveDialog.current?.contains(active))) archiveInvoker.current.focus(); }} className="action-dialog archive-dialog"><div className="dialog-heading"><h2 id="archive-title">Archive study</h2><Button variant="quiet" icon={<ActionIcon name="close" />} aria-label="Close Archive study" onClick={() => archiveDialog.current?.close()} /></div><div className="dialog-body"><p>Archive “{archiveTarget?.name}”? It disappears from Home for everyone. Nothing is deleted; restore it from Archived.</p><div className="actions"><Button variant="primary" disabled={busy || !!api.pending} onClick={confirmArchive}>Archive study</Button><Button data-safe-choice onClick={() => archiveDialog.current?.close()}>Cancel</Button></div></div></DialogFrame>
    <footer><a href="/ui/THIRD_PARTY_NOTICES.txt">Third-party software notices</a></footer>
  </main></CaseNavigation.Provider>;
}
