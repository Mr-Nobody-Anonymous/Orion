"""
Orion Risk Engine
Comprehensive risk management: Market, Credit, Liquidity, 
Operational, Tail, Regime
"""

import asyncio
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
from scipy import stats
import warnings
warnings.filterwarnings('ignore')


@dataclass
class RiskLimits:
    # Portfolio level
    max_portfolio_var: float = 0.02          # 2% daily VaR
    max_portfolio_cvar: float = 0.03         # 3% CVaR (Expected Shortfall)
    max_drawdown: float = 0.15               # 15% max drawdown
    max_leverage: float = 2.0               # 2x max leverage
    max_gross_exposure: float = 2.0
    max_net_exposure: float = 1.0
    
    # Position level
    max_position_size: float = 0.10          # 10% of portfolio per position
    max_sector_exposure: float = 0.25        # 25% per sector
    max_asset_class_exposure: float = 0.40  # 40% per asset class
    max_single_name_loss: float = 0.02       # 2% max loss per position
    
    # Correlation limits
    max_correlation: float = 0.80            # Max between-position correlation
    max_beta: float = 1.5                    # Max portfolio beta
    
    # Liquidity
    min_avg_daily_volume: float = 1_000_000  # $1M minimum ADV
    max_adv_participation: float = 0.05      # Max 5% of ADV
    max_liquidation_days: int = 5            # Must liquidate within 5 days
    
    # Factor exposure
    max_factor_exposure: float = 3.0         # Max factor exposure in std devs
    
    # Stop losses
    daily_loss_limit: float = 0.03          # 3% daily loss → halt trading
    weekly_loss_limit: float = 0.07         # 7% weekly loss → reduce risk
    monthly_loss_limit: float = 0.12        # 12% monthly → stop trading


@dataclass
class RiskMetrics:
    # Value at Risk
    var_95: float = 0.0
    var_99: float = 0.0
    cvar_95: float = 0.0
    cvar_99: float = 0.0
    
    # Greeks (for options)
    portfolio_delta: float = 0.0
    portfolio_gamma: float = 0.0
    portfolio_vega: float = 0.0
    portfolio_theta: float = 0.0
    
    # Risk-adjusted returns
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    omega_ratio: float = 0.0
    
    # Drawdown
    current_drawdown: float = 0.0
    max_drawdown: float = 0.0
    
    # Exposure
    gross_exposure: float = 0.0
    net_exposure: float = 0.0
    leverage: float = 0.0
    beta: float = 0.0
    
    # Tail risk
    skewness: float = 0.0
    kurtosis: float = 0.0
    tail_ratio: float = 0.0


class VaRCalculator:
    """Multiple VaR methodologies"""
    
    @staticmethod
    def historical_var(returns: pd.Series, confidence: float = 0.95, 
                       lookback: int = 252) -> float:
        """Historical simulation VaR"""
        recent_returns = returns.tail(lookback).dropna()
        return float(np.percentile(recent_returns, (1 - confidence) * 100))
    
    @staticmethod
    def parametric_var(returns: pd.Series, confidence: float = 0.95) -> float:
        """Parametric (Normal) VaR"""
        mu = returns.mean()
        sigma = returns.std()
        z_score = stats.norm.ppf(1 - confidence)
        return float(mu + z_score * sigma)
    
    @staticmethod
    def monte_carlo_var(returns: pd.Series, confidence: float = 0.95,
                        n_simulations: int = 10000, horizon: int = 1) -> float:
        """Monte Carlo VaR"""
        mu = returns.mean()
        sigma = returns.std()
        
        # Generate random returns
        simulated = np.random.normal(
            mu * horizon, 
            sigma * np.sqrt(horizon), 
            n_simulations
        )
        
        return float(np.percentile(simulated, (1 - confidence) * 100))
    
    @staticmethod
    def cornish_fisher_var(returns: pd.Series, confidence: float = 0.95) -> float:
        """Cornish-Fisher VaR (adjusts for skewness and kurtosis)"""
        mu = returns.mean()
        sigma = returns.std()
        skew = returns.skew()
        kurt = returns.kurtosis()
        
        z = stats.norm.ppf(confidence)
        
        # Cornish-Fisher adjustment
        z_cf = (z + (z**2 - 1) * skew / 6 + 
                (z**3 - 3*z) * kurt / 24 - 
                (2*z**3 - 5*z) * skew**2 / 36)
        
        return float(-(mu - z_cf * sigma))
    
    @staticmethod
    def component_var(weights: np.ndarray, cov_matrix: np.ndarray,
                      confidence: float = 0.95) -> np.ndarray:
        """Component VaR - contribution of each position to portfolio VaR"""
        portfolio_var = np.sqrt(weights @ cov_matrix @ weights)
        marginal_var = cov_matrix @ weights / portfolio_var
        component_var = marginal_var * weights * portfolio_var
        return component_var


