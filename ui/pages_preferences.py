"""The Design Preferences screen.

Three groups in one form: the style, the palette and the requirements, with the
budget alongside. Style and palette are chosen from local reference images
(``DESIGN_SYSTEM.md`` §6.4), while the requirements and budget stay plain
controls (§6.5).

The cards are rendered as image + text + a selection button inside a fixed-width
container. Streamlit cannot style its own buttons reliably, so selection is
communicated twice: by a "Selected" badge in the card, and by the button's label
changing to "Selected". Neither relies on colour alone.
"""

from __future__ import annotations

from models.schemas import DesignStyle, PaletteDirection

from ui import commits, references, session, theme
from ui.shell import (
    render_flash,
    render_issues,
    render_shell_header,
    render_warnings,
    stage_eyebrow,
)

#: The style and palette cards are fixed-width so the images keep one consistent
#: presentation even though the source assets have mixed aspect ratios.
_CARD_WIDTH = 208

#: Sensible starting amount for the budget field. Not a recommendation, just a
#: number that is obviously editable.
_DEFAULT_BUDGET = 45000.0
_MAX_BUDGET = 10_000_000.0


def _seed_form() -> None:
    preferences = session.stored_preferences()
    requirements = session.stored_requirements()
    budget = session.stored_budget()

    session.seed("style", preferences.style if preferences else DesignStyle.JAPANDI)
    session.seed(
        "palette",
        preferences.palette if preferences else PaletteDirection.WARM_NEUTRAL,
    )
    session.seed(
        "materials",
        list(preferences.material_preferences) if preferences else [],
    )
    session.seed(
        "requirements",
        list(requirements.functional_requirements) if requirements else [],
    )
    session.seed("notes", requirements.notes if requirements else "")
    session.seed(
        "budget",
        float(budget.total_budget) if budget else _DEFAULT_BUDGET,
    )


def _reference_card(
    *,
    card_key: str,
    image_path,
    name: str,
    description: str,
    selected: bool,
    swatches: tuple[str, ...] = (),
) -> bool:
    """Draw one reference card and report whether its button was pressed."""

    import streamlit as st

    with st.container(key=card_key, width=_CARD_WIDTH, border=True):
        # The image is illustrative, not informative: its meaning is the name and
        # description printed below it. ``alt`` still has to say that in words,
        # or a screen reader announces an unlabelled graphic.
        st.image(
            str(image_path),
            width="stretch",
            alt=f"Illustrative reference image for the {name} direction.",
        )
        if selected:
            theme.html_block(theme.selected_badge())
        swatch_html = ""
        if swatches:
            spans = "".join(
                f'<span class="hm-swatch" style="background:{theme.escape(colour)}">'
                "</span>"
                for colour in swatches
            )
            swatch_html = f'<div class="hm-swatches">{spans}</div>'
        theme.html_block(
            theme.card_name(name)
            + f'<p class="hm-card-copy">{theme.escape(description)}</p>'
            + f"{swatch_html}"
        )
        label = "Selected" if selected else "Choose"
        return st.button(
            label,
            key=session.widget_key(card_key),
            type="primary" if selected else "secondary",
            width="stretch",
        )


def _render_style_cards(current: DesignStyle) -> DesignStyle | None:
    """All six style cards; returns the newly clicked style, if any."""

    import streamlit as st

    library = references.load_references()
    chosen: DesignStyle | None = None

    with st.container(horizontal=True, wrap=True, gap="small"):
        for reference in library.styles:
            pressed = _reference_card(
                card_key=f"style-{reference.style.name.lower()}",
                image_path=reference.image_path,
                name=reference.name,
                description=reference.description,
                selected=reference.style is current,
            )
            if pressed and reference.style is not current:
                chosen = reference.style
    return chosen


def _render_palette_cards(current: PaletteDirection) -> PaletteDirection | None:
    import streamlit as st

    library = references.load_references()
    chosen: PaletteDirection | None = None

    with st.container(horizontal=True, wrap=True, gap="small"):
        for reference in library.palettes:
            pressed = _reference_card(
                card_key=f"palette-{reference.palette.name.lower()}",
                image_path=reference.image_path,
                name=reference.name,
                description=reference.description,
                selected=reference.palette is current,
                swatches=reference.swatches,
            )
            if pressed and reference.palette is not current:
                chosen = reference.palette
    return chosen


