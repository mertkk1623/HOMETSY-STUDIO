"""Deterministic furniture placement.

The engine proposes a layout; :mod:`core.spatial_engine` decides whether that
layout is acceptable. No geometry rule is re-implemented here: candidate
filtering reuses the spatial engine's primitives (``rect_inside_room``,
``rects_overlap``, ``opening_clearance_rect``, ``effective_size_cm``) and the
selected layout is checked by ``validate_placement``. Its report is the only
statement about validity that leaves this module.

The AI never supplies coordinates. ``FurnitureRecommendation`` may carry
``position_x_cm``/``position_y_cm`` as ``None``; the engine ignores those fields
and computes every coordinate itself, so a ``None`` position is normal input,
not an error.

Algorithm (V1, deliberately small)
-----------------------------------
1. Resolve each recommendation against the catalog. An unknown identifier is
   reported as an unplaced item, never dropped and never guessed.
2. For each of four wall-preference strategies, place the items greedily:
   largest footprint first (fewest valid positions), each item at the
   best-scoring free position of its two rectangle orientations.
3. Score every produced layout on six weighted criteria (see ``LAYOUT_WEIGHTS``).
4. Rank layouts by completeness first, then by score, then by strategy order,
   and validate the winner through the spatial engine.

Candidate positions are wall anchors on a fixed step, plus an interior grid and
the room centre. Every step is a constant, so the same inputs always produce the
same candidates in the same order.

Rotation
--------
The advisor's ``rotation_degrees`` is a hint, not an instruction: the advisor is
told not to decide placement and never sees the room's geometry. Both the
requested orientation and its quarter turn are therefore tried, and the better
scoring one wins. The orientation actually used is stored on the footprint, so
the drawing layer never has to guess, and a half turn is not a separate case
because V1 has no notion of which way a piece faces.

Scoring
-------
Layout criteria, used to compare complete candidates:

===================  ======  =========================================
criterion            weight  why
===================  ======  =========================================
boundary_fit         0.15    legality; kept in the score so a generation
                             bug lowers the score instead of hiding
door_access          0.20    the doorway is the only mandatory
                             circulation point in the room
window_clearance     0.15    daylight matters, but the existing engine
                             treats obstruction as a warning only
overlap_free         0.15    legality; scored for the same reason as
                             boundary_fit
circulation          0.20    usable free floor is the second functional
                             requirement after the doorway
placement_quality    0.15    wall anchoring, sensible spacing, central
                             pieces in the middle
===================  ======  =========================================

While placing a single item the engine uses a cheaper per-item quality figure
(``_item_quality``). It shares the criteria above but adds three
generation-only terms: ``anchor`` (the item's longest edge actually lies on a
wall), ``position`` (how central the item is *along* the wall it touches) and
``wall_preference`` (a small tiebreaker for the strategy's wall). Catalog
categories that read as wall pieces — seating, storage, sleeping — weight
anchoring heavily; tables, lighting and decor are scored on centrality instead,
because a coffee table belongs in the middle of the room. All weights are
constants below, so any layout can be re-derived by hand.

The layout score itself is strategy-neutral on purpose: ``QUALITY_WEIGHTS`` and
``FREE_STANDING_QUALITY_WEIGHTS`` contain no ``wall_preference`` term, so one
layout can never win merely because a different wall order was used to build it.

Resolution and failure
----------------------
Every recommendation is resolved against the catalog by identifier. An unknown
identifier, an unusable rotation or a position that cannot be found is reported
as :class:`UnplacedFurniture` with a count and a sentence naming the item and the
obstacle, so nothing is dropped silently.

:func:`place_furniture` returns a :class:`PlacementResult` whose status is one of:

* ``COMPLETE`` — every requested copy was placed and the spatial engine accepts
  the layout;
* ``PARTIAL`` — some copies were placed and validated, others could not be
  placed; the validated layout is offered, but the status is not success;
* ``FAILED`` — nothing was placed, or the spatial engine rejected the best
  candidate; ``candidate`` is ``None`` so no caller can draw a rejected layout.

``apply_placements`` is the only function that writes coordinates back onto
``FurnitureRecommendation``, so the stored geometry is always the geometry that
was validated.

Known V1 limitations
--------------------
* Only rectangular footprints, so a large area rug is treated as solid furniture
  and will usually be reported unplaced next to a full seating group.
* One footprint per copy for every item. ``quantity`` is placed copy by copy,
  which is right for chairs and small tables but would over-furnish a room if
  the advisor asked for a run of wardrobes.
* The placement is greedy and single-pass: an early item that takes a good
  position is never reconsidered, so a better global arrangement may exist. The
  four strategies mitigate this without searching the whole space.
* Wall anchoring prefers the *longest* side against a wall. That suits sofas,
  beds and storage but is wrong for an intentionally free-standing desk.
* Room-type suitability is a catalog concern (``core.validation``), not a
  geometric one: this engine places whatever the catalog resolves.
* The engine cannot reason about sightlines, focal points or a room's front
  face, so "placement quality" is a heuristic about walls, spacing and free
  floor — not a judgement about whether the room looks good.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from core.room_engine import EPS_CM, normalize_rotation, wall_length_cm
from core.spatial_engine import (
    DEFAULT_DOOR_CLEARANCE_CM,
    DEFAULT_WINDOW_CLEARANCE_CM,
    FurnitureFootprint,
    PlacementIssue,
    PlacementReport,
    Rect,
    effective_size_cm,
    make_footprint,
    opening_clearance_rect,
    rect_inside_room,
    rect_intersection_area,
    rects_overlap,
    to_spatial_validation,
    validate_placement,
)
from core.validation import ValidationFinding, placement_findings
from models.schemas import (
    ConceptCompatibility,
    FurnitureItem,
    FurniturePosition,
    FurnitureRecommendation,
    IntentCheck,
    PlacedFootprint,
    PlacementOutcome,
    PlacementStatus,
    RoomInput,
    ScoreTerm,
    SpatialValidation,
    UnplacedItem,
    Wall,
    WallPreference,
)

# --------------------------------------------------------------------------- #
# Tuning constants
# --------------------------------------------------------------------------- #

#: Step between two wall-anchored candidate positions, in centimeters.
ANCHOR_STEP_CM: float = 20.0

#: Step of the interior candidate grid, in centimeters.
GRID_STEP_CM: float = 40.0

#: Distance from a wall over which "standing against the wall" stops counting,
#: in centimeters.
WALL_ANCHOR_RANGE_CM: float = 60.0

#: Free depth in front of a doorway that counts as a comfortable approach,
#: in centimeters. Only a scoring target; the spatial engine owns the rule.
DOOR_COMFORT_CM: float = 90.0

#: Depth of the doorway approach band measured by the door criterion.
DOOR_APPROACH_CM: float = 90.0

#: Gap between two footprints that counts as generous spacing, in centimeters.
SPACING_COMFORT_CM: float = 30.0

#: Below this share of free floor the circulation criterion scores zero.
CIRCULATION_FLOOR_RATIO: float = 0.25

#: At or above this share of free floor the circulation criterion scores one.
CIRCULATION_COMFORT_RATIO: float = 0.55

#: Catalog categories that read as wall pieces in the approved style library.
WALL_ANCHORED_CATEGORIES: frozenset[str] = frozenset(
    {"Seating", "Storage", "Sleeping"}
)

#: Layout-level weights. Sum is 1.0; the rationale is in the module docstring.
LAYOUT_WEIGHTS: dict[str, float] = {
    "boundary_fit": 0.15,
    "door_access": 0.20,
    "window_clearance": 0.15,
    "overlap_free": 0.15,
    "circulation": 0.20,
    "placement_quality": 0.15,
}

#: Per-item weights for pieces that belong against a wall. ``wall_preference``
#: is a small tiebreaker for which wall the strategy wants; ``position`` is the
#: larger term and rewards a sensible spot *along* that wall, so an item is not
#: crammed into a corner merely because the corner is on the preferred wall.
#: Used only while generating; see ``QUALITY_WEIGHTS`` for the neutral view.
WALL_ANCHORED_WEIGHTS: dict[str, float] = {
    "anchor": 0.30,
    "wall_preference": 0.05,
    "position": 0.20,
    "centrality": 0.00,
    "window": 0.15,
    "door": 0.10,
    "spacing": 0.20,
}

#: Per-item weights for pieces that belong in the middle of the room. These get
#: no ``position`` credit: a coffee table in the middle of a wall is worse than
#: one in the middle of the room, not better.
FREE_STANDING_WEIGHTS: dict[str, float] = {
    "anchor": 0.10,
    "wall_preference": 0.00,
    "position": 0.00,
    "centrality": 0.40,
    "window": 0.20,
    "door": 0.10,
    "spacing": 0.20,
}

#: Weights of the neutral per-item quality figure used to score a finished
#: layout. Deliberately strategy-free: one layout must not look better merely
#: because it was generated under a different wall order.
QUALITY_WEIGHTS: dict[str, float] = {
    "anchor": 0.35,
    "position": 0.10,
    "centrality": 0.00,
    "window": 0.20,
    "door": 0.15,
    "spacing": 0.20,
}

#: The same neutral figure for a piece that belongs in the middle of the room.
FREE_STANDING_QUALITY_WEIGHTS: dict[str, float] = {
    "anchor": 0.05,
    "position": 0.00,
    "centrality": 0.40,
    "window": 0.20,
    "door": 0.15,
    "spacing": 0.20,
}


# ``PlacementStatus`` is imported from :mod:`models.schemas` rather than defined
# here. The status is stored in the workflow state as part of
# ``PlacementOutcome``, so the vocabulary belongs with the stored models; keeping
# a second enum would give the interface two unequal ``COMPLETE`` objects. It is
# re-exported in ``__all__`` so existing imports keep working.


@dataclass(frozen=True)
class PlacementStrategy:
    """One deterministic wall-preference order."""

    name: str
    wall_order: tuple[Wall, ...]


STRATEGIES: tuple[PlacementStrategy, ...] = (
    PlacementStrategy(
        "north-first", (Wall.NORTH, Wall.EAST, Wall.WEST, Wall.SOUTH)
    ),
    PlacementStrategy(
        "east-first", (Wall.EAST, Wall.NORTH, Wall.SOUTH, Wall.WEST)
    ),
    PlacementStrategy(
        "south-first", (Wall.SOUTH, Wall.EAST, Wall.WEST, Wall.NORTH)
    ),
    PlacementStrategy(
        "west-first", (Wall.WEST, Wall.NORTH, Wall.SOUTH, Wall.EAST)
    ),
)


# --------------------------------------------------------------------------- #
# Result types
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class PlacedFurniture:
    """One footprint the engine placed, with its position in the request."""

    request_index: int
    footprint: FurnitureFootprint
    wall_anchored: bool = True

    @property
    def item_id(self) -> str:
        return self.footprint.item_id

    @property
    def label(self) -> str:
        return self.footprint.label

    @property
    def rotation_degrees(self) -> int:
        return self.footprint.rotation_degrees

    @property
    def rect(self) -> Rect:
        return self.footprint.rect


@dataclass(frozen=True)
class UnplacedFurniture:
    """Recommended copies the engine could not place, and why."""

    item_id: str
    label: str
    count: int
    reason_code: str
    reason: str


@dataclass(frozen=True)
class ScoreComponent:
    """One weighted criterion of a layout score."""

    name: str
    weight: float
    value: float

    @property
    def contribution(self) -> float:
        return round(self.weight * self.value, 6)


@dataclass(frozen=True)
class LayoutCandidate:
    """One complete attempt: what could be placed, and how good it is."""

    strategy: str
    placements: tuple[PlacedFurniture, ...] = ()
    unplaced: tuple[UnplacedFurniture, ...] = ()
    components: tuple[ScoreComponent, ...] = ()

    @property
    def score(self) -> float:
        return round(sum(c.weight * c.value for c in self.components), 6)

    @property
    def placed_count(self) -> int:
        return len(self.placements)

    @property
    def unplaced_count(self) -> int:
        return sum(item.count for item in self.unplaced)

    @property
    def requested_count(self) -> int:
        return self.placed_count + self.unplaced_count

    @property
    def is_complete(self) -> bool:
        return not self.unplaced

    @property
    def footprints(self) -> tuple[FurnitureFootprint, ...]:
        return tuple(placement.footprint for placement in self.placements)

    def component(self, name: str) -> float:
        for component in self.components:
            if component.name == name:
                return component.value
        raise KeyError(f"Unknown layout criterion: {name!r}")


@dataclass(frozen=True)
class PlacementResult:
    """The engine's answer, together with the spatial engine's verdict.

    ``candidate`` is set only for a layout the spatial engine accepts, so a
    rejected layout can never be drawn by accident. ``best`` always holds the
    highest-ranked attempt, which is what makes a failure explainable: the
    caller can still see which items were left out and why. Every attempt is
    kept in ``candidates`` for diagnosis.

    ``findings`` is the same placement report read through
    :func:`core.validation.placement_findings`, so the interface can merge it
    with the room, catalog and budget findings without a second conversion.
    """

    status: PlacementStatus
    candidates: tuple[LayoutCandidate, ...] = ()
    best: LayoutCandidate | None = None
    candidate: LayoutCandidate | None = None
    report: PlacementReport | None = None
    validation: SpatialValidation | None = None
    findings: tuple[ValidationFinding, ...] = ()
    notes: tuple[PlacementIssue, ...] = ()

    @property
    def placements(self) -> tuple[PlacedFurniture, ...]:
        return self.candidate.placements if self.candidate else ()

    @property
    def footprints(self) -> tuple[FurnitureFootprint, ...]:
        return self.candidate.footprints if self.candidate else ()

    @property
    def unplaced(self) -> tuple[UnplacedFurniture, ...]:
        """Items the engine could not place, from the highest-ranked attempt."""

        return self.best.unplaced if self.best else ()

    @property
    def is_complete(self) -> bool:
        return self.status is PlacementStatus.COMPLETE

    @property
    def is_partial(self) -> bool:
        return self.status is PlacementStatus.PARTIAL

    @property
    def is_failed(self) -> bool:
        return self.status is PlacementStatus.FAILED

    @property
    def messages(self) -> tuple[str, ...]:
        """Engine notes followed by the validator's own messages."""

        texts = [note.message for note in self.notes]
        if self.report is not None:
            texts.extend(issue.message for issue in self.report.issues)
        return tuple(texts)

    def to_outcome(self) -> PlacementOutcome:
        """The storable, drawable summary of this result.

        Only a layout the spatial engine accepted contributes footprints: a
        ``FAILED`` result carries no ``placed`` entries at all, so no drawing
        layer can render a rejected candidate even by accident. Scores likewise
        come from ``best`` only when a candidate was validated, because the
        score of a rejected attempt is not an achieved result.

        Unplaced copies always come from ``best`` — that is what makes a failure
        explainable — and the engine's notes are preserved in order.
        """

        validated = self.candidate is not None
        best = self.best

        placed: list[PlacedFootprint] = []
        if self.candidate is not None:
            placed = [
                PlacedFootprint(
                    item_id=footprint.item_id,
                    label=footprint.label,
                    left_cm=footprint.left_cm,
                    bottom_cm=footprint.bottom_cm,
                    width_cm=footprint.width_cm,
                    depth_cm=footprint.depth_cm,
                    rotation_degrees=footprint.rotation_degrees,
                )
                for footprint in self.candidate.footprints
            ]

        unplaced: list[UnplacedItem] = []
        if best is not None:
            unplaced = [
                UnplacedItem(
                    item_id=item.item_id,
                    label=item.label,
                    count=item.count,
                    reason_code=item.reason_code,
                    reason=item.reason,
                )
                for item in best.unplaced
            ]

        score_terms: list[ScoreTerm] = []
        if validated and best is not None:
            score_terms = [
                ScoreTerm(name=c.name, weight=c.weight, value=c.value)
                for c in best.components
            ]

        return PlacementOutcome(
            status=self.status,
            strategy=best.strategy if best is not None else "",
            score=best.score if validated and best is not None else None,
            placed=placed,
            unplaced=unplaced,
            score_terms=score_terms,
            notes=[issue.message for issue in self.notes],
        )


