"""Professional PDF project report.

The reporting layer described in ``TECHNICAL_ARCHITECTURE.md`` §9. It receives
the consolidated :class:`models.schemas.ProjectResult` plus the already-computed
budget result, and lays them out as an A4 document.

Why it calculates nothing
-------------------------
``AGENTS.md`` §8 puts geometry and money on Python's side, and both already have
an owner: ``core.placement_engine`` produced the footprints, ``core.budget_engine``
produced the totals and the per-item lines. This module divides by the drawing
box to scale the plan and adds nothing else. It never prices an item, never
re-measures a room, never re-scores a layout and never re-derives a total; if a
figure is not in the data it is described as missing rather than estimated.

Honesty rules the layout enforces
---------------------------------
* A ``FAILED`` placement has no validated layout, so no plan is drawn — only an
  explanation. A ``PARTIAL`` one draws the copies that were placed and states
  how many are missing.
* Materials carry no price in V1, so they are shown as "not priced" and are
  explicitly outside the furniture total.
* The design evaluation is presented as a written opinion with no score and no
  verdict, because the schema has neither.
* A catalog cost is labelled indicative everywhere it appears.

Typography
----------
DejaVu Sans is bundled under ``assets/fonts`` (Bitstream Vera / public-domain
DejaVu licence, copied alongside the files). It is used instead of a built-in
PDF font because the base-14 fonts cannot represent ğ Ğ ş Ş ı İ ö Ö ü Ü ç Ç,
and a report that mangles a Turkish room name is not acceptable.
"""

from __future__ import annotations

import math
import re
import unicodedata
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Sequence
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    KeepTogether,
    LongTable,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.flowables import HRFlowable

from core.budget_engine import BudgetResult, LineItem
from core.spatial_engine import (
    DEFAULT_DOOR_CLEARANCE_CM,
    DEFAULT_WINDOW_CLEARANCE_CM,
)
from models.schemas import (
    FurnitureItem,
    FurnitureRecommendation,
    PlacementOutcome,
    PlacedFootprint,
    ProjectResult,
    RoomInput,
    Wall,
)

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

PROJECT_ROOT = Path(__file__).resolve().parents[1]

#: Where generated reports are written. Inside the project, never a temp folder
#: the user cannot find, and excluded from version control.
OUTPUT_DIR = PROJECT_ROOT / "output" / "reports"

#: The bundled, Turkish-capable faces. Checked at first use, not at import, so a
#: missing asset file breaks report generation rather than the whole application.
FONT_REGULAR = PROJECT_ROOT / "assets" / "fonts" / "DejaVuSans.ttf"
FONT_BOLD = PROJECT_ROOT / "assets" / "fonts" / "DejaVuSans-Bold.ttf"
FONT_FAMILY = "HometsySans"

#: Page geometry.
PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN_SIDE = 18 * mm
MARGIN_TOP = 24 * mm
MARGIN_BOTTOM = 18 * mm

REPORT_TITLE = "Room design report"
BRAND_NAME = "HOMETSY"
BRAND_SUBTITLE = "Room Intelligence Studio"

#: Mirrors ``ui.theme.COLORS``. Duplicated rather than imported so this module
#: stays free of the presentation layer; ``tests/test_report_generator.py``
#: asserts the two tables agree.
PALETTE: dict[str, str] = {
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

_INK = colors.HexColor(PALETTE["text_primary"])
_MUTED = colors.HexColor(PALETTE["text_secondary"])
_HEADING = colors.HexColor(PALETTE["primary_dark"])
_ACCENT = colors.HexColor(PALETTE["primary"])
_RULE = colors.HexColor(PALETTE["border"])
_BAND = colors.HexColor(PALETTE["surface_muted"])
_WARNING = colors.HexColor(PALETTE["warning"])
_ERROR = colors.HexColor(PALETTE["error"])
_SUCCESS = colors.HexColor(PALETTE["success"])
_FURNITURE_FILL = colors.HexColor("#DDD8CB")
_FURNITURE_STROKE = colors.HexColor("#7A7568")

_MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)

#: Vertical reference is the room's south-west corner, as everywhere else.
_HORIZONTAL_WALLS = (Wall.NORTH, Wall.SOUTH)


class ReportGenerationError(Exception):
    """The report could not be produced. Carries a message a user may read."""


# --------------------------------------------------------------------------- #
# Fonts
# --------------------------------------------------------------------------- #

_registered = False


def register_fonts() -> None:
    """Register the bundled faces once. Raises if an asset is missing."""

    global _registered
    if _registered:
        return
    for name, path in (
        (FONT_FAMILY, FONT_REGULAR),
        (f"{FONT_FAMILY}-Bold", FONT_BOLD),
    ):
        if not path.exists():
            raise ReportGenerationError(
                "The report font is missing from assets/fonts, so the PDF cannot "
                "be produced with correct Turkish characters."
            )
        pdfmetrics.registerFont(TTFont(name, str(path)))
    pdfmetrics.registerFontFamily(
        FONT_FAMILY,
        normal=FONT_FAMILY,
        bold=f"{FONT_FAMILY}-Bold",
        italic=FONT_FAMILY,
        boldItalic=f"{FONT_FAMILY}-Bold",
    )
    _registered = True


# --------------------------------------------------------------------------- #
# Filename
# --------------------------------------------------------------------------- #

#: Turkish letters that ASCII folding alone would lose. ``ı`` and ``İ`` do not
#: decompose to ``i`` under NFKD, so they are mapped explicitly.
_TURKISH_FOLD = str.maketrans(
    {
        "ı": "i",
        "İ": "i",
        "ş": "s",
        "Ş": "s",
        "ğ": "g",
        "Ğ": "g",
        "ç": "c",
        "Ç": "c",
        "ö": "o",
        "Ö": "o",
        "ü": "u",
        "Ü": "u",
    }
)

_MAX_NAME_CHARS = 60


def report_filename(project_name: str) -> str:
    """A safe download name derived from the project name.

    The name reaches a filesystem path, so everything outside ``[a-z0-9-]`` is
    removed: Turkish letters are folded to their ASCII equivalents, spaces and
    punctuation become single dashes, and the result is length-limited. A name
    that survives as nothing usable falls back to ``project``, which means the
    user's text can never select a directory or overwrite another file.
    """

    folded = (project_name or "").translate(_TURKISH_FOLD)
    ascii_only = (
        unicodedata.normalize("NFKD", folded).encode("ascii", "ignore").decode()
    )
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_only.lower()).strip("-")
    slug = slug[:_MAX_NAME_CHARS].strip("-")
    if not slug:
        slug = "project"
    return f"hometsy-{slug}-report.pdf"


# --------------------------------------------------------------------------- #
# Formatting helpers
# --------------------------------------------------------------------------- #

_TWO_PLACES = Decimal("0.01")


def format_money(amount: Decimal, currency: str = "TRY") -> str:
    """Group thousands the way the interface does, with an explicit currency.

    Delegates to :func:`core.budget_engine.format_money`; the parity with
    ``ui.commits.format_money`` is asserted in the tests so the report, the
    screen and the engine's own sentences can never drift apart.
    """

    from core.budget_engine import format_money as _format_money

    return _format_money(amount, currency)


