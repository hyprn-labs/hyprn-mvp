---
name: scientific-engineering
description: Frame and assess engineering studies in HYPRN MVP, preserving the user's question while selecting methods, interpreting sources, designing checks and qualifying conclusions. Use for scientific authoring or review, not API mechanics or application development.
---

# Scientific and engineering judgment

Repository-owned scientific guidance. Its core workflow is integrated into the
application's [packaged playbook](../playbook.md), whose authoritative source is
[playbook.py](../../../application/src/hyprn_mvp_app/agent_tools/playbook.py).
Agents receive that guidance through `get_playbook`; this file adds the detailed
source-interpretation and comparison practices below. It is not automatically
installed as a separate client skill and grants no API or execution authority.
The owner-operated demonstration uses [its supported API path](../local-api-demo.md).
Keep the runtime guidance and this reference consistent; do not distribute another
editable copy in study folders.

Use this guidance to decide what a calculation can establish and to write a
study another engineer can inspect without the conversation. Apply the parts
relevant to the question; a small correction does not require a new study plan.

## Boundary with the application

| Application contracts own | Scientific judgment owns |
|---|---|
| Accepted value types, declared units and input provenance fields | Whether the units express the intended physical quantity and the cited source warrants the chosen value |
| Exact saved versions, retained runs and evidence references | Whether a reference supports, challenges or merely contextualizes a particular claim |
| Execution and criterion outcomes | Whether the equations, assumptions and criteria are appropriate to the engineering question |
| Permissions, revisions, receipts and execution containment | Which authorized calculation is informative, and how strongly its result supports a conclusion |

Read the current contract and capability information for API mechanics; do not
copy schemas, endpoint recipes or runtime limits here. Preserve the scientific
invariants in [AGENTS.md](../../../AGENTS.md) and use the meanings in
[CONTEXT.md](../../../CONTEXT.md). Guidance cannot replace enforcement or grant
execution access. Evaluate candidate model code only through the application's
supported restricted execution path.

## Preserve the question; explain the current approach

Keep the user's engineering question, requirements and requested deliverables
intact when a narrower calculation is possible. Put the current method and its
scope in the Modeling approach. A missing cost model does not turn a ticket-price
question into a fuel-expense question. Track which requested answers remain open.

Retain original wording when it is actually available. If only a summary survives,
label a reconstruction or restatement as such; do not invent a verbatim human
quotation or attribution. Do not silently drop ranges, alternatives, constraints
or secondary objectives when making the question easier to read.

Explain the reasoning connecting the question, selected methods and intended cases.
For each implemented method, link exact model versions and relevant elements;
several methods may share a model, and a method may use several models. Preserve
proposed or partial methods and their unresolved work. A link is not evidence that
the method is scientifically complete.
Make the method explanation specific enough to reconstruct its logic without reading
code. Purpose names the contribution to the study question; basis and reasoning
explain why these equations, sources and approximations are suitable; calculation
in plain words follows the actual input-to-output sequence and names the material
intermediate quantities. Check that it describes the linked implementation, including
its omissions. Avoid repeating the same broad description for unrelated components.
Let the reasoning determine useful case comparisons and groupings; do not force a
fuel-comparison template, a fixed set of outputs or universal case categories on
other studies.

State exclusions and unresolved validity conditions in limits. Keep assumptions
separate: an assumption is a condition being adopted, with its rationale and
support; a limit says what cannot be inferred. An open question identifies what
must be resolved next. Do not repeat the same caveat in each field.

Use ordinary engineering language in study prose. Leave optional text empty when
it adds nothing. Keep implementation labels, migration terminology, version hashes
and progress messages out of that prose; use record links for traceability.

## Match every citation to the assertion

Before saving a configuration, inspect each input's attached evidence against its
actual value, units, scenario and role. A source describing Mach 6 does not support
an authored Mach 8 scenario. Label that input as an explicit scenario choice and
cite the study requirement or case rationale that warrants exploring it; keep the
Mach 6 source only with the correlation or reference case it actually supports.
Apply the same check to criteria, assumptions, limits and answer statements.
Topical relevance is not support for a numerical assignment. After changing a value,
recheck its provenance statement and each citation; remove misplaced attachments
or replace them with evidence that supports the revised assertion. General context
belongs with the method or study statement it explains, not copied onto every input.
Do not hide a mismatch by rewriting a source note to agree with the calculation.

## Establish what the sources actually say

For each consequential equation, coefficient or interpretation, retain a source
and a locator precise enough to check it. Distinguish the printed statement from
your interpretation. Read surrounding definitions, tables and figure axes before
assigning units. Check dimensions and conventions, including normalization bases,
reference conditions and whether a plotted value is measured, computed or read off
a graph. More displayed digits do not create greater source precision.

