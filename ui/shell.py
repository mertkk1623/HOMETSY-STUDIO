"""The workflow shell: brand line, stage indicator and queued feedback.

``DESIGN_SYSTEM.md`` §6.2 asks the user to always know which stage they are in,
what is required and what happens next. The five brand-facing stages are defined
here and mapped onto the ten internal workflow steps; the mapping is a display
concern, so it lives in the interface and not in ``workflow``.

Stage state is derived from ``WorkflowState.is_complete`` for the steps a stage
covers — never from "is this value not None". That is what keeps a retained but
prerequisite-less result from being presented as current.

A stage is listed in :data:`AVAILABLE_STAGES` only once its screens exist. The
brief and the concepts screens are part of the same "Design Concepts" stage, so
the stage becomes complete when all three of its steps are, and the strip says
"In progress" while only some of them are.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from workflow.state import (
    STEP_LABELS,
    WorkflowState,
    WorkflowStep,
)

from ui import theme

#: The five stages the user sees (DESIGN_SYSTEM.md §6.2), each backed by the
#: internal steps it governs.
#:
#: The evaluation and the budget belong to "Design Plan" because they read the
#: plan: the evaluation interprets it and the budget prices it. "Final Report" is
#: the PDF, which is the last screen of the journey.
STAGES: Final[tuple[tuple[str, tuple[WorkflowStep, ...]], ...]] = (
    ("Room Setup", (WorkflowStep.ROOM_INFORMATION,)),
    ("Design Preferences", (WorkflowStep.DESIGN_PREFERENCES,)),
    (
        "Design Concepts",
        (
            WorkflowStep.BRIEF_ANALYSIS,
            WorkflowStep.CONCEPT_GENERATION,
            WorkflowStep.CONCEPT_SELECTION,
        ),
    ),
    (
        "Design Plan",
        (
            WorkflowStep.RECOMMENDATIONS,
            WorkflowStep.SPATIAL_VALIDATION,
            WorkflowStep.DESIGN_EVALUATION,
            WorkflowStep.BUDGET_ANALYSIS,
        ),
    ),
    ("Final Report", (WorkflowStep.FINAL_RESULT,)),
)

#: Stages this development step implements. The rest are shown as unavailable so
#: the interface never implies that unimplemented screens exist.
#:
#: Phase 6 completes the strip: every stage the V1 journey describes now has a
#: screen, so nothing is left marked "Not available yet".
AVAILABLE_STAGES: Final[frozenset[str]] = frozenset(
    {
        "Room Setup",
        "Design Preferences",
        "Design Concepts",
        "Design Plan",
        "Final Report",
    }
)


@dataclass(frozen=True)
class StageStatus:
    name: str
    state: str  # complete | current | pending | unavailable

    @property
    def label(self) -> str:
        return {
            "complete": "Complete",
            "current": "In progress",
            "pending": "Not started",
            "unavailable": "Not available yet",
        }[self.state]


def stage_statuses(state: WorkflowState, current_stage: str) -> tuple[StageStatus, ...]:
    """Classify all five stages for the indicator strip.

    A stage with some but not all of its steps complete is "In progress" even
    when the user has moved on, because "Not started" would be untrue once its
    brief exists.
    """

    statuses: list[StageStatus] = []
    for name, steps in STAGES:
        if name not in AVAILABLE_STAGES:
            statuses.append(StageStatus(name, "unavailable"))
            continue
        done = [state.is_complete(step) for step in steps]
        if all(done):
            statuses.append(StageStatus(name, "complete"))
        elif any(done) or name == current_stage:
            statuses.append(StageStatus(name, "current"))
        else:
            statuses.append(StageStatus(name, "pending"))
    return tuple(statuses)


def stage_position(current_stage: str) -> tuple[int, int]:
    """Where the current stage sits in the five-stage journey, 1-based.

    The screens used to number themselves against internal steps — "Step 1 of
    2" on the room screen, "Design Plan · step 5" on the budget screen — while
    the header simultaneously reported "2 of 10 steps complete". Three
    vocabularies for one journey. This function is the single answer, and the
    pages take their numbering from it rather than counting for themselves.
    """

    names = [name for name, _ in STAGES]
    total = len(names)
    if current_stage in names:
        return names.index(current_stage) + 1, total
    return 1, total


def stage_eyebrow(current_stage: str) -> str:
    """The one-line position label shown above a page title, e.g. ``Stage 2 of 5``."""

    number, total = stage_position(current_stage)
    return f"Stage {number} of {total}"


def next_action_hint(state: WorkflowState, current_stage: str) -> str:
    """One sentence naming the next thing the workflow needs, or ``""``.

    Derived from ``WorkflowState.next_step`` so the shell cannot invent a next
    step the workflow disagrees with, and silent when nothing is outstanding — a
    finished project is not told to "continue".

    It is suppressed when the outstanding step belongs to the stage on screen,
    because that page already carries a specific instruction for it and a generic
    "Next: Budget analysis." above a budget screen would be noise. What remains
    is the case the pages cannot cover themselves: the user moved on to a later
    stage while an earlier one went stale — the report is now built on an old
    estimate — and nothing else on the screen says so.
    """

    stage_steps: tuple[WorkflowStep, ...] = ()
    for name, steps in STAGES:
        if name == current_stage:
            stage_steps = steps
            break

    step = state.next_step
    if step is None or step in stage_steps or step is WorkflowStep.FINAL_RESULT:
        return ""
    return f"Next: {STEP_LABELS[step]}."


def stage_strip(current_stage: str, state: WorkflowState) -> str:
    """The strip markup. Each stage names its own state in words, not colour."""

    items = []
    for status in stage_statuses(state, current_stage):
        css = {
            "complete": "hm-stage hm-stage--complete",
            "current": "hm-stage hm-stage--current",
            "pending": "hm-stage",
            "unavailable": "hm-stage",
        }[status.state]
        items.append(
            f'<li class="{css}">'
            f'<span class="hm-stage-name">{theme.escape(status.name)}</span>'
            f'<span class="hm-stage-state">{theme.escape(status.label)}</span>'
            "</li>"
        )
    return f'<ul class="hm-stage-strip">{"".join(items)}</ul>'


def render_shell_header(state: WorkflowState, current_stage: str) -> None:
    """Brand line, stage strip and — only when it says something new — the next
    outstanding action.

    The bar reports *stages* complete, matching the strip beneath it and the
    ``Stage n of 5`` eyebrow on the page. It used to report internal steps
    ("0 of 10 steps complete") while the pages numbered themselves differently
    again, so one screen showed three different progress counts.
    """

    statuses = stage_statuses(state, current_stage)
    done = sum(1 for status in statuses if status.state == "complete")
    total = len(STAGES)
    theme.html_block(
        theme.brand_bar(f"{done} of {total} stages complete")
        + stage_strip(current_stage, state)
    )

    hint = next_action_hint(state, current_stage)
    if hint:
        theme.html_block(theme.call_note(hint))


def render_flash() -> None:
    """Show the message queued by the previous action, once.

    ``take_flash`` pops the value, so a widget interaction that triggers an
    unrelated rerun does not repeat an old confirmation.
    """

    import streamlit as st

    from ui import session

    message = session.take_flash()
    if not message:
        return
    tone = message.get("tone", "info")
    text = message.get("message", "")
    if tone == "success":
        st.success(text)
    elif tone == "warning":
        st.warning(text)
    elif tone == "error":
        st.error(text)
    else:
        st.info(text)


def render_issues(issues: tuple) -> None:
    """Show every blocking message at once, without a traceback."""

    import streamlit as st

    if not issues:
        return
    problem_count = (
        "1 problem needs attention:"
        if len(issues) == 1
        else f"{len(issues)} problems need attention:"
    )
    st.error(f"Nothing was saved. {problem_count}")
    for issue in issues:
        st.markdown(f"- {issue.message}")


def render_warnings(warnings: tuple[str, ...]) -> None:
    import streamlit as st

    for warning in warnings:
        st.warning(warning)


def step_name(step: WorkflowStep) -> str:
    """The workflow's own label, so the interface never renames a step."""

    return STEP_LABELS[step]


__all__ = [
    "AVAILABLE_STAGES",
    "STAGES",
    "StageStatus",
    "next_action_hint",
    "render_flash",
    "render_issues",
    "render_shell_header",
    "render_warnings",
    "stage_eyebrow",
    "stage_position",
    "stage_statuses",
    "stage_strip",
    "step_name",
]
