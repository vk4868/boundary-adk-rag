# Cloud quality regression review

A reviewer-only agent (`/root/astra_orchestrator/review_ui`, configured GPT-5.6 Terra) performed a source-based assessment of the saved responses from the frozen quality-v3 Cloud Run revision. This is an agent assessment, not human approval.

The run used revision `boundary-adk-00004-s8l` and immutable image digest `sha256:f193be4c0fbb9188baf5707f023acc04b9c7dcccc6c093c800b9fa7a1abfa6cc`. The reviewed result artifact hash was `fbc2477389c9c97b12acf2093d4ba1457030656568083b11856663a88e2cd2ee`; the runtime-freeze artifact hash was `8ca895bc06b2fd3b978a8ebf1bb5fd672c7fbb3dcdb030ea3b238b9db9044c17`. The run records the canonical acceptance-case hash `76bf323773b4e132424057082ab233a83ceea77d83a8507e32ff8c3b71fa11b5` and the fixed-index hash `4518de9adb0d63f4217eeb52e917671ad802ca78dd6952264aa96cc1f8ac1cee`.

The regression planned 10 cases and 11 turns. It dispatched 10 turns: six returned HTTP 200 and four returned HTTP 502. One required setup turn failed, so its follow-up was not dispatched. All four HTTP 502 outcomes were recorded as provider `_ResourceExhaustedError` wrappers and remain unavailable rather than being treated as semantic results.

Source assessment found 5 of 10 final cases passed, 1 available answer failed for omitted junior-rule format/team scope, and 4 final cases were unavailable. The unavailable cases remain in the denominator. The available safe abstention and safe refusal passed their respective cases; citation presence and governance flags were not used as a substitute for source assessment.

The private per-case assessment is stored with restricted permissions under `work/root-evidence/acceptance-cloud-quality-v3.semantic-review.json`. It retains case-level evidence references and the setup/follow-up outcome without publishing responses, questions, source passages, credentials, or logs. These results apply only to this saved frozen-revision run and do not establish broader semantic accuracy.

## Final browser attempts

Two separately recorded browser sequences ran against `boundary-adk-00004-s8l`. They planned four turns in total, dispatched the two independent first turns, returned zero answers, and skipped both dependent follow-ups. Both first turns ended in a `ValidationError` without an answer. No source-content or semantic assessment is possible from these attempts, and the available metadata does not establish the exact invalid schema field.

Earlier pre-resumption browser evidence with two successful turns belongs to a different candidate and is excluded from these counts. The private metadata assessment is `work/browser-quality-v3.semantic-review.json` with restricted permissions; it records only artifact hashes, counts, and error categories.
