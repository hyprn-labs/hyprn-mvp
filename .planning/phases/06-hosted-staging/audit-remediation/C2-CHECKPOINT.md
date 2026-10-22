# C2 — pinned native guidance and constrained research/review configuration

Implementation commit: `0b475c40296b74d78485a38f06cacff740d87600`.
Hosted startup follow-up: `39c09ba0`.
Owned files: `assistant/claude.py`, its tests, `deployment/managed_assistant.py`,
`deployment/managed_skill.py`, and setup tests. No provider/staging mutation or
budget reset occurred. Parent integration and live acceptance remain required.

## Delivered contract

- `bootstrap(deployment, model, effort, public_hosts=None)` creates an offline
  reviewed manifest. CLI: `bootstrap --plan ... --deployment ... --model ... --effort ...`.
- Existing `apply` and `reconcile` accept that bootstrap plan. Apply requires its
  digest; reconciliation uses only GETs. Bootstrap returns exact `skill` and
  `reviewers` bindings. Durable intents precede uploads/creates; unknown effects
  reconcile by identity and full downloaded content, never by automatic repost.
- `definition(..., bindings=..., public_hosts=None)` requires these bindings.
  CLI `plan --bindings ...` produces the final exact primary-agent configuration;
  `apply` provisions environment/primary only after checking skill and reviewers.
  Missing/latest skill versions, mismatched bundle hashes or reviewer pins fail closed.
- `validate_plan(plan)` recomputes the current inputs. Startup must also call
  `await verify_bindings(provider, plan)` before the existing primary/environment
  readback. `plan.bindings.reviewers` maps role to exact agent ID/version.
- `Claude.thread_agent(session_id, session_thread_id)` reads authenticated provider
  thread identity and rejects a mismatching session/thread response. Parent owns
  application-side read-only dispatch, durable role identity and bounded admission.
- Toolset starts disabled; only read, web_search and web_fetch are enabled.
  Reviewer custom tools come only from registry effect `read`. Inline agents,
  nested delegation, workflows, advisor, MCP and package installation stay disabled.
  No repository, application files, native store or host credentials are mounted.
- Public research hosts are explicit and plan-pinned. Generic scientific defaults
  can be replaced with repeated `--research-host` arguments. Blocked sources remain
  unverified and require a new reviewed provider plan. This provider sandbox policy
  is distinct from the attested HYPRN worker that alone executes scientific code.
- Review limits passed to parent: three threads, 24 custom calls per thread,
  12,000 task characters and 16,000 result characters. Prompt/context instructions
  are not provider-enforced hard limits. Cumulative USD 20/user accounting remains
  owned by the existing application budget path; setup creates no sessions or caps.

## Evidence

Both groups ran through the pinned entry point with the configured external
local development root/tool cache; fixtures created isolated scopes.

| Command | Result | Evidence identity |
|---|---|---|
| `./hyprn-mvp dev check assistant-bridge` | 165 passed, 0 failed, exit 0; 17.17 s | check `996c491f-e0c3-45ec-bfa6-587ef49b3992`, scope `1a15bc92-5837-4cbf-b2af-cc733f0bbbbc` |
| `./hyprn-mvp dev check hosted-assistant-setup` | 24 passed, 0 failed, exit 0; 12.12 s, committed tree | check `d7098db8-114c-47f5-b30f-3f2caa3efb9f`, scope `dd658af4-b5c7-4d6b-b7b5-83cbf96c5967` |

Bridge-tested provider files equal the implementation commit. The last setup delta
was a safe rejection of non-object skill-list records and was covered by the
committed-tree setup group. Scratch fixture cleanup completed; retained runner
evidence remains external. `git diff --check` passed for owned files.

Failures retained: first invocation exited 5 because the sandbox could not access
the existing uv cache; an approved escalation ran the pinned checks. Initial setup
run had 14 passes and two failures: stale-source validation returned a pin error
instead of release-drift, and the ambiguity fixture duplicated a reviewer rather
than the searched primary. Both were corrected. Later setup runs passed 22, 23,
then 24 tests as coverage was added. Earlier bridge runs passed 162 tests before
three authenticated thread-identity cases were added.

