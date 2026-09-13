"""Tests for the env-driven cloud provider factory (no network calls)."""

from __future__ import annotations

import pytest

from orion.models.cloud import (
    CohereProvider,
    DeepSeekProvider,
    GeminiProvider,
    MistralProvider,
    OpenRouterProvider,
    cloud_provider_status,
    create_cloud_providers_from_env,
)


@pytest.fixture(autouse=True)
def _clean_keys(monkeypatch: pytest.MonkeyPatch):
    for var in (
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
        "OPENAI_BASE_URL",
        "OPENROUTER_API_KEY",
        "OPENROUTER_MODEL",
        "OPENROUTER_BASE_URL",
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_MODEL",
        "DEEPSEEK_BASE_URL",
        "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "AZURE_OPENAI_API_KEY",
        "COHERE_API_KEY",
        "MISTRAL_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


class TestFactory:
    def test_no_keys_no_providers(self) -> None:
        assert create_cloud_providers_from_env() == []

    def test_openai_key_activates_openai(self, monkeypatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        providers = create_cloud_providers_from_env()
        assert [p.name for p in providers] == ["openai"]
        assert providers[0].status().available is True

    def test_gemini_key_activates_gemini(self, monkeypatch) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "g-key")
        providers = create_cloud_providers_from_env()
        assert [p.name for p in providers] == ["gemini"]
        assert isinstance(providers[0], GeminiProvider)

    def test_status_is_redacted(self, monkeypatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-verysecret-value")
        status = cloud_provider_status()
        assert status and all("verysecret" not in str(s) for s in status)

    def test_gemini_reads_google_fallback(self, monkeypatch) -> None:
        monkeypatch.setenv("GOOGLE_API_KEY", "fallback")
        providers = create_cloud_providers_from_env()
        assert [p.name for p in providers] == ["gemini"]

    def test_cohere_key_activates_cohere(self, monkeypatch) -> None:
        monkeypatch.setenv("COHERE_API_KEY", "co-test")
        providers = create_cloud_providers_from_env()
        assert [p.name for p in providers] == ["cohere"]
        assert isinstance(providers[0], CohereProvider)
        assert providers[0].status().available is True

    def test_mistral_key_activates_mistral(self, monkeypatch) -> None:
        monkeypatch.setenv("MISTRAL_API_KEY", "m-test")
        providers = create_cloud_providers_from_env()
        assert [p.name for p in providers] == ["mistral"]
        assert isinstance(providers[0], MistralProvider)
        assert providers[0].status().available is True

    def test_multiple_keys_activate_multiple_providers(self, monkeypatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("COHERE_API_KEY", "co-test")
        monkeypatch.setenv("MISTRAL_API_KEY", "m-test")
        names = [p.name for p in create_cloud_providers_from_env()]
        assert "openai" in names
        assert "cohere" in names
        assert "mistral" in names

    # ------------------------------------------------------------ openrouter

    def test_openrouter_key_activates_openrouter(self, monkeypatch) -> None:
        monkeypatch.setenv("OPENROUTER_API_KEY", "or-test")
        providers = create_cloud_providers_from_env()
        assert [p.name for p in providers] == ["openrouter"]
        assert isinstance(providers[0], OpenRouterProvider)
        assert providers[0].status().available is True

    def test_openrouter_free_model_env_is_honoured(self, monkeypatch) -> None:
        monkeypatch.setenv("OPENROUTER_API_KEY", "or-test")
        monkeypatch.setenv("OPENROUTER_MODEL", "deepseek/deepseek-chat-v3.1:free")
        provider = create_cloud_providers_from_env()[0]
        assert provider.config.model == "deepseek/deepseek-chat-v3.1:free"

    def test_openrouter_endpoint_env_is_honoured(self, monkeypatch) -> None:
        monkeypatch.setenv("OPENROUTER_API_KEY", "or-test")
        monkeypatch.setenv("OPENROUTER_BASE_URL", "https://gateway.example/api/v1")
        provider = create_cloud_providers_from_env()[0]
        assert provider.config.endpoint == "https://gateway.example/api/v1"

    # -------------------------------------------------------------- deepseek

    def test_deepseek_key_activates_deepseek(self, monkeypatch) -> None:
        monkeypatch.setenv("DEEPSEEK_API_KEY", "ds-test")
        providers = create_cloud_providers_from_env()
        assert [p.name for p in providers] == ["deepseek"]
        assert isinstance(providers[0], DeepSeekProvider)
        assert providers[0].status().available is True

    def test_deepseek_model_env_is_honoured(self, monkeypatch) -> None:
        monkeypatch.setenv("DEEPSEEK_API_KEY", "ds-test")
        monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-reasoner")
        provider = create_cloud_providers_from_env()[0]
        assert provider.config.model == "deepseek-reasoner"

    def test_deepseek_endpoint_env_is_honoured(self, monkeypatch) -> None:
        monkeypatch.setenv("DEEPSEEK_API_KEY", "ds-test")
        monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://mirror.example/v1")
        provider = create_cloud_providers_from_env()[0]
        assert provider.config.endpoint == "https://mirror.example/v1"

    # --------------------------------------------- OpenAI gateway overrides

    def test_openai_model_env_is_honoured(self, monkeypatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("OPENAI_MODEL", "deepseek-v4-flash")
        provider = create_cloud_providers_from_env()[0]
        assert provider.config.model == "deepseek-v4-flash"

    def test_openai_base_url_env_is_honoured(self, monkeypatch) -> None:
        # The OpenAI provider routes through any OpenAI-compatible gateway
        # (e.g. Token Harbor, Groq) when OPENAI_BASE_URL is configured.
        monkeypatch.setenv("OPENAI_API_KEY", "th-test")
        monkeypatch.setenv("OPENAI_BASE_URL", "https://api.tokenharbor.ai/v1")
        provider = create_cloud_providers_from_env()[0]
        assert provider.config.endpoint == "https://api.tokenharbor.ai/v1"

    def test_openai_constructor_beats_env(self, monkeypatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("OPENAI_MODEL", "from-env")
        monkeypatch.setenv("OPENAI_BASE_URL", "https://env.example/v1")
        provider = create_cloud_providers_from_env()[0]
        assert provider.config.model == "from-env"
        assert provider.config.endpoint == "https://env.example/v1"
        from orion.models.cloud import OpenAIProvider

        explicit = OpenAIProvider(api_key="k", model="explicit", endpoint="https://explicit.example/v1")
        assert explicit.config.model == "explicit"
        assert explicit.config.endpoint == "https://explicit.example/v1"
