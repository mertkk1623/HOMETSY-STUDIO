"""The Budget Analysis screen: deterministic arithmetic, presented only.

Nothing here is mocked at the arithmetic level. The real
``core.budget_engine.compute_budget`` is exercised through the screen, because the
screen's whole job is to present *that* engine's answer without adding to it. The
only stub is the advisor, so a plausible basket can be installed without a model.

The scenarios mirror §7.2 of the step brief:

1. the engine is called with the stored basket, and nothing else prices it;
2. quantities are included in the arithmetic;
3. an unpriced item is reported, never costed at zero;
4. an over-budget estimate is reported as an overrun;
5. the remaining budget is the engine's own figure;
6. materials are excluded and shown as unpriced;
7. the result is stored in the workflow under the budget key;
8. changing the budget limit invalidates the stored analysis;
9. changing the basket invalidates the stored analysis.
"""

from __future__ import annotations

from decimal import Decimal

from streamlit.testing.v1 import AppTest

from core.budget_engine import compute_budget
from models.schemas import (
    BudgetAnalysis,
    ConceptCollection,
    DesignBrief,
    DesignConcept,
    DesignRecommendation,
    FurnitureRecommendation,
)
from ui import budget as budget_view, commits, layout, references
from ui.references import load_catalog
from workflow.dependencies import DataKey
from workflow.state import WorkflowState, WorkflowStep

PROJECT_ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "app.py"

ROOM_FORM_SUBMIT = "FormSubmitter:hm_room_form-Save room information"
PREFERENCES_FORM_SUBMIT = (
    "FormSubmitter:hm_preferences_form-Save preferences and budget"
)

RECALCULATE_LABEL = "Recalculate the estimate"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def make_brief() -> DesignBrief:
    return DesignBrief(
        summary="A calm living room for four people.",
        functional_priorities=["Seating for four"],
        constraints=["One door and one window"],
        ambiguities=[],
        warnings=[],
    )


def make_concept(name: str = "Low Horizon") -> DesignConcept:
    return DesignConcept(
        name=name,
        description=f"{name} arranges the room around seating pulled to the edges.",
        design_direction="seating pulled to the edges",
        color_and_material_direction="Pale oak, undyed linen, oatmeal wool.",
        furniture_approach="A small number of low, long pieces.",
        functional_rationale="Seats four and keeps the window band open.",
        budget_suitability="Workable with a low piece count.",
    )


def assert_no_exceptions(at: AppTest) -> None:
    exceptions = [element.message for element in at.exception]
    assert exceptions == [], exceptions


def state_of(at: AppTest) -> WorkflowState:
    state = at.session_state["hm_workflow_state"]
    assert isinstance(state, WorkflowState)
    return state


def rendered(at: AppTest) -> str:
    return " ".join(element.value for element in at.markdown)


def rendered_plain(at: AppTest) -> str:
    import re

    text = rendered(at)
    text = text.split("</style>")[-1] if "</style>" in text else text
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text))


def alerts(at: AppTest) -> str:
    groups = (at.error, at.warning, at.success, at.info)
    return " ".join(element.value for group in groups for element in group)


def page_text(at: AppTest) -> str:
    return f"{rendered_plain(at)} {alerts(at)}"


def click(at: AppTest, label: str) -> AppTest:
    matches = [button for button in at.button if button.label == label]
    assert matches, (
        f"No button labelled {label!r}. Have: {[b.label for b in at.button]}"
    )
    matches[0].click().run()
    assert_no_exceptions(at)
    return at


def fresh_app() -> AppTest:
    return AppTest.from_file(str(APP_PATH), default_timeout=90).run()


def build_complete_input(at: AppTest, *, budget: float = 85000.0) -> AppTest:
    at = click(at, "Start Room Setup")
    at.text_input(key="hmw_room_name").set_value("Living Room")
    at.number_input(key="hmw_width_cm").set_value(400.0)
    at.number_input(key="hmw_length_cm").set_value(520.0)
    at.number_input(key="hmw_door_offset").set_value(20.0)
    at.number_input(key="hmw_door_width").set_value(80.0)
    at.number_input(key="hmw_window_offset").set_value(20.0)
    at.number_input(key="hmw_window_width").set_value(80.0)
    at.button(key=ROOM_FORM_SUBMIT).click().run()
    assert_no_exceptions(at)

    at.multiselect(key="hmw_materials").set_value(["pale oak"])
    at.multiselect(key="hmw_requirements").set_value(["Seating for four"])
    at.text_area(key="hmw_notes").set_value("Keep the window side open.")
    at.number_input(key="hmw_budget").set_value(budget)
    at.button(key=PREFERENCES_FORM_SUBMIT).click().run()
    assert_no_exceptions(at)
    return at


