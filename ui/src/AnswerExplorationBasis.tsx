import { useEffect, useState } from 'react';
import { message, type HyprnMvpApi } from './api';
import type {
  CalculationEstimateRead2,
  CalculationOutput1,
  StudyAnswerExplorationBasis1,
} from './contract';
import { Checkbox, Select } from './design';

/** Editing the answer's basis is explicit and follows the ordinary answer draft/version save. */
export function AnswerExplorationBasis({
  api,
  studyId,
  value,
  choices,
  onChange,
}: {
  api: HyprnMvpApi;
  studyId: string;
  value: StudyAnswerExplorationBasis1 | null;
  choices: { id: string; label: string }[];
  onChange: (value: StudyAnswerExplorationBasis1 | null) => void;
}) {
  const [estimates, setEstimates] = useState<CalculationEstimateRead2[]>([]);
  const [versionName, setVersionName] = useState('');
  const [outputs, setOutputs] = useState<CalculationOutput1[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const version = value?.calculation_version_id;
  useEffect(() => {
    const fence = api.fence({ studyId });
    setEstimates([]);
    setOutputs([]);
    setVersionName('');
    setError('');
    setLoading(!!version);
    if (!version) return () => fence.abort();
    void Promise.all([
      api.calculationExploration(studyId, version, 0, null, fence.signal),
      api.calculationVersion(studyId, version, fence.signal),
      (async () => {
        const items: CalculationEstimateRead2[] = [];
        let cursor: string | undefined;
        do {
          const page = await api.calculationEstimates(studyId, version, cursor, fence.signal);
          items.push(...page.items);
          cursor = page.next_cursor ?? undefined;
        } while (cursor && fence.valid());
        return items;
      })(),
    ])
      .then(([basis, calculation, items]) => {
        if (!fence.valid()) return;
        setVersionName(`${calculation.content.name} · Version ${calculation.version_number}`);
        setOutputs(
          basis.outputs.filter((o) =>
            calculation.content.criterion_bindings.some(
              (b) =>
                b.output.instance_id === o.target.instance_id &&
                b.output.port_id === o.target.port_id,
            ),
          ),
        );
        setEstimates(items.filter((e) => ['ready', 'assessed'].includes(e.state)));
      })
      .catch(async (e) => {
        await api.readFailed(e, fence);
        if (fence.valid()) setError(message(e));
      })
      .finally(() => {
        if (fence.valid()) setLoading(false);
        fence.done();
      });
    return () => fence.abort();
  }, [api, studyId, version]);
  const selected = estimates.find((e) => e.estimate_id === value?.estimate_id);
  return (
    <fieldset className="form-stack">
      <legend>Answer exploration</legend>
      <label>
        Analysis version
        <Select
          aria-label="Exploration analysis version"
          value={version ?? ''}
          onChange={(e) =>
            onChange(
              e.target.value
                ? { calculation_version_id: e.target.value, estimate_id: null, shown_outputs: [] }
                : null,
            )
          }
        >
          <option value="">No figure</option>
          {version && !choices.some((c) => c.id === version) && (
            <option value={version}>{versionName || `Saved · ${version.slice(0, 8)}`} </option>
          )}
          {choices.map((c) => (
            <option key={c.id} value={c.id}>
              {c.label}
            </option>
          ))}
        </Select>
      </label>
      {value && (
        <>
          <label>
            Assessed estimate
            <Select
              aria-label="Exploration estimate"
              value={value.estimate_id ?? ''}
              disabled={loading}
              onChange={(e) => {
                const estimate = estimates.find((i) => i.estimate_id === e.target.value);
                onChange({
                  ...value,
                  estimate_id: e.target.value || null,
                  shown_outputs: value.shown_outputs.filter(
                    (p) =>
                      !estimate ||
                      estimate.request.tolerances.some(
                        (t) =>
                          t.target.instance_id === p.instance_id && t.target.port_id === p.port_id,
                      ),
                  ),
                });
              }}
            >
              <option value="">Calculated points only</option>
              {estimates.map((e) => (
                <option key={e.estimate_id} value={e.estimate_id}>
                  {e.state === 'ready' ? 'Usable estimates' : 'Assessed, unavailable'} ·{' '}
                  {e.estimate_id.slice(0, 8)}
                </option>
              ))}
            </Select>
          </label>
          <fieldset disabled={loading}>
            <legend>Shown outcomes</legend>
            {outputs
              .filter(
                (o) =>
                  !selected ||
                  selected.request.tolerances.some(
                    (t) =>
                      t.target.instance_id === o.target.instance_id &&
                      t.target.port_id === o.target.port_id,
                  ),
              )
              .map((o) => (
                <label
                  className="hf-exploration-choice-row"
                  key={o.target.instance_id + '/' + o.target.port_id}
                >
                  <Checkbox
                    checked={value.shown_outputs.some(
                      (p) =>
                        p.instance_id === o.target.instance_id && p.port_id === o.target.port_id,
                    )}
                    onChange={(e) =>
                      onChange({
                        ...value,
                        shown_outputs: e.target.checked
                          ? [...value.shown_outputs, o.target]
                          : value.shown_outputs.filter(
                              (p) =>
                                p.instance_id !== o.target.instance_id ||
                                p.port_id !== o.target.port_id,
                            ),
                      })
                    }
                  />
                  <span>
                    {o.name}
                    <small>{o.instance_name}</small>
                  </span>
                </label>
              ))}
            {!loading && !outputs.length && (
              <p>Bind study criteria to this analysis’s outputs first.</p>
            )}
          </fieldset>
        </>
      )}
      {loading && <p role="status">Loading exploration choices…</p>}
      {error && <p role="alert">{error}</p>}
    </fieldset>
  );
}
