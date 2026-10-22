import type {
  FrozenConfigurationRead7,
  LiteralRequest,
  ResultRequest,
  ResultBinding,
  ModelRevisionRead4,
  SampledDesign1,
  SampledDesign2,
  SampledDesign3,
  SampledDesign4,
  SampledDimension1,
} from './contract';
import { modelPorts } from './modelPorts';
import { resolvedUnit } from './unitLabels';

export type SamplingRow = {
  mode: 'fixed' | 'range';
  value: string;
  lower: string;
  upper: string;
  step: string;
};
const key = (target: { instance_id: string; port_id: string }) =>
  target.instance_id + '/' + target.port_id;
const freeInputs = (model: ModelRevisionRead4) =>
  modelPorts(model).filter(
    (p) =>
      p.direction === 'input' &&
      !model.connections.some((c) => key(c.target_ref) === key(p.target)),
  );

/** Only revising this design restores values. An unrelated configuration is never a default. */
export function samplingRows(
  model: ModelRevisionRead4,
  reference: FrozenConfigurationRead7 | null,
  dimensions: SampledDimension1[] = [],
): Record<string, SamplingRow> {
  return Object.fromEntries(
    freeInputs(model).map((p) => {
      const input = reference?.configuration.inputs.find((i) => key(i.target) === key(p.target));
      const range = dimensions.find((d) => key(d.target) === key(p.target));
      return [
        key(p.target),
        {
          mode: range ? 'range' : 'fixed',
          value: input ? String(input.value) : '',
          lower: range ? String(range.lower) : '',
          upper: range ? String(range.upper) : '',
          step: range?.step == null ? '' : String(range.step),
        },
      ];
    }),
  );
}

export function samplingDeclaration(
  model: ModelRevisionRead4,
  rows: Record<string, SamplingRow>,
  reference: FrozenConfigurationRead7 | null,
  design: SampledDesign1 | SampledDesign2 | SampledDesign3 | SampledDesign4 | null,
) {
  const dimensions: SampledDimension1[] = [];
  const inputs: Array<LiteralRequest | ResultRequest> = [];
  let reuseReference = reference !== null;
  const finite = (text: string, label: string) => {
    const value = text.trim() ? Number(text) : NaN;
    if (!Number.isFinite(value) || (Number.isInteger(value) && !Number.isSafeInteger(value)))
      throw new Error(`${label}: enter an explicit finite value.`);
    return value;
  };
  for (const port of freeInputs(model)) {
    const row = rows[key(port.target)];
    const units = resolvedUnit(port.units);
    if (units === undefined) throw new Error(`${port.label}: specify units in the model first.`);
    const old = reference?.configuration.inputs.find((i) => key(i.target) === key(port.target));
    const original = design?.groups[0]?.dimensions.find((d) => key(d.target) === key(port.target));
    let value: number;
    let statement: string;
    let unchanged = false;
    if (row.mode === 'range') {
      const lower = finite(row.lower, port.label + ' minimum');
      const upper = finite(row.upper, port.label + ' maximum');
      const step = row.step.trim() ? finite(row.step, port.label + ' step') : null;
      if (lower >= upper || (step !== null && step <= 0))
        throw new Error(`${port.label}: maximum must exceed minimum; step must be positive.`);
      dimensions.push({
        target: port.target,
        units,
        lower,
        upper,
        step,
        covary_group: original?.covary_group ?? null,
      });
      unchanged =
        original?.lower === lower &&
        original.upper === upper &&
        original.step === step &&
        original.units === units;
      value = old?.value ?? lower;
      statement =
        unchanged && old
          ? old.provenance.statement
          : `User-declared exploration range: ${lower} to ${upper} ${units || '(dimensionless)'}` +
            (step === null ? '.' : `; step ${step}.`) +
            ' The minimum is the preparation anchor when no earlier anchor exists.';
    } else {
      value = finite(row.value, port.label);
      unchanged = old?.value === value && old.units === units;
      statement =
        unchanged && old
          ? old.provenance.statement
          : 'Fixed value explicitly entered for this sampling analysis.';
      if (!unchanged) reuseReference = false;
    }
    const binding =
      old && 'result_binding' in old
        ? (old as { result_binding: ResultBinding | null }).result_binding
        : null;
    if (row.mode === 'fixed' && unchanged && binding) {
      inputs.push({
        kind: 'run_result',
        target: port.target,
        source_run_id: binding.source_run_id,
        source_output: binding.source_output,
        expected_results_digest: binding.results_digest,
        provenance: old!.provenance,
      });
      continue;
    }
    inputs.push({
      kind: 'literal',
      target: port.target,
      value,
      units,
      provenance:
        unchanged && old
          ? old.provenance
          : {
              kind: 'manual',
              statement,
              evidence_version_ids: [],
            },
    });
  }
  if (!dimensions.length) throw new Error('Set at least one input to Range.');
  // Existing range provenance belongs only to its exact bounds, units and step. New bounds
  // record the user's declaration; they do not inherit an old scientific justification.
  const unchangedRanges =
    design &&
    dimensions.length === design.groups[0]?.dimensions.length &&
    dimensions.every((d) =>
      design.groups[0].dimensions.some(
        (old) =>
          key(old.target) === key(d.target) &&
          old.lower === d.lower &&
          old.upper === d.upper &&
          old.units === d.units &&
          old.step === d.step &&
          old.covary_group === d.covary_group,
      ),
    );
  const rationale = unchangedRanges
    ? design.rationale
    : dimensions
        .map((d) => {
          const old = design?.groups[0]?.dimensions.find((o) => key(o.target) === key(d.target));
          const same =
            old &&
            old.lower === d.lower &&
            old.upper === d.upper &&
            old.units === d.units &&
            old.step === d.step;
          return (
            `${modelPorts(model).find((p) => key(p.target) === key(d.target))!.label}: ` +
            `${d.lower} to ${d.upper} ${d.units || '(dimensionless)'}` +
            (d.step === null ? '' : `; step ${d.step}`) +
            '. ' +
            (same
              ? `Recorded range provenance: ${design!.rationale}`
              : 'User-declared exploration range.')
          );
        })
        .join('\n');
  return { inputs, dimensions, rationale, reuseReference };
}
