# Execution presentation and domain alignment

Request: remove irrelevant no-result/criteria placeholders, harmonize Runs with the other
collections, and put useful execution facts above run outputs using the design system.

## Scope and meaning

ADR-0010 already makes configuration 6/results 3 criterion-free. No API, schema, stored record,
worker or sampling change is required. Current configuration readers/editors omit the empty
Criteria section; run headlines show no study criteria. Historical stored definitions, where
still readable, remain labelled rather than silently replaced by current brief criteria.

The Runs collection uses ResourceCard/CollectionToolbar like calculations/configurations.
The Execution panel uses shared MetricGrid: recorded status, saved numerical operation,
measured launcher wall duration and time limit when present. Missing times are omitted, not
zero. Failure messages stay visible. Execution details holds logs/source mapping/file access;
results are the output table. No solver convergence or optimization success is inferred.

Design-system guidance captures future OpenMDAO solver/driver metrics and their distinct
meaning; no placeholder or fabricated instrumentation is added. Official OpenMDAO references
are linked in design-system/components/Calculations.md. Existing numerical behavior is unchanged.

The no-result legend is conditional on displayed unavailable values. Failures and outside-range
predictions remain explicit, and loading remains Updating. Real sliders/surrogates are unchanged.

## Checks to date

All checks through `./hyprn-mvp dev check`, configured host environment, isolated scopes.
- combined-static: initial failures in stale source guards requiring the old RunOutcomes and
  Run files heading. Guards updated to require shared execution status, MetricGrid and collection
  cards. Third run passes all 9 stages, including design/ownership/contract checks and UI build.
  Log: `/private/tmp/run-execution-static-3.log`; scope `064718cc-ec6f-4dc2-96f3-ac1e708bfbd7`.
- foundry-nav: first run 5 pass/6 fail. Five failures were omitted model-explanation fixture
  reads; one still expected the retired Open modeling approach. Updated fixtures to current
  domain endpoints and the zoom journey to Edit brief. New execution/duration/narrow layout
  assertions passed in the first run. Second run: 6 pass/5 fail, all the same omitted pinned
  model-version explanation GET (the model-level explanation route was insufficient).
  Fixture corrected in `6e0e7d4`; final committed run passes 11/11, zero skips/flakes,
  34.419 s. Log `/private/tmp/run-execution-browser-3.log`; evidence session
  `da205658-d517-4d35-afae-f050e51b43d5`, scope `c2b27020-4efc-46be-956c-bd6d33e0d8c1`.
- Exact delivery `6e0e7d4` (production `4e8ccad`): combined-static passes 9/9 stages,
  10.101 s. Log `/private/tmp/run-execution-delivery.log`; retained build scope
  `ae7c48ed-aa35-456c-8102-0a5d233094c8`. Browser scopes release automatically; retained
  static scopes are build/evidence only. Other edited browser selectors are migrated but their
  separate suites were not repeated; no full qualification claim.

## Live readback

Guarded asset publication to the existing localhost:54821 demo passed unchanged-runtime and
unchanged-live-index checks. Delivery manifest and previous index are in
`/private/tmp/hyprn-final-exploration/ui-delivery`. No process restart or scientific-data mutation.

Real UI readback on study `1174be5a-8527-4a51-83d9-aad3c8e4aeaa`:
- Answer legend shows calculated and estimated only for the available displayed results.
- Run history uses shared collection cards and filters, with bounded 20-item page/load more.
- Run `499272c6-b9c4-479c-9e70-762788f290b8` shows Completed, Model evaluation, 3.038 s
  recorded wall duration and 300 s time limit; outputs 11.831 K and -2.091 kW remain visible.
- Execution details opens retained file groups and expandable raw diagnostics/source mapping.
- Run Configuration tab shows Inputs and provenance with no criteria section.
- Screenshot: `/private/tmp/hyprn-execution-presentation/run.png` (728px viewport).

Numerical/worker/backend sources and records are unchanged; their earlier sampling and
surrogate evidence remains applicable. Future coupled/optimization telemetry is a documented
presentation contract, not an implemented solver capability. No full release qualification or
human acceptance claimed. Next: human demo review.
Unrelated ROADMAP and research/proposal changes are excluded and preserved.
