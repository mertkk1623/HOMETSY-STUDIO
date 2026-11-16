"""Tests for the illustrative room diagram and the presentation helpers.

The diagram is a picture, not a validator, so these tests check only what it is
allowed to claim: that it draws a rectangle for the numbers it is given, that it
clips an opening that overflows without crashing, and that its legend still
reads as separate words. Nothing here asserts an opinion about geometry — that
is ``core.room_engine``'s job, and duplicating it here would let the two drift.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from models.schemas import Wall
from ui import diagram, shell, theme
from ui.references import load_references
from workflow.state import WorkflowState

# --------------------------------------------------------------------------- #
# The SVG
# --------------------------------------------------------------------------- #


def build(**overrides: object) -> str:
    payload = {
        "width_cm": 400.0,
        "length_cm": 500.0,
        "door_wall": Wall.SOUTH,
        "door_offset_cm": 60.0,
        "door_width_cm": 90.0,
        "window_wall": Wall.NORTH,
        "window_offset_cm": 120.0,
        "window_width_cm": 160.0,
    }
    payload.update(overrides)
    return diagram.room_diagram_svg(**payload)  # type: ignore[arg-type]


def test_the_diagram_is_a_self_contained_svg() -> None:
    svg = build()
    assert svg.startswith("<svg")
    assert svg.endswith("</svg>")
    # No external references: the image must render offline.
    assert "http" not in svg
    assert "<image" not in svg


def test_the_diagram_marks_itself_as_an_illustration_for_screen_readers() -> None:
    svg = build()
    assert 'role="img"' in svg
    # The accessible name comes from a <title> rather than an aria-label, so the
    # longer description in <desc> is not shadowed by a label attribute.
    assert 'aria-labelledby="' in svg
    assert "<title" in svg
    assert "Illustration" in svg


def test_every_wall_combination_draws_without_raising() -> None:
    for wall in Wall:
        svg = build(door_wall=wall, window_wall=wall)
        assert svg.startswith("<svg")


def test_a_zero_dimension_does_not_divide_by_zero() -> None:
    # The widget cannot produce this, but the function must not explode if a
    # future caller passes an unset value.
    svg = build(width_cm=0.0, length_cm=0.0)
    assert svg.startswith("<svg")


def test_an_opening_wider_than_its_wall_is_clipped_not_crashed() -> None:
    svg = build(door_offset_cm=0.0, door_width_cm=5000.0)
    assert svg.startswith("<svg")
    # The segment is clamped inside the box rather than drawn off-canvas.
    for value in re.findall(r'x1="([\d.]+)"', svg):
        assert 0.0 <= float(value) <= 260.0


def test_the_room_rectangle_uses_the_requested_proportions_not_a_fixed_one() -> None:
    wide = build(width_cm=800.0, length_cm=200.0)
    tall = build(width_cm=200.0, length_cm=800.0)
    assert wide != tall


def test_the_legend_names_both_openings_as_separate_words() -> None:
    text = re.sub(r"<[^>]+>", "", diagram.legend())
    assert "Door" in text
    assert "Window" in text
    # A regression guard: an inline-flex parent once dropped the space and the
    # two labels read as one word.
    assert "DoorWindow" not in text
    assert re.search(r"Door[\s\u00a0]+Window", text)


def test_the_legend_states_the_offset_convention_and_the_scale_caveat() -> None:
    text = re.sub(r"<[^>]+>", "", diagram.legend()).lower()
    assert "west end" in text
    assert "south end" in text
    assert "not to scale" in text


def test_the_legend_marks_the_colour_swatches_as_decorative() -> None:
    # The colour is not the message; the label is.
    assert 'aria-hidden="true"' in diagram.legend()


# --------------------------------------------------------------------------- #
# Text alternatives for both drawings
# --------------------------------------------------------------------------- #


def _desc_of(svg: str) -> str:
    match = re.search(r"<desc[^>]*>(.*?)</desc>", svg, re.DOTALL)
    assert match is not None, "the drawing has no <desc>"
    return match.group(1)


def test_the_room_sketch_describes_itself_in_words() -> None:
    """A screen reader must get the geometry, not just "an illustration".

    The sketch communicates entirely through position and colour. Without a
    description it announces nothing about the room, so the same facts are
    written out: the dimensions, the area, and where each opening sits.
    """

    svg = build()
    assert "<title" in svg and "<desc" in svg
    # The description is linked, not merely present.
    assert "aria-describedby=" in svg and "aria-labelledby=" in svg
    assert 'aria-label="' not in svg, "an aria-label would shadow the <desc>"

    text = _desc_of(svg)
    assert "400" in text and "500" in text
    assert "20.00 square metres" in text
    assert "Door on the south wall" in text
    assert "Window on the north wall" in text
    assert "90 cm wide" in text and "160 cm wide" in text
    assert "not to scale" in text


def test_the_room_sketch_description_follows_the_actual_inputs() -> None:
    # A description that ignored its arguments would pass the test above.
    svg = build(
        width_cm=300.0,
        length_cm=350.0,
        door_wall=Wall.EAST,
        door_offset_cm=45.0,
        door_width_cm=70.0,
        window_wall=Wall.WEST,
        window_offset_cm=88.0,
        window_width_cm=110.0,
    )
    text = _desc_of(svg)
    assert "300" in text and "350" in text
    assert "Door on the east wall" in text
    assert "Window on the west wall" in text
    assert "70 cm wide" in text and "110 cm wide" in text


def test_the_room_sketch_description_cannot_inject_markup() -> None:
    # The values come from the form, so they are untrusted like any other input.
    svg = build()
    assert "&lt;" not in _desc_of(svg)
    hostile = diagram.room_diagram_svg(
        width_cm=400.0,
        length_cm=520.0,
        door_wall="<script>",
        door_offset_cm=60.0,
        door_width_cm=90.0,
        window_wall=Wall.NORTH,
        window_offset_cm=120.0,
        window_width_cm=160.0,
    )
    assert "<script>" not in hostile
    assert "&lt;script&gt;" in hostile


def test_the_plan_describes_every_placed_piece_in_words() -> None:
    from models.schemas import PlacedFootprint

    footprints = [
        PlacedFootprint(
            item_id="sofa_three_seat",
            label="Three-seat sofa",
            left_cm=180.0,
            bottom_cm=0.0,
            width_cm=220.0,
            depth_cm=90.0,
            rotation_degrees=0,
        )
    ]
    svg = diagram.placement_plan_svg(
        width_cm=400.0,
        length_cm=520.0,
        door_wall=Wall.SOUTH,
        door_offset_cm=60.0,
        door_width_cm=90.0,
        window_wall=Wall.NORTH,
        window_offset_cm=120.0,
        window_width_cm=160.0,
        footprints=footprints,
    )
    assert "<title" in svg and "<desc" in svg
    text = _desc_of(svg)
    assert "Three-seat sofa" in text
    assert "220 by 90 centimetres" in text
    assert "at 180, 0 centimetres" in text
    assert "Door on the south wall" in text
    assert "not a construction drawing" in text


def test_the_plan_says_so_when_nothing_could_be_placed() -> None:
    # Silence would read as "the room is empty"; the failure must be stated.
    svg = diagram.placement_plan_svg(
        width_cm=150.0,
        length_cm=150.0,
        door_wall=Wall.SOUTH,
        door_offset_cm=20.0,
        door_width_cm=60.0,
        window_wall=Wall.NORTH,
        window_offset_cm=20.0,
        window_width_cm=60.0,
        footprints=[],
    )
    assert "No furniture could be placed" in _desc_of(svg)


def test_both_drawings_give_their_title_and_description_unique_ids() -> None:
    """Duplicate ids would make the second drawing announce the first's text."""

    sketch = build()
    plan_svg = diagram.placement_plan_svg(
        width_cm=400.0,
        length_cm=520.0,
        door_wall=Wall.SOUTH,
        door_offset_cm=60.0,
        door_width_cm=90.0,
        window_wall=Wall.NORTH,
        window_offset_cm=120.0,
        window_width_cm=160.0,
        footprints=[],
    )
    # Both drawings sit on the same page, so their ids share one namespace.
    ids = re.findall(r'id="([^"]+)"', sketch + plan_svg)
    assert len(ids) == 4, ids
    assert len(ids) == len(set(ids)), f"duplicate id in {ids}"

    # And each drawing really points at its own nodes, not at the other's.
    assert 'aria-labelledby="hm-room-sketch-title"' in sketch
    assert 'aria-labelledby="hm-plan-title"' in plan_svg
    assert "hm-plan-title" not in sketch
    assert "hm-room-sketch-title" not in plan_svg


