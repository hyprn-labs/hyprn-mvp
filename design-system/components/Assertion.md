# Assertions and attached evidence

Use `Assertion` for a scientific statement and its directly attached evidence,
inside `AssertionList`. An assumption and a limit keep their separate domain
meaning and headings; they share this presentation. Callers resolve exact sources
and own editing/versioning. These primitives do not fetch or interpret evidence.

- Statement: body typography, preserved line breaks, maximum 75ch.
- Statement to its evidence: 12px (`space-3`).
- Source to source: 8px (`space-2`), in `EvidenceStack`.
- Source title: body-strong; action row below, compact `sm` buttons. Titles may wrap
  to the full available width. No source is moved away from its assertion.
- Assertion to next assertion: 16px before and after a hairline. No bottom margin
  on the final assertion, whether evidence exists or not.
- No attachments: omit the collection, or let an empty EvidenceStack render hidden.
  Missing linked records are different: show the unavailable indication.
- Actions follow the evidence in ActionGroup. Editors reuse the same owner layout;
  form fields have their own field gaps, not extra paragraph margins.

`ReadingStack` and `ReadingSection` provide 24px section separator spacing and a
16px heading-to-content gap. Empty optional sections are omitted by the caller.
No descendant page selector may change these component interiors.

ClaimCard adds domain kind, explicit scope, limits and actual attribution over Assertion; it is not a persisted Claim entity. Its direct children keep zero outer margins so the shared 12px interval remains exact; source rows use 8px. ClaimButton counts distinct stable IDs within one explicit owner/version. Complete-empty, partial-empty and unknown sets are words, never a dead zero-count button. A one-item partial set says “1 loaded statement”. Answer-wide basis is uncounted prose with its own honest label. Direct View evidence stays direct; the context source reader preserves complete content, selected card, scroll and return focus.
