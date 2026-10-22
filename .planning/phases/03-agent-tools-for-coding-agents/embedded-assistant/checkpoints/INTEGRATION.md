# Managed bridge integration — 20 October 2026

Source `1784d6d` from the earlier assistant worktree integrated as `0063509` on
`codex/resume-domain-integration`. Architecture-table conflict resolved by retaining
all current imports and adding only the assistant row. Unrelated working-tree changes
were neither staged nor reset. No provider credential read, remote session, paid call,
live data mutation or deployment occurred. The UI remains disconnected.

Acceptance on integrated source through `./hyprn-mvp dev check <group> --keep-scope`,
using the existing host environment and isolated scratch-checks stores:

| Group | Result | Seconds | Scope suffix |
|---|---|---:|---|
| assistant-bridge | 97 passed | 1.73 | dc17b01a-5b8c-4eec-b823-ebc26ba68a33 |
| agent-tools | 327 passed | 65.28 | 522bfddd-943a-47da-8b2d-0f649e82e03b |
| locality-contracts | 165 passed | 13.83 | 79d42b3c-d3ca-4e94-a38a-5288ca275bae |
| style-ratchet | 32 passed, 1 failed | 13.66 | 4a5ea372-8ff6-49c2-9e00-52e51d343c8f |

Style failure is the whole-tree ratchet: formatting/line-length findings in existing
application, UI, tests and deployment files. No assistant module/test is an offender.
Offending lines in the two touched registrations are outside this commit's additions
(checked against the parent diff). No baseline rerun or broad reformat was performed.
The integrated tree is therefore not claimed to pass every acceptance gate. Existing
Starlette deprecation warnings remain. Test resources released by the runners; scoped
evidence retained. No native services, containers or browser instances started.

The 97 tests establish normalized synthetic request handling, study admission, duplicate
identity and Stop/uncertain-delivery behavior through the existing runtime/public API.
They do not establish durable restart, actual provider behavior or an operational assistant.
See ../CURRENT.md for the user-visible target, pending provider/credential/budget choices
and the next complete implementation batch. Do not resume the obsolete approach-domain
instructions from the original proposal.

Official docs verified this turn (no account-backed calls):
- https://developers.openai.com/api/docs/guides/agents-api/overview
- https://platform.claude.com/docs/en/managed-agents/sessions
- https://platform.claude.com/docs/en/managed-agents/tools
- https://platform.claude.com/docs/en/managed-agents/budgets

Claude budgets are specified in whole US cents as strings, can be set only at session
creation, and pause new requests with possible in-flight overshoot. They must not be
presented as exact cost cutoffs. Actual account eligibility/configuration remains unknown.
