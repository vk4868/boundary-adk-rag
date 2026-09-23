# Verification results

This evidence report distinguishes deterministic checks, custom HTTP evaluation, native ADK tool-trajectory scoring and source-based agent assessment. None alone establishes production readiness. Raw responses, source excerpts, credentials and detailed operational artifacts remain private under `work/` or the local ADK artifact directory.

## Latest resumed deployment checkpoint

The current private Cloud Run revision is `boundary-adk-00004-s8l`, built from the reviewed runtime freeze in `work/runtime-freeze-quality-v3.json`. The immutable image digest is `sha256:f193be4c0fbb9188baf5707f023acc04b9c7dcccc6c093c800b9fa7a1abfa6cc`; build `ba305f42-2c01-481b-bb8c-a44f7951c5cc` succeeded. IAM denial without credentials, application denial without its token, authenticated access to all three sources and index readiness were rechecked.

**119 offline tests plus 12 subtests passed**, as did the Node response validator. The final focused independent implementation review passed 22 tests. These checks establish tested boundaries, not semantic accuracy.

The unchanged ten-case acceptance/regression set planned eleven turns and dispatched ten. The follow-up setup failed, so its dependent turn was not sent; its final case remains in the denominator. Six requests returned HTTP200 and four returned HTTP502. Independent source assessment credited **5/10 final passes**: three correct sourced answers and two appropriate safe outcomes. One available answer omitted both governing junior contexts: the two-day boys/Under12-pathways section and the Under11 boys section. Four final cases were unavailable; cloud audit identified all four as provider resource-exhaustion errors. See [REVIEW_CLOUD_QUALITY.md](REVIEW_CLOUD_QUALITY.md).

The aggregate remains 5/10, matching the earlier deployed result with a different failure mix. The amendment and runner-condition cases now passed this run; the bowling-end comparison remained unavailable. Do not infer a general accuracy improvement, semantic validation of that comparison, or production reliability from these observations.

The current browser demo was attempted twice as separate recorded sequences. Both first turns failed with `ValidationError` after five model calls and three tools. Across the two sequences, four turns were planned, two first turns were dispatched, zero answers were produced, and both dependent follow-ups were skipped. The exact invalid schema field was not captured in metadata; no specific schema-cause claim is made. The current live browser demo is not verified as reliable. Both failures remain separate from the cloud regression and the historical successful browser sample.

The fresh native ADK run executed all three selected cases and four turns. All three recorded tool-trajectory scores were 1.0. Source assessment credited **2/3 final cases**, with 3/4 supported turns: the junior setup passed but its answerable MCC follow-up was safely rejected. See [REVIEW_NATIVE_QUALITY.md](REVIEW_NATIVE_QUALITY.md). Native completion does not replace browser verification.

Final reconciliation covers **169 requests**: **$0.9835934** estimated observed model/embedding/build usage, **$5.90** uncertainty reserve and **$1.25** hosting/storage reserve, totaling **$8.1335934** against the $10 authorization. The remaining **$1.8664066** is less than the **$2.13** conservative headroom for another diagnostic, build, full eleven-turn regression and two-turn browser check. Further paid repair/revalidation is paused at this checkpoint. These are estimates and reserves, not an invoice.

The final bounded Cloud Logging scan covered 334 records and 47 terminal events, all matched to preflights, including 12 on the current revision. It found no configured token, no exact matches for 33 checked test questions, and no unknown audit fields. This snapshot check is not a universal privacy guarantee. Raw evidence remains private.

## Original deployed baseline (before resumed quality fixes)

Local development, corrected native evaluation and paced deployed acceptance have completed with source assessments. Their exact denominators and limitations are reported separately.

The operator configuration shared by the original and resumed runs is Vertex `gemini-3.1-flash-lite` at `global`, eight model calls, 80,000 aggregate input tokens, 900 output tokens per call / 7,200 aggregate, a 60-second per-model timeout and a 120-second overall request timeout. The code/sample default per-model timeout remains 30 seconds; final operator settings explicitly override it. The v3 development run used these settings before the final capability adapter; its exact snapshot is private `work/runtime-freeze-final.json`. That process used dotenv settings without the cloud Vertex environment flag. The final adapter explicitly preserves the same formatter-tool path across environments; the full development set was not rerun after this compatibility correction. Final native and cloud evidence below covers the corrected revision.

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

The release gate enforces current-invocation citation identity, source access, reviewer verdict and explicit scope rules. It cannot prove semantic completeness. The original deployed baseline had no mandatory per-question-part completeness field; live tests found supported but incomplete answers that it approved. The resumed revision adds typed coverage and condition checks, but those model judgments still cannot guarantee semantic completeness or section-level scope. Source ranking, multi-turn citation compliance and provider deadlines also remain relevant limitations.

This is an intermediate single-workspace demo: a shared application token, server-assigned role, temporary session storage, private Cloud Run access and metadata-only audit. It has no enterprise SSO, durable multi-instance conversations, production readiness certification, public recruiter endpoint or measured business-impact claim. Cloud filesystem writes and estimated budgets are not durable conversation storage or a hard billing cap.

## Native source-review distinction

