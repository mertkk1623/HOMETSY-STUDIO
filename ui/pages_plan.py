"""The Design Plan screen: AI operation 3, the layout, and its validation.

This screen does three things in a fixed order, and the order is visible to the
user because the two halves answer different questions:

1. **The advisor** (AI, one request, button only) chooses *which* catalog items
   suit the selected concept and *why*. It never supplies a coordinate, a price
   or a dimension: identifiers are checked against the local catalog by Python
   and the basket is priced by ``core.budget_engine``.
2. **The placement** (deterministic, no network) puts the chosen items into the
   room and validates the result with ``core.spatial_engine``. This runs in the
   same click but never calls the model, so the geometry is reproducible from
   the stored basket alone.
3. **The presentation** reports three independent facts separately, because
   conflating them is the mistake this screen exists to avoid:

   * whether the layout is *geometrically valid* (the spatial verdict),
   * whether the engine could place *every* requested item (COMPLETE / PARTIAL
     / FAILED), and
   * how good the layout is by a heuristic *quality score*, which is not a
     geometric claim and never turns a red result green.

A failed AI call stores nothing. A failed placement still stores what the engine
produced, because "we could not place this" is a real, explainable result — and
it is shown as a failure, with no plan and no score.
"""

from __future__ import annotations

from core.spatial_engine import DEFAULT_DOOR_CLEARANCE_CM, DEFAULT_WINDOW_CLEARANCE_CM
from core.validation import validate_catalog_references
from models.schemas import (
    PlacedFootprint,
    PlacementOutcome,
    PlacementStatus,
    SpatialValidation,
)
from workflow.state import WorkflowStep

from ui import (
    ai_actions,
    budget as budget_view,
    diagram,
    layout,
    references,
    session,
    theme,
)
from ui.shell import render_flash, render_shell_header, stage_eyebrow

_CALL_NOTE = (
    "Sending this uses one AI request to choose catalog items for the selected "
    "concept and to describe the materials. The room layout is then calculated "
    "here, in Python, from the catalog's real dimensions — the model is not "
    "asked where anything goes and no price is written by the model."
)

_REGENERATE_NOTE = (
    "Running the advisor again replaces the furniture and the materials, and "
    "recalculates the layout for the new basket. The previous plan is cleared, "
    "because it described a different set of pieces."
)

_MATERIALS_NOTE = (
    "Materials and finishes suggested for this concept. The application has no "
    "price list for materials, so none of them is priced and none is included "
    "in the furniture total. Treat them as a specification, not a quotation."
)

_PLAN_NOTE = (
    "The plan is drawn from the coordinates the placement engine produced and "
    "the spatial engine accepted. It is illustrative and not a construction or "
    "building-code drawing."
)

_SCORE_NOTE = (
    "A heuristic quality figure out of 1.00, built from wall contact, doorway "
    "approach, window clearance and free floor. It is not a geometric verdict "
    "and not an aesthetic judgement: a layout can be perfectly valid and still "
    "score low."
)


# --------------------------------------------------------------------------- #
# Small formatting helpers
# --------------------------------------------------------------------------- #


def _format_score(score: float | None) -> str:
    return "—" if score is None else f"{score:.2f}"


def _format_dimensions(footprint: PlacedFootprint) -> str:
    return f"{footprint.width_cm:g} × {footprint.depth_cm:g} cm"


def _format_position(footprint: PlacedFootprint) -> str:
    return (
        f"x {footprint.left_cm:g}–{footprint.right_cm:g}, "
        f"y {footprint.bottom_cm:g}–{footprint.top_cm:g} cm"
    )


def _status_copy(outcome: PlacementOutcome) -> tuple[str, str]:
    """The badge text and the sentence that explains the status.

    The sentence never softens a failure into a warning or a partial layout into
    a success (§10 of the step brief).
    """

    if outcome.status is PlacementStatus.COMPLETE:
        return (
            "Complete layout",
            f"Every one of the {outcome.requested_count} requested items was "
            "placed and the layout passed the spatial checks.",
        )
    if outcome.status is PlacementStatus.PARTIAL:
        return (
            "Partial layout",
            f"{outcome.placed_count} of {outcome.requested_count} requested "
            "items were placed. The layout below is incomplete: the items "
            "listed as unplaced are not in the room.",
        )
    return (
        "Layout failed",
        "No valid layout could be produced, so there is no plan to show. The "
        "reason is reported below; nothing here should be read as a placed "
        "layout.",
    )


