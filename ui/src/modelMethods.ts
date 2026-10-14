import { useEffect, useState } from 'react';
import type { ApproachContent, HyprnMvpApi } from './api';
import { useAccessLoss } from './accessLoss';
import type {
  ApproachClosureRead3,
  ApproachStep1,
  ApproachVersionRead2,
  ConfigurationRevision,
} from './contract';
import type { Snapshot } from './GraphView';
import { referencedInstances } from './quantityDefinitions';
import { configurationContext, linkedApproach } from './recordViews';

/**
 * Why a component exists: the method steps of one exact approach
 * version (or the approach draft) that reference components of the displayed model. The model
 * view shows each linked step's authored Transformation, Purpose and rationale beside the
 * component. Links are read from exact implementation references only, never matched by name.
 */
export type MethodLink = {
  key: string;
  /** Exact saved approach version; null for the current approach draft. */
  approachVersionId: string | null;
  versionNumber: number | null;
  stepId: string;
  stepNumber: number;
  step: ApproachStep1;
  /** Exact model versions the step's references are pinned to (a draft may show older pins). */
  modelRevisionIds: string[];
  /** Components of the displayed model that the step references. */
  instanceIds: string[];
};

export type MethodLinks =
  | { kind: 'none' }
  | { kind: 'loading' }
  | { kind: 'unavailable' }
  | { kind: 'loaded'; links: MethodLink[] };

/** Steps of one approach content that reference the displayed model. A saved model version
 * matches its exact pins; a model draft matches pins of the same model (its instances keep
 * their identities), and each link names the exact model versions it is pinned to. */
export function methodLinks(
  content: ApproachContent,
  version: { id: string; number: number } | null,
  snapshot: Snapshot,
): MethodLink[] {
  const exact = 'model_revision_id' in snapshot ? snapshot.model_revision_id : null;
  const bindings = content.model_bindings.filter(
    (b) => b.model_id === snapshot.model_id && (exact === null || b.model_revision_id === exact),
  );
  return content.steps.flatMap((step, index) => {
    const pinned = bindings.filter((b) =>
      step.implementation_refs.some((r) => r.binding_id === b.binding_id),
    );
    const refs = step.implementation_refs.filter((r) =>
      pinned.some((b) => b.binding_id === r.binding_id),
    );
    const instanceIds = referencedInstances(snapshot, refs).map((i) => i.instance_id);
    if (!instanceIds.length) return [];
    return [
      {
        key: (version?.id ?? 'draft') + '/' + step.step_id,
        approachVersionId: version?.id ?? null,
        versionNumber: version?.number ?? null,
        stepId: step.step_id,
        stepNumber: index + 1,
        step,
        modelRevisionIds: [...new Set(pinned.map((b) => b.model_revision_id))],
        instanceIds,
      },
    ];
  });
}

/** The exact approach version a saved configuration (or a run's configuration) is pinned to,
 * read from the retained closure only; never today's approach. */
export function retainedApproachVersion(
  configuration: ConfigurationRevision | null | undefined,
  closure: ApproachClosureRead3 | null | undefined,
): ApproachVersionRead2 | null {
  if (!configuration || !closure) return null;
  const pin = linkedApproach(configurationContext(configuration));
  return pin
    ? (closure.approach_versions.find((v) => v.approach_version_id === pin.approach_version_id) ??
        null)
    : null;
}

/** Links from a retained approach version (configuration and run contexts). */
export function retainedMethodLinks(
  version: ApproachVersionRead2 | null,
  snapshot: Snapshot | null | undefined,
): MethodLinks {
  if (!snapshot || !version) return { kind: 'none' };
  return {
    kind: 'loaded',
    links: methodLinks(
      version.content,
      { id: version.approach_version_id, number: version.version_number },
      snapshot,
    ),
  };
}

/** The model draft reads the approach draft; saved models read the latest saved approach.
 * One bounded read pair (state, then the exact version); failures show "unavailable" and
 * never invents a link. Cleared on sign-out or confirmed access loss. */
export function useLatestMethodLinks(
  api: HyprnMvpApi,
  studyId: string | undefined,
  snapshot: Snapshot | null | undefined,
): MethodLinks {
  const [record, setRecord] = useState<
    | { studyId: string; version: ApproachVersionRead2 | null; draft: ApproachContent | null }
    | 'loading'
    | 'unavailable'
  >('loading');
  useAccessLoss(api, studyId, () => setRecord('unavailable'));
  useEffect(() => {
    if (!studyId) return;
    setRecord('loading');
    const read = api.fence({ studyId });
    void (async () => {
      try {
        const state = await api.approach(studyId, read.signal);
        const latest = state.latest_version;
        const saved = latest
          ? await api.approachVersion(studyId, latest.approach_version_id, read.signal)
          : null;
        if (read.valid())
          setRecord({
            studyId,
            version: saved?.version ?? null,
            draft: state.draft?.content ?? null,
          });
      } catch (error) {
        if (!read.signal.aborted) await api.readFailed(error, read);
        if (read.valid()) setRecord('unavailable');
      } finally {
        read.done();
      }
    })();
    return () => {
      read.abort();
      read.done();
    };
  }, [api, studyId, api.actor]);
  if (!snapshot) return { kind: 'none' };
  if (record === 'loading') return { kind: 'loading' };
  if (record === 'unavailable' || record.studyId !== studyId) return { kind: 'unavailable' };
  if ('draft_revision' in snapshot && record.draft) {
    return { kind: 'loaded', links: methodLinks(record.draft, null, snapshot) };
  }
  if (!record.version) return { kind: 'loaded', links: [] };
  return {
    kind: 'loaded',
    links: methodLinks(
      record.version.content,
      { id: record.version.approach_version_id, number: record.version.version_number },
      snapshot,
    ),
  };
}
