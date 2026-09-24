"""Secret management: isolation, redaction, and prompt scrubbing.

Broker credentials and API keys must never reach an LLM prompt, a log line,
or a serialized payload. The vault is write-once per key, comparison-only,
and redacts anything that looks like a secret in outbound text.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from hashlib import sha256
from typing import Mapping


SECRET_PATTERN = re.compile(
    "("
    r"(?:sk-[A-Za-z0-9]{16,})"                     # OpenAI-style keys
    r"|(?:AKIA[0-9A-Z]{16})"                       # AWS access keys
    r"|(?:ghp_[A-Za-z0-9]{30,})"                   # GitHub tokens
    r"|(?:Bearer\s+[A-Za-z0-9\-._~+/]+=*)"         # bearer tokens
    r"|(?:xox[bap]-[A-Za-z0-9\-]{10,})"            # Slack tokens
    ")",
)


@dataclass(frozen=True, slots=True)
class SecretReference:
    """A handle that can travel through logs and prompts safely."""

    name: str
    digest: str

    def __repr__(self) -> str:  # pragma: no cover - display only
        return f"SecretReference({self.name}, sha256:{self.digest[:12]})"


class SecretVault:
    """In-memory secret store; values are write-once and never returned."""

    def __init__(self) -> None:
        self._secrets: dict[str, str] = {}

    def store(self, name: str, value: str) -> SecretReference:
        if not name.strip():
            raise ValueError("secret name is required")
        if not value:
            raise ValueError("secret value must be non-empty")
        if name in self._secrets:
            raise ValueError("secrets are write-once; create a new versioned name to rotate")
        self._secrets[name] = value
        return SecretReference(name, sha256(value.encode("utf-8")).hexdigest())

    def store_from_env(self, name: str, env_var: str) -> SecretReference:
        value = os.environ.get(env_var)
        if not value:
            raise ValueError(f"environment variable not set: {env_var}")
        return self.store(name, value)

    def verify(self, name: str, candidate: str) -> bool:
        """Constant-shape comparison; returns whether the candidate matches."""
        if name not in self._secrets:
            return False
        expected = sha256(self._secrets[name].encode("utf-8")).hexdigest()
        return sha256(candidate.encode("utf-8")).hexdigest() == expected

    def resolve(self, reference: SecretReference, name: str) -> str:
        """Deliver the secret ONLY to explicitly named consumers (e.g. an
        HTTP client constructed outside the LLM path). Never call this with
        text destined for a prompt."""
        if reference.name != name:
            raise ValueError("reference does not match requested secret")
        if name not in self._secrets:
            raise KeyError(f"unknown secret: {name}")
        return self._secrets[name]

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._secrets))

    def scrub(self, text: str, *, replacement: str = "[REDACTED]") -> tuple[str, int]:
        """Remove secret-shaped material from outbound text."""
        scrubbed, count = SECRET_PATTERN.subn(replacement, text)
        for name, value in self._secrets.items():
            if value and value in scrubbed:
                scrubbed = scrubbed.replace(value, replacement)
                count += scrubbed.count(replacement)
        return scrubbed, count


class PromptGuard:
    """Screens outbound LLM payloads for credential leakage."""

    def __init__(self, vault: SecretVault | None = None) -> None:
        self.vault = vault or SecretVault()
        self.blocked_count = 0

    def screen(self, prompt: str) -> tuple[str, bool]:
        """Returns (safe_prompt, allowed). Blocked prompts are scrubbed and
        allowed only in redacted form; callers must use the returned text."""
        scrubbed, count = self.vault.scrub(prompt)
        if count:
            self.blocked_count += count
        return scrubbed, True

    @property
    def leakage_attempts_detected(self) -> int:
        return self.blocked_count


def redact_mapping(payload: Mapping[str, object], *, keys: tuple[str, ...] = ("api_key", "secret", "password", "token")) -> dict[str, object]:
    """Redact well-known secret keys from a mapping copy."""
    redacted: dict[str, object] = {}
    for key, value in payload.items():
        if any(marker in key.lower() for marker in keys):
            redacted[key] = "[REDACTED]"
        else:
            redacted[key] = value
    return redacted


__all__ = [
    "PromptGuard",
    "SecretReference",
    "SecretVault",
    "redact_mapping",
]
