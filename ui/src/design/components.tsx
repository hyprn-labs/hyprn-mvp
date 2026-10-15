import { formatNumber } from './numbers';
/*
 * HYPRN MVP Foundry components: the typed React 19 implementation of the design system
 * (design-system/README.md and design-system/components/*.md). Class names, ARIA roles, the
 * tone-to-mark mapping, the field tag mapping, missing-value words and the Tabs/Ledger/DataTable
 * structure follow the component notes.
 *
 * Implementation rules this layer keeps:
 * - Icon props are ReactNode (for example an inline SVG), never icon-font ligature strings.
 *   Icon-only buttons must carry aria-label.
 * - Built-in glyphs (RecordBar lock and return arrow, SourceChip document, InferenceBlock and
 *   AttributionChip iris mark, Readout basis glyphs) are tiny inline SVGs authored independently for HYPRN MVP: currentColor,
 *   aria-hidden, focusable false, sized by the .hf-glyph class. No icon-library path data.
 * - No inline style attributes anywhere; layout details are the classes .hf-field__meaning,
 *   .hf-field__tag, .hf-th--num and .hf-visually-hidden in foundry.css.
 * - Field never tags a blank value as "assigned" or "saved": a null or '' value shows the advisory
 *   "unassigned" tag (unless the state is invalid), and a blank read-only value is worded
 *   "unassigned" in ink-muted. 0 stays an explicit assigned value.
 * - Tabs implement roving-focus keyboard support (Left/Right/Home/End), so unselected tabs stay
 *   reachable although they leave the tab order.
 *
 * This layer imports no CSS: main.tsx imports tokens.css and then foundry.css once.
 */
import type { ButtonHTMLAttributes, Ref, ChangeEvent, KeyboardEvent, ReactElement, ReactNode } from 'react';

export type Tone = 'alarm' | 'warning' | 'advisory' | 'ok' | 'inert' | 'running';

function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(' ');
}

function isBlank(value: unknown): boolean {
  return value === null || value === undefined || value === '';
}

/* ---- Independently authored glyphs (24-unit viewBox, currentColor) ---- */

type GlyphName = 'lock' | 'back' | 'document' | 'iris' | 'computed' | 'measured' | 'sourced' | 'inferred';

function Glyph({ name }: { name: GlyphName }): ReactElement {
  let body: ReactElement;
  switch (name) {
    case 'lock':
      body = (
        <>
          <rect x="5" y="10" width="14" height="10" rx="1" fill="currentColor" />
          <path d="M8 10V7a4 4 0 0 1 8 0v3" fill="none" stroke="currentColor" strokeWidth="2" />
        </>
      );
      break;
    case 'back':
      body = <path d="M20 12H6M11 6l-6 6 6 6" fill="none" stroke="currentColor" strokeWidth="2" />;
      break;
    case 'document':
    case 'sourced':
      body = (
        <>
          <path d="M6 3h8l4 4v14H6z" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="miter" />
          <path d="M9 12h6M9 16h6" fill="none" stroke="currentColor" strokeWidth="2" />
        </>
      );
      break;
    case 'iris':
      body = (
        <>
          <circle cx="12" cy="12" r="7" fill="none" stroke="currentColor" strokeWidth="2" />
          <circle cx="12" cy="12" r="3" fill="currentColor" />
        </>
      );
      break;
    case 'computed':
      body = <path d="M4 18l5-6 4 3 7-9" fill="none" stroke="currentColor" strokeWidth="2" />;
      break;
    case 'measured':
      body = (
        <>
          <path d="M4 17a8 8 0 0 1 16 0" fill="none" stroke="currentColor" strokeWidth="2" />
          <path d="M12 17l4-6" fill="none" stroke="currentColor" strokeWidth="2" />
        </>
      );
      break;
    case 'inferred':
      body = <circle cx="12" cy="12" r="7" fill="none" stroke="currentColor" strokeWidth="2" strokeDasharray="3 2.5" />;
      break;
  }
  return (
    <svg className="hf-glyph" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      {body}
    </svg>
  );
}

function Icon({ children }: { children: ReactNode }): ReactElement {
  return (
    <span className="hf-icon" aria-hidden="true">
      {children}
    </span>
  );
}

function Mark({ tone }: { tone: Tone }): ReactElement {
  return <span className={'hf-mark hf-mark--' + tone} aria-hidden="true" />;
}

