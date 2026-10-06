"""Smoke tests: the deterministic checks pass yet the sentinel catches drift.

These run with the zero-key mock backend, so CI needs no secrets.
"""

import os

import pytest

os.environ.setdefault("JEV_BACKEND", "mock")

from sentinel.adapter import process_batch  # noqa: E402
from sentinel.circuit_breaker import evaluate_gate  # noqa: E402
from sentinel.schemas import DEMO_QUESTIONS, CircuitState  # noqa: E402
from sentinel.warehouse import Warehouse  # noqa: E402


@pytest.fixture()
def wh(tmp_path):
    w = Warehouse(path=str(tmp_path / "test.duckdb"))
    w.seed()
    yield w
    w.close()


def test_deterministic_checks_all_pass(wh):
    for version in ("v1", "v2"):
        rep = wh.deterministic_checks(version)
        assert rep.all_passed, f"{version} should pass every deterministic check"
        assert rep.total_rows == 13


@pytest.mark.asyncio
async def test_semantic_drift_is_detected(wh):
    v1 = await process_batch(wh.rows_to_evaluate("v1"), DEMO_QUESTIONS)
    v2 = await process_batch(wh.rows_to_evaluate("v2"), DEMO_QUESTIONS)

    mean_v1 = sum(e.quality for e in v1) / len(v1)
    mean_v2 = sum(e.quality for e in v2) / len(v2)

    # v2 silently drifted: its semantic quality must be clearly lower.
    assert mean_v1 > mean_v2
    assert mean_v1 - mean_v2 > 0.15


@pytest.mark.asyncio
async def test_circuit_breaker_trips_on_v2(wh):
    v1 = await process_batch(wh.rows_to_evaluate("v1"), DEMO_QUESTIONS)
    v2 = await process_batch(wh.rows_to_evaluate("v2"), DEMO_QUESTIONS)
    baseline = sum(e.quality for e in v1) / len(v1)

    decision, review = evaluate_gate(v2, "v2", baseline_quality=baseline)
    assert decision.state == CircuitState.OPEN
    assert len(review) > 0


@pytest.mark.asyncio
async def test_idempotent_evaluation(wh):
    rows = wh.rows_to_evaluate("v2")
    evals = await process_batch(rows + rows, DEMO_QUESTIONS)  # duplicated input
    # Same row id@version must collapse to one stable result.
    by_key = {(e.row_id, e.deployment_version): e.quality for e in evals}
    assert len(by_key) == len(rows)
