# Boundary: local ADK RAG interview guide

## The project in one minute

“I already had a document RAG project. I rebuilt its workflow with Google ADK to understand how an agent framework coordinates tool calls, state, and multiple agents. A researcher finds and reads document evidence, a separate reviewer checks the proposed claims, and a deterministic Python gate validates citations and source permissions before releasing an answer. The current local workflow uses Ollama for generation and EmbeddingGemma for embeddings.”

The local migration has passing offline checks and partial live acceptance: 4/6 development cases passed source/safety assessment in the final frozen run. See `RESULTS_LOCAL.md` for browser checks and failures. Historical cloud results do not validate local models.

## What each layer does

- **RAG:** extracts PDF text, embeds it, retrieves relevant pages, and supplies evidence for an answer.
- **ADK:** runs the agents in order, manages invocation/session state, exposes Python functions as tools, and provides a developer interface and evaluation facilities.
- **Ollama:** serves the local generation and embedding models. ADK is the orchestration framework, not the model provider.
- **Researcher:** calls `list_sources`, `search_documents`, and `read_evidence`; proposes cited claims.
- **Reviewer:** gets a separate model invocation with review instructions and checks evidence support, question coverage, conditions, and scope. It can use the same model as the researcher; that is a different role, not an independent model family.
- **Deterministic gate:** ordinary Python validates the reviewer decision, citation IDs, current-turn evidence reads, source permissions, and scope rules. Invalid output is withheld. Valid citations alone cannot guarantee factual correctness.

## Why local

Local inference makes this a focused ADK learning project and removes hosted inference credentials and per-token API charges from the running app. Documents, embeddings, model requests, and app logs stay on the laptop in the configured local workflow. Hardware memory, inference latency, and smaller-model reliability are the trade-offs. The local model is not assumed to outperform a cloud model; evaluate it.

If asked about the earlier implementation: “I experimented with a GCP-hosted version, then simplified the active project to local inference so I could focus on ADK orchestration and make the demo easier to reproduce.” Do not deny the historical experiment or present historical cloud evaluation numbers as current local results.

## Resume wording

Built a locally hosted Google ADK multi-agent document research system, with researcher and reviewer agents and a deterministic gate enforcing citations and blocking invalid or unauthorized source references.

No claim of production readiness, perfect accuracy, elimination of hallucinations, or business impact is implied. This is a portfolio prototype. Discuss the actual tests and remaining limitations in `RESULTS_LOCAL.md`.

## Explaining the local model choice

“I tested local models against the same ADK workflow and strict output contracts. Gemma 4 produced tool-format problems and false rejections in the development cases. I retained those failures and compared the installed Granite 4.2 model. I chose the running model using measured source review, not the model brand.” Use the exact current selection and results in `RESULTS_LOCAL.md`; do not imply a broad benchmark or that every possible question is solved.

## Questions to prepare for

1. Why use an agent workflow instead of one RAG prompt? Explain explicit stages, tool use, inspection, and independent release checks; mention extra latency.
2. Why two agents using the same model? Separate responsibilities and prompts; shared model weaknesses remain.
3. What makes the gate deterministic? Show code checks and a rejected fabricated citation, without a model judging permission.
4. What does ADK manage versus your code? ADK executes agents and tools; application code handles retrieval, permissions, contracts, budgets, and release.
5. How are follow-ups grounded? Conversation supplies context, but citations must be retrieved and read in the current invocation.
6. How did you evaluate it? Separate offline guardrail tests, ADK tool trajectories, source-based answer review, and browser workflow checks.
7. What would you improve? Better retrieval granularity, section context, a larger unseen evaluation set, and measured latency/reliability improvements.
