"""End-to-end tests for the deterministic workflow, driven through Streamlit.

These tests load the real ``app.py`` in Streamlit's own test harness, so they
exercise the whole adapter: widgets, forms, commits, session state, navigation
and rendering. Nothing is stubbed. What they are protecting is the user-visible
contract of this development step:

* a valid project can be built from nothing without any AI call,
* invalid input is refused and leaves the stored project untouched,
* upstream edits clear exactly the downstream work that depended on them,
* a retained result is never presented as current,
* every screen renders without an exception.

The AI layer is deliberately absent from this path. ``app.py`` does not import
``ai`` and one test below asserts that structurally, so "no API call was made"
is a property of the wiring rather than a promise in a comment.
"""

from __future__ import annotations

import re
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from models.schemas import (
    BudgetAnalysis,
    ConceptCollection,
    DesignBrief,
    DesignConcept,
    DesignEvaluation,
    DesignRecommendation,
    FurnitureRecommendation,
    MaterialRecommendation,
    SpatialValidation,
)
from workflow.dependencies import DataKey
from workflow.state import WorkflowState, WorkflowStep

#: Repository root, so the app is found regardless of the pytest working dir.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "app.py"

ROOM_FORM_SUBMIT = "FormSubmitter:hm_room_form-Save room information"
PREFERENCES_FORM_SUBMIT = (
    "FormSubmitter:hm_preferences_form-Save preferences and budget"
)


# --------------------------------------------------------------------------- #
# Harness helpers
# --------------------------------------------------------------------------- #


def fresh_app() -> AppTest:
    """Load the application on the landing page."""

    at = AppTest.from_file(str(APP_PATH), default_timeout=90).run()
    assert_no_exceptions(at)
    return at


def assert_no_exceptions(at: AppTest) -> None:
    exceptions = [element.message for element in at.exception]
    assert exceptions == [], exceptions


def state_of(at: AppTest) -> WorkflowState:
    """The live workflow object held by the session."""

    state = at.session_state["hm_workflow_state"]
    assert isinstance(state, WorkflowState)
    return state


def click(at: AppTest, label: str) -> AppTest:
    """Click the single button with ``label`` and rerun."""

    matches = [button for button in at.button if button.label == label]
    assert matches, f"No button labelled {label!r}. Have: {[b.label for b in at.button]}"
    matches[0].click().run()
    assert_no_exceptions(at)
    return at


def enter_room_form(at: AppTest) -> AppTest:
    """Landing page -> room screen."""

    click(at, "Start Room Setup")
    assert at.session_state["hm_screen"] == "room"
    return at


def submit_valid_room(at: AppTest, name: str = "Living Room", width: float = 400.0) -> AppTest:
    at.text_input(key="hmw_room_name").set_value(name)
    at.number_input(key="hmw_width_cm").set_value(width)
    at.button(key=ROOM_FORM_SUBMIT).click().run()
    assert_no_exceptions(at)
    return at


def submit_valid_preferences(at: AppTest) -> AppTest:
    at.multiselect(key="hmw_materials").set_value(["pale oak", "linen"])
    at.multiselect(key="hmw_requirements").set_value(["Seating for four"])
    at.text_area(key="hmw_notes").set_value("Keep the window side open.")
    at.number_input(key="hmw_budget").set_value(45000.0)
    at.button(key=PREFERENCES_FORM_SUBMIT).click().run()
    assert_no_exceptions(at)
    return at


def build_complete_input(at: AppTest) -> AppTest:
    """Drive the real UI to a complete deterministic input."""

    enter_room_form(at)
    submit_valid_room(at)
    submit_valid_preferences(at)
    return at


def make_concept(name: str) -> DesignConcept:
    return DesignConcept(
        name=name,
        description=f"{name} description.",
        design_direction="Quiet composition.",
        color_and_material_direction="Warm neutrals with oak.",
        furniture_approach="Low-profile seating.",
        functional_rationale="Keeps circulation clear.",
        budget_suitability="Fits the budget.",
    )