# --------------------------------------------------------------------------- #
# Theme helpers
# --------------------------------------------------------------------------- #


def test_escape_neutralises_markup() -> None:
    assert theme.escape("<script>") == "&lt;script&gt;"
    assert theme.escape('a "b"') == "a &quot;b&quot;"


def test_the_stylesheet_uses_only_approved_colours() -> None:
    """Every hex value in the CSS must come from the approved token set.

    A stray literal would let the interface drift from ``DESIGN_SYSTEM.md``
    without anyone noticing, because it would look like a deliberate choice.

    ``theme.ACCENT`` is allowed in addition to ``COLORS`` because UI V2 adds two
    decorative hues from the approved asset pack that the product palette has no
    slot for. The brief forbids changing ``COLORS`` (it is pinned equal to the
    PDF palette), so they live in a separate, explicitly non-semantic table —
    see the two tests below, which keep that table from becoming a second
    palette or reaching the report.
    """

    approved = {value.upper() for value in theme.COLORS.values()} | {
        value.upper() for value in theme.ACCENT.values()
    } | {
        "#FFFFFF"  # the on-primary text colour from §3
    }
    for found in re.findall(r"#[0-9A-Fa-f]{6}", theme.APP_CSS):
        assert found.upper() in approved, found


def test_the_decorative_accents_are_not_product_tokens() -> None:
    """``ACCENT`` must stay a decoration table, not a second palette.

    Two ways it could quietly become one, and both are refused here: sharing a
    value with ``COLORS`` (so the same colour has two names) and sharing a value
    with the PDF palette. The report must not move because the screen did.
    """

    from core import report_generator

    product = {value.upper() for value in theme.COLORS.values()}
    accents = {value.upper() for value in theme.ACCENT.values()}
    assert not product & accents
    assert not accents & {value.upper() for value in report_generator.PALETTE.values()}
    # And no accent is addressable through the product table by key.
    assert set(theme.ACCENT) & set(theme.COLORS) == set()


