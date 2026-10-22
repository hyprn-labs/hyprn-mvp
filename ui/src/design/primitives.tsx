import { cloneElement, createContext, useContext, useEffect, useId, useRef, useState, type ReactElement, type ReactNode, type ComponentPropsWithRef } from 'react';
import { createPortal } from 'react-dom';
import { Button, Tabs, StatusTag, type Tone, type ButtonProps } from './components';
import { formatNumber } from './numbers';
import sectionHelp from './section-help.json';
import { displayUnit } from '../unitLabels';

import { ActionIcon } from './icons';
import { OpenLink } from './navigation';
export { ActionIcon } from './icons';
export type { ActionIconName } from './icons';

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
/** Ordinary form fields share visible labels, optionality and spacing across editors. */
export function FormField({ label, optional = false, children }: {
  label: string;
  optional?: boolean;
  children: ReactNode;
}) {
  return <label className="hf-form-field">
    <span>{label}{optional && <span className="hf-form-field__optional"> (optional)</span>}</span>
    {children}
  </label>;
}
/** Optional field guidance has its own hierarchy; warnings remain full-size alerts. */
export function FieldHint({ children, id }: { children: ReactNode; id?: string }) {
  return <p id={id} className="hf-field-hint">{children}</p>;
}
export function TextArea({ className = '', ...props }: ComponentPropsWithRef<'textarea'>) {
  return <textarea {...props} className={'hf-input hf-textarea ' + className} />;
}
export { Select } from './select';
export function Checkbox(props: ComponentPropsWithRef<'input'>) {
  return <TextInput {...props} type="checkbox" />;
}
export function Disclosure({ className = '', ...props }: ComponentPropsWithRef<'details'>) {
  return <details {...props} className={'hf-disclosure ' + className} />;
}
type DialogFooter = { root: HTMLDivElement; secondary: HTMLDivElement; primary: HTMLDivElement };
const DialogFooterContext = createContext<DialogFooter | null | undefined>(undefined);

type CompletionActionsProps = {
  children?: ReactNode;
  primary?: ReactElement<ButtonProps> | false | null;
};
function primaryAction(primary: CompletionActionsProps['primary']) {
  return primary ? cloneElement(primary, {
    variant: primary.props.variant === 'danger' ? 'danger' : 'primary',
  }) : null;
}

/** Inline editors use the same action order and emphasis as modal editors. */
export function FormActions({ children, primary }: CompletionActionsProps) {
  return <div className="hf-form-actions">{children}{primaryAction(primary)}</div>;
}

/** Secondary actions always precede the highlighted primary action, including in
 * keyboard order. Submit form ownership and disabled/hidden state stay explicit.
 */
export function DialogActions({ children, primary, active = true }: {
  active?: boolean;
} & CompletionActionsProps) {
  const host = useContext(DialogFooterContext);
  if (!active) return null;
  const commit = primaryAction(primary);
  if (host === undefined) return <div className="hf-dialog-actions">{children}{commit}</div>;
  return host ? <>
    {children && createPortal(children, host.secondary)}
    {commit && createPortal(commit, host.primary)}
  </> : null;
}

/** A modal frame; `width="wide"` gives a comparison its reading width from the layout tokens. */
export function DialogFrame({ className = '', width = 'default', onKeyDown, children, ...props }: ComponentPropsWithRef<'dialog'> & { width?: 'default' | 'wide' }) {
  // Create the portal target before children mount. Mounting it in the same commit
  // keeps native form refs and the owner's initial modal focus available to effects.
  const [footer] = useState(() => {
    if (typeof document === 'undefined') return null;
    const root = document.createElement('div');
    const secondary = document.createElement('div');
    const primary = document.createElement('div');
    root.className = secondary.className = primary.className = 'hf-dialog-actions';
    root.append(secondary, primary);
    return { root, secondary, primary };
  });
  return <dialog {...props} className={'hf-dialog ' + (width === 'wide' ? 'hf-dialog--wide ' : '') + className} onKeyDown={event => {
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
  }}>
    <DialogFooterContext.Provider value={footer}>{children}</DialogFooterContext.Provider>
    <div className="dialog-footer" ref={element => {
      if (element && footer && footer.root.parentNode !== element) element.appendChild(footer.root);
    }} />
  </dialog>;
}
export type SectionHelpTopic = keyof typeof sectionHelp;

/** Shared section meanings; agent guidance carries the same domain distinctions. */
export function SectionHelp({ topic }: { topic: SectionHelpTopic }) {
  const content = sectionHelp[topic];
  return (
    <HelpButton title={content.title}>
      {content.paragraphs.map((paragraph) => (
        <p key={paragraph}>{paragraph}</p>
      ))}
    </HelpButton>
  );
}

