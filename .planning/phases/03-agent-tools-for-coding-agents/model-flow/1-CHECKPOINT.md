# Model flow — execution checkpoint

2026-10-16. One approved cohesive UI batch; not Phase 3 completion or release qualification.

## Delivery and commits

- RED: `50bb30f` — individual route / full-width reader / quantity action journey.
- Implementation: `100d7eeaa9eb1649a06e9da5ca01786ccc76f2f0` — 31 explicitly owned files, no deletions.
- Unrelated parent commit `4638b6a` is between those commits. Its files were not staged here.
- No production API/backend/dependency changes. ROADMAP, STATE, research and unrelated staging preserved.

Five exact model connections now have deterministic measured-port routing, individual selection and nearest-route pointer picking at reduced zoom. Explorer `portContent` retains its own renderer. Dedicated quantity tokens and the shared direction mark retain Input/Output words and combined connected meaning. The full-width Diagram / Model explanation composition and component Explanation / Python / Quantities panels preserve mounted editors and existing guards. Shared method prose belongs to model scope; local prose stays with its component. The single named table scroll owner clips its surface and retains row-heading parity, selection scrolling and direct quantity actions. Pending local removal opens an actionable editor notice rather than silently doing nothing. Preview dialogs remain visible outside hidden reading panels.

## Verification environment and commands

All groups ran through `./hyprn-mvp dev check <group>` in the pinned environment. Browser/build groups were serialized; style ran independently. Logs and retained artifacts are outside the checkout.

The parent supplied host-specific `HYPRN_MVP_DATA_ROOT`, `HYPRN_MVP_TOOLS_DIR`,
`HYPRN_MVP_SCRATCH_ROOT` and `HYPRN_MVP_CHROMIUM`. Interpreter/browser identities are
retained in the runner logs. Machine-specific home paths are kept out of this record.

Each table row gives the exact command suffix, result and runner session identity. Retained evidence is under `/private/tmp/hyprn-model-flow/.hyprn-checks/<session>/evidence/`; each session records exact scope/artifact identities and cleanup. Console logs named below are under `/private/tmp/hyprn-model-flow-evidence/`.

| Command (`./hyprn-mvp dev check …`) | Log | Result | Session |
|---|---|---|---|
| ui-reading | red.log | 27 pass, 1 expected RED, 0 skip; missing individual route | f8feaeec-e2b3-478f-8fbc-9f26d9140d04 |
| combined-static | static-first.log | stopped at obsolete literal named-region contract | 87715b82-1589-40f6-935f-51e53bb45dde |
| combined-static | static-second.log | stopped at lost unassigned Needs value smoke assertion | 171ce41a-a789-43b2-9e2b-b943750fc6e2 |
| combined-static | static-third.log | TypeScript: 6 TS2774 checks after portContent narrowing | e1decfcd-4d88-4317-9b35-5bfdb2375fc8 |
| ui-reading | reading-first.log | build refused adjacent specimen JSX; no browser tests | a85ea1c6-28ef-446c-a51c-4cb2b01b41d9 |
| ui-reading | reading-second.log | 26 pass, 2 fail, 0 skip: wrong sorted-port assertion, footer beyond 878px | 399a5932-53b2-4ada-8858-33745d1a5458 |
| ui-reading | reading-third.log | 29 pass, 0 fail/skip/flaky | b9576546-1bcc-40d4-848d-766254f1fb19 |
| units-ui-reading | units-first.log | 10 pass, 1 fail, 0 skip: test double lacked quantity-definition capability | aad1d2cd-7be6-4fcc-bf1a-479e7dd3d344 |
| units-ui-reading | units-second.log | 10 pass, 1 fail, 0 skip: reload needed fixture reauthentication | 5dcf7b7e-0ece-4a67-89d7-595527a41b38 |
| units-ui-reading | units-third.log | 11 pass, 1 fail, 0 skip: cancellation assertion expected already-closed guard | 8239badd-0482-42f1-adc1-350da5ac17cd |
| units-ui-reading | units-final.log | 12 pass, 0 fail/skip, 31.92s, no server errors | 09bcfe90-856a-4d4f-a3bf-8ed7338e47b5 |
| combined-static | static-final.log | 9 checks pass, 0 fail, 6.34s | 6ad505cc-0d52-4111-82b3-cbddda549b44 |
| style-ratchet | style-first.log | 32 pass, 1 fail: 85 findings including owned additions | 62bf7d82-6162-4a3a-b1e7-340597d1403c |
| style-ratchet | style-second.log | 32 pass, 1 fail: 63 findings | 5dc9e762-1e10-4db4-a620-b2a909847f7b |
| style-ratchet | style-final.log | 32 pass, 1 fail: exactly 61 pre-existing findings; no new findings | 37f689a1-3732-4d43-9657-b2dfeb420838 |
| combined-static | static-delivery.log | final source: 9 checks pass, 0 fail, 6.04s | 8641c0b3-b455-48f4-a6aa-1751c85b9592 |
| ui-reading | reading-final.log | final source/tests: 29 pass, 0 fail/skip/flaky, 24.87s | 0ef80634-1e71-433d-8c56-5f4186043417 |

