"""Prompt construction and the single structured-request flow.

Every AI service performs the same sequence: build a prompt from validated
inputs, send exactly one request, parse the answer, and permit at most one
correction. That sequence lives here once so the four services stay small and
cannot drift apart.

Prompt layout
-------------
A :class:`PromptSpec` has three parts:

``system``
    The role and the non-negotiable output rules.
``context``
    The validated input data, serialised deterministically.
``contract``
    The exact JSON shape and field limits the answer must satisfy.

The context is reused verbatim when a correction is requested, so the model
always repairs against the same facts. The model's previous answer is
deliberately *not* echoed back: it is untrusted text, it can be thousands of
tokens long, and the error description plus the contract are what a correction
actually needs.

What this module does not do: no HTTP of its own, no Streamlit, no credential
handling, no domain arithmetic. It calls ``ai.client.complete`` (or a callable
injected by a test) and returns a validated Pydantic model.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, TypeVar

from pydantic import BaseModel

from ai.client import DEFAULT_TIMEOUT_SECONDS, ChatCompletion, complete
from ai.config import AIConfig
from ai.parsing import AIStructuredOutputError, parse_with_correction
from models.schemas import FurnitureItem, RoomInput, RoomType, Wall

#: Type variable for the Pydantic model an answer is validated into.
ModelT = TypeVar("ModelT", bound=BaseModel)

#: Callable used to reach the model. Production callers leave it as ``None`` so
#: :func:`ai.client.complete` is used; tests inject a fake so no socket opens.
Completer = Callable[..., ChatCompletion]

#: Rules that apply to every AI response in this application. They are repeated
#: in each prompt because a model has no memory between calls.
OUTPUT_RULES = (
    "Answer with exactly one JSON object. No prose, no Markdown, no code fences.\n"
    "Use only the keys listed in the contract. Any other key is an error.\n"
    "Never invent catalog items, prices, dimensions or measurements.\n"
    "Never perform arithmetic. Figures described as calculated are "
    "authoritative and must be repeated as given, not recomputed.\n"
    "Write plain sentences in text fields, not Markdown or bullet lists."
)

#: Sentence used to open a correction request.
_CORRECTION_LEAD = "Your previous answer could not be used."


# --------------------------------------------------------------------------- #
# Serialisation
# --------------------------------------------------------------------------- #


def _jsonable(value: Any) -> Any:
    """Convert models, enums and decimals into JSON-safe primitives.

    ``model_dump(mode="json")`` already handles the pydantic types; the other
    branches cover plain values that callers pass alongside them.
    """

    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def json_block(value: Any) -> str:
    """Render ``value`` as indented JSON for inclusion in a prompt.

    Deterministic ordering and no ASCII escaping keep the prompt stable between
    runs, which makes prompt-level tests meaningful.
    """

    return json.dumps(_jsonable(value), ensure_ascii=False, indent=2)


def system_prompt(role: str) -> str:
    """Combine a service's role statement with the shared output rules."""

    return f"{role}\n\nOUTPUT RULES\n{OUTPUT_RULES}"


# --------------------------------------------------------------------------- #
# Prompt specification
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class PromptSpec:
    """A complete prompt, reusable for the first attempt and the correction."""

    system: str
    context: str
    contract: str

    def messages(self) -> list[dict[str, str]]:
        """Messages for the first attempt."""

        return [
            {"role": "system", "content": self.system},
            {"role": "user", "content": self.user_content()},
        ]

    def user_content(self) -> str:
        """The user message body: data first, then the required shape."""

        return f"{self.context}\n\n{self.contract}"

    def correction_messages(
        self, error: AIStructuredOutputError
    ) -> list[dict[str, str]]:
        """Messages for the single permitted correction attempt.

        The error text is the content-free diagnosis produced by
        :mod:`ai.parsing`, so no provider output reaches the model or a log.
        """

        note = (
            f"{_CORRECTION_LEAD}\n"
            f"Reason: {error.original_reason}\n"
            "Return the corrected JSON object now. Reply with JSON only."
        )
        return [
            {"role": "system", "content": self.system},
            {
                "role": "user",
                "content": f"{self.context}\n\n{note}\n\n{self.contract}",
            },
        ]


# --------------------------------------------------------------------------- #
# Request flow
# --------------------------------------------------------------------------- #


def run_structured_request(
    config: AIConfig,
    spec: PromptSpec,
    model: type[ModelT],
    *,
    max_tokens: int,
    temperature: float = 0.0,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    completer: Completer | None = None,
) -> ModelT:
    """Send one request, validate the answer, allow one correction.

    A transport failure (timeout, authentication, rate limit, truncation) is
    raised by :func:`ai.client.complete` before parsing starts, so no correction
    is attempted for those: retrying an unreachable or truncated call would
    repeat the same failure. Only an unparseable or schema-invalid answer
    triggers the correction, which is exactly the rule in
    ``TECHNICAL_ARCHITECTURE.md``.

    Domain checks that Python must own — catalog identifiers, room-type
    support — are deliberately *not* part of this loop. They run afterwards as
    validation findings, so a model answer is never silently rewritten to look
    valid and a provider never gets to arbitrate a catalog fact.

    Raises
    ------
    ai.client.AIError
        Any classified transport or response failure.
    ai.parsing.AIStructuredOutputError
        The answer could not be validated and no correction was possible.
    ai.parsing.AICorrectionFailedError
        The correction was attempted and also failed.
    """

    call = completer if completer is not None else complete

    first = call(
        config,
        spec.messages(),
        max_tokens=max_tokens,
        temperature=temperature,
        timeout=timeout,
    )

    def correct(error: AIStructuredOutputError) -> str:
        repaired = call(
            config,
            spec.correction_messages(error),
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
        )
        return repaired.content

    outcome = parse_with_correction(first.content, model, corrector=correct)
    return outcome.value


# --------------------------------------------------------------------------- #
# Shared input fragments
# --------------------------------------------------------------------------- #


def room_facts(room: RoomInput) -> dict[str, Any]:
    """Deterministic room figures, supplied so the model never computes them."""

    return {
        "room_type": room.room_type.value,
        "floor_area_sqm": round(room.area_sqm, 2),
        "wall_spans_cm": {
            wall.value: room.wall_span_cm(wall) for wall in Wall
        },
    }


def catalogue_entry(item: FurnitureItem) -> dict[str, Any]:
    """One catalog item as the model may see it.

    Dimensions and costs come from the local catalog, never from the model, and
    the model is told not to repeat them in its answer. The cost is formatted to
    two decimal places so the same item always renders identically in a prompt.
    """

    return {
        "item_id": item.item_id,
        "name": item.name,
        "category": item.category,
        "width_cm": item.width_cm,
        "depth_cm": item.depth_cm,
        "indicative_unit_cost": f"{Decimal(item.indicative_unit_cost):.2f}",
        "supported_room_types": [
            room_type.value for room_type in item.supported_room_types
        ],
    }


def items_for_room(
    items: Sequence[FurnitureItem], room_type: RoomType
) -> list[FurnitureItem]:
    """Catalog entries that the room type may actually use."""

    return [item for item in items if room_type in item.supported_room_types]


__all__ = [
    "Completer",
    "ModelT",
    "OUTPUT_RULES",
    "PromptSpec",
    "catalogue_entry",
    "items_for_room",
    "json_block",
    "room_facts",
    "run_structured_request",
    "system_prompt",
]
