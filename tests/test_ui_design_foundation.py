"""The UI V2 design foundation: tokens, type, brand assets and icon wiring.

``DESIGN_SYSTEM.md`` fixes a palette and a type hierarchy; ``AGENTS.md`` §11
requires every runtime asset to be local and every licence to be recorded. These
tests hold the two together, and they exist because the failures they describe
are invisible: a hardcoded pixel size looks identical to a token once the
f-string has been evaluated, and a remote font looks identical to a local one
until the machine is offline.

Nothing here asserts an opinion about layout. The browser-verified behaviour of
the centred column is documented in ``app.py``; a CSS string cannot prove a
viewport width, so this file does not pretend to.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from ui import theme

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "app.py"
CONFIG_PATH = PROJECT_ROOT / ".streamlit" / "config.toml"

#: Every asset the application reads at runtime, and the file it must find.
RUNTIME_ASSETS = {
    "logo": "assets/brand/hometsy-logo.svg",
    "logo_light": "assets/brand/hometsy-logo-light.svg",
    "symbol": "assets/brand/hometsy-symbol.svg",
    "favicon": "assets/brand/favicon-64.png",
}


# --------------------------------------------------------------------------- #
# Design tokens
# --------------------------------------------------------------------------- #


def test_the_approved_palette_values_are_unchanged() -> None:
    """UI V2 must not move a single product colour.

    ``DESIGN_SYSTEM.md`` §3 is the approved palette and the brief for this phase
    says the existing values stay. The duplicated assertion against the PDF
    palette is in ``test_ui_presentation``; this one pins the literal values, so
    a well-meaning "warm it up slightly" edit fails here first.
    """

    assert theme.COLORS == {
        "primary": "#4B5147",
        "primary_dark": "#343A32",
        "background": "#F6F4EF",
        "surface": "#FFFFFF",
        "surface_muted": "#EEECE5",
        "text_primary": "#292B27",
        "text_secondary": "#5A5C56",
        "border": "#E4E1D9",
        "success": "#4F6A53",
        "warning": "#8A602C",
        "error": "#A44A40",
    }


def test_the_spacing_scale_is_strictly_increasing() -> None:
    steps = ("xs", "sm", "md", "lg", "xl", "2xl", "3xl")
    values = [int(theme.SPACE[name].removesuffix("px")) for name in steps]
    assert values == sorted(values)
    assert len(set(values)) == len(values)


def test_every_measure_is_a_character_cap() -> None:
    """Reading measures are in ``ch``, not pixels.

    A pixel cap stops being a measure the moment the type size changes, and the
    landing intro and the page intros deliberately do not share a size.
    """

    assert theme.MEASURE
    for value in theme.MEASURE.values():
        assert re.fullmatch(r"\d+ch", value), value


def test_the_content_width_fits_the_plan_frame() -> None:
    """The centred column must be wider than the drawing it has to hold.

    The plan is a 640-unit viewBox and the frame never renders below 1:1, so a
    content column narrower than that would make the plan scroll on a desktop
    as well as a phone — turning a phone-only accommodation into the default
    experience.
    """

    assert theme.CONTENT_WIDTH > 640
    # And wide enough for a readable line without being a full-bleed page.
    assert 960 <= theme.CONTENT_WIDTH <= 1280


# --------------------------------------------------------------------------- #
# Type
# --------------------------------------------------------------------------- #


def test_the_font_stack_declares_a_local_fallback() -> None:
    """No remote font, and a face the machine already has.

    Inter is not bundled (see the phase report), so the stack has to end in a
    generic family. If ``sans-serif`` were dropped and Inter were the only
    entry, an offline machine with no Inter would fall back to the user agent's
    serif default.
    """

    stack = [part.strip() for part in theme.FONT_FAMILY.split(",")]
    assert stack[-1] == "sans-serif"
    assert "Arial" in stack
    assert "http" not in theme.FONT_FAMILY
    assert "url(" not in theme.FONT_FAMILY


def test_the_same_font_stack_reaches_widgets_and_html() -> None:
    """One typeface for the whole screen.

    Before UI V2, ``.streamlit/config.toml`` asked for ``"sans serif"`` and the
    stylesheet asked for Inter/Arial, so a widget label and the HTML beside it
    were set in different faces. Both now name the same string.
    """

    assert "font-family: " + theme.FONT_FAMILY in theme.APP_CSS

    import tomllib

    config = tomllib.loads(CONFIG_PATH.read_text(encoding="utf-8"))["theme"]
    assert config["font"] == theme.FONT_FAMILY
    assert config["headingFont"] == theme.FONT_FAMILY


def test_every_icon_name_maps_to_a_local_file() -> None:
    """The icon set is closed and every member exists on disk.

    A missing file would raise inside ``icon()`` at render time — a crash on a
    page, caused by an asset that was never copied. Checking the directory here
    turns that into a test failure.
    """

    assert theme.ICON_NAMES
    assert len(set(theme.ICON_NAMES)) == len(theme.ICON_NAMES)
    for name in theme.ICON_NAMES:
        assert (theme.ICONS_DIR / f"{name}.svg").is_file(), name


def test_the_icon_helper_emits_current_colour_and_hides_itself() -> None:
    """An icon inherits its colour and is never announced.

    Both properties are functional, not cosmetic: ``currentColor`` is what lets
    one rule colour every icon, and ``aria-hidden`` is what keeps a decorative
    glyph from being read out beside the label that already says the same thing.
    """

    markup = theme.icon("home")
    assert 'aria-hidden="true"' in markup
    assert "currentColor" in markup
    # The hardcoded ink from the asset pack must have been rewritten.
    assert "#252A28" not in markup
    # And the outer wrapper is the helper's, not the file's.
    assert markup.count("<svg") == 1
    assert markup.startswith('<span class="hm-icon"')


def test_an_unknown_icon_name_fails_loudly() -> None:
    """A typo raises rather than rendering an empty box."""

    with pytest.raises(ValueError, match="Unknown icon"):
        theme.icon("no-such-icon")
    with pytest.raises(ValueError, match="Unknown icon"):
        theme._icon_source("no-such-icon")


# --------------------------------------------------------------------------- #
# Brand assets
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(("name", "relative"), sorted(RUNTIME_ASSETS.items()))
def test_every_runtime_brand_asset_exists(name: str, relative: str) -> None:
    """The application reads these from disk on every render."""

    declared = {
        "logo": theme.LOGO_PATH,
        "logo_light": theme.LOGO_LIGHT_PATH,
        "symbol": theme.SYMBOL_PATH,
        "favicon": theme.FAVICON_PATH,
    }[name]
    assert declared == PROJECT_ROOT / relative
    assert declared.is_file(), relative
    assert declared.stat().st_size > 0


def test_the_runtime_brand_assets_are_local_and_self_contained() -> None:
    """No SVG may reference a font, an image or a stylesheet over the network.

    The pack's logo files specify a ``font-family`` for their text; that is a
    local family name and resolves to whatever the system has. What is refused
    here is an ``href``/``src`` that would make a request.
    """

    for path in (
        theme.LOGO_PATH,
        theme.LOGO_LIGHT_PATH,
        theme.SYMBOL_PATH,
        *sorted(theme.ICONS_DIR.glob("*.svg")),
    ):
        source = path.read_text(encoding="utf-8")
        assert "http://" not in source.replace("http://www.w3.org", ""), path.name
        assert "https://" not in source, path.name
        assert "@import" not in source, path.name
        assert "xlink:href" not in source, path.name


def test_the_favicon_is_a_png_of_the_declared_size() -> None:
    """``page_icon`` accepts a path; a truncated or mislabelled file would not.

    Checking the PNG signature and the IHDR width/height keeps the tab icon from
    silently disappearing if the file is ever replaced.
    """

    data = theme.FAVICON_PATH.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    assert width == height == 64


def test_the_brand_mark_draws_the_symbol_not_a_second_copy_of_it() -> None:
    """The mark is the same path as ``hometsy-symbol.svg``.

    Two copies of a path would drift the moment one was "tidied". The helper
    inlines the geometry because SVG cannot be ``<img>``-ed and inherit colour,
    so the path is duplicated by design — and pinned to the file it came from.
    """

    source = theme.SYMBOL_PATH.read_text(encoding="utf-8")
    path = re.search(r'<path d="([^"]+)"', source)
    assert path is not None
    assert path.group(1) in theme.brand_mark()
    assert 'aria-hidden="true"' in theme.brand_mark()


def test_the_landing_page_renders_the_brand_mark_and_its_icons() -> None:
    """The brand assets are actually used, not merely present in ``assets/``.

    An asset nobody renders is dead weight; the phase that adds it should be the
    phase that proves it reaches a screen.
    """

    from ui import pages_landing

    landing = (PROJECT_ROOT / "ui" / "pages_landing.py").read_text(encoding="utf-8")
    assert "theme.brand_mark()" in landing
    assert "theme.capability(" in landing
    for _, _, icon_name in pages_landing.CAPABILITIES:
        assert icon_name in theme.ICON_NAMES, icon_name


def test_the_entry_point_declares_the_favicon_and_the_logo() -> None:
    """``app.py`` owns the two calls that put the brand in the browser chrome."""

    source = APP_PATH.read_text(encoding="utf-8")
    assert "page_icon=str(theme.FAVICON_PATH)" in source
    assert "st.logo(" in source
    assert "icon_image=str(theme.SYMBOL_PATH)" in source
    # The emoji that used to be the favicon is gone.
    assert "🏠" not in source


def test_the_application_keeps_one_centred_content_column() -> None:
    """The centred width comes from the token and from documented parameters.

    ``horizontal_alignment`` and ``width`` are ``st.container`` arguments, so no
    generated class name appears on either side of the nesting. Asserting the
    pair keeps someone from replacing it with a ``max-width`` on an internal
    element that would break on the next Streamlit release.
    """

    source = APP_PATH.read_text(encoding="utf-8")
    assert 'st.container(horizontal=True, horizontal_alignment="center")' in source
    assert "st.container(width=theme.CONTENT_WIDTH)" in source
    for forbidden in ("st-emotion-cache", "data-testid", "stMainBlockContainer"):
        assert forbidden not in source, forbidden


# --------------------------------------------------------------------------- #
# Nothing remote, nothing invented
# --------------------------------------------------------------------------- #


def test_no_stylesheet_anywhere_loads_a_remote_resource() -> None:
    """Fonts and images are local or they are absent (AGENTS.md §11)."""

    assert "@import" not in theme.APP_CSS
    assert "url(http" not in theme.APP_CSS
    assert "url(//" not in theme.APP_CSS
    assert "fonts.googleapis" not in theme.APP_CSS
    assert "fontFaces" not in CONFIG_PATH.read_text(encoding="utf-8")


def test_the_source_admits_that_inter_is_not_bundled() -> None:
    """The one place the limitation is written down for the next reader.

    Reporting a font as "integrated" when only its name is in a CSS stack would
    be the kind of quiet overclaim this project forbids. The comment states it,
    and this test keeps the statement from being deleted while the font is still
    absent — if Inter is ever added, this test should fail and be replaced with
    a ``@font-face`` assertion.
    """

    source = Path(theme.__file__).read_text(encoding="utf-8")
    assert "not bundled" in source
    assert not (PROJECT_ROOT / "assets" / "fonts" / "Inter-Regular.woff2").exists()