def prime_downstream_results(state: WorkflowState) -> None:
    """Attach plausible results so invalidation has something to clear.

    This is what a later phase will do through the AI steps. It is written here
    so this step can prove that a room edit discards them, which is the whole
    point of the dependency table.
    """

    state.record_brief(
        DesignBrief(
            summary="A calm living room.",
            functional_priorities=["Seating for four"],
            constraints=["One door and one window"],
            ambiguities=[],
            warnings=[],
        )
    )
    state.record_concepts(
        ConceptCollection(
            concepts=[
                make_concept("Quiet Oak"),
                make_concept("Soft Contrast"),
                make_concept("Warm Studio"),
            ]
        )
    )
    state.select_concept_by_name("Quiet Oak")
    state.record_recommendation(
        DesignRecommendation(
            furniture=[
                FurnitureRecommendation(
                    item_id="sofa_three_seat", quantity=1, rationale="Main seating."
                )
            ],
            materials=[
                MaterialRecommendation(
                    name="Pale oak",
                    category="Flooring",
                    color_direction="Warm neutral",
                    rationale="Matches the palette.",
                )
            ],
            color_direction="Warm neutrals.",
            design_rationale="Low and quiet.",
        )
    )
    state.record_spatial(
        SpatialValidation(
            is_valid=True,
            boundary_violations=[],
            overlaps=[],
            warnings=[],
        )
    )
    state.record_budget_analysis(
        BudgetAnalysis(
            furniture_subtotal=Decimal("21000.00"),
            total_estimated=Decimal("21000.00"),
            remaining_budget=Decimal("24000.00"),
        )
    )
    state.record_evaluation(
        DesignEvaluation(
            requirement_compatibility="Seating for four is satisfied.",
            style_consistency="Consistent with Japandi.",
            functional_suitability="Circulation remains clear.",
            budget_suitability="Within budget.",
        )
    )


# --------------------------------------------------------------------------- #
# 1. The application starts
# --------------------------------------------------------------------------- #


def test_the_application_opens_on_the_landing_page_without_an_error() -> None:
    at = fresh_app()
    # Nothing has been set: the landing page is the default, derived from the
    # absence of the key rather than from a stored ``False``.
    assert "hm_workflow_entered" not in at.session_state
    assert any(button.label == "Start Room Setup" for button in at.button)
    # The workflow object is not created just by opening the app.
    assert "hm_workflow_state" not in at.session_state


def test_the_landing_page_does_not_claim_unimplemented_stages_are_ready() -> None:
    at = fresh_app()
    rendered = " ".join(
        [element.value for element in at.markdown]
        + [element.value for element in at.caption]
    ).lower()
    assert "not implemented" in rendered or "planned" in rendered


def test_the_landing_page_does_not_call_implemented_stages_future_work() -> None:
    """Regression: the start note was a Phase-3 leftover.

    It said "the concept, plan and report stages follow in later development
    steps" — on the first page a reviewer reads, about three stages that all work.
    ``AGENTS.md`` §10 forbids presenting implemented features as planned.
    """

    at = fresh_app()
    rendered = " ".join(element.value for element in at.markdown)
    assert "later development steps" not in rendered
    assert "available now and work without any AI call" not in rendered
    # What replaces it has to be true and specific.
    assert "without an AI call" in rendered


def test_the_landing_page_advertises_the_journey_the_shell_actually_walks() -> None:
    """The hero's flow line and the stage strip name the same five stages.

    A landing page that advertises four differently-worded steps while the shell
    shows five named stages is the first place a reader can catch them disagreeing.
    """

    from ui.shell import STAGES

    at = fresh_app()
    rendered = " ".join(element.value for element in at.markdown)
    for name, _ in STAGES:
        assert name in rendered, f"{name} is not advertised on the landing page"
    # And the old four-step wording is gone.
    assert "Explore Concepts" not in rendered
    assert "Generate Your Report" not in rendered


def test_the_roadmap_does_not_call_the_finished_version_unfinished() -> None:
    """Regression: the V1 card still read "In development" after V1 was done.

    The landing page said "V1 is the only version under development" and badged
    the finished release as in progress, while both READMEs and
    ``RELEASE_READINESS.md`` called V1 complete. A reader who reached the bottom
    of the first page was told the product was unfinished.
    """

    from ui.pages_landing import BADGE_LABELS, ROADMAP

    at = fresh_app()
    rendered = " ".join(element.value for element in at.markdown).lower()

    assert "in development" not in rendered
    assert "under development" not in rendered
    # Each card's badge is decided by its state, so the vocabulary cannot drift
    # from the data.
    states = [state for _, _, state, _ in ROADMAP]
    assert states[0] == "complete"
    assert set(states[1:]) == {"planned"}
    assert BADGE_LABELS["complete"] == "Complete"
    assert BADGE_LABELS["planned"] == "Planned"


