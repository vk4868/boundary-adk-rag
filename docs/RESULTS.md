# Verification results

This evidence report distinguishes deterministic checks, custom HTTP evaluation, native ADK tool-trajectory scoring and source-based agent assessment. None alone establishes production readiness. Raw responses, source excerpts, credentials and detailed operational artifacts remain private under `work/` or the local ADK artifact directory.

## Final verification checkpoint

Local development, corrected native evaluation and paced deployed acceptance have completed with source assessments. Their exact denominators and limitations are reported separately.

The final operator configuration is Vertex `gemini-3.1-flash-lite` at `global`, eight model calls, 80,000 aggregate input tokens, 900 output tokens per call / 7,200 aggregate, a 60-second per-model timeout and a 120-second overall request timeout. The code/sample default per-model timeout remains 30 seconds; final operator settings explicitly override it. The v3 development run used these settings before the final capability adapter; its exact snapshot is private `work/runtime-freeze-final.json`. That process used dotenv settings without the cloud Vertex environment flag. The final adapter explicitly preserves the same formatter-tool path across environments; the full development set was not rerun after this compatibility correction. Final native and cloud evidence below covers the corrected revision.

| Check | Exact coverage and result | Environment / evidence |
|---|---|---|
| Offline boundaries | 88 tests plus 12 subtests passed; final independent execution and material-change reviews passed | Root independently ran the final suite in 1.26 seconds; Node validator passed; author compilation passed |
| Development v3, before capability adapter | 17 of 20 automated passes; 14 of 20 source-assessed final passes; 22 of 23 planned turns dispatched; 20 responses saved | Custom local HTTP harness, 300.063 seconds total elapsed; `work/dev-full-v3.json`, `REVIEW_FULL_V3.md` |
| Corrected native ADK evaluation | 3 cases / 4 turns; all recorded tool-trajectory scores 1.0 at threshold 1.0 | Actual status/metric records inspected; source review credits only dev-01 final as complete |
| Paced deployed acceptance/regression | 5 of 10 final cases passed source assessment; 11 of 11 turns dispatched; 9 HTTP200 / 2 HTTP502 | Unchanged case set through authenticated private proxy; 30-second inter-turn delay; `REVIEW_CLOUD_ACCEPTANCE.md` |
| Deployed browser sample | Two same-session turns passed source assessment; desktop and mobile checks passed | Four-over lookup then runner follow-up; evidence panel/trace opened; no horizontal overflow or JavaScript errors observed |
| Final Google estimate | $0.75399465 observed usage estimate + $4.60 uncertainty + $1.25 hosting/storage = $6.60399465; $3.39600535 authorization remains | 138 reconciled local/cloud requests; not an invoice; credits unverified |

## Preserved development history

All development cases are available for tuning and are not a holdout. The corrected dataset SHA-256 is `176ab7ffe6a865f9534a6e4248426540220a6f3493c5780b864ad43fd3fe13b9`; annotation changes and the original dataset are preserved separately.

| Run | Planned / dispatched turns | Final case results | Interpretation |
|---|---|---|---|
| Flash Lite baseline v1 | 23 / 22 | 8 of 20 automated and source-assessed passes | Baseline failures retained; wrong junior-format answer identified |
| Flash Lite retrieval v2 | 23 / 22 | 16 of 20 automated and source-assessed passes | Incomplete runner comparison and unread-citation failures remained |
| Selected Gemini 3.8 configuration | 6 / 5 | 0 of 4 final passes | Operationally unsuccessful; four server errors, one incomplete setup answer |
| Selected Flash Lite formatter repair | 5 / 5 | 1 of 3 final passes | Actual formatter→read→formatter recovery; incomplete setup, withheld comparison and HTTP error retained |

Final v3 source review found 11 useful answered cases and three appropriate safe outcomes. Six final cases did not pass: dev-02 was safely withheld but incomplete; dev-11 made an unsupported MCC absence claim; dev-13 and dev-15 were unavailable after HTTP errors; dev-17 did not resolve current worldwide applicability; and dev-20 avoided restricted disclosure but answered with irrelevant venue content. Dev-12's setup was incomplete although its final follow-up passed. All saved citation excerpts matched the canonical index, demonstrating why citation integrity and task correctness must be reported separately. The later revision did not improve every aggregate score over v2; all results remain preserved.

