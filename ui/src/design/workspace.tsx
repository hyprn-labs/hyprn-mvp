import { OpenLink } from './navigation';
import { createContext, useContext, useEffect, useLayoutEffect, useId, useRef, useState, type ReactNode, type ComponentProps } from 'react';
import { TextArea, ActionIcon } from './primitives';
import { BrandLogo } from './BrandLogo';
import { Button, Panel, type TabItem } from './components';
import { Assertion, ActionGroup } from './compositions';

const DockExpansion = createContext<{expanded: boolean; toggle: () => void} | null>(null);

function PanelToggle({expanded, direction, label, onClick, className = ''}: {expanded: boolean; direction: 'left' | 'right'; label: string; onClick: () => void; className?: string}) {
  return <Button variant="quiet" size="sm" iconOnly className={className} aria-label={label} title={label} aria-expanded={expanded} onClick={onClick} icon={<ActionIcon name={direction === 'left' ? 'chevron-left' : 'chevron-right'} />} />;
}

/** Layout only: the application owns destinations, guards and record reads. */
export function WorkspaceShell({
  navigation,
  children,
  context,
  assistant,
  onToggleAssistant,
  onAssistantHost,
  assistantExpanded = false,
}: {
  navigation: ReactNode;
  children: ReactNode;
  context?: ReactNode;
  assistant?: ReactNode;
  onToggleAssistant?: () => void;
  onAssistantHost?: (node: HTMLDivElement | null) => void;
  assistantExpanded?: boolean;
}) {
  const [width, setWidth] = useState(0);
  const drag = useRef<{ x: number; width: number; unit: number } | null>(null);
  const launcher = useRef<HTMLButtonElement>(null);
  const wasOpen = useRef(!!assistant);
  useEffect(() => {
    if (wasOpen.current && !assistant) launcher.current?.focus();
    wasOpen.current = !!assistant;
  }, [assistant]);
  const resize = (value: number) => setWidth(Math.max(-2, Math.min(8, value)));
  return (
    <div className="hf-workspace">
      {navigation}
      <div className="hf-workspace__stage" data-assistant-expanded={assistantExpanded && !!assistant} data-assistant-width={width}>
        <div className="hf-workspace__reading" hidden={assistantExpanded && !!assistant}>
          <div className="hf-workspace__canvas">
            <div className="hf-workspace__content">{children}</div>
          </div>
          {context && <DetailsDock>{context}</DetailsDock>}
        </div>
        {assistant && (
          <div ref={onAssistantHost} id="workspace-assistant" className="hf-workspace__assistant">
            {!assistantExpanded && <div className="hf-assistant-resizer" role="separator" tabIndex={0}
              aria-label="Resize assistant" aria-orientation="vertical" aria-valuemin={-2} aria-valuemax={8} aria-valuenow={width}
              aria-valuetext={width === 0 ? 'Default width' : String(100 + width * 10) + '% of default width'}
              title="Drag to resize · double-click to reset"
              onDoubleClick={() => setWidth(0)}
              onKeyDown={event => {
                if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
                event.preventDefault();
                resize(event.key === 'Home' ? 0 : event.key === 'End' ? 8 : width + (event.key === 'ArrowLeft' ? 1 : -1));
              }}
              onPointerDown={event => {
                event.currentTarget.setPointerCapture(event.pointerId);
                drag.current = { x: event.clientX, width, unit: event.currentTarget.parentElement!.getBoundingClientRect().width / (10 + width) };
              }}
              onPointerMove={event => {
                if (drag.current) resize(drag.current.width + Math.round((drag.current.x - event.clientX) / drag.current.unit));
              }}
              onPointerUp={event => { drag.current = null; event.currentTarget.releasePointerCapture(event.pointerId); }}
              onPointerCancel={() => { drag.current = null; }}
            />}
            {assistant}
          </div>
        )}
      </div>
      {onToggleAssistant && !assistant && (
        <Button
          ref={launcher}
          size="floor"
          className="hf-assistant-launcher"
          aria-label={assistant ? 'Close assistant' : 'Open assistant'}
          title={assistant ? 'Close assistant' : 'Open assistant'}
          aria-expanded={!!assistant}
          aria-controls={assistant ? 'workspace-assistant' : undefined}
          onClick={onToggleAssistant}
          icon={
            <svg className="hf-glyph" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
              <path
                d="M4 5h16v11H9l-5 4V5Z M8 9h8 M8 12h5"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.6"
              />
            </svg>
          }
        >
          Assistant
        </Button>
      )}
    </div>
  );
}

