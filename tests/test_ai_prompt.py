"""Tests for the shared prompt and structured-request layer.

The four AI services all flow through this module, so its guarantees are tested
once, thoroughly, here:

* prompts contain the validated inputs and nothing secret,
* exactly one request is sent when the first answer is good,
* exactly one correction is sent when it is not,
* transport failures are never turned into correction attempts.
"""

from __future__ import annotations

import json

import pytest

from ai.client import AITimeoutError, AITruncatedResponseError, ChatCompletion
from ai.parsing import (
    AICorrectionFailedError,
    AIEmptyResponseError,
    AISchemaValidationError,
)
from ai.prompt import (
    OUTPUT_RULES,
    PromptSpec,
    catalogue_entry,
    items_for_room,
    json_block,
    room_facts,
    run_structured_request,
    system_prompt,
)
from models.schemas import DesignBrief, RoomType

GOOD_BRIEF = json.dumps(
    {
        "summary": "A calm living room with a reading corner.",
        "functional_priorities": ["Seating for four"],
        "constraints": ["One door and one window"],
        "ambiguities": [],
        "warnings": [],
    }
)

SPEC = PromptSpec(
    system="You are a test service.",
    context="INPUT DATA",
    contract="REQUIRED SHAPE",
)


# --------------------------------------------------------------------------- #
# Serialisation
# --------------------------------------------------------------------------- #


def test_json_block_renders_models_as_json() -> None:
    from models.schemas import BudgetInput

    block = json_block(BudgetInput(total_budget="1000.00"))
    assert json.loads(block) == {"total_budget": "1000.00", "currency": "TRY"}


def test_json_block_renders_enums_as_their_values() -> None:
    from models.schemas import DesignPreferences, DesignStyle, PaletteDirection

    block = json_block(
        DesignPreferences(
            style=DesignStyle.JAPANDI, palette=PaletteDirection.WARM_NEUTRAL
        )
    )
    payload = json.loads(block)
    assert payload["style"] == "Japandi"
    assert payload["palette"] == "Warm Neutral"


def test_json_block_renders_decimals_as_strings() -> None:
    # A float would silently round money on the way into the prompt.
    from decimal import Decimal

    assert json.dumps(json_block({"amount": Decimal("1234.50")})) == (
        '"{\\n  \\"amount\\": \\"1234.50\\"\\n}"'
    )


def test_json_block_is_deterministic() -> None:
    payload = {"b": 2, "a": 1}
    assert json_block(payload) == json_block(payload)


def test_json_block_supports_nested_structures() -> None:
    block = json_block({"items": [{"id": "x"}], "meta": {"count": 1}})
    assert json.loads(block)["items"][0]["id"] == "x"


# --------------------------------------------------------------------------- #
# Prompt composition
# --------------------------------------------------------------------------- #


def test_system_prompt_contains_the_shared_rules() -> None:
    prompt = system_prompt("You are a designer.")
    assert "You are a designer." in prompt
    assert OUTPUT_RULES in prompt


def test_shared_rules_forbid_invented_data_and_arithmetic() -> None:
    assert "Never invent" in OUTPUT_RULES
    assert "Never perform arithmetic" in OUTPUT_RULES
    assert "exactly one JSON object" in OUTPUT_RULES


def test_first_attempt_messages_have_a_system_and_user_turn() -> None:
    messages = SPEC.messages()
    assert [m["role"] for m in messages] == ["system", "user"]
    assert "INPUT DATA" in messages[1]["content"]
    assert "REQUIRED SHAPE" in messages[1]["content"]


def test_correction_messages_name_the_reason() -> None:
    error = AIEmptyResponseError("The AI response was empty.")
    messages = SPEC.correction_messages(error)
    assert messages[0]["role"] == "system"
    assert "could not be used" in messages[1]["content"]
    assert "The AI response was empty." in messages[1]["content"]


def test_correction_messages_repeat_the_same_context_and_contract() -> None:
    # The model must repair against the same facts, not start over.
    messages = SPEC.correction_messages(AIEmptyResponseError("empty"))
    content = messages[1]["content"]
    assert "INPUT DATA" in content
    assert "REQUIRED SHAPE" in content


def test_correction_messages_do_not_echo_the_previous_answer() -> None:
    # Echoing untrusted output back into a prompt is both wasteful and risky.
    error = AIEmptyResponseError("The AI response was empty.")
    messages = SPEC.correction_messages(error)
    for message in messages:
        assert "LEAK-CANARY" not in message["content"]


# --------------------------------------------------------------------------- #
# Room facts and catalog views
# --------------------------------------------------------------------------- #


def test_room_facts_come_from_the_model_not_the_llm(room) -> None:
    facts = room_facts(room)
    assert facts["floor_area_sqm"] == round(room.area_sqm, 2)
    assert facts["wall_spans_cm"]["north"] == room.width_cm
    assert facts["wall_spans_cm"]["east"] == room.length_cm
    assert facts["room_type"] == "Living Room"


