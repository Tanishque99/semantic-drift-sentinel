-- Layer 1: deterministic data-quality checks in BigQuery.
-- These are the checks the warehouse is great at. On the demo data they all
-- return 0 failing rows for BOTH deployment versions -- the drift is semantic
-- and invisible here. The local DuckDB version in src/sentinel/warehouse.py
-- mirrors these 1:1.

-- Completeness: resolution_summary must be present.
SELECT deployment_version, COUNT(*) AS null_summary_rows
FROM `project.dataset.tickets`
WHERE resolution_summary IS NULL OR LENGTH(TRIM(resolution_summary)) = 0
GROUP BY deployment_version;

-- Schema / enum validity: category must be one of the allowed values.
SELECT deployment_version, COUNT(*) AS invalid_category_rows
FROM `project.dataset.tickets`
WHERE category NOT IN ('billing', 'technical', 'account', 'other')
GROUP BY deployment_version;

-- Uniqueness: row_id must be unique within a deployment version.
SELECT deployment_version, COUNT(*) AS duplicate_id_rows
FROM (
  SELECT deployment_version, row_id, COUNT(*) AS c
  FROM `project.dataset.tickets`
  GROUP BY deployment_version, row_id
  HAVING COUNT(*) > 1
)
GROUP BY deployment_version;

-- Freshness: no rows older than 30 days.
SELECT deployment_version, COUNT(*) AS stale_rows
FROM `project.dataset.tickets`
WHERE created_at < DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
GROUP BY deployment_version;

-- Routing: select high-risk / sampled rows to send to the async adapter.
-- Here: everything that passed the checks (tune the sample for scale/cost).
SELECT row_id, deployment_version, ticket_text, category, resolution_summary
FROM `project.dataset.tickets`
WHERE deployment_version = @deployment_version
ORDER BY row_id;
