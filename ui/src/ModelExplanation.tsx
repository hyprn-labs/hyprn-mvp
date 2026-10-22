import { DialogActions, FormActions } from './design';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import {
  ApiError,
  message,
  type EvidenceRecord,
  type HyprnMvpApi,
  type RevisionSummary,
} from './api';
import { AttributionDetail, RecordAttribution } from './attribution';
import type {
  ModelExplanationContent3,
  ModelExplanationStateRead3,
  ModelExplanationVersionRead3,
} from './contract';
import {
  ReadingSection,
  ReadingStack,
  Button,
  RecordState,
  PageHeader,
  RecordDetails,
  ActionDialog,
  FormField,
  VersionSelect,
  lineageVersions,
  StatusTag,
  TextArea,
} from './design';
import {
  currentDocumentation,
  documentationChanged,
  onDocumentationChange,
} from './modelDocumentation';
import { MonetaryBasisEditor, MonetaryBasisReader } from './MonetaryBasis';
import { useUnitCatalog, UnitGuidance } from './UnitEditor';
import { EvidencePicker } from './EvidencePicker';
import { evidenceTitle, EvidenceList } from './EvidenceView';
import type { Snapshot } from './GraphView';
import { cleanGuard, type EditorGuard } from './workspaceModel';

const EMPTY: ModelExplanationContent3 = {
  schema_version: '3',
  monetary_quantities: [],
  limits: '',
  component_details: [],
  represents: '',
  basis: '',
  calculation_logic: '',
  components: [],
  evidence_links: [],
};
const TEXTS = [
  ['represents', 'Description'],
  ['basis', 'Basis and reasoning'],
  ['calculation_logic', 'Calculation logic'],
  ['limits', 'Limits'],
] as const;
const RELATIONS = { supports: 'Supports', challenges: 'Challenges', context: 'Context' } as const;

type Loaded =
  | { kind: 'loading' }
  | { kind: 'failed'; error: string }
  | { kind: 'draft'; state: ModelExplanationStateRead3 }
  | {
      kind: 'version';
      state: ModelExplanationStateRead3;
      saved: ModelExplanationVersionRead3 | null;
    };

/** Component names come from the displayed model; an explanation of a definition version
 * names every component that uses it. Identity is never inferred from a name. */
function componentName(snapshot: Snapshot, item: ModelExplanationContent3['components'][number]) {
  if (item.kind === 'instance')
    return (
      snapshot.instances.find((i) => i.instance_id === item.instance_id)?.name ??
      'Component unavailable in this model version'
    );
  const users = snapshot.instances.filter(
    (i) => i.definition_version_id === item.definition_version_id,
  );
  return `Shared definition${users.length ? ` · ${users.map((i) => i.name).join(', ')}` : ''}`;
}

/** Read only authored sections; source identities are exact, never current replacements. */
function ExplanationReader({
  content,
  snapshot,
  evidence,
}: {
  content: ModelExplanationContent3;
  snapshot: Snapshot;
  evidence: EvidenceRecord[];
}) {
  return (
    <ReadingStack>
      {TEXTS.filter(([key]) => content[key].trim()).map(([key, heading]) => (
        <ReadingSection key={key} aria-label={heading}>
          <h4>{heading}</h4>
          <p className="context-copy">{content[key]}</p>
        </ReadingSection>
      ))}
      {!!content.monetary_quantities.length && (
        <MonetaryBasisReader
          snapshot={snapshot}
          items={content.monetary_quantities}
          evidence={evidence}
        />
      )}
      {!!content.components.length && (
        <ReadingSection aria-label="Component explanations">
          <h4>Component explanations</h4>
          <ul>
            {content.components.map((item) => (
              <li
                key={
                  item.kind +
                  (item.kind === 'instance' ? item.instance_id : item.definition_version_id)
                }
              >
                <strong>{componentName(snapshot, item)}</strong>: {item.explanation}
              </li>
            ))}
          </ul>
        </ReadingSection>
      )}
      {!!content.evidence_links.length && (
        <ReadingSection aria-label="Explanation evidence">
          <EvidenceList
            records={evidence}
            ids={content.evidence_links.map((link) => link.evidence_version_id)}
            links={content.evidence_links}
          />
        </ReadingSection>
      )}
    </ReadingStack>
  );
}

