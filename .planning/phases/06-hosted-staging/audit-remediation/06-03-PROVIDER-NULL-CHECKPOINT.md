# Provider readback: nullable fetch source setting

The real provider retained the first exact reviewed reviewer but added
`url_sources: null` to its `web_fetch` config. The metadata, version, skill and
remaining controlled fields matched. Strict byte-shaped comparison incorrectly
reported definition drift. Diagnosis used only GET/list; no duplicate creation,
provider session, runtime mutation or scientific data change occurred. Temporary
credential material was removed in `finally`.

`deployment.managed_assistant.readback_tools` now treats only this known optional
null default as omitted. Non-null restrictions, unknown properties, tool additions
and policy changes remain mismatches. Desired definitions and their approved
configuration digests do not change. The existing intent/reconciliation journal
continues to control creation.

Sources inspected on 2026-10-22:
- https://platform.claude.com/docs/en/api/go/beta/agents
- https://platform.claude.com/docs/en/managed-agents/tools
- https://platform.claude.com/docs/en/managed-agents/skills

Verification:

```text
HYPRN_MVP_DATA_ROOT=<development-root> HYPRN_MVP_TOOLS_DIR=<pinned-tools>
HYPRN_MVP_TEST_BUILD_CACHE_BYTES=21474836480
./hyprn-mvp dev check hosted-assistant-setup
```

26 tests passed in 12.76 s, exit 0; isolated scope
`521675a9-7d5d-43f3-971e-c9295320846e` released. Log:
`/private/tmp/hyprn-assistant-null-readback-check.log`.
The provider double now emits the observed null field. Public command tests cover
successful intent reconciliation without new writes and refusal of actual URL
policy changes and unknown fields. No earlier checks repeated.

Real read-only diagnosis is retained privately in
`/private/tmp/hyprn-audit-remediation-release/reviewer-readback.json`.
Real corrected readback and continuation remain the deployment orchestrator's
next step; these local tests do not prove complete live setup or skill use.
