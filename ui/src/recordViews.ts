import type {
  ModifiedRunSeedRead6,
  ConfigurationAssumption,
  ConfigurationCandidate,
  ConfigurationCandidate6,
  ConfigurationRevisionRead6,
  Criterion,
  Derivation,
  EvidenceRecord,
  EvidenceSnapshot,
  Instance,
  ModelAssumption,
  ModelDraftRead4,
  ModelRevisionRead4,
} from './contract';

/**
 * Domain read views over versioned wire records.
 *
 * Display components request these views instead of branching on wire schema
 * versions, so supporting a new record version has one interpretation point per
 * record family, in this file:
 * - model assumptions: `modelAssumptions` (Model1–4 revisions and drafts);
 * - configuration context: `configurationContext` (Configuration1–4 records and candidates);
 * - evidence snapshots: `evidenceSnapshotView` (Evidence1–3 records).
 *
 * Every view keeps the source format version beside the projected data and never
 * replaces the record: identities, digests and evidence snapshots are still read
 * from the record itself. Views distinguish an unavailable record, a concept the
 * format does not record, invalid content and a format this application cannot
 * read. They invent no defaults, upgrade no scientific meaning and never change
 * the source record. Command producers, api.ts (transport) and exports.ts (import
 * admission) keep explicit versions.
 */

/** Exact wording for limitations that more than one display states. */
export const recordLimitations = {
  modelAssumptionsNotInFormat: 'Model versions saved in this older format have no assumptions.',
  modelAssumptionsUnreadable:
    'This application cannot read assumptions from this model version format.',
  modelVersionUnavailable: "This model version can't be loaded.",
  configurationUnsupported:
    'This configuration uses a record format this application cannot display.',
  evidenceUnsupported: 'This evidence uses a record format this application cannot display.',
} as const;

/** Assumptions recorded by one exact model version or draft. */
export type ModelAssumptionsView =
  /** No model record was retained or read; nothing is substituted. */
  | { kind: 'unavailable' }
  | {
      kind: 'recorded';
      version: '2' | '3' | '4';
      items: ModelAssumption[];
      modelOwned: ModelAssumption[];
      components: Array<{ instance: Instance; items: ModelAssumption[] }>;
    }
  /** Model1 has no assumption concept; this is not an empty list. */
  | { kind: 'not_in_format'; version: '1' }
  /** The format requires an assumption list but the record carries none. */
  | { kind: 'invalid'; version: '2' | '3' | '4' }
  /** A format this application cannot read; compatibility is never guessed. */
  | { kind: 'unsupported'; version: string };

export function modelAssumptions(
  model: ModelRevisionRead4 | ModelDraftRead4 | null | undefined,
): ModelAssumptionsView {
  if (!model) return { kind: 'unavailable' };
  const format: string = model.schema_version;
  if (model.schema_version === '1') return { kind: 'not_in_format', version: '1' };
  if (model.schema_version !== '2' && model.schema_version !== '3' && model.schema_version !== '4')
    return { kind: 'unsupported', version: format };
  const version = model.schema_version,
    items = model.assumptions;
  if (!Array.isArray(items)) return { kind: 'invalid', version };
  const owned = (instance: Instance) =>
    items.filter(
      (a) => a.owner.kind === 'instance' && a.owner.instance_id === instance.instance_id,
    );
  return {
    kind: 'recorded',
    version,
    items,
    modelOwned: items.filter((a) => a.owner.kind === 'model'),
    components: model.instances
      .filter((instance) => owned(instance).length)
      .map((instance) => ({ instance, items: owned(instance) })),
  };
}

/** Assumption items when the exact format records them; otherwise none are read. */
export function recordedModelAssumptions(view: ModelAssumptionsView): ModelAssumption[] {
  return view.kind === 'recorded' ? view.items : [];
}

/** True when assumptions cannot be read from the record (as opposed to absent from its format). */
export function unreadableModelAssumptions(view: ModelAssumptionsView): boolean {
  return view.kind === 'unsupported' || view.kind === 'invalid';
}

