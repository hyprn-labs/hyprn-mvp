---
name: scientific-engineering
description: Author and assess computational engineering studies in HYPRN (HYPRN MVP), from the engineering question through models, explicit cases, verification, uncertainty and versioned answers. Use for scientific modeling or review through the supported application client, not application development.
---

# Computational engineering in HYPRN

Produce an answer another engineer can challenge, reproduce and use within a
stated scope. A successful run is an observation; a scientifically acceptable
answer connects that observation to the question through justified physics,
checks, applicable evidence and explicit limitations. An unresolved or conditional
answer can be scientifically sound. It is not completion of an unmet objective.

This is the repository-owned skill for HYPRN MVP, called HYPRN by the user.
It grants no execution or write authority. The installed agent receives the essential
rules through `get_playbook`; its authoritative text is
[playbook.py](../../../application/src/hyprn_mvp_app/agent_tools/playbook.py), rendered
into [the playbook](../playbook.md). This skill adds detailed operating guidance.
Do not install it globally or copy editable instructions into a study unless asked.

## Start with the decision and available means

1. Read the existing study, its saved approach, relevant models, configurations,
   answers and outstanding objections. Read the session's capabilities and tool
   descriptions. Reuse records deliberately; neither a familiar name nor “latest”
   establishes their suitability for the question.
2. Preserve the user's alternatives, ranges, constraints, priorities and requested
   outputs. Keep the original question intact; put the tractable approximation in
   the current approach. Do not invent verbatim original wording from a summary.
3. State the intended use: explanation, screening, comparison, design sizing,
   optimization, or a consequential decision. Identify quantities of interest,
   evaluation conditions, acceptable error where known, and what could reverse the
   decision. Scale effort to those consequences and sensitivities, not model size.
4. Check the authorized execution surface. Delegated agents use only exposed tools.
   The separately authorized owner demo uses [the public API helper](../local-api-demo.md).
   A tool named in guidance is not necessarily implemented or enabled. Read the live
   schema for fields, units and numerical modes; never guess them from this skill.

Before authoring, read [Operating on HYPRN primitives](references/hyprn-primitives.md).
For a numerical conclusion, also read
[Scientific depth and stopping rules](references/scientific-acceptance.md).
For reference interpretation, validation or uncertainty, the
[primary-source basis](references/primary-sources.md) identifies the relevant guidance
and its limits. This skill adapts those practices; it does not certify compliance.

## Form a testable approach

For each requested deliverable, connect:

**question → observable output → physical argument → implemented method → informative
cases → checks and evidence → permissible conclusion.**

Keep this reasoning in the Modeling approach, using its existing prose and method
fields rather than inventing a new plan schema. Identify the system boundary,
operating envelope, material/geometry/environment conventions, governing balances,
constitutive or empirical relations, and material exclusions. Choose the simplest
model that can discriminate the decision; add fidelity when an omitted effect or
uncertainty could overturn it. If that cannot be bounded, state the gap rather than
assuming it is small. Avoid completing an elaborate implementation before testing
one useful baseline and its principal verification check.

For every method explain:

- **Purpose:** which part of the question it answers.
- **Basis and reasoning:** why the physical relations, source domain and simplifying
  assumptions are suitable, and what competing choice would matter.
- **Calculation in plain words:** the actual input-to-output sequence, important
  intermediate quantities, coupling and excluded effects.
- **Implementation and assurance:** relevant saved model/component versions; checks
  with expected behavior and tolerances justified before examining agreement.

A method can span models; a model can support several methods. Do not make the
approach a second executable graph. Keep proposed methods and their missing work
explicit. A source link or implementation link never establishes scientific adequacy.

## Author information where it belongs

Use the primitive map for field placement. In particular:

- A quantity definition explains physical meaning, direction, unit and conventions;
  a configuration supplies its value. Case-specific coefficients and uncertain
  properties are explicit inputs, not constants hidden in source.
- An assumption is an adopted condition, a rationale explains a choice, evidence
  supplies a source or observation, and a limit bounds inference. Store one
  authoritative assumption at its narrowest applicable owner and reference it.
- A case asks why a situation should be examined. A configuration says exactly what
  will be computed. A run records what happened. An answer interprets selected
  evidence; none substitutes for the others.
- Attach evidence to the assertion it actually warrants. A reference for an equation
  is not automatically evidence for every coefficient, boundary condition or chosen
  scenario. A cited Mach 6 example cannot justify an authored Mach 8 input.

Inspect a consequential source's definitions, equation, surrounding text, table
headers and axes. Record a precise locator, the printed value/unit, reference
conditions, uncertainty or extraction precision, and any interpretation. Distinguish
measurement, simulation, fitted correlation, approximate graph reading and author
judgment. A URL alone does not establish provenance. Never claim to have inspected
an inaccessible source; seek an accessible primary source or qualify the gap.

