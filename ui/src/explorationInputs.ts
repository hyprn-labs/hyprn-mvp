import type { ExplorationInput1, PortRef } from './contract';
import type { ExplorationDesignRequest1 } from './contract';

export type Dimension = ExplorationDesignRequest1['combinations'][number]['dimensions'][number];
export type SelectedInput = { target: PortRef; value: number | null; units: string };

export function explorationReason(reason?: string | null): string | null {
  if (!reason) return null;
  const labels: Record<string, string> = {
    observed_tolerance_unmet: 'Accuracy target not met',
    outside_sampled_coverage: 'Outside sampled coverage',
    outside_bounds: 'Outside the declared range',
    incomplete_samples: 'Some required calculations are missing',
    underfunded_design: 'More calculated samples are needed',
    underfunded_or_failed_fits: 'Too few samples or fitting failed',
    fit_failed: 'Fitting failed',
    original_unavailable: 'The original calculation has no result',
    nonfinite_prediction: 'The estimate is not a finite number',
    numerical_unavailable: 'The calculation service is unavailable',
  };
  return labels[reason] ?? reason.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase());
}

export function selectInput(
  vector: SelectedInput[],
  dimensions: Dimension[],
  target: PortRef,
  value: number | null,
) {
  const control = dimensions.find((d) => key(d.target) === key(target));
  return vector.map((p) => {
    const d = dimensions.find((item) => key(item.target) === key(p.target));
    return key(p.target) === key(target) ||
      (control?.covary_group && d?.covary_group === control.covary_group)
      ? { ...p, value }
      : p;
  });
}

export function carryCommon(
  vector: SelectedInput[],
  before: Dimension[],
  baseline: SelectedInput[],
  after: Dimension[],
) {
  let next = baseline;
  for (const d of after) {
    if (!d.common_key) continue;
    const old = before.find(
      (p) => p.common_key === d.common_key && p.units === d.units && p.step === d.step,
    );
    const value = old && vector.find((p) => key(p.target) === key(old.target))?.value;
    if (
      value !== undefined &&
      value !== null &&
      d.lower !== null &&
      d.upper !== null &&
      value >= d.lower &&
      value <= d.upper &&
      validStep(value, d)
    )
      next = selectInput(next, after, d.target, value);
  }
  return next;
}

export function validStep(value: number, d: Dimension) {
  if (d.step === null) return true;
  if (d.lower === null) return false;
  const n = (value - d.lower) / d.step;
  return Math.abs(n - Math.round(n)) <= Number.EPSILON * Math.max(1, Math.abs(n)) * 8;
}

export function completeVector(vector: SelectedInput[], dimensions: Dimension[]) {
  if (
    vector.some(
      (p) =>
        p.value === null ||
        !Number.isFinite(p.value) ||
        Math.abs(p.value) > Number.MAX_SAFE_INTEGER,
    )
  )
    return undefined;
  if (
    dimensions.some((d) => {
      const p = vector.find((i) => key(i.target) === key(d.target));
      return !p || p.value === null || !validStep(p.value, d);
    })
  )
    return undefined;
  return vector as QuantityInput[];
}

export function supportedCombination(
  combinations: ExplorationDesignRequest1['combinations'],
  values: string[],
) {
  return combinations.find(
    (c) => c.categories.length === values.length && c.categories.every((v, i) => v === values[i]),
  );
}

type QuantityInput = { target: PortRef; value: number; units: string };
const key = (ref: PortRef) => ref.instance_id + '/' + ref.port_id;

/** A saved number is inseparable from its saved unit; model units are metadata. */
export function savedInputQuantity(input: ExplorationInput1) {
  return input.binding.kind === 'free' ? input.binding.assignment : undefined;
}

/** V1 numerical preparation requires exact units and never converts in the browser. */
export function preparedInputUnitsMatch(inputs: ExplorationInput1[]) {
  return inputs.every((input) => {
    const quantity = savedInputQuantity(input);
    return !quantity || quantity.units === input.units;
  });
}

