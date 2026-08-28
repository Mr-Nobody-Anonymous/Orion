"""The autonomous research agent.

Pipeline: question → discovery → extraction → synthesis → hypotheses →
experiment proposals → (optionally) controlled execution → provenance.

The agent never claims evidence it does not have: when discovery is
unavailable it returns an explicit BLOCKED result, and every hypothesis
carries its source titles.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from ..infrastructure.provenance import ProvenanceStore
from .discovery import ResearchDiscovery, ResearchSource
from .experiments import ExperimentPipeline, ExperimentReport, ExperimentSpec, experiment_from_hypothesis
from .extraction import PaperProfile, extract_all
from .synthesis import Hypothesis, SynthesisReport, synthesize


@dataclass(frozen=True, slots=True)
class ResearchResult:
    question: str
    status: str  # "COMPLETED" | "BLOCKED"
    sources: tuple[ResearchSource, ...] = ()
    profiles: tuple[PaperProfile, ...] = ()
    synthesis: SynthesisReport | None = None
    hypotheses: tuple[Hypothesis, ...] = ()
    experiment: ExperimentReport | None = None
    reason: str = ""
    ran_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "question": self.question,
            "status": self.status,
            "reason": self.reason,
            "source_count": len(self.sources),
            "hypotheses": [
                {
                    "statement": h.statement,
                    "prediction": h.testable_prediction,
                    "sources": list(h.source_titles),
                }
                for h in self.hypotheses
            ],
        }
        if self.synthesis is not None:
            payload["evidence_status"] = self.synthesis.evidence_status
            payload["conflicts"] = [
                {"topic": c.topic, "supporting": list(c.supporting), "contradicting": list(c.contradicting)}
                for c in self.synthesis.conflicts
            ]
        if self.experiment is not None:
            payload["experiment"] = self.experiment.as_dict()
        return payload


class ResearchAgent:
    """Runs the research loop with provenance for every artifact."""

    def __init__(
        self,
        *,
        discovery: ResearchDiscovery | None = None,
        pipeline: ExperimentPipeline | None = None,
        provenance: ProvenanceStore | None = None,
        fetcher: Callable[[str], bytes] | None = None,
    ) -> None:
        self.provenance = provenance or ProvenanceStore()
        self._discovery = discovery or ResearchDiscovery(fetcher=fetcher)
        self._pipeline = pipeline or ExperimentPipeline(provenance=self.provenance)

    def investigate(
        self,
        question: str,
        prices: Any = None,
        *,
        limit: int = 5,
        run_experiment: bool = False,
        lookback: int = 3,
    ) -> ResearchResult:
        """Full loop. Experiment execution only happens when `run_experiment`
        is true AND usable price data is supplied."""
        if not question.strip():
            raise ValueError("a research question is required")
        try:
            sources = self._discovery.discover_papers(question, limit=limit)
        except Exception as error:  # network failure is a first-class outcome
            self.provenance.record(f"research-blocked:{question}", "research", "orion.research.agent", question,
                                   status="BLOCKED")
            return ResearchResult(question, "BLOCKED", reason=f"discovery unavailable: {error}")
        if not sources:
            return ResearchResult(question, "BLOCKED", reason="no public sources found for the question")
        for index, source in enumerate(sources):
            self.provenance.record(f"research-source:{index}:{question[:40]}", "paper_metadata",
                                   source.url, source.title, provider=source.source)
        profiles = extract_all(sources)
        synthesis = synthesize(question, profiles)
        hypotheses = synthesis.hypotheses
        experiment: ExperimentReport | None = None
        if run_experiment:
            if prices is None or len(prices) < 20:
                return ResearchResult(question, "BLOCKED", sources, profiles, synthesis, hypotheses,
                                      reason="experiment requested but fewer than 20 prices supplied")
            if not hypotheses:
                experiment = None
            else:
                spec = experiment_from_hypothesis(hypotheses[0], name=f"auto:{question[:40]}", lookback=lookback)
                experiment = self._pipeline.run(spec, prices)
        self.provenance.record(f"research:{question}", "research_result", "orion.research.agent",
                               question, status="COMPLETED", sources=len(sources),
                               hypotheses=len(hypotheses))
        return ResearchResult(question, "COMPLETED", sources, profiles, synthesis, hypotheses, experiment)
