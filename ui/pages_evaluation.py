"""The Design Evaluation screen: AI operation 4, under the user's control.

This screen does not calculate and does not decide. Every figure it shows —
the layout status, the geometric verdict, the blocking problems, the warnings,
the budget position — was produced by Python before the button was pressed, and
it is rendered from the stored objects rather than from the model's prose. The
one thing the model is asked for is the interpretation
(:class:`models.schemas.DesignEvaluation`).

What the screen refuses to do
-----------------------------
* **No evaluation without the facts it interprets.** The button is shown only
  when the spatial result *and* the deterministic budget result exist, which is
  ``WorkflowState``'s own prerequisite list for this step — not a second rule
  invented here.
* **No improvement on a failure.** ``PARTIAL`` and ``FAILED`` layouts are stated
  verbatim next to the AI text, so a model that calls the design "spatially
  applicable" cannot overrule the engine in front of the user.
* **No invented fields.** ``DesignEvaluation`` has four narrative judgements and
  two lists. It has no overall verdict, no score and no strengths list, so none
  is displayed and none is derived.
* **No silent retry.** Streamlit reruns on every interaction; the request is an
  event, so a rerun with no click never reaches the call.
* **No lost result.** The write goes through ``WorkflowState.attempt``, so a
  failed call cannot reach the stored evaluation, and the previous valid one
  stays on screen.
"""

from __future__ import annotations

from typing import Final

from models.schemas import DesignEvaluation, PlacementOutcome, SpatialValidation
from workflow.state import WorkflowStep

from ui import ai_actions, budget as budget_view, commits, references, session, theme
from ui.shell import render_flash, render_shell_header, stage_eyebrow

_CALL_NOTE = (
    "This sends the saved brief, the selected concept, the recommended catalog "
    "items and the results Python has already calculated to the AI model once. "
    "It asks for a written critique only: the model is told not to recalculate a "
    "figure, not to change the layout and not to add a catalog item."
)

_AGAIN_NOTE = (
    "Evaluating again sends the same current data and replaces the stored "
    "evaluation. Nothing else in the project is recalculated: the layout, the "
    "prices and the validation are already finished and are sent unchanged."
)

_OPINION_NOTE = (
    "This is a design opinion, not an engineering approval. It does not certify "
    "structural, ergonomic, accessibility or building-code compliance, and it "
    "cannot make an incomplete layout complete."
)

_SCHEMA_NOTE = (
    "The evaluation model returns four written judgements and two lists. It has "
    "no numeric score and no single overall-verdict field, so none is shown here."
)

_FIELD_LABELS: Final[tuple[tuple[str, str], ...]] = (
    ("requirement_compatibility", "How well the brief is met"),
    ("style_consistency", "Style and concept consistency"),
    ("functional_suitability", "How the room will work in use"),
    ("budget_suitability", "Budget suitability"),
)


# --------------------------------------------------------------------------- #
# The deterministic facts the AI is interpreting
# --------------------------------------------------------------------------- #


def _status_sentence(outcome: PlacementOutcome | None) -> tuple[str, str]:
    """Badge text and one sentence for the placement status.

    The wording is the plan screen's, restated here rather than softened: a
    partial layout is never a success and a failed one is never a plan.
    """

    if outcome is None:
        return ("Layout not recorded", "No placement result is stored.")
    if outcome.is_complete:
        return (
            "Complete layout",
            f"All {outcome.requested_count} requested items were placed and "
            "validated.",
        )
    if outcome.is_partial:
        return (
            "Partial layout",
            f"{outcome.placed_count} of {outcome.requested_count} requested "
            "items were placed. The items listed by the plan screen as unplaced "
            "are not in the room, so this design is only partly buildable.",
        )
    return (
        "Layout failed",
        "No valid layout could be produced. Nothing was placed, so this design "
        "cannot be presented as spatially applicable as it stands.",
    )


def _render_spatial_facts(
    validation: SpatialValidation,
    outcome: PlacementOutcome | None,
) -> None:
    """What the spatial engine decided, before any AI text is read."""

    badge, sentence = _status_sentence(outcome)
    badge_html = (
        theme.success_badge(badge)
        if outcome is not None and outcome.is_complete
        else (
            theme.warning_badge(badge)
            if outcome is not None and outcome.is_partial
            else theme.error_badge(badge)
        )
    )
    blocking = list(validation.boundary_violations) + list(validation.overlaps)

    theme.html_block(
        theme.group_heading("What the spatial engine decided")
        + badge_html
        + f'<p class="hm-card-copy">{theme.escape(sentence)}</p>'
        + theme.summary(
            [
                (
                    "Geometric validity",
                    "Valid" if validation.is_valid else "Not valid",
                ),
                ("Blocking problems", str(len(blocking))),
                ("Warnings", str(len(validation.warnings))),
            ]
        )
    )

    if blocking:
        theme.html_block(
            '<p class="hm-subheading">Blocking problems</p>'
            + "".join(
                '<div class="hm-issue hm-issue--error">'
                '<span class="hm-issue-kind">Error</span>'
                f"{theme.escape(message)}</div>"
                for message in blocking
            )
        )
    if validation.warnings:
        theme.html_block(
            '<p class="hm-subheading">Warnings</p>'
            + "".join(
                '<div class="hm-issue hm-issue--warning">'
                '<span class="hm-issue-kind">Warning</span>'
                f"{theme.escape(message)}</div>"
                for message in validation.warnings
            )
            + theme.field_note(
                "A warning is not a blocking problem. It describes something "
                "worth knowing; it does not stop the layout."
            )
        )


