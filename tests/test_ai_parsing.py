"""Tests for structured AI output parsing.

No network, no Streamlit, no credential. Every test drives local strings through
the parsers and asserts both what succeeded and how failures are reported.

Two properties are checked repeatedly because they are the point of the module:

* Response text never appears in an error message or a ``detail`` string.
* A failure is never turned into a success, and a correction never erases the
  reason the first attempt failed.
"""

from __future__ import annotations

import json
from dataclasses import fields
from typing import Any

import pytest
from pydantic import BaseModel, Field

from ai.client import AIError
from ai.parsing import (
    AICorrectionFailedError,
    AIEmptyResponseError,
    AIInvalidJSONError,
    AIRootTypeError,
    AISchemaValidationError,
    AIStructuredOutputError,
    FieldIssue,
    ParseOutcome,
    collect_issues,
    describe_json_type,
    parse_json,
    parse_json_with_meta,
    parse_structured,
    parse_with_correction,
    strip_code_fence,
    validate_model,
)
from models.schemas import ConceptCollection, DesignBrief, DesignConcept

FENCE = "```"

#: A marker string planted inside malformed answers. If it shows up in an error
#: message, response content leaked.
SECRET_MARKER = "LEAK-CANARY-9f3a"

BRIEF_JSON = json.dumps({"summary": "A calm reading corner."})


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _concept(name: str) -> dict[str, Any]:
    """One complete concept payload, so tests can vary a single field."""

    return {
        "name": name,
        "description": "Warm, quiet and practical.",
        "design_direction": "Warm Minimalism",
        "color_and_material_direction": "Oak and off-white.",
        "furniture_approach": "Few, low pieces.",
        "functional_rationale": "Leaves a clear walking path.",
        "budget_suitability": "Fits the stated budget.",
    }


def _concepts_json(*names: str) -> str:
    return json.dumps({"concepts": [_concept(name) for name in names]})


def _assert_no_content(text: str) -> None:
    """Fail if any answer content reached a message."""

    assert SECRET_MARKER not in text


# --------------------------------------------------------------------------- #
# Plain JSON
# --------------------------------------------------------------------------- #


def test_plain_json_object_is_parsed() -> None:
    data = parse_json('{"summary": "text"}')
    assert data == {"summary": "text"}


def test_nested_json_object_is_parsed() -> None:
    data = parse_json('{"outer": {"inner": [1, 2, 3]}}')
    assert data["outer"]["inner"] == [1, 2, 3]


def test_surrounding_whitespace_is_ignored() -> None:
    data = parse_json('  \n\t {"summary": "text"} \n ')
    assert data == {"summary": "text"}


def test_plain_json_validates_against_the_model() -> None:
    brief = parse_structured(BRIEF_JSON, DesignBrief)
    assert isinstance(brief, DesignBrief)
    assert brief.summary == "A calm reading corner."


def test_optional_fields_receive_their_defaults() -> None:
    brief = parse_structured(BRIEF_JSON, DesignBrief)
    assert brief.functional_priorities == []
    assert brief.constraints == []
    assert brief.ambiguities == []
    assert brief.warnings == []


def test_exactly_three_concepts_validate() -> None:
    collection = parse_structured(
        _concepts_json("Warm Nook", "Nordic Study", "Soft Industrial"),
        ConceptCollection,
    )
    assert len(collection.concepts) == 3
    assert collection.concepts[0].name == "Warm Nook"


# --------------------------------------------------------------------------- #
# Markdown code fences
# --------------------------------------------------------------------------- #


def test_json_tagged_fence_is_unwrapped() -> None:
    text = f'{FENCE}json\n{{"summary": "text"}}\n{FENCE}'
    payload, used_fence = strip_code_fence(text)
    assert payload == '{"summary": "text"}'
    assert used_fence is True


def test_bare_fence_is_unwrapped() -> None:
    text = f'{FENCE}\n{{"summary": "text"}}\n{FENCE}'
    payload, used_fence = strip_code_fence(text)
    assert payload == '{"summary": "text"}'
    assert used_fence is True


def test_fence_with_crlf_line_endings_is_unwrapped() -> None:
    text = f'{FENCE}json\r\n{{"summary": "text"}}\r\n{FENCE}'
    payload, _ = strip_code_fence(text)
    assert json.loads(payload) == {"summary": "text"}


