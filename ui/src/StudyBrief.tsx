import { EvidenceList, evidenceAccessLost } from './EvidenceView';
import { evidenceIds } from './referencedEvidence';
import { useCollectionRead } from './useCollectionRead';
import type { EvidenceRecord } from './api';
import { useEffect, useId, useRef, useState, type ReactNode } from 'react';
import type { HyprnMvpApi } from './api';
import {
  BriefController,
  newCriterion,
  useBriefController,
  type BriefForm,
  type CriterionForm,
} from './BriefController';
import type { StudyBriefContent1, StudyCriterion1 } from './contract';
import { criterionOperators } from './criterionLabels';
import {
  RecordDetails,
  RecordState,
  ActionDialog,
  ActionGroup,
  ReadingSection,
  ReadingStack,
  Assertion,
  AssertionList,
  Button,
  FormActions,
  DataTable,
  Panel,
  SectionHeader,
  Select,
  FormField,
  TextArea,
  TextInput,
  VersionSelect,
  formatNumber,
} from './design';
import { displayUnit } from './unitLabels';

const unit = (units: string) => (units ? displayUnit(units) : 'dimensionless');

function requirement(criterion: StudyCriterion1) {
  if (criterion.kind === 'objective')
    return criterion.direction === 'minimize' ? 'Minimize' : 'Maximize';
  return `${criterionOperators[criterion.operator]} ${formatNumber(criterion.threshold)}`;
}

function tolerance(criterion: StudyCriterion1) {
  if (criterion.kind === 'objective') return 'Not applicable';
  const parts = [];
  if (criterion.absolute_tolerance !== undefined)
    parts.push(`absolute ${formatNumber(criterion.absolute_tolerance)} ${unit(criterion.units)}`);
  if (criterion.relative_tolerance !== undefined)
    parts.push(`relative ${formatNumber(criterion.relative_tolerance)}`);
  return parts.length ? parts.join(' · ') : 'None';
}

/** One brief as it reads: question, scope, alternatives, criteria in priority order,
 * assumptions, limits and open questions. Empty optional lists are left out. */
