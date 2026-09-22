# Cost controls and estimates

Checked 22 September 2026. All amounts are USD, before tax and credits. The user authorized $10 in Google usage and reported approximately $300 trial credit with 18 days remaining. Billing access works; the remaining credit balance has not been independently verified.

ADK is the application framework. Google model execution, builds, storage and hosting are separately metered services.

| Component | Rate used | Tonight's allocation |
|---|---|---:|
| Gemini 3.1 Flash-Lite, Vertex global | $0.25 / million input tokens; $1.50 / million output tokens, including reasoning | $3.00 |
| Gemini Embedding online | $0.00015 / 1,000 billable characters | $0.25 |
| Cloud Build, e2-standard-2 | $0.006 / build minute | $0.50 |
| Cloud Run, request billing, us-central1 | $0.000024 / vCPU-second; $0.0000025 / GiB-second; $0.40 / million requests | $1.00 |
| Private object/image storage and Secret Manager | Usage dependent; retain small artifacts only | $0.25 |
| Reserved for fixes and verification | Do not spend automatically | $5.00 |

Rates: [Google model pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing), [Cloud Build](https://cloud.google.com/build/pricing), [Cloud Run](https://cloud.google.com/run/pricing). Free allowances or eligible credits can reduce the eventual bill; this plan does not depend on them.

The initial 156-page embedding run reported **322,961 billable characters**, approximately **$0.04844**, with zero truncated pages. This is a usage-based estimate, not a billing invoice.

All consumed usage is deducted from the table's allocations, never added to the $10 total. Immediately after ingestion, the embedding allocation had approximately $0.20156 left and the total authorization approximately $9.95156 left, before probes and subsequent runs. The final acceptance report must reconcile all later model/embedding usage, failures and hosting/build estimates before reporting the remaining budget. Evaluation reservations represent committed budget, not measured bills, and must not be counted again as additional token charges.

The application bounds model calls, tool calls, request duration, output tokens and session history. Evaluation runs reserve $0.10 per dispatched turn, including uncertain failures. Root coordinates paid runs to avoid concurrent budget consumption. Input/output counters and billable embedding characters support later cost reconciliation.

Cloud Run uses minimum instances zero and maximum one. IAM and an application token restrict usage. These controls reduce spending; they are not a hard billing cap. Stop additional paid runs if the remaining allocation cannot cover the next bounded run. Do not run recurring evaluations or leave load tests active.

Development uses the local UI with cloud models; only final cloud verification incurs Cloud Run compute. Keep cloud artifacts private and document their cleanup. Existing BigQuery resources are outside this project's cleanup scope. Codex subscription usage is separate from this Google Cloud budget.

## Final execution estimate

The final reconciliation covers 138 audited local/cloud requests, including all 35 cloud request terminal records and the recorded native runs. Estimated observed model, embedding and build usage is **$0.75399465**. Add **$4.60** reserved for uncertain or failed requests and **$1.25** for hosting/storage: the conservative total is **$6.60399465**, leaving **$3.39600535** within the authorized $10. These reserves are not additional measured charges. No further model runs are scheduled.

This is an operational estimate, not a billing invoice. Query embedding charges use a conservative character bound; cloud runtime/storage are reserved rather than measured. Trial credits, free allowances and tax have not been applied. The private reconciliation is `work/cost-final.json`, based on metadata-only local audit and `work/cloud-audit-final.json`. Cloud logging reconciles all 35 expected requests to preflight and terminal records.