def test_the_decorative_accents_are_never_used_for_text() -> None:
    """An accent is a stroke or a hairline, never a text colour.

    ``#BD8065`` on the warm background is about 2.4:1 — well below the 4.5:1
    this project holds itself to. Reaching ``AA`` would mean either changing the
    approved hue or pretending the ratio is fine; instead the accents are kept
    to decoration an adjacent text label already describes, and this test keeps
    them out of every rule that sets ``color:``.
    """

    body = re.sub(r"</?style>", "", theme.APP_CSS)
    accents = {value.lower() for value in theme.ACCENT.values()}
    for rule in body.split("}"):
        if "{" not in rule:
            continue
        selector, declarations = rule.split("{", 1)
        for declaration in declarations.split(";"):
            if ":" not in declaration:
                continue
            prop, value = declaration.split(":", 1)
            # An accent may frame, fill or stroke an element. It may never be
            # the colour of a glyph.
            assert not (
                prop.strip().lower() == "color" and value.strip().lower() in accents
            ), selector.strip().splitlines()[-1]


def test_the_streamlit_theme_config_matches_the_approved_tokens() -> None:
    """The base page colours are set in Streamlit's own theme, so check them.

    UI V2 adds keys that carry the type stack and the two radii, because those
    are the only documented way to reach Streamlit's own widgets without
    targeting their internal DOM. They are asserted against the same token
    tables the stylesheet uses, so the two can never disagree: a widget and an
    HTML fragment round by the same amount and are set in the same typeface.
    """

    from pathlib import Path

    config_path = Path(__file__).resolve().parents[1] / ".streamlit" / "config.toml"
    assert config_path.exists()

    import tomllib

    config = tomllib.loads(config_path.read_text(encoding="utf-8"))["theme"]
    expected = {
        "primaryColor": theme.COLORS["primary"],
        "backgroundColor": theme.COLORS["background"],
        "secondaryBackgroundColor": theme.COLORS["surface"],
        "textColor": theme.COLORS["text_primary"],
        "borderColor": theme.COLORS["border"],
    }
    for key, colour in expected.items():
        assert config[key].upper() == colour.upper(), key

    # One type stack for the whole application, declared twice on purpose:
    # Streamlit owns the widgets, `APP_CSS` owns the HTML, and a mismatch is
    # exactly the two-typeface bug this pass removes.
    assert config["font"] == theme.FONT_FAMILY
    assert config["headingFont"] == theme.FONT_FAMILY
    assert "font-family: " + theme.FONT_FAMILY in theme.APP_CSS

    # Two radii, one for surfaces and one for controls, shared with the CSS.
    assert config["baseRadius"] == theme.RADIUS["lg"]
    assert config["buttonRadius"] == theme.RADIUS["md"]
    assert config["showWidgetBorder"] is True


def test_the_type_scale_is_ordered_from_largest_to_smallest() -> None:
    """A scale that is not monotonic is not a scale.

    Each step is checked against the next so that a later rule cannot claim to
    be smaller while rendering larger — the kind of drift that makes a heading
    hierarchy look accidental without any single rule being obviously wrong.
    """

    descending = (
        "display",
        "title",
        "metric",
        "section",
        "group",
        "card",
        "lead",
        "body",
        "reading",
        "small",
        "caption",
        "label",
        "micro",
    )
    sizes = [int(theme.TYPE[name].removesuffix("px")) for name in descending]
    assert sizes == sorted(sizes, reverse=True)
    assert len(set(sizes)) == len(sizes)

    # ``metric_narrow`` is a phone variant of ``metric``, not a step between
    # ``section`` and ``group``, so it is excluded above and related here.
    assert int(theme.TYPE["metric_narrow"].removesuffix("px")) < int(
        theme.TYPE["metric"].removesuffix("px")
    )


def test_the_radius_scale_is_monotonic() -> None:
    steps = ("xs", "sm", "md", "lg", "xl")
    values = [int(theme.RADIUS[name].removesuffix("px")) for name in steps]
    assert values == sorted(values)
    assert theme.RADIUS["pill"] == "999px"


def test_the_stylesheet_has_no_hardcoded_font_size() -> None:
    """Every size comes from ``TYPE``, so the scale cannot drift one rule at a time.

    A literal here would be invisible in review: it looks the same as a token
    once the f-string has been evaluated, so the only way to tell them apart is
    to compare the rendered values back against the table.
    """

    body = re.sub(r"/\*.*?\*/", "", theme.APP_CSS, flags=re.DOTALL)
    sized = re.findall(r"font-size:\s*([^;]+);", body)
    assert sized
    for value in sized:
        assert value.strip() in theme.TYPE.values(), value


def test_the_stylesheet_is_scoped_to_the_application_class() -> None:
    """Every rule is qualified, so nothing leaks into Streamlit's own DOM.

    Two selectors are allowed, and only two:

    * ``.hm-page`` — a class this application renders itself, on every fragment
      it emits. All element styling lives under it.
    * ``[class*="st-key-…"]`` — an *attribute* prefix matching the class
      Streamlit documents for ``st.container(key=...)`` / ``st.button(key=...)``.
      Keys are minted by this application (``style-*``, ``palette-*``,
      ``hm-concept-*``), so the selector names a hook we control. It reached
      Streamlit's rules for that container, not its generated class names, and
      it fails safe: if the key changes, the card returns to Streamlit's default
      chrome and nothing breaks.

    What stays forbidden is the real fragility: a bare ``st-emotion-cache-*``
    hash, a ``[data-testid=…]`` internal, or an unqualified tag/class selector
    that would restyle unrelated parts of the page.
    """

    body = re.sub(r"</?style>", "", theme.APP_CSS)
    # Comments explain why rules exist; they are stripped here so that a comment
    # that *mentions* a forbidden selector does not read as one.
    stripped = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    rules = [rule.strip() for rule in stripped.split("}") if "{" in rule]
    assert rules
    for rule in rules:
        selector = rule.split("{")[0].strip()
        if not selector or selector.startswith("/*"):
            continue
        for part in selector.split(","):
            part = part.strip()
            if not part:
                continue
            allowed = (
                part.startswith(".hm-page")
                or part.startswith("@")
                or part.startswith('[class*="st-key-')
            )
            assert allowed, part

    # And the forbidden forms appear in no selector.
    selectors = [rule.split("{")[0] for rule in stripped.split("}") if "{" in rule]
    joined = " ".join(selectors)
    assert "st-emotion-cache-" not in joined
    assert "data-testid" not in joined
    assert "data-baseweb" not in joined


