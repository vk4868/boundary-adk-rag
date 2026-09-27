> Historical Vertex/Cloud Run baseline, retained for provenance. Not current local setup or local validation.

# Boundary — Document Intelligence

A governed document research assistant built with Google ADK, Vertex AI and FastAPI. Ask about a rule, compare competing rulebooks, or follow up on an earlier answer. Boundary retrieves authorized source pages, runs a second agent to review the evidence, and releases a response only after deterministic citation checks.

![Boundary document research interface](docs/assets/boundary-demo.png)

The included sample collection contains three cricket rulebooks, making scope a real reasoning problem: general MCC Laws, junior competition formats, and US Ismaili Games tournament rules can differ. For example, a tournament's runner prohibition must not silently replace the conditional runner provisions of the supplied MCC Laws.

**Project status:** intermediate portfolio demo. Offline tests and live acceptance are recorded separately; see `docs/` and private `work/` evidence. This is not a production compliance or policy decision system. The repository includes the manifest and three user-authorized source PDFs so another developer can reproduce ingestion; generated indexes, credentials, logs, sessions and raw evaluation responses remain private.

> **Measured limitation:** in the latest paced deployed acceptance/regression run, **5 of 10 final cases passed source assessment**. One returned answer omitted junior-format restrictions; four final cases were unavailable because of provider resource exhaustion. Ten of eleven planned turns ran because a failed setup prevented its follow-up. Both latest browser-demo attempts also failed during workflow validation. Stronger structural checks have not established a reliable live demo. See [RESULTS.md](RESULTS.md).

## What it demonstrates

- A real ADK `SequentialAgent`: a tool-using researcher, a separate reviewer `LlmAgent`, then a deterministic gate agent.
- Three typed tools: `list_sources`, `search_documents`, and `read_evidence`.
- Actual Vertex embeddings with a fixed page/vector snapshot and local BM25/cosine hybrid retrieval; optional explicitly labeled lexical mode for offline work.
- Source role allowlists applied before retrieval and rechecked at release; current-invocation evidence IDs advertised in request-local tool schemas; actual page reads required before citation release.
- Typed reviewer checks for question-part coverage, conditions and unsupported absence claims; deterministic validation rejects inconsistent or stale outputs.
- Authenticated web research with follow-up sessions, source evidence panels, citations, and visible run counters.
- Metadata audit logs, bounded model/tool calls, token accounting including thinking, and privacy-aware evaluation evidence.

Measured outcomes and retained failures are in [RESULTS.md](RESULTS.md). The diagram and exact boundaries are in [ARCHITECTURE.md](HISTORICAL_CLOUD_ARCHITECTURE.md). For a code-guided explanation, use [LEARNING_GUIDE.md](LEARNING_GUIDE.md); for setup and the five-minute walkthrough, use [DEMO_GUIDE.md](HISTORICAL_CLOUD_DEMO.md). [PORTFOLIO_NARRATIVE.md](PORTFOLIO_NARRATIVE.md) contains ready-to-use résumé bullets and interview questions. Project working rules are in [AGENTS.md](../AGENTS.md).

## Local setup

Python 3.12 and `uv` are the tested runtime. Dependencies are pinned in `pyproject.toml` and `uv.lock`.

```bash
uv sync --extra dev
cp -n .env.example .env  # First setup only; preserve an existing private file.
```

