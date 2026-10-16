# Live explorer deployment and preparation

The current local demo was refreshed from `6d9beaf` (UI source `a2a322a`;
subsequent delta is integration documentation). The existing application store
was stopped and backed up; the modeling service and authoring store were
preserved. The current worker was rebuilt and successfully attested before
restarting the existing loopback application and both dispatch lanes.

The first refresh attempt stopped before mutation because the retained demo
uses the explicitly configured development scratch root, while the normal
check environment resolves the OS temporary root. Supplying the verified
existing demo scratch root corrected that mismatch; no guard was bypassed.

## Live scientific preparation — in progress

Only public named tools author exploration for the selected study
`50e423fd-a709-4e21-9381-0b09022b4115`, saved answer
`5a2786ed-d321-4aa7-b0b9-ebfabe5131c1`, exact model
`420b8ed0-dbc6-465b-968b-3e1ca7dc0df6`. Existing interpretations are unchanged.
The design declares three category/configuration mappings and all fourteen
free inputs, with explicit ranges, units, common selections and covary pairs.
These are study data, never product-specific rules.

The declared preparation budget is at most 120 original evaluations: 48 joint
points (12 training and four reserved checks per category), then 72 baseline
and axis support points. The first check selects the numerical method; three
separate checks assess each output. Targets remain absolute 1e-6 in output
units plus 1% relative error. Estimates missing those targets remain unavailable.
Baseline/axis support does not establish full-domain physical validity.

Design `d2f37d8f-6116-440e-9c1c-eaf6f3a34460`; sample operation
`affa1be8-769a-4fe9-8632-f3071c5a5a19`. Last observed snapshot: 16/48 joint points, 0 failed.
The preparation process persists command IDs before writes and returned IDs
after acceptance; uncertain submissions stop for reconciliation. It subsequently
adopts exact support runs, builds, warms and verifies baseline queries. Do not
submit a duplicate operation when resuming.

Owner-host evidence is in `/private/tmp/hyprn-explorer-demo`: recovery backup,
worker proof, `preparation.json`, `progress.json`, `preparation.log`, and the
public-tool preparation client. The demo uses the retained f7145c6a scope
identified by its readiness record; no fixture test ran against this installation.

Live UI inspection is pending sign-in. The focused isolated acceptance in
[3.V5-integrated.md](3.V5-integrated.md) remains valid; live preparation, human
acceptance and full release qualification are not claimed complete. Next owner:
main agent reconciles the saved operation/process, inspects the completed
assessment, verifies the live view, then records final deployment evidence.
