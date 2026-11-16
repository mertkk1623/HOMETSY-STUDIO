"""The Design Concepts screen: AI operation 2 and the user's selection.

Layout
------
Three cards in one row on a wide window, stacking on a narrow one, so the three
alternatives can be read against each other (``DESIGN_SYSTEM.md`` §6.6).

Visual references
-----------------
The style reference image is *the user's own chosen style*, shown once above the
cards with a caption that says exactly what it is. It is never repeated per card
and never presented as an illustration of an individual AI concept: the model
produced text, not images, and the card copy must not imply otherwise. Palette
swatches work the same way — they are the approved palette's colours, not a claim
about the concept.

Selection
---------
One concept only, stored through ``WorkflowState.select_concept``, which refuses
anything that is not a member of the current collection. Selection is signalled
twice — a "Selected" badge and a disabled button reading "Selected" — so it never
depends on colour.
"""

from __future__ import annotations

from models.schemas import DesignConcept
from workflow.state import WorkflowStep

from ui import ai_actions, references, session, theme
from ui.shell import render_flash, render_shell_header, stage_eyebrow

_CALL_NOTE = (
    "Generating concepts sends the saved input and the brief to the AI model "
    "once. You will get exactly three concepts to compare. No furniture is "
    "chosen and no price is calculated at this step."
)

_REGENERATE_NOTE = (
    "Generating again replaces the three concepts and clears your selection, "
    "because the previous choice no longer belongs to the new set."
)

_REFERENCE_NOTE = (
    "Your chosen style and palette, as reference. These images are part of the "
    "local reference library: they are not generated for these concepts, are "
    "not shown to the AI, and do not depict them."
)


def _reference_strip(state) -> None:
    """The style image plus palette swatches, captioned as references."""

    import streamlit as st

    library = references.load_references()
    assert state.preferences is not None
    style_image = library.image_for_style(state.preferences.style)
    palette = next(
        (
            reference
            for reference in library.palettes
            if reference.palette is state.preferences.palette
        ),
        None,
    )

    with st.container(border=True):
        image_col, copy_col = st.columns([1, 2], gap="large")
        with image_col:
            if style_image is not None:
                st.image(
                    str(style_image),
                    width="stretch",
                    alt=(
                        "Illustrative reference image for the "
                        f"{state.preferences.style.value} style."
                    ),
                )
        with copy_col:
            swatch_html = ""
            if palette is not None:
                spans = "".join(
                    f'<span class="hm-swatch" style="background:'
                    f'{theme.escape(colour)}"></span>'
                    for colour in palette.swatches
                )
                swatch_html = f'<div class="hm-swatches">{spans}</div>'
            theme.html_block(
                theme.block_title("Style reference", level=2)
                + theme.paragraph(
                    f"{state.preferences.style.value} · "
                    f"{state.preferences.palette.value}"
                )
                + f"{swatch_html}"
                + theme.reference_caption(_REFERENCE_NOTE)
            )


def _concept_card(
    concept: DesignConcept,
    *,
    index: int,
    selected: bool,
) -> bool:
    """Draw one concept and report whether its select button was pressed.

    Only fields that exist on ``DesignConcept`` are shown. There is no invented
    "style characteristics" field: style is already fixed by the user's
    preference, and the model's own words live in the fields below.
    """

    import streamlit as st

    with st.container(key=f"hm-concept-{index}", border=True):
        if selected:
            theme.html_block(theme.selected_badge())
        # The description leads: it is the one field that states the whole
        # proposition in a sentence, and the three cards are read side by side.
        # The remaining fields are supporting detail at label size, so the eye
        # can compare three descriptions before it descends into any of them.
        theme.html_block(
            theme.card_name(concept.name)
            + theme.concept_field("Description", concept.description, lead=True)
            + theme.concept_field("Design direction", concept.design_direction)
            + theme.concept_field(
                "Colour and material direction", concept.color_and_material_direction
            )
            + theme.concept_field("Furniture approach", concept.furniture_approach)
            + theme.concept_field(
                "Functional rationale", concept.functional_rationale
            )
            + theme.concept_field("Budget suitability", concept.budget_suitability)
        )
        if selected:
            # A disabled button, not a hidden one: the action is present and
            # visibly complete, so the user is not left wondering where it went.
            st.button(
                "Selected",
                key=session.widget_key(f"select-{index}"),
                type="primary",
                width="stretch",
                disabled=True,
            )
            return False
        return st.button(
            "Select this concept",
            key=session.widget_key(f"select-{index}"),
            width="stretch",
        )


