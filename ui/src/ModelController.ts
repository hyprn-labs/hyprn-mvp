import { useSyncExternalStore } from 'react';
import type { HyprnMvpApi, ModelDraftRead5, RevisionSummary } from './api';
import { unresolvedModelUnits } from './unitLabels';
import { saveGuards, type GuardEntry } from './workspaceModel';

/** The unsaved edits a model version includes, in the shell's save order: pasted ports, the
 * model editor and the study metadata. Other editors keep their edits. */
const versionGuards: readonly string[] = ['port-paste', 'editor', 'metadata'];
/** A saved version with an active component whose units are not specified cannot be
 * configured yet; the notice says so instead of naming the version. */
const unitsIncomplete =
  'Model version saved · units incomplete. Resolve units in the listed active components ' +
  'before creating a configuration.';

export type ModelControllerState = {
  status: 'idle' | 'saving';
  /** The model version the last completed save recorded, for this controller's lifetime. */
  savedVersion: string | null;
};

/** Where a model version save reports to: the shell's unsaved-changes list and the model,
 * version list and notice it shows. */
export type ModelVersionHost = {
  guards: readonly GuardEntry[];
  onModel: (model: ModelDraftRead5) => void;
  onRevisions: (revisions: RevisionSummary[]) => void;
  onNotice: (notice: string) => void;
};

/** Model workflow beside `ApproachController`: it owns the model version save. The shell
 * owns actor and navigation; a save stops, without reporting, as soon as the actor or the
 * shell's navigation generation changes, so a superseded save never shows its results. */
export class ModelController {
  private state: ModelControllerState = { status: 'idle', savedVersion: null };
  private listeners = new Set<() => void>();
  constructor(
    private api: HyprnMvpApi,
    private generation: { readonly current: number },
  ) {}
  getSnapshot = () => this.state;
  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };
  private update(patch: Partial<ModelControllerState>) {
    this.state = { ...this.state, ...patch };
    this.listeners.forEach((fn) => fn());
  }
  /** Saves the included unsaved edits, re-reads the draft, records it as a model version,
   * re-reads the version list and reports the saved version (or that its units are
   * incomplete). Errors propagate unchanged; edits that refuse to save stop the sequence. */
  saveVersion = async (studyId: string, modelId: string, host: ModelVersionHost) => {
    const token = this.generation.current,
      actor = this.api.actor;
    const valid = () => token === this.generation.current && actor === this.api.actor;
    const included = host.guards.filter((guard) => versionGuards.includes(guard.name));
    this.update({ status: 'saving' });
    try {
      if ((await saveGuards(included, valid)).outcome !== 'saved') return;
      const current = await this.api.model(studyId, modelId);
      if (!valid()) return;
      host.onModel(current);
      const saved = await this.api.commitModel(current);
      if (!valid()) return;
      const versions = await this.api.revisions(studyId, modelId);
      if (!valid()) return;
      host.onRevisions(versions);
      this.update({ savedVersion: saved.model_revision_id });
      host.onNotice(
        unresolvedModelUnits(saved).length
          ? unitsIncomplete
          : `Model version ${saved.model_revision_id.slice(0, 8)} saved.`,
      );
    } finally {
      this.update({ status: 'idle' });
    }
  };
}

export const useModelController = (controller: ModelController) =>
  useSyncExternalStore(controller.subscribe, controller.getSnapshot);
