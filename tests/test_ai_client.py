"""Tests for the AI HTTP client.

Every test injects a fake ``opener``, so the suite never opens a socket. That is
also how the "exactly one request" guarantee is asserted: the fake counts calls.
"""

from __future__ import annotations

import json
import socket
import urllib.error
from typing import Any

import pytest

from ai.client import (
    AIAuthenticationError,
    AIError,
    AINetworkError,
    AIRateLimitError,
    AIRequestError,
    AIResponseFormatError,
    AIServerError,
    AITimeoutError,
    AITruncatedResponseError,
    ChatCompletion,
    build_request_body,
    complete,
)
from ai.config import AIConfig

FAKE_KEY = "test-key-0123456789abcdef"

MESSAGES = [{"role": "user", "content": 'Return {"ok": true} as JSON.'}]


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #


class FakeResponse:
    """Minimal ``http.client.HTTPResponse`` stand-in."""

    def __init__(self, body: bytes, status: int = 200) -> None:
        self._body = body
        self.status = status
        self.headers = {"Content-Type": "application/json"}

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


class FakeOpener:
    """Records every request and returns a queued result."""

    def __init__(self, *results: Any) -> None:
        self._results = list(results)
        self.calls: list[urllib.error.Request | Any] = []
        self.timeouts: list[float] = []

    def __call__(self, request: Any, timeout: float | None = None) -> Any:
        self.calls.append(request)
        self.timeouts.append(timeout)  # type: ignore[arg-type]
        if not self._results:
            raise AssertionError("The client made more requests than expected.")
        result = self._results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


def completion_payload(
    content: str = '{"ok": true}',
    finish_reason: str = "stop",
) -> bytes:
    return json.dumps(
        {
            "id": "chatcmpl-test",
            "model": "deepseek-ai/deepseek-v4.1-flash-1017",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": finish_reason,
                }
            ],
            "usage": {
                "prompt_tokens": 54,
                "completion_tokens": 23,
                "total_tokens": 77,
            },
        }
    ).encode("utf-8")


def http_error(status: int, body: bytes = b"") -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        "https://api-cdn.deploy.com/api/v1/chat/completions",
        status,
        "error",
        {},  # type: ignore[arg-type]
        _BodyReader(body),
    )


class _BodyReader:
    """File-like body used by :class:`urllib.error.HTTPError`.

    ``close`` exists because ``HTTPError`` owns the handle and closes it during
    cleanup; without it, every error test leaks an unraisable warning.
    """

    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body

    def close(self) -> None:
        return None


@pytest.fixture
def config() -> AIConfig:
    return AIConfig(api_key=FAKE_KEY)


# --------------------------------------------------------------------------- #
# Request construction
# --------------------------------------------------------------------------- #


def test_request_body_requests_json_object(config: AIConfig) -> None:
    body = json.loads(build_request_body(config, MESSAGES, max_tokens=32))
    assert body["response_format"] == {"type": "json_object"}
    assert body["stream"] is False
    assert body["model"] == "deepseek-ai/deepseek-v4.1-flash-1017"
    assert body["max_tokens"] == 32


def test_request_body_defaults_to_zero_temperature(config: AIConfig) -> None:
    body = json.loads(build_request_body(config, MESSAGES, max_tokens=32))
    assert body["temperature"] == 0


def test_request_body_rejects_an_empty_message_list(config: AIConfig) -> None:
    with pytest.raises(AIRequestError):
        build_request_body(config, [], max_tokens=32)


def test_request_body_rejects_a_non_positive_token_limit(config: AIConfig) -> None:
    with pytest.raises(AIRequestError):
        build_request_body(config, MESSAGES, max_tokens=0)


def test_request_carries_bearer_authorisation(config: AIConfig) -> None:
    opener = FakeOpener(FakeResponse(completion_payload()))
    complete(config, MESSAGES, max_tokens=32, opener=opener)
    request = opener.calls[0]
    assert request.get_header("Authorization") == f"Bearer {FAKE_KEY}"


def test_request_targets_the_chat_completions_endpoint(config: AIConfig) -> None:
    opener = FakeOpener(FakeResponse(completion_payload()))
    complete(config, MESSAGES, max_tokens=32, opener=opener)
    assert opener.calls[0].full_url == (
        "https://api-cdn.deploy.com/api/v1/chat/completions"
    )


