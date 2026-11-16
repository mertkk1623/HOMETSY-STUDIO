"""The PDF report generator.

These tests exercise the real ReportLab document, because the things that can go
wrong here are the ones a mock would hide: a missing font, a table that overflows,
a plan drawn from invented coordinates, a truncated multi-page document. Every
test reads the produced bytes back rather than trusting the return value.

What is asserted, and why
-------------------------
* the file exists, starts with ``%PDF`` and is not empty;
* the report is multi-page, and every page after the cover carries a header and
  a "Page n of N" footer, so a reader can tell where they are;
* Turkish characters survive into the text layer (ğ Ğ ş Ş ı İ ö Ö ü Ü ç Ç), and
  the font that carries them is embedded rather than assumed;
* a ``FAILED`` layout draws no plan, a ``PARTIAL`` one draws only what was placed
  and says how much is missing;
* an unpriced item or material is reported as unpriced, never as zero;
* quantities above one reach the cost table and the plan;
* the coordinates in the plan are the ones the placement engine stored;
* the download filename is safe whatever the project is called.

Nothing here calls the AI layer or the network.
"""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from reportlab.lib.units import mm

from core.budget_engine import BudgetResult, compute_budget
from core import report_generator
from core.report_generator import (
    ReportGenerationError,
    build_story,
    format_money,
    generate_report,
    register_fonts,
    report_filename,
    write_report,
)
from core.spatial_engine import DEFAULT_DOOR_CLEARANCE_CM
from models.schemas import (
    BudgetAnalysis,
    ConceptCollection,
    DesignBrief,
    DesignConcept,
    DesignEvaluation,
    FurnitureItem,
    FurnitureRecommendation,
    MaterialRecommendation,
    PlacedFootprint,
    PlacementOutcome,
    PlacementStatus,
    ProjectResult,
    SpatialValidation,
)
from ui import commits, theme

GENERATED_AT = datetime(2026, 11, 15, 14, 30)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


def make_concept(name: str = "Quiet Oak") -> DesignConcept:
    return DesignConcept(
        name=name,
        description=f"{name} builds a quiet composition around the window.",
        design_direction="Low horizontal lines with a clear centre.",
        color_and_material_direction="Warm neutrals, oak and linen.",
        furniture_approach="One large sofa and two light occasional pieces.",
        functional_rationale="Leaves a continuous path from door to window.",
        budget_suitability="Fits within the stated budget.",
    )


def make_brief() -> DesignBrief:
    return DesignBrief(
        summary="A calm living room for four with a reading corner at the window.",
        functional_priorities=["Seating for four", "Reading corner"],
        constraints=["One door and one window"],
        ambiguities=["Seating type is not specified"],
        warnings=["A four-seat sofa may crowd the room"],
    )


def make_evaluation() -> DesignEvaluation:
    return DesignEvaluation(
        requirement_compatibility="Seating for four is met by one three-seat sofa.",
        style_consistency="The oak and linen palette matches the chosen direction.",
        functional_suitability="The path from the door to the window stays clear.",
        budget_suitability="The selected items stay within the stated budget.",
        limitations=["The reading corner is only implied"],
        recommendations=["Add a floor lamp beside the armchair"],
    )


def make_placement(
    *,
    status: PlacementStatus = PlacementStatus.COMPLETE,
    placed: tuple[PlacedFootprint, ...] | None = None,
    unplaced: tuple = (),
    score: float | None = 0.78,
) -> PlacementOutcome:
    if placed is None:
        placed = (
            PlacedFootprint(
                item_id="sofa_three_seat",
                label="Three-seat sofa",
                left_cm=20,
                bottom_cm=20,
                width_cm=210,
                depth_cm=90,
            ),
            PlacedFootprint(
                item_id="coffee_table",
                label="Coffee table",
                left_cm=120,
                bottom_cm=170,
                width_cm=90,
                depth_cm=60,
            ),
        )
    return PlacementOutcome(
        status=status,
        strategy="grid",
        score=score,
        placed=list(placed),
        unplaced=list(unplaced),
        notes=["Placed from the stored basket."],
    )


def make_result(
    room,
    preferences,
    requirements,
    budget,
    catalog: tuple[FurnitureItem, ...],
    *,
    recommendations: tuple[FurnitureRecommendation, ...] | None = None,
    placement: PlacementOutcome | None = None,
    materials: tuple[MaterialRecommendation, ...] = (),
    evaluation: DesignEvaluation | None = None,
    concept: DesignConcept | None = None,
) -> tuple[ProjectResult, BudgetResult]:
    """A complete project plus the budget result the report is built from."""

    selected = concept or make_concept()
    concepts = ConceptCollection(
        concepts=[
            selected,
            make_concept("Soft Contrast"),
            make_concept("Warm Studio"),
        ]
    )
    basket = list(
        recommendations
        or (
            FurnitureRecommendation(
                item_id="sofa_three_seat", quantity=1, rationale="Main seating."
            ),
            FurnitureRecommendation(
                item_id="coffee_table", quantity=1, rationale="Centres the group."
            ),
        )
    )
    budget_result = compute_budget(budget, basket, catalog)
    result = ProjectResult(
        room=room,
        preferences=preferences,
        requirements=requirements,
        budget=budget,
        brief=make_brief(),
        concepts=concepts,
        selected_concept=selected,
        recommendations=basket,
        spatial_validation=SpatialValidation(
            is_valid=True, warnings=["Window clearance zone lightly used."]
        ),
        budget_analysis=budget_result.analysis,
        evaluation=evaluation or make_evaluation(),
        materials=list(materials),
        color_direction="Warm off-whites with pale oak and muted olive accents.",
        design_rationale="A restrained palette keeps the small room calm.",
        placement=placement if placement is not None else make_placement(),
    )
    return result, budget_result


