> Local Ollama migration: this document records the earlier Vertex/Cloud Run implementation or its evaluation procedure. For the active local setup use `README.md` and `docs/DEMO_GUIDE.md`; current local evidence is in `docs/RESULTS_LOCAL.md`. Historical commands/results are not proof of local-model behavior.

# Development evaluation

`cases.jsonl` is a transparent 20-case development set. It is available to implementers and is **not a holdout**. The three follow-up cases add a setup turn, for 23 endpoint requests. Root maintains a separate final acceptance set.

Plan only, no calls:

```bash
.venv/bin/python evals/run.py
```

Execute only against an already configured, authorized endpoint and after reconciling the remaining Google budget. Use the token-safe Python example in [the demo guide](../docs/HISTORICAL_CLOUD_DEMO.md#reproduce-evaluations-carefully), which reads the private settings in-process and sets a $2.50 evaluator allowance for all 23 turns. Do not put a token in command arguments or shell history. The CLI sends `X-App-Token` to coexist with Cloud Run IAM; `--ids dev-01,dev-09` selects a subset and records that selected denominator.

The evaluator reserves a conservative allowance before each dispatched endpoint turn, reads reported usage costs when available, and stops before its configured estimate. It is an additional guard, not a Google billing cap. The application enforces per-run call, token, tool, evidence and time budgets; the evaluator owns the monetary reservation. `--per-turn-reservation-usd` defaults to $0.10. The separate Gemini 3.8 benchmark uses $0.20 per attempted turn. Both this amount and `--max-estimated-usd` must be finite and strictly positive. Every checkpoint records the selected reserve and budget; the harness rechecks the available reserve before each dispatch, including follow-ups after a setup cost is reconciled. Uncertain requests retain their reserve. Actual costs must be reconciled with application usage and billing metadata.

The report records all planned IDs, executed IDs, failures, denominator, dataset SHA-256, response statuses, source/page locations, latency and token usage. Incomplete runs cannot appear as complete passes. Network failures count as failures. The normal report contains no full prompts, answers or passages. `--save-responses` explicitly writes a private adjacent responses file with mode 0600 under gitignored `work/` for separate source-based review.

Automated checks cover:

- Response status versus the expected safe/answered outcome.
- Non-empty structured claims and citation metadata.
- Citation IDs unique, present, and linked from claims.
- Expected source and page coverage where a narrow factual expectation is known.

These are **structural and coverage checks**, not evidence of semantic correctness. Each case contains a source-review rubric in the legacy `human_rubric` field. A reviewer must read the answer and cited source excerpts, then mark support, factual correctness, competition/edition scope, completeness, and appropriate abstention. The report remains `semantic_review: pending` until that review is recorded separately. Matching the expected page does not prove that the cited passage entails the answer.

Keep evaluation output private; it can contain licensed source excerpts. Publish the harness and aggregate results only after verifying their contents and receiving repository publication authorization.

## Native ADK evaluation artifact

Native evaluation needs the ADK evaluation extras in the local operator environment. After the normal `uv sync --extra dev`, install the same pinned ADK version with its optional evaluator dependencies:

```bash
uv pip install --python .venv/bin/python 'google-adk[eval]==2.9.2'
```

Run this after syncing: a later `uv sync --extra dev` removes packages outside the runtime/dev lock. These local evaluation extras are not part of the deployed runtime image. Installing them makes no model call; running the native commands below can. An initial CLI prerequisite error is not an executed agent evaluation.

`native.evalset.json` is a small native ADK Eval artifact with three development cases and four conversation turns. `native.config.json` measures only the expected `list_sources → search_documents → read_evidence` tool trajectory, with arguments ignored. It does not score answer quality, citation entailment, safety, or semantic correctness.

The artifact and native trajectory metric have been validated offline with three synthetic-event tests in `tests/test_native_eval.py`. That is SDK/artifact validation, not a live native ADK Eval run and not a model-quality result.

The following command is reserved for the root operator because it can make Google model calls and incur authorized Google usage:

```bash
PYTHONPATH="$PWD" APP_ALLOW_ADK_CLI=true .venv/bin/adk eval app evals/native.evalset.json:dev-01 \
  --config_file_path evals/native.config.json --log_level warning
PYTHONPATH="$PWD" APP_ALLOW_ADK_CLI=true .venv/bin/adk eval app evals/native.evalset.json:dev-09 \
  --config_file_path evals/native.config.json --log_level warning
PYTHONPATH="$PWD" APP_ALLOW_ADK_CLI=true .venv/bin/adk eval app evals/native.evalset.json:dev-13 \
  --config_file_path evals/native.config.json --log_level warning
```

Run these selectors from the project root with the shown quoted `PYTHONPATH` so the console script can import the local `app` package. Run them sequentially: one conversation per case, four total turns including the follow-up setup. The metric itself uses no model judge; the agent still performs ordinary paid model inference. Keep its output private under `work/`, record its exact runtime/model settings, and do not describe native order matching as semantic validation. The custom HTTP harness above remains the 20-case/23-turn development evaluation and remains `semantic_review: pending`.

Do not infer an evaluation pass from the CLI exit code. In this build the native CLI exited zero even when provider requests failed and no metrics were produced. Inspect each case's `final_eval_status` and actual metric results in private `app/.adk/eval_history/`. Preserve prerequisite failures, failed inference attempts and successful scoring as distinct records. That nested ADK directory is excluded from deployment contexts and source publication.

## Reviewer identity

The rubric field is named `human_rubric`, and automated reports deliberately retain `semantic_review: pending`. A separate reviewer may assess the saved answers against those rubrics and source excerpts. Record that reviewer as an agent or a human accurately; an independent agent assessment is not human approval. Keep the user's later manual verification separate, without adding a new blocker to already-authorized overnight delivery.

The independent assessment procedure is [docs/SEMANTIC_REVIEW_PROTOCOL.md](../docs/SEMANTIC_REVIEW_PROTOCOL.md). The page-annotation correction history is [docs/EVAL_ANNOTATION_AUDIT.md](../docs/EVAL_ANNOTATION_AUDIT.md).

## Controlled model/configuration comparison

The Flash Lite baseline and retrieval rerun remain preserved. A separate benchmark can use `gemini-3.8-flash`, LOW thinking, 2,000 output tokens per call and a 16,000-token aggregate output limit. This changes both model and output configuration; it is not a model-only experiment. Researcher and reviewer use the same model within each run. Trusted terminal audit records identify the configured model, provider and location, and the cost ledger prices them separately.

For a root-coordinated selected benchmark, add `--ids dev-09,dev-11,dev-12,dev-13 --per-turn-reservation-usd 0.20 --max-estimated-usd 1.5` to the token-safe runner invocation. These cases have six planned turns. No prompt, retrieval, dataset, rubric or release-gate change is part of that comparison. A prepared configuration is not evidence of a successful live benchmark; refer to the actual preserved run and source-review record.
