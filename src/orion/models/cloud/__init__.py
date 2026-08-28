"""ORION cloud LLM providers.

Every cloud capability is opt-in. ``NullCloudProvider`` is the
default stub that raises ``CloudProviderUnavailable`` so that no
infrastructure may make a silent cloud call.

The four shipping providers — :class:`OpenAIProvider`,
:class:`AnthropicProvider`, :class:`AzureOpenAIProvider`, and
:class:`HttpProvider` — share the same :class:`BaseHttpCloudProvider`
transport: stdlib-only, bounded retries, credential-redacted
status, explicit refusal to issue a request without a configured
``api_key``.

None of these providers log the API key. Diagnostic surfaces
redact the credential to ``ab****yz`` style.
"""

from __future__ import annotations

from .anthropic import AnthropicProvider
from .azure_openai import AzureOpenAIProvider
from .base import (
    BaseHttpCloudProvider,
    CloudProviderError,
    CloudProviderStatus,
    HttpCloudConfig,
    env_or_none,
)
from .http import HttpProvider
from .openai import OpenAIProvider
from .provider import CloudProviderUnavailable, NullCloudProvider

__all__ = [
    "AnthropicProvider",
    "AzureOpenAIProvider",
    "BaseHttpCloudProvider",
    "CloudProviderError",
    "CloudProviderStatus",
    "CloudProviderUnavailable",
    "HttpCloudConfig",
    "HttpProvider",
    "NullCloudProvider",
    "OpenAIProvider",
    "env_or_none",
]
