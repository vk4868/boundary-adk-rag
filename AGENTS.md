# Boundary — ADK Document Research Assistant

This is the canonical project working-rules file. Keep the uppercase name `AGENTS.md`; do not create a second `agents.md`. Apply these rules to this directory and its descendants. Later explicit user instructions take precedence. Update factual implementation notes when the implementation changes; do not silently reinterpret the authorized scope.

## 1. User-authorized scope and constraints

These are user requirements, not optional architecture preferences:

- Build an intermediate portfolio demo in `/Users/vineetkumar/Documents/Work/RAG/ADK RAG`, separate from `RAG Project` and `policy-kpi-rag`. Do not modify those projects or unrelated resources.
- The portfolio target is an AI/Data Consultant or AI Data Engineer role, including the Deloitte role discussed by the user. Prioritize an explainable, useful, demonstrable workflow and evidence-backed engineering claims.
- Demonstrate real Google ADK multi-agent orchestration, real tool calling, structured logging, evaluation, and code-enforced governance. A prompt that merely describes multiple agents does not satisfy this requirement.
- Deliver a simple, polished web interface with document research, citations, follow-up questions, and comparisons across sources.
- The user authorized at most **US$10 total Google service usage** for this build and sending the existing three PDFs to Google model services. Include embeddings, generation, retries/uncertain requests, build, storage and hosting in the tracked estimate. Existing trial credits are not permission to exceed this limit.
- The user explicitly authorized publishing this project's source code and the three existing corpus PDFs to GitHub on 23 September 2026. Publish only the reviewed repository allowlist. This authorization does not include credentials, private derived index, container image containing that index, raw evaluation responses, logs, or unrelated files.
- The original overnight timebox was 2026-09-22 11:06–21:06 UTC. The user subsequently explicitly resumed the automation beyond that deadline. Continue the documented quality fixes and authorized GitHub publication; the original US$10 Google ceiling remains unchanged.
- No public unauthenticated model endpoint and no external messages. Private Google Cloud deployment within the authorized scope is permitted and is coordinated by root.
- Preserve immutable originals. Do not rewrite, rename, delete, or replace the PDFs in the original `RAG Project`.

Already-authorized reversible implementation, fixes, testing, and private deployment preparation should continue without asking for the same permission again. This file adds no new approval gate for that work. Escalate only a real conflict, missing authorization, required external input, or exhausted time/spend constraint; make the concrete result reviewable first.

## 2. Team responsibilities and review

- **Astra:** architecture, implementation coordination, contracts, integration, and technical handoff.
- **GPT-5.6 Sol:** major implementation work.
- **GPT-5.6 Terra:** minor fixes and bounded supporting tasks.
- **Root:** cloud configuration, credentials, spend controls, original-corpus inspection, deployment, and final end-to-end acceptance. Other agents must not provision cloud services or make paid model/embedding calls without root coordination.
- Use explicit file ownership when delegating. Work in parallel only on independent bounded tasks; do not edit another agent's active files. Respect the available concurrency slots, including root and orchestrator.
- A **reviewer-only agent** must inspect material implementation and evidence. The reviewer identifies every concrete discrepancy with severity and location. Fix the findings and obtain re-review before claiming validation.
- A reviewer may later switch to an implementation task, but cannot independently approve their own fixes. Assign a different reviewer for the resulting change.
- Record the review outcome and actual commands/results in `docs/REVIEW_*.md` or the appropriate private evidence record. Distinguish author tests, independent review, live model checks, and final acceptance.
- When blocked or corrected by the user, preserve the current objective and completed work. Do not restart the project or silently abandon required work.

## 3. Current implementation choices

This section describes the current design; it is not a request to add a new framework or service.

