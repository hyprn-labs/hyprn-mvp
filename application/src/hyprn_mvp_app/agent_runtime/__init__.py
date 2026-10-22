"""Agent runtime: the installation's administration of agent access and the agent records.

Modules: ``schema`` (the runtime-owned tables, created through the store's connection by the
composition root), ``records`` (the only SQL over the agent records; it runs on a connection the
store hands out, so ``Store`` stays the single transaction owner), ``control`` (the
installation kill switch), ``delegations`` (authority ceilings and access state), ``attribution``
(who wrote what, cross-checked against the owners' receipts), ``routes`` (the human-only agent
routes of the public API). The embedded Assistant opens server-owned sessions through
``Runtime``; this package exposes no external transport or operator entrypoint.
"""