def test_request_uses_post(config: AIConfig) -> None:
    opener = FakeOpener(FakeResponse(completion_payload()))
    complete(config, MESSAGES, max_tokens=32, opener=opener)
    assert opener.calls[0].get_method() == "POST"


def test_timeout_is_forwarded(config: AIConfig) -> None:
    opener = FakeOpener(FakeResponse(completion_payload()))
    complete(config, MESSAGES, max_tokens=32, opener=opener, timeout=45)
    assert opener.timeouts == [45]


def test_default_timeout_is_sixty_seconds(config: AIConfig) -> None:
    opener = FakeOpener(FakeResponse(completion_payload()))
    complete(config, MESSAGES, max_tokens=32, opener=opener)
    assert opener.timeouts == [60.0]


def test_non_positive_timeout_is_rejected(config: AIConfig) -> None:
    with pytest.raises(AIRequestError):
        complete(config, MESSAGES, max_tokens=32, opener=FakeOpener(), timeout=0)


# --------------------------------------------------------------------------- #
# Successful response
# --------------------------------------------------------------------------- #


def test_successful_response_is_returned(config: AIConfig) -> None:
    opener = FakeOpener(FakeResponse(completion_payload()))
    result = complete(config, MESSAGES, max_tokens=32, opener=opener)
    assert isinstance(result, ChatCompletion)
    assert result.content == '{"ok": true}'
    assert result.finish_reason == "stop"
    assert result.model == "deepseek-ai/deepseek-v4.1-flash-1017"


def test_usage_is_surfaced(config: AIConfig) -> None:
    opener = FakeOpener(FakeResponse(completion_payload()))
    result = complete(config, MESSAGES, max_tokens=32, opener=opener)
    assert result.prompt_tokens == 54
    assert result.completion_tokens == 23
    assert result.total_tokens == 77


def test_missing_usage_does_not_fail_the_call(config: AIConfig) -> None:
    payload = json.loads(completion_payload())
    del payload["usage"]
    opener = FakeOpener(FakeResponse(json.dumps(payload).encode()))
    result = complete(config, MESSAGES, max_tokens=32, opener=opener)
    assert result.total_tokens is None
    assert result.content == '{"ok": true}'


def test_content_is_stripped(config: AIConfig) -> None:
    opener = FakeOpener(FakeResponse(completion_payload('  {"ok": true}\n')))
    result = complete(config, MESSAGES, max_tokens=32, opener=opener)
    assert result.content == '{"ok": true}'


def test_content_filter_finish_reason_is_accepted(config: AIConfig) -> None:
    # The provider censored the answer but did not truncate it; the caller can
    # still parse whatever valid JSON came back.
    opener = FakeOpener(
        FakeResponse(completion_payload('{"ok": true}', "content_filter"))
    )
    result = complete(config, MESSAGES, max_tokens=32, opener=opener)
    assert result.finish_reason == "content_filter"


# --------------------------------------------------------------------------- #
# Truncation and unknown finish reasons
# --------------------------------------------------------------------------- #


def test_length_finish_reason_is_a_truncation_error(config: AIConfig) -> None:
    partial = '{"ok": tr'
    opener = FakeOpener(FakeResponse(completion_payload(partial, "length")))
    with pytest.raises(AITruncatedResponseError) as excinfo:
        complete(config, MESSAGES, max_tokens=32, opener=opener)
    assert excinfo.value.category == "truncated_response"
    # The partial content must not be handed back, not even in the message.
    assert partial not in str(excinfo.value)


def test_truncation_error_is_a_response_format_error(config: AIConfig) -> None:
    opener = FakeOpener(FakeResponse(completion_payload("{}", "length")))
    with pytest.raises(AIResponseFormatError):
        complete(config, MESSAGES, max_tokens=32, opener=opener)


def test_unknown_finish_reason_is_reported(config: AIConfig) -> None:
    opener = FakeOpener(FakeResponse(completion_payload("{}", "tool_calls")))
    with pytest.raises(AIResponseFormatError) as excinfo:
        complete(config, MESSAGES, max_tokens=32, opener=opener)
    assert "tool_calls" in str(excinfo.value)


def test_missing_finish_reason_is_reported(config: AIConfig) -> None:
    payload = json.loads(completion_payload())
    del payload["choices"][0]["finish_reason"]
    opener = FakeOpener(FakeResponse(json.dumps(payload).encode()))
    with pytest.raises(AIResponseFormatError) as excinfo:
        complete(config, MESSAGES, max_tokens=32, opener=opener)
    assert "finish reason" in str(excinfo.value)