# --------------------------------------------------------------------------- #
# Small numeric helpers
# --------------------------------------------------------------------------- #


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _clean(value: float) -> float:
    """Round a coordinate to a stable representation."""

    return round(value + 0.0, 6)


def _offsets(limit_cm: float, step_cm: float) -> tuple[float, ...]:
    """Deterministic offsets from 0 to ``limit_cm`` inclusive.

    The far end and the centre are always present, so an item can sit flush
    against either end of a wall or exactly in the middle of the room.
    """

    if limit_cm <= EPS_CM:
        return (0.0,)

    values: list[float] = []
    position = 0.0
    while position < limit_cm - EPS_CM:
        values.append(_clean(position))
        position += step_cm
    values.append(_clean(limit_cm))
    values.append(_clean(limit_cm / 2.0))
    return tuple(sorted(set(values)))


def _wall_gap_cm(rect: Rect, room: RoomInput) -> float:
    """Distance from a footprint to the nearest room wall."""

    return max(
        0.0,
        min(
            rect.left_cm,
            rect.bottom_cm,
            room.width_cm - rect.right_cm,
            room.length_cm - rect.top_cm,
        ),
    )


def _wall_contact_cm(rect: Rect, room: RoomInput) -> float:
    """Length of the footprint edge that actually lies on a wall.

    A sofa turned side-on to a wall touches it with its short edge, which reads
    as "against the wall" by distance alone but is not what a person means by
    it. Contact length distinguishes the two cases.
    """

    contact_cm = 0.0
    if rect.left_cm <= EPS_CM:
        contact_cm = max(contact_cm, rect.depth_cm)
    if rect.bottom_cm <= EPS_CM:
        contact_cm = max(contact_cm, rect.width_cm)
    if abs(rect.right_cm - room.width_cm) <= EPS_CM:
        contact_cm = max(contact_cm, rect.depth_cm)
    if abs(rect.top_cm - room.length_cm) <= EPS_CM:
        contact_cm = max(contact_cm, rect.width_cm)
    return contact_cm


