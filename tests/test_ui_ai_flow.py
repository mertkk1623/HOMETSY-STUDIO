"""Tests for the AI-assisted brief and concept screens.

These tests protect the contract of Phase 5 / Step 4, which is mostly about
*restraint*:

* **No call without a click.** The request must be an event, not a render. If it
  ever became a render-time side effect, every unrelated rerun would spend tokens
  and overwrite results.
* **No failed call recorded as a result.** ``WorkflowState.attempt`` must leave
  the previous state untouched when the service raises.
* **No concept without a current brief.** "Current" means
  ``is_complete(BRIEF_ANALYSIS)``, not "a brief object exists".
* **No invented concept fields.** The cards show the fields ``DesignConcept``
  actually has.
* **No claim that a reference image is AI output.** The style image is the
  user's own chosen style, drawn once, captioned as a local reference.

Every AI call in this file is a fake. The four services were validated against
the real provider in Phase 5 Step 3; nothing here opens a socket, reads a
credential, or depends on the network.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from streamlit.testing.v1 import AppTest

from ai.client import AITimeoutError, AITruncatedResponseError
from models.schemas import (
    BudgetAnalysis,
    ConceptCollection,
    DesignBrief,
    DesignConcept,
    DesignEvaluation,
    DesignRecommendation,
    FurnitureRecommendation,
    SpatialValidation,
)
from ui import ai_actions
from workflow.dependencies import DataKey
from workflow.state import WorkflowState, WorkflowStep

PROJECT_ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "app.py"

ROOM_FORM_SUBMIT = "FormSubmitter:hm_room_form-Save room information"
PREFERENCES_FORM_SUBMIT = (
    "FormSubmitter:hm_preferences_form-Save preferences and budget"
)


# --------------------------------------------------------------------------- #
# Fake AI answers
# --------------------------------------------------------------------------- #


def make_brief(summary: str = "A calm living room for four people.") -> DesignBrief:
    return DesignBrief(
        summary=summary,
        functional_priorities=["Seating for four", "Reading corner"],
        constraints=["One door and one window"],
        ambiguities=["Whether existing furniture stays"],
        warnings=["The budget is tight for the stated scope"],
    )


def make_concept(name: str, direction: str) -> DesignConcept:
    return DesignConcept(
        name=name,
        description=f"{name} arranges the room around {direction}.",
        design_direction=direction,
        color_and_material_direction="Pale oak, undyed linen, oatmeal wool.",
        furniture_approach="A small number of low, long pieces.",
        functional_rationale="Seats four and keeps the window band open.",
        budget_suitability="Workable with a low piece count.",
    )


def make_concepts(
    names: tuple[str, str, str] = ("Low Horizon", "Window Bench", "Shelf Spine"),
) -> ConceptCollection:
    directions = (
        "seating pulled to the edges",
        "the window wall as a reading bench",
        "storage concentrated on one wall",
    )
    return ConceptCollection(
        concepts=[
            make_concept(name, direction)
            for name, direction in zip(names, directions)
        ]
    )


class FakeAI:
    """A stand-in for ``ui.ai_actions``'s two services.

    Records every call so a test can assert the request count, and replays a
    queued answer or exception. Mirrors the real signature so a screen that
    changes its arguments fails loudly here.
    """

    def __init__(self) -> None:
        self.brief_calls: list[dict[str, object]] = []
        self.concept_calls: list[dict[str, object]] = []
        self._brief: DesignBrief | BaseException = make_brief()
        self._concepts: ConceptCollection | BaseException = make_concepts()

    # -- configuration --------------------------------------------------- #
    def returns_brief(self, value: DesignBrief | BaseException) -> FakeAI:
        self._brief = value
        return self

    def returns_concepts(
        self, value: ConceptCollection | BaseException
    ) -> FakeAI:
        self._concepts = value
        return self

    # -- services -------------------------------------------------------- #
    def analyze_brief(self, **kwargs) -> DesignBrief:
        self.brief_calls.append(kwargs)
        if isinstance(self._brief, BaseException):
            raise self._brief
        return self._brief

    def generate_concepts(self, **kwargs) -> ConceptCollection:
        self.concept_calls.append(kwargs)
        if isinstance(self._concepts, BaseException):
            raise self._concepts
        return self._concepts

    @property
    def total_calls(self) -> int:
        return len(self.brief_calls) + len(self.concept_calls)


@pytest.fixture
def fake_ai(monkeypatch) -> FakeAI:
    """Replace both services in the bridge for the duration of one test."""

    fake = FakeAI()
    monkeypatch.setattr(ai_actions, "analyze_brief", fake.analyze_brief)
    monkeypatch.setattr(ai_actions, "generate_concepts", fake.generate_concepts)
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


def click(at: AppTest, label: str) -> AppTest:
    matches = [button for button in at.button if button.label == label]
    assert matches, f"No button labelled {label!r}. Have: {[b.label for b in at.button]}"
    matches[0].click().run()
    assert_no_exceptions(at)
    return at


def rendered_text(at: AppTest) -> str:
    return " ".join(element.value for element in at.markdown)


def build_complete_input(at: AppTest) -> AppTest:
    """Landing page to a complete, valid project input."""

    at = click(at, "Start Room Setup")
    at.text_input(key="hmw_room_name").set_value("Living Room")
    at.number_input(key="hmw_width_cm").set_value(400.0)
    at.number_input(key="hmw_length_cm").set_value(500.0)
    at.button(key=ROOM_FORM_SUBMIT).click().run()
    assert_no_exceptions(at)

    at.multiselect(key="hmw_materials").set_value(["pale oak", "linen"])
    at.multiselect(key="hmw_requirements").set_value(["Seating for four"])
    at.text_area(key="hmw_notes").set_value("Keep the window side open.")
    at.number_input(key="hmw_budget").set_value(85000.0)
    at.button(key=PREFERENCES_FORM_SUBMIT).click().run()
    assert_no_exceptions(at)
    assert at.session_state["hm_screen"] == "review"
    return at


def open_brief_screen(at: AppTest) -> AppTest:
    """Complete input, then navigate to the brief screen."""

    at = build_complete_input(at)
    return click(at, "Continue to design brief")


def open_concepts_screen(at: AppTest, fake_ai: FakeAI) -> AppTest:
    """Complete input, analyse a brief, then continue to the concepts screen."""

    at = open_brief_screen(at)
    at = click(at, "Analyse the brief")
    return click(at, "Continue to concepts")


def prime_downstream(state: WorkflowState) -> None:
    """Attach plan-stage results so selection invalidation has something to clear."""

    state.record_recommendation(
        DesignRecommendation(
            furniture=[
                FurnitureRecommendation(item_id="sofa_three_seat", quantity=1)
            ],
            materials=[],
            color_direction="Warm neutrals.",
            design_rationale="Low and quiet.",
        )
    )
    state.record_spatial(
        SpatialValidation(
            is_valid=True, boundary_violations=[], overlaps=[], warnings=[]
        )
    )
    state.record_budget_analysis(
        BudgetAnalysis(
            furniture_subtotal=Decimal("18500.00"),
            total_estimated=Decimal("18500.00"),
            remaining_budget=Decimal("66500.00"),
        )
    )
    state.record_evaluation(
        DesignEvaluation(
            requirement_compatibility="Seating for four is satisfied.",
            style_consistency="Consistent.",
            functional_suitability="Circulation is clear.",
            budget_suitability="Within budget.",
        )
    )


# --------------------------------------------------------------------------- #
# 1. The brief is never requested without a click
# --------------------------------------------------------------------------- #


def test_opening_the_brief_screen_makes_no_request(fake_ai: FakeAI) -> None:
    at = open_brief_screen(AppTest.from_file(str(APP_PATH), default_timeout=90).run())
    assert fake_ai.brief_calls == []
    assert at.session_state["hm_screen"] == "brief"
    # Nothing was invented to fill the gap.
    assert state_of(at).brief is None


def test_repeated_reruns_do_not_repeat_the_request(fake_ai: FakeAI) -> None:
    """The core protection against Streamlit re-sending on every rerun."""

    at = open_brief_screen(AppTest.from_file(str(APP_PATH), default_timeout=90).run())
    for _ in range(3):
        at.run()
        assert_no_exceptions(at)
    assert fake_ai.brief_calls == []


def test_after_a_brief_exists_a_rerun_still_makes_no_request(fake_ai: FakeAI) -> None:
    at = open_brief_screen(AppTest.from_file(str(APP_PATH), default_timeout=90).run())
    at = click(at, "Analyse the brief")
    assert len(fake_ai.brief_calls) == 1

    for _ in range(3):
        at.run()
        assert_no_exceptions(at)
    assert len(fake_ai.brief_calls) == 1


def test_the_button_click_makes_exactly_one_request(fake_ai: FakeAI) -> None:
    at = open_brief_screen(AppTest.from_file(str(APP_PATH), default_timeout=90).run())
    at = click(at, "Analyse the brief")
    assert len(fake_ai.brief_calls) == 1


def test_the_request_receives_the_saved_input(fake_ai: FakeAI) -> None:
    at = open_brief_screen(AppTest.from_file(str(APP_PATH), default_timeout=90).run())
    at = click(at, "Analyse the brief")

    call = fake_ai.brief_calls[0]
    room = call["room"]
    budget = call["budget"]
    assert room.name == "Living Room"
    assert room.width_cm == 400.0
    assert room.length_cm == 500.0
    assert budget.total_budget == Decimal("85000.0")
    assert call["preferences"].style.value == "Japandi"
    assert call["requirements"].functional_requirements == ["Seating for four"]


# --------------------------------------------------------------------------- #
# 2. A successful brief is stored and shown
# --------------------------------------------------------------------------- #


def test_a_successful_brief_is_stored_and_rendered(fake_ai: FakeAI) -> None:
    at = open_brief_screen(AppTest.from_file(str(APP_PATH), default_timeout=90).run())
    at = click(at, "Analyse the brief")

    state = state_of(at)
    assert state.brief is not None
    assert state.is_complete(WorkflowStep.BRIEF_ANALYSIS) is True

    rendered = rendered_text(at)
    assert "A calm living room for four people." in rendered
    assert "Seating for four" in rendered
    assert "One door and one window" in rendered
    # Every section of the model is presented, including the awkward ones.
    assert "Open questions" in rendered
    assert "Risks worth knowing" in rendered

    assert any("ready" in element.value.lower() for element in at.success)


def test_the_brief_screen_escapes_model_text(fake_ai: FakeAI) -> None:
    """AI output is untrusted, so markup in it must not become markup."""

    fake_ai.returns_brief(make_brief("<script>alert('x')</script> is the plan."))
    at = open_brief_screen(AppTest.from_file(str(APP_PATH), default_timeout=90).run())
    at = click(at, "Analyse the brief")

    rendered = rendered_text(at)
    assert "&lt;script&gt;" in rendered
    assert "<script>alert" not in rendered


# --------------------------------------------------------------------------- #
# 3. Failures never become results
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (AITimeoutError("raw provider wording"), "did not answer in time"),
        (
            AITruncatedResponseError("raw provider wording"),
            "cut off before it finished",
        ),
    ],
)
def test_a_failed_brief_is_reported_and_stores_nothing(
    fake_ai: FakeAI, error: BaseException, expected: str
) -> None:
    fake_ai.returns_brief(error)
    at = open_brief_screen(AppTest.from_file(str(APP_PATH), default_timeout=90).run())
    at = click(at, "Analyse the brief")

    state = state_of(at)
    assert state.brief is None
    assert state.is_complete(WorkflowStep.BRIEF_ANALYSIS) is False

    errors = " ".join(element.value for element in at.error)
    assert expected in errors
    # No traceback, no exception element, no raw provider text.
    assert_no_exceptions(at)
    assert "Traceback" not in errors
    assert "raw provider wording" not in errors
    assert AITimeoutError.__name__ not in errors
    assert AITruncatedResponseError.__name__ not in errors

    # The button remains, so the user can retry deliberately.
    assert any(button.label == "Analyse the brief" for button in at.button)


def test_a_failure_keeps_the_previous_valid_brief(fake_ai: FakeAI) -> None:
    """Rebuilding must not destroy a good brief when the retry fails."""

    at = open_brief_screen(AppTest.from_file(str(APP_PATH), default_timeout=90).run())
    at = click(at, "Analyse the brief")
    assert state_of(at).brief is not None

    fake_ai.returns_brief(AITimeoutError("did not answer"))
    at = click(at, "Rebuild the brief")

    state = state_of(at)
    assert state.brief is not None
    assert state.is_complete(WorkflowStep.BRIEF_ANALYSIS) is True
    assert len(fake_ai.brief_calls) == 2


def test_a_failed_regeneration_keeps_the_previous_concepts(fake_ai: FakeAI) -> None:
    at = open_concepts_screen(
        AppTest.from_file(str(APP_PATH), default_timeout=90).run(), fake_ai
    )
    at = click(at, "Generate three concepts")
    before = state_of(at).concepts
    assert before is not None

    fake_ai.returns_concepts(AITimeoutError("did not answer"))
    at = click(at, "Generate concepts again")
    assert state_of(at).concepts == before
    assert state_of(at).is_complete(WorkflowStep.CONCEPT_GENERATION) is True


def test_a_selection_is_never_assigned_to_a_concept_from_an_older_set(
    fake_ai: FakeAI,
) -> None:
    """``select_concept`` refuses a concept that is not in the current set."""

    at = open_concepts_screen(
        AppTest.from_file(str(APP_PATH), default_timeout=90).run(), fake_ai
    )
    at = click(at, "Generate three concepts")
    state = state_of(at)
    assert state.concepts is not None
    stale = make_concept("From An Older Set", "a set that no longer exists")

    from workflow.state import WorkflowError

    with pytest.raises(WorkflowError):
        state.select_concept(stale)
    assert state.selected_concept is None


def test_rebuilding_the_brief_clears_the_concepts_built_on_the_old_one(
    fake_ai: FakeAI,
) -> None:
    """A new brief is upstream of the concepts, so they cannot survive it."""

    at = open_concepts_screen(
        AppTest.from_file(str(APP_PATH), default_timeout=90).run(), fake_ai
    )
    at = click(at, "Generate three concepts")
    at = click(at, "Select this concept")
    assert state_of(at).selected_concept is not None

    at = click(at, "Back to the brief")
    fake_ai.returns_brief(make_brief("A revised brief with a different emphasis."))
    at = click(at, "Rebuild the brief")

    state = state_of(at)
    assert state.brief is not None
    assert state.brief.summary.startswith("A revised brief")
    assert state.concepts is None
    assert state.selected_concept is None
    assert state.is_complete(WorkflowStep.CONCEPT_GENERATION) is False


# --------------------------------------------------------------------------- #
# 4. Concepts need a current brief
# --------------------------------------------------------------------------- #


def test_the_concepts_screen_refuses_to_open_without_a_brief(fake_ai: FakeAI) -> None:
    at = build_complete_input(AppTest.from_file(str(APP_PATH), default_timeout=90).run())
    # Jump straight there by hand, as a stale link or an edited session would.
    at.session_state["hm_screen"] = "concepts"
    at.run()
    assert_no_exceptions(at)

    assert at.session_state["hm_screen"] == "brief"
    assert fake_ai.brief_calls == []
    assert fake_ai.concept_calls == []


def test_the_concepts_screen_refuses_a_brief_whose_input_changed(
    fake_ai: FakeAI,
) -> None:
    """A stored brief is not a current one once the input it came from moved."""

    at = open_brief_screen(AppTest.from_file(str(APP_PATH), default_timeout=90).run())
    at = click(at, "Analyse the brief")

    # Edit the budget, which invalidates the brief and everything after it.
    at.session_state["hm_screen"] = "preferences"
    at.run()
    at.number_input(key="hmw_budget").set_value(60000.0)
    at.button(key=PREFERENCES_FORM_SUBMIT).click().run()
    assert_no_exceptions(at)

    state = state_of(at)
    assert state.brief is None
    assert state.is_complete(WorkflowStep.BRIEF_ANALYSIS) is False

    at.session_state["hm_screen"] = "concepts"
    at.run()
    assert_no_exceptions(at)
    assert at.session_state["hm_screen"] == "brief"
    assert fake_ai.concept_calls == []


def test_concepts_are_not_generated_without_a_click(fake_ai: FakeAI) -> None:
    at = open_concepts_screen(
        AppTest.from_file(str(APP_PATH), default_timeout=90).run(), fake_ai
    )
    assert fake_ai.concept_calls == []
    for _ in range(3):
        at.run()
        assert_no_exceptions(at)
    assert fake_ai.concept_calls == []


# --------------------------------------------------------------------------- #
# 5. Exactly three concepts, rendered from the model's own fields
# --------------------------------------------------------------------------- #


def test_the_concepts_screen_shows_exactly_three_concepts(fake_ai: FakeAI) -> None:
    at = open_concepts_screen(
        AppTest.from_file(str(APP_PATH), default_timeout=90).run(), fake_ai
    )
    at = click(at, "Generate three concepts")

    state = state_of(at)
    assert state.concepts is not None
    assert len(state.concepts.concepts) == 3
    assert state.is_complete(WorkflowStep.CONCEPT_GENERATION) is True

    rendered = rendered_text(at)
    for name in ("Low Horizon", "Window Bench", "Shelf Spine"):
        assert name in rendered
    # One select button per concept, and no selection yet.
    assert sum(b.label == "Select this concept" for b in at.button) == 3


def test_the_concept_card_shows_every_model_field(fake_ai: FakeAI) -> None:
    at = open_concepts_screen(
        AppTest.from_file(str(APP_PATH), default_timeout=90).run(), fake_ai
    )
    at = click(at, "Generate three concepts")
    rendered = rendered_text(at)

    for label in (
        "Description",
        "Design direction",
        "Colour and material direction",
        "Furniture approach",
        "Functional rationale",
        "Budget suitability",
    ):
        assert label in rendered

    # The model had no such field, so the screen must not invent one.
    assert "Style characteristics" not in rendered
    assert "Style characteristics" not in rendered.lower()


def test_a_concept_set_of_the_wrong_size_is_never_stored(fake_ai: FakeAI) -> None:
    """The model's own validator refuses two or four concepts.

    A fake that returns such a value cannot exist as a ``ConceptCollection``, so
    the service would have raised during validation. This test pins that the
    screen does not paper over a rejected answer.
    """

    with pytest.raises(Exception):
        ConceptCollection(
            concepts=[make_concept("Only One", "a single idea")]
        )


# --------------------------------------------------------------------------- #
# 6. Reference images: shown once, described honestly
# --------------------------------------------------------------------------- #


def test_the_reference_image_is_the_users_chosen_style(
    fake_ai: FakeAI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The strip must show the image belonging to the user's own style.

    ``AppTest`` reports the image as a content-hashed mock URL, which cannot be
    traced back to a file, so the argument handed to ``st.image`` is recorded
    instead. The script runs in this interpreter, so the patch is visible to it.
    """

    import streamlit

    from ui import references

    shown: list[str] = []
    real_image = streamlit.image

    def recording_image(image, *args, **kwargs):
        shown.append(str(image))
        return real_image(image, *args, **kwargs)

    monkeypatch.setattr(streamlit, "image", recording_image)

    at = open_concepts_screen(
        AppTest.from_file(str(APP_PATH), default_timeout=90).run(), fake_ai
    )
    # The preferences screen draws every style card, so start counting only from
    # the concepts screen, where exactly one reference image belongs.
    shown.clear()
    at = click(at, "Generate three concepts")

    library = references.load_references()
    style = state_of(at).preferences.style
    expected = library.image_for_style(style)
    assert expected is not None
    # Every reference image drawn after arriving here is the user's own style;
    # the page may be drawn more than once by the rerun the click triggers.
    assert shown, "the reference strip drew no image"
    assert set(shown) == {str(expected)}
    assert len(at.get("image")) == 1