def _render_budget_facts(state, estimate) -> None:
    """The deterministic money position, with its scope stated."""
    analysis = state.budget_analysis
    assert analysis is not None
    currency = analysis.currency
    remaining = analysis.remaining_budget

    rows = [
        (
            "Indicative furniture total",
            commits.format_money(analysis.total_estimated, currency),
        ),
        ("Your budget", commits.format_money(state.budget.total_budget, currency)),
    ]
    if analysis.is_over_budget:
        rows.append(
            (
                "Over budget by",
                commits.format_money(abs(remaining), currency),
            )
        )
    else:
        rows.append(("Remaining budget", commits.format_money(remaining, currency)))

    parts = [
        theme.group_heading("What the budget engine calculated"),
        theme.summary(rows),
    ]

    if estimate is not None and not estimate.is_trustworthy:
        parts.append(
            theme.error_badge("Estimate incomplete")
            + f'<p class="hm-field-note">'
            f"{theme.escape(budget_view.INCOMPLETE_NOTE)}</p>"
        )
        parts.append(
            "".join(
                '<div class="hm-issue hm-issue--error">'
                '<span class="hm-issue-kind">Error</span>'
                f"{theme.escape(error.message)}</div>"
                for error in estimate.errors
            )
        )
        parts.append(
            theme.field_note(
                "The evaluation is told that the total is partial, so it must "
                "not describe the budget position as final."
            )
        )
    else:
        parts.append(theme.field_note(budget_view.MATERIALS_NOTE))

    theme.html_block("".join(parts))


# --------------------------------------------------------------------------- #
# The stored evaluation
# --------------------------------------------------------------------------- #


def _render_evaluation(evaluation: DesignEvaluation) -> None:
    """The model's own fields, exactly as the schema defines them.

    The four judgements are the reading; the two lists qualify it. Rendering
    all six identically let ten bullet points outweigh the four sentences they
    comment on, so the lists sit in one subordinate panel beneath them.
    """

    values = {
        "requirement_compatibility": evaluation.requirement_compatibility,
        "style_consistency": evaluation.style_consistency,
        "functional_suitability": evaluation.functional_suitability,
        "budget_suitability": evaluation.budget_suitability,
    }
    fields = "".join(
        theme.concept_field(label, values[key]) for key, label in _FIELD_LABELS
    )
    theme.html_block(theme.group_heading("Design evaluation") + fields)

    theme.html_block(
        theme.aside(
            "Limitations and risks",
            theme.bullet_list(evaluation.limitations),
        )
        + theme.aside(
            "Improvement suggestions",
            theme.bullet_list(evaluation.recommendations),
        )
        + theme.field_note(_SCHEMA_NOTE)
    )


def _render_previous(state) -> None:
    """The stored evaluation, or an explicit statement that there is none."""

    theme.html_block(theme.group_heading("Saved evaluation"))
    current = (
        state.evaluation
        if state.is_complete(WorkflowStep.DESIGN_EVALUATION)
        else None
    )
    if current is not None:
        _render_evaluation(current)
    else:
        theme.html_block(
            '<p class="hm-card-copy">This design has not been evaluated yet.</p>'
        )


# --------------------------------------------------------------------------- #
# Running the step
# --------------------------------------------------------------------------- #


def _run_evaluation(state, estimate) -> None:
    """One request, recorded only if it succeeds, then a rerun."""

    import streamlit as st

    from workflow.state import StepFailed

    assert state.room is not None
    assert state.preferences is not None
    assert state.budget is not None
    assert state.brief is not None
    assert state.selected_concept is not None
    assert state.spatial is not None
    assert state.budget_analysis is not None

    with st.spinner(
        "Reviewing the design against your brief and the calculated results. "
        "This sends one request and usually takes ten to twenty seconds."
    ):
        try:
            state.attempt(
                WorkflowStep.DESIGN_EVALUATION,
                lambda: ai_actions.evaluate_design(
                    room=state.room,
                    preferences=state.preferences,
                    budget=state.budget,
                    brief=state.brief,
                    concept=state.selected_concept,
                    recommendations=state.furniture,
                    spatial=state.spatial,
                    analysis=state.budget_analysis,
                    budget_is_complete=estimate.is_trustworthy,
                    placement=state.placement,
                    compatibility=state.concept_compatibility,
                ),
                state.record_evaluation,
            )
        except StepFailed as failure:
            session.set_flash(ai_actions.failure_message(failure.cause), tone="error")
            st.rerun()
            return
        except Exception as unexpected:  # noqa: BLE001 - never a traceback on screen
            session.set_flash(ai_actions.failure_message(unexpected), tone="error")
            st.rerun()
            return

    session.set_flash("The design evaluation is ready.", tone="success")
    st.rerun()


