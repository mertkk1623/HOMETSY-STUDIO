"""``ui.layout``: the seam between the plan screen and the two engines.

These tests are deliberately engine-facing rather than screen-facing. The screen
tests prove the user sees the right thing; these prove the numbers it shows are
the engine's own, that nothing here invents geometry, and that the "no candidate"
case is reported as a failure rather than as an empty success.
"""

from __future__ import annotations

from models.schemas import (
    FurnitureItem,
    FurnitureRecommendation,
    PlacementStatus,
    RoomInput,
    RoomType,
    OpeningInput,
    Wall,
)
from ui.layout import analyse_layout


def hidden_room(width_cm: float = 400.0, length_cm: float = 520.0) -> RoomInput:
    """The test fixture room, rebuilt so this module needs no conftest state."""

    return RoomInput(
        room_type=RoomType.LIVING_ROOM,
        name="Living Room",
        width_cm=width_cm,
        length_cm=length_cm,
        ceiling_height_cm=270,
        door=OpeningInput(wall=Wall.SOUTH, offset_cm=20, width_cm=80),
        window=OpeningInput(wall=Wall.NORTH, offset_cm=20, width_cm=80),
    )


def catalogue() -> tuple[FurnitureItem, ...]:
    import json
    from pathlib import Path

    payload = json.loads(
        (
            Path(__file__).resolve().parents[1] / "data" / "furniture_catalog.json"
        ).read_text("utf-8")
    )
    return tuple(FurnitureItem(**record) for record in payload["items"])


def recommend(*item_ids: str, **quantities: int) -> tuple[FurnitureRecommendation, ...]:
    requests = [
        FurnitureRecommendation(item_id=item_id) for item_id in item_ids
    ]
    requests.extend(
        FurnitureRecommendation(item_id=item_id, quantity=count)
        for item_id, count in quantities.items()
    )
    return tuple(requests)


# --------------------------------------------------------------------------- #
# The engine is called, not re-implemented
# --------------------------------------------------------------------------- #


def test_the_analysis_returns_the_engines_own_validation() -> None:
    room = hidden_room()
    analysis = analyse_layout(room, recommend("sofa_three_seat"), catalogue())

    assert analysis.validation.is_valid is True
    assert analysis.outcome.status is PlacementStatus.COMPLETE
    assert analysis.is_complete is True
    assert analysis.is_failed is False
    assert analysis.outcome.placed


def test_the_coordinates_are_written_into_the_basket() -> None:
    room = hidden_room()
    requests = recommend("sofa_three_seat", "coffee_table")
    analysis = analyse_layout(room, requests, catalogue())

    # The caller's tuple is untouched; the returned one is annotated.
    assert all(item.position_x_cm is None for item in requests)
    for original, placed in zip(requests, analysis.placements):
        assert original.item_id == placed.item_id
        assert placed.positions
        assert placed.position_x_cm == placed.positions[0].position_x_cm
        assert placed.position_y_cm == placed.positions[0].position_y_cm


def test_the_placement_and_the_drawing_agree() -> None:
    """Each written position has a matching accepted footprint."""

    room = hidden_room()
    analysis = analyse_layout(
        room, recommend("sofa_three_seat", "bookshelf"), catalogue()
    )

    written = {
        (item.item_id, position.position_x_cm, position.position_y_cm)
        for item in analysis.placements
        for position in item.positions
    }
    drawn = {
        (footprint.item_id, footprint.left_cm, footprint.bottom_cm)
        for footprint in analysis.outcome.placed
    }
    assert written == drawn


def test_quantity_is_measured_copy_by_copy() -> None:
    room = hidden_room()
    analysis = analyse_layout(
        room, (FurnitureRecommendation(item_id="dining_chair", quantity=4),),
        catalogue(),
    )

    assert analysis.outcome.status is PlacementStatus.COMPLETE
    assert analysis.outcome.placed_count == 4
    assert len(analysis.placements[0].positions) == 4
    # The request still says four; the budget depends on it.
    assert analysis.placements[0].quantity == 4
    # Four distinct positions, not one repeated four times.
    distinct = {
        (p.left_cm, p.bottom_cm) for p in analysis.outcome.placed
    }
    assert len(distinct) == 4