function BriefReader({
  content,
  compact = false,
  api,
  studyId,
}: {
  api: HyprnMvpApi;
  studyId: string;
  content: StudyBriefContent1;
  compact?: boolean;
}) {
  const ids = evidenceIds(content);
  const collection = useCollectionRead<EvidenceRecord, string>({
    api,
    study: studyId,
    scope: JSON.stringify(ids),
    enabled: ids.length > 0 && !compact,
    load: async (_cursor, signal) => {
      const results = await Promise.allSettled(
        ids.map((id) => api.evidenceVersion(studyId, id, signal)),
      );
      const denied = results.find(
        (result) => result.status === 'rejected' && evidenceAccessLost(result.reason),
      );
      if (denied?.status === 'rejected') throw denied.reason;
      return {
        rows: results.flatMap((result) => (result.status === 'fulfilled' ? [result.value] : [])),
        next: null,
      };
    },
    identity: (record) => record.evidence_version_id,
  });
  const evidence = (links: StudyBriefContent1['assumptions'][number]['evidence_links']) =>
    links.length > 0 && collection.busy ? (
      <p role="status">Loading evidence…</p>
    ) : (
      <EvidenceList
        records={collection.rows}
        ids={links.map((link) => link.evidence_version_id)}
        links={links}
      />
    );
  if (compact)
    return (
      <ReadingStack>
        <ReadingSection aria-label="Study question">
          <h3>Study question</h3>
          <p className="context-copy">{content.question || 'No study question yet'}</p>
        </ReadingSection>
        <ActionGroup align="end">
          <ActionDialog
            purpose="reader"
            label="See details"
            title="Study brief details"
            width="workspace"
            size="sm"
          >
            <BriefReader api={api} studyId={studyId} content={content} />
          </ActionDialog>
        </ActionGroup>
      </ReadingStack>
    );
  return (
    <ReadingStack>
      <ReadingSection aria-label="Study question">
        <h3>Study question</h3>
        <p className="context-copy">{content.question || 'No study question yet'}</p>
        {content.original_question &&
          content.original_question.text.trim().replace(/\s+/g, ' ') !==
            content.question.trim().replace(/\s+/g, ' ') && (
            <p className="context-line">
              Original wording (supplied, unverified): {content.original_question.text}
            </p>
          )}
        {content.elaboration && (
          <p className="context-line">
            Elaboration (supplied, unverified): {content.elaboration.text}
          </p>
        )}
      </ReadingSection>
      {content.scope && (
        <ReadingSection aria-label="Scope">
          <h3>Scope</h3>
          <p className="context-copy">{content.scope}</p>
        </ReadingSection>
      )}
      <ReadingSection aria-label="Alternatives">
        <h3>Alternatives</h3>
        {content.alternatives.length ? (
          <ol className="hf-option-list">
            {content.alternatives.map((item) => (
              <li key={item.alternative_id}>
                <h4>{item.name}</h4>
                {item.description && <p>{item.description}</p>}
                {item.reason && <p className="context-line">Included because: {item.reason}</p>}
              </li>
            ))}
          </ol>
        ) : (
          <p>No alternatives recorded</p>
        )}
      </ReadingSection>
      <ReadingSection aria-label="Study criteria">
        <h3>Study criteria</h3>
        {content.criteria.length ? (
          <>
            <DataTable
              label="Study criteria in priority order"
              columns={[
                { key: 'priority', label: 'Priority', numeric: true },
                { key: 'name', label: 'Criterion' },
                { key: 'kind', label: 'Kind' },
                { key: 'requirement', label: 'Requirement' },
                { key: 'unit', label: 'Unit', unit: true },
                { key: 'tolerance', label: 'Tolerance' },
                ...(content.criteria.some((c) => c.evidence_links.length)
                  ? [{ key: 'evidence', label: 'Evidence' }]
                  : []),
              ]}
              rows={content.criteria.map((criterion, index) => ({
                priority: index + 1,
                name: criterion.name,
                kind: criterion.kind === 'constraint' ? 'Constraint' : 'Objective',
                requirement: requirement(criterion),
                unit: unit(criterion.units),
                tolerance: tolerance(criterion),
                evidence: evidence(criterion.evidence_links),
              }))}
            />
            {content.criteria.some((c) => c.kind === 'objective') && (
              <p className="context-line">
                Alternatives that meet every constraint are ranked by the objectives in this order;
                no weight or score is implied.
              </p>
            )}
          </>
        ) : (
          <p>No study criteria recorded</p>
        )}
      </ReadingSection>
      {(
        [
          [
            'Assumptions',
            content.assumptions.map(
              (a) => [a.assumption_id, a.statement, a.evidence_links] as const,
            ),
          ],
          [
            'Limits',
            content.limits.map((l) => [l.limit_id, l.statement, l.evidence_links] as const),
          ],
          [
            'Open questions',
            content.open_questions.map((q) => [q.question_id, q.text, []] as const),
          ],
        ] as const
      ).map(
        ([title, items]) =>
          items.length > 0 && (
            <ReadingSection key={title} aria-label={title}>
              <h3>{title}</h3>
              <AssertionList>
                {items.map(([id, statement, links]) => (
                  <Assertion key={id} statement={statement}>
                    {evidence([...links])}
                  </Assertion>
                ))}
              </AssertionList>
            </ReadingSection>
          ),
      )}
    </ReadingStack>
  );
}

function move<T>(list: T[], index: number, offset: number): T[] {
  const next = [...list],
    target = index + offset;
  if (target < 0 || target >= next.length) return next;
  [next[index], next[target]] = [next[target], next[index]];
  return next;
}

/** Order and removal controls of one list item, named after the item. */
function ItemControls({
  name,
  index,
  count,
  onMove,
  onRemove,
}: {
  name: string;
  index: number;
  count: number;
  onMove: (offset: number) => void;
  onRemove: () => void;
}) {
  return (
    <div className="section-actions">
      <Button
        size="sm"
        disabled={index === 0}
        aria-label={`Move ${name} up`}
        onClick={() => onMove(-1)}
      >
        Move up
      </Button>
      <Button
        size="sm"
        disabled={index === count - 1}
        aria-label={`Move ${name} down`}
        onClick={() => onMove(1)}
      >
        Move down
      </Button>
      <Button size="sm" aria-label={`Remove ${name}`} onClick={onRemove}>
        Remove
      </Button>
    </div>
  );
}

