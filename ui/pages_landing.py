"""The landing page.

The primary action enters the workflow rather than announcing that room setup
does not exist yet; that sentence was true in Phase 1 and is not true now, and
``AGENTS.md`` §10 forbids presenting planned features as implemented — or
implemented ones as planned.

The hero's flow line names the same five stages the workflow shell shows, in the
same order and the same words (``ui.shell.STAGES``). A landing page that
advertises a different journey from the one the product walks is the first place
a reader can catch the two disagreeing.
"""

from __future__ import annotations

from ui import session, theme
from ui.shell import STAGES

APP_TITLE = "HOMETSY — ROOM INTELLIGENCE STUDIO"
APP_TAGLINE = "AI-assisted interior design and spatial planning"
SHORT_INTRO = (
    "Turn a few room measurements, a design direction and a budget into a "
    "structured interior design proposal: analysed requirements, three design "
    "concepts, furniture recommendations, a dimensioned 2D plan and a "
    "professional PDF report."
)

#: The hero photograph's alt text. It describes the room in words, because the
#: picture is the only thing on the page a screen reader cannot reach by itself.
#: It deliberately says nothing about the AI: the model never receives this file
#: (``DESIGN_SYSTEM.md`` §9), and alt text is the easiest place to imply
#: otherwise by accident.
HERO_IMAGE_ALT = (
    "An illustrative living room in a warm Japandi style: a pale corner sofa "
    "with olive and terracotta cushions, a round travertine coffee table holding "
    "a vase of olive branches, and a tall arched floor lamp beside a window."
)

#: The visible caption. It states the same thing the alt text cannot: that this
#: is a picture of the *kind* of room the product plans, not a generated concept
#: and not something the model has seen.
HERO_IMAGE_CAPTION = "Illustrative interior — not generated or analysed by the AI."

ROADMAP = [
    (
        "V1",
        "Core Room Intelligence Workflow",
        "complete",
        [
            "Rectangular room setup and design preferences",
            "AI brief analysis and three design concepts",
            "Furniture and material recommendations",
            "Dimensioned 2D room plan and spatial checks",
            "Deterministic budget analysis and PDF report",
        ],
    ),
    (
        "V2",
        "Visual Understanding",
        "planned",
        [
            "Room photograph analysis",
            "Image-based style extraction",
            "AI-generated concept images",
            "Additional layout alternatives",
        ],
    ),
    (
        "V3",
        "Advanced Spatial Planning",
        "planned",
        [
            "3D visualisation",
            "Multi-room planning",
            "Product catalog integration",
            "Advanced spatial optimisation",
        ],
    ),
]

#: Roadmap states in words. The card shows the label, so an unimplemented
#: version can never be presented as finished, nor a finished one as pending.
BADGE_LABELS = {"complete": "Complete", "planned": "Planned"}

#: The three things the product actually does, each with the icon that names it.
#: The icon repeats the title visually and is ``aria-hidden``; the title is the
#: thing a reader navigates by, so the pairing adds only recognition, not a
#: second channel a screen reader has to reconcile.
CAPABILITIES = [
    (
        "Structured requirements",
        "A validated design brief instead of an unstructured chat transcript.",
        "projects",
    ),
    (
        "Deterministic geometry",
        "Room, openings and furniture checked in centimeters by Python.",
        "plan",
    ),
    (
        "Transparent budget",
        "Illustrative costs calculated and totalled by the application.",
        "report",
    ),
]


