"""Tests for the foundational Pydantic models.

Covers the Phase 1 acceptance criteria: valid and invalid room input, opening
placement, preferences, budget, the three-concept rule and the consolidated
project result. No AI, geometry or budget arithmetic is exercised here.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from models.schemas import (
    BudgetAnalysis,
    BudgetInput,
    ConceptCollection,
    ConceptCompatibility,
    DesignEvaluation,
    DesignPreferences,
    DesignConcept,
    DesignStyle,
    FurnitureItem,
    FurnitureRecommendation,
    IntentCheck,
    OpeningInput,
    PaletteDirection,
    ProjectResult,
    RoomInput,
    RoomType,
    SpatialValidation,
    UserRequirements,
    Wall,
    WallPreference,
)

# --------------------------------------------------------------------------- #
# Room input
# --------------------------------------------------------------------------- #


def test_valid_room_input(room: RoomInput) -> None:
    assert room.room_type is RoomType.LIVING_ROOM
    assert room.width_cm == 400
    assert room.length_cm == 520
    assert room.ceiling_height_cm == 270


def test_room_area_is_reported_in_square_meters(room: RoomInput) -> None:
    # 400 cm x 520 cm == 20.8 m²
    assert room.area_sqm == pytest.approx(20.8)


def test_ceiling_height_defaults_to_270_cm(room: RoomInput) -> None:
    data = room.model_dump(exclude={"ceiling_height_cm"})
    assert RoomInput(**data).ceiling_height_cm == 270


@pytest.mark.parametrize("dimension", ["width_cm", "length_cm"])
@pytest.mark.parametrize("value", [99, 0, -250, 2001])
def test_invalid_room_dimensions_are_rejected(room, dimension, value) -> None:
    data = room.model_dump()
    data[dimension] = value
    with pytest.raises(ValidationError):
        RoomInput(**data)


@pytest.mark.parametrize("value", [199, 501])
def test_invalid_ceiling_height_is_rejected(room, value) -> None:
    data = room.model_dump()
    data["ceiling_height_cm"] = value
    with pytest.raises(ValidationError):
        RoomInput(**data)


def test_unsupported_room_type_is_rejected(room) -> None:
    data = room.model_dump()
    data["room_type"] = "Kitchen"
    with pytest.raises(ValidationError):
        RoomInput(**data)


def test_unknown_field_is_rejected(room) -> None:
    data = room.model_dump()
    data["colour"] = "green"
    with pytest.raises(ValidationError):
        RoomInput(**data)


def test_blank_room_name_is_rejected(room) -> None:
    data = room.model_dump()
    data["name"] = "   "
    with pytest.raises(ValidationError):
        RoomInput(**data)


# --------------------------------------------------------------------------- #
# Openings
# --------------------------------------------------------------------------- #


def test_valid_opening_data(room: RoomInput) -> None:
    assert room.door.wall is Wall.SOUTH
    assert room.door.offset_cm + room.door.width_cm <= room.width_cm
    assert room.window.wall is Wall.NORTH


def test_wall_span_follows_wall_orientation(room: RoomInput) -> None:
    assert room.wall_span_cm(Wall.NORTH) == 400
    assert room.wall_span_cm(Wall.SOUTH) == 400
    assert room.wall_span_cm(Wall.EAST) == 520
    assert room.wall_span_cm(Wall.WEST) == 520


@pytest.mark.parametrize("field_name", ["door", "window"])
def test_opening_that_exceeds_its_wall_is_rejected(room, field_name) -> None:
    data = room.model_dump()
    data[field_name]["offset_cm"] = 380
    data[field_name]["width_cm"] = 90  # 380 + 90 > 400
    with pytest.raises(ValidationError):
        RoomInput(**data)


@pytest.mark.parametrize("value", [-1, -50])
def test_negative_opening_offset_is_rejected(value) -> None:
    with pytest.raises(ValidationError):
        OpeningInput(wall=Wall.SOUTH, offset_cm=value, width_cm=90)


@pytest.mark.parametrize("value", [0, 39, 2001])
def test_invalid_opening_width_is_rejected(value) -> None:
    with pytest.raises(ValidationError):
        OpeningInput(wall=Wall.SOUTH, offset_cm=10, width_cm=value)


def test_unknown_wall_is_rejected() -> None:
    with pytest.raises(ValidationError):
        OpeningInput(wall="ceiling", offset_cm=10, width_cm=90)


def test_opening_offset_at_exact_wall_end_is_accepted() -> None:
    opening = OpeningInput(wall=Wall.SOUTH, offset_cm=310, width_cm=90)
    assert opening.offset_cm + opening.width_cm == 400


# --------------------------------------------------------------------------- #
# Preferences and requirements
# --------------------------------------------------------------------------- #


def test_valid_design_preferences(preferences: DesignPreferences) -> None:
    assert preferences.style is DesignStyle.JAPANDI
    assert preferences.palette is PaletteDirection.WARM_NEUTRAL
    assert preferences.material_preferences == ["oak", "linen"]


def test_material_preferences_are_optional() -> None:
    preferences = DesignPreferences(
        style=DesignStyle.SCANDINAVIAN, palette=PaletteDirection.COOL_MODERN
    )
    assert preferences.material_preferences == []


def test_invalid_style_is_rejected() -> None:
    with pytest.raises(ValidationError):
        DesignPreferences(style="Art Deco", palette=PaletteDirection.EARTHY)


def test_only_one_palette_is_accepted() -> None:
    with pytest.raises(ValidationError):
        DesignPreferences(
            style=DesignStyle.INDUSTRIAL,
            palette=[PaletteDirection.EARTHY, PaletteDirection.COOL_MODERN],
        )


def test_user_requirements_default_to_empty() -> None:
    requirements = UserRequirements()
    assert requirements.functional_requirements == []
    assert requirements.notes == ""


# --------------------------------------------------------------------------- #
# Budget
# --------------------------------------------------------------------------- #


def test_valid_budget(budget: BudgetInput) -> None:
    assert budget.total_budget == Decimal("45000.00")
    assert budget.currency == "TRY"


def test_budget_is_stored_as_decimal() -> None:
    budget = BudgetInput(total_budget="12500.50")
    assert isinstance(budget.total_budget, Decimal)
    assert budget.total_budget == Decimal("12500.50")


@pytest.mark.parametrize("value", [-1, "-0.01", "not-a-number"])
def test_invalid_budget_is_rejected(value) -> None:
    with pytest.raises(ValidationError):
        BudgetInput(total_budget=value)


def test_unsupported_currency_is_rejected() -> None:
    with pytest.raises(ValidationError):
        BudgetInput(total_budget=Decimal("1000"), currency="USD")


def test_budget_analysis_rejects_negative_amounts() -> None:
    with pytest.raises(ValidationError):
        BudgetAnalysis(furniture_subtotal=Decimal("-1"))


# --------------------------------------------------------------------------- #
# Concepts
# --------------------------------------------------------------------------- #


def test_exactly_three_concepts_are_accepted(concepts: ConceptCollection) -> None:
    assert len(concepts.concepts) == 3
    assert concepts.concepts[0].name == "Quiet Oak"


def _concept(name: str) -> DesignConcept:
    return DesignConcept(
        name=name,
        description="A conceptual description.",
        design_direction="Direction.",
        color_and_material_direction="Color and material direction.",
        furniture_approach="Furniture approach.",
        functional_rationale="Functional rationale.",
        budget_suitability="Budget suitability.",
    )


@pytest.mark.parametrize("count", [0, 1, 2, 4])
def test_concept_count_must_be_three(count) -> None:
    generated = [_concept(f"Concept {index}") for index in range(count)]
    with pytest.raises(ValidationError):
        ConceptCollection(concepts=generated)


def test_duplicate_concept_names_are_rejected(concepts) -> None:
    duplicated = [concepts.concepts[0], concepts.concepts[0], concepts.concepts[1]]
    with pytest.raises(ValidationError):
        ConceptCollection(concepts=duplicated)


# --------------------------------------------------------------------------- #
# Catalog and recommendations
# --------------------------------------------------------------------------- #


def test_valid_catalog_item() -> None:
    item = FurnitureItem(
        item_id="sofa_3_seat",
        name="Three-seat sofa",
        category="Seating",
        width_cm=220,
        depth_cm=90,
        indicative_unit_cost=Decimal("18000.00"),
        supported_room_types=[RoomType.LIVING_ROOM],
    )
    assert item.drawing_shape == "rectangle"


def test_catalog_item_requires_a_supported_room_type() -> None:
    with pytest.raises(ValidationError):
        FurnitureItem(
            item_id="sofa_3_seat",
            name="Three-seat sofa",
            category="Seating",
            width_cm=220,
            depth_cm=90,
            indicative_unit_cost=Decimal("18000.00"),
            supported_room_types=[],
        )


def test_recommendation_placement_is_optional() -> None:
    recommendation = FurnitureRecommendation(item_id="sofa_3_seat")
    assert recommendation.position_x_cm is None
    assert recommendation.rotation_degrees == 0


def test_recommendation_rejects_unapproved_rotation() -> None:
    with pytest.raises(ValidationError):
        FurnitureRecommendation(item_id="sofa_3_seat", rotation_degrees=45)


# --------------------------------------------------------------------------- #
# Layout intent
# --------------------------------------------------------------------------- #


def test_layout_intent_is_absent_by_default() -> None:
    """An item with no preference is exactly the pre-intent request."""

    recommendation = FurnitureRecommendation(item_id="sofa_3_seat")
    assert recommendation.preferred_wall is None
    assert recommendation.wall_priority is WallPreference.PREFERRED


def test_layout_intent_accepts_a_named_wall() -> None:
    recommendation = FurnitureRecommendation(
        item_id="bed_double", preferred_wall=Wall.WEST
    )
    assert recommendation.preferred_wall is Wall.WEST
    # Naming a wall does not make it binding.
    assert recommendation.wall_priority is WallPreference.PREFERRED


def test_layout_intent_accepts_required_priority() -> None:
    recommendation = FurnitureRecommendation(
        item_id="bed_double",
        preferred_wall=Wall.WEST,
        wall_priority=WallPreference.REQUIRED,
    )
    assert recommendation.wall_priority is WallPreference.REQUIRED


def test_layout_intent_rejects_a_required_priority_without_a_wall() -> None:
    """Nothing can be required of a wall that was never named."""

    with pytest.raises(ValidationError, match="no preferred_wall"):
        FurnitureRecommendation(
            item_id="bed_double", wall_priority=WallPreference.REQUIRED
        )


def test_layout_intent_rejects_an_unknown_wall() -> None:
    with pytest.raises(ValidationError):
        FurnitureRecommendation(
            item_id="bed_double", preferred_wall="north-east"
        )


def test_layout_intent_rejects_an_unknown_priority() -> None:
    with pytest.raises(ValidationError):
        FurnitureRecommendation(
            item_id="bed_double",
            preferred_wall=Wall.WEST,
            wall_priority="mandatory",
        )


def test_old_recommendation_data_without_intent_still_parses() -> None:
    """Projects stored before intent support must load unchanged.

    The JSON below is the shape written by the previous release: no
    ``preferred_wall`` and no ``wall_priority`` key at all.
    """

    legacy = {
        "item_id": "bed_double",
        "quantity": 1,
        "rotation_degrees": 0,
        "position_x_cm": 0.0,
        "position_y_cm": 130.0,
        "positions": [],
        "rationale": "Centred on the west wall.",
    }

    recommendation = FurnitureRecommendation.model_validate(legacy)

    assert recommendation.preferred_wall is None
    assert recommendation.wall_priority is WallPreference.PREFERRED
    assert recommendation.position_x_cm == 0.0


def test_concept_compatibility_counts_only_known_verdicts() -> None:
    """A verdict is three-valued, and ``None`` is never counted as satisfied."""

    compatibility = ConceptCompatibility(
        checks=[
            IntentCheck(
                item_id="bed_double",
                label="Double bed",
                preferred_wall=Wall.WEST,
                satisfied=True,
            ),
            IntentCheck(
                item_id="desk",
                label="Desk",
                preferred_wall=Wall.EAST,
                satisfied=False,
                note="Requested east, placed north instead.",
            ),
            IntentCheck(
                item_id="wardrobe",
                label="Wardrobe",
                preferred_wall=Wall.NORTH,
                priority=WallPreference.REQUIRED,
                satisfied=None,
            ),
        ]
    )

    assert compatibility.is_evaluated is True
    assert compatibility.satisfied_count == 1
    assert compatibility.unmet_count == 1
    assert compatibility.unknown_count == 1
    assert compatibility.is_fully_satisfied is False
    assert [check.item_id for check in compatibility.unmet] == ["desk"]


def test_concept_compatibility_without_checks_is_not_evaluated() -> None:
    compatibility = ConceptCompatibility(
        note="No layout intent was recorded for this project."
    )
    assert compatibility.is_evaluated is False
    assert compatibility.satisfied_count == 0
    # "Nothing was asked for" must not read as "everything was met".
    assert compatibility.is_fully_satisfied is False


def test_project_result_treats_compatibility_as_optional(
    project_result: ProjectResult,
) -> None:
    """A result assembled before intent support still validates."""

    assert project_result.concept_compatibility is None

    data = project_result.model_dump()
    assert "concept_compatibility" in data
    restored = ProjectResult(**data)
    assert restored.concept_compatibility is None


# --------------------------------------------------------------------------- #
# Project result
# --------------------------------------------------------------------------- #


def test_project_result_accepts_consistent_data(project_result: ProjectResult) -> None:
    assert project_result.room.area_sqm == pytest.approx(20.8)
    assert len(project_result.concepts.concepts) == 3
    assert project_result.spatial_validation.is_valid is True


def test_project_result_rejects_selected_concept_outside_collection(
    project_result: ProjectResult,
) -> None:
    data = project_result.model_dump()
    data["selected_concept"]["name"] = "Unrelated concept"
    with pytest.raises(ValidationError):
        ProjectResult(**data)


def test_project_result_requires_recommendations(project_result: ProjectResult) -> None:
    data = project_result.model_dump()
    data["recommendations"] = []
    with pytest.raises(ValidationError):
        ProjectResult(**data)


def test_spatial_validation_separates_errors_from_warnings() -> None:
    validation = SpatialValidation(
        is_valid=False,
        overlaps=["Sofa overlaps coffee table"],
        warnings=["Circulation path is narrow"],
    )
    assert validation.is_valid is False
    assert validation.boundary_violations == []


def test_design_evaluation_requires_assessments() -> None:
    with pytest.raises(ValidationError):
        DesignEvaluation(
            requirement_compatibility="Fits the brief.",
            style_consistency="Consistent.",
            functional_suitability="Workable.",
        )
