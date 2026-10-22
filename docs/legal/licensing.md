# Licensing

Status: record of licensing facts, recorded obligations and open items. This is not legal advice and not a legal opinion; it states what is known and what still needs counsel. **Legal review is pending before any commercial cloud distribution of HYPRN MVP.**

Per-component detail lives in the provenance records: `modeling/provenance.md`, `application/provenance.md`, `integration/provenance.md`, `integration/document-parser-provenance.md`, `ui/provenance.md` and the browser licence copies in `ui/licenses/browser.txt`.

## 1. HYPRN MVP's own code

The HYPRN MVP application (`hyprn_mvp_app`), execution integration (`hyprn_mvp_integration`), UI, contracts and design system are independently authored. They contain no WhatsOpt application code, templates, authentication, serializers, adapters or product UI, and no WhatsOpt code is copied into any client. Product, agent and assessment logic stay outside WhatsOpt. Clients reach modeling only through the independently authored Modeling Backend Contract.

## 2. WhatsOpt and what HYPRN MVP runs

| Fact | Value |
|---|---|
| WhatsOpt repository licence | GNU Affero General Public License v3 (AGPL-3.0) |
| WhatsOpt frontend package | `package.json` declares `UNLICENSED` |
| WhatsOpt CLI (`wop`) | Apache-2.0; HYPRN MVP clients never use it |
| Upstream identity | Official `WhatsOpt/WhatsOpt` commit `597f5abf18d4a6335c2f3b9174ab16acdf1de4bd`, source archive SHA-256 `4937188df6ea12daa8a2b00767005e3649d2974ab6e634409f7756043ef0b360` |
| What HYPRN MVP runs | A **patched copy** of WhatsOpt as its private modeling service, behind the Modeling Backend Contract, on a private network with no public listener |
| HYPRN MVP modifications | An in-process contract adapter and its successors (ordered patches `040` to `090`) and an AGPL-3.0-only deployment adaptation that removes the native product UI and executable helpers; all listed in `modeling/provenance.md` |
| WhatsOpt product UI | Not copied, embedded or distributed |

## 3. Obligations recorded

These are the obligations the project treats as applying to the modeling service. Whether and when each is triggered (for example by a cloud offering in which users never interact with the modeling service directly) is for counsel to confirm.

1. **Notices.** The upstream `LICENSE`, `Gemfile`, `Gemfile.lock` and `package.json` stay in the modeling image. Every HYPRN MVP patch and the deployment policy carry explicit AGPL-3.0-only notices.
2. **Corresponding source for modifications.** The modeling image carries every ordered patch, the deployment policy, the Dockerfile, the provenance record and the source identity in a corresponding-source directory, and the repository keeps the native, control and authoring build recipes and pins. Source access for recipients includes the upstream source (identified by commit and archive hash), every modification and the matching build and install recipes, offered alongside any distribution or AGPL network offer. These records are a compliance inventory, not a certification.
3. **Separation is not immunity.** Network and container separation are technical isolation. They are not treated as settling licensing obligations.
4. **Generated model code: unresolved.** The native OpenMDAO code templates carry no generated-code exception, and the bodies they emit are substantive. Until counsel decides, generated files are treated as inside the AGPL scope, template licences are recorded per prepared artifact, and every prepared artifact carries a generated-code notice.
5. **Separate licence sets per artifact.** Model-author declarations, generated-code and template licences, and runtime dependency licences are tracked as separate sets in every prepared artifact and execution bundle.

### Local-edition corresponding source

The local edition builds WhatsOpt under AGPL-3.0 from the commit, archive SHA-256 and length in `deployment/locks/upstream.json`. Setup fetches that archive by pin and refuses changed bytes. The modeling image ships the original archive, `upstream/whatsopt-patches/`, the modeling policy, both source and modeling Dockerfiles, the upstream and gem locks, and their build identity in `/usr/share/hyprn-mvp-modeling-source/`. These files, together with the repository's matching build code and pins, identify the corresponding source for recipients. `THIRD_PARTY_NOTICES.md` lists the shipped components. This inventory does not resolve the pending legal review under L1 and L4.

## 4. Other components

| Component | Licence | Use and obligation |
|---|---|---|
| OpenMDAO 3.45.1 | Apache-2.0 | Numerical engine in the restricted worker; unit catalog derived from it at build time |
| AiiDA | MIT | Execution lifecycle and stored artifacts on the trusted host runner |
| Application dependencies (FastAPI, Pydantic, Starlette, Uvicorn, httpx, jsonschema, rfc8785 and transitive packages) | MIT, BSD, Apache-2.0, PSF | Upstream notices kept on redistribution |
| certifi | MPL-2.0 | Unmodified; keep its licence and the availability of its source |
| React, React DOM, scheduler | MIT | Shipped in the browser bundle; notices in `ui/public/THIRD_PARTY_NOTICES.txt` |
| Vite, TypeScript, Playwright, Rolldown | MIT, Apache-2.0 | Build and test tools only; Rolldown platform bindings rely on the main `rolldown` package's MIT notice |
| Lightning CSS | MPL-2.0 | Unmodified build tool only; not in the served bundle |
| pypdf 6.20.0 | BSD-3-Clause plus embedded Adobe, Unicode and contributor notices | Planned document parser; all embedded notices are kept in the parser image's notice bundle |
| uv 0.12.24 | MIT OR Apache-2.0 | Toolchain only: `./hyprn-mvp` downloads it on each host from the official release and verifies its SHA-256 (`deployment/locks/tools.json`); not redistributed |
| CPython 3.12.15 (python-build-standalone `20261003`) | Python-2.0 and CNRI-Python, with bundled libraries under their own licences (`docs/operations/dependency-audit.md` §3) | Provisioned by uv on each host from the upstream release with uv's embedded SHA-256; not redistributed; see L6 |

