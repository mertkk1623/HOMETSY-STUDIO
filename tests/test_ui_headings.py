"""Heading structure: what a screen reader navigates by.

A manual accessibility-tree inspection of the running application found that the
one heading naming each screen was an ``h2``, and every section heading inside a
screen — "Room", "Door", "Window", "Layout preview", "Spatial validation" — was a
plain ``<p>``. Heading navigation, which is the main way a screen-reader user
skims a form, therefore reached the page title and nothing else.

These tests pin the structure that replaced it: one ``h1`` per screen, section
headings as ``h2``, card and block names as ``h3``, and no skipped levels. They
assert the *tags*, not the words, because the words are pinned by the copy tests
and the styling is unchanged by construction (``APP_CSS`` styles the classes and
a reset makes the inherited text presentation match what a ``<p>`` had).

Note on axe: ``page-has-heading-one`` in axe-core 4.10.2 reported ``pass`` on a
page with zero ``h1`` elements, so the earlier "zero violations" result was not
evidence about headings. These tests are.
"""

from __future__ import annotations

import html
import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from core.budget_engine import compute_budget
from models.schemas import (
    ConceptCollection,
    DesignBrief,
    DesignConcept,
    DesignEvaluation,
    DesignRecommendation,
    FurnitureRecommendation,
)
from ui import layout, references, theme
from workflow.dependencies import DataKey
from workflow.state import WorkflowState, WorkflowStep

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "app.py"

ROOM_FORM_SUBMIT = "FormSubmitter:hm_room_form-Save room information"
PREFERENCES_FORM_SUBMIT = (
    "FormSubmitter:hm_preferences_form-Save preferences and budget"
)

HEADING_RE = re.compile(r"<h([1-6])\b[^>]*>(.*?)</h\1>", re.DOTALL)


# --------------------------------------------------------------------------- #
# Reading the rendered headings
# --------------------------------------------------------------------------- #


def assert_no_exceptions(at: AppTest) -> None:
    exceptions = [element.message for element in at.exception]
    assert exceptions == [], exceptions


def headings(at: AppTest) -> list[tuple[int, str]]:
    """Every heading the browser would expose, in document order.

    The stylesheet is injected as markdown too, so it is removed first: the CSS
    text contains no headings, but keeping it would make failures unreadable.
    """

    markup = "\n".join(element.value for element in at.markdown)
    markup = re.sub(r"<style>.*?</style>", "", markup, flags=re.DOTALL)
    found = []
    for level, inner in HEADING_RE.findall(markup):
        text = " ".join(html.unescape(re.sub(r"<[^>]+>", "", inner)).split())
        found.append((int(level), text))
    return found


def assert_one_h1(at: AppTest, expected: str) -> None:
    """Exactly one level-one heading, and it is the title of the screen."""

    found = headings(at)
    level_ones = [text for level, text in found if level == 1]
    assert level_ones == [expected], (
        f"expected exactly one h1 reading {expected!r}, found {level_ones!r}"
    )


def assert_no_skipped_levels(at: AppTest) -> None:
    """Heading levels descend one step at a time, as screen readers expect."""

    found = headings(at)
    assert found, "the screen has no headings at all"
    assert found[0][0] == 1, f"the first heading must be an h1, got {found[0]}"
    previous = 1
    for level, text in found[1:]:
        assert level <= previous + 1, (
            f"{text!r} is an h{level} after an h{previous}, which skips a level"
        )
        previous = level


# --------------------------------------------------------------------------- #
# The helpers themselves
# --------------------------------------------------------------------------- #


def test_the_page_title_is_the_h1() -> None:
    markup = theme.page_intro("Stage 1 of 5 · Room", "Describe the room", "Intro.")
    assert markup.count("<h1") == 1
    assert '<h1 class="hm-page-title">Describe the room</h1>' in markup
    # The eyebrow stays a paragraph: it is a label, not the name of the screen.
    assert '<p class="hm-eyebrow">Stage 1 of 5 · Room</p>' in markup


def test_a_group_heading_is_an_h2() -> None:
    assert theme.group_heading("Room") == '<h2 class="hm-group">Room</h2>'


def test_the_group_note_stays_a_paragraph() -> None:
    markup = theme.group_heading("Room", "Measured in centimetres.")
    assert markup == (
        '<h2 class="hm-group">Room</h2>'
        '<p class="hm-group-note">Measured in centimetres.</p>'
    )


def test_a_block_title_is_an_h3_by_default() -> None:
    assert theme.block_title("Constraints") == (
        '<h3 class="hm-block-title">Constraints</h3>'
    )


def test_a_block_title_can_be_promoted_to_a_section() -> None:
    """One block sits directly under the page title rather than under a group."""

    assert theme.block_title("Style reference", level=2) == (
        '<h2 class="hm-block-title">Style reference</h2>'
    )