def _anchor_score(rect: Rect, room: RoomInput) -> float:
    """How strongly a footprint reads as anchored to a wall, in ``0..1``.

    Full marks when its longest side lies on a wall, zero when it floats more
    than ``WALL_ANCHOR_RANGE_CM`` away from every wall.
    """

    longest_cm = max(rect.width_cm, rect.depth_cm)
    contact_cm = _wall_contact_cm(rect, room)
    near_wall = _clip01(1.0 - _wall_gap_cm(rect, room) / WALL_ANCHOR_RANGE_CM)
    if longest_cm <= EPS_CM:
        return near_wall
    return round(near_wall * (contact_cm / longest_cm), 6)


def _rect_gap_cm(first: Rect, second: Rect) -> float:
    """Shortest distance between two rectangles; 0.0 when they touch."""

    gap_x = max(
        0.0,
        first.left_cm - second.right_cm,
        second.left_cm - first.right_cm,
    )
    gap_y = max(
        0.0,
        first.bottom_cm - second.top_cm,
        second.bottom_cm - first.top_cm,
    )
    return (gap_x * gap_x + gap_y * gap_y) ** 0.5


def _wall_preference(
    rect: Rect, room: RoomInput, wall_order: tuple[Wall, ...]
) -> float:
    """How early in the strategy's wall order this footprint's wall appears.

    An empty ``wall_order`` means "no strategy is being applied", which is how
    the layout-level score stays strategy-neutral: generation may prefer a wall,
    but the comparison between finished layouts must not.

    A footprint can touch a wall that is absent from ``wall_order`` — that is
    the normal case when a strategy is restricted to one preferred wall and the
    piece lands flush against a neighbouring one. Such a wall is simply not in
    the order, so it ranks last rather than raising.
    """

    if not wall_order:
        return 0.0

    touching = walls_touched(rect, room)
    if not touching:
        return 0.0
    best = min(
        (
            wall_order.index(wall)
            for wall in touching
            if wall in wall_order
        ),
        default=len(wall_order),
    )
    return round(1.0 - best / len(wall_order), 6)


def _centrality(rect: Rect, room: RoomInput) -> float:
    """1.0 at the centre of the room, 0.0 at a corner."""

    centre_x = rect.left_cm + rect.width_cm / 2.0
    centre_y = rect.bottom_cm + rect.depth_cm / 2.0
    offset_x = (centre_x - room.width_cm / 2.0) / (room.width_cm / 2.0)
    offset_y = (centre_y - room.length_cm / 2.0) / (room.length_cm / 2.0)
    distance = (offset_x * offset_x + offset_y * offset_y) ** 0.5
    return _clip01(1.0 - distance / (2.0**0.5))


