"""The Final Report screen: finalize the project, then hand over the PDF.

This is the last step of the workflow and the only screen that produces a file.
Three rules shape it:

* **No report without a complete project.** The button appears only when
  :func:`ui.report.can_finalize` says every earlier step is complete, which is
  ``WorkflowState``'s own prerequisite list rather than a second rule invented
  here.
* **Generating is an event, not a render step.** Streamlit reruns on every
  interaction, so the PDF is written only inside the button's branch. A rerun
  with no click re-uses the artifact already in the session, and
  :func:`ui.report.is_current` decides whether that artifact still describes the
  project.
* **A failed PDF does not destroy the project.** ``finalize()`` runs first and
  stores ``ProjectResult``; a generation failure afterwards is reported as a
  failure and leaves the finalized result in place, so the button remains and
  the report can be produced again.

Nothing here calculates. Layout, money and the written evaluation all arrive
already computed.
"""

from __future__ import annotations

from typing import Final

from workflow.state import WorkflowStep
from workflow import state as workflow

from ui import commits, report as report_view, session, theme
from ui.shell import render_flash, render_shell_header, stage_eyebrow
#: The artifact lives under its own session key so the workflow object stays the
#: only holder of project data.
ARTIFACT_KEY: Final[str] = "hm_report_artifact"

_GENERATE_LABEL: Final[str] = "Generate the PDF report"
_REGENERATE_LABEL: Final[str] = "Generate the report again"

_SCOPE_NOTE: Final[str] = (
    "The report contains the project overview, the design brief, the selected "
    "concept, the furniture and materials, the validated 2D plan, the spatial "
    "validation, the budget analysis, the AI design evaluation and the "
    "limitations. Every figure in it comes from the results already on screen."
)

_NO_CALCULATION_NOTE: Final[str] = (
    "Generating the report sends nothing to the AI model and recalculates "
    "nothing. It lays out the stored results as an A4 PDF, so the file is "
    "reproducible from the same project data."
)

_FAILURE_NOTE: Final[str] = (
    "Your project is unchanged and the results are still stored, so the report "
    "can be generated again."
)


def _artifact():
    import streamlit as st

    return st.session_state.get(ARTIFACT_KEY)


def _store_artifact(artifact) -> None:
    import streamlit as st

    st.session_state[ARTIFACT_KEY] = artifact


def _clear_artifact() -> None:
    import streamlit as st

    st.session_state.pop(ARTIFACT_KEY, None)


# --------------------------------------------------------------------------- #
# What will be in the report
# --------------------------------------------------------------------------- #


def _render_contents(state, source_room) -> None:
    """A factual summary of the project the report will describe."""

    assert state.brief is not None
    assert state.selected_concept is not None
    assert state.budget_analysis is not None
    assert state.placement is not None

    rows = [
        ("Room", f"{source_room.name} · {source_room.area_sqm:.2f} m²"),
        ("Design style", state.preferences.style.value),
        ("Colour palette", state.preferences.palette.value),
        ("Selected concept", state.selected_concept.name),
        ("Catalog items", str(len(state.furniture))),
        (
            "Layout",
            f"{state.placement.placed_count} of "
            f"{state.placement.requested_count} placed",
        ),
        (
            "Indicative furniture total",
            commits.format_money(
                state.budget_analysis.total_estimated,
                state.budget_analysis.currency,
            ),
        ),
        ("Design evaluation", "Recorded"),
    ]
    theme.html_block(theme.group_heading("What the report will describe"))
    theme.html_block(theme.summary(rows))
    theme.html_block(theme.field_note(_SCOPE_NOTE))


# --------------------------------------------------------------------------- #
# The download
# --------------------------------------------------------------------------- #


def _render_download(artifact) -> None:
    """Offer the file that already exists. Never regenerates it."""

    import streamlit as st

    try:
        payload = artifact.path.read_bytes()
    except OSError:
        theme.html_block(
            theme.error_badge("Report file missing")
            + '<p class="hm-card-copy">The report file is no longer on disk. '
            "Generate it again below.</p>"
        )
        return

    theme.html_block(
        theme.success_badge("Report ready")
        + theme.paragraph(
            f"The PDF has been generated ({artifact.size_bytes:,} bytes) and can "
            "be downloaded below. It stays available until the project changes."
        )
    )
    st.download_button(
        "Download the PDF report",
        data=payload,
        file_name=artifact.filename,
        mime="application/pdf",
        width="stretch",
    )
    theme.html_block(
        theme.field_note(
            "The file name is derived from the room name and made safe for a "
            "filesystem: Turkish letters are transliterated, spaces become "
            "dashes, and anything else is removed."
        )
    )


