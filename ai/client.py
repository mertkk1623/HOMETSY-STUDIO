"""OpenAI-compatible chat completions client.

This is the only module in the application that performs HTTP. Everything else
passes a config in and receives structured data or a typed error out.

Design rules:

* Exactly one request per call. There is no retry loop here; controlled
  correction of malformed output belongs to a higher layer that can reason about
  what went wrong.
* The credential never appears in an exception message, a log line or a
  ``repr``. Provider error bodies are redacted before they are surfaced, because
  a misbehaving endpoint could echo a request header back.
* ``finish_reason`` is mandatory. A truncated answer is reported as truncation,
  not as a generic failure, and it is never returned as if it were complete.
* The client does not import Streamlit and does not parse domain JSON. It
  returns the assistant's message text; turning that text into a validated model
  is a separate concern.
"""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from ai.config import AIConfig, redact_secrets

#: Seconds to wait for the provider before giving up.
DEFAULT_TIMEOUT_SECONDS = 60.0

#: Responses below this size are almost certainly not a real answer.
_MIN_CONTENT_LENGTH = 1

#: Characters of provider text kept in a message. Long error bodies are noise.
_MAX_DETAIL_LENGTH = 400


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #


class AIError(RuntimeError):
    """Base class for every failure the AI layer can report.

    ``category`` is a stable machine-readable label so the interface can decide
    how to present the problem without inspecting the message text.
    """

    category: str = "ai_error"
    retryable: bool = False

    def __init__(self, message: str, *, detail: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail

    def __str__(self) -> str:
        return self.message


class AINetworkError(AIError):
    """The request never produced an HTTP response."""

    category = "network_error"
    retryable = True


class AITimeoutError(AINetworkError):
    """The provider did not answer within the timeout."""

    category = "timeout"
    retryable = True


class AIAuthenticationError(AIError):
    """401/403: the credential was rejected or lacks access."""

    category = "authentication_error"


class AIRequestError(AIError):
    """400/404/422 and other client-side mistakes: the request itself is wrong."""

    category = "request_error"


class AIRateLimitError(AIError):
    """429: the provider asked the caller to slow down."""

    category = "rate_limit"
    retryable = True


class AIServerError(AIError):
    """5xx: the provider failed while handling an otherwise valid request."""

    category = "server_error"
    retryable = True


class AIResponseFormatError(AIError):
    """The provider answered, but not with a usable chat completion."""

    category = "response_format_error"


class AITruncatedResponseError(AIResponseFormatError):
    """``finish_reason`` was ``length``: the answer was cut off mid-generation."""

    category = "truncated_response"


# --------------------------------------------------------------------------- #
# Result model
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ChatCompletion:
    """A successful chat completion.

    ``content`` is the assistant's raw text. It is intentionally not parsed
    here; schema validation happens in the parsing layer.
    """

    content: str
    model: str
    finish_reason: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    response_id: str | None = field(default=None, repr=False)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _redact(text: str, config: AIConfig) -> str:
    """Remove the credential and token-shaped substrings from provider text."""

    return redact_secrets(text, config.api_key)[:_MAX_DETAIL_LENGTH]


def _provider_message(body: bytes, config: AIConfig) -> str | None:
    """Best-effort human-readable error from an OpenAI-style error body."""

    try:
        decoded = body.decode("utf-8", "replace")
    except Exception:  # noqa: BLE001 - decoding must never mask the real error
        return None

    try:
        payload = json.loads(decoded)
    except Exception:  # noqa: BLE001
        cleaned = _redact(decoded, config).strip()
        return cleaned or None

    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str) and message.strip():
                return _redact(message.strip(), config)
        for key in ("message", "detail"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return _redact(value.strip(), config)

    return None


def _raise_for_status(status: int, body: bytes, config: AIConfig) -> None:
    """Translate an HTTP status into the matching typed error.

    The mapping is explicit so an unexpected status cannot fall through and be
    mistaken for success.
    """

    provider_message = _provider_message(body, config)
    suffix = f" Provider said: {provider_message}" if provider_message else ""

    if status in (401, 403):
        reason = (
            "The AI provider rejected the credentials. Check that the API key is "
            "correct."
            if status == 401
            else "The AI provider refused access. Check that the API key may use "
            "this model."
        )
        raise AIAuthenticationError(f"{reason}{suffix}", detail=provider_message)
    if status == 429:
        raise AIRateLimitError(
            "The AI provider is rate limiting requests. Wait a moment and try "
            f"again.{suffix}",
            detail=provider_message,
        )
    if status == 404:
        raise AIRequestError(
            "The AI endpoint or model was not found. Check the base URL and model "
            f"identifier.{suffix}",
            detail=provider_message,
        )
    if status == 400:
        raise AIRequestError(
            f"The AI provider rejected the request as invalid.{suffix}",
            detail=provider_message,
        )
    if status >= 500:
        raise AIServerError(
            f"The AI provider reported a server error (HTTP {status}). Try "
            f"again later.{suffix}",
            detail=provider_message,
        )
    if status >= 400:
        raise AIRequestError(
            f"The AI provider returned an unexpected error (HTTP {status}).{suffix}",
            detail=provider_message,
        )


def _parse_usage(payload: dict) -> dict[str, int | None]:
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None}

    def as_int(name: str) -> int | None:
        value = usage.get(name)
        return value if isinstance(value, int) and not isinstance(value, bool) else None

    return {
        "prompt_tokens": as_int("prompt_tokens"),
        "completion_tokens": as_int("completion_tokens"),
        "total_tokens": as_int("total_tokens"),
    }


