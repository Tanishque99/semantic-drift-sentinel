-- Layer 5: the closed loop. Versioned semantic quality metrics written back
-- into BigQuery so you can trace and alert on drift over time.

CREATE TABLE IF NOT EXISTS `project.dataset.quality_metrics` (
  row_id              STRING,
  deployment_version  STRING,
  quality             FLOAT64,     -- 0..1 aggregate semantic quality
  answers_json        JSON,        -- the typed Jev answers for this row
  backend             STRING,      -- jev | claude | mock
  latency_ms          FLOAT64,
  cost_usd            FLOAT64,
  scored_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
PARTITION BY DATE(scored_at)
CLUSTER BY deployment_version;

-- Semantic drift by deployment version (the headline operational metric).
SELECT
  deployment_version,
  COUNT(*)        AS n_rows,
  AVG(quality)    AS mean_quality,
  SUM(cost_usd)   AS total_cost_usd,
  APPROX_QUANTILES(latency_ms, 100)[OFFSET(95)] AS p95_latency_ms
FROM `project.dataset.quality_metrics`
GROUP BY deployment_version
ORDER BY deployment_version;

-- Drift trend over time: compare each version's mean quality to the prior one.
SELECT
  deployment_version,
  mean_quality,
  mean_quality - LAG(mean_quality) OVER (ORDER BY deployment_version)
    AS drift_vs_previous
FROM (
  SELECT deployment_version, AVG(quality) AS mean_quality
  FROM `project.dataset.quality_metrics`
  GROUP BY deployment_version
);