/** All contextual readers share geometry, including readers inside a native dialog. */
export function DetailsDock({ children, modal = false }: { children: ReactNode; modal?: boolean }) {
  const [expanded, setExpanded] = useState(false);
  return <DockExpansion.Provider value={{expanded, toggle: () => setExpanded(value => !value)}}><div data-expanded={expanded} className={'hf-details-dock ' + (modal ? 'hf-details-dock--modal' : 'hf-workspace__context')}>
    {children}
  </div></DockExpansion.Provider>;
}

/** Retain Back state without breaking the dock's bounded layout. */
export function DetailsLayer({ children, hidden = false }: { children: ReactNode; hidden?: boolean }) {
  return <div className="hf-details-layer" hidden={hidden}>{children}</div>;
}

/** Grouped, collapsible application navigation. Actions stay owned by the application. */
export function NavigationRail({ primary, study, section, items, value, onChange,
  onHome, isHome, account, onSettings, onHelp, onSignOut, disabled = false,
}: {
  primary?: ReactNode; study?: string; section?: string; items?: TabItem[]; value?: string;
  onChange?: (id: string) => void; onHome?: () => void; isHome?: boolean;
  account?: string; onSettings?: () => void;
  onHelp?: () => void; onSignOut?: () => void; disabled?: boolean;
}) {
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem('hyprn-navigation-collapsed') === 'true'; }
    catch { return false; }
  });
  const toggle = () => setCollapsed(previous => {
    const next = !previous;
    try { localStorage.setItem('hyprn-navigation-collapsed', String(next)); } catch { /* Usable without storage. */ }
    return next;
  });
  const item = (entry: TabItem) => <Button key={entry.id} variant="quiet"
    className="hf-navigation__item" aria-label={String(entry.label)} title={String(entry.label)}
    aria-current={value === entry.id ? 'page' : undefined} onClick={() => onChange?.(entry.id)}
    icon={<NavigationIcon name={entry.id} />}><span className="hf-navigation__label">{entry.label}</span></Button>;
  const studySections = items?.filter(entry => !['evidence', 'documents', 'help'].includes(entry.id)) ?? [];
  const library = items?.filter(entry => ['evidence', 'documents'].includes(entry.id)) ?? [];
  return <aside className="hf-navigation" data-collapsed={collapsed} aria-label="Workspace navigation">
    <div className="hf-navigation__brand">
      <div className="hf-navigation__wordmark"><BrandLogo /></div>
      <PanelToggle className="hf-navigation__toggle" onClick={toggle} expanded={!collapsed} direction={collapsed ? 'right' : 'left'} label={collapsed ? 'Expand menu' : 'Collapse menu'} />
    </div>
    <nav className="hf-navigation__primary" aria-label="Main navigation">
      {onHome ? isHome ? <span className="hf-navigation__item hf-navigation__current" aria-label="Home" title="Home" aria-current="page">
        <NavigationIcon name="home" /><span className="hf-navigation__label">Home</span>
      </span> : <Button variant="quiet" className="hf-navigation__item" aria-label="Home" title="Home"
        onClick={onHome} icon={<NavigationIcon name="home" />}><span className="hf-navigation__label">Home</span></Button> : primary}
      {study && <div className="hf-navigation__location" title={study} aria-label={'Study: ' + study}>
        <span className="hf-navigation__avatar" aria-hidden="true">{study.trim().slice(0, 1).toUpperCase()}</span>
        <div className="hf-navigation__label"><span className="hf-navigation__eyebrow">Study</span><span className="hf-navigation__study">{study}</span></div>
      </div>}
    </nav>
    {items && <nav className="hf-navigation__sections" aria-label="Workspace sections">
      {studySections.map(item)}
      {!!library.length && <div className="hf-navigation__group"><span className="hf-navigation__eyebrow hf-navigation__label">Library</span>{library.map(item)}</div>}
    </nav>}
    <div className="hf-navigation__footer">
      {onHelp && <Button variant="quiet" className="hf-navigation__item" onClick={onHelp} aria-label="Help" title="Help" aria-current={value === 'help' ? 'page' : undefined} icon={<NavigationIcon name="help" />}><span className="hf-navigation__label">Help</span></Button>}
      {onSettings && <Button variant="quiet" className="hf-navigation__item" onClick={onSettings} aria-label="Settings" title="Settings" icon={<NavigationIcon name="settings" />}><span className="hf-navigation__label">Settings</span></Button>}
      {account !== undefined && <div className="hf-navigation__account">
        <span className="hf-navigation__item hf-navigation__identity" role="img" aria-label={'Signed in as ' + (account || 'unknown user')} title={account}>
          <span className="hf-navigation__avatar" aria-hidden="true">{(account || 'User').slice(0, 2).toUpperCase()}</span>
          <span className="hf-navigation__label" aria-hidden="true">{account}</span>
        </span>
        {onSignOut && <Button variant="quiet" size="sm" onClick={onSignOut} disabled={disabled} aria-label="Sign out" title="Sign out"><NavigationIcon name="logout" /></Button>}
      </div>}
    </div>
  </aside>;
}

