"""Tests for the local data and visual asset library (Phase 2).

These tests validate structure, not design taste: JSON parses, identifiers are
unique, catalog records satisfy the Pydantic model, referenced image files exist
and every approved reference category is either backed by an asset or explicitly
recorded as missing.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from models.schemas import (
    DesignStyle,
    FurnitureItem,
    PaletteDirection,
    RoomType,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
CATALOG_PATH = DATA_DIR / "furniture_catalog.json"
REFERENCES_PATH = DATA_DIR / "design_references.json"


def _load(path: Path) -> dict:
    assert path.exists(), f"Missing data file: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def catalog() -> dict:
    return _load(CATALOG_PATH)


@pytest.fixture(scope="module")
def references() -> dict:
    return _load(REFERENCES_PATH)


# --------------------------------------------------------------------------- #
# Furniture catalog
# --------------------------------------------------------------------------- #


def test_catalog_parses_and_has_items(catalog: dict) -> None:
    assert catalog["catalog_version"] == "1.0"
    assert catalog["currency"] == "TRY"
    assert len(catalog["items"]) >= 15


def test_catalog_declares_illustrative_costs(catalog: dict) -> None:
    disclaimer = catalog["cost_disclaimer"].lower()
    assert "indicative" in disclaimer
    assert "not verified" in disclaimer


def test_every_catalog_item_matches_the_model(catalog: dict) -> None:
    for record in catalog["items"]:
        item = FurnitureItem(**record)
        assert item.width_cm > 0
        assert item.depth_cm > 0


def test_catalog_item_ids_are_unique(catalog: dict) -> None:
    ids = [record["item_id"] for record in catalog["items"]]
    assert len(ids) == len(set(ids))


def test_catalog_uses_only_supported_room_types(catalog: dict) -> None:
    supported = {room.value for room in RoomType}
    for record in catalog["items"]:
        assert set(record["supported_room_types"]) <= supported


def test_every_room_type_has_catalog_coverage(catalog: dict) -> None:
    covered = {
        room_type
        for record in catalog["items"]
        for room_type in record["supported_room_types"]
    }
    assert covered == {room.value for room in RoomType}


def test_catalog_dimensions_are_plausible(catalog: dict) -> None:
    for record in catalog["items"]:
        # A single furniture footprint must fit a supported room's minimum size.
        assert 20 <= record["width_cm"] <= 300
        assert 20 <= record["depth_cm"] <= 300


def test_catalog_costs_are_positive_integers(catalog: dict) -> None:
    for record in catalog["items"]:
        assert isinstance(record["indicative_unit_cost"], int)
        assert record["indicative_unit_cost"] > 0


# --------------------------------------------------------------------------- #
# Design references
# --------------------------------------------------------------------------- #


def test_references_parse_with_expected_sections(references: dict) -> None:
    assert references["references_version"] == "1.0"
    assert len(references["styles"]) == 6
    assert len(references["palettes"]) == 4


def test_style_ids_cover_every_approved_style(references: dict) -> None:
    mapped = {entry["design_style"] for entry in references["styles"]}
    assert mapped == {style.value for style in DesignStyle}


def test_palette_ids_cover_every_approved_direction(references: dict) -> None:
    mapped = {entry["palette_direction"] for entry in references["palettes"]}
    assert mapped == {direction.value for direction in PaletteDirection}


def test_reference_ids_are_unique(references: dict) -> None:
    style_ids = [entry["id"] for entry in references["styles"]]
    palette_ids = [entry["id"] for entry in references["palettes"]]
    assert len(style_ids) == len(set(style_ids))
    assert len(palette_ids) == len(set(palette_ids))


def test_approved_references_point_to_existing_local_images(references: dict) -> None:
    for entry in references["styles"] + references["palettes"]:
        if entry["status"] == "missing":
            assert entry["image"] is None
            continue
        assert entry["image"] is not None
        image_path = PROJECT_ROOT / entry["image"]
        assert image_path.exists(), f"Missing image: {entry['image']}"
        assert image_path.stat().st_size > 0
        assert entry["image"].startswith("assets/images/")


def test_every_style_has_a_displayable_image(references: dict) -> None:
    """Phase 2 correction: all six approved styles must now be displayable."""

    for entry in references["styles"]:
        assert entry["status"] in {"approved", "available"}, entry["id"]
        assert entry["image"] is not None, entry["id"]
        assert (PROJECT_ROOT / entry["image"]).exists(), entry["image"]


def test_every_palette_has_a_displayable_image(references: dict) -> None:
    for entry in references["palettes"]:
        assert entry["status"] in {"approved", "available"}, entry["id"]
        assert entry["image"] is not None, entry["id"]
        assert (PROJECT_ROOT / entry["image"]).exists(), entry["image"]


def test_no_reference_remains_missing_or_provisional(references: dict) -> None:
    statuses = {e["status"] for e in references["styles"] + references["palettes"]}
    assert "missing" not in statuses
    assert "provisional" not in statuses


def test_no_reference_depends_on_a_remote_url(references: dict) -> None:
    for entry in references["styles"] + references["palettes"]:
        for value in (entry.get("image"), entry.get("source_image")):
            if value is not None:
                assert not value.startswith(("http://", "https://"))


def test_source_images_are_preserved(references: dict) -> None:
    for entry in references["styles"] + references["palettes"]:
        source = entry.get("source_image")
        if source is None:
            continue
        assert (PROJECT_ROOT / source).exists(), f"Missing source: {source}"


def test_corrected_styles_point_to_the_replacement_pack(references: dict) -> None:
    by_style = {entry["design_style"]: entry for entry in references["styles"]}
    for style, filename in (
        ("Warm Minimalism", "warm_minimalism"),
        ("Japandi", "japandi"),
    ):
        entry = by_style[style]
        assert entry["status"] == "available"
        assert entry["image"] == f"assets/images/styles/{filename}.jpg"
        assert entry["source_image"] == (
            f"assets/source_pack/Replacements/{filename}.jpg"
        )


def test_natural_materials_is_available_and_remapped(references: dict) -> None:
    by_palette = {entry["palette_direction"]: entry for entry in references["palettes"]}
    entry = by_palette["Natural Materials"]
    assert entry["status"] == "available"
    assert entry["image"] == "assets/images/palettes/natural_materials.jpg"
    assert entry["source_image"] == (
        "assets/source_pack/Replacements/natural_materials.jpg"
    )
    # The superseded source must no longer be referenced by any category.
    assert "calm_blue" not in entry["image"]
    assert "calm_blue" not in entry["source_image"]


def test_calm_blue_is_retained_but_unmapped(references: dict) -> None:
    mapped_sources = {
        entry.get("source_image")
        for entry in references["styles"] + references["palettes"]
    }
    assert "assets/source_pack/palettes/calm_blue.jpg" not in mapped_sources
    unmapped = {e["source_image"] for e in references["unmapped_source_assets"]}
    assert "assets/source_pack/palettes/calm_blue.jpg" in unmapped
    # The file itself must still exist in the preserved source pack.
    assert (PROJECT_ROOT / "assets/source_pack/palettes/calm_blue.jpg").exists()


def test_overridden_application_image_is_no_longer_the_calm_blue_copy(
    references: dict,
) -> None:
    """natural_materials.jpg in the app tree must now hold the replacement board."""

    from PIL import Image

    app_image = PROJECT_ROOT / "assets/images/palettes/natural_materials.jpg"
    original = PROJECT_ROOT / "assets/source_pack/palettes/calm_blue.jpg"
    with Image.open(app_image) as new_board, Image.open(original) as old_board:
        assert new_board.size == (378, 323)
        assert new_board.size != old_board.size


def test_reference_metadata_states_ai_does_not_see_images(references: dict) -> None:
    note = references["ai_usage_note"].lower()
    assert "never" in note
    assert "image" in note


def test_excluded_source_assets_are_documented(references: dict) -> None:
    excluded = {Path(entry["source_image"]).name for entry in references["excluded_source_assets"]}
    assert excluded == {"modern.jpg", "minimalist.jpg"}


def test_excluded_sources_are_still_present_in_the_pack(references: dict) -> None:
    """Excluded never means deleted."""

    for entry in references["excluded_source_assets"]:
        assert (PROJECT_ROOT / entry["source_image"]).exists()


def test_replacement_record_matches_the_references(references: dict) -> None:
    record = _load(DATA_DIR / "asset_replacements.json")
    assert len(record["resolved"]) == 3

    resolved = {entry["category"]: entry for entry in record["resolved"]}
    by_style = {e["design_style"]: e for e in references["styles"]}
    by_palette = {e["palette_direction"]: e for e in references["palettes"]}

    for category, entry in resolved.items():
        assert entry["new_status"] == "available"
        assert (PROJECT_ROOT / entry["source_image"]).exists()
        assert (PROJECT_ROOT / entry["application_image"]).exists()
        live = by_style.get(category) or by_palette[category]
        assert live["image"] == entry["application_image"]
        assert live["source_image"] == entry["source_image"]


def test_replacement_record_preserves_retained_files() -> None:
    record = _load(DATA_DIR / "asset_replacements.json")
    retained = record["retained_unmapped"] + record["retained_excluded"]
    assert len(retained) == 3
    for entry in retained:
        assert (PROJECT_ROOT / entry["source_image"]).exists(), entry["source_image"]


def test_replacement_assets_are_not_reused_between_categories(references: dict) -> None:
    images = [e["image"] for e in references["styles"] + references["palettes"]]
    assert len(images) == len(set(images))
    sources = [e["source_image"] for e in references["styles"] + references["palettes"]]
    assert len(sources) == len(set(sources))


def _resolves_case_exactly(relative_path: str) -> tuple[bool, str]:
    """Walk a relative path matching on-disk case, emulating a Linux filesystem.

    Windows resolves ``Replacements`` and ``replacements`` identically, so a
    case mismatch would pass locally and break on a case-sensitive host.

    Returns ``(resolved, failing_component)``.
    """

    current = PROJECT_ROOT
    for part in Path(relative_path).parts:
        try:
            names = {entry.name for entry in current.iterdir()}
        except (NotADirectoryError, FileNotFoundError):
            return False, part
        if part not in names:
            return False, part
        current = current / part
    return True, ""


def _collect_reference_paths(references: dict) -> list[tuple[str, str]]:
    """Return every ``(label, path)`` pair the metadata declares.

    Derived from the loaded JSON rather than a hand-maintained list, so a new
    path field cannot be added without being validated.
    """

    collected: list[tuple[str, str]] = []

    for key, value in references["source_pack"].items():
        # Only path-valued keys. `note` is prose that happens to contain "/".
        if isinstance(value, str) and value.startswith(("assets/", "data/")):
            collected.append((f"source_pack.{key}", value))

    for section in ("styles", "palettes"):
        for entry in references[section]:
            for key, value in entry.items():
                if isinstance(value, str) and value.startswith(("assets/", "data/")):
                    collected.append((f"{section}[{entry['id']}].{key}", value))

    for section in ("excluded_source_assets", "unmapped_source_assets"):
        for index, entry in enumerate(references.get(section, [])):
            collected.append((f"{section}[{index}]", entry["source_image"]))

    return collected


def test_reference_path_inventory_is_complete(references: dict) -> None:
    """Guards the audit numbers quoted in the Phase 2 report."""

    pairs = _collect_reference_paths(references)
    labels = [label for label, _ in pairs]
    assert len(labels) == len(set(labels)), "duplicate reference labels"

    expected = {
        "source_pack.manifest",
        "source_pack.replacements_manifest",
        "source_pack.styles_dir",
        "source_pack.palettes_dir",
        "source_pack.replacements_dir",
    }
    assert expected <= set(labels)
    # 5 source_pack + 6 styles x 2 + 4 palettes x 2 + 2 excluded + 1 unmapped
    assert len(pairs) == 5 + 12 + 8 + 2 + 1 == 28


def test_all_referenced_paths_resolve_with_exact_case(references: dict) -> None:
    pairs = _collect_reference_paths(references)
    assert pairs, "no path references were collected"

    failures: list[str] = []
    for label, relative_path in pairs:
        resolved, failing = _resolves_case_exactly(relative_path)
        if not resolved:
            failures.append(f"{label} -> {relative_path} (missing '{failing}')")

    assert not failures, "Case-exact resolution failed:\n" + "\n".join(failures)


def test_every_declared_reference_path_exists_on_disk(references: dict) -> None:
    """Case-exact success must also mean the target is a file or directory."""

    for label, relative_path in _collect_reference_paths(references):
        target = PROJECT_ROOT / relative_path
        assert target.exists(), f"{label} does not exist: {relative_path}"
        assert target.is_file() or target.is_dir(), f"{label} is neither: {relative_path}"


def test_reference_path_inventory_has_no_null_entries(references: dict) -> None:
    """After the correction pack no category may declare a null image."""

    for section in ("styles", "palettes"):
        for entry in references[section]:
            assert entry["image"] is not None, entry["id"]
            assert entry["source_image"] is not None, entry["id"]



def test_replacement_manifest_declares_all_three_assets() -> None:
    replacements_dir = PROJECT_ROOT / "assets/source_pack/Replacements"
    manifest = json.loads((replacements_dir / "asset_manifest.json").read_text("utf-8"))
    declared = {entry["file"] for entry in manifest["assets"]}
    assert declared == {"warm_minimalism.jpg", "japandi.jpg", "natural_materials.jpg"}
    for filename in declared:
        assert (replacements_dir / filename).exists()


# --------------------------------------------------------------------------- #
# Repository hygiene
# --------------------------------------------------------------------------- #


def test_no_reference_images_live_outside_the_asset_tree(references: dict) -> None:
    for entry in references["styles"] + references["palettes"]:
        if entry["image"]:
            assert Path(entry["image"]).parts[0] == "assets"
