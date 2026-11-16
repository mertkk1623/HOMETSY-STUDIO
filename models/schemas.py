"""Pydantic data models for Hometsy — Room Intelligence Studio.

Scope (Phase 1): the foundational, validated data structures shared by the
workflow, AI and calculation layers. No geometry, budget or reporting logic
lives here — only shape and constraints.

Conventions that follow the approved documentation:

* All spatial values are centimeters internally; area is exposed in m².
* The room origin is the bottom-left corner (south-west).
* Walls are named north, south, east and west.
* Budgets are explicit about their currency and use ``Decimal`` so that no
  binary floating-point rounding enters financial data.
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# --------------------------------------------------------------------------- #
# Domain vocabulary
# --------------------------------------------------------------------------- #

#: Rectangular rooms only (V1). Values are the user-facing labels.
MIN_ROOM_DIMENSION_CM: float = 100.0
MAX_ROOM_DIMENSION_CM: float = 2000.0
MIN_CEILING_HEIGHT_CM: float = 200.0
MAX_CEILING_HEIGHT_CM: float = 500.0
MIN_OPENING_WIDTH_CM: float = 40.0

#: Exactly three concepts are required by the V1 workflow.
REQUIRED_CONCEPT_COUNT: int = 3


class RoomType(str, Enum):
    """The four residential room types supported by V1."""

    LIVING_ROOM = "Living Room"
    BEDROOM = "Bedroom"
    HOME_OFFICE = "Home Office"
    DINING_ROOM = "Dining Room"


class Wall(str, Enum):
    """Room walls. The origin is the south-west corner, so ``south`` grows +x."""

    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"


class DesignStyle(str, Enum):
    """The six interior design styles supported by V1."""

    WARM_MINIMALISM = "Warm Minimalism"
    SCANDINAVIAN = "Scandinavian"
    JAPANDI = "Japandi"
    CONTEMPORARY = "Contemporary"
    INDUSTRIAL = "Industrial"
    BOHEMIAN = "Bohemian"


class PaletteDirection(str, Enum):
    """The four palette and material directions supported by V1."""

    WARM_NEUTRAL = "Warm Neutral"
    EARTHY = "Earthy"
    COOL_MODERN = "Cool Modern"
    NATURAL_MATERIALS = "Natural Materials"


#: Only TRY is approved for V1, but the currency is explicit in the data model.
Currency = Literal["TRY"]

#: Furniture may only be placed axis-aligned in 90° steps (V1).
RotationDegrees = Literal[0, 90, 180, 270]


class PlacementStatus(str, Enum):
    """How much of a furniture request the placement engine could satisfy.

    Defined here rather than in :mod:`core.placement_engine` because the answer
    is stored in the workflow state and shown to the user, exactly like
    ``Wall`` or ``RoomType``. ``core`` re-exports it, so the engine keeps a
    single vocabulary.
    """

    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"


#: Non-negative money amount with at most two decimal places.
Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]

#: Short narrative text supplied by the user or produced by the AI.
ShortText = Annotated[str, Field(min_length=1, max_length=200)]
LongText = Annotated[str, Field(min_length=1, max_length=2000)]


class _BaseModel(BaseModel):
    """Shared configuration: reject unknown fields and trim whitespace."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# --------------------------------------------------------------------------- #
# User input models
# --------------------------------------------------------------------------- #


class OpeningInput(_BaseModel):
    """A door or window on one wall.

    ``offset_cm`` is measured along the wall from its origin, using the
    bottom-left (south-west) corner convention:

    * south / north walls are measured from the west end (+x),
    * west / east walls are measured from the south end (+y).

    The opening must fit entirely on its wall; that check lives in
    :class:`RoomInput`, which knows the wall spans.
    """

    wall: Wall
    offset_cm: Annotated[float, Field(ge=0)]
    width_cm: Annotated[float, Field(ge=MIN_OPENING_WIDTH_CM, le=MAX_ROOM_DIMENSION_CM)]


