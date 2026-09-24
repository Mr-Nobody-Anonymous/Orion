"""ORION Stress Testing Engine.

Maintains a permanent scenario library covering historical crises and
synthetic macro scenarios. Calculates portfolio loss, factor contribution,
margin impact, and recovery estimates under each scenario.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Mapping, Sequence


@dataclass(frozen=True, slots=True)
class StressScenario:
    """A historical or synthetic stress scenario."""

    scenario_id: str
    name: str
    description: str
    category: str  # historical, synthetic, regulatory
    shocks: Mapping[str, Decimal]  # factor/asset_class -> shock magnitude
    probability_estimate: Decimal = Decimal("0.05")  # estimated probability


@dataclass(frozen=True, slots=True)
class StressResult:
    """Result of applying a stress scenario to a portfolio."""

    scenario_id: str
    scenario_name: str
    portfolio_value: Decimal
    stressed_value: Decimal
    dollar_loss: Decimal
    percentage_loss: Decimal
    factor_contributions: Mapping[str, Decimal]
    margin_breach: bool
    liquidity_impact_pct: Decimal
    recovery_time_estimate_days: int


class ScenarioLibrary:
    """Permanent library of historical and synthetic crisis scenarios.

    Based on actual historical market events with calibrated factor shocks.
    """

    SCENARIOS: dict[str, StressScenario] = {
        "2008_financial_crisis": StressScenario(
            scenario_id="2008_financial_crisis",
            name="2008 Global Financial Crisis",
            description="Lehman collapse, credit freeze, equity crash, flight to treasuries",
            category="historical",
            shocks={
                "equity": Decimal("-0.30"), "high_yield": Decimal("-0.15"),
                "treasury_10y": Decimal("0.08"), "usd": Decimal("0.08"),
                "oil": Decimal("-0.25"), "vix": Decimal("1.00"),
                "credit_spread": Decimal("0.30"), "liquidity": Decimal("-0.50"),
                "crypto": Decimal("-0.45"),
            },
        ),
        "covid_2020": StressScenario(
            scenario_id="covid_2020",
            name="2020 COVID Crash",
            description="Rapid systemic shock, liquidity evaporation, global lockdown",
            category="historical",
            shocks={
                "equity": Decimal("-0.34"), "high_yield": Decimal("-0.10"),
                "treasury_10y": Decimal("0.05"), "oil": Decimal("-0.65"),
                "vix": Decimal("2.00"), "credit_spread": Decimal("0.20"),
                "liquidity": Decimal("-0.40"), "crypto": Decimal("-0.50"),
            },
        ),
        "rate_shock_200bp": StressScenario(
            scenario_id="rate_shock_200bp",
            name="2022-style Rate Shock (+200bp)",
            description="Rapid tightening, multiple compression, bond/equity simultaneous decline",
            category="historical",
            shocks={
                "equity": Decimal("-0.22"), "bond": Decimal("-0.16"),
                "treasury_10y": Decimal("-0.12"), "usd": Decimal("0.08"),
                "vix": Decimal("0.40"), "credit_spread": Decimal("0.10"),
                "crypto": Decimal("-0.65"), "duration": Decimal("-0.08"),
            },
        ),
        "dot_com_crash": StressScenario(
            scenario_id="dot_com_crash",
            name="Dot-Com Crash (2000-2002)",
            description="Technology bubble burst, 78% NASDAQ decline",
            category="historical",
            shocks={
                "equity": Decimal("-0.25"), "technology": Decimal("-0.50"),
                "growth": Decimal("-0.40"), "value": Decimal("-0.05"),
                "treasury_10y": Decimal("0.04"), "vix": Decimal("0.60"),
            },
        ),
        "black_monday_1987": StressScenario(
            scenario_id="black_monday_1987",
            name="Black Monday 1987",
            description="22% single-day equity crash, program trading cascade",
            category="historical",
            shocks={
                "equity": Decimal("-0.22"), "vix": Decimal("1.50"),
                "liquidity": Decimal("-0.60"), "treasury_10y": Decimal("0.03"),
            },
        ),
        "flash_crash": StressScenario(
            scenario_id="flash_crash",
            name="Flash Crash (2010)",
            description="Sudden intraday liquidity evaporation and market-order cascade",
            category="historical",
            shocks={
                "equity": Decimal("-0.09"), "vix": Decimal("0.80"),
                "liquidity": Decimal("-0.70"), "crypto": Decimal("-0.20"),
            },
        ),
        "oil_shock": StressScenario(
            scenario_id="oil_shock",
            name="Oil Price Shock",
            description="60% oil price decline with energy sector contagion",
            category="synthetic",
            shocks={
                "oil": Decimal("-0.60"), "energy": Decimal("-0.40"),
                "equity": Decimal("-0.10"), "high_yield": Decimal("-0.08"),
                "credit_spread": Decimal("0.15"),
            },
        ),
        "credit_crisis": StressScenario(
            scenario_id="credit_crisis",
            name="Credit Spread Blowout",
            description="Investment-grade and high-yield spread widening",
            category="synthetic",
            shocks={
                "high_yield": Decimal("-0.20"), "investment_grade": Decimal("-0.08"),
                "credit_spread": Decimal("0.35"), "equity": Decimal("-0.15"),
                "liquidity": Decimal("-0.30"),
            },
        ),
        "currency_shock": StressScenario(
            scenario_id="currency_shock",
            name="USD Strength Shock",
            description="Rapid USD appreciation, EM currency crisis",
            category="synthetic",
            shocks={
                "usd": Decimal("0.15"), "em_equity": Decimal("-0.25"),
                "em_bond": Decimal("-0.15"), "commodities": Decimal("-0.12"),
                "equity": Decimal("-0.08"),
            },
        ),
        "liquidity_freeze": StressScenario(
            scenario_id="liquidity_freeze",
            name="Liquidity Freeze",
            description="Complete market-wide liquidity evaporation",
            category="synthetic",
            shocks={
                "liquidity": Decimal("-0.80"), "equity": Decimal("-0.20"),
                "high_yield": Decimal("-0.25"), "crypto": Decimal("-0.40"),
                "vix": Decimal("1.20"), "credit_spread": Decimal("0.25"),
            },
        ),
        "crypto_collapse": StressScenario(
            scenario_id="crypto_collapse",
            name="Crypto Market Collapse",
            description="Systemic crypto exchange failure and stablecoin depeg",
            category="synthetic",
            shocks={
                "crypto": Decimal("-0.70"), "equity": Decimal("-0.05"),
                "liquidity": Decimal("-0.20"),
            },
        ),
        "regional_bank_crisis": StressScenario(
            scenario_id="regional_bank_crisis",
            name="Regional Bank Crisis (SVB-style)",
            description="Rapid deposit flight, duration mismatch, contagion",
            category="historical",
            shocks={
                "financials": Decimal("-0.30"), "equity": Decimal("-0.08"),
                "treasury_10y": Decimal("0.04"), "credit_spread": Decimal("0.12"),
                "liquidity": Decimal("-0.25"),
            },
        ),
    }

    @classmethod
    def get_scenario(cls, scenario_id: str) -> StressScenario:
        if scenario_id not in cls.SCENARIOS:
            raise KeyError(
                f"Unknown scenario: '{scenario_id}'. "
                f"Available: {sorted(cls.SCENARIOS.keys())}"
            )
        return cls.SCENARIOS[scenario_id]

    @classmethod
    def list_scenarios(cls) -> list[str]:
        return sorted(cls.SCENARIOS.keys())

    @classmethod
    def get_all(cls) -> dict[str, StressScenario]:
        return dict(cls.SCENARIOS)


class StressTestEngine:
    """Portfolio stress testing engine.

    Applies scenario shocks to portfolio positions and calculates
    the resulting losses, factor contributions, and margin impacts.
    """

    def __init__(self, library: ScenarioLibrary | None = None) -> None:
        self.library = library or ScenarioLibrary()

    def run_scenario(
        self,
        portfolio_value: Decimal,
        asset_allocations: Mapping[str, Decimal],
        scenario_id: str,
    ) -> StressResult:
        """Apply a single stress scenario to the portfolio.

        Args:
            portfolio_value: Total portfolio value.
            asset_allocations: Mapping of factor/asset_class to portfolio weight.
            scenario_id: ID of scenario from the library.

        Returns:
            StressResult with loss estimates and factor contributions.
        """
        scenario = self.library.get_scenario(scenario_id)
        return self._apply_scenario(portfolio_value, asset_allocations, scenario)

    def run_all_scenarios(
        self,
        portfolio_value: Decimal,
        asset_allocations: Mapping[str, Decimal],
    ) -> list[StressResult]:
        """Run all scenarios in the library."""
        results = []
        for scenario_id in self.library.list_scenarios():
            scenario = self.library.get_scenario(scenario_id)
            result = self._apply_scenario(portfolio_value, asset_allocations, scenario)
            results.append(result)
        return sorted(results, key=lambda r: r.percentage_loss, reverse=True)

    def generate_synthetic_scenario(
        self,
        name: str,
        equity_shock: Decimal = Decimal("-0.15"),
        rate_shock_bp: int = 100,
        credit_shock: Decimal = Decimal("0.10"),
        fx_shock: Decimal = Decimal("0.05"),
        oil_shock: Decimal = Decimal("-0.20"),
        liquidity_shock: Decimal = Decimal("-0.30"),
        vix_shock: Decimal = Decimal("0.50"),
    ) -> StressScenario:
        """Generate a custom synthetic scenario."""
        return StressScenario(
            scenario_id=f"synthetic_{name.lower().replace(' ', '_')}",
            name=name,
            description=f"Custom scenario: equity {equity_shock}, rates +{rate_shock_bp}bp",
            category="synthetic",
            shocks={
                "equity": equity_shock,
                "bond": Decimal(str(-rate_shock_bp / 10000)),
                "credit_spread": credit_shock,
                "usd": fx_shock,
                "oil": oil_shock,
                "liquidity": liquidity_shock,
                "vix": vix_shock,
            },
        )

    def _apply_scenario(
        self,
        portfolio_value: Decimal,
        allocations: Mapping[str, Decimal],
        scenario: StressScenario,
    ) -> StressResult:
        """Apply a scenario's shocks to portfolio allocations."""
        total_shock = Decimal("0")
        factor_contrib: dict[str, Decimal] = {}

        for factor, weight in allocations.items():
            factor_lower = factor.lower()
            # Find matching shock
            shock = scenario.shocks.get(factor_lower, Decimal("0"))
            contribution = weight * shock
            total_shock += contribution
            if shock != 0:
                factor_contrib[factor] = contribution

        stressed_value = max(Decimal("0"), portfolio_value * (Decimal("1") + total_shock))
        dollar_loss = portfolio_value - stressed_value
        pct_loss = (dollar_loss / portfolio_value * 100) if portfolio_value > 0 else Decimal("0")

        # Estimate liquidity impact
        liq_shock = abs(scenario.shocks.get("liquidity", Decimal("0")))
        liq_impact = liq_shock * Decimal("100")

        # Margin breach if loss > 30%
        margin_breach = pct_loss > Decimal("30")

        # Recovery estimate (rough heuristic based on severity)
        recovery_days = int(min(500, max(5, float(pct_loss) * 10)))

        q = Decimal("0.01")
        return StressResult(
            scenario_id=scenario.scenario_id,
            scenario_name=scenario.name,
            portfolio_value=portfolio_value.quantize(q),
            stressed_value=stressed_value.quantize(q),
            dollar_loss=dollar_loss.quantize(q),
            percentage_loss=pct_loss.quantize(q),
            factor_contributions=factor_contrib,
            margin_breach=margin_breach,
            liquidity_impact_pct=liq_impact.quantize(q),
            recovery_time_estimate_days=recovery_days,
        )
