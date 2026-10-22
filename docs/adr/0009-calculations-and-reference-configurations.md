---
status: accepted
date: 2026-10-18
decision-makers: Owner
---

# ADR-0009: Calculations are versioned sets of configurations with their runs; reference configurations are marked

## Context and Problem Statement

Configurations and runs are listed one by one, while most of them are produced by sampling around a few baseline configurations: in the fuel demonstration, about 140 of 149 configurations were preparation points. The sampling design, its points, and the estimates fitted to them were exploration records keyed by an answer version, so the Calculations area showed machine output without the structure that produced it. "Calculation" was also used loosely for a run, component logic and the worker.

## Decision Drivers

- Name the unit engineers actually reason about: a deliberate set of calculated points.
- Keep configurations and runs immutable and exactly pinned.
- Let a few configurations stand out as the baselines people choose.

## Considered Options

- **A:** a Calculation primitive: a versioned set of configurations with its design and runs; reference configurations marked.
- **B:** keep listing configurations and filter preparation points by provenance.
- **C:** group preparation points under the exploration that created them.

## Decision Outcome

Chosen option: **A**.

- **Calculation.** A study's calculation has immutable versions. A calculation version freezes an exact set of configuration versions, all for one model version, together with how the set was made: hand-picked, or generated from reference configurations by a sampling design (ranges, method, seed). A single configuration with one run is a calculation of size one. Adding or removing points creates a new calculation version.
- **Runs.** Runs remain immutable records of one configuration version and attach to a calculation version by reference. Running or retrying points adds runs without creating a new calculation version.
- **Estimates.** An estimate (a fitted surrogate) is built from exactly one calculation version and its runs. Its predictions are estimates, never calculated results.
- **Reference configuration.** A reference mark labels an exact configuration version as a baseline for its model. A model may have several. The mark can be moved or removed and never changes or pins the configuration; anything scientific pins exact versions.
- The Calculations area lists calculations first; each opens to its design, configurations, runs and estimates. Sampling settings move from the answer exploration to the calculation.

### Consequences

- Good: the Calculations area shows structure people chose, not hundreds of loose points.
- Good: answers cite calculation versions (ADR-0008), and estimates have an unambiguous basis.
- Good: reference configurations match the reference configurations planned for reusable packages.
- Bad: new storage, contract routes and agent tools for calculations; exploration designs and samples are re-homed.

### Confirmation

- A saved calculation version's configuration set never changes; adding a point creates a new version.
- All configurations in a calculation version share one model version.
- A run submitted for a configuration in a calculation is listed under that calculation version without changing it.
- Moving a reference mark leaves every configuration version and every pin unchanged.
- "Calculation" is not used for a run, component logic or the worker in the interface.