# --------------------------------------------------------------------------- #
# A minimal PDF reader
#
# No third-party PDF library is installed, and adding one for a test would be a
# dependency the project does not need. This reads only what the assertions
# require: the page count, the embedded font names, and the decoded text layer.
# --------------------------------------------------------------------------- #


def _objects(data: bytes) -> dict[int, bytes]:
    return {
        int(match.group(1)): match.group(2)
        for match in re.finditer(rb"(\d+)\s+0\s+obj(.*?)endobj", data, re.S)
    }


def _stream(body: bytes) -> bytes:
    match = re.search(rb"stream\r?\n(.*?)endstream", body, re.S)
    if not match:
        return b""
    import base64
    import zlib

    raw = match.group(1)
    filters = re.search(rb"/Filter\s*\[(.*?)\]", body, re.S)
    names = (
        re.findall(rb"/(\w+)", filters.group(1))
        if filters
        else re.findall(rb"/Filter\s*/(\w+)", body)
    )
    data = raw
    for name in names:
        if name == b"ASCII85Decode":
            data = base64.a85decode(data, adobe=True)
        elif name == b"FlateDecode":
            data = zlib.decompress(data)
    return data


def _cmap(text: bytes) -> dict[int, str]:
    mapping: dict[int, str] = {}
    for block in re.findall(rb"beginbfchar(.*?)endbfchar", text, re.S):
        for src, dst in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", block):
            mapping[int(src, 16)] = bytes.fromhex(dst.decode()).decode(
                "utf-16-be", "replace"
            )
    for block in re.findall(rb"beginbfrange(.*?)endbfrange", text, re.S):
        for lo, hi, dst in re.findall(
            rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", block
        ):
            start, end, base = int(lo, 16), int(hi, 16), int(dst, 16)
            for offset in range(end - start + 1):
                mapping[start + offset] = chr(base + offset)
    return mapping


def _unescape(raw: bytes) -> bytes:
    out = bytearray()
    index = 0
    simple = {
        ord("n"): 0x0A,
        ord("r"): 0x0D,
        ord("t"): 0x09,
        ord("b"): 0x08,
        ord("f"): 0x0C,
    }
    while index < len(raw):
        byte = raw[index]
        index += 1
        if byte != 0x5C:
            out.append(byte)
            continue
        if index >= len(raw):
            break
        nxt = raw[index]
        index += 1
        if nxt in simple:
            out.append(simple[nxt])
        elif 0x30 <= nxt <= 0x37:
            digits = bytes([nxt])
            while index < len(raw) and len(digits) < 3 and 0x30 <= raw[index] <= 0x37:
                digits += bytes([raw[index]])
                index += 1
            out.append(int(digits, 8) & 0xFF)
        elif nxt in (0x0A, 0x0D):
            continue
        else:
            out.append(nxt)
    return bytes(out)


def pdf_pages(path: Path) -> list[str]:
    """The text layer of each page, in document order."""

    data = path.read_bytes()
    objects = _objects(data)
    cmaps: dict[bytes, dict[int, str]] = {}
    for body in objects.values():
        if b"/ToUnicode" not in body:
            continue
        ref = re.search(rb"/ToUnicode\s+(\d+)\s+0\s+R", body)
        name = re.search(rb"/Name\s*/([\w+]+)", body)
        if ref and name and int(ref.group(1)) in objects:
            cmaps[name.group(1)] = _cmap(_stream(objects[int(ref.group(1))]))

    pages: list[str] = []
    for body in objects.values():
        if b"/Contents" not in body or b"/MediaBox" not in body:
            continue
        ref = re.search(rb"/Contents\s+(\d+)\s+0\s+R", body)
        if not ref:
            continue
        content = _stream(objects.get(int(ref.group(1)), b""))
        current: dict[int, str] = {}
        chunks: list[str] = []
        for match in re.finditer(
            rb"/([\w+]+)\s+[\d.]+\s+Tf|\((.*?)(?<!\\)\)\s*Tj|\[(.*?)\]\s*TJ",
            content,
            re.S,
        ):
            if match.group(1):
                current = cmaps.get(match.group(1), {})
            elif match.group(2) is not None:
                chunks.append(_decode(match.group(2), current))
            else:
                for piece in re.findall(rb"\((.*?)(?<!\\)\)", match.group(3), re.S):
                    chunks.append(_decode(piece, current))
        pages.append(" ".join(chunks))
    return pages


