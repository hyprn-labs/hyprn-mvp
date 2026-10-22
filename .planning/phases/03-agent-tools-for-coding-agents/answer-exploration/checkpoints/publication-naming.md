# Publication naming correction — 2026-10-16

Owner authorized replacement of the retired product name with HYPRN in prose and hyprn in file names/identifiers, including unpublished history required by the existing pre-push hook. Current working-source corrections update the scientific skill and its primitive-reference links, the earlier guidance checkpoint, and the project cache marker/test. No source equations or scientific records changed.

Validation: `./hyprn-mvp dev check check-storage` — 31 passed (4.41 s), isolated scratch scope released. Skill relative links resolve; `git diff --check` passes. No new dependencies. Concurrent design/model-flow/ROADMAP/research changes remain untouched.

Publication is prepared in a separate scratch Git checkout, preserving original local history and existing remote main. The exact corrected committed tree is compared with the rewritten publication tip before pushing. The unchanged pre-push hook remains active, scanning history, paths and blobs; no force push or hook bypass is authorized or used. Final publication identity and outcome are reported after the push, not claimed by this preparatory checkpoint.
