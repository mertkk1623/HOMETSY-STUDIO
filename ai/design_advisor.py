"""Design Advisor: recommend catalog furniture and materials for one concept.

The third AI operation. It answers in the shape of
:class:`models.schemas.DesignRecommendation`: catalog references plus material
and colour direction.

The division of labour is the whole point of this module.

The model may choose *which* catalog items suit the concept and explain why.
It may not state a price, a dimension or a placement, and it may not invent an
identifier. Every identifier it returns is checked against
``data/furniture_catalog.json`` by :func:`verify_catalog_references`, which is
plain Python and runs afterwards.

A bad reference is reported, never repaired. Substituting a similar item would
mean the user's basket silently differs from what the model chose, and a
fabricated total is worse than an honest error.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

from ai.client import DEFAULT_TIMEOUT_SECONDS
from ai.config import AIConfig
from ai.prompt import (
    Completer,
    PromptSpec,
    catalogue_entry,
    items_for_room,
    json_block,
    room_facts,
    run_structured_request,
    system_prompt,
)
from models.schemas import (
    BudgetAnalysis,
    BudgetInput,
    DesignBrief,
    DesignConcept,
    DesignPreferences,
    DesignRecommendation,
    FurnitureItem,
    RoomInput,
)
from core.budget_engine import BudgetResult, compute_budget
from core.validation import validate_catalog_references

#: Application token budget for this operation.
#:
#: Raised from 4000 after live validation in Phase 5 Step 3: this model spends
#: part of the output budget on reasoning tokens before it writes the JSON, and a
#: real answer needed 3007 completion tokens (2100 of them reasoning) for a
#: 3620-character payload. 4000 left too little room for the JSON and the
#: provider returned ``finish_reason=length``. The cap is output-only; the prompt
#: is not charged against it.
MAX_TOKENS = 8000

_ROLE = (
    "You are the furniture and materials advisor for an interior design "
    "application. Given one selected concept, the room and a fixed local "
    "catalog, you choose the items that will furnish the room and describe the "
    "materials and colours.\n"
    "You are choosing from a list. You are not measuring the room, pricing the "
    "basket, or deciding where each piece is placed. You may say which wall a "
    "piece belongs against when the concept calls for it, and the application "
    "works out the exact position."
)

_CONTRACT = """REQUIRED OUTPUT SHAPE (one JSON object, no extra keys)
{
  "furniture": [
    {
      "item_id": "must match an item_id from the CATALOG list exactly",
      "quantity": 1,
      "rotation_degrees": 0,
      "rationale": "one or two sentences, at most 500 characters",
      "preferred_wall": "north, south, east, west, or null",
      "wall_priority": "preferred or required, default preferred"
    }
  ],
  "materials": [
    {
      "name": "material or finish, 1-80 characters",
      "category": "short category, 1-60 characters",
      "color_direction": "one sentence, at most 200 characters",
      "rationale": "one or two sentences, at most 500 characters",
      "quantity_note": "scope such as full floor or feature wall, max 200 chars"
    }
  ],
  "color_direction": "one paragraph, at most 500 characters",
  "design_rationale": "2-4 sentences explaining the choices, at most 2000 characters"
}

FIELD RULES
- furniture: at least 1 item, at most 20. Each item_id must appear verbatim in
  the CATALOG list provided. Never invent an identifier, and never translate or
  re-case one.
- quantity: whole number from 1 to 20.
- rotation_degrees: one of 0, 90, 180, 270.
- materials: at most 12. Describe materials, not products from the catalog.
- preferred_wall: one of north, south, east, west, or null. Use null when the
  concept does not call for a particular wall.
- Every field shown above is required unless it has a default in the shape.

PREFERRED WALL RULES
- At most THREE furniture items may carry a preferred_wall. This is a limit on
  how specific a concept's layout language may be, not a style preference.
- Only give a preferred_wall when the SELECTED CONCEPT names or clearly implies
  that wall for that piece, for example "the bed pushed toward the west wall"
  or "a desk at the east window".
- Never give a preferred_wall to an item the concept treats as flexible.
- wall_priority: use "required" only when the concept insists on the wall and
  the piece would be pointless elsewhere. Otherwise use "preferred", which
  lets the application fall back to another wall rather than lose the item.
- Name the wall, never the position. "west" is allowed; a coordinate, an
  offset, a distance along the wall, or "the north-west corner" is not.

WHAT YOU MUST NOT DO
- Do not state prices, costs, totals or currency amounts. Pricing is done by the
  application from the catalog.
- Do not state widths, depths or any other dimension. Dimensions come from the
  catalog.
- Do not assign coordinates or exact positions. You may name a wall, and that
  is all: the application decides where along the wall a piece sits, which way
  it faces, and whether your wall is achievable at all.
