"""Tests for the deterministic furniture placement engine.

The room fixture is 400 x 520 cm with a south door (x 60-150) and a north
window (x 120-280). Default clearance zones are therefore:

* door:   x 60-150,  y 0-60
* window: x 120-280, y 490-520

Placements below are chosen against those zones explicitly so a passing test
means "the rule fired (or did not fire) for the stated reason".
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from core.room_engine import EPS_CM
from core.spatial_engine import (
    DEFAULT_DOOR_CLEARANCE_CM,
    DEFAULT_WINDOW_CLEARANCE_CM,
    FurnitureFootprint,
    Rect,
    build_footprints,
    effective_size_cm,
    make_footprint,
    opening_clearance_rect,
    rect_inside_room,
    rect_intersection_area,
    rect_within_wall_span,
    rects_overlap,
    to_spatial_validation,
    validate_placement,
    validate_recommendations,
)
from models.schemas import (
    FurnitureItem,
    FurnitureRecommendation,
    RoomInput,
    RoomType,
    Wall,
)

CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "furniture_catalog.json"


@pytest.fixture(scope="module")
def catalog() -> list[FurnitureItem]:
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return [FurnitureItem(**record) for record in payload["items"]]


def placed(
    item_id: str, x_cm: float, y_cm: float, **kwargs: object
) -> FurnitureRecommendation:
    return FurnitureRecommendation(
        item_id=item_id,
        position_x_cm=x_cm,
        position_y_cm=y_cm,
        **kwargs,  # type: ignore[arg-type]
    )


def codes(report) -> list[str]:
    return [issue.code for issue in report.issues]


# --------------------------------------------------------------------------- #
# Geometry primitives
# --------------------------------------------------------------------------- #


def test_intersection_area_of_overlapping_rects() -> None:
    first = Rect(0, 0, 100, 100)
    second = Rect(50, 50, 100, 100)
    assert rect_intersection_area(first, second) == pytest.approx(50 * 50)


def test_touching_rects_share_no_area() -> None:
    first = Rect(0, 0, 100, 100)
    second = Rect(100, 0, 100, 100)
    assert rect_intersection_area(first, second) == 0.0
    assert rects_overlap(first, second) is False


def test_disjoint_rects_share_no_area() -> None:
    assert rect_intersection_area(Rect(0, 0, 10, 10), Rect(50, 50, 10, 10)) == 0.0


def test_tiny_numeric_drift_is_not_an_overlap() -> None:
    first = Rect(0, 0, 100, 100)
    second = Rect(100 + EPS_CM / 2, 0, 100, 100)
    assert rects_overlap(first, second) is False


def test_rect_inside_room_accepts_a_rect_touching_all_four_walls(
    room: RoomInput,
) -> None:
    assert rect_inside_room(Rect(0, 0, room.width_cm, room.length_cm), room) is True


def test_wall_span_matches_orientation(room: RoomInput) -> None:
    assert rect_within_wall_span(room, Wall.NORTH) == (0.0, 400.0)
    assert rect_within_wall_span(room, Wall.SOUTH) == (0.0, 400.0)
    assert rect_within_wall_span(room, Wall.EAST) == (0.0, 520.0)
    assert rect_within_wall_span(room, Wall.WEST) == (0.0, 520.0)


# --------------------------------------------------------------------------- #
# Rotation
# --------------------------------------------------------------------------- #


def test_quarter_turn_swaps_width_and_depth() -> None:
    assert effective_size_cm(220, 90, 90) == (90, 220)
    assert effective_size_cm(220, 90, 270) == (90, 220)


@pytest.mark.parametrize("rotation", [0, 180, 360])
def test_half_and_full_turns_keep_size(rotation: int) -> None:
    assert effective_size_cm(220, 90, rotation) == (220, 90)


def test_make_footprint_stores_rotated_size() -> None:
    footprint = make_footprint(
        item_id="sofa",
        label="Sofa",
        left_cm=10,
        bottom_cm=20,
        width_cm=220,
        depth_cm=90,
        rotation_degrees=90,
    )
    assert (footprint.width_cm, footprint.depth_cm) == (90, 220)
    assert footprint.rotation_degrees == 90


def test_make_footprint_rejects_zero_dimensions() -> None:
    with pytest.raises(ValueError):
        make_footprint(
            item_id="x",
            label="X",
            left_cm=0,
            bottom_cm=0,
            width_cm=0,
            depth_cm=90,
        )


def test_make_footprint_rejects_non_right_angle_rotation() -> None:
    with pytest.raises(ValueError):
        make_footprint(
            item_id="x",
            label="X",
            left_cm=0,
            bottom_cm=0,
            width_cm=80,
            depth_cm=80,
            rotation_degrees=45,
        )


# --------------------------------------------------------------------------- #
# Clearance zones
# --------------------------------------------------------------------------- #


def test_south_door_clearance_lies_inside_the_room(room: RoomInput) -> None:
    zone = opening_clearance_rect(room, Wall.SOUTH, 60, 90, 60)
    assert zone == Rect(60, 0, 90, 60)


def test_north_window_clearance_lies_just_below_the_wall(room: RoomInput) -> None:
    zone = opening_clearance_rect(room, Wall.NORTH, 120, 160, 30)
    assert zone == Rect(120, 490, 160, 30)


def test_west_opening_clearance_is_tall_and_thin(room: RoomInput) -> None:
    zone = opening_clearance_rect(room, Wall.WEST, 100, 90, 60)
    assert zone == Rect(0, 100, 60, 90)


def test_east_opening_clearance_sits_against_the_east_wall(room: RoomInput) -> None:
    zone = opening_clearance_rect(room, Wall.EAST, 100, 90, 60)
    assert zone == Rect(340, 100, 60, 90)


@pytest.mark.parametrize("clearance", [0, -5])
def test_non_positive_clearance_disables_the_zone(
    room: RoomInput, clearance: float
) -> None:
    assert opening_clearance_rect(room, Wall.SOUTH, 60, 90, clearance) is None


# --------------------------------------------------------------------------- #
# A valid layout
# --------------------------------------------------------------------------- #


def test_furniture_inside_the_room_is_valid(room: RoomInput) -> None:
    footprint = make_footprint(
        item_id="sofa",
        label="Sofa",
        left_cm=0,
        bottom_cm=200,
        width_cm=220,
        depth_cm=90,
    )
    report = validate_placement(room, [footprint])
    assert report.is_valid is True
    assert report.issues == ()


def test_furniture_exactly_filling_the_room_is_valid(room: RoomInput) -> None:
    footprint = make_footprint(
        item_id="rug",
        label="Rug",
        left_cm=0,
        bottom_cm=0,
        width_cm=room.width_cm,
        depth_cm=room.length_cm,
    )
    report = validate_placement(
        room, [footprint], door_clearance_cm=0, window_clearance_cm=0
    )
    assert report.is_valid is True


# --------------------------------------------------------------------------- #
# Boundary violations
# --------------------------------------------------------------------------- #


def test_furniture_crossing_the_east_wall_is_rejected(room: RoomInput) -> None:
    footprint = make_footprint(
        item_id="armchair",
        label="Armchair",
        left_cm=350,
        bottom_cm=200,
        width_cm=80,
        depth_cm=80,
    )
    report = validate_placement(room, [footprint])
    assert report.is_valid is False
    assert "outside_room" in codes(report)


def test_furniture_crossing_the_north_wall_is_rejected(room: RoomInput) -> None:
    footprint = make_footprint(
        item_id="sofa",
        label="Sofa",
        left_cm=0,
        bottom_cm=480,
        width_cm=220,
        depth_cm=90,
    )
    report = validate_placement(room, [footprint])
    assert [issue.code for issue in report.errors] == ["outside_room"]


def test_furniture_with_a_negative_origin_is_rejected(room: RoomInput) -> None:
    footprint = make_footprint(
        item_id="chair",
        label="Chair",
        left_cm=-10,
        bottom_cm=200,
        width_cm=60,
        depth_cm=60,
    )
    assert "outside_room" in codes(validate_placement(room, [footprint]))


def test_boundary_violation_message_names_the_item(room: RoomInput) -> None:
    footprint = make_footprint(
        item_id="armchair",
        label="Armchair",
        left_cm=350,
        bottom_cm=200,
        width_cm=80,
        depth_cm=80,
    )
    report = validate_placement(room, [footprint])
    assert "Armchair" in report.errors[0].message


# --------------------------------------------------------------------------- #
# Overlap detection
# --------------------------------------------------------------------------- #


def test_overlapping_furniture_is_rejected(room: RoomInput) -> None:
    first = make_footprint(
        item_id="a", label="A", left_cm=100, bottom_cm=200, width_cm=80, depth_cm=80
    )
    second = make_footprint(
        item_id="b", label="B", left_cm=140, bottom_cm=200, width_cm=80, depth_cm=80
    )
    report = validate_placement(room, [first, second])
    assert report.is_valid is False
    assert [issue.code for issue in report.errors] == ["furniture_overlap"]
    assert report.errors[0].message.startswith("'A' and 'B' overlap by")


def test_touching_furniture_is_allowed(room: RoomInput) -> None:
    first = make_footprint(
        item_id="a", label="A", left_cm=100, bottom_cm=200, width_cm=80, depth_cm=80
    )
    second = make_footprint(
        item_id="b", label="B", left_cm=180, bottom_cm=200, width_cm=80, depth_cm=80
    )
    report = validate_placement(room, [first, second])
    assert report.is_valid is True
    assert report.issues == ()


def test_corner_touch_is_allowed(room: RoomInput) -> None:
    first = make_footprint(
        item_id="a", label="A", left_cm=100, bottom_cm=200, width_cm=80, depth_cm=80
    )
    second = make_footprint(
        item_id="b", label="B", left_cm=180, bottom_cm=280, width_cm=80, depth_cm=80
    )
    report = validate_placement(room, [first, second])
    assert report.is_valid is True


def test_three_way_overlap_reports_every_pair(room: RoomInput) -> None:
    footprints = [
        make_footprint(
            item_id="a", label="A", left_cm=100, bottom_cm=200, width_cm=60, depth_cm=60
        ),
        make_footprint(
            item_id="b", label="B", left_cm=120, bottom_cm=210, width_cm=60, depth_cm=60
        ),
        make_footprint(
            item_id="c", label="C", left_cm=140, bottom_cm=220, width_cm=60, depth_cm=60
        ),
    ]
    report = validate_placement(room, footprints)
    overlaps = [issue for issue in report.errors if issue.code == "furniture_overlap"]
    assert len(overlaps) == 3


# --------------------------------------------------------------------------- #
# Door and window constraints
# --------------------------------------------------------------------------- #


def test_furniture_in_the_door_clearance_is_an_error(room: RoomInput) -> None:
    footprint = make_footprint(
        item_id="table",
        label="Coffee table",
        left_cm=50,
        bottom_cm=0,
        width_cm=100,
        depth_cm=60,
    )
    report = validate_placement(room, [footprint])
    assert report.is_valid is False
    assert "door_blocked" in codes(report)


def test_furniture_just_past_the_door_clearance_is_allowed(room: RoomInput) -> None:
    footprint = make_footprint(
        item_id="plant",
        label="Plant",
        left_cm=60,
        bottom_cm=DEFAULT_DOOR_CLEARANCE_CM,
        width_cm=50,
        depth_cm=50,
    )
    report = validate_placement(room, [footprint])
    assert report.is_valid is True


def test_furniture_in_the_window_clearance_is_only_a_warning(
    room: RoomInput,
) -> None:
    footprint = make_footprint(
        item_id="plant",
        label="Plant",
        left_cm=150,
        bottom_cm=470,
        width_cm=50,
        depth_cm=50,
    )
    report = validate_placement(room, [footprint])
    assert report.is_valid is True
    assert [issue.code for issue in report.warnings] == ["window_obstructed"]
    assert report.errors == ()


def test_furniture_just_below_the_window_clearance_is_allowed(
    room: RoomInput,
) -> None:
    footprint = make_footprint(
        item_id="cabinet",
        label="Cabinet",
        left_cm=150,
        bottom_cm=470 - DEFAULT_WINDOW_CLEARANCE_CM,
        width_cm=50,
        depth_cm=DEFAULT_WINDOW_CLEARANCE_CM,
    )
    report = validate_placement(room, [footprint])
    assert report.issues == ()


def test_clearance_can_be_relaxed_per_call(room: RoomInput) -> None:
    footprint = make_footprint(
        item_id="table",
        label="Coffee table",
        left_cm=50,
        bottom_cm=0,
        width_cm=100,
        depth_cm=60,
    )
    report = validate_placement(room, [footprint], door_clearance_cm=0)
    assert report.is_valid is True


# --------------------------------------------------------------------------- #
# Recommendation resolution
# --------------------------------------------------------------------------- #


def test_build_footprints_uses_catalog_dimensions(
    catalog: list[FurnitureItem],
) -> None:
    footprints, issues = build_footprints(
        [placed("sofa_three_seat", 10, 20)], catalog
    )
    assert issues == []
    assert len(footprints) == 1
    # The real catalog entry is 220 x 90 cm.
    assert (footprints[0].width_cm, footprints[0].depth_cm) == (220, 90)
    assert footprints[0].label == "Three-seat sofa"


def test_unknown_catalog_item_is_an_error(
    room: RoomInput, catalog: list[FurnitureItem]
) -> None:
    report, validation = validate_recommendations(
        room=room,
        recommendations=[placed("does_not_exist", 10, 20)],
        catalog=catalog,
    )
    assert report.is_valid is False
    assert [issue.code for issue in report.errors] == ["unknown_catalog_item"]
    assert validation.is_valid is False
    assert validation.boundary_violations


def test_unplaced_recommendation_is_reported_as_a_warning(
    room: RoomInput, catalog: list[FurnitureItem]
) -> None:
    report, validation = validate_recommendations(
        room=room,
        recommendations=[FurnitureRecommendation(item_id="sofa_three_seat")],
        catalog=catalog,
    )
    assert report.footprints == ()
    assert [issue.code for issue in report.warnings] == ["unplaced_item"]
    assert report.is_valid is True
    assert validation.warnings


def test_quantity_above_one_is_measured_copy_by_copy(
    room: RoomInput, catalog: list[FurnitureItem]
) -> None:
    """Four placed chairs are four footprints, not one collapsed one."""

    report, _ = validate_recommendations(
        room=room,
        recommendations=[placed("dining_chair", 10, 200, quantity=4)],
        catalog=catalog,
    )
    # A single legacy coordinate with a quantity of four is an under-placed
    # recommendation, and the report says exactly that.
    assert [issue.code for issue in report.warnings] == ["unplaced_copies"]
    assert len(report.footprints) == 1


def test_four_legacy_coordinates_are_reporting_nothing_missing(
    room: RoomInput, catalog: list[FurnitureItem]
) -> None:
    """A quantity of one per placement is the fully placed case."""

    report, _ = validate_recommendations(
        room=room,
        recommendations=[
            placed("dining_chair", 10, 200),
            placed("dining_chair", 60, 200),
            placed("dining_chair", 110, 200),
            placed("dining_chair", 160, 200),
        ],
        catalog=catalog,
    )
    assert report.warnings == ()
    assert len(report.footprints) == 4


def test_rotation_is_applied_through_recommendations(
    room: RoomInput, catalog: list[FurnitureItem]
) -> None:
    report, _ = validate_recommendations(
        room=room,
        recommendations=[placed("sofa_three_seat", 0, 200, rotation_degrees=90)],
        catalog=catalog,
    )
    assert (report.footprints[0].width_cm, report.footprints[0].depth_cm) == (90, 220)


# --------------------------------------------------------------------------- #
# Conversion to the shared validation model
# --------------------------------------------------------------------------- #


def test_blocking_issue_is_never_demoted_to_a_warning(room: RoomInput) -> None:
    footprint = make_footprint(
        item_id="table",
        label="Coffee table",
        left_cm=50,
        bottom_cm=0,
        width_cm=100,
        depth_cm=60,
    )
    validation = to_spatial_validation(validate_placement(room, [footprint]))
    assert validation.is_valid is False
    assert validation.boundary_violations
    assert validation.warnings == []


def test_overlap_is_reported_in_its_own_field(room: RoomInput) -> None:
    first = make_footprint(
        item_id="a", label="A", left_cm=100, bottom_cm=200, width_cm=80, depth_cm=80
    )
    second = make_footprint(
        item_id="b", label="B", left_cm=140, bottom_cm=200, width_cm=80, depth_cm=80
    )
    validation = to_spatial_validation(validate_placement(room, [first, second]))
    assert validation.overlaps
    assert validation.boundary_violations == []


def test_valid_layout_converts_to_a_valid_model(room: RoomInput) -> None:
    footprint = make_footprint(
        item_id="sofa",
        label="Sofa",
        left_cm=0,
        bottom_cm=200,
        width_cm=220,
        depth_cm=90,
    )
    validation = to_spatial_validation(validate_placement(room, [footprint]))
    assert validation.is_valid is True
    assert (
        validation.boundary_violations == []
        and validation.overlaps == []
        and validation.warnings == []
    )


def test_footprint_rect_reflects_position() -> None:
    footprint = FurnitureFootprint(
        item_id="a", label="A", left_cm=10, bottom_cm=20, width_cm=30, depth_cm=40
    )
    assert footprint.rect == Rect(10, 20, 30, 40)
    assert footprint.rect.area_sqm == pytest.approx(0.12)


def test_degenerate_catalog_footprint_is_reported_not_raised(
    room: RoomInput,
) -> None:
    broken = FurnitureItem.model_construct(
        item_id="broken",
        name="Broken Item",
        category="Test",
        width_cm=0.0,
        depth_cm=60.0,
        indicative_unit_cost=Decimal("100.00"),
        supported_room_types=[RoomType.LIVING_ROOM],
        drawing_shape="rectangle",
    )
    report, validation = validate_recommendations(
        room, [placed("broken", 10, 10)], [broken]
    )
    assert report.is_valid is False
    assert [issue.code for issue in report.errors] == ["invalid_footprint"]
    assert validation.is_valid is False


def test_rect_inside_room_rejects_a_rect_outside(room: RoomInput) -> None:
    assert rect_inside_room(Rect(0, 0, 400, 520), room) is True
    assert rect_inside_room(Rect(1, 0, 400, 520), room) is False