class RoomInput(_BaseModel):
    """A rectangular room with exactly one door and one window."""

    room_type: RoomType
    name: Annotated[str, Field(min_length=1, max_length=80)]
    width_cm: Annotated[
        float, Field(ge=MIN_ROOM_DIMENSION_CM, le=MAX_ROOM_DIMENSION_CM)
    ]
    length_cm: Annotated[
        float, Field(ge=MIN_ROOM_DIMENSION_CM, le=MAX_ROOM_DIMENSION_CM)
    ]
    ceiling_height_cm: Annotated[
        float, Field(ge=MIN_CEILING_HEIGHT_CM, le=MAX_CEILING_HEIGHT_CM)
    ] = 270.0
    door: OpeningInput
    window: OpeningInput

    @property
    def area_sqm(self) -> float:
        """Floor area in square meters (user-facing unit)."""

        return (self.width_cm * self.length_cm) / 10_000.0

    def wall_span_cm(self, wall: Wall) -> float:
        """Length of ``wall`` in centimeters."""

        if wall in (Wall.NORTH, Wall.SOUTH):
            return self.width_cm
        return self.length_cm

    @model_validator(mode="after")
    def _openings_fit_on_their_walls(self) -> RoomInput:
        for label, opening in (("door", self.door), ("window", self.window)):
            span = self.wall_span_cm(opening.wall)
            if opening.offset_cm + opening.width_cm > span:
                raise ValueError(
                    f"The {label} does not fit on the {opening.wall.value} wall: "
                    f"offset {opening.offset_cm:g} cm + width "
                    f"{opening.width_cm:g} cm exceeds the {span:g} cm wall span."
                )
        return self


class DesignPreferences(_BaseModel):
    """Selected style, one palette, and optional separate material preferences."""

    style: DesignStyle
    palette: PaletteDirection
    material_preferences: Annotated[list[str], Field(max_length=10)] = Field(
        default_factory=list
    )


class UserRequirements(_BaseModel):
    """Functional requirements and free-form notes."""

    functional_requirements: Annotated[list[str], Field(max_length=20)] = Field(
        default_factory=list
    )
    notes: Annotated[str, Field(max_length=2000)] = ""


class BudgetInput(_BaseModel):
    """The user's total design budget, with an explicit currency."""

    total_budget: Money
    currency: Currency = "TRY"


# --------------------------------------------------------------------------- #
# AI output models
# --------------------------------------------------------------------------- #


class DesignBrief(_BaseModel):
    """Structured brief produced by the Brief Analyzer."""

    summary: LongText
    functional_priorities: Annotated[list[ShortText], Field(max_length=10)] = Field(
        default_factory=list
    )
    constraints: Annotated[list[ShortText], Field(max_length=10)] = Field(
        default_factory=list
    )
    ambiguities: Annotated[list[ShortText], Field(max_length=10)] = Field(
        default_factory=list
    )
    warnings: Annotated[list[ShortText], Field(max_length=10)] = Field(
        default_factory=list
    )


class DesignConcept(_BaseModel):
    """One generated design concept."""

    name: Annotated[str, Field(min_length=1, max_length=80)]
    description: LongText
    design_direction: ShortText
    color_and_material_direction: ShortText
    furniture_approach: ShortText
    functional_rationale: LongText
    budget_suitability: ShortText


class ConceptCollection(_BaseModel):
    """Exactly three distinct concepts, as required by the V1 workflow."""

    concepts: Annotated[
        list[DesignConcept], Field(min_length=REQUIRED_CONCEPT_COUNT, max_length=REQUIRED_CONCEPT_COUNT)
    ]

    @model_validator(mode="after")
    def _concepts_are_distinct(self) -> ConceptCollection:
        names = [concept.name.casefold() for concept in self.concepts]
        if len(set(names)) != len(names):
            raise ValueError("Each concept must have a distinct name.")
        return self


# --------------------------------------------------------------------------- #
# Catalog and recommendation models
# --------------------------------------------------------------------------- #


