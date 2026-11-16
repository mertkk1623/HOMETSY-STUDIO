"""Illustrative room drawings.

Two renderers live here and they answer different questions.

``room_diagram_svg`` is the small orientation sketch on the room form: it draws
the rectangle the user described and marks which wall each opening sits on. It
checks nothing and is not to scale in any physical sense
(``DESIGN_SYSTEM.md`` §6.3).

``placement_plan_svg`` is the design plan (``DESIGN_SYSTEM.md`` §6.7 and §10): a
scaled drawing of the validated layout, with the room boundary, the door and
window, every placed footprint with its label and dimensions, and a legend. It
draws only what ``models.schemas.PlacementOutcome`` holds, which is only what the
placement and spatial engines accepted — so a rejected layout has nothing to
draw, and a partial layout draws only the copies that were placed. No coordinate
in it is computed here: the footprint extents come from the engine already
rotated.

Neither renderer is a validator. ``core.spatial_engine`` decides whether a layout
is acceptable and its verdict is what the screen reports; these functions only
draw the result.
"""

from __future__ import annotations

from typing import Sequence

from models.schemas import PlacedFootprint, Wall

from ui import theme

#: Drawing area of the room-form viewBox, in user units.
_BOX_W = 260.0
_BOX_H = 190.0
_PAD = 16.0
_DOOR_STROKE = 6.0
_WINDOW_STROKE = 4.0

#: Which coordinate of the room's north/south walls an opening is measured along.
_HORIZONTAL_WALLS = (Wall.NORTH, Wall.SOUTH)


def _scaled(
    width_cm: float, length_cm: float
) -> tuple[float, float, float]:
    """Fit the room into the box and return ``(w, h, scale)`` in user units."""

    safe_width = max(float(width_cm or 0.0), 1.0)
    safe_length = max(float(length_cm or 0.0), 1.0)
    usable_w = _BOX_W - 2 * _PAD
    usable_h = _BOX_H - 2 * _PAD
    scale = min(usable_w / safe_width, usable_h / safe_length)
    return safe_width * scale, safe_length * scale, scale


def _opening(
    wall: Wall,
    offset_cm: float,
    width_cm: float,
    *,
    room_w: float,
    room_h: float,
    scale: float,
    x0: float,
    y0: float,
) -> tuple[float, float, float, float]:
    """Coordinates of an opening's line segment, clipped to the room box."""

    start = offset_cm * scale
    end = (offset_cm + width_cm) * scale
    start = max(0.0, min(start, room_w))
    end = max(0.0, min(end, room_w if wall in _HORIZONTAL_WALLS else room_h))

    if wall is Wall.SOUTH:
        return x0 + start, y0, x0 + end, y0
    if wall is Wall.NORTH:
        return x0 + start, y0 + room_h, x0 + end, y0 + room_h
    if wall is Wall.WEST:
        return x0, y0 + start, x0, y0 + end
    return x0 + room_w, y0 + start, x0 + room_w, y0 + end


def _wall_name(wall: Wall) -> str:
    """The wall as a word, accepting either the enum or its value."""

    return getattr(wall, "value", str(wall))


def _spoken_opening(
    label: str, wall: Wall, offset_cm: float, width_cm: float
) -> str:
    """One opening as a sentence a screen reader can read out.

    The drawing shows the door and window as coloured strokes; colour alone is
    not information, so the same facts have to exist as words.
    """

    return (
        f"{label} on the {_wall_name(wall)} wall, {float(offset_cm):g} cm along "
        f"that wall from its origin, {float(width_cm):g} cm wide"
    )


def _spoken_room(
    width_cm: float,
    length_cm: float,
    door_wall: Wall,
    door_offset_cm: float,
    door_width_cm: float,
    window_wall: Wall,
    window_offset_cm: float,
    window_width_cm: float,
) -> str:
    """The room and both openings as one description, in words not geometry."""

    area = (float(width_cm) * float(length_cm)) / 10_000.0
    return (
        f"A rectangular room {float(width_cm):g} cm wide and "
        f"{float(length_cm):g} cm long, {area:.2f} square metres. "
        + _spoken_opening("Door", door_wall, door_offset_cm, door_width_cm)
        + ". "
        + _spoken_opening(
            "Window", window_wall, window_offset_cm, window_width_cm
        )
        + ". South is at the bottom of the drawing. The sketch is illustrative "
        "and not to scale."
    )


