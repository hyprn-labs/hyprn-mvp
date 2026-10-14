# Continuous modeling approach UI — integration candidate

Status: implementation committed; integrated browser acceptance pending with the root
executor under the focused delivery amendment. This is not phase completion, human
acceptance, a completed scientific assessment, or deployment evidence.

## Source and scope

- Implementation: `d969ccfb777f98fac03de300c667a785e51521d6`.
- Parent for the tested candidate: `c756b19` (answer API integration). Earlier local
  prerequisites: plan `991aa1f`, result-format follow-ups `de2eeb8` and `9dd4e8c`.
- Owned changes: ApproachPanel, ApproachMethod, ApproachFindings, scoped styles,
  approach browser tests, findings-native and unit-native browser selectors,
  approach-layout UI contract assertions, control map, UI target and layout notes.
- No backend, API client, generated contracts, configuration components, assumption
  owners, runtime inputs, live records, STATE, ROADMAP or HANDOVER changes.
- The external user-approved minimal mock supplied composition only. Its illustrative
  questions, values and answers were not imported as product or study data.

The reader now follows the complete saved question, expandable methods, compact
expandable cases and final study answer. Section links preserve the workspace route.
Methods retain canonical exact model views and assumption owners. All associated
configuration/run links remain present. Outputs use the shared table, with units,
missing-value reasons and explicit zero; full precision and execution/criteria remain
supporting details. Scientific prose comes only from exact-approach answer records;
saved study answers open the exact case-answer versions they cite. Basis reads are
bounded and fenced by study/session/access; denied or changed identities clear them.
Historical records explicitly state that answers are not included in that record.

Range formatting of changed functions accounts for much of the line delta. The
changed-line style gate requires formatting; unrelated owners were not reformatted.

## Verification

Every check below ran through `./hyprn-mvp dev check <group>`, with an isolated runner
scope. Scope UUIDs identify external evidence; no screenshots or stores are tracked.

Final candidate, source-identical to the implementation commit:

| Command | Result | Evidence scope |
| --- | --- | --- |
| `./hyprn-mvp dev check combined-static` | 6 stages passed, 0 failed; design, tokens, UI contracts, criterion checks, TypeScript, build | `bb909eb6-9d62-43ef-9a98-9dfb1db2900d` |
| `./hyprn-mvp dev check style-ratchet` | 33 passed, 0 failed, 0 skipped | `9178a1e4-d213-46c0-96d7-37d2cc43c4ac` |
| `git diff --check` | passed | candidate tree |
| `./hyprn-mvp dev check guard` | 116 passed, 0 failed; implementation commit plus this checkpoint | `9b6cf5cf-4863-41a8-891e-cfb4c55ab02b` |

All failed or superseded executor runs:

| Group / scope | Result and disposition |
| --- | --- |
| combined-static / `036e50d5-3ff6-48ad-b937-f98b58546ab9` | Design/tokens passed; source checker failed on obsolete Study limits wiring. Updated scoped assertions. |
| combined-static / `7faf95ad-fd05-4a4a-bb24-a2070f8d0fe7` | Design/tokens passed; source checker expected removed chapter tab IDs. Replaced with continuous-navigation guards. |
| combined-static / `4e968632-faaf-4afb-953a-addd10a02fe4` | 6 stages passed; superseded by answer integration and final changes. |
| approach-ui-method / `8880d886-0cc9-40b2-ba36-329a435ed4cd` | 8 reported passes, 2 failures, 0 reported skips, then a 150-second subprocess timeout. Collapsed step actions and partial-link selector were corrected. Model-description rebind test timed out without a final assertion report; integrated rerun remains required. Source/test edits during this early run mean it is not final acceptance evidence. |
| style-ratchet / `6c5d10aa-170a-4e8b-a586-b3917c7d7dac` | 32 passed, 1 failed: 145 changed long lines. Scoped range formatting corrected them. |
| combined-static / `1e72e483-2a74-4055-bcbb-9d581962c5bb` | 6 stages passed; superseded by formatting and final changes. |
| combined-static / `a283e639-ea5d-4bba-8eaa-7626ccbb9cd7` | Design/tokens passed; source checker failed on formatting-sensitive slice spelling. Updated the assertion without dropping its bound. |
| style-ratchet / `c2500dcd-b980-4160-aa56-a65674cccb93` | 33 passed; superseded by final changes. |
| combined-static / `0ef1d980-2a97-446e-aafc-2b0f6655b459` | 6 stages passed; superseded by final changes. |
| approach-ui-reading / `4053a763-4a84-43ad-8706-e28fbfc4a419` | 16 passed, 3 failed, 0 skipped, 105.85 seconds. All three new scenarios requested a model-package fixture absent from the lightweight reading group; they failed before UI assertions. Moved them to the method group, which supplies that fixture. Existing 16 reading scenarios passed. |
| combined-static / `7dd5a76f-4c90-4641-8f6c-42f63db73d72` | Design/tokens passed; source checker rejected a retired output-region label. Reused the canonical Output values label. |
| style-ratchet / `e9f61f64-c2a1-4b8a-b9a7-68141296b970` | 32 passed, 1 failed: two changed long lines. Wrapped import and shortened invariant test title. |
| combined-static / `8ff56566-4ddc-4976-b84f-fc8ee36a3f82` | 6 stages passed; followed only by browser-helper and session assertion changes. |
| style-ratchet / `1ccad64b-b500-45fa-beab-6309c625fea6` | 33 passed; followed by those test changes. |

