import { useEffect, useId, useRef, useState, type ReactElement, type ReactNode, type ComponentPropsWithRef } from 'react';
import { createPortal } from 'react-dom';
import { Button, Tabs, StatusTag, type Tone, type ButtonProps } from './components';
import { formatNumber } from './numbers';

export type ActionIconName = 'close' | 'back' | 'add' | 'import' | 'export'
  | 'chevron-left' | 'chevron-right' | 'chevron-up' | 'chevron-down' | 'search';

// Independently drawn on a 24-unit grid; no icon library or font assets.
const paths: Record<Exclude<ActionIconName, 'search'>, string> = {
  close: 'M6 6l12 12M18 6L6 18',
  back: 'M20 12H4m7-7-7 7 7 7',
  add: 'M12 4v16M4 12h16',
  import: 'M12 3v12m-5-5 5 5 5-5M4 15v6h16v-6',
  export: 'M12 16V4m-5 5 5-5 5 5M4 15v6h16v-6',
  'chevron-left': 'm15 5-7 7 7 7',
  'chevron-right': 'm9 5 7 7-7 7',
  'chevron-up': 'm5 15 7-7 7 7',
  'chevron-down': 'm5 9 7 7 7-7',
};

/** Decorative only. Give the containing Button visible text or an aria-label. */
export function ActionIcon({ name }: { name: ActionIconName }): ReactElement {
  return (
    <svg className="hf-glyph" viewBox="0 0 24 24" aria-hidden="true" focusable="false"
      fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="square" strokeLinejoin="miter">
      {name === 'search' ? <><circle cx="10" cy="10" r="6" /><path d="m15 15 6 6" /></> : <path d={paths[name]} />}
    </svg>
  );
}

/** Native semantics and controlled values pass through; no domain state lives here. */
export function TextInput({ className = '', ...props }: ComponentPropsWithRef<'input'>) {
  return <input {...props} className={'hf-input ' + className} />;
}
/** English action/filename presentation; the platform file chooser keeps its native locale. */
export function FilePicker({ label, ...props }: Omit<ComponentPropsWithRef<'input'>, 'type' | 'ref'> & { label: string }) {
  const input = useRef<HTMLInputElement>(null), [name, setName] = useState('No file selected');
  return <div className="hf-file-picker"><input {...props} ref={input} type="file" hidden tabIndex={-1} aria-label={label} onChange={event => { setName(event.target.files?.[0]?.name ?? 'No file selected'); props.onChange?.(event); }} /><Button disabled={props.disabled} onClick={() => input.current?.click()}>Choose file</Button><span aria-live="polite">{name}</span></div>;
}
/** Only explicit work counts determine progress; stages never imply elapsed-time percentages. */
export function Progress({ label, message, count }: {
  label: string;
  message?: string;
  count?: { completed: number; total: number };
}) {
  const known = count && Number.isSafeInteger(count.completed) &&
    Number.isSafeInteger(count.total) && count.total > 0 &&
    count.completed >= 0 && count.completed <= count.total;
  return <section className="hf-progress">
    <p role="status">{label}</p>
    <progress aria-label={label} value={known ? count.completed : undefined}
      max={known ? count.total : undefined} />
    {message && <p className="hf-progress__message">{message}</p>}
  </section>;
}
export function TextArea({ className = '', ...props }: ComponentPropsWithRef<'textarea'>) {
  return <textarea {...props} className={'hf-input hf-textarea ' + className} />;
}
export function Select({ className = '', ...props }: ComponentPropsWithRef<'select'>) {
  return <select {...props} className={'hf-input ' + className} />;
}
export function Checkbox(props: ComponentPropsWithRef<'input'>) {
  return <TextInput {...props} type="checkbox" />;
}
export function Disclosure(props: ComponentPropsWithRef<'details'>) {
  return <details {...props} />;
}
export function DialogFrame({ className = '', onKeyDown, ...props }: ComponentPropsWithRef<'dialog'>) {
  return <dialog {...props} className={'hf-dialog ' + className} onKeyDown={event => {
    onKeyDown?.(event);
    const dialog = event.currentTarget;
    // Native modal inertness blocks the page, but Tab can still leave for browser
    // chrome. Wrap only the active modal's boundaries; keep its native inner order.
    if (event.defaultPrevented || event.key !== 'Tab' || event.altKey || event.ctrlKey || event.metaKey
      || !dialog.matches(':modal') || (event.target as Element).closest('dialog:modal') !== dialog) return;
    const candidates = Array.from(dialog.querySelectorAll<HTMLElement>('button, input, select, textarea, a[href], area[href], summary, iframe, object, embed, [tabindex], [contenteditable], audio[controls], video[controls]'))
      .filter(element => element.tabIndex >= 0 && !element.matches(':disabled') && !element.closest('[inert]')
        && element.closest('dialog') === dialog && element.checkVisibility({ visibilityProperty: true }));
    const tabbable = candidates.filter(element => {
      if (!(element instanceof HTMLInputElement) || element.type !== 'radio' || !element.name) return true;
      const group = candidates.filter((other): other is HTMLInputElement => other instanceof HTMLInputElement
        && other.type === 'radio' && other.name === element.name && other.form === element.form);
      return element === (group.find(radio => radio.checked) ?? group[0]);
    }).sort((a, b) => (a.tabIndex || Infinity) - (b.tabIndex || Infinity));
    const first = tabbable[0], last = tabbable[tabbable.length - 1], active = document.activeElement;
    if (!first || active === dialog || (event.shiftKey ? active === first : active === last)) {
      event.preventDefault();
      (event.shiftKey ? last : first)?.focus();
    }
  }} />;
}
export function SectionHeader({ title, actions, level = 3, id }: { title: ReactNode; actions?: ReactNode; level?: 2 | 3 | 4; id?: string }) {
  const Heading = ('h' + level) as 'h2' | 'h3' | 'h4';
  return <div className="section-header"><Heading id={id}>{title}</Heading>{actions && <div className="section-actions">{actions}</div>}</div>;
}

