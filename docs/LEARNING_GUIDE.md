# Understand and explain Boundary

This guide teaches the ideas through this project's code. Start with one question: **How does the app know that a returned claim came from a document the user was allowed to read?** Follow that question through the files before memorizing framework names.

## A 30-minute reading path

1. Read `README.md` and `docs/ARCHITECTURE.md` for the user problem and request flow.
2. Open `app/models.py`: inspect `ResearchDraft`, `ReviewDecision`, `ChatResponse`, and the source/page records.
3. Open `app/agents.py`: find the researcher, reviewer, shared Gemini configuration and deterministic gate agent.
4. Open `app/tools.py` and `app/index.py`: follow a source-restricted query through retrieval and `read_evidence`.
5. Open `app/gate.py`: trace a cited claim that succeeds and a stale or unauthorized evidence ID that fails.
6. Open `app/service.py` and `app/audit.py`: inspect per-turn state, session ownership, audit preflight and release.
7. Run the offline tests, then inspect the development evaluation plan. Read the separate live results before describing measured performance.

## The core concepts, mapped to code

| Concept | Plain meaning | Boundary implementation | Why it matters |
|---|---|---|---|
| ADK | A framework that runs agents and exposes their events, sessions and tools | `app/agents.py`, `app/service.py` | The workflow has executable agent orchestration, not only a prompt describing roles |
| `LlmAgent` | A model configured with a job, instructions, tools and an output contract | `document_researcher` and `evidence_reviewer` | The researcher gathers evidence; a separate inference reviews it |
| Sequential orchestration | Run steps in a fixed order | `SequentialAgent` in `build_agent()` | The reviewer runs after the research draft; the gate runs after the review |
| A tool | An ordinary function the model can request through a declared interface | `list_sources`, `search_documents`, `read_evidence` | The model can request evidence without obtaining arbitrary filesystem or cloud access |
| Structured output | A response that must fit a defined schema | Pydantic models in `app/models.py` | Missing claims, invalid verdicts and unexpected fields fail validation instead of becoming prose guesses |
| A deterministic agent | A workflow step that runs code without asking an LLM to decide | `DeterministicGateAgent` and `apply_gate()` | Citation identity and access rules are enforced even when the model wants to answer |
| RAG | Retrieve relevant document content, then generate using that evidence | `IndexRepository.search()` → document tools → researcher | The answer has a bounded source context rather than relying solely on model memory |
| An embedding | A numeric representation used to rank similarity | Vertex document/query embeddings, 768 values per vector | It retrieves semantically related pages; similarity alone does not prove relevance or truth |
| Cosine similarity | Compare the direction of two numeric vectors | `_cosine()` in `app/index.py` | It contributes the dense component of the local hybrid rank without a separate database |
| BM25 | Rank pages by matching words, accounting for word rarity and page length | `_bm25_scores()` in `app/index.py` | Exact format names and numbers can matter more than a broad semantic resemblance |
| Hybrid ranking | Combine word matches with vector similarity | Normalized BM25/cosine scores in `IndexRepository.search()` | It balances exact constraints and paraphrases; the score is a rank, not a probability that an answer is correct |
| A session | Conversation state across requests | `ChatService` plus `InMemorySessionService` | A follow-up can refer to the previous subject, while each turn still retrieves fresh evidence |
| An event | A record emitted during an agent invocation | `Runner.run_async()` events | The app can observe actual agent authors and function-call names |
| A citation gate | Code that checks which evidence an answer refers to | `app/gate.py` | A fabricated or old evidence ID cannot become an authorized source citation |
| Semantic support | Whether the source actually justifies the claim | Reviewer inference plus source-based semantic assessment, with reviewer type recorded | A valid page number can still accompany a wrong answer |
| Fail closed | Withhold a response when a required check cannot complete | Schema, ACL, budget, audit and final-response checks | An error cannot silently become an apparently verified answer |

A model deciding to call a tool is still probabilistic. The function's permission checks, input bounds and return shape are ordinary code. Keep this distinction clear when explaining governance.

## Follow one request end to end

Suppose the question is: “In the supplied US Ismaili Games rules, how many overs may one bowler bowl?”

