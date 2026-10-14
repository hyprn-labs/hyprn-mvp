# Continuous modeling approach — approved follow-up batch

Scope: the approved minimal reader journey and effective scientific authoring guidance.
This is a focused continuation under DELIVERY-PLAN.md, not phase completion.

## User outcome and acceptance

The local product presents the preserved engineering question, reasoning and methods,
cases with exact supporting configurations/runs, then a qualified answer where an
explicit authoritative assessment exists. Simple section jumps replace chapter tabs
and the method map. Proposed methods, missing results, failed runs, multiple runs,
historical versions, keyboard use and narrow layouts remain understandable.

The approved HTML mock is an external visual reference supplied by the user; its
illustrative prose and values are not study data. Leave live authoring records unchanged.

## Independent implementation ownership

1. UI executor: ApproachPanel.tsx, ApproachMethod.tsx, ApproachFindings.tsx, their scoped
   CSS and browser assertions, affected UI specifications/control map. Reuse the canonical
   model view and existing assumption-owner components. No API/schema, configuration
   components, generated contracts, runtime/build inputs or live-store edits.
2. Guidance executor: docs/agents/scientific-engineering/, authoritative runtime
   agent_tools/playbook.py, generated docs/agents/playbook.md, affected guidance tests
   and concise tooling documentation corrections. No API/schema/runtime execution
   changes or model authoring. Guidance must describe actually available capabilities.
3. Root: backend integration boundary, any explicitly needed answer persistence,
   integrated acceptance, native lane, live runtime refresh, project state and handover.

The result-format executor owns its existing backend/schema/API changes until merged.
UI and guidance may proceed independently in isolated worktrees. Root serializes heavy
browser/native checks and commits/checks the combined delivery tree before demo refresh.

## Required behavior

- Preserve question, constraints and deliverables; distinguish current approach from limits.
- Explain how methods and intended cases answer the question; link exact model versions
  and relevant elements. Many methods/models are allowed; linked does not mean complete.
- Expand compact case rows to show purpose, all associated configurations/runs, recorded
  outputs with units and missing-value reasons. No implicit latest-run selection or generic
  promotion of an arbitrary output. Criteria and execution are supporting facts, not answers.
- Scientific interpretations and final synthesis require an explicit persisted association
  to their basis. Never infer them from successful runs or evidence titles. Where no
  assessment exists, state that plainly. The answer-record capability is being scoped
  separately; preserve a clear integration seam without speculative API calls.
- Each assumption remains at its existing owner. Reference/open it, do not copy an editable
  list. Study limits stay in Study details; input provenance stays with inputs.
- Runtime guidance requires deliverable accounting, scientific reasoning, exact method/model
  links, purposeful comparisons, observations separate from interpretations, specified result
  bases and qualified synthesis. Use meaningful prose, not compulsory filler headings.

## Verification and delivery

Executors run focused checks through ./hyprn-mvp dev check and record exact commands,
counts, failures and cleanup in their own checkpoints. UI: combined-static, design checks
covered by the established groups, affected approach reader/method/findings browser groups.
Guidance: actual served/playbook surface checks and relevant agent-tool tests; independent
scenario responses on the existing scenarios, without a new evaluation framework.

Root reviews integrated changes, reruns the union of affected acceptance once, verifies
contracts/UI checker after any API change, and inspects the actual UI. No full phase gate,
human acceptance, portability or completed scientific assessment is implied by automated
checks. Preserve unrelated edits, all historical records and the running demo until its
replacement is verified. Each executor uses explicit-path commits and reports remaining gaps.
