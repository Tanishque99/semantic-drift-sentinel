# Deploying to real GCP

The demo runs entirely locally (DuckDB stands in for BigQuery, the adapter runs
in-process). This is the path to the production topology in the architecture
diagram. Nothing in `src/sentinel/` changes.

## 1. Cloud Run — the async adapter

```bash
gcloud run deploy semantic-drift-sentinel \
  --source . \
  --region us-central1 \
  --set-env-vars JEV_BACKEND=jev,MAX_CONCURRENCY=8,BATCH_SIZE=16 \
  --set-secrets TYPESAFE_API_KEY=typesafe-api-key:latest \
  --no-allow-unauthenticated
```

(Build uses `deploy/Dockerfile`.)

## 2. BigQuery — checks + closed loop

Replace the local DuckDB reads/writes in `src/sentinel/warehouse.py` with a
`google-cloud-bigquery` client. The SQL is already written for BigQuery:

- `bigquery/01_deterministic_checks.sql` — layer 1 checks + routing query
- `bigquery/02_quality_metrics_schema.sql` — layer 5 metrics table + drift views

## 3. Wiring

- Schedule the deterministic checks + routing query (Cloud Scheduler → a job or
  a BigQuery scheduled query) to push high-risk rows to the Cloud Run `/evaluate`
  endpoint.
- The adapter writes versioned metrics back to `quality_metrics`.
- Point an alert (Slack / PagerDuty) at the circuit-breaker decision, and a
  human-review queue (a table, a ticketing webhook) at the routed anomalies.

## Secrets

Keep `TYPESAFE_API_KEY` in Secret Manager and mount it with `--set-secrets`.
Never bake keys into the image.
