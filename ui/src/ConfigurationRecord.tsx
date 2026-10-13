import { ConfigurationApproachRecord } from './ConfigurationApproach';
import type { ApproachClosureRead3 } from './contract';
import { Assumptions } from './Assumptions';
import type { ConfigurationRevision, EvidenceSnapshot, ModelRevisionRead4, PortRef, RetainedResults } from './contract';
import { ActionDialog, Button, DataTable, Field, SectionHeader, CriterionRecord, formatNumber } from './design';
import { EvidenceReferences } from './EvidenceView';
import { criterionOperators } from './criterionLabels';
import { useId, useState } from 'react';
import { ModelView } from './ModelView';
import { retainedApproachVersion, retainedMethodLinks } from './modelMethods';
import type { Selection } from './workspaceModel';
import { configurationContext, linkedApproach, modelAssumptions, recordLimitations, unreadableModelAssumptions } from './recordViews';

/** Shared read-only layout. It cannot query current models or submit a run. */
export function ConfigurationRecord({ configuration: c, model, results, approachClosure,  onViewSourceResult }: { approachClosure?: ApproachClosureRead3 | null; configuration: ConfigurationRevision; model: ModelRevisionRead4 | null; results?: RetainedResults | null; onViewSourceResult?: (runId: string, output: PortRef) => void }) {
  const quantity = (target: PortRef) => {
    const instance = model?.instances.find(i => i.instance_id === target.instance_id);
    const port = model?.definitions.find(d => d.definition_version_id === instance?.definition_version_id)?.ports.find(p => p.port_id === target.port_id);
    return `${instance?.name ?? target.instance_id} · ${port?.name ?? target.port_id}`;
  };
  const references = (ids: string[] = []) => <EvidenceReferences records={c.evidence_snapshots} ids={ids} />;
  const context = configurationContext(c);
  // An unreadable format is named, never read as an older one; Record details keep the exact record.
  if (context.kind === 'unsupported') return <section className="configuration-section configuration-context" aria-label="Configuration context"><SectionHeader title="Context" /><p role="status">{recordLimitations.configurationUnsupported} The full configuration record is available in Record details.</p></section>;
  const reasons: Record<string, string> = { required_output_unavailable: 'Required output unavailable', convergence_unresolved: 'Convergence unresolved', invalid_criterion_or_units: 'Invalid criterion or units' };
  return <>
    {context.derivation.kind === 'recorded' && context.derivation.derivation && <p>Based on run {context.derivation.derivation.source_run_id.slice(0,8)} · Configuration origin; numerical dependencies are shown with each input.</p>}
    <section className="configuration-section configuration-context" aria-label="Configuration context"><SectionHeader title="Context" />
      <p className="evidence-content">{c.context_snapshot.description || 'No description.'}</p>{c.context_snapshot.boundary && <p className="evidence-content">{c.context_snapshot.boundary}</p>}
      {references(context.generalContext.evidenceVersionIds)}
      <ConfigurationApproachRecord selection={linkedApproach(context)} closure={approachClosure} />
    </section>
    <SectionHeader title="Inputs and provenance" />
    {c.inputs.length ? <DataTable regionLabel="Saved configuration inputs" className="configuration-inputs"><thead><tr><th>Free input</th><th>Value</th><th>Units</th><th>Provenance</th></tr></thead><tbody>{c.inputs.map(i => {
      const binding = 'result_binding' in i ? i.result_binding : null;
      return <tr key={`${i.target.instance_id}/${i.target.port_id}`}><th scope="row">{quantity(i.target)}</th><td><span title={`Full precision: ${i.value}`}><Field compact label={quantity(i.target) + ' value'} value={formatNumber(i.value)} unit="" state="readonly" className="configuration-value" /></span></td><td>{i.units || 'dimensionless'}</td><td>{binding && <><p>Uses result from {binding.labels.run_name} · {binding.labels.instance_name} · {binding.labels.output_name}</p><p className="context-line">{binding.labels.model_name ?? 'Unnamed model'} · Model version {binding.labels.model_revision_id.slice(0,8)}</p><p title={`Full-precision original: ${binding.original_value}; factor: ${binding.conversion.factor}; received: ${binding.conversion.destination_value}`}>{formatNumber(binding.original_value)} {binding.original_units || 'dimensionless'} → {formatNumber(binding.conversion.destination_value)} {binding.conversion.destination_units || 'dimensionless'} · factor {formatNumber(binding.conversion.factor)}</p>{onViewSourceResult && <Button size="sm" onClick={() => onViewSourceResult(binding.source_run_id, binding.source_output)}>View source result</Button>}</>}<p className="evidence-content">{i.provenance.statement}</p>{references(i.provenance.evidence_version_ids)}</td></tr>;
    })}</tbody></DataTable> : <p>No free inputs were specified.</p>}
    <section className="configuration-section configuration-criterion"><SectionHeader title="Criteria" />
    {c.criteria.length ? c.criteria.map((criterion, index) => {
      const outcome = results?.criteria.find(r => r.criterion_id === criterion.criterion_id);
      return <CriterionRecord key={criterion.criterion_id} number={index + 1} target={quantity(criterion.target)} comparison={criterionOperators[criterion.operator]} threshold={criterion.threshold} units={criterion.units}
        tolerances={criterion.operator === 'eq' ? { absolute: criterion.absolute_tolerance ?? null, relative: criterion.relative_tolerance ?? null } : undefined}
        evaluation={results !== undefined ? { label: outcome?.outcome === 'met' ? 'Met' : outcome?.outcome === 'violated' ? 'Not met' : 'Not evaluated', tone: outcome?.outcome === 'met' ? 'ok' : outcome?.outcome === 'violated' ? 'alarm' : 'advisory', reason: outcome && outcome.reason !== 'threshold_comparison' ? reasons[outcome.reason] ?? 'Criterion evaluation reason unavailable' : undefined } : undefined}
        evidence={references(criterion.evidence_version_ids)} />;
    }) : <p>No criteria specified.</p>}
    {results?.criteria.filter(outcome => !c.criteria.some(criterion => criterion.criterion_id === outcome.criterion_id)).map(outcome => <p key={outcome.criterion_id}>Criterion definition unavailable: {outcome.criterion_id} · {outcome.outcome === 'met' ? 'Met' : outcome.outcome === 'violated' ? 'Not met' : 'Not evaluated'}</p>)}
    </section>
    {context.assumptions.kind === 'recorded' && <section className="configuration-section" aria-label="Configuration assumption owners"><Assumptions ownerKey={c.configuration_revision_id} ownerLabel="Configuration" items={context.assumptions.items} records={c.evidence_snapshots} /><ModelAssumptionsLink model={model} records={c.evidence_snapshots} configuration={c} closure={approachClosure} /></section>}

  </>;
}

