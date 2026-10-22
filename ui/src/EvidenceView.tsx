import { OpenLink } from './design';
import type { EvidenceSnapshotRead4 } from './contract';
import { useCollectionRead } from './useCollectionRead';
import { CollectionStatus } from './design';
import { readEvidenceContent, evidenceSummary } from './evidenceContent';
import { EvidenceDisclosure } from './ContextDetails';
import { RecordDetails } from './design';
import { ActionGroup } from './design';
import { EvidenceStack } from './design';
import { AttributionDetail, RecordAttribution, useAttribution } from './attribution';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { ApiError, HyprnMvpApi, message, type EvidenceRecord, type EvidenceSnapshot } from './api';
import { Button, SectionHeader, StatusTag, EvidenceReading } from './design';

export const evidenceTitle = (record: EvidenceSnapshotRead4) =>
  'title' in record ? record.title : 'Evidence note';
export const evidenceContext = (record: EvidenceSnapshotRead4) =>
  'resource_scope' in record && record.resource_scope.kind === 'study'
    ? 'Study evidence'
    : 'recorded_context' in record
      ? record.recorded_context.label
      : null;
export const evidenceAccessLost = (error: unknown) =>
  error instanceof ApiError &&
  ['unauthenticated', 'forbidden', 'resource_not_found'].includes(error.detail.code);