def test_the_progress_strip_carries_an_accessible_name() -> None:
    """A list of five items with no name is indistinguishable from any other list.

    The strip is the one place a screen reader can answer "where am I" in a
    single stop, so it is named. Its items still state their own condition in
    words (see the status-label test below), never through colour alone.
    """

    markup = shell.stage_strip("Room Setup", WorkflowState())
    assert markup.startswith('<ul class="hm-stage-strip" aria-label="Workflow progress"')
    # The name is on the list, not repeated on each item.
    assert markup.count("aria-label=") == 1


def test_every_status_label_exists_in_words() -> None:
    # Colour alone must never carry a state (DESIGN_SYSTEM.md §7).
    for key in theme.STATUS_LABELS:
        assert theme.STATUS_LABELS[key].strip()
        assert theme.STATUS_LABELS[key] != key


def test_the_css_is_one_string_with_no_remote_import() -> None:
    assert "@import" not in theme.APP_CSS
    assert "url(http" not in theme.APP_CSS


def test_wide_tables_cannot_push_the_page_into_horizontal_scroll() -> None:
    """Regression: the six-column cost table overflowed narrow screens.

    At 404 px the table kept a fixed minimum width (``white-space: nowrap`` on
    every numeric cell), so the document itself became ~66 px wider than the
    viewport and the whole page scrolled sideways instead of the table. The fix
    is a narrow-screen block that lets numbers wrap and gives any table that
    still does not fit its own scroll box.

    Asserting on the stylesheet keeps the rule from being dropped or weakened
    without a browser: the visible symptom returned whenever it was absent.
    """

    narrow = re.search(
        r"@media\s*\(max-width:\s*640px\)\s*\{(?P<body>.*?)\n  \}",
        theme.APP_CSS,
        re.DOTALL,
    )
    assert narrow is not None, "the narrow-screen table block is missing"
    body = narrow.group("body")

    # Numbers must be allowed to wrap, or a money column cannot shrink.
    numeric = re.search(
        r"\.hm-page \.hm-table td\.hm-num\s*\{(?P<body>[^}]*)\}", body
    )
    assert numeric is not None
    assert re.search(r"white-space:\s*normal", numeric.group("body"))

    # And a table that still needs more room scrolls inside itself, not the page.
    table = re.search(r"\.hm-page \.hm-table\s*\{(?P<body>[^}]*)\}", body)
    assert table is not None
    table_body = table.group("body")
    assert re.search(r"overflow-x:\s*auto", table_body)
    assert re.search(r"max-width:\s*100%", table_body)


# --------------------------------------------------------------------------- #
# The validated design plan
# --------------------------------------------------------------------------- #


def placed(
    label: str = "Three-seat sofa",
    *,
    item_id: str = "sofa_three_seat",
    left_cm: float = 40.0,
    bottom_cm: float = 20.0,
    width_cm: float = 220.0,
    depth_cm: float = 90.0,
    rotation: int = 0,
) -> object:
    from models.schemas import PlacedFootprint

    return PlacedFootprint(
        item_id=item_id,
        label=label,
        left_cm=left_cm,
        bottom_cm=bottom_cm,
        width_cm=width_cm,
        depth_cm=depth_cm,
        rotation_degrees=rotation,
    )


def plan(**overrides: object) -> str:
    payload = {
        "width_cm": 400.0,
        "length_cm": 500.0,
        "door_wall": Wall.SOUTH,
        "door_offset_cm": 60.0,
        "door_width_cm": 90.0,
        "window_wall": Wall.NORTH,
        "window_offset_cm": 120.0,
        "window_width_cm": 160.0,
        "footprints": [placed()],
    }
    payload.update(overrides)
    return diagram.placement_plan_svg(**payload)  # type: ignore[arg-type]


def test_the_plan_is_a_self_contained_svg() -> None:
    svg = plan()
    assert svg.startswith("<svg")
    assert svg.endswith("</svg>")
    # Offline: no external reference may become a runtime dependency.
    assert "http" not in svg
    assert "<image" not in svg


def test_the_plan_is_marked_as_an_image_with_a_description() -> None:
    svg = plan()
    assert 'role="img"' in svg
    # The accessible name and description are referenced by id, so a screen
    # reader announces both instead of only a short label.
    assert 'aria-labelledby="' in svg and 'aria-describedby="' in svg
    assert "Validated" in svg or "validated" in svg


def test_the_plan_draws_the_room_from_its_real_dimensions() -> None:
    svg = plan(width_cm=400.0, length_cm=500.0)
    # The dimension annotations carry the measured numbers, not a scaled guess.
    assert "400 × 500 cm" in svg
    assert "20.00 m²" in svg
    # And the origin convention is stated in the picture.
    assert "south-west" in svg


