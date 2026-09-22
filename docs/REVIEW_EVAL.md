# Evaluation Harness Review

Reviewer-only re-review completed on 2026-09-22.

## Scope

- `evals/run.py`
- `evals/cases.jsonl`
- `evals/README.md`
- `tests/test_eval_harness.py`

## Result

The evaluation harness passes this offline review.

It records malformed API data as explicit integrity failures; prevents a follow-up case from dispatching its final prompt after an invalid setup response; validates the reviewed-answer governance and deterministic gate; checks canonical citation IDs and source page bounds; and writes an allowlisted report metadata subset. Checkpoints retain pre-dispatch reservations, count dispatched turns, and leave semantic review pending.

## Executed checks

```text
.venv/bin/python -m unittest tests/test_eval_harness.py
Ran 12 tests: OK

.venv/bin/python evals/run.py
case_count: 20
endpoint_turns: 23
semantic_scoring: human_review_required
```

Both commands ran without `--execute`; no endpoint, cloud, model, or credential-backed application calls were made.

## Limits

This evidence covers offline structural checks only. It does not establish semantic correctness, retrieval quality, citation entailment, billing accuracy, or end-to-end endpoint behavior. The automated report retains `semantic_review: pending`. A separate source-based assessment must identify its reviewer as an agent or a human; agent assessment is not human approval. The historical plan output above is preserved. The user’s later manual verification is separate from authorized overnight delivery.

## Checkpoint privacy correction

A later reviewer pass found that the old temporary writer applied mode 0600 only after writing JSON. Terra implemented a unique `mkstemp` writer; Astra independently reviewed it and ran 16 isolated HTTP-harness/native-metric tests successfully. The descriptor is private before serialization, then flushed/fsynced and atomically replaced. A separate induced serialization failure preserved the previous report and removed the uncommitted temporary. Legacy predictable temporary files are not reused. Historical live reports and dataset/scoring fields were unchanged; new plan output uses `source_review_required` to describe the separate assessment accurately.

## Configurable dispatch reservations

Astra added a finite-positive `--per-turn-reservation-usd` option, retaining the $0.10 default and recording the selected reserve and budget in checkpoints. Decimal arithmetic preserves exact monetary boundaries. Terra found that a setup response costing more than its reserve could allow a later dispatch above the budget; Astra added a check before every turn and the exact regression. Terra independently re-reviewed: 16 harness tests and 12 validation subcases passed. A $0.15 setup under a $0.20 budget/$0.10 reserve now prevents the follow-up, preserves the completed setup response and reports one dispatched of two planned turns. Dataset and semantic scoring are unchanged.
