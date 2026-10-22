import { DialogActions } from './design';
import { useCollectionRead } from './useCollectionRead';
import { CollectionStatus } from './design';
import { EvidenceDisclosure } from './ContextDetails';
import { ActionGroup } from './design';
import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import {
  Button,
  DialogFrame,
  SectionHeader,
  TextArea,
  StatusTag,
  Select,
  TextInput,
} from './design';
import { Assertion, EvidenceStack } from './design';
import { EvidencePicker } from './EvidencePicker';
import {
  EvidenceList,
  EvidenceRecordBody,
  evidenceAccessLost,
  evidenceTitle,
} from './EvidenceView';
import { message, type HyprnMvpApi, type EvidenceRecord, type EvidenceSnapshot } from './api';
import type { ConfigurationAssumption, EvidenceResourceRef1 } from './contract';

type Props = {
  showHeading?: boolean;
  brief?: boolean;
  headingLevel?: 3 | 4;
  itemActions?: (item: ConfigurationAssumption) => ReactNode;
  /** Read-only index use: the host names the region; each item may name its owner within the host (e.g. "Component · name"). */
  regionless?: boolean;
  itemContext?: (item: ConfigurationAssumption) => ReactNode;
  ownerKey: string;
  ownerLabel: string;
  items: ConfigurationAssumption[];
  records: EvidenceSnapshot[];
  editable?: {
    api: HyprnMvpApi;
    studyId: string;
    scope: EvidenceResourceRef1 | null;
    onChange: (items: ConfigurationAssumption[]) => void;
    onRecords: (records: EvidenceRecord[]) => void;
    onDirty: (dirty: boolean) => void;
    disabled?: boolean;
  };
};

const relationLabel = (relation: ConfigurationAssumption['evidence_links'][number]['relation']) =>
  relation === 'supports' ? 'Supports' : relation === 'challenges' ? 'Challenges' : 'Context';

