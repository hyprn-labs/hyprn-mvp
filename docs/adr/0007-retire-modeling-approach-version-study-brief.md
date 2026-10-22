---
status: accepted
date: 2026-10-18
decision-makers: Owner
---

# ADR-0007: Retire the modeling approach; the study owns a versioned brief

## Context and Problem Statement

The modeling approach grew into a second home for almost everything a study says about itself: the question, scope, limits and open questions, approach-level assumptions, method steps that mostly describe one model, proposed model conditions and earlier work. The glossary placed the question on Study, while the records placed it in the approach version. The interface consequently rendered the study answer twice, offered three editors for the question, two editors for method prose, and a page whose removal would orphan most of this content. Each record type should have one owner and one home.

## Decision Drivers

- One concept, one owner, one home in the interface.
- A study answer must pin the exact question, scope and assumptions it answers.
- Claims and their evidence stay with the application; the modeling service remains private and replaceable.
- Keep the number of primitives small.

## Considered Options

- **A:** keep the approach as a study-level record and split its page between Overview and the Model page.
- **B:** retire the approach; distribute its content to Study, the model explanation, model assumptions and the study answer.
- **C:** make method steps model-owned inside the modeling service.

## Decision Outcome

Chosen option: **B**. The modeling approach leaves the domain, the public API and the interface.

- **Study brief.** A study owns a brief: the question (with original wording and elaboration), scope, global assumptions, limits and open questions. The brief has one draft and immutable saved versions, like a model. Study name and list description remain plain study metadata; `boundary` is removed.
- **Model explanation.** Each model version has an application-owned explanation record: what the model represents, its basis and reasoning, its calculation logic, and per-component explanations, with attached evidence. It is saved and frozen with the model version it explains. It is not stored in the modeling service.
- **Model assumptions.** Conditions proposed for a model are model or component assumptions in a proposed state, not separate approach items.
- **Earlier work** becomes justification in the study answer (ADR-0008), keeping the supports / challenges / context relation.
- Configurations no longer link an approach version and no longer copy study text into a frozen context. Reasoning that spans several models belongs to the study answer's justification.

The owner authorized discarding all development studies and records on 2026-10-18, so no stored approach, configuration or answer record is migrated and no reader for retired formats is kept. This is a reset of development data; studies remain archived and restored, never deleted, in the product.

### Consequences

- Good: Overview is the study's single home (brief, answer, exploration); models carry their own explanation; every object has one home.
- Good: answers pin an exact brief version instead of an approach version.
- Bad: a large staged change across the store, the public contract, agent tools, the study workflow skill and the browser suites; many approach tests are deleted rather than migrated.
- Bad: the fuel demonstration must be re-created on the new records after the development store is reset.

### Confirmation

- No public route, schema, UI view or agent tool names the modeling approach; the module-boundary and contract tests pass.
- Saving a study brief creates an immutable version; editing the draft never changes a saved version.
- A model version's explanation is read from the application store and is unchanged after the modeling service is restarted or replaced.
- CONTEXT.md lists Study brief and Model explanation, and lists Modeling approach only as retired.
