"""ORION research subsystem: discovery, extraction, synthesis, experiments,
replication, and the autonomous research agent."""

from .agent import ResearchAgent, ResearchResult
from .discovery import ResearchDiscovery, ResearchReport, ResearchSource, build_research_report
from .experiments import (
    ExperimentPipeline,
    ExperimentReport,
    ExperimentSpec,
    StageResult,
    experiment_from_hypothesis,
)
from .extraction import ExtractedClaim, PaperProfile, extract_all, extract_profile
from .replication import ReplicationReport, ReplicationTrial, replicate
from .synthesis import (
    EvidenceConflict,
    Hypothesis,
    MethodConsensus,
    SynthesisReport,
    generate_hypotheses,
    synthesize,
)

__all__ = [
    "EvidenceConflict",
    "ExperimentPipeline",
    "ExperimentReport",
    "ExperimentSpec",
    "ExtractedClaim",
    "Hypothesis",
    "MethodConsensus",
    "PaperProfile",
    "ReplicationReport",
    "ReplicationTrial",
    "ResearchAgent",
    "ResearchDiscovery",
    "ResearchReport",
    "ResearchResult",
    "ResearchSource",
    "StageResult",
    "SynthesisReport",
    "build_research_report",
    "experiment_from_hypothesis",
    "extract_all",
    "extract_profile",
    "generate_hypotheses",
    "replicate",
    "synthesize",
]

