import type { Dispatch, ReactNode, RefObject, SetStateAction } from 'react';
import type { ApproachSelection1, EvidenceSnapshot } from '../contract';
import type {
  ConfigurationRevision,
  EvidenceRecord,
  FrozenConfigurationRead7,
  HyprnMvpApi,
  ModelDraftRead4,
  ModelRevisionRead4,
  ModifiedRunSeedRead6,
  PublicRun,
  PublicRunDetail,
  RevisionSummary,
  Study,
} from '../api';
import type { ApproachController } from '../ApproachController';
import type { ApproachHandoff } from '../ApproachAssumptions';
import type { ConfigurationHandle, ConfigurationInspection } from '../ConfigurationPanel';
import type { EditorHandle } from '../ModelEditor';
import type { MethodLink, MethodLinks } from '../modelMethods';
import type { ModelController } from '../ModelController';
import type { RunFilters } from '../RunPanel';
import type { useUnitCatalog } from '../UnitEditor';
import type { VariableContext } from '../VariablesTable';
import {
  parseWorkspaceLink,
  type EditorGuard,
  type GuardEntry,
  type GuardSlot,
  type Selection,
  type ViewLinkRules,
  type WorkspaceContext,
  type WorkspaceLink,
  type WorkspaceView,
} from '../workspaceModel';
import { approachView } from './approach';
import { configurationsView } from './configurations';
import { evidenceView } from './evidence';
import { modelView } from './model';
import { overviewView } from './overview';
import { runsView } from './runs';

/** Session features a view may require before it is offered. Every study view is available
 * with no feature today; a view added later states the feature it needs. */
export type ViewCapabilities = { readonly features: ReadonlySet<string> };

/** Where a view appears in the study shell: a study tab with its label and position, or a
 * view reached by links only, shown under the tab it belongs to. */
export type ViewPlacement =
  | { readonly kind: 'tab'; readonly label: string; readonly position: number }
  | { readonly kind: 'link'; readonly tab: WorkspaceView; readonly breadcrumb: string };

/** What a view's editor guard reads: the shell's guard slots and the editors' dirty state. */
export type GuardContext = {
  view: WorkspaceView;
  study: Study | null;
  approach: ApproachController;
  approachEditing: boolean;
  approachEditingRef: RefObject<boolean>;
  setApproachEditing: Dispatch<SetStateAction<boolean>>;
  setApproachEditEpoch: Dispatch<SetStateAction<number>>;
  portPasteSlot: GuardSlot<EditorGuard>;
  editorSlot: GuardSlot<EditorHandle>;
  metadataDirty: boolean;
  saveMetadata: () => Promise<void>;
  setCurrentStudy: (value: Study) => void;
  evidenceSlot: GuardSlot<EditorGuard>;
  configurationSlot: GuardSlot<ConfigurationHandle>;
};

type Setter<T> = Dispatch<SetStateAction<T>>;
type PortRef = { instance_id: string; port_id: string };
export type SourceReturn = {
  view: WorkspaceView;
  link: string;
  context: WorkspaceContext | null;
  selection: Selection;
  run: PublicRun | null;
  runId: string;
  output: PortRef;
};
export type CaseReturn = { link: WorkspaceLink; key: string };
export type RequestedCase = { approach?: string; id: string; token: number };
export type StudyMetadata = { name: string; description: string; boundary: string };

/** The shell values a study view renders from. Views read and call these; the shell owns the
 * state, the navigation through the editor guards and the requests' generation checks. */