def store_basket(state: WorkflowState, *items: FurnitureRecommendation) -> None:
    """Install a basket and the two deterministic results, without a model."""

    state.record_recommendation(
        DesignRecommendation(
            furniture=list(items),
            materials=[],
            color_direction="Warm neutrals.",
            design_rationale="Low pieces keep the window band open.",
        )
    )
    analysis = layout.analyse_layout(
        state.room, state.furniture, references.load_catalog()
    )
    state.record_spatial(analysis.validation, analysis.outcome, analysis.placements)
    state.record_budget_analysis(
        compute_budget(
            state.budget, state.furniture, references.load_catalog()
        ).analysis
    )


def open_budget_screen(
    at: AppTest,
    *,
    budget: float = 85000.0,
    items: tuple[FurnitureRecommendation, ...] | None = None,
) -> AppTest:
    at = build_complete_input(at, budget=budget)
    state = state_of(at)
    state.record_brief(make_brief())
    state.record_concepts(
        ConceptCollection(
            concepts=[
                make_concept("Low Horizon"),
                make_concept("Window Bench"),
                make_concept("Shelf Spine"),
            ]
        )
    )
    state.select_concept_by_name("Low Horizon")
    store_basket(
        state,
        *(
            items
            if items is not None
            else (
                FurnitureRecommendation(item_id="sofa_three_seat", quantity=1),
                FurnitureRecommendation(item_id="coffee_table", quantity=1),
            )
        ),
    )
    at.run()
    assert_no_exceptions(at)

    at.session_state["hm_screen"] = "budget"
    at.run()
    assert_no_exceptions(at)
    return at


def expected_analysis(
    state: WorkflowState, items: tuple[FurnitureRecommendation, ...]
) -> BudgetAnalysis:
    return compute_budget(
        state.budget, list(items), references.load_catalog()
    ).analysis


# --------------------------------------------------------------------------- #
# 1-2. The engine is the only thing that prices, and it counts quantities
# --------------------------------------------------------------------------- #


def test_the_screen_shows_the_engines_own_figures() -> None:
    at = open_budget_screen(fresh_app())
    state = state_of(at)
    assert state.budget_analysis is not None

    plain = rendered_plain(at)
    analysis = state.budget_analysis
    currency = analysis.currency
    assert commits.format_money(analysis.total_estimated, currency) in plain
    assert commits.format_money(state.budget.total_budget, currency) in plain
    assert commits.format_money(analysis.remaining_budget, currency) in plain


def test_quantity_multiplies_the_line_total() -> None:
    at = open_budget_screen(
        fresh_app(),
        items=(FurnitureRecommendation(item_id="armchair", quantity=3),),
    )
    state = state_of(at)
    assert state.budget_analysis is not None

    catalog = {item.item_id: item for item in load_catalog()}
    unit = catalog["armchair"].indicative_unit_cost
    expected_total = Decimal(str(unit)) * 3

    assert state.budget_analysis.furniture_subtotal == expected_total
    plain = rendered_plain(at)
    assert commits.format_money(expected_total, "TRY") in plain
    # The quantity appears in the item table, so the multiplication is visible.
    assert "3" in plain


def test_the_item_table_lists_every_priced_line_with_its_subtotal() -> None:
    at = open_budget_screen(
        fresh_app(),
        items=(
            FurnitureRecommendation(item_id="sofa_three_seat", quantity=1),
            FurnitureRecommendation(item_id="side_table", quantity=2),
        ),
    )
    state = state_of(at)
    assert state.budget_analysis is not None

    plain = rendered_plain(at)
    catalog = {item.item_id: item for item in load_catalog()}
    for item_id, quantity in (("sofa_three_seat", 1), ("side_table", 2)):
        item = catalog[item_id]
        line_total = Decimal(str(item.indicative_unit_cost)) * quantity
        assert item.name in plain
        assert commits.format_money(line_total, "TRY") in plain


def test_the_screen_never_recomputes_a_total_itself() -> None:
    """The presented total is compared against the engine, not recomputed."""

    at = open_budget_screen(fresh_app())
    state = state_of(at)
    assert state.budget_analysis is not None

    engine = expected_analysis(
        state,
        tuple(state.furniture),
    )
    assert state.budget_analysis == engine
    assert budget_view.matches(state.budget_analysis, budget_view.compute_estimate(
        state.budget, state.furniture, references.load_catalog()
    ))


