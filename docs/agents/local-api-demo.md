# Owner-operated local API workflow

This helper lets a local coding agent use an ordinary user's authorized session
for the engineering workflow. The user remains the recorded actor. It is a local
demonstration aid, not delegated-agent authentication or a supported MCP client.

Start one persistent process with the running application's exact loopback IP
origin and the existing owner's password file:

```sh
python3 -B deployment/tools/local_api.py \
  --origin "$APP_ORIGIN" --username owner --password-file "$OWNER_PASSWORD_FILE"
```

The password file must be owned by the current user with mode `0600`. Its path is
explicit; the helper does not create a credential file or discover an installation.
Alternatively omit `--password-file` and send the password as the first line over
a private stdin pipe, never a terminal or a tool call containing the secret.
Use the same process throughout the work; cookies and CSRF values live only in
memory. Successful login emits `{"ready":true}`. Close stdin to end the client.
The server's normal session expiry and authorization rules still apply.

Send one JSON object per line and wait for its response before sending the next.
Ordinary requests accept `method`, `path` and optional `body`; `method` defaults to `GET`.
Responses are `{"status":200,"body":...}` with the unchanged public API envelope,
or `{"error":"..."}` for a local/transport failure. Headers and credentials are
never printed. Supply request fields from `contracts/hyprn-mvp.openapi.yaml`.

```json
{"method":"GET","path":"/api/1/studies"}
```

Before authoring, read `/api/1/capabilities` and the selected study's
`/api/1/studies/{study_id}/unit-catalog`. Consult the current public request/response
schemas; for example, a configuration read wraps its saved record in
`data.configuration`, rather than putting the revision ID directly under `data`.

For pending runs, the client also accepts a read-only shortcut:

```json
{"operation":"run_status","study_id":"<study UUID>","run_ids":["<run UUID>"]}
```

It sends one `GET /api/1/studies/{study_id}/run-status?run_id=...` for 1–20 distinct
run IDs, preserving the normal `{status, body}` response. The Python method is
`client.run_status(study_id, run_ids)`. Split larger sets into batches of at most 20;
retain only pending IDs for later polls. Back off when nothing changes (for example,
5, 10, 20, then 30 seconds) and fetch full records for completed runs or diagnosis.
This shortcut adds no scheduler, automatic retry, new endpoint or change to execution.
Read stale readiness as an observation about the executor, not a failed accepted run.

After creating a study, use its returned ID for reads and edits in this same
process. Every request stays on the configured origin under `/api/1/`; no proxy,
redirect, automatic login renewal or mutation retry is used. Request and response
bodies are limited to 4 MiB; each socket operation has a 45-second timeout
(`--timeout` accepts up to 120 seconds). The helper supports GET, POST, PUT and
PATCH. The authorized scientific workflow excludes deletion, archive/restore,
membership changes and credential administration.

Keep every command ID before submitting its request. If a mutation times out,
disconnects, or gives an uncertain reply, read its existing receipt with
`GET /api/1/commands/{command_id}` or
`GET /api/1/studies/{study_id}/commands/{command_id}` as specified by the operation.
Follow the server's receipt outcome and run status; never blindly repeat a launch.
An HTTP error is returned for inspection, not treated as permission to retry.

Read the brief, record its context and legitimate evidence, and develop the
Modeling approach before authoring component source and the model. Save explicit
configurations with units and input provenance, preview them, submit real runs,
inspect their errors/results, revise and run again when scientifically needed.
Read current revisions before editing. Keep saved versions and recorded runs
immutable. Readiness or execution success alone does not establish a scientifically
valid answer. Use the scientific writing and interpretation rules in
`docs/agents/playbook.md`; tool names there describe capabilities, while this
demonstration calls the existing public endpoints directly. Save case and study answers through the current answer endpoints, citing exact
approach, case, configuration, run, evidence and case-answer versions as applicable.
Separate observations from interpretation and keep unanswered deliverables explicit.
Then conclude in chat with actual results, assumptions, sources and limitations,
and inspect the saved reader journey in the UI when it is part of the request and
accessible. API-only work requires record readback, not browser inspection. Do not
substitute seeded models or results for the authoring loop.
