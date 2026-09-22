# Selected model/configuration comparison: first run

The selected benchmark used Gemini 3.8 Flash with LOW thinking, 2,000 output tokens per model call and a 16,000-token aggregate output limit. The Flash Lite development rerun used 900 and 7,200 respectively. This was a model-and-output-configuration comparison, with the same retrieval, prompts, dataset, release gate and 30-second per-model timeout. It does not isolate a model-only effect.

The private report `work/dev-model-comparison-v1.json` preserves four selected final cases (dev-09, dev-11, dev-12, dev-13), six planned turns, five dispatched turns and one saved response. None of the four final cases passed. Four attempted turns failed operationally with HTTP/SDK server errors; dev-13's final turn was not dispatched after its setup error. These unavailable answers do not support a semantic-quality conclusion. The evaluator retained $1.00 in dispatch reservations; this is not measured provider spend.

A reviewer-only GPT-5.6 Terra agent assessed the sole saved dev-12 setup answer against the development rubric and fixed source index. Its stated claims are supported by USIG pages 3 and 10 and scoped to that tournament, but it omits the required playoff Eliminator/Super Over distinction. It therefore fails setup completeness. This is an agent assessment, not human approval.

The complete source-review record is private `work/dev-model-comparison-v1.semantic-review.json`, written with mode 0600. The report retains all operational failures and the skipped final turn. Separate diagnostics or timeout experiments must be recorded as additional runs; they cannot replace these outcomes or retrospectively change their configuration.

## Separate deadline diagnostics and decision

A separate dev-09 diagnostic with the same 30-second model timeout captured provider code 504, status `DEADLINE_EXCEEDED`, and the message “Deadline expired before operation could complete.” The private record is `work/model-comparison-diagnostic.json`. Installed SDK inspection confirmed that the configured timeout becomes both the transport timeout and the `X-Server-Timeout` header. No concrete thought-signature, forced-function-selection or tool-history serialization incompatibility was identified.

One further isolated dev-09 diagnostic raised only the per-model timeout to 60 seconds while retaining the 120-second request limit. It ended with the application's overall `TimeoutError` at 120.1 seconds, without a governed answer (`work/model-timeout-diagnostic.json`). This does not establish a general model defect or quality comparison; it establishes that the tested configuration did not complete this workflow within the application's latency budget.

Gemini 3.8 Flash was therefore rejected as the working candidate for this bounded demo. Work returned to the preserved Flash Lite configuration with 900 output tokens per call and a 7,200-token aggregate limit. No further 3.8 attempts or wider timeout limits were used to manufacture a successful comparison. Later structural repairs belong to a separate Flash Lite revision and evaluation.