def format_length(value: float) -> str:
    """Centimeters without a trailing ``.0``."""

    return f"{value:g} cm"


def format_date(moment: datetime) -> str:
    """``15 November 2026``, independent of the machine's locale."""

    return f"{moment.day} {_MONTHS[moment.month - 1]} {moment.year}"


def title_of(value: object) -> str:
    """An enum member's own label, so no vocabulary is invented here."""

    return str(getattr(value, "value", value))


# --------------------------------------------------------------------------- #
# Styles
# --------------------------------------------------------------------------- #


def _styles() -> dict[str, ParagraphStyle]:
    # Imported late: register_fonts() must run first, and ParagraphStyle does not
    # care, but keeping the two together makes the substitution obvious.
    base = ParagraphStyle(
        "body",
        fontName=FONT_FAMILY,
        fontSize=9.2,
        leading=13.4,
        textColor=_INK,
        spaceAfter=2.4 * mm,
        alignment=0,
    )
    return {
        "body": base,
        "lead": ParagraphStyle(
            "lead",
            parent=base,
            fontSize=10,
            leading=15,
            textColor=_INK,
            spaceAfter=4 * mm,
        ),
        "h1": ParagraphStyle(
            "h1",
            parent=base,
            fontName=f"{FONT_FAMILY}-Bold",
            fontSize=15,
            leading=18,
            textColor=_HEADING,
            spaceBefore=2 * mm,
            spaceAfter=1.2 * mm,
            keepWithNext=1,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base,
            fontName=f"{FONT_FAMILY}-Bold",
            fontSize=10.2,
            leading=13,
            textColor=_HEADING,
            spaceBefore=3.4 * mm,
            spaceAfter=1.4 * mm,
            keepWithNext=1,
        ),
        "label": ParagraphStyle(
            "label",
            parent=base,
            fontSize=7.4,
            leading=9.6,
            textColor=_MUTED,
            spaceAfter=0.6 * mm,
        ),
        "muted": ParagraphStyle(
            "muted",
            parent=base,
            fontSize=8,
            leading=11.4,
            textColor=_MUTED,
        ),
        "note": ParagraphStyle(
            "note",
            parent=base,
            fontSize=7.6,
            leading=10.6,
            textColor=_MUTED,
            spaceBefore=1.2 * mm,
        ),
        "bullet": ParagraphStyle(
            "bullet",
            parent=base,
            fontSize=9,
            leading=12.8,
            leftIndent=4.6 * mm,
            bulletIndent=0.6 * mm,
            spaceAfter=1.2 * mm,
        ),
        "cell": ParagraphStyle(
            "cell",
            parent=base,
            fontSize=8,
            leading=10.6,
            spaceAfter=0,
        ),
        "cell_head": ParagraphStyle(
            "cell_head",
            parent=base,
            fontName=f"{FONT_FAMILY}-Bold",
            fontSize=7.8,
            leading=10.2,
            textColor=_HEADING,
            spaceAfter=0,
        ),
        "cell_num_head": ParagraphStyle(
            "cell_num_head",
            parent=base,
            fontName=f"{FONT_FAMILY}-Bold",
            fontSize=7.8,
            leading=10.2,
            textColor=_HEADING,
            alignment=2,
            spaceAfter=0,
        ),
        "cell_muted": ParagraphStyle(
            "cell_muted",
            parent=base,
            fontSize=7.2,
            leading=9.4,
            textColor=_MUTED,
            spaceAfter=0,
        ),
        "cell_num": ParagraphStyle(
            "cell_num",
            parent=base,
            fontSize=8,
            leading=10.6,
            alignment=2,
            spaceAfter=0,
        ),
        "cover_brand": ParagraphStyle(
            "cover_brand",
            parent=base,
            fontName=f"{FONT_FAMILY}-Bold",
            fontSize=26,
            leading=30,
            textColor=_HEADING,
            spaceAfter=0,
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub",
            parent=base,
            fontSize=11.6,
            leading=16,
            textColor=_MUTED,
            spaceAfter=0,
        ),
        "cover_title": ParagraphStyle(
            "cover_title",
            parent=base,
            fontName=f"{FONT_FAMILY}-Bold",
            fontSize=20,
            leading=25,
            textColor=_INK,
            spaceAfter=0,
        ),
        "two_column_label": ParagraphStyle(
            "two_column_label",
            parent=base,
            fontSize=8.2,
            leading=11.6,
            textColor=_MUTED,
            spaceAfter=0,
        ),
        "two_column_value": ParagraphStyle(
            "two_column_value",
            parent=base,
            fontSize=8.6,
            leading=11.8,
            textColor=_INK,
            spaceAfter=0,
        ),
    }


def _p(text: object, style: ParagraphStyle) -> Paragraph:
    """A paragraph with the text escaped, so data can never become markup."""

    return Paragraph(escape(str(text)), style)


def _bullets(items: Sequence[str], style: ParagraphStyle) -> list[Paragraph]:
    return [
        Paragraph(escape(str(item)), style, bulletText="\u2022") for item in items
    ]


def _or_none(items: Sequence[str], empty: str = "None recorded.") -> list[str]:
    """The list, or one honest sentence instead of an invented entry."""

    return list(items) if items else [empty]


# --------------------------------------------------------------------------- #
# Plan drawing
# --------------------------------------------------------------------------- #


