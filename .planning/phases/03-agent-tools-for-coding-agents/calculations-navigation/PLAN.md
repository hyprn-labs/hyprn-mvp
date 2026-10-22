# Calculations navigation and compact input sliders

Owner: this session. Authorized user journey: Overview → Models → saved-version-scoped Calculations (Configurations / Runs), with the approved compact sliders and unchanged real prediction/sampling paths. Target: existing local demo, UI-only refresh. Stop after focused checks and live verification; release qualification remains deferred by the user.

Own Workspace.tsx, views/{configurations,runs,cases,model,registry}, RunPanel.tsx, new calculation navigation/model-version controls, exploration.tsx and a separate slider CSS recipe, focused navigation tests. Preserve concurrent evidence edits, especially ConfigurationPanel/Record, ContextDetails, EvidenceView, foundry.css, workspace.tsx, compositions.tsx and shared design documents. No evidence rendering changes or scientific record mutations.

Acceptance: exactly three study destinations; saved model selection persists across calculation tabs and links; lists include only configurations/runs pinned to that version; drafts cannot be selected as a calculation version; existing exact record links and unsaved guards work; numeric entries/slider stops preserve all values and prediction semantics. Use combined-static and ui-navigation through the local entry point, then read-only live navigation and real slider predictions. Record fixture vs real evidence separately.
