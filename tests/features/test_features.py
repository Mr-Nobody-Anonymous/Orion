"""Tests for the technical feature pipeline."""

from __future__ import annotations

import random
import math

import pytest

from orion.prediction.features import (
    FeatureContext,
    FeatureProvider,
    FeatureValidationError,
    assert_no_lookahead,
    build_feature_matrix,
    default_registry,
    provider_status,
    validate_no_lookahead,
)
from orion.prediction.features.technical import (
    adx,
    atr,
    bollinger_width,
    ema,
    macd,
    momentum,
    provider,
    rsi,
    sma,
    stochastic_k,
    volume_ratio,
)


def make_series(length: int, *, seed: int = 0):
    rng = random.Random(seed)
    closes = tuple(100.0 + rng.random() for _ in range(length))
    highs = tuple(c + rng.random() * 0.3 for c in closes)
    lows = tuple(c - rng.random() * 0.3 for c in closes)
    volumes = tuple(1000.0 + rng.random() * 100 for _ in range(length))
    return closes, highs, lows, volumes


def test_provider_reports_live_status() -> None:
    status = provider()
    assert status.name == "technical"
    assert status.version == "1.0.0"
    # TA-Lib 0.6.8 is installed on this machine; the provider must say so.
    assert status.available is True
    assert "TA-Lib" in status.detail


def test_provider_status_aggregates_backends() -> None:
    aggregated = provider_status()
    assert "technical" in aggregated
    assert isinstance(aggregated["technical"], FeatureProvider)


def test_default_registry_has_unique_names() -> None:
    registry = default_registry()
    names = registry.names()
    assert names
    assert len(set(names)) == len(names)
    assert "rsi_14" in names and "atr_14" in names and "macd_12_26_9" in names


def test_feature_meta_rejects_uses_future() -> None:
    from orion.prediction.features import FeatureMeta

    with pytest.raises(ValueError):
        FeatureMeta(name="bad", version="1.0.0", lookback=1,
                     formula="x", source="x", uses_future=True)


def test_rsi_matches_reference() -> None:
    # On a strictly rising series RSI should be 100.
    closes = tuple(100.0 + i for i in range(20))
    ctx = FeatureContext(closes=closes, highs=closes, lows=closes, opens=closes,
                          volumes=tuple(0.0 for _ in closes), index=len(closes) - 1)
    assert rsi(ctx) == pytest.approx(100.0)


def test_sma_insufficient_history() -> None:
    closes = (1.0, 2.0, 3.0)
    ctx = FeatureContext(closes=closes, highs=closes, lows=closes, opens=closes,
                          volumes=tuple(0.0 for _ in closes), index=2)
    assert sma(ctx, period=3) == pytest.approx(2.0)
    # period > index+1 is impossible at the FeatureContext level
    with pytest.raises(ValueError):
        sma(FeatureContext(closes=closes, highs=closes, lows=closes, opens=closes,
                            volumes=tuple(0.0 for _ in closes), index=2), period=4)


def test_ema_warmup() -> None:
    closes = (1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0)
    ctx = FeatureContext(closes=closes, highs=closes, lows=closes, opens=closes,
                          volumes=tuple(0.0 for _ in closes), index=9)
    value = ema(ctx, period=10)
    assert value is not None
    assert 0.0 < value < 100.0


def test_macd_and_roc_shapes() -> None:
    closes, highs, lows, volumes = make_series(60, seed=1)
    ctx = FeatureContext(closes=closes, highs=highs, lows=lows, opens=closes,
                          volumes=volumes, index=59)
    assert macd(ctx) is not None
    assert atr(ctx) is not None
    assert bollinger_width(ctx) is not None
    assert adx(ctx) is not None
    assert stochastic_k(ctx) is not None
    assert momentum(ctx) is not None
    assert volume_ratio(ctx) is not None


def test_build_feature_matrix_warmup() -> None:
    registry = default_registry()
    closes, highs, lows, volumes = make_series(80, seed=2)
    rows, indices = build_feature_matrix(registry.all(), closes, highs, lows, closes, volumes)
    assert rows
    assert len(indices) == len(rows)
    # EMA-20 + RSI-14 + ADX-14 push the warmup past bar 35.
    assert indices[0] >= 30
    assert len(rows[0]) == len(registry.names())


def test_build_feature_matrix_short_series() -> None:
    registry = default_registry()
    rows, indices = build_feature_matrix(registry.all(), (100.0, 101.0, 102.0))
    assert rows == []
    assert indices == ()


def test_validate_no_lookahead_passes_for_default_registry() -> None:
    registry = default_registry()
    validate_no_lookahead(registry.all())


def test_feature_with_future_read_is_rejected() -> None:
    from orion.prediction.features import Feature, FeatureMeta

    def cheating(ctx: FeatureContext) -> float:
        return ctx.closes[ctx.index + 1]  # reads the future

    bad = Feature(FeatureMeta("cheat", "1.0.0", 0, "looks at the next bar", "test"),
                  cheating)
    with pytest.raises(FeatureValidationError):
        assert_no_lookahead(bad)


def test_assert_no_lookahead_accepts_none() -> None:
    from orion.prediction.features import Feature, FeatureMeta

    def returns_none(_ctx: FeatureContext) -> float | None:
        return None

    f = Feature(FeatureMeta("noop", "1.0.0", 0, "always None", "test"), returns_none)
    # Should not raise.
    assert_no_lookahead(f)
