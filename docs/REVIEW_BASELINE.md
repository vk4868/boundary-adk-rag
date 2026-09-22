# Baseline development-run source review

A reviewer-only `/root/astra_orchestrator/review_ui` agent, configured as GPT-5.6 Terra, performed a source-based semantic assessment of the saved `dev-full-v1` baseline. This is an **agent** assessment, not human approval or statistically independent verification.

The reviewed inputs were the corrected 20-case development dataset (`176ab7…3fe13b9`), the fixed private index (`4518de…ac1cee`), the baseline report (`bff401…b88b79`), and its saved-response file (`add3d8…d8aa52`). Raw answers and source excerpts remain private in `work/`.

- Planned: 20 cases and 23 turns. Dispatched: 22 turns. Saved responses assessed: 16 (13 final responses and 3 setup responses).
- Final outcomes: 8 structural and semantic passes, including 3 useful sourced answers and 5 appropriate safe outcomes. Five answerable finals were safely withheld but did not complete the task.
- Seven final outcomes are unavailable and were not counted as passes: six HTTP errors and the dev-13 final skipped after its rejected setup.
- The dev-14 setup response was semantically inadequate: it used other junior-format participation material instead of the requested Under-12 pathways 13-player rule. Its final follow-up then had an HTTP error.

The complete private record is [dev-full-v1.semantic-review.json](../work/dev-full-v1.semantic-review.json). It records all case outcomes, the three setup turns, dimension judgments, supporting page IDs, and exact denominators. Page coverage remains a structural locator, not proof of semantic entailment.