class FurnitureItem(_BaseModel):
    """One entry of the local furniture catalog.

    ``drawing_shape`` is the simple 2D representation key used by the plan
    renderer; it is intentionally a plain string rather than a geometry type.
    """

    item_id: Annotated[str, Field(min_length=1, max_length=60)]
    name: Annotated[str, Field(min_length=1, max_length=120)]
    category: Annotated[str, Field(min_length=1, max_length=60)]
    width_cm: Annotated[float, Field(gt=0, le=MAX_ROOM_DIMENSION_CM)]
    depth_cm: Annotated[float, Field(gt=0, le=MAX_ROOM_DIMENSION_CM)]
    indicative_unit_cost: Money
    supported_room_types: Annotated[list[RoomType], Field(min_length=1)]
    drawing_shape: Annotated[str, Field(min_length=1, max_length=40)] = "rectangle"


class FurniturePosition(_BaseModel):
    """One placed copy of a recommended item, in centimeters.

    Written only by ``core.placement_engine.apply_placements`` from a footprint
    the spatial engine accepted. It exists because a recommendation can ask for
    several copies of one catalog item and each copy stands somewhere else; a
    single coordinate pair would collapse them.
    """

    position_x_cm: Annotated[float, Field(ge=0)]
    position_y_cm: Annotated[float, Field(ge=0)]
    rotation_degrees: RotationDegrees = 0


class FurnitureRecommendation(_BaseModel):
    """A catalog item selected for the project.

    Placement is optional: the deterministic placement engine (Phase 5) assigns
    coordinates later, so ``None`` means "not placed yet". The AI never supplies
    them.

    ``positions`` holds one entry per copy the engine actually placed, so
    ``quantity > 1`` survives write-back. When it is non-empty it is
    authoritative and ``position_x_cm``/``position_y_cm`` mirror its first
    entry; when it is empty only the single pair is meaningful. A partial layout
    has fewer positions than ``quantity``, and the copies that are missing are
    reported rather than invented.
    """

    item_id: Annotated[str, Field(min_length=1, max_length=60)]
    quantity: Annotated[int, Field(ge=1, le=20)] = 1
    rotation_degrees: RotationDegrees = 0
    position_x_cm: Annotated[float, Field(ge=0)] | None = None
    position_y_cm: Annotated[float, Field(ge=0)] | None = None
    positions: Annotated[list[FurniturePosition], Field(max_length=20)] = Field(
        default_factory=list
    )
    rationale: Annotated[str, Field(max_length=500)] = ""

    @model_validator(mode="after")
    def _positions_never_exceed_quantity(self) -> FurnitureRecommendation:
        if len(self.positions) > self.quantity:
            raise ValueError(
                f"'{self.item_id}' has {len(self.positions)} placed positions "
                f"but a quantity of {self.quantity}."
            )
        return self


class MaterialRecommendation(_BaseModel):
    """A material or finish suggested by the Design Advisor.

    Materials have no catalog price list in V1, so this model deliberately
    carries no cost field: an invented price would be indistinguishable from a
    real one once it reached the budget engine. ``quantity_note`` describes
    scope ("full floor", "feature wall") rather than a measured amount.
    """

    name: Annotated[str, Field(min_length=1, max_length=80)]
    category: Annotated[str, Field(min_length=1, max_length=60)]
    color_direction: Annotated[str, Field(min_length=1, max_length=200)]
    rationale: Annotated[str, Field(min_length=1, max_length=500)]
    quantity_note: Annotated[str, Field(max_length=200)] = ""


class DesignRecommendation(_BaseModel):
    """The Design Advisor's complete answer: catalog items plus materials.

    ``furniture`` holds catalog references only. Whether those identifiers
    exist and suit the room type is checked by Python afterwards, using
    :func:`core.validation.validate_catalog_references`, so this model cannot
    make an invalid reference look valid.
    """

    furniture: Annotated[list[FurnitureRecommendation], Field(min_length=1)]
    materials: Annotated[list[MaterialRecommendation], Field(max_length=12)] = Field(
        default_factory=list
    )
    color_direction: Annotated[str, Field(min_length=1, max_length=500)]
    design_rationale: Annotated[str, Field(min_length=1, max_length=2000)]