def test_the_plan_draws_every_placed_footprint() -> None:
    svg = plan(
        footprints=[
            placed("Three-seat sofa", left_cm=40.0, bottom_cm=20.0),
            placed(
                "Coffee table",
                item_id="coffee_table",
                left_cm=100.0,
                bottom_cm=180.0,
                width_cm=100.0,
                depth_cm=60.0,
            ),
        ]
    )
    # Each footprint is drawn once in the drawing body. Its name also appears in
    # the text alternative, so the count excludes <title>/<desc>.
    drawing = re.sub(r"<desc.*?</desc>|<title.*?</title>", "", svg, flags=re.DOTALL)
    assert drawing.count("Three-seat sofa") == 1
    assert drawing.count("Coffee table") == 1
    # ...and both are described for a screen reader too.
    desc = _desc_of(svg)
    assert "Three-seat sofa" in desc and "Coffee table" in desc
    # Two furniture blocks, each a filled rectangle.
    assert drawing.count('fill="#DDD8CB"') == 2


def test_the_plan_labels_a_block_with_its_size() -> None:
    svg = plan(footprints=[placed(width_cm=220.0, depth_cm=90.0)])
    assert "220 × 90" in svg


def test_a_small_block_gets_a_wrapped_label_not_a_fragment() -> None:
    """A long name in a narrow block would overflow it.

    The label wraps rather than truncating to its first word: "Narrow" alone
    reads as a different piece of furniture, while "Narrow side / table" does not.
    """

    svg = plan(
        footprints=[
            placed(
                "Narrow side table",
                item_id="side_table",
                width_cm=70.0,
                depth_cm=60.0,
            )
        ]
    )
    spans = re.findall(r"<tspan[^>]*>([^<]*)</tspan>", svg)
    assert spans, "the label was not drawn at all"
    assert spans == ["Narrow side", "table"]
    # Every word survives, in order — no fragment stands in for the name.
    assert " ".join(spans) == "Narrow side table"
    # And it is never claimed inside the block as one unbroken run.
    assert ">Narrow side table<" not in svg


def test_a_block_too_small_for_text_still_draws() -> None:
    svg = plan(
        footprints=[
            placed(
                "Tiny",
                item_id="tiny",
                width_cm=20.0,
                depth_cm=20.0,
            )
        ]
    )
    assert svg.count('fill="#DDD8CB"') == 1
    assert svg.endswith("</svg>")


def test_an_empty_plan_draws_the_room_but_no_furniture() -> None:
    """A failure shows the space the failure refers to, not a blank panel."""

    svg = plan(footprints=[])
    assert svg.startswith("<svg")
    assert 'fill="#DDD8CB"' not in svg
    # The room and its openings are still drawn.
    assert "400 × 500 cm" in svg
    assert svg.count("<line") >= 2


def test_the_plan_uses_the_footprint_coordinates_it_is_given() -> None:
    """The drawing is not allowed to compute its own geometry."""

    left, bottom, width, depth = 40.0, 20.0, 220.0, 90.0
    svg = plan(
        footprints=[
            placed(
                left_cm=left,
                bottom_cm=bottom,
                width_cm=width,
                depth_cm=depth,
            )
        ]
    )
    # The scale is the plan's, so the expected pixel values are derived here from
    # the same rule the module documents, and the block must match exactly.
    from ui.diagram import _PLAN_H, _PLAN_PAD, _PLAN_W

    scale = min(
        (_PLAN_W - 2 * _PLAN_PAD) / 400.0, (_PLAN_H - 2 * _PLAN_PAD) / 500.0
    )
    x0 = (_PLAN_W - 400.0 * scale) / 2
    y0 = (_PLAN_H - 500.0 * scale) / 2
    expected_x = x0 + left * scale
    expected_top = _PLAN_H - (y0 + (bottom + depth) * scale)
    assert f'x="{expected_x:.1f}"' in svg
    assert f'y="{expected_top:.1f}"' in svg
    assert f'width="{width * scale:.1f}"' in svg
    assert f'height="{depth * scale:.1f}"' in svg


def test_the_plan_escapes_a_hostile_label() -> None:
    svg = plan(
        footprints=[
            placed("<script>alert(1)</script>", item_id="hostile")
        ]
    )
    assert "<script>" not in svg
    assert "&lt;script&gt;" in svg


def test_a_partial_plan_describes_itself_as_partly_placed_not_validated() -> None:
    """A plan missing requested items must not be announced as validated.

    The screen already says "partial plan" in a badge; the accessible name is
    what a screen-reader user hears first, so it has to agree with the badge or
    the two contradict each other in the same view.
    """

    complete = plan()
    partial = plan(partial=True)

    assert "Scaled plan of the validated furniture layout" in complete
    assert "Some requested items could not be placed" not in complete

    assert "Scaled plan of the partly placed furniture layout" in partial
    assert "validated furniture layout" not in partial
    # The omission is stated in the description too, not only in the title.
    assert "Some requested items could not be placed" in partial
    # And the geometry is untouched: the same room, the same placed piece.
    assert "400 × 500 cm" in partial
    assert "Three-seat sofa" in partial


def test_a_complete_plan_is_not_described_as_partial() -> None:
    """The flag defaults to complete, so callers that place everything are safe."""

    svg = plan(partial=False)
    assert "partly placed" not in svg
    assert "could not be placed" not in svg


def test_the_plan_legend_names_every_mark_in_words() -> None:
    markup = diagram.plan_legend()
    assert "Placed furniture" in markup
    assert "Door" in markup
    assert "Window" in markup
    assert "Room boundary" in markup
    # And it says what the drawing is not.
    assert "not a construction or building-code drawing" in markup
    assert "illustrative" in markup.lower()


