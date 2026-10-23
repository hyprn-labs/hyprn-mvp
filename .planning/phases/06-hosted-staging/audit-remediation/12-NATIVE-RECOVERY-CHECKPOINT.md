# Explicit native reconciliation checkpoint — 2026-10-23

Product commit: `c993837a` (`Reconcile explicitly resumed analyses through native absence proof`).
Owner: creation_coherence. Parent authorized this additional narrow recovery after the completed
study-creation work. No staging data, provider conversation or live deployment was changed.

## Result

The existing public `resume_analysis` command can request reconciliation for an intact,
linked uncertain run under the original continuous authority. It records an immutable intent;
the API does not supply proof or reset execution. Aggregate progress becomes calculating/waiting.
The dispatcher holds its existing application lock and serialized exclusive native owner lane.
AiiDA checks related request identities, collisions and partial processes in its pinned store.
An empty exact-match query alone is insufficient. All affected runs require proof of no start
before any original prepared run is released. Numerical runtime pins, request, command, source,
bundle and run identity remain unchanged. Failure consumes the intent and retains uncertainty
with an actionable diagnostic; polls and command replay never authorize another attempt.

Migration 0016 adds immutable intent/results records. Proof publication and release are one
transaction through `hyprn_reconcile_native`, executable only by the dispatcher background
credential. Web and Assistant credentials cannot forge proof or release an uncertain run.
Existing authorization-recovery tables/policies are unchanged. The new audit applies only to
this explicit uncertainty path. Existing native adoption remains unchanged.

The pinned AiiDA process implementation sets process type and stores its process and input
nodes before the owned runner calls continuation. Real isolated AiiDA tests cover absence,
orphan request records, mismatched identities and partial processes. Application HTTP and
PostgreSQL tests cover replay, zero automatic retry, preserved bytes and the role boundary.
Native transport and agent tool descriptions/playbook were updated; the deployed managed agent
must be refreshed to receive those behavioral bytes. No public response shape changed.

## Verification

Every group used `./hyprn-mvp dev check GROUP` with the established development data/tool roots.
Final invocations also set
`HYPRN_MVP_STAGING_STORAGE_CONFIG=/private/tmp/hyprn-new-study-diagnosis/no-retention-policy.json`
(the intentionally absent test setting avoids unrelated local-retention preflight scans).

| Group | Result | Evidence/log |
|---|---|---|
| calculations-api, committed tree | 103 passed, exit 0, 85.41 s | `/private/tmp/hyprn-native-recovery-api-final.log` |
| hosted-postgres, committed tree | 58 passed, exit 0, 81.47 s | `/private/tmp/hyprn-native-recovery-postgres-final.log` |
| bridge-history | 165 passed, exit 0, 78.35 s | `/private/tmp/hyprn-native-recovery-bridge-3.log` |
| agent-tools | 331 passed, exit 0, 58.46 s | `/private/tmp/hyprn-native-recovery-agent.log` |
| bindings, committed tree | 62 passed, 12 failed, exit 1, 34.53 s | `/private/tmp/hyprn-native-recovery-bindings-final.log` |
| bindings, isolated pre-change `100a88fe` | Same 62 passed and 12 failed, exit 1 | `/private/tmp/hyprn-native-recovery-bindings-baseline.log` |

Bridge/agent behavioral source bytes passed before commit; later deltas were queued analysis
projection/PG function integration, extra API/PG assertions, formatting and explanatory docs.
Their affected API/PG groups were repeated on the committed tree. Generated playbook freshness
and `git diff --check` passed.

The 12 baseline failures are in `test_result_bindings.py`: bundle11 variants one/two/fanout/multi;
preclaim variants missing/changed/revoked/source_race/uncertain; concurrent save/dispatch;
static preparation private snapshot; prepared-resume sources. They fail retained conversion
interpretation or old preparation-state expectations before launch. The selected existing
`test_submission.py` fault-window/no-redispatch checks pass in both runs. No unrelated fixture
or production conversion logic was changed. Full bindings qualification remains failing.

Development failures retained in earlier logs: initial new API tests compared dynamic request
IDs (100 passed/3 failed); new PG fixture nested actor scopes (57/1); then native-proof publication
correctly refused the ordinary request credential (57/1), resolved with the restricted dispatcher
function; new native fixtures initially omitted explicit runtime root, then fixture user and UUID
normalization (161/4 each). These were fixture/integration corrections, not weakened invariants.
The first baseline snapshot extraction used an unsupported system-Python tar filter; extraction
was retried after checking all archived members are relative, traversal-free and not links.

Final check storage sessions (all scoped runtime paths confirmed absent/released):
`7c465922-48ce-43a1-81e5-3d8171165619`, `cefc9582-cfda-4940-84ff-43eac4e6f66a`,
`77273f12-61af-480a-87e5-79e74cf7163e`, `3e74130d-1e3c-494a-aad4-de246f386854`,
`4ca903f1-d34a-47af-90ad-b1cccd2a7c08`, `a5fc131a-6cb6-4f99-9cc6-ced7da558908`.
The isolated git-archive baseline snapshot was removed after its runner exited. Logs and
runner evidence remain outside the repository. No active checks remain from this worker.

## Remaining integration

Parent owns deployment migration ledger 16, native attestation/release assembly, managed-agent
refresh, lifecycle/drain changes and the analysis progress UI. Original numerical image/policy
bytes must remain compatible with the prepared runtime; a changed numerical runtime refuses
recovery. Native absence proof is deliberately conservative: retained collisions/orphan or
partial processes remain uncertain and need inspection. This is not a general retry API.
Local checks do not establish live staging recovery or human acceptance. The user will ask
the Assistant to resume after deployment; no message was sent on the user's behalf.
