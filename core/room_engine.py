"""Deterministic room geometry.

Pure functions over primitive centimeter values, plus thin adapters for the
Pydantic room model. No Streamlit, no AI, no file I/O.

Coordinate system
-----------------
The origin is the south-west (bottom-left) corner.

* ``width_cm`` extends along +x (west to east),
* ``length_cm`` extends along +y (south to north).

Opening offsets follow the same convention as the data model: south and north
walls are measured from the west end, west and east walls from the south end.

Every function here is reproducible from its arguments alone.
"""

from __future__ import annotations

from dataclasses import dataclass

from models.schemas import MAX_CEILING_HEIGHT_CM, MAX_ROOM_DIMENSION_CM
from models.schemas import MIN_CEILING_HEIGHT_CM, MIN_OPENING_WIDTH_CM
from models.schemas import MIN_ROOM_DIMENSION_CM, OpeningInput, RoomInput, Wall

#: Tolerance for floating-point comparisons of centimeter values.
EPS_CM: float = 1e-6

#: Full circle in degrees, used to normalise rotations.
_FULL_TURN = 360


@dataclass(frozen=True)
class Point:
    """A point in room coordinates, in centimeters."""

    x_cm: float
    y_cm: float


@dataclass(frozen=True)
class Segment:
    """A straight segment on a wall, in room coordinates."""

    start: Point
    end: Point

    @property
    def length_cm(self) -> float:
        return ((self.end.x_cm - self.start.x_cm) ** 2 + (
            self.end.y_cm - self.start.y_cm
        ) ** 2) ** 0.5


@dataclass(frozen=True)
class RoomMetrics:
    """Derived dimensions of a rectangular room."""

    width_cm: float
    length_cm: float
    area_sqm: float
    perimeter_cm: float
    wall_lengths_cm: dict[Wall, float]


@dataclass(frozen=True)
class OpeningPlacement:
    """Where an opening sits, both along its wall and in room coordinates."""

    label: str
    wall: Wall
    offset_cm: float
    width_cm: float
    along_wall_start_cm: float
    along_wall_end_cm: float
    segment: Segment
    inside_room: bool


# --------------------------------------------------------------------------- #
# Primitive validation
# --------------------------------------------------------------------------- #


def validate_dimensions(
    width_cm: float,
    length_cm: float,
    *,
    ceiling_height_cm: float | None = None,
) -> list[str]:
    """Return dimension problems; an empty list means the room is acceptable.

    The function accepts raw numbers so that zero and negative values can be
    reported as data errors instead of raising during model construction.
    """

    problems: list[str] = []

    for label, value, minimum, maximum in (
        ("width", width_cm, MIN_ROOM_DIMENSION_CM, MAX_ROOM_DIMENSION_CM),
        ("length", length_cm, MIN_ROOM_DIMENSION_CM, MAX_ROOM_DIMENSION_CM),
    ):
        if value is None:
            problems.append(f"The room {label} is missing.")
        elif not isinstance(value, (int, float)) or isinstance(value, bool):
            problems.append(f"The room {label} must be a number.")
        elif value != value:  # NaN
            problems.append(f"The room {label} is not a valid number.")
        elif value <= 0:
            problems.append(f"The room {label} must be greater than zero.")
        elif value < minimum:
            problems.append(
                f"The room {label} of {value:g} cm is below the {minimum:g} cm minimum."
            )
        elif value > maximum:
            problems.append(
                f"The room {label} of {value:g} cm exceeds the {maximum:g} cm maximum."
            )

    if ceiling_height_cm is not None:
        if not isinstance(ceiling_height_cm, (int, float)) or isinstance(
            ceiling_height_cm, bool
        ):
            problems.append("The ceiling height must be a number.")
        elif ceiling_height_cm <= 0:
            problems.append("The ceiling height must be greater than zero.")
        elif not (
            MIN_CEILING_HEIGHT_CM <= ceiling_height_cm <= MAX_CEILING_HEIGHT_CM
        ):
            problems.append(
                f"The ceiling height of {ceiling_height_cm:g} cm is outside the "
                f"{MIN_CEILING_HEIGHT_CM:g}-{MAX_CEILING_HEIGHT_CM:g} cm range."
            )

    return problems


