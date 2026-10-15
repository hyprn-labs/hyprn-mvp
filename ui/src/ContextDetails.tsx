import { createPortal } from 'react-dom';
import { AttributionContext } from './attribution';
import type { AttributionIndex } from './api';
import {
  createContext,
  useContext,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import type { EvidenceSnapshot, HyprnMvpApi } from './api';
import { EvidenceRecordBody, evidenceTitle } from './EvidenceView';
import {
  ActionDialog,
  AssistantPane,
  Button,
  ClaimButton,
  ClaimCard,
  ContextualPanel,
  Select,
  SettingsSection,
  WorkspaceShell,
} from './design';

export type ContextStatement = {
  id: string;
  kind: string;
  statement: string;
  scope: string;
  limits?: ReactNode;
  attribution?: ReactNode;
  actions?: ReactNode;
  basisLabel?: string;
  sources: Array<{ id: string; relation?: string; locator?: string; record?: EvidenceSnapshot }>;
};
type Group = {
  owner: string;
  version: string;
  label: string;
  statements: ContextStatement[];
  state?: 'complete' | 'partial' | 'unknown';
};
type Reader = {
  group: Group;
  selected: string;
  invoker: HTMLElement | null;
  host: HTMLDialogElement | null;
  attribution: AttributionIndex;
  focusSelection: boolean;
};
type ContextValue = {
  inspect: (group: Group, selected: string | undefined, attribution: AttributionIndex) => void;
  clearOwner: (owner: string) => void;
};
const Context = createContext<ContextValue | null>(null);

/** Selection is ephemeral; authoritative content stays at its existing record owner. */
export function StatementActions({
  group,
  selected,
  compact = false,
  actionLabel = 'Inspect statement',
}: {
  group: Group;
  selected?: string;
  compact?: boolean;
  actionLabel?: string;
}) {
  const context = useContext(Context);
  const attribution = useContext(AttributionContext);
  const signature = JSON.stringify([
    group.owner,
    group.version,
    group.statements.map((item) => [
      item.id,
      item.statement,
      item.sources.map((source) => [source.id, source.relation, source.record]),
    ]),
  ]);
  useEffect(
    () => () => context?.clearOwner(group.owner),
    [context?.clearOwner, group.owner, signature],
  );
  if (!context) return null;
  return compact ? (
    <Button size="sm" onClick={() => context.inspect(group, selected, attribution)}>
      {actionLabel}
    </Button>
  ) : (
    <ClaimButton
      set={{
        owner: group.owner,
        version: group.version,
        label: group.label,
        ids: group.statements.map((item) => item.id),
        state: group.state ?? 'complete',
      }}
      onClick={() => context.inspect(group, selected, attribution)}
    />
  );
}

/** Source reads use the study/session fence and verify the requested version. */
function SourceReader({
  api,
  studyId,
  source,
}: {
  api: HyprnMvpApi;
  studyId: string;
  source: ContextStatement['sources'][number];
}) {
  const heading = useRef<HTMLHeadingElement>(null);
  useLayoutEffect(() => {
    heading.current?.focus();
  }, []);
  const [record, setRecord] = useState<EvidenceSnapshot | null>(source.record ?? null);
  const [error, setError] = useState(''),
    [attempt, retry] = useState(0);
  useEffect(() => {
    const read = api.fence({ studyId });
    setRecord(source.record ?? null);
    setError('');
    if (source.record) return () => read.abort();
    void api
      .evidenceVersion(studyId, source.id, read.signal)
      .then((value) => {
        if (!read.valid()) return;
        if (value.evidence_version_id !== source.id) throw new Error('Evidence identity mismatch');
        setRecord(value);
      })
      .catch(async (error) => {
        const result = await api.readFailed(error, read);
        if (read.valid() && result !== 'stale' && result !== 'access-lost')
          setError('Evidence unavailable. This version could not be loaded.');
      })
      .finally(read.done);
    return () => read.abort();
  }, [api, studyId, source, attempt]);
  return (
    <>
      <h3 ref={heading} tabIndex={-1}>
        Evidence content
      </h3>
      {source.relation && <p>{source.relation}</p>}
      {source.locator && <p>{source.locator}</p>}
      <p>Source passage unavailable. Showing evidence content.</p>
      {record ? (
        <EvidenceRecordBody record={record} contextual />
      ) : error ? (
        <>
          <p role="alert">{error}</p>
          <Button onClick={() => retry((value) => value + 1)}>Retry evidence</Button>
        </>
      ) : (
        <p role="status">Loading evidence…</p>
      )}
    </>
  );
}

export function ContextWorkspace({
  api,
  studyId,
  identity,
  studyName,
  navigation,
  children,
}: {
  api: HyprnMvpApi;
  studyId?: string;
  identity: string;
  studyName?: string;
  navigation: ReactNode;
  children: ReactNode;
}) {
  const [reader, setReader] = useState<Reader | null>(null);
  const [source, setSource] = useState<ContextStatement['sources'][number] | null>(null);
  const [assistant, setAssistant] = useState(false);
  const assistantInvoker = useRef<HTMLElement | null>(null);
  const restore = useRef<{ focus: HTMLElement | null; scroll: number } | null>(null);
  const body = useRef<HTMLDivElement>(null);
  const owner = useRef<string | null>(null);
  const clearOwner = useRef((value: string) => {
    if (owner.current === value) {
      owner.current = null;
      setReader(null);
      setSource(null);
      restore.current = null;
    }
  }).current;
  function close() {
    const target = reader?.invoker;
    owner.current = null;
    setReader(null);
    setSource(null);
    restore.current = null;
    if (target?.isConnected) target.focus();
  }
  function closeAssistant() {
    setAssistant(false);
    if (assistantInvoker.current?.isConnected) assistantInvoker.current.focus();
  }
  useLayoutEffect(() => {
    owner.current = null;
    setReader(null);
    setSource(null);
    setAssistant(false);
    restore.current = null;
  }, [identity, api.actor, api.csrf]);
  useEffect(
    () =>
      api.onSessionChange((change) => {
        if (change.kind !== 'access-lost' || change.studyId === studyId) {
          owner.current = null;
          setReader(null);
          setSource(null);
          setAssistant(false);
          restore.current = null;
        }
      }),
    [api, studyId],
  );
  useEffect(() => {
    const host = reader?.host;
    if (!host) return;
    const clear = () => {
      owner.current = null;
      setReader(null);
      setSource(null);
      restore.current = null;
    };
    host.addEventListener('close', clear);
    return () => host.removeEventListener('close', clear);
  }, [reader?.host]);
  useLayoutEffect(() => {
    if (!source && reader) {
      const card = [
        ...(body.current?.querySelectorAll<HTMLElement>('[data-statement]') ?? []),
      ].find((node) => node.dataset.statement === reader.selected);
      if (card && reader.focusSelection) {
        card.scrollIntoView({ block: 'nearest' });
        card.focus();
      }
    }
  }, [reader?.selected, reader?.group.owner]);
  function back() {
    setSource(null);
    requestAnimationFrame(() => {
      if (body.current && restore.current) body.current.scrollTop = restore.current.scroll;
      if (restore.current?.focus?.isConnected) restore.current.focus.focus();
    });
  }
  const panel = reader && studyId && (
    <AttributionContext.Provider value={reader.attribution}>
      <ContextualPanel
        title="Scientific context"
        onClose={close}
        onBack={source ? back : undefined}
        focusOnOpen={!reader.focusSelection}
      >
        <div ref={body} className="hf-context-reader">
          <div hidden={!!source}>
            <h3>{reader.group.label}</h3>
            <ActionDialog title="Statement scope" label="Statement scope details" size="sm">
              <dl>
                <dt>Owner</dt>
                <dd>{reader.group.owner}</dd>
                <dt>Version or draft context</dt>
                <dd>{reader.group.version}</dd>
                <dt>Coverage</dt>
                <dd>{reader.group.state ?? 'complete'}</dd>
              </dl>
            </ActionDialog>
            {reader.group.statements.map((selected) => (
              <div key={selected.id} data-statement={selected.id} tabIndex={-1}>
                <ClaimCard
                  kind={selected.kind}
                  statement={selected.statement}
                  scope={selected.scope}
                  limits={selected.limits}
                  attribution={selected.attribution}
                  actions={selected.actions}
                >
                  <h4>{selected.basisLabel ?? 'Attached evidence'}</h4>
                  {!selected.sources.length && <p>No evidence linked</p>}
                  {selected.sources.map((item, index) => (
                    <div className="hf-context-source" key={index}>
                      <p>{item.relation ?? 'Relationship unspecified'}</p>
                      <p>
                        {item.record
                          ? evidenceTitle(item.record)
                          : 'Evidence version ' + item.id.slice(0, 8)}
                      </p>
                      <Button
                        size="sm"
                        onClick={() => {
                          setReader({ ...reader, selected: selected.id });
                          restore.current = {
                            focus: document.activeElement as HTMLElement,
                            scroll: body.current?.scrollTop ?? 0,
                          };
                          setSource(item);
                        }}
                      >
                        View evidence
                      </Button>
                    </div>
                  ))}
                </ClaimCard>
              </div>
            ))}
          </div>
          {source && <SourceReader key={source.id} api={api} studyId={studyId} source={source} />}
        </div>
      </ContextualPanel>
    </AttributionContext.Provider>
  );
  return (
    <Context.Provider
      value={{
        clearOwner,
        inspect: (group, selected, attribution) => {
          owner.current = group.owner;
          setSource(null);
          restore.current = null;
          setReader({
            group,
            selected: selected ?? group.statements[0]?.id,
            invoker: document.activeElement as HTMLElement,
            host: document.activeElement?.closest('dialog[open]') as HTMLDialogElement | null,
            attribution,
            focusSelection: selected !== undefined,
          });
        },
      }}
    >
      <WorkspaceShell
        navigation={navigation}
        context={reader?.host ? undefined : panel}
        assistant={
          assistant && (
            <AssistantPane
              state="disconnected"
              context={
                studyName
                  ? 'Study: ' + studyName + '. No record context attached.'
                  : 'No study context attached.'
              }
              onClose={closeAssistant}
            />
          )
        }
      >
        {studyId && (
          <div className="hf-workspace__tools">
            <Button
              size="sm"
              aria-expanded={assistant}
              onClick={() => {
                assistantInvoker.current = document.activeElement as HTMLElement;
                if (assistant) closeAssistant();
                else setAssistant(true);
              }}
            >
              {assistant ? 'Close assistant' : 'Open assistant'}
            </Button>
          </div>
        )}
        {children}
      </WorkspaceShell>
      {reader?.host && createPortal(panel, reader.host)}
    </Context.Provider>
  );
}

type Theme = 'system' | 'light' | 'dark';
export function AppearanceSettings() {
  const [theme, setTheme] = useState<Theme>(() => {
    try {
      const stored = localStorage.getItem('hyprn-appearance');
      return stored === 'light' || stored === 'dark' ? stored : 'system';
    } catch {
      return 'system';
    }
  });
  useEffect(() => {
    if (theme === 'system') delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = theme;
  }, [theme]);
  return (
    <SettingsSection title="Appearance">
      <label>
        Appearance
        <Select
          aria-label="Appearance"
          value={theme}
          onChange={(event) => {
            const value = event.target.value as Theme;
            setTheme(value);
            try {
              localStorage.setItem('hyprn-appearance', value);
            } catch {
              /* Presentation still works without storage. */
            }
          }}
        >
          <option value="system">System</option>
          <option value="light">Day</option>
          <option value="dark">Control room</option>
        </Select>
      </label>
      <p>Appearance applies only to this browser.</p>
    </SettingsSection>
  );
}

/** Apply the local preference before Profile opens; denied storage keeps system behavior. */
export function useAppearance() {
  useLayoutEffect(() => {
    try {
      const theme = localStorage.getItem('hyprn-appearance');
      if (theme === 'light' || theme === 'dark') document.documentElement.dataset.theme = theme;
      else delete document.documentElement.dataset.theme;
    } catch {
      delete document.documentElement.dataset.theme;
    }
  }, []);
}