def test_fence_with_uppercase_tag_is_accepted() -> None:
    text = f'{FENCE}JSON\n{{"summary": "text"}}\n{FENCE}'
    payload, used_fence = strip_code_fence(text)
    assert used_fence is True
    assert json.loads(payload) == {"summary": "text"}


def test_single_line_fence_is_unwrapped() -> None:
    # Models sometimes emit the whole block on one line.
    text = f'{FENCE}{{"summary": "text"}}{FENCE}'
    payload, used_fence = strip_code_fence(text)
    assert payload == '{"summary": "text"}'
    assert used_fence is True


def test_fenced_json_validates_against_the_model() -> None:
    text = f'{FENCE}json\n{BRIEF_JSON}\n{FENCE}'
    brief = parse_structured(text, DesignBrief)
    assert brief.summary == "A calm reading corner."


def test_parse_outcome_reports_fence_usage() -> None:
    fenced = parse_with_correction(f'{FENCE}json\n{BRIEF_JSON}\n{FENCE}', DesignBrief)
    plain = parse_with_correction(BRIEF_JSON, DesignBrief)
    assert fenced.used_code_fence is True
    assert plain.used_code_fence is False


def test_unfenced_payload_reports_no_fence() -> None:
    payload, used_fence = strip_code_fence(BRIEF_JSON)
    assert payload == BRIEF_JSON
    assert used_fence is False


def test_unterminated_fence_is_rejected() -> None:
    text = f'{FENCE}json\n{{"summary": "text"}}'
    with pytest.raises(AIInvalidJSONError) as excinfo:
        strip_code_fence(text)
    assert "never closed" in str(excinfo.value)


def test_text_after_the_closing_fence_is_rejected() -> None:
    text = f'{FENCE}json\n{{"summary": "text"}}\n{FENCE}\nHope this helps!'
    with pytest.raises(AIInvalidJSONError) as excinfo:
        strip_code_fence(text)
    assert "after the closing code fence" in str(excinfo.value)
    # The trailing prose is model output and must not be quoted back.
    assert "Hope this helps" not in str(excinfo.value)


def test_unsupported_language_tag_is_rejected() -> None:
    text = f'{FENCE}python\n{{"summary": "text"}}\n{FENCE}'
    with pytest.raises(AIInvalidJSONError) as excinfo:
        strip_code_fence(text)
    assert "language tag" in str(excinfo.value)
    assert "python" not in str(excinfo.value)


def test_empty_fenced_block_is_an_empty_response() -> None:
    text = f"{FENCE}json\n\n{FENCE}"
    with pytest.raises(AIEmptyResponseError):
        strip_code_fence(text)


def test_whitespace_only_fenced_block_is_an_empty_response() -> None:
    text = f"{FENCE}\n   \n\t\n{FENCE}"
    with pytest.raises(AIEmptyResponseError):
        strip_code_fence(text)


def test_single_line_fence_with_only_a_tag_is_an_empty_response() -> None:
    # Opening and closing fences on one line with nothing between the tag and
    # the close: there is no payload, so this must not be read as JSON "json".
    with pytest.raises(AIEmptyResponseError):
        strip_code_fence(f"{FENCE}json{FENCE}")


def test_single_line_fence_without_a_closing_fence_is_rejected() -> None:
    with pytest.raises(AIInvalidJSONError) as excinfo:
        strip_code_fence(f'{FENCE}{{"summary": "text"}}')
    assert "never closed" in str(excinfo.value)


def test_text_before_the_opening_fence_is_not_silently_skipped() -> None:
    # Without a leading fence the text is treated as the payload, so the prose
    # makes it invalid JSON rather than being quietly discarded.
    text = f'Here is the JSON:\n{FENCE}json\n{{"summary": "text"}}\n{FENCE}'
    with pytest.raises(AIInvalidJSONError):
        parse_json(text)


# --------------------------------------------------------------------------- #
# Empty and non-text content
# --------------------------------------------------------------------------- #


def test_none_is_an_empty_response() -> None:
    with pytest.raises(AIEmptyResponseError):
        parse_json(None)


def test_empty_string_is_an_empty_response() -> None:
    with pytest.raises(AIEmptyResponseError):
        parse_json("")


