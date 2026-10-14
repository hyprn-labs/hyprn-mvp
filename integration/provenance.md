# Execution integration provenance

`hyprn_mvp_integration` (bundle reading, launcher, AiiDA calculation and parser, results, scalar worker and contract fixtures) is independently authored against the public Modeling Backend Contract and the public AiiDA plugin API. No WhatsOpt application, template or native adapter code is copied into it. The launcher's selector, drain and cleanup pattern closes and waits for the client before killing a process, so output flooding cannot stall it.

## Worker image

The numerical engine builds from the digest-pinned Python base, the exact managed interpreter and `integration/worker-requirements.lock`. Seventeen distributions install from hashed official wheels. Three source distributions use the owner-approved, packaging-only Flit transformations in `upstream/engine-packaging/`, with their archive and payload hashes in `deployment/locks/engine-sources.json`. Each source wheel is built twice offline and its runtime files must remain byte-identical. The restricted worker derives from the recorded engine build identity and adds only the independent worker entrypoint. Native modeling-service source and notices stay in the modeling service artifact.

The worker runs CPython 3.12.15 with OpenMDAO 3.45.1; the trusted host runner uses CPython 3.12.15 (the interpreter `./hyprn-mvp` provisions, pinned in `deployment/locks/tools.json`) with AiiDA 2.9.3. The interpreter version actually measured in each image is recorded in the runtime identity. The full numerical and AiiDA licence and distribution metadata are included in every numerical execution bundle. Placeholder notices exist only in pure test fixtures and never authorize a real runtime.

## Native environment

The host runner's virtual environment is built by copying only the declared dependency closure from existing installed distributions, never by a package manager, download, replacement dependency or network resolution. The reviewed AiiDA wheel hash is checked first, then every copied package file is verified against its installed `RECORD` SHA-256. Upstream project URLs, licences, versions and the hashes of every copied file are kept in `locks/native-installed.json`; metadata and the actual licence and notice files are kept under `licenses/native/`. Console wrappers and bytecode are excluded. Independently authored plugin metadata registers only the `hyprn_mvp.scalar` calculation entry point, and source paths reference only this repository's application and integration packages.

The closure holds 89 native, test and transport distributions. The 20 runtime distributions of the numerical image are inspected without network access or candidate imports; their exact metadata, licences and version inventory join the hashed worker lock. The retained comparison image additionally contains pip, a build tool excluded from the rebuilt engine. `selected.json` binds all of these bytes, and its SHA-256 is part of the attested runtime identity. Every launch compares the selected lock and licence bytes as well as the expected bundle digest; rehashing a modified bundle never authorizes changed runtime dependencies. A change to deployment sources or the package inventory requires a new containment attestation before any numerical launch.

## AiiDA behaviour relied on

The calculation uses AiiDA's `instantiate_process` and `Runner.run_get_node(process)` with `communicator=None`. Tests on a fresh profile cover node storage, continuation and response fault windows. They prove that at most one matching stored process is adopted and that a launch is never repeated; they do not claim general exactly-once execution. A stored but never continued node stays `created`. Full cancellation and recovery are future work.

## References

- OpenMDAO explicit components: https://openmdao.org/newdocs/versions/latest/features/core_features/working_with_components/explicit_component.html
- OpenMDAO execution order: https://openmdao.org/newdocs/versions/latest/features/core_features/working_with_groups/set_order.html
- AiiDA engine internals: https://aiida.readthedocs.io/projects/aiida-core/en/stable/internals/engine.html
- AiiDA calculations: https://aiida.readthedocs.io/projects/aiida-core/en/stable/topics/calculations/usage.html
