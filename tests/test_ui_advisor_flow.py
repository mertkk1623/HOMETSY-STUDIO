"""The Design Plan screen: advisor, placement, validation and the drawing.

Every test here is mock-only. ``ui.ai_actions.recommend_furniture`` is replaced
by a stub, so no HTTP request is made and the suite needs no API key. The
placement and spatial engines are the real ones: they are deterministic, they
are what this screen exists to show, and stubbing them would test nothing.

The scenarios mirror the fourteen requirements of the step brief:

1. the advisor runs only on a button press;
2. it never runs without a valid concept;
3. a failed call leaves the previous valid state intact;
4. catalog references are preserved, never rewritten;
5. the placement engine is integrated, not re-implemented;
6. COMPLETE / PARTIAL / FAILED are presented distinctly;
7. the plan uses the engine's real coordinates;
8. a FAILED candidate is never drawn;
9. a PARTIAL plan draws only the placed copies;
10. quantities survive the write-back;
11. spatial errors and warnings stay separate;
12. no material price is invented;
13. a rerun makes no request;
14. the AI-free start of the workflow still works.
"""

from __future__ import annotations

import re
from decimal import Decimal

import pytest
from streamlit.testing.v1 import AppTest

from ai.client import AITimeoutError
from ai.design_advisor import AdvisorResult, CatalogCheck
from core.budget_engine import compute_budget
from models.schemas import (
    DesignBrief,
    DesignConcept,
    DesignRecommendation,
    FurnitureRecommendation,
    MaterialRecommendation,
    PlacementStatus,
    RoomInput,
)
from ui import ai_actions, layout
from ui.references import load_catalog
from workflow.dependencies import DataKey
from workflow.state import WorkflowState, WorkflowStep

PROJECT_ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "app.py"

ROOM_FORM_SUBMIT = "FormSubmitter:hm_room_form-Save room information"
PREFERENCES_FORM_SUBMIT = (
    "FormSubmitter:hm_preferences_form-Save preferences and budget"
)

ADVISOR_LABEL = "Recommend furniture and build the plan"
REGENERATE_LABEL = "Run the advisor again"


# --------------------------------------------------------------------------- #
# Fake advisor
# --------------------------------------------------------------------------- #


def make_brief() -> DesignBrief:
    return DesignBrief(
        summary="A calm living room for four people.",
        functional_priorities=["Seating for four", "Reading corner"],
        constraints=["One door and one window"],
        ambiguities=["Whether existing furniture stays"],
        warnings=["The budget is tight for the stated scope"],
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


def make_materials(*names: str) -> list[MaterialRecommendation]:
    return [
        MaterialRecommendation(
            name=name,
            category="Flooring" if "floor" in name.casefold() else "Textile",
            color_direction="Warm pale oak.",
            rationale="Matches the palette.",
            quantity_note="Whole room",
        )
        for name in (names or ("Pale oak flooring",))
    ]


def make_advice(
    *furniture: FurnitureRecommendation,
    materials: list[MaterialRecommendation] | None = None,
    catalog_check: CatalogCheck | None = None,
) -> AdvisorResult:
    """An advisor answer shaped like the real one.

    The basket is priced by the real budget engine from the real catalog, so a
    test that reads a price is reading the same arithmetic the application uses.
    """

    catalog = load_catalog()
    recommendation = DesignRecommendation(
        furniture=list(furniture),
        materials=make_materials() if materials is None else materials,
        color_direction="Warm neutrals with pale oak and oatmeal linen.",
        design_rationale="Low pieces keep the window band open.",
    )
    return AdvisorResult(
        recommendation=recommendation,
        catalog_check=catalog_check or CatalogCheck(findings=()),
        budget=compute_budget(
            __import__(
                "models.schemas", fromlist=["BudgetInput"]
            ).BudgetInput(total_budget=Decimal("85000.00")),
            list(furniture),
            catalog,
        ),
    )


class FakeAdvisor:
    """Records every advisor call and replays a queued answer or exception."""

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self._answer: AdvisorResult | BaseException = make_advice(
            FurnitureRecommendation(item_id="sofa_three_seat", quantity=1),
            FurnitureRecommendation(item_id="coffee_table", quantity=1),
        )

    def returns(self, value: AdvisorResult | BaseException) -> FakeAdvisor:
        self._answer = value
        return self

    def recommend_furniture(self, **kwargs) -> AdvisorResult:
        self.calls.append(kwargs)
        if isinstance(self._answer, BaseException):
            raise self._answer
        return self._answer

    @property
    def call_count(self) -> int:
        return len(self.calls)


@pytest.fixture
def advisor(monkeypatch) -> FakeAdvisor:
    fake = FakeAdvisor()
    monkeypatch.setattr(ai_actions, "recommend_furniture", fake.recommend_furniture)
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
    """All markdown, which is where the plan SVG and the tables are written."""

    return " ".join(element.value for element in at.markdown)


def rendered_plain(at: AppTest) -> str:
    """Rendered text with the stylesheet and tags removed."""

    text = rendered(at)
    text = text.split("</style>")[-1] if "</style>" in text else text
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text))


