"""Brief Analyzer: turn the user's raw input into a structured design brief.

This is the first of the four AI operations. It reads validated input models and
returns a :class:`models.schemas.DesignBrief`.

What the model may do: interpret intent, name functional priorities, spot
constraints, ambiguities and contradictions, and flag warnings.

What the model may not do: change the room, the budget or the stated
preferences, and it is given the already-computed floor area rather than being
asked to derive one.
"""

from __future__ import annotations

from dataclasses import dataclass

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
    DesignBrief,
    DesignPreferences,
    RoomInput,
    UserRequirements,
)

#: Application token budget for this operation. Not a provider maximum.
#:
#: Raised from 2000 in Phase 6 after the provider intermittently truncated real
#: brief answers. This model spends part of the output budget on reasoning
#: tokens before it writes the JSON, so a brief that looks small on paper needs
#: far more than its character count suggests. Measured on real responses for
#: the Phase 6 QA room: prompt 751 tokens, completion 1437-2202 tokens for a
#: 1.8-2.9 KB payload, with 2000 truncating once in three attempts and 8000
#: finishing with ``stop`` every time. The cap is output-only; the prompt is not
#: charged against it, so raising it costs nothing unless the model uses it.
MAX_TOKENS = 8000

_ROLE = (
    "You are the brief analyst for an interior design application. You read a "
    "user's room, preferences, requirements and budget, then produce a concise "
    "structured brief that the rest of the application will rely on.\n"
    "You describe what the user wants. You do not design the room, choose "
    "furniture, or change any figure you are given."
)

_CONTRACT = """REQUIRED OUTPUT SHAPE (one JSON object, no extra keys)
{
  "summary": "2-4 sentences describing the user's goals and the space",
  "functional_priorities": ["up to 10 short phrases, most important first"],
  "constraints": ["up to 10 short phrases limiting the design"],
  "ambiguities": ["up to 10 short phrases about unclear or missing information"],
  "warnings": ["up to 10 short phrases about likely problems"]
}

FIELD RULES
- summary: 1-2000 characters, plain prose.
- Each list: at most 10 items, each 1-200 characters, one idea per item.
- Use an empty list when a category genuinely does not apply.
- constraints must reflect facts the user supplied; do not invent rules.
- ambiguities are questions the user has not answered, not criticisms.
- warnings are practical risks, such as a tight budget for the stated
  requirements. Do not repeat an ambiguity as a warning.
- figures such as floor area are supplied as calculated facts. Never restate
  them as your own measurement, and never compute new ones."""


def build_prompt(
    room: RoomInput,
    preferences: DesignPreferences,
    requirements: UserRequirements,
    budget: BudgetInput,
) -> PromptSpec:
    """Assemble the prompt from validated inputs.

    Published as a function so tests can assert what the model is actually told
    without intercepting a request.
    """

    context = (
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


@dataclass(frozen=True)
class BriefAnalysis:
    """A brief plus the prompt that produced it.

    ``prompt`` is kept for the interface's "what was sent" panel and for tests;
    it contains only input data, never the credential or the raw answer.
    """

    brief: DesignBrief
    prompt: PromptSpec


def analyze_brief(
    config: AIConfig,
    room: RoomInput,
    preferences: DesignPreferences,
    requirements: UserRequirements,
    budget: BudgetInput,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    completer: Completer | None = None,
) -> DesignBrief:
    """Analyse the user's input and return a validated brief.

    Raises
    ------
    ai.client.AIError
        The request failed (network, authentication, rate limit, truncation).
        No correction is attempted for these.
    ai.parsing.AIStructuredOutputError
        The answer was unusable and no correction was possible.
    ai.parsing.AICorrectionFailedError
        The single correction attempt also failed.
    """

    return analyze_brief_with_prompt(
        config,
        room,
        preferences,
        requirements,
        budget,
        timeout=timeout,
        completer=completer,
    ).brief


def analyze_brief_with_prompt(
    config: AIConfig,
    room: RoomInput,
    preferences: DesignPreferences,
    requirements: UserRequirements,
    budget: BudgetInput,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    completer: Completer | None = None,
) -> BriefAnalysis:
    """Same as :func:`analyze_brief`, also returning the prompt."""

    spec = build_prompt(room, preferences, requirements, budget)
    brief = run_structured_request(
        config,
        spec,
        DesignBrief,
        max_tokens=MAX_TOKENS,
        timeout=timeout,
        completer=completer,
    )
    return BriefAnalysis(brief=brief, prompt=spec)


__all__ = [
    "MAX_TOKENS",
    "BriefAnalysis",
    "analyze_brief",
    "analyze_brief_with_prompt",
    "build_prompt",
]