# --------------------------------------------------------------------------- #
# Advisor result
# --------------------------------------------------------------------------- #


def _render_basket(state) -> None:
    """The advisor's furniture choices, with catalog facts, never model facts."""

    catalog = {item.item_id: item for item in references.load_catalog()}
    rows = []
    for recommendation in state.furniture:
        item = catalog.get(recommendation.item_id)
        if item is None:
            # Cannot happen for a stored basket: the advisor refuses to record
            # one with an unknown identifier. Stated rather than skipped.
            rows.append(
                f'<tr><td colspan="4">Unknown catalog item '
                f"'{theme.escape(recommendation.item_id)}'</td></tr>"
            )
            continue
        rows.append(
            "<tr>"
            f'<td>{theme.escape(item.name)}</td>'
            f'<td class="hm-num">{recommendation.quantity}</td>'
            f'<td class="hm-num">{item.width_cm:g} × {item.depth_cm:g} cm</td>'
            f"<td>{theme.escape(recommendation.rationale) or '—'}</td>"
            "</tr>"
        )

    theme.html_block(
        '<table class="hm-table">'
        "<thead><tr><th>Item</th><th>Qty</th><th>Catalog size</th>"
        "<th>Why this piece</th></tr></thead>"
        f'<tbody>{"".join(rows)}</tbody>'
        "</table>"
        + theme.field_note(
            "Sizes and prices come from the local catalog, not from the AI "
            "answer. The quantity is what the advisor asked for; the plan below "
            "shows how many copies could actually be placed."
        )
    )


def _render_narrative(state) -> None:
    """Colour direction and design rationale, escaped."""

    parts = [theme.group_heading("Design direction")]
    if state.color_direction:
        parts.append(theme.concept_field("Colour direction", state.color_direction))
    if state.design_rationale:
        parts.append(
            theme.concept_field("Why these choices", state.design_rationale)
        )
    theme.html_block("".join(parts))


def _render_materials(state) -> None:
    """Materials in their own section, explicitly unpriced."""

    theme.html_block(
        theme.group_heading("Materials and finishes")
        + f'<p class="hm-card-copy">{theme.escape(_MATERIALS_NOTE)}</p>'
    )
    if not state.materials:
        theme.html_block(
            '<p class="hm-card-copy">No materials were recommended for this '
            "concept.</p>"
        )
        return

    cards = []
    for material in state.materials:
        scope = (
            f'<p class="hm-field-note">{theme.escape(material.quantity_note)}</p>'
            if material.quantity_note
            else ""
        )
        cards.append(
            '<div class="hm-card">'
            f"{theme.card_heading(material.name)}"
            + theme.quiet_badge(material.category)
            + f'<p class="hm-card-text" style="margin-top:10px;">'
            f"{theme.escape(material.color_direction)}</p>"
            '<p class="hm-card-text" style="margin-top:8px;">'
            f"{theme.escape(material.rationale)}</p>"
            f"{scope}"
            # No price field exists on MaterialRecommendation, and the interface
            # must never invent one, so the absence is stated instead.
            '<p class="hm-field-note">Not priced: materials have no catalog '
            "cost in this application.</p>"
            "</div>"
        )
    theme.html_block("".join(cards))


# --------------------------------------------------------------------------- #
# Layout, validation and score
# --------------------------------------------------------------------------- #