def _along_wall_position(rect: Rect, room: RoomInput) -> float:
    """How central the footprint is along the wall it touches.

    Full marks for the middle of a wall, zero for either end. This is what stops
    the search from choosing a corner simply because a corner is available.
    """

    if abs(rect.bottom_cm) <= EPS_CM or abs(rect.top_cm - room.length_cm) <= EPS_CM:
        span_cm = room.width_cm
        centre_cm = rect.left_cm + rect.width_cm / 2.0
    elif abs(rect.left_cm) <= EPS_CM or abs(rect.right_cm - room.width_cm) <= EPS_CM:
        span_cm = room.length_cm
        centre_cm = rect.bottom_cm + rect.depth_cm / 2.0
    else:
        return 0.0

    if span_cm <= EPS_CM:
        return 0.0
    distance = abs(centre_cm - span_cm / 2.0)
    return _clip01(1.0 - 2.0 * distance / span_cm)


# --------------------------------------------------------------------------- #
# Openings
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class _Zones:
    """Clearance zones the placement has to work around."""

    door: Rect | None
    window: Rect | None
    door_access: Rect | None


def _door_access_rect(
    room: RoomInput, door_zone: Rect | None, approach_cm: float
) -> Rect | None:
    """The clearance zone extended into the room by the approach band.

    Blocking the clearance zone itself is a hard error in the spatial engine;
    the extension is where a piece may stand but starts to feel cramped, so it
    only affects the score.
    """

    if door_zone is None:
        return None

    depth_cm = min(approach_cm + door_zone.depth_cm, room.length_cm)
    width_cm = min(approach_cm + door_zone.width_cm, room.width_cm)

    if room.door.wall is Wall.SOUTH:
        return Rect(door_zone.left_cm, 0.0, door_zone.width_cm, depth_cm)
    if room.door.wall is Wall.NORTH:
        return Rect(
            door_zone.left_cm,
            room.length_cm - depth_cm,
            door_zone.width_cm,
            depth_cm,
        )
    if room.door.wall is Wall.WEST:
        return Rect(0.0, door_zone.bottom_cm, width_cm, door_zone.depth_cm)
    return Rect(
        room.width_cm - width_cm,
        door_zone.bottom_cm,
        width_cm,
        door_zone.depth_cm,
    )


def _zones(
    room: RoomInput,
    door_clearance_cm: float,
    window_clearance_cm: float,
) -> _Zones:
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
    return _Zones(
        door=door_zone,
        window=window_zone,
        door_access=_door_access_rect(room, door_zone, DOOR_APPROACH_CM),
    )


# --------------------------------------------------------------------------- #
# Resolution
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class _Request:
    """A catalog item resolved from one recommendation."""

    index: int
    item: FurnitureItem
    quantity: int
    requested_rotation: int
    preferred_wall: Wall | None = None
    wall_priority: WallPreference = WallPreference.PREFERRED

    @property
    def area_cm2(self) -> float:
        return self.item.width_cm * self.item.depth_cm

    @property
    def is_wall_anchored(self) -> bool:
        return self.item.category in WALL_ANCHORED_CATEGORIES

    @property
    def has_wall_intent(self) -> bool:
        return self.preferred_wall is not None


def _resolve(
    recommendations: tuple[FurnitureRecommendation, ...],
    catalog: tuple[FurnitureItem, ...],
) -> tuple[tuple[_Request, ...], tuple[UnplacedFurniture, ...]]:
    by_id = {item.item_id: item for item in catalog}
    requests: list[_Request] = []
    unplaced: list[UnplacedFurniture] = []

    for index, recommendation in enumerate(recommendations):
        item = by_id.get(recommendation.item_id)
        if item is None:
            unplaced.append(
                UnplacedFurniture(
                    item_id=recommendation.item_id,
                    label=recommendation.item_id,
                    count=recommendation.quantity,
                    reason_code="unknown_catalog_item",
                    reason=(
                        f"Recommendation {index + 1} references unknown catalog "
                        f"item '{recommendation.item_id}', so it cannot be "
                        "placed."
                    ),
                )
            )
            continue

        try:
            rotation = normalize_rotation(recommendation.rotation_degrees)
        except ValueError as exc:
            unplaced.append(
                UnplacedFurniture(
                    item_id=item.item_id,
                    label=item.name,
                    count=recommendation.quantity,
                    reason_code="unsupported_rotation",
                    reason=str(exc),
                )
            )
            continue

        requests.append(
            _Request(
                index=index,
                item=item,
                quantity=recommendation.quantity,
                requested_rotation=rotation,
                preferred_wall=recommendation.preferred_wall,
                wall_priority=recommendation.wall_priority,
            )
        )

    return tuple(requests), tuple(unplaced)


# --------------------------------------------------------------------------- #
# Candidate generation
# --------------------------------------------------------------------------- #


def rotation_candidates(requested_degrees: int) -> tuple[int, int]:
    """The two rectangle orientations worth testing for one item.

    A half turn keeps the footprint, and V1 has no notion of a front face, so
    the requested orientation and its quarter turn are the only distinct
    shapes. Raises ``ValueError`` when the angle is not a multiple of 90.
    """

    rotation = normalize_rotation(requested_degrees)
    return (rotation, (rotation + 90) % 360)


def _wall_rect(
    room: RoomInput,
    wall: Wall,
    offset_cm: float,
    size_x_cm: float,
    size_y_cm: float,
) -> Rect:
    """A footprint sitting flush against one wall.

    ``size_x_cm``/``size_y_cm`` are the axes extents of the chosen orientation.
    The rectangle is returned as-is on every wall, so the footprint stored later
    by ``make_footprint`` is the same rectangle that was tested here. Which
    orientation reads as "back to the wall" is left to the score.
    """

    if wall is Wall.SOUTH:
        return Rect(offset_cm, 0.0, size_x_cm, size_y_cm)
    if wall is Wall.NORTH:
        return Rect(
            offset_cm, room.length_cm - size_y_cm, size_x_cm, size_y_cm
        )
    if wall is Wall.WEST:
        return Rect(0.0, offset_cm, size_x_cm, size_y_cm)
    return Rect(
        room.width_cm - size_x_cm, offset_cm, size_x_cm, size_y_cm
    )


