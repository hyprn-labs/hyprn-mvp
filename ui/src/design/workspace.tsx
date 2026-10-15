import { useEffect, useId, useRef, type ReactNode, type ComponentProps } from 'react';
import { BrandLogo } from './BrandLogo';
import { Button, Panel, Tabs, type TabItem } from './components';
import { Assertion, ActionGroup } from './compositions';

/** Layout only: the application owns destinations, guards and record reads. */
export function WorkspaceShell({
  navigation,
  children,
  context,
  assistant,
}: {
  navigation: ReactNode;
  children: ReactNode;
  context?: ReactNode;
  assistant?: ReactNode;
}) {
  return (
    <div className="hf-workspace">
      {navigation}
      <div className="hf-workspace__stage">
        <div className="hf-workspace__canvas">
          <div className="hf-workspace__content">{children}</div>
        </div>
        {context && <div className="hf-workspace__context">{context}</div>}
        {assistant && <div className="hf-workspace__assistant">{assistant}</div>}
      </div>
    </div>
  );
}

/** Real destinations supplied by the registry; no fabricated workflow progress. */
export function NavigationRail({
  primary,
  study,
  section,
  items,
  value,
  onChange,
}: {
  primary: ReactNode;
  study?: string;
  section?: string;
  items?: TabItem[];
  value?: string;
  onChange?: (id: string) => void;
}) {
  return (
    <aside className="hf-navigation" aria-label="Workspace navigation">
      <div className="hf-navigation__brand">
        <BrandLogo />
      </div>
      <nav className="hf-navigation__primary" aria-label="Main navigation">
        {primary}
        {study && (
          <div className="hf-navigation__location">
            <span className="hf-navigation__study">{study}</span>
            <span className="hf-navigation__section">{section}</span>
          </div>
        )}
      </nav>
      {items && value && <WorkflowNavigation items={items} value={value} onChange={onChange} />}
    </aside>
  );
}

export function WorkflowNavigation(props: {
  items: TabItem[];
  value: string;
  onChange?: (id: string) => void;
}) {
  return (
    <Tabs navigation className="hf-navigation__sections" label="Workspace sections" {...props} />
  );
}

export function ResourceCard({
  title,
  metadata,
  actions,
  children,
  className = '',
}: {
  title: ReactNode;
  metadata?: ReactNode;
  actions?: ReactNode;
  children?: ReactNode;
  className?: string;
}) {
  return (
    <article className={'hf-resource-card ' + className}>
      <div>
        <h2>{title}</h2>
        {children}
        {metadata}
      </div>
      {actions && <ActionGroup>{actions}</ActionGroup>}
    </article>
  );
}

export function SettingsSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="hf-settings" aria-label={title}>
      <h2>{title}</h2>
      {children}
    </section>
  );
}

/** Domain kind, statement scope and basis are supplied, never inferred. */
export function ClaimCard({
  kind,
  statement,
  scope,
  limits,
  attribution,
  children,
  actions,
}: {
  kind: string;
  statement: ReactNode;
  scope: ReactNode;
  limits?: ReactNode;
  attribution?: ReactNode;
  children?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <Assertion className="hf-claim">
      <h3>{kind}</h3>
      <p className="hf-claim__scope">{scope}</p>
      <div className="hf-claim__statement">{statement}</div>
      {attribution}
      {limits && <div className="hf-claim__limits">{limits}</div>}
      {children}
      {actions && <ActionGroup>{actions}</ActionGroup>}
    </Assertion>
  );
}

export type StatementSet = {
  owner: string;
  version: string;
  ids: readonly string[];
  state: 'complete' | 'partial' | 'unknown';
  label: string;
};

/** Count identities within one explicit owner/version, never source records or prose fragments. */
export function ClaimButton({ set, onClick }: { set: StatementSet; onClick: () => void }) {
  const count = new Set(set.ids).size;
  if (set.state === 'unknown')
    return <p className="hf-claim__scope">Statements unavailable · {set.label}</p>;
  if (!count)
    return (
      <p className="hf-claim__scope">
        {set.state === 'complete' ? 'No linked statements' : 'Statements partially loaded'} ·{' '}
        {set.label}
      </p>
    );
  const label =
    set.state === 'partial'
      ? count + (count === 1 ? ' loaded statement' : ' loaded statements') + ' · partial set'
      : count + (count === 1 ? ' statement' : ' statements');
  return (
    <Button
      className="hf-claim-button"
      size="sm"
      onClick={onClick}
      aria-label={label + ' · ' + set.label}
    >
      {label}
    </Button>
  );
}

/** A nonmodal dock/stack: Escape closes only this layer; modal descendants keep their Escape. */
export function ContextualPanel({
  title,
  onClose,
  onBack,
  children,
  focusOnOpen = false,
  ...props
}: Omit<ComponentProps<typeof Panel>, 'title'> & {
  title: string;
  onClose?: () => void;
  onBack?: () => void;
  focusOnOpen?: boolean;
}) {
  const heading = useRef<HTMLHeadingElement>(null),
    id = useId();
  useEffect(() => {
    if (focusOnOpen) heading.current?.focus();
  }, [focusOnOpen]);
  return (
    <Panel
      {...props}
      label={props.label ?? title}
      className={'hf-context-panel ' + (props.className ?? '')}
    >
      <div
        onKeyDown={(event) => {
          if (
            event.key === 'Escape' &&
            onClose &&
            !event.currentTarget.contains((event.target as HTMLElement).closest('dialog'))
          ) {
            event.preventDefault();
            event.stopPropagation();
            onClose();
          }
        }}
      >
        <div className="hf-context-panel__heading">
          <h2 id={id} ref={heading} tabIndex={-1}>
            {title}
          </h2>
          <ActionGroup>
            {onBack && (
              <Button size="sm" onClick={onBack}>
                Back to statements
              </Button>
            )}
            {onClose && (
              <Button size="sm" aria-label={'Close ' + title} onClick={onClose}>
                Close
              </Button>
            )}
          </ActionGroup>
        </div>
        <div className="hf-context-panel__body">{children}</div>
      </div>
    </Panel>
  );
}

/** Connection, transcript and sends remain the integration owner's responsibility. */
export function AssistantPane({
  state,
  context,
  children,
  actions,
  onClose,
}: {
  state: 'unavailable' | 'disconnected' | 'connected';
  context: ReactNode;
  children?: ReactNode;
  actions?: ReactNode;
  onClose: () => void;
}) {
  return (
    <ContextualPanel title="Assistant" onClose={onClose} focusOnOpen>
      <p>{context}</p>
      {state !== 'connected' ? (
        <p>Not connected. Assistant conversations are unavailable in this workspace.</p>
      ) : (
        children
      )}
      {state === 'connected' && actions}
    </ContextualPanel>
  );
}

/** Local reader destinations only; callers own focus and disclosure state. */
export function ReadingContents({
  items,
}: {
  items: { id: string; label: string; onSelect: () => void }[];
}) {
  if (items.length < 2) return null;
  return (
    <nav className="hf-reading-contents" aria-label="In this explanation">
      <ActionGroup>
        {items.map((item) => (
          <Button key={item.id} size="sm" variant="quiet" onClick={item.onSelect}>
            {item.label}
          </Button>
        ))}
      </ActionGroup>
    </nav>
  );
}
