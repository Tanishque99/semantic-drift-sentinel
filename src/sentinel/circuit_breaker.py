"""The data circuit breaker (layer 4).

Applies semantic thresholds at the gate. If the new deployment's mean semantic
quality drops too far versus the baseline -- or falls below an absolute floor --
the breaker trips OPEN: block the downstream pipeline, fire an alert, and route
the worst rows to a human review queue.
"""

from __future__ import annotations

from .config import settings
from .schemas import BreakerDecision, CircuitState, RowEvaluation


def evaluate_gate(
    evals: list[RowEvaluation],
    deployment_version: str,
    baseline_quality: float | None,
    review_bottom_k: int = 3,
) -> tuple[BreakerDecision, list[RowEvaluation]]:
    """Decide whether to trip, and return the rows routed to human review."""
    version_evals = [e for e in evals if e.deployment_version == deployment_version]
    if not version_evals:
        decision = BreakerDecision(
            state=CircuitState.CLOSED, deployment_version=deployment_version,
            mean_quality=1.0, drift_vs_baseline=0.0,
            threshold=settings.drift_threshold, reason="no rows evaluated",
        )
        return decision, []

    mean_q = sum(e.quality for e in version_evals) / len(version_evals)
    drift = (baseline_quality - mean_q) if baseline_quality is not None else 0.0

    tripped_by_drift = drift > settings.drift_threshold
    tripped_by_floor = mean_q < settings.quality_floor
    tripped = tripped_by_drift or tripped_by_floor

    if tripped:
        reasons = []
        if tripped_by_drift:
            reasons.append(
                f"semantic drift {drift:.2f} > {settings.drift_threshold:.2f}"
            )
        if tripped_by_floor:
            reasons.append(
                f"mean quality {mean_q:.2f} < floor {settings.quality_floor:.2f}"
            )
        reason = "; ".join(reasons)
    else:
        reason = (
            f"mean quality {mean_q:.2f} within tolerance "
            f"(drift {drift:.2f} <= {settings.drift_threshold:.2f})"
        )

    review: list[RowEvaluation] = []
    if tripped:
        review = sorted(version_evals, key=lambda e: e.quality)[:review_bottom_k]

    decision = BreakerDecision(
        state=CircuitState.OPEN if tripped else CircuitState.CLOSED,
        deployment_version=deployment_version,
        mean_quality=mean_q,
        drift_vs_baseline=drift,
        threshold=settings.drift_threshold,
        reason=reason,
        routed_to_review=len(review),
    )
    return decision, review
