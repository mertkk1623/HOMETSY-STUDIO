"""The Design Evaluation screen: AI operation 4 under the user's control.

Every test is mock-only. ``ui.ai_actions.evaluate_design`` is replaced by a stub,
so no HTTP request is made and the suite needs no API key. The spatial engine,
the placement engine and the budget engine are the real ones: they are the
deterministic half this screen must not contradict, and stubbing them would test
nothing.

The scenarios mirror §7.1 of the step brief:

1. the evaluator is called with the current, stored inputs;
2. no button and no call while a prerequisite is missing;
3. a FAILED layout is never presented as spatially applicable;
4. a PARTIAL layout is stated as partial;
5. spatial errors and warnings stay separate;
6. an over-budget result is reported as a real risk;
7. an incomplete estimate is reported as an incomplete estimate;
8. a failed call keeps the previous valid evaluation;
9. a rerun makes no request;
10. no request happens without a button press.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from streamlit.testing.v1 import AppTest

from ai.client import AITimeoutError
from core.budget_engine import compute_budget
from models.schemas import (
    BudgetInput,
    ConceptCollection,
    DesignBrief,
    DesignConcept,
    DesignEvaluation,
    DesignRecommendation,
    FurnitureRecommendation,
    SpatialValidation,
)
from ui import ai_actions, layout, references
from ui.references import load_catalog
from workflow.state import WorkflowState, WorkflowStep

PROJECT_ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "app.py"

ROOM_FORM_SUBMIT = "FormSubmitter:hm_room_form-Save room information"
PREFERENCES_FORM_SUBMIT = (
    "FormSubmitter:hm_preferences_form-Save preferences and budget"
)

EVALUATE_LABEL = "Evaluate the design"
EVALUATE_AGAIN_LABEL = "Evaluate the design again"
ADVISOR_LABEL = "Recommend furniture and build the plan"


# --------------------------------------------------------------------------- #
# Fake evaluator
# --------------------------------------------------------------------------- #


def make_evaluation(**overrides: object) -> DesignEvaluation:
    payload: dict[str, object] = {
        "requirement_compatibility": "Seating for four is met by one three-seat sofa.",
        "style_consistency": "Low pale-oak pieces hold the Japandi direction.",
        "functional_suitability": "Circulation along the window wall stays clear.",
        "budget_suitability": "The indicative total sits inside the stated budget.",
        "limitations": ["No dedicated reading light is specified."],
        "recommendations": ["Add a floor lamp beside the sofa."],
    }
    payload.update(overrides)
    return DesignEvaluation(**payload)  # type: ignore[arg-type]


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


def make_advice(*furniture: FurnitureRecommendation):
    from ai.design_advisor import AdvisorResult, CatalogCheck
    from models.schemas import DesignRecommendation as Recommendation

    recommendation = Recommendation(
        furniture=list(furniture),
        materials=[],
        color_direction="Warm neutrals.",
        design_rationale="Low pieces keep the window band open.",
    )
    return AdvisorResult(
        recommendation=recommendation,
        catalog_check=CatalogCheck(findings=()),
        budget=compute_budget(
            BudgetInput(total_budget=Decimal("85000.00")),
            list(furniture),
            load_catalog(),
        ),
    )


class FakeEvaluator:
    """Records every evaluator call and replays a queued answer or exception."""

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self._answer: DesignEvaluation | BaseException = make_evaluation()

    def returns(self, value: DesignEvaluation | BaseException) -> FakeEvaluator:
        self._answer = value
        return self

    def evaluate_design(self, **kwargs) -> DesignEvaluation:
        self.calls.append(kwargs)
        if isinstance(self._answer, BaseException):
            raise self._answer
        return self._answer

    @property
    def call_count(self) -> int:
        return len(self.calls)


@pytest.fixture
def evaluator(monkeypatch) -> FakeEvaluator:
    fake = FakeEvaluator()
    monkeypatch.setattr(ai_actions, "evaluate_design", fake.evaluate_design)
    return fake


# --------------------------------------------------------------------------- #
# Harness
# --------------------------------------------------------------------------- #


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


def build_complete_input(
    at: AppTest,
    *,
    budget: float = 85000.0,
    width: float = 400.0,
    length: float = 520.0,
) -> AppTest:
    at = click(at, "Start Room Setup")
    at.text_input(key="hmw_room_name").set_value("Living Room")
    at.number_input(key="hmw_width_cm").set_value(width)
    at.number_input(key="hmw_length_cm").set_value(length)
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


def prime_through_plan(
    at: AppTest,
    *,
    furniture: tuple[FurnitureRecommendation, ...] | None = None,
    budget: float = 85000.0,
    room: tuple[float, float] = (400.0, 520.0),
) -> AppTest:
    """Complete the input, the AI stages and the deterministic plan results."""

    at = build_complete_input(at, budget=budget, width=room[0], length=room[1])
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
    state.record_recommendation(
        make_advice(
            *(
                furniture
                or (
                    FurnitureRecommendation(item_id="sofa_three_seat", quantity=1),
                    FurnitureRecommendation(item_id="coffee_table", quantity=1),
                )
            )
        ).recommendation
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
    at.run()
    assert_no_exceptions(at)
    return at


def open_evaluation_screen(at: AppTest, **kwargs) -> AppTest:
    prime_through_plan(at, **kwargs)
    at.session_state["hm_screen"] = "evaluation"
    at.run()
    assert_no_exceptions(at)
    return at


# --------------------------------------------------------------------------- #
# 1. Button only, and only with the prerequisites
# --------------------------------------------------------------------------- #


def test_opening_the_evaluation_screen_makes_no_request(
    evaluator: FakeEvaluator,
) -> None:
    at = open_evaluation_screen(fresh_app())
    assert evaluator.call_count == 0
    assert "This design has not been evaluated yet." in rendered_plain(at)
    assert EVALUATE_LABEL in {button.label for button in at.button}


def test_a_rerun_after_an_evaluation_does_not_call_the_model_again(
    evaluator: FakeEvaluator,
) -> None:
    at = open_evaluation_screen(fresh_app())
    at = click(at, EVALUATE_LABEL)
    assert evaluator.call_count == 1

    at.run()
    at.run()
    assert evaluator.call_count == 1
    assert state_of(at).evaluation is not None


def test_the_screen_refuses_to_run_without_a_layout(evaluator: FakeEvaluator) -> None:
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
    state.record_recommendation(
        DesignRecommendation(
            furniture=[FurnitureRecommendation(item_id="sofa_three_seat")],
            materials=[],
            color_direction="Warm.",
            design_rationale="Low.",
        )
    )
    at.run()

    at.session_state["hm_screen"] = "evaluation"
    at.run()
    assert_no_exceptions(at)

    # Sent back to the plan, and offered no way to evaluate unmeasured data.
    assert at.session_state["hm_screen"] == "plan"
    assert EVALUATE_LABEL not in {button.label for button in at.button}
    assert evaluator.call_count == 0


def test_the_screen_refuses_to_run_without_a_budget_result(
    evaluator: FakeEvaluator,
) -> None:
    """A layout alone is not enough: the evaluator's contract needs a price."""

    at = prime_through_plan(fresh_app())
    state = state_of(at)
    # Drop the stored estimate the way an older project would: the layout
    # survives, the price does not.
    state.budget_analysis = None
    at.run()
    assert state.is_complete(WorkflowStep.BUDGET_ANALYSIS) is False

    at.session_state["hm_screen"] = "evaluation"
    at.run()
    assert_no_exceptions(at)

    assert at.session_state["hm_screen"] == "plan"
    assert EVALUATE_LABEL not in {button.label for button in at.button}
    assert evaluator.call_count == 0