def _candidate_rects(
    room: RoomInput,
    request: _Request,
    wall_order: tuple[Wall, ...],
    *,
    walls_only: Wall | None = None,
):
    """Every position the engine is willing to test, in a fixed order.

    ``walls_only`` restricts the search to positions flush against one named
    wall and **skips the interior grid sweep entirely**. This is what makes a
    preferred-wall intent real: reordering ``wall_order`` alone does not
    restrict anything, because the grid sweep that follows always offers every
    free spot in the room, and a free-standing position can outscore a wall one.

    The restriction is a candidate-set change, not a scoring change, so the
    weights and the layout score keep their existing meaning.
    """

    item = request.item
    for rotation in rotation_candidates(request.requested_rotation):
        size_x_cm, size_y_cm = effective_size_cm(
            item.width_cm, item.depth_cm, rotation
        )
        if size_x_cm > room.width_cm or size_y_cm > room.length_cm:
            # A quarter turn may still fit, so only this orientation is skipped.
            continue

        walls = (walls_only,) if walls_only is not None else wall_order
        for wall in walls:
            span_cm = wall_length_cm(room.width_cm, room.length_cm, wall)
            along_cm = (
                size_y_cm if wall in (Wall.WEST, Wall.EAST) else size_x_cm
            )
            for offset_cm in _offsets(span_cm - along_cm, ANCHOR_STEP_CM):
                yield rotation, _wall_rect(
                    room, wall, offset_cm, size_x_cm, size_y_cm
                )

        if walls_only is not None:
            # A preferred wall is a wall. Handing the search the whole floor as
            # well would let a free-standing spot win, which is the bug this
            # restriction exists to prevent.
            continue

        for bottom_cm in _offsets(room.length_cm - size_y_cm, GRID_STEP_CM):
            for left_cm in _offsets(room.width_cm - size_x_cm, GRID_STEP_CM):
                yield rotation, Rect(left_cm, bottom_cm, size_x_cm, size_y_cm)


def _quality_components(
    rect: Rect,
    others: list[Rect],
    room: RoomInput,
    zones: _Zones,
) -> dict[str, float]:
    """The unweighted per-item quality terms."""

    window = 1.0
    if zones.window is not None and rects_overlap(rect, zones.window):
        window = 0.0

    door = 1.0
    if zones.door_access is not None:
        door = _clip01(
            _rect_gap_cm(rect, zones.door_access) / DOOR_COMFORT_CM
        )

    spacing = 1.0
    if others:
        spacing = min(
            _clip01(_rect_gap_cm(rect, other) / SPACING_COMFORT_CM)
            for other in others
        )

    return {
        "anchor": _anchor_score(rect, room),
        "position": _along_wall_position(rect, room),
        "centrality": _centrality(rect, room),
        "window": window,
        "door": door,
        "spacing": spacing,
    }


def _weighted(terms: dict[str, float], weights: dict[str, float]) -> float:
    return round(sum(weights[name] * terms[name] for name in weights), 6)


def _item_quality(
    rect: Rect,
    others: list[Rect],
    room: RoomInput,
    zones: _Zones,
    *,
    wall_anchored: bool,
    wall_order: tuple[Wall, ...],
) -> float:
    """How good one position is while a layout is being generated."""

    terms = _quality_components(rect, others, room, zones)
    terms["wall_preference"] = _wall_preference(rect, room, wall_order)
    weights = WALL_ANCHORED_WEIGHTS if wall_anchored else FREE_STANDING_WEIGHTS
    return _weighted(terms, weights)


def _neutral_quality(
    rect: Rect,
    others: list[Rect],
    room: RoomInput,
    zones: _Zones,
    *,
    wall_anchored: bool,
) -> float:
    """Strategy-neutral quality of one placed item, used to score a layout."""

    terms = _quality_components(rect, others, room, zones)
    weights = (
        QUALITY_WEIGHTS if wall_anchored else FREE_STANDING_QUALITY_WEIGHTS
    )
    return _weighted(terms, weights)


def _unplaced_code(request: _Request) -> str:
    """The reason code for an item the greedy pass could not place.

    A *required* wall that could not host the piece is its own code, so the
    interface can distinguish "the concept asked for a wall that does not work"
    from "the room is too full". A merely preferred wall falls back before it
    can fail, so an unplaced preferred item is an ordinary space problem.
    """

    if (
        request.preferred_wall is not None
        and request.wall_priority is WallPreference.REQUIRED
    ):
        return "required_wall_unavailable"
    return "no_valid_position"


def _unplaced_reason(
    request: _Request,
    room: RoomInput,
    placed_count: int,
    free_area_sqm: float,
) -> str:
    """Explain as precisely as the algorithm can why an item was left out."""

    item = request.item
    fits_alone = any(
        width_cm <= room.width_cm + EPS_CM
        and depth_cm <= room.length_cm + EPS_CM
        for width_cm, depth_cm in (
            effective_size_cm(item.width_cm, item.depth_cm, rotation)
            for rotation in rotation_candidates(request.requested_rotation)
        )
    )
    dimensions = f"{item.width_cm:g} x {item.depth_cm:g} cm"

    if not fits_alone:
        return (
            f"'{item.name}' ({dimensions}) does not fit inside the "
            f"{room.width_cm:g} x {room.length_cm:g} cm room in any supported "
            "orientation."
        )

    if request.preferred_wall is not None:
        wall_name = request.preferred_wall.value
        if request.wall_priority is WallPreference.REQUIRED:
            if placed_count == 0:
                return (
                    f"No clear position was found for '{item.name}' "
                    f"({dimensions}) on the {wall_name} wall: every point along "
                    "it overlaps the door clearance zone or leaves the room, "
                    f"although {free_area_sqm:.2f} m² of floor is free "
                    "elsewhere. The wall was required, so the item was not "
                    "moved to another wall."
                )
            return (
                f"No clear position was found for '{item.name}' ({dimensions}) "
                f"on the {wall_name} wall: every point along it overlaps the "
                f"door clearance zone or the {placed_count} item(s) already "
                f"placed, although {free_area_sqm:.2f} m² of floor is free "
                "elsewhere. The wall was required, so the item was not moved "
                "to another wall."
            )

        # PREFERRED: the wall was a wish, and the unrestricted fallback ran.
        # The piece is out of the room because no wall *and* no free floor could
        # take it — claiming it "was required" here would be false.
        return (
            f"No clear position was found for '{item.name}' ({dimensions}) "
            f"anywhere in the room. The {wall_name} wall was preferred but "
            "could not host it, and the unrestricted search that followed "
            f"found no free floor either, although {free_area_sqm:.2f} m² was "
            "still unoccupied."
        )

    if placed_count == 0:
        return (
            f"No clear rectangular position was found for '{item.name}' "
            f"({dimensions}): every candidate overlapped the door clearance "
            f"zone or left the room, although {free_area_sqm:.2f} m² of floor "
            "is still free."
        )

    return (
        f"No clear rectangular position was found for '{item.name}' "
        f"({dimensions}): every candidate overlapped the door clearance zone "
        f"or the {placed_count} item(s) already placed, although "
        f"{free_area_sqm:.2f} m² of floor is still free."
    )


def _place_request(
    room: RoomInput,
    request: _Request,
    placed: list[PlacedFurniture],
    zones: _Zones,
    wall_order: tuple[Wall, ...],
) -> FurnitureFootprint | None:
    """Best free position for one copy, or ``None`` when none exists.

    When the request carries a preferred wall the search is restricted to that
    wall first. A ``PREFERRED`` intent falls back to the unrestricted search so
    the piece is still placed; a ``REQUIRED`` intent does not, and returns
    ``None`` so the caller can report the miss instead of moving the piece to a
    wall the concept never asked for.
    """

    if request.preferred_wall is not None:
        footprint = _best_rect_on_wall(
            room,
            request,
            placed,
            zones,
            request.preferred_wall,
            _intent_wall_order(request.preferred_wall, wall_order),
        )
        if footprint is not None:
            return footprint
        if request.wall_priority is WallPreference.REQUIRED:
            return None
        # PREFERRED: the wall could not host the piece, so fall through to the
        # unrestricted search rather than losing the item entirely.

    return _best_rect(
        room,
        _candidate_rects(room, request, wall_order),
        request,
        placed,
        zones,
        wall_order,
    )


