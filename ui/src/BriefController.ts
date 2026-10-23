import { useSyncExternalStore } from 'react';
import {
  ApiError,
  HyprnMvpApi,
  accessLostText,
  accessUnverifiedText,
  message,
  type SessionChange,
} from './api';
import type {
  Diagnostic,
  StudyBriefContent2,
  StudyBriefContentRead2,
  StudyBriefStateRead2,
  StudyBriefVersionRead2,
  StudyCriterion1,
} from './contract';
import type { EditorGuard } from './workspaceModel';

/** A criterion as it is edited: numbers stay the text the engineer typed until saving, so a
 * blank threshold reads "unassigned" and is refused, never replaced by a number. */
export type CriterionForm = {
  criterion_id: string;
  kind: 'constraint' | 'objective';
  name: string;
  statement: string;
  operator: 'lt' | 'le' | 'eq' | 'ge' | 'gt';
  threshold: string;
  units: string;
  absolute_tolerance: string;
  relative_tolerance: string;
  direction: 'minimize' | 'maximize';
  evidence_links: StudyCriterion1['evidence_links'];
};
export type BriefForm = Omit<StudyBriefContent2, 'criteria'> & { criteria: CriterionForm[] };

export const emptyBrief = (): StudyBriefContent2 => ({
  schema_version: '2',
  deliverables: [],
  question: '',
  original_question: null,
  elaboration: null,
  scope: '',
  alternatives: [],
  criteria: [],
  assumptions: [],
  limits: [],
  open_questions: [],
});

const text = (value: number | undefined) => (value === undefined ? '' : String(value));

export function criterionForm(criterion: StudyCriterion1): CriterionForm {
  const base = {
    criterion_id: criterion.criterion_id,
    name: criterion.name,
    statement: criterion.statement,
    units: criterion.units,
    evidence_links: criterion.evidence_links,
  };
  return criterion.kind === 'constraint'
    ? {
        ...base,
        kind: 'constraint',
        operator: criterion.operator,
        threshold: text(criterion.threshold),
        absolute_tolerance: text(criterion.absolute_tolerance),
        relative_tolerance: text(criterion.relative_tolerance),
        direction: 'minimize',
      }
    : {
        ...base,
        kind: 'objective',
        operator: 'le',
        threshold: '',
        absolute_tolerance: '',
        relative_tolerance: '',
        direction: criterion.direction,
      };
}

export const briefForm = (content: StudyBriefContentRead2): BriefForm => ({
  ...structuredClone(content),
  schema_version: '2',
  deliverables: content.schema_version === '2' ? content.deliverables : [],
  criteria: content.criteria.map(criterionForm),
});

export const newCriterion = (kind: CriterionForm['kind']): CriterionForm => ({
  criterion_id: crypto.randomUUID(),
  kind,
  name: '',
  statement: '',
  operator: 'le',
  threshold: '',
  units: '',
  absolute_tolerance: '',
  relative_tolerance: '',
  direction: 'minimize',
  evidence_links: [],
});

/** A finite number from typed text; blank is unassigned (null), anything else is refused. */
function number(value: string): number | null | 'invalid' {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) && /^[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?$/.test(trimmed)
    ? parsed
    : 'invalid';
}

