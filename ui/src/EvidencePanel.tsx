import { DialogActions, ActionGroup } from './design';
import { configurationCriteria } from './recordViews';
import { readEvidenceContent, writeEvidenceContent } from './evidenceContent';
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import {
  PageHeader,
  Button,
  Checkbox,
  Select,
  TextArea,
  TextInput,
  StatusTag,
  DialogFrame,
  SectionHeader,
} from './design';
import {
  ApiError,
  HyprnMvpApi,
  message,
  accessLostText,
  type EvidenceRecord,
  type EvidenceResourceRef1,
  type EvidenceCreate3,
  type EvidenceRevise3,
  type ModelRevisionRead4,
  type ConfigurationRevisionRead6,
} from './api';
import { EvidenceRecordBody, evidenceAccessLost, evidenceTitle } from './EvidenceView';
import { cleanGuard, type EditorGuard, type WorkspaceLink } from './workspaceModel';
import { useReferencedEvidence } from './referencedEvidence';
import { EvidenceStack, ReadingStack } from './design';
export { EvidenceRecordBody } from './EvidenceView';
export type EvidenceScopeOption = { label: string; scope: EvidenceResourceRef1 };
type Draft = {
  quoted: boolean;
  excerpt: string;
  reference: string;
  location: string;
  title: string;
  content: string;
  refs: string;
  scope: EvidenceResourceRef1;
  expected?: string;
  command?: EvidenceCreate3 | EvidenceRevise3;
  saved?: EvidenceRecord;
  stale: boolean;
  revoked: boolean;
};
const uncertainMessage =
  'The evidence may already be saved. Check the original command before trying again.';
