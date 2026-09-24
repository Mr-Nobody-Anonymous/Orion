"""ORION coding subsystem: generation, analysis, sandboxed execution,
debugging, patching, and verification of candidate code.

The canonical sandbox implementation is :mod:`orion.coding.sandbox_v2`.
The legacy :mod:`orion.coding.sandbox` module is preserved as a thin
back-compatibility shim that re-exports the v2 surface.
"""

from .analysis import CodeAnalysis, analyze_source
from .debugging import FailureDiagnosis, FailureMode, SelfDebugger, diagnose
from .generation import GeneratedCandidate, StrategyCodeGenerator
from .patching import PatchApplier, PatchOperation, PatchResult
from .sandbox import CodeSandbox, SandboxResult, build_sandbox_program
from .sandbox_v2 import PolicyViolation, SandboxPolicy, run_isolated
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
    "PolicyViolation",
    "SandboxPolicy",
    "SandboxResult",
    "SelfDebugger",
    "StrategyCodeGenerator",
    "analyze_source",
    "build_sandbox_program",
    "diagnose",
    "run_isolated",
    "verify_candidate_source",
]

