# Shared limit evidence and model presentation integration

Authorized by the user's Study details and model cleanup request. The UI batch builds on
`2c399e8`; model/filter/export implementation is `7b6236c`, with executor evidence in
[model-details-cleanup.md](model-details-cleanup.md). The backend result-format change is
an independent active batch; this checkpoint does not claim that work complete.

## Behavior

Read-only Study details renders an exact evidence version and relationship shared by
several limits once, with numbered limit references. Different versions or relationships
remain separate even when their display titles match. Draft controls remain per limit.
No saved approach, question, evidence, run or digest changes to achieve this presentation.

Model details uses Method context for the linked step's transformation and Why this method
for purpose and rationale. Exact step, approach and model identities remain in Method
record. Empty read-only assumptions are omitted. The Components box and its visibility
control are removed, together with the quantities Availability filter. Missing output
values and reasons remain visible. The two run export actions share one wrapping group.

## Development evidence

All checks use `./hyprn-mvp dev check <group>` with isolated fixtures. The static group
passes six commands (including design/token contracts, TypeScript and build); style passes
33 tests. The shared evidence regression exercises real public authoring, saved reads and
the browser; its fixture uses the existing private modeling double, not native execution.

Recorded corrections, with external logs retained:

- Initial static passed, then style could not import its fixture because the development
  data-root environment was absent. Retried with the existing development environment.
- Style identified two changed long lines; both were wrapped, then 33 tests passed.
- One invocation used an unregistered group name and allocated no scope. The registered
  group is `approach-ui-assumptions`.
- Two assumption-group runs passed 18/19. The new regression supplied a method-evidence
  locator to a limit citation, whose API deliberately accepts only version and relationship.
  Corrected the fixture to use supported fields and an independently versioned record.
  No contract or scientific guard was relaxed.

External evidence bundles have prefix `hyprn-orchestration-verification-` and suffixes
`req12ml5`, `ltwkftlb`, `vjqlqa85`, `7q0zm5nf`, `hqx0h_zs`, `5pcforo_`. Completed scopes
from those bundles are archived and released. The live demo scope remains retained.

## Remaining verification

Integrated browser acceptance and live demo inspection are recorded below. The exact
historical API/result cleanup and its producer rebuild/re-attestation have separate
ownership and remain active. Automated browser checks do not establish human acceptance or release
qualification; the reference-image set remains unavailable.

Further development corrections: the citation-title assertion initially counted the
matching title inside closed evidence dialogs; it now counts visible rows. The next run
passed the new regression but timed out in an existing model-condition preview wait.
The integrated serialized rerun passes all 19 assumption tests. A separate diagnostics
formatting attempt expanded unrelated JSX and failed a source-wiring assertion; restoring
untouched markup and formatting only the changed element restored all six static checks
and 33 style tests. External bundles: `agdz9v4v`, `xn9adyen`, `qqtutb9r`, `vptj1zbd`.
Those completed scopes are archived/released. Naming 9, hygiene 5, guard 116 and
units-guards 138 pass in `md4g1qrz`; all five scopes are released.

## Observed demo behavior

UI source `0cf9dba` includes implementation `7c57a6a` and editable-empty-state fix
`3ee243c`. Rebuilding only the owned static UI preserved the runtime bytes and all
49 attested source hashes. Actual browser inspection confirms one visible Explicit
screening assumptions row for limits 1, 2 and 4, direct evidence access, unaltered full
question, clean saved-model method paragraphs, no Availability filter or Components box,
and adjacent run export buttons with an 8px token gap. The ten existing run histories
compare equal through the public API to their retained pre-change snapshots.

External demo evidence is in the retained scope's `evidence/model-limits-cleanup` folder:
`runtime-preservation.json`, `ui-build.log` and `run-preservation.json`. Browser captures
are retained outside the repository. This is automated observation, not human acceptance.

## Integrated UI acceptance

Committed batch `7c57a6a`, followed by `3ee243c` (editable empty-state copy); `0cf9dba`
adds only the executor checkpoint. The serialized union `iy_p2js_` passes static 6
commands, style 33, approach-ui-assumptions 19, approach-ui-method 14,
approach-ui-reading 16, foundry-nav 8, ui-reading 15, ae-ui-configuration 14 and ui-c 11.
The final empty-state delta passes combined-static 6, style 33, guard 116,
units-guards 138 and ae-ui-model 6 on `0cf9dba` in `onsog3u1`. All counts have zero
failures/skips. Together these cover 103 browser tests. The later delta changes only
editable empty-state copy and its three assertions; unaffected prior checks remain valid.
The live draft now shows Assumptions and Add assumption without the empty sentence.

All nine `iy_p2js_` and five `onsog3u1` scopes are archived/released. Counts-only terminology scan has zero
findings. The UI delivery is verified; backend integration, native producer rebuild,
worker re-attestation and new-format demo execution remain active and are not claimed
complete here. Reference-image qualification and human acceptance remain separate.
