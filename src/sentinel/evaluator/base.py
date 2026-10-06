"""Evaluator protocol + shared aggregation logic.

Every backend takes the same input (a row's `state` + the shared `questions`)
and returns the same typed `Answer` objects. That uniformity is what lets you
flip `JEV_BACKEND` between `jev`, `claude`, and `mock` without touching the rest
of the pipeline.
"""

from __future__ import annotations

from typing import Protocol

from ..schemas import (
    Answer,
    QUALITY_WEIGHTS,
    Question,
    QuestionType,
)


class Evaluator(Protocol):
    name: str
    price_per_mtok: float

    async def evaluate(
        self, state: dict, questions: list[Question]
    ) -> tuple[dict[str, Answer], float]:
        """Return (answers_by_key, input_tokens_used)."""
        ...


def answer_to_unit(answer: Answer) -> float:
    """Normalize any answer type to a 0..1 goodness value for aggregation."""
    if answer.type == QuestionType.NOUL:
        return answer.noul if answer.noul is not None else 0.0
    if answer.type == QuestionType.SCORE:
        # SCORE questions in the demo are on a 1..5 rubric.
        s = answer.score if answer.score is not None else 1.0
        return max(0.0, min(1.0, (s - 1.0) / 4.0))
    if answer.type == QuestionType.CHOICE:
        # Treated as a confidence-weighted hit elsewhere; default neutral.
        return answer.confidence
    return 0.0


def aggregate_quality(answers: dict[str, Answer]) -> float:
    """Weighted 0..1 semantic quality score for a single row."""
    total_w = 0.0
    acc = 0.0
    for key, weight in QUALITY_WEIGHTS.items():
        if key in answers:
            acc += weight * answer_to_unit(answers[key])
            total_w += weight
    return acc / total_w if total_w else 0.0
