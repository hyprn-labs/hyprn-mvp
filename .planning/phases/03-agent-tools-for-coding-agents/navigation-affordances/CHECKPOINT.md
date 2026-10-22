# Navigation affordances checkpoint

2026-10-20. Implementation commit: `447f1c5`.

## Delivered scope

One typed `OpenLink` owns named label + inclined arrow, arrow-only and back-arrow
presentations, reusing the existing SVG through the independent icons module.
Native URL links remain anchors; guarded application navigation remains buttons.
Reader dialogs, RecordDetails, SourceChip, evidence readers, references, record
lists, output/component inspection and returns adopt it. Passive facts/statuses
remain outside their separate arrow target. Commands lose link underlining.
Sidebar, tabs, graph selection, disclosures and editor/confirmation behavior remain
with their existing patterns. No dependency, API or scientific execution change.

Coherence, component documentation and the Contour inventory define the contract.
The ownership guard rejects raw anchors outside design and the removed Button
link variant. Browser checks exercise actual rendered controls with fixture APIs;
they do not establish live API acceptance.

## Verification

All commands sourced the existing host environment from
`/private/tmp/hyprn-collection-env.sh` without printing its contents, then used the
pinned local entry point.

| Command | Result |
|---|---|
| `./hyprn-mvp dev check combined-static` | Final 9/9 stages passed: design, ownership, tokens, contracts, 18 tooling tests, 142 smoke assertions / 117 renders, 27 Node tests, TypeScript, production build. |
| `./hyprn-mvp dev check ui-navigation` | Last run 21 passed / 1 failed / 0 skipped / 0 flaky. All navigation-specific cases passed. Sole remaining failure was the older unavailable-Assistant expectation; the owning agent subsequently updated that assertion outside this commit. |
| `git diff --cached --check` | Passed before the atomic commit. |

The new browser coverage verifies label/arrow composition, exact shared glyphs,
keyboard activation, exact record identity, Escape/focus return, passive run status,
URL semantics, command/sidebar/tab distinctions, both themes and 1440/390 widths.
Existing navigation checks cover guarded route changes, exact versions and evidence
readers. Screenshots were inspected at light desktop and dark narrow sizes.

Final static retained evidence:
`/private/var/folders/wh/2pmy8w2s1jn6g9mflpywh2500000gn/T/.hyprn-checks/54cccab4-d06f-41b2-95f0-76fbe41ffa62`.

Last browser retained evidence:
`/private/var/folders/wh/2pmy8w2s1jn6g9mflpywh2500000gn/T/.hyprn-checks/07d91d14-368f-4a80-bcc9-19d53f5727fc`.
Screenshots are in its evidence scope's `nav/navigation-affordances-*.png`.
The scoped runner released its scratch folders and copied evidence outside source.

These are precommit working-tree checks of the committed navigation changes,
alongside existing unrelated RunPanel/header-metric working edits. The final delta
after browser acceptance preserves SourceChip's trace colour on hover and formats
the two new modules; final static includes it. The orchestrator owns committed-tree
integration acceptance with the main agent's subsequent updates.

## Failures and corrections

- Initial sandboxed check could not access the approved tool cache; escalated
  checks used the same pinned environment successfully.
- Static migration initially exposed the old raw-anchor footer assertion, exact
  SourceChip class-string smoke assertion and the isolated renderer's explicit
  local-module list. All were updated for the shared component without weakening
  behavior checks. Earlier static evidence sessions:
  `930692e6-a3c6-4414-aa63-6d1944b1681e`,
  `ef352053-0549-4024-b324-9d7573ca8b97`,
  `8e538aff-f11a-402d-9646-d13082d5355c`.
- First browser run: 19/22. Two pre-existing expectations were reconciled with
  current code on orchestrator instruction: appearance defaults dark, and the
  export dialog completion label is Close. The third Assistant expectation remains
  main-agent owned. First browser session:
  `d8259edd-3ce9-469f-928e-0919a721ef27`.
- Existing React smoke warnings about title child arrays and list keys were
  observed; they were not introduced or altered by this task.
- Initial Git staging was sandbox-denied; approved explicit-file/hunk staging
  succeeded. No unrelated index changes were discarded.

## Ownership and remaining work

Only navigation hunks of RunPanel and foundry.css were committed. Existing run
duration/status changes, scientific-state/calculation documentation, hosted
planning and concurrent assistant edits were preserved. The concurrent Assistant
test hunks were explicitly excluded from staging and remain owned by that agent.
No tracked file was deleted, no dependency installed, no live deployment performed.

No implementation stubs remain. Full release qualification, real installed
application acceptance and human acceptance are not claimed. Parent integrates
verification and updates the shared current state; this non-numbered extension does
not advance the unrelated phase plan counter.

## Self-check

`447f1c5` exists in the branch; both new design modules exist. Reviewed staged scope
contained the 43 navigation-owned files/hunks and no unrelated state/backend files.

## Orchestrator integration acceptance

At HEAD `81bcbf9`, after independently reviewing the shared primitive, consumer
migration, documentation, guard and rendered desktop/narrow screenshots:

- `source /private/tmp/hyprn-collection-env.sh` then
  `./hyprn-mvp dev check combined-static --keep-scope`: exit 0, all nine stages
  passed (9.35 s reported check time). Evidence:
  `.hyprn-checks/a0bc8751-735a-47c0-823d-18c4d0f810b1` under the same host temporary root.
- Same environment, `./hyprn-mvp dev check ui-navigation --keep-scope`: exit 0,
  22 passed, zero failed/skipped/flaky (43.25 s reported browser time).
  Evidence: `.hyprn-checks/29bb6b33-43c0-46dc-9550-ca0ae0db508e`.
- Tested UI working-tree delta: earlier RunPanel status/duration and header-metric
  changes, plus the assistant owner's corrected Home conversation assertion.
  Those edits remain outside this navigation commit. No navigation source changed
  after acceptance; this final addition only records evidence.

The browser group uses the production UI with declared in-browser API doubles.
This verifies interaction/presentation, not native numerical execution. Scope and
evidence retention use the runner; no live stores were touched.

The main agent is conducting live provider/sampling acceptance. The verified UI
artifact and passing evidence were handed to that agent for coordinated publication;
this task did not publish over the active session. Full release qualification and
human acceptance remain separate. Implementation and focused acceptance are complete.
