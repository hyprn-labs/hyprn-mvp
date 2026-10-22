---
phase: 03-agent-tools-for-coding-agents
plan: usersnap
type: execute
wave: 1
depends_on: []
autonomous: true
requirements: [UI-01, SEC-01]
files_modified:
  - application/src/hyprn_mvp_app/ui.py
  - application/tests/test_ui_static.py
  - ui/src/main.tsx
  - ui/src/usersnap.ts
  - ui/tests/usersnap.spec.ts
  - deployment/tests/usersnap_ui_fixture.py
  - deployment/checks.py
  - ui/provenance.md
  - docs/operations/usersnap.md
estimate:
  tokens: 18000
  raw_tokens: 18000
  tasks: 1
  confidence: low
must_haves:
  truths:
    - The configured existing local demo can display and open the real Usersnap feedback widget.
    - An unconfigured installation makes no Usersnap request and keeps its existing restrictive static policy.
    - Enabled HTML carries fresh matching CSP and loader nonces, with only evidenced vendor resources admitted.
    - Widget failure leaves the workspace usable and does not change scientific records or execution.
    - Isolated tests, real provider evidence, deployment status and human acceptance are recorded separately.
  artifacts:
    - path: ui/src/usersnap.ts
      provides: Idempotent optional loader using bounded server configuration
    - path: application/src/hyprn_mvp_app/ui.py
      provides: Validated configuration and response-specific CSP at the static boundary
    - path: ui/tests/usersnap.spec.ts
      provides: Real HTTP browser checks for policy, initialization, isolation and failure behavior
  key_links:
    - from: HYPRN_MVP_USERSNAP_GLOBAL_ID
      to: WorkspaceFiles HTML response
      via: Server-side canonical UUID validation and bounded inert configuration
    - from: ui/src/main.tsx
      to: ui/src/usersnap.ts
      via: Optional initialization independent of workspace rendering
    - from: WorkspaceFiles CSP nonce
      to: Usersnap loader and inherited frame policy
      via: Matching script attribute and n query parameter
---

<objective>
Make feedback reporting available in the existing local demo through the authorized Usersnap widget, with explicit opt-in and preserved application boundaries (D-01–D-07).

This scoped PLAN.md follows the repository's existing scoped-plan convention and the parent's requested single numbered fresh-executor task. Its cohesive integration includes seven production/test paths and two service records, keeping the served boundary with its browser evidence. It does not replace a numbered phase plan, reconcile the pending Phase 3 requirement mapping, or claim phase/release completion.
</objective>

<execution_context>
@AGENTS.md
@.planning/phases/03-agent-tools-for-coding-agents/usersnap/CONTEXT.md
</execution_context>

<context>
@application/src/hyprn_mvp_app/ui.py
@application/tests/test_ui_static.py
@ui/src/main.tsx
@ui/index.html
@deployment/checks.py
@deployment/tests/foundry_ui_fixture.py
@.claude/skills/hyprn-mvp-ui/SKILL.md
@design-system/README.md
@design-system/Layouts.md
@design-system/Scientific-states.md
@docs/legal/licensing.md
</context>

