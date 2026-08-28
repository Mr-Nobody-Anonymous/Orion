"""Built-in ORION tools wired to canonical capabilities.

Each tool is a thin, argument-validating wrapper over an existing module.
Tools perform no I/O beyond what their underlying capability already does.
"""

from __future__ import annotations

from typing import Any, Sequence

from ...mathematics import black_scholes_price, historical_var, linear_regression
from ...backtesting.engine import vectorized_momentum_backtest
from ...backtesting.evaluation import performance_metrics
from ...simulation import bootstrap_market_paths
from ...world_model import classify_regime
from .registry import ToolPermission, ToolRegistry, ToolSpec


def safe_calculator(expression: str) -> float:
    """Evaluate a restricted arithmetic expression (numbers, + - * / ** () only)."""
    import ast
    import operator

    allowed_operators = {
        ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.Pow: operator.pow, ast.USub: operator.neg,
        ast.UAdd: operator.pos, ast.Mod: operator.mod,
    }

    def evaluate(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return evaluate(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.BinOp) and type(node.op) in allowed_operators:
            return allowed_operators[type(node.op)](evaluate(node.left), evaluate(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in allowed_operators:
            return allowed_operators[type(node.op)](evaluate(node.operand))
        raise ValueError(f"disallowed expression element: {ast.dump(node)[:60]}")

    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as error:
        raise ValueError(f"invalid expression: {error.msg}") from error
    result = evaluate(tree)
    if isinstance(result, complex):
        raise ValueError("complex results are not supported")
    return result


def statistics_tool(values: Sequence[float], statistic: str = "mean") -> float:
    """Compute a summary statistic over a numeric series."""
    if not values:
        raise ValueError("values must be non-empty")
    n = len(values)
    mean = sum(values) / n
    if statistic == "mean":
        return mean
    if statistic == "variance":
        return sum((v - mean) ** 2 for v in values) / n
    if statistic == "stdev":
        return (sum((v - mean) ** 2 for v in values) / n) ** 0.5
    if statistic == "min":
        return min(values)
    if statistic == "max":
        return max(values)
    if statistic == "var_95":
        return historical_var(values, confidence=0.95)
    raise ValueError(f"unknown statistic: {statistic}")


def regression_tool(x: Sequence[float], y: Sequence[float]) -> dict[str, float]:
    result = linear_regression(x, y)
    return {"slope": result.slope, "intercept": result.intercept, "r_squared": result.r_squared, "n": float(result.n)}


def backtest_tool(prices: Sequence[float], lookback: int = 3) -> dict[str, Any]:
    result = vectorized_momentum_backtest(prices, lookback=lookback)
    metrics = performance_metrics(prices, result)
    return {
        "total_return": float(result.total_return),
        "trades": result.trades,
        "transaction_costs": float(result.transaction_costs),
        "sharpe": float(metrics.sharpe),
        "max_drawdown": float(metrics.max_drawdown),
        "win_rate": float(metrics.win_rate),
    }


def simulate_tool(prices: Sequence[float], paths: int = 50, horizon: int = 20, seed: int = 7) -> dict[str, float]:
    result = bootstrap_market_paths(prices, paths=paths, horizon=horizon, seed=seed)
    return {"terminal_mean": result.terminal_mean, "terminal_p05": result.terminal_p05, "terminal_p95": result.terminal_p95}


def regime_tool(prices: Sequence[float]) -> dict[str, Any]:
    assessment = classify_regime(prices)
    return assessment.as_dict()


def pricing_tool(spot: float, strike: float, maturity: float, rate: float, volatility: float,
                 option_type: str = "call") -> float:
    return black_scholes_price(spot, strike, maturity, rate, volatility, option_type=option_type)


def memory_tool(memory: Any, query: str, limit: int = 3) -> list[dict[str, Any]]:
    items = memory.retrieve(query, limit=limit)
    return [{"summary": item.summary, "layer": item.layer.value, "importance": item.importance} for item in items]


def register_builtin_tools(registry: ToolRegistry, *, memory: Any | None = None) -> None:
    """Install the standard ORION tool set into a registry."""
    registry.register(ToolSpec("calculator", "Restricted arithmetic evaluation",
                               ToolPermission.COMPUTE, safe_calculator))
    registry.register(ToolSpec("statistics", "Summary statistics over a numeric series",
                               ToolPermission.COMPUTE, statistics_tool))
    registry.register(ToolSpec("regression", "OLS regression of y on x",
                               ToolPermission.COMPUTE, regression_tool))
    registry.register(ToolSpec("backtest", "Vectorized momentum backtest with metrics",
                               ToolPermission.BACKTEST, backtest_tool))
    registry.register(ToolSpec("simulate", "Seeded bootstrap market simulation",
                               ToolPermission.SIMULATION, simulate_tool))
    registry.register(ToolSpec("regime", "Market regime classification",
                               ToolPermission.MARKET_DATA, regime_tool))
    registry.register(ToolSpec("option_price", "Black-Scholes option price",
                               ToolPermission.PRICING, pricing_tool))
    if memory is not None:
        registry.register(ToolSpec("memory_search", "Retrieve relevant memories",
                                   ToolPermission.MEMORY, lambda query, limit=3: memory_tool(memory, query, limit)))
