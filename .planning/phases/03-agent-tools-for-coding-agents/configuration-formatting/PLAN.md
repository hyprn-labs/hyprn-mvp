# Configuration formatting correction

User scope (2026-10-16): preserve the original configuration layout; correct overlapping back navigation, title/actions alignment and formatting through the design system. The rejected HTML redesign is not a delivery target.

Single cohesive UI batch: keep the existing input/provenance table, evidence blocks, criteria and bottom Run/model actions. Move the header into normal document flow, use token spacing and responsive alignment, right-align values and use existing unit typography without changing stored values. Add a regression for long titles, back navigation and exact value preservation. Scope the zoom test's evidence action to its open dialog.

Acceptance: combined-static; foundry-nav (saved/draft journey and genuine 200% zoom); browser inspection of the actual saved configuration at desktop and narrow width. Refresh only the local installation's static UI with a guarded backup; preserve authoring data and runtime. Automated checks are not human acceptance.

Ownership: this turn owns the configuration source/CSS, two design documents, related browser tests and this checkpoint directory. Unrelated planning/research edits remain untouched. Follow the approved cohesive-batch cadence amendment in DELIVERY-PLAN.md.
