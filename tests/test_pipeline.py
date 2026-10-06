"""Smoke tests: the deterministic checks pass yet the sentinel catches drift.

The semantic tests call the real Jev backend, so they are skipped unless
TYPESAFE_API_KEY is set. The deterministic-check test needs no key.
"""

import os

import pytest

os.environ.setdefault("JEV_BACKEND", "jev")

from sentinel.adapter import process_batch  # noqa: E402
from sentinel.circuit_breaker import evaluate_gate  # noqa: E402
from sentinel.schemas import DEMO_QUESTIONS, CircuitState  # noqa: E402
from sentinel.warehouse import Warehouse  # noqa: E402

requires_jev = pytest.mark.skipif(
    not os.getenv("TYPESAFE_API_KEY"),
    reason="Jev backend requires TYPESAFE_API_KEY",
)


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


@requires_jev
@pytest.mark.asyncio
async def test_semantic_drift_is_detected(wh):
    v1 = await process_batch(wh.rows_to_evaluate("v1"), DEMO_QUESTIONS)
    v2 = await process_batch(wh.rows_to_evaluate("v2"), DEMO_QUESTIONS)

    mean_v1 = sum(e.quality for e in v1) / len(v1)
    mean_v2 = sum(e.quality for e in v2) / len(v2)

    # v2 silently drifted: its semantic quality must be clearly lower.
    assert mean_v1 > mean_v2
    assert mean_v1 - mean_v2 > 0.15


@requires_jev
@pytest.mark.asyncio
async def test_circuit_breaker_trips_on_v2(wh):
    v1 = await process_batch(wh.rows_to_evaluate("v1"), DEMO_QUESTIONS)
    v2 = await process_batch(wh.rows_to_evaluate("v2"), DEMO_QUESTIONS)
    baseline = sum(e.quality for e in v1) / len(v1)

    decision, review = evaluate_gate(v2, "v2", baseline_quality=baseline)
    assert decision.state == CircuitState.OPEN
    assert len(review) > 0


@requires_jev
@pytest.mark.asyncio
async def test_idempotent_evaluation(wh):
    rows = wh.rows_to_evaluate("v2")
    evals = await process_batch(rows + rows, DEMO_QUESTIONS)  # duplicated input
    # Same row id@version must collapse to one stable result.
    by_key = {(e.row_id, e.deployment_version): e.quality for e in evals}
    assert len(by_key) == len(rows)


# --- consumer-goods dataset: category drift in a valid enum column ----------

from sentinel.datasets import get_dataset  # noqa: E402


@pytest.fixture()
def goods_wh(tmp_path):
    w = Warehouse(get_dataset("goods"), path=str(tmp_path / "goods.duckdb"))
    w.seed()
    yield w
    w.close()


def test_goods_deterministic_checks_all_pass(goods_wh):
    # The drifted category (e.g. iPhone -> Home Appliances) is still a VALID
    # enum value, so every deterministic check passes on both versions.
    for version in ("v1", "v2"):
        rep = goods_wh.deterministic_checks(version)
        assert rep.all_passed, f"{version} should pass every deterministic check"
        assert rep.total_rows == 12


@requires_jev
@pytest.mark.asyncio
async def test_goods_category_drift_is_detected(goods_wh):
    spec = goods_wh.spec
    v1 = await process_batch(goods_wh.rows_to_evaluate("v1"), spec.questions,
                             quality_weights=spec.quality_weights)
    v2 = await process_batch(goods_wh.rows_to_evaluate("v2"), spec.questions,
                             quality_weights=spec.quality_weights)
    mean_v1 = sum(e.quality for e in v1) / len(v1)
    mean_v2 = sum(e.quality for e in v2) / len(v2)
    # v2 silently miscategorised: semantic quality must drop clearly.
    assert mean_v1 - mean_v2 > 0.15