<tasks>
<task type="tracer">
  <name>Task 1 — Optional feedback widget through the served application boundary</name>
  <files>application/src/hyprn_mvp_app/ui.py, application/tests/test_ui_static.py, ui/src/main.tsx, ui/src/usersnap.ts, ui/tests/usersnap.spec.ts, deployment/tests/usersnap_ui_fixture.py, deployment/checks.py, ui/provenance.md, docs/operations/usersnap.md</files>
  <precondition>The parent supplies the observed vendor resource evidence and the development environment resolves the existing pinned tools, scoped scratch stores and browser; this task does not use or mutate the live demo.</precondition>
  <action>
  Read the scoped decisions and preserve the shared working tree. Implement D-03–D-04 in the existing WorkspaceFiles/mount_workspace boundary without changing the public API or its application mount caller. Resolve the opt-in at mount/startup, reject noncanonical nonempty identifiers with an actionable configuration error, and retain the current disabled response. Transform only successful HTML document responses; ordinary assets remain ordinary assets. Use a bounded, escaped inert configuration element inserted once into the document head. Generate a fresh nonce using the standard library cryptographic generator; retain matching header/body identity and correct content length. Enabled HTML must not be reused through stale ETag, Last-Modified, conditional or shared-cache behavior: disable caching/conditional reuse for transformed documents and verify repeated and conditional requests receive consistent fresh body/header pairs. Preserve GET/HEAD, missing paths, content types, host/origin enforcement, X-Frame-Options and source/traversal refusal.

  Add a small typed idempotent initializer in ui/src/usersnap.ts and call it from main.tsx independently of rendering (D-01, D-04–D-06). Read only the expected bounded configuration, return immediately when disabled, register the documented global callback before appending one asynchronous script, and construct the fixed official /global/load/ UUID URL using URL/searchParams. Set both the script nonce and n parameter. Initialize with the exact D-05 options; handle script load errors and rejected initialization without an unhandled rejection or blocking the workspace. Avoid a reusable SDK framework. Do not attach identity or study fields, log credentials, write application records, or create repeated scripts after rerender/reinitialization.

  Build the enabled policy from fixed exact origins justified by the parent's resource evidence. Keep default-src, base-uri and frame-ancestors deny-by-default and preserve same-origin application resources. Admit the response nonce for vendor script/style propagation. Keep fonts self-hosted using the official system-font option. Test inherited policy in vendor-style about:blank/srcdoc frames; do not add general remote frame permission. Treat the two observed vendor hosts as the initial evidence to refine, not a completed runtime inventory. Add a resource only in the directive that needs it, with its evidence recorded. D-02 authorizes this provider-specific exception; D-06 prohibits silently broadening it if the vendor behaves differently.

  Extend test_ui_static.py for disabled behavior, accepted/rejected identifiers, escaped configuration, fresh nonces, HTML/asset/HEAD/conditional behavior and retained boundary refusals. Register one narrowly scoped usersnap-ui group in deployment/checks.py, backed by deployment/tests/usersnap_ui_fixture.py and ui/tests/usersnap.spec.ts. Reuse existing scope allocation, approved application interpreter, clean environment, scoped Vite build, Chromium configuration and cleanup conventions. Serve the actual WorkspaceFiles HTTP path and compiled entry module; do not substitute the in-browser Foundry API double for the static/CSP boundary. Deterministically intercept only vendor responses with small test-owned scripts to observe the callback, init arguments, style nonce and inherited frame behavior; this is adapter evidence, not live-provider proof. Cover disabled zero outbound requests, enabled one loader, matching nonce/query, blocked unrelated origin, refusal of an unnonced injected script, accepted nonced style in the inherited frame, and provider failure with a still-functional workspace. Keep screenshots and network logs outside the repository. No new installed package is needed; runtime provisioning belongs to the parent.

  Record the hosted proprietary service, official sources, observed loader identity and mutable-runtime limitation in ui/provenance.md. Add docs/operations/usersnap.md with the default-off configuration, exact enabled policy, D-02's user-authorized script/style exception, privacy options, local activation prerequisites and rollback by removing the setting and restoring the reviewed release. Link the two records. Do not change main metadata or characterize this service as an audited permissively licensed package. Host-specific environment values and evidence locations remain outside portable instructions.

  Run the focused checks below, then make explicit-path atomic commits and create 1-CHECKPOINT.md beside this plan (D-07). Record every failure, counts, tested revision, exact commands, vendor provenance/evidence identities, temporary scopes released, remaining risks and the parent handoff. Do not stage generated builds, test evidence, another task's files, STATE.md or ROADMAP.md. The parent owns live activation, local deployment and final real-provider verification; record that obligation rather than declaring deployment complete.
  </action>
  <verify>
    <automated>./hyprn-mvp dev check public-api</automated>
    <automated>./hyprn-mvp dev check combined-static</automated>
    <automated>./hyprn-mvp dev check usersnap-ui</automated>
    <automated>./hyprn-mvp dev check locality-contracts</automated>
    <human-check>The parent opens the activated real widget in the identified deployed local demo, verifies no relevant CSP violations or unexpected origins, and records opening/closing, keyboard behavior and preserved workspace navigation. Automated observations do not establish human acceptance.</human-check>
  </verify>
  <done>The committed integration passes the registered HTTP/browser and static checks; disabled installations retain their prior policy and make no vendor request; enabled documents have fresh coherent nonces; provider failure leaves the workspace functional; the checkpoint is ready for parent verification and deployment.</done>
</task>
</tasks>

<threat_model>
## Trust boundaries