def _intent_wall_order(
    preferred: Wall, wall_order: tuple[Wall, ...]
) -> tuple[Wall, ...]:
    """The strategy's order with the preferred wall moved to the front.

    The scoring order still has to be a full ordering for ``_wall_preference``
    to behave meaningfully, so the remaining walls follow the strategy as usual.
    """

    return (preferred,) + tuple(wall for wall in wall_order if wall is not preferred)


def _best_rect_on_wall(
    room: RoomInput,
    request: _Request,
    placed: list[PlacedFurniture],
    zones: _Zones,
    wall: Wall,
    wall_order: tuple[Wall, ...],
) -> FurnitureFootprint | None:
    """The best position for one copy restricted to a single wall."""

    return _best_rect(
        room,
        _candidate_rects(room, request, wall_order, walls_only=wall),
        request,
        placed,
        zones,
        wall_order,
    )


def _best_rect(
    room: RoomInput,
    candidates,
    request: _Request,
    placed: list[PlacedFurniture],
    zones: _Zones,
    wall_order: tuple[Wall, ...],
) -> FurnitureFootprint | None:
    """Score the candidate rectangles and return the footprint of the best."""

    rects = [placement.footprint.rect for placement in placed]
    best: tuple[float, int, Rect] | None = None

    for rotation, rect in candidates:
        if not rect_inside_room(rect, room):
            continue
        if zones.door is not None and rects_overlap(rect, zones.door):
            continue
        if any(rects_overlap(rect, other) for other in rects):
            continue

        quality = _item_quality(
            rect,
            rects,
            room,
            zones,
            wall_anchored=request.is_wall_anchored,
            wall_order=wall_order,
        )
        if best is None or quality > best[0] + EPS_CM:
            best = (quality, rotation, rect)

    if best is None:
        return None

    _, rotation, rect = best
    return make_footprint(
        item_id=request.item.item_id,
        label=request.item.name,
        left_cm=rect.left_cm,
        bottom_cm=rect.bottom_cm,
        width_cm=request.item.width_cm,
        depth_cm=request.item.depth_cm,
        rotation_degrees=rotation,
    )


def _layout_components(
    room: RoomInput,
    placements: list[PlacedFurniture],
    zones: _Zones,
) -> tuple[ScoreComponent, ...]:
    """The six weighted criteria of one layout."""

    rects = [placement.footprint.rect for placement in placements]
    floor_area = room.width_cm * room.length_cm

    inside = sum(1 for rect in rects if rect_inside_room(rect, room))
    boundary_fit = inside / len(rects) if rects else 1.0

    door_access = 1.0
    if zones.door_access is not None:
        blocked = sum(
            rect_intersection_area(rect, zones.door_access) for rect in rects
        )
        door_access = _clip01(
            1.0 - blocked / (zones.door_access.width_cm * zones.door_access.depth_cm)
        )

    window_clearance = 1.0
    if zones.window is not None:
        obstructed = sum(
            rect_intersection_area(rect, zones.window) for rect in rects
        )
        window_clearance = _clip01(
            1.0 - obstructed / (zones.window.width_cm * zones.window.depth_cm)
        )

    overlap_free = 1.0
    if len(rects) > 1:
        shared = sum(
            rect_intersection_area(rects[first], rects[second])
            for first in range(len(rects))
            for second in range(first + 1, len(rects))
        )
        placed_area = sum(rect.width_cm * rect.depth_cm for rect in rects)
        overlap_free = _clip01(1.0 - shared / placed_area) if placed_area else 1.0

    placed_area = sum(rect.width_cm * rect.depth_cm for rect in rects)
    free_ratio = 1.0 - placed_area / floor_area if floor_area else 0.0
    circulation = _clip01(
        (free_ratio - CIRCULATION_FLOOR_RATIO)
        / (CIRCULATION_COMFORT_RATIO - CIRCULATION_FLOOR_RATIO)
    )

    quality_scores = [
        _neutral_quality(
            placement.footprint.rect,
            [
                other.footprint.rect
                for other in placements
                if other is not placement
            ],
            room,
            zones,
            wall_anchored=placement.wall_anchored,
        )
        for placement in placements
    ]
    placement_quality = (
        round(sum(quality_scores) / len(quality_scores), 6)
        if quality_scores
        else 0.0
    )

    values = {
        "boundary_fit": boundary_fit,
        "door_access": door_access,
        "window_clearance": window_clearance,
        "overlap_free": overlap_free,
        "circulation": circulation,
        "placement_quality": placement_quality,
    }
    return tuple(
        ScoreComponent(name=name, weight=weight, value=round(values[name], 6))
        for name, weight in LAYOUT_WEIGHTS.items()
    )


def _build_layout(
    room: RoomInput,
    requests: tuple[_Request, ...],
    unresolved: tuple[UnplacedFurniture, ...],
    strategy: PlacementStrategy,
    zones: _Zones,
) -> LayoutCandidate:
    """Greedy placement pass for one strategy.

    Items that carry a wall intent are placed before the rest, still largest
    first within each group. Intent is a constraint on a specific piece, so the
    piece has to claim its wall while the wall is still free — otherwise a rug
    or a wardrobe placed earlier can occupy the very spot the concept asked for.
    Without that ordering the restriction is technically applied but
    meaningless: the bed ends up in the corner of its preferred wall, flush
    against two walls at once, rather than along it.

    Items with no intent keep the original area ordering exactly, so a basket
    with no preferences produces the layout it always did.
    """

    ordered = sorted(
        requests,
        key=lambda request: (
            0 if request.has_wall_intent else 1,
            -request.area_cm2,
            request.item.item_id,
        ),
    )
    placed: list[PlacedFurniture] = []
    unplaced: list[UnplacedFurniture] = list(unresolved)
    floor_area = room.width_cm * room.length_cm

    for request in ordered:
        missed = 0
        for _copy in range(request.quantity):
            footprint = _place_request(
                room, request, placed, zones, strategy.wall_order
            )
            if footprint is None:
                missed += 1
                continue
            placed.append(
                PlacedFurniture(
                    request_index=request.index,
                    footprint=footprint,
                    wall_anchored=request.is_wall_anchored,
                )
            )

        if missed:
            placed_area = sum(
                entry.footprint.rect.width_cm * entry.footprint.rect.depth_cm
                for entry in placed
            )
            free_area_sqm = max(0.0, floor_area - placed_area) / 10_000.0
            unplaced.append(
                UnplacedFurniture(
                    item_id=request.item.item_id,
                    label=request.item.name,
                    count=missed,
                    reason_code=_unplaced_code(request),
                    reason=_unplaced_reason(
                        request, room, len(placed), free_area_sqm
                    ),
                )
            )

    ordered_placements = tuple(
        sorted(placed, key=lambda entry: entry.request_index)
    )
    return LayoutCandidate(
        strategy=strategy.name,
        placements=ordered_placements,
        unplaced=tuple(unplaced),
        components=_layout_components(room, list(ordered_placements), zones),
    )


