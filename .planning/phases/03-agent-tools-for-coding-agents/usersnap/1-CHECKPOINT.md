# Usersnap Task 1 checkpoint

Date: 2026-10-20. Implementation, parent acceptance and local-demo deployment
complete. Provider activation and end-to-end feedback remain blocked on dashboard
sign-in. This is not a completed feedback journey, Phase 3 or release.

## Revision and ownership

- Plan/context: `1aa2986` (parent).
- Code: `e310379b7588d4b9efbcd260cc7e843b2db2b9e6`,
  `feat(03-usersnap): add optional feedback with response-specific CSP`.
- Exactly the plan's nine production/test/document paths were committed. No
  tracked files were deleted. Branch: `codex/resume-domain-integration`; shared
  checkout, no new worktree. Parent owns committing this checkpoint.
- Central planning, design/scientific-state edits, calculation/prediction work,
  hosted-staging records and unrelated research remained unstaged and untouched.
  Sibling source changes were ongoing during execution. Parent owns final
  acceptance of the integrated committed tree.

## Delivered behavior

Default-off mount-time canonical UUID configuration; inert bounded document
configuration; cryptographic per-response nonce; matching script attribute and
loader query; uncached full enabled HTML responses including conditional and HEAD
handling; existing asset/static/host/origin/framing restrictions preserved.
The async initializer uses system fonts, no geolocation collection and no local
storage, and adds no identity or study fields. Network, rejected initialization
and synchronous initialization failures leave real sign-in usable.

The new `usersnap-ui` group builds the real entry module, serves the real
application/WorkspaceFiles over a guarded ephemeral HTTP socket, and intercepts
vendor responses with test-owned scripts. All other HTTPS requests are aborted.
Five cases cover disabled/no outbound, coherent nonce and inherited frame style,
blocked unrelated/unnonced scripts, single initialization, and three failure
modes. No external feedback submission occurs.

## Commands and evidence

The parent-provided development environment script was sourced before each
command; its machine-specific location remains outside this portable record.
Every check ran through the pinned local edition entry point, with `--keep-scope`
requested for parent inspection and potential deployment artifacts.

| Exact command | Result | Seconds | Scope UUID |
|---|---|---:|---|
| `./hyprn-mvp dev check public-api --keep-scope` | 83 passed, 0 failed, 0 skipped; 13 existing warnings | 213.3 | `3847b86a-9e9b-435c-8d87-ccad15195969` |
| `./hyprn-mvp dev check combined-static --keep-scope` | 9 commands passed, 0 failed | 4.6 | `42110702-b28f-4d4a-b3f8-c797e0b4bc3e` |
| `./hyprn-mvp dev check usersnap-ui --keep-scope` | 5 passed, 0 failed, 0 skipped, 0 flaky | 7.8 | `a53e4d33-69d3-446e-92f6-6397e99a5db2` |
| `./hyprn-mvp dev check locality-contracts --keep-scope` | 165 passed, 0 failed; 1 existing warning | 13.4 | `8bb34e8f-7af2-4e29-adb8-a08c47579f2e` |
| `./hyprn-mvp dev check style-ratchet --keep-scope` | 32 passed, 1 aggregate failure | 13.8 | `12cda42a-4428-4096-8060-39d28bdf9b73` |

Find each scope as `hyprn-mvp-test-UUID` below the configured scratch root.
`evidence/result.json` carries exact commands, interpreter/scope identities and
target SHA-256 values; `tests.json`, `stdout.log` and `stderr.log` carry counts.
Browser evidence also includes `browser-report.json`, `browser-stderr.log` and
`fixture-build.log`. Combined-static includes design checks, token generation,
public UI contract, design tooling/smoke, client unit checks, TypeScript and build.

These initial runs tested the implementation working tree based on `1aa2986`.
The subsequent delta before code commit was pinned Ruff/Prettier formatting of
`ui.py`, `test_ui_static.py`, `usersnap_ui_fixture.py`, `usersnap.ts` and
`usersnap.spec.ts`; no behavior was changed. Parent reruns on the committed tree
are required before deployment and supersede this preliminary evidence.

The initial browser build is `artifacts/usersnap-dist`; the static build is
`artifacts/ui` in their respective scopes. Both initial `index.html` files have
SHA-256 `61763218742a303cb9dc7ac8fcda51e3cdbf68264b9f4d1731022f4b0c4ae268`.
These pre-format builds are preliminary evidence, not a final deployment identity.

## Failure history and adjustments

1. The single style run failed its aggregate tree assertion with **1,234
   findings**, including substantial pre-existing debt and this task's new
   formatting/long-line findings. Fixed only owned findings with the pinned
   Ruff/Prettier tools; no baseline update and no unrelated formatting.
   `deployment/checks.py` findings were outside the added hunks.
   A final source scan found no lines over 100 characters in the five formatted
   owned files. The full style group was not rerun; it remains unpassed.
2. Parent reported its first planning commit hook rejected a machine-specific
   workflow include in PLAN.md. Parent removed that include and committed
   successfully. No implementation effect.

No required focused group failed. Existing warnings are Starlette's httpx
deprecation and unregistered legacy pytest markers. No dependency was installed
or substituted. No implementation stub remains.

## Provenance, containment and cleanup