def test_null_finish_reason_is_reported(config: AIConfig) -> None:
    payload = json.loads(completion_payload())
    payload["choices"][0]["finish_reason"] = None
    opener = FakeOpener(FakeResponse(json.dumps(payload).encode()))
    with pytest.raises(AIResponseFormatError):
        complete(config, MESSAGES, max_tokens=32, opener=opener)


def test_non_string_finish_reason_is_reported(config: AIConfig) -> None:
    payload = json.loads(completion_payload())
    payload["choices"][0]["finish_reason"] = 42
    opener = FakeOpener(FakeResponse(json.dumps(payload).encode()))
    with pytest.raises(AIResponseFormatError):
        complete(config, MESSAGES, max_tokens=32, opener=opener)


# --------------------------------------------------------------------------- #
# Malformed payloads
# --------------------------------------------------------------------------- #


def test_invalid_json_body_is_reported(config: AIConfig) -> None:
    opener = FakeOpener(FakeResponse(b"this is not json"))
    with pytest.raises(AIResponseFormatError) as excinfo:
        complete(config, MESSAGES, max_tokens=32, opener=opener)
    assert "not valid JSON" in str(excinfo.value)


def test_json_array_body_is_reported(config: AIConfig) -> None:
    opener = FakeOpener(FakeResponse(b"[]"))
    with pytest.raises(AIResponseFormatError):
        complete(config, MESSAGES, max_tokens=32, opener=opener)


def test_missing_choices_is_reported(config: AIConfig) -> None:
    opener = FakeOpener(FakeResponse(json.dumps({"model": "x"}).encode()))
    with pytest.raises(AIResponseFormatError) as excinfo:
        complete(config, MESSAGES, max_tokens=32, opener=opener)
    assert "no choices" in str(excinfo.value)


def test_empty_choices_is_reported(config: AIConfig) -> None:
    opener = FakeOpener(FakeResponse(json.dumps({"choices": []}).encode()))
    with pytest.raises(AIResponseFormatError):
        complete(config, MESSAGES, max_tokens=32, opener=opener)


def test_missing_message_is_reported(config: AIConfig) -> None:
    payload = json.loads(completion_payload())
    del payload["choices"][0]["message"]
    opener = FakeOpener(FakeResponse(json.dumps(payload).encode()))
    with pytest.raises(AIResponseFormatError) as excinfo:
        complete(config, MESSAGES, max_tokens=32, opener=opener)
    assert "message object" in str(excinfo.value)


def test_null_content_is_reported(config: AIConfig) -> None:
    payload = json.loads(completion_payload())
    payload["choices"][0]["message"]["content"] = None
    opener = FakeOpener(FakeResponse(json.dumps(payload).encode()))
    with pytest.raises(AIResponseFormatError) as excinfo:
        complete(config, MESSAGES, max_tokens=32, opener=opener)
    assert "no content" in str(excinfo.value)


def test_empty_content_is_reported(config: AIConfig) -> None:
    opener = FakeOpener(FakeResponse(completion_payload("   ")))
    with pytest.raises(AIResponseFormatError) as excinfo:
        complete(config, MESSAGES, max_tokens=32, opener=opener)
    assert "empty" in str(excinfo.value)


def test_non_string_content_is_reported(config: AIConfig) -> None:
    payload = json.loads(completion_payload())
    payload["choices"][0]["message"]["content"] = [{"type": "text"}]
    opener = FakeOpener(FakeResponse(json.dumps(payload).encode()))
    with pytest.raises(AIResponseFormatError) as excinfo:
        complete(config, MESSAGES, max_tokens=32, opener=opener)
    assert "not text" in str(excinfo.value)


# --------------------------------------------------------------------------- #
# HTTP error classification
# --------------------------------------------------------------------------- #


def test_401_is_an_authentication_error(config: AIConfig) -> None:
    opener = FakeOpener(http_error(401, b'{"error":{"message":"invalid key"}}'))
    with pytest.raises(AIAuthenticationError) as excinfo:
        complete(config, MESSAGES, max_tokens=32, opener=opener)
    assert excinfo.value.category == "authentication_error"
    assert excinfo.value.retryable is False


def test_403_is_an_authentication_error(config: AIConfig) -> None:
    opener = FakeOpener(http_error(403, b""))
    with pytest.raises(AIAuthenticationError):
        complete(config, MESSAGES, max_tokens=32, opener=opener)


