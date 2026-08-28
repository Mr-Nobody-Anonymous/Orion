"""Tests for the Intelligence / Truth / Control plane rule.

The architecture must enforce that:

* Intelligence-layer modules (LLM, research, evolution, agents,
  coding) may not import from the control layer (trading.execution,
  trading.risk, integrations.brokers, security, compliance).
* Control-layer modules (the broker, the risk engine, real-broker
  adapters) may not call into intelligence (LLM, agents, research).
* Truth-layer modules may not bypass control to execute trades.

These tests are static: they parse ``src/orion/`` ASTs and assert
that no forbidden import edges exist. They also include a
synthetic-import sanity check: if a hypothetical forbidden edge is
introduced, the static check must surface it.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
SRC = ROOT / "src"


def _load_enforce_planes():
    spec = importlib.util.spec_from_file_location("enforce_planes", TOOLS / "enforce_planes.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["enforce_planes"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_plane_classifier_assigns_expected_planes() -> None:
    m = _load_enforce_planes()
    assert m.classify("brain.orchestrator") == "intelligence"
    assert m.classify("intelligence.llm.ollama") == "intelligence"
    assert m.classify("agents.researcher") == "intelligence"
    assert m.classify("research.agent") == "intelligence"
    assert m.classify("evolution.engine") == "intelligence"
    assert m.classify("coding.sandbox") == "intelligence"
    assert m.classify("memory.layered") == "intelligence"
    assert m.classify("prediction.forecasting") == "intelligence"
    # Truth plane
    assert m.classify("data.contracts") == "truth"
    assert m.classify("world_model.state") == "truth"
    assert m.classify("evaluation.lab") == "truth"
    assert m.classify("backtesting.engine") == "truth"
    # Control plane
    assert m.classify("trading.execution") == "control"
    assert m.classify("trading.risk") == "control"
    assert m.classify("integrations.brokers.alpaca") == "control"
    assert m.classify("security.secrets") == "control"
    assert m.classify("compliance.audit") == "control"
    # Foundation
    assert m.classify("infrastructure.configuration") == "foundation"
    assert m.classify("models.local.ollama") == "foundation"


def test_real_orion_tree_has_no_forbidden_edges() -> None:
    """The canonical ``src/orion/`` tree must currently have no
    Intelligence→Control or Control→Intelligence edges. If a future
    refactor introduces one, this test will fail with the offending
    file and line number."""
    m = _load_enforce_planes()
    violations = m.check()
    rendered = [str(v) for v in violations]
    assert not violations, (
        "Forbidden plane crossings detected. Resolve before merging:\n"
        + "\n".join(rendered)
    )


def test_forbidden_intelligence_to_broker_is_detected(tmp_path, monkeypatch) -> None:
    """The static check must surface a synthetic Intelligence→Control
    edge. We synthesise a tiny in-memory file in a temp directory
    that mimics the ``src/orion/`` layout and run the AST walker
    against it directly to prove the rule is wired correctly."""
    import textwrap

    m = _load_enforce_planes()
    # Build a fake ``src/orion/`` tree under tmp_path.
    fake_src = tmp_path / "orion"
    (fake_src / "intelligence").mkdir(parents=True)
    (fake_src / "trading").mkdir(parents=True)
    (fake_src / "trading" / "execution").mkdir(parents=True)
    # A clean intelligence file that imports a control-plane module.
    bad = fake_src / "intelligence" / "evil.py"
    bad.write_text(
        textwrap.dedent(
            """
            from orion.trading.execution import SimulatedBroker
            from orion.intelligence.llm.ollama import OllamaProvider
            """
        ),
        encoding="utf-8",
    )

    # Patch the SRC + ROOT to point at our fake tree, then run check().
    monkeypatch.setattr(m, "SRC", fake_src)
    monkeypatch.setattr(m, "ROOT", tmp_path)
    violations = m.check()
    relevant = [
        v for v in violations
        if v.source_module == "intelligence.evil"
        and v.target_module == "trading.execution"
    ]
    assert relevant, (
        "check() should detect the synthetic intelligence -> trading.execution "
        f"import; got {[(v.source_module, v.target_module) for v in violations]}"
    )
    v = relevant[0]
    assert v.source_plane == "intelligence"
    assert "must not" in v.reason.lower() or "broker" in v.reason.lower()


def test_forbidden_control_to_intelligence_is_detected(tmp_path, monkeypatch) -> None:
    """The symmetric rule: control must not import from intelligence."""
    import textwrap

    m = _load_enforce_planes()
    fake_src = tmp_path / "orion"
    (fake_src / "intelligence").mkdir(parents=True)
    (fake_src / "intelligence" / "llm").mkdir(parents=True)
    (fake_src / "trading").mkdir(parents=True)
    (fake_src / "trading" / "execution").mkdir(parents=True)
    bad = fake_src / "trading" / "execution" / "evil.py"
    bad.write_text(
        textwrap.dedent(
            """
            from orion.intelligence.llm.ollama import OllamaProvider
            from orion.trading.risk import RiskEngine
            """
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(m, "SRC", fake_src)
    monkeypatch.setattr(m, "ROOT", tmp_path)
    violations = m.check()
    relevant = [
        v for v in violations
        if v.source_module == "trading.execution.evil"
        and "intelligence" in v.target_module
    ]
    assert relevant, (
        "check() should detect the synthetic trading.execution -> intelligence "
        f"import; got {[(v.source_module, v.target_module) for v in violations]}"
    )
    v = relevant[0]
    assert v.source_plane == "control"
    assert "intelligence" in v.target_module
    assert "must not" in v.reason.lower() or "artifacts" in v.reason.lower()


def test_no_circular_intelligence_to_control_in_actual_brain() -> None:
    """The brain is the orchestrator. It may import truth and
    intelligence (it is itself intelligence) but it must not directly
    import the broker. The current ``brain/orchestrator.py``
    imports ``trading.execution`` (the protocol) and ``trading.risk``
    via type — both are control-plane modules.

    This test documents the **explicit, allowed** exception: the
    orchestrator is the one intelligence-plane module that has a
    narrow, audited path to ``trading.execution`` and
    ``trading.risk`` because it must coordinate the executive loop.
    Anything else in the intelligence plane that imports those
    modules is a violation.
    """
    m = _load_enforce_planes()
    # The brain itself currently has trading.execution + trading.risk
    # imports; we record that this is the **only** intelligence-plane
    # module allowed to do so.
    brain_violations = [
        v for v in m.check()
        if v.source_plane == "intelligence"
        and v.source_module.startswith("brain.")
    ]
    allowed_paths = {"brain.orchestrator", "brain.executive"}
    for v in brain_violations:
        assert v.source_module in allowed_paths, (
            f"Only the executive orchestrator is allowed to bridge "
            f"intelligence to control; found {v}"
        )
