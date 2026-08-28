"""ORION capability registry.

A typed, in-memory catalogue of the capabilities ORION can draw on,
both inside ``src/orion/`` and across the cloned upstream
repositories in ``source_repositories/``. The registry is the
"capability bus" the 2026-08-28 review asked for: instead of
"ORION has 30 cloned repos", the registry says "ORION has 30
discoverable tools, each with a clean input/output contract,
permissions, and risk profile".

Design choices
--------------

* **Plain data, no I/O.** Discovery is in-memory and deterministic
  so a test can assert exact contents. A future iteration can
  back the registry with a database or filesystem index, but the
  current goal is *falsifiability* — the registry has to be
  inspectable from a unit test, not loaded at runtime from a
  hidden YAML.
* **Single ``Tool`` record.** Every capability — internal or
  upstream — is a ``Tool``. There is no separate class for
  "ORION-internal" vs "external reference". The discriminator is
  the ``kind`` and ``source`` fields. This is the reviewer's
  point: a capability is a capability.
* **Strict input/output schema.** A ``Tool`` carries a tuple of
  ``Field`` objects for inputs and outputs. A consumer can
  inspect the schema before invocation. We do not (yet) validate
  payloads against the schema — that is a job for the eventual
  agent kernel — but the schema is part of the registry record.
* **Permissions and risk.** Every tool declares whether it touches
  capital, the network, the filesystem, secrets, or production
  state. The risk gate can refuse to invoke a high-risk tool
  without explicit operator consent, even if an upstream agent
  requested it.
* **Plane-typed.** Each tool records the plane it lives in
  (``intelligence``, ``truth``, ``control``, ``foundation``)
  and the planes it may consume. The plane rule in
  :mod:`tools.enforce_planes` will refuse a control-plane
  module that imports a high-risk tool from the intelligence
  plane; the registry exposes the same information in a
  machine-readable form.

The registry is intentionally small. It is not an agent
framework, a planner, or a tool dispatcher. It is a *catalogue*.
The agent, planner, and dispatcher are downstream consumers
that this session is explicitly *not* building — they are the
wrong next step until an experiment has been run to tell us
what they need to do.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence


class CapabilityKind(str, Enum):
    """The 13 high-level categories the reviewer asked for.

    Every tool belongs to exactly one kind. The kind is the
    primary key an agent uses to discover tools (``"find me a
    backtesting tool"`` → ``kind=BACKTESTING``).
    """

    DATA = "data"
    MODEL = "model"
    RESEARCH = "research"
    SIMULATION = "simulation"
    OPTIMIZATION = "optimization"
    VISION = "vision"
    NLP = "nlp"
    CODING = "coding"
    RL = "rl"
    FORECASTING = "forecasting"
    AGENT = "agent"
    EVALUATION = "evaluation"
    TOOL = "tool"


class IntegrationMode(str, Enum):
    """How a tool is integrated with ORION.

    Mirrors the integration modes recorded in
    ``source_repositories/MANIFEST.yaml`` so the registry can be
    cross-referenced with the provenance manifest.
    """

    DEPENDENCY = "dependency"
    ADAPTER = "adapter"
    SIDECAR = "sidecar"
    REFERENCE = "reference"
    BENCHMARK = "benchmark"
    CONCEPTUAL = "conceptual"
    RESEARCH = "research"
    OPTIONAL = "optional"
    FALLBACK = "fallback"
    DEPRECATED = "deprecated"
    EXCLUDED = "excluded"
    ISOLATED = "isolated"
    INTERNAL = "internal"  # lives in src/orion, not source_repositories/


class RiskLevel(str, Enum):
    """How dangerous a tool is to invoke.

    A high-risk tool may touch capital, production state, the
    network, or untrusted input. The risk gate (control plane)
    must explicitly authorise a ``HIGH`` tool before an agent
    can invoke it.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Plane(str, Enum):
    """The ORION plane a tool lives in.

    Tools respect the same plane separation as modules. A
    ``CONTROL``-plane tool may not be invoked directly from the
    ``INTELLIGENCE`` plane; the request must flow through the
    truth-plane validator (the risk gate) first.
    """

    INTELLIGENCE = "intelligence"
    TRUTH = "truth"
    CONTROL = "control"
    FOUNDATION = "foundation"


@dataclass(frozen=True, slots=True)
class Field:
    """A single input or output field of a tool."""

    name: str
    type_name: str  # e.g. "str", "Sequence[float]", "ExperimentArtifact"
    description: str = ""
    required: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type_name,
            "description": self.description,
            "required": self.required,
        }