def room_diagram_svg(
    *,
    width_cm: float,
    length_cm: float,
    door_wall: Wall,
    door_offset_cm: float,
    door_width_cm: float,
    window_wall: Wall,
    window_offset_cm: float,
    window_width_cm: float,
) -> str:
    """Render the diagram as a self-contained SVG string."""

    room_w, room_h, scale = _scaled(width_cm, length_cm)
    x0 = (_BOX_W - room_w) / 2
    y0 = (_BOX_H - room_h) / 2

    door = _opening(
        door_wall,
        door_offset_cm,
        door_width_cm,
        room_w=room_w,
        room_h=room_h,
        scale=scale,
        x0=x0,
        y0=y0,
    )
    window = _opening(
        window_wall,
        window_offset_cm,
        window_width_cm,
        room_w=room_w,
        room_h=room_h,
        scale=scale,
        x0=x0,
        y0=y0,
    )

    view_y = _BOX_H - y0 - room_h  # flip so south sits at the bottom
    door_y1, door_y2 = _BOX_H - door[1], _BOX_H - door[3]
    window_y1, window_y2 = _BOX_H - window[1], _BOX_H - window[3]

    spoken = _spoken_room(
        width_cm,
        length_cm,
        door_wall,
        door_offset_cm,
        door_width_cm,
        window_wall,
        window_offset_cm,
        window_width_cm,
    )

    # ``<title>`` and ``<desc>`` are what a screen reader actually announces; the
    # ids let the SVG point at them so the text is not read twice. The visible
    # caption stays inside the drawing, so the picture is still self-describing
    # when the image is copied out of the page.
    return (
        f'<svg viewBox="0 0 {_BOX_W:g} {_BOX_H:g}" role="img" '
        'aria-labelledby="hm-room-sketch-title" '
        'aria-describedby="hm-room-sketch-desc" '
        'style="width:100%;height:auto;display:block;">'
        f'<title id="hm-room-sketch-title">Illustration of the room: '
        f"{theme.escape(f'{float(width_cm):g} by {float(length_cm):g} centimetre room')}"
        "</title>"
        f'<desc id="hm-room-sketch-desc">{theme.escape(spoken)}</desc>'
        f'<rect x="{x0:.1f}" y="{view_y:.1f}" width="{room_w:.1f}" '
        f'height="{room_h:.1f}" fill="{theme.COLORS["surface_muted"]}" '
        f'stroke="{theme.COLORS["primary_dark"]}" stroke-width="1.5"/>'
        f'<line x1="{door[0]:.1f}" y1="{door_y1:.1f}" x2="{door[2]:.1f}" '
        f'y2="{door_y2:.1f}" stroke="{theme.COLORS["primary"]}" '
        f'stroke-width="{_DOOR_STROKE:g}" stroke-linecap="butt"/>'
        f'<line x1="{window[0]:.1f}" y1="{window_y1:.1f}" x2="{window[2]:.1f}" '
        f'y2="{window_y2:.1f}" stroke="{theme.COLORS["warning"]}" '
        f'stroke-width="{_WINDOW_STROKE:g}"/>'
        f'<text x="{_BOX_W / 2:.1f}" y="{_BOX_H - 2:.1f}" text-anchor="middle" '
        f'font-family="Inter, Arial, sans-serif" font-size="9" '
        f'fill="{theme.COLORS["text_secondary"]}">South &middot; entrance side'
        "</text>"
        "</svg>"
    )


def legend() -> str:
    """The key for the two opening colours, stated in words as well.

    The swatch and its label are one inline-flex item, and the plain text space
    between the two items is a real text node: a flex parent would discard it,
    which made the two labels read as a single word ("DoorWindow") to a screen
    reader and in extracted text.
    """

    def item(colour: str, label: str, *, first: bool) -> str:
        margin = "" if first else "margin-left:18px;"
        return (
            f'<span style="display:inline-flex;align-items:center;'
            f'gap:6px;{margin}">'
            f'<span aria-hidden="true" style="display:inline-block;width:16px;'
            f'height:4px;background:{colour};"></span>'
            f"{label}</span>"
        )

    return (
        '<p class="hm-field-note">'
        + item(theme.COLORS["primary"], "Door", first=True)
        + " "
        + item(theme.COLORS["warning"], "Window", first=False)
        + "</p>"
        '<p class="hm-field-note">Offsets run from the west end on the north and '
        "south walls, and from the south end on the west and east walls. "
        "The drawing is illustrative and not to scale.</p>"
    )