def test_the_reference_is_captioned_as_local_and_not_ai_output(
    fake_ai: FakeAI,
) -> None:
    at = open_concepts_screen(
        AppTest.from_file(str(APP_PATH), default_timeout=90).run(), fake_ai
    )
    at = click(at, "Generate three concepts")
    rendered = rendered_text(at).lower()

    assert "reference" in rendered
    assert "not generated for these concepts" in rendered
    assert "not shown to the ai" in rendered


def test_one_reference_image_is_not_reused_three_times(fake_ai: FakeAI) -> None:
    """The style image belongs to the user's preference, not to each concept."""

    at = open_concepts_screen(
        AppTest.from_file(str(APP_PATH), default_timeout=90).run(), fake_ai
    )
    at = click(at, "Generate three concepts")
    # One reference strip, not one image per card.
    assert len(at.get("image")) == 1


# --------------------------------------------------------------------------- #
# 7. Selection
# --------------------------------------------------------------------------- #


def test_selecting_a_concept_stores_it(fake_ai: FakeAI) -> None:
    at = open_concepts_screen(
        AppTest.from_file(str(APP_PATH), default_timeout=90).run(), fake_ai
    )
    at = click(at, "Generate three concepts")
    at = click(at, "Select this concept")

    state = state_of(at)
    assert state.selected_concept is not None
    assert state.selected_concept.name == "Low Horizon"
    assert state.is_complete(WorkflowStep.CONCEPT_SELECTION) is True
    assert any("selected" in element.value.lower() for element in at.success)