Official sources and service limits are recorded in `ui/provenance.md` and
`docs/operations/usersnap.md`. The parent's observed 14,839-byte global loader
SHA-256 is `77dc5d57b35f461bf85f0d4ed20bcbbe46f7f87b65d070cfb13f4c47d2c03d96`.
The loader/setup chain supports the exact initial widget/resources origins and
nonce-bearing blank frames. This is a mutable proprietary service, not a pinned
permissively licensed dependency. No vendor code was installed or vendored.

The browser fixture reports `server_stopped: true`, exited its browser process,
and released its ephemeral listener. Public-api completed the owned modeling
fixture's label-checked container/network teardown with no teardown error; it
imported no native numerical modules. No live installation/store was used.
All five evidence scopes are intentionally retained (`--keep-scope`), not deleted;
parent owns their release after artifact inspection/deployment. No authoring
record was removed.

## Parent handoff and remaining obligations

Rerun committed acceptance; coordinate sibling calculation work before publishing
the shared application; identify/recover the current demo release and private
configuration; activate only that installation; then record actual provider
requests, opening/closing, keyboard behavior, light/dark/narrow layouts and
workspace navigation. Provider dashboard authentication/activation was still
pending in the parent's latest report. Never expand the policy without concrete
resource evidence and the scoped constraints.

Implementation: committed. Committed-tree acceptance: parent pending.
Deployment: parent pending. Live widget opening: unverified. Feedback submission:
unverified. Human acceptance: pending. Full release qualification remains open.

## Self-check

All nine owned files and this checkpoint exist; code commit is an ancestor of
HEAD; no unexpected deletions or task-generated repository artifacts remain.

## Parent committed acceptance

The parent reviewed the nine owned paths, confirmed they matched `e310379`, and
reran every required group through the configured local edition entry point.
The commands above were repeated with `--keep-scope`:

| Group | Result | Seconds | Scope UUID |
|---|---|---:|---|
| public-api | 83 passed, 13 existing warnings | 95.8 | `87cee441-f5c0-45ff-ad8e-10778e122b3e` |
| locality-contracts | 165 passed, 1 existing warning | 12.9 | `00a5968b-4a07-419f-828d-2c0c0c7c844a` |
| usersnap-ui | 5 passed, no failures/skips/flaky cases | 11.0 | `10200a25-c842-4239-852d-9914f8670841` |
| combined-static | 9 commands passed | 6.0 | `19c2f58c-4fd2-4bff-a28d-f696cfd0ca56` |

Each command exited zero; browser/server teardown completed. The shared checkout
also contained the main chat's prediction/evidence-reader integration, committed
as `9e69b8e` and `d835661`. These reruns supersede the pre-format checks for the
Usersnap change. Subsequent main-chat UI publication is tracked separately below;
no claim is made that unrelated work received full release qualification here.
The broader style-ratchet remains unpassed.

## Local deployment and real-provider observation

The main chat published the integrated UI using its existing guarded publisher.
The parent verified the served assets include the Usersnap initializer, their
hashes match the publication receipt, and all UI source fingerprints match the
final baseline. No second UI publication was needed.

- Verified integrated HEAD: `e39ecba514ee4eade3ed9863ed4a8afabc62e9c2`.
- Final successful static-build scope:
  `0b1a5786-18cf-4ce3-9a69-5b67c9b6a9c5`.
- Served index SHA-256:
  `531c1898e0a09033b4d482b266e9cfb2c6db81a37239fbc8b431713a34a59aa7`.
- Served JavaScript SHA-256:
  `b096545bc3cf01792a2b7f6bf38e8eec96be712b68ef601b57df7c0b19eb4ba3`.
- Target: the existing loopback demo, scope
  `f7145c6a-9848-4541-8aa4-0acf069102fb`; no cloud deployment.

After the main chat reported its final live verification complete, the parent
enabled only this installation in its private launcher, retained the previous
launcher, and invoked the existing guarded web-only restart. It exited zero,
replacing web PID 88400 with 89151. The calculation runtime identity remained
`7dbcb3501fda57170d6e6df19911f53d57513ac1d4b278212632fcd543393bb5`.
No worker restart, calculation launch, authoring-store mutation or feedback
submission was performed by this task.

Two live GETs returned 200, `Cache-Control: no-store`, the configured public ID and
different matching header/document nonces. In Chrome the real global loader
created its Usersnap Feedback frame; no relevant CSP/Usersnap console error was
reported. HYPRN's sign-in form remained visible. This establishes real loader
startup, not successful widget opening or submission.

The dashboard initially showed **Set live**. The attempted activation did not
produce a confirmed success; subsequent inspection showed the session had
expired and required sign-in. The public loader still omitted the intended
project widget ID, and the demo showed no feedback button. The parent asked the
user asynchronously to sign in and retained the dashboard tab for handoff.
Do not claim project activation or silently broaden CSP to compensate.

Live receipts, the previous launcher, header pairs, browser observations and
screenshots are retained in the task's temporary Usersnap evidence directory
outside the repository. The private configuration receipt identifies the exact
restore path and before/after SHA-256; normal rollback is removing the opt-in and
using the same web-only restart. A read-only guard initially detected the main
chat's in-progress `exploration.tsx` change and refused a source-match assertion;
after its final publication the assertion passed. No deployment was made from
that mismatched baseline.

Remaining owner: this chat resumes provider activation after the user restores
dashboard sign-in, then verifies opening/closing, light/dark/narrow layouts and a
clearly synthetic feedback submission under the real CSP. Human acceptance and
full release qualification remain open. The isolated evidence scopes remain
retained under the check-storage expiry/budget policy; test processes and
ephemeral listeners were released.
