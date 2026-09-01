"""Tests for the env-driven cloud provider factory (no network calls)."""

from __future__ import annotations

import pytest

from orion.models.cloud import (
    CohereProvider,
    GeminiProvider,
    MistralProvider,
    cloud_provider_status,
    create_cloud_providers_from_env,
)


@pytest.fixture(autouse=True)
def _clean_keys(monkeypatch: pytest.MonkeyPatch):
    for var in (
        "OPENAI_API_KEY",
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