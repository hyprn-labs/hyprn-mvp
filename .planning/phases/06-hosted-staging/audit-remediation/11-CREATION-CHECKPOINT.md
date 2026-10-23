# Shared study creation checkpoint

Date: 2026-10-23. Implementation: `114f186d`.

## Outcome and ownership

Canvas New study and Assistant Start a new study now render `StudyCreation`, one
application owner composed exclusively from the existing design-system field,
text-area, toggle and action-footer recipes. Required name and question precede
Autonomous agent (off by default); Cancel precedes primary Create study.
Both invoke the existing public workflow: create study, save the supplied brief
question, optionally submit the scoped autonomous request. Partial setup retains
command identities and continues the same study. Navigation away prevents a late
completion from replacing the new page.

No live study records, provider messages or deployments were touched. Scientific
sampling, surrogate checks and saved-version behavior are unchanged.

Existing browser creation fixtures now provide an explicit question and expect an
initial brief draft. Three scoped fixture adapters admit that normal public write
or revise the existing draft by its actual revision. No production API exception
was added. Shared navigation tests include the activity worker's harness/test,
committed here with parent/worker coordination.

## Verification

Commands used the existing installation's `HYPRN_MVP_DATA_ROOT` and
`HYPRN_MVP_TOOLS_DIR`; public browser stores were isolated and released.

- `./hyprn-mvp dev check brief-ui`: **3 passed**, 28.56 seconds. Real browser,
  API, receipts and store; native modeling is a declared double.
- `./hyprn-mvp dev check ui-navigation`: final **48 passed**, 0 skipped/flaky,
  56.87 seconds. Both creation surfaces, manual versus autonomous intent, retry
  command reuse, required fields, saved-model identity and activity disclosure.
  This group uses public-API-shaped doubles, not a live Assistant provider.
- `ui/node_modules/.bin/tsc --noEmit -p ui/tsconfig.json`: passed.
- `python3 ui/check_design_system.py`: no FAIL.
- `python3 ui/design_tokens.py --check`: fresh.
- `python3 ui/check_component_ownership.py`: 0 violations.
- `python3 ui/check_ui_contract.py`: passed.
- Three changed Python fixture modules compile; `git diff --check` clean.

Private logs: `/private/tmp/hyprn-creation-{brief-ui-2,navigation-2,design-check,ownership}.log`.
Final browser evidence is retained under check session
`0b0b2441-d96e-4040-bd7d-a1f7409c334e`, scope
`fedc56af-4b18-495f-b188-5a109a75dfab`. Inspected the light-theme 390px creation
screenshot: labels, question, toggle and trailing action order remain readable.
Automated evidence is not human acceptance.

## Failures and limits

Initial brief invocation stopped before building because the default tool-cache
path was sandboxed; explicit existing tool-cache location fixed invocation.
An initial TypeScript check ran while the activity worker's successor contract was
still being generated; final integrated check passed after generation.
First UI group: **45 passed, 3 failed**. Two new creation tests used an over-scoped
`form.filter` locator despite the correct visible switch; using the owning page
resolved those tests. The third exposed an existing title inconsistency for a
saved model after Assistant refresh; the activity worker fixed the reader to use
its selected version name with a historical-schema fallback (`b0295621`). All
48 passed on the resulting integrated source. Failure evidence remains in check
session `cb7928b1-0606-42f1-ada5-ae1db91cb0a6`.

Full qualification and live deployment remain the parent session's obligations.
Other creation-fixture groups received mechanical field/revision updates but were
not all rerun in this focused pass. The existing floating Assistant launcher comes
close to the creation footer at 390px; the parent was notified for shared-shell
review. This is not a claim that every mobile shell layout was requalified.
