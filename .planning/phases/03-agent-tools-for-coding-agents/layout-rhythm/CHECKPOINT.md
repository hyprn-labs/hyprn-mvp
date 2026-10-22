# Shared layout rhythm

User outcome: separate cards and record sections, readable narrative and alternatives,
comfortable control padding, and consistent design-system ownership across pages.
Target: existing local demo on port 54821; scientific data and runtime unchanged.

Implementation: shared flow recipes on study/model/calculation/configuration/run collections;
24px panel padding (16px narrow), 16px card gaps and 24px record-section gaps. Brief, answer
and model explanation use ReadingStack/ReadingSection, the 14/24 prose token and the existing
75ch measure. Alternatives are distinct inset option entries. Canvas search loses its old
4px screen override; shared 24/16px toolbar insets preserve focus clearance. Headings reserve
readable width and wrap command groups below. Wider reading tables scroll locally.
Ownership guard covers the new layout recipes; responsive browser checks measure gaps.

Development evidence:
- combined-static: 9/9 pass before final header/table adjustments; scope
  3653d17f-d03b-45bc-aeb3-735348c3f50d; /private/tmp/hyprn-spacing-static.log.
- foundry-nav: 11/12 pass. New narrative-spacing test fixture omitted the query string on
  brief versions, so it loaded no version; fixed route to match pathname. Other layout checks
  passed. /private/tmp/hyprn-spacing-browser.log. Final repeat required after CSS adjustments.
- Live early review confirms separated Run cards and readable alternatives; found heading
  crushed by actions at 728px, corrected in shared header flex basis and added regression.
- Final results and live readback are recorded below.

No numerical, API, sampling, surrogate or stored-record changes. No full release qualification
or human acceptance claimed. Preserve unrelated ROADMAP and untracked research/proposal files.


## Integrated delivery and review

Production commits: `ffa1b3e`, `027960f`, `c29c2b7`. Test navigation corrections:
`c747f14`, `2571af7`. Unrelated changes remain untouched.

- The strengthened ownership check found a second `.model-view .canvas-toolbar` padding
  override; removed instead of weakening the guard. Static attempt failed 1 ownership stage,
  then passed 9/9 at scope 42ce9439-a501-4d61-b569-e946001b6840.
- Final static/build on `c747f14`: 9/9, 4.840 s; scope
  14eb9079-14f1-46d7-bbeb-7d4305fd2246, log `/private/tmp/hyprn-spacing-final-static.log`.
  Later delta `2571af7` changes only the browser test's readiness wait.
- Second navigation attempt: 11/12, new test checked Models before its asynchronous cards
  arrived; replaced the early count branch with a locator wait/click. Third attempt: 11/12;
  the new measured spacing journey passes all desktop/narrow assertions. Zoom failed when
  answer controls appeared between Tab and Shift+Tab; now explicitly awaits both readers
  before checking tab order, preserving all focus assertions. Final committed run passes
  12/12, zero skipped/flaky, 32.250 s; scope 9e379541-98d4-4abc-9c3a-7a8ddbfeb9e1,
  evidence session a7a40ad2-25ab-4173-ac70-91f48364fc35,
  log `/private/tmp/hyprn-spacing-nav-ready.log`.
- Broader ui-reading: 24/33 pass, 9 failures against retired UI: old run-files disclosure,
  old About this study/Edit study/modeling approach, run-label-as-button, run criterion ledger,
  old model explanation/component text. Evidence session d1ea40e4-1ea3-4866-90a2-12804af3476b;
  log `/private/tmp/hyprn-spacing-reading.log`. No failure is a spacing assertion. These are
  unqualified journeys; UI test maintainers must migrate them to the current domain in a
  separate batch. No full-suite or release pass is claimed.

Final assets published with the guarded helper; runtime fingerprint unchanged. Build manifest
and previous live index: `/private/tmp/hyprn-final-exploration/ui-delivery`. Live readback on
study 1174be5a-8527-4a51-83d9-aad3c8e4aeaa at 728px confirms readable header/action wrapping,
separate alternatives, heading/table clearance, card separation, model search clearance,
and Execution-to-tabs-to-outputs spacing. Screenshots under `/private/tmp/hyprn-layout-rhythm/`:
overview.png, alternatives.png, model.png, configurations.png, run.png. All scientific records,
output values and runtime remain unchanged. The user tab is left on Overview.

Next: human visual review. Browser scopes released by the runner; kept static builds remain
available for delivery/recovery. No unrelated processes stopped.