/* ---- Button ---- */

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  ref?: Ref<HTMLButtonElement>;
  /** primary: once per view · secondary: default · quiet: inline/tertiary · ai: apply an assistant proposal · danger: inside a confirmation only */
  variant?: 'primary' | 'secondary' | 'quiet' | 'link' | 'ai' | 'danger';
  /** Text alignment and stacked content are explicit compositions, not screen overrides. */
  align?: 'center' | 'start';
  stacked?: boolean;
  iconOnly?: boolean;
  /** desk 36px (default) · sm 28px · floor 48px for touch displays */
  size?: 'desk' | 'sm' | 'floor';
  /** Icon element (for example an inline SVG); decorative, so icon-only buttons need aria-label */
  icon?: ReactNode;
}

/** The one button. primary at most once per view; ai only to apply an assistant proposal; danger only inside a confirmation. */
export function Button({
  variant = 'secondary',
  size = 'desk',
  align = 'center',
  stacked = false,
  iconOnly = false,
  icon,
  className,
  children,
  type,
  ...rest
}: ButtonProps): ReactElement {
  return (
    <button
      type={type ?? 'button'}
      {...rest}
      className={cx(
        'hf-btn',
        'hf-btn--' + variant,
        'hf-btn--' + size,
        align === 'start' && 'hf-btn--start',
        stacked && 'hf-btn--stacked',
        (iconOnly || (!!icon && !children)) && 'hf-btn--icon',
        className,
      )}
    >
      {icon ? <Icon>{icon}</Icon> : null}
      {children}
    </button>
  );
}

/* ---- Field ---- */

export type FieldState = 'assigned' | 'unassigned' | 'invalid' | 'readonly';

const FIELD_TAG: Record<FieldState, [Tone, string]> = {
  assigned: ['ok', 'assigned'],
  unassigned: ['advisory', 'unassigned'],
  invalid: ['alarm', 'invalid'],
  readonly: ['inert', 'saved'],
};

export interface FieldProps {
  /** Table column headings supply the visible label; accessible name and missing-value meaning remain. */
  compact?: boolean;
  /** Variable name, set in mono, e.g. "Linear response.x" */
  label: string;
  /** Short plain-language meaning shown after the name */
  meaning?: string;
  /** '' or null means unassigned; 0 is an explicit value */
  value?: string | number | null;
  unit?: string;
  /** Compatible units offered in a select; one entry renders a fixed unit */
  units?: string[];
  state?: FieldState;
  /** Validation or conversion message under the row */
  message?: ReactNode;
  /** Where the value came from, e.g. "Entered manually · cfg-01" */
  provenance?: ReactNode;
  id?: string;
  onChange?: (e: ChangeEvent<HTMLInputElement>) => void;
  onUnitChange?: (e: ChangeEvent<HTMLSelectElement>) => void;
  className?: string;
  inputProps?: {
    type?: 'number' | 'text';
    step?: string;
    'aria-label'?: string;
    'data-input-key'?: string;
  };
}

function noop(): void {}

/** An explicit scalar input: value, unit, state and provenance. Blank is unassigned; 0 is a value. */
export function Field(p: FieldProps): ReactElement {
  const blank = isBlank(p.value);
  const declared: FieldState = p.state ?? 'assigned';
  const state: FieldState = blank && declared === 'assigned' ? 'unassigned' : declared;
  const id =
    p.id ??
    'hf-' +
      String(p.label || 'field')
        .replace(/\W+/g, '-')
        .toLowerCase();
  const tag = blank && state !== 'invalid' ? FIELD_TAG.unassigned : FIELD_TAG[state];
  const units = p.units ?? [p.unit ?? '1'];
  const msgId = p.message ? id + '-msg' : undefined;
  const input =
    state === 'readonly' ? (
      <span className={cx('hf-field__ro', blank && 'hf-field__ro--missing')} id={id}>
        {blank ? 'unassigned' : String(p.value)}
      </span>
    ) : (
      <input
        {...p.inputProps}
        id={id}
        value={p.value ?? ''}
        placeholder="unassigned"
        inputMode="decimal"
        onChange={p.onChange ?? noop}
        aria-invalid={state === 'invalid' ? 'true' : undefined}
        aria-describedby={msgId}
      />
    );
  const unit =
    state === 'readonly' || units.length < 2 ? (
      <span className="hf-field__unit">{p.unit ?? units[0]}</span>
    ) : (
      <select
        value={p.unit ?? units[0]}
        onChange={p.onUnitChange ?? noop}
        aria-label={'Unit of ' + (p.label || 'value')}
      >
        {units.map((u) => (
          <option key={u} value={u}>
            {u}
          </option>
        ))}
      </select>
    );
  return (
    <div
      className={cx(
        'hf-field',
        'hf-field--' + state,
        p.compact && 'hf-field--compact',
        p.className,
      )}
    >
      <label className={cx('hf-field__label', p.compact && 'hf-visually-hidden')} htmlFor={id}>
        <span className="hf-mono">{p.label}</span>
        {p.meaning ? <span className="hf-muted hf-field__meaning">{p.meaning}</span> : null}
        {!p.compact && (
          <span className="hf-field__tag">
            <StatusTag tone={tag[0]}>{tag[1]}</StatusTag>
          </span>
        )}
      </label>
      <div className="hf-field__row">
        {input}
        {unit}
      </div>
      {p.message ? (
        <div className="hf-field__msg" id={msgId} role={state === 'invalid' ? 'alert' : undefined}>
          {p.message}
        </div>
      ) : null}
      {p.provenance ? <div className="hf-field__prov">{p.provenance}</div> : null}
    </div>
  );
}