# --------------------------------------------------------------------------- #
# The validated design plan
# --------------------------------------------------------------------------- #

#: Drawing area of the plan, in user units. Larger than the form diagram because
#: ``DESIGN_SYSTEM.md`` §6.7 asks for the plan to receive real visual space.
_PLAN_W = 640.0
_PLAN_H = 640.0

#: Space reserved around the room for the dimension annotations.
_PLAN_PAD = 54.0

#: The plan's label sizes, in user units, and the average character width used
#: to decide whether a label fits its block. Inter/Arial averages close to 0.5 em;
#: 0.56 is an upper bound, so a label is shortened slightly early rather than
#: allowed to overrun its rectangle.
_LABEL_FONT_SIZE = 9.0
_SIZE_FONT_SIZE = 8.0
_CHAR_WIDTH_EM = 0.56

#: Furniture fill. One colour for every block, per §10 ("consistent furniture
#: colors"); the label distinguishes the pieces, never the hue.
_FURNITURE_FILL = "#DDD8CB"
_FURNITURE_STROKE = "#7A7568"


def _plan_geometry(
    width_cm: float, length_cm: float
) -> tuple[float, float, float, float, float]:
    """Scale the room into the plan box, keeping the aspect ratio.

    Returns ``(room_w, room_h, scale, x0, y0)`` where ``x0``/``y0`` are the
    bottom-left corner of the room *in the unflipped coordinate system*, so
    every conversion below is one multiplication.
    """

    safe_width = max(float(width_cm or 0.0), 1.0)
    safe_length = max(float(length_cm or 0.0), 1.0)
    usable_w = _PLAN_W - 2 * _PLAN_PAD
    usable_h = _PLAN_H - 2 * _PLAN_PAD
    scale = min(usable_w / safe_width, usable_h / safe_length)
    room_w = safe_width * scale
    room_h = safe_length * scale
    return room_w, room_h, scale, (_PLAN_W - room_w) / 2, (_PLAN_H - room_h) / 2


def _wrap_label(name: str, available: float, max_lines: int) -> list[str]:
    """Split ``name`` into at most ``max_lines`` lines that each fit ``available``.

    Returns an empty list when the name cannot be split small enough, which the
    caller treats as "draw no label". Wrapping is preferred over truncation
    because a plan label is a name, not a sentence: "Floor" alone reads as a
    different piece of furniture, while "Floor / lamp" does not.
    """

    words = name.split()
    if not words:
        return []

    budget = available - 4.0
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if _estimated_text_width(candidate, _LABEL_FONT_SIZE) <= budget:
            current = candidate
            continue
        if current:
            lines.append(current)
            current = word
        else:
            # A single word wider than the block cannot be helped.
            return []
        if len(lines) == max_lines:
            return []

    if current:
        lines.append(current)
    if len(lines) > max_lines:
        return []
    # Every line must fit, including the last one.
    if any(_estimated_text_width(line, _LABEL_FONT_SIZE) > budget for line in lines):
        return []
    return lines


def _label_for(
    footprint: PlacedFootprint,
    *,
    available: float | None = None,
    max_lines: int = 1,
) -> str:
    """The block label that actually fits inside the block.

    A long name in a small block would overflow the rectangle and make the plan
    unreadable. The label is first tried whole; if it does not fit it is wrapped
    onto up to ``max_lines`` lines; if it still does not fit, no label is drawn.
    The full name is always in the list beneath the plan, so nothing is lost —
    but a misleading fragment is worse than an empty block, which is why the
    label is never cut down to its first word alone.

    ``available`` is the block's drawn width in user units. The decision is made
    from the estimated text width rather than from the physical dimensions,
    because a small room is drawn at a smaller scale and a name that fits at
    400 cm does not fit at 100 cm. The estimate is deliberately conservative:
    the plan is illustrative, and a label that is slightly too wide for its
    block reads as a mistake.
    """

    name = footprint.label.strip() or footprint.item_id

    if available is not None:
        budget = available - 4.0
        if _estimated_text_width(name, _LABEL_FONT_SIZE) <= budget:
            return name
        lines = _wrap_label(name, available, max_lines)
        # Joined with a space: the wrap is a drawing decision, so the label the
        # DOM exposes stays the readable name rather than a hyphenated fragment.
        return " ".join(lines)

    if footprint.width_cm < 60 or footprint.depth_cm < 40:
        return name.split()[0]
    return name