If units or conventions conflict, preserve the printed statement and proposed
interpretation separately. Test plausible readings as labelled cases when useful
and authorized. Agreement obtained by choosing a reading or tuning a coefficient
is not independent confirmation of that choice. User approval of a hypothesis
permits its exploration; it does not make the hypothesis true.

## Execute an adaptive scientific loop

Start with an informative baseline, then choose the next case from what remains
uncertain. Common-condition comparisons isolate an option's effects; separately
sized designs answer a different question. State which quantities are fixed,
changed, derived or constrained. Choose boundary cases, limiting cases, perturbations
and interactions that can reveal a failure or change a ranking. A few successful
points do not establish an entire continuous operating envelope.

Before submission, inspect the full model and all free inputs, units, provenance,
criteria, numerical settings and approach/case links. Read the preview's warnings;
API acceptance is structural checking, not physical verification. Save coherent
versions and retain their returned identities. Run candidate code only through the
supported restricted worker, including numerical verification models. Do not execute
it in the agent shell, import it for inspection, or bypass missing platform features
with a hidden solver, external service, randomness or private backend access.

For each completed run:

1. Read execution/termination information, declared outputs, units, missing-value
   reasons and criterion evaluations. Do not infer convergence or applicability from
   successful execution; do not turn failure or missing data into zero.
2. Check implementation and numerical behavior against the preselected tests. Check
   balances and physically meaningful intermediate outputs, not only the final
   number. A failed check blocks its dependent conclusion until explained or fixed.
3. Compare with applicable physical observations when a predictive claim needs them.
   Identify what was calibrated and what remains independent validation evidence.
4. Assess decision sensitivity to uncertain inputs, numerical error and model-form
   choices. Report unquantified contributors. An uncertainty interval is not a
   probability statement without a justified probabilistic interpretation.
5. Refine only the affected model, input, evidence or inference. Re-run when changed
   physics, source or inputs invalidate a result; do not re-run merely to improve prose.
   When a source changes, inspect downstream assignments and conclusions too.

Keep the next action explicit: correct an error, obtain evidence, evaluate a
specified case, improve fidelity, answer conditionally, or stop because the evidence
cannot support the requested claim. Continue independent useful work when only one
deliverable is blocked. Reuse authorization already given; ask only for missing
choices that materially affect the answer or newly required authority.

## Reach the right depth, then record an answer

Use the acceptance reference to select the depth required by the intended claim.
Do not call a candidate an optimum, a criterion a validity assessment, a component
balance full-system feasibility, or a partial expense a ticket/total cost. Optimization
requires an actually executed supported optimization method and evidence for its
stated claim; a sampled best case is only best among evaluated cases.

For each material conclusion, be able to answer:

| Question | Evidence needed before making the claim |
|---|---|
| What does this answer, under which conditions? | The preserved brief, selected case and explicit scope. |
| What produced the number? | Exact model, configuration, run/output and relevant source versions. |
| Were the equations implemented and solved adequately? | Applicable implementation and solution checks, discrepancies, tolerances and failures. |
| Why should this model represent this system here? | Physical argument, applicability domain and relevant validation evidence, or an explicit predictive gap. |
| Could plausible uncertainty or omitted physics change the conclusion? | Decision-relevant sensitivity/error analysis; unknown contributions remain visible. |
| What is still unanswered and what would resolve it? | Specific missing evidence/method/input and its consequence for the requested deliverable. |

Save a **case answer** for the selected approach version and case, using observations
for checked results, interpretation for their engineering meaning, qualifications
for conditions that change that meaning, and open deliverables for unresolved work.
Cite exact configurations, runs and evidence; explain conflicting runs and their
roles. Save the **study answer** against deliberately selected case-answer versions,
covering every requested deliverable. Use the actual answer operation; a titled
evidence note is not a persistent answer. If the client cannot save it, provide the
answer and report that persistence is unavailable; never claim a save occurred.

Before finishing, read back the saved records and inspect the public reader journey.
Follow the evidence links and check agreement of values, units, denominators,
scenario descriptions, controlled comparisons and claim strength. Revise stale
references and affected answers together. Keep old records identifiable rather than
silently replacing their basis. Use concise explanatory prose, appropriate precision,
and selected comparisons; link full result tables instead of copying every output.
A reviewer should understand the answer without the conversation or internal IDs.

Report the supported answer, its scope and uncertainty, the unresolved deliverables,
and what was actually saved/run. Stop when the evidence meets the stated use and
further work is unlikely to change the decision at the required resolution, or when
a named gap prevents a stronger answer. Do not invent a numerical confidence score.

When maintaining this skill, use the
[behavioral scenarios](references/behavioral-scenarios.md) to assess decisions,
including capability limits and adverse evidence. File validation and API tests do
not establish scientific judgment or human acceptance.
