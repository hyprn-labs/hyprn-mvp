import type { Criterion } from './contract';

export const criterionOperators: Record<Criterion['operator'], string> = {
  lt: 'less than',
  le: 'at most',
  eq: 'equal to',
  ge: 'at least',
  gt: 'greater than',
};

/** Quantity-name comparison ignores presentation casing and whitespace only. */
export function sameQuantityName(left: string, right: string): boolean {
  const normalize = (name: string) => name.trim().replace(/\s+/g, ' ').toLowerCase();
  return normalize(left) === normalize(right);
}

/** Suggest only a unique quantity-name and exact-unit match, never a dimensional guess. */
export function suggestCriterionOutput(
  criterion: { name: string; units: string },
  outputs: { key: string; name: string; units: string | undefined }[],
): string {
  const matching = outputs.filter(
    (output) => output.units === criterion.units && sameQuantityName(output.name, criterion.name),
  );
  return matching.length === 1 ? matching[0].key : '';
}

/** Output names suffice unless another offered quantity has the same name. */
export function criterionOutputLabels(
  outputs: { key: string; name: string; label: string }[],
): Record<string, string> {
  return Object.fromEntries(
    outputs.map((output) => [
      output.key,
      outputs.filter((other) => sameQuantityName(other.name, output.name)).length > 1
        ? output.label
        : output.name,
    ]),
  );
}
