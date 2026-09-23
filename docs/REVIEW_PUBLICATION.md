# GitHub publication review

Historical review of the original 83-file publication at commit `985a4412d161a52687d608e97816e5a4300a656b`. Later quality changes and their results are covered by the quality review records.

On 23 September 2026, the project owner explicitly authorized publishing the project source and three supplied PDF documents to GitHub. This does not authorize publishing credentials, generated indexes, container images, raw evaluation responses, logs or sessions.

A reviewer-only Terra agent independently reviewed the publication scope, exact corpus allowlist, preserved original hashes, deployment exclusions and documentation claims. No unresolved publication finding remained. The README prominently retains the final 5/10 paced cloud source-assessment result; publication is not a new answer-quality validation.

Root verified a fresh source export without the private environment, index or evaluation history. After `uv sync --extra dev --frozen`, 88 Python tests plus 12 subtests passed. The browser response validator passed. Offline ingestion using `.venv/bin/python -m app.ingest --manifest corpus/manifest.json --output work/offline-index.json --embedding-provider lexical` succeeded for all three sources and 156 pages.

The original documented direct-script ingestion command failed to import the app in that fresh environment. The published runbook now uses the verified module entrypoint. No application runtime logic changed, no live evaluation was repeated, and no additional Google model calls were made for publication.

The three published PDF copies match their manifest SHA-256 values. Their original author and copyright notices are retained; no new document license or ownership claim is asserted. Secrets and private artifacts were checked against the publication file allowlist. Detailed local check outputs remain under private `work/`.