- Product name: **Boundary — Document Intelligence**. Its sample domain is cricket rules, illustrating policy-style document research with competition and edition awareness.
- Runtime: Python 3.12, FastAPI, static HTML/CSS/JavaScript, and pinned dependencies in `pyproject.toml`/`uv.lock`.
- Google ADK 2.9.2: a real `SequentialAgent` runs `document_researcher` (`LlmAgent`), `evidence_reviewer` (a separate `LlmAgent` inference), then a deterministic non-model gate agent.
- `GovernedGemini` explicitly selects ADK's formatter-tool path. Preserve clean-process parity tests with the Vertex environment flag both true and false; environment-dependent capability inference previously broke native and deployed forced tool calls. Keep researcher tool MIME/schema handling separate from the reviewer's JSON schema.
- Every model agent uses the same configured low-cost Gemini model. The configured generation target is Vertex `gemini-3.1-flash-lite` at `global`; application-level live generation acceptance is recorded separately. The ingested embedding snapshot uses Vertex `gemini-embedding-001` at `us-central1`, 768 dimensions.
- The researcher has exactly three document tools: `list_sources`, `search_documents`, and `read_evidence`. Tools expose no arbitrary filesystem, shell, URL fetch, or cloud mutation operation.
- The live retrieval path uses a fixed private page/vector JSON index and hybrid ranking (65% normalized BM25, 35% normalized cosine similarity). The explicit lexical mode is for offline/debug use; never silently substitute it for the live vector path.
- The native ADK CLI/dev/eval export constructs a fresh governed pipeline and ledger per invocation. `APP_ALLOW_ADK_CLI=true` is an explicit local-operator opt-in; it is not a substitute for HTTP authentication on a deployed endpoint.
- ADK currently warns that `SequentialAgent` is deprecated in favor of `Workflow`. The pinned version works; treat migration as future work requiring revalidation, not an excuse for a last-minute rewrite.

### Corpus identity and source scope

| Stable source ID | Supplied source | Interpretation |
|---|---|---|
| `junior_2025` | September 2025 junior cricket rules, 52 pages | Multiple age divisions and formats; do not collapse their rules |
| `mcc_2022` | MCC Laws, 2017 Code, 3rd edition 2022, 79 pages | General Laws in the supplied edition |
| `usig_2023` | US Ismaili Games tournament rules, 25 pages | Competition-specific; effective date unspecified |

The `usig_2023` identifier does **not** establish an effective rule date. Do not infer current validity from file metadata or from a filename. Distinguish source disagreement explicitly; do not invent precedence between rulebooks. For example, a tournament runner prohibition and the supplied MCC runner conditions are different scopes, not interchangeable universal rules.

The published corpus manifest is `corpus/manifest.json`. Source paths are confined to its directory, hashes identify immutable inputs, and evidence IDs use `source_id:pNNNN` for one-based original PDF pages. The index loader validates the configured snapshot hash (required in production), unique sources, canonical contiguous pages, vector dimensions and finite values. A corpus change requires a new versioned snapshot with recorded hashes and re-running affected evaluations; it must not silently alter the evidence behind existing results.

## 4. Code-enforced guardrails

### Authentication, authorization, and sessions

- `/api/sources` and `/api/chat` require the configured application token. Use `X-App-Token` so Cloud Run can use `Authorization` for its independent IAM identity token. A local Bearer fallback may remain supported.
- The server assigns the role. Reject client-supplied role elevation, including a `role` field in chat requests; never trust browser role selection.
- Apply manifest role allowlists before retrieval and again before releasing citations. Unauthorized source requests must fail before query embedding or source disclosure.
- The browser keeps the token only in tab memory. Do not put tokens, service-account keys, or credentials in source code, browser storage, screenshots, logs, or command arguments.
- Bind opaque session IDs to the authenticated principal. Unknown, expired, or foreign sessions fail closed.
- Clear researcher draft, review decision, final response, evidence IDs, and counters for each invocation. A released result must match the current request and public session identity.
- Count failed dispatched turns toward history bounds. Do not let repeated failures grow history indefinitely.
- A shared token and a server role are a single-workspace demo boundary, not enterprise per-user authorization. State this limitation honestly.

### Evidence, tools, and response release

