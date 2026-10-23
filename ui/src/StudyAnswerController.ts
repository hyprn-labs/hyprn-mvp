import { useSyncExternalStore } from 'react';
import {
  ApiError,
  HyprnMvpApi,
  accessLostText,
  accessUnverifiedText,
  message,
  type EvidenceRecord,
  type SessionChange,
} from './api';
import type {
  Calculation4,
  CalculationVersionRead4,
  Diagnostic,
  StudyAnswerContent3,
  StudyAnswerContentRead3,
  StudyAnswerStateRead3,
  StudyAnswerVersionRead3,
  StudyBriefVersionRead2,
} from './contract';
import type { EditorGuard } from './workspaceModel';

export const emptyAnswer = (): StudyAnswerContent3 => ({
  schema_version: '3',
  completion: { state: 'interim', deliverables: [] },
  scientific_review: {
    brief_fidelity: { state: 'unassessed', explanation: '' },
    source_basis: { state: 'unassessed', explanation: '' },
    physical_validity: { state: 'unassessed', explanation: '' },
    sensitivity: { state: 'unassessed', explanation: '' },
  },
  brief_version_id: null,
  alternative_mappings: [],
  comparison: [],
  justifications: [],
  interpretation: {
    interpretation: '',
  },
  outcome: null,
  decisive_uncertainties: [],
  next_analysis: { statement: '', resolves: '' },
  exploration_basis: null,
});

/** Historical saved versions keep their bytes; only an editing/reading copy is adapted. */
export function currentAnswer(content: StudyAnswerContentRead3): StudyAnswerContent3 {
  if (content.schema_version === '3') return structuredClone(content);
  if (content.schema_version === '2')
    return { ...emptyAnswer(), ...structuredClone(content), schema_version: '3' };
  const old = content.interpretation;
  return {
    ...emptyAnswer(),
    ...structuredClone(content),
    schema_version: '3',
    comparison: content.comparison.map((cell) => ({ ...cell, output_name: null })),
    interpretation: {
      interpretation: [old.observations, old.interpretation, old.qualifications]
        .filter(Boolean)
        .join('\n\n'),
    },
    next_analysis: {
      ...content.next_analysis,
      statement: [content.next_analysis.statement, ...old.open_deliverables.map((d) => d.text)]
        .filter(Boolean)
        .join('\n\n'),
    },
  };
}

/** The records an answer cites, read once with the answer: saved brief versions (for the
 * alternatives and criteria), the study's calculations with their latest versions, and the
 * study's evidence. */
export type AnswerReferences = {
  briefVersions: StudyBriefVersionRead2[];
  calculations: Calculation4[];
  calculationVersions: CalculationVersionRead4[];
  evidence: EvidenceRecord[];
};

/** The content to save, or the first problem in the form's own words. Cells' evaluations are
 * cleared: the application fills them from the cited runs. */
export function answerContent(
  form: StudyAnswerContent3,
): { content: StudyAnswerContent3 } | { problem: string } {
  for (const [index, item] of form.justifications.entries())
    if (!item.reason.trim()) return { problem: `Justification ${index + 1}: enter the reason.` };
  for (const [index, item] of form.decisive_uncertainties.entries())
    if (!item.statement.trim())
      return { problem: `Decisive uncertainty ${index + 1}: enter a statement.` };
  if (form.outcome && !form.outcome.reason.trim()) return { problem: 'Outcome: enter the reason.' };
  const content = structuredClone(form);
  content.comparison = content.comparison.map((cell) => ({ ...cell, evaluation: null }));
  return { content };
}

export type StudyAnswerControllerState = {
  studyId: string | null;
  status: 'idle' | 'loading' | 'ready' | 'working' | 'stale' | 'uncertain' | 'error';
  server: StudyAnswerStateRead3 | null;
  /** Saved versions, newest first. */
  versions: StudyAnswerVersionRead3[];
  references: AnswerReferences;
  /** The editing copy; null while the answer is only read. */
  local: StudyAnswerContent3 | null;
  error: string;
  diagnostics: Diagnostic[];
  /** Confirmed access loss with unsaved edits: nothing read from the server is kept; the
   * edits stay under the unsaved-changes guard until discarded. */
  accessLost: boolean;
};
const noReferences = (): AnswerReferences => ({
  briefVersions: [],
  calculations: [],
  calculationVersions: [],
  evidence: [],
});
const initial = (): StudyAnswerControllerState => ({
  studyId: null,
  status: 'idle',
  server: null,
  versions: [],
  references: noReferences(),
  local: null,
  error: '',
  diagnostics: [],
  accessLost: false,
});
type Command = { id: string; category: 'answer_draft' | 'answer_version' };

/** Memory-only study answer projection and editing copy for one study. Reads are scoped to the
 * actor, session and generation; a late reply is discarded. A command keeps its original id on
 * the shared receipt path, and an uncertain outcome is never resent from here. */
