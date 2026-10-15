import type { ScientificAnswer1, ScientificAnswerHeads1, ScientificAnswerSave1 } from './contract';
import type { ApproachContent1, ApproachContent2, ApproachResolution1, ApproachResolution3 } from './contract';
export type ApproachContent = ApproachContent1 | ApproachContent2;
export type ApproachResolution = ApproachResolution1 | ApproachResolution3;
import type { Study, Association, ModelDraftRead4, ModelRevisionRead4, Edit2, Source, Error as ContractError, PublicReceipt, ConfigurationCandidate1, FrozenConfigurationRead7, CompatibilityResult1, PublicRun, PublicRunDetail, RunHistoryItem, RevisionSummary, EvidenceRecord, EvidenceCreate2, ExecutionReadiness, Session, ApplyRead4, ResultSourcePage, ConfigurationRequest2, ConfigurationPreview2, ConfigurationCommit2, ModifiedRunSeed1, RecordRequestRead as RecordRequest, RecordPreviewRequest, RecordCreateRequest } from './contract';
import type {
  ConfigurationRequest4,
  ConfigurationPreview4,
  ConfigurationPreview6,
  ConfigurationPreview7,
  ConfigurationCommit4,
  EvidenceCreate3,
  EvidenceRevise3,
  EvidenceRecord3,
  EvidenceFamily3,
  AssumptionEvidenceResolution1,
  ConfigurationRequest3,
  ConfigurationPreview3,
  ConfigurationCommit3,
  ModifiedRunSeedRead6,
} from './contract';
import type { ApproachState2, ApproachPreviewRequestRead2, ApproachPreviewRead3, ApproachDraftWriteRead2, ApproachDraftRead2, ApproachVersionSave1, ApproachVersionSavedRead3, ApproachRestore1, ApproachSavedRead3, ApproachPageRequest1, ApproachVersionPage2, ApproachUsageRequest1, ApproachUsagePage1, ApproachReceiptRead2, ApproachReceiptCategory1 } from './contract';
import type { UnitCatalog1, PublicNewModel } from './contract';
import type { StudyArchiveCommand } from './contract';
import type { ReceiptError } from './contract';
import type { AgentAttribution1, AgentAttributionPage1 } from './contract';
export type * from './contract';
export type Envelope<T> = { schema_version: '1'; data: T; next_cursor?: string | null };
export type EvidencePage = Envelope<EvidenceRecord[]> & { next_cursor: string | null };
export type EvidenceQuery = { view?: 'heads' | 'versions'; limit?: number; cursor?: string; scope_kind?: 'study' | 'model_revision' | 'definition_version' | 'instance' | 'port' | 'connection' | 'configuration' | 'run' | 'criterion' | 'legacy'; model_id?: string; model_revision_id?: string; instance_id?: string; port_id?: string; configuration_revision_id?: string; run_id?: string; legacy_scope?: string };
export type EvidenceSelector = { model_revision_id: string; draft_revision?: never } | { draft_revision: string; model_revision_id?: never };
/** The recovery members of a receipt read's answer or of its 404 error object. */
type Recovery = Partial<Pick<ReceiptError['error'], 'recovery' | 'retry_after_s'>>;
export type EvidenceReceipt = Omit<PublicReceipt, 'result'> & { result: EvidenceRecord | null };
export class ApiError extends Error {
  constructor(public detail: ContractError['error']) { super(detail.message); }
}
/** One denial classification for every read host. These codes are a
 * confirmed denial; a concealed `resource_not_found` is confirmed by a study probe. */
export const accessDeniedCodes: readonly string[] = ['unauthenticated', 'unauthorized', 'forbidden'];
export const accessDenied = (error: unknown) => error instanceof ApiError && accessDeniedCodes.includes(error.detail.code);
const concealed = (error: unknown) => error instanceof ApiError && error.detail.code === 'resource_not_found';
export const accessLostText = 'Access to this resource is no longer available.';
export const accessUnverifiedText = 'Study access could not be verified. Retry the read.';
/** Client-only session signal; no wire change. */
export type SessionChange =
  | { kind: 'signed-out' }
  | { kind: 'signed-in'; actor: string }
  | { kind: 'access-lost'; studyId: string };
/** Fence for one read: captured actor, CSRF session, session epoch and the study's
 * access epoch. It deliberately carries no dialog or list generation, so a list or
 * version switch can never discard a confirmed denial:
 * hosts that need "latest request wins" keep their own token beside it. */
export type ReadFence = { readonly studyId?: string; signal: AbortSignal; valid(): boolean; abort(): void; done(): void };
/** stale: the fence no longer holds (session or access already changed);
 * access-lost: confirmed denial, already signalled; transient: the study probe
 * failed, keep content and offer a retry; error: an ordinary read failure. */
