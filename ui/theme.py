"""Design tokens and the one central stylesheet for the application.

``DESIGN_SYSTEM.md`` §3 fixes the palette and §13 requires custom CSS to live in
one place and stay scoped. Every rule here is qualified under ``.hm-page`` (a
class this application renders itself) or under Streamlit's documented
``st-key-`` class convention. Nothing targets Streamlit's internal DOM, so the
interface stays usable if a rule fails to apply.

This module also owns the brand and icon assets, because they are presentation
and nothing else: a logo in the header, a favicon in the tab, an icon beside a
label. Every asset is read from ``assets/`` on disk — no remote URL is ever
constructed (AGENTS.md §11).
"""

from __future__ import annotations

import html
from functools import lru_cache
from pathlib import Path
from typing import Final, Sequence

#: Repository root, derived rather than hardcoded so the app runs from any cwd.
PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

#: Brand assets (UI V2 asset pack). All local, all licensed for this project —
#: see ``COPYRIGHT.md`` and ``docs/design-reference/ASSET_GUIDE.md``.
LOGO_PATH: Final[Path] = PROJECT_ROOT / "assets" / "brand" / "hometsy-logo.svg"
LOGO_LIGHT_PATH: Final[Path] = (
    PROJECT_ROOT / "assets" / "brand" / "hometsy-logo-light.svg"
)
SYMBOL_PATH: Final[Path] = PROJECT_ROOT / "assets" / "brand" / "hometsy-symbol.svg"
FAVICON_PATH: Final[Path] = PROJECT_ROOT / "assets" / "brand" / "favicon-64.png"
ICONS_DIR: Final[Path] = PROJECT_ROOT / "assets" / "icons"

#: The landing hero photograph. The source PNG is 2.6 MB; this is the same image
#: re-encoded as a progressive JPEG at 1280x720 (169.8 KB), which is the width
#: the hero renders at on a 3x display. It is decorative: it illustrates the
#: subject, and nothing reads it (``DESIGN_SYSTEM.md`` §9).
HERO_IMAGE_PATH: Final[Path] = (
    PROJECT_ROOT / "assets" / "images" / "hero-living-room.jpg"
)

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

#: The interface typeface stack (DESIGN_SYSTEM.md §4).
#:
#: Inter is the approved face but is **not bundled** with this project and no
#: remote font is loaded (AGENTS.md §11), so the stack resolves to Arial today
#: and to Inter on a machine where Inter happens to be installed. The important
#: property is that it is the *same* stack everywhere: ``.streamlit/config.toml``
#: hands Streamlit's own widgets this exact string, so a field's label and the
#: input beneath it are never set in two different typefaces — which is what
#: ``font = "sans serif"`` used to do (Source Sans widgets, Arial HTML).
FONT_FAMILY: Final[str] = "Inter, Arial, sans-serif"

#: Typographic scale, in pixels. ``DESIGN_SYSTEM.md`` §4 gives ranges; these are
#: the sizes the interface actually renders, kept in one place so a heading and
#: its section cannot drift a pixel apart.
TYPE: Final[dict[str, str]] = {
    "display": "34px",  # landing product title
    "title": "30px",  # workflow screen title
    "metric": "26px",  # one figure in a metric card
    "section": "22px",  # landing/roadmap section
    "group": "18px",  # form group ("Room", "Door")
    "card": "17px",  # card name
    "lead": "16px",  # landing intro
    "body": "15px",  # page intro, brief summary
    "reading": "14px",  # body copy inside cards
    "small": "13px",  # supporting copy, tables
    "caption": "12px",  # captions, field notes
    "label": "11px",  # uppercase badges, table heads
    "micro": "10px",  # issue kind
    "metric_narrow": "21px",  # the same figure on a phone
}

#: Line heights, unitless so they scale with the type they describe.
LINE: Final[dict[str, str]] = {
    "none": "1.15",
    "tight": "1.2",
    "heading": "1.25",
    "snug": "1.55",
    "body": "1.6",
    "reading": "1.65",
    "loose": "1.7",
}