def test_a_started_project_cannot_reach_the_evaluation_early(
    evaluator: FakeEvaluator,
) -> None:
    at = fresh_app()
    at = click(at, "Start Room Setup")
    at.session_state["hm_screen"] = "evaluation"
    at.run()
    assert_no_exceptions(at)
    assert at.session_state["hm_screen"] == "room"
    assert evaluator.call_count == 0


# --------------------------------------------------------------------------- #
# 2. The evaluator receives the current stored data
# --------------------------------------------------------------------------- #


def test_the_evaluator_receives_the_stored_data_and_no_calculated_figure(
    evaluator: FakeEvaluator,
) -> None:
    at = open_evaluation_screen(fresh_app())
    click(at, EVALUATE_LABEL)

    call = evaluator.calls[0]
    state = state_of(at)
    assert call["room"] == state.room
    assert call["preferences"] == state.preferences
    assert call["budget"] == state.budget
    assert call["brief"] == state.brief
    assert call["concept"] == state.selected_concept
    assert list(call["recommendations"]) == list(state.furniture)
    assert call["spatial"] == state.spatial
    assert call["analysis"] == state.budget_analysis
    # A complete basket is announced as complete, so the model does not have to
    # guess whether the total is final.
    assert call["budget_is_complete"] is True


def test_the_stored_layout_outcome_is_sent_to_the_evaluator(
    evaluator: FakeEvaluator,
) -> None:
    """The evaluator needs the placement verdict, not only the geometry verdict.

    A live run was told the geometry was valid and nothing else, and called a
    one-of-three layout "buildable as calculated".
    """

    at = open_evaluation_screen(fresh_app())
    click(at, EVALUATE_LABEL)

    call = evaluator.calls[0]
    state = state_of(at)
    assert call["placement"] == state.placement
    assert call["placement"] is not None