/** The selected model determines draft or exact immutable explanation reading.
 * Publication requires an explicit target and never replaces an existing explanation. */
export function ModelExplanation({
  api,
  studyId,
  modelId,
  revisionId,
  revisions,
  snapshot,
  editable,
  onHandle,
}: {
  api: HyprnMvpApi;
  studyId: string;
  modelId: string;
  /** The displayed saved model version, or null for the draft. */
  revisionId: string | null;
  revisions: RevisionSummary[];
  snapshot: Snapshot;
  editable: boolean;
  onHandle?: (handle: EditorGuard) => void;
}) {
  const [loaded, setLoaded] = useState<Loaded>({ kind: 'loading' });
  const [form, setForm] = useState<ModelExplanationContent3 | null>(null);
  const guidance = useUnitCatalog(api, form ? studyId : '', modelId);
  const [evidence, setEvidence] = useState<EvidenceRecord[]>([]);
  const [picker, setPicker] = useState(false);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState('');
  const [stale, setStale] = useState(false);
  const [chosen, setChosen] = useState('');
  const [publication, setPublication] = useState<{
    id: string;
    kind: 'available' | 'exists' | 'failed';
  } | null>(null);
  const [completion, setCompletion] = useState(0);
  const [retryPublication, setRetryPublication] = useState(0);
  const target = revisionId ?? chosen;
  useEffect(() => {
    if (!form || !target) return;
    const fence = api.fence({ studyId });
    setPublication(null);
    void api
      .modelVersionExplanation(studyId, modelId, target, fence.signal)
      .then((value) => {
        if (fence.valid())
          setPublication({ id: target, kind: value.explanation ? 'exists' : 'available' });
      })
      .catch(async (error) => {
        await api.readFailed(error, fence);
        if (fence.valid()) setPublication({ id: target, kind: 'failed' });
      })
      .finally(() => fence.done());
    return () => {
      fence.abort();
      fence.done();
    };
  }, [api, api.actor, studyId, modelId, target, !!form, retryPublication]);
  const editButton = useRef<HTMLButtonElement>(null);
  const generation = useRef(0);
  const handle = useRef<EditorGuard>(cleanGuard());
  useEffect(() => {
    onHandle?.(handle.current);
  });
  useEffect(
    () => () => {
      onHandle?.(cleanGuard());
    },
    [],
  );
  useEffect(
    () =>
      api.onSessionChange((change) => {
        if (
          change.kind === 'signed-out' ||
          (change.kind === 'access-lost' && change.studyId === studyId)
        ) {
          generation.current++;
          setEvidence([]);
          setLoaded({ kind: 'failed', error: 'Access to this model is no longer available.' });
          setForm(null);
          handle.current = cleanGuard();
        }
      }),
    [api, studyId],
  );

  // Leaving the editor after a save returns focus to the control that opened it.
  const returnFocus = useRef(false);
  useEffect(() => {
    if (returnFocus.current && !form && !working && loaded.kind === 'draft') {
      returnFocus.current = false;
      editButton.current?.focus();
    }
  }, [form, working, loaded]);

  /** A refresh keeps the shown explanation until the new read answers. */
  async function load(refresh = false) {
    const token = ++generation.current;
    if (!refresh) setLoaded({ kind: 'loading' });
    const fence = api.fence({ studyId });
    try {
      const state = await api.modelExplanation(studyId, modelId, fence.signal);
      const saved = revisionId
        ? (await api.modelVersionExplanation(studyId, modelId, revisionId, fence.signal))
            .explanation
        : null;
      if (token !== generation.current || !fence.valid()) return;
      const content = revisionId ? saved?.content : state.draft?.content;
      const attached = await Promise.all(
        [
          ...(content?.evidence_links ?? []),
          ...(content && 'monetary_quantities' in content
            ? content.monetary_quantities.flatMap((item) => item.evidence_links)
            : []),
        ].map(async (link) => {
          try {
            return await api.evidenceVersion(studyId, link.evidence_version_id, fence.signal);
          } catch (error) {
            await api.readFailed(error, fence);
            return null;
          }
        }),
      );
      if (token !== generation.current || !fence.valid()) return;
      setEvidence(attached.filter((record): record is EvidenceRecord => record !== null));
      setLoaded(revisionId ? { kind: 'version', state, saved } : { kind: 'draft', state });
    } catch (e) {
      const outcome = await api.readFailed(e, fence);
      if (token === generation.current && outcome !== 'access-lost')
        setLoaded({
          kind: 'failed',
          error: 'The model explanation could not be loaded. ' + message(e),
        });
    } finally {
      fence.done();
    }
  }
  useEffect(() => {
    void load();
    return () => {
      generation.current++;
    };
  }, [api, api.actor, studyId, modelId, revisionId]);

  useEffect(
    () =>
      onDocumentationChange(api, modelId, () => {
        if (!form) void load(true);
      }),
    [api, modelId, !!form],
  );

  if (loaded.kind === 'loading') return <p role="status">Loading model explanation…</p>;
  if (loaded.kind === 'failed')
    return (
      <div role="alert">
        <p>{loaded.error}</p>
        <Button onClick={() => void load()}>Retry model explanation</Button>
      </div>
    );
  const { state } = loaded;
  const draft = state.draft;
  const changed =
    !!form && JSON.stringify(form) !== JSON.stringify(currentDocumentation(draft?.content));
  const canPublish = publication?.id === target && publication.kind === 'available';

  async function run(action: () => Promise<void>) {
    setWorking(true);
    setError('');
    setStale(false);
    try {
      await action();
      return true;
    } catch (e) {
      setStale(e instanceof ApiError && e.detail.code === 'stale_revision');
      setError(
        e instanceof ApiError && e.detail.code === 'stale_revision'
          ? 'The explanation draft changed since it was loaded. ' +
              'Your edits are kept; load the latest draft to compare.'
          : e instanceof ApiError && e.detail.code === 'reference_conflict'
            ? 'This model version already has an explanation. ' +
              'Save a new model version to explain it anew.'
            : e instanceof ApiError && e.detail.fields.length
              ? 'The explanation was not saved. ' + e.detail.fields.map((f) => f.message).join(' ')
              : 'The explanation was not saved. ' + message(e),
      );
      return false;
    } finally {
      setWorking(false);
    }
  }
  const saveDraft = () =>
    run(async () => {
      if (!form) return;
      const components = form.components.filter((c) => c.explanation.trim());
      await api.saveModelExplanationDraft(studyId, modelId, {
        command_id: crypto.randomUUID(),
        expected_revision: draft?.revision ?? null,
        content: { ...form, components },
      });
      documentationChanged(api, modelId);
      returnFocus.current = true;
      setForm(null);
      await load(true);
    });
  const saveVersion = () =>
    run(async () => {
      if (!form || !target || !canPublish) return;
      let prepared = draft;
      if (!prepared || changed) {
        prepared = await api.saveModelExplanationDraft(studyId, modelId, {
          command_id: crypto.randomUUID(),
          expected_revision: draft?.revision ?? null,
          content: {
            ...form,
            components: form.components.filter((item) => item.explanation.trim()),
          },
        });
        // A failed publication must retain the acknowledged draft's compare-and-swap token.
        setLoaded((previous) =>
          previous.kind === 'draft' || previous.kind === 'version'
            ? { ...previous, state: { ...previous.state, draft: prepared! } }
            : previous,
        );
      }
      await api.saveModelExplanationVersion(studyId, modelId, {
        command_id: crypto.randomUUID(),
        expected_revision: prepared.revision,
        model_revision_id: target,
      });
      setCompletion((value) => value + 1);
      returnFocus.current = true;
      setForm(null);
      setChosen('');
      await load(true);
    });

  handle.current = {
    dirty:
      working ||
      (!!form && JSON.stringify(form) !== JSON.stringify(currentDocumentation(draft?.content))),
    save: async () => {
      if (working || api.pending) return false;
      return form ? saveDraft() : true;
    },
    discard: () => {
      setForm(null);
      setPicker(false);
    },
  };

  const publicationDialog = (
    <ActionDialog
      title="Save explanation version"
      label="Save for model version"
      completionKey={completion}
      disabled={working || !!api.pending}
    >
      {revisionId ? (
        <p>Save this explanation for the model version currently open.</p>
      ) : (
        <FormField label="Model version">
          <VersionSelect
            label="Model version to explain"
            showLabel={false}
            value={chosen}
            disabled={working}
            onChange={setChosen}
            placeholder="Choose a model version"
            versions={lineageVersions(
              revisions.map((item) => ({
                id: item.model_revision_id,
                parent: item.parent_model_revision_id,
              })),
            )}
          />
        </FormField>
      )}
      <p>
        Review the explanation against this model version before saving. Its saved explanation
        cannot be replaced.
      </p>
      {!revisions.length && !revisionId && <p>Save a model version first.</p>}
      {target && publication?.id !== target && <p role="status">Checking model version…</p>}
      {publication?.id === target && publication.kind === 'exists' && (
        <p>This version already has an explanation. Choose another model version.</p>
      )}
      {publication?.id === target && publication.kind === 'failed' && (
        <>
          <p role="alert">Could not check this model version.</p>
          <Button onClick={() => setRetryPublication((value) => value + 1)}>
            Retry model version check
          </Button>
        </>
      )}
      <DialogActions
        primary={
          <Button
            variant="primary"
            disabled={working || !!api.pending || !canPublish}
            onClick={() => void saveVersion()}
          >
            Save explanation version
          </Button>
        }
      />
      {error && <p role="alert">{error}</p>}
    </ActionDialog>
  );
  let body: ReactNode;
  if (form) {
    const instanceText = (id: string) =>
      form.components.find((c) => c.kind === 'instance' && c.instance_id === id)?.explanation ?? '';
    const setInstanceText = (id: string, explanation: string) =>
      setForm({
        ...form,
        components: [
          ...form.components.filter((c) => !(c.kind === 'instance' && c.instance_id === id)),
          { kind: 'instance', instance_id: id, explanation },
        ],
      });
    body = (
      <fieldset className="form-stack" disabled={working} aria-label="Edit model explanation draft">
        {TEXTS.map(([key, heading]) => (
          <FormField key={key} label={heading} optional>
            <TextArea
              aria-label={heading}
              maxLength={16384}
              value={form[key]}
              onChange={(e) => setForm({ ...form, [key]: e.target.value })}
            />
          </FormField>
        ))}
        <UnitGuidance guidance={guidance} />
        <MonetaryBasisEditor
          snapshot={snapshot}
          items={form.monetary_quantities}
          evidence={evidence}
          catalog={guidance.catalog}
          api={api}
          studyId={studyId}
          onChange={(items) => setForm({ ...form, monetary_quantities: items })}
          onEvidence={(records) =>
            setEvidence((known) => [
              ...known.filter((k) => !records.some((r) => r.evidence_id === k.evidence_id)),
              ...records,
            ])
          }
        />
        <h4>Component explanations</h4>
        {snapshot.instances
          .filter((i) => i.instance_id !== snapshot.root_instance_id)
          .map((instance) => (
            <FormField
              key={instance.instance_id}
              label={`Component explanation · ${instance.name}`}
              optional
            >
              <TextArea
                aria-label={`Component explanation · ${instance.name}`}
                maxLength={4096}
                value={instanceText(instance.instance_id)}
                onChange={(e) => setInstanceText(instance.instance_id, e.target.value)}
              />
            </FormField>
          ))}
        <h4>Evidence</h4>
        {form.evidence_links.length ? (
          <ul>
            {form.evidence_links.map((link) => (
              <li key={link.evidence_version_id + link.relation}>
                <StatusTag>{RELATIONS[link.relation]}</StatusTag>{' '}
                {evidence.find((e) => e.evidence_version_id === link.evidence_version_id)
                  ? evidenceTitle(
                      evidence.find((e) => e.evidence_version_id === link.evidence_version_id)!,
                    )
                  : 'Evidence'}{' '}
                <Button
                  variant="quiet"
                  size="sm"
                  onClick={() =>
                    setForm({
                      ...form,
                      evidence_links: form.evidence_links.filter((l) => l !== link),
                    })
                  }
                >
                  Remove evidence
                </Button>
              </li>
            ))}
          </ul>
        ) : (
          <p>No evidence linked yet.</p>
        )}
        <div className="section-actions">
          <Button onClick={() => setPicker(true)}>Add evidence</Button>
        </div>
        {picker && (
          <EvidencePicker
            api={api}
            studyId={studyId}
            ownerKey={'model-explanation/' + modelId}
            label="Model explanation"
            scope={null}
            assumption
            onRecords={(records) =>
              setEvidence((known) => [
                ...known.filter((k) => !records.some((r) => r.evidence_id === k.evidence_id)),
                ...records,
              ])
            }
            onClose={() => setPicker(false)}
            onAttach={(record, relation) => {
              if (!relation) return;
              setEvidence((known) => [
                ...known.filter((k) => k.evidence_id !== record.evidence_id),
                record,
              ]);
              if (
                !form.evidence_links.some(
                  (l) =>
                    l.evidence_version_id === record.evidence_version_id && l.relation === relation,
                )
              )
                setForm({
                  ...form,
                  evidence_links: [
                    ...form.evidence_links,
                    { evidence_version_id: record.evidence_version_id, relation },
                  ],
                });
              setPicker(false);
            }}
          />
        )}
        <FormActions
          primary={
            <Button
              variant="primary"
              disabled={working || !!api.pending}
              onClick={() => void saveDraft()}
            >
              Save draft
            </Button>
          }
        >
          <Button
            disabled={working}
            onClick={() => {
              returnFocus.current = true;
              setForm(null);
              setError('');
            }}
          >
            Cancel editing
          </Button>
          {publicationDialog}
        </FormActions>
      </fieldset>
    );
  } else {
    const content = loaded.kind === 'version' ? loaded.saved?.content : draft?.content;
    const hasContent =
      content &&
      (TEXTS.some(([key]) => currentDocumentation(content)[key].trim()) ||
        content.components.length ||
        currentDocumentation(content).monetary_quantities.length ||
        content.evidence_links.length);
    body = hasContent ? (
      <ExplanationReader
        content={currentDocumentation(content)}
        snapshot={snapshot}
        evidence={evidence}
      />
    ) : (
      <p>
        {loaded.kind === 'version'
          ? 'No explanation was saved for this model version.'
          : 'No model explanation yet.'}
      </p>
    );
  }
  const record = loaded.kind === 'version' ? loaded.saved : draft;
  const status = (
    <RecordState
      state={
        changed
          ? 'changed'
          : loaded.kind === 'version' && loaded.saved
            ? 'saved'
            : draft
              ? 'draft'
              : 'new'
      }
    />
  );
  const editableExplanation = editable && (loaded.kind === 'draft' || !loaded.saved);
  return (
    <section className="form-stack" aria-label="Application model explanation">
      <PageHeader
        level={3}
        title="Model explanation"
        help="modelExplanation"
        details={
          record ? (
            <RecordDetails
              kind="Model explanation"
              metadata={
                <>
                  {status}
                  <RecordAttribution
                    kind={
                      loaded.kind === 'version'
                        ? 'model_explanation_version'
                        : 'model_explanation_draft'
                    }
                    id={
                      'explanation_version_id' in record
                        ? record.explanation_version_id
                        : record.revision
                    }
                    inline
                  />
                </>
              }
            >
              <dl className="hf-record-details">
                <AttributionDetail
                  kind={
                    loaded.kind === 'version'
                      ? 'model_explanation_version'
                      : 'model_explanation_draft'
                  }
                  id={
                    'explanation_version_id' in record
                      ? record.explanation_version_id
                      : record.revision
                  }
                  label="Saved by"
                />
              </dl>
              <pre tabIndex={0} aria-label="Model explanation JSON">
                {JSON.stringify(record, null, 2)}
              </pre>
            </RecordDetails>
          ) : loaded.kind === 'version' && !form ? undefined : (
            status
          )
        }
        actions={
          !form && editableExplanation ? (
            <Button
              ref={editButton}
              disabled={working || !!api.pending}
              aria-label="Edit explanation"
              onClick={() => setForm(structuredClone(currentDocumentation(draft?.content)))}
            >
              Edit
            </Button>
          ) : undefined
        }
      />
      {body}

      {working && <p role="status">Saving model explanation…</p>}
      {error && (
        <div role="alert">
          <p>{error}</p>
          {stale && <Button onClick={() => void load(true)}>Load latest draft</Button>}
        </div>
      )}
    </section>
  );
}
