import type { AnalysisExecution1 } from './contract';
import type {
  AssistantBudgetRead2,
  AssistantConversationRead4,
  AssistantMessageRequest1,
} from './contract';
import type { ConfigurationSummary1 } from './contract';
import type {
  ConfigurationCommit6,
  ConfigurationPreview8,
  ConfigurationRequest6,
} from './contract';
import type {
  CalculationCreate4,
  CalculationEstimateRead2,
  CalculationExploration1,
  CalculationPredictionRequest1,
  CalculationPrediction1,
  CalculationEstimatePage2,
  CalculationEstimateRequest1,
  CalculationPage4,
  CalculationRunPage1,
  CalculationRunRequest1,
  CalculationRunRequestResult1,
  CalculationSampleOperationRead4,
  CalculationSamplePage4,
  CalculationSampleRequestRead4,
  CalculationVersionRead4,
  CalculationVersionPage4,
  CalculationVersionSave4,
  ReferenceMarkCommand1,
  ReferenceMarkList1,
  ReferenceMarkState1,
} from './contract';
import type {
  ModelExplanationDraftRead3,
  ModelExplanationDraftSaveRead3,
  ModelExplanationStateRead3,
  ModelExplanationVersionSave1,
  ModelExplanationVersionSavedRead3,
  ModelVersionExplanationRead3,
} from './contract';
import type {
  StudyAnswerDraftRead3,
  StudyAnswerDraftSaveRead3,
  StudyAnswerStateRead3,
  StudyAnswerVersionRead3,
  StudyAnswerVersionPageRead3,
  StudyAnswerVersionSave1,
  StudyAnswerVersionSavedRead3,
} from './contract';
import type {
  StudyBriefVersionRead2,
  StudyBriefDraftRead2,
  StudyBriefDraftSaveRead2,
  StudyBriefStateRead2,
  StudyBriefVersionPageRead2,
  StudyBriefVersionSave1,
  StudyBriefVersionSavedRead2,
} from './contract';
import type {
  Study,
  Association,
  ModelDraftRead5,
  ModelRevisionRead5,
  Edit2,
  Source,
  Error as ContractError,
  PublicReceipt,
  FrozenConfigurationRead7,
  PublicRun,
  PublicRunDetail2,
  RunHistoryItem2,
  RevisionSummary,
  EvidenceRecord,
  EvidenceCreate2,
  ExecutionReadiness,
  Session,
  ApplyRead5,
  ResultSourcePage,
  ModifiedRunSeed1,
  ApplicationCapabilities,
  RecordRequestRead as RecordRequest,
  RecordPreviewRequest,
  RecordCreateRequest,
} from './contract';
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
import type {
  ApproachState2,
  ApproachPreviewRequestRead2,
  ApproachPreviewRead3,
  ApproachDraftWriteRead2,
  ApproachDraftRead2,
  ApproachVersionSave1,
  ApproachVersionSavedRead3,
  ApproachRestore1,
  ApproachSavedRead3,
  ApproachPageRequest1,
  ApproachVersionPage2,
  ApproachUsageRequest1,
  ApproachUsagePage1,
  ApproachReceiptRead2,
  ApproachReceiptCategory1,
} from './contract';
import type { UnitCatalog2, PublicNewModel } from './contract';
import type { StudyArchiveCommand } from './contract';
import type { ReceiptError } from './contract';
import type { AgentAttribution1, AgentAttributionPage1 } from './contract';
export type * from './contract';
export type Envelope<T> = { schema_version: '1'; data: T; next_cursor?: string | null };
export type EvidencePage = Envelope<EvidenceRecord[]> & { next_cursor: string | null };
export type EvidenceQuery = {
  view?: 'heads' | 'versions';
  limit?: number;
  cursor?: string;
  scope_kind?:
    | 'study'
    | 'model_revision'
    | 'definition_version'
    | 'instance'
    | 'port'
    | 'connection'
    | 'configuration'
    | 'run'
    | 'criterion'
    | 'legacy';
  model_id?: string;
  model_revision_id?: string;
  instance_id?: string;
  port_id?: string;
  configuration_revision_id?: string;
  run_id?: string;
  legacy_scope?: string;
};
export type EvidenceSelector =
  | { model_revision_id: string; draft_revision?: never }
  | { draft_revision: string; model_revision_id?: never };
/** The recovery members of a receipt read's answer or of its 404 error object. */
type Recovery = Partial<Pick<ReceiptError['error'], 'recovery' | 'retry_after_s'>>;
export type EvidenceReceipt = Omit<PublicReceipt, 'result'> & { result: EvidenceRecord | null };
export class ApiError extends Error {
  constructor(public detail: ContractError['error']) {
    super(detail.message);
  }
}
/** One denial classification for every read host. These codes are a
 * confirmed denial; a concealed `resource_not_found` is confirmed by a study probe. */
export const accessDeniedCodes: readonly string[] = [
  'unauthenticated',
  'unauthorized',
  'forbidden',
];
export const accessDenied = (error: unknown) =>
  error instanceof ApiError && accessDeniedCodes.includes(error.detail.code);
const concealed = (error: unknown) =>
  error instanceof ApiError && error.detail.code === 'resource_not_found';
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
export type ReadFence = {
  readonly studyId?: string;
  signal: AbortSignal;
  valid(): boolean;
  abort(): void;
  done(): void;
};
/** stale: the fence no longer holds (session or access already changed);
 * access-lost: confirmed denial, already signalled; transient: the study probe
 * failed, keep content and offer a retry; error: an ordinary read failure. */