def test_whitespace_only_string_is_an_empty_response() -> None:
    with pytest.raises(AIEmptyResponseError):
        parse_json("   \n\t  ")


def test_empty_response_has_a_machine_readable_category() -> None:
    with pytest.raises(AIEmptyResponseError) as excinfo:
        parse_json("")
    assert excinfo.value.category == "empty_response"
    assert excinfo.value.retryable is False


@pytest.mark.parametrize("value", [0, 12.5, True, [], {}, b"{}"])
def test_non_text_content_is_an_empty_response(value: object) -> None:
    with pytest.raises(AIEmptyResponseError) as excinfo:
        parse_json(value)  # type: ignore[arg-type]
    assert "not text" in str(excinfo.value)


# --------------------------------------------------------------------------- #
# Broken JSON
# --------------------------------------------------------------------------- #


def test_broken_json_is_rejected() -> None:
    with pytest.raises(AIInvalidJSONError) as excinfo:
        parse_json(f'{{"summary": "{SECRET_MARKER}", ')
    assert "not valid JSON" in str(excinfo.value)
    _assert_no_content(str(excinfo.value))


def test_broken_json_reports_a_position() -> None:
    with pytest.raises(AIInvalidJSONError) as excinfo:
        parse_json('{"summary": "text" "other": 1}')
    message = str(excinfo.value)
    assert "line 1" in message
    assert "column" in message


def test_broken_json_keeps_the_json_error_as_its_cause() -> None:
    with pytest.raises(AIInvalidJSONError) as excinfo:
        parse_json('{"a": }')
    assert isinstance(excinfo.value.__cause__, json.JSONDecodeError)


def test_truncated_json_is_rejected() -> None:
    # What ``finish_reason=length`` would leave behind if it ever got this far.
    with pytest.raises(AIInvalidJSONError):
        parse_json('{"summary": "A calm read')


def test_javascript_literals_are_not_accepted() -> None:
    # ``json.loads`` is strict on purpose; no Python/JS relaxation.
    with pytest.raises(AIInvalidJSONError):
        parse_json("{'summary': 'text'}")


# --------------------------------------------------------------------------- #
# Root type
# --------------------------------------------------------------------------- #


def test_json_array_root_is_rejected() -> None:
    with pytest.raises(AIRootTypeError) as excinfo:
        parse_json('[{"summary": "text"}]')
    assert "array (1 items)" in str(excinfo.value)


def test_json_array_root_names_the_expected_shape() -> None:
    with pytest.raises(AIRootTypeError) as excinfo:
        parse_json("[]")
    assert "not a JSON object" in str(excinfo.value)


def test_json_string_root_is_rejected() -> None:
    with pytest.raises(AIRootTypeError):
        parse_json('"just a string"')


def test_json_number_root_is_rejected() -> None:
    with pytest.raises(AIRootTypeError):
        parse_json("42")


def test_json_boolean_root_is_rejected() -> None:
    # ``bool`` is a subclass of ``int``; the check must not mistake it for one.
    with pytest.raises(AIRootTypeError) as excinfo:
        parse_json("true")
    assert "boolean" in str(excinfo.value)


def test_json_null_root_is_rejected() -> None:
    with pytest.raises(AIRootTypeError) as excinfo:
        parse_json("null")
    assert "null" in str(excinfo.value)


def test_root_type_error_has_a_machine_readable_category() -> None:
    with pytest.raises(AIRootTypeError) as excinfo:
        parse_json("[]")
    assert excinfo.value.category == "unexpected_root_type"


def test_validate_model_checks_the_root_type_before_pydantic() -> None:
    with pytest.raises(AIRootTypeError):
        validate_model(["not", "an", "object"], DesignBrief)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "null"),
        (True, "a boolean"),
        (7, "a number"),
        (1.5, "a number"),
        ("abc", "a string (3 characters)"),
        ([1, 2], "an array (2 items)"),
        ({"a": 1}, "an object (1 keys)"),
    ],
)
def test_describe_json_type_names_the_shape(value: object, expected: str) -> None:
    assert describe_json_type(value) == expected


def test_describe_json_type_does_not_reveal_the_value() -> None:
    assert SECRET_MARKER not in describe_json_type(SECRET_MARKER)


