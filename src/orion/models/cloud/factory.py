"""Env-driven cloud provider factory.

Reads every supported provider's credential from the process
environment (populated from ``.env`` by
:func:`orion.infrastructure.env.load_env`) and returns **only the
providers that are actually configured**. Nothing here fabricates
availability: a provider without a key is simply absent from the
result, so callers can trust that a returned provider will accept
requests (modulo network conditions).
"""

from __future__ import annotations

from ...infrastructure.env import load_env
from .anthropic import AnthropicProvider
from .azure_openai import AzureOpenAIProvider
from .base import BaseHttpCloudProvider
from .gemini import GeminiProvider
from .openai import OpenAIProvider


def create_cloud_providers_from_env(*, load_dotenv: bool = True) -> list[BaseHttpCloudProvider]:
    """Build every cloud provider whose API key is configured.

    ``load_dotenv`` loads a repository-root ``.env`` first (without
    overriding real environment variables) so operators only need one
    file. Missing credentials simply omit the provider.
    """
    if load_dotenv:
        load_env()
    providers: list[BaseHttpCloudProvider] = []

    def _try(name: str, construct):  # type: ignore[no-untyped-def]
        try:
            provider = construct()
            if provider.config.api_key:
                providers.append(provider)
        except Exception:  # noqa: BLE001 - a broken optional provider must never break startup
            return

    _try("openai", OpenAIProvider)
    _try("anthropic", AnthropicProvider)
    _try("gemini", GeminiProvider)
    _try("azure-openai", AzureOpenAIProvider)
    return providers


def cloud_provider_status() -> list[dict[str, object]]:
    """Redacted status of every configured cloud provider."""
    return [provider.status().as_dict() for provider in create_cloud_providers_from_env()]