export function SectionHeader({
  title,
  actions,
  help,
  level = 3,
  id,
}: {
  title: ReactNode;
  actions?: ReactNode;
  help?: SectionHelpTopic;
  level?: 2 | 3 | 4;
  id?: string;
}) {
  const Heading = ('h' + level) as 'h2' | 'h3' | 'h4';
  return (
    <div className="section-header">
      <div className="hf-heading-group">
        <Heading id={id}>{title}</Heading>
        {help && <SectionHelp topic={help} />}
      </div>
      {actions && (
        <div className="section-actions">
          {actions}
        </div>
      )}
    </div>
  );
}

/** Labels and scientific states are inert; only the distinct arrow navigates. */
export function RecordNavigation({
  children,
  label,
  onOpen,
}: {
  children: ReactNode;
  label: string;
  onOpen: () => void;
}) {
  return (
    <span className="hf-record-navigation">
      <span>{children}</span>
      <OpenLink
        size="sm"
        iconOnly
        className="hf-record-navigation__open"
        aria-label={label}
        title={label}
        onClick={onOpen}
      />
    </span>
  );
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
  const id = useId(), unit = units ? displayUnit(units) : 'dimensionless';
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
              <span className="hf-criterion__unit">{evaluation.units === undefined ? unit : evaluation.units ? displayUnit(evaluation.units) : 'dimensionless'}</span>
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
  purpose = 'action',
  children,
  disabled = false,
  actionHost,
  completionKey,
  size,
  triggerLabel,
  triggerClassName,
  icon,
  variant,
  width = 'default',
  closeLabel = 'Done',
  help,
  onOpen,
  onDismiss,
}: {
  purpose?: 'action' | 'reader';
  closeLabel?: string;
  help?: SectionHelpTopic;
  /** Called each time the dialog opens, so its content can load on demand. */
  onOpen?: () => void;
  /** Discard only local editor state on Cancel, Escape or the close control. */
  onDismiss?: () => void | boolean;
  variant?: ButtonProps['variant'];
  width?: 'default' | 'workspace';
  size?: 'sm' | 'desk';
  triggerLabel?: string;
  triggerClassName?: string;
  icon?: ReactNode;
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
  function dismiss() {
    if (onDismiss?.() === false) return;
    dialog.current?.close();
  }
  const open = () => {
    invoker.current = document.activeElement as HTMLElement;
    dialog.current?.showModal();
    onOpen?.();
  };
  const trigger = purpose === 'reader' ? (
    <OpenLink size={size} aria-label={triggerLabel} className={triggerClassName}
      disabled={disabled} aria-haspopup="dialog" onClick={open}>{label}</OpenLink>
  ) : (
    <Button variant={variant} size={size} iconOnly={label === '…'}
      aria-label={triggerLabel} className={triggerClassName} icon={icon}
      disabled={disabled} aria-haspopup="dialog" onClick={open}>{label}</Button>
  );
  // Native close normally restores focus; its delayed event must not steal a later selection.
  return (
    <>
      {actionHost ? createPortal(trigger, actionHost) : trigger}
      {typeof document !== 'undefined' && createPortal(
        <DialogFrame
          ref={dialog}
          aria-labelledby={id}
          className={'action-dialog' + (width === 'workspace' ? ' hf-dialog--workspace' : '')}
          onCancel={event => { if (event.target !== event.currentTarget) return; event.preventDefault(); dismiss(); }}
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
            <div className="hf-heading-group">
              <h2 id={id}>{title}</h2>
              {help && <SectionHelp topic={help} />}
            </div>
            <Button
              variant="quiet"
              icon={<ActionIcon name="close" />}
              aria-label={'Close ' + title}
              onClick={dismiss}
            />
          </div>
          <div className="dialog-body">{children}</div>
          <DialogActions>
            <Button onClick={dismiss}>{closeLabel}</Button>
          </DialogActions>
        </DialogFrame>,
        document.body,
      )}
    </>
  );
}
/** Context help: one circular trigger, a named dialog, keyboard dismissal and focus return. */
export function HelpButton({ title, children }: { title: string; children: ReactNode }) {
  return <ActionDialog title={title} label="?" triggerLabel={'Help: ' + title}
    triggerClassName="hf-help" variant="quiet" size="sm">{children}</ActionDialog>;
}

export function DetailTabs({ ports, source, assumptions }: { ports: ReactNode; source: ReactNode; assumptions: ReactNode }) {
  const [tab, setTab] = useState('0'), id = useId();
  return <><Tabs className="detail-tabs" label="Component details" value={tab} onChange={setTab}
    items={['Ports', 'Source', 'Assumptions'].map((label, i) => ({ id: String(i), label, tabId: id + '-tab-' + i, panelId: id + '-panel-' + i }))} />
    {[ports, source, assumptions].map((content, i) => <div key={i} role="tabpanel" id={id + '-panel-' + i} aria-labelledby={id + '-tab-' + i} hidden={tab !== String(i)}>{content}</div>)}</>;
}
