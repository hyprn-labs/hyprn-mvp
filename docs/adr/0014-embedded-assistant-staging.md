# 0014 — Usable staging with the embedded Assistant

Date: 2026-10-20

Status: Accepted from the product owner's explicit implementation instruction.

## Decision

The first usable staging application includes the embedded Assistant, scientific
authoring, restricted execution, joint sampling, surrogate validation and answer
exploration. A read-only demonstration remains an internal checkpoint, not the
delivery outcome.

Remove external MCP and ChatGPT connection functionality. Preserve the shared
agent tools, delegated API authority, attribution, operation receipts and runtime
checks that the embedded Assistant uses. Cloudflare Access email PIN and Tunnel
remain; Managed OAuth for external tools is no longer required.

Initialize a fresh PostgreSQL installation. The owner authorizes discarding the
current application demo data, so transferring SQLite records is out of scope.
This is not permission to reset data on routine deployment or discard unrelated
installations, secrets or fixtures. New staging records retain the normal
immutability, version and recovery guarantees.

Keep one application process and one execution dispatcher initially, with bounded
worker concurrency. Replica scaling requires durable coordination and accounting
before activation. Worker attestation must cover the actual staging runtime.

Keep product code and portable lifecycle operations in the product repository;
keep infrastructure, identities, secret delivery and deployment operations in the
platform repository. Staging branch updates deploy checked immutable artifacts.
Infrastructure settings, resource costs and cloud mutations still require the
exact reviewed operational approval described in platform AGENTS.md.

## Supersession

This supersedes ADR-0013's MCP/ChatGPT and Managed OAuth requirements, its
read-only delivery boundary, and deferral of the embedded Assistant. PostgreSQL,
stable actor identities, private study permissions, deployment hostnames, branch
deployment intent and security boundaries remain.

## Acceptance

Two admitted users remain isolated. A fresh study can be authored and executed
through the embedded Assistant; joint predictions pass the existing accuracy
checks and sliders use saved exact values or validated estimates without model
reruns. A second branch deployment, process restart and recovery exercise preserve
the new records. Automated evidence, human acceptance and production qualification
are reported separately.