def test_400_is_a_request_error(config: AIConfig) -> None:
    opener = FakeOpener(http_error(400, b'{"error":{"message":"bad format"}}'))
    with pytest.raises(AIRequestError) as excinfo:
        complete(config, MESSAGES, max_tokens=32, opener=opener)
    assert "bad format" in str(excinfo.value)


def test_404_is_a_request_error(config: AIConfig) -> None:
    opener = FakeOpener(http_error(404, b""))
    with pytest.raises(AIRequestError) as excinfo:
        complete(config, MESSAGES, max_tokens=32, opener=opener)
    assert "not found" in str(excinfo.value).lower()


def test_429_is_a_rate_limit_error(config: AIConfig) -> None:
    opener = FakeOpener(http_error(429, b'{"error":{"message":"slow down"}}'))
    with pytest.raises(AIRateLimitError) as excinfo:
        complete(config, MESSAGES, max_tokens=32, opener=opener)
    assert excinfo.value.category == "rate_limit"
    assert excinfo.value.retryable is True


def test_500_is_a_server_error(config: AIConfig) -> None:
    opener = FakeOpener(http_error(500, b""))
    with pytest.raises(AIServerError) as excinfo:
        complete(config, MESSAGES, max_tokens=32, opener=opener)
    assert excinfo.value.retryable is True


def test_503_is_a_server_error(config: AIConfig) -> None:
    opener = FakeOpener(http_error(503, b"upstream unavailable"))
    with pytest.raises(AIServerError) as excinfo:
        complete(config, MESSAGES, max_tokens=32, opener=opener)
    assert "503" in str(excinfo.value)


def test_unexpected_4xx_is_a_request_error(config: AIConfig) -> None:
    opener = FakeOpener(http_error(418, b""))
    with pytest.raises(AIRequestError) as excinfo:
        complete(config, MESSAGES, max_tokens=32, opener=opener)
    assert "418" in str(excinfo.value)


# --------------------------------------------------------------------------- #
# Network failures
# --------------------------------------------------------------------------- #


def test_timeout_is_raised_as_a_timeout_error(config: AIConfig) -> None:
    opener = FakeOpener(socket.timeout("timed out"))
    with pytest.raises(AITimeoutError) as excinfo:
        complete(config, MESSAGES, max_tokens=32, opener=opener, timeout=5)
    assert excinfo.value.category == "timeout"
    assert "5 seconds" in str(excinfo.value)


def test_url_error_wrapping_a_timeout_is_a_timeout(config: AIConfig) -> None:
    opener = FakeOpener(urllib.error.URLError(socket.timeout("timed out")))
    with pytest.raises(AITimeoutError):
        complete(config, MESSAGES, max_tokens=32, opener=opener)


def test_connection_error_is_a_network_error(config: AIConfig) -> None:
    opener = FakeOpener(urllib.error.URLError(ConnectionRefusedError("refused")))
    with pytest.raises(AINetworkError) as excinfo:
        complete(config, MESSAGES, max_tokens=32, opener=opener)
    assert excinfo.value.category == "network_error"


def test_dns_failure_is_a_network_error(config: AIConfig) -> None:
    opener = FakeOpener(urllib.error.URLError(socket.gaierror("name resolution")))
    with pytest.raises(AINetworkError):
        complete(config, MESSAGES, max_tokens=32, opener=opener)


def test_builtin_timeout_error_is_a_timeout_error(config: AIConfig) -> None:
    opener = FakeOpener(TimeoutError("timed out"))
    with pytest.raises(AITimeoutError):
        complete(config, MESSAGES, max_tokens=32, opener=opener)


# --------------------------------------------------------------------------- #
# Retry discipline
# --------------------------------------------------------------------------- #


def test_success_uses_exactly_one_request(config: AIConfig) -> None:
    opener = FakeOpener(FakeResponse(completion_payload()))
    complete(config, MESSAGES, max_tokens=32, opener=opener)
    assert len(opener.calls) == 1


@pytest.mark.parametrize(
    "failure",
    [
        socket.timeout("timed out"),
        urllib.error.URLError(ConnectionRefusedError("refused")),
        http_error(429, b""),
        http_error(500, b""),
        http_error(401, b""),
    ],
)
def test_failures_are_not_retried(config: AIConfig, failure: Exception) -> None:
    # One queued result: a second attempt would raise AssertionError, not the
    # expected AIError, so this asserts the absence of a retry loop.
    opener = FakeOpener(failure)
    with pytest.raises(AIError):
        complete(config, MESSAGES, max_tokens=32, opener=opener)
    assert len(opener.calls) == 1