def test_a_block_title_rejects_a_level_below_the_page_title() -> None:
    """An h1 inside a page that already has one would split the document."""

    for level in (1, 4, 0):
        with pytest.raises(ValueError):
            theme.block_title("Nope", level=level)


def test_the_landing_helpers_are_headings_too() -> None:
    assert theme.section_heading("Roadmap") == (
        '<h2 class="hm-section-label">Roadmap</h2>'
    )
    assert theme.card_heading("Structured requirements") == (
        '<h3 class="hm-card-title">Structured requirements</h3>'
    )
    assert theme.card_name("Japandi") == '<h3 class="hm-card-name">Japandi</h3>'


def test_a_card_heading_can_carry_an_inline_style() -> None:
    """The roadmap used inline spacing on its title; it still can."""

    markup = theme.card_heading("V1 · Complete", style="margin-top:14px;")
    assert markup == (
        '<h3 class="hm-card-title" style="margin-top:14px;">V1 · Complete</h3>'
    )


@pytest.mark.parametrize(
    "helper",
    [
        lambda: theme.block_title("<script>x</script>"),
        lambda: theme.card_heading("<b>bold</b>"),
        lambda: theme.card_name("<img src=x onerror=y>"),
        lambda: theme.section_heading("<i>italic</i>"),
    ],
)
def test_heading_text_is_still_escaped(helper) -> None:
    """Turning a label into a heading must not turn text into markup."""

    markup = helper()
    assert "<script>" not in markup
    assert "<b>" not in markup
    assert "<img" not in markup
    assert "<i>" not in markup


def test_the_landing_title_helper_is_the_h1() -> None:
    assert theme.page_title("HOMETSY") == '<h1 class="hm-title">HOMETSY</h1>'


def test_no_page_writes_a_heading_class_on_a_paragraph() -> None:
    """The source-level guard: the classes that mean "heading" are headings.

    A future page that hand-writes ``<p class="hm-group">`` would quietly bring
    back the original defect, so the absence is asserted across every page.
    """

    heading_classes = (
        "hm-page-title",
        "hm-group",
        "hm-section-label",
        "hm-card-title",
        "hm-card-name",
        "hm-block-title",
    )
    offenders = []
    for path in sorted((PROJECT_ROOT / "ui").glob("pages_*.py")):
        source = path.read_text(encoding="utf-8")
        for css_class in heading_classes:
            for pattern in (
                f'<p class="{css_class}"',
                f"<p class='{css_class}'",
                f'<div class="{css_class}"',
            ):
                if pattern in source:
                    offenders.append(f"{path.name}: {pattern}")
    assert offenders == [], offenders


def test_the_reset_covers_the_heading_tags_the_helpers_emit() -> None:
    """Appearance is preserved per class, so every class must be covered.

    The reset is not global (see the test below for why); it names the classes
    whose tag changed. A class added later without a rule would inherit
    Streamlit's heading typeface and padding instead of its paragraph look.
    """

    css = theme.APP_CSS
    for css_class in (
        "hm-section-label",
        "hm-group",
        "hm-card-title",
        "hm-card-name",
        "hm-block-title",
    ):
        assert f".hm-page .{css_class}" in css, css_class


# --------------------------------------------------------------------------- #
# Driving the real application
# --------------------------------------------------------------------------- #


def fresh_app() -> AppTest:
    at = AppTest.from_file(str(APP_PATH), default_timeout=90).run()
    assert_no_exceptions(at)
    return at


def click(at: AppTest, label: str) -> AppTest:
    matches = [button for button in at.button if button.label == label]
    assert matches, (
        f"No button labelled {label!r}. Have: {[b.label for b in at.button]}"
    )
    matches[0].click().run()
    assert_no_exceptions(at)
    return at


def make_concept(name: str) -> DesignConcept:
    return DesignConcept(
        name=name,
        description=f"{name} arranges the room around seating pulled to the edges.",
        design_direction="Seating pulled to the edges.",
        color_and_material_direction="Pale oak, undyed linen, oatmeal wool.",
        furniture_approach="A small number of low, long pieces.",
        functional_rationale="Seats four and keeps the window band open.",
        budget_suitability="Workable with a low piece count.",
    )