def _render_plan(room, outcome: PlacementOutcome) -> None:
    """Draw the validated layout, or explicitly draw nothing for a failure."""

    if outcome.is_failed:
        theme.html_block(theme.group_heading("Room plan"))
        theme.html_block(
            theme.error_badge("No plan drawn")
            + '<p class="hm-card-copy">A failed placement has no validated '
            "layout, so nothing is drawn. Drawing the rejected candidate would "
            "present furniture that the spatial engine refused.</p>"
        )
        return

    parts = [theme.group_heading("Room plan")]
    if outcome.is_partial:
        parts.append(
            theme.warning_badge("Partial plan")
            + '<p class="hm-card-copy">Only the items the engine placed are '
            "drawn. The unplaced items are listed below and are not in this "
            "room.</p>"
        )
    parts.append(
        # The frame scrolls its drawing sideways on a narrow screen, so it must
        # be reachable and scrollable by keyboard: axe-core flags a scroll
        # container with no focusable content as ``scrollable-region-focusable``,
        # because a keyboard user cannot pan it at all. ``tabindex="0"`` puts it
        # in the tab order and the role names it as the region it is.
        f'<div class="hm-plan-frame" tabindex="0" role="group" '
        f'aria-label="Room plan drawing. Scroll sideways to see the whole plan.">'
        + diagram.placement_plan_svg(
            width_cm=room.width_cm,
            length_cm=room.length_cm,
            door_wall=room.door.wall,
            door_offset_cm=room.door.offset_cm,
            door_width_cm=room.door.width_cm,
            window_wall=room.window.wall,
            window_offset_cm=room.window.offset_cm,
            window_width_cm=room.window.width_cm,
            footprints=outcome.placed,
            partial=outcome.is_partial,
        )
        + "</div>"
        + diagram.plan_legend()
        + theme.field_note(_PLAN_NOTE)
    )
    theme.html_block("".join(parts))


def _render_placement_table(outcome: PlacementOutcome) -> None:
    """Every placed copy, with the coordinates the engine produced."""

    if not outcome.placed:
        return
    rows = "".join(
        "<tr>"
        f"<td>{theme.escape(footprint.label)}</td>"
        f'<td class="hm-num">{_format_dimensions(footprint)}</td>'
        f'<td class="hm-num">{footprint.rotation_degrees}&deg;</td>'
        f'<td class="hm-num">{_format_position(footprint)}</td>'
        "</tr>"
        for footprint in outcome.placed
    )
    theme.html_block(
        theme.group_heading("Placed pieces")
        + '<table class="hm-table">'
        "<thead><tr><th>Item</th><th>Placed size</th><th>Rotation</th>"
        "<th>Position</th></tr></thead>"
        f'<tbody>{rows}</tbody>'
        "</table>"
        + theme.field_note(
            "Placed size is the catalog size after rotation. The position is the "
            "footprint in centimetres, measured from the south-west corner."
        )
    )


def _render_unplaced(outcome: PlacementOutcome) -> None:
    """Unplaced copies, with the engine's own reason for each."""

    import streamlit as st

    if not outcome.unplaced:
        return
    theme.html_block(theme.group_heading("Items that were not placed"))
    for item in outcome.unplaced:
        st.warning(
            f"{item.label} — {item.count} "
            f"{'copy' if item.count == 1 else 'copies'} not placed. "
            f"{item.reason}"
        )
    theme.html_block(
        theme.field_note(
            "These copies do not appear in the plan and are not counted as "
            "placed. They remain in the basket, so the budget still includes "
            "them, because that is what the design asks for."
        )
    )


def _render_validation(
    validation: SpatialValidation, outcome: PlacementOutcome
) -> None:
    """The spatial verdict: blocking problems and warnings, kept apart."""

    import streamlit as st

    theme.html_block(theme.group_heading("Spatial validation"))

    if outcome.is_failed:
        st.error("The layout did not pass spatial validation.")
    elif validation.is_valid:
        st.success("All blocking spatial checks passed for this layout.")
    else:
        # A validated candidate with an error would be a contradiction; report it
        # as the blocking problem it is rather than trusting either half.
        st.error("The stored layout reports blocking spatial problems.")

    blocking = list(validation.boundary_violations) + list(validation.overlaps)
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
                "Warnings do not block the layout. They describe something worth "
                "knowing, such as a piece standing within a window's clearance "
                "band."
            )
        )

    if outcome.notes:
        theme.html_block(
            '<p class="hm-subheading">Placement notes</p>'
            + "".join(
                f'<div class="hm-issue">{theme.escape(note)}</div>'
                for note in outcome.notes
            )
        )


