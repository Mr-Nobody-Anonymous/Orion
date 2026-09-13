"""Test suite for all 30 external repository adapters and integration registry."""

from __future__ import annotations

import pytest

from orion.capabilities.agent_memory import MemoryRecord, MemoryRetrievalRequest
from orion.capabilities.backtesting import BacktestRequest
from orion.capabilities.execution import ExecutionRequest
from orion.capabilities.fixed_income import BondPricingRequest
from orion.capabilities.forecasting import ForecastRequest
from orion.capabilities.options import OptionPricingRequest
from orion.capabilities.prediction_markets import PMDiscoveryRequest
from orion.capabilities.reinforcement_learning import RLPolicyRequest
from orion.capabilities.sentiment import SentimentAnalysisRequest
from orion.dashboard.web import DashboardState
from orion.integrations.agents.a_evolve import AEvolveAdapter
from orion.integrations.agents.agentic_trading import AgenticTradingAdapter
from orion.integrations.agents.evolver import EvolverAdapter
from orion.integrations.agents.hermes import HermesMemoryAdapter
from orion.integrations.agents.quantmuse import QuantMuseAdapter
from orion.integrations.agents.vibe_trading import VibeTradingAdapter
from orion.integrations.financial_llm.fingpt import FinGPTSentimentProvider
from orion.integrations.forecasting.kronos import KronosForecasterAdapter
from orion.integrations.forecasting.neural_prophet import NeuralProphetForecasterAdapter
from orion.integrations.forecasting.qlib import QlibFactorProvider
from orion.integrations.forecasting.tslib import TimeSOFABenchmarkAdapter
from orion.integrations.inference.airllm import AirLLMInferenceAdapter
from orion.integrations.inference.kimi import KimiInferenceAdapter
from orion.integrations.inference.ollama import OllamaInferenceProvider
from orion.integrations.mathematics.py_vollib import PyVollibOptionsProvider
from orion.integrations.mathematics.quantlib import QuantLibFixedIncomeProvider
from orion.integrations.prediction_markets.homerun import HomerunSimulatorAdapter
from orion.integrations.prediction_markets.toolkit import PMToolkitAdapter
from orion.integrations.prediction_markets.weather_bot import WeatherArbitrageAdapter
from orion.integrations.provenance import load_provenance_manifest
from orion.integrations.registry import get_capability_router, get_master_registry
from orion.integrations.research.assume import AssumeEnergyMarketAdapter, PowerMarketBids
from orion.integrations.research.stock_environment import StockTradingEnvironmentProvenance
from orion.integrations.trading.backtrader import BacktraderAdapter
from orion.integrations.trading.finrl import FinRLPolicyBenchmarkAdapter
from orion.integrations.trading.finrl_meta import FinRLMetaEnvironmentAdapter, MarketEnvConfig
from orion.integrations.trading.freqtrade import FreqtradeCryptoAdapter
from orion.integrations.trading.intelligent_trading_bot import IntelligentTradingBotAdapter
from orion.integrations.trading.jesse import JesseCryptoRiskAdapter
from orion.integrations.trading.lean import LeanSidecarClient
from orion.integrations.trading.vectorbt import VectorBTAdapter


def test_provenance_manifest_loads_all_30():
    """Verify that MANIFEST.yaml is parsed into exactly 30 validated repository records."""
    records = load_provenance_manifest()
    assert len(records) == 30
    names = set(records.keys())
    assert "Kronos" in names
    assert "QuantLib" in names
    assert "vectorbt" in names
    assert "FinGPT" in names
    assert "ollama" in names


def test_master_registry_initialization():
    """Verify master registry instantiates all adapters and builds health report."""
    reg = get_master_registry()
    adapters = reg.get_all_adapters()
    assert len(adapters) >= 30

    health = reg.get_health_report()
    assert "summary" in health
    assert health["summary"]["total_repositories"] == 30
    assert health["summary"]["coverage_pct"] > 0
    assert len(health["adapters"]) >= 30


def test_agents_adapters():
    """Test all agent adapters for multi-agent coordination, tools, and memory."""
    at = AgenticTradingAdapter()
    coord = at.coordinate_agents("Evaluate NVDA", ["research", "risk", "trading"])
    assert coord["status"] == "COMPLETED"

    qm = QuantMuseAdapter()
    hypo = qm.extract_alpha_hypotheses("NVIDIA reported record datacenter revenue growth of 120% YoY")
    assert len(hypo) > 0
    assert hypo[0]["confidence"] > 0.5

    vt = VibeTradingAdapter()
    manifest = vt.format_mcp_manifest([{"name": "market.get_price", "description": "Fetch asset price"}])
    assert manifest["protocol"] == "mcp-v1"

    ae = AEvolveAdapter()
    mutated = ae.mutate_strategy_genome({"lookback": 20, "stop_loss_pct": 0.05})
    assert mutated["generation"] == 1

    ev = EvolverAdapter()
    rec = ev.generate_lineage_record("Momentum_v2", "Momentum_v1", "parameter_tuning")
    assert rec["parent"] == "Momentum_v1"

    hm = HermesMemoryAdapter()
    stored = hm.record_experience(
        MemoryRecord(
            record_id="TEST-01",
            kind="mistake",
            summary="Slippage was 12bps higher on thin book",
            similarity_score=0.9,
        )
    )
    assert stored is True

    search_res = hm.search_memory(MemoryRetrievalRequest("rate shock", top_k=2))
    assert search_res.total_records >= 1


