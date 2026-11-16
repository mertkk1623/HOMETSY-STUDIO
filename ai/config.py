"""Central AI configuration.

One place decides which endpoint, model and credential the AI layer uses, so no
service module has to know those details.

Credential handling rules, which the rest of the AI package relies on:

* The key is read from ``DEPLOY_API_KEY`` in the process environment first.
* If the environment does not define it, the application layer may pass the
  value it obtained from its own secret store (Streamlit secrets). This module
  never imports Streamlit, so the dependency direction stays one-way.
* A missing or malformed key raises :class:`AIConfigurationError` with a message
  that says what is wrong and never contains the key.
* The key is excluded from ``repr`` and from every error message, so an
  accidental ``print(config)`` or logged exception cannot leak it.

The endpoint and model were verified against the live provider in Phase 4
Step 2; they are configuration, not guesses.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

#: Provider base URL, including the version segment. OpenAI-compatible paths are
#: appended to this value (``/chat/completions``).
DEFAULT_BASE_URL = "https://api-cdn.deploy.com/api/v1"

#: The approved model identifier. The ``deploy/`` routing prefix used by the
#: editor configuration is deliberately absent: this is the identifier the API
#: itself expects and echoes back.
DEFAULT_MODEL = "deepseek-ai/deepseek-v4.1-flash-1017"

#: Environment variable holding the credential.
API_KEY_ENV_VAR = "DEPLOY_API_KEY"

#: Minimum plausible length for a key. Used only to catch obvious mistakes such
#: as an empty string or a truncated copy; it is not a format assertion.
MIN_API_KEY_LENGTH = 8


class AIConfigurationError(RuntimeError):
    """The AI layer cannot be configured.

    The message is safe to show to a user and safe to log: it never includes the
    credential value.
    """


@dataclass(frozen=True)
class AIConfig:
    """Resolved connection settings.

    ``api_key`` is marked ``repr=False`` so the generated ``__repr__`` omits it.
    Equality and hashing still consider it, which keeps two configs with
    different credentials distinct. It is declared first because it has no
    default and dataclasses require non-default fields to precede defaulted ones.
    """

    api_key: str = field(repr=False)
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL

    @property
    def chat_completions_url(self) -> str:
        """Full URL of the chat completions endpoint."""

        return f"{self.base_url.rstrip('/')}/chat/completions"

    def __repr__(self) -> str:
        """Show which endpoint and model are configured, never the key."""

        return (
            f"AIConfig(base_url={self.base_url!r}, model={self.model!r}, "
            f"api_key=<redacted>)"
        )

    def __str__(self) -> str:
        """Human-readable summary that never contains the key."""

        return self.__repr__()


def validate_api_key(api_key: str | None) -> str:
    """Return a usable API key or raise :class:`AIConfigurationError`.

    Rejects empty values, surrounding whitespace and characters that cannot be
    sent in an HTTP header. The error text describes the problem in terms of the
    variable name, never in terms of the value.
    """

    if api_key is None:
        raise AIConfigurationError(
            f"No AI API key was provided. Set the {API_KEY_ENV_VAR} environment "
            "variable or configure it in the application's secret store."
        )

    cleaned = api_key.strip()
    if not cleaned:
        raise AIConfigurationError(
            f"The AI API key is empty. Set the {API_KEY_ENV_VAR} environment "
            "variable or configure it in the application's secret store."
        )

    if cleaned != api_key:
        raise AIConfigurationError(
            "The AI API key contains leading or trailing whitespace. Re-enter the "
            "value without surrounding spaces or newlines."
        )

    if len(cleaned) < MIN_API_KEY_LENGTH:
        raise AIConfigurationError(
            f"The AI API key looks truncated (fewer than {MIN_API_KEY_LENGTH} "
            "characters). Re-enter the full value."
        )

    if any(not 33 <= ord(character) <= 126 for character in cleaned):
        raise AIConfigurationError(
            "The AI API key contains characters that cannot be used in an HTTP "
            "header. Re-enter the value as a single line of plain text."
        )

    return cleaned


def resolve_api_key(fallback_api_key: str | None = None) -> str:
    """Resolve the credential: environment first, then the caller's fallback.

    The application layer passes a value from its secret store as
    ``fallback_api_key``. That keeps Streamlit out of the AI package while still
    allowing a deployment that only configures Streamlit secrets.
    """

    from_environment = os.environ.get(API_KEY_ENV_VAR)
    if from_environment is not None:
        return validate_api_key(from_environment)

    return validate_api_key(fallback_api_key)


def load_config(
    *,
    fallback_api_key: str | None = None,
    base_url: str = DEFAULT_BASE_URL,
    model: str = DEFAULT_MODEL,
) -> AIConfig:
    """Build the connection settings.

    Parameters
    ----------
    fallback_api_key:
        A credential supplied by the application layer, used only when the
        environment does not define one.
    base_url, model:
        Overrides for testing. Production callers should rely on the defaults,
        which match the approved configuration.
    """

    if not base_url or not base_url.strip():
        raise AIConfigurationError("The AI base URL is empty.")
    if not model or not model.strip():
        raise AIConfigurationError("The AI model identifier is empty.")

    return AIConfig(
        api_key=resolve_api_key(fallback_api_key),
        base_url=base_url.strip(),
        model=model.strip(),
    )


def redact_secrets(text: str, *extra_secrets: str) -> str:
    """Return ``text`` with known secrets replaced by a placeholder.

    Used as a final guard before any provider text reaches a log line or an
    exception message. It also strips things that look like bearer tokens even
    when the exact key is not known to the caller.
    """

    redacted = text
    for secret in extra_secrets:
        if secret:
            redacted = redacted.replace(secret, "<redacted>")

    redacted = re.sub(
        r"(?i)bearer\s+[A-Za-z0-9._\-]{6,}", "Bearer <redacted>", redacted
    )
    redacted = re.sub(r"sk-[A-Za-z0-9_\-]{6,}", "<redacted>", redacted)
    return redacted


__all__ = [
    "API_KEY_ENV_VAR",
    "DEFAULT_BASE_URL",
    "DEFAULT_MODEL",
    "MIN_API_KEY_LENGTH",
    "AIConfig",
    "AIConfigurationError",
    "load_config",
    "redact_secrets",
    "resolve_api_key",
    "validate_api_key",
]