def test_an_incomplete_estimate_is_announced_as_incomplete(
    evaluator: FakeEvaluator,
) -> None:
    """An unpriced item must not arrive at the model as a final total."""

    at = prime_through_plan(
        fresh_app(),
        furniture=(FurnitureRecommendation(item_id="ghost_sofa", quantity=1),),
    )
    state = state_of(at)
    assert state.budget_analysis is not None
    # The stored analysis is what a project built from an unknown reference
    # would hold: the engine priced nothing, so the screen recomputes from the
    # same basket and finds the error.
    at.session_state["hm_screen"] = "evaluation"
    at.run()
    assert_no_exceptions(at)

    at = click(at, EVALUATE_LABEL)
    assert evaluator.call_count == 1
    assert evaluator.calls[0]["budget_is_complete"] is False


# --------------------------------------------------------------------------- #
# 3-5. The deterministic verdict is never improved by the answer
# --------------------------------------------------------------------------- #


def test_a_failed_layout_is_never_presented_as_spatially_applicable(
    evaluator: FakeEvaluator,
) -> None:
    # A basket that cannot fit: three large sofas in a 150 cm room.
    at = prime_through_plan(
        fresh_app(),
        room=(150.0, 150.0),
        furniture=(
            FurnitureRecommendation(item_id="sofa_three_seat", quantity=3),
        ),
    )
    state = state_of(at)
    assert state.placement is not None
    assert state.placement.is_failed
    assert state.spatial is not None and state.spatial.is_valid is False

    at.session_state["hm_screen"] = "evaluation"
    at.run()
    assert_no_exceptions(at)

    plain = page_text(at).lower()
    assert "layout failed" in plain
    assert "cannot be presented as spatially applicable" in plain
    # No score and no drawing of a rejected candidate.
    assert "<svg" not in rendered(at)

    # Even if the model answers as if the design were fine, the engine's verdict
    # is on the screen beside it.
    evaluator.returns(
        make_evaluation(
            functional_suitability="The layout is fully applicable as designed."
        )
    )
    at = click(at, EVALUATE_LABEL)
    plain = page_text(at).lower()
    assert "layout failed" in plain
    assert "not valid" in plain