def alerts(at: AppTest) -> str:
    """Every alert, which is where ``render_flash`` and ``st.error`` write."""

    groups = (at.error, at.warning, at.success, at.info)
    return " ".join(
        element.value for group in groups for element in group
    )


def page_text(at: AppTest) -> str:
    """Everything the user can read: markup plus alerts."""

    return f"{rendered_plain(at)} {alerts(at)}"


def click(at: AppTest, label: str) -> AppTest:
    matches = [button for button in at.button if button.label == label]
    assert matches, (
        f"No button labelled {label!r}. Have: {[b.label for b in at.button]}"
    )
    matches[0].click().run()
    assert_no_exceptions(at)
    return at


def build_complete_input(
    at: AppTest, *, width: float = 400.0, length: float = 520.0
) -> AppTest:
    at = click(at, "Start Room Setup")
    at.text_input(key="hmw_room_name").set_value("Living Room")
    at.number_input(key="hmw_width_cm").set_value(width)
    at.number_input(key="hmw_length_cm").set_value(length)
    # Small openings, so the same form is valid for a 150 cm room as for a
    # 400 cm one. The screen under test is the plan, not the room form.
    at.number_input(key="hmw_door_offset").set_value(20.0)
    at.number_input(key="hmw_door_width").set_value(80.0)
    at.number_input(key="hmw_window_offset").set_value(20.0)
    at.number_input(key="hmw_window_width").set_value(80.0)
    at.button(key=ROOM_FORM_SUBMIT).click().run()
    assert_no_exceptions(at)
    assert at.session_state["hm_screen"] == "preferences", rendered_plain(at)

    at.multiselect(key="hmw_materials").set_value(["pale oak", "linen"])
    at.multiselect(key="hmw_requirements").set_value(["Seating for four"])
    at.text_area(key="hmw_notes").set_value("Keep the window side open.")
    at.number_input(key="hmw_budget").set_value(85000.0)
    at.button(key=PREFERENCES_FORM_SUBMIT).click().run()
    assert_no_exceptions(at)
    return at


def open_plan_screen(
    at: AppTest,
    *,
    width: float = 400.0,
    length: float = 520.0,
) -> AppTest:
    """Complete the deterministic input and the AI stages, stopping at the plan.

    The brief and the concepts are recorded directly rather than driven through
    their screens: this module tests the plan, and the earlier screens have
    their own tests. Nothing here touches a model.
    """

    at = build_complete_input(at, width=width, length=length)
    state = state_of(at)
    state.record_brief(make_brief())
    state.record_concepts(
        __import__("models.schemas", fromlist=["ConceptCollection"]).ConceptCollection(
            concepts=[
                make_concept("Low Horizon"),
                make_concept("Window Bench"),
                make_concept("Shelf Spine"),
            ]
        )
    )
    state.select_concept_by_name("Low Horizon")
    at.run()
    assert_no_exceptions(at)

    at.session_state["hm_screen"] = "plan"
    at.run()
    assert_no_exceptions(at)
    assert at.session_state["hm_screen"] == "plan"
    return at


def fresh_app() -> AppTest:
    return AppTest.from_file(str(APP_PATH), default_timeout=90).run()


# --------------------------------------------------------------------------- #
# 1-2. The advisor is button-only, and needs a valid concept
# --------------------------------------------------------------------------- #