def pdf_text(path: Path) -> str:
    """The document's text layer, in page order."""

    return " ".join(pdf_pages(path))


def _decode(raw: bytes, cmap: dict[int, str]) -> str:
    raw = _unescape(raw)
    if not cmap:
        return raw.decode("latin-1")
    return "".join(cmap.get(byte, "") for byte in raw)


def page_count(path: Path) -> int:
    return len(
        [
            body
            for body in _objects(path.read_bytes()).values()
            if b"/Contents" in body and b"/MediaBox" in body
        ]
    )


# --------------------------------------------------------------------------- #
# Harness
# --------------------------------------------------------------------------- #


@pytest.fixture
def written(tmp_path, room, preferences, requirements, budget, catalog):
    """Write one report and return ``(path, result, budget_result)``."""

    result, estimate = make_result(
        room, preferences, requirements, budget, catalog
    )
    path = write_report(
        result,
        catalog=catalog,
        budget=estimate,
        path=tmp_path / "report.pdf",
        generated_at=GENERATED_AT,
    )
    return path, result, estimate


# --------------------------------------------------------------------------- #
# 1. The file
# --------------------------------------------------------------------------- #


def test_the_report_is_written_and_is_a_pdf(written) -> None:
    path, _, _ = written
    assert path.exists()
    assert path.stat().st_size > 0
    assert path.read_bytes()[:5] == b"%PDF-"


def test_the_report_is_multi_page(written) -> None:
    path, _, _ = written
    assert page_count(path) >= 10


def test_every_body_page_is_numbered_and_has_a_header(written) -> None:
    path, _, _ = written
    text = pdf_text(path)
    labels = re.findall(r"Page (\d+) of (\d+)", text)
    assert labels, "no page numbers were found"
    total = int(labels[0][1])
    assert total == page_count(path)
    # The cover carries no number; every later page does.
    assert [int(number) for number, _ in labels] == list(range(2, total + 1))
    assert text.count("HOMETSY") >= total - 1


def test_the_report_names_every_required_section(written) -> None:
    path, _, _ = written
    text = pdf_text(path)
    for section in (
        "Project overview",
        "Design brief",
        "Selected design concept",
        "Furniture and materials",
        "Validated 2D room plan",
        "Spatial validation",
        "Budget analysis",
        "AI design evaluation",
        "Limitations and disclaimer",
    ):
        assert section in text, section


def test_the_cover_carries_the_brand_and_the_room(written) -> None:
    path, result, _ = written
    text = pdf_text(path)
    assert "HOMETSY" in text
    assert "Room Intelligence Studio" in text
    assert result.room.name in text
    assert "V1" in text and "AI-assisted design report" in text
    assert "15 November 2026" in text


# --------------------------------------------------------------------------- #
# 2. Turkish characters and fonts
# --------------------------------------------------------------------------- #


TURKISH = "ğĞşŞıİöÖüÜçÇ"


def test_the_font_contains_every_turkish_letter() -> None:
    from reportlab.pdfbase.ttfonts import TTFontFile

    register_fonts()
    faces = [report_generator.FONT_REGULAR, report_generator.FONT_BOLD]
    for face in faces:
        charset = TTFontFile(str(face)).charToGlyph
        missing = [character for character in TURKISH if ord(character) not in charset]
        assert missing == [], f"{face.name} cannot draw {missing}"


def test_the_font_is_embedded_in_the_pdf(written) -> None:
    path, _, _ = written
    data = path.read_bytes()
    # An embedded TrueType face, not a reference to a base-14 font.
    assert b"/FontFile2" in data
    assert b"DejaVuSans" in data


def test_turkish_text_survives_into_the_text_layer(tmp_path, catalog) -> None:
    from decimal import Decimal

    from models.schemas import (
        BudgetInput,
        DesignPreferences,
        DesignStyle,
        OpeningInput,
        PaletteDirection,
        RoomInput,
        RoomType,
        UserRequirements,
        Wall,
    )

    room = RoomInput(
        room_type=RoomType.LIVING_ROOM,
        name="Şişli Salonu — Çalışma Köşesi",
        width_cm=400,
        length_cm=520,
        ceiling_height_cm=270,
        door=OpeningInput(wall=Wall.SOUTH, offset_cm=20, width_cm=80),
        window=OpeningInput(wall=Wall.NORTH, offset_cm=20, width_cm=80),
    )
    preferences = DesignPreferences(
        style=DesignStyle.JAPANDI,
        palette=PaletteDirection.WARM_NEUTRAL,
        material_preferences=["meşe", "keten"],
    )
    requirements = UserRequirements(
        functional_requirements=["Dört kişilik oturma", "Okuma köşesi"],
        notes="Pencere tarafı açık kalsın. Işık kuzeyden geliyor.",
    )
    result, estimate = make_result(
        room,
        preferences,
        requirements,
        BudgetInput(total_budget=Decimal("85000.00")),
        catalog,
        evaluation=DesignEvaluation(
            requirement_compatibility="Dört kişilik oturma sağlanıyor.",
            style_consistency="Japandi yönüyle tutarlı.",
            functional_suitability="Kapıdan pencereye geçiş açık.",
            budget_suitability="Bütçe içinde kalıyor.",
        ),
    )
    path = write_report(
        result,
        catalog=catalog,
        budget=estimate,
        path=tmp_path / "turkish.pdf",
        generated_at=GENERATED_AT,
    )
    text = pdf_text(path)

    for needle in (
        "Şişli Salonu",
        "Çalışma Köşesi",
        "Dört kişilik oturma",
        "Okuma köşesi",
        "Pencere tarafı açık kalsın",
        "Işık kuzeyden geliyor",
        "meşe",
        "Japandi yönüyle tutarlı",
        "Bütçe içinde kalıyor",
    ):
        assert needle in text, needle

    found = {character for character in text if character in TURKISH}
    # The report must actually use the letters, not merely be able to.
    assert {"ş", "Ş", "ı", "ç", "ö", "ü"} <= found