def test_catalogue_entry_exposes_catalog_values(catalog) -> None:
    item = next(i for i in catalog if i.item_id == "sofa_three_seat")
    entry = catalogue_entry(item)
    assert entry["item_id"] == "sofa_three_seat"
    assert entry["width_cm"] == 220
    assert entry["indicative_unit_cost"] == "18500.00"


def test_items_for_room_filters_by_room_type(catalog) -> None:
    bedroom_items = items_for_room(catalog, RoomType.BEDROOM)
    assert bedroom_items
    assert all(RoomType.BEDROOM in item.supported_room_types for item in bedroom_items)
    assert not any(item.item_id == "dining_table" for item in bedroom_items)


def test_items_for_room_returns_nothing_for_an_unsupported_type(catalog) -> None:
    # Sanity check on the filter itself, not on the catalog contents.
    assert items_for_room(catalog, RoomType.DINING_ROOM)


# --------------------------------------------------------------------------- #
# Request flow: success
# --------------------------------------------------------------------------- #


def test_valid_first_answer_needs_one_request(ai_config, fake_completer) -> None:
    fake_completer.queue(GOOD_BRIEF)
    result = run_structured_request(
        ai_config, SPEC, DesignBrief, max_tokens=100, completer=fake_completer
    )
    assert result.summary.startswith("A calm living room")
    assert fake_completer.call_count == 1


def test_first_request_uses_the_service_token_limit(ai_config, fake_completer) -> None:
    fake_completer.queue(GOOD_BRIEF)
    run_structured_request(
        ai_config, SPEC, DesignBrief, max_tokens=1234, completer=fake_completer
    )
    assert fake_completer.calls[0]["max_tokens"] == 1234


def test_zero_temperature_is_requested(ai_config, fake_completer) -> None:
    fake_completer.queue(GOOD_BRIEF)
    run_structured_request(
        ai_config, SPEC, DesignBrief, max_tokens=100, completer=fake_completer
    )
    assert fake_completer.calls[0]["temperature"] == 0


def test_timeout_is_forwarded(ai_config, fake_completer) -> None:
    fake_completer.queue(GOOD_BRIEF)
    run_structured_request(
        ai_config,
        SPEC,
        DesignBrief,
        max_tokens=100,
        timeout=15,
        completer=fake_completer,
    )
    assert fake_completer.calls[0]["timeout"] == 15


def test_fenced_answer_is_accepted(ai_config, fake_completer) -> None:
    fence = "`" * 3
    fake_completer.queue(f"{fence}json\n{GOOD_BRIEF}\n{fence}")
    result = run_structured_request(
        ai_config, SPEC, DesignBrief, max_tokens=100, completer=fake_completer
    )
    assert result.summary
    assert fake_completer.call_count == 1


# --------------------------------------------------------------------------- #
# Request flow: correction
# --------------------------------------------------------------------------- #


def test_invalid_first_answer_triggers_exactly_one_correction(
    ai_config, fake_completer
) -> None:
    fake_completer.queue(*["not json", GOOD_BRIEF])
    result = run_structured_request(
        ai_config, SPEC, DesignBrief, max_tokens=100, completer=fake_completer
    )
    assert result.summary
    assert fake_completer.call_count == 2


def test_correction_keeps_the_same_token_limit(ai_config, fake_completer) -> None:
    fake_completer.queue(*["not json", GOOD_BRIEF])
    run_structured_request(
        ai_config, SPEC, DesignBrief, max_tokens=999, completer=fake_completer
    )
    assert [call["max_tokens"] for call in fake_completer.calls] == [999, 999]


def test_correction_receives_the_diagnosis(ai_config, fake_completer) -> None:
    fake_completer.queue(*["not json", GOOD_BRIEF])
    run_structured_request(
        ai_config, SPEC, DesignBrief, max_tokens=100, completer=fake_completer
    )
    assert "not valid JSON" in fake_completer.prompt_text(1)


def test_schema_failure_is_also_correctable(ai_config, fake_completer) -> None:
    fake_completer.queue(*['{"summary": 5}', GOOD_BRIEF])
    result = run_structured_request(
        ai_config, SPEC, DesignBrief, max_tokens=100, completer=fake_completer
    )
    assert result.summary
    assert fake_completer.call_count == 2


def test_two_failures_raise_a_correction_error(ai_config, fake_completer) -> None:
    fake_completer.queue(*["not json", "still not json"])
    with pytest.raises(AICorrectionFailedError) as excinfo:
        run_structured_request(
            ai_config, SPEC, DesignBrief, max_tokens=100, completer=fake_completer
        )
    assert fake_completer.call_count == 2
    assert "First problem" in str(excinfo.value)
    assert "Correction problem" in str(excinfo.value)


