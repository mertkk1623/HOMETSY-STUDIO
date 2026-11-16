"""The deterministic half of the Design Plan step.

Everything here is plain Python: no Streamlit, no AI, no session state. The plan
screen calls :func:`analyse_layout` once, after the advisor has produced a
basket, and gets back the three things it has to show:

* the recommendations with the engine's coordinates written in, which is what
  the workflow stores;
* the :class:`~models.schemas.PlacementOutcome` the drawing and the score come
  from;
* the :class:`~models.schemas.SpatialValidation` produced by the spatial engine.

Why a separate module
---------------------
The screen must never compute geometry: ``AGENTS.md`` §7 puts dimensions,
boundaries, overlaps and the 2D plan on Python's side, and the placement engine
already owns all of it. This module is only the seam — it calls
``place_furniture``, then ``apply_placements``, then hands the engine's own
validation through unchanged. There is no second validator, no rounding and no
"close enough" check anywhere in it.

The equally important rule is that it never invents the missing half of a
result. A failed placement yields no footprints and no score; the caller stores
the failure with its unplaced items and its notes so the screen can explain it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from core.placement_engine import apply_placements, place_furniture
from core.spatial_engine import DEFAULT_DOOR_CLEARANCE_CM, DEFAULT_WINDOW_CLEARANCE_CM
from models.schemas import (
    FurnitureItem,
    FurnitureRecommendation,
    PlacementOutcome,
    RoomInput,
    SpatialValidation,
)


@dataclass(frozen=True)
class LayoutAnalysis:
    """The storable result of one placement pass.

    ``placements`` is the tuple to record through ``WorkflowState``; every other
    field is derived from it and from the engine, never recomputed here.
    """

    placements: tuple[FurnitureRecommendation, ...]
    outcome: PlacementOutcome
    validation: SpatialValidation

    @property
    def is_complete(self) -> bool:
        return self.outcome.is_complete

    @property
    def is_partial(self) -> bool:
        return self.outcome.is_partial

    @property
    def is_failed(self) -> bool:
        return self.outcome.is_failed


def analyse_layout(
    room: RoomInput,
    recommendations: Sequence[FurnitureRecommendation],
    catalog: Sequence[FurnitureItem],
    *,
    door_clearance_cm: float = DEFAULT_DOOR_CLEARANCE_CM,
    window_clearance_cm: float = DEFAULT_WINDOW_CLEARANCE_CM,
) -> LayoutAnalysis:
    """Place the basket, validate the chosen layout, and return both.

    The validation is the engine's own ``PlacementResult.validation``. When the
    engine rejected every candidate it still returns a ``SpatialValidation``
    describing why for the cases it could check; when it produced no report at
    all — nothing requested, nothing placeable — an invalid verdict is
    synthesised from the engine's notes, because "we could not check this" must
    never read as "this is fine".
    """

    result = place_furniture(
        room,
        tuple(recommendations),
        tuple(catalog),
        door_clearance_cm=door_clearance_cm,
        window_clearance_cm=window_clearance_cm,
    )
    placements = apply_placements(tuple(recommendations), result)
    outcome = result.to_outcome()
    validation = result.validation

    if validation is None:
        # No candidate survived, so there was nothing for the spatial engine to
        # validate. That is a failure, not an absence of problems.
        validation = SpatialValidation(
            is_valid=False,
            boundary_violations=list(outcome.notes),
            overlaps=[],
            warnings=[],
        )

    return LayoutAnalysis(
        placements=placements,
        outcome=outcome,
        validation=validation,
    )


__all__ = ["LayoutAnalysis", "analyse_layout"]