def test_the_selected_concept_is_marked_in_words_not_only_colour(
    fake_ai: FakeAI,
) -> None:
    at = open_concepts_screen(
        AppTest.from_file(str(APP_PATH), default_timeout=90).run(), fake_ai
    )
    at = click(at, "Generate three concepts")
    at = click(at, "Select this concept")

    rendered = rendered_text(at)
    assert "Selected" in rendered
    # The chosen card offers a disabled confirmation button, so the action is
    # visibly complete rather than simply absent.
    disabled = [button for button in at.button if button.label == "Selected"]
    assert disabled
    assert sum(b.label == "Select this concept" for b in at.button) == 2


def test_changing_the_selection_clears_the_plan_results(fake_ai: FakeAI) -> None:
    """The invalidation rule, observed through the interface."""

    at = open_concepts_screen(
        AppTest.from_file(str(APP_PATH), default_timeout=90).run(), fake_ai
    )
    at = click(at, "Generate three concepts")
    at = click(at, "Select this concept")

    state = state_of(at)
    prime_downstream(state)
    assert state.is_complete(WorkflowStep.DESIGN_EVALUATION) is True
    assert state.furniture

    at.run()
    assert_no_exceptions(at)
    # Pick a different concept: the second card's button.
    others = [b for b in at.button if b.label == "Select this concept"]
    assert len(others) == 2
    others[0].click().run()
    assert_no_exceptions(at)

    state = state_of(at)
    assert state.selected_concept is not None
    assert state.selected_concept.name != "Low Horizon"
    # Everything derived from the old concept is gone; the concepts themselves
    # and the brief they came from survive.
    assert state.furniture == ()
    assert state.spatial is None
    assert state.budget_analysis is None
    assert state.evaluation is None
    assert state.concepts is not None
    assert state.brief is not None