def test_opening_the_plan_screen_makes_no_request(advisor: FakeAdvisor) -> None:
    at = open_plan_screen(fresh_app())
    assert advisor.call_count == 0
    assert REGENERATE_LABEL not in {b.label for b in at.button}
    assert "No furniture has been recommended yet." in rendered_plain(at)


def test_a_rerun_after_the_advisor_does_not_call_it_again(
    advisor: FakeAdvisor,
) -> None:
    at = open_plan_screen(fresh_app())
    at = click(at, ADVISOR_LABEL)
    assert advisor.call_count == 1

    # Two plain reruns: a widget interaction elsewhere must not re-request.
    at.run()
    at.run()
    assert advisor.call_count == 1
    assert state_of(at).placement is not None


def test_the_plan_screen_refuses_to_run_without_a_selected_concept() -> None:
    at = build_complete_input(fresh_app())
    state = state_of(at)
    state.record_brief(make_brief())
    state.record_concepts(
        __import__("models.schemas", fromlist=["ConceptCollection"]).ConceptCollection(
            concepts=[
                make_concept("Low Horizon"),
                make_concept("Window Bench"),
                make_concept("Shelf Spine"),
            ]
        )
    )
    at.run()

    at.session_state["hm_screen"] = "plan"
    at.run()
    assert_no_exceptions(at)

    # The screen sends the user back rather than offering a button that cannot
    # work, and it offers no advisor call at all.
    assert at.session_state["hm_screen"] == "concepts"
    assert ADVISOR_LABEL not in {b.label for b in at.button}


def test_the_advisor_receives_the_stored_inputs_and_the_selected_concept(
    advisor: FakeAdvisor,
) -> None:
    at = open_plan_screen(fresh_app())
    click(at, ADVISOR_LABEL)

    call = advisor.calls[0]
    state = state_of(at)
    assert call["room"] == state.room
    assert call["preferences"] == state.preferences
    assert call["budget"] == state.budget
    assert call["brief"] == state.brief
    assert call["concept"] == state.selected_concept


# --------------------------------------------------------------------------- #
# 3. A failed call preserves the previous valid state
# --------------------------------------------------------------------------- #


def test_a_failed_advisor_call_keeps_the_previous_plan(
    advisor: FakeAdvisor,
) -> None:
    at = open_plan_screen(fresh_app())
    at = click(at, ADVISOR_LABEL)

    state = state_of(at)
    before = (state.furniture, state.placement, state.spatial)
    assert before[1] is not None
    score_before = before[1].score

    advisor.returns(AITimeoutError("the request timed out"))
    at = click(at, REGENERATE_LABEL)

    after = state_of(at)
    assert after.furniture == before[0]
    assert after.placement == before[1]
    assert after.spatial == before[2]
    assert after.placement is not None
    assert after.placement.score == score_before
    # The failure is reported, and the plan is still on screen.
    assert "did not answer in time" in alerts(at).lower()
    assert "nothing was saved" in alerts(at).lower()
    assert "<svg" in rendered(at)


def test_a_failed_advisor_call_stores_nothing_when_there_was_no_plan(
    advisor: FakeAdvisor,
) -> None:
    at = open_plan_screen(fresh_app())
    advisor.returns(AITimeoutError("the request timed out"))
    at = click(at, ADVISOR_LABEL)

    state = state_of(at)
    assert state.furniture == ()
    assert state.placement is None
    assert state.is_complete(WorkflowStep.RECOMMENDATIONS) is False
    assert "No furniture has been recommended yet." in rendered_plain(at)
    assert "did not answer in time" in alerts(at).lower()