def test_the_plan_caption_describes_what_the_labels_now_do() -> None:
    """Regression: the caption still promised labels were shortened.

    Phase 8 replaced the first-word fallback with a wrapped label, so a caption
    saying labels are "shortened on small blocks" described the previous
    behaviour. An inaccurate caption is worse than none: it tells the reader to
    reinterpret a label that is in fact the whole name on two lines.
    """

    markup = diagram.plan_legend()
    assert "shortened" not in markup.lower()
    # What it does say has to match the renderer: wrapped names, then no label.
    assert "wrap" in markup.lower()
    assert "too small" in markup.lower()
    assert "beside the plan" in markup


def test_the_plan_legend_labels_are_separated_for_text_extraction() -> None:
    markup = diagram.plan_legend()
    plain = re.sub(r"<[^>]+>", "", markup)
    # A flex parent must not swallow the space between two entries.
    assert "Placed furniture Door" in re.sub(r"\s+", " ", plain)


# --------------------------------------------------------------------------- #
# Reference library
# --------------------------------------------------------------------------- #


def test_the_library_covers_every_approved_style_and_palette() -> None:
    from models.schemas import DesignStyle, PaletteDirection

    library = load_references()
    assert {reference.style for reference in library.styles} == set(DesignStyle)
    assert {reference.palette for reference in library.palettes} == set(
        PaletteDirection
    )
    # Each exactly once, so no card is drawn twice.
    assert len(library.styles) == len(DesignStyle)
    assert len(library.palettes) == len(PaletteDirection)


def test_every_reference_image_exists_and_is_not_empty() -> None:
    library = load_references()
    for reference in (*library.styles, *library.palettes):
        assert reference.image_path.exists(), reference.image_path
        assert reference.image_path.stat().st_size > 0
        # Local only: a remote URL would be a runtime dependency.
        assert "http" not in str(reference.image_path)


def test_every_reference_has_a_name_and_a_description() -> None:
    library = load_references()
    for reference in (*library.styles, *library.palettes):
        assert reference.name.strip()
        assert reference.description.strip()


def test_palettes_expose_swatches_for_the_card() -> None:
    library = load_references()
    for palette in library.palettes:
        assert palette.swatches, palette.palette
        for colour in palette.swatches:
            assert re.fullmatch(r"#[0-9A-Fa-f]{6}", colour), colour


def test_the_library_lookup_helpers_agree_with_the_cards() -> None:
    library = load_references()
    for reference in library.styles:
        assert library.image_for_style(reference.style) == reference.image_path
    for reference in library.palettes:
        assert library.image_for_palette(reference.palette) == reference.image_path


def test_every_reference_image_is_given_alt_text() -> None:
    """A reference image with no ``alt`` is announced as an unlabelled graphic.

    The images are illustrative, so the alternative text says what they are
    rather than describing the picture: the name and description printed beside
    each card carry the actual meaning.
    """

    pages = Path(__file__).resolve().parents[1] / "ui"
    sources = {
        name: (pages / name).read_text(encoding="utf-8")
        for name in ("pages_preferences.py", "pages_concepts.py")
    }

    for name, source in sources.items():
        calls = re.findall(r"st\.image\((.*?)\)\n", source, re.DOTALL)
        assert calls, f"no st.image call found in {name}"
        for call in calls:
            assert "alt=" in call, f"{name}: st.image call without alt text"

    # And the text says the image is illustrative and names the direction.
    assert "Illustrative reference image" in sources["pages_preferences.py"]
    assert "Illustrative reference image" in sources["pages_concepts.py"]


@pytest.mark.parametrize("name", ["styles", "palettes"])
def test_the_library_is_verified_at_load_time(name: str) -> None:
    """A missing image must fail loudly instead of drawing a broken card."""

    from ui import references as module

    original = module._load_json

    def broken(path):
        payload = original(path)
        payload[name] = payload[name][:-1]
        return payload

    module._load_json = broken
    module.load_references.cache_clear()
    try:
        with pytest.raises(module.ReferenceError):
            module.load_references()
    finally:
        module._load_json = original
        module.load_references.cache_clear()

    # And the real library still loads afterwards.
    assert len(module.load_references().styles) == 6


# --------------------------------------------------------------------------- #
# Phase 8: contrast, label fitting and progress vocabulary
# --------------------------------------------------------------------------- #


def _relative_luminance(colour: str) -> float:
    """WCAG 2.1 relative luminance of a ``#RRGGBB`` value."""

    value = colour.lstrip("#")
    channels = [int(value[index : index + 2], 16) / 255 for index in (0, 2, 4)]

    def linearise(channel: float) -> float:
        if channel <= 0.03928:
            return channel / 12.92
        return ((channel + 0.055) / 1.055) ** 2.4

    red, green, blue = (linearise(channel) for channel in channels)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _contrast_ratio(foreground: str, background: str) -> float:
    """WCAG 2.1 contrast ratio, 1:1 to 21:1."""

    first = _relative_luminance(foreground)
    second = _relative_luminance(background)
    lighter, darker = max(first, second), min(first, second)
    return (lighter + 0.05) / (darker + 0.05)


@pytest.mark.parametrize(
    "token", ["text_secondary", "success", "warning", "error"]
)
def test_the_status_tokens_clear_the_aa_contrast_minimum(token: str) -> None:
    """Every coloured token must reach 4.5:1 on all three product surfaces.

    A real axe-core scan measured ``success`` at 3.61:1 on the muted surface and
    ``text_secondary`` at 4.24:1 — both below the WCAG 2.1 AA minimum, on 11px
    uppercase badge text that gets no large-text exemption. The scan is an
    external instrument, so the rule it enforced is pinned here: any future
    palette change that undoes the fix fails this test rather than silently
    regressing the badge contrast.
    """

    for surface in ("surface_muted", "background", "surface"):
        ratio = _contrast_ratio(theme.COLORS[token], theme.COLORS[surface])
        assert ratio >= 4.5, (
            f"{token} on {surface}: {ratio:.2f}:1 is below the 4.5:1 minimum"
        )


