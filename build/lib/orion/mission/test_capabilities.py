"""Deterministic, sandboxed test capabilities for the mission vertical slice.

Phase 1 ORION 2.0, corrections #20 and #22. These capabilities:

* are LOW-risk and registered in an ISOLATED
  :class:`~orion.intelligence.capability_registry.CapabilityRegistry`
  (the default registry is untouched);
* operate only inside a sandbox directory constructed by the test —
  a path that resolves outside the sandbox is refused, so the agent
  can never read the user's real filesystem;
* are fully deterministic and produce simulated costs only — no real
  money, no network, no live brokerage.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from ..agent.executor import CapabilityExecutor, CapabilityResult
from ..intelligence.capability_registry import (
    CapabilityKind,
    CapabilityRegistry,
    IntegrationMode,
    Plane,
    RiskLevel,
    Tool,
)

_SOURCE = "src/orion/mission/test_capabilities.py"


def write_sandbox_documents(root: Path, docs: list[tuple[str, str]]) -> Path:
    """Create the fake test documents inside the sandbox directory."""
    root.mkdir(parents=True, exist_ok=True)
    for name, text in docs:
        (root / name).write_text(text, encoding="utf-8")
    return root


def _result(
    capability, payload, *, sandbox, success=True, error="", provenance_extra=None
):
    provenance = {
        "sandbox_root": str(sandbox),
        "capability_source": _SOURCE,
    }
    if provenance_extra:
        provenance.update(provenance_extra)
    return CapabilityResult(
        capability=capability,
        success=success,
        output=payload,
        error=error,
        cost_units=1.0,  # simulated cost; every action costs 1 unit
        provenance=provenance,
        reproducibility={"deterministic": True},
    )


def _impl(name, fn):
    def run(input: Mapping[str, Any], context, constraints) -> CapabilityResult:
        return fn(input)

    run.__name__ = f"impl_{name}"
    return run


def _register(registry: CapabilityRegistry, name: str, description: str) -> None:
    registry.register(
        Tool(
            name=name,
            kind=CapabilityKind.DATA,
            plane=Plane.INTELLIGENCE,
            integration=IntegrationMode.DEPENDENCY,
            source=_SOURCE,
            description=description,
            permissions=frozenset({"read_data"}),
            risk=RiskLevel.LOW,
        )
    )


def build_test_executor(sandbox: Path) -> CapabilityExecutor:
    """Build an isolated registry + executor with the four test tools."""
    sandbox = Path(sandbox)
    registry = CapabilityRegistry()

    # ------------------------------------------------ test.fs.discover
    def discover(input):
        names = sorted(p.name for p in sandbox.glob("*.txt"))
        return _result(
            "test.fs.discover",
            {"documents": names, "n_documents": len(names)},
            sandbox=sandbox,
        )

    # --------------------------------------------------- test.fs.read
    def read(input):
        requested = input.get("path")
        if requested is not None:
            resolved = Path(requested).resolve()
            if sandbox.resolve() not in resolved.parents:
                return _result(
                    "test.fs.read",
                    {},
                    sandbox=sandbox,
                    success=False,
                    error=f"path {requested!r} is outside the sandbox",
                )
        docs = {}
        for path in sorted(sandbox.glob("*.txt")):
            docs[path.stem] = path.read_text(encoding="utf-8")
        return _result(
            "test.fs.read",
            {"contents": docs, "n_documents": len(docs)},
            sandbox=sandbox,
        )

    # --------------------------------------------- test.text.summarize
    def summarize(input):
        docs = {
            path.stem: path.read_text(encoding="utf-8")
            for path in sorted(sandbox.glob("*.txt"))
        }
        lines = [f"{stem}: {text.split('.')[0]}." for stem, text in docs.items()]
        summary = "\n".join(lines)
        return _result(
            "test.text.summarize",
            {
                "summary": summary,
                "n_documents": len(docs),
                "documents": sorted(docs),
            },
            sandbox=sandbox,
            provenance_extra={"summary": summary},
        )

    # ---------------------------------------------- test.text.validate
    def validate(input):
        docs = sorted(p.stem for p in sandbox.glob("*.txt"))
        summary = str(input.get("summary", ""))
        missing = [d for d in docs if d not in summary]
        valid = not missing
        return _result(
            "test.text.validate",
            {
                "valid": valid,
                "missing": missing,
                "n_documents": len(docs),
            },
            sandbox=sandbox,
            success=valid,
            error="" if valid else f"summary missing: {missing}",
        )

    implementations = {}
    for name, fn, description in (
        ("test.fs.discover", discover, "List test documents in the sandbox"),
        ("test.fs.read", read, "Read test documents inside the sandbox only"),
        ("test.text.summarize", summarize, "Summarize sandbox documents deterministically"),
        ("test.text.validate", validate, "Validate the summary covers every document"),
    ):
        _register(registry, name, description)
        implementations[name] = _impl(name, fn)

    return CapabilityExecutor(registry=registry, implementations=implementations)


__all__ = ["build_test_executor", "write_sandbox_documents"]