export function explorationInputVector(
  inputs: ExplorationInput1[],
  axis?: PortRef,
  value?: number | null,
): QuantityInput[] | undefined {
  if (axis) {
    const input = inputs.find((item) => key(item.target) === key(axis));
    const quantity = input && savedInputQuantity(input);
    if (!quantity || quantity.units !== input?.units || value == null) return undefined;
  }
  return inputs.flatMap((input) => {
    const quantity = savedInputQuantity(input);
    return quantity
      ? [
          {
            target: input.target,
            units: quantity.units,
            value: axis && key(input.target) === key(axis) ? value! : quantity.value,
          },
        ]
      : [];
  });
}

export function sameInputVector(expected: QuantityInput[], actual: QuantityInput[]) {
  return (
    expected.length === actual.length &&
    expected.every((value) =>
      actual.some(
        (item) =>
          key(item.target) === key(value.target) &&
          item.units === value.units &&
          item.value === value.value,
      ),
    )
  );
}

export type ExplorationPoint = {
  inputs: { target: PortRef; value: number; units: string }[];
  outputs: {
    target: PortRef;
    value: number | null;
    units: string;
    kind: 'calculated' | 'estimated' | 'unavailable';
    reason?: string | null;
    run_id?: string | null;
    preparation_id?: string;
  }[];
};

/** Stops belong to this exact fixed-input slice, including explicit covary bindings. */
export function availableStops(
  points: ExplorationPoint[],
  vector: SelectedInput[],
  dimensions: Dimension[],
  target: PortRef,
  outputs: PortRef[],
) {
  const control = dimensions.find((d) => key(d.target) === key(target));
  const available = new Map<number, 'calculated' | 'estimated'>();
  for (const point of points) {
    const value = point.inputs.find((v) => key(v.target) === key(target));
    if (
      !value ||
      (control &&
        (!validStep(value.value, control) ||
          (control.lower !== null && value.value < control.lower) ||
          (control.upper !== null && value.value > control.upper)))
    )
      continue;
    const candidate = selectInput(vector, dimensions, target, value.value);
    if (!sameInputVector(candidate as ExplorationPoint['inputs'], point.inputs)) continue;
    const results = outputs.map((t) => point.outputs.find((o) => key(o.target) === key(t)));
    if (
      !results.length ||
      results.some(
        (o) => !o || o.kind === 'unavailable' || o.value === null || !Number.isFinite(o.value),
      )
    )
      continue;
    const kind = results.every((o) => o?.kind === 'calculated') ? 'calculated' : 'estimated';
    if (available.get(value.value) !== 'calculated') available.set(value.value, kind);
  }
  return [...available].sort(([a], [b]) => a - b).map(([value, kind]) => ({ value, kind }));
}

/** Keep every prepared coordinate selectable; its basis belongs to the current full vector. */
export function selectableStops(
  points: ExplorationPoint[],
  vector: SelectedInput[],
  dimensions: Dimension[],
  target: PortRef,
  outputs: PortRef[],
): { value: number; kind: 'calculated' | 'estimated' | 'unavailable' }[] {
  const available = new Map(
    availableStops(points, vector, dimensions, target, outputs).map((p) => [p.value, p.kind]),
  );
  const control = dimensions.find((d) => key(d.target) === key(target));
  const units = vector.find((p) => key(p.target) === key(target))?.units;
  const values = new Set<number>();
  for (const point of points) {
    const input = point.inputs.find((p) => key(p.target) === key(target));
    if (!input || input.units !== units || !Number.isFinite(input.value)) continue;
    if (
      control &&
      (!validStep(input.value, control) ||
        (control.lower !== null && input.value < control.lower) ||
        (control.upper !== null && input.value > control.upper))
    )
      continue;
    values.add(input.value);
  }
  return [...values]
    .sort((a, b) => a - b)
    .map((value) => ({ value, kind: available.get(value) ?? 'unavailable' }));
}
