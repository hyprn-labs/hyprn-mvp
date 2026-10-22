import type { AnalysisEstimatePlan1, PortRef } from './contract';
import {
  Checkbox,
  ErrorAllowance,
  DataTable,
  FormField,
  SectionHelp,
  Panel,
  TextInput,
} from './design';
import { unitLabel } from './unitLabels';

export type EstimateChoices = Record<string, { on: boolean; absolute: string; relative: string }>;
const key = (target: PortRef) => target.instance_id + '/' + target.port_id;
export function estimateChoices(plan: AnalysisEstimatePlan1 | null): EstimateChoices {
  return Object.fromEntries(
    (plan?.tolerances ?? []).map((t) => [
      key(t.target),
      {
        on: true,
        absolute: String(t.absolute),
        relative: String(t.relative * 100),
      },
    ]),
  );
}
export function estimatePlan(
  enabled: boolean,
  choices: EstimateChoices,
  outputs: { target: PortRef }[],
): AnalysisEstimatePlan1 | null {
  if (!enabled) return null;
  const tolerances = outputs
    .filter((o) => choices[key(o.target)]?.on)
    .map((o) => {
      const row = choices[key(o.target)];
      if (!row.absolute.trim() || !row.relative.trim())
        throw new Error('Enter both error limits, including zero.');
      const absolute = Number(row.absolute),
        relative = Number(row.relative) / 100;
      if (![absolute, relative].every((n) => Number.isFinite(n) && n >= 0))
        throw new Error('Error limits must be finite, non-negative values.');
      return { target: o.target, absolute, relative };
    });
  if (!tolerances.length) throw new Error('Choose at least one output to estimate.');
  return { tolerances };
}

export function AnalysisEstimateSettings({
  enabled,
  readOnly = false,
  onEnabled,
  choices,
  onChoices,
  outputs,
}: {
  enabled: boolean;
  readOnly?: boolean;
  onEnabled: (value: boolean) => void;
  choices: EstimateChoices;
  onChoices: (value: EstimateChoices) => void;
  outputs: { target: PortRef; label: string; units: string }[];
}) {
  if (readOnly)
    return (
      <Panel
        title="Surrogate settings"
        label="Estimate settings"
        headingLevel={3}
        bodyClassName="hf-flow"
        tone="sunken"
        className="hf-panel--compact"
      >
        {enabled ? (
          <DataTable
            regionLabel="Saved error limits"
            columns={[
              { key: 'output', label: 'Output' },
              { key: 'allowance', label: 'Allowed error' },
            ]}
            rows={outputs
              .filter((o) => choices[key(o.target)]?.on)
              .map((o) => ({
                output: o.label,
                allowance: (
                  <ErrorAllowance
                    absolute={Number(choices[key(o.target)].absolute)}
                    relative={Number(choices[key(o.target)].relative) / 100}
                    units={o.units}
                    reference="calculated output"
                  />
                ),
              }))}
          />
        ) : (
          <p>No surrogate requested.</p>
        )}
      </Panel>
    );
  return (
    <Panel
      title="Estimates"
      label="Estimate settings"
      help={<SectionHelp topic="errorLimits" />}
      tone="sunken"
      headingLevel={3}
      className="hf-panel--compact"
      bodyClassName="hf-form-stack"
    >
      <label className="calculation-member">
        <Checkbox checked={enabled} onChange={(e) => onEnabled(e.target.checked)} />
        Estimate between calculated points
      </label>
      {enabled && (
        <>
          {outputs.map((o) => {
            const id = key(o.target);
            const row = choices[id] ?? { on: false, absolute: '', relative: '' };
            const set = (change: Partial<typeof row>) =>
              onChoices({ ...choices, [id]: { ...row, ...change } });
            return (
              <div key={id} className="hf-form-section">
                <label className="calculation-member">
                  <Checkbox
                    aria-label={'Estimate ' + o.label}
                    checked={row.on}
                    onChange={(e) => set({ on: e.target.checked })}
                  />
                  {o.label}
                </label>
                <div className="hf-form-grid hf-form-grid--pair">
                  <FormField label={'Absolute limit · ' + unitLabel(o.units)}>
                    <TextInput
                      type="number"
                      step="any"
                      aria-label={o.label + ' absolute error'}
                      disabled={!row.on}
                      value={row.absolute}
                      onChange={(e) => set({ absolute: e.target.value })}
                    />
                  </FormField>
                  <FormField label="Relative limit (%)">
                    <TextInput
                      type="number"
                      step="any"
                      aria-label={o.label + ' relative error (%)'}
                      disabled={!row.on}
                      value={row.relative}
                      onChange={(e) => set({ relative: e.target.value })}
                    />
                  </FormField>
                </div>
              </div>
            );
          })}
        </>
      )}
    </Panel>
  );
}
