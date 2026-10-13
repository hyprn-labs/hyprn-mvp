import { useEffect, useState, useId } from 'react';
import { Button, Select, TextInput } from './design';
import { HyprnMvpApi, message } from './api';
import { evidenceAccessLost } from './EvidenceView';
import type { UnitCatalog1 } from './contract';
import { type UnitDraft, unitDeclaration } from './unitLabels';

export function useUnitCatalog(api: HyprnMvpApi, studyId: string, resource = '') {
  const [catalog, setCatalog] = useState<UnitCatalog1 | null>(null);
  const [error, setError] = useState(''), [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);
  const scope = studyId + '/' + api.actor + '/' + resource;
  const [loadedScope, setLoadedScope] = useState('');
  useEffect(() => {
    if (!studyId || !api.actor) { setCatalog(null); setError(''); setLoading(false); return; }
    const abort = new AbortController(); let current = true;
    setCatalog(null); setError(''); setLoading(true); setLoadedScope(scope);
    void api.unitCatalog(studyId, abort.signal).then(value => { if (current) setCatalog(value); })
      .catch(e => { if (current) { setCatalog(null); if (evidenceAccessLost(e)) { api.onAuthorizationLoss(); } setError(evidenceAccessLost(e) ? 'Access to this resource is no longer available.' : 'Unit guidance is unavailable. Retry unit guidance. Your edits are kept. ' + message(e)); } })
      .finally(() => { if (current) setLoading(false); });
    return () => { current = false; abort.abort(); };
  }, [api, scope, attempt]);
  return {catalog: loadedScope === scope ? catalog : null, error: loadedScope === scope ? error : '', loading: loadedScope !== scope || loading, retry: () => setAttempt(n => n + 1)};
}
export type UnitGuidanceState = ReturnType<typeof useUnitCatalog>;
export function UnitGuidance({guidance}: {guidance: UnitGuidanceState}) {
  return <>{guidance.loading && <p role="status">Loading unit guidance…</p>}{guidance.error && <div role="alert"><p>{guidance.error}</p><Button onClick={guidance.retry}>Retry unit guidance</Button></div>}</>;
}
type Props = { label: string; value: UnitDraft; onChange: (value: UnitDraft) => void; catalog: UnitCatalog1 | null; disabled?: boolean; resolvedOnly?: boolean };
export function UnitEditor({label,value,onChange,catalog,disabled,resolvedOnly=false}: Props) {
  const suggestions = useId();
  let error = '';
  if (catalog && value.kind === 'physical') { try { unitDeclaration(value,catalog); } catch (e) { error = message(e); } }
  return <div>
    <label>{label}<Select aria-label={label} disabled={disabled || !catalog} value={value.kind} onChange={e => onChange(e.target.value === 'physical' ? {kind:'physical',expression:''} : e.target.value === 'dimensionless' ? {kind:'dimensionless'} : {kind:'unspecified'})}>
      <option value="unspecified" disabled={resolvedOnly}>Not specified</option><option value="dimensionless">Dimensionless</option><option value="physical">Physical units</option>
    </Select></label>
    {value.kind === 'physical' && <><label>{label} spelling<br/><TextInput aria-label={label+' spelling'} list={suggestions} value={value.expression} maxLength={64} disabled={disabled} aria-invalid={!!error} onChange={e => onChange({kind:'physical',expression:e.target.value})}/></label>
      <datalist id={suggestions}>{catalog?.supported_units.map(unit=><option key={unit} value={unit}/>)}</datalist><p>Choose a supported spelling from the suggestions.</p></>}
    {error && <p role="alert">{error}</p>}
  </div>;
}
