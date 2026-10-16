import { useRef, useState } from 'react';
import {
  ActionDialog,
  AttributionChip,
  Checkbox,
  ContextualPanel,
  ClaimButton,
  ClaimCard,
  CriterionRecord,
  DetailTabs,
  DialogFrame,
  Disclosure,
  FilePicker,
  GraphCanvas,
  InferenceBlock,
  Ledger,
  ModelNode,
  NavigationRail,
  Progress,
  Readout,
  RecordBar,
  RecordState,
  ResourceCard,
  SectionHeader,
  Select,
  SettingsSection,
  SourceChip,
  SourceSurface,
  Tabs,
  TextArea,
  WorkspaceShell,
  WorkflowNavigation,
  AssistantPane,
  ReadingContents,
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
  QuantitySlider,
  AnswerExplorationPanel,
  InterpretationPanel,
  QuantityResult,
  ResponseCurve,
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
  const [tab, setTab] = useState('first');
  const [checked, setChecked] = useState(false);
  const [quantity, setQuantity] = useState<number | null>(1);
  const [context, setContext] = useState(true);
  const [assistant, setAssistant] = useState(true);
  const dialog = useRef<HTMLDialogElement>(null);
  const code = useRef<HTMLTextAreaElement>(null);
  const bytes = "# Exact source <tag>\noutputs['value'] = inputs['value'] ** 2\n";
  const items = [
    { id: 'first', label: 'First view' },
    { id: 'second', label: 'Second view with a long label' },
  ];
  const recipeControls = (where: string) => (
    <ActionGroup aria-label={where + ' recipe controls'}>
      {(['sm', 'desk', 'floor'] as const).map((size) => (
        <Button key={size} size={size} data-recipe={size}>
          Same action
        </Button>
      ))}
    </ActionGroup>
  );
  return (
    <main className="workspace-shell">
      <div data-components="BrandLogo">
        <BrandLogo />
      </div>
      <ReadingStack>
        <ReadingSection
          aria-label="Answer exploration recipes"
          data-components={
            'QuantitySlider QuantityResult ResponseCurve AnswerExplorationPanel InterpretationPanel'
          }
        >
          <AnswerExplorationPanel
            settings={<Button>Sample settings</Button>}
            categories={<span>Illustrative category</span>}
            footer={<Button>Open model</Button>}
          >
            <QuantitySlider
              label="Illustrative input"
              units="m"
              values={[0, 1, 2]}
              value={quantity}
              onChange={setQuantity}
            />
            <QuantityResult value={0} units="m" state="calculated" />
            <QuantityResult value={2} units="m" state="estimated" />
            <QuantityResult value={null} units="m" state="unavailable" reason="No estimate" />
            <ResponseCurve
              label="Illustrative response"
              axis="Input (m)"
              units="m"
              selected={1}
              points={[
                { x: 0, y: 0 },
                { x: 1, y: 2 },
                { x: 2, y: null },
              ]}
              calculated={[{ x: 0, y: 0 }]}
            />
          </AnswerExplorationPanel>
          <InterpretationPanel>Illustrative prose; no scientific result.</InterpretationPanel>
        </ReadingSection>
        <ReadingSection
          aria-label="Control recipes"
          data-components="Button ActionIcon ActionGroup"
        >
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
        <ReadingSection
          aria-label="Assertion rhythm"
          data-components="Assertion AssertionList EvidenceStack ReadingSection ReadingStack"
        >
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
        <ReadingSection
          aria-label="Form and states"
          data-components="Panel Field TextInput StatusTag DataTable"
        >
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

        <ReadingSection
          aria-label="Workspace recipes"
          data-components={[
            'WorkspaceShell',
            'NavigationRail',
            'WorkflowNavigation',
            'ResourceCard',
            'SettingsSection',
            'ContextualPanel',
            'AssistantPane',
            'ClaimCard',
            'ClaimButton',
          ].join(' ')}
        >
          <WorkspaceShell
            navigation={
              <NavigationRail
                primary={recipeControls('shell')}
                study={'Long study ' + 'measurement-'.repeat(12)}
                section="Scientific context"
                items={items}
                value={tab}
                onChange={setTab}
              />
            }
            context={
              context && (
                <ContextualPanel title="Specimen context" onClose={() => setContext(false)}>
                  {recipeControls('context')}
                  <ClaimCard
                    kind="Assumption"
                    scope="Illustrative saved configuration"
                    statement={'Full statement with a long identifier ' + 'quantity_'.repeat(18)}
                    limits="Only the measured interval is supported."
                    attribution={
                      <AttributionChip agent="Example assistant" user="Example engineer" />
                    }
                  >
                    <EvidenceStack>
                      <div className="hf-context-source">
                        <p>Supports</p>
                        <p>Named evidence content; source passage unavailable.</p>
                        {recipeControls('evidence')}
                      </div>
                    </EvidenceStack>
                  </ClaimCard>
                </ContextualPanel>
              )
            }
            assistant={
              assistant && (
                <AssistantPane
                  state="disconnected"
                  context="Current illustrative study"
                  onClose={() => setAssistant(false)}
                />
              )
            }
          >
            <ResourceCard
              title="Resource with full title and independently available actions"
              metadata={<RecordState state="saved" />}
              actions={recipeControls('card')}
            >
              <p>Full description with a long identifier {'definition_'.repeat(20)}.</p>
            </ResourceCard>
            <SettingsSection title="Presentation">
              <label>
                Display preference
                <Select value={tab} onChange={(e) => setTab(e.target.value)}>
                  {items.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.label}
                    </option>
                  ))}
                </Select>
              </label>
              {recipeControls('settings')}
            </SettingsSection>
            <WorkflowNavigation items={items} value={tab} onChange={setTab} />
            <ActionGroup>
              <Button onClick={() => setContext(true)}>Show specimen context</Button>
              <Button onClick={() => setAssistant(true)}>Show specimen assistant</Button>
            </ActionGroup>
            <div aria-label="Statement set states">
              {[
                { ids: ['one', 'one', 'two'], state: 'complete' as const, label: 'Complete set' },
                { ids: ['one'], state: 'partial' as const, label: 'Partial set' },
                { ids: [], state: 'partial' as const, label: 'Loading set' },
                { ids: [], state: 'complete' as const, label: 'Empty set' },
                { ids: [], state: 'unknown' as const, label: 'Unavailable set' },
              ].map((set) => (
                <ClaimButton
                  key={set.label}
                  set={{ owner: 'example', version: 'v1', ...set }}
                  onClick={() => setContext(true)}
                />
              ))}
            </div>
          </WorkspaceShell>
        </ReadingSection>
        <ReadingSection
          aria-label="Scientific records"
          data-components={[
            'Readout',
            'Ledger',
            'SourceChip',
            'InferenceBlock',
            'RecordBar',
            'RecordState',
            'AttributionChip',
            'CriterionRecord',
          ].join(' ')}
        >
          <RecordBar
            title="Saved run · read-only"
            detail="Illustrative specimen"
            onReturn={() => {}}
          />
          <ActionGroup>
            {(['new', 'draft', 'changed', 'saved'] as const).map((state) => (
              <RecordState key={state} state={state} />
            ))}
          </ActionGroup>
          <Ledger
            label="Independent facets"
            facets={[
              { label: 'Execution', value: 'Completed', tone: 'ok' },
              { label: 'Criteria', value: '1 of 1 not met', tone: 'alarm' },
              { label: 'Applicability', value: 'Not established', tone: 'inert' },
            ]}
          />
          <ActionGroup>
            {(['alarm', 'warning', 'advisory', 'ok', 'inert', 'running'] as const).map((tone) => (
              <StatusTag key={tone} tone={tone}>
                {tone} state with a full explanation
              </StatusTag>
            ))}
          </ActionGroup>
          {(['computed', 'measured', 'sourced', 'inferred'] as const).map((basis) => (
            <Readout
              key={basis}
              value={0}
              unit="kPa"
              label={basis}
              basis={basis}
              source="Illustrative basis"
            />
          ))}
          <Readout
            value={null}
            unit="kPa"
            label="Unavailable quantity"
            missingText="not computed · missing input"
          />
          <Readout value={1e-10} unit="m" size="sm" label="Small nonzero value" />
          <SourceChip
            label="Example primary source"
            locator="Example section"
            onClick={() => dialog.current?.showModal()}
          />
          <SourceChip
            label="Example secondary source"
            authority="secondary"
            onClick={() => dialog.current?.showModal()}
          />
          <SourceChip
            label="Unverified source"
            authority="unverified"
            onClick={() => dialog.current?.showModal()}
          />
          {(['proposed', 'applied', 'discarded', 'checking'] as const).map((status) => (
            <InferenceBlock
              key={status}
              title="Illustrative proposal"
              status={status}
              basis={[<Readout key="basis" value={0} unit="m" source="Illustrative run" />]}
            >
              <p>Review the stated assumption; a computed result does not establish validity.</p>
            </InferenceBlock>
          ))}
          <CriterionRecord
            number={1}
            target="pressure"
            comparison="less than"
            threshold={1}
            units="kPa"
            tolerances={{ absolute: 0, relative: null }}
            evaluation={{
              label: 'Not evaluated',
              tone: 'advisory',
              actual: null,
              reason: 'Output not computed',
            }}
          />
          <CriterionRecord
            number={2}
            target={null}
            comparison="less than"
            threshold={null}
            units=""
          />
        </ReadingSection>
        <ReadingSection
          aria-label="Native inputs and dialogs"
          data-components={[
            'TextArea',
            'Select',
            'Checkbox',
            'Disclosure',
            'DialogFrame',
            'SectionHeader',
            'ActionDialog',
            'DetailTabs',
            'FilePicker',
            'Progress',
            'Tabs',
            'ReadingContents',
          ].join(' ')}
        >
          <SectionHeader
            title="Editing and recovery"
            level={2}
            actions={recipeControls('heading')}
          />
          <div className="form-stack">
            <label>
              Long explanation
              <TextArea value={value} onChange={(e) => setValue(e.target.value)} />
            </label>
            <label className="check">
              <Checkbox checked={checked} onChange={(e) => setChecked(e.target.checked)} />
              Independent choice
            </label>
            <label className="check">
              <Checkbox disabled />
              Unavailable choice
            </label>
            <label>
              Unavailable input
              <TextInput disabled value="Unavailable" />
            </label>
            <Field label="Unassigned quantity" value={null} unit="m" />
            <Field
              label="Explicit zero"
              value={0}
              unit="m"
              units={['m', 'cm']}
              provenance="Entered for this specimen"
            />
            <Field label="Saved quantity" value={0} unit="m" state="readonly" />
            <Field label="Compact input" value="" unit="m" compact />
            <FilePicker label="Example file" />
            <FilePicker label="Unavailable file choice" disabled />
          </div>
          <Disclosure>
            <summary>Additional explanation</summary>
            <p>All full text remains available.</p>
          </Disclosure>
          <Tabs label="Specimen views" items={items} value={tab} onChange={setTab} />
          <Tabs
            label="Specimen segmented views"
            variant="segmented"
            items={items}
            value={tab}
            onChange={setTab}
          />
          <DetailTabs
            ports={<p>Explicit quantities</p>}
            source={<p>Source content</p>}
            assumptions={<p>Assumption content</p>}
          />
          <ReadingContents
            items={items.map((item) => ({ ...item, onSelect: () => setTab(item.id) }))}
          />
          <ActionDialog title="Recipe dialog" size="sm" label="Open recipe dialog">
            {recipeControls('dialog')}
            <p>Long text {'explanation '.repeat(30)}</p>
          </ActionDialog>
          <Button onClick={() => dialog.current?.showModal()}>Open native dialog</Button>
          <DialogFrame ref={dialog} aria-label="Native specimen dialog">
            <h2>Native specimen dialog</h2>
            <p>Full source content.</p>
            <Button onClick={() => dialog.current?.close()}>Close native specimen</Button>
          </DialogFrame>
          <Progress
            label="Loading evidence"
            message="Known content remains above; no count is inferred."
          />
          <Panel title="Unavailable record" tone="sunken">
            <p role="alert">This version could not be loaded. Try again.</p>
          </Panel>
          <DataTable
            label="Dense selected values"
            regionLabel="Dense values"
            dense
            selected={0}
            columns={[
              { key: 'name', label: 'Quantity' },
              { key: 'value', label: 'Value', numeric: true },
            ]}
            rows={[
              { name: 'Full scientific label '.repeat(8), value: 0 },
              { name: 'Missing value', value: null },
            ]}
          />
          <DataTable
            label="Empty values"
            regionLabel="Empty values"
            columns={[{ key: 'name', label: 'Quantity' }]}
            rows={[]}
          />
        </ReadingSection>
        <ReadingSection
          aria-label="Source and graph chrome"
          data-components="GraphCanvas ModelNode SourceSurface"
        >
          <SourceSurface display={bytes} codeRef={code}>
            <TextArea ref={code} aria-label="Specimen exact source" value={bytes} readOnly />
          </SourceSurface>
          <GraphCanvas
            projection={{ nodes: [], groups: [], invalid: [] }}
            selection={{ kind: 'none' }}
            onSelect={() => {}}
            trace={{ nodes: new Set(), links: new Set() }}
          />
          {(['incomplete', 'proposed', undefined] as const).map((status, index) => (
            <ModelNode
              key={index}
              name={'Component ' + index}
              definition="Explicit definition version"
              selected={index === 0}
              status={status}
              onSelect={() => {}}
              ports={[
                { name: 'x', dir: 'in', state: 'unassigned', onSelect: () => {} },
                { name: 'y', dir: 'out', state: 'output', onSelect: () => {} },
                { name: 'z', dir: 'in', state: 'connected', onSelect: () => {} },
                { name: 'q', dir: 'in', state: 'free', onSelect: () => {} },
              ]}
            />
          ))}
          <QuantitySlider
            label="Unassigned exploration"
            units="m"
            value={null}
            values={[]}
            onChange={() => {}}
          />
          <ResponseCurve
            label="Unavailable response"
            axis="Input"
            units="m"
            points={[]}
            selected={0}
          />
        </ReadingSection>
      </ReadingStack>
    </main>
  );
}