def build_complete_input(at: AppTest) -> AppTest:
    """Room and preferences through the real forms, then everything after them.

    The later results are recorded directly rather than produced by a model:
    this module is about the markup of each screen, so it needs the screens to
    open, not an AI call.
    """

    at = click(at, "Start Room Setup")
    at.text_input(key="hmw_room_name").set_value("Living Room")
    at.number_input(key="hmw_width_cm").set_value(400.0)
    at.number_input(key="hmw_length_cm").set_value(520.0)
    at.number_input(key="hmw_door_offset").set_value(20.0)
    at.number_input(key="hmw_door_width").set_value(80.0)
    at.number_input(key="hmw_window_offset").set_value(20.0)
    at.number_input(key="hmw_window_width").set_value(80.0)
    at.button(key=ROOM_FORM_SUBMIT).click().run()
    assert_no_exceptions(at)

    at.multiselect(key="hmw_materials").set_value(["pale oak"])
    at.multiselect(key="hmw_requirements").set_value(["Seating for four"])
    at.text_area(key="hmw_notes").set_value("Keep the window side open.")
    at.number_input(key="hmw_budget").set_value(85000.0)
    at.button(key=PREFERENCES_FORM_SUBMIT).click().run()
    assert_no_exceptions(at)

    state = at.session_state["hm_workflow_state"]
    assert isinstance(state, WorkflowState)
    state.record_brief(
        DesignBrief(
            summary="A calm living room for four people.",
            functional_priorities=["Seating for four", "Reading corner"],
            constraints=["One door and one window"],
            ambiguities=[],
            warnings=[],
        )
    )
    state.record_concepts(
        ConceptCollection(
            concepts=[
                make_concept("Low Horizon"),
                make_concept("Window Bench"),
                make_concept("Shelf Spine"),
            ]
        )
    )
    state.select_concept_by_name("Low Horizon")
    state.record_recommendation(
        DesignRecommendation(
            furniture=[
                FurnitureRecommendation(item_id="sofa_three_seat", quantity=1),
                FurnitureRecommendation(item_id="coffee_table", quantity=1),
            ],
            materials=[],
            color_direction="Warm neutrals.",
            design_rationale="Low pieces keep the window band open.",
        )
    )
    analysis = layout.analyse_layout(
        state.room, state.furniture, references.load_catalog()
    )
    state.record_spatial(analysis.validation, analysis.outcome, analysis.placements)
    state.record_budget_analysis(
        compute_budget(
            state.budget, state.furniture, references.load_catalog()
        ).analysis
    )
    state.record_evaluation(
        DesignEvaluation(
            requirement_compatibility="Seating for four is met.",
            style_consistency="Consistent with the chosen direction.",
            functional_suitability="The path from door to window stays clear.",
            budget_suitability="Within the stated budget.",
        )
    )
    at.run()
    assert_no_exceptions(at)
    return at


def open_screen(at: AppTest, screen: str) -> AppTest:
    at.session_state["hm_screen"] = screen
    at.run()
    assert_no_exceptions(at)
    assert at.session_state["hm_screen"] == screen, (
        f"the {screen} screen redirected: {at.session_state['hm_screen']!r}"
    )
    return at


# --------------------------------------------------------------------------- #
# The screens
# --------------------------------------------------------------------------- #

#: Every screen a reader can reach, with the title its ``h1`` must carry.
SCREEN_TITLES = (
    ("room", "Describe the room"),
    ("preferences", "Choose a direction"),
    ("review", "Your project input"),
    ("brief", "Analyse the design brief"),
    ("concepts", "Compare three directions"),
    ("plan", "Furniture, layout and validation"),
    ("evaluation", "Evaluate the design"),
    ("budget", "Indicative budget analysis"),
    ("report", "Download the project report"),
)


def test_the_landing_page_has_one_h1_and_a_sectioned_body() -> None:
    at = fresh_app()
    found = headings(at)

    level_ones = [text for level, text in found if level == 1]
    assert level_ones == ["HOMETSY — ROOM INTELLIGENCE STUDIO"], level_ones
    # Each landing section is a real h2, and each card inside it an h3.
    level_twos = [text for level, text in found if level == 2]
    assert level_twos == ["What it does", "Roadmap", "Start a project"], level_twos
    assert all(level == 3 for level, _ in found[1:] if level > 2)
    assert_no_skipped_levels(at)


def test_every_screen_has_exactly_one_h1() -> None:
    """The regression: no workflow screen used to have any h1 at all."""

    at = build_complete_input(fresh_app())
    for screen, title in SCREEN_TITLES:
        with_screen = open_screen(at, screen)
        assert_one_h1(with_screen, title)


def test_every_screen_descends_without_skipping_a_level() -> None:
    at = build_complete_input(fresh_app())
    for screen, _ in SCREEN_TITLES:
        with_screen = open_screen(at, screen)
        assert_no_skipped_levels(with_screen)


def test_the_room_form_sections_are_navigable_headings() -> None:
    """The exact case the manual inspection found: five paragraphs, not headings."""

    at = open_screen(build_complete_input(fresh_app()), "room")
    level_twos = [text for level, text in headings(at) if level == 2]
    for section in ("Room", "Door", "Window"):
        assert section in level_twos, (section, level_twos)