/** Independently drawn icons; navigation meaning is always available as an accessible name. */
function NavigationIcon({ name }: { name: string }) {
  const paths: Record<string, string> = {
    home: 'M3 11 12 3l9 8M5 10v11h5v-7h4v7h5V10',
    overview: 'M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z',
    model: 'M3 3h6v6H3zM15 3h6v6h-6zM9 15h6v6H9zM6 9v3h12V9M12 12v3',
    configurations: 'M4 3h16v18H4zM7 7h10M7 11h2m6 0h2M7 15h2m6 0h2M7 18h2m6 0h2',
    evidence: 'M6 3h12v18H6zM9 7h6M9 11h6M9 15h4',
    documents: 'M8 12v5a4 4 0 0 0 8 0V7a3 3 0 0 0-6 0v10a1 1 0 0 0 2 0V8',
    help: 'M9 8a3 3 0 1 1 5 2c-2 1-2 2-2 3M12 17h.01M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20',
    settings: 'M9 3h6l1 3 3 1 2 5-2 5-3 1-1 3H9l-1-3-3-1-2-5 2-5 3-1zM12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8',
    logout: 'M10 3H4v18h6M9 12h12m-5-5 5 5-5 5',
  };
  return <svg className="hf-glyph" viewBox="0 0 24 24" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d={paths[name] ?? paths.evidence} /></svg>;
}

/** Honest destination for a visible feature that has no product implementation yet. */
export function FeatureUnavailable({ name }: { name: string }) {
  return <Panel label={name}><h2>{name}</h2><p>This functionality is not implemented yet.</p></Panel>;
}

/** Labeled scientific scope above a tabbed collection, with a clear content gap. */
export function CalculationNavigation({ model, version, children }: {
  model: ReactNode; version: ReactNode; children: ReactNode;
}) {
  return <section className="hf-calculation-navigation" aria-label="Experiments navigation">
    <div className="hf-calculation-navigation__scope">
      <h2>Experiments</h2>
      <div className="hf-calculation-navigation__fields">
        <label><span>Model</span>{model}</label>
        <label><span>Model version</span>{version}</label>
      </div>
    </div>
    {children}
  </section>;
}

/** A collection's count and commands, without repeating its selected tab title. */
export function CollectionToolbar({ summary, actions }: { summary: ReactNode; actions?: ReactNode }) {
  return <div className="hf-collection-toolbar">
    <p>{summary}</p><ActionGroup>{actions}</ActionGroup>
  </div>;
}

/** Facts from one record; numbers and status retain their own presentation and meaning. */
export function MetricGrid({ label, items, layout = 'grid' }: {
  label: string;
  layout?: 'grid' | 'inline';
  items: { label: string; value: ReactNode; detail?: ReactNode }[];
}) {
  return <dl className={'hf-metric-grid' + (layout === 'inline' ? ' hf-metric-grid--inline' : '')} aria-label={label}>
    {items.map((item) => <div key={item.label}>
      <dt>{item.label}</dt>
      <dd>{item.value}</dd>
      {item.detail && <dd className="hf-metric-detail">{item.detail}</dd>}
    </div>)}
  </dl>;
}