def test_the_old_selection_is_never_attached_to_the_new_concepts(
    fake_ai: FakeAI,
) -> None:
    at = open_concepts_screen(
        AppTest.from_file(str(APP_PATH), default_timeout=90).run(), fake_ai
    )
    at = click(at, "Generate three concepts")
    at = click(at, "Select this concept")
    assert state_of(at).selected_concept is not None

    fake_ai.returns_concepts(
        make_concepts(("Quiet Oak", "Soft Contrast", "Warm Studio"))
    )
    at = click(at, "Generate concepts again")

    state = state_of(at)
    assert state.concepts is not None
    assert state.concepts.concepts[0].name == "Quiet Oak"
    # The previous choice belonged to the previous set and was discarded.
    assert state.selected_concept is None
    assert state.is_complete(WorkflowStep.CONCEPT_SELECTION) is False


def test_regenerating_an_identical_set_keeps_a_still_valid_selection(
    fake_ai: FakeAI,
) -> None:
    """Nothing changed, so nothing is thrown away.

    ``record_concepts`` returns early when the new collection equals the stored
    one, so the selection it invalidates is not touched. That is the correct
    outcome: the user's choice still belongs to the set on screen.
    """

    at = open_concepts_screen(
        AppTest.from_file(str(APP_PATH), default_timeout=90).run(), fake_ai
    )
    at = click(at, "Generate three concepts")
    at = click(at, "Select this concept")
    before = state_of(at).selected_concept

    at = click(at, "Generate concepts again")

    state = state_of(at)
    assert state.concepts is not None
    assert len(state.concepts.concepts) == 3
    assert state.selected_concept == before
    assert state.is_complete(WorkflowStep.CONCEPT_SELECTION) is True