def _render_metrics(outcome: PlacementOutcome, validation: SpatialValidation) -> None:
    """Status, score and counts, each labelled for what it actually means."""

    import streamlit as st

    badge, sentence = _status_copy(outcome)
    badge_html = {
        PlacementStatus.COMPLETE: theme.success_badge(badge),
        PlacementStatus.PARTIAL: theme.warning_badge(badge),
        PlacementStatus.FAILED: theme.error_badge(badge),
    }[outcome.status]

    theme.html_block(
        theme.group_heading("Result")
        + badge_html
        + f'<p class="hm-card-copy">{theme.escape(sentence)}</p>'
    )

    columns = st.columns(3, gap="medium")
    with columns[0]:
        theme.html_block(
            theme.score_line(
                "Layout score",
                _format_score(outcome.score),
                "Quality heuristic, not a validity check.",
            )
        )
    with columns[1]:
        theme.html_block(
            theme.score_line(
                "Items placed",
                f"{outcome.placed_count} / {outcome.requested_count}",
                "Copies, so a quantity of four counts as four.",
            )
        )
    with columns[2]:
        verdict = "Valid" if validation.is_valid else "Not valid"
        theme.html_block(
            theme.score_line(
                "Geometric validity",
                verdict,
                "Decided by the spatial engine, independently of the score.",
            )
        )


def _render_score_terms(outcome: PlacementOutcome) -> None:
    """How the score was built, so the number is not a black box."""

    if not outcome.score_terms:
        return
    rows = "".join(
        "<tr>"
        f"<td>{theme.escape(term.name.replace('_', ' ').capitalize())}</td>"
        f'<td class="hm-num">{term.weight:.2f}</td>'
        f'<td class="hm-num">{term.value:.2f}</td>'
        f'<td class="hm-num">{term.weight * term.value:.2f}</td>'
        "</tr>"
        for term in outcome.score_terms
    )
    theme.html_block(
        theme.group_heading("How the score is built")
        + '<table class="hm-table">'
        "<thead><tr><th>Criterion</th><th>Weight</th><th>Value</th>"
        "<th>Contribution</th></tr></thead>"
        f'<tbody>{rows}</tbody>'
        "</table>"
        + theme.field_note(_SCORE_NOTE)
    )


def _render_clearances(state) -> None:
    """The clearance bands the validation used, stated in centimetres."""

    room = state.room
    assert room is not None
    theme.html_block(
        theme.group_heading("Clearance rules applied")
        + theme.summary(
            [
                (
                    "Door clearance kept free",
                    f"{DEFAULT_DOOR_CLEARANCE_CM:g} cm in front of the "
                    f"{room.door.wall.value} door",
                ),
                (
                    "Window clearance watched",
                    f"{DEFAULT_WINDOW_CLEARANCE_CM:g} cm inside the "
                    f"{room.window.wall.value} window",
                ),
                (
                    "Consequence",
                    "Blocking the doorway is an error; standing in the window "
                    "band is a warning.",
                ),
            ]
        )
        + theme.field_note(
            "These are illustrative V1 values, not building-code or accessibility "
            "requirements."
        )
    )


# --------------------------------------------------------------------------- #
# Running the step
# --------------------------------------------------------------------------- #


def _run_advisor(state) -> None:
    """One AI request, then the deterministic layout, then a rerun.

    The AI half runs inside ``state.attempt`` so a failure can never be stored.
    The placement half then runs with no AI involved: if it raises, the basket
    the advisor just produced stays stored, and the screen reports that the
    layout failed rather than losing the recommendation.
    """

    import streamlit as st

    from workflow.state import StepFailed

    assert state.room is not None
    assert state.preferences is not None
    assert state.budget is not None
    assert state.brief is not None
    assert state.selected_concept is not None

    with st.spinner(
        "Choosing furniture and materials for this concept. This sends one "
        "request; the layout is then calculated here and takes a moment."
    ):
        try:
            advice = state.attempt(
                WorkflowStep.RECOMMENDATIONS,
                lambda: ai_actions.recommend_furniture(
                    room=state.room,
                    preferences=state.preferences,
                    budget=state.budget,
                    brief=state.brief,
                    concept=state.selected_concept,
                ),
                lambda result: state.record_recommendation(result.recommendation),
            )
        except StepFailed as failure:
            session.set_flash(
                ai_actions.failure_message(failure.cause), tone="error"
            )
            st.rerun()
            return
        except Exception as unexpected:  # noqa: BLE001 - never a traceback on screen
            session.set_flash(ai_actions.failure_message(unexpected), tone="error")
            st.rerun()
            return

    check = advice.catalog_check
    if not check.is_valid:
        # The basket is stored so the user can see what was proposed, but it is
        # not presented as usable and no layout is computed from it.
        session.set_flash(
            "The advisor proposed an item that is not in the local catalog, so "
            "the basket cannot be used. Nothing was planned. " + check.messages[0],
            tone="error",
        )
        st.rerun()
        return

    _place_and_store(state)
    session.set_flash(
        "Furniture and materials are ready, and the layout has been calculated.",
        tone="success",
    )
    st.rerun()


