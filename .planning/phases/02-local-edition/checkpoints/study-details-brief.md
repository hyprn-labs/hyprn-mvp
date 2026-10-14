# Study details engineering brief — executor checkpoint

User-authorized UI follow-up, 2026-10-14. Implementation commit: `bbd2f3d181d62fa84768747928a94cfdf39f726e`.
Base: `7085926`. Branch: `codex/study-details-brief`.

## Delivered behavior

Study details separates the saved question, current approach, assumptions, limits and open questions. Empty optional read-only sections disappear; authoring retains Add assumption and Add limit. Older limits prose stays visible without migration labels. Supplied authorship remains explicitly unverified. Evidence opens directly from each statement, with exact version and citation relationship available inside its detail. Conflicting evidence stays visibly labelled. Proposed conditions remain distinguishable from adopted assumptions. The Results limits action is absent when the saved approach has no limits.

Shared assumption and evidence components use an opt-in brief presentation; other owners retain their existing presentation. No public API, scientific values, saved record content or runtime source changed here. Root owns live content changes and the live UI rebuild. Formatter expansion is confined to touched syntax ranges in owned files; no baseline was changed.

## Verification and evidence

Commands ran from the attached isolated worktree after sourcing the existing development environment; normal checks used OS temporary scopes. All group commands used `./hyprn-mvp dev check <group>`.

- `combined-static`: final 6/6 commands passed (design checker, token generation check, UI contract wiring, criterion record tests, TypeScript, production Vite build). The TypeScript + Vite commands are the package build's two steps, with output in the guarded scope.
- `style-ratchet`: final 33 tests passed, 0 failed.
- `approach-ui-reading`: 16 passed, 0 failed/skipped. Tests include empty sections, full question retention, light/dark and genuine 200% zoom. The subsequent semantic delta preserves visible conflicting evidence and removes the empty limits navigation; root's integrated rerun covers final source.
- `approach-ui-assumptions`: final 18 passed, 0 failed/skipped, including direct exact evidence navigation, visibly conflicting evidence, editable assumptions and historical saved-context reads.
- `python3 ui/test_design_tooling.py`: 13 passed, 0 failed.
- `node ui/design_smoke.mjs`: all checks passed, 50 renders; scratch self-released.
- `git diff --check`: passed before commit.

Final static/style/assumptions logs and archived scopes:
`hyprn-orchestration-verification-leodc382`.
Reading evidence and first browser attempt:
`hyprn-orchestration-verification-_s7izfyu`.
Light desktop and dark 200% Study details captures were inspected: readable stacked sections, no horizontal overflow, body scroll within dialog. Automated browser evidence is not human acceptance. Reference-image comparison and product-owner acceptance remain unverified.

## Failures and corrections

- Final static rerun initially failed its named UI test registry after renaming the empty-limits navigation test. Updated `ui/control-map.json`; final static passed. Evidence archive `hyprn-orchestration-verification-c2lugkfl` in the external executor evidence bundle.
- First style run: 32 passed / 1 failed, 47 changed-line violations. Formatted touched syntax ranges. Second style run: 32 passed / 1 failed, 8 remaining long strings/comments; split those without changing text. Final 33/33 passed. Evidence archives `hyprn-orchestration-verification-tjz6sr70` and `hyprn-orchestration-verification-r4o5fth9`.
- First assumptions browser run: 15 passed / 2 failed. One old assertion expected removed "No assumptions" filler. The new hidden-version assertion accidentally included text inside the closed nested evidence dialog. Corrected the former to absence and the latter to visibility; final 18/18 passed. That first run also emitted a fixture SQLite-lock diagnostic; the two reported test failures were the assertions just described.

All 10 executor check scopes were archived and released with zero remaining; each archive's `release.json` records the identities. No live demo stores, services, authoring records or unrelated worktrees were changed. The primary checkout's ROADMAP edits were untouched.

## Integration obligations

Root owns the committed-tree integrated checks: combined-static, naming, hygiene, guard, units-guards, style-ratchet, approach-ui-reading, approach-ui-assumptions and approach-ui-configuration. The configuration group covers the changed empty-limits action. History-group assertions for removed explanatory labels were updated; full native/history qualification is deferred, with the retained-context assumptions regressions passing here.

Rebuild only the retained demo's owned static UI output through the existing Vite build command after integration, then reload its verification tab. Do not restart the numerical runtime for this UI-only change. Verify the updated authored study through the real owner-facing UI and retain screenshots separately. Human acceptance remains pending.


## Integrated acceptance and live demo

Integrated UI/checkpoint commits: `15e5ae7`, `7b590ab`. Scientific foundation:
`fcc715e`, `05b2a47`. The following committed-tree acceptance ran at `7b590ab`:

| Group (`./hyprn-mvp dev check`) | Result |
|---|---|
| combined-static | 6 commands passed |
| naming | 9 tests passed |
| hygiene | 5 tests passed |
| guard | 116 tests passed |
| units-guards | 138 tests passed |
| style-ratchet | 33 tests passed |
| approach-ui-reading | 16 tests passed |
| approach-ui-assumptions | 18 tests passed |
| approach-ui-configuration | 24 tests passed |

All groups exited 0; the 58 browser tests reported zero failures or skips.
Evidence bundle `hyprn-orchestration-verification-69503idb` retains exact commands,
logs, original scope identities and `release.json`: all nine scopes released,
zero remaining. The executor's final assumptions count above was corrected from
its reported 17 to the log's actual 18; no additional test run was required.

`npm --prefix ui run build -- --configLoader runner --outDir <owned-demo-ui>`
passed TypeScript and Vite, updating only the retained demo's static UI. The
existing large-chunk build advisory remains non-blocking. The browser verified the
actual saved full question, separate current approach and four cited limits,
absence of empty/internal labels, and exact source-version access. Its authenticated
session was renewed after reload. This is automated inspection, not human acceptance.
See [the rehearsal follow-up](../../../DEMO-REHEARSAL.md) for authored version and
history evidence, retained scope and scientific guidance integration limits.

All ten complete historical run records compare unchanged; the preceding approach
version remains intact. All 49 attested paths and the runtime descriptor still
match. No numerical execution, runtime restart, API change or new dependency was
needed. The later delta is checkpoint/state/rehearsal documentation only, including
removing machine-specific evidence locations from this checkpoint. Broader native
history qualification and release acceptance remain deferred.
