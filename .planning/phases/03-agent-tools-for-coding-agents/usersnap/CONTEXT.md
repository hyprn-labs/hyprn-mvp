# Usersnap integration — scoped decisions

Recorded 2026-10-20 from the current user-authorized integration, test and local-demo deployment request. This is an additive scoped task, not a replan or completion of Phase 3.

## Decisions

- **D-01 — Outcome and target.** Integrate the Usersnap global widget `9c4a930c-b62f-4b89-bca3-260ec022694a`, test it and deploy it to the existing local demo. The parent session owns target identification, provider activation and deployment. Cloud deployment is outside this task.
- **D-02 — Narrow policy amendment.** The user's explicit request authorizes this hosted Usersnap integration and the necessary CSP changes as a scoped exception to the external runtime script prohibition in `AGENTS.md` and `.claude/skills/hyprn-mvp-ui/SKILL.md`. It does not authorize general third-party scripts, remote fonts, weakening scientific boundaries or changing worker containment.
- **D-03 — Explicit opt-in.** Installations default to disabled. Configure the public widget identifier through `HYPRN_MVP_USERSNAP_GLOBAL_ID`; an absent/empty value disables it. Validate a canonical UUID before constructing any HTML or URL. The demo identifier is deployment configuration, not a global product default or a secret.
- **D-04 — Constrained integration.** Generate a cryptographically unpredictable nonce per enabled HTML response; expose only the validated identifier and nonce as bounded inert HTML configuration. Keep executable initialization in the compiled frontend module. Pass the nonce through both `script.nonce` and Usersnap's `n` URL parameter. Retain the deny-by-default CSP and existing host, origin, framing and traversal controls.
- **D-05 — Reduced collection.** Initialize with `useSystemFonts: true`, `collectGeoLocation: 'none'` and `useLocalStorage: false`. Do not supply automatic user identity, custom study metadata, scientific records or credentials. This does not claim that the hosted service receives no network metadata or that user-created screenshots contain no data.
- **D-06 — Evidence and provenance.** Use only exact vendor origins justified by observed requests and official documentation. No Google font origins, permissive scheme sources, blanket vendor subdomains, general remote frame permission, permissive inline/evaluation policy or new installed dependency. The hosted proprietary service is not a pinned, audited permissively licensed package. Do not vendor its code. Provider outage must not prevent the workspace from working.
- **D-07 — Ownership and completion.** One numbered integration task runs in a fresh executor context, preserving unrelated edits and using explicit-path commits. The parent verifies the committed batch, deploys to the identified existing demo and records real widget behavior separately from isolated browser evidence and human acceptance. No study writes, calculation launches, worker changes, central planning edits or cloud implementation.

## Verified research and remaining discovery

Official sources checked on 2026-10-20:

- [Usersnap global API](https://help.usersnap.com/reference/global-api): the global loader endpoint, asynchronous `init`, and the three options in D-05.
- [Usersnap CSP guidance](https://help.usersnap.com/docs/usersnap-with-csp): script/style nonces and propagation through the loader attribute and query parameter. Its broad example is not an approved application policy.

The parent retrieved the official global loader on 2026-10-20: 14,839 bytes, SHA-256 `77dc5d57b35f461bf85f0d4ed20bcbbe46f7f87b65d070cfb13f4c47d2c03d96`. The observed loader references `widget.usersnap.com` and `resources.usersnap.com`; follow-on vendor setup code propagates the nonce into `about:blank` frames. These are observations, not an exhaustive runtime allowlist or an immutable version pin. Temporary external files are evidence only and are not product inputs.

The parent owns inspection of actual widget requests, precise directive-to-origin mapping and provider activation. The Issue reporting project was not live when inspected. Before deployment, record the resulting active project and actual resource policy in the checkpoint. If observed needs conflict with D-04–D-06, retain the constraints and report the concrete incompatible behavior; do not silently broaden policy.

The executor records durable service provenance in `ui/provenance.md` and the scoped policy amendment, configuration and rollback in `docs/operations/usersnap.md`. Required integration groups are `public-api`, `usersnap-ui`, `combined-static` and `locality-contracts`, all through the local edition entry point. Runtime provisioning and live installation changes belong to the parent.

## Deferred and excluded

Cloud rollout, broad telemetry, automatic identity enrichment, session replay, video/microphone capture, new dependency installation and scientific-data changes are not included. Existing phase and release obligations remain open.
