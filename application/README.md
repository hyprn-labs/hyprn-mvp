# HYPRN MVP application

`hyprn_mvp_app` is the one cohesive, independently authored HYPRN MVP application: the public HTTP API (`/api/1`), local authentication and sessions, study-scoped authorization, studies and memberships, evidence and assumptions, the Modeling approach, configurations, command receipts, run submission and dispatch, historical reads, computational record exports and the static UI. It uses FastAPI and Pydantic for transport and standard `sqlite3` local transactions for its store.

The private modeling service owns the editable model graph and source behind the Modeling Backend Contract (`contracts/modeling.openapi.yaml`). The application keeps immutable model snapshots and command receipts, never an editable copy of the graph. Terms follow the glossary in `CONTEXT.md`; persisted wire names that predate it are mapped in `contracts/README.md`. The architecture, guarantees and ownership rules are specified in `docs/specs/architecture-and-contracts.md`.

## Module ownership

The application import graph is acyclic, function-local imports included. `application/tests/test_module_boundaries.py` pins the directions below.

| Module | Owns | Must not own or reach |
|---|---|---|
| `contracts` | Canonical JSON bytes and digests, identifiers, strict JSON parsing, schema loading and validation, the public `Error` envelope (`DomainError`) and schema failures with field diagnostics (`ContractError`) | SQLite, HTTP, auth, workflows, runtime activation, candidate imports |
| `units` | Unit labels, active-port admission, resolved model units and the single port-units rule (`port_units`: literal units for Model1/2 records, resolved units for Model3/4, other record format versions unsupported) | Physical parsing or conversion, stores, clients |
| `scientific_configuration`, `approach_closure` | Literal scientific snapshots; data-only validation of an exact Modeling approach closure (references only, never an executable graph) | Stores, model client, live lookups |
| `execution_bundle` | The execution bundle (wire `ExecutionBundleN`): assembly, every admission and re-admission check, version predicates, the single pairing table of supported record combinations (`RETAINED_PAIRINGS`, `bundle_family`) | Store, HTTP, dispatch, worker code |
| `store` | Transactions, command receipts, studies and membership, study archive state, exact evidence reads and snapshots (`evidence_record`, `exact_evidence`, `evidence_snapshot`), in-transaction reads (`study_row`, `command_receipt`, `model_association`) | Canonicalization or schema loading (imported from `contracts`) |
| `modeling` | `ModelingClient` (private contract transport), `Coordinator` (durable model commands, portable model record import and export checks) and the pure `checked_model` integrity check | Schema loading; an editable model graph |
| `history` | Authorized reading of stored runs (`run_row`, `read`, `retained`, `recheck`), pure outcome completeness (`complete_outcome`) and read integrity. Never consults current models, configurations or evidence | Model service access |
| `result_bindings`, `modified_runs` | Result-linked input sources and modified-run seeds, through `history` | Each other's or `history`'s private rows |
| `configuration`, `approach` | Configuration preview and commit (exact snapshots, write-time rechecks); Modeling approach authoring (`saved_version`) | The reverse dependency (`approach` never imports `configuration`) |
| `execution` | `StaticPreparation` and `Submissions` (receipt, outbox, dispatch) | Bundle checks (in `execution_bundle`) |
| `computational_export` | Computational record export requests, inspection and archive publication | Native imports, model clients, current-model reads |
| `readiness`, `dispatcher`, `auth`, `ui`, `api` | Operational observations; the trusted bridge to the host executor; local auth; static assets; the public HTTP surface | — |

The integration package (`hyprn_mvp_integration`: launcher, calculation, results, integration-side export) reaches the application only through `contracts`, `units`, `scientific_configuration`, `approach_closure` and `execution_bundle`. The attested execution source set (`launcher.execution_source_hashes()`) is exactly that static import closure plus the deployment inputs; `worker.py` and `results.py` keep their own independent admission checks.

## Running

The local edition starts the application through `./hyprn-mvp start`, inside its own container with a read-only root filesystem, a fixed non-root user, dropped capabilities, no-new-privileges and CPU, memory and process bounds. It mounts only its application store and the read-only modeling-service credential: no launcher, container socket, execution store, native product code or provider credential.