An initial sandbox attempt could not access the pinned uv cache; it did not execute a test. The authorized escalated run provided RED evidence. Every listed implementation failure was corrected; the 61 unrelated style findings remain intentionally untouched, with no baseline changes. The deprecated Starlette TestClient/httpx notice is pre-existing and not a test failure.

The checkpoint's first commit attempt was rejected by the term-scan hook for private
host paths. Those paths were removed; no product source or verification result changed.

The final static and reading runs cover the committed production source. The final units run preceded only the local table-scroll selection correction and additional narrow/zoom assertions; committed-tree integration is owned by the parent. Static checks include design, ownership, generated tokens, UI contracts, tooling, smoke, color/unit tests, TypeScript and Vite build. The reading suite covers exact five-route anchors, obstacles, crossed-height routes, 50% pointer lanes, keyboard selection, Fit/resize, scoped prose, retained drafts, pending removal and cancelled-owner guards, and both-theme 390px final-column actions/surface parity. The genuine 200% final-action assertion is in foundry-nav and awaits the parent run.

## Fixture boundary and approved deviations

The parent approved narrow ownership extensions to `ui/design_smoke.mjs` for the shared export, `ui/check_ui_contract.py` for the named scroll owner, and `deployment/tests/units_ui_fixture.py` for schema-4 quantity definitions. The latter extends the existing declared private modeling double with advertised capabilities, set/clear definition operations and schema-4 validation, retaining historical schema 1–3 coverage. It changes no production service or runner.

`units-ui-reading` proves real product HTTP/API/auth/application persistence through row edit → preview → apply → reload, then clearing the optional definition and reloading. The private modeling transport and retained-history service remain explicit test doubles: this is not native modeling or numerical-execution proof. `ui-reading` uses the existing browser API double. No live scientific records were mutated.

## Cleanup, self-check and remaining obligations

- Runner sessions record `keep:false` and released scratch stores; evidence is retained in `.hyprn-checks`. No browser/test process remains from this executor.
- Implementation commit exists, exact owned paths were staged, `git diff --check` passed and no tracked files were deleted. No functional stubs or new network/auth/file-access surfaces were introduced.
- Parent owns committed-tree `combined-static`, `ui-reading`, `foundry-nav`, `units-ui-reading`, `ui-navigation`, and style union; foundry-nav/ui-navigation have not been run by this executor.
- Parent owns identity-checked live asset refresh and read-only visual inspection at the requested sizes/themes, including actual role contrast and all five live links. Automated browser results are not product-owner acceptance.
- Full qualification and genuine human acceptance remain outstanding under DELIVERY-PLAN. Do not report the whole repository green while the style baseline remains failing.

Self-check: implementation and RED commits exist; checkpoint is written; no unrelated edits staged.