# --------------------------------------------------------------------------- #
# Public entry points
# --------------------------------------------------------------------------- #


def generate_layouts(
    room: RoomInput,
    recommendations: Sequence[FurnitureRecommendation],
    catalog: Sequence[FurnitureItem],
    *,
    door_clearance_cm: float = DEFAULT_DOOR_CLEARANCE_CM,
    window_clearance_cm: float = DEFAULT_WINDOW_CLEARANCE_CM,
) -> tuple[LayoutCandidate, ...]:
    """Every candidate layout, best first.

    Ordering is completeness, then score, then strategy order, so the same
    inputs always return the same candidates in the same order.
    """

    requests, unresolved = _resolve(tuple(recommendations), tuple(catalog))
    zones = _zones(room, door_clearance_cm, window_clearance_cm)

    attempts = [
        _build_layout(room, requests, unresolved, strategy, zones)
        for strategy in STRATEGIES
    ]
    ranked = sorted(
        enumerate(attempts),
        key=lambda pair: (-pair[1].placed_count, -pair[1].score, pair[0]),
    )
    return tuple(candidate for _index, candidate in ranked)


def place_furniture(
    room: RoomInput,
    recommendations: Sequence[FurnitureRecommendation],
    catalog: Sequence[FurnitureItem],
    *,
    door_clearance_cm: float = DEFAULT_DOOR_CLEARANCE_CM,
    window_clearance_cm: float = DEFAULT_WINDOW_CLEARANCE_CM,
) -> PlacementResult:
    """Place every recommended item, then validate the chosen layout.

    A partially placed layout is reported as ``PARTIAL``, never as success. A
    layout that the spatial engine rejects, or one that placed nothing at all,
    is reported as ``FAILED`` and carries no usable candidate.
    """

    candidates = generate_layouts(
        room,
        recommendations,
        catalog,
        door_clearance_cm=door_clearance_cm,
        window_clearance_cm=window_clearance_cm,
    )
    best = candidates[0]

    if best.requested_count == 0:
        return PlacementResult(
            status=PlacementStatus.FAILED,
            candidates=candidates,
            best=best,
            notes=(
                PlacementIssue(
                    severity="error",
                    code="no_recommendations",
                    message=(
                        "No furniture was recommended, so there is nothing to "
                        "place."
                    ),
                ),
            ),
        )

    if best.placed_count == 0:
        return PlacementResult(
            status=PlacementStatus.FAILED,
            candidates=candidates,
            best=best,
            notes=(
                PlacementIssue(
                    severity="error",
                    code="no_valid_layout",
                    message=(
                        "No recommended item could be placed in this room: "
                        + " ".join(item.reason for item in best.unplaced)
                    ),
                ),
            ),
        )

    report = validate_placement(
        room,
        best.footprints,
        door_clearance_cm=door_clearance_cm,
        window_clearance_cm=window_clearance_cm,
    )
    validation = to_spatial_validation(report)
    findings = tuple(placement_findings(report))

    if report.errors:
        return PlacementResult(
            status=PlacementStatus.FAILED,
            candidates=candidates,
            best=best,
            report=report,
            validation=validation,
            findings=findings,
            notes=(
                PlacementIssue(
                    severity="error",
                    code="layout_rejected",
                    message=(
                        "The best candidate layout was rejected by the spatial "
                        "engine and is not offered as a result."
                    ),
                ),
            ),
        )

    status = (
        PlacementStatus.COMPLETE
        if best.is_complete
        else PlacementStatus.PARTIAL
    )
    notes: tuple[PlacementIssue, ...] = ()
    if status is PlacementStatus.PARTIAL:
        notes = (
            PlacementIssue(
                severity="warning",
                code="partial_placement",
                message=(
                    f"{best.placed_count} of {best.requested_count} items were "
                    "placed; the rest could not be positioned."
                ),
            ),
        )

    return PlacementResult(
        status=status,
        candidates=candidates,
        best=best,
        candidate=best,
        report=report,
        validation=validation,
        findings=findings,
        notes=notes,
    )


def apply_placements(
    recommendations: Sequence[FurnitureRecommendation],
    result: PlacementResult,
) -> tuple[FurnitureRecommendation, ...]:
    """Return the recommendations with the engine's coordinates written in.

    ``FurnitureRecommendation`` is the only model that persists a position, and
    the advisor always leaves those fields ``None``. This is therefore the one
    place a coordinate is written, so the stored project carries exactly the
    geometry the spatial engine validated.

    Every placed copy is written to ``positions``, in the order the engine
    placed them, so ``quantity > 1`` survives write-back and a partial layout
    stores exactly the copies that exist. ``position_x_cm``/``position_y_cm``
    and ``rotation_degrees`` mirror the first entry, which is what the Phase 3
    validator reads; ``core.spatial_engine.build_footprints`` uses ``positions``
    when it is present, so the two agree instead of collapsing the copies.

    A copy that was not placed contributes nothing: its coordinate is never
    invented, and an item placed zero times keeps ``None`` coordinates and an
    empty ``positions`` list. Its ``quantity`` is untouched, so the budget is
    unaffected.
    """

    if result.candidate is None:
        return tuple(recommendations)

    by_request: dict[int, list[FurnitureFootprint]] = {}
    for placement in result.candidate.placements:
        by_request.setdefault(placement.request_index, []).append(
            placement.footprint
        )

    updated: list[FurnitureRecommendation] = []
    for index, recommendation in enumerate(recommendations):
        footprints = by_request.get(index, [])
        if not footprints:
            updated.append(recommendation)
            continue
        positions = [
            FurniturePosition(
                position_x_cm=footprint.left_cm,
                position_y_cm=footprint.bottom_cm,
                rotation_degrees=normalize_rotation(footprint.rotation_degrees),
            )
            for footprint in footprints
        ]
        first = positions[0]
        updated.append(
            recommendation.model_copy(
                update={
                    "position_x_cm": first.position_x_cm,
                    "position_y_cm": first.position_y_cm,
                    "rotation_degrees": first.rotation_degrees,
                    "positions": positions,
                }
            )
        )
    return tuple(updated)


def walls_touched(
    rect: Rect, room: RoomInput
) -> tuple[Wall, ...]:
    """Every wall a footprint lies flush against, in the declared wall order.

    This is the single definition of "touching a wall" used both while scoring
    candidates and when judging the finished layout. Two definitions would drift
    and the report would then disagree with the engine that produced the plan.

    A corner footprint touches two walls at once; both are returned. A caller
    that wants to decide which wall a piece reads as "belonging to" must compare
    the contact lengths, which is why :func:`contact_length_cm` exists.
    """

    return tuple(
        wall
        for wall, flush in (
            (Wall.WEST, rect.left_cm <= EPS_CM),
            (Wall.SOUTH, rect.bottom_cm <= EPS_CM),
            (Wall.EAST, abs(rect.right_cm - room.width_cm) <= EPS_CM),
            (Wall.NORTH, abs(rect.top_cm - room.length_cm) <= EPS_CM),
        )
        if flush
    )


