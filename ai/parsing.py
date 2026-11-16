"""Structured AI output parsing.

The provider returns a chat message whose text is *supposed* to be JSON. This
module turns that text into a validated Pydantic model, and it does so
defensively: the text is untrusted input.

What this module does:

* Parses JSON with ``json.loads``.
* Accepts a single Markdown code fence around the payload, which models
  frequently add even when asked for bare JSON. Anything outside the fence must
  be whitespace, so a chatty answer is rejected rather than half-read.
* Checks the root type before validation, because "expected an object, got an
  array" is a clearer diagnosis than a schema error.
* Validates with the supplied Pydantic model.
* Reports problems twice over: a short, plain-language summary for the user and
  a structured list of field issues for the developer.
* Offers a helper that permits exactly one correction attempt, without this
  module ever making an API call.

What this module does not do:

* No HTTP, no Streamlit, no credential access, no retry loop.
* No silent repair. A malformed answer is never coerced into a valid one, and a
  failed correction keeps the original cause visible.

Response text is never copied into an error message. Messages describe the shape
of the problem ("expected a string, got a number") rather than echoing content,
so a provider that pads its output — or leaks something into it — cannot push
that text into logs or the interface.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Generic, TypeVar

from pydantic import BaseModel, ValidationError

from ai.client import AIError

#: Type variable for the Pydantic model a caller expects back. Declared here so
#: every annotation below can refer to it.
ModelT = TypeVar("ModelT", bound=BaseModel)

#: Maximum number of field issues quoted in the user-facing summary.
_MAX_SUMMARY_ISSUES = 5

#: Fence markers accepted around the JSON payload.
_FENCE = "```"


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #


class AIStructuredOutputError(AIError):
    """The AI answer could not be turned into a validated model.

    Subclasses :class:`ai.client.AIError` so the application can catch every AI
    failure in one place. ``category`` stays machine-readable for the interface.
    """

    category = "structured_output_error"

    @property
    def original_reason(self) -> str:
        """A full diagnosis, safe to keep after this error stops being raised.

        Subclasses that carry structured detail (field issues) override this to
        include it, so a preserved error still explains what went wrong.
        """

        return str(self)


class AIEmptyResponseError(AIStructuredOutputError):
    """The answer was missing, blank, or contained nothing after the fence."""

    category = "empty_response"


class AIInvalidJSONError(AIStructuredOutputError):
    """The answer was not valid JSON."""

    category = "invalid_json"


class AIRootTypeError(AIStructuredOutputError):
    """The JSON was valid but the wrong kind of value at the root."""

    category = "unexpected_root_type"


class AISchemaValidationError(AIStructuredOutputError):
    """The JSON did not satisfy the expected Pydantic model.

    ``issues`` holds one :class:`FieldIssue` per problem, suitable for a
    developer log. The message itself is the user-facing summary, so ``str()``,
    ``user_message`` and what an interface shows all agree.
    """

    category = "schema_validation_error"

    def __init__(
        self,
        *,
        model_name: str,
        issues: tuple[FieldIssue, ...],
        detail: str | None = None,
    ) -> None:
        self.model_name = model_name
        self.issues = issues
        super().__init__(self._compose(model_name, issues), detail=detail)

    @property
    def user_message(self) -> str:
        """A short explanation that names no provider content."""

        return self.message

    @property
    def original_reason(self) -> str:
        """The full reason, identical to the message."""

        return self.message

    @staticmethod
    def _compose(model_name: str, issues: tuple[FieldIssue, ...]) -> str:
        if not issues:
            return f"The AI response did not match the expected {model_name}."

        shown = issues[:_MAX_SUMMARY_ISSUES]
        listed = "; ".join(issue.summary for issue in shown)
        remaining = len(issues) - len(shown)
        suffix = f" (and {remaining} more)" if remaining > 0 else ""
        return (
            f"The AI response did not match the expected {model_name}: "
            f"{listed}{suffix}"
        )


class AICorrectionFailedError(AIStructuredOutputError):
    """A correction attempt was made and it also failed.

    The original failure is preserved on ``first_error`` and restated in the
    message, so the first reason is never lost behind the second.
    """

    category = "correction_failed"

    def __init__(
        self,
        message: str,
        *,
        first_error: AIStructuredOutputError,
        correction_error: Exception | None,
        detail: str | None = None,
    ) -> None:
        super().__init__(message, detail=detail)
        self.first_error = first_error
        self.correction_error = correction_error

    @property
    def original_reason(self) -> str:
        """The first attempt's full reason, still readable after correction."""

        return self.first_error.original_reason