/** Owner-keyed local editing; retained callers provide exact snapshots and no API. */
export function Assumptions(props: Props) {
  return <OwnedAssumptions key={props.ownerKey} {...props} />;
}
function OwnedAssumptions({
  showHeading = true,
  brief = false,
  headingLevel = 3,
  itemActions,
  ownerKey,
  ownerLabel,
  items,
  records,
  editable,
  regionless,
  itemContext,
}: Props) {
  const [editing, setEditing] = useState<ConfigurationAssumption | null>(null),
    [initial, setInitial] = useState('');
  const [evidenceDirty, setEvidenceDirty] = useState(false);
  const [picker, setPicker] = useState(false),
    [discarding, setDiscarding] = useState(false),
    [error, setError] = useState('');
  const [removing, setRemoving] = useState<ConfigurationAssumption | null>(null);
  const [changingVersion, setChangingVersion] = useState<{
    index: number;
    record: EvidenceSnapshot & { evidence_id: string };
  } | null>(null);
  const removalDialog = useRef<HTMLDialogElement>(null),
    removalInvoker = useRef<HTMLElement | null>(null);
  const dialog = useRef<HTMLDialogElement>(null),
    add = useRef<HTMLButtonElement>(null),
    invoker = useRef<HTMLElement | null>(null),
    // The evidence panel holding "Change version" may close while the version dialog is open.
    versionInvoker = useRef<HTMLElement | null>(null);
  const dirty = !!editing && JSON.stringify(editing) !== initial;
  useLayoutEffect(() => {
    editable?.onDirty(dirty || evidenceDirty);
  }, [dirty, evidenceDirty]);
  useEffect(
    () => () => {
      editable?.onDirty(false);
    },
    [],
  );
  useEffect(() => {
    if (editing) {
      dialog.current?.showModal();
      dialog.current?.querySelector('textarea')?.focus();
    }
  }, [!!editing]);
  useEffect(() => {
    if (removing) {
      removalDialog.current?.showModal();
      removalDialog.current?.querySelector<HTMLButtonElement>('[data-safe-choice]')?.focus();
    }
  }, [!!removing]);
  function closeRemoval(removed = false) {
    removalDialog.current?.close();
    setRemoving(null);
    (removed ? add.current : removalInvoker.current)?.focus();
  }
  function close() {
    if (picker || changingVersion) return;
    if (dirty) setDiscarding(true);
    else finish();
  }
  function finish() {
    dialog.current?.close();
    setEditing(null);
    setPicker(false);
    setDiscarding(false);
    setError('');
    editable?.onDirty(false);
    (invoker.current?.isConnected ? invoker.current : add.current)?.focus();
  }
  function edit(item?: ConfigurationAssumption) {
    invoker.current = document.activeElement as HTMLElement;
    const value = structuredClone(
      item ?? {
        assumption_id: crypto.randomUUID(),
        statement: '',
        evidence_links: [],
      },
    );
    setInitial(JSON.stringify(value));
    setEditing(value);
  }
  function evidenceRows(item: ConfigurationAssumption) {
    return item.evidence_links.length ? (
      <EvidenceList
        records={records}
        ids={item.evidence_links.map((link) => link.evidence_version_id)}
        links={item.evidence_links}
        label={item.statement}
      />
    ) : (
      !brief && <p className="context-line">No evidence linked.</p>
    );
  }
  function citations(item: ConfigurationAssumption, mutable = false) {
    return item.evidence_links.length ? (
      <EvidenceDisclosure
        live={mutable}
        count={new Set(item.evidence_links.map((link) => link.evidence_version_id)).size}
        version={JSON.stringify(item.evidence_links)}
      >
        <EvidenceStack>
          {item.evidence_links.map((link, index) => {
            const record = records.find((r) => r.evidence_version_id === link.evidence_version_id);
            return (
              <article className="evidence-record" key={link.evidence_version_id + link.relation}>
                <p>{relationLabel(link.relation)}</p>
                {record ? (
                  <EvidenceRecordBody record={record} contextual />
                ) : (
                  <>
                    <StatusTag tone="warning">Evidence unavailable</StatusTag>
                    <p className="evidence-content">{link.evidence_version_id}</p>
                  </>
                )}
                {mutable && record && 'evidence_id' in record && (
                  <Button
                    disabled={editable?.disabled}
                    onClick={() => {
                      versionInvoker.current = document.activeElement as HTMLElement;
                      setChangingVersion({ index, record });
                    }}
                  >
                    Change version
                  </Button>
                )}
                {mutable && (
                  <Button
                    onClick={() =>
                      setEditing({
                        ...item,
                        evidence_links: item.evidence_links.filter((_, i) => i !== index),
                      })
                    }
                  >
                    Remove attachment
                  </Button>
                )}
              </article>
            );
          })}
        </EvidenceStack>
      </EvidenceDisclosure>
    ) : (
      <p>No evidence linked.</p>
    );
  }
  // One concept for every owner: heading, statement, evidence rows. The owner is named by the
  // place the list appears (and in dialog titles), never repeated under the heading.
  const addButton = editable && (
    <Button ref={add} disabled={editable.disabled || items.length >= 1000} onClick={() => edit()}>
      Add assumption
    </Button>
  );
  const List = regionless ? 'div' : 'section';
  return (
    <List
      aria-label={regionless ? undefined : ownerLabel + ' assumptions'}
      className="assumption-list hf-assertions"
    >
      {showHeading ? (
        <SectionHeader level={headingLevel} help="assumptions" title="Assumptions" actions={addButton} />
      ) : (
        addButton
      )}
      {!items.length && !brief && !editable && <p className="context-line">No assumptions</p>}
      {items.map((item) => (
        <Assertion className="assumption-item" key={item.assumption_id} statement={item.statement}>
          {itemContext && <p className="context-line assumption-owner">{itemContext(item)}</p>}
          {evidenceRows(item)}
          {editable && (
            <ActionGroup className="actions">
              <Button
                disabled={editable.disabled}
                aria-label={'Edit assumption: ' + item.statement}
                onClick={() => edit(item)}
              >
                Edit
              </Button>
              <Button
                disabled={editable.disabled}
                aria-label={'Remove assumption: ' + item.statement}
                onClick={() => {
                  removalInvoker.current = document.activeElement as HTMLElement;
                  setRemoving(item);
                }}
              >
                Remove assumption
              </Button>
              {itemActions?.(item)}
            </ActionGroup>
          )}
        </Assertion>
      ))}
      {removing && editable && (
        <DialogFrame
          ref={removalDialog}
          aria-label="Remove assumption"
          onCancel={(event) => {
            if (event.target !== event.currentTarget) return;
            event.preventDefault();
            closeRemoval();
          }}
        >
          <SectionHeader level={2} title={<>Remove this assumption from {ownerLabel}?</>} />
          <p className="evidence-content">{removing.statement}</p>
          <p>Its evidence records and saved versions will remain.</p>
          <DialogActions
            primary={
              <Button
                variant="danger"
                disabled={editable.disabled}
                onClick={() => {
                  editable.onChange(items.filter((a) => a.assumption_id !== removing.assumption_id));
                  closeRemoval(true);
                }}
              >
                Remove assumption
              </Button>
            }
          >
            <Button data-safe-choice onClick={() => closeRemoval()}>
              Keep assumption
            </Button>
          </DialogActions>
        </DialogFrame>
      )}
      {editing && editable && (
        <DialogFrame
          ref={dialog}
          aria-label="Edit assumption"
          onCancel={(event) => {
            if (event.target !== event.currentTarget) return;
            event.preventDefault();
            close();
          }}
        >
          <SectionHeader
            level={2}
            help="assumptions"
            title={items.some((a) => a.assumption_id === editing.assumption_id)
              ? 'Edit assumption' : 'Add assumption'}
          />
          <p>{ownerLabel}</p>
          <label>
            Statement
            <TextArea
              aria-label="Statement"
              maxLength={4096}
              rows={3}
              value={editing.statement}
              onChange={(event) => {
                setError('');
                setEditing({ ...editing, statement: event.target.value });
              }}
            />
          </label>
          {citations(editing, true)}
          <Button
            disabled={editable.disabled || editing.evidence_links.length >= 64}
            onClick={() => setPicker(true)}
          >
            Add evidence
          </Button>
          {error && <p role="alert">{error}</p>}
          <DialogActions
            primary={
              <Button
                variant="primary"
                disabled={editable.disabled || picker}
                onClick={() => {
                  if (!editing.statement.trim()) {
                    setError('Enter an assumption statement.');
                    dialog.current?.querySelector('textarea')?.focus();
                    return;
                  }
                  editable.onChange(
                    items.some((a) => a.assumption_id === editing.assumption_id)
                      ? items.map((a) => (a.assumption_id === editing.assumption_id ? editing : a))
                      : [...items, editing],
                  );
                  finish();
                }}
              >
                Apply assumption
              </Button>
            }
          >
            <Button onClick={close}>Cancel</Button>
          </DialogActions>
          {discarding && (
            <>
              <p>Discard unsaved assumption changes?</p>
              <DialogActions>
                <Button
                  onClick={() => {
                    setDiscarding(false);
                    dialog.current?.querySelector('textarea')?.focus();
                  }}
                >
                  Keep editing
                </Button>
                <Button variant="danger" onClick={finish}>
                  Discard changes
                </Button>
              </DialogActions>
            </>
          )}
          {picker && (
            <EvidencePicker
              onDirty={setEvidenceDirty}
              api={editable.api}
              studyId={editable.studyId}
              ownerKey={ownerKey + '/' + editing.assumption_id}
              label={ownerLabel + ' assumption'}
              scope={editable.scope}
              assumption
              onRecords={editable.onRecords}
              onClose={() => setPicker(false)}
              onAttach={(record, relation) => {
                if (!relation) return;
                const link = { evidence_version_id: record.evidence_version_id, relation };
                if (
                  !editing.evidence_links.some(
                    (l) =>
                      l.evidence_version_id === link.evidence_version_id && l.relation === relation,
                  )
                )
                  setEditing({ ...editing, evidence_links: [...editing.evidence_links, link] });
                setPicker(false);
              }}
            />
          )}
          {changingVersion && (
            <AssumptionVersionChange
              api={editable.api}
              studyId={editable.studyId}
              ownerLabel={ownerLabel}
              original={changingVersion.record}
              relation={editing.evidence_links[changingVersion.index].relation}
              duplicateIds={editing.evidence_links
                .filter(
                  (link, index) =>
                    index !== changingVersion.index &&
                    link.relation === editing.evidence_links[changingVersion.index].relation,
                )
                .map((link) => link.evidence_version_id)}
              onUnavailable={() => editable.onRecords([])}
              onClose={() => {
                setChangingVersion(null);
                requestAnimationFrame(() => {
                  const target = versionInvoker.current;
                  if (target?.isConnected && target.checkVisibility()) target.focus();
                  else
                    dialog.current
                      ?.querySelector<HTMLElement>('.hf-evidence-action button')
                      ?.focus();
                });
              }}
              onApply={(record) => {
                editable.onRecords([record]);
                setEditing({
                  ...editing,
                  evidence_links: editing.evidence_links.map((link, index) =>
                    index === changingVersion.index
                      ? { ...link, evidence_version_id: record.evidence_version_id }
                      : link,
                  ),
                });
                setChangingVersion(null);
                requestAnimationFrame(() => dialog.current?.querySelector('textarea')?.focus());
              }}
            />
          )}
        </DialogFrame>
      )}
    </List>
  );
}