#: Corner radii. Streamlit's own widgets take ``theme.baseRadius`` /
#: ``theme.buttonRadius`` from the same two values (see ``.streamlit/config.toml``
#: and ``test_the_streamlit_theme_config_matches_the_design_tokens``), so a card
#: drawn in HTML and a card drawn by Streamlit round by the same amount.
RADIUS: Final[dict[str, str]] = {
    "xs": "4px",
    "sm": "8px",
    "md": "10px",
    "lg": "12px",
    "xl": "16px",
    "pill": "999px",
}

#: Reading measures. Long prose is capped in ``ch`` because a line held to ~65
#: characters is what makes an editorial layout readable at 1440 px.
MEASURE: Final[dict[str, str]] = {
    "prose": "62ch",
    "wide": "68ch",
    "note": "78ch",
}

#: The centred content column, in CSS pixels (``DESIGN_SYSTEM.md`` §5: "use a
#: centered content area"). ``app.py`` opens a flex row with
#: ``horizontal_alignment="center"`` and puts this width inside it — both are
#: documented Streamlit parameters, so no internal DOM is targeted. The value is
#: wide enough for the 640-unit plan drawing and the six-column cost table, and
#: narrow enough that text does not run the full width of a large monitor.
CONTENT_WIDTH: Final[int] = 1180

#: UI V2 decorative accents — strictly non-semantic.
#:
#: This table exists because the approved V2 direction adds warmth that the
#: product palette has no slot for, while the brief forbids changing the product
#: tokens. Three rules keep that from becoming a second palette:
#:
#: * **Disjoint from :data:`COLORS`.** No accent may name or shadow a product
#:   token. A test asserts the two tables share no key and no value.
#: * **Never in the PDF.** :data:`core.report_generator.PALETTE` is pinned equal
#:   to ``COLORS`` and stays untouched, so the report does not move.
#: * **Never carries meaning.** Accents appear only as decoration that has a text
#:   label beside it or no meaning at all: the rule under an eyebrow, the frame
#:   of the brand mark. No status, no control state, no body copy — so none of
#:   them is ever load-bearing for comprehension or contrast.
#:
#: Only the two hues the interface actually uses are declared; the asset pack's
#: ivory and charcoal already equal ``COLORS["background"]`` and
#: ``COLORS["text_primary"]`` within a rounding step, so introducing them again
#: would create two names for one colour.
ACCENT: Final[dict[str, str]] = {
    "terracotta": "#BD8065",
    "olive": "#858A70",
}