# --------------------------------------------------------------------------- #
# 8. Navigation
# --------------------------------------------------------------------------- #


def test_the_brief_screen_offers_no_way_forward_without_a_brief(
    fake_ai: FakeAI,
) -> None:
    at = open_brief_screen(AppTest.from_file(str(APP_PATH), default_timeout=90).run())
    labels = {button.label for button in at.button}
    assert "Continue to concepts" not in labels
    assert "Continue to concepts unlocks once a current brief exists." in (
        rendered_text(at)
    )


def test_the_brief_screen_only_offers_buttons_that_work(fake_ai: FakeAI) -> None:
    at = open_brief_screen(AppTest.from_file(str(APP_PATH), default_timeout=90).run())
    labels = {button.label for button in at.button}
    assert labels <= {
        "Analyse the brief",
        "Edit input",
        "Start a new project",
        "Back to overview",
    }


def test_a_concept_can_be_selected_then_the_stage_completes(fake_ai: FakeAI) -> None:
    at = open_concepts_screen(
        AppTest.from_file(str(APP_PATH), default_timeout=90).run(), fake_ai
    )
    at = click(at, "Generate three concepts")
    at = click(at, "Select this concept")

    rendered = rendered_text(at)
    # The selection is confirmed on the screen and the next stage is now
    # reachable, rather than being described as unbuilt.
    assert "Concept selected" in rendered
    # And the screen does not let the concept's prose pass for a layout spec: a
    # named wall is passed through, but the position is still computed from the
    # furniture's dimensions. The note is HTML-escaped by the theme helper, so
    # the apostrophes arrive as entities.
    assert "A concept describes a direction in words" in rendered
    assert "passed to the layout engine as a preference" in rendered
    assert (
        "calculated from the furniture&#x27;s real dimensions" in rendered
    )
    labels = {button.label for button in at.button}
    assert "Continue to the design plan" in labels
    assert sum(b.label == "Select this concept" for b in at.button) == 2
    # The plan itself needs the advisor, so it is not claimed as finished.
    assert "Design Plan" in rendered


