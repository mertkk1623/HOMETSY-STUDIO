"""The Design Brief screen: AI operation 1, under the user's control.

The call happens only when the user presses the button. Nothing here decides
whether the brief is current — that is ``WorkflowState.is_complete`` — and nothing
here can store a brief from a failed call, because the write goes through
``WorkflowState.attempt``, which records only what ``produce`` returned.

Why the button rather than a form
---------------------------------
Streamlit reruns a script top to bottom on every interaction. If the request were
issued inline whenever the step was incomplete, an unrelated widget on another
screen would quietly re-send it. A button makes the call an event: the body runs
in the same rerun the click caused, and a rerun with no click reaches the render
branch and stops.
"""

from __future__ import annotations

from models.schemas import DesignBrief
from workflow.state import WorkflowStep

from ui import ai_actions, commits, session, theme
from ui.shell import (
    render_flash,
    render_issues,
    render_shell_header,
    stage_eyebrow,
)

#: What the button is about to send, stated before it is pressed.
_CALL_NOTE = (
    "This sends your saved room, preferences, requirements and budget to the "
    "AI model once, and nothing else. No catalog item is chosen and no price is "
    "calculated. It usually takes a few seconds."
)

_REBUILD_NOTE = (
    "Rebuilding sends the same saved input again and replaces the stored brief. "
    "Concept generation depends on the brief, so an existing set of concepts "
    "will be cleared when the new brief differs."
)


def _input_rows(state) -> list[tuple[str, str]]:
    """The four stored inputs, read back from their own models."""

    assert state.room is not None
    assert state.preferences is not None
    assert state.requirements is not None
    assert state.budget is not None
    requirements = ", ".join(state.requirements.functional_requirements) or "None given"
    # The name often equals the type ("Living Room"), so the type is only added
    # when it says something the name does not.
    room_label = state.room.name
    if state.room.room_type.value.casefold() not in room_label.casefold():
        room_label = f"{room_label} · {state.room.room_type.value}"
    return [
        ("Room", room_label),
        (
            "Floor area",
            f"{state.room.width_cm:g} × {state.room.length_cm:g} cm "
            f"({state.room.area_sqm:.2f} m²)",
        ),
        ("Style", state.preferences.style.value),
        ("Colour palette", state.preferences.palette.value),
        ("Requirements", requirements),
        (
            "Budget",
            commits.format_money(state.budget.total_budget, state.budget.currency),
        ),
    ]


def _render_brief(brief: DesignBrief) -> None:
    """Present the stored brief. Every string is AI output, so all of it is
    escaped by the theme helpers before it reaches HTML."""

    theme.html_block(
        theme.group_heading("Brief summary")
        + theme.brief_summary(brief.summary)
    )

    for title, items in (
        ("Functional priorities", brief.functional_priorities),
        ("Constraints", brief.constraints),
        ("Open questions", brief.ambiguities),
        ("Risks worth knowing", brief.warnings),
    ):
        theme.html_block(
            '<div class="hm-brief-block">'
            f"{theme.block_title(title)}"
            f"{theme.bullet_list(items)}"
            "</div>"
        )


