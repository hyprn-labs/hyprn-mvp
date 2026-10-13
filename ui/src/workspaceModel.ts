import { createContext, useRef, useState } from 'react';
import type { ModelDraftRead4, ModelRevisionRead4 } from './contract';

/** Unsaved-work seam of one editor that Workspace guards before navigation.
 * `dirty` describes the latest handle; `save` resolves false when the editor kept
 * its edits (invalid, refused, stale, cancelled) and navigation must not follow;
 * `discard` synchronously returns the editor to its clean base. */
export type EditorGuard = { dirty: boolean; save: () => Promise<boolean>; discard: () => void };
export const cleanGuard = (): EditorGuard => ({ dirty: false, save: async () => true, discard: () => {} });

/** One entry of Workspace's ordered unsaved-changes list. The list order is the
 * save order and the discard order. */
export type GuardEntry = {
  name: string;
  /** Latest guard, read when used, so edits made since the last render count. */
  guard: () => EditorGuard;
  /** Render-time dirty mirror for the page (beforeunload, status labels, dialog copy). */
  shown: boolean;
  /** An open nested editor that must be applied or discarded first: Save is unavailable. */
  blocking?: boolean;
  /** Skip this save. `dirtyWhenSaved` names earlier entries that were dirty when saved. */
  skip?: (dirtyWhenSaved: ReadonlySet<string>) => boolean;
  /** Focus target after this entry refused to save and the dialog closed. */
  onRefused?: () => void;
  /** Mark clean after the whole list saved or discarded. */
  settle?: () => void;
  /** Return to a clean guard when the editor context is cleared. */
  reset?: () => void;
};
export const guardsShown = (entries: readonly GuardEntry[]) => entries.some(entry => entry.shown);
export const guardsDirty = (entries: readonly GuardEntry[]) => entries.some(entry => entry.guard().dirty);
export const guardsBlocked = (entries: readonly GuardEntry[]) => entries.some(entry => entry.blocking && entry.shown);
export type GuardSaveResult = { outcome: 'saved' } | { outcome: 'refused'; entry: GuardEntry } | { outcome: 'superseded' };
/** Saves every entry in order (clean editors resolve true) and stops at the first
 * refusal. `current` is checked after each entry; a false result stops the sequence
 * because the actor or navigation generation changed. Errors propagate unchanged. */
export async function saveGuards(entries: readonly GuardEntry[], current: () => boolean = () => true): Promise<GuardSaveResult> {
  const dirtyWhenSaved = new Set<string>();
  for (const entry of entries) {
    if (!entry.skip?.(dirtyWhenSaved)) {
      const guard = entry.guard();
      if (guard.dirty) dirtyWhenSaved.add(entry.name);
      if (!await guard.save()) return { outcome: 'refused', entry };
    }
    if (!current()) return { outcome: 'superseded' };
  }
  return { outcome: 'saved' };
}
/** Discards every entry in order, then marks each clean. */
export function discardGuards(entries: readonly GuardEntry[]) {
  entries.forEach(entry => entry.guard().discard());
  entries.forEach(entry => entry.settle?.());
}
/** Slot for an editor that reports its guard through an `onHandle` callback: `receive`
 * keeps the latest handle (read by `current` and the entry) and mirrors its dirty flag
 * into render state; `entry` places the slot in the guard list. */
export function useGuardSlot<T extends EditorGuard>(clean: () => T) {
  const ref = useRef<T | null>(null);
  const [dirty, setDirty] = useState(false);
  const current = () => ref.current ??= clean();
  return {
    dirty, current,
    receive(handle: T) { ref.current = handle; if (handle.dirty !== dirty) setDirty(handle.dirty); },
    entry(name: string, extra: Partial<GuardEntry> = {}): GuardEntry {
      return { name, guard: current, shown: dirty, settle: () => { ref.current = { ...current(), dirty: false }; setDirty(false); }, reset: () => { ref.current = clean(); setDirty(false); }, ...extra };
    },
  };
}