# --------------------------------------------------------------------------- #
# 3. The plan
# --------------------------------------------------------------------------- #


def test_the_plan_is_drawn_only_for_a_layout_that_was_placed(written) -> None:
    path, _, _ = written
    text = pdf_text(path)
    assert "Complete layout" in text
    assert "Placed pieces" in text
    assert "Drawn to scale" in text


def test_a_failed_layout_draws_no_plan(tmp_path, room, preferences, requirements,
                                       budget, catalog) -> None:
    result, estimate = make_result(
        room,
        preferences,
        requirements,
        budget,
        catalog,
        placement=make_placement(
            status=PlacementStatus.FAILED, placed=(), unplaced=(), score=None
        ),
    )
    path = write_report(
        result,
        catalog=catalog,
        budget=estimate,
        path=tmp_path / "failed.pdf",
        generated_at=GENERATED_AT,
    )
    text = pdf_text(path)
    assert "Layout failed" in text
    assert "No plan is drawn in this report" in text
    # A rejected layout must not be presented as furniture in the room.
    assert "Placed pieces" not in text
    assert "Partial layout" not in text


def test_a_failed_layout_is_not_called_a_validated_plan(tmp_path, room, preferences,
                                                        requirements, budget,
                                                        catalog) -> None:
    """The section heading must agree with the verdict printed under it.

    A report that heads the page "Validated 2D room plan" and then says "Layout
    failed" contradicts itself in the same page. The heading is therefore part
    of the honesty requirement, not decoration.
    """

    result, estimate = make_result(
        room,
        preferences,
        requirements,
        budget,
        catalog,
        placement=make_placement(
            status=PlacementStatus.FAILED, placed=(), unplaced=(), score=None
        ),
    )
    path = write_report(
        result,
        catalog=catalog,
        budget=estimate,
        path=tmp_path / "failed-heading.pdf",
        generated_at=GENERATED_AT,
    )

    pages = pdf_pages(path)
    plan_page = next(p for p in pages if "2D room plan" in p)
    assert "Layout failed" in plan_page
    assert "Validated 2D room plan" not in plan_page, plan_page[:400]
    assert "2D room plan (not drawn)" in plan_page

    # The cover summary must not promise a validated layout either.
    cover = pages[0]
    assert "a validated 2D layout" not in cover
    assert "could not be validated" in cover


def test_a_partial_layout_is_not_called_validated_either(tmp_path, room, preferences,
                                                          requirements, budget,
                                                          catalog) -> None:
    from models.schemas import UnplacedItem

    placed = (
        PlacedFootprint(
            item_id="sofa_three_seat",
            label="Three-seat sofa",
            left_cm=20,
            bottom_cm=20,
            width_cm=210,
            depth_cm=90,
        ),
    )
    result, estimate = make_result(
        room,
        preferences,
        requirements,
        budget,
        catalog,
        placement=make_placement(
            status=PlacementStatus.PARTIAL,
            placed=placed,
            unplaced=(
                UnplacedItem(
                    item_id="armchair",
                    label="Armchair",
                    count=1,
                    reason_code="door_clearance",
                    reason="Every candidate position overlapped the door clearance.",
                ),
            ),
            score=0.4,
        ),
    )
    path = write_report(
        result,
        catalog=catalog,
        budget=estimate,
        path=tmp_path / "partial-heading.pdf",
        generated_at=GENERATED_AT,
    )
    pages = pdf_pages(path)
    plan_page = next(p for p in pages if "2D room plan" in p)
    assert "Partial layout" in plan_page
    assert "Validated 2D room plan" not in plan_page
    # A partly drawn plan is still drawn, so the heading says so explicitly.
    assert "2D room plan (partial layout)" in plan_page
    assert "2D room plan (not drawn)" not in plan_page
    assert "a partly validated 2D layout" in pages[0]
    # ...while the cover is still honest about the shortfall.
    assert "a validated 2D layout" not in pages[0]