def _place_and_store(state) -> None:
    """Run the deterministic placement and record it. No AI, no network.

    Called from the advisor flow and from the screen's own "recalculate" button,
    because placement depends only on the stored basket and the room: a user who
    edits nothing must get the same layout, and a rerun must never need a model.

    The budget estimate is recorded here too, and for the same reason: it is
    deterministic arithmetic over the basket that was just placed. Doing it now
    means the evaluation screen's prerequisites (a spatial result *and* a price)
    are satisfied by the act that produced the plan, so the user is never asked
    to visit a screen just to unlock a button. It writes an ``BudgetAnalysis``
    produced by ``core.budget_engine``; nothing is calculated in the interface.
    """

    assert state.room is not None
    analysis = layout.analyse_layout(
        state.room, state.furniture, references.load_catalog()
    )
    state.record_spatial(
        analysis.validation, analysis.outcome, analysis.placements
    )
    # ``record_spatial`` invalidates the previous price, so the estimate is
    # written after it, from the basket as it now stands.
    state.record_budget_analysis(
        budget_view.compute_estimate(
            state.budget, state.furniture, references.load_catalog()
        ).analysis
    )


def _blocking_basket_findings(state) -> list:
    """Catalog problems that make the stored basket unplannable.

    The check is ``core.validation.validate_catalog_references`` — the same rule
    the advisor applies — so the screen cannot disagree with the layer that
    produced the basket. Only errors are returned: a warning does not stop a
    layout.
    """

    assert state.room is not None
    return [
        finding
        for finding in validate_catalog_references(
            state.room, state.furniture, references.load_catalog()
        )
        if finding.is_error
    ]


# --------------------------------------------------------------------------- #
# Navigation
# --------------------------------------------------------------------------- #