def test_an_unusable_catalog_reference_is_not_planned(
    advisor: FakeAdvisor,
) -> None:
    """A bad identifier is reported, never silently repaired or drawn."""

    from core.validation import validate_catalog_references
    from models.schemas import RoomInput as SchemeRoom

    room = SchemeRoom(
        room_type="Living Room",
        name="Living Room",
        width_cm=400,
        length_cm=520,
        door={"wall": "south", "offset_cm": 60, "width_cm": 90},
        window={"wall": "north", "offset_cm": 120, "width_cm": 160},
    )
    recommendation = DesignRecommendation(
        furniture=[FurnitureRecommendation(item_id="ghost_sofa")],
        materials=[],
        color_direction="Unchanged.",
        design_rationale="Unchanged.",
    )
    findings = validate_catalog_references(
        room, recommendation.furniture, load_catalog()
    )
    assert findings and findings[0].severity == "error"

    advisor.returns(
        make_advice(
            FurnitureRecommendation(item_id="ghost_sofa"),
            materials=[],
            catalog_check=CatalogCheck(findings=tuple(findings)),
        )
    )
    at = open_plan_screen(fresh_app())
    at = click(at, ADVISOR_LABEL)

    state = state_of(at)
    # The unknown identifier is preserved for the user to see; it is not
    # rewritten to a similar item.
    assert [item.item_id for item in state.furniture] == ["ghost_sofa"]
    assert state.placement is None
    assert "<svg" not in rendered(at)
    plain = page_text(at).lower()
    assert "not in the local catalog" in plain
    assert "ghost_sofa" in plain


def test_an_unplannable_basket_is_never_offered_for_planning(
    advisor: FakeAdvisor,
) -> None:
    """A basket with a blocking catalog error must not get a "calculate" button.

    The advisor rejects such a basket, but the rule has to hold on the screen too:
    otherwise a reload could offer to plan a basket the catalogue rejects.
    """

    from core.validation import validate_catalog_references

    at = open_plan_screen(fresh_app())
    click(at, ADVISOR_LABEL)
    state = state_of(at)
    assert state.room is not None

    # Store an item the living-room catalogue does not offer, the way a stored
    # or reloaded project could. Nothing repairs it.
    state.record_recommendation(
        DesignRecommendation(
            furniture=[FurnitureRecommendation(item_id="dining_table")],
            materials=[],
            color_direction="Unchanged.",
            design_rationale="Unchanged.",
        )
    )
    state.record_spatial(
        __import__("models.schemas", fromlist=["SpatialValidation"]).SpatialValidation(
            is_valid=True, boundary_violations=[], overlaps=[], warnings=[]
        )
    )
    findings = validate_catalog_references(
        state.room, state.furniture, load_catalog()
    )
    assert [f.code for f in findings if f.is_error] == ["unsupported_room_type"]

    at.run()
    assert_no_exceptions(at)

    plain = page_text(at).lower()
    assert "basket cannot be used" in plain
    assert "dining table" in plain
    # The screen offers no way to plan it, and draws no layout from it.
    labels = {button.label for button in at.button}
    assert "Calculate the layout" not in labels
    assert "Recalculate the layout" not in labels
    assert "<svg" not in rendered(at)


# --------------------------------------------------------------------------- #
# 4 and 10. Catalog references and quantities survive
# --------------------------------------------------------------------------- #


def test_the_stored_basket_keeps_every_catalog_reference(
    advisor: FakeAdvisor,
) -> None:
    advisor.returns(
        make_advice(
            FurnitureRecommendation(item_id="sofa_three_seat", quantity=1),
            FurnitureRecommendation(item_id="bookshelf", quantity=2),
            FurnitureRecommendation(item_id="floor_lamp", quantity=1),
        )
    )
    at = open_plan_screen(fresh_app())
    at = click(at, ADVISOR_LABEL)

    state = state_of(at)
    assert [item.item_id for item in state.furniture] == [
        "sofa_three_seat",
        "bookshelf",
        "floor_lamp",
    ]
    # The advisor supplied no coordinates; the engine did.
    assert all(item.positions for item in state.furniture)


def test_every_placed_copy_gets_its_own_position(advisor: FakeAdvisor) -> None:
    # Both items are catalogued for a living room, so the basket is plannable.
    advisor.returns(
        make_advice(
            FurnitureRecommendation(item_id="armchair", quantity=2),
            FurnitureRecommendation(item_id="side_table", quantity=3),
        )
    )
    at = open_plan_screen(fresh_app())
    at = click(at, ADVISOR_LABEL)

    state = state_of(at)
    positions = {item.item_id: len(item.positions) for item in state.furniture}
    assert positions == {"armchair": 2, "side_table": 3}

    outcome = state.placement
    assert outcome is not None
    assert outcome.status is PlacementStatus.COMPLETE
    assert outcome.placed_count == 5
    # Five placed copies, five distinct coordinate pairs: nothing is collapsed.
    coordinates = {
        (round(p.left_cm, 6), round(p.bottom_cm, 6)) for p in outcome.placed
    }
    assert len(coordinates) == 5
    # The request still says what was asked for, because the budget uses it.
    assert [item.quantity for item in state.furniture] == [2, 3]

    # The plan draws five blocks beside the room outline, not two.
    assert rendered(at).count('fill="#DDD8CB"') == 5


