import './quantity-slider.css';
import './exploration-focus.css';
import { useId, useState, type ReactNode } from 'react';
import { Button, Panel, StatusTag } from './components';
import { SectionHeader, TextInput, Disclosure, Select } from './primitives';
import { formatNumber } from './numbers';
import { displayUnit as unitLabel } from '../unitLabels';

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
    <Panel label="Explore the answer" className="hf-answer-exploration">
      <header className="hf-exploration-header">
        <SectionHeader level={3} title="Explore the answer" help="exploration" actions={settings} />
        <div className="hf-exploration-categories">{categories}</div>
      </header>
      {children}
      <footer className="hf-exploration-footer">{footer}</footer>
    </Panel>
  );
}

/** Selection only: the owner supplies supported values and resolves their saved basis. */
export function QualitativeChoice({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: { value: string; disabled?: boolean }[];
  onChange: (value: string) => void;
}) {
  const id = useId();
  if (options.length > 4)
    return (
      <label className="hf-qualitative-choice" htmlFor={id}>
        {label}
        <Select id={id} value={value} onChange={(event) => onChange(event.target.value)}>
          {options.map((option) => (
            <option key={option.value} value={option.value} disabled={option.disabled}>
              {option.value}
              {option.disabled ? ' — unavailable for current choices' : ''}
            </option>
          ))}
        </Select>
      </label>
    );
  return (
    <div className="hf-qualitative-choice" role="group" aria-labelledby={id}>
      <span id={id}>{label}</span>
      <div className="hf-choice-buttons">
        {options.map((option) => (
          <Button
            key={option.value}
            size="sm"
            aria-pressed={value === option.value}
            disabled={option.disabled}
            title={option.disabled ? 'Unavailable for current choices' : undefined}
            onClick={() => {
              if (value !== option.value) onChange(option.value);
            }}
          >
            {option.value}
          </Button>
        ))}
      </div>
    </div>
  );
}

