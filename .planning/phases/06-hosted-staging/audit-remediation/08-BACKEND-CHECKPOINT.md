# Bounded provider documents and Assistant recovery

Owner: backend executor. Parent owns UI, release integration, deployment and live resume.
No live provider mutation, staging data edit, model run or new dependency in this task.

## Delivered behavior

- Built-in provider tool-result document/image base64 content is decoded with strict
  validation and replaced in retained history by media type, decoded byte length,
  SHA-256 and exact provider event reference. Provider-owned bytes remain at the
  provider; this is retrieval metadata, never a verified scientific excerpt.
- Ordinary retained events remain limited to 1 MiB. Custom tool arguments/results,
  fetched text and messages are never silently truncated or attachment-projected.
  Decoded attachment totals are bounded to 32 MiB per event. Event-list GET pages
  shrink from 100 to one when the 8 MiB normal response cap is reached; only the
  one-event GET can use the bounded 48 MiB attachment response allowance. Total
  history admission stays at 10,000 events and page attempts are bounded.
- History callbacks receive the compact records, releasing the raw PDF payloads
  between pages instead of retaining every base64 string in the pump.
- Explicit Resume can recover the existing `provider_response_too_large` turn and
  application-interrupted turns. After unread history and pending tools reconcile,
  an idle provider receives one correlated continuation request. Durable intent,
  exact echoed-content lookup and accepted continuation receipts prevent automatic
  resends on uncertain delivery. Already accepted tools and the original message
  are not replayed. Old idle events cannot falsely finish the resumed turn.
- An accepted continuation consumes its preceding interruption evidence. A later
  unrelated local error does not re-wake work using a stale interrupt receipt.
- Stop locates its new interrupt receipt from that receipt's creation timestamp,
  bypassing unread old oversized attachments. Actor access, current allowance,
  pending unknown-write refusal, exact tool results and evidence receipt rules stay.

No schema, OpenAPI, managed agent definition, numerical image, sampling, surrogate
or accuracy-check change. New local event kinds use the existing immutable event
journal and indexed reference fields; no database migration is required.

## Commits and verification

Implementation commits: `f1b5a46e`, `7a32ded4`, `1d75e98d`, `93cce42e`, `059fd57e`.
Final tested implementation is `059fd57e`. Later delta is this checkpoint and a
line wrap in the transport signature, verified to have an identical Python AST.

Pinned check command (existing host data/tool roots supplied externally):

    ./hyprn-mvp dev check assistant-bridge

- First regression run: 206 passed / 1 failed. The test supplied the same Python
  dictionary twice; deepcopy retained that alias, so replacing its source made the
  second occurrence skip aggregate counting. Independent block copies fix this and
  the test now protects the total even for non-JSON in-memory callers.
- Intermediate committed checks: 208 passed (aggregate and Stop fix); 209 passed
  (10,000-event bound); 209 passed (compact history callback). Each later run was
  required by the subsequent source change; these are not claimed as final coverage.
- Final committed-tree acceptance: **210 passed, 36.87 s**, command exit 0 and scoped
  cleanup exit 0. Log: `/private/tmp/hyprn-assistant-attachments-final-acceptance.log`.
  Regression coverage includes
  a 6.37 MB encoded PDF, corrupt base64, aggregate limits, unchanged custom content,
  bounded paging/cursor retention, public Resume and delivery uncertainty, no replay
  of an accepted evidence write, old-interrupt consumption and public Stop recovery.
- `git diff --check` on owned changes passed. Existing evidence-receipt tests exercise
  exact fetched text and conservative non-text evidence classification.

Private logs: `/private/tmp/hyprn-assistant-attachments-*.log`. Test scopes are
runner-created, isolated from user stores, with cleanup exit recorded by the runner.
Full qualification and real cloud/provider behavior remain parent-owned; synthetic
transport tests do not establish successful staging resumption.