def test_a_partial_layout_draws_only_what_was_placed(tmp_path, room, preferences,
                                                     requirements, budget,
                                                     catalog) -> None:
    from models.schemas import UnplacedItem

    placed = (
        PlacedFootprint(
            item_id="sofa_three_seat",
            label="Three-seat sofa",
            left_cm=20,
            bottom_cm=20,
            width_cm=210,
            depth_cm=90,
        ),
    )
    result, estimate = make_result(
        room,
        preferences,
        requirements,
        budget,
        catalog,
        placement=make_placement(
            status=PlacementStatus.PARTIAL,
            placed=placed,
            unplaced=(
                UnplacedItem(
                    item_id="coffee_table",
                    label="Coffee table",
                    count=1,
                    reason_code="no_space",
                    reason="No free area large enough remained.",
                ),
            ),
            score=0.61,
        ),
    )
    path = write_report(
        result,
        catalog=catalog,
        budget=estimate,
        path=tmp_path / "partial.pdf",
        generated_at=GENERATED_AT,
    )
    text = pdf_text(path)
    assert "Partial layout" in text
    assert "1 of 2 requested items were placed" in text
    assert "Items that were not placed" in text
    assert "No free area large enough remained." in text
    # The placed copy is drawn and tabulated; the missing one is not drawn.
    assert "Three-seat sofa" in text
    assert "Coffee table — 1 copy not placed." in text
    assert "Complete layout" not in text


def test_the_plan_uses_the_stored_coordinates(tmp_path, room, preferences,
                                             requirements, budget, catalog) -> None:
    placed = (
        PlacedFootprint(
            item_id="sofa_three_seat",
            label="Corner sofa",
            left_cm=137.5,
            bottom_cm=42.25,
            width_cm=180,
            depth_cm=90,
        ),
    )
    result, estimate = make_result(
        room,
        preferences,
        requirements,
        budget,
        catalog,
        placement=make_placement(
            status=PlacementStatus.COMPLETE, placed=placed, score=0.9
        ),
    )
    path = write_report(
        result,
        catalog=catalog,
        budget=estimate,
        path=tmp_path / "coords.pdf",
        generated_at=GENERATED_AT,
    )
    text = pdf_text(path)
    # The table repeats the engine's own numbers, to the centimetre.
    assert "137.5, 42.25 cm" in text
    assert "180 × 90 cm" in text


def test_the_plan_reports_a_layout_that_was_never_recorded(tmp_path, room,
                                                           preferences,
                                                           requirements, budget,
                                                           catalog) -> None:
    result, estimate = make_result(
        room, preferences, requirements, budget, catalog, placement=None
    )
    result = result.model_copy(update={"placement": None})
    path = write_report(
        result,
        catalog=catalog,
        budget=estimate,
        path=tmp_path / "none.pdf",
        generated_at=GENERATED_AT,
    )
    text = pdf_text(path)
    assert "Layout not recorded" in text
    assert "Placed pieces" not in text


# --------------------------------------------------------------------------- #
# 4. Furniture, quantities and prices
# --------------------------------------------------------------------------- #


def test_quantities_above_one_reach_the_cost_table(tmp_path, room, preferences,
                                                   requirements, budget,
                                                   catalog) -> None:
    basket = (
        FurnitureRecommendation(item_id="coffee_table", quantity=3),
    )
    result, estimate = make_result(
        room,
        preferences,
        requirements,
        budget,
        catalog,
        recommendations=basket,
    )
    path = write_report(
        result,
        catalog=catalog,
        budget=estimate,
        path=tmp_path / "qty.pdf",
        generated_at=GENERATED_AT,
    )
    text = pdf_text(path)

    unit = next(
        item.indicative_unit_cost
        for item in catalog
        if item.item_id == "coffee_table"
    )
    line_total = Decimal(str(unit)) * 3

    # The quantity is carried into both tables and into the arithmetic.
    assert estimate.line_items[0].quantity == 3
    furniture_table = text.split("Furniture and materials")[1].split(
        "Furniture subtotal"
    )[0]
    assert "Coffee table" in furniture_table
    assert " 3 " in furniture_table
    # Three copies are priced as three copies, in both the table and the subtotal.
    assert format_money(Decimal(str(unit))) in text
    assert format_money(line_total) in text
    assert format_money(line_total) == format_money(
        result.budget_analysis.furniture_subtotal
    )


def test_an_unpriced_item_is_named_and_never_costed_at_zero(tmp_path, room,
                                                            preferences,
                                                            requirements, budget,
                                                            catalog) -> None:
    basket = (
        FurnitureRecommendation(item_id="sofa_three_seat", quantity=1),
        FurnitureRecommendation(item_id="not_in_the_catalog", quantity=1),
    )
    result, estimate = make_result(
        room,
        preferences,
        requirements,
        budget,
        catalog,
        recommendations=basket,
    )
    assert not estimate.is_trustworthy

    path = write_report(
        result,
        catalog=catalog,
        budget=estimate,
        path=tmp_path / "unpriced.pdf",
        generated_at=GENERATED_AT,
    )
    text = pdf_text(path)

    # The item appears in the furniture table by its id, is labelled as not
    # priced, and its line is excluded rather than counted as zero.
    assert "not_in_the_catalog" in text
    assert "Not priced" in text
    assert "Excluded" in text
    # The engine's own error is repeated instead of a made-up reason.
    assert "could not price" in text.lower()
    # The incomplete estimate is announced as incomplete.
    assert "The estimate is incomplete" in text

    # Only the priced line reaches the itemised cost table, so the table cannot
    # be read as "this item costs nothing".
    item_table = text.split("Cost by item")[1].split("This is a furniture")[0]
    assert "Three-seat sofa" in item_table
    assert "not_in_the_catalog" not in item_table

    # The subtotal covers the sofa only.
    sofa_unit = next(
        item.indicative_unit_cost
        for item in catalog
        if item.item_id == "sofa_three_seat"
    )
    assert format_money(Decimal(str(sofa_unit))) in text