export function ResourceCard({
  title,
  metadata,
  facts,
  actions,
  actionLayout = 'inline',
  level = 2,
  children,
  className = '',
}: {
  title: ReactNode;
  /** Heading level within the page: 2 below a page h1, 3 below a page h2. */
  level?: 2 | 3;
  metadata?: ReactNode;
  /** At most three distinguishing facts. Counts belong to the enclosing collection. */
  facts?: readonly [ReactNode, ReactNode?, ReactNode?];
  actions?: ReactNode;
  actionLayout?: 'inline' | 'stacked';
  children?: ReactNode;
  className?: string;
}) {
  return (
    <article className={'hf-resource-card ' + className} data-action-layout={actionLayout}>
      <div>
        {level === 3 ? <h3>{title}</h3> : <h2>{title}</h2>}
        {children}
        {facts && (
          <ul className="hf-resource-facts">
            {facts.filter(Boolean).map((fact, index) => (
              <li key={index}>{fact}</li>
            ))}
          </ul>
        )}
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

/** One action per supported item; the application supplies the distinct version count. */
export function EvidenceButton({ count, onClick }: { count: number; onClick: () => void }) {
  if (!count) return null;
  return <div className="hf-evidence-action"><OpenLink size="sm" onClick={onClick}>View evidence ({count})</OpenLink></div>;
}

/** A nonmodal dock/stack: Escape closes only this layer; modal descendants keep their Escape. */
export function ContextualPanel({
  title,
  onClose,
  onBack,
  children,
  focusOnOpen = false,
  headerActions,
  closeLabel,
  help,
  ...props
}: Omit<ComponentProps<typeof Panel>, 'title'> & {
  title: string;
  onClose?: () => void;
  onBack?: () => void;
  focusOnOpen?: boolean;
  headerActions?: ReactNode;
  closeLabel?: string;
}) {
  const expansion = useContext(DockExpansion);
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
      <div className="hf-context-panel__layout"
        onKeyDown={(event) => {
          if (
            event.key === 'Escape' &&
            onClose &&
            (event.target as HTMLElement).closest('dialog') === event.currentTarget.closest('dialog')
          ) {
            event.preventDefault();
            event.stopPropagation();
            onClose();
          }
        }}
      >
        <div className="hf-context-panel__heading">
          <div className="hf-heading-group">
            <h2 id={id} ref={heading} tabIndex={-1}>
              {title}
            </h2>
            {help}
          </div>
          <ActionGroup>
            {headerActions}
            {expansion && <PanelToggle expanded={expansion.expanded} direction={expansion.expanded ? 'right' : 'left'} label={expansion.expanded ? 'Restore details width' : 'Expand details'} onClick={expansion.toggle} />}
            {onBack && (
              <OpenLink size="sm" direction="back" onClick={onBack}>
                Back
              </OpenLink>
            )}
            {onClose && (
              <Button variant="quiet" size="sm" aria-label={closeLabel ?? 'Close ' + title} title={closeLabel ?? 'Close ' + title} onClick={onClose}><ActionIcon name="close" /></Button>
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
  navigation,
  children,
  actions,
  onClose,
  expanded = false,
  onToggleExpanded,
}: {
  state: 'unavailable' | 'disconnected' | 'connected';
  context: ReactNode;
  navigation?: ReactNode;
  children?: ReactNode;
  actions?: ReactNode;
  onClose: () => void;
  expanded?: boolean;
  onToggleExpanded?: () => void;
}) {
  const scroll = useRef<HTMLDivElement>(null);
  const follow = useRef(true);
  useLayoutEffect(() => {
    const element = scroll.current;
    if (element && follow.current) element.scrollTop = element.scrollHeight;
  }, [children]);
  return (
    <ContextualPanel title="Assistant" className="hf-assistant-pane" onClose={onClose} closeLabel="Hide assistant" focusOnOpen
      headerActions={onToggleExpanded && <PanelToggle expanded={expanded} direction={expanded ? 'right' : 'left'} label={expanded ? 'Exit full screen' : 'Expand to full width'} onClick={onToggleExpanded} />}>
      {navigation}
      {context && <p className="hf-assistant-context">{context}</p>}
      <div className="hf-assistant-conversation" ref={scroll} onScroll={() => {
        const element = scroll.current;
        if (element) follow.current = element.scrollHeight - element.scrollTop - element.clientHeight < 48;
      }}>
        {state !== 'connected' ? (
          <p className="hf-assistant-empty">Assistant is not available yet</p>
        ) : (
          children
        )}
      </div>
      {state === 'connected' ? (
        actions
      ) : (
        <div className="hf-assistant-composer">
          <TextArea
            aria-label="Message assistant"
            placeholder="Message assistant…"
            rows={3}
            disabled
          />
          <Button disabled>Send</Button>
        </div>
      )}
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