const identityLabels: Record<string, string> = {
  study_id: 'Study ID',
  model_id: 'Model ID',
  model_revision_id: 'Model version ID',
  definition_id: 'Definition ID',
  definition_version_id: 'Definition version ID',
  instance_id: 'Component ID',
  port_id: 'Quantity ID',
  connection_id: 'Connection ID',
  configuration_revision_id: 'Configuration version ID',
  criterion_id: 'Criterion ID',
  run_id: 'Run ID',
};
const resourceLabels = {
  study: 'Study',
  model: 'Model',
  definition: 'Definition',
  instance: 'Component',
  port: 'Quantity',
  connection: 'Connection',
  configuration: 'Configuration',
  criterion: 'Criterion',
  run: 'Run',
};

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
  contextual = false,
}: {
  record: EvidenceSnapshotRead4;
  action?: ReactNode;
  library?: { api: HyprnMvpApi; studyId: string };
  onSelectVersion?: (record: EvidenceRecord) => void;
  onUnavailable?: () => void;
  compact?: boolean;
  contextual?: boolean;
  brief?: boolean;
  /** Relationship word shown before the title (assumption evidence rows). */ relation?: string;
}) {
  const [inspected, setInspected] = useState(record);
  const [loading, setLoading] = useState(false),
    [error, setError] = useState(''),
    [unavailable, setUnavailable] = useState(false),
    [showVersions, setShowVersions] = useState(false);
  const generation = useRef(0),
    request = useRef<AbortController | null>(null),
    actor = library?.api.actor;
  useEffect(() => {
    setInspected(record);
    setShowVersions(false);
    setUnavailable(false);
    setError('');
    return () => {
      generation.current++;
      request.current?.abort();
    };
  }, [record, library?.api, library?.studyId, actor]);
  async function read(action: (signal: AbortSignal, current: () => boolean) => Promise<void>) {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    const token = ++generation.current;
    setLoading(true);
    setError('');
    try {
      await action(
        controller.signal,
        () =>
          token === generation.current &&
          actor === library?.api.actor &&
          !controller.signal.aborted,
      );
    } catch (e) {
      if (token === generation.current && actor === library?.api.actor) {
        if (evidenceAccessLost(e)) {
          setUnavailable(true);
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
  const collection = useCollectionRead<EvidenceRecord, string>({
    api: library?.api,
    study: library?.studyId ?? '',
    scope: record.evidence_version_id,
    enabled: !!library && showVersions && 'evidence_id' in record,
    load: async (cursor, signal) => {
      if (!library || !('evidence_id' in record)) throw new Error('Evidence family unavailable.');
      const page = await library.api.evidenceVersions(
        library.studyId,
        record.evidence_id,
        { limit: 20, cursor },
        signal,
      );
      if (
        page.data.some(
          (value) => value.evidence_id !== record.evidence_id || value.study_id !== library.studyId,
        )
      )
        throw new Error('Evidence versions do not belong to this family.');
      return { rows: page.data, next: page.next_cursor };
    },
    identity: (row) => row.evidence_version_id,
    onUnavailable: () => {
      setUnavailable(true);
      onUnavailable?.();
    },
  });
  const versions = collection.rows;
  async function inspect(version: string) {
    if (!library) return;
    await read(async (signal, current) => {
      const exact = await library.api.evidenceVersion(library.studyId, version, signal);
      if (current()) setInspected(exact);
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
  const author = useAttribution('evidence_version', inspected.evidence_version_id);
  if (unavailable)
    return (
      <p role="alert">
        <StatusTag tone="warning">Evidence unavailable</StatusTag> Access to this evidence is no
        longer available. Choose another record or remove the attachment.
      </p>
    );
  const structured = readEvidenceContent(inspected.content);
  const scope = 'resource_scope' in inspected ? inspected.resource_scope : null;
  const context = evidenceContext(inspected);
  const labels =
    'recorded_context' in inspected && scope?.kind !== 'study'
      ? inspected.recorded_context.resource_labels
      : [];
  return (
    <div className={'hf-evidence-card' + (compact ? ' hf-evidence-card--compact' : '')}>
      {!contextual && !compact && (
        <div className="hf-evidence-heading">
          {relation && (!brief || relation.toLowerCase() === 'challenges') && (
            <span className="hf-evidence-relation">
              {brief ? 'Conflicting evidence' : relation}
            </span>
          )}
          <h3 className="hf-evidence-title">{evidenceTitle(record)}</h3>
          {!brief && (
            <p className="hf-evidence-metadata">
              {!compact && evidenceContext(record)}
              {library && (
                <RecordAttribution kind="evidence_version" id={record.evidence_version_id} inline />
              )}
            </p>
          )}
        </div>
      )}
      {!compact && !contextual && (
        <p className="evidence-content hf-evidence-excerpt">{evidenceSummary(record.content)}</p>
      )}
      <div className="hf-evidence-content">
        <EvidenceReaderFrame contextual={contextual} version={record.evidence_version_id}>
          <h3 className="hf-evidence-title">{evidenceTitle(inspected)}</h3>
          <RecordDetails kind="Evidence" versionId={inspected.evidence_version_id}>
            {labels.length ? (
              <>
                <SectionHeader title="Context" />
                <dl className="hf-record-details">
                  {labels.map((label, i) => (
                    <div key={i}>
                      <dt>{resourceLabels[label.kind]}</dt>
                      <dd>{label.name}</dd>
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
            {structured && (
              <p>Excerpt transcribed by the author; not automatically matched to the source.</p>
            )}
            <Button size="sm" onClick={download}>
              Download evidence record
            </Button>
          </RecordDetails>
          {brief && relation && <p className="hf-evidence-relation">{relation}</p>}
          <EvidenceReading
            passages={
              'citations' in inspected
                ? inspected.citations.map((citation) => ({
                    reference: citation.title || citation.filename,
                    excerpt: citation.quoted_text ?? undefined,
                    location:
                      citation.locator.kind === 'pdf_page'
                        ? `p. ${citation.locator.page}`
                        : citation.locator.kind === 'original_file'
                          ? citation.locator.section_label
                          : citation.locator.line_start !== undefined
                            ? `Lines ${citation.locator.line_start}–${citation.locator.line_end ?? citation.locator.line_start}`
                            : `Characters ${citation.locator.start}–${citation.locator.end}`,
                  }))
                : undefined
            }
            assistant={!!author}
            excerpt={structured?.excerpt}
            reference={structured?.source_reference}
            location={structured?.location}
            explanation={structured?.explanation ?? inspected.content}
            attribution={
              <RecordAttribution kind="evidence_version" id={inspected.evidence_version_id} line />
            }
            references={inspected.source_refs.filter((ref) => ref !== structured?.source_reference)}
          />
          <ActionGroup className="actions">
            {library && (
              <Button disabled={loading} onClick={() => setShowVersions(true)}>
                Versions
              </Button>
            )}
            {onSelectVersion && 'study_id' in inspected && (
              <Button onClick={() => onSelectVersion(inspected as EvidenceRecord)}>
                Choose this version
              </Button>
            )}
          </ActionGroup>
          {loading && <p role="status">Loading evidence version…</p>}
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
                  <OpenLink
                    disabled={loading}
                    onClick={() => void inspect(version.evidence_version_id)}
                  >
                    Inspect {evidenceTitle(version)} · Version{' '}
                    {version.evidence_version_id.slice(0, 8)}
                  </OpenLink>
                </p>
              ))}
              <CollectionStatus
                entity={{ singular: 'evidence version', plural: 'evidence versions' }}
                state={collection.state}
                onMore={() => void collection.more()}
                onRetry={() => void collection.retry()}
              />
            </section>
          )}
        </EvidenceReaderFrame>
        {action && <ActionGroup className="actions">{action}</ActionGroup>}
      </div>
    </div>
  );
}

export function EvidenceReferences({
  records,
  ids,
  onRemove,
  label,
}: {
  label?: string;
  records: EvidenceSnapshot[];
  ids: string[];
  onRemove?: (id: string) => void;
}) {
  if (!ids.length) return null;
  return <EvidenceList records={records} ids={ids} onRemove={onRemove} label={label} compact />;
}
export function EvidenceList({
  records,
  ids = records.map((e) => e.evidence_version_id),
  onRemove,
  links = [],
  label,
}: {
  label?: string;
  records: EvidenceSnapshot[];
  ids?: string[];
  onRemove?: (id: string) => void;
  compact?: boolean;
  links?: Array<{ evidence_version_id: string; relation?: string; locator?: string }>;
}) {
  const distinct = [...new Set(ids)];
  if (!distinct.length) return null;
  return (
    <>
      {links.some((link) => link.relation?.toLowerCase() === 'challenges') && (
        <StatusTag tone="warning">Conflicting evidence</StatusTag>
      )}
      <EvidenceDisclosure
        count={distinct.length}
        version={JSON.stringify([distinct, links, records])}
      >
        {label && <p className="hf-claim__statement">{label}</p>}
        <EvidenceStack className="hf-evidence-list">
          {distinct.map((id) => {
            const record = records.find((e) => e.evidence_version_id === id);
            return (
              <article className="evidence-record" key={id}>
                {links
                  .filter((link) => link.evidence_version_id === id)
                  .map((link, index) => (
                    <div className="hf-evidence-relation" key={index}>
                      {link.relation && (
                        <p>
                          {link.relation.toLowerCase() === 'supports'
                            ? 'Supports this statement'
                            : link.relation.toLowerCase() === 'challenges'
                              ? 'Challenges this statement'
                              : 'Background for this statement'}
                        </p>
                      )}
                      {link.locator && <p className="context-line">{link.locator}</p>}
                    </div>
                  ))}
                {record ? (
                  <EvidenceRecordBody record={record} contextual />
                ) : (
                  <>
                    <StatusTag tone="warning">Evidence unavailable</StatusTag>
                    <p className="evidence-content">{id}</p>
                  </>
                )}
                {onRemove && (
                  <Button size="sm" onClick={() => onRemove(id)}>
                    Remove attachment
                  </Button>
                )}
              </article>
            );
          })}
        </EvidenceStack>
      </EvidenceDisclosure>
    </>
  );
}

function EvidenceReaderFrame({
  contextual,
  children,
  version,
}: {
  contextual: boolean;
  version: string;
  children: ReactNode;
}) {
  return contextual ? (
    <div className="hf-evidence-reader">{children}</div>
  ) : (
    <EvidenceDisclosure count={1} version={version} live>
      {children}
    </EvidenceDisclosure>
  );
}
