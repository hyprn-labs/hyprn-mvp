# Overview and shared method details

User follow-up, 2026-10-14. Delivered UI code: `87cb515`; final test-only delta:
`6310678`. Implementation commits: `81ee3f0`, `4c3dd1d`, `f2757e4`;
agent checkpoint: `471e17c`.

Overview directly reads the saved approach in three bordered sections. Case filters
are visible. Answers separate supporting results, sources and compact record details;
referenced case answers open in dialogs. Model and overview methods share purpose,
reasoning, plain-language calculation and exact Python source. Models edits the
existing approach draft and component source; saved overview content stays read-only.
Draft explanation edits survive reload. Port-metadata paste controls are removed.

## Verification

- `./hyprn-mvp dev check combined-static`: six stages pass on `87cb515` (3.6s):
  design system, tokens, public contract wiring, criterion record tests, TypeScript,
  production build. The later delta changes one browser assertion only.
- `./hyprn-mvp dev check style-ratchet`: 33 pass on `6310678` (11.6s).
- `./hyprn-mvp dev check approach-ui-method`: 18 pass, 0 fail, 0 skip on
  `6310678` (115.6s). Includes actual API draft save/reload, saved-version immutability,
  overview section/filter behavior, read-only source, navigation and narrow/zoom views.
- Actual demo refreshed with UI `87cb515`. Browser inspected Overview, case filtering,
  case answer support, model explanation editor and Python source editor. No scientific
  authoring record or run changed. The existing eight successful runs and their answers
  remain the numerical demonstration; no native execution was repeated for UI changes.

Initial attempts: unsupported `ui-static` group and tool-cache sandbox refusal;
static wiring assertions retained old labels/whitespace, then a draft-only editor used
an overly broad Snapshot type. Corrected before passing. Formatting checks identified
changed long lines, then passed after wrapping. First method browser run: 11 pass / 7
fail (old label/focus/source expectations, duplicate explanation selector and an exact
textarea-label lookup). Explicit aria-labels and updated expectations resolved these.
Second: 17 pass / 1 fail (obsolete assertion that Overview contains no Python source).
Final assertion checks the requested source disclosure and absence of editing controls.

Evidence is outside the repository in `hyprn-overview-refinement`: 18 root scratch
scopes released, 486 SHA-indexed evidence files in `cleanup.json`. Final browser scope
`19a8a253-af6e-47d5-ab31-427e79030086`; preceding 17/18 scope
`d3e21d0b-092e-4d0d-9f69-ec3777534183`. Wrapper logs retained alongside their result JSON.
The running demo scope remains active; unrelated ROADMAP edits were untouched.

Live screenshot `overview-refined.png` SHA-256:
`d37da7f74d16220dd4ba33423f3b92ceb32cc79918f6b60b49806b6a7720cd50`.
Model detail screenshot `model-method-details.png` SHA-256:
`8e7fe44103ecc923db6b0aaac3a8f0d2200e4edb540a6dafce1e34d98f04eaa1`.
Both are in the existing external `hyprn-result-format-cleanup` evidence folder.

Automated verification is separate from human acceptance. Full release qualification,
other hosts/clients and scientific mission/cost closure remain deferred. No push or
publication. Next action: user review of this UI iteration.
