"""Tests for the deterministic room geometry engine."""

from __future__ import annotations

import pytest

from core.room_engine import (
    EPS_CM,
    area_sqm,
    normalize_rotation,
    opening_conflict_messages,
    opening_interval_cm,
    opening_placement,
    opening_segment,
    openings_overlap,
    perimeter_cm,
    room_metrics,
    validate_dimensions,
    validate_opening,
    validate_room,
    wall_length_cm,
    wall_lengths_cm,
)
from models.schemas import OpeningInput, RoomInput, RoomType, Wall


# --------------------------------------------------------------------------- #
# Normal room dimensions
# --------------------------------------------------------------------------- #


def test_area_is_reported_in_square_meters() -> None:
    assert area_sqm(400, 520) == pytest.approx(20.8)


def test_perimeter_is_the_sum_of_all_walls() -> None:
    assert perimeter_cm(400, 520) == pytest.approx(1840)


def test_wall_lengths_follow_orientation() -> None:
    lengths = wall_lengths_cm(400, 520)
    assert lengths[Wall.NORTH] == 400
    assert lengths[Wall.SOUTH] == 400
    assert lengths[Wall.EAST] == 520
    assert lengths[Wall.WEST] == 520


def test_north_and_south_span_the_width() -> None:
    assert wall_length_cm(300, 700, Wall.NORTH) == 300
    assert wall_length_cm(300, 700, Wall.SOUTH) == 300


def test_east_and_west_span_the_length() -> None:
    assert wall_length_cm(300, 700, Wall.EAST) == 700
    assert wall_length_cm(300, 700, Wall.WEST) == 700


def test_room_metrics_from_model(room: RoomInput) -> None:
    metrics = room_metrics(room)
    assert metrics.area_sqm == pytest.approx(20.8)
    assert metrics.perimeter_cm == pytest.approx(1840)
    assert metrics.wall_lengths_cm[Wall.NORTH] == 400


def test_valid_room_has_no_problems(room: RoomInput) -> None:
    assert validate_room(room) == []


def test_valid_dimensions_pass() -> None:
    assert validate_dimensions(400, 520, ceiling_height_cm=270) == []


# --------------------------------------------------------------------------- #
# Zero and negative dimensions
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("value", [0, -1, -250])
def test_non_positive_width_is_reported(value: float) -> None:
    problems = validate_dimensions(value, 400)
    assert any("width" in problem for problem in problems)


@pytest.mark.parametrize("value", [0, -1, -250])
def test_non_positive_length_is_reported(value: float) -> None:
    problems = validate_dimensions(400, value)
    assert any("length" in problem for problem in problems)


def test_area_of_zero_room_raises() -> None:
    with pytest.raises(ValueError):
        area_sqm(0, 400)


def test_area_of_negative_room_raises() -> None:
    with pytest.raises(ValueError):
        area_sqm(-100, 400)


def test_perimeter_of_zero_room_raises() -> None:
    with pytest.raises(ValueError):
        perimeter_cm(400, 0)


def test_dimension_below_minimum_is_reported() -> None:
    problems = validate_dimensions(99, 400)
    assert any("below" in problem for problem in problems)


def test_dimension_above_maximum_is_reported() -> None:
    problems = validate_dimensions(2001, 400)
    assert any("exceeds" in problem for problem in problems)


@pytest.mark.parametrize("value", [0, -10, 199, 501])
def test_invalid_ceiling_height_is_reported(value: float) -> None:
    problems = validate_dimensions(400, 400, ceiling_height_cm=value)
    assert problems


def test_non_numeric_dimension_is_reported() -> None:
    problems = validate_dimensions("wide", 400)  # type: ignore[arg-type]
    assert any("must be a number" in problem for problem in problems)


# --------------------------------------------------------------------------- #
# Door and window placement
# --------------------------------------------------------------------------- #


def test_opening_interval_is_offset_plus_width() -> None:
    assert opening_interval_cm(60, 90) == (60, 150)


def test_south_opening_sits_on_the_bottom_edge() -> None:
    segment = opening_segment(400, 520, Wall.SOUTH, 60, 90)
    assert (segment.start.x_cm, segment.start.y_cm) == (60, 0)
    assert (segment.end.x_cm, segment.end.y_cm) == (150, 0)
    assert segment.length_cm == pytest.approx(90)