def render() -> None:
    """Draw the concepts screen."""

    import streamlit as st

    state = session.get_workflow()
    if state.room is None or state.preferences is None:
        session.set_flash(
            "Save the room and the design preferences first.", tone="warning"
        )
        session.go_to(session.SCREEN_ROOM)
        return

    if not state.is_complete(WorkflowStep.BRIEF_ANALYSIS):
        # A concept set can only come from a current brief. Send the user to the
        # screen that can produce one rather than offering a button that would
        # be refused by the workflow's own guard.
        session.set_flash(
            "Analyse a current design brief before generating concepts.",
            tone="warning",
        )
        session.go_to(session.SCREEN_BRIEF)
        return

    render_shell_header(state, "Design Concepts")
    render_flash()

    theme.html_block(
        theme.page_intro(
            stage_eyebrow("Design Concepts") + " · Concepts",
            "Compare three directions",
            "Three concepts written from your brief. They share your chosen "
            "style and palette but organise the room differently. Read them "
            "against each other, then pick the one you want to develop.",
        )
    )

    _reference_strip(state)

    has_concepts = state.concepts is not None
    concepts_current = state.is_complete(WorkflowStep.CONCEPT_GENERATION)

    theme.html_block(theme.group_heading("Concepts"))
    if concepts_current and state.concepts is not None:
        selected = state.selected_concept
        # The row is a keyed container so the stylesheet can equalise the three
        # cards through a hook this application mints, rather than by guessing at
        # Streamlit's column classes. Aligning the buttons to one baseline is a
        # layout fix only: every card still renders its whole concept text.
        with st.container(key="hm-concepts-row"):
            columns = st.columns(len(state.concepts.concepts), gap="medium")
            chosen: DesignConcept | None = None
            for index, (column, concept) in enumerate(
                zip(columns, state.concepts.concepts)
            ):
                with column:
                    is_selected = (
                        selected is not None and selected.name == concept.name
                    )
                    if _concept_card(concept, index=index, selected=is_selected):
                        chosen = concept
        if chosen is not None:
            _select(state, chosen)
        if selected is not None:
            theme.html_block(
                theme.success_badge("Concept selected")
                + theme.field_note(
                    f"'{selected.name}' is stored as your choice. Changing it "
                    "clears the design plan results that were derived from the "
                    "previous concept."
                )
                + theme.field_note(
                    "A concept describes a direction in words. Where it names a "
                    "wall for a piece, that wall is passed to the layout engine "
                    "as a preference, but the exact position is still calculated "
                    "from the furniture's real dimensions, and a wall that cannot "
                    "work is reported rather than forced."
                )
            )
    elif has_concepts:
        theme.html_block(
            theme.quiet_badge("Out of date")
            + '<p class="hm-field-note">Concepts are stored, but the brief they '
            "were generated from has since changed, so they are not shown as "
            "current. Generate again to replace them.</p>"
        )
    else:
        theme.html_block(
            '<p class="hm-card-copy">No concepts have been generated yet.</p>'
        )

    theme.html_block(theme.call_note(_CALL_NOTE))
    label = "Generate concepts again" if has_concepts else "Generate three concepts"
    if has_concepts:
        theme.html_block(theme.field_note(_REGENERATE_NOTE))
    # One primary action per screen: once a concept set exists, generating again
    # replaces it, so it is a repeat action rather than the way forward. It used
    # to render as a primary button directly above the primary "Continue to the
    # design plan", leaving two equally weighted actions stacked on one another.
    if st.button(
        label,
        type="secondary" if has_concepts else "primary",
        width="stretch",
    ):
        _run_generation(state)

    _render_navigation(state)


def _select(state, concept: DesignConcept) -> None:
    """Store the choice and explain what it cleared, then redraw."""

    import streamlit as st

    before = session.present_keys(state)
    dropped = state.select_concept(concept)
    message = session.invalidation_message(dropped, previously_present=before)
    if message:
        session.set_flash(message, tone="info")
    else:
        session.set_flash(f"'{concept.name}' selected.", tone="success")
    st.rerun()


def _run_generation(state) -> None:
    """Perform exactly one request, then rerun. Failures never store a result."""

    import streamlit as st

    from workflow.state import StepFailed

    assert state.room is not None
    assert state.preferences is not None
    assert state.requirements is not None
    assert state.budget is not None
    assert state.brief is not None

    with st.spinner(
        "Writing three concepts from your brief. This sends one request and "
        "usually takes ten to twenty seconds."
    ):
        try:
            state.attempt(
                WorkflowStep.CONCEPT_GENERATION,
                lambda: ai_actions.generate_concepts(
                    room=state.room,
                    preferences=state.preferences,
                    requirements=state.requirements,
                    budget=state.budget,
                    brief=state.brief,
                ),
                state.record_concepts,
            )
        except StepFailed as failure:
            session.set_flash(ai_actions.failure_message(failure.cause), tone="error")
            st.rerun()
            return
        except Exception as unexpected:  # noqa: BLE001 - never a traceback on screen
            session.set_flash(ai_actions.failure_message(unexpected), tone="error")
            st.rerun()
            return

    session.set_flash("Three concepts are ready to compare.", tone="success")
    st.rerun()


def _render_navigation(state) -> None:
    """Back to the brief, or on to the plan once a concept is selected."""

    import streamlit as st

    selected = state.is_complete(WorkflowStep.CONCEPT_SELECTION)
    forward, back, restart = st.columns([2, 1, 1], gap="small")
    with forward:
        if selected:
            if st.button(
                "Continue to the design plan", type="primary", width="stretch"
            ):
                session.go_to(session.SCREEN_PLAN)
        else:
            theme.html_block(
                theme.field_note(
                    "Select one of the three concepts before moving on."
                )
            )
    with back:
        if st.button("Back to the brief", width="stretch"):
            session.go_to(session.SCREEN_BRIEF)
    with restart:
        if st.button("Start a new project", width="stretch"):
            session.reset_workflow()
            session.set_flash(
                "Project cleared. Describe a new room to begin.", tone="info"
            )
            session.go_to(session.SCREEN_ROOM)


__all__ = ["render"]