/** The content to save, or the first problem in the form's own words. */
export function briefContent(
  form: BriefForm,
): { content: StudyBriefContent2 } | { problem: string } {
  const criteria: StudyCriterion1[] = [];
  for (const [index, c] of form.criteria.entries()) {
    const label = `Criterion ${index + 1}`;
    if (!c.name.trim()) return { problem: `${label}: enter a name.` };
    const base = {
      criterion_id: c.criterion_id,
      name: c.name,
      statement: c.statement,
      units: c.units,
      evidence_links: c.evidence_links,
    };
    if (c.kind === 'objective') {
      criteria.push({ ...base, kind: 'objective', direction: c.direction });
      continue;
    }
    const threshold = number(c.threshold);
    if (threshold === null)
      return { problem: `${label}: the threshold is unassigned. Enter a number.` };
    if (threshold === 'invalid')
      return { problem: `${label}: the threshold must be a finite number.` };
    const tolerances: { absolute_tolerance?: number; relative_tolerance?: number } = {};
    for (const [key, word] of [
      ['absolute_tolerance', 'absolute tolerance'],
      ['relative_tolerance', 'relative tolerance'],
    ] as const) {
      const value = number(c[key]);
      if (value === 'invalid' || (value !== null && value < 0))
        return { problem: `${label}: the ${word} must be a number of at least 0, or blank.` };
      if (value !== null) tolerances[key] = value;
    }
    criteria.push({ ...base, kind: 'constraint', operator: c.operator, threshold, ...tolerances });
  }
  for (const [index, a] of form.alternatives.entries())
    if (!a.name.trim()) return { problem: `Alternative ${index + 1}: enter a name.` };
  for (const [list, word] of [
    [form.assumptions, 'Assumption'],
    [form.limits, 'Limit'],
  ] as const)
    for (const [index, item] of list.entries())
      if (!item.statement.trim()) return { problem: `${word} ${index + 1}: enter a statement.` };
  for (const [index, item] of form.open_questions.entries())
    if (!item.text.trim()) return { problem: `Open question ${index + 1}: enter the question.` };
  return { content: { ...structuredClone(form), criteria } };
}

export type BriefControllerState = {
  studyId: string | null;
  status: 'idle' | 'loading' | 'ready' | 'working' | 'stale' | 'uncertain' | 'error';
  server: StudyBriefStateRead2 | null;
  /** Saved versions, newest first. */
  versions: StudyBriefVersionRead2[];
  /** The editing copy; null while the brief is only read. */
  local: BriefForm | null;
  error: string;
  diagnostics: Diagnostic[];
  /** Confirmed access loss with unsaved edits: nothing read from the server is kept; the
   * edits stay under the unsaved-changes guard until discarded. */
  accessLost: boolean;
};
const initial = (): BriefControllerState => ({
  studyId: null,
  status: 'idle',
  server: null,
  versions: [],
  local: null,
  error: '',
  diagnostics: [],
  accessLost: false,
});
type Command = { id: string; category: 'brief_draft' | 'brief_version' };

/** Memory-only brief projection and editing copy for one study. Reads are scoped to the
 * actor, session and generation; a late reply is discarded. A command keeps its original id on
 * the shared receipt path, and an uncertain outcome is never resent from here. */
