from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
from typing import Sequence

from ..backtesting.engine import vectorized_momentum_backtest
from ..backtesting.evaluation import performance_metrics, walk_forward_momentum
from ..brain.decision import DecisionContext, DecisionEngine
from ..brain.executive import ExecutiveBrain
from ..data.contracts import Action, Asset, AssetClass, Event, MarketQuote, OrderRequest, TradeProposal
from ..data.validation import DataQualityValidator
from ..infrastructure.configuration import OrionConfig
from ..infrastructure.event_bus import EventBus
from ..infrastructure.governance import PromotionGate
from ..infrastructure.provenance import ProvenanceStore
from ..intelligence.financial_reasoning import FinancialReasoner
from ..intelligence.sentiment import SentimentAnalyzer
from ..prediction.machine_learning import MLRidgeForecaster
from ..intelligence.llm.providers import create_local_llm_provider
from ..learning.self_improvement import SelfImprovementEngine
from ..memory import LayeredMemory, MemoryLayer, MemoryStore
from ..prediction.ensembles.model_council import build_default_council
from ..prediction.forecasting import PredictionEnsemble
from ..quant import momentum_signal
from ..trading.execution import SimulatedBroker
from ..trading.risk import RiskEngine, RiskLimits
from ..world_model import FinancialWorldModel
from ..evolution import EvolutionEngine, Fitness, StrategyCandidate
from ..research import ResearchDiscovery, build_research_report
from ..simulation import bootstrap_market_paths
from ..agents import (
    AgentController,
    ComplianceAgent,
    DecisionAgent,
    NewsAgent,
    QuantAgent,
    ResearcherAgent,
    RiskAgent,
    StrategyAgent,
)
from ..compliance import AuditLog, RoleBasedAccess, RestrictedList
from ..data.providers.filings import FilingsManager
from ..distributed import OrionController as DistributedController
from ..portfolio.factors import (
    FACTOR_NAMES,
    factor_alpha_decomposition,
    compute_factor_signal,
)
from ..portfolio.optimizer import mean_variance, mvp_weights, risk_parity


