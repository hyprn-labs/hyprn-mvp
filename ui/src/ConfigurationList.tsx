import { OpenLink } from './design';
import { useCollectionRead } from './useCollectionRead';
import { CollectionStatus } from './design';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import type { ConfigurationSummary1, HyprnMvpApi } from './api';
import type { CalculationScope } from './calculationScope';
import { ActionGroup, Button, Panel, ResourceCard, StatusTag } from './design';
import { message } from './api';

export function ConfigurationList({
  api,
  study,
  scope,
  onOpen,
  actions,
}: {
  api: HyprnMvpApi;
  study: string;
  scope: CalculationScope;
  onOpen: (id: string) => void;
  actions?: ReactNode;
}) {
  const collection = useCollectionRead<ConfigurationSummary1, string>({
    api,
    study,
    scope: JSON.stringify([scope.model, scope.revision]),
    enabled: !!scope.revision,
    prerequisite: 'Save a model version in Models to create configurations.',
    load: async (cursor, signal) => {
      const page = await api.configurationSummaries(
        study,
        {
          model_id: scope.model,
          model_revision_id: scope.revision,
          cursor,
        },
        signal,
      );
      return { rows: page.data, next: page.next_cursor ?? null };
    },
    identity: (row) => row.configuration_revision_id,
  });
  const rows = collection.rows;
  // Configuration versions marked as references (baselines) for the selected model.
  const [marked, setMarked] = useState<ReadonlySet<string>>(new Set());
  const [marking, setMarking] = useState<string | null>(null);
  const [markError, setMarkError] = useState<unknown>(null);
  const epoch = useRef(0);
  async function loadMarks() {
    const token = epoch.current,
      read = api.fence({ studyId: study });
    try {
      const marks = await api.referenceMarks(study, scope.model, read.signal);
      if (token === epoch.current && read.valid())
        setMarked(new Set(marks.items.map((m) => m.configuration_revision_id)));
    } catch (e) {
      const outcome = await api.readFailed(e, read);
      if (token === epoch.current && outcome !== 'stale') setMarkError(e);
    } finally {
      read.done();
    }
  }
  /** Set or clear one mark; the configuration version itself never changes. */
  async function toggleMark(id: string) {
    const token = epoch.current;
    setMarking(id);
    setMarkError(null);
    try {
      const state = await api.setReferenceMark(study, id, marked.has(id) ? 'clear' : 'set');
      if (token !== epoch.current) return;
      setMarked((previous) => {
        const next = new Set(previous);
        if (state.mark) next.add(id);
        else next.delete(id);
        return next;
      });
    } catch (e) {
      if (token === epoch.current) setMarkError(e);
    } finally {
      if (token === epoch.current) setMarking(null);
    }
  }
  useEffect(() => {
    setMarked(new Set());
    setMarking(null);
    setMarkError(null);
    if (scope.revision) {
      void loadMarks();
    }
    return () => {
      epoch.current++;
    };
  }, [api, study, scope.model, scope.revision]);
  useEffect(
    () =>
      api.onSessionChange((change) => {
        if (change.kind !== 'access-lost' || change.studyId === study) {
          epoch.current++;
          setMarked(new Set());
          setMarking(null);
          setMarkError(null);
        }
      }),
    [api, study],
  );
  return (
    <Panel label="Configurations" bodyClassName="hf-flow">
      <CollectionStatus
        entity={{ singular: 'configuration version', plural: 'configuration versions' }}
        state={collection.state}
        actions={actions}
        onMore={() => void collection.more()}
        onRetry={() => void collection.retry()}
      />
      {markError != null && <p role="alert">{message(markError)}</p>}
      {rows.map((c) => (
        <ResourceCard
          key={c.configuration_revision_id}
          level={3}
          title={c.name}
          facts={[
            `${c.input_count} inputs`,
            marked.has(c.configuration_revision_id) && (
              <StatusTag tone="inert">Reference</StatusTag>
            ),
          ]}
          actions={
            <ActionGroup>
              <OpenLink onClick={() => onOpen(c.configuration_revision_id)}>
                Open configuration
              </OpenLink>
              <Button
                disabled={marking !== null || !!api.pending}
                aria-label={
                  (marked.has(c.configuration_revision_id)
                    ? 'Clear reference mark of '
                    : 'Mark as reference: ') + c.name
                }
                onClick={() => void toggleMark(c.configuration_revision_id)}
              >
                {marked.has(c.configuration_revision_id)
                  ? 'Clear reference mark'
                  : 'Mark as reference'}
              </Button>
            </ActionGroup>
          }
        />
      ))}
    </Panel>
  );
}