APP_CSS: Final[str] = f"""
<style>
  /* The one stylesheet. Two kinds of selector appear below, and only these two:
     a class this application renders itself (under ``.hm-page``), or an
     ``st-key-`` class the application mints with ``st.container(key=...)``.
     Nothing targets Streamlit's internal DOM, so the interface stays usable if
     a decorative rule fails to apply (DESIGN_SYSTEM.md §13). */
  .hm-page {{
    font-family: {FONT_FAMILY};
    font-size: {TYPE["body"]};
    line-height: {LINE["body"]};
    color: {COLORS["text_primary"]};
    -webkit-font-smoothing: antialiased;
    text-rendering: optimizeLegibility;
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
  /* The landing hero. It was one HTML card; it is now a Streamlit container so
     the copy and the photograph can sit in two real columns. Only the container's
     documented `st-key-` class is targeted, so if the key ever changes the panel
     simply loses its surface and keeps working (§13). */
  [class*="st-key-hm-hero-panel"] {{
    background: {COLORS["surface"]};
    border: 1px solid {COLORS["border"]};
    border-radius: {RADIUS["xl"]};
    padding: {SPACE["2xl"]} {SPACE["2xl"]} {SPACE["xl"]} {SPACE["2xl"]};
    margin-bottom: {SPACE["xl"]};
  }}
  /* One 16:9 window for the photograph, cropped rather than distorted. The image
     is decoration: it shows the subject the product is about, and nothing — in
     the browser or in the model — reads it (§9). */
  [class*="st-key-hm-hero-panel"] img {{
    display: block;
    width: 100%;
    height: auto;
    aspect-ratio: 16 / 9;
    object-fit: cover;
    border: 1px solid {COLORS["border"]};
    border-radius: {RADIUS["lg"]};
  }}
  .hm-page .hm-eyebrow {{
    font-size: {TYPE["caption"]};
    font-weight: 500;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: {COLORS["text_secondary"]};
    margin: 0 0 {SPACE["md"]} 0;
  }}
  .hm-page .hm-title {{
    font-size: {TYPE["display"]};
    font-weight: 600;
    line-height: {LINE["tight"]};
    letter-spacing: -0.02em;
    color: {COLORS["primary_dark"]};
    margin: 0 0 {SPACE["md"]} 0;
  }}
  .hm-page .hm-intro {{
    font-size: {TYPE["lead"]};
    line-height: {LINE["reading"]};
    color: {COLORS["text_secondary"]};
    max-width: {MEASURE["prose"]};
    margin: 0;
  }}
  .hm-page .hm-flow {{
    margin: {SPACE["lg"]} 0 0 0;
    font-size: {TYPE["small"]};
    font-weight: 500;
    letter-spacing: 0.02em;
    color: {COLORS["primary"]};
  }}
  /* The one primary action under the landing hero. It needs to read as a
     deliberate band rather than a button that fell between two sections, so it
     carries its own top rule and generous space beneath. */
  .hm-page .hm-cta-note {{
    font-size: {TYPE["small"]};
    line-height: {LINE["body"]};
    color: {COLORS["text_secondary"]};
    margin: 0 0 {SPACE["sm"]} 0;
    max-width: {MEASURE["note"]};
  }}
  .hm-page .hm-cta-close {{
    height: {SPACE["xl"]};
  }}
  .hm-page .hm-section-label {{
    font-size: {TYPE["section"]};
    font-weight: 600;
    letter-spacing: -0.01em;
    color: {COLORS["primary_dark"]};
    margin: 0 0 {SPACE["sm"]} 0;
  }}
  .hm-page .hm-section-note {{
    font-size: {TYPE["reading"]};
    line-height: {LINE["body"]};
    color: {COLORS["text_secondary"]};
    margin: 0 0 {SPACE["md"]} 0;
  }}
  .hm-page .hm-card {{
    background: {COLORS["surface"]};
    border: 1px solid {COLORS["border"]};
    border-radius: {RADIUS["lg"]};
    padding: {SPACE["lg"]} {SPACE["lg"]};
    height: 100%;
    margin-bottom: {SPACE["md"]};
  }}
  .hm-page .hm-card-title {{
    font-size: {TYPE["card"]};
    font-weight: 600;
    letter-spacing: -0.005em;
    color: {COLORS["primary_dark"]};
    margin: 0 0 6px 0;
  }}
  .hm-page .hm-card-text {{
    font-size: {TYPE["reading"]};
    line-height: {LINE["body"]};
    color: {COLORS["text_secondary"]};
    margin: 0;
  }}
  .hm-page .hm-list {{
    margin: {SPACE["sm"]} 0 0 0;
    padding-left: 18px;
    color: {COLORS["text_primary"]};
  }}
  .hm-page .hm-list li {{
    font-size: {TYPE["reading"]};
    line-height: {LINE["loose"]};
    margin-bottom: {SPACE["xs"]};
  }}
  .hm-page .hm-badge {{
    display: inline-block;
    font-size: {TYPE["label"]};
    font-weight: 600;
    letter-spacing: 0.07em;
    text-transform: uppercase;
    padding: 4px 10px;
    border-radius: {RADIUS["pill"]};
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
    font-size: {TYPE["caption"]};
    line-height: {LINE["body"]};
    color: {COLORS["text_secondary"]};
    margin-top: {SPACE["lg"]};
  }}

  /* ---- workflow shell ------------------------------------------------ */
  .hm-page .hm-bar {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: {SPACE["md"]};
    flex-wrap: wrap;
    border-bottom: 1px solid {COLORS["border"]};
    padding-bottom: {SPACE["md"]};
    margin-bottom: {SPACE["lg"]};
  }}
  .hm-page .hm-bar-brand {{
    font-size: {TYPE["caption"]};
    font-weight: 600;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: {COLORS["primary_dark"]};
    margin: 0;
  }}
  .hm-page .hm-bar-meta {{
    font-size: {TYPE["caption"]};
    color: {COLORS["text_secondary"]};
    margin: 0;
    font-variant-numeric: tabular-nums;
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
    border-radius: {RADIUS["md"]};
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
    font-size: {TYPE["caption"]};
    font-weight: 600;
    color: {COLORS["primary_dark"]};
  }}
  .hm-page .hm-stage-state {{
    display: block;
    font-size: {TYPE["label"]};
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: {COLORS["text_secondary"]};
    margin-top: 2px;
  }}
  .hm-page .hm-page-title {{
    font-size: {TYPE["title"]};
    font-weight: 600;
    line-height: {LINE["heading"]};
    letter-spacing: -0.015em;
    color: {COLORS["primary_dark"]};
    margin: 0 0 10px 0;
  }}
  .hm-page .hm-page-intro {{
    font-size: {TYPE["body"]};
    line-height: {LINE["reading"]};
    color: {COLORS["text_secondary"]};
    max-width: {MEASURE["wide"]};
    margin: 0 0 {SPACE["lg"]} 0;
  }}
  .hm-page .hm-group {{
    font-size: {TYPE["group"]};
    font-weight: 600;
    letter-spacing: -0.005em;
    color: {COLORS["primary_dark"]};
    margin: {SPACE["lg"]} 0 {SPACE["sm"]} 0;
  }}
  .hm-page .hm-group-note {{
    font-size: {TYPE["small"]};
    line-height: {LINE["body"]};
    color: {COLORS["text_secondary"]};
    margin: 0 0 12px 0;
  }}
  .hm-page .hm-field-note {{
    font-size: {TYPE["caption"]};
    line-height: {LINE["snug"]};
    color: {COLORS["text_secondary"]};
    margin: 4px 0 0 0;
  }}
  .hm-page .hm-required {{
    font-size: {TYPE["caption"]};
    color: {COLORS["text_secondary"]};
    margin: 0 0 12px 0;
  }}
  .hm-page .hm-summary {{
    background: {COLORS["surface"]};
    border: 1px solid {COLORS["border"]};
    border-radius: {RADIUS["lg"]};
    padding: {SPACE["md"]} {SPACE["md"]};
    margin: {SPACE["sm"]} 0 {SPACE["md"]} 0;
  }}
  .hm-page .hm-summary-row {{
    display: flex;
    justify-content: space-between;
    gap: {SPACE["md"]};
    font-size: {TYPE["reading"]};
    padding: {SPACE["xs"]} 0;
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
    font-variant-numeric: tabular-nums;
  }}
  /* The reference-card image. Nothing emits this class today — the card images
     are ``st.image`` elements inside a keyed container — so it is kept only as
     the documented hook for a future HTML-rendered card, and is styled to match
     the ``st-key-style-*`` / ``st-key-palette-*`` treatment above it. */
  .hm-page .hm-ref-image {{
    aspect-ratio: 4 / 3;
    overflow: hidden;
    border-radius: {RADIUS["sm"]};
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
    font-size: {TYPE["body"]};
    font-weight: 600;
    letter-spacing: -0.005em;
    color: {COLORS["primary_dark"]};
    margin: 10px 0 4px 0;
  }}
  .hm-page .hm-card-copy {{
    font-size: {TYPE["small"]};
    line-height: {LINE["snug"]};
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
    border-radius: {RADIUS["xs"]};
    border: 1px solid {COLORS["border"]};
  }}

  /* ---- AI result blocks --------------------------------------------- */
  .hm-page .hm-brief-summary {{
    font-size: {TYPE["body"]};
    line-height: {LINE["reading"]};
    color: {COLORS["text_primary"]};
    margin: 0 0 {SPACE["md"]} 0;
  }}
  .hm-page .hm-brief-block {{
    margin-bottom: {SPACE["md"]};
  }}
  .hm-page .hm-block-title {{
    font-size: {TYPE["small"]};
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
    font-size: {TYPE["label"]};
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: {COLORS["text_secondary"]};
    margin: 0 0 2px 0;
  }}
  .hm-page .hm-concept-value {{
    font-size: {TYPE["small"]};
    line-height: {LINE["snug"]};
    color: {COLORS["text_primary"]};
    margin: 0;
  }}
  .hm-page .hm-ref-caption {{
    font-size: {TYPE["caption"]};
    line-height: {LINE["snug"]};
    color: {COLORS["text_secondary"]};
    margin: 6px 0 0 0;
  }}
  .hm-page .hm-call-note {{
    background: {COLORS["surface_muted"]};
    border: 1px solid {COLORS["border"]};
    border-radius: {RADIUS["md"]};
    padding: {SPACE["md"]};
    font-size: {TYPE["small"]};
    line-height: {LINE["body"]};
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
    border-radius: {RADIUS["pill"]};
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
    font-size: {TYPE["small"]};
    line-height: {LINE["body"]};
    color: {COLORS["text_primary"]};
  }}
  .hm-page .hm-meter-caption {{
    font-size: {TYPE["caption"]};
    color: {COLORS["text_secondary"]};
    margin: 6px 0 0 0;
    font-variant-numeric: tabular-nums;
  }}

  /* Secondary commentary. The evaluation screen renders four written
     judgements and then two lists; at paragraph size the lists outweighed the
     judgements they qualify. This panel keeps them readable but subordinate. */
  .hm-page .hm-aside {{
    background: {COLORS["surface_muted"]};
    border: 1px solid {COLORS["border"]};
    border-radius: {RADIUS["lg"]};
    padding: {SPACE["md"]};
    margin: {SPACE["md"]} 0 {SPACE["md"]} 0;
  }}
  .hm-page .hm-aside .hm-list {{
    margin-top: {SPACE["xs"]};
  }}
  .hm-page .hm-aside .hm-list li {{
    font-size: {TYPE["small"]};
    line-height: {LINE["body"]};
  }}

  /* The leading sentence of a concept card. The three alternatives are read
     against each other, so the one field that distinguishes them in a line —
     the description — is set above the supporting fields rather than level
     with them. */
  .hm-page .hm-concept-lead {{
    font-size: {TYPE["reading"]};
    line-height: {LINE["reading"]};
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
    border-radius: {RADIUS["lg"]};
    padding: {SPACE["md"]} {SPACE["md"]};
    height: 100%;
  }}
  .hm-page .hm-metric-label {{
    font-size: {TYPE["label"]};
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: {COLORS["text_secondary"]};
    margin: 0 0 6px 0;
  }}
  .hm-page .hm-metric-value {{
    font-size: {TYPE["metric"]};
    font-weight: 600;
    line-height: {LINE["none"]};
    letter-spacing: -0.02em;
    color: {COLORS["primary_dark"]};
    margin: 0;
    /* A money value contains a thin/no-break-adjacent comma, and "41.800,00
       TRY" happily breaks after it, leaving "41.800," on one line and "00 TRY"
       on the next. The figure is one token, so it must not break. */
    white-space: nowrap;
  }}
  .hm-page .hm-metric-note {{
    font-size: {TYPE["caption"]};
    line-height: {LINE["snug"]};
    color: {COLORS["text_secondary"]};
    margin: 6px 0 0 0;
  }}
  .hm-page .hm-plan-frame {{
    background: {COLORS["surface"]};
    border: 1px solid {COLORS["border"]};
    border-radius: {RADIUS["lg"]};
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
    font-size: {TYPE["caption"]};
    color: {COLORS["text_secondary"]};
    margin: {SPACE["sm"]} 0 0 0;
  }}
  .hm-page .hm-subheading {{
    font-size: {TYPE["reading"]};
    font-weight: 600;
    color: {COLORS["primary_dark"]};
    margin: {SPACE["md"]} 0 {SPACE["xs"]} 0;
  }}
  .hm-page .hm-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: {TYPE["small"]};
    margin: {SPACE["sm"]} 0 {SPACE["md"]} 0;
  }}
  .hm-page .hm-table th {{
    text-align: left;
    font-weight: 600;
    font-size: {TYPE["label"]};
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
    font-size: {TYPE["small"]};
    line-height: {LINE["snug"]};
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
    font-size: {TYPE["micro"]};
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: {COLORS["text_secondary"]};
  }}

  /* ---- brand and iconography ----------------------------------------- */
  /* The inline icon helper. The span sets the box; the SVG inside inherits the
     colour through `currentColor` and is sized here rather than in markup, so
     one rule moves every icon in the interface. An icon is always decorative:
     it sits beside its own text label, so it is `aria-hidden` and never the only
     carrier of meaning (DESIGN_SYSTEM.md §8, §14).

     The stroke is a product token, not an accent. An icon is drawn in the same
     ink as the text it belongs to, so it reads as part of the line rather than
     as a separate coloured object — and so the one colour that must be legible
     is a token that already clears 4.5:1. */
  .hm-page .hm-icon {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1.15em;
    height: 1.15em;
    flex: none;
    vertical-align: -0.16em;
    color: {COLORS["primary"]};
  }}
  .hm-page .hm-icon svg {{
    width: 100%;
    height: 100%;
    display: block;
  }}
  /* The mark that opens the landing hero: the symbol in its own tile, framed in
     the muted olive of the V2 accents. The frame encodes nothing — the mark is
     the information, and it is `aria-hidden` because the page title beside it
     names the product. */
  .hm-page .hm-mark {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 64px;
    height: 64px;
    border-radius: {RADIUS["xl"]};
    background: {COLORS["surface_muted"]};
    border: 1px solid {ACCENT["olive"]};
    margin-bottom: {SPACE["lg"]};
    color: {COLORS["primary_dark"]};
  }}
  .hm-page .hm-mark svg {{
    width: 34px;
    height: 34px;
    display: block;
  }}
  /* A capability row: icon, then the text it belongs to. */
  .hm-page .hm-capability {{
    display: flex;
    align-items: flex-start;
    gap: 10px;
  }}
  .hm-page .hm-capability .hm-icon {{
    margin-top: 3px;
    width: 18px;
    height: 18px;
  }}
  /* The one place the V2 accent appears: a short terracotta rule beneath an
     eyebrow. The eyebrow is a short uppercase label ("Stage 2 of 5 · Room") that
     already says what the page is, so the bar beneath it is pure ornament — it
     encodes nothing, and removing it loses no information. That is the only way
     a colour at ~2.4:1 can be used at all without making a claim this project
     cannot back up with a contrast ratio. */
  .hm-page .hm-eyebrow::after {{
    content: "";
    display: block;
    width: 28px;
    height: 2px;
    margin-top: {SPACE["sm"]};
    border-radius: 1px;
    background: {ACCENT["terracotta"]};
  }}

  /* ---- reference-card hooks (st-key-) -------------------------------- */
  /* Streamlit gives a container a `st-key-<key>` class when it is opened with
     `st.container(key=...)`. That is a documented, stable class name — not an
     internal — so it is the one way to style a Streamlit-owned card without
     reaching into its DOM.

     The value selector below is an attribute prefix on that documented class
     (`.st-key-style-*`, `.st-key-palette-*`); the descendants it reaches are
     plain HTML elements (`img`, `p`, `h3`), never a Streamlit test id or
     generated `st-emotion-cache-*` name. If any of these rules stops applying
     the card simply returns to Streamlit's default chrome — which is the
     "must remain functional if a decorative rule fails" requirement of §13. */
  [class*="st-key-style-"],
  [class*="st-key-palette-"] {{
    padding: 10px 10px 12px 10px;
    background: {COLORS["surface"]};
    border-color: {COLORS["border"]};
    border-radius: {RADIUS["lg"]};
  }}
  /* One aspect ratio for every reference image, so a portrait source does not
     make its card taller than the landscape ones beside it. `object-fit: cover`
     crops rather than distorts; the caption and the alt text carry the meaning,
     so nothing is lost by trimming the edges of an illustrative picture. */
  [class*="st-key-style-"] img,
  [class*="st-key-palette-"] img {{
    aspect-ratio: 4 / 3;
    object-fit: cover;
    border-radius: {RADIUS["sm"]};
    display: block;
  }}

  /* ---- concept-card hooks (st-key-) ---------------------------------- */
  [class*="st-key-hm-concept-"] {{
    padding: {SPACE["md"]};
    background: {COLORS["surface"]};
    border-color: {COLORS["border"]};
    border-radius: {RADIUS["lg"]};
  }}
  /* Three cards in one row must offer three buttons on one line, or the eye
     reads a shared action whose targets sit at three different heights.

     Streamlit draws each column as a stack of wrappers (`stColumn` ->
     `stVerticalBlock` -> `stLayoutWrapper` -> the card) and writes an explicit
     pixel `height` onto `stColumn`. A flex item with a definite height opts out
     of `align-items: stretch`, which is why each column was only as tall as its
     own prose and a rule on the card alone changed nothing.

     Clearing that height is the whole fix: the row is already `align-items:
     stretch`, so the columns then share the tallest card's height. `:has()`
     reaches that box by naming the child this application minted, so no
     Streamlit internal is named and the rule cannot leak to another row. If the
     nesting ever changes the rule simply stops matching and the cards go back to
     content height — the layout degrades, the content does not.

     Clearing the column's height is necessary but not sufficient: the two
     wrappers between the column and the card still size to their content, so the
     card has to be told to fill them as well. Both are named by the same
     `:has()` chain, and the column itself is the only box in the chain that is
     *not* given a height — it must stay `auto` for the stretch to apply.

     Once the cards are equal height, `margin-top: auto` on the button's block
     pushes it to the bottom, so all three buttons start on one line. No text is
     clipped: the cards grow downwards, and the longest description sets the row
     height, which is what it already did. */
  [class*="st-key-hm-concepts-row"] div:has(> [class*="st-key-hm-concept-"]),
  [class*="st-key-hm-concepts-row"] div:has(> div > [class*="st-key-hm-concept-"]) {{
    height: 100%;
  }}
  [class*="st-key-hm-concepts-row"]
    div:has(> div > div > [class*="st-key-hm-concept-"]) {{
    height: auto;
  }}
  [class*="st-key-hm-concept-"] {{
    display: flex;
    flex-direction: column;
    height: 100%;
  }}
  [class*="st-key-hm-concept-"] > div:last-child {{
    margin-top: auto;
  }}

  /* Narrow screens. The hero becomes one column: the photograph is decoration,
     and on a phone it did nothing but push the primary action past the fold, so
     it is dropped rather than stacked. The spacing inside the panel tightens for
     the same reason — the start button has to be reachable without scrolling
     (DESIGN_SYSTEM.md §12). Type sizes are untouched: a 34px display size is
     still comfortable at 390px, and shrinking an approved step to buy space
     would trade the approved hierarchy for a layout convenience. */
  @media (max-width: 900px) {{
    /* The media column and every wrapper between it and the row. Written as a
       depth chain rather than one rule so a change in Streamlit's nesting
       degrades to "the picture reappears", never to a hidden paragraph. */
    [class*="st-key-hm-hero-panel"] div:has(> [class*="st-key-hm-hero-media"]),
    [class*="st-key-hm-hero-panel"]
      div:has(> div > [class*="st-key-hm-hero-media"]),
    [class*="st-key-hm-hero-panel"]
      div:has(> div > div > [class*="st-key-hm-hero-media"]) {{
      display: none;
    }}
    [class*="st-key-hm-hero-panel"] {{
      padding: {SPACE["lg"]} {SPACE["md"]} {SPACE["md"]} {SPACE["md"]};
      margin-bottom: {SPACE["md"]};
    }}
    /* The mark, the eyebrow and the title each carried a generous bottom margin
       that reads as air at 1180px and as waste at 390px. */
    [class*="st-key-hm-hero-panel"] .hm-mark {{
      width: 48px;
      height: 48px;
      margin-bottom: 14px;
    }}
    [class*="st-key-hm-hero-panel"] .hm-mark svg {{
      width: 26px;
      height: 26px;
    }}
    [class*="st-key-hm-hero-panel"] .hm-eyebrow {{
      margin-bottom: 10px;
    }}
    [class*="st-key-hm-hero-panel"] .hm-title {{
      margin-bottom: 12px;
    }}
    [class*="st-key-hm-hero-panel"] .hm-flow {{
      margin-top: {SPACE["sm"]};
    }}
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
      font-size: {TYPE["caption"]};
    }}
    .hm-page .hm-stage-state {{
      font-size: {TYPE["micro"]};
    }}
    .hm-page .hm-table {{
      display: block;
      overflow-x: auto;
      max-width: 100%;
      font-size: {TYPE["label"]};
    }}
    .hm-page .hm-table th {{
      font-size: {TYPE["micro"]};
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
      font-size: {TYPE["metric_narrow"]};
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


# --------------------------------------------------------------------------- #
# Icons
# --------------------------------------------------------------------------- #

#: Every icon the interface may draw, by name. The list is closed on purpose: a
#: name outside it raises at the call site rather than rendering nothing, which
#: is how a missing icon used to disappear silently.
ICON_NAMES: Final[tuple[str, ...]] = (
    "arrow-right",
    "check",
    "chevron-left",
    "download",
    "evaluation",
    "home",
    "image",
    "info",
    "menu",
    "plan",
    "plus",
    "projects",
    "report",
    "room",
    "settings",
    "sliders",
    "sofa",
)


@lru_cache(maxsize=None)
def _icon_source(name: str) -> str:
    """The inner markup of one icon file, ready to inline.

    The pack ships each icon as a standalone SVG with a hardcoded stroke colour.
    Two edits make it usable here and neither changes the drawing:

    * ``stroke="#252A28"`` becomes ``stroke="currentColor"``, so the icon takes
      the colour of the element it is placed in. A fixed colour would be wrong
      in a badge, on the primary button, and beside muted text.
    * the outer ``<svg>`` wrapper is dropped. The helper supplies its own, with
      the size and the ``aria-hidden`` the surrounding text implies.

    Reading from disk at call time (once, via the cache) keeps the asset the
    single source of truth — there is no second copy of the path data in Python.
    """

    if name not in ICON_NAMES:
        raise ValueError(f"Unknown icon: {name!r}. Known: {', '.join(ICON_NAMES)}")
    path = ICONS_DIR / f"{name}.svg"
    source = path.read_text(encoding="utf-8")
    inner = source[source.index(">") + 1 : source.rindex("</svg>")]
    return inner.replace('stroke="#252A28"', 'stroke="currentColor"')


def icon(name: str) -> str:
    """One inline icon, decorative by construction.

    The icon is ``aria-hidden``: it always sits beside a text label that says the
    same thing, so announcing it again would only make a screen reader repeat
    itself (DESIGN_SYSTEM.md §14). There is no accessible-name parameter, because
    an icon that carries meaning on its own is the thing this helper refuses to
    produce.
    """

    return (
        '<span class="hm-icon" aria-hidden="true">'
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">'
        f"{_icon_source(name)}"
        "</svg>"
        "</span>"
    )


def brand_mark() -> str:
    """The standalone architectural symbol, for the landing hero."""

    return (
        '<span class="hm-mark" aria-hidden="true">'
        '<svg viewBox="0 0 128 128" fill="none">'
        '<path d="M18 62 64 20l46 42v48H79V77H49v33H18Z" stroke="currentColor" '
        'stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/>'
        "</svg>"
        "</span>"
    )


def capability(title: str, text: str, *, icon_name: str) -> str:
    """One capability: an icon, a card heading, and a sentence.

    The icon is decoration; the heading is what a reader navigates by. Both were
    text-only before, which made three equal-weight cards read as three
    paragraphs rather than three distinct promises.
    """

    return (
        '<div class="hm-card">'
        '<div class="hm-capability">'
        f"{icon(icon_name)}"
        "<div>"
        f"{card_heading(title)}"
        f'<p class="hm-card-text">{escape(text)}</p>'
        "</div>"
        "</div>"
        "</div>"
    )