export function InterpretationPanel({
  children,
  collapsed = false,
}: {
  children: ReactNode;
  collapsed?: boolean;
}) {
  return (
    <Panel label="Interpretation" className={collapsed ? 'hf-interpretation' : undefined}>
      {collapsed ? (
        <Disclosure>
          <summary>Interpretation & qualifications</summary>
          <div className="hf-answer-reading">{children}</div>
        </Disclosure>
      ) : (
        <>
          <h3>Interpretation</h3>
          <div className="hf-answer-reading">{children}</div>
        </>
      )}
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

/** Select prepared coordinates; result status belongs to the full input vector. */
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
  const [editing, setEditing] = useState(false);
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
      className="hf-quantity-slider hf-quantity-slider--compact"
      onFocus={onFocus}
      onPointerDown={(e) => e.stopPropagation()}
    >
      <div className="hf-quantity-entry">
        <label htmlFor={id}>{label}</label>
        <div className="hf-quantity-value-box">
          <TextInput
            id={id}
            aria-label={label + ' · ' + unitLabel(units)}
            type="number"
            step={step ?? 'any'}
            value={value === null ? '' : editing ? value : formatNumber(value)}
            title={value === null ? undefined : String(value)}
            onFocus={() => setEditing(true)}
            onBlur={() => setEditing(false)}
            onChange={(event) => {
              const next = event.currentTarget.valueAsNumber;
              onChange(
                Number.isFinite(next) && Math.abs(next) <= Number.MAX_SAFE_INTEGER ? next : null,
              );
            }}
          />
          <span className="hf-quantity-unit">{unitLabel(units)}</span>
        </div>
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
      {(values?.length || declared) && (
        <div className="hf-quantity-range-labels" aria-hidden="true">
          <span>{formatNumber(values?.[0] ?? lower ?? 0)}</span>
          <span>{formatNumber(values?.at(-1) ?? upper ?? 0)}</span>
        </div>
      )}
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
  pending = false,
}: {
  pending?: boolean;
  value: number | null;
  units: string;
  state: 'estimated' | 'calculated' | 'unavailable';
  reason?: string | null;
}) {
  if (pending)
    return (
      <div className="hf-quantity-result" aria-busy="true" aria-label="Updating predictions">
        <StatusTag tone="running">Updating…</StatusTag>
      </div>
    );
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
          <span aria-hidden="true">{state === 'calculated' ? '●' : '○'}</span>
          <span className="sr-only">{label}</span>
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
  pending = false,
  referenceLines = [],
}: {
  pending?: boolean;
  label: string;
  axis: string;
  units: string;
  points: { x: number; y: number | null }[];
  calculated?: { x: number; y: number }[];
  selected: number;
  selectedResult?: { value: number | null; state: 'estimated' | 'calculated' };
  /** Declared criteria already expressed in the output's display units. */
  referenceLines?: { value: number; label: string }[];
}) {
  calculated = calculated.filter(
    (p, i, all) => all.findIndex((q) => q.x === p.x && q.y === p.y) === i,
  );
  const selectedPoint = selectedResult
    ? selectedResult.value === null
      ? undefined
      : { x: selected, y: selectedResult.value }
    : points.find((p) => p.x === selected && p.y !== null);
  const selectedCalculated = selectedResult
    ? selectedResult.state === 'calculated'
    : calculated.some((p) => p.x === selected && p.y === selectedPoint?.y);
  const available = [...points, ...calculated, ...(selectedPoint ? [selectedPoint] : [])].filter(
    (p): p is { x: number; y: number } => p.y !== null,
  );
  if (!available.length)
    return (
      <p>
        {axis} · {pending ? 'Updating…' : 'Not computed'}
      </p>
    );
  const references = referenceLines.filter((line) => Number.isFinite(line.value));
  const xs = [...points, ...calculated, ...(selectedPoint ? [selectedPoint] : [])].map((p) => p.x),
    ys = [...available.map((p) => p.y), ...references.map((line) => line.value)];
  const lo = Math.min(...xs),
    hi = Math.max(...xs),
    minimum = Math.min(...ys),
    maximum = Math.max(...ys);
  // A small relative display span prevents near-constant responses from filling the
  // plot with numerical noise. Values and uncertainty are not modified.
  const span = Math.max(
    maximum - minimum,
    Math.max(Math.abs(minimum), Math.abs(maximum)) * 1e-4,
    maximum === 0 && minimum === 0 ? 1 : Number.MIN_VALUE,
  );
  const middle = minimum / 2 + maximum / 2;
  const bottom = middle - span * 0.6,
    top = middle + span * 0.6;
  if (new Set(available.map((p) => p.x)).size < 2)
    return (
      <p className="hf-response-note">
        {pending ? 'Updating curve…' : 'No curve for this input combination.'}
      </p>
    );
  const x = (v: number) => 48 + ((v - lo) / (hi - lo || 1)) * 300;
  const y = (v: number) => (top === bottom ? 44 : 76 - ((v - bottom) / (top - bottom)) * 64);
  const tick = (v: number) => {
    const digits = Math.min(12, Math.max(0, 1 - Math.floor(Math.log10(span))));
    return Math.abs(v) >= 1e6 || (v !== 0 && Math.abs(v) < 0.001)
      ? v.toExponential(3)
      : Number(v.toFixed(digits)).toString();
  };
  return (
    <figure className="hf-response-curve">
      <svg viewBox="0 0 360 100" role="img" aria-label={label + ' response to ' + axis}>
        <title>
          {label}:{' '}
          {available
            .map((p) => `${formatNumber(p.x)}: ${formatNumber(p.y)} ${unitLabel(units)}`)
            .join('; ')}
        </title>
        <path className="hf-response-curve__axis" d="M48 76H348" />
        {bottom < 0 && top > 0 && (
          <path className="hf-response-curve__axis" d={`M48 ${y(0)}H348`} aria-label="Zero" />
        )}
        <text x="44" y={top === bottom ? '48' : '16'} textAnchor="end">
          {tick(top)}
        </text>
        {top !== bottom && (
          <text x="44" y="76" textAnchor="end">
            {tick(bottom)}
          </text>
        )}
        {references.map((line, i) => (
          <g key={i} aria-label={`${line.label}: ${formatNumber(line.value)} ${unitLabel(units)}`}>
            <path className="hf-response-curve__reference" d={`M48 ${y(line.value)}H348`} />
            <text
              className="hf-response-curve__reference-label"
              x="348"
              y={y(line.value) - 4}
              textAnchor="end"
            >
              {line.label} {formatNumber(line.value)}
            </text>
          </g>
        ))}
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
        {points.map(
          (p, i) =>
            p.y !== null &&
            !calculated.some((c) => c.x === p.x && c.y === p.y) && (
              <circle
                key={'estimate-' + i}
                className="hf-response-curve__sample"
                cx={x(p.x)}
                cy={y(p.y)}
                r="2"
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
            className="hf-response-curve__selection"
            cx={x(selectedPoint.x)}
            cy={y(selectedPoint.y)}
            r="6"
            aria-hidden="true"
          />
        )}
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
        <text x="348" y="94" textAnchor="end">
          {formatNumber(hi)}
        </text>
      </svg>
      <figcaption>{axis}</figcaption>
    </figure>
  );
}

/** Compact study controls and outcomes; the caller owns all scientific state. */
export function ExplorationFocus({
  inputs,
  outputs,
  onExpand,
  inputControls,
  outputControls,
}: {
  inputControls?: ReactNode;
  outputControls?: ReactNode;
  inputs: ReactNode[];
  outputs: ReactNode[];
  onExpand?: () => void;
}) {
  return (
    <div className="hf-exploration-focus">
      {inputControls && <div className="hf-exploration-input-controls">{inputControls}</div>}
      {outputControls && <div className="hf-exploration-output-controls">{outputControls}</div>}
      <section aria-label="Independent inputs" className="hf-exploration-focus-inputs">
        <h4>Inputs</h4>
        <div className="hf-exploration-input-list">
          {inputs.length ? inputs : <p>No independent inputs.</p>}
        </div>
      </section>
      <div className="hf-exploration-model-connection">
        {onExpand && (
          <Button onClick={onExpand} aria-expanded={false} aria-label="Expand model">
            Expand model
          </Button>
        )}
      </div>
      <section aria-label="Study outcomes" className="hf-exploration-focus-outcomes">
        <header className="hf-focus-outcome-heading">
          <h4>Outcomes</h4>
        </header>
        <div className="hf-exploration-outcome-grid">{outputs}</div>
      </section>
    </div>
  );
}

export function ExplorationQuantity({
  title,
  context,
  children,
}: {
  title?: string;
  context: string;
  children: ReactNode;
}) {
  return (
    <article className="hf-exploration-quantity" aria-label={title} title={context}>
      {title && <h5>{title}</h5>}
      {children}
    </article>
  );
}

export function ExplorationLegend({ unavailable = false }: { unavailable?: boolean }) {
  return (
    <div className="hf-result-legend" aria-label="Result types">
      <span className="hf-result-basis hf-result-basis--calculated">
        <span aria-hidden="true">●</span> calculated
      </span>
      {' · '}
      <span className="hf-result-basis hf-result-basis--estimated">
        <span aria-hidden="true">○</span> estimated
      </span>
      {unavailable && (
        <>
          {' · '}
          <span className="hf-result-basis hf-result-basis--unavailable">
            <span aria-hidden="true">□</span> no result
          </span>
        </>
      )}
    </div>
  );
}
