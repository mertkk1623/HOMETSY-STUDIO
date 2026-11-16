"""Design tokens and the one central stylesheet for the application.

``DESIGN_SYSTEM.md`` §3 fixes the palette and §13 requires custom CSS to live in
one place and stay scoped. Every rule here is qualified under ``.hm-page`` (a
class this application renders itself) or under Streamlit's documented
``st-key-`` class convention. Nothing targets Streamlit's internal DOM, so the
interface stays usable if a rule fails to apply.
"""

from __future__ import annotations

import html
from typing import Final, Sequence

#: Approved design-system tokens (DESIGN_SYSTEM.md §3).
COLORS: Final[dict[str, str]] = {
    "primary": "#4B5147",
    "primary_dark": "#343A32",
    "background": "#F6F4EF",
    "surface": "#FFFFFF",
    "surface_muted": "#EEECE5",
    "text_primary": "#292B27",
    # Darkened from the approved secondary grey so body copy keeps readable
    # contrast on the warm background (DESIGN_SYSTEM.md §14).
    #
    # Phase 8 darkened this again, and the three status colours with it, because
    # a real axe-core scan measured them below the 4.5:1 minimum on the muted
    # surface: the 11px uppercase badge text gets no large-text exemption. These
    # are the closest values to the approved hues that clear 4.5:1 on all three
    # surfaces the product uses (muted / background / white).
    "text_secondary": "#5A5C56",  # 5.73 / 6.16 / 6.77
    "border": "#E4E1D9",
    "success": "#4F6A53",  # 5.05 / 5.43 / 5.97
    "warning": "#8A602C",  # 4.69 / 5.04 / 5.54
    "error": "#A44A40",  # 4.89 / 5.26 / 5.78
}

#: Status labels paired with every status, because §7 forbids communicating a
#: state through colour alone.
STATUS_LABELS: Final[dict[str, str]] = {
    "valid": "Valid",
    "warning": "Warning",
    "error": "Error",
    "planned": "Planned",
}

#: Spacing scale (DESIGN_SYSTEM.md §5).
SPACE: Final[dict[str, str]] = {
    "xs": "4px",
    "sm": "8px",
    "md": "16px",
    "lg": "24px",
    "xl": "32px",
    "2xl": "48px",
    "3xl": "64px",
}

