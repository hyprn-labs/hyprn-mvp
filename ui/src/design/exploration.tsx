import { useId } from 'react';
import { StatusTag } from './components';
import { TextInput } from './primitives';
import { formatNumber } from './numbers';
import { unitLabel } from '../unitLabels';

/** Select returned query vectors only: drawing a line never evaluates a model. */
export function QuantitySlider({
  label,
  units,
  values,
  lower,
  upper,
  step,
  onFocus,
  value,
  onChange,
}: {
  label: string;
  units: string;
  values?: number[];
  lower?: number | null;
  upper?: number | null;
  step?: number | null;
  onFocus?: () => void;
  value: number | null;
  onChange: (value: number | null) => void;
}) {
  const id = useId(),
    index = value === null ? -1 : (values?.indexOf(value) ?? -1);
  const declared = lower != null && upper != null;
  const outside = declared && value !== null && (value < lower || value > upper);
  const coordinate = declared && value !== null && step ? (value - lower) / step : 0;
  const offStep =
    Math.abs(coordinate - Math.round(coordinate)) >
    Number.EPSILON * Math.max(1, Math.abs(coordinate)) * 8;
  return (
    <div
      className="hf-quantity-slider"
      onFocus={onFocus}
      onPointerDown={(e) => e.stopPropagation()}
    >
      <label htmlFor={id}>
        {label} · {unitLabel(units)}
      </label>
      <TextInput
        id={id}
        type="number"
        step={step ?? 'any'}
        value={value ?? ''}
        onChange={(event) => {
          const next = event.currentTarget.valueAsNumber;
          onChange(
            Number.isFinite(next) && Math.abs(next) <= Number.MAX_SAFE_INTEGER ? next : null,
          );
        }}
      />
      <input
        type="range"
        aria-label={label + (values ? ' prepared points' : ' range')}
        min={values ? 0 : (lower ?? 0)}
        max={values ? Math.max(0, values.length - 1) : (upper ?? 0)}
        step={values ? 1 : (step ?? 'any')}
        value={values ? Math.max(0, index) : (value ?? lower ?? 0)}
        disabled={values ? !values.length : !declared || outside || value === null}
        aria-valuetext={
          value === null ? 'unassigned' : formatNumber(value) + ' ' + unitLabel(units)
        }
        onChange={(event) =>
          onChange(
            values ? values[Number(event.currentTarget.value)] : event.currentTarget.valueAsNumber,
          )
        }
      />
      {(values ? index < 0 : !declared || outside || value === null) && (
        <span role="status">
          {value === null
            ? 'Unassigned'
            : values
              ? 'No prepared estimate at this value.'
              : !declared
                ? 'Declare a range in Sample settings.'
                : 'Outside the declared range.'}
        </span>
      )}
      {offStep && (
        <span role="status">
          Use the declared step of {step} from {lower}.
        </span>
      )}
    </div>
  );
}

export function QuantityResult({
  value,
  units,
  state,
  reason,
}: {
  value: number | null;
  units: string;
  state: 'estimated' | 'calculated' | 'unavailable';
  reason?: string | null;
}) {
  const label =
    value === null ? 'Not computed' : state === 'calculated' ? 'Calculated' : 'Estimated';
  return (
    <div
      className="hf-quantity-result"
      title={value === null ? 'not computed' : String(value)}
      aria-label={
        label +
        ': ' +
        (value === null ? 'not computed' : formatNumber(value)) +
        ' ' +
        unitLabel(units)
      }
    >
      <span className="hf-mono">
        {value === null
          ? 'not computed'
          : (state === 'estimated' ? '≈ ' : '') + formatNumber(value)}{' '}
        {unitLabel(units)}
      </span>
      <StatusTag tone={value === null ? 'advisory' : state === 'calculated' ? 'ok' : 'inert'}>
        {label}
      </StatusTag>
      {value === null && reason && <span>{reason}</span>}
    </div>
  );
}

export function ResponseCurve({
  label,
  axis,
  units,
  points,
  calculated = [],
  selected,
}: {
  label: string;
  axis: string;
  units: string;
  points: { x: number; y: number | null }[];
  calculated?: { x: number; y: number }[];
  selected: number;
}) {
  const available = [...points, ...calculated].filter(
    (p): p is { x: number; y: number } => p.y !== null,
  );
  if (!available.length) return <p>{axis} · Not computed</p>;
  const xs = [...points, ...calculated].map((p) => p.x),
    ys = available.map((p) => p.y);
  const lo = Math.min(...xs),
    hi = Math.max(...xs),
    bottom = Math.min(...ys),
    top = Math.max(...ys);
  const x = (v: number) => 12 + ((v - lo) / (hi - lo || 1)) * 176;
  const y = (v: number) => (top === bottom ? 38 : 66 - ((v - bottom) / (top - bottom)) * 56);
  const selectedPoint = calculated.some((p) => p.x === selected)
    ? undefined
    : points.find((p) => p.x === selected && p.y !== null);
  return (
    <figure className="hf-response-curve">
      <svg viewBox="0 0 200 80" role="img" aria-label={label + ' response to ' + axis}>
        <title>
          {label}:{' '}
          {available
            .map((p) => `${formatNumber(p.x)}: ${formatNumber(p.y)} ${unitLabel(units)}`)
            .join('; ')}
        </title>
        <path className="hf-response-curve__axis" d="M12 10V66H188" />
        {points
          .slice(1)
          .map(
            (p, i) =>
              p.y !== null &&
              points[i].y !== null && (
                <path
                  key={i}
                  className="hf-response-curve__estimate"
                  d={`M${x(points[i].x)} ${y(points[i].y!)}L${x(p.x)} ${y(p.y)}`}
                />
              ),
          )}
        {calculated.map((p) => (
          <circle
            key={p.x}
            className="hf-response-curve__calculated"
            cx={x(p.x)}
            cy={y(p.y)}
            r="3"
          />
        ))}
        {selectedPoint?.y != null && (
          <circle
            className="hf-response-curve__cursor"
            cx={x(selectedPoint.x)}
            cy={y(selectedPoint.y)}
            r="4"
          />
        )}
        <text x="12" y="78">
          {formatNumber(lo)}
        </text>
        <text x="188" y="78" textAnchor="end">
          {formatNumber(hi)}
        </text>
      </svg>
      <figcaption>
        {axis} · {label} ({unitLabel(units)}) · {formatNumber(bottom)}–{formatNumber(top)}
      </figcaption>
    </figure>
  );
}
