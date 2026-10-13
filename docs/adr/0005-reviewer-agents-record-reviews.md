---
status: accepted
date: 2026-10-13
decision-makers: Owner
---

# ADR-0005: An agent acting for a Reviewer may record scientific reviews

Extends [ADR-0003](0003-agent-write-rights-revised.md); everything else in ADR-0003 stays in force.

## Context and Problem Statement

ADR-0003 lets agents record scientific reviews, labelled as recorded by an assistant, but kept the role ceilings unchanged: an agent acting for a Reviewer had the `reader` ceiling and could only read and post progress notes and platform-issue reports. A Reviewer's work in HYPRN MVP is reviewing, so a read-only assistant cannot help with the one record a Reviewer creates.

## Decision Drivers

- A Reviewer's assistant should be able to help with the Reviewer's own task.
- A Reviewer must never gain the ability to change the work under review, directly or through an agent.
- Agent-recorded reviews stay distinguishable from reviews a person recorded.

## Considered Options

- **A:** keep the Reviewer's agent read-only.
- **B:** give the Reviewer's agent the effect "record a scientific review", and nothing else beyond the `reader` effects.

## Decision Outcome

Chosen option: **B**. An agent acting for a Reviewer may record scientific reviews of the work the Reviewer can see, within the Reviewer's own review eligibility, attributed "{agent} for {user}" and labelled as recorded by an assistant. It still cannot edit, version, configure, submit runs, create studies, or perform any human-only action (ADR-0003). The ceiling becomes `reader` plus the `review` effect; the authorization intersection (delegation, the Reviewer's current access, the ceiling) is rechecked on every call as before.

### Consequences

- Good: a Reviewer's assistant can draft and record the review the Reviewer is responsible for.
- Good: the Reviewer's write surface stays exactly one record type, so the work under review cannot be changed through the agent.
- Bad: more reviews may be agent-recorded; policies that require an independent human review rely on the agent-recorded label to tell them apart.

### Confirmation

- Registry tests: for a reader-ceiling delegation, `record_scientific_review` is listed (once the review record exists) and every other write tool is absent; write routes other than the review route refuse the delegation.
- Attribution tests: a review recorded by a Reviewer's agent shows "{agent} for {user}" and the agent-recorded label.