@dataclass(frozen=True, slots=True)
class Tool:
    """A discoverable capability.

    A ``Tool`` is the smallest unit the registry tracks. It
    corresponds 1-to-1 to a callable function in ``src/orion/``
    or a documented surface in an upstream repository.
    """

    name: str
    kind: CapabilityKind
    plane: Plane
    integration: IntegrationMode
    source: str  # e.g. "src/orion/evaluation/lab.py" or "source_repositories/prediction/Kronos"
    description: str
    inputs: tuple[Field, ...] = ()
    outputs: tuple[Field, ...] = ()
    permissions: frozenset[str] = frozenset()
    risk: RiskLevel = RiskLevel.LOW
    version: str = "0.0.0"
    # When set, the registry treats the tool as an alias for an
    # upstream capability that has not yet been ported into
    # ``src/orion/``. The string is the local path under
    # ``source_repositories/``.
    upstream_path: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Tool.name must be non-empty")
        if not self.source:
            raise ValueError("Tool.source must be non-empty")
        # Permissions validation
        allowed_perms = {
            "read_data", "write_files", "network", "capital",
            "read_secrets", "execute_code", "modify_self", "long_running",
        }
        for perm in self.permissions:
            if perm not in allowed_perms:
                raise ValueError(f"unknown permission {perm!r}")
        # A high-risk tool must declare *why* it is high-risk
        if self.risk == RiskLevel.HIGH and not (
            "capital" in self.permissions
            or "modify_self" in self.permissions
            or "read_secrets" in self.permissions
        ):
            raise ValueError(
                f"Tool {self.name!r} has RiskLevel.HIGH but no high-risk permission declared"
            )
        # A control-plane tool must carry the capital permission
        # if it can move money.
        if self.plane == Plane.CONTROL and "capital" in self.permissions and self.risk != RiskLevel.HIGH:
            raise ValueError(
                f"Tool {self.name!r} is on the control plane and touches capital; "
                "RiskLevel must be HIGH"
            )

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind.value,
            "plane": self.plane.value,
            "integration": self.integration.value,
            "source": self.source,
            "description": self.description,
            "inputs": [f.as_dict() for f in self.inputs],
            "outputs": [f.as_dict() for f in self.outputs],
            "permissions": sorted(self.permissions),
            "risk": self.risk.value,
            "version": self.version,
            "upstream_path": self.upstream_path,
        }


@dataclass(frozen=True, slots=True)
class CapabilityQuery:
    """A discoverability filter.

    A consumer can pass a :class:`CapabilityQuery` to
    :meth:`CapabilityRegistry.search` to narrow the catalogue by
    kind, plane, integration mode, risk level, or a substring
    match on the name or description.
    """

    kinds: tuple[CapabilityKind, ...] = ()
    planes: tuple[Plane, ...] = ()
    integrations: tuple[IntegrationMode, ...] = ()
    max_risk: RiskLevel | None = None
    name_contains: str = ""
    has_permission: str = ""

    def matches(self, tool: Tool) -> bool:
        if self.kinds and tool.kind not in self.kinds:
            return False
        if self.planes and tool.plane not in self.planes:
            return False
        if self.integrations and tool.integration not in self.integrations:
            return False
        if self.max_risk is not None and _risk_rank(tool.risk) > _risk_rank(self.max_risk):
            return False
        if self.name_contains and self.name_contains.lower() not in tool.name.lower():
            return False
        if self.has_permission and self.has_permission not in tool.permissions:
            return False
        return True


_RISK_RANK: dict[RiskLevel, int] = {
    RiskLevel.LOW: 0,
    RiskLevel.MEDIUM: 1,
    RiskLevel.HIGH: 2,
}


def _risk_rank(risk: RiskLevel) -> int:
    return _RISK_RANK[risk]


