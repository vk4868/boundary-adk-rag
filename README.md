# Boundary — Local Document Research with Google ADK

A local RAG portfolio project using **Google ADK for multi-agent orchestration**, **Granite 4.2 through Ollama** for generation, and **EmbeddingGemma through Ollama** for embeddings. A researcher gathers document evidence, a separate reviewer checks the proposed answer, and a deterministic Python gate enforces citations and source permissions.

This rebuild focuses on learning ADK tool calling, agent/session state, separate agent responsibilities, evaluation, and governance. The application, PDFs, vector index, inference, and audit logs run on the laptop. No hosted inference API key or Google Cloud project is needed for the local profile.

**Status:** local migration implemented; final development regression passed 4/6 cases, and browser answer/citation checks passed while follow-up handling failed. Exact validation and limitations are recorded in [RESULTS_LOCAL.md](docs/RESULTS_LOCAL.md). Do not interpret historical screenshots or cloud evaluation numbers as current local proof. This is an intermediate learning/portfolio prototype, not a production decision system or a guarantee of factual correctness.

## Workflow

```text
Question → ADK researcher → local search/read tools
         → ADK reviewer → deterministic gate → cited answer
```

- The two model agents share the same local Granite 4.2 model but have separate roles and invocations.
- Three Python tools list authorized sources, search the local index, and read exact source pages.
- Retrieval combines BM25 and local embedding similarity. The corpus contains three immutable cricket rulebooks, 156 pages, with distinct competition/edition scopes.
- The gate rejects invalid/unauthorized citations and unread evidence. A real source citation does not prove that a model interpreted it correctly.
- The local UI provides citations, source text, follow-ups, and run counters. Audit logs retain metadata without prompts, answers, or document passages.

Gemma 4 remains selectable with `APP_MODEL=gemma4:latest`, but the active demo uses Granite after the retained local comparisons. See the exact results and limitations before demonstrating it.

## Setup

Use Python 3.12, `uv`, and Ollama. The tested machine has 24 GiB RAM; actual context size and other running applications affect memory and latency. The model tags below are local model names, not cloud models.

```bash
uv sync --extra dev
ollama pull granite4.2:8b
ollama pull embeddinggemma:latest
cp -n .env.example .env
```

Preserve an existing private `.env`. Configure it for the local profile following [DEMO_GUIDE.md](docs/DEMO_GUIDE.md). The template disables generation until explicitly enabled and contains no application token. Keep credentials, derived indexes, runtime sessions and raw evaluation output out of git.

Build a **new** local embedding index from the included PDFs; never reuse a Vertex vector index with EmbeddingGemma:

```bash
.venv/bin/python -m app.ingest --manifest corpus/manifest.json \
  --output data/index-ollama.json --embedding-provider ollama \
  --embedding-model embeddinggemma:latest --embedding-dimensions 768
shasum -a 256 data/index-ollama.json
```

Set `APP_INDEX_PATH=data/index-ollama.json` and `APP_INDEX_SHA256` to the printed hash in `.env`. Then start the custom interface:

```bash
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000` and connect using the private `APP_TOKEN`. The token remains in tab memory. Local model requests use `http://127.0.0.1:11434`; there is no cloud fallback.

To inspect the actual ADK agents and events, use a separate terminal:

```bash
PYTHONPATH="$PWD" APP_ALLOW_ADK_CLI=true .venv/bin/adk web \
  --host 127.0.0.1 --port 8001 \
  --session_service_uri memory:// --artifact_service_uri memory:// \
  --log_level warning app
```

Open `http://127.0.0.1:8001` and select `app`. ADK's developer UI is local operator tooling and exposes intermediate agent events; the custom application shows only governed final responses. Keep the developer UI bound to loopback.

## Verification

```bash
.venv/bin/python -m pytest -q
node --test tests/web_response_validator.test.js
# Local regression plan; no model calls:
.venv/bin/python evals/run_local.py
# Explicitly run against the local Ollama application:
.venv/bin/python evals/run_local.py --execute
```

The bounded local regression runner refuses a server configured with a non-Ollama model/index. It refuses an existing output file, preserves failed turns, and records source-assessment as pending: structural checks and tool trajectories are not semantic accuracy. Detailed responses go to private `work/`; aggregate findings belong in [RESULTS_LOCAL.md](docs/RESULTS_LOCAL.md).

See [architecture](docs/ARCHITECTURE.md), [demo guide](docs/DEMO_GUIDE.md), [interview explanation](docs/PORTFOLIO_NARRATIVE.md), and [working rules](AGENTS.md).

## Scope and limitations

The project is a single-workspace demonstration with a shared local token, bounded in-memory sessions, and a fixed source corpus. Local models can be slow, abstain unnecessarily, or misinterpret evidence; measure these outcomes and preserve failures. The reviewer uses the same model family and can share the researcher's mistakes. The deterministic gate checks defined contracts and references, not universal truth.

Model inference has no paid per-token API charge in this local configuration; it consumes laptop resources and electricity. Existing historical cloud resources are separate and were not deleted by this migration. The original `RAG Project` and `policy-kpi-rag` remain untouched.

The original cloud experiment and its results are preserved under [historical README](docs/HISTORICAL_CLOUD_README.md), [historical architecture](docs/HISTORICAL_CLOUD_ARCHITECTURE.md), [historical demo](docs/HISTORICAL_CLOUD_DEMO.md), and dated review reports. Those instructions describe the previous version and are not the active setup.

The three PDFs are included under the user's publication authorization; their original notices remain intact. No additional license for those documents is asserted. Private derived indexes, credentials, logs, and raw evaluation responses are excluded from publication.
