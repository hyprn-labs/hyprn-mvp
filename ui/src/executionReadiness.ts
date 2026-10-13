import { useEffect, useRef, useState } from 'react';
import { HyprnMvpApi, accessLostText, accessUnverifiedText, message, type ExecutionReadiness } from './api';
import { useAccessLoss } from './accessLoss';

export function useExecutionReadiness(api: HyprnMvpApi, studyId: string) {
  const [readiness, setReadiness] = useState<ExecutionReadiness | null>(null), [readinessError, setReadinessError] = useState(''), [clock, setClock] = useState(Date.now());
  const alive = useRef(true), generation = useRef(0);
  const checking = useRef(false), lost = useRef(false);
  // A confirmed denial stops the periodic check; an explicit check may try again.
  useAccessLoss(api, studyId, change => { if (change.kind !== 'access-lost') return; lost.current = true; generation.current++; checking.current = false; setReadiness(null); setReadinessError(accessLostText); });
  async function refreshReadiness(manual = true) {
    if (checking.current || !manual && lost.current) return;
    checking.current = true; lost.current = false;
    const token = ++generation.current, read = api.fence({ studyId });
    const current = () => alive.current && token === generation.current && read.valid();
    try { const value = await api.readiness(studyId); if (current()) { setReadiness(value); setReadinessError(''); setClock(Date.now()); } }
    catch (e) {
      const outcome = await api.readFailed(e, read);
      if (outcome !== 'stale' && outcome !== 'access-lost' && current()) { setReadiness(null); setReadinessError(outcome === 'transient' ? accessUnverifiedText : message(e)); }
    }
    finally { read.done(); if (token === generation.current) checking.current = false; }
  }
  useEffect(() => { alive.current = true; checking.current = false; lost.current = false; setReadiness(null); void refreshReadiness(); const timer = setInterval(() => setClock(Date.now()), 1000); const refresh = setInterval(() => void refreshReadiness(false), 20000); return () => { alive.current = false; generation.current++; clearInterval(timer); clearInterval(refresh); }; }, [api, studyId]);
  const ready = readiness?.status === 'ready' && !!readiness.expires_at && Date.parse(readiness.expires_at) > clock;
  const readinessStatus = readiness?.expires_at && Date.parse(readiness.expires_at) <= clock ? 'unknown' : readiness?.status ?? 'unknown';
  return { readiness, readinessError, readinessStatus, ready, refreshReadiness: () => refreshReadiness() };
}
