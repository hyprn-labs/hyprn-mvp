import { useEffect, useRef, useState } from 'react';
import { accessLostText, accessUnverifiedText, message, type HyprnMvpApi } from './api';
import type { CollectionState } from './design';

/** One paged application read. Design owns presentation; API fences remain authoritative. */
export function useCollectionRead<T, C extends string | number>({
  api,
  study,
  scope,
  load,
  identity,
  enabled = true,
  prerequisite,
  onRows,
  onUnavailable,
  onSuccess,
}: {
  api?: HyprnMvpApi;
  study: string;
  scope: string;
  load: (cursor: C | undefined, signal: AbortSignal) => Promise<{ rows: T[]; next: C | null }>;
  identity: (row: T) => string;
  enabled?: boolean;
  prerequisite?: string;
  onRows?: (rows: T[]) => void;
  onUnavailable?: () => void;
  onSuccess?: () => void;
}) {
  const initialState: CollectionState =
    enabled && api ? { status: 'loading' } : { status: 'idle', reason: prerequisite };
  const key = JSON.stringify([study, scope, api?.actor, enabled, prerequisite]);
  const latest = useRef({ load, identity, onRows, onUnavailable, onSuccess, key, api });
  latest.current = { load, identity, onRows, onUnavailable, onSuccess, key, api };
  const [snapshot, setSnapshot] = useState<{
    key: string;
    rows: T[];
    cursor: C | null;
    state: CollectionState;
  }>({ key, rows: [], cursor: null, state: initialState });
  const saved = useRef(snapshot);
  const request = useRef<ReturnType<HyprnMvpApi['fence']> | null>(null);
  const epoch = useRef(0);
  const intent = useRef<C | undefined>(undefined);
  const alive = useRef(true);
  function publish(value: typeof snapshot) {
    saved.current = value;
    setSnapshot(value);
    latest.current.onRows?.(value.rows);
  }
  function clear(error = accessLostText) {
    if (!alive.current || latest.current.key !== key || latest.current.api !== api) return;
    intent.current = undefined;
    epoch.current++;
    request.current?.abort();
    request.current = null;
    publish({ key, rows: [], cursor: null, state: { status: 'failed', error } });
    latest.current.onUnavailable?.();
  }
  async function read(cursor?: C) {
    if (
      !api ||
      !enabled ||
      request.current ||
      !alive.current ||
      latest.current.key !== key ||
      latest.current.api !== api
    )
      return;
    const token = ++epoch.current;
    const fence = api.fence({ studyId: study });
    request.current = fence;
    intent.current = cursor;
    const previous =
      saved.current.key === key
        ? saved.current
        : {
            key,
            rows: [],
            cursor: null,
            state: { status: 'loading' } as CollectionState,
          };
    const ready = previous.state.status === 'ready';
    const operation = cursor !== undefined ? 'append' : 'refresh';
    const current = () =>
      alive.current &&
      token === epoch.current &&
      latest.current.key === key &&
      latest.current.api === api &&
      fence.valid();
    publish({
      ...previous,
      state: ready
        ? {
            status: 'ready',
            count: previous.rows.length,
            more: previous.cursor !== null,
            operation,
          }
        : { status: 'loading' },
    });
    try {
      const page = await latest.current.load(cursor, fence.signal);
      if (!current()) return;
      const rows = cursor === undefined ? ([] as T[]) : [...previous.rows];
      const positions = new Map(rows.map((row, index) => [latest.current.identity(row), index]));
      for (const row of page.rows) {
        const id = latest.current.identity(row),
          index = positions.get(id);
        if (index === undefined) {
          positions.set(id, rows.length);
          rows.push(row);
        } else rows[index] = row;
      }
      publish({
        key,
        rows,
        cursor: page.next,
        state: {
          status: 'ready',
          count: rows.length,
          more: page.next !== null,
        },
      });
      latest.current.onSuccess?.();
    } catch (error) {
      const outcome = await api.readFailed(error, fence);
      if (!current() || outcome === 'stale') return;
      if (outcome === 'access-lost') {
        clear();
        return;
      }
      const reason = outcome === 'transient' ? accessUnverifiedText : message(error);
      publish({
        ...previous,
        state: ready
          ? {
              status: 'ready',
              count: previous.rows.length,
              more: previous.cursor !== null,
              operation,
              error: reason,
            }
          : { status: 'failed', error: reason },
      });
    } finally {
      fence.done();
      if (token === epoch.current) request.current = null;
    }
  }
  useEffect(() => {
    alive.current = true;
    epoch.current++;
    request.current?.abort();
    request.current = null;
    intent.current = undefined;
    publish({ key, rows: [], cursor: null, state: initialState });
    const unsubscribe = api?.onSessionChange((change) => {
      if (change.kind !== 'access-lost' || change.studyId === study) clear();
    });
    if (enabled) void read();
    return () => {
      alive.current = false;
      epoch.current++;
      request.current?.abort();
      request.current = null;
      unsubscribe?.();
    };
  }, [api, key]);
  const value =
    snapshot.key === key
      ? snapshot
      : {
          key,
          rows: [] as T[],
          cursor: null,
          state: initialState,
        };
  const busy =
    value.state.status === 'loading' ||
    (value.state.status === 'ready' && !!value.state.operation && value.state.error === undefined);
  return {
    rows: value.rows,
    state: value.state,
    busy,
    clear,
    refresh: () => {
      if (!alive.current || latest.current.key !== key || latest.current.api !== api)
        return Promise.resolve();
      epoch.current++;
      request.current?.abort();
      request.current = null;
      return read();
    },
    more: () => (saved.current.cursor !== null ? read(saved.current.cursor) : Promise.resolve()),
    retry: () => read(intent.current),
  };
}
