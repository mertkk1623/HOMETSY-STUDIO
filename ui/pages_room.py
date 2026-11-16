"""The Room Information screen.

One form, two groups: the room itself and its two openings. Submitting runs the
same two gates the rest of the application uses — Pydantic, then
``core.validation`` — and only a room that passes both reaches
``WorkflowState.set_room``.

The form is a *form* rather than a live-updating set of widgets on purpose. In a
live form every keystroke would commit a partial room, and each commit would
invalidate the user's downstream work; a half-typed width of 4 cm would clear a
completed concept stage. Explicit submission is what makes "invalidation happens
because the user changed something" true.
"""

from __future__ import annotations

from models.schemas import RoomType, Wall

from ui import commits, diagram, session, theme
from ui.shell import (
    render_flash,
    render_issues,
    render_shell_header,
    render_warnings,
    stage_eyebrow,
)

#: Guard rails for the widgets. These mirror the approved model limits purely so
#: the control cannot produce a value Pydantic would reject; the ranges are not
#: restated as rules — ``models.schemas`` and ``core.room_engine`` remain the
#: authority, and a value outside them is still reported by both gates.
_MIN_DIM = 100.0
_MAX_DIM = 2000.0
_MIN_CEILING = 200.0
_MAX_CEILING = 500.0
_MIN_OPENING = 40.0

_WALL_LABELS = {
    Wall.NORTH: "North wall",
    Wall.SOUTH: "South wall",
    Wall.EAST: "East wall",
    Wall.WEST: "West wall",
}


def _initial_room_values() -> dict[str, object]:
    """Seed values for the form, taken from the stored room when there is one.

    Reading from the workflow state rather than from the widgets is what makes
    "come back and edit" show the saved room instead of an empty form.
    """

    room = session.stored_room()
    if room is None:
        return {
            "room_type": RoomType.LIVING_ROOM,
            "room_name": "",
            "width_cm": 400.0,
            "length_cm": 500.0,
            "ceiling_cm": 270.0,
            "door_wall": Wall.SOUTH,
            "door_offset": 60.0,
            "door_width": 90.0,
            "window_wall": Wall.NORTH,
            "window_offset": 120.0,
            "window_width": 160.0,
        }
    return {
        "room_type": room.room_type,
        "room_name": room.name,
        "width_cm": room.width_cm,
        "length_cm": room.length_cm,
        "ceiling_cm": room.ceiling_height_cm,
        "door_wall": room.door.wall,
        "door_offset": room.door.offset_cm,
        "door_width": room.door.width_cm,
        "window_wall": room.window.wall,
        "window_offset": room.window.offset_cm,
        "window_width": room.window.width_cm,
    }


def _seed_form() -> None:
    for name, value in _initial_room_values().items():
        session.seed(name, value)


def _wall_span_cm(wall: Wall, width_cm: float, length_cm: float) -> float:
    """The wall's own length, used only to bound the offset widget.

    This is not a validation: the same arithmetic is done by
    ``core.room_engine.wall_length_cm`` for the checks. Here it just keeps the
    slider from offering a position the wall does not have.
    """

    return width_cm if wall in (Wall.NORTH, Wall.SOUTH) else length_cm


