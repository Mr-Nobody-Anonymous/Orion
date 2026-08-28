"""Tests for the ORION capability registry.

The registry is the "capability bus" the 2026-08-28 review asked
for. The tests confirm:

* Registration is idempotent and refuses conflicting definitions.
* The frozen registry refuses new tool names.
* Search by kind / plane / integration / risk works.
* The canonical :func:`default_registry` is non-empty and contains
  both internal and reference tools.
* Every ``HIGH``-risk tool declares a high-risk permission
  (capital / secrets / self-modification).
* Every control-plane tool that touches capital is ``HIGH``-risk.
* Tools are JSON-serialisable (for the eventual truth artifact).
"""

from __future__ import annotations

import json

import pytest

from orion.intelligence.capability_registry import (
    CapabilityKind,
    CapabilityRegistry,
    Field,
    FrozenRegistryError,
    IntegrationMode,
    Plane,
    RiskLevel,
    Tool,
    default_registry,
)


def _make_tool(**overrides) -> Tool:
    defaults = dict(
        name="x.test_tool",
        kind=CapabilityKind.TOOL,
        plane=Plane.TRUTH,
        integration=IntegrationMode.INTERNAL,
        source="src/orion/some/module.py",
        description="A test tool.",
    )
    defaults.update(overrides)
    return Tool(**defaults)


# --------------------------------------------------------------------------- shape / validation


def test_tool_requires_name_and_source() -> None:
    with pytest.raises(ValueError, match="name"):
        Tool(name="", kind=CapabilityKind.TOOL, plane=Plane.TRUTH,
             integration=IntegrationMode.INTERNAL, source="x", description="x")
    with pytest.raises(ValueError, match="source"):
        Tool(name="x", kind=CapabilityKind.TOOL, plane=Plane.TRUTH,
             integration=IntegrationMode.INTERNAL, source="", description="x")


def test_tool_rejects_unknown_permissions() -> None:
    with pytest.raises(ValueError, match="unknown permission"):
        _make_tool(permissions=frozenset({"definitely_not_a_real_permission"}))


def test_high_risk_tool_requires_high_risk_permission() -> None:
    """A HIGH-risk tool must declare a permission that justifies the risk.

    Without this, a future maintainer could mark a tool HIGH "to be
    safe" and the gate would block it without the operator
    understanding *why* it is dangerous.
    """
    with pytest.raises(ValueError, match="RiskLevel.HIGH"):
        _make_tool(risk=RiskLevel.HIGH)  # no permissions at all


def test_control_plane_capital_tool_must_be_high_risk() -> None:
    """A control-plane tool that moves money is HIGH-risk by construction."""
    with pytest.raises(ValueError, match="RiskLevel must be HIGH"):
        _make_tool(
            plane=Plane.CONTROL,
            permissions=frozenset({"capital"}),
            risk=RiskLevel.MEDIUM,  # wrong
        )


def test_tool_as_dict_is_json_serialisable() -> None:
    tool = _make_tool(
        inputs=(Field(name="x", type_name="int"),),
        outputs=(Field(name="y", type_name="float"),),
    )
    payload = json.dumps(tool.as_dict())
    assert "x.test_tool" in payload
    assert "int" in payload


# --------------------------------------------------------------------------- registry semantics


def test_registry_register_is_idempotent() -> None:
    reg = CapabilityRegistry()
    t = _make_tool()
    reg.register(t)
    reg.register(t)  # identical, no error
    assert len(reg) == 1


def test_registry_rejects_conflicting_definitions() -> None:
    reg = CapabilityRegistry()
    reg.register(_make_tool())
    with pytest.raises(ValueError, match="different definition"):
        reg.register(_make_tool(description="different description"))


def test_registry_freeze_refuses_new_tools() -> None:
    reg = CapabilityRegistry()
    reg.register(_make_tool(name="a.first"))
    reg.freeze()
    with pytest.raises(FrozenRegistryError):
        reg.register(_make_tool(name="b.second"))


def test_registry_freeze_allows_re_registration_of_existing() -> None:
    """Freeze is about new names, not about re-asserting known tools."""
    reg = CapabilityRegistry()
    t = _make_tool(name="a.first")
    reg.register(t)
    reg.freeze()
    reg.register(t)  # same tool, same definition: allowed
    assert len(reg) == 1


def test_registry_get_unknown_raises_helpfully() -> None:
    reg = CapabilityRegistry()
    with pytest.raises(KeyError, match="unknown tool"):
        reg.get("nonexistent")
    with pytest.raises(KeyError, match="registered names"):
        reg.get("nonexistent")


def test_registry_search_by_kind() -> None:
    reg = CapabilityRegistry()
    reg.register(_make_tool(name="eval.run", kind=CapabilityKind.EVALUATION))
    reg.register(_make_tool(name="data.x", kind=CapabilityKind.DATA))
    res = reg.search_by_kind(CapabilityKind.EVALUATION)
    assert {t.name for t in res} == {"eval.run"}


def test_registry_search_by_plane() -> None:
    reg = CapabilityRegistry()
    reg.register(_make_tool(name="t1", plane=Plane.TRUTH))
    reg.register(_make_tool(name="t2", plane=Plane.CONTROL))
    res = reg.search_by_plane(Plane.CONTROL)
    assert {t.name for t in res} == {"t2"}


