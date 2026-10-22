# Evidence reader delivery — 2026-10-20

## Result and ownership

Own managed worktree, branch `codex/evidence-reader`. Initial base `222a021`; rebased
onto `78530e6` after detecting a concurrent live publication. Primary checkout and
its index were not changed. Implemented commits `9b5d710`, `b9925fd`, `0c1e966`,
`a6b5e5c`, `1d955a5`, `c84b155`; `b60a1eb` reconciles design-system wording only.
Final executable UI source is `c84b155` (unchanged by subsequent documentation).

Shared source → exact excerpt/location → attributed explanation. Legacy notes stay
notes, without inferred quotations. Brief assumptions/limits/criteria and answer
justifications open the same shared details panel. Model explanation links deduplicate
through the same component. Evidence library reads cited versions directly, including
history and explicit component bindings; there is no nested View evidence. Missing
and partial reads remain explicit. Saving a new version never retargets references.
Library prose and spacing use the existing tokens and reading compositions.

The larger live study exposed needless run-by-run history loading. Frozen configuration,
model and approach closures are now read once; one retained run is a fallback for a
missing owner. A 202-run regression verifies only that fallback run is read.

## Integrated acceptance

Every group invoked through `./hyprn-mvp dev check GROUP` in this worktree using the
pinned local-edition runtime. Host environment setup is outside the repository at
`/private/tmp/check-evidence-worktree.sh`. No test writes touched the user installation.

| Group | Result | Scope / archived session |
|---|---|---|
| `combined-static --keep-scope` | 9/9, exit 0, 5.61 s; design/token/ownership/UI contract, smoke, unit checks, TypeScript and Vite | `40c150fd-3546-4337-8099-d6ba579858f6` / `3fe6f64e-5396-46cc-9f27-564c4c9fd209` |
| `ae-ui-evidence` | 15/15, 0 skipped, exit 0, 30.69 s | `677ed26f-cf08-42c1-8014-93110911ee03` / `5e4cc7f6-6473-48b2-9940-c212fe366173` |
| `brief-ui` | 3/3, exit 0, 24.66 s | `144b5614-6edd-4b7a-9870-953087ce6c5e` / `a3ba3188-ec16-45b5-9a56-a1d4be59bb8d` |
| `study-answer-ui` | 2/2, exit 0, 18.83 s | `4ba7aa08-81e3-4a0f-9fab-282f6044c043` / `ec7efa91-66e6-49b0-a2dd-a5f1bf703a99` |
| `ui-reading` | Final: 22/37 pass, 15 fail, 0 skipped/flaky, exit 1, 186.68 s; all evidence-library/reader cases pass | `2e90daa8-79c4-4581-abbd-5d5d176f64c5` / `46a01bec-8c72-4e2e-9809-e4d4aa52cfbd` |

Brief/answer tests ran on the same reader code before `c84b155`; that later change only
optimizes library ownership reads and adds its regression, covered by the final evidence
suite. Broad UI reading uses a declared browser API double. Evidence/brief/answer suites
exercise actual HTTP/API/auth/store with scoped fixtures; scientific execution is not
part of these checks. Light/dark, 390/720/1440 widths, immutable references, stale writes,
recovery, missing records, access loss, panel geometry and focus are covered.

Archive prefix: `/private/tmp/hyprn-configuration-checks/.hyprn-checks/`; each session
contains `evidence/hyprn-mvp-test-<scope>/` reports and screenshots. Ordinary fixture
scopes were released by the runner. Explicitly kept static-build scopes are disposable,
retained under the runner's 24-hour budget policy; no processes were left by tests.

## Failures encountered and resolved

- New worktree initially lacked locked browser dependencies: two environment refusals;
  installed locked `npm ci --offline`, no dependency changes.
- Static checks initially exposed missing inherited run status metadata and a stale
  duration-selector guard. Later integrated the exact deployed run-header polish,
  verified against its publication fingerprints; restored the final guard accordingly.
- TypeScript caught brief tuple widening and document-citation unknown typing; corrected.
- Fixture permission rules initially disallowed brief/evidence writes required to create
  real attachments; extended only the relevant isolated fixture groups.
- Browser regressions exposed helper save timing, ambiguous note-label selectors,
  stale CSRF after fixture reauthentication and hidden/global denial alerts; corrected.
- Navigation integration changed the shared evidence affordance class; corrected the
  test to require OpenLink. Spaced library composition required the matching guard.
- Earlier evidence-suite runs: 13 tests with 5, 6, then 1 failures; 14 tests with 1 failure;
  final 15/15 passes. Earlier brief run 2/3 before fixture correction, then 3/3.
- Earlier broad reading run 21/37; updated the obsolete library-detail test and obtained
  22/37. Remaining failures concern retired model/run/overview/help labels and selectors,
  model graph footer geometry, outdated design specimen exports and old version labels.
  These remain open outside this evidence change; this is not full release qualification.
- Aborted test reads emitted BrokenPipe messages in the local fixture server; final group
  exit status and all assertions passed. No production request was involved.
- A live publication fingerprint mismatch prevented overwriting newer work. Rebased onto
  the latest commits, resolved two import/reader-prop conflicts, and retained the deployed
  RunPanel/CSS delta whose hashes matched the primary files. One shell check was initially
  invoked without `bash` and returned permission denied; corrected the invocation.

## Live verification and recovery

Local app `http://127.0.0.1:54821/ui/`, target study
`b27f14ae-e101-448c-a9e5-aed5bc6d9cb1`. Guarded static publication from final kept build:
`/private/tmp/hyprn-configuration-checks/hyprn-mvp-test-40c150fd-3546-4337-8099-d6ba579858f6`.
Index SHA-256 `bbc1ac673d7e53b2d3840c78e870051474c45035f3a4693b0d3a6502fc17e45d`.
Source fingerprints, compiled asset hashes, previous index and recovery publisher live
under `/private/tmp/hyprn-evidence-reader/live-delivery/`. Content-hashed old assets remain.
Backend runtime hash was unchanged; no backend restart, schema change or authoring edits.

CUA verification: library contains the actual cited version directly; answer View evidence
opens one shared panel; no nested button; record metadata identifies the exact version;
expand/restore, metadata dialog return, assistant alongside details, close and navigation
all work. Final screenshot: `/private/tmp/hyprn-evidence-reader/live-evidence-final.png`.
Larger current study `1174be5a-8527-4a51-83d9-aad3c8e4aeaa` completes its empty referenced
library within the observed 9.3-second login/read window after the optimization.

The older study `50e423fd-a709-4e21-9381-0b09022b4115` is absent from this running installation.
The target live study contains an authored note, explicitly without a source quotation;
it is intentionally not relabelled or migrated. Exact source/excerpt/page and assistant
attribution were verified with representative isolated browser fixtures, including
`structured-evidence.png` in the final evidence-suite archive. No fabricated live evidence.

Automated and agent browser verification are complete for this UI journey. Human acceptance
is pending user review. Full release qualification is not claimed. Next owner: primary
maintainer can integrate this branch and address the unrelated broad-suite regressions;
keep this worktree attached for review.