| Boundary | Control |
|---|---|
| Installation configuration → served HTML | Strict bounded UUID, escaped inert values, no operator-supplied origin |
| HTML response → browser execution | Unpredictable response nonce, correct cache/conditional handling, fixed origin policy |
| Application origin → hosted Usersnap code | Explicit opt-in, narrowly authorized provider, reduced collection, retained service provenance |
| Test runner → browser/server processes | Existing scoped stores, protected live roots/ports, guaranteed cleanup |

| Threat ID | Category | Component | Severity | Disposition | Mitigation plan |
|---|---|---|---|---|---|
| T-03-USNAP-01 | Tampering | HTML configuration/CSP | high | mitigate | Validate UUID; escape bounded values; fresh matching nonce; conditional/cache tests; block unrelated scripts |
| T-03-USNAP-02 | Information disclosure | Hosted widget | high | mitigate | Default off; explicit local opt-in; D-05 options; no automatic identity/custom study data; record actual requests |
| T-03-USNAP-03 | Denial of service | Frontend initialization | medium | mitigate | Async idempotent loader; caught failures; workspace remains interactive |
| T-03-USNAP-04 | Tampering | Mutable vendor service | medium | accept | User-authorized hosted integration; evidence hash is not a runtime pin; disabling configuration removes loading; no permissive-package audit claim |
| T-03-SC | Tampering | Package installation | high | mitigate | No new npm/pip/cargo dependency or vendor source installation; any added dependency requires a separately reviewed provenance audit |
</threat_model>

<verification>
The parent reruns Task 1's acceptance groups on the committed integration and checks its checkpoint before deployment. public-api already includes test_ui_static.py; combined-static already includes design-system, token, UI contract, TypeScript and build checks. usersnap-ui must be registered by Task 1, with missing browser/build/fixture treated as failure. locality-contracts protects application/module boundaries. Do not run the check runner directly or tests under another interpreter. If the existing workflow requires style-ratchet, run `./hyprn-mvp dev check style-ratchet` once and record new delta separately from established debt; avoid unrelated formatting.

Before deployment, the parent identifies the current demo release, source revision, process/container and recoverable prior configuration; coordinates any concurrent deployment; enables only this installation; and deploys using its existing procedure. Preserve authoring records and attestation invariants. Do not broaden the target to cloud work.

After deployment, inspect the real provider's loading and widget opening under the effective CSP, including inherited frames. Check light/dark and narrow layouts, keyboard dismissal and return to workspace navigation. Use synthetic feedback only if the existing authorization covers sending it; otherwise distinguish successful opening from unverified end-to-end submission. Record observed required origins and any provider dashboard activation separately. The parent retains the full qualification gate as a release obligation; focused integration evidence does not claim a qualified release.
</verification>

<success_criteria>
The local demo actually serves the reviewed integration and can open the real widget; the disabled path remains unchanged; all focused checks pass on the committed batch; the provider-origin inventory and narrow exception are recorded; no scientific records or workers changed. Distinguish implementation complete, deployed, verified widget opening, feedback submission and human acceptance in the handoff.
</success_criteria>

## Multi-source coverage audit

| Source | Item | Coverage |
|---|---|---|
| GOAL | Authorized local-demo Usersnap integration/test/deploy | Task 1 plus explicitly owned parent deployment/real-provider verification |
| GOAL | Roadmap Phase 3 embedded assistant | Outside this additive request; unchanged and not claimed complete |
| REQ | UI-01 public API/design ownership | Task 1 preserves workspace and public boundary; provider exception D-02 is explicit |
| REQ | SEC-01 ASVS L1 | Task 1 policy/configuration/failure tests and threat register; release qualification remains separate |
| RESEARCH | Official global loader, init options and nonce propagation | Task 1; exact source links and observed loader identity in CONTEXT.md |
| RESEARCH | Complete runtime resource inventory/provider activation | Parent evidence handoff before final CSP/deployment; no guessed allowlist |
| CONTEXT | D-01–D-07 | Task 1 and parent acceptance/deployment obligations cited above |

<output>
Create `.planning/phases/03-agent-tools-for-coding-agents/usersnap/1-CHECKPOINT.md`. The parent appends integration/deployment evidence and records any remaining submission or human-acceptance obligation. The parent owns committing these scoped planning artifacts with explicit paths; no central planning files are modified by this planner.
</output>
