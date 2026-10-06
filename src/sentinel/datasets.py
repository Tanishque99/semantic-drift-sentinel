"""Dataset registry -- the pipeline is generic over the data it scores.

A `DatasetSpec` bundles everything that is dataset-specific: the warehouse
table shape, which column is the enum to validate, which column must be
non-empty, the typed questions Jev answers, the quality weights, and the row
generator. The warehouse, adapter, and demo are all driven by one of these, so
adding a new drift scenario is a matter of adding a spec.

Two ship with the repo:

  * `tickets` -- support tickets whose v2 resolution summaries silently stop
    addressing the ticket (drift in a free-text column).
  * `goods`   -- a product catalog whose v2 category is silently wrong, e.g.
    the iPhone moves from `Mobile` to `Home Appliances`. The category string
    stays valid; only its meaning drifts (drift in an enum column).

Pick one with the `DATASET` env var (default `tickets`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from . import sampledata, sampledata_goods
from .schemas import (
    DEMO_QUESTIONS,
    QUALITY_WEIGHTS,
    Question,
    QuestionType,
)


@dataclass(frozen=True)
class DatasetSpec:
    name: str
    table: str
    # Content columns -- stored as VARCHAR and sent to Jev as the row `state`.
    text_columns: tuple[str, ...]
    enum_column: str                 # the category-like column to validate
    valid_values: tuple[str, ...]    # the allowed enum values
    completeness_column: str         # the column that must be non-empty
    questions: list[Question]
    quality_weights: dict[str, float]
    rows_fn: Callable[[], list[dict]]
    headline: str                    # one-line story for the demo banner
    review_reason: str               # shown in the human-review queue

    def rows(self) -> list[dict]:
        return self.rows_fn()


# --- goods question set -----------------------------------------------------
# The drift is in the `category` column, so the headline question asks whether
# the category is right for the product. `catalog_accuracy` (a SCORE) exercises
# the full typed contract; `description_matches_product` stays high in both
# versions, which is what keeps the mean from collapsing to zero.

GOODS_QUESTIONS: list[Question] = [
    Question(
        key="category_correct",
        type=QuestionType.NOUL,
        label="category_ok",
        instructions=(
            "Is the assigned `category` the correct product category for the "
            "item named in product_name and described in description?"
        ),
    ),
    Question(
        key="description_matches_product",
        type=QuestionType.NOUL,
        label="desc_match",
        instructions=(
            "Does the description actually describe the product named in "
            "product_name?"
        ),
    ),
    Question(
        key="catalog_accuracy",
        type=QuestionType.SCORE,
        label="catalog(1-5)",
        instructions=(
            "Rate how accurately this product is catalogued overall, where "
            "product_name, category, and description should all be consistent."
        ),
        levels=[
            "Badly miscatalogued; the category is wrong for the product.",
            "Mostly wrong; category or description clearly does not fit.",
            "Partially correct but with a meaningful inconsistency.",
            "Mostly accurate with only a minor inconsistency.",
            "Fully accurate; name, category, and description all agree.",
        ],
    ),
]

GOODS_WEIGHTS = {
    "category_correct": 0.5,
    "description_matches_product": 0.2,
    "catalog_accuracy": 0.3,
}


TICKETS = DatasetSpec(
    name="tickets",
    table="tickets",
    text_columns=("ticket_text", "category", "resolution_summary"),
    enum_column="category",
    valid_values=tuple(sampledata.VALID_CATEGORIES),
    completeness_column="resolution_summary",
    questions=DEMO_QUESTIONS,
    quality_weights=QUALITY_WEIGHTS,
    rows_fn=sampledata.all_rows,
    headline=(
        "support tickets: between v1 and v2 the resolution summaries silently "
        "stopped addressing the actual ticket."
    ),
    review_reason="resolution_summary does not address the ticket",
)

GOODS = DatasetSpec(
    name="goods",
    table="products",
    text_columns=("product_name", "category", "description"),
    enum_column="category",
    valid_values=tuple(sampledata_goods.VALID_CATEGORIES_GOODS),
    completeness_column="description",
    questions=GOODS_QUESTIONS,
    quality_weights=GOODS_WEIGHTS,
    rows_fn=sampledata_goods.all_rows,
    headline=(
        "consumer goods data drift: between v1 and v2 products were silently "
        "miscategorised into a different valid category. The category string "
        "stays valid; its meaning is wrong."
    ),
    review_reason="category does not match the product",
)

DATASETS = {spec.name: spec for spec in (TICKETS, GOODS)}


def get_dataset(name: str | None = None) -> DatasetSpec:
    key = (name or "tickets").strip().lower()
    try:
        return DATASETS[key]
    except KeyError:
        raise ValueError(
            f"unknown dataset {key!r}; choose one of: {', '.join(DATASETS)}"
        ) from None