export type CriterionRecordProps = {
  number: number;
  target: string | null;
  comparison: string;
  threshold: number | null;
  units: string;
  tolerances?: { absolute: number | null; relative: number | null };
  evidence?: ReactNode;
  evaluation?: { label: string; tone: Tone; reason?: string; actual?: number | null; units?: string };
};

/** Presentation only: callers resolve quantities and supply saved criterion evaluations. */
export function CriterionRecord({ number, target, comparison, threshold, units, tolerances, evidence, evaluation }: CriterionRecordProps) {
  const id = useId(), unit = units || 'dimensionless';
  const value = (n: number | null, missing = 'unassigned') => n === null ? missing : formatNumber(n);
  return (
    <article className="hf-criterion-record hf-criterion" aria-labelledby={id}>
      <div className="hf-criterion__heading">
        <h4 id={id}>Criterion {number}</h4>
        {evaluation && <StatusTag tone={evaluation.tone}>{evaluation.label}</StatusTag>}
      </div>
      <p className="hf-criterion__target">{target || 'Choose output'}</p>
      <div className="hf-criterion__requirement">
        <span>{comparison}</span>
        <span
          className="hf-criterion__number"
          title={threshold === null ? undefined : String(threshold)}
        >
          {value(threshold)}
        </span>
        <span className="hf-criterion__unit">{unit}</span>
      </div>
      {tolerances && (
        <dl className="hf-criterion__facts">
          <div>
            <dt>Absolute tolerance</dt>
            <dd>
              {value(tolerances.absolute)} <span className="hf-criterion__unit">{unit}</span>
            </dd>
          </div>
          <div>
            <dt>Relative tolerance</dt>
            <dd>{value(tolerances.relative)}</dd>
          </div>
        </dl>
      )}
      {evaluation?.actual !== undefined && (
        <dl className="hf-criterion__facts">
          <div>
            <dt>Actual value</dt>
            <dd>
              {value(evaluation.actual, 'not computed')}{' '}
              <span className="hf-criterion__unit">{evaluation.units ?? unit}</span>
            </dd>
          </div>
        </dl>
      )}
      {evaluation?.reason && <p className="hf-criterion__reason">{evaluation.reason}</p>}
      {evidence && <div className="hf-criterion__evidence">{evidence}</div>}
    </article>
  );
}

/** Closing hides rather than unmounts children, preserving the owning controller's draft. */
export function ActionDialog({
  title,
  label = title,
  children,
  disabled = false,
  actionHost,
  completionKey,
  size,
  triggerLabel,
  variant,
  width = 'default',
  closeLabel = 'Done',
}: {
  closeLabel?: string;
  variant?: ButtonProps['variant'];
  width?: 'default' | 'workspace';
  size?: 'sm' | 'desk';
  triggerLabel?: string;
  title: string;
  label?: string;
  children: ReactNode;
  disabled?: boolean;
  actionHost?: HTMLElement | null;
  completionKey?: number;
}) {
  const dialog = useRef<HTMLDialogElement>(null),
    invoker = useRef<HTMLElement | null>(null),
    id = useId();
  useEffect(() => {
    if (completionKey) dialog.current?.close();
  }, [completionKey]);
  const trigger = (
    <Button
      variant={variant}
      size={size}
      iconOnly={label === '…'}
      aria-label={triggerLabel}
      disabled={disabled}
      aria-haspopup="dialog"
      onClick={() => {
        invoker.current = document.activeElement as HTMLElement;
        dialog.current?.showModal();
      }}
    >
      {label}
    </Button>
  );
  // Native close normally restores focus; its delayed event must not steal a later selection.
  return (
    <>
      {actionHost ? createPortal(trigger, actionHost) : trigger}
      <DialogFrame
        ref={dialog}
        aria-labelledby={id}
        className={'action-dialog' + (width === 'workspace' ? ' hf-dialog--workspace' : '')}
        onClose={() => {
          const active = document.activeElement;
          if (
            invoker.current?.isConnected &&
            (active === document.body || !active || dialog.current?.contains(active))
          )
            invoker.current.focus();
        }}
      >
        <div className="dialog-heading">
          <h2 id={id}>{title}</h2>
          <Button
            variant="quiet"
            icon={<ActionIcon name="close" />}
            aria-label={'Close ' + title}
            onClick={() => dialog.current?.close()}
          />
        </div>
        <div className="dialog-body">{children}</div>
        <div className="dialog-footer">
          <Button onClick={() => dialog.current?.close()}>{closeLabel}</Button>
        </div>
      </DialogFrame>
    </>
  );
}
export function DetailTabs({ ports, source, assumptions }: { ports: ReactNode; source: ReactNode; assumptions: ReactNode }) {
  const [tab, setTab] = useState('0'), id = useId();
  return <><Tabs className="detail-tabs" label="Component details" value={tab} onChange={setTab}
    items={['Ports', 'Source', 'Assumptions'].map((label, i) => ({ id: String(i), label, tabId: id + '-tab-' + i, panelId: id + '-panel-' + i }))} />
    {[ports, source, assumptions].map((content, i) => <div key={i} role="tabpanel" id={id + '-panel-' + i} aria-labelledby={id + '-tab-' + i} hidden={tab !== String(i)}>{content}</div>)}</>;
}