When a source is inconsistent, keep its printed reading and your proposed reading
distinct. Explain the discrepancy and how it changes the calculation. If useful
and already authorized, compare plausible interpretations as explicitly labelled
sensitivity cases. Do not choose a reading merely because it fits a reference.
A close match can support investigating a hypothesis; it does not establish a
correction to the source. A user's approval to explore that hypothesis does not
resolve its scientific truth.

Use evidence relations deliberately: context explains a choice, support warrants a
claim within a stated scope, and contradictory evidence must remain visible. Do not
present a source citation as supporting an interpretation the source never states.

## Choose checks that could change the conclusion

Before extending a model, identify a small set of checks capable of exposing the
important mistakes: dimensions, conservation or balance, a limiting case, known
scaling, a reference calculation, or independent observations. Select checks for
the model's actual failure modes; do not require irrelevant tests for ceremony.

For a reference comparison, state the common inputs, output being compared,
reference precision and a physically justified tolerance before inspecting
agreement; do not choose the tolerance to fit the observed difference. Report
the discrepancy in physical units and, where meaningful, relative terms. Explain
material differences in equations, conditions or definitions before claiming the
comparison is like for like. Avoid tuning an assumption to match and then treating
that same match as independent validation.

Distinguish an implementation check from evidence that the model describes the
physical system adequately for the proposed use. Agreement with a second
implementation of the same equations is a consistency check. A published result
may itself be a model prediction. Neither, alone, demonstrates mission feasibility.

## Make comparisons and conclusions commensurate

Choose intended cases with a reason: a common reference for comparing alternatives,
a boundary important to the question, or a sensitivity capable of changing a
ranking. Distinguish a common-input comparison from a comparison of different
design assumptions. Use controlled sensitivity comparisons to isolate the effects
of changed inputs; otherwise say their contributions are unresolved. Do not
attribute all of the observed difference to the alternative being compared.

A candidate mass supplied from a figure is an input, not an optimum calculated by
the study. Use "optimum" only when the executed method actually solves a defined
optimization problem, with stated variables, objective, constraints and numerical
outcome; qualify local or global claims by the available evidence. A positive
balance in one flight segment is a necessary condition within that model, not a
complete aircraft or mission feasibility result.

Name cost outputs by their included terms and denominator. Record currency, price
year, unit basis, occupancy and relevant operating assumptions. Fuel expense per
occupied seat does not establish a ticket price. Missing capital, insurance,
operations or mission inputs remain unresolved; do not silently substitute zero
or invented values. Explain which missing terms prevent the requested estimate.

Record each case answer against the selected approach version and case. Identify
all configurations, runs and source versions that support it, explaining their
roles. Separate observations from interpretation and preserve missing or failed
results where they affect the answer. Never substitute a newer run silently.

Synthesize a study answer across explicitly selected case-answer versions. Address
every requested deliverable, including unanswered ones. For each claim, state
whether it is computed, sourced or judgment, and attach the qualification that
changes its interpretation. Save a new answer version when revising the conclusion;
ordinary evidence notes do not become answers because of their titles. Preserve distinctions among
execution, convergence, termination, feasibility, completeness, applicability and
criterion outcome. Report unresolved applicability as unresolved, even when a
criterion is met. Confidence is a reasoned judgment, not an unsupported probability.

## Continue useful work; escalate only the dependent decision

Reuse the user's established choices and authorization. Continue independent,
in-scope work when a scientific gap blocks only one deliverable. Ask for a missing
input or interpretation when it materially changes the answer and cannot be
resolved from available evidence or existing choices. Explain the consequence and
the specific decision needed; do not request approval again for the same choice.

Where a bounded conditional answer is defensible, give it and preserve the unmet
part of the original question. Where it is not, withhold that claim and say what
would resolve it. Do not label an incomplete study complete merely because the
application accepted every operation.

Before finishing, inspect the saved study through the public client: the question
still expresses the brief, the approach explains the method, source links support
their actual claims, limits state the missing coverage, and the conclusion answers
only what the retained evidence establishes. Correct authored content with new
versions where required; never rewrite the records used by historical runs.

Before publishing a revision, perform a focused coherence review of the affected
question, approach, cases, cited assumption notes, configurations and answers. Follow
the references as a reader would: compare consequential values, units, denominators,
constraints and claims about what is held constant with the selected input records.
A revised answer does not repair an older assumption note still cited by the current
approach. Update affected references and conclusions together using new versions;
retain an older record only when its historical or contrasting role is explicit.
Keep shared qualifications at their owner and repeat only the case-specific
consequence. Check that each qualification actually applies to its case. Review
claim strength and physical meaning, not merely matching words or API validity.

When changing this guidance, use the contrasting requests in
[behavioral scenarios](references/behavioral-scenarios.md). They test decisions,
not exact prose or headings.
