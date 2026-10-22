---
phase: 06-hosted-staging
plan: 03B
type: execute
autonomous: true
wave: 3
depends_on: []
files_modified: [deployment/managed_assistant.py, deployment/tests/test_managed_assistant.py, deployment/checks.py, docs/agents/embedded-assistant.md]
---

<objective>Deliver release-bound managed assistant provisioning as code, reviewable offline and exercised against an isolated provider double. Live apply requires a later explicitly approved plan; no live sessions, mutations, secrets transfer or spending changes are authorized.</objective>
<tasks>
<task type="auto" tdd="true">
<name>03B: Prepare deterministic managed assistant definitions and safe reconciliation</name>
<files>deployment/managed_assistant.py, deployment/tests/test_managed_assistant.py, deployment/checks.py, docs/agents/embedded-assistant.md</files>
<behavior>Offline plan derives custom tools and scientific guidance from the shared registry and playbook. Explicit model settings, no network/packages/MCP/built-ins/workflows, exact version readback, private state, durable intent before mutation, uncertain reconciliation without blind retry, partial recovery, drift refusal, repeat no-op and changed release replacement are covered through the command boundary.</behavior>
<action>Reuse the audited Claude HTTP adapter and official resource API payloads. Keep one study conversation and shared allowance ownership in existing application code. No new dependencies, resource deletion or generic infrastructure framework. Emit the existing Settings binding names and a configuration digest for platform integration.</action>
<verify><automated>./hyprn-mvp dev check hosted-assistant-setup</automated></verify>
<done>Focused fake-provider journey passes and deployment instructions specify the exact review/apply/reconcile workflow; live provider acceptance remains explicitly unverified.</done>
</task>
</tasks>
<threat_model>Credential disclosure: private owner-only file through existing adapter, safe fixed diagnostics. Endpoint injection: fixed adapter host. Duplicate creation: fsynced intent and metadata lookup; uncertain absence blocks. Concurrent writers: exclusive state lock. Definition drift: regenerate and compare reviewed content plus exact provider readback. No provider scientific execution.</threat_model>