class _RoomPlan(Flowable):
    """The validated layout, drawn from the engine's own footprints.

    Every rectangle comes from a :class:`models.schemas.PlacedFootprint`, whose
    extents the spatial engine already rotated. The only arithmetic here fits
    the room into the available box; no coordinate is derived, corrected or
    re-measured.
    """

    def __init__(
        self,
        room: RoomInput,
        footprints: Sequence[PlacedFootprint],
        *,
        max_height: float = 150 * mm,
    ) -> None:
        super().__init__()
        self.room = room
        self.footprints = list(footprints)
        self.max_height = max_height

    def wrap(self, avail_width: float, avail_height: float) -> tuple[float, float]:
        """Use the full width, and as much height as the room's aspect needs.

        The plan is the report's visual centrepiece, so it is given the whole
        frame width and up to ``max_height``. The room keeps its proportions
        because ``_box`` takes the smaller of the two scales.
        """

        self.width = avail_width
        aspect = self.room.length_cm / max(self.room.width_cm, 1.0)
        # The frame inside the flowable is inset horizontally by 24 mm; solve for
        # the height that lets that inner width set the scale.
        inner_width = max(avail_width - 24 * mm, 40 * mm)
        wanted = inner_width * aspect + 20 * mm
        self.height = max(70 * mm, min(self.max_height, wanted))
        return self.width, self.height

    # -- geometry ------------------------------------------------------ #

    def _box(self) -> tuple[float, float, float]:
        pad_left, pad_right = 6 * mm, 18 * mm
        pad_top, pad_bottom = 10 * mm, 10 * mm
        usable_w = self.width - pad_left - pad_right
        usable_h = self.height - pad_top - pad_bottom
        scale = min(usable_w / self.room.width_cm, usable_h / self.room.length_cm)
        room_w = self.room.width_cm * scale
        room_h = self.room.length_cm * scale
        origin_x = pad_left + (usable_w - room_w) / 2
        origin_y = pad_bottom + (usable_h - room_h) / 2
        return origin_x, origin_y, scale

    def _opening_segment(
        self,
        wall: Wall,
        offset: float,
        width: float,
        origin_x: float,
        origin_y: float,
        scale: float,
    ) -> tuple[float, float, float, float]:
        """Both endpoints of an opening, clipped to its wall."""

        span = (
            self.room.width_cm if wall in _HORIZONTAL_WALLS
            else self.room.length_cm
        )
        start = max(0.0, min(offset, span)) * scale
        end = max(0.0, min(offset + width, span)) * scale
        room_w = self.room.width_cm * scale
        room_h = self.room.length_cm * scale

        if wall is Wall.SOUTH:
            return origin_x + start, origin_y, origin_x + end, origin_y
        if wall is Wall.NORTH:
            return (
                origin_x + start,
                origin_y + room_h,
                origin_x + end,
                origin_y + room_h,
            )
        if wall is Wall.WEST:
            return origin_x, origin_y + start, origin_x, origin_y + end
        return (
            origin_x + room_w,
            origin_y + start,
            origin_x + room_w,
            origin_y + end,
        )

    # -- painting ------------------------------------------------------ #

    def draw(self) -> None:
        canvas = self.canv
        origin_x, origin_y, scale = self._box()
        room_w = self.room.width_cm * scale
        room_h = self.room.length_cm * scale

        canvas.saveState()
        canvas.setLineJoin(1)

        # Floor.
        canvas.setFillColor(colors.HexColor(PALETTE["surface"]))
        canvas.setStrokeColor(_HEADING)
        canvas.setLineWidth(1.2)
        canvas.rect(origin_x, origin_y, room_w, room_h, stroke=1, fill=1)

        # Furniture.
        for footprint in self.footprints:
            self._draw_footprint(canvas, footprint, origin_x, origin_y, scale)

        # Openings on top, so an edge is never hidden behind a block.
        door = self._opening_segment(
            self.room.door.wall,
            self.room.door.offset_cm,
            self.room.door.width_cm,
            origin_x,
            origin_y,
            scale,
        )
        window = self._opening_segment(
            self.room.window.wall,
            self.room.window.offset_cm,
            self.room.window.width_cm,
            origin_x,
            origin_y,
            scale,
        )
        canvas.setStrokeColor(_ACCENT)
        canvas.setLineWidth(2.6)
        canvas.line(*door)
        canvas.setStrokeColor(_WARNING)
        canvas.setLineWidth(1.8)
        canvas.line(*window)

        # Dimensions: width above, floor area to the right.
        canvas.setStrokeColor(_MUTED)
        canvas.setLineWidth(0.4)
        tick = 1.6 * mm
        top = origin_y + room_h + 4 * mm
        canvas.line(origin_x, top, origin_x + room_w, top)
        canvas.line(origin_x, top - tick / 2, origin_x, top + tick / 2)
        canvas.line(
            origin_x + room_w, top - tick / 2, origin_x + room_w, top + tick / 2
        )
        canvas.setFillColor(_MUTED)
        canvas.setFont(FONT_FAMILY, 7)
        canvas.drawCentredString(
            origin_x + room_w / 2, top + 1.2 * mm, format_length(self.room.width_cm)
        )

        right = origin_x + room_w + 3 * mm
        canvas.line(right, origin_y, right, origin_y + room_h)
        canvas.line(right - tick / 2, origin_y, right + tick / 2, origin_y)
        canvas.line(
            right - tick / 2, origin_y + room_h, right + tick / 2, origin_y + room_h
        )
        canvas.saveState()
        canvas.translate(right + 3.4 * mm, origin_y + room_h / 2)
        canvas.rotate(90)
        canvas.drawCentredString(
            0, 0, f"{format_length(self.room.length_cm)} \u00b7 "
            f"{self.room.area_sqm:.2f} m\u00b2"
        )
        canvas.restoreState()

        # Origin marker, so the coordinate convention is visible in the picture.
        canvas.setFillColor(_MUTED)
        canvas.setFont(FONT_FAMILY, 6.4)
        canvas.drawString(
            origin_x,
            origin_y - 5 * mm,
            "Origin (0, 0) \u00b7 south-west corner, centimetres",
        )
        canvas.restoreState()

    def _draw_footprint(
        self,
        canvas: pdf_canvas.Canvas,
        footprint: PlacedFootprint,
        origin_x: float,
        origin_y: float,
        scale: float,
    ) -> None:
        left = origin_x + footprint.left_cm * scale
        bottom = origin_y + footprint.bottom_cm * scale
        width = footprint.width_cm * scale
        height = footprint.depth_cm * scale

        canvas.setFillColor(_FURNITURE_FILL)
        canvas.setStrokeColor(_FURNITURE_STROKE)
        canvas.setLineWidth(0.5)
        canvas.setDash()
        canvas.rect(left, bottom, width, height, stroke=1, fill=1)

        # A block too small for a readable label keeps its rectangle and is
        # named in the placement table instead; nothing is dropped.
        if width < 13 * mm or height < 5.5 * mm:
            return

        label = footprint.label.strip() or footprint.item_id
        if width < 24 * mm:
            label = label.split()[0]

        canvas.setFillColor(_INK)
        canvas.setFont(FONT_FAMILY, 6.2)
        text_y = bottom + height / 2 if height < 10 * mm else bottom + height / 2 + 1.6 * mm
        canvas.drawCentredString(left + width / 2, text_y, _clip(canvas, label, width))
        if height >= 10 * mm:
            canvas.setFillColor(_MUTED)
            canvas.setFont(FONT_FAMILY, 5.6)
            canvas.drawCentredString(
                left + width / 2,
                bottom + height / 2 - 2.2 * mm,
                f"{footprint.width_cm:g} \u00d7 {footprint.depth_cm:g}",
            )


def _clip(canvas: pdf_canvas.Canvas, text: str, max_width: float) -> str:
    """Shorten a label until it fits its block. The full name is in the table."""

    if pdfmetrics.stringWidth(text, FONT_FAMILY, 6.2) <= max_width - 1.6 * mm:
        return text
    trimmed = text
    while trimmed and (
        pdfmetrics.stringWidth(trimmed + "\u2026", FONT_FAMILY, 6.2)
        > max_width - 1.6 * mm
    ):
        trimmed = trimmed[:-1]
    return (trimmed.rstrip() + "\u2026") if trimmed else ""


