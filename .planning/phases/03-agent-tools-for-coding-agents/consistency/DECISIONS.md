# Consistency decisions

Product-owner decisions of 2026-10-18 after the read-only consistency audit (domain object map, object × screen matrix, journeys and screenshot atlas of the live demo at `570b7be`). They replace page-by-page issue reporting with one domain model, one home per object and one page contract.

## Decisions

| | Decision | Record |
|---|---|---|
| D1 | The study owns a versioned brief (question, scope, global assumptions, limits, open questions). The modeling approach leaves the domain and the app. | ADR-0007 |
| D2 | Overview is the study's home: brief, study answer and answer exploration. The Model page shows the application-owned Model explanation tab above the graph. Models and their versions are under Models; calculations, configurations and runs under Calculations. | ADR-0007 |
| D3 | One study answer family: conclusion with justifications, plus the answer exploration's basis, versioned together and pinning the brief version. Moving exploration inputs never writes. | ADR-0008 |
| D4 | Calculation is a primitive: a versioned set of configuration versions for one model version with its design and runs. Reference configurations are a movable mark. The Calculations area lists calculations first. | ADR-0009 |
| D5 | One page and wording contract, enforced by checks: Open navigates to a record page; View reads in place; Edit, Save draft, Save version; Return to destination. One page header, one return link, one version select (name · short ID (draft or read-only)), one record state. "Calculations" names the area; "assessment" means scientific interpretation only. One decimal separator; no repeated "Dimensionless". | This file; Naming.md and Layouts.md in B3 |
| D6 | Delete dead and retired surfaces (Comparison, unused modules and statement components, duplicate Help, stale case wording, raw links). Keep Documents, Help and Assistant as labelled placeholders. | This file |
| D7 | Studies frame engineering decisions: the brief lists alternatives and defines study criteria (constraints and objectives) once; calculation versions bind those criteria to their model's outputs and configurations carry no criteria; the study answer has a draft and versions, maps alternatives to calculation versions (no separate grouping record) and records the comparison, a recommendation or "insufficient evidence", decisive uncertainties and the next analysis. One study frames one decision; a Decision record across studies is deferred. Fuel selection is the first workflow, checked afterwards against a prospective partner's decision case. | ADR-0010 |

Ranking, 2026-10-18 (owner): as a first layer of prioritization, alternatives that meet every constraint are ranked by the objectives in their brief order, first objective first. Weights or richer trade-off rules may refine this later.

Calculation evaluation, 2026-10-18 (owner, M2 slice 1): a run's criterion evaluation uses the glossary's words on the wire (`met`, `not_met`, `unresolved`; objectives `measured`), not the configuration-criteria value `violated`. The application keeps its own pure comparison, pinned to the worker's `evaluate_criteria` by a parity test, so the attested worker is untouched. Runs are evaluated only from their integrity-checked retained records, at most 20 per page; a run without a usable record is unresolved.

Identity golden corpus, 2026-10-18 (owner): the three golden bundles whose approach versions carry the retired `cases` field are listed as retired in `test_identity_golden.py`; assembly must refuse them, and the corpus bytes and pin stay unchanged.

Slice 3 acceleration, 2026-10-18 (owner): configuration-writing tests of the approach flows that M5 removes are retired now rather than migrated; the test migration runs with 3–4 parallel agents on disjoint files; checks stay on the affected groups per batch, with native groups and full qualification at the end of slice 3.

Old configuration requests, 2026-10-18 (owner): new configurations in request versions 2–4 are refused in slice 3, not at M5; tests that write them migrate to version 6 now.

Configurations without criteria, 2026-10-18 (owner, M2 slice 3): criteria leave configurations through new record format versions; retained formats stay readable. The new configuration version also drops `approach_binding` (ADR-0007), so no new approach closure versions are made. Batches A–C land after the agent-writes branch is merged. Plan: `configurations-without-criteria-PLAN.md`.

Authorization, 2026-10-18: all existing development studies and records may be discarded when the new domain lands, so no stored approach, configuration or answer record is migrated and no reader for retired formats is kept. The product invariant that studies are archived and restored, never deleted, is unchanged.

## Sequence

| Batch | Content | Depends on |
|---|---|---|
| B1 | ADR-0007 to ADR-0009, glossary, case wording in the contract and specs | D1–D4 |
| B2 | Remove retired surfaces and dead code | D6 |
| B3 | Page contract components and checks, adopted on pages that survive the migration (Home, Model, Evidence, Settings); foundry-nav, ported-isolated, units-ui-authoring and ae-ui-model made green | D5 |
| M1 | Study brief with alternatives and study criteria: store, contract, Overview editor, agent tools, browser tests for the brief | B1, B3, ADR-0010 |
| M2 | Calculation, reference mark and criterion bindings: store, contract, Calculations area; configuration criteria removed; sampling and estimates re-homed; configuration and run-history browser tests rewritten | B1, B3, ADR-0010 |
| M3 | Study answer draft and versions: alternative mapping, comparison, recommendation, decisive uncertainties, next analysis, answer exploration per alternative and compared; editor on Overview; exploration browser tests rewritten | M1, M2 |
| M4 | Model explanation records and tab | B1 |
| M5 | Remove the modeling approach (routes, store, UI, agent tools, study workflow skill, suites); reset the development store; re-create the fuel demonstration | M1–M4 |

Browser test work is folded into these batches (owner decision, 2026-10-18): each batch makes the suites for the pages it touches green rather than migrating tests for pages a later batch rebuilds. Each batch ends with focused checks, an atlas before and after for the owner, and its own checkpoint. Automated evidence is never human acceptance.
