import { AttributionDetail, RecordAttribution } from './attribution';
import type { ApproachResolution } from './api';
import type { ApproachContent } from './api';
import { CaseNavigation, type WorkspaceLink } from './workspaceModel';
import { ApproachFindings } from './ApproachFindings';
import {
  ApproachAnnotations,
  StudyDetailsDialog,
  StudyQuestionBox,
  type ApproachHandoff,
  type StudyDetailsHandle,
} from './ApproachAssumptions';
import { useEffect, useId, useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import {
  Button,
  Panel,
  TextArea,
  TextInput,
  Select,
  DialogFrame,
  StatusTag,
  RecordState,
  ActionDialog,
} from './design';
import {
  ApproachMethod,
  ApproachCases,
  ApproachBasis,
  forgetMethodViews,
  rememberMethodStep,
} from './ApproachMethod';
import {
  HyprnMvpApi,
  accessLostText,
  accessUnverifiedText,
  message,
  descriptiveApproach,
  type ReadFence,
} from './api';
import { useAccessLoss } from './accessLoss';
import { ApproachController, useApproachController } from './ApproachController';
import type {
  ModelRevisionRead4,
  ApproachSelection1,
  ApproachSavedRead3,
  ApproachVersionSummaryRead2,
  ApproachCursor1,
} from './contract';

/** Method reading positions never outlive the session that read them. */
export function forgetApproachReading(studyId?: string) {
  forgetMethodViews(studyId);
}
/** The model view's "Open step n in modeling approach": the exact saved version opens
 * with that step expanded and focused. A reading position only; no data. */
export function showMethodStep(studyId: string, versionId: string | null, stepId: string) {
  const viewKey = versionId ? studyId + '/saved/' + versionId : studyId + '/draft/draft';
  rememberMethodStep(viewKey, stepId);
}
export type ApproachReadSource =
  | { kind: 'draft'; content: ApproachContent; resolved?: ApproachResolution }
  | { kind: 'saved' | 'retained'; record: ApproachSavedRead3 };

/** An explicit snapshot-only reader, also usable by retained history. It never
 * fetches today's model, evidence, usage or draft as a historical substitute. */
/** Live results for an exact saved version: one card per case (definition, runs and
 * configurations together). Study limits open the reader's Study details at Limits. */
export type ApproachResultsSlot = (slot: {
  answerId: string;
  casesId: string;
  focusCase?: { id: string; token: number };
  onViewStep: (stepId: string) => void;
  onStudyLimits?: () => void;
}) => ReactNode;

export function ApproachReader({
  source,
  presentation = 'full',
  onAccessLost,
  questionActions,
  detailsEditor,
  detailsActions,
  findings,
  focusCase,
  api,
  studyId,
  onChange,
  disabled,
  baseVersion,
  onHandoff,
  onOpenModel,
  onEditingChange,
  onCreateConfiguration,
}: {
  presentation?: 'full' | 'overview' | 'cases';
  onAccessLost?: () => void;
  onCreateConfiguration?: (caseId: string) => void;
  onEditingChange?: (dirty: boolean) => void;
  onOpenModel?: (id: string) => void;
  baseVersion?: string | null;
  onHandoff?: (value: ApproachHandoff) => void;
  source: ApproachReadSource;
  questionActions?: ReactNode;
  detailsEditor?: React.ComponentProps<typeof StudyDetailsDialog>['editor'];
  detailsActions?: ReactNode;
  findings?: ApproachResultsSlot;
  focusCase?: { id: string; token: number };
  api?: HyprnMvpApi;
  studyId?: string;
  onChange?: (content: ApproachContent) => void;
  disabled?: boolean;
}) {
  const sectionId = useId();
  const content = source.kind === 'draft' ? source.content : source.record.version.content;
  const resolved = source.kind === 'draft' ? source.resolved : source.record.closure;
  // Exact version (or current draft) keeps its own reading position across owner navigation.
  const viewKey =
    (studyId ?? '') +
    '/' +
    source.kind +
    '/' +
    (source.kind === 'draft' ? 'draft' : source.record.version.approach_version_id);
  const [requestedStep, setRequestedStep] = useState<{ id: string; token: number }>();
  const viewStep = (id: string) => {
    setRequestedStep((old) => ({ id, token: (old?.token ?? 0) + 1 }));
  };
  const details = useRef<StudyDetailsHandle>(null);
  const casesPanel = (
    <ApproachCases
      onCreateConfiguration={onCreateConfiguration}
      content={content}
      models={resolved?.models}
      onChange={onChange}
      disabled={disabled}
    />
  );
  const findingsContent = findings?.({
    answerId: sectionId + '-answer', casesId: sectionId + '-cases', focusCase,
    onViewStep: viewStep,
    onStudyLimits: () => details.current?.open('limits'),
  });
  // Retained and draft readers never navigate to live case usage.
  return (
    <CaseNavigation.Provider value={null}>
      <ApproachAnnotations
        onAccessLost={onAccessLost}
        contextLabel={
          source.kind === 'draft'
            ? 'Current approach draft'
            : 'Saved approach v' + source.record.version.version_number
        }
        api={source.kind === 'draft' ? api : undefined}
        studyId={studyId}
        content={content}
        resolved={resolved}
        onChange={onChange}
        disabled={disabled}
        onEditingChange={onEditingChange}
        baseVersion={baseVersion}
        onHandoff={onHandoff}
        onOpenModel={onOpenModel}
      >
        <div role="region" aria-label="The modeling approach">
          {presentation !== 'cases' && (
            <StudyQuestionBox
              question={content.question}
              scope={content.scope}
              headingId={sectionId + '-question'}
              onDetails={() => details.current?.open()}
              actions={
                <>
                  {questionActions}
                  {source.kind === 'retained' && (
                    <ActionDialog title="Earlier work">
                      <ApproachBasis
                        closure={source.record.closure}
                        content={content}
                        resolved={resolved}
                      />
                    </ActionDialog>
                  )}
                </>
              }
            />
          )}
          <StudyDetailsDialog ref={details} editor={detailsEditor} actions={detailsActions} />
          {presentation !== 'full' && findingsContent}
          {presentation !== 'cases' && (
            <Panel
              className="approach-section"
              id={sectionId + '-methods'}
              label="Reasoning and methods"
              title="Reasoning and methods"
              headingLevel={3}
            >
              <ApproachMethod
                key={viewKey}
                viewKey={viewKey}
                version={
                  source.kind === 'draft'
                    ? null
                    : {
                        id: source.record.version.approach_version_id,
                        number: source.record.version.version_number,
                      }
                }
                requestedStep={requestedStep}
                onOpenModel={onOpenModel}
                api={source.kind === 'draft' ? api : undefined}
                studyId={studyId}
                content={content}
                resolved={resolved}
                onChange={onChange}
                disabled={disabled}
              />
            </Panel>
          )}
          {presentation === 'full' &&
            (findings ? (
              findingsContent
            ) : (
              <>
                <Panel
                  className="approach-section"
                  id={sectionId + '-cases'}
                  label="Cases"
                  title="Cases"
                  headingLevel={3}
                >
                  {casesPanel}
                </Panel>
                <Panel
                  id={sectionId + '-answer'}
                  className="approach-section approach-results"
                  label="Answer to the study question"
                  title="Answer to the study question"
                >
                  <h3 className="approach-results-answer">
                    {source.kind === 'draft'
                      ? 'No study answer has been assessed.'
                      : 'Scientific answers are not included in this historical record.'}
                  </h3>
                  <p className="context-line">
                    {source.kind === 'draft'
                      ? 'Save an approach version to connect configurations and runs ' +
                        'to this explanation.'
                      : 'Results belong to the configurations and runs that used this version. ' +
                        'This view shows its explanation only.'}
                  </p>
                </Panel>
              </>
            ))}
        </div>
      </ApproachAnnotations>
    </CaseNavigation.Provider>
  );
}
export function ApproachPanel({ requestedCase, api, controller, studyId, requestedVersion, navigate, onSelection, onBack, onHandoff, onOpenModel, onEditingChange, onCreateConfiguration, onOpenRecord }: { onCreateConfiguration?:(model:ModelRevisionRead4,selection:ApproachSelection1)=>void;onOpenRecord?:(target:WorkspaceLink)=>void; requestedCase?: { id: string; token: number }; onEditingChange?: (dirty: boolean) => void; onOpenModel?: (id: string) => void; onHandoff?: (value: ApproachHandoff) => void; api: HyprnMvpApi; controller: ApproachController; studyId: string; requestedVersion?: string; navigate: (action: () => void) => void; onSelection: (id?: string) => void; onBack: () => void }) {
  const state = useApproachController(controller);
  const [editing,setEditing]=useState(false);
  const [questionOpen,setQuestionOpen]=useState(false),[annotationEditing,setAnnotationEditing]=useState(false),[basisEditing,setBasisEditing]=useState(false);
  const [creating, setCreating] = useState(false), [versions, setVersions] = useState<ApproachVersionSummaryRead2[]>([]), [cursor, setCursor] = useState<ApproachCursor1 | null>(null);
  const [listError, setListError] = useState('');
  const editor = useRef<HTMLDialogElement>(null), versionDialog = useRef<HTMLDialogElement>(null), restoreDialog = useRef<HTMLDialogElement>(null);
  const beforeEdit = useRef<ApproachContent | null>(null), invoker = useRef<HTMLElement | null>(null);
  const versionId = state.saved?.version.approach_version_id ?? requestedVersion;
  const attributionKind = state.saved ? 'approach_version' : 'approach_draft';
  const attributionId = state.accessLost
    ? null
    : state.saved?.version.approach_version_id ??
      (controller.dirty ? null : state.server?.draft?.revision);
  const locked = controller.busy || !!api.pending || state.status === 'uncertain';
  // `guard` is the latest-list token (display only). Denial is confirmed against the
  // shared session fence, so a version switch cannot discard it.
  const guard = useRef(0);
  // Study whose protected approach content was cleared by a confirmed denial: no
  // automatic re-read and no retained version labels until an explicit choice or retry.
  const [lostStudy,setLostStudy]=useState<string|null>(null),lost=lostStudy===studyId;
  function clearProtectedApproach(){
    guard.current++;setVersions([]);setCursor(null);setEditing(false);setLostStudy(studyId);
    setListError(accessLostText);controller.loseAccess(studyId);forgetApproachReading(studyId);
  }
  // Confirmed denial from this page, its Findings, its annotations or any other host.
  useAccessLoss(api,studyId,change=>{if(change.kind==='access-lost')clearProtectedApproach();});
  async function versionReadFailed(error:unknown,read:ReadFence,latest:()=>boolean){
    const outcome=await api.readFailed(error,read);
    if(outcome==='transient'&&latest())setListError(accessUnverifiedText);
    else if(outcome==='error'&&latest())setListError(message(error));
  }
  useEffect(() => { if(lost)return; const token=++guard.current,read=api.fence({studyId}),latest=()=>token===guard.current;
    const apply=()=>read.valid()&&latest()&&controller.getSnapshot().studyId===studyId;
    setListError('');setVersions([]);setCursor(null);
    api.approachVersions(studyId,{},read.signal).then(page=>{if(apply()){setVersions(page.items);setCursor(page.next_cursor);}}).catch(error=>void versionReadFailed(error,read,latest)).finally(read.done);
    return()=>{read.abort();guard.current++;};
  },[api,studyId,versionId,lost]);
  function loadMoreVersions(){
    if(!cursor)return;
    const token=guard.current,read=api.fence({studyId}),latest=()=>token===guard.current;
    const apply=()=>read.valid()&&latest()&&controller.getSnapshot().studyId===studyId;
    setListError('');
    void api.approachVersions(studyId,{cursor},read.signal).then(page=>{if(apply()){setVersions(old=>[...old,...page.items]);setCursor(page.next_cursor);}}).catch(error=>void versionReadFailed(error,read,latest)).finally(read.done);
  }
  /** An explicit choice or retry reads again; a remaining denial is confirmed again. */
  function readAgain(versionId?:string){setLostStudy(null);void controller.open(studyId,versionId);}
  useEffect(() => { if (state.status === 'ready') onSelection(state.saved?.version.approach_version_id); }, [state.status, versionId]);
  useEffect(() => { document.getElementById('approach-heading')?.focus(); }, [studyId]);
  const close = (dialog: HTMLDialogElement | null) => { dialog?.close(); invoker.current?.focus(); };
  const show = (dialog: HTMLDialogElement | null) => { invoker.current = document.activeElement as HTMLElement; dialog?.showModal(); dialog?.querySelector<HTMLElement>('textarea, [data-safe-choice], button')?.focus(); };
  const choose = (id?: string) => navigate(() => { setEditing(false); onSelection(id); readAgain(id); });
  const source: ApproachReadSource | null = state.accessLost ? null : state.saved ? { kind: 'saved', record: state.saved } : state.local ? { kind: 'draft', content: state.local, resolved: state.preview?.resolved } : null;
  const absent = !state.server?.draft && !state.saved && !creating && !controller.dirty;
  /** Create a configuration for one case of the exact saved version, with that version's retained model. */
  const createForCase = state.saved && onCreateConfiguration ? (caseId:string)=>{const saved=state.saved!;const item=saved.version.content.cases.find(c=>c.case_id===caseId);const binding=saved.version.content.model_bindings.find(b=>b.binding_id===item?.binding_id);const model=saved.closure.models.find(m=>m.model_revision_id===binding?.model_revision_id&&m.model_id===binding?.model_id);if(model)onCreateConfiguration(model,{approach_version_id:saved.version.approach_version_id,case_id:caseId});} : undefined;
  function beginEditing(){navigate(()=>{if(state.saved){void controller.open(studyId).then(ok=>{if(ok)setEditing(true);});}else setEditing(true);});}
  function beginEdit() { setQuestionOpen(true);beforeEdit.current = structuredClone(state.local); show(editor.current); }
  function cancelEdit() { setQuestionOpen(false);if (beforeEdit.current) controller.edit(beforeEdit.current); close(editor.current); }
  const questionDirty=questionOpen&&JSON.stringify(state.local)!==JSON.stringify(beforeEdit.current);
  useLayoutEffect(()=>{onEditingChange?.(questionDirty||annotationEditing||basisEditing);return()=>onEditingChange?.(false);},[questionDirty,annotationEditing,basisEditing]);
  return (
    <section className="approach-page" aria-labelledby="approach-heading">
      <div className="approach-topline">
        <Button className="link back-link" aria-label="Back to overview" onClick={onBack}>
          ← Overview
        </Button>
      </div>
      <div className="page-heading">
        <div>
          <h2 id="approach-heading" tabIndex={-1}>
            Modeling approach
          </h2>
        </div>
        <div className="section-actions">
          <Select
            aria-label="Approach version"
            value={lost ? 'draft' : (versionId ?? 'draft')}
            disabled={locked}
            onChange={(e) => choose(e.target.value === 'draft' ? undefined : e.target.value)}
          >
            <option value="draft">Draft</option>
            {versions.map((v) => (
              <option key={v.approach_version_id} value={v.approach_version_id}>
                v{v.version_number} (read-only)
              </option>
            ))}
            {!lost && versionId && !versions.some((v) => v.approach_version_id === versionId) && (
              <option value={versionId}>
                {state.saved ? `v${state.saved.version.version_number}` : 'Selected version'}{' '}
                (read-only)
              </option>
            )}
          </Select>
          {state.saved && <RecordAttribution kind={attributionKind} id={attributionId} />}
          {!absent &&
            !state.accessLost &&
            (editing && !state.saved ? (
              <>
                <Button disabled={locked} onClick={() => navigate(() => setEditing(false))}>
                  Leave editing
                </Button>
                <Button
                  variant={controller.dirty ? 'primary' : 'secondary'}
                  disabled={locked || !state.local || (!controller.dirty && !!state.server?.draft)}
                  onClick={() => void controller.save()}
                >
                  Save draft
                </Button>
                <Button
                  disabled={locked || controller.dirty || !state.server?.draft}
                  onClick={() => {
                    invoker.current = document.activeElement as HTMLElement;
                    void controller.preview().then((ok) => {
                      if (ok) {
                        versionDialog.current?.showModal();
                        versionDialog.current
                          ?.querySelector<HTMLButtonElement>('[data-safe-choice]')
                          ?.focus();
                      }
                    });
                  }}
                >
                  Save approach version
                </Button>
              </>
            ) : (
              <Button variant="primary" disabled={locked} onClick={beginEditing}>
                Edit approach
              </Button>
            ))}
          {source && !absent && (
            <ActionDialog title="Approach actions" label="…" triggerLabel="Approach actions">
              <div className="hf-action-list">
                <ActionDialog
                  title="Approach record"
                  label="Approach record details"
                  size="sm"
                  variant="quiet"
                >
                  <dl className="hf-record-details">
                    <AttributionDetail
                      kind={attributionKind}
                      id={attributionId}
                      label={state.saved ? 'Saved by' : 'Changed by'}
                    />
                  </dl>
                  <pre tabIndex={0}>
                    {JSON.stringify(state.saved ?? state.server?.draft, null, 2)}
                  </pre>
                </ActionDialog>
                <ActionDialog title="Earlier work">
                  <ApproachAnnotations
                    studyId={studyId}
                    content={
                      source.kind === 'draft' ? source.content : source.record.version.content
                    }
                    resolved={source.kind === 'draft' ? source.resolved : source.record.closure}
                    onChange={editing && state.local ? controller.edit : undefined}
                    disabled={locked}
                    onEditingChange={setBasisEditing}
                  >
                    <ApproachBasis
                      closure={source.kind === 'draft' ? undefined : source.record.closure}
                      api={editing ? api : undefined}
                      studyId={studyId}
                      content={
                        source.kind === 'draft' ? source.content : source.record.version.content
                      }
                      resolved={source.kind === 'draft' ? source.resolved : source.record.closure}
                      onChange={editing && state.local ? controller.edit : undefined}
                      disabled={locked}
                    />
                  </ApproachAnnotations>
                </ActionDialog>
                {state.saved && (
                  <Button
                    disabled={locked}
                    onClick={(e) => {
                      e.currentTarget.closest('dialog')?.close();
                      show(restoreDialog.current);
                    }}
                  >
                    Use this version in draft
                  </Button>
                )}
              </div>
            </ActionDialog>
          )}
        </div>
      </div>

      {state.local && !absent && (
        <div className="section-actions approach-draft-status">
          <p role="status">
            <RecordState
              state={controller.dirty ? 'changed' : state.server?.draft ? 'draft' : 'new'}
            />
          </p>
          {!state.saved && <RecordAttribution kind={attributionKind} id={attributionId} />}
          {editing &&
            state.local &&
            !!(
              state.local.assumptions.length ||
              state.local.steps.length ||
              state.local.cases.length ||
              state.local.basis_refs.length ||
              state.server?.draft?.content.basis_refs.length
            ) && (
              <Button disabled={locked} onClick={() => void controller.preview()}>
                {controller.dirty ? 'Review approach changes' : 'Load linked records'}
              </Button>
            )}
        </div>
      )}
      {controller.busy && (
        <p role="status">
          <StatusTag tone="running">
            {state.status === 'loading' ? 'Loading modeling approach…' : 'Resolving and saving…'}
          </StatusTag>
        </p>
      )}
      {state.error && (
        <div role="alert">
          <p>{state.error}</p>
          {!!state.diagnostics.length && (
            <ul>
              {state.diagnostics.map((issue, i) => (
                <li key={i}>
                  <p>{issue.message}</p>
                  <p className="context-line">
                    Field: <code>{issue.path}</code>
                  </p>
                </li>
              ))}
            </ul>
          )}
          {state.status === 'stale' && (
            <Button onClick={() => void controller.reviewLatest()}>Review latest draft</Button>
          )}
          {state.accessLost && controller.dirty && (
            <p>
              Your unsaved approach edits are kept but cannot be saved. Discard them to read the
              approach again.
            </p>
          )}
          {!source && (
            <Button
              onClick={() =>
                state.accessLost ? navigate(() => readAgain(versionId)) : readAgain(versionId)
              }
            >
              Retry this version
            </Button>
          )}
        </div>
      )}

      {state.preview && state.local && controller.dirty && (
        <Panel title="Approach changes">
          <ul>
            {state.preview.changes.map((change, i) => (
              <li key={i}>{change.description}</li>
            ))}
          </ul>
          <p>
            These edits change the explanation and its references. They do not modify or execute the
            referenced models.
          </p>
        </Panel>
      )}
      {!!state.preview?.issues.length && (
        <Panel title="References to review">
          <ul>
            {state.preview.issues.map((issue, i) => (
              <li role="alert" key={i}>
                <p>{issue.message}</p>
                <p className="context-line">
                  Field: <code>{issue.path}</code>
                </p>
              </li>
            ))}
          </ul>
        </Panel>
      )}
      {state.latest && (
        <Panel label="Review latest draft">
          <h3>Review latest draft</h3>
          <div className="approach-review">
            {(
              [
                { title: 'Your local explanation', content: state.local },
                { title: 'Latest saved explanation', content: state.latest.draft?.content },
              ] as const
            ).map((item) => (
              <div key={item.title}>
                <h4>{item.title}</h4>
                {(['question', 'scope', 'limitations', 'open_questions'] as const).map((key) => (
                  <div key={key}>
                    <h5>
                      {
                        {
                          question: 'Engineering question',
                          scope: 'Scope',
                          limitations: 'Limitations',
                          open_questions: 'Open questions',
                        }[key]
                      }
                    </h5>
                    <p className="context-copy">{item.content?.[key] || 'None'}</p>
                  </div>
                ))}
              </div>
            ))}
          </div>
          <p>
            Your local content will replace the latest draft only after another preview and save.
          </p>
          <Button disabled={locked} onClick={controller.reapplyToLatest}>
            Reapply my changes
          </Button>
        </Panel>
      )}
      {!source && !state.error && !controller.busy && (
        <div role="alert">
          <p>{lost ? accessLostText : 'This approach is unavailable in the current session.'}</p>
          <Button onClick={() => readAgain(versionId)}>Retry this version</Button>
        </div>
      )}
      {listError && <p role="alert">Versions could not be loaded. {listError}</p>}
      {cursor && <Button onClick={loadMoreVersions}>Load more versions</Button>}
      {source &&
        (absent ? (
          <Panel title="No modeling approach yet">
            <p>Describe the question and method before linking an implementation.</p>
            <Button
              variant="primary"
              disabled={locked}
              onClick={() => {
                setCreating(true);
                setEditing(true);
              }}
            >
              Create modeling approach
            </Button>
          </Panel>
        ) : (
          <ApproachReader
            onAccessLost={clearProtectedApproach}
            onCreateConfiguration={createForCase}
            findings={
              state.saved && onOpenRecord
                ? (slot) => (
                    <ApproachFindings
                      answerId={slot.answerId}
                      casesId={slot.casesId}
                      api={api}
                      studyId={studyId}
                      saved={state.saved!}
                      onOpen={onOpenRecord}
                      focusCase={slot.focusCase}
                      onViewStep={slot.onViewStep}
                      onCreateConfiguration={createForCase}
                    />
                  )
                : undefined
            }
            focusCase={
              state.saved &&
              requestedCase &&
              state.saved.version.approach_version_id === requestedVersion
                ? requestedCase
                : undefined
            }
            onEditingChange={setAnnotationEditing}
            onOpenModel={onOpenModel}
            baseVersion={
              state.server?.draft?.base_version_id ??
              state.server?.latest_version?.approach_version_id
            }
            onHandoff={onHandoff}
            source={source}
            api={api}
            studyId={studyId}
            onChange={editing && state.local ? controller.edit : undefined}
            disabled={locked}
            questionActions={
              editing &&
              state.local && (
                <Button disabled={locked} onClick={beginEdit}>
                  Edit question and scope
                </Button>
              )
            }
          />
        ))}
      <DialogFrame ref={editor} aria-labelledby="approach-edit-title" onCancel={cancelEdit}>
        <h2 id="approach-edit-title">Edit question and scope</h2>
        <form
          className="form-stack"
          onSubmit={(e) => {
            e.preventDefault();
            setQuestionOpen(false);
            close(editor.current);
          }}
        >
          {state.local &&
            (['question', 'scope', 'limitations', 'open_questions'] as const).map((key) => (
              <label key={key}>
                {
                  {
                    question: 'Engineering question',
                    scope: 'Scope',
                    limitations: 'Limitations',
                    open_questions: 'Open questions',
                  }[key]
                }
                <TextArea
                  aria-label={
                    {
                      question: 'Engineering question',
                      scope: 'Scope',
                      limitations: 'Limitations',
                      open_questions: 'Open questions',
                    }[key]
                  }
                  maxLength={4096}
                  value={state.local![key]}
                  onChange={(e) => controller.edit({ ...state.local!, [key]: e.target.value })}
                />
              </label>
            ))}
          {state.local &&
            (['original_question', 'elaboration'] as const).map((key) => {
              const content = descriptiveApproach(state.local!);
              const claim = content[key];
              const title =
                key === 'original_question' ? 'Original wording' : 'Detailed elaboration';
              return (
                <fieldset key={key}>
                  <legend>{title}</legend>
                  <p className="context-line">
                    {key === 'original_question'
                      ? 'Enter only wording that was actually supplied.'
                      : 'Keep elaboration separate from the agreed question.'}{' '}
                    Attribution is a supplied origin claim.
                  </p>
                  <label>
                    {title}
                    <TextArea
                      aria-label={title}
                      maxLength={4096}
                      value={claim?.text ?? ''}
                      onChange={(e) =>
                        controller.edit({
                          ...content,
                          [key]: {
                            text: e.target.value,
                            attribution: claim?.attribution ?? { kind: 'unknown', label: null },
                          },
                        })
                      }
                    />
                  </label>
                  <label>
                    {title} attribution
                    <Select
                      aria-label={title + ' attribution'}
                      value={claim?.attribution.kind ?? 'unknown'}
                      onChange={(e) => {
                        const kind = e.target.value;
                        if (kind === 'human' || kind === 'agent' || kind === 'unknown')
                          controller.edit({
                            ...content,
                            [key]: {
                              text: claim?.text ?? '',
                              attribution: { kind, label: claim?.attribution.label ?? null },
                            },
                          });
                      }}
                    >
                      <option value="unknown">Unknown</option>
                      <option value="human">Human (supplied claim)</option>
                      <option value="agent">Agent (supplied claim)</option>
                    </Select>
                  </label>
                  <label>
                    {title} attribution label
                    <TextInput
                      aria-label={title + ' attribution label'}
                      maxLength={256}
                      value={claim?.attribution.label ?? ''}
                      onChange={(e) =>
                        controller.edit({
                          ...content,
                          [key]: {
                            text: claim?.text ?? '',
                            attribution: {
                              kind: claim?.attribution.kind ?? 'unknown',
                              label: e.target.value || null,
                            },
                          },
                        })
                      }
                    />
                  </label>
                  {claim && (
                    <Button
                      type="button"
                      onClick={() => controller.edit({ ...content, [key]: null })}
                    >
                      Remove {title.toLowerCase()}
                    </Button>
                  )}
                </fieldset>
              );
            })}
          <div className="actions">
            <Button type="submit" variant="primary">
              Apply to draft
            </Button>
            <Button type="button" onClick={cancelEdit}>
              Cancel
            </Button>
          </div>
        </form>
      </DialogFrame>
      <DialogFrame
        ref={versionDialog}
        aria-labelledby="approach-version-title"
        onCancel={() => invoker.current?.focus()}
      >
        <h2 id="approach-version-title">Save approach version</h2>
        <p>Save this draft as a new approach version. Later edits stay in the draft.</p>
        {state.preview && (
          <p>
            {state.preview.coverage.proposed} proposed · {state.preview.coverage.partial} partially
            linked · {state.preview.coverage.linked} linked steps
          </p>
        )}
        <div className="actions">
          <Button
            variant="primary"
            disabled={locked}
            onClick={() => {
              close(versionDialog.current);
              void controller.saveVersion();
            }}
          >
            Save version
          </Button>
          <Button data-safe-choice onClick={() => close(versionDialog.current)}>
            Keep editing
          </Button>
        </div>
      </DialogFrame>
      <DialogFrame
        ref={restoreDialog}
        aria-labelledby="approach-restore-title"
        onCancel={() => invoker.current?.focus()}
      >
        <h2 id="approach-restore-title">Use this version in draft</h2>
        <p>
          Replace the saved draft with this version's content. Existing approach versions, models
          and evidence remain unchanged.
        </p>
        <div className="actions">
          <Button
            variant="primary"
            disabled={locked}
            onClick={() => {
              close(restoreDialog.current);
              if (versionId)
                void controller.restore(versionId).then((ok) => {
                  if (ok) setEditing(true);
                });
            }}
          >
            Restore draft
          </Button>
          <Button data-safe-choice onClick={() => close(restoreDialog.current)}>
            Keep current draft
          </Button>
        </div>
      </DialogFrame>
    </section>
  );
}
