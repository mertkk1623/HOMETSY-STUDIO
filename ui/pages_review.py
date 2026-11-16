"""The Project Input Review screen.

This screen closes the loop on the brief's first goal: "the user can build a
valid design input without making an AI call". It shows the four stored inputs,
the findings ``core.validation`` produced for them, and the route to the first
AI-assisted step.

Nothing here computes anything: the area comes from ``RoomInput.area_sqm``, the
money from ``BudgetInput.total_budget``, and the validity from
``validate_inputs`` plus ``WorkflowState.is_complete``.

Reaching the brief screen from here does not call a model. The brief screen makes
the request only when its own button is pressed.
"""

from __future__ import annotations

from core.validation import validate_inputs
from models.schemas import BudgetInput, DesignPreferences, RoomInput, UserRequirements
from workflow.state import WorkflowStep

from ui import commits, session, theme
from ui.shell import render_flash, render_shell_header, stage_eyebrow

_NEXT_STEP_NOTE = (
    "The next step asks the AI for a structured design brief. Nothing has been "
    "sent to a model yet: the brief screen makes one request, and only when you "
    "press its button."
)

_NEXT_STEP_BLOCKED = (
    "The AI-assisted steps need a complete, valid input. Correct the problems "
    "above before continuing."
)


def _preference_rows(
    preferences: DesignPreferences,
    requirements: UserRequirements,
    budget: BudgetInput,
) -> list[tuple[str, str]]:
    materials = ", ".join(preferences.material_preferences) or "None given"
    functions = ", ".join(requirements.functional_requirements) or "None given"
    notes = requirements.notes or "None given"
    return [
        ("Design style", preferences.style.value),
        ("Colour palette", preferences.palette.value),
        ("Material preferences", materials),
        ("Functional requirements", functions),
        ("Additional notes", notes),
        ("Budget", commits.format_money(budget.total_budget, budget.currency)),
    ]


def _findings_block(room: RoomInput, preferences: DesignPreferences,
                    requirements: UserRequirements, budget: BudgetInput) -> None:
    """Render the shared validation report for the four inputs."""

    import streamlit as st

    findings = validate_inputs(room, preferences, requirements, budget)
    errors = [finding for finding in findings if finding.is_error]
    warnings = [finding for finding in findings if not finding.is_error]

    if errors:
        st.error(
            "The saved input no longer passes validation. Nothing downstream "
            "can be trusted until it is corrected."
        )
        for finding in errors:
            st.markdown(f"- {finding.message}")
    else:
        st.success("All blocking checks passed.")

    for finding in warnings:
        st.warning(finding.message)


def render() -> None:
    """Draw the review screen."""

    import streamlit as st

    state = session.get_workflow()
    if state.room is None:
        session.set_flash("Describe the room first.", tone="warning")
        session.go_to(session.SCREEN_ROOM)
        return

    render_shell_header(state, "Design Preferences")
    render_flash()

    theme.html_block(
        theme.page_intro(
            stage_eyebrow("Design Preferences") + " · Review",
            "Your project input",
            "These are the four values every later step is derived from. "
            "Changing any of them will clear the results that depended on it.",
        )
    )

    theme.html_block(theme.group_heading("Room"))
    theme.html_block(theme.summary(commits.room_summary_rows(state.room)))

    if state.preferences is None or state.requirements is None or state.budget is None:
        theme.html_block(
            theme.group_heading("Preferences and budget")
            + '<p class="hm-card-copy">This step has not been completed yet.</p>'
        )
        theme.html_block(theme.group_heading("Checks"))
        theme.html_block(
            theme.summary([("Room information", "Saved")])
        )
        _render_actions()
        return

    theme.html_block(theme.group_heading("Preferences and budget"))
    theme.html_block(
        theme.summary(
            _preference_rows(state.preferences, state.requirements, state.budget)
        )
    )

    theme.html_block(theme.group_heading("Checks"))
    # ``validate_inputs`` is the single source of the advisory findings, so the
    # screen renders them from the stored inputs rather than also replaying the
    # copy captured at commit time — which listed every warning twice.
    _findings_block(state.room, state.preferences, state.requirements, state.budget)

    _render_status(state)
    _render_actions()


def _render_status(state) -> None:
    """State which workflow steps are complete, using the workflow's own answer."""

    import streamlit as st

    complete = state.is_complete(WorkflowStep.DESIGN_PREFERENCES)
    theme.html_block(theme.group_heading("Workflow status"))
    if complete:
        theme.html_block(
            theme.success_badge("Input complete")
            + '<p class="hm-field-note">Room information, design preferences, '
            "requirements and budget are all saved and valid. This is the "
            "complete deterministic input for the project.</p>"
        )
    else:
        theme.html_block(
            theme.quiet_badge("Incomplete")
            + '<p class="hm-field-note">One or more required values are '
            "missing.</p>"
        )

    theme.html_block(theme.group_heading("Next stage"))
    if complete:
        theme.html_block(f'<p class="hm-card-copy">{theme.escape(_NEXT_STEP_NOTE)}</p>')
        if st.button("Continue to design brief", type="primary", width="stretch"):
            session.go_to(session.SCREEN_BRIEF)
    else:
        theme.html_block(
            f'<p class="hm-card-copy">{theme.escape(_NEXT_STEP_BLOCKED)}</p>'
        )


def _render_actions() -> None:
    import streamlit as st

    first, second, third = st.columns([1, 1, 2], gap="small")
    with first:
        if st.button("Edit room", width="stretch"):
            session.go_to(session.SCREEN_ROOM)
    with second:
        if st.button("Edit preferences", width="stretch"):
            session.go_to(session.SCREEN_PREFERENCES)
    with third:
        if st.button("Start a new project", width="stretch"):
            session.reset_workflow()
            session.set_flash(
                "Project cleared. Describe a new room to begin.", tone="info"
            )
            session.go_to(session.SCREEN_ROOM)


__all__ = ["render"]