1. The browser sends the message to `/api/chat` with `X-App-Token`. It does not choose the role. `authenticated_principal()` checks the token, and the server supplies the configured role.
2. `ChatService.chat()` resolves an opaque session owned by that principal. The audit preflight must succeed before model work. A fresh ledger tracks this request's evidence and limits.
3. ADK runs the researcher. The intended tool path is to list the available scopes, search the authorized collection, and read the selected page. Source filters are checked before embedding/retrieval.
4. The researcher returns a `ResearchDraft` of claims and evidence IDs. The draft is not yet an answer the web user receives.
5. The reviewer performs a separate model inference over the original question, draft and evidence. It maps requested question parts to draft claims and checks support, conditions, scope and edition handling.
6. The deterministic gate requires the reviewer to pass, the coverage mapping and checked claim count to be consistent, and each citation to refer to an authorized page read during this invocation. It also applies explicit source-scope rules. A valid mapping cannot prove that the model understood every requested part correctly.
7. The service rejects stale request/session identity, writes final metadata, and returns the governed response. The UI validates the response again, renders claims as text, and opens the cited page excerpt on demand.

This sequence is the design. The run's actual event metadata and evaluation record establish what happened in a particular execution. Do not infer a successful tool path from the diagram alone.

## Why use two model agents?

Separating research and review makes the responsibilities inspectable and allows the reviewer to reject a draft. It also costs another inference and increases latency. Both agents use the same model, so their errors can be correlated; “separate reviewer” does not mean statistically independent verification. The deterministic gate and source-based assessment are additional boundaries, not proof that all hallucinations disappear.

The resumed evaluation exposed a narrower lesson: structured question-part checks and valid citations still missed section-level scope. A cited junior-rule page contained genuine bowling limits, but its section applied to two-day games for specified boys' formats. The answer omitted that qualification. Even the initial reviewer-only source assessment missed it; a contextual re-check corrected the targeted result from 4/5 to 3/5 semantic passes and preserved the earlier record. In an interview, explain this as an observed limitation and the importance of checking governing headings across pages—not proof that adding review fields makes answers reliable.

The final browser checks provide a second lesson: both attempted first turns failed validation, so neither dependent follow-up ran. Successful API/native cases and passing offline tests did not establish a reliable live browser walkthrough. The next work should identify the exact failing schema boundary on that original prompt, retain fail-closed release checks, and repeat the full interaction after a reviewed fix. Keep this availability problem separate from the known section-scope error and provider resource exhaustion; they require different evidence and remedies. The prioritized remaining work is recorded in [QUALITY_CONTRACT.md](QUALITY_CONTRACT.md).

A useful interview answer is: “I chose a fixed researcher→reviewer→gate workflow because the order is a requirement of the product. I did not need an open-ended team of agents deciding their own permissions.”

## Why a page index rather than a vector database?

The supplied corpus has only three documents and 156 pages. The included manifest and PDFs make extraction reproducible, while a fixed JSON index is easy to inspect, hash, package privately for runtime and query with dense/lexical hybrid ranking. It avoids provisioning a database merely to demonstrate similarity search.

The tradeoff is limited scale and update handling. Every query compares against the eligible pages; changing the corpus requires rebuilding and validating a new snapshot. A larger system would need an index suited to its scale, transactional metadata/ACL updates, retention policy and operational monitoring. A separate vector database would not remove the need for access checks or answer evaluation.

Pages preserve a simple source locator, but they are not perfect semantic chunks. Tables and multi-page rules can be difficult to extract or retrieve. The current pipeline combines normalized BM25 and cosine scores, preserves the current question alongside model search refinements, and selects a query-focused search preview. These changes address observed query drift and previews that hid a relevant section below the page opening; they do not prove that the model selects the right evidence.

The current pipeline uses PDF text extraction; it does not claim full layout understanding. More sophisticated parsing/chunking should be justified by measured retrieval failures.

Rules can continue onto another page. Search therefore exposes adjacent same-source pages with bounded context previews: an exact requested provision when present, otherwise the previous page's tail or next page's head. The model must still request their actual contents through `read_evidence`. Issuing an ID, returning a snippet, and recording a full read are three distinct states. An invalid read consumes its attempted tool call and returns only previously issued authorized suggestions. One ordinary corrected read may follow per invocation; a new search cannot reset that allowance, and repeated failure must finalize safely within the same budget.

## What each Google Cloud service does

