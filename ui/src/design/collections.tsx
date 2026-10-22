import type { ReactNode } from 'react';
import { Button } from './components';
import { ActionGroup } from './compositions';

export type CollectionEntity = { singular: string; plural: string };
export type CollectionState =
  | { status: 'loading' }
  | { status: 'failed'; error: string }
  | {
      status: 'ready';
      count: number;
      more: boolean;
      operation?: 'append' | 'refresh';
      error?: string;
    };

/** Counts describe received records; only explicit exhaustion establishes completeness. */
export function CollectionStatus({
  entity,
  state,
  matches,
  onMore,
  onRetry,
  actions,
  countInHeading = false,
}: {
  entity: CollectionEntity;
  state: CollectionState;
  matches?: number;
  onMore?: () => void;
  onRetry?: () => void;
  actions?: ReactNode;
  /** The enclosing tabs already display the complete unfiltered count. */
  countInHeading?: boolean;
}) {
  const { singular, plural } = entity;
  const title = plural.charAt(0).toUpperCase() + plural.slice(1);
  const ready = state.status === 'ready';
  const error = state.status === 'failed' || (ready && state.error !== undefined);
  const operation = ready ? state.operation : undefined;
  const busy = state.status === 'loading' || (ready && !!operation && !error);
  const verb =
    operation === 'append' ? 'loading more' : operation === 'refresh' ? 'refreshing' : 'loading';
  const count = ready ? state.count : 0;
  const more = ready && state.more;
  const quantity = `${count} ${count === 1 ? singular : plural}`;
  const coverage = quantity + (more ? ' shown · More available' : '');
  const summary =
    matches === undefined
      ? coverage
      : `${matches} ${matches === 1 ? 'match' : 'matches'} in ${coverage}`;
  const failedRead = `${title} could not be ${operation === 'refresh' ? 'refreshed' : 'loaded'}.`;
  const kept = ready ? ` The ${plural} already shown are kept.` : '';
  if (countInHeading && ready && count > 0 && !busy && !error && !more
      && matches === undefined) return null;
  return (
    <div className="hf-collection-status hf-flow" aria-busy={busy}>
      {ready && (!countInHeading || matches !== undefined || more) && (
        <p className="hf-collection-status__summary" role="status">
          {summary}
        </p>
      )}
      {state.status === 'loading' && <p role="status">Loading {plural}…</p>}
      {error && (
        <div role="alert">
          <p>
            {operation === 'append'
              ? `More ${plural} could not be loaded. The ${plural} already shown are kept.`
              : failedRead + kept}
          </p>
          {state.error && <p>{state.error}</p>}
        </div>
      )}
      {ready &&
        !error &&
        !busy &&
        (matches === 0 ? (
          <p>
            {more
              ? `No matches in the ${plural} shown. Load more ${plural} or clear the filters.`
              : `No ${plural} match these filters.`}
          </p>
        ) : (
          count === 0 && !more && <p>No {plural} yet.</p>
        ))}
      <ActionGroup>
        {error && onRetry ? (
          <Button onClick={onRetry}>
            Retry {verb} {plural}
          </Button>
        ) : (
          more &&
          onMore && (
            <Button disabled={busy} onClick={onMore}>
              {busy && operation === 'append' ? `Loading more ${plural}…` : `Load more ${plural}`}
            </Button>
          )
        )}
        {busy && operation === 'refresh' && <p role="status">Refreshing {plural}…</p>}
        {actions}
      </ActionGroup>
    </div>
  );
}
