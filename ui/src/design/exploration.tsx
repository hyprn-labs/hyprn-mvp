import { useId, type ReactNode } from 'react';
import { Panel, StatusTag } from './components';
import { SectionHeader, TextInput } from './primitives';
import { formatNumber } from './numbers';
import { unitLabel } from '../unitLabels';

export function AnswerExplorationPanel({
  settings,
  categories,
  children,
  footer,
}: {
  settings: ReactNode;
  categories: ReactNode;
  children: ReactNode;
  footer: ReactNode;
}) {
  return (
    <Panel label="Explore the answer">
      <header className="hf-exploration-header">
        <SectionHeader level={3} title="Explore the answer" actions={settings} />
        <div className="hf-exploration-categories">{categories}</div>
      </header>
      {children}
      <footer className="hf-exploration-footer">{footer}</footer>
    </Panel>
  );
}

export function InterpretationPanel({ children }: { children: ReactNode }) {
  return (
    <Panel label="Interpretation" title="Interpretation" headingLevel={3}>
      <p className="hf-response-note">
        Saved answer. Changing exploration inputs does not revise its observations, interpretation
        or qualifications.
      </p>
      {children}
    </Panel>
  );
}

/** Plain saved text: preserve paragraphs and simple lists without interpreting HTML. */
export function AnswerProse({ text }: { text: string }) {
  const blocks: { list: boolean; lines: string[] }[] = [];
  for (const line of text.split(/\r?\n/)) {
    if (!line.trim()) {
      blocks.push({ list: false, lines: [] });
      continue;
    }
    const bullet = /^\s*[-*]\s+(.+)$/.exec(line);
    const list = !!bullet;
    const last = blocks.at(-1);
    if (!last || last.list !== list || !last.lines.length)
      blocks.push({ list, lines: [bullet?.[1] ?? line] });
    else last.lines.push(bullet?.[1] ?? line);
  }
  return (
    <div className="hf-answer-prose">
      {blocks
        .filter((b) => b.lines.length)
        .map((b, i) =>
          b.list ? (
            <ul key={i}>
              {b.lines.map((line, n) => (
                <li key={n}>{line}</li>
              ))}
            </ul>
          ) : (
            <p key={i}>{b.lines.join('\n')}</p>
          ),
        )}
    </div>
  );
}

