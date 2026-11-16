"""Tests for AI configuration resolution and credential safety."""

from __future__ import annotations

import pytest

from ai import config as config_module
from ai.config import (
    API_KEY_ENV_VAR,
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    AIConfig,
    AIConfigurationError,
    load_config,
    redact_secrets,
    resolve_api_key,
    validate_api_key,
)

#: A fake credential. It is not a real key and is safe to use in tests.
FAKE_KEY = "test-key-0123456789abcdef"


@pytest.fixture(autouse=True)
def _clear_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(API_KEY_ENV_VAR, raising=False)


# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #


def test_defaults_match_the_approved_configuration() -> None:
    assert DEFAULT_BASE_URL == "https://api-cdn.deploy.com/api/v1"
    assert DEFAULT_MODEL == "deepseek-ai/deepseek-v4.1-flash-1017"


def test_model_identifier_has_no_routing_prefix() -> None:
    # The editor configuration uses ``deploy/...`` for routing; the API itself
    # expects the bare identifier verified in Phase 4 Step 2.
    assert not DEFAULT_MODEL.startswith("deploy/")
    assert "/" in DEFAULT_MODEL


def test_chat_completions_url_is_appended_once() -> None:
    config = AIConfig(api_key=FAKE_KEY)
    assert config.chat_completions_url == (
        "https://api-cdn.deploy.com/api/v1/chat/completions"
    )


def test_trailing_slash_in_base_url_does_not_double_up() -> None:
    config = AIConfig(base_url="https://example.test/api/v1/", api_key=FAKE_KEY)
    assert config.chat_completions_url == "https://example.test/api/v1/chat/completions"


# --------------------------------------------------------------------------- #
# Credential validation
# --------------------------------------------------------------------------- #


def test_valid_key_is_returned_unchanged() -> None:
    assert validate_api_key(FAKE_KEY) == FAKE_KEY


def test_missing_key_is_rejected() -> None:
    with pytest.raises(AIConfigurationError) as excinfo:
        validate_api_key(None)
    assert API_KEY_ENV_VAR in str(excinfo.value)


def test_empty_key_is_rejected() -> None:
    with pytest.raises(AIConfigurationError):
        validate_api_key("")


def test_whitespace_only_key_is_rejected() -> None:
    with pytest.raises(AIConfigurationError):
        validate_api_key("   \n\t ")


def test_surrounding_whitespace_is_rejected_rather_than_trimmed() -> None:
    # Silently trimming would hide a copy-paste mistake in a deployment variable.
    with pytest.raises(AIConfigurationError) as excinfo:
        validate_api_key(f" {FAKE_KEY} ")
    assert "whitespace" in str(excinfo.value)


def test_truncated_key_is_rejected() -> None:
    with pytest.raises(AIConfigurationError) as excinfo:
        validate_api_key("short")
    assert "truncated" in str(excinfo.value)


@pytest.mark.parametrize("bad", ["key with space", "key\twith\ttab", "keyünïcode"])
def test_key_with_unusable_characters_is_rejected(bad: str) -> None:
    with pytest.raises(AIConfigurationError):
        validate_api_key(bad)


def test_error_message_never_contains_the_key_value() -> None:
    secret = "  should-not-appear-in-message  "
    with pytest.raises(AIConfigurationError) as excinfo:
        validate_api_key(secret)
    assert secret.strip() not in str(excinfo.value)


# --------------------------------------------------------------------------- #
# Resolution order
# --------------------------------------------------------------------------- #


def test_environment_takes_priority(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(API_KEY_ENV_VAR, "env-value-0123456789")
    assert resolve_api_key("fallback-value-0123456789") == "env-value-0123456789"


def test_fallback_is_used_when_environment_is_absent() -> None:
    assert resolve_api_key("fallback-value-0123456789") == "fallback-value-0123456789"


def test_missing_both_is_a_configuration_error() -> None:
    with pytest.raises(AIConfigurationError):
        resolve_api_key(None)


def test_empty_environment_value_does_not_fall_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # An explicitly empty variable is a configuration mistake; falling back
    # would hide it.
    monkeypatch.setenv(API_KEY_ENV_VAR, "")
    with pytest.raises(AIConfigurationError):
        resolve_api_key("fallback-value-0123456789")


def test_load_config_reads_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(API_KEY_ENV_VAR, FAKE_KEY)
    config = load_config()
    assert config.api_key == FAKE_KEY
    assert config.model == DEFAULT_MODEL
    assert config.base_url == DEFAULT_BASE_URL


def test_load_config_accepts_an_application_supplied_key() -> None:
    config = load_config(fallback_api_key=FAKE_KEY)
    assert config.api_key == FAKE_KEY


def test_load_config_rejects_an_empty_base_url() -> None:
    with pytest.raises(AIConfigurationError):
        load_config(fallback_api_key=FAKE_KEY, base_url="  ")


def test_load_config_rejects_an_empty_model() -> None:
    with pytest.raises(AIConfigurationError):
        load_config(fallback_api_key=FAKE_KEY, model="")


# --------------------------------------------------------------------------- #
# Leak resistance
# --------------------------------------------------------------------------- #


def test_repr_omits_the_key() -> None:
    config = AIConfig(api_key=FAKE_KEY)
    assert FAKE_KEY not in repr(config)
    assert "redacted" in repr(config)


def test_str_omits_the_key() -> None:
    config = AIConfig(api_key=FAKE_KEY)
    assert FAKE_KEY not in str(config)


def test_dataclass_dict_holds_the_key_but_repr_does_not() -> None:
    # ``__dict__`` is Python's raw attribute storage and cannot be hidden without
    # abandoning the dataclass. What must hold is that the default, accidental
    # views (repr, str, logging) never show the value.
    config = AIConfig(api_key=FAKE_KEY)
    assert config.__dict__["api_key"] == FAKE_KEY
    assert FAKE_KEY not in repr(config)
    assert FAKE_KEY not in str(config)
    assert FAKE_KEY not in f"{config}"


def test_redact_secrets_removes_an_exact_key() -> None:
    text = f"The provider echoed {FAKE_KEY} back."
    assert FAKE_KEY not in redact_secrets(text, FAKE_KEY)


def test_redact_secrets_removes_bearer_tokens() -> None:
    text = "Authorization: Bearer abcdef1234567890"
    assert "abcdef1234567890" not in redact_secrets(text)


def test_redact_secrets_removes_sk_style_tokens() -> None:
    text = "key sk-abcdef1234567890 leaked"
    assert "sk-abcdef1234567890" not in redact_secrets(text)


def test_redact_secrets_leaves_ordinary_text_alone() -> None:
    assert redact_secrets("HTTP 429 rate limited") == "HTTP 429 rate limited"


def test_config_module_does_not_import_streamlit() -> None:
    # The AI layer must stay usable without Streamlit; the application supplies
    # the secret instead.
    source = config_module.__file__
    assert source is not None
    with open(source, encoding="utf-8") as handle:
        text = handle.read()
    assert "import streamlit" not in text
    assert "from streamlit" not in text
