"""Central configuration, read from the environment.

The guiding principle of the whole demo: `git clone && make demo` must produce
live output with zero API keys. So the evaluator backend auto-selects:

    JEV_BACKEND set            -> use it (jev | claude | mock)
    else TYPESAFE_API_KEY set  -> jev   (the production path from the diagram)
    else ANTHROPIC_API_KEY set -> claude
    else                       -> mock  (deterministic, no network)
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _auto_backend() -> str:
    explicit = os.getenv("JEV_BACKEND")
    if explicit:
        return explicit.strip().lower()
    if os.getenv("TYPESAFE_API_KEY"):
        return "jev"
    if os.getenv("ANTHROPIC_API_KEY"):
        return "claude"
    return "mock"


@dataclass(frozen=True)
class Settings:
    # Which evaluator backend powers the semantic layer.
    backend: str = _auto_backend()

    # Models per backend.
    claude_model: str = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5")
    jev_model: str = os.getenv("JEV_MODEL", "jev-1.13.0")

    # Cloud Run adapter limits (the engineering boundary the post is about).
    max_concurrency: int = int(os.getenv("MAX_CONCURRENCY", "8"))
    batch_size: int = int(os.getenv("BATCH_SIZE", "16"))
    max_retries: int = int(os.getenv("MAX_RETRIES", "3"))

    # Circuit breaker thresholds.
    # Trip if semantic quality drops more than this vs. the baseline version...
    drift_threshold: float = float(os.getenv("DRIFT_THRESHOLD", "0.15"))
    # ...or if absolute mean quality on the new version falls below this floor.
    quality_floor: float = float(os.getenv("QUALITY_FLOOR", "0.70"))

    # Deterministic SQL layer: fraction of clean rows to sample for eval even
    # when they pass every deterministic check (catch silent drift early).
    high_risk_sample_rate: float = float(os.getenv("SAMPLE_RATE", "1.0"))

    # Local warehouse file (our stand-in for BigQuery).
    warehouse_path: str = os.getenv("WAREHOUSE_PATH", "data/warehouse.duckdb")

    # Pricing for the cost-per-loop operational metric (USD / 1M input tokens).
    jev_price_per_mtok: float = 0.042
    claude_price_per_mtok: float = 0.80  # Haiku-class input, approx.


settings = Settings()