class _CostBars(Flowable):
    """Horizontal bars, one per priced line, using the engine's own totals."""

    _ROW = 5.4 * mm
    _LABEL_WIDTH = 52 * mm

    def __init__(self, lines: Sequence[LineItem], currency: str) -> None:
        super().__init__()
        self.lines = list(lines)
        self.currency = currency

    def wrap(self, avail_width: float, avail_height: float) -> tuple[float, float]:
        self.width = avail_width
        self.height = self._ROW * len(self.lines) + 3 * mm
        return self.width, self.height

    def draw(self) -> None:
        canvas = self.canv
        largest = max((float(line.line_total) for line in self.lines), default=0.0)
        if largest <= 0:
            return
        bar_area = self.width - self._LABEL_WIDTH - 26 * mm
        canvas.saveState()
        for index, line in enumerate(self.lines):
            baseline = self.height - 3 * mm - index * self._ROW - self._ROW / 2
            share = float(line.line_total) / largest
            canvas.setFillColor(_INK)
            canvas.setFont(FONT_FAMILY, 6.8)
            canvas.drawString(0, baseline - 2, _short(line.name, self._LABEL_WIDTH))
            canvas.setFillColor(_ACCENT)
            canvas.rect(
                self._LABEL_WIDTH,
                baseline - 2.4 * mm,
                max(bar_area * share, 0.6),
                3.2 * mm,
                stroke=0,
                fill=1,
            )
            canvas.setFillColor(_MUTED)
            canvas.setFont(FONT_FAMILY, 6.4)
            canvas.drawString(
                self._LABEL_WIDTH + bar_area + 2 * mm,
                baseline - 2,
                format_money(line.line_total, self.currency),
            )
        canvas.restoreState()


def _short(text: str, max_width: float) -> str:
    """Trim a bar label to the space beside it."""

    if pdfmetrics.stringWidth(text, FONT_FAMILY, 6.8) <= max_width - 2 * mm:
        return text
    trimmed = text
    while trimmed and (
        pdfmetrics.stringWidth(trimmed + "\u2026", FONT_FAMILY, 6.8)
        > max_width - 2 * mm
    ):
        trimmed = trimmed[:-1]
    return (trimmed.rstrip() + "\u2026") if trimmed else ""


# --------------------------------------------------------------------------- #
# Page furniture
# --------------------------------------------------------------------------- #


