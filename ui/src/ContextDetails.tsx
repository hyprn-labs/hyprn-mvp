import { OpenLink } from './design';
import { createPortal } from 'react-dom';
import { StudyAssistant } from './StudyAssistant';
import { AttributionContext } from './attribution';
import type { AttributionIndex } from './api';
import {
  createContext,
  useContext,
  useId,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import type { HyprnMvpApi } from './api';
import {
  Button,
  ContextualPanel,
  DetailsDock,
  DetailsLayer,
  EvidenceButton,
  Select,
  SettingsSection,
  WorkspaceShell,
} from './design';

type Group = { owner: string; version: string; label: string; content: ReactNode };
type Reader = {
  group: Group;
  invoker: HTMLElement | null;
  host: HTMLDialogElement | null;
  attribution: AttributionIndex;
};
type EvidenceDetail = {
  owner: string;
  content: ReactNode;
  invoker: HTMLElement | null;
  host: HTMLDialogElement | null;
  attribution: AttributionIndex;
};
type ContextValue = {
  evidence: (detail: EvidenceDetail) => void;
  clearEvidence: (owner: string) => void;
  updateEvidence: (owner: string, content: ReactNode) => void;
  inspect: (group: Group, attribution: AttributionIndex) => void;
  clearOwner: (owner: string) => void;
};
const Context = createContext<ContextValue | null>(null);
const InsideDetails = createContext(false);

/** Reader content is mounted only on demand and cleared when its owning attachments change. */
export function EvidenceDisclosure({
  count,
  children,
  version = '',
  live = false,
}: {
  count: number;
  children: ReactNode;
  version?: string;
  live?: boolean;
}) {
  const insideDetails = useContext(InsideDetails);
  const context = useContext(Context),
    attribution = useContext(AttributionContext),
    owner = useId();
  useEffect(
    () => () => context?.clearEvidence(owner),
    [context?.clearEvidence, owner, live ? '' : version],
  );
  useEffect(() => {
    if (live) context?.updateEvidence(owner, children);
  }, [context?.updateEvidence, owner, children, live]);
  if (insideDetails) return <>{children}</>;
  return (
    <EvidenceButton
      count={count}
      onClick={() =>
        context?.evidence({
          owner,
          content: children,
          attribution,
          invoker: document.activeElement as HTMLElement,
          host: document.activeElement?.closest('dialog[open]') as HTMLDialogElement | null,
        })
      }
    />
  );
}

/** Open distinct supporting content, never a duplicate statement/evidence intermediary. */
export function ContextAction({group, label}: {group: Group; label: string}) {
  const context = useContext(Context), attribution = useContext(AttributionContext);
  useEffect(() => () => context?.clearOwner(group.owner), [context?.clearOwner, group.owner, group.version]);
  return <OpenLink size="sm" onClick={() => context?.inspect(group, attribution)}>{label}</OpenLink>;
}

export function ContextWorkspace({
  api,
  studyId,
  identity,
  studyName,
  navigation,
  home,
  onOpenStudy,
  onStudyChanged,
  children,
}: {
  api: HyprnMvpApi;
  studyId?: string;
  identity: string;
  studyName?: string;
  navigation: ReactNode;
  home: boolean;
  onOpenStudy: (id: string) => void;
  onStudyChanged: (studyId: string) => void;
  children: ReactNode;
}) {
  const [detail, setDetail] = useState<EvidenceDetail | null>(null);
  const detailOwner = useRef<string | null>(null);
  const detailInvoker = useRef<HTMLElement | null>(null);
  const clearEvidence = useRef((value: string) => {
    if (detailOwner.current === value) {
      detailOwner.current = null;
      setDetail(null);
      const target = detailInvoker.current;
      requestAnimationFrame(() => { if (target?.isConnected) target.focus(); });
    }
  }).current;
  const updateEvidence = useRef((value: string, content: ReactNode) => {
    setDetail((previous) =>
      previous?.owner === value && previous.content !== content
        ? { ...previous, content }
        : previous,
    );
  }).current;
  const [reader, setReader] = useState<Reader | null>(null);
  const [assistant, setAssistant] = useState(false);
  const [assistantStarted, setAssistantStarted] = useState(false);
  const [assistantHost, setAssistantHost] = useState<HTMLDivElement | null>(null);
  const [attachedStudy, setAttachedStudy] = useState<{ id: string; name?: string } | null>(null);
  const attachedId = studyId ?? attachedStudy?.id;
  const attachedName = studyId ? studyName : attachedStudy?.name;
  useLayoutEffect(() => {
    if (studyId) setAttachedStudy({ id: studyId, name: studyName });
  }, [studyId, studyName]);
  const [assistantExpanded, setAssistantExpanded] = useState(false);
  const assistantInvoker = useRef<HTMLElement | null>(null);
  const owner = useRef<string | null>(null);
  const clearOwner = useRef((value: string) => {
    if (owner.current === value) {
      owner.current = null;
      detailOwner.current = null;
      setDetail(null);
      setReader(null);
    }
  }).current;
  function closeEvidence() {
    const target = detail?.invoker;
    detailOwner.current = null;
    setDetail(null);
    requestAnimationFrame(() => {
      if (target?.isConnected) target.focus();
    });
  }
  function close() {
    const target = reader?.invoker;
    owner.current = null;
    detailOwner.current = null;
    setDetail(null);
    setReader(null);

    if (target?.isConnected) target.focus();
  }
  function closeAssistant() {
    setAssistant(false);
    setAssistantExpanded(false);
    if (assistantInvoker.current?.isConnected) assistantInvoker.current.focus();
  }
  useLayoutEffect(() => {
    owner.current = null;
    detailOwner.current = null;
    setDetail(null);
    setReader(null);
  }, [identity, api.actor, api.csrf]);
  useLayoutEffect(() => {
    setAssistant(false);
    setAssistantExpanded(false);
    setAttachedStudy(null);
    setAssistantStarted(false);
  }, [api.actor, api.csrf]);
  useEffect(
    () =>
      api.onSessionChange((change) => {
        if (change.kind !== 'access-lost' || change.studyId === attachedId) {
          owner.current = null;
          detailOwner.current = null;
          setDetail(null);
          setReader(null);

          setAttachedStudy(null);
          setAssistant(false);
          setAssistantExpanded(false);
        }
      }),
    [api, attachedId],
  );
  useEffect(() => {
    const host = detail?.host ?? reader?.host;
    if (!host) return;
    const clear = () => {
      owner.current = null;
      detailOwner.current = null;
      setDetail(null);
      setReader(null);
    };
    host.addEventListener('close', clear);
    return () => host.removeEventListener('close', clear);
  }, [reader?.host, detail?.host]);
  const supportingPanel = reader && studyId && (
    <AttributionContext.Provider value={reader.attribution}>
      <ContextualPanel
        title={reader.group.label}
        onClose={close}
        focusOnOpen
      >
        <div className="hf-context-reader">
          <div>
            <InsideDetails.Provider value={true}>{reader.group.content}</InsideDetails.Provider>
          </div>
        </div>
      </ContextualPanel>
    </AttributionContext.Provider>
  );
  const host = detail?.host ?? reader?.host;
  const panel = (
    <>
      {supportingPanel && <DetailsLayer hidden={!!detail}>{supportingPanel}</DetailsLayer>}
      {detail && (
        <AttributionContext.Provider value={detail.attribution}>
          <ContextualPanel
            label="Evidence details"
            title="Evidence"
            onClose={closeEvidence}
            onBack={reader ? closeEvidence : undefined}
            focusOnOpen
          >
            <div className="hf-context-reader"><InsideDetails.Provider value={true}>{detail.content}</InsideDetails.Provider></div>
          </ContextualPanel>
        </AttributionContext.Provider>
      )}
    </>
  );
  return (
    <Context.Provider
      value={{
        clearOwner,
        clearEvidence,
        updateEvidence,
        evidence: (value) => {
          if (!value.invoker?.closest('.hf-context-panel')) {
            owner.current = null;
            setReader(null);
          }
          detailOwner.current = value.owner;
          detailInvoker.current = value.invoker;
          setDetail(value);
        },
        inspect: (group, attribution) => {
          detailOwner.current = null;
          setDetail(null);
          owner.current = group.owner;

          setReader({
            group,
            invoker: document.activeElement as HTMLElement,
            host: document.activeElement?.closest('dialog[open]') as HTMLDialogElement | null,
            attribution,
          });
        },
      }}
    >
      <WorkspaceShell
        navigation={navigation}
        assistantExpanded={assistantExpanded}
        context={!host && (reader || detail) ? panel : undefined}
        onToggleAssistant={() => {
          assistantInvoker.current = document.activeElement as HTMLElement;
          if (assistant) closeAssistant();
          else { setAssistantStarted(true); setAssistant(true); }
        }}
        assistant={assistant ? <></> : undefined}
        onAssistantHost={setAssistantHost}
      >
        {children}
      </WorkspaceShell>
      {assistantStarted && (
        <StudyAssistant
          key={attachedId ?? 'no-study'}
          api={api}
          studyId={attachedId}
          studyName={attachedName}
          home={home}
          onOpenStudy={onOpenStudy}
          onStudyChanged={onStudyChanged}
          container={assistantHost}
          expanded={assistantExpanded}
          onToggleExpanded={() => setAssistantExpanded(value => !value)}
          onClose={closeAssistant}
        />
      )}
      {host && createPortal(<DetailsDock modal>{panel}</DetailsDock>, host)}
    </Context.Provider>
  );
}

type Theme = 'light' | 'dark';
/** One default for sign-in, workspace and settings; explicit choices are retained. */
function preferredTheme(): Theme {
  try {
    return localStorage.getItem('hyprn-appearance') === 'light' ? 'light' : 'dark';
  } catch {
    return 'dark';
  }
}
export function AppearanceSettings() {
  const [theme, setTheme] = useState<Theme>(preferredTheme);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
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
          <option value="light">Light</option>
          <option value="dark">Dark</option>
        </Select>
      </label>
      <p>Appearance applies only to this browser.</p>
    </SettingsSection>
  );
}

/** Apply the same preference before the first paint, including sign-in. */
export function useAppearance() {
  useLayoutEffect(() => {
    document.documentElement.dataset.theme = preferredTheme();
  }, []);
}