## Live-review polish

Parent live inspection identified unnecessary outer loops on adjacent forward links and
redundant Model framing inside Model explanation. Commit `7566a59` addresses only these
findings in the route helper, ModelView, SelectionInspector and reading tests. Adjacent
routes use short rounded gutter elbows when their endpoint heights do not create
collinear overlap with another route. Reversed/equal-row conflicts retain distinct outer
lanes; bypass and feedback still route outside cards. The embedded inspector preserves
counts, assumptions, evidence and format limitations without a nested panel or Model
heading. Parent explicitly extended this follow-up's ownership to those reader files.

| Exact command | Log | Result | Session |
|---|---|---|---|
| `./hyprn-mvp dev check combined-static` | static-polish.log | 9 checks pass, 0 fail, 7.39s | 42a18fb6-6d40-4ba8-b268-70b9088ea923 |
| `./hyprn-mvp dev check ui-reading` | reading-polish.log | 29 pass, 1 fail, 0 skip/flaky, 26.73s | 1d72a6b9-379e-45da-9604-bca47a28af2d |
| `./hyprn-mvp dev check ui-reading` | reading-polish-final.log | 30 pass, 0 fail/skip/flaky, 25.04s | 5d23ab38-254b-43ba-9f09-877fb4ede639 |

The new straight-line assertion initially counted the arrowhead's 16px browser bounds.
Using the SVG path's own `getBBox()` correctly excludes markers; production source did
not need a correction. Tests now explicitly cover compact forward routes, the five-link
swapped-row outer lanes, an unaffected straight route, and absent duplicate model framing.
The final static run covers the production source apart from a comment clarification;
the final reading run covers the committed source/tests. Sessions released their scratch
scopes and retained evidence under the same external roots. No checks remain active.
Parent retains final committed-tree union and live visual verification ownership.

## Final integrated acceptance and live delivery

Parent verified production revision `7566a59` on checkout `114a3f6` (the latter adds only this checkpoint). Final evidence is `hyprn-model-flow-evidence/final-checks.json` and the six `final-*.log` files outside the repository.

| Exact command | Result | Runner session |
|---|---|---|
| `./hyprn-mvp dev check combined-static --keep-scope` | 9 stages pass | `fb4f8034-f2ed-42cf-a9e4-b4d0658a8428` |
| `./hyprn-mvp dev check ui-reading` | 30 pass, 0 fail/skip | `306c0ef5-2720-49ef-ae21-9fcd4e119c4a` |
| `./hyprn-mvp dev check foundry-nav --keep-scope` | 8 pass, 0 fail/skip | `2e226ef9-e69d-45a1-bdb5-2921ccc357ba` |
| `./hyprn-mvp dev check units-ui-reading` | 12 pass, 0 fail/skip | `74c4a87f-921e-421c-a808-3edb44dfe531` |
| `./hyprn-mvp dev check ui-navigation` | 9 pass, 0 fail/skip | `b879af1b-7a3d-403c-982f-0a0bd3dcecbc` |
| `./hyprn-mvp dev check style-ratchet` | 32 pass, 1 fail; same 61 unrelated findings | `c76c396b-4924-4b45-9bb1-66b5496ddb6c` |

All 59 browser cases pass. Static includes 16 design-tooling tests and 14 Node tests in its 9 stages. Style remains a known failure, with no baseline adjustment or unrelated formatting. No broad qualification or human acceptance is claimed.

Live delivery: the existing demonstration at loopback port 54821, scope `f7145c6a-9848-4541-8aa4-0acf069102fb`, now serves `7566a59`. The identity-checked refresh preserved a complete previous UI backup and atomically replaced the index after copying/verifying assets. Loaded JS `/ui/assets/index-Bgf2p3gb.js` and CSS `/ui/assets/index-GwisTI7D.css` match the manifest; final index SHA256 is `6d724c9587c62e2ed8189c3646cb9f970c493f0234ffcedf289d876dcac540ef`. Backend runtime and scientific records were unchanged; readiness metadata records only the new UI revision.

