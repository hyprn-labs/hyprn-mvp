# Analyses within Experiments — delivery checkpoint

Implementation: `a95527b`; fixture-only follow-ups `29372c6` and `9b4fa93` (2026-10-19). User approved the domain/UI update.
ADR-0012 records the current language and answer version rule.

## Outcome

- Experiments remains the model/version workspace, with Analyses, Configurations and Runs.
  Inventories are independent of the analysis selection; analyses reference reusable records.
- Canonical analysis API routes share the existing handlers/writer/authorization/receipts.
  Historical calculation_* schema fields and original routes remain compatible.
- Publication rejects different versions of one logical analysis or model across all answer
  citations. Drafts remain editable and historical saved answers are not rewritten.
- Agent tools and /hyprn distinguish a complementary analysis from a revision.
- Live demo has separate operating-point and sampled analyses. New answer
  `6520275a-8ea7-4513-a57a-8210df71ddb4`; comparison analysis version
  `b31bff3d-e4be-4e97-ac58-7ddf2b1599eb`; sampled version
  `20b9f8e8-b4be-4bb5-9a23-39604ff6924e` and estimate
  `41d5dce9-ff67-4a4f-b6d2-6728bfe32762` unchanged.
  All 36 configuration and 36 run identities preserved; no new numerical execution.

## Evidence

All groups use `./hyprn-mvp dev check <group>` via the development environment script.
Prior focused evidence applies to unchanged production areas:
- study-answer-api: 29 passed (22.53 s); mixed analysis/model pins, drafts, distinct analyses,
  alias idempotency and existing-run reuse. `/private/tmp/hyprn-analysis-answer.log`.
- contracts: 127 passed (8.53 s); `/private/tmp/hyprn-analysis-contracts.log`.
- combined-static --keep-scope: 9/9 (4.46 s), including production build/design checks;
  `/private/tmp/hyprn-analysis-static-final.log`. UI source unchanged since this build.
- study-answer-ui: 2 passed (19.76 s); `/private/tmp/hyprn-analysis-answer-browser.log`.
- local-api-client: 18 passed (9.08 s); `/private/tmp/hyprn-analysis-owner-final.log`.
- agent-tools: 326 passed on the committed guidance (53.18 s);
  `/private/tmp/hyprn-analysis-tools-committed.log`.

Failures during development: stale control-map title; old tool/projection expectations;
old cursor golden following tool rename; old canonical-route expectation; browser sidebar
label expecting Analyses rather than Experiments; removed run-id label; sampling fixture
relying on old 5/3 and Latin-hypercube defaults instead of explicitly setting them. Corrected each without weakening
production checks or numerical tolerances. Final browser and agent checks pass. A further stale estimate-sentence capitalization was
corrected in the browser assertion only.

Live browser: two analyses (3 and 33 configurations), global 36 configurations, paginated
runs, and two simultaneous slider changes produced estimated outputs/curves
(12.24766348560613 K and -2.4810004703830733 kW). Numerical basis unchanged.
Screenshot and public-API before/after records: `/private/tmp/hyprn-analysis-demo/`.
UI published from retained static scope `8d817f22-f1d4-4016-8d76-593481e4fecc`;
web process refreshed, dispatcher and attested scientific runtime unchanged.

## Final integrated browser acceptance

`./hyprn-mvp dev check calculations-ui` on `9b4fa93`: 4 passed, 0 failed,
0 skipped (26.72 s). `/private/tmp/hyprn-analysis-browser-delivery.log`. Actual
browser/controller/HTTP/API/auth/receipts/store, including creation, revision,
reference marks, 200% zoom, sampling and estimate assessment. Numerical transports
in this browser fixture are data-only stand-ins; the live preserved surrogate was
checked separately as described above. No production source changed after the static,
API and contract evidence; later changes were guidance, fixtures and this checkpoint.
Agent guidance passed 326 checks on its final committed content.

## Remaining scope

Human visual acceptance and broader release qualification remain separate. Internal historical
module/schema/key names deliberately retain compatibility spelling; no second writer/store.
Test scopes are released by the runner except the retained static build used for deployment.
Other session's roadmap and untracked proposals were not staged or modified.
