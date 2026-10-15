import { AttributionDetail, RecordAttribution } from './attribution';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { ApiError, HyprnMvpApi, message, type EvidenceRecord, type EvidenceSnapshot } from './api';
import { ActionDialog, Button, SectionHeader, StatusTag } from './design';

export const evidenceTitle = (record: EvidenceSnapshot) => 'title' in record ? record.title : 'Evidence note';
export const evidenceContext = (record: EvidenceSnapshot) => 'resource_scope' in record && record.resource_scope.kind === 'study' ? 'Study evidence' : 'recorded_context' in record ? record.recorded_context.label : null;
export const evidenceAccessLost = (error: unknown) => error instanceof ApiError && ['unauthenticated', 'forbidden', 'resource_not_found'].includes(error.detail.code);
const identityLabels: Record<string, string> = { study_id: 'Study ID', model_id: 'Model ID', model_revision_id: 'Model version ID', definition_id: 'Definition ID', definition_version_id: 'Definition version ID', instance_id: 'Component ID', port_id: 'Quantity ID', connection_id: 'Connection ID', configuration_revision_id: 'Configuration version ID', criterion_id: 'Criterion ID', run_id: 'Run ID' };
const resourceLabels = { study: 'Study', model: 'Model', definition: 'Definition', instance: 'Component', port: 'Quantity', connection: 'Connection', configuration: 'Configuration', criterion: 'Criterion', run: 'Run' };

