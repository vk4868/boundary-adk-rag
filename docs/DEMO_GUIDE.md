# Run and demonstrate Boundary

This is an IAM-private, single-workspace runtime demo built from a repository that includes its user-authorized sample PDFs. Check the final acceptance evidence before presenting any live-flow or performance claim. The scripts below describe the intended demonstration; they are not a record that each live step passed.

**Current limitation:** both final browser sequences failed on their first submitted question with `ValidationError`; neither follow-up ran. The current revision is not a reliable live recruiter walkthrough. Use the architecture, offline checks and accurately labeled saved evaluation evidence for a presentation until the failing interaction has been diagnosed and revalidated. See [the final cloud and browser review](REVIEW_CLOUD_QUALITY.md). Paid verification has stopped; these instructions do not authorize another run.

## Reproduce the local setup

From the configured project:

```bash
cd '/Users/vineetkumar/Documents/Work/RAG/ADK RAG'
uv sync --extra dev
.venv/bin/python -m pytest -q
node --test tests/web_response_validator.test.js
```

Do not overwrite an existing private `.env` or rebuild the indexed corpus unnecessarily. On a new workstation only, copy the offline `.env.example` to a new `.env`, authenticate the authorized Google account, and configure the required values. Do not place the token in command arguments or a shared terminal recording.

For a new workstation that has not configured Application Default Credentials:

```bash
gcloud auth application-default login
```

The existing build workstation is already authenticated; repeating login is unnecessary. `gcloud` CLI identity and Application Default Credentials are related but distinct configuration surfaces. Local model SDK calls use ADC; the cloud runtime uses its service account.

The required private settings for a live Vertex index are:

| Setting | Required meaning |
|---|---|
| `APP_TOKEN` | A long random workspace token; never the sample placeholder |
| `APP_SERVER_ROLE`, `APP_ALLOWED_ROLES` | `analyst` for this supplied manifest |
| `APP_ENABLE_MODEL_CALLS` | `true` only for a coordinated, budgeted live run |
| `APP_MODEL_PROVIDER`, `APP_MODEL` | `vertex`, `gemini-3.1-flash-lite` |
| `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION` | Authorized project, `global` for generation |
| `APP_EMBEDDING_PROVIDER`, `APP_EMBEDDING_MODEL` | `vertex`, `gemini-embedding-001` |
| `EMBEDDING_LOCATION`, `APP_EMBEDDING_DIMENSIONS` | `us-central1`, `768` |
| `APP_INDEX_PATH`, `APP_INDEX_SHA256` | The existing private index and its recorded SHA-256 |
| `APP_MAX_SEARCH_QUERY_CHARS` | Model refinement limit: `1200` characters by default, supported maximum `4000` |
| `APP_MAX_EFFECTIVE_SEARCH_QUERY_CHARS` | Original question plus refinement: `7500` characters by default, supported maximum `10000`; overflow fails explicitly |
| Model/tool/token/time settings | The bounded values in `.env.example`, reviewed before changes |

To inspect the local snapshot hash without exposing its contents:

```bash
shasum -a 256 data/index.json
```

Ingestion commands are in the main README. The repository includes `corpus/manifest.json` and its three referenced PDFs, so offline extraction can be reproduced directly. Rebuilding the Vertex snapshot additionally requires the developer's own Google project, ADC and explicit spend authorization. The generated live index is not included.

Start the application:

```bash
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`. Confirm `/health` reports the intended provider/index. Connect through the token dialog; show the three source titles, supplied editions/scopes and page counts. Connecting and reading the source list do not generate an answer. Submitting a question invokes paid Google model/embedding services when live mode is enabled.

## Five-minute demonstration

| Time | Action | What to explain |
|---|---|---|
| 0:00–0:40 | Show the source library | Three rulebooks have different scopes. This is document research, not a claim that every supplied rule is current worldwide. |
| 0:40–1:30 | Ask “In the supplied US Ismaili Games rules, how many overs may one bowler bowl in a full 20-over innings?” | The researcher retrieves and reads authorized evidence, then a second agent reviews the answer. |
| 1:30–2:10 | Open the numbered citation and read the relevant clause | The source panel shows the original PDF page and extracted text. The citation gate checks identity/access; the audience can inspect factual support. |
| 2:10–3:20 | Ask “Compare whether an injured batter can use a runner under the supplied MCC Laws and the US Ismaili Games rules.” | Different scopes can legitimately disagree. The assistant must identify which rulebook supports each part. |
| 3:20–4:00 | Follow up: “Which rulebook prohibits the runner?” | The session preserves the subject, but the new answer still needs evidence read during this invocation. |
| 4:00–4:30 | Ask an out-of-corpus question, such as the 2026 IPL final winner | The correct behavior is to withhold an unsupported answer. Do not present an abstention as a failure to be hidden. |
| 4:30–5:00 | Expand research activity and show the evidence/test summary | Show actual agent/tool names, usage and gate result. State the measured evaluation denominator and any remaining limitation. |