class _NumberedCanvas(pdf_canvas.Canvas):
    """A canvas that can print "Page n of N" without a second render pass."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._pages: list[dict] = []

    def showPage(self) -> None:  # noqa: N802 - ReportLab's spelling
        self._pages.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        total = len(self._pages)
        for state in self._pages:
            self.__dict__.update(state)
            if self._pageNumber > 1:
                self.setFont(FONT_FAMILY, 7.6)
                self.setFillColor(_MUTED)
                self.drawRightString(
                    PAGE_WIDTH - MARGIN_SIDE,
                    MARGIN_BOTTOM - 7 * mm,
                    f"Page {self._pageNumber} of {total}",
                )
            super().showPage()
        super().save()


def _draw_body_header(canvas: pdf_canvas.Canvas, doc) -> None:
    """Brand line, project title and the rule under them."""

    canvas.saveState()
    canvas.setFont(FONT_FAMILY, 8)
    canvas.setFillColor(_HEADING)
    canvas.drawString(MARGIN_SIDE, PAGE_HEIGHT - 14 * mm, BRAND_NAME)
    canvas.setFillColor(_MUTED)
    canvas.drawString(
        MARGIN_SIDE + pdfmetrics.stringWidth(BRAND_NAME, FONT_FAMILY, 8) + 2.2 * mm,
        PAGE_HEIGHT - 14 * mm,
        f"\u00b7 {BRAND_SUBTITLE}",
    )
    title = getattr(doc, "project_title", "")
    if title:
        canvas.setFont(FONT_FAMILY, 7.6)
        canvas.drawRightString(PAGE_WIDTH - MARGIN_SIDE, PAGE_HEIGHT - 14 * mm, title)
    canvas.setStrokeColor(_RULE)
    canvas.setLineWidth(0.6)
    canvas.line(
        MARGIN_SIDE,
        PAGE_HEIGHT - 17 * mm,
        PAGE_WIDTH - MARGIN_SIDE,
        PAGE_HEIGHT - 17 * mm,
    )
    canvas.setFont(FONT_FAMILY, 6.8)
    canvas.setFillColor(_MUTED)
    canvas.drawString(
        MARGIN_SIDE,
        MARGIN_BOTTOM - 7 * mm,
        "V1 AI-assisted design report \u00b7 illustrative, not a construction "
        "drawing or an engineering approval",
    )
    canvas.restoreState()


def _draw_cover_footer(canvas: pdf_canvas.Canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont(FONT_FAMILY, 6.8)
    canvas.setFillColor(_MUTED)
    canvas.drawString(
        MARGIN_SIDE,
        MARGIN_BOTTOM - 7 * mm,
        "V1 AI-assisted design report",
    )
    canvas.restoreState()


# --------------------------------------------------------------------------- #
# Section builders
# --------------------------------------------------------------------------- #


def _heading(section: str, title: str, styles: dict) -> list:
    """Section heading with a hairline rule, kept with the text that follows."""

    return [
        Paragraph(
            f'<font color="{PALETTE["text_secondary"]}" size="8">{escape(section)}'
            f"</font><br/>{escape(title)}",
            styles["h1"],
        ),
        HRFlowable(
            width="100%",
            thickness=0.8,
            color=_RULE,
            spaceBefore=1.2 * mm,
            spaceAfter=3.2 * mm,
        ),
    ]


def _two_column(rows: Sequence[tuple[str, str]], styles: dict) -> Table:
    """A label/value table that wraps instead of overflowing."""

    data = [
        [
            _p(label, styles["two_column_label"]),
            _p(value, styles["two_column_value"]),
        ]
        for label, value in rows
    ]
    table = Table(data, colWidths=[52 * mm, 122 * mm], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 1.1 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1.1 * mm),
                ("LINEBELOW", (0, 0), (-1, -2), 0.4, _RULE),
            ]
        )
    )
    return table


def _cell(value: object, style: ParagraphStyle) -> object:
    """A table cell, escaped if it is text and passed through if it is a flowable.

    ReportLab accepts a list of flowables in one cell, which is how an item name
    is paired with its rationale inside the first column. Escaping those would
    print their repr instead of their text.
    """

    if isinstance(value, Flowable):
        return value
    if isinstance(value, (list, tuple)):
        return [
            item if isinstance(item, Flowable) else _p(item, style) for item in value
        ]
    return _p(value, style)


def _data_table(
    header: Sequence[str],
    rows: Sequence[Sequence[object]],
    widths: Sequence[float],
    styles: dict,
    *,
    numeric: Sequence[int] = (),
) -> LongTable:
    """A table that repeats its header on every page it spans.

    ``numeric`` lists the column indexes whose content is right-aligned; their
    headers are right-aligned to match, so a column of figures lines up with its
    own label.
    """

    data = [
        [
            Paragraph(
                escape(str(cell)),
                styles["cell_num_head"] if index in numeric else styles["cell_head"],
            )
            for index, cell in enumerate(header)
        ]
    ]
    for row in rows:
        data.append(
            [
                _cell(cell, styles["cell_num"] if index in numeric else styles["cell"])
                for index, cell in enumerate(row)
            ]
        )
    table = LongTable(
        data, colWidths=list(widths), repeatRows=1, hAlign="LEFT"
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _BAND),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 2.4 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2.4 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 1.5 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5 * mm),
                ("LINEBELOW", (0, 0), (-1, -1), 0.4, _RULE),
                ("LINEBELOW", (0, 0), (-1, 0), 0.7, _RULE),
            ]
        )
    )
    return table


def _note(text: str, styles: dict) -> Paragraph:
    return _p(text, styles["note"])


def _bulleted_block(
    title: str, items: Sequence[str], styles: dict, *, empty: str = "None recorded."
) -> list:
    return [
        Paragraph(escape(title), styles["h2"]),
        *_bullets(_or_none(items, empty), styles["bullet"]),
    ]


# -- B: overview ------------------------------------------------------------ #


def _overview(result: ProjectResult, styles: dict) -> list:
    room = result.room
    prefs = result.preferences
    reqs = result.requirements

    overview = [
        ("Room type", title_of(room.room_type)),
        ("Room name", room.name),
        ("Width", format_length(room.width_cm)),
        ("Length", format_length(room.length_cm)),
        ("Floor area", f"{room.area_sqm:.2f} m\u00b2"),
        ("Ceiling height", format_length(room.ceiling_height_cm)),
        (
            "Door",
            f"{title_of(room.door.wall)} wall, {format_length(room.door.offset_cm)} "
            f"from the wall origin, {format_length(room.door.width_cm)} wide",
        ),
        (
            "Window",
            f"{title_of(room.window.wall)} wall, "
            f"{format_length(room.window.offset_cm)} from the wall origin, "
            f"{format_length(room.window.width_cm)} wide",
        ),
        ("Design style", title_of(prefs.style)),
        ("Colour palette", title_of(prefs.palette)),
        (
            "Material preferences",
            ", ".join(prefs.material_preferences) or "None stated",
        ),
        (
            "Budget limit",
            format_money(result.budget.total_budget, result.budget.currency),
        ),
        (
            "Functional requirements",
            "; ".join(reqs.functional_requirements) or "None stated",
        ),
        ("Additional notes", reqs.notes or "None"),
    ]

    story: list = _heading("B", "Project overview", styles)
    story.append(
        _p(
            "The room and the user's requirements, exactly as they were saved and "
            "used for every calculation in this report.",
            styles["muted"],
        )
    )
    story.append(Spacer(1, 2.4 * mm))
    story.append(_two_column(overview, styles))
    return story


# -- C: brief --------------------------------------------------------------- #


def _brief(result: ProjectResult, styles: dict) -> list:
    brief = result.brief
    story: list = _heading("C", "Design brief", styles)
    story.append(
        _p(
            "Produced by the brief analyzer from the saved room, preferences and "
            "requirements. It describes what the user wants; it does not decide "
            "the design.",
            styles["muted"],
        )
    )
    story.append(Spacer(1, 2.4 * mm))
    story.append(_p(brief.summary, styles["lead"]))
    story.extend(
        _bulleted_block("Functional priorities", brief.functional_priorities, styles)
    )
    story.extend(_bulleted_block("Constraints", brief.constraints, styles))
    story.extend(_bulleted_block("Open questions", brief.ambiguities, styles))
    story.extend(_bulleted_block("Risks worth knowing", brief.warnings, styles))
    return story


# -- D: concept ------------------------------------------------------------- #


def _concept(result: ProjectResult, styles: dict) -> list:
    concept = result.selected_concept
    others = [
        item.name
        for item in result.concepts.concepts
        if item.name.casefold() != concept.name.casefold()
    ]
    rows = [
        ("Concept name", concept.name),
        ("Description", concept.description),
        ("Design direction", concept.design_direction),
        ("Colour and material direction", concept.color_and_material_direction),
        ("Furniture approach", concept.furniture_approach),
        ("Functional rationale", concept.functional_rationale),
        ("Budget suitability", concept.budget_suitability),
    ]

    story: list = _heading("D", "Selected design concept", styles)
    story.append(
        _p(
            f"Chosen by the user from the three generated directions. The other "
            f"two were: {', '.join(others) or 'none recorded'}.",
            styles["muted"],
        )
    )
    story.append(Spacer(1, 2.4 * mm))
    story.append(_two_column(rows, styles))
    return story


# -- E: furniture and materials --------------------------------------------- #


def _furniture_rows(
    recommendations: Sequence[FurnitureRecommendation],
    by_id: dict[str, FurnitureItem],
    priced: dict[str, LineItem],
    currency: str,
    styles: dict,
) -> list[list[object]]:
    """One row per recommendation, priced when the engine priced it."""

    rows: list[list[object]] = []
    for recommendation in recommendations:
        item = by_id.get(recommendation.item_id)
        line = priced.get(recommendation.item_id)
        name = item.name if item else recommendation.item_id
        rationale = (
            _p(recommendation.rationale, styles["cell_muted"])
            if recommendation.rationale
            else ""
        )
        rows.append(
            [
                [Paragraph(escape(name), styles["cell"]), rationale]
                if rationale
                else Paragraph(escape(name), styles["cell"]),
                item.category if item else "Unknown item",
                str(recommendation.quantity),
                (
                    f"{item.width_cm:g} \u00d7 {item.depth_cm:g} cm"
                    if item
                    else "Not available"
                ),
                format_money(line.unit_cost, currency) if line else "Not priced",
                format_money(line.line_total, currency) if line else "Excluded",
            ]
        )
    return rows


def _furniture(
    result: ProjectResult,
    budget: BudgetResult,
    catalog: Sequence[FurnitureItem],
    styles: dict,
) -> list:
    currency = result.budget_analysis.currency
    by_id = {item.item_id: item for item in catalog}
    priced = {line.item_id: line for line in budget.line_items}
    rows = _furniture_rows(
        result.recommendations, by_id, priced, currency, styles
    )

    story: list = _heading("E", "Furniture and materials", styles)
    story.append(
        _p(
            "The catalog items the advisor selected for the chosen concept, with "
            "the costs the budget engine calculated and the copies the placement "
            "engine accepted. Dimensions are the local catalog's own values.",
            styles["muted"],
        )
    )
    story.append(Spacer(1, 2.4 * mm))
    header = [
        "Item",
        "Category",
        "Qty",
        "Dimensions",
        "Unit cost",
        "Line total",
    ]
    table = _data_table(
        header,
        rows,
        [52 * mm, 26 * mm, 14 * mm, 26 * mm, 28 * mm, 28 * mm],
        styles,
        numeric=(2, 4, 5),
    )
    story.append(table)
    story.append(
        _note(
            f"Furniture subtotal, priced lines only: "
            f"{format_money(result.budget_analysis.furniture_subtotal, currency)}. "
            "Every amount is an indicative estimate taken from the local catalog's "
            "illustrative unit costs, not a verified market price, supplier "
            "quotation or current retail figure.",
            styles,
        )
    )

    if budget.errors:
        story.append(
            _p(
                "Items the budget engine could not price",
                styles["h2"],
            )
        )
        story.extend(_bullets([error.message for error in budget.errors], styles["bullet"]))

    # Materials: always unpriced in V1, and said so rather than shown as zero.
    story.append(Paragraph("Materials and finishes", styles["h2"]))
    if result.materials:
        material_rows = [
            [
                material.name,
                material.category,
                material.color_direction,
                material.rationale,
                material.quantity_note or "Not stated",
            ]
            for material in result.materials
        ]
        story.append(
            _data_table(
                ["Material", "Category", "Colour direction", "Rationale", "Scope"],
                material_rows,
                [30 * mm, 22 * mm, 38 * mm, 58 * mm, 26 * mm],
                styles,
            )
        )
    else:
        story.append(_p("No materials were recommended for this concept.", styles["body"]))
    story.append(
        _note(
            "Not priced \u2014 excluded from furniture cost total. The application "
            "has no material price list, so material cost is unknown rather than "
            "zero, and it is outside the furniture subtotal above.",
            styles,
        )
    )

    if result.color_direction or result.design_rationale:
        story.append(Paragraph("Advisor's overall direction", styles["h2"]))
        if result.color_direction:
            story.append(_two_column([("Colour direction", result.color_direction)], styles))
        if result.design_rationale:
            story.append(_two_column([("Design rationale", result.design_rationale)], styles))
    return story


# -- F: plan ---------------------------------------------------------------- #


def _placement_status(outcome: PlacementOutcome | None) -> tuple[str, str]:
    if outcome is None:
        return (
            "Layout not recorded",
            "No placement result is stored for this project, so there is no "
            "validated layout to draw.",
        )
    if outcome.is_complete:
        return (
            "Complete layout",
            f"All {outcome.requested_count} requested items were placed and "
            "validated by the spatial engine.",
        )
    if outcome.is_partial:
        return (
            "Partial layout",
            f"{outcome.placed_count} of {outcome.requested_count} requested items "
            "were placed. The items listed as unplaced are not in the room, so "
            "this design is only partly buildable.",
        )
    return (
        "Layout failed",
        "No valid layout could be produced. Nothing is drawn, because drawing the "
        "rejected candidate would present furniture that the spatial engine "
        "refused.",
    )


def _layout_phrase(result: ProjectResult) -> str:
    """How the cover describes the plan, in agreement with the real outcome.

    The cover is printed before the plan section, so it cannot say "a validated
    2D layout" unconditionally: for a partial or failed placement that sentence
    would claim something the rest of the document contradicts.
    """

    outcome = result.placement
    if outcome is None:
        return "a room plan"
    if outcome.is_complete:
        return "a validated 2D layout"
    if outcome.is_partial:
        return "a partly validated 2D layout"
    return "a room plan that could not be validated"


def _plan(result: ProjectResult, styles: dict) -> list:
    outcome = result.placement
    status, sentence = _placement_status(outcome)
    # The heading must agree with the verdict underneath it: a failed layout is
    # not a validated one, and printing "Validated" above "Layout failed" would
    # misdescribe the report's own content. A partial layout is drawn, but the
    # design as a whole was not validated, so it gets its own wording.
    if outcome is not None and outcome.is_complete:
        title = "Validated 2D room plan"
    elif outcome is not None and outcome.is_partial:
        title = "2D room plan (partial layout)"
    else:
        title = "2D room plan (not drawn)"
    drawn = outcome is not None and not outcome.is_failed and bool(outcome.placed)
    story: list = _heading("F", title, styles)
    story.append(_p(status, styles["h2"]))
    story.append(_p(sentence, styles["body"]))

    if not drawn:
        story.append(
            _note(
                "No plan is drawn in this report. The room measurements and the "
                "requested items are described in sections B and E.",
                styles,
            )
        )
        return story

    story.append(Spacer(1, 1.6 * mm))
    story.append(
        KeepTogether(
            [
                _RoomPlan(result.room, outcome.placed),
                _note(
                    "Drawn to scale from the coordinates the placement engine "
                    "produced: each rectangle is a catalog footprint after "
                    "rotation, positioned from the room's south-west corner.",
                    styles,
                ),
            ]
        )
    )
    story.append(
        _note(
            "The plan is calculated, not interpreted. The selected concept in "
            "section D describes a design direction in words; the layout engine "
            "does not read that text. It places the catalog pieces it is given "
            "under its own fixed rules, so a position here may differ from where "
            "the concept's wording suggests a piece would go.",
            styles,
        )
    )
    story.append(
        _note(
            "Legend: filled rectangles are placed furniture; the dark line is the "
            "room boundary; the heavier accent line is the door and the lighter "
            "line is the window. Labels wrap onto a second line where a block is "
            "narrow, and a block too small for its name carries none; the full "
            "details follow in the table.",
            styles,
        )
    )

    rows = [
        [
            footprint.label,
            f"{footprint.width_cm:g} \u00d7 {footprint.depth_cm:g} cm",
            f"{footprint.rotation_degrees}\u00b0",
            f"{footprint.left_cm:g}, {footprint.bottom_cm:g} cm",
        ]
        for footprint in outcome.placed
    ]
    story.append(Paragraph("Placed pieces", styles["h2"]))
    story.append(
        _data_table(
            ["Item", "Placed size", "Rotation", "Position (x, y)"],
            rows,
            [76 * mm, 34 * mm, 22 * mm, 42 * mm],
            styles,
            numeric=(1, 2, 3),
        )
    )
    story.append(
        _note(
            "Placed size is the catalog size after rotation. Position is the "
            "footprint's south-west corner in centimetres.",
            styles,
        )
    )

    if outcome.unplaced:
        story.append(Paragraph("Items that were not placed", styles["h2"]))
        story.extend(
            _bullets(
                [
                    f"{item.label} \u2014 {item.count} "
                    f"{'copy' if item.count == 1 else 'copies'} not placed. "
                    f"{item.reason}"
                    for item in outcome.unplaced
                ],
                styles["bullet"],
            )
        )
        story.append(
            _note(
                "These copies are not in the plan and are not counted as placed. "
                "They remain in the basket and therefore in the estimate, because "
                "that is what the design asks for.",
                styles,
            )
        )
    return story


# -- G: spatial validation -------------------------------------------------- #


def _spatial(result: ProjectResult, styles: dict) -> list:
    validation = result.spatial_validation
    outcome = result.placement
    status, sentence = _placement_status(outcome)
    blocking = list(validation.boundary_violations) + list(validation.overlaps)

    rows = [("Placement status", status)]
    if outcome is not None:
        rows.extend(
            [
                ("Items placed", str(outcome.placed_count)),
                (
                    "Items requested",
                    str(outcome.requested_count),
                ),
            ]
        )
        if outcome.unplaced:
            rows.append(("Items not placed", str(outcome.unplaced_count)))
        if outcome.score is not None:
            rows.append(
                (
                    "Layout score",
                    f"{outcome.score:.2f} \u2014 a heuristic layout score, not a "
                    "design-quality rating",
                )
            )
        if outcome.strategy:
            rows.append(("Placement strategy", outcome.strategy))
    rows.append(
        ("Geometric validity", "Valid" if validation.is_valid else "Not valid")
    )
    rows.append(("Blocking problems", str(len(blocking))))
    rows.append(("Warnings", str(len(validation.warnings))))

    story: list = _heading("G", "Spatial validation", styles)
    story.append(_p(sentence, styles["body"]))
    if outcome is not None and outcome.strategy:
        story.append(
            _note(
                "The placement strategy names which wall the engine tried first "
                "while searching for a layout. The engine builds one candidate "
                "per wall order and keeps the best-scoring one, so the name "
                "reports how this layout was found rather than a design decision "
                "about the room.",
                styles,
            )
        )
    story.append(Spacer(1, 2 * mm))
    story.append(_two_column(rows, styles))

    story.append(Paragraph("Blocking problems", styles["h2"]))
    if blocking:
        story.extend(_bullets(blocking, styles["bullet"]))
    else:
        story.append(_p("None. The layout passed every blocking check.", styles["body"]))

    story.append(Paragraph("Warnings", styles["h2"]))
    if validation.warnings:
        story.extend(_bullets(validation.warnings, styles["bullet"]))
    else:
        story.append(_p("None recorded.", styles["body"]))
    story.append(
        _note(
            "A warning is not a blocking problem: it describes something worth "
            "knowing and does not stop the layout. The checks keep door and "
            f"window clearance zones free "
            f"({DEFAULT_DOOR_CLEARANCE_CM:g} cm in front of the door is blocking, "
            f"{DEFAULT_WINDOW_CLEARANCE_CM:g} cm in front of the window is a "
            "warning) and reject overlaps and footprints outside the room.",
            styles,
        )
    )
    return story


# -- H: budget -------------------------------------------------------------- #


def _budget(result: ProjectResult, budget: BudgetResult, styles: dict) -> list:
    analysis = result.budget_analysis
    currency = analysis.currency
    over = analysis.is_over_budget

    headline = [
        (
            "Indicative furniture total",
            format_money(analysis.total_estimated, currency),
        ),
        ("Budget limit", format_money(result.budget.total_budget, currency)),
    ]
    if over:
        headline.append(
            (
                "Over budget by",
                format_money(abs(analysis.remaining_budget), currency),
            )
        )
    else:
        headline.append(
            ("Remaining budget", format_money(analysis.remaining_budget, currency))
        )
    if budget.budget_usage_percent is not None:
        headline.append(
            ("Budget usage", f"{budget.budget_usage_percent}% of the limit")
        )

    composition = [
        ("Furniture subtotal", format_money(analysis.furniture_subtotal, currency)),
        (
            "Materials and finishes",
            "Not priced \u2014 excluded from the total",
        ),
        ("Other expenses", "None recorded"),
        ("Total estimated", format_money(analysis.total_estimated, currency)),
    ]

    story: list = _heading("H", "Budget analysis", styles)
    story.append(
        _p(
            "Every figure in this section was calculated by the application's "
            "budget engine from the local catalog and the quantities in the "
            "basket. The AI model never prices an item or totals a basket.",
            styles["muted"],
        )
    )
    story.append(Spacer(1, 2.4 * mm))
    story.append(_two_column(headline, styles))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph("How the total is built", styles["h2"]))
    story.append(_two_column(composition, styles))

    if over:
        story.append(
            _p(
                f"The indicative furniture total exceeds the budget you set by "
                f"{format_money(abs(analysis.remaining_budget), currency)}. The "
                "design is not affordable as priced.",
                styles["body"],
            )
        )
    else:
        story.append(
            _p(
                "The indicative furniture total fits inside the budget you set.",
                styles["body"],
            )
        )

    if not budget.is_trustworthy:
        story.append(
            _p(
                "The estimate is incomplete: it could not price every item in the "
                "basket, so the total covers only the items listed with a cost. "
                "It is not a final figure.",
                styles["body"],
            )
        )

    if budget.line_items:
        story.append(Paragraph("Cost by item", styles["h2"]))
        story.append(
            _data_table(
                ["Item", "Qty", "Unit cost", "Line total"],
                [
                    [
                        line.name,
                        str(line.quantity),
                        format_money(line.unit_cost, currency),
                        format_money(line.line_total, currency),
                    ]
                    for line in budget.line_items
                ],
                [86 * mm, 16 * mm, 36 * mm, 36 * mm],
                styles,
                numeric=(1, 2, 3),
            )
        )
        if len(budget.line_items) >= 2:
            story.append(Spacer(1, 3 * mm))
            story.append(_CostBars(budget.line_items, currency))
            story.append(
                _note(
                    "Same figures as the table: each bar is one line total. "
                    "Materials are absent because they are not priced.",
                    styles,
                )
            )
    else:
        story.append(
            _p("No item in the basket could be priced, so there is no item table.", styles["body"])
        )

    story.append(
        _note(
            "This is a furniture estimate only. Materials, labour, delivery, "
            "installation and VAT are outside it, and no figure here is a "
            "supplier quotation or a current retail price.",
            styles,
        )
    )
    return story


# -- I: evaluation ---------------------------------------------------------- #


def _evaluation(result: ProjectResult, styles: dict) -> list:
    evaluation = result.evaluation
    story: list = _heading("I", "AI design evaluation", styles)
    story.append(
        _p(
            "The model read the brief, the selected concept, the recommended "
            "catalog items and the results calculated by the application, then "
            "wrote this critique. The layout, the prices and the spatial verdict "
            "above were not changed by it.",
            styles["muted"],
        )
    )
    story.append(Spacer(1, 2.4 * mm))
    story.append(
        _two_column(
            [
                ("How well the brief is met", evaluation.requirement_compatibility),
                ("Style and concept consistency", evaluation.style_consistency),
                ("How the room will work in use", evaluation.functional_suitability),
                ("Budget suitability", evaluation.budget_suitability),
            ],
            styles,
        )
    )
    story.extend(_bulleted_block("Limitations and risks", evaluation.limitations, styles))
    story.extend(
        _bulleted_block("Improvement suggestions", evaluation.recommendations, styles)
    )
    story.append(
        _note(
            "This is a design opinion, not an engineering approval. The evaluation "
            "schema has four written judgements and two lists, so this report "
            "shows no score and no overall verdict: none exists to show. The "
            "critique does not certify structural, ergonomic, accessibility or "
            "building-code compliance, and it cannot make an incomplete layout "
            "complete.",
            styles,
        )
    )
    return story


# -- J: limitations --------------------------------------------------------- #


def _limitations(styles: dict) -> list:
    points = [
        "This report is an AI-assisted design output produced within the V1 scope "
        "of Hometsy \u2014 Room Intelligence Studio.",
        "Furniture placement is checked against a rectangular room, the room's "
        "door and window, and the application's own simple rules. Irregular "
        "geometry, sloped ceilings, columns and multi-room layouts are outside "
        "this version.",
        "The layout score is the result of the application's placement heuristic. "
        "It is not a design-quality rating, and a high score does not mean the "
        "room is well designed.",
        "Catalog prices are illustrative values recorded with the local catalog. "
        "They are not verified current market prices, supplier quotations or "
        "retail figures.",
        "Materials are not priced in this version, so material cost is unknown "
        "and is excluded from the budget analysis rather than counted as zero.",
        "This document is not a professional construction or implementation "
        "drawing, not a bill of quantities, and not an engineering approval.",
        "Confirm real measurements, product availability and current prices with "
        "the relevant suppliers before purchasing anything described here.",
    ]
    story: list = _heading("J", "Limitations and disclaimer", styles)
    story.extend(_bullets(points, styles["bullet"]))
    story.append(
        _note(
            "Report generated by Hometsy V1. The figures are reproducible from the "
            "saved project data: the layout comes from the placement engine, the "
            "money from the budget engine, and the written critique from the AI "
            "evaluation.",
            styles,
        )
    )
    return story


# -- A: cover --------------------------------------------------------------- #


def _cover(result: ProjectResult, generated_at: datetime, styles: dict) -> list:
    room = result.room
    story: list = [
        Spacer(1, 30 * mm),
        _p(BRAND_NAME, styles["cover_brand"]),
        _p(BRAND_SUBTITLE, styles["cover_sub"]),
        Spacer(1, 5 * mm),
        HRFlowable(width="100%", thickness=1, color=_ACCENT, spaceAfter=0),
        Spacer(1, 40 * mm),
        _p(room.name, styles["cover_title"]),
        Spacer(1, 3 * mm),
        _p(
            f"{title_of(room.room_type)} \u00b7 {room.area_sqm:.2f} m\u00b2",
            styles["cover_sub"],
        ),
        Spacer(1, 26 * mm),
        _two_column(
            [
                ("Report", REPORT_TITLE),
                ("Generated", format_date(generated_at)),
                ("Design style", title_of(result.preferences.style)),
                ("Palette direction", title_of(result.preferences.palette)),
                (
                    "Budget limit",
                    format_money(
                        result.budget.total_budget, result.budget.currency
                    ),
                ),
            ],
            styles,
        ),
        Spacer(1, 22 * mm),
        _p(
            "An AI-assisted interior design study for one rectangular room: the "
            "structured brief, the selected concept, the furniture and materials, "
            f"{_layout_phrase(result)}, the indicative budget and a written design "
            "evaluation.",
            styles["lead"],
        ),
        Spacer(1, 4 * mm),
        _p("V1 \u00b7 AI-assisted design report", styles["muted"]),
    ]
    return story


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def _document(path: Path) -> BaseDocTemplate:
    doc = BaseDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=MARGIN_SIDE,
        rightMargin=MARGIN_SIDE,
        topMargin=MARGIN_TOP,
        bottomMargin=MARGIN_BOTTOM,
        title=REPORT_TITLE,
        author="Hometsy — Room Intelligence Studio",
        subject="AI-assisted room design report",
        creator="Hometsy V1",
    )

    cover_frame = Frame(
        MARGIN_SIDE,
        MARGIN_BOTTOM,
        PAGE_WIDTH - 2 * MARGIN_SIDE,
        PAGE_HEIGHT - MARGIN_TOP - MARGIN_BOTTOM,
        id="cover",
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )
    body_frame = Frame(
        MARGIN_SIDE,
        MARGIN_BOTTOM,
        PAGE_WIDTH - 2 * MARGIN_SIDE,
        PAGE_HEIGHT - MARGIN_TOP - MARGIN_BOTTOM,
        id="body",
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )
    doc.addPageTemplates(
        [
            PageTemplate(id="cover", frames=[cover_frame], onPage=_draw_cover_footer),
            PageTemplate(id="body", frames=[body_frame], onPage=_draw_body_header),
        ]
    )
    return doc


def build_story(
    result: ProjectResult,
    *,
    catalog: Sequence[FurnitureItem],
    budget: BudgetResult,
    generated_at: datetime,
) -> list:
    """The document as a list of flowables, in report order.

    Separated from :func:`write_report` so tests can inspect the structure
    without writing a file, and so a future export format could reuse it.
    """

    styles = _styles()
    story: list = _cover(result, generated_at, styles)
    story.append(NextPageTemplate("body"))
    story.append(PageBreak())
    for section in (
        _overview(result, styles),
        _brief(result, styles),
        _concept(result, styles),
        _furniture(result, budget, catalog, styles),
        _plan(result, styles),
        _spatial(result, styles),
        _budget(result, budget, styles),
        _evaluation(result, styles),
        _limitations(styles),
    ):
        story.extend(section)
        # A section always starts on a fresh page: a long report reads as a
        # document rather than a continuous scroll, and a section heading can
        # never be trapped at the foot of the previous page.
        story.append(PageBreak())
    story.pop()
    return story


def write_report(
    result: ProjectResult,
    *,
    catalog: Sequence[FurnitureItem],
    budget: BudgetResult,
    path: Path,
    generated_at: datetime | None = None,
) -> Path:
    """Write the PDF to ``path`` and return it. Raises on failure."""

    register_fonts()
    moment = generated_at or datetime.now().astimezone()
    story = build_story(
        result, catalog=catalog, budget=budget, generated_at=moment
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        doc = _document(path)
        doc.project_title = result.room.name
        doc.build(story, canvasmaker=_NumberedCanvas)
    except ReportGenerationError:
        raise
    except Exception as exc:  # noqa: BLE001 - re-raised with a readable message
        raise ReportGenerationError(
            "The PDF could not be produced. The project data is unchanged, so the "
            "report can be generated again."
        ) from exc
    return path


def generate_report(
    result: ProjectResult,
    *,
    catalog: Sequence[FurnitureItem],
    budget: BudgetResult,
    output_dir: Path | None = None,
    generated_at: datetime | None = None,
) -> Path:
    """Write a report into the controlled output directory.

    The filename is derived from the project name through
    :func:`report_filename`, and the final path is checked to be inside
    ``output_dir``, so nothing the user typed can choose where the file lands.
    """

    directory = (output_dir or OUTPUT_DIR).resolve()
    filename = report_filename(result.room.name)
    path = (directory / filename).resolve()
    if directory not in path.parents:
        raise ReportGenerationError(
            "The report filename resolved outside the report directory."
        )
    return write_report(
        result,
        catalog=catalog,
        budget=budget,
        path=path,
        generated_at=generated_at,
    )


__all__ = [
    "OUTPUT_DIR",
    "PALETTE",
    "REPORT_TITLE",
    "ReportGenerationError",
    "build_story",
    "format_money",
    "generate_report",
    "register_fonts",
    "report_filename",
    "write_report",
]