# --------------------------------------------------------------------------- #
# Schema validation
# --------------------------------------------------------------------------- #


def test_missing_required_field_is_reported() -> None:
    with pytest.raises(AISchemaValidationError) as excinfo:
        parse_structured("{}", DesignBrief)
    error = excinfo.value
    assert error.model_name == "DesignBrief"
    assert error.category == "schema_validation_error"
    missing = [issue for issue in error.issues if issue.issue_type == "missing"]
    assert len(missing) == 1
    assert missing[0].location == "summary"
    assert "required" in missing[0].summary


def test_wrong_data_type_is_reported() -> None:
    with pytest.raises(AISchemaValidationError) as excinfo:
        parse_structured('{"summary": 42}', DesignBrief)
    issue = excinfo.value.issues[0]
    assert issue.location == "summary"
    assert issue.issue_type == "string_type"
    assert "text" in issue.summary


def test_wrong_list_element_type_is_reported() -> None:
    payload = json.dumps({"summary": "ok", "constraints": [1, 2]})
    with pytest.raises(AISchemaValidationError) as excinfo:
        parse_structured(payload, DesignBrief)
    locations = {issue.location for issue in excinfo.value.issues}
    assert "constraints[0]" in locations


def test_unexpected_field_is_rejected() -> None:
    payload = json.dumps({"summary": "ok", "invented_field": "x"})
    with pytest.raises(AISchemaValidationError) as excinfo:
        parse_structured(payload, DesignBrief)
    issue = excinfo.value.issues[0]
    assert issue.issue_type == "extra_forbidden"
    assert "unexpected field" in issue.summary


def test_unexpected_field_name_is_not_quoted() -> None:
    # The key is model output; naming it would copy response text into a log.
    payload = json.dumps({"summary": "ok", SECRET_MARKER: "x"})
    with pytest.raises(AISchemaValidationError) as excinfo:
        parse_structured(payload, DesignBrief)
    _assert_no_content(str(excinfo.value))
    _assert_no_content(str(excinfo.value.detail or ""))
    for issue in excinfo.value.issues:
        _assert_no_content(issue.location)
        _assert_no_content(issue.message)
        _assert_no_content(issue.summary)


def test_enum_violation_is_reported() -> None:
    # ``design_direction`` is free text, so the constrained field here is the
    # rotation angle of a furniture recommendation.
    from models.schemas import FurnitureRecommendation

    with pytest.raises(AISchemaValidationError) as excinfo:
        parse_structured(
            json.dumps({"item_id": "sofa-01", "rotation_degrees": 45}),
            FurnitureRecommendation,
        )
    issue = excinfo.value.issues[0]
    assert issue.location == "rotation_degrees"
    assert "allowed values" in issue.summary
    assert "45" not in issue.summary


def test_too_few_concepts_is_reported() -> None:
    with pytest.raises(AISchemaValidationError) as excinfo:
        parse_structured(_concepts_json("Only One"), ConceptCollection)
    issue = excinfo.value.issues[0]
    assert issue.location == "concepts"
    assert "too few" in issue.summary


def test_too_many_concepts_is_reported() -> None:
    text = _concepts_json("One", "Two", "Three", "Four")
    with pytest.raises(AISchemaValidationError) as excinfo:
        parse_structured(text, ConceptCollection)
    assert "too many" in excinfo.value.issues[0].summary


def test_duplicate_concept_names_are_reported() -> None:
    text = _concepts_json("Same Name", "Same Name", "Other")
    with pytest.raises(AISchemaValidationError) as excinfo:
        parse_structured(text, ConceptCollection)
    messages = " ".join(issue.message for issue in excinfo.value.issues)
    assert "distinct" in messages


def test_blank_string_violates_the_minimum_length() -> None:
    # ``str_strip_whitespace`` trims first, so an all-space summary is empty.
    with pytest.raises(AISchemaValidationError) as excinfo:
        parse_structured('{"summary": "   "}', DesignBrief)
    assert excinfo.value.issues[0].location == "summary"


def test_overlong_text_is_reported() -> None:
    with pytest.raises(AISchemaValidationError) as excinfo:
        parse_structured(json.dumps({"summary": "x" * 2001}), DesignBrief)
    assert "too long" in excinfo.value.issues[0].summary