class CapabilityRegistry:
    """An in-memory catalogue of :class:`Tool` records.

    The registry is a plain ``Mapping[str, Tool]`` underneath; the
    only methods it adds are :meth:`register`, :meth:`search`, and
    :meth:`describe` (the human-readable summary an agent would
    see when planning a task).

    The registry is **read-mostly**. Tools are registered at
    process start (or by an explicit registration call) and are
    not modified at runtime. New tools added after the registry
    is "frozen" raise a :class:`FrozenRegistryError`.
    """

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}
        self._frozen: bool = False

    def register(self, tool: Tool) -> None:
        """Register a tool. Idempotent if the existing record is identical."""
        if self._frozen and tool.name not in self._tools:
            raise FrozenRegistryError(
                f"registry is frozen; cannot register new tool {tool.name!r}"
            )
        if tool.name in self._tools and self._tools[tool.name] != tool:
            raise ValueError(
                f"tool {tool.name!r} already registered with a different definition"
            )
        self._tools[tool.name] = tool

    def register_many(self, tools: Sequence[Tool]) -> None:
        for t in tools:
            self.register(t)

    def freeze(self) -> None:
        """Mark the registry as immutable for new tool names.

        Re-registering an existing tool with an identical record
        is still allowed (idempotent). Adding a brand-new tool
        name after freeze raises.
        """
        self._frozen = True

    def get(self, name: str) -> Tool:
        try:
            return self._tools[name]
        except KeyError:
            raise KeyError(f"unknown tool {name!r}; registered names: {sorted(self._tools)}") from None

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and name in self._tools

    def __len__(self) -> int:
        return len(self._tools)

    def __iter__(self):
        return iter(self._tools)

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._tools))

    def tools(self) -> tuple[Tool, ...]:
        """Return every registered :class:`Tool`, sorted by name.

        Iterating the registry directly yields tool *names* (so
        ``for name in reg`` reads naturally). Use this method when
        you need the :class:`Tool` records themselves.
        """
        return tuple(self._tools[name] for name in self.names())

    def search(self, query: CapabilityQuery | None = None) -> tuple[Tool, ...]:
        q = query or CapabilityQuery()
        return tuple(t for t in self._tools.values() if q.matches(t))

    def search_by_kind(self, kind: CapabilityKind) -> tuple[Tool, ...]:
        return self.search(CapabilityQuery(kinds=(kind,)))

    def search_by_plane(self, plane: Plane) -> tuple[Tool, ...]:
        return self.search(CapabilityQuery(planes=(plane,)))

    def search_by_integration(self, integration: IntegrationMode) -> tuple[Tool, ...]:
        return self.search(CapabilityQuery(integrations=(integration,)))

    def kinds(self) -> tuple[CapabilityKind, ...]:
        seen: set[CapabilityKind] = set()
        for t in self._tools.values():
            seen.add(t.kind)
        return tuple(sorted(seen, key=lambda k: k.value))

    def describe(self, name: str) -> str:
        """Return a human-readable summary of a single tool.

        The format is plain text and stable; agents that want a
        machine-readable form should call :meth:`Tool.as_dict`.
        """
        t = self.get(name)
        lines = [
            f"# {t.name}",
            f"kind:        {t.kind.value}",
            f"plane:       {t.plane.value}",
            f"integration: {t.integration.value}",
            f"risk:        {t.risk.value}",
            f"version:     {t.version}",
            f"source:      {t.source}",
            f"description: {t.description}",
        ]
        if t.permissions:
            lines.append(f"permissions: {', '.join(sorted(t.permissions))}")
        if t.upstream_path:
            lines.append(f"upstream:    {t.upstream_path}")
        if t.inputs:
            lines.append("inputs:")
            for f in t.inputs:
                req = "required" if f.required else "optional"
                lines.append(f"  - {f.name} ({f.type_name}, {req}) — {f.description}")
        if t.outputs:
            lines.append("outputs:")
            for f in t.outputs:
                lines.append(f"  - {f.name} ({f.type_name}) — {f.description}")
        return "\n".join(lines)

    def as_dict(self) -> dict[str, Any]:
        return {
            "frozen": self._frozen,
            "n_tools": len(self._tools),
            "tools": {name: t.as_dict() for name, t in sorted(self._tools.items())},
        }


class FrozenRegistryError(RuntimeError):
    """Raised when a new tool is registered into a frozen registry."""


# --------------------------------------------------------------------------- canonical registry