@dataclass(frozen=True)
class FieldIssue:
    """One schema problem.

    ``message`` is the raw Pydantic text and is meant for logs: it is precise
    and stable. ``user_message`` rewrites the common cases into plain language
    for the interface. Neither ever quotes the response.
    """

    location: str
    issue_type: str
    message: str

    @property
    def user_message(self) -> str:
        """A plain-language restatement of the problem."""

        return _PLAIN_MESSAGES.get(self.issue_type, self.message)

    @property
    def summary(self) -> str:
        """A compact line for the user-facing message."""

        if self.location == "(root)":
            return self.user_message
        return f"{self.location} {self.user_message}"


#: Wording for a field the model does not define. Shared by the message and the
#: plain-language map so the two cannot drift apart.
_UNEXPECTED_FIELD = "contains an unexpected field"

#: Plain-language wording for the Pydantic error types a caller is likely to
#: see. Anything absent falls back to Pydantic's own text, which is still
#: accurate but more technical.
_PLAIN_MESSAGES: dict[str, str] = {
    "missing": "is required but was not provided",
    "string_type": "should be text",
    "string_too_short": "is too short",
    "string_too_long": "is too long",
    "int_type": "should be a whole number",
    "int_parsing": "should be a whole number",
    "float_type": "should be a number",
    "float_parsing": "should be a number",
    "bool_type": "should be true or false",
    "bool_parsing": "should be true or false",
    "list_type": "should be a list",
    "dict_type": "should be a JSON object",
    "decimal_type": "should be an amount",
    "decimal_parsing": "should be a valid amount",
    "decimal_max_places": "has too many decimal places",
    "extra_forbidden": _UNEXPECTED_FIELD,
    "too_short": "has too few items",
    "too_long": "has too many items",
    "literal_error": "is not one of the allowed values",
    "enum": "is not one of the allowed values",
    "greater_than": "is below the allowed minimum",
    "greater_than_equal": "is below the allowed minimum",
    "less_than": "is above the allowed maximum",
    "less_than_equal": "is above the allowed maximum",
}

#: Longest location string kept. A hostile key name must not bloat a message.
_MAX_LOCATION_LENGTH = 80


# --------------------------------------------------------------------------- #
# Code fences
# --------------------------------------------------------------------------- #


def _empty_block_error() -> AIEmptyResponseError:
    return AIEmptyResponseError("The AI response contained an empty code block.")


def _unclosed_fence_error() -> AIInvalidJSONError:
    return AIInvalidJSONError(
        "The AI response opened a Markdown code fence but never closed it."
    )


def strip_code_fence(text: str) -> tuple[str, bool]:
    """Remove a single surrounding Markdown fence.

    Returns the payload and whether a fence was removed. Only a fence that wraps
    the entire answer is accepted: text before or after it means the model
    answered conversationally, and guessing which braces were meant is exactly
    the kind of silent repair this module avoids.

    Both layouts are supported: the usual multi-line block and a compact
    single-line form such as ````` ```{"a": 1}``` `````.

    Raises
    ------
    AIEmptyResponseError
        The fence was closed but contained nothing.
    AIInvalidJSONError
        The fence was never closed, carried an unsupported language tag, or was
        followed by other text.
    """

    stripped = text.strip()
    if not stripped.startswith(_FENCE):
        return stripped, False

    # Drop the opening fence and an optional language tag on the same line.
    remainder = stripped[len(_FENCE) :]
    newline_at = remainder.find("\n")

    if newline_at == -1:
        # Everything sits on one line, so the closing fence must be the last
        # thing in the answer.
        if not remainder.endswith(_FENCE):
            raise _unclosed_fence_error()
        payload = remainder[: -len(_FENCE)].strip()
        if not payload or payload.lower() == "json":
            raise _empty_block_error()
        return payload, True

    language_tag = remainder[:newline_at].strip().lower()
    if language_tag not in {"", "json"}:
        # The tag is model output, so it is described rather than quoted.
        raise AIInvalidJSONError(
            "The AI response used an unsupported code fence language tag; only "
            "a bare fence or the json tag is accepted."
        )

    body = remainder[newline_at + 1 :]
    closing_at = body.rfind(_FENCE)
    if closing_at == -1:
        raise _unclosed_fence_error()

    trailing = body[closing_at + len(_FENCE) :].strip()
    if trailing:
        raise AIInvalidJSONError(
            "The AI response contained text after the closing code fence."
        )

    payload = body[:closing_at].strip()
    if not payload:
        raise _empty_block_error()

    return payload, True


# --------------------------------------------------------------------------- #
# Root type helpers
# --------------------------------------------------------------------------- #


def describe_json_type(value: Any) -> str:
    """Name a JSON value's type without revealing the value."""

    if value is None:
        return "null"
    if isinstance(value, bool):
        return "a boolean"
    if isinstance(value, (int, float)):
        return "a number"
    if isinstance(value, str):
        return f"a string ({len(value)} characters)"
    if isinstance(value, list):
        return f"an array ({len(value)} items)"
    if isinstance(value, dict):
        return f"an object ({len(value)} keys)"
    return f"a {type(value).__name__}"


