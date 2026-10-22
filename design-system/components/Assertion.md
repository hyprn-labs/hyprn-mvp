# Assertions and attached evidence

Use `Assertion` for a scientific statement and its directly attached evidence,
inside `AssertionList`. An assumption and a limit keep their separate domain
meaning and headings; they share this presentation. Callers resolve exact sources
and own editing/versioning. These primitives do not fetch or interpret evidence.

- Statement: body typography, preserved line breaks, maximum 75ch.
- Statement to its evidence: 12px (`space-3`).
- Source to source: 8px (`space-2`), in `EvidenceStack`.
- One bordered View evidence (n) button follows the statement on its own left-aligned action row. Source titles and content appear together inside the shared contextual panel, using EvidenceStack.
- Assertion to next assertion: 16px before and after a hairline. No bottom margin
  on the final assertion, whether evidence exists or not.
- No attachments: omit the collection, or let an empty EvidenceStack render hidden.
  Missing linked records are different: show the unavailable indication.
- Actions follow the evidence in ActionGroup. Editors reuse the same owner layout;
  form fields have their own field gaps, not extra paragraph margins.

`ReadingStack` and `ReadingSection` provide 24px section separator spacing and a
16px heading-to-content gap. Empty optional sections are omitted by the caller.
No descendant page selector may change these component interiors.

ClaimCard adds domain kind, explicit scope, limits and actual attribution over Assertion; it is not a persisted Claim entity. Its direct children keep zero outer margins so the shared 12px interval remains exact; source rows use 8px. Statement-count buttons and duplicate statement readers are retired. The grouped View evidence (n) action opens complete evidence directly and preserves return focus.

## Direct evidence amendment

Statements stay inline. Do not render Statement details, Inspect statement, statement-count openers or a second statement reader. Each item has at most one View evidence (n), directly opening complete source excerpts and explanations. Evidence panels never contain another View evidence action. Supporting results is distinct content and may open the shared panel, with its evidence already expanded. Missing saved sources remain explicitly unavailable.
