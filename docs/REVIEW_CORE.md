# Core review record

Astra performed a reviewer-only inspection of Sol's backend implementation and authored independent offline boundary tests. Core changes were made by Sol, then re-inspected and exercised by the reviewer. Root independently inspected runtime configuration and is responsible for paid model/deployment acceptance.

## Findings corrected before the first paid smoke

- Generation usage referenced a nonexistent SDK field. Accounting now uses candidates plus thinking tokens, and prospective request estimates include the full request structure. SDK retries are disabled rather than silently escaping the model-call counter.
- Native ADK export used a shared mutable ledger. It now creates a fresh governed pipeline and ledger per invocation, including parallel native evaluation cases.
- Search-result IDs alone could satisfy evidence availability. The release gate now requires pages read during the current invocation, rechecks ACLs, and clears all prior draft/review/final state each turn.
- A stale previous response could otherwise survive an incomplete event stream. The service checks current request and public session identity before release.
- Failed attempts could bypass history rotation. Every dispatched turn now counts toward the bound.
- Source panels could omit the supporting passage because citations showed only a fixed prefix. They now return the authorized full page within the source limits.
- Immutable-index checks were incomplete. The loader verifies an expected snapshot hash when configured (required in production), and the schema checks unique sources, canonical contiguous page IDs, embedding dimensions and finite vectors.
- Query embedding truncation and provider timeouts were implicit. Truncation is disabled/rejected and SDK calls have explicit finite timeouts. A local timeout still does not prove upstream cancellation.
- Audit output lacked guaranteed preflight durability and usable cloud stdout. Preflight append precedes model dispatch; final append must succeed before release. Allowlisted metadata uses an explicit JSON stdout logger after fsync. Unknown fields/tool names are rejected or normalized; short writes are completed before fsync.
- Observed event timing initially attributed the next agent's work to the previous author and omitted the initial wait. The current trace associates each observed interval with its arriving author and includes explicit tool names. These are observed stage intervals, not distributed tracing spans.
- API response security headers and cache controls were added and checked against actual TestClient responses.

## Executed offline evidence

`tests/test_governance_review.py` checks real ADK agent hierarchy, model equality, retry limits, tool declarations, stale evidence, repeated ACL checks, reviewer failures, scope refusal, full citation text, budget rejection, ledger reset, and billable output token accounting.

`tests/test_service_boundaries.py` checks session owner binding, history rotation, audit-preflight failure before model construction, stale response rejection, failed-turn accounting, content-free audit metadata, private JSONL mode, actual subprocess JSON stdout matching the durable file, authentication/role rejection, and security headers. SDK/model execution is replaced; no paid request is made by these tests.

The evaluation harness has a separate Terra reviewer record at `REVIEW_EVAL.md`. Native metric tests invoke Google's actual `TrajectoryEvaluator` on synthetic event sequences; they do not execute the model. UI fixes and re-review are recorded at `REVIEW_UI.md`.

## Limits of this result

This is an offline code and boundary review. It is not evidence that Gemini answers the corpus correctly, that follow-up retrieval succeeds in live inference, or that the cloud deployment is operational. Root's live HTTP/native ADK evaluation, source-based assessment with reviewer identity, browser acceptance, and deployment evidence remain separate. Syntax and page-ID checks establish citation integrity; they do not prove semantic grounding. The application remains an intermediate, single-workspace portfolio demo.

## Structural repair after the first complete live baseline

The preserved development baseline scored 8/20 structural passes and exposed skipped reads and research exhausting the reviewer budget. Sol implemented phase-aware Gemini function selection driven by successful per-turn tool state, prevented a late new search from consuming required read/finalize/review slots, and increased the configured total to eight calls with a 7,200-token aggregate output allowance. HTTP now passes an explicit ADK `RunConfig`; the native wrapper preserves any stricter positive caller cap. Native failures before the gate receive a sanitized terminal usage audit, while a successful gate writes only one terminal record.

Astra inspected the installed ADK processor/callback ordering and independently reproduced the offline suite. Terra independently reviewed the phase and budget boundaries, exact requested age/format/attribute criteria, HTTP configuration and native terminal auditing. A P2 native override of stricter caller limits was fixed and re-reviewed with None/0/3/500 cases. Final offline result for this checkpoint: **52 passed**. No reviewer made a paid model call.

The deterministic citation gate remains unchanged. Requiring at least one read from a search does not prove every later cited page was read; the final gate still rejects an unread citation. Tool-path controls do not establish retrieval relevance or semantic completeness. The selected live retry improved safety but still withheld two answerable questions; full post-repair quality and deployment validation remain separate evidence. See `REVIEW_BASELINE.md` for the preserved baseline source assessment.
