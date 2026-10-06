"""Typed contracts for the semantic evaluation layer.

This is the "TypeSafe" boundary in the architecture: the Jev evaluator must
return answers that validate against these schemas, so the rest of the pipeline
never parses free text. It mirrors Jev's own `state + questions -> typed
answers` contract (Noul / Choice / Score).
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class QuestionType(str, Enum):
    NOUL = "noul"       # yes/no -> probability the answer is "yes"
    CHOICE = "choice"   # pick one of a fixed set of options
    SCORE = "score"     # ordered rubric level


class Question(BaseModel):
    """A single atomic judgment to make against a row's state."""

    key: str
    type: QuestionType
    instructions: str
    # Short column header for display; falls back to `key` when empty.
    label: str = ""
    # Only used for CHOICE questions: option_key -> what it means.
    criteria: dict[str, str] = Field(default_factory=dict)
    # Only used for SCORE questions: an ordered rubric, low end -> high end.
    # Jev requires these level descriptions.
    levels: list[str] = Field(default_factory=list)

    @property
    def header(self) -> str:
        return self.label or self.key


class Answer(BaseModel):
    """A typed, calibrated answer to one Question.

    `noul` is the probability (0..1) that the yes/no answer is "yes".
    `choice` is the selected option key for CHOICE questions.
    `score` is the rubric level for SCORE questions.
    `confidence` is the model's calibrated confidence in the answer.
    """

    key: str
    type: QuestionType
    noul: float | None = None
    choice: str | None = None
    score: float | None = None
    confidence: float = 1.0

    @field_validator("noul", "confidence")
    @classmethod
    def _in_unit_interval(cls, v: float | None) -> float | None:
        if v is None:
            return v
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"expected a probability in [0, 1], got {v}")
        return v


class RowEvaluation(BaseModel):
    """All answers for one warehouse row, plus a derived quality score."""

    row_id: str
    deployment_version: str
    answers: dict[str, Answer]
    quality: float  # 0..1 aggregate semantic quality for this row
    backend: str
    latency_ms: float
    cost_usd: float = 0.0


class CircuitState(str, Enum):
    CLOSED = "closed"  # healthy, data flows
    OPEN = "open"      # tripped, downstream blocked


class BreakerDecision(BaseModel):
    state: CircuitState
    deployment_version: str
    mean_quality: float
    drift_vs_baseline: float
    threshold: float
    reason: str
    routed_to_review: int = 0


# ---------------------------------------------------------------------------
# The question set the demo evaluates against. Each is an *atomic* judgment,
# per Jev's design guidance (one decision a knowledgeable person makes fast).
# ---------------------------------------------------------------------------

Severity = Literal["billing", "technical", "account", "other"]

DEMO_QUESTIONS: list[Question] = [
    Question(
        key="summary_addresses_ticket",
        type=QuestionType.NOUL,
        label="addresses_ticket",
        instructions=(
            "Does the resolution_summary actually address the specific problem "
            "the customer described in ticket_text? Answer about substance, not tone."
        ),
    ),
    Question(
        key="category_correct",
        type=QuestionType.NOUL,
        label="category_ok",
        instructions=(
            "Is the assigned `category` the correct category for the problem "
            "described in ticket_text?"
        ),
    ),
    Question(
        key="resolution_quality",
        type=QuestionType.SCORE,
        label="resolution(1-5)",
        instructions=(
            "Rate how well the resolution_summary resolves the customer's issue "
            "on a 1-5 scale, where 1 is irrelevant/generic and 5 is a complete, "
            "specific resolution."
        ),
        levels=[
            "Irrelevant or generic; does not engage the customer's actual issue.",
            "Barely relevant; mentions the topic but offers no real resolution.",
            "Partially addresses the issue but leaves it largely unresolved.",
            "Mostly resolves the issue with minor gaps.",
            "Complete, specific resolution of the customer's actual issue.",
        ],
    ),
]

# Weights for aggregating answers into a single 0..1 quality score per row.
QUALITY_WEIGHTS = {
    "summary_addresses_ticket": 0.5,
    "category_correct": 0.2,
    "resolution_quality": 0.3,
}
