# Owner-operated fuel demo rehearsal

Date: 2026-10-14. Status: the local public-API author–run–inspect–revise journey is demonstrated. The scientific result is a qualified cruise screening comparison; complete-mission feasibility and ticket pricing remain unresolved. No phase or release qualification is claimed.

The subsequent Study details follow-up is recorded below. The original rehearsal
identities and numerical evidence remain unchanged.

## Delivery and exact source

Integrated `30f91a8` and `c6c0078aa2abda91021b3107e1ce7124eb7ac792`: the thin ordinary-session client, focused tests, runner/guard registration and usage guide. No dependency, API, UI or attested runtime file changed. Runtime application source is `6c4d2ae`; its application bytes are identical on the delivery commit. All 49 reviewed attested paths still match the final 2.8 inventory; the active runtime descriptor is unchanged.

One ordinary owner login served study creation and every subsequent scientific API operation. All authoring, previews, saves, submissions and retained reads used `/api/1`. Candidate Python ran only in the actual restricted worker through the existing dispatcher; no prebuilt model, generated scientific result or host-side candidate execution was used. The existing scoped startup created one empty bootstrap study, separate from the authored fuel study.

Study: `50e423fd-a709-4e21-9381-0b09022b4115` (Hypersonic fuel comparison). Model versions: `9f1d7d5f-b4cc-418c-83a2-a16895bc7836` and `420b8ed0-dbc6-465b-968b-3e1ca7dc0df6`. Three connected components cover aerodynamics/propulsion, cruise fuel and mass/cost screening. Version 2 exposes wetted area and engine mass; instances explicitly rebind to the new definition. Two saved approaches pin exact model versions. Ten configurations were saved and every one was run.

The conclusion is an immutable evidence-family revision, version `bf6e89d4-0363-49a1-a7dc-24dbec52c3ab`; its preceding reference interpretation remains readable. A second assumptions-evidence version clarifies baseline versus revised cases, the structural-unit hypothesis, payload-volume interpretation and numerical currency representation.

## Real execution and scientific evidence

| Case | Run | Available outputs | Mass criterion |
|---|---|---:|---|
| Hydrogen reference with g per square metre interpretation | `d1236902-3d01-4de4-b55e-091a970ccfe4` | 9 | violated |
| Hydrogen reference with literal kg per square metre interpretation | `3e1a007f-c9d0-40b3-bb7d-e791ac4f6e28` | 9 | violated |
| Kerosene at the mass ceiling | `5fbbc5b0-aa05-4b05-ba92-2c18cd389a48` | 9 | met |
| Methane at the mass ceiling | `abe944cc-ee8e-41af-87c0-62ea0966b1f2` | 9 | met |
| Hydrogen at the mass ceiling | `6f4fd358-3f01-4fdc-8a2c-278446589514` | 9 | met |
| Kerosene revised 402 tonne candidate | `a58df5d1-bf65-49e7-9f3e-a598be926583` | 11 | met |
| Methane revised 340 tonne candidate | `24a2bdad-ce0a-4aa4-a943-eeb7a911ea7a` | 11 | met |
| Hydrogen revised 170 tonne candidate | `bed801a2-66ac-45af-978b-6fb038e4ee5b` | 11 | met |
| Hydrogen short-range Mach 4 screen | `21e1a359-d38c-4f0e-b90a-e697d8c60596` | 11 | met |
| Hydrogen long-range Mach 8 screen | `bdfde1f2-a34a-4826-af7a-4ebeee9886cd` | 11 | met |

All ten executions finished with exit code 0; all expected outputs are available, with no failed or unavailable outputs. Convergence/optimization are not applicable to this explicit model, and applicability remains unassessed. The two violated reference mass criteria remain violated; successful execution does not change them.

At the shared Mach 6, tau 0.18, 575 tonne, 9000 km baseline, calculated cruise fuel is 354.747 / 323.677 / 167.877 tonnes for kerosene / methane / hydrogen. Fuel expense is 2601.48 / 5437.77 / 7834.26 USD2021 per occupied seat. Hydrogen uses less fuel mass; kerosene has the lowest fuel expense under these historical prices.

