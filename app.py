"""Hometsy — Room Intelligence Studio.

Application entry point. This file owns the page configuration and decides which
screen to draw; the screens themselves live in ``ui.pages_*`` and the project
data lives in ``workflow``.

No geometry, AI, budget or PDF logic belongs in this layer. In particular this
module never imports ``ai``. The AI-backed screens reach the model through
``ui.ai_actions``, which imports ``ai`` inside its functions, so the model layer
is loaded only at the moment a user presses a button. A session that never
presses one never loads it.
"""

from __future__ import annotations

import streamlit as st

from ui import (
    pages_brief,
    pages_budget,
    pages_concepts,
    pages_evaluation,
    pages_landing,
    pages_plan,
    pages_preferences,
    pages_report,
    pages_review,
    pages_room,
    session,
    theme,
)

#: The landing page shows the full brand lockup; the workflow uses the compact
#: treatment (DESIGN_SYSTEM.md §2), so the page title changes with context.
LANDING_TITLE = "Hometsy — Room Intelligence Studio"
WORKFLOW_TITLE = "Hometsy · Room Setup"

_SCREENS = {
    session.SCREEN_ROOM: pages_room.render,
    session.SCREEN_PREFERENCES: pages_preferences.render,
    session.SCREEN_REVIEW: pages_review.render,
    session.SCREEN_BRIEF: pages_brief.render,
    session.SCREEN_CONCEPTS: pages_concepts.render,
    session.SCREEN_PLAN: pages_plan.render,
    session.SCREEN_EVALUATION: pages_evaluation.render,
    session.SCREEN_BUDGET: pages_budget.render,
    session.SCREEN_REPORT: pages_report.render,
}


def _render_workflow() -> None:
    screen = session.current_screen()
    renderer = _SCREENS.get(screen, pages_room.render)
    renderer()

    if st.sidebar.button("Back to overview"):
        session.leave_workflow()
        st.rerun()
    if st.sidebar.button("Start a new project"):
        session.reset_workflow()
        session.set_flash("Project cleared. Describe a new room to begin.", tone="info")
        st.rerun()


def main() -> None:
    in_workflow = session.has_entered()

    st.set_page_config(
        page_title=WORKFLOW_TITLE if in_workflow else LANDING_TITLE,
        page_icon="🏠",
        layout="wide",
        initial_sidebar_state="collapsed" if not in_workflow else "auto",
    )
    theme.inject_css()

    if in_workflow:
        _render_workflow()
    else:
        pages_landing.render()


if __name__ == "__main__":
    main()
