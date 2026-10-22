# Repository/build hygiene checkpoint — 2026-10-20

Implementation: `74ae2a4`.

- `.gitignore` covers additional database files, private key containers,
  service-account filenames and infrastructure state/private configuration;
  explicit nonsecret environment templates remain trackable.
- Repository-root Docker context has a source-root allowlist and private-file
  exclusions. The actual temporary-context builder independently refuses private
  filename classes and symlinks before Docker receives any bytes, preserving
  source-drift verification.
- ADR-0014 and the phase amendment record fresh PostgreSQL initialization and
  retirement of external MCP/ChatGPT while retaining the embedded Assistant.

Verification: with the existing off-repository development environment sourced,
`./hyprn-mvp dev check deployment-hardening`: **76 passed**, before commit and on
the committed batch. The latter took 1.01 seconds including test startup.
Fixture scopes were released by the check runner. Git ignore checks cover seven
synthetic private paths; safe `.env` examples and application source remain
trackable. `git diff --check` passed for the edited implementation paths.

Initial invocation with the default tool-cache location failed: sandbox cache
access was denied, then the cache proved to lack the pinned Python executable.
Using the existing configured development toolchain resolved this without changing
dependencies or the repository launcher.

Read-only operational observation: dedicated HYPRN GitHub identity reports
organization plan `free`; remote `main` and `codex/publish-local-edition` are
unprotected. No `staging` branch was returned. No GitHub settings were modified.
Required private-branch protections remain an activation prerequisite.

An additional read-only history scan inspected 5,578 product and 686 platform
blobs reachable from local Git refs. Five high-confidence patterns covered private
key headers, Anthropic/GitHub tokens, Google service-account documents and AWS
access-key IDs; no blob exceeded the 5 MiB scan bound. Two product hits were
the same negative export-test fixture in historical revisions: a bare PEM header,
not a key. Platform had no hits. No credentials were printed or rotated, no
history was rewritten. Unfetched remote refs, encrypted/encoded material and
patterns outside this limited scan remain outside its claim.

Limits: this is build-input hygiene and a bounded history scan, not a complete
secret audit or release qualification. PostgreSQL, cloud identity, real hosted execution,
release lifecycle, infrastructure and CI are ongoing. No cloud resources changed,
no live data deleted, no hosted release claimed.