def test_schema_error_summary_lists_issues() -> None:
    with pytest.raises(AISchemaValidationError) as excinfo:
        parse_structured("{}", DesignBrief)
    summary = excinfo.value.user_message
    assert "DesignBrief" in summary
    assert "summary" in summary


def test_schema_error_summary_is_capped() -> None:
    # Six unknown fields would otherwise produce a wall of text.
    payload = {f"junk_{index}": index for index in range(6)}
    payload["summary"] = "ok"
    with pytest.raises(AISchemaValidationError) as excinfo:
        parse_structured(json.dumps(payload), DesignBrief)
    assert len(excinfo.value.issues) == 6
    assert "more" in excinfo.value.user_message


def test_schema_error_keeps_the_pydantic_error_as_its_cause() -> None:
    from pydantic import ValidationError

    with pytest.raises(AISchemaValidationError) as excinfo:
        parse_structured("{}", DesignBrief)
    assert isinstance(excinfo.value.__cause__, ValidationError)


def test_issues_do_not_carry_the_offending_input() -> None:
    # ``FieldIssue`` has exactly three fields; Pydantic's ``input`` is dropped.
    with pytest.raises(AISchemaValidationError) as excinfo:
        parse_structured(
            json.dumps({"summary": "ok", "constraints": [SECRET_MARKER, 5]}),
            DesignBrief,
        )
    for issue in excinfo.value.issues:
        _assert_no_content(issue.location)
        _assert_no_content(issue.message)
        assert [f.name for f in fields(FieldIssue)] == [
            "location",
            "issue_type",
            "message",
        ]


def test_collect_issues_formats_nested_locations() -> None:
    from pydantic import ValidationError

    try:
        DesignBrief.model_validate(
            {"summary": "ok", "constraints": [SECRET_MARKER, 5]}
        )
    except ValidationError as exc:
        issues = collect_issues(exc)
    else:  # pragma: no cover - the payload is invalid by construction
        pytest.fail("Expected a ValidationError.")

    assert issues[0].location == "constraints[1]"
    assert isinstance(issues[0], FieldIssue)
    _assert_no_content(issues[0].summary)


def test_issue_summary_formats_root_location() -> None:
    issue = FieldIssue(location="(root)", issue_type="missing", message="required")
    assert issue.summary == "is required but was not provided"


def test_unknown_issue_type_falls_back_to_pydantic_text() -> None:
    issue = FieldIssue(location="summary", issue_type="made_up", message="is odd")
    assert "is odd" in issue.summary


def test_validation_error_subclasses_the_ai_error_base() -> None:
    with pytest.raises(AIError):
        parse_structured("{}", DesignBrief)


def test_all_parsing_errors_share_one_base() -> None:
    for error in (
        AIEmptyResponseError("x"),
        AIInvalidJSONError("x"),
        AIRootTypeError("x"),
    ):
        assert isinstance(error, AIStructuredOutputError)
        assert isinstance(error, AIError)


# --------------------------------------------------------------------------- #
# parse_with_correction: first attempt succeeds
# --------------------------------------------------------------------------- #


def test_first_attempt_success_reports_one_attempt() -> None:
    outcome = parse_with_correction(BRIEF_JSON, DesignBrief)
    assert isinstance(outcome, ParseOutcome)
    assert outcome.attempts == 1
    assert outcome.corrected is False
    assert outcome.first_error is None
    assert outcome.value.summary == "A calm reading corner."


def test_first_attempt_success_does_not_call_the_corrector() -> None:
    calls: list[AIStructuredOutputError] = []

    def corrector(error: AIStructuredOutputError) -> str:
        calls.append(error)
        return BRIEF_JSON

    parse_with_correction(BRIEF_JSON, DesignBrief, corrector=corrector)
    assert calls == []


# --------------------------------------------------------------------------- #
# parse_with_correction: the correction is used exactly once
# --------------------------------------------------------------------------- #


def test_correction_success_reports_two_attempts() -> None:
    calls: list[AIStructuredOutputError] = []

    def corrector(error: AIStructuredOutputError) -> str:
        calls.append(error)
        return BRIEF_JSON

    outcome = parse_with_correction('{"summary": ', DesignBrief, corrector=corrector)
    assert outcome.attempts == 2
    assert outcome.corrected is True
    assert outcome.value.summary == "A calm reading corner."
    assert len(calls) == 1


