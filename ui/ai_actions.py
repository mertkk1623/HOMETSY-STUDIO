"""The single bridge between the AI services and the Streamlit screens.

Why this module exists
----------------------
The screens need three things the AI package cannot give them directly: a
configured client, one call per service, and a sentence a person can read when
the call fails. Keeping those here means:

* the page modules stay presentation-only and never build a prompt,
* ``ai`` is imported **inside** the functions, so importing the interface does
  not import the AI layer. That is what keeps the deterministic screens provably
  AI-free, and it is the same lazy-import rule ``ui.session`` already follows
  for Streamlit,
* error copy lives in one table instead of being rewritten per screen.

What this module deliberately does not do
-----------------------------------------
No retry, no second attempt, no prompt editing and no model choice. Approval for
those belongs to ``ai`` and to the project owner. A failure is reported as a
failure; it is never turned into a result.
"""

from __future__ import annotations

from typing import Final, Sequence

from models.schemas import (
    BudgetAnalysis,
    BudgetInput,
    ConceptCollection,
    DesignBrief,
    DesignConcept,
    DesignEvaluation,
    DesignPreferences,
    FurnitureRecommendation,
    PlacementOutcome,
    RoomInput,
    SpatialValidation,
    UserRequirements,
)

#: Name of the credential, used only in the message that explains how to set it.
SECRET_NAME: Final[str] = "DEPLOY_API_KEY"

#: One readable sentence per failure category reported by ``ai.client`` and
#: ``ai.parsing``. Keyed by their stable ``category`` attribute rather than by
#: class, so a new subclass of an existing failure needs no change here.
_FAILURE_MESSAGES: Final[dict[str, str]] = {
    "authentication_error": (
        "The AI provider rejected the API key. Check that the key is correct "
        "and is allowed to use this model, then try again."
    ),
    "rate_limit": (
        "The AI provider is receiving too many requests right now. Wait a "
        "moment, then try again."
    ),
    "timeout": (
        "The AI provider did not answer in time. Nothing was saved. Try again "
        "when the connection is stable."
    ),
    "network_error": (
        "The AI provider could not be reached. Check the network connection, "
        "then try again. Nothing was saved."
    ),
    "truncated_response": (
        "The AI answer was cut off before it finished, so it was not used. "
        "Try again; if it keeps happening the request needs a larger answer "
        "allowance, which is a change for the project owner to approve."
    ),
    "server_error": (
        "The AI provider reported an internal error. This is on their side. "
        "Try again in a few minutes. Nothing was saved."
    ),
    "invalid_json": (
        "The AI answer was not readable as structured data, so it was not "
        "used. Try again."
    ),
    "schema_validation_error": (
        "The AI answer did not match the required format, even after one "
        "correction attempt. Nothing was saved. Try again."
    ),
    "correction_failed": (
        "The AI answer did not match the required format, and the one "
        "permitted correction also failed. Nothing was saved. Try again."
    ),
    "empty_response": (
        "The AI provider returned an empty answer, so there was nothing to "
        "use. Try again."
    ),
    "response_format_error": (
        "The AI provider returned an answer this application cannot read. "
        "Nothing was saved. Try again."
    ),
    "request_error": (
        "The AI provider rejected the request as invalid. This is a "
        "configuration problem rather than something you did."
    ),
}

#: Shown for anything not in the table above, and for the configuration error
#: that has no category. Deliberately says nothing about the exception's text:
#: provider wording is untrusted and may be long or irrelevant.
_FALLBACK_MESSAGE: Final[str] = (
    "The AI request could not be completed, so nothing was saved. Try again."
)

_CONFIGURATION_MESSAGE: Final[str] = (
    f"The AI service is not configured. Set the {SECRET_NAME} environment "
    "variable or add it to the application's secret store, then reload."
)


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #


def _secret_value() -> str | None:
    """The credential from Streamlit's secret store, if it is configured.

    Reading ``st.secrets`` raises when no secrets file exists, which is the
    normal case for a local run that uses the environment variable instead. That
    is not an error: the environment is checked first by ``ai.config``, so this
    is only ever a fallback.
    """

    import streamlit as st

    try:
        value = st.secrets[SECRET_NAME]
    except Exception:  # noqa: BLE001 - an absent store is a normal state
        return None
    if isinstance(value, str) and value.strip():
        return value
    return None


