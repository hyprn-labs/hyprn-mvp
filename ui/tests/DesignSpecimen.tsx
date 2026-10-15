import { useState } from 'react';
import {
  ActionGroup,
  ActionIcon,
  Assertion,
  AssertionList,
  BrandLogo,
  Button,
  DataTable,
  EvidenceStack,
  Field,
  Panel,
  ReadingSection,
  ReadingStack,
  StatusTag,
  TextInput,
} from '../src/design';
import { EvidenceRecordBody } from '../src/EvidenceView';
import type { EvidenceSnapshot } from '../src/api';

const source = (index: number): EvidenceSnapshot =>
  ({
    evidence_schema_version: '3',
    evidence_version_id: `specimen-source-${index}`,
    kind: 'note',
    title: index
      ? 'A long reference title with an explicit operating range and limitations'
      : 'Reference basis',
    content: 'Reference text preserved with its statement.',
    source_refs: [],
    resource_scope: { scope_version: '1', kind: 'study', study_id: 'specimen' },
  }) as EvidenceSnapshot;

/** Test-only reference surface: no product route, persistence or substitute API. */
export function DesignSpecimen() {
  const [value, setValue] = useState('');
  return (
    <main className="workspace-shell">
      <BrandLogo />
      <ReadingStack>
        <ReadingSection aria-label="Control recipes">
          <h1>Shared design reference</h1>
          {(['desk', 'sm', 'floor'] as const).map((size) => (
            <ActionGroup key={size} aria-label={size + ' controls'}>
              {(['primary', 'secondary', 'quiet', 'link', 'danger', 'ai'] as const).map(
                (variant) => (
                  <Button key={variant} size={size} variant={variant}>
                    {variant}
                  </Button>
                ),
              )}
              <Button size={size} icon={<ActionIcon name="close" />} aria-label={'Close ' + size} />
              <Button size={size} disabled>
                Unavailable
              </Button>
            </ActionGroup>
          ))}
          <Button size="sm">
            An unusually long action label that must remain fully readable when the screen is narrow
          </Button>
        </ReadingSection>
        <ReadingSection aria-label="Assertion rhythm">
          <h2>Assumptions and limits</h2>
          <AssertionList>
            {[0, 1, 2].map((count) => (
              <Assertion key={count} statement={'Explicit statement with ' + count + ' sources.'}>
                <EvidenceStack>
                  {Array.from({ length: count }, (_, index) => (
                    <div className="hf-evidence-item" key={index}>
                      <EvidenceRecordBody record={source(index)} compact />
                    </div>
                  ))}
                </EvidenceStack>
              </Assertion>
            ))}
          </AssertionList>
        </ReadingSection>
        <ReadingSection aria-label="Form and states">
          <Panel title="Shared fields">
            <div className="form-stack">
              <label>
                Study name
                <TextInput value={value} onChange={(event) => setValue(event.target.value)} />
              </label>
              <Field
                label="Temperature"
                value=""
                unit="K"
                state="invalid"
                message="Enter a finite temperature in K."
              />
            </div>
          </Panel>
          <ActionGroup>
            <StatusTag tone="warning">Needs review with a long explanation</StatusTag>
            <StatusTag tone="alarm">Failed</StatusTag>
            <StatusTag tone="ok">Completed</StatusTag>
          </ActionGroup>
          <DataTable
            label="Reference values"
            columns={[
              { key: 'name', label: 'Quantity' },
              { key: 'value', label: 'Value', numeric: true },
              { key: 'unit', label: 'Unit', unit: true },
            ]}
            rows={[
              { name: 'Computed zero', value: 0, unit: 'K' },
              { name: 'Unavailable output', value: null, unit: 'K' },
            ]}
          />
        </ReadingSection>
      </ReadingStack>
    </main>
  );
}
