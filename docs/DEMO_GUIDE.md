# Run and explain Boundary locally

## Prerequisites

Start Ollama on the laptop, with `granite4.2:8b` and `embeddinggemma:latest` installed. Run all commands from this repository's root. Use `uv sync --extra dev` to install the pinned Python dependencies. No Google credentials or OpenAI API key are required by the local runtime.

## Private local configuration

Create `.env` from `.env.example` only if it does not exist. Set these fields locally:

| Setting | Value |
|---|---|
| `APP_MODEL_PROVIDER` | `ollama` |
| `APP_MODEL` | `granite4.2:8b` |
| `APP_ENABLE_MODEL_CALLS` | `true` |
| `APP_OLLAMA_BASE_URL` | `http://127.0.0.1:11434` |
| `APP_EMBEDDING_PROVIDER` | `ollama` |
| `APP_EMBEDDING_MODEL` | `embeddinggemma:latest` |
| `APP_EMBEDDING_DIMENSIONS` | `768` |
| `APP_INDEX_PATH` | `data/index-ollama.json` |
| `APP_INDEX_SHA256` | SHA-256 of the newly generated local index |
| `APP_AUDIT_PATH` | `data/audit/local-events.jsonl` |
| `APP_TOKEN` | A private random workspace token; never publish it |

Keep the local request/context limits from the template unless a measured test warrants a change. Do not reuse old Vertex configuration or embedding vectors. PDFs and query vectors must use the same recorded embedding model/method. The ingestion command and hash command are in the main README.

## Application interface

```bash
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Visit `http://127.0.0.1:8000`. Connect with the private workspace token. `/health` should show `model_provider: ollama`, `model: granite4.2:8b`, and an Ollama retrieval index. A successful health check proves configuration and index readiness, not answer quality.

## ADK developer interface

```bash
PYTHONPATH="$PWD" APP_ALLOW_ADK_CLI=true .venv/bin/adk web \
  --host 127.0.0.1 --port 8001 \
  --session_service_uri memory:// --artifact_service_uri memory:// \
  --log_level warning app
```

Visit `http://127.0.0.1:8001` and select `app`. The native export executes the governed ADK workflow with per-invocation state. Inspect Events and Traces to explain actual agent/tool calls. Intermediate drafts can appear in this developer inspector; use the custom UI when demonstrating final-answer release to an end user. Memory-backed inspector sessions disappear when the server stops.

## Interview walkthrough

Consult current [local results](RESULTS_LOCAL.md) before selecting a demonstrated flow. These are suggested scenarios, not claims that every run succeeds:

1. Ask how many overs a bowler may bowl in a full 20-over US Ismaili Games innings.
2. Open the returned citation and inspect the actual source text/page.
3. Ask the runner-rule comparison as a standalone question. The recorded cross-document follow-up hit a context preflight; explain that limitation instead of promising a successful follow-up.
4. Ask a question outside the documents and explain safe withholding. The final recorded unavailable-result case was rejected with no claims; secret-extraction handling still had an operational error, so do not promise that every refusal completes cleanly.
5. Show an offline gate test rejecting a fabricated or unauthorized citation. Do not imply an LLM's refusal alone enforces permissions.
6. Explain the distinction between agent review, deterministic validation, and source-based answer assessment.

A concise explanation: “I rebuilt my document RAG project with ADK to learn how to orchestrate tool use, agent roles, and state. Ollama provides local inference; ADK runs a researcher and reviewer; Python checks citations and access before releasing the final answer.”

The researcher/reviewer share local model weights with different prompts. That is a multi-agent workflow, not two independently trained models. Source validation blocks nonexistent or unauthorized references, but does not guarantee correct interpretation of genuine source pages.

## Verification and stopping

`python evals/run_local.py` prints a plan only. Add `--execute` using the project's `.venv/bin/python` for the bounded local HTTP regression. Preserve complete denominators and failures. Each executed run needs a new `--output work/<run-name>.json`; the runner refuses to overwrite an existing file. Source review is separate from automatic checks.

Stop each server with Ctrl-C in its own terminal. Do not stop unrelated Ollama clients or alter the original RAG projects. For historical cloud information use `HISTORICAL_CLOUD_DEMO.md`; those resources are not part of the local demo and their retirement is a separate scoped action.