# --------------------------------------------------------------------------- #
# 5 and 7. The placement engine is integrated and the plan uses its numbers
# --------------------------------------------------------------------------- #


def test_the_screen_uses_the_engine_rather_than_its_own_geometry(
    advisor: FakeAdvisor,
) -> None:
    advisor.returns(
        make_advice(
            FurnitureRecommendation(item_id="sofa_three_seat", quantity=1),
            FurnitureRecommendation(item_id="coffee_table", quantity=1),
        )
    )
    at = open_plan_screen(fresh_app())
    at = click(at, ADVISOR_LABEL)

    state = state_of(at)
    expected = layout.analyse_layout(
        state.room, state.furniture, load_catalog()
    )
    stored = state.placement
    assert stored is not None
    # Same engine, same inputs, same coordinates: the screen did not invent a
    # second layout.
    assert [(p.item_id, p.left_cm, p.bottom_cm) for p in stored.placed] == [
        (p.item_id, p.left_cm, p.bottom_cm) for p in expected.outcome.placed
    ]


def test_the_plan_draws_the_engine_coordinates(advisor: FakeAdvisor) -> None:
    advisor.returns(
        make_advice(
            FurnitureRecommendation(item_id="sofa_three_seat", quantity=1),
            FurnitureRecommendation(item_id="bookshelf", quantity=1),
        )
    )
    at = open_plan_screen(fresh_app())
    at = click(at, ADVISOR_LABEL)

    outcome = state_of(at).placement
    assert outcome is not None
    markup = rendered(at)

    # The room outline is drawn from the saved dimensions.
    assert 'width="' in markup
    assert "400" in markup and "520" in markup

    # Every placed piece appears in the table with its measured position, so
    # the numbers in the picture are checkable.
    plain = rendered_plain(at)
    for footprint in outcome.placed:
        assert footprint.label in plain
        assert f"x {footprint.left_cm:g}–{footprint.right_cm:g}" in plain
        assert f"{footprint.width_cm:g} × {footprint.depth_cm:g} cm" in plain


# --------------------------------------------------------------------------- #
# 6, 8, 9. The three statuses, and what each one draws
# --------------------------------------------------------------------------- #


def test_a_complete_layout_is_presented_as_complete_and_drawn(
    advisor: FakeAdvisor,
) -> None:
    advisor.returns(
        make_advice(
            FurnitureRecommendation(item_id="sofa_three_seat", quantity=1),
            FurnitureRecommendation(item_id="coffee_table", quantity=1),
        )
    )
    at = open_plan_screen(fresh_app())
    at = click(at, ADVISOR_LABEL)

    state = state_of(at)
    assert state.placement is not None
    assert state.placement.status is PlacementStatus.COMPLETE
    assert state.placement.score is not None
    assert state.spatial is not None and state.spatial.is_valid

    plain = rendered_plain(at)
    assert "Complete layout" in plain
    assert "Every one of the 2 requested items was placed" in plain
    assert "Partial layout" not in plain
    assert "Layout failed" not in plain
    assert "<svg" in rendered(at)
    # The score is labelled as a heuristic, never as validity.
    assert "Quality heuristic, not a validity check." in plain
    assert "Geometric validity" in plain


