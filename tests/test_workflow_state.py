"""Tests for workflow state: ordering, prerequisites and invalidation.

Two things are being protected here.

**Order.** A step must not run before its prerequisites exist, otherwise the
interface could store a brief for a room that was never described.

**Freshness.** When an input changes, exactly the results that depended on it
must disappear — no more (which would destroy valid work) and no fewer (which
would show a stale result as current).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from models.schemas import (
    BudgetAnalysis,
    BudgetInput,
    ConceptCollection,
    ConceptCompatibility,
    DesignBrief,
    DesignConcept,
    DesignEvaluation,
    DesignPreferences,
    DesignRecommendation,
    DesignStyle,
    FurniturePosition,
    FurnitureRecommendation,
    IntentCheck,
    MaterialRecommendation,
    OpeningInput,
    PaletteDirection,
    RoomInput,
    RoomType,
    SpatialValidation,
    UserRequirements,
    Wall,
    WallPreference,
)
from workflow.dependencies import DataKey
from workflow.state import (
    STEP_ORDER,
    IncompleteWorkflowError,
    PrerequisiteError,
    StepFailed,
    WorkflowError,
    WorkflowState,
    WorkflowStep,
    room_change_keys,
    unplace_recommendation,
)


# --------------------------------------------------------------------------- #
# Builders
# --------------------------------------------------------------------------- #


def make_room(width: float = 400, length: float = 520) -> RoomInput:
    return RoomInput(
        room_type=RoomType.LIVING_ROOM,
        name="Living Room",
        width_cm=width,
        length_cm=length,
        ceiling_height_cm=270,
        door=OpeningInput(wall=Wall.SOUTH, offset_cm=60, width_cm=90),
        window=OpeningInput(wall=Wall.NORTH, offset_cm=120, width_cm=160),
    )


def make_concepts() -> ConceptCollection:
    return ConceptCollection(
        concepts=[
            DesignConcept(
                name=name,
                description=f"{name} description.",
                design_direction="Low horizontal lines.",
                color_and_material_direction="Oak and linen.",
                furniture_approach="Sparse.",
                functional_rationale="Clear path to the window.",
                budget_suitability="Fits.",
            )
            for name in ("Quiet Oak", "Soft Contrast", "Warm Studio")
        ]
    )


def make_brief() -> DesignBrief:
    return DesignBrief(
        summary="A calm living room with a reading corner.",
        functional_priorities=["Seating for four"],
    )


def make_recommendation(
    item_id: str = "sofa_three_seat",
    material: str = "White oak",
) -> DesignRecommendation:
    return DesignRecommendation(
        furniture=[FurnitureRecommendation(item_id=item_id)],
        materials=[
            MaterialRecommendation(
                name=material,
                category="Wood",
                color_direction="Pale honey.",
                rationale="Matches the palette.",
            )
        ],
        color_direction="Warm off-whites with pale oak.",
        design_rationale="A restrained palette keeps the room calm.",
    )


def make_spatial(valid: bool = True) -> SpatialValidation:
    return SpatialValidation(is_valid=valid)


def recommend_item(
    item_id: str = "bed_double", **intent: object
) -> DesignRecommendation:
    """A one-item advisor result, carrying whatever layout intent is given.

    ``DesignRecommendation`` also demands the narrative fields, so this keeps the
    intent tests about intent rather than about the model's required prose.
    """

    return DesignRecommendation(
        furniture=[FurnitureRecommendation(item_id=item_id, **intent)],
        color_direction="Warm off-whites with pale oak.",
        design_rationale="A restrained palette keeps the room calm.",
    )


def complete_with(recommendation: DesignRecommendation) -> WorkflowState:
    """A finished workflow whose basket is exactly this recommendation.

    Recording a basket invalidates the layout it no longer justifies, so the
    derived results have to be recorded again — that is the behaviour under
    test, and getting to a settled state has to respect it.
    """

    state = complete()
    state.record_recommendation(recommendation)
    state.record_spatial(make_spatial())
    state.record_budget_analysis(make_analysis())
    state.record_evaluation(make_evaluation())
    return state


def make_analysis(total: str = "18500.00") -> BudgetAnalysis:
    amount = Decimal(total)
    return BudgetAnalysis(
        furniture_subtotal=amount,
        total_estimated=amount,
        remaining_budget=Decimal("45000.00") - amount,
    )


def make_evaluation() -> DesignEvaluation:
    return DesignEvaluation(
        requirement_compatibility="Seating is satisfied.",
        style_consistency="Consistent with Japandi.",
        functional_suitability="Circulation remains clear.",
        budget_suitability="Within budget.",
    )


def with_inputs() -> WorkflowState:
    """A state that has all four user inputs and nothing derived."""

    state = WorkflowState()
    state.set_room(make_room())
    state.set_preferences(
        DesignPreferences(
            style=DesignStyle.JAPANDI,
            palette=PaletteDirection.WARM_NEUTRAL,
            material_preferences=["oak"],
        )
    )
    state.set_requirements(
        UserRequirements(functional_requirements=["Seating for four"])
    )
    state.set_budget(BudgetInput(total_budget=Decimal("45000.00")))
    return state


def through_concepts() -> WorkflowState:
    state = with_inputs()
    state.record_brief(make_brief())
    state.record_concepts(make_concepts())
    state.select_concept_by_name("Quiet Oak")
    return state


def through_recommendations() -> WorkflowState:
    state = through_concepts()
    state.record_recommendation(make_recommendation())
    return state


def complete() -> WorkflowState:
    state = through_recommendations()
    state.record_spatial(make_spatial())
    state.record_budget_analysis(make_analysis())
    state.record_evaluation(make_evaluation())
    return state


# --------------------------------------------------------------------------- #
# 1. Fresh state
# --------------------------------------------------------------------------- #


def test_fresh_state_is_empty() -> None:
    state = WorkflowState()
    assert state.room is None
    assert state.brief is None
    assert state.furniture == ()
    assert state.completed_steps == ()


def test_fresh_state_starts_at_room_information() -> None:
    assert WorkflowState().next_step is WorkflowStep.ROOM_INFORMATION


def test_fresh_state_is_not_finished() -> None:
    assert not WorkflowState().is_finished


def test_step_order_matches_the_approved_workflow() -> None:
    assert [step.value for step in STEP_ORDER] == [
        "room_information",
        "design_preferences",
        "brief_analysis",
        "concept_generation",
        "concept_selection",
        "recommendations",
        "spatial_validation",
        "budget_analysis",
        "design_evaluation",
        "final_result",
    ]


def test_only_the_first_step_is_runnable_on_a_fresh_state() -> None:
    state = WorkflowState()
    state.guard(WorkflowStep.ROOM_INFORMATION)
    with pytest.raises(PrerequisiteError):
        state.guard(WorkflowStep.BRIEF_ANALYSIS)


# --------------------------------------------------------------------------- #
# 2. Ordering and prerequisites
# --------------------------------------------------------------------------- #


def test_steps_advance_in_order() -> None:
    state = WorkflowState()
    assert state.next_step is WorkflowStep.ROOM_INFORMATION

    state.set_room(make_room())
    assert state.next_step is WorkflowStep.DESIGN_PREFERENCES

    state.set_preferences(
        DesignPreferences(
            style=DesignStyle.JAPANDI, palette=PaletteDirection.WARM_NEUTRAL
        )
    )
    assert state.next_step is WorkflowStep.DESIGN_PREFERENCES

    state.set_requirements(UserRequirements())
    assert state.next_step is WorkflowStep.DESIGN_PREFERENCES

    state.set_budget(BudgetInput(total_budget=Decimal("45000.00")))
    assert state.next_step is WorkflowStep.BRIEF_ANALYSIS

    state.record_brief(make_brief())
    assert state.next_step is WorkflowStep.CONCEPT_GENERATION

    state.record_concepts(make_concepts())
    assert state.next_step is WorkflowStep.CONCEPT_SELECTION

    state.select_concept_by_name("Quiet Oak")
    assert state.next_step is WorkflowStep.RECOMMENDATIONS

    state.record_recommendation(make_recommendation())
    assert state.next_step is WorkflowStep.SPATIAL_VALIDATION

    state.record_spatial(make_spatial())
    assert state.next_step is WorkflowStep.BUDGET_ANALYSIS

    state.record_budget_analysis(make_analysis())
    assert state.next_step is WorkflowStep.DESIGN_EVALUATION

    state.record_evaluation(make_evaluation())
    assert state.next_step is WorkflowStep.FINAL_RESULT

    state.finalize()
    assert state.next_step is None
    assert state.is_finished


def test_brief_cannot_be_recorded_without_inputs() -> None:
    state = WorkflowState()
    with pytest.raises(PrerequisiteError) as excinfo:
        state.record_brief(make_brief())
    assert WorkflowStep.ROOM_INFORMATION in excinfo.value.missing
    assert state.brief is None


def test_concepts_cannot_be_recorded_without_a_brief() -> None:
    state = with_inputs()
    with pytest.raises(PrerequisiteError):
        state.record_concepts(make_concepts())
    assert state.concepts is None


def test_selection_cannot_happen_without_concepts() -> None:
    state = with_inputs()
    state.record_brief(make_brief())
    with pytest.raises(PrerequisiteError):
        state.select_concept_by_name("Quiet Oak")
    assert state.selected_concept is None


def test_recommendation_requires_a_selection() -> None:
    state = with_inputs()
    state.record_brief(make_brief())
    state.record_concepts(make_concepts())
    with pytest.raises(PrerequisiteError):
        state.record_recommendation(make_recommendation())
    assert state.furniture == ()


def test_spatial_requires_recommendations() -> None:
    state = through_concepts()
    with pytest.raises(PrerequisiteError):
        state.record_spatial(make_spatial())


def test_budget_analysis_requires_recommendations() -> None:
    state = through_concepts()
    with pytest.raises(PrerequisiteError):
        state.record_budget_analysis(make_analysis())


def test_evaluation_requires_both_deterministic_results() -> None:
    state = through_recommendations()
    with pytest.raises(PrerequisiteError) as excinfo:
        state.record_evaluation(make_evaluation())
    assert WorkflowStep.SPATIAL_VALIDATION in excinfo.value.missing
    assert WorkflowStep.BUDGET_ANALYSIS in excinfo.value.missing


def test_evaluation_is_blocked_when_only_one_result_exists() -> None:
    state = through_recommendations()
    state.record_spatial(make_spatial())
    with pytest.raises(PrerequisiteError) as excinfo:
        state.record_evaluation(make_evaluation())
    assert excinfo.value.missing == (WorkflowStep.BUDGET_ANALYSIS,)


def test_spatial_and_budget_are_independent_of_each_other() -> None:
    # Either order must work: they are siblings, not a chain.
    first = through_recommendations()
    first.record_spatial(make_spatial())
    first.record_budget_analysis(make_analysis())

    second = through_recommendations()
    second.record_budget_analysis(make_analysis())
    second.record_spatial(make_spatial())

    assert first.is_complete(WorkflowStep.DESIGN_EVALUATION) is False
    assert second.is_complete(WorkflowStep.DESIGN_EVALUATION) is False
    assert first.is_complete(WorkflowStep.BUDGET_ANALYSIS)
    assert second.is_complete(WorkflowStep.SPATIAL_VALIDATION)


def test_prerequisite_error_names_the_missing_step() -> None:
    state = WorkflowState()
    with pytest.raises(PrerequisiteError) as excinfo:
        state.record_concepts(make_concepts())
    message = str(excinfo.value)
    assert "Concept generation" in message
    assert "Brief analysis" in message


def test_missing_prerequisites_lists_only_direct_needs() -> None:
    state = with_inputs()
    assert state.missing_prerequisites(WorkflowStep.BRIEF_ANALYSIS) == ()
    assert state.missing_prerequisites(WorkflowStep.RECOMMENDATIONS) == (
        WorkflowStep.CONCEPT_SELECTION,
    )


# --------------------------------------------------------------------------- #
# 3. Room changes
# --------------------------------------------------------------------------- #


def test_room_dimension_change_invalidates_everything_downstream() -> None:
    state = complete()
    dropped = state.set_room(make_room(width=420))

    assert set(dropped) == {
        DataKey.BRIEF,
        DataKey.CONCEPTS,
        DataKey.SELECTED_CONCEPT,
        DataKey.FURNITURE,
        DataKey.MATERIALS,
        DataKey.SPATIAL,
        DataKey.BUDGET_ANALYSIS,
        DataKey.EVALUATION,
    }
    assert state.brief is None
    assert state.concepts is None
    assert state.selected_concept is None
    assert state.furniture == ()
    assert state.materials == ()
    assert state.spatial is None
    assert state.budget_analysis is None
    assert state.evaluation is None


def test_room_dimension_change_keeps_the_user_inputs() -> None:
    state = complete()
    state.set_room(make_room(width=420))
    assert state.room is not None
    assert state.room.width_cm == 420
    assert state.preferences is not None
    assert state.requirements is not None
    assert state.budget is not None


def test_room_type_change_invalidates_the_budget_analysis() -> None:
    state = complete()
    bedroom = make_room().model_copy(update={"room_type": RoomType.BEDROOM})
    dropped = state.set_room(bedroom)
    assert DataKey.BUDGET_ANALYSIS in dropped
    assert state.budget_analysis is None


def test_opening_change_keeps_the_budget_analysis() -> None:
    state = complete()
    moved_door = make_room().model_copy(
        update={"door": OpeningInput(wall=Wall.SOUTH, offset_cm=120, width_cm=90)}
    )
    dropped = state.set_room(moved_door)

    assert DataKey.SPATIAL in dropped
    assert DataKey.BUDGET_ANALYSIS not in dropped
    assert state.budget_analysis is not None
    assert state.spatial is None


def test_opening_change_keeps_concepts_invalid_by_the_rule() -> None:
    # The approved table lists concepts as invalidated by an opening change.
    state = complete()
    moved_window = make_room().model_copy(
        update={"window": OpeningInput(wall=Wall.NORTH, offset_cm=140, width_cm=160)}
    )
    dropped = state.set_room(moved_window)
    assert DataKey.CONCEPTS in dropped
    assert state.concepts is None


def test_ceiling_height_counts_as_a_dimension_change() -> None:
    state = complete()
    taller = make_room().model_copy(update={"ceiling_height_cm": 300})
    dropped = state.set_room(taller)
    assert DataKey.BUDGET_ANALYSIS in dropped


def test_renaming_the_room_invalidates_nothing() -> None:
    state = complete()
    renamed = make_room().model_copy(update={"name": "Snug"})
    dropped = state.set_room(renamed)
    assert dropped == ()
    assert state.brief is not None
    assert state.evaluation is not None


def test_resubmitting_the_same_room_invalidates_nothing() -> None:
    state = complete()
    assert state.set_room(make_room()) == ()
    assert state.evaluation is not None


def test_first_room_assignment_invalidates_nothing() -> None:
    state = WorkflowState()
    assert state.set_room(make_room()) == ()


def test_room_change_keys_detects_each_facet() -> None:
    base = make_room()
    assert room_change_keys(base, make_room()) == frozenset()
    assert room_change_keys(base, make_room(width=410)) == {
        DataKey.ROOM_DIMENSIONS
    }
    assert room_change_keys(
        base, base.model_copy(update={"room_type": RoomType.BEDROOM})
    ) == {DataKey.ROOM_TYPE}
    assert room_change_keys(
        base,
        base.model_copy(
            update={"door": OpeningInput(wall=Wall.SOUTH, offset_cm=10, width_cm=90)}
        ),
    ) == {DataKey.ROOM_OPENINGS}


def test_a_change_touching_two_facets_reports_both() -> None:
    base = make_room()
    both = make_room(width=410).model_copy(
        update={"room_type": RoomType.BEDROOM}
    )
    assert room_change_keys(base, both) == {
        DataKey.ROOM_DIMENSIONS,
        DataKey.ROOM_TYPE,
    }


# --------------------------------------------------------------------------- #
# 4. Preference, requirement and budget changes
# --------------------------------------------------------------------------- #


def test_preference_change_invalidates_ai_results_but_not_geometry() -> None:
    state = complete()
    dropped = state.set_preferences(
        DesignPreferences(
            style=DesignStyle.INDUSTRIAL, palette=PaletteDirection.EARTHY
        )
    )

    assert DataKey.BRIEF in dropped
    assert DataKey.CONCEPTS in dropped
    assert DataKey.FURNITURE in dropped
    assert DataKey.EVALUATION in dropped
    # Independent, still-correct results survive.
    assert DataKey.SPATIAL not in dropped
    assert DataKey.BUDGET_ANALYSIS not in dropped
    assert state.spatial is not None
    assert state.budget_analysis is not None


def test_preference_change_clears_the_selection() -> None:
    state = complete()
    state.set_preferences(
        DesignPreferences(style=DesignStyle.BOHEMIAN, palette=PaletteDirection.EARTHY)
    )
    assert state.selected_concept is None
    assert state.concepts is None


def test_requirement_change_invalidates_the_brief_and_concepts() -> None:
    state = complete()
    dropped = state.set_requirements(
        UserRequirements(functional_requirements=["Home office for two"])
    )
    assert DataKey.BRIEF in dropped
    assert DataKey.CONCEPTS in dropped
    assert state.brief is None


def test_budget_change_keeps_spatial_and_selection() -> None:
    # The headline case from the brief: only geometry-independent results fall.
    state = complete()
    dropped = state.set_budget(BudgetInput(total_budget=Decimal("30000.00")))

    assert DataKey.BRIEF in dropped
    assert DataKey.CONCEPTS in dropped
    assert DataKey.FURNITURE in dropped
    assert DataKey.BUDGET_ANALYSIS in dropped
    assert DataKey.EVALUATION in dropped

    assert DataKey.SPATIAL not in dropped
    assert DataKey.SELECTED_CONCEPT not in dropped
    assert state.spatial is not None
    assert state.selected_concept is not None
    assert state.budget_analysis is None


def test_budget_change_preserves_the_room_facts() -> None:
    state = complete()
    state.set_budget(BudgetInput(total_budget=Decimal("30000.00")))
    assert state.room is not None
    assert state.preferences is not None


def test_preserved_spatial_result_is_not_presented_as_current() -> None:
    """The layout survives a budget change, but cannot pass as a current result.

    The approved table keeps ``spatial`` when the budget changes, because the
    geometry is still a fact about the room. It is nonetheless left without its
    prerequisite: the furniture it described has been cleared. Completion is
    derived from data *and* prerequisites, so the retained layout is inert until
    the basket is regenerated — at which point the furniture edge fires and
    clears it properly. This test pins that reasoning down.
    """

    state = complete()
    state.set_budget(BudgetInput(total_budget=Decimal("30000.00")))

    # Retained as data...
    assert state.spatial is not None
    # ...but not usable as a completed step, because the basket is gone.
    assert state.furniture == ()
    assert not state.is_complete(WorkflowStep.RECOMMENDATIONS)
    assert not state.is_complete(WorkflowStep.SPATIAL_VALIDATION)
    assert state.next_step is WorkflowStep.BRIEF_ANALYSIS

    # And re-recording the basket clears the leftover layout.
    state.record_brief(make_brief())
    state.record_concepts(make_concepts())
    state.select_concept_by_name("Quiet Oak")
    state.record_recommendation(make_recommendation("sofa_two_seat"))
    assert state.spatial is None


def test_identical_budget_invalidates_nothing() -> None:
    state = complete()
    assert state.set_budget(BudgetInput(total_budget=Decimal("45000.00"))) == ()
    assert state.evaluation is not None


def test_identical_preferences_invalidate_nothing() -> None:
    state = complete()
    same = DesignPreferences(
        style=DesignStyle.JAPANDI,
        palette=PaletteDirection.WARM_NEUTRAL,
        material_preferences=["oak"],
    )
    assert state.set_preferences(same) == ()
    assert state.evaluation is not None


def test_identical_requirements_invalidate_nothing() -> None:
    state = complete()
    same = UserRequirements(functional_requirements=["Seating for four"])
    assert state.set_requirements(same) == ()
    assert state.evaluation is not None


# --------------------------------------------------------------------------- #
# 5. Result-to-result changes
# --------------------------------------------------------------------------- #


def test_new_concepts_clear_the_previous_selection() -> None:
    state = complete()
    dropped = state.record_concepts(make_concepts())
    # Identical concepts are a no-op; a different set is the real case.
    assert dropped == ()


def test_different_concepts_invalidate_selection_and_advice() -> None:
    state = complete()
    replacement = ConceptCollection(
        concepts=[
            DesignConcept(
                name=name,
                description="Different direction.",
                design_direction="High contrast.",
                color_and_material_direction="Deep tones.",
                furniture_approach="Dense.",
                functional_rationale="Maximises seating.",
                budget_suitability="Tight.",
            )
            for name in ("Bold One", "Bold Two", "Bold Three")
        ]
    )
    dropped = state.record_concepts(replacement)

    assert DataKey.SELECTED_CONCEPT in dropped
    assert DataKey.FURNITURE in dropped
    assert state.selected_concept is None
    assert state.furniture == ()
    assert state.concepts == replacement


def test_changing_the_selected_concept_clears_advice_and_checks() -> None:
    state = complete()
    soft = next(c for c in state.concepts.concepts if c.name == "Soft Contrast")
    dropped = state.select_concept(soft)

    assert set(dropped) == {
        DataKey.FURNITURE,
        DataKey.MATERIALS,
        DataKey.SPATIAL,
        DataKey.BUDGET_ANALYSIS,
        DataKey.EVALUATION,
    }
    assert state.furniture == ()
    assert state.spatial is None
    assert state.budget_analysis is None
    assert state.evaluation is None
    assert state.selected_concept == soft


def test_selecting_the_same_concept_invalidates_nothing() -> None:
    state = complete()
    current = state.selected_concept
    assert state.select_concept(current) == ()
    assert state.evaluation is not None


def test_selecting_a_concept_outside_the_collection_is_refused() -> None:
    state = through_concepts()
    stranger = DesignConcept(
        name="Not Generated",
        description="Invented.",
        design_direction="x",
        color_and_material_direction="y",
        furniture_approach="z",
        functional_rationale="r",
        budget_suitability="b",
    )
    with pytest.raises(WorkflowError) as excinfo:
        state.select_concept(stranger)
    assert "not one of the generated concepts" in str(excinfo.value)


def test_selecting_an_unknown_name_is_refused() -> None:
    state = through_concepts()
    with pytest.raises(WorkflowError) as excinfo:
        state.select_concept_by_name("Does Not Exist")
    assert "No concept is named" in str(excinfo.value)


def test_selection_by_name_is_case_insensitive() -> None:
    state = through_concepts()
    state.select_concept_by_name("warm studio")
    assert state.selected_concept is not None
    assert state.selected_concept.name == "Warm Studio"


def test_new_furniture_invalidates_spatial_budget_and_evaluation() -> None:
    state = complete()
    dropped = state.record_recommendation(make_recommendation("sofa_two_seat"))

    assert set(dropped) == {
        DataKey.SPATIAL,
        DataKey.BUDGET_ANALYSIS,
        DataKey.EVALUATION,
    }
    assert state.spatial is None
    assert state.budget_analysis is None
    assert state.evaluation is None


def test_new_furniture_keeps_the_materials() -> None:
    # The brief's table gives furniture no edge to materials.
    state = complete()
    state.record_recommendation(make_recommendation("sofa_two_seat"))
    assert len(state.materials) == 1
    assert state.materials[0].name == "White oak"


def test_material_only_change_keeps_the_layout() -> None:
    state = complete()
    dropped = state.set_materials(
        [
            MaterialRecommendation(
                name="Linen",
                category="Textile",
                color_direction="Soft cream.",
                rationale="Softer.",
            )
        ]
    )

    assert set(dropped) == {DataKey.BUDGET_ANALYSIS, DataKey.EVALUATION}
    assert state.spatial is not None
    assert state.furniture != ()
    assert state.materials[0].name == "Linen"


def test_identical_recommendation_invalidates_nothing() -> None:
    state = complete()
    assert state.record_recommendation(make_recommendation()) == ()
    assert state.evaluation is not None


def test_a_new_preferred_wall_invalidates_the_layout() -> None:
    """The wall changes where the engine searches, so the plan is stale.

    The item, its quantity and its rationale are all identical; only the
    requested wall differs. If intent were left out of the basket identity the
    stored layout would silently outlive the request that produced it.
    """

    state = complete_with(recommend_item())
    assert state.spatial is not None

    dropped = state.record_recommendation(
        recommend_item(preferred_wall=Wall.WEST)
    )

    assert DataKey.SPATIAL in dropped
    assert state.spatial is None
    assert state.placement is None
    assert state.concept_compatibility is None
    assert state.furniture[0].preferred_wall is Wall.WEST


def test_a_new_wall_priority_invalidates_the_layout() -> None:
    """``preferred`` to ``required`` is a different constraint, not a cosmetic one."""

    state = complete_with(recommend_item(preferred_wall=Wall.WEST))
    assert state.spatial is not None

    dropped = state.record_recommendation(
        recommend_item(
            preferred_wall=Wall.WEST, wall_priority=WallPreference.REQUIRED
        )
    )

    assert DataKey.SPATIAL in dropped
    assert state.spatial is None


def test_the_same_intent_invalidates_nothing() -> None:
    """Re-submitting an identical intent must not throw the layout away."""

    state = complete_with(recommend_item(preferred_wall=Wall.WEST))
    before = state.spatial

    assert state.record_recommendation(recommend_item(preferred_wall=Wall.WEST)) == ()
    assert state.spatial is before


def test_unplacing_a_recommendation_keeps_its_intent() -> None:
    """Only the engine's coordinates are stripped, never the request.

    ``positions`` belong to one placement run; ``preferred_wall`` belongs to the
    basket. Conflating them would erase the design intent the moment a layout
    went stale.
    """

    placed = FurnitureRecommendation(
        item_id="bed_double",
        preferred_wall=Wall.WEST,
        wall_priority=WallPreference.REQUIRED,
        position_x_cm=0.0,
        position_y_cm=120.0,
        positions=[FurniturePosition(position_x_cm=0.0, position_y_cm=120.0)],
    )

    cleared = unplace_recommendation(placed)

    assert cleared.position_x_cm is None
    assert cleared.position_y_cm is None
    assert cleared.positions == []
    assert cleared.preferred_wall is Wall.WEST
    assert cleared.wall_priority is WallPreference.REQUIRED
    assert cleared.item_id == placed.item_id


def test_invalidating_the_layout_clears_the_compatibility_verdict() -> None:
    """The verdict judged those coordinates, so it expires with them."""

    state = complete_with(recommend_item(preferred_wall=Wall.WEST))
    compatibility = ConceptCompatibility(
        checks=[
            IntentCheck(
                item_id="bed_double",
                label="Double bed",
                preferred_wall=Wall.WEST,
                satisfied=True,
            )
        ]
    )
    state.record_spatial(
        make_spatial(),
        placement=None,
        placements=state.furniture,
        compatibility=compatibility,
    )
    assert state.concept_compatibility is compatibility

    # A different basket no longer justifies that layout.
    state.record_recommendation(recommend_item(item_id="wardrobe"))

    assert state.spatial is None
    assert state.placement is None
    assert state.concept_compatibility is None


def test_storing_spatial_keeps_the_compatibility_verdict() -> None:
    """Compatibility judges the stored coordinates, so it lives with them."""

    state = complete_with(recommend_item(preferred_wall=Wall.EAST))
    compatibility = ConceptCompatibility(
        checks=[
            IntentCheck(
                item_id="bed_double",
                label="Double bed",
                preferred_wall=Wall.EAST,
                satisfied=False,
                note="Requested east, placed west instead.",
            )
        ]
    )

    dropped = state.record_spatial(make_spatial(), compatibility=compatibility)

    assert DataKey.EVALUATION in dropped
    assert state.concept_compatibility == compatibility

    state.record_budget_analysis(make_analysis())
    state.record_evaluation(make_evaluation())
    assert state.finalize().concept_compatibility == compatibility


def test_a_changed_wall_reaches_the_final_result() -> None:
    """The finalised snapshot reports the intent that is actually stored."""

    state = complete_with(recommend_item(preferred_wall=Wall.EAST))

    result = state.finalize()

    assert result.recommendations[0].preferred_wall is Wall.EAST


def test_setting_materials_without_furniture_is_refused() -> None:
    state = through_concepts()
    with pytest.raises(WorkflowError):
        state.set_materials([])


# --------------------------------------------------------------------------- #
# 6. Failure leaves the state intact
# --------------------------------------------------------------------------- #


def test_failed_step_records_nothing() -> None:
    state = with_inputs()

    def boom() -> DesignBrief:
        raise TimeoutError("The AI provider did not answer.")

    with pytest.raises(StepFailed) as excinfo:
        state.attempt(WorkflowStep.BRIEF_ANALYSIS, boom, state.record_brief)

    assert state.brief is None
    assert isinstance(excinfo.value.cause, TimeoutError)
    assert state.next_step is WorkflowStep.BRIEF_ANALYSIS


def test_failed_step_preserves_previously_valid_results() -> None:
    state = complete()

    def boom() -> DesignEvaluation:
        raise RuntimeError("correction failed")

    with pytest.raises(StepFailed):
        state.attempt(WorkflowStep.DESIGN_EVALUATION, boom, state.record_evaluation)

    assert state.evaluation is not None
    assert state.spatial is not None


def test_failed_step_does_not_partially_apply() -> None:
    state = with_inputs()
    state.record_brief(make_brief())

    def boom() -> ConceptCollection:
        raise ValueError("truncated")

    with pytest.raises(StepFailed):
        state.attempt(
            WorkflowStep.CONCEPT_GENERATION, boom, state.record_concepts
        )
    assert state.concepts is None


def test_attempt_returns_the_recorded_value() -> None:
    state = with_inputs()
    brief = state.attempt(
        WorkflowStep.BRIEF_ANALYSIS, make_brief, state.record_brief
    )
    assert brief == state.brief


def test_attempt_still_guards_prerequisites() -> None:
    state = WorkflowState()
    with pytest.raises(PrerequisiteError):
        state.attempt(
            WorkflowStep.BRIEF_ANALYSIS, make_brief, state.record_brief
        )


def test_step_failed_preserves_the_original_exception() -> None:
    state = with_inputs()

    def boom() -> DesignBrief:
        raise KeyError("catalog_missing")

    with pytest.raises(StepFailed) as excinfo:
        state.attempt(WorkflowStep.BRIEF_ANALYSIS, boom, state.record_brief)
    assert isinstance(excinfo.value.__cause__, KeyError)


# --------------------------------------------------------------------------- #
# 7. Invalidation log
# --------------------------------------------------------------------------- #


def test_invalidation_log_records_the_cause() -> None:
    state = complete()
    state.set_budget(BudgetInput(total_budget=Decimal("30000.00")))
    cause, dropped = state.invalidation_log[-1]
    assert cause is DataKey.BUDGET
    assert DataKey.BRIEF in dropped


def test_no_op_changes_do_not_log() -> None:
    state = complete()
    before = len(state.invalidation_log)
    state.set_budget(BudgetInput(total_budget=Decimal("45000.00")))
    assert len(state.invalidation_log) == before


# --------------------------------------------------------------------------- #
# 8. Views and final result
# --------------------------------------------------------------------------- #


def test_as_recommendation_rebuilds_the_advisor_answer() -> None:
    state = complete()
    rebuilt = state.as_recommendation()
    assert rebuilt is not None
    assert rebuilt.furniture == list(state.furniture)
    assert rebuilt.materials == list(state.materials)
    assert rebuilt.color_direction == state.color_direction


def test_as_recommendation_is_none_without_furniture() -> None:
    assert through_concepts().as_recommendation() is None


def test_build_result_returns_a_project_result() -> None:
    result = complete().build_result()
    assert result.selected_concept.name == "Quiet Oak"
    assert len(result.recommendations) == 1
    assert result.budget_analysis.total_estimated == Decimal("18500.00")


def test_build_result_refuses_a_partial_project() -> None:
    state = through_recommendations()
    with pytest.raises(IncompleteWorkflowError) as excinfo:
        state.build_result()
    assert WorkflowStep.SPATIAL_VALIDATION in excinfo.value.missing
    assert WorkflowStep.BUDGET_ANALYSIS in excinfo.value.missing


def test_build_result_after_a_budget_change_refuses() -> None:
    state = complete()
    state.set_budget(BudgetInput(total_budget=Decimal("30000.00")))
    with pytest.raises(IncompleteWorkflowError):
        state.build_result()


def test_outstanding_steps_lists_everything_remaining() -> None:
    state = through_concepts()
    outstanding = state.outstanding_steps()
    assert outstanding[0] is WorkflowStep.RECOMMENDATIONS
    assert outstanding[-1] is WorkflowStep.FINAL_RESULT


def test_completed_steps_are_contiguous_from_the_start() -> None:
    state = through_recommendations()
    completed = state.completed_steps
    assert completed == STEP_ORDER[: len(completed)]


def test_data_for_reads_each_key() -> None:
    state = complete()
    assert state.data_for(DataKey.BRIEF) is state.brief
    assert state.data_for(DataKey.FURNITURE) == state.furniture
    assert state.data_for(DataKey.EVALUATION) is state.evaluation
    assert state.data_for(DataKey.ROOM_TYPE) is state.room


def test_data_for_returns_none_for_absent_results() -> None:
    assert WorkflowState().data_for(DataKey.BRIEF) is None


# --------------------------------------------------------------------------- #
# 9. Finalisation and staleness of the stored report
# --------------------------------------------------------------------------- #


def test_finalize_stores_the_result() -> None:
    state = complete()
    result = state.finalize()
    assert state.result is result
    assert state.is_finished


def test_finalize_requires_a_complete_workflow() -> None:
    state = through_recommendations()
    with pytest.raises(PrerequisiteError):
        state.finalize()
    assert state.result is None


def test_editing_after_finalising_clears_the_stored_report() -> None:
    # A report that describes a previous version of the project is worse than
    # no report at all: it looks authoritative and is wrong.
    state = complete()
    state.finalize()
    assert state.result is not None

    state.set_budget(BudgetInput(total_budget=Decimal("30000.00")))
    assert state.result is None
    assert not state.is_finished


def test_finalised_report_matches_the_current_state() -> None:
    state = complete()
    result = state.finalize()
    assert result.room == state.room
    assert result.selected_concept == state.selected_concept
    assert result.recommendations == list(state.furniture)


def test_project_result_from_state_is_self_consistent() -> None:
    # core.validation recomputes the stored arithmetic rather than trusting it.
    import json
    from pathlib import Path

    from core.validation import validate_result_consistency
    from models.schemas import FurnitureItem

    path = Path(__file__).resolve().parents[1] / "data" / "furniture_catalog.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    catalog = [FurnitureItem.model_validate(entry) for entry in payload["items"]]

    state = complete()
    result = state.finalize()
    findings = validate_result_consistency(result, catalog)
    assert findings == []


def test_final_result_step_is_not_complete_before_finalize() -> None:
    state = complete()
    assert state.is_complete(WorkflowStep.DESIGN_EVALUATION)
    assert not state.is_complete(WorkflowStep.FINAL_RESULT)


# --------------------------------------------------------------------------- #
# 10. Architectural boundaries
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "module_name", ["workflow", "workflow.state", "workflow.dependencies"]
)
def test_workflow_modules_do_not_import_streamlit(module_name: str) -> None:
    import importlib

    module = importlib.import_module(module_name)
    source = module.__file__
    assert source is not None
    with open(source, encoding="utf-8") as handle:
        text = handle.read()
    assert "import streamlit" not in text
    assert "from streamlit" not in text


@pytest.mark.parametrize(
    "module_name", ["workflow", "workflow.state", "workflow.dependencies"]
)
def test_workflow_modules_do_not_import_the_ai_layer(module_name: str) -> None:
    # The workflow receives results through callables; it never runs a prompt or
    # touches a credential.
    import importlib

    module = importlib.import_module(module_name)
    source = module.__file__
    assert source is not None
    with open(source, encoding="utf-8") as handle:
        text = handle.read()
    assert "import ai" not in text
    assert "from ai" not in text


@pytest.mark.parametrize("module_name", ["workflow.state", "workflow.dependencies"])
def test_workflow_modules_perform_no_http(module_name: str) -> None:
    import importlib

    module = importlib.import_module(module_name)
    source = module.__file__
    assert source is not None
    with open(source, encoding="utf-8") as handle:
        text = handle.read()
    for forbidden in (
        "import urllib",
        "import requests",
        "import socket",
        "http.client",
    ):
        assert forbidden not in text


@pytest.mark.parametrize("module_name", ["workflow.state", "workflow.dependencies"])
def test_workflow_modules_read_no_credentials(module_name: str) -> None:
    import importlib

    module = importlib.import_module(module_name)
    source = module.__file__
    assert source is not None
    with open(source, encoding="utf-8") as handle:
        text = handle.read()
    assert "os.environ" not in text
    assert "DEPLOY_API_KEY" not in text


def test_workflow_state_performs_no_arithmetic() -> None:
    # Structural guard: no Decimal/float arithmetic in the state module. Every
    # figure it holds was computed by core and is stored verbatim.
    import workflow.state as state_module

    source = state_module.__file__
    assert source is not None
    with open(source, encoding="utf-8") as handle:
        text = handle.read()
    assert "Decimal(" not in text