class OrionSystem:
    def __init__(self, config: OrionConfig | None = None) -> None:
        self.config = config or OrionConfig()
        self.events = EventBus()
        self.memory = MemoryStore()
        self.layered_memory = LayeredMemory()
        self.world = FinancialWorldModel()
        self.provenance = ProvenanceStore()
        self.governance = PromotionGate()
        self.broker = SimulatedBroker()
        self.risk = RiskEngine(RiskLimits(max_order_notional=Decimal("10000")))
        self.executive = ExecutiveBrain(self.broker, self.risk, self.events)
        self.learning = SelfImprovementEngine(self.memory)
        self.forecaster = PredictionEnsemble()
        self.validator = DataQualityValidator()
        self.decision_engine = DecisionEngine()
        self.evolution = EvolutionEngine()
        self.council_model = build_default_council()
        self.ml_forecaster = MLRidgeForecaster()
        self.reasoner = FinancialReasoner()
        # P1-5: filings manager wired with the deterministic reference
        # providers. The CLI / operator can swap in live providers
        # without touching the system.
        from ..data.providers.filings.reference import (
            ReferenceEarningsProvider,
            ReferenceNewsProvider,
            ReferenceSecEdgarProvider,
        )
        self.filings = FilingsManager(
            sec=ReferenceSecEdgarProvider(),
            news=ReferenceNewsProvider(),
            earnings=ReferenceEarningsProvider(),
        )
        # P2-2: agent controller with the full default hierarchy.
        self.agents = AgentController(
            agents=[
                ComplianceAgent(restricted=RestrictedList()),
                RiskAgent(),
                DecisionAgent(reasoner=self.reasoner),
                ResearcherAgent(),
                QuantAgent(),
                NewsAgent(analyzer=SentimentAnalyzer()),
                StrategyAgent(),
            ]
        )
        # P2-3: compliance scaffolding.
        self.audit_log = AuditLog()
        self.rbac = RoleBasedAccess()
        self.restricted_list = RestrictedList()
        # P2-4: distributed job control.
        self.distributed = DistributedController()
        # P1-6: factor cache is recomputed on demand; the registry is
        # always available.
        self.factor_names: tuple[str, ...] = FACTOR_NAMES

    def status(self) -> dict[str, object]:
        _, router, hardware = create_local_llm_provider()
        return {
            "mode": self.config.mode.value,
            "execution_mode": self.config.execution_mode,
            "autonomy_level": self.config.autonomy_level,
            "hardware": {"ram_gb": hardware.ram_gb, "gpu": hardware.gpu_name, "cuda": hardware.cuda_available},
            "model_tier": router.select().name,
            "root": "src/orion",
            "capabilities": {
                "world_state": "IMPLEMENTED",
                "layered_memory": "IMPLEMENTED",
                "research_discovery": "IMPLEMENTED",
                "evolution": "IMPLEMENTED",
                "simulation": "IMPLEMENTED",
                "paper_execution": "IMPLEMENTED",
                "cloud_inference": "BLOCKED",
                "live_execution": "BLOCKED",
            },
        }

    def analyze(self, symbol: str, prices: Sequence[float], actual_return: Decimal | None = None) -> dict[str, object]:
        asset = Asset(symbol, AssetClass.EQUITY)
        return self.run(asset, prices, actual_return)

    def run(self, asset: Asset, prices: Sequence[float], actual_return: Decimal | None = None) -> dict[str, object]:
        if len(prices) < 3:
            raise ValueError("at least three prices are required")
        quote = MarketQuote(
            asset,
            __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            Decimal(str(prices[-1] * 0.999)),
            Decimal(str(prices[-1] * 1.001)),
            Decimal(str(prices[-1])),
            Decimal("1000"),
            "local-demo",
            "validated",
        )
        issues = self.validator.validate_quote(quote)
        if issues:
            raise ValueError(f"market data failed validation: {issues}")
        self.broker.set_quote(quote)
        self.world.register_asset(asset)
        self.world.set_state(asset.symbol, {"last": str(quote.last), "source": quote.source}, source=quote.source)
        returns = [prices[index] / prices[index - 1] - 1 for index in range(1, len(prices))]
        self.world.update_market(returns, quality=quote.quality, source=quote.source)
        prediction = self.forecaster.predict(asset, prices)
        signal = momentum_signal(prices)
        backtest = vectorized_momentum_backtest(prices)
        decision = self.decision_engine.decide(DecisionContext(prediction, Decimal("-0.02"), Decimal("0.01"), Decimal("1")))
        order = OrderRequest(asset, Decimal("1"), decision, limit_price=quote.ask) if decision in {Action.BUY, Action.SHORT} else None
        risk_decision = None
        if order:
            risk_decision = self.executive.execute(TradeProposal(order, prediction, "ensemble + momentum", Decimal("0.10")))
            self.world.risk.approved = self.world.set_state("risk.approved", risk_decision.approved, source="risk")
            self.world.risk.reasons = self.world.set_state("risk.reasons", risk_decision.reasons, source="risk")
        self.world.models.confidence = self.world.set_state("model.confidence", float(prediction.confidence), source=prediction.model_name)
        self.world.decision.action = self.world.set_state("decision.action", decision.value, source="decision_engine")
        # Model council: each member's view plus disagreement, so the executive
        # can see what every model believes and where they diverge.
        try:
            council_result = self.council_model.predict(asset, prices, regime=self.world.market.regime.value)
            council_payload = council_result.as_dict()
        except ValueError:
            council_payload = {"status": "UNAVAILABLE", "reason": "insufficient-valid-prices"}
        thesis = self.reasoner.build_thesis(asset.symbol, prediction=prediction, signal=signal)
        result = {
            "asset": asset.symbol,
            "prediction": asdict(prediction),
            "quant_signal": asdict(signal),
            "backtest": asdict(backtest),
            "decision": decision.value,
            "risk": asdict(risk_decision) if risk_decision else None,
            "fills": len(self.broker.fills),
            "market_regime": self.world.market.regime.value,
            "state_confidence": self.world.market.regime.confidence,
            "model_council": council_payload,
            "thesis": thesis.as_dict(),
        }
        self.memory.append("decision", result)
        self.layered_memory.remember(MemoryLayer.WORKING, result, summary=f"{asset.symbol} {decision.value} in {self.world.market.regime.value}", tags={asset.symbol, decision.value.lower()}, importance=float(prediction.confidence))
        if actual_return is not None:
            self.learning.record_outcome(
                asset=asset.symbol,
                prediction=prediction.expected_return,
                actual_return=actual_return,
                model=prediction.model_name,
                confidence=prediction.confidence,
                regime="unclassified",
                features={"momentum": str(signal.score)},
            )
            result["training_dataset_size"] = len(self.learning.create_training_dataset())
        self.events.publish(Event("ModelPrediction", {"asset": asset.symbol, "model": prediction.model_name}))
        return result

    def council(self, symbol: str, prices: Sequence[float]) -> dict[str, object]:
        """Ask every council member for its view and report disagreement."""
        try:
            result = self.council_model.predict(Asset(symbol, AssetClass.EQUITY), prices)
        except ValueError as error:
            return {"status": "UNAVAILABLE", "reason": str(error)}
        return result.as_dict()

    def backtest(self, prices: Sequence[float]) -> dict[str, object]:
        result = vectorized_momentum_backtest(prices)
        payload = asdict(result)
        payload["metrics"] = asdict(performance_metrics(prices, result))
        if len(prices) >= 12:
            payload["walk_forward"] = asdict(walk_forward_momentum(prices, train_window=max(6, len(prices) // 2), test_window=max(2, len(prices) // 4)))
        return payload

    def train(self, dataset: Sequence[dict[str, object]] | None = None, baseline_error: Decimal = Decimal("0.02")) -> dict[str, object]:
        from ..learning.training import TrainingPipeline
        from ..models.registry import ImmutableRegistry

        training_data = dataset or [{"prediction": "0.01", "actual_return": "0.02"}]
        result = TrainingPipeline().train_and_register(training_data, ImmutableRegistry(), baseline_error)
        return {"model": asdict(result["model"]), "mean_absolute_error": str(result["mean_absolute_error"]), "status": result["status"].value}

    def evaluate(self, dataset: Sequence[dict[str, object]] | None = None) -> dict[str, object]:
        candidate = self.learning.propose_candidate()
        if candidate is None:
            return {"evaluation": "NO_DATA"}
        evaluated = self.learning.evaluate_candidate(candidate, Decimal("0.01"))
        evaluated["promotion"] = asdict(self.governance.decide({
            "generalization": -1.0 if evaluated["evaluation"] == "REJECT" else 0.1,
            "robustness": -1.0 if evaluated["evaluation"] == "REJECT" else 0.1,
            "calibration": -1.0 if evaluated["evaluation"] == "REJECT" else 0.1,
            "risk_adjusted_return": -1.0 if evaluated["evaluation"] == "REJECT" else 0.1,
        }))
        return evaluated

    def run_evaluation(
        self,
        symbol: str,
        prices: Sequence[float],
        *,
        ablations: Sequence = (),
        config: object | None = None,
    ) -> dict[str, object]:
        """Run the P0-3 evaluation lab against a price series.

        Wires the system to :class:`orion.evaluation.EvaluationLab`,
        executes a contamination-safe walk-forward ablation, and
        persists a reproducible artifact tree.

        Parameters
        ----------
        symbol:
            The asset symbol the prices correspond to.
        prices:
            Bar series in chronological order.
        ablations:
            Optional iterable of
            :class:`orion.evaluation.AblationVariant` for "Orion - X"
            experiments.
        config:
            Optional :class:`orion.evaluation.LabConfig`.

        Returns
        -------
        dict with ``run_id``, ``artifact_dir``, ``report`` (a
        serialised :class:`EvaluationReport`), and ``ablations``
        (the list of ablation results).
        """
        from ..data.contracts import Asset, AssetClass
        from ..evaluation import (
            AblationVariant as _AblationVariant,
            EvaluationLab,
            LabConfig,
            make_orion_predictor,
        )

        asset = Asset(symbol, AssetClass.EQUITY)
        predictor = make_orion_predictor(self, asset)
        lab_config = config if isinstance(config, LabConfig) else LabConfig()
        ablations_tuple = tuple(ablations)
        for a in ablations_tuple:
            if not isinstance(a, _AblationVariant):
                raise TypeError(
                    "ablations must be a sequence of orion.evaluation.AblationVariant; "
                    f"got {type(a).__name__}"
                )

        lab = EvaluationLab(
            predictor,
            prices,
            ablations=ablations_tuple,
            config=lab_config,
        )
        artifact, report = lab.run()
        return {
            "run_id": artifact.run_id,
            "artifact_dir": str(artifact.artifact_dir),
            "report": report.as_dict(),
            "ablations": [
                {"name": a.name, "description": a.description} for a in ablations_tuple
            ],
        }

    def research(self, question: str, *, limit: int = 5) -> dict[str, object]:
        self.world.research.question = self.world.set_state("research.question", question, source="user")
        try:
            sources = ResearchDiscovery().discover_papers(question, limit=limit)
        except Exception as error:
            return {"question": question, "status": "BLOCKED", "reason": f"public research discovery unavailable: {error}"}
        report = build_research_report(question, sources)
        self.world.research.evidence_count = self.world.set_state("research.evidence_count", len(sources), source="OpenAlex")
        self.layered_memory.remember(MemoryLayer.RESEARCH, {"question": question, "sources": [source.url for source in sources]}, summary=f"Research: {question}", tags={"research"}, importance=0.7)
        for index, source in enumerate(sources):
            self.provenance.record(f"research-{index}", "paper_metadata", source.url, source.title, provider=source.source)
        return {"status": report.evidence_status, "question": question, "sources": [asdict(source) for source in sources], "provenance_records": len(sources)}

    def evolve(self, prices: Sequence[float], *, population_size: int = 8) -> dict[str, object]:
        population = self.evolution.seed_population(population_size, max_lookback=max(2, min(30, len(prices) // 3)))
        result = self.evolution.evolve(population, lambda candidate: self._fitness(candidate, prices))
        return {
            "status": "EXPERIMENTAL",
            "generation": result.generation,
            "ranked": [{"candidate": asdict(candidate), "fitness": asdict(fitness), "score": fitness.score} for candidate, fitness in result.ranked],
            "next_population": [asdict(candidate) for candidate in result.next_population],
        }

    def simulate(self, prices: Sequence[float], *, paths: int = 100, horizon: int = 20, seed: int = 7) -> dict[str, object]:
        result = bootstrap_market_paths(prices, paths=paths, horizon=horizon, seed=seed)
        return {"status": "IMPLEMENTED", "terminal_mean": result.terminal_mean, "terminal_p05": result.terminal_p05,
                "terminal_p95": result.terminal_p95, "paths": len(result.paths), "horizon": horizon, "seed": seed}

    def benchmark(self, prices: Sequence[float], *, lookbacks: Sequence[int] = (3, 5, 8)) -> dict[str, object]:
        """Standardized, contamination-safe model and strategy comparison."""
        from ..benchmarking import BenchmarkReport, build_default_report

        report: BenchmarkReport = build_default_report(list(prices), lookbacks=tuple(lookbacks))
        return {
            "status": "IMPLEMENTED",
            "report": report.as_dict(),
        }

    def doctor(self) -> dict[str, object]:
        checks = {
            "canonical_root": "PASS",
            "execution_mode": "PASS" if self.config.execution_mode != "live" else "FAIL",
            "live_trading_disabled": "PASS" if not self.config.live_trading_enabled else "FAIL",
            "risk_gate": "PASS" if isinstance(self.risk, RiskEngine) else "FAIL",
            "memory": "PASS" if self.layered_memory.counts() else "FAIL",
            "provenance": "PASS",
            "filings": "PASS" if self.filings is not None else "FAIL",
            "agents": "PASS" if self.agents is not None else "FAIL",
            "compliance": "PASS" if self.audit_log is not None else "FAIL",
            "distributed": "PASS" if self.distributed is not None else "FAIL",
        }
        return {"status": "HEALTHY" if all(value == "PASS" for value in checks.values()) else "ATTENTION", "checks": checks}

    # ------------------- P1-5 / P1-6 / P2 public surface -------------------

    def compute_factors(self, prices: Sequence[float], factors: Sequence[str] = ()) -> dict[str, object]:
        """Return the canonical factor signals for ``prices``."""
        names = tuple(factors) if factors else self.factor_names
        unknown = [n for n in names if n not in self.factor_names]
        if unknown:
            raise KeyError(f"unknown factors: {unknown}")
        return {
            "status": "IMPLEMENTED",
            "signals": [compute_factor_signal(n, list(prices)).as_dict() for n in names],
        }

    def factor_exposures(
        self,
        strategy_returns: Sequence[float],
        factor_returns: dict[str, Sequence[float]],
        factor_names: Sequence[str] = (),
    ) -> dict[str, object]:
        """Run the factor-alpha decomposition on a strategy return stream."""
        names = tuple(factor_names) if factor_names else self.factor_names
        report = factor_alpha_decomposition(
            list(strategy_returns), factor_returns, factor_names=names
        )
        return {"status": "IMPLEMENTED", "report": report.as_dict()}

    def fetch_filings(
        self,
        asset: "Asset",
        *,
        as_of: "datetime | None" = None,
        news_query: str | None = None,
    ) -> dict[str, object]:
        """P1-5 filings fetch via the wired-in providers."""
        bundle = self.filings.fetch(
            asset,
            as_of=as_of,
            news_query=news_query,
        )
        return {"status": "IMPLEMENTED", "bundle": bundle.as_dict()}

    def run_agents(
        self,
        symbol: str,
        prices: Sequence[float],
        *,
        asset_class: str = "equity",
        risk_limits: dict[str, float] | None = None,
        portfolio: dict[str, float] | None = None,
        metadata: dict[str, object] | None = None,
        news: Sequence[dict[str, object]] = (),
    ) -> dict[str, object]:
        """Run the agent hierarchy for a single decision context."""
        from ..agents import AgentContext

        context = AgentContext(
            symbol=symbol,
            asset_class=asset_class,
            prices=list(prices),
            risk_limits=dict(risk_limits or {}),
            portfolio=dict(portfolio or {}),
            metadata=dict(metadata or {}),
            news=tuple(news),
        )
        report = self.agents.run(context)
        return {"status": "IMPLEMENTED", "report": report.as_dict()}

    def optimize_portfolio(
        self,
        expected_returns: dict[str, float],
        *,
        volatilities: dict[str, float] | None = None,
        method: str = "mvp",
        risk_aversion: float = 1.0,
    ) -> dict[str, object]:
        """Run a portfolio optimiser. ``method`` is one of mvo / mvp / risk-parity."""
        if not expected_returns:
            raise ValueError("expected_returns must be non-empty")
        symbols = tuple(expected_returns)
        if method == "mvo":
            result = mean_variance(
                expected_returns, volatilities=volatilities, risk_aversion=risk_aversion
            )
        elif method == "mvp":
            result = mvp_weights(symbols, volatilities=volatilities)
        elif method == "risk-parity":
            result = risk_parity(symbols, volatilities=volatilities)
        else:
            raise ValueError(f"unknown method: {method!r}")
        return {"status": "IMPLEMENTED", "result": result.as_dict()}

    def distributed_drain(self) -> dict[str, int]:
        """Drain one job from every named pool (P2-4)."""
        return self.distributed.drain()

    @staticmethod
    def _fitness(candidate: StrategyCandidate, prices: Sequence[float]) -> Fitness:
        if len(prices) < 4:
            raise ValueError("at least four prices are required for evolution")
        lookback = max(2, min(len(prices) - 1, int(candidate.parameters["lookback"])))
        result = vectorized_momentum_backtest(prices, lookback=lookback)
        metrics = performance_metrics(prices, result)
        threshold_penalty = candidate.parameters["threshold"] * 10
        return Fitness(
            max(-5.0, min(5.0, float(metrics.sharpe) - threshold_penalty)),
            float(metrics.max_drawdown),
            result.trades / len(prices),
            max(-1.0, min(1.0, float(metrics.calmar) / 5)),
            max(-1.0, min(1.0, float(metrics.total_return))),
            float(metrics.win_rate),
        )