def test_correction_receives_the_original_error() -> None:
    seen: list[AIStructuredOutputError] = []

    def corrector(error: AIStructuredOutputError) -> str:
        seen.append(error)
        return BRIEF_JSON

    parse_with_correction("not json at all", DesignBrief, corrector=corrector)
    assert len(seen) == 1
    assert isinstance(seen[0], AIInvalidJSONError)


def test_correction_records_the_first_error_on_the_outcome() -> None:
    def corrector(error: AIStructuredOutputError) -> str:
        return BRIEF_JSON

    outcome = parse_with_correction("nope", DesignBrief, corrector=corrector)
    assert outcome.first_error is not None
    assert isinstance(outcome.first_error, AIInvalidJSONError)


def test_correction_fixing_a_missing_field_succeeds() -> None:
    def corrector(error: AIStructuredOutputError) -> str:
        return BRIEF_JSON

    outcome = parse_with_correction("{}", DesignBrief, corrector=corrector)
    assert outcome.value.summary == "A calm reading corner."


def test_correction_returning_fenced_json_succeeds() -> None:
    def corrector(error: AIStructuredOutputError) -> str:
        return f'{FENCE}json\n{BRIEF_JSON}\n{FENCE}'

    outcome = parse_with_correction("{}", DesignBrief, corrector=corrector)
    assert outcome.corrected is True
    assert outcome.used_code_fence is True


def test_correction_is_not_retried_when_it_also_fails() -> None:
    calls: list[AIStructuredOutputError] = []

    def corrector(error: AIStructuredOutputError) -> str:
        calls.append(error)
        return "still not json"

    with pytest.raises(AICorrectionFailedError):
        parse_with_correction("not json", DesignBrief, corrector=corrector)
    assert len(calls) == 1


def test_exactly_one_correction_is_permitted() -> None:
    # A corrector that keeps returning rubbish must be called once, not looped.
    calls = 0

    def corrector(error: AIStructuredOutputError) -> str:
        nonlocal calls
        calls += 1
        return "{"

    with pytest.raises(AICorrectionFailedError):
        parse_with_correction("{", DesignBrief, corrector=corrector)
    assert calls == 1


# --------------------------------------------------------------------------- #
# parse_with_correction: failures preserve the original reason
# --------------------------------------------------------------------------- #


def test_no_corrector_raises_the_original_error() -> None:
    with pytest.raises(AIInvalidJSONError) as excinfo:
        parse_with_correction("not json", DesignBrief)
    assert excinfo.value.category == "invalid_json"


def test_no_corrector_does_not_wrap_the_error() -> None:
    with pytest.raises(AIStructuredOutputError) as excinfo:
        parse_with_correction("[]", DesignBrief)
    assert not isinstance(excinfo.value, AICorrectionFailedError)
    assert isinstance(excinfo.value, AIRootTypeError)


def test_corrector_returning_none_preserves_the_original_error() -> None:
    def corrector(error: AIStructuredOutputError) -> None:
        return None

    with pytest.raises(AICorrectionFailedError) as excinfo:
        parse_with_correction("not json", DesignBrief, corrector=corrector)
    error = excinfo.value
    assert isinstance(error.first_error, AIInvalidJSONError)
    assert "First problem" in str(error)
    assert error.original_reason == str(error.first_error)
    assert error.correction_error is None


def test_corrector_returning_invalid_json_preserves_the_original_error() -> None:
    def corrector(error: AIStructuredOutputError) -> str:
        return "also broken"

    with pytest.raises(AICorrectionFailedError) as excinfo:
        parse_with_correction("not json", DesignBrief, corrector=corrector)
    error = excinfo.value
    assert isinstance(error.first_error, AIInvalidJSONError)
    assert isinstance(error.correction_error, AIInvalidJSONError)
    # Both reasons are visible, and the original is a distinct object rather
    # than being replaced by the correction's error.
    assert "First problem" in str(error)
    assert "Correction problem" in str(error)
    assert error.first_error is not error.correction_error
    assert "not valid JSON" in error.original_reason


