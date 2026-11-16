"""Tests for the deterministic budget engine.

All figures come from the real local catalog:

* ``sofa_three_seat`` — 18 500 TRY
* ``coffee_table``    — 4 900 TRY

so an expected total of 23 400 TRY is traceable to the data file rather than to
a number invented inside a test.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from core.budget_engine import (
    MONEY_QUANTUM,
    compute_budget,
    percent_of,
    price_recommendations,
    to_money,
)
from models.schemas import (
    BudgetInput,
    FurnitureItem,
    FurnitureRecommendation,
    RoomType,
)

CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "furniture_catalog.json"

SOFA_COST = Decimal("18500.00")
TABLE_COST = Decimal("4900.00")
BOTH_COST = SOFA_COST + TABLE_COST


@pytest.fixture(scope="module")
def catalog() -> list[FurnitureItem]:
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return [FurnitureItem(**record) for record in payload["items"]]


def basket() -> list[FurnitureRecommendation]:
    return [
        FurnitureRecommendation(item_id="sofa_three_seat", quantity=1),
        FurnitureRecommendation(item_id="coffee_table", quantity=1),
    ]


def budget(amount: str) -> BudgetInput:
    return BudgetInput(total_budget=Decimal(amount))


def item(item_id: str, cost: str, name: str = "Item") -> FurnitureItem:
    return FurnitureItem(
        item_id=item_id,
        name=name,
        category="Test",
        width_cm=100,
        depth_cm=60,
        indicative_unit_cost=Decimal(cost),
        supported_room_types=[RoomType.LIVING_ROOM],
    )


# --------------------------------------------------------------------------- #
# Money helpers
# --------------------------------------------------------------------------- #


def test_to_money_returns_decimal_not_float() -> None:
    assert isinstance(to_money(18500), Decimal)


def test_to_money_keeps_two_decimal_places() -> None:
    assert to_money("1234.5") == Decimal("1234.50")
    assert to_money("1234.5").as_tuple().exponent == -2


def test_to_money_rounds_half_up() -> None:
    assert to_money("10.005") == Decimal("10.01")
    assert to_money("10.004") == Decimal("10.00")


def test_to_money_rejects_booleans() -> None:
    with pytest.raises(TypeError):
        to_money(True)


def test_to_money_rejects_non_numeric_text() -> None:
    with pytest.raises(ValueError):
        to_money("not a price")


def test_to_money_rejects_infinity() -> None:
    with pytest.raises(ValueError):
        to_money("Infinity")


def test_percent_of_reports_a_ratio() -> None:
    assert percent_of(Decimal("23400"), Decimal("45000")) == Decimal("52.0")


def test_percent_of_rounds_to_one_decimal_place() -> None:
    assert percent_of(Decimal("1"), Decimal("3")) == Decimal("33.3")


def test_percent_of_zero_whole_is_undefined() -> None:
    # 0/0 must not be reported as 0% or as an error value.
    assert percent_of(Decimal("100"), Decimal("0")) is None


# --------------------------------------------------------------------------- #
# Pricing individual lines
# --------------------------------------------------------------------------- #


def test_price_recommendations_sums_the_basket(
    catalog: list[FurnitureItem],
) -> None:
    lines, errors, subtotal = price_recommendations(basket(), catalog)
    assert errors == []
    assert subtotal == BOTH_COST
    assert [line.name for line in lines] == ["Three-seat sofa", "Coffee table"]
    assert lines[0].unit_cost == SOFA_COST
    assert lines[0].line_total == SOFA_COST


def test_quantity_multiplies_the_line_total(catalog: list[FurnitureItem]) -> None:
    lines, errors, subtotal = price_recommendations(
        [FurnitureRecommendation(item_id="dining_chair", quantity=4)], catalog
    )
    assert errors == []
    assert lines[0].quantity == 4
    assert lines[0].line_total == Decimal("9600.00")
    assert subtotal == Decimal("9600.00")


def test_empty_basket_prices_to_zero(catalog: list[FurnitureItem]) -> None:
    lines, errors, subtotal = price_recommendations([], catalog)
    assert (lines, errors) == ([], [])
    assert subtotal == Decimal("0.00")


# --------------------------------------------------------------------------- #
# Under, equal and over budget
# --------------------------------------------------------------------------- #


def test_under_budget_leaves_a_positive_remainder(
    catalog: list[FurnitureItem],
) -> None:
    result = compute_budget(budget("45000.00"), basket(), catalog)
    assert result.is_trustworthy is True
    assert result.analysis.furniture_subtotal == BOTH_COST
    assert result.analysis.total_estimated == BOTH_COST
    assert result.analysis.remaining_budget == Decimal("21600.00")
    assert result.analysis.is_over_budget is False
    assert result.budget_usage_percent == Decimal("52.0")


def test_exactly_on_budget_leaves_no_remainder(
    catalog: list[FurnitureItem],
) -> None:
    result = compute_budget(budget("23400.00"), basket(), catalog)
    assert result.analysis.remaining_budget == Decimal("0.00")
    assert result.analysis.is_over_budget is False
    assert result.budget_usage_percent == Decimal("100.0")
    assert any("exactly" in warning for warning in result.warnings)


def test_over_budget_reports_a_negative_remainder(
    catalog: list[FurnitureItem],
) -> None:
    result = compute_budget(budget("20000.00"), basket(), catalog)
    assert result.analysis.is_over_budget is True
    assert result.analysis.remaining_budget == Decimal("-3400.00")
    assert result.analysis.total_estimated == BOTH_COST
    assert result.budget_usage_percent == Decimal("117.0")
    assert any("exceeds the budget" in warning for warning in result.warnings)


def test_the_overrun_warning_states_its_figure_in_the_ui_format(
    catalog: list[FurnitureItem],
) -> None:
    """The interface prints engine warnings verbatim, so they must match its format.

    A raw ``3400.00 TRY`` beside a ``3.400,00 TRY`` badge on the same screen
    reads as two different numbers.
    """

    result = compute_budget(budget("20000.00"), basket(), catalog)
    warning = next(w for w in result.warnings if "exceeds the budget" in w)
    assert "3.400,00 TRY" in warning
    assert "3400.00" not in warning


def test_a_zero_budget_overrun_states_its_figure_in_the_ui_format(
    catalog: list[FurnitureItem],
) -> None:
    result = compute_budget(budget("0.00"), basket(), catalog)
    warning = next(w for w in result.warnings if "overrun" in w)
    assert "23.400,00 TRY" in warning
    assert "23400.00" not in warning


def test_one_lira_under_budget_is_not_an_overrun(
    catalog: list[FurnitureItem],
) -> None:
    result = compute_budget(budget("23401.00"), basket(), catalog)
    assert result.analysis.is_over_budget is False
    assert result.analysis.remaining_budget == Decimal("1.00")


def test_one_lira_over_budget_is_an_overrun(
    catalog: list[FurnitureItem],
) -> None:
    result = compute_budget(budget("23399.00"), basket(), catalog)
    assert result.analysis.is_over_budget is True
    assert result.analysis.remaining_budget == Decimal("-1.00")


def test_small_overrun_is_exact_even_when_percentage_rounds_to_100(
    catalog: list[FurnitureItem],
) -> None:
    # 23400 / 23399 = 100.004...%, which rounds to 100.0%. The overrun flag is
    # computed from exact decimals, so it stays correct regardless of display
    # rounding. This pins that behaviour rather than pretending it is exact.
    result = compute_budget(budget("23399.00"), basket(), catalog)
    assert result.budget_usage_percent == Decimal("100.0")
    assert result.analysis.is_over_budget is True


# --------------------------------------------------------------------------- #
# Zero and empty input
# --------------------------------------------------------------------------- #


def test_zero_budget_has_no_usage_percentage(
    catalog: list[FurnitureItem],
) -> None:
    result = compute_budget(budget("0.00"), basket(), catalog)
    assert result.budget_usage_percent is None
    assert result.analysis.total_estimated == BOTH_COST
    assert result.analysis.is_over_budget is True
    assert any("zero" in warning for warning in result.warnings)


def test_zero_budget_with_empty_basket_is_not_an_overrun(
    catalog: list[FurnitureItem],
) -> None:
    result = compute_budget(budget("0.00"), [], catalog)
    assert result.analysis.total_estimated == Decimal("0.00")
    assert result.analysis.is_over_budget is False
    assert result.budget_usage_percent is None
    # A zero budget with a zero estimate is not "exactly on budget" in any
    # useful sense; only the undefined-percentage notice should appear.
    assert not any("exactly" in warning for warning in result.warnings)


def test_zero_budget_overrun_names_the_overrun(
    catalog: list[FurnitureItem],
) -> None:
    result = compute_budget(budget("0.00"), basket(), catalog)
    assert any("overrun" in warning for warning in result.warnings)


def test_empty_recommendations_produce_a_zero_total(
    catalog: list[FurnitureItem],
) -> None:
    result = compute_budget(budget("45000.00"), [], catalog)
    assert result.analysis.total_estimated == Decimal("0.00")
    assert result.analysis.remaining_budget == Decimal("45000.00")
    assert result.line_items == ()
    assert result.line_count == 0
    assert result.budget_usage_percent == Decimal("0.0")


# --------------------------------------------------------------------------- #
# Invalid cost data
# --------------------------------------------------------------------------- #


def test_unknown_catalog_item_blocks_a_trustworthy_total(
    catalog: list[FurnitureItem],
) -> None:
    result = compute_budget(
        budget("45000.00"),
        [FurnitureRecommendation(item_id="ghost_item", quantity=1)],
        catalog,
    )
    assert result.is_trustworthy is False
    assert len(result.errors) == 1
    assert result.errors[0].item_id == "ghost_item"
    assert "ghost_item" in result.errors[0].message
    # The message must say what the total *excludes*, not merely that pricing
    # failed, so a reader cannot mistake the subtotal for a full basket.
    assert "excludes" in result.errors[0].message
    assert result.analysis.total_estimated == Decimal("0.00")


def test_unknown_item_does_not_discard_valid_lines(
    catalog: list[FurnitureItem],
) -> None:
    result = compute_budget(
        budget("45000.00"),
        [
            FurnitureRecommendation(item_id="sofa_three_seat", quantity=1),
            FurnitureRecommendation(item_id="ghost_item", quantity=1),
        ],
        catalog,
    )
    assert result.analysis.furniture_subtotal == SOFA_COST
    assert result.is_trustworthy is False
    assert result.line_count == 1


def test_negative_material_subtotal_is_rejected(
    catalog: list[FurnitureItem],
) -> None:
    result = compute_budget(
        budget("45000.00"), basket(), catalog, material_subtotal="-500.00"
    )
    assert result.is_trustworthy is False
    assert result.analysis.material_subtotal == Decimal("0.00")
    assert result.analysis.total_estimated == BOTH_COST
    assert [error.code for error in result.errors] == ["negative_materials"]


def test_unusable_material_subtotal_is_reported(
    catalog: list[FurnitureItem],
) -> None:
    result = compute_budget(
        budget("45000.00"), basket(), catalog, material_subtotal="lots"
    )
    assert result.is_trustworthy is False
    assert result.analysis.material_subtotal == Decimal("0.00")
    assert result.analysis.total_estimated == BOTH_COST
    assert [error.code for error in result.errors] == ["invalid_expense"]


def test_negative_other_expenses_are_rejected(
    catalog: list[FurnitureItem],
) -> None:
    result = compute_budget(
        budget("45000.00"), basket(), catalog, other_expenses="-1.00"
    )
    assert result.is_trustworthy is False
    assert result.analysis.other_expenses == Decimal("0.00")
    assert [error.code for error in result.errors] == ["negative_other_expenses"]


def test_material_and_other_costs_are_added_to_the_total(
    catalog: list[FurnitureItem],
) -> None:
    result = compute_budget(
        budget("45000.00"),
        basket(),
        catalog,
        material_subtotal="3000.00",
        other_expenses="1250.50",
    )
    assert result.analysis.material_subtotal == Decimal("3000.00")
    assert result.analysis.other_expenses == Decimal("1250.50")
    assert result.analysis.total_estimated == BOTH_COST + Decimal("4250.50")
    assert result.is_trustworthy is True


def test_catalog_item_with_an_unusable_cost_is_reported_not_raised() -> None:
    # A hand-edited catalog could carry a broken cost. The engine must report
    # it as data, not crash the whole budget calculation.
    broken = FurnitureItem.model_construct(
        item_id="broken",
        name="Broken Item",
        category="Test",
        width_cm=100,
        depth_cm=60,
        indicative_unit_cost=Decimal("-50.00"),
        supported_room_types=[RoomType.LIVING_ROOM],
        drawing_shape="rectangle",
    )
    result = compute_budget(
        budget("45000.00"),
        [FurnitureRecommendation(item_id="broken", quantity=1)],
        [broken],
    )
    assert result.is_trustworthy is False
    assert result.analysis.total_estimated == Decimal("0.00")
    assert "Broken Item" in result.errors[0].message


def test_mapping_catalog_is_accepted() -> None:
    mapping = {"only_item": item("only_item", "100.00")}
    result = compute_budget(
        budget("500.00"),
        [FurnitureRecommendation(item_id="only_item", quantity=2)],
        mapping,
    )
    assert result.analysis.total_estimated == Decimal("200.00")


def test_a_budget_cannot_be_negative() -> None:
    # The model already forbids this, so the engine never sees it. The test
    # documents that the guard lives upstream rather than being absent.
    with pytest.raises(Exception):
        budget("-1.00")


# --------------------------------------------------------------------------- #
# Model contract
# --------------------------------------------------------------------------- #


def test_analysis_currency_comes_from_the_budget(
    catalog: list[FurnitureItem],
) -> None:
    result = compute_budget(budget("45000.00"), basket(), catalog)
    assert result.analysis.currency == "TRY"


def test_analysis_money_fields_are_decimal(
    catalog: list[FurnitureItem],
) -> None:
    analysis = compute_budget(budget("45000.00"), basket(), catalog).analysis
    for value in (
        analysis.furniture_subtotal,
        analysis.total_estimated,
        analysis.remaining_budget,
    ):
        assert isinstance(value, Decimal)
        assert value.as_tuple().exponent == -2


def test_money_quantum_is_two_decimal_places() -> None:
    assert MONEY_QUANTUM == Decimal("0.01")
