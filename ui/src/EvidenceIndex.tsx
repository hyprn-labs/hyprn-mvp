import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Button, Panel, SectionHeader, StatusTag } from './design';
import { Assumptions } from './Assumptions';
import { ApiError, HyprnMvpApi, accessLostText, accessUnverifiedText, descriptiveApproach, message, type EvidenceSnapshot } from './api';
import { useAccessLoss } from './accessLoss';
import type { ConfigurationAssumption, FrozenConfigurationRead7, ModelAssumption, RunHistoryRead6 } from './contract';
import { configurationContext, linkedApproach, modelAssumptions, recordLimitations, type ModelAssumptionsView } from './recordViews';
import type { WorkspaceLink } from './workspaceModel';

/**
 * Evidence index.
 *
 * One read-only view of assumptions grouped by owner, with their evidence, shared by the
 * Evidence page (current owners) and Run › Evidence (the versions retained with the run).
 * Each owner keeps its own group, so identical statements of different owners are never
 * merged. Assumptions are edited only at their owner.
 *
 * Owner content keeps "unknown" apart from "none": a failed read is "could not be loaded",
 * a format without assumptions states its limitation, and only a loaded empty list says
 * "No assumptions".
 */
export type OwnerContent =
  | { kind: 'loading' }
  /** The owner's read failed: its assumptions are unknown, never reported as none. */
  | { kind: 'failed'; message: string }
  /** The record cannot carry or be read for assumptions; this is not an empty list. */
  | { kind: 'limitation'; text: string }
  /** Explicitly nothing to list, for example no saved modeling approach version. */
  | { kind: 'none'; text: string }
  | { kind: 'assumptions'; items: ConfigurationAssumption[]; records: EvidenceSnapshot[]; approach?: boolean; owners?: ReadonlyMap<string, string> };
export type IndexOwner = {
  key: string; kind: 'approach' | 'model' | 'configuration';
  /** Names the owner's region: "<label> assumptions". */
  label: string; title: string; detail?: string; open?: ReactNode; content: OwnerContent;
};
export type EvidenceIndexState = {
  owners: IndexOwner[];
  /** Owner lists that could not be read: those owners are unknown, so nothing is implied about them. */
  unlisted: Array<{ what: string; message: string }>;
  /** Loaded owners with nothing to list, summarised instead of shown one by one. */
  summary?: string;
  loading?: boolean;
  /** Confirmed access loss for the study: everything protected was cleared. */
  lost?: boolean;
};

const kindOrder = { approach: 0, model: 1, configuration: 2 } as const;
const modelUnavailableText = "This run's model version can't be shown. The current model is not shown in its place.";
const configurationNoAssumptionsText = 'Configurations saved in this older format have no assumptions.';

/** Model and component assumptions of one exact model version or draft, read through recordViews. */
function modelContent(view: ModelAssumptionsView, records: EvidenceSnapshot[], unavailable = modelUnavailableText): OwnerContent {
  if (view.kind === 'unavailable') return { kind: 'limitation', text: unavailable };
  if (view.kind === 'not_in_format') return { kind: 'limitation', text: recordLimitations.modelAssumptionsNotInFormat };
  if (view.kind !== 'recorded') return { kind: 'limitation', text: recordLimitations.modelAssumptionsUnreadable };
  const owners = new Map<string, string>(), items: ModelAssumption[] = [];
  for (const item of view.modelOwned) { owners.set(item.assumption_id, 'Whole model'); items.push(item); }
  for (const { instance, items: owned } of view.components) for (const item of owned) { owners.set(item.assumption_id, 'Component · ' + instance.name); items.push(item); }
  // An owner component missing from the version is stated, never dropped.
  for (const item of view.items) if (!owners.has(item.assumption_id)) { owners.set(item.assumption_id, 'Component not in this model version'); items.push(item); }
  return { kind: 'assumptions', items, records, owners };
}

/**
 * Assumptions a run used, read only from what is retained with it: the linked approach
 * version in its approach closure, its model version snapshot and its configuration
 * revision. Nothing current is read or substituted (no API, no live evidence).
 */