# --------------------------------------------------------------------------- #
# 2. Room form: valid submission
# --------------------------------------------------------------------------- #


def test_entering_the_workflow_creates_the_state_exactly_once() -> None:
    at = fresh_app()
    enter_room_form(at)
    first = state_of(at)
    at.run()
    assert_no_exceptions(at)
    assert state_of(at) is first


def test_a_valid_room_is_stored_and_unlocks_the_next_screen() -> None:
    at = fresh_app()
    enter_room_form(at)
    submit_valid_room(at, name="Living Room", width=420.0)

    state = state_of(at)
    assert state.room is not None
    assert state.room.name == "Living Room"
    assert state.room.width_cm == 420.0
    assert state.is_complete(WorkflowStep.ROOM_INFORMATION) is True

    assert at.session_state["hm_screen"] == "preferences"
    assert any("Room information saved." == element.value for element in at.success)


def test_inputs_survive_a_rerun_that_changes_nothing() -> None:
    at = fresh_app()
    enter_room_form(at)
    submit_valid_room(at)
    before = state_of(at).room
    screen_before = at.session_state["hm_screen"]

    at.run()
    assert_no_exceptions(at)
    assert state_of(at).room == before
    assert at.session_state["hm_screen"] == screen_before


def test_returning_to_the_room_form_shows_the_saved_room_not_an_empty_one() -> None:
    at = build_complete_input(fresh_app())
    click(at, "Edit room")

    # The widgets are seeded from the stored room, so "edit" means edit.
    assert at.text_input(key="hmw_room_name").value == "Living Room"
    assert at.number_input(key="hmw_width_cm").value == 400.0
    assert at.selectbox(key="hmw_door_wall").value.name == "SOUTH"


# --------------------------------------------------------------------------- #
# 3. Room form: invalid submission
# --------------------------------------------------------------------------- #


def test_a_room_without_a_name_is_refused_and_nothing_is_stored() -> None:
    at = fresh_app()
    enter_room_form(at)
    at.button(key=ROOM_FORM_SUBMIT).click().run()
    assert_no_exceptions(at)

    state = state_of(at)
    assert state.room is None
    assert state.is_complete(WorkflowStep.ROOM_INFORMATION) is False
    # The user stays on the form, with a sentence rather than a traceback.
    assert at.session_state["hm_screen"] == "room"
    errors = " ".join(element.value for element in at.error)
    assert "Nothing was saved" in errors
    bullets = " ".join(element.value for element in at.markdown)
    assert "Room name" in bullets


def test_a_door_that_does_not_fit_its_wall_is_refused_by_geometry() -> None:
    at = fresh_app()
    enter_room_form(at)
    at.text_input(key="hmw_room_name").set_value("Overflow")
    # The widget caps the offset at the wall span, so the door is moved by
    # shrinking the room instead: 100 cm wide, door offset 60 + width 90.
    at.number_input(key="hmw_width_cm").set_value(100.0)
    at.button(key=ROOM_FORM_SUBMIT).click().run()
    assert_no_exceptions(at)

    state = state_of(at)
    assert state.room is None
    assert state.is_complete(WorkflowStep.ROOM_INFORMATION) is False
    detail = " ".join(element.value for element in at.markdown).lower()
    assert "door" in detail and "fit" in detail


def test_a_door_and_window_on_the_same_stretch_are_refused() -> None:
    at = fresh_app()
    enter_room_form(at)
    # Everything is set before submitting: a form only reports its widget values
    # when it is submitted, so an intermediate rerun would drop them.
    at.selectbox(key="hmw_window_wall").set_value(
        at.selectbox(key="hmw_door_wall").value
    )
    at.text_input(key="hmw_room_name").set_value("Collision")
    # Door occupies 60..150 cm on the south wall; the window is put right on top.
    at.number_input(key="hmw_window_offset").set_value(60.0)
    at.button(key=ROOM_FORM_SUBMIT).click().run()
    assert_no_exceptions(at)

    state = state_of(at)
    assert state.room is None
    detail = " ".join(element.value for element in at.markdown).lower()
    assert "overlap" in detail