def test_a_failed_layout_draws_no_plan_and_claims_no_score(
    advisor: FakeAdvisor,
) -> None:
    # A 150 x 150 room cannot hold a three-seat sofa under the clearance rules.
    at = open_plan_screen(fresh_app(), width=150.0, length=150.0)
    advisor.returns(
        make_advice(
            FurnitureRecommendation(item_id="sofa_three_seat", quantity=1),
            materials=[],
        )
    )
    at = click(at, ADVISOR_LABEL)

    state = state_of(at)
    assert state.placement is not None
    assert state.placement.status is PlacementStatus.FAILED
    # No validated layout, so no footprint and no achieved score.
    assert state.placement.placed == []
    assert state.placement.score is None
    assert state.placement.unplaced

    markup = rendered(at)
    plain = rendered_plain(at)
    assert "<svg" not in markup
    assert "Layout failed" in plain
    assert "No plan drawn" in plain
    assert "Every one of the 2 requested items" not in plain
    assert "Complete layout" not in plain
    # The reason is stated, and it names the item that did not fit.
    assert "Three-seat sofa" in plain


def test_a_partial_layout_draws_only_the_placed_copies(
    advisor: FakeAdvisor,
) -> None:
    # Twenty armchairs do not fit in a 400 x 500 room; some do.
    at = open_plan_screen(fresh_app(), width=400.0, length=500.0)
    advisor.returns(
        make_advice(
            FurnitureRecommendation(item_id="armchair", quantity=20),
            materials=[],
        )
    )
    at = click(at, ADVISOR_LABEL)

    state = state_of(at)
    outcome = state.placement
    assert outcome is not None
    assert outcome.status is PlacementStatus.PARTIAL
    assert 0 < outcome.placed_count < 20
    assert outcome.unplaced_count == 20 - outcome.placed_count

    plain = rendered_plain(at)
    assert "Partial layout" in plain
    assert (
        f"{outcome.placed_count} of 20 requested items were placed" in plain
    )
    assert "Complete layout" not in plain
    assert "Layout failed" not in plain
    assert "Partial plan" in plain
    assert "not in this room" in plain

    # Every drawn block is a placed footprint, and the drawn count matches the
    # stored count: no unplaced copy is drawn to fill the gap.
    markup = rendered(at)
    blocks = markup.count('fill="#DDD8CB"')
    assert blocks == outcome.placed_count
    assert blocks < 20
    # The unplaced copies are named with the engine's reason.
    assert "not placed" in plain.lower()


def test_the_three_statuses_cannot_be_confused_by_their_wording() -> None:
    """A failure sentence and a success sentence never share their key phrase."""

    from models.schemas import (
        PlacedFootprint,
        PlacementOutcome,
        UnplacedItem,
    )
    from ui.pages_plan import _status_copy

    placed = PlacedFootprint(
        item_id="armchair",
        label="Armchair",
        left_cm=0.0,
        bottom_cm=0.0,
        width_cm=80.0,
        depth_cm=80.0,
    )
    unplaced = UnplacedItem(
        item_id="sofa_three_seat",
        label="Three-seat sofa",
        count=1,
        reason_code="no_room",
        reason="There is no free wall space long enough.",
    )

    complete = _status_copy(
        PlacementOutcome(
            status=PlacementStatus.COMPLETE, score=0.9, placed=[placed]
        )
    )
    partial = _status_copy(
        PlacementOutcome(
            status=PlacementStatus.PARTIAL,
            score=0.5,
            placed=[placed],
            unplaced=[unplaced],
        )
    )
    failed = _status_copy(
        PlacementOutcome(
            status=PlacementStatus.FAILED, placed=[], unplaced=[unplaced]
        )
    )

    badges = [complete[0], partial[0], failed[0]]
    assert len(set(badges)) == 3
    assert "complete" in complete[0].lower()
    assert "partial" in partial[0].lower()
    assert "failed" in failed[0].lower()

    # The failure never reports a count of placed items, and explicitly denies
    # that there is a plan; the other two do state one.
    assert "1 of 2 requested items were placed" in partial[1]
    assert "every one of the 1 requested items" in complete[1].lower()
    assert "no plan to show" in failed[1].lower()
    assert "requested items were placed" not in failed[1]


# --------------------------------------------------------------------------- #
# 11. Errors are not warnings, and warnings are not errors
# --------------------------------------------------------------------------- #


