# Progress, calculation latency and Help — 2026-10-23

Implementation: Help `6e0b7a14`, progress `af1a30d6`, validation CPU `70bb9631`,
verified-result consumers `48d240c5`. Worker checkpoints in this directory retain
exact scope, commands and isolated-vs-live limitations.

## Observed cause and correction

Twenty new hypersonic model executions used 71.5133 seconds total (median3.5474,
max3.9344), while their analysis took about17minutes. Native calculation time was
not the main delay. Preparation and repeated full retained-bundle validation sat
in the serial dispatcher path. Analysis completion and estimate construction now
reuse the existing persisted verified projection. Its compact runtime identity
keeps mixed-runtime refusal intact; exact source/receipt witnesses, current study
access and reader-code identity are rechecked. Cold or damaged caches still undergo
full archive admission. No numerical method, tolerance, validation partition,
execution containment, immutable record or budget rule changed.

Schema version unions skip only provably incompatible branches. Local replay of
actual retained bytes reduced cold bundle validation median0.4247→0.2782seconds.
Read-only deployed baseline without profiler: full retained read1.761seconds cold,
0.611/0.587seconds warm. These are component timings, not an end-to-end speedup claim.

## Checks

Through the pinned `./hyprn-mvp dev check` entry point:

- hosted-postgres:57passed,68.95s. New public analysis regression first failed at
  the unnecessary archive read, then passed with exact cached result after owner
  restart. Source tampering, foreign access, damaged caches and code invalidation
  remain covered. Earlier run55passed/2failed because the bounded fixture filled
  its256MiB tmpfs; fixture now512MiB with1GiB memory. No live storage was touched.
- calculations-api:100passed,79.04s. Initial99passed/1failed because an existing
  lifecycle double mocked the old full-record seam; updated only that double.
  Added estimate-projection and mixed-runtime rejection tests.
- api-a:125passed,90.23s.
- contracts:127passed,12.33s.
- locality-contracts:174passed,13.06s (validation owner).
- assistant-bridge211, agent-tools331, integrated ui-navigation45 passed; see
  progress and Help checkpoints. Typecheck/design/tokens/ownership/UI contract and
  smoke120 renders passed. No relevant UI delta after these checks.

All scoped test runners released their scopes. Existing warning output retained
in private logs under the task's performance evidence directory. No staging data
repair or direct study mutation. Full qualification and human acceptance are not
claimed. Remaining: frozen build, provider-definition provisioning, normal backup/
activation/attestation, public Help/progress proof and staging after measurements.

## Staging delivery and measured verification

Remote staging source `efcdb75f3e11f448e78262d322f9db9265bd8596` is the exact
implementation tree, with the prior staging source as parent. Sequence26 release
`adb68e331e89cd42882db6a67f147f372b7aeca37f8ec1cfac0762d0fe94743e`, configuration
`4310b33645b7f6ce011335c85034ebb50a9dbd174a870c632db41f86cab73190`.
Platform `492eeb2d` and schema15 unchanged. Provider skill, reviewers and main-agent
definitions were provisioned with the updated tool/playbook instructions.

Fresh application/native build and extraction verification passed. Unchanged
numerical build inputs were proven equal, so the existing worker/modeling image
bytes were retained to preserve saved surrogate runtime identities. Host contracts
changed and therefore fresh containment was required and passed. Numerical-image
continuity proof is in the private build packet; unused rebuilt images are not deployed.

Normal quiet admission close, coherent database/file backup, installation, owner
schema check15→15, containment/startup and19 network probes passed. SSH disconnected
before returning installation output; the exact durable completion, installed
identity and startup receipts were reconciled read-only. No installation or backup
was repeated. The protected backup wrote approximately4GB. No study-data repair,
secret reissue, numerical rerun or budget reset was performed.

Public signed-in Chrome verified Help, its workflow navigation and Assistant recovery
guidance. Existing answer loaded after cold verification. All four independent
sliders moved together; real estimates changed to150899.9807227989kg and
591.9874323746903USD/pax. Exact hashes of138 configurations,138 run associations,
five analysis versions, one brief, one answer and seven evidence records stayed
unchanged through deployment and slider verification.

Live alternating reads on the same run (five each, same canonical numerical-result
hash): full archive median1.160638s; verified projection median0.371487s (3.12×).
Initial projection after changed code took2.174159s: full cold admission is retained.
An earlier timing-only equality assertion used noncanonical JSON and falsely
compared integral floats with integers; canonical comparison passed. This measures
the changed consumer path, not a new end-to-end20-point analysis or whole-study speedup.

The optional additional Assistant20-point progress benchmark was not submitted:
Chrome's Cloudflare session expired before the composer was usable. The public
login page confirms reauthentication is needed; server admission renewal is healthy.
User asked to sign in. Progress behavior is covered by the211 assistant,331 agent
and45 navigation checks, but a new live in-progress card remains to be observed.
Full qualification and human acceptance remain unclaimed. Private evidence:
`hyprn-progress-help-release`, `hyprn-progress-help-deploy/packet-2`,
`hyprn-analysis-performance` under the task's temporary evidence root.

Ongoing named-user staging access promotion succeeded (`mode: staging`); the
existing two-user access policy and cumulative USD20/user budget remain unchanged.