# --------------------------------------------------------------------------- #
# Result models
# --------------------------------------------------------------------------- #


class SpatialValidation(_BaseModel):
    """Deterministic geometry results: blocking issues separated from warnings."""

    is_valid: bool
    boundary_violations: Annotated[list[str], Field(default_factory=list)]
    overlaps: Annotated[list[str], Field(default_factory=list)]
    warnings: Annotated[list[str], Field(default_factory=list)]


class PlacedFootprint(_BaseModel):
    """One piece of furniture as the placement engine positioned it.

    The width and depth are the *rotated* extents, exactly as the spatial engine
    measured them, so a drawing layer never recomputes geometry.
    """

    item_id: Annotated[str, Field(min_length=1, max_length=60)]
    label: Annotated[str, Field(min_length=1, max_length=120)]
    left_cm: Annotated[float, Field(ge=0)]
    bottom_cm: Annotated[float, Field(ge=0)]
    width_cm: Annotated[float, Field(gt=0)]
    depth_cm: Annotated[float, Field(gt=0)]
    rotation_degrees: RotationDegrees = 0

    @property
    def right_cm(self) -> float:
        return self.left_cm + self.width_cm

    @property
    def top_cm(self) -> float:
        return self.bottom_cm + self.depth_cm


class UnplacedItem(_BaseModel):
    """Recommended copies the placement engine could not position, and why."""

    item_id: Annotated[str, Field(min_length=1, max_length=60)]
    label: Annotated[str, Field(min_length=1, max_length=120)]
    count: Annotated[int, Field(ge=1, le=20)]
    reason_code: Annotated[str, Field(min_length=1, max_length=60)]
    reason: Annotated[str, Field(min_length=1, max_length=500)]


class ScoreTerm(_BaseModel):
    """One weighted criterion of the layout score, kept for transparency."""

    name: Annotated[str, Field(min_length=1, max_length=60)]
    weight: Annotated[float, Field(ge=0, le=1)]
    value: Annotated[float, Field(ge=0, le=1)]


class PlacementOutcome(_BaseModel):
    """What the placement engine achieved, in a storable, drawable shape.

    Stored beside :class:`SpatialValidation` under the same workflow key, because
    a layout and its validation are one fact. ``status`` is a first-class result:
    ``PARTIAL`` is not success, and a ``FAILED`` outcome keeps the items that
    could not be placed so the screen can explain the failure instead of showing
    an empty plan.
    """

    status: PlacementStatus
    strategy: Annotated[str, Field(max_length=60)] = ""
    #: The validated layout's score. ``None`` when no layout was validated, so a
    #: rejected candidate's score can never be presented as achieved.
    score: Annotated[float, Field(ge=0, le=1)] | None = None
    placed: Annotated[list[PlacedFootprint], Field(default_factory=list)] = Field(
        default_factory=list
    )
    unplaced: Annotated[list[UnplacedItem], Field(default_factory=list)] = Field(
        default_factory=list
    )
    score_terms: Annotated[list[ScoreTerm], Field(default_factory=list)] = Field(
        default_factory=list
    )
    #: Engine notes in the order the engine produced them. Always includes the
    #: reason for a failed placement.
    notes: Annotated[list[str], Field(default_factory=list)] = Field(
        default_factory=list
    )

    @property
    def placed_count(self) -> int:
        return len(self.placed)

    @property
    def unplaced_count(self) -> int:
        return sum(item.count for item in self.unplaced)

    @property
    def requested_count(self) -> int:
        return self.placed_count + self.unplaced_count

    @property
    def is_complete(self) -> bool:
        return self.status is PlacementStatus.COMPLETE

    @property
    def is_partial(self) -> bool:
        return self.status is PlacementStatus.PARTIAL

    @property
    def is_failed(self) -> bool:
        return self.status is PlacementStatus.FAILED



