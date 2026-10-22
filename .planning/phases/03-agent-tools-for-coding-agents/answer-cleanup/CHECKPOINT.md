# Concise answers and Experiments delivery — 2026-10-19

Implementation: `08b423f` on `codex/resume-domain-integration`. The final source tree is the
same tree built by the delivery static check; committing did not change tested bytes.

## Delivered

- Experiments names the model/version-scoped area containing calculations, configurations and
  runs. ADR-0011 and the domain glossary preserve their distinct ownership and exact pins;
  no redundant persisted grouping is introduced.
- Brief prose and assertions use the available reading width. Record IDs and immutable-version
  narration are removed from ordinary readers; technical details and version choices retain pins.
- One Alternatives comparison table separates output name, value, criterion and evaluation,
  with exact calculation links. Supporting sample sets stay accessible and exploration pins
  identify their role. Justification text keeps its cited records without raw inline IDs.
- Answer content 2 and agent authoring retire separate observations/qualifications/open
  deliverables. Interpretation preserves necessary qualifications; next analysis carries
  unfinished work. Legacy saved content stays byte-identical; editing copies carry it forward.
  Output names and evaluations are populated from the cited run/model and calculation binding.
- Current run detail/list projections use status and duration from real stored execution facts.
  Execution-diagnostic projection and its UI are retired; original artifacts and exports remain.
  Unknown/missing is never success. No sampling, surrogate or accuracy-policy code changed.

## Verification

Commands used the locked local entry point and isolated stores, with the development environment
loaded from its existing host configuration. Counts are not a release qualification claim.

| Command | Result | Evidence log outside repository |
|---|---|---|
| `./hyprn-mvp dev check study-answer-api` | 24 passed, 19.33 s | `/private/tmp/hyprn-answer-cleanup-api-final.log` |
| `./hyprn-mvp dev check units-api` | 94 passed, 44.20 s | `/private/tmp/hyprn-answer-cleanup-units.log` |
| `./hyprn-mvp dev check agent-tools` | 326 passed, 55.58 s | `/private/tmp/hyprn-answer-cleanup-tools.log` |
| `./hyprn-mvp dev check contracts` | 127 passed, 8.95 s | `/private/tmp/hyprn-answer-cleanup-contracts.log` |
| `./hyprn-mvp dev check study-answer-ui` | 2 passed, no failures/skips, 22.24 s | `/private/tmp/hyprn-answer-cleanup-browser.log` |
| `./hyprn-mvp dev check combined-static --keep-scope` | 9/9, 4.69 s, final delivery tree | `/private/tmp/hyprn-answer-cleanup-static-delivery.log` |

The browser check exercises real browser/controller/HTTP/auth/store with recorded modeling;
no numerical execution. It verifies concise answer editing, cited comparisons, exact saved
history and refusal to publish unprepared exploration. The final delta after that check was
comparison numeric alignment, a supporting-calculation label and shared table width; the final
static/build and live browser checked that delta without rerunning the unchanged API groups.

Interim failures, resolved: sandbox tool-cache denial (rerun with reviewed escalation); a stale
contract-interpreter location (used the configured locked environment); deleted Files/artifact
UI source assertions (updated to the current retained-export and summary controls); mistaken
`static --keep` group (corrected to `combined-static --keep-scope`). These failed invocations
were not claimed as passing evidence. The first 19-test answer run passed before five additional
format/history/lifecycle cases were added; the final 24-test run supersedes it.

## Live delivery

Demo study `1174be5a-8527-4a51-83d9-aad3c8e4aeaa`, origin `http://127.0.0.1:54821`.
Only the web process restarted, from PID 6175 to 37814. A first maintenance invocation inherited
the test-only scratch root and was refused before a process change; the ensuing new-format
write was rejected with HTTP 400 by the old server. The corrected maintenance invocation used
this demo's exact identity/scope and preserved other live ports and the dispatcher. No tests
used the live store.

The public API saved answer `ebde4145-cb51-4f27-9322-486c717a2737` with content 2. Earlier answer
`026ac8e2-724f-4aec-9a76-8fd338216ae4` remains immutable. All 36 original runs remain. The same
checked estimate and calculation pins are retained. Run-list reads measured 0.443 s then 0.359 s;
run detail reports Completed / 3.0376942919101566 s from retained launcher timing.

Live browser: brief paragraph and section both measure 532 px; no page horizontal overflow;
the comparison scrolls locally at the narrow viewport. Experiments exposes the existing three
tabs. Run list displays Completed; detail contains Status and Duration with no Execution details
button or visible record ID. Moving two sliders jointly changed real estimated values to
12.288590341746522 K and -2.5174419096520313 kW; run count remained 36.

Final built UI scope: `hyprn-mvp-test-a39dba6f-21e5-4fe2-98c6-ad1d0ec6c5bd`. Published through
existing fingerprint-checked helper; runtime fingerprint unchanged and prior index retained.
Screenshots and public-API readback: `/private/tmp/hyprn-answer-cleanup/`.
The final retained build scope is temporary under the check-storage policy; normal test scopes
were released by their runners. No unrelated process was stopped.

## Remaining

Human visual acceptance and broader release qualification remain outstanding. The previously
recorded legacy reading-suite migration debt is unchanged. The user’s separate roadmap and
research edits were neither staged nor altered. Next: human review of the updated demo.