def validate_opening(
    offset_cm: float,
    width_cm: float,
    wall_span_cm: float,
    *,
    label: str = "opening",
) -> list[str]:
    """Check that an opening fits entirely on its wall."""

    problems: list[str] = []

    if not isinstance(offset_cm, (int, float)) or isinstance(offset_cm, bool):
        problems.append(f"The {label} offset must be a number.")
    elif offset_cm < -EPS_CM:
        problems.append(f"The {label} offset cannot be negative.")

    if not isinstance(width_cm, (int, float)) or isinstance(width_cm, bool):
        problems.append(f"The {label} width must be a number.")
    elif width_cm <= 0:
        problems.append(f"The {label} width must be greater than zero.")
    elif width_cm < MIN_OPENING_WIDTH_CM:
        problems.append(
            f"The {label} width of {width_cm:g} cm is below the "
            f"{MIN_OPENING_WIDTH_CM:g} cm minimum."
        )

    if problems:
        return problems

    end_cm = offset_cm + width_cm
    if end_cm > wall_span_cm + EPS_CM:
        problems.append(
            f"The {label} does not fit on the wall: offset {offset_cm:g} cm plus "
            f"width {width_cm:g} cm exceeds the {wall_span_cm:g} cm wall span."
        )

    return problems


# --------------------------------------------------------------------------- #
# Room metrics
# --------------------------------------------------------------------------- #


def area_sqm(width_cm: float, length_cm: float) -> float:
    """Floor area in square meters.

    Raises ``ValueError`` when either dimension is not positive, because a
    non-positive rectangle has no meaningful area.
    """

    if width_cm <= 0 or length_cm <= 0:
        raise ValueError("Room dimensions must be greater than zero.")
    return (width_cm * length_cm) / 10_000.0


def perimeter_cm(width_cm: float, length_cm: float) -> float:
    """Wall perimeter in centimeters."""

    if width_cm <= 0 or length_cm <= 0:
        raise ValueError("Room dimensions must be greater than zero.")
    return 2.0 * (width_cm + length_cm)


def wall_length_cm(width_cm: float, length_cm: float, wall: Wall) -> float:
    """Length of a single wall.

    North and south walls span the room width; east and west walls span the
    room length.
    """

    if wall in (Wall.NORTH, Wall.SOUTH):
        return width_cm
    return length_cm


def wall_lengths_cm(width_cm: float, length_cm: float) -> dict[Wall, float]:
    """Lengths of all four walls."""

    return {
        wall: wall_length_cm(width_cm, length_cm, wall) for wall in Wall
    }


def room_metrics(room: RoomInput) -> RoomMetrics:
    """Adapter: derive metrics from the validated room model."""

    return RoomMetrics(
        width_cm=room.width_cm,
        length_cm=room.length_cm,
        area_sqm=area_sqm(room.width_cm, room.length_cm),
        perimeter_cm=perimeter_cm(room.width_cm, room.length_cm),
        wall_lengths_cm=wall_lengths_cm(room.width_cm, room.length_cm),
    )


# --------------------------------------------------------------------------- #
# Opening placement
# --------------------------------------------------------------------------- #


def opening_interval_cm(offset_cm: float, width_cm: float) -> tuple[float, float]:
    """The ``(start, end)`` interval an opening occupies along its wall."""

    return (offset_cm, offset_cm + width_cm)


