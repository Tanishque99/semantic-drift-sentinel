"""The async compute layer -- a Cloud Run service in production.

This is where the post's real thesis lives: at scale the LLM/Jev call is the
easy part; the hard part is the infrastructure boundary around it -- batching,
retries with backoff, idempotency, and strict concurrency throttling so you
never melt your budget or trip provider rate limits.

The same logic runs two ways:
  * in-process from `demo.py` (so `make demo` needs no running server), and
  * as a FastAPI app (`make serve`) that mirrors a real Cloud Run deployment.
"""

from __future__ import annotations

import asyncio
import time

from .config import settings
from .evaluator import Evaluator, aggregate_quality, get_evaluator
from .schemas import Question, RowEvaluation


def _row_id(row: dict) -> str:
    return f"{row['row_id']}@{row['deployment_version']}"


async def _evaluate_one(
    evaluator: Evaluator,
    sem: asyncio.Semaphore,
    seen: dict[str, RowEvaluation],
    row: dict,
    questions: list[Question],
    quality_weights: dict[str, float] | None = None,
) -> RowEvaluation:
    key = _row_id(row)
    if key in seen:  # idempotency: never pay to score the same row twice
        return seen[key]

    # The row's content columns are the Jev `state`; row_id and
    # deployment_version are bookkeeping, not part of what gets scored.
    state = {k: v for k, v in row.items() if k not in ("row_id", "deployment_version")}

    async with sem:  # strict concurrency throttle -> cost + rate-limit control
        start = time.perf_counter()
        answers, tokens = await _with_retries(evaluator, state, questions)
        latency_ms = (time.perf_counter() - start) * 1000.0

    cost = (tokens / 1_000_000.0) * evaluator.price_per_mtok
    result = RowEvaluation(
        row_id=row["row_id"],
        deployment_version=row["deployment_version"],
        answers=answers,
        quality=aggregate_quality(answers, quality_weights),
        backend=evaluator.name,
        latency_ms=latency_ms,
        cost_usd=cost,
    )
    seen[key] = result
    return result


async def _with_retries(evaluator: Evaluator, state: dict, questions: list[Question]):
    delay = 0.25
    last_exc: Exception | None = None
    for attempt in range(settings.max_retries):
        try:
            return await evaluator.evaluate(state, questions)
        except Exception as exc:  # noqa: BLE001 -- adapter must be resilient
            last_exc = exc
            if attempt == settings.max_retries - 1:
                break
            await asyncio.sleep(delay)
            delay *= 2  # exponential backoff
    raise RuntimeError(f"evaluation failed after retries: {last_exc}")


async def process_batch(
    rows: list[dict],
    questions: list[Question],
    evaluator: Evaluator | None = None,
    quality_weights: dict[str, float] | None = None,
) -> list[RowEvaluation]:
    """Fan rows out under a concurrency cap, in batches, with idempotency."""
    evaluator = evaluator or get_evaluator()
    sem = asyncio.Semaphore(settings.max_concurrency)
    seen: dict[str, RowEvaluation] = {}
    results: list[RowEvaluation] = []

    for i in range(0, len(rows), settings.batch_size):
        batch = rows[i : i + settings.batch_size]
        results.extend(
            await asyncio.gather(
                *(
                    _evaluate_one(evaluator, sem, seen, r, questions, quality_weights)
                    for r in batch
                )
            )
        )
    return results


# --- FastAPI surface (optional; mirrors the real Cloud Run service) ---------

def build_app():  # pragma: no cover - exercised via `make serve`
    from fastapi import FastAPI
    from pydantic import BaseModel

    from .schemas import DEMO_QUESTIONS

    class EvalRequest(BaseModel):
        rows: list[dict]

    app = FastAPI(title="semantic-drift-sentinel adapter")

    @app.get("/healthz")
    async def healthz() -> dict:
        return {"status": "ok", "backend": settings.backend}

    @app.post("/evaluate")
    async def evaluate(req: EvalRequest) -> dict:
        evals = await process_batch(req.rows, DEMO_QUESTIONS)
        return {"evaluations": [e.model_dump() for e in evals]}

    return app
