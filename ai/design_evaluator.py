"""Design Evaluator: judge a selected concept against the real project data.

The fourth AI operation. It receives the brief, the concept, the recommended
items and — critically — the spatial and budget results that Python already
computed, and returns a validated :class:`models.schemas.DesignEvaluation`.

The evaluator is an *interpreter*, not a calculator. It is handed finished
figures and asked what they mean for this design. It is explicitly told not to
recompute, re-round or contradict them, and the figures it was given are
rendered from the Python objects rather than retyped by hand, so the prompt
cannot drift from the calculation.

If the budget result is not trustworthy (an item failed to price), the prompt
says so instead of presenting a partial sum as the total.
"""

from __future__ import annotations

from typing import Sequence

from ai.client import DEFAULT_TIMEOUT_SECONDS
from ai.config import AIConfig
from ai.prompt import (
    Completer,
    PromptSpec,
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
    DesignEvaluation,
    DesignPreferences,
    FurnitureItem,
    FurnitureRecommendation,
    PlacementOutcome,
    PlacementStatus,
    RoomInput,
    SpatialValidation,
)

#: Application token budget for this operation.
#:
#: Raised from 3000 alongside the advisor's limit: reasoning tokens share the
#: output budget with the answer, so a cap sized for prose alone truncates the
#: JSON. See the note in :mod:`ai.design_advisor`.
MAX_TOKENS = 8000

#: Sent instead of a material figure, because the figure would be a lie of omission.
MATERIALS_NOT_PRICED_NOTE = (
    "Materials and finishes are not priced by this application: it has no "
    "material price list, so their cost is unknown rather than zero. They are "
    "excluded from every total below. Never describe them as free, as costing "
    "0.00, or as a zero subtotal."
)

_ROLE = (
    "You are a design reviewer for an interior design application. You receive "
    "one finished concept together with the geometric and budget results that "
    "the application has already calculated, and you assess how well the design "
    "answers the user's brief.\n"
    "You explain and critique. You do not measure, price, or recalculate."
)

_CONTRACT = """REQUIRED OUTPUT SHAPE (one JSON object, no extra keys)
{
  "requirement_compatibility": "1-3 sentences on how well the brief is met",
  "style_consistency": "1-3 sentences on coherence with the chosen style",
  "functional_suitability": "1-3 sentences on how the room will work in use",
  "budget_suitability": "1-3 sentences on the budget position",
  "limitations": ["up to 10 short phrases naming real weaknesses"],
  "recommendations": ["up to 10 short phrases suggesting practical improvements"]
}

FIELD RULES
- Each narrative field: 1-2000 characters, plain prose.
- limitations and recommendations: at most 10 items, each 1-200 characters.
- Use empty lists when you genuinely have nothing to add.
- limitations must follow from the data you were given, not from speculation.

CRITICAL RULES ABOUT CALCULATED DATA
- The section marked CALCULATED RESULTS was produced by the application's own
  deterministic engines. It is correct by construction.
- Never restate a calculated figure with a different value, never recalculate
  it, and never contradict it. You may quote a figure exactly as given.
- If the spatial result lists blocking problems, the design is not buildable as
  it stands: say so plainly in functional_suitability.
- If the layout is marked incomplete for any other reason, the requested items
  that were not placed are not in the room: do not call the design fully
  buildable, and name what is missing.
- If the budget result is marked incomplete, do not describe the total as final.
- Materials are not priced in this application. Never present them as free, as
  costing zero, as a "material subtotal of 0.00", or as included in a total.
  Their cost is unknown and must be described as unknown when it is mentioned.
- Do not invent measurements, prices or catalog items.
- Judge only the concept you were given. Do not propose a different concept."""


def _spatial_block(validation: SpatialValidation) -> dict[str, object]:
    """Deterministic geometry outcome, exactly as Python produced it."""

    return {
        "is_valid": validation.is_valid,
        "blocking_boundary_violations": list(validation.boundary_violations),
        "blocking_overlaps": list(validation.overlaps),
        "warnings": list(validation.warnings),
    }


def _placement_block(placement: PlacementOutcome | None) -> dict[str, object]:
    """Whether every requested item reached the room, and what did not.

    A geometrically valid layout can still be missing furniture: the spatial
    engine only checks what was placed. Without this block the evaluator was
    told the geometry was valid and nothing else, and it wrote that a
    one-of-three layout was "buildable as calculated".
    """

    if placement is None:
        return {"recorded": False}

    return {
        "status": placement.status.value,
        "every_requested_item_placed": placement.status is PlacementStatus.COMPLETE,
        "placed_count": placement.placed_count,
        "requested_count": placement.requested_count,
        "unplaced": [
            {
                "item_id": item.item_id,
                "name": item.label,
                "copies_not_placed": item.count,
                "reason": item.reason,
            }
            for item in placement.unplaced
        ],
    }


