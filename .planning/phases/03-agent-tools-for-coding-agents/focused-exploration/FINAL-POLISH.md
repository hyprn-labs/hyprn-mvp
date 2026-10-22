# Exploration controls, Home navigation and initial curves

User-approved focused correction: units appear once per input; explanation actions say Why; model disclosure says Expand model / Collapse model; Select outcomes precedes Sample settings. Qualitative fields are compact labelled groups driven by study data, wrap independently, and share a toolbar with the bounded Plot against selector. No fuel-specific UI logic or numerical selection logic was introduced.

The concurrent navigation correction landed in the same batch: Home always opens Studies (a current-location marker on Studies itself), the study filter reads Active | Archived and study cards stack Open and Archive.

## Commits

- `f992cc6` Make Home always open Studies with Active and Archived filters
- `ba7c6d8` Simplify answer exploration controls and qualitative fields
- `c3eec92` Migrate approach and assumption suites to current reader controls

## Checks

Each group ran through `./hyprn-mvp dev check <group>` in a dedicated scratch root. Browser groups ran on the working tree that became `c3eec92`; the only later change before committing was one design-system wording line (`Expand calculation` → `Expand model` in Scientific-states.md).

| Group | Result | Comparison at parent `7c693b6` |
|---|---|---|
| combined-static | 9/9 stages, also rerun on committed `c3eec92` | — |
| ui-navigation | 18/18 | — |
| ui-reading | 33/33 (earlier specimen-coverage gap closed) | 32/33 before this batch |
| approach-ui-reading | 18/18 | 16/18 |
| ae-ui-evidence | 13/13 | — |
| ae-ui-configuration | 8/14 | 2/14; the 6 remaining failures also fail at the parent |
| ae-ui-model | 4/6 | 4/6; same 2 failures |
| term scan | 4 findings | identical 4 at the parent; none in this batch's files |

Remaining failures, all present before this batch: ae-configuration Seed2 retained owners, configuration assumption listing, outage stale context, genuine 200% context, Evidence page assumptions by owner, run Evidence tab; ae-model component assumptions local apply and statement/evidence rows. Not run: `exploration-ui` (native served journey; its spec changes are label renames, checked by search for retired labels) and full qualification.

## Initial curves on the live demo

Scientific preparation uses the public thin tools and restricted worker. Existing joint sampling and surrogate are retained; five original training points plus two disjoint checks per qualitative combination complement them on the declared initial-axis baseline slice, using unchanged bounds and tolerances. This repairs the default curve, not arbitrary boundary combinations. Unsupported vectors must remain no result. Recovery and returned record identities are persisted outside the repository in the task scratch manifest before dependent actions.

Interruption and reconciliation: the demo's dispatch loop ran in the foreground of the serving process, which ended with its host application at about 2026-10-17T20:25Z; the web process kept accepting runs. Check point 6 (run `37097f41-f325-4180-9001-705d5d034fc0`) stayed `accepted_run` and was never claimed (outbox read-only: 155 recorded, this one accepted, none dispatching or uncertain), so starting dispatch was a first launch, not a re-dispatch. Only the dispatch loop was restarted beside the existing web process; it verified the current attestation before launching. The run was recorded with exit status 0, then the manifest resumed.

Result: all three qualitative combinations have 7/7 recorded runs; each fit estimates 11/11 outputs and meets 11/11 unchanged error targets (22 held-out comparisons each, 0 failed). Fit requests `2acad2f4-0b5c-4f2e-bc38-25456ad3db56`, `d15bfe46-d7f6-4f65-b374-d9e7c3ed7238`, `3ba5ba17-118f-4ceb-8156-2445d350c8e3`. A met numerical target is surrogate agreement with the model, not physical validation.

UI delivery: the live UI was unchanged since its capture and was rebuilt from committed `aada619` (combined-static passed, 9/9) and published as a static refresh with the runtime unchanged. The served bundle contains Expand model, Collapse model, Select outcomes, Why, Active and Open, and none of the retired labels. No signed-in visual check of the live demo was made in this session.

The restarted dispatch loop runs from a desktop terminal tab, not a service; it stops with that tab. Human visual acceptance and full release qualification remain separate. Unrelated roadmap and research edits were not staged.
