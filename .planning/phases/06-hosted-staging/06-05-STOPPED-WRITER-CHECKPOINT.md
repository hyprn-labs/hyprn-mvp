# Stopped-writer verification

Scoped prerequisite for the coordinated recovery batch, not completion of 06-05.
Source: `226151b`. Parent acceptance ran on that committed source.

`Lifecycle.assert_stopped()` checks the installation identity, exact closed
browser/scientific admission, absence of the native process, and actual Docker
inspection of every container in the installation project. One-off database
operations are included. Unknown service/image identities, restart policies,
missing observations and running/paused/restarting containers refuse backup.
The backup owner calls this while retaining deployment, product and native locks;
the predicate deliberately does not reacquire the native executor lock. Product
stop now verifies this postcondition before returning success.

| Registered group | Passed | Failed | Test seconds |
|---|---:|---:|---:|
| cloud-execution-config | 16 | 0 | 0.124 |
| hosted-lifecycle | 20 | 0 | 8.993 |

Commands: `./hyprn-mvp dev check cloud-execution-config` and
`./hyprn-mvp dev check hosted-lifecycle`, after loading the development path
configuration and the approved 16 GiB test build-cache budget. Both exited 0.
The first unprivileged invocation failed before collection because the sandbox
could not write the pinned tool cache; the authorized scoped invocation succeeded.
Development runs before commit also passed 16 and 20 tests.

The added Docker test creates one isolated, constrained container with no network,
secrets or mounted stores. It verifies actual created/running/stopped states and
removes that exact container in its finally block. Protected control-file and
native-process observations are explicit doubles in that test. Existing hosted
lifecycle tests exercise real isolated PostgreSQL. These checks do not prove the
whole Linux/GCE fence, coherent managed database backup, restore, or cloud access.
No cloud resource, live installation or provider session was changed.

Parent owns integration with platform backup/reconciliation and final installed
qualification. Rebuild payloads before using this source in a published release.
