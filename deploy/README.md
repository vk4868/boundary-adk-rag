> Local Ollama migration: this document records the earlier Vertex/Cloud Run implementation or its evaluation procedure. For the active local setup use `README.md` and `docs/DEMO_GUIDE.md`; current local evidence is in `docs/RESULTS_LOCAL.md`. Historical commands/results are not proof of local-model behavior.

# Private Google Cloud deployment

This is a single-user portfolio demonstration. The Cloud Run service requires Google Cloud IAM authentication. The application additionally requires its own token through `X-App-Token`; `Authorization` is reserved for the Cloud Run identity token.

## Resources

- Project: `sql-bigquery-502206`
- Runtime region: `us-central1`; generation model endpoint: `global`
- Runtime service account: `boundary-agent@sql-bigquery-502206.iam.gserviceaccount.com`
- Build service account: `boundary-builder@sql-bigquery-502206.iam.gserviceaccount.com`
- Private corpus snapshot bucket: `gs://sql-bigquery-502206-boundary-corpus`
- Private image repository: `us-central1-docker.pkg.dev/sql-bigquery-502206/boundary-images`
- Secret Manager secret: `boundary-app-token`

The service account has Vertex AI access, object read access on the corpus bucket, and access to the specific application-token secret. No service-account key file is created.

The separate builder can read the private staging bucket, write only to the application image repository, and emit Cloud Logging records. It has no application-token access.

## Build context

Run `python deploy/prepare_context.py --output work/cloud-build-context-v1` after indexing. This constructs an explicit upload allowlist: runtime code, frontend, pinned dependencies, Dockerfile and the **private derived index**. It excludes PDFs, local credentials, tokens, logs and sessions. Do not publish this private context or image.

Build with Cloud Build and deploy the resulting immutable image digest. Use request-based billing, minimum instances zero, maximum instances one, one worker, and a bounded request timeout. Do not enable unauthenticated invocation.

From the project directory, after root has coordinated the budgeted run:

```sh
.venv/bin/python deploy/prepare_context.py --output work/cloud-build-context-v1
gcloud builds submit work/cloud-build-context-v1 \
  --project=sql-bigquery-502206 --region=us-central1 \
  --config=deploy/cloudbuild.yaml \
  --gcs-source-staging-dir=gs://sql-bigquery-502206-boundary-corpus/build-source \
  --async --format=json > work/cloud-build-v1.json
```

Submit the prepared context explicitly, never `.`. Root `.gcloudignore` and `.dockerignore` also enforce a runtime-file allowlist. The private index is intentionally included; the original PDFs, `.env`, private logs and evaluation responses are excluded. Use a new named context for another build to avoid stale files. Each new build uses its unique Cloud Build ID in the image tag. Wait for Cloud Build success and record the returned image digest before deploying; a queued build is not success.

Read the build ID from `work/cloud-build-v1.json`, then resolve its actual result:

```sh
BOUNDARY_BUILD_ID='REPLACE_WITH_RETURNED_BUILD_ID'
gcloud builds describe "$BOUNDARY_BUILD_ID" \
  --project=sql-bigquery-502206 --region=us-central1 \
  --format=json > work/cloud-build-v1-result.json
```

Only after `status` is `SUCCESS`, use the `results.images[0].name` repository and `results.images[0].digest` from that record. Discard the tag and append `@sha256:...` to the repository. Do not infer the digest from a mutable tag. The initial historical build used `demo-v1`; later configuration uses unique build tags, and all deployments use the recorded digest.

`cloudrun.env.yaml` contains the complete non-secret production configuration, including the exact approved index hash, explicit model/embedding providers, project and locations, disabled ADK CLI export, and request/session limits. `APP_TOKEN` is bound separately to Secret Manager version 1. Do not copy the local `.env` into deployment configuration.

```sh
# Set this to the verified repository path@sha256:digest from the successful build.
BOUNDARY_IMAGE_DIGEST='us-central1-docker.pkg.dev/sql-bigquery-502206/boundary-images/boundary-adk@sha256:REPLACE_WITH_VERIFIED_DIGEST'
gcloud run deploy boundary-adk \
  --project=sql-bigquery-502206 --region=us-central1 \
  --image="$BOUNDARY_IMAGE_DIGEST" \
  --service-account=boundary-agent@sql-bigquery-502206.iam.gserviceaccount.com \
  --env-vars-file=deploy/cloudrun.env.yaml \
  --set-secrets=APP_TOKEN=boundary-app-token:1 \
  --cpu=1 --memory=1Gi --concurrency=8 --timeout=180 \
  --min=0 --max=1 --min-instances=0 --max-instances=1 \
  --cpu-throttling --no-cpu-boost \
  --invoker-iam-check --no-allow-unauthenticated
```

The image starts one Uvicorn worker. Production index validation must pass before chat can use the corpus. Verify IAM denial without credentials, application denial without `X-App-Token`, a live sourced answer and follow-up, and sanitized JSON audit records in Cloud Logging. Keep tokens out of shell history and command arguments; use a local Python script reading the private environment and calling the authenticated proxy for checks.

## Access

After deployment, run:

```sh
gcloud run services proxy boundary-adk --project=sql-bigquery-502206 --region=us-central1 --port=8085
```

Open `http://127.0.0.1:8085` and enter the app token from the private local environment file. This exercises the cloud service through an authenticated local proxy. It is not a publicly accessible recruiter link; a live walkthrough or authorized IAM access is required.

## Operating limits

- The three original PDFs remain unchanged; user-authorized copies and their manifest are included in version control. PDFs remain excluded from the Cloud Build context and runtime image.
- The container contains a fixed, derived index; rebuild to change documents. The bucket keeps the private snapshot separately.
- Sessions and local audit files are temporary on Cloud Run. They are not a durable multi-user database. Runtime operational logs should also go to Cloud Logging, with source text and prompts omitted.
- Application token and model-call limits reduce exposure; they do not enforce a cloud billing ceiling. Track embedding, model, build, storage, and hosting costs separately.
- The user authorized US$10 of Google service usage. Trial credit balance was reported by the user; billing-enabled status and API access were verified, but remaining credit was not independently verified.
- Existing BigQuery resources are not part of this application and must not be changed or deleted by its cleanup procedure.

Actual image digest, service URL, verification results and estimated usage will be recorded after deployment succeeds.

When the interview demo is no longer needed, use [CLEANUP.md](CLEANUP.md) to retire only its dedicated resources. The cleanup commands are documented but have not been executed.