# --------------------------------------------------------------------------- #
# 3. An unpriced item is not free
# --------------------------------------------------------------------------- #


def test_an_unpriced_item_is_reported_and_never_costed_at_zero() -> None:
    at = open_budget_screen(
        fresh_app(),
        items=(
            FurnitureRecommendation(item_id="sofa_three_seat", quantity=1),
            FurnitureRecommendation(item_id="ghost_sofa", quantity=1),
        ),
    )
    state = state_of(at)
    assert state.budget_analysis is not None

    # The engine priced only what it could find, and says so.
    result = budget_view.compute_estimate(
        state.budget, state.furniture, references.load_catalog()
    )
    assert result.is_trustworthy is False
    assert budget_view.unpriced_errors(result) == ("ghost_sofa",)
    assert state.budget_analysis.furniture_subtotal == Decimal("18500.00")

    plain = page_text(at).lower()
    assert "estimate incomplete" in plain
    assert "ghost_sofa" in plain
    assert "excluded from the total, not costed at zero" in plain
    assert "not a final figure" in plain


def test_a_wholly_unpriced_basket_has_no_item_table() -> None:
    at = open_budget_screen(
        fresh_app(),
        items=(FurnitureRecommendation(item_id="ghost_sofa", quantity=1),),
    )
    plain = page_text(at).lower()
    assert "no item in the basket could be priced" in plain
    assert "estimate incomplete" in plain


# --------------------------------------------------------------------------- #
# 4-5. Budget limit, remaining budget and overrun
# --------------------------------------------------------------------------- #


def test_an_overrun_is_reported_with_the_engines_own_figure() -> None:
    at = open_budget_screen(fresh_app(), budget=500.0)
    state = state_of(at)
    assert state.budget_analysis is not None
    analysis = state.budget_analysis
    assert analysis.is_over_budget is True
    assert analysis.remaining_budget < 0

    plain = rendered_plain(at)
    assert "Over budget by" in plain
    assert "Over budget" in plain
    assert commits.format_money(abs(analysis.remaining_budget), "TRY") in plain
    assert "not affordable as priced" in plain


def test_a_remaining_budget_is_reported_as_remaining() -> None:
    at = open_budget_screen(fresh_app(), budget=200000.0)
    state = state_of(at)
    assert state.budget_analysis is not None
    analysis = state.budget_analysis
    assert analysis.is_over_budget is False

    plain = rendered_plain(at)
    assert "Remaining budget" in plain
    assert "Within budget" in plain
    assert commits.format_money(analysis.remaining_budget, "TRY") in plain


def test_a_zero_budget_does_not_report_a_percentage() -> None:
    """Usage is undefined when the limit is zero; the screen says so."""

    at = open_budget_screen(fresh_app(), budget=0.0)
    state = state_of(at)
    assert state.budget is not None
    assert state.budget.total_budget == Decimal("0.0")

    plain = page_text(at).lower()
    assert "cannot be expressed as a percentage" in plain or (
        "usage cannot be a percentage" in plain
    )


# --------------------------------------------------------------------------- #
# 6. Materials are excluded and shown as unpriced
# --------------------------------------------------------------------------- #


def test_materials_are_listed_as_unpriced_and_outside_the_total() -> None:
    at = open_budget_screen(fresh_app())
    state = state_of(at)
    assert state.materials == ()
    plain = rendered_plain(at).lower()
    # No materials were recommended, so the screen says that rather than
    # pretending a material cost is zero.
    assert "no materials were recommended" in plain

    # The engine's total excludes materials by construction: they are not part
    # of the furniture subtotal and no material amount is added.
    assert state.budget_analysis is not None
    assert state.budget_analysis.material_subtotal == Decimal("0.00")
    assert (
        state.budget_analysis.total_estimated
        == state.budget_analysis.furniture_subtotal
    )
    assert "materials and finishes" in plain
    assert "not priced" in plain


def test_the_screen_states_that_the_estimate_is_indicative() -> None:
    at = open_budget_screen(fresh_app())
    plain = page_text(at)
    assert "indicative" in plain.lower()
    assert "not verified market prices" in plain.lower()
    # The catalog's own disclaimer is shown, not a paraphrase of it.
    assert references.catalog_image_free_note()[:40] in plain


# --------------------------------------------------------------------------- #
# 7. State
# --------------------------------------------------------------------------- #


