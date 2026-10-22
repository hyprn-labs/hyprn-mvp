# Evidence excerpt and explanation reader

User-authorized follow-up, 2026-10-17. Commits: `7f6af6d` (reader, authoring,
content validation and agent guidance), `db1351f` (spacing/specimen), `e4b3667`
(narrow layout and overlap regression). Existing page layouts are retained.

## Delivered behavior

- One bordered `View evidence (n)` button in a shared, left-aligned action row.
- A 360 px contextual reader uses the available viewport height, with a quiet
  header, close icon and one scrolling body. Narrow screens stack it below the
  complete main content. Source records are separated by whitespace and hairlines.
- Exact authored excerpts, source references and page/location are separate from
  explanations. Record details and downloads remain secondary. The design-system
  component, tokens, specimens and ownership guards enforce the shared recipes.
- The owner helper accepts structured evidence content; the public API stores
  its versioned serialization inside the existing immutable `content` string.
  Create/revise validate four nonempty text fields and reject malformed marked
  content. No record envelope, historical closure or worker attestation changed.
- The installed HYPRN skill resolves to the updated repository skill. It requires
  inspected verbatim text, an actual locator, separate interpretation and saved
  read-back. Legacy prose is never guessed into a quotation or rewritten.

This is author-transcribed source material, not authenticated document retrieval.
The original-source document service remains deferred. Existing records and
historical evidence pins are unchanged.

## Evidence and source identity

Logs, reports, screenshots, source archives and refresh manifests are in
`/private/tmp/hyprn-evidence-reader`. Every command uses
`./hyprn-mvp dev check <group>` with fixture-created scratch stores. Log
`check_storage` entries identify retained reports after automatic scope release.

The isolated evidence tree is `7f6af6d` plus the exact evidence-only changes in
`db1351f` and `e4b3667`. Concurrent calculation implementation `c33a4a4` was
committed between those follow-ups; it was preserved and separately included in
the full-tree integration checks. Source hashes are in `ui-manifest.json`.

| Source / group | Result | Log |
|---|---|---|
| `7f6af6d` / ae-public | 41 pass, 7 deselected | committed-public.log |
| `7f6af6d` / ae-evidence | 54 pass | store.log |
| Evidence tree / ae-contracts | 78 pass | contracts.log |
| Evidence tree / agent-tools | 271 pass | agent.log |
| Evidence tree / local-api-client | 17 pass | client.log |
| Final evidence tree / combined-static | 9 stages pass | final-layout-static.log |
| Final evidence tree / ae-ui-evidence | 13 pass, 0 fail | final-layout-browser.log |
| Full `e4b3667` / combined-static | 9 stages pass | integrated-static.log |
| Full `e4b3667` / locality-contracts | 164 pass | integrated-locality-corrected.log |
| Full `e4b3667` / ae-ui-evidence | 13 pass, 0 fail | integrated-browser.log |
| Final evidence tree / ui-reading | 20 pass, 12 fail | final-reading.log |
| Unchanged `d79cebf` / ui-reading | Same 20 pass, same 12 failing names | baseline-reading.log |

Browser coverage exercises the actual HTTP/UI/API/store journey for structured
create, missing-location refusal, read, revision and exact original history.
It also checks grouped sources, unavailable content, access loss, editor recovery,
downloads, both themes, desktop and narrow widths. The modeling transport is a
declared fixture double; these tests do not qualify scientific execution.

## Failures and corrections

- Initial browser runs: old validation-text expectation, pagination hiding a newly
  created fixture record, and a test reading before save completion. Corrected
  expectations/pagination/wait; final 13/13 passes.
- Browser inspection found a shared narrow media rule accidentally setting the
  main column to viewport height. Split the rules and added an overflow/position
  regression. Rebuilt and rechecked the real app at 720 px.
- First broad reading run: 19/32 pass, 13 fail. One missing specimen registration
  was ours and fixed. The other failures are obsolete run-navigation expectations.
- ae-generated: 5 pass, 2 fail (`ResultSource` and `ModifiedRunSeedRead6` expected
  shapes). Both failures reproduced on unchanged parent `d79cebf`; no generated
  API envelope was changed by this task. Logs: generated.log,
  baseline-generated.log.
- A shared-tree build encountered concurrent incomplete calculation edits;
  isolated builds passed. Initial module-boundary codec allowlist omission was
  fixed; full integrated locality checks pass.
- One permission-review attempt timed out; its retry succeeded. An attempted
  `factorization-locality` group name was refused by the runner; the registered
  `locality-contracts` group passed. No failed command is counted as verification.

## Live verification and deployment

The user's reference Claims/source panel was inspected directly for its proportions,
quiet header and source hierarchy. No reference application code or assets were copied.
HYPRN's live configuration page was refreshed and visually inspected at desktop
and 720 px. Its existing notes are accurately labelled as notes. The structured
reader was also captured through the real isolated application test fixture.

Screenshots: `live-desktop.png`, `live-narrow.png`, `structured-evidence.png`.
The UI refresh checked installation UUID and the previous index hash, kept a full
rollback copy, copied verified assets and atomically replaced the index. The final
index hash is `fd3559b0b240651fbdb02536bbb03f67cbc6f2362567053db146da4e1f64e878`.
No live authoring records, calculations or backend processes were changed.

The live UI uses the evidence-only source composition above, compatible with its
existing runtime. Concurrent calculation API deployment belongs to its task.
New server-side marked-content validation is tested but is not installed by this
UI-only refresh. The UI and owner helper already emit the compatible format.

Human visual acceptance, source-content curation and full release qualification
remain separate. `baseline-comparison.json` confirms identical broad-navigation
failures. The new reader specimen passes after its registration correction.

Completed fixture scopes were released through the identity-checked storage
cleanup, and the three isolated source trees were removed. `cleanup.json` retains
the released identities. Source archives, logs, screenshots and live UI rollback
copies remain outside the repository. No unrelated scopes or stores were touched.