export function retainedRunAssumptions(history: RunHistoryRead6, open: { approach?: ReactNode; model?: ReactNode; configuration?: ReactNode } = {}): IndexOwner[] {
  const owners: IndexOwner[] = [], configuration = history.configuration, model = history.model_snapshot, records = history.evidence ?? [];
  const context = configuration ? configurationContext(configuration) : null, pin = context ? linkedApproach(context) : null;
  const closure = 'approach_closure' in history ? history.approach_closure : null;
  if (pin) {
    const version = closure?.approach_versions.find(v => v.approach_version_id === pin.approach_version_id);
    owners.push({ key: 'approach', kind: 'approach', label: 'Modeling approach', title: version ? 'Modeling approach · Version ' + version.version_number : 'Modeling approach', open: open.approach,
      content: version && closure ? { kind: 'assumptions', items: descriptiveApproach(version.content).assumptions, records: closure.evidence, approach: true }
        : { kind: 'limitation', text: 'The linked modeling approach could not be loaded. The link to its version is unchanged.' } });
  } else if (context?.kind === 'supported' && context.approach.kind === 'unlinked') {
    owners.push({ key: 'approach', kind: 'approach', label: 'Modeling approach', title: 'Modeling approach', content: { kind: 'none', text: 'No modeling approach is linked.' } });
  }
  owners.push({ key: 'model', kind: 'model', label: 'Model', title: model ? 'Model version ' + model.model_revision_id.slice(0, 8) : 'Model', open: model ? open.model : undefined, content: modelContent(modelAssumptions(model), records) });
  if (configuration && context?.kind === 'supported') owners.push({ key: 'configuration', kind: 'configuration', label: 'Configuration', title: 'Configuration · ' + configuration.name, open: open.configuration,
    content: context.assumptions.kind === 'recorded' ? { kind: 'assumptions', items: context.assumptions.items, records } : { kind: 'limitation', text: configurationNoAssumptionsText } });
  return owners;
}

function OwnerGroup({ owner }: { owner: IndexOwner }) {
  const content = owner.content;
  return <section className="evidence-index-owner" aria-label={owner.label + ' assumptions'}>
    <div className="evidence-index-owner-head"><div><h4 className="evidence-index-owner-title">{owner.title}</h4>{owner.detail && <p className="context-line">{owner.detail}</p>}</div>{owner.open}</div>
    {content.kind === 'loading' && <p className="context-line">Loading assumptions…</p>}
    {content.kind === 'failed' && <p className="evidence-index-failed"><StatusTag tone="warning">Not loaded</StatusTag> Assumptions could not be loaded. {content.message}</p>}
    {content.kind === 'limitation' && <p>{content.text}</p>}
    {content.kind === 'none' && <p className="context-line">{content.text}</p>}
    {content.kind === 'assumptions' && <Assumptions regionless showHeading={false} approach={content.approach} ownerKey={'index/' + owner.key} ownerLabel={owner.label} items={content.items} records={content.records}
      itemContext={content.owners ? item => content.owners!.get(item.assumption_id) : undefined} />}
  </section>;
}