def load_config():
    """Resolve the endpoint, model and credential through ``ai.config``."""

    from ai.config import load_config as _load_config

    return _load_config(fallback_api_key=_secret_value())


# --------------------------------------------------------------------------- #
# One call per service
# --------------------------------------------------------------------------- #


def analyze_brief(
    *,
    room: RoomInput,
    preferences: DesignPreferences,
    requirements: UserRequirements,
    budget: BudgetInput,
) -> DesignBrief:
    """Run AI operation 1 exactly once and return the validated brief."""

    from ai.brief_analyzer import analyze_brief as _analyze_brief

    return _analyze_brief(
        load_config(), room, preferences, requirements, budget
    )


def generate_concepts(
    *,
    room: RoomInput,
    preferences: DesignPreferences,
    requirements: UserRequirements,
    budget: BudgetInput,
    brief: DesignBrief,
) -> ConceptCollection:
    """Run AI operation 2 exactly once and return the three concepts."""

    from ai.concept_generator import generate_concepts as _generate_concepts

    return _generate_concepts(
        load_config(), room, preferences, requirements, budget, brief
    )


def recommend_furniture(
    *,
    room: RoomInput,
    preferences: DesignPreferences,
    budget: BudgetInput,
    brief: DesignBrief,
    concept: DesignConcept,
):
    """Run AI operation 3 exactly once and return the advisor's answer.

    The result is an ``ai.design_advisor.AdvisorResult``: the model's
    recommendation plus Python's catalog check and its own priced basket. It has
    no return annotation because naming the class would require importing ``ai``
    at module scope, which is exactly what this module exists to avoid.

    A catalog problem does not raise. It is reported on the result, so the screen
    can show what the model proposed together with the defect; only a transport
    or structured-output failure raises.
    """

    from ai.design_advisor import recommend_furniture as _recommend_furniture

    from ui.references import load_catalog

    return _recommend_furniture(
        load_config(),
        room,
        preferences,
        budget,
        brief,
        concept,
        load_catalog(),
    )


def evaluate_design(
    *,
    room: RoomInput,
    preferences: DesignPreferences,
    budget: BudgetInput,
    brief: DesignBrief,
    concept: DesignConcept,
    recommendations: Sequence[FurnitureRecommendation],
    spatial: SpatialValidation,
    analysis: BudgetAnalysis,
    budget_is_complete: bool = True,
    placement: PlacementOutcome | None = None,
) -> DesignEvaluation:
    """Run AI operation 4 exactly once and return the validated evaluation.

    Only the interpretation is asked for. The room, the basket, the spatial
    verdict and the totals are all finished values produced by Python and handed
    over unchanged; ``budget_is_complete`` is the budget engine's own
    ``is_trustworthy``, so a partial estimate is described as partial instead of
    being presented as a final total. ``placement`` is the stored layout
    outcome, so an incomplete layout is described as incomplete rather than
    being read off the geometry verdict alone.
    """

    from ai.design_evaluator import evaluate_design as _evaluate_design

    from ui.references import load_catalog

    return _evaluate_design(
        load_config(),
        room,
        preferences,
        budget,
        brief,
        concept,
        recommendations,
        spatial,
        analysis,
        load_catalog(),
        budget_is_complete=budget_is_complete,
        placement=placement,
    )


# --------------------------------------------------------------------------- #
# Failure copy
# --------------------------------------------------------------------------- #

def failure_message(exc: BaseException) -> str:
    """Translate a failure into one sentence fit for the screen.

    Returns copy written for this application, never the provider's own text.
    The exception is inspected only for its ``category`` attribute and for the
    configuration type, so no raw response body can reach the interface.
    """

    from ai.config import AIConfigurationError

    if isinstance(exc, AIConfigurationError):
        return _CONFIGURATION_MESSAGE

    category = getattr(exc, "category", None)
    if isinstance(category, str):
        message = _FAILURE_MESSAGES.get(category)
        if message:
            return message
    return _FALLBACK_MESSAGE


def is_configuration_failure(exc: BaseException) -> bool:
    """True when retrying cannot help until the credential is fixed."""

    from ai.config import AIConfigurationError

    return isinstance(exc, AIConfigurationError)


__all__ = [
    "SECRET_NAME",
    "analyze_brief",
    "evaluate_design",
    "failure_message",
    "generate_concepts",
    "is_configuration_failure",
    "load_config",
    "recommend_furniture",
]