Corrected native dev-01 is supported and complete. Dev-09 remains incomplete: the MCC permission omits umpire/injury or wholly acceptable reason conditions and includes an irrelevant citation. Dev-13's setup passes, but its final comparison is safely withheld and does not complete the answerable task. All three native cases passed the tool-order metric; only one of three final cases passed source-based completion review. The four-turn private record is `work/native-adapter.semantic-review.json`.

## Original deployment accounting and log review

Root reconciled local and cloud usage within the US$10 authorization using conservative reserves. The observed estimate and reserved amount above are different quantities; reserves are not claimed charges. Cloud Logging review covered 229 records and matched all 35 expected terminal records to preflights. The bounded scan found no configured token, exact test-question or unknown-audit-field leakage in that evidence; this is not a universal privacy guarantee. Detailed records remain private.

The paced cloud errors were categorized as resource exhaustion for the acceptance follow-up and `KeyError` after `read_evidence` with zero evidence for the other failed case. The exact cause of that KeyError was not established. Both outcomes remain unavailable and are not attributed to provider availability as a group.

## Paced deployed answer quality

Five of ten final acceptance cases passed source assessment. Three available answers failed: one omitted the same-end bowling restriction, one omitted the conditional MCC runner provisions, and one made an unsupported/incorrect junior-format comparison. Two final outcomes were unavailable; the follow-up setup itself passed. The separate browser sample passed both turns, but it does not replace this broader 5/10 final result.

All eleven planned turns were dispatched with a 30-second delay between turns. This pacing changed scheduling, not the case inputs, rubrics, model or runtime. The rapid corrected batch's five HTTP errors and six HTTP200 turns remain preserved separately, as does the earlier all-error integration run. Final acceptance is regression evidence after the environment-parity correction, not an untouched holdout or production reliability claim. Those failures remain in the original denominator. The later quality runs below are separate executions, not replacements for failed cases.


## Resumed quality candidate v1 — not promoted

After the user resumed work, a bounded candidate added typed question-part review, adjacent-page references, and structured evidence-read errors. Its offline implementation review passed after a rejected-read accounting correction; root independently executed 102 tests plus 12 subtests. This did not establish improved answer quality.

The unchanged targeted subset contained five cases and five turns: a previously passing control, the three known semantic failures, and the prior read-error case. All five turns were dispatched with 30-second spacing. Independent source assessment credited **0/5 final passes**: two HTTP200 answers remained semantically incorrect/incomplete; one request failed with the ADK wrapper for a provider HTTP429 resource-exhaustion error; two requests reached an application budget boundary after repeated unsuccessful evidence reads. The subset is regression evidence, not a replacement for the historical ten-case deployed denominator. The candidate was not deployed.

Private diagnostic traces subsequently showed that the junior-change page ranked first but its snippet emphasized an unrelated age group; the model tried canonical pages inferred from a table of contents that had not been issued by search. A separate trace showed the runner-eligibility page available only as an adjacent reference, while the model read runner-conduct pages and the reviewer incorrectly approved unconditional permission. These are separate diagnostic executions and are not counted as replacements for the five scored outcomes. Raw traces and the source-review record remain private under `work/`.


## Resumed quality candidate v2 — targeted evidence

The next candidate added exact numeric qualifiers in search previews, charged adjacent-page previews, bounded corrective reads, and the original question in the reviewer's structured checks. Hybrid ranking, corpus, evaluation inputs, model and call/token limits were unchanged. Root executed 113 offline tests plus 12 subtests; the reviewer independently executed 44 focused tests.

The same five-case subset dispatched all five turns. The corrected independent source assessment is **3/5 final passes**: the simple control, explicit junior amendment and conditional runner comparison passed; the ambiguous bowling-limit answer omitted the cited junior two-day format scope; the bowling-end comparison failed closed during execution. Four responses were HTTP200 and one HTTP502. An initial 4/5 agent assessment missed the section-level restriction; root requested a source re-check, the reviewer corrected the score, and both assessments remain preserved. This demonstrates a limitation of model-based review even when citation identity and typed coverage checks pass.

A separate exact-question trace of the failed comparison showed an unissued evidence-ID request consuming limited research calls, followed by an inconsistent reviewer output rejected by schema validation. This additional diagnostic is counted in costs and is not a replacement scored answer. No claim of broader quality or current deployment improvement follows from this targeted subset.


## Final bounded declaration candidate — separate diagnostic

The final resumed candidate constrains the outbound `read_evidence` function declaration to reauthorized IDs issued in the current invocation, with request-local schema copies and unchanged server validation. Root executed **119 offline tests plus 12 subtests**, and the Node response validator passed. The independent focused review executed 22 tests and checked the final serialized Vertex request, missing-declaration rejection, isolation, authorization and input estimation.

The single additional exact-question bowling-end diagnostic reached both rulebooks through valid issued-ID reads, then failed with Google HTTP429 resource exhaustion before producing a final answer. The request is retained as unavailable and counted in costs. It demonstrates live acceptance of the constrained function declaration and progress beyond the earlier invalid-ID call, not a correct answer or a passed case. No additional diagnostic retry replaced it.