// In-memory only, isolated by API/session/study/owner. Commands survive dialog unmount without retargeting.
const drafts = new WeakMap<HyprnMvpApi, Map<string, Draft>>();
export function EvidenceEditor({
  api,
  studyId,
  ownerKey,
  scopes,
  record,
  onSaved,
  onHandle,
  onUnavailable,
  active = true,
}: {
  api: HyprnMvpApi;
  studyId: string;
  ownerKey: string;
  scopes: EvidenceScopeOption[];
  record?: EvidenceRecord;
  onSaved: (record: EvidenceRecord) => void;
  onHandle: (handle: EditorGuard) => void;
  onUnavailable?: () => void;
  active?: boolean;
}) {
  const actor = api.actor,
    key = JSON.stringify([actor, studyId, ownerKey, record?.evidence_version_id ?? 'new']);
  if (!drafts.has(api)) drafts.set(api, new Map());
  const cache = drafts.get(api)!;
  const source = record ? readEvidenceContent(record.content) : null;
  if (!cache.has(key))
    cache.set(key, {
      quoted: !!source,
      excerpt: source?.excerpt ?? '',
      reference: source?.source_reference ?? '',
      location: source?.location ?? '',
      title: record && 'title' in record ? record.title : '',
      content: source?.explanation ?? record?.content ?? '',
      refs: record?.source_refs.join('\n') ?? '',
      scope: record && 'resource_scope' in record ? record.resource_scope : scopes[0].scope,
      expected: record?.evidence_version_id,
      stale: false,
      revoked: false,
    });
  const [draft] = useState(() => cache.get(key)!);
  const unresolved = [...cache.entries()].some(
    ([owner, value]) => JSON.parse(owner)[0] === actor && !!value.command,
  );
  const [, render] = useState(0),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(''),
    [latest, setLatest] = useState<EvidenceRecord | null>(null);
  const controller = useRef<AbortController | null>(null),
    generation = useRef(0),
    locked = useRef(false),
    form = useRef<HTMLFieldSetElement>(null);
  const callbacks = useRef({ onSaved, onUnavailable });
  callbacks.current = { onSaved, onUnavailable };
  const update = () => render((n) => n + 1);
  const dirty =
    !draft.saved &&
    (!!draft.command ||
      draft.title !== (record && 'title' in record ? record.title : '') ||
      draft.content !== (source?.explanation ?? record?.content ?? '') ||
      draft.quoted !== !!source ||
      draft.excerpt !== (source?.excerpt ?? '') ||
      draft.reference !== (source?.source_reference ?? '') ||
      draft.location !== (source?.location ?? '') ||
      draft.refs !== (record?.source_refs.join('\n') ?? '') ||
      JSON.stringify(draft.scope) !==
        JSON.stringify(
          record && 'resource_scope' in record ? record.resource_scope : scopes[0].scope,
        ));
  useEffect(() => {
    if (draft.saved) callbacks.current.onSaved(draft.saved);
    return () => {
      generation.current++;
      controller.current?.abort();
    };
  }, [key]);
  function revoke() {
    draft.title = '';
    draft.content = '';
    draft.refs = '';
    draft.excerpt = '';
    draft.reference = '';
    draft.location = '';
    draft.quoted = false;
    draft.saved = undefined;
    draft.revoked = true;
    setLatest(null);
    callbacks.current.onUnavailable?.();
  }
  async function perform(action: (signal: AbortSignal) => Promise<EvidenceRecord | null>) {
    if (locked.current || draft.revoked) return false;
    locked.current = true;
    setBusy(true);
    setError('');
    controller.current = new AbortController();
    const token = generation.current;
    try {
      const saved = await action(controller.current.signal);
      if (actor !== api.actor || token !== generation.current) return false;
      if (saved) {
        draft.command = undefined;
        draft.saved = saved;
        cache.delete(key);
        callbacks.current.onSaved(saved);
      }
      update();
      return !!saved;
    } catch (e) {
      if (actor === api.actor && token === generation.current) {
        if (evidenceAccessLost(e)) {
          revoke();
          setError(
            'Access to this evidence is no longer available. Choose another record or remove the attachment.',
          );
        } else if (e instanceof ApiError && e.detail.code === 'stale_revision') {
          draft.command = undefined;
          draft.stale = true;
          setError(
            'A newer evidence version was saved. Your edits are kept. Review the latest version before saving.',
          );
        } else if (draft.command && api.pending?.body.command_id === draft.command.command_id)
          setError(uncertainMessage);
        else {
          draft.command = undefined;
          setError(
            'Evidence was not saved. Your edits are kept. Correct the reported fields and try again. ' +
              message(e),
          );
        }
        update();
      }
      return false;
    } finally {
      locked.current = false;
      if (token === generation.current) setBusy(false);
    }
  }
  async function save() {
    if (draft.saved) return true;
    if (unresolved || draft.stale || api.pending || draft.revoked) return false;
    const invalid = !draft.title.trim()
      ? 'Enter a title.'
      : !draft.content.trim()
        ? 'Enter an explanation or note.'
        : draft.quoted &&
            (!draft.excerpt.trim() || !draft.reference.trim() || !draft.location.trim())
          ? 'Enter the source excerpt, source reference and page or location.'
          : '';
    const content = draft.quoted
      ? writeEvidenceContent({
          excerpt: draft.excerpt,
          source_reference: draft.reference,
          location: draft.location,
          explanation: draft.content,
        })
      : draft.content;
    const refs = draft.refs ? draft.refs.split('\n') : [];
    const limits =
      draft.title.length > 200 ||
      content.length > 4096 ||
      refs.length > 1000 ||
      refs.some((ref) => ref.length > 4096);
    if (invalid || limits) {
      setError(
        invalid ||
          'Title: at most 200 characters. The complete evidence content and each source reference: at most 4096 characters; at most 1000 references.',
      );
      form.current
        ?.querySelector<HTMLInputElement | HTMLTextAreaElement>(
          !draft.title.trim() ? 'input' : 'textarea',
        )
        ?.focus();
      return false;
    }
    return perform(async (signal) => {
      const command: EvidenceCreate3 = {
        command_id: crypto.randomUUID(),
        evidence_schema_version: '3',
        title: draft.title,
        content,
        source_refs: refs,
        resource_scope: structuredClone(draft.scope),
        kind: 'note',
      };
      draft.command = record ? { ...command, expected_revision: draft.expected! } : command;
      update();
      return record
        ? api.reviseEvidence(studyId, record.evidence_id, draft.command as EvidenceRevise3, signal)
        : api.createEvidenceCommand(studyId, command, signal);
    });
  }
  async function recover(retry = false) {
    return perform(async (signal) => {
      const id = draft.command?.command_id;
      if (!id) return null;
      if (retry) await api.retryOriginal();
      // Reconcile only the matching original; an unrelated owner command is never consumed.
      if (api.pending?.body.command_id === id) await api.reconcile();
      if (api.pending?.body.command_id === id && api.retryReady) {
        setError(uncertainMessage);
        return null;
      }
      const receipt = await api.evidenceReceipt(studyId, id, signal);
      if (receipt.state === 'committed' && receipt.result) return receipt.result;
      if (receipt.state === 'rejected') {
        draft.command = undefined;
        draft.stale = receipt.error?.code === 'stale_revision';
        throw new Error('The original evidence command was rejected. Your edits are kept.');
      }
      throw new Error('The original evidence command is not yet resolved.');
    });
  }
  async function review() {
    await perform(async (signal) => {
      const family = await api.evidenceFamily(studyId, record!.evidence_id, signal);
      setLatest(family.head);
      return null;
    });
  }
  function discard() {
    if (draft.command) return;
    draft.title = record && 'title' in record ? record.title : '';
    draft.content = source?.explanation ?? record?.content ?? '';
    draft.quoted = !!source;
    draft.excerpt = source?.excerpt ?? '';
    draft.reference = source?.source_reference ?? '';
    draft.location = source?.location ?? '';
    draft.refs = record?.source_refs.join('\n') ?? '';
    draft.scope = record && 'resource_scope' in record ? record.resource_scope : scopes[0].scope;
    draft.saved = undefined;
    draft.stale = false;
    draft.expected = record?.evidence_version_id;
    setError('');
    setLatest(null);
    update();
  }
  useLayoutEffect(() => {
    onHandle({ dirty, save, discard });
  });
  const options = scopes.some(
    (option) => JSON.stringify(option.scope) === JSON.stringify(draft.scope),
  )
    ? scopes
    : [{ label: 'Context of this version', scope: draft.scope }, ...scopes];
  return (
    <>
      {record && (
        <p>
          Saving creates a new evidence version. Existing attachments keep the version they cite.
        </p>
      )}
      {busy && (
        <p role="status">
          <StatusTag tone="running">
            {record ? 'Saving new version…' : 'Saving evidence…'}
          </StatusTag>
        </p>
      )}
      {error && error !== uncertainMessage && <p role="alert">{error}</p>}
      {draft.command && !busy && !draft.revoked && (
        <aside className="evidence-recovery">
          <StatusTag tone="warning">Outcome uncertain</StatusTag>
          <p role="alert">{uncertainMessage}</p>
          <Button onClick={() => void recover()}>Check original command</Button>
          {api.retryReady && api.pending?.body.command_id === draft.command.command_id && (
            <Button onClick={() => void recover(true)}>Retry original command</Button>
          )}
        </aside>
      )}
      {draft.stale && !draft.revoked && (
        <>
          <Button disabled={busy} onClick={() => void review()}>
            Review latest version
          </Button>
          {latest && (
            <section aria-label="Latest evidence version">
              <EvidenceRecordBody record={latest} />
              <p>
                Your edited title, note, references and context are kept. Review them against this
                version before reapplying.
              </p>
              <Button
                disabled={busy}
                onClick={() => {
                  draft.expected = latest.evidence_version_id;
                  draft.stale = false;
                  setLatest(null);
                  setError('');
                  update();
                }}
              >
                Reapply edits to this version
              </Button>
            </section>
          )}
        </>
      )}
      {!draft.revoked && !draft.saved && (
        <fieldset ref={form} className="form-stack" disabled={busy || !!api.pending || unresolved}>
          <label>
            Title
            <TextInput
              aria-label="Title"
              autoFocus
              value={draft.title}
              maxLength={200}
              onChange={(e) => {
                draft.title = e.target.value;
                update();
              }}
            />
          </label>
          <label>
            <Checkbox
              aria-label="Include source excerpt"
              checked={draft.quoted}
              onChange={(e) => {
                draft.quoted = e.target.checked;
                update();
              }}
            />
            Include source excerpt
          </label>
          {draft.quoted && (
            <>
              <label>
                Source excerpt
                <TextArea
                  aria-label="Source excerpt"
                  value={draft.excerpt}
                  maxLength={4096}
                  onChange={(e) => {
                    draft.excerpt = e.target.value;
                    update();
                  }}
                />
              </label>
              <label>
                Source reference
                <TextInput
                  aria-label="Source reference"
                  value={draft.reference}
                  maxLength={4096}
                  onChange={(e) => {
                    draft.reference = e.target.value;
                    update();
                  }}
                />
              </label>
              <label>
                Page or location
                <TextInput
                  aria-label="Page or location"
                  value={draft.location}
                  maxLength={4096}
                  onChange={(e) => {
                    draft.location = e.target.value;
                    update();
                  }}
                />
              </label>
            </>
          )}
          <label>
            {draft.quoted ? 'Explanation' : 'Evidence note'}
            <TextArea
              aria-label={draft.quoted ? 'Explanation' : 'Evidence note'}
              value={draft.content}
              maxLength={4096}
              onChange={(e) => {
                draft.content = e.target.value;
                update();
              }}
            />
          </label>
          <label>
            Source references
            <TextArea
              aria-label="Source references"
              value={draft.refs}
              onChange={(e) => {
                draft.refs = e.target.value;
                update();
              }}
            />
          </label>
          <p>One source reference per line.</p>
          <label>
            Context
            <Select
              aria-label="Context"
              value={JSON.stringify(draft.scope)}
              onChange={(e) => {
                draft.scope = options.find(
                  (option) => JSON.stringify(option.scope) === e.target.value,
                )!.scope;
                update();
              }}
            >
              {options.map((option) => (
                <option key={JSON.stringify(option.scope)} value={JSON.stringify(option.scope)}>
                  {option.label}
                </option>
              ))}
            </Select>
          </label>
          <DialogActions
            active={active}
            primary={
              <Button
                variant="primary"
                disabled={draft.stale || busy || !!api.pending || unresolved}
                onClick={() => void save()}
              >
                {record ? 'Save new version' : 'Create evidence'}
              </Button>
            }
          />
        </fieldset>
      )}
      {(api.pending || unresolved) && !draft.command && (
        <p>Check the original command before making more changes.</p>
      )}
    </>
  );
}

