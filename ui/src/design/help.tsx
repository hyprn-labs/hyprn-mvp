import { useEffect, useRef, useState } from 'react';
import { Button, Panel } from './components';
import { ContentColumn, PageHeader } from './pageHeader';

type TopicId = 'start' | 'brief' | 'model' | 'experiments' | 'explore' | 'evidence' | 'assistant';
type GuideCard = { title: string; text: string; steps?: string[] };
type GuideTopic = {
  id: TopicId;
  label: string;
  title: string;
  summary: string;
  cards: GuideCard[];
  remember: string;
};

// Product guidance only. No study data, example results or execution states are inferred here.
const topics: GuideTopic[] = [
  {
    id: 'start',
    label: 'Start here',
    title: 'From a question to a supported answer',
    summary:
      'HYPRN connects the decision you need to make with the model, inputs and evidence behind it. Start with the question; the graphs are a way to inspect the answer, not a substitute for it.',
    cards: [
      {
        title: 'Overview',
        text: 'Frame the study in its brief. Read the recommendation, compare alternatives and explore how selected inputs affect the outcomes.',
      },
      {
        title: 'Models',
        text: 'Inspect or edit the component graph, quantity definitions, connections and Python source. Explain what the model represents and where it applies.',
      },
      {
        title: 'Experiments',
        text: 'Choose a saved model version, then prepare analyses, inspect configurations and follow their runs. These are three views of related numerical work.',
      },
    ],
    remember:
      'A successful execution is a calculation. An engineering answer also needs criteria, evidence and a judgment about the model’s limits.',
  },
  {
    id: 'brief',
    label: 'Study brief',
    title: 'Make the decision explicit',
    summary:
      'A useful brief says what you are comparing, what counts as acceptable and what the study can reasonably establish. Edit the brief from Overview.',
    cards: [
      {
        title: 'Question and alternatives',
        text: 'State the decision in one clear question. Name the alternatives you want compared; a single alternative can ask whether a proposal is acceptable.',
      },
      {
        title: 'Criteria',
        text: 'A constraint sets an acceptable bound. An objective states what to minimise or maximise. Give each criterion its units; an analysis links it to the model output that measures it.',
      },
      {
        title: 'Scope and unanswered questions',
        text: 'Describe what is included, record global assumptions and limits, and leave unresolved questions visible. A missing input or unsupported claim should remain explicit.',
      },
      {
        title: 'Save a stable basis',
        text: 'Work in a draft, then save a version. An answer refers to the particular brief version it addresses. Revising the brief does not rewrite earlier answers.',
      },
    ],
    remember:
      '“Meets the threshold” and “suitable for the intended use” are different conclusions. The brief gives the context needed to judge both.',
  },
  {
    id: 'model',
    label: 'Models and quantities',
    title: 'Keep the computation inspectable',
    summary:
      'A model joins Python components through named input and output quantities. Its graph shows the computation; its explanation makes the scientific choices reviewable.',
    cards: [
      {
        title: 'Components and connections',
        text: 'A component performs a transformation. A connection carries one component’s output into another component’s input. Inspect the graph and component details to follow that chain.',
      },
      {
        title: 'Independent inputs',
        text: 'Inputs without an upstream connection need explicit values in a configuration. A quantity definition supplies its name, meaning and units; it does not supply a physical value.',
      },
      {
        title: 'Explain the model',
        text: 'Use the model and component editors to record the calculation logic, evidence, assumptions and limits. Inspect the Python alongside the explanation when reviewing how an output is obtained.',
      },
      {
        title: 'Drafts and versions',
        text: 'Edit a draft. Saved model versions are read-only, and configurations refer to one particular version. Use Create new version when the computation changes; old runs continue to describe what they actually used.',
      },
    ],
    remember:
      'Changing a label, a connection or source code does not update old calculations. Check the selected model version before preparing new work.',
  },
  {
    id: 'experiments',
    label: 'Analyses and sampling',
    title: 'One investigation, many explicit inputs',
    summary:
      'An analysis groups the numerical work needed to answer a particular question about one model version. Select existing configurations or generate combinations by sampling.',
    cards: [
      {
        title: 'Configuration → run → analysis',
        text: 'A configuration is a saved set of inputs. A run executes it and records outputs and execution status. An analysis brings configurations and their runs together for comparison or surrogate validation. They can also be reused in another analysis.',
      },
      {
        title: 'Define the input space',
        text: 'For sampling, choose a fixed value or a range for each independent input. Each generated point is a complete combination across the inputs, not a separate calculation for only one slider.',
        steps: [
          'Choose ranges supported by the brief, evidence or an explicit assumption.',
          'Set the sampling method, training size, validation size and seed.',
          'Review the settings before saving and launching the analysis.',
        ],
      },
      {
        title: 'Fit, select, validate',
        text: 'Training points fit the surrogate. If method selection is used, separate points help choose between candidate methods. Independent validation points are held out from fitting and method selection to test the chosen surrogate against declared error limits.',
      },
      {
        title: 'Read the result correctly',
        text: 'Training and validation describe a point’s purpose. Both can have calculated outputs from actual runs. Estimated values come from the surrogate. A failed validation needs a revised analysis or model; it is not permission to hide the error.',
      },
    ],
    remember:
      'Saved analysis settings are read-only. A changed range, sampling plan or accuracy requirement belongs in a new version; a different investigation deserves a separate analysis.',
  },
  {
    id: 'explore',
    label: 'Answers and graphs',
    title: 'Explore without changing the evidence',
    summary:
      'The answer combines a recommendation with its supporting comparison, interpretation, uncertainties and next analysis. The interactive figure inspects prepared numerical behavior; it does not rewrite the saved conclusion.',
    cards: [
      {
        title: 'Calculated or estimated?',
        text: 'Calculated values come from model runs and use filled neutral marks. Estimated values come from a validated surrogate and use orange outlined marks or dashed curves. The legend and Why action explain the basis. Neither label means physically verified.',
      },
      {
        title: 'Move several inputs',
        text: 'Sliders select combinations inside the prepared domain. The saved surrogate supplies estimates without rerunning the engineering model. Fixed inputs remain visible as values; they need a sampled range before they can become sliders.',
      },
      {
        title: 'Read a response curve',
        text: 'Plot against chooses the horizontal axis independently of the selected input values. The curve holds other selected inputs fixed, except for declared linked inputs. Select outcomes changes which outputs you inspect; Expand model reveals intermediate quantities.',
      },
      {
        title: 'Understand the boundary',
        text: 'Interactive publication requires the displayed outputs to pass the required coverage and accuracy checks. Updating is a pending read, not a result. If a value is unavailable, read its reason; zero must never stand in for a missing output.',
      },
    ],
    remember:
      'Surrogate validation measures agreement with the computational model. Physical validity still depends on the model’s evidence, assumptions and intended use.',
  },
  {
    id: 'evidence',
    label: 'Evidence and limits',
    title: 'Know what supports each claim',
    summary:
      'Evidence belongs beside the statement or input it supports. A source may support a claim, challenge it or provide context; those relationships are not interchangeable.',
    cards: [
      {
        title: 'Evidence',
        text: 'Open View evidence to inspect the cited source and location. A document title alone does not establish a number: check the passage, units, conditions and interpretation that support the value.',
      },
      {
        title: 'Assumptions',
        text: 'An assumption is a condition or approximation the work relies on. Record it at the relevant study, model, component or configuration level. Writing it down does not establish that it is true.',
      },
      {
        title: 'Limits',
        text: 'A limit states what the result cannot establish: an excluded effect, an unsupported regime or a missing part of the system. Keep these separate from conditions the model assumes.',
      },
      {
        title: 'Trace a result',
        text: 'Follow Why and the related model, configuration or run to inspect the numerical basis. Record details provides exact identities when you need to audit or distinguish saved versions.',
      },
    ],
    remember:
      'An estimate, an engineering interpretation and a quoted source are different kinds of support. Preserve those distinctions when deciding what a result is worth.',
  },
  {
    id: 'assistant',
    label: 'Assistant and recovery',
    title: 'Work with the Assistant, keep the study in view',
    summary:
      'The Assistant is attached to the study named in its header. It uses the platform’s authoring and execution tools, so you can inspect its models, analyses and answer in the same workspace.',
    cards: [
      {
        title: 'Start or continue',
        text: 'From Home, start a study with its name and question, switch studies, or continue the current conversation. Opening another study switches its conversation too. Starting or switching shows the selection form before returning to the conversation.',
      },
      {
        title: 'Autonomous work',
        text: 'Enable Autonomous agent when creating a study to ask the Assistant to complete the brief and carry the work through models, calculations and a supported answer. Review the scope and assumptions it records; autonomy does not remove accuracy checks.',
      },
      {
        title: 'Waiting is not always stuck',
        text: 'The Assistant can wait while HYPRN calculates or validates, without generating text continuously. Read the current stage and any available completed-point count. A provider session may look idle during this wait; unchanged progress alone does not prove a failed calculation.',
      },
      {
        title: 'When attention is needed',
        text: 'Read the stated reason and the recovery action offered by the app. Resume continues an eligible interrupted analysis using its saved work. Uncertain execution must be reconciled before another launch; do not create a duplicate analysis just to clear a status.',
        steps: [
          'For missing inputs or evidence, supply the information in the current study.',
          'For validation failure, review the error and revise the model or sampling plan without weakening the required accuracy.',
          'For access, budget or service problems, follow the displayed next step; repeated messages cannot remove the restriction.',
        ],
      },
    ],
    remember:
      'If you stop the Assistant, already-submitted calculations may continue. Inspect their state before asking it to resume, and keep the conversation tied to the study in its header.',
  },
];