export type WorkspaceView = 'overview' | 'model' | 'configurations' | 'runs' | 'evidence' | 'approach';
export type Selection = { kind: 'none' } | { kind: 'instance'; instance_id: string }
  | { kind: 'variable'; instance_id: string; port_id: string }
  | { kind: 'connection'; connection_id: string }
  | { kind: 'connection_group'; source_instance_id: string; target_instance_id: string; connection_ids: string[] };
export type WorkspaceContext = { actor_id: string; study_id: string; view: WorkspaceView } & (
  { kind: 'study' } | { kind: 'draft'; model_id: string; draft_revision: string; snapshot: ModelDraftRead4 }
  | { kind: 'revision'; model_id: string; model_revision_id: string; snapshot: ModelRevisionRead4 }
  | { kind: 'configuration'; model_id: string; model_revision_id: string; configuration_revision_id: string; snapshot: ModelRevisionRead4 }
  | { kind: 'run'; run_id: string; model_id?: string; model_revision_id?: string; configuration_revision_id?: string; snapshot?: ModelRevisionRead4 });
/** `case` is meaningful only beside its exact approach version: a case UUID, or
 * `none` for the explicit null pin (No specific case). */
export type WorkspaceLink = { view: WorkspaceView; study?: string; model?: string; revision?: string; configuration?: string; run?: string; approach?: string; case?: string };
const views: WorkspaceView[] = ['overview', 'model', 'configurations', 'runs', 'evidence', 'approach'];
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export function parseWorkspaceLink(hash: string): WorkspaceLink | null {
  if (!hash || !hash.startsWith('#v=')) return null;
  const query = new URLSearchParams(hash.slice(1));
  if (query.get('v') !== '1') throw new Error('This workspace link uses an unsupported version.');
  const view = query.get('view') ?? 'overview';
  if (!views.includes(view as WorkspaceView)) throw new Error('This workspace view is unavailable.');
  const link: WorkspaceLink = { view: view as WorkspaceView };
  for (const key of ['study', 'model', 'revision', 'configuration', 'run', 'approach'] as const) {
    const value = query.get(key); if (!value) continue;
    if (!uuid.test(value)) throw new Error('This workspace link has an invalid resource identity.');
    link[key] = value;
  }
  if (!link.study || (link.revision && !link.model) || (link.run && link.configuration)) throw new Error('This workspace link is incomplete.');
  if ((link.approach && link.view !== 'approach') || (link.view === 'approach' && (link.model || link.revision || link.configuration || link.run))) throw new Error('This approach link has conflicting resource context.');
  const caseId = query.get('case');
  if (caseId !== null) {
    // A case identity is never global: it must be qualified by its exact approach version.
    if (!link.approach) throw new Error('This case link does not name an approach version.');
    if (caseId !== 'none' && !uuid.test(caseId)) throw new Error('This workspace link has an invalid resource identity.');
    link.case = caseId;
  }
  return link;
}
export function workspaceHash(link: WorkspaceLink): string {
  const query = new URLSearchParams({ v: '1', view: link.view });
  for (const key of ['study', 'model', 'revision', 'configuration', 'run', 'approach'] as const) if (link[key]) query.set(key, link[key]!);
  if (link.case && link.approach && link.view === 'approach') query.set('case', link.case);
  return '#' + query.toString();
}

/** Exact version-qualified case target. `case_id` null is the explicit null pin. */
export type CaseNavigationTarget = { approach_version_id: string; case_id: string | null };
/** Live hosts (Workspace) provide navigation to the exact approach version and
 * case; `returnKey` names the invoking control for focus return. Historical
 * readers provide null, so retained closures never navigate to current usage. */
export const CaseNavigation = createContext<((target: CaseNavigationTarget, returnKey: string) => void) | null>(null);

// Shared active-instance readiness; retained unused definitions do not block.
export { unresolvedModelUnits } from './unitLabels';