export type ReadFailure = 'stale' | 'access-lost' | 'transient' | 'error';
export function message(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.detail.code === 'stale_revision') return 'This model changed. Your edits are preserved; review the current revision.';
    if (error.detail.code === 'backend_unavailable') return 'Modeling is unavailable. Your edits are preserved. Retry the read when it is available.';
    if (error.detail.outcome === 'unknown' || error.detail.outcome === 'pending') return 'Command outcome is uncertain. Check the original command before making more changes.';
  }
  return error instanceof Error ? error.message : 'The request could not be completed.';
}
export async function sourceFromBytes(raw: Uint8Array): Promise<Source> {
  const digest = await crypto.subtle.digest('SHA-256', raw as Uint8Array<ArrayBuffer>);
  let binary = ''; for (const byte of raw) binary += String.fromCharCode(byte);
  return { encoding: 'base64', media_type: 'text/x-python', bytes: btoa(binary), sha256: Array.from(new Uint8Array(digest), b => b.toString(16).padStart(2, '0')).join('') };
}
export const sourceFromText = (text: string) => sourceFromBytes(new TextEncoder().encode(text));
export const sourceText = (source: Source) => new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(Uint8Array.from(atob(source.bytes), c => c.charCodeAt(0)));
// Closed typed commands are preserved from preview through apply/recovery.
export function validateEditCommand(command: ApplyRead4, snapshot?: ModelDraftRead4) {
  if (!command.edits.length || command.edits.length > 256) throw new Error('Batch must contain 1–256 edits; it will not be split.');
  if (new TextEncoder().encode(JSON.stringify(command)).length > 2 * 1024 * 1024) throw new Error('Batch exceeds the 2 MiB request limit; reduce the proposal.');
  for (const [row, edit] of command.edits.entries()) {
    const sources = edit.kind === 'create_definition' ? [edit.source] : edit.kind === 'revise_definition' ? edit.changes.flatMap(c => c.kind === 'set_source' ? [c.source] : []) : [];
    if (sources.some(source => atob(source.bytes).length > 256 * 1024)) throw new Error(`Row ${row + 1}: source exceeds 256 KiB.`);
  }
  if (snapshot && snapshot.instances.length + snapshot.connections.length + snapshot.definitions.reduce((n, d) => n + d.ports.length, 0) > 1000) throw new Error('Preview exceeds the 1000 element limit; reduce the proposal.');
}
const modelPath = (sid: string, mid: string) => `/studies/${sid}/models/${mid}`;
/** Who acted for one agent-written record: the agent's and the delegating user's names, each
 * from its own API field and never parsed from text. A user without a name reads "unknown
 * user", so an agent-written record never looks person-written. */
