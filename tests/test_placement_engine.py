"""Tests for the deterministic furniture placement engine.

The module under test *proposes* a layout; ``core.spatial_engine`` decides
whether it is acceptable. Most assertions below therefore check two things at
once: the property the engine claims to guarantee, and the fact that the shared
spatial engine agrees. A test that only checked the engine's own bookkeeping
would not prove that the layout is usable.

The shared ``room`` fixture is 400 x 520 cm with a south door (x 60-150) and a
north window (x 120-280), so the clearance zones are:

* door:   x 60-150,  y 0-60
* window: x 120-280, y 490-520
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.placement_engine import (
    LAYOUT_WEIGHTS,
    STRATEGIES,
    LayoutCandidate,
    PlacementStatus,
    apply_placements,
    generate_layouts,
    place_furniture,
    rotation_candidates,
)
from core.room_engine import EPS_CM, validate_room
from core.spatial_engine import (
    DEFAULT_DOOR_CLEARANCE_CM,
    DEFAULT_WINDOW_CLEARANCE_CM,
    effective_size_cm,
    opening_clearance_rect,
    rect_inside_room,
    rects_overlap,
    validate_placement,
)
from models.schemas import (
    FurnitureItem,
    FurnitureRecommendation,
    OpeningInput,
    RoomInput,
    RoomType,
    Wall,
)

CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "furniture_catalog.json"


@pytest.fixture(scope="module")
def catalog() -> list[FurnitureItem]:
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return [FurnitureItem(**record) for record in payload["items"]]


@pytest.fixture(scope="module")
def catalogue(catalog: list[FurnitureItem]) -> tuple[FurnitureItem, ...]:
    return tuple(catalog)


def recommend(*item_ids: str, **kwargs: object) -> tuple[FurnitureRecommendation, ...]:
    """Recommendations with no coordinates, exactly as the advisor returns them."""

    return tuple(
        FurnitureRecommendation(item_id=item_id, **kwargs)  # type: ignore[arg-type]
        for item_id in item_ids
    )


def hidden_room(
    width_cm: float,
    length_cm: float,
    *,
    door_wall: Wall = Wall.SOUTH,
    door_offset_cm: float = 10.0,
    door_width_cm: float = 70.0,
    window_wall: Wall = Wall.NORTH,
    window_offset_cm: float = 10.0,
    window_width_cm: float = 70.0,
) -> RoomInput:
    return RoomInput(
        room_type=RoomType.LIVING_ROOM,
        name="Test Room",
        width_cm=width_cm,
        length_cm=length_cm,
        ceiling_height_cm=270,
        door=OpeningInput(
            wall=door_wall, offset_cm=door_offset_cm, width_cm=door_width_cm
        ),
        window=OpeningInput(
            wall=window_wall,
            offset_cm=window_offset_cm,
            width_cm=window_width_cm,
        ),
    )


def accepts_layout(
    room: RoomInput,
    candidate: LayoutCandidate,
    catalogue: tuple[FurnitureItem, ...],
) -> None:
    """Assert the shared spatial engine agrees that the layout is usable."""

    report = validate_placement(room, candidate.footprints)
    assert report.errors == (), [issue.message for issue in report.issues]
    assert report.is_valid is True

    for footprint in candidate.footprints:
        assert rect_inside_room(footprint.rect, room) is True


# --------------------------------------------------------------------------- #
# 1. A valid simple room layout
# --------------------------------------------------------------------------- #


def test_single_item_is_placed_and_validated(
    room: RoomInput, catalogue: tuple[FurnitureItem, ...]
) -> None:
    result = place_furniture(room, recommend("armchair"), catalogue)

    assert result.status is PlacementStatus.COMPLETE
    assert len(result.placements) == 1

    footprint = result.footprints[0]
    assert footprint.item_id == "armchair"
    # Dimensions come from the catalog, never from the AI.
    assert (footprint.width_cm, footprint.depth_cm) == (80.0, 80.0)
    accepts_layout(room, result.candidate, catalogue)


def test_placement_uses_catalog_dimensions_not_recommendation_fields(
    room: RoomInput, catalogue: tuple[FurnitureItem, ...]
) -> None:
    """A recommendation may carry coordinates; the engine recomputes them."""

    recommendation = FurnitureRecommendation(
        item_id="sofa_three_seat", position_x_cm=0.0, position_y_cm=0.0
    )
    result = place_furniture(room, (recommendation,), catalogue)

    assert result.status is PlacementStatus.COMPLETE
    footprint = result.footprints[0]
    assert (footprint.width_cm, footprint.depth_cm) in ((220.0, 90.0), (90.0, 220.0))
    # The advised origin (0, 0) would sit in the corner regardless of fit; the
    # engine's own choice must at least be a legal one.
    assert rect_inside_room(footprint.rect, room) is True


def test_null_coordinates_are_normal_input(
    room: RoomInput, catalogue: tuple[FurnitureItem, ...]
) -> None:
    recommendation = FurnitureRecommendation(item_id="bookshelf")
    assert recommendation.position_x_cm is None
    assert recommendation.position_y_cm is None

    result = place_furniture(room, (recommendation,), catalogue)

    assert result.status is PlacementStatus.COMPLETE
    assert result.unplaced == ()
    assert result.validation.is_valid is True


# --------------------------------------------------------------------------- #
# 2. Determinism
# --------------------------------------------------------------------------- #


def test_same_inputs_produce_identical_layouts(
    room: RoomInput, catalogue: tuple[FurnitureItem, ...]
) -> None:
    requests = recommend(
        "sofa_three_seat", "coffee_table", "tv_unit", "armchair", "floor_lamp"
    )

    first = place_furniture(room, requests, catalogue)
    second = place_furniture(room, requests, catalogue)

    assert first.status is second.status
    assert first.footprints == second.footprints
    assert first.candidate == second.candidate


def test_candidate_order_is_stable_and_follows_the_declared_strategies(
    room: RoomInput, catalogue: tuple[FurnitureItem, ...]
) -> None:
    requests = recommend("sofa_three_seat", "coffee_table")

    first = generate_layouts(room, requests, catalogue)
    second = generate_layouts(room, requests, catalogue)

    assert first == second
    assert len(first) == len(STRATEGIES)
    assert {candidate.strategy for candidate in first} == {
        strategy.name for strategy in STRATEGIES
    }


def test_ranking_prefers_more_placed_items_then_higher_score(
    room: RoomInput, catalogue: tuple[FurnitureItem, ...]
) -> None:
    candidates = generate_layouts(room, recommend("sofa_three_seat"), catalogue)

    for earlier, later in zip(candidates, candidates[1:]):
        assert earlier.placed_count >= later.placed_count
        if earlier.placed_count == later.placed_count:
            assert earlier.score >= later.score


def test_wall_strategies_produce_different_layouts(
    room: RoomInput, catalogue: tuple[FurnitureItem, ...]
) -> None:
    """The four strategies must be more than cosmetic.

    Wall preference is a tiebreaker, so an easy room may converge; this room and
    item set are chosen so the preferred wall genuinely changes the result.
    """

    requests = recommend(
        "sofa_three_seat", "coffee_table", "tv_unit", "armchair", "bookshelf"
    )
    candidates = generate_layouts(room, requests, catalogue)

    layouts = {
        tuple(
            (p.item_id, p.footprint.left_cm, p.footprint.bottom_cm)
            for p in candidate.placements
        )
        for candidate in candidates
    }
    assert len(layouts) > 1


def test_layout_score_does_not_depend_on_the_generation_strategy(
    room: RoomInput, catalogue: tuple[FurnitureItem, ...]
) -> None:
    """The score must be a property of the layout, not of how it was built.

    A strategy name may differ between two candidates that contain identical
    geometry; if their scores differed too, the ranking would be partly
    arbitrary. This is also a guard against reintroducing a strategy term into
    the layout-level quality weights.
    """

    requests = recommend(
        "sofa_three_seat", "coffee_table", "tv_unit", "armchair", "bookshelf"
    )
    candidates = generate_layouts(room, requests, catalogue)

    scores_by_geometry: dict[tuple, set[float]] = {}
    for candidate in candidates:
        geometry = tuple(
            (p.item_id, p.footprint.left_cm, p.footprint.bottom_cm)
            for p in candidate.placements
        )
        scores_by_geometry.setdefault(geometry, set()).add(candidate.score)

    assert all(len(scores) == 1 for scores in scores_by_geometry.values())
    # The comparison is only meaningful if more than one strategy is present.
    assert len({candidate.strategy for candidate in candidates}) > 1


def test_seating_is_anchored_to_a_wall_not_floating(
    room: RoomInput, catalogue: tuple[FurnitureItem, ...]
) -> None:
    """A sofa must touch a wall with its long edge, not merely sit near one."""

    result = place_furniture(room, recommend("sofa_three_seat"), catalogue)
    footprint = result.footprints[0]
    rect = footprint.rect

    contact_cm = 0.0
    if rect.left_cm <= EPS_CM or abs(rect.right_cm - room.width_cm) <= EPS_CM:
        contact_cm = max(contact_cm, rect.depth_cm)
    if rect.bottom_cm <= EPS_CM or abs(rect.top_cm - room.length_cm) <= EPS_CM:
        contact_cm = max(contact_cm, rect.width_cm)

    assert contact_cm >= min(footprint.width_cm, footprint.depth_cm)
    assert contact_cm >= max(footprint.width_cm, footprint.depth_cm) - EPS_CM


# --------------------------------------------------------------------------- #
# 3. Boundary violations are prevented
# --------------------------------------------------------------------------- #


def test_no_footprint_ever_leaves_the_room(
    room: RoomInput, catalogue: tuple[FurnitureItem, ...]
) -> None:
    requests = recommend(
        "sofa_three_seat", "coffee_table", "sideboard", "armchair", "plant_large"
    )

    result = place_furniture(room, requests, catalogue)

    assert result.placements
    for footprint in result.footprints:
        assert rect_inside_room(footprint.rect, room) is True
    accepts_layout(room, result.candidate, catalogue)


@pytest.mark.parametrize(
    ("width_cm", "length_cm"),
    [(100.0, 100.0), (110.0, 150.0), (120.0, 120.0)],
)
def test_room_too_small_for_any_item_is_reported_not_forced(
    width_cm: float,
    length_cm: float,
    catalogue: tuple[FurnitureItem, ...],
) -> None:
    narrow = hidden_room(width_cm, length_cm)

    result = place_furniture(narrow, recommend("sofa_three_seat"), catalogue)

    assert result.status is PlacementStatus.FAILED
    assert result.candidate is None
    assert result.footprints == ()
    # The item is named, and the reason mentions the actual obstacle.
    assert [item.item_id for item in result.unplaced] == ["sofa_three_seat"]
    assert "sofa" in result.unplaced[0].reason.lower()


def test_an_item_wider_than_the_room_is_reported_as_unplaceable(
    catalogue: tuple[FurnitureItem, ...],
) -> None:
    narrow = hidden_room(100.0, 150.0)

    result = place_furniture(narrow, recommend("sofa_three_seat"), catalogue)

    assert result.status is PlacementStatus.FAILED
    unplaced = result.unplaced[0]
    assert unplaced.reason_code == "no_valid_position"
    assert "does not fit inside" in unplaced.reason


# --------------------------------------------------------------------------- #
# 4. Overlaps are prevented
# --------------------------------------------------------------------------- #


def test_placed_footprints_never_overlap(
    room: RoomInput, catalogue: tuple[FurnitureItem, ...]
) -> None:
    requests = recommend(
        "sofa_three_seat", "coffee_table", "armchair", "side_table", "bookshelf"
    )

    result = place_furniture(room, requests, catalogue)
    footprints = result.footprints

    assert len(footprints) == len(requests)
    for first_index, first in enumerate(footprints):
        for second in footprints[first_index + 1 :]:
            assert rects_overlap(first.rect, second.rect) is False


def test_touching_edge_to_edge_is_allowed_and_reported_as_no_overlap(
    room: RoomInput, catalogue: tuple[FurnitureItem, ...]
) -> None:
    """The engine may put pieces side by side; that is not an overlap error."""

    requests = recommend("armchair", "armchair")
    result = place_furniture(room, requests, catalogue)

    assert len(result.footprints) == 2
    first, second = (footprint.rect for footprint in result.footprints)
    assert rects_overlap(first, second) is False
    assert result.report.errors == ()


# --------------------------------------------------------------------------- #
# 5. Door access is preserved
# --------------------------------------------------------------------------- #


def test_door_clearance_zone_stays_empty(
    room: RoomInput, catalogue: tuple[FurnitureItem, ...]
) -> None:
    door_zone = opening_clearance_rect(
        room,
        room.door.wall,
        room.door.offset_cm,
        room.door.width_cm,
        DEFAULT_DOOR_CLEARANCE_CM,
    )
    assert door_zone is not None

    requests = recommend(
        "sofa_three_seat", "coffee_table", "tv_unit", "armchair", "bookshelf"
    )
    result = place_furniture(room, requests, catalogue)

    assert result.status is PlacementStatus.COMPLETE
    for footprint in result.footprints:
        assert rects_overlap(footprint.rect, door_zone) is False
    assert "door_blocked" not in {issue.code for issue in result.report.issues}


def test_a_room_whose_only_free_floor_is_the_doorway_places_nothing(
    catalogue: tuple[FurnitureItem, ...],
) -> None:
    """The doorway is never sacrificed to make a recommendation fit."""

    # 100 x 120 cm with a door spanning the whole south wall: the 60 cm
    # clearance leaves a 100 x 60 cm strip, which an 80 x 80 armchair cannot
    # occupy. The engine must refuse rather than stand the chair in the doorway.
    doorway_room = hidden_room(
        100.0,
        120.0,
        door_offset_cm=0.0,
        door_width_cm=100.0,
        window_offset_cm=20.0,
        window_width_cm=60.0,
    )
    result = place_furniture(doorway_room, recommend("armchair"), catalogue)

    assert result.status is PlacementStatus.FAILED
    assert result.candidate is None
    assert result.unplaced[0].item_id == "armchair"
    assert "door clearance zone" in result.unplaced[0].reason


# --------------------------------------------------------------------------- #
# 6. Window clearance is preserved
# --------------------------------------------------------------------------- #


def test_window_clearance_is_preferred_even_though_it_is_only_a_warning(
    room: RoomInput, catalogue: tuple[FurnitureItem, ...]
) -> None:
    window_zone = opening_clearance_rect(
        room,
        room.window.wall,
        room.window.offset_cm,
        room.window.width_cm,
        DEFAULT_WINDOW_CLEARANCE_CM,
    )
    assert window_zone is not None

    result = place_furniture(room, recommend("sofa_three_seat"), catalogue)

    assert result.status is PlacementStatus.COMPLETE
    footprint = result.footprints[0]
    assert rects_overlap(footprint.rect, window_zone) is False
    assert result.candidate.component("window_clearance") == 1.0


def test_window_obstruction_lowers_the_score_instead_of_failing(
    catalogue: tuple[FurnitureItem, ...],
) -> None:
    """A room that forces a piece under the window still yields a usable plan."""

    # 170 x 200: the 160 cm window spans nearly the whole north wall, so a
    # 180 cm TV unit cannot avoid it. The spatial engine reports a warning, the
    # layout stays valid, and the score records the loss.
    cramped = hidden_room(
        170.0,
        200.0,
        door_offset_cm=10.0,
        door_width_cm=70.0,
        window_offset_cm=5.0,
        window_width_cm=160.0,
    )
    result = place_furniture(cramped, recommend("tv_unit"), catalogue)

    assert result.status is PlacementStatus.COMPLETE
    assert result.validation.is_valid is True
    assert "window_obstructed" in {issue.code for issue in result.report.issues}
    assert result.candidate.component("window_clearance") < 1.0


# --------------------------------------------------------------------------- #
# 7. Unsupported rotations are rejected
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("requested", [0, 90, 180, 270])
def test_supported_rotations_are_accepted(
    requested: int, room: RoomInput, catalogue: tuple[FurnitureItem, ...]
) -> None:
    recommendation = FurnitureRecommendation(
        item_id="sofa_three_seat", rotation_degrees=requested
    )
    result = place_furniture(room, (recommendation,), catalogue)

    assert result.status is PlacementStatus.COMPLETE
    footprint = result.footprints[0]
    assert footprint.rotation_degrees in (requested, (requested + 90) % 360)
    assert footprint.rotation_degrees % 90 == 0


def test_rotation_candidates_only_contain_right_angles() -> None:
    for requested in (0, 90, 180, 270):
        pair = rotation_candidates(requested)
        assert pair[0] == requested
        assert all(rotation % 90 == 0 for rotation in pair)
        assert pair[1] == (requested + 90) % 360


def test_non_right_angle_rotation_is_reported_as_unplaced(
    room: RoomInput, catalogue: tuple[FurnitureItem, ...]
) -> None:
    """The model rejects such a value, so the engine must not trust a bypass."""

    recommendation = FurnitureRecommendation.model_construct(
        item_id="armchair",
        quantity=1,
        rotation_degrees=45,
        position_x_cm=None,
        position_y_cm=None,
        rationale="",
    )

    result = place_furniture(room, (recommendation,), catalogue)

    assert result.status is PlacementStatus.FAILED
    assert result.candidate is None
    assert result.unplaced[0].reason_code == "unsupported_rotation"
    assert "90" in result.unplaced[0].reason


def test_every_placed_footprint_uses_a_supported_rotation(
    room: RoomInput, catalogue: tuple[FurnitureItem, ...]
) -> None:
    requests = recommend(
        "sofa_three_seat", "coffee_table", "bookshelf", "wardrobe"
    )
    result = place_furniture(room, requests, catalogue)

    for footprint in result.footprints:
        assert footprint.rotation_degrees in (0, 90, 180, 270)


# --------------------------------------------------------------------------- #
# 8. Missing catalog items are reported
# --------------------------------------------------------------------------- #


def test_unknown_catalog_item_is_reported_by_name(
    room: RoomInput, catalogue: tuple[FurnitureItem, ...]
) -> None:
    requests = recommend("sofa_three_seat", "holographic_fireplace")

    result = place_furniture(room, requests, catalogue)

    assert [item.item_id for item in result.unplaced] == ["holographic_fireplace"]
    assert result.unplaced[0].reason_code == "unknown_catalog_item"
    assert "holographic_fireplace" in result.unplaced[0].reason
    # The known item is still placed; the unknown one is never invented.
    assert [footprint.item_id for footprint in result.footprints] == [
        "sofa_three_seat"
    ]


def test_only_unknown_items_means_the_placement_fails(
    room: RoomInput, catalogue: tuple[FurnitureItem, ...]
) -> None:
    result = place_furniture(room, recommend("ghost_chair"), catalogue)

    assert result.status is PlacementStatus.FAILED
    assert result.candidate is None
    assert result.unplaced[0].reason_code == "unknown_catalog_item"


def test_unknown_item_quantity_is_counted_in_the_report(
    room: RoomInput, catalogue: tuple[FurnitureItem, ...]
) -> None:
    recommendation = FurnitureRecommendation(item_id="ghost_chair", quantity=3)

    result = place_furniture(room, (recommendation,), catalogue)

    assert result.unplaced[0].count == 3


# --------------------------------------------------------------------------- #
# 9. Unplaceable items are reported explicitly
# --------------------------------------------------------------------------- #


def test_quantity_beyond_the_available_floor_is_reported_per_copy(
    catalogue: tuple[FurnitureItem, ...],
) -> None:
    """Six three-seat sofas cannot fit in a 5.8 m² room; the excess is named."""

    cramped = hidden_room(240.0, 240.0)
    recommendation = FurnitureRecommendation(item_id="sofa_three_seat", quantity=6)

    result = place_furniture(cramped, (recommendation,), catalogue)

    placed = len(result.placements)
    unplaced = result.unplaced
    assert placed >= 1
    assert placed < 6
    assert unplaced
    assert unplaced[0].item_id == "sofa_three_seat"
    assert unplaced[0].count == 6 - placed
    assert unplaced[0].reason_code == "no_valid_position"
    assert "Three-seat sofa" in unplaced[0].reason


def test_quantity_that_fits_is_placed_in_full(
    room: RoomInput, catalogue: tuple[FurnitureItem, ...]
) -> None:
    recommendation = FurnitureRecommendation(item_id="dining_chair", quantity=4)

    result = place_furniture(room, (recommendation,), catalogue)

    assert result.status is PlacementStatus.COMPLETE
    assert len(result.placements) == 4
    assert result.unplaced == ()
    # Every copy keeps the requested item and the catalog dimensions (in one of
    # the two supported orientations of a 45 x 50 cm footprint).
    for footprint in result.footprints:
        assert footprint.item_id == "dining_chair"
        assert (footprint.width_cm, footprint.depth_cm) in (
            (45.0, 50.0),
            (50.0, 45.0),
        )


def test_unplaceable_reason_mentions_the_free_area_when_floor_remains(
    catalogue: tuple[FurnitureItem, ...],
) -> None:
    cramped = hidden_room(240.0, 240.0)

    result = place_furniture(
        cramped,
        recommend("bed_double", "sofa_three_seat"),
        catalogue,
    )

    unplaced = result.unplaced
    assert unplaced
    assert unplaced[0].reason_code == "no_valid_position"
    assert "free" in unplaced[0].reason


# --------------------------------------------------------------------------- #
# 10. Partial placement is not success
# --------------------------------------------------------------------------- #


def test_partial_placement_has_its_own_status(
    catalogue: tuple[FurnitureItem, ...],
) -> None:
    small = hidden_room(230.0, 230.0)

    result = place_furniture(
        small, recommend("bed_double", "sofa_three_seat", "coffee_table"), catalogue
    )

    assert result.status is PlacementStatus.PARTIAL
    assert result.is_complete is False
    assert result.is_partial is True
    assert result.unplaced
    # A partial layout is still a real, validated layout: it is offered for
    # drawing but never flagged as complete.
    assert result.candidate is not None
    assert result.validation.is_valid is True
    assert any(note.code == "partial_placement" for note in result.notes)


def test_partial_layout_still_makes_the_spatial_engine_pass(
    catalogue: tuple[FurnitureItem, ...],
) -> None:
    small = hidden_room(230.0, 230.0)
    result = place_furniture(
        small, recommend("bed_double", "sofa_three_seat"), catalogue
    )

    assert result.status is PlacementStatus.PARTIAL
    accepts_layout(small, result.candidate, catalogue)


def test_status_properties_agree_with_the_enum(
    room: RoomInput, catalogue: tuple[FurnitureItem, ...]
) -> None:
    complete = place_furniture(room, recommend("armchair"), catalogue)
    assert (complete.is_complete, complete.is_partial, complete.is_failed) == (
        True,
        False,
        False,
    )

    failed = place_furniture(
        hidden_room(100.0, 100.0), recommend("armchair"), catalogue
    )
    assert (failed.is_complete, failed.is_partial, failed.is_failed) == (
        False,
        False,
        True,
    )


# --------------------------------------------------------------------------- #
# 11. Integration with the existing spatial engine
# --------------------------------------------------------------------------- #


def test_engine_never_bypasses_the_shared_validator(
    room: RoomInput, catalogue: tuple[FurnitureItem, ...], monkeypatch
) -> None:
    """If the shared validator reports an error, the engine must fail too."""

    import core.spatial_engine as spatial_engine

    real_validate = spatial_engine.validate_placement

    def rejecting(room_input, footprints, **kwargs):
        report = real_validate(room_input, footprints, **kwargs)
        return spatial_engine.PlacementReport(
            footprints=report.footprints,
            issues=report.issues
            + (
                spatial_engine.PlacementIssue(
                    severity="error",
                    code="forced_rejection",
                    message="Rejected for the test.",
                ),
            ),
        )

    monkeypatch.setattr(
        "core.placement_engine.validate_placement", rejecting
    )

    result = place_furniture(room, recommend("armchair"), catalogue)

    assert result.status is PlacementStatus.FAILED
    assert result.candidate is None
    assert any(note.code == "layout_rejected" for note in result.notes)


def test_result_carries_the_spatial_validation_model(
    room: RoomInput, catalogue: tuple[FurnitureItem, ...]
) -> None:
    result = place_furniture(
        room, recommend("sofa_three_seat", "coffee_table"), catalogue
    )

    validation = result.validation
    assert validation is not None
    assert validation.is_valid is True
    assert validation.boundary_violations == []
    assert validation.overlaps == []


def test_findings_use_the_shared_validation_vocabulary(
    room: RoomInput, catalogue: tuple[FurnitureItem, ...]
) -> None:
    """The placement report must be readable by ``core.validation`` callers."""

    from core.validation import ERROR, STAGE_PLACEMENT, ValidationFinding

    result = place_furniture(
        room, recommend("sofa_three_seat", "armchair"), catalogue
    )

    assert isinstance(result.findings, tuple)
    for finding in result.findings:
        assert isinstance(finding, ValidationFinding)
        assert finding.stage == STAGE_PLACEMENT
        assert finding.severity in (ERROR, "warning")
    # A clean layout produces no findings and no errors through that view.
    assert result.validation.is_valid is True


def test_placement_findings_are_empty_for_a_clean_layout(
    room: RoomInput, catalogue: tuple[FurnitureItem, ...]
) -> None:
    result = place_furniture(room, recommend("armchair"), catalogue)

    assert result.report.errors == ()
    assert result.findings == ()


def test_written_coordinates_survive_the_shared_recommendation_path(
    room: RoomInput, catalogue: tuple[FurnitureItem, ...]
) -> None:
    """The engine's coordinates must read back as a valid layout elsewhere.

    ``FurnitureRecommendation`` is the only place coordinates are persisted, so
    ``apply_placements`` writes them there and the existing Phase 3 path
    (``validate_recommendations``) has to agree with the engine's own verdict.
    """

    from core.spatial_engine import validate_recommendations

    requests = recommend("sofa_three_seat", "coffee_table", "armchair")
    result = place_furniture(room, requests, catalogue)
    written = apply_placements(requests, result)

    assert len(written) == len(requests)
    for original, placed in zip(requests, written):
        assert original.position_x_cm is None
        assert placed.position_x_cm is not None
        assert placed.position_y_cm is not None
        assert placed.rotation_degrees in (0, 90, 180, 270)
        # Nothing else changes.
        assert placed.item_id == original.item_id
        assert placed.quantity == original.quantity
        assert placed.rationale == original.rationale

    report, validation = validate_recommendations(
        room, list(written), list(catalogue)
    )

    assert report.errors == ()
    assert validation.is_valid is True
    assert "unplaced_item" not in {issue.code for issue in report.issues}
    assert report.footprints == result.footprints


def test_unplaced_recommendations_keep_their_null_coordinates(
    catalogue: tuple[FurnitureItem, ...],
) -> None:
    small = hidden_room(230.0, 230.0)
    requests = recommend("bed_double", "sofa_three_seat")
    result = place_furniture(small, requests, catalogue)

    assert result.status is PlacementStatus.PARTIAL
    written = apply_placements(requests, result)

    placed_ids = {footprint.item_id for footprint in result.footprints}
    for placed in written:
        if placed.item_id in placed_ids:
            assert placed.position_x_cm is not None
        else:
            # No coordinate is invented for an item that was not placed.
            assert placed.position_x_cm is None
            assert placed.position_y_cm is None


def test_apply_placements_on_a_failed_result_changes_nothing(
    catalogue: tuple[FurnitureItem, ...],
) -> None:
    requests = recommend("armchair")
    result = place_furniture(hidden_room(100.0, 100.0), requests, catalogue)

    assert result.candidate is None
    assert apply_placements(requests, result) == requests


def test_placement_is_idempotent_through_the_write_back(
    room: RoomInput, catalogue: tuple[FurnitureItem, ...]
) -> None:
    """Re-running on the engine's own output must not move anything.

    Coordinates are never inputs, so the second pass sees the same geometry
    request as the first. This also proves the stored position and the computed
    footprint agree exactly, with no rounding drift between them.
    """

    requests = recommend("sofa_three_seat", "coffee_table", "armchair")
    first = place_furniture(room, requests, catalogue)
    written = apply_placements(requests, first)
    second = place_furniture(room, written, catalogue)

    assert second.status is first.status
    assert second.footprints == first.footprints
    assert second.candidate.score == first.candidate.score


def test_multiple_copies_survive_the_write_back(
    room: RoomInput, catalogue: tuple[FurnitureItem, ...]
) -> None:
    """Every copy the engine placed is written back, not just the first.

    Before Step 5B ``FurnitureRecommendation`` held a single position, so four
    chairs collapsed into one stored footprint and the Phase 3 validator
    reported ``quantity_collapsed``. ``positions`` now records one entry per
    placed copy, so the stored project and the engine's layout agree.
    """

    from core.spatial_engine import validate_recommendations

    requests = (FurnitureRecommendation(item_id="dining_chair", quantity=4),)
    result = place_furniture(room, requests, catalogue)
    assert len(result.placements) == 4

    written = apply_placements(requests, result)
    assert len(written[0].positions) == 4
    # The legacy pair mirrors the first copy, so older readers still work.
    assert written[0].position_x_cm == written[0].positions[0].position_x_cm
    assert written[0].position_y_cm == written[0].positions[0].position_y_cm
    assert written[0].quantity == 4

    report, validation = validate_recommendations(
        room, list(written), list(catalogue)
    )

    assert len(report.footprints) == 4
    assert report.footprints == result.footprints
    assert "quantity_collapsed" not in {issue.code for issue in report.issues}
    assert "unplaced_copies" not in {issue.code for issue in report.issues}
    assert validation.is_valid is True


def test_a_partly_placed_quantity_does_not_claim_missing_copies(
    catalogue: tuple[FurnitureItem, ...],
) -> None:
    """Twenty armchairs do not fit; nineteen do, and only nineteen are stored."""

    from core.spatial_engine import validate_recommendations

    room = hidden_room(400.0, 500.0)
    requests = (FurnitureRecommendation(item_id="armchair", quantity=20),)
    result = place_furniture(room, requests, catalogue)

    assert result.status is PlacementStatus.PARTIAL
    placed = len(result.placements)
    assert 0 < placed < 20

    written = apply_placements(requests, result)
    assert len(written[0].positions) == placed
    # The request still records what the user asked for; the budget depends on it.
    assert written[0].quantity == 20

    report, validation = validate_recommendations(
        room, list(written), list(catalogue)
    )
    assert len(report.footprints) == placed
    assert [issue.code for issue in report.warnings] == ["unplaced_copies"]
    assert validation.is_valid is True


def test_footprints_match_what_the_spatial_engine_recomputes(
    room: RoomInput, catalogue: tuple[FurnitureItem, ...]
) -> None:
    """An independent validation of the same footprints must agree."""

    result = place_furniture(
        room,
        recommend("sofa_three_seat", "coffee_table", "armchair"),
        catalogue,
    )

    independent = validate_placement(room, result.footprints)

    assert independent.errors == ()
    assert tuple(independent.footprints) == result.footprints


# --------------------------------------------------------------------------- #
# 12. Realistic multi-furniture living room
# --------------------------------------------------------------------------- #


def test_realistic_living_room_is_furnished_completely(
    room: RoomInput, catalogue: tuple[FurnitureItem, ...]
) -> None:
    """Six-item living room, exactly as the advisor would recommend it."""

    requests = recommend(
        "sofa_three_seat",
        "coffee_table",
        "tv_unit",
        "armchair",
        "floor_lamp",
        "bookshelf",
    )

    result = place_furniture(room, requests, catalogue)

    assert result.status is PlacementStatus.COMPLETE
    assert len(result.placements) == 6
    assert result.unplaced == ()

    # Every recommendation is represented, in request order.
    assert [footprint.item_id for footprint in result.footprints] == [
        recommendation.item_id for recommendation in requests
    ]

    # The layout passes the shared validator with no blocking issue and no
    # window warning, because the engine had room to avoid the window.
    assert result.report.errors == ()
    assert "window_obstructed" not in {
        issue.code for issue in result.report.issues
    }

    # It is a real layout: nothing overlaps, nothing leaves the room.
    footprints = result.footprints
    for first_index, first in enumerate(footprints):
        assert rect_inside_room(first.rect, room) is True
        for second in footprints[first_index + 1 :]:
            assert rects_overlap(first.rect, second.rect) is False

    # Circulation: the group does not fill the floor.
    occupied_sqm = sum(
        footprint.rect.width_cm * footprint.rect.depth_cm for footprint in footprints
    ) / 10_000.0
    assert occupied_sqm < room.area_sqm * 0.55


def test_realistic_room_scores_every_criterion(
    room: RoomInput, catalogue: tuple[FurnitureItem, ...]
) -> None:
    result = place_furniture(
        room,
        recommend(
            "sofa_three_seat", "coffee_table", "tv_unit", "armchair", "floor_lamp"
        ),
        catalogue,
    )

    candidate = result.candidate
    assert candidate is not None
    assert {component.name for component in candidate.components} == set(
        LAYOUT_WEIGHTS
    )
    assert candidate.score == pytest.approx(
        sum(component.weight * component.value for component in candidate.components)
    )
    for component in candidate.components:
        assert 0.0 <= component.value <= 1.0


def test_declared_weight_sets_are_normalised() -> None:
    """Every weight set must sum to 1.0, so a score is always in ``0..1``."""

    from core.placement_engine import (
        FREE_STANDING_QUALITY_WEIGHTS,
        FREE_STANDING_WEIGHTS,
        QUALITY_WEIGHTS,
        WALL_ANCHORED_WEIGHTS,
    )

    for name, weights in (
        ("LAYOUT_WEIGHTS", LAYOUT_WEIGHTS),
        ("WALL_ANCHORED_WEIGHTS", WALL_ANCHORED_WEIGHTS),
        ("FREE_STANDING_WEIGHTS", FREE_STANDING_WEIGHTS),
        ("QUALITY_WEIGHTS", QUALITY_WEIGHTS),
        ("FREE_STANDING_QUALITY_WEIGHTS", FREE_STANDING_QUALITY_WEIGHTS),
    ):
        assert sum(weights.values()) == pytest.approx(1.0), name
        assert all(weight >= 0.0 for weight in weights.values()), name


def test_a_bedroom_scenario_places_the_bed_against_a_wall(
    catalogue: tuple[FurnitureItem, ...],
) -> None:
    bedroom = hidden_room(
        320.0,
        380.0,
        door_offset_cm=40.0,
        door_width_cm=80.0,
        window_offset_cm=60.0,
        window_width_cm=140.0,
    )
    bedroom = bedroom.model_copy(update={"room_type": RoomType.BEDROOM})

    result = place_furniture(
        bedroom,
        recommend("bed_double", "wardrobe", "bedside_table", "floor_lamp"),
        catalogue,
    )

    assert result.status is PlacementStatus.COMPLETE
    accepts_layout(bedroom, result.candidate, catalogue)

    bed = next(
        footprint
        for footprint in result.footprints
        if footprint.item_id == "bed_double"
    )
    width_cm, depth_cm = effective_size_cm(160.0, 200.0, bed.rotation_degrees)
    assert (bed.width_cm, bed.depth_cm) == (width_cm, depth_cm)
    # A bed is never free-floating in the middle of the room.
    assert min(
        bed.left_cm,
        bed.bottom_cm,
        bedroom.width_cm - bed.rect.right_cm,
        bedroom.length_cm - bed.rect.top_cm,
    ) <= EPS_CM


# --------------------------------------------------------------------------- #
# Input hygiene
# --------------------------------------------------------------------------- #


def test_room_fixture_is_itself_valid(room: RoomInput) -> None:
    """Guards the whole file: a broken fixture would invalidate every claim."""

    assert validate_room(room) == []


def test_empty_recommendation_list_yields_no_layout(
    room: RoomInput, catalogue: tuple[FurnitureItem, ...]
) -> None:
    result = place_furniture(room, (), catalogue)

    assert result.status is PlacementStatus.FAILED
    assert result.placements == ()
    assert result.unplaced == ()
    assert [note.code for note in result.notes] == ["no_recommendations"]


def test_generator_input_is_accepted(
    room: RoomInput, catalogue: tuple[FurnitureItem, ...]
) -> None:
    """Callers may pass any sequence; the engine must not require a tuple."""

    result = place_furniture(
        room,
        (FurnitureRecommendation(item_id=item_id) for item_id in ("armchair",)),
        catalogue,
    )

    assert result.status is PlacementStatus.COMPLETE
    assert len(result.placements) == 1


def test_empty_catalog_places_nothing(
    room: RoomInput,
) -> None:
    result = place_furniture(room, recommend("sofa_three_seat"), ())

    assert result.status is PlacementStatus.FAILED
    assert result.unplaced[0].reason_code == "unknown_catalog_item"


def test_custom_clearance_values_are_honoured(
    room: RoomInput, catalogue: tuple[FurnitureItem, ...]
) -> None:
    """A caller may widen the clearance; the engine must respect the value."""

    strict_cm = 150.0
    result = place_furniture(
        room,
        recommend("sofa_three_seat", "armchair"),
        catalogue,
        door_clearance_cm=strict_cm,
        window_clearance_cm=strict_cm,
    )

    assert result.candidate is not None
    assert result.validation.is_valid is True

    door_zone = opening_clearance_rect(
        room,
        room.door.wall,
        room.door.offset_cm,
        room.door.width_cm,
        strict_cm,
    )
    window_zone = opening_clearance_rect(
        room,
        room.window.wall,
        room.window.offset_cm,
        room.window.width_cm,
        strict_cm,
    )
    assert door_zone is not None and window_zone is not None
    for footprint in result.footprints:
        assert rects_overlap(footprint.rect, door_zone) is False
        assert rects_overlap(footprint.rect, window_zone) is False
