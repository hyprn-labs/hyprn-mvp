import { formatNumber } from './numbers';
import { displayUnit } from '../unitLabels';

/** Presentation of a saved error rule, never a calculation or a validation decision.
 * A relative allowance must name its dimensional reference; an unknown unit is not dimensionless.
 */
export function ErrorAllowance({
  absolute,
  relative,
  units,
  reference,
  compact = false,
}: {
  absolute: number;
  relative: number;
  units: string | undefined;
  reference: 'calculated output' | 'criterion threshold';
  compact?: boolean;
}) {
  if (
    units === undefined ||
    !Number.isFinite(absolute) ||
    !Number.isFinite(relative) ||
    absolute < 0 ||
    relative < 0
  )
    return <span>Allowance unavailable</span>;
  const unit = units ? ` ${displayUnit(units)}` : '';
  if (compact)
    return (
      <span
        className="hf-error-allowance"
        aria-label={`${formatNumber(absolute)}${unit} plus ${formatNumber(relative * 100)}% of the magnitude of the ${reference}`}
      >
        <span>
          {formatNumber(absolute)}
          {unit}
        </span>
        <span>
          + {formatNumber(relative * 100)}% × |
          {reference === 'calculated output' ? 'output' : 'threshold'}|
        </span>
      </span>
    );
  return (
    <span title={`${absolute}${unit} + ${relative} × |${reference}|`}>
      {formatNumber(absolute)}
      {unit} + {formatNumber(relative * 100)}% × |{reference}|
    </span>
  );
}