def _extract_content(choice: dict, config: AIConfig) -> str:
    """Pull the assistant text out of a choice, or explain why it is missing."""

    message = choice.get("message")
    if not isinstance(message, dict):
        raise AIResponseFormatError(
            "The AI response did not contain a message object."
        )

    content = message.get("content")
    if content is None:
        raise AIResponseFormatError("The AI response contained no content.")
    if not isinstance(content, str):
        raise AIResponseFormatError(
            "The AI response content was not text."
        )

    stripped = content.strip()
    if len(stripped) < _MIN_CONTENT_LENGTH:
        raise AIResponseFormatError("The AI response content was empty.")

    return stripped


def _interpret_response(raw: bytes, config: AIConfig) -> ChatCompletion:
    """Turn a raw response body into a completion or a typed error."""

    try:
        payload = json.loads(raw.decode("utf-8", "replace"))
    except Exception as exc:  # noqa: BLE001 - reported as a format error
        preview = _redact(raw.decode("utf-8", "replace"), config)
        raise AIResponseFormatError(
            "The AI response was not valid JSON.",
            detail=preview,
        ) from exc

    if not isinstance(payload, dict):
        raise AIResponseFormatError(
            "The AI response was not a JSON object.",
        )

    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise AIResponseFormatError(
            "The AI response contained no choices.",
        )

    choice = choices[0]
    if not isinstance(choice, dict):
        raise AIResponseFormatError(
            "The AI response contained a malformed choice.",
        )

    finish_reason = choice.get("finish_reason")
    if finish_reason is None:
        raise AIResponseFormatError(
            "The AI response did not report a finish reason, so it cannot be "
            "treated as complete."
        )
    if not isinstance(finish_reason, str):
        raise AIResponseFormatError(
            "The AI response reported a non-text finish reason."
        )

    if finish_reason == "length":
        raise AITruncatedResponseError(
            "The AI answer was cut off because it reached the output token "
            "limit. Retry with a shorter prompt or a larger limit."
        )

    if finish_reason not in {"stop", "content_filter"}:
        raise AIResponseFormatError(
            f"The AI response finished for an unexpected reason "
            f"({_redact(finish_reason, config)!r}), so it is not used.",
            detail=_redact(finish_reason, config),
        )

    content = _extract_content(choice, config)
    usage = _parse_usage(payload)
    model = payload.get("model")
    response_id = payload.get("id")

    return ChatCompletion(
        content=content,
        model=model if isinstance(model, str) else config.model,
        finish_reason=finish_reason,
        prompt_tokens=usage["prompt_tokens"],
        completion_tokens=usage["completion_tokens"],
        total_tokens=usage["total_tokens"],
        response_id=response_id if isinstance(response_id, str) else None,
    )


