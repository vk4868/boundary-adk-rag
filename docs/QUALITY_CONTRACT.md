# Resumed quality-improvement contract

The user explicitly resumed work after the published checkpoint. The historical paced result remains 5/10 final cases passing source assessment. This contract records the bounded corrections implemented during resumed work; offline and live verification results are recorded separately.

## Evidence motivating the change

Three released answers passed citation identity checks but did not satisfy the question: a related batting rule omitted the requested bowling change; runner conduct evidence was used to claim unconditional eligibility; and a comparison substituted a different numbered rule and inferred an absent local exception from irrelevant evidence. Some needed context falls on adjoining pages. Historical metadata does not reconstruct every search result or read, so the team does not label every failure a proven retrieval defect.

A separate offline reproduction showed that an invalid evidence ID raises `KeyError` before evidence is recorded. The original cloud request did not log its tool arguments, so this reproduction establishes a recoverable error path, not the exact cause or offending ID in that historical request.

## Approved boundaries

- The reviewer must assess the original question's requested parts, conditions and exceptions, not merely whether individual draft claims sound supported. Compact typed coverage must map to actual draft claims. Empty or malformed coverage and invalid claim references cannot approve an answered response.
- Unsupported statements that a source contains no rule require explicit review. A missed search result is not evidence that a rule is absent. Legitimate insufficient-evidence answers follow a separate compatible review path.
- Search may explicitly issue bounded same-source adjacent-page references to expose continuation context. These are context references, not additional vector-ranked hits. They are never marked read automatically; the model must call the governed read tool, and citations still require actual current-invocation reads.
- The read tool accepts exact IDs issued in the current invocation, including earlier searches in that invocation. It validates and resolves the whole batch before recording evidence. Malformed, unissued, unavailable or unauthorized IDs receive a generic structured failure without existence/content disclosure or partial mutation. Attempts still count; no ID guessing or substitution is permitted.
- The fixed index and hashes, source ACL, final citation gate, evaluation questions/rubrics, model and per-request budgets remain unchanged. No new model stage or automatic transport retry is added. Retrieval changes require an offline probe and generalizable tests rather than case-specific answer/page logic.

## Verification contract

Offline checks must cover vacuous and malformed reviewer output, strict claim references, evidence/claim linkage, conditional claims, legitimate abstention, read-error atomicity and privacy, adjacent-page boundaries and ACL, invocation reset, and practical output size under the existing 900-token-per-call allowance. Tests use synthetic cases independent of the acceptance answers.

A reviewer-only agent inspects the implementation before root runs any paid checks. Root owns the unchanged-case targeted regression, later full cloud/native/browser checks, spend reconciliation and publication. Every failure stays in its planned/dispatched denominator. An improved typed review remains a model judgment; it is not a deterministic guarantee of semantic truth or completeness.

## First targeted result and trace-driven follow-up

The first resumed candidate passed 102 offline tests plus 12 subtests and independent code review, but its five-case live regression produced **0/5 semantic final passes**: two available answers retained their source failures and three requests were unavailable. Preserve that result; typed coverage alone did not establish improvement.

Private diagnostic traces then established narrower causes. A correct amendment page ranked first but its preview selected a different age group's changes; dotted provision numbers contributed misleading numeric overlap. A runner comparison did not read the preceding page containing eligibility conditions, although its ID had been exposed. Another comparison's reviewer assessed a different numbered provision from the original question. The failed read loop requested canonical but unissued IDs inferred from a table of contents; the generic error did not explain a usable next step.

The next bounded correction is therefore:

- Preserve dotted numeric provisions as distinct snippet tokens and prioritize exact numeric query phrases in previews. An offline ranking probe moved the required provision only from rank 10 to 9, still outside the five results, so the proposed ranking change was rejected. BM25 ranking tokenization, hybrid weights, dense query, fixed index and evaluation questions remain unchanged.
- Expose small adjacent-page previews, favoring an exact requested numeric provision when present and otherwise the previous page's tail or next page's head. These remain search context, requiring an actual read before citation. Charge distinct returned text fragments atomically; repeated identical fragments may deduplicate, while overlaps can conservatively count twice.
- Return only authorized, already-issued ID suggestions on a read failure, with guidance matching the available phase. Permit at most one ordinary corrective read per invocation before safe finalization. A later search cannot reset the allowance, and exhaustion cannot reopen reads through formatter repair. Do not extend the model/tool budget.
- Give the reviewer the current original question explicitly as quoted untrusted state, refreshed for each invocation, alongside the draft and evidence. This improves input clarity without treating the model's coverage judgment as deterministic truth.

This follow-up received independent offline review and a new measured live regression. The failed first candidate remains part of the evidence history.

## Final bounded declaration change

The second targeted assessment was corrected to 3/5 semantic passes: one available answer omitted necessary section-level format scope, and one case was unavailable. The latter diagnostic showed an unissued read consuming budget before finalization; an inconsistent reviewer response then correctly failed strict validation. Preserve both failures and the source-assessment correction.

The final bounded candidate adds a request-local enum of reauthorized current-invocation IDs to the outbound read declaration. It supports the installed SDK's JSON-schema and typed-schema representations, counts the schema in input estimation, omits the declaration when no ID qualifies, and rejects more than 256 IDs without truncation. It must not mutate cached tools, leak prior-turn choices, replace server validation, relax review consistency, add a loop, or increase any call/token budget. Root coordinated the single diagnostic check and full cloud regression; no further tuning cycle is planned within this budget.

The final implementation review is recorded in [REVIEW_QUALITY_RESUMPTION.md](REVIEW_QUALITY_RESUMPTION.md). The frozen release's [cloud source assessment](REVIEW_CLOUD_QUALITY.md) and [native trajectory/source assessment](REVIEW_NATIVE_QUALITY.md) retain the remaining semantic and availability failures. Passing offline boundaries or native tool-order metrics is not evidence that every answer is correct.

## Remaining priorities after the paid-work stop

The final browser verification attempted two separate sequences: four planned turns, two dispatched first turns, zero answers, and two skipped follow-ups. Both first turns failed with `ValidationError`. The current live browser chat is not a reliable recruiter demonstration. Earlier successful browser evidence belongs to a previous revision.

1. **Diagnose the exact browser validation failure.** Capture the failing draft/review boundary privately on the original browser prompt before changing schemas. The terminal error category alone does not identify which field failed. An earlier diagnostic established inconsistent reviewer output on a different request; do not assume both browser failures had that same cause. Preserve fail-closed behavior and never count an error converted to a rejection as a correct answer.
2. **Carry governing section context into evidence.** Page-level previews still omit restrictions inherited from section headings, such as two-day boys' formats and Under 11 boys. Evaluate a versioned section-context approach against the unchanged questions and scope rubric. Any new index must have a new recorded hash; do not alter the existing evidence snapshot silently.
3. **Measure answerable follow-ups separately from safe withholding.** The final native follow-up was answerable but rejected. Determine its specific failure boundary before modifying research budgets or gates. Tool-trajectory success does not complete the user's question.
4. **Evaluate provider availability separately from semantic quality.** All four unavailable final cloud cases had provider resource-exhaustion errors; the underlying capacity or quota cause was not established. Any future retry/backoff policy needs an explicit bounded cost/call contract and preserved attempt denominators; it must not conceal failed first attempts.

No further runtime tuning or paid requests were made after the final stop. A new diagnosis/build/full-cloud/browser cycle would exceed the remaining headroom under the agreed conservative accounting. Packaging this intermediate project is not a reliability or production-readiness claim.