Actual browser inspection verified all five exact selections with two highlighted endpoints each; compact forward arrows and outer bypass; Fit model at 1440×1000 and 1920×878 (footer bottom 867px); model explanation once with actual linked components; component Python; XDSM; draft versus read-only saved-version actions; exact quantity-definition field focus without saving; coherent Day/Control room table surfaces; and 390×844 component focus/table scrolling with document width exactly 390px. Genuine 200% zoom and persistence use the isolated suites. The original System appearance and normal browser sizing were restored, Saved draft remains visible, and the requested model tab is left open. Only unrelated extension errors appeared in console capture.

Screenshots are outside the repository in `/private/tmp/hyprn-model-flow-evidence/`: `model-final-day-1440.png`, `model-final-day-1920.png`, `model-final-control-room-1440.png`, `model-final-narrow-control-room.png`, `model-explanation-final.png`, `component-python-final.png`, `table-day.png`, `table-control-room.png`, and `table-narrow-control-room.png`. Table screenshots preceded only routing/content-frame polish; their source/CSS is identical.

Integration correction: the initial passing static run released its build automatically, so the first refresh attempt failed before touching the live UI. Static was repeated with `--keep-scope` to retain the artifact. A first live review led to the recorded compact-route/content-frame polish; all final required groups were then run on that revision. Successful default scopes were released; retained build/zoom scopes are explicitly kept for 24 hours under the runner storage budget. No test process remains. No managed worktree was created.

The scoped UI task is delivered. Next owner: product owner for visual acceptance; existing phase/release obligations and unrelated style backlog remain with their recorded owners.

## Task 2 — Minimal model controls and persistent assistant

User-authorized follow-up; implementation prepared for the parent's committed-tree union
and live verification. Task 1's delivery record above remains historical evidence.

Commits: `2a64e4b` focused RED; `d78c5d7` parent-owned persistent assistant;
`1b1663c` model simplification (20 explicitly owned paths, no deletions).
ROADMAP, unrelated research, and parent-owned source were not staged by this executor.
The appended Task 2 in PLAN records scope and ownership; no phase closure is claimed.

Model changes: row Edit quantity details opens only its selected saved quantity; all-quantity
management remains on Component. Component / Python / Quantities retain mounted buffers
and navigation guards. Edit component combines name and optional explanation; its public
atomic edit batch uses rename_instance and set_annotation on that exact instance.
Architecture-and-contracts.md assigns model-local descriptions to annotations, and Edit4
already supports this operation and its 4096-character bound. Current draft loading and
saved reading use the shown snapshot's annotation. No localStorage, second prose store,
approach-method copy, backend/API/dependency change or live scientific mutation was added.
Shared/local approach prose and pins remain at their existing owners. Removed redundant
navigation, source expansion/instructions and header save-version explanation; navigation
has its own row and the title aligns with right-side actions.

Parent assistant scope (`d78c5d7`): persistent circular 48px neutral raised launcher with
the shared assistant iris; viewport-bounded 400px right panel on authenticated pages;
ordinary navigation persistence; existing session/access clearing, Escape/Close focus and
disconnected Send restrictions. An independent product supplied only a visual-pattern
reference; no proprietary source or asset was copied. Parent owns token, Contour, Button,
shared shell/context and assistant test changes. Layouts now agrees with Contour: scientific
context docks/stacks, while the assistant is a fixed viewport panel.

### Focused checks and failures

All commands use the pinned `./hyprn-mvp dev check` entrypoint and the same host-provided
environment variables as Task 1, with scratch `/private/tmp/hyprn-model-minimal` and logs
`/private/tmp/hyprn-model-minimal-evidence`. Browser/build checks were serialized across
parent and executor. Evidence is retained under the scratch root's
`.hyprn-checks/<session>/evidence/`, including exact artifact/scope identities.