/** A library API explicitly enables version discovery. Retained callers never fetch. */
export function EvidenceRecordBody({
  record,
  action,
  library,
  onSelectVersion,
  onUnavailable,
  compact = false,
  relation,
  brief = compact,
}: {
  record: EvidenceSnapshot;
  action?: ReactNode;
  library?: { api: HyprnMvpApi; studyId: string };
  onSelectVersion?: (record: EvidenceRecord) => void;
  onUnavailable?: () => void;
  compact?: boolean;
  brief?: boolean;
  /** Relationship word shown before the title (assumption evidence rows). */ relation?: string;
}) {
  const [inspected, setInspected] = useState(record),
    [versions, setVersions] = useState<EvidenceRecord[]>([]),
    [cursor, setCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(false),
    [error, setError] = useState(''),
    [unavailable, setUnavailable] = useState(false),
    [showVersions, setShowVersions] = useState(false);
  const generation = useRef(0),
    request = useRef<AbortController | null>(null),
    actor = library?.api.actor;
  useEffect(() => {
    setInspected(record);
    setVersions([]);
    setCursor(null);
    setShowVersions(false);
    setUnavailable(false);
    setError('');
    return () => {
      generation.current++;
      request.current?.abort();
    };
  }, [record, library?.api, library?.studyId, actor]);
  async function read(action: (signal: AbortSignal) => Promise<void>) {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    const token = ++generation.current;
    setLoading(true);
    setError('');
    try {
      await action(controller.signal);
    } catch (e) {
      if (token === generation.current && actor === library?.api.actor) {
        if (evidenceAccessLost(e)) {
          setUnavailable(true);
          setVersions([]);
          onUnavailable?.();
        }
        setError(
          'Evidence unavailable. This version could not be loaded. Retry loading this version. ' +
            message(e),
        );
      }
    } finally {
      if (token === generation.current) setLoading(false);
    }
  }
  async function loadVersions(more = false) {
    if (!library || !('evidence_id' in record)) return;
    await read(async (signal) => {
      const page = await library.api.evidenceVersions(
        library.studyId,
        record.evidence_id,
        { limit: 20, ...(more && cursor ? { cursor } : {}) },
        signal,
      );
      setVersions((old) => (more ? [...old, ...page.data] : page.data));
      setCursor(page.next_cursor);
      setShowVersions(true);
    });
  }
  async function inspect(version: string) {
    if (!library) return;
    await read(async (signal) => {
      const exact = await library.api.evidenceVersion(library.studyId, version, signal);
      setInspected(exact);
    });
  }
  function download() {
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(inspected, null, 2)], { type: 'application/json' }),
    );
    const link = document.createElement('a');
    link.href = url;
    link.download = 'evidence-' + inspected.evidence_version_id + '.json';
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  if (unavailable)
    return (
      <p role="alert">
        <StatusTag tone="warning">Evidence unavailable</StatusTag> Access to this evidence is no
        longer available. Choose another record or remove the attachment.
      </p>
    );
  const scope = 'resource_scope' in inspected ? inspected.resource_scope : null;
  const context = evidenceContext(inspected);
  const labels =
    'recorded_context' in inspected && scope?.kind !== 'study'
      ? inspected.recorded_context.resource_labels
      : [];
  return (
    <div className={'hf-evidence-card' + (compact ? ' hf-evidence-card--compact' : '')}>
      <div className="hf-evidence-heading">
        {relation && (!brief || relation.toLowerCase() === 'challenges') && (
          <span className="hf-evidence-relation">{brief ? 'Conflicting evidence' : relation}</span>
        )}
        <h3 className="hf-evidence-title">{evidenceTitle(record)}</h3>
        {!brief && (
          <p className="hf-evidence-metadata">
            Version {record.evidence_version_id.slice(0, 8)}
            {!compact && evidenceContext(record) && <> · {evidenceContext(record)}</>}
            {library && (
              <RecordAttribution kind="evidence_version" id={record.evidence_version_id} inline />
            )}
          </p>
        )}
      </div>
      {!compact && <p className="evidence-content hf-evidence-excerpt">{record.content}</p>}
      <div className="section-actions">
        <ActionDialog title="Evidence detail" label="View evidence" size="sm">
          <h3 className="hf-evidence-title">{evidenceTitle(inspected)}</h3>
          <RecordAttribution kind="evidence_version" id={inspected.evidence_version_id} line />
          {brief && relation && (
            <p className="context-line">
              {relation.toLowerCase() === 'context'
                ? 'Background for this statement'
                : relation.toLowerCase() === 'supports'
                  ? 'Supports this statement'
                  : 'Challenges this statement'}
            </p>
          )}
          <p className="evidence-content">{inspected.content}</p>
          {inspected.source_refs.length > 0 && (
            <>
              <SectionHeader title="Source references" />
              <ol className="hf-evidence-references">
                {inspected.source_refs.map((ref, index) => (
                  <li key={index}>
                    <p className="evidence-content">{ref}</p>
                  </li>
                ))}
              </ol>
            </>
          )}
          <div className="actions">
            <ActionDialog
              title="Evidence record"
              label="Evidence record details"
              size="sm"
              variant="quiet"
            >
              {labels.length ? (
                <>
                  <SectionHeader title="Context" />
                  <dl className="hf-record-details">
                    {labels.map((label, i) => (
                      <div key={i}>
                        <dt>{resourceLabels[label.kind]}</dt>
                        <dd>
                          {label.name}
                          {label.version_id && <> · Version {label.version_id.slice(0, 8)}</>}
                        </dd>
                      </div>
                    ))}
                  </dl>
                </>
              ) : (
                context && <p className="hf-evidence-metadata">{context}</p>
              )}

              {!scope && <p>No scope.</p>}
              <dl className="hf-record-details">
                <AttributionDetail
                  kind="evidence_version"
                  id={inspected.evidence_version_id}
                  label="Saved by"
                />
                <dt>Evidence version ID</dt>
                <dd>
                  <code>{inspected.evidence_version_id}</code>
                </dd>
                {'evidence_id' in inspected && (
                  <>
                    <dt>Evidence family ID</dt>
                    <dd>
                      <code>{inspected.evidence_id}</code>
                    </dd>
                  </>
                )}
                {scope &&
                  Object.entries(scope)
                    .filter(([key]) => key in identityLabels)
                    .map(([key, value]) => (
                      <div key={key}>
                        <dt>{identityLabels[key]}</dt>
                        <dd>
                          <code>{value}</code>
                        </dd>
                      </div>
                    ))}
              </dl>
            </ActionDialog>
            <Button size="sm" onClick={download}>
              Download evidence record
            </Button>
            {library && (
              <Button disabled={loading} onClick={() => void loadVersions()}>
                Versions
              </Button>
            )}
            {onSelectVersion && 'study_id' in inspected && (
              <Button onClick={() => onSelectVersion(inspected as EvidenceRecord)}>
                Choose this version
              </Button>
            )}
          </div>
          {loading && <p role="status">Loading versions…</p>}
          {error && (
            <p role="alert">
              {error}
              <Button onClick={() => void inspect(inspected.evidence_version_id)}>
                Retry loading this version
              </Button>
            </p>
          )}
          {showVersions && (
            <section aria-label="Evidence versions">
              {versions.map((version) => (
                <p key={version.evidence_version_id}>
                  <Button
                    disabled={loading}
                    onClick={() => void inspect(version.evidence_version_id)}
                  >
                    Inspect {evidenceTitle(version)} · Version{' '}
                    {version.evidence_version_id.slice(0, 8)}
                  </Button>
                </p>
              ))}
              {cursor && (
                <Button disabled={loading} onClick={() => void loadVersions(true)}>
                  Load more versions
                </Button>
              )}
            </section>
          )}
        </ActionDialog>
        {action}
      </div>
    </div>
  );
}

export function EvidenceReferences({ records, ids, onRemove }: { records: EvidenceSnapshot[]; ids: string[]; onRemove?: (id: string) => void }) {
  if (!ids.length) return null;
  return <EvidenceList records={records} ids={ids} onRemove={onRemove} compact />;
}
export function EvidenceList({ records, ids = records.map(e => e.evidence_version_id), onRemove, compact = false }: { records: EvidenceSnapshot[]; ids?: string[]; onRemove?: (id: string) => void; compact?: boolean }) {
  return <div className="hf-evidence-list">{ids.map(id => { const record = records.find(e => e.evidence_version_id === id); return <article className={'evidence-record' + (compact ? ' hf-evidence-record--compact' : '')} key={id}>
    {record ? <EvidenceRecordBody record={record} compact={compact} action={onRemove && <Button size="sm" onClick={() => onRemove(id)}>Remove attachment</Button>} /> : <><StatusTag tone="warning">Evidence unavailable</StatusTag><p className="evidence-content">{id}</p>{onRemove && <Button size="sm" onClick={() => onRemove(id)}>Remove attachment</Button>}</>}
  </article>; })}</div>;
}