def test_malformed_response_is_not_retried(config: AIConfig) -> None:
    opener = FakeOpener(FakeResponse(b"not json"))
    with pytest.raises(AIResponseFormatError):
        complete(config, MESSAGES, max_tokens=32, opener=opener)
    assert len(opener.calls) == 1


# --------------------------------------------------------------------------- #
# Credential containment
# --------------------------------------------------------------------------- #


def _assert_no_leak(text: str) -> None:
    assert FAKE_KEY not in text
    assert "Bearer " + FAKE_KEY not in text


def test_authentication_error_does_not_leak_the_key(config: AIConfig) -> None:
    opener = FakeOpener(http_error(401, b'{"error":{"message":"invalid key"}}'))
    with pytest.raises(AIAuthenticationError) as excinfo:
        complete(config, MESSAGES, max_tokens=32, opener=opener)
    _assert_no_leak(str(excinfo.value))


def test_provider_echoing_the_key_is_redacted(config: AIConfig) -> None:
    # A misconfigured proxy could echo the header back; that text must not
    # survive into the exception.
    body = json.dumps(
        {"error": {"message": f"Rejected header Authorization: Bearer {FAKE_KEY}"}}
    ).encode()
    opener = FakeOpener(http_error(401, body))
    with pytest.raises(AIAuthenticationError) as excinfo:
        complete(config, MESSAGES, max_tokens=32, opener=opener)
    _assert_no_leak(str(excinfo.value))
    _assert_no_leak(str(excinfo.value.detail or ""))


def test_network_error_does_not_leak_the_key(config: AIConfig) -> None:
    opener = FakeOpener(urllib.error.URLError(f"failed for {FAKE_KEY}"))
    with pytest.raises(AINetworkError) as excinfo:
        complete(config, MESSAGES, max_tokens=32, opener=opener)
    _assert_no_leak(str(excinfo.value))


def test_invalid_json_body_does_not_leak_the_key(config: AIConfig) -> None:
    body = f'{{"echo": "Bearer {FAKE_KEY}" this is broken'.encode()
    opener = FakeOpener(FakeResponse(body))
    with pytest.raises(AIResponseFormatError) as excinfo:
        complete(config, MESSAGES, max_tokens=32, opener=opener)
    _assert_no_leak(str(excinfo.value))
    _assert_no_leak(str(excinfo.value.detail or ""))


def test_error_payload_messages_are_redacted(config: AIConfig) -> None:
    body = json.dumps({"error": {"message": f"bad token {FAKE_KEY} supplied"}}).encode()
    opener = FakeOpener(http_error(429, body))
    with pytest.raises(AIRateLimitError) as excinfo:
        complete(config, MESSAGES, max_tokens=32, opener=opener)
    _assert_no_leak(str(excinfo.value))


def test_detail_is_truncated(config: AIConfig) -> None:
    body = json.dumps({"error": {"message": "x" * 2000}}).encode()
    opener = FakeOpener(http_error(500, body))
    with pytest.raises(AIServerError) as excinfo:
        complete(config, MESSAGES, max_tokens=32, opener=opener)
    assert len(str(excinfo.value)) < 700


def test_result_repr_hides_the_response_id(config: AIConfig) -> None:
    opener = FakeOpener(FakeResponse(completion_payload()))
    result = complete(config, MESSAGES, max_tokens=32, opener=opener)
    assert result.response_id == "chatcmpl-test"
    assert "chatcmpl-test" not in repr(result)


# --------------------------------------------------------------------------- #
# Layer boundaries
# --------------------------------------------------------------------------- #


def test_client_does_not_import_streamlit() -> None:
    import ai.client as client_module

    source = client_module.__file__
    assert source is not None
    with open(source, encoding="utf-8") as handle:
        text = handle.read()
    assert "import streamlit" not in text
    assert "from streamlit" not in text


def test_streamlit_is_not_imported_as_a_side_effect_of_using_the_client() -> None:
    # The AI package must stay framework-agnostic; if a stray import existed,
    # this would catch it in a fresh interpreter.
    import subprocess
    import sys

    code = (
        "import sys;"
        "import ai.client, ai.config;"
        "print('streamlit' in sys.modules)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    assert result.stdout.strip() == "False"
