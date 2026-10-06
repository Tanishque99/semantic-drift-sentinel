"""Deterministic, zero-dependency evaluator.

Guarantees that `git clone && make demo` produces live, meaningful output with
no API keys and no network. It is NOT a random stub: it reads the actual row
content and scores whether the resolution summary shares salient terms with the
ticket, so it genuinely detects the planted v1 -> v2 semantic drift via content.
"""

from __future__ import annotations

import re

from ..schemas import Answer, Question, QuestionType

_STOP = {
    "the", "a", "an", "and", "or", "to", "of", "for", "in", "on", "at", "it",
    "is", "are", "was", "were", "you", "your", "we", "our", "i", "my", "me",
    "can", "will", "with", "that", "this", "not", "do", "does", "did", "have",
    "has", "had", "be", "been", "from", "up", "out", "so", "if", "all", "any",
}


def _terms(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", text.lower()) if w not in _STOP and len(w) > 2}


def _overlap(a: str, b: str) -> float:
    ta, tb = _terms(a), _terms(b)
    if not ta:
        return 0.0
    return len(ta & tb) / len(ta)


class MockEvaluator:
    name = "mock"
    price_per_mtok = 0.0

    async def evaluate(
        self, state: dict, questions: list[Question]
    ) -> tuple[dict[str, Answer], float]:
        ticket = state.get("ticket_text", "")
        summary = state.get("resolution_summary", "")
        rel = _overlap(ticket, summary)  # 0..1 term overlap

        answers: dict[str, Answer] = {}
        for q in questions:
            if q.key == "summary_addresses_ticket":
                # Map overlap to a probability with a soft threshold at ~0.12.
                p = max(0.02, min(0.98, (rel - 0.05) * 6.0))
                answers[q.key] = Answer(key=q.key, type=QuestionType.NOUL,
                                        noul=round(p, 3), confidence=0.8)
            elif q.key == "category_correct":
                # Category is valid in both versions -> high but not certain.
                answers[q.key] = Answer(key=q.key, type=QuestionType.NOUL,
                                        noul=0.9, confidence=0.7)
            elif q.key == "resolution_quality":
                score = 1.0 + round(min(1.0, rel * 5.0) * 4.0, 2)  # 1..5
                answers[q.key] = Answer(key=q.key, type=QuestionType.SCORE,
                                        score=score, confidence=0.75)
            else:
                answers[q.key] = Answer(key=q.key, type=q.type, noul=0.5,
                                        confidence=0.5)

        approx_tokens = (len(ticket) + len(summary)) / 4.0
        return answers, approx_tokens