def test_a_partial_layout_is_stated_as_partial(evaluator: FakeEvaluator) -> None:
    # Two sofas requested, one placeable: the engine reports PARTIAL.
    at = prime_through_plan(
        fresh_app(),
        room=(220.0, 200.0),
        furniture=(
            FurnitureRecommendation(item_id="sofa_three_seat", quantity=2),
        ),
    )
    state = state_of(at)
    assert state.placement is not None
    assert state.placement.is_partial

    at.session_state["hm_screen"] = "evaluation"
    at.run()
    assert_no_exceptions(at)
    plain = page_text(at).lower()
    assert "partial layout" in plain
    assert "only partly buildable" in plain
    assert "1 of 2 requested items were placed" in plain


def test_blocking_problems_and_warnings_stay_separate(
    evaluator: FakeEvaluator,
) -> None:
    at = open_evaluation_screen(fresh_app())
    state = state_of(at)
    paired = SpatialValidation(
        is_valid=False,
        boundary_violations=["The sofa crosses the east wall."],
        overlaps=[],
        warnings=["The armchair stands in the window clearance band."],
    )
    state.record_spatial(paired, state.placement, state.furniture)
    at.run()
    assert_no_exceptions(at)

    plain = rendered(at)
    # Both lists are rendered, each under its own heading, with its own label.
    assert "Blocking problems" in plain
    assert "Warnings" in plain
    assert "The sofa crosses the east wall." in plain
    assert "The armchair stands in the window clearance band." in plain
    assert plain.count("hm-issue--error") >= 1
    assert plain.count("hm-issue--warning") >= 1
    # A warning is explicitly not an error.
    assert "a warning is not a blocking problem" in page_text(at).lower()


# --------------------------------------------------------------------------- #
# 6-7. The budget position is reported, not recomputed
# --------------------------------------------------------------------------- #


def test_an_over_budget_design_is_reported_as_a_real_risk(
    evaluator: FakeEvaluator,
) -> None:
    at = open_evaluation_screen(fresh_app(), budget=500.0)
    state = state_of(at)
    assert state.budget_analysis is not None
    assert state.budget_analysis.is_over_budget is True

    plain = rendered(at)
    assert "Over budget by" in plain
    # The verdict is stated in words, and the figure is the engine's own.
    assert "is_over_budget" not in plain
    assert "Over budget" in plain


def test_the_evaluation_screen_never_calculates_a_price_itself(
    evaluator: FakeEvaluator,
) -> None:
    """Every figure on screen equals a field of the stored analysis."""

    from ui import commits

    at = open_evaluation_screen(fresh_app())
    state = state_of(at)
    assert state.budget_analysis is not None

    plain = rendered_plain(at)
    analysis = state.budget_analysis
    expected = commits.format_money(analysis.total_estimated, analysis.currency)
    assert expected in plain
    expected_budget = commits.format_money(
        state.budget.total_budget, state.budget.currency
    )
    assert expected_budget in plain


# --------------------------------------------------------------------------- #
# 8. A failure preserves the previous valid result
# --------------------------------------------------------------------------- #


def test_a_failed_call_keeps_the_previous_evaluation(
    evaluator: FakeEvaluator,
) -> None:
    at = open_evaluation_screen(fresh_app())
    at = click(at, EVALUATE_LABEL)
    first = state_of(at).evaluation
    assert first is not None

    evaluator.returns(AITimeoutError("the request timed out"))
    at = click(at, EVALUATE_AGAIN_LABEL)

    state = state_of(at)
    assert state.evaluation == first
    assert state.is_complete(WorkflowStep.DESIGN_EVALUATION) is True
    assert "did not answer in time" in alerts(at).lower()
    assert "nothing was saved" in alerts(at).lower()
    # The earlier evaluation is still readable.
    assert "How well the brief is met" in rendered_plain(at)


