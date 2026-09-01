"""Reproducible out-of-sample backtest on a frozen holdout (P3-2).

The P3-2 deliverable is the *evidence* that turns ORION's
implementation into a claim that can be checked.  Without a
reproducible out-of-sample run, every other P-tier claim is
unverified.

This module provides the smallest piece that earns the right to
say "ORION beats the factor-neutral baseline on the frozen
holdout":

* :data:`FROZEN_HOLDOUT` — a fixed, byte-stable price series of 300
  bars.  The bytes are part of the public contract; modifying the
  series breaks any downstream backtest that pinned itself to a
  specific value.
* :func:`run_frozen_backtest` — runs the ORION ensemble predictor
  plus the canonical baseline strategies
  (:class:`BuyAndHold`, :class:`MomentumStrategy`,
  :class:`MeanReversionStrategy`, :class:`FactorNeutralBaseline`,
  :class:`RandomNullStrategy`) on the frozen holdout and returns a
  structured :class:`FrozenHoldoutResult`.
* :func:`write_frozen_artifact` — writes the result + the literal
  holdout bytes + the config to a directory, so the operator can
  diff two runs and prove reproducibility.

The runner is intentionally not a new backtesting engine — it
reuses :mod:`orion.evaluation.baselines_strategies.run_backtest`
and :mod:`orion.evaluation.lab.make_orion_predictor` so the
methodology is one-source-of-truth with the rest of the
evaluation lab.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from .baselines_strategies import (
    BacktestResult,
    BuyAndHold,
    FactorNeutralBaseline,
    MeanReversionStrategy,
    MomentumStrategy,
    RandomNullStrategy,
    run_backtest,
)
from .lab import make_orion_predictor


def _seeded_synthetic_series(n: int = 300, *, seed: int = 0x4F52_1040) -> list[float]:
    """Build a deterministic, reproducible 300-bar price series."""
    import math
    import random as _random

    rng = _random.Random(seed)
    out: list[float] = []
    price = 100.0
    for i in range(n):
        drift = 0.0003
        wave = 0.012 * math.sin(i * 0.37)
        shock = rng.gauss(0.0, 0.006)
        # Regime break around bar 150 to test cross-regime robustness.
        if 140 <= i < 160:
            shock -= 0.004
        price *= 1.0 + drift + wave + shock
        out.append(round(price, 6))
    return out


# Frozen holdout. The bytes are part of the public contract.
FROZEN_HOLDOUT: tuple[float, ...] = tuple(_seeded_synthetic_series())
HOLDOUT_SCHEMA_VERSION = 1


def _holdout_bytes_hash(prices: Sequence[float]) -> str:
    raw = json.dumps(list(prices), separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True, slots=True)
class FrozenHoldoutResult:
    """A single, reproducible comparison of ORION vs the canonical baselines."""

    schema_version: int
    holdout_hash: str
    n_bars: int
    cost_per_trade: float
    initial_equity: float
    orion: dict[str, Any] | None
    baselines: dict[str, dict[str, Any]]
    as_of: str = field(default_factory=lambda: datetime.now(tz=timezone.utc).isoformat())

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "holdout_hash": self.holdout_hash,
            "n_bars": self.n_bars,
            "cost_per_trade": self.cost_per_trade,
            "initial_equity": self.initial_equity,
            "as_of": self.as_of,
            "orion": self.orion,
            "baselines": self.baselines,
        }

    def beats_factor_neutral(self) -> bool:
        """``True`` iff ORION's final equity strictly beats the factor-neutral baseline."""
        if not self.orion:
            return False
        orion_equity = float(self.orion.get("final_equity", 0.0))
        neutral_entry = self.baselines.get("factor_neutral")
        if not neutral_entry:
            return False
        neutral_equity = float(neutral_entry.get("final_equity", 0.0))
        return orion_equity > neutral_equity


def _baseline_suite() -> tuple[Any, ...]:
    return (
        BuyAndHold(),
        MomentumStrategy(),
        MeanReversionStrategy(),
        FactorNeutralBaseline(),
        RandomNullStrategy(seed=42),
    )