def _render_navigation(state) -> None:
    import streamlit as st

    # Both deterministic results are the evaluation's own prerequisites, so the
    # screen asks the workflow rather than inventing a second rule.
    ready = state.is_complete(WorkflowStep.SPATIAL_VALIDATION) and state.is_complete(
        WorkflowStep.BUDGET_ANALYSIS
    )
    forward, back, restart = st.columns([2, 1, 1], gap="small")
    with forward:
        if ready:
            if st.button(
                "Continue to the design evaluation", type="primary", width="stretch"
            ):
                session.go_to(session.SCREEN_EVALUATION)
        else:
            theme.html_block(
                theme.field_note(
                    "The design evaluation unlocks once the layout and the "
                    "budget estimate are both current."
                )
            )
    with back:
        if st.button("Back to concepts", width="stretch"):
            session.go_to(session.SCREEN_CONCEPTS)
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
    """Draw the design plan screen."""

    import streamlit as st

    state = session.get_workflow()
    if state.room is None or state.preferences is None:
        session.set_flash(
            "Save the room and the design preferences first.", tone="warning"
        )
        session.go_to(session.SCREEN_ROOM)
        return

    if not state.is_complete(WorkflowStep.CONCEPT_SELECTION):
        session.set_flash(
            "Select a design concept before planning the room.", tone="warning"
        )
        session.go_to(session.SCREEN_CONCEPTS)
        return

    render_shell_header(state, "Design Plan")
    render_flash()

    theme.html_block(
        theme.page_intro(
            stage_eyebrow("Design Plan") + " · Furniture and layout",
            "Furniture, layout and validation",
            "The advisor chooses catalog pieces for your selected concept, and "
            "Python places them in the room and checks the result. The plan, the "
            "score and the validation below all come from real catalog "
            "dimensions and the room you measured.",
        )
    )

    has_basket = bool(state.furniture)
    basket_problems = _blocking_basket_findings(state) if has_basket else []
    # A stored basket is only plannable when every reference resolves. Without
    # this the screen could say "nothing was planned" and offer to plan it.
    plan_current = (
        state.is_complete(WorkflowStep.RECOMMENDATIONS)
        and not basket_problems
        and state.placement is not None
    )

    # --- The deterministic half ----------------------------------------- #
    #
    # Order is deliberate: the screen exists to answer "does this room work?",
    # so once a layout exists the answer, the drawing, the coordinates and the
    # verdict are read *before* the furniture table and the six material cards
    # that produced them. Reading them the other way round buried the result
    # roughly 2,800 px down the page — past every material — which is the exact
    # failure DESIGN_SYSTEM.md §6.7 warns about ("Spatial warnings should be
    # easy to distinguish from informational notes").
    if plan_current:
        outcome = state.placement
        validation = state.spatial
        assert outcome is not None and validation is not None

        _render_metrics(outcome, validation)
        _render_plan(state.room, outcome)
        _render_placement_table(outcome)
        _render_unplaced(outcome)
        _render_validation(validation, outcome)
        _render_score_terms(outcome)
        _render_clearances(state)

        if outcome.is_complete or outcome.is_partial:
            if st.button("Recalculate the layout", width="stretch"):
                _place_and_store(state)
                session.set_flash(
                    "The layout has been recalculated from the current basket.",
                    tone="info",
                )
                st.rerun()
    elif has_basket and state.placement is None and not basket_problems:
        theme.html_block(
            theme.group_heading("Room plan")
            + '<p class="hm-card-copy">The layout has not been calculated '
            "yet. Recalculate it from the stored basket, or run the advisor "
            "again.</p>"
        )
        if st.button("Calculate the layout", width="stretch"):
            _place_and_store(state)
            st.rerun()

    # --- The advisor, as the supporting detail --------------------------- #
    _render_basket_block(state, has_basket, basket_problems, plan_current)
    _render_materials(state)

    theme.html_block(theme.call_note(_CALL_NOTE))
    if has_basket:
        theme.html_block(theme.field_note(_REGENERATE_NOTE))
    label = (
        "Run the advisor again"
        if has_basket
        else "Recommend furniture and build the plan"
    )
    # Once a plan exists, running the advisor again replaces the furniture and
    # recalculates, so it is a repeat action, not the way forward. Rendering it
    # as a primary button left it competing with the primary navigation below.
    if st.button(
        label,
        type="secondary" if plan_current else "primary",
        width="stretch",
    ):
        _run_advisor(state)

    _render_navigation(state)


def _render_basket_block(
    state,
    has_basket: bool,
    basket_problems: list,
    plan_current: bool,
) -> None:
    """The advisor's output: what was chosen, and why.

    Kept together in one function because the four states below are one idea —
    "is there a usable basket, and if not, why not" — and splitting them across
    the screen would let the headings drift out of order.
    """

    theme.html_block(theme.group_heading("Furniture and materials"))
    if plan_current:
        _render_narrative(state)
        _render_basket(state)
    elif basket_problems:
        theme.html_block(
            theme.error_badge("Basket cannot be used")
            + '<p class="hm-field-note">The advisor proposed an item this '
            "application cannot place, so no layout was calculated from it. "
            "The request is shown below exactly as it was returned: it has not "
            "been substituted or repaired.</p>"
        )
        _render_basket(state)
        theme.html_block(
            "".join(
                '<div class="hm-issue hm-issue--error">'
                '<span class="hm-issue-kind">Error</span>'
                f"{theme.escape(finding.message)}</div>"
                for finding in basket_problems
            )
        )
    elif has_basket:
        theme.html_block(
            theme.quiet_badge("Out of date")
            + '<p class="hm-field-note">A basket is stored, but the concept it '
            "was chosen for has since changed, so it is not shown as current. "
            "Run the advisor again to replace it.</p>"
        )
    else:
        theme.html_block(
            '<p class="hm-card-copy">No furniture has been recommended yet.</p>'
        )


__all__ = ["render"]
