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

The inspected coolant answer fixed specific heat at 4.2 while varying load and
flow because the earlier launch instruction explicitly requested that restriction,
with 3.8 handled in a separate comparison. The Assistant followed that instruction;
this was an orchestration scope choice, not a failed numerical control or an
Assistant mistake. The brief covers both scenarios and the answer disclosed the
exploration exclusion. Existing immutable scientific records
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

Live Chrome verification passed: login, Start/Switch forms hiding history/composer,
question retained in the brief, Off/On switch and one admitted autonomous turn.
The shared prose renders existing Markdown tables/lists without changing messages.
The brief editor shows 12 px after fieldset legends and 16 px internal gaps. The
home canvas reaches the dock height. Existing joint slider changes returned
11.717 K and -1.994 kW estimates; its 27 runs, 26 configurations, three analysis
versions and one answer version were unchanged. No existing model rerun occurred.

Containment, startup and all 19 network probes passed. Named-user access is promoted
to ongoing staging. No database migration, initialization or secret reissue occurred.
The new autonomous verification study completed its two comparison runs and is
sampling. Its saved settings were read in Chrome: load 12–15 kW, mass flow
0.25–0.30 kg/s, specific heat 3.8–4.2 kJ/(kg*K), rise limit fixed at 10 K;
32 training and 12 validation-pool points. Both temperature outputs have pre-set
0.05 K plus 1% relative limits. Its final answer is not yet verified. Do not claim that its full study or
three-input surrogate has passed before its retained results establish that.

The publication hook rejected inherited integration-history terms. A clean staging
publication commit `48ef69a903580ae419afe4c03fa19a8c390b436d`, parented on remote main,
contains the exact reviewed integration tree `ac7860c7`. The hook passed and remote
`staging` was verified. Local integration history remains intact. The delta from
runtime `415a5555` is four documentation files only; unrelated edits were excluded.
Final evidence documentation may follow this publication without changing runtime.

Screenshot: `/private/tmp/hyprn-staging-assistant-ui/assistant-start-study.png`.
Deployment and browser evidence are in that packet's `application-evidence/`.

Full release qualification, second-user acceptance and automatic deployment from
GitHub remain separate obligations. Unrelated working-tree changes are preserved.