export type AttributionEntry = { readonly agent: string; readonly user: string };
/** Attribution entries keyed by `attributionKey`: newest entry first wins. */
export type AttributionIndex = ReadonlyMap<string, AttributionEntry>;
export type AttributionKind = AgentAttribution1['record_kind'];
/** Index key of one record: its kind and its version id (versioned records) or record id. */
export const attributionKey = (kind: AttributionKind, id: string) => kind + '\u0000' + id;
const attributionEntry = (item: AgentAttribution1): AttributionEntry => ({
  agent: item.agent.display_name,
  user: item.delegator.display_name ?? 'unknown user',
});
/** Every page of one attribution read (newest first), following its opaque cursor. */
async function attributionPages(
  read: (cursor: string | null) => Promise<AgentAttributionPage1>,
): Promise<AgentAttribution1[]> {
  const items: AgentAttribution1[] = [];
  let cursor: string | null = null;
  do {
    const page: AgentAttributionPage1 = await read(cursor);
    items.push(...page.items);
    cursor = page.next_cursor;
  } while (cursor);
  return items;
}
export class HyprnMvpApi {
  answers = async (sid: string, version: string, signal?: AbortSignal) =>
    (await this.request<ScientificAnswerHeads1>(
      `/studies/${sid}/approach/versions/${version}/answers`, undefined, 'GET', signal,
    )).data;
  answer = async (sid: string, version: string, signal?: AbortSignal) =>
    (await this.request<ScientificAnswer1>(
      `/studies/${sid}/answers/${version}`, undefined, 'GET', signal,
    )).data;
  saveAnswer = async (sid: string, body: ScientificAnswerSave1) =>
    (await this.mutate<ScientificAnswer1>(
      `/studies/${sid}/answers`, body, 'answer_save', sid,
    )).data;
  unitCatalog = async (sid: string, signal?: AbortSignal) => (await this.request<UnitCatalog1>(`/studies/${sid}/unit-catalog`, undefined, 'GET', signal)).data;
  approach = async (sid: string, signal?: AbortSignal) => (await this.request<ApproachState2>(`/studies/${sid}/approach`, undefined, 'GET', signal)).data;
  previewApproach = async (sid: string, body: ApproachPreviewRequestRead2, signal?: AbortSignal) => (await this.request<ApproachPreviewRead3>(`/studies/${sid}/approach/preview`, body, 'POST', signal)).data;
  saveApproachDraft = async (sid: string, body: ApproachDraftWriteRead2) => (await this.mutate<ApproachDraftRead2>(`/studies/${sid}/approach/draft`, body, 'approach_draft', sid)).data;
  saveApproachVersion = async (sid: string, body: ApproachVersionSave1) => (await this.mutate<ApproachVersionSavedRead3>(`/studies/${sid}/approach/versions`, body, 'approach_version', sid)).data;
  restoreApproach = async (sid: string, body: ApproachRestore1) => (await this.mutate<ApproachDraftRead2>(`/studies/${sid}/approach/draft/restore`, body, 'approach_restore', sid)).data;
  approachVersion = async (sid: string, id: string, signal?: AbortSignal) => (await this.request<ApproachSavedRead3>(`/studies/${sid}/approach/versions/${id}`, undefined, 'GET', signal)).data;
  approachVersions = async (sid: string, query: Partial<ApproachPageRequest1> = {}, signal?: AbortSignal) => {
    const params = new URLSearchParams();
    if (query.limit !== undefined) params.set('limit', String(query.limit));
    if (query.cursor) params.set('cursor', JSON.stringify(query.cursor));
    return (await this.request<ApproachVersionPage2>(`/studies/${sid}/approach/versions?${params}`, undefined, 'GET', signal)).data;
  };
  approachUsage = async (sid: string, id: string, query: Partial<ApproachUsageRequest1> = {}, signal?: AbortSignal) => {
    const params = new URLSearchParams();
    if (query.limit !== undefined) params.set('limit', String(query.limit));
    if (query.cursor) params.set('cursor', JSON.stringify(query.cursor));
    if (query.case_id) params.set('case_id', query.case_id);
    return (await this.request<ApproachUsagePage1>(`/studies/${sid}/approach/versions/${id}/usage?${params}`, undefined, 'GET', signal)).data;
  };
  approachReceipt = async (sid: string, command: string, category: ApproachReceiptCategory1, signal?: AbortSignal) => (await this.request<ApproachReceiptRead2>(`/studies/${sid}/commands/${command}?category=${category}`, undefined, 'GET', signal)).data;
  modifiedRunSeedRead = async (sid: string, rid: string, signal?: AbortSignal) => (await this.request<ModifiedRunSeedRead6>(`/studies/${sid}/runs/${rid}/modified-run-seed`, undefined, 'GET', signal)).data;
  async modifiedRunSeed(sid: string, rid: string): Promise<ModifiedRunSeed1> {
    const seed = await this.modifiedRunSeedRead(sid, rid);
    if (seed.schema_version !== '1') throw new Error('This configuration requires the assumptions-aware modified-run editor.');
    return seed;
  }
  csrf = '';
  actor = '';
  onAuthorizationLoss = () => {};
  private recovery = new Map<string, { pending: HyprnMvpApi['pending']; retryReady: boolean }>();
  private closeSession() {
    if (this.pending && this.actor) this.recovery.set(this.actor, { pending: this.pending, retryReady: this.retryReady });
    this.pending = null; this.retryReady = false; this.csrf = ''; this.actor = '';
    this.emit({ kind: 'signed-out' });
  }
  private sessionListeners = new Set<(change: SessionChange) => void>();
  private sessionEpoch = 0;
  private accessEpochs = new Map<string, number>();
  private openReads = new Set<{ studyId?: string; abort: AbortController }>();
  private probes = new Map<string, Promise<ReadFailure | 'ok'>>();
  /** Session and access-loss signal for protected-content hosts. Returns unsubscribe. */
  onSessionChange(listener: (change: SessionChange) => void): () => void {
    this.sessionListeners.add(listener);
    return () => { this.sessionListeners.delete(listener); };
  }
  private emit(change: SessionChange) {
    // Invalidate before notifying: no late reply may repopulate a cleared host.
    if (change.kind === 'access-lost') this.accessEpochs.set(change.studyId, (this.accessEpochs.get(change.studyId) ?? 0) + 1);
    else this.sessionEpoch++;
    for (const read of [...this.openReads]) if (change.kind !== 'access-lost' || read.studyId === change.studyId) { read.abort.abort(); this.openReads.delete(read); }
    for (const listener of [...this.sessionListeners]) listener(change);
  }
  /** Confirmed denial for one study: invalidates its fences, aborts its open reads and signals hosts. */
  accessLost(studyId: string) { this.emit({ kind: 'access-lost', studyId }); }
  fence(scope: { studyId?: string } = {}): ReadFence {
    const actor = this.actor, csrf = this.csrf, session = this.sessionEpoch, studyId = scope.studyId;
    const access = studyId === undefined ? 0 : this.accessEpochs.get(studyId) ?? 0;
    const entry = { studyId, abort: new AbortController() };
    this.openReads.add(entry);
    return { studyId, signal: entry.abort.signal, abort: () => entry.abort.abort(), done: () => { this.openReads.delete(entry); },
      valid: () => !entry.abort.signal.aborted && actor === this.actor && csrf === this.csrf && session === this.sessionEpoch &&
        (studyId === undefined || access === (this.accessEpochs.get(studyId) ?? 0)) };
  }
  /** Probe current study access once per study, session and access epoch; concurrent callers share it. */
  async confirmAccess(fence: ReadFence, studyId = fence.studyId): Promise<ReadFailure | 'ok'> {
    if (!fence.valid()) return 'stale';
    if (studyId === undefined) return 'error';
    const key = [studyId, this.actor, this.csrf, this.sessionEpoch, this.accessEpochs.get(studyId) ?? 0].join('\u0000');
    let probe = this.probes.get(key);
    if (!probe) {
      const scope = this.fence({ studyId });
      probe = this.study(studyId, scope.signal).then((): ReadFailure | 'ok' => 'ok', (error): ReadFailure | 'ok' => {
        if (!scope.valid()) return 'stale';
        if (accessDenied(error) || concealed(error)) { this.accessLost(studyId); return 'access-lost'; }
        return 'transient';
      }).finally(() => { scope.done(); this.probes.delete(key); });
      this.probes.set(key, probe);
    }
    const outcome = await probe;
    if (outcome === 'access-lost') return 'access-lost';
    return fence.valid() ? outcome : 'stale';
  }
  /** Shared read-failure classification for every protected-content host. A failed
   * command (`command: true`) may be refused for its role, not for read access: a
   * `forbidden` there is confirmed by the study probe instead of clearing directly. */
  async readFailed(error: unknown, fence: ReadFence, options: { command?: boolean } = {}): Promise<ReadFailure> {
    const studyId = fence.studyId;
    if (!fence.valid()) return 'stale';
    const roleRefusal = options.command && error instanceof ApiError && error.detail.code === 'forbidden';
    if (accessDenied(error) && !roleRefusal) { if (studyId !== undefined) this.accessLost(studyId); return 'access-lost'; }
    if ((concealed(error) || roleRefusal) && studyId !== undefined) {
      const outcome = await this.confirmAccess(fence, studyId);
      if (outcome !== 'ok') return outcome;
    }
    return fence.valid() ? 'error' : 'stale';
  }
  onPendingChange = () => {};
  retryReady = false;
  pending: { path: string; body: { command_id: string }; method: string; category: string; study?: string } | null = null;
  async request<T>(path: string, body?: unknown, method = body === undefined ? 'GET' : 'POST', signal?: AbortSignal): Promise<Envelope<T>> {
    const actor = this.actor;
    const timeout = AbortSignal.timeout(30000);
    const result = await fetch('/api/1' + path, { method, credentials: 'same-origin', signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
      headers: body === undefined ? {} : { 'Content-Type': 'application/json', 'X-CSRF-Token': this.csrf },
      body: body === undefined ? undefined : JSON.stringify(body) });
    const value = await result.json();
    signal?.throwIfAborted();
    if (path !== '/session' && actor !== this.actor) throw new Error('The session changed. This response was not applied.');
    if (!result.ok) {
      if (result.status === 401 && path !== '/session') { this.closeSession(); this.onAuthorizationLoss(); }
      throw new ApiError(value.error ?? { code: 'invalid_request', message: 'The request was rejected. Review the entered values.', fields: [], outcome: 'unchanged' });
    }
    return value;
  }
  async login(username: string, password: string) {
    const result = await this.request<Session>('/session', { username, password });
    this.csrf = result.data.csrf_token; this.actor = result.data.actor_id;
    const recovery = this.recovery.get(this.actor); this.pending = recovery?.pending ?? null; this.retryReady = recovery?.retryReady ?? false; this.recovery.delete(this.actor);
    this.emit({ kind: 'signed-in', actor: this.actor });
  }
  async logout() { await this.request('/session', {}, 'DELETE'); this.closeSession(); }
  async mutate<T>(path: string, body: { command_id: string }, category: string, study?: string, method = 'POST', signal?: AbortSignal): Promise<Envelope<T>> {
    if (this.pending) throw new Error('Check the original command before making more changes.');
    const command = { path, body: structuredClone(body), method, category, study };
    const actor = this.actor;
    this.retryReady = false;
    try {
      const result = await this.request<T>(path, command.body, method, signal);
      // Accepted remote model commands can be pending without an HTTP error.
      if ('state' in (result.data as object) && (result.data as { state: string }).state === 'pending_remote') {
        this.pending = command; throw new Error('Command outcome is uncertain. Check the original command.');
      }
      return result;
    } catch (error) {
      if (actor !== this.actor) {
        if (actor) this.recovery.set(actor, { pending: command, retryReady: false });
        throw error;
      }
      if (!(error instanceof ApiError) || ['unknown', 'pending'].includes(error.detail.outcome)) this.pending = command;
      throw error;
    } finally { this.onPendingChange(); }
  }
  async reconcile() {
    const p = this.pending;
    if (!p) return;
    this.retryReady = false;
    const id = p.body.command_id;
    const path = p.study ? `/studies/${p.study}/commands/${id}` : `/commands/${id}`;
    try {
      const receipt = (await this.request<PublicReceipt>(`${path}?category=${p.category}`)).data;
      this.follow(receipt.recovery);
      return receipt;
    } catch (error) {
      // A missing receipt in a scope this reader may see carries the owner's recovery; an
      // error without one (access ended) keeps the command pending and never retry-ready.
      const recovery = error instanceof ApiError ? (error.detail as Recovery).recovery : undefined;
      if (recovery === undefined || recovery === 'wait') {
        this.follow(recovery);
        throw error;
      }
      this.follow(recovery);
      return;
    } finally {
      this.onPendingChange();
    }
  }
  /** The owner decides the recovery (ADR-0004): this client only follows it. adopt and
   * refused settle the command; resend_same_command allows one resend of the exact original
   * body; wait, uncertain or no recovery at all keep it pending and never resend. */
  private follow(recovery: Recovery['recovery']) {
    if (recovery === 'adopt' || recovery === 'refused') this.pending = null;
    else this.retryReady = recovery === 'resend_same_command';
  }
  async retryOriginal() {
    const p = this.pending;
    if (!p || !this.retryReady) throw new Error('Check the original command before retrying.');
    await this.reconcile();
    if (!this.pending) return; // A lost acknowledgement may now be resolved.
    if (!this.retryReady) throw new Error('The original command cannot be retried yet.');
    this.pending = null;
    return this.mutate(p.path, p.body, p.category, p.study, p.method);
  }
  async list<T>(path: string, signal?: AbortSignal): Promise<T[]> {
    const all: T[] = []; let cursor: string | null | undefined;
    do { const page = await this.request<T[]>(path + (cursor ? `${path.includes('?') ? '&' : '?'}cursor=${encodeURIComponent(cursor)}` : ''), undefined, 'GET', signal); all.push(...page.data); cursor = page.next_cursor; } while (cursor);
    return all;
  }
  /** Who wrote what in one study: every page of its attribution read, indexed by record kind
   * and by both the record id and the version id of each entry (newest entry first wins). */
  attribution = async (sid: string, signal?: AbortSignal): Promise<AttributionIndex> => {
    const path = `/studies/${sid}/agent/attribution?limit=100`;
    const items = await attributionPages(async (cursor) => {
      const next = cursor ? `${path}&cursor=${encodeURIComponent(cursor)}` : path;
      return (await this.request<AgentAttributionPage1>(next, undefined, 'GET', signal)).data;
    });
    const index = new Map<string, AttributionEntry>();
    for (const item of items) {
      for (const id of [item.record_id, item.version_id]) {
        const key = id === null ? null : attributionKey(item.record_kind, id);
        if (key !== null && !index.has(key)) index.set(key, attributionEntry(item));
      }
    }
    return index;
  };
  /** The studies an agent created that the signed-in user is a member of, keyed by study id. */
  createdStudies = async (signal?: AbortSignal): Promise<ReadonlyMap<string, AttributionEntry>> => {
    const path = '/agent/attribution/studies?limit=100';
    const items = await attributionPages(async (cursor) => {
      const next = cursor ? `${path}&cursor=${encodeURIComponent(cursor)}` : path;
      return (await this.request<AgentAttributionPage1>(next, undefined, 'GET', signal)).data;
    });
    const created = new Map<string, AttributionEntry>();
    for (const item of items) {
      if (item.record_kind === 'study' && !created.has(item.study_id)) {
        created.set(item.study_id, attributionEntry(item));
      }
    }
    return created;
  };
  studies = () => this.list<Study>('/studies');
  /** Study-wide archive. Home reads both lists; archive is presentation
   * state, never access control or deletion. Commands use the shared receipt/recovery path. */
  archivedStudies = () => this.list<Study>('/studies?archived=true');
  archiveStudy = async (sid: string, command: StudyArchiveCommand) => (await this.mutate<Study>(`/studies/${sid}/archive`, command, 'study_archive', sid)).data;
  restoreStudy = async (sid: string, command: StudyArchiveCommand) => (await this.mutate<Study>(`/studies/${sid}/restore`, command, 'study_archive', sid)).data;
  study = async (sid: string, signal?: AbortSignal) => (await this.request<Study>(`/studies/${sid}`, undefined, 'GET', signal)).data;
  createStudy = async (name: string) => (await this.mutate<Study>('/studies', { command_id: crypto.randomUUID(), name } as { command_id: string }, 'study_create')).data;
  updateStudy = async (study: Study, changes: Pick<Study, 'name' | 'description' | 'boundary'>) => (await this.mutate<Study>(`/studies/${study.study_id}`, { command_id: crypto.randomUUID(), expected_revision: study.revision, ...changes } as { command_id: string }, 'study', study.study_id, 'PATCH')).data;
  models = (sid: string, signal?: AbortSignal) => this.list<Association>(`/studies/${sid}/models`, signal);
  model = async (sid: string, mid: string, signal?: AbortSignal) => (await this.request<ModelDraftRead4>(modelPath(sid, mid), undefined, 'GET', signal)).data;
  revisions = (sid: string, mid: string) => this.list<RevisionSummary>(modelPath(sid, mid) + '/revisions');
  revision = async (sid: string, mid: string, rid: string, signal?: AbortSignal) => (await this.request<ModelRevisionRead4>(modelPath(sid, mid) + '/revisions/' + rid, undefined, 'GET', signal)).data;
  evidence = (sid: string) => this.list<EvidenceRecord>(`/studies/${sid}/evidence`);
  evidencePage = async (sid: string, options: EvidenceQuery = {}, signal?: AbortSignal): Promise<EvidencePage> => {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(options)) if (value !== undefined) query.set(key, String(value));
    const page = await this.request<EvidenceRecord[]>(`/studies/${sid}/evidence?${query}`, undefined, 'GET', signal);
    return { ...page, next_cursor: page.next_cursor ?? null };
  };
  evidenceVersion = async (sid: string, version: string, signal?: AbortSignal) => (await this.request<EvidenceRecord>(`/studies/${sid}/evidence/${version}`, undefined, 'GET', signal)).data;
  evidenceFamily = async (sid: string, family: string, signal?: AbortSignal) => (await this.request<EvidenceFamily3>(`/studies/${sid}/evidence-families/${family}`, undefined, 'GET', signal)).data;
  evidenceVersions = async (sid: string, family: string, options: Pick<EvidenceQuery, 'limit' | 'cursor'> = {}, signal?: AbortSignal): Promise<EvidencePage> => {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(options)) if (value !== undefined) query.set(key, String(value));
    const page = await this.request<EvidenceRecord[]>(`/studies/${sid}/evidence-families/${family}/versions?${query}`, undefined, 'GET', signal);
    return { ...page, next_cursor: page.next_cursor ?? null };
  };
  createEvidence = async (sid: string, value: Omit<EvidenceCreate2, 'command_id'> | Omit<EvidenceCreate3, 'command_id'>) => (await this.mutate<EvidenceRecord>(`/studies/${sid}/evidence`, { ...value, command_id: crypto.randomUUID() }, 'evidence', sid)).data;
  createEvidenceCommand = async (sid: string, command: EvidenceCreate3, signal?: AbortSignal) => (await this.mutate<EvidenceRecord3>(`/studies/${sid}/evidence`, command, 'evidence', sid, 'POST', signal)).data;
  reviseEvidence = async (sid: string, family: string, command: EvidenceRevise3, signal?: AbortSignal) => (await this.mutate<EvidenceRecord3>(`/studies/${sid}/evidence-families/${family}/versions`, command, 'evidence', sid, 'POST', signal)).data;
  evidenceReceipt = async (sid: string, command: string, signal?: AbortSignal) => (await this.request<EvidenceReceipt>(`/studies/${sid}/commands/${command}?category=evidence`, undefined, 'GET', signal)).data;
  assumptionEvidence = async (sid: string, mid: string, selector: EvidenceSelector, signal?: AbortSignal) => {
    const query = new URLSearchParams();
    if (selector.model_revision_id !== undefined) query.set('model_revision_id', selector.model_revision_id);
    if (selector.draft_revision !== undefined) query.set('draft_revision', selector.draft_revision);
    return (await this.request<AssumptionEvidenceResolution1>(modelPath(sid, mid) + '/assumption-evidence?' + query, undefined, 'GET', signal)).data;
  };
  readiness = async (sid: string) => (await this.request<ExecutionReadiness>(`/studies/${sid}/execution-readiness`)).data;
  explorationBasis = async (
    sid: string, answer: string, configuration: string, signal?: AbortSignal,
  ) => (await this.request<import('./contract').ExplorationBasis1>(
    `/studies/${sid}/answers/${answer}/exploration-basis/${configuration}`,
    undefined, 'GET', signal,
  )).data;
  preparedExplorations = (
    sid: string, answer: string, configuration: string, signal?: AbortSignal,
  ) => this.list<import('./contract').ExplorationOperation1>(
    `/studies/${sid}/exploration-requests?` +
    new URLSearchParams({ answer_version_id: answer, configuration_revision_id: configuration }),
    signal,
  );
  explorationDesigns = (sid: string, answer: string, signal?: AbortSignal) =>
    this.list<import('./contract').ExplorationDesign1>(
      `/studies/${sid}/exploration-designs?` +
      new URLSearchParams({answer_version_id: answer}), signal);
  saveExplorationDesign = async (
    sid: string, body: import('./contract').ExplorationDesignRequest1,
  ) => (await this.mutate<import('./contract').ExplorationDesign1>(
    `/studies/${sid}/exploration-designs`, body, 'exploration_design', sid)).data;
  explorationSamples = (sid: string, answer: string, signal?: AbortSignal) =>
    this.list<import('./contract').ExplorationSampleOperation1 |
      import('./contract').ExplorationSampleOperation2>(
      `/studies/${sid}/exploration-samples?` +
      new URLSearchParams({answer_version_id: answer}), signal);
  previewExplorationSamples = async (
    sid: string, body: import('./contract').ExplorationSampleRequest2, signal?: AbortSignal,
  ) => (await this.request<import('./contract').ExplorationSamplePreview1>(
    `/studies/${sid}/exploration-samples/preview`, body, 'POST', signal)).data;
  submitExplorationSamples = async (
    sid: string, body: import('./contract').ExplorationSampleRequest2,
  ) => (await this.mutate<import('./contract').ExplorationSampleOperation2>(
    `/studies/${sid}/exploration-samples`, body, 'exploration_sample', sid)).data;
  readExplorationSamples = async (sid: string, id: string, signal?: AbortSignal) =>
    (await this.request<import('./contract').ExplorationSampleOperation1 |
      import('./contract').ExplorationSampleOperation2>(
      `/studies/${sid}/exploration-samples/${id}`, undefined, 'GET', signal)).data;
  controlExplorationSamples = async (
    sid: string, id: string, action: 'cancel' | 'reconcile' | 'resume',
  ) => (await this.mutate<import('./contract').ExplorationSampleOperation1 |
    import('./contract').ExplorationSampleOperation2>(
    `/studies/${sid}/exploration-samples/${id}/controls`,
    {command_id:crypto.randomUUID(), action} as import('./contract').ExplorationSampleControl1,
    'exploration_sample_control', sid)).data;
  configuration = async (sid: string, rid: string, signal?: AbortSignal) => (await this.request<FrozenConfigurationRead7>(`/studies/${sid}/configurations/${rid}`, undefined, 'GET', signal)).data;
  createModelCommand = async (sid: string, command: PublicNewModel) => (await this.mutate<ModelDraftRead4>(`/studies/${sid}/models`, command, 'model', sid)).data;
  createModel = async (study: Study, name: string, template: 'empty' | 'two_component_example') => this.createModelCommand(study.study_id, { command_id: crypto.randomUUID(), expected_revision: study.revision, name, template });
  previewEdits = async (model: ModelDraftRead4, command: ApplyRead4) => {
    validateEditCommand(command);
    const { command_id: _commandId, ...preview }: ApplyRead4 = command;
    const value = (await this.request<ModelDraftRead4>(modelPath(model.study_id, model.model_id) + '/preview', preview)).data;
    validateEditCommand(command, value); return value;
  };
  applyCommand = async (model: ModelDraftRead4, command: ApplyRead4) => { validateEditCommand(command); return (await this.mutate<ModelDraftRead4>(modelPath(model.study_id, model.model_id) + '/edits', command, 'model', model.study_id)).data; };
  apply = async (model: ModelDraftRead4, edits: Edit2[]) => {
    if (model.schema_version === '3' || model.schema_version === '4') throw new Error('Use an explicit version3 or version4 command for this model.');
    return this.applyCommand(model, { schema_version: '2', command_id: crypto.randomUUID(), expected_revision: model.draft_revision, edits });
  };
  commitModel = async (model: ModelDraftRead4) => (await this.mutate<ModelRevisionRead4>(modelPath(model.study_id, model.model_id) + '/commits', { command_id: crypto.randomUUID(), expected_revision: model.draft_revision } as { command_id: string }, 'model', model.study_id)).data;
  configurations = (sid: string, signal?: AbortSignal) => this.list<FrozenConfigurationRead7>(`/studies/${sid}/configurations`, signal);
  previewConfiguration = async (candidate: ConfigurationCandidate1) => (await this.request<CompatibilityResult1>(`/studies/${candidate.study_id}/configurations/preview`, candidate)).data;
  resultSourcesPage = async (study: string, limit = 25, cursor?: string) => {
    const query = new URLSearchParams({ limit: String(limit) });
    if (cursor !== undefined) query.set('cursor', cursor);
    return (await this.request<ResultSourcePage>(`/studies/${study}/result-sources?${query}`)).data;
  };
  previewConfiguration2 = async (candidate: ConfigurationRequest2) => (await this.request<ConfigurationPreview2>(`/studies/${candidate.study_id}/configurations/preview`, candidate)).data;
  commitConfiguration2 = async (body: ConfigurationCommit2) => (await this.mutate<FrozenConfigurationRead7>(`/studies/${body.configuration.study_id}/configurations`, body, 'configuration', body.configuration.study_id)).data;
  previewConfiguration4 = async (candidate: ConfigurationRequest4, signal?: AbortSignal) => (
    await this.request<ConfigurationPreview4 | ConfigurationPreview6 | ConfigurationPreview7>(
      `/studies/${candidate.study_id}/configurations/preview`, candidate, 'POST', signal
    )
  ).data;
  commitConfiguration4 = async (body: ConfigurationCommit4) => (await this.mutate<FrozenConfigurationRead7>(`/studies/${body.configuration.study_id}/configurations`, body, 'configuration', body.configuration.study_id)).data;
  previewConfiguration3 = async (candidate: ConfigurationRequest3, signal?: AbortSignal) => (await this.request<ConfigurationPreview3>(`/studies/${candidate.study_id}/configurations/preview`, candidate, 'POST', signal)).data;
  commitConfiguration3 = async (body: ConfigurationCommit3) => (await this.mutate<FrozenConfigurationRead7>(`/studies/${body.configuration.study_id}/configurations`, body, 'configuration', body.configuration.study_id)).data;
  commitConfiguration = async (candidate: ConfigurationCandidate1) => (await this.mutate<FrozenConfigurationRead7>(`/studies/${candidate.study_id}/configurations`, { command_id: crypto.randomUUID(), expected_revision: null, configuration: candidate } as { command_id: string }, 'configuration', candidate.study_id)).data;
  submitRun = async (sid: string, revision: string) => (await this.mutate<PublicRun>(`/studies/${sid}/runs`, { command_id: crypto.randomUUID(), configuration_revision_id: revision } as { command_id: string }, 'run', sid)).data;
  runs = (sid: string) => this.list<RunHistoryItem>(`/studies/${sid}/runs`);
  run = async (sid: string, rid: string) => (await this.request<PublicRunDetail>(`/studies/${sid}/runs/${rid}`)).data;
  previewComputationalRecord = async (sid: string, body: RecordPreviewRequest) => (await this.mutate<RecordRequest>(`/studies/${sid}/computational-record-previews`, body, 'computational_record_preview', sid)).data;
  createComputationalRecord = async (sid: string, body: RecordCreateRequest) => (await this.mutate<RecordRequest>(`/studies/${sid}/computational-records`, body, 'computational_record_create', sid)).data;
  computationalRecord = async (sid: string, id: string, signal?: AbortSignal) => (await this.request<RecordRequest>(`/studies/${sid}/computational-records/${id}`, undefined, 'GET', signal)).data;
  async downloadComputationalRecord(sid: string, id: string, expected: NonNullable<RecordRequest['download']>) {
    const actor = this.actor;
    if (expected.size < 1 || expected.size > 33554432) throw new Error('The record export exceeds the download limit.');
    const response = await fetch(`/api/1/studies/${sid}/computational-records/${id}/download`, { credentials: 'same-origin', signal: AbortSignal.timeout(30000) });
    if (actor !== this.actor) throw new Error('The session changed. No record export was downloaded.');
    if (!response.ok) {
      if (response.status === 401) { this.closeSession(); this.onAuthorizationLoss(); }
      const value = await response.json();
      throw new ApiError(value.error ?? { code:'resource_not_found', message:'This record export is unavailable.', fields:[], outcome:'unchanged' });
    }
    const reader = response.body?.getReader();
    if (!reader) throw new Error('The record export could not be read.');
    const chunks: Uint8Array<ArrayBuffer>[] = []; let size = 0;
    try {
      while (true) {
        const part = await reader.read(); if (part.done) break;
        size += part.value.byteLength;
        if (size > expected.size) { await reader.cancel(); throw new Error('Record export verification failed. No file was downloaded.'); }
        chunks.push(part.value as Uint8Array<ArrayBuffer>);
      }
    } finally { reader.releaseLock(); }
    const blob = new Blob(chunks, { type:'application/zip' });
    const hash = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', await blob.arrayBuffer())), b => b.toString(16).padStart(2,'0')).join('');
    if (actor !== this.actor || size !== expected.size || hash !== expected.sha256) throw new Error('Record export verification failed. No file was downloaded.');
    return blob;
  }
  /** A refused read keeps its error code so hosts classify it through readFailed;
   * the displayed sentence stays the same. 401 ends the session like every other read. */
  async artifact(sid: string, rid: string, artifact: { artifact_id: string; sha256: string; size: number }, signal?: AbortSignal) {
    const actor = this.actor, timeout = AbortSignal.timeout(30000);
    const response = await fetch(`/api/1/studies/${sid}/runs/${rid}/artifacts/${artifact.artifact_id}`, { credentials: 'same-origin', signal: signal ? AbortSignal.any([signal, timeout]) : timeout });
    signal?.throwIfAborted();
    if (actor !== this.actor) throw new Error('The session changed. This response was not applied.');
    if (!response.ok) {
      if (response.status === 401) { this.closeSession(); this.onAuthorizationLoss(); }
      // Same envelope handling as downloadComputationalRecord: the server error is kept as reported.
      const value = await response.json().catch(() => null);
      const unavailable = 'This run file is unavailable.';
      throw new ApiError(value?.error ? { ...value.error, message: unavailable } : { code: 'resource_not_found', message: unavailable, fields: [], outcome: 'unchanged' });
    }
    const raw = await response.arrayBuffer();
    const hash = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', raw)), b => b.toString(16).padStart(2, '0')).join('');
    if (raw.byteLength !== artifact.size || hash !== artifact.sha256) throw new Error('This file could not be verified. It was not downloaded.');
    return new Blob([raw], { type: 'application/octet-stream' });
  }
}

/** Explicit authoring upgrade. Historical readers never call this helper. */
export function descriptiveApproach(content: ApproachContent): ApproachContent2 {
  return content.schema_version === '2' ? content : {...content,schema_version:'2',original_question:null,elaboration:null,limit_items:[]};
}