def test_north_opening_sits_on_the_top_edge() -> None:
    segment = opening_segment(400, 520, Wall.NORTH, 60, 90)
    assert (segment.start.y_cm, segment.end.y_cm) == (520, 520)


def test_west_opening_sits_on_the_left_edge() -> None:
    segment = opening_segment(400, 520, Wall.WEST, 60, 90)
    assert (segment.start.x_cm, segment.start.y_cm) == (0, 60)
    assert (segment.end.x_cm, segment.end.y_cm) == (0, 150)


def test_east_opening_sits_on_the_right_edge() -> None:
    segment = opening_segment(400, 520, Wall.EAST, 60, 90)
    assert segment.start.x_cm == 400
    assert segment.end.x_cm == 400


def test_opening_placement_reports_inside(room: RoomInput) -> None:
    placement = opening_placement(room, room.door, label="door")
    assert placement.inside_room is True
    assert placement.along_wall_start_cm == 60
    assert placement.along_wall_end_cm == 150


def test_opening_that_exceeds_the_wall_is_reported() -> None:
    problems = validate_opening(380, 90, 400, label="door")
    assert any("does not fit" in problem for problem in problems)


def test_opening_exactly_filling_the_wall_is_accepted() -> None:
    assert validate_opening(310, 90, 400, label="door") == []


def test_opening_one_centimeter_over_the_wall_is_reported() -> None:
    assert validate_opening(311, 90, 400, label="door")


@pytest.mark.parametrize("value", [-1, -25])
def test_negative_offset_is_reported(value: float) -> None:
    problems = validate_opening(value, 90, 400, label="door")
    assert any("cannot be negative" in problem for problem in problems)


@pytest.mark.parametrize("value", [0, 39])
def test_too_narrow_opening_is_reported(value: float) -> None:
    problems = validate_opening(10, value, 400, label="window")
    assert problems


def test_floating_point_end_is_tolerated() -> None:
    # 0.1 + 0.2 style drift must not produce a spurious failure.
    problems = validate_opening(310 - EPS_CM, 90, 400, label="door")
    assert problems == []


# --------------------------------------------------------------------------- #
# Door / window conflicts
# --------------------------------------------------------------------------- #


def test_openings_on_different_walls_never_conflict() -> None:
    room = RoomInput(
        room_type=RoomType.BEDROOM,
        name="Bedroom",
        width_cm=400,
        length_cm=520,
        door=OpeningInput(wall=Wall.SOUTH, offset_cm=100, width_cm=90),
        window=OpeningInput(wall=Wall.NORTH, offset_cm=100, width_cm=160),
    )
    assert openings_overlap(room) is False
    assert opening_conflict_messages(room) == []


def test_overlapping_openings_on_one_wall_are_detected() -> None:
    room = RoomInput(
        room_type=RoomType.BEDROOM,
        name="Bedroom",
        width_cm=400,
        length_cm=520,
        door=OpeningInput(wall=Wall.SOUTH, offset_cm=50, width_cm=90),
        window=OpeningInput(wall=Wall.SOUTH, offset_cm=100, width_cm=160),
    )
    assert openings_overlap(room) is True
    assert opening_conflict_messages(room)


def test_adjacent_openings_on_one_wall_are_allowed() -> None:
    # Door 50-140, window 140-300: touching but not overlapping.
    room = RoomInput(
        room_type=RoomType.BEDROOM,
        name="Bedroom",
        width_cm=400,
        length_cm=520,
        door=OpeningInput(wall=Wall.SOUTH, offset_cm=50, width_cm=90),
        window=OpeningInput(wall=Wall.SOUTH, offset_cm=140, width_cm=160),
    )
    assert openings_overlap(room) is False


# --------------------------------------------------------------------------- #
# Rotation helper
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("degrees", [0, 90, 180, 270, 360])
def test_supported_rotations_normalise(degrees: int) -> None:
    assert normalize_rotation(degrees) in (0, 90, 180, 270)


def test_full_turn_wraps_to_zero() -> None:
    assert normalize_rotation(360) == 0
    assert normalize_rotation(720) == 0


def test_non_right_angle_rotation_raises() -> None:
    with pytest.raises(ValueError):
        normalize_rotation(45)
