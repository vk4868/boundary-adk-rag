# Retire this private demo

These commands are a manual runbook, not an automatic cleanup job. They have **not** been executed. Keep the deployment for the interview; retire its dedicated resources when no longer needed. Minimum instances zero reduces idle compute but does not delete stored images, objects or secrets. Check Cloud Billing for actual charges and trial expiry.

The names below belong to this Boundary build in `sql-bigquery-502206`. Confirm the resource identity before deletion. Do not delete the project, billing account, existing BigQuery datasets, or unrelated service accounts. Local originals and the working project are preserved by this procedure.

First stop the application from accepting more paid requests by deleting only its service:

```sh
gcloud run services delete boundary-adk \
  --project=sql-bigquery-502206 --region=us-central1
```

After retaining any required private deployment/evaluation evidence, remove the dedicated image repository and corpus/build-source bucket. These deletions remove the cloud copy of the derived index and container images; rebuilding later requires the local authorized inputs.

```sh
gcloud artifacts repositories delete boundary-images \
  --project=sql-bigquery-502206 --location=us-central1
gcloud storage rm --recursive gs://sql-bigquery-502206-boundary-corpus
```

Delete the application secret and the two dedicated service accounts last:

```sh
gcloud secrets delete boundary-app-token --project=sql-bigquery-502206
gcloud iam service-accounts delete \
  boundary-agent@sql-bigquery-502206.iam.gserviceaccount.com \
  --project=sql-bigquery-502206
gcloud iam service-accounts delete \
  boundary-builder@sql-bigquery-502206.iam.gserviceaccount.com \
  --project=sql-bigquery-502206
```

Cloud Build history and Cloud Logging entries follow their configured retention; deleting the service does not erase those records. Inspect billing after deletion to confirm no new workload usage. No recurring model evaluation or load test should remain running. Closing the locally started proxy/server does not delete the cloud service.
