# Evidence reader — owner-requested UI amendment

Base: 222a02163b3cb7ff6b0aa68f7850c0602012d66b. Separate managed worktree evidence-reader.
First usable outcome: claims open their cited evidence directly in the shared panel;
the Evidence page shows those versions with source, quotation/location and explanation.
Target: existing local app at port 54821, no authoring mutations.

One cohesive journey: shared reader + referenced library + brief/answer access.
Acceptance: no nested evidence buttons; explicit source/quotation/explanation; correct
agent attribution; direct record metadata; saved exact-version pins; unavailable and
partial reads; no source fabrication. Existing layouts and dock behavior retained.

Checks: combined-static; ae-ui-evidence; brief-ui; study-answer-ui; ui-reading.
Update obsolete library tests to assert referenced membership and immutable history,
retaining creation, revision, stale/recovery, pagination picker and access guarantees.
Deploy the verified static build with source/live fingerprint guards and recoverable
index backup. Verify real public UI for structured and legacy evidence, claim access,
light/dark and responsive behavior. Record automated checks separately from human
acceptance. This UI batch is not full numerical/release qualification.