def test_blocking_errors_and_warnings_are_reported_separately(
    advisor: FakeAdvisor,
) -> None:
    from models.schemas import SpatialValidation

    at = open_plan_screen(fresh_app())
    at = click(at, ADVISOR_LABEL)
    state = state_of(at)

    # Replace the verdict with one carrying both kinds of finding, through the
    # same setter the screen uses.
    assert state.placement is not None
    mixed = SpatialValidation(
        is_valid=False,
        boundary_violations=["'Three-seat sofa' extends beyond the north wall."],
        overlaps=[],
        warnings=["'Floor lamp' stands inside the window clearance band."],
    )
    state.record_spatial(mixed, state.placement)
    at.run()

    plain = rendered_plain(at)
    assert "Blocking problems" in plain
    assert "beyond the north wall" in plain
    assert "Warnings" in plain
    assert "inside the window clearance band" in plain

    # Order and labelling: the blocking message is never filed under warnings.
    blocking_at = plain.index("Blocking problems")
    warnings_at = plain.index("Warnings")
    assert blocking_at < warnings_at
    assert plain.index("beyond the north wall") < warnings_at
    assert "Warnings do not block the layout." in plain


def test_door_and_window_clearance_rules_are_stated(
    advisor: FakeAdvisor,
) -> None:
    at = open_plan_screen(fresh_app())
    at = click(at, ADVISOR_LABEL)
    plain = rendered_plain(at)
    assert "Door clearance kept free" in plain
    assert "Window clearance watched" in plain
    assert "Blocking the doorway is an error" in plain
    assert "standing in the window band is a warning" in plain


# --------------------------------------------------------------------------- #
# 12. Materials are shown, and never priced
# --------------------------------------------------------------------------- #


def test_materials_are_shown_in_their_own_unpriced_section(
    advisor: FakeAdvisor,
) -> None:
    advisor.returns(
        make_advice(
            FurnitureRecommendation(item_id="sofa_three_seat", quantity=1),
            materials=make_materials("Pale oak flooring", "Linen curtain"),
        )
    )
    at = open_plan_screen(fresh_app())
    at = click(at, ADVISOR_LABEL)

    plain = rendered_plain(at)
    assert "Materials and finishes" in plain
    assert "Pale oak flooring" in plain
    assert "Linen curtain" in plain
    # Each material is explicitly unpriced; no figure is attached to one.
    assert plain.count("Not priced: materials have no catalog cost") == 2
    assert "no price list for materials" in plain
    # No currency figure is invented anywhere in the material section.
    materials_section = plain.split("Materials and finishes", 1)[1]
    materials_section = materials_section.split("Furniture and materials", 1)[0]
    assert "₺" not in materials_section and "TRY" not in materials_section


def test_no_material_price_field_exists_to_render() -> None:
    """The absence is a model fact, so the interface cannot be tempted."""

    fields = set(MaterialRecommendation.model_fields)
    assert not fields & {"price", "cost", "unit_cost", "indicative_unit_cost"}


# --------------------------------------------------------------------------- #
# Staleness: state rules, not screen rules
# --------------------------------------------------------------------------- #


def test_changing_the_concept_makes_the_old_plan_stale(
    advisor: FakeAdvisor,
) -> None:
    at = open_plan_screen(fresh_app())
    at = click(at, ADVISOR_LABEL)

    state = state_of(at)
    assert state.placement is not None
    state.select_concept_by_name("Window Bench")
    at.run()

    state = state_of(at)
    assert state.furniture == ()
    assert state.placement is None
    assert state.spatial is None
    assert state.is_complete(WorkflowStep.RECOMMENDATIONS) is False
    # The screen does not draw the old plan under the new concept.
    assert "<svg" not in rendered(at)


def test_a_room_dimension_change_strips_the_stored_coordinates() -> None:
    """The stored position belongs to the validation that produced it."""

    at = open_plan_screen(fresh_app())
    state = state_of(at)
    state.record_recommendation(
        make_advice(
            FurnitureRecommendation(item_id="sofa_three_seat", quantity=1)
        ).recommendation
    )
    analysis = layout.analyse_layout(
        state.room, state.furniture, load_catalog()
    )
    state.record_spatial(analysis.validation, analysis.outcome, analysis.placements)
    assert state.furniture[0].positions

    room = state.room
    assert room is not None
    narrower = RoomInput(
        room_type=room.room_type,
        name=room.name,
        width_cm=room.width_cm - 40.0,
        length_cm=room.length_cm,
        ceiling_height_cm=room.ceiling_height_cm,
        door=room.door,
        window=room.window.model_copy(update={"width_cm": 140.0}),
    )
    state.set_room(narrower)

    # The layout and its coordinates are gone together, and nothing invented a
    # new position for the new room.
    assert state.placement is None
    assert state.spatial is None
    assert state.furniture == () or all(
        not item.positions for item in state.furniture
    )


