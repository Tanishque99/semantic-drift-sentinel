"""Claude as a Jev-style "System One" judge.

Implements the SAME typed contract as the real Jev backend (Noul / Score with a
calibrated probability), but backed by Claude via forced tool use so the output
is always schema-valid JSON -- never free text we have to parse. This is the
default backend when ANTHROPIC_API_KEY is present, which keeps the demo runnable
on any laptop, while `JEV_BACKEND=jev` swaps in the real product unchanged.

Model id: claude-haiku-4-5 (fast + cheap, a good analog to a System-One judge).
"""

from __future__ import annotations

import json

from ..config import settings
from ..schemas import Answer, Question, QuestionType

_SYSTEM = (
    "You are a strict data-quality judge. You evaluate whether an upstream "
    "pipeline preserved the MEANING of support-ticket data. Judge substance, "
    "not politeness. A generic, deflecting, or off-topic resolution_summary "
    "does NOT address the ticket even if it is polite. Answer every question "
    "independently and calibrate your probabilities to reality."
)


def _tool_schema(questions: list[Question]) -> dict:
    props: dict = {}
    for q in questions:
        if q.type == QuestionType.NOUL:
            props[q.key] = {
                "type": "object",
                "properties": {
                    "noul": {"type": "number", "minimum": 0, "maximum": 1,
                             "description": f"Probability that YES: {q.instructions}"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": ["noul", "confidence"],
            }
        elif q.type == QuestionType.SCORE:
            props[q.key] = {
                "type": "object",
                "properties": {
                    "score": {"type": "number", "minimum": 1, "maximum": 5,
                              "description": q.instructions},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": ["score", "confidence"],
            }
        elif q.type == QuestionType.CHOICE:
            props[q.key] = {
                "type": "object",
                "properties": {
                    "choice": {"type": "string", "enum": list(q.criteria.keys())},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": ["choice", "confidence"],
            }
    return {
        "name": "record_judgment",
        "description": "Record the typed judgment for every question.",
        "input_schema": {"type": "object", "properties": props,
                         "required": list(props.keys())},
    }


class ClaudeEvaluator:
    name = "claude"
    price_per_mtok = settings.claude_price_per_mtok

    def __init__(self) -> None:
        from anthropic import AsyncAnthropic  # imported lazily

        self.client = AsyncAnthropic()
        self.model = settings.claude_model

    async def evaluate(
        self, state: dict, questions: list[Question]
    ) -> tuple[dict[str, Answer], float]:
        tool = _tool_schema(questions)
        state_block = json.dumps(state, indent=2)
        msg = await self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=_SYSTEM,
            tools=[tool],
            tool_choice={"type": "tool", "name": "record_judgment"},
            messages=[{
                "role": "user",
                "content": (
                    "Evaluate this row's state against the questions encoded in "
                    f"the tool schema.\n\nstate:\n{state_block}"
                ),
            }],
        )

        payload: dict = {}
        for block in msg.content:
            if block.type == "tool_use":
                payload = block.input
                break

        answers: dict[str, Answer] = {}
        for q in questions:
            raw = payload.get(q.key, {}) if isinstance(payload, dict) else {}
            conf = float(raw.get("confidence", 0.8))
            if q.type == QuestionType.NOUL:
                answers[q.key] = Answer(key=q.key, type=q.type,
                                        noul=float(raw.get("noul", 0.0)), confidence=conf)
            elif q.type == QuestionType.SCORE:
                answers[q.key] = Answer(key=q.key, type=q.type,
                                        score=float(raw.get("score", 1.0)), confidence=conf)
            elif q.type == QuestionType.CHOICE:
                answers[q.key] = Answer(key=q.key, type=q.type,
                                        choice=raw.get("choice"), confidence=conf)

        tokens = float(getattr(msg.usage, "input_tokens", 0))
        return answers, tokens