def _estimated_text_width(text: str, font_size: float) -> float:
    """A conservative width estimate for one line of SVG text, in user units."""

    return len(text) * font_size * _CHAR_WIDTH_EM


def furniture_block_svg(
    footprint: PlacedFootprint,
    *,
    room_w: float,
    room_h: float,
    scale: float,
    x0: float,
    y0: float,
) -> str:
    """One furniture block, its label and its size, in plan coordinates."""

    # Native SVG y grows downwards, the room's y grows north, so the top edge of
    # the block is the flipped bottom plus its depth.
    left = x0 + footprint.left_cm * scale
    top = _PLAN_H - (y0 + (footprint.bottom_cm + footprint.depth_cm) * scale)
    width = footprint.width_cm * scale
    height = footprint.depth_cm * scale
    centre_x = left + width / 2
    centre_y = top + height / 2

    # Two label lines plus the size line need about 32 units of block height; a
    # 42-unit block holds them with a visible margin. Below that the name gets a
    # single line. Wrapping keeps the name meaningful where a first-word fragment
    # ("Floor", "Side") would read as a different piece of furniture.
    line_capacity = 2 if height >= 42 else 1
    budget = width - 4.0
    name = footprint.label.strip() or footprint.item_id
    if _estimated_text_width(name, _LABEL_FONT_SIZE) <= budget:
        lines = [name]
    else:
        lines = _wrap_label(name, width, line_capacity)
    size_text = f"{footprint.width_cm:g} × {footprint.depth_cm:g}"

    text = ""
    if width >= 34 and height >= 18 and lines:
        # Centre the label block vertically; the size line, when it fits, sits
        # below the label rather than replacing it.
        show_size = height >= 34
        label_height = 10.0 * len(lines)
        top_y = centre_y - (label_height / 2) + 5.0 - (4.0 if show_size else 0.0)
        spans = "".join(
            f'<tspan x="{centre_x:.1f}" y="{top_y + index * 10.0:.1f}">'
            f"{theme.escape(line)}</tspan>"
            for index, line in enumerate(lines)
        )
        text = (
            f'<text text-anchor="middle" dominant-baseline="middle" '
            f'font-family="Inter, Arial, sans-serif" font-size="{_LABEL_FONT_SIZE:g}" '
            f'fill="{theme.COLORS["text_primary"]}">{spans}</text>'
        )
        if show_size:
            text += (
                f'<text x="{centre_x:.1f}" y="{top_y + label_height:.1f}" '
                'text-anchor="middle" dominant-baseline="middle" '
                f'font-family="Inter, Arial, sans-serif" '
                f'font-size="{_SIZE_FONT_SIZE:g}" '
                f'fill="{theme.COLORS["text_secondary"]}">'
                f"{theme.escape(size_text)}</text>"
            )

    return (
        f'<g><rect x="{left:.1f}" y="{top:.1f}" width="{width:.1f}" '
        f'height="{height:.1f}" fill="{_FURNITURE_FILL}" '
        f'stroke="{_FURNITURE_STROKE}" stroke-width="1" rx="1.5"/>'
        f"{text}</g>"
    )