/* ---- Tabs ---- */

export interface TabItem {
  id: string;
  label: ReactNode;
  count?: number;
  tabId?: string;
  panelId?: string;
}

export interface TabsProps {
  items: TabItem[];
  value: string;
  onChange?: (id: string) => void;
  /** underline (default) for page sections · segmented for view switches */
  variant?: 'underline' | 'segmented';
  navigation?: boolean;
  label?: string;
  className?: string;
}

/** Underlined section tabs, or a segmented view switch. */
export function Tabs(p: TabsProps): ReactElement {
  const items = p.items ?? [];
  const onKeyDown = (e: KeyboardEvent<HTMLButtonElement>, index: number): void => {
    let next = -1;
    if (e.key === 'ArrowRight') next = (index + 1) % items.length;
    else if (e.key === 'ArrowLeft') next = (index - 1 + items.length) % items.length;
    else if (e.key === 'Home') next = 0;
    else if (e.key === 'End') next = items.length - 1;
    if (next < 0) return;
    e.preventDefault();
    p.onChange?.(items[next].id);
    const siblings = e.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>('[role="tab"]');
    siblings?.[next]?.focus();
  };
  return (
    <div role={p.navigation ? "navigation" : "tablist"} aria-label={p.label} className={cx('hf-tabs', p.variant === 'segmented' && 'hf-tabs--segmented', p.className)}>
      {items.map((it, index) => {
        const sel = it.id === p.value;
        return (
          <button
            key={it.id}
            type="button"
            id={it.tabId}
            role={p.navigation ? undefined : "tab"}
            aria-controls={p.navigation ? undefined : it.panelId}
            aria-current={p.navigation && sel ? "page" : undefined}
            className="hf-tab"
            aria-selected={p.navigation ? undefined : sel ? 'true' : 'false'}
            tabIndex={p.navigation || sel ? 0 : -1}
            onClick={() => p.onChange?.(it.id)}
            onKeyDown={p.navigation ? undefined : (e) => onKeyDown(e, index)}
          >
            {it.label}
            {it.count != null ? <span className="hf-tab__count">{it.count}</span> : null}
          </button>
        );
      })}
    </div>
  );
}

/* ---- Panel ---- */

export interface PanelProps {
  ref?: Ref<HTMLElement>;
  id?: string;
  hidden?: boolean;
  title?: ReactNode;
  actions?: ReactNode;
  tone?: 'default' | 'sunken';
  bodyClassName?: string;
  headingLevel?: 2 | 3 | 4;
  label?: string;
  children?: ReactNode;
  className?: string;
}

/** A surface with an optional header row of title and actions. */
export function Panel(p: PanelProps): ReactElement {
  const Heading = ('h' + (p.headingLevel ?? 2)) as 'h2' | 'h3' | 'h4';
  return (
    <section ref={p.ref} id={p.id} hidden={p.hidden} className={cx('hf-panel', p.tone === 'sunken' && 'hf-panel--sunken', p.className)} aria-label={p.label}>
      {p.title ? (
        <header className="hf-panel__head">
          <Heading className="hf-panel__title">{p.title}</Heading>
          {p.actions ? <div className="hf-panel__actions">{p.actions}</div> : null}
        </header>
      ) : null}
      <div className={cx("hf-panel__body", p.bodyClassName)}>{p.children}</div>
    </section>
  );
}

/* ---- StatusTag ---- */