export type ReadFailure = 'stale' | 'access-lost' | 'transient' | 'error';
export function message(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.detail.code === 'stale_revision')
      return 'This model changed. Your edits are preserved; review the current revision.';
    if (error.detail.code === 'backend_unavailable')
      return 'Modeling is unavailable. Your edits are preserved. Retry the read when it is available.';
    if (error.detail.outcome === 'unknown' || error.detail.outcome === 'pending')
      return 'Command outcome is uncertain. Check the original command before making more changes.';
  }
  return error instanceof Error ? error.message : 'The request could not be completed.';
}
export async function sourceFromBytes(raw: Uint8Array): Promise<Source> {
  const digest = await crypto.subtle.digest('SHA-256', raw as Uint8Array<ArrayBuffer>);
  let binary = '';
  for (const byte of raw) binary += String.fromCharCode(byte);
  return {
    encoding: 'base64',
    media_type: 'text/x-python',
    bytes: btoa(binary),
    sha256: Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, '0')).join(''),
  };
}
export const sourceFromText = (text: string) => sourceFromBytes(new TextEncoder().encode(text));
export const sourceText = (source: Source) =>
  new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(
    Uint8Array.from(atob(source.bytes), (c) => c.charCodeAt(0)),
  );
// Closed typed commands are preserved from preview through apply/recovery.
export function validateEditCommand(command: ApplyRead5, snapshot?: ModelDraftRead5) {
  if (!command.edits.length || command.edits.length > 256)
    throw new Error('Batch must contain 1–256 edits; it will not be split.');
  if (new TextEncoder().encode(JSON.stringify(command)).length > 2 * 1024 * 1024)
    throw new Error('Batch exceeds the 2 MiB request limit; reduce the proposal.');
  for (const [row, edit] of command.edits.entries()) {
    const sources =
      edit.kind === 'create_definition'
        ? [edit.source]
        : edit.kind === 'revise_definition'
          ? edit.changes.flatMap((c) => (c.kind === 'set_source' ? [c.source] : []))
          : [];
    if (sources.some((source) => atob(source.bytes).length > 256 * 1024))
      throw new Error(`Row ${row + 1}: source exceeds 256 KiB.`);
  }
  if (
    snapshot &&
    snapshot.instances.length +
      snapshot.connections.length +
      snapshot.definitions.reduce((n, d) => n + d.ports.length, 0) >
      1000
  )
    throw new Error('Preview exceeds the 1000 element limit; reduce the proposal.');
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
  assistantBudget = async (sid?: string, signal?: AbortSignal) =>
    (
      await this.request<AssistantBudgetRead2>(
        sid ? `/studies/${sid}/assistant/budget` : '/assistant/budget',
        undefined,
        'GET',
        signal,
      )
    ).data;
  assistant = async (sid: string, signal?: AbortSignal, page: { after?: string; before?: string } = {}) =>
    (
      await this.request<AssistantConversationRead4>(
        `/studies/${sid}/assistant${Object.keys(page).length ? `?${new URLSearchParams(page)}` : ''}`,
        undefined,
        'GET',
        signal,
      )
    ).data;
  assistantSend = async (sid: string, body: AssistantMessageRequest1) =>
    (
      await this.request<AssistantConversationRead4>(
        `/studies/${sid}/assistant/messages`,
        body,
        'POST',
      )
    ).data;
  assistantResume = async (sid: string) =>
    (await this.request<AssistantConversationRead4>(`/studies/${sid}/assistant/resume`, {}, 'POST'))
      .data;
  assistantStop = async (sid: string) =>
    (await this.request<AssistantConversationRead4>(`/studies/${sid}/assistant/stop`, {}, 'POST'))
      .data;
  /** The study brief: its draft and latest saved version, the saved versions (newest first,
   * paged by version number), and the draft and version commands on the shared receipt path. */
  brief = async (sid: string, signal?: AbortSignal) =>
    (await this.request<StudyBriefStateRead2>(`/studies/${sid}/brief`, undefined, 'GET', signal)).data;
  briefVersions = async (sid: string, before?: number, signal?: AbortSignal) =>
    (
      await this.request<StudyBriefVersionPageRead2>(
        `/studies/${sid}/brief/versions?limit=100${before === undefined ? '' : `&before=${before}`}`,
        undefined,
        'GET',
        signal,
      )
    ).data;
  briefVersion = async (sid: string, versionId: string, signal?: AbortSignal) =>
    (
      await this.request<StudyBriefVersionRead2>(
        `/studies/${sid}/brief/versions/${versionId}`,
        undefined,
        'GET',
        signal,
      )
    ).data;
  saveBriefDraft = async (sid: string, body: StudyBriefDraftSaveRead2) =>
    (await this.mutate<StudyBriefDraftRead2>(`/studies/${sid}/brief/draft`, body, 'brief_draft', sid))
      .data;
  saveBriefVersion = async (sid: string, body: StudyBriefVersionSave1) =>
    (
      await this.mutate<StudyBriefVersionSavedRead2>(
        `/studies/${sid}/brief/versions`,
        body,
        'brief_version',
        sid,
      )
    ).data;
  /** Model explanations (ADR-0007): a model's explanation draft and latest saved explanation,
   * the explanation saved for one model version (null when none was saved), and the draft and
   * version commands on the shared receipt path. Reads never depend on the modeling service. */
  modelExplanation = async (sid: string, mid: string, signal?: AbortSignal) =>
    (
      await this.request<ModelExplanationStateRead3>(
        modelPath(sid, mid) + '/explanation',
        undefined,
        'GET',
        signal,
      )
    ).data;
  modelVersionExplanation = async (sid: string, mid: string, rid: string, signal?: AbortSignal) =>
    (
      await this.request<ModelVersionExplanationRead3>(
        modelPath(sid, mid) + `/revisions/${rid}/explanation`,
        undefined,
        'GET',
        signal,
      )
    ).data;
  saveModelExplanationDraft = async (sid: string, mid: string, body: ModelExplanationDraftSaveRead3) =>
    (
      await this.mutate<ModelExplanationDraftRead3>(
        modelPath(sid, mid) + '/explanation/draft',
        body,
        'model_explanation_draft',
        sid,
      )
    ).data;
  saveModelExplanationVersion = async (
    sid: string,
    mid: string,
    body: ModelExplanationVersionSave1,
  ) =>
    (
      await this.mutate<ModelExplanationVersionSavedRead3>(
        modelPath(sid, mid) + '/explanation/versions',
        body,
        'model_explanation_version',
        sid,
      )
    ).data;
  /** The study answer (ADR-0008, ADR-0010): its draft and latest saved version, the saved
   * versions (newest first, paged by version number), and the draft and version commands. */
  studyAnswer = async (sid: string, signal?: AbortSignal) =>
    (await this.request<StudyAnswerStateRead3>(`/studies/${sid}/answer`, undefined, 'GET', signal))
      .data;
  studyAnswerVersions = async (sid: string, before?: number, signal?: AbortSignal) =>
    (
      await this.request<StudyAnswerVersionPageRead3>(
        `/studies/${sid}/answer/versions?limit=100` +
          (before === undefined ? '' : `&before=${before}`),
        undefined,
        'GET',
        signal,
      )
    ).data;
  studyAnswerVersion = async (sid: string, versionId: string, signal?: AbortSignal) =>
    (
      await this.request<StudyAnswerVersionRead3>(
        `/studies/${sid}/answer/versions/${versionId}`,
        undefined,
        'GET',
        signal,
      )
    ).data;
  saveStudyAnswerDraft = async (sid: string, body: StudyAnswerDraftSaveRead3) =>
    (
      await this.mutate<StudyAnswerDraftRead3>(
        `/studies/${sid}/answer/draft`,
        body,
        'answer_draft',
        sid,
      )
    ).data;
  saveStudyAnswerVersion = async (sid: string, body: StudyAnswerVersionSave1) =>
    (
      await this.mutate<StudyAnswerVersionSavedRead3>(
        `/studies/${sid}/answer/versions`,
        body,
        'answer_version',
        sid,
      )
    ).data;
  /** Every calculation of the study with its latest version, in creation order. */
  studyCalculations = async (sid: string, after?: number, signal?: AbortSignal) =>
    (
      await this.request<CalculationPage4>(
        `/studies/${sid}/analyses?limit=100${after === undefined ? '' : `&after=${after}`}`,
        undefined,
        'GET',
        signal,
      )
    ).data;
  /** Calculations (ADR-0009, ADR-0010): pages of calculations with their latest version, the
   * exact versions, their runs evaluated against the pinned brief criteria (at most 20 a page),
   * the create and new-version commands, and the reference marks of configuration versions. */
  calculations = async (
    sid: string,
    modelRevisionId: string,
    after?: number,
    signal?: AbortSignal,
  ) =>
    (
      await this.request<CalculationPage4>(
        `/studies/${sid}/analyses?limit=100&model_revision_id=${modelRevisionId}${after === undefined ? '' : `&after=${after}`}`,
        undefined,
        'GET',
        signal,
      )
    ).data;
  calculationVersions = async (
    sid: string,
    calculationId: string,
    before?: number,
    signal?: AbortSignal,
  ) =>
    (
      await this.request<CalculationVersionPage4>(
        `/studies/${sid}/analyses/${calculationId}/versions?limit=100${before === undefined ? '' : `&before=${before}`}`,
        undefined,
        'GET',
        signal,
      )
    ).data;
  calculationVersion = async (sid: string, versionId: string, signal?: AbortSignal) =>
    (
      await this.request<CalculationVersionRead4>(
        `/studies/${sid}/analysis-versions/${versionId}`,
        undefined,
        'GET',
        signal,
      )
    ).data;
  calculationRuns = async (
    sid: string,
    versionId: string,
    after?: number,
    signal?: AbortSignal,
    configurationRevisionId?: string,
  ) =>
    (
      await this.request<CalculationRunPage1>(
        `/studies/${sid}/analysis-versions/${versionId}/runs?${new URLSearchParams({
          ...(after === undefined ? {} : { after: String(after) }),
          ...(configurationRevisionId
            ? { configuration_revision_id: configurationRevisionId }
            : {}),
        })}`,
        undefined,
        'GET',
        signal,
      )
    ).data;
  createCalculation = async (sid: string, body: CalculationCreate4) =>
    (
      await this.mutate<CalculationVersionRead4>(
        `/studies/${sid}/analyses`,
        body,
        'calculation_create',
        sid,
      )
    ).data;
  saveCalculationVersion = async (
    sid: string,
    calculationId: string,
    body: CalculationVersionSave4,
  ) =>
    (
      await this.mutate<CalculationVersionRead4>(
        `/studies/${sid}/analyses/${calculationId}/versions`,
        body,
        'calculation_version',
        sid,
      )
    ).data;
  /** Sampled versions (ADR-0009): a sampling operation generates the points and saves the
   * version; it is accepted at once and advanced by the dispatcher. */
  sampleCalculation = async (sid: string, body: CalculationSampleRequestRead4) =>
    (
      await this.mutate<CalculationSampleOperationRead4>(
        `/studies/${sid}/analysis-samples`,
        body,
        'calculation_sample',
        sid,
      )
    ).data;
  calculationSample = async (sid: string, operationId: string, signal?: AbortSignal) =>
    (
      await this.request<CalculationSampleOperationRead4>(
        `/studies/${sid}/analysis-samples/${operationId}`,
        undefined,
        'GET',
        signal,
      )
    ).data;
  calculationSamples = async (sid: string, signal?: AbortSignal) =>
    (
      await this.request<CalculationSamplePage4>(
        `/studies/${sid}/analysis-samples`,
        undefined,
        'GET',
        signal,
      )
    ).data;
  analysisExecution = async (sid: string, versionId: string, signal?: AbortSignal) =>
    (
      await this.request<AnalysisExecution1 | null>(
        `/studies/${sid}/analysis-versions/${versionId}/execution`,
        undefined,
        'GET',
        signal,
      )
    ).data;
  launchAnalysis = async (sid: string, versionId: string) =>
    (
      await this.request<AnalysisExecution1>(
        `/studies/${sid}/analysis-versions/${versionId}/execution`,
        {},
        'POST',
      )
    ).data;
  /** Ordinary runs for named members; repeating the same command returns the same runs. */
  requestCalculationRuns = async (sid: string, versionId: string, body: CalculationRunRequest1) =>
    (
      await this.request<CalculationRunRequestResult1>(
        `/studies/${sid}/analysis-versions/${versionId}/run-requests`,
        body,
        'POST',
      )
    ).data;
  /** Estimates fitted to one sampled calculation version;
   * their values are never calculated results. */
  buildCalculationEstimate = async (sid: string, body: CalculationEstimateRequest1) =>
    (
      await this.mutate<CalculationEstimateRead2>(
        `/studies/${sid}/analysis-estimates`,
        body,
        'calculation_estimate',
        sid,
      )
    ).data;
  calculationEstimate = async (sid: string, estimateId: string, signal?: AbortSignal) =>
    (
      await this.request<CalculationEstimateRead2>(
        `/studies/${sid}/analysis-estimates/${estimateId}`,
        undefined,
        'GET',
        signal,
      )
    ).data;
  calculationEstimates = async (
    sid: string,
    versionId: string,
    cursor?: string,
    signal?: AbortSignal,
  ) =>
    (
      await this.request<CalculationEstimatePage2>(
        `/studies/${sid}/analysis-versions/${versionId}/estimates` +
          (cursor ? `?cursor=${cursor}` : ''),
        undefined,
        'GET',
        signal,
      )
    ).data;
  calculationExploration = async (
    sid: string,
    versionId: string,
    group: number,
    estimateId?: string | null,
    signal?: AbortSignal,
  ) => {
    try {
      return (
        await this.request<CalculationExploration1>(
          `/studies/${sid}/analysis-versions/${versionId}/exploration?group=${group + 1}` +
            (estimateId ? `&estimate_id=${estimateId}` : ''),
          undefined,
          'GET',
          signal,
          90000,
        )
      ).data;
    } catch (error) {
      if (error instanceof DOMException && error.name === 'TimeoutError')
        throw new Error('Checking saved calculations took too long. Retry loading results.');
      throw error;
    }
  };
  predictCalculation = async (
    sid: string,
    estimateId: string,
    body: CalculationPredictionRequest1,
    signal?: AbortSignal,
  ) =>
    (
      await this.request<CalculationPrediction1>(
        `/studies/${sid}/analysis-estimates/${estimateId}/predictions`,
        body,
        'POST',
        signal,
      )
    ).data;
  referenceMarks = async (sid: string, modelId?: string, signal?: AbortSignal) =>
    (
      await this.request<ReferenceMarkList1>(
        `/studies/${sid}/reference-marks${modelId ? `?model_id=${modelId}` : ''}`,
        undefined,
        'GET',
        signal,
      )
    ).data;
  setReferenceMark = async (
    sid: string,
    configurationRevisionId: string,
    action: 'set' | 'clear',
  ) =>
    (
      await this.mutate<ReferenceMarkState1>(
        `/studies/${sid}/reference-marks`,
        {
          command_id: crypto.randomUUID(),
          configuration_revision_id: configurationRevisionId,
          action,
        } as ReferenceMarkCommand1,
        'reference_mark',
        sid,
      )
    ).data;
  unitCatalog = async (sid: string, signal?: AbortSignal) =>
    (await this.request<UnitCatalog2>(`/studies/${sid}/unit-catalog`, undefined, 'GET', signal))
      .data;

  modifiedRunSeedRead = async (sid: string, rid: string, signal?: AbortSignal) =>
    (
      await this.request<ModifiedRunSeedRead6>(
        `/studies/${sid}/runs/${rid}/modified-run-seed`,
        undefined,
        'GET',
        signal,
      )
    ).data;
  async modifiedRunSeed(sid: string, rid: string): Promise<ModifiedRunSeed1> {
    const seed = await this.modifiedRunSeedRead(sid, rid);
    if (seed.schema_version !== '1')
      throw new Error('This configuration requires the assumptions-aware modified-run editor.');
    return seed;
  }
  csrf = '';
  actor = '';
  hosted = false;
  onAuthorizationLoss = () => {};
  private recovery = new Map<string, { pending: HyprnMvpApi['pending']; retryReady: boolean }>();
  private closeSession() {
    if (!this.hosted && this.pending && this.actor)
      this.recovery.set(this.actor, { pending: this.pending, retryReady: this.retryReady });
    this.pending = null;
    this.retryReady = false;
    this.csrf = '';
    this.actor = '';
    if (this.hosted) this.recovery.clear();
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
    return () => {
      this.sessionListeners.delete(listener);
    };
  }
  private emit(change: SessionChange) {
    // Invalidate before notifying: no late reply may repopulate a cleared host.
    if (change.kind === 'access-lost')
      this.accessEpochs.set(change.studyId, (this.accessEpochs.get(change.studyId) ?? 0) + 1);
    else this.sessionEpoch++;
    for (const read of [...this.openReads])
      if (change.kind !== 'access-lost' || read.studyId === change.studyId) {
        read.abort.abort();
        this.openReads.delete(read);
      }
    for (const listener of [...this.sessionListeners]) listener(change);
  }
  /** Confirmed denial for one study: invalidates its fences, aborts its open reads and signals hosts. */
  accessLost(studyId: string) {
    this.emit({ kind: 'access-lost', studyId });
  }
  fence(scope: { studyId?: string } = {}): ReadFence {
    const actor = this.actor,
      csrf = this.csrf,
      session = this.sessionEpoch,
      studyId = scope.studyId;
    const access = studyId === undefined ? 0 : (this.accessEpochs.get(studyId) ?? 0);
    const entry = { studyId, abort: new AbortController() };
    this.openReads.add(entry);
    return {
      studyId,
      signal: entry.abort.signal,
      abort: () => entry.abort.abort(),
      done: () => {
        this.openReads.delete(entry);
      },
      valid: () =>
        !entry.abort.signal.aborted &&
        actor === this.actor &&
        csrf === this.csrf &&
        session === this.sessionEpoch &&
        (studyId === undefined || access === (this.accessEpochs.get(studyId) ?? 0)),
    };
  }
  /** Probe current study access once per study, session and access epoch; concurrent callers share it. */
  async confirmAccess(fence: ReadFence, studyId = fence.studyId): Promise<ReadFailure | 'ok'> {
    if (!fence.valid()) return 'stale';
    if (studyId === undefined) return 'error';
    const key = [
      studyId,
      this.actor,
      this.csrf,
      this.sessionEpoch,
      this.accessEpochs.get(studyId) ?? 0,
    ].join('\u0000');
    let probe = this.probes.get(key);
    if (!probe) {
      const scope = this.fence({ studyId });
      probe = this.study(studyId, scope.signal)
        .then(
          (): ReadFailure | 'ok' => 'ok',
          (error): ReadFailure | 'ok' => {
            if (!scope.valid()) return 'stale';
            if (accessDenied(error) || concealed(error)) {
              this.accessLost(studyId);
              return 'access-lost';
            }
            return 'transient';
          },
        )
        .finally(() => {
          scope.done();
          this.probes.delete(key);
        });
      this.probes.set(key, probe);
    }
    const outcome = await probe;
    if (outcome === 'access-lost') return 'access-lost';
    return fence.valid() ? outcome : 'stale';
  }
  /** Shared read-failure classification for every protected-content host. A failed
   * command (`command: true`) may be refused for its role, not for read access: a
   * `forbidden` there is confirmed by the study probe instead of clearing directly. */
  async readFailed(
    error: unknown,
    fence: ReadFence,
    options: { command?: boolean } = {},
  ): Promise<ReadFailure> {
    const studyId = fence.studyId;
    if (!fence.valid()) return 'stale';
    const roleRefusal =
      options.command && error instanceof ApiError && error.detail.code === 'forbidden';
    if (accessDenied(error) && !roleRefusal) {
      if (studyId !== undefined) this.accessLost(studyId);
      return 'access-lost';
    }
    if ((concealed(error) || roleRefusal) && studyId !== undefined) {
      const outcome = await this.confirmAccess(fence, studyId);
      if (outcome !== 'ok') return outcome;
    }
    return fence.valid() ? 'error' : 'stale';
  }
  onPendingChange = () => {};
  retryReady = false;
  pending: {
    path: string;
    body: { command_id: string };
    method: string;
    category: string;
    study?: string;
  } | null = null;
  async request<T>(
    path: string,
    body?: unknown,
    method = body === undefined ? 'GET' : 'POST',
    signal?: AbortSignal,
    timeoutMs = 30000,
  ): Promise<Envelope<T>> {
    const actor = this.actor;
    const requestSession = this.sessionEpoch;
    const timeout = AbortSignal.timeout(timeoutMs);
    const result = await fetch('/api/1' + path, {
      method,
      credentials: 'same-origin',
      redirect: this.hosted ? 'manual' : 'follow',
      signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
      headers:
        body === undefined ? {} : { 'Content-Type': 'application/json', 'X-CSRF-Token': this.csrf },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    // Access can return an HTML denial/redirect; it must still clear private state.
    if (this.hosted && actor === this.actor && requestSession === this.sessionEpoch &&
        (result.status === 401 || result.status === 403 || result.redirected || result.type === 'opaqueredirect')) {
      this.closeSession();
      this.onAuthorizationLoss();
    }
    const value = await result.json();
    signal?.throwIfAborted();
    if (path !== '/session' && actor !== this.actor)
      throw new Error('The session changed. This response was not applied.');
    if (!result.ok) {
      if (result.status === 401 && path !== '/session') {
        this.closeSession();
        this.onAuthorizationLoss();
      }
      throw new ApiError(
        value.error ?? {
          code: 'invalid_request',
          message: 'The request was rejected. Review the entered values.',
          fields: [],
          outcome: 'unchanged',
        },
      );
    }
    return value;
  }
  async login(username: string, password: string) {
    const result = await this.request<Session>('/session', { username, password });
    this.csrf = result.data.csrf_token;
    this.actor = result.data.actor_id;
    const recovery = this.recovery.get(this.actor);
    this.pending = recovery?.pending ?? null;
    this.retryReady = recovery?.retryReady ?? false;
    this.recovery.delete(this.actor);
    this.emit({ kind: 'signed-in', actor: this.actor });
    return result.data.profile;
  }
  async sessionMode() {
    const result = await this.request<import('./contract').SessionMode>('/session/mode');
    this.hosted = result.data.mode === 'hosted';
    return result.data.mode;
  }
  async bootstrap() {
    this.closeSession();
    this.onAuthorizationLoss();
    const result = await this.request<Session>('/session/external', {});
    this.csrf = result.data.csrf_token;
    this.actor = result.data.actor_id;
    this.emit({ kind: 'signed-in', actor: this.actor });
    return result.data.profile;
  }
  async profile() {
    return (await this.request<import('./contract').UserProfile1>('/profile')).data;
  }
  async saveProfile(display_alias: string | null, expected_revision: number) {
    return (await this.request<import('./contract').UserProfile1>(
      '/profile', { display_alias, expected_revision }, 'PUT',
    )).data;
  }
  async logout() {
    try { await this.request('/session', {}, 'DELETE'); }
    finally { this.closeSession(); this.onAuthorizationLoss(); }
  }
  async mutate<T>(
    path: string,
    body: { command_id: string },
    category: string,
    study?: string,
    method = 'POST',
    signal?: AbortSignal,
  ): Promise<Envelope<T>> {
    if (this.pending) throw new Error('Check the original command before making more changes.');
    const command = { path, body: structuredClone(body), method, category, study };
    const actor = this.actor;
    this.retryReady = false;
    try {
      const result = await this.request<T>(path, command.body, method, signal);
      // Accepted remote model commands can be pending without an HTTP error.
      if (
        'state' in (result.data as object) &&
        (result.data as { state: string }).state === 'pending_remote'
      ) {
        this.pending = command;
        throw new Error('Command outcome is uncertain. Check the original command.');
      }
      return result;
    } catch (error) {
      if (actor !== this.actor) {
        if (actor) this.recovery.set(actor, { pending: command, retryReady: false });
        throw error;
      }
      if (!(error instanceof ApiError) || ['unknown', 'pending'].includes(error.detail.outcome))
        this.pending = command;
      throw error;
    } finally {
      this.onPendingChange();
    }
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
    const all: T[] = [];
    let cursor: string | null | undefined;
    do {
      const page = await this.request<T[]>(
        path +
          (cursor ? `${path.includes('?') ? '&' : '?'}cursor=${encodeURIComponent(cursor)}` : ''),
        undefined,
        'GET',
        signal,
      );
      all.push(...page.data);
      cursor = page.next_cursor;
    } while (cursor);
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
  archiveStudy = async (sid: string, command: StudyArchiveCommand) =>
    (await this.mutate<Study>(`/studies/${sid}/archive`, command, 'study_archive', sid)).data;
  restoreStudy = async (sid: string, command: StudyArchiveCommand) =>
    (await this.mutate<Study>(`/studies/${sid}/restore`, command, 'study_archive', sid)).data;
  study = async (sid: string, signal?: AbortSignal) =>
    (await this.request<Study>(`/studies/${sid}`, undefined, 'GET', signal)).data;
  createStudy = async (name: string, commandId = crypto.randomUUID()) =>
    (
      await this.mutate<Study>(
        '/studies',
        { command_id: commandId, name } as { command_id: string },
        'study_create',
      )
    ).data;
  models = (sid: string, signal?: AbortSignal) =>
    this.list<Association>(`/studies/${sid}/models`, signal);
  model = async (sid: string, mid: string, signal?: AbortSignal) =>
    (await this.request<ModelDraftRead5>(modelPath(sid, mid), undefined, 'GET', signal)).data;
  revisions = (sid: string, mid: string, signal?: AbortSignal) =>
    this.list<RevisionSummary>(modelPath(sid, mid) + '/revisions', signal);
  revision = async (sid: string, mid: string, rid: string, signal?: AbortSignal) =>
    (
      await this.request<ModelRevisionRead5>(
        modelPath(sid, mid) + '/revisions/' + rid,
        undefined,
        'GET',
        signal,
      )
    ).data;
  evidence = (sid: string, signal?: AbortSignal) =>
    this.list<EvidenceRecord>(`/studies/${sid}/evidence`, signal);
  evidencePage = async (
    sid: string,
    options: EvidenceQuery = {},
    signal?: AbortSignal,
  ): Promise<EvidencePage> => {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(options))
      if (value !== undefined) query.set(key, String(value));
    const page = await this.request<EvidenceRecord[]>(
      `/studies/${sid}/evidence?${query}`,
      undefined,
      'GET',
      signal,
    );
    return { ...page, next_cursor: page.next_cursor ?? null };
  };
  evidenceVersion = async (sid: string, version: string, signal?: AbortSignal) =>
    (
      await this.request<EvidenceRecord>(
        `/studies/${sid}/evidence/${version}`,
        undefined,
        'GET',
        signal,
      )
    ).data;
  evidenceFamily = async (sid: string, family: string, signal?: AbortSignal) =>
    (
      await this.request<EvidenceFamily3>(
        `/studies/${sid}/evidence-families/${family}`,
        undefined,
        'GET',
        signal,
      )
    ).data;
  evidenceVersions = async (
    sid: string,
    family: string,
    options: Pick<EvidenceQuery, 'limit' | 'cursor'> = {},
    signal?: AbortSignal,
  ): Promise<EvidencePage> => {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(options))
      if (value !== undefined) query.set(key, String(value));
    const page = await this.request<EvidenceRecord[]>(
      `/studies/${sid}/evidence-families/${family}/versions?${query}`,
      undefined,
      'GET',
      signal,
    );
    return { ...page, next_cursor: page.next_cursor ?? null };
  };
  createEvidence = async (
    sid: string,
    value: Omit<EvidenceCreate2, 'command_id'> | Omit<EvidenceCreate3, 'command_id'>,
  ) =>
    (
      await this.mutate<EvidenceRecord>(
        `/studies/${sid}/evidence`,
        { ...value, command_id: crypto.randomUUID() },
        'evidence',
        sid,
      )
    ).data;
  createEvidenceCommand = async (sid: string, command: EvidenceCreate3, signal?: AbortSignal) =>
    (
      await this.mutate<EvidenceRecord3>(
        `/studies/${sid}/evidence`,
        command,
        'evidence',
        sid,
        'POST',
        signal,
      )
    ).data;
  reviseEvidence = async (
    sid: string,
    family: string,
    command: EvidenceRevise3,
    signal?: AbortSignal,
  ) =>
    (
      await this.mutate<EvidenceRecord3>(
        `/studies/${sid}/evidence-families/${family}/versions`,
        command,
        'evidence',
        sid,
        'POST',
        signal,
      )
    ).data;
  evidenceReceipt = async (sid: string, command: string, signal?: AbortSignal) =>
    (
      await this.request<EvidenceReceipt>(
        `/studies/${sid}/commands/${command}?category=evidence`,
        undefined,
        'GET',
        signal,
      )
    ).data;
  assumptionEvidence = async (
    sid: string,
    mid: string,
    selector: EvidenceSelector,
    signal?: AbortSignal,
  ) => {
    const query = new URLSearchParams();
    if (selector.model_revision_id !== undefined)
      query.set('model_revision_id', selector.model_revision_id);
    if (selector.draft_revision !== undefined) query.set('draft_revision', selector.draft_revision);
    return (
      await this.request<AssumptionEvidenceResolution1>(
        modelPath(sid, mid) + '/assumption-evidence?' + query,
        undefined,
        'GET',
        signal,
      )
    ).data;
  };
  readiness = async (sid: string) =>
    (await this.request<ExecutionReadiness>(`/studies/${sid}/execution-readiness`)).data;
  capabilities = async (signal?: AbortSignal) =>
    (await this.request<ApplicationCapabilities>('/capabilities', undefined, 'GET', signal)).data;
  configuration = async (sid: string, rid: string, signal?: AbortSignal) =>
    (
      await this.request<FrozenConfigurationRead7>(
        `/studies/${sid}/configurations/${rid}`,
        undefined,
        'GET',
        signal,
      )
    ).data;
  createModelCommand = async (sid: string, command: PublicNewModel) =>
    (await this.mutate<ModelDraftRead5>(`/studies/${sid}/models`, command, 'model', sid)).data;
  createModel = async (study: Study, name: string, template: 'empty' | 'two_component_example') =>
    this.createModelCommand(study.study_id, {
      command_id: crypto.randomUUID(),
      expected_revision: study.revision,
      name,
      template,
    });
  previewEdits = async (model: ModelDraftRead5, command: ApplyRead5) => {
    validateEditCommand(command);
    const { command_id: _commandId, ...preview }: ApplyRead5 = command;
    const value = (
      await this.request<ModelDraftRead5>(
        modelPath(model.study_id, model.model_id) + '/preview',
        preview,
      )
    ).data;
    validateEditCommand(command, value);
    return value;
  };
  applyCommand = async (model: ModelDraftRead5, command: ApplyRead5) => {
    validateEditCommand(command);
    return (
      await this.mutate<ModelDraftRead5>(
        modelPath(model.study_id, model.model_id) + '/edits',
        command,
        'model',
        model.study_id,
      )
    ).data;
  };
  apply = async (model: ModelDraftRead5, edits: Edit2[]) => {
    if (['3', '4', '5'].includes(model.schema_version))
      throw new Error('Use an explicit version3 or version4 command for this model.');
    return this.applyCommand(model, {
      schema_version: '2',
      command_id: crypto.randomUUID(),
      expected_revision: model.draft_revision,
      edits,
    });
  };
  commitModel = async (model: ModelDraftRead5) =>
    (
      await this.mutate<ModelRevisionRead5>(
        modelPath(model.study_id, model.model_id) + '/commits',
        { command_id: crypto.randomUUID(), expected_revision: model.draft_revision } as {
          command_id: string;
        },
        'model',
        model.study_id,
      )
    ).data;
  configurationSummaries = (
    sid: string,
    query: { model_id?: string; model_revision_id?: string; cursor?: string } = {},
    signal?: AbortSignal,
  ) => {
    const params = new URLSearchParams({ limit: '50' });
    for (const [key, value] of Object.entries(query)) if (value) params.set(key, value);
    return this.request<ConfigurationSummary1[]>(
      `/studies/${sid}/configuration-summaries?${params}`,
      undefined,
      'GET',
      signal,
    );
  };
  runsPage = (
    sid: string,
    query: { model_id?: string; model_revision_id?: string; cursor?: string } = {},
    signal?: AbortSignal,
  ) => {
    const params = new URLSearchParams({ limit: '20', newest_first: 'true' });
    for (const [key, value] of Object.entries(query)) if (value) params.set(key, value);
    return this.request<RunHistoryItem2[]>(
      `/studies/${sid}/runs?${params}`,
      undefined,
      'GET',
      signal,
    );
  };
  configurations = (sid: string, signal?: AbortSignal) =>
    this.list<FrozenConfigurationRead7>(`/studies/${sid}/configurations`, signal);
  resultSourcesPage = async (study: string, limit = 25, cursor?: string) => {
    const query = new URLSearchParams({ limit: String(limit) });
    if (cursor !== undefined) query.set('cursor', cursor);
    return (await this.request<ResultSourcePage>(`/studies/${study}/result-sources?${query}`)).data;
  };
  /** New configurations: version 6 only (no criteria, no approach binding). */
  previewConfiguration6 = async (candidate: ConfigurationRequest6, signal?: AbortSignal) =>
    (
      await this.request<ConfigurationPreview8>(
        `/studies/${candidate.study_id}/configurations/preview`,
        candidate,
        'POST',
        signal,
      )
    ).data;
  commitConfiguration6 = async (body: ConfigurationCommit6) =>
    (
      await this.mutate<FrozenConfigurationRead7>(
        `/studies/${body.configuration.study_id}/configurations`,
        body,
        'configuration',
        body.configuration.study_id,
      )
    ).data;
  submitRun = async (sid: string, revision: string) =>
    (
      await this.mutate<PublicRun>(
        `/studies/${sid}/runs`,
        { command_id: crypto.randomUUID(), configuration_revision_id: revision } as {
          command_id: string;
        },
        'run',
        sid,
      )
    ).data;
  runs = (sid: string, signal?: AbortSignal) => this.list<RunHistoryItem2>(`/studies/${sid}/runs`, signal);
  run = async (sid: string, rid: string, signal?: AbortSignal) =>
    (await this.request<PublicRunDetail2>(`/studies/${sid}/runs/${rid}`, undefined, 'GET', signal)).data;
  previewComputationalRecord = async (sid: string, body: RecordPreviewRequest) =>
    (
      await this.mutate<RecordRequest>(
        `/studies/${sid}/computational-record-previews`,
        body,
        'computational_record_preview',
        sid,
      )
    ).data;
  createComputationalRecord = async (sid: string, body: RecordCreateRequest) =>
    (
      await this.mutate<RecordRequest>(
        `/studies/${sid}/computational-records`,
        body,
        'computational_record_create',
        sid,
      )
    ).data;
  computationalRecord = async (sid: string, id: string, signal?: AbortSignal) =>
    (
      await this.request<RecordRequest>(
        `/studies/${sid}/computational-records/${id}`,
        undefined,
        'GET',
        signal,
      )
    ).data;
  async downloadComputationalRecord(
    sid: string,
    id: string,
    expected: NonNullable<RecordRequest['download']>,
  ) {
    const actor = this.actor;
    if (expected.size < 1 || expected.size > 33554432)
      throw new Error('The record export exceeds the download limit.');
    const response = await fetch(`/api/1/studies/${sid}/computational-records/${id}/download`, {
      credentials: 'same-origin',
      signal: AbortSignal.timeout(30000),
    });
    if (actor !== this.actor)
      throw new Error('The session changed. No record export was downloaded.');
    if (!response.ok) {
      if (response.status === 401) {
        this.closeSession();
        this.onAuthorizationLoss();
      }
      const value = await response.json();
      throw new ApiError(
        value.error ?? {
          code: 'resource_not_found',
          message: 'This record export is unavailable.',
          fields: [],
          outcome: 'unchanged',
        },
      );
    }
    const reader = response.body?.getReader();
    if (!reader) throw new Error('The record export could not be read.');
    const chunks: Uint8Array<ArrayBuffer>[] = [];
    let size = 0;
    try {
      while (true) {
        const part = await reader.read();
        if (part.done) break;
        size += part.value.byteLength;
        if (size > expected.size) {
          await reader.cancel();
          throw new Error('Record export verification failed. No file was downloaded.');
        }
        chunks.push(part.value as Uint8Array<ArrayBuffer>);
      }
    } finally {
      reader.releaseLock();
    }
    const blob = new Blob(chunks, { type: 'application/zip' });
    const hash = Array.from(
      new Uint8Array(await crypto.subtle.digest('SHA-256', await blob.arrayBuffer())),
      (b) => b.toString(16).padStart(2, '0'),
    ).join('');
    if (actor !== this.actor || size !== expected.size || hash !== expected.sha256)
      throw new Error('Record export verification failed. No file was downloaded.');
    return blob;
  }
  /** A refused read keeps its error code so hosts classify it through readFailed;
   * the displayed sentence stays the same. 401 ends the session like every other read. */
  async artifact(
    sid: string,
    rid: string,
    artifact: { artifact_id: string; sha256: string; size: number },
    signal?: AbortSignal,
  ) {
    const actor = this.actor,
      timeout = AbortSignal.timeout(30000);
    const response = await fetch(
      `/api/1/studies/${sid}/runs/${rid}/artifacts/${artifact.artifact_id}`,
      { credentials: 'same-origin', signal: signal ? AbortSignal.any([signal, timeout]) : timeout },
    );
    signal?.throwIfAborted();
    if (actor !== this.actor)
      throw new Error('The session changed. This response was not applied.');
    if (!response.ok) {
      if (response.status === 401) {
        this.closeSession();
        this.onAuthorizationLoss();
      }
      // Same envelope handling as downloadComputationalRecord: the server error is kept as reported.
      const value = await response.json().catch(() => null);
      const unavailable = 'This run file is unavailable.';
      throw new ApiError(
        value?.error
          ? { ...value.error, message: unavailable }
          : { code: 'resource_not_found', message: unavailable, fields: [], outcome: 'unchanged' },
      );
    }
    const raw = await response.arrayBuffer();
    const hash = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', raw)), (b) =>
      b.toString(16).padStart(2, '0'),
    ).join('');
    if (raw.byteLength !== artifact.size || hash !== artifact.sha256)
      throw new Error('This file could not be verified. It was not downloaded.');
    return new Blob([raw], { type: 'application/octet-stream' });
  }
}