def placement_plan_svg(
    *,
    width_cm: float,
    length_cm: float,
    door_wall: Wall,
    door_offset_cm: float,
    door_width_cm: float,
    window_wall: Wall,
    window_offset_cm: float,
    window_width_cm: float,
    footprints: Sequence[PlacedFootprint],
    partial: bool = False,
) -> str:
    """Render the layout as a scaled, dimensioned plan.

    The drawing is a picture of the result, not a second opinion about it: it
    receives only the footprints the engines accepted, and every label, size and
    coordinate is taken from those footprints rather than recomputed here. When
    ``footprints`` is empty the room is still drawn, so the screen shows the
    space the failure refers to instead of a blank panel.

    ``partial`` marks a plan in which some requested copies were not placed. It
    only changes the words: a partial plan is not a validated layout, so the
    accessible name must not say that it is. The geometry is unaffected.
    """

    room_w, room_h, scale, x0, y0 = _plan_geometry(width_cm, length_cm)

    top_edge = _PLAN_H - (y0 + room_h)
    right_edge = x0 + room_w

    door = _opening(
        door_wall,
        door_offset_cm,
        door_width_cm,
        room_w=room_w,
        room_h=room_h,
        scale=scale,
        x0=x0,
        y0=y0,
    )
    window = _opening(
        window_wall,
        window_offset_cm,
        window_width_cm,
        room_w=room_w,
        room_h=room_h,
        scale=scale,
        x0=x0,
        y0=y0,
    )
    door_y1, door_y2 = _PLAN_H - door[1], _PLAN_H - door[3]
    window_y1, window_y2 = _PLAN_H - window[1], _PLAN_H - window[3]

    blocks = "".join(
        furniture_block_svg(
            footprint, room_w=room_w, room_h=room_h, scale=scale, x0=x0, y0=y0
        )
        for footprint in footprints
    )

    floor_label = f"{width_cm:g} × {length_cm:g} cm"
    area_label = f"{(width_cm * length_cm) / 10_000.0:.2f} m²"

    # What a screen reader hears. The plan's meaning is the set of placed pieces,
    # so each footprint is named with its size and position; the drawing alone
    # would otherwise be an unlabelled picture.
    spoken_pieces = " ".join(
        f"{footprint.label}, {footprint.width_cm:g} by "
        f"{footprint.depth_cm:g} centimetres, at {footprint.left_cm:g}, "
        f"{footprint.bottom_cm:g} centimetres from the south-west corner;"
        for footprint in footprints
    ) or "No furniture could be placed in this room."
    plan_label = (
        "Scaled plan of the partly placed furniture layout"
        if partial
        else "Scaled plan of the validated furniture layout"
    )
    spoken = (
        f"Plan of a room {float(width_cm):g} centimetres wide and "
        f"{float(length_cm):g} centimetres long, "
        f"{(float(width_cm) * float(length_cm)) / 10_000.0:.2f} square metres. "
        + _spoken_opening("Door", door_wall, door_offset_cm, door_width_cm)
        + ". "
        + _spoken_opening(
            "Window", window_wall, window_offset_cm, window_width_cm
        )
        + f". Placed furniture: {spoken_pieces} "
        + (
            "Some requested items could not be placed and are not in this room. "
            if partial
            else ""
        )
        + "Origin is the south-west corner; south is at the bottom. This is an "
        "illustrative design plan, not a construction drawing."
    )

    return (
        f'<svg viewBox="0 0 {_PLAN_W:g} {_PLAN_H:g}" role="img" '
        'aria-labelledby="hm-plan-title" aria-describedby="hm-plan-desc" '
        'style="width:100%;height:auto;display:block;">'
        f'<title id="hm-plan-title">{theme.escape(plan_label)}: '
        f"{theme.escape(floor_label)}</title>"
        f'<desc id="hm-plan-desc">{theme.escape(spoken)}</desc>'
        # Room boundary and floor.
        f'<rect x="{x0:.1f}" y="{top_edge:.1f}" width="{room_w:.1f}" '
        f'height="{room_h:.1f}" fill="{theme.COLORS["surface"]}" '
        f'stroke="{theme.COLORS["primary_dark"]}" stroke-width="2"/>'
        f"{blocks}"
        # Door and window, after the blocks so an edge is never hidden.
        f'<line x1="{door[0]:.1f}" y1="{door_y1:.1f}" x2="{door[2]:.1f}" '
        f'y2="{door_y2:.1f}" stroke="{theme.COLORS["primary"]}" '
        f'stroke-width="{_DOOR_STROKE:g}" stroke-linecap="butt"/>'
        f'<line x1="{window[0]:.1f}" y1="{window_y1:.1f}" '
        f'x2="{window[2]:.1f}" y2="{window_y2:.1f}" '
        f'stroke="{theme.COLORS["warning"]}" '
        f'stroke-width="{_WINDOW_STROKE:g}"/>'
        # Width dimension, above the room.
        f'<line x1="{x0:.1f}" y1="{top_edge - 22:.1f}" '
        f'x2="{right_edge:.1f}" y2="{top_edge - 22:.1f}" '
        f'stroke="{theme.COLORS["text_secondary"]}" stroke-width="1"/>'
        f'<text x="{(x0 + right_edge) / 2:.1f}" y="{top_edge - 28:.1f}" '
        'text-anchor="middle" font-family="Inter, Arial, sans-serif" '
        f'font-size="11" fill="{theme.COLORS["text_secondary"]}">'
        f"{theme.escape(floor_label)}</text>"
        # Length dimension, right of the room.
        f'<line x1="{right_edge + 22:.1f}" y1="{top_edge:.1f}" '
        f'x2="{right_edge + 22:.1f}" y2="{top_edge + room_h:.1f}" '
        f'stroke="{theme.COLORS["text_secondary"]}" stroke-width="1"/>'
        f'<text x="{right_edge + 28:.1f}" '
        f'y="{top_edge + room_h / 2:.1f}" dominant-baseline="middle" '
        'font-family="Inter, Arial, sans-serif" font-size="11" '
        f'fill="{theme.COLORS["text_secondary"]}">{theme.escape(area_label)}</text>'
        # The origin, so the coordinate convention is visible in the picture.
        f'<text x="{x0:.1f}" y="{top_edge + room_h + 16:.1f}" '
        'font-family="Inter, Arial, sans-serif" font-size="9" '
        f'fill="{theme.COLORS["text_secondary"]}">'
        "Origin (0, 0) &middot; south-west</text>"
        "</svg>"
    )