def render() -> None:
    """Draw the preferences screen."""

    import streamlit as st

    state = session.get_workflow()
    if state.room is None:
        # Reachable only if the session was edited by hand or the screen order
        # changed; the workflow refuses the write anyway, so send the user back
        # rather than showing a form that cannot be saved.
        session.set_flash(
            "Describe the room before choosing preferences.", tone="warning"
        )
        session.go_to(session.SCREEN_ROOM)
        return

    render_shell_header(state, "Design Preferences")
    render_flash()

    theme.html_block(
        theme.page_intro(
            stage_eyebrow("Design Preferences") + " · Inputs",
            "Choose a direction",
            "Pick one style and one palette from the approved library, describe "
            "what the room has to do for you, and set the budget you want to "
            "work within. The reference images are illustrative; they are not "
            "analysed by the AI.",
        )
    )

    _seed_form()

    style = st.session_state[session.widget_key("style")]
    palette = st.session_state[session.widget_key("palette")]

    theme.html_block(
        theme.group_heading(
            "Design style",
            "Six approved styles. Your choice is passed to the AI as a text "
            "preference.",
        )
    )
    clicked_style = _render_style_cards(style)
    if clicked_style is not None:
        # Selection is applied immediately and the screen redraws, so the badge
        # and the button label agree on the very next frame.
        st.session_state[session.widget_key("style")] = clicked_style
        st.rerun()

    theme.html_block(
        theme.group_heading(
            "Colour palette",
            "Four approved palette and material directions.",
        )
    )
    clicked_palette = _render_palette_cards(palette)
    if clicked_palette is not None:
        st.session_state[session.widget_key("palette")] = clicked_palette
        st.rerun()

    with st.form("hm_preferences_form", clear_on_submit=False):
        theme.html_block(
            theme.group_heading(
                "Material preferences",
                "Optional. Separate entries with Enter; these are notes for the "
                "brief, not a catalog selection.",
            )
        )
        st.multiselect(
            "Material preferences",
            options=[],
            accept_new_options=True,
            max_selections=10,
            key=session.widget_key("materials"),
            placeholder="e.g. pale oak, linen, brushed brass",
            label_visibility="collapsed",
        )

        theme.html_block(
            theme.group_heading(
                "Functional requirements",
                "What must this room do? Add each requirement separately.",
            )
        )
        st.multiselect(
            "Functional requirements",
            options=[],
            accept_new_options=True,
            max_selections=20,
            key=session.widget_key("requirements"),
            placeholder="e.g. seating for four, a reading corner, storage for books",
            label_visibility="collapsed",
        )

        theme.html_block(theme.group_heading("Additional notes", "Optional."))
        st.text_area(
            "Additional notes",
            key=session.widget_key("notes"),
            max_chars=2000,
            height=110,
            placeholder=(
                "Anything a designer should know about light, use or constraints."
            ),
            label_visibility="collapsed",
        )

        theme.html_block(
            theme.group_heading(
                "Budget",
                "The total you want to stay within. Catalog prices are "
                "illustrative estimates, not verified market prices.",
            )
        )
        st.number_input(
            "Total budget",
            min_value=0.0,
            max_value=_MAX_BUDGET,
            step=1000.0,
            format="%.2f",
            key=session.widget_key("budget"),
            help="Amount in Turkish lira (TRY).",
        )
        theme.html_block(
            '<p class="hm-field-note">Currency: TRY. This is the only currency '
            "supported in V1.</p>"
        )

        submitted = st.form_submit_button(
            "Save preferences and budget", type="primary"
        )

    if not submitted:
        return

    style = st.session_state[session.widget_key("style")]
    palette = st.session_state[session.widget_key("palette")]

    preferences_outcome = commits.build_preferences(
        style=style,
        palette=palette,
        material_preferences=st.session_state[session.widget_key("materials")],
    )
    requirements_outcome = commits.build_requirements(
        functional_requirements=st.session_state[session.widget_key("requirements")],
        notes=st.session_state[session.widget_key("notes")],
    )
    budget_outcome = commits.build_budget(
        st.session_state[session.widget_key("budget")]
    )

    outcomes = (preferences_outcome, requirements_outcome, budget_outcome)
    issues = tuple(issue for outcome in outcomes for issue in outcome.issues)
    if issues or any(outcome.value is None for outcome in outcomes):
        render_issues(issues)
        render_warnings(
            tuple(warning for outcome in outcomes for warning in outcome.warnings)
        )
        return

    preferences = preferences_outcome.value
    requirements = requirements_outcome.value
    budget = budget_outcome.value
    if preferences is None or requirements is None or budget is None:
        # Unreachable: the guard above already returned when any outcome failed.
        render_issues(issues)  # pragma: no cover
        return

    # Snapshot what exists before the three writes, for the same reason as the
    # room screen: the flash should describe a real loss, not a rule table.
    before = session.present_keys(state)

    dropped: list = []
    dropped.extend(state.set_preferences(preferences))
    dropped.extend(state.set_requirements(requirements))
    dropped.extend(state.set_budget(budget))

    unique_dropped = tuple(dict.fromkeys(dropped))
    message = session.invalidation_message(unique_dropped, previously_present=before)
    if message:
        session.set_flash(message, tone="info")
    else:
        session.set_flash(
            "Preferences, requirements and budget saved.", tone="success"
        )

    # Advisory findings are deliberately not stored here. ``validate_inputs``
    # recomputes them on the review screen from the stored models, so there is
    # one authoritative list instead of a snapshot that can go stale.
    session.go_to(session.SCREEN_REVIEW)


__all__ = ["render"]
