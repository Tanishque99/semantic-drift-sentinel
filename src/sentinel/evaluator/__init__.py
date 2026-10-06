"""Evaluator factory: one env var picks the backend, same typed contract."""

from __future__ import annotations

from ..config import settings
from .base import Evaluator, aggregate_quality, answer_to_unit

__all__ = ["Evaluator", "get_evaluator", "aggregate_quality", "answer_to_unit"]


def get_evaluator(backend: str | None = None) -> Evaluator:
    name = (backend or settings.backend).lower()
    if name == "jev":
        from .jev import JevEvaluator
        return JevEvaluator()
    if name == "claude":
        from .claude import ClaudeEvaluator
        return ClaudeEvaluator()
    if name == "mock":
        from .mock import MockEvaluator
        return MockEvaluator()
    raise ValueError(
        f"unknown backend {name!r}; set JEV_BACKEND to one of: jev, claude, mock"
    )