def test_materials_are_presented_as_unpriced(tmp_path, room, preferences,
                                             requirements, budget, catalog) -> None:
    result, estimate = make_result(
        room,
        preferences,
        requirements,
        budget,
        catalog,
        materials=(
            MaterialRecommendation(
                name="White oak",
                category="Wood",
                color_direction="Pale honey tones.",
                rationale="Matches the Japandi direction.",
                quantity_note="Main furniture pieces.",
            ),
        ),
    )
    path = write_report(
        result,
        catalog=catalog,
        budget=estimate,
        path=tmp_path / "materials.pdf",
        generated_at=GENERATED_AT,
    )
    text = pdf_text(path)
    assert "White oak" in text
    assert "Not priced — excluded from furniture cost total." in text
    # Material money is never part of the furniture total.
    assert estimate.analysis.material_subtotal == Decimal("0.00")


def test_no_materials_says_so_instead_of_inventing_one(tmp_path, room,
                                                       preferences, requirements,
                                                       budget, catalog) -> None:
    result, estimate = make_result(
        room, preferences, requirements, budget, catalog, materials=()
    )
    path = write_report(
        result,
        catalog=catalog,
        budget=estimate,
        path=tmp_path / "no-materials.pdf",
        generated_at=GENERATED_AT,
    )
    text = pdf_text(path)
    assert "No materials were recommended for this concept." in text


def test_the_budget_section_reports_the_engine_figures(written) -> None:
    path, result, estimate = written
    text = pdf_text(path)
    analysis = result.budget_analysis
    assert format_money(analysis.furniture_subtotal) in text
    assert format_money(analysis.total_estimated) in text
    assert format_money(result.budget.total_budget) in text
    assert f"{estimate.budget_usage_percent}% of the limit" in text


def test_an_over_budget_project_is_stated_as_an_overrun(tmp_path, room,
                                                        preferences, requirements,
                                                        catalog) -> None:
    from models.schemas import BudgetInput

    tight = BudgetInput(total_budget=Decimal("5000.00"))
    result, estimate = make_result(
        room, preferences, requirements, tight, catalog
    )
    assert estimate.analysis.is_over_budget

    path = write_report(
        result,
        catalog=catalog,
        budget=estimate,
        path=tmp_path / "over.pdf",
        generated_at=GENERATED_AT,
    )
    text = pdf_text(path)
    assert "Over budget by" in text
    assert "not affordable as priced" in text
    assert "Within budget" not in text.replace("stays within the stated budget", "")


def test_the_material_scope_is_stated_beside_the_total(written) -> None:
    path, _, _ = written
    text = pdf_text(path)
    assert "Not priced — excluded from the total" in text
    assert "Materials, labour, delivery, installation and VAT are outside it" in text


# --------------------------------------------------------------------------- #
# 5. Evaluation, honesty and the disclaimer
# --------------------------------------------------------------------------- #


def test_the_evaluation_is_presented_as_an_opinion_without_a_score(written) -> None:
    path, _, _ = written
    text = pdf_text(path)
    assert "How well the brief is met" in text
    assert "Style and concept consistency" in text
    assert "design opinion, not an engineering approval" in text
    assert "no score and no overall verdict" in text


def test_the_limitations_section_covers_the_required_points(written) -> None:
    path, _, _ = written
    text = pdf_text(path)
    for point in (
        "V1 scope",
        "rectangular room",
        "not a design-quality rating",
        "not verified current market prices",
        "excluded from the budget analysis rather than counted as zero",
        "not an engineering approval",
        "before purchasing",
    ):
        assert point in text, point


def test_the_clearance_rule_is_stated_with_the_engine_constant(written) -> None:
    path, _, _ = written
    text = pdf_text(path)
    assert f"{DEFAULT_DOOR_CLEARANCE_CM:g} cm in front of the door is blocking" in text


# --------------------------------------------------------------------------- #
# 6. Long content and pagination
# --------------------------------------------------------------------------- #