def default_registry() -> CapabilityRegistry:
    """Build the canonical ORION capability registry.

    Every tool listed here is one an honest operator can invoke
    today (the implementation lives in the source path given).
    The list is deliberately small and conservative — only
    capabilities that are *real code in this repository* are
    included. The cloned upstream repos are listed with
    ``integration=REFERENCE`` and a description of what they
    *would* provide, but they are not callable until an adapter
    exists.
    """
    reg = CapabilityRegistry()
    tools: list[Tool] = [
        # -------------------------- truth plane
        Tool(
            name="evaluation.run_lab",
            kind=CapabilityKind.EVALUATION,
            plane=Plane.TRUTH,
            integration=IntegrationMode.INTERNAL,
            source="src/orion/evaluation/lab.py",
            description=(
                "Run the contamination-safe walk-forward evaluation lab on a "
                "price history and write a reproducible artifact tree."
            ),
            inputs=(
                Field("prices", "Sequence[float]", "Price history, oldest first."),
                Field("orion_predictor", "Callable[[Sequence[float]], float]",
                      "The full ORION prediction function."),
                Field("ablations", "Sequence[AblationVariant]", "Optional ablated variants.", required=False),
                Field("config", "LabConfig", "Optional lab configuration.", required=False),
            ),
            outputs=(
                Field("artifact", "LabArtifact", "Bundle of files on disk for this run."),
                Field("report", "EvaluationReport", "In-memory per-spec metrics and significance."),
            ),
            permissions=frozenset({"read_data", "write_files"}),
            risk=RiskLevel.LOW,
            version="0.1.0",
        ),
        Tool(
            name="evaluation.run_baseline_suite",
            kind=CapabilityKind.EVALUATION,
            plane=Plane.TRUTH,
            integration=IntegrationMode.INTERNAL,
            source="src/orion/evaluation/baselines_strategies.py",
            description=(
                "Run the canonical baseline strategy suite (buy-and-hold, "
                "momentum, mean-reversion, factor-neutral, random-null) on a "
                "price history with realistic costs. Returns a per-strategy "
                "BacktestResult."
            ),
            inputs=(
                Field("prices", "Sequence[float]", "Price history, oldest first."),
                Field("cost_per_trade", "float", "Proportional cost per unit turnover.", required=False),
                Field("initial_equity", "float", "Starting equity (default 1.0).", required=False),
            ),
            outputs=(
                Field("results", "Mapping[str, BacktestResult]", "Per-strategy backtest outcome."),
            ),
            permissions=frozenset(),
            risk=RiskLevel.LOW,
            version="0.1.0",
        ),
        Tool(
            name="evaluation.baseline.buy_and_hold",
            kind=CapabilityKind.EVALUATION,
            plane=Plane.TRUTH,
            integration=IntegrationMode.INTERNAL,
            source="src/orion/evaluation/baselines_strategies.py",
            description=(
                "Buy-and-hold baseline strategy. The long-only lower bound "
                "every ORION strategy must beat on a single asset."
            ),
            inputs=(Field("prices", "Sequence[float]"),),
            outputs=(Field("target_position", "float"),),
            permissions=frozenset(),
            risk=RiskLevel.LOW,
            version="0.1.0",
        ),
        Tool(
            name="evaluation.baseline.momentum",
            kind=CapabilityKind.EVALUATION,
            plane=Plane.TRUTH,
            integration=IntegrationMode.INTERNAL,
            source="src/orion/evaluation/baselines_strategies.py",
            description=(
                "Momentum baseline: long when the trailing ``lookback`` "
                "return is positive, flat otherwise."
            ),
            inputs=(Field("prices", "Sequence[float]"),),
            outputs=(Field("target_position", "float"),),
            permissions=frozenset(),
            risk=RiskLevel.LOW,
            version="0.1.0",
        ),
        Tool(
            name="evaluation.baseline.mean_reversion",
            kind=CapabilityKind.EVALUATION,
            plane=Plane.TRUTH,
            integration=IntegrationMode.INTERNAL,
            source="src/orion/evaluation/baselines_strategies.py",
            description=(
                "Mean-reversion baseline: long when the trailing "
                "``lookback`` return is negative, flat otherwise."
            ),
            inputs=(Field("prices", "Sequence[float]"),),
            outputs=(Field("target_position", "float"),),
            permissions=frozenset(),
            risk=RiskLevel.LOW,
            version="0.1.0",
        ),
        Tool(
            name="evaluation.baseline.factor_neutral",
            kind=CapabilityKind.EVALUATION,
            plane=Plane.TRUTH,
            integration=IntegrationMode.INTERNAL,
            source="src/orion/evaluation/baselines_strategies.py",
            description=(
                "Factor-neutral baseline: position is the average of the "
                "momentum and mean-reversion signals so the strategy is "
                "uncorrelated with either factor in expectation. Closes "
                "the factor-neutral gap from the 2026-08-28 review."
            ),
            inputs=(Field("prices", "Sequence[float]"),),
            outputs=(Field("target_position", "float"),),
            permissions=frozenset(),
            risk=RiskLevel.LOW,
            version="0.1.0",
        ),
        Tool(
            name="evaluation.baseline.random_null",
            kind=CapabilityKind.EVALUATION,
            plane=Plane.TRUTH,
            integration=IntegrationMode.INTERNAL,
            source="src/orion/evaluation/baselines_strategies.py",
            description=(
                "Random-null baseline: deterministic seeded random "
                "position policy. The negative control — the question it "
                "answers is 'is ORION doing anything better than noise?'."
            ),
            inputs=(Field("prices", "Sequence[float]"),),
            outputs=(Field("target_position", "float"),),
            permissions=frozenset(),
            risk=RiskLevel.LOW,
            version="0.1.0",
        ),
        Tool(
            name="evaluation.walk_forward",
            kind=CapabilityKind.EVALUATION,
            plane=Plane.TRUTH,
            integration=IntegrationMode.INTERNAL,
            source="src/orion/evaluation/walk_forward.py",
            description=(
                "Build a contamination-safe walk-forward fold schedule with "
                "embargo and purge between train and test windows."
            ),
            inputs=(
                Field("n_samples", "int", "Total number of bars."),
                Field("train_size", "int"),
                Field("test_size", "int"),
                Field("step", "int"),
                Field("embargo", "int", required=False),
                Field("purge", "int", required=False),
            ),
            outputs=(Field("folds", "Sequence[WalkForwardFold]"),),
            permissions=frozenset(),
            risk=RiskLevel.LOW,
            version="0.1.0",
        ),
        Tool(
            name="data.compute_exposure",
            kind=CapabilityKind.DATA,
            plane=Plane.TRUTH,
            integration=IntegrationMode.INTERNAL,
            source="src/orion/trading/exposure.py",
            description=(
                "Compute market-value portfolio exposure "
                "(sum |qty * price| / equity) with quote-missing handled."
            ),
            inputs=(
                Field("positions", "Mapping[Asset, Decimal]"),
                Field("quotes", "Mapping[Asset, MarketQuote]"),
                Field("equity", "Decimal"),
            ),
            outputs=(Field("breakdown", "ExposureBreakdown"),),
            permissions=frozenset(),
            risk=RiskLevel.LOW,
            version="0.1.0",
        ),
        # -------------------------- intelligence plane
        Tool(
            name="prediction.council_predict",
            kind=CapabilityKind.FORECASTING,
            plane=Plane.INTELLIGENCE,
            integration=IntegrationMode.INTERNAL,
            source="src/orion/prediction/ensembles/model_council.py",
            description=(
                "Combine multiple forecasters with regime-dependent weights. "
                "Surviving-member weight remapping is bug-fixed (the index-slice "
                "regression found in the 2026-08-28 review)."
            ),
            inputs=(
                Field("asset", "Asset"),
                Field("prices", "Sequence[float]"),
                Field("regime", "str | None", required=False),
            ),
            outputs=(Field("result", "CouncilPrediction"),),
            permissions=frozenset(),
            risk=RiskLevel.LOW,
            version="0.1.0",
        ),
        Tool(
            name="research.discover_papers",
            kind=CapabilityKind.RESEARCH,
            plane=Plane.INTELLIGENCE,
            integration=IntegrationMode.INTERNAL,
            source="src/orion/research/discovery.py",
            description=(
                "Query the public OpenAlex metadata API for papers on a topic. "
                "Returns an explicit BLOCKED result on network failure — never "
                "fabricates evidence."
            ),
            inputs=(Field("query", "str"),),
            outputs=(Field("bundle", "PaperBundle"),),
            permissions=frozenset({"network", "read_data"}),
            risk=RiskLevel.LOW,
            version="0.1.0",
        ),
        Tool(
            name="coding.sandbox_run",
            kind=CapabilityKind.CODING,
            plane=Plane.INTELLIGENCE,
            integration=IntegrationMode.INTERNAL,
            source="src/orion/coding/sandbox_v2/runner.py",
            description=(
                "Run a Python snippet in a subprocess sandbox with a "
                "configurable CPU / memory / network / filesystem policy."
            ),
            inputs=(
                Field("code", "str"),
                Field("policy", "SandboxPolicy", required=False),
            ),
            outputs=(Field("result", "SandboxResult"),),
            permissions=frozenset({"execute_code"}),
            risk=RiskLevel.MEDIUM,
            version="0.2.0",
        ),
        # -------------------------- control plane
        Tool(
            name="trading.simulated_broker_submit",
            kind=CapabilityKind.SIMULATION,
            plane=Plane.CONTROL,
            integration=IntegrationMode.INTERNAL,
            source="src/orion/trading/execution.py",
            description=(
                "Submit an order to the simulated broker. Realistic fill "
                "modelling, latency, spread, partial fills, market impact."
            ),
            inputs=(
                Field("order", "OrderRequest"),
                Field("account", "Account", required=False),
            ),
            outputs=(Field("fill", "Fill"),),
            permissions=frozenset({"capital"}),
            risk=RiskLevel.HIGH,  # moves simulated capital; in production would be live
            version="0.1.0",
        ),
        Tool(
            name="trading.alpaca_paper_submit",
            kind=CapabilityKind.SIMULATION,
            plane=Plane.CONTROL,
            integration=IntegrationMode.INTERNAL,
            source="src/orion/integrations/brokers/alpaca.py",
            description=(
                "Submit a paper order to Alpaca. Live mode is blocked by "
                "construction unless the ORION config explicitly enables it."
            ),
            inputs=(Field("order", "Mapping[str, Any]"),),
            outputs=(Field("response", "Mapping[str, Any]"),),
            permissions=frozenset({"network", "capital", "read_secrets"}),
            risk=RiskLevel.HIGH,
            version="0.1.0",
        ),
        # -------------------------- references (cloned upstream repos)
        # These are the *capabilities* the reviewer said the cloned repos
        # should provide once wrapped. None of them are callable today;
        # they exist so the registry is honest about what *could* be
        # exposed and so the gap is visible.
        Tool(
            name="upstream.qlib.factors",
            kind=CapabilityKind.MODEL,
            plane=Plane.INTELLIGENCE,
            integration=IntegrationMode.REFERENCE,
            source="source_repositories/prediction/qlib",
            description=(
                "MSRA qlib factor library: alpha factors over OHLCV. "
                "REFERENCE only — not callable until an ORION adapter exists."
            ),
            inputs=(Field("market_data", "pandas.DataFrame", required=True),),
            outputs=(Field("factors", "pandas.DataFrame"),),
            permissions=frozenset(),
            risk=RiskLevel.LOW,
            upstream_path="source_repositories/prediction/qlib",
        ),
        Tool(
            name="upstream.vectorbt.backtest",
            kind=CapabilityKind.SIMULATION,
            plane=Plane.TRUTH,
            integration=IntegrationMode.REFERENCE,
            source="source_repositories/trading/vectorbt",
            description=(
                "vectorbt vectorised backtesting. PRIMARY engine per the "
                "audit, but REFERENCE here until a stdlib-compatible "
                "adapter is implemented (vectorbt requires numpy/pandas)."
            ),
            inputs=(Field("prices", "Sequence[float]"),),
            outputs=(Field("equity_curve", "Sequence[float]"),),
            permissions=frozenset(),
            risk=RiskLevel.LOW,
            upstream_path="source_repositories/trading/vectorbt",
        ),
        Tool(
            name="upstream.quantlib.pricing",
            kind=CapabilityKind.MODEL,
            plane=Plane.TRUTH,
            integration=IntegrationMode.REFERENCE,
            source="source_repositories/mathematics/QuantLib",
            description=(
                "QuantLib derivatives pricing (bonds, options, swaps). "
                "REFERENCE — QuantLib is C++; the Python bindings require "
                "a non-stdlib install."
            ),
            inputs=(Field("instrument", "str"),),
            outputs=(Field("npv", "float"),),
            permissions=frozenset(),
            risk=RiskLevel.LOW,
            upstream_path="source_repositories/mathematics/QuantLib",
        ),
        Tool(
            name="upstream.py_vollib.greeks",
            kind=CapabilityKind.MODEL,
            plane=Plane.TRUTH,
            integration=IntegrationMode.REFERENCE,
            source="source_repositories/mathematics/py_vollib",
            description=(
                "py_vollib option Greeks and implied volatility. "
                "REFERENCE — stdlib-compatible but no ORION adapter yet."
            ),
            inputs=(Field("option_type", "str"),),
            outputs=(Field("greeks", "Mapping[str, float]"),),
            permissions=frozenset(),
            risk=RiskLevel.LOW,
            upstream_path="source_repositories/mathematics/py_vollib",
        ),
        Tool(
            name="upstream.kronos.forecast",
            kind=CapabilityKind.FORECASTING,
            plane=Plane.INTELLIGENCE,
            integration=IntegrationMode.REFERENCE,
            source="source_repositories/prediction/Kronos",
            description=(
                "Kronos K-line foundation model. PRIMARY forecasting candidate "
                "per the audit, but REFERENCE here — the model weights are not "
                "in this repository and a real adapter is not implemented."
            ),
            inputs=(Field("klines", "Sequence[float]"),),
            outputs=(Field("forecast", "Sequence[float]"),),
            permissions=frozenset(),
            risk=RiskLevel.LOW,
            upstream_path="source_repositories/prediction/Kronos",
        ),
        Tool(
            name="upstream.fingpt.sentiment",
            kind=CapabilityKind.NLP,
            plane=Plane.INTELLIGENCE,
            integration=IntegrationMode.OPTIONAL,
            source="source_repositories/intelligence/FinGPT",
            description=(
                "FinGPT financial-domain LoRA-tuned LLM for sentiment and "
                "news NLG. OPTIONAL — heavy GPU dependency; ORION does not "
                "require FinGPT to be available."
            ),
            inputs=(Field("text", "str"),),
            outputs=(Field("sentiment", "Mapping[str, float]"),),
            permissions=frozenset({"network"}),
            risk=RiskLevel.LOW,
            upstream_path="source_repositories/intelligence/FinGPT",
        ),
        Tool(
            name="upstream.ollama.local_inference",
            kind=CapabilityKind.MODEL,
            plane=Plane.INTELLIGENCE,
            integration=IntegrationMode.DEPENDENCY,
            source="src/orion/models/local/ollama.py",
            description=(
                "Local LLM inference via the Ollama HTTP API. PRIMARY local "
                "inference path per the audit. Stdlib-only client; refuses "
                "without a reachable daemon."
            ),
            inputs=(Field("prompt", "str"),),
            outputs=(Field("completion", "str"),),
            permissions=frozenset({"network"}),
            risk=RiskLevel.LOW,
            upstream_path="source_repositories/intelligence/ollama",
        ),
        Tool(
            name="upstream.freqtrade.freqai",
            kind=CapabilityKind.MODEL,
            plane=Plane.INTELLIGENCE,
            integration=IntegrationMode.REFERENCE,
            source="source_repositories/trading/freqtrade",
            description=(
                "FreqAI ML pipeline from freqtrade. REFERENCE — crypto-only "
                "and tightly coupled to the freqtrade runtime; not adapted."
            ),
            inputs=(Field("ohlcv", "Mapping[str, Sequence[float]]"),),
            outputs=(Field("model", "Any"),),
            permissions=frozenset(),
            risk=RiskLevel.LOW,
            upstream_path="source_repositories/trading/freqtrade",
        ),
        Tool(
            name="upstream.finrl_market_env",
            kind=CapabilityKind.SIMULATION,
            plane=Plane.TRUTH,
            integration=IntegrationMode.REFERENCE,
            source="source_repositories/trading/FinRL-Meta",
            description=(
                "FinRL-Meta market environments for DRL. REFERENCE — Python "
                "is in scope but the gym environments are not wrapped in an "
                "ORION adapter."
            ),
            inputs=(Field("asset", "str"),),
            outputs=(Field("env", "Any"),),
            permissions=frozenset(),
            risk=RiskLevel.LOW,
            upstream_path="source_repositories/trading/FinRL-Meta",
        ),
    ]
    reg.register_many(tools)
    reg.freeze()
    return reg