# --------------------------------------------------------------------------- #
# Request
# --------------------------------------------------------------------------- #


def build_request_body(
    config: AIConfig,
    messages: list[dict[str, str]],
    *,
    max_tokens: int,
    temperature: float = 0.0,
) -> bytes:
    """Serialise the request payload.

    ``response_format`` requests a JSON object, which Phase 4 Step 2 confirmed
    the provider supports. ``stream`` is explicitly false so a streaming branch
    can never be reached by accident.
    """

    if not messages:
        raise AIRequestError("At least one message is required.")
    if max_tokens < 1:
        raise AIRequestError("max_tokens must be a positive integer.")

    payload = {
        "model": config.model,
        "messages": messages,
        "response_format": {"type": "json_object"},
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }
    return json.dumps(payload).encode("utf-8")


def _build_request(config: AIConfig, body: bytes) -> urllib.request.Request:
    """Assemble the HTTP request.

    The Authorization header is built here and nowhere else, so there is a single
    place where the credential enters an outgoing message.
    """

    return urllib.request.Request(
        config.chat_completions_url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "hometsy/1.0",
        },
    )


def complete(
    config: AIConfig,
    messages: list[dict[str, str]],
    *,
    max_tokens: int,
    temperature: float = 0.0,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    opener: object | None = None,
) -> ChatCompletion:
    """Send one chat completion request and return its validated envelope.

    Parameters
    ----------
    opener:
        Optional replacement for ``urllib.request.urlopen``. Tests inject a fake
        so the suite never touches the network. Production callers omit it.

    Raises
    ------
    AIError
        A subclass for every outcome that is not a complete, non-truncated
        answer. Exactly one request is attempted per call.
    """

    if timeout <= 0:
        raise AIRequestError("timeout must be greater than zero.")

    body = build_request_body(
        config, messages, max_tokens=max_tokens, temperature=temperature
    )
    request = _build_request(config, body)
    open_url = opener if opener is not None else urllib.request.urlopen

    try:
        with open_url(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        try:
            error_body = exc.read()
        except Exception:  # noqa: BLE001 - the status is what matters most
            error_body = b""
        _raise_for_status(exc.code, error_body, config)
        raise AIError(
            f"The AI provider returned HTTP {exc.code}."  # pragma: no cover
        ) from None
    except socket.timeout as exc:
        raise AITimeoutError(
            f"The AI provider did not answer within {timeout:g} seconds."
        ) from exc
    except urllib.error.URLError as exc:
        reason = exc.reason
        if isinstance(reason, socket.timeout):
            raise AITimeoutError(
                f"The AI provider did not answer within {timeout:g} seconds."
            ) from exc
        safe_reason = _redact(str(reason), config) if reason else "no details"
        raise AINetworkError(
            f"Could not reach the AI provider. Check the network connection. "
            f"({safe_reason})"
        ) from exc
    except TimeoutError as exc:
        raise AITimeoutError(
            f"The AI provider did not answer within {timeout:g} seconds."
        ) from exc

    return _interpret_response(raw, config)


__all__ = [
    "DEFAULT_TIMEOUT_SECONDS",
    "AIError",
    "AIAuthenticationError",
    "AINetworkError",
    "AIRateLimitError",
    "AIRequestError",
    "AIResponseFormatError",
    "AIServerError",
    "AITimeoutError",
    "AITruncatedResponseError",
    "ChatCompletion",
    "build_request_body",
    "complete",
]
