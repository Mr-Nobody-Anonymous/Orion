"""Cross-paper synthesis: agreement, conflict detection, hypothesis generation.

Every synthesized claim carries the provenance of the profiles it came from.
Conflicting evidence is preserved and labeled, never averaged away.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Sequence

from .extraction import PaperProfile


@dataclass(frozen=True, slots=True)
class MethodConsensus:
    method: str
    paper_count: int
    papers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EvidenceConflict:
    topic: str
    supporting: tuple[str, ...]
    contradicting: tuple[str, ...]
    resolution: str  # "unresolved" until a controlled experiment runs


@dataclass(frozen=True, slots=True)
class Hypothesis:
    statement: str
    rationale: str
    testable_prediction: str
    source_titles: tuple[str, ...]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True, slots=True)
class SynthesisReport:
    question: str
    profiles: tuple[PaperProfile, ...]
    consensus_methods: tuple[MethodConsensus, ...]
    agreements: tuple[str, ...]
    conflicts: tuple[EvidenceConflict, ...]
    hypotheses: tuple[Hypothesis, ...]
    evidence_status: str

    @property
    def has_conflicts(self) -> bool:
        return bool(self.conflicts)


def _method_consensus(profiles: Sequence[PaperProfile]) -> tuple[MethodConsensus, ...]:
    index: dict[str, list[str]] = {}
    for profile in profiles:
        for method in profile.methods:
            index.setdefault(method, []).append(profile.source.title)
    consensus = tuple(
        MethodConsensus(method, len(titles), tuple(titles))
        for method, titles in sorted(index.items(), key=lambda kv: -len(kv[1]))
    )
    return consensus


def _detect_conflicts(profiles: Sequence[PaperProfile]) -> tuple[EvidenceConflict, ...]:
    """Detect conflicting directional evidence on shared method families."""
    conflicts: list[EvidenceConflict] = []
    by_method: dict[str, list[PaperProfile]] = {}
    for profile in profiles:
        for method in profile.methods:
            by_method.setdefault(method, []).append(profile)
    for method, group in sorted(by_method.items()):
        positive = tuple(p.source.title for p in group if p.dominant_direction == "positive")
        negative = tuple(p.source.title for p in group if p.dominant_direction == "negative")
        if positive and negative:
            conflicts.append(EvidenceConflict(
                topic=method,
                supporting=positive,
                contradicting=negative,
                resolution="unresolved",
            ))
    return tuple(conflicts)


def generate_hypotheses(question: str, profiles: Sequence[PaperProfile]) -> tuple[Hypothesis, ...]:
    """Generate falsifiable hypotheses grounded in the extracted evidence.

    A hypothesis is only produced when at least one source reports a
    directional finding; ORION does not invent hypotheses from nothing.
    """
    hypotheses: list[Hypothesis] = []
    for profile in profiles:
        positive_claims = [c for c in profile.claims if c.direction == "positive"]
        negative_claims = [c for c in profile.claims if c.direction == "negative"]
        for claim in positive_claims[:1]:
            method_hint = profile.methods[0] if profile.methods else "the studied method"
            hypotheses.append(Hypothesis(
                statement=f"{method_hint.replace('_', ' ').title()} signal retains out-of-sample predictive power on current data.",
                rationale=f"Derived from: '{claim.sentence}' in '{profile.source.title}'.",
                testable_prediction="Walk-forward strategy using this signal achieves positive out-of-sample risk-adjusted return.",
                source_titles=(profile.source.title,),
            ))
        for claim in negative_claims[:1]:
            method_hint = profile.methods[0] if profile.methods else "the studied method"
            hypotheses.append(Hypothesis(
                statement=f"{method_hint.replace('_', ' ').title()} signal has decayed and no longer predicts out-of-sample returns.",
                rationale=f"Derived from: '{claim.sentence}' in '{profile.source.title}'.",
                testable_prediction="Walk-forward strategy using this signal fails to beat a buy-and-hold baseline out of sample.",
                source_titles=(profile.source.title,),
            ))
    return tuple(hypotheses)


def synthesize(question: str, profiles: Sequence[PaperProfile]) -> SynthesisReport:
    if not profiles:
        raise ValueError("at least one paper profile is required")
    consensus = _method_consensus(profiles)
    agreements = tuple(
        f"{c.method}: reported by {c.paper_count} papers" for c in consensus if c.paper_count >= 2
    )
    conflicts = _detect_conflicts(profiles)
    hypotheses = generate_hypotheses(question, profiles)
    sufficient = len(profiles) >= 2 and bool(hypotheses)
    return SynthesisReport(
        question=question,
        profiles=tuple(profiles),
        consensus_methods=consensus,
        agreements=agreements,
        conflicts=conflicts,
        hypotheses=hypotheses,
        evidence_status="SUFFICIENT_FOR_EXPERIMENT" if sufficient else "INSUFFICIENT_EVIDENCE",
    )
