"""The local design reference library.

Phase 2 shipped ``data/design_references.json`` with one licensed local image per
approved style and palette. This module reads it and hands the interface plain
records; it does not decide which styles exist — the enums do — and it refuses to
start if the two ever disagree.

The images are shown as visual references only. Nothing here is sent to the AI,
and the application must not imply that the model has looked at them
(``DESIGN_SYSTEM.md`` §9).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from models.schemas import DesignStyle, FurnitureItem, PaletteDirection, RoomType

#: Repository root, derived rather than hardcoded so the app runs from any cwd.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

REFERENCES_PATH = PROJECT_ROOT / "data" / "design_references.json"
CATALOG_PATH = PROJECT_ROOT / "data" / "furniture_catalog.json"


@dataclass(frozen=True)
class StyleReference:
    """One approved style with its local reference image."""

    style: DesignStyle
    name: str
    description: str
    image_path: Path


@dataclass(frozen=True)
class PaletteReference:
    """One approved palette with its local reference board and swatches."""

    palette: PaletteDirection
    name: str
    description: str
    image_path: Path
    swatches: tuple[str, ...]


@dataclass(frozen=True)
class ReferenceLibrary:
    """Everything the preference screen needs to draw its cards."""

    styles: tuple[StyleReference, ...]
    palettes: tuple[PaletteReference, ...]

    def image_for_style(self, style: DesignStyle) -> Path | None:
        for reference in self.styles:
            if reference.style is style:
                return reference.image_path
        return None

    def image_for_palette(self, palette: PaletteDirection) -> Path | None:
        for reference in self.palettes:
            if reference.palette is palette:
                return reference.image_path
        return None


class ReferenceError(RuntimeError):
    """The reference library on disk cannot support the approved categories."""


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_references() -> ReferenceLibrary:
    """Read and verify the reference library once per process.

    Verification is deliberately strict: a style or palette without a local
    image is a broken screen, and the application should say so at startup
    rather than render a card with a hole in it.
    """

    payload = _load_json(REFERENCES_PATH)

    styles: list[StyleReference] = []
    for entry in payload["styles"]:
        image = entry.get("image")
        if not image:
            raise ReferenceError(
                f"The style '{entry.get('design_style')}' has no reference image."
            )
        styles.append(
            StyleReference(
                style=DesignStyle(entry["design_style"]),
                name=entry.get("display_name", entry["design_style"]),
                description=entry.get("description", ""),
                image_path=PROJECT_ROOT / image,
            )
        )

    palettes: list[PaletteReference] = []
    for entry in payload["palettes"]:
        image = entry.get("image")
        if not image:
            raise ReferenceError(
                f"The palette '{entry.get('palette_direction')}' has no "
                "reference image."
            )
        palettes.append(
            PaletteReference(
                palette=PaletteDirection(entry["palette_direction"]),
                name=entry.get("display_name", entry["palette_direction"]),
                description=entry.get("description", ""),
                image_path=PROJECT_ROOT / image,
                swatches=tuple(entry.get("swatches", ())),
            )
        )

    library = ReferenceLibrary(styles=tuple(styles), palettes=tuple(palettes))
    _assert_complete(library)
    return library


def _assert_complete(library: ReferenceLibrary) -> None:
    """Every approved category must have exactly one card, with a real file."""

    style_values = [reference.style for reference in library.styles]
    if set(style_values) != set(DesignStyle) or len(style_values) != len(DesignStyle):
        raise ReferenceError(
            "The reference library does not cover the approved styles exactly once."
        )

    palette_values = [reference.palette for reference in library.palettes]
    if set(palette_values) != set(PaletteDirection) or len(palette_values) != len(
        PaletteDirection
    ):
        raise ReferenceError(
            "The reference library does not cover the approved palettes exactly "
            "once."
        )

    for path in [
        *(reference.image_path for reference in library.styles),
        *(reference.image_path for reference in library.palettes),
    ]:
        if not path.exists() or path.stat().st_size == 0:
            raise ReferenceError(f"Missing reference image: {path}")


@lru_cache(maxsize=1)
def catalog_image_free_note() -> str:
    """The catalog's own disclaimer, so the interface never invents its own."""

    payload = _load_json(CATALOG_PATH)
    return str(payload.get("cost_disclaimer", "")).strip()


@lru_cache(maxsize=1)
def load_catalog() -> tuple[FurnitureItem, ...]:
    """The local furniture catalog, validated by its own model.

    Read once per process. Every record is parsed through
    :class:`models.schemas.FurnitureItem`, so the interface can never show a
    dimension or a cost the models would reject. A parse failure is a broken
    deployment rather than a user error, so it raises instead of rendering an
    empty catalog: an empty list would silently price nothing.
    """

    payload = _load_json(CATALOG_PATH)
    return tuple(FurnitureItem(**record) for record in payload["items"])


@lru_cache(maxsize=1)
def catalog_note() -> str:
    """The catalog's dimension note, shown beside any listed drawings."""

    payload = _load_json(CATALOG_PATH)
    return str(payload.get("dimension_note", "")).strip()


def room_type_options() -> tuple[RoomType, ...]:
    """The four approved room types, in enum order."""

    return tuple(RoomType)


def style_options() -> tuple[DesignStyle, ...]:
    """The six approved styles, in enum order."""

    return tuple(DesignStyle)


def palette_options() -> tuple[PaletteDirection, ...]:
    """The four approved palette directions, in enum order."""

    return tuple(PaletteDirection)
