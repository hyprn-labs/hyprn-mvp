import { useCollectionRead } from './useCollectionRead';
import { CollectionStatus } from './design';
import { useEffect, useRef, useState } from 'react';
import { Button, DialogActions, DialogFrame, SectionHeader, StatusTag, TextInput } from './design';
import { unitLabel } from './unitLabels';
import { HyprnMvpApi, message, type ResultSourcePage3 } from './api';
/** A verified scalar source: results 2 (with criteria) or results 3 (execution only). */
export type ResultSource = ResultSourcePage3['items'][number];
import { RunOutcomes, resultOutcomes } from './runStatus';

/** Inventory contains retained public labels and verified scalar bytes only. */
export function ResultPicker({
  api,
  studyId,
  label,
  onChoose,
  onClose,
}: {
  api: HyprnMvpApi;
  studyId: string;
  label: string;
  onChoose: (source: ResultSource) => void;
  onClose: () => void;
}) {
  const [filter, setFilter] = useState('');
  const dialog = useRef<HTMLDialogElement>(null);
  const actor = api.actor;
  const collection = useCollectionRead<ResultSource, string>({
    api,
    study: studyId,
    scope: label,
    load: async (cursor) => {
      const page = await api.resultSourcesPage(studyId, 25, cursor);
      return { rows: page.items, next: page.next_cursor };
    },
    identity: (row) => JSON.stringify([row.source_run_id, row.source_output]),
  });
  const items = collection.rows,
    busy = collection.busy;
  useEffect(() => {
    const invoking = document.activeElement as HTMLElement;
    const element = dialog.current;
    element?.showModal();
    return () => {
      element?.close();
      requestAnimationFrame(() => {
        if (invoking?.isConnected) invoking.focus();
      });
    };
  }, [api, studyId, actor]);
  const visible = items.filter((i) =>
    `${i.labels.run_name} ${i.labels.model_name ?? ''} ${i.labels.instance_name} ${i.labels.output_name} ${i.source_run_id}`
      .toLowerCase()
      .includes(filter.toLowerCase()),
  );
  return (
    <DialogFrame
      ref={dialog}
      className="evidence-picker"
      aria-label={`Use a run result for ${label}`}
      onKeyDown={(e) => {
        if (e.key === 'Escape') {
          e.preventDefault();
          e.stopPropagation();
          onClose();
        }
      }}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
    >
      <SectionHeader level={2} title="Use a run result" help="runOutputs" />
      <p>
        Choose a run output for {label}. Execution and criteria are reported separately. Criteria
        are fixed-threshold checks, not a scientific assessment.
      </p>
      <label>
        Filter results
        <TextInput type="search" value={filter} onChange={(e) => setFilter(e.target.value)} />
      </label>
      <CollectionStatus
        entity={{ singular: 'result', plural: 'results' }}
        state={collection.state}
        matches={filter ? visible.length : undefined}
        onMore={() => void collection.more()}
        onRetry={() => void collection.retry()}
      />
      <div className="evidence-options">
        {visible.map((i) => (
          <article
            className="evidence-record"
            key={`${i.source_run_id}/${i.source_output.instance_id}/${i.source_output.port_id}`}
          >
            <h3>{i.labels.run_name}</h3>
            <p>{i.labels.model_name ?? 'Unnamed model'}</p>
            <p>
              Component: {i.labels.instance_name} · Output: {i.labels.output_name}
            </p>
            <p>
              <strong>
                {i.value} {unitLabel(i.units)}
              </strong>
            </p>
            <RunOutcomes
              outcomes={resultOutcomes(
                i.outcomes.execution,
                'criteria' in i.outcomes ? i.outcomes.criteria : undefined,
              )}
            />
            <p>
              Units as produced by the source run. Availability is checked again before the run.
            </p>
            <Button disabled={busy} onClick={() => onChoose(i)}>
              Use this result · {i.labels.instance_name} · {i.labels.output_name}
            </Button>
          </article>
        ))}
      </div>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
      </DialogActions>
    </DialogFrame>
  );
}
