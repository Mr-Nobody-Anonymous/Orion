"""ORION coding subsystem: generation, analysis, sandboxed execution,
debugging, patching, and verification of candidate code."""

from .analysis import CodeAnalysis, analyze_source
from .debugging import FailureDiagnosis, FailureMode, SelfDebugger, diagnose
from .generation import GeneratedCandidate, StrategyCodeGenerator
from .patching import PatchApplier, PatchOperation, PatchResult
from .sandbox import CodeSandbox, SandboxResult, build_sandbox_program
from .verification import CodeVerification, verify_candidate_source

__all__ = [
    "CodeAnalysis",
    "CodeSandbox",
    "CodeVerification",
    "FailureDiagnosis",
    "FailureMode",
    "GeneratedCandidate",
    "PatchApplier",
    "PatchOperation",
    "PatchResult",
    "SandboxResult",
    "SelfDebugger",
    "StrategyCodeGenerator",
    "analyze_source",
    "build_sandbox_program",
    "diagnose",
    "verify_candidate_source",
]