function CriterionFields({
  criterion,
  number,
  onChange,
}: {
  criterion: CriterionForm;
  number: number;
  onChange: (value: CriterionForm) => void;
}) {
  const set = (patch: Partial<CriterionForm>) => onChange({ ...criterion, ...patch });
  const label = `Criterion ${number}`;
  return (
    <>
      <label>
        {label} kind
        <Select
          aria-label={`${label} kind`}
          value={criterion.kind}
          onChange={(e) => set({ kind: e.target.value as CriterionForm['kind'] })}
        >
          <option value="constraint">Constraint (a threshold that must hold)</option>
          <option value="objective">Objective (a direction to prefer)</option>
        </Select>
      </label>
      <label>
        {label} name
        <TextInput
          value={criterion.name}
          maxLength={256}
          onChange={(e) => set({ name: e.target.value })}
        />
      </label>
      <label>
        {label} statement
        <TextArea
          aria-label={`${label} statement`}
          value={criterion.statement}
          maxLength={4096}
          onChange={(e) => set({ statement: e.target.value })}
        />
      </label>
      {criterion.kind === 'constraint' ? (
        <>
          <label>
            {label} comparison
            <Select
              aria-label={`${label} comparison`}

              value={criterion.operator}
              onChange={(e) => set({ operator: e.target.value as CriterionForm['operator'] })}
            >
              {Object.entries(criterionOperators).map(([value, text]) => (
                <option key={value} value={value}>
                  {text}
                </option>
              ))}
            </Select>
          </label>
          <label>
            {label} threshold
            <TextInput
              inputMode="decimal"
              value={criterion.threshold}
              placeholder="unassigned"
              maxLength={64}
              onChange={(e) => set({ threshold: e.target.value })}
            />
          </label>
        </>
      ) : (
        <label>
          {label} direction
          <Select
            aria-label={`${label} direction`}

            value={criterion.direction}
            onChange={(e) => set({ direction: e.target.value as CriterionForm['direction'] })}
          >
            <option value="minimize">Minimize</option>
            <option value="maximize">Maximize</option>
          </Select>
        </label>
      )}
      <label>
        {label} unit
        <TextInput
          value={criterion.units}
          placeholder="dimensionless"
          maxLength={64}
          onChange={(e) => set({ units: e.target.value })}
        />
      </label>
      {criterion.kind === 'constraint' && (
        <>
          <label>
            {label} absolute tolerance (optional)
            <TextInput
              inputMode="decimal"
              value={criterion.absolute_tolerance}
              placeholder="none"
              maxLength={64}
              onChange={(e) => set({ absolute_tolerance: e.target.value })}
            />
          </label>
          <label>
            {label} relative tolerance (optional)
            <TextInput
              inputMode="decimal"
              value={criterion.relative_tolerance}
              placeholder="none"
              maxLength={64}
              onChange={(e) => set({ relative_tolerance: e.target.value })}
            />
          </label>
        </>
      )}
    </>
  );
}

/** A list of statements (assumptions, limits or open questions) edited in order. */
function StatementList<T>({
  title,
  word,
  items,
  identity,
  read,
  write,
  create,
  onChange,
}: {
  title: string;
  word: string;
  items: T[];
  identity: (item: T) => string;
  read: (item: T) => string;
  write: (item: T, value: string) => T;
  create: () => T;
  onChange: (items: T[]) => void;
}) {
  return (
    <ReadingSection tone="sunken" aria-label={title}>
      <fieldset className="form-stack">
        <legend>{title}</legend>
        {items.map((item, index) => {
          const name = `${word} ${index + 1}`;
          return (
            <div key={identity(item)} className="form-stack">
              <label>
                {name}
                <TextArea
                  aria-label={name}
                  value={read(item)}
                  maxLength={4096}
                  onChange={(e) =>
                    onChange(items.map((x, i) => (i === index ? write(x, e.target.value) : x)))
                  }
                />
              </label>
              <ItemControls
                name={name}
                index={index}
                count={items.length}
                onMove={(offset) => onChange(move(items, index, offset))}
                onRemove={() => onChange(items.filter((_, i) => i !== index))}
              />
            </div>
          );
        })}
        <Button onClick={() => onChange([...items, create()])}>Add {word.toLowerCase()}</Button>
      </fieldset>
    </ReadingSection>
  );
}

