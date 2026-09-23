# Resumed quality-contract review

GPT-5.6 Terra completed this reviewer-only agent review after the resumed implementation freeze; this was not human approval. The review covered typed question-part coverage, condition and absence checks, current-invocation evidence issuance, bounded adjacent references, atomic reads, formatter repair, ACL preservation, and the existing eight-call / 900-output-token-per-call configuration.

## Finding and correction

The first review found that a rejected formatter-repair `read_evidence` request returned from the callback before the governed tool incremented its counters. That contradicted the contract requiring attempted invalid reads to consume tool budget.

The correction calls the normal ledger tool-budget/time guard and increments the read-attempt counter in both intercepted rejection branches. A permitted repair read still reaches the real read tool and is counted once. The updated regression verifies that two rejected repair reads consume two tool/read attempts, leave no read evidence, and do not permit a retry.

## Evidence

- Focused independent execution: `tests/test_formatter_read_repair.py`, `tests/test_evidence_read_contract.py`, and `tests/test_completeness_contract.py` — 20 passed.
- Author-reported frozen full offline suite: 102 tests plus 12 subtests; no model or cloud call was made for this review.

The implementation now fails closed for empty or malformed coverage, non-integer or out-of-range mappings, unsupported absence claims, unread evidence, invalid/unissued/unauthorized atomic read batches, and stale invocation state. Adjacent page IDs are issued references only and are charged when later returned as snippets; they do not become reads automatically. The reviewer’s typed assessment remains a model judgment and does not establish semantic completeness without new live measurement.

## V2 retrieval, read-recovery, and completeness re-review

GPT-5.6 Terra completed a second reviewer-only review after Sol's final core freeze. This was an agent review, not human approval. It covered `app/models.py`, `app/agents.py`, `app/gate.py`, `app/tools.py`, `app/index.py`, the associated offline tests, and the matching working rules and explanatory documentation.

The review confirmed that an answered draft requires nonempty typed question-part coverage with strict zero-based indices, read evidence for every mapped claim, preserved conditions, and no unsupported absence claims. A justified zero-claim abstention takes its own compatible path. The original question is refreshed as quoted untrusted reviewer state for each invocation.

Adjacent candidates remain same-source, ACL-filtered, explicitly issued references; previews never mark a page read. Each distinct returned text fragment is charged atomically. The two-search/three-full-read budget regression stays below the existing 24,000-character cap with 350-character adjacent previews. Exact dotted references survive source-filter preprocessing, and the negative `17.1`/`17.10` regression prevents a same-prefix preview match.

One P2 documentation finding was corrected before this re-review: the code enforces one ordinary corrective read **per invocation**, and a later search cannot reset that allowance or reopen formatter repair. `AGENTS.md`, `docs/QUALITY_CONTRACT.md`, `docs/ARCHITECTURE.md`, and `docs/LEARNING_GUIDE.md` now state the same rule. Invalid reads still count, resolve and authorize their whole batch before mutation, disclose only revalidated issued IDs, and fail closed. Earlier same-invocation issued evidence remains eligible; prior-invocation state is cleared.

Evidence:

- Independent offline execution: `tests/test_completeness_contract.py`, `tests/test_evidence_read_contract.py`, `tests/test_formatter_read_repair.py`, `tests/test_research_phase_control.py`, and `tests/test_retrieval_constraints.py` — **44 passed**. `python -m compileall -q app` and `git diff --check` also passed.
- Parent independently reproduced the frozen full offline suite: **113 tests plus 12 subtests** in 1.35 seconds. No model or cloud call was made for this review.

Disposition: **cleared for the authorized five-case regression run.** The checks establish bounded contract behavior and do not claim semantic improvement; retain every live result and its availability outcome in the planned denominator.

## Dynamic read-schema re-review

GPT-5.6 Terra completed a final reviewer-only review of the bounded dynamic
`read_evidence` declaration change. This was an agent review, not human
approval. The review covered the request-local declaration copy in
`app/agents.py`, the actual ADK-assembled researcher request, the Vertex
converter representation, and `tests/test_dynamic_read_schema.py`.

For each researcher dispatch, the callback reauthorizes the complete
current-invocation issued-ID union against the active role before placing its
sorted IDs in the read tool's string-item enum. Restricted, missing, and
prior-invocation IDs therefore do not enter the advertised choices. An empty
allowlist removes both the declaration and its otherwise empty wrapper; a
forced read without an eligible declaration fails before model dispatch. More
than 256 IDs raises instead of truncating. The real read tool remains the
authorization boundary for actual arguments.

Both ADK schema representations are covered. Successive requests and separate
agents do not share enum values, and the underlying function-tool declaration
is unchanged. The enum is included in the conservative input estimate. The
final regression explicitly checks that a forced read with only `tools_dict`
and no outbound declaration fails with zero model calls. It also serializes the
converted Vertex declaration with aliases and confirms the nested
`parametersJsonSchema.properties.evidence_ids.items.enum` value. No model,
cloud, or network call was made.

Evidence:

- Independent offline execution: `tests/test_dynamic_read_schema.py`,
  `tests/test_research_phase_control.py`, and
  `tests/test_formatter_read_repair.py` — **22 passed**. `python -m
  compileall -q app` and `git diff --check` also passed.
- Author-reported frozen full offline suite: **119 tests plus 12 subtests**.

Disposition: **cleared for the one authorized diagnostic check.** This
declaration constrains offered choices and preserves server-side validation; it
does not establish a semantic-quality improvement.

## Final documentation accuracy and privacy review

GPT-5.6 Terra completed a reviewer-only read of the final project-status,
cost, portfolio, architecture, learning, quality-contract, demo, and review
documents, together with the private handoff draft. This is an agent document
review, not human approval.

The current results are stated with their proper denominators: the resumed
cloud regression has 5/10 source-assessed final passes, one available
scope/completeness failure and four unavailable provider-resource-exhaustion
outcomes; the 11-turn plan dispatched 10 turns. Native tool trajectory remains
separate from source assessment: 3/3 trajectory cases scored 1.0, while 2/3
cases completed semantically across four turns. The two latest browser
sequences planned four turns, dispatched two first turns, returned no answers,
and skipped both follow-ups after validation errors. Earlier successful browser
evidence is consistently labeled historical rather than evidence of the current
browser flow.

Cost language matches the final ledger: 169 requests, a $0.9835934
usage-based estimate, $5.90 uncertainty reserve, and $1.25 hosting/storage
reserve total $8.1335934; $1.8664066 remains below the $2.13 conservative next
cycle headroom. The documents call these estimates and reserves, not a billing
invoice or hard cap. The bounded privacy snapshot is likewise described as a
limited scan rather than a universal guarantee, and public records omit raw
responses, prompts, source passages, credentials, sessions, and logs.

One wording discrepancy was corrected during review: the handoff's former
"observed usage" shorthand now says "usage-based estimate," reflecting the
ledger's conservative query-embedding bound. Provider failures are described
as resource-exhaustion wrappers; no document attributes an unproven rate-limit
or exact schema-field cause.

Disposition: **substantive documentation cleared.** The verified baseline
publication remains separate from the resumed quality-v3 candidate. Actual
candidate commit, remote publication, archive, and hash receipts are still
required for a final publication-specific re-review before delivery; this is a
recorded execution check, not evidence already claimed here.