export type ViewContext = GuardContext & {
  study: Study;
  api: HyprnMvpApi;
  guards: GuardEntry[];
  dirty: boolean;
  busy: boolean;
  loading: boolean;
  error: unknown;
  notice: string;
  generation: RefObject<number>;
  navigate: (action: () => void) => void;
  perform: (action: () => Promise<void>) => Promise<void>;
  openLink: (target: WorkspaceLink, keepCaseReturn?: boolean) => Promise<void>;
  link: (value: WorkspaceLink) => void;
  clearEditor: () => void;
  select: (value: Selection) => void;
  selection: Selection;
  setSelection: Setter<Selection>;
  setView: Setter<WorkspaceView>;
  setContext: Setter<WorkspaceContext | null>;
  // Overview
  metadata: StudyMetadata;
  setMetadata: Setter<StudyMetadata>;
  approachEntry: RefObject<HTMLButtonElement | null>;
  // Approach
  approachReturn: WorkspaceLink | null;
  setApproachReturn: Setter<WorkspaceLink | null>;
  caseReturn: CaseReturn | null;
  returnFromCase: () => void;
  requestedCase: RequestedCase | undefined;
  setRequestedCase: Setter<RequestedCase | undefined>;
  requestedApproach: string | undefined;
  setRequestedApproach: Setter<string | undefined>;
  approachEditEpoch: number;
  approachHandoff: ApproachHandoff | null;
  setApproachHandoff: Setter<ApproachHandoff | null>;
  returnToApproachEntry: RefObject<boolean>;
  newConfiguration: (
    modelId: string,
    exact?: ModelRevisionRead4,
    approachSelection?: ApproachSelection1,
  ) => Promise<void>;
  // Models
  models: Array<{ model_id: string; name: string }>;
  model: ModelDraftRead4 | null;
  setModel: Setter<ModelDraftRead4 | null>;
  revision: ModelRevisionRead4 | null;
  setRevision: Setter<ModelRevisionRead4 | null>;
  revisions: RevisionSummary[];
  selectedModel: string;
  creatingModel: boolean;
  setCreatingModel: Setter<boolean>;
  creationGuidance: ReturnType<typeof useUnitCatalog>;
  newModel: string;
  setNewModel: Setter<string>;
  template: 'empty' | 'two_component_example';
  setTemplate: Setter<'empty' | 'two_component_example'>;
  chooseModel: (mid: string) => Promise<void>;
  currentModel: (value: ModelDraftRead4) => void;
  modelVersions: ModelController;
  setNotice: Setter<string>;
  setRevisions: Setter<RevisionSummary[]>;
  modelActionHost: HTMLDivElement | null;
  setModelActionHost: Setter<HTMLDivElement | null>;
  setResourceActions: Setter<HTMLDivElement | null>;
  // The displayed model version and its projections (Models, configuration, Run › Model)
  displayedSnapshot: ModelDraftRead4 | ModelRevisionRead4 | null | undefined;
  variableContext: VariableContext;
  frozenEvidence: EvidenceSnapshot[];
  methods: MethodLinks;
  openMethodStep: (link: MethodLink) => void;
  // Configurations
  configuration: FrozenConfigurationRead7 | null;
  configurations: FrozenConfigurationRead7[];
  configInspection: ConfigurationInspection | null;
  setConfigInspection: Setter<ConfigurationInspection | null>;
  modified: { seed: ModifiedRunSeedRead6; source: ConfigurationRevision } | null;
  initialConfigurationRevision: ModelRevisionRead4 | null;
  initialConfigurationApproach: ApproachSelection1 | null;
  choosingConfiguration: boolean;
  setChoosingConfiguration: Setter<boolean>;
  chooseConfigurationModel: () => Promise<void>;
  chooseView: (next: WorkspaceView) => void;
  copyRunConfiguration: (
    config: ConfigurationRevision,
    snapshot: ModelRevisionRead4,
  ) => Promise<void>;
  pendingCopy: RefObject<{
    configuration: ConfigurationRevision;
    snapshot: ModelRevisionRead4;
  } | null>;
  evidence: EvidenceRecord[];
  setEvidence: Setter<EvidenceRecord[]>;
  submitConfiguration: (configurationId: string) => Promise<void>;
  viewSourceResult: (runId: string, output: PortRef) => Promise<void>;
  sourceReturn: SourceReturn | null;
  activeRun: boolean;
  // Runs
  returnToConfiguration: () => void;
  runFilters: RunFilters;
  setRunFilters: Setter<RunFilters>;
  runListEpoch: number;
  submitted: PublicRun | null;
  setActiveRun: Setter<boolean>;
  runInspection: PublicRunDetail | null;
  setRunInspection: Setter<PublicRunDetail | null>;
  createModified: (seed: ModifiedRunSeedRead6, source: ConfigurationRevision) => void;
};

