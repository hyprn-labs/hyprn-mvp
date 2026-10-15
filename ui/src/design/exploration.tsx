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
  value,
  onChange,
}: {
  label: string;
  units: string;
  values: number[];
  value: number | null;
  onChange: (value: number | null) => void;
}) {
  const id = useId(),
    index = value === null ? -1 : values.indexOf(value);
  return (
    <div className="hf-quantity-slider">
      <label htmlFor={id}>
        {label} · {unitLabel(units)}
      </label>
      <TextInput
        id={id}
        type="number"
        step="any"
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
        aria-label={label + ' prepared points'}
        min={0}
        max={Math.max(0, values.length - 1)}
        step={1}
        value={Math.max(0, index)}
        disabled={!values.length}
        aria-valuetext={
          value === null ? 'unassigned' : formatNumber(value) + ' ' + unitLabel(units)
        }
        onChange={(event) => onChange(values[Number(event.currentTarget.value)])}
      />
      {index < 0 && (
        <span role="status">
          {value === null ? 'Unassigned' : 'No prepared estimate at this value.'}
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
  if (!available.length) return <p>No computed response.</p>;
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