- Source documents and user questions are untrusted inputs, never executable instructions. Prompt text in a PDF cannot change tools, roles, budgets, logging, or the release gate.
- Enforce tool/model call limits, bounded queries and evidence size, exact evidence ID validation, and fail-closed errors in code, not only prompts.
- Constrain research function selection using successful per-turn tool state. Preserve room for evidence reading, structured finalization and the separate reviewer; do not let another late search consume their remaining calls. A phase constraint does not mark evidence read or replace the release gate.
- Constrain the outbound read tool's string-item enum to reauthorized IDs issued in the current invocation, on a request-local declaration copy. Omit the read declaration when no ID qualifies; fail closed if a required declaration is absent or the 256-ID bound is exceeded. Include the dynamic schema in input estimation, preserve SDK cache/session isolation, and keep server-side validation authoritative.
- Supported factual claims need non-empty citations to authorized pages actually read in the **current invocation**. Old conversation citations or search snippets alone cannot satisfy the gate.
- Search may expose at most two adjacent same-source pages per hit as continuation references with bounded previews. Prefer an exact requested dotted provision when present; otherwise use the previous page's tail or next page's head. These are explicitly issued candidates, not ranked hits or completed reads. Charge all distinct returned text fragments atomically; identical fragments may deduplicate, but a different later snippet must still count toward the evidence budget.
- `read_evidence` accepts exact canonical IDs issued in this invocation. Resolve and authorize the whole batch before recording reads. Invalid, unissued or unavailable IDs return a generic structured error without partial evidence mutation; corrective suggestions may disclose only revalidated authorized IDs already issued by search. Attempted calls still consume the tool budget. Permit at most one ordinary corrective read per invocation before safe finalization; a later search cannot reset that allowance or reopen formatter repair. Never guess, normalize or substitute page IDs.
- One bounded pre-finalization repair may request an actual read of authorized unread IDs issued by any search in the current invocation. It must preserve room for read, finalization and review, clear repair state every turn, and never mark pages read in a callback. The final gate remains unchanged; a failed or ineligible repair cannot release unsupported claims.
- The separate reviewer checks the original question's requested parts, conditions and exceptions against the proposed claims and read evidence. Required compact coverage maps to strict zero-based claim indices. Empty coverage, inconsistent status and invalid references cannot approve an answer. A missed search is not evidence that a source has no rule. Combined evidence may support a comparison; every cited page must be relevant, but one page need not entail the whole cross-source sentence.
- The deterministic gate checks reviewer outcome and coverage consistency, claim count, citation identity, ACL, and scope rules. Justified insufficient-evidence responses use a separate compatible contract. A failed gate withholds the research draft. The normal web interface shows only the final governed response. Typed coverage cannot prove that the model identified every relevant question part correctly.
- Do not claim semantic grounding from syntactic citation checks. The model reviewer can also miss errors; source-based semantic assessment is part of acceptance. Label an agent assessment accurately and keep the user's later manual verification separate.
- Source panels must expose the supporting text and original page location, not an arbitrary prefix that hides the cited clause.
- The UI validates response shape and citation linkage. Only an explicit successful answer with all governance flags and a passed deterministic gate receives the reviewed badge. Safe abstentions/rejections have neutral labels.
- Render untrusted text as text, not HTML. Preserve the self-only content security policy, anti-framing, no-referrer, nosniff, and no-store API controls.

### Budgets and timeouts

- All paid calls are coordinated by root and reconciled against the remaining US$10 authorization. Do not run a cloud-enabled ingestion or evaluator merely to see if it works.
- Count both researcher and reviewer calls, each custom document-tool call, and billable output including thinking tokens. `usage.tool_calls` counts the three governed document tools; ADK internal formatting calls such as `set_model_response` appear separately in the event trace and are not included in that custom-tool counter. Transport retries must remain explicitly bounded and accounted for; the current SDK configuration uses one attempt.
- Per-request model/tool/token/time limits are configured centrally in `app/config.py`. The current defaults are eight model calls, eight tool calls, an 80,000-token aggregate input limit, a 7,200-token aggregate output limit, 900 output tokens per call, and 120 seconds per request.
- Prospective input usage is estimated, not an exact tokenizer guarantee. Cost estimates and cloud billing budgets are **not hard billing caps**. Reserve conservatively for a dispatched request even if the client times out or the response is lost.
- Generation and embedding SDK calls have finite explicit timeouts. A local timeout or canceled coroutine does not prove that upstream work stopped or that no cost accrued.
- Preserve the current user question alongside the model's search refinement. The refinement defaults to 1,200 characters (maximum 4,000); the combined query defaults to 7,500 characters (maximum 10,000), with explicit overflow failure and no silent truncation. Search previews use query-focused windows, while released citations retain the full source page.
- Disable embedding auto-truncation and reject truncated, missing, non-finite, or dimensionally invalid vectors. Record billable character counts where returned.

### Audit and privacy