| Exact command | Log | Result | Session |
|---|---|---|---|
| `./hyprn-mvp dev check units-ui-reading` | red.log | 11 pass, 2 expected RED, 0 skip; 58.18s | fd2a3dfc-6944-4a97-b95e-cc285a78781a |
| `./hyprn-mvp dev check ui-navigation` (parent) | assistant-navigation.log | 9 pass, 0 fail/skip; 9.36s | 922675a3-ffeb-42f0-89f5-8ee836d758da |
| `./hyprn-mvp dev check combined-static` (parent) | assistant-static.log | 9 stages pass; 5.99s | 7b7acd8c-a5ef-4f77-a6c9-78e6e5bde049 |
| `./hyprn-mvp dev check units-ui-reading` | units-first.log | 12 pass, 1 fail, 0 skip; 50.66s | a09d5fef-e11d-4cff-bb92-c42be290860c |
| `./hyprn-mvp dev check style-ratchet` | style-first.log | 32 pass, 1 fail; 65 findings; 16.78s | 025ca847-6044-4d2b-bb80-1188b9885472 |
| `./hyprn-mvp dev check style-ratchet` (parent) | style.log | 32 pass, 1 fail; same 65 findings; 15.35s | e8ef515e-faec-40ff-a5fe-dcf585172f53 |
| `./hyprn-mvp dev check ui-reading` | reading-first.log | 30 pass, 1 fail, 0 skip/flaky; 39.73s | b92ec1d8-c613-4e9e-826f-f29801506baa |
| `./hyprn-mvp dev check units-ui-reading` | units-final.log | 13 pass, 0 fail/skip; 36.91s; no server errors | cf39241b-4d72-4d27-b4b6-da9885985afd |
| `./hyprn-mvp dev check ui-reading` | reading-final.log | 31 pass, 0 fail/skip/flaky; 27.36s | cd067b52-eea6-42d9-aa95-8319bfd4134b |
| `./hyprn-mvp dev check combined-static` | static-final.log | 9 stages pass; 6.17s | e0cfd0d4-20c9-4a24-8edc-c82a08c88f52 |

RED proved that a row exposed four quantity fields and Component did not exist. The first
GREEN units run found the populated explanation textarea lacked an explicit stable
accessible label; added aria-label. The first reading run found an older assertion looking
for the component title in Python; it now verifies preserved Python selection after guard
cancellation, reads the title in Component, then verifies unchanged source in Python.
Style found four new diagnostics (one fixture long line counted twice and two test lines);
those exact lines were corrected without touching the 61 unrelated findings or baseline.
Parent will confirm the final style count in integration; style is not claimed passing.

The final focused runs cover `1b1663c` production source and tests. Public HTTP tests prove
name and instance explanation survive preview cancellation, atomic save and reload, retain
a sibling annotation, and read the original nonempty explanation/name from an old saved
version without edit controls. They also prove single-quantity definition save/reload/clear.
The existing fixture's private modeling double gained only declared instance annotation
editing and nonempty historical fixtures, preserving schema validation and other records.
Real application HTTP/auth/storage are exercised; native modeling and numerical execution
are not proven by this double.

Reading tests prove source text is never executed, caret and local scroll survive Component
tab changes, Tab leaves source, narrow layout stays contained, navigation cancellation keeps
the draft, and removed controls stay absent. Prior source verification and method/pin tests
remain in the passing suites. The older `source-editor.spec.ts` expansion assertions were
updated, but its native `ui-served` group was deliberately not run; no full served/native
qualification is claimed. No functional stub was introduced.

All executor scopes above were released (`keep:false`), with evidence retained externally.
No executor check process remains. Self-check: RED and implementation commits exist;
explicit staging and `git diff --check` passed; no tracked file was deleted.
Parent owns the final committed static/reading/foundry-nav/units/navigation/style union,
retained-build refresh and read-only live inspection. Human visual acceptance and full
release qualification remain separate obligations.

### Task 2 — Final integration and live verification