/** A configuration does not repeat its model's assumptions. One line states how
 * many the exact selected or retained model version records and opens them read-only; the
 * model owns and lists them. No library or model service reads. */
export function ModelAssumptionsLink({ model, records, configuration, closure }: { model: ModelRevisionRead4 | null; records: EvidenceSnapshot[]; configuration?: ConfigurationRevision; closure?: ApproachClosureRead3 | null }) {
  const view = modelAssumptions(model);
  const summary = view.kind === 'recorded' && model ? `${view.items.length} in Model version ${model.model_revision_id.slice(0, 8)}`
    : view.kind === 'not_in_format' ? recordLimitations.modelAssumptionsNotInFormat
    : unreadableModelAssumptions(view) ? recordLimitations.modelAssumptionsUnreadable
    : recordLimitations.modelVersionUnavailable;
  // The action opens the canonical model view of this exact version, read-only, with
  // nothing selected (the model's own assumptions); each component lists its own.
  const [selection, setSelection] = useState<Selection>({ kind: 'none' }), viewId = useId();
  return <div className="model-assumptions-link"><span>Model assumptions: {summary}</span>
    {model && view.kind === 'recorded' && view.items.length > 0 && <ActionDialog title={'Model version ' + model.model_revision_id.slice(0, 8)} label="View model assumptions" size="sm" width="workspace">
      <p className="context-line">Read-only · select a component to see its assumptions, what it computes and why</p>
      <ModelView idPrefix={viewId + '-'} snapshot={model} selection={selection} onSelect={setSelection} evidence={records} values={configuration ? { kind: 'configuration', configuration } : undefined} methods={retainedMethodLinks(retainedApproachVersion(configuration, closure), model)} />
    </ActionDialog>}
  </div>;
}

/** Scoped configuration provenance action for saved and retained headers. */
export function ConfigurationRecordDetails({ configuration: c }: { configuration: ConfigurationRevision }) {
  return <ActionDialog title="Configuration record" label="Record details" size="sm"><dl className="hf-record-details"><dt>Configuration version</dt><dd>{c.configuration_revision_id}</dd><dt>Model version</dt><dd>{c.model_revision_id}</dd></dl><pre tabIndex={0} aria-label="Saved configuration JSON">{JSON.stringify(c, null, 2)}</pre></ActionDialog>;
}
