import { criterionStatus, evaluationReasons } from './design';
import { OpenLink } from './design';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { message, type HyprnMvpApi } from './api';
import type {
  CalculationRun1,
  CriterionEvaluation1,
  StudyAnswerCell2,
  StudyAnswerContent3,
  StudyAnswerJustification1,
  StudyAnswerOutcome1,
} from './contract';
import { evidenceTitle, EvidenceList } from './EvidenceView';
import {
  StudyAnswerController,
  currentAnswer,
  useStudyAnswerController,
  type AnswerReferences,
} from './StudyAnswerController';
import {
  ActionGroup,
  RecordDetails,
  RecordState,
  RecordNavigation,
  SectionHelp,
  ReadingSection,
  ReadingStack,
  Button,
  FormActions,
  FormField,
  Checkbox,
  DataTable,
  Panel,
  SectionHeader,
  Select,
  StatusTag,
  TextArea,
  TextInput,
  VersionSelect,
  formatNumber,
} from './design';
import { requirement } from './AnalysisResults';
import { unitLabel } from './unitLabels';
import { CalculationExplorer } from './CalculationExplorer';
import { AnswerExplorationBasis } from './AnswerExplorationBasis';
import type { WorkspaceLink } from './workspaceModel';

const short = (id: string) => id.slice(0, 8);
const reviewLabels = {
  brief_fidelity: 'Fit to the question',
  source_basis: 'Source checks',
  physical_validity: 'Physical limits',
  sensitivity: 'Sensitivity',
} as const;

/** Names of the records an answer cites, from the references read with it. */
function names(refs: AnswerReferences, briefVersionId: string | null) {
  const brief = refs.briefVersions.find((v) => v.brief_version_id === briefVersionId) ?? null;
  const calculation = (id: string) => {
    const version = refs.calculationVersions.find((v) => v.calculation_version_id === id);
    return version ? `${version.content.name} · version ${version.version_number}` : 'Analysis';
  };
  return {
    brief,
    alternatives: brief?.content.alternatives ?? [],
    criteria: brief?.content.criteria ?? [],
    alternative: (id: string) =>
      brief?.content.alternatives.find((a) => a.alternative_id === id)?.name ?? 'Alternative',
    criterion: (id: string) =>
      brief?.content.criteria.find((c) => c.criterion_id === id)?.name ?? 'Criterion',
    calculation,
    evidence: (id: string) => {
      const record = refs.evidence.find((e) => e.evidence_version_id === id);
      return record ? evidenceTitle(record) : 'Evidence';
    },
  };
}

/** A cited run's criterion evaluation: shape, word and colour; the value with its units, or
 * "not computed". A cell saved but not yet evaluated says so. */
function Evaluation({
  evaluation,
  statusOnly = false,
}: {
  evaluation: CriterionEvaluation1 | null;
  statusOnly?: boolean;
}) {
  if (!evaluation) return <StatusTag tone="advisory">Evaluated when saved</StatusTag>;
  const value =
    evaluation.value === null
      ? 'not computed'
      : formatNumber(evaluation.value) + ' ' + unitLabel(evaluation.units);
  const [tone, word] = criterionStatus(evaluation.outcome);
  return (
    <span className="calculation-evaluation">
      <StatusTag tone={tone}>{word}</StatusTag>
      {!statusOnly && (
        <span>
          {evaluation.outcome === 'unresolved' ? evaluationReasons[evaluation.reason] : value}
        </span>
      )}
    </span>
  );
}

const relations = { supports: 'Supports', challenges: 'Challenges', context: 'Context' } as const;

function cited(item: StudyAnswerJustification1, n: ReturnType<typeof names>) {
  if (item.kind === 'evidence_version') return n.evidence(item.evidence_version_id);
  if (item.kind === 'run') return `Run from ${n.calculation(item.calculation_version_id)}`;
  return n.calculation(item.calculation_version_id);
}