def plan_legend() -> str:
    """The plan's key, in words as well as colour.

    Every entry names what it marks, so the drawing is readable without relying
    on the swatches (``DESIGN_SYSTEM.md`` §7).
    """

    def swatch(fill: str, stroke: str, *, dashed: bool = False) -> str:
        dash = 'border-style:dashed;' if dashed else ""
        return (
            f'<span aria-hidden="true" style="display:inline-block;width:16px;'
            f'height:12px;background:{fill};border:1px solid {stroke};'
            f'border-radius:2px;{dash}"></span>'
        )

    def item(markup: str, label: str, *, first: bool = False) -> str:
        margin = "" if first else "margin-left:20px;"
        return (
            f'<span style="display:inline-flex;align-items:center;gap:6px;'
            f'{margin}">{markup}{theme.escape(label)}</span>'
        )

    door_mark = (
        f'<span aria-hidden="true" style="display:inline-block;width:16px;'
        f'height:4px;background:{theme.COLORS["primary"]};"></span>'
    )
    window_mark = (
        f'<span aria-hidden="true" style="display:inline-block;width:16px;'
        f'height:4px;background:{theme.COLORS["warning"]};"></span>'
    )

    return (
        '<p class="hm-plan-legend">'
        + item(
            swatch(_FURNITURE_FILL, _FURNITURE_STROKE),
            "Placed furniture",
            first=True,
        )
        # A real text space between entries: the parent is a flex container, so
        # a bare newline would be discarded and the labels would run together
        # ("Placed furnitureDoorWindow") for a screen reader and in copied text.
        + " "
        + item(door_mark, "Door")
        + " "
        + item(window_mark, "Window")
        + " "
        + item(
            swatch(theme.COLORS["surface"], theme.COLORS["primary_dark"], dashed=True),
            "Room boundary",
        )
        + "</p>"
        '<p class="hm-field-note">Drawn to scale from the coordinates the '
        "placement and spatial engines produced. Names wrap onto a second line "
        "where a block is narrow, and a block too small for its name carries no "
        "label; the full name, size and position of every piece are listed "
        "beside the plan. This is an illustrative design plan, not a "
        "construction or building-code drawing.</p>"
    )


__all__ = [
    "furniture_block_svg",
    "legend",
    "placement_plan_svg",
    "plan_legend",
    "room_diagram_svg",
]