Do not promise fixed response times; observe the actual current latency. If a live request is rejected or a service is unavailable, explain the visible result and use the saved, privately reviewed evidence. Do not replace it with a fabricated successful response or silently switch to lexical/offline mode.

## Demonstrate the private cloud deployment

Only use this after the deployment evidence confirms that the service is ready:

```bash
gcloud run services proxy boundary-adk \
  --project=sql-bigquery-502206 --region=us-central1 --port=8085
```

Open `http://127.0.0.1:8085` and connect with the application token. The proxy supplies the Google IAM identity; the app receives its own token through `X-App-Token`. This tests the private Cloud Run deployment, not the local FastAPI process.

A recruiter cannot use this localhost URL remotely. Offer a live walkthrough or use explicitly authorized IAM access. Do not make the service public, expose its app token, or publish the private index to obtain a shareable link. See `deploy/README.md` for the root-owned build/deploy configuration.

## Reproduce evaluations carefully

No-call planning and native-artifact validation:

```bash
.venv/bin/python evals/run.py
.venv/bin/python evals/build_native.py
.venv/bin/python -m pytest tests/test_native_eval.py -q
```

The following HTTP example is for the root-coordinated live run only. It loads the token in-process from the private settings without printing it or placing it in shell history. It writes private diagnostic responses under `work/`:

```bash
.venv/bin/python - <<'PY'
import os
import sys
from app.config import Settings
from evals.run import main
settings = Settings()
if not settings.app_token or not settings.auth_ready:
    raise SystemExit('Configure the private workspace token first.')
os.environ['APP_AUTH_TOKEN'] = settings.app_token.get_secret_value()
sys.argv = ['evals/run.py', '--execute', '--max-estimated-usd', '2.5',
            '--output', 'work/dev-eval-report.json', '--save-responses']
main()
PY
```

Do not run this merely because the command is available. Coordinate the remaining Google budget first. Twenty development cases include 23 endpoint turns; the harness keeps conservative reservations when usage is uncertain and requires a separate source-based semantic assessment. Record the reviewer type; an agent assessment does not replace the user's later manual verification. For the native ADK command and metric limitations, use `evals/README.md`.

## Before a recording or interview

- Close any terminal pane that displays credentials, raw private passages or unreviewed diagnostics.
- Use the included repository PDFs when showing original sources, and retain their original author and copyright notices. Keep the generated index, credentials, raw responses and unreviewed diagnostics private.
- Start a new research session so the first question has an understandable context.
- Verify which environment is being shown: local app with Vertex, or the IAM-proxied cloud app.
- Quote only final measured results with their denominator and scope; keep pending metrics out of slides and résumé bullets.
- Explain one successful case and one real limitation. The source/privacy/evaluation decisions are part of the engineering story.

## Optional local ADK inspector

The polished Boundary interface exposes only the released response. ADK's development UI can show intermediate agent/tool events for an operator learning the framework. It is an unauthenticated local development surface, so keep it bound to loopback and never deploy or proxy it publicly. Intermediate drafts and tool responses can contain private document text; do not use the inspector in a public recording.

The installed ADK CLI supports this syntax:

```bash
(
  umask 077
  PYTHONPATH="$PWD" APP_ALLOW_ADK_CLI=true .venv/bin/adk web \
    --host 127.0.0.1 --port 8001 \
    --session_service_uri memory:// --artifact_service_uri memory:// \
    --log_level warning app
)
```

Open `http://127.0.0.1:8001` locally. The explicit CLI opt-in enables the same governed export; submitting a prompt can make paid calls under the configured model settings. Coordinate it with the Google usage ledger. Memory-backed inspector sessions disappear when the process stops. CLI help verified the command options; a successful inspector session must be recorded separately before claiming that flow was tested.