function BriefEditor({ form, onChange }: { form: BriefForm; onChange: (form: BriefForm) => void }) {
  const set = (patch: Partial<BriefForm>) => onChange({ ...form, ...patch });
  return (
    <div className="form-stack">
      <ReadingSection tone="sunken" aria-label="Description">
        <FormField label="Study question">
          <TextArea
            aria-label="Study question"
            value={form.question}
            maxLength={4096}
            onChange={(e) => set({ question: e.target.value })}
          />
        </FormField>
        <FormField label="Scope" optional>
          <TextArea
            aria-label="Scope"
            value={form.scope}
            maxLength={4096}
            onChange={(e) => set({ scope: e.target.value })}
          />
        </FormField>
      </ReadingSection>
      <StatementList
        title="Assumptions"
        word="Assumption"
        items={form.assumptions}
        identity={(item) => item.assumption_id}
        read={(item) => item.statement}
        write={(item, statement) => ({ ...item, statement })}
        create={() => ({ assumption_id: crypto.randomUUID(), statement: '', evidence_links: [] })}
        onChange={(assumptions) => set({ assumptions })}
      />
      <StatementList
        title="Limits"
        word="Limit"
        items={form.limits}
        identity={(item) => item.limit_id}
        read={(item) => item.statement}
        write={(item, statement) => ({ ...item, statement })}
        create={() => ({ limit_id: crypto.randomUUID(), statement: '', evidence_links: [] })}
        onChange={(limits) => set({ limits })}
      />
      <fieldset className="form-stack">
        <legend>Alternatives</legend>
        {form.alternatives.map((item, index) => {
          const name = `Alternative ${index + 1}`;
          const change = (patch: Partial<typeof item>) =>
            set({
              alternatives: form.alternatives.map((x, i) => (i === index ? { ...x, ...patch } : x)),
            });
          return (
            <Panel
              key={item.alternative_id}
              tone="sunken"
              headingLevel={4}
              title={name}
              bodyClassName="form-stack"
              actions={
                <ItemControls
                  name={name}
                  index={index}
                  count={form.alternatives.length}
                  onMove={(offset) => set({ alternatives: move(form.alternatives, index, offset) })}
                  onRemove={() =>
                    set({ alternatives: form.alternatives.filter((_, i) => i !== index) })
                  }
                />
              }
            >
              <label>
                {name} name
                <TextInput
                  value={item.name}
                  maxLength={256}
                  onChange={(e) => change({ name: e.target.value })}
                />
              </label>
              <FormField label={`${name} description`} optional>
                <TextArea
                  aria-label={`${name} description`}
                  value={item.description}
                  maxLength={4096}
                  onChange={(e) => change({ description: e.target.value })}
                />
              </FormField>
              <FormField label={`${name} reason for inclusion`} optional>
                <TextInput
                  aria-label={`${name} reason for inclusion`}
                  value={item.reason}
                  maxLength={4096}
                  onChange={(e) => change({ reason: e.target.value })}
                />
              </FormField>
            </Panel>
          );
        })}
        <Button
          onClick={() =>
            set({
              alternatives: [
                ...form.alternatives,
                { alternative_id: crypto.randomUUID(), name: '', description: '', reason: '' },
              ],
            })
          }
        >
          Add alternative
        </Button>
      </fieldset>
      <fieldset className="form-stack">
        <legend>Study criteria, in priority order</legend>
        {form.criteria.map((criterion, index) => (
          <Panel
            key={criterion.criterion_id}
            tone="sunken"
            headingLevel={4}
            title={`Criterion ${index + 1}`}
            bodyClassName="form-stack"
            actions={
              <ItemControls
                name={`Criterion ${index + 1}`}
                index={index}
                count={form.criteria.length}
                onMove={(offset) => set({ criteria: move(form.criteria, index, offset) })}
                onRemove={() => set({ criteria: form.criteria.filter((_, i) => i !== index) })}
              />
            }
          >
            <CriterionFields
              criterion={criterion}
              number={index + 1}
              onChange={(value) =>
                set({ criteria: form.criteria.map((x, i) => (i === index ? value : x)) })
              }
            />
          </Panel>
        ))}
        <div className="section-actions">
          <Button onClick={() => set({ criteria: [...form.criteria, newCriterion('constraint')] })}>
            Add constraint
          </Button>
          <Button onClick={() => set({ criteria: [...form.criteria, newCriterion('objective')] })}>
            Add objective
          </Button>
        </div>
      </fieldset>
      <StatementList
        title="Open questions"
        word="Open question"
        items={form.open_questions}
        identity={(item) => item.question_id}
        read={(item) => item.text}
        write={(item, text) => ({ ...item, text })}
        create={() => ({ question_id: crypto.randomUUID(), text: '' })}
        onChange={(open_questions) => set({ open_questions })}
      />
    </div>
  );
}

/** The study brief on Overview: the latest saved version by default, the draft or any saved
 * version on request, and the draft editor. Saving a version freezes the saved draft. */
