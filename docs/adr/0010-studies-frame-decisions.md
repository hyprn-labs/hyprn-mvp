---
status: accepted
date: 2026-10-18
decision-makers: Owner
---

# ADR-0010: Studies frame engineering decisions

Extends [ADR-0007](0007-retire-modeling-approach-version-study-brief.md), [ADR-0008](0008-one-study-answer.md) and [ADR-0009](0009-calculations-and-reference-configurations.md); everything else in them stays in force.

## Context and Problem Statement

HYPRN MVP is meant to help engineers decide which design to pursue, why, with what confidence, and what to investigate before committing, not only to compute. A decision compares alternatives against objectives and constraints with evidence, and may honestly conclude that the evidence is not yet sufficient. The study brief, study answer and calculations defined by ADR-0007 to ADR-0009 are not yet built, so the decision structure can be part of them from the start instead of a later layer. Two gaps stand out. Alternatives exist only implicitly (in the fuel demonstration, as one qualitative input). Criteria are copied into every configuration and point at one model's outputs, so they cannot compare alternatives built from different models.

## Decision Drivers

- Derive the minimum decision structure from one real workflow (fuel selection) before generalising.
- Alternatives may be different models or the same model with different reference configurations.
- Criteria must compare alternatives across models.
- "Insufficient evidence" is a first-class outcome, not an absence.
- No fabricated precision: no default weights, scores or numeric confidence.

## Considered Options

- **A:** fold the decision structure into the study: alternatives and criteria in the brief, criterion bindings in calculations, the comparison and recommendation in the study answer.
- **B:** add a separate grouping record between calculations and the answer (a trade study or comparison) that maps alternatives to calculations.
- **C:** add a Decision record above studies, related many-to-many.

## Decision Outcome

Chosen option: **A**. One study frames one decision. A Decision record that draws on several studies is deferred; study answers keep stable versioned identities so a later Decision can cite them.

- **Alternatives.** The study brief lists the alternatives under consideration, each with a name, description and reason for inclusion. A study with one alternative is a go / no-go feasibility question. Changing the list is a change of framing and creates a new brief version when saved.
- **Study criteria.** The brief defines each criterion once, with units, as a constraint (a threshold that must hold) or an objective (a direction to minimise or maximise). Configurations no longer carry criteria.
- **Criterion bindings.** Each calculation version binds the brief's criteria to the outputs of its own model version that measure them. Runs in the calculation are evaluated against the brief's criteria through these bindings (met, not met or unresolved), so alternatives built from different models are compared on the same criteria.
- **Study answer.** The answer has a draft and immutable versions. It maps each alternative to the calculation versions that back it (several are allowed, possibly across models). It holds the alternatives × criteria table with cited calculations, runs and evidence, the interpretation, an outcome, the decisive uncertainties (assumptions or inputs that would change the preferred alternative) and the next most valuable analysis. The outcome is a recommended alternative (for one alternative: go or no-go), or no recommendation because evidence is insufficient or contested, with the reason. Calculations are mapped to alternatives only in the answer; there is no separate grouping record.
- **Answer exploration.** The figure explores one alternative's calculation at a time, or compares alternatives on a bound criterion output and shows where the preferred alternative changes across an input range the alternatives share.

### Consequences

- Good: the product's central record is a defensible recommendation, or an explicit statement that one cannot yet be made.
- Good: criteria are defined once and compare alternatives built from different models.
- Good: the answer draft is the working comparison, so nothing is pinned until a version is saved.
- Bad: criterion bindings add a step when a calculation is created for a model whose outputs differ from the criteria's wording.
- Bad: the brief, calculation and answer contracts carry more structure, and the agent workflow must frame alternatives and criteria before calculating.

### Confirmation

- A brief version lists alternatives and criteria; a saved configuration carries no criteria.
- A calculation version cannot be evaluated against a criterion it has not bound; an unbound criterion is unresolved, never met.
- Two calculations built from different models produce comparable cells for the same brief criterion.
- An answer version records either a recommended alternative or no recommendation with its reason; neither is inferred from execution or criteria alone.
- Moving exploration inputs or switching the compared alternative creates no record until the answer is saved.
