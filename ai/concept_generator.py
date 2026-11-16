"""Concept Generator: produce exactly three distinct design concepts.

The second AI operation. It reads the analysed brief and the user's choices and
returns a validated :class:`models.schemas.ConceptCollection` containing three
concepts that differ in substance, not just in name.

Distinctness is enforced twice: the prompt asks for genuinely different
directions, and ``ConceptCollection``'s own validator rejects duplicate names.
The model is also told not to clone one set of ideas under three headings,
because a choice between three copies is not a choice.
"""

from __future__ import annotations

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
    BudgetInput,
    ConceptCollection,
    DesignBrief,
    DesignPreferences,
    RoomInput,
    UserRequirements,
    REQUIRED_CONCEPT_COUNT,
)

#: Application token budget. Three full concepts need the most headroom.
MAX_TOKENS = 6000

_ROLE = (
    "You are a senior interior designer. Given a structured brief and the user's "
    "chosen style and palette, you propose exactly three design concepts for one "
    "room.\n"
    "Each concept is a different way to answer the brief, not a different "
    "word for the same answer."
)

_CONTRACT = f"""REQUIRED OUTPUT SHAPE (one JSON object, no extra keys)
{{
  "concepts": [
    {{
      "name": "short distinctive title, 1-80 characters",
      "description": "2-4 sentences: the overall idea and atmosphere",
      "design_direction": "one sentence on composition and layout intent",
      "color_and_material_direction": "one sentence on palette and materials",
      "furniture_approach": "one sentence on the kind and amount of furniture",
      "functional_rationale": "1-3 sentences on how the brief is satisfied",
      "budget_suitability": "one sentence on fit with the stated budget"
    }}
  ]
}}

FIELD RULES
- concepts: exactly {REQUIRED_CONCEPT_COUNT} items. More or fewer is an error.
- name: 1-80 characters. All three names must differ from each other.
- description: 1-2000 characters. Other text fields: 1-200 characters.
- All fields are required in every concept.

DISTINCTNESS RULES
- Give each concept a different organising idea, for example a different
  seating arrangement, a different focal point, or a different use of the
  budget.
- Do not submit the same concept under three names, and do not vary only the
  adjectives.
- Keep the user's chosen style and palette recognisable in all three; the
  concepts are variations within that direction, not a replacement for it.
- If the user chose a style and a palette that pull in different directions,
  explore that tension differently in each concept.

CONSTRAINT RULES
- Never invent measurements, prices or catalog items.
- Do not claim a concept fits the budget unless the brief or the budget data
  supports it.
- The three concepts must all be achievable in the described room."""


def build_prompt(
    room: RoomInput,
    preferences: DesignPreferences,
    requirements: UserRequirements,
    budget: BudgetInput,
    brief: DesignBrief,
) -> PromptSpec:
    """Assemble the prompt from the brief and the user's choices."""

    context = (
        "STRUCTURED DESIGN BRIEF\n"
        f"{json_block(brief)}\n\n"
        "ROOM\n"
        f"{json_block(room)}\n\n"
        "CALCULATED ROOM FACTS (authoritative, do not recompute)\n"
        f"{json_block(room_facts(room))}\n\n"
        "DESIGN PREFERENCES\n"
        f"{json_block(preferences)}\n\n"
        "USER REQUIREMENTS\n"
        f"{json_block(requirements)}\n\n"
        "BUDGET\n"
        f"{json_block(budget)}"
    )
    return PromptSpec(
        system=system_prompt(_ROLE),
        context=context,
        contract=_CONTRACT,
    )


def generate_concepts(
    config: AIConfig,
    room: RoomInput,
    preferences: DesignPreferences,
    requirements: UserRequirements,
    budget: BudgetInput,
    brief: DesignBrief,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    completer: Completer | None = None,
) -> ConceptCollection:
    """Generate and validate three concepts.

    Raises
    ------
    ai.client.AIError
        Transport or response failure, including truncation. Truncation is
        raised rather than repaired: a half-written concept set cannot be
        corrected into a complete one by asking again without more room.
    ai.parsing.AIStructuredOutputError
        The answer was unusable and no correction was possible. The collection's
        own validator rejects a count other than three and duplicate names.
    ai.parsing.AICorrectionFailedError
        The single correction attempt also failed.
    """

    spec = build_prompt(room, preferences, requirements, budget, brief)
    return run_structured_request(
        config,
        spec,
        ConceptCollection,
        max_tokens=MAX_TOKENS,
        timeout=timeout,
        completer=completer,
    )


__all__ = [
    "MAX_TOKENS",
    "build_prompt",
    "generate_concepts",
]