Keep an existing configured `.env`; do not replace it with the offline sample. Configure the application token in `.env` without committing it. The [demo runbook](HISTORICAL_CLOUD_DEMO.md#reproduce-the-local-setup) lists the required provider, project, embedding and index-hash settings and explains ADC setup. The browser sends `X-App-Token`, leaving `Authorization` available for Cloud Run IAM. Local development is bound to `127.0.0.1`; do not expose an unauthenticated model endpoint.

The configured model target is Vertex `gemini-3.1-flash-lite` in `global`; embeddings use `gemini-embedding-001` in `us-central1`, 768 dimensions. Both model agents use the same configured generation model. Actual generation is opt-in through `APP_ENABLE_MODEL_CALLS` and the provider settings. The root operator controls cloud authentication and spend.

The included `corpus/manifest.json` references the three repository PDFs and defines stable source IDs, titles, supplied versions, competition scopes, allowed roles, paths and expected SHA-256 hashes. PDF paths must remain beneath the manifest directory. Ingestion reads the originals without modification, so a developer can reproduce either the offline lexical snapshot or a Vertex embedding snapshot with their own configured Google project.

```bash
# Offline extraction and lexical index (no cloud calls)
.venv/bin/python -m app.ingest --manifest corpus/manifest.json \
  --output work/offline-index.json --embedding-provider lexical

# Real Vertex embeddings; this command incurs Google service usage
.venv/bin/python -m app.ingest --manifest corpus/manifest.json \
  --output data/index.json --embedding-provider vertex \
  --project YOUR_PROJECT --location us-central1 \
  --embedding-model gemini-embedding-001 --embedding-dimensions 768
```

Set `APP_INDEX_PATH`, `APP_INDEX_SHA256`, and `APP_EMBEDDING_PROVIDER` to the intended snapshot. A Vertex snapshot cannot silently fall back to lexical retrieval. The ingestion tool disables automatic truncation and rejects truncated or malformed vectors. Retrieval preserves the current user question, combines it with a bounded model refinement, and selects query-focused search previews. `APP_MAX_SEARCH_QUERY_CHARS=1200` limits the refinement; `APP_MAX_EFFECTIVE_SEARCH_QUERY_CHARS=7500` limits the combined query (supported maximum 10000). Overflow fails explicitly. One real Vertex query embedding is combined with local lexical ranking; the index remains unchanged.

```bash
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open the local URL, connect with your workspace token, and ask a question. Tokens stay in the tab's memory. The PDF itself is never served; authenticated evidence responses display extracted text and the original page location.

## Try the workflow

These are walkthrough steps, not a current success claim. The earlier browser sequence passed, but both attempts on the latest revision failed before an answer; review [current results](RESULTS.md) before relying on a live interview demo.

1. Ask: “In the supplied US Ismaili Games rules, how many overs may one bowler bowl?”
2. Open the numbered citation and inspect the source page text.
3. Ask: “Can an injured batter have a runner in that tournament?”
4. Follow up: “How does that compare with the MCC Laws?”
5. Expand research activity to inspect model/tool counts and the deterministic gate outcome.
6. Ask a question outside the rulebooks to observe abstention.

Each statement is scoped to the supplied editions. “Evidence reviewed” means the reviewer and deterministic release checks passed; it is not a promise of semantic correctness.

## Verification and evaluation

```bash
# Fully offline tests; test settings isolate the live .env
.venv/bin/python -m pytest -q
node --test tests/web_response_validator.test.js

# Evaluation plan only; no endpoint or model calls
.venv/bin/python evals/run.py
```

The custom HTTP development harness contains 20 cases/23 turns and records structural integrity, expected page/source coverage, and explicit source-review rubrics. It does not use an LLM judge or label page matches as factual correctness. See [evals/README.md](../evals/README.md). The separate acceptance set was first used after the development freeze; integration failures informed a compatibility correction, so subsequent runs are labeled acceptance/regression. Evaluation files with raw responses remain private under `work/`.

The [native ADK evaluation artifact](../evals/README.md#native-adk-evaluation-artifact) has three development cases and four turns. The latest live native run passed all three tool-order cases across four turns. Source assessment credited two of three final answers as complete; the answerable follow-up was safely rejected. Tool-order scoring is not semantic validation. The custom HTTP harness is the separate 20-case/23-turn development evaluation and must not be described as native ADK Eval execution or semantic validation.

## Known limits

This is a single-workspace demo with a shared access token and server-assigned role, not an enterprise identity system. Conversation state is bounded and temporary. A restart may end a session. The constrained deployment avoids claiming durable multi-instance sessions or globally atomic spend accounting. PDFs use text extraction rather than full layout/table understanding. A fixed corpus does not automatically reflect the newest rules. Model-based review can miss errors, and conservative deterministic scope checks can reject otherwise valid wording.

ADK 2.9.2 currently supports this `SequentialAgent` API but emits a deprecation notice recommending `Workflow`. Dependencies are pinned; a future migration requires re-running orchestration and governance tests.

The source code, manifest and three supplied PDFs are published under the user's explicit authorization. Original author and copyright notices in the documents must remain intact; this documentation does not assert an additional license for the source documents. The derived vector index, credentials, runtime logs, sessions and raw evaluation artifacts are intentionally excluded. The original RAG prototype and the separate policy/KPI project remain unchanged.

## Private cloud access and cost

Follow [deploy/README.md](../deploy/README.md) for the private build and runtime configuration. For the verified IAM-private service, `gcloud run services proxy boundary-adk --project=sql-bigquery-502206 --region=us-central1 --port=8085` opens an IAM-authenticated local proxy; the app still requires its own token. This is not a public recruiter URL. [COSTS.md](COSTS.md) separates usage estimates from billing caps. Live/deployed success and final metrics remain tied to the recorded acceptance evidence.

Tool-count interpretation: `usage.tool_calls` counts the three custom document tools. ADK may also emit an internal `set_model_response` formatting call in the trace; it is not an additional document retrieval and is not included in that custom-tool counter.
