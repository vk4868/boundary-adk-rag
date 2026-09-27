# Independent review — local Ollama migration

## Decision

**Implementation approved for the authorized local migration and publication.** The review does not approve a claim that the system is reliable across all questions or that live acceptance is complete.

The active configuration uses Google ADK to run separate researcher and reviewer agents with `granite4.2:8b` on numeric loopback Ollama. Retrieval uses the separately built `embeddinggemma:latest` index. The deterministic gate, ACL checks, source-read requirement, index/model identity checks, bounded budgets, and metadata-only audit remain active. There is no cloud inference fallback.

## What was independently verified

- Loopback-only Ollama configuration rejects remote, proxyable, redirected, and malformed endpoints; transport uses one dispatch with zero retries.
- Active model calls require Ollama generation and Ollama embeddings. Retrieval validates the fixed index’s embedding identity before dispatch.
- Researcher and reviewer remain separate ADK `LlmAgent` invocations. The reviewer receives only its bounded current-invocation evidence pack and uses a typed internal formatter tool.
- Formatter declarations sent to Ollama are request-local, fully inlined canonical Pydantic schemas. They preserve required fields, forbidden extras, and array bounds. Invalid reviewer output receives at most one SDK validation correction, within the global eight-model-call limit; no correction can start a ninth call.
- The deterministic gate continues to withhold invalid, unread, unauthorized, stale, or scope-mismatched citations. It does not claim to prove every model interpretation correct.
- Offline verification passed: **165 pytest tests plus 12 Python subtests**. Node TAP separately passed **one test file**. `uv lock --check` and `git diff --check` passed.
- Native ADK evidence records one full real workflow: list, search, read MCC p12, researcher formatter, reviewer formatter, and gate, producing the correct cited pitch dimensions.
- The custom browser shows one correct standalone pitch answer, reviewed badge, and MCC p12 source panel. Its follow-up failed closed with a generic error.
- The bounded privacy receipt found no configured application token or any of the 20 exact development questions in the scanned default audit/server/native logs; it also confirms immutable PDF/index hashes and active Ollama loopback identities. This is an exact-match receipt, not a universal secret scan.

## Live acceptance and retained limits

The final frozen Granite v14 development regression is **4/6 source/safety-assessed case passes across 7/7 dispatched turns**. Dev-01, Dev-05, and Dev-09 have correct scoped citations; Dev-15 safely withholds an unavailable external result with zero claims. Dev-13’s setup is source-correct, but its required follow-up fails HTTP 429 before its fourth model dispatch, consistent with the conservative context-window preflight. Dev-19 fails closed with HTTP 429 and releases no secret, but is not a successful refusal.

The local browser’s standalone answer/citation path passes, while its simple follow-up fails HTTP 429. The shared local model can still make semantic errors or reject valid drafts. These failures are retained in `docs/RESULTS_LOCAL.md` and private `work/` artifacts; they must remain visible in portfolio and demo claims.

## Publication conclusion

Publication is approved because the source documents, configuration, guardrails, tests, local identities, evidence records, and limitations are documented consistently. Present this as an intermediate local RAG/ADK learning prototype with partial live acceptance, not a production-ready or generally reliable question-answering system.
