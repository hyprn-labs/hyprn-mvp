# 06-03B — Managed assistant definitions and safe setup

Status: code complete; offline approval artifact prepared. Live provisioning and hosted
assistant acceptance are not performed or authorized by this checkpoint.

## Delivered revision

- `6d492a2`: failing offline command acceptance and group registration.
- `1e0c10a`: implementation, 16 command-boundary checks and installation instructions.
- Owned files: `deployment/managed_assistant.py`, `deployment/tests/test_managed_assistant.py`,
  the `hosted-assistant-setup` entries in `deployment/checks.py`, and
  `docs/agents/embedded-assistant.md`.
- No application conversation/store/budget code, platform code, dependency or scientific
  runtime was changed. No provider resources, sessions or budgets were touched.

## Evidence

Command: `source` the private development environment, then
`./hyprn-mvp dev check hosted-assistant-setup`.

| Run | Result | Meaning |
| --- | --- | --- |
| Initial sandbox run | exit 5 before collection | Pinned tool cache was outside writable roots; rerun with authorized tool-cache access. |
| Initial pytest RED | 0 pass, 1 expected assertion failure | Offline plan returned 2 instead of 0. |
| Registered unittest RED | 0 pass, 1 expected assertion failure | Same command assertion; machine classifier returned `RED_EVIDENCE_OK`. |
| First GREEN | 15 pass, 0 fail, 0 skip | Full fake-provider command journey. |
| Private-directory/final-readback change | 16 pass, 0 fail, 0 skip | Additional path isolation and explicit retry after definite rejection. |
| Live-fence/format change | 16 pass, 0 fail, 0 skip | Same journey under repository live-store fence. |
| Final package-request correction | 16 pass, 0 fail, 0 skip | 3.988 seconds tests; 4.316 seconds scoped command; exit 0. Matches implementation `1e0c10a`. |

The RED target was
`test_managed_assistant.SetupTests.test_offline_plan_is_release_bound_and_has_no_remote_effects`.
It executed and failed on its planned success assertion, not a fixture/import fault.
The original raw output and classifier record were kept outside Git after the commit
hook rejected machine-specific paths in the raw record. The retry committed only portable
artifacts; no hook was bypassed.

Final runner session identity: `9a4049d5-a109-49bf-a9a7-a36bc09fa2fc`.
Final scratch identity: `76db9826-b55b-4c14-9f8d-f9ba2ad8f4cb`.
The scope was released; the runner retained `tests.json`, `result.json`, stdout and stderr
in its normal external evidence store. Temporary fake credentials/state were cleaned by
the test fixture. No containers or ports were allocated. The review artifact is retained
separately for approval.

The actual `python -m deployment.managed_assistant plan` process also exited 0 with the
locked interpreter and no credential argument. Artifact: `assistant-plan.json`, private
review directory identity `hyprn-managed-review-0cjmg8mb`.

| Identity | SHA-256 |
| --- | --- |
| Review file bytes | `7109481a5d42c8bbd143bec320c1246a70aebc12fa9c5d0069e523a2d4bb1f85` |
| Configuration | `2da94a9c7bd47c242d48395e0f9a9ad9e2d0b814d526e1bad9e55128fc65e735` |
| 56 offered definitions | `9edfb46ae939e9cfcbb3a46c415d3495eb86ac182b444cf8cf1a965faa735f5e` |
| Packaged playbook | `d646cee70a700d1e26f42e51d52c8d28574b32bb0d831473e262e127a1d9ae3f` |

`git diff --check` passed. The pinned formatter was applied only to owned Python files.
No stubs were found in modified implementation/tests/documentation.

## Integration handoff

The orchestrator must rerun `./hyprn-mvp dev check hosted-assistant-setup` on the committed
integrated tree before treating this task as accepted. The orchestrator owns global
STATE/ROADMAP reconciliation; this independent task does not rewrite their concurrent edits.

The binding output supplies `HYPRN_MVP_ASSISTANT_` plus `AGENT_ID`, `AGENT_VERSION`,
`ENVIRONMENT_ID`, `DEFINITIONS_SHA256`, `CONFIGURATION_SHA256`. Version is a positive integer
encoded as an environment string. The configuration hash is platform evidence; only the
definitions digest is currently consumed by application Settings. Provider credential
delivery remains a separate private `KEY_FILE` reference.

Runtime allowance fields and persisted usage must carry forward the approved EUR 100,
reviewed USD conversion and current prior usage. This command never supplies, resets or
allocates an allowance. Preserve existing study sessions. It only adds content-addressed
agent/environment resources after the reviewed hash is explicitly applied.

## Remaining limits and owners

- Deployment operator: approve the exact plan before any live apply. Reconcile using the
  same durable private journal; no deletion/archive/reset command exists.
- Platform owner: render the binding fields and secret-file reference, preserving explicit
  allowance configuration and authoring/conversation stores.
- Live acceptance owner: verify account/model access, actual create/readback shapes and
  provider restrictions with approved resources, then the hosted user journey. Fake transport
  evidence proves command behavior, not those external facts.
- Environments are mutable and unversioned. Reconcile before activation; this setup command
  is not continuous drift monitoring. All operators must share its journal for serialization.
- Changed releases create a distinct agent. Existing resources without matching metadata
  are never silently adopted. Existing sessions retain their own immutable delegation policy.
- Full qualification and human acceptance remain separate phase gates.