APP_CSS: Final[str] = f"""
<style>
  .hm-page {{
    font-family: Inter, Arial, sans-serif;
    color: {COLORS["text_primary"]};
  }}
  /* Headings carry structure; the class carries the look.

     Five helpers used to emit a <p> for something that is really a heading
     ("Room", "Door", "Spatial validation", card names). They now emit h2/h3.
     Streamlit's markdown stylesheet gives every heading its own typeface
     (Source Sans), line-height and padding, so these selectors restore exactly
     the presentation those labels had as paragraphs. Without this the tag
     change would silently restyle every section label on every screen.

     Two-class selectors are used deliberately: Streamlit's rule is
     `.st-emotion-cache-xxxx h2`, so a single-class descendant selector would
     only tie with it and the winner would depend on insertion order. */
  .hm-page .hm-section-label,
  .hm-page .hm-group,
  .hm-page .hm-card-title,
  .hm-page .hm-card-name,
  .hm-page .hm-block-title {{
    font-family: inherit;
    line-height: inherit;
    letter-spacing: normal;
    padding: 0;
  }}
  /* The page title was an h2 and is now the screen's h1. It must keep the box
     it rendered with as an h2, so Streamlit's h1 padding and tracking are
     replaced with the h2 values. */
  .hm-page .hm-page-title {{
    padding: 15px 0;
    letter-spacing: -0.005em;
  }}
  .hm-page .hm-hero {{
    background: {COLORS["surface"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 16px;
    padding: 40px 40px 32px 40px;
    margin-bottom: {SPACE["xl"]};
  }}
  .hm-page .hm-eyebrow {{
    font-size: 12px;
    font-weight: 500;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: {COLORS["text_secondary"]};
    margin: 0 0 {SPACE["md"]} 0;
  }}
  .hm-page .hm-title {{
    font-size: 34px;
    font-weight: 600;
    line-height: 1.2;
    color: {COLORS["primary_dark"]};
    margin: 0 0 {SPACE["md"]} 0;
  }}
  .hm-page .hm-intro {{
    font-size: 16px;
    line-height: 1.65;
    color: {COLORS["text_primary"]};
    max-width: 62ch;
    margin: 0;
  }}
  .hm-page .hm-flow {{
    margin: {SPACE["lg"]} 0 0 0;
    font-size: 14px;
    font-weight: 500;
    color: {COLORS["primary"]};
  }}
  /* The one primary action under the landing hero. It needs to read as a
     deliberate band rather than a button that fell between two sections, so it
     carries its own top rule and generous space beneath. */
  .hm-page .hm-cta-note {{
    font-size: 13px;
    line-height: 1.6;
    color: {COLORS["text_secondary"]};
    margin: 0 0 {SPACE["sm"]} 0;
    max-width: 78ch;
  }}
  .hm-page .hm-cta-close {{
    height: {SPACE["xl"]};
  }}
  .hm-page .hm-section-label {{
    font-size: 22px;
    font-weight: 600;
    color: {COLORS["primary_dark"]};
    margin: 0 0 {SPACE["sm"]} 0;
  }}
  .hm-page .hm-section-note {{
    font-size: 14px;
    color: {COLORS["text_secondary"]};
    margin: 0 0 {SPACE["md"]} 0;
  }}
  .hm-page .hm-card {{
    background: {COLORS["surface"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 12px;
    padding: 20px 22px;
    height: 100%;
    margin-bottom: {SPACE["md"]};
  }}
  .hm-page .hm-card-title {{
    font-size: 17px;
    font-weight: 600;
    color: {COLORS["primary_dark"]};
    margin: 0 0 6px 0;
  }}
  .hm-page .hm-card-text {{
    font-size: 14px;
    line-height: 1.6;
    color: {COLORS["text_secondary"]};
    margin: 0;
  }}
  .hm-page .hm-list {{
    margin: {SPACE["sm"]} 0 0 0;
    padding-left: 18px;
    color: {COLORS["text_primary"]};
  }}
  .hm-page .hm-list li {{
    font-size: 14px;
    line-height: 1.7;
    margin-bottom: 4px;
  }}
  .hm-page .hm-badge {{
    display: inline-block;
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    padding: 4px 10px;
    border-radius: 999px;
    border: 1px solid {COLORS["border"]};
  }}
  .hm-page .hm-badge--current {{
    background: {COLORS["surface_muted"]};
    color: {COLORS["primary_dark"]};
    border: 1px solid {COLORS["primary"]};
  }}
  .hm-page .hm-badge--planned {{
    background: {COLORS["surface_muted"]};
    color: {COLORS["text_secondary"]};
    border: 1px solid {COLORS["border"]};
  }}
  .hm-page .hm-badge--selected {{
    background: {COLORS["primary"]};
    border-color: {COLORS["primary"]};
    color: #FFFFFF;
  }}
  .hm-page .hm-badge--quiet {{
    background: {COLORS["surface_muted"]};
    color: {COLORS["text_secondary"]};
  }}
  .hm-page .hm-badge--success {{
    background: {COLORS["surface_muted"]};
    color: {COLORS["success"]};
    border-color: {COLORS["success"]};
  }}
  .hm-page .hm-footnote {{
    font-size: 12px;
    line-height: 1.6;
    color: {COLORS["text_secondary"]};
    margin-top: {SPACE["lg"]};
  }}

  /* ---- workflow shell ------------------------------------------------ */
  .hm-page .hm-bar {{
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: {SPACE["md"]};
    flex-wrap: wrap;
    border-bottom: 1px solid {COLORS["border"]};
    padding-bottom: 12px;
    margin-bottom: {SPACE["lg"]};
  }}
  .hm-page .hm-bar-brand {{
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: {COLORS["primary_dark"]};
    margin: 0;
  }}
  .hm-page .hm-bar-meta {{
    font-size: 12px;
    color: {COLORS["text_secondary"]};
    margin: 0;
  }}
  .hm-page .hm-stage-strip {{
    display: flex;
    flex-wrap: wrap;
    gap: {SPACE["sm"]};
    margin: 0 0 {SPACE["xl"]} 0;
    padding: 0;
    list-style: none;
  }}
  .hm-page .hm-stage {{
    flex: 1 1 140px;
    border: 1px solid {COLORS["border"]};
    border-radius: 10px;
    padding: 10px 12px;
    background: {COLORS["surface"]};
  }}
  .hm-page .hm-stage--complete {{
    border-color: {COLORS["success"]};
  }}
  .hm-page .hm-stage--current {{
    border-color: {COLORS["primary"]};
    box-shadow: inset 0 0 0 1px {COLORS["primary"]};
    background: {COLORS["surface_muted"]};
  }}
  .hm-page .hm-stage-name {{
    display: block;
    font-size: 13px;
    font-weight: 600;
    color: {COLORS["primary_dark"]};
  }}
  .hm-page .hm-stage-state {{
    display: block;
    font-size: 11px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: {COLORS["text_secondary"]};
    margin-top: 2px;
  }}
  .hm-page .hm-page-title {{
    font-size: 30px;
    font-weight: 600;
    line-height: 1.25;
    color: {COLORS["primary_dark"]};
    margin: 0 0 10px 0;
  }}
  .hm-page .hm-page-intro {{
    font-size: 15px;
    line-height: 1.65;
    color: {COLORS["text_secondary"]};
    max-width: 68ch;
    margin: 0 0 {SPACE["lg"]} 0;
  }}
  .hm-page .hm-group {{
    font-size: 18px;
    font-weight: 600;
    color: {COLORS["primary_dark"]};
    margin: {SPACE["lg"]} 0 {SPACE["sm"]} 0;
  }}
  .hm-page .hm-group-note {{
    font-size: 13px;
    color: {COLORS["text_secondary"]};
    margin: 0 0 12px 0;
  }}
  .hm-page .hm-field-note {{
    font-size: 12px;
    color: {COLORS["text_secondary"]};
    margin: 4px 0 0 0;
  }}
  .hm-page .hm-required {{
    font-size: 12px;
    color: {COLORS["text_secondary"]};
    margin: 0 0 12px 0;
  }}
  .hm-page .hm-summary {{
    background: {COLORS["surface"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 12px;
    padding: 16px 18px;
    margin: {SPACE["sm"]} 0 {SPACE["md"]} 0;
  }}
  .hm-page .hm-summary-row {{
    display: flex;
    justify-content: space-between;
    gap: {SPACE["md"]};
    font-size: 14px;
    padding: 4px 0;
    border-bottom: 1px solid {COLORS["border"]};
  }}
  .hm-page .hm-summary-row:last-child {{
    border-bottom: none;
  }}
  .hm-page .hm-summary-key {{
    color: {COLORS["text_secondary"]};
  }}
  .hm-page .hm-summary-value {{
    color: {COLORS["text_primary"]};
    font-weight: 500;
    text-align: right;
  }}
  .hm-page .hm-ref-image {{
    aspect-ratio: 4 / 3;
    overflow: hidden;
    border-radius: 8px;
    border: 1px solid {COLORS["border"]};
    background: {COLORS["surface_muted"]};
  }}
  .hm-page .hm-ref-image img {{
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }}
  .hm-page .hm-card-name {{
    font-size: 15px;
    font-weight: 600;
    color: {COLORS["primary_dark"]};
    margin: 10px 0 4px 0;
  }}
  .hm-page .hm-card-copy {{
    font-size: 13px;
    line-height: 1.55;
    color: {COLORS["text_secondary"]};
    margin: 0;
  }}
  .hm-page .hm-swatches {{
    display: flex;
    gap: 6px;
    margin: 10px 0 0 0;
  }}
  .hm-page .hm-swatch {{
    width: 22px;
    height: 22px;
    border-radius: 4px;
    border: 1px solid {COLORS["border"]};
  }}

  /* ---- AI result blocks --------------------------------------------- */
  .hm-page .hm-brief-summary {{
    font-size: 15px;
    line-height: 1.7;
    color: {COLORS["text_primary"]};
    margin: 0 0 {SPACE["md"]} 0;
  }}
  .hm-page .hm-brief-block {{
    margin-bottom: {SPACE["md"]};
  }}
  .hm-page .hm-block-title {{
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: {COLORS["text_secondary"]};
    margin: 0 0 2px 0;
  }}
  .hm-page .hm-concept-field {{
    margin: 0 0 10px 0;
  }}
  .hm-page .hm-concept-label {{
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: {COLORS["text_secondary"]};
    margin: 0 0 2px 0;
  }}
  .hm-page .hm-concept-value {{
    font-size: 13px;
    line-height: 1.55;
    color: {COLORS["text_primary"]};
    margin: 0;
  }}
  .hm-page .hm-ref-caption {{
    font-size: 12px;
    line-height: 1.55;
    color: {COLORS["text_secondary"]};
    margin: 6px 0 0 0;
  }}
  .hm-page .hm-call-note {{
    background: {COLORS["surface_muted"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 10px;
    padding: 14px 16px;
    font-size: 13px;
    line-height: 1.6;
    color: {COLORS["text_secondary"]};
    margin: 0 0 {SPACE["md"]} 0;
  }}

  /* A horizontal proportion bar. Used for budget usage, where the number was
     previously a sentence ("96.3% of the budget limit") attached to the
     *remaining* figure, so the emptiest card carried the fullest percentage.
     The bar shows the same figure in the place it belongs: under the totals,
     against the limit it is a proportion of. It is a plain div, not an image,
     so it costs no request and re-renders with the value. */
  .hm-page .hm-meter {{
    height: 10px;
    border: 1px solid {COLORS["border"]};
    border-radius: 999px;
    background: {COLORS["surface_muted"]};
    overflow: hidden;
    margin: {SPACE["md"]} 0 0 0;
  }}
  .hm-page .hm-meter-fill {{
    height: 100%;
    background: {COLORS["primary"]};
  }}
  .hm-page .hm-meter-fill--error {{
    background: {COLORS["error"]};
  }}
  .hm-page .hm-status-row {{
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: {SPACE["sm"]};
    margin: {SPACE["md"]} 0 0 0;
  }}
  .hm-page .hm-status-row p {{
    margin: 0;
    font-size: 13px;
    line-height: 1.6;
    color: {COLORS["text_primary"]};
  }}
  .hm-page .hm-meter-caption {{
    font-size: 12px;
    color: {COLORS["text_secondary"]};
    margin: 6px 0 0 0;
  }}

  /* Secondary commentary. The evaluation screen renders four written
     judgements and then two lists; at paragraph size the lists outweighed the
     judgements they qualify. This panel keeps them readable but subordinate. */
  .hm-page .hm-aside {{
    background: {COLORS["surface_muted"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 12px;
    padding: 16px 18px;
    margin: {SPACE["md"]} 0 {SPACE["md"]} 0;
  }}
  .hm-page .hm-aside .hm-list {{
    margin-top: {SPACE["xs"]};
  }}
  .hm-page .hm-aside .hm-list li {{
    font-size: 13px;
    line-height: 1.6;
  }}

  /* The leading sentence of a concept card. The three alternatives are read
     against each other, so the one field that distinguishes them in a line —
     the description — is set above the supporting fields rather than level
     with them. */
  .hm-page .hm-concept-lead {{
    font-size: 14px;
    line-height: 1.65;
    color: {COLORS["text_primary"]};
    margin: 8px 0 {SPACE["md"]} 0;
  }}

  /* ---- design plan --------------------------------------------------- */
  .hm-page .hm-badge--warning {{
    background: {COLORS["surface_muted"]};
    color: {COLORS["warning"]};
    border-color: {COLORS["warning"]};
  }}
  .hm-page .hm-badge--error {{
    background: {COLORS["surface_muted"]};
    color: {COLORS["error"]};
    border-color: {COLORS["error"]};
  }}
  .hm-page .hm-metric {{
    background: {COLORS["surface"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 12px;
    padding: 14px 16px;
    height: 100%;
  }}
  .hm-page .hm-metric-label {{
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: {COLORS["text_secondary"]};
    margin: 0 0 6px 0;
  }}
  .hm-page .hm-metric-value {{
    font-size: 26px;
    font-weight: 600;
    line-height: 1.15;
    color: {COLORS["primary_dark"]};
    margin: 0;
    /* A money value contains a thin/no-break-adjacent comma, and "41.800,00
       TRY" happily breaks after it, leaving "41.800," on one line and "00 TRY"
       on the next. The figure is one token, so it must not break. */
    white-space: nowrap;
  }}
  .hm-page .hm-metric-note {{
    font-size: 12px;
    line-height: 1.5;
    color: {COLORS["text_secondary"]};
    margin: 6px 0 0 0;
  }}
  .hm-page .hm-plan-frame {{
    background: {COLORS["surface"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 12px;
    padding: 12px;
    /* The plan is a 640-unit drawing whose labels are 9 user units tall, so its
       legibility is decided by the scale it is rendered at. Fitting it to a
       350 px phone frame shrank those labels to 4.6 CSS px — unreadable. The
       frame therefore never renders the drawing below 1:1 (640 CSS px, the
       viewBox width) and scrolls sideways inside itself instead. The page never
       overflows; this box does. The frame is focusable, so a keyboard user can
       pan it (axe: scrollable-region-focusable). */
    overflow-x: auto;
  }}
  .hm-page .hm-plan-frame > svg {{
    min-width: 640px;
  }}
  .hm-page .hm-plan-legend {{
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: {COLORS["text_secondary"]};
    margin: {SPACE["sm"]} 0 0 0;
  }}
  .hm-page .hm-subheading {{
    font-size: 14px;
    font-weight: 600;
    color: {COLORS["primary_dark"]};
    margin: {SPACE["md"]} 0 {SPACE["xs"]} 0;
  }}
  .hm-page .hm-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
    margin: {SPACE["sm"]} 0 {SPACE["md"]} 0;
  }}
  .hm-page .hm-table th {{
    text-align: left;
    font-weight: 600;
    font-size: 11px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: {COLORS["text_secondary"]};
    border-bottom: 1px solid {COLORS["border"]};
    padding: 6px 8px;
  }}
  .hm-page .hm-table td {{
    border-bottom: 1px solid {COLORS["border"]};
    padding: 6px 8px;
    color: {COLORS["text_primary"]};
    vertical-align: top;
  }}
  .hm-page .hm-table td.hm-num {{
    text-align: right;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }}
  .hm-page .hm-issue {{
    border-left: 3px solid {COLORS["border"]};
    padding: 2px 0 2px 10px;
    margin: 0 0 {SPACE["sm"]} 0;
    font-size: 13px;
    line-height: 1.55;
    color: {COLORS["text_primary"]};
  }}
  .hm-page .hm-issue--error {{
    border-left-color: {COLORS["error"]};
  }}
  .hm-page .hm-issue--warning {{
    border-left-color: {COLORS["warning"]};
  }}
  .hm-page .hm-issue-kind {{
    display: block;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: {COLORS["text_secondary"]};
  }}

  /* Narrow screens: the widest tables (the six-column cost table especially)
     cannot fit the content column, so they used to push the whole page into
     horizontal scroll. Tighten the type first, then let a table that still
     needs more room scroll inside its own box rather than the page. Scoped to
     ``.hm-page .hm-table`` so no other element's layout changes. */
  @media (max-width: 640px) {{
    /* The strip is the interface's primary orientation aid, but five stacked
       cards used to take 221 of an 844 px viewport (26%) before the page title
       appeared. A two-column grid keeps all five visible in three short rows
       while halving the height. */
    .hm-page .hm-stage-strip {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 6px;
      margin-bottom: {SPACE["lg"]};
    }}
    .hm-page .hm-stage {{
      flex: none;
      padding: 8px 10px;
    }}
    .hm-page .hm-stage-name {{
      font-size: 12px;
    }}
    .hm-page .hm-stage-state {{
      font-size: 10px;
    }}
    .hm-page .hm-table {{
      display: block;
      overflow-x: auto;
      max-width: 100%;
      font-size: 11px;
    }}
    .hm-page .hm-table th {{
      font-size: 10px;
      padding: 5px 4px;
    }}
    .hm-page .hm-table td {{
      padding: 5px 4px;
    }}
    .hm-page .hm-table td.hm-num {{
      white-space: normal;
    }}
    /* A 26px unbreakable money value does not fit a 160px metric card on a
       phone, so the figure shrinks rather than breaking mid-number or
       overflowing its card. */
    .hm-page .hm-metric-value {{
      font-size: 21px;
    }}
  }}
</style>
"""


