"""Deterministic furniture placement validation.

Pure geometry over axis-aligned rectangles in centimeters. No Streamlit, no AI.
The room origin is the south-west corner, so ``y`` grows north and ``x`` grows
east.

V1 rules, stated plainly so they are not mistaken for ergonomic standards:

* A furniture footprint must lie entirely inside the room.
* Two footprints may touch edge-to-edge; only a positive-area intersection is an
  overlap.
* A footprint that intrudes on a door clearance zone is a blocking error: the
  doorway would be unusable.
* A footprint that intrudes on a window clearance zone is a warning only: the
  window is not obstructed in a way this application can judge.

Clearance depths are simple illustrative V1 constants, not building-code or
accessibility requirements.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from core.room_engine import EPS_CM, normalize_rotation
from models.schemas import (
    FurnitureItem,
    FurnitureRecommendation,
    RoomInput,
    SpatialValidation,
    Wall,
)

#: Illustrative clearance depth kept free in front of a door, in centimeters.
DEFAULT_DOOR_CLEARANCE_CM: float = 60.0

#: Illustrative clearance depth kept free in front of a window, in centimeters.
DEFAULT_WINDOW_CLEARANCE_CM: float = 30.0


@dataclass(frozen=True)
class Rect:
    """Axis-aligned rectangle: origin (left, bottom) plus size."""

    left_cm: float
    bottom_cm: float
    width_cm: float
    depth_cm: float

    @property
    def right_cm(self) -> float:
        return self.left_cm + self.width_cm

    @property
    def top_cm(self) -> float:
        return self.bottom_cm + self.depth_cm

    @property
    def area_sqm(self) -> float:
        return (self.width_cm * self.depth_cm) / 10_000.0


@dataclass(frozen=True)
class FurnitureFootprint:
    """A placed furniture item, resolved to its rotated rectangle."""

    item_id: str
    label: str
    left_cm: float
    bottom_cm: float
    width_cm: float
    depth_cm: float
    rotation_degrees: int = 0

    @property
    def rect(self) -> Rect:
        return Rect(self.left_cm, self.bottom_cm, self.width_cm, self.depth_cm)


@dataclass(frozen=True)
class PlacementIssue:
    """A single placement problem, classified by severity."""

    severity: str  # "error" or "warning"
    code: str
    message: str


@dataclass(frozen=True)
class PlacementReport:
    """Full deterministic placement result."""

    footprints: tuple[FurnitureFootprint, ...]
    issues: tuple[PlacementIssue, ...] = ()

    @property
    def errors(self) -> tuple[PlacementIssue, ...]:
        return tuple(i for i in self.issues if i.severity == "error")

    @property
    def warnings(self) -> tuple[PlacementIssue, ...]:
        return tuple(i for i in self.issues if i.severity == "warning")

    @property
    def is_valid(self) -> bool:
        return not self.errors


# --------------------------------------------------------------------------- #
# Rotation and primitives
# --------------------------------------------------------------------------- #


def effective_size_cm(
    width_cm: float, depth_cm: float, rotation_degrees: int
) -> tuple[float, float]:
    """Footprint size after rotation.

    A quarter turn swaps width and depth; half and full turns keep them.
    """

    rotation = normalize_rotation(rotation_degrees)
    if rotation in (90, 270):
        return (depth_cm, width_cm)
    return (width_cm, depth_cm)


def make_footprint(
    *,
    item_id: str,
    label: str,
    left_cm: float,
    bottom_cm: float,
    width_cm: float,
    depth_cm: float,
    rotation_degrees: int = 0,
) -> FurnitureFootprint:
    """Build a footprint whose stored width/depth are already rotated.

    Raises ``ValueError`` for a degenerate footprint: a zero or negative side
    would make every boundary and overlap comparison meaningless.
    """

    if width_cm <= 0 or depth_cm <= 0:
        raise ValueError(
            "Furniture dimensions must be greater than zero, got "
            f"{width_cm!r} x {depth_cm!r} cm."
        )

    rotated_width, rotated_depth = effective_size_cm(
        width_cm, depth_cm, rotation_degrees
    )
    return FurnitureFootprint(
        item_id=item_id,
        label=label,
        left_cm=left_cm,
        bottom_cm=bottom_cm,
        width_cm=rotated_width,
        depth_cm=rotated_depth,
        rotation_degrees=normalize_rotation(rotation_degrees),
    )


def rect_intersection_area(first: Rect, second: Rect) -> float:
    """Area shared by two rectangles, in square centimeters.

    Exactly touching rectangles share zero area.
    """

    overlap_width = min(first.right_cm, second.right_cm) - max(
        first.left_cm, second.left_cm
    )
    overlap_depth = min(first.top_cm, second.top_cm) - max(
        first.bottom_cm, second.bottom_cm
    )
    if overlap_width <= EPS_CM or overlap_depth <= EPS_CM:
        return 0.0
    return overlap_width * overlap_depth


def rects_overlap(first: Rect, second: Rect) -> bool:
    """True only when the rectangles share a positive area."""

    return rect_intersection_area(first, second) > EPS_CM


def rect_inside_room(rect: Rect, room: RoomInput) -> bool:
    """True when the rectangle lies fully inside the room boundary."""

    return (
        rect.left_cm >= -EPS_CM
        and rect.bottom_cm >= -EPS_CM
        and rect.right_cm <= room.width_cm + EPS_CM
        and rect.top_cm <= room.length_cm + EPS_CM
    )


def rect_within_wall_span(room: RoomInput, wall: Wall) -> tuple[float, float]:
    """The ``(start, end)`` interval along a wall, in room coordinates."""

    if wall in (Wall.NORTH, Wall.SOUTH):
        return (0.0, room.width_cm)
    return (0.0, room.length_cm)


# --------------------------------------------------------------------------- #
# Opening clearance
# --------------------------------------------------------------------------- #


def opening_clearance_rect(
    room: RoomInput,
    wall: Wall,
    offset_cm: float,
    width_cm: float,
    clearance_cm: float,
) -> Rect | None:
    """The zone kept free on the room side of an opening.

    Returns ``None`` when the clearance is zero or negative, meaning the
    caller does not want this constraint applied.
    """

    if clearance_cm <= EPS_CM:
        return None

    if wall is Wall.SOUTH:
        return Rect(offset_cm, 0.0, width_cm, clearance_cm)
    if wall is Wall.NORTH:
        return Rect(
            offset_cm, room.length_cm - clearance_cm, width_cm, clearance_cm
        )
    if wall is Wall.WEST:
        return Rect(0.0, offset_cm, clearance_cm, width_cm)
    return Rect(room.width_cm - clearance_cm, offset_cm, clearance_cm, width_cm)


# --------------------------------------------------------------------------- #
# Building footprints
# --------------------------------------------------------------------------- #


def _positioned_copies(
    recommendation: FurnitureRecommendation,
) -> tuple[tuple[float, float, int], ...]:
    """The ``(x, y, rotation)`` of every copy the placement engine wrote.

    ``positions`` is authoritative when it is present, because it records one
    entry per copy actually placed. When it is absent the recommendation predates
    the placement engine (or has not been placed), so only the single legacy
    coordinate pair can be read. Nothing is inferred: an empty result means no
    copy has coordinates.
    """

    if recommendation.positions:
        return tuple(
            (
                position.position_x_cm,
                position.position_y_cm,
                normalize_rotation(position.rotation_degrees),
            )
            for position in recommendation.positions
        )

    if (
        recommendation.position_x_cm is None
        or recommendation.position_y_cm is None
    ):
        return ()

    return (
        (
            recommendation.position_x_cm,
            recommendation.position_y_cm,
            normalize_rotation(recommendation.rotation_degrees),
        ),
    )


def build_footprints(
    recommendations: Sequence[FurnitureRecommendation],
    catalog: Sequence[FurnitureItem],
) -> tuple[list[FurnitureFootprint], list[PlacementIssue]]:
    """Resolve recommendations against the catalog.

    Unplaced recommendations (missing coordinates) are reported rather than
    silently dropped, because the caller must know that a recommended item is
    absent from the layout.

    One footprint is produced per *placed copy*: a recommendation with a
    ``positions`` list contributes all of its entries, so a request for four
    chairs is measured as four chairs. A recommendation whose ``positions`` are
    fewer than its ``quantity`` still contributes what it has, with the missing
    copies reported — a partly placed item is never rounded up to its requested
    quantity.
    """

    by_id = {item.item_id: item for item in catalog}
    footprints: list[FurnitureFootprint] = []
    issues: list[PlacementIssue] = []

    for index, recommendation in enumerate(recommendations):
        catalog_item = by_id.get(recommendation.item_id)
        if catalog_item is None:
            issues.append(
                PlacementIssue(
                    severity="error",
                    code="unknown_catalog_item",
                    message=(
                        f"Recommendation {index + 1} references unknown catalog "
                        f"item '{recommendation.item_id}'."
                    ),
                )
            )
            continue

        copies = _positioned_copies(recommendation)
        if not copies:
            issues.append(
                PlacementIssue(
                    severity="warning",
                    code="unplaced_item",
                    message=(
                        f"'{catalog_item.name}' has no placement coordinates and "
                        "is not part of the evaluated layout."
                    ),
                )
            )
            continue

        quantity = recommendation.quantity
        if len(copies) < quantity:
            issues.append(
                PlacementIssue(
                    severity="warning",
                    code="unplaced_copies",
                    message=(
                        f"'{catalog_item.name}' has quantity {quantity} but only "
                        f"{len(copies)} placed "
                        f"{'copy' if len(copies) == 1 else 'copies'}; the "
                        "remaining copies are not part of the evaluated layout."
                    ),
                )
            )

        for left_cm, bottom_cm, rotation_degrees in copies:
            try:
                footprint = make_footprint(
                    item_id=catalog_item.item_id,
                    label=catalog_item.name,
                    left_cm=left_cm,
                    bottom_cm=bottom_cm,
                    width_cm=catalog_item.width_cm,
                    depth_cm=catalog_item.depth_cm,
                    rotation_degrees=rotation_degrees,
                )
            except ValueError as exc:
                # A catalog entry with a degenerate footprint cannot be placed;
                # the problem is reported instead of aborting the layout check.
                issues.append(
                    PlacementIssue(
                        severity="error",
                        code="invalid_footprint",
                        message=f"'{catalog_item.name}' cannot be placed: {exc}",
                    )
                )
                break

            footprints.append(footprint)

    return footprints, issues


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #


def _boundary_issue(
    footprint: FurnitureFootprint, room: RoomInput
) -> PlacementIssue | None:
    rect = footprint.rect
    if rect_inside_room(rect, room):
        return None

    return PlacementIssue(
        severity="error",
        code="outside_room",
        message=(
            f"'{footprint.label}' extends outside the room: it occupies "
            f"x {rect.left_cm:g}-{rect.right_cm:g} cm and "
            f"y {rect.bottom_cm:g}-{rect.top_cm:g} cm, while the room is "
            f"{room.width_cm:g} x {room.length_cm:g} cm."
        ),
    )


def _overlap_issues(
    footprints: Sequence[FurnitureFootprint],
) -> list[PlacementIssue]:
    issues: list[PlacementIssue] = []
    for first_index in range(len(footprints)):
        for second_index in range(first_index + 1, len(footprints)):
            first = footprints[first_index]
            second = footprints[second_index]
            area_cm2 = rect_intersection_area(first.rect, second.rect)
            if area_cm2 <= EPS_CM:
                continue
            issues.append(
                PlacementIssue(
                    severity="error",
                    code="furniture_overlap",
                    message=(
                        f"'{first.label}' and '{second.label}' overlap by "
                        f"{area_cm2 / 10_000.0:.2f} m²."
                    ),
                )
            )
    return issues


def _clearance_issues(
    footprints: Sequence[FurnitureFootprint],
    room: RoomInput,
    *,
    door_clearance_cm: float,
    window_clearance_cm: float,
) -> list[PlacementIssue]:
    issues: list[PlacementIssue] = []

    door_zone = opening_clearance_rect(
        room,
        room.door.wall,
        room.door.offset_cm,
        room.door.width_cm,
        door_clearance_cm,
    )
    window_zone = opening_clearance_rect(
        room,
        room.window.wall,
        room.window.offset_cm,
        room.window.width_cm,
        window_clearance_cm,
    )

    for footprint in footprints:
        if door_zone is not None and rects_overlap(footprint.rect, door_zone):
            issues.append(
                PlacementIssue(
                    severity="error",
                    code="door_blocked",
                    message=(
                        f"'{footprint.label}' blocks the {room.door.wall.value} "
                        f"door clearance zone ({door_clearance_cm:g} cm)."
                    ),
                )
            )
        if window_zone is not None and rects_overlap(footprint.rect, window_zone):
            issues.append(
                PlacementIssue(
                    severity="warning",
                    code="window_obstructed",
                    message=(
                        f"'{footprint.label}' stands within {window_clearance_cm:g} "
                        f"cm of the {room.window.wall.value} window."
                    ),
                )
            )

    return issues


def validate_placement(
    room: RoomInput,
    footprints: Sequence[FurnitureFootprint],
    *,
    extra_issues: Iterable[PlacementIssue] = (),
    door_clearance_cm: float = DEFAULT_DOOR_CLEARANCE_CM,
    window_clearance_cm: float = DEFAULT_WINDOW_CLEARANCE_CM,
) -> PlacementReport:
    """Run every deterministic placement check and collect the results."""

    issues: list[PlacementIssue] = list(extra_issues)

    for footprint in footprints:
        boundary = _boundary_issue(footprint, room)
        if boundary is not None:
            issues.append(boundary)

    issues.extend(_overlap_issues(footprints))
    issues.extend(
        _clearance_issues(
            footprints,
            room,
            door_clearance_cm=door_clearance_cm,
            window_clearance_cm=window_clearance_cm,
        )
    )

    return PlacementReport(footprints=tuple(footprints), issues=tuple(issues))


def to_spatial_validation(report: PlacementReport) -> SpatialValidation:
    """Convert a placement report into the shared validation model.

    ``SpatialValidation`` separates blocking problems (``boundary_violations``
    and ``overlaps``) from non-blocking ones (``warnings``). The model has no
    generic "other errors" field, so every blocking issue that is not a
    furniture-to-furniture overlap is reported under ``boundary_violations``:
    the room-boundary breach, the blocked doorway and the unknown catalog
    reference are all constraints the placement cannot satisfy. Nothing is
    demoted to a warning, so a blocking issue can never read as success.
    """

    return SpatialValidation(
        is_valid=report.is_valid,
        boundary_violations=[
            issue.message
            for issue in report.errors
            if issue.code != "furniture_overlap"
        ],
        overlaps=[
            issue.message
            for issue in report.errors
            if issue.code == "furniture_overlap"
        ],
        warnings=[issue.message for issue in report.warnings],
    )


def validate_recommendations(
    room: RoomInput,
    recommendations: Sequence[FurnitureRecommendation],
    catalog: Sequence[FurnitureItem],
    *,
    door_clearance_cm: float = DEFAULT_DOOR_CLEARANCE_CM,
    window_clearance_cm: float = DEFAULT_WINDOW_CLEARANCE_CM,
) -> tuple[PlacementReport, SpatialValidation]:
    """End-to-end helper: recommendations plus catalog to validated result."""

    footprints, build_issues = build_footprints(recommendations, catalog)
    report = validate_placement(
        room,
        footprints,
        extra_issues=build_issues,
        door_clearance_cm=door_clearance_cm,
        window_clearance_cm=window_clearance_cm,
    )
    return report, to_spatial_validation(report)


__all__ = [
    "DEFAULT_DOOR_CLEARANCE_CM",
    "DEFAULT_WINDOW_CLEARANCE_CM",
    "FurnitureFootprint",
    "PlacementIssue",
    "PlacementReport",
    "Rect",
    "build_footprints",
    "effective_size_cm",
    "make_footprint",
    "opening_clearance_rect",
    "rect_inside_room",
    "rect_intersection_area",
    "rect_within_wall_span",
    "rects_overlap",
    "to_spatial_validation",
    "validate_placement",
    "validate_recommendations",
]