/** One answer as it reads: outcome first, then the comparison and its justification. */
function AnswerReader({
  content,
  refs,
  figure,
  studyId,
  onOpen,
}: {
  content: StudyAnswerContent3;
  refs: AnswerReferences;
  figure: ReactNode;
  studyId: string;
  onOpen: (target: WorkspaceLink) => void;
}) {
  const n = names(refs, content.brief_version_id);
  const { interpretation } = content;
  // Mappings preserve relevant calculation sets; only cited output cells are comparisons.
  const supportingCalculations = [
    ...new Set(content.alternative_mappings.flatMap((m) => m.calculation_version_ids)),
  ].filter(
    (id) =>
      !content.comparison.some((c) => c.calculation_version_id === id) &&
      !content.justifications.some(
        (j) => j.kind === 'calculation_version' && j.calculation_version_id === id,
      ),
  );
  const basisGroups = [
    { id: 'calculations', title: 'Analyses and checks' },
    { id: 'exploration', title: 'Interactive estimates' },
    { id: 'evidence', title: 'Reference evidence' },
  ];
  const groupFor = (j: StudyAnswerJustification1) =>
    j.kind === 'evidence_version'
      ? 'evidence'
      : j.calculation_version_id === content.exploration_basis?.calculation_version_id
        ? 'exploration'
        : 'calculations';
  return (
    <ReadingStack>
      <StatusTag tone={content.completion.state === 'complete' ? 'ok' : 'advisory'}>
        {content.completion.state === 'complete' ? 'Requested work complete' : 'Interim answer'}
      </StatusTag>
      <Panel
        label="Conclusion"
        title="Conclusion"
        headingLevel={3}
        tone="sunken"
        bodyClassName="hf-flow"
      >
        {content.outcome ? (
          <>
            <div className="hf-decision-summary" aria-label="Recommendation">
              <span className="hf-decision-summary__label">Recommendation</span>
              <StatusTag
                tone={
                  content.outcome.kind === 'recommended'
                    ? 'ok'
                    : content.outcome.kind === 'no_go'
                      ? 'alarm'
                      : 'advisory'
                }
              >
                {content.outcome.kind === 'recommended'
                  ? 'Recommended'
                  : content.outcome.kind === 'no_go'
                    ? 'No-go'
                    : 'No recommendation'}
              </StatusTag>
              {content.outcome.kind !== 'no_recommendation' && (
                <span>{n.alternative(content.outcome.alternative_id)}</span>
              )}
            </div>
            <ReadingSection aria-label="Evidence and reasoning">
              <h4>Evidence and reasoning</h4>
              <p className="context-copy">
                {content.outcome.kind === 'no_recommendation' && (
                  <strong>
                    {content.outcome.basis === 'insufficient_evidence'
                      ? 'Insufficient evidence. '
                      : 'Contested evidence. '}
                  </strong>
                )}
                {content.outcome.reason}
              </p>
            </ReadingSection>
          </>
        ) : (
          <p>No outcome stated</p>
        )}
      </Panel>
      {figure}
      {Object.values(content.scientific_review).some((item) => item.explanation) && (
        <ReadingSection aria-label="Scientific review">
          <SectionHeader level={3} title="Scientific review" help="scientificReview" />
          <ReadingStack>
            {Object.entries(reviewLabels).map(([key, title]) => {
              const item = content.scientific_review[key as keyof typeof reviewLabels];
              return (
                item.explanation && (
                  <ReadingSection key={key} aria-label={title}>
                    <h4>{title}</h4>
                    <p className="context-copy">{item.explanation}</p>
                  </ReadingSection>
                )
              );
            })}
          </ReadingStack>
        </ReadingSection>
      )}
      <ReadingSection aria-label="Alternatives comparison">
        <SectionHeader level={3} title="Alternatives comparison" help="answerComparison" />
        <DataTable
          className="hf-table--comparison hf-table--grouped"
          label="Alternatives comparison"
        >
          <thead>
            <tr>
              <th className="hf-col--label">Alternative</th>
              <th className="hf-col--label">Output</th>
              <th className="hf-th--num">Value</th>
              <th>Requirement</th>
              <th className="hf-col--compact">Result</th>
              <th>Source</th>
            </tr>
          </thead>
          {content.alternative_mappings.map((mapping) => {
            const cells = content.comparison.filter(
              (c) => c.alternative_id === mapping.alternative_id,
            );
            const commonSource = cells.every(
              (c) => c.calculation_version_id === cells[0]?.calculation_version_id,
            );
            const source = (cell: StudyAnswerCell2) => (
              <RecordNavigation
                label={`Open analysis · ${n.calculation(cell.calculation_version_id)}`}
                onOpen={() =>
                  onOpen({
                    study: studyId,
                    view: 'calculations',
                    calculation_version: cell.calculation_version_id,
                  })
                }
              >
                {n.calculation(cell.calculation_version_id)}
              </RecordNavigation>
            );
            return (
              <tbody key={mapping.alternative_id}>
                {cells.length ? (
                  cells.map((cell, index) => {
                    const criterion = n.criteria.find((c) => c.criterion_id === cell.criterion_id);
                    return (
                      <tr key={index}>
                        {index === 0 && (
                          <th scope="rowgroup" rowSpan={cells.length}>
                            {n.alternative(mapping.alternative_id)}
                          </th>
                        )}
                        <th scope="row">{cell.output_name ?? 'Not identified'}</th>
                        <td className={cell.evaluation?.value == null ? 'missing' : 'num'}>
                          {cell.evaluation?.value == null
                            ? 'not computed'
                            : formatNumber(cell.evaluation.value) +
                              ' ' +
                              unitLabel(cell.evaluation.units)}
                          {cell.monetary_basis && (
                            <span
                              className="hf-field-hint"
                              title={cell.monetary_basis.economic_basis}
                            >
                              {' · '}
                              {cell.monetary_basis.price_year} prices
                            </span>
                          )}
                        </td>
                        <td>
                          {criterion ? (
                            <span className="hf-result-cell">
                              {criterion.name !== cell.output_name && <span>{criterion.name}</span>}
                              <span>{requirement(criterion)}</span>
                            </span>
                          ) : (
                            'Not assigned'
                          )}
                        </td>
                        <td className="hf-col--compact">
                          <Evaluation evaluation={cell.evaluation} statusOnly />
                        </td>
                        {(!commonSource || index === 0) && (
                          <td rowSpan={commonSource ? cells.length : undefined}>{source(cell)}</td>
                        )}
                      </tr>
                    );
                  })
                ) : (
                  <tr>
                    <th scope="row">{n.alternative(mapping.alternative_id)}</th>
                    <td colSpan={5}>No comparison recorded</td>
                  </tr>
                )}
              </tbody>
            );
          })}
        </DataTable>
        {content.alternative_mappings.map((mapping) => {
          const notes = [
            ...new Set(
              content.comparison
                .filter((c) => c.alternative_id === mapping.alternative_id)
                .map((c) => c.note)
                .filter(Boolean),
            ),
          ];
          return notes.length ? (
            <p className="context-line" key={mapping.alternative_id}>
              <strong>{n.alternative(mapping.alternative_id)}:</strong> {notes.join(' ')}
            </p>
          ) : null;
        })}
      </ReadingSection>
      {(content.justifications.length > 0 || supportingCalculations.length > 0) && (
        <ReadingSection aria-label="Answer basis">
          <SectionHeader level={3} title="Answer basis" help="answerBasis" />
          {basisGroups.map((group) => {
            const justifications = content.justifications.filter((j) => groupFor(j) === group.id);
            const calculations = supportingCalculations.filter(
              (id) =>
                (id === content.exploration_basis?.calculation_version_id
                  ? 'exploration'
                  : 'calculations') === group.id,
            );
            if (!justifications.length && !calculations.length) return null;
            return (
              <div className="hf-basis-group" key={group.id}>
                <h4>{group.title}</h4>
                <ul className="hf-option-list">
                  {justifications.map((j) => (
                    <li key={j.justification_id}>
                      <p>{j.reason}</p>
                      <ActionGroup>
                        {j.kind === 'evidence_version' ? (
                          <EvidenceList
                            records={refs.evidence}
                            ids={[j.evidence_version_id]}
                            links={[j]}
                          />
                        ) : (
                          <OpenLink
                            aria-label={`Open ${j.kind === 'run' ? 'run' : 'analysis'} · ${cited(j, n)}`}
                            onClick={() =>
                              onOpen({
                                study: studyId,
                                view: j.kind === 'run' ? 'runs' : 'calculations',
                                ...(j.kind === 'run'
                                  ? { run: j.run_id }
                                  : { calculation_version: j.calculation_version_id }),
                              })
                            }
                          >
                            {j.kind === 'run'
                              ? cited(j, n)
                              : n.calculation(j.calculation_version_id)}
                          </OpenLink>
                        )}
                        {j.relation !== 'supports' && (
                          <StatusTag tone="inert">{relations[j.relation]}</StatusTag>
                        )}
                      </ActionGroup>
                    </li>
                  ))}
                  {calculations.map((id) => (
                    <li key={id}>
                      <OpenLink
                        aria-label={`Open analysis · ${n.calculation(id)}`}
                        onClick={() =>
                          onOpen({
                            study: studyId,
                            view: 'calculations',
                            calculation_version: id,
                          })
                        }
                      >
                        {n.calculation(id)}
                      </OpenLink>
                      <p>
                        {content.alternative_mappings
                          .filter((m) => m.calculation_version_ids.includes(id))
                          .map((m) => n.alternative(m.alternative_id))
                          .join(' · ')}
                      </p>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </ReadingSection>
      )}
      {interpretation.interpretation && (
        <ReadingSection aria-label="Interpretation">
          <SectionHeader level={3} title="Interpretation" help="interpretation" />
          <p className="context-copy">{interpretation.interpretation}</p>
        </ReadingSection>
      )}
      {content.decisive_uncertainties.length > 0 && (
        <ReadingSection aria-label="Uncertainties">
          <SectionHeader level={3} title="Uncertainties" help="uncertainties" />
          <ul className="hf-prose-list">
            {content.decisive_uncertainties.map((u) => (
              <li key={u.uncertainty_id}>
                <strong>{u.statement}</strong>
                {u.stated_range && <p>{u.stated_range}</p>}
                {u.effect && <p>{u.effect}</p>}
              </li>
            ))}
          </ul>
        </ReadingSection>
      )}
      {content.next_analysis.statement && (
        <ReadingSection aria-label="Next analysis">
          <SectionHeader level={3} title="Next analysis" help="nextAnalysis" />
          <p className="context-copy">{content.next_analysis.statement}</p>
          {content.next_analysis.resolves && <p>{content.next_analysis.resolves}</p>}
        </ReadingSection>
      )}
    </ReadingStack>
  );
}

/** Removal control of one list item, named after the item. */
function Remove({ name, onRemove }: { name: string; onRemove: () => void }) {
  return (
    <Button size="sm" aria-label={`Remove ${name}`} onClick={onRemove}>
      Remove
    </Button>
  );
}

/** The form that adds one table cell: alternative, criterion, a calculation version mapped to
 * that alternative and one of its runs. The evaluation is read by the application on save. */
function CellAdder({
  api,
  studyId,
  form,
  refs,
  onAdd,
}: {
  api: HyprnMvpApi;
  studyId: string;
  form: StudyAnswerContent3;
  refs: AnswerReferences;
  onAdd: (cell: StudyAnswerCell2) => void;
}) {
  const n = names(refs, form.brief_version_id);
  const [alternative, setAlternative] = useState('');
  const [criterion, setCriterion] = useState('');
  const [calculation, setCalculation] = useState('');
  const [run, setRun] = useState('');
  const [runs, setRuns] = useState<CalculationRun1[]>([]);
  const [problem, setProblem] = useState('');
  const mapped =
    form.alternative_mappings.find((m) => m.alternative_id === alternative)
      ?.calculation_version_ids ?? [];
  useEffect(() => {
    setRun('');
    setRuns([]);
    if (!calculation) return;
    const abort = new AbortController();
    setProblem('');
    void (async () => {
      const items: CalculationRun1[] = [];
      let after: number | undefined;
      do {
        const page = await api.calculationRuns(studyId, calculation, after, abort.signal);
        if (abort.signal.aborted) return;
        items.push(...page.items);
        after = page.next_cursor ?? undefined;
      } while (after !== undefined);
      setRuns(items);
    })().catch((error) => {
      if (!abort.signal.aborted) setProblem(message(error));
    });
    return () => abort.abort();
  }, [api, studyId, calculation]);
  const evaluationWord = (r: CalculationRun1) => {
    const e = r.evaluations.find((x) => x.criterion_id === criterion);
    if (!e) return 'criterion not evaluated';
    return criterionStatus(e.outcome)[1].toLowerCase();
  };
  return (
    <fieldset className="form-stack">
      <legend>Add a table cell</legend>
      <label>
        Cell alternative
        <Select
          aria-label="Cell alternative"
          value={alternative}
          onChange={(e) => {
            setAlternative(e.target.value);
            setCalculation('');
          }}
        >
          <option value="">Choose an alternative</option>
          {n.alternatives.map((a) => (
            <option key={a.alternative_id} value={a.alternative_id}>
              {a.name}
            </option>
          ))}
        </Select>
      </label>
      <label>
        Cell criterion
        <Select
          aria-label="Cell criterion"
          value={criterion}
          onChange={(e) => setCriterion(e.target.value)}
        >
          <option value="">Choose a criterion</option>
          {n.criteria.map((c) => (
            <option key={c.criterion_id} value={c.criterion_id}>
              {c.name}
            </option>
          ))}
        </Select>
      </label>
      <label>
        Cell analysis version
        <Select
          aria-label="Cell analysis version"
          value={calculation}
          disabled={!mapped.length}
          onChange={(e) => setCalculation(e.target.value)}
        >
          <option value="">
            {mapped.length
              ? 'Choose a mapped analysis version'
              : 'Map an analysis version to this alternative first'}
          </option>
          {mapped.map((id) => (
            <option key={id} value={id}>
              {n.calculation(id)}
            </option>
          ))}
        </Select>
      </label>
      <label>
        Cell run
        <Select
          aria-label="Cell run"
          value={run}
          disabled={!runs.length}
          onChange={(e) => setRun(e.target.value)}
        >
          <option value="">{runs.length ? 'Choose a run' : 'No run listed'}</option>
          {runs.map((r) => (
            <option key={r.run_id} value={r.run_id}>
              Run {short(r.run_id)} · {criterion ? evaluationWord(r) : 'choose a criterion'}
            </option>
          ))}
        </Select>
      </label>
      {problem && <p role="alert">{problem}</p>}
      <Button
        disabled={!alternative || !criterion || !calculation || !run}
        onClick={() => {
          onAdd({
            alternative_id: alternative,
            criterion_id: criterion,
            calculation_version_id: calculation,
            run_id: run,
            note: '',
            evaluation: null,
            output_name: null,
          });
          setRun('');
        }}
      >
        Add table cell
      </Button>
    </fieldset>
  );
}

type JustificationKind = StudyAnswerJustification1['kind'];

function AnswerEditor({
  api,
  studyId,
  form,
  refs,
  onChange,
}: {
  api: HyprnMvpApi;
  studyId: string;
  form: StudyAnswerContent3;
  refs: AnswerReferences;
  onChange: (form: StudyAnswerContent3) => void;
}) {
  const set = (patch: Partial<StudyAnswerContent3>) => onChange({ ...form, ...patch });
  const n = names(refs, form.brief_version_id);
  const calculationVersions = refs.calculations.map((c) => c.latest_version.calculation_version_id);
  const [kind, setKind] = useState<JustificationKind>('calculation_version');
  const [target, setTarget] = useState('');
  const [runTarget, setRunTarget] = useState('');
  const outcome = form.outcome;
  const setOutcome = (value: StudyAnswerOutcome1 | null) => set({ outcome: value });
  const firstAlternative = n.alternatives[0]?.alternative_id ?? '';
  const citedVersions = new Set([
    ...form.alternative_mappings.flatMap((m) => m.calculation_version_ids),
    ...form.comparison.map((c) => c.calculation_version_id),
    ...form.justifications.flatMap((j) =>
      j.kind === 'evidence_version' ? [] : [j.calculation_version_id],
    ),
    ...(form.exploration_basis ? [form.exploration_basis.calculation_version_id] : []),
  ]);
  const analysisPins = new Map<string, string>();
  const modelPins = new Map<string, string>();
  const conflicts = new Set<string>();
  for (const version of refs.calculationVersions) {
    if (!citedVersions.has(version.calculation_version_id)) continue;
    const previous = analysisPins.get(version.calculation_id);
    if (previous && previous !== version.calculation_version_id)
      conflicts.add(
        'This answer uses multiple versions of one analysis. Select one version, or create a separate analysis for a complementary investigation.',
      );
    analysisPins.set(version.calculation_id, version.calculation_version_id);
    const model = modelPins.get(version.content.model_id);
    if (model && model !== version.content.model_revision_id)
      conflicts.add(
        'This answer uses multiple versions of one model. Select analyses that use the same model version.',
      );
    modelPins.set(version.content.model_id, version.content.model_revision_id);
  }

  return (
    <div className="form-stack">
      {[...conflicts].map((warning) => (
        <p role="alert" key={warning}>
          {warning}
        </p>
      ))}
      <label>
        Brief version answered
        <Select
          aria-label="Brief version answered"
          value={form.brief_version_id ?? ''}
          onChange={(e) => {
            const id = e.target.value || null;
            const brief = refs.briefVersions.find((v) => v.brief_version_id === id);
            // Every alternative of the chosen brief is listed, keeping existing mappings.
            const mappings = (brief?.content.alternatives ?? []).map(
              (a) =>
                form.alternative_mappings.find((m) => m.alternative_id === a.alternative_id) ?? {
                  alternative_id: a.alternative_id,
                  calculation_version_ids: [],
                },
            );
            set({ brief_version_id: id, alternative_mappings: mappings });
          }}
        >
          <option value="">No brief version chosen</option>
          {refs.briefVersions.map((v) => (
            <option key={v.brief_version_id} value={v.brief_version_id}>
              Study brief version {v.version_number}
            </option>
          ))}
        </Select>
      </label>
      <ReadingSection tone="sunken" aria-label="Completion">
        <FormField label="Answer status">
          <Select
            aria-label="Answer status"
            value={form.completion.state}
            onChange={(e) =>
              set({
                completion: {
                  ...form.completion,
                  state: e.target.value as 'interim' | 'complete',
                },
              })
            }
          >
            <option value="interim">Interim answer</option>
            <option value="complete">Requested work complete</option>
          </Select>
        </FormField>
        {(n.brief?.content.schema_version === '2' ? n.brief.content.deliverables : []).map(
          (item) => {
            const assessment = form.completion.deliverables.find(
              (value) => value.deliverable_id === item.deliverable_id,
            ) ?? {
              deliverable_id: item.deliverable_id,
              state: 'pending' as const,
              explanation: '',
            };
            const change = (patch: Partial<typeof assessment>) =>
              set({
                completion: {
                  ...form.completion,
                  deliverables: [
                    ...form.completion.deliverables.filter(
                      (value) => value.deliverable_id !== item.deliverable_id,
                    ),
                    { ...assessment, ...patch },
                  ],
                },
              });
            return (
              <ReadingSection key={item.deliverable_id} aria-label={item.statement}>
                <FormField label={item.statement}>
                  <Select
                    aria-label={item.statement}
                    value={assessment.state}
                    onChange={(e) => change({ state: e.target.value as typeof assessment.state })}
                  >
                    <option value="pending">Pending</option>
                    <option value="fulfilled">Fulfilled</option>
                    <option value="unavailable">Unavailable</option>
                  </Select>
                </FormField>
                <FormField label="Assessment">
                  <TextArea
                    aria-label={`Assessment: ${item.statement}`}
                    value={assessment.explanation}
                    maxLength={4096}
                    onChange={(e) => change({ explanation: e.target.value })}
                  />
                </FormField>
              </ReadingSection>
            );
          },
        )}
      </ReadingSection>
      <ReadingSection tone="sunken" aria-label="Scientific review">
        <SectionHeader level={3} title="Scientific review" help="scientificReview" />
        {Object.entries(reviewLabels).map(([key, title]) => {
          const aspect = key as keyof typeof reviewLabels;
          const item = form.scientific_review[aspect];
          const change = (patch: Partial<typeof item>) =>
            set({
              scientific_review: {
                ...form.scientific_review,
                [aspect]: { ...item, ...patch },
              },
            });
          return (
            <ReadingSection key={key} aria-label={title}>
              <FormField label={title}>
                <Select
                  aria-label={title}
                  value={item.state}
                  onChange={(e) => change({ state: e.target.value as typeof item.state })}
                >
                  <option value="unassessed">Not assessed</option>
                  <option value="checked">Checked</option>
                  <option value="limited">Limited</option>
                </Select>
              </FormField>
              <FormField label="Checks and remaining limits">
                <TextArea
                  aria-label={`Checks: ${title}`}
                  value={item.explanation}
                  maxLength={4096}
                  onChange={(e) => change({ explanation: e.target.value })}
                />
              </FormField>
            </ReadingSection>
          );
        })}
      </ReadingSection>
      <fieldset className="form-stack">
        <legend>Alternatives and their analyses</legend>
        {!form.alternative_mappings.length && (
          <p>Choose a brief version to list its alternatives.</p>
        )}
        {form.alternative_mappings.map((m, index) => {
          const name = n.alternative(m.alternative_id);
          const offered = [...new Set([...calculationVersions, ...m.calculation_version_ids])];
          return (
            <fieldset key={m.alternative_id} className="form-stack">
              <legend>{name}</legend>
              {!offered.length && <p>No analysis in this study yet.</p>}
              {offered.map((id) => (
                <label key={id}>
                  <Checkbox
                    checked={m.calculation_version_ids.includes(id)}
                    aria-label={`${name}: ${n.calculation(id)}`}
                    onChange={(e) =>
                      set({
                        alternative_mappings: form.alternative_mappings.map((x, i) =>
                          i !== index
                            ? x
                            : {
                                ...x,
                                calculation_version_ids: e.target.checked
                                  ? [...x.calculation_version_ids, id]
                                  : x.calculation_version_ids.filter((v) => v !== id),
                              },
                        ),
                      })
                    }
                  />
                  {n.calculation(id)}
                </label>
              ))}
            </fieldset>
          );
        })}
      </fieldset>
      <fieldset className="form-stack">
        <legend>Comparison</legend>
        {form.comparison.map((cell, index) => {
          const name = `Table cell ${index + 1}`;
          return (
            <div
              key={`${cell.alternative_id}:${cell.criterion_id}:${cell.run_id}`}
              className="form-stack"
            >
              <p>
                {name}: {n.alternative(cell.alternative_id)} · {n.criterion(cell.criterion_id)} ·
                <Evaluation evaluation={cell.evaluation} />
              </p>
              <label>
                {name} note
                <TextInput
                  value={cell.note}
                  maxLength={4096}
                  onChange={(e) =>
                    set({
                      comparison: form.comparison.map((x, i) =>
                        i === index ? { ...x, note: e.target.value } : x,
                      ),
                    })
                  }
                />
              </label>
              <Remove
                name={name}
                onRemove={() => set({ comparison: form.comparison.filter((_, i) => i !== index) })}
              />
            </div>
          );
        })}
        <CellAdder
          api={api}
          studyId={studyId}
          form={form}
          refs={refs}
          onAdd={(cell) => set({ comparison: [...form.comparison, cell] })}
        />
      </fieldset>
      <fieldset className="form-stack">
        <legend>Justifications</legend>
        {form.justifications.map((j, index) => {
          const name = `Justification ${index + 1}`;
          const change = (patch: Partial<StudyAnswerJustification1>) =>
            set({
              justifications: form.justifications.map((x, i) =>
                i === index ? ({ ...x, ...patch } as StudyAnswerJustification1) : x,
              ),
            });
          return (
            <div key={j.justification_id} className="form-stack">
              <p>
                {name}: {cited(j, n)}
              </p>
              <label>
                {name} relation
                <Select
                  aria-label={`${name} relation`}
                  value={j.relation}
                  onChange={(e) =>
                    change({ relation: e.target.value as StudyAnswerJustification1['relation'] })
                  }
                >
                  {Object.entries(relations).map(([value, text]) => (
                    <option key={value} value={value}>
                      {text}
                    </option>
                  ))}
                </Select>
              </label>
              <label>
                {name} reason
                <TextArea
                  aria-label={`${name} reason`}
                  value={j.reason}
                  maxLength={4096}
                  onChange={(e) => change({ reason: e.target.value })}
                />
              </label>
              <Remove
                name={name}
                onRemove={() =>
                  set({ justifications: form.justifications.filter((_, i) => i !== index) })
                }
              />
            </div>
          );
        })}
        <fieldset className="form-stack">
          <legend>Cite a record</legend>
          <label>
            Cited record kind
            <Select
              aria-label="Cited record kind"
              value={kind}
              onChange={(e) => {
                setKind(e.target.value as JustificationKind);
                setTarget('');
                setRunTarget('');
              }}
            >
              <option value="calculation_version">Analysis version</option>
              <option value="run">Run of an analysis version</option>
              <option value="evidence_version">Evidence version</option>
            </Select>
          </label>
          <label>
            Cited record
            <Select
              aria-label="Cited record"
              value={target}
              onChange={(e) => {
                setTarget(e.target.value);
                setRunTarget('');
              }}
            >
              <option value="">Choose a record</option>
              {kind === 'evidence_version'
                ? refs.evidence.map((e) => (
                    <option key={e.evidence_version_id} value={e.evidence_version_id}>
                      {evidenceTitle(e)}
                    </option>
                  ))
                : calculationVersions.map((id) => (
                    <option key={id} value={id}>
                      {n.calculation(id)}
                    </option>
                  ))}
            </Select>
          </label>
          {kind === 'run' && (
            <label>
              Cited run ID
              <TextInput
                value={runTarget}
                maxLength={36}
                placeholder="unassigned"
                onChange={(e) => setRunTarget(e.target.value.trim())}
              />
            </label>
          )}
          <Button
            disabled={!target || (kind === 'run' && !runTarget)}
            onClick={() => {
              const base = {
                justification_id: crypto.randomUUID(),
                relation: 'supports' as const,
                reason: '',
              };
              const item: StudyAnswerJustification1 =
                kind === 'evidence_version'
                  ? { ...base, kind, evidence_version_id: target }
                  : kind === 'run'
                    ? { ...base, kind, calculation_version_id: target, run_id: runTarget }
                    : { ...base, kind, calculation_version_id: target };
              set({ justifications: [...form.justifications, item] });
              setTarget('');
              setRunTarget('');
            }}
          >
            Add justification
          </Button>
        </fieldset>
      </fieldset>
      <fieldset className="form-stack">
        <legend>Interpretation</legend>
        <label>
          Interpretation
          <TextArea
            aria-label="Interpretation"
            value={form.interpretation.interpretation}
            maxLength={12292}
            onChange={(e) => set({ interpretation: { interpretation: e.target.value } })}
          />
        </label>
      </fieldset>
      <fieldset className="form-stack">
        <legend>Outcome</legend>
        <label>
          Outcome kind
          <Select
            aria-label="Outcome kind"
            value={outcome?.kind ?? ''}
            onChange={(e) => {
              const value = e.target.value;
              const reason = outcome?.reason ?? '';
              if (!value) setOutcome(null);
              else if (value === 'no_recommendation')
                setOutcome({ kind: value, basis: 'insufficient_evidence', reason });
              else
                setOutcome({
                  kind: value as 'recommended' | 'no_go',
                  alternative_id:
                    outcome && 'alternative_id' in outcome
                      ? outcome.alternative_id
                      : firstAlternative,
                  reason,
                });
            }}
          >
            <option value="">Not stated</option>
            <option value="recommended">
              {n.alternatives.length === 1 ? 'Go' : 'Recommend an alternative'}
            </option>
            {n.alternatives.length === 1 && <option value="no_go">No-go</option>}
            <option value="no_recommendation">No recommendation</option>
          </Select>
        </label>
        {outcome && outcome.kind !== 'no_recommendation' && (
          <label>
            Outcome alternative
            <Select
              aria-label="Outcome alternative"
              value={outcome.alternative_id}
              onChange={(e) => setOutcome({ ...outcome, alternative_id: e.target.value })}
            >
              {n.alternatives.map((a) => (
                <option key={a.alternative_id} value={a.alternative_id}>
                  {a.name}
                </option>
              ))}
            </Select>
          </label>
        )}
        {outcome?.kind === 'no_recommendation' && (
          <label>
            Why there is no recommendation
            <Select
              aria-label="Why there is no recommendation"
              value={outcome.basis}
              onChange={(e) =>
                setOutcome({
                  ...outcome,
                  basis: e.target.value as 'insufficient_evidence' | 'contested_evidence',
                })
              }
            >
              <option value="insufficient_evidence">The evidence is insufficient</option>
              <option value="contested_evidence">The evidence is contested</option>
            </Select>
          </label>
        )}
        {outcome && (
          <label>
            Outcome reason
            <TextArea
              aria-label="Outcome reason"
              value={outcome.reason}
              maxLength={4096}
              onChange={(e) => setOutcome({ ...outcome, reason: e.target.value })}
            />
          </label>
        )}
      </fieldset>
      <fieldset className="form-stack">
        <legend>Decisive uncertainties</legend>
        {form.decisive_uncertainties.map((u, index) => {
          const name = `Decisive uncertainty ${index + 1}`;
          const change = (patch: Partial<typeof u>) =>
            set({
              decisive_uncertainties: form.decisive_uncertainties.map((x, i) =>
                i === index ? { ...x, ...patch } : x,
              ),
            });
          return (
            <div key={u.uncertainty_id} className="form-stack">
              <label>
                {name}
                <TextInput
                  value={u.statement}
                  maxLength={4096}
                  onChange={(e) => change({ statement: e.target.value })}
                />
              </label>
              <label>
                {name} stated range
                <TextInput
                  value={u.stated_range}
                  maxLength={4096}
                  onChange={(e) => change({ stated_range: e.target.value })}
                />
              </label>
              <label>
                {name} effect on the recommendation
                <TextInput
                  value={u.effect}
                  maxLength={4096}
                  onChange={(e) => change({ effect: e.target.value })}
                />
              </label>
              <Remove
                name={name}
                onRemove={() =>
                  set({
                    decisive_uncertainties: form.decisive_uncertainties.filter(
                      (_, i) => i !== index,
                    ),
                  })
                }
              />
            </div>
          );
        })}
        <Button
          onClick={() =>
            set({
              decisive_uncertainties: [
                ...form.decisive_uncertainties,
                {
                  uncertainty_id: crypto.randomUUID(),
                  statement: '',
                  stated_range: '',
                  effect: '',
                },
              ],
            })
          }
        >
          Add decisive uncertainty
        </Button>
      </fieldset>
      <AnswerExplorationBasis
        api={api}
        studyId={studyId}
        value={form.exploration_basis}
        choices={calculationVersions.map((id) => ({ id, label: n.calculation(id) }))}
        onChange={(exploration_basis) => set({ exploration_basis })}
      />
      <fieldset className="form-stack">
        <legend>Next analysis</legend>
        <label>
          Next analysis
          <TextArea
            aria-label="Next analysis"
            value={form.next_analysis.statement}
            maxLength={4096}
            onChange={(e) =>
              set({ next_analysis: { ...form.next_analysis, statement: e.target.value } })
            }
          />
        </label>
        <label>
          What it would resolve
          <TextArea
            aria-label="What it would resolve"
            value={form.next_analysis.resolves}
            maxLength={4096}
            onChange={(e) =>
              set({ next_analysis: { ...form.next_analysis, resolves: e.target.value } })
            }
          />
        </label>
      </fieldset>
    </div>
  );
}

/** The study answer on Overview, its only home: the latest saved version by default, the draft
 * or any saved version on request, and the draft editor. Saving a version freezes the draft. */
export function StudyAnswer({
  api,
  studyId,
  controller,
  onOpen,
}: {
  api: HyprnMvpApi;
  studyId: string;
  controller: StudyAnswerController;
  onOpen: (target: WorkspaceLink) => void;
}) {
  const state = useStudyAnswerController(controller);
  const [selected, setSelected] = useState<string | null>(null);
  const editButton = useRef<HTMLButtonElement>(null);
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
      <Panel className="overview-card" label="Study answer">
        <SectionHeader level={2} help="studyAnswer" title="Study answer" />
        <p role="status">Loading study answer…</p>
      </Panel>
    );
  const { server, versions, local, references } = state;
  const working = controller.busy || !!api.pending;
  const choice =
    selected ?? (server?.latest_version ? server.latest_version.answer_version_id : 'draft');
  const version = versions.find((v) => v.answer_version_id === choice);
  const rawShown = choice === 'draft' ? server?.draft?.content : version?.content;
  const shown = rawShown ? currentAnswer(rawShown) : null;
  const draftSaved =
    !!server?.draft &&
    (!server.latest_version ||
      JSON.stringify(server.draft.content) !== JSON.stringify(server.latest_version.content));
  let body: ReactNode;
  if (local) {
    body = (
      <fieldset className="form-stack" disabled={working} aria-label="Edit study answer draft">
        <AnswerEditor
          api={api}
          studyId={studyId}
          form={local}
          refs={references}
          onChange={controller.edit}
        />
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
    body = (
      <AnswerReader
        content={shown}
        studyId={studyId}
        onOpen={onOpen}
        refs={references}
        figure={
          shown.exploration_basis && (
            <CalculationExplorer
              key={choice + JSON.stringify(shown.exploration_basis)}
              api={api}
              studyId={studyId}
              basis={shown.exploration_basis}
              requirements={
                references.calculationVersions
                  .find(
                    (v) =>
                      v.calculation_version_id ===
                        shown.exploration_basis?.calculation_version_id &&
                      v.content.brief_version_id === shown.brief_version_id,
                  )
                  ?.content.criterion_bindings.flatMap((binding) => {
                    const criterion = references.briefVersions
                      .find((v) => v.brief_version_id === shown.brief_version_id)
                      ?.content.criteria.find((c) => c.criterion_id === binding.criterion_id);
                    return criterion?.kind === 'constraint'
                      ? [{ target: binding.output, criterion }]
                      : [];
                  }) ?? []
              }
              onOpen={onOpen}
            />
          )
        }
      />
    );
  } else {
    body = (
      <p>
        No study answer yet. Edit the answer to map the alternatives to analyses, compare them on
        the criteria and state the outcome.
      </p>
    );
  }
  const actions = !local && server && (
    <>
      <VersionSelect
        label="Study answer version"
        value={choice}
        draft
        versions={versions.map((v) => ({ id: v.answer_version_id, number: v.version_number }))}
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
          : 'Edit answer'}
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
          Save answer version
        </Button>
      )}
    </>
  );
  return (
    <Panel className="overview-card" label="Study answer">
      <SectionHeader level={2} help="studyAnswer" title="Study answer" actions={actions} />
      {server && !local && (version || server.draft) && (
        <RecordDetails
          kind="Study answer"
          metadata={<RecordState state={version ? 'saved' : 'draft'} />}
        >
          <dl className="hf-record-details">
            <dt>Record ID</dt>
            <dd>{version?.answer_version_id ?? server.draft?.revision}</dd>
            <dt>Brief version ID</dt>
            <dd>{shown?.brief_version_id ?? 'Unassigned'}</dd>
          </dl>
        </RecordDetails>
      )}
      {body}
      {state.status === 'working' && <p role="status">Saving study answer…</p>}
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
            <Button onClick={() => void controller.open(studyId)}>Retry study answer</Button>
          )}
        </div>
      )}
    </Panel>
  );
}