/** Explicit same-family replacement; inspecting a version never changes a citation. */
function AssumptionVersionChange({
  api,
  studyId,
  ownerLabel,
  original,
  relation,
  duplicateIds,
  onUnavailable,
  onClose,
  onApply,
}: {
  api: HyprnMvpApi;
  studyId: string;
  ownerLabel: string;
  original: EvidenceSnapshot & { evidence_id: string };
  relation: ConfigurationAssumption['evidence_links'][number]['relation'];
  duplicateIds: string[];
  onUnavailable: () => void;
  onClose: () => void;
  onApply: (record: EvidenceRecord) => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null),
    live = useRef(true),
    request = useRef<AbortController | null>(null),
    generation = useRef(0);
  const [proposed, setProposed] = useState<EvidenceRecord | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(''),
    [unavailable, setUnavailable] = useState(false);

  const actor = api.actor;
  useEffect(() => {
    const invoking = document.activeElement as HTMLElement;
    dialog.current?.showModal();
    return () => {
      live.current = false;
      generation.current++;
      request.current?.abort();
      invoking?.isConnected && invoking.focus();
    };
  }, []);
  function lostAccess() {
    setUnavailable(true);
    setProposed(null);
    onUnavailable();
  }
  async function read(action: (signal: AbortSignal, current: () => boolean) => Promise<void>) {
    request.current?.abort();
    const token = ++generation.current,
      controller = new AbortController();
    request.current = controller;
    const current = () => live.current && token === generation.current && actor === api.actor;
    setBusy(true);
    setError('');
    try {
      await action(controller.signal, current);
    } catch (e) {
      if (current()) {
        if (evidenceAccessLost(e)) lostAccess();
        setError(message(e));
      }
    } finally {
      if (current()) setBusy(false);
    }
  }
  const collection = useCollectionRead<EvidenceRecord, string>({
    api,
    study: studyId,
    scope: original.evidence_id,
    load: async (cursor, signal) => {
      const page = await api.evidenceVersions(
        studyId,
        original.evidence_id,
        { limit: 20, cursor },
        signal,
      );
      if (
        page.data.some(
          (record) => record.evidence_id !== original.evidence_id || record.study_id !== studyId,
        )
      )
        throw new Error('Evidence versions do not belong to this family.');
      return { rows: page.data, next: page.next_cursor };
    },
    identity: (row) => row.evidence_version_id,
    onUnavailable: lostAccess,
  });
  const versions = collection.rows;
  async function choose(versionId: string, apply = false) {
    if (busy || unavailable) return;
    await read(async (signal, current) => {
      const exact = await api.evidenceVersion(studyId, versionId, signal);
      if (!current()) return;
      if (
        exact.study_id !== studyId ||
        exact.evidence_id !== original.evidence_id ||
        exact.evidence_version_id !== versionId ||
        duplicateIds.includes(exact.evidence_version_id)
      )
        throw new Error(
          'Choose another version from this evidence family without duplicating an existing relationship.',
        );
      if (apply) onApply(exact);
      else setProposed(exact);
    });
  }
  return (
    <DialogFrame
      ref={dialog}
      aria-label="Change evidence version"
      onCancel={(event) => {
        if (event.target !== event.currentTarget) return;
        event.preventDefault();
        onClose();
      }}
    >
      <SectionHeader level={2} title="Change evidence version" help="evidence" />
      <p>{ownerLabel}</p>
      <p>
        The existing{' '}
        {relation === 'supports'
          ? 'Supports'
          : relation === 'challenges'
            ? 'Challenges'
            : 'Context'}{' '}
        relationship is preserved. Other uses remain unchanged.
      </p>
      {unavailable ? (
        <p role="alert">Evidence unavailable. Choose another record or remove the attachment.</p>
      ) : (
        <>
          <section aria-label="Evidence versions">
            {versions.map((record) => (
              <p key={record.evidence_version_id}>
                <Button
                  disabled={busy}
                  aria-pressed={proposed?.evidence_version_id === record.evidence_version_id}
                  title={record.evidence_version_id}
                  onClick={() => void choose(record.evidence_version_id)}
                >
                  Choose {evidenceTitle(record)} · Saved {record.evidence_version_id.slice(0, 8)}
                  {record.evidence_version_id === original.evidence_version_id
                    ? ' · Current attachment'
                    : ''}
                </Button>
              </p>
            ))}
            <CollectionStatus
              entity={{ singular: 'evidence version', plural: 'evidence versions' }}
              state={collection.state}
              onMore={() => void collection.more()}
              onRetry={() => void collection.retry()}
            />
          </section>
          {proposed && (
            <section aria-label="Proposed evidence replacement">
              <p>
                {evidenceTitle(original)} · Version{' '}
                <abbr title={original.evidence_version_id}>
                  {original.evidence_version_id.slice(0, 8)}
                </abbr>{' '}
                → {evidenceTitle(proposed)} · Version{' '}
                <abbr title={proposed.evidence_version_id}>
                  {proposed.evidence_version_id.slice(0, 8)}
                </abbr>
              </p>
              <p className="hf-visually-hidden">
                From evidence version {original.evidence_version_id} to evidence version{' '}
                {proposed.evidence_version_id}.
              </p>
              <EvidenceRecordBody record={proposed} />
            </section>
          )}
        </>
      )}
      {error && <p role="alert">{error}</p>}
      {busy && <p role="status">Checking evidence version…</p>}
      <DialogActions
        primary={
          <Button
            variant="primary"
            disabled={
              busy ||
              unavailable ||
              !proposed ||
              proposed.evidence_version_id === original.evidence_version_id ||
              !!api.pending
            }
            onClick={() => proposed && void choose(proposed.evidence_version_id, true)}
          >
            Apply version change
          </Button>
        }
      >
        <Button onClick={onClose}>Keep current version</Button>
      </DialogActions>
      {(!proposed || proposed.evidence_version_id === original.evidence_version_id) &&
        !unavailable && <p>Choose a different version before applying this change.</p>}
    </DialogFrame>
  );
}