def test_a_long_text_does_not_overflow_the_page(tmp_path, room, preferences,
                                                requirements, budget, catalog) -> None:
    long_summary = "Uzun bir açıklama. " * 90
    long_summary = long_summary[:1500]
    result, estimate = make_result(
        room,
        preferences,
        requirements,
        budget,
        catalog,
        concept=make_concept(),
        evaluation=DesignEvaluation(
            requirement_compatibility=long_summary,
            style_consistency=long_summary,
            functional_suitability=long_summary,
            budget_suitability=long_summary,
            limitations=[f"Kısıt {index}" for index in range(10)],
            recommendations=[f"Öneri {index}" for index in range(10)],
        ),
    )
    path = write_report(
        result,
        catalog=catalog,
        budget=estimate,
        path=tmp_path / "long.pdf",
        generated_at=GENERATED_AT,
    )
    assert path.stat().st_size > 0
    text = pdf_text(path)
    assert "Uzun bir açıklama." in text
    assert "Kısıt 9" in text
    # ReportLab would raise a LayoutError if a paragraph could not be split.
    assert page_count(path) >= 10


def test_a_long_table_repeats_its_header_across_pages(tmp_path) -> None:
    """``repeatRows=1`` is the guarantee, so it is asserted on a table long enough
    to span pages: every page that carries rows must also carry the header."""

    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate

    register_fonts()
    styles = report_generator._styles()
    rows = [
        [
            f"Catalog item {index}",
            "Seating",
            "1",
            "210 \u00d7 90 cm",
            "18.500,00 TRY",
            "18.500,00 TRY",
        ]
        for index in range(60)
    ]
    table = report_generator._data_table(
        ["Item", "Category", "Qty", "Dimensions", "Unit cost", "Line total"],
        rows,
        [52 * mm, 26 * mm, 14 * mm, 26 * mm, 28 * mm, 28 * mm],
        styles,
        numeric=(2, 4, 5),
    )
    path = tmp_path / "long-table.pdf"
    SimpleDocTemplate(str(path), pagesize=A4).build([table])

    pages = [page for page in pdf_pages(path) if page.strip()]
    assert len(pages) >= 2, "the table was not long enough to span pages"
    for number, page in enumerate(pages, start=1):
        assert "Category" in page, f"page {number} lost the header"
        assert "Qty" in page, f"page {number} lost the header"
    # No row was dropped to make the pagination work.
    assert "Catalog item 0" in pages[0]
    assert "Catalog item 59" in pages[-1]


def test_a_long_basket_keeps_every_row(tmp_path, room, preferences, requirements,
                                       budget, catalog) -> None:
    items = [
        item for item in catalog if room.room_type in item.supported_room_types
    ]
    basket = tuple(
        FurnitureRecommendation(item_id=item.item_id, quantity=1)
        for item in items[:12]
    )
    result, estimate = make_result(
        room,
        preferences,
        requirements,
        budget,
        catalog,
        recommendations=basket,
    )
    path = write_report(
        result,
        catalog=catalog,
        budget=estimate,
        path=tmp_path / "rows.pdf",
        generated_at=GENERATED_AT,
    )
    assert len(estimate.line_items) == len(basket)

    text = pdf_text(path)
    furniture_section = text.split("Furniture and materials")[1].split(
        "Spatial validation"
    )[0]
    # Each item name in the basket reaches the report; none is silently dropped.
    for item in items[:12]:
        assert item.name in furniture_section, item.name
    assert furniture_section.count(" TRY") >= len(basket)


# --------------------------------------------------------------------------- #
# 7. Filenames
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Living Room", "hometsy-living-room-report.pdf"),
        ("Şişli Salonu", "hometsy-sisli-salonu-report.pdf"),
        ("Çalışma Köşesi", "hometsy-calisma-kosesi-report.pdf"),
        ("Ölçü & Plan / 2026", "hometsy-olcu-plan-2026-report.pdf"),
        ("   ", "hometsy-project-report.pdf"),
        ("...", "hometsy-project-report.pdf"),
        ("../../etc/passwd", "hometsy-etc-passwd-report.pdf"),
        ("C:\\Windows\\System32", "hometsy-c-windows-system32-report.pdf"),
    ],
)
def test_the_filename_is_safe_and_folded(name: str, expected: str) -> None:
    assert report_filename(name) == expected


def test_the_filename_never_contains_a_path_separator() -> None:
    for name in ("a/b", "a\\b", "../..", "C:/x", "..\\..\\", "/", "\\"):
        filename = report_filename(name)
        assert "/" not in filename
        assert "\\" not in filename
        assert filename.startswith("hometsy-")
        assert filename.endswith("-report.pdf")
        assert filename == Path(filename).name


def test_a_very_long_name_is_shortened() -> None:
    filename = report_filename("A" * 500)
    assert len(filename) <= len("hometsy-") + 60 + len("-report.pdf")


def test_generation_writes_inside_the_output_directory(tmp_path, room, preferences,
                                                       requirements, budget,
                                                       catalog) -> None:
    result, estimate = make_result(
        room, preferences, requirements, budget, catalog
    )
    path = generate_report(
        result,
        catalog=catalog,
        budget=estimate,
        output_dir=tmp_path,
        generated_at=GENERATED_AT,
    )
    assert path.parent == tmp_path.resolve()
    assert path.name == report_filename(room.name)
    assert path.exists()