export interface StatusTagProps {
  tone?: Tone;
  children: ReactNode;
  className?: string;
}

/** Status as shape + word + colour. Tones follow alarm priority. */
export function StatusTag({ tone = 'inert', children, className }: StatusTagProps): ReactElement {
  return (
    <span className={cx('hf-tag', 'hf-tag--' + tone, className)}>
      <Mark tone={tone} />
      {children}
    </span>
  );
}

/* ---- AttributionChip ---- */

export interface AttributionChipProps {
  /** The agent's display name, as its own API field ("Codex (local)") */
  agent: string;
  /** The display name of the person the agent acted for, as its own API field */
  user: string;
  className?: string;
}

/**
 * Who acted through an assistant: "{agent} for {user}" and nobody else (agent writes are direct,
 * there is no confirmer). Names are plain text and never truncated; the chip wraps. The visually
 * hidden "Assistant: " prefix gives screen readers the assistant origin that the aria-hidden iris
 * mark shows. Not focusable, not interactive.
 */
export function AttributionChip({ agent, user, className }: AttributionChipProps): ReactElement {
  return (
    <span className={cx('hf-attr', className)}>
      <span className="hf-attr__mark" aria-hidden="true">
        <Glyph name="iris" />
      </span>
      <span className="hf-attr__text">
        <span className="hf-visually-hidden">Assistant: </span>
        {agent}
        <span className="hf-attr__for"> for </span>
        {user}
      </span>
    </span>
  );
}

/* ---- Readout ---- */

export type Basis = 'computed' | 'measured' | 'sourced' | 'inferred';

const BASIS: Record<Basis, [GlyphName, string]> = {
  computed: ['computed', 'Computed'],
  measured: ['measured', 'Measured'],
  sourced: ['sourced', 'Sourced'],
  inferred: ['inferred', 'Inference'],
};

export interface ReadoutProps {
  label?: string;
  /** null or '' renders "not computed" — never 0 */
  value?: string | number | null;
  unit?: string;
  basis?: Basis;
  /** e.g. "run-02" or "N-1 §2" */
  source?: string;
  size?: 'lg' | 'sm';
  missingText?: string;
  className?: string;
}

/** A value with its unit and the basis it rests on. A missing value says so in words. */
export function Readout(p: ReadoutProps): ReactElement {
  const missing = isBlank(p.value);
  const basis = p.basis ?? 'computed';
  const b = BASIS[basis];
  return (
    <div className={cx('hf-readout', p.size === 'sm' && 'hf-readout--sm', p.className)}>
      {p.label ? <span className="hf-readout__label">{p.label}</span> : null}
      {missing ? (
        <span className="hf-readout__missing">{p.missingText || 'not computed'}</span>
      ) : (
        <span
          className="hf-readout__value"
          title={typeof p.value === 'number' ? `Full precision: ${p.value}` : undefined}
        >
          {typeof p.value === 'number' ? formatNumber(p.value) : String(p.value)}
          {p.unit ? <span className="hf-readout__unit">{p.unit}</span> : null}
        </span>
      )}
      {p.source ? (
        <span
          className={cx('hf-readout__basis', basis === 'inferred' && 'hf-readout__basis--inferred')}
        >
          <Icon>
            <Glyph name={b[0]} />
          </Icon>
          {b[1] + ' · ' + p.source}
        </span>
      ) : null}
    </div>
  );
}

/* ---- Ledger ---- */

export interface LedgerFacet {
  label: string;
  value: ReactNode;
  tone?: Tone;
  detail?: ReactNode;
}

export interface LedgerProps {
  facets: LedgerFacet[];
  label?: string;
  className?: string;
}

/** The scientific status ledger: one facet per question, never collapsed into one badge. */
export function Ledger(p: LedgerProps): ReactElement {
  return (
    <div className={cx('hf-ledger', p.className)} role="list" aria-label={p.label || 'Status'}>
      {(p.facets ?? []).map((f) => (
        <div key={f.label} className="hf-facet" role="listitem">
          <span className="hf-facet__k">{f.label}</span>
          <span className="hf-facet__v">
            <StatusTag tone={f.tone ?? 'inert'}>{f.value}</StatusTag>
          </span>
          {f.detail ? <span className="hf-facet__d">{f.detail}</span> : null}
        </div>
      ))}
    </div>
  );
}

/* ---- SourceChip ---- */

