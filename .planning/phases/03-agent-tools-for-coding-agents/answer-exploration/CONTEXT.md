# Answer exploration — execution context

Date: 2026-10-15. Owner: main agent. Status: implementation authorized by the user; not implemented or scientifically validated. This is a scoped delivery addition to Phase 3, not a replan of the embedded assistant or permission to execute the entire old Phase 3 plan. Preserve the unrelated ROADMAP edit and other chats' work. The latest user request below supersedes earlier visualization proposals and the HTML prototype where they differ.

## User outcome and authority

An engineer (Guerric first) opens the fuel study, selects categorical choices, slides every free numerical input and sees calculated/estimated intermediate and final quantities on the existing graph. Sample settings owns additional original-model calculations, sample ranges, budgets and accuracy targets. The bottom interpretation addresses: **Which fuel is preferable, under which cruise conditions, and why?**

The user explicitly requested building this implementation plan and sending it to the `main agent` chat for execution. First environment: existing local HYPRN on the owner's Mac. First demonstration: a real public-API-to-UI fuel slice. Usable customer slice: all free inputs, categorical mapping, honest estimates, additional calculations/recovery and the cleaned answer UI. Qualified release and human scientific acceptance remain separate.

## Locked UI decisions

1. Study question in a box; Explore the answer in the next box; Interpretation and still to answer in the final box.
2. Exploration shows categorical selectors, Sample settings at the graph's top right, the canonical graph with input sliders and output curves, and Open model at the **bottom of the exploration box**.
3. Remove Curves against entirely. Proposed resolution: the input last focused/dragged determines the curve axis; each plot retains the input's short label/unit so it is interpretable. All other selected values stay fixed for that slice. This is a routine implementation decision, not a user-approved extra control.
4. Every free numerical input is slidable with exact numeric entry, including fuel-property inputs where the category supplies an initial assignment. Connected inputs are derived and read-only. Integer-valued semantic inputs such as passenger count use declared integer steps. Do not restrict completion to the mockup's four inputs or a top-K selection.
5. All calculation actions are **inside Sample settings**: prepare/refine estimates and calculate the current combination. No Calculate button below the graph.
6. Remove supporting-results lists and reasoning/methods from the answer page. Methods and their editing live on the Model page. Remove the metadata prose, Saved interpretation labels, Reset inputs toolbar, View combination button, duplicate accuracy buttons, helper paragraphs, mockup variant controls, and decorative text. Keep only labels/units, Estimated/Calculated/unavailable distinctions, necessary diagnostics and contextual details needed to check a value.
7. Scientific sources and answer basis are not deleted: retain their records and access through compact value/claim details and existing run/model homes. Removing verbose presentation does not remove evidence, qualifications or open questions.

## Scientific and numerical intent

- The user explicitly reaffirmed that the entire answer visualization is generic;
  fuel is only the real evaluation study. Product controls, categories, labels,
  units, curves and bindings derive from public model metadata and declared
  exploration settings. Fuel-specific assignments, ranges and co-varying input
  pairs are study data, never application branches, constants or inferred names.
- Use bounded space-filling sampling and validated surrogates instead of exhaustive grids by default. Reuse OpenMDAO, SciPy/NumPy and AiiDA. Do not rewrite physics in JavaScript or copy prototype arithmetic.
- Categories may select different exact model versions, or different complete value assignments on the same model. No interpolation across qualitative categories; unsupported combinations are explicit.
- Initial ranges, categorical choices and tolerances are a study-design proposal with provenance/rationale, not hidden defaults. Populate them through the public API. Ordinary slide movement never saves a model/configuration/answer or launches a run.
- Calculated means original-model output, not physically proven truth. Estimated means surrogate output. Missing/failed results are not zero; surrogate fit error is distinct from physical uncertainty, applicability and criterion outcome.
- Interpretations retain their explicit supporting configurations/runs and assumptions. Moving sliders does not silently rewrite claims. Essential baseline conditions may be concise prose, but never an unexplained metadata banner.

## First fuel source and research

The user selected study `50e423fd-a709-4e21-9381-0b09022b4115`, model family `3f4d85eb-41bd-484f-a7a7-91729ddbf4e7` on the existing local installation. Resolve the exact **answer-linked model version/configurations** at execution time; the supplied model-page URL points at a family/draft context, not an execution pin. Do not switch to the later timed fuel study just because it is newer. Test copies live only in isolated fixtures; authoring records are preserved.

Observed components: Cruise aerodynamics and propulsion → Breguet cruise fuel → Aircraft mass budget and fuel expense. Fuel mass and lift-to-drag also feed the final component. Fuel categories: kerosene, liquid methane, liquid hydrogen. The existing common comparison uses Mach 6, 9,000 km, 574 t, tau 0.18 and 100 occupied seats. Inspect all other assignments/source units rather than inventing them. Structural units remain provisional; cruise screening does not establish full-mission feasibility or ticket price.

Research: `docs/research/fuel-visualization/recommendation.md` and `frontend-libraries.md`. The conversation's HTML mockup is a visual reference only; synthetic data and fake validation must never enter a production seed. Browser verification of its final surrogate flow was incomplete. Runtime compatibility of current documentation with the pinned version must be proved in Task 3.V1.

Official references checked during discussion:
- https://openmdao.org/newdocs/versions/latest/features/building_blocks/components/metamodelunstructured_comp.html
- https://openmdao.org/newdocs/versions/latest/features/building_blocks/surrogates/kriging.html
- https://openmdao.org/newdocs/versions/latest/features/building_blocks/components/metamodelstructured_comp.html
- https://openmdao.org/newdocs/versions/latest/features/building_blocks/drivers/doe_driver.html
- https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.qmc.LatinHypercube.html

These establish available upstream facilities, not qualification of the installed HYPRN runtime. Direct fetch of tagged 3.45.1 source failed during plan preparation; inspect the pinned installed source in the attested environment instead.
