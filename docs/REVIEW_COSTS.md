# Cost reconciliation review

Astra independently reviewed the root-authored `deploy/cost_report.py` on 2026-09-22. The script produces a conservative usage estimate, not a billing invoice or hard spend cap.

The review identified a provenance gap: missing model metadata initially defaulted to the historical Flash Lite model for any request. Root corrected this by allowing inference only for the 61 request IDs in an integrity-pinned private historical snapshot. New requests must carry model, provider and location; conflicting partial historical metadata fails closed. Original audit rows were preserved.

Independent offline execution reproduced the historical 61-request total and $7.36434635 remaining authorization after the recorded reserves. Synthetic mixed-model input added exactly $0.01125 generation estimate and $0.20 uncertainty reserve. Unknown models, expired Gemini 3.8 introductory pricing, and a new request without attribution all failed closed. Output ledger permissions were 0600. These are checkpoint figures before the stronger-model benchmark, not final project spend.

The cost implementation prices the configured global Vertex models separately, deduplicates terminal requests, bounds query-embedding characters conservatively, records build estimates and reserves for uncertain requests plus hosting/storage. Final cloud audit records and later usage must be included before reporting final totals. Missing external or audit records remain outside its coverage.

Outcome: the reviewed provenance correction and per-model accounting passed. No cloud or model calls were made during this review. Private replay outputs are under `work/cost-check/reviewer-*.json`; fixtures and source excerpts are not published.

Root subsequently added `tests/test_cost_report.py` with synthetic temporary-project fixtures. Astra independently reviewed and executed all nine tests successfully. They cover the model-specific charge, one uncertainty reservation when both error and missing usage apply, mode-0600 output, unknown model/provider/region, expired or timezone-free pricing timestamps, and missing attribution on new requests. The tests read no live credentials, corpus or audit records.