export interface SourceChipProps {
  label: ReactNode;
  /** Exact location: "p. 2 §2", "Table 1", "line 3" */
  locator?: string;
  authority?: 'primary' | 'secondary' | 'unverified';
  icon?: ReactNode;
  href?: string;
  onClick?: () => void;
  className?: string;
}

/** A provenance link to an exact location in a source. */
export function SourceChip(p: SourceChipProps): ReactElement {
  const auth = p.authority ?? 'primary';
  const content = (
    <>
      <Icon>{p.icon ?? <Glyph name="document" />}</Icon>
      <span>{p.label}</span>
      {p.locator ? <span className="hf-chip__loc">{p.locator}</span> : null}
      <span className={'hf-chip__auth hf-chip__auth--' + auth} aria-label={auth + ' source'} />
    </>
  );
  if (p.href) {
    return (
      <a className={cx('hf-chip', p.className)} href={p.href} onClick={p.onClick} title={auth + ' source'}>
        {content}
      </a>
    );
  }
  return (
    <button type="button" className={cx('hf-chip', p.className)} onClick={p.onClick} title={auth + ' source'}>
      {content}
    </button>
  );
}

/* ---- InferenceBlock ---- */

export type InferenceStatus = 'proposed' | 'applied' | 'discarded' | 'checking';

const PSTATE: Record<InferenceStatus, [Tone, string]> = {
  proposed: ['advisory', 'not applied'],
  applied: ['ok', 'applied'],
  discarded: ['inert', 'discarded'],
  checking: ['running', 'checking outcome'],
};

export interface InferenceBlockProps {
  title: ReactNode;
  kind?: 'Proposal' | 'Inference' | 'Explanation';
  status?: InferenceStatus;
  /** SourceChips and computed Readouts the content rests on */
  basis?: ReactNode[];
  actions?: ReactNode;
  children?: ReactNode;
  className?: string;
}

/** Assistant-originated content: a proposal or an inference, always reviewable. */
export function InferenceBlock(p: InferenceBlockProps): ReactElement {
  const kind = p.kind ?? 'Proposal';
  const st = PSTATE[p.status ?? 'proposed'];
  const titleText = typeof p.title === 'string' || typeof p.title === 'number' ? String(p.title) : '';
  return (
    <section className={cx('hf-infer', p.className)} aria-label={titleText ? kind + ': ' + titleText : kind}>
      <header className="hf-infer__head">
        <span className="hf-infer__mark" aria-hidden="true">
          <Icon>
            <Glyph name="iris" />
          </Icon>
        </span>
        <span className="hf-infer__kind">{kind}</span>
        <span className="hf-infer__title">{p.title}</span>
        <StatusTag tone={st[0]}>{st[1]}</StatusTag>
      </header>
      <div className="hf-infer__body">
        {p.children}
        {p.basis && p.basis.length ? (
          <div className="hf-infer__basis">
            Rests on
            {p.basis.map((item, i) => (
              <span key={i}>{item}</span>
            ))}
          </div>
        ) : null}
        {p.actions ? <div className="hf-infer__actions">{p.actions}</div> : null}
      </div>
    </section>
  );
}

/* ---- RecordBar ---- */

export interface RecordBarProps {
  title: ReactNode;
  detail?: ReactNode;
  returnLabel?: string;
  onReturn?: () => void;
  className?: string;
}

/** The inverse band shown while a frozen run or revision is open. */
export function RecordBar(p: RecordBarProps): ReactElement {
  return (
    <div className={cx('hf-record', p.className)} role="status">
      <Icon>
        <Glyph name="lock" />
      </Icon>
      <span className="hf-record__text">
        <b>{p.title}</b>
        {p.detail ? <> · {p.detail}</> : null}
      </span>
      {p.onReturn || p.returnLabel ? (
        <Button size="sm" onClick={p.onReturn} icon={<Glyph name="back" />}>
          {p.returnLabel || 'Return to current model'}
        </Button>
      ) : null}
    </div>
  );
}

/* ---- ModelNode ---- */

export type PortState = 'connected' | 'free' | 'output' | 'unassigned';

const PORT: Record<PortState, string> = {
  connected: 'Connected',
  free: 'Input',
  output: 'Output',
  unassigned: 'Needs value',
};

export interface ModelNodePort {
  content?: ReactNode;
  name: string;
  dir: 'in' | 'out';
  state?: PortState;
  id?: string;
  title?: string;
  selected?: boolean;
  onSelect?: () => void;
}

