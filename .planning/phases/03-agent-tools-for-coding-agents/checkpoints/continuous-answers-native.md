# Native scientific answer journey — test integration checkpoint

Status: test extension committed; actual native verification remains assigned to the
orchestrator. This checkpoint does not claim that the new native assertions have passed.

## Source and scope

- Base: `7c4291fd579c1d6ebad3c189aeb83f7d6d4748bb`.
- Test commit: `1b3b2ef6212887946755ec329402da0dd7e83a8e`.
- Sole code file: `deployment/tests/test_units_native.py`.
- File SHA-256: `1c87b3d5d14c9af70c68d3b75a098ef20d8feb1b4013734706b9134a8d2b9187`.

The existing seven-run compound-conversion test now saves a modeling approach after
native records exist. The method refers to their exact model versions; its comparison
case names an exact model binding and existing evidence. Ordinary study HTTP commands
save a case answer using the first pair of exact configurations/runs/evidence, then
study synthesis using all seven records and the exact first case-answer version.

A later case-answer version adds a qualification without changing the saved synthesis
basis. After the existing modeling outage and web restart, assertions read all three
answer versions exactly, read the two explicit heads, and recover the original case
answer through its command receipt. Existing history/configuration/raw-payload checks
still follow. Process-count assertions remain seven before and after authoring/restart.

The existing final native proof gains `scientific_answers`, including the exact approach
version, original/revised case answers, study synthesis and restart assertion marker.
Scientific wording is explicitly confined to the synthetic analytical fixture and
does not claim engineering validity or feasibility.

No production owner, fixture manager, API contract, UI, execution input, runtime pin,
or shared planning state was modified. No additional process, container, browser,
native execution or live-study write was performed by this executor.

## Checks

- `./hyprn-mvp dev check style-ratchet`: initial 32 passed, 1 failed. Three added
  lines exceeded the limit; shortened two rationales and wrapped one assertion.
- Same command after correction: 33 passed, 0 failed, 0 skipped, exit 0.
- `git diff --check`: exit 0.
- Authored case shape was inspected against `ApproachCase1`; the existing
  `save_approach`, `step`, `request`, `offline` and `restart_web` helpers were
  read before constructing commands. This is implementation review, not runtime evidence.

Evidence scopes: initial `e64ac935-b58a-4d25-98b5-aa61af187dfc`; passing
`66854ca5-a4a9-4df3-9a10-a59ec0613d66`. Both task-owned scopes' temporary stores,
homes, native and aiida folders were released; evidence remains outside the repository.

## Required next action

The orchestrator integrates the test commit and runs
`./hyprn-mvp dev check units-native` in its serialized native lane. Until that
command passes, native answer creation/revision/restart assertions are unverified.
No separate scientific process or parallel native run is required.

## Self-check: PASSED

The test file exists, its checksum matches the committed source, and the test commit
is reachable. Only the owned test file changed in that commit. Human acceptance and
phase completion are not claimed.