# --------------------------------------------------------------------------- #
# Navigation
# --------------------------------------------------------------------------- #


def _render_navigation(state) -> None:
    import streamlit as st

    # The budget estimate is calculated with the layout, so it is already
    # complete when this screen opens — gating the forward button's *emphasis*
    # on it would have shown two primary buttons at once, "Evaluate the design"
    # and "Continue to budget analysis", before any evaluation existed. The
    # emphasis follows this screen's own step instead; the button itself still
    # appears as soon as the budget is there, because skipping the evaluation
    # is a legitimate route.
    ready_for_budget = state.is_complete(WorkflowStep.BUDGET_ANALYSIS)
    evaluated = state.is_complete(WorkflowStep.DESIGN_EVALUATION)
    forward, back, restart = st.columns([2, 1, 1], gap="small")
    with forward:
        if ready_for_budget:
            if st.button(
                "Continue to budget analysis",
                type="primary" if evaluated else "secondary",
                width="stretch",
            ):
                session.go_to(session.SCREEN_BUDGET)
        else:
            theme.html_block(
                theme.field_note(
                    "The budget analysis unlocks once a current estimate exists."
                )
            )
    with back:
        if st.button("Back to the plan", width="stretch"):
            session.go_to(session.SCREEN_PLAN)
    with restart:
        if st.button("Start a new project", width="stretch"):
            session.reset_workflow()
            session.set_flash(
                "Project cleared. Describe a new room to begin.", tone="info"
            )
            session.go_to(session.SCREEN_ROOM)


# --------------------------------------------------------------------------- #
# The screen
# --------------------------------------------------------------------------- #


def render() -> None:
    """Draw the design evaluation screen."""

    import streamlit as st

    state = session.get_workflow()
    if state.room is None or state.preferences is None:
        session.set_flash(
            "Save the room and the design preferences first.", tone="warning"
        )
        session.go_to(session.SCREEN_ROOM)
        return

    if not state.is_complete(WorkflowStep.RECOMMENDATIONS):
        session.set_flash(
            "Recommend furniture and build the plan before evaluating it.",
            tone="warning",
        )
        session.go_to(session.SCREEN_PLAN)
        return

    if state.placement is None or state.spatial is None:
        session.set_flash(
            "Calculate and validate the layout before evaluating the design.",
            tone="warning",
        )
        session.go_to(session.SCREEN_PLAN)
        return

    if state.budget_analysis is None:
        session.set_flash(
            "The budget estimate is calculated with the layout; recalculate the "
            "layout on the plan screen before evaluating the design.",
            tone="warning",
        )
        session.go_to(session.SCREEN_PLAN)
        return

    render_shell_header(state, "Design Plan")
    render_flash()

    theme.html_block(
        theme.page_intro(
            stage_eyebrow("Design Plan") + " · Evaluation",
            "Evaluate the design",
            "The AI reads the brief, the selected concept, the recommended "
            "catalog items and the results Python has already calculated, and "
            "writes a critique of them. The layout, the prices and the spatial "
            "verdict below come from the application and are not changed by the "
            "answer.",
        )
    )

    assert state.brief is not None
    assert state.budget_analysis is not None
    assert state.selected_concept is not None
    assert state.placement is not None
    estimate = budget_view.compute_estimate(
        state.budget, state.furniture, references.load_catalog()
    )

    theme.html_block(theme.group_heading("What will be evaluated"))
    theme.html_block(
        theme.summary(
            [
                ("Room", f"{state.room.name} · {state.room.area_sqm:.2f} m²"),
                ("Concept", state.selected_concept.name),
                ("Catalog items", str(len(state.furniture))),
                (
                    "Layout",
                    f"{state.placement.placed_count} of "
                    f"{state.placement.requested_count} placed",
                ),
                (
                    "Indicative total",
                    commits.format_money(
                        state.budget_analysis.total_estimated,
                        state.budget_analysis.currency,
                    ),
                ),
            ]
        )
    )

    _render_spatial_facts(state.spatial, state.placement)
    _render_budget_facts(state, estimate)
    _render_previous(state)

    has_evaluation = state.is_complete(WorkflowStep.DESIGN_EVALUATION)
    theme.html_block(theme.call_note(_CALL_NOTE))
    if has_evaluation:
        theme.html_block(theme.field_note(_AGAIN_NOTE))

    if st.button(
        "Evaluate the design again" if has_evaluation else "Evaluate the design",
        type="secondary" if has_evaluation else "primary",
        width="stretch",
    ):
        _run_evaluation(state, estimate)

    theme.html_block(theme.field_note(_OPINION_NOTE))
    _render_navigation(state)


__all__ = ["render"]