def test_corrector_returning_a_schema_invalid_object_preserves_both_reasons() -> None:
    def corrector(error: AIStructuredOutputError) -> str:
        return '{"summary": 5}'

    with pytest.raises(AICorrectionFailedError) as excinfo:
        parse_with_correction("{}", DesignBrief, corrector=corrector)
    error = excinfo.value
    assert isinstance(error.first_error, AISchemaValidationError)
    assert isinstance(error.correction_error, AISchemaValidationError)
    # Field-level detail from the first attempt survives into the raised message.
    assert "summary" in error.original_reason
    assert "summary" in str(error)


def test_corrector_raising_an_ai_error_preserves_both_reasons() -> None:
    def corrector(error: AIStructuredOutputError) -> str:
        raise AIInvalidJSONError("the repair request itself failed")

    with pytest.raises(AICorrectionFailedError) as excinfo:
        parse_with_correction("not json", DesignBrief, corrector=corrector)
    error = excinfo.value
    assert isinstance(error.first_error, AIInvalidJSONError)
    assert isinstance(error.correction_error, AIInvalidJSONError)
    assert "repair request itself failed" in str(error)


def test_corrector_raising_a_transport_error_keeps_it_visible() -> None:
    # A timeout during the correction is not a formatting failure. Wrapping it
    # in AICorrectionFailedError would report a network fault as a bad answer.
    from ai.client import AITimeoutError

    def corrector(error: AIStructuredOutputError) -> str:
        raise AITimeoutError("The AI provider did not answer within 60 seconds.")

    with pytest.raises(AITimeoutError):
        parse_with_correction("not json", DesignBrief, corrector=corrector)


def test_corrector_raising_a_truncation_error_keeps_it_visible() -> None:
    from ai.client import AITruncatedResponseError

    def corrector(error: AIStructuredOutputError) -> str:
        raise AITruncatedResponseError("The AI answer was cut off.")

    with pytest.raises(AITruncatedResponseError):
        parse_with_correction("not json", DesignBrief, corrector=corrector)


def test_corrector_raising_an_ordinary_exception_preserves_the_original_error() -> None:
    def corrector(error: AIStructuredOutputError) -> str:
        raise TimeoutError("the network gave up")

    with pytest.raises(AICorrectionFailedError) as excinfo:
        parse_with_correction("not json", DesignBrief, corrector=corrector)
    error = excinfo.value
    assert isinstance(error.first_error, AIInvalidJSONError)
    assert isinstance(error.correction_error, TimeoutError)
    assert "First problem" in str(error)
    # The exception type is named; its text is not copied blindly.
    assert "TimeoutError" in str(error.detail or "")


def test_correction_failure_keeps_the_cause_chain() -> None:
    def corrector(error: AIStructuredOutputError) -> str:
        return "still broken"

    with pytest.raises(AICorrectionFailedError) as excinfo:
        parse_with_correction("not json", DesignBrief, corrector=corrector)
    assert isinstance(excinfo.value.__cause__, AIStructuredOutputError)


def test_correction_failure_is_machine_readable() -> None:
    def corrector(error: AIStructuredOutputError) -> str:
        return None

    with pytest.raises(AICorrectionFailedError) as excinfo:
        parse_with_correction("not json", DesignBrief, corrector=corrector)
    assert excinfo.value.category == "correction_failed"


def test_correction_failure_subclasses_the_ai_error_base() -> None:
    def corrector(error: AIStructuredOutputError) -> str:
        return None

    with pytest.raises(AIError):
        parse_with_correction("not json", DesignBrief, corrector=corrector)


# --------------------------------------------------------------------------- #
# Correction failure must not leak provider content
# --------------------------------------------------------------------------- #


def test_correction_failure_does_not_leak_the_first_response() -> None:
    def corrector(error: AIStructuredOutputError) -> str:
        return None

    with pytest.raises(AICorrectionFailedError) as excinfo:
        parse_with_correction(
            f'{{"{SECRET_MARKER}": ', DesignBrief, corrector=corrector
        )
    _assert_no_content(str(excinfo.value))
    _assert_no_content(str(excinfo.value.detail or ""))
    _assert_no_content(excinfo.value.original_reason)