/** One study view of the closed registry. `parseLink` holds the view's own link rules,
 * `banner` renders directly below the study tabs, `render` renders the view's page (a view
 * whose content stays mounted while hidden renders its hidden container on every view),
 * `guard` lists the view's unsaved-changes entries and `available` says whether the session
 * may open it. */
export type ViewEntry<Name extends WorkspaceView = WorkspaceView> = {
  readonly name: Name;
  readonly placement: ViewPlacement;
  readonly parseLink: ViewLinkRules;
  readonly banner?: (ctx: ViewContext) => ReactNode;
  readonly render: (ctx: ViewContext) => ReactNode;
  readonly guard?: (ctx: GuardContext) => GuardEntry[];
  readonly available: (capabilities: ViewCapabilities) => boolean;
};

// Exactly one entry per workspace view name: the names form a closed type.
const entries: { readonly [Name in WorkspaceView]: ViewEntry<Name> } = {
  overview: overviewView,
  approach: approachView,
  model: modelView,
  configurations: configurationsView,
  runs: runsView,
  evidence: evidenceView,
};

/** The study views in page order (the order their content is rendered in). */
export const viewRegistry: readonly ViewEntry[] = Object.freeze([
  entries.overview,
  entries.approach,
  entries.model,
  entries.configurations,
  entries.runs,
  entries.evidence,
]);

/** Save and discard order of the views' unsaved-changes entries: the approach editors, the
 * model editors, the study metadata, evidence, then the configuration draft. */
export const guardOrder: readonly WorkspaceView[] = Object.freeze([
  'approach',
  'model',
  'overview',
  'evidence',
  'configurations',
]);

/** The capabilities of the signed-in session: no view needs a feature today. */
export const sessionCapabilities: ViewCapabilities = Object.freeze({ features: new Set<string>() });

export const viewEntry = (name: WorkspaceView): ViewEntry => entries[name];

/** The available view with this exact name, or undefined (never an inherited property). */
function availableView(name: string, capabilities: ViewCapabilities) {
  const entry = viewRegistry.find((candidate) => candidate.name === name);
  return entry?.available(capabilities) ? entry : undefined;
}

/** Parses a workspace link with the rules of the view it names. */
export function parseViewLink(hash: string, capabilities: ViewCapabilities = sessionCapabilities) {
  return parseWorkspaceLink(hash, (name) => availableView(name, capabilities));
}

/** The unsaved-changes list of every view, in save and discard order. */
export function viewGuards(ctx: GuardContext): GuardEntry[] {
  return guardOrder.flatMap((name) => entries[name].guard?.(ctx) ?? []);
}

/** The study tabs, in position order, of the views available to the session. */
export function studyTabs(capabilities: ViewCapabilities = sessionCapabilities) {
  return viewRegistry
    .flatMap((entry) =>
      entry.placement.kind === 'tab' && entry.available(capabilities)
        ? [{ id: entry.name, label: entry.placement.label, position: entry.placement.position }]
        : [],
    )
    .sort((a, b) => a.position - b.position)
    .map(({ id, label }) => ({ id, label }));
}

/** The study tab that is selected while `view` is shown. */
export function selectedTab(view: WorkspaceView): WorkspaceView {
  const placement = entries[view].placement;
  return placement.kind === 'tab' ? view : placement.tab;
}

/** The breadcrumb section name of `view`. */
export function breadcrumbOf(view: WorkspaceView): string {
  const placement = entries[view].placement;
  return placement.kind === 'tab' ? placement.label : placement.breadcrumb;
}