export function StudyBrief({
  api,
  studyId,
  controller,
}: {
  api: HyprnMvpApi;
  studyId: string;
  controller: BriefController;
}) {
  const state = useBriefController(controller);
  const [selected, setSelected] = useState<string | null>(null);
  const editButton = useRef<HTMLButtonElement>(null);
  const headingId = useId();
  // Leaving the editor (saved or cancelled) returns focus to the control that opened it.
  const editing = useRef(false);
  useEffect(() => {
    if (editing.current && !state.local) editButton.current?.focus();
    editing.current = !!state.local;
  }, [state.local]);
  useEffect(() => {
    const current = controller.getSnapshot();
    if (
      current.studyId !== studyId ||
      current.status === 'idle' ||
      (current.status === 'ready' && !current.local) ||
      (current.status === 'error' && !current.local)
    )
      void controller.open(studyId);
  }, [controller, studyId, api.actor]);
  if (
    state.studyId !== studyId ||
    state.status === 'idle' ||
    (state.status === 'loading' && !state.server)
  )
    return (
      <Panel className="overview-card" label="Study brief">
        <SectionHeader level={2} help="studyBrief" title="Study brief" />
        <p role="status">Loading study brief…</p>
      </Panel>
    );
  const { server, versions, local } = state;
  const working = state.status === 'working' || !!api.pending;
  const choice =
    selected ?? (server?.latest_version ? server.latest_version.brief_version_id : 'draft');
  const version = versions.find((v) => v.brief_version_id === choice);
  const shown: StudyBriefContent1 | null =
    choice === 'draft' ? (server?.draft?.content ?? null) : (version?.content ?? null);
  const draftSaved =
    !!server?.draft &&
    (!server.latest_version ||
      JSON.stringify(server.draft.content) !== JSON.stringify(server.latest_version.content));
  let body: ReactNode;
  if (local) {
    body = (
      <fieldset className="form-stack" disabled={working} aria-label="Edit study brief draft">
        <BriefEditor form={local} onChange={controller.edit} />
        <FormActions
          primary={
            <Button
              variant="primary"
              disabled={working || state.accessLost}
              onClick={() => void controller.save()}
            >
              Save draft
            </Button>
          }
        >
          <Button disabled={working} onClick={() => controller.discard()}>
            Cancel editing
          </Button>
        </FormActions>
      </fieldset>
    );
  } else if (!server) {
    body = null;
  } else if (shown) {
    body = <BriefReader api={api} studyId={studyId} content={shown} compact={choice !== 'draft'} />;
  } else {
    body = (
      <p>
        No study brief yet. Edit the brief to state the question, the alternatives and the criteria
        they are compared on.
      </p>
    );
  }
  const actions = !local && server && (
    <>
      <VersionSelect
        label="Study brief version"
        value={choice}
        draft
        versions={versions.map((v) => ({ id: v.brief_version_id, number: v.version_number }))}
        disabled={working}
        onChange={(value) => setSelected(value)}
      />
      <Button
        ref={editButton}
        disabled={working || state.accessLost}
        onClick={() => {
          setSelected('draft');
          controller.beginEdit();
        }}
      >
        {version
          ? JSON.stringify(server.draft?.content) === JSON.stringify(version.content)
            ? 'Create new version'
            : 'Continue draft'
          : 'Edit brief'}
      </Button>
      {choice === 'draft' && (
        <Button
          variant="primary"
          disabled={working || !draftSaved}
          onClick={() =>
            void controller.saveVersion().then((ok) => {
              if (ok) setSelected(null);
            })
          }
        >
          Save brief version
        </Button>
      )}
    </>
  );
  return (
    <Panel className="overview-card" label="Study brief">
      <SectionHeader
        level={2}
        id={headingId}
        help="studyBrief"
        title="Study brief"
        actions={actions}
      />
      {server && !local && (version || server.draft) && (
        <RecordDetails
          kind="Study brief"
          metadata={<RecordState state={version ? 'saved' : 'draft'} />}
        >
          <dl className="hf-record-details">
            <dt>Record ID</dt>
            <dd>{version?.brief_version_id ?? server.draft?.revision}</dd>
          </dl>
        </RecordDetails>
      )}
      {body}
      {state.status === 'working' && <p role="status">Saving study brief…</p>}
      {state.error && (
        <div role="alert">
          <p>{state.error}</p>
          {state.diagnostics.length > 0 && (
            <ul className="hf-prose-list">
              {state.diagnostics.map((d, i) => (
                <li key={i}>{d.message}</li>
              ))}
            </ul>
          )}
          {state.status === 'stale' && (
            <Button onClick={() => void controller.loadLatest()}>Load latest draft</Button>
          )}
          {state.status === 'uncertain' && (
            <Button onClick={() => void controller.checkCommand()}>
              Check the original command
            </Button>
          )}
          {state.status === 'error' && !local && !state.accessLost && (
            <Button onClick={() => void controller.open(studyId)}>Retry study brief</Button>
          )}
        </div>
      )}
    </Panel>
  );
}