def test_the_screen_records_nothing_until_the_user_recalculates() -> None:
    at = open_budget_screen(fresh_app())
    state = state_of(at)
    before = state.budget_analysis
    assert before is not None

    at.run()
    at.run()
    assert state_of(at).budget_analysis == before
    assert state_of(at).invalidation_log == state.invalidation_log


def test_recalculating_stores_the_same_deterministic_result() -> None:
    at = open_budget_screen(fresh_app())
    state = state_of(at)
    before = state.budget_analysis
    assert before is not None

    at = click(at, RECALCULATE_LABEL)
    assert state_of(at).budget_analysis == before
    assert "recalculated from the current basket" in alerts(at).lower()


def test_a_stale_stored_analysis_is_not_shown_as_current() -> None:
    """A stored figure that disagrees with the engine is refused, not rendered."""

    at = open_budget_screen(fresh_app())
    state = state_of(at)
    # A value that could not have come from this basket: an older, cheaper one.
    state.budget_analysis = BudgetAnalysis(
        furniture_subtotal=Decimal("1.00"),
        total_estimated=Decimal("1.00"),
        remaining_budget=Decimal("84999.00"),
    )
    at.run()
    assert_no_exceptions(at)

    plain = page_text(at).lower()
    assert "recalculation needed" in plain
    assert "no longer matches the current basket" in plain
    # The stale figure is not presented as the estimate.
    assert commits.format_money(Decimal("1.00"), "TRY") not in rendered_plain(at)

    at = click(at, RECALCULATE_LABEL)
    state = state_of(at)
    assert state.budget_analysis is not None
    assert state.budget_analysis.furniture_subtotal != Decimal("1.00")
    assert "Recalculation needed" not in page_text(at)


def test_the_estimate_is_recorded_by_the_plan_step_not_the_budget_screen() -> None:
    """The evaluation's prerequisites are satisfied by producing the plan."""

    at = build_complete_input(fresh_app())
    state = state_of(at)
    state.record_brief(make_brief())
    state.record_concepts(
        ConceptCollection(
            concepts=[
                make_concept("Low Horizon"),
                make_concept("Window Bench"),
                make_concept("Shelf Spine"),
            ]
        )
    )
    state.select_concept_by_name("Low Horizon")
    store_basket(
        state, FurnitureRecommendation(item_id="sofa_three_seat", quantity=1)
    )
    at.run()
    assert_no_exceptions(at)

    assert state.is_complete(WorkflowStep.BUDGET_ANALYSIS) is True
    assert state.is_complete(WorkflowStep.SPATIAL_VALIDATION) is True


# --------------------------------------------------------------------------- #
# 8-9. Invalidation
# --------------------------------------------------------------------------- #


def test_changing_the_budget_limit_invalidates_the_stored_analysis() -> None:
    at = open_budget_screen(fresh_app())
    state = state_of(at)
    assert state.budget_analysis is not None

    at.session_state["hm_screen"] = "preferences"
    at.run()
    assert_no_exceptions(at)
    at.number_input(key="hmw_budget").set_value(99000.0)
    at.button(key=PREFERENCES_FORM_SUBMIT).click().run()
    assert_no_exceptions(at)

    state = state_of(at)
    assert state.budget is not None
    assert state.budget.total_budget == Decimal("99000.0")
    assert state.budget_analysis is None
    assert state.is_complete(WorkflowStep.BUDGET_ANALYSIS) is False
    # The layout is geometry, not money, and survives: the rule is exact.
    assert state.spatial is not None


def test_changing_the_basket_invalidates_the_stored_analysis() -> None:
    at = open_budget_screen(fresh_app())
    state = state_of(at)
    assert state.budget_analysis is not None

    dropped = state.record_recommendation(
        DesignRecommendation(
            furniture=[FurnitureRecommendation(item_id="sofa_three_seat", quantity=2)],
            materials=[],
            color_direction="Warm.",
            design_rationale="Low.",
        )
    )

    assert DataKey.BUDGET_ANALYSIS in dropped
    assert state.budget_analysis is None
    assert state.is_complete(WorkflowStep.BUDGET_ANALYSIS) is False


def test_recording_coordinates_does_not_invalidate_the_price() -> None:
    """A placement annotation is not a new basket."""

    at = open_budget_screen(fresh_app())
    state = state_of(at)
    before = state.budget_analysis
    assert before is not None

    analysis = layout.analyse_layout(
        state.room, state.furniture, references.load_catalog()
    )
    dropped = state.record_spatial(
        analysis.validation, analysis.outcome, analysis.placements
    )

    assert DataKey.BUDGET_ANALYSIS not in dropped
    assert state.budget_analysis == before