def inject_css() -> None:
    """Write the stylesheet. Called once per page render."""

    import streamlit as st

    st.markdown(APP_CSS, unsafe_allow_html=True)


def html_block(markup: str) -> None:
    """Render a scoped HTML fragment.

    Every fragment is wrapped in ``.hm-page`` so the descendant selectors above
    apply consistently across separate Streamlit elements.
    """

    import streamlit as st

    st.markdown(f'<div class="hm-page">{markup}</div>', unsafe_allow_html=True)


def escape(value: object) -> str:
    """Escape user-supplied text before it enters an HTML fragment."""

    return html.escape(str(value), quote=True)


def brand_bar(right_text: str = "") -> str:
    """The compact in-workflow brand line (DESIGN_SYSTEM.md §2)."""

    meta = f'<p class="hm-bar-meta">{escape(right_text)}</p>' if right_text else ""
    return (
        '<div class="hm-bar">'
        '<p class="hm-bar-brand">Hometsy &middot; Room Intelligence Studio</p>'
        f"{meta}"
        "</div>"
    )


def page_title(text: str) -> str:
    """The product's own name, as the landing page's ``h1``.

    The landing page has no ``page_intro`` (there is no stage to announce), so
    its title needs its own helper. Keeping it here means no page hand-writes a
    heading tag and picks a level that fights its own outline.
    """

    return f'<h1 class="hm-title">{escape(text)}</h1>'