# --------------------------------------------------------------------------- #
# JSON parsing
# --------------------------------------------------------------------------- #


def parse_json_with_meta(text: str | None) -> tuple[dict[str, Any], bool]:
    """Parse a JSON object and report whether a code fence was removed.

    Split out so :func:`parse_with_correction` can record fence usage without
    stripping the text twice.

    Raises
    ------
    AIEmptyResponseError
        When the text is missing or blank, or the code block is empty.
    AIInvalidJSONError
        When the payload is not valid JSON, or is wrapped in a fence that also
        contains other text.
    AIRootTypeError
        When the JSON root is not an object.
    """

    if text is None:
        raise AIEmptyResponseError("The AI response was empty.")

    if not isinstance(text, str):
        raise AIEmptyResponseError(
            "The AI response was not text, so it could not be read as JSON."
        )

    if not text.strip():
        raise AIEmptyResponseError("The AI response was empty.")

    payload, used_fence = strip_code_fence(text)

    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        # Report only the mechanical fault. Quoting the payload here would put
        # provider content into the message.
        raised = AIInvalidJSONError(
            "The AI response was not valid JSON "
            f"(line {exc.lineno}, column {exc.colno}: {exc.msg})."
        )
        raise raised from exc

    if not isinstance(data, dict):
        raise AIRootTypeError(
            "The AI response was not a JSON object; "
            f"received {describe_json_type(data)}."
        )

    return data, used_fence


def parse_json(text: str | None) -> dict[str, Any]:
    """Parse a JSON object from an AI answer.

    Raises
    ------
    AIEmptyResponseError
        When the text is missing or blank, or the code block is empty.
    AIInvalidJSONError
        When the payload is not valid JSON, or is wrapped in a fence that also
        contains other text.
    AIRootTypeError
        When the JSON root is not an object.
    """

    data, _ = parse_json_with_meta(text)
    return data


# --------------------------------------------------------------------------- #
# Schema validation
# --------------------------------------------------------------------------- #


def _format_location(location: tuple[Any, ...]) -> str:
    """Render a Pydantic location as ``field[0].name``.

    Location parts come from the response's own keys, so the rendered string is
    clamped. A pathologically long key cannot inflate a message.
    """

    if not location:
        return "(root)"

    rendered = ""
    for part in location:
        if isinstance(part, int):
            rendered += f"[{part}]"
        elif isinstance(part, str):
            rendered += f".{part}" if rendered else part
        else:  # pragma: no cover - Pydantic emits str/int locations
            rendered += f".{part}"

    rendered = rendered or "(root)"
    if len(rendered) > _MAX_LOCATION_LENGTH:
        rendered = rendered[: _MAX_LOCATION_LENGTH - 3] + "..."
    return rendered


def _issue_from_error(error: dict[str, Any]) -> FieldIssue:
    """Convert one Pydantic error dict into a content-free issue.

    Pydantic includes the offending ``input``; it is deliberately dropped.
    ``ctx`` is kept only when it carries a validator's own message, which is our
    code talking, not the provider's.

    An unexpected key is named only by its parent path. The key itself is model
    output, so repeating it would put response text into a log line.
    """

    location_parts = tuple(error.get("loc", ()))
    issue_type = str(error.get("type", "unknown"))

    if issue_type == "extra_forbidden":
        parent = _format_location(location_parts[:-1])
        if parent == "(root)":
            parent = "the response"
        return FieldIssue(
            location=parent,
            issue_type=issue_type,
            message=_UNEXPECTED_FIELD,
        )

    location = _format_location(location_parts)
    message = str(error.get("msg", "is invalid"))

    context = error.get("ctx")
    if isinstance(context, dict):
        nested = context.get("error")
        if isinstance(nested, str) and nested.strip():
            message = f"{message} ({nested.strip()})"

    return FieldIssue(location=location, issue_type=issue_type, message=message)


def collect_issues(error: ValidationError) -> tuple[FieldIssue, ...]:
    """Turn a Pydantic ``ValidationError`` into structured issues."""

    return tuple(
        _issue_from_error(entry)
        for entry in error.errors(include_url=False)
    )


def validate_model(
    data: Any,
    model: type[ModelT],
) -> ModelT:
    """Validate parsed data against ``model``.

    Raises
    ------
    AIRootTypeError
        When ``data`` is not an object, checked before Pydantic so the message
        describes the shape problem plainly.
    AISchemaValidationError
        When the object does not satisfy the model.
    """

    if not isinstance(data, dict):
        raise AIRootTypeError(
            f"The AI response was not a JSON object; "
            f"received {describe_json_type(data)}."
        )

    try:
        return model.model_validate(data)
    except ValidationError as exc:
        issues = collect_issues(exc)
        raise AISchemaValidationError(
            model_name=model.__name__,
            issues=issues,
            detail="; ".join(issue.message for issue in issues),
        ) from exc