class BudgetAnalysis(_BaseModel):
    """Deterministic budget results. Arithmetic is produced by Python."""

    currency: Currency = "TRY"
    furniture_subtotal: Money = Decimal("0")
    material_subtotal: Money = Decimal("0")
    other_expenses: Money = Decimal("0")
    total_estimated: Money = Decimal("0")
    remaining_budget: Decimal = Decimal("0")
    is_over_budget: bool = False


class DesignEvaluation(_BaseModel):
    """AI evaluation of the selected concept against structured data."""

    requirement_compatibility: LongText
    style_consistency: LongText
    functional_suitability: LongText
    budget_suitability: LongText
    limitations: Annotated[list[ShortText], Field(max_length=10)] = Field(
        default_factory=list
    )
    recommendations: Annotated[list[ShortText], Field(max_length=10)] = Field(
        default_factory=list
    )


class ProjectResult(_BaseModel):
    """Consolidated output consumed by the reporting layer.

    Everything a report needs to describe the project is here, so the reporting
    layer never has to reach back into the workflow state or re-run an engine.
    The four fields below Phase 6 added are additive and defaulted, because a
    ``ProjectResult`` assembled before they existed is still a valid one; the
    report distinguishes "absent" from "empty" and says so in words.

    ``placement`` carries the coordinates and sizes the placement engine
    produced. Without it a report could only describe the requested basket, and
    would have to recompute the layout to draw it — which is exactly the
    geometry ownership the reporting layer must not take.

    ``materials``, ``color_direction`` and ``design_rationale`` are the part of
    the advisor's answer that is not a furniture recommendation. They were held
    on ``WorkflowState`` only, so a report built from this model alone would have
    silently dropped them.
    """

    room: RoomInput
    preferences: DesignPreferences
    requirements: UserRequirements
    budget: BudgetInput
    brief: DesignBrief
    concepts: ConceptCollection
    selected_concept: DesignConcept
    recommendations: Annotated[list[FurnitureRecommendation], Field(min_length=1)]
    spatial_validation: SpatialValidation
    budget_analysis: BudgetAnalysis
    evaluation: DesignEvaluation
    materials: Annotated[list[MaterialRecommendation], Field(max_length=12)] = Field(
        default_factory=list
    )
    color_direction: Annotated[str, Field(max_length=500)] = ""
    design_rationale: Annotated[str, Field(max_length=2000)] = ""
    placement: PlacementOutcome | None = None

    @model_validator(mode="after")
    def _selected_concept_belongs_to_collection(self) -> ProjectResult:
        available = {concept.name.casefold() for concept in self.concepts.concepts}
        if self.selected_concept.name.casefold() not in available:
            raise ValueError(
                "The selected concept must be one of the generated concepts."
            )
        return self


__all__ = [
    "MAX_CEILING_HEIGHT_CM",
    "MAX_ROOM_DIMENSION_CM",
    "MIN_CEILING_HEIGHT_CM",
    "MIN_OPENING_WIDTH_CM",
    "MIN_ROOM_DIMENSION_CM",
    "REQUIRED_CONCEPT_COUNT",
    "BudgetAnalysis",
    "BudgetInput",
    "ConceptCollection",
    "Currency",
    "DesignBrief",
    "DesignConcept",
    "DesignEvaluation",
    "DesignPreferences",
    "DesignRecommendation",
    "DesignStyle",
    "FurnitureItem",
    "FurniturePosition",
    "FurnitureRecommendation",
    "MaterialRecommendation",
    "OpeningInput",
    "PaletteDirection",
    "PlacedFootprint",
    "PlacementOutcome",
    "PlacementStatus",
    "ProjectResult",
    "RoomInput",
    "RoomType",
    "RotationDegrees",
    "ScoreTerm",
    "SpatialValidation",
    "UnplacedItem",
    "UserRequirements",
    "Wall",
]
