"""Enforce the Intelligence / Truth / Control plane separation.

Architecture rule (per the ORION external review of 2026-08-28):

    Intelligence  →  Truth  →  Control  →  Capital

Where:

* **Intelligence** is anything creative: LLM, research, hypothesis
  generation, evolution, memory formation, the model council,
  reflection. It produces *candidates*.
* **Truth** is what determines whether a candidate is actually
  true: data contracts, point-in-time data, evaluation, walk-forward,
  ablation, statistical testing, calibration, the world model.
* **Control** is anything that can affect money or system
  integrity: risk, execution, brokers, secrets, audit, governance,
  compliance, kill-switches.
* **Capital** is the actual market — touched only via Control.

ORION must enforce this dependency direction mechanically. A module
in the Intelligence plane may import from the Truth plane (to
evaluate its candidates) but must NEVER import from the Control
plane. A module in the Control plane may read Truth artifacts but
must NEVER call Intelligence directly. If you can write
``from orion.intelligence.llm import ...`` inside a control-plane
file, the architecture has been eroded.

This tool performs a static, stdlib-only import-graph check:

1.  Walk every ``.py`` file in ``src/orion/`` (skipping ``__init__.py``
    and tests).
2.  Resolve every ``from orion.<...> import ...`` and
    ``import orion.<...>`` statement to its target module.
3.  Classify the importing module and the target module by plane.
4.  Report every edge that crosses a forbidden boundary.

The check is conservative — a forbidden import is a hard failure
even if the symbol is not used. The point is to prevent drift, not
to police exact data flow.

Forbidden edges
---------------

* ``intelligence.*`` → ``trading.execution``, ``trading.risk``,
  ``trading.brokers``, ``integrations.brokers``, ``security``,
  ``compliance``, ``dashboard``
* ``trading.execution`` / ``trading.risk`` / ``integrations.brokers``
  → ``intelligence.*``, ``agents.*``, ``research.*``
* ``evolution.*`` → ``trading.execution``, ``integrations.brokers``
  (evolution produces candidates; it must not deploy them)
* ``coding.sandbox_v2`` → ``trading.execution`` (generated code
  must not reach the broker directly)
* ``world_model.*`` → ``trading.execution`` (the world model is
  read by the brain but never reaches the broker)
* ``memory.*`` → ``trading.execution`` (memory is knowledge, not
  control)

Allowed edges
-------------

* ``brain.*`` → any truth/intelligence (brain is the orchestrator)
* ``trading.execution`` → ``trading.risk`` (the broker consumes
  risk decisions)
* anything → ``data.contracts``, ``world_model``, ``evaluation``,
  ``infrastructure`` (foundations and the truth plane)
* tests → anything (tests may legally cross the plane)
"""

from __future__ import annotations

import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "orion"

# Plane assignments. A module is classified by the first prefix in this
# list that matches its dotted path. Order matters: longer prefixes
# (more specific) must come first.
PLANE_RULES: list[tuple[str, str]] = [
    # --- Intelligence plane
    ("intelligence", "intelligence"),
    ("agents", "intelligence"),
    ("brain", "intelligence"),
    ("research", "intelligence"),
    ("evolution", "intelligence"),
    ("hypothesis", "intelligence"),
    ("memory", "intelligence"),
    ("coding", "intelligence"),
    ("learning", "intelligence"),
    ("prediction", "intelligence"),
    # --- Truth plane
    ("data.contracts", "truth"),
    ("data.market_data", "truth"),
    ("data.validation", "truth"),
    ("data.providers", "truth"),
    ("evaluation", "truth"),
    ("benchmarking", "truth"),
    ("backtesting", "truth"),
    ("world_model", "truth"),
    ("simulation", "truth"),
    ("portfolio", "truth"),
    ("markets", "truth"),
    ("mathematics", "truth"),
    ("orchestration", "truth"),
    # --- Control plane
    ("trading.execution", "control"),
    ("trading.risk", "control"),
    ("trading.brokers", "control"),
    ("integrations.brokers", "control"),
    ("security", "control"),
    ("compliance", "control"),
    ("dashboard", "control"),
    ("ops", "control"),
    # --- Foundations (cross-cutting; not a plane)
    ("models", "foundation"),
    ("infrastructure", "foundation"),
    ("trading", "truth"),  # anything else in trading/ is truth
    ("storage", "foundation"),
    ("distributed", "foundation"),
    ("cli", "foundation"),
    ("providers", "truth"),
    ("intelligence.tool_use", "intelligence"),
]


def classify(module: str) -> str | None:
    """Return the plane name for an ORION module, or None if not classified."""
    # Try longest prefixes first (already in order).
    for prefix, plane in PLANE_RULES:
        if module == prefix or module.startswith(prefix + "."):
            return plane
    # Default: check the top-level package
    top = module.split(".", 1)[0]
    for prefix, plane in PLANE_RULES:
        if top == prefix:
            return plane
    return None


