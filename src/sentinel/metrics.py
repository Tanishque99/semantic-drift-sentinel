"""Operational metrics -- the numbers the post argues are more useful than a
raw model score.

  * Semantic drift by deployment version
  * Human vs evaluator disagreement rate
  * False-positive rate vs processing latency overhead
  * Total cost per evaluation loop
"""

from __future__ import annotations

from dataclasses import dataclass

from .schemas import RowEvaluation


@dataclass
class LoopMetrics:
    backend: str
    rows_evaluated: int
    mean_quality_by_version: dict[str, float]
    semantic_drift: float
    disagreement_rate: float | None
    p50_latency_ms: float
    p95_latency_ms: float
    total_cost_usd: float
    cost_per_row_usd: float


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    k = max(0, min(len(ordered) - 1, int(round((pct / 100.0) * (len(ordered) - 1)))))
    return ordered[k]


def compute_loop_metrics(
    evals: list[RowEvaluation],
    human_labels: dict[str, bool] | None = None,
    disagreement_threshold: float = 0.5,
) -> LoopMetrics:
    """`human_labels` maps row_id@version -> is_good (optional ground truth)."""
    by_version: dict[str, list[float]] = {}
    for e in evals:
        by_version.setdefault(e.deployment_version, []).append(e.quality)

    means = {v: sum(q) / len(q) for v, q in by_version.items()}
    versions = sorted(means)
    drift = (means[versions[0]] - means[versions[-1]]) if len(versions) >= 2 else 0.0

    disagreement: float | None = None
    if human_labels:
        compared = 0
        disagree = 0
        for e in evals:
            key = f"{e.row_id}@{e.deployment_version}"
            if key in human_labels:
                compared += 1
                evaluator_says_good = e.quality >= disagreement_threshold
                if evaluator_says_good != human_labels[key]:
                    disagree += 1
        disagreement = (disagree / compared) if compared else None

    latencies = [e.latency_ms for e in evals]
    total_cost = sum(e.cost_usd for e in evals)
    backend = evals[0].backend if evals else "n/a"

    return LoopMetrics(
        backend=backend,
        rows_evaluated=len(evals),
        mean_quality_by_version=means,
        semantic_drift=drift,
        disagreement_rate=disagreement,
        p50_latency_ms=_percentile(latencies, 50),
        p95_latency_ms=_percentile(latencies, 95),
        total_cost_usd=total_cost,
        cost_per_row_usd=(total_cost / len(evals)) if evals else 0.0,
    )
