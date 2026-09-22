# Portfolio and interview narrative

This is a draft for a project section or interview, not a claim of employment experience. Use only statements you can explain from the code and final evidence. Do not describe an AI-assisted build as manually authored line by line, invent a client engagement, or imply production adoption.

## A clear project description

“Boundary is a document research assistant built with Google ADK and Vertex AI. It retrieves private rulebook evidence, runs separate research and review agents, and uses a deterministic gate to enforce citation identity and source access before releasing an answer. Its sample corpus includes conflicting competition-specific cricket rules, which makes source scope a real part of the reasoning problem.”

This description concerns the implemented design. When presenting it as a functioning live demo, first confirm the final application-level acceptance result. A framework import or an offline unit test does not establish that live inference works.

## How the work maps to an AI/Data role

| Role capability | Concrete project evidence to discuss |
|---|---|
| Data ingestion and quality | Immutable PDF inputs, source hashes, page extraction, truncation checks and validated embedding dimensions |
| Applied generative AI | Real ADK agent orchestration, typed tool calls, structured output and Vertex client configuration |
| Retrieval engineering | Document/query embeddings, scope-aware source filters, hybrid lexical/dense search and fixed-index tradeoffs |
| Governance and security | Authentication, server-assigned role, pre-retrieval ACL, current-turn citation checks, private cloud access and metadata-only audit |
| Evaluation | Development versus acceptance separation, exact denominators, structural/trajectory metrics and source-based semantic assessment with reviewer identity |
| Cloud engineering | Private Cloud Run, runtime identity, Secret Manager, private build context/image/index and bounded service configuration |
| Consulting communication | Explain the user problem, a business-relevant decision boundary, tradeoffs, evidence and remaining risks in plain language |

Cricket is a manageable demonstration domain. Do not claim that the same implementation is already approved for regulated client policies. Explain what would need to change: identity integration, durable storage, corpus lifecycle, stronger operational controls, scale testing and domain-specific evaluation.

## Ready-to-use résumé bullets

- Built Boundary, a Google ADK and Vertex AI document research assistant over 156 PDF pages, combining hybrid retrieval, typed tools, separate research/review agents and deterministic citation/access checks.
- Implemented invocation-scoped evidence controls, bounded repair and metadata audit; verified 88 offline tests plus 12 subtests and three native ADK tool-trajectory cases covering four turns, reporting answer quality separately.
- Deployed to IAM-private Cloud Run with a dedicated runtime identity, Secret Manager and an immutable private index; verified an authenticated browser-to-model sourced answer and documented provider-availability and semantic-completeness limitations.

These describe a portfolio project, not client employment or production adoption. The build was AI-assisted. Adapt the phrasing to the work you can explain and demonstrate personally. Performance and source-review results—including failures—belong in [RESULTS.md](RESULTS.md); a native tool-order pass is not an answer-correctness claim. Do not claim business impact, enterprise readiness, zero hallucinations or a public recruiter endpoint.

## A concise interview story

**Problem:** People need answers from documents with different scopes and editions. A plausible answer that applies the wrong rulebook can be worse than an explicit “not enough evidence.”

**Design:** Use a small fixed corpus to make behavior measurable. Give the researcher only three authorized document tools. Run a separate model review and a non-model release gate. Keep document content private while exposing source locations and operational trace metadata.

**Tradeoff:** The second model inference adds latency and cost, and the same model can repeat its own mistakes. Page-level retrieval is easy to trace but can struggle with tables or rules spread across pages. The fixed index and temporary sessions suit an intermediate demo rather than a multi-tenant production system.

**Verification:** Point to the actual offline tests and final live results. Explain which checks are deterministic, which are model judgments, and which were assessed by an independent agent or by the user. Do not describe agent assessment as human approval. Show a disagreement or abstention case rather than only a simple lookup.

**Next step:** Pick one limitation supported by the evaluation. For example, improve retrieval for multi-page comparisons or add durable authenticated sessions. Re-evaluate before claiming improvement.

## Questions you should be able to answer without a script

1. Why is `SequentialAgent` appropriate for this fixed workflow?
2. What can the model request through a tool, and what can it never access?
3. How are stale citations and cross-session responses rejected?
4. Why does an ACL need to run before an embedding search?
5. How did you verify that `.env` configuration actually reached Vertex's SDK client?
6. What happens when audit storage fails, a model times out, or a schema cannot be parsed?
7. Which metrics prove tool order or citation integrity, and which evaluate semantic correctness?
8. Why is the index private even though it is derived from PDFs rather than the original files?
9. What are the limits of the current spending controls and temporary Cloud Run sessions?
10. What did the final evaluation fail, and what did you change because of that evidence?

Use `docs/LEARNING_GUIDE.md` to map each answer to code and `docs/DEMO_GUIDE.md` to rehearse the demonstration. Final measurements belong in the completed evidence report; this draft intentionally does not invent them.