# --------------------------------------------------------------------------- #
# 9. Failure copy
# --------------------------------------------------------------------------- #


def test_every_failure_category_has_readable_copy() -> None:
    categories = [
        "authentication_error",
        "rate_limit",
        "timeout",
        "network_error",
        "truncated_response",
        "server_error",
        "invalid_json",
        "schema_validation_error",
        "correction_failed",
        "empty_response",
        "request_error",
    ]

    class Fake(Exception):
        def __init__(self, category: str) -> None:
            self.category = category
            super().__init__("provider detail that must not be shown")

    for category in categories:
        message = ai_actions.failure_message(Fake(category))
        assert message
        # Never the provider's own words, never a token or a URL.
        assert "provider detail" not in message
        assert "http" not in message.lower()
        assert "bearer" not in message.lower()


def test_a_configuration_failure_explains_how_to_fix_it() -> None:
    from ai.config import AIConfigurationError

    message = ai_actions.failure_message(AIConfigurationError("key missing"))
    assert ai_actions.SECRET_NAME in message
    assert "key missing" not in message


def test_an_unclassified_failure_gets_the_generic_sentence() -> None:
    message = ai_actions.failure_message(RuntimeError("something odd"))
    assert "nothing was saved" in message.lower()
    assert "something odd" not in message


