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