The revised Mach 7.2 candidates use graph-informed mass/tau pairs 402 t/0.09, 340 t/0.14 and 170 t/0.28; calculated cruise mass margins are 7.382 / 6.699 / 2.457 tonnes. These are declared inputs, not independently found optima. Their fuel expense is 1725.48 / 3126.18 / 2381.48 USD2021 per occupied seat. Mass and geometry vary together, so these are not controlled fuel-only comparisons. No complete-mission or ticket-price claim follows.

The 380 tonne, Mach 7.2, tau 0.2, 18000 km hydrogen reference requires 380.626 tonnes under the inferred g/m² structural reading. Its 0.626 tonne deficit is 0.165 percent of the candidate mass, but still violates the criterion. The literal kg/m² interpretation requires 72717.769 tonnes. The source unit remains unresolved; near agreement with a plot supports a conditional interpretation, not validation. The two hydrogen range-endpoint scenarios do not establish coverage of the whole envelope.

Source: Andro et al. (2022), HiSST-2022-352, pp.3–11, plus the cited standard-atmosphere source. Independent read-only formula review found no consequential transcription error for the declared Mach 4–8 cases. The study retains limitations: no ascent/descent, reserves, cryogenic tank engineering or optimization; incomplete insurance/regression-unit cost assumptions; currency dimensions represented in labels rather than dimensionally checked metadata.

## Verification, failures and retention

On committed `c6c0078`:

- `./hyprn-mvp dev check local-api-client`: 7 passed, 0 failed/errors/skips (4.5 s including wrapper).
- `./hyprn-mvp dev check guard`: 116 passed, 0 failed/errors/skips (4.1 s).
- `./hyprn-mvp dev check style-ratchet`: 33 passed, 0 failed/errors/skips (9.0 s).
- `python3 -B deployment/tools/term_scan.py`: total 0.

The orchestrator inspected the actual served UI: all ten runs, computed values, the frozen first-version component graph and the revised hydrogen result. Two earlier full run histories compared equal after the model/approach/conclusion revisions; the earlier conclusion version also remained unchanged. This is automated UI evidence, not human acceptance. The final documentation delta changes no behavior and does not invalidate the recorded checks.

Observed failures: an initial client launch in a different tool environment could not log in; the same helper succeeded in the authorized local execution environment. One approach preview rejected a missing required assumption role (400, unchanged); supplying `overall_method` succeeded. A run-scoped evidence note returned 404 unchanged because frozen-model label resolution expects a synthetic root instance that the production model does not contain. The conclusion was saved at study scope with exact run references; fix the narrow label-resolution issue later, without substituting current content. No uncertain launch was retried. Two browser locator attempts failed due to accessibility-role/state differences; current DOM inspection resolved them without product changes.

All three helper executor scopes and all three integrated verification scopes were released. The live demo scope `f7145c6a-9848-4541-8aa4-0acf069102fb`, services, authoring records and native run data are intentionally retained. Do not run fixture cleanup on that scope. Foreign resources were untouched. External evidence is indexed by `hyprn-fuel-demo/manifest.json`, API transcript, UI screenshots/DOM captures and the existing helper verification logs. The manifest records exact configuration/model/result identities; no credentials are in those evidence files.

## Deferred work and stopping point

Stop adding features after this rehearsal. Preserve the ordinary authenticated demo and its records. Productized installation/lifecycle, other hosts and clients, embedded assistance, broader agent surfaces, full qualification and release audits are separate future scope. Full scientific mission and cost closure require additional source resolution/modeling work; do not present this screening study as a validated aircraft design.

The earlier optional batches remain unmerged and recoverable: `agent-local-foundation` at `d353c796b2f8948c8594b3d9d8f5179fa0fd4304` and `agent-mcp-surface` at `63b617c`. Their checkpoints retain partial checks and remaining findings; the MCP/notes branch still has its recorded style failure. No original numbered task closes merely because the demo works.

