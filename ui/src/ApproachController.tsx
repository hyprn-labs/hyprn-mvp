import type { ApproachContent2, ApproachPreviewRequestRead2 } from './contract';
import type { ApproachContent } from './api';
import { useSyncExternalStore } from 'react';
import { ApiError, HyprnMvpApi, accessDenied, accessLostText, accessUnverifiedText, message, type SessionChange } from './api';
import type { EditorGuard } from './workspaceModel';
import type { ApproachState2, ApproachSavedRead3, ApproachPreviewRead3, ApproachDraftRead2, ApproachVersionSavedRead3, ApproachReceiptCategory1, Diagnostic } from './contract';

export const emptyApproach = (): ApproachContent2 => ({ schema_version: '2', original_question: null, elaboration: null, limit_items: [], question: '', scope: '', limitations: '', open_questions: '', model_bindings: [], steps: [], assumptions: [], cases: [], basis_refs: [] });
export type ApproachControllerState = {
  studyId: string | null; status: 'idle' | 'loading' | 'ready' | 'working' | 'stale' | 'uncertain' | 'error';
  server: ApproachState2 | null; local: ApproachContent | null; saved: ApproachSavedRead3 | null;
  preview: ApproachPreviewRead3 | null; latest: ApproachState2 | null; error: string; diagnostics: Diagnostic[];
  /** Confirmed access loss for `studyId` while unsaved local edits existed: every
   * server-derived projection is cleared and nothing is displayed; only the user's own
   * unsaved edits remain, under the workspace unsaved-changes guard, until discarded. */
  accessLost: boolean;
};
const initial = (): ApproachControllerState => ({ studyId: null, status: 'idle', server: null, local: null, saved: null, preview: null, latest: null, error: '', diagnostics: [], accessLost: false });
type Command = { id: string; category: ApproachReceiptCategory1 };

/** Memory-only authoring projection. Workspace owns actor/navigation and calls
 * clear on logout/unmount; resource navigation uses handle before open. Reads
 * are scoped to actor and generation. Mutations retain their original API key. */