Product source is `1b1663c`, including assistant `d78c5d7`. Commit `c5e5b5d`
changes only the genuine-zoom test interaction order after checkpoint `84c77e1`:
close the floating assistant before testing controls underneath it. No product
source changed after the passing isolated static build.

Concurrent explorer edits appeared in the shared checkout during final checks.
They were preserved; a clean managed verification worktree pinned the committed
revision and reused the existing locked UI dependencies. Final evidence is in
`/private/tmp/hyprn-model-minimal-evidence/isolated-*.log` and the referenced scoped
runner evidence under `/private/tmp/hyprn-model-minimal/.hyprn-checks/`.

| Entry-point command | Final result | Seconds |
|---|---|---|
| `./hyprn-mvp dev check combined-static --keep-scope` | 9 stages pass | 5.96 |
| `./hyprn-mvp dev check foundry-nav --keep-scope` | 8 pass, 0 fail/skip | 26.05 |
| `./hyprn-mvp dev check ui-reading` | 31 pass, 0 fail/skip | 26.93 |
| `./hyprn-mvp dev check units-ui-reading` | 13 pass, 0 fail/skip | 32.32 |
| `./hyprn-mvp dev check ui-navigation` | 9 pass, 0 fail/skip | 9.03 |
| `./hyprn-mvp dev check style-ratchet` | 32/33; same 61 unrelated baseline findings | 10.43 |

All 61 browser cases pass. Genuine 200% zoom uses the browser extension zoom API,
not viewport emulation. Source save/history checks use real application HTTP/auth/
storage with an explicit private modeling transport double; no new native execution
or full ui-served qualification is claimed.

Integration failures retained: the mutable shared tree had 74 style findings and
a zoom failure with an unrelated open study dialog. Those runs were superseded by
isolated checks. The isolated zoom run first exposed the always-open specimen
assistant obscuring a context control; `c5e5b5d` corrected the user interaction
sequence and the full group passed. The four executor-owned style additions were
removed; the isolated count returned to 61. No baseline was weakened.

The live UI changed concurrently after the baseline capture. The identity/hash
guard refused this session's refresh before any write. The newer served assets
were preserved and directly verified: JS `index-LZ2S3b-9.js`, CSS
`index-CZNX0WIG.css`, index SHA256
`10abb7b78cc99b51e6db360ea5572f0719b59dfca7ed56375b0d1525adf9ca7f`.
`live-preserved-manifest.json` records their hashes. The live artifact includes
concurrent UI work and is not represented as a pristine build of this commit.
Readiness metadata and scientific records were not written by this session.

Direct browser evidence covers the requested model at 1440×1000 in Day and
Control room, 390×844 table/assistant layouts, and the restored normal viewport.
The title/actions align; requested duplicate controls/text are absent; Component
has both editing fields; the quantity dialog contains only the chosen quantity;
Python has source controls only; assistant persists through Profile navigation,
updates its context, fits inside the narrow viewport and closes with Escape.
Page width equals viewport width. System appearance and normal viewport were
restored; Saved draft is visible with no pending edits. Screenshots are external
`live-model-light.png`, `live-model-dark.png`, `live-one-quantity.png`,
`live-component-dialog.png`, `live-python.png`, `live-assistant*.png`,
`live-quantities-narrow.png` and `live-model-final.png` in the evidence root.

Default test scopes were released; retained build/zoom scopes expire under the
runner's 24-hour storage policy. The clean verification worktree was archived
after evidence capture. No test process remains. Human visual acceptance,
the disconnected chat integration and full release qualification remain separate.

Integration handoff: unrelated explorer/shared-design edits arrived after `1b1663c`.
Parent is isolating that commit for exact-tree checks and the live artifact. A later mixed
working-tree style run reported 74 findings and cannot establish this batch's final count.
Those unrelated files and index entries remain untouched by this executor.
The documentation commit hook initially rejected a banned reference name; the wording
was generalized before retrying, without changing implementation or verification claims.