- Do not choose catalog items that do not support this room type."""


def build_prompt(
    room: RoomInput,
    preferences: DesignPreferences,
    budget: BudgetInput,
    brief: DesignBrief,
    concept: DesignConcept,
    catalog: Sequence[FurnitureItem],
) -> PromptSpec:
    """Assemble the prompt, including the catalog the model may choose from.

    Only entries that support this room type are listed, so an unusable
    identifier cannot be picked in the first place. Validation still runs
    afterwards: a model can ignore an instruction.
    """

    usable = items_for_room(catalog, room.room_type)
    context = (
        "SELECTED CONCEPT\n"
        f"{json_block(concept)}\n\n"
        "STRUCTURED DESIGN BRIEF\n"
        f"{json_block(brief)}\n\n"
        "ROOM\n"
        f"{json_block(room)}\n\n"
        "CALCULATED ROOM FACTS (authoritative, do not recompute)\n"
        f"{json_block(room_facts(room))}\n\n"
        "DESIGN PREFERENCES\n"
        f"{json_block(preferences)}\n\n"
        f"BUDGET (authoritative, do not recompute)\n{json_block(budget)}\n\n"
        f"CATALOG ({len(usable)} items available for this room type; the only "
        "identifiers you may use)\n"
        f"{json_block([catalogue_entry(item) for item in usable])}"
    )
    return PromptSpec(
        system=system_prompt(_ROLE),
        context=context,
        contract=_CONTRACT,
    )


@dataclass(frozen=True)
class CatalogCheck:
    """The outcome of checking a recommendation against the local catalog.

    ``is_valid`` is the single thing an interface should branch on. ``findings``
    carries the detail, reusing the Phase 3 validation vocabulary so the same
    message reaches the user however the problem was discovered.
    """

    findings: tuple[Any, ...] = ()

    @property
    def is_valid(self) -> bool:
        return not any(finding.is_error for finding in self.findings)

    @property
    def errors(self) -> tuple[Any, ...]:
        return tuple(f for f in self.findings if f.is_error)

    @property
    def messages(self) -> list[str]:
        return [finding.message for finding in self.findings]


def verify_catalog_references(
    room: RoomInput,
    recommendation: DesignRecommendation,
    catalog: Sequence[FurnitureItem],
) -> CatalogCheck:
    """Check every identifier against the catalog and the room type.

    Uses :func:`core.validation.validate_catalog_references`, the Phase 3 rule,
    rather than a second implementation. Unknown identifiers and unsupported
    room types therefore produce the same codes and wording everywhere.
    """

    findings = validate_catalog_references(
        room, recommendation.furniture, catalog
    )
    return CatalogCheck(findings=tuple(findings))


@dataclass(frozen=True)
class AdvisorResult:
    """A recommendation together with Python's view of it.

    The recommendation is returned even when the references are bad, because the
    interface must be able to show *what* the model proposed before saying it
    cannot be used. Nothing here is presented as a valid basket: the catalog
    check and the budget's own trust flag are separate and explicit.
    """

    recommendation: DesignRecommendation
    catalog_check: CatalogCheck
    budget: BudgetResult

    @property
    def is_usable(self) -> bool:
        """True only when every reference resolved and the total is complete.

        A total computed while an item failed to price is a partial sum; showing
        it as the project cost would misstate the basket, so it is not usable.
        """

        return self.catalog_check.is_valid and self.budget.is_trustworthy

    @property
    def priced(self) -> BudgetAnalysis:
        """The budget figures, valid only when :attr:`is_usable` is true."""

        return self.budget.analysis

    @property
    def furniture_subtotal(self) -> Decimal:
        return self.budget.analysis.furniture_subtotal


def recommend_furniture(
    config: AIConfig,
    room: RoomInput,
    preferences: DesignPreferences,
    budget: BudgetInput,
    brief: DesignBrief,
    concept: DesignConcept,
    catalog: Sequence[FurnitureItem],
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    completer: Completer | None = None,
) -> AdvisorResult:
    """Recommend furniture and materials, then price them in Python.

    Raises
    ------
    ai.client.AIError
        Transport or response failure.
    ai.parsing.AIStructuredOutputError
        The answer was unusable and no correction was possible.
    ai.parsing.AICorrectionFailedError
        The single correction attempt also failed.

    A catalog problem does **not** raise: it is reported on the result so the
    caller can show the proposal and its defect together.
    """

    spec = build_prompt(room, preferences, budget, brief, concept, catalog)
    recommendation = run_structured_request(
        config,
        spec,
        DesignRecommendation,
        max_tokens=MAX_TOKENS,
        timeout=timeout,
        completer=completer,
    )

    check = verify_catalog_references(room, recommendation, catalog)
    budget_result = compute_budget(budget, recommendation.furniture, catalog)

    return AdvisorResult(
        recommendation=recommendation,
        catalog_check=check,
        budget=budget_result,
    )


__all__ = [
    "MAX_TOKENS",
    "AdvisorResult",
    "CatalogCheck",
    "build_prompt",
    "recommend_furniture",
    "verify_catalog_references",
]
