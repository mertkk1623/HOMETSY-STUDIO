"""Tests for the four AI services.

Every test injects a fake completer, so no socket opens and no key is needed.
The assertions concentrate on the two things that can actually go wrong in an
LLM pipeline: the model is told the wrong thing, or its answer is trusted when
it should not be.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from ai.brief_analyzer import (
    MAX_TOKENS as BRIEF_TOKENS,
)
from ai.brief_analyzer import analyze_brief, analyze_brief_with_prompt, build_prompt
from ai.client import (
    AIAuthenticationError,
    AIRateLimitError,
    AIServerError,
    AITimeoutError,
    AITruncatedResponseError,
)
from ai.concept_generator import MAX_TOKENS as CONCEPT_TOKENS
from ai.concept_generator import generate_concepts
from ai.parsing import AIInvalidJSONError
from ai.design_advisor import (
    MAX_TOKENS as ADVISOR_TOKENS,
)
from ai.design_advisor import (
    recommend_furniture,
    verify_catalog_references,
)
from ai.design_evaluator import MAX_TOKENS as EVALUATOR_TOKENS
from ai.design_evaluator import evaluate_design
from ai.parsing import (
    AICorrectionFailedError,
    AIStructuredOutputError,
)
from models.schemas import (
    BudgetAnalysis,
    ConceptCollection,
    DesignBrief,
    DesignEvaluation,
    DesignRecommendation,
    RoomType,
    SpatialValidation,
)

# --------------------------------------------------------------------------- #
# Reusable answers
# --------------------------------------------------------------------------- #

BRIEF_JSON = json.dumps(
    {
        "summary": "A calm living room with seating for four and a reading corner.",
        "functional_priorities": ["Seating for four", "Reading corner"],
        "constraints": ["One door and one window", "Keep the window side open"],
        "ambiguities": ["Seating type is not specified"],
        "warnings": ["A four-seat sofa may crowd the room"],
    }
)


def _concept(name: str) -> dict[str, str]:
    return {
        "name": name,
        "description": "A quiet composition built around the window.",
        "design_direction": "Low horizontal lines with a clear centre.",
        "color_and_material_direction": "Warm neutrals, oak and linen.",
        "furniture_approach": "One large sofa and two light occasional pieces.",
        "functional_rationale": "Leaves a continuous path from door to window.",
        "budget_suitability": "Fits within the stated budget.",
    }


CONCEPTS_JSON = json.dumps(
    {
        "concepts": [
            _concept("Quiet Oak"),
            _concept("Soft Contrast"),
            _concept("Warm Studio"),
        ]
    }
)

RECOMMENDATION_JSON = json.dumps(
    {
        "furniture": [
            {
                "item_id": "sofa_three_seat",
                "quantity": 1,
                "rotation_degrees": 0,
                "rationale": "Main seating, facing the window wall.",
            },
            {
                "item_id": "coffee_table",
                "quantity": 1,
                "rotation_degrees": 0,
                "rationale": "Centres the seating group.",
            },
        ],
        "materials": [
            {
                "name": "White oak",
                "category": "Wood",
                "color_direction": "Pale honey tones.",
                "rationale": "Matches the Japandi direction.",
                "quantity_note": "Main furniture pieces.",
            }
        ],
        "color_direction": "Warm off-whites with pale oak and muted olive accents.",
        "design_rationale": "A restrained palette keeps the small room calm.",
    }
)

EVALUATION_JSON = json.dumps(
    {
        "requirement_compatibility": "Seating for four is met by one three-seat sofa "
        "and an armchair.",
        "style_consistency": "The oak and linen palette matches the chosen Japandi "
        "direction.",
        "functional_suitability": "The walking path from the door to the window stays "
        "clear.",
        "budget_suitability": "The selected items stay within the stated budget.",
        "limitations": ["The reading corner is only implied"],
        "recommendations": ["Add a floor lamp beside the armchair"],
    }
)


# --------------------------------------------------------------------------- #
# Fixtures for the common argument sets
# --------------------------------------------------------------------------- #


@pytest.fixture
def brief() -> DesignBrief:
    return DesignBrief(
        summary="A calm living room for four with a reading corner.",
        functional_priorities=["Seating for four"],
        constraints=["One door and one window"],
        ambiguities=[],
        warnings=[],
    )


@pytest.fixture
def concept(brief: DesignBrief):
    from models.schemas import DesignConcept

    return DesignConcept.model_validate(_concept("Quiet Oak"))


@pytest.fixture
def spatial() -> SpatialValidation:
    return SpatialValidation(is_valid=True, warnings=["Tight clearance at the door"])


@pytest.fixture
def analysis() -> BudgetAnalysis:
    return BudgetAnalysis(
        furniture_subtotal=Decimal("25200.00"),
        total_estimated=Decimal("25200.00"),
        remaining_budget=Decimal("19800.00"),
    )


# --------------------------------------------------------------------------- #
# Token limits
# --------------------------------------------------------------------------- #


def test_application_token_limits_match_the_approved_values() -> None:
    # Concepts passed live validation unchanged. The advisor and the evaluator
    # were raised together in Phase 5 Step 3 after the provider truncated a real
    # advisor answer at 4000 completion tokens. The brief analyzer was raised in
    # Phase 6 for the same reason: its real answers needed up to 2202 completion
    # tokens, so the 2000 cap truncated intermittently.
    assert BRIEF_TOKENS == 8000
    assert CONCEPT_TOKENS == 6000
    assert ADVISOR_TOKENS == 8000
    assert EVALUATOR_TOKENS == 8000


@pytest.mark.parametrize(
    ("runner", "expected"),
    [
        ("brief", 8000),
        ("concepts", 6000),
        ("advisor", 8000),
        ("evaluator", 8000),
    ],
)
def test_each_service_uses_its_own_limit(
    runner, expected, ai_config, fake_completer, room, preferences, requirements,
    budget, brief, concept, catalog, spatial, analysis
) -> None:
    answers = {
        "brief": BRIEF_JSON,
        "concepts": CONCEPTS_JSON,
        "advisor": RECOMMENDATION_JSON,
        "evaluator": EVALUATION_JSON,
    }
    fake_completer.queue(answers[runner])

    if runner == "brief":
        analyze_brief(
            ai_config, room, preferences, requirements, budget,
            completer=fake_completer,
        )
    elif runner == "concepts":
        generate_concepts(
            ai_config, room, preferences, requirements, budget, brief,
            completer=fake_completer,
        )
    elif runner == "advisor":
        recommend_furniture(
            ai_config, room, preferences, budget, brief, concept, catalog,
            completer=fake_completer,
        )
    else:
        evaluate_design(
            ai_config, room, preferences, budget, brief, concept, [], spatial,
            analysis, catalog, completer=fake_completer,
        )

    assert fake_completer.calls[0]["max_tokens"] == expected


# --------------------------------------------------------------------------- #
# Brief Analyzer
# --------------------------------------------------------------------------- #


def test_analyze_brief_returns_a_validated_model(
    ai_config, fake_completer, room, preferences, requirements, budget
) -> None:
    fake_completer.queue(BRIEF_JSON)
    result = analyze_brief(
        ai_config, room, preferences, requirements, budget, completer=fake_completer
    )
    assert isinstance(result, DesignBrief)
    assert result.summary.startswith("A calm living room")
    assert result.functional_priorities == ["Seating for four", "Reading corner"]


def test_analyze_brief_sends_one_request(
    ai_config, fake_completer, room, preferences, requirements, budget
) -> None:
    fake_completer.queue(BRIEF_JSON)
    analyze_brief(
        ai_config, room, preferences, requirements, budget, completer=fake_completer
    )
    assert fake_completer.call_count == 1


def test_brief_prompt_contains_every_user_input(
    room, preferences, requirements, budget
) -> None:
    prompt = build_prompt(room, preferences, requirements, budget)
    text = f"{prompt.context}\n{prompt.contract}"
    assert "Seating for four" in text
    assert "Keep the window side open" in text
    assert "Japandi" in text
    assert "Warm Neutral" in text
    assert "45000" in text
    assert "oak" in text


def test_brief_prompt_supplies_the_calculated_area(
    room, preferences, requirements, budget
) -> None:
    # The area is computed by Python and handed over, so the model never derives it.
    prompt = build_prompt(room, preferences, requirements, budget)
    assert str(round(room.area_sqm, 2)) in prompt.context


def test_brief_prompt_forbids_designing_the_room(
    room, preferences, requirements, budget
) -> None:
    prompt = build_prompt(room, preferences, requirements, budget)
    assert "You do not design the room" in prompt.system


def test_brief_prompt_requires_the_exact_output_keys(
    room, preferences, requirements, budget
) -> None:
    prompt = build_prompt(room, preferences, requirements, budget)
    for key in (
        "summary",
        "functional_priorities",
        "constraints",
        "ambiguities",
        "warnings",
    ):
        assert key in prompt.contract


def test_analyze_brief_with_prompt_returns_both(
    ai_config, fake_completer, room, preferences, requirements, budget
) -> None:
    fake_completer.queue(BRIEF_JSON)
    result = analyze_brief_with_prompt(
        ai_config, room, preferences, requirements, budget, completer=fake_completer
    )
    assert result.brief.summary
    assert "ROOM" in result.prompt.context


def test_brief_missing_summary_triggers_correction(
    ai_config, fake_completer, room, preferences, requirements, budget
) -> None:
    fake_completer.queue("{}", BRIEF_JSON)
    result = analyze_brief(
        ai_config, room, preferences, requirements, budget, completer=fake_completer
    )
    assert result.summary
    assert fake_completer.call_count == 2


def test_brief_two_bad_answers_raise(
    ai_config, fake_completer, room, preferences, requirements, budget
) -> None:
    fake_completer.queue("{}", "{}")
    with pytest.raises(AICorrectionFailedError):
        analyze_brief(
            ai_config, room, preferences, requirements, budget, completer=fake_completer
        )


def test_brief_that_hits_the_token_limit_is_not_corrected(
    ai_config, fake_completer, room, preferences, requirements, budget
) -> None:
    """The Phase 6 failure mode: ``finish_reason == "length"``.

    A truncated answer is a transport-shaped failure, raised by
    :func:`ai.client.complete` before parsing. Asking the model to reformat an
    answer it never finished would spend a second, larger call on the same
    cause, so exactly one request must be made and the truncation must travel
    unchanged.
    """

    fake_completer.queue(AITruncatedResponseError("cut off at 8000 tokens"))
    with pytest.raises(AITruncatedResponseError) as excinfo:
        analyze_brief(
            ai_config, room, preferences, requirements, budget, completer=fake_completer
        )
    assert excinfo.value.category == "truncated_response"
    assert fake_completer.call_count == 1
    # The request was made at the application's own budget, not a smaller one.
    assert fake_completer.calls[0]["max_tokens"] == BRIEF_TOKENS


def test_brief_correction_uses_the_same_token_limit(
    ai_config, fake_completer, room, preferences, requirements, budget
) -> None:
    """A correction must not silently shrink the budget it was given.

    The 2000-token cap was what truncated the first answer, so a correction at
    the same limit would inherit the problem; this asserts the two calls agree
    and that both use the raised figure.
    """

    fake_completer.queue("{}", BRIEF_JSON)
    analyze_brief(
        ai_config, room, preferences, requirements, budget, completer=fake_completer
    )
    assert fake_completer.call_count == 2
    limits = [call["max_tokens"] for call in fake_completer.calls]
    assert limits == [BRIEF_TOKENS, BRIEF_TOKENS]
    assert BRIEF_TOKENS == 8000


def test_an_empty_brief_answer_is_reported_as_empty(
    ai_config, fake_completer, room, preferences, requirements, budget
) -> None:
    # An empty answer is a structured-output failure, so one correction is
    # attempted; the second empty answer ends the exchange.
    fake_completer.queue("", "")
    with pytest.raises(AICorrectionFailedError) as excinfo:
        analyze_brief(
            ai_config, room, preferences, requirements, budget, completer=fake_completer
        )
    assert "empty" in str(excinfo.value).lower()
    assert fake_completer.call_count == 2


def test_an_empty_first_answer_can_be_corrected(
    ai_config, fake_completer, room, preferences, requirements, budget
) -> None:
    fake_completer.queue("   ", BRIEF_JSON)
    result = analyze_brief(
        ai_config, room, preferences, requirements, budget, completer=fake_completer
    )
    assert result.summary.startswith("A calm living room")
    assert fake_completer.call_count == 2


def test_a_provider_error_before_any_content_is_raised_as_itself(
    ai_config, fake_completer, room, preferences, requirements, budget
) -> None:
    """A rate limit is not a formatting problem and gets no correction."""

    fake_completer.queue(AIRateLimitError("429 from the provider"))
    with pytest.raises(AIRateLimitError):
        analyze_brief(
            ai_config, room, preferences, requirements, budget, completer=fake_completer
        )
    assert fake_completer.call_count == 1


def test_a_server_error_before_any_content_is_raised_as_itself(
    ai_config, fake_completer, room, preferences, requirements, budget
) -> None:
    fake_completer.queue(AIServerError("503 from the provider"))
    with pytest.raises(AIServerError):
        analyze_brief(
            ai_config, room, preferences, requirements, budget, completer=fake_completer
        )
    assert fake_completer.call_count == 1


def test_a_schema_error_in_the_first_answer_is_corrected(
    ai_config, fake_completer, room, preferences, requirements, budget
) -> None:
    """A wrong type is correctable; only transport failures are not."""

    fake_completer.queue(json.dumps({"summary": 5}), BRIEF_JSON)
    result = analyze_brief(
        ai_config, room, preferences, requirements, budget, completer=fake_completer
    )
    assert result.summary.startswith("A calm living room")
    assert fake_completer.call_count == 2


def test_a_valid_first_answer_is_never_sent_twice(
    ai_config, fake_completer, room, preferences, requirements, budget
) -> None:
    """The happy path costs exactly one request."""

    fake_completer.queue(BRIEF_JSON)
    analyze_brief(
        ai_config, room, preferences, requirements, budget, completer=fake_completer
    )
    assert fake_completer.call_count == 1


def test_truncated_json_content_is_corrected_once_then_reported(
    ai_config, fake_completer, room, preferences, requirements, budget
) -> None:
    """JSON cut off mid-string is an ``invalid_json`` failure, not a transport one.

    This is the shape the old 2000-token cap produced when the provider still
    reported ``stop``: valid framing, unfinished payload. It is correctable, and
    it is corrected exactly once.
    """

    truncated = '{"summary": "A calm living room for four people with a read'
    fake_completer.queue(truncated, BRIEF_JSON)
    result = analyze_brief(
        ai_config, room, preferences, requirements, budget, completer=fake_completer
    )
    assert result.summary.startswith("A calm living room")
    assert fake_completer.call_count == 2

    # And when the repair is truncated too, the failure is reported, never
    # returned as a partial brief.
    fake_completer.queue(truncated, truncated)
    with pytest.raises(AICorrectionFailedError) as excinfo:
        analyze_brief(
            ai_config, room, preferences, requirements, budget, completer=fake_completer
        )
    assert "First problem" in str(excinfo.value)
    assert isinstance(excinfo.value.first_error, AIInvalidJSONError)
    assert fake_completer.call_count == 4


# --------------------------------------------------------------------------- #
# Concept Generator
# --------------------------------------------------------------------------- #


def test_generate_concepts_returns_exactly_three(
    ai_config, fake_completer, room, preferences, requirements, budget, brief
) -> None:
    fake_completer.queue(CONCEPTS_JSON)
    result = generate_concepts(
        ai_config, room, preferences, requirements, budget, brief,
        completer=fake_completer,
    )
    assert isinstance(result, ConceptCollection)
    assert len(result.concepts) == 3
    assert [c.name for c in result.concepts] == [
        "Quiet Oak",
        "Soft Contrast",
        "Warm Studio",
    ]


def test_concepts_are_distinct(
    ai_config, fake_completer, room, preferences, requirements, budget, brief
) -> None:
    fake_completer.queue(CONCEPTS_JSON)
    result = generate_concepts(
        ai_config, room, preferences, requirements, budget, brief,
        completer=fake_completer,
    )
    names = [c.name.casefold() for c in result.concepts]
    assert len(set(names)) == 3


def test_two_concepts_are_rejected_and_corrected(
    ai_config, fake_completer, room, preferences, requirements, budget, brief
) -> None:
    short = json.dumps({"concepts": [_concept("Only One"), _concept("Only Two")]})
    fake_completer.queue(short, CONCEPTS_JSON)
    result = generate_concepts(
        ai_config, room, preferences, requirements, budget, brief,
        completer=fake_completer,
    )
    assert len(result.concepts) == 3
    assert fake_completer.call_count == 2


def test_four_concepts_are_rejected(
    ai_config, fake_completer, room, preferences, requirements, budget, brief
) -> None:
    four = json.dumps(
        {"concepts": [_concept(f"C{index}") for index in range(4)]}
    )
    fake_completer.queue(four, four)
    with pytest.raises(AICorrectionFailedError):
        generate_concepts(
            ai_config, room, preferences, requirements, budget, brief,
            completer=fake_completer,
        )


def test_duplicate_concept_names_are_rejected(
    ai_config, fake_completer, room, preferences, requirements, budget, brief
) -> None:
    duplicate = json.dumps(
        {"concepts": [_concept("Same"), _concept("Same"), _concept("Other")]}
    )
    fake_completer.queue(duplicate, duplicate)
    with pytest.raises(AICorrectionFailedError):
        generate_concepts(
            ai_config, room, preferences, requirements, budget, brief,
            completer=fake_completer,
        )


def test_concept_prompt_asks_for_three_distinct_directions(
    room, preferences, requirements, budget, brief
) -> None:
    from ai.concept_generator import build_prompt as concept_prompt

    prompt = concept_prompt(room, preferences, requirements, budget, brief)
    assert "exactly 3" in prompt.contract
    assert "different organising idea" in prompt.contract
    assert "Do not submit the same concept under three names" in prompt.contract


def test_concept_prompt_carries_the_brief(
    room, preferences, requirements, budget, brief
) -> None:
    from ai.concept_generator import build_prompt as concept_prompt

    prompt = concept_prompt(room, preferences, requirements, budget, brief)
    assert brief.summary in prompt.context


def test_concept_prompt_forbids_inventing_prices(
    room, preferences, requirements, budget, brief
) -> None:
    from ai.concept_generator import build_prompt as concept_prompt

    prompt = concept_prompt(room, preferences, requirements, budget, brief)
    assert "Never invent measurements, prices or catalog items" in prompt.contract


def test_truncated_concept_answer_is_not_corrected(
    ai_config, fake_completer, room, preferences, requirements, budget, brief
) -> None:
    # A truncated answer needs more tokens, not a reformat; asking again would
    # simply truncate again.
    fake_completer.queue(AITruncatedResponseError("cut off at 6000 tokens"))
    with pytest.raises(AITruncatedResponseError):
        generate_concepts(
            ai_config, room, preferences, requirements, budget, brief,
            completer=fake_completer,
        )
    assert fake_completer.call_count == 1


# --------------------------------------------------------------------------- #
# Design Advisor: happy path
# --------------------------------------------------------------------------- #


def test_recommend_furniture_returns_a_validated_model(
    ai_config, fake_completer, room, preferences, budget, brief, concept, catalog
) -> None:
    fake_completer.queue(RECOMMENDATION_JSON)
    result = recommend_furniture(
        ai_config, room, preferences, budget, brief, concept, catalog,
        completer=fake_completer,
    )
    assert isinstance(result.recommendation, DesignRecommendation)
    assert len(result.recommendation.furniture) == 2
    assert result.recommendation.materials[0].name == "White oak"


def test_valid_recommendation_is_usable(
    ai_config, fake_completer, room, preferences, budget, brief, concept, catalog
) -> None:
    fake_completer.queue(RECOMMENDATION_JSON)
    result = recommend_furniture(
        ai_config, room, preferences, budget, brief, concept, catalog,
        completer=fake_completer,
    )
    assert result.catalog_check.is_valid
    assert result.is_usable


def test_subtotal_comes_from_the_catalog_not_the_model(
    ai_config, fake_completer, room, preferences, budget, brief, concept, catalog
) -> None:
    # sofa 18500 + coffee table 4900 = 23400, straight from data/.
    fake_completer.queue(RECOMMENDATION_JSON)
    result = recommend_furniture(
        ai_config, room, preferences, budget, brief, concept, catalog,
        completer=fake_completer,
    )
    assert result.furniture_subtotal == Decimal("23400.00")


def test_advisor_prompt_lists_only_usable_catalog_items(
    room, preferences, budget, brief, concept, catalog
) -> None:
    from ai.design_advisor import build_prompt as advisor_prompt

    prompt = advisor_prompt(room, preferences, budget, brief, concept, catalog)
    assert "sofa_three_seat" in prompt.context
    # A bedroom-only item must not be offered to a living room.
    assert "wardrobe" not in prompt.context
    assert "bed_double" not in prompt.context


def test_advisor_prompt_forbids_prices_and_dimensions(
    room, preferences, budget, brief, concept, catalog
) -> None:
    from ai.design_advisor import build_prompt as advisor_prompt

    prompt = advisor_prompt(room, preferences, budget, brief, concept, catalog)
    assert "Do not state prices" in prompt.contract
    assert "Do not state widths" in prompt.contract
    assert "Do not assign positions" in prompt.contract


# --------------------------------------------------------------------------- #
# Design Advisor: catalog validation
# --------------------------------------------------------------------------- #


def test_unknown_item_id_is_reported(
    ai_config, fake_completer, room, preferences, budget, brief, concept, catalog
) -> None:
    payload = json.loads(RECOMMENDATION_JSON)
    payload["furniture"][0]["item_id"] = "designer_sofa_deluxe"
    fake_completer.queue(json.dumps(payload))
    result = recommend_furniture(
        ai_config, room, preferences, budget, brief, concept, catalog,
        completer=fake_completer,
    )
    assert not result.catalog_check.is_valid
    assert not result.is_usable
    codes = [finding.code for finding in result.catalog_check.findings]
    assert "unknown_catalog_item" in codes


def test_unknown_item_is_not_replaced(
    ai_config, fake_completer, room, preferences, budget, brief, concept, catalog
) -> None:
    # Silently swapping in a similar sofa would change what the user is buying.
    payload = json.loads(RECOMMENDATION_JSON)
    payload["furniture"][0]["item_id"] = "designer_sofa_deluxe"
    fake_completer.queue(json.dumps(payload))
    result = recommend_furniture(
        ai_config, room, preferences, budget, brief, concept, catalog,
        completer=fake_completer,
    )
    ids = [item.item_id for item in result.recommendation.furniture]
    assert "designer_sofa_deluxe" in ids
    assert ids.count("sofa_three_seat") == 0


def test_room_type_mismatch_is_reported(
    ai_config, fake_completer, room, preferences, budget, brief, concept, catalog
) -> None:
    # ``wardrobe`` supports bedrooms only.
    payload = json.loads(RECOMMENDATION_JSON)
    payload["furniture"].append(
        {"item_id": "wardrobe", "quantity": 1, "rotation_degrees": 0, "rationale": ""}
    )
    fake_completer.queue(json.dumps(payload))
    result = recommend_furniture(
        ai_config, room, preferences, budget, brief, concept, catalog,
        completer=fake_completer,
    )
    codes = [finding.code for finding in result.catalog_check.findings]
    assert "unsupported_room_type" in codes
    assert not result.is_usable


def test_bedroom_room_accepts_a_wardrobe(
    ai_config, fake_completer, preferences, budget, brief, concept, catalog
) -> None:
    from models.schemas import OpeningInput, RoomInput, Wall

    bedroom = RoomInput(
        room_type=RoomType.BEDROOM,
        name="Bedroom",
        width_cm=350,
        length_cm=400,
        door=OpeningInput(wall=Wall.SOUTH, offset_cm=40, width_cm=80),
        window=OpeningInput(wall=Wall.NORTH, offset_cm=100, width_cm=120),
    )
    payload = {
        "furniture": [
            {"item_id": "bed_double", "quantity": 1, "rotation_degrees": 0},
            {"item_id": "wardrobe", "quantity": 1, "rotation_degrees": 0},
        ],
        "materials": [],
        "color_direction": "Soft neutrals.",
        "design_rationale": "Two required pieces only.",
    }
    fake_completer.queue(json.dumps(payload))
    result = recommend_furniture(
        ai_config, bedroom, preferences, budget, brief, concept, catalog,
        completer=fake_completer,
    )
    assert result.catalog_check.is_valid


def test_catalog_check_uses_the_phase_three_rule(
    room, catalog, concept
) -> None:
    # The codes must be the ones core.validation already emits, not a new set.
    from core.validation import validate_catalog_references
    from models.schemas import FurnitureRecommendation

    recommendation = DesignRecommendation(
        furniture=[FurnitureRecommendation(item_id="ghost")],
        materials=[],
        color_direction="Neutral.",
        design_rationale="Test.",
    )
    check = verify_catalog_references(room, recommendation, catalog)
    expected = validate_catalog_references(room, recommendation.furniture, catalog)
    assert [f.code for f in check.findings] == [f.code for f in expected]


def test_unknown_item_does_not_produce_a_trustworthy_total(
    ai_config, fake_completer, room, preferences, budget, brief, concept, catalog
) -> None:
    payload = json.loads(RECOMMENDATION_JSON)
    payload["furniture"].append(
        {"item_id": "ghost_table", "quantity": 1, "rotation_degrees": 0}
    )
    fake_completer.queue(json.dumps(payload))
    result = recommend_furniture(
        ai_config, room, preferences, budget, brief, concept, catalog,
        completer=fake_completer,
    )
    assert not result.budget.is_trustworthy
    assert not result.is_usable


def test_catalog_error_does_not_raise(
    ai_config, fake_completer, room, preferences, budget, brief, concept, catalog
) -> None:
    # A bad reference is a finding, not a crash: the interface shows the
    # proposal and the defect together.
    payload = json.loads(RECOMMENDATION_JSON)
    payload["furniture"][0]["item_id"] = "ghost"
    fake_completer.queue(json.dumps(payload))
    result = recommend_furniture(
        ai_config, room, preferences, budget, brief, concept, catalog,
        completer=fake_completer,
    )
    assert result.catalog_check.messages


# --------------------------------------------------------------------------- #
# Design Advisor: the model may not price or measure
# --------------------------------------------------------------------------- #


def test_model_supplied_prices_are_ignored(
    ai_config, fake_completer, room, preferences, budget, brief, concept, catalog
) -> None:
    # The schema has no price field, so an attempt to include one is rejected by
    # ``extra="forbid"`` rather than silently influencing the subtotal.
    payload = json.loads(RECOMMENDATION_JSON)
    payload["furniture"][0]["unit_cost"] = "1.00"
    fake_completer.queue(json.dumps(payload), RECOMMENDATION_JSON)
    result = recommend_furniture(
        ai_config, room, preferences, budget, brief, concept, catalog,
        completer=fake_completer,
    )
    assert fake_completer.call_count == 2
    assert result.furniture_subtotal == Decimal("23400.00")


def test_model_supplied_dimensions_are_ignored(
    ai_config, fake_completer, room, preferences, budget, brief, concept, catalog
) -> None:
    payload = json.loads(RECOMMENDATION_JSON)
    payload["furniture"][0]["width_cm"] = 9999
    fake_completer.queue(json.dumps(payload), RECOMMENDATION_JSON)
    result = recommend_furniture(
        ai_config, room, preferences, budget, brief, concept, catalog,
        completer=fake_completer,
    )
    assert fake_completer.call_count == 2
    priced_ids = [line.item_id for line in result.budget.line_items]
    assert "sofa_three_seat" in priced_ids


def test_geometry_fields_are_not_accepted_from_the_model(
    ai_config, fake_completer, room, preferences, budget, brief, concept, catalog
) -> None:
    # Position is optional in the schema but must not be invented: if the model
    # supplies one, it is kept as data only and never used for validation.
    payload = json.loads(RECOMMENDATION_JSON)
    payload["furniture"][0]["position_x_cm"] = 10
    payload["furniture"][0]["position_y_cm"] = 10
    fake_completer.queue(json.dumps(payload))
    result = recommend_furniture(
        ai_config, room, preferences, budget, brief, concept, catalog,
        completer=fake_completer,
    )
    # The advisor never runs spatial validation; it only prices.
    assert result.furniture_subtotal == Decimal("23400.00")


def test_advisor_makes_no_geometry_claims(
    ai_config, fake_completer, room, preferences, budget, brief, concept, catalog
) -> None:
    fake_completer.queue(RECOMMENDATION_JSON)
    result = recommend_furniture(
        ai_config, room, preferences, budget, brief, concept, catalog,
        completer=fake_completer,
    )
    # There is no spatial result on an AdvisorResult at all: geometry is a
    # separate, deterministic step the caller must run.
    assert not hasattr(result, "spatial_validation")


# --------------------------------------------------------------------------- #
# Design Evaluator
# --------------------------------------------------------------------------- #


def test_evaluate_design_returns_a_validated_model(
    ai_config, fake_completer, room, preferences, budget, brief, concept,
    catalog, spatial, analysis,
) -> None:
    fake_completer.queue(EVALUATION_JSON)
    result = evaluate_design(
        ai_config, room, preferences, budget, brief, concept, [], spatial,
        analysis, catalog, completer=fake_completer,
    )
    assert isinstance(result, DesignEvaluation)
    assert result.limitations == ["The reading corner is only implied"]


def test_evaluator_prompt_contains_the_calculated_results(
    room, preferences, budget, brief, concept, catalog, spatial, analysis
) -> None:
    from ai.design_evaluator import build_prompt as evaluator_prompt

    prompt = evaluator_prompt(
        room, preferences, budget, brief, concept, [], spatial, analysis, catalog
    )
    assert "25200.00" in prompt.context
    assert "19800.00" in prompt.context
    assert "Tight clearance at the door" in prompt.context
    assert "is_valid" in prompt.context


def test_evaluator_prompt_forbids_recalculation(
    room, preferences, budget, brief, concept, catalog, spatial, analysis
) -> None:
    from ai.design_evaluator import build_prompt as evaluator_prompt

    prompt = evaluator_prompt(
        room, preferences, budget, brief, concept, [], spatial, analysis, catalog
    )
    assert "never recalculate" in prompt.contract
    assert "It is correct by construction" in prompt.contract


def test_evaluator_is_told_when_the_budget_is_incomplete(
    room, preferences, budget, brief, concept, catalog, spatial, analysis
) -> None:
    from ai.design_evaluator import build_prompt as evaluator_prompt

    prompt = evaluator_prompt(
        room, preferences, budget, brief, concept, [], spatial, analysis, catalog,
        budget_is_complete=False,
    )
    assert '"is_complete": false' in prompt.context


def test_evaluator_sees_blocking_problems(
    ai_config, fake_completer, room, preferences, budget, brief, concept, catalog,
    analysis,
) -> None:
    invalid = SpatialValidation(
        is_valid=False,
        boundary_violations=["sofa_three_seat extends beyond the north wall"],
        overlaps=["sofa_three_seat overlaps coffee_table"],
    )
    fake_completer.queue(EVALUATION_JSON)
    evaluate_design(
        ai_config, room, preferences, budget, brief, concept, [], invalid,
        analysis, catalog, completer=fake_completer,
    )
    prompt = fake_completer.prompt_text(0)
    assert "extends beyond the north wall" in prompt
    assert "overlaps coffee_table" in prompt


def test_evaluator_uses_catalog_names_not_model_names(
    ai_config, fake_completer, room, preferences, budget, brief, concept,
    catalog, spatial, analysis,
) -> None:
    from models.schemas import FurnitureRecommendation

    fake_completer.queue(EVALUATION_JSON)
    evaluate_design(
        ai_config, room, preferences, budget, brief, concept,
        [FurnitureRecommendation(item_id="sofa_three_seat")],
        spatial, analysis, catalog, completer=fake_completer,
    )
    assert "Three-seat sofa" in fake_completer.prompt_text(0)


def test_unknown_item_reaches_the_evaluator_as_unknown(
    ai_config, fake_completer, room, preferences, budget, brief, concept,
    catalog, spatial, analysis,
) -> None:
    from models.schemas import FurnitureRecommendation

    fake_completer.queue(EVALUATION_JSON)
    evaluate_design(
        ai_config, room, preferences, budget, brief, concept,
        [FurnitureRecommendation(item_id="ghost_item")],
        spatial, analysis, catalog, completer=fake_completer,
    )
    assert "(not in catalog)" in fake_completer.prompt_text(0)


def test_evaluator_is_told_materials_are_not_priced_rather_than_zero(
    room, preferences, budget, brief, concept, catalog, spatial, analysis
) -> None:
    """A bare ``material_subtotal: 0.00`` reads to a model as "materials are free".

    A live run duly wrote "the material subtotal of 0.00", so the figure is
    withheld and replaced by a sentence that says the cost is unknown.
    """

    from ai.design_evaluator import (
        MATERIALS_NOT_PRICED_NOTE,
        build_prompt as evaluator_prompt,
    )

    assert analysis.material_subtotal == Decimal("0.00")
    prompt = evaluator_prompt(
        room, preferences, budget, brief, concept, [], spatial, analysis, catalog
    )
    assert '"material_subtotal"' not in prompt.context
    assert "cost is unknown rather than zero" in prompt.context
    assert MATERIALS_NOT_PRICED_NOTE in prompt.context
    # And the contract forbids the wording the live run produced.
    assert '"material subtotal of 0.00"' in prompt.contract
    assert "unknown" in prompt.contract


def test_a_real_material_cost_is_still_reported(
    room, preferences, budget, brief, concept, catalog, spatial
) -> None:
    """Withholding a genuine cost would be the opposite mistake."""

    from ai.design_evaluator import build_prompt as evaluator_prompt
    from models.schemas import BudgetAnalysis

    priced = BudgetAnalysis(
        furniture_subtotal=Decimal("25200.00"),
        material_subtotal=Decimal("3000.00"),
        total_estimated=Decimal("28200.00"),
        remaining_budget=Decimal("16800.00"),
    )
    prompt = evaluator_prompt(
        room, preferences, budget, brief, concept, [], spatial, priced, catalog
    )
    assert '"material_subtotal": "3000.00"' in prompt.context


def test_evaluator_is_told_when_the_layout_left_items_out(
    room, preferences, budget, brief, concept, catalog, spatial, analysis
) -> None:
    """Valid geometry is not a complete design: the omission must be explicit.

    Without this block a live run called a one-of-three layout "buildable as
    calculated", because the spatial verdict was the only geometry it saw.
    """

    from ai.design_evaluator import build_prompt as evaluator_prompt
    from models.schemas import (
        PlacementOutcome,
        PlacementStatus,
        PlacedFootprint,
        UnplacedItem,
    )

    partial = PlacementOutcome(
        status=PlacementStatus.PARTIAL,
        placed=[
            PlacedFootprint(
                item_id="bookshelf", label="Bookshelf", left_cm=10.0,
                bottom_cm=65.0, width_cm=90.0, depth_cm=35.0,
            )
        ],
        unplaced=[
            UnplacedItem(
                item_id="armchair", label="Armchair", count=1,
                reason_code="no_space",
                reason="Every candidate position overlapped the door clearance.",
            )
        ],
    )
    prompt = evaluator_prompt(
        room, preferences, budget, brief, concept, [], spatial, analysis, catalog,
        placement=partial,
    )
    assert '"status": "partial"' in prompt.context
    assert '"every_requested_item_placed": false' in prompt.context
    assert '"copies_not_placed": 1' in prompt.context
    assert "Armchair" in prompt.context
    assert "do not call the design fully" in prompt.contract


def test_a_complete_layout_is_not_flagged_as_incomplete(
    room, preferences, budget, brief, concept, catalog, spatial, analysis
) -> None:
    from ai.design_evaluator import build_prompt as evaluator_prompt
    from models.schemas import PlacementOutcome, PlacementStatus

    complete = PlacementOutcome(status=PlacementStatus.COMPLETE)
    prompt = evaluator_prompt(
        room, preferences, budget, brief, concept, [], spatial, analysis, catalog,
        placement=complete,
    )
    assert '"every_requested_item_placed": true' in prompt.context
    assert '"status": "partial"' not in prompt.context


def test_an_unrecorded_layout_is_stated_as_unrecorded(
    room, preferences, budget, brief, concept, catalog, spatial, analysis
) -> None:
    """The default must not silently claim the layout was complete."""

    from ai.design_evaluator import build_prompt as evaluator_prompt

    prompt = evaluator_prompt(
        room, preferences, budget, brief, concept, [], spatial, analysis, catalog
    )
    assert '"recorded": false' in prompt.context
    assert "every_requested_item_placed" not in prompt.context


# --------------------------------------------------------------------------- #
# The evaluator must see where the furniture actually is
# --------------------------------------------------------------------------- #


def _placed_layout():
    """A layout that contradicts a "bed centred on the west wall" concept."""

    from models.schemas import PlacementOutcome, PlacementStatus, PlacedFootprint

    return PlacementOutcome(
        status=PlacementStatus.COMPLETE,
        strategy="east-first",
        placed=[
            PlacedFootprint(
                item_id="bed_double", label="Double bed", left_cm=240.0,
                bottom_cm=380.0, width_cm=200.0, depth_cm=160.0,
                rotation_degrees=90,
            ),
            PlacedFootprint(
                item_id="bedside_table", label="Bedside table", left_cm=100.0,
                bottom_cm=0.0, width_cm=45.0, depth_cm=40.0,
            ),
        ],
    )


def test_placement_block_carries_the_real_coordinates(
    room, preferences, budget, brief, concept, catalog, spatial, analysis
) -> None:
    """The model cannot check a spatial claim it was never shown the evidence for.

    A live report repeated "the bed centred on the 540 cm west wall" while the
    bed stood at (240, 380), because the evaluator received counts only.
    """

    from ai.design_evaluator import build_prompt as evaluator_prompt

    prompt = evaluator_prompt(
        room, preferences, budget, brief, concept, [], spatial, analysis, catalog,
        placement=_placed_layout(),
    )
    context = prompt.context

    assert '"position_x_cm": 240.0' in context
    assert '"position_y_cm": 380.0' in context
    assert '"position_x_cm": 100.0' in context
    assert '"position_y_cm": 0.0' in context
    # The rotated extents, not the catalog's unrotated width/depth.
    assert '"width": 200.0' in context
    assert '"depth": 160.0' in context
    assert '"rotation_degrees": 90' in context
    assert "Double bed" in context


def test_placement_block_explains_the_coordinate_frame(
    room, preferences, budget, brief, concept, catalog, spatial, analysis
) -> None:
    """Coordinates are meaningless without an origin and axis directions."""

    from ai.design_evaluator import build_prompt as evaluator_prompt

    prompt = evaluator_prompt(
        room, preferences, budget, brief, concept, [], spatial, analysis, catalog,
        placement=_placed_layout(),
    )

    assert "south-west corner" in prompt.context
    assert "x grows towards the east wall" in prompt.context
    assert "y grows towards the north wall" in prompt.context


def test_placement_block_without_placed_items_reports_none(
    room, preferences, budget, brief, concept, catalog, spatial, analysis
) -> None:
    """A complete-but-empty placement list must not fabricate coordinates."""

    from ai.design_evaluator import build_prompt as evaluator_prompt
    from models.schemas import PlacementOutcome, PlacementStatus

    prompt = evaluator_prompt(
        room, preferences, budget, brief, concept, [], spatial, analysis, catalog,
        placement=PlacementOutcome(status=PlacementStatus.COMPLETE),
    )

    assert '"placed": []' in prompt.context
    assert "position_x_cm" not in prompt.context


def test_an_unrecorded_layout_carries_no_coordinates(
    room, preferences, budget, brief, concept, catalog, spatial, analysis
) -> None:
    """Without a stored layout there is no evidence, so no frame is offered."""

    from ai.design_evaluator import build_prompt as evaluator_prompt

    prompt = evaluator_prompt(
        room, preferences, budget, brief, concept, [], spatial, analysis, catalog
    )

    assert '"recorded": false' in prompt.context
    assert "position_x_cm" not in prompt.context
    assert "south-west corner" not in prompt.context


def test_evaluator_must_not_claim_unverified_spatial_consistency(
    room, preferences, budget, brief, concept, catalog, spatial, analysis
) -> None:
    """The contract has to forbid the exact sentence the live run produced."""

    from ai.design_evaluator import build_prompt as evaluator_prompt

    prompt = evaluator_prompt(
        room, preferences, budget, brief, concept, [], spatial, analysis, catalog,
        placement=_placed_layout(),
    )

    contract = prompt.contract
    assert "design intent, not a measured fact" in contract
    assert "unless the placed coordinates below confirm it" in contract
    assert "contradict the concept's spatial wording" in contract
    # Validity must not be presented as proof of concept consistency.
    assert "Geometric validity and concept consistency are separate findings" in (
        contract
    )
    assert "do not claim the arrangement matches the concept" in contract


def test_evaluator_is_told_the_engine_ignores_the_concept_wording(
    room, preferences, budget, brief, concept, catalog, spatial, analysis
) -> None:
    from ai.design_evaluator import build_prompt as evaluator_prompt

    prompt = evaluator_prompt(
        room, preferences, budget, brief, concept, [], spatial, analysis, catalog,
        placement=_placed_layout(),
    )

    assert "placement engine does not read it" in prompt.contract
    assert "own fixed rule set" in prompt.contract


def test_evaluator_bad_output_is_corrected(
    ai_config, fake_completer, room, preferences, budget, brief, concept,
    catalog, spatial, analysis,
) -> None:
    fake_completer.queue("{}", EVALUATION_JSON)
    result = evaluate_design(
        ai_config, room, preferences, budget, brief, concept, [], spatial,
        analysis, catalog, completer=fake_completer,
    )
    assert result.budget_suitability
    assert fake_completer.call_count == 2


# --------------------------------------------------------------------------- #
# Error propagation across all four services
# --------------------------------------------------------------------------- #


def test_authentication_error_propagates_from_brief(
    ai_config, fake_completer, room, preferences, requirements, budget
) -> None:
    fake_completer.queue(
        AIAuthenticationError("The AI provider rejected the credentials.")
    )
    with pytest.raises(AIAuthenticationError):
        analyze_brief(
            ai_config, room, preferences, requirements, budget, completer=fake_completer
        )


def test_authentication_error_propagates_from_concepts(
    ai_config, fake_completer, room, preferences, requirements, budget, brief
) -> None:
    fake_completer.queue(AIAuthenticationError("rejected"))
    with pytest.raises(AIAuthenticationError):
        generate_concepts(
            ai_config, room, preferences, requirements, budget, brief,
            completer=fake_completer,
        )


def test_authentication_error_propagates_from_advisor(
    ai_config, fake_completer, room, preferences, budget, brief, concept, catalog
) -> None:
    fake_completer.queue(AIAuthenticationError("rejected"))
    with pytest.raises(AIAuthenticationError):
        recommend_furniture(
            ai_config, room, preferences, budget, brief, concept, catalog,
            completer=fake_completer,
        )


def test_authentication_error_propagates_from_evaluator(
    ai_config, fake_completer, room, preferences, budget, brief, concept,
    catalog, spatial, analysis,
) -> None:
    fake_completer.queue(AIAuthenticationError("rejected"))
    with pytest.raises(AIAuthenticationError):
        evaluate_design(
            ai_config, room, preferences, budget, brief, concept, [], spatial,
            analysis, catalog, completer=fake_completer,
        )


def test_timeout_propagates_from_brief(
    ai_config, fake_completer, room, preferences, requirements, budget
) -> None:
    fake_completer.queue(AITimeoutError("timed out"))
    with pytest.raises(AITimeoutError):
        analyze_brief(
            ai_config, room, preferences, requirements, budget, completer=fake_completer
        )
    assert fake_completer.call_count == 1


def test_truncation_propagates_from_evaluator(
    ai_config, fake_completer, room, preferences, budget, brief, concept,
    catalog, spatial, analysis,
) -> None:
    fake_completer.queue(AITruncatedResponseError("cut off"))
    with pytest.raises(AITruncatedResponseError):
        evaluate_design(
            ai_config, room, preferences, budget, brief, concept, [], spatial,
            analysis, catalog, completer=fake_completer,
        )


def test_no_service_retries_a_transport_error(
    ai_config, fake_completer, room, preferences, budget, brief, concept, catalog
) -> None:
    fake_completer.queue(AITimeoutError("timed out"))
    with pytest.raises(AITimeoutError):
        recommend_furniture(
            ai_config, room, preferences, budget, brief, concept, catalog,
            completer=fake_completer,
        )
    # One queued error: a second request would raise AssertionError instead.
    assert fake_completer.call_count == 1


# --------------------------------------------------------------------------- #
# Credential containment
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("service", ["brief", "concepts", "advisor", "evaluator"])
def test_no_service_puts_the_key_in_its_prompt(
    service, ai_config, fake_completer, room, preferences, requirements, budget,
    brief, concept, catalog, spatial, analysis,
) -> None:
    answers = {
        "brief": BRIEF_JSON,
        "concepts": CONCEPTS_JSON,
        "advisor": RECOMMENDATION_JSON,
        "evaluator": EVALUATION_JSON,
    }
    fake_completer.queue(answers[service])

    if service == "brief":
        analyze_brief(
            ai_config, room, preferences, requirements, budget,
            completer=fake_completer,
        )
    elif service == "concepts":
        generate_concepts(
            ai_config, room, preferences, requirements, budget, brief,
            completer=fake_completer,
        )
    elif service == "advisor":
        recommend_furniture(
            ai_config, room, preferences, budget, brief, concept, catalog,
            completer=fake_completer,
        )
    else:
        evaluate_design(
            ai_config, room, preferences, budget, brief, concept, [], spatial,
            analysis, catalog, completer=fake_completer,
        )

    assert ai_config.api_key not in fake_completer.prompt_text(0)


def test_service_error_messages_do_not_contain_the_key(
    ai_config, fake_completer, room, preferences, requirements, budget
) -> None:
    fake_completer.queue("not json", "still not json")
    with pytest.raises(AIStructuredOutputError) as excinfo:
        analyze_brief(
            ai_config, room, preferences, requirements, budget, completer=fake_completer
        )
    assert ai_config.api_key not in str(excinfo.value)


# --------------------------------------------------------------------------- #
# Architectural boundaries
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "module_name",
    [
        "ai.prompt",
        "ai.brief_analyzer",
        "ai.concept_generator",
        "ai.design_advisor",
        "ai.design_evaluator",
    ],
)
def test_ai_service_modules_do_not_import_streamlit(module_name: str) -> None:
    import importlib

    module = importlib.import_module(module_name)
    source = module.__file__
    assert source is not None
    with open(source, encoding="utf-8") as handle:
        text = handle.read()
    assert "import streamlit" not in text
    assert "from streamlit" not in text


@pytest.mark.parametrize(
    "module_name",
    [
        "ai.prompt",
        "ai.brief_analyzer",
        "ai.concept_generator",
        "ai.design_advisor",
        "ai.design_evaluator",
    ],
)
def test_ai_service_modules_do_not_read_credentials(module_name: str) -> None:
    import importlib

    module = importlib.import_module(module_name)
    source = module.__file__
    assert source is not None
    with open(source, encoding="utf-8") as handle:
        text = handle.read()
    assert "os.environ" not in text
    assert "DEPLOY_API_KEY" not in text


def test_services_do_not_call_each_other() -> None:
    # Independent operations: the workflow layer composes them, not the AI layer.
    import ai.brief_analyzer as brief_module
    import ai.concept_generator as concept_module
    import ai.design_advisor as advisor_module
    import ai.design_evaluator as evaluator_module

    for module in (brief_module, concept_module, advisor_module, evaluator_module):
        source = module.__file__
        assert source is not None
        with open(source, encoding="utf-8") as handle:
            text = handle.read()
        for other in (
            "brief_analyzer",
            "concept_generator",
            "design_advisor",
            "design_evaluator",
        ):
            # A module may name itself in its docstring, but must not import
            # another service.
            assert f"from ai.{other}" not in text
            assert f"import ai.{other}" not in text
