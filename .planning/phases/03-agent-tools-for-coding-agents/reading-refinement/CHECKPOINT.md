# Reading refinement — 2026-10-19

Implementation: `89e0b15`, on `codex/resume-domain-integration`.

## Outcome

- Overview, Models and Experiments share one heading-free navigation group.
- Shared inline MetricGrid reduces the live run execution summary from 169 to 48 px
  at the same viewport. Status and duration still come from the backend.
- Nested ResourceCard/Panel and answer-basis cards share sunken, shadowless surfaces.
- Comparison rows contain original-run outputs only. Other mapped calculation sets
  move to Answer basis, deduplicated and grouped by stored kind/exploration pin.
  Authored justification reasons remain intact; the UI does not invent support claims.
- /hyprn and generated playbook clarify uncertainty, causal consequences, concrete
  next analysis and the distinction between numerical checks and physical validation.
  Retired answer-field/diagnostic guidance corrected. Installed skill symlinks to repo.
- Audited CalculationsPanel content.description and CalculationDesign design.rationale:
  both come from public saved records. No coolant/fuel-specific strings found in
  application/src or ui/src. Scientific prose must not be added to app code.

## Verification and delivery

All checks use isolated local-edition groups and tested the implementation bytes
committed above. Committing changed no source. No numerical or runtime policy changes.

- `./hyprn-mvp dev check combined-static --keep-scope`: 9/9, 4.63 s.
  `/private/tmp/hyprn-reading-refinement-static-final.log`.
- `./hyprn-mvp dev check agent-tools`: 326 passed, one Starlette/httpx deprecation warning,
  58.82 s. `/private/tmp/hyprn-reading-refinement-tools.log`.
- `./hyprn-mvp dev check study-answer-ui`: 2 passed, no skipped tests, 21.69 s.
  `/private/tmp/hyprn-reading-refinement-browser.log`. Real browser/API/auth/store,
  recorded modeling fixture; no original numerical execution.
- Skill creator `quick_validate.py docs/agents/scientific-engineering`: valid.
- Initial static attempt failed TypeScript flatMap row-union inference; fixed explicit
  ReactNode row type, then the complete static group passed. No outstanding new failure.
- Deployed checked assets from scope `c5977279-ff20-4490-b92b-e98d6932fb65`; runtime
  hash unchanged. Restarted only the verified demo web process for playbook reload;
  dispatcher and worker remained running. Build scope retained under check-storage TTL;
  other group scopes released automatically.
- Live browser: heading-free navigation, compact run status/duration, four comparison
  output rows with unchanged values; supporting sampled calculation absent from table
  and present under Interactive estimates. Home inner card rgb(232,235,236), outer
  rgb(255,255,255), inner shadow none. Screenshots and API receipts in
  `/private/tmp/hyprn-reading-refinement/` (run.png, basis.png, home.png, prose.png).
- Public API authored clearer justification/uncertainty/next-analysis prose in new
  answer `af62b860-2d8e-4ea9-82ee-674554b5b155`. Readback confirmed exact comparison,
  outcome, alternative mappings and exploration pins unchanged; all 36 run IDs unchanged.
  Earlier answer versions and all scientific records preserved. No sampling or fitting.

Automated verification is not human acceptance or full release qualification.
Next: user review. Existing broader legacy-suite migration and release obligations remain
with UI/release maintainers; no unrelated roadmap/research edits included in this batch.