/** Context of one exact configuration record or candidate. */
export type ConfigurationContextView =
  | {
      kind: 'supported';
      version: '1' | '2' | '3' | '4' | '6';
      /** Configuration3+ select general context explicitly. Older formats (legacy description)
       * only imply it: evidence not owned by any input or criterion. */
      generalContext:
        | { kind: 'explicit'; evidenceVersionIds: string[] }
        | { kind: 'legacy_unowned'; evidenceVersionIds: string[] };
      assumptions:
        { kind: 'recorded'; items: ConfigurationAssumption[] } | { kind: 'not_in_format' };
      derivation: { kind: 'recorded'; derivation: Derivation | null } | { kind: 'not_in_format' };
    }
  /** A format this application cannot read; nothing is read as an older format. */
  | { kind: 'unsupported'; version: string };

export function configurationContext(
  c: ConfigurationRevisionRead6 | ConfigurationCandidate | ConfigurationCandidate6,
): ConfigurationContextView {
  const format: string = c.schema_version;
  if (c.schema_version === '3' || c.schema_version === '4')
    return {
      kind: 'supported',
      version: c.schema_version,
      generalContext: {
        kind: 'explicit',
        evidenceVersionIds: c.general_context_evidence_version_ids,
      },
      assumptions: { kind: 'recorded', items: c.assumptions },
      derivation: { kind: 'recorded', derivation: c.derivation },
    };
  if (c.schema_version === '6')
    return {
      kind: 'supported',
      version: c.schema_version,
      generalContext: {
        kind: 'explicit',
        evidenceVersionIds: c.general_context_evidence_version_ids,
      },
      assumptions: { kind: 'recorded', items: c.assumptions },
      derivation: { kind: 'recorded', derivation: c.derivation },
    };
  if (c.schema_version === '1' || c.schema_version === '2') {
    const owned = new Set([
      ...c.inputs.flatMap((i) => i.provenance.evidence_version_ids),
      ...c.criteria.flatMap((i) => i.evidence_version_ids),
    ]);
    return {
      kind: 'supported',
      version: c.schema_version,
      generalContext: {
        kind: 'legacy_unowned',
        evidenceVersionIds: c.evidence_snapshots
          .filter((e) => !owned.has(e.evidence_version_id))
          .map((e) => e.evidence_version_id),
      },
      assumptions: { kind: 'not_in_format' },
      derivation:
        c.schema_version === '2'
          ? { kind: 'recorded', derivation: c.derivation }
          : { kind: 'not_in_format' },
    };
  }
  return { kind: 'unsupported', version: format };
}

/** Thrown when a record's format cannot be projected; callers state the limitation. */
export class UnsupportedRecordVersion extends Error {}

/** Snapshot shape of one exact evidence record, as a configuration retains it. */
export function evidenceSnapshotView(record: EvidenceRecord): EvidenceSnapshot {
  const common = {
    evidence_version_id: record.evidence_version_id,
    kind: record.kind,
    content: record.content,
    source_refs: record.source_refs,
  };
  // Evidence1 carries a legacy free-text scope, never a typed resource scope.
  if (!('evidence_schema_version' in record)) return common;
  if (record.evidence_schema_version === '2')
    return {
      ...common,
      evidence_schema_version: record.evidence_schema_version,
      resource_scope: record.resource_scope,
    };
  if (record.evidence_schema_version === '3') return record;
  throw new UnsupportedRecordVersion(recordLimitations.evidenceUnsupported);
}

/** A retained configuration's own criteria. Version 6 carries none: study criteria are
 * defined in the brief and evaluated through calculation bindings. */
export function configurationCriteria(
  c: ConfigurationRevisionRead6 | ConfigurationCandidate | ConfigurationCandidate6,
): Criterion[] {
  return c.schema_version === '6' ? [] : c.criteria;
}

/** Whether a retained configuration carries its own criteria (versions before 6). */
export function carriesOwnCriteria(
  c: ConfigurationRevisionRead6 | ConfigurationCandidate | ConfigurationCandidate6,
): boolean {
  return c.schema_version !== '6';
}

/** New configurations need a model version in the current format (Model4). */
export function configurableModel(model: ModelRevisionRead4 | ModelDraftRead4): boolean {
  return model.schema_version === '4';
}

/** A modified-run seed that can be saved: from a configuration without criteria (seed 8). */
export function criteriaFreeSeed(seed: ModifiedRunSeedRead6): boolean {
  return seed.schema_version === '8';
}