def test_a_failed_first_call_stores_nothing(evaluator: FakeEvaluator) -> None:
    at = open_evaluation_screen(fresh_app())
    evaluator.returns(AITimeoutError("the request timed out"))
    at = click(at, EVALUATE_LABEL)

    state = state_of(at)
    assert state.evaluation is None
    assert state.is_complete(WorkflowStep.DESIGN_EVALUATION) is False
    assert "This design has not been evaluated yet." in rendered_plain(at)
    assert EVALUATE_LABEL in {button.label for button in at.button}


# --------------------------------------------------------------------------- #
# 9. The stored result is the schema's fields, and nothing else
# --------------------------------------------------------------------------- #


def test_every_schema_field_is_shown_and_no_other_is_invented(
    evaluator: FakeEvaluator,
) -> None:
    at = open_evaluation_screen(fresh_app())
    at = click(at, EVALUATE_LABEL)

    plain = rendered_plain(at)
    for label in (
        "How well the brief is met",
        "Style and concept consistency",
        "How the room will work in use",
        "Budget suitability",
        "Limitations and risks",
        "Improvement suggestions",
    ):
        assert label in plain

    evaluation = state_of(at).evaluation
    assert evaluation is not None
    for value in (
        evaluation.requirement_compatibility,
        evaluation.style_consistency,
        evaluation.functional_suitability,
        evaluation.budget_suitability,
        evaluation.limitations[0],
        evaluation.recommendations[0],
    ):
        assert value in plain

    # The schema has no score, no verdict and no strengths list, so none is
    # presented as a result of the evaluation.
    lower = plain.lower()
    assert "this is a design opinion, not an engineering approval" in lower
    assert "no single overall-verdict field" in lower


def test_an_edit_that_clears_the_plan_clears_the_evaluation_too(
    evaluator: FakeEvaluator,
) -> None:
    """A new basket drops the layout, the price and the critique together."""

    at = open_evaluation_screen(fresh_app())
    at = click(at, EVALUATE_LABEL)
    state = state_of(at)
    assert state.evaluation is not None

    state.record_recommendation(
        make_advice(
            FurnitureRecommendation(item_id="sofa_three_seat", quantity=2)
        ).recommendation
    )
    at.run()
    assert_no_exceptions(at)

    state = state_of(at)
    assert state.evaluation is None
    assert state.placement is None
    assert state.budget_analysis is None
    # With nothing left to evaluate the screen no longer offers the button, and
    # sends the user back rather than showing a critique of a stale basket.
    assert at.session_state["hm_screen"] == "plan"
    assert EVALUATE_LABEL not in {button.label for button in at.button}
    assert "How well the brief is met" not in rendered_plain(at)


def test_a_retained_evaluation_without_its_prerequisites_is_not_shown(
    evaluator: FakeEvaluator,
) -> None:
    """The freshness rule, observed on this screen.

    ``WorkflowState`` can hold a value whose prerequisite has gone. The screen
    must not present that as a current evaluation, which is why it asks
    ``is_complete`` instead of testing ``evaluation is not None``.
    """

    at = open_evaluation_screen(fresh_app())
    at = click(at, EVALUATE_LABEL)
    state = state_of(at)
    assert state.evaluation is not None
    # Deliberately leave the evaluation behind while removing the price it was
    # written from: an older project, or a reloaded one.
    state.budget_analysis = None
    assert state.is_complete(WorkflowStep.DESIGN_EVALUATION) is False

    at.run()
    assert_no_exceptions(at)

    # The screen refuses to evaluate without the price and shows nothing stale.
    assert at.session_state["hm_screen"] == "plan"
    assert "How well the brief is met" not in rendered_plain(at)


# --------------------------------------------------------------------------- #
# 10. Navigation
# --------------------------------------------------------------------------- #


def test_the_evaluation_screen_offers_the_budget_step(evaluator: FakeEvaluator) -> None:
    at = open_evaluation_screen(fresh_app())
    labels = {button.label for button in at.button}
    assert "Continue to budget analysis" in labels
    assert "Back to the plan" in labels