| Service | Role in this project | What it does not solve |
|---|---|---|
| Vertex AI generation | Runs the configured Gemini model for both LLM agents | It does not enforce the app's document ACL or verify every factual claim |
| Vertex AI embeddings | Creates document/query vectors | It does not decide rule precedence or guarantee an answer exists |
| Cloud Run | Hosts the same containerized FastAPI/static app behind IAM | It does not make in-memory sessions durable across restarts |
| IAM and runtime service account | Control who can invoke the private service and what the workload can access | The app still needs its own role/source checks |
| Secret Manager | Supplies the application token without putting it in the image | It is not a multi-user identity provider |
| Cloud Storage | Keeps a private derived index/manifest snapshot | Publication of the repository PDFs does not make the generated index, credentials or runtime artifacts public |
| Artifact Registry | Stores the private runtime image | The image remains sensitive because it contains derived source text/index data |
| Cloud Build | Builds the explicit allowlisted context | An incorrectly selected build context can still upload private files |
| Cloud Logging | Receives allowlisted operational JSON from stdout | It is not the conversation database and must not contain raw source text |

Generation is configured for `global`, while embeddings and the runtime use `us-central1`. These are separate configuration choices. Do not describe this as a strict regional data-residency solution.

## Important implementation lessons

**Configuration must reach the SDK.** Reading `.env` into a Pydantic settings object does not automatically populate a provider's environment-based client. The model client is explicitly configured with Vertex mode, project and location, and an offline regression checks the resulting client. This was an integration issue found before a successful application-level generation run.

**Validate the whole model request when estimating input.** ADK requests can contain instructions, tool declarations and structured-response schemas, not just user text. Serialization and accounting must handle those actual SDK types. An estimate is useful for a preflight bound; it is not an exact tokenizer or a billing invoice.

**Reserve the whole workflow.** A researcher can use its entire call allowance searching and leave no inference for review. Boundary constrains required tool phases through the model's function-calling configuration, prevents a late new search that cannot fit a read plus finalization, and reserves a separate reviewer call. The code sets the HTTP ADK `RunConfig` explicitly; a value in `.env` is not automatically an SDK environment variable. Requiring a tool path does not solve an answer that retrieves the wrong age division or format, so source-based assessment remains necessary.

**Repair before release, within the same budget.** The researcher can cite a search result that it never opened. A `before_tool_callback` can intercept its structured finalization once and require an actual read of the missing authorized pages. It reserves space for the read, revised draft and reviewer. This repairs a missing action; it does not declare a citation valid or bypass the final gate. Compare the pending repair IDs in `app/agents.py` with the only successful read operation that updates evidence state in `app/tools.py`.

**Expose valid choices before a tool call.** The researcher can also invent a page ID and waste its remaining calls correcting it. The outbound read schema now enumerates only authorized IDs already issued in the current invocation. This is a request-local copy, so one turn's choices cannot remain in a later turn's tool schema. The server still checks every actual argument. A constrained declaration can reduce invalid choices; it does not decide which evidence answers the question.

**Test a clean process, not only a warm local server.** ADK inferred schema/tool support from the process Vertex flag, while local dotenv settings configured the client separately. Cloud and native runs therefore took a different formatting path and failed. `GovernedGemini` now selects that capability explicitly, with clean true/false environment tests. This is why configuration parity belongs in deployment validation.

**Errors still have state and possibly cost.** A failed dispatched turn counts toward the history bound. A transport timeout retains a conservative cost reservation because the client cannot prove upstream cancellation. An old final response must never be reused when a new invocation fails to produce one.

**Logs are part of the design.** A successful code path that writes `.info()` to an unconfigured logger may emit nothing. The audit test checks real JSON stdout after the durable file write, rather than making a test logger visible and assuming production behaves the same way.

## Practice questions

- What is the difference between the ADK reviewer agent and the deterministic gate? Open the two relevant classes and answer with one concrete failure each catches.
- Why must ACL checks happen before retrieval as well as before response release?
- Why are search snippets insufficient for the final evidence gate?
- What happens to a follow-up when the session reaches its turn limit or the process restarts?
- Why can a citation check pass while an answer is wrong?
- What would change for 100,000 documents, 50 users, or daily corpus updates?
- Which cost limits are enforced by the application, and which remain estimates coordinated by the operator?
- Which failures in the final evaluation were fixed, and which remain limitations? Use the actual final report, not a hypothetical answer.

For the walkthrough see `docs/DEMO_GUIDE.md`. For conditional résumé wording and an interview narrative see `docs/PORTFOLIO_NARRATIVE.md`. Read `AGENTS.md` before changing guards or running paid evaluations.

Tool-count interpretation: `usage.tool_calls` counts the three custom document tools. ADK may also emit an internal `set_model_response` formatting call in the trace; it is not an additional document retrieval and is not included in that custom-tool counter.