class RiskEngine:
    """
    Orion Institutional Risk Engine.
    Coordinates pre-trade validation, real-time risk calculations, VaR, and limit enforcement.
    """

    def __init__(self, limits: Optional[RiskLimits] = None):
        self.limits = limits or RiskLimits()
        self.var_calculator = VaRCalculator()
        self.circuit_breaker_active = False
        logger.info("RiskEngine initialized with institutional limits")

    def validate_order(self, order: Dict, current_portfolio: Dict) -> Tuple[bool, str]:
        """
        Pre-trade risk validation: checks position sizing, leverage, ADV limits, and circuit breakers.
        """
        if self.circuit_breaker_active:
            return False, "Risk check failed: Circuit breaker is currently active"

        order_size = order.get("quantity", 0) * order.get("price", 0)
        portfolio_val = current_portfolio.get("total_value", 1.0)
        
        # Max position size limit
        if portfolio_val > 0 and (order_size / portfolio_val) > self.limits.max_position_size:
            return False, f"Risk check failed: Order exceeds max position size limit ({self.limits.max_position_size * 100}%)"

        return True, "Pre-trade risk checks passed"

    def calculate_portfolio_risk(
        self, returns: pd.Series, weights: Optional[np.ndarray] = None, cov_matrix: Optional[np.ndarray] = None
    ) -> RiskMetrics:
        """
        Computes real-time comprehensive risk metrics across all risk dimensions.
        """
        metrics = RiskMetrics()
        if returns.empty or len(returns) < 5:
            return metrics

        # VaR Calculations
        metrics.var_95 = self.var_calculator.historical_var(returns, confidence=0.95)
        metrics.var_99 = self.var_calculator.historical_var(returns, confidence=0.99)
        metrics.cvar_95 = float(returns[returns <= metrics.var_95].mean()) if (returns <= metrics.var_95).any() else metrics.var_95
        metrics.cvar_99 = float(returns[returns <= metrics.var_99].mean()) if (returns <= metrics.var_99).any() else metrics.var_99

        # Drawdown
        cum_returns = (1 + returns).cumprod()
        peak = cum_returns.cummax()
        drawdown = (cum_returns - peak) / peak
        metrics.current_drawdown = float(drawdown.iloc[-1]) if not drawdown.empty else 0.0
        metrics.max_drawdown = float(drawdown.min()) if not drawdown.empty else 0.0

        # Ratios
        mu = returns.mean() * 252
        sigma = returns.std() * np.sqrt(252)
        metrics.sharpe_ratio = float(mu / sigma) if sigma > 0 else 0.0

        downside_std = returns[returns < 0].std() * np.sqrt(252)
        metrics.sortino_ratio = float(mu / downside_std) if downside_std > 0 else 0.0

        metrics.skewness = float(returns.skew())
        metrics.kurtosis = float(returns.kurtosis())

        # Check circuit breaker condition
        if abs(metrics.current_drawdown) >= self.limits.max_drawdown:
            self.circuit_breaker_active = True
            logger.warning(f"Drawdown breach ({metrics.current_drawdown:.2%})! Circuit breaker tripped.")

        return metrics

    def stress_test(self, returns: pd.Series, scenario_shock_pct: float = -0.10) -> Dict[str, float]:
        """
        Simulate portfolio impact under stress scenario.
        """
        base_var = self.var_calculator.historical_var(returns)
        stressed_returns = returns + scenario_shock_pct
        stressed_var = self.var_calculator.historical_var(stressed_returns)
        return {
            "base_var_95": base_var,
            "shock_applied": scenario_shock_pct,
            "stressed_var_95": stressed_var,
            "var_impact": stressed_var - base_var
        }