# --------------------------------------------------------------------------- #
# Actions
# --------------------------------------------------------------------------- #


def _generate(state) -> None:
    """Finalize and write the PDF. One click, one file, then a rerun."""

    import streamlit as st

    with st.spinner(
        "Finalising the project and laying out the PDF report. This takes a "
        "moment and sends nothing to the AI model."
    ):
        try:
            artifact = report_view.finalize_and_build(state)
        except Exception as failure:  # noqa: BLE001 - never a traceback on screen
            _clear_artifact()
            session.set_flash(report_view.report_error_message(failure), tone="error")
            st.rerun()
            return

    _store_artifact(artifact)
    session.set_flash(
        "The PDF report is ready to download.", tone="success"
    )
    st.rerun()


# --------------------------------------------------------------------------- #
# Navigation
# --------------------------------------------------------------------------- #


def _render_navigation(state) -> None:
    import streamlit as st

    back, restart = st.columns(2, gap="small")
    with back:
        if st.button("Back to the budget analysis", width="stretch"):
            session.go_to(session.SCREEN_BUDGET)
    with restart:
        if st.button("Start a new project", width="stretch"):
            session.reset_workflow()
            _clear_artifact()
            session.set_flash(
                "Project cleared. Describe a new room to begin.", tone="info"
            )
            session.go_to(session.SCREEN_ROOM)


# --------------------------------------------------------------------------- #
# The screen
# --------------------------------------------------------------------------- #


def render() -> None:
    """Draw the final report screen."""

    import streamlit as st

    state = session.get_workflow()

    # The artifact is withdrawn before anything else can return early: a report
    # that no longer describes the project must not survive in the session, even
    # while the user is being sent back to fix the step that changed.
    stale = False
    artifact = _artifact()
    if artifact is not None and not report_view.is_current(artifact, state):
        _clear_artifact()
        artifact = None
        stale = True

    if state.room is None or state.preferences is None:
        session.set_flash(
            "Save the room and the design preferences first.", tone="warning"
        )
        session.go_to(session.SCREEN_ROOM)
        return

    if not state.is_complete(WorkflowStep.DESIGN_EVALUATION):
        session.set_flash(
            "Evaluate the design before generating the report.", tone="warning"
        )
        session.go_to(session.SCREEN_EVALUATION)
        return

    render_shell_header(state, "Final Report")
    render_flash()

    theme.html_block(
        theme.page_intro(
            stage_eyebrow("Final Report") + " · Export",
            "Download the project report",
            "Finalising the project assembles everything you have approved into "
            "one result, and the report lays that result out as a professional "
            "A4 PDF: overview, brief, concept, furniture and materials, the "
            "validated plan, the spatial verdict, the budget and the design "
            "evaluation.",
        )
    )

    _render_contents(state, state.room)

    current = artifact is not None

    if current:
        _render_download(artifact)
    elif stale:
        theme.html_block(
            theme.warning_badge("Report out of date")
            + theme.paragraph(
                "The project has changed since the last report was generated, so "
                "that file no longer describes it and has been withdrawn. "
                "Generate the report again to include the current results."
            )
        )

    can_build = report_view.can_finalize(state)
    if can_build:
        theme.html_block(theme.call_note(_NO_CALCULATION_NOTE))
        label = _REGENERATE_LABEL if current else _GENERATE_LABEL
        # With a current file in place, generating again is a repeat action; the
        # download above is the way forward and keeps the emphasis.
        if st.button(
            label,
            type="secondary" if current else "primary",
            width="stretch",
        ):
            _generate(state)
    else:
        outstanding = tuple(
            step
            for step in state.outstanding_steps
            if step is not WorkflowStep.FINAL_RESULT
        )
        theme.html_block(
            theme.field_note(
                "The report unlocks when every earlier step is complete. Still "
                "outstanding: "
                + ", ".join(
                    workflow.STEP_LABELS[step] for step in outstanding
                )
                + "."
            )
        )

    theme.html_block(theme.field_note(_FAILURE_NOTE))
    _render_navigation(state)


__all__ = ["ARTIFACT_KEY", "render"]