def contact_length_cm(rect: Rect, room: RoomInput, wall: Wall) -> float:
    """How much of a footprint's side lies along one wall, in centimeters.

    Zero when the footprint is not flush against that wall. This is what
    separates "pushed against the west wall" from "parked in the corner, which
    happens to include the west wall": in a corner the piece touches two walls,
    and only the longer contact is the arrangement a reader would name.
    """

    if wall not in walls_touched(rect, room):
        return 0.0
    if wall in (Wall.WEST, Wall.EAST):
        return rect.depth_cm
    return rect.width_cm


def _display_label(item_id: str) -> str:
    """A readable stand-in for a catalogue item the caller did not supply.

    Only used for an unplaced row when no catalogue was passed or the identifier
    is unknown to it. It is deliberately mechanical: inventing a prettier name
    for an item that has no catalogue entry would put a display name in the
    report that no data source supports.
    """

    return item_id.replace("_", " ").capitalize()


def _dominant_wall(
    rect: Rect, room: RoomInput, requested: Wall | None = None
) -> Wall | None:
    """The wall a footprint most convincingly belongs to, or ``None``.

    ``requested`` resolves the one case geometry cannot: a piece pushed into a
    corner has two equally long contacts, and nothing in the rectangle says
    which wall the design meant. When the requested wall is one of the longest
    contacts it wins the tie, because that is the reading the concept asked for.
    Every other tie keeps the fixed order ``walls_touched`` yields, so the
    answer stays deterministic for callers that pass no request.
    """

    touching = walls_touched(rect, room)
    if not touching:
        return None
    contact_cm = {wall: contact_length_cm(rect, room, wall) for wall in touching}
    longest_cm = max(contact_cm.values())
    if requested in touching and contact_cm[requested] == longest_cm:
        return requested
    return max(touching, key=lambda wall: contact_cm[wall])


def check_intent(
    room: RoomInput,
    recommendations: Sequence[FurnitureRecommendation],
    placements: Sequence[PlacedFootprint] | None = None,
    *,
    catalog: Sequence[FurnitureItem] | None = None,
) -> ConceptCompatibility:
    """Judge the requested walls against the coordinates actually produced.

    Deterministic, and deliberately separate from the layout score: the score
    measures geometry, this measures whether the geometry kept the design's
    promise. An item is satisfied when the placed footprint lies along the
    requested wall as its dominant contact, so a corner that merely grazes the
    wall does not count as having been pushed against it. Where two walls are
    equally long contacts the requested wall wins, because the rectangle alone
    cannot say which of the two the design meant.

    An item that was requested with a wall but not placed is reported as
    ``satisfied=None`` with a note, never as satisfied.

    ``catalog`` supplies the display name for an item that was not placed: the
    placed branch reads it from the footprint, and a row that reports a failure
    must not be the one place a reader sees a raw ``bedside_table``. Without it
    the identifier is humanised, which is close but not authoritative.
    """

    wanted = [item for item in recommendations if item.preferred_wall is not None]
    if not wanted:
        return ConceptCompatibility(
            checks=[],
            note=(
                "No layout intent was recorded for this project, so concept "
                "compatibility was not assessed."
            ),
        )

    by_id: dict[str, list[PlacedFootprint]] = {}
    for footprint in placements or ():
        by_id.setdefault(footprint.item_id, []).append(footprint)

    # A placed row takes its label from the footprint, which the engine already
    # filled from the catalog. An unplaced row has no footprint, so the catalog
    # is the only authoritative source; the humanised identifier is a fallback
    # for callers that did not pass one.
    catalog_names = {
        entry.item_id: entry.name for entry in catalog or ()
    }

    checks: list[IntentCheck] = []
    for item in wanted:
        assert item.preferred_wall is not None  # filtered above
        placed = by_id.get(item.item_id, [])
        if not placed:
            checks.append(
                IntentCheck(
                    item_id=item.item_id,
                    label=catalog_names.get(
                        item.item_id, _display_label(item.item_id)
                    ),
                    preferred_wall=item.preferred_wall,
                    priority=item.wall_priority,
                    satisfied=None,
                    note=(
                        "Not placed, so the preferred wall could not be "
                        "assessed."
                    ),
                )
            )
            continue

        rects = [
            Rect(
                footprint.left_cm,
                footprint.bottom_cm,
                footprint.width_cm,
                footprint.depth_cm,
            )
            for footprint in placed
        ]
        satisfied = all(
            _dominant_wall(rect, room, item.preferred_wall)
            is item.preferred_wall
            for rect in rects
        )
        # ``walls_touched`` already yields in a fixed order, so de-duplicating in
        # place keeps the stored list deterministic without a second ordering.
        actual = list(
            dict.fromkeys(
                wall
                for rect in rects
                for wall in walls_touched(rect, room)
            )
        )
        note = ""
        if not satisfied:
            # No requested wall is passed here: the verdict already established
            # that it is not the longest contact, so naming the strict winner is
            # the honest description of where the piece actually went.
            dominant = _dominant_wall(rects[0], room)
            where = dominant.value if dominant is not None else "free-standing"
            note = (
                f"Requested {item.preferred_wall.value}, placed "
                f"{where} instead."
            )
        checks.append(
            IntentCheck(
                item_id=item.item_id,
                label=placed[0].label,
                preferred_wall=item.preferred_wall,
                priority=item.wall_priority,
                satisfied=satisfied,
                actual_walls=list(actual),
                note=note,
            )
        )

    return ConceptCompatibility(
        checks=checks,
        note=(
            f"{sum(1 for c in checks if c.satisfied is True)} of {len(checks)} "
            "requested walls were met by the calculated plan."
        ),
    )


__all__ = [
    "ANCHOR_STEP_CM",
    "CIRCULATION_COMFORT_RATIO",
    "CIRCULATION_FLOOR_RATIO",
    "DOOR_APPROACH_CM",
    "DOOR_COMFORT_CM",
    "FREE_STANDING_WEIGHTS",
    "GRID_STEP_CM",
    "LAYOUT_WEIGHTS",
    "LayoutCandidate",
    "PlacedFurniture",
    "PlacementResult",
    "PlacementStatus",
    "PlacementStrategy",
    "SPACING_COMFORT_CM",
    "STRATEGIES",
    "ScoreComponent",
    "UnplacedFurniture",
    "WALL_ANCHORED_CATEGORIES",
    "WALL_ANCHORED_WEIGHTS",
    "WALL_ANCHOR_RANGE_CM",
    "WallPreference",
    "apply_placements",
    "check_intent",
    "contact_length_cm",
    "generate_layouts",
    "place_furniture",
    "rotation_candidates",
    "walls_touched",
]