export class ApproachController {
  private state = initial();
  private listeners = new Set<() => void>();
  private generation = 0;
  private actor = '';
  private read: AbortController | null = null;
  private command: Command | null = null;
  private unsubscribe: (() => void) | null = null;
  constructor(private api: HyprnMvpApi) {}
  /** Shared session seam. Subscribed on the first open, so the controller is
   * cleared on sign-out or a confirmed access loss for its study reported by any host,
   * including while no approach page is mounted. `dispose` ends the subscription. */
  private sessionChanged = (change: SessionChange) => {
    if (change.kind === 'signed-out') { if (this.state.studyId || this.command) this.clear(); }
    else if (change.kind === 'access-lost') this.loseAccess(change.studyId);
  };
  dispose = () => { this.unsubscribe?.(); this.unsubscribe = null; this.clear(); };
  /** Confirmed access loss for `studyId` (this controller's read or any host). Clean state is
   * cleared completely, as before. Unsaved local edits are never dropped silently: the
   * server-derived draft, saved version, preview and latest draft are cleared, nothing is
   * displayed, nothing can be saved or previewed, and the edits stay under the existing
   * unsaved-changes guard until the user discards them (discard then clears completely). */
  loseAccess = (studyId: string) => {
    if (this.state.studyId !== studyId) return;
    this.generation++; this.read?.abort(); this.read = null;
    if (!this.dirty) { this.clear(); return; }
    this.state = { ...initial(), studyId, local: this.state.local, accessLost: true, status: 'error', error: accessLostText };
    this.listeners.forEach(fn => fn());
  };
  getSnapshot = () => this.state;
  subscribe = (listener: () => void) => { this.listeners.add(listener); return () => { this.listeners.delete(listener); }; };
  private update(patch: Partial<ApproachControllerState>) { this.state = { ...this.state, ...(patch.error !== undefined ? { diagnostics: [] } : {}), ...patch }; this.listeners.forEach(fn => fn()); }
  get ownsPendingCommand() { const pending = this.api.pending; return !!this.command && pending?.body.command_id === this.command.id && pending.category === this.command.category && pending.study === this.state.studyId && this.actor === this.api.actor; }
  get busy() { return this.state.status === 'loading' || this.state.status === 'working'; }
  get dirty() { return !!this.command || !!this.state.local && JSON.stringify(this.state.local) !== JSON.stringify(this.state.server?.draft?.content ?? emptyApproach()); }
  get handle(): EditorGuard { return { dirty: this.dirty || this.busy, save: this.save, discard: this.discard }; }
  clear = () => { this.generation++; this.read?.abort(); this.read = null; this.command = null; this.actor = ''; this.state = initial(); this.listeners.forEach(fn => fn()); };
  private ticket() { const generation = this.generation, actor = this.api.actor, session = this.api.csrf; return () => generation === this.generation && actor === this.api.actor && actor === this.actor && session === this.api.csrf; }
  private async failed(error: unknown) {
    if (!this.api.actor || this.actor !== this.api.actor) { this.clear(); return; }
    // Shared classification (api.readFailed): denied codes clear; a missing
    // reference and revoked membership intentionally share 404, so the study is
    // rechecked before protected authoring content is kept. A confirmed denial is
    // signalled to every host of the study.
    const studyId = this.state.studyId;
    if (studyId) {
      const valid = this.ticket(), read = this.api.fence({ studyId });
      const outcome = await this.api.readFailed(error, read);
      read.done();
      if (outcome === 'access-lost') { if (valid()) this.loseAccess(studyId); return; }
      if (!valid()) return;
      if (outcome === 'transient') { this.update({ status: this.command ? 'uncertain' : 'error', error: accessUnverifiedText }); return; }
    } else if (accessDenied(error)) { this.clear(); return; }
    const stale = error instanceof ApiError && error.detail.code === 'stale_revision';
    this.update({ status: this.command && this.api.pending?.body.command_id === this.command.id ? 'uncertain' : stale ? 'stale' : 'error', error: stale ? 'This approach draft changed. Your edits are preserved. Review the latest draft before saving.' : message(error), diagnostics: error instanceof ApiError ? error.detail.fields : [] });
  }
  open = async (studyId: string, versionId?: string): Promise<boolean> => {
    if (this.dirty || this.busy) return false;
    this.unsubscribe ??= this.api.onSessionChange(this.sessionChanged);
    this.clear(); this.actor = this.api.actor; const valid = this.ticket();
    this.read = new AbortController(); this.update({ studyId, status: 'loading' });
    try {
      if (versionId) { const saved = await this.api.approachVersion(studyId, versionId, this.read.signal); if (!valid()) return false; this.update({ saved, status: 'ready' }); }
      else { const server = await this.api.approach(studyId, this.read.signal); if (!valid()) return false; this.update({ server, local: structuredClone(server.draft?.content ?? emptyApproach()), status: 'ready' }); }
      return true;
    } catch (error) { if (valid()) await this.failed(error); return false; }
  };
  edit = (content: ApproachContent) => {
    if (this.busy || this.command || this.api.pending || !this.state.local || this.state.accessLost || this.actor !== this.api.actor) return;
    this.update({ local: structuredClone(content), preview: null, error: '', status: 'ready' });
  };
  discard = () => {
    if (this.busy || this.command || this.api.pending || !this.state.local) return;
    if (this.state.accessLost) { this.clear(); return; }
    this.update({ local: structuredClone(this.state.server?.draft?.content ?? emptyApproach()), preview: null, latest: null, error: '', status: 'ready' });
  };
  private previewRequest(content: ApproachContent): ApproachPreviewRequestRead2 {
    const expected_revision = this.state.server?.draft?.revision ?? null;
    return content.schema_version === '2' ? {schema_version:'2',expected_revision,content} : {schema_version:'1',expected_revision,content};
  }
  preview = async (): Promise<boolean> => {
    if (this.busy || this.command || this.api.pending || !this.state.local || !this.state.studyId || this.state.accessLost) return false;
    const valid = this.ticket(); this.update({ status: 'working', error: '' });
    try {
      const preview = await this.api.previewApproach(this.state.studyId, this.previewRequest(this.state.local));
      if (!valid()) return false;
      this.update({ preview, status: 'ready', error: preview.issues.length ? 'Resolve the referenced records before saving.' : '' }); return !preview.issues.length;
    } catch (error) { if (valid()) await this.failed(error); return false; }
  };
  private accept(result: ApproachDraftRead2 | ApproachVersionSavedRead3) {
    this.command = null;
    if ('saved' in result) {
      // The receipt returns the new token, not a complete updated draft. Read
      // the actual draft on explicit navigation; never fabricate its metadata.
      this.update({ saved: result.saved, server: null, local: null, preview: null, latest: null, error: '', status: 'ready' });
    } else this.update({ server: { draft: result, latest_version: this.state.server?.latest_version ?? null }, saved: null, local: structuredClone(result.content), preview: null, latest: null, error: '', status: 'ready' });
  }
  private async write(category: ApproachReceiptCategory1, operation: (id: string) => Promise<ApproachDraftRead2 | ApproachVersionSavedRead3>) {
    const valid = this.ticket(); this.command = { id: crypto.randomUUID(), category }; this.update({ status: 'working', error: '' });
    try { const result = await operation(this.command.id); if (!valid()) return false; this.accept(result); return true; }
    catch (error) { if (valid()) { if (!this.api.pending) this.command = null; await this.failed(error); } return false; }
  }
  save = async (): Promise<boolean> => {
    if (this.busy || this.command || this.api.pending || this.state.accessLost) return false;
    if (!this.state.local) return !!this.state.saved;
    if (!this.dirty && this.state.server?.draft) return true;
    if (!await this.preview() || !this.state.preview || !this.state.local || !this.state.studyId) return false;
    const sid = this.state.studyId, body = { ...this.previewRequest(structuredClone(this.state.local)), expected_preview_digest: this.state.preview.preview_digest };
    return this.write('approach_draft', id => this.api.saveApproachDraft(sid, { ...body, command_id: id }));
  };
  saveVersion = async (): Promise<boolean> => {
    if (this.state.accessLost || this.dirty || !this.state.server?.draft || !await this.preview() || !this.state.preview || !this.state.studyId) return false;
    const sid = this.state.studyId, revision = this.state.server.draft.revision, digest = this.state.preview.preview_digest;
    return this.write('approach_version', id => this.api.saveApproachVersion(sid, { schema_version: '1', command_id: id, expected_revision: revision, expected_preview_digest: digest }));
  };
  restore = async (versionId: string): Promise<boolean> => {
    if (this.state.accessLost || this.dirty || this.busy || this.api.pending || !this.state.studyId) return false;
    const sid = this.state.studyId, valid = this.ticket(); this.update({ status: 'working' });
    try {
      const current = await this.api.approach(sid); if (!valid()) return false;
      return this.write('approach_restore', id => this.api.restoreApproach(sid, { schema_version: '1', command_id: id, expected_revision: current.draft?.revision ?? null, approach_version_id: versionId }));
    } catch (error) { if (valid()) await this.failed(error); return false; }
  };
  reviewLatest = async (): Promise<boolean> => {
    if (this.state.accessLost || this.busy || this.command || this.api.pending || !this.state.studyId) return false;
    const valid = this.ticket(); this.update({ status: 'working' });
    try { const latest = await this.api.approach(this.state.studyId); if (!valid()) return false; this.update({ latest, status: 'ready' }); return true; }
    catch (error) { if (valid()) await this.failed(error); return false; }
  };
  reapplyToLatest = () => { if (!this.state.accessLost && !this.busy && !this.command && !this.api.pending && this.state.latest && this.state.local) this.update({ server: this.state.latest, latest: null, preview: null, status: 'ready', error: '' }); };
  reconcile = async (): Promise<boolean> => {
    if (!this.command || !this.state.studyId || this.busy) return false;
    const command = this.command, sid = this.state.studyId, valid = this.ticket(); this.update({ status: 'working' });
    try {
      const receipt = await this.api.approachReceipt(sid, command.id, command.category);
      if (!valid()) return false;
      if (this.api.pending?.body.command_id === command.id) await this.api.reconcile();
      if (!valid()) return false;
      if (receipt.state === 'committed' && receipt.result) { this.accept(receipt.result); return true; }
      this.command = null; this.update({ status: 'error', error: 'The command was rejected. Your local edits are preserved.' }); return false;
    } catch (error) {
      if (!valid()) return false;
      if (error instanceof ApiError && error.detail.code === 'resource_not_found' && this.api.pending?.body.command_id === command.id) {
        try { await this.api.study(sid); if (!valid()) return false; await this.api.reconcile(); if (valid()) this.update({ status: 'uncertain', error: 'No receipt yet. Retry the original command when ready.' }); }
        catch (failure) { if (valid()) await this.failed(failure); }
      } else await this.failed(error);
      return false;
    }
  };
  retryOriginal = async (): Promise<boolean> => {
    if (!this.command || this.busy || this.api.pending?.body.command_id !== this.command.id || !this.api.retryReady) return false;
    const valid = this.ticket(); this.update({ status: 'working' });
    try { await this.api.retryOriginal(); if (!valid()) return false; this.update({ status: 'uncertain' }); return this.reconcile(); }
    catch (error) { if (valid()) { if (!this.api.pending) this.command = null; await this.failed(error); } return false; }
  };
}

export const useApproachController = (controller: ApproachController) => useSyncExternalStore(controller.subscribe, controller.getSnapshot);
