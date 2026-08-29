"""Peer-AI council: learn from other AI systems through their APIs.

Every cloud provider configured in the environment (``.env`` or OS
env — OpenAI, Anthropic, Gemini, Azure OpenAI) becomes a *peer* that
ORION can consult. A deliberation asks each peer the same structured
question, requires a strict-JSON answer, and stores the result as a
:class:`PeerInsight` with full provenance (provider, model, timestamp,
question hash).

Failure policy
--------------

A peer that errors, times out, or returns unparseable output is
recorded as a failure and *skipped*, never allowed to break the
council. An empty provider list means the council is unavailable —
it reports that honestly instead of pretending to deliberate.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Sequence

from ..models.cloud.base import BaseHttpCloudProvider, CloudProviderError
from ..models.cloud.factory import create_cloud_providers_from_env

PEER_SYSTEM_PROMPT = (
    "You are a peer analyst consulted by ORION, an autonomous financial "
    "intelligence system. Answer with STRICT JSON only (no markdown, no "
    "prose outside the JSON object) using exactly these keys: "
    '{"thesis": string, "confidence": number between 0 and 1, '
    '"rationale": string, "risks": array of strings}. '
    "Be specific, calibrated, and concise. If you are uncertain, lower "
    "the confidence rather than hedging in prose."
)


@dataclass(frozen=True, slots=True)
class PeerInsight:
    provider: str
    model: str
    thesis: str
    confidence: float
    rationale: str
    risks: tuple[str, ...]
    question: str
    question_hash: str
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "thesis": self.thesis,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "risks": list(self.risks),
            "question": self.question,
            "question_hash": self.question_hash,
            "retrieved_at": self.retrieved_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class PeerFailure:
    provider: str
    error: str
    question_hash: str
    failed_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "error": self.error[:200],
            "question_hash": self.question_hash,
            "failed_at": self.failed_at.isoformat(),
        }


def _extract_json(text: str) -> dict[str, Any]:
    """Extract the first JSON object from a peer response."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.startswith("json"):
            stripped = stripped[4:]
        stripped = stripped.strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no JSON object found in peer response")
    parsed = json.loads(stripped[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("peer response JSON is not an object")
    return parsed


class PeerAICouncil:
    """Consult every configured external AI and keep the insights."""

    def __init__(
        self,
        providers: Sequence[BaseHttpCloudProvider] | None = None,
        *,
        max_insights: int = 500,
        max_failures: int = 200,
    ) -> None:
        self._providers = list(providers) if providers is not None else create_cloud_providers_from_env()
        self.insights: list[PeerInsight] = []
        self.failures: list[PeerFailure] = []
        self._max_insights = max_insights
        self._max_failures = max_failures

    # ------------------------------------------------------------- status

    @property
    def available(self) -> bool:
        return bool(self._providers)

    def peers(self) -> list[dict[str, Any]]:
        return [provider.status().as_dict() for provider in self._providers]

    def status(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "peers": self.peers(),
            "insights": len(self.insights),
            "failures": len(self.failures),
        }

    # -------------------------------------------------------- deliberation

    def deliberate(self, question: str, *, max_tokens: int = 700) -> list[PeerInsight]:
        """Ask every configured peer; return the insights gathered now."""
        if not question.strip():
            raise ValueError("question must be non-empty")
        if not self._providers:
            return []
        question_hash = hashlib.sha256(question.strip().encode("utf-8")).hexdigest()[:16]
        gathered: list[PeerInsight] = []
        for provider in self._providers:
            try:
                raw = provider.generate(
                    question,
                    system=PEER_SYSTEM_PROMPT,
                    max_tokens=max_tokens,
                    temperature=0.3,
                )
                parsed = _extract_json(raw)
                insight = PeerInsight(
                    provider=provider.name,
                    model=provider.config.model,
                    thesis=str(parsed.get("thesis", ""))[:2000],
                    confidence=max(0.0, min(1.0, float(parsed.get("confidence", 0.0)))),
                    rationale=str(parsed.get("rationale", ""))[:4000],
                    risks=tuple(str(r).strip()[:300] for r in parsed.get("risks", []) if r),
                    question=question,
                    question_hash=question_hash,
                )
                gathered.append(insight)
                self._remember(insight)
            except (CloudProviderError, ValueError, TypeError, KeyError, RuntimeError, OSError) as exc:
                # Per-peer failure never breaks the council. A peer that
                # raised a bare ``RuntimeError`` is still surfaced via
                # ``peer_status()`` (see the ``last_error`` field).
                self._remember_failure(PeerFailure(provider.name, str(exc), question_hash))
        return gathered

    def _remember(self, insight: PeerInsight) -> None:
        self.insights.append(insight)
        if len(self.insights) > self._max_insights:
            self.insights.pop(0)

    def _remember_failure(self, failure: PeerFailure) -> None:
        self.failures.append(failure)
        if len(self.failures) > self._max_failures:
            self.failures.pop(0)

    # ------------------------------------------------------------- lessons

    def lessons_from_peers(self, topic: str | None = None) -> list[str]:
        """Compact lesson lines from stored insights (for the learning loop)."""
        lessons: list[str] = []
        for insight in reversed(self.insights):
            if topic and topic.lower() not in insight.thesis.lower() and topic.lower() not in insight.rationale.lower():
                continue
            lessons.append(
                f"[{insight.provider}/{insight.model} conf={insight.confidence:.2f}] "
                f"{insight.thesis} || risks: {'; '.join(insight.risks) if insight.risks else 'none stated'}"
            )
        return lessons

    def consensus(self) -> dict[str, Any] | None:
        """Aggregate the current insights into a crude consensus view."""
        if not self.insights:
            return None
        mean_conf = sum(i.confidence for i in self.insights) / len(self.insights)
        by_provider = {i.provider: i.confidence for i in self.insights}
        return {
            "mean_confidence": round(mean_conf, 4),
            "insight_count": len(self.insights),
            "per_provider": by_provider,
            "top_risks": sorted(
                {risk for i in self.insights for risk in i.risks},
                key=len,
                reverse=True,
            )[:5],
        }

    def recent_insights(self, count: int = 20) -> list[PeerInsight]:
        """Return up to ``count`` most recent insights (bounded, never None)."""
        if count < 1:
            raise ValueError("count must be at least one")
        # ``insights`` is already a bounded deque; this is the formal reader.
        return list(self.insights)[-count:]

    def peer_status(self) -> list[dict[str, Any]]:
        """Per-peer health snapshot: model, availability, last insight / error."""
        latest_insight: dict[str, datetime] = {}
        for insight in self.insights:
            latest_insight[insight.provider] = insight.retrieved_at
        latest_failure: dict[str, datetime] = {}
        latest_error: dict[str, str] = {}
        for failure in self.failures:
            if failure.provider not in latest_failure or failure.failed_at > latest_failure[failure.provider]:
                latest_failure[failure.provider] = failure.failed_at
                latest_error[failure.provider] = failure.error
        statuses: list[dict[str, Any]] = []
        for provider in self._providers:
            config = provider.config
            entry = {
                "provider": provider.name,
                "model": config.model,
                "endpoint": config.endpoint,
                "available": bool(config.api_key),
                "last_insight_at": latest_insight[provider.name].isoformat() if provider.name in latest_insight else None,
                "last_error_at": latest_failure[provider.name].isoformat() if provider.name in latest_failure else None,
                "last_error": latest_error.get(provider.name),
            }
            statuses.append(entry)
        return statuses