def test_failure_copy_never_includes_the_credential(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEPLOY_API_KEY", "test-key-should-never-appear")

    class Fake(Exception):
        category = "authentication_error"

    message = ai_actions.failure_message(Fake())
    assert "test-key-should-never-appear" not in message


# --------------------------------------------------------------------------- #
# 10. The AI-free start of the journey still works
# --------------------------------------------------------------------------- #


def test_the_deterministic_input_flow_never_touches_the_ai_layer(
    fake_ai: FakeAI,
) -> None:
    """Reaching the review screen must not call a service.

    The *structural* half of this claim — that the ``ai`` package is never even
    imported on this path — is asserted in a child process by
    ``test_ui_app.test_the_whole_workflow_runs_without_importing_the_ai_layer``.
    It cannot be asserted here, because this module imports the client's error
    classes at import time.
    """

    at = build_complete_input(AppTest.from_file(str(APP_PATH), default_timeout=90).run())
    assert at.session_state["hm_screen"] == "review"
    assert fake_ai.total_calls == 0
    # And the review screen does not offer the concept screen yet either.
    labels = {button.label for button in at.button}
    assert "Continue to concepts" not in labels


def test_the_whole_new_flow_renders_without_an_exception(fake_ai: FakeAI) -> None:
    at = open_concepts_screen(
        AppTest.from_file(str(APP_PATH), default_timeout=90).run(), fake_ai
    )
    at = click(at, "Generate three concepts")
    at = click(at, "Select this concept")
    assert_no_exceptions(at)
    assert at.session_state["hm_screen"] == "concepts"


def test_the_stage_strip_reports_the_concepts_stage_as_available(
    fake_ai: FakeAI,
) -> None:
    at = open_concepts_screen(
        AppTest.from_file(str(APP_PATH), default_timeout=90).run(), fake_ai
    )
    at = click(at, "Generate three concepts")
    at = click(at, "Select this concept")

    rendered = rendered_text(at)
    assert "Design Concepts" in rendered
    assert "Complete" in rendered
    # Phase 6 completed the journey, so every stage now has a screen.
    assert rendered.count("Not available yet") == 0


def test_data_keys_cleared_by_a_selection_match_the_dependency_table() -> None:
    """The screen relies on the table, so the table's row is pinned here too."""

    from workflow.dependencies import invalidated_by

    dropped = invalidated_by(DataKey.SELECTED_CONCEPT)
    assert dropped == (
        DataKey.FURNITURE,
        DataKey.MATERIALS,
        DataKey.SPATIAL,
        DataKey.BUDGET_ANALYSIS,
        DataKey.EVALUATION,
    )