/** Shared assumptions-by-owner view, then the host's sources or evidence uses (`children`). */
export function EvidenceIndex({ state, intro, onRetry, framed = false, children }: { state: EvidenceIndexState; intro?: ReactNode; onRetry?: () => void; framed?: boolean; children?: ReactNode }) {
  const owners = [...state.owners].sort((a, b) => kindOrder[a.kind] - kindOrder[b.kind]);
  const failed = owners.filter(o => o.content.kind === 'failed').length, waiting = owners.filter(o => o.content.kind === 'loading').length;
  const loaded = owners.length - failed - waiting, loading = !!state.loading || waiting > 0, partial = !loading && (failed > 0 || state.unlisted.length > 0);
  const body = <>
    {intro && <p className="context-line evidence-index-intro">{intro}</p>}
    {state.lost ? <div role="alert" className="evidence-index-partial"><p>{accessLostText}</p>{onRetry && <Button size="sm" onClick={onRetry}>Retry loading assumptions</Button>}</div> : <>
      {loading && <p className="evidence-index-loading" aria-busy="true"><StatusTag tone="running">Loading assumptions…</StatusTag> {loaded} of {owners.length} groups loaded</p>}
      {partial && <div role="status" className="evidence-index-partial">
        <p><StatusTag tone="warning">Partial</StatusTag> {loaded} of {owners.length} groups loaded.{state.unlisted.map(u => ` ${u.what} could not be listed: ${/[.!?]$/.test(u.message) ? u.message : u.message + "."}`).join('')} Groups that could not be loaded are left out; they are not shown as having no assumptions.</p>
        {onRetry && <Button size="sm" onClick={onRetry}>Retry loading assumptions</Button>}
      </div>}
      {!loading && !partial && !owners.length && <p className="context-line">No assumptions</p>}
      {owners.map(owner => <OwnerGroup key={owner.key} owner={owner} />)}
      {state.summary && <p className="context-line evidence-index-summary">{state.summary}</p>}
    </>}
  </>;
  return <>
    {framed ? <Panel title="Assumptions" headingLevel={3} label="Assumptions by owner" className="evidence-index">{body}</Panel>
      : <section className="evidence-index" aria-label="Assumptions by owner"><SectionHeader title="Assumptions" />{body}</section>}
    {children}
  </>;
}

/** Bounded concurrency for independent owner reads. */
function limiter(max: number) {
  let active = 0; const queue: Array<() => void> = [];
  return (task: () => Promise<void>) => new Promise<void>(resolve => {
    const start = () => { active++; task().catch(() => {}).finally(() => { active--; queue.shift()?.(); resolve(); }); };
    if (active < max) start(); else queue.push(start);
  });
}

const readText = (error: unknown) => error instanceof ApiError && error.detail.code === 'backend_unavailable' ? 'Modeling is unavailable.' : message(error);

/**
 * Current assumptions of one study for the Evidence page: the latest saved
 * approach version, every model's current draft and the latest revision of each
 * configuration family. Reads are scoped by the shared session seam and run two at a time.
 * A confirmed denial clears everything (any host may report it); a failed owner read is
 * marked on that owner; a list that cannot be read is reported, never shown as empty.
 */
