"""Agent runtime: the installation's administration of agent access and the agent records.

Modules: ``schema`` (the runtime-owned tables, created through the store's connection by the
composition root), ``records`` (the only SQL over the agent records; it runs on a connection the
store hands out, so ``Store`` stays the single transaction owner), ``control`` (the
installation kill switch), ``delegations`` (local delegations an Owner issues), ``tokens``
(minting, listing and revoking local tool tokens; no HTTP route mints one), ``attribution``
(who wrote what, cross-checked against the owners' receipts), ``routes`` (the human-only agent
routes of the public API) and ``__main__`` (the operator commands).

This file imports nothing, so ``python -m hyprn_mvp_app.agent_runtime`` runs the operator
commands once.
"""