export class StudyAnswerController {
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
  private set(state: StudyAnswerControllerState) {
    this.state = state;
    this.listeners.forEach((fn) => fn());
  }
  private update(patch: Partial<StudyAnswerControllerState>) {
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
      JSON.stringify(currentAnswer(this.state.server?.draft?.content ?? emptyAnswer()))
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
          ? 'The answer draft changed since you opened it. Your edits are preserved. ' +
            'Load the latest draft before saving.'
          : message(error),
      diagnostics: error instanceof ApiError ? error.detail.fields : [],
    });
  }
  private async versionsOf(studyId: string, signal?: AbortSignal) {
    const versions: StudyAnswerVersionRead3[] = [];
    let before: number | undefined;
    do {
      const page = await this.api.studyAnswerVersions(studyId, before, signal);
      versions.push(...page.items);
      before = page.next_cursor ?? undefined;
    } while (before !== undefined);
    return versions;
  }
  private async referencesOf(
    studyId: string,
    signal?: AbortSignal,
    answers = this.state.versions,
  ): Promise<AnswerReferences> {
    const briefVersions: StudyBriefVersionRead2[] = [];
    let before: number | undefined;
    do {
      const page = await this.api.briefVersions(studyId, before, signal);
      briefVersions.push(...page.items);
      before = page.next_cursor ?? undefined;
    } while (before !== undefined);
    const calculations: Calculation4[] = [];
    let after: number | undefined;
    do {
      const page = await this.api.studyCalculations(studyId, after, signal);
      calculations.push(...page.items);
      after = page.next_cursor ?? undefined;
    } while (after !== undefined);
    const evidence = await this.api.evidence(studyId);
    const calculationVersions: CalculationVersionRead4[] = calculations.map(
      (c) => c.latest_version,
    );
    const referenced = new Set(
      answers.flatMap((a) =>
        a.content.alternative_mappings.flatMap((m) => m.calculation_version_ids),
      ),
    );
    for (const id of referenced) {
      if (!calculationVersions.some((v) => v.calculation_version_id === id))
        calculationVersions.push(await this.api.calculationVersion(studyId, id, signal));
    }
    return { briefVersions, calculations, calculationVersions, evidence };
  }
  /** Read the answer, its saved versions and the records it can cite. Refused while edits
   * are unsaved. */
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
      const server = await this.api.studyAnswer(studyId, signal);
      const versions = await this.versionsOf(studyId, signal);
      const references = await this.referencesOf(studyId, signal, versions);
      if (!valid()) return false;
      this.update({ server, versions, references, status: 'ready' });
      return true;
    } catch (error) {
      if (valid()) await this.failed(error);
      return false;
    }
  };
  beginEdit = async () => {
    if (this.busy || this.state.local || this.state.accessLost || !this.state.server) return;
    const studyId = this.state.studyId!;
    const valid = this.ticket();
    this.read?.abort();
    this.read = new AbortController();
    this.update({ status: 'loading', error: '' });
    try {
      // The brief or calculations may have changed since Overview first opened.
      const references = await this.referencesOf(studyId, this.read.signal);
      if (!valid()) return;
      this.update({
        references,
        local: currentAnswer(this.state.server?.draft?.content ?? emptyAnswer()),
        error: '',
        status: 'ready',
      });
    } catch (error) {
      if (valid()) await this.failed(error);
    }
  };
  edit = (form: StudyAnswerContent3) => {
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
    const built = answerContent(local);
    if ('problem' in built) {
      this.update({ status: 'error', error: built.problem });
      return false;
    }
    return this.write(
      'answer_draft',
      (id) =>
        this.api.saveStudyAnswerDraft(studyId, {
          command_id: id,
          expected_revision: server.draft?.revision ?? null,
          content: built.content,
        }),
      (draft) =>
        this.update({ server: { ...server, draft }, local: null, status: 'ready', error: '' }),
    );
  };
  /** Freeze the saved draft as the next numbered version; its cells are re-read from runs. */
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
      'answer_version',
      (id) =>
        this.api.saveStudyAnswerVersion(studyId, { command_id: id, expected_revision: revision }),
      (saved) =>
        this.update({
          server: { draft: saved.draft, latest_version: saved.version },
          versions: [saved.version, ...this.state.versions],
          status: 'ready',
          error: '',
        }),
    );
  };
  /** After a stale revision: read the latest answer and keep the editing copy. */
  loadLatest = async (): Promise<boolean> => {
    const { studyId, local } = this.state;
    if (this.busy || this.command || !studyId) return false;
    const valid = this.ticket();
    this.update({ status: 'working', error: '' });
    try {
      const server = await this.api.studyAnswer(studyId);
      if (!valid()) return false;
      this.update({ server, local, status: 'ready' });
      return true;
    } catch (error) {
      if (valid()) await this.failed(error);
      return false;
    }
  };
  /** Ask the owner for the original command's outcome; a settled command reloads the answer. */
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
      const server = await this.api.studyAnswer(studyId);
      if (!valid()) return false;
      const versions =
        command.category === 'answer_version'
          ? await this.versionsOf(studyId)
          : this.state.versions;
      if (!valid()) return false;
      const kept =
        local &&
        JSON.stringify(local) !==
          JSON.stringify(currentAnswer(server.draft?.content ?? emptyAnswer()))
          ? local
          : null;
      this.update({ server, versions, local: kept, status: 'ready', error: '' });
      return true;
    } catch (error) {
      if (valid()) await this.failed(error);
      return false;
    }
  };
}

export const useStudyAnswerController = (controller: StudyAnswerController) =>
  useSyncExternalStore(controller.subscribe, controller.getSnapshot);