export function useCurrentAssumptions(api: HyprnMvpApi, studyId: string, onOpen?: (target: WorkspaceLink) => void) {
  const [state, setState] = useState<EvidenceIndexState>({ owners: [], unlisted: [], loading: true });
  const [attempt, setAttempt] = useState(0);
  const generation = useRef(0), open = useRef(onOpen); open.current = onOpen;
  useAccessLoss(api, studyId, change => { generation.current++; setState({ owners: [], unlisted: [], lost: change.kind === 'access-lost' }); });
  useEffect(() => {
    const token = ++generation.current, read = api.fence({ studyId }), run = limiter(2);
    const live = () => token === generation.current && read.valid();
    let owners: IndexOwner[] = [], pending = 0, summary: string | undefined;
    const unlisted: EvidenceIndexState['unlisted'] = [];
    const publish = () => { if (live()) setState({ owners, unlisted: [...unlisted], summary, loading: pending > 0 }); };
    const set = (key: string, patch: Partial<IndexOwner>) => { owners = owners.map(o => o.key === key ? { ...o, ...patch } : o); publish(); };
    const add = (owner: IndexOwner) => { owners = [...owners, owner]; };
    const link = (label: string, name: string, target: WorkspaceLink) => <Button size="sm" variant="quiet" aria-label={name ? label + ' ' + name : undefined} onClick={() => open.current?.(target)}>{label}</Button>;
    /** Shared classification: null when the read is stale or the denial already cleared everything. */
    const failure = async (error: unknown) => { const outcome = await api.readFailed(error, read); return outcome === 'access-lost' || outcome === 'stale' ? null : outcome === 'transient' ? accessUnverifiedText : readText(error); };
    const task = (work: () => Promise<void>) => { pending++; void run(async () => { if (live()) await work(); }).finally(() => { pending--; publish(); }); };
    add({ key: 'approach', kind: 'approach', label: 'Modeling approach', title: 'Modeling approach', content: { kind: 'loading' } });
    task(async () => {
      try {
        const current = await api.approach(studyId, read.signal); if (!live()) return;
        const latest = current.latest_version;
        if (!latest) { set('approach', { content: { kind: 'none', text: 'No saved modeling approach version.' }, open: link('Open modeling approach', '', { study: studyId, view: 'approach' }) }); return; }
        const saved = await api.approachVersion(studyId, latest.approach_version_id, read.signal); if (!live()) return;
        set('approach', { title: 'Modeling approach · Version ' + saved.version.version_number, open: link('Open modeling approach', 'version ' + saved.version.version_number, { study: studyId, view: 'approach', approach: saved.version.approach_version_id }),
          content: { kind: 'assumptions', items: descriptiveApproach(saved.version.content).assumptions, records: saved.closure.evidence, approach: true } });
      } catch (error) { const text = await failure(error); if (text !== null && live()) set('approach', { content: { kind: 'failed', message: text } }); }
    });
    task(async () => {
      try {
        const associations = await api.models(studyId, read.signal); if (!live()) return;
        for (const { model_id } of associations) {
          const key = 'model:' + model_id, short = 'Model ' + model_id.slice(0, 8);
          add({ key, kind: 'model', label: short, title: short, content: { kind: 'loading' } });
          task(async () => {
            try {
              const draft = await api.model(studyId, model_id, read.signal); if (!live()) return;
              const view = modelAssumptions(draft);
              const cited = view.kind === 'recorded' && view.items.some(item => item.evidence_links.length);
              const records = cited ? (await api.assumptionEvidence(studyId, model_id, { draft_revision: draft.draft_revision }, read.signal)).evidence : [];
              if (!live()) return;
              set(key, { label: 'Model · ' + draft.name, title: 'Model · ' + draft.name + ' (draft)', open: link('Open model', draft.name, { study: studyId, view: 'model', model: model_id }), content: modelContent(view, records) });
            } catch (error) { const text = await failure(error); if (text !== null && live()) set(key, { content: { kind: 'failed', message: text } }); }
          });
        }
        publish();
      } catch (error) { const text = await failure(error); if (text !== null && live()) { unlisted.push({ what: 'Models', message: text }); publish(); } }
    });
    task(async () => {
      try {
        const records = await api.configurations(studyId, read.signal); if (!live()) return;
        // Public collections are in insertion order: the last revision of a family is its latest.
        const latest = new Map<string, FrozenConfigurationRead7>();
        for (const record of records) latest.set(record.configuration.configuration_id ?? record.configuration.configuration_revision_id, record);
        let empty = 0, legacy = 0;
        for (const [family, { configuration: c }] of latest) {
          const context = configurationContext(c);
          const content: OwnerContent | null = context.kind === 'unsupported' ? { kind: 'limitation', text: recordLimitations.configurationUnsupported }
            : context.assumptions.kind !== 'recorded' ? (legacy++, null)
            : context.assumptions.items.length ? { kind: 'assumptions', items: context.assumptions.items, records: c.evidence_snapshots } : (empty++, null);
          if (content) add({ key: 'configuration:' + family, kind: 'configuration', label: 'Configuration · ' + c.name, title: 'Configuration · ' + c.name, detail: 'Version ' + c.configuration_revision_id.slice(0, 8),
            open: link('Open configuration', c.name, { study: studyId, view: 'configurations', configuration: c.configuration_revision_id }), content });
        }
        const parts = [empty && `${empty} configuration${empty === 1 ? ' has' : 's have'} no assumptions.`, legacy && `${legacy} configuration${legacy === 1 ? ' is' : 's are'} saved in an older format without assumptions.`].filter(Boolean);
        summary = parts.length ? parts.join(' ') : undefined;
        publish();
      } catch (error) { const text = await failure(error); if (text !== null && live()) { unlisted.push({ what: 'Configurations', message: text }); publish(); } }
    });
    publish();
    return () => { generation.current++; read.abort(); read.done(); };
  }, [api, studyId, attempt]);
  return { state, retry: () => setAttempt(n => n + 1) };
}
