# Assistant creation and shared conversation layout

Runtime source: `415a5555b4195304165c7950ac32bebfb2984ca7`.
Target: existing private staging; continuing owner deployment authorization.

## Delivered source

Shared conversation prose renders safe Markdown, compact role cards and scrollable
message tables. Home navigation precedes the conversation context. Create/Switch
forms replace history and composer. Creation saves the human's question through
the brief API; the opt-in autonomous action then uses the existing Assistant API.
Stable command identifiers preserve retry identity. Shared fieldset spacing and
canvas minimum height apply across screens. Compact exploration omits fixed-input
captions; those values remain accessible through the domain/model readers.

The software-notices product link and standalone served file are removed. Required
licence copies remain embedded in delivered JavaScript and native artifacts. No
backend notice record or endpoint existed to delete. No new dependency was added.

The inspected coolant answer deliberately fixed specific heat at 4.2 while varying
load and flow. Its brief also requests 3.8 in the adverse scenario. Thus the missing
slider reflects incomplete exploration coverage, not a failed numerical control.
The answer already disclosed that exclusion. Existing immutable scientific records
are preserved. The generic engineering playbook and /hyprn now require matching
scenario-changing independent inputs to exploration dimensions or explicit groups.

## Focused evidence

- `./hyprn-mvp dev check ui-navigation`: 28 passed, no failures/skips on `415a5555`.
- `./hyprn-mvp dev check agent-tools`: 321 passed, same product source before commit.
- Design guard, token freshness, UI contract and production build passed.
- Design tooling: 18 passed. Design smoke: 117 renders passed (existing key warnings).
- Initial browser checks exposed two obsolete notices assertions and one incorrect
  Light-mode test locator; corrected before the final passing run.
- Actual built image: seven UI assets; embedded browser licence text verified after
  minification. Native clean build: 20,868 files; installed image inventory verified.
- Ten focused recovery/activation helper checks passed before deployment.

Private evidence: `/private/tmp/hyprn-assistant-navigation-final.log`,
`/private/tmp/hyprn-assistant-agent-tools.log`, design/contract/tooling/smoke/build
logs under the same prefix, and `/private/tmp/hyprn-staging-assistant-ui/`.

## Deployment and remaining work

Release `10a81dacc2bf1a2497c3c2e193533646bd685eab5867accba0f314215c2e08bf`;
configuration `6bc04fdead30fdb4561e04b38b69c6a0c5cd4a71d9191f78184574d87400c543`;
desired sequence 15. Platform runtime remains `3488a518`; the previously tested
operator loader correction handles staging. Provider agent instructions are repinned
to the new playbook with unchanged tools, environment permissions and shared budget.

Deployment initially stopped before installation because the stage manifest omitted
the already reviewed Assistant plan. Read-only reconciliation found exactly that
missing file, unchanged old runtime identity/journal and no recovery archive. The
continuation preserves the failure evidence, installs only the exact pinned missing
file and resumes the original recovery. No database initialization is repeated.

Live browser verification and ongoing activation are pending at this checkpoint.
Full release qualification, second-user acceptance and automatic deployment from
GitHub remain separate obligations. Unrelated working-tree changes are preserved.
