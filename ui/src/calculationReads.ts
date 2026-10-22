import { useEffect, useRef } from 'react';
import type { ConfigurationSummary1, HyprnMvpApi } from './api';
import type { CalculationScope } from './calculationScope';

/** Reads that belong to one study: dropped after access loss or when a newer read starts. */
export function useStudyRead(api: HyprnMvpApi, study: string) {
  const epoch = useRef(0);
  useEffect(
    () =>
      api.onSessionChange((change) => {
        if (change.kind !== 'access-lost' || change.studyId === study) epoch.current++;
      }),
    [api, study],
  );
  return async function read<T>(
    load: (signal: AbortSignal) => Promise<T>,
    apply: (value: T) => void,
    fail: (error: unknown) => void,
  ) {
    const token = ++epoch.current,
      fence = api.fence({ studyId: study });
    try {
      const value = await load(fence.signal);
      if (token === epoch.current && fence.valid()) apply(value);
    } catch (e) {
      const outcome = await api.readFailed(e, fence);
      if (token === epoch.current && outcome !== 'stale') fail(e);
    } finally {
      fence.done();
    }
  };
}

/** The saved configurations of one model version, read page by page until none is left. */
export async function scopeConfigurations(
  api: HyprnMvpApi,
  study: string,
  scope: CalculationScope,
  signal: AbortSignal,
) {
  const rows: ConfigurationSummary1[] = [];
  let cursor: string | undefined;
  do {
    const page = await api.configurationSummaries(
      study,
      { model_id: scope.model, model_revision_id: scope.revision, cursor },
      signal,
    );
    rows.push(...page.data);
    cursor = page.next_cursor ?? undefined;
  } while (cursor);
  return rows;
}