def render() -> None:
    """Draw the room screen."""

    import streamlit as st

    state = session.get_workflow()
    render_shell_header(state, "Room Setup")
    render_flash()

    theme.html_block(
        theme.page_intro(
            stage_eyebrow("Room Setup") + " · Room",
            "Describe the room",
            "Hometsy works from a rectangular room. Give it a name, its "
            "dimensions in centimetres, and the two openings that shape how the "
            "space can be used.",
        )
    )

    if state.room is not None:
        theme.html_block(
            theme.summary(commits.room_summary_rows(state.room))
            + '<p class="hm-field-note">Saved. Editing the form below replaces '
            "this room; anything already derived from it will be cleared.</p>"
        )

    _seed_form()

    with st.form("hm_room_form", clear_on_submit=False):
        theme.html_block(theme.group_heading("Room"))

        left, right = st.columns(2, gap="large")
        with left:
            room_type = st.selectbox(
                "Room type",
                options=tuple(RoomType),
                format_func=lambda value: value.value,
                key=session.widget_key("room_type"),
            )
        with right:
            name = st.text_input(
                "Room name",
                key=session.widget_key("room_name"),
                max_chars=80,
                placeholder="e.g. Living room",
            )

        width_col, length_col, ceiling_col = st.columns(3, gap="large")
        with width_col:
            width = st.number_input(
                "Width (cm)",
                min_value=_MIN_DIM,
                max_value=_MAX_DIM,
                step=10.0,
                key=session.widget_key("width_cm"),
                help="The wall the door and window offsets are measured along "
                "when they sit on the north or south side.",
            )
        with length_col:
            length = st.number_input(
                "Length (cm)",
                min_value=_MIN_DIM,
                max_value=_MAX_DIM,
                step=10.0,
                key=session.widget_key("length_cm"),
            )
        with ceiling_col:
            ceiling = st.number_input(
                "Ceiling height (cm)",
                min_value=_MIN_CEILING,
                max_value=_MAX_CEILING,
                step=5.0,
                key=session.widget_key("ceiling_cm"),
                help="Used as context for the design brief; it does not affect "
                "the 2D floor plan.",
            )

        theme.html_block(
            theme.group_heading(
                "Door",
                "One door is required. The offset is the distance from the wall's "
                "starting corner to the near edge of the door.",
            )
        )
        door_col_a, door_col_b, door_col_c = st.columns(3, gap="large")
        with door_col_a:
            door_wall = st.selectbox(
                "Door wall",
                options=tuple(Wall),
                format_func=lambda value: _WALL_LABELS[value],
                key=session.widget_key("door_wall"),
            )
        with door_col_b:
            door_offset = st.number_input(
                "Door offset (cm)",
                min_value=0.0,
                max_value=max(_wall_span_cm(door_wall, width, length), 0.0),
                step=5.0,
                key=session.widget_key("door_offset"),
            )
        with door_col_c:
            door_width = st.number_input(
                "Door width (cm)",
                min_value=_MIN_OPENING,
                max_value=max(
                    min(_wall_span_cm(door_wall, width, length), _MAX_DIM),
                    _MIN_OPENING,
                ),
                step=5.0,
                key=session.widget_key("door_width"),
            )

        theme.html_block(
            theme.group_heading(
                "Window",
                "One window is required. A door and a window on the same wall "
                "cannot share the same stretch of wall.",
            )
        )
        win_col_a, win_col_b, win_col_c = st.columns(3, gap="large")
        with win_col_a:
            window_wall = st.selectbox(
                "Window wall",
                options=tuple(Wall),
                format_func=lambda value: _WALL_LABELS[value],
                key=session.widget_key("window_wall"),
            )
        with win_col_b:
            window_offset = st.number_input(
                "Window offset (cm)",
                min_value=0.0,
                max_value=max(_wall_span_cm(window_wall, width, length), 0.0),
                step=5.0,
                key=session.widget_key("window_offset"),
            )
        with win_col_c:
            window_width = st.number_input(
                "Window width (cm)",
                min_value=_MIN_OPENING,
                max_value=max(
                    min(_wall_span_cm(window_wall, width, length), _MAX_DIM),
                    _MIN_OPENING,
                ),
                step=5.0,
                key=session.widget_key("window_width"),
            )

        theme.html_block(theme.required_note())
        submitted = st.form_submit_button("Save room information", type="primary")

    # The diagram reads the widget values directly, so it follows the form while
    # it is being filled in without committing anything.
    preview_col, notes_col = st.columns([3, 2], gap="large")
    with preview_col:
        theme.html_block(
            theme.group_heading("Layout preview")
            + diagram.room_diagram_svg(
                width_cm=float(width),
                length_cm=float(length),
                door_wall=door_wall,
                door_offset_cm=float(door_offset),
                door_width_cm=float(door_width),
                window_wall=window_wall,
                window_offset_cm=float(window_offset),
                window_width_cm=float(window_width),
            )
            + diagram.legend()
        )
    with notes_col:
        theme.html_block(
            theme.group_heading("What happens next")
            + '<p class="hm-card-copy">Saving stores this room and unlocks the '
            "preferences step. Nothing is sent to the AI yet, and nothing is "
            "priced.</p>"
        )

    if submitted:
        # Snapshot what exists before the edit, so the confirmation can describe
        # what the user actually lost rather than what the rule table covers.
        before = session.present_keys(state)
        outcome = commits.build_room(
            room_type=room_type,
            name=name,
            width_cm=float(width),
            length_cm=float(length),
            ceiling_height_cm=float(ceiling),
            door_wall=door_wall,
            door_offset_cm=float(door_offset),
            door_width_cm=float(door_width),
            window_wall=window_wall,
            window_offset_cm=float(window_offset),
            window_width_cm=float(window_width),
        )

        if not outcome.is_ok or outcome.value is None:
            render_issues(outcome.issues)
            render_warnings(outcome.warnings)
            return

        dropped = state.set_room(outcome.value)
        message = session.invalidation_message(dropped, previously_present=before)
        if message:
            session.set_flash(message, tone="info")
        else:
            session.set_flash("Room information saved.", tone="success")
        session.go_to(session.SCREEN_PREFERENCES)


__all__ = ["render"]