def page_intro(eyebrow: str, title: str, intro: str) -> str:
    """Eyebrow, page title and one supporting paragraph.

    The title is the screen's ``h1``. Screen-reader users navigate by heading,
    so the one heading that names the screen has to *be* a level-one heading;
    rendering it as an ``h2`` (or as a styled paragraph) left every workflow
    screen with no ``h1`` at all. Styling comes from the class, never the tag.
    """

    return (
        f'<p class="hm-eyebrow">{escape(eyebrow)}</p>'
        f'<h1 class="hm-page-title">{escape(title)}</h1>'
        f'<p class="hm-page-intro">{escape(intro)}</p>'
    )


def group_heading(title: str, note: str = "") -> str:
    """A titled group of form controls, as a level-two heading.

    These name the major regions of a screen ("Room", "Door", "Spatial
    validation"). They used to be paragraphs, so heading navigation — the main
    way a screen-reader user skims a form — jumped from the page title straight
    past all of them.
    """

    note_html = f'<p class="hm-group-note">{escape(note)}</p>' if note else ""
    return f'<h2 class="hm-group">{escape(title)}</h2>{note_html}'


def field_note(text: str) -> str:
    return f'<p class="hm-field-note">{escape(text)}</p>'


def required_note() -> str:
    """Say which fields are mandatory, without relying on colour alone."""

    return (
        '<p class="hm-required">All fields are required unless marked optional. '
        "Measurements are in centimetres.</p>"
    )


