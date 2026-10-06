"""Evaluator factory for the Jev semantic backend."""

from __future__ import annotations

from ..config import settings
from .base import Evaluator, aggregate_quality, answer_to_unit

__all__ = ["Evaluator", "get_evaluator", "aggregate_quality", "answer_to_unit"]


def get_evaluator(backend: str | None = None) -> Evaluator:
    name = (backend or settings.backend).lower()
    if name == "jev":
        from .jev import JevEvaluator
        return JevEvaluator()
    raise ValueError(
        f"unknown backend {name!r}; the only supported backend is: jev"
    )