def opening_segment(
    width_cm: float,
    length_cm: float,
    wall: Wall,
    offset_cm: float,
    opening_width_cm: float,
) -> Segment:
    """Project an opening onto the room boundary.

    The segment lies on the wall itself, so a door on the south wall is drawn at
    ``y = 0`` from ``x = offset`` to ``x = offset + width``.
    """

    start_cm = offset_cm
    end_cm = offset_cm + opening_width_cm

    if wall is Wall.SOUTH:
        return Segment(Point(start_cm, 0.0), Point(end_cm, 0.0))
    if wall is Wall.NORTH:
        return Segment(
            Point(start_cm, length_cm), Point(end_cm, length_cm)
        )
    if wall is Wall.WEST:
        return Segment(Point(0.0, start_cm), Point(0.0, end_cm))
    return Segment(Point(width_cm, start_cm), Point(width_cm, end_cm))


def opening_placement(
    room: RoomInput, opening: OpeningInput, *, label: str
) -> OpeningPlacement:
    """Describe one opening relative to its wall."""

    span_cm = wall_length_cm(room.width_cm, room.length_cm, opening.wall)
    start_cm, end_cm = opening_interval_cm(opening.offset_cm, opening.width_cm)
    inside = start_cm >= -EPS_CM and end_cm <= span_cm + EPS_CM

    return OpeningPlacement(
        label=label,
        wall=opening.wall,
        offset_cm=opening.offset_cm,
        width_cm=opening.width_cm,
        along_wall_start_cm=start_cm,
        along_wall_end_cm=end_cm,
        segment=opening_segment(
            room.width_cm,
            room.length_cm,
            opening.wall,
            opening.offset_cm,
            opening.width_cm,
        ),
        inside_room=inside,
    )


def validate_room(room: RoomInput) -> list[str]:
    """Full geometric validation of a room and its openings.

    The Pydantic model already rejects most invalid input, but this function is
    the engine's own gate: it does not assume the caller constructed a valid
    model and never trusts a model that was built with ``model_construct``.
    """

    problems = validate_dimensions(
        room.width_cm, room.length_cm, ceiling_height_cm=room.ceiling_height_cm
    )

    for label, opening in (("door", room.door), ("window", room.window)):
        span_cm = wall_length_cm(room.width_cm, room.length_cm, opening.wall)
        problems.extend(
            validate_opening(
                opening.offset_cm,
                opening.width_cm,
                span_cm,
                label=label,
            )
        )

    return problems


def openings_overlap(room: RoomInput) -> bool:
    """True when the door and window occupy the same stretch of the same wall.

    Two openings on different walls can never collide. On a shared wall the
    intervals must be disjoint; exactly touching intervals are allowed.
    """

    if room.door.wall is not room.window.wall:
        return False

    door_start, door_end = opening_interval_cm(room.door.offset_cm, room.door.width_cm)
    window_start, window_end = opening_interval_cm(
        room.window.offset_cm, room.window.width_cm
    )

    return door_start < window_end - EPS_CM and window_start < door_end - EPS_CM


def opening_conflict_messages(room: RoomInput) -> list[str]:
    """Human-readable problems shared by the room's openings."""

    messages: list[str] = []
    if openings_overlap(room):
        messages.append(
            "The door and the window overlap on the same wall; they must occupy "
            "separate parts of the wall."
        )
    return messages


def normalize_rotation(degrees: float) -> int:
    """Normalise an angle to one of the four supported orientations."""

    normalized = int(round(degrees)) % _FULL_TURN
    if normalized % 90 != 0:
        raise ValueError(
            f"Furniture rotation must be a multiple of 90 degrees, got {degrees!r}."
        )
    return normalized


__all__ = [
    "EPS_CM",
    "OpeningPlacement",
    "Point",
    "RoomMetrics",
    "Segment",
    "area_sqm",
    "normalize_rotation",
    "opening_conflict_messages",
    "opening_interval_cm",
    "opening_placement",
    "opening_segment",
    "openings_overlap",
    "perimeter_cm",
    "room_metrics",
    "validate_dimensions",
    "validate_opening",
    "validate_room",
    "wall_length_cm",
    "wall_lengths_cm",
]