Observed system prompt: 1,649 characters; previously embedded playbook: 40,198.
Skill ZIP SHA-256: `7c562f4ecba5456b49a04b0bcb5da248dda15a2aaacaae5e99c69bea873b74ad`.
Frozen behavioral-scenario SHA-256:
`22e376fe1af2103c6149f27925e6d9f887b4d248e4b1f34dfb4d3bc7c493623b`.
The manifest records each curated input and generated file digest. Exact ZIP
content is deterministic; downloaded archives are checked file-by-file because
provider ZIP metadata may differ. Symlinks, duplicate files and extra content fail.

Medium/high offline comparison freezes identical guidance/scenarios and varies
only explicit effort. Correctness, tokens, cost and latency were **not measured**:
those require the parent's live scenario evaluation. No production effort default
was changed. Doubles establish payload/recovery behavior, not provider acceptance,
live skill loading, real research, scientific judgment or human acceptance.

## Remaining integration (parent)

The hosted startup follow-up packages the helper and curated guidance through
`.dockerignore` and the cloud Dockerfile. Startup validates the bound plan,
downloaded skill content and exact reviewers before configuring application
reviewer authority. Isolated lifecycle and installed-image fixtures now use
explicit synthetic pins. C3 must reconcile guidance and dangling repository-only links: SKILL.md references
`../local-api-demo.md`; hyprn-primitives.md references CONTEXT, OpenAPI and the local
API demo outside the bundle. Only the playbook links currently remap to real
bundled content. Guidance changes invalidate the recorded bundle digest.

Enforce reviewer identity/read effects/bounds in the application bridge, qualify
shared user spending and persist research inspection evidence. Successful search
is discovery; source-checked needs actual successful fetch evidence with provider
event identity, source URL, retrieval time, precise locator/excerpt and retained
content digest. Blocked/error tool results cannot establish source inspection.

Legacy sessions cannot acquire new skills/system/multiagent configuration through
the provider's tools-only session update. Parent must reconcile supported
continuation without discarding history or claiming an in-place skill upgrade.
Run integrated acceptance on the final C3/bridge/startup tree and perform live
provider attachment/research/reviewer/effort qualification before publication.

## Provider references checked 2026-10-22

- [Skills and native attachment](https://platform.claude.com/docs/en/managed-agents/skills)
- [Skill upload](https://platform.claude.com/docs/en/api/skills/create), [exact version reads](https://platform.claude.com/docs/en/api/beta/skills/versions/retrieve), [downloaded content](https://platform.claude.com/docs/en/api/beta/skills/versions/download)
- [Toolset configuration](https://platform.claude.com/docs/en/managed-agents/tools), [web restrictions](https://platform.claude.com/docs/en/managed-agents/tools-web-restrictions)
- [Predefined agents](https://platform.claude.com/docs/en/managed-agents/multiagent-orchestration), [thread routing](https://platform.claude.com/docs/en/managed-agents/session-threads)
- [Environment networking](https://platform.claude.com/docs/en/managed-agents/environments): an empty allowlist also blocks web tools; allowed hosts must include research sources.


## Hosted startup follow-up evidence

Command: `HYPRN_MVP_TEST_BUILD_CACHE_BYTES=17179869184 ./hyprn-mvp dev check hosted-lifecycle`
with the same configured development root/tool cache. Result: **25 passed,
0 failed, exit 0**, 17.38 seconds. Check identity
`70ece185-f688-4fc1-8b2c-1aa4781dad07`; scratch scope
`483c4468-f583-46e2-a2f1-7695df9e5f93`. The tested five-file delta is exactly
commit `39c09ba0`; only this checkpoint changes afterwards. Scoped Docker and
Postgres cleanup completed and the shared Docker slot was released to the native
qualification agent. No provider effects occurred.

The first lifecycle preflight exited 2 without running tests because retained
shared Docker build layers occupied 13,565,506,689 bytes, above the default 10 GiB
ceiling. Active/shared layers were preserved. The retry explicitly allowed 16 GiB
and was serialized after the native group's completion; no blanket prune or
shared-image deletion was used. `git diff --check` passed for the five owned files.

This gate covers live isolated database/container ownership and mocked provider
startup verification. It does not establish the rebuilt installed image: parent
must run its existing installed-artifact gate on final committed C3/runtime bytes.
`configure_reviewers` is called only after full successful startup reconciliation;
its enforcement remains in the parent's application runtime changes. No new
reviewer environment variables were introduced; pins and limits come from the
verified plan.