- Default logs contain operational metadata only: request/session references, allowlisted agent/tool names, order, durations, counters, statuses, and error categories. Never log raw prompts, PDF passages, tool arguments/results, hidden instructions, secrets, or answers.
- Use the audit allowlist; do not expand it casually. Normalize unknown model-produced tool/agent names instead of recording arbitrary text.
- An audit preflight must be durable before model dispatch. A final audit append must succeed before a successful response is released. An audit-write failure fails closed.
- JSONL writes are append-only, private, completed fully and fsynced. The dedicated metadata logger emits JSON to stdout after the durable append; do not globally enable verbose SDK logging.
- Cloud Run's filesystem is temporary. Local fsync and Cloud Logging are not a durable multi-user conversation database. Observed stage intervals are not distributed tracing spans.
- Detailed evaluation responses are a separate, explicit private diagnostic artifact under `work/`, with restricted file permissions. They are not permitted in default audit logs or public reports.

## 5. Evaluation, evidence, and honest claims

- Preserve deterministic offline tests for meaningful boundaries: authorization, stale evidence/state, budgets, audit failure, output structure, sessions, index integrity, and citation release.
- Offline tests must isolate `.env` and replace SDK/model execution. The real local `.env` may enable paid calls. Do not treat importing a configuration as authorization to dispatch a request.
- `evals/cases.jsonl` is the transparent 20-case development set, with 23 requests including setup turns. It is available for implementation tuning and must never be called a holdout.
- `evals/run.py` is a **custom HTTP harness**. It checks structure, source/page coverage, and expected outcomes, records all planned/executed IDs and failures, and leaves semantic review pending. Setup turns must themselves be valid and retain their session before a follow-up is scored.
- `evals/native.evalset.json` and `evals/native.config.json` use the **native Google ADK trajectory metric** for three development cases/four turns. Tool-order scoring is not answer correctness or semantic grounding. Synthetic metric tests are not live ADK Eval execution.
- Root owns the separate final acceptance set. Keep it untouched until the implementation freeze. If its failures inform fixes, report it subsequently as an acceptance/regression set, not untouched holdout evidence.
- Keep denominators exact. Do not omit difficult cases, discard failed requests, replace tests without disclosure, or present a partial run as a full pass.
- Record dataset and corpus hashes, runtime/model/provider configuration, commands, costs/usage, outcomes, limitations, and reviewer status. Save checkpoints so interruptions do not erase evidence.
- Semantic review must inspect factual support, completeness, competition/edition scope, conflicting evidence, and appropriate abstention. Record whether the reviewer was an agent or a human; do not label agent review as human approval. The user's later manual review is separate and is not a new blocker to already-authorized overnight delivery. Do not use citation presence or keyword matching as a substitute.
- Résumé, README and demo claims must match executed evidence. Do not invent accuracy, latency, cost savings, business impact, user adoption, production deployment, independent review, or enterprise readiness. Use measured aggregates with their denominator, environment and limitations.

## 6. Navigation and safe working commands

Start from this file, then `README.md`, `docs/ARCHITECTURE.md`, and the relevant implementation/tests. Use `rg` for targeted discovery rather than scanning private artifacts broadly.

| Location | Purpose |
|---|---|
| `app/config.py`, `app/models.py` | Runtime settings and typed contracts |
| `app/ingest.py`, `scripts/ingest.py` | Immutable-source extraction and optional paid embedding |
| `app/index.py`, `app/tools.py` | Authorized retrieval and run ledger |
| `app/agents.py`, `app/gate.py` | Real ADK agents and deterministic release |
| `app/service.py`, `app/main.py`, `app/audit.py` | Sessions, HTTP auth, audit and API |
| `app/agent.py` | Explicitly enabled native ADK CLI/dev/eval export |
| `web/` | Static interface; no external frontend dependency required |
| `tests/`, `evals/` | Offline boundary tests and clearly labeled evaluators |
| `docs/REVIEW_*.md` | Reviewer findings, corrections and evidence limits |
| `deploy/README.md`, `deploy/prepare_context.py`, `Dockerfile` | Root-owned private deployment workflow |
| `corpus/manifest.json`, `corpus/pdf1.pdf`, `corpus/pdf2.pdf`, `corpus/pdf3.pdf` | User-authorized published inputs; exact files allowed in git |
| `data/`, `.env`, `.adk/`, `work/` | Private index, credentials, runtime/evaluation artifacts; excluded from git |