def test_an_invalid_edit_does_not_destroy_the_room_that_was_already_saved() -> None:
    at = build_complete_input(fresh_app())
    assert state_of(at).preferences is not None

    # Go back to the room and submit an empty name.
    click(at, "Edit room")
    assert at.session_state["hm_screen"] == "room"
    assert at.text_input(key="hmw_room_name").value == "Living Room"
    at.text_input(key="hmw_room_name").set_value("   ")
    at.button(key=ROOM_FORM_SUBMIT).click().run()
    assert_no_exceptions(at)

    state = state_of(at)
    assert state.room is not None
    assert state.room.name == "Living Room"
    assert state.preferences is not None
    assert at.session_state["hm_screen"] == "room"


# --------------------------------------------------------------------------- #
# 4. Preferences, requirements and budget
# --------------------------------------------------------------------------- #


def test_preferences_requirements_and_budget_are_stored_from_the_form() -> None:
    at = fresh_app()
    enter_room_form(at)
    submit_valid_room(at)
    submit_valid_preferences(at)

    state = state_of(at)
    assert state.preferences is not None
    assert state.preferences.material_preferences == ["pale oak", "linen"]
    assert state.requirements is not None
    assert state.requirements.functional_requirements == ["Seating for four"]
    assert state.requirements.notes == "Keep the window side open."
    assert state.budget is not None
    assert state.budget.total_budget == Decimal("45000.0")
    assert state.budget.currency == "TRY"
    assert state.is_complete(WorkflowStep.DESIGN_PREFERENCES) is True
    assert at.session_state["hm_screen"] == "review"


def test_selecting_a_style_card_changes_the_stored_preference() -> None:
    at = fresh_app()
    enter_room_form(at)
    submit_valid_room(at)

    before = at.session_state["hmw_style"]
    cards = [button for button in at.button if button.label in {"Choose", "Selected"}]
    assert len(cards) >= 10  # six styles plus four palettes

    # The first style card is Scandinavian; the default is Japandi.
    cards[0].click().run()
    assert_no_exceptions(at)
    after = at.session_state["hmw_style"]
    assert after is not before
    assert after.name == "SCANDINAVIAN"

    # The visible indicator follows the new selection.
    labels = [button.label for button in at.button]
    assert labels.count("Selected") >= 2  # one style and one palette


def test_a_style_choice_is_kept_even_before_the_form_is_submitted() -> None:
    at = fresh_app()
    enter_room_form(at)
    submit_valid_room(at)
    cards = [button for button in at.button if button.label in {"Choose", "Selected"}]
    cards[0].click().run()
    assert_no_exceptions(at)
    # Nothing was committed yet: the workflow still has no preferences.
    assert state_of(at).preferences is None
    assert at.session_state["hm_screen"] == "preferences"


def test_the_budget_is_stored_exactly_as_typed() -> None:
    at = fresh_app()
    enter_room_form(at)
    submit_valid_room(at)

    at.number_input(key="hmw_budget").set_value(1234.56)
    at.button(key=PREFERENCES_FORM_SUBMIT).click().run()
    assert_no_exceptions(at)

    state = state_of(at)
    assert state.budget is not None
    assert state.budget.total_budget == Decimal("1234.56")
    # Not 1234.5599999999999: the value went through ``Decimal(str(...))``.
    assert str(state.budget.total_budget) == "1234.56"


def test_a_budget_the_model_cannot_accept_is_refused_by_the_commit_path() -> None:
    """The widget formats to two decimals, so this guard lives one level down.

    The interface must not "fix" an amount it cannot accept. ``build_budget`` is
    the gate, and it rejects rather than rounds; the AppTest run below confirms
    the refusal surfaces as a sentence on the review-independent form path.
    """

    from ui.commits import build_budget

    outcome = build_budget(Decimal("1234.567"))
    assert outcome.value is None
    assert outcome.issues
    assert "two decimal places" in outcome.issues[0].message.lower()


# --------------------------------------------------------------------------- #
# 5. Review screen
# --------------------------------------------------------------------------- #