A custom deployment runs:

```sh
PYTHONPATH=application/src python -m uvicorn hyprn_mvp_app.api:from_environment --factory
```

with these variables:

| Variable | Meaning |
|---|---|
| `HYPRN_MVP_APP_STORE` | Path of the application SQLite store |
| `HYPRN_MVP_ORIGIN` | Exact public origin; only `https://…` or an explicit `http://127.0.0.1:<port>` development origin is accepted |
| `HYPRN_MVP_MODEL_URL` | Base URL of the private modeling service (`…/modeling/1`) |
| `HYPRN_MVP_MODEL_KEY_FILE` | File holding the modeling-service credential |

## Credentials and sessions

- First setup generates a cryptographically random password for the local user `owner`, stores only its scrypt hash and writes the password once to an owner-only (0600) provisioning file in the installation's data root. It is never printed, logged or passed through process arguments or environment. There is no default password. The file is an initial handover, not a permanent source of truth.
- Recovery is a local operator command, never an HTTP endpoint: `python -m hyprn_mvp_app.auth recover --store <application store>`, run inside the application container. The password is entered through hidden prompts, the identity is kept and all previous sessions are revoked. Recovery never resets scientific records.
- Browser requests use an HttpOnly, SameSite=strict session cookie (Secure over HTTPS), the exact `Origin` and `X-CSRF-Token` on every mutation; login also requires the exact `Origin`. `POST /session` returns the actor, expiry and CSRF token.
- Every operation authorizes actor, study and resource, including reads, exports and receipt replay.

## Contract and state

`contracts/hyprn-mvp.openapi.yaml` is generated by `application/generate_contract.py` from the actual routes and the closed, independently authored domain schemas. It documents responses, error statuses, origin and CSRF requirements and study-scoped cursor pagination. There is no native escape route. Source, schema and transport bounds reject duplicate keys, unknown properties, non-finite or unsafe numbers and excessive depth or size before any mutation.

- **Model commands.** Model creation and import consume the current study revision when their durable pending intent is accepted. The pending command keeps its exact remote operation, payload and command ID in the same transaction. Remote completion is adopted through the matching authoritative receipt and digest. A GET may adopt a proven result but never resubmits an absent remote command; only an authenticated retry of the same POST can. No remote lock spans an application transaction, and authorization is rechecked when adopting results and before replay.
- **Configuration preview** takes a candidate with the current study context and exact evidence snapshots, checks that every referenced evidence version belongs to the study and is unchanged, fetches the exact committed model version, verifies its identity, model digest and raw source-byte hashes, then calls only the pure configuration-compatibility operation. It allocates no IDs, receipts or configurations, writes no files and starts no processes.
- **Configuration commit** carries `{command_id, expected_revision, configuration_id?, configuration}` and the preview's candidate digest. A new configuration has a null expected revision and no configuration ID; a new version gives the current head and the configuration ID. Commit freezes the model snapshot, configuration, context, evidence and study revision in one local transaction with compare-and-set. Reads return `{configuration, model_snapshot, study_revision}`; execution uses those exact pins. Current metadata changes or a modeling outage never change historical reads.
- **Runs.** Submission records the run and an outbox entry in one transaction; one serialized dispatcher hands work to the trusted host executor through the bounded bridge. Uncertain or old work is never dispatched automatically.

The application store holds studies and memberships, archive state, immutable evidence and configurations, approach records, receipts, model associations, run associations, the outbox and export requests.

## Dependencies and tests

Dependencies are pinned by exact hash in `requirements.lock` and inventoried with origin and licence in `dependency-pins.json`; see `provenance.md`. Installation is offline and hash-enforced (`--no-index --require-hashes`).

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=application/src python -m pytest application/tests -q -p no:cacheprovider
```

Tests use fresh, isolated stores outside the source tree. Tests marked as live need a running local installation and act only on its own synthetic studies. Never inspect a live SQLite store from the host while its container is writing; run queries inside the container. Passing tests are not scientific or human acceptance.