export interface ModelNodeProps {
  name: string;
  instanceId?: string;
  title?: string;
  nameSelected?: boolean;
  index?: number;
  ports?: ModelNodePort[];
  /** e.g. "Affine · v1" */
  definition?: string;
  selected?: boolean;
  status?: 'incomplete' | 'proposed';
  onSelect?: () => void;
  className?: string;
}

/** A component in the graph view: name, ports and definition version. */
export function ModelNode(p: ModelNodeProps): ReactElement {
  return (
    <div
      className={cx('hf-node', p.status && 'hf-node--' + p.status, p.className)}
      data-selected={p.selected || undefined}
    >
      <Button
        size="floor"
        align="start"
        className="hf-node__head"
        data-instance={p.instanceId}
        title={p.title}
        aria-pressed={p.nameSelected ?? p.selected ?? false}
        onClick={p.onSelect}
      >
        {p.index != null ? <span className="hf-node__idx">{p.index}</span> : null}
        <span className="hf-node__name">{p.name}</span>
      </Button>
      {(p.ports ?? []).map((pt) => {
        const st: PortState = pt.state ?? (pt.dir === 'out' ? 'output' : 'free');
        const control = (
          <Button
            size="floor"
            align="start"
            key={pt.id ?? pt.dir + pt.name}
            className="hf-node__port"
            data-port={pt.id}
            title={pt.title}
            aria-pressed={pt.selected ?? false}
            onClick={pt.onSelect}
          >
            <code>{pt.dir === 'out' ? pt.name + ' →' : '→ ' + pt.name}</code>
            <span
              className={cx('hf-node__state', st === 'unassigned' && 'hf-node__state--unassigned')}
            >
              {st === 'unassigned' ? <Mark tone="advisory" /> : null}
              {PORT[st]}
            </span>
          </Button>
        );
        return pt.content ? (
          <div key={pt.id ?? pt.dir + pt.name} className="hf-node__exploration-port">
            {control}{pt.content}
          </div>
        ) : control;
      })}
      {(p.definition || p.status) && (
        <div className="hf-node__foot">
          {p.definition}
          {p.status === 'incomplete' ? (
            <StatusTag tone="advisory">implementation missing</StatusTag>
          ) : null}
          {p.status === 'proposed' ? <StatusTag tone="inert">proposed</StatusTag> : null}
        </div>
      )}
    </div>
  );
}

/* ---- DataTable ---- */

export interface DataTableColumn {
  key: string;
  label: ReactNode;
  numeric?: boolean;
  unit?: boolean;
  missingText?: string;
}

export interface DataTableProps {
  regionLabel?: string;
  columns?: DataTableColumn[];
  rows?: Record<string, ReactNode>[];
  children?: ReactNode;
  label?: string;
  dense?: boolean;
  selected?: number;
  caption?: string;
  className?: string;
}

/** A data table: numbers right-aligned in mono, units in their own column, missing values as words. */
export function DataTable(p: DataTableProps): ReactElement {
  const cols = p.columns ?? [];
  return (
    <div className="hf-table-wrap" role={p.regionLabel ? "region" : undefined} aria-label={p.regionLabel} tabIndex={p.regionLabel ? 0 : undefined}>
      <table aria-label={p.label} className={cx('hf-table', p.dense && 'hf-table--dense', p.className)}>
        {p.caption ? <caption className="hf-visually-hidden">{p.caption}</caption> : null}
        {p.children ?? <><thead>
          <tr>
            {cols.map((c) => (
              <th key={c.key} scope="col" className={c.numeric ? 'hf-th--num' : undefined}>
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {(p.rows ?? []).map((r, i) => (
            <tr key={i} aria-selected={p.selected === i ? 'true' : undefined}>
              {cols.map((c) => {
                const v = r[c.key];
                if (c.numeric && isBlank(v)) {
                  return (
                    <td key={c.key} className="missing">
                      {c.missingText || 'not computed'}
                    </td>
                  );
                }
                return (
                  <td key={c.key} className={c.numeric ? 'num' : c.unit ? 'unit' : undefined}>
                    {v}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody></>}
      </table>
    </div>
  );
}


/** Storage and editability are separate from scientific outcome. */
export function RecordState({ state }: {
  state: 'draft' | 'changed' | 'saved' | 'new'
}): ReactElement {
  const label = {
    draft: 'Saved draft',
    changed: 'Unsaved changes',
    saved: 'Saved version · read-only',
    new: 'New draft',
  }[state];
  return <StatusTag className="hf-record-state" tone={state === 'changed' ? 'warning' : 'inert'}>
    {label}
  </StatusTag>;
}