def _render_hero() -> None:
    """The hero, followed by the page's one primary action.

    The start action used to live only in the closing "Start a project" block,
    three sections down — below the fold on a 1000 × 700 window, which is the
    one thing §6.1 asks the landing page to get right ("Primary start action").
    It now follows the hero, where the reader decides whether to continue.

    The hero is two columns: the copy on the left, and one illustrative interior
    photograph on the right. The photograph is decoration. It is not uploaded,
    not sent to the model, and not analysed — the alt text and the caption both
    say what it is, because ``DESIGN_SYSTEM.md`` §9 forbids implying that the
    model has looked at a local image.

    The five stage names stay inside the hero but span its full width beneath
    both columns: in a 511 px text column the line wrapped mid-stage ("Final
    Report" split across two lines), which read as a list of six stages.
    """

    import streamlit as st

    with st.container(key="hm-hero-panel"):
        copy, media = st.columns([1, 1], gap="large", vertical_alignment="center")
        with copy:
            theme.html_block(
                f"{theme.brand_mark()}"
                f'<p class="hm-eyebrow">{theme.escape(APP_TAGLINE)}</p>'
                f"{theme.page_title(APP_TITLE)}"
                f'<p class="hm-intro">{theme.escape(SHORT_INTRO)}</p>'
            )
        with media:
            # The key is what the narrow-screen rule hides. Keeping the image in
            # its own container means the rule targets one hook, not a guess at
            # Streamlit's column structure.
            with st.container(key="hm-hero-media"):
                st.image(
                    str(theme.HERO_IMAGE_PATH),
                    width="stretch",
                    alt=HERO_IMAGE_ALT,
                    caption=HERO_IMAGE_CAPTION,
                )
        # The five stage names come from the shell's own table, so the hero
        # cannot advertise a journey the workflow does not walk.
        theme.html_block(
            f'<p class="hm-flow">'
            f'{theme.escape(" → ".join(name for name, _ in STAGES))}</p>'
        )

    theme.html_block(
        '<p class="hm-cta-note">No account, no setup: the first screen asks '
        "for the room. Nothing is sent to the AI model until you press an AI "
        "button.</p>"
    )
    left, right = st.columns([1, 2], gap="medium")
    with left:
        if st.button("Start Room Setup", type="primary", width="stretch"):
            session.enter_workflow()
            st.rerun()
    with right:
        if session.has_workflow() and session.get_workflow().room is not None:
            if st.button("Resume current project", width="stretch"):
                st.session_state[session.ENTERED_KEY] = True
                st.rerun()

    # Separates the action band from the "What it does" section beneath it. The
    # button sat flush against that heading without it.
    theme.html_block('<div class="hm-cta-close"></div>')


def _render_capabilities() -> None:
    import streamlit as st

    theme.html_block(theme.section_heading("What it does"))
    columns = st.columns(len(CAPABILITIES), gap="medium")
    for column, (title, text, icon_name) in zip(columns, CAPABILITIES):
        with column:
            theme.html_block(theme.capability(title, text, icon_name=icon_name))


def _render_roadmap() -> None:
    import streamlit as st

    theme.html_block(
        theme.section_heading("Roadmap")
        + '<p class="hm-section-note">V1 is complete and is the only version you '
        "can run here. V2 and V3 are planned and not implemented.</p>"
    )

    columns = st.columns(len(ROADMAP), gap="medium")
    for column, (version, title, state, items) in zip(columns, ROADMAP):
        # Every card states its own status in words. V1 used to read "In
        # development" long after it was finished, which contradicted the
        # release documentation and the five working stages above it.
        badge_class = "hm-badge--current" if state == "complete" else "hm-badge--planned"
        badge_label = BADGE_LABELS[state]
        bullets = "".join(f"<li>{theme.escape(item)}</li>" for item in items)
        with column:
            theme.html_block(
                f'<div class="hm-card">'
                f'<span class="hm-badge {badge_class}">{badge_label}</span>'
                f"{theme.card_heading(f'{version} · {title}', style='margin-top:14px;')}"
                f'<ul class="hm-list">{bullets}</ul>'
                "</div>"
            )


def _render_start() -> None:
    """The closing block: what the first screens will ask for.

    The start action itself now sits directly under the hero, because the one
    thing §6.1 asks the landing page to get right is a clear primary start
    action, and it used to sit three sections down. This section no longer
    repeats the button: two identically labelled primary buttons on one page is
    exactly the ambiguity this pass is removing elsewhere.
    """

    theme.html_block(
        theme.section_heading("Start a project")
        + '<p class="hm-section-note">The first screen asks for the room, its '
        "two openings and a name; the second for a style, a palette, what the "
        "room has to do and a budget. The whole workflow runs without an AI call "
        "until you press an AI button: room measurements, preferences and the "
        "budget are plain Python. The brief, the concepts, the furniture "
        "selection and the evaluation each make one request when you ask for "
        "them.</p>"
    )


def _render_footnote() -> None:
    theme.html_block(
        '<p class="hm-footnote">Hometsy is a portfolio project. Catalog prices '
        "and generated layouts are illustrative estimates, not verified market "
        "prices or professional architectural drawings.</p>"
    )


def render() -> None:
    _render_hero()
    _render_capabilities()
    _render_roadmap()
    _render_start()
    _render_footnote()


__all__ = ["render"]
