---
status: accepted
date: 2026-10-18
decision-makers: Owner
---

# ADR-0008: One study answer: conclusion and answer exploration, versioned together

## Context and Problem Statement

The delivered scientific answer has one head per approach version, so a new approach version shows no answer until one is saved again. The glossary does not name it; specifications call it a conclusion record, an assessment or a synthesis, and agents use an interim "Study conclusion" evidence note. No screen can write or revise it. Its exploration objects (designs, display settings, estimates) are keyed by answer version and rendered in two places. With the modeling approach retired (ADR-0007), the answer needs its own clear identity.

## Decision Drivers

- One interpretation record per study, with one home.
- Every number shown as part of the answer is traceable to exact versions.
- Interacting with the exploration figure must not create records.

## Considered Options

- **A:** one study answer family whose versions combine the conclusion and the exploration figure's basis.
- **B:** keep separate conclusion and exploration records with independent versions.
- **C:** keep one answer per brief version.

## Decision Outcome

Chosen option: **A**. A study has one answer family. Each saved answer version contains:

- the conclusion: observations, interpretation, qualifications and open deliverables;
- justifications: cited exact calculation versions, runs and evidence versions, each with its relation (supports, challenges or context) and reason;
- the answer exploration's basis: the calculation version and estimate it explores and the outcomes it shows.

Each answer version pins the exact study brief version it answers. Several calculations, across models, may justify one answer; the exploration figure shows exactly one calculation. Moving inputs on the figure is presentation and never creates a version; changing which calculation, estimate or outcomes the figure shows does. Overview is the answer's only home and offers its editor. The interim "Study conclusion" evidence note is retired. "Study answer" is the record; an assessment is the interpretation it contains.

### Consequences

- Good: one record answers the study, written and revised in the interface, the API and agent tools alike.
- Good: the figure and the conclusion can no longer drift apart silently.
- Bad: the answer contract, its storage key (study instead of approach version) and its agent tools change; attribution gains an answer record kind.

### Confirmation

- At most one answer head per study; saving creates an immutable version pinning one brief version.
- An answer cannot cite a calculation version, run or evidence version from another study.
- Moving exploration inputs issues no write; changing displayed outcomes and saving creates a new answer version.
- Agent-saved answer versions carry "{agent} for {user}" attribution.