Use the relocated project path; the old `adk-document-assistant` directory no longer exists. Preserve shell quoting around the space in `ADK RAG`.

```bash
cd '/Users/vineetkumar/Documents/Work/RAG/ADK RAG'
uv sync --extra dev
.venv/bin/python -m pytest -q
node --test tests/web_response_validator.test.js
.venv/bin/python evals/run.py                 # Plan only; no model calls
.venv/bin/python evals/build_native.py        # Build/validate native artifacts only
```

Use `python -m pytest`, not an unrelated globally resolved `pytest` script. If the project moves again, regenerate editable installs/entrypoints with the new path. Do not overwrite the private `.env` with the sample; `.env.example` must remain usable with authentication and model calls disabled by default.

```bash
# Local server; launching is not permission for unbudgeted paid chat requests.
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Offline extraction only, explicitly separate from the live index.
.venv/bin/python -m app.ingest --manifest corpus/manifest.json \
  --output work/offline-index.json --embedding-provider lexical
```

Root coordinates commands that use `--embedding-provider vertex`, `evals/run.py --execute`, `APP_ALLOW_ADK_CLI=true ... adk eval`, cloud builds/deployments, or any configured live `/api/chat` request. They incur or can incur authorized Google usage and require current accounting, not a new permission ritual when already coordinated.

Use `work/` for scratch files. Keep immutable originals in the separate prototype untouched. Only the three approved PDF copies and their manifest may enter git; keep embeddings, credentials, sessions and sensitive logs excluded. Use the explicit deployment upload allowlist; do not upload the whole workspace. Do not perform unrelated changes, destructive cleanup, or deletion of existing BigQuery resources. Stop only processes created for this task and identified precisely.

## 7. Private cloud deployment

Follow `deploy/README.md`; root owns its resources and release actions. The current target is IAM-private Cloud Run with a dedicated runtime service account, Secret Manager application token, private image/index artifacts, minimum instances zero, maximum instances one, one worker and bounded timeouts.

- Keep Cloud Run IAM authentication enabled and application-token authentication in place. Do not create a public model proxy or share an unauthenticated invocation URL.
- Use a private prebuilt index, pinned by hash. Do not put PDFs or local credentials in the image or build context.
- Use the authenticated local Cloud Run proxy or authorized IAM access for demonstrations. A private deployment is not a publicly accessible recruiter link.
- Store deployment digest, configuration, service status and browser/API verification separately from local results. A successful build is not proof that the application works end to end.
- Preserve existing unrelated Google resources and permissions. Do not create service-account key files or broaden access to solve a routine deployment error.

## 8. Done criteria and exclusions

A completion claim must identify what was actually achieved:

1. The local interface works with the fixed authorized corpus, including a sourced answer, a follow-up, a cross-source comparison, a safe abstention and rejection of invalid access/citation behavior.
2. Real ADK researcher/reviewer execution and actual document tool calls are observable in metadata evidence; the gate controls the released response.
3. Meaningful offline tests pass and reviewer findings are corrected and re-reviewed. Live model evaluation and reviewer semantic assessment are recorded with exact coverage, reviewer type and remaining failures; any pending user manual review is stated separately.
4. Default logs and distributed artifacts respect the privacy boundary; original PDF hashes remain unchanged; configuration and estimated Google usage are reconciled within the authorized ceiling.
5. The README, architecture, working rules, evaluation instructions, review evidence and limitations match the implementation. The user can run and demonstrate the result without reconstructing undocumented steps.
6. If private cloud deployment completes within the timebox, verify the deployed browser→API→retrieval→model→review→gate path and record it. If deployment cannot complete, report the verified local result and precise cloud blocker without pretending deployment passed.

Explicit exclusions: production/enterprise readiness certification; publication outside the authorized source/PDF scope; multi-tenant identity/SSO; durable multi-instance conversation storage; globally atomic billing caps; arbitrary uploads/web browsing/shell tools; automatic corpus updates; modification of the original prototype, policy/KPI project or existing BigQuery resources; and unmeasured business-impact or résumé claims.

Do not mark an incomplete evaluation, unreviewed material change, or untested deployment as validated. Report remaining work candidly and continue authorized fixes while time and budget remain.