def test_the_text_primary_and_primary_tokens_also_clear_the_minimum() -> None:
    """Body and heading text is the most-read text in the product."""

    for token in ("text_primary", "primary", "primary_dark"):
        for surface in ("surface_muted", "background", "surface"):
            ratio = _contrast_ratio(theme.COLORS[token], theme.COLORS[surface])
            assert ratio >= 4.5, f"{token} on {surface}: {ratio:.2f}:1"


def test_the_pdf_palette_matches_the_interface_palette() -> None:
    """The report and the screen must not drift apart.

    Duplicated rather than imported so ``core.report_generator`` stays free of
    the presentation layer; the duplication is what makes this assertion worth
    having.
    """

    from core import report_generator

    assert report_generator.PALETTE == theme.COLORS


def test_the_plan_frame_scrolls_its_drawing_instead_of_shrinking_it() -> None:
    """Regression: at 390 px the plan's labels rendered at 4.56 px.

    The drawing is a 640-unit viewBox scaled to the frame width, so on a phone
    every label shrank below legibility. The frame keeps the drawing at its own
    scale and scrolls inside itself, which never makes the page wider than the
    viewport — the failure mode the narrow-screen table rules already prevent.
    """

    frame = re.search(r"\.hm-page \.hm-plan-frame\s*\{(?P<body>[^}]*)\}", theme.APP_CSS)
    assert frame is not None
    assert re.search(r"overflow-x:\s*auto", frame.group("body"))

    drawing = re.search(
        r"\.hm-page \.hm-plan-frame > svg\s*\{(?P<body>[^}]*)\}", theme.APP_CSS
    )
    assert drawing is not None, "the minimum plan width rule is missing"
    minimum = re.search(r"min-width:\s*(\d+)px", drawing.group("body"))
    assert minimum is not None
    # The floor is the drawing's own viewBox width, so a 9-unit label is never
    # rendered smaller than 9 CSS px. A smaller floor brings back the 4.6 px
    # labels this rule exists to prevent.
    from ui.diagram import _PLAN_W

    assert int(minimum.group(1)) >= int(_PLAN_W)


def test_the_narrow_screen_stage_strip_is_a_two_column_grid() -> None:
    """Regression: five stacked stage cards took 221 px of an 844 px viewport.

    That is 26% of the first screen before the page title appears, on every
    screen. The grid is asserted rather than the height because the height is a
    browser measurement, while ``grid-template-columns`` is the rule that
    produces it.
    """

    narrow = re.search(
        r"@media\s*\(max-width:\s*640px\)\s*\{(?P<body>.*?)\n  \}",
        theme.APP_CSS,
        re.DOTALL,
    )
    assert narrow is not None
    body = narrow.group("body")

    strip = re.search(r"\.hm-page \.hm-stage-strip\s*\{(?P<body>[^}]*)\}", body)
    assert strip is not None, "the narrow-screen stage-strip rule is missing"
    assert re.search(r"display:\s*grid", strip.group("body"))
    assert re.search(r"grid-template-columns:\s*1fr\s+1fr", strip.group("body"))


def test_a_money_metric_is_not_broken_after_its_decimal_comma() -> None:
    """Regression: "41.800,00 TRY" wrapped into "41.800," and "00 TRY".

    A comma is a permitted break opportunity for the line breaker, and the
    Turkish money format puts one in the middle of every figure. The number is
    one token, so the card must not break it — the value wraps as a whole, or
    shrinks on a narrow screen, but never splits mid-number.
    """

    value = re.search(
        r"\.hm-page \.hm-metric-value\s*\{(?P<body>[^}]*)\}", theme.APP_CSS
    )
    assert value is not None, "the metric value rule is missing"
    assert re.search(r"white-space:\s*nowrap", value.group("body"))

    # And the narrow-screen block shrinks it, so "nowrap" cannot overflow a
    # 160 px metric card on a phone.
    narrow = re.search(
        r"@media\s*\(max-width:\s*640px\)\s*\{(?P<body>.*?)\n  \}",
        theme.APP_CSS,
        re.DOTALL,
    )
    assert narrow is not None
    small = re.search(
        r"\.hm-page \.hm-metric-value\s*\{(?P<body>[^}]*)\}", narrow.group("body")
    )
    assert small is not None, "no narrow-screen metric value rule"
    size = re.search(r"font-size:\s*(\d+)px", small.group("body"))
    assert size is not None
    assert int(size.group(1)) < 26, "the phone rule must be smaller than the default"


def test_a_label_is_dropped_when_the_block_cannot_hold_it() -> None:
    """A scale-aware label, not a fixed one.

    The same 45 × 45 cm block is drawn at a different width in a small room and a
    large one, so the fitting decision has to come from the drawn width. The
    previous rule only checked the physical dimensions, which is why "Bookshelf"
    overran its block at 390 px while fitting at 1440 px.
    """

    from ui import diagram as module

    footprint = placed("Bookshelf", item_id="bookshelf", width_cm=45.0, depth_cm=35.0)
    # "Bookshelf" is nine characters, so at 9 units it needs ~45 user units.
    assert module._estimated_text_width("Bookshelf", 9.0) > 44

    # Plenty of room: the full name survives.
    assert module._label_for(footprint, available=200.0) == "Bookshelf"
    # Just enough for the word and its margin.
    assert module._label_for(footprint, available=55.0) == "Bookshelf"
    # Too narrow even for the one word: nothing is drawn rather than text that
    # overruns its block. A single word cannot be wrapped any smaller.
    assert module._label_for(footprint, available=28.0) == ""


