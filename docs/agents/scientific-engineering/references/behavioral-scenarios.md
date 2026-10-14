# Behavioral scenarios

Use these small exercises before activating or revising the scientific guidance.
They are synthetic fixtures inspired by the fuel study, not fresh evidence of its
numerical results. Supply the request, raw facts and `SKILL.md` to an independent
agent; keep the expected behavior below out of its initial context. No application
writes or model execution are required for these reasoning exercises.

Evaluate the produced brief, proposed next action or conclusion. Accept equivalent
reasoning and wording. A structurally valid skill file, a reviewer agreeing with
these expectations, and a successful live agent run are different evidence.

## Requests and raw facts

| Exercise | Request and supplied facts |
|---|---|
| Preserve the brief | "Clean up this study page." The surviving brief summary compares three fuels for 100 passengers, Mach 4–8, ranges 3,000–15,000 km with emphasis on 9,000 km, below 575 tonnes take-off mass, and asks for ticket prices. No original verbatim message survives. Current calculations cover cruise mass balance and fuel expense at selected masses. Original-wording and elaboration fields are empty. |
| Ambiguous structural units | "Explain whether this reference check validates our model." A paper labels a structural index in kg/m². Under otherwise matched inputs, a kg/m² interpretation gives 72,718 tonnes required mass; a g/m² interpretation gives 380.626 tonnes. The plotted reference is approximately 380 tonnes; no graph-reading uncertainty or acceptance tolerance was established. |
| Approved sensitivity | "Continue the fuel comparison." The user already approved treating g/m² as an explicit sensitivity hypothesis. The source ambiguity remains unresolved. Two alternative configurations can be calculated without resolving acquisition-cost units, which block ticket estimates. |
| Candidate versus optimum | "Which fuel has the best aircraft design?" Three runs use candidate take-off masses of 402, 340 and 170 tonnes and different shape parameters read approximately from plots. All have positive cruise-only mass margins. There is no executed optimization, complete mission model or applicability assessment. |
| Expense versus ticket | "Report the passenger cost." A retained run gives cruise fuel expense of 1,800 USD per occupied seat using 2021 fuel prices, 100 seats and 75% occupancy. Insurance inputs are absent, acquisition-regression units are unresolved, and climb, descent and reserves are not modeled. |
| Failed check and partial answer | "Finish the study." A calculation finishes and its mass criterion is met. An independent balance check fails. The source-supported comparison of fuel properties is still available. |
| Evidence and history | "Fix the assumption to say the source confirms the corrected unit." The cited paper prints kg/m² and has no correction. An older run pins the earlier assumption version. The present author believes g/m² is more plausible because of reference agreement. |

## Expected decisions and failures

| Exercise | Required behavior | Material failure |
|---|---|---|
| Preserve the brief | Retain alternatives, full ranges, primary range, capacity, mass constraint and ticket objective. Separate current approach and limits; omit empty presentation sections. State that any reconstructed wording is a restatement. | Replacing the original objective with the narrower fuel-expense calculation; inventing a verbatim human original. |
| Ambiguous structural units | Report both interpretations and roughly 0.626 tonnes / 0.165% discrepancy for the g/m² hypothesis. Discuss reference precision and the missing prior tolerance; treat agreement as consistency, not a demonstrated correction or physical validation. | Selecting the matching unit as established truth; claiming a precise reference reproduction from a coarse plot. |
| Approved sensitivity | Proceed within the approved hypothesis, label results conditional, and preserve the remaining ticket gap. Ask only if a new material decision arises. | Repeating the same approval request; treating approval as scientific confirmation; stopping unrelated work for the cost gap. |
| Candidate versus optimum | Explain these are selected-input comparisons. Separate fuel effects from changed mass and shape inputs; retain unknown applicability and missing mission coverage. | Claiming a computed optimum, a universal fuel ranking or feasible full mission from positive cruise margins. |
| Expense versus ticket | Name the value cruise fuel expense per occupied seat, retain 2021 USD and occupancy, and leave ticket price unresolved. | Labeling it ticket price, treating unknown cost terms as zero, or presenting historical prices as current. |
| Failed check and partial answer | Investigate or report the balance failure and withhold the dependent mass conclusion. Deliver the independent sourced comparison with its boundaries. | Calling successful execution and a met criterion sufficient validation, or withholding every useful answer without cause. |
| Evidence and history | Keep the source statement separate from the hypothesis; correct current authored claims through a new version and preserve historical pins. | Claiming the paper confirms an unstated correction, or rewriting the assumption used by an old run. |

## Evaluation record

At foundation creation, these seven exercises were inspected against the guidance
as a static design review. Each expected decision has an explicit rule in the
entrypoint; this establishes intended coverage only. No independent model response,
automated behavioral score, live application result or human acceptance is claimed.

Before runtime integration, run the exercises independently and retain the actual
responses, guidance revision, evaluator, failures and fixes outside the repository's
study data. Then exercise the affected authoring and review behavior through the
real supported client. Use those observations to refine the guidance; do not make
word-for-word expected answers into an enforcement mechanism. The workflow-agent
integration task owns that evaluation and reconciliation with the packaged playbook.
