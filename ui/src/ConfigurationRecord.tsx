import { OpenLink } from './design';
import type { HyprnMvpApi } from './api';
import { RecordDetails } from './design';
import { displayUnit } from './unitLabels';
import { AttributionDetail } from './attribution';
import { Assumptions } from './Assumptions';
import type {
  ConfigurationRevisionRead6,
  EvidenceSnapshot,
  ModelRevisionRead5,
  PortRef,
  RetainedResultsRead3,
} from './contract';
import {
  ActionDialog,
  Button,
  DataTable,
  Field,
  SectionHeader,
  CriterionRecord,
  formatNumber,
} from './design';
import { EvidenceReferences } from './EvidenceView';
import { criterionOperators } from './criterionLabels';
import { useId, useState } from 'react';
import { ModelView } from './ModelView';
import type { Selection } from './workspaceModel';
import {
  configurationContext,
  modelAssumptions,
  recordLimitations,
  unreadableModelAssumptions,
  configurationCriteria,
  carriesOwnCriteria,
} from './recordViews';

/** Shared read-only layout. It cannot query current models or submit a run. */
export function ConfigurationRecord({
  api,
  configuration: c,
  model,
  results,
  onViewSourceResult,
}: {
  api?: HyprnMvpApi;
  configuration: ConfigurationRevisionRead6;
  model: ModelRevisionRead5 | null;
  results?: RetainedResultsRead3 | null;
  onViewSourceResult?: (runId: string, output: PortRef) => void;
}) {
  const quantity = (target: PortRef) => {
    const instance = model?.instances.find((i) => i.instance_id === target.instance_id);
    const port = model?.definitions
      .find((d) => d.definition_version_id === instance?.definition_version_id)
      ?.ports.find((p) => p.port_id === target.port_id);
    return `${instance?.name ?? target.instance_id} · ${port?.name ?? target.port_id}`;
  };
  const references = (ids: string[] = [], label?: string) => (
    <EvidenceReferences records={c.evidence_snapshots} ids={ids} label={label} />
  );
  const context = configurationContext(c);
  // An unreadable format is named, never read as an older one; Record details keep the exact record.
  if (context.kind === 'unsupported')
    return (
      <section
        className="configuration-section configuration-context"
        aria-label="Configuration context"
      >
        <SectionHeader title="Context" />
        <p role="status">
          {recordLimitations.configurationUnsupported} The full configuration record is available in
          Record details.
        </p>
      </section>
    );
  const reasons: Record<string, string> = {
    required_output_unavailable: 'Required output unavailable',
    convergence_unresolved: 'Convergence unresolved',
    invalid_criterion_or_units: 'Invalid criterion or units',
  };
  const criteria = configurationCriteria(c);
  // Results 3 carry no criteria; earlier results record one outcome per configuration criterion.
  const resultCriteria = results && 'criteria' in results ? results.criteria : [];
  return (
    <>
      <SectionHeader help="inputs" title="Inputs and provenance" />
      {c.inputs.length ? (
        <DataTable regionLabel="Saved configuration inputs" className="configuration-inputs">
          <thead>
            <tr>
              <th>Free input</th>
              <th className="hf-th--num">Value</th>
              <th>Units</th>
              <th>Provenance</th>
            </tr>
          </thead>
          <tbody>
            {c.inputs.map((i) => {
              const binding = 'result_binding' in i ? i.result_binding : null;
              return (
                <tr key={`${i.target.instance_id}/${i.target.port_id}`}>
                  <th scope="row">{quantity(i.target)}</th>
                  <td className="num">
                    <span title={`Full precision: ${i.value}`}>
                      <Field
                        compact
                        label={quantity(i.target) + ' value'}
                        value={formatNumber(i.value)}
                        unit=""
                        state="readonly"
                        className="configuration-value"
                      />
                    </span>
                  </td>
                  <td>{i.units ? displayUnit(i.units) : 'dimensionless'}</td>
                  <td>
                    {binding && (
                      <>
                        <p>
                          Uses result from {binding.labels.run_name} ·{' '}
                          {binding.labels.instance_name} · {binding.labels.output_name}
                        </p>
                        <p className="context-line">
                          {binding.labels.model_name ?? 'Unnamed model'}
                        </p>
                        <p
                          title={
                            `Full-precision original: ${binding.original_value}; ` +
                            `factor: ${binding.conversion.factor}; ` +
                            `received: ${binding.conversion.destination_value}`
                          }
                        >
                          {formatNumber(binding.original_value)}{' '}
                          {binding.original_units
                            ? displayUnit(binding.original_units)
                            : 'dimensionless'}{' '}
                          → {formatNumber(binding.conversion.destination_value)}{' '}
                          {binding.conversion.destination_units
                            ? displayUnit(binding.conversion.destination_units)
                            : 'dimensionless'}{' '}
                          · factor {formatNumber(binding.conversion.factor)}
                        </p>
                        {onViewSourceResult && (
                          <OpenLink
                            size="sm"
                            onClick={() =>
                              onViewSourceResult(binding.source_run_id, binding.source_output)
                            }
                          >
                            View source result
                          </OpenLink>
                        )}
                      </>
                    )}
                    <p className="evidence-content">{i.provenance.statement}</p>
                    {references(
                      i.provenance.evidence_version_ids,
                      quantity(i.target) +
                        ' · ' +
                        formatNumber(i.value) +
                        ' ' +
                        (i.units ? displayUnit(i.units) : 'dimensionless'),
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </DataTable>
      ) : (
        <p>No free inputs were specified.</p>
      )}
      {carriesOwnCriteria(c) && (criteria.length > 0 || resultCriteria.length > 0) && (
        <section className="configuration-section configuration-criterion">
          <SectionHeader title="Recorded criteria" />
          {criteria.length ? (
            criteria.map((criterion, index) => {
              const outcome = resultCriteria.find((r) => r.criterion_id === criterion.criterion_id);
              return (
                <CriterionRecord
                  key={criterion.criterion_id}
                  number={index + 1}
                  target={quantity(criterion.target)}
                  comparison={criterionOperators[criterion.operator]}
                  threshold={criterion.threshold}
                  units={criterion.units}
                  tolerances={
                    criterion.operator === 'eq'
                      ? {
                          absolute: criterion.absolute_tolerance ?? null,
                          relative: criterion.relative_tolerance ?? null,
                        }
                      : undefined
                  }
                  evaluation={
                    results !== undefined
                      ? {
                          label:
                            outcome?.outcome === 'met'
                              ? 'Met'
                              : outcome?.outcome === 'violated'
                                ? 'Not met'
                                : 'Not evaluated',
                          tone:
                            outcome?.outcome === 'met'
                              ? 'ok'
                              : outcome?.outcome === 'violated'
                                ? 'alarm'
                                : 'advisory',
                          reason:
                            outcome && outcome.reason !== 'threshold_comparison'
                              ? (reasons[outcome.reason] ??
                                'Criterion evaluation reason unavailable')
                              : undefined,
                        }
                      : undefined
                  }
                  evidence={references(criterion.evidence_version_ids, quantity(criterion.target))}
                />
              );
            })
          ) : (
            <p>No criteria specified.</p>
          )}
          {resultCriteria
            .filter(
              (outcome) =>
                !criteria.some((criterion) => criterion.criterion_id === outcome.criterion_id),
            )
            .map((outcome) => (
              <p key={outcome.criterion_id}>
                Criterion definition unavailable: {outcome.criterion_id} ·{' '}
                {outcome.outcome === 'met'
                  ? 'Met'
                  : outcome.outcome === 'violated'
                    ? 'Not met'
                    : 'Not evaluated'}
              </p>
            ))}
        </section>
      )}
      {context.assumptions.kind === 'recorded' && (
        <section className="configuration-section" aria-label="Configuration assumption owners">
          {context.assumptions.items.length > 0 && (
            <Assumptions
              brief
              ownerKey={c.configuration_revision_id}
              ownerLabel="Configuration"
              items={context.assumptions.items}
              records={c.evidence_snapshots}
            />
          )}
          <ModelAssumptionsLink api={api} studyId={c.study_id} model={model} records={c.evidence_snapshots} configuration={c} />
        </section>
      )}
    </>
  );
}

/** A configuration does not repeat its model's assumptions. One line states how
 * many the exact selected or retained model version records and opens them read-only; the
 * model owns and lists them. No library or model service reads. */
export function ModelAssumptionsLink({
  api,
  studyId,
  model,
  records,
  configuration,
}: {
  api?: HyprnMvpApi;
  studyId?: string;
  model: ModelRevisionRead5 | null;
  records: EvidenceSnapshot[];
  configuration?: ConfigurationRevisionRead6;
}) {
  const view = modelAssumptions(model);
  const summary =
    view.kind === 'recorded' && model
      ? `${view.items.length} in the model`
      : view.kind === 'not_in_format'
        ? recordLimitations.modelAssumptionsNotInFormat
        : unreadableModelAssumptions(view)
          ? recordLimitations.modelAssumptionsUnreadable
          : recordLimitations.modelVersionUnavailable;
  // The action opens the canonical model view of this exact version, read-only, with
  // nothing selected (the model's own assumptions); each component lists its own.
  const [selection, setSelection] = useState<Selection>({ kind: 'none' }),
    viewId = useId();
  if (view.kind === 'recorded' && !view.items.length) return null;
  return (
    <div className="model-assumptions-link">
      <span>Model assumptions: {summary}</span>
      {model && view.kind === 'recorded' && view.items.length > 0 && (
        <ActionDialog
          purpose="reader" title="Model assumptions"
          label="View model assumptions"
          size="sm"
          width="workspace"
        >
          <p className="context-line">
            Read-only · select a component to see its assumptions, what it computes and why
          </p>
          <ModelView
            api={api}
            studyId={studyId}
            idPrefix={viewId + '-'}
            snapshot={model}
            selection={selection}
            onSelect={setSelection}
            evidence={records}
            values={configuration ? { kind: 'configuration', configuration } : undefined}
          />
        </ActionDialog>
      )}
    </div>
  );
}

/** Scoped configuration provenance action for saved and retained headers. */
export function ConfigurationRecordDetails({
  configuration: c,
  metadata,
  primary = false,
}: {
  configuration: ConfigurationRevisionRead6;
  metadata?: React.ReactNode;
  primary?: boolean;
}) {
  return (
    <RecordDetails
      kind="Configuration"
      versionId={primary ? c.configuration_revision_id : undefined}
      metadata={metadata}
    >
      <dl className="hf-record-details">
        <AttributionDetail
          kind="configuration_version"
          id={c.configuration_revision_id}
          label="Saved by"
        />
        <dt>Configuration version</dt>
        <dd>{c.configuration_revision_id}</dd>
        <dt>Model version</dt>
        <dd>{c.model_revision_id}</dd>
      </dl>
      <pre tabIndex={0} aria-label="Saved configuration JSON">
        {JSON.stringify(c, null, 2)}
      </pre>
    </RecordDetails>
  );
}
