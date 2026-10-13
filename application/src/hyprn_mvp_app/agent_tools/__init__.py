"""Agent tool registry: the curated tools an agent uses to work in one study.

Every tool composes owner operations of the public API (``/api/1``), reached in process with a
delegated agent session; no tool reaches a store, the modeling service or an engine directly.
The package reaches only itself and ``contracts``. Modules: ``spec`` (the tool specification
and its closed vocabularies), ``registry`` (build rules, offered definitions, validated
invocation), ``write_policy`` (the closed human-only route classification), ``api_client``
(the in-process API client), ``playbook`` (the packaged playbook sections), ``instructions``
(the MCP server instructions) and ``catalogue`` (one module per area).

This file imports nothing, so ``python -m hyprn_mvp_app.agent_tools.playbook`` runs the
playbook module once.
"""