/** Evidence library: read the exact versions cited by the study, directly. */
export function EvidencePanel({
  api,
  studyId,
  snapshot,
  configuration,
  runId,
  onRecords,
  onHandle,
  onOpen,
}: {
  api: HyprnMvpApi;
  studyId: string;
  snapshot?: ModelRevisionRead4 | null;
  configuration?: ConfigurationRevisionRead6 | null;
  runId?: string;
  records?: EvidenceRecord[];
  onRecords: (records: EvidenceRecord[]) => void;
  onHandle: (handle: EditorGuard) => void;
  onOpen?: (target: WorkspaceLink) => void;
}) {
  const [filter, setFilter] = useState('');
  const [error, setError] = useState(''),
    [editing, setEditing] = useState<EvidenceRecord | 'new' | null>(null),
    [discarding, setDiscarding] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null),
    invoker = useRef<HTMLElement | null>(null);
  const handle = useRef<EditorGuard>(cleanGuard());
  const actor = api.actor,
    common = { scope_version: '1' as const, study_id: studyId };
  const scopes: EvidenceScopeOption[] = [{ label: 'Study', scope: { ...common, kind: 'study' } }];
  if (snapshot) {
    const model = {
      ...common,
      model_id: snapshot.model_id,
      model_revision_id: snapshot.model_revision_id,
    };
    scopes.push({ label: 'Model version', scope: { ...model, kind: 'model_revision' } });
    snapshot.definitions.forEach((d) =>
      scopes.push({
        label: 'Definition ' + d.name,
        scope: {
          ...model,
          kind: 'definition_version',
          definition_id: d.definition_id,
          definition_version_id: d.definition_version_id,
        },
      }),
    );
    snapshot.instances.forEach((i) => {
      scopes.push({
        label: 'Component ' + i.name,
        scope: { ...model, kind: 'instance', instance_id: i.instance_id },
      });
      snapshot.definitions
        .find((d) => d.definition_version_id === i.definition_version_id)
        ?.ports.forEach((p) =>
          scopes.push({
            label: 'Quantity ' + i.name + ' · ' + p.name,
            scope: { ...model, kind: 'port', instance_id: i.instance_id, port_id: p.port_id },
          }),
        );
    });
    snapshot.connections.forEach((c) =>
      scopes.push({
        label: 'Connection ' + c.connection_id.slice(0, 8),
        scope: { ...model, kind: 'connection', connection_id: c.connection_id },
      }),
    );
  }
  if (configuration) {
    scopes.push({
      label: 'Configuration version',
      scope: {
        ...common,
        kind: 'configuration',
        configuration_revision_id: configuration.configuration_revision_id,
      },
    });
    configurationCriteria(configuration).forEach((c) =>
      scopes.push({
        label: 'Criterion ' + c.criterion_id.slice(0, 8),
        scope: {
          ...common,
          kind: 'criterion',
          configuration_revision_id: configuration.configuration_revision_id,
          criterion_id: c.criterion_id,
        },
      }),
    );
  }
  if (runId) scopes.push({ label: 'Run', scope: { ...common, kind: 'run', run_id: runId } });
  const collection = useReferencedEvidence(api, studyId);
  const records = collection.records,
    loading = collection.loading;
  useEffect(() => {
    if (collection.unavailable) setEditing(null);
  }, [collection.unavailable]);
  const refresh = collection.refresh;
  const clear = () => {
    setEditing(null);
    refresh();
  };
  useEffect(() => {
    if (editing) dialog.current?.showModal();
    else dialog.current?.close();
  }, [editing]);
  useEffect(() => {
    onHandle(
      editing
        ? {
            dirty: handle.current.dirty,
            save: () => handle.current.save(),
            discard: () => handle.current.discard(),
          }
        : cleanGuard(),
    );
  });
  function close() {
    if (api.pending?.category === 'evidence' && api.pending.study === studyId) return;
    if (handle.current.dirty) setDiscarding(true);
    else setEditing(null);
  }
  function open(record: EvidenceRecord | 'new') {
    invoker.current = document.activeElement as HTMLElement;
    setDiscarding(false);
    setEditing(record);
  }
  const visible = records.filter((record) =>
    (evidenceTitle(record) + ' ' + record.content + ' ' + record.source_refs.join(' '))
      .toLowerCase()
      .includes(filter.toLowerCase()),
  );
  return (
    <section aria-label="Evidence" className="evidence-page">
      <PageHeader
        title="Evidence"
        actions={
          <Button variant="primary" disabled={collection.unavailable} onClick={() => open('new')}>
            New evidence
          </Button>
        }
      />
      <ReadingStack role="region" aria-label="Evidence library">
        {error && <p role="status">{error}</p>}
        <ActionGroup>
          <Button disabled={loading} onClick={refresh}>
            Refresh evidence
          </Button>
          {records.length > 1 && (
            <label>
              Filter evidence
              <TextInput type="search" value={filter} onChange={(e) => setFilter(e.target.value)} />
            </label>
          )}
        </ActionGroup>
        {loading && <p role="status">Loading referenced evidence…</p>}
        {collection.issues.length > 0 && (
          <div role="alert">
            <p>
              {collection.unavailable
                ? accessLostText
                : 'Some evidence references could not be loaded. The list may be incomplete.'}
            </p>
            <Button onClick={refresh}>Retry loading evidence</Button>
          </div>
        )}
        {!loading && !collection.issues.length && !records.length && !collection.missing.length && (
          <p>No evidence referenced yet.</p>
        )}
        <EvidenceStack className="hf-evidence-list">
          {visible.map((record) => (
            <article className="evidence-record" key={record.evidence_version_id}>
              <EvidenceRecordBody
                record={record}
                contextual
                onUnavailable={() => {
                  clear();
                  setError(
                    'Access to this evidence is no longer available. Choose another record or remove the attachment.',
                  );
                }}
                action={
                  'study_id' in record && 'evidence_id' in record ? (
                    <Button size="sm" onClick={() => open(record as EvidenceRecord)}>
                      Edit
                    </Button>
                  ) : null
                }
              />
            </article>
          ))}
          {collection.missing.map((id) => (
            <p key={id}>
              <StatusTag tone="warning">Evidence unavailable</StatusTag>
            </p>
          ))}
        </EvidenceStack>
        {filter && !visible.length && <p>No matching evidence.</p>}
      </ReadingStack>
      <DialogFrame
        ref={dialog}
        aria-label={editing === 'new' ? 'New evidence' : 'Edit evidence'}
        onCancel={(e) => {
          e.preventDefault();
          close();
        }}
        onClose={() => invoker.current?.isConnected && invoker.current.focus()}
      >
        <SectionHeader
          level={2}
          title={editing === 'new' ? 'New evidence' : 'Edit evidence'}
          help="evidence"
        />
        {editing && (
          <EvidenceEditor
            key={JSON.stringify([
              actor,
              studyId,
              editing === 'new' ? 'new' : editing.evidence_version_id,
            ])}
            api={api}
            studyId={studyId}
            ownerKey="library"
            scopes={scopes}
            record={editing === 'new' ? undefined : editing}
            onHandle={(value) => {
              handle.current = value;
              onHandle(value);
            }}
            onUnavailable={clear}
            onSaved={() => {
              setError(
                'Evidence saved. Existing references keep their cited version; attach the new version where it supports a claim.',
              );
              setEditing(null);
              void refresh();
            }}
          />
        )}
        <DialogActions>
          {discarding ? (
            <section aria-label="Unsaved evidence changes">
              <p>Discard unsaved evidence changes?</p>
              <Button onClick={() => setDiscarding(false)}>Keep editing</Button>
              <Button
                variant="danger"
                onClick={() => {
                  handle.current.discard();
                  setEditing(null);
                  setDiscarding(false);
                }}
              >
                Discard changes
              </Button>
            </section>
          ) : (
            <Button onClick={close}>Cancel</Button>
          )}
        </DialogActions>
      </DialogFrame>
    </section>
  );
}