The Gemini 3.8 comparison changed model and output configuration (LOW thinking, 2,000 tokens per call / 16,000 aggregate). A separate 60-second model-timeout experiment still reached the 120-second request timeout. It was rejected as the working candidate for this latency-bounded demo; unavailable responses do not demonstrate model quality. The final Flash Lite timeout configuration must be recorded separately from earlier 30-second checkpoints.

Source assessments were performed by a reviewer-only GPT-5.6 Terra agent. They are agent assessments, not human approval or statistically independent verification. Detailed review records are summarized in `REVIEW_BASELINE.md`, `REVIEW_FULL_V2.md`, `REVIEW_MODEL_COMPARISON.md` and `REVIEW_REPAIR.md`.

## Preserved deployment integration failure

Before corrected deployment validation, the first cloud acceptance run attempted ten of eleven planned turns across ten cases; every case ended with HTTP 502 before document-tool execution. The separate browser attempt also failed. Native provider attempts likewise failed without scored metrics, even though the CLI returned exit code zero. Root traced these integration failures to environment-dependent ADK schema/tool capability selection: the cloud Vertex environment retained JSON response mode while the workflow forced function calls. The original reports remain preserved. Because this acceptance failure informed an integration correction, subsequent runs of those cases are acceptance/regression evidence, not untouched holdout results.

## Fixed corpus and release boundaries

The private index contains 156 original PDF pages across three immutable documents, with 768-dimensional Vertex embeddings and zero provider truncations at ingestion. Its SHA-256 is `4518de9adb0d63f4217eeb52e917671ad802ca78dd6952264aa96cc1f8ac1cee`. The ingester recorded 322,961 billable characters. The repository includes the manifest and three source PDFs under the user's explicit publication authorization; the generated vector index, credentials, runtime logs and raw evaluation artifacts remain excluded.

The release gate enforces current-invocation citation identity, source access, reviewer verdict and explicit scope rules. It cannot prove semantic completeness. The reviewer has no mandatory per-question-part completeness field; live tests found supported but incomplete answers that it approved. Source ranking, multi-turn citation compliance and provider deadlines also remain relevant limitations.

This is an intermediate single-workspace demo: a shared application token, server-assigned role, temporary session storage, private Cloud Run access and metadata-only audit. It has no enterprise SSO, durable multi-instance conversations, production readiness certification, public recruiter endpoint or measured business-impact claim. Cloud filesystem writes and estimated budgets are not durable conversation storage or a hard billing cap.

## Native source-review distinction

Corrected native dev-01 is supported and complete. Dev-09 remains incomplete: the MCC permission omits umpire/injury or wholly acceptable reason conditions and includes an irrelevant citation. Dev-13's setup passes, but its final comparison is safely withheld and does not complete the answerable task. All three native cases passed the tool-order metric; only one of three final cases passed source-based completion review. The four-turn private record is `work/native-adapter.semantic-review.json`.

## Final accounting and log review

Root reconciled local and cloud usage within the US$10 authorization using conservative reserves. The observed estimate and reserved amount above are different quantities; reserves are not claimed charges. Cloud Logging review covered 229 records and matched all 35 expected terminal records to preflights. The bounded scan found no configured token, exact test-question or unknown-audit-field leakage in that evidence; this is not a universal privacy guarantee. Detailed records remain private.

The paced cloud errors were categorized as resource exhaustion for the acceptance follow-up and `KeyError` after `read_evidence` with zero evidence for the other failed case. The exact cause of that KeyError was not established. Both outcomes remain unavailable and are not attributed to provider availability as a group.

## Paced deployed answer quality

Five of ten final acceptance cases passed source assessment. Three available answers failed: one omitted the same-end bowling restriction, one omitted the conditional MCC runner provisions, and one made an unsupported/incorrect junior-format comparison. Two final outcomes were unavailable; the follow-up setup itself passed. The separate browser sample passed both turns, but it does not replace this broader 5/10 final result.

All eleven planned turns were dispatched with a 30-second delay between turns. This pacing changed scheduling, not the case inputs, rubrics, model or runtime. The rapid corrected batch's five HTTP errors and six HTTP200 turns remain preserved separately, as does the earlier all-error integration run. Final acceptance is regression evidence after the environment-parity correction, not an untouched holdout or production reliability claim. No further model calls were made to replace failed cases.