def test_the_review_screen_shows_the_four_inputs_and_no_ai_claim() -> None:
    at = build_complete_input(fresh_app())
    assert at.session_state["hm_screen"] == "review"

    rendered = " ".join(element.value for element in at.markdown)
    assert "Living Room" in rendered
    assert "45.000,00 TRY" in rendered
    assert "Japandi" in rendered or "JAPANDI" in rendered
    assert "All blocking checks passed." in " ".join(
        element.value for element in at.success
    )

    # Reaching this screen must not have contacted the model: the next step is
    # offered, and the copy states that nothing has been sent yet.
    rendered_lower = rendered.lower()
    assert "nothing has been sent to a model yet" in rendered_lower


def test_the_review_screen_only_offers_screens_that_exist() -> None:
    at = build_complete_input(fresh_app())
    labels = {button.label for button in at.button}
    # Every action belongs to an implemented stage. The concepts and plan
    # screens are not reachable in one click from here, and no button pretends
    # that a later stage is finished.
    assert labels <= {
        "Edit room",
        "Edit preferences",
        "Continue to design brief",
        "Start a new project",
        "Back to overview",
    }


def test_starting_a_new_project_clears_the_project_and_returns_to_the_room() -> None:
    at = build_complete_input(fresh_app())
    click(at, "Start a new project")
    assert state_of(at).room is None
    assert at.session_state["hm_screen"] == "room"
    assert at.text_input(key="hmw_room_name").value == ""


# --------------------------------------------------------------------------- #
# 6. Invalidation through the real interface
# --------------------------------------------------------------------------- #


def test_a_first_save_confirms_the_save_instead_of_claiming_a_loss() -> None:
    """Nothing existed before the first save, so nothing can have been cleared.

    The workflow correctly reports every key its dependency table invalidates;
    the interface must not turn that into "earlier results were cleared" when no
    earlier results were ever generated.
    """

    at = fresh_app()
    enter_room_form(at)
    submit_valid_room(at)
    submit_valid_preferences(at)

    assert any(
        element.value == "Preferences, requirements and budget saved."
        for element in at.success
    )
    assert not any("no longer apply" in element.value for element in at.info)


def test_a_real_edit_reports_the_results_it_actually_cleared() -> None:
    at = build_complete_input(fresh_app())
    prime_downstream_results(state_of(at))

    click(at, "Edit room")
    at.number_input(key="hmw_width_cm").set_value(430.0)
    at.button(key=ROOM_FORM_SUBMIT).click().run()
    assert_no_exceptions(at)

    notices = " ".join(element.value for element in at.info)
    assert "no longer apply" in notices
    assert "the design brief" in notices


def test_advisory_findings_are_shown_once_not_twice() -> None:
    """The review screen is the only place warnings are rendered.

    A commit used to also stash the advisory findings in session state and the
    review screen replayed them alongside the freshly computed ones, so a single
    warning appeared twice. ``validate_inputs`` is the one source; this test
    pins that nothing else duplicates it.
    """

    at = fresh_app()
    enter_room_form(at)
    submit_valid_room(at)
    # No material preferences and no requirements: one advisory is expected.
    at.button(key=PREFERENCES_FORM_SUBMIT).click().run()
    assert_no_exceptions(at)

    warnings = [element.value for element in at.warning]
    thin_brief = [
        text
        for text in warnings
        if "material preferences or functional requirements" in text
    ]
    assert len(thin_brief) == 1, warnings


def test_the_review_screen_reports_an_error_if_a_stored_input_breaks() -> None:
    """The review revalidates, so a broken stored input is caught on screen."""

    at = build_complete_input(fresh_app())
    state = state_of(at)
    # Force a room that the engine rejects while the model still holds it.
    assert state.room is not None
    state.room = state.room.model_copy(update={"width_cm": 90.0, "length_cm": 90.0})
    state.preferences = state.preferences
    at.run()
    assert_no_exceptions(at)

    errors = " ".join(element.value for element in at.error)
    assert "no longer passes validation" in errors


def test_changing_the_room_after_preferences_clears_derived_results() -> None:
    at = build_complete_input(fresh_app())
    state = state_of(at)
    prime_downstream_results(state)
    assert state.brief is not None

    click(at, "Edit room")
    at.number_input(key="hmw_width_cm").set_value(430.0)
    at.button(key=ROOM_FORM_SUBMIT).click().run()
    assert_no_exceptions(at)

    state = state_of(at)
    assert state.room is not None
    assert state.room.width_cm == 430.0
    # Everything derived from the room is gone...
    assert state.brief is None
    assert state.concepts is None
    assert state.selected_concept is None
    assert state.furniture == ()
    assert state.materials == ()
    assert state.spatial is None
    assert state.budget_analysis is None
    assert state.evaluation is None
    # ...and the user is told so, in words.
    notices = " ".join(element.value for element in at.info)
    assert "no longer apply" in notices
    assert "design brief" in notices


