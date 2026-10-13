import { useEffect, useRef } from 'react';
import type { HyprnMvpApi, SessionChange } from './api';

/** Subscribe one protected-content host to the shared session seam. `clear` runs
 * after sign-out, or after a confirmed access loss for `studyId` reported by any
 * host's read. The latest callback is used; it should clear protected displayed
 * content only (unsaved authoring keeps each host's own rule) and submit nothing. */
export function useAccessLoss(api: HyprnMvpApi, studyId: string | undefined, clear: (change: SessionChange) => void) {
  const latest = useRef(clear);
  latest.current = clear;
  useEffect(() => api.onSessionChange(change => {
    if (change.kind === 'signed-out' || change.kind === 'access-lost' && change.studyId === studyId) latest.current(change);
  }), [api, studyId]);
}
