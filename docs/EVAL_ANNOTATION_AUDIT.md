# Development annotation audit — v1 to v2

The first successful live `dev-01` answer cited `usig_2023:p0010`, which directly contains the four-over rule. Version 1 expected only page 1, an earlier overview containing the same rule. The application answer was therefore structurally valid but the development page-coverage annotation produced a false failure.

The original dataset and generator were preserved in private `work/annotation-audit/cases-v1.jsonl` and `make_cases-v1.py`. Existing smoke reports were not overwritten. All 20 development cases were audited against the fixed index's one-based PDF pages. Twelve cases gained relevant supporting pages; no cases, questions, categories, expected statuses, source requirements, setup turns or semantic rubrics changed. The denominator remains 20 cases/23 turns.

- Original dataset SHA-256: `1af41f126e3e06eadda26e85eaa1c0acb72c281f8e492680a5084aca1af28d5d`
- Corrected dataset SHA-256: `176ab7ffe6a865f9534a6e4248426540220a6f3493c5780b864ad43fd3fe13b9`
- Fixed index SHA-256: `4518de9adb0d63f4217eeb52e917671ad802ca78dd6952264aa96cc1f8ac1cee`

| Case | Source | Original accepted pages | Corrected accepted pages | Evidence reason |
|---|---|---|---|---|
| dev-01 | USIG | 1 | 1,10 | Overview and “Number of overs per bowler” both state four; page 10 also qualifies reduced innings |
| dev-02 | USIG | 2 | 2,18 | Overview bouncer rule and detailed dangerous/short-pitched bowling section both state second delivery no-ball |
| dev-03 | USIG | 3 | 3,10,11 | Overview, tie section and continued eliminator/playoff rules support the Super Over outcome |
| dev-04 | USIG | 2 | 2,16,17 | Overview and detailed fielding sections state two outside the circle during Powerplay; pages 2/16 explicitly define first six |
| dev-06 | MCC | 24 | 24,25 | Law 17 defines six valid balls; its continuation discusses an over mistakenly continuing after six valid balls |
| dev-07 | Junior | 7 | 7,29,50 | General permitted batting/bowling table, Under 10 rule 16.3(iv), and quick-reference batting/bowling rows |
| dev-09 | USIG | 2 | 2,16 | Overview and “Substitutes and Runners” both prohibit runners; MCC 38/39 unchanged |
| dev-10 | Junior | 7 | 7,26,50 | General comparison table and quick reference cover both formats; rule 15.3 on 26 supports stage 2's nine-player component |
| dev-12 | USIG | 3 | 3,10,11 | Same playoff provisions as dev-03; setup and follow-up wording unchanged |
| dev-13 | USIG | 2 | 2,16 | Same runner provisions as dev-09; setup/follow-up and MCC 38/39 unchanged |
| dev-14 | Junior | 7 | 7,26,50 | General table, rule 15.3 and quick reference support stage 2's nine-player limit |
| dev-18 | USIG | 1 | 1,10 | Same four-over provisions as dev-01; adversarial question and refusal/correction outcomes unchanged |

The remaining cases were checked and retain their original annotations: dev-05 uses MCC 12 for pitch dimensions; dev-08 uses Junior 14 for weekend press responsibility; dev-11 and dev-15–17/dev-19–20 have no narrow page expectation and retain source/outcome/rubric checks. Contents-page mentions and unrelated age divisions were not added.

An accepted-page list is a **coverage check**, not an assertion that any one of those pages entails every possible claim. In a comparison, multiple pages may support different parts. For example, Junior 26 alone supports the stage 2 component but does not establish the pathways number; semantic assessment must still require support for both. Similarly, USIG 17's Powerplay limit does not by itself establish the first-six definition. The reviewer must inspect the exact response and its cited passages. This audit does not weaken the runtime gate or change the semantic rubrics.

The generator `evals/make_cases.py` reproduces the corrected JSONL. An automated comparison confirmed that only `expected_pages` changed. The 12 HTTP-harness tests and 3 native-metric tests passed after regeneration. Rechecking an existing saved smoke response does not count as another live model run.