# --------------------------------------------------------------------------- #
# Parsing + validation
# --------------------------------------------------------------------------- #


def parse_structured(text: str | None, model: type[ModelT]) -> ModelT:
    """Parse an AI answer and validate it against ``model``.

    The single entry point for callers that do not want a correction attempt.
    """

    data = parse_json(text)
    return validate_model(data, model)


#: Signature of the correction callback. It receives the failure, and returns
#: replacement text (typically from a second, repair-oriented API call) or
#: ``None`` when it cannot offer one.
Corrector = Callable[[AIStructuredOutputError], "str | None"]


@dataclass(frozen=True)
class ParseOutcome(Generic[ModelT]):
    """A successful parse, plus what it took to get there."""

    value: ModelT
    attempts: int
    corrected: bool
    used_code_fence: bool
    first_error: AIStructuredOutputError | None = field(default=None, repr=False)


def parse_with_correction(
    text: str | None,
    model: type[ModelT],
    *,
    corrector: Corrector | None = None,
) -> ParseOutcome[ModelT]:
    """Parse, allowing at most one correction attempt.

    This function never calls the API itself. When the first attempt fails and a
    ``corrector`` is supplied, the corrector is called exactly once with the
    error and is expected to return replacement text. That is the whole retry
    policy: one attempt, decided here, not a loop.

    Parameters
    ----------
    text:
        The first answer's raw content.
    model:
        The Pydantic model the answer must satisfy.
    corrector:
        Optional callback. It should build a repair request, send it, and return
        the new content. Any exception it raises is treated as a failed
        correction, with the original reason preserved.

    Raises
    ------
    AIStructuredOutputError
        The original error, when no corrector is supplied or the corrector
        declines to try.
    AICorrectionFailedError
        The correction was attempted and did not produce a valid answer. Carries
        the original failure on ``first_error``.
    """

    try:
        data, used_fence = parse_json_with_meta(text)
        value = validate_model(data, model)
    except AIStructuredOutputError as first_error:
        if corrector is None:
            raise

        try:
            replacement = corrector(first_error)
        except AIStructuredOutputError as nested:
            raise AICorrectionFailedError(
                "The AI response could not be parsed and the correction attempt "
                f"also failed.\nFirst problem: {first_error.original_reason}\n"
                f"Correction problem: {nested.original_reason}",
                first_error=first_error,
                correction_error=nested,
                detail=nested.original_reason,
            ) from nested
        except AIError:
            # A transport failure during the correction (timeout, authentication,
            # rate limit, truncation) is not a failed correction: it is its own
            # problem, and collapsing it into "correction failed" would hide a
            # network fault behind a formatting message. Let it travel as itself.
            raise
        except Exception as exc:  # noqa: BLE001 - reported, never swallowed
            raise AICorrectionFailedError(
                "The AI response could not be parsed and the correction request "
                f"failed.\nFirst problem: {first_error.original_reason}",
                first_error=first_error,
                correction_error=exc,
                detail=f"correction raised {type(exc).__name__}",
            ) from exc

        if replacement is None:
            raise AICorrectionFailedError(
                "The AI response could not be parsed and no correction was "
                f"offered.\nFirst problem: {first_error.original_reason}",
                first_error=first_error,
                correction_error=None,
                detail=first_error.original_reason,
            ) from first_error

        try:
            corrected_data, corrected_fence = parse_json_with_meta(replacement)
            corrected_value = validate_model(corrected_data, model)
        except AIStructuredOutputError as second_error:
            raise AICorrectionFailedError(
                "The AI response could not be parsed and the single correction "
                "attempt also failed.\n"
                f"First problem: {first_error.original_reason}\n"
                f"Correction problem: {second_error.original_reason}",
                first_error=first_error,
                correction_error=second_error,
                detail=second_error.original_reason,
            ) from second_error

        return ParseOutcome(
            value=corrected_value,
            attempts=2,
            corrected=True,
            used_code_fence=corrected_fence,
            first_error=first_error,
        )

    return ParseOutcome(
        value=value,
        attempts=1,
        corrected=False,
        used_code_fence=used_fence,
        first_error=None,
    )


__all__ = [
    "AICorrectionFailedError",
    "AIEmptyResponseError",
    "AIInvalidJSONError",
    "AIRootTypeError",
    "AISchemaValidationError",
    "AIStructuredOutputError",
    "Corrector",
    "FieldIssue",
    "ParseOutcome",
    "collect_issues",
    "describe_json_type",
    "parse_json",
    "parse_json_with_meta",
    "parse_structured",
    "parse_with_correction",
    "strip_code_fence",
    "validate_model",
]