/** Select returned query vectors only: drawing a line never evaluates a model. */
export function QuantitySlider({
  label,
  units,
  values,
  stops,
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
  stops?: { value: number; kind: 'calculated' | 'estimated' | 'unavailable' }[];
  lower?: number | null;
  upper?: number | null;
  step?: number | null;
  onFocus?: () => void;
  value: number | null;
  onChange: (value: number | null) => void;
}) {
  values = stops ? stops.map((p) => p.value) : values;
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
      <div className="hf-quantity-entry">
        <label htmlFor={id}>{label}</label>
        <TextInput
          id={id}
          aria-label={label + ' · ' + unitLabel(units)}
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
        <span className="hf-quantity-unit">{unitLabel(units)}</span>
      </div>
      <div
        className={'hf-discrete-track hf-discrete-track--' + (stops?.[index]?.kind ?? 'unassigned')}
      >
        <input
          type="range"
          aria-label={label + (values ? ' prepared points' : ' range')}
          min={values ? 0 : (lower ?? 0)}
          max={values ? Math.max(0, values.length - 1) : (upper ?? 0)}
          step={values ? 1 : (step ?? 'any')}
          value={values ? Math.max(0, index) : (value ?? lower ?? 0)}
          disabled={values ? values.length < 2 : !declared || outside || value === null}
          aria-valuetext={
            value === null ? 'unassigned' : formatNumber(value) + ' ' + unitLabel(units)
          }
          onChange={(event) =>
            onChange(
              values
                ? values[Number(event.currentTarget.value)]
                : event.currentTarget.valueAsNumber,
            )
          }
        />
        {stops && (
          <div className="hf-slider-stops" aria-hidden="true">
            {stops.map((p) => (
              <span key={p.value} className={'hf-slider-stop--' + p.kind} />
            ))}
          </div>
        )}
      </div>
      {stops && stops.length < 2 && <span className="hf-slider-caption">More samples needed</span>}
      {(values ? index < 0 : !declared || outside || value === null) && (
        <span role="status">
          {value === null
            ? 'Unassigned'
            : outside
              ? 'Outside the declared range.'
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
      {value !== null && (
        <span className="hf-mono">
          {(state === 'estimated' ? '≈ ' : '') + formatNumber(value)}{' '}
          <span className="hf-result-unit">{unitLabel(units)}</span>
        </span>
      )}
      {value === null ? (
        <StatusTag tone="advisory">{label}</StatusTag>
      ) : (
        <span className={'hf-result-basis hf-result-basis--' + state}>
          <span aria-hidden="true">{state === 'calculated' ? '●' : '○'}</span> <span>{label}</span>
        </span>
      )}
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
  selectedResult,
}: {
  label: string;
  axis: string;
  units: string;
  points: { x: number; y: number | null }[];
  calculated?: { x: number; y: number }[];
  selected: number;
  selectedResult?: { value: number | null; state: 'estimated' | 'calculated' };
}) {
  const selectedPoint = selectedResult
    ? selectedResult.value === null
      ? undefined
      : { x: selected, y: selectedResult.value }
    : points.find((p) => p.x === selected && p.y !== null);
  const selectedCalculated =
    selectedResult?.state === 'calculated' || calculated.some((p) => p.x === selected);
  const available = [...points, ...calculated, ...(selectedPoint ? [selectedPoint] : [])].filter(
    (p): p is { x: number; y: number } => p.y !== null,
  );
  if (!available.length) return <p>{axis} · Not computed</p>;
  const xs = [...points, ...calculated, ...(selectedPoint ? [selectedPoint] : [])].map((p) => p.x),
    ys = available.map((p) => p.y);
  const lo = Math.min(...xs),
    hi = Math.max(...xs),
    bottom = Math.min(...ys),
    top = Math.max(...ys);
  if (new Set(available.map((p) => p.x)).size < 2)
    return <p className="hf-response-note">No curve for this input combination.</p>;
  const x = (v: number) => 48 + ((v - lo) / (hi - lo || 1)) * 180;
  const y = (v: number) => (top === bottom ? 44 : 76 - ((v - bottom) / (top - bottom)) * 64);
  const tick = (v: number) => formatNumber(Number(v.toPrecision(3)));
  return (
    <figure className="hf-response-curve">
      <svg viewBox="0 0 240 100" role="img" aria-label={label + ' response to ' + axis}>
        <title>
          {label}:{' '}
          {available
            .map((p) => `${formatNumber(p.x)}: ${formatNumber(p.y)} ${unitLabel(units)}`)
            .join('; ')}
        </title>
        <path className="hf-response-curve__axis" d="M48 12V76H228" />
        {bottom < 0 && top > 0 && (
          <path className="hf-response-curve__axis" d={`M48 ${y(0)}H228`} aria-label="Zero" />
        )}
        <text x="44" y={top === bottom ? '48' : '16'} textAnchor="end">
          {tick(top)}
        </text>
        {top !== bottom && (
          <text x="44" y="76" textAnchor="end">
            {tick(bottom)}
          </text>
        )}
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
        {calculated.map((p, i) => (
          <circle
            key={p.x + ':' + i}
            className="hf-response-curve__calculated"
            cx={x(p.x)}
            cy={y(p.y)}
            r="3"
          />
        ))}
        {selectedPoint?.y != null && (
          <circle
            className={
              selectedCalculated ? 'hf-response-curve__calculated' : 'hf-response-curve__cursor'
            }
            cx={x(selectedPoint.x)}
            cy={y(selectedPoint.y)}
            r="4"
          />
        )}
        <text x="48" y="94">
          {formatNumber(lo)}
        </text>
        <text x="228" y="94" textAnchor="end">
          {formatNumber(hi)}
        </text>
      </svg>
      <figcaption>X: {axis}</figcaption>
    </figure>
  );
}
