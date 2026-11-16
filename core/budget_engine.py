"""Deterministic budget calculation.

All arithmetic uses ``Decimal`` so no binary floating-point rounding enters
financial data. No Streamlit, no AI.

The engine never invents prices. A recommendation whose catalog item is missing
is reported as a data error instead of being skipped silently, because a total
computed from an incomplete basket would be misleading.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Mapping, Sequence

from models.schemas import (
    BudgetAnalysis,
    BudgetInput,
    FurnitureItem,
    FurnitureRecommendation,
)

#: Money is rounded to kuruş (two decimal places) using half-up rounding.
MONEY_QUANTUM = Decimal("0.01")

#: Percentages are reported to one decimal place.
PERCENT_QUANTUM = Decimal("0.1")

ZERO = Decimal("0.00")


@dataclass(frozen=True)
class LineItem:
    """One priced line of the estimate."""

    item_id: str
    name: str
    quantity: int
    unit_cost: Decimal
    line_total: Decimal


@dataclass(frozen=True)
class BudgetLineError:
    """A basket problem that prevents a trustworthy total.

    ``code`` names the kind of problem (``unpriced_item``, ``invalid_quantity``,
    ``invalid_cost``, ``negative_cost``, ``negative_materials``,
    ``negative_other_expenses``) so callers can react without parsing the
    message text.
    """

    item_id: str
    message: str
    code: str = "budget_data"


@dataclass(frozen=True)
class BudgetResult:
    """Computed budget figures plus the data problems encountered."""

    analysis: BudgetAnalysis
    line_items: tuple[LineItem, ...]
    errors: tuple[BudgetLineError, ...]
    warnings: tuple[str, ...]
    budget_usage_percent: Decimal | None
    line_count: int

    @property
    def is_trustworthy(self) -> bool:
        """False when the total was computed from an incomplete basket."""

        return not self.errors


def to_money(value: Decimal | int | float | str) -> Decimal:
    """Coerce a value to a two-decimal money amount."""

    if isinstance(value, Decimal):
        amount = value
    elif isinstance(value, bool):
        raise TypeError("A boolean is not a valid money amount.")
    else:
        try:
            amount = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(f"'{value}' is not a valid money amount.") from exc

    if not amount.is_finite():
        raise ValueError(f"'{value}' is not a finite money amount.")

    return amount.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def format_money(amount: Decimal, currency: str = "TRY") -> str:
    """Group thousands the way the interface does, with an explicit currency.

    The engine writes sentences that the interface shows verbatim, so its
    figures have to look like the ones beside them: ``12.700,00 TRY``, not
    ``12700.00``. ``ui.commits`` and ``core.report_generator`` delegate here, so
    there is one implementation and no format can drift from another.
    """

    whole, _, fraction = f"{to_money(amount):.2f}".partition(".")
    grouped = f"{int(whole):,}".replace(",", ".")
    return f"{grouped},{fraction} {currency}"


def percent_of(part: Decimal, whole: Decimal) -> Decimal | None:
    """``part`` as a percentage of ``whole``.

    Returns ``None`` when ``whole`` is zero, because an undefined ratio must not
    be reported as ``0%`` or ``inf``.
    """

    if whole == 0:
        return None
    return (part / whole * Decimal(100)).quantize(
        PERCENT_QUANTUM, rounding=ROUND_HALF_UP
    )


def price_recommendations(
    recommendations: Sequence[FurnitureRecommendation],
    catalog: Sequence[FurnitureItem] | Mapping[str, FurnitureItem],
) -> tuple[list[LineItem], list[BudgetLineError], Decimal]:
    """Price each recommendation against the catalog.

    Returns the priced lines, the data errors and the furniture subtotal.
    """

    by_id: Mapping[str, FurnitureItem]
    if isinstance(catalog, Mapping):
        by_id = catalog
    else:
        by_id = {item.item_id: item for item in catalog}

    lines: list[LineItem] = []
    errors: list[BudgetLineError] = []
    subtotal = ZERO

    for index, recommendation in enumerate(recommendations):
        item = by_id.get(recommendation.item_id)
        if item is None:
            errors.append(
                BudgetLineError(
                    item_id=recommendation.item_id,
                    message=(
                        f"The estimate excludes recommendation {index + 1} "
                        f"('{recommendation.item_id}') because it could not be "
                        "priced from the catalog."
                    ),
                    code="unpriced_item",
                )
            )
            continue

        if recommendation.quantity < 1:
            errors.append(
                BudgetLineError(
                    item_id=recommendation.item_id,
                    message=(
                        f"'{item.name}' has a non-positive quantity "
                        f"({recommendation.quantity}) and cannot be priced."
                    ),
                    code="invalid_quantity",
                )
            )
            continue

        try:
            unit_cost = to_money(item.indicative_unit_cost)
        except (TypeError, ValueError) as exc:
            errors.append(
                BudgetLineError(
                    item_id=item.item_id,
                    message=(
                        f"The estimate excludes '{item.name}' because its "
                        f"catalog cost is not a usable money amount ({exc})."
                    ),
                    code="invalid_cost",
                )
            )
            continue

        if unit_cost < 0:
            errors.append(
                BudgetLineError(
                    item_id=item.item_id,
                    message=(
                        f"The estimate excludes '{item.name}' because its catalog "
                        f"cost is negative ({unit_cost})."
                    ),
                    code="negative_cost",
                )
            )
            continue

        line_total = to_money(unit_cost * recommendation.quantity)
        subtotal += line_total

        lines.append(
            LineItem(
                item_id=item.item_id,
                name=item.name,
                quantity=recommendation.quantity,
                unit_cost=unit_cost,
                line_total=line_total,
            )
        )

    return lines, errors, to_money(subtotal)


#: Codes reported for a negative non-catalog expense.
_NEGATIVE_CODES = {
    "material_subtotal": "negative_materials",
    "other_expenses": "negative_other_expenses",
}


def _coerce_expense(
    value: Decimal | int | float | str,
    *,
    field: str,
    label: str,
    errors: list[BudgetLineError],
) -> Decimal:
    """Coerce a non-catalog expense, reporting bad input instead of raising.

    These values arrive from the interface or a stored project, so a malformed
    amount must become a reported data problem rather than an exception that
    loses the rest of the analysis.
    """

    try:
        amount = to_money(value)
    except (TypeError, ValueError) as exc:
        errors.append(
            BudgetLineError(
                item_id=field,
                message=f"The {label} is not a usable money amount ({exc}).",
                code="invalid_expense",
            )
        )
        return ZERO

    if amount < 0:
        errors.append(
            BudgetLineError(
                item_id=field,
                message=f"The {label} cannot be negative.",
                code=_NEGATIVE_CODES[field],
            )
        )
        return ZERO

    return amount


def compute_budget(
    budget: BudgetInput,
    recommendations: Sequence[FurnitureRecommendation],
    catalog: Sequence[FurnitureItem] | Mapping[str, FurnitureItem],
    *,
    material_subtotal: Decimal | int | float | str = ZERO,
    other_expenses: Decimal | int | float | str = ZERO,
) -> BudgetResult:
    """Compute the full budget analysis.

    ``material_subtotal`` and ``other_expenses`` are explicit inputs rather than
    catalog lookups because materials are not part of the furniture catalog.
    """

    lines, errors, furniture_subtotal = price_recommendations(
        recommendations, catalog
    )

    materials = _coerce_expense(
        material_subtotal,
        field="material_subtotal",
        label="material subtotal",
        errors=errors,
    )
    others = _coerce_expense(
        other_expenses,
        field="other_expenses",
        label="other expenses",
        errors=errors,
    )

    total = to_money(furniture_subtotal + materials + others)
    available = to_money(budget.total_budget)
    remaining = to_money(available - total)

    warnings: list[str] = []
    is_over = total > available
    usage = percent_of(total, available)

    if available == ZERO:
        if is_over:
            warnings.append(
                f"The budget is zero, so the entire estimate of "
                f"{format_money(total, budget.currency)} is an overrun and usage "
                "cannot be expressed as a percentage."
            )
        else:
            warnings.append(
                "The budget is zero, so budget usage cannot be expressed as a "
                "percentage."
            )
    elif is_over:
        warnings.append(
            f"The estimate exceeds the budget by "
            f"{format_money(abs(remaining), budget.currency)} "
            f"({usage}% of the available budget)."
        )
    elif total == available:
        warnings.append(
            "The estimate matches the budget exactly; no contingency remains."
        )

    analysis = BudgetAnalysis(
        currency=budget.currency,
        furniture_subtotal=furniture_subtotal,
        material_subtotal=materials,
        other_expenses=others,
        total_estimated=total,
        remaining_budget=remaining,
        is_over_budget=is_over,
    )

    return BudgetResult(
        analysis=analysis,
        line_items=tuple(lines),
        errors=tuple(errors),
        warnings=tuple(warnings),
        budget_usage_percent=usage,
        line_count=len(lines),
    )


__all__ = [
    "MONEY_QUANTUM",
    "PERCENT_QUANTUM",
    "BudgetLineError",
    "BudgetResult",
    "LineItem",
    "compute_budget",
    "format_money",
    "percent_of",
    "price_recommendations",
    "to_money",
]
