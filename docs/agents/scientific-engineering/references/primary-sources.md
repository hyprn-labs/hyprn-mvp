# Primary-source basis

Reviewed 15 October 2026. These sources inform the scientific practices in this skill;
they do not prescribe HYPRN's schema or certify a study. The primitive mapping,
execution restrictions and version rules come from the repository contracts and
implemented client capabilities.

| Source | Relevant material | Use in this skill |
|---|---|---|
| [NASA-STD-7009B, Standard for Models and Simulations, 5 March 2024](https://standards.nasa.gov/sites/default/files/standards/NASA/B/1/NASA-STD-7009B-Final-3-5-2024.pdf) ([standard record](https://standards.nasa.gov/standard/nasa/nasa-std-7009)) | §§4.2.3, 4.2.5; §§4.3.1, 4.3.3, 4.3.5–4.3.6, 4.3.8; appendices D–E | Relate credibility work to intended use and decision consequence. Distinguish implementation/solution verification, validation, sensitivity, uncertainty and reporting. HYPRN does not claim NASA compliance or reproduce NASA approval processes. |
| [NASA/NPARC Alliance, Verification Assessment](https://www.grc.nasa.gov/www/wind/valid/tutorial/verassess.html) | Verification activities and numerical-error assessment | Choose checks that can expose implementation and solution errors. Agreement between codes alone does not establish physical validity. Adapt this CFD-oriented guidance to the actual numerical method. |
| [NASA/NPARC Alliance, Validation Assessment](https://www.grc.nasa.gov/www/wind/valid/tutorial/valassess.html) | Validation strategy, experiments and comparisons | Judge physical representation against relevant observations and their uncertainty within an identified domain. Distinguish calibration and implementation checks from independent validation. |
| [NASA/NPARC Alliance, Examining Spatial (Grid) Convergence](https://www.grc.nasa.gov/www/wind/valid/tutorial/spatconv.html) | Refinement, observed order and extrapolation assumptions | Examine discretization error when the method actually uses a mesh. Small successive differences alone are insufficient. This does not create a mesh/CFD capability in HYPRN. |
| [BIPM/JCGM 100:2008, Guide to the expression of uncertainty in measurement](https://www.bipm.org/documents/20126/2071204/JCGM_100_2008_E.pdf) ([publication collection](https://www.bipm.org/en/web/guest/publications/guides)) | §§4–5, 7–8: input uncertainties, propagation including correlations, reporting | Preserve uncertainty meaning, dependence and appropriate precision. Measurement-uncertainty propagation does not automatically quantify model-form error, extrapolation or unknown omissions. |

Use the sources for their stated scope. Do not force a CFD verification procedure
onto a closed-form scalar model, apply linear uncertainty propagation without checking
its adequacy, or turn an unsupported probability assumption into a confidence claim.
Project-specific standards and experimental evidence still govern the actual domain.