const journey: Array<{ topic: TopicId; label: string; detail: string }> = [
  { topic: 'brief', label: 'Frame', detail: 'Question & criteria' },
  { topic: 'model', label: 'Model', detail: 'Logic & quantities' },
  { topic: 'experiments', label: 'Calculate', detail: 'Inputs & runs' },
  { topic: 'explore', label: 'Judge', detail: 'Answer & exploration' },
];

/** A single, read-only help surface shared by Home and study routes. */
export function HelpCenter() {
  const [selected, setSelected] = useState<TopicId>('start');
  const heading = useRef<HTMLHeadingElement>(null);
  const moved = useRef(false);
  const topic = topics.find((item) => item.id === selected)!;
  useEffect(() => {
    if (moved.current) heading.current?.focus({ preventScroll: true });
  }, [selected]);
  const choose = (id: TopicId) => {
    moved.current = true;
    if (id === selected) heading.current?.focus({ preventScroll: true });
    setSelected(id);
  };
  return (
    <ContentColumn width="reading">
      <section className="hf-help-center" aria-label="Help center">
        <PageHeader level={1} title="Help center" />
        <div className="hf-help-center__layout">
          <nav className="hf-help-center__topics" aria-label="Help topics">
            {topics.map((item) => (
              <Button
                key={item.id}
                aria-current={item.id === selected ? 'page' : undefined}
                onClick={() => choose(item.id)}
              >
                {item.label}
              </Button>
            ))}
          </nav>
          <Panel className="hf-help-center__article">
            <article aria-labelledby="help-topic-title">
              <header className="hf-help-center__intro">
                <h2 id="help-topic-title" ref={heading} tabIndex={-1}>
                  {topic.title}
                </h2>
                <p>{topic.summary}</p>
              </header>
              {selected === 'start' && (
                <ol className="hf-help-center__journey" aria-label="Study workflow">
                  {journey.map((step, index) => (
                    <li key={step.topic}>
                      <span className="hf-help-center__step" aria-hidden="true">
                        {index + 1}
                      </span>
                      <Button onClick={() => choose(step.topic)}>{step.label}</Button>
                      <span>{step.detail}</span>
                    </li>
                  ))}
                </ol>
              )}
              <div className="hf-help-center__cards">
                {topic.cards.map((card) => (
                  <section className="hf-help-center__card" key={card.title}>
                    <h3>{card.title}</h3>
                    <p>{card.text}</p>
                    {card.steps && (
                      <ol>
                        {card.steps.map((step) => (
                          <li key={step}>{step}</li>
                        ))}
                      </ol>
                    )}
                  </section>
                ))}
              </div>
              <aside className="hf-help-center__takeaway" aria-label="Key distinction">
                <h3>Keep in mind</h3>
                <p>{topic.remember}</p>
              </aside>
            </article>
          </Panel>
        </div>
      </section>
    </ContentColumn>
  );
}