def summary(rows: list[tuple[str, str]]) -> str:
    """A definition-style summary block."""

    body = "".join(
        '<div class="hm-summary-row">'
        f'<span class="hm-summary-key">{escape(key)}</span>'
        f'<span class="hm-summary-value">{escape(value)}</span>'
        "</div>"
        for key, value in rows
    )
    return f'<div class="hm-summary">{body}</div>'


def selected_badge() -> str:
    """The visible selection indicator used on reference cards."""

    return '<span class="hm-badge hm-badge--selected">Selected</span>'


def quiet_badge(text: str) -> str:
    return f'<span class="hm-badge hm-badge--quiet">{escape(text)}</span>'


def success_badge(text: str) -> str:
    return f'<span class="hm-badge hm-badge--success">{escape(text)}</span>'


def warning_badge(text: str) -> str:
    """A non-blocking result. Always a warning, never an error and never a pass."""

    return f'<span class="hm-badge hm-badge--warning">{escape(text)}</span>'


def error_badge(text: str) -> str:
    """A blocking result or a failure. Never dressed as success."""

    return f'<span class="hm-badge hm-badge--error">{escape(text)}</span>'


def score_line(label: str, value: str, note: str = "") -> str:
    """One metric: a label, a value and an optional sentence beneath it.

    Used for the layout score, which is a heuristic quality figure and must never
    be read as a geometric verdict. The label says what the number is, and the
    note says what it is not.
    """

    note_html = f'<p class="hm-metric-note">{escape(note)}</p>' if note else ""
    return (
        '<div class="hm-metric">'
        f'<p class="hm-metric-label">{escape(label)}</p>'
        f'<p class="hm-metric-value">{escape(value)}</p>'
        f"{note_html}"
        "</div>"
    )


