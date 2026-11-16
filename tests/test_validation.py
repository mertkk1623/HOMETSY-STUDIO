"""Tests for the consolidated validation engine."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from core.validation import (
    ERROR,
    STAGE_BUDGET,
    STAGE_CATALOG,
    STAGE_CONSISTENCY,
    STAGE_PLACEMENT,
    STAGE_ROOM,
    WARNING,
    ValidationFinding,
    budget_findings,
    merge_findings,
    placement_findings,
    run_validation,
    spatial_validation_findings,
    validate_budget_input,
    validate_catalog_references,
    validate_inputs,
    validate_result_consistency,
    validate_room_input,
)
from core.budget_engine import compute_budget
from core.spatial_engine import make_footprint, validate_placement
from models.schemas import (
    BudgetInput,
    DesignPreferences,
    DesignStyle,
    FurnitureItem,
    FurnitureRecommendation,
    OpeningInput,
    PaletteDirection,
    RoomInput,
    RoomType,
    SpatialValidation,
    UserRequirements,
    Wall,
)

CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "furniture_catalog.json"


@pytest.fixture(scope="module")
def catalog() -> list[FurnitureItem]:
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return [FurnitureItem(**record) for record in payload["items"]]


def codes(findings) -> list[str]:
    return [finding.code for finding in findings]


def codes_in(report, stage: str) -> list[str]:
    return [finding.code for finding in report.findings if finding.stage == stage]


def basket() -> list[FurnitureRecommendation]:
    return [
        FurnitureRecommendation(
            item_id="sofa_three_seat",
            quantity=1,
            position_x_cm=0,
            position_y_cm=200,
        ),
        FurnitureRecommendation(
            item_id="coffee_table",
            quantity=1,
            position_x_cm=0,
            position_y_cm=100,
        ),
    ]


def budget(amount: str = "45000.00") -> BudgetInput:
    return BudgetInput(total_budget=Decimal(amount))


# --------------------------------------------------------------------------- #
# Room input validation
# --------------------------------------------------------------------------- #


def test_valid_room_produces_no_findings(room: RoomInput) -> None:
    assert validate_room_input(room) == []


def test_room_problem_is_reported_as_an_error(room: RoomInput) -> None:
    broken = room.model_copy(update={"window": room.window.model_copy(
        update={"offset_cm": 380.0}
    )})
    findings = validate_room_input(broken)
    assert findings
    assert all(finding.severity == ERROR for finding in findings)
    assert all(finding.stage == STAGE_ROOM for finding in findings)


def test_overlapping_openings_are_reported(room: RoomInput) -> None:
    conflicting = room.model_copy(
        update={
            "door": room.door.model_copy(
                update={"wall": Wall.NORTH, "offset_cm": 100}
            ),
            "window": room.window.model_copy(
                update={"offset_cm": 120, "width_cm": 160}
            ),
        }
    )
    assert "opening_conflict" in codes(validate_room_input(conflicting))


# --------------------------------------------------------------------------- #
# Budget input validation
# --------------------------------------------------------------------------- #


def test_valid_budget_passes() -> None:
    assert validate_budget_input(budget()) == []


def test_zero_budget_is_an_accepted_input() -> None:
    # Zero is a legitimate input; usage is simply undefined later.
    assert validate_budget_input(budget("0.00")) == []


def test_negative_budget_is_reported() -> None:
    malformed = BudgetInput.model_construct(
        total_budget=Decimal("-1.00"), currency="TRY"
    )
    findings = validate_budget_input(malformed)
    assert codes(findings) == ["invalid_budget"]
    assert findings[0].severity == ERROR


def test_non_decimal_budget_is_reported() -> None:
    malformed = BudgetInput.model_construct(total_budget=100, currency="TRY")
    assert codes(validate_budget_input(malformed)) == ["invalid_budget"]


# --------------------------------------------------------------------------- #
# Combined input validation
# --------------------------------------------------------------------------- #


def test_inputs_with_a_thin_brief_warn(room: RoomInput) -> None:
    # Neither material preferences nor functional requirements were provided.
    thin = DesignPreferences(
        style=DesignStyle.JAPANDI, palette=PaletteDirection.WARM_NEUTRAL
    )
    findings = validate_inputs(room, thin, UserRequirements(), budget())
    assert "thin_brief" in codes(findings)
    assert all(f.severity == WARNING for f in findings if f.code == "thin_brief")


def test_thin_brief_warning_disappears_with_requirements(
    room: RoomInput,
    preferences: DesignPreferences,
    requirements: UserRequirements,
) -> None:
    findings = validate_inputs(room, preferences, requirements, budget())
    assert "thin_brief" not in codes(findings)


def test_material_preferences_alone_avoid_the_thin_brief_warning(
    room: RoomInput, preferences: DesignPreferences
) -> None:
    findings = validate_inputs(room, preferences, UserRequirements(), budget())
    assert "thin_brief" not in codes(findings)


def test_small_room_warns(preferences: DesignPreferences) -> None:
    small = RoomInput(
        room_type=RoomType.BEDROOM,
        name="Box Room",
        width_cm=200,
        length_cm=240,
        ceiling_height_cm=250,
        door=room_door(),
        window=room_window(),
    )
    findings = validate_inputs(
        small, preferences, UserRequirements(notes="x"), budget("1000.00")
    )
    assert "small_room" in codes(findings)


# --------------------------------------------------------------------------- #
# Catalog references
# --------------------------------------------------------------------------- #


def test_valid_references_pass(
    room: RoomInput, catalog: list[FurnitureItem]
) -> None:
    assert validate_catalog_references(room, basket(), catalog) == []


def test_unknown_item_is_an_error(
    room: RoomInput, catalog: list[FurnitureItem]
) -> None:
    findings = validate_catalog_references(
        room, [FurnitureRecommendation(item_id="ghost")], catalog
    )
    assert codes(findings) == ["unknown_catalog_item"]
    assert findings[0].severity == ERROR


def test_item_for_another_room_type_is_an_error(
    room: RoomInput, catalog: list[FurnitureItem]
) -> None:
    # The double bed is a bedroom item; the fixture is a living room.
    findings = validate_catalog_references(
        room, [FurnitureRecommendation(item_id="bed_double")], catalog
    )
    assert codes(findings) == ["unsupported_room_type"]


# --------------------------------------------------------------------------- #
# Adapting engine output
# --------------------------------------------------------------------------- #


def test_placement_issues_keep_their_severity(room: RoomInput) -> None:
    blocking = make_footprint(
        item_id="a", label="A", left_cm=50, bottom_cm=0, width_cm=100, depth_cm=60
    )
    report = validate_placement(room, [blocking])
    findings = placement_findings(report)
    assert [f.severity for f in findings] == [ERROR]
    assert [f.stage for f in findings] == [STAGE_PLACEMENT]


def test_window_warning_stays_a_warning(room: RoomInput) -> None:
    near_window = make_footprint(
        item_id="a", label="A", left_cm=150, bottom_cm=470, width_cm=50, depth_cm=50
    )
    findings = placement_findings(validate_placement(room, [near_window]))
    assert [f.severity for f in findings] == [WARNING]


def test_spatial_validation_round_trip_is_faithful() -> None:
    validation = SpatialValidation(
        is_valid=False,
        boundary_violations=["outside"],
        overlaps=["collision"],
        warnings=["window"],
    )
    findings = spatial_validation_findings(validation)
    assert [f.severity for f in findings] == [ERROR, ERROR, WARNING]
    assert findings[0].stage == STAGE_PLACEMENT


def test_inconsistent_spatial_validation_is_flagged() -> None:
    contradictory = SpatialValidation(
        is_valid=True, boundary_violations=["outside"], overlaps=[], warnings=[]
    )
    findings = spatial_validation_findings(contradictory)
    assert "inconsistent_spatial_validation" in codes(findings)
    assert any(f.stage == STAGE_CONSISTENCY for f in findings)


def test_budget_errors_become_budget_errors(
    catalog: list[FurnitureItem],
) -> None:
    result = compute_budget(
        budget(), [FurnitureRecommendation(item_id="ghost")], catalog
    )
    findings = budget_findings(result)
    assert [f.severity for f in findings] == [ERROR]
    assert all(f.stage == STAGE_BUDGET for f in findings)
    # The engine's specific code is preserved, not flattened to a generic one.
    # ``unpriced_item`` is deliberately distinct from the catalog stage's
    # ``unknown_catalog_item``: this one explains the effect on the total.
    assert [f.code for f in findings] == ["unpriced_item"]


def test_budget_notice_becomes_a_warning(
    catalog: list[FurnitureItem],
) -> None:
    result = compute_budget(budget("100.00"), basket(), catalog)
    findings = budget_findings(result)
    assert any(f.severity == WARNING for f in findings)


# --------------------------------------------------------------------------- #
# End-to-end
# --------------------------------------------------------------------------- #


def test_clean_project_is_valid(
    room: RoomInput,
    preferences: DesignPreferences,
    requirements: UserRequirements,
    catalog: list[FurnitureItem],
) -> None:
    report, placement, budget_result = run_validation(
        room, preferences, requirements, budget(), basket(), catalog
    )
    assert report.is_valid is True
    assert report.errors == ()
    assert placement.is_valid is True
    assert budget_result.is_trustworthy is True


def test_report_groups_findings_by_stage(
    room: RoomInput,
    preferences: DesignPreferences,
    requirements: UserRequirements,
    catalog: list[FurnitureItem],
) -> None:
    crowded = [
        FurnitureRecommendation(
            item_id="sofa_three_seat",
            position_x_cm=0,
            position_y_cm=0,
        )
    ]
    report, _, _ = run_validation(
        room, preferences, requirements, budget("1000.00"), crowded, catalog
    )
    # The sofa sits in the door clearance zone: a placement error.
    assert "door_blocked" in codes_in(report, STAGE_PLACEMENT)
    # The budget is far below the sofa price: a budget warning.
    assert "budget_notice" in codes_in(report, STAGE_BUDGET)
    assert report.is_valid is False


def test_report_messages_can_be_filtered_by_stage(
    room: RoomInput,
    preferences: DesignPreferences,
    requirements: UserRequirements,
    catalog: list[FurnitureItem],
) -> None:
    crowded = [
        FurnitureRecommendation(
            item_id="sofa_three_seat", position_x_cm=0, position_y_cm=0
        )
    ]
    report, _, _ = run_validation(
        room, preferences, requirements, budget("1000.00"), crowded, catalog
    )
    assert report.messages(STAGE_PLACEMENT)
    assert report.messages(STAGE_BUDGET)
    assert report.error_messages(STAGE_PLACEMENT)
    assert all(isinstance(m, str) for m in report.warning_messages())


def test_empty_layout_is_valid_but_reports_no_lines(
    room: RoomInput,
    preferences: DesignPreferences,
    requirements: UserRequirements,
    catalog: list[FurnitureItem],
) -> None:
    report, placement, budget_result = run_validation(
        room, preferences, requirements, budget(), [], catalog
    )
    assert placement.footprints == ()
    assert budget_result.line_count == 0
    assert budget_result.analysis.total_estimated == Decimal("0.00")
    assert STAGE_CONSISTENCY not in codes_in(report, STAGE_CONSISTENCY)


def test_unknown_item_is_reported_once_per_stage(
    room: RoomInput,
    preferences: DesignPreferences,
    requirements: UserRequirements,
    catalog: list[FurnitureItem],
) -> None:
    report, _, _ = run_validation(
        room,
        preferences,
        requirements,
        budget(),
        [FurnitureRecommendation(item_id="ghost")],
        catalog,
    )
    unknown = [f for f in report.findings if f.code == "unknown_catalog_item"]
    # The catalog stage owns this problem; the spatial and budget engines also
    # see it but must not repeat it to the user.
    assert len(unknown) == 1
    assert unknown[0].stage == STAGE_CATALOG


def test_single_finding_per_problem_in_an_end_to_end_run(
    room: RoomInput,
    preferences: DesignPreferences,
    requirements: UserRequirements,
    catalog: list[FurnitureItem],
) -> None:
    report, placement, budget_result = run_validation(
        room,
        preferences,
        requirements,
        budget(),
        [FurnitureRecommendation(item_id="ghost")],
        catalog,
    )
    messages = [f.message for f in report.findings]
    assert len(messages) == len(set(messages))
    # The engines themselves still know, even though the report is deduplicated.
    assert any(i.code == "unknown_catalog_item" for i in placement.issues)
    assert budget_result.is_trustworthy is False


# --------------------------------------------------------------------------- #
# Stored result consistency
# --------------------------------------------------------------------------- #


def test_consistent_result_passes(
    project_result, catalog: list[FurnitureItem]
) -> None:
    # The Phase 1 fixture is internally consistent.
    assert validate_result_consistency(project_result, catalog) == []


def test_mismatched_total_is_caught(
    project_result, catalog: list[FurnitureItem]
) -> None:
    broken = project_result.model_copy(
        update={
            "budget_analysis": project_result.budget_analysis.model_copy(
                update={"total_estimated": Decimal("99999.00")}
            )
        }
    )
    assert "budget_total_mismatch" in codes(
        validate_result_consistency(broken, catalog)
    )


def test_mismatched_remaining_is_caught(
    project_result, catalog: list[FurnitureItem]
) -> None:
    broken = project_result.model_copy(
        update={
            "budget_analysis": project_result.budget_analysis.model_copy(
                update={"remaining_budget": Decimal("1.00")}
            )
        }
    )
    assert "budget_remaining_mismatch" in codes(
        validate_result_consistency(broken, catalog)
    )


def test_contradictory_over_budget_flag_is_caught(
    project_result, catalog: list[FurnitureItem]
) -> None:
    broken = project_result.model_copy(
        update={
            "budget_analysis": project_result.budget_analysis.model_copy(
                update={"is_over_budget": True}
            )
        }
    )
    assert "budget_flag_mismatch" in codes(
        validate_result_consistency(broken, catalog)
    )


def test_unknown_catalog_item_in_a_stored_result_is_caught(
    project_result, catalog: list[FurnitureItem]
) -> None:
    broken = project_result.model_copy(
        update={"recommendations": [FurnitureRecommendation(item_id="ghost")]}
    )
    assert "unknown_catalog_item" in codes(
        validate_result_consistency(broken, catalog)
    )


# --------------------------------------------------------------------------- #
# Report merging
# --------------------------------------------------------------------------- #


def test_merge_concatenates_in_order() -> None:
    first = [
        ValidationFinding(
            stage=STAGE_ROOM, severity=ERROR, code="a", message="A problem."
        )
    ]
    second = [
        ValidationFinding(
            stage=STAGE_BUDGET, severity=WARNING, code="b", message="A notice."
        )
    ]
    merged = merge_findings(first, second)
    assert codes(merged.findings) == ["a", "b"]
    assert merged.is_valid is False
    assert merged.warnings[0].code == "b"


def test_merge_deduplicates_an_authoritative_code() -> None:
    catalog_side = ValidationFinding(
        stage=STAGE_CATALOG,
        severity=ERROR,
        code="unknown_catalog_item",
        message="Unknown item.",
    )
    placement_side = ValidationFinding(
        stage=STAGE_PLACEMENT,
        severity=ERROR,
        code="unknown_catalog_item",
        message="Unknown item.",
    )
    merged = merge_findings([catalog_side], [placement_side])
    assert len(merged.findings) == 1
    assert merged.findings[0].stage == STAGE_CATALOG


def test_merge_keeps_a_code_when_no_owner_reported_it() -> None:
    # Without a catalog-stage finding there is nothing to replace it with, so a
    # real problem must survive rather than be dropped.
    placement_side = ValidationFinding(
        stage=STAGE_PLACEMENT,
        severity=ERROR,
        code="unknown_catalog_item",
        message="Unknown item.",
    )
    merged = merge_findings([placement_side])
    assert len(merged.findings) == 1


def test_empty_merge_is_valid() -> None:
    assert merge_findings().is_valid is True


def room_door() -> OpeningInput:
    return OpeningInput(wall=Wall.SOUTH, offset_cm=20, width_cm=80)


def room_window() -> OpeningInput:
    return OpeningInput(wall=Wall.NORTH, offset_cm=20, width_cm=60)
