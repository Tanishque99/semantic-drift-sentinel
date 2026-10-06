"""The warehouse layer -- BigQuery in production, DuckDB locally.

Responsibilities (layers 1 and 5 in the architecture):
  1. Load raw rows and run the DETERMINISTIC checks (freshness, completeness,
     schema/enum validity, uniqueness). These are the checks BigQuery is great
     at -- and the ones that pass even when meaning has drifted.
  2. Route only high-risk / sampled rows out to the async adapter.
  5. Write versioned semantic quality metrics back, so drift can be traced over
     time (the closed loop).

The SQL here is intentionally plain so it maps 1:1 onto the BigQuery DDL in
`bigquery/`. Swap `duckdb.connect(path)` for a BigQuery client and the shape of
the pipeline is unchanged.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import duckdb

from .config import settings
from .sampledata import VALID_CATEGORIES, all_rows
from .schemas import RowEvaluation


@dataclass
class DeterministicReport:
    total_rows: int
    failures: dict[str, int]  # check name -> row count that failed

    @property
    def all_passed(self) -> bool:
        return sum(self.failures.values()) == 0


class Warehouse:
    def __init__(self, path: str | None = None):
        self.path = path or settings.warehouse_path
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.con = duckdb.connect(self.path)
        self._init_schema()

    def _init_schema(self) -> None:
        self.con.execute(
            """
            CREATE TABLE IF NOT EXISTS tickets (
                row_id              VARCHAR,
                deployment_version  VARCHAR,
                ticket_text         VARCHAR,
                category            VARCHAR,
                resolution_summary  VARCHAR,
                created_at          DATE
            );
            CREATE TABLE IF NOT EXISTS quality_metrics (
                row_id              VARCHAR,
                deployment_version  VARCHAR,
                quality             DOUBLE,
                answers_json        VARCHAR,
                backend             VARCHAR,
                latency_ms          DOUBLE,
                cost_usd            DOUBLE,
                scored_at           TIMESTAMP DEFAULT now()
            );
            """
        )

    # --- Layer 1: ingestion -------------------------------------------------

    def seed(self) -> None:
        """Load the deterministic sample dataset (idempotent)."""
        self.con.execute("DELETE FROM tickets;")
        rows = all_rows()
        self.con.executemany(
            "INSERT INTO tickets VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    r["row_id"],
                    r["deployment_version"],
                    r["ticket_text"],
                    r["category"],
                    r["resolution_summary"],
                    r["created_at"],
                )
                for r in rows
            ],
        )

    def deterministic_checks(self, version: str) -> DeterministicReport:
        """Run the standard BigQuery-style checks. These all PASS on the demo
        data -- that is the whole point."""
        q = lambda sql: self.con.execute(sql, [version]).fetchone()[0]  # noqa: E731
        total = q("SELECT count(*) FROM tickets WHERE deployment_version = ?")
        failures = {
            "completeness_null_summary": q(
                "SELECT count(*) FROM tickets WHERE deployment_version = ? "
                "AND (resolution_summary IS NULL OR length(trim(resolution_summary)) = 0)"
            ),
            "schema_invalid_category": self.con.execute(
                "SELECT count(*) FROM tickets WHERE deployment_version = ? "
                "AND category NOT IN "
                f"({','.join(['?'] * len(VALID_CATEGORIES))})",
                [version, *VALID_CATEGORIES],
            ).fetchone()[0],
            "uniqueness_duplicate_id": q(
                "SELECT count(*) FROM (SELECT row_id FROM tickets "
                "WHERE deployment_version = ? GROUP BY row_id HAVING count(*) > 1)"
            ),
            "freshness_stale_rows": q(
                "SELECT count(*) FROM tickets WHERE deployment_version = ? "
                "AND created_at < current_date - INTERVAL 30 DAY"
            ),
        }
        return DeterministicReport(total_rows=total, failures=failures)

    def rows_to_evaluate(self, version: str) -> list[dict]:
        """Layer 1 routing: select the high-risk / sampled rows that survived
        deterministic checks and should get semantic evaluation."""
        rate = max(0.0, min(1.0, settings.high_risk_sample_rate))
        rows = self.con.execute(
            "SELECT row_id, deployment_version, ticket_text, category, "
            "resolution_summary FROM tickets WHERE deployment_version = ? "
            "ORDER BY row_id",
            [version],
        ).fetchall()
        cols = ["row_id", "deployment_version", "ticket_text", "category",
                "resolution_summary"]
        selected = rows if rate >= 1.0 else rows[: max(1, int(len(rows) * rate))]
        return [dict(zip(cols, r)) for r in selected]

    # --- Layer 5: closed loop ----------------------------------------------

    def write_metrics(self, evals: list[RowEvaluation]) -> None:
        """Persist versioned semantic quality metrics back into the warehouse."""
        self.con.executemany(
            "INSERT INTO quality_metrics "
            "(row_id, deployment_version, quality, answers_json, backend, "
            " latency_ms, cost_usd) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    e.row_id,
                    e.deployment_version,
                    e.quality,
                    json.dumps({k: a.model_dump() for k, a in e.answers.items()}),
                    e.backend,
                    e.latency_ms,
                    e.cost_usd,
                )
                for e in evals
            ],
        )

    def drift_by_version(self) -> list[dict]:
        """Operational metric: mean semantic quality per deployment version."""
        rows = self.con.execute(
            "SELECT deployment_version, count(*) AS n, avg(quality) AS mean_quality, "
            "sum(cost_usd) AS total_cost FROM quality_metrics "
            "GROUP BY deployment_version ORDER BY deployment_version"
        ).fetchall()
        return [
            {"deployment_version": r[0], "n": r[1],
             "mean_quality": r[2], "total_cost": r[3]}
            for r in rows
        ]

    def close(self) -> None:
        self.con.close()