def test_two_failures_never_loop(ai_config, fake_completer) -> None:
    # Only two queued answers; a third request would raise AssertionError.
    fake_completer.queue(*["not json", "also bad"])
    with pytest.raises(AICorrectionFailedError):
        run_structured_request(
            ai_config, SPEC, DesignBrief, max_tokens=100, completer=fake_completer
        )
    assert fake_completer.call_count == 2


# --------------------------------------------------------------------------- #
# Request flow: transport failures are not corrected
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "transport_error",
    [
        AITimeoutError("The AI provider did not answer within 60 seconds."),
        AITruncatedResponseError("The AI answer was cut off."),
    ],
)
def test_transport_error_is_raised_without_a_correction(
    ai_config, fake_completer, transport_error
) -> None:
    # Retrying a timeout with a second full-price request would repeat the same
    # fault; the caller decides whether to try again.
    fake_completer.queue(transport_error)
    with pytest.raises(type(transport_error)):
        run_structured_request(
            ai_config, SPEC, DesignBrief, max_tokens=100, completer=fake_completer
        )
    assert fake_completer.call_count == 1


def test_correction_transport_failure_is_not_disguised(
    ai_config, fake_completer
) -> None:
    # First answer is unparseable, then the provider times out. The user must be
    # told about the timeout, not about a formatting problem.
    fake_completer.queue(
        "not json", AITimeoutError("The AI provider did not answer.")
    )
    with pytest.raises(AITimeoutError):
        run_structured_request(
            ai_config, SPEC, DesignBrief, max_tokens=100, completer=fake_completer
        )
    assert fake_completer.call_count == 2


def test_correction_truncation_is_not_disguised(ai_config, fake_completer) -> None:
    fake_completer.queue("not json", AITruncatedResponseError("cut off"))
    with pytest.raises(AITruncatedResponseError):
        run_structured_request(
            ai_config, SPEC, DesignBrief, max_tokens=100, completer=fake_completer
        )


# --------------------------------------------------------------------------- #
# Credential safety
# --------------------------------------------------------------------------- #


def test_prompts_contain_no_credential(ai_config, fake_completer, room) -> None:
    # The config carries the key but a prompt is built from domain data only.
    fake_completer.queue(GOOD_BRIEF)
    run_structured_request(
        ai_config, SPEC, DesignBrief, max_tokens=100, completer=fake_completer
    )
    for message in fake_completer.calls[0]["messages"]:  # type: ignore[union-attr]
        assert ai_config.api_key not in message["content"]


def test_prompt_module_does_not_import_streamlit() -> None:
    import ai.prompt as prompt_module

    source = prompt_module.__file__
    assert source is not None
    with open(source, encoding="utf-8") as handle:
        text = handle.read()
    assert "import streamlit" not in text
    assert "from streamlit" not in text


def test_prompt_module_has_no_http_of_its_own() -> None:
    import ai.prompt as prompt_module

    source = prompt_module.__file__
    assert source is not None
    with open(source, encoding="utf-8") as handle:
        text = handle.read()
    # It calls ai.client.complete, but imports no transport of its own.
    for forbidden in ("import urllib", "import requests", "import socket"):
        assert forbidden not in text
    assert "http.client" not in text


def test_prompt_module_reads_no_credentials() -> None:
    import ai.prompt as prompt_module

    source = prompt_module.__file__
    assert source is not None
    with open(source, encoding="utf-8") as handle:
        text = handle.read()
    assert "os.environ" not in text
    assert "DEPLOY_API_KEY" not in text


# --------------------------------------------------------------------------- #
# Schema validation still applies
# --------------------------------------------------------------------------- #


def test_wrong_root_type_after_correction_is_reported(
    ai_config, fake_completer
) -> None:
    fake_completer.queue(*["[]", "[1, 2]"])
    with pytest.raises(AICorrectionFailedError):
        run_structured_request(
            ai_config, SPEC, DesignBrief, max_tokens=100, completer=fake_completer
        )


def test_empty_answers_are_reported(ai_config, fake_completer) -> None:
    fake_completer.queue(*["", "   "])
    with pytest.raises(AICorrectionFailedError):
        run_structured_request(
            ai_config, SPEC, DesignBrief, max_tokens=100, completer=fake_completer
        )


def test_schema_error_detail_reaches_the_caller(ai_config, fake_completer) -> None:
    fake_completer.queue(*['{"summary": 5}', "not json"])
    with pytest.raises(AICorrectionFailedError) as excinfo:
        run_structured_request(
            ai_config, SPEC, DesignBrief, max_tokens=100, completer=fake_completer
        )
    assert isinstance(excinfo.value.first_error, AISchemaValidationError)
    assert "summary" in excinfo.value.original_reason


def test_fake_completer_returns_a_chat_completion(ai_config, fake_completer) -> None:
    fake_completer.queue(GOOD_BRIEF)
    result = fake_completer(
        ai_config, SPEC.messages(), max_tokens=10
    )
    assert isinstance(result, ChatCompletion)
    assert result.finish_reason == "stop"