def test_correction_failure_does_not_leak_the_replacement_response() -> None:
    def corrector(error: AIStructuredOutputError) -> str:
        return f"still {SECRET_MARKER} broken"

    with pytest.raises(AICorrectionFailedError) as excinfo:
        parse_with_correction("not json", DesignBrief, corrector=corrector)
    _assert_no_content(str(excinfo.value))
    _assert_no_content(str(excinfo.value.detail or ""))


def test_schema_failure_does_not_leak_values() -> None:
    payload = json.dumps({"summary": 12345, "constraints": [SECRET_MARKER]})
    with pytest.raises(AIStructuredOutputError) as excinfo:
        parse_with_correction(payload, DesignBrief)
    _assert_no_content(str(excinfo.value))
    _assert_no_content(str(excinfo.value.detail or ""))


@pytest.mark.parametrize(
    "payload",
    [
        f'{{"summary": "{SECRET_MARKER}", ',
        f"[{SECRET_MARKER}]",
        f"{FENCE}yaml\n{SECRET_MARKER}\n{FENCE}",
        f"{FENCE}json\n{SECRET_MARKER}\n{FENCE}\nafter",
    ],
)
def test_every_error_path_keeps_content_out_of_the_message(payload: str) -> None:
    with pytest.raises(AIStructuredOutputError) as excinfo:
        parse_json(payload)
    _assert_no_content(str(excinfo.value))
    _assert_no_content(str(excinfo.value.detail or ""))


@pytest.mark.parametrize(
    "payload",
    [
        json.dumps({"summary": SECRET_MARKER, "constraints": [SECRET_MARKER, 1]}),
        json.dumps({"summary": 7}),
        json.dumps({SECRET_MARKER: SECRET_MARKER}),
        json.dumps({"summary": "ok", "constraints": "x"}),
        json.dumps({"summary": "x" * 3000}),
    ],
)
def test_every_schema_error_keeps_content_out_of_the_message(payload: str) -> None:
    with pytest.raises(AIStructuredOutputError) as excinfo:
        parse_structured(payload, DesignBrief)
    error = excinfo.value
    _assert_no_content(str(error))
    _assert_no_content(str(error.detail or ""))
    _assert_no_content(error.original_reason)
    for issue in getattr(error, "issues", ()):
        _assert_no_content(issue.location)
        _assert_no_content(issue.summary)
        _assert_no_content(issue.user_message)


# --------------------------------------------------------------------------- #
# Module boundaries
# --------------------------------------------------------------------------- #


def test_parsing_module_does_not_import_streamlit() -> None:
    import ai.parsing as parsing_module

    source = parsing_module.__file__
    assert source is not None
    with open(source, encoding="utf-8") as handle:
        text = handle.read()
    assert "import streamlit" not in text
    assert "from streamlit" not in text


def test_parsing_module_performs_no_http() -> None:
    import ai.parsing as parsing_module

    source = parsing_module.__file__
    assert source is not None
    with open(source, encoding="utf-8") as handle:
        text = handle.read()
    for forbidden in ("urllib", "requests", "http.client", "socket"):
        assert forbidden not in text


def test_parsing_module_reads_no_credentials() -> None:
    import ai.parsing as parsing_module

    source = parsing_module.__file__
    assert source is not None
    with open(source, encoding="utf-8") as handle:
        text = handle.read()
    assert "api_key" not in text
    assert "DEPLOY_API_KEY" not in text
    assert "os.environ" not in text


def test_parse_json_with_meta_is_the_only_fence_reporting_entry_point() -> None:
    data, used_fence = parse_json_with_meta(f'{FENCE}json\n{BRIEF_JSON}\n{FENCE}')
    assert data["summary"] == "A calm reading corner."
    assert used_fence is True


def test_local_model_is_validated_like_a_domain_model() -> None:
    # The parser is model-agnostic, which is what lets the four AI functions
    # share it without the parsing layer knowing their schemas.
    class Local(BaseModel):
        count: int = Field(ge=1)

    assert validate_model({"count": 3}, Local).count == 3
    with pytest.raises(AISchemaValidationError) as excinfo:
        validate_model({"count": 0}, Local)
    assert "minimum" in excinfo.value.issues[0].summary


def test_domain_concept_model_round_trips() -> None:
    text = json.dumps(_concept("Reading Nook"))
    concept = parse_structured(text, DesignConcept)
    assert concept.name == "Reading Nook"
    assert concept.design_direction == "Warm Minimalism"
