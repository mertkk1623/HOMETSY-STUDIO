"""Integration between the workflow state and the four AI services.

The state module deliberately does not import ``ai``. These tests prove the
bridge works anyway: a caller passes the service call to ``attempt``, the state
runs it, and the result is recorded exactly once. The AI layer is reached
through its own public functions, with a fake completer, so no socket opens.

The point is not to re-test the AI services. It is to check the seam: that a
failed call cannot be recorded, that a successful one is, and that the recorded
result matches what the service returned.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from ai.brief_analyzer import analyze_brief
from ai.client import AITimeoutError
from ai.concept_generator import generate_concepts
from ai.design_advisor import recommend_furniture
from ai.design_evaluator import evaluate_design
from core.budget_engine import compute_budget
from core.validation import validate_catalog_references
from models.schemas import (
    BudgetAnalysis,
    BudgetInput,
    DesignBrief,
    DesignEvaluation,
    DesignPreferences,
    DesignStyle,
    OpeningInput,
    PaletteDirection,
    RoomInput,
    RoomType,
    SpatialValidation,
    UserRequirements,
    Wall,
)
from workflow.state import (
    StepFailed,
    WorkflowState,
    WorkflowStep,
)

# --------------------------------------------------------------------------- #
# Canned answers, in the shapes the services validate
# --------------------------------------------------------------------------- #

BRIEF_JSON = json.dumps(
    {
        "summary": "A calm living room with seating for four and a reading corner.",
        "functional_priorities": ["Seating for four", "Reading corner"],
        "constraints": ["One door and one window"],
        "ambiguities": [],
        "warnings": [],
    }
)


def _concept(name: str) -> dict[str, str]:
    return {
        "name": name,
        "description": "A quiet composition built around the window.",
        "design_direction": "Low horizontal lines with a clear centre.",
        "color_and_material_direction": "Warm neutrals, oak and linen.",
        "furniture_approach": "One large sofa and two light occasional pieces.",
        "functional_rationale": "Leaves a continuous path from door to window.",
        "budget_suitability": "Fits within the stated budget.",
    }


CONCEPTS_JSON = json.dumps(
    {
        "concepts": [
            _concept("Quiet Oak"),
            _concept("Soft Contrast"),
            _concept("Warm Studio"),
        ]
    }
)

RECOMMENDATION_JSON = json.dumps(
    {
        "furniture": [
            {
                "item_id": "sofa_three_seat",
                "quantity": 1,
                "rotation_degrees": 0,
                "rationale": "Main seating.",
            },
            {
                "item_id": "coffee_table",
                "quantity": 1,
                "rotation_degrees": 0,
                "rationale": "Centres the group.",
            },
        ],
        "materials": [
            {
                "name": "White oak",
                "category": "Wood",
                "color_direction": "Pale honey.",
                "rationale": "Matches Japandi.",
            }
        ],
        "color_direction": "Warm off-whites with pale oak.",
        "design_rationale": "A restrained palette keeps the room calm.",
    }
)

EVALUATION_JSON = json.dumps(
    {
        "requirement_compatibility": "Seating for four is met.",
        "style_consistency": "Matches Japandi.",
        "functional_suitability": "The path from door to window stays clear.",
        "budget_suitability": "Within budget.",
        "limitations": ["The reading corner is only implied"],
        "recommendations": ["Add a floor lamp"],
    }
)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def room() -> RoomInput:
    return RoomInput(
        room_type=RoomType.LIVING_ROOM,
        name="Living Room",
        width_cm=400,
        length_cm=520,
        door=OpeningInput(wall=Wall.SOUTH, offset_cm=60, width_cm=90),
        window=OpeningInput(wall=Wall.NORTH, offset_cm=120, width_cm=160),
    )


@pytest.fixture
def preferences() -> DesignPreferences:
    return DesignPreferences(
        style=DesignStyle.JAPANDI,
        palette=PaletteDirection.WARM_NEUTRAL,
        material_preferences=["oak", "linen"],
    )


@pytest.fixture
def requirements() -> UserRequirements:
    return UserRequirements(
        functional_requirements=["Seating for four", "Reading corner"],
        notes="Keep the window side open.",
    )


@pytest.fixture
def budget() -> BudgetInput:
    return BudgetInput(total_budget=Decimal("45000.00"))


@pytest.fixture
def inputs(
    room: RoomInput,
    preferences: DesignPreferences,
    requirements: UserRequirements,
    budget: BudgetInput,
) -> WorkflowState:
    state = WorkflowState()
    state.set_room(room)
    state.set_preferences(preferences)
    state.set_requirements(requirements)
    state.set_budget(budget)
    return state


# --------------------------------------------------------------------------- #
# The four services, reached through the state
# --------------------------------------------------------------------------- #


def test_brief_service_result_is_recorded(inputs, ai_config, fake_completer) -> None:
    fake_completer.queue(BRIEF_JSON)

    brief = inputs.attempt(
        WorkflowStep.BRIEF_ANALYSIS,
        lambda: analyze_brief(
            ai_config,
            inputs.room,
            inputs.preferences,
            inputs.requirements,
            inputs.budget,
            completer=fake_completer,
        ),
        inputs.record_brief,
    )

    assert isinstance(brief, DesignBrief)
    assert inputs.brief is brief
    assert fake_completer.call_count == 1
    assert inputs.next_step is WorkflowStep.CONCEPT_GENERATION


def test_concept_service_returns_three_and_records_them(
    inputs, ai_config, fake_completer
) -> None:
    inputs.record_brief(
        DesignBrief(summary="A calm living room with seating for four.")
    )
    fake_completer.queue(CONCEPTS_JSON)

    collection = inputs.attempt(
        WorkflowStep.CONCEPT_GENERATION,
        lambda: generate_concepts(
            ai_config,
            inputs.room,
            inputs.preferences,
            inputs.requirements,
            inputs.budget,
            inputs.brief,
            completer=fake_completer,
        ),
        inputs.record_concepts,
    )

    assert len(collection.concepts) == 3
    assert inputs.concepts == collection
    assert inputs.next_step is WorkflowStep.CONCEPT_SELECTION


def test_advisor_result_is_recorded_and_priced_by_python(
    inputs, ai_config, fake_completer, catalog
) -> None:
    inputs.record_brief(DesignBrief(summary="Brief."))
    inputs.record_concepts(_concepts_collection())
    inputs.select_concept_by_name("Quiet Oak")
    fake_completer.queue(RECOMMENDATION_JSON)

    advice = inputs.attempt(
        WorkflowStep.RECOMMENDATIONS,
        lambda: recommend_furniture(
            ai_config,
            inputs.room,
            inputs.preferences,
            inputs.budget,
            inputs.brief,
            inputs.selected_concept,
            catalog,
            completer=fake_completer,
        ),
        lambda result: inputs.record_recommendation(result.recommendation),
    )

    assert len(inputs.furniture) == 2
    assert inputs.materials[0].name == "White oak"
    # 18500 (sofa) + 4900 (coffee table), read from the catalog.
    assert advice.furniture_subtotal == Decimal("23400.00")
    assert advice.is_usable


def test_recommendation_records_exactly_what_the_advisor_returned(
    inputs, ai_config, fake_completer, catalog
) -> None:
    inputs.record_brief(DesignBrief(summary="Brief."))
    inputs.record_concepts(_concepts_collection())
    inputs.select_concept_by_name("Quiet Oak")
    fake_completer.queue(RECOMMENDATION_JSON)

    advice = recommend_furniture(
        ai_config,
        inputs.room,
        inputs.preferences,
        inputs.budget,
        inputs.brief,
        inputs.selected_concept,
        catalog,
        completer=fake_completer,
    )
    inputs.record_recommendation(advice.recommendation)

    rebuilt = inputs.as_recommendation()
    assert rebuilt is not None
    assert [item.item_id for item in rebuilt.furniture] == [
        "sofa_three_seat",
        "coffee_table",
    ]


def test_evaluation_service_is_recorded_after_both_engine_results(
    inputs, ai_config, fake_completer, catalog
) -> None:
    _fill_through_recommendations(inputs, ai_config, fake_completer, catalog)

    # Python, not the model, produces the spatial and budget facts.
    spatial = SpatialValidation(is_valid=True, warnings=["Tight at the door"])
    analysis = BudgetAnalysis(
        furniture_subtotal=Decimal("23400.00"),
        total_estimated=Decimal("23400.00"),
        remaining_budget=Decimal("21600.00"),
    )
    inputs.record_spatial(spatial)
    inputs.record_budget_analysis(analysis)

    fake_completer.queue(EVALUATION_JSON)
    evaluation = inputs.attempt(
        WorkflowStep.DESIGN_EVALUATION,
        lambda: evaluate_design(
            ai_config,
            inputs.room,
            inputs.preferences,
            inputs.budget,
            inputs.brief,
            inputs.selected_concept,
            inputs.furniture,
            inputs.spatial,
            inputs.budget_analysis,
            catalog,
            budget_is_complete=True,
            completer=fake_completer,
        ),
        inputs.record_evaluation,
    )

    assert isinstance(evaluation, DesignEvaluation)
    assert inputs.evaluation is evaluation
    assert inputs.next_step is WorkflowStep.FINAL_RESULT


def test_full_workflow_reaches_a_project_result(
    inputs, ai_config, fake_completer, catalog
) -> None:
    # One answer per AI step, consumed in workflow order.
    fake_completer.queue(
        BRIEF_JSON, CONCEPTS_JSON, RECOMMENDATION_JSON, EVALUATION_JSON
    )

    inputs.attempt(
        WorkflowStep.BRIEF_ANALYSIS,
        lambda: analyze_brief(
            ai_config,
            inputs.room,
            inputs.preferences,
            inputs.requirements,
            inputs.budget,
            completer=fake_completer,
        ),
        inputs.record_brief,
    )
    inputs.attempt(
        WorkflowStep.CONCEPT_GENERATION,
        lambda: generate_concepts(
            ai_config,
            inputs.room,
            inputs.preferences,
            inputs.requirements,
            inputs.budget,
            inputs.brief,
            completer=fake_completer,
        ),
        inputs.record_concepts,
    )
    inputs.select_concept_by_name("Quiet Oak")

    advice = inputs.attempt(
        WorkflowStep.RECOMMENDATIONS,
        lambda: recommend_furniture(
            ai_config,
            inputs.room,
            inputs.preferences,
            inputs.budget,
            inputs.brief,
            inputs.selected_concept,
            catalog,
            completer=fake_completer,
        ),
        lambda result: inputs.record_recommendation(result.recommendation),
    )

    spatial, _ = _spatial(inputs, catalog)
    inputs.record_spatial(spatial)
    budget_result = compute_budget(inputs.budget, inputs.furniture, catalog)
    inputs.record_budget_analysis(budget_result.analysis)

    inputs.attempt(
        WorkflowStep.DESIGN_EVALUATION,
        lambda: evaluate_design(
            ai_config,
            inputs.room,
            inputs.preferences,
            inputs.budget,
            inputs.brief,
            inputs.selected_concept,
            inputs.furniture,
            inputs.spatial,
            inputs.budget_analysis,
            catalog,
            budget_is_complete=budget_result.is_trustworthy,
            completer=fake_completer,
        ),
        inputs.record_evaluation,
    )

    assert fake_completer.call_count == 4
    assert advice.is_usable

    result = inputs.finalize()
    assert result.selected_concept.name == "Quiet Oak"
    assert result.budget_analysis.total_estimated == Decimal("23400.00")
    assert inputs.is_finished


# --------------------------------------------------------------------------- #
# Failure at the seam
# --------------------------------------------------------------------------- #


def test_timeout_is_not_recorded(inputs, ai_config, fake_completer) -> None:
    fake_completer.queue(AITimeoutError("The AI provider did not answer."))

    with pytest.raises(StepFailed) as excinfo:
        inputs.attempt(
            WorkflowStep.BRIEF_ANALYSIS,
            lambda: analyze_brief(
                ai_config,
                inputs.room,
                inputs.preferences,
                inputs.requirements,
                inputs.budget,
                completer=fake_completer,
            ),
            inputs.record_brief,
        )

    assert isinstance(excinfo.value.cause, AITimeoutError)
    assert inputs.brief is None
    assert fake_completer.call_count == 1


def test_truncated_concepts_are_not_recorded(
    inputs, ai_config, fake_completer
) -> None:
    from ai.client import AITruncatedResponseError

    inputs.record_brief(DesignBrief(summary="Brief."))
    fake_completer.queue(AITruncatedResponseError("cut off at 6000 tokens"))

    with pytest.raises(StepFailed):
        inputs.attempt(
            WorkflowStep.CONCEPT_GENERATION,
            lambda: generate_concepts(
                ai_config,
                inputs.room,
                inputs.preferences,
                inputs.requirements,
                inputs.budget,
                inputs.brief,
                completer=fake_completer,
            ),
            inputs.record_concepts,
        )

    assert inputs.concepts is None


def test_unusable_catalog_reference_does_not_block_recording_but_is_reported(
    inputs, ai_config, fake_completer, catalog
) -> None:
    # The advisor returns its finding rather than raising, and the state records
    # the proposal so the interface can show what was chosen and what is wrong
    # with it. Nothing here claims the basket is valid.
    inputs.record_brief(DesignBrief(summary="Brief."))
    inputs.record_concepts(_concepts_collection())
    inputs.select_concept_by_name("Quiet Oak")

    payload = json.loads(RECOMMENDATION_JSON)
    payload["furniture"][0]["item_id"] = "ghost_sofa"
    fake_completer.queue(json.dumps(payload))

    advice = recommend_furniture(
        ai_config,
        inputs.room,
        inputs.preferences,
        inputs.budget,
        inputs.brief,
        inputs.selected_concept,
        catalog,
        completer=fake_completer,
    )
    inputs.record_recommendation(advice.recommendation)

    assert not advice.is_usable
    assert "ghost_sofa" in [item.item_id for item in inputs.furniture]
    findings = validate_catalog_references(
        inputs.room, list(inputs.furniture), catalog
    )
    assert any(finding.code == "unknown_catalog_item" for finding in findings)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _concepts_collection():
    from models.schemas import ConceptCollection

    return ConceptCollection.model_validate(json.loads(CONCEPTS_JSON))


def _fill_through_recommendations(state, config, completer, catalog) -> None:
    state.record_brief(DesignBrief(summary="A calm living room."))
    state.record_concepts(_concepts_collection())
    state.select_concept_by_name("Quiet Oak")
    completer.queue(RECOMMENDATION_JSON)
    advice = recommend_furniture(
        config,
        state.room,
        state.preferences,
        state.budget,
        state.brief,
        state.selected_concept,
        catalog,
        completer=completer,
    )
    state.record_recommendation(advice.recommendation)


def _spatial(state, catalog):
    """Run the Phase 3 geometry check and convert it to the stored model."""

    from core.spatial_engine import to_spatial_validation, validate_recommendations

    placement, _ = validate_recommendations(
        state.room, list(state.furniture), catalog
    )
    return to_spatial_validation(placement), placement