## 5. Rule for new dependencies

Every new dependency needs, before installation, a review of its official source, exact version, hash and licence, with notice files recorded. Only permissive licences are admitted for new dependencies. A material provenance or licence conflict is raised for review before extraction, vendoring or distribution. The proposed workbench engines (for example Keycloak, Tiptap, Yjs, React Flow, XDSMjs, dockview, assistant-ui) were chosen partly for permissive licences, but each still goes through this review when adopted, and licence changes upstream are watched.

## 6. Permissive replacement modeling backend

WhatsOpt sits behind the independently authored, versioned Modeling Backend Contract precisely so it can be replaced. A permissive replacement backend (composition, XDSM views, OpenMDAO code generation on Apache-2.0 OpenMDAO, XDSMjs for diagrams) can be scoped behind the same contract in parallel with the legal review.

Replacing WhatsOpt changes only the modeling-service implementation, its deployment configuration and its data migration, never the clients, provided the contract version, capabilities and behaviour are preserved. Readiness is shown by the contract itself, portable-model-record export and import round trips, backend-independent contract tests and numerical-equivalence checks, not by running a second production backend. Stored runs and computational record exports stay readable without either backend. A replacement backend would use permissive templates, removing the generated-code question for new artifacts.

## 7. Open items

| # | Item | Recommended default |
|---|---|---|
| L1 | AGPL obligations of the modeling service for a commercial cloud product | No commercial cloud launch before legal review; internal staging may proceed; keep all WhatsOpt material inside the modeling service's compliance scope |
| L2 | Licence status of generated model code | Treat generated files as inside the AGPL scope and record template licences per artifact until counsel decides |
| L3 | Permissive replacement modeling backend | Scope it behind the Modeling Backend Contract in parallel with L1; decide adoption after the legal review |
| L4 | Distribution of the local edition, which includes the modeling image | Treat it like any other distribution: ship the corresponding-source directory and notices with it, pending L1 |
| L5 | Third-party notice bundle for cloud releases | Every release carries the licence and source notices of the modeling service, the browser bundle and, once adopted, the parser image |
| L6 | Berkeley DB 6.0.19 (Sleepycat licence) is linked into the `_dbm` extension module of the Linux CPython builds that uv provisions (python-build-standalone `20261003`). Sleepycat requires redistributions to offer the complete source of the DB software and of any software that uses it | HYPRN MVP does not redistribute the interpreter: each installation downloads it from the python-build-standalone GitHub release with a pinned SHA-256, so Linux is not blocked. Before any distribution that ships an interpreter (local-edition bundle, images), either remove `lib-dynload/_dbm*.so`, which upstream builds as a separate shared module for this purpose (no HYPRN MVP source imports `dbm` or `shelve`), or obtain counsel's view together with L4. Upstream: astral-sh/python-build-standalone#836. Record: `docs/operations/dependency-audit.md` §3 and §8 |

## 8. Demo interface notice review — 2026-10-15

The interface has no software-notices page or footer link. The exact installed MIT
licence texts for React, React DOM and scheduler are retained in
`ui/licenses/browser.txt` and embedded by the UI build in each delivered JavaScript
bundle. This satisfies the copy-accompanying requirement without introducing a
product navigation item. Build verification must check that the notice survives
minification. Licence/source records belonging to redistributed native and modeling
artifacts remain intact; removing the interface feature does not remove those obligations.

Other obligations follow the delivered artifact, not a general advertising requirement:

- **AiiDA (MIT):** retain its copyright and licence with distributed host software. Its installed native notice inventory contains `aiida_core-2.9.3.dist-info/licenses/LICENSE.txt`. This does not require an AiiDA badge in the browser.
- **OpenMDAO (Apache-2.0):** retain the licence and applicable attribution/NOTICE material with redistributed worker software. [Apache-2.0 §4](https://www.apache.org/licenses/LICENSE-2.0) permits the required NOTICE attribution in accompanying documentation; it does not require a home-page supplier badge. Worker packaging remains the owner of those notices.
- **Modified WhatsOpt (AGPL-3.0):** a short credit is insufficient. The running demo's modeling image was inspected read-only: `/native/LICENSE`, the pinned upstream archive, ordered patches, policy, build recipes, dependency pins and source identity are retained. Distribution must provide the matching corresponding source; [AGPL §13](https://www.gnu.org/licenses/agpl-3.0.html#section13) also requires a prominent source offer to remote users interacting with a modified program when that provision applies. Private networking is not an exemption. The existing source inventory is not proof of a complete recipient-facing source offer.
- **Generated artifacts:** preserve their recorded author, template/generated-code and runtime licence sets. The unresolved generated-code scope in L2 remains unchanged.

This review records artifact-level licence retention; it is not release legal clearance. Before external network operation or software distribution, L1/L4/L5 still require confirmation of source-offer scope, completeness and delivery for the exact release. No backend source bundle or newly exposed network endpoint was added by this UI change. Existing dependency and source notices were not removed.
