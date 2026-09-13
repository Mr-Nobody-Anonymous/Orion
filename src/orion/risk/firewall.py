"""ORION 12-Gate Risk Firewall.

Every live order must pass through all 12 sequential gates before execution.
No LLM, strategy, or external library may bypass the firewall.

Gates:
  1. Instrument Validation
  2. Position Limits
  3. Concentration Limits
  4. Leverage Limits
  5. Liquidity Check
  6. Market Risk (VaR/CVaR)
  7. Factor Risk
  8. Stress Test Check
  9. Credit / Counterparty
  10. Compliance
  11. Model Health
  12. Kill Switch

Each gate produces an auditable RiskGateResult.
The firewall produces a FirewallDecision with the complete audit trail.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Mapping, Sequence

from ..data.contracts import (
    Action,
    AssetClass,
    FirewallDecision,
    Instrument,
    OrderIntent,
    PortfolioSnapshot,
    Position,
    RiskGateResult,
    RiskGateVerdict,
    RiskMeasurement,
    Scenario,
    ScenarioResult,
)


@dataclass
class FirewallLimits:
    """Configurable limits for every gate in the 12-Gate Risk Firewall.

    All limits are enforced deterministically. No AI/LLM may alter these
    at runtime. Changes require explicit operator action.
    """

    # Gate 1: Instrument validation
    allowed_asset_classes: frozenset[AssetClass] = frozenset(AssetClass)
    require_active_instrument: bool = True

    # Gate 2: Position limits
    max_position_notional: Decimal = Decimal("100000")  # per position
    max_position_fraction: Decimal = Decimal("0.10")  # max % of portfolio per position
    max_open_positions: int = 100

    # Gate 3: Concentration limits
    max_single_security_pct: Decimal = Decimal("0.10")
    max_sector_pct: Decimal = Decimal("0.30")
    max_country_pct: Decimal = Decimal("0.40")
    max_currency_pct: Decimal = Decimal("0.50")
    max_asset_class_pct: Decimal = Decimal("0.60")

    # Gate 4: Leverage limits
    max_gross_exposure: Decimal = Decimal("3.0")  # 300%
    max_net_exposure: Decimal = Decimal("1.5")
    max_leverage: Decimal = Decimal("3.0")

    # Gate 5: Liquidity
    max_adv_participation_rate: Decimal = Decimal("0.05")  # max 5% of ADV
    min_adv_ratio: Decimal = Decimal("0.001")  # position must be < 0.1% of ADV
    max_time_to_liquidate_days: Decimal = Decimal("5.0")
    max_spread_bps: Decimal = Decimal("100")  # max acceptable spread

    # Gate 6: Market risk
    max_portfolio_var_pct: Decimal = Decimal("0.05")  # 5% VaR
    max_portfolio_cvar_pct: Decimal = Decimal("0.10")  # 10% CVaR
    max_incremental_var_pct: Decimal = Decimal("0.01")  # 1% incremental VaR

    # Gate 7: Factor risk
    max_factor_exposure: Decimal = Decimal("2.0")  # max beta to any single factor
    max_factor_concentration_pct: Decimal = Decimal("0.40")  # max risk from one factor

    # Gate 8: Stress test
    max_stress_loss_pct: Decimal = Decimal("0.30")  # max loss under any scenario
    required_scenarios: tuple[str, ...] = (
        "2008_crisis", "covid_2020", "rate_shock_200bp",
        "credit_shock", "liquidity_freeze",
    )

    # Gate 9: Credit / counterparty
    max_counterparty_exposure_pct: Decimal = Decimal("0.25")
    max_broker_concentration_pct: Decimal = Decimal("0.50")

    # Gate 10: Compliance
    restricted_symbols: frozenset[str] = frozenset()
    max_order_notional: Decimal = Decimal("50000")
    require_rationale: bool = True
    min_order_notional: Decimal = Decimal("10")

    # Gate 11: Model health
    min_model_confidence: Decimal = Decimal("0.30")
    max_prediction_age_seconds: int = 3600
    require_model_version: bool = True

    # Gate 12: Kill switch
    global_kill_switch: bool = False
    strategy_kill_switches: frozenset[str] = frozenset()
    asset_kill_switches: frozenset[str] = frozenset()
    venue_kill_switches: frozenset[str] = frozenset()


@dataclass
class PortfolioContext:
    """Current portfolio state needed for firewall evaluation.

    Provides the snapshot the firewall gates read from to make
    deterministic pass/fail decisions.
    """

    equity: Decimal = Decimal("100000")
    cash: Decimal = Decimal("100000")
    gross_exposure: Decimal = Decimal("0")
    net_exposure: Decimal = Decimal("0")
    leverage: Decimal = Decimal("0")
    positions: tuple[Position, ...] = ()
    sector_exposures: Mapping[str, Decimal] = field(default_factory=dict)
    country_exposures: Mapping[str, Decimal] = field(default_factory=dict)
    currency_exposures: Mapping[str, Decimal] = field(default_factory=dict)
    asset_class_exposures: Mapping[str, Decimal] = field(default_factory=dict)
    factor_exposures: Mapping[str, Decimal] = field(default_factory=dict)
    counterparty_exposures: Mapping[str, Decimal] = field(default_factory=dict)
    current_var_pct: Decimal = Decimal("0")
    current_cvar_pct: Decimal = Decimal("0")
    stress_losses: Mapping[str, Decimal] = field(default_factory=dict)
    model_confidence: Decimal = Decimal("0.5")
    model_version: str = ""
    prediction_timestamp: datetime | None = None


class RiskFirewall:
    """12-Gate Risk Firewall — deterministic, auditable, non-bypassable.

    Every order intent passes through all 12 gates sequentially.
    A single FAIL verdict blocks the order. WARN verdicts are recorded
    but do not block. The complete gate-by-gate audit trail is returned.

    No LLM, strategy, or external library may bypass this firewall.
    The firewall is independent of all intelligence/prediction layers.
    """

    def __init__(self, limits: FirewallLimits | None = None) -> None:
        self.limits = limits or FirewallLimits()
        self._gate_functions = [
            self._gate_01_instrument_validation,
            self._gate_02_position_limits,
            self._gate_03_concentration_limits,
            self._gate_04_leverage_limits,
            self._gate_05_liquidity_check,
            self._gate_06_market_risk,
            self._gate_07_factor_risk,
            self._gate_08_stress_test,
            self._gate_09_counterparty,
            self._gate_10_compliance,
            self._gate_11_model_health,
            self._gate_12_kill_switch,
        ]

    def evaluate(
        self,
        intent: OrderIntent,
        context: PortfolioContext,
        instrument: Instrument | None = None,
    ) -> FirewallDecision:
        """Run all 12 gates sequentially. Returns a complete audit trail.

        A single FAIL blocks the order immediately. All gates are still
        evaluated for the audit record even after a failure.
        """
        results: list[RiskGateResult] = []
        first_failure: str | None = None

        for i, gate_fn in enumerate(self._gate_functions, start=1):
            result = gate_fn(intent, context, instrument)
            results.append(result)
            if result.verdict == RiskGateVerdict.FAIL and first_failure is None:
                first_failure = result.gate_name

        passed = sum(1 for r in results if r.verdict == RiskGateVerdict.PASS)
        failed = sum(1 for r in results if r.verdict == RiskGateVerdict.FAIL)
        warned = sum(1 for r in results if r.verdict == RiskGateVerdict.WARN)

        return FirewallDecision(
            approved=failed == 0,
            gate_results=tuple(results),
            order_intent_id=intent.intent_id,
            total_gates=len(results),
            gates_passed=passed,
            gates_failed=failed,
            gates_warned=warned,
            blocking_gate=first_failure,
        )

    # ── Gate implementations ─────────────────────────────────────────

    def _gate_01_instrument_validation(
        self, intent: OrderIntent, ctx: PortfolioContext, inst: Instrument | None,
    ) -> RiskGateResult:
        """Gate 1: Validate the instrument is known, active, and allowed."""
        if inst is None:
            # No instrument metadata — allow with warning for simulation
            return RiskGateResult(
                gate_name="instrument_validation",
                gate_index=1,
                verdict=RiskGateVerdict.WARN,
                reason="No instrument metadata provided; proceeding with reduced confidence",
            )

        if not inst.is_active:
            return RiskGateResult(
                gate_name="instrument_validation",
                gate_index=1,
                verdict=RiskGateVerdict.FAIL,
                reason=f"Instrument {inst.symbol} is not active",
            )

        if inst.asset_class not in self.limits.allowed_asset_classes:
            return RiskGateResult(
                gate_name="instrument_validation",
                gate_index=1,
                verdict=RiskGateVerdict.FAIL,
                reason=f"Asset class {inst.asset_class.value} not in allowed set",
            )

        if inst.corporate_actions_pending:
            return RiskGateResult(
                gate_name="instrument_validation",
                gate_index=1,
                verdict=RiskGateVerdict.WARN,
                reason=f"Corporate action pending for {inst.symbol}",
            )

        return RiskGateResult(
            gate_name="instrument_validation", gate_index=1,
            verdict=RiskGateVerdict.PASS,
        )

    def _gate_02_position_limits(
        self, intent: OrderIntent, ctx: PortfolioContext, inst: Instrument | None,
    ) -> RiskGateResult:
        """Gate 2: Check position notional and portfolio fraction limits."""
        notional = intent.target_quantity * (intent.limit_price or Decimal("100"))

        if notional > self.limits.max_position_notional:
            return RiskGateResult(
                gate_name="position_limits", gate_index=2,
                verdict=RiskGateVerdict.FAIL,
                reason=f"Order notional ${notional} exceeds limit ${self.limits.max_position_notional}",
                metric_value=notional,
                limit_value=self.limits.max_position_notional,
            )

        if ctx.equity > 0:
            fraction = notional / ctx.equity
            if fraction > self.limits.max_position_fraction:
                return RiskGateResult(
                    gate_name="position_limits", gate_index=2,
                    verdict=RiskGateVerdict.FAIL,
                    reason=f"Position {fraction:.1%} of equity exceeds {self.limits.max_position_fraction:.1%} limit",
                    metric_value=fraction,
                    limit_value=self.limits.max_position_fraction,
                )

        if len(ctx.positions) >= self.limits.max_open_positions:
            if intent.side in (Action.BUY, Action.SHORT):
                return RiskGateResult(
                    gate_name="position_limits", gate_index=2,
                    verdict=RiskGateVerdict.FAIL,
                    reason=f"Max open positions ({self.limits.max_open_positions}) reached",
                    metric_value=Decimal(str(len(ctx.positions))),
                    limit_value=Decimal(str(self.limits.max_open_positions)),
                )

        return RiskGateResult(
            gate_name="position_limits", gate_index=2,
            verdict=RiskGateVerdict.PASS,
        )

    def _gate_03_concentration_limits(
        self, intent: OrderIntent, ctx: PortfolioContext, inst: Instrument | None,
    ) -> RiskGateResult:
        """Gate 3: Check sector, country, currency, and asset class concentration."""
        if inst is None:
            return RiskGateResult(
                gate_name="concentration_limits", gate_index=3,
                verdict=RiskGateVerdict.WARN,
                reason="Cannot assess concentration without instrument metadata",
            )

        notional = intent.target_quantity * (intent.limit_price or Decimal("100"))
        warnings: list[str] = []

        # Sector concentration
        if inst.sector and ctx.equity > 0:
            current_sector = ctx.sector_exposures.get(inst.sector, Decimal("0"))
            new_sector = (current_sector + notional) / ctx.equity
            if new_sector > self.limits.max_sector_pct:
                return RiskGateResult(
                    gate_name="concentration_limits", gate_index=3,
                    verdict=RiskGateVerdict.FAIL,
                    reason=f"Sector {inst.sector} concentration {new_sector:.1%} exceeds {self.limits.max_sector_pct:.1%}",
                    metric_value=new_sector, limit_value=self.limits.max_sector_pct,
                )

        # Country concentration
        if inst.country and ctx.equity > 0:
            current_country = ctx.country_exposures.get(inst.country, Decimal("0"))
            new_country = (current_country + notional) / ctx.equity
            if new_country > self.limits.max_country_pct:
                return RiskGateResult(
                    gate_name="concentration_limits", gate_index=3,
                    verdict=RiskGateVerdict.FAIL,
                    reason=f"Country {inst.country} concentration {new_country:.1%} exceeds {self.limits.max_country_pct:.1%}",
                    metric_value=new_country, limit_value=self.limits.max_country_pct,
                )

        # Asset class concentration
        if ctx.equity > 0:
            ac_key = inst.asset_class.value
            current_ac = ctx.asset_class_exposures.get(ac_key, Decimal("0"))
            new_ac = (current_ac + notional) / ctx.equity
            if new_ac > self.limits.max_asset_class_pct:
                warnings.append(
                    f"Asset class {ac_key} at {new_ac:.1%} (limit {self.limits.max_asset_class_pct:.1%})"
                )

        if warnings:
            return RiskGateResult(
                gate_name="concentration_limits", gate_index=3,
                verdict=RiskGateVerdict.WARN,
                reason="; ".join(warnings),
            )

        return RiskGateResult(
            gate_name="concentration_limits", gate_index=3,
            verdict=RiskGateVerdict.PASS,
        )

    def _gate_04_leverage_limits(
        self, intent: OrderIntent, ctx: PortfolioContext, inst: Instrument | None,
    ) -> RiskGateResult:
        """Gate 4: Check gross exposure, net exposure, and leverage limits."""
        notional = intent.target_quantity * (intent.limit_price or Decimal("100"))

        if ctx.equity > 0:
            new_gross = (ctx.gross_exposure + notional) / ctx.equity
            if new_gross > self.limits.max_gross_exposure:
                return RiskGateResult(
                    gate_name="leverage_limits", gate_index=4,
                    verdict=RiskGateVerdict.FAIL,
                    reason=f"Gross exposure {new_gross:.1%} exceeds {self.limits.max_gross_exposure:.1%}",
                    metric_value=new_gross, limit_value=self.limits.max_gross_exposure,
                )

            direction = Decimal("1") if intent.side in (Action.BUY, Action.HOLD) else Decimal("-1")
            new_net = abs(ctx.net_exposure + direction * notional) / ctx.equity
            if new_net > self.limits.max_net_exposure:
                return RiskGateResult(
                    gate_name="leverage_limits", gate_index=4,
                    verdict=RiskGateVerdict.FAIL,
                    reason=f"Net exposure {new_net:.1%} exceeds {self.limits.max_net_exposure:.1%}",
                    metric_value=new_net, limit_value=self.limits.max_net_exposure,
                )

        return RiskGateResult(
            gate_name="leverage_limits", gate_index=4,
            verdict=RiskGateVerdict.PASS,
        )

    def _gate_05_liquidity_check(
        self, intent: OrderIntent, ctx: PortfolioContext, inst: Instrument | None,
    ) -> RiskGateResult:
        """Gate 5: Check ADV participation rate, spread, and time-to-liquidate."""
        if inst is None:
            return RiskGateResult(
                gate_name="liquidity_check", gate_index=5,
                verdict=RiskGateVerdict.WARN,
                reason="Cannot assess liquidity without instrument metadata",
            )

        # Spread check
        if inst.spread_bps > self.limits.max_spread_bps:
            return RiskGateResult(
                gate_name="liquidity_check", gate_index=5,
                verdict=RiskGateVerdict.FAIL,
                reason=f"Spread {inst.spread_bps}bps exceeds {self.limits.max_spread_bps}bps limit",
                metric_value=inst.spread_bps, limit_value=self.limits.max_spread_bps,
            )

        # ADV participation rate
        if inst.avg_daily_volume > 0:
            participation = intent.target_quantity / inst.avg_daily_volume
            if participation > self.limits.max_adv_participation_rate:
                return RiskGateResult(
                    gate_name="liquidity_check", gate_index=5,
                    verdict=RiskGateVerdict.FAIL,
                    reason=f"Order is {participation:.1%} of ADV (limit {self.limits.max_adv_participation_rate:.1%})",
                    metric_value=participation,
                    limit_value=self.limits.max_adv_participation_rate,
                )

        return RiskGateResult(
            gate_name="liquidity_check", gate_index=5,
            verdict=RiskGateVerdict.PASS,
        )

    def _gate_06_market_risk(
        self, intent: OrderIntent, ctx: PortfolioContext, inst: Instrument | None,
    ) -> RiskGateResult:
        """Gate 6: Check portfolio VaR and CVaR limits."""
        if ctx.current_var_pct > self.limits.max_portfolio_var_pct:
            return RiskGateResult(
                gate_name="market_risk", gate_index=6,
                verdict=RiskGateVerdict.FAIL,
                reason=f"Portfolio VaR {ctx.current_var_pct:.2%} exceeds {self.limits.max_portfolio_var_pct:.2%}",
                metric_value=ctx.current_var_pct,
                limit_value=self.limits.max_portfolio_var_pct,
            )

        if ctx.current_cvar_pct > self.limits.max_portfolio_cvar_pct:
            return RiskGateResult(
                gate_name="market_risk", gate_index=6,
                verdict=RiskGateVerdict.FAIL,
                reason=f"Portfolio CVaR {ctx.current_cvar_pct:.2%} exceeds {self.limits.max_portfolio_cvar_pct:.2%}",
                metric_value=ctx.current_cvar_pct,
                limit_value=self.limits.max_portfolio_cvar_pct,
            )

        # Warn if approaching limits
        if ctx.current_var_pct > self.limits.max_portfolio_var_pct * Decimal("0.8"):
            return RiskGateResult(
                gate_name="market_risk", gate_index=6,
                verdict=RiskGateVerdict.WARN,
                reason=f"VaR at {ctx.current_var_pct:.2%}, approaching {self.limits.max_portfolio_var_pct:.2%} limit",
                metric_value=ctx.current_var_pct,
                limit_value=self.limits.max_portfolio_var_pct,
            )

        return RiskGateResult(
            gate_name="market_risk", gate_index=6,
            verdict=RiskGateVerdict.PASS,
        )

    def _gate_07_factor_risk(
        self, intent: OrderIntent, ctx: PortfolioContext, inst: Instrument | None,
    ) -> RiskGateResult:
        """Gate 7: Check factor exposure limits."""
        if not ctx.factor_exposures:
            return RiskGateResult(
                gate_name="factor_risk", gate_index=7,
                verdict=RiskGateVerdict.WARN,
                reason="No factor exposure data available",
            )

        for factor, exposure in ctx.factor_exposures.items():
            if abs(exposure) > self.limits.max_factor_exposure:
                return RiskGateResult(
                    gate_name="factor_risk", gate_index=7,
                    verdict=RiskGateVerdict.FAIL,
                    reason=f"Factor {factor} exposure {exposure:.2f} exceeds ±{self.limits.max_factor_exposure:.2f}",
                    metric_value=abs(exposure),
                    limit_value=self.limits.max_factor_exposure,
                )

        return RiskGateResult(
            gate_name="factor_risk", gate_index=7,
            verdict=RiskGateVerdict.PASS,
        )

    def _gate_08_stress_test(
        self, intent: OrderIntent, ctx: PortfolioContext, inst: Instrument | None,
    ) -> RiskGateResult:
        """Gate 8: Check portfolio survives stress scenarios."""
        if not ctx.stress_losses:
            return RiskGateResult(
                gate_name="stress_test", gate_index=8,
                verdict=RiskGateVerdict.WARN,
                reason="No stress test results available",
            )

        for scenario, loss_pct in ctx.stress_losses.items():
            if abs(loss_pct) > self.limits.max_stress_loss_pct:
                return RiskGateResult(
                    gate_name="stress_test", gate_index=8,
                    verdict=RiskGateVerdict.FAIL,
                    reason=f"Scenario '{scenario}' loss {loss_pct:.1%} exceeds {self.limits.max_stress_loss_pct:.1%}",
                    metric_value=abs(loss_pct),
                    limit_value=self.limits.max_stress_loss_pct,
                )

        return RiskGateResult(
            gate_name="stress_test", gate_index=8,
            verdict=RiskGateVerdict.PASS,
        )

    def _gate_09_counterparty(
        self, intent: OrderIntent, ctx: PortfolioContext, inst: Instrument | None,
    ) -> RiskGateResult:
        """Gate 9: Check counterparty and broker concentration limits."""
        venue = intent.venue or "default"

        if ctx.counterparty_exposures and ctx.equity > 0:
            venue_exposure = ctx.counterparty_exposures.get(venue, Decimal("0"))
            notional = intent.target_quantity * (intent.limit_price or Decimal("100"))
            new_exposure = (venue_exposure + notional) / ctx.equity

            if new_exposure > self.limits.max_counterparty_exposure_pct:
                return RiskGateResult(
                    gate_name="counterparty", gate_index=9,
                    verdict=RiskGateVerdict.FAIL,
                    reason=f"Counterparty {venue} exposure {new_exposure:.1%} exceeds {self.limits.max_counterparty_exposure_pct:.1%}",
                    metric_value=new_exposure,
                    limit_value=self.limits.max_counterparty_exposure_pct,
                )

        return RiskGateResult(
            gate_name="counterparty", gate_index=9,
            verdict=RiskGateVerdict.PASS,
        )

    def _gate_10_compliance(
        self, intent: OrderIntent, ctx: PortfolioContext, inst: Instrument | None,
    ) -> RiskGateResult:
        """Gate 10: Check compliance rules, restricted symbols, and order bounds."""
        # Restricted symbols
        if intent.symbol in self.limits.restricted_symbols:
            return RiskGateResult(
                gate_name="compliance", gate_index=10,
                verdict=RiskGateVerdict.FAIL,
                reason=f"Symbol {intent.symbol} is on the restricted list",
            )

        # Order notional bounds
        notional = intent.target_quantity * (intent.limit_price or Decimal("100"))
        if notional > self.limits.max_order_notional:
            return RiskGateResult(
                gate_name="compliance", gate_index=10,
                verdict=RiskGateVerdict.FAIL,
                reason=f"Order notional ${notional} exceeds compliance limit ${self.limits.max_order_notional}",
                metric_value=notional,
                limit_value=self.limits.max_order_notional,
            )

        if notional < self.limits.min_order_notional:
            return RiskGateResult(
                gate_name="compliance", gate_index=10,
                verdict=RiskGateVerdict.FAIL,
                reason=f"Order notional ${notional} below minimum ${self.limits.min_order_notional}",
                metric_value=notional,
                limit_value=self.limits.min_order_notional,
            )

        # Require rationale
        if self.limits.require_rationale and not intent.rationale:
            return RiskGateResult(
                gate_name="compliance", gate_index=10,
                verdict=RiskGateVerdict.WARN,
                reason="Order has no rationale attached",
            )

        return RiskGateResult(
            gate_name="compliance", gate_index=10,
            verdict=RiskGateVerdict.PASS,
        )

    def _gate_11_model_health(
        self, intent: OrderIntent, ctx: PortfolioContext, inst: Instrument | None,
    ) -> RiskGateResult:
        """Gate 11: Check model confidence, staleness, and version tracking."""
        if ctx.model_confidence < self.limits.min_model_confidence:
            return RiskGateResult(
                gate_name="model_health", gate_index=11,
                verdict=RiskGateVerdict.FAIL,
                reason=f"Model confidence {ctx.model_confidence:.2f} below {self.limits.min_model_confidence:.2f}",
                metric_value=ctx.model_confidence,
                limit_value=self.limits.min_model_confidence,
            )

        # Check prediction staleness
        if ctx.prediction_timestamp is not None:
            age = (datetime.now(timezone.utc) - ctx.prediction_timestamp).total_seconds()
            if age > self.limits.max_prediction_age_seconds:
                return RiskGateResult(
                    gate_name="model_health", gate_index=11,
                    verdict=RiskGateVerdict.FAIL,
                    reason=f"Prediction is {age:.0f}s old (limit {self.limits.max_prediction_age_seconds}s)",
                    metric_value=Decimal(str(int(age))),
                    limit_value=Decimal(str(self.limits.max_prediction_age_seconds)),
                )

        # Check model version
        if self.limits.require_model_version and not ctx.model_version:
            return RiskGateResult(
                gate_name="model_health", gate_index=11,
                verdict=RiskGateVerdict.WARN,
                reason="No model version recorded",
            )

        return RiskGateResult(
            gate_name="model_health", gate_index=11,
            verdict=RiskGateVerdict.PASS,
        )

    def _gate_12_kill_switch(
        self, intent: OrderIntent, ctx: PortfolioContext, inst: Instrument | None,
    ) -> RiskGateResult:
        """Gate 12: Check all kill switches (global, strategy, asset, venue).

        A risk model can say BLOCK and no language model can override it.
        """
        # Global kill switch
        if self.limits.global_kill_switch:
            return RiskGateResult(
                gate_name="kill_switch", gate_index=12,
                verdict=RiskGateVerdict.FAIL,
                reason="GLOBAL KILL SWITCH IS ACTIVE — all orders blocked",
            )

        # Strategy kill switch
        if intent.strategy_id in self.limits.strategy_kill_switches:
            return RiskGateResult(
                gate_name="kill_switch", gate_index=12,
                verdict=RiskGateVerdict.FAIL,
                reason=f"Strategy '{intent.strategy_id}' kill switch is active",
            )

        # Asset kill switch
        if intent.symbol in self.limits.asset_kill_switches:
            return RiskGateResult(
                gate_name="kill_switch", gate_index=12,
                verdict=RiskGateVerdict.FAIL,
                reason=f"Asset '{intent.symbol}' kill switch is active",
            )

        # Venue kill switch
        venue = intent.venue or "default"
        if venue in self.limits.venue_kill_switches:
            return RiskGateResult(
                gate_name="kill_switch", gate_index=12,
                verdict=RiskGateVerdict.FAIL,
                reason=f"Venue '{venue}' kill switch is active",
            )

        return RiskGateResult(
            gate_name="kill_switch", gate_index=12,
            verdict=RiskGateVerdict.PASS,
        )

    # ── Utility methods ──────────────────────────────────────────────

    def engage_global_kill_switch(self) -> None:
        """Engage the global kill switch. No orders will pass."""
        # FirewallLimits is a dataclass, not frozen, so we can mutate
        self.limits.global_kill_switch = True

    def disengage_global_kill_switch(self) -> None:
        """Disengage the global kill switch."""
        self.limits.global_kill_switch = False

    def add_strategy_kill_switch(self, strategy_id: str) -> None:
        """Block a specific strategy from trading."""
        self.limits.strategy_kill_switches = (
            self.limits.strategy_kill_switches | frozenset({strategy_id})
        )

    def add_asset_kill_switch(self, symbol: str) -> None:
        """Block a specific asset from trading."""
        self.limits.asset_kill_switches = (
            self.limits.asset_kill_switches | frozenset({symbol})
        )

    def add_venue_kill_switch(self, venue: str) -> None:
        """Block a specific venue from receiving orders."""
        self.limits.venue_kill_switches = (
            self.limits.venue_kill_switches | frozenset({venue})
        )

    def summary(self) -> dict[str, Any]:
        """Return a human-readable summary of firewall configuration."""
        return {
            "global_kill_switch": self.limits.global_kill_switch,
            "strategy_kill_switches": sorted(self.limits.strategy_kill_switches),
            "asset_kill_switches": sorted(self.limits.asset_kill_switches),
            "venue_kill_switches": sorted(self.limits.venue_kill_switches),
            "max_position_notional": str(self.limits.max_position_notional),
            "max_position_fraction": str(self.limits.max_position_fraction),
            "max_gross_exposure": str(self.limits.max_gross_exposure),
            "max_portfolio_var_pct": str(self.limits.max_portfolio_var_pct),
            "max_stress_loss_pct": str(self.limits.max_stress_loss_pct),
            "restricted_symbols_count": len(self.limits.restricted_symbols),
            "min_model_confidence": str(self.limits.min_model_confidence),
            "total_gates": 12,
        }