def _run_orion_backtest(
    system,
    asset,
    prices: Sequence[float],
    *,
    cost_per_trade: float,
    initial_equity: float,
) -> dict[str, Any] | None:
    """Run ORION as a strategy against the frozen holdout.

    ORION's native interface is :meth:`OrionSystem.evaluate`, which
    returns a dict per cycle. We fold each cycle's signal into a
    strategy-level backtest by mapping the per-bar ``prediction`` to
    a target position. To keep this dependency-light and
    deterministic, we use a thin shim: long when ORION's expected
    return is positive, flat otherwise.
    """
    predictor = make_orion_predictor(system, asset)

    class _OrionStrategy:
        name = "orion"

        def position(self, _prices: Sequence[float], index: int) -> float:
            window = list(_prices[: index + 1])
            if len(window) < 6:
                return 0.0
            pred = predictor(window)
            return 1.0 if pred > 0.0 else 0.0

    try:
        result: BacktestResult = run_backtest(
            _OrionStrategy(),
            prices,
            cost_per_trade=cost_per_trade,
            initial_equity=initial_equity,
        )
    except Exception as exc:  # noqa: BLE001
        return {"status": "UNAVAILABLE", "reason": str(exc)}
    return {
        "strategy": result.strategy,
        "final_equity": result.final_equity,
        "n_periods": result.n_periods,
        "n_trades": result.n_trades,
        "cost_per_trade": result.cost_per_trade,
        "metrics": dict(result.metrics),
        "equity_curve": list(result.equity_curve),
    }


def run_frozen_backtest(
    system,
    asset,
    *,
    cost_per_trade: float = 0.001,
    initial_equity: float = 1.0,
    prices: Sequence[float] | None = None,
) -> FrozenHoldoutResult:
    """Run ORION + canonical baselines on the frozen holdout.

    The result is reproducible byte-for-byte as long as
    :data:`FROZEN_HOLDOUT` is not modified and ``system`` is
    constructed with the same config (so the seed is stable).
    """
    series = list(prices) if prices is not None else list(FROZEN_HOLDOUT)

    baselines: dict[str, dict[str, Any]] = {}
    for strategy in _baseline_suite():
        result = run_backtest(
            strategy,
            series,
            cost_per_trade=cost_per_trade,
            initial_equity=initial_equity,
        )
        baselines[strategy.name] = {
            "strategy": result.strategy,
            "final_equity": result.final_equity,
            "n_periods": result.n_periods,
            "n_trades": result.n_trades,
            "cost_per_trade": result.cost_per_trade,
            "metrics": dict(result.metrics),
            "equity_curve": list(result.equity_curve),
        }

    orion_payload = _run_orion_backtest(
        system,
        asset,
        series,
        cost_per_trade=cost_per_trade,
        initial_equity=initial_equity,
    )

    return FrozenHoldoutResult(
        schema_version=HOLDOUT_SCHEMA_VERSION,
        holdout_hash=_holdout_bytes_hash(series),
        n_bars=len(series),
        cost_per_trade=cost_per_trade,
        initial_equity=initial_equity,
        orion=orion_payload,
        baselines=baselines,
    )


def write_frozen_artifact(
    result: FrozenHoldoutResult,
    *,
    artifact_dir: str | Path,
    prices: Sequence[float] | None = None,
) -> Path:
    """Persist a frozen-backtest result to disk.

    The artifact directory contains:

    * ``result.json`` — the :class:`FrozenHoldoutResult` payload.
    * ``holdout.json`` — the literal holdout bytes.
    * ``config.json`` — the schema version + holdout hash + verdict.
    """
    out_dir = Path(artifact_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    series = list(prices) if prices is not None else list(FROZEN_HOLDOUT)
    (out_dir / "holdout.json").write_text(
        json.dumps(series, indent=2), encoding="utf-8"
    )
    (out_dir / "result.json").write_text(
        json.dumps(result.as_dict(), indent=2, default=str), encoding="utf-8"
    )
    config = {
        "schema_version": result.schema_version,
        "holdout_hash": result.holdout_hash,
        "n_bars": result.n_bars,
        "beats_factor_neutral": result.beats_factor_neutral(),
        "as_of": result.as_of,
    }
    (out_dir / "config.json").write_text(
        json.dumps(config, indent=2), encoding="utf-8"
    )
    return out_dir


__all__ = [
    "FROZEN_HOLDOUT",
    "HOLDOUT_SCHEMA_VERSION",
    "FrozenHoldoutResult",
    "run_frozen_backtest",
    "write_frozen_artifact",
]