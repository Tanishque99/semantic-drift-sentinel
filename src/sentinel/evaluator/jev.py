"""The real Jev backend (TypeSafe AI) -- the production eval layer from the
architecture diagram.

Jev is a hosted "System One" model: you send `state` + `questions` and get back
typed answers with calibrated probabilities (Noul / Choice / Score). This is a
thin adapter that maps our Question/Answer schema onto the TypeSafe SDK. It is
selected automatically when TYPESAFE_API_KEY is set, or explicitly with
JEV_BACKEND=jev.

Docs: https://docs.typesafe.ai  ·  SDK: pip install typesafe-sdk
"""

from __future__ import annotations

from ..config import settings
from ..schemas import Answer, Question, QuestionType


class JevEvaluator:
    name = "jev"
    price_per_mtok = settings.jev_price_per_mtok

    def __init__(self) -> None:
        # Imported lazily so the package is only required when this backend runs.
        from typesafe_sdk import TypeSafeClient  # type: ignore

        self.client = TypeSafeClient()  # reads TYPESAFE_API_KEY
        self.model = settings.jev_model

    def _build_questions(self, questions: list[Question]) -> dict:
        from typesafe_sdk import Choice, Noul, Score  # type: ignore

        out: dict = {}
        for q in questions:
            if q.type == QuestionType.NOUL:
                out[q.key] = Noul(instructions=q.instructions)
            elif q.type == QuestionType.CHOICE:
                out[q.key] = Choice(instructions=q.instructions, criteria=q.criteria)
            elif q.type == QuestionType.SCORE:
                # Jev Score takes an ordered rubric as `criteria`: level
                # descriptions from the low end to the high end (0-based).
                levels = q.levels or [
                    "Very poor", "Poor", "Fair", "Good", "Excellent"
                ]
                out[q.key] = Score(instructions=q.instructions, criteria=list(levels))
        return out

    async def evaluate(
        self, state: dict, questions: list[Question]
    ) -> tuple[dict[str, Answer], float]:
        # The SDK call is synchronous; the async adapter already throttles
        # concurrency, so we invoke it directly inside the worker task.
        resp = self.client.system_one(
            model=self.model,
            state=state,
            questions=self._build_questions(questions),
        )

        answers: dict[str, Answer] = {}
        for q in questions:
            a = resp.answers[q.key]
            if q.type == QuestionType.NOUL:
                answers[q.key] = Answer(key=q.key, type=q.type,
                                        noul=float(a.noul),
                                        confidence=float(getattr(a, "confidence", 1.0)))
            elif q.type == QuestionType.CHOICE:
                answers[q.key] = Answer(key=q.key, type=q.type,
                                        choice=a.choice,
                                        confidence=float(getattr(a, "confidence", 1.0)))
            elif q.type == QuestionType.SCORE:
                # Jev returns the score as a 0-based probability-weighted mean
                # over the rubric indices. The rest of the pipeline (the demo
                # table, answer_to_unit) uses a 1..N convention, so shift by 1
                # to match.
                answers[q.key] = Answer(key=q.key, type=q.type,
                                        score=float(a.score) + 1.0,
                                        confidence=float(getattr(a, "confidence", 1.0)))

        tokens = float(getattr(getattr(resp, "usage", None), "input_tokens", 0) or 0)
        return answers, tokens
