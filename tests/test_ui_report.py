"""The Final Report step: finalization and the PDF download.

Two layers are tested together because that is how they will be used:

* the deterministic seam in ``ui/report.py`` — when a report may exist, and what
  happens when finalizing or writing the file fails;
* the screen itself under ``AppTest`` — which button is offered, that a rerun
  does not regenerate the file, and that the download carries a safe filename.

Report generation is replaced by a stub in most tests, so the suite asserts the
*contract* (one call per click, results untouched on failure) rather than
ReportLab behaviour. ``tests/test_report_generator.py`` covers the real document.
No test here calls the AI layer or opens a socket.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from streamlit.testing.v1 import AppTest

from core.budget_engine import compute_budget
from core.report_generator import ReportGenerationError
from models.schemas import (
    BudgetInput,
    ConceptCollection,
    DesignBrief,
    DesignConcept,
    DesignEvaluation,
    DesignRecommendation,
    FurnitureRecommendation,
    ProjectResult,
    SpatialValidation,
)
from ui import layout, references, report as report_view
from ui.pages_report import ARTIFACT_KEY
from workflow.state import WorkflowState, WorkflowStep

PROJECT_ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "app.py"

ROOM_FORM_SUBMIT = "FormSubmitter:hm_room_form-Save room information"
PREFERENCES_FORM_SUBMIT = (
    "FormSubmitter:hm_preferences_form-Save preferences and budget"
)

GENERATE_LABEL = "Generate the PDF report"
REGENERATE_LABEL = "Generate the report again"
DOWNLOAD_LABEL = "Download the PDF report"


# --------------------------------------------------------------------------- #
# Fixtures
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


def make_evaluation() -> DesignEvaluation:
    return DesignEvaluation(
        requirement_compatibility="Seating for four is met.",
        style_consistency="Consistent with the chosen direction.",
        functional_suitability="The path from door to window stays clear.",
        budget_suitability="Within the stated budget.",
        limitations=["The reading corner is only implied"],
        recommendations=["Add a floor lamp beside the armchair"],
    )


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


def button_labels(at: AppTest) -> set[str]:
    return {button.label for button in at.button}


def download_labels(at: AppTest) -> list[str]:
    return [widget.label for widget in at.get("download_button")]


def click(at: AppTest, label: str) -> AppTest:
    matches = [button for button in at.button if button.label == label]
    assert matches, f"No button labelled {label!r}. Have: {sorted(button_labels(at))}"
    matches[0].click().run()
    assert_no_exceptions(at)
    return at


def fresh_app() -> AppTest:
    return AppTest.from_file(str(APP_PATH), default_timeout=90).run()


def build_complete_input(
    at: AppTest, *, budget: float = 85000.0
) -> AppTest:
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


def prime_through_evaluation(
    at: AppTest, *, budget: float = 85000.0
) -> AppTest:
    """Every step before the report, including the AI-produced evaluation.

    The AI services are not called: the models' answers are recorded directly,
    which is what the screens themselves do after a successful call.
    """

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
    state.record_recommendation(
        DesignRecommendation(
            furniture=[
                FurnitureRecommendation(item_id="sofa_three_seat", quantity=1),
                FurnitureRecommendation(item_id="coffee_table", quantity=1),
            ],
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
    state.record_evaluation(make_evaluation())
    at.run()
    assert_no_exceptions(at)
    return at


def open_report_screen(at: AppTest, **kwargs) -> AppTest:
    at = prime_through_evaluation(at, **kwargs)
    at.session_state["hm_screen"] = "report"
    at.run()
    assert_no_exceptions(at)
    return at


# --------------------------------------------------------------------------- #
# A stub generator, so "how many PDFs were written" is countable
# --------------------------------------------------------------------------- #


class FakeGenerator:
    """Stands in for ``core.report_generator.generate_report``.

    ``base_dir`` is a temporary directory, so the suite never writes into the
    project's real ``output/reports/``: a test run must not leave files a user
    could mistake for a generated report.
    """

    def __init__(self, base_dir) -> None:
        self.base_dir = base_dir
        self.calls: list[dict[str, object]] = []
        self.failure: BaseException | None = None

    def fails_with(self, error: BaseException) -> FakeGenerator:
        self.failure = error
        return self

    def __call__(self, result, *, catalog, budget, output_dir=None, generated_at=None):
        from pathlib import Path

        from core.report_generator import report_filename

        self.calls.append(
            {
                "result": result,
                "catalog": catalog,
                "budget": budget,
                "output_dir": output_dir,
            }
        )
        if self.failure is not None:
            raise self.failure
        directory = Path(output_dir or self.base_dir)
        directory.mkdir(parents=True, exist_ok=True)
        # Named exactly as the real generator names it, so the test sees the
        # same safe filename the user would download.
        path = directory / report_filename(result.room.name)
        path.write_bytes(b"%PDF-1.4\n% stub report\n")
        return path

    @property
    def call_count(self) -> int:
        return len(self.calls)


@pytest.fixture
def generator(monkeypatch, tmp_path) -> FakeGenerator:
    fake = FakeGenerator(tmp_path)
    monkeypatch.setattr(report_view.report_generator, "generate_report", fake)
    return fake


# --------------------------------------------------------------------------- #
# 1. The seam: when a report may exist
# --------------------------------------------------------------------------- #


def test_can_finalize_requires_every_earlier_step() -> None:
    at = fresh_app()
    at = build_complete_input(at)
    at.session_state["hm_workflow_entered"] = True
    state = state_of(at)

    # Inputs alone are not a project.
    assert report_view.can_finalize(state) is False

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
            furniture=[FurnitureRecommendation(item_id="sofa_three_seat", quantity=1)],
            materials=[],
            color_direction="Warm neutrals.",
            design_rationale="Low pieces.",
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
    # Still missing the evaluation, which is the last prerequisite.
    assert report_view.can_finalize(state) is False
    state.record_evaluation(make_evaluation())
    assert report_view.can_finalize(state) is True


def test_a_report_before_the_evaluation_is_refused(generator) -> None:
    at = open_report_screen(fresh_app())
    state = state_of(at)
    # The screen itself refuses to open without the evaluation, so drop back.
    at.session_state["hm_screen"] = "report"
    state.evaluation = None
    at.run()
    assert_no_exceptions(at)

    assert at.session_state["hm_screen"] != "report"
    assert generator.call_count == 0
    assert state.result is None


# --------------------------------------------------------------------------- #
# 2. Finalization is the only thing that creates a result
# --------------------------------------------------------------------------- #


def test_finalize_is_the_only_creator_of_a_project_result() -> None:
    at = open_report_screen(fresh_app())
    state = state_of(at)
    assert state.result is None
    assert state.is_complete(WorkflowStep.FINAL_RESULT) is False

    result = state.finalize()
    assert isinstance(result, ProjectResult)
    assert state.result is result
    assert state.is_complete(WorkflowStep.FINAL_RESULT) is True


def test_the_final_result_carries_the_advisor_and_layout_data() -> None:
    """The report works from the model alone, so nothing may be left behind."""

    at = open_report_screen(fresh_app())
    state = state_of(at)
    result = state.finalize()

    assert result.recommendations == list(state.furniture)
    assert result.placement is state.placement
    assert result.color_direction == state.color_direction
    assert result.design_rationale == state.design_rationale
    assert result.materials == list(state.materials)
    assert result.budget_analysis is state.budget_analysis
    assert result.evaluation is state.evaluation
    assert result.spatial_validation is state.spatial


def test_the_screen_offers_the_button_only_when_the_project_is_complete() -> None:
    at = fresh_app()
    at = build_complete_input(at)
    at.session_state["hm_screen"] = "report"
    at.run()
    assert_no_exceptions(at)
    # Incomplete project: the screen explains what is outstanding instead.
    assert at.session_state["hm_screen"] != "report"


def test_the_complete_project_shows_the_generate_button() -> None:
    at = open_report_screen(fresh_app())
    assert GENERATE_LABEL in button_labels(at)
    assert REGENERATE_LABEL not in button_labels(at)
    assert download_labels(at) == []
    # Nothing has been finalized or written yet.
    assert state_of(at).result is None


# --------------------------------------------------------------------------- #
# 3. One click, one PDF
# --------------------------------------------------------------------------- #


def test_generating_finalizes_and_stores_an_artifact(generator) -> None:
    at = open_report_screen(fresh_app())
    at = click(at, GENERATE_LABEL)

    state = state_of(at)
    assert generator.call_count == 1
    assert state.result is not None
    assert state.is_complete(WorkflowStep.FINAL_RESULT) is True

    artifact = at.session_state[ARTIFACT_KEY]
    assert artifact.result is state.result
    assert artifact.path.exists()
    assert artifact.filename.endswith(".pdf")
    assert generator.calls[0]["result"] is state.result


def test_the_download_button_is_offered_after_generation(generator) -> None:
    at = open_report_screen(fresh_app())
    at = click(at, GENERATE_LABEL)

    assert download_labels(at) == [DOWNLOAD_LABEL]
    assert REGENERATE_LABEL in button_labels(at)
    assert GENERATE_LABEL not in button_labels(at)
    assert "Report ready" in page_text(at)


def test_the_download_filename_is_safe_and_derived_from_the_room(generator) -> None:
    at = open_report_screen(fresh_app())
    state = state_of(at)
    state.room = state.room.model_copy(update={"name": "Şişli Salonu — Köşe"})
    at.run()
    assert_no_exceptions(at)

    at = click(at, GENERATE_LABEL)

    # The artifact carries the name the download button is given. The Turkish
    # letters are folded, so the file can be saved anywhere.
    artifact = at.session_state[ARTIFACT_KEY]
    assert artifact.filename == "hometsy-sisli-salonu-kose-report.pdf"
    assert artifact.path.name == artifact.filename
    assert download_labels(at) == [DOWNLOAD_LABEL]


def test_the_download_widget_receives_a_pdf_payload(generator) -> None:
    at = open_report_screen(fresh_app())
    at = click(at, GENERATE_LABEL)

    artifact = at.session_state[ARTIFACT_KEY]
    widget = at.get("download_button")[0]
    # A media URL means Streamlit accepted a payload, rather than the button
    # rendering without anything to download.
    assert widget.proto.url.endswith(".pdf"), widget.proto.url
    assert artifact.path.read_bytes().startswith(b"%PDF-")


def test_a_rerun_does_not_generate_a_second_pdf(generator) -> None:
    at = open_report_screen(fresh_app())
    at = click(at, GENERATE_LABEL)
    assert generator.call_count == 1

    path = at.session_state[ARTIFACT_KEY].path
    before = path.read_bytes()

    at.run()
    assert_no_exceptions(at)
    at.run()
    assert_no_exceptions(at)

    # Streamlit reruns on every widget interaction; none of them is a request
    # for another report.
    assert generator.call_count == 1
    assert path.read_bytes() == before
    assert download_labels(at) == [DOWNLOAD_LABEL]


def test_generating_again_replaces_the_file_on_purpose(generator) -> None:
    at = open_report_screen(fresh_app())
    at = click(at, GENERATE_LABEL)
    first = at.session_state[ARTIFACT_KEY]

    at = click(at, REGENERATE_LABEL)
    assert generator.call_count == 2
    second = at.session_state[ARTIFACT_KEY]
    assert second is not first
    assert second.result is state_of(at).result


# --------------------------------------------------------------------------- #
# 4. A failed PDF keeps the project
# --------------------------------------------------------------------------- #


def test_a_pdf_failure_keeps_the_finalized_result(generator) -> None:
    generator.fails_with(
        ReportGenerationError(
            "The PDF could not be produced. The project data is unchanged, so "
            "the report can be generated again."
        )
    )
    at = open_report_screen(fresh_app())
    at = click(at, GENERATE_LABEL)

    state = state_of(at)
    # Finalization succeeded before generation failed, and it is not undone.
    assert state.result is not None
    assert state.is_complete(WorkflowStep.FINAL_RESULT) is True
    assert at.session_state.get(ARTIFACT_KEY) is None
    assert download_labels(at) == []

    errors = " ".join(element.value for element in at.error)
    assert "project data is unchanged" in errors
    assert "can be generated again" in errors


def test_a_pdf_failure_leaves_the_button_available(generator) -> None:
    generator.fails_with(ReportGenerationError("The PDF could not be produced."))
    at = open_report_screen(fresh_app())
    at = click(at, GENERATE_LABEL)

    assert GENERATE_LABEL in button_labels(at)

    # The failure is not sticky: the next click succeeds without any repair.
    generator.failure = None
    at = click(at, GENERATE_LABEL)
    assert generator.call_count == 2
    assert download_labels(at) == [DOWNLOAD_LABEL]


def test_an_unexpected_error_is_reported_without_a_traceback(generator) -> None:
    generator.fails_with(OSError("disk quota exceeded at C:\\secret\\path"))
    at = open_report_screen(fresh_app())
    at = click(at, GENERATE_LABEL)

    assert_no_exceptions(at)
    text = page_text(at)
    assert "could not be generated" in text
    assert "disk quota" not in text
    assert "secret" not in text
    assert state_of(at).result is not None


def test_the_failure_message_never_echoes_provider_or_path_details() -> None:
    message = report_view.report_error_message(
        RuntimeError("401 Unauthorized https://api.example/v1 key sk-abc123")
    )
    assert "sk-abc123" not in message
    assert "api.example" not in message
    assert "401" not in message

    # A deliberate, user-facing message is passed through unchanged.
    explicit = report_view.report_error_message(
        ReportGenerationError("The report font is missing from assets/fonts.")
    )
    assert explicit == "The report font is missing from assets/fonts."


# --------------------------------------------------------------------------- #
# 5. A stale artifact is withdrawn, never offered
# --------------------------------------------------------------------------- #


def test_an_invalidation_withdraws_the_artifact_even_when_the_screen_redirects(
    generator,
) -> None:
    at = open_report_screen(fresh_app())
    at = click(at, GENERATE_LABEL)
    assert download_labels(at) == [DOWNLOAD_LABEL]

    state = state_of(at)
    # Any upstream change invalidates the stored result and the steps after it,
    # so the screen sends the user back rather than drawing the report step.
    state.set_budget(BudgetInput(total_budget=Decimal("99000.00")))
    at.run()
    assert_no_exceptions(at)

    assert state.result is None
    assert at.session_state.get(ARTIFACT_KEY) is None
    assert at.session_state["hm_screen"] != "report"
    assert download_labels(at) == []


def test_a_stale_artifact_is_withdrawn_with_an_explanation(generator) -> None:
    """The case where the project is still complete but the result was rebuilt.

    ``WorkflowState`` clears ``result`` on every invalidation, so a complete
    project with a replaced result object is the shape a stale file takes once
    the user has re-run the steps. The screen must not offer it.
    """

    at = open_report_screen(fresh_app())
    at = click(at, GENERATE_LABEL)
    assert download_labels(at) == [DOWNLOAD_LABEL]

    state = state_of(at)
    state.result = state.build_result()
    at.run()
    assert_no_exceptions(at)

    assert at.session_state.get(ARTIFACT_KEY) is None
    assert download_labels(at) == []
    text = page_text(at)
    assert "Report out of date" in text
    assert "has been withdrawn" in text
    # The project is still complete, so it can be rebuilt in one click.
    assert state.is_complete(WorkflowStep.FINAL_RESULT) is True
    assert GENERATE_LABEL in button_labels(at)


def test_the_same_result_object_is_what_makes_a_report_current() -> None:
    """Identity, not content, because invalidation clears ``state.result``."""

    at = open_report_screen(fresh_app())
    state = state_of(at)
    state.finalize()

    from ui.report import ReportArtifact

    current = ReportArtifact(
        path=PROJECT_ROOT / "output" / "reports" / "hometsy-current-report.pdf",
        result=state.result,
        filename="hometsy-current-report.pdf",
    )
    assert report_view.is_current(current, state) is True

    # A rebuilt result describes the same project but is not the stored one.
    state.result = state.build_result()
    assert report_view.is_current(current, state) is False

    # Nor is a report current once the result has been discarded.
    state.result = None
    assert report_view.is_current(current, state) is False
    assert report_view.is_current(None, state) is False


def test_a_missing_file_is_reported_instead_of_offering_it(generator) -> None:
    at = open_report_screen(fresh_app())
    at = click(at, GENERATE_LABEL)

    artifact = at.session_state[ARTIFACT_KEY]
    artifact.path.unlink()

    at.run()
    assert_no_exceptions(at)
    text = page_text(at)
    assert "Report file missing" in text
    assert "Generate it again" in text
    assert download_labels(at) == []


# --------------------------------------------------------------------------- #
# 6. The report step sends nothing to the model
# --------------------------------------------------------------------------- #


def test_finalizing_and_generating_make_no_ai_call(monkeypatch, generator) -> None:
    from ui import ai_actions

    calls: list[str] = []

    def record(name: str):
        def spy(*args, **kwargs):
            calls.append(name)
            raise AssertionError(f"{name} must not be called by the report step")

        return spy

    for name in (
        "analyze_brief",
        "generate_concepts",
        "recommend_furniture",
        "evaluate_design",
    ):
        monkeypatch.setattr(ai_actions, name, record(name))

    at = open_report_screen(fresh_app())
    at = click(at, GENERATE_LABEL)
    at.run()
    assert_no_exceptions(at)

    assert calls == []
    assert download_labels(at) == [DOWNLOAD_LABEL]


def test_the_screen_says_the_report_calculates_nothing(generator) -> None:
    at = open_report_screen(fresh_app())
    text = page_text(at)
    assert "sends nothing to the AI model" in text


# --------------------------------------------------------------------------- #
# 7. What the report will describe
# --------------------------------------------------------------------------- #


def test_the_screen_summarises_the_stored_results(generator) -> None:
    at = open_report_screen(fresh_app())
    state = state_of(at)
    text = page_text(at)

    assert "Living Room" in text
    assert "20.80 m²" in text
    assert state.selected_concept.name in text
    assert (
        f"{state.placement.placed_count} of {state.placement.requested_count} placed"
        in text
    )
    assert "55.500,00 TRY" in text or "TRY" in text
    assert "Design evaluation" in text


def test_a_back_link_returns_to_the_budget_screen(generator) -> None:
    at = open_report_screen(fresh_app())
    at = click(at, "Back to the budget analysis")
    assert at.session_state["hm_screen"] == "budget"


def test_starting_a_new_project_clears_the_artifact(generator) -> None:
    at = open_report_screen(fresh_app())
    at = click(at, GENERATE_LABEL)
    assert at.session_state.get(ARTIFACT_KEY) is not None

    at = click(at, "Start a new project")
    assert at.session_state.get(ARTIFACT_KEY) is None
    assert at.session_state["hm_screen"] == "room"
    assert state_of(at).result is None


# --------------------------------------------------------------------------- #
# 8. One budget snapshot, never two
# --------------------------------------------------------------------------- #


def test_a_pdf_is_refused_when_the_recomputed_costs_disagree(generator) -> None:
    """The PDF must never quote two different budget snapshots.

    The report re-runs ``core.budget_engine`` for the per-line table while the
    totals come from the stored ``BudgetAnalysis``. With the same catalog those
    agree — the engine is deterministic — but a caller that passes a different
    catalog would otherwise write a file whose lines contradict its totals.
    """

    from decimal import Decimal

    from models.schemas import BudgetAnalysis

    at = open_report_screen(fresh_app())
    state = state_of(at)

    # A stored analysis the current basket cannot reproduce, as a changed
    # catalog would produce.
    analysis = state.budget_analysis
    state.budget_analysis = analysis.model_copy(
        update={"furniture_subtotal": Decimal("123456.78")}
    )

    with pytest.raises(report_view.ReportGenerationError):
        report_view.finalize_and_build(state)

    assert generator.call_count == 0, "no file may be written from mixed figures"


def test_the_normal_path_writes_the_pdf_once_the_costs_agree(generator) -> None:
    """Guard against the new check rejecting the ordinary, correct case."""

    at = open_report_screen(fresh_app())
    state = state_of(at)
    artifact = report_view.finalize_and_build(state)

    assert generator.call_count == 1
    assert artifact.path.exists()
    # The lines and the totals come from the same computation.
    assert generator.calls[0]["budget"].analysis == state.budget_analysis
