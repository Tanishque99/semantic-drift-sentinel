"""Central configuration, read from the environment.

The semantic layer is powered by Jev, the TypeSafe AI "System One" model (the
production path from the diagram). Set `TYPESAFE_API_KEY` (e.g. in a local
`.env` file) and `make demo` runs the full loop against it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# Load a local .env file if python-dotenv is installed, so keys placed in .env
# are picked up automatically (no `source .env` needed). Optional: if the
# package is absent the demo still runs with environment variables alone.
try:
    from dotenv import load_dotenv

    load_dotenv()
except ModuleNotFoundError:
    pass


def _auto_backend() -> str:
    # Jev is the only backend; the env var is kept for forward compatibility.
    return os.getenv("JEV_BACKEND", "jev").strip().lower()


@dataclass(frozen=True)
class Settings:
    # Which evaluator backend powers the semantic layer.
    backend: str = _auto_backend()

    # Model for the Jev backend.
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


settings = Settings()
