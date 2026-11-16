"""The deterministic half of the Budget Analysis step.

Everything here is plain Python: no Streamlit, no AI, no session state. Both the
plan screen and the budget screen call :func:`compute_estimate`, so the rule
about materials is written once and cannot drift between the two.

Why a separate module
--------------------
``AGENTS.md`` §8 puts every price on Python's side, and ``core.budget_engine``
already owns the arithmetic: quantities, per-line totals, the furniture subtotal,
the remaining budget and the over-budget flag. This module adds nothing to that.
It only supplies the two inputs the engine cannot know by itself:

* **materials carry no price in V1.** There is no material price list, so the
  material subtotal is passed as an explicit zero *and* reported to the user as
  unpriced. Costing a material at zero would silently understate the estimate,
  which is why :data:`MATERIALS_NOTE` says so in words rather than leaving an
  empty column to be read as "free".
* **the total is indicative.** The catalog's own disclaimer is surfaced instead
  of an invented one.

:func:`matches` is the single definition of "the stored analysis still describes
the current basket", used by the budget screen and by the design evaluation
before it is allowed to call the model.
"""

from __future__ import annotations

from typing import Sequence

from core.budget_engine import BudgetResult, ZERO, compute_budget
from models.schemas import (
    BudgetAnalysis,
    BudgetInput,
    FurnitureItem,
    FurnitureRecommendation,
)

#: Shown wherever the estimate is presented. Materials are excluded, not free.
MATERIALS_NOTE = (
    "Materials and finishes are not included in the estimate and are not priced "
    "at zero: the application has no material price list, so their cost is "
    "unknown. The furniture total below covers catalog furniture only."
)

#: Shown beside the totals. Prevents an indicative figure being read as a quote.
INDICATIVE_NOTE = (
    "Every amount is an indicative estimate calculated from the local catalog's "
    "illustrative unit costs. These are not verified market prices, supplier "
    "quotations or current retail figures."
)

#: Why the estimate can be incomplete while still being shown.
INCOMPLETE_NOTE = (
    "The estimate could not price every item in the basket. The total covers "
    "only the items listed with a cost, so it is not a final figure and the "
    "excluded items are named below."
)


def compute_estimate(
    budget: BudgetInput,
    recommendations: Sequence[FurnitureRecommendation],
    catalog: Sequence[FurnitureItem],
) -> BudgetResult:
    """Price the current basket, with materials explicitly excluded.

    The engine, not this function, decides whether the basket is trustworthy:
    an item it cannot price becomes a reported ``BudgetLineError`` rather than a
    zero, and :attr:`core.budget_engine.BudgetResult.is_trustworthy` then reads
    False.
    """

    return compute_budget(
        budget,
        recommendations,
        catalog,
        material_subtotal=ZERO,
    )


def matches(stored: BudgetAnalysis | None, result: BudgetResult | None) -> bool:
    """True when the stored analysis is exactly what the current basket yields.

    A stored analysis that disagrees with the engine is stale, whatever the
    screen's widgets say. Comparing the models is enough because the engine is
    deterministic and the analysis holds every figure it produced.
    """

    return stored is not None and result is not None and stored == result.analysis


def unpriced_errors(result: BudgetResult) -> tuple[str, ...]:
    """The basket entries that were left out because they could not be priced."""

    return tuple(
        error.item_id for error in result.errors if error.code == "unpriced_item"
    )


def usage_text(result: BudgetResult) -> str:
    """Budget usage as a sentence, or an explicit "cannot be shown"."""

    if result.budget_usage_percent is None:
        return "Not available: the budget is zero, so usage cannot be a percentage."
    return f"{result.budget_usage_percent}% of the budget limit"


__all__ = [
    "INCOMPLETE_NOTE",
    "INDICATIVE_NOTE",
    "MATERIALS_NOTE",
    "compute_estimate",
    "matches",
    "unpriced_errors",
    "usage_text",
]