def test_the_plan_screen_reaches_the_evaluation_once_it_can(
    evaluator: FakeEvaluator,
) -> None:
    at = prime_through_plan(fresh_app())
    at.session_state["hm_screen"] = "plan"
    at.run()
    assert_no_exceptions(at)

    labels = {button.label for button in at.button}
    assert "Continue to the design evaluation" in labels
    at = click(at, "Continue to the design evaluation")
    assert at.session_state["hm_screen"] == "evaluation"
    assert evaluator.call_count == 0


def test_the_plan_screen_makes_no_evaluation_request(evaluator: FakeEvaluator) -> None:
    at = prime_through_plan(fresh_app())
    at.session_state["hm_screen"] = "plan"
    at.run()
    assert evaluator.call_count == 0


# --------------------------------------------------------------------------- #
# 11. Invalidation and the finalised result
# --------------------------------------------------------------------------- #


def test_a_new_brief_clears_the_evaluation(evaluator: FakeEvaluator) -> None:
    at = open_evaluation_screen(fresh_app())
    at = click(at, EVALUATE_LABEL)
    state = state_of(at)
    assert state.evaluation is not None

    dropped = state.record_brief(
        DesignBrief(
            summary="A different brief entirely.",
            functional_priorities=["A single reading chair"],
            constraints=[],
            ambiguities=[],
            warnings=[],
        )
    )

    from workflow.dependencies import DataKey

    assert DataKey.EVALUATION in dropped
    assert state.evaluation is None


def test_a_new_selection_clears_the_evaluation(evaluator: FakeEvaluator) -> None:
    at = open_evaluation_screen(fresh_app())
    at = click(at, EVALUATE_LABEL)
    state = state_of(at)
    assert state.evaluation is not None

    dropped = state.select_concept_by_name("Window Bench")

    from workflow.dependencies import DataKey

    assert DataKey.EVALUATION in dropped
    assert state.evaluation is None


def test_a_new_spatial_verdict_clears_only_the_evaluation(
    evaluator: FakeEvaluator,
) -> None:
    at = open_evaluation_screen(fresh_app())
    at = click(at, EVALUATE_LABEL)
    state = state_of(at)
    assert state.evaluation is not None
    price = state.budget_analysis
    assert state.placement is not None

    paired = SpatialValidation(
        is_valid=True,
        boundary_violations=[],
        overlaps=[],
        warnings=["The sofa stands in the window clearance band."],
    )
    dropped = state.record_spatial(paired, state.placement, state.furniture)

    from workflow.dependencies import DataKey

    assert DataKey.EVALUATION in dropped
    # Geometry is not money: the price and the basket survive.
    assert DataKey.BUDGET_ANALYSIS not in dropped
    assert state.budget_analysis == price
    assert state.evaluation is None


def test_a_recomputed_budget_clears_the_evaluation(evaluator: FakeEvaluator) -> None:
    at = open_evaluation_screen(fresh_app())
    at = click(at, EVALUATE_LABEL)
    state = state_of(at)
    assert state.evaluation is not None

    analysis = state.budget_analysis
    assert analysis is not None
    recalculated = analysis.model_copy(
        update={"remaining_budget": analysis.remaining_budget - Decimal("1.00")}
    )
    dropped = state.record_budget_analysis(recalculated)

    from workflow.dependencies import DataKey

    assert DataKey.EVALUATION in dropped
    assert state.evaluation is None


def test_the_finalised_result_carries_the_new_results(
    evaluator: FakeEvaluator,
) -> None:
    """``finalize`` still assembles a complete ``ProjectResult``."""

    at = open_evaluation_screen(fresh_app())
    at = click(at, EVALUATE_LABEL)
    state = state_of(at)

    result = state.finalize()

    assert result.evaluation == state.evaluation
    assert result.budget_analysis == state.budget_analysis
    assert result.spatial_validation == state.spatial
    assert result.recommendations == list(state.furniture)
    assert state.is_complete(WorkflowStep.FINAL_RESULT) is True

