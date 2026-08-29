"""Tests for the peer-AI council (no network: fake providers only)."""

from __future__ import annotations

import pytest

from orion.intelligence.peer_ai import PeerAICouncil, PeerInsight, _extract_json
from orion.models.cloud.base import CloudProviderError, CloudProviderStatus, HttpCloudConfig


class FakePeer:
    """Minimal stand-in for BaseHttpCloudProvider."""

    def __init__(self, name: str, reply: str | None = None, error: Exception | None = None) -> None:
        self.name = name
        self.reply = reply
        self.error = error
        self.config = HttpCloudConfig(endpoint="https://example.invalid", api_key="k", model="fake-1")

    def status(self) -> CloudProviderStatus:
        return CloudProviderStatus(name=self.name, available=True, endpoint="https://example.invalid", model="fake-1")

    def generate(self, prompt: str, *, system: str | None = None, **kwargs) -> str:
        if self.error is not None:
            raise self.error
        return self.reply or ""


GOOD_REPLY = (
    '{"thesis": "Momentum favours risk-on into month end.", "confidence": 0.62, '
    '"rationale": "Breadth improving.", "risks": [" CPI surprise", "gap risk"]}'
)
FENCED_REPLY = "```json\n{\"thesis\": \"t\", \"confidence\": 0.5, \"rationale\": \"r\", \"risks\": []}\n```"


class TestExtractJson:
    def test_plain(self) -> None:
        assert _extract_json(GOOD_REPLY)["confidence"] == pytest.approx(0.62)

    def test_fenced(self) -> None:
        assert _extract_json(FENCED_REPLY)["thesis"] == "t"

    def test_garbage_raises(self) -> None:
        with pytest.raises(ValueError):
            _extract_json("no json here at all")


class TestCouncil:
    def test_unavailable_without_providers(self) -> None:
        council = PeerAICouncil(providers=[])
        assert not council.available
        assert council.deliberate("question?") == []
        assert council.consensus() is None

    def test_good_reply_becomes_insight(self) -> None:
        council = PeerAICouncil(providers=[FakePeer("openai", GOOD_REPLY)])
        insights = council.deliberate("what is the regime?")
        assert len(insights) == 1
        insight = insights[0]
        assert isinstance(insight, PeerInsight)
        assert insight.provider == "openai"
        assert insight.confidence == pytest.approx(0.62)
        assert insight.risks == ("CPI surprise", "gap risk")
        assert council.consensus()["mean_confidence"] == pytest.approx(0.62)
        assert council.lessons_from_peers()

    def test_failure_is_recorded_not_raised(self) -> None:
        council = PeerAICouncil(
            providers=[
                FakePeer("broken", error=CloudProviderError("timeout")),
                FakePeer("good", GOOD_REPLY),
            ]
        )
        insights = council.deliberate("question?")
        assert len(insights) == 1
        assert len(council.failures) == 1
        assert council.failures[0].provider == "broken"

    def test_malformed_json_counts_as_failure(self) -> None:
        council = PeerAICouncil(providers=[FakePeer("loopy", "the market is fine, trust me")])
        assert council.deliberate("q") == []
        assert len(council.failures) == 1

    def test_empty_question_rejected(self) -> None:
        council = PeerAICouncil(providers=[FakePeer("x", GOOD_REPLY)])
        with pytest.raises(ValueError):
            council.deliberate("   ")