def test_the_plan_screen_sections_are_navigable_headings() -> None:
    at = open_screen(build_complete_input(fresh_app()), "plan")
    level_twos = [text for level, text in headings(at) if level == 2]
    for section in (
        "Furniture and materials",
        "Room plan",
        "Spatial validation",
    ):
        assert section in level_twos, (section, level_twos)


def test_the_brief_blocks_are_headings() -> None:
    """The four brief blocks are headings, one level under their section.

    They sit inside the "Brief summary" section rather than directly under the
    page title, so ``h3`` is the honest level.
    """

    at = open_screen(build_complete_input(fresh_app()), "brief")
    found = headings(at)
    assert found[0] == (1, "Analyse the design brief")
    level_twos = [text for level, text in found if level == 2]
    level_threes = [text for level, text in found if level == 3]
    assert "Brief summary" in level_twos, level_twos
    for block in ("Functional priorities", "Constraints", "Open questions"):
        assert block in level_threes, (block, level_twos, level_threes)


def test_the_concept_cards_are_headings_under_the_concepts_section() -> None:
    at = open_screen(build_complete_input(fresh_app()), "concepts")
    found = headings(at)
    level_threes = [text for level, text in found if level == 3]
    for concept in ("Low Horizon", "Window Bench", "Shelf Spine"):
        assert concept in level_threes, (concept, level_threes)


def test_no_screen_leaves_a_heading_empty() -> None:
    """An empty heading is announced as "heading, level 2" with no name."""

    at = build_complete_input(fresh_app())
    for screen, _ in SCREEN_TITLES:
        with_screen = open_screen(at, screen)
        empty = [level for level, text in headings(with_screen) if not text]
        assert empty == [], f"{screen} has empty headings: {empty}"


def rule_body(css: str, selector: str) -> str:
    """The declaration block of one CSS rule, or a readable failure."""

    marker = f"{selector} {{"
    assert marker in css, f"no rule for {selector}"
    return css.split(marker, 1)[1].split("}", 1)[0]


def test_the_reset_preserves_the_presentation_each_class_rendered_with() -> None:
    """A tag change must not restyle anything.

    Streamlit's markdown stylesheet gives every heading its own typeface,
    letter-spacing and padding. ``hm-page-title`` and ``hm-title`` were heading
    tags before, so they keep the heading presentation; the five label classes
    were paragraphs, so they must be pinned back to the inherited paragraph
    presentation. Getting this wrong silently restyles every label on every
    screen, which is why it is asserted rather than eyeballed.
    """

    css = theme.APP_CSS

    # One rule lists the five label classes, so each of them is pinned exactly
    # once by the same declaration block.
    assert ".hm-page .hm-section-label,\n  .hm-page .hm-group," in css
    for css_class in (
        "hm-section-label",
        "hm-group",
        "hm-card-title",
        "hm-card-name",
        "hm-block-title",
    ):
        assert f"  .hm-page .{css_class}," in css or f"  .hm-page .{css_class} {{" in css

    # The declarations that restore the paragraph look.
    labels_end = css.index("  /* The page title was an h2")
    labels_block = css[css.index("  .hm-page .hm-section-label,"):labels_end]
    assert "font-family: inherit" in labels_block
    assert "line-height: inherit" in labels_block
    assert "padding: 0" in labels_block

    # The page title was an h2 and is now an h1; it keeps the h2 box.
    assert "padding: 15px 0" in rule_body(css, ".hm-page .hm-page-title")

    # The landing title was already an h1, so it needs no box correction: its
    # own rule sets size, weight and margin only, and Streamlit's h1 padding
    # stays exactly as it rendered before.
    assert "padding" not in rule_body(css, ".hm-page .hm-title")


def test_the_stylesheet_does_not_reset_every_heading_globally() -> None:
    """A blanket ``.hm-page h1`` reset would restyle the titles too.

    That is exactly the mistake this guards: the titles are supposed to keep
    Streamlit's heading presentation, so a global reset of font-family or
    padding is wrong even though it looks like the tidy thing to write.
    """

    css = theme.APP_CSS
    assert ".hm-page h1," not in css
    assert "  .hm-page h2," not in css


def test_the_heading_helpers_are_used_by_the_pages_not_hand_written() -> None:
    """Every heading tag in the UI comes from ``ui.theme``.

    This keeps one definition of each level. A page that writes its own ``<h2>``
    would be free to pick a level that fights the page's own outline.
    """

    offenders = []
    for path in sorted((PROJECT_ROOT / "ui").glob("pages_*.py")):
        source = path.read_text(encoding="utf-8")
        for tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            for pattern in (f"<{tag}>", f"<{tag} "):
                if pattern in source:
                    offenders.append(f"{path.name}: {pattern}")
    assert offenders == [], offenders