def render() -> None:
    """Draw the brief screen."""

    import streamlit as st

    state = session.get_workflow()
    if state.room is None or state.preferences is None:
        session.set_flash(
            "Save the room and the design preferences before analysing a brief.",
            tone="warning",
        )
        session.go_to(
            session.SCREEN_ROOM
            if state.room is None
            else session.SCREEN_PREFERENCES
        )
        return

    render_shell_header(state, "Design Concepts")
    render_flash()

    theme.html_block(
        theme.page_intro(
            stage_eyebrow("Design Concepts") + " · Brief analysis",
            "Analyse the design brief",
            "The AI reads the input you have already saved and writes a short "
            "structured brief: what the room has to do, what limits the design, "
            "and what is still unclear. It describes your request; it does not "
            "design the room or choose furniture.",
        )
    )

    theme.html_block(theme.group_heading("What will be sent"))
    theme.html_block(theme.summary(_input_rows(state)))

    ready = state.is_complete(WorkflowStep.DESIGN_PREFERENCES)
    if not ready:
        theme.html_block(
            theme.group_heading("Not ready yet")
            + '<p class="hm-card-copy">The room, preferences, requirements and '
            "budget must all be saved before a brief can be analysed.</p>"
        )
        _render_navigation()
        return

    brief_is_current = state.is_complete(WorkflowStep.BRIEF_ANALYSIS)
    has_brief = state.brief is not None

    theme.html_block(theme.group_heading("Saved brief" if brief_is_current else "Brief"))
    if brief_is_current and state.brief is not None:
        _render_brief(state.brief)
    elif has_brief:
        # A brief is present but one of its prerequisites is missing, so it is
        # not current. Saying so is the whole point of asking ``is_complete``
        # rather than checking for a stored value.
        theme.html_block(
            theme.quiet_badge("Out of date")
            + '<p class="hm-field-note">A brief is stored, but the input it was '
            "analysed from has since changed. It is not shown as a current "
            "result. Analyse again to replace it.</p>"
        )
    else:
        theme.html_block(
            '<p class="hm-card-copy">No brief has been analysed yet.</p>'
        )

    theme.html_block(theme.call_note(_CALL_NOTE))
    label = (
        "Rebuild the brief"
        if has_brief
        else "Analyse the brief"
    )
    if has_brief:
        theme.html_block(theme.field_note(_REBUILD_NOTE))

    if st.button(label, type="primary", width="stretch"):
        _run_analysis(state)

    _render_navigation(
        allow_concepts=brief_is_current,
    )


def _run_analysis(state) -> None:
    """Perform exactly one request, then rerun.

    The work happens inside ``state.attempt`` so a failure cannot reach the
    stored brief: ``attempt`` records only what its callable returned, and wraps
    any exception in ``StepFailed`` with the cause preserved.
    """

    import streamlit as st

    from workflow.state import StepFailed

    assert state.room is not None
    assert state.preferences is not None
    assert state.requirements is not None
    assert state.budget is not None

    with st.spinner(
        "Analysing your input. This sends one request and usually takes a few "
        "seconds."
    ):
        try:
            state.attempt(
                WorkflowStep.BRIEF_ANALYSIS,
                lambda: ai_actions.analyze_brief(
                    room=state.room,
                    preferences=state.preferences,
                    requirements=state.requirements,
                    budget=state.budget,
                ),
                state.record_brief,
            )
        except StepFailed as failure:
            message = ai_actions.failure_message(failure.cause)
            session.set_flash(message, tone="error")
            st.rerun()
            return
        except Exception as unexpected:  # noqa: BLE001 - never a traceback on screen
            session.set_flash(ai_actions.failure_message(unexpected), tone="error")
            st.rerun()
            return

    session.set_flash("The design brief is ready.", tone="success")
    st.rerun()


def _render_navigation(*, allow_concepts: bool = False) -> None:
    """Move on, back, or to the concepts screen when a current brief exists."""

    import streamlit as st

    forward, back, restart = st.columns([2, 1, 1], gap="small")
    with forward:
        if allow_concepts:
            if st.button(
                "Continue to concepts", type="primary", width="stretch"
            ):
                session.go_to(session.SCREEN_CONCEPTS)
        else:
            theme.html_block(
                theme.field_note(
                    "Continue to concepts unlocks once a current brief exists."
                )
            )
    with back:
        if st.button("Edit input", width="stretch"):
            session.go_to(session.SCREEN_REVIEW)
    with restart:
        if st.button("Start a new project", width="stretch"):
            session.reset_workflow()
            session.set_flash(
                "Project cleared. Describe a new room to begin.", tone="info"
            )
            session.go_to(session.SCREEN_ROOM)


__all__ = ["render"]