export class BriefController {
  private state = initial();
  private listeners = new Set<() => void>();
  private generation = 0;
  private actor = '';
  private read: AbortController | null = null;
  private command: Command | null = null;
  private unsubscribe: (() => void) | null = null;
  constructor(private api: HyprnMvpApi) {}
  private sessionChanged = (change: SessionChange) => {
    if (change.kind === 'signed-out') {
      if (this.state.studyId || this.command) this.clear();
    } else if (change.kind === 'access-lost') this.loseAccess(change.studyId);
  };
  dispose = () => {
    this.unsubscribe?.();
    this.unsubscribe = null;
    this.clear();
  };
  loseAccess = (studyId: string) => {
    if (this.state.studyId !== studyId) return;
    this.generation++;
    this.read?.abort();
    this.read = null;
    if (!this.dirty) {
      this.clear();
      return;
    }
    this.set({
      ...initial(),
      studyId,
      local: this.state.local,
      accessLost: true,
      status: 'error',
      error: accessLostText,
    });
  };
  getSnapshot = () => this.state;
  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };
  private set(state: BriefControllerState) {
    this.state = state;
    this.listeners.forEach((fn) => fn());
  }
  private update(patch: Partial<BriefControllerState>) {
    this.set({
      ...this.state,
      ...(patch.error !== undefined ? { diagnostics: [] } : {}),
      ...patch,
    });
  }
  get busy() {
    return this.state.status === 'loading' || this.state.status === 'working';
  }
  get dirty() {
    const local = this.state.local;
    if (this.command) return true;
    if (!local) return false;
    return (
      JSON.stringify(local) !==
      JSON.stringify(briefForm(this.state.server?.draft?.content ?? emptyBrief()))
    );
  }
  get handle(): EditorGuard {
    // A read in flight is never unsaved work; a write in flight is.
    return {
      dirty: this.dirty || this.state.status === 'working',
      save: this.save,
      discard: this.discard,
    };
  }
  clear = () => {
    this.generation++;
    this.read?.abort();
    this.read = null;
    this.command = null;
    this.actor = '';
    this.set(initial());
  };
  private ticket() {
    const generation = this.generation,
      actor = this.api.actor,
      session = this.api.csrf;
    return () =>
      generation === this.generation &&
      actor === this.api.actor &&
      actor === this.actor &&
      session === this.api.csrf;
  }
  private async failed(error: unknown) {
    if (!this.api.actor || this.actor !== this.api.actor) {
      this.clear();
      return;
    }
    const studyId = this.state.studyId;
    if (studyId) {
      const valid = this.ticket(),
        read = this.api.fence({ studyId });
      const outcome = await this.api.readFailed(error, read, { command: !!this.command });
      read.done();
      if (outcome === 'access-lost') {
        if (valid()) this.loseAccess(studyId);
        return;
      }
      if (!valid()) return;
      if (outcome === 'transient') {
        this.update({ status: this.command ? 'uncertain' : 'error', error: accessUnverifiedText });
        return;
      }
    }
    const stale = error instanceof ApiError && error.detail.code === 'stale_revision';
    const pending = !!this.command && this.api.pending?.body.command_id === this.command.id;
    if (!pending) this.command = null;
    this.update({
      status: pending ? 'uncertain' : stale ? 'stale' : 'error',
      error: pending
        ? 'Command outcome is uncertain. Check the original command before making more changes.'
        : stale
          ? 'The brief draft changed since you opened it. Your edits are preserved. Load the latest draft before saving.'
          : message(error),
      diagnostics: error instanceof ApiError ? error.detail.fields : [],
    });
  }
  /** Read the brief and every saved version of `studyId`. Refused while edits are unsaved. */
  open = async (studyId: string, refresh = false): Promise<boolean> => {
    if (this.dirty || this.busy || (refresh && this.state.local)) return false;
    this.unsubscribe ??= this.api.onSessionChange(this.sessionChanged);
    if (!refresh || this.state.studyId !== studyId || this.actor !== this.api.actor) this.clear();
    this.actor = this.api.actor;
    const valid = this.ticket();
    this.read = new AbortController();
    this.update({ studyId, status: 'loading' });
    try {
      const signal = this.read.signal;
      const server = await this.api.brief(studyId, signal);
      const versions: StudyBriefVersionRead2[] = [];
      let before: number | undefined;
      do {
        const page = await this.api.briefVersions(studyId, before, signal);
        if (!valid()) return false;
        versions.push(...page.items);
        before = page.next_cursor ?? undefined;
      } while (before !== undefined);
      if (!valid()) return false;
      this.update({ server, versions, status: 'ready' });
      return true;
    } catch (error) {
      if (valid()) await this.failed(error);
      return false;
    }
  };
  beginEdit = () => {
    if (this.busy || this.state.local || this.state.accessLost || !this.state.server) return;
    this.update({
      local: briefForm(this.state.server.draft?.content ?? emptyBrief()),
      error: '',
      status: 'ready',
    });
  };
  edit = (form: BriefForm) => {
    if (this.busy || this.command || this.api.pending || !this.state.local || this.state.accessLost)
      return;
    this.update({ local: structuredClone(form), error: '', status: 'ready' });
  };
  /** Leave editing without saving: the draft on the server is unchanged. */
  discard = () => {
    if (this.busy || this.command) return;
    if (this.state.accessLost) {
      this.clear();
      return;
    }
    this.update({ local: null, error: '', status: 'ready' });
  };
  private async write<T>(
    category: Command['category'],
    operation: (id: string) => Promise<T>,
    accept: (result: T) => void,
  ) {
    const valid = this.ticket();
    this.command = { id: crypto.randomUUID(), category };
    this.update({ status: 'working', error: '' });
    try {
      const result = await operation(this.command.id);
      if (!valid()) return false;
      this.command = null;
      accept(result);
      return true;
    } catch (error) {
      if (valid()) await this.failed(error);
      return false;
    }
  }
  /** Save the editing copy as the draft under the revision it was opened from. */
  save = async (): Promise<boolean> => {
    const { local, studyId, server, accessLost } = this.state;
    // Nothing unsaved (including a brief never opened) is already saved for the guard.
    if (!this.dirty) {
      if (local && !this.busy) this.update({ local: null });
      return true;
    }
    if (
      this.busy ||
      this.command ||
      this.api.pending ||
      accessLost ||
      !studyId ||
      !server ||
      !local
    )
      return false;
    const built = briefContent(local);
    if ('problem' in built) {
      this.update({ status: 'error', error: built.problem });
      return false;
    }
    return this.write(
      'brief_draft',
      (id) =>
        this.api.saveBriefDraft(studyId, {
          command_id: id,
          expected_revision: server.draft?.revision ?? null,
          content: built.content,
        }),
      (draft) =>
        this.update({ server: { ...server, draft }, local: null, status: 'ready', error: '' }),
    );
  };
  /** Freeze the saved draft as the next numbered version. */
  saveVersion = async (): Promise<boolean> => {
    const { studyId, server, accessLost } = this.state;
    if (
      this.busy ||
      this.dirty ||
      this.state.local ||
      this.api.pending ||
      accessLost ||
      !studyId ||
      !server?.draft
    )
      return false;
    const revision = server.draft.revision;
    return this.write(
      'brief_version',
      (id) => this.api.saveBriefVersion(studyId, { command_id: id, expected_revision: revision }),
      (saved) =>
        this.update({
          server: { draft: saved.draft, latest_version: saved.version },
          versions: [saved.version, ...this.state.versions],
          status: 'ready',
          error: '',
        }),
    );
  };
  /** After a stale revision: read the latest brief and keep the editing copy, so the next save
   * replaces the newer draft only when the engineer saves again. */
  loadLatest = async (): Promise<boolean> => {
    const { studyId, local } = this.state;
    if (this.busy || this.command || !studyId) return false;
    const valid = this.ticket();
    this.update({ status: 'working', error: '' });
    try {
      const server = await this.api.brief(studyId);
      if (!valid()) return false;
      this.update({ server, local, status: 'ready' });
      return true;
    } catch (error) {
      if (valid()) await this.failed(error);
      return false;
    }
  };
  /** Ask the owner for the original command's outcome; a settled command reloads the brief. */
  checkCommand = async (): Promise<boolean> => {
    const { studyId } = this.state;
    if (!this.command || !studyId || this.busy) return false;
    const command = this.command,
      valid = this.ticket();
    this.update({ status: 'working' });
    try {
      await this.api.reconcile();
      if (!valid()) return false;
      if (this.api.pending?.body.command_id === command.id) {
        this.update({
          status: 'uncertain',
          error: 'The original command is not settled yet. Check again shortly.',
        });
        return false;
      }
      this.command = null;
      const local = this.state.local;
      const server = await this.api.brief(studyId);
      if (!valid()) return false;
      const versions =
        command.category === 'brief_version' ? await this.reread(studyId) : this.state.versions;
      if (!valid()) return false;
      const kept =
        local &&
        JSON.stringify(local) !== JSON.stringify(briefForm(server.draft?.content ?? emptyBrief()))
          ? local
          : null;
      this.update({ server, versions, local: kept, status: 'ready', error: '' });
      return true;
    } catch (error) {
      if (valid()) await this.failed(error);
      return false;
    }
  };
  private async reread(studyId: string) {
    const versions: StudyBriefVersionRead2[] = [];
    let before: number | undefined;
    do {
      const page = await this.api.briefVersions(studyId, before);
      versions.push(...page.items);
      before = page.next_cursor ?? undefined;
    } while (before !== undefined);
    return versions;
  }
}

export const useBriefController = (controller: BriefController) =>
  useSyncExternalStore(controller.subscribe, controller.getSnapshot);