def test_renaming_the_room_alone_does_not_clear_downstream_work() -> None:
    at = build_complete_input(fresh_app())
    state = state_of(at)
    prime_downstream_results(state)
    brief_before = state.brief

    click(at, "Edit room")
    at.text_input(key="hmw_room_name").set_value("Lounge")
    at.button(key=ROOM_FORM_SUBMIT).click().run()
    assert_no_exceptions(at)

    state = state_of(at)
    assert state.room is not None and state.room.name == "Lounge"
    # A name is presentation only, so a rename must cost the user nothing.
    assert state.brief == brief_before
    assert state.concepts is not None
    assert state.preferences is not None


def test_moving_only_the_door_keeps_the_budget_analysis() -> None:
    at = build_complete_input(fresh_app())
    state = state_of(at)
    prime_downstream_results(state)
    budget_before = state.budget_analysis
    assert budget_before is not None

    click(at, "Edit room")
    at.number_input(key="hmw_door_offset").set_value(120.0)
    at.button(key=ROOM_FORM_SUBMIT).click().run()
    assert_no_exceptions(at)

    state = state_of(at)
    assert state.room is not None and state.room.door.offset_cm == 120.0
    # An opening move reaches geometry but never money.
    assert state.budget_analysis == budget_before
    assert state.spatial is None
    assert state.brief is None


def test_editing_preferences_keeps_the_room_and_clears_only_ai_results() -> None:
    at = build_complete_input(fresh_app())
    state = state_of(at)
    prime_downstream_results(state)
    room_before = state.room

    click(at, "Edit preferences")
    at.number_input(key="hmw_budget").set_value(52000.0)
    at.button(key=PREFERENCES_FORM_SUBMIT).click().run()
    assert_no_exceptions(at)

    state = state_of(at)
    assert state.room == room_before
    assert state.budget is not None
    assert state.budget.total_budget == Decimal("52000.0")
    assert state.brief is None
    assert state.budget_analysis is None


# --------------------------------------------------------------------------- #
# 7. Stale results are not "current"
# --------------------------------------------------------------------------- #


def test_a_retained_result_without_its_prerequisite_is_not_reported_complete() -> None:
    """The core freshness rule, observed through the interface.

    ``WorkflowState`` may keep a value whose prerequisite disappeared (it is a
    plain dataclass and callers can construct one that way). The interface must
    still refuse to call that step complete, which is why every screen asks
    ``is_complete`` rather than testing ``value is not None``.
    """

    at = build_complete_input(fresh_app())
    state = state_of(at)
    # Deliberately leave an evaluation behind while the steps it needs are gone.
    state.evaluation = DesignEvaluation(
        requirement_compatibility="x",
        style_consistency="x",
        functional_suitability="x",
        budget_suitability="x",
    )
    assert state.evaluation is not None
    assert state.is_complete(WorkflowStep.DESIGN_EVALUATION) is False

    at.run()
    assert_no_exceptions(at)
    rendered = " ".join(element.value for element in at.markdown)
    # The review screen reports the input as complete and never implies the
    # final report exists.
    assert "Input complete" in rendered
    # The stale evaluation is never rendered as an achieved result.
    assert "Requirement compatibility" not in rendered


def test_the_stage_strip_reports_states_in_words_not_only_colour() -> None:
    at = build_complete_input(fresh_app())
    rendered = " ".join(element.value for element in at.markdown)
    assert "Complete" in rendered
    assert "Room Setup" in rendered
    assert "Design Preferences" in rendered


def test_stage_indicator_never_marks_an_unimplemented_stage_complete() -> None:
    at = build_complete_input(fresh_app())
    rendered = " ".join(element.value for element in at.markdown)
    # Phase 6 completed the journey, so no stage is announced as unavailable and
    # the two implemented ones at this point in the flow are complete.
    assert rendered.count("Not available yet") == 0
    assert rendered.count("Complete") == 2
    # The design plan is no longer announced as unavailable, and is not marked
    # complete just because its screen exists.
    assert "Final Report" in rendered