def test_recording_coordinates_does_not_invalidate_the_budget(
    advisor: FakeAdvisor,
) -> None:
    """Placement is an annotation: it must not discard a computed price."""

    at = open_plan_screen(fresh_app())
    state = state_of(at)
    state.record_recommendation(
        make_advice(
            FurnitureRecommendation(item_id="sofa_three_seat", quantity=1)
        ).recommendation
    )
    state.record_budget_analysis(
        compute_budget(state.budget, state.furniture, load_catalog()).analysis
    )
    assert state.budget_analysis is not None

    analysis = layout.analyse_layout(
        state.room, state.furniture, load_catalog()
    )
    dropped = state.record_spatial(
        analysis.validation, analysis.outcome, analysis.placements
    )

    assert DataKey.BUDGET_ANALYSIS not in dropped
    assert state.budget_analysis is not None
    assert state.furniture[0].positions


def test_a_later_rerun_keeps_the_stored_plan(advisor: FakeAdvisor) -> None:
    at = open_plan_screen(fresh_app())
    at = click(at, ADVISOR_LABEL)
    first = state_of(at).placement
    assert first is not None

    at.run()
    at.run()
    assert state_of(at).placement == first


def test_repeating_the_same_advice_keeps_the_layout_and_the_price(
    advisor: FakeAdvisor,
) -> None:
    """An unchanged request is not a new basket, even after coordinates exist."""

    at = open_plan_screen(fresh_app())
    at = click(at, ADVISOR_LABEL)
    state = state_of(at)
    first_placement = state.placement
    first_furniture = state.furniture
    assert first_placement is not None
    assert first_furniture[0].positions

    state.record_budget_analysis(
        compute_budget(state.budget, state.furniture, load_catalog()).analysis
    )
    at.run()

    # The same answer again: the advisor supplies no coordinates, the stored copy
    # has some, and the engine changed the rotation. None of that is a new
    # request, so nothing downstream is discarded.
    dropped = state.record_recommendation(
        make_advice(
            *(
                FurnitureRecommendation(
                    item_id=item.item_id,
                    quantity=item.quantity,
                    rationale=item.rationale,
                )
                for item in first_furniture
            )
        ).recommendation
    )

    assert dropped == ()
    assert state.budget_analysis is not None
    assert state.spatial is not None
    assert state.placement == first_placement


def test_a_changed_request_still_invalidates_the_layout(
    advisor: FakeAdvisor,
) -> None:
    at = open_plan_screen(fresh_app())
    at = click(at, ADVISOR_LABEL)
    state = state_of(at)
    assert state.placement is not None

    dropped = state.record_recommendation(
        make_advice(
            FurnitureRecommendation(item_id="sofa_three_seat", quantity=2),
        ).recommendation
    )

    # The replaced key is not listed as invalidated (it was refreshed), but
    # everything derived from it is, and the old layout is gone.
    assert DataKey.SPATIAL in dropped
    assert state.furniture[0].quantity == 2
    assert state.placement is None
    assert state.spatial is None


# --------------------------------------------------------------------------- #
# 14. The start of the workflow is still AI-free
# --------------------------------------------------------------------------- #


def test_the_first_screens_still_make_no_advisor_call(
    advisor: FakeAdvisor,
) -> None:
    at = build_complete_input(fresh_app())
    assert advisor.call_count == 0
    at = click(at, "Continue to design brief")
    assert advisor.call_count == 0
    at = click(at, "Back to overview")
    assert advisor.call_count == 0


def test_the_plan_screen_plays_no_part_in_starting_a_project(
    advisor: FakeAdvisor,
) -> None:
    """The screen requires an existing concept and never fabricates one."""

    at = fresh_app()
    at = click(at, "Start Room Setup")
    at.session_state["hm_screen"] = "plan"
    at.run()
    assert_no_exceptions(at)
    assert at.session_state["hm_screen"] == "room"
    assert advisor.call_count == 0