def footnote(text: str) -> str:
    return f'<p class="hm-footnote">{escape(text)}</p>'


def usage_meter(percent: float, *, over: bool = False) -> str:
    """A proportion bar for budget usage, with the figure as its caption.

    The bar is decorative: the percentage is printed beside it as text, so the
    value is never carried by colour or length alone (DESIGN_SYSTEM.md §7). The
    fill is clamped to the track because an overrun is reported as a figure, and
    a bar that overflowed its own container would misreport how far over it is.
    """

    clamped = max(0.0, min(float(percent), 100.0))
    fill_class = "hm-meter-fill hm-meter-fill--error" if over else "hm-meter-fill"
    return (
        '<div class="hm-meter" role="presentation">'
        f'<div class="{fill_class}" style="width:{clamped:.1f}%"></div>'
        "</div>"
        f'<p class="hm-meter-caption">{percent:.1f}% of the budget limit</p>'
    )


def status_row(badge: str, sentence: str) -> str:
    """A status badge and its one-sentence explanation, on one baseline.

    The badge used to sit alone on its own line with the sentence beneath,
    which read as two unrelated statements. They answer the same question, so
    they share a row and the sentence stays in normal reading size.
    """

    return (
        '<div class="hm-status-row">'
        f"{badge}"
        f"<p>{escape(sentence)}</p>"
        "</div>"
    )