def test_the_project_name_cannot_escape_the_output_directory(tmp_path, room,
                                                             preferences,
                                                             requirements, budget,
                                                             catalog) -> None:
    escaping = room.model_copy(update={"name": "../../../../tmp/evil"})
    result, estimate = make_result(
        room, preferences, requirements, budget, catalog
    )
    result = result.model_copy(update={"room": escaping})
    path = generate_report(
        result,
        catalog=catalog,
        budget=estimate,
        output_dir=tmp_path,
        generated_at=GENERATED_AT,
    )
    assert path.parent == tmp_path.resolve()
    assert path.name.startswith("hometsy-")


# --------------------------------------------------------------------------- #
# 8. Failure behaviour
# --------------------------------------------------------------------------- #


def test_a_missing_font_is_reported_as_a_report_error(monkeypatch, tmp_path,
                                                      room, preferences,
                                                      requirements, budget,
                                                      catalog) -> None:
    result, estimate = make_result(
        room, preferences, requirements, budget, catalog
    )
    monkeypatch.setattr(report_generator, "_registered", False)
    monkeypatch.setattr(
        report_generator, "FONT_REGULAR", tmp_path / "not-a-font.ttf"
    )
    with pytest.raises(ReportGenerationError) as excinfo:
        write_report(
            result,
            catalog=catalog,
            budget=estimate,
            path=tmp_path / "x.pdf",
        )
    assert "font" in str(excinfo.value).lower()
    monkeypatch.setattr(report_generator, "_registered", True)


def test_a_write_failure_raises_a_report_error_without_leaking_details(
    monkeypatch, tmp_path, room, preferences, requirements, budget, catalog
) -> None:
    result, estimate = make_result(
        room, preferences, requirements, budget, catalog
    )

    def explode(*args, **kwargs):
        raise OSError("disk on fire at C:\\secret\\path")

    monkeypatch.setattr(report_generator.BaseDocTemplate, "build", explode)
    with pytest.raises(ReportGenerationError) as excinfo:
        write_report(
            result,
            catalog=catalog,
            budget=estimate,
            path=tmp_path / "boom.pdf",
        )
    message = str(excinfo.value)
    assert "could not be produced" in message
    assert "disk on fire" not in message
    assert "secret" not in message
    assert "project data is unchanged" in message


# --------------------------------------------------------------------------- #
# 9. The generator does not calculate
# --------------------------------------------------------------------------- #


def test_the_report_repeats_the_engine_total_rather_than_recomputing(
    written,
) -> None:
    path, result, estimate = written
    text = pdf_text(path)
    # Exactly the stored figure, formatted the same way the screen formats it.
    assert format_money(result.budget_analysis.total_estimated) in text
    assert estimate.analysis.total_estimated == result.budget_analysis.total_estimated


def test_the_report_module_does_not_import_the_ai_layer() -> None:
    import ast

    source = Path(report_generator.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "ai" not in imported
    assert "streamlit" not in imported


# --------------------------------------------------------------------------- #
# 10. Parity with the interface
# --------------------------------------------------------------------------- #


def test_the_report_palette_matches_the_design_system() -> None:
    assert report_generator.PALETTE == theme.COLORS


def test_the_report_money_format_matches_the_screen() -> None:
    for amount in (Decimal("0.00"), Decimal("1234.50"), Decimal("85000.00")):
        assert format_money(amount) == commits.format_money(amount)


def test_build_story_is_pure_and_needs_no_file(written) -> None:
    _, result, estimate = written
    story = build_story(
        result,
        catalog=tuple(),
        budget=estimate,
        generated_at=GENERATED_AT,
    )
    assert story
    again = build_story(
        result,
        catalog=tuple(),
        budget=estimate,
        generated_at=GENERATED_AT,
    )
    assert len(story) == len(again)


def test_a_project_without_the_optional_fields_still_reports(tmp_path, room,
                                                             preferences,
                                                             requirements, budget,
                                                             catalog) -> None:
    """A ``ProjectResult`` built before Phase 6 must still produce a report."""

    analysis = BudgetAnalysis(
        furniture_subtotal=Decimal("18500.00"),
        total_estimated=Decimal("18500.00"),
        remaining_budget=Decimal("26500.00"),
    )
    older = ProjectResult(
        room=room,
        preferences=preferences,
        requirements=requirements,
        budget=budget,
        brief=make_brief(),
        concepts=ConceptCollection(
            concepts=[
                make_concept("Quiet Oak"),
                make_concept("Soft Contrast"),
                make_concept("Warm Studio"),
            ]
        ),
        selected_concept=make_concept("Quiet Oak"),
        recommendations=[
            FurnitureRecommendation(item_id="sofa_three_seat", quantity=1)
        ],
        spatial_validation=SpatialValidation(is_valid=True),
        budget_analysis=analysis,
        evaluation=make_evaluation(),
    )
    assert older.materials == []
    assert older.placement is None

    estimate = compute_budget(
        budget,
        older.recommendations,
        catalog,
    )
    path = write_report(
        older,
        catalog=catalog,
        budget=estimate,
        path=tmp_path / "legacy.pdf",
        generated_at=GENERATED_AT,
    )
    text = pdf_text(path)
    assert "Layout not recorded" in text
    assert "No materials were recommended for this concept." in text
