# Explicit clean staging restart

The owner superseded retained-data migration on 2026-10-22: empty application
PostgreSQL and begin new studies. A separate explicit answer authorizes resetting
user spending for this one restart. Subsequent budgets remain cumulative USD20/user.

The original sequence18 migration refused and rolled back to schema9. Its receipt
and completed consistent backup remain retained. A populated local conversation
regression also found that migration0011 lacks migration-role read authority for
retained Assistant events. That retained-data upgrade path is deferred by the
owner's clean-start decision; no claim of successful migration is made. The test
and failing evidence are retained privately, not shipped as a silently passing test.

`deployment/clear_application_store.py` is an operator-only transaction, with no
startup/UI/agent invocation. It verifies exact old schema checksums, store identity,
migration role, exclusive writer locks and public-object ownership. Only then does
it replace owned schema objects and initialize the tested schema. Exceptions roll
back the transaction. The host wrapper separately verifies stopped services and
backup identity, retains the failed journal and uses temporary credential delivery.
Roles, grants, infrastructure, secrets and linked model/execution stores are retained.
The fresh application has no associations to old scientific records.

Verification: `./hyprn-mvp dev check hosted-postgres`,48 passed in45.59s, runner
46.03s, storage6838a6b5-d8a7-453d-a1d0-959290e8a713, scopeac0f70aa. Wrong-store
refusal, rollback after an initialization error, empty initialization and unchanged
roles are exercised against real isolated PostgreSQL. Initial reset check failed
before execution because the helper imported an unused driver; corrected to the
already pinned pg8000/qmark driver, with no new dependency. Scope cleanup passed.

The live atomic reset completed on schema13; its exact receipt and the consistent
backup remain retained. Sequence18 qualification passed, but app startup correctly
refused five provider sessions whose application associations were cleared.
Sequence19 classifies all10 idle/terminated retired sessions (1899 provider cents)
in the existing startup continuity record. These are reconciliation evidence only;
the new cumulative per-user account ledger starts at zero. No provider sessions or
new studies are created by this configuration transition.

The reset wrapper also initially placed reset metadata in the strict deployment
journal. The continuation preserved that journal verbatim in its recovery archive,
then restored the supported shape with migration=null; the failed migration is not
reported as completed. Sequence19 host qualification and startup passed. All19 service-network probes
passed (verified database TLS, required routes, and denied metadata/unapproved
network access). The Cloudflare connector and bounded qualification access are
active. Chrome reached the expected email sign-in page; its login had expired. The owner
confirmed signing in on a different browser/device; that does not authenticate
the connected Chrome profile. A second request identifies the exact profile.
Public login, a fresh autonomous study, joint sliders without reruns and ongoing
access promotion remain pending the requested owner sign-in. Private operator packets/receipts are in
audit-remediation-release/deploy and hyprn-staging-reset-continuity;
no credentials or scientific records are committed here. Existing source7cbe3e and
its verified container/native artifacts remain unchanged by this operator/test delta.


Active configuration:020f9b17e769f0a4fdbcc72fa6f19a38598d2c1219ff40d5fe050f7f0916fdc4;
desired sequence19/generation1792708475289042. Release99844b1c and platform492eeb2d
are unchanged. Private continuity policy e6de029283ba456628c05a523879f7d54f93925d211ccc4dfe178cea74a4c393
records exact prior inventory and owner authority. Subsequent configuration changes
must use this active binding, not the sequence18 release-directory binding.

Host after startup:15.45GB available of16.78GB, app101MiB, dispatcher51MiB,
modeling108MiB; no OOM. No evidence supports a RAM upgrade. After the startup/network checks, database activity measured27.88 transactions/s
(243.29 returned tuples/s) versus359.98/s (37702.34 returned tuples/s) in the old
installation. These
are different data/workload conditions after the explicit reset, not a controlled
performance comparison or proof of end-to-end study speed. A fresh study and
steady activity measurement are still required. Full release qualification,
matched medium/high effort evaluation and human acceptance remain open.