## Study details and scientific guidance follow-up

The product owner subsequently requested the Study details cleanup and the start
of scientific engineering guidance for the workflow agent. UI implementation
`15e5ae7` separates the question, current approach, assumptions, limits and open
questions. Empty optional sections and internal format labels are hidden. Evidence
versions and relationships remain accessible through View evidence; conflicting
evidence remains visible in the brief. The
[UI checkpoint](phases/02-local-edition/checkpoints/study-details-brief.md) records
all nine passing integrated groups, 58 passing browser tests, corrected assertions
and formatter changes. All nine integrated test scopes are released.

The same owner-authorized public API session saved approach version 3,
`573e9290-5abb-4553-bd6b-4909ffe6f3fc`, and study revision
`163dc5a3-5bf8-43d3-a320-8a9c8153bfa0`. The question restates the surviving full
engineering brief: three fuels, 100 passengers, 3000–15000 km with emphasis on
9000 km, Mach 4–8, below 575 tonnes, aircraft mass and ticket price. No verbatim
human original was available, so original-wording and attribution fields were not
invented. The current method describes the actual cruise calculation and cases.
Four separately cited limits retain mission, scenario coverage, source-unit and
cost restrictions. The structural-unit interpretation is explicitly provisional.

The preceding approach content and all ten complete run histories and result
integrity records compare unchanged. No model, configuration, numerical input or
result changed. All 49 attested source paths and the running descriptor still match
the retained attestation. Numerical reruns are unnecessary for this presentation
and authored-context correction.

The production UI build from integrated `7b590ab` was applied to the existing
owned static directory without restarting the runtime. The real UI shows the new
saved brief, omitted empty fields, distinct limits and the exact cited source
version. Screenshots and DOM capture are retained with before/after API responses
and historical comparisons in the live scope's `evidence/study-details-brief`,
indexed by `file-identities.json`. Browser sign-in was renewed after page reload.
This is automated inspection, not human acceptance.

Scientific guidance commit `fcc715e` adds
[the foundation skill](../docs/agents/scientific-engineering/SKILL.md) and seven
behavioral scenarios. Static review establishes intended coverage only. The
foundation is not installed or loaded by the workflow agent; future integration
must reconcile it with the single packaged playbook and evaluate actual agent
responses. No API or runtime instruction source changed. See the
[foundation checkpoint](phases/03-agent-tools-for-coding-agents/checkpoints/scientific-engineering-foundation.md).

## Overview, evidence and run presentation follow-up

The subsequent requested cleanup keeps one About this study card with the saved
engineering question and adjacent details/approach actions. Evidence rows in limits
match assumptions; source content and visible authorship precede technical metadata.
Run Results shows all outputs once, with unavailable reasons beside the value.
The old preview selected the first four API outputs without scientific ranking.
The renamed Export model and data action distinguishes model/diagram/CSV/source
downloads from the computational archive. The
[presentation checkpoint](phases/02-local-edition/checkpoints/study-overview-run-cleanup.md)
records integrated checks, corrections and scope cleanup.

The live UI from `ed27ba8` retains the full question, displays all eleven outputs
for the revised hydrogen run and downloads model version
`420b8ed0-dbc6-465b-968b-3e1ca7dc0df6`. Runtime bytes and all 49 attested source paths
remain unchanged. No scientific record, numerical input or result changed. Screenshots,
DOM, model download and output-table evidence are in the retained scope's
`evidence/overview-run-cleanup`, indexed by `file-identities.json`.

Computational-record review request `6488355f-f5ca-4005-8aea-7ecb3b4aa0a9` remains
queued: the demo dispatcher was started without the existing export-processing mode.
Its command is `3923d30a-a01b-48e9-92de-fa116c58cfdf`. No duplicate was submitted and
no archive download is claimed. Export-loop integration is deferred separately from
this UI cleanup. Automated browser verification does not establish human acceptance
or release qualification.