def test_inference_adapters():
    """Test inference adapters (Ollama, AirLLM, Kimi)."""
    ol = OllamaInferenceProvider()
    assert ol.health().status.value in ("available", "degraded", "simulated")

    air = AirLLMInferenceAdapter()
    assert air.is_memory_constrained(8.0) is True

    kimi = KimiInferenceAdapter()
    assert kimi.health().status.value in ("isolated", "unavailable", "simulated")


def test_financial_llm_sentiment():
    """Test FinGPT financial sentiment analysis."""
    fg = FinGPTSentimentProvider()
    res = fg.analyze_sentiment(SentimentAnalysisRequest("Record earnings and dividend increase", "AAPL"))
    assert res.sentiment_label in ("BULLISH", "NEUTRAL", "BEARISH")


def test_prediction_markets_adapters():
    """Test Kalshi, Homerun, and WeatherBot adapters."""
    pm = PMToolkitAdapter()
    contracts = pm.list_contracts(PMDiscoveryRequest("fed"))
    assert len(contracts) > 0
    edge = pm.evaluate_edge(contracts[0], 0.70)
    assert edge.edge_pct > 0

    hr = HomerunSimulatorAdapter()
    hr_contracts = hr.list_contracts(PMDiscoveryRequest("macro"))
    assert len(hr_contracts) > 0

    wb = WeatherArbitrageAdapter()
    wb_contracts = wb.list_contracts(PMDiscoveryRequest("weather"))
    assert len(wb_contracts) > 0


def test_mathematics_adapters():
    """Test QuantLib and py_vollib with fallback safety."""
    ql = QuantLibFixedIncomeProvider()
    bond_res = ql.price_bond(BondPricingRequest(1000.0, 5.0, 5.0, 5.0, 2))
    assert abs(bond_res.clean_price - 1000.0) < 0.05

    pv = PyVollibOptionsProvider()
    opt_res = pv.calculate_greeks(
        OptionPricingRequest(
            underlying_price=100.0,
            strike_price=100.0,
            time_to_expiry_years=1.0,
            volatility=0.2,
            risk_free_rate=0.05,
            is_call=True,
        )
    )
    assert opt_res.delta > 0.0


def test_forecasting_adapters():
    """Test Kronos, Qlib, NeuralProphet, and TSLib."""
    kr = KronosForecasterAdapter()
    fc = kr.forecast(ForecastRequest("NVDA", [100, 101, 102, 103, 104], 3))
    assert fc.predicted_return != 0.0 or fc.confidence > 0.0

    qlib = QlibFactorProvider()
    factors = qlib.extract_alpha158_factors([100, 101, 102, 103, 104, 105])
    assert "momentum_5" in factors

    np = NeuralProphetForecasterAdapter()
    np_fc = np.forecast(ForecastRequest("SPY", [500, 502, 501, 505], 2))
    assert np_fc.predicted_return != 0.0 or np_fc.confidence > 0.0

    tslib = TimeSOFABenchmarkAdapter()
    bench = tslib.run_benchmark_comparison([100, 101, 102, 103, 104])
    assert len(bench["benchmark_results"]) >= 3


def test_trading_adapters():
    """Test VectorBT, Backtrader, Freqtrade, Jesse, Lean, FinRL, and Online Learner."""
    vbt = VectorBTAdapter()
    res = vbt.run_backtest(BacktestRequest("Trend", "BTC", [50000, 51000, 52000, 51500, 53000]))
    assert res.total_trades >= 0

    bt = BacktraderAdapter()
    bt_res = bt.run_backtest(BacktestRequest("Event", "ETH", [3000, 3100, 3050, 3200]))
    assert bt_res.equity_curve is not None

    ft = FreqtradeCryptoAdapter()
    stop = ft.calculate_trailing_stop(98.0, 100.0)
    assert stop > 0.0

    js = JesseCryptoRiskAdapter()
    sizing = js.calculate_position_size(100_000.0, 1.0, 100.0, 95.0, leverage=2.0)
    assert sizing.position_size > 0.0

    lean = LeanSidecarClient()
    ord_res = lean.submit_order(ExecutionRequest("AAPL", "BUY", 10.0))
    assert ord_res.status in ("FILLED", "SUBMITTED")

    finrl = FinRLPolicyBenchmarkAdapter()
    rl_res = finrl.train_policy(RLPolicyRequest("PPO", 10, 2), [100, 102, 101, 104, 106])
    assert rl_res.convergence_status is not None

    meta = FinRLMetaEnvironmentAdapter()
    spec = meta.build_environment_spec(MarketEnvConfig(("AAPL", "MSFT")))
    assert spec["gym_compatible"] is True

    itb = IntelligentTradingBotAdapter()
    drift = itb.detect_drift([1.0, 1.1, 1.0, 0.9], [2.5, 2.6, 2.7, 2.8])
    assert drift.drift_detected is True


def test_research_adapters():
    """Test ASSUME and Stock Trading Environment provenance."""
    stock_prov = StockTradingEnvironmentProvenance()
    meta = stock_prov.get_provenance_metadata()
    assert meta["status"] == "deprecated"

    assume = AssumeEnergyMarketAdapter()
    bids = PowerMarketBids("DE-LU", [50.0, 100.0], [45.0, 60.0], 80.0)
    cleared = assume.clear_market(bids)
    assert cleared.clearing_price_eur_mwh == 60.0


def test_dashboard_state_integrations_health():
    """Verify DashboardState serves integration health snapshot."""
    state = DashboardState()
    health = state.api_integrations_health()
    assert "summary" in health
    assert health["summary"]["total_repositories"] == 30

    test_res = state.api_test_integration("Kronos")
    assert test_res["success"] is True