# search by CapabilityQuery
def test_registry_search_with_query_combines_filters() -> None:
    from orion.intelligence.capability_registry import CapabilityQuery
    reg = CapabilityRegistry()
    reg.register(_make_tool(name="internal.low", plane=Plane.TRUTH,
                             risk=RiskLevel.LOW, integration=IntegrationMode.INTERNAL))
    reg.register(_make_tool(name="internal.high", plane=Plane.TRUTH,
                             risk=RiskLevel.HIGH, integration=IntegrationMode.INTERNAL,
                             permissions=frozenset({"capital"})))
    reg.register(_make_tool(name="ref.x", plane=Plane.TRUTH,
                             risk=RiskLevel.LOW, integration=IntegrationMode.REFERENCE))
    q = CapabilityQuery(integrations=(IntegrationMode.INTERNAL,),
                         max_risk=RiskLevel.LOW)
    names = {t.name for t in reg.search(q)}
    assert names == {"internal.low"}


# --------------------------------------------------------------------------- canonical registry


def test_default_registry_is_not_empty() -> None:
    reg = default_registry()
    assert len(reg) > 5


def test_default_registry_is_frozen() -> None:
    reg = default_registry()
    with pytest.raises(FrozenRegistryError):
        reg.register(_make_tool(name="x.something_new"))


def test_default_registry_contains_internal_and_reference_tools() -> None:
    """The canonical registry must contain both internal (callable
    today) and reference (upstream, not yet wrapped) tools. The
    reviewer's point is that the gap is visible.
    """
    reg = default_registry()
    integrations = {t.integration for t in reg.tools()}
    assert IntegrationMode.INTERNAL in integrations
    assert IntegrationMode.REFERENCE in integrations


def test_default_registry_contains_canonical_tool_names() -> None:
    """The registry must list the capabilities the audit said are
    core: evaluation lab, walk-forward, model council, exposure,
    sandbox, simulated broker, Alpaca paper, plus the upstream
    candidates (qlib, vectorbt, Kronos, etc.)."""
    reg = default_registry()
    expected = {
        "evaluation.run_lab",
        "evaluation.run_baseline_suite",
        "evaluation.walk_forward",
        "data.compute_exposure",
        "prediction.council_predict",
        "research.discover_papers",
        "coding.sandbox_run",
        "trading.simulated_broker_submit",
        "trading.alpaca_paper_submit",
        "upstream.qlib.factors",
        "upstream.vectorbt.backtest",
        "upstream.quantlib.pricing",
        "upstream.py_vollib.greeks",
        "upstream.kronos.forecast",
        "upstream.fingpt.sentiment",
        "upstream.ollama.local_inference",
    }
    missing = expected - set(reg)
    assert not missing, f"missing canonical tools: {sorted(missing)}"


def test_default_registry_internal_tools_have_real_sources() -> None:
    """Every INTERNAL tool must point to a real path in ``src/orion/``.

    This is the falsifiability check: a tool that points to a
    nonexistent file is a lie. We assert the file exists on disk.
    """
    import os
    repo_root = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
    reg = default_registry()
    for t in reg.tools():
        if t.integration != IntegrationMode.INTERNAL:
            continue
        # ``source`` is a path relative to the repo root.
        path = os.path.join(repo_root, t.source.replace("/", os.sep))
        assert os.path.exists(path), f"tool {t.name!r} points at missing source {path}"


def test_default_registry_high_risk_tools_have_high_risk_permissions() -> None:
    """The validation in Tool.__post_init__ enforces this, but a
    direct assertion here documents the contract for the reader."""
    reg = default_registry()
    high_risk = [t for t in reg.tools() if t.risk == RiskLevel.HIGH]
    assert high_risk, "expected at least one HIGH-risk tool in the default registry"
    high_risk_perms = {"capital", "read_secrets", "modify_self"}
    for t in high_risk:
        assert t.permissions & high_risk_perms, (
            f"HIGH-risk tool {t.name!r} must declare at least one of "
            f"{high_risk_perms}, got {sorted(t.permissions)}"
        )


def test_default_registry_control_plane_tools_with_capital_are_high_risk() -> None:
    reg = default_registry()
    for t in reg.tools():
        if t.plane == Plane.CONTROL and "capital" in t.permissions:
            assert t.risk == RiskLevel.HIGH, (
                f"control-plane tool {t.name!r} touches capital but is not HIGH-risk"
            )


def test_default_registry_describe_is_human_readable() -> None:
    reg = default_registry()
    text = reg.describe("evaluation.run_lab")
    assert "evaluation.run_lab" in text
    assert "kind:" in text
    assert "inputs:" in text


def test_default_registry_as_dict_is_json_serialisable() -> None:
    """The registry must be JSON-serialisable so it can be embedded
    in the truth artifact and the Hugging Face model card."""
    reg = default_registry()
    payload = json.dumps(reg.as_dict())
    parsed = json.loads(payload)
    assert parsed["n_tools"] == len(reg)
    assert parsed["frozen"] is True


def test_default_registry_baseline_names_match_baselines_strategies() -> None:
    """Falsifiability: the registry must advertise exactly the
    baseline strategies that ``default_baselines()`` actually
    produces. If a maintainer adds a new baseline strategy and
    forgets to register it, this test will fail.
    """
    from orion.evaluation.baselines_strategies import default_baselines
    reg = default_registry()
    actual_names = {s.name for s in default_baselines()}
    advertised = {t.name for t in reg.tools() if t.name.startswith("evaluation.baseline.")}
    expected = {f"evaluation.baseline.{n}" for n in actual_names}
    missing = expected - advertised
    extra = advertised - expected
    assert not missing, f"registry missing baseline tools: {sorted(missing)}"
    assert not extra, f"registry has phantom baseline tools: {sorted(extra)}"