def _budget_block(analysis: BudgetAnalysis, complete: bool) -> dict[str, object]:
    """Deterministic budget outcome plus whether it may be trusted.

    ``material_subtotal`` is deliberately not sent as a number. Materials carry
    no price list in V1, so the engine's ``0.00`` means "not priced", not "free";
    handed the bare figure the model wrote "the material subtotal of 0.00 means
    those finishes are not yet represented in the costed scheme", which implies a
    priced-and-therefore-free line. The field is replaced by an explicit note and
    the arithmetic value is withheld, so there is nothing to misread.
    """

    block: dict[str, object] = {
        "currency": analysis.currency,
        "furniture_subtotal": str(analysis.furniture_subtotal),
        "other_expenses": str(analysis.other_expenses),
        "total_estimated": str(analysis.total_estimated),
        "remaining_budget": str(analysis.remaining_budget),
        "is_over_budget": analysis.is_over_budget,
        "is_complete": complete,
        "materials_pricing": MATERIALS_NOT_PRICED_NOTE,
    }
    if analysis.material_subtotal:
        # Only a non-zero subtotal is a real cost; report it when it exists.
        block["material_subtotal"] = str(analysis.material_subtotal)
    return block


def _recommendation_block(
    recommendations: Sequence[FurnitureRecommendation],
    catalog: Sequence[FurnitureItem],
) -> list[dict[str, object]]:
    """The chosen items, named from the catalog rather than from the model.

    Names and dimensions are read from the local catalog, so the evaluator
    cannot be shown a product description the model invented.
    """

    by_id = {item.item_id: item for item in catalog}
    block: list[dict[str, object]] = []
    for recommendation in recommendations:
        item = by_id.get(recommendation.item_id)
        block.append(
            {
                "item_id": recommendation.item_id,
                "name": item.name if item else "(not in catalog)",
                "category": item.category if item else "(unknown)",
                "quantity": recommendation.quantity,
                "rotation_degrees": recommendation.rotation_degrees,
            }
        )
    return block


def build_prompt(
    room: RoomInput,
    preferences: DesignPreferences,
    budget: BudgetInput,
    brief: DesignBrief,
    concept: DesignConcept,
    recommendations: Sequence[FurnitureRecommendation],
    spatial: SpatialValidation,
    analysis: BudgetAnalysis,
    catalog: Sequence[FurnitureItem],
    *,
    budget_is_complete: bool = True,
    placement: PlacementOutcome | None = None,
) -> PromptSpec:
    """Assemble the prompt around the finished deterministic results."""

    context = (
        "STRUCTURED DESIGN BRIEF\n"
        f"{json_block(brief)}\n\n"
        "SELECTED CONCEPT\n"
        f"{json_block(concept)}\n\n"
        "ROOM\n"
        f"{json_block(room)}\n\n"
        "CALCULATED ROOM FACTS (authoritative, do not recompute)\n"
        f"{json_block(room_facts(room))}\n\n"
        "DESIGN PREFERENCES\n"
        f"{json_block(preferences)}\n\n"
        "BUDGET LIMIT\n"
        f"{json_block(budget)}\n\n"
        "RECOMMENDED ITEMS (names and dimensions from the local catalog)\n"
        f"{json_block(_recommendation_block(recommendations, catalog))}\n\n"
        "CALCULATED RESULTS (authoritative, produced by Python, do not recompute)\n"
        "Spatial validation:\n"
        f"{json_block(_spatial_block(spatial))}\n"
        "Placement completeness:\n"
        f"{json_block(_placement_block(placement))}\n"
        "Budget:\n"
        f"{json_block(_budget_block(analysis, budget_is_complete))}"
    )
    return PromptSpec(
        system=system_prompt(_ROLE),
        context=context,
        contract=_CONTRACT,
    )


def evaluate_design(
    config: AIConfig,
    room: RoomInput,
    preferences: DesignPreferences,
    budget: BudgetInput,
    brief: DesignBrief,
    concept: DesignConcept,
    recommendations: Sequence[FurnitureRecommendation],
    spatial: SpatialValidation,
    analysis: BudgetAnalysis,
    catalog: Sequence[FurnitureItem],
    *,
    budget_is_complete: bool = True,
    placement: PlacementOutcome | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    completer: Completer | None = None,
) -> DesignEvaluation:
    """Assess the concept against the brief and the deterministic results.

    Parameters
    ----------
    budget_is_complete:
        False when the budget could not price every item. The evaluator is then
        told the total is partial instead of being handed a misleading number.
    placement:
        The stored layout outcome. Supplied so the evaluator knows whether every
        requested item reached the room; a valid geometry with unplaced items is
        not a complete design.

    Raises
    ------
    ai.client.AIError
        Transport or response failure.
    ai.parsing.AIStructuredOutputError
        The answer was unusable and no correction was possible.
    ai.parsing.AICorrectionFailedError
        The single correction attempt also failed.
    """

    spec = build_prompt(
        room,
        preferences,
        budget,
        brief,
        concept,
        recommendations,
        spatial,
        analysis,
        catalog,
        budget_is_complete=budget_is_complete,
        placement=placement,
    )
    return run_structured_request(
        config,
        spec,
        DesignEvaluation,
        max_tokens=MAX_TOKENS,
        timeout=timeout,
        completer=completer,
    )


__all__ = [
    "MATERIALS_NOT_PRICED_NOTE",
    "MAX_TOKENS",
    "build_prompt",
    "evaluate_design",
]