def test_a_two_word_label_wraps_instead_of_losing_a_word() -> None:
    """The fragment problem: "Floor" alone names nothing useful.

    A block that is narrow but tall gets the name on two lines, so the reader
    sees "Floor lamp" rather than "Floor" — a plan label has to stay a name.
    """

    from ui import diagram as module

    footprint = placed("Floor lamp", item_id="floor_lamp", width_cm=40.0, depth_cm=40.0)
    # One line cannot hold it, two can.
    assert module._label_for(footprint, available=30.0, max_lines=1) == ""
    assert module._label_for(footprint, available=30.0, max_lines=2) == "Floor lamp"


def test_a_wrapped_label_is_split_into_separate_lines_in_the_drawing() -> None:
    """The wrap is drawn, not just joined back into one over-wide run."""

    svg = plan(
        footprints=[
            placed(
                "Coffee table",
                item_id="coffee_table",
                width_cm=60.0,
                depth_cm=100.0,
            )
        ]
    )
    spans = re.findall(r"<tspan[^>]*>([^<]*)</tspan>", svg)
    assert spans, "the label was not wrapped onto lines"
    assert "Coffee" in spans
    # Together the spans still spell the whole name.
    assert " ".join(part for part in spans if part) .strip() in svg or len(spans) > 1


def test_the_label_fitting_is_driven_by_the_drawn_width_not_the_centimetres() -> None:
    """The regression that mattered: the same piece in two rooms.

    A 90 cm two-seat sofa is a "large" block by centimetres and always kept its
    full name, yet in a small room the drawing scales down until that name no
    longer fits. Two identical footprints therefore get different labels, which
    is only possible if the decision comes from the drawn width.
    """

    from ui import diagram as module

    sofa = placed(
        "Two-seat sofa", item_id="sofa_two_seat", width_cm=90.0, depth_cm=90.0
    )
    # At full scale the block is wide enough for the whole name on one line.
    assert module._label_for(sofa, available=95.0) == "Two-seat sofa"
    # Shrunk, the name wraps rather than losing a word.
    assert module._label_for(sofa, available=50.0, max_lines=2) == "Two-seat sofa"
    # With no second line available and no room for the whole name, the block
    # gets no label rather than the misleading fragment "Two-seat".
    assert module._label_for(sofa, available=50.0, max_lines=1) == ""


def test_a_multi_word_label_wraps_rather_than_losing_a_word() -> None:
    from ui import diagram as module

    footprint = placed(
        "Coffee table", item_id="coffee_table", width_cm=60.0, depth_cm=60.0
    )
    # "Coffee table" needs about 60 user units at 9 units tall, so a 40-unit
    # block cannot hold it on one line but can hold it on two.
    assert module._label_for(footprint, available=40.0, max_lines=2) == (
        "Coffee table"
    )
    assert module._label_for(footprint, available=40.0, max_lines=1) == ""
    # Wide enough for the whole thing, the wrap is not needed at all.
    assert module._label_for(footprint, available=120.0) == "Coffee table"


def test_a_label_that_needs_too_many_lines_is_left_off() -> None:
    """Three words in a very narrow block is not a wrap, it is a guess.

    The plan is illustrative, so an unlabelled block with its name in the list
    below is honest; three stacked fragments are not.
    """

    from ui import diagram as module

    footprint = placed(
        "Large potted plant", item_id="plant", width_cm=40.0, depth_cm=40.0
    )
    # Each word fits alone, but the name needs three lines and only two exist.
    assert module._wrap_label("Large potted plant", 40.0, 2) == []
    assert module._label_for(footprint, available=40.0, max_lines=2) == ""


def test_the_drawn_label_never_overruns_its_block_at_phone_scale() -> None:
    """The end-to-end assertion: what is drawn fits what is drawn.

    A 390 px viewport draws the 640-unit plan at roughly 324 px, a scale of
    0.506. At that scale the blocks in a 400 × 500 cm room are small, so this is
    the case that used to overflow.
    """

    from ui import diagram as module

    svg = plan(
        footprints=[
            placed("Bookshelf", item_id="bookshelf", width_cm=45.0, depth_cm=35.0),
            placed(
                "Two-seat sofa",
                item_id="sofa_two_seat",
                left_cm=100.0,
                width_cm=90.0,
                depth_cm=180.0,
            ),
        ]
    )

    # Whatever label survives, every drawn line must fit the block drawn for it.
    # The estimate is the module's own, so this checks the decision rather than
    # re-deriving it.
    blocks = re.findall(
        r'<g><rect x="[\d.]+" y="[\d.]+" width="(?P<w>[\d.]+)"[^>]*/>(?P<rest>.*?)</g>',
        svg,
        re.DOTALL,
    )
    assert blocks, "no furniture blocks were drawn"
    checked = 0
    for width_text, rest in blocks:
        width = float(width_text)
        for size_text, line in re.findall(
            r'font-size="(?P<size>[\d.]+)"[^>]*>(?P<line>[^<]*)<', rest
        ):
            if not line.strip():
                continue
            assert (
                module._estimated_text_width(line, float(size_text)) <= width
            ), f"label {line!r} needs more than the {width:.1f} units drawn for it"
            checked += 1
    assert checked, "no labels were checked"