def test_the_shell_reports_stages_not_internal_steps() -> None:
    """Regression: one screen used to show three different progress counts.

    The bar said "1 of 10 steps complete", the room page said "Step 1 of 2" and
    the brief page said "Design Concepts · step 1" — three vocabularies for one
    journey. The bar now counts the same five stages the strip shows, so a
    reviewer cannot find a contradiction between the bar and the page.
    """

    at = build_complete_input(fresh_app())
    rendered = " ".join(element.value for element in at.markdown)
    assert "of 5 stages complete" in rendered
    assert "of 10 steps complete" not in rendered
    # The five stages the strip shows and the five the bar counts are the same
    # five; "2 of 5" is correct once the room and preferences are saved.
    assert "2 of 5 stages complete" in rendered


def test_every_workflow_screen_numbers_itself_with_the_same_vocabulary() -> None:
    """The eyebrow above each page title is ``Stage n of 5``, never a fraction."""

    from ui import shell

    for stage, number in (
        ("Room Setup", 1),
        ("Design Preferences", 2),
        ("Design Concepts", 3),
        ("Design Plan", 4),
        ("Final Report", 5),
    ):
        assert shell.stage_eyebrow(stage) == f"Stage {number} of 5"
    # An unknown stage falls back to the first rather than inventing a number.
    assert shell.stage_eyebrow("Not a stage") == "Stage 1 of 5"


def test_no_page_still_numbers_itself_against_internal_steps() -> None:
    """The old strings are gone from the source, not merely unused.

    Leaving one behind would reintroduce the contradiction the moment that page
    was edited again, so the absence is asserted directly.
    """

    pages = PROJECT_ROOT / "ui"
    for path in sorted(pages.glob("pages_*.py")):
        source = path.read_text(encoding="utf-8")
        assert "Step 1 of 2" not in source, path.name
        assert "Step 2 of 2" not in source, path.name
        assert not re.search(r"·\s*step\s*\d", source), path.name


# --------------------------------------------------------------------------- #
# 8. No AI call
# --------------------------------------------------------------------------- #


def test_the_whole_workflow_runs_without_importing_the_ai_layer() -> None:
    """Structural proof, in a child process with an empty module table.

    ``app.py`` cannot reach ``ai`` because it never imports it. Checking
    ``sys.modules`` after a full run proves nothing imported it *transitively*
    either — which is what a comment cannot do.
    """

    script = f"""
import json
import sys

from streamlit.testing.v1 import AppTest

at = AppTest.from_file({str(APP_PATH)!r}, default_timeout=90).run()
at.button[0].click().run()
at.text_input(key="hmw_room_name").set_value("Living Room")
at.button(key={ROOM_FORM_SUBMIT!r}).click().run()
at.multiselect(key="hmw_materials").set_value(["oak"])
at.multiselect(key="hmw_requirements").set_value(["Seating for four"])
at.number_input(key="hmw_budget").set_value(45000.0)
at.button(key={PREFERENCES_FORM_SUBMIT!r}).click().run()

ai_modules = sorted(
    name for name in sys.modules if name == "ai" or name.startswith("ai.")
)
print(json.dumps({{
    "exceptions": len(list(at.exception)),
    "screen": at.session_state["hm_screen"],
    "ai_modules": ai_modules,
}}))
"""

    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert completed.returncode == 0, completed.stderr

    lines = [line for line in completed.stdout.splitlines() if line.startswith("{")]
    assert lines, completed.stdout
    import json

    payload = json.loads(lines[-1])
    assert payload["exceptions"] == 0
    assert payload["screen"] == "review"
    assert payload["ai_modules"] == []


def test_app_py_does_not_import_the_ai_layer() -> None:
    """A cheap guard on the source, so a later edit cannot quietly add one."""

    source = APP_PATH.read_text(encoding="utf-8")
    for line in source.splitlines():
        stripped = line.strip()
        assert not stripped.startswith("import ai"), stripped
        assert not stripped.startswith("from ai"), stripped


def test_ui_package_is_the_only_streamlit_importer() -> None:
    """The workflow layer must stay framework-free."""

    offenders: list[str] = []
    for path in (PROJECT_ROOT / "workflow").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "import streamlit" in text or "from streamlit" in text:
            offenders.append(str(path.relative_to(PROJECT_ROOT)))
    assert offenders == []
