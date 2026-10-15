# Callable hyprn skill and lightweight status reads

User-directed quick batch, 2026-10-15. Tested implementation commit: `baabd60`.
The user requested a callable skill named `hyprn` and authorized short useful
application/client corrections. This bounded batch uses focused verification;
it does not reopen a numerical-runtime or release qualification phase.

## Delivered

- Repository-owned scientific skill is named `hyprn`, with Codex interface metadata
  and a local user-scope link to that source. Codex `skills/list` discovers exactly
  one enabled `hyprn` entry. Direct invocation uses `$hyprn` with the brief/documents;
  no custom Codex slash-command implementation is claimed.
- The launch sequence makes discovery, deliverable coverage, reference comparability,
  quantity meanings, scoped assumptions, adaptive iteration and coherent answer
  readback explicit. Guidance supports API-only work without a browser requirement.
  New examples use thermal/process questions and generic references. Existing aircraft
  exercises are explicitly hypothetical, not facts about the source paper.
- The owner JSON-lines client accepts `run_status` for 1–20 distinct run IDs, calling
  the existing lightweight public endpoint once and preserving its response envelope.
  Invalid batches refuse before transport. No automatic retries or scheduler.
- Public API schema, UI, packaged playbook, attested source and live study data were
  not changed. The unrelated ROADMAP edit was neither staged nor modified.

## Verification and evidence

On the committed implementation:

| Command / observation | Result |
|---|---|
| `./hyprn-mvp dev check local-api-client` | 10 passed, 0 failed/skipped; 5.16 s. |
| `./hyprn-mvp dev check style-ratchet` | 33 passed, 0 failed/skipped; 9.94 s. |
| Skill creator `quick_validate.py` using the pinned native Python, installed skill path | `Skill is valid!`, exit 0. |
| Temporary local Codex app-server `initialize`, `skills/list` with force reload | One enabled user-scope `hyprn`, correct source and interface; server stopped. |
| Public API status shortcut on retained study `a04b7ddc-0cd3-46d4-94f7-b4fed043b02a` | HTTP 200, 20 recorded runs, all configuration pins matched prior readback. Read only; no execution. |
| `git diff --check` | Exit 0. |

An earlier focused client run also passed 10 tests before formatting and a deterministic
invalid-ID fixture correction; the committed-tree run supersedes it. All three scoped
test stores were identity-checked, evidence archived, and released: `de669924-ef08-4ce7-b449-b508b47291dd`,
`3ee8ee7b-90f6-4dc7-88fb-acc1b52df668`, `24fed8ad-5eb5-4307-9088-27a1aa0879c3`.
External evidence folder: `hyprn-callable-checks-baabd60` in the task scratch directory.

Recovered failures: an initial patch did not match and changed no files; the first
test invocation could not write the tool cache inside the sandbox; sandboxed Codex
discovery closed before initialization and the local API connection was refused.
Those checks succeeded with narrowly approved local access. A formatter lookup used
an older environment without ruff; formatting succeeded with the current pinned one.
No test assertion failed and no server error was observed.

## Remaining boundaries

Skill packaging/discovery, client behavior and a real public read are verified.
No new full scientific study or independent behavioral evaluation was run; the
three new workflow scenarios remain evaluation inputs, not passing evidence.
The workflow-agent integration owner retains that next step. Exact `/hyprn` slash
alias behavior in the desktop composer was not verified; `$hyprn` is the documented
explicit skill invocation.

Detailed API diagnostics and the expanded unit catalogue remain follow-ups: their
shared runtime sources require rebuilding/re-attestation. Execution timing and
readiness improvements are also deferred. No global instruction file changed,
no new dependency, no push, no UI acceptance or qualified release claim.
