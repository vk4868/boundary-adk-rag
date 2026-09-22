# UI review record

The initial reviewer-only Terra pass found two P1 integrity defects: a generic success status could display “Evidence reviewed,” and unknown claim/citation links were silently skipped. It also found response-shape handling, canceled-token clearing, and evidence-panel focus issues.

Terra implemented the fixes. Astra independently inspected the resulting code and required a second correction: legitimate insufficient-evidence/rejected outcomes needed their own safe display path, answered output had to use only structured cited claims, optional null durations had to be accepted, and citation IDs/pages had to match the connected source metadata. Those corrections are now present.

Verified offline on the final reviewed frontend:

- `node --test tests/web_response_validator.test.js` passes.
- JavaScript syntax checks pass.
- The supported answer path requires `status=answered`, all three governance flags, a passed deterministic gate, canonical valid citations, and resolved non-empty claim evidence references.
- Safe non-answers do not display the reviewed badge and contain no factual claims/citations.
- Raw text uses DOM `textContent`, with no HTML interpolation of answers or source excerpts.
- `X-App-Token` coexists with IAM authentication; the token is kept in tab memory, and canceled dialog values are cleared.
- Closing source evidence restores focus to its invoking button.
- Desktop1440x1000 and mobile390x844 screenshots were visually inspected; mobile has no horizontal overflow.

This review is frontend/contract evidence. Root's live browser and model-flow acceptance are separate. It does not establish semantic correctness of an answer.

## Execution versus approval wording

Terra changed the activity panel so successful execution of the pipeline, researcher, reviewer and deterministic gate agent displays **Completed**. The separate final `deterministic_gate` decision retains **Passed/Failed**. Astra independently inspected the mapping, requested inclusion of the parent pipeline stage, and rechecked that correction. Raw protocol statuses and the reviewed-answer validator were unchanged. Node syntax and existing validator checks passed. This is a display clarification; it does not turn reviewer execution into semantic approval. Final browser verification remains with the deployed/local acceptance run.