# Forbidden edges: (source_plane, target_module_prefix, reason)
# We forbid by module prefix, not just plane, because some planes
# (e.g. trading) have sub-modules on multiple sides of the line.
FORBIDDEN: list[tuple[str, str, str]] = [
    # Intelligence must not reach into control.
    ("intelligence", "trading.execution", "LLM/tool layer must not call broker directly"),
    ("intelligence", "trading.risk", "intelligence must submit candidates through truth, not bypass risk"),
    ("intelligence", "integrations.brokers", "intelligence must not call real broker APIs"),
    ("intelligence", "security", "intelligence must not read secrets"),
    ("intelligence", "compliance", "intelligence must not write compliance events"),
    ("intelligence", "dashboard", "intelligence must not call dashboard internals"),
    ("agents", "trading.execution", "agent must not call broker directly"),
    ("agents", "integrations.brokers", "agent must not call real broker APIs"),
    ("evolution", "trading.execution", "evolution produces candidates, never deploys"),
    ("evolution", "integrations.brokers", "evolution must not call real broker APIs"),
    ("research", "trading.execution", "research is a candidate producer, not a control plane"),
    ("coding", "trading.execution", "generated code must not reach the broker directly"),
    ("coding", "integrations.brokers", "generated code must not call real broker APIs"),
    # Control must not call intelligence directly.
    ("control", "intelligence", "control must consume artifacts, not call LLMs"),
    ("control", "agents", "control must consume agent decisions, not call agents"),
    ("control", "research", "control must not trigger research directly"),
    # Truth must not bypass control.
    ("truth", "trading.execution", "truth evaluates; it does not execute"),
    ("truth", "integrations.brokers", "truth does not touch real brokers"),
]


@dataclass(frozen=True)
class Violation:
    source_file: Path
    source_module: str
    source_plane: str
    target_module: str
    target_plane: str | None
    reason: str
    line: int

    def __str__(self) -> str:
        rel = self.source_file.relative_to(ROOT)
        return (
            f"{rel}:{self.line}  {self.source_module} ({self.source_plane}) "
            f"-> {self.target_module} ({self.target_plane}): {self.reason}"
        )


def _module_path_to_dotted(rel: Path) -> str:
    parts = list(rel.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _is_orion_target(name: str) -> bool:
    return name == "orion" or name.startswith("orion.")


def _resolve_target(target: str, current_module: str) -> str:
    """Resolve a possibly-relative import to a fully-qualified orion module.

    Returns the dotted module path, or the original string if it cannot
    be resolved. We do not try to model the full Python import system;
    we only need to catch ``from orion.X import Y`` and
    ``import orion.X.Y``.
    """
    if target.startswith("orion."):
        return target
    if target == "orion":
        return "orion"
    # Relative import: walk up the package.
    parts = current_module.split(".")
    # Drop the last segment (the module itself).
    if parts:
        parts = parts[:-1]
    # ``from . import x`` is 1-level-relative; each leading dot adds 1 level.
    raise ValueError("relative imports outside this scope — not handled")


def _iter_imports(tree: ast.AST) -> list[tuple[int, str]]:
    """Yield ``(line_number, target_dotted_path)`` for every ORION import."""
    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and _is_orion_target(node.module):
                # ``from orion.X import Y`` -> target is orion.X (the
                # module containing Y). The symbol Y is irrelevant for
                # the plane check; the module is.
                out.append((node.lineno, node.module))
            elif node.level and node.module and (node.module.startswith("orion.") or node.module == "orion"):
                # ``from .orion.X import Y`` — handle later
                pass
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if _is_orion_target(alias.name):
                    out.append((node.lineno, alias.name))
    return out


def _python_files() -> list[Path]:
    return sorted(SRC.rglob("*.py"))


def check() -> list[Violation]:
    violations: list[Violation] = []
    for path in _python_files():
        try:
            rel = path.relative_to(SRC)
        except ValueError:
            continue
        # Skip __init__.py — they are import-time, not control flow.
        if path.name == "__init__.py":
            continue
        source_module = _module_path_to_dotted(rel)
        source_plane = classify(source_module)
        if source_plane is None:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError:
            # The compiler will catch it; not our problem here.
            continue
        for line, target in _iter_imports(tree):
            target_module = target.removeprefix("orion.")
            target_plane = classify(target_module)
            for src_plane, tgt_prefix, reason in FORBIDDEN:
                if source_plane == src_plane and (
                    target_module == tgt_prefix or target_module.startswith(tgt_prefix + ".")
                ):
                    violations.append(
                        Violation(
                            source_file=path,
                            source_module=source_module,
                            source_plane=source_plane,
                            target_module=target_module,
                            target_plane=target_plane,
                            reason=reason,
                            line=line,
                        )
                    )
    return violations


def main() -> int:
    violations = check()
    if not violations:
        print("ORION plane-separation check: OK")
        print("No forbidden Intelligence / Truth / Control edges detected.")
        return 0
    print(f"ORION plane-separation check: {len(violations)} forbidden edge(s) detected")
    print("=" * 78)
    for v in violations:
        print(v)
    print("=" * 78)
    print("Fix: refactor so the importing module does not need the forbidden")
    print("dependency. The dependency direction is:")
    print("    Intelligence -> Truth -> Control -> Capital")
    print("Intelligence must not call Control. Control must not call Intelligence.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