def aside(heading: str, body: str, note: str = "") -> str:
    """Secondary commentary, set apart from the primary readings above it."""

    note_html = f'<p class="hm-field-note">{escape(note)}</p>' if note else ""
    return (
        '<div class="hm-aside">'
        f"{block_title(heading)}"
        f"{body}"
        f"{note_html}"
        "</div>"
    )


def section_heading(text: str) -> str:
    """A major section of a page, as a level-two heading.

    Used where a region is marked up outside :func:`group_heading` — the landing
    page's sections. Same look as before; the tag is the difference.
    """

    return f'<h2 class="hm-section-label">{escape(text)}</h2>'


def card_heading(text: str, *, style: str = "") -> str:
    """The name of a card, as a level-three heading.

    Cards sit inside a section (``h2``) on a page (``h1``), so their names are
    ``h3``. A screen reader can then list the cards of a section by heading.
    """

    style_attr = f' style="{style}"' if style else ""
    return f'<h3 class="hm-card-title"{style_attr}>{escape(text)}</h3>'


def card_name(text: str) -> str:
    """The name of a selectable reference card, as a level-three heading."""

    return f'<h3 class="hm-card-name">{escape(text)}</h3>'


def block_title(text: str, *, level: int = 3) -> str:
    """A small uppercase label above a block of text, as a heading.

    Defaults to ``h3``: these sit under a ``group_heading`` (``h2``) inside the
    page (``h1``). ``level`` exists for the one place where the block is a
    top-level region of the screen rather than a part of one.
    """

    if level not in (2, 3):
        raise ValueError(f"block_title level must be 2 or 3, got {level!r}")
    return f'<h{level} class="hm-block-title">{escape(text)}</h{level}>'


def paragraph(text: str, *, css_class: str = "hm-card-copy") -> str:
    """One paragraph of untrusted (possibly AI-written) text, escaped."""

    return f'<p class="{css_class}">{escape(text)}</p>'


def brief_summary(text: str) -> str:
    """The brief's summary, set at reading size rather than card size."""

    return f'<p class="hm-brief-summary">{escape(text)}</p>'


def bullet_list(items: Sequence[str]) -> str:
    """An escaped bullet list, or an explicit "none" sentence when empty."""

    if not items:
        return '<p class="hm-card-copy">None identified.</p>'
    entries = "".join(f"<li>{escape(item)}</li>" for item in items)
    return f'<ul class="hm-list">{entries}</ul>'


def concept_field(label: str, value: str, *, lead: bool = False) -> str:
    """One labelled field of a concept card.

    ``lead`` sets the value at reading size instead of label size. It is used
    for the description, which states the whole proposition in a sentence and
    is compared across the three cards before their supporting fields are read.
    """

    value_class = "hm-concept-value hm-concept-lead" if lead else "hm-concept-value"
    return (
        '<div class="hm-concept-field">'
        f'<p class="hm-concept-label">{escape(label)}</p>'
        f'<p class="{value_class}">{escape(value)}</p>'
        "</div>"
    )


def call_note(text: str) -> str:
    """Explain what a button is about to send, before it is pressed."""

    return f'<p class="hm-call-note">{escape(text)}</p>'


def reference_caption(text: str) -> str:
    return f'<p class="hm-ref-caption">{escape(text)}</p>'
