# Interface cleanup: evidence, answers and editors

User-directed batch, 2026-10-15. Implementation: `e5e98cd`; final redundant-return-link correction: `6e05318`.

Overview now reads question → study answer → methods. Cases replace the Evidence
workspace tab. Study support is a case title and aligned configuration/run/answer
actions. Every assertion shows its own evidence title and View evidence action;
relationship and version information stay inside the evidence detail. One Edit study
editor includes metadata and scientific context, with separated fields and cancel
restoration. Methods use a distinct purpose lead, reasoning/calculation panels and
Python disclosure. Model actions use component/quantity terminology, omit internal
version prose, and only offer additional recipients when code is shared.
Configurations lead with inputs and provenance; empty assumptions disappear.
Runs have Results, Model and Configuration, with files/diagnostics in Results.
Precision buttons are removed; values and exported precision are preserved.

The scientific skill and runtime playbook now distinguish exact source-supported
values from authored scenario choices. A Mach 6 source cannot justify a Mach 8 input.
One behavioral scenario was added; no independent evaluation of that new scenario
or scientific re-authoring of existing demo records is claimed.

## Focused verification

Commands use `./hyprn-mvp dev check` and isolated scratch scopes.

- `combined-static`: six stages pass on `e5e98cd`, 3.29s: design system, tokens,
  UI contract checker, four criterion-render tests, TypeScript and production build.
  Scope `f013c91a-acce-4095-b627-d5df48173042`.
- `style-ratchet`: 33 pass on `e5e98cd`, 10.82s.
  Scope `e87a38ea-8fd3-40a4-85b9-92fe311d4acc`.
- `approach-ui-method`: 19 pass, zero failures/skips on `e5e98cd`, 122.55s.
  Real browser/HTTP/API/store authoring, exact-version reads, editor save/reopen,
  navigation, both themes, narrow layouts and genuine 200% zoom. Private modeling
  responses are controlled fixtures; no fresh native calculation was performed.
  Scope `c82400ee-68c5-43d9-8382-d17c7144b9eb`.
- `agent-tools`: 270 pass, 42.67s, with the existing Starlette deprecation warning.
  Scope `45049617-2343-4e65-8dc1-263bd3c78435`. Guidance bytes are identical to
  `e5e98cd`; subsequent deltas were UI, test and design-document changes.

Final `6e05318` changes only the return-link visibility condition and formats its
component. Combined-static passes all six stages (3.14s), scope
`ef9e36c9-d658-4ae5-ac00-3e78179d670f`; style passes 33 (9.03s), scope
`c71055b5-6bf6-4166-a3d8-be1e2bd863d1`. The focused browser suite above covers the
main batch; the final link condition is checked in the refreshed live browser.

## Corrected failures

Initial TypeScript check caught a leftover shared-citation variable. Initial static
checker still expected the removed RunEvidence component. Browser collection caught
one malformed test delimiter introduced by range formatting. First collected browser
run passed 17/19; two tests still expected cases inside Overview. They now follow the
Cases tab. Three style attempts reported changed long lines/new-file formatting;
final style check passes. No failed check counts as completion.

## Demo and boundaries

The final static build is served in the existing demo scope; only its web child was
restarted, preserving the loopback address, stores and attested worker. External
folder `hyprn-interface-cleanup` contains the UI SHA-256 manifest, process identity,
screenshots and check evidence. All 14 completed check scopes were archived and released; the live demo scope remains active. Live observations verify the combined editor's
spacing, evidence beside individual limits, compact study support, method hierarchy,
Python source, model record placement, the single-instance component editor, inputs-first configuration, case expansion and all three run tabs. These are
automated observations, not human acceptance.

Numerical records and source content were not rewritten. Full qualification and a
scientific coherence correction of the existing demo remain separate. The unrelated
ROADMAP changes are untouched. No push/publication. Next: user review of the refreshed
interface; no additional feature work is a prerequisite.