An early method screenshot was inspected: `polish-method-saved-light.png`, scope
`8880d886-0cc9-40b2-ba36-329a435ed4cd`, SHA-256
`30bfef1aa734be9ec006d226f4a94436fccf46b63d59f301f198068ccba8ee3d`.
The reading scope includes `s5-approach-question-200-dark.png`, SHA-256
`372e02a6300003d16880eb99d26f8da3bfedec239f86eb9c01f78c9207b96794`.
These are intermediate visual artifacts, not final visual or human acceptance.

## Cleanup and remaining acceptance

The two browser commands exited. Four orphaned Chrome processes from the completed
executor scopes were identified by their exact scoped profile paths and terminated;
zero matching browser processes remain. Other processes were not targeted. External
test artifacts remain for diagnosis.
No live store or live browser profile was used. The dependency symlink remains
ignored. No tracked files were deleted; the implementation commit left a clean tree.

Root owns one integrated acceptance union after its serialized native lane:

- `approach-ui-reading`, `approach-ui-method`, `approach-ui-assumptions`,
  `approach-ui-configuration`, `approach-ui-history` (changed shared selectors and
  continuous reader affect all five groups).
- `findings-native-read` using the reviewed durable fixture, and `units-native`
  for the updated exact-step helper; root chooses whether its native union also
  needs to regenerate the findings fixture.
- Final combined-static/style on any integration or corrective source delta,
  plus actual UI inspection in both themes and narrow/200-percent layouts.

The three new method scenarios exercise section focus/route retention, persisted
answer revision pinning and sign-out clearing, and failed answer reads versus true
unassessed states. They are authored but have not yet passed their correct fixture
group. No browser success is claimed for the final candidate. Root explicitly owns
this remaining verification under the approved integrated-batch cadence.

## Self-check

Implementation commit exists; explicit owned paths only; no file deletions. Final
candidate static and style checks passed. Browser qualification remains open.

## Fixture follow-up

Root preflight found that the method fixture refused the new answer POST before
the saved-answer browser scenario could run. Its closed write allowlist now admits
only POST to the exact study answers collection, only in the method group. The
reading group still refuses it; DELETE and descendant POST routes remain refused.
Browser assertions cover these three negative cases. Other scenario actions use
existing permitted model-import, evidence, approach and session routes. No product
API or production permission changes were made.

`./hyprn-mvp dev check style-ratchet`: 33 passed, 0 failed, 0 skipped; scope
`a42f4cfe-ea7d-41eb-8178-8589a0ff2338`. Browser runs remain assigned to root's
integrated union; none were started during its active native lane.

All 17 earlier executor scopes and this follow-up scope were archived externally
with per-file SHA-256 verification before release: 18 scopes, 353 evidence/metadata
files, no remaining source scopes. The archive includes a release ledger and each
scope's hash manifest. No live or other executor scope was targeted.