# --------------------------------------------------------------------------- #
# Failure is reported as failure
# --------------------------------------------------------------------------- #


def test_a_room_too_small_for_everything_fails_without_a_plan() -> None:
    room = hidden_room(150.0, 150.0)
    analysis = analyse_layout(room, recommend("sofa_three_seat"), catalogue())

    assert analysis.outcome.status is PlacementStatus.FAILED
    assert analysis.is_failed is True
    # No accepted layout means nothing to draw and no achieved score.
    assert analysis.outcome.placed == []
    assert analysis.outcome.score is None
    assert analysis.outcome.unplaced
    # And the basket keeps no coordinate for a copy that was not placed.
    assert analysis.placements[0].positions == []
    assert analysis.placements[0].position_x_cm is None


def test_a_failed_analysis_never_synthesises_a_valid_verdict() -> None:
    room = hidden_room(150.0, 150.0)
    analysis = analyse_layout(room, recommend("sofa_three_seat"), catalogue())

    assert analysis.validation.is_valid is False
    # The reason is carried in the blocking list, not silently dropped.
    assert analysis.validation.boundary_violations
    assert analysis.validation.is_valid is not analysis.outcome.score


def test_a_rejected_candidate_is_not_offered_as_a_placed_layout() -> None:
    """Whenever the verdict is invalid, nothing is offered as placed."""

    for width, length in ((120.0, 160.0), (150.0, 150.0), (200.0, 200.0)):
        room = hidden_room(width, length)
        analysis = analyse_layout(
            room,
            recommend("sofa_three_seat", "bed_double"),
            catalogue(),
        )
        if analysis.validation.is_valid:
            continue
        assert analysis.outcome.placed == [] or analysis.outcome.is_partial
        if analysis.outcome.is_failed:
            assert analysis.outcome.placed == []
            assert analysis.outcome.score is None


def test_a_partial_analysis_reports_the_shortfall() -> None:
    room = hidden_room(400.0, 500.0)
    analysis = analyse_layout(
        room, (FurnitureRecommendation(item_id="armchair", quantity=20),),
        catalogue(),
    )

    assert analysis.outcome.status is PlacementStatus.PARTIAL
    assert analysis.is_partial is True
    assert analysis.outcome.placed_count < 20
    assert analysis.outcome.unplaced_count == 20 - analysis.outcome.placed_count
    # Only the placed copies are written back.
    assert len(analysis.placements[0].positions) == analysis.outcome.placed_count
    assert analysis.placements[0].quantity == 20


def test_an_unknown_item_is_reported_and_never_placed() -> None:
    room = hidden_room()
    analysis = analyse_layout(room, recommend("ghost_sofa"), catalogue())

    assert analysis.outcome.placed == []
    assert [item.item_id for item in analysis.outcome.unplaced] == ["ghost_sofa"]
    assert analysis.placements[0].positions == []
    # Nothing invented a position for an item that does not exist.
    assert analysis.placements[0].item_id == "ghost_sofa"


def test_an_empty_basket_is_not_a_valid_layout() -> None:
    room = hidden_room()
    analysis = analyse_layout(room, (), catalogue())

    assert analysis.outcome.is_failed is True
    assert analysis.outcome.placed == []
    assert analysis.validation.is_valid is False
    assert analysis.validation.boundary_violations


# --------------------------------------------------------------------------- #
# Reproducibility
# --------------------------------------------------------------------------- #


def test_the_same_inputs_produce_the_same_layout() -> None:
    """Placement is deterministic, so a rerun cannot move the furniture."""

    room = hidden_room()
    requests = recommend("sofa_three_seat", "coffee_table", "bookshelf")
    first = analyse_layout(room, requests, catalogue())
    second = analyse_layout(room, requests, catalogue())

    assert first.outcome == second.outcome
    assert first.validation == second.validation
    assert first.placements == second.placements
