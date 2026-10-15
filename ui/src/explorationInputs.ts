import type { ExplorationInput1, PortRef } from './contract';

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