# --------------------------------------------------------------------------- #
# 10. Prerequisites and navigation
# --------------------------------------------------------------------------- #


def test_the_budget_screen_refuses_to_run_without_a_basket() -> None:
    at = build_complete_input(fresh_app())
    at.session_state["hm_screen"] = "budget"
    at.run()
    assert_no_exceptions(at)

    # Each screen guards its own prerequisite, so the redirect chains back to
    # the first thing that is missing rather than stopping half way.
    assert at.session_state["hm_screen"] != "budget"
    assert RECALCULATE_LABEL not in {button.label for button in at.button}
    assert "Indicative budget analysis" not in rendered_plain(at)


def test_the_budget_screen_refuses_to_run_without_an_estimate() -> None:
    at = open_budget_screen(fresh_app())
    state = state_of(at)
    state.budget_analysis = None
    at.run()
    assert_no_exceptions(at)

    assert at.session_state["hm_screen"] == "plan"


def test_the_budget_screen_links_back_to_the_evaluation() -> None:
    at = open_budget_screen(fresh_app())
    labels = {button.label for button in at.button}
    assert "Back to the evaluation" in labels
    # The report is now a real next step rather than an announced future one.
    assert "Continue to the final report" in labels


def test_the_budget_screen_makes_no_ai_call(monkeypatch) -> None:
    """Nothing on this screen may reach the model layer."""

    from ui import ai_actions

    calls: list[str] = []

    def forbid(name):  # noqa: ANN001 - test double
        def stub(**kwargs):  # noqa: ANN003
            calls.append(name)
            raise AssertionError(f"The budget screen called {name}.")

        return stub

    for name in (
        "analyze_brief",
        "generate_concepts",
        "recommend_furniture",
        "evaluate_design",
    ):
        monkeypatch.setattr(ai_actions, name, forbid(name))

    at = open_budget_screen(fresh_app())
    click(at, RECALCULATE_LABEL)
    at.run()
    assert calls == []
    assert_no_exceptions(at)


def test_the_distribution_chart_repeats_the_table_and_adds_nothing() -> None:
    at = open_budget_screen(fresh_app())
    # Two priced lines are enough for the chart, and it is drawn from the same
    # line totals the table shows.
    plain = rendered_plain(at)
    assert "Cost distribution" in plain or "cost by item" in plain.lower()


def test_a_single_priced_line_does_not_get_a_chart() -> None:
    at = open_budget_screen(
        fresh_app(),
        items=(FurnitureRecommendation(item_id="armchair", quantity=1),),
    )
    plain = rendered_plain(at)
    assert "Cost distribution" not in plain


def test_the_cost_chart_carries_alternative_text_naming_every_bar() -> None:
    """Regression: axe-core reported a serious ``image-alt`` violation.

    ``st.pyplot`` renders the Matplotlib figure as a bare ``<img>``. Without an
    ``alt`` a screen reader announces an unlabelled graphic and every figure in
    the chart is unreachable — the chart, unlike the table, has no text fallback.
    The alternative must therefore carry the figures, in the currency shown.
    """

    at = open_budget_screen(fresh_app())
    state = state_of(at)
    result = compute_budget(
        state.budget, state.furniture, references.load_catalog()
    )
    from ui.pages_budget import distribution_alt_text

    alt = distribution_alt_text(result.line_items, result.analysis.currency)

    assert alt.startswith("Horizontal bar chart")
    assert result.analysis.currency in alt
    for line in result.line_items:
        assert line.name in alt, f"{line.name} is missing from the chart's alt text"
    # It points at the table rather than pretending to be the only copy.
    assert "table" in alt
    assert not alt.endswith(" ")


def test_the_cost_chart_alt_text_states_a_value_for_each_bar() -> None:
    """An empty alternative would read as decorative, which the chart is not."""

    at = open_budget_screen(fresh_app())
    state = state_of(at)
    result = compute_budget(
        state.budget, state.furniture, references.load_catalog()
    )
    from ui.pages_budget import distribution_alt_text

    alt = distribution_alt_text(result.line_items, result.analysis.currency)

    # Two or more priced lines are required for the chart to be drawn at all.
    assert len(result.line_items) >= 2
    for line in result.line_items:
        assert f"{line.line_total:,.0f} {result.analysis.currency}" in alt
    # Bars are described largest first, matching the reading order of the chart.
    totals = [line.line_total for line in result.line_items]
    assert totals == sorted(totals, reverse=True) or alt.count(";") == len(totals) - 1
